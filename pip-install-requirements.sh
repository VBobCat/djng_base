#!/usr/bin/env bash
# set -euo pipefail

# Save current directory and switch to script's own directory
# -------------------------------------------------------------------
ORIG_DIR="$(pwd)"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK_DIR="$SCRIPT_DIR/backend"
[ -d "$WORK_DIR" ] || { echo "Directory not found: $WORK_DIR"; exit 1; }
cd "$WORK_DIR"

echo
echo "Install/update devtools (pip setuptools pipdeptree)..."
echo "======================================================"
python -m pip install --upgrade --upgrade-strategy eager pip setuptools pipdeptree colorama isort ssort wheel

echo
echo "Install/update requirements (-r requirements.txt)..."
echo "===================================================="
python -m pip install --upgrade --upgrade-strategy eager -r requirements.txt

echo
echo "Check broken dependencies..."
echo "============================"
pip check

echo
echo "List remaining outdated packages (may be pinned by other packages)..."
echo "====================================================================="
pip list -o

cd "$ORIG_DIR"
