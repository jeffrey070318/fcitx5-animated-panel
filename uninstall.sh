#!/usr/bin/env bash
set -euo pipefail
# Leave installed files for reversible recovery. No input configuration is changed.
systemctl --user disable --now fcitx5-animated-panel.service
printf '%s\n' 'Animated panel disabled. Fcitx5 automatically returns to classicui.'
