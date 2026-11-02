import pytest
from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QWidget


@pytest.fixture
def manager(qapp):
    from chopper.gui.theme import ThemeManager

    original = QPalette(qapp.palette())
    owner = QWidget()
    theme = ThemeManager(parent=owner)
    yield theme
    owner.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qapp.setPalette(original)
    qapp.processEvents()


def system_scheme(qapp, scheme):
    qapp.styleHints().colorSchemeChanged.emit(scheme)
    qapp.processEvents()


def test_force_dark_then_restore_current_system_scheme(manager, qapp):
    system_scheme(qapp, Qt.ColorScheme.Light)
    light = manager.palette
    manager.set_force_dark(True)
    dark = manager.palette
    assert light.background != dark.background
    assert light.text != dark.text
    assert dark.dark
    system_scheme(qapp, Qt.ColorScheme.Dark)
    manager.set_force_dark(False)
    assert manager.palette.dark
    system_scheme(qapp, Qt.ColorScheme.Light)
    assert manager.palette == light


def test_unknown_scheme_uses_external_palette_not_forced_widget_palette(manager, qapp):
    system_scheme(qapp, Qt.ColorScheme.Unknown)
    palette = QPalette(qapp.palette())
    palette.setColor(QPalette.ColorRole.Window, QColor("#fafafa"))
    qapp.setPalette(palette)
    qapp.processEvents()
    assert not manager.palette.dark
    manager.set_force_dark(True)
    window = QWidget()
    window.setPalette(manager.palette.to_qpalette())
    manager.set_force_dark(False)
    assert not manager.palette.dark
    manager.set_force_dark(True)
    palette.setColor(QPalette.ColorRole.Window, QColor("#121212"))
    qapp.setPalette(palette)
    qapp.processEvents()
    manager.set_force_dark(False)
    assert manager.palette.dark
    window.close()


def luminance(color):
    values = [v / 255 for v in (color.red(), color.green(), color.blue())]
    linear = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in values]
    return sum(value * weight for value, weight in zip(linear, (0.2126, 0.7152, 0.0722), strict=True))


@pytest.mark.parametrize("scheme", [Qt.ColorScheme.Light, Qt.ColorScheme.Dark])
def test_palette_contrast_and_sample_states(manager, qapp, scheme):
    system_scheme(qapp, scheme)
    palette = manager.palette
    for background in (palette.background, palette.surface):
        for text in (palette.text, palette.secondary):
            high, low = sorted((luminance(QColor(background)), luminance(QColor(text))), reverse=True)
            assert (high + 0.05) / (low + 0.05) >= 4.5
    loop = palette.sample_color("loop", marked=False)
    shot = palette.sample_color("shot", marked=False)
    assert 15 <= loop.hue() <= 40
    assert 190 <= shot.hue() <= 230
    marked = palette.sample_color("loop", marked=True)
    assert loop.hue() == marked.hue()
    assert marked.alpha() > loop.alpha()
    assert palette.active != palette.playing


def test_repeated_force_choice_does_not_emit_or_loop(manager, qapp):
    changes = []
    manager.changed.connect(lambda: changes.append(True))
    system_scheme(qapp, Qt.ColorScheme.Light)
    changes.clear()
    manager.set_force_dark(True)
    manager.set_force_dark(True)
    for _ in range(3):
        qapp.processEvents()
    assert changes == [True]


def test_window_graphs_and_table_follow_theme_without_losing_state(qapp, tmp_path, loaded_track, monkeypatch):
    import sounddevice as sd

    from chopper.core.cache import AnalysisCache
    from chopper.core.settings import Settings
    from chopper.gui.main_window import MainWindow

    window = MainWindow(Settings(), AnalysisCache(tmp_path / "cache.sqlite"))

    class Stream:
        active = True

    stream = Stream()

    def stop(**kwargs):
        stream.active = False

    monkeypatch.setattr(sd, "play", lambda *args, **kwargs: None)
    monkeypatch.setattr(sd, "get_stream", lambda: stream)
    monkeypatch.setattr(sd, "stop", stop)
    try:
        window._on_track_analyzed(loaded_track)
        state = window.sample_state
        state.click(state.items[0].id)
        state.toggle_mark(state.items[1].id)
        player = window.preview_player
        audio = state.loaded_track.samples
        x_range, y_range = window.waveform_view.viewRange()
        window.theme_manager.set_force_dark(True)
        qapp.processEvents()
        palette = window.theme_manager.palette
        assert window.palette().color(QPalette.ColorRole.Window) == QColor(palette.background)
        assert window.waveform_view.backgroundBrush().color() == QColor(palette.surface)
        assert window.sample_lanes.palette().color(QPalette.ColorRole.Base) == QColor(palette.surface)
        assert window.candidates_panel.table.palette().color(QPalette.ColorRole.Text) == QColor(palette.text)
        assert window.preview_player is player
        assert state.loaded_track.samples is audio
        assert state.active_id == state.items[0].id
        assert state.playing_id == state.items[0].id
        assert window.waveform_view._playing_region.isVisible()
        assert state.marked_ids == {state.items[1].id}
        new_x, new_y = window.waveform_view.viewRange()
        assert new_x == pytest.approx(x_range)
        assert new_y == pytest.approx(y_range)
    finally:
        window.close()
