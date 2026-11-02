# AGENTS.md — Chopper

Instructions permanentes pour les agents IA (OpenCode, Claude Code) sur ce projet. À lire avant toute action.
Historique des bugs corrigés : `docs/HISTORIQUE.md`.

## Le projet en une phrase
Logiciel Linux de bureau (interface graphique) qui analyse un morceau ou un album
de la bibliothèque de l'utilisateur, propose automatiquement plusieurs samples
(boucles calées sur la mesure + one-shots), les fait préécouter, puis les exporte
nommés automatiquement.

Spécification complète : `docs/SPEC.md`. Décisions techniques et leurs raisons :
`docs/DECISIONS.md`. Feuille de route : `docs/ROADMAP.md`.

## L'utilisateur
- Non-développeur professionnel, curieux, apprend en pilotant OpenCode et Claude Code.
- Répondre en français, clairement, sans jargon non expliqué.
- Le logiciel et sa documentation utilisateur sont en anglais adapté aux home-studios.
- Une chose à la fois : ne pas empiler les options. Proposer UNE solution,
  la justifier en une phrase.
- Avant chaque question posée, dire à quoi sert la réponse.
- Pas de préambule, pas de compliment, pas de formule de clôture.
- Signaler les incertitudes. Ne jamais inventer une API : vérifier dans la
  doc officielle ou le code source de la bibliothèque.

## Règles de travail
- Avancer par petites étapes vérifiables (une étape de `docs/ROADMAP.md` à la fois).
- Après chaque étape : lancer les tests, montrer le résultat, attendre validation.
- Ne jamais créer de dossier dans le home (`~`) de l'utilisateur sans lui
  demander l'emplacement.
- Ne jamais modifier ni supprimer les fichiers audio sources : lecture seule.
- Pas de Docker, pas de service web, pas de serveur local.
- Commits git petits et explicites, en français.

## Stack (voir DECISIONS.md pour le pourquoi)
- Python 3.12, environnement géré par `uv`.
- Interface : PySide6 (Qt 6). Forme d'onde : pyqtgraph.
- Temps et premiers temps de mesure : `beat_this` (CPJKU, licence MIT).
- Attaques (one-shots), séparation percussif/harmonique, tempo : librosa 0.11
  (la 1.0 est sortie en août 2026 : migration à faire comme une étape à part, tests à l'appui).
- Lecture/écriture audio : soundfile ; décodage MP3/AAC via ffmpeg.
- Préécoute : sounddevice.
- Tags des morceaux (artiste, album, titre) : mutagen.
- Cache des analyses : SQLite (module standard `sqlite3`).
- Tests : pytest.

## Architecture (règle d'or : le moteur ne connaît pas l'interface)
```
src/chopper/
  core/        # moteur, AUCUN import Qt ici
    audio_io.py     # charger un fichier, exporter un extrait
    rhythm.py       # beat_this : temps + premiers temps de mesure
    onsets.py       # librosa : attaques, séparation percussif/harmonique
    candidates.py   # choisir les meilleurs samples (boucles / one-shots)
    naming.py       # nommage automatique des fichiers exportés
    cache.py        # SQLite : ne pas réanalyser un fichier inchangé
    models.py       # dataclasses : Track, Analysis, Candidate
  gui/         # interface PySide6, appelle core/ uniquement
    main_window.py
    library_panel.py    # navigation dossiers / albums / pistes
    waveform_view.py    # forme d'onde + marqueurs des candidats
    candidates_panel.py # liste, préécoute, cocher, exporter
    settings_dialog.py
    workers.py          # analyses en arrière-plan (QThread)
  app.py       # point d'entrée
tests/
```
Pourquoi : le moteur doit pouvoir être testé sans interface, et resservir
plus tard (ligne de commande, autre interface, fiche d'analyse).

## Portabilité (le logiciel sera prêté)
- Aucun chemin en dur. Les chemins viennent des paramètres utilisateur.
- Paramètres dans `~/.config/chopper/settings.toml` (standard XDG,
  via `platformdirs`), cache dans `~/.cache/chopper/`.
  Si le nouveau fichier manque, lire l'ancien `choppeur/settings.toml` sans le
  modifier ; sauvegarder ensuite uniquement sous `chopper`. Garder l'ancien cache.
- Fonctionner sans GPU (CPU, plus lent) ; utiliser le GPU s'il existe.
- Les dossiers réseau (NAS monté) doivent marcher comme des dossiers locaux.

## Commandes
- Installer : `uv sync`
- Lancer : `uv run chopper` (alias temporaire `choppeur` pour les anciens lanceurs).
- Tests : `uv run pytest`
- Activer les hooks après un clone : `uv run pre-commit install`

## Pre-commit (règle permanente)
Le fichier `.pre-commit-config.yaml` commence par les hooks du modèle personnel
(pre-commit-hooks, semgrep, gitleaks, pas-de-chemin-perso). Ne jamais les retirer
ni réécrire le fichier : seulement AJOUTER des hooks à la fin.
Ne jamais contourner les hooks (`--no-verify`).
