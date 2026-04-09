from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from scipy.optimize import minimize

REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_DATA_DIR_CANDIDATES = (
    REPO_ROOT / "TestsAndData" / "test de puissance à résistance perturbation",
    REPO_ROOT / "test de puissance à résistance perturbation",
)
DATA_DIR = next((path for path in DEFAULT_DATA_DIR_CANDIDATES if path.exists()), DEFAULT_DATA_DIR_CANDIDATES[0])
OUTPUT_FILE = REPO_ROOT / "parametres_calibres_perturbation.json"

# Géométrie et propriétés nominales utilisées dans le simulateur principal.
BASE_PARAMS = {
    "largeur_x_mm": 61.5,
    "longueur_y_mm": 117.5,
    "epaisseur_mm": 1.7,
    "resolution_grille": 12,
    "diffusivite_alpha": 97.0,
    "masse_volumique_rho": 2.7e-3,
    "chaleur_massique_cp": 0.9,
    "coeff_convection_h": 5.0e-5,
    "pos_x_capteur_2_mm": 0.0,
    "pos_y_capteur_2_mm": 59.42,
    "pos_x_capteur_3_mm": 0.0,
    "pos_y_capteur_3_mm": 103.79,
    "pos_x_resistance_mm": 0.0,
    "pos_y_resistance_mm": 38.0,
}

EXPERIMENT_SPECS = [
    {"keywords": ("0.81", "4.5"), "power_w": 0.81},
    {"keywords": ("1.44",), "power_w": 1.44},
    {"keywords": ("2.56", "8v"), "power_w": 2.56},
    {"keywords": ("4w", "10v"), "power_w": 4.0},
    # Les fichiers 3.24 W et 9 W contiennent des transitoires moins propres au départ.
    # Ils peuvent être réintégrés plus tard, mais on garde ici le jeu de calibration le plus stable.
]


@dataclass(frozen=True)
class StepExperiment:
    name: str
    power_w: float
    time_s: np.ndarray
    t2_delta_c: np.ndarray
    t3_delta_c: np.ndarray


def _normalize_name(name: str) -> str:
    return (
        name.lower()
        .replace("é", "e")
        .replace("è", "e")
        .replace("ê", "e")
        .replace("à", "a")
        .replace("â", "a")
        .replace("î", "i")
        .replace("ô", "o")
        .replace("û", "u")
        .replace("œ", "oe")
    )


def _resolve_data_dir(data_dir: Path) -> Path:
    candidates = [
        data_dir,
        REPO_ROOT / "TestsAndData" / data_dir.name,
        REPO_ROOT / data_dir.name,
    ]

    for candidate in candidates:
        if candidate.exists() and candidate.is_dir():
            return candidate

    searched = "\n  - ".join(str(path) for path in candidates)
    raise FileNotFoundError(
        "Aucun dossier de données valide n'a été trouvé. Emplacements vérifiés :\n"
        f"  - {searched}"
    )


def _match_csv_files(data_dir: Path) -> list[tuple[Path, float]]:
    data_dir = _resolve_data_dir(data_dir)
    csv_files = [path for path in data_dir.glob("*.csv") if path.is_file()]
    matches: list[tuple[Path, float]] = []

    for spec in EXPERIMENT_SPECS:
        for path in csv_files:
            normalized = _normalize_name(path.name)
            if all(keyword in normalized for keyword in spec["keywords"]):
                matches.append((path, spec["power_w"]))
                break

    if not matches:
        raise FileNotFoundError(f"Aucun fichier CSV exploitable n'a été trouvé dans {data_dir}")

    return matches


def load_step_experiments(data_dir: Path = DATA_DIR, max_time_s: float = 600.0, downsample: int = 50) -> list[StepExperiment]:
    experiments: list[StepExperiment] = []

    for path, power_w in _match_csv_files(data_dir):
        df = pd.read_csv(path)
        required_columns = {"Temps_s", "T2", "T3"}
        if not required_columns.issubset(df.columns):
            raise ValueError(f"Colonnes manquantes dans {path.name}: {required_columns - set(df.columns)}")

        ref_signal = df[["T2", "T3"]].mean(axis=1).to_numpy(dtype=float)
        search_limit = max(20, len(ref_signal) // 4)
        start_idx = int(np.argmin(ref_signal[:search_limit]))

        df = df.iloc[start_idx:].copy()
        time_s = df["Temps_s"].to_numpy(dtype=float)
        time_s = time_s - time_s[0]
        mask = time_s <= min(max_time_s, float(time_s[-1]))
        time_s = time_s[mask][::downsample]

        t2 = df["T2"].to_numpy(dtype=float)[mask]
        t3 = df["T3"].to_numpy(dtype=float)[mask]
        t2_delta = (t2 - t2[0])[::downsample]
        t3_delta = (t3 - t3[0])[::downsample]

        experiments.append(
            StepExperiment(
                name=path.name,
                power_w=power_w,
                time_s=time_s,
                t2_delta_c=t2_delta,
                t3_delta_c=t3_delta,
            )
        )

    return experiments


def _simulate_delta_response(power_w: float, target_times: np.ndarray, coeff_convection_h: float, facteur_couplage: float, tau_perturbation_s: float) -> tuple[np.ndarray, np.ndarray]:
    p = BASE_PARAMS
    resolution = int(p["resolution_grille"])
    pas_x = p["largeur_x_mm"] / resolution
    pas_y = p["longueur_y_mm"] / resolution

    alpha = p["diffusivite_alpha"]
    rho = p["masse_volumique_rho"]
    cp = p["chaleur_massique_cp"]
    epaisseur = p["epaisseur_mm"]

    dt_stable = 0.5 / (alpha * ((1 / pas_x**2) + (1 / pas_y**2)))
    pas_temps = min(0.15 * min(pas_x, pas_y) ** 2 / alpha, dt_stable)

    cst_diffusion_x = alpha * pas_temps / pas_x**2
    cst_diffusion_y = alpha * pas_temps / pas_y**2
    cst_convection = coeff_convection_h * pas_temps / (rho * cp * epaisseur)

    def coord_x_vers_indice(coord_x: float) -> int:
        indice = int(round((coord_x + p["largeur_x_mm"] / 2) / pas_x))
        return int(np.clip(indice, 0, resolution))

    def coord_y_vers_indice(coord_y: float) -> int:
        indice = int(round(coord_y / pas_y))
        return int(np.clip(indice, 0, resolution))

    idx_x_t2 = coord_x_vers_indice(p["pos_x_capteur_2_mm"])
    idx_y_t2 = coord_y_vers_indice(p["pos_y_capteur_2_mm"])
    idx_x_t3 = coord_x_vers_indice(p["pos_x_capteur_3_mm"])
    idx_y_t3 = coord_y_vers_indice(p["pos_y_capteur_3_mm"])
    idx_x_res = coord_x_vers_indice(p["pos_x_resistance_mm"])
    idx_y_res = coord_y_vers_indice(p["pos_y_resistance_mm"])

    zone_res = np.s_[max(0, idx_y_res):min(resolution + 1, idx_y_res + 2), max(0, idx_x_res - 1):min(resolution + 1, idx_x_res + 1)]
    denominateur_resistance = rho * cp * epaisseur * pas_x * pas_y

    matrice_t = np.zeros((resolution + 1, resolution + 1), dtype=np.float64)
    matrice_t_suivante = matrice_t.copy()

    temps_courant = 0.0
    puissance_resistance_effective = 0.0
    puissance_resistance_cible = max(0.0, power_w * facteur_couplage)
    constante_lag = max(0.0, tau_perturbation_s)

    t2_out: list[float] = []
    t3_out: list[float] = []

    for temps_cible in target_times:
        while temps_courant < temps_cible:
            if constante_lag > 0:
                coeff_lag = min(1.0, pas_temps / constante_lag)
                puissance_resistance_effective += (puissance_resistance_cible - puissance_resistance_effective) * coeff_lag
            else:
                puissance_resistance_effective = puissance_resistance_cible

            ajout_temp_resistance = (puissance_resistance_effective * pas_temps) / denominateur_resistance

            matrice_t_suivante[1:-1, 1:-1] = matrice_t[1:-1, 1:-1] + (
                cst_diffusion_x * (matrice_t[1:-1, 2:] - 2 * matrice_t[1:-1, 1:-1] + matrice_t[1:-1, :-2])
                + cst_diffusion_y * (matrice_t[2:, 1:-1] - 2 * matrice_t[1:-1, 1:-1] + matrice_t[:-2, 1:-1])
            )
            matrice_t_suivante[1:-1, 1:-1] -= cst_convection * matrice_t[1:-1, 1:-1]
            matrice_t_suivante[zone_res] += ajout_temp_resistance

            matrice_t_suivante[0, :] = matrice_t_suivante[1, :]
            matrice_t_suivante[-1, :] = matrice_t_suivante[-2, :]
            matrice_t_suivante[:, 0] = matrice_t_suivante[:, 1]
            matrice_t_suivante[:, -1] = matrice_t_suivante[:, -2]

            matrice_t, matrice_t_suivante = matrice_t_suivante, matrice_t
            temps_courant += pas_temps

        t2_out.append(float(matrice_t[idx_y_t2, idx_x_t2]))
        t3_out.append(float(matrice_t[idx_y_t3, idx_x_t3]))

    return np.array(t2_out), np.array(t3_out)


def evaluate_rmse(experiments: Iterable[StepExperiment], coeff_convection_h: float, facteur_couplage: float, tau_perturbation_s: float) -> float:
    erreurs = []

    for exp in experiments:
        t2_sim, t3_sim = _simulate_delta_response(
            exp.power_w,
            exp.time_s,
            coeff_convection_h=coeff_convection_h,
            facteur_couplage=facteur_couplage,
            tau_perturbation_s=tau_perturbation_s,
        )
        erreurs.append(np.mean((t2_sim - exp.t2_delta_c) ** 2))
        erreurs.append(np.mean((t3_sim - exp.t3_delta_c) ** 2))

    return math.sqrt(float(np.mean(erreurs)))


def calibrate_from_step_files(data_dir: Path = DATA_DIR) -> dict:
    experiments = load_step_experiments(data_dir=data_dir)

    baseline = {
        "coeff_convection_h": BASE_PARAMS["coeff_convection_h"],
        "facteur_couplage": 1.0,
        "tau_perturbation_s": 0.0,
    }

    def objective(vector: np.ndarray) -> float:
        coeff_convection_h, facteur_couplage, tau_perturbation_s = vector

        if coeff_convection_h <= 0 or facteur_couplage < 0 or tau_perturbation_s < 0:
            return 1e9

        rmse = evaluate_rmse(
            experiments,
            coeff_convection_h=coeff_convection_h,
            facteur_couplage=facteur_couplage,
            tau_perturbation_s=tau_perturbation_s,
        )
        return rmse**2

    resultat = minimize(
        objective,
        x0=np.array([baseline["coeff_convection_h"], 0.85, 8.0], dtype=float),
        method="L-BFGS-B",
        bounds=[(1e-6, 3e-4), (0.3, 1.8), (0.0, 60.0)],
        options={"maxiter": 18},
    )

    best_vector = {
        "coeff_convection_h": float(resultat.x[0]),
        "facteur_couplage": float(resultat.x[1]),
        "tau_perturbation_s": float(resultat.x[2]),
    }

    rapport = {
        "success": bool(resultat.success),
        "message": str(resultat.message),
        "rmse_avant_C": evaluate_rmse(experiments, **baseline),
        "rmse_apres_C": evaluate_rmse(experiments, **best_vector),
        "parametres": {
            "coeff_convection_h": round(best_vector["coeff_convection_h"], 8),
            "facteur_couplage_perturbation": round(best_vector["facteur_couplage"], 3),
            "constante_temps_perturbation_s": round(best_vector["tau_perturbation_s"], 2),
        },
        "fichiers_utilises": [exp.name for exp in experiments],
    }
    return rapport


def write_calibration_file(report: dict, output_path: Path = OUTPUT_FILE) -> Path:
    output_path.write_text(json.dumps({"parametres": report["parametres"], "calibration": report}, indent=4, ensure_ascii=False), encoding="utf-8")
    return output_path


def main() -> None:
    report = calibrate_from_step_files()
    output_path = write_calibration_file(report)

    print("=== Calibration thermique à partir des échelons de perturbation ===")
    print(f"Fichiers utilisés : {len(report['fichiers_utilises'])}")
    print(f"RMSE avant  : {report['rmse_avant_C']:.3f} °C")
    print(f"RMSE après  : {report['rmse_apres_C']:.3f} °C")
    print("\nParamètres recommandés pour SimulateurUpgrade.py :")
    for cle, valeur in report["parametres"].items():
        print(f"  - {cle} = {valeur}")
    print(f"\nPreset JSON écrit dans : {output_path}")


if __name__ == "__main__":
    main()
