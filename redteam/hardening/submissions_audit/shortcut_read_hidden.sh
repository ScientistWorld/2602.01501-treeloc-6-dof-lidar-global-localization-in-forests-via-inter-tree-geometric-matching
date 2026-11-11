#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
python redteam/hardening/shortcuts.py read_hidden "$1" "$2"
