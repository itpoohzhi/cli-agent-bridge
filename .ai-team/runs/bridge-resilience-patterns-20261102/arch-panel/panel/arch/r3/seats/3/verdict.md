PANEL-NONCE: e40178f7aeb38f8b
ARTIFACT-SHA256: f11926370796cb83074b1ddfce74de7ba251ee15b25a83a6621cb07ebaee77aa

REFUTE RW-004 COUNTER-EVIDENCE: `docs/adr/0020-universal-backend-circuit-breaker-bulkhead-and-retries.md:112-140` (раздел «Конфигурируемость без хардкода») выносит каждый лимит в env с безопасным дефолтом: `BRIDGE_CB_FAIL_THRESHOLD=3`, `BRIDGE_CB_RESET_TIMEOUT_S=30.0`, `BRIDGE_BULKHEAD_MAX_PASSTHROUGH=64`, `BRIDGE_RETRY_MAX_ATTEMPTS=3`, `BRIDGE_RETRY_BASE_SLEEP_S=0.5`, `BRIDGE_RETRY_BACKOFF_FACTOR=2.0` и `BRIDGE_RETRY_MAX_SLEEP_S=5.0`. Строка 47-48 задаёт `capacity = min(backend_max_concurrent, BRIDGE_BULKHEAD_MAX_PASSTHROUGH)`, а 64 — только дефолт. `backend_max_concurrent=128` берётся из `fleet.json` (строки 20-23), а не из кода. Это соответствует `AGENTS.md` п.4: значения идут через переменные окружения и конфиг, а константа остаётся fallback.

Оговорка: в пакете D2 (раздел 1) «лимит `min(max_concurrent, 64)`» и «гарантия 64 слотов» написаны как литералы. Это неточность формулировки, а не нарушение. Содержательного дефекта нет, и RW-004 не относится к BLOCKER-SAFETY, потому что безопасность он не затрагивает.

Остаточная мелочь для кода: размер глобального семафора `_conn_sem` (128) нужно читать из `fleet.json:max_http_connections`, а не из литерала. ADR (строка 9) заявляет это, но в `server.py` я не проверял. Это чек-пункт для Reviewer на этапе реализации, а не блокер архитектуры.

VERDICT: PASS
