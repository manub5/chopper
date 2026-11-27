# Chopper — Ajustement temporaire des bornes d’un sample

À livrer avant les options de découpe en ligne de commande.

## Approche

Ajouter deux colonnes **Start offset (ms)** et **End offset (ms)** au tableau
des samples, à côté de **Position**. Elles montrent l’écart de chaque borne
avec la découpe d’origine et se modifient au clavier, sans molette, curseur
ni boutons de réglage.

## Comportement

- Chaque borne reçoit un décalage signé en millisecondes, initialement `0`.
  `-25` avance la borne concernée de 25 ms ; `+25` la retarde de 25 ms, sans
  déplacer l’autre. Les valeurs sont relatives à la découpe d’origine et ne se
  cumulent pas. `0` restaure uniquement la borne éditée si le résultat est valide.
- La durée peut changer. L’audio est lu et exporté à sa vitesse et à sa hauteur
  d’origine, sans rééchantillonnage ni modification du BPM. Refuser une valeur
  qui sort de la piste, inverse les bornes ou ne laisse aucune trame audio ;
  conserver alors la dernière valeur valable. La sélection de découpe n’est
  pas une limite de déplacement.
- **Position**, **Length**, le rectangle, la prochaine préécoute et tous les
  nouveaux exports, y compris le glisser-déposer, utilisent les bornes ajustées.
  L’édition ne lance pas de lecture ; si ce sample est en cours de préécoute,
  l’arrêter pour ne pas afficher une position différente de celle qui joue.
  Conserver l’identité du sample, ses marques et la sélection courante.
- Ne rien enregistrer dans les préférences ni le cache. Une nouvelle découpe ou
  un changement de piste efface les décalages. Ne modifier ni l’audio source ni
  les exports existants.

## Vérification

Tester les deux signes sur chaque borne, l’indépendance des réglages, le retour
à zéro, l’annulation, les deux bords de piste et le refus d’un extrait vide ou
inversé. Sur un signal synthétique, vérifier que la préécoute et les nouveaux
exports reçoivent les trames attendues sans traitement de vitesse ou de hauteur.
Contrôler aussi le tableau, le rectangle et les marques.
