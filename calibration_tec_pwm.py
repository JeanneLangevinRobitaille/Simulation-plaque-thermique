from __future__ import annotations

import argparse
import json
import math
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from scipy.optimize import minimize

REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_DATA_DIR_CANDIDATES = (
    REPO_ROOT / "TestsAndData" / "test pwm tec",
    REPO_ROOT / "TestsAndData" / "test PWM TEC",
    REPO_ROOT / "TestsAndData" / "echelons pwm tec",
    REPO_ROOT / "TestsAndData" / "echelons tec",
    REPO_ROOT / "TestsAndData" / "tec_pwm_steps",
)
DATA_DIR = next((path for path in DEFAULT_DATA_DIR_CANDIDATES if path.exists()), DEFAULT_DATA_DIR_CANDIDATES[0])
OUTPUT_FILE = REPO_ROOT / "parametres_calibres_tec_pwm.json"

# Géométrie et positions reprises du simulateur principal.
BASE_PARAMS = {
    "largeur_x_mm": 61.5,
    "longueur_y_mm": 117.5,
    "epaisseur_mm": 1.7,
    "resolution_grille": 12,
    "temperature_ambiante_C": 20.0,
    "diffusivite_alpha": 97.0,
    "masse_volumique_rho": 2.7e-3,
    "chaleur_massique_cp": 0.9,
    "coeff_convection_h": 5.0e-5,
    "pos_x_capteur_1_mm": 0.0,
    "pos_y_capteur_1_mm": 14.57,
    "pos_x_capteur_2_mm": 0.0,
    "pos_y_capteur_2_mm": 59.42,
    "pos_x_capteur_3_mm": 0.0,
    "pos_y_capteur_3_mm": 103.79,
    "pos_x_tec_mm": 0.0,
    "pos_y_tec_mm": 5.0,
}

# Optionnel : renseigner ici les essais si les noms de fichiers n'indiquent pas clairement le PWM.
# Exemple :
# TEC_EXPERIMENT_SPECS = [
#     {"keywords": ("pwm 10", "chauffe"), "pwm_percent": 10.0, "sign": 1.0},
#     {"keywords": ("pwm 15", "refroid"), "pwm_percent": 15.0, "sign": -1.0},
# ]
TEC_EXPERIMENT_SPECS: list[dict[str, object]] = []


@dataclass(frozen=True)
class TecStepExperiment:
    name: str
    pwm_percent: float
    sign: float
    time_s: np.ndarray
    sensor_deltas_c: dict[str, np.ndarray]


def _normalize_name(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9%+\-.]+", " ", ascii_name.lower()).strip()


def _resolve_data_dir(data_dir: Path) -> Path:
    data_dir = Path(data_dir)
    candidates = [
        data_dir,
        REPO_ROOT / data_dir.name,
        REPO_ROOT / "TestsAndData" / data_dir.name,
        *DEFAULT_DATA_DIR_CANDIDATES,
    ]

    seen: set[Path] = set()
    for candidate in candidates:
        candidate = candidate.resolve(strict=False)
        if candidate in seen:
            continue
        seen.add(candidate)
        if candidate.exists() and candidate.is_dir():
            return candidate

    searched = "\n  - ".join(str(path) for path in seen)
    raise FileNotFoundError(
        "Aucun dossier TEC valide n'a été trouvé. Emplacements vérifiés :\n"
        f"  - {searched}"
    )


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
        except Exception as exc:  # pragma: no cover - message utile à l'utilisateur
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


def _infer_sign(normalized_name: str, pwm_value: float) -> tuple[float, float]:
    if pwm_value < 0:
        return abs(pwm_value), -1.0

    negative_hints = ("refroid", "cool", "froid", "negative", "negatif", "neg")
    if any(hint in normalized_name for hint in negative_hints):
        return pwm_value, -1.0

    return pwm_value, 1.0


def _match_csv_files(data_dir: Path) -> list[tuple[Path, float, float]]:
    data_dir = _resolve_data_dir(data_dir)
    csv_files = sorted(path for path in data_dir.glob("*.csv") if path.is_file())
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
            pwm_percent, sign = _infer_sign(normalized, pwm_percent)
            matches.append((path, float(pwm_percent), float(sign)))

    if not matches:
        raise FileNotFoundError(
            "Aucun CSV TEC exploitable n'a été trouvé.\n"
            f"Dossier inspecté : {data_dir}\n"
            "Nommer les fichiers avec le PWM (ex. `pwm_20_chauffe.csv` ou `pwm_-15_refroid.csv`)\n"
            "ou renseigner `TEC_EXPERIMENT_SPECS` en haut du script."
        )

    return matches


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


def pwm_percent_to_power_w(pwm_percent: float) -> float:
    pwm = float(np.clip(abs(pwm_percent), 0.0, 100.0))
    return (((1.703277e-05 * pwm + 9.947817e-04) * pwm) + 1.406312e-01) * pwm + 1.734031e-02


def load_pwm_step_experiments(
    data_dir: Path = DATA_DIR,
    max_time_s: float = 800.0,
    downsample: int = 10,
) -> list[TecStepExperiment]:
    experiments: list[TecStepExperiment] = []

    for path, pwm_percent, sign in _match_csv_files(data_dir):
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
        time_s = time_s[mask][:: max(1, int(downsample))]

        sensor_deltas: dict[str, np.ndarray] = {}
        for sensor_name, column_name in sensor_columns.items():
            values = df[column_name].to_numpy(dtype=float)[mask]
            sensor_deltas[sensor_name] = (values - values[0])[:: max(1, int(downsample))]

        experiments.append(
            TecStepExperiment(
                name=path.name,
                pwm_percent=float(pwm_percent),
                sign=float(sign),
                time_s=time_s,
                sensor_deltas_c=sensor_deltas,
            )
        )

    return experiments


def _simulate_tec_delta_response(
    pwm_percent: float,
    sign: float,
    target_times: np.ndarray,
    diffusivite_alpha: float,
    coeff_convection_h: float,
    facteur_couplage_tec: float,
    tau_tec_s: float,
) -> dict[str, np.ndarray]:
    p = BASE_PARAMS
    resolution = int(p["resolution_grille"])
    pas_x = p["largeur_x_mm"] / resolution
    pas_y = p["longueur_y_mm"] / resolution

    rho = p["masse_volumique_rho"]
    cp = p["chaleur_massique_cp"]
    epaisseur = p["epaisseur_mm"]

    dt_stable = 0.5 / (diffusivite_alpha * ((1 / pas_x**2) + (1 / pas_y**2)))
    pas_temps = min(0.15 * min(pas_x, pas_y) ** 2 / diffusivite_alpha, dt_stable)

    cst_diffusion_x = diffusivite_alpha * pas_temps / pas_x**2
    cst_diffusion_y = diffusivite_alpha * pas_temps / pas_y**2
    cst_convection = coeff_convection_h * pas_temps / (rho * cp * epaisseur)
    volume_module_tec = (2 * pas_x) * (2 * pas_y) * epaisseur

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

    idx_x_t1 = coord_x_vers_indice(p["pos_x_capteur_1_mm"])
    idx_y_t1 = coord_y_vers_indice(p["pos_y_capteur_1_mm"])
    idx_x_t2 = coord_x_vers_indice(p["pos_x_capteur_2_mm"])
    idx_y_t2 = coord_y_vers_indice(p["pos_y_capteur_2_mm"])
    idx_x_t3 = coord_x_vers_indice(p["pos_x_capteur_3_mm"])
    idx_y_t3 = coord_y_vers_indice(p["pos_y_capteur_3_mm"])
    idx_x_tec = coord_x_vers_indice(p["pos_x_tec_mm"])
    idx_y_tec = coord_y_vers_indice(p["pos_y_tec_mm"])
    zone_tec = creer_zone_source(idx_y_tec, idx_x_tec)

    matrice_t = np.zeros((resolution + 1, resolution + 1), dtype=np.float64)
    matrice_t_suivante = matrice_t.copy()

    temps_courant = 0.0
    puissance_effective = 0.0
    puissance_cible = sign * facteur_couplage_tec * pwm_percent_to_power_w(pwm_percent)
    constante_lag = max(0.0, tau_tec_s)

    t1_out: list[float] = []
    t2_out: list[float] = []
    t3_out: list[float] = []

    for temps_cible in target_times:
        while temps_courant < temps_cible:
            if constante_lag > 0:
                coeff_lag = min(1.0, pas_temps / constante_lag)
                puissance_effective += (puissance_cible - puissance_effective) * coeff_lag
            else:
                puissance_effective = puissance_cible

            puissance_volumique_tec = puissance_effective / volume_module_tec
            ajout_temp_tec = (puissance_volumique_tec * pas_temps) / (rho * cp)

            matrice_t_suivante[1:-1, 1:-1] = matrice_t[1:-1, 1:-1] + (
                cst_diffusion_x * (matrice_t[1:-1, 2:] - 2 * matrice_t[1:-1, 1:-1] + matrice_t[1:-1, :-2])
                + cst_diffusion_y * (matrice_t[2:, 1:-1] - 2 * matrice_t[1:-1, 1:-1] + matrice_t[:-2, 1:-1])
            )
            matrice_t_suivante[1:-1, 1:-1] -= cst_convection * matrice_t[1:-1, 1:-1]
            matrice_t_suivante[zone_tec] += ajout_temp_tec

            matrice_t_suivante[0, :] = matrice_t_suivante[1, :]
            matrice_t_suivante[-1, :] = matrice_t_suivante[-2, :]
            matrice_t_suivante[:, 0] = matrice_t_suivante[:, 1]
            matrice_t_suivante[:, -1] = matrice_t_suivante[:, -2]

            matrice_t, matrice_t_suivante = matrice_t_suivante, matrice_t
            temps_courant += pas_temps

        t1_out.append(float(matrice_t[idx_y_t1, idx_x_t1]))
        t2_out.append(float(matrice_t[idx_y_t2, idx_x_t2]))
        t3_out.append(float(matrice_t[idx_y_t3, idx_x_t3]))

    return {
        "T1": np.array(t1_out),
        "T2": np.array(t2_out),
        "T3": np.array(t3_out),
    }


def evaluate_rmse(
    experiments: Iterable[TecStepExperiment],
    diffusivite_alpha: float,
    coeff_convection_h: float,
    facteur_couplage_tec: float,
    tau_tec_s: float,
) -> float:
    errors: list[float] = []

    for exp in experiments:
        sim = _simulate_tec_delta_response(
            exp.pwm_percent,
            exp.sign,
            exp.time_s,
            diffusivite_alpha=diffusivite_alpha,
            coeff_convection_h=coeff_convection_h,
            facteur_couplage_tec=facteur_couplage_tec,
            tau_tec_s=tau_tec_s,
        )
        for sensor_name, measured_values in exp.sensor_deltas_c.items():
            errors.append(float(np.mean((sim[sensor_name] - measured_values) ** 2)))

    return math.sqrt(float(np.mean(errors)))


def calibrate_tec_parameters(experiments: Iterable[TecStepExperiment]) -> dict:
    experiments = list(experiments)
    if not experiments:
        raise ValueError("Aucun essai TEC à calibrer")

    baseline = {
        "diffusivite_alpha": BASE_PARAMS["diffusivite_alpha"],
        "coeff_convection_h": BASE_PARAMS["coeff_convection_h"],
        "facteur_couplage_tec": 1.0,
        "tau_tec_s": 6.0,
    }
    baseline_rmse = evaluate_rmse(
        experiments,
        diffusivite_alpha=baseline["diffusivite_alpha"],
        coeff_convection_h=baseline["coeff_convection_h"],
        facteur_couplage_tec=baseline["facteur_couplage_tec"],
        tau_tec_s=baseline["tau_tec_s"],
    )

    def objective(vector: np.ndarray) -> float:
        diffusivite_alpha, coeff_convection_h, facteur_couplage_tec, tau_tec_s = vector
        if diffusivite_alpha <= 0 or coeff_convection_h <= 0 or facteur_couplage_tec <= 0 or tau_tec_s < 0:
            return 1e9

        rmse = evaluate_rmse(
            experiments,
            diffusivite_alpha=diffusivite_alpha,
            coeff_convection_h=coeff_convection_h,
            facteur_couplage_tec=facteur_couplage_tec,
            tau_tec_s=tau_tec_s,
        )
        return rmse**2

    result = minimize(
        objective,
        x0=np.array([
            baseline["diffusivite_alpha"],
            baseline["coeff_convection_h"],
            baseline["facteur_couplage_tec"],
            baseline["tau_tec_s"],
        ], dtype=float),
        method="L-BFGS-B",
        bounds=[(30.0, 220.0), (1e-6, 3e-4), (0.1, 2.5), (0.0, 80.0)],
        options={"maxiter": 25},
    )

    best = {
        "diffusivite_alpha": float(result.x[0]),
        "coeff_convection_h": float(result.x[1]),
        "facteur_couplage_tec": float(result.x[2]),
        "constante_temps_tec_s": float(result.x[3]),
    }

    rmse_after = evaluate_rmse(
        experiments,
        diffusivite_alpha=best["diffusivite_alpha"],
        coeff_convection_h=best["coeff_convection_h"],
        facteur_couplage_tec=best["facteur_couplage_tec"],
        tau_tec_s=best["constante_temps_tec_s"],
    )
    usable_solution = math.isfinite(float(result.fun)) and rmse_after <= baseline_rmse + 1e-12

    report = {
        "success": bool(result.success or usable_solution),
        "optimiseur_reussi": bool(result.success),
        "message": str(result.message),
        "rmse_avant_C": baseline_rmse,
        "rmse_apres_C": rmse_after,
        "parametres": {
            "diffusivite_alpha": round(best["diffusivite_alpha"], 3),
            "coeff_convection_h": round(best["coeff_convection_h"], 8),
            "facteur_couplage_tec": round(best["facteur_couplage_tec"], 3),
            "constante_temps_tec_s": round(best["constante_temps_tec_s"], 2),
        },
        "fichiers_utilises": [
            {
                "nom": exp.name,
                "pwm_percent": exp.pwm_percent,
                "mode": "refroidissement" if exp.sign < 0 else "chauffage",
                "puissance_estimee_W": round(exp.sign * pwm_percent_to_power_w(exp.pwm_percent), 3),
            }
            for exp in experiments
        ],
    }
    return report


def calibrate_from_pwm_step_files(
    data_dir: Path = DATA_DIR,
    max_time_s: float = 800.0,
    downsample: int = 10,
) -> dict:
    experiments = load_pwm_step_experiments(
        data_dir=data_dir,
        max_time_s=max_time_s,
        downsample=downsample,
    )
    return calibrate_tec_parameters(experiments)


def write_calibration_file(report: dict, output_path: Path = OUTPUT_FILE) -> Path:
    payload = {"parametres": report["parametres"], "calibration": report}
    output_path.write_text(json.dumps(payload, indent=4, ensure_ascii=False), encoding="utf-8")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Calibre la branche TEC à partir d'échelons PWM mesurés.")
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR, help="Dossier contenant les CSV d'échelons TEC")
    parser.add_argument("--max-time-s", type=float, default=800.0, help="Durée maximale retenue par essai")
    parser.add_argument("--downsample", type=int, default=10, help="Sous-échantillonnage des mesures")
    parser.add_argument("--output", type=Path, default=OUTPUT_FILE, help="Fichier JSON de sortie")
    parser.add_argument("--list-only", action="store_true", help="Liste seulement les CSV trouvés et leur PWM détecté")
    args = parser.parse_args()

    if args.list_only:
        for path, pwm_percent, sign in _match_csv_files(args.data_dir):
            mode = "refroidissement" if sign < 0 else "chauffage"
            print(f"- {path.name}: PWM={pwm_percent:.1f} %, {mode}, puissance≈{sign * pwm_percent_to_power_w(pwm_percent):.3f} W")
        return

    report = calibrate_from_pwm_step_files(
        data_dir=args.data_dir,
        max_time_s=args.max_time_s,
        downsample=args.downsample,
    )
    output_path = write_calibration_file(report, output_path=args.output)

    print("=== Calibration thermique TEC à partir des échelons PWM ===")
    print(f"Fichiers utilisés : {len(report['fichiers_utilises'])}")
    print(f"RMSE avant  : {report['rmse_avant_C']:.3f} °C")
    print(f"RMSE après  : {report['rmse_apres_C']:.3f} °C")
    print("\nParamètres recommandés pour SimulateurUpgrade.py :")
    for key, value in report["parametres"].items():
        print(f"  - {key} = {value}")
    print(f"\nPreset JSON écrit dans : {output_path}")


if __name__ == "__main__":
    main()
