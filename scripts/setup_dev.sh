#!/usr/bin/env bash
set -euo pipefail

echo "=== Smart Traffic Development Setup ==="
[ -f .env ] || cp .env.example .env

cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cd ..

cd ml
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cd ..

cd frontend
npm install
cd ..

echo "Setup complete! Generate secrets with: python3 scripts/generate_secrets.py"
