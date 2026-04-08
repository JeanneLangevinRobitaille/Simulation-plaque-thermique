**1. À l'ouverture du repo**

Le fichier principal contenant le simulateur est *SimulateurClassic.py*. Avant tout, il 
faut s'assurer que les bonnes librairies sont installée sur votre machine :

- numpy
- matplotlib
- tkinter
- json

Pour activer le simulateur, il faut exécuter le fichier *SimulateurClassic.py* soit 
avec une commande du terminal ou en appuyant sur le bouton d'exécution de votre IDE.

**2. L'interface**

Afin de faciliter l'interaction avec le simulateur, un interface est inclue pour servir 
comme centre de contrôle. Dès que le simulateur est activé, la fenêtre de l'interface 
apparaît sur l'écran. Celle-ci contient les paramètres de simulation ainsi que les boutons de commande. 
Des paramètres communs sont présente dans l'interface par défaut, mais ils peuvent être changés en cliquant 
sur les lignes de texte et en utilisant le clavier. Les boutons de contrôle sont similairement interactifs et 
ils contrôlent les fonctions majeures du simulateur. Les deux prochaines sections expliquent en plus grand détails 
chacunes des caractéristiques de l'interface.

**3. Les paramètres**

La simulation fonctionne avec une grande variété de paramètres qui définissent la nature 
de la plaque, de ses intrants et des points d'intérêt. Tous les paramètres peuvent être 
changés avant de lancer une nouvelle simulation, sauf la puissance intrante, qui elle peut 
être changée plusieurs fois dans une même simulation.

Les paramètres sont les suivants :

- Paramètres de la plaque
  - Longueur : en mm, la longueur du plus long côté de la plaque
  - Largeur : en mm, la largeur du plus petit côté de la plaque
  - Épaisseur : en mm, l'épaisseur de la plaque en métal
- Paramètres de la simulation
  - Puissance entrée : en watts, la puissance fourni par le TEC à la plaque 
  - Temps simulation : en secondes, le temps de simulation voulu
  - Résolution : un nombre entier $$N$$, le nombre de cellules totales de la plaque sera $$N^2$$
  - Température ambiante : en °C, la température de la pièce ou la température initale de la plaque
  - Saut d'image : un nombre entier $$N$$, donne le nombre de calculs effectués avant que la simulation 
  se mette à jour
- Paramètres physiques
 - $$\alpha$$ : la diffusivité thermique en $$\text{mm}^2/s$$, la capacité au matériau à transferer la 
 chaleur
 - $$\rho$$ : la densité du matériau en $$\text{kg}^2/\text{mm}^3$$
 - $$c_p$$ : la capacité calorifique massique du matériau en $$\text{J}/\text{mg}\cdot\text{K}$$, la 
 capacité au matériau à stocker la chaleur
 - $$h$$ : le coefficient de convection en $$\text{W}^2/\text{mm}^2\cdot\text{K}$$, l'intensité du 
 transfert de chaleur entre la plaque et son environnement
- Coordonnées d'intérêt (assume que (0,0) se trouve au centre du petit bord de la plaque)
  - TEC : en mm, les coordonnées de l'actuateur thermoélectrique
  - T1 : en mm, position de la première thermistance
  - T2 : en mm, position de la deuxième thermistance
  - T3 : en mm, position de la troisème thermistance
- Perturbation
  - Position : en mm, la position de la résistance perturbative
  - Résistance : en ohms, la valeur de résistance de la perturbation
  - Tension : en volts, la tension constante appliquée à la résistance perturbative

**4. Les boutons**

Après avoir entré les paramètres voulus dans l'interface, le bouton *Simulate* active la simulation. Une 
fenêtre secondaire apparait à côté de l'interface qui contient une représentation 3D de la plaque 
ainsi qu'un graphique pour les données de température à travers le temps de T1, T2 et T3. À n'importe 
quel moment, le bouton *Pause/Resume* met la simulation sur pause et la résume lorsqu'il est utilisé une 
seconde fois. Lorsque la simulation est figée, il est possible de changer la valeur de **Puissance entrée** et **Tension**. Le bouton *Save* ouvre une fenêtre du système de fichier de la machine et permet de sauvegarder les données de la simulation sous la forme d'un fichier JSON. Le bouton *Input* fait la même chose que *Save*, sauf avec un fichier JSON qui
contient une liste de paramètres. Ceux-ci sont automatiquement intégrés dans l'interface. Un fichier 
exemple *testparams.json* est inclue avec le repo à fin d'exemple. Finalement, le bouton *Exit* ferme l'application.