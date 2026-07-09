#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"
if [[ ! -f .venv/bin/activate ]]; then
    echo "Ambiente virtual ausente. Crie com: python3 -m venv .venv"
    exit 1
fi
source .venv/bin/activate
exec streamlit run 06_app/app.py
