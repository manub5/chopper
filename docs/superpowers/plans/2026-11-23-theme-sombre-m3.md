# Thème sombre inspiré de Material Design 3 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Moderniser le mode sombre existant sans changer le mode clair ni les fonctionnalités.

**Architecture:** Centraliser palette et règles Qt dans `gui/theme.py` et les
appliquer à la fenêtre existante, sans modifier la palette globale de Qt.

**Tech Stack:** Python 3.12, PySide6, pyqtgraph, pytest.

**Spec:** `docs/superpowers/specs/2026-11-23-theme-sombre-m3-design.md`.

## Global Constraints

- Mode sombre uniquement ; conserver le suivi système et **Force dark mode**.
- Aucune nouvelle bibliothèque, modification du moteur, installation ou écriture audio.
- Commit local en français dans l’espace isolé existant, hooks inchangés.

## Review Focus

- Retour au mode clair : retirer la feuille sombre, sans modifier la palette globale.
- Navigation au clavier : focus visible et contrôles toujours utilisables.
- Champs avec flèches : conserver le menu déroulant et les commandes numériques.
- Contraste : forme d’onde claire et états de sélection/lecture distincts.
- Bascule pendant la lecture : préserver état, données et zoom, comme aujourd’hui.

### Task 1: Appliquer le style à la fenêtre existante

**Files:** `src/chopper/gui/theme.py`, `src/chopper/gui/main_window.py`,
`tests/test_theme.py`, `docs/HISTORIQUE.md`.

**Interfaces:** `ThemePalette.widget_style_sheet() -> str` renvoie une feuille
de style pour le sombre et une chaîne vide pour le clair ;
`ThemePalette.apply_control_styles(parent: QWidget) -> None` applique le style
aux contrôles concernés, à l’ouverture des paramètres et lors d’une bascule.

- [x] **1. Rouge :** étendre les tests Qt pour vérifier le style au passage sombre,
  son retrait au retour clair, la palette globale inchangée et le contraste du
  tracé. Conserver les tests existants de zoom/lecture, vérifier qu’un champ
  stylé et le menu de longueur restent utilisables.
- [x] **2. Observer le rouge :** `uv run pytest -q tests/test_theme.py` ; les
  nouvelles attentes de style doivent échouer avant l’implémentation.
- [x] **3. Implémenter :** palette sombre de la spec, états focus/désactivé et
  arrondis dans `theme.py`, raccord local dans `_apply_theme`. Pas de changement
  d’agencement ni de comportement.
- [x] **4. Vérifier :** mêmes tests puis `uv run pytest -q`, Ruff, mypy et
  `git diff --check`. Inspection d’une capture Qt hors écran sur données
  synthétiques, sans serveur ni usage des réglages réels.
- [x] **5. Livrer :** historique des résultats, commit local `Modernise le thème
  sombre de Chopper`, puis attendre validation utilisateur.
