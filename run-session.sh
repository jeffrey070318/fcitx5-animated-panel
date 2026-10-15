#!/usr/bin/env bash
set -euo pipefail
base="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-xcb}"
restore() { pkill -P $$ -x fcitx5 2>/dev/null || true; env -u LD_LIBRARY_PATH -u LD_PRELOAD -u PYTHONPATH -u PYTHONHOME fcitx5 -d >/dev/null 2>&1 || true; }
trap restore EXIT INT TERM
env -u LD_LIBRARY_PATH -u LD_PRELOAD -u PYTHONPATH -u PYTHONHOME /usr/bin/python3 "$base/animated_panel.py" >/tmp/fcitx5-animated-panel.log 2>&1 &
panel_pid=$!
for _ in $(seq 1 30); do kill -0 "$panel_pid" 2>/dev/null || { echo 'animated panel exited; see /tmp/fcitx5-animated-panel.log' >&2; exit 1; }; sleep .1; done
pkill -u "$USER" -x fcitx5 2>/dev/null || true
env -u LD_LIBRARY_PATH -u LD_PRELOAD -u PYTHONPATH -u PYTHONHOME fcitx5 --disable classicui --ui kimpanel -d
