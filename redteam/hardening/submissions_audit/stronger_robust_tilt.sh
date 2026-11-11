#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
python redteam/hardening/treeloc_robust.py --input "$1" --output "$2" --tilt
