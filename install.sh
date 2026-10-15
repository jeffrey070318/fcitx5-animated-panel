#!/usr/bin/env bash
set -euo pipefail
base="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 -m py_compile "$base/animated_panel.py"
echo "Dependencies are available. Run:"
echo "  env -u LD_LIBRARY_PATH -u LD_PRELOAD /usr/bin/python3 '$base/animated_panel.py'"
echo "Preview:"
echo "  /usr/bin/python3 '$base/animated_panel.py' --preview"
