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
BRIDGE_MAX_CONCURRENT="${BRIDGE_MAX_CONCURRENT:-${DROID_DSH_BRIDGE_MAX_CONCURRENT:-}}"
export BRIDGE_MAX_CONCURRENT="${BRIDGE_MAX_CONCURRENT:-128}"
export BRIDGE_MAX_HTTP_CONNECTIONS="${BRIDGE_MAX_HTTP_CONNECTIONS:-128}"
BRIDGE_INSTR_LIMIT="$(_first '' BRIDGE_INSTR_LIMIT DROID_DSH_BRIDGE_INSTR_LIMIT)"
# Предел блока валидирует сервер (b_guard.resolve_block_limit): пусто — умолчание 100000.
[[ -n "$BRIDGE_INSTR_LIMIT" ]] && export BRIDGE_INSTR_LIMIT
BRIDGE_KEY="${BRIDGE_KEY:-${DROID_DSH_BRIDGE_KEY:-}}"
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

# Родные ключи upstream: окружение имеет приоритет, .env читается без исполнения.
if [[ -f "$HOME/.dsh/.env" ]]; then
  for _name in CLAUDE_P_BRIDGE_KEY AGY_BRIDGE_KEY OPENCODE_ZEN_BRIDGE_KEY CODEX_LB_API_KEY; do
    if [[ -n "${!_name+x}" ]]; then
      continue
    fi
    _k="$(grep -E "^[[:space:]]*(export[[:space:]]+)?${_name}=" "$HOME/.dsh/.env" \
      | tail -n 1 | cut -d= -f2- || true)"
    _k="${_k%$'\r'}"
    if [[ "$_k" == \"*\" || "$_k" == \'*\' ]]; then
      _k="${_k:1:${#_k}-2}"
    fi
    if [[ -n "$_k" ]]; then
      export "$_name=$_k"
    fi
  done
  # Подгружаем все BRIDGE_* переменные конфигурации из ~/.dsh/.env (если не переопределены)
  while IFS='=' read -r _bkey _bval || [[ -n "$_bkey" ]]; do
    _bkey="$(echo "$_bkey" | sed -E 's/^[[:space:]]*(export[[:space:]]+)?//;s/[[:space:]]*$//')"
    if [[ "$_bkey" =~ ^BRIDGE_[A-Za-z0-9_]+$ && -z "${!_bkey+x}" ]]; then
      _bval="${_bval%$'\r'}"
      _bval="$(echo "$_bval" | sed -E 's/^[[:space:]]*["'"'"']?//;s/["'"'"']?[[:space:]]*$//')"
      export "$_bkey=$_bval"
    fi
  done < <(grep -E '^[[:space:]]*(export[[:space:]]+)?BRIDGE_[A-Za-z0-9_]+=' "$HOME/.dsh/.env" || true)
fi
unset _k _name _bkey _bval 2>/dev/null || true
export BRIDGE_NONSTREAM_FIRST_PROGRESS_TIMEOUT_S="${BRIDGE_NONSTREAM_FIRST_PROGRESS_TIMEOUT_S:-300}"

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
# ADR-0015: invalid BRIDGE_CLI_*/BRIDGE_NONSTREAM_*/BRIDGE_WATCHDOG_* config -> exit 78
"${PYTHON_BIN:-$HOME/.local/bin/python3}" -c 'from core.cli_runtime_config import CliRuntimeConfig as C, NonstreamConfig as N, WatchdogConfig as W; C.from_env(); N.from_env(); W.from_env()' || exit 78
exec "${PYTHON_BIN:-$HOME/.local/bin/python3}" server.py
