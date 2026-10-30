# Refonte de l'interface — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans pour réaliser les tâches dans cette session. **Exception impérative à son exécution continue : arrêter après chaque étape et attendre la validation utilisateur**, conformément au design et à AGENTS.md. Ne pas lancer automatiquement l'étape suivante. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Livrer l'interface approuvée, avec tous les samples visibles et
cliquables, écoute cohérente, exports permanents et glisser-déposer testé sous KDE.

**Architecture:** Garder PySide6/pyqtgraph et le moteur existant. Un état commun
pilote la liste, les couloirs et la lecture ; un lecteur audio dédié signale sa
fin réelle. Séparer placement des rectangles, rendu, exports et actions clavier.

**Tech Stack:** Python 3.12, uv, PySide6 >=6.7, pyqtgraph >=0.13,
NumPy/soundfile/sounddevice existants, pytest. Aucune dépendance ajoutée.

**Spec:** `docs/REFONTE_INTERFACE.md`, approuvé avec `M`, `glissés/` et le bouton
« Analyser l'album » maintenu en haut à côté de « Lecture auto ».

## Global Constraints

- Une étape à la fois : tests rouges, correction minimale, tests verts, commit,
  résultat présenté, puis **attente de validation** avant toute étape suivante.
- Aucun changement du détecteur de rythme, attaques ou scores. Révision du
  30/10 : longueurs de boucles limitées à 0,5 et 1 mesure avant l'étape 4.
- Aucun import Qt dans `core/`. Sources audio exclusivement en lecture seule.
- Forme d'onde sans rectangles permanents ; surlignage uniquement pendant lecture.
- Couloirs 1/0,5/shots, catégories vides masquées, sous-lignes sans occultation.
- Axe vertical ajusté au chargement puis figé, zoom/pan horizontaux seuls, bouton A masqué.
- `M` marque/retire le sample actif ; ne pas enregistrer Ctrl+Espace.
- Les glissers créent leurs WAV PCM24 dans `<export_dir>/glissés/`, à la demande.
  Les boutons exportent dans `<export_dir>/`, avec WAV/FLAC selon les paramètres.
- Fréquence et canaux conservés ; aucun écrasement ni nettoyage automatique.
- Le bouton « Analyser l'album » reste visible à côté de « Lecture auto », même
  lorsqu'il est désactivé faute de dossier ou pendant une analyse.
- Suivre KDE clair/sombre ; option « Forcer sombre » désactivée par défaut.
- Pas de serveur, navigateur, dossier nouveau dans le home, ni chemin personnel
  en dur. Sous-dossier `glissés/` créé seulement sous la destination choisie.
- Préserver les travaux antérieurs : migration librosa, documentation, tests
  de downbeats, audit et prototype, commités avant exécution en `21fb2c1`,
  `a7541ae` et `d0d7863`. N'inclure dans une étape que son propre diff.
- Ne pas confondre tests Qt sans affichage et validation réelle Bitwig/KDE.

## Review Focus

1. Signal de fin d'une ancienne lecture après changement de piste/sample : ne
   jamais effacer l'état d'une nouvelle lecture ; couvert étape 1.
2. Samples de bornes identiques : tous doivent rester
   identifiables et accessibles, même après tri ; couvert étapes 3/4.
3. Barre de défilement, redimensionnement ou écran haute densité : conserver
   l'alignement en pixels de l'onde et des couloirs ; couvert étape 4.
4. Export partiel, disque plein ou NAS indisponible : préserver les réussites,
   afficher l'échec et ne jamais proposer une URL inexistante ; couvert étape 6.
5. Focus dans un champ texte ou dialogue : `M`, Espace et Ctrl+A ne doivent pas
   déclencher les actions des candidats ; couvert étape 7.

## Carte des fichiers et interfaces communes

| Fichier | Responsabilité |
|---|---|
| `gui/presentation.py` (nouveau) | Données immuables `LoadedTrack`, `SampleItem`, sans logique d'interaction |
| `gui/sample_state.py` (nouveau) | État commun, identité, actif, marques, commandes de lecture |
| `gui/preview_player.py` (nouveau) | Préécoute non bloquante, fin réelle, erreurs et jetons de lecture |
| `gui/lane_layout.py` (nouveau) | Placement déterministe par catégorie et sous-ligne, sans Qt graphique |
| `gui/sample_lanes.py` (nouveau) | Rectangles, info-bulles, clics et défilement des couloirs |
| `gui/theme.py` (nouveau) | Palette commune Qt/pyqtgraph et suivi du thème |
| `gui/actions.py` (nouveau) | Registre unique des actions, raccourcis, menus et aide |
| `gui/sample_drag.py` (nouveau) | Geste de poignée et transfert Qt d'un WAV déjà écrit |
| `core/exporting.py` (nouveau) | Export par bouton et par glisser, compte rendu partiel, aucun Qt |
| Fichiers GUI existants | Intégration et adaptation progressive, pas de seconde application |

Les chemins abrégés `gui/` et `core/` désignent `src/choppeur/gui/` et
`src/choppeur/core/`. Le prototype reste jetable : ne pas l'importer dans le produit.

Contrats à introduire à l'étape 1 dans `gui/presentation.py` :

- `LoadedTrack(analysis: Analysis, candidates: tuple[Candidate, ...], samples:
  np.ndarray, sample_rate: int)` : audio source mono ou multicanal, pas la courbe
  réduite d'affichage. L'interface le traite en lecture seule.
- `SampleItem(id: int, candidate: Candidate)` : identifiant unique attribué par
  l'état, jamais déduit d'une ligne triée ou de l'égalité de deux candidats.

Tests partagés : ajouter dans `tests/conftest.py` une fixture `loaded_track`
avec 3 s d'audio stéréo à 1 000 Hz, une boucle `[0,1]` et un shot `[1,1.2]`,
analyse à 120 BPM. Conserver la fixture Qt existante. Les tests de placement
construisent leurs propres candidats, indépendamment du détecteur.

### Porte de vérification et de livraison G — à chaque étape

Après les tests ciblés de l'étape, lancer :

```bash
uv run pytest -q
uv run ruff check src tests prototypes evaluate.py
uv run ruff format --check src tests prototypes evaluate.py
uv run mypy src tests prototypes evaluate.py
uv run bandit -qc pyproject.toml -r src prototypes evaluate.py -ll
git diff --check
```

Attendu : aucun test en échec, aucun défaut Ruff/format/mypy, aucun signalement
Bandit moyen/élevé, aucun défaut d'espacement. Distinguer les avertissements
préexistants de nouveaux problèmes. La référence actuelle est de **130 tests**
dans le dossier de travail, incluant les quatre tests du prototype désormais commités.

Charger `verification-before-completion` avant de déclarer une étape terminée.
Relire le diff, indexer uniquement ses changements, ne pas contourner les hooks,
créer le commit proposé, présenter tests et effets de bord, puis attendre.
Pour les validations visuelles intermédiaires, lancer explicitement
`QT_QPA_PLATFORM=wayland uv run choppeur` ; le défaut XCB n'est changé qu'étape 8.

---

## Étape 1 — État partagé et lecteur de préécoute

**Fichiers :** créer `gui/presentation.py`, `gui/sample_state.py`,
`gui/preview_player.py`, `tests/test_sample_state.py`, `tests/test_preview_player.py` ;
modifier `core/settings.py`, `gui/settings_dialog.py`, `tests/conftest.py`,
`tests/test_settings.py`, `tests/test_settings_dialog.py`.

**Consomme :** `Track`, `Analysis`, `Candidate`, paramètres et sounddevice actuels.
**Produit :** `SampleState(QObject)` avec `items`, `active_id`, `playing_id`,
`marked_ids`, `auto_play` ; méthodes `load_track(LoadedTrack)`, `clear()`,
`click(id: int, control: bool = False)`, `navigate(id: int)`, `toggle_mark(id: int)`,
`mark_all()`, `clear_marks()`, `toggle_playback()`, `stop()`,
`set_auto_play(enabled: bool)`.
Signaux : `changed()`, `play_requested(id: int, token: int)`, `stop_requested()`,
`error_reported(message: str)`.
Les accusés `playback_started(token)`, `playback_finished(token)` et
`playback_failed(token, message)` ignorent les anciens jetons.

`PreviewPlayer(QObject)` expose `play(samples: np.ndarray, sample_rate: int,
candidate: Candidate, token: int)`, `stop()` ; signaux `started(token)`,
`finished(token)`, `failed(token, message)`. Réutiliser `sd.play(..., loop=False)`
non bloquant, conserver le flux de `sd.get_stream()` et surveiller `active` par
QTimer à 20 ms ; ne pas appeler `sd.wait()` dans l'interface. Annuler la
surveillance précédente lors d'un nouveau play/stop. Aucun minuteur basé seulement
sur la durée théorique de l'extrait.

- [x] **1. Écrire les tests comportementaux.** Exemple avec les fixtures ci-dessus :
  ```python
  state = SampleState(auto_play=False)
  state.load_track(loaded_track)
  first, second = state.items
  state.click(first.id)
  state.click(second.id, control=True)
  assert state.active_id == first.id
  assert state.marked_ids == frozenset({second.id})
  assert state.playing_id is None
  ```
  Ajouter `test_old_completion_cannot_stop_new_playback`, clic auto/second clic,
  clic auto désactivée, bascule Ctrl, arrêt puis sélection d'un autre sample,
  fin naturelle sans perte des marques, remise à zéro sur nouvelle piste,
  identité distincte pour deux candidats égaux, absence d'actif et ID périmé.
  Tester le découpage stéréo réel remis au lecteur, fin du flux, erreur de play,
  erreur de surveillance et stop répété. Seul l'accès PortAudio est simulé.
- [x] **2. Observer le rouge :** `uv run pytest -q tests/test_sample_state.py tests/test_preview_player.py`.
  Attendu : échecs des contrats encore absents, pas une faute de syntaxe.
- [x] **3. Implémenter les interfaces ci-dessus.** IDs monotones à travers les
  chargements, jeton nouveau à chaque demande de lecture, un seul flux actif.
  Ajouter `Settings.auto_play: bool = True` et `Settings.force_dark: bool = False`.
  Le dialogue existant doit conserver ces champs même avant d'exposer le thème.
- [x] **4. Vert et porte G.** Tester aussi ancien TOML sans nouvelles clés,
  sauvegarde/chargement des deux booléens et absence de perte en validant le dialogue.
- [x] **5. Commit :** `Introduit l’état partagé et une préécoute à fin détectée`.
  **Validation utilisateur :** fondations testées ; interface actuelle inchangée.
  Attendre sa validation, sans commencer l'étape 2.

**Avancement au 30/10/2026 :** étape 1 commitée en `ee2f522` et validée ; étape 2
autorisée. État et nouveau lecteur seront raccordés à l'étape 3.

## Étape 2 — Transporter l'audio multicanal hors du thread graphique

**Fichiers :** `gui/workers.py`, `gui/main_window.py`, `gui/waveform_view.py`,
`tests/test_workers.py`, `tests/test_main_window.py`, `tests/test_waveform_view.py`.

**Consomme :** `LoadedTrack` de l'étape 1 et le pipeline d'analyse existant.
**Produit :** `TrackAnalysisWorker.finished` transporte un `LoadedTrack` ;
`MainWindow._on_track_analyzed(result: LoadedTrack)` ne décode plus le fichier.
`analyze_track()` et les signaux d'album gardent leur contrat actuel.

- [x] **1. Écrire les tests :**
  `test_track_worker_returns_original_stereo_audio`,
  `test_gui_does_not_reload_audio_after_worker_result`,
  `test_stereo_waveform_is_only_a_display_projection`.
  Écrire un vrai WAV stéréo de 1 000 trames et deux canaux différents ; vérifier
  `result.samples.shape == (1000, 2)`, fréquence 1 000, données intactes et
  projection mono seulement dans les données du graphe. Tester source devenue
  illisible au second chargement : signal d'échec, thread libéré, aucun résultat.
- [x] **2. Observer le rouge :**
  `uv run pytest -q tests/test_workers.py tests/test_main_window.py tests/test_waveform_view.py`.
- [x] **3. Charger l'audio avec `audio_io.load(path, mono=False)` dans le worker
  après l'analyse, puis émettre `LoadedTrack`.** Cela déplace la relecture
  actuelle, sans prétendre supprimer les décodages internes de beat_this.
  Adapter tous les consommateurs/tests du signal dans le même commit.
  Ne pas convertir le tableau de lecture/export en mono pour tracer la courbe.
- [x] **4. Vert et porte G.** Rejouer notamment les tests de refus d'analyse
  concurrente et de reprise après échec. Les tests de workers simulant le calcul
  doivent fournir un vrai petit fichier audio pour cette relecture.
- [x] **5. Commit :** `Conserve la stéréo et charge l’audio d’affichage en arrière-plan`.
  **Validation :** préécoute/export stéréo sur une piste ; aucune modification source.
  Attendre avant l'étape suivante.

**Résultat étape 2 :** 184 tests réussis, dont cinq nouveaux ; porte G réussie.
WAV stéréo réel vérifié jusqu'à la préécoute simulée et l'export réel, sans
modification source. Écoute matérielle non validée ; attendre l'accord utilisateur
avant l'étape 3.

## Étape 3 — Disposition, liste compacte et interactions communes

**Fichiers :** `gui/main_window.py`, `gui/candidates_panel.py`,
`tests/test_main_window.py`, `tests/test_candidates_panel.py`.

**Consomme :** `SampleState`, `PreviewPlayer`, `LoadedTrack`.
**Produit :** un `MainWindow.sample_state` partagé ;
`CandidatesPanel(state: SampleState, parent=None)` ne possède plus de lecteur
ni de copie indépendante de la sélection. Signaux `export_requested(mode: str)`
avec `mode` égal à `marked` ou `all`, et `drag_requested(id: int)` réservé étape 6.

- [x] **1. Écrire les tests :** titre/tempo de la piste affichée, bibliothèque à
  gauche, onde prioritaire en hauteur, boutons album/auto voisins et visibles,
  cases et compteurs synchronisés. Vérifier que le mode `all` fournit les deux
  candidats de la fixture et `marked` seulement celui marqué, pas l'actif.
  Vérifier clic liste avec/sans auto, Ctrl sans changement d'actif, navigation
  clavier sans lecture, état de lecture distinct de la marque et du focus.
  Tester deux candidats égaux et un tri de la liste : le bon ID reste ciblé.
- [x] **2. Observer le rouge :**
  `uv run pytest -q tests/test_main_window.py tests/test_candidates_panel.py`.
- [x] **3. Intégrer un seul état et un seul lecteur.** Utiliser une table Qt non
  éditable avec les cinq colonnes et repères `✓`/`▶`, ordre initial des candidats
  conservé. Identifier les lignes par ID en rôle utilisateur, pas leur index.
  La poignée ne sélectionne, ne joue ni ne marque ; elle sera activée étape 6.
  Les boutons export gardent à cette étape une destination choisie par dialogue
  et appellent l'export actuel avec la liste exacte calculée par l'état ; l'étape 6
  remplacera ce raccordement par le service commun et la destination configurée.
- [x] **4. Brancher les transitions.** Case auto persistée immédiatement ; le
  dialogue paramètres ne la remet pas à sa valeur par défaut. Changement de piste :
  arrêter et vider les anciens résultats avant l'analyse ; échec sans titre/exports
  d'une autre piste. Lecture finie/échouée répercute son état dans la liste.
  À la fermeture, arrêter le lecteur et son minuteur avant la logique existante
  d'arrêt des analyses ; tester qu'aucun audio ne continue après cette fermeture.
  Mettre à jour les anciens tests qui imposaient la préécoute d'une case cochée :
  ce comportement est explicitement remplacé par la lecture du sample actif.
- [x] **5. Vert et porte G ; commit :** `Réorganise la fenêtre et synchronise la liste des samples`.
  **Validation native Wayland :** disposition, titre/tempo, bouton album visible,
  clic/auto/Ctrl et compteurs ; signaler que couloirs, thème et raccourcis complets
  arrivent aux étapes suivantes. Attendre validation.

**Résultat étape 3 :** 189 tests réussis ; porte G réussie. Tests de l'ancien
panneau adaptés au contrat approuvé (actif distinct des marques). Arrêt réel du
flux simulé et du minuteur vérifié à la fermeture ; sources inchangées.
Validation visuelle et écoute native Wayland à réaliser par l'utilisateur avant
l'étape 4. Aucun couloir, thème ou registre de raccourcis ajouté à cette étape.

## Préalable à l'étape 4 — Trois catégories et navigation horizontale

**Fichiers :** `core/models.py`, `core/candidates.py`, `core/settings.py`,
`core/naming.py`, `gui/settings_dialog.py`, `gui/candidates_panel.py`,
`gui/waveform_view.py` et leurs tests.

- [x] Tests rouges : boucles 0,5 et 1 mesure seulement, durées moitié/entière
  sur la même grille existante ; refus des longueurs non autorisées ; migration
  TOML avec 2/4/8, mélange et valeurs inattendues, répétée sans changement ;
  noms `0.5bars`/`1bars` ; réglages sans saisie libre ; axe Y inchangé après gestes.
- [x] Implémenter `Candidate.bars: float | None`, longueurs par défaut `(0.5, 1.0)`,
  validation moteur/nommage et migration paramètres. Ne pas modifier la détection
  des downbeats ni le calcul actuel de durée médiane d'une mesure.
  Réglage par choix fermés 1/2, 1 ou les deux ; anciens réglages filtrés,
  repli sur les deux si aucun valide. Étiquette « Boucle 1/2 mesure »/« Boucle 1 mesure ».
- [x] Verrouiller Y à la plage calculée au chargement, conserver le zoom X,
  désactiver interactions Y et auto Y après le cadrage, masquer le bouton A.
- [x] Porte G, commit, présenter les tests puis commencer l'étape 4 selon
  l'autorisation explicite de l'utilisateur (pas de nouvelle validation intermédiaire).

## Étape 4 — Forme d'onde nette et couloirs à sous-lignes

**Fichiers :** créer `gui/lane_layout.py`, `gui/sample_lanes.py`,
`tests/test_lane_layout.py`, `tests/test_sample_lanes.py` ; modifier
`gui/waveform_view.py`, `gui/main_window.py`, `tests/test_waveform_view.py`,
`tests/test_main_window.py`.

**Consomme :** `SampleItem`, `SampleState`, `Analysis.downbeat_times`.
**Produit :** `LanePlacement(item_id: int, category: tuple[str, float], row: int,
start_seconds: float, end_seconds: float)` ;
`layout_samples(items: tuple[SampleItem, ...]) -> tuple[LanePlacement, ...]`.
Catégories : `('loop', 1.0)`, `('loop', 0.5)`, `('shot', 0.0)`, dans cet ordre
uniquement. Sous-lignes de 22 pixels logiques minimum.

`SampleLanesView(state: SampleState)` expose
`link_time_axis(waveform: WaveformView)` et `reveal(item_id: int)`.
`WaveformView` expose `set_downbeats(times: tuple[float, ...])` et
`set_playing_candidate(candidate: Candidate | None)` ; ce dernier surlignage
est passif, sans poignées ni possibilité d'édition.

- [x] **1. Tests d'abord :** pour les boucles 1 mesure ID 10 `[0,2]`, 11 `[1,3]`,
  12 `[2,4]`, attendre les sous-lignes `{10: 0, 11: 1, 12: 0}`. Ajouter intervalles
  inclus, débuts identiques, deux copies exactes, entrée mélangée, trois recouvrements,
  catégories 1/0,5/shot et catégories vides. Chaque ID doit apparaître une fois.
  Tester géométrie/hit-test des rectangles réellement affichés, infobulles,
  Ctrl+clic, non-édition après glisser et stabilité après marquage.
- [x] **2. Observer le rouge :**
  `uv run pytest -q tests/test_lane_layout.py tests/test_sample_lanes.py tests/test_waveform_view.py`.
- [x] **3. Implémenter le placement pur puis le rendu.** Trier par début/fin/ID,
  affecter la première sous-ligne libre avec `fin <= début`, sans écraser d'item.
  Conteneur à défilement vertical plutôt qu'une limite de sous-lignes. Les clics
  appellent l'état ; les rafraîchissements depuis l'état n'émettent aucun clic.
  Afficher type/tempo/durée/position selon le design, y compris tempo inconnu.
- [x] **4. Lier les vues temporelles et remplacer les anciens marqueurs de candidats
  sur la courbe par les seuls downbeats.** Tester zoom et pan depuis les deux vues,
  redimensionnement et apparition de la barre verticale : même seconde à la même
  abscisse, à un pixel près. Le défilement pour révéler un sample ne modifie pas le
   zoom. Le surlignage de lecture disparaît à la fin, à l'arrêt et sur erreur.
   Interdire tout zoom/pan vertical, garder l'amplitude pleine hauteur et aucun
   bouton A ; même contrainte sur les couloirs (défilement vertical dédié seulement).
  Remplacer le test historique « deux marqueurs par candidat », devenu contraire
  au design, par ces invariants ; conserver les tests de réduction de la courbe.
- [x] **5. Vert et porte G ; commit :** `Affiche les samples dans des couloirs sans occultation`.
  **Validation :** contrôler manuellement les chevauchements, toutes les sous-lignes,
   la synchronisation avec la liste et l'alignement lors du zoom. Attendre validation.

**Résultat étape 4 :** 224 tests réussis ; porte G réussie. Tests graphiques
complémentaires sous `QT_SCALE_FACTOR=1.5` réussis. Capture native Wayland sur
la piste 16 réelle ; couleurs/thème définitifs et raccourcis restent les étapes
5 et 7. Les catégories sans candidat restent masquées. Attendre la validation
utilisateur avant l'étape 5.

## Étape 5 — Thèmes KDE et option « Forcer sombre »

**Fichiers :** créer `gui/theme.py`, `tests/test_theme.py` ; modifier
`gui/settings_dialog.py`, `gui/main_window.py`, `gui/candidates_panel.py`,
`gui/sample_lanes.py`, `gui/waveform_view.py`, `tests/test_settings_dialog.py`.

**Consomme :** `Settings.force_dark`, état de lecture/marquage, vues étapes 3/4.
**Produit :** `ThemeManager(QObject)` avec `set_force_dark(enabled: bool)` et
`changed()` ; `palette` fournit les mêmes rôles de couleurs aux widgets et graphes.

- [ ] **1. Tests :** couleurs de fond/texte différentes entre clair/sombre, orange
  pour boucles et bleu-gris pour shots, marquage plus vif mais même teinte,
  focus et lecture distincts. Vérifier restauration du suivi système après
  désactivation du forçage et conservation des autres paramètres par le dialogue.
- [ ] **2. Observer le rouge :**
  `uv run pytest -q tests/test_theme.py tests/test_settings_dialog.py`.
- [ ] **3. Implémenter le gestionnaire et la case.** Lire le thème via
  `QGuiApplication.styleHints().colorScheme()` et son signal ; quand Qt annonce
  `Unknown`, utiliser la palette système observée avant application des couleurs
  personnalisées, jamais déduire le système de sa propre palette forcée. Réagir
  au changement de palette sans boucle d'événements ni lecteur audio recréé.
  Ne pas compter sur `setColorScheme()` pour forcer le rendu sur tous les bureaux.
  Fixer les couleurs exactes dans ce module seulement ; viser un contraste texte
  normal/fond d'au moins 4,5:1 et maintenir les symboles pour l'information d'état.
  Point de départ des rôles : fond `#292B2E`, surface `#32353A`, texte `#E2E3E6`,
  secondaire `#AEB4BC`, boucles `#D99A64`, shots `#7F98A8` ; en clair, fond
  `#F3F4F5`, surface `#E9ECEF`, texte `#2B3035`, secondaire `#59616A`, mêmes teintes
  d'accents. Ajuster seulement si les contrôles de contraste l'exigent, sans
  changer la direction validée. Garder la police KDE, deux graisses au maximum,
  chiffres de durée alignés et aucun effet décoratif. L'axe temporel et les
  rectangles restent l'élément structurant, pas une grille de cartes générique.
- [ ] **4. Vert et porte G ; commit :** `Suit le thème KDE et ajoute le forçage sombre`.
  **Validation KDE :** clair/sombre à chaud, forçage puis retour au système, tous
  les états marqué/actif/lecture et absence de dégradé/lueur. Attendre validation.

## Étape 6 — Exports communs et glisser permanent dans `glissés/`

**Fichiers :** créer `core/exporting.py`, `gui/sample_drag.py`,
`tests/test_exporting.py`, `tests/test_sample_drag.py` ; modifier
`gui/main_window.py`, `gui/candidates_panel.py`, `tests/test_main_window.py`,
`tests/test_candidates_panel.py`.

**Consomme :** `audio_io.export_candidates`, `LoadedTrack`, IDs de l'état et
`Settings.export_dir/export_format`. Ne pas importer le prototype.
**Produit :** `ExportReport(paths: tuple[Path, ...], error: str | None)` ;
`export_batch(samples: np.ndarray, sample_rate: int, track: Track,
candidates: tuple[Candidate, ...], destination: Path, file_format: str)
-> ExportReport`.
`export_drag(samples: np.ndarray, sample_rate: int, track: Track,
candidate: Candidate, export_dir: Path) -> Path` écrit dans `export_dir / 'glissés'`.

L'interface extrait ces valeurs de `LoadedTrack` ; le moteur ne dépend d'aucun
objet GUI et n'importe pas `gui.presentation`.

- [ ] **1. Tests d'abord :** WAV bouton dans `exports/`, WAV glisser dans
  `exports/glissés/`, FLAC bouton inchangé, sous-dossier Unicode, deux glissers
  distincts et empreinte du premier inchangée, fréquence 44 100 et deux canaux.
  Comparer le segment exporté et celui envoyé au lecteur, à la quantification près.
  Simuler disque plein au deuxième candidat : première réussite gardée et nommée
  dans le rapport, échec visible, fichier partiel nettoyé par le writer existant.
  Tester dossier réseau levant OSError et résultat sans fausse réussite.
- [ ] **2. Observer le rouge :**
  `uv run pytest -q tests/test_exporting.py tests/test_sample_drag.py`.
- [ ] **3. Implémenter les exports purs.** Réutiliser la réservation atomique et
  le nommage existants, traiter les candidats un par un pour rapporter les succès
  précédant un échec. PCM24/WAV obligatoire pour le glisser, sans supprimer même
  après annulation. Les boutons utilisent le dossier configuré ; sinon dialogue
  de destination, dont l'annulation n'écrit rien et ne change pas les paramètres.
- [ ] **4. Brancher la poignée seulement.** Seuil `QApplication.startDragDistance()`
  avec bouton gauche maintenu ; créer le WAV avant `QDrag.exec`, puis
  `QMimeData.setUrls([QUrl.fromLocalFile(...)])` et copie uniquement. Un simple
  clic, clic sur une autre colonne ou l'ouverture de piste ne crée ni WAV ni
  `glissés/`. Sans configuration, poignée désactivée avec explication ; aucun
  dialogue au milieu du geste. Échec d'écriture : message, pas de drag lancé.
  Enregistrer le chemin conservé, jamais « import Bitwig réussi » sur retour Qt.
- [ ] **5. Vert et porte G ; commit :** `Exporte les WAV glissés dans un sous-dossier permanent`.
  **Validation réelle :** Bitwig et Dolphin, copie, annulation/réessai, absence
  d'écoute au clic de poignée, réouverture du projet Bitwig après fermeture de
  Choppeur. Vérifier que les fichiers restent dans `glissés/` et séparés des
  exports par bouton. Attendre validation ; ne pas nettoyer les fichiers d'essai.

## Étape 7 — Actions, menus, aide et touche `M`

**Fichiers :** créer `gui/actions.py`, `tests/test_actions.py` ; modifier
`gui/main_window.py`, `gui/candidates_panel.py`, `tests/test_main_window.py`.

**Consomme :** méthodes de l'état et commandes d'export validées.
**Produit :** `ActionRegistry(window: QMainWindow, candidate_scope: QWidget)`
expose ses `QAction` par identifiant ; ces instances alimentent menus, boutons,
info-bulles et le dialogue « Aide > Raccourcis clavier » sans listes dupliquées.

- [ ] **1. Tests d'abord :** `M` bascule la marque du seul actif, deux appuis la
  retirent ; Espace joue/arrête, Échap arrête sans effacer les marques. Vérifier
  la présence de `M` dans l'action, menu et aide, l'absence de Ctrl+Espace,
  et les info-bulles des boutons pour les raccourcis définis dans le design.
  Dans un QLineEdit puis un dialogue modal, saisir `m m` : texte intact, aucun
  ordre de lecture ni marquage. Ctrl+A dans la bibliothèque ne marque pas les
  candidats. Pas d'actif/liste vide : raccourcis sans effet et actions désactivées.
- [ ] **2. Observer le rouge :**
  `uv run pytest -q tests/test_actions.py tests/test_main_window.py`.
- [ ] **3. Implémenter le registre et les menus Fichier, Lecture, Export, Aide.**
  Appliquer exactement la table du design corrigée. Limiter `M`, Espace et les
  sélections multiples au contexte des candidats et neutraliser ces actions lors
  d'une saisie ou d'un dialogue ; ne pas installer un filtre clavier global qui
  consomme tout. Réutiliser l'action album sur le bouton déjà visible ; l'entrée
  de menu est complémentaire. Haut/bas naviguent sans lecture automatique.
- [ ] **4. Vert et porte G ; commit :** `Centralise les actions et ajoute les raccourcis dont M`.
  **Validation :** clavier seul, menus/aide/info-bulles cohérents, saisie de texte
  normale et bouton album toujours visible. Attendre validation.

## Étape 8 — Wayland par défaut et recette finale

**Fichiers :** `src/choppeur/app.py`, `tests/test_app.py`, `tests/test_main_window.py`,
`docs/DECISIONS.md`, `docs/HISTORIQUE.md`, `README.md`.
Indexer uniquement les ajouts de cette étape dans les documents déjà modifiés.

**Prérequis :** étapes visuelles et drag validées sous Wayland explicite.
**Consomme :** interface complète, thème, actions et politique actuelle XCB.
**Produit :** politique par défaut Wayland pour une session Wayland, choix
explicite d'environnement préservé et instructions de secours XCB documentées.

- [ ] **1. Tests d'abord :** sans `QT_QPA_PLATFORM`, une session Wayland choisit
  `wayland` plutôt que `xcb` ; une valeur explicite `xcb` ou `wayland` est
  respectée ; une session X11 reste inchangée. Le portail KDE existant est
  conservé. Remplacer le test imposant l'ancien défaut XCB, pas le supprimer.
- [ ] **2. Observer le rouge :** `uv run pytest -q tests/test_app.py`.
- [ ] **3. Modifier uniquement la politique de démarrage concernée.** Ne pas
  masquer un problème de plugin en basculant silencieusement de backend, et ne
  prétendre supprimer la possibilité XCB. Documenter l'ancien contournement des
  zébrures et sa vérification manuelle avec la nouvelle interface.
- [ ] **4. Recette de non-régression et porte G.** Piste mono/stéréo, piste longue,
  nombreux recouvrements, longueurs héritées, aucun candidat, album vide/illisible,
  analyse en cours, changements de piste/paramètres et erreurs audio/export.
  Contrôler que seul le contenu de la piste affichée est exporté. L'analyse d'album
  et sa progression gardent leur comportement existant ; cette refonte n'invente
  pas une sélection/export multi-pistes ni une nouvelle restitution des albums.
- [ ] **5. Commit :** `Utilise Wayland par défaut après validation de la nouvelle interface`.
  **Validation utilisateur finale :** lancement simple `uv run choppeur`, absence
  de zébrures, thèmes KDE, clic/second clic/Ctrl+clic/M/Espace/fin naturelle/glisser/export,
  Bitwig/Dolphin et essai `QT_QPA_PLATFORM=xcb uv run choppeur` si nécessaire.
  Si la configuration native révèle une régression bloquante, la signaler et
  arrêter : ne pas déclarer la compatibilité acquise sur la base du prototype.

## Auto-revue et risques résiduels

- Couverture : sections 1/8 du design → étapes 1/2 ; disposition/liste → 3 ;
  onde/couloirs/infos → 4 ; KDE → 5 ; exports/`glissés/` → 6 ; clavier/`M` → 7 ;
  validation native et bouton album conservé → 3/7/8. Les cinq risques de Review
  Focus ont un test propriétaire explicite. Tous les signaux/interfaces partagés
  sont nommés ; `LoadedTrack` reste une donnée GUI et ne franchit pas la frontière
  vers `core/exporting.py`.
- Chaque étape doit livrer une tranche vérifiable ; l'apparence intermédiaire
  n'est pas présentée comme la refonte complète. Les interfaces héritées privées
  peuvent changer, avec remplacement explicite des tests devenus contraires au
  design, mais sans perdre la couverture des échecs audio, threads et exports.
- Les glissers annulés créent volontairement des fichiers permanents. Un NAS
  figé au niveau du noyau peut bloquer une écriture ; un message Python ne peut
  pas interrompre un tel appel système. Pas de promesse d'un timeout inexistant.
- Le bug de fermeture après dépassement des 30 s d'analyse, connu dans l'audit,
  n'est pas déclaré corrigé par cette refonte. La fermeture du nouveau lecteur
  est couverte, mais les changements de cycle de vie des workers d'analyse
  nécessitent leur propre correctif/test/commit si abordés séparément.
- L'exécution prévue est directe dans cette session, **avec validation après
  chaque étape**, sans délégation d'implémentation ni lancement en continu.
  Le choix d'un éventuel worktree ne doit ni perdre les changements existants ni
  déclencher une création de dossier hors des emplacements autorisés.
- Aucun code produit modifié pour écrire ce plan. Ne commencer l'étape 1 qu'après
  confirmation de ce plan par l'utilisateur.
