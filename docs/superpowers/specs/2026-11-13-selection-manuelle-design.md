# Sélection manuelle — design

## Objectif et état

Choisir un passage d'une piste déjà analysée, le préécouter et y rechercher des
boucles/one-shots, sans nouvelle analyse beat_this ni modification des sources.
Cette fonction est la priorité actuelle. Elle ne réécrit pas les commits de
distribution déjà publiés et ne remplace pas automatiquement le ZIP existant.

Choix explicitement confirmés par l'utilisateur : gestes décrits ci-dessous,
longueurs ¼/½/1/2/4 mesures, bouton Chop selection et raccourci C, résultats
restreints à la sélection, retour Whole track, et même confirmation lors d'un
retour par Échap ou clic extérieur. Si l'export échoue ou est annulé, conserver
la sélection et les résultats. Si les boucles demandées ne tiennent pas, chercher
quand même les one-shots et afficher un message clair.

Les règles complémentaires marquées **proposition** ci-dessous sont des choix
de conception à approuver avec ce document, pas des demandes déjà formulées.
Aucun code produit modifié pendant cette phase. Plan et réalisation après accord.

## Approche retenue

Conserver l'audio et Analysis en mémoire ; ajouter seulement `window=(start, end)`
optionnel aux deux fonctions de recherche core. Les positions restent exprimées
en secondes depuis le début de la piste, y compris pour la lecture et l'export.
Cette approche a été exposée pendant le cadrage et respecte la demande initiale.

Alternatives écartées : recouper/réanalyser un nouveau fichier relancerait des
calculs inutiles ; découper le tableau avec une origine locale imposerait des
conversions de positions et augmenterait les risques d'export décalé. Filtrer
seulement les meilleurs résultats globaux après leur calcul manquerait les bons
samples de la zone à cause des quotas : la recherche doit être bornée avant tri.

## Interaction et aspect

Contrôles compacts sous le titre et au-dessus de la forme d'onde, sans changer
la bibliothèque, les couloirs, la liste ni la poignée de glisser vers le DAW :

```text
Track title — BPM
Length: [1 bar v]   [Chop selection  C]   [Whole track]
Selection: 00:12.000 – 00:20.000
~~~~~~~~~~~|========== selected passage ==========|~~~~~~~~~~~
sample lanes
sample list / existing export controls
```

L'application reste en anglais : `Length`, `¼ bar`, `½ bar`, `1 bar`, `2 bars`,
`4 bars`, `Chop selection`, `Whole track`. **Proposition :** longueur initiale
1 mesure, mémorisée pour la session seulement ; aucun nouveau réglage TOML.

Réutiliser la police système et ThemePalette : surface/texte natifs, sélection
bleutée translucide (`selection`), bords visibles (`active`), lecture existante
distincte (`playing`). Les repères de mesure et le tracé restent lisibles.
Pas de nouvelle charte graphique, animation, dépendance web ou serveur local.

### Dessiner et ajuster

- Glisser gauche sur la forme d'onde crée une LinearRegionItem distincte de la
  surbrillance passive de lecture. Seuil de déplacement Qt pour distinguer glisser
  et clic ; un clic simple ne crée pas un passage nul.
- **Proposition :** ses deux bords sont ajustables ; glisser à l'intérieur déplace
  la région entière ; un glisser extérieur dessine une nouvelle région. Un simple
  clic intérieur ne retire rien et ne relance pas la lecture.
- Bornes toujours triées, contenues dans l'audio réellement chargé. Les glissers
  de droite à gauche et le croisement des bords ne provoquent pas d'inversion.
- Aimantation au premier temps de mesure le plus proche, uniquement à partir
  d'Analysis.downbeat_times. **Proposition :** égalité départagée vers le plus tôt.
  Alt suspend l'aimantation pendant le geste ; son état final est pris en compte
  au relâchement, y compris après pression/relâchement en cours de déplacement.
- Sans premier temps utilisable : sélection libre, sans inventer une grille.
  Si l'aimantation ramène les deux bords au même instant, pas de sélection valide
  ni de préécoute ; ne pas forcer artificiellement une mesure supplémentaire.
- Au relâchement d'un geste valide, préécouter une fois le passage si Auto-preview
  est activé. Aucune préécoute par simple mise à jour programmatique du rectangle.
- Bouton milieu et Maj+molette déplacent horizontalement la vue ; molette seule
  garde le zoom horizontal, borné à la piste. Axe vertical toujours figé.
  **Proposition :** mêmes commandes de navigation sur les couloirs liés ; leurs
  clics gauches de sélection/marquage restent disponibles, mais plus de pan gauche.
  Ne pas laisser le glisser droit pyqtgraph modifier silencieusement les axes.

### États affichés

- **Whole track :** candidats automatiques et aucune région manuelle.
- **Sélection prête :** région présente, recherche déclenchée seulement par
  Chop selection, jamais au simple dessin de la région.
- **Résultats manuels :** liste et couloirs issus du dernier Chop selection.
- **Proposition :** modifier la région ou Length ne recalcule pas en permanence.
  Les résultats existants restent associés à leurs bornes d'origine, affichées
  dans un libellé ; message `Selection changed. Chop again to update samples.`
  s'ils ne correspondent plus à la région courante. Exporter ces résultats exporte
  toujours leurs bornes d'origine, jamais celles du rectangle ajusté ensuite.

## Sortir de la sélection sans perdre les résultats

Échap, clic simple extérieur sur la forme d'onde et Whole track appellent une
seule procédure de sortie. Le clic extérieur est reconnu au relâchement, pas à
la pression, pour ne pas transformer le début d'un nouveau glisser en suppression.

Si une région ou des résultats manuels sont présents, ouvrir la même confirmation
en anglais, y compris avant la première découpe ou après une recherche vide :

- `Export and return` : exporter **tous** ces résultats, pas seulement les cochés,
  puis revenir aux candidats automatiques et retirer le rectangle.
- `Return without exporting` : retirer résultats manuels et rectangle, rétablir
  les résultats automatiques. Ne supprimer aucun fichier déjà écrit.
- `Cancel` : conserver région, résultats et marques. Fermeture de la boîte ou
  Échap dans cette boîte équivaut à Cancel, jamais à une seconde action globale.

**Proposition :** Cancel est le choix sûr par défaut. Sans résultat manuel à
exporter, désactiver Export and return et expliquer que seuls le rectangle et
le mode de sélection seront retirés ; ne pas exporter les candidats automatiques
encore affichés avant le premier Chop selection. Sans région ni résultats manuels,
Whole track est désactivé et Échap se limite à l'arrêt de lecture habituel.

L'export reprend le dossier, le format et la fréquence/canaux existants. Annulation
du choix de dossier, échec de sauvegarde des paramètres ou export partiel/échoué :
ne pas changer de mode ni retirer la région/les résultats/les marques. Signaler les
fichiers déjà réussis sans les supprimer. Une nouvelle tentative peut créer des
noms distincts, conformément à la politique actuelle ; pas de faux succès.

**Proposition de protection complémentaire :** si une action doit remplacer des
résultats manuels (nouveau Chop selection, autre piste, analyse d'album ou fermeture
de la fenêtre), appliquer la même décision exporter/continuer, continuer sans
exporter ou annuler. Adapter le texte à l'action, sans bouton qui annonce un retour
alors qu'il ferme l'application. Toute annulation/erreur bloque l'action destructive.
Les gestes d'ajustement seuls ne suppriment pas les anciens résultats.

Échap arrête également la préécoute, comme aujourd'hui ; l'arrêt ne dépend pas du
choix ultérieur de confirmation. Annuler la sortie ne redémarre pas l'audio.

## Recherche bornée dans le moteur

Élargir LOOP_LENGTHS_BARS et is_loop_length à 0.25, 0.5, 1, 2, 4. Séparer les
longueurs automatiques (0.25, 0.5, 1) de cet ensemble supporté : mêmes valeurs
par défaut, mêmes cases Settings, même migration version 3 et mêmes préférences.
Les anciennes valeurs 2/4 d'un TOML ne doivent pas soudain activer l'analyse longue.

- find_loop_candidates et find_one_shot_candidates reçoivent `window=None` par
  défaut. Sans fenêtre : comportement et résultats automatiques conservés.
- **Proposition :** 2 et 4 mesures acceptées par la recherche de boucles seulement
  avec une fenêtre explicite ; sans fenêtre, l'ancien contrat reste inchangé.
- Contrat d'une fenêtre : deux nombres finis, 0 ≤ start < end ≤ durée de l'audio.
  Rejeter les booléens/NaN/infini, ordre inversé et bornes hors piste avec une erreur
  claire ; l'interface borne ses gestes avant l'appel et traduit l'erreur en message.
- Bornage de la recherche avant classement/quota. Les scores audio (énergie,
  seuil de silence, lissage de coupure) ne lisent pas hors de la fenêtre demandée.
  Avec fenêtre, calculer les références RMS/crête sur ce passage seulement.
- Réutiliser les premiers temps de toute l'analyse pour estimer la durée d'une
  mesure comme aujourd'hui, même si la région ne contient qu'un premier temps.
  Départ de boucle sur un premier temps inclus, durée complète demandée, fin
  incluse dans la fenêtre : jamais raccourcir une boucle pour la faire tenir.
- Une sélection libre Alt ne crée pas de nouveaux repères rythmiques ; elle borne
  la recherche, sans modifier l'analyse. Sans rythme exploitable, one-shots seulement
  et message explicatif. Pas d'invention d'une mesure à partir du seul tempo.
- One-shots : départ sur une attaque mémorisée incluse, fin limitée par retour au
  silence, attaque suivante, durée maximale actuelle et fin de fenêtre. Ne pas lire
  un bloc de détection de silence au-delà de cette fin.
- Les temps renvoyés gardent l'origine piste ; lecture et exports utilisent la même
  convention de conversion temps/échantillons qu'aujourd'hui, sans découpage mono
  destructif, normalisation ou changement de fréquence/canaux.
- Quotas actuels conservés : respecter Settings.candidates_per_track (1 à 8) pour
  les boucles de la longueur choisie et séparément pour les one-shots, ainsi que
  Settings.max_one_shot_seconds. Jusqu'à 8 de chaque avec les réglages par défaut,
  moins si demandé ou si la zone ne le permet pas. Pas de catégorie automatique ajoutée.
- Trop court pour la boucle : liste de boucles vide mais recherche one-shot faite.
  Message, par exemple `Selection too short for 4-bar loops. Found 3 one-shots.`
  Si rien n'est trouvé, résultat vide explicite, pas une exception non gérée.

Whole track réutilise toujours l'analyse et l'audio en mémoire, avec les réglages
automatiques actuels et `window=None` ; aucun nouveau beat_this, aucune nouvelle
lecture du fichier source. **Proposition :** refaire seulement le classement des
candidats plutôt que relancer le pipeline ou conserver des réglages devenus anciens.

## Intégration, lecture et concurrence

- Conserver LoadedTrack/Analysis/audio comme source de vérité. Le résultat manual
  remplace uniquement les candidats, sans réinitialiser le tracé, le zoom ou la
  région. Mettre à jour liste et couloirs par le même SampleState, nouveaux IDs
  stables pour la nouvelle génération ; effacer actif/marques périmés après succès.
- Étendre catégories, libellés et noms d'export aux boucles 2/4 mesures. Ne pas
  laisser une longueur acceptée par le moteur devenir invisible dans les couloirs
  ou provoquer une erreur de table de libellés.
- Utiliser le lecteur existant pour le passage manuel, sans l'insérer comme faux
  sample dans les résultats. Un seul flux audio et un seul espace de jetons pour
  les lectures de samples et de sélection ; ignorer toute fin d'ancienne lecture.
- **Proposition :** la dernière action choisit la cible de préécoute : sélection
  après geste terminé, sample après clic/navigation de sample. Espace agit sur
  cette cible ; l'auto-préécoute désactivée n'empêche pas la demande explicite.
- C est une action du registre, dans la zone samples/forme d'onde, sans répétition
  automatique, désactivée dans les champs de saisie/modales et sans région valide.
  F1 et infobulle dérivent de la même action. Pas de raccourci Échap concurrent.
- **Proposition :** reclassement en worker léger, réutilisant les conventions de
  QThread existantes ; aucune seconde analyse rythmique ni détection d'attaques.
  Requête identifiée par piste/région/longueur/génération ; résultat obsolète ignoré.
  Une seule tâche à la fois, contrôles de remplacement désactivés pendant le calcul.
  Échec : ancien affichage conservé et message ; arrêt/fermeture maîtrisés.
- La préécoute est arrêtée avant export/transition, pas de lecture automatique des
  nouveaux résultats au simple clic Chop selection ou au retour Whole track.

## Tests et compatibilité

Tests moteur sans Qt : fenêtre et invalides, aucun candidat hors bornes, quotas
dans une zone ignorée par les meilleurs candidats globaux, pas de lecture audio
de scoring hors fenêtre, one-shot coupé à la fin, boucles exactes 2/4, fenêtres
courtes/vides/silencieuses et rythme absent ; régression window=None.

Tests interface avec vrais gestes : direction inverse, seuil de clic, poignées,
Alt changé pendant le geste, aimantation/égalité/pas de repères, zoom/pan bornés,
y immobile et alignment couloirs à 150 %, lecture seulement au relâchement,
Auto-preview off, Échap/modalité/F1/C sans intercepter la frappe.

Tests de parcours : remplacement des deux vues, messages courts, zéro nouvel appel
beat_this/onsets/audio_io.load, paramètres historiques inchangés, affichage/export
2/4, sauvegarde ou abandon explicites, annulation et échec partiel sans perte de
résultats, sélections modifiées sans exporter des bornes erronées, vieux retours de
worker/lecture ignorés, changement de piste et fermeture avec choix annulé.

Les tests historiques définissant 2/4 comme invalides pour les noms d'export ou
l'affichage doivent devenir des tests positifs ; garder les rejets des longueurs
encore invalides (ex. 3/8/None). Ne pas enlever de couverture pour obtenir du vert.
Garder les rejets 2/4 sans fenêtre dans le moteur et dans les Settings historiques.

Après chaque étape d'implémentation : suite complète, contrôles et hooks existants,
résultat communiqué puis validation utilisateur. Revue indépendante finale et
essai natif KDE/Wayland/audio ; aucun push ou nouveau ZIP sans demande.

## Nettoyage et effets de bord

Ne supprimer que les dossiers réellement vides sous `src/choppeur/`, au moyen
d'une suppression de dossier vide qui refuse tout contenu. Dans l'espace inspecté,
ce chemin n'existe déjà plus : nettoyage sans effet si toujours absent. Aucun
nettoyage récursif d'un autre espace, de caches, de glissers ou d'exports existants.

Sélection et résultats sont transitoires en mémoire, pas d'écriture dans le cache
d'analyse ou les préférences pour mémoriser ce mode. Sources toujours en lecture
seule ; seules les exportations demandées écrivent des samples. Exports et glissers
répétés restent non idempotents par nom distinct ; retour/annulation ne supprime
aucun fichier et n'exporte rien implicitement.

## Références et liberté d'implémentation

Documentation pyqtgraph consultée : LinearRegionItem (bornes, région ajustable,
signaux de changement/fin) et interactions ViewBox. Vérifier les méthodes exactes
dans la version installée 0.14 avant implémentation ; ne pas copier aveuglément les
signatures d'une documentation de développement.

Le plan fixera les noms/signatures des petits composants GUI : gestion des gestes,
état de sélection/confirmation, orchestration worker et lecture. Garder core sans
Qt et éviter d'entasser toutes ces responsabilités dans MainWindow. Les détails
de facteur de zoom/pan restent au constructeur, sous les tests de bornes et de
non-régression ; pas de dépendance ou persistance supplémentaire à introduire.

**État :** relecture de constructibilité effectuée ; quotas et confirmation même
sans résultat précisés après cette relecture. Design en attente d'approbation
utilisateur avant writing-plans. Les propositions complémentaires (protections
sur les autres remplacements, conservation des résultats pendant les ajustements,
retour avec réglages actuels, cible Espace et manipulations de région/couloirs)
doivent être approuvées avec ce document, pas supposées déjà acceptées.
