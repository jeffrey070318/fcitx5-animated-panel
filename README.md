# Fcitx5 Animated Panel

An X11 candidate frontend for Fcitx5, with a rounded dark panel, subtle shadow,
115 ms fade-in and 100 ms fade-out, with a short 24 ms hide debounce.
Rime continues to handle input, dictionaries,
Shift switching and learned word frequencies. This is an independent project,
not affiliated with WeChat.

## Interaction

- Reuse candidate buttons rather than destroy/recreate them on every key.
- Coalesce text, position and visibility messages within the Qt event loop.
- Do not replay fade-in while typing; reverse an interrupted fade smoothly.
- Ease panel growth over 135 ms; wait 90 ms before a 155 ms shrink transition.
- Retain the last complete candidate frame throughout fade-out.
- Keep glyphs at their native size while the background expands around them.
- Share a precise timer across opacity, reveal and size animations, using the
  caret screen's reported refresh rate (about 4 ms at 240 Hz). Follow screen and
  refresh-rate changes; stop the timer whenever all transitions finish.
- Advance animations by monotonic elapsed time so delayed frames do not stretch
  the transition duration. This timer is not synchronized to compositor vsync
  and does not guarantee a particular displayed frame rate.
- Track the caret immediately; do not add movement interpolation/input delay.
- Handle the real `org.kde.impanel2.SetLookupTable` and `SetSpotRect` methods.
- Candidate selection and page buttons use the `org.kde.impanel` signals.
- Never record entered text in application logs.

## Requirements

Tested on Ubuntu 22.04 / GNOME X11, Fcitx5 5.0.14, Rime 1.7.3, system Python
and Qt5 with GLib event integration. A compositor is needed for opacity effects.
Wayland and arbitrary Qt event dispatchers are not supported by this version.

```bash
sudo apt install fcitx5 python3-pyqt5 python3-dbus
```

Use Ubuntu's Python and Qt libraries, not an Anaconda runtime. The runner clears
common library/plugin overrides.

## Try and install

Preview (does not take over input):

```bash
./run-session.sh --preview
```

Temporary frontend (Ctrl+C exits):

```bash
./run-session.sh
```

Install into `~/.local/share/fcitx5-animated-panel` and enable for graphical login:

```bash
./install.sh --enable
```

The user service owns `org.kde.impanel`, which makes Fcitx5 choose its Kimpanel
adapter. It does **not** disable classicui, restart Fcitx5 or edit Rime settings.
A conflicting existing panel makes startup fail rather than replace it.

A systemd watchdog terminates an unresponsive frontend after approximately five
seconds. Losing the bus name makes Fcitx5 automatically return to classicui.
The service does not restart on failure, preventing repeated takeover failures.

Stop and disable autostart:

```bash
./uninstall.sh
```

This keeps installed files for recovery. The same can be done directly:

```bash
systemctl --user disable --now fcitx5-animated-panel.service
```

After editing source, run `./install.sh --enable` to update the installed copy.

## Validation

```bash
env -u LD_LIBRARY_PATH -u PYTHONPATH -u PYTHONHOME \
  /usr/bin/python3 -m unittest test_panel.py
env -u LD_LIBRARY_PATH -u PYTHONPATH -u PYTHONHOME dbus-run-session -- \
  /usr/bin/python3 test_bus.py "$PWD/animated_panel.py"
```

Seventeen tests cover button reuse, opacity continuity, auxiliary visibility,
fade reversal, selection indices, screen placement, size transitions, retained
exit content, duplicate caret updates, refresh-rate changes, idle timer shutdown
and progress after a delayed frame. The isolated D-Bus test
checks the real method signatures and release of frontend ownership.

Local desktop validation also exercised a dedicated IBus input context backed
by the real Fcitx5/Rime: `jisuanji` produced seven candidates and selecting the
first committed `计算机`. Stopping the panel restored `classicui`; a deliberately
stalled service was stopped by the watchdog and also restored `classicui`.
These checks validate functionality, not refresh-rate/frame-time performance.
Login autostart still needs observation at the next graphical login.
