# Revue finale — sélection manuelle

18/11/2026. Revue indépendante unique de la plage `50e4305..538f5e9`, couvrant
les cinq étapes, le design et les cinq risques du plan. Relecteur en lecture seule,
sans délégation supplémentaire. Aucun push, fusion ni ZIP demandé ou effectué.

## Résultats et corrections

Deux points importants, aucun critique, un mineur. Les deux défauts importants
ont été reproduits avant correction dans sept tests de vrais événements Qt :

- **Croisement des poignées** : les bornes triées étaient réaffectées aux mauvaises
  lignes natives ; région susceptible de disparaître. Identité de la ligne
  déplacée et borne opposée désormais conservées pendant le geste. Gauche/droite,
  avec et sans Alt, vérifiées.
- **Petit mouvement** : le seuil natif pyqtgraph pouvait précéder celui de Qt,
  laissant le rectangle différent des bornes utilisées. Le relâchement traité
  comme clic restaure maintenant le rectangle canonique, sans signal de lecture.
  Les deux poignées et le corps sont couverts.

Vérification après cette passe unique : **719 tests complets**, **171 tests
interface/gestes/actions sous Wayland à 150 %**, Ruff lint/format, mypy et Bandit
réussis. Les hooks de commit restent obligatoires. Aucun risque de sécurité
évident supplémentaire trouvé par l'analyse statique et la revue.

## Point mineur différé

La confirmation d'analyse d'album sans résultats exportables annonce que la
sélection sera retirée. Ce traitement remplit le cache mais conserve l'affichage
manuel actuel : le texte doit être précisé. Les résultats ne sont pas perdus.
Ce point n'est pas inclus dans la passe de correction des anomalies importantes.

## Arbitrages pris pendant l'exécution

- **Validation entre étapes** plutôt qu'exécution continue : respecter le plan
  approuvé et AGENTS ; coût : une confirmation utilisateur entre livraisons.
- **Cible de passage conservée au remplacement des candidats**, lecture arrêtée ;
  clear_range rétablit un éventuel sample actif sans le jouer. Justification :
  la région et la dernière cible choisie restent présentes. Risque si inadapté :
  Espace vise le passage plutôt qu'un nouveau sample tant qu'aucun sample n'est choisi.
- **Identifiant lu sur le worker dans un slot QObject principal**, plutôt que
  lambda : test rouge prouvant qu'une lambda traitait l'erreur dans le mauvais
  thread. Coût : une propriété de métadonnée supplémentaire, signaux inchangés.
- **Signal d'invalidation distinct pour geste effondré** : pas de fausse sélection
  terminée valide, aucun ancien résultat effacé, Chop désactivé. Risque si inadapté :
  le passage n'est plus sélectionné, mais les résultats restent à quitter explicitement.
- **Arrêt de préécoute avant export par poignée en mode manuel seulement** :
  préserver le contrat historique testé du glisser automatique. Coût : différence
  entre les deux modes ; exports par boutons toujours précédés d'un arrêt.
- **Analyse d'album conserve l'affichage manuel après consentement** : ce workflow
  remplit le cache sans remplacer le morceau affiché. Coût : une future transition
  destructive peut demander à nouveau confirmation ; ne pas renommer ces résultats
  manuels en résultats automatiques.
- **Espace natif et ledger conservés pour l'essai utilisateur**, plutôt que
  nettoyage destructif ou intégration implicite. Justification : validation
  utilisateur et consentement avant suppression imposés par le projet. Coût :
  notes de revue ignorées par Git restant localement, sans effet sur l'application.

## Limites retenues après la revue

- Audio matériel, import DAW et interception d'Alt par KWin : essai humain requis,
  pas une preuve donnée par des événements synthétiques. Risque : comportement
  propre à un périphérique ou à la configuration du bureau.
- Installation Kubuntu destinataire et ZIP : non reconstruits/non validés pour
  cette fonction. Risque : l'ancien ZIP ne contient pas la sélection manuelle.
- Précision des détecteurs et analyse interne corrompue : contrats historiques non
  élargis ; le worker signale un échec et conserve les anciens résultats. Risque :
  métadonnées mauvaises donnant des résultats inutilisables ou une erreur.

## Effets de bord et régressions

Recherche répétable sans écriture audio, préférences ou cache ; sources toujours
en lecture seule. Aucun ancien export supprimé. Les exports répétés sont
volontairement non idempotents et produisent des noms distincts.

Régressions : réglages automatiques, classement local, formats WAV/FLAC, identité
audio/Analysis, clics/marques, raccourcis/modalité et fermeture des threads.
Limites : fenêtres courtes/invalides/vides, non-fini hors zone, silence en bordure,
retours anciens, export partiel/annulé et fermeture échouée. Recette de l'essai
utilisateur : `docs/FINAL_VALIDATION.md`.
