#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
python method/treeloc.py --input "$1" --output "$2" --top-tdh 0 --top-hash 0
