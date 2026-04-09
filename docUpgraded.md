**1. À l'ouverture du repo**

Le fichier principal contenant le simulateur est *SimulateurUpgraded.py*. Avant tout, il 
faut s'assurer que les bonnes librairies sont installée sur votre machine. Il suffit de suivre les instruction du README pour télecharger toute les libraires.

Pour activer le simulateur, il faut exécuter le fichier [SimulateurUpgrade.py](SimulateurUpgrade.py) soit 
avec une commande du terminal ou en appuyant sur le bouton d'exécution de votre IDE.

**2. L'interface**

Un panneau à gauche donne accès à tous les paramètres importants de la simulation et un champ de texte aide à les changer selon les besoins de l'utilisateur. Une barre de défilement horizontale ainsi que l'utilisation de la roue de défilement occupent la même fonction, quoique plus grossièrement. Les paramètres utilisés dans les calculs se regroupent en plusieurs catégories, voir la section Paramètres

Afin de pouvoir simuler des changements dynamiques dans la puissance appliquée par le TEC et la perturbation de la résistance, les paramètres d'entrée du TEC et de la tension peuvent être ajustés continuellement pendant une simulation ; elle s'ajustera instantanément. En bas de ce panneau se trouvent le sélecteur de modes et les boutons de contrôle principaux. La simulation peut être utilisée en deux modes :

- PID automatique (consigne) :
- 

Les boutons de contrôle sont ce qui permettent d'envoyer les paramètres choisis aux processus de calcul du simulateur. Le bouton Démarrer en vert active la simulation, le bouton Pause en jaune la met sur pause et la réactive et le bouton Arrêter en rouge termine la simulation sans option de la réactiver. Le bouton Démarrer peut être appuyé une deuxième fois pour redémarrer la simulation zéro. Il y a aussi deux boutons qui facilitent la manipulation des données du simulateur. Ils sont Importer JSON qui intègre les paramètres d'un fichier JSON préparé et Sauver JSON, qui exporte les paramètres de la simulation ainsi que les données temporelles aux trois points d'intérêt dans un fichier JSON. Un bouton Quicksave sauvegarde aussi les données, mais seulement quand la simulation est mis sur pause. Lors de la simulation, une barre de progrès au bas de l'écran affiche le pourcentage de la simulation qui a été réalisé. 

À droite de l'écran, une surface montre l'évolution de la température sur la surface de la plaque et représente les thermistances par des points colorés. Ces points sont aussi représentés dans un graphique de température en fonction du temps qui est synchronisé avec la surface. Finalement, une barre de défilement permet d'observer rapidement l'évolution temporelle de la température de la même façon qu'une vidéo, ce qui facilite la révision de la simulation en préparation pour une autre. Un sélecteur de vitesse est aussi inclue à côté de cette barre de défilement, cependant elle n'affecte la simulation que très peu.

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
   - $$\rho$$ : la densité du matériau en $$\text{kg}/\text{mm}^3$$
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

  **4. Les fonctions**

  
