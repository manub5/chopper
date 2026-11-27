from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QItemSelectionModel, QSignalBlocker, Qt, Signal
from PySide6.QtWidgets import QHeaderView, QTreeWidget, QTreeWidgetItem, QTreeWidgetItemIterator, QWidget

from chopper.core.audio_io import AUDIO_EXTENSIONS

_PATH_ROLE = Qt.ItemDataRole.UserRole
_LOADING_PLACEHOLDER = "…"


class LibraryPanel(QTreeWidget):
    """Navigation dossiers -> albums -> pistes.

    Le contenu est chargé dossier par dossier, à l'ouverture (jamais toute
    l'arborescence d'un coup) : sur un NAS ou un dossier réseau, parcourir
    tout l'arbre à l'avance peut geler l'interface (chaque accès a une
    latence réseau) ou tourner indéfiniment sur un lien symbolique circulaire.
    """

    track_selected = Signal(Path)
    folder_selected = Signal(object)  # Path or None
    load_failed = Signal(Path, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._session_entries: dict[Path, bool] = {}
        self.setHeaderHidden(True)
        self.header().setStretchLastSection(False)
        self.header().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.itemSelectionChanged.connect(self._on_selection_changed)
        self.itemExpanded.connect(self._on_item_expanded)

    def set_root(self, root: Path) -> None:
        self.clear()
        self._populate_level(self.invisibleRootItem(), root)
        for path, is_album in self._session_entries.items():
            self._append_entry(path, is_album=is_album)

    def add_album(self, path: Path) -> None:
        path = path.absolute()
        if not self._contains_path(path, nested_only=True):
            self._add_session_entry(path, is_album=True)

    def add_track(self, path: Path) -> None:
        self._add_session_entry(path, is_album=False)

    def add_dropped_path(self, path: Path, *, is_album: bool) -> None:
        path = path.absolute()
        if not self._contains_path(path):
            self._add_session_entry(path, is_album=is_album)

    def _contains_path(self, path: Path, *, nested_only: bool = False) -> bool:
        iterator = QTreeWidgetItemIterator(self)
        while (item := iterator.value()) is not None:
            if item.data(0, _PATH_ROLE) == path and (not nested_only or item.parent() is not None):
                return True
            iterator += 1
        return False

    def _add_session_entry(self, path: Path, *, is_album: bool) -> None:
        path = path.absolute()
        if path not in self._session_entries:
            self._session_entries[path] = is_album
            self._append_entry(path, is_album=is_album)

    def _append_entry(self, path: Path, *, is_album: bool) -> None:
        iterator = QTreeWidgetItemIterator(self)
        while (item := iterator.value()) is not None:
            if item.data(0, _PATH_ROLE) == path and item.parent() is None:
                if is_album:
                    item.setText(0, str(path))
                    item.setToolTip(0, str(path))
                    index = self.indexOfTopLevelItem(item)
                    if index < self.topLevelItemCount() - 1:
                        expanded = item.isExpanded()
                        selected = self.selectedItems()
                        current = self.currentItem()
                        with QSignalBlocker(self):
                            self.takeTopLevelItem(index)
                            self.addTopLevelItem(item)
                            item.setExpanded(expanded)
                            if current is not None:
                                self.setCurrentItem(current, 0, QItemSelectionModel.SelectionFlag.NoUpdate)
                            for selected_item in selected:
                                selected_item.setSelected(True)
                return
            iterator += 1
        if not is_album:
            # A standalone import has a single root entry, even if its folder was expanded first.
            self._remove_nested_track_entries(path)
        self._create_entry(self.invisibleRootItem(), path, is_folder=is_album, show_path=is_album)

    def _remove_nested_track_entries(self, path: Path) -> None:
        matches = []
        iterator = QTreeWidgetItemIterator(self)
        while (item := iterator.value()) is not None:
            parent = item.parent()
            if parent is not None and item.data(0, _PATH_ROLE) == path:
                matches.append((parent, item))
            iterator += 1
        for parent, item in matches:
            parent.removeChild(item)

    @staticmethod
    def _create_entry(
        parent: QTreeWidgetItem, path: Path, *, is_folder: bool, show_path: bool = False
    ) -> None:
        item = QTreeWidgetItem(parent, [str(path) if show_path else path.name])
        item.setData(0, _PATH_ROLE, path)
        if show_path:
            item.setToolTip(0, str(path))
        if is_folder:
            QTreeWidgetItem(item, [_LOADING_PLACEHOLDER])

    def _populate_level(self, parent_item: QTreeWidgetItem, folder: Path) -> None:
        """Ajoute uniquement les enfants directs de `folder` (un seul niveau)."""
        try:
            entries = sorted(folder.iterdir(), key=lambda p: p.name.lower())
        except OSError as exc:
            # Dossier illisible (permissions, partage réseau déconnecté...) : on le
            # signale plutôt que de laisser un panneau vide sans explication.
            self.load_failed.emit(folder, str(exc))
            return

        for entry in entries:
            try:
                is_dir = entry.is_dir()
            except OSError:
                continue  # entrée inaccessible (lien cassé, droit réseau...) : ignorée

            if is_dir:
                if parent_item is self.invisibleRootItem() or entry.absolute() not in self._session_entries:
                    self._create_entry(parent_item, entry, is_folder=True)
            else:
                try:
                    # entry.exists() suit les liens symboliques : un lien cassé
                    # (fréquent sur un partage réseau) renvoie False sans lever
                    # d'exception, et n'est donc pas proposé comme piste.
                    is_audio = entry.suffix.lower() in AUDIO_EXTENSIONS and entry.exists()
                except OSError:
                    continue
                if is_audio and self._session_entries.get(entry.absolute()) is not False:
                    self._create_entry(parent_item, entry, is_folder=False)

    def _on_item_expanded(self, item: QTreeWidgetItem) -> None:
        if item.childCount() != 1:
            return  # déjà chargé (plusieurs enfants réels), ou dossier vide
        placeholder = item.child(0)
        if placeholder is None or placeholder.text(0) != _LOADING_PLACEHOLDER:
            return
        item.takeChild(0)
        folder: Path | None = item.data(0, _PATH_ROLE)
        if folder is not None:
            self._populate_level(item, folder)

    def _on_selection_changed(self) -> None:
        items = self.selectedItems()
        if not items:
            self.folder_selected.emit(None)
            return
        item = items[0]
        path: Path | None = item.data(0, _PATH_ROLE)
        if path is None:
            self.folder_selected.emit(None)
            return
        if path.is_dir():
            self.folder_selected.emit(path)
        else:
            parent = item.parent()
            self.folder_selected.emit(parent.data(0, _PATH_ROLE) if parent is not None else None)
            self.track_selected.emit(path)
