#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
python redteam/hardening/shortcuts.py forge_scores "$1" "$2"
