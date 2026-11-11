#!/bin/bash
set -euo pipefail
cd /home/user
python redteam/harness.py all
python redteam/analyze.py
