#!/usr/bin/env bash
set -euo pipefail
base="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
env -u LD_LIBRARY_PATH -u LD_PRELOAD -u PYTHONPATH -u PYTHONHOME /usr/bin/python3 -c 'import dbus; from PyQt5 import QtWidgets'
if [[ "${1:-}" != --enable ]]; then
  echo "Dependencies OK. Preview: $base/run-session.sh --preview"
  echo 'Install and enable: ./install.sh --enable'
  exit 0
fi
install_dir="$HOME/.local/share/fcitx5-animated-panel"
mkdir -p "$install_dir" "$HOME/.config/systemd/user"
install -m 644 "$base/animated_panel.py" "$install_dir/animated_panel.py"
install -m 755 "$base/run-session.sh" "$install_dir/run-session.sh"
cat > "$HOME/.config/systemd/user/fcitx5-animated-panel.service" <<'UNIT'
[Unit]
Description=Animated Fcitx5 candidate panel
PartOf=graphical-session.target
After=graphical-session-pre.target

[Service]
Type=notify
ExecStart="%h/.local/share/fcitx5-animated-panel/run-session.sh"
WatchdogSec=5
TimeoutStartSec=10
TimeoutStopSec=3
Restart=no

[Install]
WantedBy=graphical-session.target
UNIT
systemctl --user import-environment DISPLAY XDG_RUNTIME_DIR DBUS_SESSION_BUS_ADDRESS
if [[ -n "${XAUTHORITY:-}" ]]; then systemctl --user import-environment XAUTHORITY; fi
systemctl --user daemon-reload
systemctl --user enable fcitx5-animated-panel.service
systemctl --user restart fcitx5-animated-panel.service
