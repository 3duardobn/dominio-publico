#!/usr/bin/env bash
# Setup: cria .venv e instala dependências. Rode 1x após o git clone.
# Uso: ./setup.sh [--with-browser]
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  python3 -m venv .venv
  echo "[setup] venv criado em .venv/"
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt

if [ "${1:-}" = "--with-browser" ]; then
  pip install -r requirements-optional.txt
  python3 -m playwright install chrome
  echo "[setup] Chromium instalado (fallback --playwright liberado)"
fi

echo "[setup] OK. Ative com: source .venv/bin/activate"
