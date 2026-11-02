PANEL-NONCE: 5de0bdc4555c0812
ARTIFACT-SHA256: 9ea833eaa5cf7579802e170f25ad5b1da3f3b5477de1aed1134370b052b65f4e

AMEND RW-001 — priority=major (не BLOCKER-SAFETY); fix=до первого полезного токена считать окно от `start_time` с отдельным `BRIDGE_FIRST_TOKEN_TIMEOUT_S` (дефолт = `total_timeout_s`, т.е. прежний TTFT-бюджет), а `last_upstream` не продлевает его — причина: `adapters/passthrough_adapter.py:700-702,724` (`last_progress is None` → база `last_upstream`, сбрасывается любой непустой строкой, включая role-кадр и `: keepalive`). Из-за этого TTFT ограничен только `safety_cap_s=3600`, а комментарий на `:889` («TTFT защищён») перестаёт быть правдой.

DISPUTE RW-006 — контр-evidence: `adapters/passthrough_adapter.py:1429` — `conn.sock.settimeout(min(read_timeout_s, remaining))` задаёт таймаут на каждый `recv`, а не накопительный настенный. Пока апстрим шлёт данные чаще ~420 с, сокет живёт. Watcher после `streaming.set()` (`:1271-1276,1366`) настенный дедлайн не применяет. Idle по умолчанию 300 с меньше 420 с, поэтому первым срабатывает idle ридера. Утверждение «старый total timeout продолжает ограничивать чтение» верно только как связка конфигов (см. RW-002), на дефолтах 420-секундного обрыва активного стрима нет.

AMEND RW-002 — priority=major; fix=после `streaming.set()` выставлять `sock.settimeout(max(idle_timeout_s, poll_interval_s))` и добавить один тест на реальном сокете (локальный `http.server` с SSE, чанки каждые меньше idle, суммарно больше `total_timeout_s`) — причина: `adapters/passthrough_adapter.py:1422-1429` (таймаут сокета выведен из `total_timeout_s`, и при `BRIDGE_IDLE_TIMEOUT_S` > остатка `total_timeout_s` он молча урезает idle). Новые тесты `tests/test_stream_resilience.py:1083,1106` синтетические (`paced_readline`) и сокет не проходят, поэтому сквозного доказательства исправления инцидента с PI_AI_ERROR на 420 с нет.

AMEND RW-007 — priority=major; fix=то же, что в RW-001: keepalive-комментарии (`:` и пустые строки) не обновляют `last_upstream` до первого полезного чанка, плюс тест «только upstream-keepalive → TimeoutError раньше `safety_cap_s`» — причина: `adapters/passthrough_adapter.py:724` (строка `: keepalive` от апстрима непустая и продлевает окно). Дубль RW-001, чинится одной правкой.

VERDICT: NEEDS WORK
