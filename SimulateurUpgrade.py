import sys
import json
import time
import ctypes
from ctypes import wintypes
import traceback
from threading import Lock

import numpy as np
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel,
                             QFileDialog, QSplitter, QFrame,
                             QScrollArea, QMessageBox, QProgressBar,
                             QGroupBox, QSlider, QLineEdit,
                             QSizePolicy, QComboBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont
import pyqtgraph as pg
import pyqtgraph.opengl as gl

# ==============================================================================
# WIDGET PERSONNALISÉ : Le Slider "à la Desmos"
# ==============================================================================
class SliderWithValue(QWidget):
    def __init__(self, min_val, max_val, default_val, decimals=1, scientific=False, parent=None):
        super().__init__(parent)
        self.decimals = decimals
        self.scientific = scientific
        self.min_val = min_val
        self.max_val = max_val
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 10000)
        self.slider.setTickPosition(QSlider.TickPosition.NoTicks)
        self.slider_value = int((default_val - min_val) / (max_val - min_val) * 10000)
        self.slider.setValue(self.slider_value)
        self.slider.setStyleSheet("""
            QSlider::groove:horizontal { border: none; height: 4px; background: #334155; border-radius: 2px; }
            QSlider::handle:horizontal { background: #38BDF8; border: 2px solid #0EA5E9; width: 14px; margin: -5px 0; border-radius: 7px; }
            QSlider::handle:horizontal:hover { background: #7DD3FC; }
            QSlider::sub-page:horizontal { background: #0EA5E9; border-radius: 2px; }
        """)
        
        self.value_input = QLineEdit()
        self.value_input.setMaximumWidth(80)
        self.value_input.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.value_input.setStyleSheet("""
            QLineEdit { color: #38BDF8; background-color: transparent; border: 1px solid #334155; border-radius: 4px; padding: 4px 8px; font-weight: bold; font-size: 12px; selection-background-color: #0EA5E9; }
            QLineEdit:focus { border: 1px solid #0EA5E9; background-color: rgba(14, 165, 233, 0.1); }
        """)
        self.update_value_label()
        
        self.slider.valueChanged.connect(self.on_slider_changed)
        self.value_input.returnPressed.connect(self.on_text_edited)
        self.value_input.editingFinished.connect(self.on_text_edited)
        
        layout.addWidget(self.slider, 1)
        layout.addWidget(self.value_input, 0)
    
    def on_slider_changed(self):
        self.update_value_label()
    
    def on_text_edited(self):
        try:
            nouveau_val = float(self.value_input.text().replace(',', '.'))
            if self.min_val <= nouveau_val <= self.max_val:
                slider_val = int((nouveau_val - self.min_val) / (self.max_val - self.min_val) * 10000)
                self.slider.blockSignals(True)
                self.slider.setValue(slider_val)
                self.slider.blockSignals(False)
                self.update_value_label()
        except ValueError:
            self.update_value_label()
    
    def update_value_label(self):
        slider_val = self.slider.value()
        actual_val = self.min_val + (slider_val / 10000) * (self.max_val - self.min_val)
        if self.scientific:
            self.value_input.setText(f"{actual_val:.{self.decimals}e}")
        elif self.decimals == 0:
            self.value_input.setText(f"{int(actual_val)}")
        else:
            self.value_input.setText(f"{actual_val:.{self.decimals}f}")
    
    def value(self):
        slider_val = self.slider.value()
        return self.min_val + (slider_val / 10000) * (self.max_val - self.min_val)
    
    def setValue(self, val):
        self.slider_value = int((val - self.min_val) / (self.max_val - self.min_val) * 10000)
        self.slider.blockSignals(True)
        self.slider.setValue(self.slider_value)
        self.slider.blockSignals(False)
        self.update_value_label()

# ==============================================================================
# STYLE GLOBAL
# ==============================================================================
DARK_QSS = """
QMainWindow { background-color: #0F172A; }
QWidget { color: #E2E8F0; font-family: 'Segoe UI', -apple-system, sans-serif; font-size: 13px; }
QScrollBar:vertical {
    border: none;
    background-color: rgba(148, 163, 184, 0.10);
    width: 7px;
    border-radius: 3px;
    margin: 4px 1px 4px 1px;
}
QScrollBar::handle:vertical {
    background-color: rgba(56, 189, 248, 0.95);
    border: none;
    border-radius: 3px;
    min-height: 34px;
}
QScrollBar::handle:vertical:hover {
    background-color: rgba(125, 211, 252, 1.0);
}
QScrollBar::handle:vertical:pressed {
    background-color: rgba(14, 165, 233, 1.0);
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
    background: transparent;
    border: none;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
    border-radius: 3px;
}
#LeftPanel {
    background-color: #111827;
    border: 1px solid #1F2937;
    border-radius: 14px;
}
#ScrollPanel {
    border: none;
    background-color: transparent;
}
#ScrollContent {
    background-color: transparent;
    border: none;
}
QScrollArea > QWidget > QWidget {
    background-color: transparent;
}
#ControlsFrame {
    background-color: rgba(15, 23, 42, 0.95);
    border: 1px solid #1E3A5F;
    border-radius: 12px;
    margin-top: 8px;
}
#RightPanel {
    background-color: #081225;
    border: 1px solid #16243B;
    border-radius: 14px;
}
#ThreeDPanel, #PlotPanel {
    background-color: rgba(11, 23, 43, 0.96);
    border: 1px solid #1E3A5F;
    border-radius: 12px;
}
#ThreeDPanel {
    padding: 8px;
}
#PlotPanel {
    padding: 6px;
}

/* === TITRES DE GROUPES === */
QGroupBox { 
    border: 1px solid #334155; 
    border-radius: 10px; 
    margin-top: 18px;
    padding-top: 28px; 
    background-color: rgba(30, 41, 59, 0.72); 
}
QGroupBox::title { 
    subcontrol-origin: margin; 
    subcontrol-position: top center;
    padding: 8px 18px; 
    background-color: #0EA5E9; 
    color: #FFFFFF; 
    font-size: 14px; 
    font-weight: 700; 
    border-radius: 6px;
    letter-spacing: 0.5px;
}

QLabel { color: #CBD5E1; font-size: 11px; }
#Section {
    background-color: transparent;
    border-top: 1px solid #1E293B;
    margin-top: 6px;
    padding-top: 6px;
}
QPushButton { background-color: #334155; color: #F8FAFC; border: 1px solid #475569; border-radius: 5px; padding: 8px 12px; font-weight: 600; font-size: 11px; }
QPushButton:hover { background-color: #475569; border: 1px solid #64748B; }
#btn_import, #btn_save { background-color: #3B82F6; border: 1px solid #1E40AF; }
#btn_import:hover, #btn_save:hover { background-color: #60A5FA; }
#btn_fullscreen, #btn_exit_fullscreen {
    background-color: rgba(124, 58, 237, 0.92);
    border: 1px solid #6D28D9;
    color: white;
    font-size: 16px;
    font-weight: bold;
    min-width: 38px;
    max-width: 38px;
    min-height: 38px;
    max-height: 38px;
    padding: 0px;
    border-radius: 19px;
}
#btn_fullscreen:hover, #btn_exit_fullscreen:hover { background-color: rgba(139, 92, 246, 0.98); }
#btn_mode_pid, #btn_mode_manual {
    background-color: #1E293B;
    color: #CBD5E1;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 7px 10px;
    font-weight: 700;
}
#btn_mode_pid:checked, #btn_mode_manual:checked {
    background-color: #0EA5E9;
    color: white;
    border: 1px solid #38BDF8;
}
#btn_mode_pid:hover, #btn_mode_manual:hover { border: 1px solid #38BDF8; }
#btn_go { background-color: #10B981; border: 1px solid #059669; color: white; font-size: 12px; font-weight: bold; padding: 9px 14px; }
#btn_go:hover { background-color: #34D399; }
#btn_close { background-color: #EF4444; border: 1px solid #DC2626; color: white; font-size: 12px; font-weight: bold; padding: 9px 14px; }
#btn_close:hover { background-color: #F87171; }
#btn_pause { background-color: #F59E0B; border: 1px solid #D97706; color: white; font-size: 12px; font-weight: bold; padding: 9px 14px; }
#btn_pause:hover { background-color: #FBBF24; }
#btn_quicksave { background-color: #8B5CF6; border: 1px solid #7C3AED; color: white; font-size: 12px; font-weight: bold; padding: 9px 14px; }
#btn_quicksave:hover { background-color: #A78BFA; }
#btn_quicksave:disabled { background-color: #4C1D95; color: #9CA3AF; border: 1px solid #312E81;}
QProgressBar { border: 1px solid #334155; border-radius: 4px; background-color: #1E293B; text-align: center; color: white; font-weight: bold; font-size: 10px; min-height: 18px; }
QProgressBar::chunk { background-color: #10B981; border-radius: 3px; }
QSplitter::handle { background-color: transparent; }
QSplitter::handle:hover { background-color: rgba(14, 165, 233, 0.2); }
"""


def calculer_facteur_stabilite_numerique(params):
    resolution = int(round(params["resolution_grille"]))
    pas_x = params["largeur_x_mm"] / resolution
    pas_y = params["longueur_y_mm"] / resolution

    limite_stabilite = 0.5 / (params["diffusivite_alpha"] * ((1 / pas_x**2) + (1 / pas_y**2)))
    pas_temps = 0.2 * min(pas_x, pas_y)**2 / params["diffusivite_alpha"]
    pas_temps = min(pas_temps, limite_stabilite)

    # Conversion en unités SI pour un calcul cohérent.
    alpha_si = params["diffusivite_alpha"] * 1e-6
    rho_si = params["masse_volumique_rho"] * 1e6
    cp_si = params["chaleur_massique_cp"] * 1e3
    k_si = alpha_si * rho_si * cp_si
    dx_si = pas_x * 1e-3
    dy_si = pas_y * 1e-3

    facteur = (k_si * pas_temps) / (rho_si * cp_si * (dx_si**2))
    if not np.isclose(dx_si, dy_si):
        facteur += (k_si * pas_temps) / (rho_si * cp_si * (dy_si**2))
    else:
        facteur *= 2.0

    return {
        "facteur": facteur,
        "k_si": k_si,
        "rho_si": rho_si,
        "cp_si": cp_si,
        "pas_temps_s": pas_temps,
        "pas_x_mm": pas_x,
        "pas_y_mm": pas_y,
    }


def calculer_bornes_temperature_fixes(params):
    temp_min = float(params["temperature_ambiante_C"])
    marge_haute = max(8.0, abs(float(params.get("puissance_tec_W", 0.0))) * 4.0)
    temp_max = max(
        temp_min + 10.0,
        float(params.get("consigne_C", temp_min)) + 5.0,
        temp_min + marge_haute,
    )
    return temp_min, temp_max

class StableGLViewWidget(gl.GLViewWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lock_2d_interaction = False
        self.last_manual_interaction = 0.0

    def _marquer_interaction_utilisateur(self):
        self.last_manual_interaction = time.perf_counter()

    def interaction_manuelle_recente(self, cooldown_s=1.25):
        return (time.perf_counter() - self.last_manual_interaction) < cooldown_s

    def mousePressEvent(self, event):
        if self.lock_2d_interaction:
            event.accept()
            return
        self._marquer_interaction_utilisateur()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.lock_2d_interaction:
            event.accept()
            return
        self._marquer_interaction_utilisateur()
        super().mouseMoveEvent(event)

    def wheelEvent(self, event):
        if self.lock_2d_interaction:
            event.accept()
            return
        self._marquer_interaction_utilisateur()
        super().wheelEvent(event)


# ==============================================================================
# THREAD DE SIMULATION
# ==============================================================================
class SimulationThread(QThread):
    progress_signal = pyqtSignal(int)
    update_signal = pyqtSignal(float, np.ndarray, float, float, float)
    finished_signal = pyqtSignal(dict, dict)
    error_signal = pyqtSignal(str)

    def __init__(self, data, mode_pid_actif):
        super().__init__()
        self.parametres = dict(data)
        self.en_cours_d_execution = True
        self.en_pause = False
        self._control_lock = Lock()

        self.mode_pid_actif = mode_pid_actif
        self.puissance_manuelle_voulue = float(data["puissance_tec_W"])
        self.consigne_voulue = float(data["consigne_C"])

        # --- NOUVEAU : Tension Dynamique ---
        self.tension_dynamique = float(data["tension_resistance_V"])
        self.puissance_dynamique = 0.0

        # Calibration empirique issue des essais d'échelons de la résistance.
        self.facteur_couplage_perturbation = max(0.0, float(data.get("facteur_couplage_perturbation", 0.85)))
        self.constante_temps_perturbation_s = max(0.0, float(data.get("constante_temps_perturbation_s", 8.0)))
        self.puissance_resistance_effective = 0.0

    def modifier_parametres_controle(self, mode_pid_actif, nouvelle_puissance, nouvelle_consigne, nouvelle_tension):
        with self._control_lock:
            self.mode_pid_actif = bool(mode_pid_actif)
            self.puissance_manuelle_voulue = float(nouvelle_puissance)
            self.consigne_voulue = float(nouvelle_consigne)
            self.tension_dynamique = float(nouvelle_tension)

    def obtenir_etat_controle(self):
        with self._control_lock:
            return (
                self.mode_pid_actif,
                self.puissance_manuelle_voulue,
                self.consigne_voulue,
                self.tension_dynamique,
            )

    # --- NOUVEAU : Fonction Pause ---
    def toggle_pause(self):
        with self._control_lock:
            self.en_pause = not self.en_pause
            return self.en_pause

    def run(self):
        resultats_finaux = {"temps": [], "T1": [], "T2": [], "T3": []}

        try:
            params = dict(self.parametres)
            resolution = int(params["resolution_grille"])

            vecteur_x = np.linspace(-params["largeur_x_mm"]/2, params["largeur_x_mm"]/2, resolution + 1)
            vecteur_y = np.linspace(0, params["longueur_y_mm"], resolution + 1)
            grille_X, grille_Y = np.meshgrid(vecteur_x, vecteur_y)

            pas_x = params["largeur_x_mm"] / resolution
            pas_y = params["longueur_y_mm"] / resolution

            limite_stabilite = 0.5 / (params["diffusivite_alpha"] * ((1/pas_x**2) + (1/pas_y**2)))
            pas_temps = 0.2 * min(pas_x, pas_y)**2 / params["diffusivite_alpha"]
            pas_temps = min(pas_temps, limite_stabilite)

            volume_module_tec = (2 * pas_x) * (2 * pas_y) * params["epaisseur_mm"]

            cst_diffusion_x = params["diffusivite_alpha"] * pas_temps / pas_x**2
            cst_diffusion_y = params["diffusivite_alpha"] * pas_temps / pas_y**2

            cst_perte_convection = params["coeff_convection_h"] * pas_temps / (params["masse_volumique_rho"] * params["chaleur_massique_cp"] * params["epaisseur_mm"])

            matrice_T = np.full_like(grille_X, params["temperature_ambiante_C"], dtype=np.float32)
            matrice_T_suivante = matrice_T.copy()

            def coord_x_vers_indice(coord_x):
                indice = int(round((coord_x + params["largeur_x_mm"]/2) / pas_x))
                return int(np.clip(indice, 0, resolution))

            def coord_y_vers_indice(coord_y):
                indice = int(round(coord_y / pas_y))
                return int(np.clip(indice, 0, resolution))

            def creer_zone_source(idx_y, idx_x):
                y_debut = max(0, idx_y)
                y_fin = min(resolution + 1, idx_y + 2)
                x_debut = max(0, idx_x - 1)
                x_fin = min(resolution + 1, idx_x + 1)
                return np.s_[y_debut:y_fin, x_debut:x_fin]

            idx_x_T1, idx_y_T1 = coord_x_vers_indice(params["pos_x_capteur_1_mm"]), coord_y_vers_indice(params["pos_y_capteur_1_mm"])
            idx_x_T2, idx_y_T2 = coord_x_vers_indice(params["pos_x_capteur_2_mm"]), coord_y_vers_indice(params["pos_y_capteur_2_mm"])
            idx_x_T3, idx_y_T3 = coord_x_vers_indice(params["pos_x_capteur_3_mm"]), coord_y_vers_indice(params["pos_y_capteur_3_mm"])
            idx_x_tec, idx_y_tec = coord_x_vers_indice(params["pos_x_tec_mm"]), coord_y_vers_indice(params["pos_y_tec_mm"])
            idx_x_res, idx_y_res = coord_x_vers_indice(params["pos_x_resistance_mm"]), coord_y_vers_indice(params["pos_y_resistance_mm"])
            zone_tec = creer_zone_source(idx_y_tec, idx_x_tec)
            zone_res = creer_zone_source(idx_y_res, idx_x_res)

            frequence_pid = 10.0
            periode_pid = 1.0 / frequence_pid
            prochain_temps_pid = 0.0
            limit_pwm_percent = 100.0

            aw_kc = 1.5
            pd_b0 = 38.142857
            pd_b1 = -38.047619
            pd_a1 = -0.904762
            int_alpha = 0.998751

            e_prev1 = 0.0
            uD_prev = 0.0
            uI_prev = 0.0
            u_prev = 0.0
            self.pwmActuel = 0

            table_consignes = [10.20, 12.15, 12.70, 16.20, 30.70, 36.38, 41.30, 54.10]
            table_pwm = [-30.0, -20.0, -15.0, -10.0, 10.0, 15.0, 20.0, 30.0]

            def obtenir_uop(target):
                if target <= table_consignes[0]:
                    return table_pwm[0]
                if target >= table_consignes[-1]:
                    return table_pwm[-1]
                for i in range(len(table_consignes) - 1):
                    if table_consignes[i] <= target <= table_consignes[i + 1]:
                        pct = (target - table_consignes[i]) / (table_consignes[i+1] - table_consignes[i])
                        return table_pwm[i] + pct * (table_pwm[i+1] - table_pwm[i])
                return 0.0

            calculs_par_actualisation = 150
            temps_ecoule = 0.0
            compteur_images = 0

            historique_temps = [0.0]
            historique_T1 = [float(matrice_T[idx_y_T1, idx_x_T1])]
            historique_T2 = [float(matrice_T[idx_y_T2, idx_x_T2])]
            historique_T3 = [float(matrice_T[idx_y_T3, idx_x_T3])]

            self.update_signal.emit(0.0, matrice_T.copy(), historique_T1[0], historique_T2[0], historique_T3[0])

            # Vérification explicite du facteur de stabilité en unités SI.
            infos_stabilite = calculer_facteur_stabilite_numerique(params)
            facteur = infos_stabilite["facteur"]

            if facteur >= 0.5:
                message = (
                    f"Erreur : Le facteur de stabilité est de {facteur:.6f}. "
                    "Il doit être strictement inférieur à 0.5 pour éviter que la simulation diverge."
                )
                print(message)
                self.error_signal.emit(message)
                return

            while self.en_cours_d_execution and temps_ecoule < params["temps_total_s"]:

                while self.en_pause and self.en_cours_d_execution:
                    self.msleep(50)
                if not self.en_cours_d_execution:
                    break

                mode_pid_actif, puissance_manuelle, consigne, tension_dynamique = self.obtenir_etat_controle()

                if mode_pid_actif:
                    if temps_ecoule >= prochain_temps_pid:
                        t3_actuel = matrice_T[idx_y_T3, idx_x_T3]
                        e_k = consigne - t3_actuel
                        aw_uop = obtenir_uop(consigne)

                        uD = (aw_kc * pd_b0 * e_k) + (aw_kc * pd_b1 * e_prev1) - (pd_a1 * uD_prev)
                        uI = (1.0 - int_alpha) * (u_prev - aw_uop) + (int_alpha * uI_prev)
                        v = uD + aw_uop + uI

                        u_sat = np.clip(v, -limit_pwm_percent, limit_pwm_percent)

                        uD_prev = uD
                        uI_prev = uI
                        e_prev1 = e_k
                        u_prev = u_sat

                        pwm_demande = int(u_sat * 10.23)
                        limit_var = 100

                        if pwm_demande > self.pwmActuel + limit_var:
                            self.pwmActuel += limit_var
                        elif pwm_demande < self.pwmActuel - limit_var:
                            self.pwmActuel -= limit_var
                        else:
                            self.pwmActuel = pwm_demande

                        pwm_percent_abs = (abs(self.pwmActuel) / 1023.0) * 100.0
                        puissance_w = (((1.703277e-05 * pwm_percent_abs + 9.947817e-04) * pwm_percent_abs) + 1.406312e-01) * pwm_percent_abs + 1.734031e-02

                        if self.pwmActuel < 0:
                            self.puissance_dynamique = -puissance_w
                        elif self.pwmActuel > 0:
                            self.puissance_dynamique = puissance_w
                        else:
                            self.puissance_dynamique = 0.0

                        prochain_temps_pid += periode_pid
                else:
                    self.puissance_dynamique = puissance_manuelle

                tension_dynamique = max(0.0, tension_dynamique)
                puissance_volumique_tec = self.puissance_dynamique / volume_module_tec
                ajout_temp_tec = (puissance_volumique_tec * pas_temps) / (params["masse_volumique_rho"] * params["chaleur_massique_cp"])

                puissance_resistance_cible = self.facteur_couplage_perturbation * (tension_dynamique**2) / params["valeur_resistance_ohm"]
                denominateur_resistance = (
                    params["masse_volumique_rho"] * params["chaleur_massique_cp"] *
                    params["epaisseur_mm"] * pas_x * pas_y
                )

                for _ in range(calculs_par_actualisation):
                    if temps_ecoule >= params["temps_total_s"]:
                        break

                    if self.constante_temps_perturbation_s > 0:
                        coeff_lag_resistance = min(1.0, pas_temps / self.constante_temps_perturbation_s)
                        self.puissance_resistance_effective += (
                            puissance_resistance_cible - self.puissance_resistance_effective
                        ) * coeff_lag_resistance
                    else:
                        self.puissance_resistance_effective = puissance_resistance_cible

                    ajout_temp_resistance = (self.puissance_resistance_effective * pas_temps) / denominateur_resistance

                    matrice_T_suivante[1:-1,1:-1] = matrice_T[1:-1,1:-1] + (
                        cst_diffusion_x * (matrice_T[1:-1,2:] - 2*matrice_T[1:-1,1:-1] + matrice_T[1:-1,:-2]) +
                        cst_diffusion_y * (matrice_T[2:,1:-1] - 2*matrice_T[1:-1,1:-1] + matrice_T[:-2,1:-1])
                    )
                    matrice_T_suivante[1:-1,1:-1] -= cst_perte_convection * (matrice_T[1:-1,1:-1] - params["temperature_ambiante_C"])

                    matrice_T_suivante[zone_tec] += ajout_temp_tec
                    matrice_T_suivante[zone_res] += ajout_temp_resistance

                    matrice_T_suivante[0,:] = matrice_T_suivante[1,:]
                    matrice_T_suivante[-1,:] = matrice_T_suivante[-2,:]
                    matrice_T_suivante[:,0] = matrice_T_suivante[:,1]
                    matrice_T_suivante[:,-1] = matrice_T_suivante[:,-2]

                    matrice_T, matrice_T_suivante = matrice_T_suivante, matrice_T
                    temps_ecoule += pas_temps

                historique_temps.append(temps_ecoule)
                historique_T1.append(matrice_T[idx_y_T1, idx_x_T1])
                historique_T2.append(matrice_T[idx_y_T2, idx_x_T2])
                historique_T3.append(matrice_T[idx_y_T3, idx_x_T3])

                self.progress_signal.emit(int((temps_ecoule / params["temps_total_s"]) * 100))
                compteur_images += 1
                if compteur_images % max(1, int(params["intervalle_affichage"])) == 0:
                    self.update_signal.emit(
                        temps_ecoule,
                        matrice_T.copy(),
                        matrice_T[idx_y_T1, idx_x_T1],
                        matrice_T[idx_y_T2, idx_x_T2],
                        matrice_T[idx_y_T3, idx_x_T3],
                    )

            resultats_finaux = {"temps": historique_temps, "T1": historique_T1, "T2": historique_T2, "T3": historique_T3}
            if temps_ecoule >= params["temps_total_s"]:
                self.progress_signal.emit(100)
            self.finished_signal.emit(params, resultats_finaux)
        except Exception:
            self.error_signal.emit(traceback.format_exc())

    def stop(self):
        with self._control_lock:
            self.en_cours_d_execution = False
            self.en_pause = False

# ==============================================================================
# FENÊTRE PRINCIPALE
# ==============================================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(DARK_QSS)
        self.setWindowTitle("Simulateur de plaque asservie en température")
        
        self.demarrer_en_plein_ecran = False

        dialog = QMessageBox()
        dialog.setWindowTitle("Taille de la fenêtre")
        dialog.setText("Quelle taille de fenêtre voulez-vous ?")
        dialog.setIcon(QMessageBox.Icon.Question)
        dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        dialog.setWindowFlag(Qt.WindowType.Window, True)
        dialog.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        btn_80 = dialog.addButton("80% de l'écran", QMessageBox.ButtonRole.AcceptRole)
        btn_plein = dialog.addButton("Plein écran", QMessageBox.ButtonRole.RejectRole)
        dialog.raise_()
        dialog.activateWindow()
        dialog.exec()

        self.demarrer_en_plein_ecran = (dialog.clickedButton() == btn_plein)

        if not self.demarrer_en_plein_ecran:
            ecran = QApplication.primaryScreen()
            geometrie_ecran = ecran.geometry()
            largeur_80 = int(geometrie_ecran.width() * 0.8)
            hauteur_80 = int(geometrie_ecran.height() * 0.8)
            self.resize(largeur_80, hauteur_80)
            x = (geometrie_ecran.width() - largeur_80) // 2
            y = (geometrie_ecran.height() - hauteur_80) // 2
            self.move(x, y)

        self.donnees_entree = None
        self.donnees_resultats = None
        self.chemin_sauvegarde = ""
        self.export_apres_arret = False
        self.params_actuels = {}
        self.thread_simulation = None
        
        self.historique_matrices_3D = []
        self.mode_direct_actif = True
        self.temperature_ambiante_ref = 20.0
        self.temperature_max_globale = 21.0
        self.exageration_z = 5.0
        self.camera_distance_initiale = 150.0
        self.camera_elevation_initiale = 45.0
        self.camera_azimuth_initiale = 45.0
        self.camera_distance_actuelle = self.camera_distance_initiale
        self.camera_centre_z = 0.0
        self.vue_2d_active = False
        self.perspective_fov = 45.0
        self.perspective_fov_reference = 45.0
        self.annotations_axes_3d = {}
        self._horodatage_cpu_precedent = time.perf_counter()
        self._temps_cpu_precedent = time.process_time()

        positions_couleurs = np.linspace(0.0, 1.0, 5)
        valeurs_rgb = np.array([
            [68, 1, 84, 255],     
            [49, 104, 142, 255],  
            [200, 70, 150, 255],  
            [255, 100, 100, 255], 
            [255, 0, 0, 255]   
        ], dtype=np.ubyte)
        self.palette_couleurs = pg.ColorMap(positions_couleurs, valeurs_rgb)

        widget_central = QWidget()
        self.setCentralWidget(widget_central)
        layout_principal = QVBoxLayout(widget_central)
        separateur_principal = QSplitter(Qt.Orientation.Horizontal)
        layout_principal.addWidget(separateur_principal)

        panneau_gauche = QWidget()
        panneau_gauche.setObjectName("LeftPanel")
        layout_gauche = QVBoxLayout(panneau_gauche)
        layout_gauche.setContentsMargins(10, 10, 10, 10)
        layout_gauche.setSpacing(10)
        
        zone_defilement = QScrollArea()
        zone_defilement.setObjectName("ScrollPanel")
        zone_defilement.setWidgetResizable(True)
        zone_defilement.setFrameShape(QFrame.Shape.NoFrame)
        contenu_defilement = QWidget()
        contenu_defilement.setObjectName("ScrollContent")
        self.layout_formulaire = QVBoxLayout(contenu_defilement)
        self.layout_formulaire.setContentsMargins(2, 2, 2, 2)
        self.layout_formulaire.setSpacing(15) 
        
        self.champs_saisie = {}
        self.consigne_fixee_C = 35.0
        
        definition_parametres = {
            "Contrôle Thermique": {"puissance_tec_W": 1.0},
            "Paramètres de la plaque": {"longueur_y_mm": 117.5, "largeur_x_mm": 61.5, "epaisseur_mm": 1.7},
            "Paramètres de la simulation": {"temps_total_s": 150.0, "resolution_grille": 50.0, "temperature_ambiante_C": 20.0, "intervalle_affichage": 1.0},
            "Paramètres physiques": {"diffusivite_alpha": 97.0, "masse_volumique_rho": 2.7e-3, "chaleur_massique_cp": 0.9, "coeff_convection_h": 3.2e-5},
            "Position TEC": {
                "pos_x_tec_mm": 0.0,
                "pos_y_tec_mm": 5.0,
            },
            "Capteur 1": {
                "pos_x_capteur_1_mm": 0.0,
                "pos_y_capteur_1_mm": 14.57,
            },
            "Capteur 2": {
                "pos_x_capteur_2_mm": 0.0,
                "pos_y_capteur_2_mm": 59.42,
            },
            "Capteur 3": {
                "pos_x_capteur_3_mm": 0.0,
                "pos_y_capteur_3_mm": 103.79,
            },
            "Perturbation (Résistance)": {
                "pos_x_resistance_mm": 0.0, "pos_y_resistance_mm": 38.0,
                "valeur_resistance_ohm": 25.0, "tension_resistance_V": 1.0,
                "facteur_couplage_perturbation": 0.85,
                "constante_temps_perturbation_s": 8.0
            }
        }

        libelles_parametres = {
            "puissance_tec_W": "Puissance TEC (W)",
            "longueur_y_mm": "Longueur Y (mm)",
            "largeur_x_mm": "Largeur X (mm)",
            "epaisseur_mm": "Épaisseur (mm)",
            "temps_total_s": "Temps total (s)",
            "resolution_grille": "Résolution grille",
            "temperature_ambiante_C": "Température ambiante (°C)",
            "intervalle_affichage": "Intervalle affichage",
            "diffusivite_alpha": "Diffusivité alpha",
            "masse_volumique_rho": "Masse volumique rho",
            "chaleur_massique_cp": "Chaleur massique cp",
            "coeff_convection_h": "Coeff. convection h",
            "pos_x_tec_mm": "Position X (mm)",
            "pos_y_tec_mm": "Position Y (mm)",
            "pos_x_capteur_1_mm": "Position X (mm)",
            "pos_y_capteur_1_mm": "Position Y (mm)",
            "pos_x_capteur_2_mm": "Position X (mm)",
            "pos_y_capteur_2_mm": "Position Y (mm)",
            "pos_x_capteur_3_mm": "Position X (mm)",
            "pos_y_capteur_3_mm": "Position Y (mm)",
            "pos_x_resistance_mm": "Position X (mm)",
            "pos_y_resistance_mm": "Position Y (mm)",
            "valeur_resistance_ohm": "Résistance (ohm)",
            "tension_resistance_V": "Tension résistance (V)",
            "facteur_couplage_perturbation": "Facteur couplage",
            "constante_temps_perturbation_s": "Constante temps (s)",
        }

        for nom_section, variables in definition_parametres.items():
            groupe = QGroupBox(nom_section)
            layout_groupe = QVBoxLayout(groupe)
            layout_groupe.setContentsMargins(12, 20, 12, 12)
            layout_groupe.setSpacing(16)
            
            for cle_variable, valeur_defaut in variables.items():
                layout_param = QVBoxLayout()
                layout_param.setSpacing(6)
                
                texte_label = libelles_parametres.get(cle_variable, cle_variable.replace("_", " ").title())
                label_param = QLabel(texte_label)
                
                plages = {
                    "puissance_tec_W": (-10, 10), "consigne_C": (-20, 100),
                    "longueur_y_mm": (50, 200), "largeur_x_mm": (30, 150),
                    "epaisseur_mm": (0.1, 5), 
                    "temps_total_s": (10, 1000), "resolution_grille": (10, 100),
                    "temperature_ambiante_C": (-20, 50), "intervalle_affichage": (1, 50),
                    "diffusivite_alpha": (50, 150), "masse_volumique_rho": (0.001, 0.01),
                    "chaleur_massique_cp": (0.5, 1.5), "coeff_convection_h": (0.00001, 0.0005),
                    "pos_x_tec_mm": (-50, 50), "pos_y_tec_mm": (0, 120),
                    "pos_x_capteur_1_mm": (-50, 50), "pos_y_capteur_1_mm": (0, 120),
                    "pos_x_capteur_2_mm": (-50, 50), "pos_y_capteur_2_mm": (0, 120),
                    "pos_x_capteur_3_mm": (-50, 50), "pos_y_capteur_3_mm": (0, 120),
                    "pos_x_resistance_mm": (-50, 50), "pos_y_resistance_mm": (0, 120),
                    "valeur_resistance_ohm": (1, 100), "tension_resistance_V": (0, 10),
                    "facteur_couplage_perturbation": (0, 2), "constante_temps_perturbation_s": (0, 60)
                }
                
                min_v, max_v = plages.get(cle_variable, (-1000, 1000))
                utiliser_scientifique = "e" in str(valeur_defaut).lower()
                decimales = 3 if utiliser_scientifique else (1 if cle_variable.endswith("_mm") or "capteur" in cle_variable or "tec" in cle_variable or "resistance" in cle_variable or "consigne" in cle_variable else 2)
                
                slider_widget = SliderWithValue(min_v, max_v, float(valeur_defaut), decimals=decimales, scientific=utiliser_scientifique)
                self.champs_saisie[cle_variable] = slider_widget
                
                layout_param.addWidget(label_param)
                layout_param.addWidget(slider_widget)
                layout_groupe.addLayout(layout_param)
            
            self.layout_formulaire.addWidget(groupe)

        self.layout_formulaire.addStretch()
        zone_defilement.setWidget(contenu_defilement)
        layout_gauche.addWidget(zone_defilement)

        # Connexion des sliders en direct
        self.champs_saisie["puissance_tec_W"].slider.valueChanged.connect(self.actualiser_controle_live)
        self.champs_saisie["tension_resistance_V"].slider.valueChanged.connect(self.actualiser_controle_live) # NOUVEAU: Écoute de la tension
        self.champs_saisie["puissance_tec_W"].value_input.editingFinished.connect(self.actualiser_controle_live)
        self.champs_saisie["tension_resistance_V"].value_input.editingFinished.connect(self.actualiser_controle_live)
        for champ in self.champs_saisie.values():
            champ.slider.valueChanged.connect(self.mettre_a_jour_indicateur_stabilite)
            champ.value_input.editingFinished.connect(self.mettre_a_jour_indicateur_stabilite)
        
        cadre_controles = QFrame()
        cadre_controles.setObjectName("ControlsFrame")
        layout_controles = QVBoxLayout(cadre_controles)
        layout_controles.setContentsMargins(12, 12, 12, 12)
        layout_controles.setSpacing(10)
        
        ligne_boutons_fichiers = QHBoxLayout()
        self.bouton_importer = QPushButton("Importer JSON")
        self.bouton_importer.clicked.connect(self.importer_parametres_json)
        self.bouton_sauvegarder_chemin = QPushButton("Sauver JSON")
        self.bouton_sauvegarder_chemin.clicked.connect(self.choisir_chemin_sauvegarde)
        ligne_boutons_fichiers.addWidget(self.bouton_importer)
        ligne_boutons_fichiers.addWidget(self.bouton_sauvegarder_chemin)

        ligne_boutons_simulation = QHBoxLayout()
        self.bouton_demarrer = QPushButton("DÉMARRER")
        self.bouton_demarrer.setObjectName("btn_go")
        self.bouton_demarrer.clicked.connect(self.lancer_simulation)
        
        self.bouton_pause = QPushButton("PAUSE")
        self.bouton_pause.setObjectName("btn_pause")
        self.bouton_pause.clicked.connect(self.basculer_pause)
        self.bouton_pause.setEnabled(False)

        self.bouton_arreter = QPushButton("ARRÊTER")
        self.bouton_arreter.setObjectName("btn_close")
        self.bouton_arreter.clicked.connect(self.stopper_simulation)
        self.bouton_arreter.setEnabled(False)
        
        ligne_boutons_simulation.addWidget(self.bouton_demarrer)
        ligne_boutons_simulation.addWidget(self.bouton_pause)
        ligne_boutons_simulation.addWidget(self.bouton_arreter)
        
        # --- NOUVEAU: Bouton QuickSave ---
        self.bouton_quicksave = QPushButton("QUICKSAVE (Pause requise)")
        self.bouton_quicksave.setObjectName("btn_quicksave")
        self.bouton_quicksave.clicked.connect(self.quicksave_instantane)
        self.bouton_quicksave.setEnabled(False)

        self.barre_progression = QProgressBar()
        self.barre_progression.setValue(0)
        self.barre_progression.setFormat("%p%")

        self.label_stabilite = QLabel()
        self.label_stabilite.setWordWrap(True)
        self.label_stabilite.setStyleSheet(
            "background-color: rgba(15, 23, 42, 0.75); border: 1px solid #334155; "
            "border-radius: 6px; padding: 8px; color: #CBD5E1;"
        )
        
        layout_controles.addLayout(ligne_boutons_fichiers)
        layout_controles.addLayout(ligne_boutons_simulation)
        layout_controles.addWidget(self.bouton_quicksave) # Ajout du QuickSave
        layout_controles.addWidget(self.barre_progression)
        layout_controles.addWidget(self.label_stabilite)
        layout_gauche.addWidget(cadre_controles)

        # === PANNEAU DROIT (Graphiques) ===
        panneau_droit = QWidget()
        panneau_droit.setObjectName("RightPanel")
        layout_droit = QVBoxLayout(panneau_droit)
        layout_droit.setContentsMargins(10, 10, 10, 10)
        layout_droit.setSpacing(10)
        separateur_graphiques = QSplitter(Qt.Orientation.Vertical)
        
        container_3d = QFrame()
        container_3d.setObjectName("ThreeDPanel")
        layout_3d_global = QVBoxLayout(container_3d)
        layout_3d_global.setContentsMargins(0, 0, 0, 0)
        layout_3d_global.setSpacing(0)

        layout_overlay = QHBoxLayout()
        layout_overlay.setContentsMargins(10, 8, 10, 0)
        layout_overlay.setSpacing(12)
        layout_overlay.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.boite_infos_3d = QWidget()
        layout_infos_3d = QVBoxLayout(self.boite_infos_3d)
        layout_infos_3d.setContentsMargins(0, 0, 0, 0)
        layout_infos_3d.setSpacing(8)

        self.label_ressources = QLabel("CPU app : --.- %\nRAM app : --.- MB")
        self.label_ressources.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.label_ressources.setStyleSheet("""
            QLabel {
                background-color: rgba(15, 23, 42, 0.82);
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 6px 10px;
                color: #7DD3FC;
                font-size: 11px;
                font-weight: 700;
            }
        """)
        layout_infos_3d.addWidget(self.label_ressources, alignment=Qt.AlignmentFlag.AlignLeft)
        layout_infos_3d.addStretch()

        layout_overlay.addWidget(self.boite_infos_3d, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        layout_overlay.addStretch(1)

        self.barre_controles_vue = QFrame()
        self.barre_controles_vue.setStyleSheet("""
            QFrame {
                background-color: rgba(15, 23, 42, 0.82);
                border: 1px solid #334155;
                border-radius: 8px;
            }
        """)
        layout_barre_controles_vue = QHBoxLayout(self.barre_controles_vue)
        layout_barre_controles_vue.setContentsMargins(8, 6, 8, 6)
        layout_barre_controles_vue.setSpacing(8)

        self.bouton_vue_2d = QPushButton("VUE 2D")
        self.bouton_vue_2d.setCheckable(True)
        self.bouton_vue_2d.setToolTip("Basculer en vue strictement 2D")
        self.bouton_vue_2d.setStyleSheet("""
            QPushButton {
                background-color: rgba(14, 165, 233, 0.92);
                color: white;
                border: 1px solid #0284C7;
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 11px;
                font-weight: bold;
                min-width: 70px;
            }
            QPushButton:hover { background-color: rgba(56, 189, 248, 0.98); }
            QPushButton:checked { background-color: rgba(16, 185, 129, 0.95); border: 1px solid #059669; }
        """)
        self.bouton_vue_2d.clicked.connect(self.basculer_vue_2d)
        layout_barre_controles_vue.addWidget(self.bouton_vue_2d)

        self.label_perspective = QLabel("Perspective")
        self.label_perspective.setStyleSheet("color: #7DD3FC; font-size: 11px; font-weight: bold; padding-left: 4px;")
        layout_barre_controles_vue.addWidget(self.label_perspective)

        self.slider_perspective = QSlider(Qt.Orientation.Horizontal)
        self.slider_perspective.setRange(5, 90)
        self.slider_perspective.setValue(int(self.perspective_fov))
        self.slider_perspective.setFixedWidth(130)
        self.slider_perspective.setToolTip("Ajuster la perspective de la vue 3D")
        self.slider_perspective.setStyleSheet("""
            QSlider::groove:horizontal { border: none; height: 4px; background: #475569; border-radius: 2px; }
            QSlider::sub-page:horizontal { background: #EAB308; border-radius: 2px; }
            QSlider::handle:horizontal { background: #FDE047; border: 1px solid #CA8A04; width: 12px; margin: -5px 0; border-radius: 6px; }
        """)
        self.slider_perspective.valueChanged.connect(self.mettre_a_jour_perspective_camera)
        layout_barre_controles_vue.addWidget(self.slider_perspective)

        self.barre_controles_vue.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        layout_overlay.addWidget(self.barre_controles_vue, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)

        self.bouton_fullscreen = QPushButton("⛶")
        self.bouton_fullscreen.setObjectName("btn_fullscreen")
        self.bouton_fullscreen.setToolTip("Passer en plein écran (F11)")
        self.bouton_fullscreen.clicked.connect(self.passer_en_plein_ecran)
        layout_overlay.addWidget(self.bouton_fullscreen, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)

        self.bouton_exit_fullscreen = QPushButton("✕")
        self.bouton_exit_fullscreen.setObjectName("btn_exit_fullscreen")
        self.bouton_exit_fullscreen.setToolTip("Quitter le plein écran (Échap)")
        self.bouton_exit_fullscreen.clicked.connect(self.quitter_plein_ecran)
        self.bouton_exit_fullscreen.hide()
        layout_overlay.addWidget(self.bouton_exit_fullscreen, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        layout_3d_global.addLayout(layout_overlay)

        layout_3d_h = QHBoxLayout()
        layout_3d_h.setContentsMargins(0, 0, 0, 0)

        self.vue_3d = StableGLViewWidget()
        self.vue_3d.setCameraPosition(
            distance=self.camera_distance_initiale,
            elevation=self.camera_elevation_initiale,
            azimuth=self.camera_azimuth_initiale,
        )
        self.vue_3d.setCameraParams(fov=self.perspective_fov)
        self.grille_3d = gl.GLGridItem()
        self.grille_3d.scale(10, 10, 10)
        self.vue_3d.addItem(self.grille_3d)

        self.axes_3d = gl.GLAxisItem()
        self.axes_3d.setSize(x=61.5, y=117.5, z=25.0)
        self.axes_3d.translate(-30.75, 0.0, 0.0)
        self.vue_3d.addItem(self.axes_3d)
        
        self.surface_thermique = gl.GLSurfacePlotItem(computeNormals=True, smooth=True, shader='shaded')
        test_data = np.ones((20, 20), dtype=np.float32) * 20.0
        test_x = np.linspace(0, 100, 20)
        test_y = np.linspace(0, 100, 20)
        test_norm = np.linspace(0, 1, 20)
        test_colors = np.zeros((20, 20, 4), dtype=np.float32)
        for i in range(20):
            ratio = i / 19.0
            test_colors[i, :] = self.palette_couleurs.map(ratio) / 255.0
        self.surface_thermique.setData(x=test_x, y=test_y, z=test_data, colors=test_colors)
        self.vue_3d.addItem(self.surface_thermique)

        self.scatter_capteurs = gl.GLScatterPlotItem(size=12, pxMode=True)
        self.vue_3d.addItem(self.scatter_capteurs)

        layout_3d_h.addWidget(self.vue_3d, stretch=1)

        container_legende = QWidget()
        container_legende.setFixedWidth(80) 
        layout_legende = QVBoxLayout(container_legende)
        layout_legende.setContentsMargins(5, 30, 15, 30)
        
        self.lbl_max_temp = QLabel("100.0 °C")
        self.lbl_max_temp.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom)
        
        self.barre_couleur = QFrame()
        self.barre_couleur.setFixedWidth(18)
        self.barre_couleur.setMinimumHeight(120) 
        self.barre_couleur.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.barre_couleur.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:1, x2:0, y2:0,
                            stop:0.0 #440154,
                            stop:0.25 #31688E,
                            stop:0.5 #C84696,
                            stop:0.75 #FF6464,
                            stop:1.0 #FF0000);
                border: 1px solid #0EA5E9;
                border-radius: 3px;
            }
        """)
        
        self.lbl_min_temp = QLabel("20.0 °C")
        self.lbl_min_temp.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        
        layout_legende.addWidget(self.lbl_max_temp)
        layout_legende.addWidget(self.barre_couleur, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout_legende.addWidget(self.lbl_min_temp)
        
        layout_3d_h.addWidget(container_legende)
        layout_3d_global.addLayout(layout_3d_h, stretch=1)

        pg.setConfigOptions(antialias=True, background='#0F172A', foreground='#E2E8F0')
        container_2d = QFrame()
        container_2d.setObjectName("PlotPanel")
        layout_plot = QVBoxLayout(container_2d)
        layout_plot.setContentsMargins(8, 8, 8, 8)

        self.graphique_2d = pg.PlotWidget(title="En Attente de Lancement...")
        self.graphique_2d.addLegend()
        self.graphique_2d.showGrid(x=True, y=True, alpha=0.3)
        self.graphique_2d.setLabel('left', 'Température', units='°C')
        self.graphique_2d.setLabel('bottom', 'Temps', units='s')
        
        self.courbe_t1 = self.graphique_2d.plot(pen=pg.mkPen('#3B82F6', width=3), name='T1 (Bleu)')
        self.courbe_t2 = self.graphique_2d.plot(pen=pg.mkPen('#F59E0B', width=3), name='T2 (Orange)')
        self.courbe_t3 = self.graphique_2d.plot(pen=pg.mkPen('#10B981', width=3), name='T3 (Vert)')
        
        self.curseur_temps_2d = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen('#EF4444', width=2, style=Qt.PenStyle.DashLine))
        self.graphique_2d.addItem(self.curseur_temps_2d)
        self.curseur_temps_2d.hide()

        self.donnees_temps, self.donnees_y_t1, self.donnees_y_t2, self.donnees_y_t3 = [], [], [], []

        layout_plot.addWidget(self.graphique_2d)
        separateur_graphiques.addWidget(container_3d)
        separateur_graphiques.addWidget(container_2d)
        separateur_graphiques.setSizes([600, 350])
        layout_droit.addWidget(separateur_graphiques)

        layout_timeline = QHBoxLayout()
        layout_timeline.setContentsMargins(15, 10, 15, 15)
        
        label_timeline = QLabel("Historique Temporel :")
        label_timeline.setStyleSheet("font-weight: bold; color: #38BDF8; font-size: 14px;")
        
        self.btn_play_pause = QPushButton("▶")
        self.btn_play_pause.setMaximumWidth(40)
        self.btn_play_pause.setEnabled(False)
        self.btn_play_pause.setStyleSheet("""
            QPushButton { background-color: #0EA5E9; color: white; border: none; border-radius: 4px; font-weight: bold; padding: 5px 10px; }
            QPushButton:hover { background-color: #38BDF8; }
            QPushButton:pressed { background-color: #06B6D4; }
            QPushButton:disabled { background-color: #334155; }
        """)
        self.btn_play_pause.clicked.connect(self.toggle_lecture_temps)
        self.lecture_en_cours = False
        
        self.slider_timeline = QSlider(Qt.Orientation.Horizontal)
        self.slider_timeline.setEnabled(False)
        self.slider_timeline.valueChanged.connect(self.naviguer_dans_historique)
        
        self.combo_vitesse = QComboBox()
        self.combo_vitesse.setMaximumWidth(80)
        self.combo_vitesse.addItems(["0.5x", "1.0x", "2.0x", "5x"])
        self.combo_vitesse.setCurrentIndex(1)
        self.combo_vitesse.setEnabled(False)
        self.combo_vitesse.setStyleSheet("""
            QComboBox { background-color: #1E293B; color: #38BDF8; border: 1px solid #334155; border-radius: 4px; padding: 4px 8px; }
            QComboBox:disabled { color: #64748B; }
            QComboBox::drop-down { border: none; }
            QComboBox::down-arrow { image: none; }
        """)
        self.vitesse_lecture = 1.0
        self.combo_vitesse.currentTextChanged.connect(self.modifier_vitesse_lecture)
        
        label_vitesse = QLabel("Vitesse:")
        label_vitesse.setStyleSheet("color: #94A3B8; font-size: 12px;")
        
        layout_timeline.addWidget(label_timeline)
        layout_timeline.addWidget(self.btn_play_pause)
        layout_timeline.addWidget(self.slider_timeline, 1)
        layout_timeline.addWidget(label_vitesse)
        layout_timeline.addWidget(self.combo_vitesse)
        layout_droit.addLayout(layout_timeline)
        
        separateur_principal.addWidget(panneau_gauche)
        separateur_principal.addWidget(panneau_droit)
        separateur_principal.setSizes([380, 1120])
        self.mettre_a_jour_indicateur_stabilite()
        self.mettre_a_jour_axes_3d_stables()
        self.mettre_a_jour_legende_axes_3d()

        self.timer_ressources = QTimer(self)
        self.timer_ressources.timeout.connect(self.mettre_a_jour_ressources_systeme)
        self.timer_ressources.start(1000)
        self.mettre_a_jour_ressources_systeme()

    def recuperer_parametres_interface(self):
        params = {cle: champ.value() for cle, champ in self.champs_saisie.items()}
        params["consigne_C"] = self.consigne_fixee_C
        return params

    def obtenir_ram_processus_mo(self):
        try:
            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            get_process_memory_info = ctypes.windll.psapi.GetProcessMemoryInfo
            get_process_memory_info.argtypes = [
                wintypes.HANDLE,
                ctypes.POINTER(PROCESS_MEMORY_COUNTERS),
                wintypes.DWORD,
            ]
            get_process_memory_info.restype = wintypes.BOOL

            compteurs = PROCESS_MEMORY_COUNTERS()
            compteurs.cb = ctypes.sizeof(compteurs)
            handle = ctypes.windll.kernel32.GetCurrentProcess()
            succes = get_process_memory_info(handle, ctypes.byref(compteurs), compteurs.cb)
            if succes:
                return compteurs.WorkingSetSize / (1024 ** 2)
        except Exception:
            pass
        return 0.0

    def mettre_a_jour_ressources_systeme(self):
        maintenant = time.perf_counter()
        temps_cpu = time.process_time()

        delta_temps = max(maintenant - self._horodatage_cpu_precedent, 1e-9)
        delta_cpu = max(temps_cpu - self._temps_cpu_precedent, 0.0)
        cpu_percent = 100.0 * delta_cpu / delta_temps
        ram_mo = self.obtenir_ram_processus_mo()

        self._horodatage_cpu_precedent = maintenant
        self._temps_cpu_precedent = temps_cpu

        if hasattr(self, "label_ressources"):
            self.label_ressources.setText(
                f"CPU app : {cpu_percent:5.1f} %\nRAM app : {ram_mo:6.1f} MB"
            )

        return cpu_percent, ram_mo

    def _supprimer_annotations_axes_3d(self):
        if not isinstance(self.annotations_axes_3d, dict):
            self.annotations_axes_3d = {}
            return

        for item in self.annotations_axes_3d.values():
            try:
                if hasattr(self, "vue_3d"):
                    self.vue_3d.removeItem(item)
            except Exception:
                pass
        self.annotations_axes_3d = {}

    def _definir_texte_axe_3d(self, cle, position, texte, couleur=(226, 232, 240, 255), taille=8, gras=False, visible=True):
        if not hasattr(self, "vue_3d") or not hasattr(gl, "GLTextItem"):
            return

        if not isinstance(self.annotations_axes_3d, dict):
            self.annotations_axes_3d = {}

        pos = np.array(position, dtype=float)
        color = pg.mkColor(couleur)
        texte = str(texte)
        police = QFont("Segoe UI", taille)
        police.setBold(gras)

        item = self.annotations_axes_3d.get(cle)
        try:
            if item is None:
                item = gl.GLTextItem(pos=pos, color=color, text=texte, font=police)
                self.vue_3d.addItem(item)
                self.annotations_axes_3d[cle] = item
            else:
                item.setData(pos=pos, color=color, text=texte, font=police)
            if hasattr(item, "setVisible"):
                item.setVisible(bool(visible))
        except Exception:
            pass

    def _definir_trait_axe_3d(self, cle, points, couleur=(148, 163, 184, 220), largeur=2.0, visible=True):
        if not hasattr(self, "vue_3d") or not hasattr(gl, "GLLinePlotItem"):
            return

        if not isinstance(self.annotations_axes_3d, dict):
            self.annotations_axes_3d = {}

        pos = np.array(points, dtype=np.float32)
        rgba = np.array(pg.mkColor(couleur).getRgbF(), dtype=np.float32)
        couleurs = np.tile(rgba, (len(pos), 1))

        item = self.annotations_axes_3d.get(cle)
        try:
            if item is None:
                item = gl.GLLinePlotItem(pos=pos, color=couleurs, width=largeur, antialias=True, mode='line_strip')
                self.vue_3d.addItem(item)
                self.annotations_axes_3d[cle] = item
            else:
                item.setData(pos=pos, color=couleurs, width=largeur, antialias=True, mode='line_strip')
            if hasattr(item, "setVisible"):
                item.setVisible(bool(visible))
        except Exception:
            pass

    def mettre_a_jour_axes_3d_stables(self, params_source=None, temp_min=None, temp_max=None):
        try:
            if params_source is None:
                params_source = self.params_actuels if self.params_actuels else self.recuperer_parametres_interface()

            largeur = max(10.0, float(params_source["largeur_x_mm"]))
            longueur = max(10.0, float(params_source["longueur_y_mm"]))
            temp_min_ref, temp_max_ref = calculer_bornes_temperature_fixes(params_source)
            temp_min_aff = temp_min_ref if temp_min is None else float(temp_min)
            temp_max_aff = temp_max_ref if temp_max is None else float(temp_max)
            if temp_max_aff <= temp_min_aff:
                temp_max_aff = temp_min_aff + 1.0
            hauteur_axes = max(20.0, (temp_max_aff - temp_min_aff) * self.exageration_z)
            origine_x = -largeur / 2.0
            origine_y = 0.0

            if hasattr(self, "grille_3d"):
                self.grille_3d.resetTransform()
                self.grille_3d.setSize(x=largeur, y=longueur)
                self.grille_3d.setSpacing(x=max(5.0, largeur / 6.0), y=max(10.0, longueur / 6.0))
                self.grille_3d.translate(0.0, longueur / 2.0, 0.0)

            if hasattr(self, "axes_3d"):
                self.axes_3d.resetTransform()
                self.axes_3d.setSize(x=largeur, y=longueur, z=0.0 if self.vue_2d_active else hauteur_axes)
                self.axes_3d.translate(origine_x, origine_y, 0.0)

            longueur_marque_x = max(2.0, largeur * 0.025)
            longueur_marque_y = max(2.0, longueur * 0.025)
            for index, ratio in enumerate(np.linspace(0.0, 1.0, 5)):
                pos_x = origine_x + (ratio * largeur)
                pos_y = ratio * longueur
                pos_z = ratio * hauteur_axes

                self._definir_trait_axe_3d(
                    f"trait_x_{index}",
                    [(pos_x, 0.0, 0.0), (pos_x, longueur_marque_y, 0.0)],
                    couleur=(125, 211, 252, 220),
                    largeur=2.0,
                    visible=True,
                )
                self._definir_trait_axe_3d(
                    f"trait_y_{index}",
                    [(origine_x, pos_y, 0.0), (origine_x + longueur_marque_x, pos_y, 0.0)],
                    couleur=(125, 211, 252, 220),
                    largeur=2.0,
                    visible=True,
                )
                self._definir_trait_axe_3d(
                    f"trait_z_{index}",
                    [(origine_x, 0.0, pos_z), (origine_x + longueur_marque_x, 0.0, pos_z)],
                    couleur=(253, 230, 138, 220),
                    largeur=2.0,
                    visible=not self.vue_2d_active,
                )
        except Exception:
            pass

    def mettre_a_jour_legende_axes_3d(self, params_source=None, temp_min=None, temp_max=None):
        try:
            if params_source is None:
                params_source = self.params_actuels if self.params_actuels else self.recuperer_parametres_interface()

            largeur = float(params_source["largeur_x_mm"])
            longueur = float(params_source["longueur_y_mm"])
            demi_largeur = largeur / 2.0

            temp_min_fixe, temp_max_fixe = calculer_bornes_temperature_fixes(params_source)
            temp_min_aff = temp_min_fixe if temp_min is None else float(temp_min)
            temp_max_aff = temp_max_fixe if temp_max is None else float(temp_max)
            if temp_max_aff <= temp_min_aff:
                temp_max_aff = temp_min_aff + 1.0
            temp_milieu = 0.5 * (temp_min_aff + temp_max_aff)
            hauteur_axes = max(20.0, (temp_max_aff - temp_min_aff) * self.exageration_z)
            decalage_x = max(2.5, largeur * 0.04)
            decalage_y = max(2.5, longueur * 0.04)
            decalage_z = max(1.0, hauteur_axes * 0.05)

            # Graduations directement placées sur les axes 3D.
            graduations_x = [
                ("x_min", -demi_largeur, f"{-demi_largeur:.0f}"),
                ("x_q1", -demi_largeur / 2.0, f"{-demi_largeur / 2.0:.0f}"),
                ("x_mid", 0.0, "0"),
                ("x_q3", demi_largeur / 2.0, f"{demi_largeur / 2.0:.0f}"),
                ("x_max", demi_largeur, f"{demi_largeur:.0f}"),
            ]
            for cle, pos_x, texte in graduations_x:
                self._definir_texte_axe_3d(cle, (pos_x, decalage_y, 0.0), texte, taille=8)
            self._definir_texte_axe_3d("x_label", (demi_largeur + decalage_x, decalage_y, 0.0), "X (mm)", (125, 211, 252, 255), taille=10, gras=True)

            graduations_y = [
                ("y_min", 0.0, "0"),
                ("y_q1", longueur * 0.25, f"{longueur * 0.25:.0f}"),
                ("y_mid", longueur * 0.5, f"{longueur * 0.5:.0f}"),
                ("y_q3", longueur * 0.75, f"{longueur * 0.75:.0f}"),
                ("y_max", longueur, f"{longueur:.0f}"),
            ]
            for cle, pos_y, texte in graduations_y:
                self._definir_texte_axe_3d(cle, (-demi_largeur + decalage_x, pos_y, 0.0), texte, taille=8)
            self._definir_texte_axe_3d("y_label", (-demi_largeur + decalage_x, longueur + decalage_y, 0.0), "Y (mm)", (125, 211, 252, 255), taille=10, gras=True)

            graduations_z = [
                ("z_min", 0.0, f"{temp_min_aff:.1f} °C"),
                ("z_q1", hauteur_axes * 0.25, f"{temp_min_aff + 0.25 * (temp_max_aff - temp_min_aff):.1f} °C"),
                ("z_mid", hauteur_axes * 0.5, f"{temp_milieu:.1f} °C"),
                ("z_q3", hauteur_axes * 0.75, f"{temp_min_aff + 0.75 * (temp_max_aff - temp_min_aff):.1f} °C"),
                ("z_max", hauteur_axes, f"{temp_max_aff:.1f} °C"),
            ]
            for cle, pos_z, texte in graduations_z:
                self._definir_texte_axe_3d(cle, (-demi_largeur + decalage_x, decalage_y, pos_z), texte, taille=8, visible=not self.vue_2d_active)
            self._definir_texte_axe_3d("z_label", (-demi_largeur + decalage_x, decalage_y, hauteur_axes + decalage_z), "Z (°C)", (253, 230, 138, 255), taille=10, gras=True, visible=not self.vue_2d_active)
        except Exception:
            pass

    def mettre_a_jour_indicateur_stabilite(self):
        try:
            params = self.valider_parametres(self.recuperer_parametres_interface())
            infos = calculer_facteur_stabilite_numerique(params)
            facteur = infos["facteur"]
            est_stable = facteur < 0.5
            couleur = "#10B981" if est_stable else "#EF4444"
            etat = "Stable" if est_stable else "Instable"

            self.label_stabilite.setText(
                f"Stabilité numérique : {etat} | facteur = {facteur:.6f}\n"
                f"Δt = {infos['pas_temps_s']:.5f} s | Δx = {infos['pas_x_mm']:.3f} mm | Δy = {infos['pas_y_mm']:.3f} mm"
            )
            self.label_stabilite.setStyleSheet(
                f"background-color: rgba(15, 23, 42, 0.75); border: 1px solid {couleur}; "
                f"border-radius: 6px; padding: 8px; color: {couleur}; font-weight: 600;"
            )
            self.mettre_a_jour_axes_3d_stables(params)
            self.mettre_a_jour_legende_axes_3d(params)
            if hasattr(self, 'bouton_demarrer') and not self.simulation_en_cours():
                self.bouton_demarrer.setEnabled(est_stable)
        except Exception as erreur:
            self.label_stabilite.setText(f"Stabilité numérique : impossible à évaluer ({erreur})")
            self.label_stabilite.setStyleSheet(
                "background-color: rgba(15, 23, 42, 0.75); border: 1px solid #F59E0B; "
                "border-radius: 6px; padding: 8px; color: #FBBF24; font-weight: 600;"
            )
            if hasattr(self, 'bouton_demarrer') and not self.simulation_en_cours():
                self.bouton_demarrer.setEnabled(True)

    def changer_mode_systeme(self, index):
        return

    def synchroniser_boutons_mode(self, index):
        return

    def valider_parametres(self, params):
        params_valides = {}
        for cle in self.champs_saisie:
            if cle not in params:
                raise ValueError(f"Paramètre manquant : {cle}")
            try:
                params_valides[cle] = float(params[cle])
            except (TypeError, ValueError) as erreur:
                raise ValueError(f"Valeur invalide pour '{cle}' : {params[cle]}") from erreur

        params_valides["resolution_grille"] = int(round(params_valides["resolution_grille"]))
        params_valides["intervalle_affichage"] = max(1, int(round(params_valides["intervalle_affichage"])))
        params_valides["consigne_C"] = float(params.get("consigne_C", self.consigne_fixee_C))

        if params_valides["resolution_grille"] < 2:
            raise ValueError("La résolution de grille doit être supérieure ou égale à 2.")
        if params_valides["largeur_x_mm"] <= 0 or params_valides["longueur_y_mm"] <= 0 or params_valides["epaisseur_mm"] <= 0:
            raise ValueError("Les dimensions de la plaque doivent être strictement positives.")
        if params_valides["temps_total_s"] <= 0:
            raise ValueError("Le temps total doit être strictement positif.")
        if params_valides["diffusivite_alpha"] <= 0 or params_valides["masse_volumique_rho"] <= 0 or params_valides["chaleur_massique_cp"] <= 0:
            raise ValueError("Les paramètres physiques alpha, rho et cp doivent être strictement positifs.")
        if params_valides["coeff_convection_h"] < 0:
            raise ValueError("Le coefficient de convection ne peut pas être négatif.")
        if params_valides["valeur_resistance_ohm"] <= 0:
            raise ValueError("La valeur de la résistance doit être strictement positive.")
        if params_valides["facteur_couplage_perturbation"] < 0:
            raise ValueError("Le facteur de couplage de la perturbation doit être positif ou nul.")
        if params_valides["constante_temps_perturbation_s"] < 0:
            raise ValueError("La constante de temps de la perturbation doit être positive ou nulle.")

        demi_largeur = params_valides["largeur_x_mm"] / 2.0
        positions_x = {
            "TEC": params_valides["pos_x_tec_mm"],
            "Capteur 1": params_valides["pos_x_capteur_1_mm"],
            "Capteur 2": params_valides["pos_x_capteur_2_mm"],
            "Capteur 3": params_valides["pos_x_capteur_3_mm"],
            "Résistance": params_valides["pos_x_resistance_mm"],
        }
        positions_y = {
            "TEC": params_valides["pos_y_tec_mm"],
            "Capteur 1": params_valides["pos_y_capteur_1_mm"],
            "Capteur 2": params_valides["pos_y_capteur_2_mm"],
            "Capteur 3": params_valides["pos_y_capteur_3_mm"],
            "Résistance": params_valides["pos_y_resistance_mm"],
        }

        positions_x_invalides = [nom for nom, valeur in positions_x.items() if abs(valeur) > demi_largeur]
        positions_y_invalides = [nom for nom, valeur in positions_y.items() if valeur < 0 or valeur > params_valides["longueur_y_mm"]]

        if positions_x_invalides:
            raise ValueError("Positions X hors plaque : " + ", ".join(positions_x_invalides))
        if positions_y_invalides:
            raise ValueError("Positions Y hors plaque : " + ", ".join(positions_y_invalides))

        return params_valides

    def importer_parametres_json(self):
        chemin_fichier, _ = QFileDialog.getOpenFileName(self, "Importer Paramètres", "", "Fichiers JSON (*.json)")
        if chemin_fichier:
            try:
                with open(chemin_fichier, 'r', encoding='utf-8') as fichier:
                    donnees = json.load(fichier)

                parametres = donnees.get("parametres", donnees)
                if not isinstance(parametres, dict):
                    raise ValueError("Le JSON doit contenir un objet de paramètres valide.")

                nb_parametres_importes = 0
                champs_invalides = []
                for cle, valeur in parametres.items():
                    if cle == "consigne_C":
                        try:
                            self.consigne_fixee_C = float(valeur)
                            nb_parametres_importes += 1
                        except (TypeError, ValueError):
                            champs_invalides.append(cle)
                    elif cle in self.champs_saisie:
                        try:
                            self.champs_saisie[cle].setValue(float(valeur))
                            nb_parametres_importes += 1
                        except (TypeError, ValueError):
                            champs_invalides.append(cle)

                if nb_parametres_importes == 0:
                    raise ValueError("Aucun paramètre reconnu n'a été trouvé dans le fichier.")

                self.actualiser_controle_live()

                if champs_invalides:
                    QMessageBox.warning(
                        self,
                        "Import partiel",
                        "Certaines valeurs ont été ignorées : " + ", ".join(champs_invalides)
                    )
            except (OSError, json.JSONDecodeError, ValueError) as erreur:
                QMessageBox.critical(self, "Erreur", f"Impossible de lire le fichier : {erreur}")

    def choisir_chemin_sauvegarde(self):
        chemin_fichier, _ = QFileDialog.getSaveFileName(self, "Choisir où sauvegarder les résultats", "", "Fichiers JSON (*.json);;Tous les fichiers (*.*)", options=QFileDialog.Option.DontUseNativeDialog)
        if chemin_fichier:
            if not chemin_fichier.endswith(".json"):
                chemin_fichier += ".json"
            self.chemin_sauvegarde = chemin_fichier

    def simulation_en_cours(self):
        return self.thread_simulation is not None and self.thread_simulation.isRunning()

    def lancer_simulation(self):
        if self.simulation_en_cours():
            QMessageBox.information(self, "Simulation en cours", "Une simulation est déjà en cours d'exécution.")
            return

        try:
            params = self.valider_parametres(self.recuperer_parametres_interface())
        except ValueError as erreur:
            QMessageBox.critical(self, "Paramètres invalides", str(erreur))
            return

        infos_stabilite = calculer_facteur_stabilite_numerique(params)
        if infos_stabilite["facteur"] >= 0.5:
            message = (
                f"Erreur : Le facteur de stabilité est de {infos_stabilite['facteur']:.6f}. "
                "Il doit être strictement inférieur à 0.5 pour éviter que la simulation diverge."
            )
            QMessageBox.critical(self, "Simulation instable", message)
            self.mettre_a_jour_indicateur_stabilite()
            return

        self.params_actuels = params
        self.export_apres_arret = False
        
        resolution = int(params["resolution_grille"])
        self.nx = resolution + 1  
        self.ny = resolution + 1  
        
        self.grille_x = np.linspace(-params["largeur_x_mm"]/2, params["largeur_x_mm"]/2, self.nx)
        self.grille_y = np.linspace(0, params["longueur_y_mm"], self.ny)
        self.pas_x = params["largeur_x_mm"] / (self.nx - 1)
        self.pas_y = params["longueur_y_mm"] / (self.ny - 1)

        self.donnees_temps.clear()
        self.donnees_y_t1.clear()
        self.donnees_y_t2.clear()
        self.donnees_y_t3.clear()
        self.historique_matrices_3D.clear()
        self.mode_direct_actif = True
        
        self.temperature_ambiante_ref, self.temperature_max_globale = calculer_bornes_temperature_fixes(params)
        
        self.lbl_min_temp.setText(f"{self.temperature_ambiante_ref:.1f} °C")
        self.lbl_max_temp.setText(f"{self.temperature_max_globale:.1f} °C")
        
        self.courbe_t1.setData([], [])
        self.courbe_t2.setData([], [])
        self.courbe_t3.setData([], [])
        self.barre_progression.setValue(0)
        self.curseur_temps_2d.hide()

        self.slider_timeline.blockSignals(True)
        self.slider_timeline.setRange(0, 0)
        self.slider_timeline.setEnabled(False)
        self.slider_timeline.blockSignals(False)
        
        self.btn_play_pause.setEnabled(False)
        self.btn_play_pause.setText("▶")
        self.combo_vitesse.setEnabled(False)
        self.lecture_en_cours = False
        
        # Reset des boutons UI
        self.bouton_demarrer.setEnabled(False)
        self.bouton_pause.setEnabled(True)
        self.bouton_pause.setText("PAUSE")
        self.bouton_pause.setStyleSheet("")
        self.bouton_arreter.setEnabled(True)
        self.bouton_quicksave.setEnabled(False)
        self.bouton_quicksave.setText("QUICKSAVE (Pause requise)")

        self.surface_thermique.resetTransform()

        centre_physique_y = params["longueur_y_mm"] / 2.0
        self.camera_centre_z = 0.0
        self.camera_distance_actuelle = max(
            self.camera_distance_initiale,
            max(params["largeur_x_mm"], params["longueur_y_mm"]) * 1.35,
        )
        self.appliquer_mode_camera()
        self.mettre_a_jour_axes_3d_stables(params)
        self.mettre_a_jour_legende_axes_3d(params, params["temperature_ambiante_C"], self.temperature_max_globale)

        matrice_initiale = np.full((self.ny, self.nx), params["temperature_ambiante_C"], dtype=np.float32)
        self.dessiner_rendu_3d(matrice_initiale, 0.0, params["temperature_ambiante_C"], params["temperature_ambiante_C"], params["temperature_ambiante_C"])

        mode_pid = False

        self.thread_simulation = SimulationThread(params, mode_pid)
        self.thread_simulation.update_signal.connect(self.actualiser_graphiques)
        self.thread_simulation.progress_signal.connect(self.barre_progression.setValue)
        self.thread_simulation.finished_signal.connect(self.terminer_simulation)
        self.thread_simulation.error_signal.connect(self.gerer_erreur_simulation)
        self.thread_simulation.finished.connect(self.nettoyer_apres_simulation)
        self.thread_simulation.start()

    # --- NOUVEAU: Mettre la simulation en pause/reprise ---
    def basculer_pause(self):
        if self.simulation_en_cours():
            est_en_pause = self.thread_simulation.toggle_pause()
            if est_en_pause:
                self.bouton_pause.setText("REPRENDRE")
                self.bouton_pause.setStyleSheet("background-color: #10B981; border: 1px solid #059669;") # Devient vert
                self.bouton_quicksave.setEnabled(True)
                self.bouton_quicksave.setText("QUICKSAVE ICI")
            else:
                self.bouton_pause.setText("PAUSE")
                self.bouton_pause.setStyleSheet("") # Retour au jaune
                self.bouton_quicksave.setEnabled(False)
                self.bouton_quicksave.setText("QUICKSAVE (Pause requise)")

    # --- NOUVEAU: Sauvegarder instantanément l'état en cours ---
    def quicksave_instantane(self):
        if not self.params_actuels or not self.donnees_temps:
            QMessageBox.warning(self, "QuickSave impossible", "Aucune donnée de simulation n'est disponible pour l'instant.")
            return

        resultats_actuels = {
            "temps": self.donnees_temps,
            "T1": self.donnees_y_t1,
            "T2": self.donnees_y_t2,
            "T3": self.donnees_y_t3
        }
        contenu_export = {"parametres": self.params_actuels, "resultats": resultats_actuels}

        chemin_fichier, _ = QFileDialog.getSaveFileName(self, "QuickSave : Sauvegarder les résultats", "quicksave.json", "Fichiers JSON (*.json);;Tous les fichiers (*.*)", options=QFileDialog.Option.DontUseNativeDialog)
        if chemin_fichier:
            try:
                if not chemin_fichier.endswith(".json"):
                    chemin_fichier += ".json"
                with open(chemin_fichier, "w", encoding="utf-8") as fichier:
                    json.dump(contenu_export, fichier, indent=4, default=lambda x: x.item() if isinstance(x, np.generic) else x)
                QMessageBox.information(self, "Succès", f"QuickSave effectué !\nFichier : {chemin_fichier}")
            except (OSError, TypeError, ValueError) as erreur:
                QMessageBox.critical(self, "Erreur de sauvegarde", f"Le QuickSave a échoué : {erreur}")

    def stopper_simulation(self):
        if self.simulation_en_cours():
            self.export_apres_arret = True
            self.thread_simulation.stop()
            self.bouton_pause.setEnabled(False)
            self.bouton_quicksave.setEnabled(False)
            
    def actualiser_controle_live(self):
        self.mettre_a_jour_indicateur_stabilite()
        if self.simulation_en_cours():
            mode_pid = False
            puiss = self.champs_saisie["puissance_tec_W"].value()
            cons = self.consigne_fixee_C
            tens = self.champs_saisie["tension_resistance_V"].value()
            self.thread_simulation.modifier_parametres_controle(mode_pid, puiss, cons, tens)

    def actualiser_graphiques(self, temps_sim, matrice_temperatures_3d, temp_T1, temp_T2, temp_T3):
        self.donnees_temps.append(temps_sim)
        self.donnees_y_t1.append(temp_T1)
        self.donnees_y_t2.append(temp_T2)
        self.donnees_y_t3.append(temp_T3)
        self.historique_matrices_3D.append(matrice_temperatures_3d)

        self.courbe_t1.setData(self.donnees_temps, self.donnees_y_t1)
        self.courbe_t2.setData(self.donnees_temps, self.donnees_y_t2)
        self.courbe_t3.setData(self.donnees_temps, self.donnees_y_t3)

        self.slider_timeline.setEnabled(True)
        self.btn_play_pause.setEnabled(True)
        self.combo_vitesse.setEnabled(True)
        self.slider_timeline.blockSignals(True)
        index_maximum = len(self.historique_matrices_3D) - 1
        self.slider_timeline.setMaximum(index_maximum)
        
        if self.mode_direct_actif:
            self.slider_timeline.setValue(index_maximum)
            self.dessiner_rendu_3d(matrice_temperatures_3d, temps_sim, temp_T1, temp_T2, temp_T3)
            self.curseur_temps_2d.hide()
            
        self.slider_timeline.blockSignals(False)

    def naviguer_dans_historique(self, index):
        if not self.historique_matrices_3D: return
        
        index_maximum = len(self.historique_matrices_3D) - 1
        self.mode_direct_actif = (index == index_maximum)
        
        matrice_historique = self.historique_matrices_3D[index]
        t1 = self.donnees_y_t1[index]
        t2 = self.donnees_y_t2[index]
        t3 = self.donnees_y_t3[index]
        temps_a_ce_moment = self.donnees_temps[index]
        
        self.curseur_temps_2d.setPos(temps_a_ce_moment)
        
        if self.mode_direct_actif:
            self.curseur_temps_2d.hide()
        else:
            self.curseur_temps_2d.show()
        
        self.dessiner_rendu_3d(matrice_historique, temps_a_ce_moment, t1, t2, t3)
    
    def toggle_lecture_temps(self):
        self.lecture_en_cours = not self.lecture_en_cours
        if self.lecture_en_cours:
            self.btn_play_pause.setText("⏸")
            self.lecture_temporelle()
        else:
            self.btn_play_pause.setText("▶")
    
    def lecture_temporelle(self):
        if not self.lecture_en_cours or not self.historique_matrices_3D:
            self.btn_play_pause.setText("▶")
            return
        
        index_courant = self.slider_timeline.value()
        index_max = self.slider_timeline.maximum()
        
        if index_courant < index_max:
            self.slider_timeline.setValue(index_courant + 1)
        else:
            self.slider_timeline.setValue(0)
        
        delai = int(100 / self.vitesse_lecture)
        QTimer.singleShot(delai, self.lecture_temporelle)
    
    def modifier_vitesse_lecture(self, text):
        vitesses = {"0.5x": 0.5, "1.0x": 1.0, "2.0x": 2.0, "5x": 5.0}
        self.vitesse_lecture = vitesses.get(text, 1.0)

    def calculer_distance_camera_compensee(self, distance_base=None, fov=None):
        distance_base = self.camera_distance_actuelle if distance_base is None else float(distance_base)
        fov_utilise = self.perspective_fov if fov is None else float(fov)
        fov_utilise = max(5.0, fov_utilise)
        fov_reference = max(5.0, float(getattr(self, "perspective_fov_reference", 45.0)))

        numerateur = np.tan(np.radians(fov_reference / 2.0))
        denominateur = max(np.tan(np.radians(fov_utilise / 2.0)), 1e-3)
        return distance_base * (numerateur / denominateur)

    def convertir_distance_vue_vers_base(self, distance_vue, fov=None):
        distance_vue = float(distance_vue)
        fov_utilise = self.perspective_fov if fov is None else float(fov)
        fov_utilise = max(5.0, fov_utilise)
        fov_reference = max(5.0, float(getattr(self, "perspective_fov_reference", 45.0)))

        numerateur = np.tan(np.radians(fov_utilise / 2.0))
        denominateur = max(np.tan(np.radians(fov_reference / 2.0)), 1e-3)
        return distance_vue * (numerateur / denominateur)

    def appliquer_mode_camera(self):
        if not hasattr(self, "vue_3d"):
            return

        params_source = self.params_actuels if self.params_actuels else self.recuperer_parametres_interface()
        centre_y = float(params_source["longueur_y_mm"]) / 2.0
        longueur_ref = max(float(params_source["largeur_x_mm"]), float(params_source["longueur_y_mm"]))

        if self.vue_2d_active:
            fov = 1.0
            distance = max(longueur_ref * 1.28 / max(np.tan(np.radians(fov / 2.0)), 1e-3), longueur_ref * 4.2)
            self.camera_centre_z = 0.0
            if hasattr(self.vue_3d, "lock_2d_interaction"):
                self.vue_3d.lock_2d_interaction = True
            self.slider_perspective.setEnabled(False)
            self.vue_3d.setCameraParams(
                center=pg.Vector(0, centre_y, 0.0),
                distance=distance,
                elevation=89.9,
                azimuth=0.0,
                fov=fov,
            )
        else:
            if hasattr(self.vue_3d, "lock_2d_interaction"):
                self.vue_3d.lock_2d_interaction = False
            self.slider_perspective.setEnabled(True)

            fov_3d = max(5.0, self.perspective_fov)
            azimuth_courant = float(self.vue_3d.opts.get("azimuth", self.camera_azimuth_initiale))
            elevation_courante = float(self.vue_3d.opts.get("elevation", self.camera_elevation_initiale))
            distance_vue_courante = float(self.vue_3d.opts.get("distance", self.calculer_distance_camera_compensee()))
            centre_courant = self.vue_3d.opts.get("center", pg.Vector(0, centre_y, self.camera_centre_z))
            interaction_recente = hasattr(self.vue_3d, "interaction_manuelle_recente") and self.vue_3d.interaction_manuelle_recente()

            if interaction_recente:
                self.camera_distance_actuelle = self.convertir_distance_vue_vers_base(distance_vue_courante, fov_3d)
                try:
                    self.camera_centre_z = float(centre_courant.z())
                except Exception:
                    pass
                self.vue_3d.setCameraParams(
                    center=centre_courant,
                    distance=distance_vue_courante,
                    elevation=elevation_courante,
                    azimuth=azimuth_courant,
                    fov=fov_3d,
                )
            else:
                distance_compensee = self.calculer_distance_camera_compensee(self.camera_distance_actuelle, fov_3d)
                self.vue_3d.setCameraParams(
                    center=pg.Vector(0, centre_y, self.camera_centre_z),
                    distance=distance_compensee,
                    elevation=elevation_courante,
                    azimuth=azimuth_courant,
                    fov=fov_3d,
                )

    def mettre_a_jour_perspective_camera(self, valeur):
        self.perspective_fov = max(5.0, float(valeur))
        if not self.vue_2d_active:
            self.appliquer_mode_camera()

    def basculer_vue_2d(self):
        self.vue_2d_active = self.bouton_vue_2d.isChecked()
        self.bouton_vue_2d.setText("VUE 3D" if self.vue_2d_active else "VUE 2D")
        self.appliquer_mode_camera()
        self.mettre_a_jour_axes_3d_stables()
        self.mettre_a_jour_legende_axes_3d()

    def mettre_a_jour_bouton_plein_ecran(self):
        est_en_plein_ecran = self.isFullScreen()
        if hasattr(self, "bouton_exit_fullscreen"):
            self.bouton_exit_fullscreen.setVisible(est_en_plein_ecran)
        if hasattr(self, "bouton_fullscreen"):
            self.bouton_fullscreen.setVisible(not est_en_plein_ecran)

    def passer_en_plein_ecran(self):
        if not self.isFullScreen():
            self.showFullScreen()
            self.raise_()
            self.activateWindow()
        self.mettre_a_jour_bouton_plein_ecran()

    def quitter_plein_ecran(self):
        if self.isFullScreen():
            self.showNormal()
            self.raise_()
            self.activateWindow()
        self.mettre_a_jour_bouton_plein_ecran()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape and self.isFullScreen():
            self.quitter_plein_ecran()
            event.accept()
            return
        if event.key() == Qt.Key.Key_F11:
            if self.isFullScreen():
                self.quitter_plein_ecran()
            else:
                self.passer_en_plein_ecran()
            event.accept()
            return
        super().keyPressEvent(event)

    def changeEvent(self, event):
        super().changeEvent(event)
        self.mettre_a_jour_bouton_plein_ecran()

    def nettoyer_apres_simulation(self):
        self.bouton_demarrer.setEnabled(True)
        self.bouton_pause.setEnabled(False)
        self.bouton_pause.setText("PAUSE")
        self.bouton_pause.setStyleSheet("")
        self.bouton_arreter.setEnabled(False)
        self.bouton_quicksave.setEnabled(False)
        self.bouton_quicksave.setText("QUICKSAVE (Pause requise)")
        self.mettre_a_jour_indicateur_stabilite()

    def gerer_erreur_simulation(self, details_erreur):
        self.export_apres_arret = False
        self.lecture_en_cours = False
        self.btn_play_pause.setText("▶")
        self.nettoyer_apres_simulation()

        dialog = QMessageBox(self)
        dialog.setWindowTitle("Erreur de simulation")
        dialog.setIcon(QMessageBox.Icon.Critical)
        dialog.setText("La simulation s'est arrêtée à cause d'une erreur.")
        dialog.setInformativeText("Consulte les détails pour identifier le problème.")
        dialog.setDetailedText(details_erreur)
        dialog.exec()

    def ajuster_camera_3d(self, matrice_z):
        if not self.params_actuels:
            return

        if self.vue_2d_active:
            self.camera_centre_z = 0.0
            self.appliquer_mode_camera()
            return

        z_min = float(np.min(matrice_z))
        z_max = float(np.max(matrice_z))
        centre_z_cible = 0.5 * (z_min + z_max)
        amplitude_z = max(1.0, z_max - z_min)
        longueur_ref = max(self.params_actuels["largeur_x_mm"], self.params_actuels["longueur_y_mm"])
        distance_cible = max(self.camera_distance_initiale, longueur_ref * 1.22 + amplitude_z * 2.6)

        self.camera_centre_z = (0.85 * self.camera_centre_z) + (0.15 * centre_z_cible)
        self.camera_distance_actuelle = (0.88 * self.camera_distance_actuelle) + (0.12 * distance_cible)

        self.appliquer_mode_camera()

    def dessiner_rendu_3d(self, matrice_temperatures_3d, temps_sim, t1, t2, t3):
        temp_min = self.temperature_ambiante_ref
        temp_max = self.temperature_max_globale
        if temp_max <= temp_min:
            temp_max = temp_min + 1.0
        
        self.lbl_min_temp.setText(f"{temp_min:.1f} °C")
        self.lbl_max_temp.setText(f"{temp_max:.1f} °C")
        
        matrice_z_T = matrice_temperatures_3d.T 
        matrice_normalisee = np.clip((matrice_z_T - temp_min) / (temp_max - temp_min), 0, 1)
        couleurs_brutes = self.palette_couleurs.map(matrice_normalisee)
        couleurs_calculees = couleurs_brutes.astype(np.float32) / 255.0
        
        matrice_z = (matrice_z_T - temp_min) * self.exageration_z
        self.surface_thermique.setData(x=self.grille_x, y=self.grille_y, z=matrice_z, colors=couleurs_calculees)
        self.ajuster_camera_3d(matrice_z)

        p = self.params_actuels if self.params_actuels else self.recuperer_parametres_interface()
        self.mettre_a_jour_axes_3d_stables(p, temp_min, temp_max)
        self.mettre_a_jour_legende_axes_3d(p, temp_min, temp_max)

        titre_live = f"T={temps_sim:.1f}s  |  T1 (Bleu): {t1:.1f}°C  |  T2 (Orange): {t2:.1f}°C  |  T3 (Vert): {t3:.1f}°C"
        self.graphique_2d.setTitle(titre_live, color='#38BDF8', size='11pt')
        def coord_vers_indices(x_mm, y_mm):
            idx_x = int(round((x_mm + p["largeur_x_mm"]/2) / self.pas_x))
            idx_y = int(round(y_mm / self.pas_y))
            idx_x = np.clip(idx_x, 0, len(self.grille_x) - 1)
            idx_y = np.clip(idx_y, 0, len(self.grille_y) - 1)
            return idx_y, idx_x 
        
        def calculer_z(x_mm, y_mm):
            idx_y, idx_x = coord_vers_indices(x_mm, y_mm)
            z = (matrice_temperatures_3d[idx_y, idx_x] - temp_min) * self.exageration_z
            return z + 0.5 

        x1, y1 = p["pos_x_capteur_1_mm"], p["pos_y_capteur_1_mm"]
        x2, y2 = p["pos_x_capteur_2_mm"], p["pos_y_capteur_2_mm"]
        x3, y3 = p["pos_x_capteur_3_mm"], p["pos_y_capteur_3_mm"]
        
        points_capteurs = np.array([
            [x1, y1, calculer_z(x1, y1)],
            [x2, y2, calculer_z(x2, y2)],
            [x3, y3, calculer_z(x3, y3)]
        ], dtype=np.float32)
        
        couleurs_capteurs = np.array([
            [59/255, 130/255, 246/255, 1.0], 
            [245/255, 158/255, 11/255, 1.0], 
            [16/255, 185/255, 129/255, 1.0] 
        ], dtype=np.float32)
        
        self.scatter_capteurs.setData(pos=points_capteurs, color=couleurs_capteurs)

    def terminer_simulation(self, parametres, resultats):
        self.donnees_entree = parametres
        self.donnees_resultats = resultats
        self.mode_direct_actif = False

        if self.donnees_temps:
            self.curseur_temps_2d.setPos(self.donnees_temps[-1])
            self.curseur_temps_2d.show()

        if self.chemin_sauvegarde or self.export_apres_arret:
            self.exporter_resultats_json()
        self.export_apres_arret = False

    def exporter_resultats_json(self):
        if self.donnees_resultats is None or self.donnees_entree is None:
            return
        if not self.chemin_sauvegarde:
            self.choisir_chemin_sauvegarde()
            if not self.chemin_sauvegarde:
                return

        contenu_export = {"parametres": self.donnees_entree, "resultats": self.donnees_resultats}
        try:
            with open(self.chemin_sauvegarde, "w", encoding="utf-8") as fichier:
                json.dump(contenu_export, fichier, indent=4, default=lambda x: x.item() if isinstance(x, np.generic) else x)
        except (OSError, TypeError, ValueError) as erreur:
            QMessageBox.critical(self, "Erreur de sauvegarde", f"Impossible d'exporter les résultats : {erreur}")

    def closeEvent(self, event):
        if self.thread_simulation is not None and self.thread_simulation.isRunning():
            self.thread_simulation.stop()
            self.thread_simulation.wait(2000)
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    fenetre_principale = MainWindow()
    if getattr(fenetre_principale, "demarrer_en_plein_ecran", False):
        fenetre_principale.showFullScreen()
    else:
        fenetre_principale.show()
    sys.exit(app.exec())