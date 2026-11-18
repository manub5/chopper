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

Cadrage et plan approuvés par l'utilisateur le 08/11/2026. Implémentation des
trois étapes et revue réalisées ; recette sur Kubuntu 26.04.1 et publication
restent soumises à validation utilisateur.

## Extension du 18/11/2026 — commande, Bureau, icône et désinstallation

### Périmètre accepté

L'utilisateur demande trois ajouts à cette distribution et accepte une
désinstallation limitée aux intégrations générées. Conserver l'installateur Bash,
le lanceur local et les outils Python standard ; pas de gestionnaire de paquets
supplémentaire, de service, de copie de l'application ou de modification audio.

- Proposer un lien `~/.local/bin/chopper` vers le lanceur `./chopper` du projet,
  pas une copie. Le lanceur doit résoudre ses liens avant de chercher `.venv`,
  transmettre les arguments intacts et fonctionner depuis un autre dossier.
- Proposer une copie du Desktop Entry dans le dossier obtenu par
  `xdg-user-dir DESKTOP`, sans supposer son nom ni sa langue. Fichier exécutable
  pour l'autorisation KDE ; ne pas ajouter un faux marqueur de confiance GNOME.
- Proposer une icône SVG dédiée, sobre, anthracite `#292B2E` et orange doux
  `#D99A64`, lisible en petite taille, sans script, police ni ressource distante.
  Source : `assets/chopper.svg`. Destination par défaut :
  `~/.local/share/icons/hicolor/scalable/apps/chopper.svg`. Comme le menu,
  respecter un `XDG_DATA_HOME` absolu lorsqu'il est configuré.
- Menu et Bureau utilisent l'icône installée ; si l'icône est refusée, garder une
  icône générique et ne pas installer un lien vers un SVG manquant. Le champ Icon
  peut porter son chemin absolu pour éviter une dépendance au cache du thème.
- Les quatre intégrations sont facultatives. Montrer chaque destination et les
  éventuels dossiers à créer avant confirmation, défaut non ; refus/EOF ne crée
  ni dossier, ni fichier, ni relevé d'installation pour cette action.

### Approche et preuve de propriété

Approche retenue lors du cadrage : étendre l'installateur et conserver un relevé
des fichiers effectivement créés. Une copie du lanceur global ne suivrait pas les
mises à jour ; un paquet système ou une modification des profils élargirait les
permissions et n'est pas demandé.

Choix du constructeur : relevé local `.chopper-install.json`, ignoré par Git et
exclu du ZIP, annoncé avant sa première écriture. Il identifie le projet, le rôle,
la destination, le type et l'identité du fichier/lien, son contenu ou sa cible et
ses permissions. Ne pas y stocker d'environnement complet, mot de passe ou secret.
Valider le relevé ; refuser un relevé étranger, mal formé ou symbolique.

Ne jamais écraser un fichier étranger, y compris un lien cassé ou un fichier
remplacé depuis l'installation. Réinstallation inchangée sans doublons ; mise à
jour uniquement d'un artefact dont la propriété est encore prouvée. Adoption d'un
ancien menu généré possible seulement si son contenu correspond exactement au
format historique et au même lanceur ; jamais sur son seul nom ou marqueur.
Les collisions et erreurs de disque/relevé ne doivent ni effacer un fichier
étranger ni annoncer un succès fictif ; nettoyer seulement les temporaires créés.

### Désinstallation acceptée

`bash uninstall.sh` présente les seuls artefacts encore attribuables à ce projet
et demande confirmation avant suppression, défaut non. Retirer uniquement lien
global, raccourcis menu/Bureau, icône et relevé devenus inutiles. Un artefact
modifié/remplacé est conservé et signalé. Une seconde désinstallation est sans
effet supplémentaire ; ne supprimer aucun dossier parent, même devenu vide.

Conserver le projet, le lanceur local, `.venv`, uv, les paquets système, profils,
préférences, caches d'analyse, audio et exports. Le retrait ne dépend pas d'une
installation Qt/PyTorch fonctionnelle ; Python standard suffit.

### PATH, KDE et recette

Le profil officiel Ubuntu Resolute ajoute `~/.local/bin` si ce dossier existe au
login ; ce n'est pas une garantie du PATH d'une session déjà ouverte. Vérifier le
PATH reçu au démarrage de l'installateur, avant tout ajout interne nécessaire à
uv. S'il manque : expliquer reconnexion et, pour le terminal courant seulement,
`export PATH="$HOME/.local/bin:$PATH"`. Ne jamais éditer un profil sans autre accord.

Tests isolés : HOME/XDG/PATH fictifs, aucun téléchargement/sudo réel, vrais
consommateurs Desktop Entry si disponibles, refus/collisions/liens cassés,
réinstallation et désinstallation conservatrices. Simuler un vrai `git pull`
local qui ne change que le code, puis relancer par commande/menu/Bureau sans
réinstaller : leurs destinations et le lanceur restent stables. Livrer les
nouveaux scripts et le SVG via la liste blanche de l'archive ; exclure le relevé.

Installation dans le compte réel seulement après consentement aux emplacements.
Recette finale : `cd /tmp && chopper`, menu des applications, icône du Bureau,
puis même parcours après mise à jour du seul code. Les tests automatisés ne
remplacent pas l'observation des clics KDE ni une écoute matérielle.

### Références officielles consultées le 18/11/2026

- Ubuntu 26.04/Resolute, profil Bash :
  https://git.launchpad.net/ubuntu/+source/bash/plain/debian/skel.profile?h=ubuntu/resolute
  (la même condition figure dans `/etc/skel/.profile` sur l'hôte Ubuntu 26.04.1).
- Ubuntu 26.04, `xdg-user-dir` et XDG_CONFIG_HOME :
  https://manpages.ubuntu.com/manpages/resolute/en/man1/xdg-user-dir.1.html
- KDE KConfig, `KDesktopFile::isAuthorizedDesktopFile` :
  https://invent.kde.org/frameworks/kconfig/-/raw/master/src/core/kdesktopfile.cpp
  (hors répertoires standard, droit d'exécution requis sauf propriétaire root,
  sous réserve des restrictions administratives KDE).
