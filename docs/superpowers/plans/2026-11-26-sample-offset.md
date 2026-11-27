# Ajustement temporaire des bornes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ajuster séparément le début et la fin de chaque sample, sans changer la vitesse ou la hauteur.

**Architecture:** Le moteur calcule les nouvelles bornes en trames sans dépendre de Qt. `SampleState` conserve la découpe d’origine et expose le candidat effectif aux vues, à la préécoute et aux exports. Le tableau émet une demande d’édition par identifiant stable ; `MainWindow` contrôle sa validité et l’état de la session.

**Tech Stack:** Python 3.12, PySide6, NumPy, SoundFile, pytest.

**Spec:** [Design révisé](../specs/2026-11-26-sample-offset-design.md).

## Global Constraints

- À livrer et valider avant les options CLI. Ne pas modifier la CLI, le BPM, les préférences ou le cache.
- Saisie numérique en millisecondes entières, sans molette ni curseur ; `0` restaure la seule borne éditée. Refuser toute paire hors piste, inversée ou vide ; ne pas la limiter à la sélection de découpe.
- Ne rien écrire lors d’une édition ; préserver l’audio source et les exports précédents. Utiliser exclusivement des médias synthétiques dans les tests.
- Tests rouge puis vert, suite complète, commit local en français avec hooks et validation utilisateur avant la suite.

## Review Focus

1. À 44,1 kHz, vérifier l’arrondi séparé, la durée résultante et le refus lorsque les deux bornes coïncident après arrondi.
2. Modifier une ligne qui n’est pas active après tri : seul son identifiant change de position, sans lecture ni sélection parasite.
3. Redécouper alors qu’un ancien identifiant existe : il ne doit plus pouvoir être édité.
4. Modifier un sample en lecture et un autre : arrêter uniquement la lecture du sample modifié, sans démarrer de lecture.
5. Exporter à nouveau après décalage : contrôler le contenu des nouveaux fichiers et les octets de l’ancien export.

### Task 1: Édition, préécoute et export d’un sample aux bornes ajustées

**Files:** créer `src/chopper/core/sample_offset.py` et `tests/test_sample_offset.py` ; modifier `src/chopper/gui/presentation.py`, `sample_state.py`, `candidates_panel.py`, `main_window.py`, les tests correspondants, `README.md` et `docs/HISTORIQUE.md`.

**Interfaces:** `adjust_candidate_bounds(candidate: Candidate, start_offset_ms: int, end_offset_ms: int, sample_rate: int, frame_count: int) -> Candidate` part du candidat d’origine. `SampleState.set_boundary_offset(item_id: int, boundary: Literal["start", "end"], offset_ms: int) -> bool` renvoie `False` pour un identifiant absent et lève `ValueError` pour un résultat invalide. `SampleItem` expose `candidate` (effectif), `start_offset_ms` et `end_offset_ms`. `CandidatesPanel.boundary_edit_requested` transmet l’identifiant et la borne à `MainWindow`.

- [ ] Écrire `test_adjust_bounds_independently` et `test_adjust_bounds_rejects_invalid_pair`. À 44 100 Hz, `[11025, 22050)` avec `(-20, +30)` donne `[10143, 23373)` et avec `(+20, -30)` donne `[11907, 20727)`. `(0, 0)` rend le candidat d’origine. Vérifier sortie à chaque bord de piste, inversion et égalité exacte ou après arrondi.
- [ ] Écrire les tests de `SampleState` : appliquer `-20` au début, `+30` à la fin, puis `0` au début ; la fin reste décalée et le candidat d’analyse reste inchangé. Vérifier que remplacer `+30` par `+20` ne cumule pas, que marques et identifiant actif sont conservés et qu’une nouvelle découpe réinitialise les offsets et invalide les anciens identifiants. Arrêter uniquement la préécoute du sample édité, sans en démarrer une nouvelle.
- [ ] Écrire les tests Qt : modifier le début d’une ligne non active après tri ; vérifier **Position**, **Length** et le rectangle. Modifier sa fin ; **Length** et le bord droit changent, **Position** ne change pas. Tester `Échap`, texte invalide, résultat hors piste ou vide et interface verrouillée. Vérifier le tri numérique et la poignée de glisser-déposer après ajout des colonnes.
- [ ] Écrire un test d’intégration sur un signal synthétique dont l’amplitude varie selon la trame : comparer la préécoute et les nouveaux WAV (export et dépôt) aux trames attendues, à la quantification près. Vérifier que les octets du WAV préexistant restent identiques.
- [ ] Lancer `QT_QPA_PLATFORM=offscreen uv run --no-sync pytest -q tests/test_sample_offset.py tests/test_sample_state.py tests/test_candidates_panel.py tests/test_main_window.py tests/test_sample_lanes.py` ; attendre des échecs pour l’interface et la fonction absentes, sans autres régressions.
- [ ] Implémenter `adjust_candidate_bounds` : ajouter à chaque borne d’origine son propre décalage arrondi en trames, puis exiger `0 <= start < end <= frame_count`. Garder les métadonnées du candidat sans rééchantillonnage. Dans `SampleState`, remplacer seulement l’élément visé et émettre `changed` sans réinitialiser les identifiants ou les marques.
- [ ] Ajouter **Start offset (ms)** et **End offset (ms)** après **Position**, avant la poignée de dépôt. Ouvrir sur double-clic ou `F2` depuis la cellule, avec un champ texte numérique, sans déclencher de préécoute. Valider la saisie entière signée et la paire résultante au moment de l’appliquer. Mettre à jour les cellules par identifiant et trier après mise à jour. Les consommateurs audio utilisent le candidat effectif de `SampleState`.
- [ ] Relancer le ciblage puis `QT_QPA_PLATFORM=offscreen uv run --no-sync pytest -q` ; aucun échec. Vérifier Ruff, mypy, Bandit et `git diff --check`. Documenter les limites, commiter `Permet d’ajuster séparément les bornes des samples`, puis attendre validation avant la CLI.
