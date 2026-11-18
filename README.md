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

After successful installation it offers a **Chopper** entry in KDE's application
menu, showing its full destination before asking permission. Skipping this entry
keeps `./chopper` usable; existing unrelated shortcuts and symbolic links are
never overwritten. See [Kubuntu installation and first-run checks](docs/INSTALL_KUBUNTU.md)
for details, retry instructions and shortcut removal. Kubuntu 26.04.1 is the
initial target, not yet a claim of verified compatibility on a clean machine.

The installer then offers an optional global command:
`~/.local/bin/chopper` is a **symbolic link** to this folder's `./chopper`, not a
copy. After accepting it, you can run `chopper` from another directory. The
launcher resolves its links and uses this project's environment without running uv.
Keep the project folder in place so future code updates use the same launcher.

Two further, separate choices offer a dedicated charcoal/orange SVG and an
executable KDE Desktop shortcut. The Desktop folder comes from `xdg-user-dir
DESKTOP`, never a guessed path. Menu and Desktop shortcuts use the same installed
SVG; declining the icon keeps a generic audio icon. No autostart is added.

The exact destinations and the local `.chopper-install.json` ownership receipt
are shown before consent. Keep this receipt: it identifies the integrations this
installation owns. Foreign or modified files/links are not replaced, even when
they have the same name or target. The receipt is not tracked or distributed.

If `~/.local/bin` was absent from the terminal's initial PATH, installation prints
instructions. Ubuntu's default profile adds the directory at login when it exists;
log out and back in, or use `export PATH="$HOME/.local/bin:$PATH"` in the current
terminal only. No profile files are edited. A different `chopper` command earlier
on PATH is reported rather than overwritten.

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

## Chop a selected passage

Left-drag on the waveform to select a passage. Drag either edge to trim it, or
drag inside to move it. Edges snap to the nearest downbeat; hold **Alt** for free
selection. Without usable downbeats, selection is free. A collapsed range does
not create a loop or start preview.

Choose **Length** (¼, ½, 1, 2 or 4 bars), then **Chop selection** (**C**).
The selected passage is previewed once at mouse release when **Auto-preview**
is on; chopping itself does not start playback. **Space** previews/stops the last
target you chose: the passage or a clicked/navigated sample, even with auto off.

Only the chosen loop length and one-shots inside the passage are searched, with
the current per-category quota and one-shot duration settings. Loops must fit in
full. A short passage can still yield one-shots; a missing downbeat grid does not
invent loop positions. Searches reuse the loaded audio and analysis.

Changing the passage or Length keeps the previous samples until you chop again.
**Samples from** shows their original bounds; exports always use those bounds,
not a subsequently adjusted rectangle. Length is remembered for this session only;
automatic analysis keeps its existing ¼-, ½- and 1-bar settings.

Use **Whole track**, **Esc**, or click outside the passage to return to automatic
samples. Chopper asks before leaving a selection or replacing manual results:
export all manual samples and continue, continue without exporting, or cancel.
Cancel is the safe default; it preserves the passage, samples and keep marks.
The same protection applies before opening another track, analyzing an album or
closing. Export cancellation/failure blocks the transition; partial exports stay
on disk and are named in the error message. Retrying can create additional files.
Esc stops preview before asking; canceling does not restart it.

Use **middle-drag** or **Shift+wheel** to pan horizontally on the waveform and
sample lanes; the wheel alone zooms. The view stays within the track and the
vertical axis stays fixed. Samples in lanes are not editable by left-dragging.

## Keyboard shortcuts

Use **Help → Keyboard shortcuts** (F1) to see the shortcut list generated from
the same actions as the menus and buttons.

| Action | Shortcut |
| --- | --- |
| Open library | Ctrl+O |
| Settings | Ctrl+, |
| Preview / stop last sample or passage target | Space |
| Stop preview / leave selection | Esc |
| Chop selection | C |
| Mark / unmark active sample | M |
| Mark all samples in the displayed track | Ctrl+A |
| Clear all marks | Ctrl+Shift+A |
| Export marked | Ctrl+E |
| Export all samples in the displayed track | Ctrl+Shift+E |
| Keyboard shortcuts | F1 |
| Quit | Ctrl+Q |

Preview, chop and marking shortcuts work in the sample area (waveform, lanes and
table), not in the library. Esc also works outside the sample area. Sample
shortcuts and Esc do not affect text fields or modal dialogs. Up/Down in the table
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

From a **clean Git checkout** (not the recipient's extracted ZIP), create a
shareable source archive and its SHA-256 file with:

```bash
uv run --no-sync python scripts/build_release.py
```

Both files go in `dist/`, named with the package version and 12 characters of the
source commit. The ZIP contains only the runtime sources, installer, license and
user guides; dependencies are downloaded during installation. It does not include
Git history, tests, developer hooks, your environment, settings or audio. A repeated
build of the same commit preserves identical outputs and refuses conflicting
files or symbolic links. The builder does not publish anything to GitHub.

For development, use the full Git repository:

```bash
uv sync --group dev
uv run pre-commit install
uv run pytest
```

Architecture, decisions and historical plans in the full repository (some in French):
`docs/SPEC.md`, `docs/DECISIONS.md`, `docs/ROADMAP.md`, `docs/HISTORIQUE.md`.
