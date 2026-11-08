# Chopper

Find usable loops and one-shots in your own music library, preview them and
export automatically named audio files to your DAW. Linux desktop application.

## Requirements

- Linux, Python 3.12, [uv](https://docs.astral.sh/uv/), ffmpeg for MP3/AAC decoding,
  and PortAudio (the `libportaudio2` package on Debian/Ubuntu).
- No GPU required. The default installation uses CPU PyTorch wheels; GPU
  acceleration requires a compatible GPU-enabled PyTorch installation.
- Allow roughly 2 GB for the first environment download. Beat analysis may
  also download model weights on first use. Analysis works on CPU, more slowly.

## Easy installation

From the unpacked project folder:

```bash
bash install.sh
./chopper
```

The installer asks before downloading/installing uv or adding missing system
packages through sudo/apt. A new uv installation goes in `~/.local/bin` without
editing shell profiles. It checks ffmpeg and PortAudio, prepares `.venv` inside
the application folder using the locked runtime dependencies, and generates
`./chopper`. Existing extra packages (including developer tools) are kept on
reinstallation. uv may also cache downloads and install Python under your account.
On systems without apt, install the system audio packages yourself.

Keep the unpacked folder: it contains the application and its Python environment.
`./chopper` starts this installed environment directly, without running uv or
downloading/updating dependencies. A first beat analysis may still download model
weights. If the environment is missing, the launcher asks you to run
`bash install.sh` again. The installer does not delete old launchers and refuses
to overwrite an unrelated `./chopper` before installing anything.

## Manual installation

With uv and the system audio packages already installed:

```bash
uv sync
uv run chopper
```

## Find and export samples

1. Choose **Open library…** and browse to an album or track, including a mounted NAS.
2. Select a track to analyze it, or select an album folder and use **Analyze album**.
3. Look through **1-bar**, **½-bar** and **¼-bar loops**, plus **One-shots**.
   Chopper offers up to eight samples per category when the track supports them;
   short tracks or missing rhythmic information may yield fewer.
4. Click a sample to select it. With **Auto-preview** enabled, it plays once.
   **Ctrl+click** marks or unmarks a sample without selecting or playing it.
5. Use **Export marked** or **Export all** for the displayed track, or drag a
   sample using its `⠿` handle. Source audio is never modified.

On the first export or attempted drag, choose your **sample folder**. There is
no forced Documents folder or setup prompt at startup. The path is remembered
and can be changed in **Settings**. After setting it up during the first drag,
drag the sample again; setup itself creates no audio. Canceling setup writes nothing.

Button exports support 24-bit WAV or FLAC. DAW drags always create permanent
24-bit WAVs in `<sample folder>/dragged/`, preserving the original sample rate
and channels. Every drag creates a separate file, even if the drop is canceled;
Chopper never cleans these files up automatically. Do not move files still
referenced by a DAW project. In Bitwig, use **File → Collect and Save** to collect
external audio into the project folder before archiving or sharing the project.
Qt's reported drop result alone does not prove that a DAW imported the sample.

## Keyboard shortcuts

Use **Help → Keyboard shortcuts** (F1) to see the shortcut list generated from
the same actions as the menus and buttons.

| Action | Shortcut |
| --- | --- |
| Open library | Ctrl+O |
| Settings | Ctrl+, |
| Preview / stop active sample | Space |
| Stop preview | Esc |
| Mark / unmark active sample | M |
| Mark all samples in the displayed track | Ctrl+A |
| Clear all marks | Ctrl+Shift+A |
| Export marked | Ctrl+E |
| Export all samples in the displayed track | Ctrl+Shift+E |
| Keyboard shortcuts | F1 |
| Quit | Ctrl+Q |

Preview and marking shortcuts work in the sample area (waveform, lanes and
table), not in the library, text fields or modal dialogs. Up/Down in the table
select a sample without starting playback. Marking does not start playback.
Unavailable actions are disabled, and holding a shortcut does not repeat it.
**Analyze album** remains available as both a File menu action and a visible button.

## KDE and Wayland

In a Wayland session, Chopper uses native Wayland by default:

```bash
uv run chopper
```

If your desktop shows painting artifacts (such as stripes or incomplete redraws),
try the explicit XWayland/X11 workaround:

```bash
QT_QPA_PLATFORM=xcb uv run chopper
```

XCB was the previous default workaround for rendering problems observed on some
KDE systems. The native default follows the interface's incremental validation;
it is not a guarantee for every compositor or graphics driver. Report regressions.
Chopper does not silently switch backends if a platform plugin fails.

An explicit `QT_QPA_PLATFORM` choice is always respected, including `wayland`,
`xcb` and test platforms such as `offscreen`. X11 sessions are left to Qt's normal
platform selection. KDE native file dialogs
use the desktop portal when no platform theme was explicitly configured. Native
dialog language and raw system/audio-driver diagnostics may follow your desktop locale.

For the final desktop/audio/DAW checks, see [Final manual validation](docs/FINAL_VALIDATION.md).

## Upgrading from Choppeur

Chopper reads legacy preferences if its new settings file does not exist.
New settings take precedence when both exist; future saves go only to the new
location, without changing the old file. The selected sample folder is preserved.

- Settings: `$XDG_CONFIG_HOME/chopper/settings.toml` (default `~/.config/chopper/settings.toml`).
- Cache: `$XDG_CACHE_HOME/chopper/analyses.sqlite` (default `~/.cache/chopper/analyses.sqlite`).

The old analysis cache is left intact; the new cache starts empty, so some tracks
will need analysis again. Existing `glissés/` exports stay where they are; only
new drags use `dragged/`. The old `choppeur` launch command remains temporarily
available for generated launchers; new commands and Python imports use `chopper`.

## License

Chopper is **source-available**, not OSI-approved open source. See the full
[Chopper Source-Available License 1.0](LICENSE), copyright (c) 2026 M.B.

Commercial audio production is allowed, including paid work, sample packs,
sound libraries and finished music, for individuals and businesses. This
software license requires no royalty or Chopper credit for audio outputs.
You remain responsible for the rights to source recordings and samples.

You may study, modify and redistribute the software without charging for it,
provided that you retain the license and copyright notices, identify changes
and do not grant rights to commercialize M.B's code beyond the license.
Selling or licensing Chopper or a software derivative for a fee, or including
either in a paid software product, requires prior written permission from M.B.
Third-party components retain their own licenses. This summary does not
replace the full license; legal review of custom terms is recommended.

## Development

```bash
uv sync --group dev
uv run pre-commit install
uv run pytest
```

Architecture, decisions and historical plans (some in French):
`docs/SPEC.md`, `docs/DECISIONS.md`, `docs/ROADMAP.md`, `docs/HISTORIQUE.md`.
