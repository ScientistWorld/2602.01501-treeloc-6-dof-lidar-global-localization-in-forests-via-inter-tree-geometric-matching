#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
python redteam/hardening/shortcuts.py artifact_replay "$1" "$2"
