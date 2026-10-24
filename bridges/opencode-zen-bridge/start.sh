#!/usr/bin/env bash
# Запуск моста opencode-zen-bridge (DSH). Ключ читается из окружения или ~/.dsh/.env.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"
export OPENCODE_ZEN_BRIDGE_HOST="${OPENCODE_ZEN_BRIDGE_HOST:-127.0.0.1}"
export OPENCODE_ZEN_BRIDGE_PORT="${OPENCODE_ZEN_BRIDGE_PORT:-9883}"
if [[ -z "${OPENCODE_ZEN_BRIDGE_KEY:-}" && -f "$HOME/.dsh/.env" ]]; then
  _k="$(grep -E '^OPENCODE_ZEN_BRIDGE_KEY=' "$HOME/.dsh/.env" | cut -d= -f2- || true)"
  [[ -n "$_k" ]] && export OPENCODE_ZEN_BRIDGE_KEY="$_k"
fi
for _name in OPENCODE_API_KEY OPENCODE_GO_API_KEY; do
  if [[ -z "${!_name:-}" && -f "$HOME/.dsh/.env" ]]; then
    _k="$(grep -E "^${_name}=" "$HOME/.dsh/.env" | cut -d= -f2- || true)"
    [[ -n "$_k" ]] && export "$_name=$_k"
  fi
done
unset _k _name
: "${OPENCODE_ZEN_BRIDGE_KEY:?OPENCODE_ZEN_BRIDGE_KEY is required}"

# Zen standalone ходит через ротирующий US-пул (1000 портов ProxyRack, свой чистый IP на порт):
# фиксированный IP упирается в дневной анонимный лимит opencode.ai (429 FreeUsageLimitError).
# Резерв — локальный форвардер 127.0.0.1:10816 (статический IP).
_PROXYRACK_POOL_FILE="$HOME/.local/share/gigaexplorator-proxies/2026-08-31-volkov-proxy-manager/06-proxyrack-global-dc-1000.txt"
if [[ -z "${OPENCODE_ZEN_BRIDGE_STANDALONE_PROXY:-}" ]]; then
  if [[ -s "$_PROXYRACK_POOL_FILE" ]]; then
    echo "[start.sh] using rotating ProxyRack pool (1000 US ports) for standalone" >&2
    export OPENCODE_ZEN_BRIDGE_STANDALONE_PROXY="pool"
  elif /usr/bin/nc -z 127.0.0.1 10816 >/dev/null 2>&1; then
    echo "opencode-zen-bridge: using rotating proxy http://127.0.0.1:10816 for standalone" >&2
    export OPENCODE_ZEN_BRIDGE_STANDALONE_PROXY="http://127.0.0.1:10816"
  else
    echo "opencode-zen-bridge: WARN 127.0.0.1:10816 not listening, using default proxy from env" >&2
  fi
fi
mkdir -p "$ROOT/logs" "$ROOT/workspace"
cd "$ROOT"

# Синхронизация каталога Zen (api.json -> кэш CLI, state/zen-catalog.json, профили DSH).
# Ошибка/недоступность сети старт моста не блокирует: мост работает на последнем каталоге
# или встроенном снимке. Ждём не дольше 40 с; запоздавший синк доработает в фоне (flock).
# Отключить: OPENCODE_ZEN_BRIDGE_SYNC=0.
if [[ "${OPENCODE_ZEN_BRIDGE_SYNC:-1}" != "0" && -f "$ROOT/sync_dsh_models.py" ]]; then
  /usr/bin/python3 "$ROOT/sync_dsh_models.py" >>"$ROOT/logs/sync.log" 2>&1 &
  _sync_pid=$!
  _waited=0
  while kill -0 "$_sync_pid" 2>/dev/null && [[ "$_waited" -lt 40 ]]; do
    sleep 1
    _waited=$((_waited + 1))
  done
  if ! kill -0 "$_sync_pid" 2>/dev/null; then
    wait "$_sync_pid" || echo "zen-autosync: sync exited rc=$? (bridge starts anyway)" >&2
  else
    echo "zen-autosync: sync still running after ${_waited}s (bridge starts anyway)" >&2
  fi
  unset _sync_pid _waited
fi

exec /usr/bin/python3 server.py
