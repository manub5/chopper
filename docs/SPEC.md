# Spécification — Chopper

Depuis le 02/11/2026, l'interface et la documentation utilisateur sont en anglais.
Commande : `uv run chopper` ; paquet : `src/chopper/`. Les paramètres anciens sont
lus sans modification si le nouveau fichier manque ; les nouveaux WAV glissés vont
dans `dragged/`, sans déplacer les anciens `glissés/`. Voir README pour l'usage courant.

## Objectif
Extraire rapidement, depuis ses propres albums, des samples exploitables
dans une STAN (Bitwig) : boucles qui démarrent sur le premier temps de la
mesure, et one-shots propres.

## Parcours utilisateur
1. Dans le panneau bibliothèque, l'utilisateur ouvre un dossier racine
   (local ou NAS monté) et navigue : dossiers → albums → pistes.
2. Il lance l'analyse sur UNE piste ou sur UN album entier.
3. L'analyse tourne en arrière-plan ; l'interface reste utilisable.
4. Pour chaque piste analysée : forme d'onde affichée, tempo, marqueurs des
   premiers temps de mesure, et liste de plusieurs samples candidats.
5. Il préécoute le sample actif en lecture unique et marque indépendamment
   ceux qu'il garde (Ctrl+clic ou M).
6. Il exporte vers son dossier de samples. Si aucun dossier n'est configuré,
   une courte explication puis un sélecteur permettent de le choisir ; ce choix
   est mémorisé pour les prochaines utilisations et modifiable dans les paramètres.
   Aucun dossier imposé ni demande au lancement. Au premier glisser sans dossier,
   choisir puis recommencer le geste ; aucun WAV n'est créé par cette configuration.

## Quatre catégories de samples
### Boucles
- Début exactement sur un premier temps de mesure.
- Trois longueurs : 1 mesure, 1/2 mesure (0,5), 1/4 de mesure (0,25), activées par défaut.
- Les longueurs 2, 4 et 8 mesures ne sont plus proposées ni générées.
- À la migration des anciens paramètres, réactiver les trois longueurs une fois,
  même si seule 1 mesure était activée. Conserver ensuite les choix explicitement
   enregistrés dans le nouveau format (version 3). Les fichiers de version 2
   sont aussi concernés par cette réactivation demandée. Migration idempotente
   après sauvegarde normale ; la simple lecture ne réécrit pas le fichier.
- Jusqu'à 8 candidats **par longueur**, classés par score à l'intérieur de chaque
  catégorie : une longueur ne peut plus évincer les autres par son score.
- Ne rien inventer si une piste est trop courte ou sans grille rythmique exploitable.

### One-shots
- Début sur une attaque nette.
- Fin : retour au silence relatif ou attaque suivante, avec court fondu.
- Durée maximale réglable.
- Jusqu'à 8 one-shots ; avec les trois longueurs activées, 32 samples maximum par piste.

## Nommage automatique
Format par défaut (modifiable dans les paramètres) :
`{artiste}_{album}_{piste}_{type}_{bpm}bpm_{mesures}bars_{position}.wav`
Exemples : `Burial_Untrue_03_loop_139bpm_1bars_01m12s.wav`,
`Burial_Untrue_03_loop_139bpm_0.5bars_01m12s.wav`,
`Burial_Untrue_03_loop_139bpm_0.25bars_01m12s.wav` (pas de barre oblique).
One-shot : `Burial_Untrue_03_shot_01m12s340.wav`
Caractères interdits nettoyés, pas d'écrasement (suffixe `_2`, `_3`…).

## Paramètres
- Dossier racine de la bibliothèque.
- Dossier cible d'export choisi par l'utilisateur, aucun chemin initial imposé.
- Format d'export : WAV 24 bits (défaut) ou FLAC ; fréquence d'origine conservée.
- Longueurs de boucle : trois cases indépendantes « 1 bar », « ½ bar », « ¼ bar »
  sous « Loop lengths ». Au moins une longueur doit rester cochée pour valider.
- Nombre de candidats **par catégorie** : de 1 à 8, 8 par défaut (même quota pour les one-shots).
- Durée maximale d'un one-shot.
- Utilisation du GPU : auto / forcé CPU.

## Hors périmètre (pour l'instant)
- Séparation de pistes (voix, batterie…) : projet séparé, pas de fusion prévue.
- Docker, web, serveur.
- Traitement de toute la bibliothèque en tâche de fond.

## Vue temporelle
- Couloirs cliquables : 1 mesure, 1/2 mesure, 1/4 de mesure, one-shots ; catégories vides masquées.
- Les samples n'apparaissent que dans ces couloirs : pas de grands traits de
  début/fin de candidat sur l'onde. Seuls les traits fins des premiers temps de
  mesure et le surlignage temporaire du sample en lecture restent sur l'onde.
- Onde et couloirs partagent le même axe du temps, pour zoom et déplacement.
- Dézoom maximal : le morceau entier, exactement de 0 à sa durée audio.
  Aucun déplacement ni zoom ne doit montrer du temps avant le début ou après la fin.
- Interaction uniquement horizontale : axe vertical ajusté à pleine hauteur au
  chargement puis figé ; aucun zoom/pan vertical, aucun bouton « A ».
- Tempo à une décimale ; durée et position en `mm:ss.mmm`.

## Évolutions envisagées
- Fiche d'analyse « avant » : passages sans voix, boucles stables,
  sections percussives (voir ROADMAP, phase ultérieure).
- Détection de la tonalité, tri par tonalité.
- Collecte automatique des samples dans le projet du séquenceur : non garantie.
  Le glisser actuel fournit un WAV permanent ; dans Bitwig, utiliser « Collect
  and Save » pour rendre le projet autonome.
