PANEL-NONCE: e10dce6b1e4b7b17
ARTIFACT-SHA256: 8b703e9c4d5d73321cc4cf48a02a801ddc4f4e47d9c325c9a21a5e75d5c38cf6
Проверю пять находок по исходникам и укажу точные строки.

Канон `~/Мой диск/Context/AGENTS.md` прочитан до `<!-- КАНОН-КОНЕЦ -->`; проектный `~/work/src/cli-agent-bridge/AGENTS.md` прочитан. В исходниках подтверждаются потеря исхода SSE и создание ManagedTurn до допуска. Проверю отдельно, когда при отсоединении клиента освобождается проба HALF_OPEN.

PANEL-NONCE: e10dce6b1e4b7b17
ARTIFACT-SHA256: 8b703e9c4d5d73321cc4cf48a02a801ddc4f4e47d9c325c9a21a5e75d5c38cf6
AGREE RW-001 — проверил: core/resilience.py:745, server.py:5304, server.py:5508 — retry_policy() не вызывается из фасада и адаптеров; прежние три попытки и линейный сон 2 * attempt не управляются новой политикой.
AGREE RW-002 — проверил: adapters/passthrough_adapter.py:1194, adapters/passthrough_adapter.py:1206, server.py:6926 — после HTTP 200 ошибка upstream превращается в SSE error-frame без передачи исхода фасаду; сохранённый status=200 вызывает record_success().
AGREE RW-003 — проверил: server.py:6353, server.py:6452, server.py:6528 — preflight и создание ManagedTurn предшествуют допуску; отказ preflight возвращает 503 без Retry-After, обходя обработчик ResilienceError.
AGREE RW-004 — проверил: server.py:524, core/resilience.py:774, core/resilience.py:782 — backend_limits не переданы; изменение ёмкости заменяет Bulkhead новым семафором, позволяя новые захваты без учёта ещё активных старых слотов.
AGREE RW-005 — проверил: server.py:7214, server.py:7222, server.py:7247, core/resilience.py:675, core/resilience.py:495 — discard до продолжающегося detached-выполнения освобождает пробу HALF_OPEN и окончательно фиксирует исход lease; последующий результат теряется, а _client_write_dead также подавляет учёт ошибки бэкенда.
VERDICT: NEEDS WORK
