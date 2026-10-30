# consensus-ledger.md — снимок после D1 (prior-ledger следующего раунда)

- round_dir: r2
- artifact_sha256: f602786d011d752b1cf1a90e2241ecfa65c6dd6149bd9034a4f852156c94ddc2

## Места

- seat 1: slot=gpt-6.1-sol-high family=OpenAI nonce=71618217f4e5a13f verdict_sha256=f5271c149331cfabedba24fc73cad3d56d3814d1f7f659ab3d1e10e4f8741244
- seat 2: slot=claude-sonnet-5-5-high family=Anthropic nonce=2d24a405688ea963 verdict_sha256=a6b28fa8791c6c071cdfd5f771f155e7c235ece0bec936adc1cd17f3739082a8
- seat 3: slot=gemini-4-argon-high family=Google nonce=8529671c83c872d2 verdict_sha256=e68f5d75116fdd41de5cd1f28124085eff07a65c3ab71b4fdf9776590e5513fd

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
- status: OPEN
- votes: {'seat_1': 'AMEND', 'seat_2': 'AGREE', 'seat_3': 'DISPUTE'}
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

