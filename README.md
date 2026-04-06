# Simulation-plaque-thermique

La simulation de la plaque thermique du prototype pour le cours GPH-2104. Permet de voir comment l'énergie thermique du TEC et de la perturbation se propage à travers la surface de la plaque. Le simulateur permet aussi de surveiller la progression temporelle de la température à trois points différents et de sauvegarder les données sur votre machine. 

**À l'ouverture du repo**

Lorsque le repositoire est ouvert pour la première fois, il devrait y avoir trois fichiers. Le fichier principal contenant le simulateur est *SimPlaqueInterface.py*. 

**Les paramètres**

La simulation fonctionne avec une grande variété de paramètres qui définissent la nature de la plaque, de ses intrants et des points d'intérêt. Tous les paramètres peuvent être changés avant de lancer une nouvelle simulation, sauf la puissance intrante, qui elle peut être changée plusieurs fois dans une même simulation.

Les paramètres sont les suivants :

- Paramètres de la plaque
  - Longueur :
  - Largeur :
  - Épaisseur :
- Paramètres de la simulation
  - Puissance entrée :
  - Temps simulation :
  - Résolution :
  - Température ambiante :
  - Saut d'image :
- Paramètres physiques
 - $$\alpha$$ :
 - $$\rho$$ :
 - $$c_p$$ : 
 - $$h$$ : 
- Coordonnées d'intérêt
  - TEC :
  - T1 :
  - T2 :
  - T3 :
- Perturbation
  - Position :
  - Résistance :
  - Tension :

**L'interface**

Afin de faciliter l'interaction avec le simulateur, un interface est inclue pour servir comme centre de contrôle.

**Utiliser le simulateur**

Après avoir entré les paramètres voulus dans l'interface, le bouton *GO* active la simulation. Une fenêtre secondaire apparait à côté de l'interface qui contient une représentation 3D de la plaque ainsi qu'un graphique pour les données de température à travers le temps de T1, T2 et T3. 

