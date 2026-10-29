# Journal d'évaluation

## Protocole figé avant mesure — 29/10/2026

- Dix WAV synthétiques PCM16 à 22 050 Hz, graine 20261029 ; annotations exactes
  en indices et secondes dans `tests/corpus/truth.json`, avec empreintes SHA-256.
- Réglage : 90, 120 et 150 BPM, une variante syncopée à 120 BPM, one-shots,
  silence. Validation : 105 et 135 BPM, autres positions de one-shots, silence.
- Même modèle beat_this `final0`, `dbn=False`, CPU, quatre threads pour chaque
  essai ; vraies inférences, aucun cache d'analyse, aucune annotation injectée
  dans la détection. Les poids du modèle sont réutilisés, pas ses prédictions.
- Boucles d'une mesure, jusqu'à 128 candidats pour ne pas confondre une limite
  d'affichage de l'interface avec la qualité du moteur.
- Appariement chronologique un-à-un maximisant le nombre de correspondances
  dans une tolérance de 100 ms, puis minimisant le décalage absolu.
- Score /100 : moyenne du score tempo `max(0, 1 - erreur_relative)`, du F1 des
  débuts de boucles et du F1 des one-shots. Chaque composante est d'abord moyennée
  par fichier : un fichier riche en attaques ne pèse pas plus qu'un autre.
- Erreurs BPM brutes, sans corriger les confusions moitié/double. Décalages en ms
  calculés seulement sur les correspondances ; une absence donne `null`, jamais
  un faux zéro. Les manquants et faux positifs restent comptés et pénalisent le F1.
- Les attaques des rythmes mixtes ne sont pas évaluées comme des one-shots isolés.
  Silence et one-shots n'ont pas de tempo de référence ; les fausses boucles y
  sont néanmoins pénalisées. Un silence correctement vide a un F1 de 1.
- Trois essais maximum : gain strict sur le réglage, score de validation non
  dégradé et aucune composante de validation dégradée au-delà de 0,001 BPM,
  0,01 ms ou 0,000001 en F1. Sinon, rejet. Les mesures et lots restent inchangés.
- Deux passages de 30 s par FLAC à 25 % et 60 % de sa durée (bornés à sa fin).
  Comparaison avant/après des mêmes passages ; aucune précision chiffrée sans
  annotations indépendantes, aucune prétendue validation à l'oreille.

## Mise en place

- Base : commit `a371a05`, migration librosa 1.0 déjà présente mais non commitée.
- Tests du corpus : trois échecs avant générateur, puis trois réussites.
- Tests des mesures/extraits : onze échecs sur interfaces non implémentées,
  puis onze réussites. Cas couverts : retard 20 ms, doublons, appariement ambigu,
  absence, silence, tempo moitié, temps invalides, chemins sortant du corpus,
  modèle indisponible, source inchangée et conversion extrait/source.
- Aucune modification d'audio personnel ; seules les fixtures synthétiques
  bénéficient d'une exception locale à la règle Git ignorant les WAV.

## Référence et essais

### Référence, moteur inchangé

Commandes (même environnement pour tous les essais) :

```bash
uv run python tests/corpus/generate.py
uv run python evaluate.py --output tests/corpus/results/baseline-synthetic.json
uv run python evaluate.py --real-root . --output tests/corpus/results/baseline-real.json
```

Lors de cette session, `TORCH_HOME` pointe sur l'espace temporaire approuvé
d'OpenCode, hors du home ; le script choisit aussi un cache temporaire par défaut.
Le premier appel télécharge les poids (pas de nouvelle installation de paquet).
Versions : librosa 1.0.0, beat-this 1.1.0, torch 2.14.0+cpu, soundfile 0.14.0,
NumPy 2.5.3. SHA-256 du modèle :
`8c328b45f59d8dd3dff219253ff6a8d6482be57d0133a29140e2febbf8eb8331`.

| Lot | Score /100 | Erreur tempo BPM | F1 boucles | Décalage boucles ms | F1 shots | Décalage shots ms |
|---|---:|---:|---:|---:|---:|---:|
| Réglage | 97,648992 | 0,227273 | 0,931995 | 5,416667 | 1,000000 | 15,181406 |
| Validation | 88,474233 | 1,457680 | 0,666667 | 7,431973 | 1,000000 | 12,596372 |

Durées cumulées observées : 12,64 s pour les synthétiques (hors téléchargement),
18,38 s pour les extraits réels. Ces temps ne sont pas des garanties de performance.

Constats de réglage : à 90 BPM, la médiane des intervalles quantifiés à 20 ms
donne 90,909 BPM ; plusieurs cas présentent des downbeats supplémentaires
intercalés, donc des faux débuts de boucles. Les one-shots sont tous retrouvés
à 100 ms, mais leur retard moyen reste mesurable. Le score de validation n'est
pas utilisé pour choisir les paramètres d'un essai, seulement pour l'accepter.

### Référence réelle, sans vérité terrain

| Fichier | Passage source (s) | BPM prédit | Candidats boucles |
|---|---|---:|---:|
| 01-Airbag.flac | 71,100–101,100 | 83,3333 | 9 |
| 01-Airbag.flac | 170,640–200,640 | 83,3333 | 9 |
| 07._Jesse_Bru_In_Different_Places.flac | 100,961–130,961 | 130,4348 | 30 |
| 07._Jesse_Bru_In_Different_Places.flac | 242,305–272,305 | 130,4348 | 15 |
| 08_Get_Lucky.flac | 92,407–122,407 | 115,3846 | 14 |
| 08_Get_Lucky.flac | 221,776–251,776 | 115,3846 | 13 |
| B1-Jamming.flac | 53,454–83,454 | 125,0000 | 15 |
| B1-Jamming.flac | 128,291–158,291 | 125,0000 | 17 |

Chaque passage atteint la limite configurée de 128 candidats one-shots : ce
nombre n'est ni une vérité musicale ni un décompte exhaustif des attaques.
Bornes à l'échantillon, positions exactes et empreintes des sources figurent
dans `tests/corpus/results/baseline-real.json`. Empreintes avant/après identiques.
