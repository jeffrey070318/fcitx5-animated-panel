# Fcitx5 Animated Panel

Experimental Qt5/D-Bus candidate panel for Fcitx5 Kimpanel. It keeps the existing Rime engine and replaces only the presentation layer with a rounded, shadowed panel and a short fade-in animation.

## Current status

- Qt5 translucent rounded panel
- Drop shadow and fade-in animation
- Receives live Fcitx5 Kimpanel preedit, lookup table, cursor position, and visibility signals
- Candidate click signals are wired to Fcitx5
- Tested with the local Fcitx5 + Rime session; the panel receives live D-Bus events

## Dependencies

Use the distro Python, rather than an Anaconda Python, so Qt and D-Bus libraries
resolve against Ubuntu's system libraries. On Ubuntu:

```bash
sudo apt install python3-pyqt5 python3-dbus python3-gi gir1.2-glib-2.0
```

## Run

```bash
env -u LD_LIBRARY_PATH -u LD_PRELOAD -u PYTHONPATH -u PYTHONHOME \
  /usr/bin/python3 animated_panel.py
```

Preview without Fcitx5 integration:

```bash
/usr/bin/python3 animated_panel.py --preview
```

This is an experimental frontend. Stop it and restart Fcitx5 to return to classicui.

`install.sh` only checks the local Python dependencies; it does not replace the
system Fcitx5 UI or change the current input method configuration.
