# Simulation-plaque-thermique

La simulation de la plaque thermique du prototype pour le cours GPH-2104. 
Permet de voir comment l'énergie thermique du TEC et de la perturbation se propage à 
travers la surface de la plaque. Le simulateur permet aussi de surveiller la progression 
temporelle de la température à trois points différents et de sauvegarder les données sur votre machine. 

Pour la remise, nous vous recommandons d'utiliser la version courante, car son interface est bien plus conviviale. 
Celle-ci et la version simple du simulateur utilisent les mêmes calculs, mais la version simple est dotée d'un interface moins esthétique, bien qu'elle ait les mêmes fonctionalités

Pour la documentation de la version courante du simulateur : [click](docUpgraded.md)

Pour la documentation de la version simple du simulateur : [click](docClassic.md)

## Gestion des librairies avec uv

Ce projet utilise maintenant `uv` pour garder les librairies synchronisees et versionnees dans Git.

### Installation de uv (Windows PowerShell)

```powershell
irm https://astral.sh/uv/install.ps1 | iex
```

Si `uv` n'est pas reconnu tout de suite, ferme et rouvre ton terminal.

### Installation des dependances du projet

Dans la racine du repo:

```powershell
uv sync
```

Cette commande cree `.venv/` localement (ignoree par Git) et installe les versions verrouillees dans `uv.lock`.

### Ajouter une nouvelle librairie

```powershell
uv add nom-librairie
```

Ensuite commit ces fichiers:

- `pyproject.toml`
- `uv.lock`
