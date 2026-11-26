# Historique des corrections

Journal des bugs trouvés et corrigés, avec leur cause.
À consulter pour comprendre pourquoi le code est écrit ainsi ; les règles en vigueur sont dans `DECISIONS.md`.
Note : les mentions « cet environnement » / « ce bac à sable » désignent l'environnement d'une IA de développement
sans audio, sans affichage et avec un réseau restreint — pas la machine de l'utilisateur. Depuis, semgrep tourne
dans pre-commit et la préécoute ne joue plus en boucle.

## 26/11/2026 — Ouvrir et ajouter depuis le gestionnaire de fichiers

- L’action contextuelle Dolphin optionnelle annonce ses types audio et les dossiers, et transmet
  un chemin local à Chopper. Un dossier s’ajoute comme album sans analyse ; une
  piste ouverte explicitement garde le même parcours d’analyse.
- Le dépôt ajoute uniquement des références de session, sans doublon, sans
  déplacer les originaux ni remplacer la piste active. Les éléments non locaux
  ou non pris en charge sont signalés. Les associations par défaut ne sont pas modifiées.

## 26/11/2026 — Panneaux redimensionnables et clic neutre sur la forme d’onde

- La bibliothèque se redimensionne en largeur ; la forme d’onde, les rectangles
  et le tableau se partagent la hauteur au moyen de deux séparateurs. En petite
  fenêtre, les panneaux visibles ne peuvent pas être écrasés et les listes
  restent accessibles par défilement. Le zoom et l’alignement temporel sont conservés.
- Si les rectangles sont masqués faute de résultats, déplacer le séparateur restant
  ne leur fait plus perdre la hauteur réglée lorsqu’ils réapparaissent.
- Un clic hors sélection ne demande plus le retour à la piste entière et ne
  modifie ni la sélection ni les résultats ou les marques. Il ne lance pas de
  préécoute. Les glissements et les actions explicites gardent leur comportement.

## 25/11/2026 — Redécoupe automatique de la sélection

- **Chop selection** remplace les résultats manuels sans confirmation. Un changement
  de **Length** relance la recherche sur la sélection courante ; sans sélection,
  il règle seulement la prochaine découpe. Une valeur inchangée ne relance rien.
- Réutilise l’audio et l’analyse en mémoire, sans travail concurrent. En cas
  d’échec, les résultats et marques précédents restent en place. Les autres
  confirmations et les fichiers déjà exportés restent inchangés.

## 25/11/2026 — Export au clic droit dans les deux vues

- **Export** vise la ligne ou le rectangle sous le clic, sans sélectionner ni
  marquer l’échantillon et sans lancer de préécoute. Réutilise le dossier et
  le format d’export existants, avec un nom distinct si un fichier existe déjà.
- Aucun export sur une zone vide, après annulation du menu, si l’échantillon
  a disparu entre-temps ou si une opération bloque l’interface. Les exports
  groupés et le glisser-déposer restent inchangés.
- Tests Qt hors écran : menu réel dans les deux vues, défilement, contenu du
  WAV exporté et conservation du premier fichier lors d’un nouvel export.

## 25/11/2026 — Albums et pistes dans la bibliothèque de session

- **File → Add album…** ajoute les dossiers en bas de la bibliothèque, chemin
  visible et défilement disponible, sans lancer d’analyse. Les ajouts ne sont pas
  enregistrés dans les préférences ; le choix du dossier principal reste distinct.
- **File → Open track…** et `chopper <fichier>` utilisent la même analyse. Une
  piste seule ajoutée après analyse réussie affiche son nom, sans ancien album
  ciblé. La forme d’onde et les échantillons restent limités à une piste chargée.
- Tests : albums homonymes, doublons, dossier déjà présent replacé en bas,
  ouverture différée des enfants, annulation, WAV corrompu et commande CLI.
- Revue finale : une piste ouverte seule reste en un seul exemplaire au premier
  niveau, que son album ait été déplié avant ou après l’ouverture. Cela ne change
  pas le contenu du dossier ni les pistes traitées par l’analyse d’album.

## 25/11/2026 — Plus de place pour la liste des échantillons

- Répartition verticale : moitié de la part de la forme d’onde et deux tiers de
  celle des rectangles ; le tableau récupère l’espace libéré. À 1100 × 1100 hors
  écran, hauteurs avant/après : 524 → 262, 174 → 116 et 175 → 495 px. À petite
  taille les minimums préservent l’accès au tracé, aux rectangles et au tableau.
- Toutes les colonnes sont redimensionnables et le tableau défile en largeur.
  La limite du réglage passe à 64 échantillons par catégorie, défaut inchangé à
  8 ; un ancien fichier indiquant une valeur valide est lu sans réécriture.
- Vérifications : 181 tests ciblés et 811 sur la suite complète ; comparaison
  Qt hors écran et inspection à taille normale et réduite. Fichiers audio et
  configuration utilisateur non modifiés.

## 23/11/2026 — Étape 3 : thème sombre inspiré de Material Design 3

- Palette anthracite, accent ambre, champs et boutons arrondis, marges internes
  régulières et contour de focus. Police, agencement, PySide6 et pyqtgraph conservés.
- Qt ne transmettait plus correctement la palette avec une feuille appliquée à
  toute la fenêtre. Style limité aux contrôles, palette explicite en mode sombre,
  retour au clair sans résidu. La revue a aussi révélé une liste déroulante sur fond
  clair et une palette sombre persistante dans les paramètres ouverts ; les deux
  cas ont été reproduits par test, puis corrigés.
- Capture Qt hors écran sur données synthétiques, contraste du tracé et des listes,
  édition des champs, bascule clair/sombre, zoom et état de lecture vérifiés.
  Pas de test audio matériel. Flèches des champs numériques peu contrastées sous
  Fusion dans la capture ; zones de clic et clavier restent fonctionnels.
- Aucun changement de réglage enregistré, dépendance, installation, moteur, audio
  source ou palette globale. Aucun besoin de réinstaller pour ce seul changement.

## 23/11/2026 — Étape 1 : ouvrir et analyser un fichier depuis la commande

- `chopper /chemin/absolu/fichier.wav` ouvre la fenêtre puis passe la piste au
  même parcours que la sélection bibliothèque : analyse en arrière-plan,
  indication « Analyzing… », état occupé habituel, puis forme d'onde/candidats.
  Sans fichier, aucun chargement automatique ajouté. Qt consomme ses options avant
  l'argument facultatif ; ouverture différée à la boucle d'événements après show.
- Point d'entrée public `MainWindow.open_file` : vérifier fichier régulier et
  accès en lecture avant de déléguer. Absence/dossier/permission refusée annoncés
  dans la fenêtre, pas de thread démarré ; audio corrompu traité par l'erreur du
  worker existant, interface réactivée. Aucun traitement d'analyse dupliqué.
- Contrat externe ajouté mot pour mot dans AGENTS.md, notamment pour le séparateur
  de stems ; usage avec chemin absolu et espaces documenté dans README.
- Rouge : 7 nouveaux cas échouaient/71 existants réussissaient. Vert : 78 tests
  ciblés et 807 tests complets réussis ; Ruff lint/format, mypy, Bandit et diff
  passent. Bandit affiche ses seuls avertissements historiques de commentaires.
  Revue indépendante ciblée : aucune anomalie concrète identifiée.
- Régressions vérifiées : démarrage inchangé, options Qt réelles en sous-processus,
  fenêtre visible avant analyse, message/état occupé puis WAV et waveform réels.
  Cas limites : espaces/Unicode/caractère dollar, absent, dossier, PermissionError,
  audio corrompu. Seule l'inférence rythmique coûteuse est simulée dans le test
  d'ouverture ; autres étapes et thread réels. Audio source identique avant/après.
- Effets conservés : cache et éventuel téléchargement initial du modèle comme une
  sélection bibliothèque ; chaque invocation ouvre sa fenêtre, pas de commande
  distante vers une fenêtre existante. Rien n'importe Qt dans core. Aucun changement
  du thème/installateur/dépendances, aucune installation réelle ni modification du
  dossier habituel ou de son hook Semgrep. Étapes 2/3 en attente de validation.

## 18/11/2026 — Revue finale de l'extension Kubuntu : concurrence

- Revue indépendante unique de `3c02cf3..69692d7` : deux anomalies importantes
  reproduites avant correction. Un remplacement entre contrôle et opération
  destructive pouvait être écrasé/supprimé ; un désinstallateur pouvait s'intercaler
  entre deux intégrations d'une même installation et produire un faux succès.
- Capture privée de l'objet réel avant toute suppression/mise à jour/retrait de
  relevé ; vérification après déplacement, suppression seulement dans cet espace
  privé. Publication et restauration sans écrasement via primitives exclusives,
  `renameat2(RENAME_NOREPLACE)` Linux documenté officiellement. Pas de fallback
  destructeur sur système de fichiers non compatible. Si restauration impossible,
  objet/sauvegarde conservé et chemin de récupération affiché, pas d'effacement
  récursif. Étendre le traitement au rollback et à la sauvegarde du relevé.
- Un verrou couvre désormais toute la phase de mutation des quatre intégrations,
  avec helpers internes sans reprise du verrou. Test d'un véritable second processus
  de désinstallation entre commande globale et Bureau : rejet, résultat cohérent.
- Tests rouges puis verts : remplacement à l'opération de mise à jour et de retrait,
  entrelacement install/uninstall ; cas complémentaire de conflit de restauration
  préserve le fichier étranger ET la sauvegarde originale. Une seule passe de
  correctifs, pas de deuxième revue déléguée.
- Vérification : 159 tests ciblés et 800 complets réussis ; Ruff lint/format, mypy,
  Bandit (avertissements historiques), syntaxe Bash et diff verts. Régressions :
  installateur, vrais consommateurs Desktop Entry, retrait, Git local et suite
  audio/interface. Limites : concurrence ordonnée au dernier instant, disque plein,
  conflits de reprise et processus concurrent, aucune intégration du compte réel.
- Mineur différé : diagnostic PATH inutile si `~/.local/bin` est lui-même un lien
  symbolique ; commande fonctionnelle, pas de fichier/profil modifié. Recette KDE,
  matériel audio, NAS représentatif et ZIP final non exécutés ni présumés validés.

## 18/11/2026 — Extension Kubuntu, étape 6 : retrait conservateur et archive préparée

- `bash uninstall.sh` utilise Python standard, sans dépendre de `.venv`, Qt ou
  PyTorch. Lit uniquement le relevé du projet explicite, affiche les artefacts
  encore prouvés et demande confirmation, défaut non/EOF. Aucun retrait sans accord.
- Retirer seulement les intégrations enregistrées encore conformes ; conserver et
  signaler les fichiers/liens modifiés ou recréés, même à contenu/cible identique.
  Revérifier après consentement. Relevé corrompu/symbolique/copié d'un autre projet
  refusé. Utiliser le Bureau enregistré, pas un nouvel emplacement XDG contenant
  un fichier étranger. Verrou de projet partagé avec l'installateur.
- Relevé actualisé pour les seuls retraits réussis/absences constatées après accord,
  conservé en cas de conflit. Retour non nul si retrait incomplet ou sauvegarde
  impossible ; une reprise gère les fichiers déjà absents. Relevé supprimé seulement
  lorsqu'il ne reste aucun artefact. Répétition après réussite sans effet.
- Projet, lanceur local, `.venv`, profils, uv/paquets système, paramètres, cache,
  sources audio et exports conservés ; aucun dossier parent retiré ni effacement
  récursif. Refus/EOF = aucune écriture. Aucun élargissement de permission implicite.
- Liste blanche d'archive étendue exactement à `uninstall.sh`, helper d'intégrations
  et `assets/chopper.svg`. Relevé local et autres assets exclus, même suivis par Git.
  Aucun ZIP de livraison créé à ce stade : génération soumise à accord séparé.
- Vrai dépôt/remote bare locaux, commit de code seul et `git pull --ff-only` :
  sondes commande/menu/Bureau observent la nouvelle version sans réinstaller ; mêmes
  liens/lanceur/raccourcis/relevé, aucun appel uv au lancement. Aucun serveur réseau.
- Rouge observé : 15 échecs nouveaux/107 réussites ; puis 125 ciblés et 796 tests
  complets réussis. Ruff lint/format, mypy, Bandit (avertissements historiques),
  syntaxe Bash et diff passent. Régressions : suite installateur/audio/interface ;
  limites : refus/EOF, liens cassés/recréés, relevé étranger, PermissionError,
  remplacement durant confirmation et sauvegarde impossible avec reprise.
- Documentation anglaise mise à jour, références officielles PATH/XDG/KDE incluses.
  Tests isolés sans installation réelle dans HOME ni modification audio/profils.
  Revue indépendante finale à effectuer après ce commit ; recette réelle KDE et
  archive restent des validations séparées, pas un résultat déduit des tests.

## 18/11/2026 — Extension Kubuntu, étape 5 : SVG et raccourci Bureau consentis

- Icône SVG statique anthracite/orange doux, sans scripts ni ressources externes.
  Rendu Qt vérifié à 16, 32 et 64 pixels. Champ Icon absolu et échappé selon les
  chaînes Desktop Entry, identique dans le menu et sa copie sur le Bureau ; refus
  de l'icône = pictogramme audio générique. Aucun changement du thème applicatif.
- Quatre confirmations distinctes, chemins et relevé annoncés avant écriture :
  menu, commande globale, icône, Bureau. Recueillir les choix puis installer le SVG
  avant les raccourcis. Bureau obtenu par `xdg-user-dir DESKTOP` sans shell : outil
  absent/en erreur, réponse vide/relative/HOME ou dossier absent = message clair,
  aucune copie ailleurs ni création de Bureau. Copie exécutable 0755 pour KDE,
  sans métadonnée de confiance GNOME inventée. Politiques administratives KDE
  éventuelles et vraie recette graphique restent à vérifier sur machine cible.
- Rôles `icon` et `desktop` dans le relevé strict ; fichiers identiques étrangers,
  liens et dossiers refusés. Réinstallation identique sans remplacement ni doublon.
  Mise à jour réservée aux fichiers encore identifiables, ancien menu générique
  adoptable uniquement par contenu historique exact vers le même lanceur.
- Échec de relevé : retirer seulement un nouveau fichier encore prouvé. Pour une
  mise à jour, sauvegarde privée préallouée avant mutation puis restauration par
  renommage, sans allocation supplémentaire si disque plein. Rouge observé sur
  ce dernier cas avant correction. L'identité restaurée est réenregistrée ; si
  le disque refuse encore le relevé, erreur explicite et refus prudent des futures
  mutations. Pas de suppression automatique de fichier devenu étranger.
- Vérification : 21 nouveaux échecs/77 réussites historiques observés au rouge,
  puis 108 tests ciblés réussis et 778 tests complets. Vrais `gio launch` et
  `desktop-file-validate` exécutés sur des sondes, chemins spéciaux et icône dédiée.
  Ruff, mypy, Bandit, syntaxe Bash et diff propres (avertissements Bandit historiques).
  Régressions : installateur/dépendances/lanceur et suite audio/interface existante.
  Limites : refus/EOF, XDG invalide, collisions, fichier recréé, disque plein.
- Effets : intégrations acceptées indépendantes, les premières peuvent rester si
  une suivante échoue ; dossiers parents consentis non retirés récursivement.
  Tests isolés, aucun audio source ni profil modifié, aucun lancement de Chopper
  réel, aucune intégration dans le compte utilisateur. Aucun ZIP reconstruit ni
  push ; désinstallation/liste blanche d'archive/revue finale restent à l'étape 6.

## 18/11/2026 — Extension Kubuntu, étape 4 : commande globale consentie

- Plan d'extension validé ; première étape seulement. Le lanceur résout ses liens
  symboliques via readlink avant de localiser le projet et `.venv`. Proposer
  `~/.local/bin/chopper` comme lien vers ce lanceur, jamais comme copie ; lancer
  depuis un autre dossier et traverser une chaîne de liens reste sans appel uv,
  avec les arguments spéciaux intacts.
- Consentement du menu conservé en premier, puis proposition de commande globale,
  défaut non/EOF. Destinations et `.chopper-install.json` annoncés avant écriture.
  Relevé privé local au projet, ignoré par Git : schéma, projet, rôle, type, cible
  ou SHA-256, parent résolu, permissions et identité inode/device/ctime. Fichiers
  étrangers, liens cassés ou recréés à cible identique refusés ; réinstallation
  inchangée sans remplacement du lien/relevé.
- Capturer le PATH avant tout ajout interne pour uv. Avertissement et instructions
  de reconnexion/export temporaire si `.local/bin` manque ; signaler une commande
  homonyme prioritaire. Aucun profil modifié. Référence officielle Ubuntu Resolute
  ajoutée au guide, sans promettre le PATH de toutes les sessions personnalisées.
- Ancien menu adopté uniquement si contenu historique exact, même lanceur et
  permissions attendues, pas sur marqueur seul. Échec de sauvegarde du relevé :
  retirer seulement le nouvel artefact encore prouvé, préserver une entrée
  préexistante et toute destination étrangère apparue entre-temps. Les dossiers
  parents créés après accord peuvent rester après échec ; aucun retrait récursif.
- Rouge observé : 22 échecs nouveaux/24 réussites historiques. Cas complémentaires
  rouges puis verts : mise à jour d'atime lors d'une simple lecture, échec de
  relevé après création du menu. Comparaison d'identité hors atime ; rollback
  réservé aux artefacts de l'invocation, sans toucher l'ancien menu.
- Trois cas de concurrence rouges puis verts : remplacer le lien ou le menu au
  moment de sa publication ne doit ni enregistrer ni retirer l'objet étranger ;
  deux installations du même projet ne doivent pas se marcher dessus. Publication
  exclusive avec identité vérifiée sur l'objet détenu ouvert, verrou de répertoire
  Linux non bloquant sans fichier de verrou supplémentaire. Échec annoncé, pas de
  faux succès, aucun remplacement étranger supprimé pendant le rollback.
- Vérification : 747 tests complets, 77 ciblés installateur/intégrations/Desktop
  Entry, Bash -n, Ruff lint/format, mypy et Bandit réussis. Régressions : uv/sudo/
  dépendances/menus et tous les parcours audio existants ; limites : refus/EOF,
  collisions, relevé invalide ou concurrent, liens spéciaux et PATH initial.
- Aucun changement du moteur ni données audio ; pas d'installation réelle dans
  HOME, pas de profil ni fichiers étrangers modifiés pendant les tests. Liens et
  relevés répétables sans doublons. Bureau/SVG/uninstall et liste blanche ZIP
  restent les étapes 5/6 : ne pas livrer une archive intermédiaire de cette étape.
  Aucun push, ZIP reconstruit ni modification du dossier habituel.

## 18/11/2026 — Revue finale de la sélection manuelle : poignées et seuil de clic

- Revue indépendante unique de toute la plage du plan, du moteur à l'interface :
  deux anomalies importantes reproduites sur les gestes natifs, aucun problème
  critique signalé. Rapport et arbitrages : `docs/REVUE_SELECTION_MANUELLE.md`.
- Croiser une poignée réaffectait les valeurs triées aux lignes physiques et
  déplaçait la borne opposée jusqu'à faire disparaître la région. Conserver
  l'identité de la ligne déplacée et la coordonnée brute de la borne fixe pendant
  le geste, puis appliquer l'aimantation sans redistribuer les poignées.
- pyqtgraph déplace parfois les poignées/l'intérieur avant le seuil de glisser Qt.
  Un petit mouvement changeait donc le rectangle visible sans modifier les bornes
  de l'état. Restaurer le rectangle canonique au relâchement traité comme clic,
  silencieusement et sans préécoute supplémentaire.
- Sept tests rouges observés (croisement gauche/droite avec/sans Alt, petits
  mouvements des deux poignées et du corps), puis verts. Suite complète : 719
  réussites ; 171 sous Wayland à 150 %, Ruff/mypy/Bandit verts. Les limites et
  régressions des gestes, lecture, exports et réglages restent couvertes.
- Point mineur différé : sans résultat exportable, le texte de confirmation
  d'album annonce le retrait de la sélection, alors que ce traitement cache-only
  la conserve volontairement. Aucun risque de perte de résultat, mais texte à
  clarifier. Aucun push/ZIP, source audio ni export existant modifié par ce correctif.

## 18/11/2026 — Sélection manuelle, étape 5 : parcours complet et protections

- Barre Length ¼/½/1/2/4 (1 par défaut, session seulement), Chop selection/C et
  Whole track partagés entre boutons et registre ; F1 et infobulles dérivés des
  actions. Esc arrête puis demande la sortie, hors saisie et dialogue ; pas de
  raccourci concurrent ni d'autorépétition. Navigation milieu/Maj+molette inchangée.
- Contrôleur transactionnel : décision sûre Cancel, confirmation également avant
  remplacement/transition, export de tous les résultats manuels indépendamment des
  marques. Annulation ou export partiel/échoué conserve région/résultats/marques ;
  les fichiers déjà réussis restent présents et sont signalés. Les nouveaux calculs
  ne retirent les anciens résultats qu'après réception d'un résultat valide.
- Worker réel raccordé en mémoire, requêtes monotones vérifiées par ID, audio,
  Analysis, fréquence, fenêtre et longueur ; retour Whole track sans détecteur ni
  rechargement, pas de remise à zéro du zoom/tracé. Modifications bloquées pendant
  calcul ; workers conservés jusqu'à thread.finished. Une fermeture dont wait
  échoue reste ignorée, cache et références vivants. Un résultat reçu pendant une
  confirmation de fermeture annulée est différé, puis appliqué sans bloquer l'UI.
- Lecture du passage via le lecteur existant et un candidat éphémère jamais ajouté
  aux résultats/exports. Rectangle synchronisé seulement depuis le contrôleur,
  pas depuis les fins de lecture. Régler Length ou le passage conserve les anciens
  extraits avec avertissement et bornes d'origine ; exports réels 2/4 vérifiés.
- Un geste aimanté effondré invalide le passage sans effacer les résultats manuels :
  Chop est désactivé, Whole track/Esc restent disponibles et gardés. Signal dédié
  ajouté après un test rouge montrant une région cachée mais une ancienne cible C.
- Tests rouges supplémentaires : clics de couloirs encore permis pendant calcul,
  rappel QAction après destruction de la fenêtre, et erreur worker traitée dans
  le mauvais thread via lambda. Correction par widgets désactivés, QTimer enfant,
  slot QObject principal et ID de requête lu sur le worker émetteur. Aucun accès
  QWidget depuis le nouveau worker ; documentation officielle Qt vérifiée.
- 712 tests complets et 164 d'intégration/gestes/actions/couloirs sous Wayland à
  150 % réussis ; Ruff lint/format, mypy et Bandit verts. Cas limites : sélection
  courte/vide, événements anciens/modalité, export annulé/partiel ou paramètres
  non sauvegardables, fermeture réentrante et wait échoué. Revue indépendante
  finale et vérifications après correctifs décrites ci-dessus.
- `src/choppeur/` absent dans cet espace : aucun nettoyage nécessaire. Aucun audio
  utilisateur modifié, aucun ancien export supprimé ; recherche sans écriture et
  mises à jour UI silencieuses. Exports répétés volontairement non idempotents,
  noms distincts sans écrasement. Aucun push, ZIP ou essai audio/DAW réel implicite.

## 17/11/2026 — Sélection manuelle, étape 4 : recherche en mémoire identifiée

- `search_candidates` réutilise exclusivement l'audio et l'Analysis du LoadedTrack.
  En sélection, une seule longueur manuelle valide ; en Whole track, uniquement
  les longueurs automatiques des Settings. Quota par catégorie et durée maximale
  des one-shots conservés, tuple final classé par score avec temps absolus piste.
- Résultat figé `CandidateSearchResult` portant identifiant de requête, piste,
  fenêtre, longueur et message. `CandidateSearchWorker` copie les Settings à sa
  construction, remplace uniquement les candidats du LoadedTrack ; audio/Analysis
  et fréquence restent identiques, sans nouvelle analyse, décodage ni accès cache.
- Messages anglais distincts : sélection trop courte pour la longueur demandée,
  grille rythmique inutilisable, aucun résultat, nombre de one-shots effectivement
  trouvés. Une grille absente n'est pas présentée comme une sélection trop courte.
  Erreurs transmises par failed ; QThread quitte sur succès comme sur erreur.
- Tests rouges observés : 22 échecs de contrats absents, 66 réussites historiques.
  Après implémentation, un test Wayland a révélé un SIGSEGV intermittent avec la
  destruction native supplémentaire du worker. Retour à la propriété Python déjà
  utilisée par les analyses : garder worker/thread jusqu'au vrai thread.finished,
  pas seulement jusqu'au résultat. 192 cycles succès/erreur supplémentaires passent
  ensuite sous Wayland ; cause interne exacte de PySide6/Qt non établie.
- Vérification finale : 665 tests complets et 110 ciblés sous Wayland à 150 % ;
  Ruff lint/format, mypy et Bandit passent. Cas limites : requête incohérente,
  absence de grille/attaques, sélection courte, résultat vide, Settings modifiés
  après construction, fin de thread en réussite/erreur répétée. Tests de barrières
  faisant échouer tout accès détecteur/fichier/cache et tableaux audio en lecture
  seule ; analyses de piste/album historiques toujours couvertes.
- Recherche déterministe sans écriture source/audio, paramètres, cache ou exports ;
  aucun effet persistant supplémentaire en cas de répétition. Aucun nouveau QWidget
  consulté par le worker. Raccordement MainWindow et rejet des résultats obsolètes
  prévus en tâche 5, pas encore livrés. Aucun push ni ZIP reconstruit.

## 17/11/2026 — Sélection manuelle, étape 3 : cible et identité de préécoute communes

- SampleState gère une cible de sample ou de passage, avec un compteur de jetons
  commun et croissant. Les fins/démarrages/erreurs d'anciennes lectures ne peuvent
  plus modifier une préécoute de l'autre type. `has_playback` inclut les demandes
  en attente ; `playing_window` décrit le passage effectivement démarré.
- Un geste de passage validé demande une seule lecture selon Auto-preview ; la
  lecture explicite reste disponible si Auto-preview est désactivé. Un clic ou
  une navigation vers un sample rétablit cette cible, même si son ID était déjà
  actif avant le passage ; Ctrl+clic ne change que les marques. Le double clic
  sur le même sample garde l'arrêt existant.
- `replace_candidates` remplace seulement les candidats via dataclasses.replace,
  conserve audio et Analysis par identité et la fréquence d'origine, attribue de
  nouveaux IDs, retire actif/marques périmés et arrête une lecture active ou en
  attente une seule fois. Aucun démarrage automatique des nouveaux résultats.
  La cible passage reste disponible tant que la région n'est pas retirée ;
  `clear_range` retire cette cible, sans interrompre un sample déjà ciblé.
- Les fenêtres de passage invalides sont refusées avant de couper la lecture ou
  de changer la cible ; absence de piste chargée = aucune demande. Effacer ou
  recharger retire la cible manuelle, sans recycler les jetons ni les IDs.
- Rouge observé : 34 nouveaux échecs, 44 tests historiques réussis. Vert : 78 tests
  ciblés et 621 complets ; Ruff lint/format, mypy et Bandit passent. Régressions :
  clics/navigation/marques, arrêt synchrone, préécoute stéréo et contrôles du lecteur.
  Cas limites : demande en attente, ancien retour started/finished/failed, liste
  vide, absence de piste, fenêtre inversée/hors piste/NaN/infini/booléen/mal formée.
- Aucun nouveau flux ni type de sample persisté, aucune écriture audio/source,
  paramètre, cache ou export. Stop/clear_range répétés sont sans nouvel effet ;
  une nouvelle sélection physique relance volontairement la préécoute autorisée.
  Le raccordement au lecteur et à MainWindow reste prévu en tâche 5 ; cette étape
  ne constitue pas une validation d'écoute réelle. Aucun push/ZIP.

## 17/11/2026 — Sélection manuelle, étape 2 : rectangle et navigation

- Région manuelle ajustable, distincte du surlignage passif de lecture ; glisser
  gauche sur le fond pour dessiner, bords et intérieur pour ajuster. Aimantation
  aux downbeats valides, Alt pour le mouvement libre, bornage à la piste ; aucune
  mesure inventée quand les deux bords aboutissent au même repère.
- Milieu et Maj+molette déplacent horizontalement, molette seule zoome ; même
  navigation dans les couloirs, sans pan gauche ni zoom droit sur la forme d'onde.
  Clic/Ctrl+clic des samples, bornes, alignement et axe y restent testés.
- Fin physique du geste suivie indépendamment des signaux pyqtgraph (setRegion
  émet aussi un signal de fin) : une seule notification par glisser valide, aucune
  au setter ou clic intérieur. Le clic extérieur demande seulement l'effacement,
  sans retirer la région avant décision du futur contrôleur. Modificateurs Alt
  lus jusqu'au relâchement ; changement de piste/clear/disable/hide annule la fin
  différée. Aucun raccourci Échap concurrent installé.
- Recette des gestes : `docs/TEST_MANUAL_SELECTION.md`. Tests Qt réels sur le
  viewport, avec bouton tenu ; 587 tests complets et 55 ciblés sous Wayland à 150 %. Ruff,
  mypy et Bandit passent (avertissements historiques uniquement).
- Lecture et confirmations non raccordées à cette étape : intégration prévue en
  tâche 5. Aucun audio source, export, préférence ni cache modifié ; mises à jour
  programmatiques silencieuses et répétables. Aucun push ni ZIP reconstruit.

## 13/11/2026 — Sélection manuelle, étape 1 : moteur borné et longueurs 2/4

- Plan validé ; première étape uniquement, gestes et boutons manuels encore à
  implémenter. Ajouter `window=(start,end)` optionnel aux deux recherches core,
  sans Qt ni accès au fichier source, en gardant les temps absolus de la piste.
- Valider forme, nombres finis/non booléens, ordre et bornes dans l'audio. Limiter
  les départs et fins avant classement/quota ; RMS/crête de référence et blocs
  de silence/coupure bornés au passage. Ignorer les candidats sans échantillon
  après conversion temps/index ; une boucle ne se raccourcit pas pour tenir.
- Garder les downbeats globaux comme métadonnées de mesure, même pour une petite
  région ; trop court pour la boucle demandée donne zéro boucle, sans bloquer
  la recherche indépendante de one-shots. Le message GUI viendra avec le worker.
- `LOOP_LENGTHS_BARS` et validation des candidats acceptent 2 et 4 mesures ;
  `AUTO_LOOP_LENGTHS_BARS` garde les trois valeurs courtes pour le défaut moteur,
  les Settings et la migration version 3. Une longueur 2/4 exige une fenêtre
  explicite dans le moteur ; aucun ajout de cases ou réactivation de préférences.
- Nommage existant étendu via la validation partagée, sans réécrire son format ;
  liste, libellés et couloirs affichent 2/4 mesures, groupes vides toujours cachés.
  Les anciennes assertions de rejet 2/4 en affichage/export sont remplacées par
  des tests positifs ; rejets 3/8/None/booléens conservés ou renforcés.
- Tests rouges observés puis verts : 548 tests complets, 206 ciblés moteur/
  paramètres/affichage/export et 39 sous Wayland à 150 %. Cas limites : fenêtre
  invalide/infime, score local malgré données non finies hors zone, fin exacte,
  bloc de silence partiel et lissage remontant avant la fenêtre. Compatibilité
  des scores/défauts et scans de silence sans fenêtre explicitement vérifiée.
- WAV et FLAC réels sur données synthétiques : stéréo/fréquence et extraits exacts
  conservés, source inchangée. Aucun audio utilisateur, préférence, cache ou export
  existant modifié. Recherche sans effet de bord ; exports/glissers répétés restent
  volontairement à noms distincts. Aucun ZIP reconstruit ni push à cette étape.

## 13/11/2026 — Revue finale : sélection du projet uv verrouillée

- La revue indépendante a trouvé un défaut important : une variable héritée
  `UV_PROJECT` pouvait sélectionner un autre projet malgré le `cd` et la cible
  `.venv` locale. Avec un ancien exécutable Chopper présent, l'installation pouvait
  annoncer un succès sans vérifier le verrou de Chopper.
- Reproduit en test avec le vrai uv hors ligne, un autre projet vide valide et
  un verrou Chopper invalide : faux succès observé avant correction. L'option
  CLI absolue `--project` impose désormais le projet en plus de l'environnement.
  Le même test exige maintenant l'échec sur le vrai verrou Chopper invalide.
- 486 tests complets réussis après correction ; contrôles statiques verts.
  Revue : aucune anomalie critique ni mineure, une importante corrigée et testée.
  Le ZIP initial de 38 fichiers a passé somme/CRC/contenu et licence/verrou exacts,
  installation réelle depuis le cache hors ligne dans une extraction temporaire
  et démarrage Qt sans affichage. Aucun sudo ni raccourci du compte réel utilisés.
- Aucun changement audio, export, préécoute ou poignée. La variable d'environnement
  n'est pas modifiée dans le compte ; seul cet appel d'installation est borné.
  Nouvelle archive à construire depuis le commit corrigé, sans supprimer l'ancienne.

## 13/11/2026 — Archive de prêt Linux traçable

- Étape 2 validée, étape 3 autorisée. Ajout de `scripts/build_release.py` pour
  livrer sources/installateur/guides dans un ZIP versionné avec SHA court dans
  le nom, SHA complet dans `RELEASE.txt` et somme SHA-256 séparée.
- Lire uniquement les blobs Git d'un commit propre, avec liste blanche ; exclure
  fichiers non suivis, historique Git, environnements, caches, paramètres et audio.
  Refuser liens suivis et données inattendues dans les sources, version dangereuse,
  fichier requis absent, `dist` redirigé par lien et sorties étrangères.
- Dates et ordre stables, modes conservés ; reconstruction identique sans réécrire
  les sorties existantes. Précontrôler archive et somme avant publication ; sur
  erreur, retirer uniquement les liens partiels créés par cet appel et nettoyer
  ses temporaires, sans toucher aux fichiers étrangers.
- 29 tests de construction rouges puis verts, sur dépôts Git temporaires sans
  réseau ni hooks utilisateur. Cas limites : index
  sale, source supprimée, version avec séparateurs/contrôles, liens et collisions,
  checksum incompatible, échec partiel, reconstruction et lancement depuis un
  autre dossier. Aucun changement moteur/audio ni nettoyage d'exports.
- Le hook de commit a révélé l'héritage de `GIT_INDEX_FILE` : le constructeur
  consultait l'index du dépôt appelant au lieu de celui demandé. Trois nouveaux
  tests rouges (`GIT_INDEX_FILE`, `GIT_DIR`, `GIT_WORK_TREE`) puis isolation des
  variables Git pour lire uniquement le dépôt explicite. Aucun hook contourné.
- Guide de vérification de somme et recette Kubuntu explicites : intégrité du ZIP
  ne prouve ni confiance dans son expéditeur, ni compatibilité matérielle.
  Vérification du livrable réel et revue finale consignées après construction.

## 08/11/2026 — Raccourci KDE créé uniquement après accord

- Étape 1 validée par l'utilisateur, étape 2 autorisée. Après installation locale
  réussie, proposer l'entrée `applications/chopper.desktop` sous le dossier XDG
  choisi (ou `.local/share` du compte) et afficher son chemin complet avant accord.
  Refus, réponse vide et EOF : aucun dossier de raccourci créé, lanceur local
  utilisable. Dossier XDG relatif refusé ; aucune élévation de privilèges.
- Helper Python standard `scripts/install_desktop.py`, sans Qt ni dépendance
  supplémentaire. Écriture temporaire puis publication ; conserver l'ancien
  raccourci si le remplacement échoue. Ne remplacer que les fichiers réguliers
  avec marqueur Chopper et identité attendue, jamais les liens même cassés.
- Échappement Desktop Entry distinct du shell. Un test réel GLib a révélé sa
  vérification d'existence du programme avant expansion de `%%` : le raccourci
  utilise `env --` pour transmettre le chemin comme argument, sans `sh -c` ni
  évaluation shell. Source GLib consultée, reproduction réduite puis test vert.
  Chemins avec `=` ou contrôles refusés explicitement.
- Régression : 456 tests réussis, dont 48 tests installateur/raccourci. Validation
  réelle par `desktop-file-validate` et lancement de sondes sans interface via
  `gio launch` : espaces, apostrophe, dollar, pourcentage, guillemet, backslash,
  accent et backtick. Refus/EOF, XDG, fichier étranger, liens cassés, réinstallation,
  erreur d'écriture et propagation de l'erreur dans Bash également couverts.
- Aucun raccourci installé dans le compte réel pendant les tests ; écritures
  uniquement dans les bacs à sable. Effet prévu chez le destinataire : un fichier
  de menu, après accord ; réinstallation actualise seulement cette entrée générée.
  Aucun changement moteur/audio/source/export/préférences/cache ; aucune copie
  de samples supplémentaire. Compatibilité réelle KDE/Kubuntu toujours à valider.
- Guide utilisateur `docs/INSTALL_KUBUNTU.md` ajouté : dossier permanent, reprise,
  nouvelle extraction après déplacement, retrait manuel prudent et recette cible.
  Archive finale, revue indépendante et publication restent des étapes séparées.

## 08/11/2026 — Installation verrouillée et lancement sans synchronisation

- Première étape du plan de distribution Kubuntu 26.04.1, dans un espace Git
  isolé ; aucune publication ni installation système réelle pendant ces travaux.
- `install.sh` contrôle les collisions de lanceur avant toute installation,
  demande confirmation avant uv et sudo/apt, et refuse par défaut ou sur EOF.
  L'installateur officiel uv est téléchargé dans un fichier temporaire nettoyé :
  un téléchargement en échec n'exécute plus son éventuel contenu partiel.
- uv installé, si nécessaire et accepté, sous `.local/bin` du compte, sans
  modification des profils shell. Synchronisation `--locked --no-dev --inexact` :
  verrou conservé, pas d'outils de développement ajoutés sur installation fraîche,
  paquets supplémentaires existants non supprimés. L'environnement est fixé au
  `.venv` du dossier choisi pour ignorer un `UV_PROJECT_ENVIRONMENT` hérité qui
  pourrait sinon cibler un environnement extérieur, voire le système.
- `./chopper` exécute directement `.venv/bin/chopper` : plus de synchronisation,
  résolution ou téléchargement de dépendances au lancement. Un environnement
  manquant ou incomplet produit une erreur explicite, sans faux succès.
- Régression : 428 tests réussis, dont 20 tests isolés de l'installateur ; cas
  limites : chemin avec espaces/apostrophe/dollar/pourcentage, arguments préservés,
  refus/EOF, erreur de téléchargement, apt et sync, réinstallation, liens cassés,
  dossier ou fichier étranger, environnement manquant et redirection héritée.
- Effets de bord annoncés : `.venv`, lanceur généré, téléchargements uv/Python et
  cache, éventuels paquets système après accord ; réinstallation du lanceur propre
  autorisée, fichiers étrangers et ancien alias préservés. Sources audio, exports,
  préférences et caches applicatifs inchangés ; glissers non idempotents inchangés.
  Les téléchargements du modèle à la première analyse restent possibles.
- Kubuntu 26.04.1 non déclaré compatible à ce stade : essai réel encore attendu.

## 07/11/2026 — Rétablit l'alternance du tri des samples

- Bug reproduit sur les quatre colonnes triables par vrais clics d'en-tête :
  l'ordre restait identique après le premier clic. QHeaderView avait déjà changé
  son indicateur avant `sectionClicked`, et le handler inversait ce nouvel ordre
  une seconde fois, annulant à chaque fois l'alternance attendue.
- Utiliser `sortIndicatorChanged(column, order)` comme source unique de l'ordre,
  sans seconde inversion. Indicateur initial sans colonne ; aucune activation
  du tri automatique pendant le remplissage de lignes, aucune modification audio.
- Quatre tests rouges puis verts : quatre clics alternent les ordres sur chaque
  colonne, tout en préservant actif, marques et absence de lecture parasite.
  411 tests réussis ; 32 tests panneau/glisser réussis sous Wayland. Ruff/mypy
  et revue indépendante sans anomalie ; tris programmatiques et réentrance vérifiés.
- Le signalement de doublon Dolphin reste en diagnostic séparé. Chopper prépare
  un WAV permanent dans `dragged/`, puis transmet une seule URL par QDrag copie.
  Le menu « Copier ici » est une décision du destinataire KIO ; sa présence seule
  ne démontre pas deux transferts Chopper. Ne supprimer aucun WAV déjà référencé
  et ne modifier aucune politique de conservation sans préciser la reproduction.
- Aucun push ; sources et exports existants intacts. Les vrais glissers répétés
  restent volontairement non idempotents et créent des fichiers distincts.

## 07/11/2026 — Wayland par défaut et recette finale

- Après validation utilisateur de l'étape 7, changement ciblé de la politique
  de démarrage : `wayland` dans une session Wayland, au lieu du forçage `xcb`.
  Tous les choix explicites restent respectés ; X11 et portail KDE inchangés.
- Ancien test du défaut XCB remplacé par son exigence Wayland, pas supprimé.
  Cas supplémentaires : XCB explicite, plugin arbitraire, `offscreen`, choix vide,
  et transmission du choix à Qt avant sa construction. Aucun changement moteur,
  audio, format d'export ou cycle de vie des workers.
- Démarrage réel via `app.main`, sans `QT_QPA_PLATFORM` forcé : Qt annonce Wayland.
  Démarrage réel avec choix XCB : Qt annonce XCB. Fenêtres avec 32 candidats
  synthétiques et cache temporaire uniquement ; captures inspectées, pas de défaut
  visible sur ces ouvertures. Cela ne garantit pas tous pilotes/compositeurs.
- La solution `QT_QPA_PLATFORM=xcb uv run chopper` reste documentée pour les
  artefacts de peinture ; aucun repli automatique ne masque un plugin défectueux.
- Sources toujours en lecture seule, WAV permanents distincts à chaque glisser
  (non-idempotence volontaire inchangée), aucun déplacement d'exports ou paramètres.
  Validation utilisateur finale attendue : lecture, thèmes KDE, zoom/défilement,
  Bitwig/Dolphin et réouverture du projet après fermeture de Chopper.
- Suite complète : 407 tests réussis sans affichage et 407 sous Wayland natif ;
  31 tests clavier/géométrie à 150 % sous Wayland réussis. Contrôles statiques
  réussis avec les seules notes mypy/Bandit préexistantes. Checklist manuelle
  `docs/FINAL_VALIDATION.md` pour distinguer ces preuves des essais matériels.
- Revue finale indépendante de `0ad7581..5af9bcb` sans anomalie critique,
  importante ou mineure ; 24 tests ciblés réussis sans affichage puis 24 sous
  Wayland à 150 % par le relecteur. Validation manuelle et publication en attente.

## 03/11/2026 — Actions partagées, menus et raccourcis clavier

- Registre unique `gui/actions.py` : actions partagées entre menus, boutons et
  dialogue « Help → Keyboard shortcuts ». Raccourcis affichés dans les menus,
  l'aide et les info-bulles ; bouton « Analyze album » conservé.
- `M` marque/retire le seul actif, Espace joue/arrête, Échap arrête sans retirer
  les marques. Ctrl+A / Ctrl+Maj+A limités aux samples. Raccourcis de préécoute
  et marquage limités à la zone onde/couloirs/table, jamais à la bibliothèque ou
  à une saisie. Pas de Ctrl+Espace ni de répétition automatique.
- Aucun filtre global de touches : contexte Qt `WidgetWithChildrenShortcut`,
  détection des champs éditables par focus et désactivation pendant les modaux.
  Actions indisponibles désactivées ; exports au clavier et aux boutons utilisent
  la même commande, sans double écriture. Saisie « m m » et sélection du texte intactes.
- Deux régressions prévenues par tests rouges puis verts : l'état modal de Qt
  peut survivre momentanément au retour du focus, d'où une resynchronisation
  différée ; l'action album doit suivre l'état occupé de l'interface et non la
  seule existence d'un thread, pour ne pas se réactiver à un changement de marque.
- Tests natifs : le clavier nécessite l'activation asynchrone par le compositeur
  Wayland. Attendre `qWaitForWindowActive` dans le banc de test, sans contourner
  le focus ni modifier le routage des touches en production.
- Vérifications : 398 tests réussis, dont 16 nouveaux ; ces 16 tests passent
  aussi sous Wayland natif, avec PortAudio seulement simulé et dialogues Qt réels.
  Sources audio et algorithmes inchangés. Exporter plusieurs fois reste non
  idempotent (WAV distincts permanents), comme avant ; aucun nettoyage automatique.
- La politique de démarrage reste XCB par défaut sous Wayland jusqu'à l'étape 8.
  Aucun push de cette étape avant validation utilisateur.
- Revue indépendante de `9998edd..e272e63` sans anomalie critique/importante/mineure ;
  160 tests ciblés et 31 tests actions/géométrie à 150 % réussis par le relecteur.
  71 tests actions/fenêtre passent aussi sous Wayland dans la session d'implémentation.
  Les tests n'attestent pas l'audio matériel, un dépôt réel Bitwig ni un NAS réel.

## 02/11/2026 — Licence Chopper validée par M.B

- Application mot pour mot du texte approuvé dans `LICENSE`, copyright 2026 M.B.
  Licence personnalisée à code accessible, pas une licence open source OSI.
- Production audio commerciale autorisée, y compris samples, banques de sons,
  morceaux et prestations rémunérées, pour particuliers et entreprises. Aucun
  droit sur les sources audio n'est accordé ; licences tierces inchangées.
- Vente/licence payante de Chopper ou d'un dérivé logiciel, ou intégration dans
  un produit logiciel payant, soumises à l'accord écrit préalable de M.B.
- README résumant ces règles ; métadonnées PEP 639 avec identifiant personnalisé
  `LicenseRef-Chopper-Source-Available-1.0` et inclusion du fichier complet dans
  les distributions. Aucun code d'exécution ni fichier audio modifié.
- Texte juridique personnalisé : relecture professionnelle recommandée, aucune
  garantie d'opposabilité déduite des tests ou des contrôles de packaging.
- Vérification : texte de 3 077 octets identique à l'approbation et aux copies
  incluses dans le wheel et le sdist ; licence personnalisée indiquée correctement
  dans les métadonnées. 382 tests réussis, contrôles Ruff/mypy et hooks réussis,
  revue indépendante sans anomalie. Aucun effet de bord d'exécution ajouté ;
  audit juridique exhaustif des dépendances et opposabilité hors de cette revue.

## 02/11/2026 — Chopper, anglais et migration non destructive

- Renommage du paquet, des imports, de la distribution et du lanceur en
  `chopper`. Commande principale `uv run chopper` ; alias temporaire `choppeur`
  vers le même point d'entrée pour les anciens lanceurs. Le dossier de travail
  et le remote existant ne sont pas renommés ; aucune publication effectuée.
- Nouveaux chemins XDG sous `chopper`. En l'absence du nouveau TOML, lecture de
  l'ancien sous `choppeur` sans le modifier ; les sauvegardes atomiques vont
  uniquement au nouveau chemin. Le nouveau fichier gagne si les deux existent.
  Un chemin explicitement fourni ne déclenche jamais ce repli. Les erreurs de
  lecture du nouveau fichier restent visibles. Préférences et longueurs v3 conservées.
- Nouveau cache d'analyse vide ; l'ancien SQLite reste intact. Effet de bord :
  certaines analyses devront être refaites. Aucun déplacement de données privées.
- Interface, erreurs applicatives, README et guide du prototype en anglais
  home-studio. Métadonnées utilisateur, chemins et diagnostics externes inchangés.
  Les sélecteurs natifs peuvent suivre la langue du bureau. Les valeurs internes
  `auto`/`cpu` restent stables malgré les libellés « Automatic » / « CPU only ».
- Nouveaux WAV glissés dans `dragged/` : aucun renommage, suppression ou déplacement
  des anciens fichiers `glissés/` susceptibles d'être référencés par un séquenceur.
  Fréquence, canaux, PCM24, anti-écrasement et conservation après annulation inchangés.
  Répéter un glisser reste volontairement non idempotent.
- Installateur testé uniquement avec des commandes externes simulées dans un
  dossier temporaire, y compris chemins avec espaces, arguments conservés et
  refus d'écraser un fichier/lien étranger. Aucun installateur exécuté sur le système.
- Mise à jour Semgrep préexistante enregistrée séparément en `c95ca2a`, avec
  autorisation explicite de l'utilisateur, sans retirer ni contourner un hook.
- Revue indépendante : un lien symbolique cassé pour le TOML était considéré
  absent et pouvait masquer une configuration devenue temporairement indisponible.
  Corrigé avec trois tests rouges puis verts : nouveau chemin, ancien chemin et
  chemin explicite signalent l'erreur, sans modifier le lien ni revenir aux défauts.
- Vérification finale : 382 tests réussis (25 de plus que la base), 72 tests
  ciblés sous Wayland réussis avec transfert natif simulé ; construction du wheel,
  contrôles statiques et hooks réussis. Captures de l'interface anglaise inspectées
  avec données synthétiques. Dépôt réel Bitwig à valider ; anomalie préexistante du
  thème au teardown des tests rouges et autres chemins d'erreurs historiques
  conservés hors de ce renommage. Aucun défaut de sécurité nouveau évident détecté.

## 01/11/2026 — Choix du dossier mémorisé et longueurs explicites

- Contrat approuvé : aucun chemin d'export imposé, aucune demande au lancement.
  Une petite explication en anglais puis un sélecteur s'ouvrent au premier export
  ou geste de glisser sans dossier. Choix mémorisé et modifiable dans les paramètres.
  Un dossier déjà configuré reste inchangé.
- Premier glisser : après configuration, demander de recommencer le geste ; aucun
  WAV ni transfert Qt à cette occasion. Annulation aux deux étapes sans effet.
  Les poignées ne sont donc plus désactivées faute de dossier. Cela remplace la
  règle précédente décrite dans l'entrée ci-dessous.
- Enregistrement des paramètres par fichier temporaire local puis remplacement
  atomique : un échec préserve l'ancien TOML et la préférence en mémoire ; aucune
  écriture audio après échec. Aucun effacement des anciens exports.
- Paramètres réellement observés : `[1.0]`, version 2. Cela explique l'absence
  des fractions, sans démontrer un défaut du moteur ni établir pourquoi ce choix
  a été enregistré. Migration version 3 réactivant les trois longueurs une fois,
  puis préservation des choix sauvegardés. La simple lecture reste sans écriture.
- Trois cases « 1 bar », « ½ bar », « ¼ bar » remplacent les sept combinaisons ;
  sélection vide refusée. Quotas indépendants et détecteur inchangés.
- Sources en lecture seule, WAV PCM24 permanents dans `glissés/`, fréquence et
  canaux préservés. Les vrais glissers répétés restent non idempotents : fichiers
  distincts conservés même après annulation ; configuration seule sans audio.
- Le renommage global Chopper/anglais et la publication GitHub publique sont
  prévus séparément, pas réalisés par ce correctif.
- Vérifications avant revue : 357 tests réussis et contrôles statiques réussis.
  24 tests ciblés passent sous Wayland, mais les interactions modales et le
  transfert Qt vers une application externe restent simulés dans ces tests.
- Revue indépendante en lecture seule de `a87e8b4..e8c61c8` : aucune anomalie
  critique, importante ou mineure démontrée. Annulation modale Qt également
  contrôlée avec une vraie boucle `exec()` offscreen par le relecteur.
- Limites conservées après revue : dépôt réel Wayland/Bitwig à valider par
  l'utilisateur ; résistance à une coupure électrique et conflits multi-instances
  non garantis par le remplacement atomique seul. Une anomalie préexistante de
  destruction `ThemeManager.eventFilter` est réapparue pendant certains tests
  rouges, pas dans les suites vertes ; les autres points de sauvegarde historiques
  n'ont pas été refondus. Renommage/publication toujours différés.

## 01/11/2026 — Exports communs et glissers WAV permanents

- Les boutons utilisent le dossier configuré ; sinon, un choix de destination
  pour cet export seulement, sans modification silencieuse des paramètres.
- Service d'export commun : chaque réussite précédant un échec est conservée
  et rapportée. Disque plein ou dossier réseau indisponible : erreur visible,
  pas de fausse réussite. Le writer nettoie les fichiers partiellement écrits.
- La poignée seule peut lancer un glisser, après déplacement suffisant avec
  bouton gauche maintenu. Aucun clic sur la poignée, y compris droit, ne change
  l'actif, ne marque ni ne joue. Sans dossier configuré, poignée désactivée et
  explication dans son info-bulle, aucun dialogue au milieu du geste.
- WAV PCM24 dans `<export_dir>/glissés/`, fréquence et canaux préservés ; URL
  locale absolue, action copie uniquement. Le chemin est affiché sans prétendre
  qu'un import Bitwig est réussi sur le seul retour Qt.
- Fichiers conservés après annulation, échec Qt et fermeture. Chaque nouveau
  glisser crée un fichier distinct : opération volontairement non idempotente,
  sans nettoyage automatique, et sans modification des sources.
- Deux boucles de réessai ont été prévenues, tests rouges puis verts : un lien
  symbolique cassé doit occuper son nom même si `exists()` est faux ; un fichier
  à la place du dossier n'est pas une collision de nom de sample. L'anti-écrasement
  atomique reste inchangé, les liens/fichiers existants ne sont jamais supprimés.
- Vérifications : 302 tests réussis et porte statique réussie. Le transfert Qt
  à la plateforme est simulé ; les essais réels Bitwig/Dolphin sous Wayland et
  la réouverture d'un projet Bitwig après fermeture restent à valider.

## 30/10/2026 — Catégories indépendantes, quarts de mesure et dézoom borné

- Deux causes à l'absence de demi-mesures : anciens paramètres `[1.0]` encore
  actifs, et classement global pouvant exclure entièrement une longueur. La
  piste 16 réelle reproduisait ces deux comportements selon les réglages.
- Correction : activer aussi les quarts de mesure ; sélectionner jusqu'à 8
  candidats par longueur, plus 8 one-shots, sans changer le score ni le détecteur.
- Migration versionnée : ancien fichier sans `loop_lengths_version = 2` réactive
  les trois longueurs ; les choix volontaires enregistrés ensuite sont préservés.
  Aucun fichier n'est réécrit à la simple lecture. Le quota devient « par catégorie »
  dans le dialogue, borné à 1–8 ; valeur non entière invalide : repli sur 8.
- Une seule limite temporelle dans la vue de l'onde : début 0, fin durée audio,
  largeur maximale durée audio. Les couloirs utilisent cette même vue, donc les
  gestes des deux vues restent dans les bornes, sans modifier l'amplitude.
- Tests rouges puis verts pour quotas, migration, quarts de mesure et navigation.
  Vérifications : 269 tests, 15 tests graphiques à 150 %, porte statique réussie.
  Piste 16 : 8 résultats dans chacune des quatre catégories ; capture Wayland.
  Les fichiers audio et paramètres utilisateur n'ont pas été modifiés par ce contrôle.

## 30/10/2026 — Apparence KDE et conservation des paramètres de boucle

- Thème commun aux widgets, à l'onde et aux couloirs, suivi via `colorSchemeChanged`
  et changements de palette ; option « Forcer sombre » dans les paramètres.
- En cas de thème Qt `Unknown`, observer la palette de l'application, jamais
  celle de la fenêtre forcée. Les couleurs personnalisées sont appliquées à la
  fenêtre et à ses enfants uniquement : aucune modification du thème système.
- Défaut découvert par le test de conservation des préférences : `findData`
  ne retrouvait pas les tuples Python de longueurs de boucles malgré leur égalité
  en Python. Le dialogue rouvrait avec l'index -1 et rétablissait les deux longueurs.
  Correction : comparaison explicite du contenu des `itemData`.
- Vérifications : 232 tests réussis ; contrastes des textes >=4,5:1, suivi du
  système, retour après forçage, bascules répétées, zoom, marques et lecture
  conservés. Captures Wayland clair/sombre réalisées, sans modification audio.
  Changement global KDE à chaud restant à confirmer par l'utilisateur.

## 30/10/2026 — Trois catégories et couloirs temporels (révision utilisateur)

- Boucles limitées à 1/2 et 1 mesure : moteur et nommage refusent 2/4/8 et les
  autres longueurs ; anciens paramètres filtrés, repli sur les deux longueurs si
  aucune valide. Migration répétable, sans écriture automatique lors de la lecture.
- Le cache des temps/mesures reste utilisable ; les candidats sont recalculés.
  Le détecteur, le score, la durée médiane d'une mesure et les sources ne changent pas.
- Rectangles répartis par début/fin/identité sur des sous-lignes sans occultation,
  avec catégories vides masquées et défilement vertical dédié.
- Le temps se transforme en pixels depuis la vue réelle de l'onde : pas de
  deuxième échelle indépendante. Zoom/pan uniquement horizontaux, Y cadré au
  chargement puis figé ; bouton d'auto-ajustement masqué.
- Les traits de début/fin des candidats sont supprimés. Restent les downbeats
  fins et le surlignage passif du seul sample effectivement en lecture.
- Vérifications : suite complète 224 tests, contrôles statiques et tests
  graphiques à 150 % ; capture Wayland de la piste 16. Thème définitif à venir.

## 30/10/2026 — Onde plate après conservation d'une échelle manuelle

- Diagnostic sur le FLAC stéréo de la piste 16 : fréquence et canaux intacts,
  pic mono d'environ 0,997 ; le chargement multicanal n'aplatit pas les données.
  Un affichage neuf est correct. Le scénario initial exact reste à confirmer
  avec l'utilisateur ; le défaut reproductible est la conservation du zoom.
- Cause reproduite : une modification manuelle des limites désactive le
  recalage automatique de pyqtgraph. `clear()` ne le réactive pas : une nouvelle
  piste conserve une plage verticale trop large et apparaît plate (ou hors cadre).
- Test rouge puis vert : charger une onde après une plage manuelle ±100 et une
  fenêtre temporelle hors piste ; vérifier le retour aux bornes audio.
- Correction : réactiver le recalage automatique avant d'attacher la nouvelle
  courbe. Aucun gain, normalisation ou changement des canaux de lecture/export.
- Affichage : tempo à une décimale dans titre, statut et table ; durée et position
  en `mm:ss.mmm`, avec retenue correcte lors de l'arrondi à la minute.
- Capture Wayland réalisée sur le FLAC réel ; grandes lignes de candidats
  volontairement conservées jusqu'à l'étape 4. Aucun fichier audio source écrit.

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
