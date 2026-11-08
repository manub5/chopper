# Distribution pour Kubuntu 26.04.1

## Objectif et choix retenu

Permettre de prêter Chopper à une personne non développeuse sous Kubuntu
26.04.1. Une commande à copier pour la première installation est acceptée.
Ensuite, lancement depuis le menu des applications KDE.

L'approche proposée et acceptée est une archive du projet avec l'installateur
existant, plutôt qu'un exécutable autonome. L'installation manuelle avec uv
reste disponible pour le développement. Un binaire autonome embarquant Qt et
PyTorch serait plus lourd à maintenir et reste hors périmètre. Aucun Flatpak,
Docker, serveur local ou changement du moteur audio.

## Livraison proposée

- Archive ZIP versionnée, produite depuis les fichiers suivis d'un commit propre
  et identifié, avec une somme SHA-256 et un dossier racine unique.
- Inclure sources, installateur, verrou de dépendances, licence et instructions
  utilisateur en anglais. Exclure Git, environnement Python, caches, secrets,
  paramètres utilisateur et fichiers audio personnels.
- Produire les livrables dans `dist/` du projet, déjà ignoré par Git.
- Ne pas publier de release GitHub sans autorisation distincte.

## Installation et lancement

- L'utilisateur choisit où décompresser l'archive et conserve ce dossier après
  installation : c'est l'emplacement de l'application, pas un dossier temporaire.
- Une commande `bash install.sh` depuis ce dossier prépare l'environnement local
  avec les versions verrouillées et sans les outils de développement.
- Conserver la vérification de ffmpeg/PortAudio et expliquer toute installation
  système avec sudo. Pas de sudo pour les fichiers de l'application.
- Environ 2 Go de téléchargements de dépendances, estimation à confirmer ; les
  poids d'analyse peuvent être téléchargés lors de la première analyse.
  Une installation entièrement hors ligne n'est pas promise.
- Conserver le lanceur `./chopper` et ajouter une entrée de menu KDE pointant
  vers ce lanceur. Respecter XDG ; proposer le dossier des applications de
  l'utilisateur et obtenir confirmation avant de le créer ou d'y écrire.
- Gérer correctement espaces et caractères spéciaux dans les chemins.
  Ne pas écraser un fichier ou lien étranger. Une réinstallation doit pouvoir
  actualiser uniquement les fichiers générés par Chopper.
- Documenter qu'un déplacement ultérieur du dossier nécessite de réinstaller
  le raccourci. Aucun téléchargement de dépendances au lancement normal.

## Sécurité, effets de bord et limites

L'installation peut télécharger uv et les dépendances, créer `.venv` dans le
dossier choisi, créer son lanceur et son raccourci après accord, et installer
les paquets système annoncés. L'accès réseau et les éventuelles modifications
du compte par l'installateur officiel uv doivent être signalés avant exécution.
Une erreur ne doit pas annoncer une installation réussie ; une reprise doit
préserver les fichiers étrangers. Aucun nettoyage automatique d'anciens dossiers.

Préférences et caches XDG existants restent inchangés par l'installateur ;
l'application conserve leur comportement actuel. Sources audio et exports
toujours préservés, glissers répétés toujours volontairement non idempotents.

## Vérification attendue

Tests isolés de l'installateur et du raccourci, sans installation système réelle :
réinstallation, refus d'écrasement, refus utilisateur, chemin avec espaces et
caractères spéciaux, dépendance manquante et erreur d'installation. Contrôler
le contenu de l'archive, sa somme et sa traçabilité, puis la suite de régression
et les contrôles statiques existants.

La compatibilité Kubuntu 26.04.1 et l'architecture de la machine destinataire
doivent être vérifiées sur la machine cible : ne pas les déduire des tests
simulés ni annoncer cette compatibilité comme acquise. Fournir une courte
recette manuelle d'installation, ouverture, première analyse et écoute réelle.

## État

Cadrage proposé, en attente d'approbation avant plan et implémentation.
