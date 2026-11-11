#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
python baseline/tdh_baseline.py --input "$1" --output "$2"
