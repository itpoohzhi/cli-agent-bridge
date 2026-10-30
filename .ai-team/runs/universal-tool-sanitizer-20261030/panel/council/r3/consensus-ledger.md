# consensus-ledger.md — снимок после D2 (prior-ledger следующего раунда)

- round_dir: r3
- artifact_sha256: f602786d011d752b1cf1a90e2241ecfa65c6dd6149bd9034a4f852156c94ddc2

## Места

- seat 1: slot=gemini-4-argon-high family=Google nonce=38ebac4c69b65187 verdict_sha256=50e66e90c5917912403201fccc10da5c6d72d73558dc156455f7d4ef01f7e1c7
- seat 2: slot=muse-wonder-full-1.0 family=Meta nonce=2ca66c90ba449621 verdict_sha256=1a3cacbab4ef720099fc6f7be161f3d4604342e55283ca8dd8e40d7a691742a1
- seat 3: slot=gpt-6.1-sol-high family=OpenAI nonce=aa0eb19ea908af64 verdict_sha256=34e67d6603e91fe671c5b2ea8b58695740ef50f4249956a7b13941366399bf79

## Находки

### F-001
- class: BLOCKER-OPINION
- status: RESOLVED
- votes: {'seat_1': 'AGREE', 'seat_2': 'AGREE', 'seat_3': 'AGREE'}
- text: RW-001 BLOCKER-OPINION — в пакет санитайзера включён нетрассированный релакс строгого контракта `reasoning_effort` (clamp вместо 400), а «Full Git Diff» пакета опускает переписанные под него тесты

### F-002
- class: BLOCKER-OPINION
- status: RESOLVED
- votes: {'seat_1': 'AGREE', 'seat_2': 'AGREE', 'seat_3': 'AGREE'}
- text: RW-002 BLOCKER-OPINION — schema-aware очистка в интегрированном поведении мертва: `tool_schemas` не передаёт ни одна прод-точка

### F-003
- class: BLOCKER-OPINION
- status: RESOLVED
- votes: {'seat_1': 'AGREE', 'seat_2': 'AGREE', 'seat_3': 'AGREE'}
- text: RW-003 BLOCKER-OPINION — заявление «Required properties keep empty strings» противоречит коду для route-полей и justification

### F-004
- class: BLOCKER-OPINION
- status: RESOLVED
- votes: {'seat_1': 'DISPUTE', 'seat_2': 'AGREE', 'seat_3': 'AGREE'}
- text: RW-004 BLOCKER-OPINION — мост фабрикует `justification` для вызовов с `sandbox_permissions` вместо отказа или перегенерации

### F-005
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-005 NON_BLOCKING — `finalize_turn(sanitize=True)` молча пропускает готовые `events`, а SSE-путь не имеет страховочного слоя JSON-пути

### F-006
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-006 NON_BLOCKING — пустой `sandbox_permissions` уходит клиенту и одновременно гасит justification-fallback

### F-007
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-007 NON_BLOCKING — верификация уже проектного гейта: полный `pytest tests/` не предъявлен

### F-008
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-008 NON_BLOCKING — тесты запущены через `unittest`, а проект требует `pytest tests/ -v`

