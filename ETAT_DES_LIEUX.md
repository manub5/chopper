# État des lieux — Choppeur

Date : 29 octobre 2026. Révision examinée : `f45db71`.

## Verdict

**Le projet est un prototype fonctionnel déjà bien structuré, mais pas encore fiable pour un prêt sans accompagnement.** Le parcours d'une piste, de la sélection à l'export, existe et ses cas usuels sont testés. Plusieurs défauts importants restent toutefois en dehors des tests : blocage après une analyse échouée, fermeture insuffisamment sécurisée, résultats d'album non affichés et limites de qualité audio.

**104 tests passent. Cela ne prouve pas que l'analyse musicale réelle ni toute l'application fonctionnent de bout en bout.** Le modèle de rythme et la sortie audio sont simulés dans les tests concernés.

## 1. Périmètre et méthode

- [x] Lecture de tous les fichiers Python du moteur, de l'interface et des tests.
- [x] Lecture des consignes, README, spécification, décisions, historique et feuille de route.
- [x] Examen de `pyproject.toml`, des hooks, du `.gitignore`, de l'installateur et du lanceur généré ; analyse du verrou TOML et de ses versions.
- [x] Exécution de la suite de tests et des contrôles locaux sans correction automatique.
- [x] Reproductions ciblées sur des fichiers synthétiques temporaires et des fenêtres Qt sans affichage.
- [x] Rédaction de ce rapport uniquement, sans correction du projet ni commit.

Les dépendances de `.venv`, les caches d'outils et les objets internes de Git ne sont pas considérés comme du code du projet à auditer intégralement. Le code installé de `beat_this` a néanmoins été consulté pour vérifier son raccordement et le chargement du modèle.

Les commandes Python utilisent l'environnement `.venv` existant, sans installation ni synchronisation. Les écritures temporaires des essais et de pytest sont dirigées sous `/tmp/user/1000/opencode`, les fichiers `.pyc` sont désactivés et les caches Ruff/pytest ne sont pas utilisés. Aucun morceau de la bibliothèque personnelle n'a été utilisé ou modifié.

### Résultats des contrôles

| Contrôle exécuté | Résultat |
|---|---|
| `.venv/bin/python -B -m pytest -q -p no:cacheprovider --basetemp=/tmp/user/1000/opencode/choppeur-audit-pytest` avec Qt `offscreen` | **104 réussis en 20,89 s**, aucun échec ni test ignoré |
| `.venv/bin/ruff check --no-cache src tests` | Aucun problème |
| `.venv/bin/ruff format --check --no-cache src tests` | 34 fichiers déjà formatés |
| `.venv/bin/mypy --cache-dir=/dev/null src tests` | Aucun problème dans 34 fichiers ; avertissement de couverture sur les fonctions sans annotations |
| `.venv/bin/bandit -qc pyproject.toml -r src -ll` | Code de sortie 0, aucun signalement moyen/élevé ; avertissements sur des commentaires `nosec` |
| `bash -n install.sh choppeur` | Syntaxe valide |
| Lecture TOML de `uv.lock` | Valide, 75 entrées de paquets |

Environnement observé : Python 3.12.14, PySide6 6.11.2, librosa 0.11.0, beat-this 1.1.0, torch 2.14.0+cpu, torchaudio 2.11.0+cpu, pytest 9.1.1. Ces versions correspondent aux entrées du verrou sur cette machine. Cela ne valide pas toutes les interactions des bibliothèques lors d'une véritable inférence.

Ni installation complète, ni fabrication de paquet, ni hooks pre-commit complets n'ont été exécutés. Certains hooks reformateraient ou corrigeraient des fichiers, ce qui contredirait la demande. Semgrep et Gitleaks sont disponibles sur cette machine, mais n'ont pas été lancés pendant cet audit.

## 2. Ce qui marche, preuves à l'appui

### Architecture et démarrage

- Séparation respectée : aucun import Qt dans `core/`.
- Modèles de données simples et indépendants de l'interface.
- Création de la fenêtre principale vérifiée sans affichage réel.
- Choix automatiques XCB sous Wayland et portail sous KDE couverts par des tests de configuration, sans écraser un choix explicite de l'utilisateur.

### Bibliothèque

- Navigation dossier par dossier, sans parcours récursif initial de toute la bibliothèque.
- Filtrage des extensions audio, émission des sélections de pistes et de dossiers.
- Dossiers illisibles et liens symboliques cassés couverts par les tests.
- Essai sur 3 000 entrées locales et absence de duplication au deuxième dépliage.

Cela ne démontre pas la fluidité sur un NAS réellement lent : les lectures d'un niveau restent synchrones dans l'interface.

### Audio, noms et export

- Lecture WAV et décodage MP3 via un vrai appel à ffmpeg testés ici ; ffmpeg est présent et le test MP3 n'a pas été ignoré.
- Lecture FLAC avec récupération des tags testée.
- Gestion de fichiers vides, faux fichiers audio, WAV tronqués, silence et repli sur le nom en l'absence de tags.
- Lecture des sources sans modification ; un test compare leur empreinte avant/après chargement.
- Export de segments, conservation de la fréquence fournie, noms automatiques et nettoyage des caractères interdits.
- Noms Unicode, suffixes anti-écrasement et collision entre choix du nom et création du fichier couverts.
- Réservation atomique du nom ; suppression du fichier partiel si son écriture échoue.
- Réglage WAV/FLAC transmis jusqu'à l'écriture ; parcours FLAC de l'interface testé.

### Candidats et cache

- Génération et classement de boucles sur grille régulière synthétique.
- Génération de one-shots sur attaques synthétiques, limite de durée et arrêt au silence/à l'attaque suivante.
- Détection librosa réellement exécutée sur des clics synthétiques.
- Test de performance des candidats sur environ 33 minutes de silence synthétique.
- Cache SQLite persistant, invalidation après modification du fichier et utilisation depuis un autre thread vérifiés.
- Le pipeline réutilise les résultats de rythme mis en cache sans rappeler l'analyseur.

### Interface, préécoute et paramètres

- Affichage de la forme d'onde et de deux marqueurs par candidat testé.
- Sélection/cochage, export des seuls candidats cochés et choix du candidat préécouté testés.
- Appel de préécoute en lecture unique, signalement des erreurs PortAudio et bouton d'arrêt testés avec sortie audio simulée.
- Identité du segment envoyé à la préécoute et du segment exporté vérifiée, à la quantification près.
- Paramètres TOML : valeurs par défaut, fichier partiel et aller-retour sauvegarde/chargement testés sur des données valides.
- Analyse d'album en arrière-plan, progression, poursuite après une piste en erreur et dossier devenu inaccessible couverts.

## 3. Ce qui est cassé ou défectueux

### A. Après l'échec d'une piste, les analyses suivantes restent bloquées — priorité haute

**Reproduit avec une vraie fenêtre et un vrai QThread**, en faisant échouer le calcul simulé.

`TrackAnalysisWorker.run()` émet `failed`, mais pas `finished` en cas d'erreur (`gui/workers.py:77-83`). Or `start_in_thread()` ne raccorde que `finished` à `thread.quit()` (`gui/workers.py:141-149`). L'interface redevient visuellement disponible, mais le thread reste actif.

Résultat constaté : après l'erreur, `thread_still_running=True`, bibliothèque réactivée ; une nouvelle sélection répond « Une analyse est déjà en cours ». Une erreur de décodage ou de téléchargement du modèle peut donc rendre toutes les nouvelles analyses impossibles jusqu'à fermeture.

Le test existant vérifie le signal d'erreur du worker appelé directement, pas la fin du thread sur ce chemin.

### B. La fermeture ferme le cache même si le thread n'a pas terminé — priorité haute

`MainWindow.closeEvent()` attend au maximum 30 secondes, ignore le résultat de `wait()`, puis ferme systématiquement le cache et accepte la fermeture (`gui/main_window.py:285-301`). `quit()` ne constitue pas une interruption du calcul en cours.

**Branche reproduite avec un thread simulé renvoyant `False` à `wait(30000)`** : le cache est fermé alors que le thread est toujours déclaré actif. Risques : accès ultérieur à une base fermée et destruction d'un QThread vivant. Le plantage natif final n'a pas été provoqué pendant l'audit.

Le test existant fait durer le travail 0,1 seconde : il ne couvre pas le dépassement de 30 secondes. La correction relatée dans l'historique atténue donc le problème, sans le résoudre entièrement.

### C. Les fins des boucles ne suivent pas les mesures réelles si le tempo varie

`find_loop_candidates()` utilise la durée médiane des mesures sur tout le morceau, puis calcule `fin = début + durée_médiane × nombre_de_mesures` (`core/candidates.py:76-88`). Il ne prend pas le premier temps réel situé le nombre de mesures demandé plus loin.

**Reproduit** avec les premiers temps `(0, 2, 4.5, 7.5, 11)` : la durée médiane vaut 2,75 s et les fins proposées sont notamment 2,75 et 4,75 s, hors de cette grille. Les boucles commencent sur une mesure, mais leur fin peut tomber au milieu d'une autre.

Les tests actuels ne comportent qu'une grille régulière et ne contrôlent pas ce cas.

### D. Les exports issus de l'interface perdent la stéréo

`_on_track_analyzed()` recharge la piste avec `audio_io.load()` sans `mono=False` (`gui/main_window.py:156`). Ce tableau mono est ensuite fourni à la préécoute et à l'export.

**Reproduit** : WAV source à deux canaux → sélection dans la fenêtre → export à un canal. Le moteur sait conserver les canaux, mais le parcours utilisateur ne le fait pas. Des canaux opposés en phase peuvent même s'annuler au mélange ; le test de chargement confirme cette annulation.

La spécification n'explicite pas le nombre de canaux attendu : c'est une perte d'information certaine, mais son caractère acceptable ou non doit être décidé avec l'utilisateur.

### E. Les erreurs d'export ne sont pas présentées proprement

`_on_export_requested()` appelle l'export sans intercepter ses erreurs (`gui/main_window.py:241-254`). **Reproduit** en simulant un disque plein : `OSError` remonte hors de cette méthode, sans message utilisateur prévu.

Le moteur nettoie le fichier partiel, ce qui est correct. L'interface ne transforme pas l'erreur en retour compréhensible. Si plusieurs candidats sont exportés, ceux déjà écrits avant l'échec restent présents sans bilan d'export partiel.

### F. Les paramètres ne sont pas validés suffisamment

**Reproduit dans la boîte de paramètres :**

- Saisir `abc` dans les longueurs provoque `ValueError` lors de `settings()`.
- `0,-1` est accepté comme longueurs de boucle.
- Une saisie vide est acceptée et supprime toutes les longueurs proposées.

`SettingsDialog` accepte le dialogue avant cette conversion, sans message de validation (`gui/settings_dialog.py:93-103`, `gui/main_window.py:228-232`).

**Reproduit lors du chargement TOML :** fichier mal formé → `TOMLDecodeError` ; clé inconnue → `TypeError` ; nombre de candidats négatif accepté. Aucun repli n'entoure ce chargement à la création de la fenêtre (`core/settings.py:29-50`, `gui/main_window.py:53`). Un fichier de paramètres invalide peut empêcher le démarrage.

### G. Modifier la racine dans « Paramètres » ne rafraîchit pas la bibliothèque

Le nouveau réglage est enregistré, mais `_on_settings_clicked()` ne rappelle pas `library_panel.set_root()` (`gui/main_window.py:228-232`). **Vérifié par interception de cet appel : zéro appel après validation d'une nouvelle racine.** Le panneau reste sur l'ancienne bibliothèque jusqu'à une autre action ou un redémarrage.

## 4. Ce qui est à moitié fait

### Analyse d'album : calcul et cache présents, restitution absente

`AlbumAnalysisWorker` émet `track_done(analysis, candidates)`, mais la fenêtre ne raccorde jamais ce signal (`gui/workers.py:98,136`, `gui/main_window.py:191-198`). Aucun résultat d'album n'est donc envoyé à la forme d'onde ou à la liste.

**Reproduit** avec un album synthétique d'une piste et un calcul simulé réussi : progression à 1, liste de candidats vide. Si une piste était déjà affichée, ses anciens candidats resteraient affichés.

Ce bouton sert actuellement surtout à remplir le cache. Il faut ensuite sélectionner les pistes individuellement pour obtenir leurs candidats à l'écran ; même en cache, le fichier est relu et les candidats sont recalculés. Il n'y a pas de sélection/export global des résultats d'album ni de récapitulatif durable des échecs.

### One-shots : bornes calculées, fondu promis absent

La spécification demande un court fondu (`docs/SPEC.md:27-30`). Ni la préécoute ni l'export n'appliquent de fondu : ils découpent directement le tableau (`gui/candidates_panel.py:115-123`, `core/audio_io.py:129-137`).

**Vérifié** en exportant un one-shot de signal constant à 0,5 : premier et dernier échantillons à 0,5, segment entièrement constant. Le risque de clic à la coupure reste présent ; son audibilité n'a pas été évaluée.

La séparation percussif/harmonique existe et possède un test de dimensions, mais n'est pas utilisée par le pipeline de sélection. Ce n'est pas une séparation de pistes vocales, laquelle reste hors périmètre.

### Paramètres et nommage : plusieurs écarts avec les promesses

- Le format de nom est fixe dans `core/naming.py`. Aucun réglage de modèle de nom, contrairement à `docs/SPEC.md:32-34`.
- « Nombre de candidats par piste » est appliqué séparément aux boucles et aux one-shots : réglage 8 → jusqu'à 16 propositions (`gui/workers.py:46-61`). Aucun plafonnement global.
- Le dossier d'export par défaut n'est utilisé que comme point de départ du sélecteur ; chaque export redemande un dossier (`gui/main_window.py:246-253`). Pas de parcours direct vers la destination enregistrée.
- Modifier les réglages de sélection ne recalcule pas immédiatement la liste déjà affichée.

### Forme d'onde : représentation présente, repères musicaux incomplets

Seuls les débuts/fins des candidats sont dessinés. Les premiers temps de mesure de `Analysis.downbeat_times` ne sont pas transmis à la vue, alors que la spécification prévoit ces marqueurs (`docs/SPEC.md:13-14`).

L'affichage réduit le signal en prenant un échantillon sur plusieurs, pas les minimums/maximums de chaque intervalle : des transitoires peuvent disparaître visuellement. C'est une limite constatée dans l'algorithme, pas un défaut graphique mesuré en session réelle.

### Interface réactive : calcul principal déporté, accès lents encore synchrones

- Lecture des tags d'une piste avant lancement du worker.
- Rechargement complet de la piste dans le thread graphique après analyse, y compris un nouveau décodage ffmpeg pour les formats concernés.
- Parcours d'un niveau de bibliothèque et exports dans le thread graphique.

Ces points sont visibles dans `gui/main_window.py:144,156,251` et `gui/library_panel.py:37-68`. Un fichier long ou un NAS lent peut donc encore figer l'interface. Aucun délai réseau réel n'a été mesuré.

La bibliothèque reste volontairement désactivée pendant l'analyse. Il n'y a ni bouton d'annulation accessible, ni progression détaillée pour une piste, ni suivi du téléchargement initial du modèle.

### Distribution : installateur présent, paquet autonome non livré

`install.sh` et le lanceur existent, avec syntaxe vérifiée. L'installation automatique des paquets système cible les distributions utilisant APT ; ailleurs elle avertit et laisse l'installation manuelle. Un paquet autonome est explicitement reporté dans `docs/DECISIONS.md`.

L'historique rapporte un ancien `uv build` réussi, mais il n'a pas été rejoué ici : aucun artefact distribuable actuel n'a été validé. Le premier calcul nécessite aussi les poids du modèle s'ils ne sont pas déjà en cache.

Le mode GPU automatique est codé, mais les dépendances livrées sont les versions CPU. L'accélération NVIDIA nécessite une intervention distincte, déjà documentée dans les décisions.

## 5. Risques, effets de bord et idempotence

### Sécurité et robustesse

- Pas de secret évident repéré dans les fichiers du projet lus ; absence non certifiée par un scan dédié.
- Requêtes SQLite paramétrées et appels ffmpeg sans interpréteur de commandes : bonnes protections contre les injections courantes.
- L'installateur exécute un script distant via `curl … | sh` ; c'est une dépendance de confiance, pas une preuve de compromission. Il peut installer des paquets avec `sudo` et écrire dans le compte utilisateur.
- `.gitignore` protège `.env`, `build/` et `dist/`, mais n'inclut pas `*.key` et `*.pem`, demandés par les consignes globales. Aucun ajout n'a été fait pendant l'audit.
- Les noms exportés ne sont pas raccourcis : des tags très longs peuvent dépasser la longueur autorisée d'un nom de fichier. Risque issu de la lecture du code, non reproduit ici.
- Cache/configuration inaccessibles ou corrompus : pas de fonctionnement de secours au démarrage.
- Un montage réseau figé au niveau du système peut immobiliser un accès ; cette limite est déjà reconnue dans `docs/HISTORIQUE.md`.

### Effets de bord et répétition des actions

- Le programme lit les sources ; ses écritures normales concernent les exports, les paramètres, le cache SQLite et les poids téléchargés du modèle.
- Réexporter les mêmes candidats **crée volontairement des doublons suffixés** : pas d'écrasement, mais action non idempotente.
- Une erreur au milieu d'un export multiple ne supprime pas les exports précédemment réussis.
- La sauvegarde TOML écrase directement le fichier, sans remplacement atomique ; une interruption peut laisser un fichier incomplet.
- Le cache garde les anciennes empreintes et n'a ni purge ni version d'algorithme : une future évolution du calcul pourrait réutiliser une ancienne analyse sans invalidation adaptée.
- Réexécuter l'installateur peut resynchroniser l'environnement et réécrit le lanceur `./choppeur` ; il n'est pas sans effets de bord.

## 6. Ce qui reste inconnu

Ces éléments ne sont **ni validés ni déclarés cassés** par cet audit :

- Précision de `beat_this` sur trois morceaux réels choisis par l'utilisateur, demandée à l'étape 2. Aucun compte rendu de cette validation n'est présent dans les documents examinés.
- Chargement/téléchargement réel du modèle et inférence complète avec les versions installées. Les tests substituent le tracker ou l'analyse rythmique.
- Pertinence musicale des scores et utilité des meilleurs samples, notamment sur ambient, rythmes irréguliers et enregistrements live.
- Préécoute audible sur le périphérique réel et comportement après changement de sortie audio.
- Rendu sous KDE/Wayland/XWayland, dialogues du portail et accès à un vrai NAS monté.
- Lecture AAC/M4A, OGG et AIFF de bout en bout : extensions prévues, sans test équivalent au MP3 dans cette suite.
- Installation sur une machine vierge, paquet autonome et accélération GPU.

## 7. État par rapport à la feuille de route

| Étape | État observé |
|---|---|
| 1 — Squelette et fenêtre | Réalisé et testé sans affichage réel |
| 2 — Rythme et validation sur 3 morceaux | Intégration présente ; validation réelle non établie |
| 3 — Boucles et WAV nommé | Présent ; calage de fin incorrect à tempo variable |
| 4 — One-shots | Présent ; fondu absent, qualité musicale non validée |
| 5 — Cache SQLite | Présent et testé ; robustesse/versionnement à compléter |
| 6 — Navigation bibliothèque | Présente et testée localement ; accès NAS réel non validé |
| 7 — Forme d'onde et marqueurs | Présents pour les candidats ; premiers temps de mesure absents |
| 8 — Liste, préécoute, export | Parcours nominal testé ; écoute réelle non validée, erreurs d'export mal gérées |
| 9 — Paramètres | Présents ; validation et application immédiate incomplètes |
| 10 — Album en arrière-plan | Calcul/progression/cache présents ; restitution des résultats absente |
| 11 — Distribution | Installateur présent ; paquet autonome reporté, installation vierge non validée |

La feuille de route ne marque pas les validations acquises. Les documents expliquent bien les décisions et les anciens incidents, mais ne doivent pas être pris comme preuve que tous les problèmes décrits sont définitivement éliminés.

## 8. Prochaine étape recommandée

**Sécuriser d'abord la fin d'une analyse échouée**, avec un test couvrant une vraie fenêtre et un vrai thread : c'est un défaut bloquant confirmé, susceptible d'apparaître dès le premier fichier illisible ou problème de téléchargement. Aucune correction n'est incluse dans ce rapport.

Régression vérifiée : les 104 tests existants et les contrôles statiques ci-dessus passent. Cas limites examinés : erreurs de calcul, thread non terminé à la fermeture, disque plein, stéréo, tempo variable, paramètres invalides et album sans restitution ; les situations réelles non exercées sont explicitement listées.
