from __future__ import annotations

import argparse
import json
import math
import re
import sys
import threading
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import tkinter as tk
from scipy.optimize import minimize
from tkinter import filedialog, messagebox, scrolledtext, ttk

REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_PERTURB_DIR = REPO_ROOT / "TestsAndData" / "test de puissance à résistance perturbation"
DEFAULT_TEC_DIR_CANDIDATES = (
    REPO_ROOT / "TestsAndData" / "test pwm tec",
    REPO_ROOT / "TestsAndData" / "test PWM TEC",
    REPO_ROOT / "TestsAndData" / "echelons pwm tec",
    REPO_ROOT / "TestsAndData" / "echelons tec",
    REPO_ROOT / "TestsAndData" / "tec_pwm_steps",
)
DEFAULT_TEC_DIR = next((path for path in DEFAULT_TEC_DIR_CANDIDATES if path.exists()), DEFAULT_TEC_DIR_CANDIDATES[0])
OUTPUT_FILE = REPO_ROOT / "parametres_calibres_combinee.json"

BASE_PARAMS = {
    "largeur_x_mm": 61.5,
    "longueur_y_mm": 117.5,
    "epaisseur_mm": 1.7,
    "resolution_grille": 12,
    "temperature_ambiante_C": 20.0,
    "diffusivite_alpha": 97.0,
    "masse_volumique_rho": 2.7e-3,
    "chaleur_massique_cp": 0.9,
    "coeff_convection_h": 5.353e-5,
    "pos_x_capteur_1_mm": 0.0,
    "pos_y_capteur_1_mm": 14.57,
    "pos_x_capteur_2_mm": 0.0,
    "pos_y_capteur_2_mm": 59.42,
    "pos_x_capteur_3_mm": 0.0,
    "pos_y_capteur_3_mm": 103.79,
    "pos_x_tec_mm": 0.0,
    "pos_y_tec_mm": 5.0,
    "pos_x_resistance_mm": 0.0,
    "pos_y_resistance_mm": 38.0,
}

PERTURBATION_EXPERIMENT_SPECS = [
    {"keywords": ("0.81", "4.5"), "power_w": 0.81},
    {"keywords": ("1.44",), "power_w": 1.44},
    {"keywords": ("2.56", "8v"), "power_w": 2.56},
    {"keywords": ("4w", "10v"), "power_w": 4.0},
]

# À remplir si les noms de fichiers TEC n'indiquent pas le PWM.
TEC_EXPERIMENT_SPECS: list[dict[str, object]] = []


@dataclass(frozen=True)
class ThermalExperiment:
    name: str
    source: str  # "perturbation" ou "tec"
    input_level: float  # puissance (W) pour perturbation, PWM (%) pour TEC
    sign: float
    time_s: np.ndarray
    sensor_deltas_c: dict[str, np.ndarray]


def _normalize_name(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9%+\-.]+", " ", ascii_name.lower()).strip()


def _resolve_dir(path: Path, candidates: Iterable[Path]) -> Path:
    probes = [Path(path), *candidates]
    seen: set[Path] = set()
    for probe in probes:
        resolved = probe.resolve(strict=False)
        if resolved in seen:
            continue
        seen.add(resolved)
        if resolved.exists() and resolved.is_dir():
            return resolved
    searched = "\n  - ".join(str(p) for p in seen)
    raise FileNotFoundError(f"Aucun dossier valide trouvé. Emplacements vérifiés :\n  - {searched}")


def _read_csv_flexible(path: Path) -> pd.DataFrame:
    attempts = (
        {"sep": None, "engine": "python"},
        {"sep": ";"},
        {},
    )
    last_error: Exception | None = None
    for kwargs in attempts:
        try:
            df = pd.read_csv(path, **kwargs)
        except Exception as exc:
            last_error = exc
            continue
        if df.shape[1] > 1:
            return df
    if last_error is not None:
        raise ValueError(f"Lecture impossible pour {path.name}: {last_error}") from last_error
    raise ValueError(f"Lecture impossible pour {path.name}")


def _find_column(df: pd.DataFrame, aliases: Iterable[str]) -> str | None:
    normalized_columns = {_normalize_name(str(col)): str(col) for col in df.columns}

    for alias in aliases:
        alias_norm = _normalize_name(alias)
        if alias_norm in normalized_columns:
            return normalized_columns[alias_norm]

    for alias in aliases:
        alias_norm = _normalize_name(alias)
        for normalized, original in normalized_columns.items():
            if alias_norm in normalized or normalized in alias_norm:
                return original

    return None


def _detect_step_start(signal: np.ndarray) -> int:
    if len(signal) < 8:
        return 0

    window = min(len(signal) if len(signal) % 2 == 1 else len(signal) - 1, 11)
    window = max(window, 3)
    smooth = pd.Series(signal).rolling(window=window, center=True, min_periods=1).mean().to_numpy()
    diffs = np.abs(np.diff(smooth))
    search_limit = max(5, min(len(diffs), int(0.4 * len(diffs))))

    if search_limit <= 0 or float(np.max(diffs[:search_limit])) < 1e-4:
        return 0
    return int(np.argmax(diffs[:search_limit]))


def _extract_power_w(normalized_name: str) -> float | None:
    match = re.search(r"([+-]?\d+(?:[\.,]\d+)?)\s*w\b", normalized_name)
    if match:
        return float(match.group(1).replace(",", "."))
    return None


def _extract_pwm_percent(normalized_name: str) -> float | None:
    patterns = [
        r"pwm\s*([+-]?\d+(?:[\.,]\d+)?)",
        r"([+-]?\d+(?:[\.,]\d+)?)\s*%",
    ]
    for pattern in patterns:
        match = re.search(pattern, normalized_name)
        if match:
            return float(match.group(1).replace(",", "."))
    return None


def _infer_tec_sign(normalized_name: str, pwm_value: float) -> tuple[float, float]:
    if pwm_value < 0:
        return abs(pwm_value), -1.0
    negative_hints = ("refroid", "cool", "froid", "negative", "negatif", "neg")
    if any(hint in normalized_name for hint in negative_hints):
        return pwm_value, -1.0
    return pwm_value, 1.0


def pwm_percent_to_power_w(pwm_percent: float) -> float:
    pwm = float(np.clip(abs(pwm_percent), 0.0, 100.0))
    return (((1.703277e-05 * pwm + 9.947817e-04) * pwm) + 1.406312e-01) * pwm + 1.734031e-02


def _load_common_csv(path: Path, max_time_s: float, downsample: int) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    df = _read_csv_flexible(path)
    time_col = _find_column(df, ("Temps_s", "Temps", "time_s", "time"))
    if time_col is None:
        raise ValueError(f"Impossible de trouver la colonne de temps dans {path.name}")

    sensor_columns: dict[str, str] = {}
    for sensor_name in ("T1", "T2", "T3"):
        found = _find_column(df, (sensor_name, f"{sensor_name}_C", f"{sensor_name} (C)"))
        if found is not None:
            sensor_columns[sensor_name] = found

    if not sensor_columns:
        raise ValueError(f"Aucune colonne T1/T2/T3 détectée dans {path.name}")

    numeric_cols = [time_col, *sensor_columns.values()]
    df = df[numeric_cols].apply(pd.to_numeric, errors="coerce").dropna().copy()
    if df.empty:
        raise ValueError(f"Les données de {path.name} sont vides après nettoyage")

    ref_signal = df[list(sensor_columns.values())].mean(axis=1).to_numpy(dtype=float)
    start_idx = _detect_step_start(ref_signal)

    df = df.iloc[start_idx:].copy()
    time_s = df[time_col].to_numpy(dtype=float)
    time_s = time_s - time_s[0]
    mask = time_s <= min(max_time_s, float(time_s[-1]))
    step = max(1, int(downsample))
    time_s = time_s[mask][::step]

    sensor_deltas: dict[str, np.ndarray] = {}
    for sensor_name, column_name in sensor_columns.items():
        values = df[column_name].to_numpy(dtype=float)[mask]
        sensor_deltas[sensor_name] = (values - values[0])[::step]

    return time_s, sensor_deltas


def load_perturbation_experiments(
    data_dir: Path = DEFAULT_PERTURB_DIR,
    max_time_s: float = 600.0,
    downsample: int = 50,
) -> list[ThermalExperiment]:
    resolved_dir = _resolve_dir(
        data_dir,
        [DEFAULT_PERTURB_DIR, REPO_ROOT / data_dir.name, REPO_ROOT / "TestsAndData" / data_dir.name],
    )
    csv_files = sorted(path for path in resolved_dir.glob("*.csv") if path.is_file())
    matches: list[tuple[Path, float]] = []

    for spec in PERTURBATION_EXPERIMENT_SPECS:
        keywords = tuple(str(keyword).lower() for keyword in spec["keywords"])
        for path in csv_files:
            normalized = _normalize_name(path.name)
            if all(keyword in normalized for keyword in keywords):
                matches.append((path, float(spec["power_w"])))
                break

    if not matches:
        for path in csv_files:
            power_w = _extract_power_w(_normalize_name(path.stem))
            if power_w is not None:
                matches.append((path, power_w))

    if not matches:
        raise FileNotFoundError(f"Aucun CSV de perturbation exploitable n'a été trouvé dans {resolved_dir}")

    experiments: list[ThermalExperiment] = []
    for path, power_w in matches:
        time_s, sensor_deltas = _load_common_csv(path, max_time_s=max_time_s, downsample=downsample)
        filtered = {name: values for name, values in sensor_deltas.items() if name in {"T2", "T3", "T1"}}
        experiments.append(
            ThermalExperiment(
                name=path.name,
                source="perturbation",
                input_level=float(power_w),
                sign=1.0,
                time_s=time_s,
                sensor_deltas_c=filtered,
            )
        )
    return experiments


def load_tec_experiments(
    data_dir: Path = DEFAULT_TEC_DIR,
    max_time_s: float = 800.0,
    downsample: int = 10,
) -> list[ThermalExperiment]:
    resolved_dir = _resolve_dir(
        data_dir,
        [*DEFAULT_TEC_DIR_CANDIDATES, REPO_ROOT / data_dir.name, REPO_ROOT / "TestsAndData" / data_dir.name],
    )
    csv_files = sorted(path for path in resolved_dir.glob("*.csv") if path.is_file())
    matches: list[tuple[Path, float, float]] = []

    if TEC_EXPERIMENT_SPECS:
        for spec in TEC_EXPERIMENT_SPECS:
            keywords = tuple(str(keyword).lower() for keyword in spec["keywords"])
            for path in csv_files:
                normalized = _normalize_name(path.name)
                if all(keyword in normalized for keyword in keywords):
                    matches.append((path, float(spec["pwm_percent"]), float(spec.get("sign", 1.0))))
                    break
    else:
        for path in csv_files:
            normalized = _normalize_name(path.stem)
            pwm_percent = _extract_pwm_percent(normalized)
            if pwm_percent is None:
                continue
            pwm_percent, sign = _infer_tec_sign(normalized, pwm_percent)
            matches.append((path, pwm_percent, sign))

    if not matches:
        raise FileNotFoundError(
            "Aucun CSV TEC exploitable n'a été trouvé.\n"
            f"Dossier inspecté : {resolved_dir}\n"
            "Nommer les fichiers avec le PWM (ex. `pwm_20_chauffe.csv` ou `pwm_-15_refroid.csv`)\n"
            "ou remplir `TEC_EXPERIMENT_SPECS` en haut du script."
        )

    experiments: list[ThermalExperiment] = []
    for path, pwm_percent, sign in matches:
        time_s, sensor_deltas = _load_common_csv(path, max_time_s=max_time_s, downsample=downsample)
        experiments.append(
            ThermalExperiment(
                name=path.name,
                source="tec",
                input_level=float(pwm_percent),
                sign=float(sign),
                time_s=time_s,
                sensor_deltas_c=sensor_deltas,
            )
        )
    return experiments


def _simulate_response(
    target_times: np.ndarray,
    diffusivite_alpha: float,
    coeff_convection_h: float,
    chaleur_massique_cp: float,
    tec_power_w: float = 0.0,
    tec_tau_s: float = 0.0,
    perturb_power_w: float = 0.0,
    perturb_tau_s: float = 0.0,
) -> dict[str, np.ndarray]:
    p = BASE_PARAMS
    resolution = int(p["resolution_grille"])
    pas_x = p["largeur_x_mm"] / resolution
    pas_y = p["longueur_y_mm"] / resolution
    rho = p["masse_volumique_rho"]
    epaisseur = p["epaisseur_mm"]

    dt_stable = 0.5 / (diffusivite_alpha * ((1 / pas_x**2) + (1 / pas_y**2)))
    pas_temps = min(0.15 * min(pas_x, pas_y) ** 2 / diffusivite_alpha, dt_stable)

    cst_diffusion_x = diffusivite_alpha * pas_temps / pas_x**2
    cst_diffusion_y = diffusivite_alpha * pas_temps / pas_y**2
    cst_convection = coeff_convection_h * pas_temps / (rho * chaleur_massique_cp * epaisseur)
    volume_module_tec = (2 * pas_x) * (2 * pas_y) * epaisseur
    denominateur_resistance = rho * chaleur_massique_cp * epaisseur * pas_x * pas_y

    def coord_x_vers_indice(coord_x: float) -> int:
        indice = int(round((coord_x + p["largeur_x_mm"] / 2) / pas_x))
        return int(np.clip(indice, 0, resolution))

    def coord_y_vers_indice(coord_y: float) -> int:
        indice = int(round(coord_y / pas_y))
        return int(np.clip(indice, 0, resolution))

    def creer_zone_source(idx_y: int, idx_x: int) -> tuple[slice, slice]:
        y_debut = max(0, idx_y)
        y_fin = min(resolution + 1, idx_y + 2)
        x_debut = max(0, idx_x - 1)
        x_fin = min(resolution + 1, idx_x + 1)
        return np.s_[y_debut:y_fin, x_debut:x_fin]

    idx_t1 = (coord_y_vers_indice(p["pos_y_capteur_1_mm"]), coord_x_vers_indice(p["pos_x_capteur_1_mm"]))
    idx_t2 = (coord_y_vers_indice(p["pos_y_capteur_2_mm"]), coord_x_vers_indice(p["pos_x_capteur_2_mm"]))
    idx_t3 = (coord_y_vers_indice(p["pos_y_capteur_3_mm"]), coord_x_vers_indice(p["pos_x_capteur_3_mm"]))
    zone_tec = creer_zone_source(coord_y_vers_indice(p["pos_y_tec_mm"]), coord_x_vers_indice(p["pos_x_tec_mm"]))
    zone_res = creer_zone_source(coord_y_vers_indice(p["pos_y_resistance_mm"]), coord_x_vers_indice(p["pos_x_resistance_mm"]))

    matrice_t = np.zeros((resolution + 1, resolution + 1), dtype=np.float64)
    matrice_t_suivante = matrice_t.copy()

    tec_effective = 0.0
    res_effective = 0.0
    temps_courant = 0.0

    t1_out: list[float] = []
    t2_out: list[float] = []
    t3_out: list[float] = []

    for temps_cible in target_times:
        while temps_courant < temps_cible:
            if tec_tau_s > 0:
                coeff_lag_tec = min(1.0, pas_temps / tec_tau_s)
                tec_effective += (tec_power_w - tec_effective) * coeff_lag_tec
            else:
                tec_effective = tec_power_w

            if perturb_tau_s > 0:
                coeff_lag_res = min(1.0, pas_temps / perturb_tau_s)
                res_effective += (perturb_power_w - res_effective) * coeff_lag_res
            else:
                res_effective = perturb_power_w

            ajout_temp_tec = ((tec_effective / volume_module_tec) * pas_temps) / (rho * chaleur_massique_cp)
            ajout_temp_resistance = (res_effective * pas_temps) / denominateur_resistance

            matrice_t_suivante[1:-1, 1:-1] = matrice_t[1:-1, 1:-1] + (
                cst_diffusion_x * (matrice_t[1:-1, 2:] - 2 * matrice_t[1:-1, 1:-1] + matrice_t[1:-1, :-2])
                + cst_diffusion_y * (matrice_t[2:, 1:-1] - 2 * matrice_t[1:-1, 1:-1] + matrice_t[:-2, 1:-1])
            )
            matrice_t_suivante[1:-1, 1:-1] -= cst_convection * matrice_t[1:-1, 1:-1]

            if tec_power_w != 0.0:
                matrice_t_suivante[zone_tec] += ajout_temp_tec
            if perturb_power_w != 0.0:
                matrice_t_suivante[zone_res] += ajout_temp_resistance

            matrice_t_suivante[0, :] = matrice_t_suivante[1, :]
            matrice_t_suivante[-1, :] = matrice_t_suivante[-2, :]
            matrice_t_suivante[:, 0] = matrice_t_suivante[:, 1]
            matrice_t_suivante[:, -1] = matrice_t_suivante[:, -2]

            matrice_t, matrice_t_suivante = matrice_t_suivante, matrice_t
            temps_courant += pas_temps

        t1_out.append(float(matrice_t[idx_t1]))
        t2_out.append(float(matrice_t[idx_t2]))
        t3_out.append(float(matrice_t[idx_t3]))

    return {"T1": np.array(t1_out), "T2": np.array(t2_out), "T3": np.array(t3_out)}


def simulate_perturbation_response(
    power_w: float,
    target_times: np.ndarray,
    diffusivite_alpha: float,
    coeff_convection_h: float,
    chaleur_massique_cp: float,
    facteur_couplage_perturbation: float,
    tau_perturbation_s: float,
) -> dict[str, np.ndarray]:
    return _simulate_response(
        target_times=target_times,
        diffusivite_alpha=diffusivite_alpha,
        coeff_convection_h=coeff_convection_h,
        chaleur_massique_cp=chaleur_massique_cp,
        perturb_power_w=max(0.0, power_w * facteur_couplage_perturbation),
        perturb_tau_s=tau_perturbation_s,
    )


def simulate_tec_response(
    pwm_percent: float,
    sign: float,
    target_times: np.ndarray,
    diffusivite_alpha: float,
    coeff_convection_h: float,
    chaleur_massique_cp: float,
    facteur_couplage_tec: float,
    tau_tec_s: float,
) -> dict[str, np.ndarray]:
    return _simulate_response(
        target_times=target_times,
        diffusivite_alpha=diffusivite_alpha,
        coeff_convection_h=coeff_convection_h,
        chaleur_massique_cp=chaleur_massique_cp,
        tec_power_w=sign * facteur_couplage_tec * pwm_percent_to_power_w(pwm_percent),
        tec_tau_s=tau_tec_s,
    )


def evaluate_rmse(experiments: Iterable[ThermalExperiment], **params: float) -> float:
    branch_errors: dict[str, list[float]] = {"perturbation": [], "tec": []}

    for exp in experiments:
        if exp.source == "perturbation":
            sim = simulate_perturbation_response(
                power_w=exp.input_level,
                target_times=exp.time_s,
                diffusivite_alpha=params["diffusivite_alpha"],
                coeff_convection_h=params["coeff_convection_h"],
                chaleur_massique_cp=params["chaleur_massique_cp"],
                facteur_couplage_perturbation=params["facteur_couplage_perturbation"],
                tau_perturbation_s=params["tau_perturbation_s"],
            )
        elif exp.source == "tec":
            sim = simulate_tec_response(
                pwm_percent=exp.input_level,
                sign=exp.sign,
                target_times=exp.time_s,
                diffusivite_alpha=params["diffusivite_alpha"],
                coeff_convection_h=params["coeff_convection_h"],
                chaleur_massique_cp=params["chaleur_massique_cp"],
                facteur_couplage_tec=params["facteur_couplage_tec"],
                tau_tec_s=params["tau_tec_s"],
            )
        else:
            raise ValueError(f"Type d'expérience inconnu: {exp.source}")

        for sensor_name, measured in exp.sensor_deltas_c.items():
            if sensor_name in sim:
                branch_errors[exp.source].append(float(np.mean((sim[sensor_name] - measured) ** 2)))

    active_branch_errors = [np.mean(values) for values in branch_errors.values() if values]
    if not active_branch_errors:
        raise ValueError("Aucune erreur de calibration n'a pu être calculée")
    return math.sqrt(float(np.mean(active_branch_errors)))


def load_all_experiments(
    perturb_dir: Path | None,
    tec_dir: Path | None,
    perturb_max_time_s: float,
    tec_max_time_s: float,
    perturb_downsample: int,
    tec_downsample: int,
) -> list[ThermalExperiment]:
    experiments: list[ThermalExperiment] = []
    errors: list[str] = []

    if perturb_dir is not None:
        try:
            experiments.extend(
                load_perturbation_experiments(
                    data_dir=perturb_dir,
                    max_time_s=perturb_max_time_s,
                    downsample=perturb_downsample,
                )
            )
        except Exception as exc:
            errors.append(f"Perturbation: {exc}")

    if tec_dir is not None:
        try:
            experiments.extend(
                load_tec_experiments(
                    data_dir=tec_dir,
                    max_time_s=tec_max_time_s,
                    downsample=tec_downsample,
                )
            )
        except Exception as exc:
            errors.append(f"TEC: {exc}")

    if not experiments:
        details = "\n".join(errors) if errors else "Aucune source d'essais n'a été fournie."
        raise FileNotFoundError(f"Impossible de charger des expériences.\n{details}")

    return experiments


def calibrate_combined(experiments: Iterable[ThermalExperiment]) -> dict:
    experiments = list(experiments)
    if not experiments:
        raise ValueError("Aucun essai chargé pour la calibration combinée")

    baseline = {
        "diffusivite_alpha": BASE_PARAMS["diffusivite_alpha"],
        "coeff_convection_h": BASE_PARAMS["coeff_convection_h"],
        "chaleur_massique_cp": BASE_PARAMS["chaleur_massique_cp"],
        "facteur_couplage_perturbation": 1.0,
        "tau_perturbation_s": 8.0,
        "facteur_couplage_tec": 1.0,
        "tau_tec_s": 6.0,
    }
    baseline_rmse = evaluate_rmse(experiments, **baseline)

    def objective(vector: np.ndarray) -> float:
        values = {
            "diffusivite_alpha": float(vector[0]),
            "coeff_convection_h": float(vector[1]),
            "chaleur_massique_cp": float(vector[2]),
            "facteur_couplage_perturbation": float(vector[3]),
            "tau_perturbation_s": float(vector[4]),
            "facteur_couplage_tec": float(vector[5]),
            "tau_tec_s": float(vector[6]),
        }
        if (
            values["diffusivite_alpha"] <= 0
            or values["coeff_convection_h"] <= 0
            or values["chaleur_massique_cp"] <= 0
            or values["facteur_couplage_perturbation"] <= 0
            or values["facteur_couplage_tec"] <= 0
            or values["tau_perturbation_s"] < 0
            or values["tau_tec_s"] < 0
        ):
            return 1e12
        rmse = evaluate_rmse(experiments, **values)
        return rmse**2

    result = minimize(
        objective,
        x0=np.array([
            baseline["diffusivite_alpha"],
            baseline["coeff_convection_h"],
            baseline["chaleur_massique_cp"],
            baseline["facteur_couplage_perturbation"],
            baseline["tau_perturbation_s"],
            baseline["facteur_couplage_tec"],
            baseline["tau_tec_s"],
        ], dtype=float),
        method="L-BFGS-B",
        bounds=[
            (30.0, 220.0),
            (1e-6, 3e-4),
            (0.4, 1.8),
            (0.2, 2.5),
            (0.0, 60.0),
            (0.2, 2.5),
            (0.0, 80.0),
        ],
        options={"maxiter": 35},
    )

    best = {
        "diffusivite_alpha": float(result.x[0]),
        "coeff_convection_h": float(result.x[1]),
        "chaleur_massique_cp": float(result.x[2]),
        "facteur_couplage_perturbation": float(result.x[3]),
        "constante_temps_perturbation_s": float(result.x[4]),
        "facteur_couplage_tec": float(result.x[5]),
        "constante_temps_tec_s": float(result.x[6]),
    }

    best_for_eval = {
        "diffusivite_alpha": best["diffusivite_alpha"],
        "coeff_convection_h": best["coeff_convection_h"],
        "chaleur_massique_cp": best["chaleur_massique_cp"],
        "facteur_couplage_perturbation": best["facteur_couplage_perturbation"],
        "tau_perturbation_s": best["constante_temps_perturbation_s"],
        "facteur_couplage_tec": best["facteur_couplage_tec"],
        "tau_tec_s": best["constante_temps_tec_s"],
    }

    rmse_after = evaluate_rmse(experiments, **best_for_eval)
    usable_solution = math.isfinite(float(result.fun)) and rmse_after <= baseline_rmse + 1e-12

    branches = sorted({exp.source for exp in experiments})
    summary = []
    for exp in experiments:
        detail = {
            "nom": exp.name,
            "source": exp.source,
            "signal": round(exp.input_level, 3),
            "capteurs": sorted(exp.sensor_deltas_c.keys()),
        }
        if exp.source == "perturbation":
            detail["puissance_W"] = round(exp.input_level, 3)
        else:
            detail["pwm_percent"] = round(exp.input_level, 3)
            detail["mode"] = "refroidissement" if exp.sign < 0 else "chauffage"
            detail["puissance_estimee_W"] = round(exp.sign * pwm_percent_to_power_w(exp.input_level), 3)
        summary.append(detail)

    return {
        "success": bool(result.success or usable_solution),
        "optimiseur_reussi": bool(result.success),
        "message": str(result.message),
        "branches_utilisees": branches,
        "nombre_essais": len(experiments),
        "rmse_avant_C": baseline_rmse,
        "rmse_apres_C": rmse_after,
        "parametres": {
            "diffusivite_alpha": round(best["diffusivite_alpha"], 3),
            "coeff_convection_h": round(best["coeff_convection_h"], 8),
            "chaleur_massique_cp": round(best["chaleur_massique_cp"], 4),
            "facteur_couplage_perturbation": round(best["facteur_couplage_perturbation"], 3),
            "constante_temps_perturbation_s": round(best["constante_temps_perturbation_s"], 2),
            "facteur_couplage_tec": round(best["facteur_couplage_tec"], 3),
            "constante_temps_tec_s": round(best["constante_temps_tec_s"], 2),
        },
        "essais": summary,
    }


def _format_experiment_line(exp: ThermalExperiment) -> str:
    if exp.source == "perturbation":
        return f"- [perturbation] {exp.name}: {exp.input_level:.2f} W, capteurs={sorted(exp.sensor_deltas_c.keys())}"

    mode = "refroidissement" if exp.sign < 0 else "chauffage"
    return f"- [tec] {exp.name}: PWM={exp.input_level:.1f} %, {mode}, capteurs={sorted(exp.sensor_deltas_c.keys())}"


def write_calibration_file(report: dict, output_path: Path = OUTPUT_FILE) -> Path:
    payload = {"parametres": report["parametres"], "calibration": report}
    output_path.write_text(json.dumps(payload, indent=4, ensure_ascii=False), encoding="utf-8")
    return output_path


def run_cli(args: argparse.Namespace) -> dict | None:
    perturb_dir = None if args.no_perturb else args.perturb_dir
    tec_dir = None if args.no_tec else args.tec_dir

    experiments = load_all_experiments(
        perturb_dir=perturb_dir,
        tec_dir=tec_dir,
        perturb_max_time_s=args.perturb_max_time_s,
        tec_max_time_s=args.tec_max_time_s,
        perturb_downsample=args.perturb_downsample,
        tec_downsample=args.tec_downsample,
    )

    if args.list_only:
        for exp in experiments:
            print(_format_experiment_line(exp))
        return None

    report = calibrate_combined(experiments)
    output_path = write_calibration_file(report, output_path=args.output)

    print("=== Calibration thermique combinée (perturbation + TEC) ===")
    print(f"Branches utilisées : {', '.join(report['branches_utilisees'])}")
    print(f"Essais utilisés     : {report['nombre_essais']}")
    print(f"RMSE avant          : {report['rmse_avant_C']:.3f} °C")
    print(f"RMSE après          : {report['rmse_apres_C']:.3f} °C")
    print("\nParamètres recommandés pour SimulateurUpgrade.py :")
    for key, value in report["parametres"].items():
        print(f"  - {key} = {value}")
    print(f"\nPreset JSON écrit dans : {output_path}")
    return report


def launch_gui() -> None:
    root = tk.Tk()
    root.title("Calibration thermique combinée")
    root.geometry("980x760")

    use_perturb_var = tk.BooleanVar(value=DEFAULT_PERTURB_DIR.exists())
    use_tec_var = tk.BooleanVar(value=DEFAULT_TEC_DIR.exists())
    perturb_dir_var = tk.StringVar(value=str(DEFAULT_PERTURB_DIR))
    tec_dir_var = tk.StringVar(value=str(DEFAULT_TEC_DIR))
    output_var = tk.StringVar(value=str(OUTPUT_FILE))
    perturb_max_time_var = tk.DoubleVar(value=600.0)
    tec_max_time_var = tk.DoubleVar(value=800.0)
    perturb_downsample_var = tk.IntVar(value=50)
    tec_downsample_var = tk.IntVar(value=10)

    main_frame = ttk.Frame(root, padding=12)
    main_frame.pack(fill="both", expand=True)

    ttk.Label(
        main_frame,
        text="Calibration combinée des essais perturbation + TEC",
        font=("Segoe UI", 12, "bold"),
    ).pack(anchor="w", pady=(0, 10))

    source_frame = ttk.LabelFrame(main_frame, text="Sources de données", padding=10)
    source_frame.pack(fill="x", pady=(0, 10))
    source_frame.columnconfigure(1, weight=1)

    def browse_directory(var: tk.StringVar) -> None:
        initial_dir = str(Path(var.get()).parent) if var.get().strip() else str(REPO_ROOT)
        selected = filedialog.askdirectory(initialdir=initial_dir)
        if selected:
            var.set(selected)

    def browse_output() -> None:
        selected = filedialog.asksaveasfilename(
            title="Fichier JSON de sortie",
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("Tous les fichiers", "*.*")],
            initialdir=str(REPO_ROOT),
            initialfile=Path(output_var.get()).name,
        )
        if selected:
            output_var.set(selected)

    ttk.Checkbutton(source_frame, text="Inclure perturbation", variable=use_perturb_var).grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
    ttk.Entry(source_frame, textvariable=perturb_dir_var).grid(row=0, column=1, sticky="ew", pady=4)
    ttk.Button(source_frame, text="Parcourir...", command=lambda: browse_directory(perturb_dir_var)).grid(row=0, column=2, padx=(8, 0), pady=4)

    ttk.Checkbutton(source_frame, text="Inclure TEC PWM", variable=use_tec_var).grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
    ttk.Entry(source_frame, textvariable=tec_dir_var).grid(row=1, column=1, sticky="ew", pady=4)
    ttk.Button(source_frame, text="Parcourir...", command=lambda: browse_directory(tec_dir_var)).grid(row=1, column=2, padx=(8, 0), pady=4)

    ttk.Label(source_frame, text="Sortie JSON").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=4)
    ttk.Entry(source_frame, textvariable=output_var).grid(row=2, column=1, sticky="ew", pady=4)
    ttk.Button(source_frame, text="Choisir...", command=browse_output).grid(row=2, column=2, padx=(8, 0), pady=4)

    options_frame = ttk.LabelFrame(main_frame, text="Options", padding=10)
    options_frame.pack(fill="x", pady=(0, 10))

    for idx in range(4):
        options_frame.columnconfigure(idx, weight=1 if idx % 2 == 1 else 0)

    ttk.Label(options_frame, text="Perturb max time (s)").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
    ttk.Entry(options_frame, textvariable=perturb_max_time_var, width=12).grid(row=0, column=1, sticky="w", pady=4)
    ttk.Label(options_frame, text="TEC max time (s)").grid(row=0, column=2, sticky="w", padx=(16, 8), pady=4)
    ttk.Entry(options_frame, textvariable=tec_max_time_var, width=12).grid(row=0, column=3, sticky="w", pady=4)

    ttk.Label(options_frame, text="Perturb downsample").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
    ttk.Entry(options_frame, textvariable=perturb_downsample_var, width=12).grid(row=1, column=1, sticky="w", pady=4)
    ttk.Label(options_frame, text="TEC downsample").grid(row=1, column=2, sticky="w", padx=(16, 8), pady=4)
    ttk.Entry(options_frame, textvariable=tec_downsample_var, width=12).grid(row=1, column=3, sticky="w", pady=4)

    button_frame = ttk.Frame(main_frame)
    button_frame.pack(fill="x", pady=(0, 10))

    log_output = scrolledtext.ScrolledText(main_frame, height=22, wrap="word", font=("Consolas", 10))
    log_output.pack(fill="both", expand=True)
    log_output.configure(state="disabled")

    buttons: list[ttk.Button] = []

    def append_log(text: str = "") -> None:
        def _append() -> None:
            log_output.configure(state="normal")
            log_output.insert("end", text + "\n")
            log_output.see("end")
            log_output.configure(state="disabled")
        root.after(0, _append)

    def set_running_state(is_running: bool) -> None:
        def _apply() -> None:
            state = "disabled" if is_running else "normal"
            for button in buttons:
                button.configure(state=state)
        root.after(0, _apply)

    def collect_settings() -> tuple[Path | None, Path | None, Path, float, float, int, int]:
        perturb_dir = None
        tec_dir = None

        if use_perturb_var.get():
            path_str = perturb_dir_var.get().strip()
            if not path_str:
                raise ValueError("Choisir un dossier pour les essais de perturbation.")
            perturb_dir = Path(path_str)

        if use_tec_var.get():
            path_str = tec_dir_var.get().strip()
            if not path_str:
                raise ValueError("Choisir un dossier pour les essais TEC.")
            tec_dir = Path(path_str)

        if perturb_dir is None and tec_dir is None:
            raise ValueError("Activer au moins une source d'essais.")

        output_path = Path(output_var.get().strip() or OUTPUT_FILE)
        return (
            perturb_dir,
            tec_dir,
            output_path,
            float(perturb_max_time_var.get()),
            float(tec_max_time_var.get()),
            int(perturb_downsample_var.get()),
            int(tec_downsample_var.get()),
        )

    def run_action(list_only: bool) -> None:
        try:
            settings = collect_settings()
        except Exception as exc:
            messagebox.showerror("Calibration", str(exc))
            return

        perturb_dir, tec_dir, output_path, perturb_max_time_s, tec_max_time_s, perturb_downsample, tec_downsample = settings

        def worker() -> None:
            set_running_state(True)
            append_log("" if list_only else "=== Lancement de la calibration ===")
            try:
                experiments = load_all_experiments(
                    perturb_dir=perturb_dir,
                    tec_dir=tec_dir,
                    perturb_max_time_s=perturb_max_time_s,
                    tec_max_time_s=tec_max_time_s,
                    perturb_downsample=perturb_downsample,
                    tec_downsample=tec_downsample,
                )

                if list_only:
                    append_log("=== Essais détectés ===")
                    for exp in experiments:
                        append_log(_format_experiment_line(exp))
                    return

                report = calibrate_combined(experiments)
                json_path = write_calibration_file(report, output_path=output_path)

                append_log(f"Branches utilisées : {', '.join(report['branches_utilisees'])}")
                append_log(f"Essais utilisés     : {report['nombre_essais']}")
                append_log(f"RMSE avant          : {report['rmse_avant_C']:.3f} °C")
                append_log(f"RMSE après          : {report['rmse_apres_C']:.3f} °C")
                append_log("Paramètres recommandés :")
                for key, value in report["parametres"].items():
                    append_log(f"  - {key} = {value}")
                append_log(f"JSON écrit dans : {json_path}")
            except Exception as exc:
                append_log(f"Erreur : {exc}")
                root.after(0, lambda: messagebox.showerror("Calibration", str(exc)))
            finally:
                set_running_state(False)

        threading.Thread(target=worker, daemon=True).start()

    list_button = ttk.Button(button_frame, text="Lister les essais", command=lambda: run_action(True))
    run_button = ttk.Button(button_frame, text="Lancer la calibration", command=lambda: run_action(False))
    close_button = ttk.Button(button_frame, text="Fermer", command=root.destroy)
    buttons.extend([list_button, run_button])

    list_button.pack(side="left")
    run_button.pack(side="left", padx=8)
    close_button.pack(side="right")

    append_log("Interface prête. Sélectionner les dossiers puis lancer la calibration.")
    root.mainloop()


def main(argv: list[str] | None = None) -> None:
    if argv is None:
        argv = sys.argv[1:]

    if not argv:
        launch_gui()
        return

    parser = argparse.ArgumentParser(description="Calibration thermique combinée avec essais de perturbation et PWM TEC.")
    parser.add_argument("--perturb-dir", type=Path, default=DEFAULT_PERTURB_DIR, help="Dossier des CSV de perturbation")
    parser.add_argument("--tec-dir", type=Path, default=DEFAULT_TEC_DIR, help="Dossier des CSV TEC PWM")
    parser.add_argument("--no-perturb", action="store_true", help="Ignore les essais de perturbation")
    parser.add_argument("--no-tec", action="store_true", help="Ignore les essais TEC")
    parser.add_argument("--perturb-max-time-s", type=float, default=600.0)
    parser.add_argument("--tec-max-time-s", type=float, default=800.0)
    parser.add_argument("--perturb-downsample", type=int, default=50)
    parser.add_argument("--tec-downsample", type=int, default=10)
    parser.add_argument("--output", type=Path, default=OUTPUT_FILE)
    parser.add_argument("--list-only", action="store_true", help="Affiche seulement les essais détectés")
    parser.add_argument("--gui", action="store_true", help="Ouvre l'interface graphique")
    args = parser.parse_args(argv)

    if args.gui:
        launch_gui()
        return

    run_cli(args)


if __name__ == "__main__":
    main()
