# Chopper — espace de travail des échantillons

## Affichage et réglage

- À taille de fenêtre identique, viser la moitié de la hauteur actuelle pour la
  forme d’onde et deux tiers pour la zone des rectangles. Donner toute la hauteur
  récupérée au panneau de la liste. Respecter les tailles minimales quand la fenêtre
  est petite ; conserver le scroll, le zoom et l’alignement temporel.
- Conserver le thème et la disposition générale. Toutes les colonnes de la liste
  deviennent redimensionnables ; la poignée de glisser-déposer reste utilisable.
- Autoriser de 1 à 64 échantillons par catégorie dans les paramètres et dans la
  validation des réglages enregistrés. Ne pas changer la valeur par défaut de 8.

## Albums et pistes

- Ajouter chaque dossier d’album choisi en bas de la bibliothèque de gauche, dans
  l’ordre d’ajout, avec son nom de dossier et son chemin pour le distinguer. Les
  albums restent visibles, repliables et accessibles par le défilement vertical.
  Choisir de nouveau le même dossier ne crée pas de doublon. Distinguer **Add
  album…**, qui ajoute à la session, de **Open library…**, qui garde son rôle de
  choix de la racine mémorisée. Conserver le chargement des enfants à la demande
  pour éviter un scan récursif.
- Ajouter une action **Open track…**. Une piste ouverte seule apparaît au niveau
  principal avec son nom de fichier, sans dossier affiché. Conserver aussi le
  contrat `chopper <fichier>` et réutiliser le même parcours d’analyse. La
  sélection d’une piste seule ne doit pas laisser **Analyze album** viser un
  dossier précédemment sélectionné.
- La bibliothèque peut lister plusieurs albums et pistes, mais une seule piste
  est chargée et alimente le tracé et la liste du bas. Ajouter un album ne lance
  pas automatiquement son analyse et ne mélange jamais ses résultats aux autres.
  L’action existante d’analyse d’album traite l’album choisi, un morceau à la fois.
- L’accumulation des ajouts concerne la session en cours ; pas de nouveau format
  de préférences ni de copie des fichiers audio.

## Découpe et export

- **Chop selection** lance la recherche habituelle et affiche ses résultats dès
  qu’ils sont prêts, sans boîte « Replace the manual samples ». Changer **Length**
  avec une sélection relance la recherche pour cette sélection ; sans sélection,
  cela change seulement la longueur du prochain découpage. Pas de seconde analyse
  audio ni de tâches simultanées sur une même fenêtre. Garder les résultats en
  place jusqu’au remplacement réussi ; aucun enregistrement automatique des anciens
  résultats. Ne pas étendre la suppression des confirmations aux autres actions.
- Clic droit → **Export** sur une ligne ou un rectangle : exporter uniquement
  l’échantillon visé, en suivant le parcours d’export existant. Ne pas lancer la
  préécoute ni changer le marquage. Aucune action sur un emplacement vide et aucun
  écrasement de fichier exporté. Les exports groupés restent inchangés.

## Approche retenue et livraison

Étendre l’arbre, la liste, les rectangles et le contrôleur actuels plutôt que
créer une seconde bibliothèque ou un second moteur de découpe. Réutiliser la même
identité d’échantillon et le même export depuis les deux vues. Pas de nouvelle
bibliothèque ni de dépendance de `core/` vers Qt ; sources audio en lecture seule.

Vérifier les changements par étapes : disposition et limites, bibliothèque et
ouverture, puis découpe et export. Tester les régressions et les cas limites,
relancer la suite et les hooks, puis fusionner et publier la version validée sur
la branche de production convenue. Avant le push, contrôler les commits sortants
pour les secrets et les données privées ; exclure la modification locale de
Semgrep. Pas de push forcé, d’installation ou de publication d’archive prévue.
