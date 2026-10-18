#!/usr/bin/env bash
# Запуск моста agy-bridge (DSH → Antigravity CLI `agy`).
# Ключ читается из окружения или ~/.dsh/.env; значение не печатается и не логируется.
# Транспорт — канонический лончер ~/.config/agy-launch/agy-cli.sh (egress-пиннинг
# Амстердам :10815, резерв hy2 :10811; прямой вызов запрещён — гео РФ).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"
export AGY_BRIDGE_HOST="${AGY_BRIDGE_HOST:-127.0.0.1}"
export AGY_BRIDGE_PORT="${AGY_BRIDGE_PORT:-9887}"
if [[ -z "${AGY_BRIDGE_KEY:-}" && -f "$HOME/.dsh/.env" ]]; then
  _k="$(grep -E '^AGY_BRIDGE_KEY=' "$HOME/.dsh/.env" | cut -d= -f2- || true)"
  [[ -n "$_k" ]] && export AGY_BRIDGE_KEY="$_k"
fi
: "${AGY_BRIDGE_KEY:?AGY_BRIDGE_KEY is required}"
unset _k 2>/dev/null || true
# core.watchdog живёт в корне репозитория cli-agent-bridge: при симлинке деплоя server.py
# находит его сам (parents[2]); PYTHONPATH — страховка на случай копии вместо симлинка.
REPO_ROOT="${CLI_AGENT_BRIDGE_ROOT:-$HOME/work/src/cli-agent-bridge}"
export PYTHONPATH="$REPO_ROOT${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p "$ROOT/logs" "$ROOT/workspace"
cd "$ROOT"
exec /usr/bin/python3 server.py
