# consensus-ledger.md — снимок после R1 (prior-ledger следующего раунда)

- round_dir: r1
- artifact_sha256: f602786d011d752b1cf1a90e2241ecfa65c6dd6149bd9034a4f852156c94ddc2

## Места

- seat 1: slot=muse-wonder-full-1.0 family=Meta nonce=4d23c2aa4bfcbe96 verdict_sha256=7dd80c944e0a2d0683213c19e17768d6fcf072ed232fb0e9265d42e5b66daaed
- seat 2: slot=gemini-4-argon-high family=Google nonce=0cd61720346b2978 verdict_sha256=576e33cfe7e14447f934383b869e8876d3e8e44193b7aab5cf2fceec793447df
- seat 3: slot=claude-sonnet-5-5-high family=Anthropic nonce=50c6e7d91aa7227a verdict_sha256=be7e89bada00de1bd9938df3c933e2ae5f9a7bcb4efd03e6499dbf9575bb1e88

## Находки

### F-001
- class: BLOCKER-OPINION
- status: OPEN
- votes: {}
- text: RW-001 BLOCKER-OPINION — в пакет санитайзера включён нетрассированный релакс строгого контракта `reasoning_effort` (clamp вместо 400), а «Full Git Diff» пакета опускает переписанные под него тесты

### F-002
- class: BLOCKER-OPINION
- status: OPEN
- votes: {}
- text: RW-002 BLOCKER-OPINION — schema-aware очистка в интегрированном поведении мертва: `tool_schemas` не передаёт ни одна прод-точка

### F-003
- class: BLOCKER-OPINION
- status: OPEN
- votes: {}
- text: RW-003 BLOCKER-OPINION — заявление «Required properties keep empty strings» противоречит коду для route-полей и justification

### F-004
- class: BLOCKER-OPINION
- status: OPEN
- votes: {}
- text: RW-004 BLOCKER-OPINION — мост фабрикует `justification` для вызовов с `sandbox_permissions` вместо отказа или перегенерации

### F-005
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-005 NON_BLOCKING — `finalize_turn(sanitize=True)` молча пропускает готовые `events`, а SSE-путь не имеет страховочного слоя JSON-пути

### F-006
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-006 NON_BLOCKING — пустой `sandbox_permissions` уходит клиенту и одновременно гасит justification-fallback

### F-007
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-007 NON_BLOCKING — верификация уже проектного гейта: полный `pytest tests/` не предъявлен

### F-008
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-008 NON_BLOCKING — тесты запущены через `unittest`, а проект требует `pytest tests/ -v`

