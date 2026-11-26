# Parcours Chopper — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Faciliter le redimensionnement, l’ouverture de médias, la découpe et l’édition du tempo sans modifier les sources.

**Architecture:** MainWindow orchestre les actions Qt et leurs workers existants. Les réglages et le rendu des extraits restent dans `core/`, indépendants de Qt ; les entrées depuis le bureau, le dépôt et la CLI réutilisent la bibliothèque existante.

**Tech Stack:** Python 3.12, PySide6, pyqtgraph, librosa avec SoXR, SoundFile, SQLite, pytest, Git et Gitleaks.

**Spec:** [Design validé](../specs/2026-11-26-workflow-chopper-design.md).

## Global Constraints

- Une étape vérifiée et validée avant la suivante ; tests rouges puis verts, suite complète et petits commits en français avec hooks actifs. Espace de travail isolé, base `2a11211`.
- Garder `chopper <fichier>`, une piste active par fenêtre, les choix existants et les fichiers sources en lecture seule. Aucun Qt dans `core/`.
- Ne pas installer réellement ni changer les associations par défaut. Isoler cache, préférences et exports de test ; utiliser des médias synthétiques.
- Avant intégration, revoir le résultat. Avant publication, vérifier la cible et tous les commits sortants ; ni secret, réglage utilisateur, média privé, modification locale de Semgrep, ni push forcé.

## Review Focus

1. Petite fenêtre et panneaux masqués : placer puis déplacer les séparateurs sans perdre un panneau, le zoom ou l’alignement des rectangles (tâche 1).
2. Un dossier replié, un fichier du même album et un dépôt mixte : pas de doublon, ni déplacement des originaux, ni remplacement de la piste active (tâche 2).
3. Deux processus avec le même cache, le même dossier d’export ou des préférences initialement identiques : conserver les résultats, les fichiers et les modifications indépendantes (tâche 3).
4. Chemin relatif avec espaces et plage invalide au-delà de l’audio : chemin résolu depuis le dossier d’appel, aucun effet d’export en cas d’argument invalide (tâche 5).
5. Retouches BPM successives avec alternance des deux modes : nouveau calcul depuis l’original, mêmes données de préécoute et d’export, aucune réécriture d’export existant (tâches 6 et 7).

### Task 1: Panneaux redimensionnables et clic neutre

**Files:** `src/chopper/gui/main_window.py`, `waveform_view.py`, `candidates_panel.py`, `tests/test_main_window.py`, `test_waveform_selection.py`, `test_manual_selection.py`, `test_sample_lanes.py`.

**Interfaces:** préserver les attributs `waveform_view`, `sample_lanes`, `candidates_panel` et la sélection existante. Le séparateur vertical contient les trois vues dans cet ordre ; la commande **Whole track** garde le même parcours.

- [x] Rouge : `test_workspace_splitters_resize_without_collapsing_views` déplace les séparateurs par événements Qt, vérifie les hauteurs/largeurs redistribuées, les curseurs `SizeVerCursor` et `SizeHorCursor`, et la disponibilité des trois vues en fenêtre compacte. Vérifier qu’une liste initialement vide peut redevenir utilisable après analyse. `test_click_outside_preserves_manual_results_without_dialog` vérifie la région, les résultats, les marques et l’absence de préécoute/confirmation. Vérifier le curseur sur les poignées et la remise au curseur normal. Remplacer les seules anciennes assertions qui imposaient une demande de retour après un clic.
- [x] Lancer `uv run --no-sync pytest -q tests/test_main_window.py tests/test_waveform_selection.py tests/test_manual_selection.py tests/test_sample_lanes.py` : constater les nouveaux échecs attendus.
- [x] Installer les séparateurs natifs Qt non rétractables, conserver la répartition verticale par défaut `9:4:17` hors contraintes minimales, vérifier les curseurs et retirer uniquement le déclenchement du retour sur clic hors sélection. Préserver le seuil de glissement et les actions explicites.
- [x] Relancer les tests ciblés et la suite ; contrôler l’alignement après redimensionnement. Commit `Rend les panneaux redimensionnables et préserve la sélection au clic`, puis attendre validation.

### Task 2: Ouvrir et ajouter depuis le bureau

**Files:** `src/chopper/app.py`, `src/chopper/gui/main_window.py`, `library_panel.py`, `scripts/install_desktop.py`, `scripts/install_integrations.py`, tests `test_app.py`, `test_main_window.py`, `test_library_panel.py`, `test_desktop_install.py`, `test_install_integrations.py`, `test_uninstall.py`, `README.md`.

**Interfaces:** `MainWindow.open_path(path: Path) -> None` ouvre un fichier ou ajoute un dossier ; `open_file(path: Path) -> None` garde son contrat. Le dépôt réutilise `LibraryPanel.add_track` et `add_album` sans déclencher `open_file`. Le raccourci accepte une cible locale via `%f`.

- [ ] Rouge : tester lancement d’une piste et d’un album, dépôt mixte avec URL non locale et doublon, piste active conservée, fichiers sources identiques. Dans les tests d’installation, vérifier le lancement d’un chemin avec espaces, la déclaration des types audio/dossiers, l’absence de modification des associations par défaut, la mise à jour d’un raccourci reconnu et le refus d’un raccourci étranger.
- [ ] Relancer `uv run --no-sync pytest -q tests/test_app.py tests/test_main_window.py tests/test_library_panel.py tests/test_desktop_install.py tests/test_install_integrations.py tests/test_uninstall.py` ; attendu : fonctionnalités nouvelles absentes à l’état initial.
- [ ] Router les cibles locales vers la bibliothèque existante ; accepter la copie au sens du protocole de dépôt Qt (ajout de références seulement), jamais l’action de déplacement. Ajouter `MimeType` et `%f` au raccourci généré ; conserver le contenu historique exact comme preuve d’adoption des anciens raccourcis et les vérifications du journal d’intégrations.
- [ ] Relancer tests ciblés et complets ; vérifier le `.desktop` et une ouverture via GLib avec une sonde locale. Décrire la distinction entre test isolé et menu Dolphin installé. Commit, puis validation.

### Task 3: Mémoire des dialogues et instances indépendantes

**Files:** `src/chopper/core/settings.py`, `cache.py` si une régression le justifie, `src/chopper/gui/main_window.py`, `settings_dialog.py`, `export_folder_dialog.py`, `tests/test_settings.py`, `test_main_window.py`, `test_settings_dialog.py`, `test_export_folder_dialog.py`, nouveau `tests/test_multi_instance.py`.

**Interfaces:** un emplacement accepté par usage (`library`, `album`, `track`, `export`) ; la piste mémorise son dossier parent. Le réglage existant `export_dir` reste la destination choisie explicitement.

- [ ] Rouge : tester les quatre emplacements indépendants après recréation de la fenêtre, annulation sans écriture, dossier supprimé, et absence de réglage implicite d’export. Faire tourner deux processus synchronisés avec le même espace de test : lecture/écriture de cache, sauvegarde de changements de préférences distincts et deux exports vers un même dossier. Un comportement déjà correct devient un test de régression, pas un échec artificiel.
- [ ] `uv run --no-sync pytest -q tests/test_settings.py tests/test_main_window.py tests/test_settings_dialog.py tests/test_export_folder_dialog.py tests/test_multi_instance.py` ; localiser précisément les conflits observés.
- [ ] Mémoriser uniquement les choix acceptés et réutiliser une destination seulement si elle est encore accessible. Empêcher une écriture de préférence indépendante d’en écraser une autre ; ne modifier la gestion du cache ou des exports que si les sondes le nécessitent.
- [ ] Relancer les sondes et la suite ; documenter le comportement lorsque deux instances éditent volontairement le même champ. Commit, puis validation.

### Task 4: Longueurs harmonisées et durée fixe des one-shots

**Files:** `src/chopper/core/models.py`, `settings.py`, `candidates.py`, `src/chopper/gui/settings_dialog.py`, `main_window.py`, `workers.py`, tests `test_settings.py`, `test_settings_dialog.py`, `test_candidates.py`, `test_candidate_window.py`, `test_workers.py`, `README.md`.

**Interfaces:** `LOOP_LENGTHS_BARS` est le catalogue de choix des deux interfaces, sans modifier la sélection automatique par défaut. Le réglage `one_shot_duration_seconds` succède à `max_one_shot_seconds` avec lecture rétrocompatible du TOML ; l’option de découpe de la tâche 5 prend la durée dans le même réglage temporaire.

- [ ] Rouge : tester les cinq longueurs disponibles dans les deux interfaces, leur persistance et les défauts historiques. Tester un one-shot de durée donnée malgré silence et attaque suivante, le raccourcissement à la limite, aucune sortie vide, et migration numérique sans écriture lors de la lecture.
- [ ] `uv run --no-sync pytest -q tests/test_settings.py tests/test_settings_dialog.py tests/test_candidates.py tests/test_candidate_window.py tests/test_workers.py` ; constater que les longueurs et les durées ne correspondent pas encore.
- [ ] Séparer les choix autorisés des défauts, garder l’analyse existante, remodeler la fin de one-shot en durée fixe bornée par la source ou la sélection. Mettre à jour les appels au moteur et les libellés anglais.
- [ ] Relancer tests ciblés et complets ; décrire l’effet de la migration sur les prochains résultats. Commit, puis validation.

### Task 5: Options de découpe en ligne de commande

**Files:** `src/chopper/app.py`, `src/chopper/gui/main_window.py`, `workers.py`, `install.sh` si nécessaire pour le dossier d’appel, `tests/test_app.py`, `test_main_window.py`, `test_install.py`, `README.md`.

**Interfaces:** `--start SECONDS` (défaut 0), `--end SECONDS` (défaut fin de piste), `--bars BARS` (un choix du catalogue), `--one-shot-duration SECONDS` (0,1 à 30), `--max-samples N` (1 à 64), `--export-dir PATH`. Options réservées à une piste ; sans `--bars`, utiliser les longueurs automatiques configurées. Réutiliser `open_path` et le réglage de durée des tâches précédentes.

- [ ] Rouge : tester une piste relative avec espaces depuis un autre dossier, les options Qt existantes, une plage bornée avec boucles et one-shots, la distinction entre affichage seul et export explicite. Tester NaN, bornes inversées ou hors piste, option appliquée à un dossier, annulation d’analyse et absence de modification des préférences.
- [ ] `uv run --no-sync pytest -q tests/test_app.py tests/test_main_window.py tests/test_install.py` ; attendu : options nouvelles non reconnues et chemin d’appel perdu par le lanceur actuel.
- [ ] Valider les arguments avant la recherche, puis les bornes par rapport au nombre de trames décodées avant tout export. Appliquer les options à la requête en mémoire, réutiliser les workers ; attendre un résultat valide avant de rendre les résultats définitifs ou d’exporter. Préserver le comportement sans option et les arguments relatifs au dossier d’appel.
- [ ] Relancer tests ciblés et complets, documenter des exemples reproductibles. Commit, puis validation.

### Task 6: Rendu audio partagé du changement de vitesse

**Files:** `src/chopper/core/models.py`, nouveau `src/chopper/core/sample_render.py`, `audio_io.py`, `exporting.py`, `naming.py`, `src/chopper/gui/preview_player.py`, tests `test_audio_io.py`, `test_exporting.py`, `test_naming.py`, `test_preview_player.py`, nouveau `tests/test_sample_render.py`.

**Interfaces:** distinguer `Candidate.bpm` (courant), `source_bpm: float | None` et `playback_rate: float` (défaut `1.0`) ; les bornes restent en temps source. `render_candidate(samples, sample_rate, candidate) -> np.ndarray` sert à la préécoute et aux exports sur une même base de trames. L’édition de la tâche 7 produit ces candidats sans changer leur identité dans l’interface.

- [ ] Rouge : rendre une sinusoïde stéréo 120 → 150 BPM, vérifier durée, fréquence audio, canaux conservés et fréquence de sortie inchangée ; tester un ralentissement, le rendu à vitesse 1, la borne de rendu, la préécoute, les exports WAV/FLAC et le WAV du glisser-déposer. Les sorties ordinaires gardent leur protection contre les collisions.
- [ ] `uv run --no-sync pytest -q tests/test_sample_render.py tests/test_audio_io.py tests/test_exporting.py tests/test_naming.py tests/test_preview_player.py` ; attendu : rendu accéléré absent.
- [ ] Extraire le passage source une fois par rendu, rééchantillonner sur l’axe du temps avec librosa/SoXR `soxr_hq` et conserver la fréquence de sortie. Refuser avant allocation les valeurs non finies, hors bornes ou entraînant un rendu vide/excessif ; définir et tester une limite de rendu à partir de la taille de sortie. Calculer la durée présentée à partir de la même règle de trames. Inclure le BPM saisi dans le nom d’export, même pour un one-shot, si renseigné.
- [ ] Relancer tests ciblés et complets ; vérifier l’égalité préécoute/export à la quantification près. Commit, puis validation.

### Task 7: Édition du BPM dans le tableau

**Files:** `src/chopper/gui/candidates_panel.py`, `sample_state.py`, `main_window.py`, `sample_lanes.py`, nouveau `src/chopper/gui/bpm_dialog.py`, tests `test_candidates_panel.py`, `test_sample_state.py`, `test_main_window.py`, `README.md`.

**Interfaces:** la demande d’édition transporte un identifiant d’échantillon ; une édition valide remplace uniquement les propriétés de ce même identifiant. La vitesse et l’étiquette restent indépendantes.

- [ ] Rouge : éditer la cellule BPM sur une ligne distincte de la sélection, vérifier 120 → 150 en accélération puis 160 en **BPM only**, vitesse identique après l’étiquette et durée toujours visible. Tester annulation, BPM invalide, one-shot sans référence, ligne devenue obsolète, préécoute en cours, session verrouillée et conservation du marquage.
- [ ] `uv run --no-sync pytest -q tests/test_candidates_panel.py tests/test_sample_state.py tests/test_main_window.py` ; attendu : la cellule n’offre pas encore d’édition.
- [ ] Ouvrir l’éditeur uniquement depuis la colonne BPM, en réutilisant le rendu de la tâche 6. Pour **Change speed**, appliquer la nouvelle vitesse par rapport au tempo source et jamais au dernier tempo affiché. Mettre à jour le tableau sans déplacer les rectangles ni déclencher de lecture spontanée ; ne pas permettre un changement non voulu pendant un export ou une recherche.
- [ ] Relancer tests ciblés et complets ; vérifier l’affichage clair/sombre et documenter les deux modes. Commit, puis validation.

### Task 8: Revue, intégration et publication

- [ ] Effectuer la revue indépendante du lot, reproduire et corriger les défauts importants, mettre à jour `docs/HISTORIQUE.md`. Relancer `uv run --no-sync pytest -q`, Ruff, mypy, Bandit, `git diff --check` et `uv run --no-sync pre-commit run --all-files` sur le résultat à intégrer.
- [ ] Vérifier la branche habituelle et l’avance rapide ; laisser les changements locaux intacts, particulièrement `.pre-commit-config.yaml`. En cas de divergence, ne pas forcer l’intégration ; vérifier le résultat en isolation avant toute fusion dans le dossier habituel.
- [ ] Contrôler avec Gitleaks en masquant les résultats et examiner les chemins concernés par **tous** les commits sortants. Refaire les tests sur le résultat intégré. Demander la confirmation de la destination du push ; ne rien envoyer si une vérification échoue. Après le push, vérifier la référence distante et distinguer tests automatisés et limites de recette réelle.
