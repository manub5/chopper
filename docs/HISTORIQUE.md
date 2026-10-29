# Historique des corrections

Journal des bugs trouvés et corrigés, avec leur cause.
À consulter pour comprendre pourquoi le code est écrit ainsi ; les règles en vigueur sont dans `DECISIONS.md`.
Note : les mentions « cet environnement » / « ce bac à sable » désignent l'environnement d'une IA de développement
sans audio, sans affichage et avec un réseau restreint — pas la machine de l'utilisateur. Depuis, semgrep tourne
dans pre-commit et la préécoute ne joue plus en boucle.

## 29/10/2026 — Blocage après l'échec de l'analyse d'une piste (état des lieux, bug A)

- Cause : `TrackAnalysisWorker` émettait `failed` en cas d'erreur, mais seul
  `finished` demandait l'arrêt du QThread. Son calcul était terminé, mais sa
  boucle d'événements restait active ; la fenêtre refusait alors toute nouvelle
  analyse, même après avoir réactivé la bibliothèque.
- Reproduction avant correction : test avec une vraie fenêtre et un vrai QThread,
  déclinés en erreur de lecture (`OSError`) et erreur de calcul (`RuntimeError`).
  Les deux cas échouaient sur l'attente de libération du thread.
- Correction minimale : dans `start_in_thread`, raccorder aussi `failed` à
  `thread.quit()` pour les workers de piste. Le signal de succès n'est pas émis
  sur erreur et les références ne sont toujours libérées qu'à la fin du thread.
- Non-régression : le test vérifie le message d'erreur, l'absence de faux
  résultats, la libération du worker/thread et l'analyse réussie d'une autre piste.
  La suite complète `uv run pytest` ainsi que Ruff, mypy et Bandit ont été lancés.
- Effets de bord : aucun changement des sources audio, des exports, du cache ou
  des paramètres ; aucune nouvelle écriture persistante. Le traitement des albums
  reste inchangé. Le dépassement du délai de fermeture (bug B) reste à traiter.

## Corrections suite au premier essai réel (Kubuntu 24.04, KDE Plasma)

### Bibliothèque : chargement dossier par dossier, pas tout l'arbre d'un coup
- Bug : `LibraryPanel` parcourait toute l'arborescence récursivement dès
  `set_root()`. Sur un NAS/dossier réseau (latence par accès, parfois des
  milliers de fichiers), ça pouvait geler l'interface durablement, voire
  tourner indéfiniment sur un lien symbolique circulaire — perçu comme
  "impossible à charger".
- Correctif : un seul niveau chargé à la fois ; un dossier reçoit un enfant
  provisoire ("…") et n'est réellement lu qu'à son ouverture (signal
  `itemExpanded`). Une entrée illisible (lien cassé, droit réseau refusé) est
  ignorée individuellement au lieu d'interrompre tout le dossier. Si le
  dossier racine choisi est lui-même illisible, `load_failed` est émis et
  affiché dans la barre de statut plutôt que de laisser un panneau vide sans
  explication.
- Incertitude restante : un partage réseau exposé uniquement via un
  protocole KIO de Dolphin (`smb://…`) sans montage FUSE/gvfs réel ne
  correspond à aucun chemin de fichier local ; un tel chemin choisi dans la
  boîte de dialogue resterait illisible pour Python. À vérifier : le dossier
  doit être monté (Dolphin propose en général de le monter automatiquement
  via gvfs, ce qui le rend accessible comme un dossier normal).

### Préécoute : erreurs remontées au lieu d'être avalées silencieusement
- Bug : une exception de `sounddevice` (ex. aucun périphérique de sortie
  disponible/configuré) était avalée silencieusement par Qt (les exceptions
  dans un slot ne remontent pas) : cliquer sur "Préécouter" ne faisait
  simplement rien, sans indice sur la cause.
- Correctif : `sd.play`/`sd.stop` sont maintenant protégés ; toute erreur est
  émise via le signal `preview_failed` et affichée dans la barre de statut.
  Cocher un candidat sans avoir cliqué dessus (sélection Qt "courante" non
  positionnée) est aussi couvert : la préécoute retombe sur le premier
  candidat coché s'il n'y a pas de ligne sélectionnée.
- Incertitude : non testable dans cet environnement de développement (aucun
  périphérique audio dans ce bac à sable — `sounddevice.query_devices()` y
  est vide). Le prochain clic sur "Préécouter" chez toi affichera le message
  d'erreur exact de PortAudio dans la barre de statut si ça échoue encore ;
  ce message précisera la vraie cause.

### Artefacts d'affichage ("zébrures") en session Wayland
- Sur KDE Plasma/Kubuntu, certaines applications Qt Widgets ont des bugs de
  rafraîchissement connus en session Wayland native (zones mal repeintes).
  `app.py` force maintenant XCB (X11 via XWayland) par défaut quand
  `XDG_SESSION_TYPE=wayland` et qu'aucun `QT_QPA_PLATFORM` n'est déjà choisi
  explicitement — XCB est le chemin le plus éprouvé pour PySide6 côté
  widgets.
- Incertitude : non vérifiable ici (pas d'affichage réel dans ce bac à
  sable). Si des zébrures persistent malgré XCB, ou si XCB pose un autre
  problème (affichage flou en cas d'écran haute résolution, par exemple),
  fixer explicitement `QT_QPA_PLATFORM=wayland` (ou une autre valeur) avant
  `uv run choppeur` annule ce choix automatique.
- Le fait que l'ancien chargement récursif de la bibliothèque provoquait
  aussi énormément de mises à jour de widgets d'un coup a pu aggraver ou
  causer ces artefacts ; le correctif de chargement paresseux ci-dessus
  devrait déjà réduire le phénomène indépendamment du choix XCB/Wayland.

## Revue qualité complète (octobre 2026) (analyse statique, typage, sécurité, revue de bugs, tests aux limites)

### Outils mis en place (groupe `dev` de `pyproject.toml`)
- `ruff` (lint + format), config dans `[tool.ruff]`/`[tool.ruff.lint]` :
  `line-length = 110` (plutôt que 88 par défaut : évite de reformater
  agressivement du code déjà lisible), règles E/F/I/UP/B/BLE/C4/SIM/RUF/PLW/PYI.
- `mypy`, config dans `[tool.mypy]`. Un fichier `src/choppeur/py.typed` a été
  ajouté (PEP 561) pour que mypy analyse correctement les imports de
  `choppeur` depuis `tests/`, pas seulement depuis `src/`.
- `bandit` pour l'analyse de sécurité. **Semgrep n'a pas pu être utilisé** :
  son `--config=auto` a besoin de `semgrep.dev`, bloqué par la politique
  réseau de cet environnement de développement (mêmes restrictions que
  `github.com`/`download.pytorch.org` documentées plus haut). Bandit tourne
  en local sans dépendance réseau et couvre l'essentiel pour du Python pur
  sans service web (pas d'injection SQL possible : requêtes SQLite
  paramétrées ; pas de `shell=True`, `eval`, `pickle`, ni désérialisation
  dangereuse dans tout le code).
- `pre-commit` (`.pre-commit-config.yaml`, hooks `language: system` via
  `uv run` — pas de dépôts externes à cloner, donc rien qui ait besoin d'un
  accès réseau bloqué ici) : lance ruff, mypy, bandit (`-ll`, seuil sévérité
  moyenne+ : le seul signalement bandit actuel, B404 sur l'import de
  `subprocess`, est accepté ci-dessus et ne doit pas bloquer chaque commit)
  et toute la suite de tests à chaque commit. Activé avec
  `uv run pre-commit install` (à refaire après un nouveau clone : ce hook
  n'est pas versionné, seul `.pre-commit-config.yaml` l'est).

### Bugs réels trouvés et corrigés (pas de simples remarques de style)
Trouvés soit par les outils ci-dessus, soit par une revue manuelle du code
en profondeur avec vérification empirique (reproduction du plantage/du
comportement avant de corriger, jamais une simple lecture) :

1. **Cache SQLite inutilisable depuis le thread d'analyse** (`core/cache.py`) :
   `sqlite3.connect()` refuse par défaut qu'une connexion créée dans un
   thread soit utilisée depuis un autre (`ProgrammingError`). Le cache est
   créé dans `MainWindow` (thread principal) mais interrogé/écrit depuis
   `TrackAnalysisWorker`/`AlbumAnalysisWorker` (QThread) : ça plantait à
   chaque analyse. Corrigé avec `check_same_thread=False` + un verrou
   (`threading.Lock`) autour de chaque accès. Reproduit puis vérifié avec un
   vrai `threading.Thread` dans le test.
2. **Course (TOCTOU) sur l'export de deux candidats au même nom en même
   temps** (`core/audio_io.export_segment`) : le nom était choisi
   (`unique_path`) puis écrit en deux étapes séparées ; deux exports
   simultanés pouvaient choisir le même nom et l'un écrasait l'autre.
   Corrigé par une réservation atomique du fichier (`os.O_CREAT|O_EXCL`) ;
   `export_candidates` retente avec le nom suivant sur collision. Si
   l'écriture échoue ensuite pour une autre raison (disque plein), le nom
   réservé est libéré (`unlink`) au lieu de rester définitivement "brûlé".
3. **`MainWindow` pouvait lancer deux analyses en même temps** et détruire un
   `QThread` encore en cours d'exécution (`self._thread`/`self._worker`
   étaient écrasés sans condition) : plantage natif (SIGABRT/SIGBUS)
   reproduit à coup sûr en sélectionnant une deuxième piste avant la fin de
   l'analyse de la première. Corrigé par un garde-fou
   (`_is_analysis_running`) et en désactivant bibliothèque/bouton pendant
   qu'une analyse tourne (`_set_busy`).
   - Corollaire découvert en écrivant les tests de ce correctif : relâcher la
     référence Python vers le thread/worker (pour laisser Qt le détruire)
     **depuis un slot connecté à `worker.finished`** re-plante, car à ce
     moment `thread.quit()` (branché sur ce même signal) n'a pas forcément
     encore été traité : le thread est donc encore réellement vivant. La
     référence n'est relâchée que dans un slot branché sur `thread.finished`
     (qui ne peut être émis qu'une fois le thread réellement arrêté).
4. **Fermer la fenêtre pendant une analyse d'album fermait le cache SQLite
   après un délai fixe de 2 s**, sans égard pour le thread qui pouvait
   encore tourner (une seule analyse dépasse largement 2 s sur CPU) :
   chaque piste restante échouait alors sur "Cannot operate on a closed
   database". Corrigé : `closeEvent` appelle `AlbumAnalysisWorker.stop()`
   puis attend la fin réelle du thread (jusqu'à 30 s, au lieu d'un délai
   arbitraire) avant de fermer le cache.
5. **Le format d'export choisi dans les paramètres (WAV/FLAC) n'avait aucun
   effet** : `CandidatesPanel.export_checked` n'acceptait pas de paramètre de
   format et écrivait toujours du WAV. `MainWindow` ne lisait jamais
   `settings.export_format`. Corrigé : le format et le sous-type sont
   maintenant transmis de bout en bout.
6. **Performance quadratique sur un morceau de plusieurs heures**
   (`core/candidates.find_loop_candidates`) : la régularité du tempo
   refiltrait tout le tableau des premiers temps de mesure pour chaque
   candidat (recherche linéaire répétée), et le niveau RMS global du
   morceau était recalculé pour chaque candidat au lieu d'une seule fois.
   Sur un morceau synthétique de ~3 h (5400 mesures), l'analyse dépassait
   2 minutes (interrompue manuellement, jamais terminée en pratique) contre
   ~6 s après correctif (recherche dichotomique avec `bisect`, RMS global
   calculé une fois par l'appelant).
7. **Analyse d'un album entier : la lecture des tags de chaque piste se
   faisait sur le thread de l'interface**, avant même de démarrer le thread
   d'arrière-plan — sur un dossier réseau avec des milliers de pistes, ça
   pouvait geler l'interface avant même l'apparition de la barre de
   progression. Corrigé : `AlbumAnalysisWorker` parcourt maintenant le
   dossier lui-même, dans `run()` ; la barre de progression démarre
   indéterminée et se met à jour une fois le dossier scanné
   (`scan_done`).
8. **Une seule piste vide/corrompue dans un dossier faisait planter la
   lecture de tags de tout l'album** : `mutagen.File(...)` lève sa propre
   exception (`EmptyChunk`, etc.) sur un fichier illisible au lieu de
   renvoyer `None` comme sur un fichier simplement non-tagué. Corrigé dans
   `core/audio_io.read_track` : ce cas est maintenant traité comme "pas de
   tags" (repli sur le nom de fichier), pas comme une erreur fatale.
9. **Un dossier réseau qui se déconnecte pendant le parcours de la
   bibliothèque d'un album** (avant même la première piste) tuait
   `AlbumAnalysisWorker.run()` avant `finished.emit()` : le bouton et la
   bibliothèque restaient désactivés indéfiniment, sans aucun signal pour le
   signaler ni moyen de s'en sortir sans relancer l'application. Corrigé par
   un nouveau signal `scan_failed`, affiché dans la barre de statut, qui
   permet quand même à `finished` d'être émis.
10. **`subprocess.run(["ffmpeg", ...])` cherchait `ffmpeg` sur le `PATH` à
    chaque appel** (bandit B607) plutôt que d'utiliser le chemin déjà résolu
    par `shutil.which`. Corrigé (chemin résolu une fois, réutilisé).

### Tests aux limites ajoutés
Fichier vide/corrompu/tronqué, silence total, mono vs stéréo, noms de
fichiers avec caractères Unicode (emoji, accents, texte non latin) écrits
réellement sur le disque, dossier avec 3000 pistes (temps borné), morceau
de ~33 minutes/1000 mesures (temps borné, régression de performance),
chemin réseau qui se déconnecte en cours d'analyse d'album (au milieu, et
avant même de commencer), disque plein pendant un export (simulé), deux
exports simultanés du même nom.

### Volontairement non corrigé (et pourquoi)
- **Un montage réseau réellement figé au niveau du noyau** (ex. un NFS "hard
  mount" qui ne répond plus du tout) peut bloquer indéfiniment un appel
  `os.stat`/`open` en cours, sans qu'aucun timeout Python ne puisse
  l'interrompre depuis l'intérieur du thread concerné. Un vrai correctif
  demanderait un mécanisme de "watchdog" (processus séparé, ou déclaration
  du montage en "soft" côté système) hors du périmètre raisonnable de cette
  revue ; seuls les cas où le système d'exploitation renvoie effectivement
  une erreur (ce qui est le cas le plus courant : ESTALE, EIO, montage
  démonté proprement) sont couverts par les corrections ci-dessus.
- **Semgrep** : voir plus haut, bloqué par la politique réseau de cet
  environnement de développement — à lancer depuis une machine avec un accès
  réseau normal si une couverture supplémentaire est souhaitée
  (`uv run --group dev semgrep --config=auto src`).
