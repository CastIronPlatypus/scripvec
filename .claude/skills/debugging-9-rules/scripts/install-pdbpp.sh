#!/usr/bin/env bash
# install-pdbpp.sh
#
# Install pdb++ into the active Python environment and drop a sane
# default ~/.pdbrc.py if one isn't already there.
#
# Usage:
#   ./install-pdbpp.sh             # installs into current python -m pip target
#   ./install-pdbpp.sh --user      # installs into user site-packages
#   PIP=uv ./install-pdbpp.sh      # use a different installer (e.g. uv pip)

set -euo pipefail

PIP="${PIP:-pip}"
EXTRA_ARGS=()

if [[ "${1:-}" == "--user" ]]; then
  EXTRA_ARGS+=(--user)
fi

echo "[install-pdbpp] Installing pdbpp via $PIP ..."
"$PIP" install "${EXTRA_ARGS[@]}" pdbpp

PDBRC="${HOME}/.pdbrc.py"
if [[ -f "$PDBRC" ]]; then
  echo "[install-pdbpp] $PDBRC already exists; leaving it alone."
else
  echo "[install-pdbpp] Writing baseline $PDBRC ..."
  cat > "$PDBRC" <<'EOF'
# ~/.pdbrc.py — pdb++ configuration
# https://pypi.org/project/pdbpp/

import pdb

class Config(pdb.DefaultConfig):
    sticky_by_default = True       # always show source pane at the prompt
    use_pygments = True            # syntax highlighting
    truncate_long_lines = False
    bg = 'dark'                    # 'dark' or 'light' — pick based on terminal
    current_line_color = 40        # ANSI bg color for the current line
EOF
fi

echo "[install-pdbpp] Done."
echo
echo "Drop a breakpoint() in your code and run the script normally."
echo "See branches/tool-pdbpp-scripts.md for usage."
