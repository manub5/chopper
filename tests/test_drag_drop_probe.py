import runpy
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest


@pytest.fixture
def probe():
    return runpy.run_path(Path(__file__).parents[1] / "prototypes" / "drag_drop_wayland.py")


def test_drag_payload_is_a_real_stereo_wav_with_local_file_url(probe, qapp, tmp_path):
    root = tmp_path / "échantillons avec espaces"
    root.mkdir()
    path, mime = probe["create_drag_payload"](root)
    info = sf.info(path)
    assert info.samplerate == 44100
    assert info.channels == 2
    assert info.frames == 88200
    assert info.subtype == "PCM_24"
    assert mime.hasFormat("text/uri-list")
    assert mime.urls()[0].isLocalFile()
    assert Path(mime.urls()[0].toLocalFile()) == path
    samples, _ = sf.read(path)
    assert np.max(np.abs(samples)) > 0
    assert np.max(np.abs(samples)) < 1


def test_repeated_drags_never_overwrite_the_previous_export(probe, qapp, tmp_path):
    first, _ = probe["create_drag_payload"](tmp_path)
    before = first.read_bytes()
    second, _ = probe["create_drag_payload"](tmp_path)
    assert first != second
    assert first.read_bytes() == before
    assert second.is_file()


def test_opening_window_and_clicking_handle_do_not_create_audio(probe, qapp, tmp_path):
    window = probe["ProbeWindow"](tmp_path)
    try:
        assert window.windowTitle() == "Chopper — disposable drag-and-drop probe"
        assert window.handle.text() == "⠿  Drag this sample"
        QTest.mouseClick(window.handle, Qt.MouseButton.LeftButton)
        assert list(tmp_path.iterdir()) == []
    finally:
        window.close()


def test_export_failure_is_visible_without_starting_external_drag(probe, qapp, tmp_path):
    not_a_directory = tmp_path / "file"
    not_a_directory.write_text("untouched")
    window = probe["ProbeWindow"](not_a_directory)
    try:
        window.handle.start_drag()
        assert "Drag-and-drop failed:" in window.log.toPlainText()
        assert not_a_directory.read_text() == "untouched"
    finally:
        window.close()
