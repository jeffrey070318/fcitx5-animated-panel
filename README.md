# Fcitx5 Animated Panel

Experimental Qt5/D-Bus candidate panel for Fcitx5 Kimpanel. It keeps the existing Rime engine and replaces only the presentation layer with a rounded, shadowed panel and a short fade-in animation.

## Current status

- Qt5 translucent rounded panel
- Drop shadow and fade-in animation
- Receives live Fcitx5 Kimpanel preedit, lookup table, cursor position, and visibility signals
- Candidate click signals are wired to Fcitx5
- Tested with the local Fcitx5 + Rime session; the panel receives live D-Bus events

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
