# Installing Chopper on Kubuntu

Target for the first shared build: **Kubuntu 26.04.1**. Compatibility on a clean
target machine and its CPU architecture still needs the checks below. Isolated
installer tests are not proof of desktop, audio-driver or hardware compatibility.
The shareable ZIP contains Chopper's sources and installer, not its large runtime
dependencies. Send the matching `.zip.sha256` alongside it. `RELEASE.txt` inside
the archive identifies the source commit used to build it.

## Check the download

Keep the ZIP and its matching `.zip.sha256` file together. From a terminal in that
folder, check their integrity before extracting:

```bash
sha256sum -c -- chopper-*.zip.sha256
```

The archive must be reported as `OK`; otherwise do not install it and ask for a
fresh copy. A checksum detects accidental corruption, not a malicious sender
who replaces both files: only accept the pair from a trusted source.

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
6. A second optional prompt offers `~/.local/bin/chopper`, linked to this project's
   launcher. Read its destination and the local `.chopper-install.json` receipt
   location before agreeing. Declining/EOF creates neither a command nor a receipt
   for that action. Existing foreign, broken or manually recreated links are
   refused, even if their target matches the intended launcher.
7. A separate prompt offers the dedicated charcoal/orange SVG, normally at
   `~/.local/share/icons/hicolor/scalable/apps/chopper.svg`. Refusing it uses the
   system's generic audio icon in shortcuts generated during this run.
8. If `xdg-user-dir DESKTOP` identifies an existing desktop folder, the installer
   shows its exact `chopper.desktop` destination and asks separately before writing.
   It does not guess `~/Desktop`, create a desktop folder, or copy into HOME when
   the desktop is disabled. Missing XDG tools or invalid locations are reported
   without preventing the other integrations.

Once installed, find **Chopper** in KDE's application menu. If you skipped the
menu entry, open a terminal in the application folder and run `./chopper`.
The optional Desktop shortcut and menu entry use the same generated content and
absolute icon path, avoiding a KDE icon-cache refresh. The Desktop copy is
executable (0755), as required by KDE's desktop-file authorization checks. Local
administrative policies can still prevent execution; no GNOME-specific trust
metadata is added. Nothing adds autostart behavior.

All four integration choices are collected before writing; accepted integrations
are then installed independently, with the icon first. An error can leave earlier
accepted integrations installed; it never authorizes a declined destination.

## Run from any folder

If you accepted the global command, try:

```bash
cd /tmp
chopper
```

The global command is a symbolic link, so code updates in the same project
directory do not require copying a launcher again. Arguments, spaces and special
characters are preserved; the launcher finds the real project before using `.venv`.

The [official Ubuntu 26.04 profile](https://git.launchpad.net/ubuntu/+source/bash/plain/debian/skel.profile?h=ubuntu/resolute)
adds `~/.local/bin` at login **if that directory exists**. A session opened before
its creation may still lack it. The installer checks the original PATH, not a
temporary PATH it may use while installing uv. If warned, log out and back in.
For the current terminal only, you may instead run:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

No `.profile`, `.bashrc` or other profile is modified. A customized login setup
may need a separate, explicitly approved configuration change. If another command
shadows Chopper earlier on PATH, installation reports that path without changing it.
You can always use the project's `./chopper` directly.

## Internet, storage and your audio

The installed launcher does not run uv, synchronize packages, or download
dependencies. The first beat analysis may still download its model weights.
An entirely offline first installation or first analysis is not promised.

Keep the application folder: the shortcut points to its launcher and the Python
environment also depends on that location. For another location, use a fresh
extraction and run the installer there, then deliberately remove the old
integrations before accepting the new ones.
Do not simply move the already-installed `.venv` and expect it to work.

Chopper never changes your source audio. Preferences and analysis cache retain
their existing XDG locations. Samples exported or dragged into a DAW are separate
files that must stay available to that DAW. Repeated drags intentionally create
distinct permanent WAVs, even when a drop is canceled; installation does not
clean up samples, settings or old application folders.

## Retry or fix an integration

- If installation fails, read the terminal error and run `bash install.sh` again
  after resolving it. A dependency error is not reported as a completed install.
- If menu-entry creation fails after the local installation succeeded, `./chopper`
  is still usable. Fix the reported destination or permission problem, then rerun
  the installer. Do not run it with sudo to work around a home-folder error.
- The installer refuses an unrelated `./chopper` or `chopper.desktop`, including
  symbolic links. The global command accepts only its own recorded symlink. Menu
  ownership is recorded too; an old menu entry can be adopted only if its exact
  historical content points to this same launcher, not on its marker alone.
   Keep `.chopper-install.json` in the project folder. Move an unrelated
   conflicting file yourself only if you know what it is and want to keep it elsewhere.
- The icon and Desktop copy also require recorded ownership, even if a foreign
  file has identical bytes. Unchanged reinstalls preserve files and receipt;
  changing an owned icon or shortcut updates its recorded identity. If saving the
  receipt fails, a new file is removed only while it is still identifiable as ours;
  an updated file's previous content is restored from a preallocated backup.
  If even refreshing the restored identity fails (for example, a full disk), the
  error explicitly warns that further automatic changes will be refused safely.
  Parent folders created after consent may remain after an error; no recursive
  cleanup of user folders is performed.
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
   Test the separate icon/Desktop choices as well. The Desktop copy should use
   the same Chopper icon and launch the app without a terminal. Try `chopper`
   from another folder after accepting the global command and checking PATH.
3. Analyze one of your tracks, including the first-use model download if needed.
4. Preview audio on your actual output device, mark a sample, and export it to a
   folder you choose. Confirm that the source audio is unchanged.
5. Close Chopper and reopen it from KDE. Check that the chosen library/settings
   are still available. Complete the [desktop/audio/DAW checks](FINAL_VALIDATION.md).

Report the version, architecture, error text and the step that failed. Do not
consider the Kubuntu target validated until these real checks have passed.
