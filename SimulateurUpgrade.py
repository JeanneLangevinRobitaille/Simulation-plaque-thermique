import os
import sys
import json
import time
import ctypes
from ctypes import wintypes
import traceback
from pathlib import Path
from threading import Lock

import numpy as np
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel,
                             QFileDialog, QSplitter, QFrame,
                             QScrollArea, QMessageBox, QProgressBar,
                             QGroupBox, QSlider, QLineEdit,
                             QSizePolicy, QComboBox, QListView)
from PyQt6.QtCore import Qt, QRect, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont
import pyqtgraph as pg

try:
    import pyqtgraph.opengl as gl
    OPENGL_DISPONIBLE = True
except Exception:
    gl = None
    OPENGL_DISPONIBLE = False

AUTO_CALIBRATION_JSON = Path(__file__).resolve().parent / "TestsAndData" / "parametres_calibres_combinee.json"
AUTO_CALIBRATION_CHECK_INTERVAL_MS = 2000
DEFAULT_SCREEN_GEOMETRY = QRect(0, 0, 1366, 768)


def obtenir_geometrie_ecran_disponible(widget=None):
    geometrie = None
    ecran = None

    if widget is not None:
        try:
            ecran = widget.screen()
        except Exception:
            ecran = None

        if ecran is None:
            try:
                centre = widget.mapToGlobal(widget.rect().center())
                ecran = QApplication.screenAt(centre)
            except Exception:
                ecran = None

    if ecran is None:
        try:
            ecran = QApplication.primaryScreen()
        except Exception:
            ecran = None

    if ecran is not None:
        try:
            geometrie = ecran.availableGeometry()
            if geometrie is None or geometrie.width() <= 0 or geometrie.height() <= 0:
                geometrie = ecran.geometry()
        except Exception:
            geometrie = None

    if geometrie is None or geometrie.width() <= 0 or geometrie.height() <= 0:
        geometrie = QRect(DEFAULT_SCREEN_GEOMETRY)

    return geometrie


def calculer_geometrie_fenetre_initiale(geometrie_ecran):
    largeur_ecran = max(520, int(geometrie_ecran.width()))
    hauteur_ecran = max(420, int(geometrie_ecran.height()))
    petit_ecran = largeur_ecran < 1366 or hauteur_ecran < 820

    largeur_max = max(480, largeur_ecran - 16)
    hauteur_max = max(360, hauteur_ecran - 16)
    largeur_cible = int(round(largeur_ecran * (0.94 if petit_ecran else 0.80)))
    hauteur_cible = int(round(hauteur_ecran * (0.94 if petit_ecran else 0.82)))

    largeur = max(min(720, largeur_max), min(largeur_cible, largeur_max))
    hauteur = max(min(520, hauteur_max), min(hauteur_cible, hauteur_max))

    x = geometrie_ecran.x() + max(0, (largeur_ecran - largeur) // 2)
    y = geometrie_ecran.y() + max(0, (hauteur_ecran - hauteur) // 2)
    return QRect(x, y, largeur, hauteur)

# ==============================================================================
# WIDGET PERSONNALISÉ : Le Slider "à la Desmos"
# ==============================================================================
class SliderWithValue(QWidget):
    def __init__(self, min_val, max_val, default_val, decimals=1, scientific=False, parent=None):
        super().__init__(parent)
        self.decimals = decimals
        self.scientific = scientific
        self.min_val = float(min_val)
        self.max_val = float(max_val)
        if np.isclose(self.max_val, self.min_val):
            self.max_val = self.min_val + 1.0
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 10000)
        self.slider.setTickPosition(QSlider.TickPosition.NoTicks)
        self.slider_value = self._convertir_valeur_vers_slider(default_val)
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
    
    def _convertir_valeur_vers_slider(self, valeur):
        plage = self.max_val - self.min_val
        if abs(plage) < 1e-12:
            return 0
        ratio = (float(valeur) - self.min_val) / plage
        return int(np.clip(round(ratio * 10000), 0, 10000))

    def on_slider_changed(self):
        self.update_value_label()
    
    def on_text_edited(self):
        try:
            nouveau_val = float(self.value_input.text().replace(',', '.'))
            if self.min_val <= nouveau_val <= self.max_val:
                slider_val = self._convertir_valeur_vers_slider(nouveau_val)
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
        self.slider_value = self._convertir_valeur_vers_slider(val)
        self.slider.blockSignals(True)
        self.slider.setValue(self.slider_value)
        self.slider.blockSignals(False)
        self.update_value_label()

    def configure_range(self, min_val=None, max_val=None, decimals=None, scientific=None, current_val=None):
        valeur_courante = self.value() if current_val is None else float(current_val)

        if min_val is not None:
            self.min_val = float(min_val)
        if max_val is not None:
            self.max_val = float(max_val)
        if decimals is not None:
            self.decimals = int(decimals)
        if scientific is not None:
            self.scientific = bool(scientific)

        if np.isclose(self.max_val, self.min_val):
            self.max_val = self.min_val + 1.0

        valeur_courante = float(np.clip(valeur_courante, self.min_val, self.max_val))
        self.slider_value = int((valeur_courante - self.min_val) / (self.max_val - self.min_val) * 10000)

        self.slider.blockSignals(True)
        self.slider.setValue(self.slider_value)
        self.slider.blockSignals(False)
        self.update_value_label()


class FullscreenSafeComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        vue = QListView()
        vue.setSpacing(2)
        vue.setUniformItemSizes(True)
        self.setView(vue)
        self.setMaxVisibleItems(12)
        self._popup_transition_active = False
        self._popup_visible = False
        self._dernier_toggle_popup = 0.0

    def _verrouiller_popup(self, delai_ms=180):
        self._popup_transition_active = True
        QTimer.singleShot(delai_ms, lambda: setattr(self, "_popup_transition_active", False))

    def _stabiliser_popup(self):
        try:
            popup = self.view().window()
            popup.setWindowFlag(Qt.WindowType.Popup, True)
            popup.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
            popup.setWindowFlag(Qt.WindowType.NoDropShadowWindowHint, True)
            popup.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
            popup.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, False)

            popup.adjustSize()
            largeur_colonne = self.view().sizeHintForColumn(0)
            largeur_popup = max(self.width(), popup.sizeHint().width(), (largeur_colonne if largeur_colonne > 0 else 0) + 36)

            hauteur_ligne = self.view().sizeHintForRow(0)
            if hauteur_ligne <= 0:
                hauteur_ligne = 24
            hauteur_popup = max(popup.sizeHint().height(), min(self.count(), self.maxVisibleItems()) * hauteur_ligne + 8)

            screen = self.screen()
            if screen is None:
                try:
                    screen = QApplication.screenAt(self.mapToGlobal(self.rect().center()))
                except Exception:
                    screen = QApplication.primaryScreen()
            zone_disponible = screen.availableGeometry() if screen is not None else popup.geometry()

            position = self.mapToGlobal(self.rect().bottomLeft())
            if position.y() + hauteur_popup > zone_disponible.bottom() - 4:
                position = self.mapToGlobal(self.rect().topLeft())
                position.setY(position.y() - hauteur_popup)

            position.setX(max(zone_disponible.left() + 4, min(position.x(), zone_disponible.right() - largeur_popup - 4)))
            position.setY(max(zone_disponible.top() + 4, min(position.y(), zone_disponible.bottom() - hauteur_popup - 4)))

            popup.setGeometry(position.x(), position.y(), largeur_popup, hauteur_popup)
            popup.show()
            popup.raise_()
            popup.activateWindow()
            self.view().setFocus(Qt.FocusReason.PopupFocusReason)
            self._popup_visible = popup.isVisible()
        except Exception:
            self._popup_visible = False

    def mousePressEvent(self, event):
        maintenant = time.perf_counter()
        if self._popup_transition_active or (maintenant - self._dernier_toggle_popup) < 0.12:
            event.accept()
            return

        fenetre = self.window()
        if fenetre is not None and fenetre.isFullScreen():
            fenetre.raise_()
            fenetre.activateWindow()
        super().mousePressEvent(event)

    def showPopup(self):
        maintenant = time.perf_counter()
        if self._popup_transition_active or (maintenant - self._dernier_toggle_popup) < 0.12:
            return

        self._dernier_toggle_popup = maintenant
        self._popup_visible = True
        self._verrouiller_popup()

        fenetre = self.window()
        if fenetre is not None and fenetre.isFullScreen():
            fenetre.raise_()
            fenetre.activateWindow()
        super().showPopup()
        QTimer.singleShot(20, self._stabiliser_popup)

    def hidePopup(self):
        maintenant = time.perf_counter()
        if self._popup_transition_active and (maintenant - self._dernier_toggle_popup) < 0.08:
            return

        self._dernier_toggle_popup = maintenant
        self._popup_visible = False
        self._verrouiller_popup(120)
        super().hidePopup()

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
QComboBox { combobox-popup: 0; }
QComboBox QAbstractItemView {
    background-color: #0F172A;
    color: #E2E8F0;
    border: 1px solid #334155;
    selection-background-color: #0EA5E9;
    selection-color: white;
    outline: 0;
}
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
    puissance_perturb = abs(float(params.get("puissance_perturbation_W", 0.0)))
    marge_haute = max(
        8.0,
        abs(float(params.get("puissance_tec_W", 0.0))) * 4.0,
        puissance_perturb * 4.0,
    )
    temp_max = max(
        temp_min + 10.0,
        float(params.get("consigne_C", temp_min)) + 5.0,
        temp_min + marge_haute,
    )
    return temp_min, temp_max


def normaliser_mode_commande_tec(mode):
    mode_normalise = str(mode).strip().lower()
    return "pwm" if "pwm" in mode_normalise else "watt"


def normaliser_mode_commande_perturbation(mode):
    mode_normalise = str(mode).strip().lower()
    return "watt" if ("watt" in mode_normalise or "power" in mode_normalise or "puissance" in mode_normalise) else "voltage"


def normaliser_degre_fit_pwm(degre):
    try:
        degre_normalise = int(round(float(degre)))
    except (TypeError, ValueError):
        return 3
    return int(np.clip(degre_normalise, 1, 3))


def ajuster_courbe_pwm_temperature_stable(paliers_pwm, temperatures_stables_C, degre=2, temperature_ambiante_C=None):
    """Ajuste un modèle indépendant PWM -> ΔT stable en boucle ouverte.

    Ce fit reste séparé des coefficients physiques calibrés (`alpha`, `rho`, `cp`, `h`).
    Il sert uniquement à dériver une loi de commande indépendante entre un pourcentage
    de PWM et l'effet thermique observé à l'état stationnaire.

    Le degré peut être 1, 2 ou 3; on peut donc démarrer avec l'équation cubique
    déjà identifiée, puis simplifier ensuite vers un modèle plus compact si désiré.
    """
    pwm = np.asarray(paliers_pwm, dtype=float)
    temperatures = np.asarray(temperatures_stables_C, dtype=float)

    if pwm.size != temperatures.size:
        raise ValueError("Les vecteurs PWM et température doivent avoir la même taille.")
    if pwm.size < 2:
        raise ValueError("Au moins deux paliers sont requis pour calculer un fit.")

    degre_utilise = min(normaliser_degre_fit_pwm(degre), pwm.size - 1)
    if temperature_ambiante_C is None:
        temperature_ambiante_C = float(np.min(temperatures))

    delta_temp = temperatures - float(temperature_ambiante_C)
    coefficients_desc = np.polyfit(np.abs(pwm), delta_temp, degre_utilise)
    coefficients = coefficients_desc[::-1]

    return {
        "temperature_ambiante_C": float(temperature_ambiante_C),
        "degre_fit_pwm": int(degre_utilise),
        "coef_pwm_a0": float(coefficients[0]),
        "coef_pwm_a1": float(coefficients[1]) if len(coefficients) > 1 else 0.0,
        "coef_pwm_a2": float(coefficients[2]) if len(coefficients) > 2 else 0.0,
        "coef_pwm_a3": float(coefficients[3]) if len(coefficients) > 3 else 0.0,
    }


def convertir_pwm_vers_puissance(pwm_percent, params):
    pwm_signe = float(np.clip(pwm_percent, -100.0, 100.0))
    amplitude = abs(pwm_signe)
    degre = normaliser_degre_fit_pwm(params.get("degre_fit_pwm", 3))

    a0 = float(params.get("coef_pwm_a0", 1.734031e-02))
    a1 = float(params.get("coef_pwm_a1", 1.406312e-01))
    a2 = float(params.get("coef_pwm_a2", 9.947817e-04)) if degre >= 2 else 0.0
    a3 = float(params.get("coef_pwm_a3", 1.703277e-05)) if degre >= 3 else 0.0

    puissance = a0 + (a1 * amplitude)
    if degre >= 2:
        puissance += a2 * (amplitude ** 2)
    if degre >= 3:
        puissance += a3 * (amplitude ** 3)

    puissance = max(0.0, puissance)
    return float(np.sign(pwm_signe) * puissance)


def convertir_puissance_vers_pwm(puissance_w, params):
    puissance_signee = float(puissance_w)
    puissance = abs(puissance_signee)
    if puissance <= 0.0:
        return 0.0

    signe = -1.0 if puissance_signee < 0 else 1.0
    degre = normaliser_degre_fit_pwm(params.get("degre_fit_pwm", 3))

    a0 = float(params.get("coef_pwm_a0", 1.734031e-02))
    a1 = float(params.get("coef_pwm_a1", 1.406312e-01))
    a2 = float(params.get("coef_pwm_a2", 9.947817e-04)) if degre >= 2 else 0.0
    a3 = float(params.get("coef_pwm_a3", 1.703277e-05)) if degre >= 3 else 0.0

    if degre == 1 or (abs(a2) < 1e-12 and abs(a3) < 1e-12):
        amplitude = 0.0 if abs(a1) < 1e-12 else (puissance - a0) / a1
    elif degre == 2 or abs(a3) < 1e-12:
        discriminant = max(0.0, (a1 ** 2) - (4.0 * a2 * (a0 - puissance)))
        racines = [
            (-a1 + np.sqrt(discriminant)) / (2.0 * a2),
            (-a1 - np.sqrt(discriminant)) / (2.0 * a2),
        ]
        candidats = [racine for racine in racines if racine >= 0.0]
        amplitude = min(
            candidats,
            key=lambda racine: abs((a0 + a1 * racine + a2 * (racine ** 2)) - puissance),
        ) if candidats else 0.0
    else:
        racines = np.roots([a3, a2, a1, a0 - puissance])
        candidats = [
            float(np.real(racine))
            for racine in racines
            if abs(np.imag(racine)) < 1e-8 and 0.0 <= float(np.real(racine)) <= 100.0
        ]
        if candidats:
            amplitude = min(
                candidats,
                key=lambda racine: abs((a0 + a1 * racine + a2 * (racine ** 2) + a3 * (racine ** 3)) - puissance),
            )
        else:
            grille = np.linspace(0.0, 100.0, 2001)
            valeurs = a0 + a1 * grille + a2 * (grille ** 2) + a3 * (grille ** 3)
            amplitude = float(grille[np.argmin(np.abs(valeurs - puissance))])

    amplitude = float(np.clip(amplitude, 0.0, 100.0))
    return signe * amplitude


def convertir_commande_tec_vers_puissance(valeur_commande, params):
    mode = normaliser_mode_commande_tec(params.get("mode_commande_tec", "watt"))
    if mode == "pwm":
        return convertir_pwm_vers_puissance(valeur_commande, params)
    return float(valeur_commande)


def convertir_tension_vers_puissance_perturbation(tension, params):
    tension = max(0.0, float(tension))
    resistance = max(1e-9, float(params.get("valeur_resistance_ohm", 1.0)))
    facteur = max(0.0, float(params.get("facteur_couplage_perturbation", 1.0)))
    return facteur * (tension ** 2) / resistance


def convertir_puissance_vers_tension_perturbation(puissance, params):
    puissance = max(0.0, float(puissance))
    resistance = max(1e-9, float(params.get("valeur_resistance_ohm", 1.0)))
    facteur = max(1e-9, float(params.get("facteur_couplage_perturbation", 1.0)))
    return float(np.sqrt((puissance * resistance) / facteur))


def convertir_commande_perturbation_vers_puissance(valeur_commande, params):
    mode = normaliser_mode_commande_perturbation(params.get("mode_commande_perturbation", "voltage"))
    if mode == "watt":
        return max(0.0, float(valeur_commande))
    return convertir_tension_vers_puissance_perturbation(valeur_commande, params)


class _NullGLItem:
    def setGLOptions(self, *_args, **_kwargs):
        return None

    def setData(self, *_args, **_kwargs):
        return None

    def scale(self, *_args, **_kwargs):
        return None

    def translate(self, *_args, **_kwargs):
        return None

    def setSize(self, *_args, **_kwargs):
        return None

    def resetTransform(self):
        return None


class StableGLViewWidget(gl.GLViewWidget if OPENGL_DISPONIBLE else QWidget):
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

        self.mode_commande_perturbation = normaliser_mode_commande_perturbation(data.get("mode_commande_perturbation", "voltage"))
        self.commande_perturbation_voulue = float(data.get("commande_perturbation_valeur", data["tension_resistance_V"]))
        self.puissance_dynamique = 0.0

        # Calibration empirique issue des essais d'échelons.
        self.facteur_couplage_perturbation = max(0.0, float(data.get("facteur_couplage_perturbation", 0.85)))
        self.constante_temps_perturbation_s = max(0.0, float(data.get("constante_temps_perturbation_s", 8.0)))
        self.debut_perturbation_s = max(0.0, float(data.get("debut_perturbation_s", 0.0)))
        self.duree_perturbation_s = max(0.0, float(data.get("duree_perturbation_s", float(data.get("temps_total_s", 150.0)))))
        self.facteur_couplage_tec = max(0.0, float(data.get("facteur_couplage_tec", 0.60)))
        self.constante_temps_tec_s = max(0.0, float(data.get("constante_temps_tec_s", 8.0)))
        self.puissance_resistance_effective = 0.0
        self.puissance_tec_effective = 0.0

    def modifier_parametres_controle(
        self,
        mode_pid_actif,
        nouvelle_puissance,
        nouvelle_consigne,
        nouvelle_tension,
        nouveau_gain_tec=None,
        nouvelle_tau_tec=None,
        nouveau_debut_perturbation=None,
        nouvelle_duree_perturbation=None,
        nouveau_mode_perturbation=None,
    ):
        with self._control_lock:
            self.mode_pid_actif = bool(mode_pid_actif)
            self.puissance_manuelle_voulue = float(nouvelle_puissance)
            self.consigne_voulue = float(nouvelle_consigne)
            self.commande_perturbation_voulue = float(nouvelle_tension)
            if nouveau_gain_tec is not None:
                self.facteur_couplage_tec = max(0.0, float(nouveau_gain_tec))
            if nouvelle_tau_tec is not None:
                self.constante_temps_tec_s = max(0.0, float(nouvelle_tau_tec))
            if nouveau_debut_perturbation is not None:
                self.debut_perturbation_s = max(0.0, float(nouveau_debut_perturbation))
            if nouvelle_duree_perturbation is not None:
                self.duree_perturbation_s = max(0.0, float(nouvelle_duree_perturbation))
            if nouveau_mode_perturbation is not None:
                self.mode_commande_perturbation = normaliser_mode_commande_perturbation(nouveau_mode_perturbation)

    def obtenir_etat_controle(self):
        with self._control_lock:
            return (
                self.mode_pid_actif,
                self.puissance_manuelle_voulue,
                self.consigne_voulue,
                self.commande_perturbation_voulue,
                self.facteur_couplage_tec,
                self.constante_temps_tec_s,
                self.debut_perturbation_s,
                self.duree_perturbation_s,
                self.mode_commande_perturbation,
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
            largeur_x_mm = float(params["largeur_x_mm"])
            longueur_y_mm = float(params["longueur_y_mm"])
            temperature_ambiante = float(params["temperature_ambiante_C"])
            diffusivite_alpha = float(params["diffusivite_alpha"])
            masse_volumique_rho = float(params["masse_volumique_rho"])
            chaleur_massique_cp = float(params["chaleur_massique_cp"])
            epaisseur_mm = float(params["epaisseur_mm"])
            coeff_convection_h = float(params["coeff_convection_h"])
            temps_total_s = float(params["temps_total_s"])

            pas_x = largeur_x_mm / resolution
            pas_y = longueur_y_mm / resolution

            limite_stabilite = 0.5 / (diffusivite_alpha * ((1 / pas_x**2) + (1 / pas_y**2)))
            pas_temps = 0.2 * min(pas_x, pas_y)**2 / diffusivite_alpha
            pas_temps = min(pas_temps, limite_stabilite)

            volume_module_tec = (2 * pas_x) * (2 * pas_y) * epaisseur_mm
            gain_temperature_tec = pas_temps / max(masse_volumique_rho * chaleur_massique_cp * volume_module_tec, 1e-12)
            gain_temperature_resistance = pas_temps / max(masse_volumique_rho * chaleur_massique_cp * epaisseur_mm * pas_x * pas_y, 1e-12)

            cst_diffusion_x = diffusivite_alpha * pas_temps / pas_x**2
            cst_diffusion_y = diffusivite_alpha * pas_temps / pas_y**2
            cst_perte_convection = coeff_convection_h * pas_temps / (masse_volumique_rho * chaleur_massique_cp * epaisseur_mm)

            forme_grille = (resolution + 1, resolution + 1)
            matrice_T = np.full(forme_grille, temperature_ambiante, dtype=np.float32)
            matrice_T_suivante = np.empty_like(matrice_T)
            tampon_diffusion = np.empty((resolution - 1, resolution - 1), dtype=np.float32)
            tampon_secondaire = np.empty_like(tampon_diffusion)

            demi_largeur = largeur_x_mm / 2.0

            def coord_x_vers_indice(coord_x):
                indice = int(round((coord_x + demi_largeur) / pas_x))
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
            dernier_progression = -1
            intervalle_min_emission_ui_s = 1.0 / 30.0
            dernier_emit_ui = time.perf_counter()

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

            while self.en_cours_d_execution and temps_ecoule < temps_total_s:

                while self.en_pause and self.en_cours_d_execution:
                    self.msleep(50)
                if not self.en_cours_d_execution:
                    break

                mode_pid_actif, puissance_manuelle, consigne, commande_perturbation, facteur_couplage_tec, constante_temps_tec_s, debut_perturbation_s, duree_perturbation_s, mode_commande_perturbation = self.obtenir_etat_controle()

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

                        pwm_percent_signe = (self.pwmActuel / 1023.0) * 100.0
                        self.puissance_dynamique = convertir_pwm_vers_puissance(pwm_percent_signe, params)

                        prochain_temps_pid += periode_pid
                else:
                    self.puissance_dynamique = puissance_manuelle

                commande_perturbation = max(0.0, commande_perturbation)
                puissance_tec_cible = facteur_couplage_tec * self.puissance_dynamique
                coeff_lag_tec = min(1.0, pas_temps / constante_temps_tec_s) if constante_temps_tec_s > 0 else 1.0
                coeff_lag_resistance = min(1.0, pas_temps / self.constante_temps_perturbation_s) if self.constante_temps_perturbation_s > 0 else 1.0
                fin_perturbation_s = debut_perturbation_s + duree_perturbation_s
                params_perturb = {
                    "mode_commande_perturbation": mode_commande_perturbation,
                    "valeur_resistance_ohm": params["valeur_resistance_ohm"],
                    "facteur_couplage_perturbation": self.facteur_couplage_perturbation,
                }
                puissance_resistance_active = convertir_commande_perturbation_vers_puissance(commande_perturbation, params_perturb)

                for _ in range(calculs_par_actualisation):
                    if temps_ecoule >= temps_total_s:
                        break

                    if constante_temps_tec_s > 0:
                        self.puissance_tec_effective += (
                            puissance_tec_cible - self.puissance_tec_effective
                        ) * coeff_lag_tec
                    else:
                        self.puissance_tec_effective = puissance_tec_cible

                    ajout_temp_tec = self.puissance_tec_effective * gain_temperature_tec

                    perturbation_active = (
                        duree_perturbation_s > 0.0
                        and debut_perturbation_s <= temps_ecoule < fin_perturbation_s
                    )
                    puissance_resistance_cible = puissance_resistance_active if perturbation_active else 0.0

                    if self.constante_temps_perturbation_s > 0:
                        self.puissance_resistance_effective += (
                            puissance_resistance_cible - self.puissance_resistance_effective
                        ) * coeff_lag_resistance
                    else:
                        self.puissance_resistance_effective = puissance_resistance_cible

                    ajout_temp_resistance = self.puissance_resistance_effective * gain_temperature_resistance

                    centre = matrice_T[1:-1, 1:-1]
                    suiv = matrice_T_suivante[1:-1, 1:-1]
                    np.copyto(suiv, centre)

                    np.multiply(centre, -2.0, out=tampon_secondaire)

                    np.add(matrice_T[1:-1, 2:], matrice_T[1:-1, :-2], out=tampon_diffusion)
                    np.add(tampon_diffusion, tampon_secondaire, out=tampon_diffusion)
                    np.multiply(tampon_diffusion, cst_diffusion_x, out=tampon_diffusion)
                    suiv += tampon_diffusion

                    np.add(matrice_T[2:, 1:-1], matrice_T[:-2, 1:-1], out=tampon_diffusion)
                    np.add(tampon_diffusion, tampon_secondaire, out=tampon_diffusion)
                    np.multiply(tampon_diffusion, cst_diffusion_y, out=tampon_diffusion)
                    suiv += tampon_diffusion

                    np.subtract(centre, temperature_ambiante, out=tampon_diffusion)
                    np.multiply(tampon_diffusion, cst_perte_convection, out=tampon_diffusion)
                    suiv -= tampon_diffusion

                    matrice_T_suivante[zone_tec] += ajout_temp_tec
                    matrice_T_suivante[zone_res] += ajout_temp_resistance

                    matrice_T_suivante[0, :] = matrice_T_suivante[1, :]
                    matrice_T_suivante[-1, :] = matrice_T_suivante[-2, :]
                    matrice_T_suivante[:, 0] = matrice_T_suivante[:, 1]
                    matrice_T_suivante[:, -1] = matrice_T_suivante[:, -2]

                    matrice_T, matrice_T_suivante = matrice_T_suivante, matrice_T
                    temps_ecoule += pas_temps

                historique_temps.append(temps_ecoule)
                historique_T1.append(matrice_T[idx_y_T1, idx_x_T1])
                historique_T2.append(matrice_T[idx_y_T2, idx_x_T2])
                historique_T3.append(matrice_T[idx_y_T3, idx_x_T3])

                progression = int((temps_ecoule / temps_total_s) * 100)
                if progression != dernier_progression:
                    self.progress_signal.emit(progression)
                    dernier_progression = progression
                compteur_images += 1
                if compteur_images % max(1, int(params["intervalle_affichage"])) == 0:
                    horodatage_ui = time.perf_counter()
                    if (horodatage_ui - dernier_emit_ui) >= intervalle_min_emission_ui_s or temps_ecoule >= temps_total_s:
                        self.update_signal.emit(
                            temps_ecoule,
                            matrice_T.copy(),
                            matrice_T[idx_y_T1, idx_x_T1],
                            matrice_T[idx_y_T2, idx_x_T2],
                            matrice_T[idx_y_T3, idx_x_T3],
                        )
                        dernier_emit_ui = horodatage_ui

            resultats_finaux = {"temps": historique_temps, "T1": historique_T1, "T2": historique_T2, "T3": historique_T3}
            if temps_ecoule >= temps_total_s:
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
        geometrie_ecran = obtenir_geometrie_ecran_disponible(self)
        self._petit_ecran = geometrie_ecran.width() < 1366 or geometrie_ecran.height() < 820

        dialog = QMessageBox(self)
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
            self.setGeometry(calculer_geometrie_fenetre_initiale(geometrie_ecran))

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
        self._plein_ecran_actif = False
        self._fullscreen_transition_active = False
        self._geometrie_avant_plein_ecran = None
        self._dernier_rendu_ui = 0.0
        self._signature_taille_ecran = None
        self._intervalle_min_rendu_ui_s = 1.0 / (24.0 if self._petit_ecran else 30.0)

        positions_couleurs = np.linspace(0.0, 1.0, 5)
        valeurs_rgb = np.array([
            [68, 1, 84, 255],     
            [49, 104, 142, 255],  
            [200, 70, 150, 255],  
            [255, 100, 100, 255], 
            [255, 0, 0, 255]   
        ], dtype=np.ubyte)
        self.palette_couleurs = pg.ColorMap(positions_couleurs, valeurs_rgb)
        self._palette_lookup = self.palette_couleurs.getLookupTable(0.0, 1.0, 256, alpha=True).astype(np.float32) / 255.0
        self._couleurs_capteurs = np.array([
            [59/255, 130/255, 246/255, 1.0],
            [245/255, 158/255, 11/255, 1.0],
            [16/255, 185/255, 129/255, 1.0]
        ], dtype=np.float32)

        widget_central = QWidget()
        self.setCentralWidget(widget_central)
        layout_principal = QVBoxLayout(widget_central)
        separateur_principal = QSplitter(Qt.Orientation.Horizontal)
        separateur_principal.setChildrenCollapsible(False)
        self.separateur_principal = separateur_principal
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
        self.labels_parametres = {}
        self.consigne_fixee_C = 35.0
        self._mode_commande_tec_ui = "watt"
        self._mode_commande_perturbation_ui = "voltage"
        self.chemin_calibration_auto = AUTO_CALIBRATION_JSON
        self._horodatage_calibration_auto = None
        
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
                "debut_perturbation_s": 0.0, "duree_perturbation_s": 150.0,
                "facteur_couplage_perturbation": 0.85,
                "constante_temps_perturbation_s": 8.0
            },
            "Commande TEC / Fit PWM": {
                "facteur_couplage_tec": 0.60,
                "constante_temps_tec_s": 8.0,
                "coef_pwm_a0": 1.734031e-02,
                "coef_pwm_a1": 1.406312e-01,
                "coef_pwm_a2": 9.947817e-04,
                "coef_pwm_a3": 1.703277e-05,
            },
        }

        libelles_parametres = {
            "puissance_tec_W": "Puissance TEC (W)",
            "facteur_couplage_tec": "Gain TEC",
            "constante_temps_tec_s": "Constante temps TEC (s)",
            "coef_pwm_a0": "Fit PWM→W : a0",
            "coef_pwm_a1": "Fit PWM→W : a1",
            "coef_pwm_a2": "Fit PWM→W : a2",
            "coef_pwm_a3": "Fit PWM→W : a3",
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
            "debut_perturbation_s": "Début perturbation (s)",
            "duree_perturbation_s": "Durée perturbation (s)",
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
                self.labels_parametres[cle_variable] = label_param
                
                plages = {
                    "puissance_tec_W": (-10, 10), "consigne_C": (-20, 100),
                    "facteur_couplage_tec": (0, 2), "constante_temps_tec_s": (0, 80),
                    "coef_pwm_a0": (-2, 2), "coef_pwm_a1": (-0.2, 0.2), "coef_pwm_a2": (-0.01, 0.01), "coef_pwm_a3": (-0.001, 0.001),
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
                    "valeur_resistance_ohm": (1, 100), "tension_resistance_V": (0, 30),
                    "debut_perturbation_s": (0, 1000), "duree_perturbation_s": (0, 1000),
                    "facteur_couplage_perturbation": (0, 2), "constante_temps_perturbation_s": (0, 60)
                }
                
                min_v, max_v = plages.get(cle_variable, (-1000, 1000))
                utiliser_scientifique = ("e" in str(valeur_defaut).lower()) or (cle_variable in {"coef_pwm_a2", "coef_pwm_a3"})
                if cle_variable in {"coef_pwm_a2", "coef_pwm_a3"}:
                    decimales = 3
                elif cle_variable in {"coef_pwm_a0", "coef_pwm_a1"}:
                    decimales = 4
                else:
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
        self.champs_saisie["puissance_tec_W"].value_input.editingFinished.connect(self.actualiser_controle_live)
        for cle_perturb in ("tension_resistance_V", "valeur_resistance_ohm", "debut_perturbation_s", "duree_perturbation_s"):
            self.champs_saisie[cle_perturb].slider.valueChanged.connect(self.actualiser_controle_live)
            self.champs_saisie[cle_perturb].value_input.editingFinished.connect(self.actualiser_controle_live)
        for champ in self.champs_saisie.values():
            champ.slider.valueChanged.connect(self.mettre_a_jour_indicateur_stabilite)
            champ.value_input.editingFinished.connect(self.mettre_a_jour_indicateur_stabilite)
        for cle_fit in ("puissance_tec_W", "facteur_couplage_tec", "constante_temps_tec_s", "coef_pwm_a0", "coef_pwm_a1", "coef_pwm_a2", "coef_pwm_a3"):
            self.champs_saisie[cle_fit].slider.valueChanged.connect(self.actualiser_resume_commande_tec)
            self.champs_saisie[cle_fit].value_input.editingFinished.connect(self.actualiser_resume_commande_tec)
            if cle_fit != "puissance_tec_W":
                self.champs_saisie[cle_fit].slider.valueChanged.connect(self.actualiser_controle_live)
                self.champs_saisie[cle_fit].value_input.editingFinished.connect(self.actualiser_controle_live)
        
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

        ligne_mode_commande = QHBoxLayout()
        ligne_mode_commande.setSpacing(8)

        label_mode_commande = QLabel("Commande TEC")
        label_mode_commande.setStyleSheet("font-weight: bold; color: #7DD3FC;")
        ligne_mode_commande.addWidget(label_mode_commande)

        self.combo_mode_commande_tec = FullscreenSafeComboBox()
        self.combo_mode_commande_tec.addItem("Watts (direct)", "watt")
        self.combo_mode_commande_tec.addItem("PWM (%) via fit", "pwm")
        self.combo_mode_commande_tec.setStyleSheet("QComboBox { background-color: #1E293B; color: #38BDF8; border: 1px solid #334155; border-radius: 4px; padding: 4px 8px; combobox-popup: 0; } QComboBox QAbstractItemView { background-color: #0F172A; color: #E2E8F0; border: 1px solid #334155; selection-background-color: #0EA5E9; }")
        ligne_mode_commande.addWidget(self.combo_mode_commande_tec, 1)

        self.combo_degre_fit_pwm = FullscreenSafeComboBox()
        self.combo_degre_fit_pwm.addItem("1er degré", 1)
        self.combo_degre_fit_pwm.addItem("2e degré", 2)
        self.combo_degre_fit_pwm.addItem("3e degré (équation actuelle)", 3)
        self.combo_degre_fit_pwm.setCurrentIndex(2)
        self.combo_degre_fit_pwm.setStyleSheet("QComboBox { background-color: #1E293B; color: #FDE68A; border: 1px solid #334155; border-radius: 4px; padding: 4px 8px; combobox-popup: 0; } QComboBox QAbstractItemView { background-color: #0F172A; color: #E2E8F0; border: 1px solid #334155; selection-background-color: #0EA5E9; }")
        ligne_mode_commande.addWidget(self.combo_degre_fit_pwm)

        label_mode_perturb = QLabel("Perturbation")
        label_mode_perturb.setStyleSheet("font-weight: bold; color: #FCA5A5;")
        ligne_mode_commande.addWidget(label_mode_perturb)

        self.combo_mode_commande_perturbation = FullscreenSafeComboBox()
        self.combo_mode_commande_perturbation.addItem("Volts + R", "voltage")
        self.combo_mode_commande_perturbation.addItem("Watts (direct)", "watt")
        self.combo_mode_commande_perturbation.setStyleSheet("QComboBox { background-color: #1E293B; color: #FCA5A5; border: 1px solid #334155; border-radius: 4px; padding: 4px 8px; combobox-popup: 0; } QComboBox QAbstractItemView { background-color: #0F172A; color: #E2E8F0; border: 1px solid #334155; selection-background-color: #EF4444; }")
        ligne_mode_commande.addWidget(self.combo_mode_commande_perturbation)

        self.combo_mode_commande_tec.currentIndexChanged.connect(self.actualiser_mode_commande_tec)
        self.combo_mode_commande_perturbation.currentIndexChanged.connect(self.actualiser_mode_commande_perturbation)
        self.combo_degre_fit_pwm.currentIndexChanged.connect(self.actualiser_resume_commande_tec)
        self.combo_degre_fit_pwm.currentIndexChanged.connect(self.actualiser_controle_live)

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

        self.label_resume_commande_tec = QLabel()
        self.label_resume_commande_tec.setWordWrap(True)
        self.label_resume_commande_tec.setStyleSheet(
            "background-color: rgba(15, 23, 42, 0.55); border: 1px solid #475569; "
            "border-radius: 6px; padding: 8px; color: #C4B5FD; font-size: 11px;"
        )
        
        layout_controles.addLayout(ligne_boutons_fichiers)
        layout_controles.addLayout(ligne_mode_commande)
        layout_controles.addLayout(ligne_boutons_simulation)
        layout_controles.addWidget(self.bouton_quicksave)
        layout_controles.addWidget(self.barre_progression)
        layout_controles.addWidget(self.label_stabilite)
        layout_controles.addWidget(self.label_resume_commande_tec)
        layout_gauche.addWidget(cadre_controles)

        # === PANNEAU DROIT (Graphiques) ===
        panneau_droit = QWidget()
        panneau_droit.setObjectName("RightPanel")
        layout_droit = QVBoxLayout(panneau_droit)
        layout_droit.setContentsMargins(10, 10, 10, 10)
        layout_droit.setSpacing(10)
        separateur_graphiques = QSplitter(Qt.Orientation.Vertical)
        separateur_graphiques.setChildrenCollapsible(False)
        self.separateur_graphiques = separateur_graphiques
        
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
        self.label_ressources.setMinimumWidth(160)
        self.label_ressources.setMinimumHeight(52)
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

        if OPENGL_DISPONIBLE:
            self.grille_3d = gl.GLGridItem()
            self.grille_3d.scale(10, 10, 10)
            self.vue_3d.addItem(self.grille_3d)

            self.axes_3d = gl.GLAxisItem()
            self.axes_3d.setSize(x=61.5, y=117.5, z=25.0)
            self.axes_3d.translate(-30.75, 0.0, 0.0)
            self.vue_3d.addItem(self.axes_3d)
            
            self.surface_thermique = gl.GLSurfacePlotItem(computeNormals=True, smooth=True, shader='shaded')
            self.surface_thermique.setGLOptions('opaque')
            test_data = np.ones((20, 20), dtype=np.float32) * 20.0
            test_x = np.linspace(0, 100, 20)
            test_y = np.linspace(0, 100, 20)
            test_colors = np.zeros((20, 20, 4), dtype=np.float32)
            for i in range(20):
                ratio = i / 19.0
                test_colors[i, :] = self.palette_couleurs.map(ratio) / 255.0
            self.surface_thermique.setData(x=test_x, y=test_y, z=test_data, colors=test_colors)
            self.vue_3d.addItem(self.surface_thermique)

            self.scatter_capteurs = gl.GLScatterPlotItem(size=12, pxMode=True)
            self.scatter_capteurs.setGLOptions('translucent')
            self.vue_3d.addItem(self.scatter_capteurs)
        else:
            self.grille_3d = _NullGLItem()
            self.axes_3d = _NullGLItem()
            self.surface_thermique = _NullGLItem()
            self.scatter_capteurs = _NullGLItem()

        layout_3d_h.addWidget(self.vue_3d, stretch=1)

        container_legende = QWidget()
        self._container_legende = container_legende
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
        self.graphique_2d.setClipToView(True)
        self.graphique_2d.setDownsampling(auto=True, mode='peak')
        
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
        
        self.combo_vitesse = FullscreenSafeComboBox()
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
        self.adapter_disposition_aux_ecrans(force=True)
        self.actualiser_mode_commande_tec(initialisation=True)
        self.actualiser_mode_commande_perturbation(initialisation=True)
        self.actualiser_resume_commande_tec()
        self.mettre_a_jour_indicateur_stabilite()
        self.mettre_a_jour_axes_3d_stables()
        self.mettre_a_jour_legende_axes_3d()

        self.timer_ressources = QTimer(self)
        self.timer_ressources.timeout.connect(self.mettre_a_jour_ressources_systeme)
        self.timer_ressources.start(1000)
        self.mettre_a_jour_ressources_systeme()

        self.timer_calibration_auto = QTimer(self)
        self.timer_calibration_auto.timeout.connect(self.verifier_mise_a_jour_calibration_auto)
        self.timer_calibration_auto.start(AUTO_CALIBRATION_CHECK_INTERVAL_MS)
        self.charger_calibration_auto(force=True, silencieux=True)

    def recuperer_parametres_interface(self):
        params = {cle: champ.value() for cle, champ in self.champs_saisie.items()}
        params["consigne_C"] = self.consigne_fixee_C
        params["mode_commande_tec"] = self.obtenir_mode_commande_tec()
        params["mode_commande_perturbation"] = self.obtenir_mode_commande_perturbation()
        params["degre_fit_pwm"] = self.obtenir_degre_fit_pwm()
        params["commande_tec_valeur"] = float(params["puissance_tec_W"])
        params["puissance_tec_W"] = convertir_commande_tec_vers_puissance(params["commande_tec_valeur"], params)
        params["pwm_tec_pct"] = convertir_puissance_vers_pwm(params["puissance_tec_W"], params)
        params["commande_perturbation_valeur"] = float(params["tension_resistance_V"])
        params["puissance_perturbation_W"] = convertir_commande_perturbation_vers_puissance(params["commande_perturbation_valeur"], params)
        return params

    def obtenir_mode_commande_tec(self):
        if hasattr(self, "combo_mode_commande_tec"):
            return normaliser_mode_commande_tec(self.combo_mode_commande_tec.currentData())
        return "watt"

    def obtenir_mode_commande_perturbation(self):
        if hasattr(self, "combo_mode_commande_perturbation"):
            return normaliser_mode_commande_perturbation(self.combo_mode_commande_perturbation.currentData())
        return "voltage"

    def obtenir_degre_fit_pwm(self):
        if hasattr(self, "combo_degre_fit_pwm"):
            return normaliser_degre_fit_pwm(self.combo_degre_fit_pwm.currentData())
        return 2

    def actualiser_mode_commande_tec(self, *_args, initialisation=False):
        mode_nouveau = self.obtenir_mode_commande_tec()
        mode_ancien = getattr(self, "_mode_commande_tec_ui", mode_nouveau)
        champ_commande = self.champs_saisie.get("puissance_tec_W")
        label_commande = self.labels_parametres.get("puissance_tec_W")

        if champ_commande is None:
            return

        params_fit = {cle: champ.value() for cle, champ in self.champs_saisie.items()}
        params_fit["degre_fit_pwm"] = self.obtenir_degre_fit_pwm()
        params_fit["mode_commande_tec"] = mode_ancien

        valeur_actuelle = champ_commande.value()
        puissance_equivalente = convertir_commande_tec_vers_puissance(valeur_actuelle, params_fit)

        if mode_nouveau == "pwm":
            nouvelle_valeur = convertir_puissance_vers_pwm(puissance_equivalente, params_fit)
            champ_commande.configure_range(-100.0, 100.0, decimals=1, scientific=False, current_val=nouvelle_valeur)
            if label_commande is not None:
                label_commande.setText("Commande TEC (PWM %)")
        else:
            champ_commande.configure_range(-10.0, 10.0, decimals=2, scientific=False, current_val=puissance_equivalente)
            if label_commande is not None:
                label_commande.setText("Puissance TEC (W)")

        self._mode_commande_tec_ui = mode_nouveau
        self.actualiser_resume_commande_tec()
        if not initialisation:
            self.actualiser_controle_live()

    def actualiser_mode_commande_perturbation(self, *_args, initialisation=False):
        mode_nouveau = self.obtenir_mode_commande_perturbation()
        mode_ancien = getattr(self, "_mode_commande_perturbation_ui", mode_nouveau)
        champ_commande = self.champs_saisie.get("tension_resistance_V")
        label_commande = self.labels_parametres.get("tension_resistance_V")
        champ_resistance = self.champs_saisie.get("valeur_resistance_ohm")

        if champ_commande is None:
            return

        params_perturb = {cle: champ.value() for cle, champ in self.champs_saisie.items()}
        params_perturb["mode_commande_perturbation"] = mode_ancien
        valeur_actuelle = champ_commande.value()
        puissance_equivalente = convertir_commande_perturbation_vers_puissance(valeur_actuelle, params_perturb)

        if mode_nouveau == "watt":
            champ_commande.configure_range(0.0, 20.0, decimals=2, scientific=False, current_val=puissance_equivalente)
            if label_commande is not None:
                label_commande.setText("Puissance perturbation (W)")
            if champ_resistance is not None:
                champ_resistance.setEnabled(False)
        else:
            nouvelle_tension = convertir_puissance_vers_tension_perturbation(puissance_equivalente, params_perturb)
            champ_commande.configure_range(0.0, 30.0, decimals=2, scientific=False, current_val=nouvelle_tension)
            if label_commande is not None:
                label_commande.setText("Tension résistance (V)")
            if champ_resistance is not None:
                champ_resistance.setEnabled(True)

        self._mode_commande_perturbation_ui = mode_nouveau
        self.actualiser_resume_commande_tec()
        if not initialisation:
            self.actualiser_controle_live()

    def actualiser_resume_commande_tec(self, *_args):
        if not hasattr(self, "label_resume_commande_tec"):
            return

        params = {cle: champ.value() for cle, champ in self.champs_saisie.items()}
        params["mode_commande_tec"] = self.obtenir_mode_commande_tec()
        params["mode_commande_perturbation"] = self.obtenir_mode_commande_perturbation()
        params["degre_fit_pwm"] = self.obtenir_degre_fit_pwm()

        commande = float(self.champs_saisie["puissance_tec_W"].value())
        puissance_equivalente = convertir_commande_tec_vers_puissance(commande, params)
        pwm_equivalent = convertir_puissance_vers_pwm(puissance_equivalente, params)

        a0 = float(params.get("coef_pwm_a0", 0.0))
        a1 = float(params.get("coef_pwm_a1", 0.0))
        a2 = float(params.get("coef_pwm_a2", 0.0))
        a3 = float(params.get("coef_pwm_a3", 0.0))
        degre = self.obtenir_degre_fit_pwm()
        if degre == 1:
            texte_modele = f"P ≈ {a0:.3f} + {a1:.4f}|PWM|"
        elif degre == 2:
            texte_modele = f"P ≈ {a0:.3f} + {a1:.4f}|PWM| + {a2:.5f}|PWM|²"
        else:
            texte_modele = f"P ≈ {a0:.3f} + {a1:.4f}|PWM| + {a2:.5f}|PWM|² + {a3:.6f}|PWM|³"

        if params["mode_commande_tec"] == "pwm":
            resume = f"Mode PWM : {commande:+.1f} % ≈ {puissance_equivalente:+.2f} W équiv."
        else:
            resume = f"Mode Watts : {commande:+.2f} W ≈ {pwm_equivalent:+.1f} % PWM"

        gain_tec = float(params.get("facteur_couplage_tec", 1.0))
        tau_tec = float(params.get("constante_temps_tec_s", 0.0))
        commande_perturb = float(self.champs_saisie["tension_resistance_V"].value())
        puissance_perturb = convertir_commande_perturbation_vers_puissance(commande_perturb, params)
        if params["mode_commande_perturbation"] == "watt":
            resume_perturb = f"Perturbation : {commande_perturb:.2f} W directs"
        else:
            resistance = float(params.get("valeur_resistance_ohm", 0.0))
            resume_perturb = f"Perturbation : {commande_perturb:.2f} V → {puissance_perturb:.2f} W (R={resistance:.1f} Ω)"

        self.label_resume_commande_tec.setText(
            resume + "\n" + texte_modele + f" | gain TEC={gain_tec:.2f}, τ={tau_tec:.1f}s" + "\n" + resume_perturb
        )

    def obtenir_ram_processus_mo(self):
        try:
            psutil = __import__("psutil")
            return psutil.Process().memory_info().rss / (1024 ** 2)
        except Exception:
            pass

        if sys.platform.startswith("win"):
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
        else:
            try:
                import resource
                utilisation = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                return utilisation / (1024 ** 2) if sys.platform == "darwin" else utilisation / 1024.0
            except Exception:
                pass

        return 0.0

    def mettre_a_jour_ressources_systeme(self):
        maintenant = time.perf_counter()
        temps_cpu = time.process_time()

        delta_temps = max(maintenant - self._horodatage_cpu_precedent, 1e-9)
        delta_cpu = max(temps_cpu - self._temps_cpu_precedent, 0.0)
        nb_coeurs = max(os.cpu_count() or 1, 1)
        cpu_percent = min(100.0, max(0.0, 100.0 * delta_cpu / (delta_temps * nb_coeurs)))
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
        params_valides["mode_commande_tec"] = normaliser_mode_commande_tec(params.get("mode_commande_tec", "watt"))
        params_valides["mode_commande_perturbation"] = normaliser_mode_commande_perturbation(params.get("mode_commande_perturbation", "voltage"))
        params_valides["degre_fit_pwm"] = normaliser_degre_fit_pwm(params.get("degre_fit_pwm", 2))
        params_valides["commande_tec_valeur"] = float(params.get("commande_tec_valeur", params.get("puissance_tec_W", 0.0)))
        params_valides["pwm_tec_pct"] = float(params.get("pwm_tec_pct", convertir_puissance_vers_pwm(params_valides["puissance_tec_W"], params_valides)))
        params_valides["commande_perturbation_valeur"] = float(params.get("commande_perturbation_valeur", params.get("tension_resistance_V", 0.0)))
        params_valides["puissance_perturbation_W"] = float(params.get("puissance_perturbation_W", convertir_commande_perturbation_vers_puissance(params_valides["commande_perturbation_valeur"], params_valides)))

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
        if params_valides["commande_perturbation_valeur"] < 0:
            raise ValueError("La commande de perturbation doit être positive ou nulle.")
        if params_valides["facteur_couplage_perturbation"] < 0:
            raise ValueError("Le facteur de couplage de la perturbation doit être positif ou nul.")
        if params_valides["constante_temps_perturbation_s"] < 0:
            raise ValueError("La constante de temps de la perturbation doit être positive ou nulle.")
        if params_valides["debut_perturbation_s"] < 0:
            raise ValueError("Le début de la perturbation doit être positif ou nul.")
        if params_valides["duree_perturbation_s"] < 0:
            raise ValueError("La durée de la perturbation doit être positive ou nulle.")
        if params_valides["facteur_couplage_tec"] < 0:
            raise ValueError("Le facteur de couplage TEC doit être positif ou nul.")
        if params_valides["constante_temps_tec_s"] < 0:
            raise ValueError("La constante de temps TEC doit être positive ou nulle.")
        if params_valides["mode_commande_tec"] == "pwm" and abs(params_valides["commande_tec_valeur"]) > 100:
            raise ValueError("Le PWM TEC doit rester entre -100 % et 100 %.")

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

    def appliquer_parametres_dict(self, parametres, afficher_message=False, source_label="JSON"):
        if not isinstance(parametres, dict):
            raise ValueError("Le JSON doit contenir un objet de paramètres valide.")

        if "mode_commande_tec" in parametres and hasattr(self, "combo_mode_commande_tec"):
            mode = normaliser_mode_commande_tec(parametres.get("mode_commande_tec", "watt"))
            index_mode = self.combo_mode_commande_tec.findData(mode)
            if index_mode >= 0:
                self.combo_mode_commande_tec.setCurrentIndex(index_mode)

        if "mode_commande_perturbation" in parametres and hasattr(self, "combo_mode_commande_perturbation"):
            mode_perturb = normaliser_mode_commande_perturbation(parametres.get("mode_commande_perturbation", "voltage"))
            index_mode_perturb = self.combo_mode_commande_perturbation.findData(mode_perturb)
            if index_mode_perturb >= 0:
                self.combo_mode_commande_perturbation.setCurrentIndex(index_mode_perturb)

        if "degre_fit_pwm" in parametres and hasattr(self, "combo_degre_fit_pwm"):
            degre = normaliser_degre_fit_pwm(parametres.get("degre_fit_pwm", 2))
            index_degre = self.combo_degre_fit_pwm.findData(degre)
            if index_degre >= 0:
                self.combo_degre_fit_pwm.setCurrentIndex(index_degre)

        nb_parametres_importes = 0
        champs_invalides = []
        for cle, valeur in parametres.items():
            if cle == "commande_tec_valeur":
                cle_cible = "puissance_tec_W"
            elif cle == "commande_perturbation_valeur":
                cle_cible = "tension_resistance_V"
            else:
                cle_cible = cle
            if cle_cible == "consigne_C":
                try:
                    self.consigne_fixee_C = float(valeur)
                    nb_parametres_importes += 1
                except (TypeError, ValueError):
                    champs_invalides.append(cle)
            elif cle_cible in self.champs_saisie:
                try:
                    self.champs_saisie[cle_cible].setValue(float(valeur))
                    nb_parametres_importes += 1
                except (TypeError, ValueError):
                    champs_invalides.append(cle)

        if nb_parametres_importes == 0:
            raise ValueError("Aucun paramètre reconnu n'a été trouvé dans le fichier.")

        self.actualiser_controle_live()
        try:
            self.statusBar().showMessage(f"Paramètres mis à jour depuis {source_label}", 4000)
        except Exception:
            pass

        if afficher_message and champs_invalides:
            QMessageBox.warning(
                self,
                "Import partiel",
                "Certaines valeurs ont été ignorées : " + ", ".join(champs_invalides)
            )

        return nb_parametres_importes

    def charger_calibration_auto(self, force=False, silencieux=True):
        chemin = Path(getattr(self, "chemin_calibration_auto", AUTO_CALIBRATION_JSON))
        if not chemin.exists():
            return False

        try:
            horodatage = chemin.stat().st_mtime
        except OSError:
            return False

        dernier_horodatage = getattr(self, "_horodatage_calibration_auto", None)
        if not force and dernier_horodatage is not None and horodatage <= dernier_horodatage:
            return False

        try:
            with open(chemin, 'r', encoding='utf-8') as fichier:
                donnees = json.load(fichier)
            parametres = donnees.get("parametres", donnees)
            self.appliquer_parametres_dict(parametres, afficher_message=not silencieux, source_label=chemin.name)
            self._horodatage_calibration_auto = horodatage
            return True
        except (OSError, json.JSONDecodeError, ValueError) as erreur:
            if not silencieux:
                QMessageBox.critical(self, "Erreur", f"Impossible de lire le fichier : {erreur}")
            return False

    def verifier_mise_a_jour_calibration_auto(self):
        self.charger_calibration_auto(force=False, silencieux=True)

    def importer_parametres_json(self):
        chemin_fichier, _ = QFileDialog.getOpenFileName(self, "Importer Paramètres", "", "Fichiers JSON (*.json)")
        if chemin_fichier:
            try:
                with open(chemin_fichier, 'r', encoding='utf-8') as fichier:
                    donnees = json.load(fichier)
                parametres = donnees.get("parametres", donnees)
                self.appliquer_parametres_dict(parametres, afficher_message=True, source_label=Path(chemin_fichier).name)
                try:
                    self._horodatage_calibration_auto = Path(chemin_fichier).stat().st_mtime
                except OSError:
                    pass
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
        self.thread_simulation.finished.connect(self.thread_simulation.deleteLater)
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
            
    def actualiser_controle_live(self, *_args):
        params_interface = self.recuperer_parametres_interface()
        self.actualiser_resume_commande_tec()
        self.mettre_a_jour_indicateur_stabilite()
        if self.simulation_en_cours():
            mode_pid = False
            puiss = params_interface["puissance_tec_W"]
            cons = self.consigne_fixee_C
            tens = params_interface["tension_resistance_V"]
            gain_tec = params_interface.get("facteur_couplage_tec", 1.0)
            tau_tec = params_interface.get("constante_temps_tec_s", 0.0)
            debut_perturb = params_interface.get("debut_perturbation_s", 0.0)
            duree_perturb = params_interface.get("duree_perturbation_s", params_interface.get("temps_total_s", 0.0))
            mode_perturb = params_interface.get("mode_commande_perturbation", "voltage")
            self.thread_simulation.modifier_parametres_controle(mode_pid, puiss, cons, tens, gain_tec, tau_tec, debut_perturb, duree_perturb, mode_perturb)

    def actualiser_graphiques(self, temps_sim, matrice_temperatures_3d, temp_T1, temp_T2, temp_T3):
        self.donnees_temps.append(temps_sim)
        self.donnees_y_t1.append(temp_T1)
        self.donnees_y_t2.append(temp_T2)
        self.donnees_y_t3.append(temp_T3)
        self.historique_matrices_3D.append(np.asarray(matrice_temperatures_3d, dtype=np.float16))

        maintenant = time.perf_counter()
        index_maximum = len(self.historique_matrices_3D) - 1
        rendu_force = index_maximum <= 1 or not self.mode_direct_actif
        autoriser_rendu = rendu_force or ((maintenant - self._dernier_rendu_ui) >= self._intervalle_min_rendu_ui_s)

        if autoriser_rendu:
            self.courbe_t1.setData(self.donnees_temps, self.donnees_y_t1, skipFiniteCheck=True)
            self.courbe_t2.setData(self.donnees_temps, self.donnees_y_t2, skipFiniteCheck=True)
            self.courbe_t3.setData(self.donnees_temps, self.donnees_y_t3, skipFiniteCheck=True)

        self.slider_timeline.setEnabled(True)
        self.btn_play_pause.setEnabled(True)
        self.combo_vitesse.setEnabled(True)
        self.slider_timeline.blockSignals(True)
        self.slider_timeline.setMaximum(index_maximum)

        if self.mode_direct_actif:
            self.slider_timeline.setValue(index_maximum)
            if autoriser_rendu:
                self.dessiner_rendu_3d(matrice_temperatures_3d, temps_sim, temp_T1, temp_T2, temp_T3)
                self._dernier_rendu_ui = maintenant
            self.curseur_temps_2d.hide()

        self.slider_timeline.blockSignals(False)

    def naviguer_dans_historique(self, index):
        if not self.historique_matrices_3D:
            return
        
        index_maximum = len(self.historique_matrices_3D) - 1
        self.mode_direct_actif = (index == index_maximum)
        
        matrice_historique = np.asarray(self.historique_matrices_3D[index], dtype=np.float32)
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

    def adapter_disposition_aux_ecrans(self, force=False):
        if not hasattr(self, "separateur_principal") or not hasattr(self, "separateur_graphiques"):
            return

        geometrie = obtenir_geometrie_ecran_disponible(self)
        largeur_fenetre = max(1, self.width() or geometrie.width())
        hauteur_fenetre = max(1, self.height() or geometrie.height())
        petit_ecran = (
            largeur_fenetre < 1280 or hauteur_fenetre < 760
            or geometrie.width() < 1366 or geometrie.height() < 820
        )
        signature = (
            largeur_fenetre,
            hauteur_fenetre,
            petit_ecran,
            self.est_en_mode_plein_ecran() if hasattr(self, "est_en_mode_plein_ecran") else False,
        )

        if not force and getattr(self, "_signature_taille_ecran", None) == signature:
            return

        self._signature_taille_ecran = signature
        self._petit_ecran = petit_ecran
        self._intervalle_min_rendu_ui_s = 1.0 / (20.0 if petit_ecran else 30.0)

        largeur_gauche = int(round(largeur_fenetre * (0.34 if petit_ecran else 0.27)))
        largeur_gauche = max(300, min(430, largeur_gauche))
        largeur_droite = max(420, largeur_fenetre - largeur_gauche)
        self.separateur_principal.setSizes([largeur_gauche, largeur_droite])

        hauteur_haut = int(round(hauteur_fenetre * (0.57 if petit_ecran else 0.62)))
        hauteur_haut = max(240, min(max(260, hauteur_fenetre - 180), hauteur_haut))
        hauteur_bas = max(180, hauteur_fenetre - hauteur_haut)
        self.separateur_graphiques.setSizes([hauteur_haut, hauteur_bas])

        if hasattr(self, "_container_legende"):
            self._container_legende.setFixedWidth(68 if petit_ecran else 80)
        if hasattr(self, "barre_controles_vue"):
            self.barre_controles_vue.setMaximumWidth(270 if petit_ecran else 360)
        if hasattr(self, "combo_vitesse"):
            self.combo_vitesse.setMaximumWidth(72 if petit_ecran else 80)

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

    def _verrouiller_transition_plein_ecran(self, delai_ms=250):
        self._fullscreen_transition_active = True
        QTimer.singleShot(delai_ms, lambda: setattr(self, "_fullscreen_transition_active", False))

    def _fermer_popups_combo(self):
        for nom in ("combo_mode_commande_tec", "combo_degre_fit_pwm", "combo_mode_commande_perturbation", "combo_vitesse"):
            combo = getattr(self, nom, None)
            if combo is not None:
                try:
                    combo.hidePopup()
                except Exception:
                    pass

    def rafraichir_apres_plein_ecran(self):
        self.mettre_a_jour_bouton_plein_ecran()
        try:
            self.adapter_disposition_aux_ecrans(force=True)
            self.appliquer_mode_camera()
            self.mettre_a_jour_axes_3d_stables()
            self.mettre_a_jour_legende_axes_3d()
            if hasattr(self, "vue_3d"):
                self.vue_3d.update()
            if hasattr(self, "graphique_2d"):
                self.graphique_2d.repaint()
            self.repaint()
        except Exception:
            pass

    def est_en_mode_plein_ecran(self):
        return bool(getattr(self, "_plein_ecran_actif", False) or self.isFullScreen())

    def mettre_a_jour_bouton_plein_ecran(self):
        est_en_plein_ecran = self.est_en_mode_plein_ecran()
        if hasattr(self, "bouton_exit_fullscreen"):
            self.bouton_exit_fullscreen.setVisible(est_en_plein_ecran)
        if hasattr(self, "bouton_fullscreen"):
            self.bouton_fullscreen.setVisible(not est_en_plein_ecran)

    def passer_en_plein_ecran(self):
        if self._fullscreen_transition_active or self.est_en_mode_plein_ecran():
            self.mettre_a_jour_bouton_plein_ecran()
            return

        self._verrouiller_transition_plein_ecran(320)
        self._fermer_popups_combo()
        self._geometrie_avant_plein_ecran = self.geometry()

        geometrie = obtenir_geometrie_ecran_disponible(self)

        self.setUpdatesEnabled(False)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.show()
        self.setGeometry(geometrie)
        self.showMaximized()
        self._plein_ecran_actif = True
        self.raise_()
        self.activateWindow()
        QTimer.singleShot(80, lambda: self.setUpdatesEnabled(True))
        QTimer.singleShot(100, self.rafraichir_apres_plein_ecran)

    def quitter_plein_ecran(self):
        if self._fullscreen_transition_active or not self.est_en_mode_plein_ecran():
            self.mettre_a_jour_bouton_plein_ecran()
            return

        self._verrouiller_transition_plein_ecran(320)
        self._fermer_popups_combo()

        geometrie = self._geometrie_avant_plein_ecran
        self.setUpdatesEnabled(False)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, False)
        self.showNormal()
        if geometrie is not None:
            self.setGeometry(geometrie)
        self._plein_ecran_actif = False
        self.raise_()
        self.activateWindow()
        QTimer.singleShot(80, lambda: self.setUpdatesEnabled(True))
        QTimer.singleShot(100, self.rafraichir_apres_plein_ecran)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape and self.est_en_mode_plein_ecran():
            self.quitter_plein_ecran()
            event.accept()
            return
        if event.key() == Qt.Key.Key_F11:
            if self.est_en_mode_plein_ecran():
                self.quitter_plein_ecran()
            else:
                self.passer_en_plein_ecran()
            event.accept()
            return
        super().keyPressEvent(event)

    def changeEvent(self, event):
        super().changeEvent(event)
        self.mettre_a_jour_bouton_plein_ecran()
        if self.isVisible() and not getattr(self, "_fullscreen_transition_active", False):
            QTimer.singleShot(0, self.rafraichir_apres_plein_ecran)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.isVisible() and not getattr(self, "_fullscreen_transition_active", False):
            self.adapter_disposition_aux_ecrans(force=False)

    def nettoyer_apres_simulation(self):
        self.bouton_demarrer.setEnabled(True)
        self.bouton_pause.setEnabled(False)
        self.bouton_pause.setText("PAUSE")
        self.bouton_pause.setStyleSheet("")
        self.bouton_arreter.setEnabled(False)
        self.bouton_quicksave.setEnabled(False)
        self.bouton_quicksave.setText("QUICKSAVE (Pause requise)")
        if self.thread_simulation is not None and not self.thread_simulation.isRunning():
            self.thread_simulation = None
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

        titre_live = f"T={temps_sim:.1f}s  |  T1 (Bleu): {t1:.1f}°C  |  T2 (Orange): {t2:.1f}°C  |  T3 (Vert): {t3:.1f}°C"
        self.graphique_2d.setTitle(titre_live, color='#38BDF8', size='11pt')

        if not OPENGL_DISPONIBLE:
            return
        
        matrice_z_T = np.asarray(matrice_temperatures_3d, dtype=np.float32).T
        matrice_normalisee = np.clip((matrice_z_T - temp_min) / (temp_max - temp_min), 0.0, 1.0)
        indices_palette = np.clip(np.rint(matrice_normalisee * 255.0), 0, 255).astype(np.uint8)
        couleurs_calculees = self._palette_lookup[indices_palette]
        
        matrice_z = (matrice_z_T - temp_min) * self.exageration_z
        self.surface_thermique.setData(x=self.grille_x, y=self.grille_y, z=matrice_z, colors=couleurs_calculees)
        self.ajuster_camera_3d(matrice_z)

        p = self.params_actuels if self.params_actuels else self.recuperer_parametres_interface()

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
        
        self.scatter_capteurs.setData(pos=points_capteurs, color=self._couleurs_capteurs)

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
    try:
        QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
    except Exception:
        pass

    if os.environ.get("SIMULATEUR_FORCE_SOFTWARE_OPENGL", "").strip().lower() in {"1", "true", "yes", "on"}:
        try:
            QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseSoftwareOpenGL, True)
        except Exception:
            pass

    app = QApplication(sys.argv)
    fenetre_principale = MainWindow()
    fenetre_principale.show()
    if getattr(fenetre_principale, "demarrer_en_plein_ecran", False):
        QTimer.singleShot(0, fenetre_principale.passer_en_plein_ecran)
    sys.exit(app.exec())