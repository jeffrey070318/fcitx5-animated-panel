#!/usr/bin/env bash
set -euo pipefail
base="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Owning org.kde.impanel activates kimpanel. Exiting restores classicui.
# Never disable classicui, restart Fcitx5, or edit the user's input settings.
exec env -u LD_LIBRARY_PATH -u LD_PRELOAD -u PYTHONPATH -u PYTHONHOME -u QT_PLUGIN_PATH -u QT_QPA_PLATFORM_PLUGIN_PATH QT_QPA_PLATFORM=xcb /usr/bin/python3 "$base/animated_panel.py" "$@"
