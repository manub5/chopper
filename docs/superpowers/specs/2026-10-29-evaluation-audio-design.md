# Protocole d'évaluation audio

Protocole validé dans la conversation le 29/10/2026. Les détails numériques
ci-dessous sont des choix de mise en œuvre proposés par l'agent.

## Objectif et approche retenue

Mesurer la vraie détection avant de la modifier, puis conserver uniquement les
améliorations vérifiées. Un banc synthétique avec vérité connue permet la mesure ;
les quatre FLAC personnels permettent des observations complémentaires, sans
vérité inventée. Une évaluation uniquement sur les morceaux réels ne permettrait
pas de mesurer leur précision, faute d'annotations indépendantes.

## Corpus et mesures

- WAV mono PCM16 à 22 050 Hz, génération déterministe, vérité en indices
  d'échantillons et secondes dans `tests/corpus/truth.json`.
- Six cas de réglage et quatre cas de validation : rythmes accentués en 4/4 à
  plusieurs tempos/décalages, one-shots isolés et silence. La séparation des lots
  est fixée avant la première évaluation et ne change pas pendant les essais.
- Erreur absolue de tempo en BPM, sans correction cachée des erreurs double/moitié.
- Décalage absolu des débuts de boucles en ms ; comparaison à tous les débuts
  admissibles annotés, et non à un unique début arbitraire.
- Appariement sans réutiliser une même annotation, précision/rappel des boucles
  et des attaques à 100 ms. Détections manquantes/fausses également comptées.
- Score global borné de 0 à 100, défini et testé avant les essais ; absence de
  détection pénalisée, mesures non applicables indiquées comme telles.

## Exécution et critères de conservation

`evaluate.py` exécute les vrais modules rythme, attaques et candidats, sans cache
d'analyse ni simulation du modèle. Le modèle reste identique entre les essais.
Les tests unitaires des mesures ne nécessitent ni réseau ni modèle téléchargé.

Au maximum trois essais, chacun limité à une hypothèse issue du lot de réglage.
Conservation uniquement si le score de réglage augmente, le score de validation
ne baisse pas et aucune composante de validation ne se dégrade au-delà de la
tolérance numérique fixée avant mesure (0,001 BPM ; 0,01 ms ; 0,000001 en F1).
Un échec, une égalité ou une régression est aussi inscrit au journal. Aucune
promesse d'amélioration si les mesures ne la démontrent pas.

## Musique réelle et contraintes

Deux passages fixes de 30 secondes par FLAC, choisis à partir de sa durée avant
les essais ; affichage des bornes exactes et positions rapportées à la source.
Si le fichier est trop court, réduire explicitement la durée au lieu de dépasser.
Comparer la référence et la version retenue sur ces mêmes passages, sans calculer
d'erreur de tempo/calage en l'absence de vérité humaine. Contrôler l'empreinte des
sources avant/après ; ne jamais modifier ni versionner les morceaux personnels.

`JOURNAL_EVAL.md` conserve commandes, versions, identité du modèle, lots, scores,
durées, décisions et limites. Les analyses réelles sont séparées des scores
synthétiques. Aucun chemin personnel en dur, aucun nouveau dossier dans le home,
aucune suppression des travaux existants. Un correctif conservé a son test de
régression écrit et observé rouge avant correction, puis son commit dédié.
