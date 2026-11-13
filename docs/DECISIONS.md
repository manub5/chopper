# Décisions techniques (et pourquoi)

Note de nommage au 02/11/2026 : les mentions Choppeur/`choppeur` ci-dessous
conservent le contexte historique. L'application actuelle s'appelle Chopper,
se lance avec `uv run chopper` et fournit `src/chopper/py.typed`.

## 07/11/2026 — Wayland natif par défaut après validation de l'interface

- Dans une session `XDG_SESSION_TYPE=wayland`, sans `QT_QPA_PLATFORM` non vide,
  sélectionner `wayland` avant de construire QApplication. Préserver toute
  sélection explicite (`xcb`, `wayland`, plugin de test ou autre) et laisser une
  session X11 inchangée. Le portail KDE et son choix explicite restent inchangés.
- XCB était un contournement d'artefacts de peinture observés sur certaines
  sessions KDE. Après validation des étapes visuelles, glisser et raccourcis,
  privilégier le protocole natif pour l'intégration Wayland ; conserver la commande
  `QT_QPA_PLATFORM=xcb uv run chopper` en secours, sans repli silencieux sur erreur.
- Contrôler le démarrage réel avec Qt natif et XCB sur données synthétiques,
  sans écrire dans les préférences/cache utilisateur. Une capture ne prouve pas
  l'absence d'artefacts pour tous pilotes ; lecture matérielle et dépôt Bitwig
  doivent faire partie de la validation utilisateur finale.

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

## Attaques et séparation percussif/harmonique : librosa 1.0
- Migration de `0.11.*` vers `1.0.*` le 29/10/2026 ; `uv.lock` fixe la
  version 1.0.0. Le tempo reste calculé à partir des beats de `beat_this`
  dans `core/rhythm.py`, pas par librosa.
- Version 1.0.0 publiée le 11/08/2026, disponibilité vérifiée sur PyPI et
  changements examinés dans la documentation officielle :
  https://pypi.org/pypi/librosa/1.0.0/json et
  https://librosa.org/doc/1.0.0/changelog.html.
- Les appels utilisés (`onset.onset_detect` avec `units="time"` et
  `effects.hpss`) restent compatibles : aucun changement du moteur requis.
  Le retrait du backend `audioread` dans librosa 1.0 ne concerne pas notre
  chargeur, qui utilise soundfile et ffmpeg. `uv lock --upgrade-package librosa`
  a uniquement mis à jour librosa et retiré audioread du verrou ; aucune autre
  version de dépendance n'a changé.
- Vérification avant migration : `uv run pytest -q`, 104 tests réussis.
  Après migration et ajout du test de calage décrit ci-dessous :
  `uv run pytest`, 108 tests réussis. Aucun échec lié à la migration, donc
  aucune correction du code métier nécessaire.
- Effets de bord : synchronisation de `.venv` sur le nouveau verrou ; aucun
  fichier audio source modifié. Les anciennes analyses du cache restent
  utilisables et ne sont pas recalculées automatiquement : le cache ne
  contient pas de version de librosa. La compatibilité testée ne garantit
  pas des résultats numériques identiques sur tous les morceaux réels.

## Vérification du rythme et de l'absence de madmom (29/10/2026)
- Analyse des imports Python de `src/` et `tests/` : aucun import de madmom.
  Aucun paquet madmom dans `uv.lock`, aucun module madmom chargé après
  import de `core.rhythm`, et paquet absent de l'environnement contrôlé.
- `core/rhythm.py` construit `File2Beats` avec `dbn=False` : le
  post-traitement DBN facultatif utilisant madmom n'est pas activé. Cela
  ne signifie pas que le code de la dépendance beat_this ne contient
  aucune référence à son option madmom.
- `analyze_rhythm()` récupère bien `(beats, downbeats)` et conserve les
  downbeats séparément. Le calage des boucles n'a pas lieu dans ce fichier :
  `gui/workers.analyze_track()` transmet `analysis.downbeat_times` à
  `core/candidates.find_loop_candidates()`, qui choisit chaque début dans
  cette liste, et non dans la liste de tous les beats.
- Test de non-régression ajouté dans `tests/test_workers.py` : de la sortie
  simulée du modèle jusqu'aux vrais candidats, avec beats toutes les 0,5 s
  et downbeats à 0,5 / 2,5 / 4,5 s. Vérification avec et sans réutilisation
  du cache, ainsi qu'en l'absence de downbeats (aucune boucle attendue).
  Seule l'inférence du modèle est remplacée ; le chargement audio,
  la conversion rythmique, librosa et la sélection des candidats sont réels.
- Vérification de sensibilité du test : substitution temporaire, en mémoire,
  des downbeats par tous les beats ; les quatre cas échouent. Cette mutation
  n'est pas une anomalie du code existant et ne modifie aucun fichier moteur.
  Ces vérifications caractérisent un comportement déjà correct ; aucune
  correction artificielle n'a été introduite pour obtenir un cycle rouge/vert.
- Limite inchangée : le début suit les downbeats, mais la fin utilise encore
  une durée médiane de mesure. Le calage des fins à tempo variable reste un
  problème distinct, non corrigé dans cette migration.

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

## 13/11/2026 — Archive de prêt traçable pour Kubuntu 26.04.1

- Format retenu : ZIP de sources et installateur, pas un binaire autonome.
  Une commande d'installation est acceptée par le destinataire ; Qt/PyTorch
  restent téléchargés dans un environnement local, poids du modèle au besoin.
- Construire uniquement depuis un état suivi propre. Lire les blobs du commit,
  jamais les fichiers audio/environnements/paramètres présents sur le disque.
  Nom `chopper-{version}-{sha12}-linux.zip`, commit complet dans `RELEASE.txt`,
  somme SHA-256 séparée ; aucune publication implicite.
- Liste blanche : sources Python et `py.typed` sous `src/chopper/`, installateur
  Bash et helper Desktop Entry, métadonnées/verrou/licence/README et deux guides
  utilisateur. Un fichier suivi inattendu sous les sources provoque un refus,
  plutôt qu'une inclusion silencieuse de secrets, audio ou caches. Les ressources
  d'un futur autre type devront être ajoutées explicitement après revue.
- Reproductibilité sur le même environnement de construction : dates ZIP fixes,
  ordre stable, modes Git conservés. Pas de garantie bit-à-bit entre versions
  différentes de zlib/Python. Les fichiers de sortie étrangers ou liens sont
  refusés, une sortie identique est conservée sans réécriture. Une erreur de
  publication nettoie seulement les sorties partielles créées par cet appel.
- Les petits scripts de construction et leurs appels Git lisent le dépôt sans
  shell ; les signalements Bandit faibles sur subprocess ne justifient pas de
  désactiver les hooks ou d'élargir les permissions.
- Test réel sur Kubuntu 26.04.1 toujours requis : architecture, installation
  fraîche, menu KDE, première analyse et périphérique audio. Aucun conteneur ou
  serveur ajouté pour contourner ce besoin ; ne pas prétendre ce test exécuté.

## Paquet distribuable (historique, avant l'archive de prêt) : pas de paquet autonome
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
