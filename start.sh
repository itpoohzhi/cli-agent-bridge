#!/usr/bin/env bash
# Запуск моста cli-agent-bridge (DSH). Параметры читаются каскадом
# BRIDGE_* -> DROID_DSH_BRIDGE_* -> умолчание (HOST, PORT, KEY, INSTR_LIMIT);
# ключ — из окружения или ~/.dsh/.env. Значения секретов не печатаются и не логируются.
# FACTORY_API_KEY необязателен: подхватывается из окружения/~/.zshenv, если есть
# (нужен только потомку `droid exec`), его отсутствие запуск не блокирует.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"

# Первое непустое из переданных имён переменных окружения; иначе — умолчание ($1).
_first() {
  local default="$1" name value
  shift
  for name in "$@"; do
    value="${!name:-}"
    if [[ -n "$value" ]]; then
      printf '%s' "$value"
      return 0
    fi
  done
  printf '%s' "$default"
}

export BRIDGE_HOST="$(_first 127.0.0.1 BRIDGE_HOST DROID_DSH_BRIDGE_HOST)"
export BRIDGE_PORT="$(_first 9882 BRIDGE_PORT DROID_DSH_BRIDGE_PORT)"
BRIDGE_INSTR_LIMIT="$(_first '' BRIDGE_INSTR_LIMIT DROID_DSH_BRIDGE_INSTR_LIMIT)"
# Предел блока валидирует сервер (b_guard.resolve_block_limit): пусто — умолчание 100000.
[[ -n "$BRIDGE_INSTR_LIMIT" ]] && export BRIDGE_INSTR_LIMIT
BRIDGE_KEY="$(_first '' BRIDGE_KEY DROID_DSH_BRIDGE_KEY)"
if [[ -z "$BRIDGE_KEY" && -f "$HOME/.dsh/.env" ]]; then
  for _name in BRIDGE_KEY DROID_DSH_BRIDGE_KEY; do
    _k="$(grep -E "^${_name}=" "$HOME/.dsh/.env" | tail -n 1 | cut -d= -f2- || true)"
    if [[ -n "$_k" ]]; then
      BRIDGE_KEY="$_k"
      break
    fi
  done
fi
: "${BRIDGE_KEY:?BRIDGE_KEY (or DROID_DSH_BRIDGE_KEY) is required}"
export BRIDGE_KEY
# Прежнее имя ключа в окружении сервера не нужно: канон — BRIDGE_KEY.
unset DROID_DSH_BRIDGE_KEY _k _name 2>/dev/null || true

# Необязательно: Factory-ключ для потомка `droid exec`. Источник — только ~/.zshenv
# (в ~/.dsh/.env секрет не дублируем: один секрет — один файл).
if [[ -z "${FACTORY_API_KEY:-}" && -f "$HOME/.zshenv" ]]; then
  _fk="$(grep -E '^[[:space:]]*export[[:space:]]+FACTORY_API_KEY=' "$HOME/.zshenv" \
    | tail -n 1 | cut -d= -f2- | tr -d '"'"'"'' | tr -d '[:space:]' || true)"
  [[ -n "$_fk" ]] && export FACTORY_API_KEY="$_fk"
fi
unset _fk 2>/dev/null || true
mkdir -p "$ROOT/logs" "$ROOT/workspace"
cd "$ROOT"
exec /usr/bin/python3 server.py
