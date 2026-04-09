# Simulation-plaque-thermique

La simulation de la plaque thermique du prototype pour le cours GPH-2104. 
Permet de voir comment l'énergie thermique du TEC et de la perturbation se propage à 
travers la surface de la plaque. Le simulateur permet aussi de surveiller la progression 
temporelle de la température à trois points différents et de sauvegarder les données sur votre machine. 

La remise utilise le fichier [SimulateurUpgrade.py](SimulateurUpgrade.py) qui contient l'entièreté du simulateur.

Pour la documentation du simulateur utilisé pour la remise : [click here](docUpgraded.md)

## Gestion des librairies avec uv

Ce projet utilise `uv` pour garder les librairies synchronisées et versionnées dans Git.

### Installation de uv (Windows PowerShell)

```powershell
irm https://astral.sh/uv/install.ps1 | iex
```

Si `uv` n'est pas reconnu tout de suite, fermer et rouvrir son terminal.

### Installation des dependances du projet

Dans la racine du repo:

```powershell
uv sync
```

Cette commande créé `.venv/` localement (ignoree par Git) et installe les versions verrouillées dans `uv.lock`.

### Ajouter une nouvelle librairie

```powershell
uv add nom-librairie
```

Ensuite, faire un commit de ces fichiers:

- `pyproject.toml`
- `uv.lock`

### Version simplifiée du simulateur

Il existe aussi une version simplifiée du simulateur ayant les mêmes fonctions, mais un interface beaucoup moins compliquée.

Pour la documentation de la version simple du simulateur : [click](LegacyEdition/docClassic.md)
