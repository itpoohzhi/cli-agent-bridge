# consensus-ledger.md — снимок после D1 (prior-ledger следующего раунда)

- round_dir: r2
- artifact_sha256: aae42c18b3702cd397ed5c32b69459bb31e2e4b22276fe4611ff823d522a7146

## Места

- seat 1: slot=gemini-4-argon-high family=Google nonce=860d6854a9c20926 verdict_sha256=d92339045804bea7de59ff061e1ee8ebca2aa3abadcef7adf9e98838c49d2888
- seat 2: slot=gpt-6.1-sol-high family=OpenAI nonce=2739386984ccc2d4 verdict_sha256=9f2aabb466b894b8bf91b25d6a78dc9156bfbca353694d4c69f69e9937cc661e
- seat 3: slot=muse-wonder-full-1.0 family=Meta nonce=edfdbd9c15f3a46f verdict_sha256=471259ff8e4359e9c5a7b8f40aef68d7c150bb17b5930432f5b0322dd9174ae1

## Находки

### F-001
- class: BLOCKER-OPINION
- status: RESOLVED
- votes: {'seat_1': 'AGREE', 'seat_2': 'AGREE', 'seat_3': 'AGREE'}
- text: RW-001 BLOCKER-OPINION — Необязательность поля не означает допустимость удаления пустого значения

### F-002
- class: BLOCKER-OPINION
- status: RESOLVED
- votes: {'seat_1': 'AGREE', 'seat_2': 'AGREE', 'seat_3': 'AGREE'}
- text: RW-002 BLOCKER-OPINION — Предложенный хук не охватывает все пути SSE и повторной доставки

### F-003
- class: BLOCKER-OPINION
- status: RESOLVED
- votes: {'seat_1': 'AGREE', 'seat_2': 'AGREE', 'seat_3': 'AGREE'}
- text: RW-003 BLOCKER-OPINION — Контракт распаковки parallel допускает неоднозначную интерпретацию

### F-004
- class: BLOCKER-OPINION
- status: RESOLVED
- votes: {'seat_1': 'AGREE', 'seat_2': 'AGREE', 'seat_3': 'AGREE'}
- text: RW-004 BLOCKER-OPINION — Ссылки VER-001…VER-005 не имеют определений проверок

### F-005
- class: BLOCKER-OPINION
- status: RESOLVED
- votes: {'seat_1': 'AGREE', 'seat_2': 'AGREE', 'seat_3': 'AGREE'}
- text: RW-005 BLOCKER-OPINION — Отсутствует обязательный механизм выключения нового поведения

### F-006
- class: BLOCKER-OPINION
- status: RESOLVED
- votes: {'seat_1': 'AGREE', 'seat_2': 'AGREE', 'seat_3': 'AGREE'}
- text: RW-006 BLOCKER-OPINION — Безопасность fallback justification заявлена без определённой политики

### F-007
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-007 NON_BLOCKING — трассируемость неполная

### F-008
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-008 NON_BLOCKING — AD-003 — это политика, а не архитектурное решение

