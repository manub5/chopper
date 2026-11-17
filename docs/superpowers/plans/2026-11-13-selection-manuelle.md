# Sélection manuelle — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sélectionner et préécouter un passage, y chercher des samples sans réanalyse et protéger les résultats avant tout abandon.

**Architecture:** Les fonctions core conservent l'origine temporelle de la piste et reçoivent une fenêtre optionnelle. Des composants GUI distincts prennent en charge les gestes, l'état de lecture, le reclassement en worker et les confirmations ; MainWindow les raccorde sans devenir propriétaire des règles de sélection. LoadedTrack conserve les mêmes objets audio/Analysis ; seuls ses candidats changent.

**Tech Stack:** Python 3.12, NumPy, PySide6, pyqtgraph 0.14, sounddevice existant, pytest ; aucune dépendance nouvelle.

**Spec:** `docs/superpowers/specs/2026-11-13-selection-manuelle-design.md` (validé le 13/11/2026).

## Global Constraints

- Aucun nouvel appel beat_this, détection d'attaques, décodage ou chargement audio pour Chop selection et Whole track.
- Core reçoit seulement une fenêtre `(start, end)` optionnelle en plus, aucun import Qt.
- Temps et candidats gardent l'origine piste ; source audio en lecture seule, stéréo/fréquence préservées.
- Longueurs supportées : 0.25, 0.5, 1, 2, 4 ; automatique/Settings/migration version 3 restent 0.25, 0.5, 1.
- Longueurs 2 et 4 admises par la recherche seulement avec fenêtre explicite ; export/affichage les acceptent.
- Quotas Settings.candidates_per_track (1 à 8) respectés séparément pour boucles et one-shots ; Settings.max_one_shot_seconds conservé.
- Alt suspend l'aimantation aux downbeats ; milieu/Maj+molette déplacent, molette zoome horizontalement, axe y figé.
- Lecture au relâchement seulement si Auto-preview ; un seul flux et des jetons communs à toutes les préécoutes.
- Échap/clic extérieur/Whole track partagent la confirmation, même avant la première découpe ; Export and return désactivé sans résultats manuels.
- Nouveau Chop, autre piste, analyse d'album et fermeture protègent aussi les résultats manuels, même après un export via les boutons existants.
- Annulation/échec/échec partiel d'export conservent région, résultats et marques ; fichiers déjà écrits jamais supprimés.
- Interface et aide en anglais ; code/commentaires anglais ; documentation interne et commits en français.
- Sélection/longueur manuelle transitoires, aucun nouveau réglage TOML ni écriture de cache d'analyse.
- Une étape testée puis validée par l'utilisateur avant la suivante ; hooks existants intacts ; aucune publication ni reconstruction de ZIP implicite.

## Review Focus

1. Échec partiel, fermeture de dialogue et événements réentrants : aucune perte de sélection/résultats ni seconde exportation (tâche 5).
2. Fin de lecture ou résultat de worker ancien : ne pas effacer/remplacer une sélection ou lecture plus récente, ni libérer un thread vivant (tâches 3–5).
3. LinearRegionItem émet une fin après setRegion programmatique ; Alt change et les poignées reçoivent leurs propres événements : pas de fausse lecture ou perte d'aimantation (tâche 2).
4. Audio très fort ou non fini hors fenêtre, et bloc de silence chevauchant sa fin : classement local sans lire/scorer hors zone (tâche 1).
5. Élargir la constante partagée ne doit ni réactiver des réglages 2/4 historiques, ni cacher les nouveaux samples, ni intercepter C/Échap dans les champs et modales (tâches 1 et 5).

## Structure des fichiers et contrats

- Modifier `core/models.py`, `core/candidates.py`, `core/settings.py` : longueurs et fenêtre, sans Qt.
- Modifier `core/naming.py` si nécessaire, `gui/presentation.py`, `gui/lane_layout.py`, `gui/sample_lanes.py` : affichage/export de 2/4 mesures et catégories.
- Créer `gui/selection_geometry.py` : normalisation/aimantation, fonctions pures sans événements.
- Créer `gui/selection_viewbox.py` : ViewBox de sélection/navigation ; `gui/waveform_view.py` garde la région et distingue gestes/programmation.
- Modifier `gui/sample_state.py` : cible de préécoute et remplacement des candidats ; lecteur sounddevice existant conservé.
- Modifier `gui/workers.py` et `gui/presentation.py` : reclassement local et résultat identifié.
- Créer `gui/selection_controller.py` : état et transitions, sans accès disque ni import MainWindow.
- Créer `gui/selection_dialog.py` : décision export/abandon/annulation uniquement.
- Modifier `gui/main_window.py`, `gui/actions.py` : raccordement et actions ; extraire le résultat booléen de l'export existant sans en dupliquer le pipeline.
- Tests nouveaux : `tests/test_candidate_window.py`, `tests/test_selection_geometry.py`, `tests/test_waveform_selection.py`, `tests/test_selection_controller.py`, `tests/test_manual_selection.py`.
- Étendre les tests existants candidats/Settings/nommage/prélecture/couloirs/workers/actions/fenêtre ; documentation README, historique et recette finale.

Notation du plan : `Window = tuple[float, float]` dans `gui/presentation.py` pour les composants GUI ; le moteur utilise l'annotation tuple directement, sans importer GUI. Fenêtre valide : nombres réels finis non booléens, `0 <= start < end <= len(samples)/sample_rate`.

## Task 1: Recherche bornée et longueurs manuelles compatibles

**Files:** modifier `src/chopper/core/{models,candidates,settings,naming}.py`, `src/chopper/gui/{presentation,lane_layout,sample_lanes}.py` ; créer `tests/test_candidate_window.py` ; étendre `tests/test_candidates.py`, `tests/test_settings.py`, `tests/test_naming.py`, `tests/test_candidates_panel.py`, `tests/test_sample_lanes.py`, `tests/test_lane_layout.py`.

**Interfaces:** produire `LOOP_LENGTHS_BARS=(0.25,0.5,1.0,2.0,4.0)` et `AUTO_LOOP_LENGTHS_BARS=(0.25,0.5,1.0)` dans models. Ajouter `window: tuple[float,float] | None = None` comme argument keyword-only aux deux fonctions existantes de candidates, sans autre changement de signature publique. `DEFAULT_LOOP_LENGTHS_BARS` et la validation Settings utilisent l'ensemble automatique, pas la constante élargie.

- [x] **1. Tests rouges moteur :** utiliser des tableaux réels, notamment cet oracle :

  ```python
  loops = find_loop_candidates(np.ones(16000), 1000, 120, tuple(float(t) for t in range(0, 17, 2)),
                               lengths_bars=(2.0, 4.0), window=(2.0, 10.0))
  assert {(c.bars, c.duration_seconds) for c in loops} == {(2.0, 4.0), (4.0, 8.0)}
  assert all(2.0 <= c.start_seconds < c.end_seconds <= 10.0 for c in loops)
  assert find_loop_candidates(np.ones(16000), 1000, 120, (0., 2., 4., 6.),
                              lengths_bars=(4.0,), window=(2.0, 3.0)) == []
  ```

  Ajouter tests nommés `test_window_rejects_invalid_bounds` (NaN, infini, booléens, inversée, hors piste, forme incorrecte), `test_window_quota_is_applied_after_local_search` (global plus fort hors zone, quota 1, résultat local présent), `test_scores_ignore_nonfinite_audio_outside_window` (audio mono et stéréo, hors zone NaN, scores locaux finis), `test_one_shot_silence_blocks_stop_at_window_end` : à 1000 Hz, 20 échantillons à 1, 5 à 0, puis 5 à 100 ; onset 0, fenêtre `(0.,0.025)` doit produire une fin à 0.020, pas être influencée par les 5 échantillons hors zone. Comparer signal avant/après, y compris lecture seule NumPy ; tester boucle finissant exactement à end et attaque à end exclue.
- [x] **2. Tests rouges compatibilité :** garder les tests existants window=None et rejets 2/4 sans fenêtre ; conserver tels quels les attentes de Settings, dont `[2,4,8] -> (0.25,0.5,1.0)`. Transformer les anciennes attentes de rejet de 2/4 en export/affichage en tests positifs précis (`2-bar loop`, `4-bar loop`, `2bars`, `4bars`) ; garder/ajouter les rejets 3/8/None. Charger de vrais candidats 2/4 dans liste et couloirs, vérifier placement et identités. Exécuter les fichiers concernés ; attendu : échecs du paramètre absent et des longueurs nouvelles, pas d'erreurs de fixture.
- [x] **3. Implémenter :** helper privé de validation/bornage dans candidates ; région audio pour RMS/crête, débuts limités avant classement, fin de boucle complète et fin de one-shot bornée. Utiliser les downbeats globaux uniquement comme métadonnées pour la durée de mesure ; aucune conversion vers une origine locale. Borner aussi les sous-blocs de `_find_return_to_silence` et le lissage de coupure. Préserver le chemin window=None ; aucun appel supplémentaire aux détecteurs.
- [x] **4. Intégrer les longueurs :** validation Settings explicitement limitée à AUTO_LOOP_LENGTHS_BARS tout en rejetant les booléens ; pas de version/migration nouvelle. Catégories de couloirs ordonnées 4, 2, 1, ½, ¼, shots, sans afficher de groupe vide ; libellés complets 2/4 et nommage automatique compatibles. Ne pas exposer 2/4 dans Settings.
- [x] **5. Vérifier :** `uv run pytest -q tests/test_candidate_window.py tests/test_candidates.py tests/test_settings.py tests/test_naming.py tests/test_candidates_panel.py tests/test_sample_lanes.py tests/test_lane_layout.py` puis `uv run pytest -q`. Attendu : tout vert, aucun import Qt dans core. Documenter résultat/effets dans `docs/HISTORIQUE.md`.
- [x] **6. Commit :** `Borne la recherche de samples et ajoute les longueurs manuelles`. Hooks actifs ; montrer tests et attendre validation.

**Résultat étape 1 :** 548 tests complets réussis, dont 206 ciblés ; 39 tests liste/
couloirs sous Wayland à 150 % réussis. Contrôles Ruff/mypy/Bandit verts, pas d'import
Qt dans core. Nommage sans modification de sa fonction : validation partagée
suffisante, WAV/FLAC réels testés. Aucun changement de réglages ou d'audio utilisateur,
aucun push/ZIP ; validation attendue avant la tâche 2.

## Task 2: Région manuelle, aimantation et nouvelle navigation

**Files:** créer `src/chopper/gui/selection_geometry.py`, `src/chopper/gui/selection_viewbox.py`, `tests/test_selection_geometry.py`, `tests/test_waveform_selection.py` ; modifier `src/chopper/gui/waveform_view.py`, `src/chopper/gui/sample_lanes.py`, `tests/test_waveform_view.py`, `tests/test_sample_lanes.py`.

**Interfaces:** `snap_window(window: Window, downbeats: tuple[float,...], duration: float, *, free: bool=False) -> Window | None` dans selection_geometry. `SelectionViewBox(pg.ViewBox)` émet `draw_requested = Signal(float,float,bool)` (début/fin/libre), `background_clicked = Signal(float)` (temps) et `wheel_input = Signal(float,bool,float)` (delta/Maj/centre temporel), raccordés par WaveformView ; pas d'import circulaire. WaveformView expose `selection: Window | None`, `set_selection(window: Window | None) -> None`, `set_selection_enabled(enabled: bool) -> None`, `selection_finished = Signal(object)` (Window valide), `selection_clear_requested = Signal()` ; le retrait effectif appartient au contrôleur futur. Navigation commune `navigate_wheel(delta: float, *, shift: bool, center: float | None=None) -> None` et `pan_horizontal(delta_seconds: float) -> None`.

- [ ] **1. Tests rouges géométrie :** `(1.1,5.2)`, downbeats `(0.,2.,4.,6.)`, duration 8 donne `(2.,6.)` ; à égalité 1 s donne 0 ; mode libre conserve `(1.1,5.2)` ; ordre inverse normalisé ; bornage 0/durée, marqueurs non finis/hors piste ignorés, absence de repères = libre ; deux bords aimantés à la même position renvoient None, pas une mesure inventée.

  ```python
  def test_snap_uses_nearest_downbeats_but_alt_keeps_exact_window():
      assert snap_window((1.1, 5.2), (0., 2., 4., 6.), 8.) == (2., 6.)
      assert snap_window((1.1, 5.2), (0., 2., 4., 6.), 8., free=True) == (1.1, 5.2)
      assert snap_window((0.2, 0.3), (0., 2., 4.), 8.) is None
  ```
- [ ] **2. Tests rouges gestes réels :** envoyer QMouseEvent/QTest sur le viewport avec bouton réellement tenu, pas seulement appeler les handlers. Vérifier création dans les deux directions, poignée gauche/droite et déplacement intérieur, Alt pressé/relâché durant le geste, aucun signal terminé au simple clic intérieur ou set_selection programmatique. Un clic extérieur demande la suppression une seule fois sans retirer la région ; un glisser extérieur ne demande pas suppression. Milieu/Maj+molette changent x, molette réduit/élargit la plage, aucun geste ne modifie y ; limites piste, redimensionnement et couloirs alignés.
- [ ] **3. Rouge :** `uv run pytest -q tests/test_selection_geometry.py tests/test_waveform_selection.py tests/test_waveform_view.py tests/test_sample_lanes.py` ; attendu : échecs des nouveaux contrats. Remplacer seulement les anciens tests imposant le pan gauche, garder leurs assertions de bornes/identité.
- [ ] **4. Implémenter :** région LinearRegionItem ajustable distincte de `_playing_region`, bornes et `swapMode='sort'`, couleurs ThemePalette existantes. ViewBox personnalisé pour dessiner sur le fond et ignorer le zoom droit ; le milieu délègue au pan horizontal sans y. Les couloirs conservent clic/ctrl-clic de samples mais le pan passe au milieu ; les molettes passent à la navigation commune.
- [ ] **5. Protéger les signaux :** suivre les pressions/déplacements/relâchements physiques sur le viewport, avec seuil Qt et identifiant de geste. Les changements natifs de la région/poignées passent par la même aimantation gardée contre la réentrance ; finaliser une fois après traitement du relâchement (QTimer 0 si nécessaire). Ne pas considérer `sigRegionChangeFinished` seul comme un geste : la version 0.14 l'émet aussi dans setRegion. Lire les modificateurs de l'événement final, pas seulement ceux du début. Une mise à jour UI n'émet jamais selection_finished et n'installe aucun raccourci Échap local concurrent.
- [ ] **6. Vert :** mêmes tests puis `uv run pytest -q`. Le dessin/navigation devient testable dans le widget ; la lecture et les confirmations seront raccordées en tâche 5, ne pas créer de câblage provisoire à supprimer ensuite. Mettre à jour historique et recette des gestes.
- [ ] **7. Commit :** `Ajoute la sélection aimantée et la navigation horizontale`. Montrer les tests puis attendre validation.

**Résultat étape 2 :** contrats et sept points réalisés ; rouge initial 29 échecs/
15 réussites, puis 587 tests complets et 55 ciblés réussis dont une exécution Wayland à 150 %.
Cas ajoutés : Alt au seul relâchement, annulation des fins différées et indépendance
du surlignage de lecture. Ruff/mypy/Bandit passent ; recette dans
`docs/TEST_MANUAL_SELECTION.md`. Validation attendue avant tâche 3.

## Task 3: Lecture de passage avec identité partagée

**Files:** modifier `src/chopper/gui/sample_state.py`, `tests/test_sample_state.py` ; étendre `tests/test_preview_player.py` si une signature interne doit changer. Aucun nouveau flux audio ni nouveau type de candidat persisté.

**Interfaces:** conserver `play_requested(int,int)` pour les samples ; ajouter `range_play_requested = Signal(object,int)` (Window, jeton), `select_range(window: Window, *, auto_preview: bool=True) -> None`, `clear_range() -> None`, propriétés `can_preview: bool`, `has_playback: bool`, `playing_window: Window | None`. Ajouter `replace_candidates(candidates: tuple[Candidate,...]) -> None` préservant les mêmes audio/Analysis dans LoadedTrack. Les jetons passent tous par `_next_token` existant.

- [ ] **1. Tests rouges :** sélection de passage avec auto on émet une demande, avec auto off aucune mais Espace explicite fonctionne via toggle_playback. Tester séquence sample -> passage -> sample avec jetons strictement croissants ; started/finished/failed de l'ancien jeton ne changent pas le nouveau. Cliquer le même ID ancien après une lecture de passage doit cibler le sample, pas arrêter seulement le passage ; Ctrl+clic ne change pas la cible. clear/load/reset retirent la cible manuelle, double clic sample conserve son comportement d'arrêt.

  ```python
  def test_manual_range_waits_for_explicit_play_when_auto_is_off(qapp, loaded_track):
      state = SampleState(auto_play=False)
      state.load_track(loaded_track)
      requests = []
      state.range_play_requested.connect(lambda window, token: requests.append((window, token)))
      state.select_range((0.2, 0.8))
      assert requests == [] and state.can_preview
      state.toggle_playback()
      assert len(requests) == 1 and requests[0][0] == (0.2, 0.8)
      assert state.has_playback
  ```
- [ ] **2. Tests rouges remplacement :** même audio et Analysis par identité (`is`), nouveaux IDs monotones, marques/actif périmés effacés, ancien callback ignoré ; aucune demande de lecture à la seule réception de nouveaux candidats. Signal d'arrêt émis une fois pour une lecture active/pending. `can_preview` vrai pour un passage sans sample actif ; `has_playback` vrai avant started pour permettre l'arrêt d'une demande en attente.
- [ ] **3. Rouge :** `uv run pytest -q tests/test_sample_state.py tests/test_preview_player.py` ; attendu : contrats absents, régressions anciennes toujours exercées.
- [ ] **4. Implémenter :** une cible courante candidate ou passage et un jeton propriétaire commun. `navigate` bascule aussi vers la cible sample si son ID est déjà actif mais que la cible précédente était un passage ; Ctrl+clic reste uniquement marquage. `replace_candidates` utilise dataclasses.replace sur LoadedTrack, pas une remise à zéro des données audio ; `load_track` remet à zéro la cible de passage mais ne recycle pas les compteurs de jetons/IDs.
- [ ] **5. Vert :** mêmes tests puis suite complète. PreviewPlayer conserve ses contrôles audio ; l'adaptateur de tâche 5 lui transmettra un candidat éphémère de bornes pour le passage, jamais ajouté aux listes/exportations. Documenter absence de lecture automatique au remplacement.
- [ ] **6. Commit :** `Unifie la préécoute des passages et des samples`. Montrer les tests puis attendre validation.

## Task 4: Reclassement en mémoire et worker identifié

**Files:** modifier `src/chopper/gui/workers.py`, `src/chopper/gui/presentation.py`, `tests/test_workers.py` ; nouveaux tests de la fonction locale dans `tests/test_candidate_window.py` ou `tests/test_workers.py` sans doubler ceux du moteur.

**Interfaces:** `search_candidates(loaded: LoadedTrack, settings: Settings, *, window: Window | None=None, length_bars: float | None=None) -> tuple[tuple[Candidate,...],str]` dans workers. Dataclass figée `CandidateSearchResult(request_id: int, loaded: LoadedTrack, window: Window | None, length_bars: float | None, message: str)` dans presentation. `CandidateSearchWorker(request_id: int, loaded: LoadedTrack, settings: Settings, *, window: Window | None=None, length_bars: float | None=None)` avec `finished = Signal(object)` et `failed = Signal(str)`, méthode `run() -> None` ; Settings copié au constructeur. Étendre start_in_thread à ce troisième worker, sans changer les deux analyses existantes.

- [ ] **1. Tests rouges orchestration :** un LoadedTrack réel, settings quota 2/durée one-shot 0.2 ; en mode manuel, seule la longueur choisie est transmise, toutes les bornes respectées, limites Settings appliquées. En automatique `window=None`, longueurs courtes Settings, pas la longueur manuelle précédente. Les fonctions beat_this/onsets/audio_io.load/cache lèvent si appelées : la recherche doit quand même réussir avec les données mémorisées. Samples/Analysis conservés par identité et données inchangées.
- [ ] **2. Tests rouges erreurs/messages :** fenêtre trop courte pour 4 mesures avec attaques valides : aucun loop, shots présents, message indiquant `4-bar` et nombre de shots ; absence de rythme = shots seuls avec explication ; pas d'attaque = résultat vide clair. Vérifier erreur propagée par failed et fin du QThread sur réussite et erreur ; changer Settings après construction ne modifie pas la requête copiée. Les slots du thread ne doivent ni lire un QWidget ni changer les préférences.

  ```python
  def test_short_selection_still_finds_the_two_cached_onsets(loaded_track):
      loaded = replace(loaded_track, analysis=replace(loaded_track.analysis, onset_times=(0.1, 0.3)))
      found, message = search_candidates(loaded, Settings(candidates_per_track=2, max_one_shot_seconds=0.2),
                                         window=(0.0, 0.6), length_bars=4.0)
      assert len(found) == 2 and all(c.type is CandidateType.ONE_SHOT for c in found)
      assert all(0.0 <= c.start_seconds < c.end_seconds <= 0.6 for c in found)
      assert "4-bar" in message and "2 one-shots" in message
  ```
- [ ] **3. Rouge :** `uv run pytest -q tests/test_workers.py tests/test_candidate_window.py` ; attendu : worker/fonction absents ou message manquant.
- [ ] **4. Implémenter :** réutiliser les fonctions de tâche 1, pas analyze_track ; tuple trié par score comme aujourd'hui, LoadedTrack remplacé uniquement sur candidats. `window != None` impose une longueur manuelle valide, `window=None` impose `length_bars=None`. Calcul des messages avec la durée globale de mesure et les résultats effectifs, sans annoncer « trop court » quand le vrai problème est l'absence de grille.
- [ ] **5. Vert :** tests ciblés puis suite complète. Le raccordement thread de ce worker doit quitter aussi sur failed ; conserver la référence worker/thread jusqu'au signal réel thread.finished, pas au résultat.
- [ ] **6. Commit :** `Reclasse les samples en mémoire dans un worker identifié`. Montrer les tests puis attendre validation.

## Task 5: Contrôles, confirmations et parcours complet

**Files:** créer `src/chopper/gui/selection_controller.py`, `src/chopper/gui/selection_dialog.py`, `tests/test_selection_controller.py`, `tests/test_manual_selection.py` ; modifier `src/chopper/gui/main_window.py`, `src/chopper/gui/actions.py`, `tests/test_main_window.py`, `tests/test_actions.py`, `README.md`, `docs/HISTORIQUE.md`, `docs/FINAL_VALIDATION.md`.

**Interfaces et responsabilité :**
- `SelectionDecision` enum (`EXPORT`, `DISCARD`, `CANCEL`) et `confirm_selection_transition(parent: QWidget, action: str, can_export: bool) -> SelectionDecision` dans selection_dialog.
- `SelectionController(state: SampleState, *, choose: Callable[[str,bool],SelectionDecision], export_all: Callable[[],bool], parent: QObject | None=None)` : propriétés window/length_bars/result_window/result_length_bars/busy/status_message, signal `changed()`, signal `search_requested(int,object,object)` (request_id, window, longueur).
- Méthodes du contrôleur : `set_selection(window: Window) -> None`, `set_length(bars: float) -> None`, `request_chop() -> bool`, `request_whole_track() -> bool`, `authorize_transition(action: str, *, include_region: bool=False) -> bool`, `apply_result(result: CandidateSearchResult) -> bool`, `fail(request_id: int, message: str) -> bool`, `reset() -> None`. Le contrôleur n'écrit pas de fichiers ; ses callbacks ne sont que les deux frontières dialogue/export. set_selection choisit la cible passage et l'auto-préécoute après geste terminé, pas lors des changements programmatiques de la vue.
- `MainWindow._export_candidates(candidates: tuple[Candidate,...]) -> bool` extrait le pipeline actuel ; vrai uniquement après succès de tous les fichiers. Les exports marked/all existants l'appellent sans changer leur sélection ; le callback de confirmation snapshotte tous les candidats manuels courants, ignore les coches.

- [ ] **1. Tests rouges contrôleur :** `test_cancel_or_failed_export_preserves_region_results_marks` paramétré CANCEL/export false, `test_discard_only_authorizes_until_search_succeeds`, `test_empty_results_still_confirm_but_cannot_export`, `test_adjusting_selection_keeps_old_result_bounds_until_chop`, `test_stale_result_cannot_replace_new_generation`. Contrôler directement propriétés, IDs, marques et signaux ; simuler seulement frontières choose/export, pas le moteur. Le résultat d'une requête porte la piste/audio attendus ainsi que fenêtre/longueur/id ; un résultat tardif n'agit ni sur l'affichage ni sur busy de la requête courante.

  ```python
  def test_cancel_retains_the_region_even_before_first_chop(qapp, loaded_track):
      state = SampleState(auto_play=False)
      state.load_track(loaded_track)
      controller = SelectionController(state, choose=lambda action, can_export: SelectionDecision.CANCEL,
                                        export_all=lambda: True)
      controller.set_selection((0.2, 0.8))
      assert controller.request_whole_track() is False
      assert controller.window == (0.2, 0.8) and not controller.busy
  ```
- [ ] **2. Tests rouges parcours réels :** dessin terminé -> audio une fois selon Auto-preview -> C -> attendre le signal du vrai worker avec QSignalSpy/attente bornée, jamais sleep arbitraire -> vérifier liste/couloirs/2 et 4 mesures/export réels. Les détecteurs et chargeur lèvent si appelés après chargement initial. Retour Whole track retrouve les catégories et réglages actuels sans nouveau beat_this. Fenêtre trop courte montre le message et les shots ; une recherche vide ne plante pas.
- [ ] **3. Tests rouges protection :** paramétrer Échap/clic extérieur/Whole track/nouveau Chop/autre piste/album/fermeture ; CANCEL et export annulé/échoué bloquent l'action et conservent région/résultats/marques. Avec export partiel réel simulant disque plein au deuxième fichier, premier fichier présent, aucun retour automatique et aucun effacement. Réussite exporte tous les samples manuels même si un seul coché ; DISCARD ne modifie aucun fichier déjà exporté. Ajuster rectangle/Length puis exporter utilise les anciennes bornes, pas les nouvelles. Préécoute arrêtée avant dialogue ; son annulation ne relance rien.
- [ ] **4. Tests rouges actions et réentrance :** C et infobulle/F1 issus d'une action unique `chop_selection` dans Playback, `whole_track` partagé avec bouton sans raccourci. C/Esc inactifs dans modales et saisie, pas d'autorépétition ; le seul raccourci Esc global arrête puis demande sortie si région présente. Échap ou fermeture de la confirmation = CANCEL, pas de deuxième dialogue. Un second close/request pendant une confirmation ouverte doit être refusé, sans double export. Tester résultat/fin de lecture ancien pendant modalité et fermeture avec worker en cours ; cache/thread restent vivants si wait échoue.
- [ ] **5. Rouge :** `uv run pytest -q tests/test_selection_controller.py tests/test_manual_selection.py tests/test_actions.py tests/test_main_window.py` ; attendu : nouvelles interfaces/actions et protections absentes. Ne pas déclarer un résultat de worker « reçu » en appelant seulement son slot à la place du parcours réel ; garder aussi des tests directs pour l'obsolescence.
- [ ] **6. Implémenter contrôleur/dialogue :** choix CANCEL sûr par défaut ; mêmes trois boutons pour les sorties et texte adapté pour remplacement/fermeture. Sans région ni mode manuel, Whole track inactif ; avec région même sans résultat confirmer, export désactivé. La décision autorise une transaction, elle ne retire aucun résultat avant succès du nouveau calcul. Requête monotone, snapshot piste/audio/fenêtre/longueur, un seul pending ; échec conserve ancien affichage. Pendant busy, modifications et nouvelles requêtes ignorées, widgets désactivés ; reset invalide les anciens résultats. Retenir le mode manuel même si la liste est vide pour que la sortie retire la région correctement. Une confirmation active verrouille les transitions réentrantes.
- [ ] **7. Raccorder MainWindow :** barre Length ¼/½/1/2/4 (défaut session 1), boutons, label de bornes et message de résultats anciens. `selection_finished` -> contrôleur.set_selection ; `selection_clear_requested`/Esc/Whole track -> request_whole_track. Sync du rectangle seulement depuis controller.changed, jamais depuis chaque SampleState.changed : ne pas réinitialiser une région en cours de déplacement quand une lecture finit. `.search_requested` crée CandidateSearchWorker avec loaded/settings instantanés ; résultat valide remplace les seuls candidats via state.replace_candidates. Ne pas appeler `_on_track_analyzed` pour le reclassement, car il recréerait la forme d'onde et détruirait zoom/région.
- [ ] **8. Raccorder audio/export/sortie :** range_play_requested fait lire au PreviewPlayer un Candidate ONE_SHOT éphémère de bornes, score 0, jamais ajouté à SampleState.items/export. Action play utilise can_preview ; stop/Échap disponible si has_playback **ou région présente**, même Auto-preview désactivé, avec libellé d'aide adapté à sa double fonction. Surbrillance choisie par playing_window ou playing_id. Export helper retourne false en cas d'annulation/erreur partielle et garde les messages existants. Intercepter autre piste/album/close avant les resets actuels. Sur fermeture autorisée invalider les requêtes, arrêter le lecteur, demander thread.quit puis attendre sa vraie fin ; si wait échoue, ignorer la fermeture, ne pas fermer le cache ou libérer le worker vivant. Garder le stop après piste de l'album existant et ne pas démarrer une nouvelle tâche tant que le QThread précédent n'a pas réellement fini.
- [ ] **9. Vert et nettoyage borné :** tests ciblés puis `uv run pytest -q`. Vérifier `src/choppeur/` uniquement dans l'espace courant ; si absent, consigner sans effet ; sinon `rmdir` des seuls sous-dossiers vides, jamais suppression de fichiers ni parcours d'un lien vers un autre espace. Ajouter aide anglaise des gestes, garde, Alt, bornes et quotas ; mettre à jour recette et historique des risques/effets/idempotence.
- [ ] **10. Vérifications finales :** `uv run ruff check src tests scripts prototypes evaluate.py`, `uv run ruff format --check src tests scripts prototypes evaluate.py`, `uv run mypy src tests scripts prototypes evaluate.py`, `uv run bandit -qc pyproject.toml -r src scripts prototypes evaluate.py -ll`, `git diff --check`. Suite complète puis tests gestes/actions/couloirs sous `QT_QPA_PLATFORM=wayland` et `QT_SCALE_FACTOR=1.5` si session disponible ; sinon annoncer explicitement l'absence de validation native. Aucune nouvelle analyse matérielle ou export utilisateur pendant les tests automatisés.
- [ ] **11. Commit :** `Intègre la découpe manuelle et protège les résultats`. Tous les hooks actifs. Revue indépendante finale de toute la plage du plan ; correctifs justifiés en tests rouges puis verts. Aucun push/ZIP automatique ; montrer les résultats et attendre l'essai utilisateur.

## Passage final et mémoire du travail

Exécution native proposée comme pour le travail précédent : une étape, ses tests,
son commit, puis validation utilisateur. À l'exécution, vérifier l'espace Git isolé
existant plutôt que créer un second worktree inutilement. Ledger propre à ce plan
sous `.superpowers/sdd/2026-11-13-selection-manuelle/`, jamais réutiliser celui de
distribution. Base : commit du plan approuvé, avant la première implémentation.

Recette utilisateur finale : gestes et Alt sous KDE/Wayland, lecture de passage
et de sample alternée, C/F1, 2/4 mesures, région trop courte, toutes décisions de
sortie y compris annulation/échec d'export, audio réel et DAW existants. Les fichiers
audio et exports antérieurs ne sont jamais les données à nettoyer pour ce test.

## Auto-revue et références

Couverture : tâche 1 = moteur/longueurs/régressions ; tâche 2 = région/navigation ;
tâche 3 = cible et identité audio ; tâche 4 = réutilisation/worker ; tâche 5 = parcours,
confirmations, actions et fermeture. Les cinq risques de revue ont des tests nommés
ou paramétrés dans leur tâche. Contrats Window/LoadedTrack/jetons et booléen export
cohérents entre producteurs et consommateurs ; aucune dépendance de core vers GUI.

Source installée pyqtgraph 0.14 consultée : LinearRegionItem.setRegion appelle
lineMoveFinished ; mouseDragEvent utilise `ev.isStart()`/`ev.isFinish()`, pas les
noms inexacts de certains exemples. ViewBox.wheelEvent emploie un événement scène
(`delta()`), différent du QWheelEvent Qt (`angleDelta()`) reçu par le viewport et
les couloirs ; adapter à la bonne frontière, ne pas les confondre.

Documentation officielle : https://pyqtgraph.readthedocs.io/en/latest/api_reference/graphicsItems/linearregionitem.html
et sources installées de graphicsItems/LinearRegionItem.py, ViewBox/ViewBox.py.
Documentation Qt vérifiée : https://doc.qt.io/qtforpython-6/PySide6/QtCore/QThread.html
(moveToThread, quit, wait booléen et finished/deleteLater).
Le design est l'autorité ; toute adaptation du plan doit être motivée dans son
ledger et rester dans le périmètre approuvé, sans élargir les opérations destructives.

**État :** plan validé par l'utilisateur le 13/11/2026 ; tâche 1 validée,
tâche 2 implémentée, validation attendue avant tâche 3. Lecture de passage,
reclassement et confirmations restent à implémenter ; pas de publication implicite.
