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

### Essai 1 — moyenne des intervalles réguliers pour le tempo — conservé

- Hypothèse issue du réglage : les intervalles de 90 BPM alternent entre 660 et
  680 ms ; leur médiane favorise 660 ms, donc surestime le tempo. Moyenner les
  intervalles situés à ±25 % de la médiane réduit ce biais tout en excluant les
  temps manquants/ajoutés isolés. Le seuil est fixé avant mesure de validation.
- Test ajouté d'abord rouge : grille à 90 BPM quantifiée à 20 ms, ancien résultat
  90,909 au lieu de 90 ±0,1. Les tests existants d'intervalle aberrant restent verts.
- Première exécution interrompue sans score : sur les one-shots irréguliers, le
  filtre pouvait ne conserver aucun intervalle et produire NaN. Un second test
  rouge reproduit ce cas ; repli sur la médiane si le groupe central est vide.
- Commande : `uv run python evaluate.py --output tests/corpus/results/trial-1-synthetic.json`.

| Lot | Score /100 | Erreur tempo BPM | F1 boucles | Décalage boucles ms | F1 shots | Décalage shots ms |
|---|---:|---:|---:|---:|---:|---:|
| Réglage | 97,720134 | 0,044576 | 0,931995 | 5,416667 | 1,000000 | 15,181406 |
| Validation | 88,860740 | 0,102292 | 0,666667 | 7,431973 | 1,000000 | 12,596372 |

Décision : conservé, score de réglage supérieur, validation supérieure, aucune
composante de validation dégradée. Aucune position de boucle ni attaque déplacée.
Effet possible hors corpus : une véritable variation de tempo reste résumée par
un tempo global ; la moyenne filtrée n'est pas une carte des variations du morceau.
Les caches d'analyse antérieurs ne sont pas invalidés automatiquement ; les
mesures de ce journal n'utilisent aucun cache d'analyse.

### Essai 2 — recaler les boucles sur une attaque locale — rejeté

- Hypothèse : les décalages de quelques ms du lot de réglage viennent de la
  grille temporelle du modèle. Recherche d'une attaque à ±40 ms du downbeat,
  uniquement si la fenêtre débute par au moins 5 ms sous 10 % de son pic ;
  première amplitude à 20 % du pic comme nouveau départ. Pas de changement
  du tempo ni de création de premiers temps supplémentaires.
- Test d'abord rouge : attaque à 0,500 s, downbeat à 0,520 s ; attendu 0,500 s.
  Le test et les tests de candidats passent après implémentation.
- Commande : `uv run python evaluate.py --output tests/corpus/results/trial-2-synthetic.json`.

| Lot | Score /100 | Erreur tempo BPM | F1 boucles | Décalage boucles ms | F1 shots | Décalage shots ms |
|---|---:|---:|---:|---:|---:|---:|
| Réglage | 97,720134 | 0,044576 | 0,931995 | 0,000000 | 1,000000 | 15,181406 |
| Validation | 88,860740 | 0,102292 | 0,666667 | 0,000000 | 1,000000 | 12,596372 |

Décision : rejeté malgré une amélioration du calage. Le score global fixé avant
les essais est inchangé : toutes ces correspondances étaient déjà sous 100 ms.
Le critère validé demande un gain strict de score, pas seulement un gain de
précision à l'intérieur de la tolérance. Le score n'a pas été redéfini après coup.
Cette limite de sensibilité devra être discutée avant une autre campagne.
Code et test expérimentaux retirés du moteur ; leur diff est archivé dans
`tests/corpus/results/trial-2-rejected.diff` pour rendre l'essai reproductible.

### Essai 3 — retour au minimum d'énergie avant les attaques — rejeté

- Hypothèse issue des retards des shots de réglage : `backtrack=True` dans
  `librosa.onset.onset_detect` remonte au minimum précédant le pic, évitant de
  tronquer l'attaque. Option vérifiée dans la documentation/source officielle.
- Test d'abord rouge : trois impulsions isolées à 0,5 / 1,5 / 2,5 s, avec
  départ attendu avant l'attaque et au plus 50 ms avant. Il passe avec l'option.
- Commande : `uv run python evaluate.py --output tests/corpus/results/trial-3-synthetic.json`.

| Lot | Score /100 | Erreur tempo BPM | F1 boucles | Décalage boucles ms | F1 shots | Décalage shots ms |
|---|---:|---:|---:|---:|---:|---:|
| Réglage | 97,720134 | 0,044576 | 0,931995 | 5,416667 | 1,000000 | 8,038549 |
| Validation | 88,860740 | 0,102292 | 0,666667 | 7,431973 | 1,000000 | 10,623583 |

Décision : rejeté pour le même critère strict que l'essai 2, malgré la baisse du
décalage des shots. Le score global reste identique à celui de l'essai 1.
Option et test expérimentaux retirés ; diff conservé dans
`tests/corpus/results/trial-3-rejected.diff`. Aucun quatrième essai.

## Vérification finale

```bash
uv run python evaluate.py --output tests/corpus/results/final-synthetic.json
uv run python evaluate.py --real-root . --output tests/corpus/results/final-real.json
uv run pytest -q
uv run ruff check src tests evaluate.py
uv run ruff format --check src tests evaluate.py
uv run mypy src tests evaluate.py
uv run bandit -qc pyproject.toml -r src evaluate.py -ll
```

La nouvelle exécution synthétique reproduit exactement les prédictions de
l'essai 1 conservé : réglage **97,648992 → 97,720134**, validation
**88,474233 → 88,860740**. Les décalages finaux de boucles restent respectivement
5,416667 et 7,431973 ms sur les correspondances, avec les mêmes faux positifs
qu'à la référence. Aucun gain de calage de boucle n'est revendiqué pour le
moteur finalement livré. Les essais 2 et 3 ne sont pas actifs.

### Passages réels rejoués après l'essai retenu

| Fichier | Début source (s) | BPM avant | BPM après |
|---|---:|---:|---:|
| 01-Airbag.flac | 71,100 | 83,3333 | 84,0164 |
| 01-Airbag.flac | 170,640 | 83,3333 | 83,9018 |
| 07._Jesse_Bru_In_Different_Places.flac | 100,961 | 130,4348 | 128,0488 |
| 07._Jesse_Bru_In_Different_Places.flac | 242,305 | 130,4348 | 128,1356 |
| 08_Get_Lucky.flac | 92,407 | 115,3846 | 116,0896 |
| 08_Get_Lucky.flac | 221,776 | 115,3846 | 116,0896 |
| B1-Jamming.flac | 53,454 | 125,0000 | 123,4818 |
| B1-Jamming.flac | 128,291 | 125,0000 | 123,3154 |

Les bornes des huit passages sont identiques entre les deux exécutions.
Toutes les positions de boucles et shots sont identiques avant/après ; seul
le résumé du tempo change. Les quatre empreintes SHA-256 finales correspondent
à celles mesurées avant la référence. **Ces différences de BPM ne démontrent
pas une meilleure précision sur ces morceaux**, faute de tempo annoté.

Tests : 126 réussis dans le dossier de travail, y compris les quatre tests de
downbeats issus de la migration antérieure. Ruff, formatage, mypy et Bandit
passent ; mypy rappelle sa couverture partielle des fonctions non annotées et
Bandit émet les avertissements de commentaires `nosec` déjà présents.
Les hooks Semgrep et Gitleaks ont également passé les commits créés.

### Décisions d'exécution et limites

- Travail dans la branche de fonctionnalité existante, sans nouveau worktree,
  afin de conserver la migration non commitée et les FLAC accessibles ; risque
  compensé par un ajout Git explicite des seuls fichiers de cette campagne.
- Extraction réelle implémentée avec le banc de mesure, avant les essais, afin
  d'acquérir une véritable référence avant toute modification du moteur.
- Les sources réelles restent non annotées. Les deux rythmes synthétiques de
  validation ne suffisent pas à généraliser à toutes les musiques ; après cette
  campagne, ils ne doivent plus être présentés comme un nouveau lot aveugle.
- La tolérance F1 de 100 ms masque des gains de calage plus fins : essais 2 et 3
  rejetés selon le protocole, mais archivés pour une éventuelle autre campagne
  avec un score continu défini **avant** ses mesures.
- Les résultats réels sont limités à deux passages par source, pas à l'album
  entier, et n'ont pas fait l'objet d'une validation d'écoute.
