# Prototype jetable : glisser-déposer vers Bitwig sous Wayland

Ce test est indépendant de l'interface actuelle et ne modifie aucun morceau,
paramètre ou cache d'analyse. Ce n'est pas une maquette de la future interface.

Depuis la racine du projet, dans une session KDE Wayland :

```bash
QT_QPA_PLATFORM=wayland uv run python prototypes/drag_drop_wayland.py
```

La première ligne du journal doit indiquer `backend Qt réel : wayland`.
Contrairement à l'application actuelle, le prototype ne force pas XWayland.
Un échec d'ouverture avec cette commande est à signaler, pas à masquer par
un changement silencieux de backend.

## Test manuel indispensable

1. Ouvrir un **projet de test** dans Bitwig, avec une piste audio.
2. Maintenir le clic gauche sur `⠿ Glisser ce sample`, puis déposer sur la piste.
3. Vérifier que le clip apparaît et que sa lecture joue les quatre pulsations
   graves de la boucle stéréo de deux secondes.
4. Faire un nouveau glisser depuis la poignée vers un dossier dans Dolphin ;
   vérifier la présence du WAV et sa lecture.
5. Annuler un glisser avec Échap, puis réessayer : la fenêtre doit rester utilisable.
6. Fermer le prototype et vérifier que le clip déjà importé dans Bitwig joue encore.

Le journal affiche l'emplacement du WAV, son URL locale et le retour de Qt.
`CopyAction` **ne suffit pas** à prouver que Bitwig a réellement importé l'audio.
Si Bitwig est installé via Flatpak ou un autre confinement, l'accès au fichier
peut différer de celui de Dolphin : l'essai réel décide de la compatibilité.

## Effets de bord

Chaque vrai début de glisser crée un nouveau sous-dossier `choppeur-dnd-probe-*`
dans le dossier temporaire du système, avec un WAV PCM24 stéréo à 44 100 Hz
(environ 530 ko). Aucun fichier n'est créé sur un simple clic.
Les fichiers restent présents même après annulation ou fermeture : Bitwig peut
encore lire leur chemin. Aucun nettoyage automatique n'est effectué par ce test.
Ils ne conviennent pas à un projet durable : le système peut nettoyer les
fichiers temporaires, notamment après redémarrage.

Pour choisir un autre emplacement, le dossier doit déjà exister :

```bash
QT_QPA_PLATFORM=wayland uv run python prototypes/drag_drop_wayland.py --output-root DOSSIER_EXISTANT
```

Les tests automatisés vérifient le vrai WAV, son URL, les noms distincts,
l'absence d'export sur clic et la remontée d'une erreur d'écriture. Ils ne
prouvent pas un dépôt dans Bitwig ou Dolphin sous Wayland.
