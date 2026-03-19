#!/usr/bin/env bash
set -euo pipefail

mkdir -p "$HOME/.agents/skills"
ln -sfn "$HOME/.codex/superpowers/skills" "$HOME/.agents/skills/superpowers"

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo "DevContainer ready."
echo "CODEX_HOME=$CODEX_HOME"
echo "superpowers skills link:"
ls -la "$HOME/.agents/skills"
