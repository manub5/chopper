# Installing Chopper on Kubuntu

Target for the first shared build: **Kubuntu 26.04.1**. Compatibility on a clean
target machine and its CPU architecture still needs the checks below. Isolated
installer tests are not proof of desktop, audio-driver or hardware compatibility.
The shareable ZIP is prepared separately; these instructions describe its install flow.

## Install once

1. Extract the Chopper archive into a folder you choose and intend to keep.
   Do not run it from inside the ZIP or a temporary extraction directory.
2. Open that extracted application folder in Dolphin, then open a terminal there
   (Shift+F4 in Dolphin) and run:

   ```bash
   bash install.sh
   ```

3. Read the prompts. If uv is missing, the installer asks before downloading its
   official installer and putting uv in `~/.local/bin`, without editing shell
   profiles. Missing ffmpeg/PortAudio packages are offered through apt and sudo;
   sudo may ask for your login password in the terminal. No application files
   need sudo. Declining a required dependency stops installation.
4. Wait for the locked runtime dependencies to install into `.venv` inside this
   application folder. Allow roughly 2 GB of downloads on first installation;
   this estimate may vary. uv can also cache downloads and install Python under
   your account. Existing extra packages are kept if you reinstall.
5. The installer shows the full location of an optional application-menu entry,
   normally `~/.local/share/applications/chopper.desktop`. Answer `y` to create
   or update it. A different absolute `XDG_DATA_HOME` is respected. The folders
   and entry are only written after you agree. Pressing Enter, answering `n`,
   or reaching the end of input skips the menu entry without failing the local
   installation.

Once installed, find **Chopper** in KDE's application menu. If you skipped the
menu entry, open a terminal in the application folder and run `./chopper`.
The menu entry uses your system's audio application icon; it does not place an
icon on the desktop or add autostart behavior.

## Internet, storage and your audio

The installed launcher does not run uv, synchronize packages, or download
dependencies. The first beat analysis may still download its model weights.
An entirely offline first installation or first analysis is not promised.

Keep the application folder: the shortcut points to its launcher and the Python
environment also depends on that location. For another location, use a fresh
extraction and run the installer there, then agree to update the menu entry.
Do not simply move the already-installed `.venv` and expect it to work.

Chopper never changes your source audio. Preferences and analysis cache retain
their existing XDG locations. Samples exported or dragged into a DAW are separate
files that must stay available to that DAW. Repeated drags intentionally create
distinct permanent WAVs, even when a drop is canceled; installation does not
clean up samples, settings or old application folders.

## Retry or fix a menu entry

- If installation fails, read the terminal error and run `bash install.sh` again
  after resolving it. A dependency error is not reported as a completed install.
- If menu-entry creation fails after the local installation succeeded, `./chopper`
  is still usable. Fix the reported destination or permission problem, then rerun
  the installer. Do not run it with sudo to work around a home-folder error.
- The installer refuses an unrelated `./chopper` or `chopper.desktop`, including
  symbolic links. It only updates its own marked regular files. Move an unrelated
  conflicting file yourself only if you know what it is and want to keep it elsewhere.
- A path containing `=` or control characters cannot be used for the menu entry;
  choose another application folder. Spaces, apostrophes, dollar signs,
  percentages, quotes, backslashes and accented characters are tested.
- Native Wayland is the default in a Wayland session. For painting problems,
  try `QT_QPA_PLATFORM=xcb ./chopper` from the application folder and report whether
  that helps; this does not change the saved menu entry.

## Remove the shortcut

Use Dolphin to remove only the `chopper.desktop` shown by this installer, normally
under `~/.local/share/applications/`. Check that it is the Chopper-generated entry
(`X-Chopper-Generated=true`) before deleting it. No automatic uninstall removes
the application folder, Python, uv, system packages, settings, cache or samples.
Before manually removing an old application folder, check that it contains no
audio exports still used by a DAW project.

## First target-machine check

Record the actual Kubuntu version and CPU architecture (the terminal commands
`lsb_release -ds` and `uname -m` can help), then:

1. Install from a fresh extraction; verify that each requested destination is clear.
2. Skip the menu entry once: no shortcut should be created. Rerun installation
   and accept it; find Chopper in KDE's menu and open it without a terminal.
3. Analyze one of your tracks, including the first-use model download if needed.
4. Preview audio on your actual output device, mark a sample, and export it to a
   folder you choose. Confirm that the source audio is unchanged.
5. Close Chopper and reopen it from KDE. Check that the chosen library/settings
   are still available. Complete the [desktop/audio/DAW checks](FINAL_VALIDATION.md).

Report the version, architecture, error text and the step that failed. Do not
consider the Kubuntu target validated until these real checks have passed.
