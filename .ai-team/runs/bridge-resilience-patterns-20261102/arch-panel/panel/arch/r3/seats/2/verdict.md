PANEL-NONCE: 3596a9229b2ba700
ARTIFACT-SHA256: f11926370796cb83074b1ddfce74de7ba251ee15b25a83a6621cb07ebaee77aa
AMEND RW-004 — priority=BLOCKER-OPINION; fix=синхронизировать формулу Bulkhead в пакете с конфигурируемым пределом ADR — причина: seats/2/brief.md:26 задаёт `min(max_concurrent, 64)`, тогда как docs/adr/0020-universal-backend-circuit-breaker-bulkhead-and-retries.md:47 использует `BRIDGE_BULKHEAD_MAX_PASSTHROUGH`; доказано противоречие спецификаций, хардкод реализации не установлен.
VERDICT: NEEDS WORK
