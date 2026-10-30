# Catégories complètes et zoom borné — Implementation Plan

Statut : validé par l'utilisateur ; réalisation et vérifications effectuées.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans.
> Une seule livraison vérifiable ; attendre la validation utilisateur après celle-ci.
> Ne pas démarrer l'étape 6 de la refonte dans ce travail.

**Goal:** Rendre disponibles 1, 1/2 et 1/4 de mesure sans éviction entre catégories,
avec 8 samples au maximum par catégorie, et limiter la navigation au morceau entier.

**Architecture:** Conserver les downbeats, la durée médiane d'une mesure, les
scores et le cache existants. Sélectionner séparément les meilleurs candidats
de chaque longueur, migrer les réglages une fois puis préserver les choix futurs.
La vue de l'onde porte les limites temporelles communes utilisées par les couloirs.

**Tech Stack:** Python 3.12, PySide6, pyqtgraph, NumPy, pytest ; aucune dépendance ajoutée.

**Spec:** `docs/SPEC.md`, `docs/REFONTE_INTERFACE.md` et accord utilisateur sur
8 candidats par catégorie, soit 32 au maximum lorsque les trois longueurs sont activées.

## Global Constraints

- Sources audio en lecture seule ; stéréo et fréquence inchangées pour lecture/export.
- Aucun import Qt dans le moteur ; aucun changement de détecteur, de score ou de grille.
- Couloirs ordonnés : 1 mesure, 1/2 mesure, 1/4 de mesure, one-shots.
- Zoom/pan horizontaux seuls, amplitude figée et bouton A masqué.
- Une catégorie peut rester vide si aucun candidat valide n'est possible ; ne pas fabriquer de résultat.
- Ne pas modifier directement le fichier de paramètres utilisateur pendant les tests.

## Diagnostic déjà effectué

- Paramètres réellement enregistrés : `loop_lengths_bars = [1.0]`, quota 8.
- Piste 16, analyse en cache : avec `(1,)`, 8 boucles d'1 mesure ; avec `(0.5,1)`,
  8 demi-mesures et aucune boucle d'1 mesure, à cause du classement global.
- `WaveformView` ne définit actuellement aucune limite X ; la molette des couloirs
  appelle `setXRange` sans borne. Les marges d'auto-cadrage débordent déjà du morceau.

## Review Focus

1. Une catégorie mieux notée ne doit pas évincer les autres : scénario de scores déséquilibrés.
2. Ancien réglage `[1]`, puis choix volontaire d'une seule longueur après migration : respecter les deux étapes.
3. Piste courte/sans downbeats : moins de 32 résultats est normal, aucune borne audio dépassée.
4. Alternance piste courte/longue : actualiser les limites X dans les deux sens sans écraser le cadrage Y.
5. Molette/pan des deux vues, resize et écran à 150 % : temps borné et alignement conservés.

## Task 1: Catégories représentées et navigation dans les bornes audio

**Fichiers :**
- Modifier `src/choppeur/core/models.py`, `core/candidates.py`, `core/settings.py`,
  `core/naming.py`, `gui/settings_dialog.py`, `gui/presentation.py`,
  `gui/candidates_panel.py`, `gui/lane_layout.py`, `gui/sample_lanes.py`, `gui/waveform_view.py`.
  Les chemins `core/` et `gui/` désignent `src/choppeur/core/` et `src/choppeur/gui/`.
- Adapter leurs tests dans `tests/`, notamment `test_workers.py` et `test_main_window.py`.
- Mettre à jour le suivi de la refonte et `docs/HISTORIQUE.md` après vérification.

**Interfaces :**
- `LOOP_LENGTHS_BARS = (0.25, 0.5, 1.0)` ; `Candidate.bars: float | None` inchangé.
- `find_loop_candidates(..., lengths_bars: tuple[float, ...], max_candidates: int)` :
  `max_candidates` limite chaque longueur, puis résultat fusionné trié par score.
  Pour N=8 et trois longueurs, au plus 24 boucles ; shots inchangés, au plus 8.
- Garder la clé TOML `candidates_per_track` pour compatibilité, avec sémantique
  par catégorie et valeur normalisée entre 1 et 8. Libellé GUI corrigé.
- Ajouter `Settings.loop_lengths_version: int = 2`. Dans `from_dict`, version
  absente, invalide ou <2 : réactiver les trois longueurs et passer à 2.
  Version 2 : filtrer les longueurs autorisées, dédupliquer, conserver les choix
  valides et rétablir toutes les longueurs seulement si aucun choix valide ne reste.
  Sauvegarde via le chemin habituel, pas d'écriture automatique au chargement.
- Le sélecteur fermé propose les sept sous-ensembles non vides de trois longueurs,
  les trois ensemble en premier et par défaut ; comparaison `itemData` en Python.
- Ajouter `sample_type_label(candidate: Candidate) -> str` dans `gui/presentation.py`
  pour les libellés cohérents de la table et des info-bulles, y compris « Boucle 1/4 de mesure ».
- `CATEGORIES` ajoute `('loop', 0.25)` avant `('shot', 0.0)`.
- `WaveformView.set_waveform` configure `ViewBox.setLimits(xMin=0, xMax=duration,
  maxXRange=duration)` et cadre X exactement sur `[0,duration]` sans padding.
  Les limites sont remplacées à chaque chargement avant le cadrage ; Y reste ajusté
  puis figé. Les couloirs gardent leur transformation issue de l'onde.

- [x] **1. Tests rouges — catégories :** signal synthétique assez long avec au
  moins 8 départs valides par longueur : compter 8 candidats pour chacune de
  `{0.25,0.5,1.0}`, y compris quand une longueur domine les scores. Tester quotas
  1 et 8, absence de downbeats, piste trop courte, durée quart = durée mesure /4.
  Tester les noms `0.25bars`, libellés, placement et clic d'un rectangle quart.
  Exemple déterministe, sans modèle audio ni mock de sélection :
  ```python
  result = find_loop_candidates(np.ones(18000), 1000, 120.0,
                               tuple(float(t) for t in range(0, 18, 2)),
                               lengths_bars=(0.25, 0.5, 1.0), max_candidates=8)
  assert Counter(c.bars for c in result) == {0.25: 8, 0.5: 8, 1.0: 8}
  assert {(c.bars, c.duration_seconds) for c in result} == {
      (0.25, 0.5), (0.5, 1.0), (1.0, 2.0)
  }
  ```
- [x] **2. Tests rouges — paramètres :** ancien TOML `[1]` sans version devient
  les trois longueurs ; save/load répété stable ; après migration, choisir `(1,)`
  explicitement reste `(1,)` au rechargement. Tester les sept choix, quota ancien
  >8 ramené à 8, conservation des préférences audio/auto/thème et absence d'écriture au load.
- [x] **3. Observer le rouge :** `uv run pytest -q tests/test_candidates.py
  tests/test_settings.py tests/test_settings_dialog.py tests/test_naming.py
  tests/test_candidates_panel.py tests/test_lane_layout.py tests/test_sample_lanes.py`.
  Attendu : échecs sur catégories, quotas et migration absents.
- [x] **4. Implémenter les contrats de catégories et paramètres**, sans modifier
  la formule de score. Vérifier via le worker réel qu'une analyse en cache refournit
  les trois longueurs ; pas de cache des anciens candidats à invalider.
- [x] **5. Tests rouges — zoom :** au chargement, X vaut exactement `[0,durée]` ;
  dézoomer plusieurs fois depuis l'onde ou les couloirs ne déborde pas. À zoom
  partiel, pan extrême à gauche/droite reste dans les bornes ; Y ne change pas.
  Rejouer sur pistes courte→longue→courte, resize et alignement à 150 %.
  Exemple pour une piste de 3 secondes :
  ```python
  view.set_waveform(np.ones(3000), 1000)
  view.setXRange(-100, 100, padding=0)
  assert view.viewRange()[0] == pytest.approx([0.0, 3.0])
  ```
- [x] **6. Observer le rouge puis borner la vue source :**
  `uv run pytest -q tests/test_waveform_view.py tests/test_sample_lanes.py`.
  Adapter les tests d'alignement qui demandaient jusqu'ici une plage hors morceau :
  tester maintenant la plage effectivement bornée, pas un dépassement autorisé.
- [x] **7. Porte complète :** `uv run pytest -q` ; Ruff check et format sur
  `src tests prototypes evaluate.py`, mypy mêmes chemins, Bandit `-qc pyproject.toml
  -r src prototypes evaluate.py -ll`, `git diff --check`. Attendu : aucune erreur,
  seuls avertissements préexistants. Référence avant changements : 232 tests.
- [x] **8. Validation réelle et commit :** sur le FLAC 16 en lecture seule,
  avec ses paramètres migrés en mémoire, relever les comptes par catégorie ;
  capture Wayland avec les quatre couloirs si candidats disponibles. Ne pas
  prétendre valider matériellement l'audio avec un lecteur simulé.
  Commit : `Garantit les catégories de samples et borne la navigation au morceau`.
  Présenter les tests, la migration et la capture ; attendre validation, sans étape 6.

**Preuves :** 269 tests réussis (37 nouveaux), porte complète réussie ; 15 tests
graphiques réussis à 150 %. Piste 16 réelle : 8 boucles d'1 mesure, 8 demi-mesures,
8 quarts de mesure et 8 one-shots. Après demande de dézoom hors bornes, plage
effective `[0, 206.47183673469388]`, exactement la durée audio. Capture native
Wayland réalisée ; paramètres utilisateur et audio source restés inchangés pendant
ce contrôle. La migration sera utilisée au prochain chargement des paramètres,
sans réécriture automatique. Attendre validation avant de reprendre la refonte.
