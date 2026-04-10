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
from typing import Callable, Iterable

import numpy as np
import pandas as pd
import tkinter as tk
from scipy.optimize import minimize
from tkinter import filedialog, messagebox, scrolledtext, ttk

REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_PERTURB_DIR = REPO_ROOT / "TestsAndData" / "test de puissance à résistance perturbation"
DEFAULT_TEC_DIR_CANDIDATES = (
    REPO_ROOT / "TestsAndData" / "test de PWM sur TEC",
    REPO_ROOT / "TestsAndData" / "test pwm tec",
    REPO_ROOT / "TestsAndData" / "test PWM TEC",
    REPO_ROOT / "TestsAndData" / "echelons pwm tec",
    REPO_ROOT / "TestsAndData" / "echelons tec",
    REPO_ROOT / "TestsAndData" / "tec_pwm_steps",
)
DEFAULT_TEC_DIR = next((path for path in DEFAULT_TEC_DIR_CANDIDATES if path.exists()), DEFAULT_TEC_DIR_CANDIDATES[0])
OUTPUT_FILE = REPO_ROOT / "parametres_calibres_combinee.json"
DEFAULT_FIXED_PARAMS_FILE = OUTPUT_FILE

DEFAULT_PWM_MODEL = {
    "degre_fit_pwm": 3,
    "coef_pwm_a0": 1.734031e-02,
    "coef_pwm_a1": 1.406312e-01,
    "coef_pwm_a2": 9.947817e-04,
    "coef_pwm_a3": 1.703277e-05,
}
PWM_COEFF_KEYS = ("coef_pwm_a0", "coef_pwm_a1", "coef_pwm_a2", "coef_pwm_a3")

BASE_PARAMS = {
    "largeur_x_mm": 61.5,
    "longueur_y_mm": 117.5,
    "epaisseur_mm": 1.7,
    "resolution_grille": 12,
    "temperature_ambiante_C": 20.0,
    "diffusivite_alpha": 97.034,
    "masse_volumique_rho": 2.7e-3,
    "chaleur_massique_cp": 0.99,
    "coeff_convection_h": 3.038e-5,
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

OPTIMIZER_PARAMETER_LABELS = {
    "diffusivite_alpha": "α diffusivité",
    "coeff_convection_h": "h convection",
    "chaleur_massique_cp": "Cp",
    "facteur_couplage_perturbation": "Couplage perturb.",
    "tau_perturbation_s": "τ perturb. (s)",
    "facteur_couplage_tec": "Couplage TEC",
    "tau_tec_s": "τ TEC (s)",
    "coef_pwm_a0": "a0",
    "coef_pwm_a1": "a1",
    "coef_pwm_a2": "a2",
    "coef_pwm_a3": "a3",
}

DEFAULT_OPTIMIZER_INITIALS = {
    "diffusivite_alpha": float(BASE_PARAMS["diffusivite_alpha"]),
    "coeff_convection_h": float(BASE_PARAMS["coeff_convection_h"]),
    "chaleur_massique_cp": float(BASE_PARAMS["chaleur_massique_cp"]),
    "facteur_couplage_perturbation": 0.20,
    "tau_perturbation_s": 8.03,
    "facteur_couplage_tec": 0.60,
    "tau_tec_s": 8.0,
    **DEFAULT_PWM_MODEL,
}

DEFAULT_MAX_VARIATION_PCT = {
    "diffusivite_alpha": 200,
    "coeff_convection_h": 200.0,
    "chaleur_massique_cp": 10.0,
    "facteur_couplage_perturbation": 40.0,
    "tau_perturbation_s": 100.0,
    "facteur_couplage_tec": 40.0,
    "tau_tec_s": 100.0,
    "coef_pwm_a0": 100.0,
    "coef_pwm_a1": 100.0,
    "coef_pwm_a2": 200.0,
    "coef_pwm_a3": 200.0,
}

ABSOLUTE_PARAMETER_BOUNDS = {
    "diffusivite_alpha": (30.0, 220.0),
    "coeff_convection_h": (1e-6, 3e-4),
    "chaleur_massique_cp": (0.4, 1.8),
    "facteur_couplage_perturbation": (0.2, 2.5),
    "tau_perturbation_s": (0.0, 60.0),
    "facteur_couplage_tec": (0.2, 2.5),
    "tau_tec_s": (0.0, 80.0),
    "coef_pwm_a0": (0.0, 0.2),
    "coef_pwm_a1": (0.01, 0.3),
    "coef_pwm_a2": (-0.01, 0.01),
    "coef_pwm_a3": (-0.001, 0.001),
}

OPTIMIZER_PARAMETER_GROUPS = {
    "Thermique (calibration combinée)": [
        "diffusivite_alpha",
        "coeff_convection_h",
        "chaleur_massique_cp",
    ],
    "PWM → W (fit TEC)": [
        "coef_pwm_a0",
        "coef_pwm_a1",
        "coef_pwm_a2",
        "coef_pwm_a3",
    ],
}

PERTURBATION_EXPERIMENT_SPECS = [
    {"keywords": ("0.81", "4.5"), "power_w": 0.81},
    {"keywords": ("1.44",), "power_w": 1.44},
    {"keywords": ("2.56", "8v"), "power_w": 2.56},
    {"keywords": ("4w", "10v"), "power_w": 4.0},
]

# À remplir si les noms de fichiers TEC n'indiquent pas le PWM.
TEC_EXPERIMENT_SPECS: list[dict[str, object]] = []
CALIBRATION_SENSOR_NAMES = ("T2", "T3")


ProgressCallback = Callable[[str], None]


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
        r"([+-]?\d+(?:[\.,]\d+)?)\s*%?\s*pwm",
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


def normalize_pwm_fit_degree(value: float | int | None) -> int:
    try:
        degree = int(round(float(value)))
    except (TypeError, ValueError):
        degree = int(DEFAULT_PWM_MODEL["degre_fit_pwm"])
    return int(np.clip(degree, 1, 3))


def _extract_pwm_model_params(params: dict[str, float] | None = None) -> dict[str, float]:
    model = dict(DEFAULT_PWM_MODEL)
    if params:
        for key in ("degre_fit_pwm", *PWM_COEFF_KEYS):
            if key in params:
                model[key] = float(params[key])
    model["degre_fit_pwm"] = normalize_pwm_fit_degree(model.get("degre_fit_pwm", 3))
    return model


def pwm_percent_to_power_w(pwm_percent: float, params: dict[str, float] | None = None) -> float:
    pwm = float(np.clip(abs(pwm_percent), 0.0, 100.0))
    model = _extract_pwm_model_params(params)

    power_w = model["coef_pwm_a0"] + (model["coef_pwm_a1"] * pwm)
    if model["degre_fit_pwm"] >= 2:
        power_w += model["coef_pwm_a2"] * (pwm**2)
    if model["degre_fit_pwm"] >= 3:
        power_w += model["coef_pwm_a3"] * (pwm**3)
    return max(0.0, float(power_w))


def _is_pwm_model_physical(params: dict[str, float]) -> bool:
    grid = np.linspace(0.0, 100.0, 201)
    values = np.array([pwm_percent_to_power_w(level, params) for level in grid], dtype=float)
    if not np.all(np.isfinite(values)):
        return False
    if np.any(values < -1e-9):
        return False
    return bool(np.all(np.diff(values) >= -1e-4))


def load_fixed_parameters_from_json(path: Path | None) -> dict[str, float]:
    if path is None:
        return {}

    resolved = Path(path)
    if not resolved.exists() or not resolved.is_file():
        return {}

    payload = json.loads(resolved.read_text(encoding="utf-8"))
    params = payload.get("parametres", payload)
    if not isinstance(params, dict):
        return {}

    normalized: dict[str, float] = {}
    for key, value in params.items():
        try:
            normalized[str(key)] = float(value)
        except (TypeError, ValueError):
            continue

    if "constante_temps_perturbation_s" in normalized:
        normalized["tau_perturbation_s"] = normalized["constante_temps_perturbation_s"]
    if "constante_temps_tec_s" in normalized:
        normalized["tau_tec_s"] = normalized["constante_temps_tec_s"]
    return normalized


def build_evaluation_params(overrides: dict[str, float] | None = None, fixed_params: dict[str, float] | None = None) -> dict[str, float]:
    params = dict(DEFAULT_OPTIMIZER_INITIALS)

    for source in (fixed_params, overrides):
        if not source:
            continue
        for key, value in source.items():
            if key in params:
                params[key] = float(value)
        if "constante_temps_perturbation_s" in source:
            params["tau_perturbation_s"] = float(source["constante_temps_perturbation_s"])
        if "constante_temps_tec_s" in source:
            params["tau_tec_s"] = float(source["constante_temps_tec_s"])

    params["degre_fit_pwm"] = normalize_pwm_fit_degree(params.get("degre_fit_pwm", 3))
    return params


def compute_parameter_bounds(key: str, initial_value: float, variation_pct: float | None) -> tuple[float, float]:
    low_abs, high_abs = ABSOLUTE_PARAMETER_BOUNDS[key]
    pct = DEFAULT_MAX_VARIATION_PCT.get(key, 100.0) if variation_pct is None else max(0.0, float(variation_pct))

    initial_value = float(np.clip(initial_value, low_abs, high_abs))
    if pct == 0.0:
        return initial_value, initial_value

    margin = abs(initial_value) * (pct / 100.0)
    if margin < 1e-12:
        span = max(abs(high_abs - low_abs), abs(high_abs), 1.0)
        margin = span * (pct / 100.0) * 0.25

    lower = max(low_abs, initial_value - margin)
    upper = min(high_abs, initial_value + margin)
    if lower > upper:
        lower, upper = low_abs, high_abs
    return float(lower), float(upper)


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
    progress_callback: ProgressCallback | None = None,
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
    for index, (path, power_w) in enumerate(matches, start=1):
        time_s, sensor_deltas = _load_common_csv(path, max_time_s=max_time_s, downsample=downsample)
        filtered = {name: values for name, values in sensor_deltas.items() if name in CALIBRATION_SENSOR_NAMES}
        experiment = ThermalExperiment(
            name=path.name,
            source="perturbation",
            input_level=float(power_w),
            sign=1.0,
            time_s=time_s,
            sensor_deltas_c=filtered,
        )
        experiments.append(experiment)
        if progress_callback is not None:
            progress_callback(
                f"Chargement {index}/{len(matches)} : [perturbation] {experiment.name} | {experiment.input_level:.2f} W | capteurs={sorted(experiment.sensor_deltas_c.keys())}"
            )
    return experiments


def load_tec_experiments(
    data_dir: Path = DEFAULT_TEC_DIR,
    max_time_s: float = 800.0,
    downsample: int = 10,
    progress_callback: ProgressCallback | None = None,
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
    for index, (path, pwm_percent, sign) in enumerate(matches, start=1):
        time_s, sensor_deltas = _load_common_csv(path, max_time_s=max_time_s, downsample=downsample)
        filtered = {name: values for name, values in sensor_deltas.items() if name in CALIBRATION_SENSOR_NAMES}
        experiment = ThermalExperiment(
            name=path.name,
            source="tec",
            input_level=float(pwm_percent),
            sign=float(sign),
            time_s=time_s,
            sensor_deltas_c=filtered,
        )
        experiments.append(experiment)
        if progress_callback is not None:
            mode = "refroidissement" if experiment.sign < 0 else "chauffage"
            progress_callback(
                f"Chargement {index}/{len(matches)} : [tec] {experiment.name} | PWM={experiment.input_level:.1f} % | {mode} | capteurs={sorted(experiment.sensor_deltas_c.keys())}"
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
    degre_fit_pwm: float = 3,
    coef_pwm_a0: float = DEFAULT_PWM_MODEL["coef_pwm_a0"],
    coef_pwm_a1: float = DEFAULT_PWM_MODEL["coef_pwm_a1"],
    coef_pwm_a2: float = DEFAULT_PWM_MODEL["coef_pwm_a2"],
    coef_pwm_a3: float = DEFAULT_PWM_MODEL["coef_pwm_a3"],
) -> dict[str, np.ndarray]:
    pwm_model = {
        "degre_fit_pwm": degre_fit_pwm,
        "coef_pwm_a0": coef_pwm_a0,
        "coef_pwm_a1": coef_pwm_a1,
        "coef_pwm_a2": coef_pwm_a2,
        "coef_pwm_a3": coef_pwm_a3,
    }
    return _simulate_response(
        target_times=target_times,
        diffusivite_alpha=diffusivite_alpha,
        coeff_convection_h=coeff_convection_h,
        chaleur_massique_cp=chaleur_massique_cp,
        tec_power_w=sign * facteur_couplage_tec * pwm_percent_to_power_w(pwm_percent, pwm_model),
        tec_tau_s=tau_tec_s,
    )


def _simulate_experiment(exp: ThermalExperiment, params: dict[str, float]) -> dict[str, np.ndarray]:
    if exp.source == "perturbation":
        return simulate_perturbation_response(
            power_w=exp.input_level,
            target_times=exp.time_s,
            diffusivite_alpha=params["diffusivite_alpha"],
            coeff_convection_h=params["coeff_convection_h"],
            chaleur_massique_cp=params["chaleur_massique_cp"],
            facteur_couplage_perturbation=params["facteur_couplage_perturbation"],
            tau_perturbation_s=params["tau_perturbation_s"],
        )
    if exp.source == "tec":
        return simulate_tec_response(
            pwm_percent=exp.input_level,
            sign=exp.sign,
            target_times=exp.time_s,
            diffusivite_alpha=params["diffusivite_alpha"],
            coeff_convection_h=params["coeff_convection_h"],
            chaleur_massique_cp=params["chaleur_massique_cp"],
            facteur_couplage_tec=params["facteur_couplage_tec"],
            tau_tec_s=params["tau_tec_s"],
            degre_fit_pwm=params.get("degre_fit_pwm", DEFAULT_PWM_MODEL["degre_fit_pwm"]),
            coef_pwm_a0=params.get("coef_pwm_a0", DEFAULT_PWM_MODEL["coef_pwm_a0"]),
            coef_pwm_a1=params.get("coef_pwm_a1", DEFAULT_PWM_MODEL["coef_pwm_a1"]),
            coef_pwm_a2=params.get("coef_pwm_a2", DEFAULT_PWM_MODEL["coef_pwm_a2"]),
            coef_pwm_a3=params.get("coef_pwm_a3", DEFAULT_PWM_MODEL["coef_pwm_a3"]),
        )
    raise ValueError(f"Type d'expérience inconnu: {exp.source}")


def summarize_experiment_rmse(experiments: Iterable[ThermalExperiment], **params: float) -> list[dict[str, object]]:
    details: list[dict[str, object]] = []

    for exp in experiments:
        sim = _simulate_experiment(exp, params)
        sensor_rmse: dict[str, float] = {}
        for sensor_name, measured in exp.sensor_deltas_c.items():
            if sensor_name in sim:
                sensor_rmse[sensor_name] = math.sqrt(float(np.mean((sim[sensor_name] - measured) ** 2)))

        if not sensor_rmse:
            continue

        details.append(
            {
                "nom": exp.name,
                "source": exp.source,
                "rmse_C": math.sqrt(float(np.mean([value**2 for value in sensor_rmse.values()]))),
                "rmse_capteurs_C": sensor_rmse,
            }
        )

    return details


def evaluate_rmse(experiments: Iterable[ThermalExperiment], **params: float) -> float:
    details = summarize_experiment_rmse(experiments, **params)
    if not details:
        raise ValueError("Aucune erreur de calibration n'a pu être calculée")
    return math.sqrt(float(np.mean([detail["rmse_C"] ** 2 for detail in details])))


def load_all_experiments(
    perturb_dir: Path | None,
    tec_dir: Path | None,
    perturb_max_time_s: float,
    tec_max_time_s: float,
    perturb_downsample: int,
    tec_downsample: int,
    progress_callback: ProgressCallback | None = None,
) -> list[ThermalExperiment]:
    experiments: list[ThermalExperiment] = []
    errors: list[str] = []

    if perturb_dir is not None:
        try:
            if progress_callback is not None:
                progress_callback(f"Recherche des essais de perturbation dans : {perturb_dir}")
            experiments.extend(
                load_perturbation_experiments(
                    data_dir=perturb_dir,
                    max_time_s=perturb_max_time_s,
                    downsample=perturb_downsample,
                    progress_callback=progress_callback,
                )
            )
        except Exception as exc:
            errors.append(f"Perturbation: {exc}")
            if progress_callback is not None:
                progress_callback(f"Erreur perturbation : {exc}")

    if tec_dir is not None:
        try:
            if progress_callback is not None:
                progress_callback(f"Recherche des essais TEC dans : {tec_dir}")
            experiments.extend(
                load_tec_experiments(
                    data_dir=tec_dir,
                    max_time_s=tec_max_time_s,
                    downsample=tec_downsample,
                    progress_callback=progress_callback,
                )
            )
        except Exception as exc:
            errors.append(f"TEC: {exc}")
            if progress_callback is not None:
                progress_callback(f"Erreur TEC : {exc}")

    if not experiments:
        details = "\n".join(errors) if errors else "Aucune source d'essais n'a été fournie."
        raise FileNotFoundError(f"Impossible de charger des expériences.\n{details}")

    return experiments


def calibrate_combined(
    experiments: Iterable[ThermalExperiment],
    initial_params: dict[str, float] | None = None,
    variation_max_pct: dict[str, float] | None = None,
    progress_callback: ProgressCallback | None = None,
) -> dict:
    experiments = list(experiments)
    if not experiments:
        raise ValueError("Aucun essai chargé pour la calibration combinée")

    initial_params = dict(initial_params or {})
    variation_max_pct = dict(variation_max_pct or {})
    optimization_keys = [
        "diffusivite_alpha",
        "coeff_convection_h",
        "chaleur_massique_cp",
        "facteur_couplage_perturbation",
        "tau_perturbation_s",
        "facteur_couplage_tec",
        "tau_tec_s",
    ]

    baseline = build_evaluation_params(
        {
            "facteur_couplage_perturbation": DEFAULT_OPTIMIZER_INITIALS["facteur_couplage_perturbation"],
            "tau_perturbation_s": DEFAULT_OPTIMIZER_INITIALS["tau_perturbation_s"],
            "facteur_couplage_tec": DEFAULT_OPTIMIZER_INITIALS["facteur_couplage_tec"],
            "tau_tec_s": DEFAULT_OPTIMIZER_INITIALS["tau_tec_s"],
            **{key: value for key, value in initial_params.items() if key in optimization_keys},
        }
    )
    baseline_rmse = evaluate_rmse(experiments, **baseline)
    if progress_callback is not None:
        progress_callback(f"RMSE initiale : {baseline_rmse:.3f} °C")

    optimization_state = {"count": 0, "best_rmse": float("inf")}

    def objective(vector: np.ndarray) -> float:
        values = build_evaluation_params(
            {
                "diffusivite_alpha": float(vector[0]),
                "coeff_convection_h": float(vector[1]),
                "chaleur_massique_cp": float(vector[2]),
                "facteur_couplage_perturbation": float(vector[3]),
                "tau_perturbation_s": float(vector[4]),
                "facteur_couplage_tec": float(vector[5]),
                "tau_tec_s": float(vector[6]),
            },
            fixed_params=baseline,
        )
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
        optimization_state["count"] += 1
        is_new_best = rmse + 1e-12 < optimization_state["best_rmse"]
        if is_new_best:
            optimization_state["best_rmse"] = rmse
        if progress_callback is not None and (optimization_state["count"] <= 3 or is_new_best):
            progress_callback(
                "Itération "
                f"{optimization_state['count']:03d} | RMSE={rmse:.3f} °C | "
                f"alpha={values['diffusivite_alpha']:.2f}, h={values['coeff_convection_h']:.3e}, Cp={values['chaleur_massique_cp']:.3f}"
            )
        return rmse**2

    result = minimize(
        objective,
        x0=np.array([baseline[key] for key in optimization_keys], dtype=float),
        method="L-BFGS-B",
        bounds=[
            compute_parameter_bounds(key, baseline[key], variation_max_pct.get(key))
            for key in optimization_keys
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
        "degre_fit_pwm": int(baseline["degre_fit_pwm"]),
        "coef_pwm_a0": float(baseline["coef_pwm_a0"]),
        "coef_pwm_a1": float(baseline["coef_pwm_a1"]),
        "coef_pwm_a2": float(baseline["coef_pwm_a2"]),
        "coef_pwm_a3": float(baseline["coef_pwm_a3"]),
    }

    best_for_eval = build_evaluation_params(
        {
            "diffusivite_alpha": best["diffusivite_alpha"],
            "coeff_convection_h": best["coeff_convection_h"],
            "chaleur_massique_cp": best["chaleur_massique_cp"],
            "facteur_couplage_perturbation": best["facteur_couplage_perturbation"],
            "tau_perturbation_s": best["constante_temps_perturbation_s"],
            "facteur_couplage_tec": best["facteur_couplage_tec"],
            "tau_tec_s": best["constante_temps_tec_s"],
            "degre_fit_pwm": best["degre_fit_pwm"],
            "coef_pwm_a0": best["coef_pwm_a0"],
            "coef_pwm_a1": best["coef_pwm_a1"],
            "coef_pwm_a2": best["coef_pwm_a2"],
            "coef_pwm_a3": best["coef_pwm_a3"],
        }
    )

    rmse_after = evaluate_rmse(experiments, **best_for_eval)
    usable_solution = math.isfinite(float(result.fun)) and rmse_after <= baseline_rmse + 1e-12

    branches = sorted({exp.source for exp in experiments})
    rmse_details = summarize_experiment_rmse(experiments, **best_for_eval)
    rmse_by_name = {detail["nom"]: detail for detail in rmse_details}

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
            detail["puissance_estimee_W"] = round(exp.sign * pwm_percent_to_power_w(exp.input_level, best_for_eval), 3)

        if exp.name in rmse_by_name:
            detail["rmse_C"] = round(float(rmse_by_name[exp.name]["rmse_C"]), 3)
            detail["rmse_capteurs_C"] = {
                key: round(float(value), 3)
                for key, value in rmse_by_name[exp.name]["rmse_capteurs_C"].items()
            }
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
            "degre_fit_pwm": int(best["degre_fit_pwm"]),
            "coef_pwm_a0": round(best["coef_pwm_a0"], 8),
            "coef_pwm_a1": round(best["coef_pwm_a1"], 8),
            "coef_pwm_a2": round(best["coef_pwm_a2"], 8),
            "coef_pwm_a3": round(best["coef_pwm_a3"], 10),
        },
        "essais": summary,
    }


def format_pwm_model_equation(params: dict[str, float]) -> str:
    model = _extract_pwm_model_params(params)
    terms = [f"{model['coef_pwm_a0']:.6g}", f"{model['coef_pwm_a1']:.6g}·|PWM|"]
    if model["degre_fit_pwm"] >= 2:
        terms.append(f"{model['coef_pwm_a2']:.6g}·|PWM|²")
    if model["degre_fit_pwm"] >= 3:
        terms.append(f"{model['coef_pwm_a3']:.6g}·|PWM|³")
    return "P(W) ≈ " + " + ".join(terms)


def calibrate_pwm_model(
    experiments: Iterable[ThermalExperiment],
    fixed_params: dict[str, float] | None = None,
    fit_degree: int = 3,
    initial_params: dict[str, float] | None = None,
    variation_max_pct: dict[str, float] | None = None,
    progress_callback: ProgressCallback | None = None,
) -> dict:
    tec_experiments = [exp for exp in experiments if exp.source == "tec"]
    if not tec_experiments:
        raise ValueError("Aucun essai TEC disponible pour ajuster le modèle PWM → W.")

    fit_degree = normalize_pwm_fit_degree(fit_degree)
    initial_params = dict(initial_params or {})
    variation_max_pct = dict(variation_max_pct or {})
    baseline = build_evaluation_params(
        {
            "degre_fit_pwm": fit_degree,
            "facteur_couplage_tec": float(initial_params.get("facteur_couplage_tec", DEFAULT_OPTIMIZER_INITIALS["facteur_couplage_tec"])),
            **{key: value for key, value in initial_params.items() if key in {"tau_tec_s", *PWM_COEFF_KEYS}},
        },
        fixed_params=fixed_params,
    )

    baseline_rmse = evaluate_rmse(tec_experiments, **baseline)
    if progress_callback is not None:
        progress_callback(f"RMSE initiale (modèle PWM figé) : {baseline_rmse:.3f} °C")
        progress_callback(f"Paramètres thermiques figés : alpha={baseline['diffusivite_alpha']:.3f}, h={baseline['coeff_convection_h']:.3e}, Cp={baseline['chaleur_massique_cp']:.4f}")
        progress_callback(f"Équation PWM initiale : {format_pwm_model_equation(baseline)}")

    varying_keys = ["facteur_couplage_tec", "tau_tec_s", "coef_pwm_a0", "coef_pwm_a1"]
    if fit_degree >= 2:
        varying_keys.append("coef_pwm_a2")
    if fit_degree >= 3:
        varying_keys.append("coef_pwm_a3")

    regularization_scales = {
        "facteur_couplage_tec": 0.2,
        "tau_tec_s": 10.0,
        "coef_pwm_a0": 0.03,
        "coef_pwm_a1": 0.04,
        "coef_pwm_a2": 0.002,
        "coef_pwm_a3": 5e-05,
    }

    optimization_state = {"count": 0, "best_rmse": float("inf")}

    def objective(vector: np.ndarray) -> float:
        trial = build_evaluation_params(
            dict(zip(varying_keys, vector.astype(float), strict=False)),
            fixed_params=baseline,
        )
        trial["degre_fit_pwm"] = fit_degree

        if trial["facteur_couplage_tec"] <= 0 or trial["tau_tec_s"] < 0 or not _is_pwm_model_physical(trial):
            return 1e12

        rmse = evaluate_rmse(tec_experiments, **trial)
        regularization = 0.015 * sum(
            ((trial[key] - baseline[key]) / regularization_scales[key]) ** 2
            for key in varying_keys
        )

        optimization_state["count"] += 1
        is_new_best = rmse + 1e-12 < optimization_state["best_rmse"]
        if is_new_best:
            optimization_state["best_rmse"] = rmse
        if progress_callback is not None and (optimization_state["count"] <= 4 or is_new_best):
            progress_callback(
                "Fit PWM "
                f"{optimization_state['count']:03d} | RMSE={rmse:.3f} °C | "
                f"gain={trial['facteur_couplage_tec']:.3f} | tau={trial['tau_tec_s']:.2f} s | {format_pwm_model_equation(trial)}"
            )
        return rmse**2 + regularization

    initial_vector = np.array([baseline[key] for key in varying_keys], dtype=float)
    result = minimize(
        objective,
        x0=initial_vector,
        method="L-BFGS-B",
        bounds=[compute_parameter_bounds(key, baseline[key], variation_max_pct.get(key)) for key in varying_keys],
        options={"maxiter": 45},
    )

    best_for_eval = build_evaluation_params(
        dict(zip(varying_keys, result.x.astype(float), strict=False)),
        fixed_params=baseline,
    )
    best_for_eval["degre_fit_pwm"] = fit_degree

    rmse_after = evaluate_rmse(tec_experiments, **best_for_eval)
    usable_solution = math.isfinite(float(result.fun)) and rmse_after <= baseline_rmse + 1e-12

    rmse_details = summarize_experiment_rmse(tec_experiments, **best_for_eval)
    rmse_by_name = {detail["nom"]: detail for detail in rmse_details}
    summary: list[dict[str, object]] = []

    for exp in tec_experiments:
        detail = {
            "nom": exp.name,
            "source": exp.source,
            "signal": round(exp.input_level, 3),
            "capteurs": sorted(exp.sensor_deltas_c.keys()),
            "pwm_percent": round(exp.input_level, 3),
            "mode": "refroidissement" if exp.sign < 0 else "chauffage",
            "puissance_estimee_W": round(exp.sign * pwm_percent_to_power_w(exp.input_level, best_for_eval), 3),
        }
        if exp.name in rmse_by_name:
            detail["rmse_C"] = round(float(rmse_by_name[exp.name]["rmse_C"]), 3)
            detail["rmse_capteurs_C"] = {
                key: round(float(value), 3)
                for key, value in rmse_by_name[exp.name]["rmse_capteurs_C"].items()
            }
        summary.append(detail)

    return {
        "success": bool(result.success or usable_solution),
        "optimiseur_reussi": bool(result.success),
        "mode_calibration": "pwm-model",
        "message": str(result.message),
        "branches_utilisees": ["tec"],
        "nombre_essais": len(tec_experiments),
        "rmse_avant_C": baseline_rmse,
        "rmse_apres_C": rmse_after,
        "equation_pwm": format_pwm_model_equation(best_for_eval),
        "parametres_fixes": {
            "diffusivite_alpha": round(best_for_eval["diffusivite_alpha"], 3),
            "coeff_convection_h": round(best_for_eval["coeff_convection_h"], 8),
            "chaleur_massique_cp": round(best_for_eval["chaleur_massique_cp"], 4),
            "facteur_couplage_perturbation": round(best_for_eval["facteur_couplage_perturbation"], 3),
            "constante_temps_perturbation_s": round(best_for_eval["tau_perturbation_s"], 2),
        },
        "parametres": {
            "diffusivite_alpha": round(best_for_eval["diffusivite_alpha"], 3),
            "coeff_convection_h": round(best_for_eval["coeff_convection_h"], 8),
            "chaleur_massique_cp": round(best_for_eval["chaleur_massique_cp"], 4),
            "facteur_couplage_perturbation": round(best_for_eval["facteur_couplage_perturbation"], 3),
            "constante_temps_perturbation_s": round(best_for_eval["tau_perturbation_s"], 2),
            "facteur_couplage_tec": round(best_for_eval["facteur_couplage_tec"], 3),
            "constante_temps_tec_s": round(best_for_eval["tau_tec_s"], 2),
            "degre_fit_pwm": int(best_for_eval["degre_fit_pwm"]),
            "coef_pwm_a0": round(best_for_eval["coef_pwm_a0"], 8),
            "coef_pwm_a1": round(best_for_eval["coef_pwm_a1"], 8),
            "coef_pwm_a2": round(best_for_eval["coef_pwm_a2"], 8),
            "coef_pwm_a3": round(best_for_eval["coef_pwm_a3"], 10),
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
    output_path = Path(output_path)
    payload_json = json.dumps(payload, indent=4, ensure_ascii=False)

    output_path.write_text(payload_json, encoding="utf-8")

    default_sync_path = OUTPUT_FILE.resolve(strict=False)
    if output_path.resolve(strict=False) != default_sync_path:
        OUTPUT_FILE.write_text(payload_json, encoding="utf-8")

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

    if args.mode == "pwm-model":
        fixed_params = load_fixed_parameters_from_json(args.fixed_params_json)
        report = calibrate_pwm_model(
            experiments,
            fixed_params=fixed_params,
            fit_degree=args.pwm_fit_degree,
        )
        title = "=== Calibration du modèle PWM → W (essais TEC) ==="
    else:
        report = calibrate_combined(experiments)
        title = "=== Calibration thermique combinée (perturbation + TEC) ==="

    output_path = write_calibration_file(report, output_path=args.output)

    print(title)
    print(f"Branches utilisées : {', '.join(report['branches_utilisees'])}")
    print(f"Essais utilisés     : {report['nombre_essais']}")
    print(f"RMSE avant          : {report['rmse_avant_C']:.3f} °C")
    print(f"RMSE après          : {report['rmse_apres_C']:.3f} °C")
    if report.get("equation_pwm"):
        print(f"Modèle PWM          : {report['equation_pwm']}")
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
    fixed_params_var = tk.StringVar(value=str(DEFAULT_FIXED_PARAMS_FILE))
    perturb_max_time_var = tk.DoubleVar(value=600.0)
    tec_max_time_var = tk.DoubleVar(value=800.0)
    perturb_downsample_var = tk.IntVar(value=50)
    tec_downsample_var = tk.IntVar(value=10)
    pwm_fit_degree_var = tk.IntVar(value=3)

    persisted_initial_params = build_evaluation_params(load_fixed_parameters_from_json(DEFAULT_FIXED_PARAMS_FILE))
    optimizer_initial_values = {
        key: float(persisted_initial_params.get(key, DEFAULT_OPTIMIZER_INITIALS[key]))
        for key in DEFAULT_OPTIMIZER_INITIALS
    }
    optimizer_initial_vars = {
        key: tk.DoubleVar(value=optimizer_initial_values[key])
        for key in DEFAULT_OPTIMIZER_INITIALS
    }
    optimizer_variation_vars = {
        key: tk.DoubleVar(value=float(DEFAULT_MAX_VARIATION_PCT[key]))
        for key in DEFAULT_MAX_VARIATION_PCT
    }

    main_frame = ttk.Frame(root, padding=12)
    main_frame.pack(fill="both", expand=True)

    ttk.Label(
        main_frame,
        text="Calibration combinée des essais perturbation + TEC",
        font=("Segoe UI", 12, "bold"),
    ).pack(anchor="w", pady=(0, 10))

    help_frame = ttk.LabelFrame(main_frame, text="Guide rapide", padding=10)
    help_frame.pack(fill="x", pady=(0, 10))
    help_frame.columnconfigure(0, weight=1)

    help_text = (
        "• Calibration combinée : optimise surtout α, h et Cp à partir des essais de perturbation et/ou TEC.\n"
        "• Lister les essais : affiche les sources détectées, leur type, leur niveau PWM/puissance et les capteurs lus.\n"
        "• Optimiser PWM → W : garde les paramètres thermiques/couplages fixes et ajuste la loi PWM↔W (degré 1, 2 ou 3).\n"
        "• Perturb/TEC max time (s) : limite la durée maximale analysée dans chaque CSV pour couper la queue inutile des essais.\n"
        "• Perturb/TEC downsample : sous-échantillonne les points lus pour accélérer l'optimisation (plus grand = plus rapide, mais moins fin).\n"
        "• Degré fit PWM : choisit si la loi PWM→W est linéaire (1), quadratique (2) ou cubique (3).\n"
        "• Réglages coeffs plaque… : ouvre un menu séparé pour fixer les valeurs initiales et le ± % max de α, h et Cp avant l'optimisation.\n"
        "• Le RMSE est calculé surtout sur T2/T3 (plus robustes) ; T1 près de la source sert mieux comme vérification visuelle.\n"
        "• Les gains/cst de temps des branches (perturbation/TEC) sont maintenant auto-ajustés en arrière-plan pour éviter de bloquer le RMSE autour de valeurs trop hautes."
    )

    help_label = ttk.Label(
        help_frame,
        text=help_text,
        justify="left",
        wraplength=900,
        font=("Segoe UI", 9),
    )
    help_label.grid(row=0, column=0, sticky="w")

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

    def browse_json_file(var: tk.StringVar) -> None:
        initial_dir = str(Path(var.get()).parent) if var.get().strip() else str(REPO_ROOT)
        selected = filedialog.askopenfilename(
            title="Choisir un JSON de paramètres fixes",
            initialdir=initial_dir,
            filetypes=[("JSON", "*.json"), ("Tous les fichiers", "*.*")],
        )
        if selected:
            var.set(selected)

    ttk.Checkbutton(source_frame, text="Inclure perturbation", variable=use_perturb_var).grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
    ttk.Entry(source_frame, textvariable=perturb_dir_var).grid(row=0, column=1, sticky="ew", pady=4)
    ttk.Button(source_frame, text="Parcourir...", command=lambda: browse_directory(perturb_dir_var)).grid(row=0, column=2, padx=(8, 0), pady=4)

    ttk.Checkbutton(source_frame, text="Inclure TEC PWM", variable=use_tec_var).grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
    ttk.Entry(source_frame, textvariable=tec_dir_var).grid(row=1, column=1, sticky="ew", pady=4)
    ttk.Button(source_frame, text="Parcourir...", command=lambda: browse_directory(tec_dir_var)).grid(row=1, column=2, padx=(8, 0), pady=4)

    ttk.Label(source_frame, text="Sortie JSON").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=4)
    ttk.Entry(source_frame, textvariable=output_var).grid(row=2, column=1, sticky="ew", pady=4)
    ttk.Button(source_frame, text="Choisir...", command=browse_output).grid(row=2, column=2, padx=(8, 0), pady=4)

    ttk.Label(source_frame, text="JSON paramètres fixes").grid(row=3, column=0, sticky="w", padx=(0, 8), pady=4)
    ttk.Entry(source_frame, textvariable=fixed_params_var).grid(row=3, column=1, sticky="ew", pady=4)
    ttk.Button(source_frame, text="Choisir...", command=lambda: browse_json_file(fixed_params_var)).grid(row=3, column=2, padx=(8, 0), pady=4)

    options_frame = ttk.LabelFrame(main_frame, text="Options", padding=10)
    options_frame.pack(fill="x", pady=(0, 10))

    for idx in range(5):
        options_frame.columnconfigure(idx, weight=1 if idx % 2 == 1 else 0)

    ttk.Label(options_frame, text="Perturb max time (s)").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
    ttk.Entry(options_frame, textvariable=perturb_max_time_var, width=12).grid(row=0, column=1, sticky="w", pady=4)
    ttk.Label(options_frame, text="TEC max time (s)").grid(row=0, column=2, sticky="w", padx=(16, 8), pady=4)
    ttk.Entry(options_frame, textvariable=tec_max_time_var, width=12).grid(row=0, column=3, sticky="w", pady=4)

    ttk.Label(options_frame, text="Perturb downsample").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
    ttk.Entry(options_frame, textvariable=perturb_downsample_var, width=12).grid(row=1, column=1, sticky="w", pady=4)
    ttk.Label(options_frame, text="TEC downsample").grid(row=1, column=2, sticky="w", padx=(16, 8), pady=4)
    ttk.Entry(options_frame, textvariable=tec_downsample_var, width=12).grid(row=1, column=3, sticky="w", pady=4)

    ttk.Label(options_frame, text="Degré fit PWM").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=4)
    ttk.Combobox(options_frame, textvariable=pwm_fit_degree_var, width=10, state="readonly", values=(1, 2, 3)).grid(row=2, column=1, sticky="w", pady=4)

    def open_plate_coeff_settings() -> None:
        existing = getattr(root, "_coeff_settings_window", None)
        if existing is not None and existing.winfo_exists():
            existing.lift()
            existing.focus_force()
            return

        window = tk.Toplevel(root)
        window.title("Réglages coefficients de la plaque")
        window.transient(root)
        window.resizable(False, False)
        root._coeff_settings_window = window

        frame = ttk.Frame(window, padding=12)
        frame.pack(fill="both", expand=True)

        ttk.Label(
            frame,
            text="Ajuster les valeurs initiales et la variation max des 3 coefficients de la plaque.",
            font=("Segoe UI", 9, "bold"),
            wraplength=520,
            justify="left",
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))
        ttk.Label(
            frame,
            text="Ce menu pilote α, h et Cp pour la calibration combinée. Les coefficients PWM restent gérés séparément.",
            wraplength=520,
            justify="left",
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 10))

        ttk.Label(frame, text="Paramètre").grid(row=2, column=0, sticky="w", padx=(0, 8))
        ttk.Label(frame, text="Initial").grid(row=2, column=1, sticky="w", padx=(0, 8))
        ttk.Label(frame, text="± % max").grid(row=2, column=2, sticky="w")

        plate_keys = ["diffusivite_alpha", "coeff_convection_h", "chaleur_massique_cp"]
        for row, key in enumerate(plate_keys, start=3):
            ttk.Label(frame, text=OPTIMIZER_PARAMETER_LABELS[key]).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=2)
            ttk.Entry(frame, textvariable=optimizer_initial_vars[key], width=12).grid(row=row, column=1, sticky="w", padx=(0, 8), pady=2)
            ttk.Entry(frame, textvariable=optimizer_variation_vars[key], width=8).grid(row=row, column=2, sticky="w", pady=2)

        ttk.Button(frame, text="Fermer", command=window.destroy).grid(row=3 + len(plate_keys), column=2, sticky="e", pady=(12, 0))

    ttk.Button(options_frame, text="Réglages coeffs plaque…", command=open_plate_coeff_settings).grid(row=2, column=2, sticky="w", padx=(16, 8), pady=4)

    button_frame = ttk.Frame(main_frame)
    button_frame.pack(fill="x", pady=(0, 10))

    log_frame = ttk.LabelFrame(main_frame, text="Sources et optimisation", padding=8)
    log_frame.pack(fill="both", expand=True)

    log_output = scrolledtext.ScrolledText(log_frame, height=22, wrap="word", font=("Consolas", 10))
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

    def apply_calibrated_params_to_ui(report: dict, json_path: Path | None = None) -> None:
        merged_params = build_evaluation_params(report.get("parametres", {}))

        def _apply() -> None:
            for key, var in optimizer_initial_vars.items():
                if key in merged_params:
                    value = float(merged_params[key])
                    var.set(value)
                    DEFAULT_OPTIMIZER_INITIALS[key] = value
            if json_path is not None:
                fixed_params_var.set(str(json_path))

        root.after(0, _apply)

    def collect_settings() -> tuple[Path | None, Path | None, Path, Path | None, float, float, int, int, int, dict[str, float], dict[str, float]]:
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

        initial_params = {key: float(var.get()) for key, var in optimizer_initial_vars.items()}
        variation_max_pct = {key: float(var.get()) for key, var in optimizer_variation_vars.items()}
        invalid_keys = [key for key, value in variation_max_pct.items() if value < 0]
        if invalid_keys:
            raise ValueError("Le pourcentage de variation doit être positif ou nul pour : " + ", ".join(invalid_keys))

        output_path = Path(output_var.get().strip() or OUTPUT_FILE)
        fixed_params_path = Path(fixed_params_var.get().strip()) if fixed_params_var.get().strip() else None
        return (
            perturb_dir,
            tec_dir,
            output_path,
            fixed_params_path,
            float(perturb_max_time_var.get()),
            float(tec_max_time_var.get()),
            int(perturb_downsample_var.get()),
            int(tec_downsample_var.get()),
            int(pwm_fit_degree_var.get()),
            initial_params,
            variation_max_pct,
        )

    def run_action(list_only: bool, mode: str = "combined") -> None:
        try:
            settings = collect_settings()
        except Exception as exc:
            messagebox.showerror("Calibration", str(exc))
            return

        (
            perturb_dir,
            tec_dir,
            output_path,
            fixed_params_path,
            perturb_max_time_s,
            tec_max_time_s,
            perturb_downsample,
            tec_downsample,
            pwm_fit_degree,
            initial_params,
            variation_max_pct,
        ) = settings

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
                    progress_callback=append_log,
                )

                if list_only:
                    append_log("=== Essais détectés ===")
                    for exp in experiments:
                        append_log(_format_experiment_line(exp))
                    return

                if mode == "pwm-model":
                    fixed_params = load_fixed_parameters_from_json(fixed_params_path)
                    if fixed_params_path is not None and fixed_params_path.exists():
                        append_log(f"Paramètres thermiques figés chargés depuis : {fixed_params_path}")
                    else:
                        append_log("Aucun JSON fixe valide fourni; utilisation des paramètres de base du script.")
                    report = calibrate_pwm_model(
                        experiments,
                        fixed_params=fixed_params,
                        fit_degree=pwm_fit_degree,
                        initial_params=initial_params,
                        variation_max_pct=variation_max_pct,
                        progress_callback=append_log,
                    )
                else:
                    report = calibrate_combined(
                        experiments,
                        initial_params=initial_params,
                        variation_max_pct=variation_max_pct,
                        progress_callback=append_log,
                    )

                json_path = write_calibration_file(report, output_path=output_path)
                apply_calibrated_params_to_ui(report, json_path)

                append_log("Les paramètres initiaux de l'interface ont été mis à jour avec le dernier résultat.")
                append_log(f"Branches utilisées : {', '.join(report['branches_utilisees'])}")
                append_log(f"Essais utilisés     : {report['nombre_essais']}")
                append_log(f"RMSE avant          : {report['rmse_avant_C']:.3f} °C")
                append_log(f"RMSE après          : {report['rmse_apres_C']:.3f} °C")
                if report.get("equation_pwm"):
                    append_log(f"Modèle PWM          : {report['equation_pwm']}")
                append_log("Paramètres recommandés :")
                for key, value in report["parametres"].items():
                    append_log(f"  - {key} = {value}")
                append_log("Résultats par essai :")
                for essai in report["essais"]:
                    append_log(f"  - {essai['nom']} | RMSE={essai.get('rmse_C', float('nan')):.3f} °C | capteurs={essai['capteurs']}")
                append_log(f"JSON écrit dans : {json_path}")
            except Exception as exc:
                append_log(f"Erreur : {exc}")
                root.after(0, lambda: messagebox.showerror("Calibration", str(exc)))
            finally:
                set_running_state(False)

        threading.Thread(target=worker, daemon=True).start()

    list_button = ttk.Button(button_frame, text="Lister les essais", command=lambda: run_action(True, "combined"))
    run_button = ttk.Button(button_frame, text="Calibration combinée", command=lambda: run_action(False, "combined"))
    pwm_button = ttk.Button(button_frame, text="Optimiser PWM → W", command=lambda: run_action(False, "pwm-model"))
    close_button = ttk.Button(button_frame, text="Fermer", command=root.destroy)
    buttons.extend([list_button, run_button, pwm_button])

    list_button.pack(side="left")
    run_button.pack(side="left", padx=8)
    pwm_button.pack(side="left")
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
    parser.add_argument("--mode", choices=("combined", "pwm-model"), default="combined", help="Mode de calibration à exécuter")
    parser.add_argument("--fixed-params-json", type=Path, default=DEFAULT_FIXED_PARAMS_FILE, help="JSON de paramètres thermiques figés pour le fit PWM")
    parser.add_argument("--pwm-fit-degree", type=int, choices=(1, 2, 3), default=3, help="Degré du modèle PWM → W")
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
