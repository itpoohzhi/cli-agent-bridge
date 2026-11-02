PANEL-NONCE: 51520967746e7b93
ARTIFACT-SHA256: 8b703e9c4d5d73321cc4cf48a02a801ddc4f4e47d9c325c9a21a5e75d5c38cf6
PANEL-NONCE: 51520967746e7b93
ARTIFACT-SHA256: 8b703e9c4d5d73321cc4cf48a02a801ddc4f4e47d9c325c9a21a5e75d5c38cf6

AGREE RW-001 — проверил: `grep RetryPolicy|retry_policy` по `server.py`, `adapters/`, `core/*.py`, `bridges/` (кроме `core/resilience.py`) не нашёл ни одного вызова. `ResilienceManager.retry_policy()` (core/resilience.py:745) никто не вызывает. Ретраи `for attempt in (1, 2, 3)` с `_sleep(2 * attempt)` (server.py:5304, 5508) остались прежними, только для droid. Флаги `RETRY_*` и пакет, который заявляет exponential backoff, ничего не делают.

AGREE RW-002 — проверил: `adapters/passthrough_adapter.py:1194` вызывает `sink.start(200, …)`, и `sink.status` навсегда остаётся 200. Дальше `except (socket.timeout, OSError, HTTPException)` на 1207 пишет error-кадр и делает `return`. `outcome.incomplete`/`overflow` только логируются. В `_serve_passthrough` (server.py:6924-6929) условие `0 < sink.status < 500` даёт `record_success()`. Обрыв upstream посреди SSE считается успехом: сбрасывает счётчик сбоев и закрывает `HALF_OPEN`.

AMEND RW-003 — priority=MAJOR, не BLOCKER; fix=для не-attach путей брать `RESILIENCE.acquire` до `create_or_attach_turn`, а `preflight()` нейтрально учитывать или отражать в `/v1/resilience` — причина: preflight (server.py:6353) и `create_or_attach_turn` (6452) идут до `_serve_resilient` (6528). Утечки хода нет: `finally` на 6537 вызывает `finalize_abandoned_turn`. Остаётся лишняя регистрация хода и слота TURN_MANAGER при открытом брейкере, то есть DoS-амплификация на уровне состояния. Отказ preflight по `launcher_unavailable` не учитывается брейкером. Для fail-fast это дефект порядка, а не потеря данных или безопасности.

AMEND RW-004 — priority=MAJOR, не BLOCKER; fix=передавать `backend_limits` из `fleet.json` в `ResilienceManager(...)` и при смене ёмкости переносить `active` в новый `Bulkhead` (или перенаправлять release) — причина: `RESILIENCE = ResilienceManager()` (server.py:524) без лимитов, а `fleet.json:58,65` задаёт `max_concurrent` 4 и 1. `_bulkhead_for` (core/resilience.py:782-784) при `capacity` != текущей создаёт новый `Bulkhead` с `active=0`. `BulkheadLease` держит ссылку на старый объект, поэтому underflow нет. Но во время горячей смены возможна временная сверхадмиссия (старые + новые слоты), а `active` в `/v1/resilience` занижается.

AGREE RW-005 — проверил: server.py:7089, 7214, 7234 и 7247 при `_client_write_dead` или `client_gone` вызывают `lease.record_discard("client_disconnected")` и делают `return`. В случае `detach_on_disconnect` (7090, 7215) управляемый ход продолжает работать (`mark_detached`). `with lease:` в `_serve_resilient` на выходе освобождает слот Bulkhead и пробу `HALF_OPEN`, пока бэкенд ещё выполняет работу. Реальный исход detached-хода (`rc`/ошибка) в брейкер не попадает. Слот отсека занижается относительно реальной нагрузки. Проба `HALF_OPEN` освобождается без результата, и можно пустить следующую пробу в ещё занятый бэкенд.

VERDICT: NEEDS WORK
