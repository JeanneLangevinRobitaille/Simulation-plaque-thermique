import sys
import json
import numpy as np
from PyQt6.QtGui import QIcon, QFont, QColor
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, 
                             QFileDialog, QFormLayout, QSplitter, QFrame,
                             QScrollArea, QMessageBox, QProgressBar, 
                             QGroupBox, QSlider, QSpinBox, QDoubleSpinBox, QLineEdit,
                             QSizePolicy, QComboBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
import pyqtgraph as pg
import pyqtgraph.opengl as gl

# ==============================================================================
# WIDGET PERSONNALISÉ : Le Slider "à la Desmos"
# ==============================================================================
class SliderWithValue(QWidget):
    def __init__(self, min_val, max_val, default_val, decimals=1, parent=None):
        super().__init__(parent)
        self.decimals = decimals
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
        if self.decimals == 0:
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
QScrollBar:vertical { border: none; background-color: #3b1a00; width: 8px; }
QScrollBar::handle:vertical { background-color: #6e3103; border-radius: 4px; min-height: 20px; }
QScrollBar::handle:vertical:hover { background-color: #4a2300; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
#LeftPanel { background-color: #0F172A; border-right: 1px solid #0F172A; }
#ScrollPanel { border: none; background-color: transparent; }

/* === TITRES DE GROUPES === */
QGroupBox { 
    border: 2px solid #334155; 
    border-radius: 8px; 
    margin-top: 18px;
    padding-top: 28px; 
    background-color: rgba(30, 41, 59, 0.4); 
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
#Section { background-color: transparent; border-top: 1px solid #1E293B; }
QPushButton { background-color: #334155; color: #F8FAFC; border: 1px solid #475569; border-radius: 5px; padding: 8px 12px; font-weight: 600; font-size: 11px; }
QPushButton:hover { background-color: #475569; border: 1px solid #64748B; }
#btn_import, #btn_save { background-color: #3B82F6; border: 1px solid #1E40AF; }
#btn_import:hover, #btn_save:hover { background-color: #60A5FA; }
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

# ==============================================================================
# THREAD DE SIMULATION
# ==============================================================================
class SimulationThread(QThread):
    progress_signal = pyqtSignal(int)
    update_signal = pyqtSignal(float, np.ndarray, float, float, float)
    finished_signal = pyqtSignal(dict, dict)

    def __init__(self, data, mode_pid_actif):
        super().__init__()
        self.parametres = data
        self.en_cours_d_execution = True
        self.en_pause = False
        
        self.mode_pid_actif = mode_pid_actif
        self.puissance_manuelle_voulue = float(data["puissance_tec_W"])
        self.consigne_voulue = float(data["consigne_C"])
        
        # --- NOUVEAU : Tension Dynamique ---
        self.tension_dynamique = float(data["tension_resistance_V"])
        self.puissance_dynamique = 0.0

    def modifier_parametres_controle(self, mode_pid_actif, nouvelle_puissance, nouvelle_consigne, nouvelle_tension):
        self.mode_pid_actif = mode_pid_actif
        self.puissance_manuelle_voulue = float(nouvelle_puissance)
        self.consigne_voulue = float(nouvelle_consigne)
        self.tension_dynamique = float(nouvelle_tension)

    # --- NOUVEAU : Fonction Pause ---
    def toggle_pause(self):
        self.en_pause = not self.en_pause
        return self.en_pause

    def run(self):
        params = self.parametres
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
            if target <= table_consignes[0]: return table_pwm[0]
            if target >= table_consignes[-1]: return table_pwm[-1]
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

        while self.en_cours_d_execution and temps_ecoule < params["temps_total_s"]:
            
            # --- GESTION DE LA PAUSE ---
            while self.en_pause and self.en_cours_d_execution:
                self.msleep(50) 
            if not self.en_cours_d_execution:
                break
                
            if self.mode_pid_actif:
                if temps_ecoule >= prochain_temps_pid:
                    t3_actuel = matrice_T[idx_y_T3, idx_x_T3] 
                    e_k = self.consigne_voulue - t3_actuel
                    aw_uop = obtenir_uop(self.consigne_voulue)
                    
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
                self.puissance_dynamique = self.puissance_manuelle_voulue


            puissance_volumique_tec = self.puissance_dynamique / volume_module_tec
            ajout_temp_tec = (puissance_volumique_tec * pas_temps) / (params["masse_volumique_rho"] * params["chaleur_massique_cp"])
            
            # --- CALCUL EN TEMPS RÉEL DE LA PERTURBATION (TENSION) ---
            ajout_temp_resistance = (self.tension_dynamique**2 * pas_temps) / (params["valeur_resistance_ohm"] * params["masse_volumique_rho"] * params["chaleur_massique_cp"] * params["epaisseur_mm"] * pas_x * pas_y)

            for _ in range(calculs_par_actualisation):
                if temps_ecoule >= params["temps_total_s"]: break
                
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
                self.update_signal.emit(temps_ecoule, matrice_T.copy(), matrice_T[idx_y_T1, idx_x_T1], matrice_T[idx_y_T2, idx_x_T2], matrice_T[idx_y_T3, idx_x_T3])

        self.progress_signal.emit(100)
        resultats_finaux = {"temps": historique_temps, "T1": historique_T1, "T2": historique_T2, "T3": historique_T3}
        self.finished_signal.emit(params, resultats_finaux)

    def stop(self):
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
        
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Taille de la fenêtre")
        dialog.setText("Quelle taille de fenêtre voulez-vous ?")
        dialog.setIcon(QMessageBox.Icon.Question)
        btn_80 = dialog.addButton("80% de l'écran", QMessageBox.ButtonRole.AcceptRole)
        btn_plein = dialog.addButton("Plein écran", QMessageBox.ButtonRole.RejectRole)
        dialog.exec()
        
        if dialog.clickedButton() == btn_plein:
            self.showMaximized()
        else:
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
        
        self.historique_matrices_3D = []
        self.mode_direct_actif = True
        self.temperature_ambiante_ref = 20.0
        self.temperature_max_globale = 21.0
        self.exageration_z = 5.0 

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
        layout_gauche.setContentsMargins(5, 5, 5, 5) 
        
        zone_defilement = QScrollArea()
        zone_defilement.setObjectName("ScrollPanel")
        zone_defilement.setWidgetResizable(True)
        contenu_defilement = QWidget()
        self.layout_formulaire = QVBoxLayout(contenu_defilement)
        self.layout_formulaire.setSpacing(15) 
        
        self.champs_saisie = {}
        
        definition_parametres = {
            "Contrôle Thermique": {"puissance_tec_W": 1.0, "consigne_C": 35.0},
            "Paramètres de la plaque": {"longueur_y_mm": 117.5, "largeur_x_mm": 61.5, "epaisseur_mm": 1.7},
            "Paramètres de la simulation": {"temps_total_s": 150.0, "resolution_grille": 50.0, "temperature_ambiante_C": 20.0, "intervalle_affichage": 1.0},
            "Paramètres physiques": {"diffusivite_alpha": 97.0, "masse_volumique_rho": 2.7e-3, "chaleur_massique_cp": 0.9, "coeff_convection_h": 5.0e-5},
            "Coordonnées d'intérêt": {
                "pos_x_tec_mm": 0.0, "pos_y_tec_mm": 5.0,
                "pos_x_capteur_1_mm": 0.0, "pos_y_capteur_1_mm": 14.57,
                "pos_x_capteur_2_mm": 0.0, "pos_y_capteur_2_mm": 59.42,
                "pos_x_capteur_3_mm": 0.0, "pos_y_capteur_3_mm": 103.79
            },
            "Perturbation (Résistance)": {
                "pos_x_resistance_mm": 0.0, "pos_y_resistance_mm": 38.0,
                "valeur_resistance_ohm": 25.0, "tension_resistance_V": 1.0
            }
        }

        for nom_section, variables in definition_parametres.items():
            groupe = QGroupBox(nom_section)
            layout_groupe = QVBoxLayout(groupe)
            layout_groupe.setContentsMargins(12, 20, 12, 12)
            layout_groupe.setSpacing(16)
            
            for cle_variable, valeur_defaut in variables.items():
                layout_param = QVBoxLayout()
                layout_param.setSpacing(6)
                
                texte_label = cle_variable.replace("_", " ").title()
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
                    "valeur_resistance_ohm": (1, 100), "tension_resistance_V": (0, 10)
                }
                
                min_v, max_v = plages.get(cle_variable, (-1000, 1000))
                decimales = 3 if "e" in str(valeur_defaut).lower() else (1 if cle_variable.endswith("_mm") or "capteur" in cle_variable or "tec" in cle_variable or "resistance" in cle_variable or "consigne" in cle_variable else 2)
                
                slider_widget = SliderWithValue(min_v, max_v, float(valeur_defaut), decimals=decimales)
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
        self.champs_saisie["consigne_C"].slider.valueChanged.connect(self.actualiser_controle_live)
        self.champs_saisie["tension_resistance_V"].slider.valueChanged.connect(self.actualiser_controle_live) # NOUVEAU: Écoute de la tension
        self.champs_saisie["puissance_tec_W"].value_input.editingFinished.connect(self.actualiser_controle_live)
        self.champs_saisie["consigne_C"].value_input.editingFinished.connect(self.actualiser_controle_live)
        self.champs_saisie["tension_resistance_V"].value_input.editingFinished.connect(self.actualiser_controle_live)
        
        cadre_controles = QFrame()
        cadre_controles.setObjectName("Section")
        layout_controles = QVBoxLayout(cadre_controles)
        
        layout_mode = QHBoxLayout()
        label_mode = QLabel("Mode de fonctionnement :")
        label_mode.setStyleSheet("font-weight: bold; color: #38BDF8;")
        self.combo_mode_sys = QComboBox()
        self.combo_mode_sys.addItems(["PID Automatique (Consigne)", "Manuel (Puissance Brute)"])
        self.combo_mode_sys.setStyleSheet("QComboBox { background-color: #1E293B; color: #E2E8F0; border: 1px solid #334155; padding: 5px; border-radius: 4px;}")
        self.combo_mode_sys.currentIndexChanged.connect(self.actualiser_controle_live)
        layout_mode.addWidget(label_mode)
        layout_mode.addWidget(self.combo_mode_sys)
        layout_controles.addLayout(layout_mode)

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
        
        layout_controles.addLayout(ligne_boutons_fichiers)
        layout_controles.addLayout(ligne_boutons_simulation)
        layout_controles.addWidget(self.bouton_quicksave) # Ajout du QuickSave
        layout_controles.addWidget(self.barre_progression)
        layout_gauche.addWidget(cadre_controles)

        # === PANNEAU DROIT (Graphiques) ===
        panneau_droit = QWidget()
        layout_droit = QVBoxLayout(panneau_droit)
        layout_droit.setContentsMargins(0, 0, 0, 0)
        separateur_graphiques = QSplitter(Qt.Orientation.Vertical)
        
        container_3d = QWidget()
        layout_3d_h = QHBoxLayout(container_3d)
        layout_3d_h.setContentsMargins(0, 0, 0, 0)

        self.vue_3d = gl.GLViewWidget()
        self.vue_3d.setCameraPosition(distance=150, elevation=45, azimuth=45)
        self.grille_3d = gl.GLGridItem()
        self.grille_3d.scale(10, 10, 10)
        self.vue_3d.addItem(self.grille_3d)
        
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

        pg.setConfigOptions(antialias=True, background='#0F172A', foreground='#E2E8F0')
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

        separateur_graphiques.addWidget(container_3d)
        separateur_graphiques.addWidget(self.graphique_2d)
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

    def recuperer_parametres_interface(self):
        return {cle: champ.value() for cle, champ in self.champs_saisie.items()}

    def importer_parametres_json(self):
        chemin_fichier, _ = QFileDialog.getOpenFileName(self, "Importer Paramètres", "", "Fichiers JSON (*.json)")
        if chemin_fichier:
            try:
                with open(chemin_fichier, 'r') as fichier:
                    donnees = json.load(fichier)
                    parametres = donnees.get("parametres", donnees)
                for cle, valeur in parametres.items():
                        if cle in self.champs_saisie:
                            self.champs_saisie[cle].setValue(float(valeur))
            except Exception as erreur:
                QMessageBox.critical(self, "Erreur", f"Impossible de lire le fichier: {erreur}")

    def choisir_chemin_sauvegarde(self):
        chemin_fichier, _ = QFileDialog.getSaveFileName(self, "Choisir où sauvegarder les résultats", "", "Fichiers JSON (*.json);;Tous les fichiers (*.*)", options=QFileDialog.Option.DontUseNativeDialog)
        if chemin_fichier:
            if not chemin_fichier.endswith(".json"):
                chemin_fichier += ".json"
            self.chemin_sauvegarde = chemin_fichier

    def lancer_simulation(self):
        if hasattr(self, 'thread_simulation') and self.thread_simulation.isRunning():
            QMessageBox.information(self, "Simulation en cours", "Une simulation est déjà en cours d'exécution.")
            return

        params = self.recuperer_parametres_interface()
        if not params: return

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
        
        self.temperature_ambiante_ref = params["temperature_ambiante_C"]
        self.temperature_max_globale = self.temperature_ambiante_ref + 1.0 
        
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
        self.bouton_quicksave.setEnabled(False)

        self.surface_thermique.resetTransform()

        centre_physique_y = params["longueur_y_mm"] / 2.0
        self.vue_3d.setCameraPosition(pos=pg.Vector(0, centre_physique_y, 0))
        self.grille_3d.resetTransform()
        self.grille_3d.scale(10, 10, 10)
        self.grille_3d.translate(0, centre_physique_y, 0)

        matrice_initiale = np.full((self.ny, self.nx), params["temperature_ambiante_C"], dtype=np.float32)
        self.dessiner_rendu_3d(matrice_initiale, 0.0, params["temperature_ambiante_C"], params["temperature_ambiante_C"], params["temperature_ambiante_C"])

        mode_pid = (self.combo_mode_sys.currentIndex() == 0)

        self.thread_simulation = SimulationThread(params, mode_pid)
        self.thread_simulation.update_signal.connect(self.actualiser_graphiques)
        self.thread_simulation.progress_signal.connect(self.barre_progression.setValue)
        self.thread_simulation.finished_signal.connect(self.terminer_simulation)
        self.thread_simulation.start()

    # --- NOUVEAU: Mettre la simulation en pause/reprise ---
    def basculer_pause(self):
        if hasattr(self, 'thread_simulation') and self.thread_simulation.isRunning():
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
        resultats_actuels = {
            "temps": self.donnees_temps,
            "T1": self.donnees_y_t1,
            "T2": self.donnees_y_t2,
            "T3": self.donnees_y_t3
        }
        contenu_export = {"parametres": self.params_actuels, "resultats": resultats_actuels}
        
        chemin_fichier, _ = QFileDialog.getSaveFileName(self, "QuickSave : Sauvegarder les résultats", "quicksave.json", "Fichiers JSON (*.json);;Tous les fichiers (*.*)", options=QFileDialog.Option.DontUseNativeDialog)
        if chemin_fichier:
            if not chemin_fichier.endswith(".json"): chemin_fichier += ".json"
            with open(chemin_fichier, "w") as fichier:
                json.dump(contenu_export, fichier, indent=4, default=lambda x: x.item() if isinstance(x, np.generic) else x)
            QMessageBox.information(self, "Succès", f"QuickSave effectué !\nFichier : {chemin_fichier}")

    def stopper_simulation(self):
        if hasattr(self, 'thread_simulation') and self.thread_simulation.isRunning():
            self.export_apres_arret = True
            self.thread_simulation.stop()
            self.bouton_pause.setEnabled(False)
            self.bouton_quicksave.setEnabled(False)
            
    def actualiser_controle_live(self):
        if hasattr(self, 'thread_simulation') and self.thread_simulation.isRunning():
            mode_pid = (self.combo_mode_sys.currentIndex() == 0)
            puiss = self.champs_saisie["puissance_tec_W"].value()
            cons = self.champs_saisie["consigne_C"].value()
            tens = self.champs_saisie["tension_resistance_V"].value()
            self.thread_simulation.modifier_parametres_controle(mode_pid, puiss, cons, tens)

    def actualiser_graphiques(self, temps_sim, matrice_temperatures_3d, temp_T1, temp_T2, temp_T3):
        max_actuel = matrice_temperatures_3d.max()
        if max_actuel > self.temperature_max_globale:
            self.temperature_max_globale = max_actuel

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

    def dessiner_rendu_3d(self, matrice_temperatures_3d, temps_sim, t1, t2, t3):
        temp_min = self.temperature_ambiante_ref
        temp_max = self.temperature_max_globale
        if temp_max <= temp_min: temp_max = temp_min + 1.0
        
        self.lbl_min_temp.setText(f"{temp_min:.1f} °C")
        self.lbl_max_temp.setText(f"{temp_max:.1f} °C")
        
        matrice_z_T = matrice_temperatures_3d.T 
        matrice_normalisee = np.clip((matrice_z_T - temp_min) / (temp_max - temp_min), 0, 1)
        couleurs_brutes = self.palette_couleurs.map(matrice_normalisee)
        couleurs_calculees = couleurs_brutes.astype(np.float32) / 255.0
        
        matrice_z = (matrice_z_T - temp_min) * self.exageration_z
        self.surface_thermique.setData(x=self.grille_x, y=self.grille_y, z=matrice_z, colors=couleurs_calculees)

        titre_live = f"T={temps_sim:.1f}s  |  T1 (Bleu): {t1:.1f}°C  |  T2 (Orange): {t2:.1f}°C  |  T3 (Vert): {t3:.1f}°C"
        self.graphique_2d.setTitle(titre_live, color='#38BDF8', size='11pt')

        p = self.params_actuels
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
        self.bouton_demarrer.setEnabled(True)
        self.bouton_pause.setEnabled(False)
        self.bouton_quicksave.setEnabled(False)
        
        if self.donnees_temps:
            self.curseur_temps_2d.setPos(self.donnees_temps[-1])
            self.curseur_temps_2d.show()
            
        if self.chemin_sauvegarde or self.export_apres_arret:
            self.exporter_resultats_json()
        self.export_apres_arret = False

    def exporter_resultats_json(self):
        if self.donnees_resultats is None or self.donnees_entree is None: return
        if not self.chemin_sauvegarde:
            self.choisir_chemin_sauvegarde()
            if not self.chemin_sauvegarde: return
             
        contenu_export = {"parametres": self.donnees_entree, "resultats": self.donnees_resultats}
        with open(self.chemin_sauvegarde, "w") as fichier:
            json.dump(contenu_export, fichier, indent=4, default=lambda x: x.item() if isinstance(x, np.generic) else x)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    fenetre_principale = MainWindow()
    fenetre_principale.show()
    sys.exit(app.exec())