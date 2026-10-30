# Refonte de l'interface — design

Statut : **approuvé par l'utilisateur, avec les trois corrections intégrées
ci-dessous**. Toutes les propositions du brouillon sont acceptées : touche
`M` pour marquer/retirer, WAV glissés dans `glissés/` sous le dossier d'export,
et bouton « Analyser l'album » toujours visible en haut, à côté de « Lecture auto ».
La réalisation reste soumise à un plan puis à une validation après chaque étape.

## 1. Objectif et périmètre

Rendre la sélection, l'écoute et l'envoi des samples détectés directs et lisibles,
dans une interface native Linux/KDE. Réutiliser PySide6, pyqtgraph, le moteur et
la bibliothèque existants. Aucun serveur, navigateur ou changement d'algorithme
de détection dans cette refonte.

L'utilisateur choisit uniquement parmi les candidats : pas de dessin de zone,
déplacement de bornes, redimensionnement de sample, découpe ou time-stretch.
Le zoom et le déplacement de la vue temporelle ne modifient jamais les samples.

## 2. Prototype préalable et portée de sa validation

Prototype indépendant : `prototypes/drag_drop_wayland.py`.
Lancement demandé : `QT_QPA_PLATFORM=wayland uv run python prototypes/drag_drop_wayland.py`.

Retour utilisateur : dépôt dans Dolphin avec choix de copie effectué ; dépôt
dans Bitwig sur une nouvelle piste effectué. Le transfert d'une URL locale de
WAV avec l'action copie est donc validé dans sa configuration testée.

Cela ne constitue pas une garantie pour toutes les versions de KDE, Bitwig,
Flatpak ou le passage XWayland/Wayland. L'annulation, la lecture après fermeture
et la réouverture d'un projet Bitwig restent à tester explicitement dans
l'intégration complète : ne pas les déclarer validées par ce seul retour.

Différence voulue avec le prototype : les WAV de l'interface finale seront
**conservés durablement dans le sous-dossier `glissés/` du dossier d'export
configuré**, sans nettoyage automatique. Ils restent séparés des exports par
bouton. Ce choix a été validé pour éviter de casser les références Bitwig.

## 3. Disposition validée, dans sa dernière version

- Bibliothèque actuelle à gauche, avec arborescence dossier/album/piste.
- En haut : case « Lecture auto », bouton « Analyser l'album » juste à côté,
  et bouton paramètres. L'analyse d'album reste visible même indisponible ;
  son activation dépend du dossier choisi et de l'absence d'analyse en cours.
- En haut à droite : titre de la piste et tempo, puis grande forme d'onde.
- Sur la forme d'onde : **aucun rectangle de candidat permanent** ; uniquement
  la courbe et les traits fins des premiers temps de mesure.
- Pendant la lecture d'un sample : sa durée est légèrement surlignée sur la
  forme d'onde. Le surlignage disparaît à la fin ou à l'arrêt.
- Sous la forme d'onde : couloirs fins, dans cet ordre : boucles 1 mesure,
  boucles 1/2 mesure, boucles 1/4 de mesure, puis one-shots. Les couloirs vides sont masqués.
- Forme d'onde et couloirs partagent exactement le même axe du temps, y compris
  lors des changements de zoom et de position de la vue.
- Dézoom maximal et déplacement bornés à `[0, durée audio]`, sans marge extérieure,
  depuis l'onde comme depuis les couloirs ; les limites suivent chaque nouvelle piste.
- Zoom et déplacement uniquement horizontaux. L'amplitude est ajustée à pleine
  hauteur lors du chargement puis figée : aucune interaction verticale ni bouton « A ».
- Dans chaque couloir, un rectangle par sample ; tout chevauchement crée
  automatiquement autant de sous-lignes fines que nécessaire.
- Aucun rectangle caché derrière un autre, ni priorité de clic fondée sur sa
  durée, son score ou sa proximité au pointeur.
- Au survol d'un rectangle : info-bulle avec type, tempo, durée et position.
- En dessous : liste compacte, synchronisée avec les rectangles dans les deux
  sens ; colonnes type, tempo, durée, position et poignée `⠿`.
- En bas : « Exporter la sélection (n) » et « Tout exporter (n) ».

**Décision technique acceptée :** conserver une hauteur minimale utilisable par
sous-ligne et permettre le défilement vertical des couloirs si nécessaire,
plutôt que de masquer des samples ou de réduire leurs rectangles à un pixel.
Les libellés de catégorie restent séparés de la zone temporelle.

**Décision technique acceptée :** placement déterministe des rectangles par début,
puis fin, puis identité ; réutiliser une sous-ligne dès que son dernier rectangle
se termine. Deux intervalles qui se touchent ne se chevauchent pas. Ni la
sélection ni le marquage ne changent ce placement.

**Dernière révision utilisateur du 30/10/2026 :** seules les boucles de 1, 1/2
et 1/4 de mesure sont autorisées. Les anciennes longueurs 2/4/8 et les longueurs non standard
sont supprimées du moteur et des réglages, sans couloir de compatibilité.
Les anciens paramètres sont migrés une fois vers les trois longueurs actives ;
un marqueur de version permet ensuite de préserver les choix volontaires.
Les analyses rythmiques en cache restent réutilisables, car les candidats sont
recalculés. Noms d'export : `1bars`, `0.5bars` et `0.25bars`.
Quota validé : jusqu'à 8 par longueur et 8 one-shots (32 au maximum), si le morceau
le permet. Le classement se fait séparément pour chaque longueur afin qu'une
catégorie ne fasse plus disparaître les autres. Le réglage de quantité est libellé
« Nombre de candidats par catégorie », limité à 1–8.
Le tempo s'affiche à une décimale ; durée et position en `mm:ss.mmm`.

## 4. Sélection, marquage et lecture

Trois notions distinctes :

- Sample **actif** : celui visé pour les commandes de lecture et la navigation.
- Sample **en lecture** : au maximum un ; jamais une superposition d'écoutes.
- Samples **à garder** : ensemble marqué, indépendant du sample actif.

Comportements validés sur les rectangles :

- Avec « Lecture auto » : clic = sélection et lecture immédiate ; second clic
  sur le même rectangle en lecture = arrêt.
- Sans « Lecture auto » : clic = sélection sans démarrage de lecture.
- Ctrl+clic = marquer à garder, couleur plus vive et `✓` dans la liste.
- Espace = lancer/arrêter le sample actif.
- Pas d'édition des rectangles et de leurs bornes.

**Décisions complémentaires acceptées :**

1. La liste suit les mêmes règles de clic et de lecture auto que les rectangles.
   Un clic sur sa poignée prépare seulement le glisser, sans écouter ni marquer.
2. Ctrl+clic bascule le marquage : un second Ctrl+clic retire la marque. Ce geste
   ne déclenche ni n'interrompt de lecture et ne change pas le sample actif.
3. Avec la lecture auto désactivée, choisir un autre sample arrête l'écoute
   précédente puis sélectionne le nouveau sans le jouer, pour éviter d'entendre
   un sample différent de celui indiqué comme actif. Un clic sur le sample déjà
   actif ne change pas son état de lecture ; Espace reste disponible pour l'arrêt.
4. « Lecture auto » est activée par défaut, mémorisée entre sessions. Décocher
   la case ne coupe pas à lui seul une écoute en cours : ce sont les prochains
   clics qui changent de comportement.
5. Une fin de lecture conserve le sample actif et les marques, mais retire
   l'indication de lecture et son surlignage sur la forme d'onde.
6. Changer de piste arrête la préécoute et réinitialise les marques de la piste
   précédente. Pas de persistance des marques ni de sélection multi-pistes dans
   cette première refonte.

Le rectangle et la ligne du sample actif ont un repère de focus distinct du
marquage « à garder » ; la lecture a une indication supplémentaire, par exemple
`▶`, pour ne pas dépendre uniquement de la couleur.

La synchronisation révèle la ligne ou sous-ligne active par défilement si besoin,
sans changer les bornes des samples ni provoquer une seconde lecture par rebond
de signaux. Ne pas modifier automatiquement le zoom temporel.

## 5. Informations et couleurs

Style validé : gris anthracite, texte gris clair, sans noir pur, dégradé ou effet
lumineux. Accent orange doux. Boucles orange, one-shots bleu-gris ; une marque
garde la même teinte, rendue plus vive. L'état actif reste lisible même si le
sample n'est pas marqué. Le fond et le texte suivent le thème clair/sombre KDE ;
les accents restent dans les mêmes familles en thème clair.

Paramètres : option « Forcer sombre », désactivée par défaut. Quand elle est
désactivée, suivre aussi un changement du thème système pendant l'exécution.
La même palette doit être appliquée aux widgets Qt et aux vues pyqtgraph.

**Présentation acceptée :** durée et position en `mm:ss.mmm` ; tempo en
BPM avec au plus une décimale, `—` si inconnu. Pour un one-shot sans BPM propre,
afficher le tempo de la piste lorsqu'il est disponible, en précisant « tempo de
la piste » dans l'info-bulle ; ne pas inventer un tempo de l'événement isolé.
Les couleurs exactes et contrastes seront vérifiés dans les deux thèmes lors
de l'étape visuelle, sans ajouter une troisième couleur d'accent.

## 6. Exports et glisser-déposer

- « Exporter la sélection (n) » concerne les samples marqués à garder, pas la
  seule ligne active ; `n` est leur nombre.
- « Tout exporter (n) » concerne tous les candidats de la piste affichée, pas
  l'album ou toute la bibliothèque ; `n` est le nombre total de candidats.
- Les exports par bouton conservent les réglages WAV/FLAC existants.
- Le glisser part exclusivement de la poignée `⠿` d'une ligne et concerne son
  sample, indépendamment des autres marques.
- Au vrai début du glisser, créer un WAV 24 bits dans le sous-dossier `glissés/`
  du dossier d'export configuré, puis fournir son URL locale au système ; action
  copie uniquement. Créer ce sous-dossier à la demande, jamais au simple clic.
- Conserver ce fichier même si le dépôt est annulé ou la fenêtre fermée : il
  peut déjà être référencé par Bitwig. Aucun nettoyage automatique.
- Aucun écrasement : nommage actuel nettoyé et suffixe anti-collision atomique.
- Les sources audio sont toujours en lecture seule ; fréquence et canaux de
  l'extrait doivent être conservés. La représentation visuelle peut être mono,
  mais elle ne doit pas servir de source audio à l'export ou à la lecture.
- Toute erreur d'export est affichée ; ne pas lancer un glisser avec une URL
  vide/inexistante ni annoncer un import Bitwig réussi sur le seul retour de Qt.

**Décisions complémentaires acceptées :**

- Les boutons exportent directement dans le dossier configuré ; s'il manque,
  demander une destination avant cet export. Ne pas modifier silencieusement
  les paramètres à cette occasion.
- Sans dossier d'export configuré, les poignées ne démarrent pas de glisser et
  indiquent dans leur info-bulle de définir ce dossier dans les paramètres.
  Ne pas ouvrir un dialogue modal au milieu du geste Wayland.
- À chaque glisser, créer un nouveau fichier, suffixé si nécessaire. Ne pas
  réutiliser ni supprimer un export précédent sur la seule base de son nom.
- Une erreur au milieu d'un export multiple indique les fichiers déjà exportés
  et l'échec ; ne pas supprimer les réussites ni présenter le lot comme complet.

Effet de bord assumé : les glissers répétés, même annulés, occupent de l'espace
disque. Ils ne sont pas idempotents ; l'utilisateur gère ses exports permanents.
Un dossier d'export réseau déconnecté doit produire un message compréhensible.

## 7. Menus et raccourcis

Exigences validées : menu « Aide > Raccourcis clavier » listant tous les raccourcis ;
chaque raccourci affiché dans son menu et l'info-bulle de son bouton.
Les actions sont définies une seule fois pour garder menus, boutons et aide
cohérents. Les commandes de lecture ne capturent pas les espaces saisis dans
un champ texte ou les interactions avec un dialogue.

**Raccourcis acceptés :**

| Action | Raccourci |
|---|---|
| Ouvrir une bibliothèque | Ctrl+O |
| Paramètres | Ctrl+, |
| Lecture/arrêt du sample actif | Espace |
| Arrêter la lecture | Échap |
| Marquer/retirer le sample actif | M |
| Marquer tous les samples de la piste | Ctrl+A |
| Retirer toutes les marques | Ctrl+Maj+A |
| Exporter les samples marqués | Ctrl+E |
| Tout exporter pour la piste affichée | Ctrl+Maj+E |
| Afficher les raccourcis clavier | F1 |
| Quitter | Ctrl+Q |

Les flèches haut/bas conservent la navigation habituelle de la liste, sans
lecture automatique sur chaque déplacement au clavier ; Espace joue le choix.
Les raccourcis de marquage restent limités au contexte des candidats, sans
intercepter Ctrl+A dans un champ texte ou dans la bibliothèque.

L'ouverture de bibliothèque reste accessible par menu/action. L'analyse d'album
dispose aussi d'une action de menu, mais son bouton reste visible en haut à côté
de « Lecture auto » : une entrée de menu ne remplace pas ce bouton.

## 8. Approche technique acceptée

Évolution progressive de l'interface Qt existante ; pas de réécriture du moteur,
pas de nouvelle boîte à outils, pas de version web. C'est l'approche cohérente
avec les contraintes du projet et le prototype validé.

Un état commun de présentation porte les candidats, leur identité stable sur
la piste, le sample actif, les marques, l'état de lecture et la lecture auto.
La forme d'onde, les couloirs et la liste ne maintiennent pas chacun leur propre
sélection indépendante. Les identités ne dépendent pas de la position visuelle
dans une liste triée.

Le moteur ne connaît toujours pas Qt. L'interface consomme `Analysis.downbeat_times`
pour ses traits fins, les candidats inchangés pour les rectangles, et l'audio
multicanal pour écouter/exporter. Aucun changement de score ou de détection n'est
justifié par cette refonte.

L'état de lecture est remis à jour à la fin réelle de la préécoute, pas seulement
au clic sur Arrêter. Une erreur de périphérique ne doit pas laisser un sample
affiché comme en lecture. Les écritures et erreurs du glisser ont un traitement
commun avec les exports, sans construire les fichiers à l'ouverture de la piste.

**Validation plateforme acceptée :** intégrer et tester sous Wayland natif
comme le prototype, conserver le choix explicite `QT_QPA_PLATFORM=xcb` comme
solution de secours. Le retrait du forçage XCB actuel sera une étape explicite
avec test utilisateur des anciens problèmes de rafraîchissement KDE ; il ne sera
pas assimilé à une simple conséquence de la réussite du prototype.

## 9. Vérifications requises et ordre de réalisation

Ce design étant approuvé : rédiger un plan avec `writing-plans`, puis
travailler **une étape à la fois**, tests et résultat présentés, validation
utilisateur avant l'étape suivante. Ne pas lancer toute la refonte en continu.

Le plan devra couvrir, avant les modifications correspondantes :

- Placement sans recouvrement dans une même sous-ligne : inclusions, débuts
  identiques, rectangles adjacents, ordre stable et catégories vides.
- Même axe temporel dans la courbe et les couloirs, zoom/déplacement synchrones,
  courbe sans rectangles permanents et traits sur les vrais downbeats.
- Clic, second clic, Ctrl+clic, navigation de liste et Espace, sans doubles
  déclenchements ni confusion entre actif, marqué et en lecture.
- Fin de lecture, changement de piste, erreur audio, absence de sample actif.
- Comptes d'export et comportement sans marque, liste vide, annulation,
  dossier absent/inaccessible, collision de nom et export partiellement réussi.
- Conservation de la stéréo, fréquence d'origine, bornes identiques entre
  préécoute, export par bouton et WAV du glisser.
- WAV réellement créé au seuil du glisser, jamais au simple clic ; fichier
  conservé après annulation et fermeture ; URL locale et copie uniquement.
- Thèmes clair/sombre KDE, forçage sombre et changement à chaud, y compris
  lisibilité de toutes les combinaisons actif/marqué/en lecture.
- Raccourcis présents dans les menus, aide et info-bulles, sans conflit avec
  saisie de texte, dialogues ou raccourcis internes de la bibliothèque.
- Régression : suite pytest complète, contrôles statiques et essai manuel
  Bitwig/Dolphin sous Wayland, puis test de la solution de secours XCB si utile.

Les choix de ce document sont acquis. Ne pas les rouvrir pendant la réalisation ;
signaler uniquement un blocage technique nouveau qui empêcherait leur respect.
