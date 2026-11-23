# Thème sombre inspiré de Material Design 3

Le nouveau style s’applique uniquement lorsque Chopper est déjà en mode sombre,
par le thème système ou par **Force dark mode**. Le mode clair, le choix du
mode et les réglages enregistrés restent inchangés.

## Approche

Conserver PySide6 et pyqtgraph, avec une palette et une feuille de style Qt
définies dans `gui/theme.py` et limitées aux fenêtres et contrôles concernés. La palette seule ne permet pas de
régler les arrondis et les espacements internes ; remplacer les composants
natifs serait hors périmètre. Un raccord dans `MainWindow._apply_theme` applique
le style sombre et le retire au retour en clair. Les paramètres suivent aussi la
bascule, même s’ils sont déjà ouverts.

## Direction visuelle

- Fond charbon `#202225`, surface de travail `#282B2F`, contrôles `#34383D`,
  texte `#ECEDEF`, texte secondaire `#BAC0C8`, accent ambre `#E7B47E`.
- Police système conservée. Les boutons et champs ont des angles arrondis,
  des espacements internes réguliers et un contour de focus visible au clavier.
  Préserver la lisibilité des états désactivés et des flèches des contrôles Qt.
- Aucun déplacement des commandes : bibliothèque à gauche, forme d’onde et
  échantillons à droite. La forme d’onde reste claire sur fond sombre ; les
  couleurs qui distinguent boucles, one-shots et lecture gardent leur rôle.

## Limites et validation

Pas de changement de fonctions, raccourcis, disposition, dépendances, moteur
audio ni palette globale Qt. Vérifier le rendu sur un exemple synthétique,
le passage sombre/clair, le contraste et les interactions des contrôles.
