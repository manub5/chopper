# Chopper — panneaux, ouverture et traitement des échantillons

## But et limites

Accélérer la préparation d’échantillons depuis le gestionnaire de fichiers, la
ligne de commande et le tableau, sans changer les originaux. Garder PySide6,
pyqtgraph et le moteur indépendant de Qt. Ne pas réintroduire les doublons de
bibliothèque, les recherches simultanées dans une fenêtre ou l’écrasement des
exports lors d’un usage normal.

## Approche

Étendre les composants existants plutôt que créer une seconde interface ou un
second moteur de découpe. Faire converger l’ouverture par le menu, le dépôt et
la ligne de commande vers le même parcours. Réutiliser un seul rendu de sample
pour la préécoute et les exports ; ne pas recalculer le rythme pour changer la
vitesse d’un extrait. Utiliser librosa et son rééchantillonnage `soxr_hq`, déjà
disponibles, plutôt qu’ajouter un moteur de traitement ou préserver artificiellement
la hauteur en mode platine.

## 1. Panneaux et interactions avec le tracé

- Garder les proportions par défaut actuelles. Conserver la séparation
  horizontale de la bibliothèque et ajouter des séparations verticales
  déplaçables entre forme d’onde, rectangles et tableau. Préserver les minimums,
  le défilement et l’alignement temporel. Utiliser les curseurs Qt de
  redimensionnement horizontal ou vertical sur les séparateurs et les bords
  de colonnes ; curseur horizontal aussi pour les poignées de sélection sur l’onde.
- Un simple clic ailleurs sur la forme d’onde ne modifie ni la sélection ni les
  résultats et ne lance ni dialogue ni nouvelle préécoute. Les actions explicites
  de retour au morceau entier et les véritables gestes de sélection restent.

## 2. Ouverture, instances et dialogues

- Une commande ouvre une fenêtre indépendante. Vérifier que deux processus
  peuvent analyser et exporter en parallèle : pas de corruption du cache ou
  des préférences, ni d’écrasement des exports ordinaires. Si nécessaire, corriger
  uniquement les conflits observés. Une seule piste active par fenêtre.
- Déclarer Chopper comme application compatible avec les dossiers et les types
  audio pris en charge, sans le définir comme application par défaut. Le menu
  **Open With** de Dolphin lance une piste ou ouvre un dossier comme album ;
  ouvrir un album l’ajoute à la bibliothèque sans l’analyser automatiquement.
  Mettre à jour les raccourcis reconnus par l’installateur sans écraser les entrées
  étrangères. Aucun changement automatique des associations utilisateur.
- Accepter le dépôt de fichiers audio et de dossiers locaux, NAS montés compris,
  et les ajouter en bas de la bibliothèque sans déplacer ni copier les originaux.
  Le dépôt ajoute des entrées, ne remplace pas la piste active ; ignorer les
  doublons et signaler les éléments non pris en charge. Les pistes seules
  affichent leur nom ; les albums gardent leur chemin visible.
- Mémoriser entre les lancements le dernier emplacement accepté, séparément pour
  chaque usage de dialogue (bibliothèque, album, piste, export). L’annulation ne
  modifie rien. Si l’emplacement n’est plus disponible, revenir au comportement
  normal du sélecteur. Ne pas changer le dossier d’export configuré implicitement.

## 3. Commande et paramètres de découpe

- Garder `chopper` et `chopper <fichier>` compatibles, accepter aussi `chopper
  <dossier>` et les chemins relatifs au dossier d’appel. Documenter les options
  `--start`, `--end` (en secondes), `--bars`, `--one-shot-duration` (en secondes),
  `--max-samples` et `--export-dir`. En présence d’options de découpe, analyser
  et découper la piste avant d’afficher les résultats finaux dans la fenêtre.
  `--bars` règle les boucles et `--one-shot-duration` règle les one-shots ;
  ni l’une ni l’autre option ne désactive l’autre catégorie.
  Écrire des exports uniquement si `--export-dir` a été fourni. Rien de saisi en
  ligne de commande ne modifie les préférences. Rejeter les combinaisons et
  valeurs invalides clairement, sans export partiel dû à un argument invalide.
- Exposer les mêmes choix de longueur, **¼, ½, 1, 2 et 4 mesures**, dans
  **Settings** et **Length**. Conserver les deux rôles : les cases choisissent
  les longueurs automatiques, **Length** choisit une longueur pour la sélection
  courante. Ne pas activer 2 et 4 mesures par défaut ni modifier les choix existants.
- Remplacer **Max. one-shot length** par **One-shot duration (s)**. À partir de
  chaque attaque, prendre cette durée même si une autre attaque arrive entre-temps ;
  ne raccourcir qu’à la fin du morceau ou de la sélection, sans ajouter de silence.
  Garder la valeur numérique déjà enregistrée lors de la migration. Les candidats
  trop courts pour contenir un échantillon audio valide ne sont pas proposés.

## 4. Édition du BPM d’un échantillon

- La colonne **BPM** montre la valeur courante, `—` si inconnue. L’édition propose
  une valeur et deux modes : **BPM only** par défaut (affichage et nom d’export,
  audio inchangé), **Change speed** (vitesse, durée et hauteur changent ensemble).
  Si une vitesse a déjà été appliquée, **BPM only** la conserve et change
  uniquement la valeur affichée et utilisée pour le nom d’export.
  Montrer la durée résultante dans **Length** ; laisser **Position** et les
  rectangles ancrés au passage source. Ne pas inventer un tempo pour un one-shot :
  sans tempo de référence fiable, seule l’édition **BPM only** est disponible.
- Le facteur de vitesse est le BPM choisi divisé par le BPM source. Les éditions
  successives repartent de l’extrait d’origine, sans rééchantillonnages cumulés.
  Le rendu conserve la fréquence d’échantillonnage de sortie et les canaux ;
  utiliser le même traitement pour préécoute, exports et glisser-déposer de WAV.
  Refuser les BPM non finis ou non positifs et les rendus excessifs ou vides.
  Une annulation ne change rien ; une édition ne réécrit aucun export existant.

## Validation et livraison

Une étape à la fois, avec tests de régression et validation utilisateur. Couvrir
les gestes Qt et le tracé, le dépôt sans déplacement, l’ouverture depuis Dolphin,
les deux processus, les dialogues annulés, les options CLI invalides et les bords
de découpe. Vérifier les durées, la hauteur et la stéréo sur du son synthétique,
ainsi que l’équivalence préécoute/export. Distinguer sondes isolées et recette
réelle : aucun lancement de l’installateur sans accord sur ses écritures externes.

Après revue et corrections, vérifier la suite, les hooks et l’ensemble des
commits sortants avec Gitleaks. Faire les commits locaux, puis intégrer et pousser
la version validée vers la branche convenue, sans push forcé ni publication de
réglages, identifiants, fichiers audio privés ou modification locale de Semgrep.
