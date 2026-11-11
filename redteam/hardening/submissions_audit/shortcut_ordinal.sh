#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
python redteam/hardening/shortcuts.py ordinal "$1" "$2"
