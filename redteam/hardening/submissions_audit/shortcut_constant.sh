#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
python redteam/hardening/shortcuts.py constant "$1" "$2"
