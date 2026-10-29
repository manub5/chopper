# Évaluation audio — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construire une mesure reproductible et mener au maximum trois essais
d'amélioration, puis observer les quatre FLAC sans inventer de vérité terrain.

**Architecture:** Un générateur indépendant produit les WAV et leurs annotations.
`evaluate.py` sépare les mesures pures de l'exécution des modules `core/`.
Le journal conserve les mesures avant/après, y compris les essais rejetés.

**Tech Stack:** Python 3.12, NumPy, soundfile, beat_this, librosa 1.0, pytest, uv.

**Spec:** `docs/superpowers/specs/2026-10-29-evaluation-audio-design.md`.

## Global Constraints

- Vraie inférence dans les évaluations ; aucun cache d'analyse ni mock de modèle.
- Au maximum trois essais ; séparation réglage/validation fixée avant mesure.
- Aucune modification ni mise sous Git des quatre FLAC personnels.
- Aucun nouveau dossier dans le home ; réutiliser l'espace temporaire approuvé
  pour les extraits et, si nécessaire, le téléchargement du modèle.
- Conserver les modifications non commitées déjà présentes : migration librosa,
  documentation et tests de downbeats. Ne pas les inclure dans les commits d'essais.
- Une hypothèse par essai et un commit par correctif effectivement retenu.

## Review Focus

- Aucune détection : pénalité explicite, jamais un faux décalage nul.
- Doublons : une annotation ne justifie pas plusieurs détections.
- Silence/one-shot sans rythme : tempo non applicable, fausses boucles comptées.
- Extrait FLAC : indices locaux reconvertis en positions dans la source.
- Modèle indisponible : erreur explicite, aucun résultat simulé substitué.

---

### Task 1: Corpus reproductible

**Files:** créer `tests/corpus/generate.py`, `tests/corpus/truth.json`, dix WAV
synthétiques et `tests/test_corpus.py` ; ajouter une exception WAV limitée à
`tests/corpus/` dans `.gitignore`.

**Interfaces:** `generate_corpus(destination: Path) -> Path` retourne le chemin du
JSON. Celui-ci porte une version de schéma et, par cas, `id`, `file`, `split`,
`kind`, `sample_rate`, `tempo_bpm`, `beat_samples`, `loop_start_samples` et
`onset_samples`. Les secondes dérivent uniquement des indices/fréquence annotés.

- [ ] Écrire d'abord les tests : deux générations ont les mêmes empreintes ;
  annotations dans les bornes ; tempo et départ décalé retrouvés à l'échantillon
  sur un cas simple ; silence réellement nul ; lot de validation distinct.
- [ ] Exécuter `uv run pytest tests/test_corpus.py` et constater l'échec initial.
- [ ] Implémenter dix cas nommés, avec graine fixe et synthèse sans dépendance au
  détecteur : réglage à 90/120/150 BPM, validation à 105/135 BPM, variantes
  d'accentuation/départ, deux cas de one-shots et deux de silence.
- [ ] Relancer les tests, générer les fichiers demandés et vérifier que seules les
  sorties synthétiques sont couvertes par l'exception Git.

### Task 2: Mesures et ligne de commande

**Files:** créer `evaluate.py`, `tests/test_evaluate.py`, `JOURNAL_EVAL.md`.

**Interfaces:** `match_events(reference: list[float], detected: list[float],
tolerance_seconds: float) -> dict` ; `score_case(truth: dict, detection: dict)
-> dict` ; `evaluate_corpus(corpus: Path, split: str, device: str) -> dict`.
Le CLI accepte `--corpus`, `--split`, `--device cpu`, `--output` et `--real-root`.

- [ ] Écrire les tests des mesures sur des valeurs calculées à la main :
  correspondances exactes, retard de 20 ms, doublons, absence de détection,
  faux positifs et mesures non applicables.
- [ ] Observer leur échec ; implémenter appariement un-à-un et agrégation par
  famille, pour qu'un morceau riche en attaques ne domine pas tous les autres.
- [ ] Définir le score global comme moyenne des composantes applicables :
  score tempo `max(0, 1 - erreur_relative)`, F1 des débuts de boucles, F1 des
  attaques ; multiplier par 100. Rapporter aussi le décalage moyen et les
  nombres de détections manquantes/fausses. Ne pas masquer les cas sans résultat.
- [ ] Ajouter les tests d'exécution : erreur explicite si modèle indisponible,
  sélection correcte des lots, chemins relatifs sûrs, sortie JSON finie.
- [ ] Brancher les vrais modules `core/` et lancer la référence sur les deux lots.
  Journaliser versions, modèle, paramètres et scores détaillés avant modification.

### Task 3: Essais mesurés, maximum trois

**Files:** modifier seulement les modules de détection justifiés par les mesures,
leurs tests existants et `JOURNAL_EVAL.md`.

**Interfaces:** conserver les interfaces publiques de `core/rhythm.py`,
`core/onsets.py` et `core/candidates.py` ; aucun accès à la vérité dans le moteur.

- [ ] Lire les erreurs du lot de réglage et choisir une seule hypothèse pour
  chaque essai, sans choisir les paramètres en regardant les cas de validation.
- [ ] Écrire et observer rouge le test reproduisant le défaut ciblé, puis
  implémenter la correction minimale.
- [ ] Relancer exactement les évaluations de référence ; consigner chaque
  composante et appliquer les critères de conservation de la spécification.
- [ ] Si rejet, retirer uniquement les changements de cet essai, garder son
  résultat au journal ; si conservation, lancer `uv run pytest`, les contrôles
  qualité et créer le commit dédié sans contourner les hooks.
- [ ] Arrêter au troisième essai même si aucune amélioration n'est conservée.

### Task 4: Passages réels et vérification finale

**Files:** compléter `evaluate.py`, `tests/test_evaluate.py`, `JOURNAL_EVAL.md`.

**Interfaces:** `evaluate_real_passages(root: Path, device: str) -> dict`, résultat
par source et passage avec `ground_truth: null`, bornes, tempo prédit et positions.

- [ ] Avant modification du moteur, relever les durées et figer deux passages
  de 30 s par FLAC (vers 25 % et 60 % de sa durée, bornés à la fin du fichier) ;
  conserver les observations de référence sur ces passages.
- [ ] Écrire d'abord les tests de lecture partielle, conversion local/source,
  fichier trop court, source inchangée et absence de faux score sans vérité.
- [ ] Observer l'échec puis implémenter l'analyse des extraits temporaires,
  jamais des réécritures ou exports sur le chemin de la source.
- [ ] Rejouer les mêmes passages avec la version retenue ; comparer les sorties,
  vérifier les empreintes des quatre originaux et noter les limites d'écoute.
- [ ] Utiliser verification-before-completion ; lancer `uv run pytest`, Ruff,
  mypy, Bandit, l'évaluation finale des deux lots et `git diff --check`.
- [ ] Présenter les scores avant/après, les essais rejetés et les résultats
  réels non annotés ; attendre validation avant toute autre étape du projet.

## Auto-revue du plan

- Couverture : corpus/JSON, métriques, inférence réelle, lots indépendants,
  trois essais bornés, journal et quatre sources réelles sont pris en charge.
- Les limites de fichiers et signatures sont définies ; les cinq risques
  ci-dessus ont un test dans les tâches correspondantes.
- La référence réelle doit être acquise avant les essais de la tâche 3 :
  exécuter les étapes préparatoires de la tâche 4 dès que le CLI est disponible.
- Aucun gain n'est promis ; une absence de modèle ou une régression est un
  résultat à signaler, pas une raison de fabriquer un score.
