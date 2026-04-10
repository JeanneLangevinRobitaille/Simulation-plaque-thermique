# Guide complet — Simulation plaque thermique

Ce document explique **la structure du projet**, **le rôle des principaux fichiers**, **le fonctionnement général du code** et **l’utilisation de l’interface** du simulateur.

---

## 1. But du projet

Le projet `Simulation-plaque-thermique` sert à :

- simuler la propagation thermique dans une plaque;
- injecter une commande **TEC**;
- ajouter une **perturbation thermique**;
- visualiser l’évolution des températures sur la surface et aux capteurs `T1`, `T2`, `T3`;
- calibrer les paramètres du modèle à partir de données expérimentales;
- sauvegarder / recharger les paramètres et résultats en `JSON`.

Le fichier principal du simulateur est :

- `SimulateurUpgrade.py`

---

## 2. Structure du projet

| Fichier / dossier | Rôle |
|---|---|
| `SimulateurUpgrade.py` | Application principale PyQt6 : interface, simulation, graphiques, rendu 3D/2D, import/export JSON |
| `calibration_thermique_combinee.py` | Outil de calibration thermique combinée et d’optimisation du modèle `PWM → W` |
| `parametres_calibres_combinee.json` | Paramètres calibrés sauvegardés; peut être relu automatiquement par le simulateur |
| `README.md` | Présentation rapide du repo et installation |
| `docUpgraded.md` | Documentation utilisateur plus ancienne / plus simple |
| `LegacyEdition/` | Ancienne version simplifiée du simulateur |
| `TestsAndData/` | Données d’essais, CSV expérimentaux, quicksaves et jeux de paramètres |

---

## 3. Installation et lancement

### Dépendances
Le projet utilise Python `3.11+` avec notamment :

- `numpy`
- `pandas`
- `scipy`
- `pyqt6`
- `pyqtgraph`
- `pyopengl`
- `matplotlib`

### Installation
Depuis la racine du projet :

```powershell
uv sync
```

### Lancer le simulateur

```powershell
& ".venv\Scripts\python.exe" "SimulateurUpgrade.py"
```

### Lancer l’outil de calibration

```powershell
& ".venv\Scripts\python.exe" "calibration_thermique_combinee.py"
```

Sans argument, la calibration ouvre directement une interface Tkinter.

---

## 4. Vue d’ensemble du fonctionnement du code

Le projet est séparé en **deux grands blocs**.

### A. Le simulateur (`SimulateurUpgrade.py`)
Il gère :

1. les widgets d’interface;
2. la lecture des paramètres;
3. la validation des bornes physiques / numériques;
4. la boucle de simulation thermique;
5. l’affichage temps réel de la plaque et des courbes;
6. l’import/export `JSON`;
7. le rechargement automatique des paramètres calibrés.

### B. La calibration (`calibration_thermique_combinee.py`)
Elle sert à :

1. lire les CSV expérimentaux;
2. détecter les essais de perturbation et les essais TEC PWM;
3. ajuster les coefficients thermiques;
4. ajuster le modèle reliant `PWM` et `puissance équivalente (W)`;
5. écrire un `JSON` de paramètres recommandés.

---

## 5. Architecture de `SimulateurUpgrade.py`

Les éléments principaux sont les suivants.

### 5.1 `SliderWithValue`
Petit widget personnalisé utilisé partout dans le panneau de gauche.

Il combine :
- un **slider horizontal**;
- un **champ texte**;
- une synchronisation entre les deux.

Il sert à modifier rapidement un paramètre tout en gardant une valeur précise.

### 5.2 `FullscreenSafeComboBox`
ComboBox personnalisée pour que les menus déroulants restent utilisables même en **plein écran**.

Elle gère :
- la position du popup;
- le focus;
- le comportement lorsque l’utilisateur clique rapidement plusieurs fois.

### 5.3 Fonctions utilitaires importantes
Le fichier contient plusieurs helpers pour :

- normaliser les modes (`watt`, `pwm`, `voltage`);
- convertir `PWM ↔ W`;
- convertir une commande de perturbation en puissance;
- calculer les bornes de température;
- vérifier la stabilité numérique du schéma.

### 5.4 `SimulationThread`
C’est le cœur du calcul.

Ce thread séparé :
- exécute la simulation sans bloquer l’interface;
- applique la commande TEC;
- applique la perturbation thermique;
- met à jour `T1`, `T2`, `T3`;
- envoie régulièrement les résultats à l’UI via des signaux Qt.

### 5.5 `MainWindow`
C’est la fenêtre principale.

Elle construit :
- le panneau de contrôle à gauche;
- le rendu 3D / 2D de la plaque;
- les courbes de température;
- la timeline de relecture;
- les boutons de contrôle (`DÉMARRER`, `PAUSE`, `ARRÊTER`, etc.).

---

## 6. Paramètres principaux du simulateur

Les paramètres sont regroupés par catégories.

### 6.1 Contrôle thermique
- `puissance_tec_W` : commande TEC principale
- mode TEC :
  - `Watts (direct)`
  - `PWM (%) via fit`
- degré du fit PWM : `1`, `2` ou `3`

### 6.2 Paramètres de la plaque
- `longueur_y_mm`
- `largeur_x_mm`
- `epaisseur_mm`

### 6.3 Paramètres de simulation
- `temps_total_s`
- `resolution_grille`
- `temperature_ambiante_C`
- `intervalle_affichage`

### 6.4 Paramètres physiques
- `diffusivite_alpha`
- `masse_volumique_rho`
- `chaleur_massique_cp`
- `coeff_convection_h`

### 6.5 Positions
- position du `TEC`
- positions des capteurs `T1`, `T2`, `T3`
- position de la perturbation

### 6.6 Perturbation
La perturbation peut maintenant être commandée de deux façons :

- `Volts + R` : la puissance est déduite de la tension et de la résistance;
- `Watts (direct)` : la puissance de perturbation est entrée directement.

On peut aussi choisir :
- `debut_perturbation_s` : moment où la perturbation commence;
- `duree_perturbation_s` : durée pendant laquelle elle est appliquée.

---

## 7. Utilisation de l’interface utilisateur (UI)

## 7.1 Partie gauche : panneau de contrôle
C’est ici qu’on prépare la simulation.

### Étapes normales d’utilisation
1. régler les dimensions et propriétés de la plaque;
2. choisir la commande TEC (`Watts` ou `PWM`);
3. choisir le mode de perturbation (`Volts + R` ou `Watts`);
4. définir le temps total de simulation;
5. cliquer sur `DÉMARRER`.

### Boutons principaux
- `DÉMARRER` : lance une nouvelle simulation
- `PAUSE` : fige temporairement le calcul
- `REPRENDRE` : continue après une pause
- `ARRÊTER` : stoppe la simulation en cours
- `IMPORTER JSON` : charge des paramètres depuis un fichier
- `SAUVER JSON` : exporte les paramètres et résultats
- `QUICKSAVE` : sauvegarde rapide des données pendant une pause

### Résumé des commandes
Une zone de résumé affiche l’équivalence actuelle, par exemple :
- conversion `PWM → W` du TEC;
- gain et constante de temps du TEC;
- résumé de la perturbation active.

---

## 7.2 Partie droite : visualisation
La zone de droite montre plusieurs vues.

### Surface thermique
Elle représente la plaque et l’évolution spatiale de la température.

### Graphique des capteurs
Trois courbes affichent :
- `T1`
- `T2`
- `T3`

### Timeline
Une barre de temps permet de :
- revenir en arrière;
- relire l’évolution comme une vidéo;
- observer un instant précis après la simulation.

### Vues et caméra
On peut :
- passer entre `vue 2D` et `vue 3D`;
- utiliser le plein écran (`F11`);
- quitter le plein écran avec `Échap`.

---

## 8. Import / export JSON

Le simulateur sait importer un `JSON` contenant soit :

- directement les paramètres;
- ou une structure du type :

```json
{
  "parametres": { ... },
  "resultats": {
    "temps": [...],
    "T1": [...],
    "T2": [...],
    "T3": [...]
  }
}
```

### Auto-rechargement
Le simulateur surveille aussi automatiquement :

- `parametres_calibres_combinee.json`

Ainsi, après une calibration, les nouveaux paramètres peuvent être repris au prochain chargement ou automatiquement si le fichier est mis à jour.

---

## 9. Calibration : à quoi sert `calibration_thermique_combinee.py`

Ce script lit les essais expérimentaux et essaie d’ajuster le modèle pour mieux coller à la réalité.

### Deux modes importants

#### `combined`
Calibre ensemble :
- la plaque;
- la perturbation;
- la réponse TEC.

#### `pwm-model`
Optimise surtout la loi :
- `PWM (%) → puissance équivalente (W)`

Ce mode garde les paramètres thermiques figés autant que possible et ajuste surtout les coefficients du modèle PWM.

### Interface GUI de calibration
L’interface permet de :
- choisir les dossiers de données;
- inclure ou non les essais de perturbation;
- inclure ou non les essais TEC;
- choisir le fichier JSON de sortie;
- lancer la calibration;
- afficher les logs et les RMSE.

### Commandes CLI utiles

```powershell
& ".venv\Scripts\python.exe" "calibration_thermique_combinee.py" --gui
```

```powershell
& ".venv\Scripts\python.exe" "calibration_thermique_combinee.py" --mode combined
```

```powershell
& ".venv\Scripts\python.exe" "calibration_thermique_combinee.py" --mode pwm-model --pwm-fit-degree 3
```

---

## 10. Workflow recommandé

### Pour une simple simulation
1. ouvrir `SimulateurUpgrade.py`;
2. ajuster les paramètres;
3. choisir le mode TEC;
4. choisir la perturbation;
5. lancer avec `DÉMARRER`;
6. observer `T1/T2/T3`;
7. sauvegarder si nécessaire.

### Pour améliorer la fidélité du modèle
1. lancer `calibration_thermique_combinee.py`;
2. choisir les dossiers de CSV;
3. exécuter la calibration;
4. générer `parametres_calibres_combinee.json`;
5. relancer ou recharger le simulateur.

---

## 11. Points importants à retenir

- Le simulateur sépare bien la **physique de la plaque** et la **couche de commande** du TEC.
- La loi `PWM → W` ne remplace pas les coefficients thermiques : elle sert seulement à traduire une consigne PWM en puissance équivalente.
- La perturbation peut être permanente ou temporisée.
- Les résultats affichés les plus utiles pour comparer aux mesures réelles sont souvent `T2` et `T3`.

---

## 12. Dépannage rapide

### Le simulateur ne démarre pas
- vérifier que `.venv` existe;
- lancer `uv sync` si nécessaire;
- utiliser le bon Python du projet.

### La simulation diverge
- réduire la résolution ou ajuster les paramètres physiques;
- vérifier l’indicateur de stabilité numérique.

### Les menus déroulants en fullscreen glitchent
- éviter de spammer trop rapidement;
- utiliser la dernière version de `SimulateurUpgrade.py`, qui inclut le correctif `FullscreenSafeComboBox`.

### Les résultats ne ressemblent pas à l’expérience
- refaire une calibration;
- vérifier les positions des capteurs;
- vérifier le mode TEC (`Watts` vs `PWM`) et le mode de perturbation.

---

## 13. Résumé court

Si vous ne devez retenir que trois choses :

1. **`SimulateurUpgrade.py`** = simulateur complet et interface.
2. **`calibration_thermique_combinee.py`** = outil pour ajuster le modèle aux données réelles.
3. **`parametres_calibres_combinee.json`** = passerelle entre calibration et simulation.

---

Si vous voulez, le prochain ajout possible est un **guide illustré section par section** avec captures d’écran de l’UI et exemples de réglages typiques.