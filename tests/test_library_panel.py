from pathlib import Path

import pytest
from PySide6.QtWidgets import QTreeWidgetItem

from chopper.gui.library_panel import LibraryPanel

_LOADING_PLACEHOLDER = "…"


@pytest.mark.parametrize("expand_first", [False, True])
def test_standalone_import_is_unique_regardless_of_album_expansion(qapp, tmp_path, expand_first):
    _make_library(tmp_path)
    panel = LibraryPanel()
    panel.set_root(tmp_path)
    album = _find_top_level(panel, "AlbumA")
    path = tmp_path / "AlbumA" / "01 - Track One.wav"
    if expand_first:
        panel.expandItem(album)
    panel.add_track(path)
    for _ in range(2):
        album = _find_top_level(panel, "AlbumA")
        panel.expandItem(album)
        assert album.childCount() == 0
        standalone = _find_top_level(panel, path.name)
        folders = []
        panel.folder_selected.connect(folders.append)
        standalone.setSelected(True)
        assert folders == [None]
        panel.folder_selected.disconnect(folders.append)
        panel.set_root(tmp_path)


def _make_library(root: Path) -> None:
    album_a = root / "AlbumA"
    album_a.mkdir()
    (album_a / "01 - Track One.wav").write_bytes(b"")
    (album_a / "cover.jpg").write_bytes(b"")  # ignoré : pas un fichier audio

    album_b = root / "AlbumB"
    album_b.mkdir()
    (album_b / "01 - Other.mp3").write_bytes(b"")


def _find_top_level(panel: LibraryPanel, name: str) -> QTreeWidgetItem:
    for i in range(panel.topLevelItemCount()):
        item = panel.topLevelItem(i)
        assert item is not None
        if item.text(0) == name:
            return item
    raise AssertionError(f"Aucun élément de premier niveau nommé {name!r}")


def test_set_root_lists_top_level_folders_without_descending(qapp, tmp_path):
    _make_library(tmp_path)
    panel = LibraryPanel()

    panel.set_root(tmp_path)

    assert panel.topLevelItemCount() == 2
    names = sorted(panel.topLevelItem(i).text(0) for i in range(panel.topLevelItemCount()))
    assert names == ["AlbumA", "AlbumB"]

    # Un seul niveau chargé : chaque dossier n'a qu'un enfant provisoire, pas
    # encore son contenu réel (indispensable pour ne pas geler sur un NAS).
    album_a_item = _find_top_level(panel, "AlbumA")
    assert album_a_item.childCount() == 1
    assert album_a_item.child(0).text(0) == _LOADING_PLACEHOLDER


def test_expanding_a_folder_loads_its_audio_files_only(qapp, tmp_path):
    _make_library(tmp_path)
    panel = LibraryPanel()
    panel.set_root(tmp_path)
    album_a_item = _find_top_level(panel, "AlbumA")

    panel.expandItem(album_a_item)

    child_names = sorted(album_a_item.child(i).text(0) for i in range(album_a_item.childCount()))
    assert child_names == ["01 - Track One.wav"]


def test_expanding_twice_does_not_duplicate_children(qapp, tmp_path):
    _make_library(tmp_path)
    panel = LibraryPanel()
    panel.set_root(tmp_path)
    album_a_item = _find_top_level(panel, "AlbumA")

    panel.expandItem(album_a_item)
    panel.expandItem(album_a_item)

    assert album_a_item.childCount() == 1


def test_added_albums_append_in_order_with_paths_and_lazy_children(qapp, tmp_path):
    root = tmp_path / "library"
    root.mkdir()
    _make_library(root)
    panel = LibraryPanel()
    panel.set_root(root)
    albums = [tmp_path / name / "Album" for name in ("second", "first")]
    tracks = []
    for album in albums:
        album.mkdir(parents=True)
        track = album / "track.wav"
        track.touch()
        tracks.append(track)
    selected = []
    panel.folder_selected.connect(selected.append)
    for album in (*albums, albums[0]):
        panel.add_album(album)
    assert panel.topLevelItemCount() == 4
    for index, (album, track) in enumerate(zip(albums, tracks, strict=True), 2):
        item = panel.topLevelItem(index)
        assert str(album) in item.text(0)
        assert item.child(0).text(0) == _LOADING_PLACEHOLDER
        panel.expandItem(item)
        assert item.child(0).text(0) == track.name
    assert not selected
    panel.resize(250, 75)
    panel.show()
    qapp.processEvents()
    assert panel.verticalScrollBar().maximum() > 0
    panel.close()


def test_standalone_track_shows_basename_and_does_not_select_on_add(qapp, tmp_path):
    panel = LibraryPanel()
    track = tmp_path / "Solo.wav"
    track.touch()
    selected = []
    panel.track_selected.connect(selected.append)
    panel.add_track(track)
    panel.add_track(track)
    assert not selected
    assert panel.topLevelItemCount() == 1
    item = panel.topLevelItem(0)
    assert item.text(0) == "Solo.wav"
    item.setSelected(True)
    assert selected == [track]


def test_adding_an_album_already_in_root_moves_it_to_end_without_duplicates(qapp, tmp_path):
    _make_library(tmp_path)
    panel = LibraryPanel()
    panel.set_root(tmp_path)
    album = tmp_path / "AlbumA"
    panel.add_album(album)
    panel.add_album(album)
    for _ in range(2):
        assert panel.topLevelItemCount() == 2
        assert panel.topLevelItem(0).text(0) == "AlbumB"
        assert panel.topLevelItem(1).text(0) == str(album)
        panel.set_root(tmp_path)


def test_selecting_a_track_emits_track_selected(qapp, tmp_path):
    _make_library(tmp_path)
    panel = LibraryPanel()
    panel.set_root(tmp_path)
    album_a_item = _find_top_level(panel, "AlbumA")
    panel.expandItem(album_a_item)
    track_item = album_a_item.child(0)

    received = []
    panel.track_selected.connect(received.append)

    track_item.setSelected(True)

    assert received == [tmp_path / "AlbumA" / "01 - Track One.wav"]


def test_selecting_a_folder_emits_folder_selected_before_expansion(qapp, tmp_path):
    _make_library(tmp_path)
    panel = LibraryPanel()
    panel.set_root(tmp_path)

    received = []
    panel.folder_selected.connect(received.append)

    panel.topLevelItem(0).setSelected(True)

    assert len(received) == 1
    assert received[0] in (tmp_path / "AlbumA", tmp_path / "AlbumB")


def test_set_root_on_unreadable_folder_emits_load_failed(qapp, tmp_path):
    # Un fichier (pas un dossier) fait échouer iterdir() avec OSError, quels
    # que soient les droits de l'utilisateur (y compris root) : cible fiable
    # pour simuler un dossier NAS devenu inaccessible.
    not_a_folder = tmp_path / "not_a_folder"
    not_a_folder.write_bytes(b"")
    panel = LibraryPanel()

    received = []
    panel.load_failed.connect(lambda folder, message: received.append((folder, message)))

    panel.set_root(not_a_folder)

    assert len(received) == 1
    assert received[0][0] == not_a_folder


def test_a_broken_symlink_does_not_break_the_rest_of_the_listing(qapp, tmp_path):
    album = tmp_path / "AlbumC"
    album.mkdir()
    (album / "01 - Good.wav").write_bytes(b"")
    (album / "broken_link.wav").symlink_to(album / "does_not_exist.wav")

    panel = LibraryPanel()
    panel.set_root(tmp_path)
    album_item = _find_top_level(panel, "AlbumC")

    panel.expandItem(album_item)

    names = [album_item.child(i).text(0) for i in range(album_item.childCount())]
    assert names == ["01 - Good.wav"]


def test_a_folder_with_thousands_of_tracks_expands_without_hanging(qapp, tmp_path):
    """
    Le chargement était auparavant récursif dès set_root() : sur une grosse
    collection (un dossier "Various Artists" ou un import en vrac), ça
    pouvait geler l'interface d'attente longtemps, surtout avec la latence
    d'un NAS. Le chargement paresseux (un seul niveau à la fois) doit rester
    rapide même avec beaucoup de fichiers dans UN SEUL dossier.
    """
    import time

    album = tmp_path / "BigCompilation"
    album.mkdir()
    n_tracks = 3000
    for i in range(n_tracks):
        (album / f"{i:04d} - Track.wav").write_bytes(b"")

    panel = LibraryPanel()

    start = time.monotonic()
    panel.set_root(tmp_path)
    album_item = _find_top_level(panel, "BigCompilation")
    panel.expandItem(album_item)
    elapsed = time.monotonic() - start

    assert album_item.childCount() == n_tracks
    assert elapsed < 10.0, f"trop lent ({elapsed:.1f}s) : régression de performance probable"
