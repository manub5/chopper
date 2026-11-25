# Espace de travail des échantillons — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Donner plus de place au tableau, ajouter albums et pistes à la bibliothèque, et simplifier découpe et export.

**Architecture:** Conserver l’arbre Qt, les deux vues d’échantillons et leur état commun. Les recherches réutilisent la piste chargée ; les exports réutilisent l’exporteur existant.

**Tech Stack:** Python 3.12, PySide6, pyqtgraph, pytest, Git et hooks existants.

**Spec:** [Design validé](../specs/2026-11-25-espace-travail-echantillons-design.md).

## Global Constraints

- Travailler dans l’espace isolé existant, base `bed5124`. Respecter `AGENTS.md` : tests, résultat et validation à chaque étape ; petits commits locaux en français, hooks inchangés.
- Aucune écriture sur les sources audio ; aucune dépendance nouvelle ni Qt dans `core/`. Préserver `chopper <fichier>` et une seule piste chargée par fenêtre.
- Ne pas inclure la modification locale de Semgrep, le relevé d’installation, les réglages, les exports ou des secrets dans les commits. Pas d’installation, d’archive ni de push forcé.

## Review Focus

1. Petite fenêtre : les zones restent utilisables malgré les réductions et la poignée de glisser-déposer reste accessible après redimensionnement des colonnes (tâche 1).
2. La borne 64 survit à un aller-retour dans les réglages ; une ancienne configuration reste compatible (tâche 1).
3. Deux albums homonymes mais de chemins distincts, ajout répété du même dossier, puis sélection d’une piste seule : ordre stable, pas de doublon ni de cible d’album périmée (tâche 2).
4. Un clic droit sur un échantillon non marqué ou sur une zone vide ne doit ni exporter le mauvais contenu ni démarrer une lecture (tâche 3).
5. Une recherche échouée ou un résultat tardif ne doit pas remplacer des résultats valides ni écraser une autre piste (tâche 4).

### Task 1: Disposition et limite de 64

**Files:** `src/chopper/gui/main_window.py`, `candidates_panel.py`, `settings_dialog.py` dans le même dossier, `src/chopper/core/settings.py` ; `tests/test_main_window.py`, `tests/test_candidates_panel.py`, `tests/test_settings.py`, `tests/test_settings_dialog.py`, `README.md`.

**Interfaces:** `Settings.candidates_per_track` garde son nom, défaut 8, bornes 1–64 ; les workers le transmettent déjà par catégorie.

- [ ] Écrire des tests : `test_sample_workspace_prioritizes_table_height` compare les trois zones à taille identique avec les proportions de référence relevées avant changement (≈ 1/2, 2/3 et somme de la place libérée, hors minimums) ; à petite taille, vérifier l’accès au tableau et au scroll. Mettre à jour les anciens tests exigeant une onde plus haute que la liste. `test_all_sample_columns_can_be_resized` teste chaque section dans les deux sens, poignée incluse. Tester `Settings()` = 8, 64 sauvegardé/rechargé et 65 ramené à 64, y compris la borne du champ numérique.
- [ ] Rouge : `uv run --no-sync pytest -q tests/test_main_window.py tests/test_candidates_panel.py tests/test_settings.py tests/test_settings_dialog.py` ; constater les écarts de taille et limites existantes.
- [ ] Ajuster les hauteurs du conteneur droit en conservant les tailles minimales, et non la hauteur interne de chaque rectangle. Passer les colonnes en mode interactif, garder leurs largeurs initiales utiles et permettre le défilement horizontal. Partager la constante de limite entre réglages et widget ; documenter 8 par défaut, 64 maximum.
- [ ] Relancer les tests ciblés et la suite ; comparer le rendu Qt hors écran à taille identique, aussi en fenêtre réduite. Commit `Agrandit la liste des échantillons et relève sa limite` ; présenter les résultats, attendre validation.

### Task 2: Albums ajoutés et piste seule

**Files:** `src/chopper/gui/library_panel.py`, `main_window.py`, `actions.py`, `tests/test_library_panel.py`, `test_main_window.py`, `test_actions.py`, `test_app.py`, `README.md`.

**Interfaces:** `LibraryPanel.add_album(path: Path) -> None` et `add_track(path: Path) -> None` ajoutent des entrées de session, sans déclencher un signal de sélection par leur seul ajout. `MainWindow.open_file(path: Path) -> None` conserve son contrat.

- [ ] Tester deux dossiers « Album » distincts en fin d’arbre avec chemins visibles, réajout sans doublon, expansion sans scan récursif, et scroll si débordement. Tester **Open track…** avec un vrai WAV temporaire, nom seul, une seule analyse et aucun album résiduel à analyser. Couvrir annulation, réouverture, échec de lecture et CLI.
- [ ] Rouge : `uv run --no-sync pytest -q tests/test_library_panel.py tests/test_main_window.py tests/test_actions.py tests/test_app.py`.
- [ ] Ajouter **Add album…** et **Open track…** à l’interface existante avec les gardes d’analyse. Garder **Open library…** et sa racine mémorisée. Réutiliser l’ouverture CLI, ajouter uniquement les pistes seules acceptées, réutiliser l’élément de bibliothèque si déjà présent. Les ajouts ne sont pas sauvegardés ; aucune seconde piste ni résultat d’album mélangé à l’affichage.
- [ ] Relancer tests ciblés et complets. Commit `Ajoute des albums et des pistes à la bibliothèque de session` ; présenter les résultats, attendre validation.

### Task 3: Export d’un échantillon au clic droit

**Files:** `src/chopper/gui/candidates_panel.py`, `sample_lanes.py`, `main_window.py`, `tests/test_candidates_panel.py`, `test_sample_lanes.py`, `test_main_window.py`, `README.md`.

**Interfaces:** les deux vues émettent `sample_export_requested = Signal(int)` ; `MainWindow._on_sample_export_requested(item_id: int) -> None` résout l’identifiant dans l’état actuel et réutilise `_export_candidates`.

- [ ] Tester **Export** sur la ligne ou le rectangle sous le clic, distinct de l’échantillon actif ; vérifier les données d’un seul fichier exporté, l’absence d’écrasement, de nouvelle lecture et de changement de marquage. Tester zone vide, menu annulé et identifiant devenu obsolète.
- [ ] Rouge : `uv run --no-sync pytest -q tests/test_candidates_panel.py tests/test_sample_lanes.py tests/test_main_window.py tests/test_exporting.py`.
- [ ] Ajouter les menus contextuels avec le ciblage des vues existantes, y compris quand elles sont défilées. Ignorer les demandes pendant une opération qui verrouille l’état. Réutiliser le choix du dossier et l’export par identifiant ; ne pas modifier les exports groupés.
- [ ] Relancer tests ciblés et complets. Commit `Exporte un échantillon depuis les deux vues` ; présenter les résultats, attendre validation.

### Task 4: Découpe directe et changement de Length

**Files:** `src/chopper/gui/selection_controller.py`, `main_window.py` si nécessaire, `tests/test_selection_controller.py`, `test_manual_selection.py`, `test_main_window.py`, `README.md`, `docs/HISTORIQUE.md`.

**Interfaces:** `SelectionController.request_chop() -> bool` et `set_length(bars: float) -> None` conservent leur signature ; les recherches passent par `_begin` et le worker existant.

- [ ] Tester deux découpes successives sans dialogue, changement de longueur avec et sans sélection, sélection courante différente de la dernière zone découpée, et aucune relance si la valeur est identique. Tester recherche échouée, ancien résultat ignoré et conservation des confirmations pour les autres transitions.
- [ ] Rouge : `uv run --no-sync pytest -q tests/test_selection_controller.py tests/test_manual_selection.py tests/test_main_window.py`.
- [ ] Supprimer la confirmation uniquement pour la découpe et sa relance par **Length**. Réutiliser les données en mémoire ; ne remplacer les échantillons qu’à réception d’un résultat valide. Garder le blocage de la commande pendant la recherche, sans créer de tâche concurrente.
- [ ] Relancer tests ciblés et complets, mettre à jour l’historique et la documentation. Commit `Relance la découpe sans confirmation superflue` ; présenter les résultats, attendre validation.

### Task 5: Intégration et publication

- [ ] Revue indépendante du lot et correctifs éventuels avec régression reproduite. Vérifier la suite, Ruff, mypy, Bandit et tous les hooks. Conserver le dossier et les données utilisateur intacts.
- [ ] Vérifier la branche cible et l’état distant avant publication. Intégrer par avance rapide quand possible ; si les historiques ont divergé, intégrer sur un espace isolé et revérifier avant de déplacer une branche de production. Ne rien masquer avec un push forcé. Préserver mot pour mot le fichier Semgrep modifié dans `Magic_sampler` ; arrêter si l’intégration locale ne peut pas le garder intact.
- [ ] Examiner la liste des fichiers suivis qui seront publiés et analyser **tous les commits sortants** avec Gitleaks, rapports masqués. Ne pas publier si le contrôle échoue ou si des données privées sont repérées. Vérifier les tests et les hooks sur le résultat intégré avant le push.
- [ ] Pousser uniquement vers la branche de production confirmée. Vérifier la référence distante après le push. Rapporter la branche, le commit, les tests et le résultat de l’audit ; pas de release automatique.
