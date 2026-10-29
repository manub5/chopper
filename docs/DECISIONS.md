# Décisions techniques (et pourquoi)

## Détection des temps et du premier temps de mesure : beat_this, pas madmom
- madmom : dernière version PyPI 0.16.1, qui ne gère que Python < 3.10 et
  numpy < 1.20 ; installation seulement depuis GitHub. Ses modèles sont sous
  licence non commerciale (CC BY-NC-SA) — gênant pour un logiciel prêté.
- beat_this (même labo, CPJKU, ISMIR 2024) : détecte temps et premiers temps
  de mesure sans post-traitement probabiliste ; code et modèles sous MIT.
- Contrepartie : dépend de PyTorch (installation lourde). On l'appelle sans
  l'option `dbn` pour ne pas dépendre de madmom.
- Incertitude : précision non vérifiée sur ambient/musiques sans percussions.
  À tester sur des morceaux réels dès l'étape 2 de la ROADMAP.

## Attaques, séparation percussif/harmonique, tempo : librosa 0.11.0
- Version stable du 11/03/2025, bibliothèque de référence, maintenue.

## Interface : PySide6
- Qt natif, cohérent sous KDE, sans navigateur ni serveur.
- Licence LGPL (compatible avec un prêt/diffusion).
- Riche et extensible : répond au besoin d'« élaborations futures ».

## Cache SQLite
- La bibliothèque peut être très grande : on mémorise les analyses
  (clé = chemin + taille + date de modification) pour ne jamais recalculer.

## uv pour l'environnement Python
- Un seul fichier `pyproject.toml` + verrou `uv.lock` : installation
  identique chez une autre personne.

## Installation de beat_this depuis PyPI, pas depuis l'archive GitHub
- Le paquet `beat-this` (même code, mêmes auteurs CPJKU) est aussi publié sur
  PyPI depuis la version 1.1.0, en plus de l'installation `pip install
  https://github.com/CPJKU/beat_this/archive/main.zip` documentée dans leur
  README. Les deux installent le même module `beat_this`.
- On utilise la version PyPI (`beat-this>=1.1.0`) : plus stable (numéro de
  version figé, pas "main" qui peut changer), et n'exige pas d'accès à
  `github.com` au moment de l'installation.
- Les poids du modèle, eux, se téléchargent automatiquement au premier lancement
  depuis le cloud de la JKU (`cloud.cp.jku.at`), pas depuis GitHub.

## Roues CPU de PyTorch par défaut
- `torch`/`torchaudio` installés depuis l'index CPU officiel
  (`download.pytorch.org/whl/cpu`, voir `[tool.uv.index]` dans
  `pyproject.toml`) plutôt que les roues par défaut de PyPI, qui embarquent
  ~2,5 Go de bibliothèques CUDA même sans GPU NVIDIA.
- Le logiciel reste utilisable sans GPU (voir portabilité dans AGENTS.md).
  Sur une machine avec GPU NVIDIA, réinstaller `torch`/`torchaudio` avec les
  roues CUDA correspondantes (voir pytorch.org/get-started/locally) pour
  accélérer l'analyse.

## Paquet distribuable (étape 11) : pas encore de paquet autonome
- `docs/ROADMAP.md` reporte explicitement ce choix ("à décider à ce
  moment-là"). Ce qui est fait pour l'instant : `pyproject.toml` produit un
  paquet Python standard, validé avec `uv build` (`choppeur-0.1.0.tar.gz` +
  `.whl`), avec le point d'entrée `choppeur = choppeur.app:main`.
- Installation actuelle chez la personne à qui le logiciel est prêté :
  `uv sync && uv run choppeur` (déjà documenté dans README.md), qui suppose
  `uv` installé chez elle.
- Non fait : un exécutable autonome (ex. PyInstaller) qui embarquerait
  PySide6 + PyTorch. C'est notoirement fragile à mettre au point (taille,
  compatibilité GPU/CPU selon la machine cible) ; le choix concret de l'outil
  dépend de la machine de la personne à qui le logiciel sera prêté, donc
  reporté comme prévu par la ROADMAP plutôt que décidé arbitrairement ici.

## Installation facilitée (niveau 2) : script `install.sh` + lanceur `./choppeur`
- Public visé : personne extérieure au projet, à l'aise pour coller une
  commande dans un terminal, mais pas développeuse. Livraison par archive zip
  (fabriquée de notre côté) que la personne décompresse ; le script est inclus
  dedans.
- Choix parmi trois niveaux discutés : (1) `uv sync` manuel (confirmé/
  développeur), (2) script d'installation semi-automatique, (3) paquet binaire
  autonome type PyInstaller. Le niveau 2 est retenu : bon rapport entre
  simplicité pour l'utilisateur et charge de maintenance. Le niveau 3 (binaire
  figé) reste reporté, cf. étape 11 de la ROADMAP.
- Ce que le script fait : contrôle Linux, installe `uv` si absent, vérifie/
  installe `ffmpeg` et `libportaudio2` via `sudo apt-get` (ces paquets étant
  systèmes, un `sudo` interactif est assumé et accepté), lance `uv sync`,
  puis génère un lanceur `./choppeur`.
- Effets de bord au compte utilisateur (documentés, pas cachés) : `uv` installé
  dans `~/.local/bin` ; paquets système via sudo ; ~2 Go téléchargés.

## Outillage qualité (groupe `dev` de `pyproject.toml`)
- `ruff` (lint + format, `line-length = 110`), `mypy` (avec `src/choppeur/py.typed`),
  `bandit` (sécurité, seuil `-ll` ; B404 sur l'import de `subprocess` accepté).
- `pre-commit` lance à chaque commit : hooks du modèle personnel (pre-commit-hooks,
  semgrep `--config auto`, gitleaks, refus des chemins perso), puis ruff, mypy,
  bandit et toute la suite pytest.
- Le hook git n'est pas versionné : `uv run pre-commit install` après un clone.

## Préécoute : lecture unique du candidat coché
- La préécoute joue le candidat coché (sinon la ligne courante), une seule fois,
  pour entendre exactement le segment qui sera exporté.

## Dialogues de fichiers sous KDE : portail du bureau
- Sous KDE, `app.py` force `QT_QPA_PLATFORMTHEME=xdgdesktopportal` (sauf choix
  explicite) pour que les dialogues voient les dossiers réseau montés.

Historique détaillé des bugs corrigés et de leurs causes : `docs/HISTORIQUE.md`.
