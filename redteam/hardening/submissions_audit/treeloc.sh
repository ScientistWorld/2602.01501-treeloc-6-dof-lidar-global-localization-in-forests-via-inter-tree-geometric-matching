#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
python method/treeloc.py --input "$1" --output "$2"
