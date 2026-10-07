#!/usr/bin/env bash
# Запуск моста droid-bridge (DSH). Ключ читается из окружения или ~/.dsh/.env.
# FACTORY_API_KEY (headless-вход Droid без интерактивного логина) читается из
# окружения, затем из ~/.zshenv — значение не печатается и не логируется.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"
export DROID_DSH_BRIDGE_HOST="${DROID_DSH_BRIDGE_HOST:-127.0.0.1}"
export DROID_DSH_BRIDGE_PORT="${DROID_DSH_BRIDGE_PORT:-9882}"
if [[ -z "${DROID_DSH_BRIDGE_KEY:-}" && -f "$HOME/.dsh/.env" ]]; then
  _k="$(grep -E '^DROID_DSH_BRIDGE_KEY=' "$HOME/.dsh/.env" | cut -d= -f2- || true)"
  [[ -n "$_k" ]] && export DROID_DSH_BRIDGE_KEY="$_k"
fi
: "${DROID_DSH_BRIDGE_KEY:?DROID_DSH_BRIDGE_KEY is required}"
# Factory-ключ нужен потомку `droid exec` (через _launch_env). Источник — только
# ~/.zshenv: в ~/.dsh/.env секрет не дублируем (канон: один секрет — один файл).
if [[ -z "${FACTORY_API_KEY:-}" && -f "$HOME/.zshenv" ]]; then
  _fk="$(grep -E '^[[:space:]]*export[[:space:]]+FACTORY_API_KEY=' "$HOME/.zshenv" \
    | tail -n 1 | cut -d= -f2- | tr -d '"'"'"'' | tr -d '[:space:]' || true)"
  [[ -n "$_fk" ]] && export FACTORY_API_KEY="$_fk"
fi
unset _fk 2>/dev/null || true
mkdir -p "$ROOT/logs" "$ROOT/workspace"
cd "$ROOT"
exec /usr/bin/python3 server.py
