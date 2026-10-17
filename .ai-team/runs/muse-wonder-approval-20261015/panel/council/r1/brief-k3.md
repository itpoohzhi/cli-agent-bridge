# Бриф судьи Совета Тимлидов по приёмке кода (COUNCIL-ACCEPT, раунд R1, место k=3)

ВАЖНО: Ты — листовой судья Совета Тимлидов (НЕ оркестратор). НЕ открывай контур cel, НЕ создавай todo/таймеры и НЕ порождай вложенных сабагентов — прочитай артефакты и выдай финальный вердикт напрямую в этом ответе!

## Твоя роль и шляпа
- Место: k=3, модель/слот: `muse-wonder-full-1.0` (Meta)
- Назначенная шляпа: **Скептик**
- Оценивай реализацию как тимлид команды по всем 6 критериям приёмки кода.

## Реализованная задача и архитектурные решения (REQ-MUSE-002/003/004)
1. **`REQ-MUSE-002` / `AD-001` & `AD-002` (Approval без рестарта хода):**
   - На `session/start` передаётся `approvalMode: "allowAll"` (поддержка `denyUnmatched` через env `MUSE_BRIDGE_APPROVAL_MODE` по `AD-007`).
   - Если сервер присылает `approval/request` внутри хода: мост отправляет квитанцию `result={}` тем же id, затем `approval/decide` с `choiceId` из `availableChoices` (предпочитая approve, не approvedForSession); `userInput/request` -> `userInput/cancel`.
   - Границы: не более 10 decide на ход, терминальный отказ защёлкивается с grace 15с (`APPROVAL_CANCEL_GRACE_S=15`), без рестарта через exec.
   - Серверный отказ `-32030` (approval_mode_ceiling, `AD-006`): автоодобрение не включается, выполняется одиночный exec-fallback до turn/start с warning; при `denyUnmatched` exec запрещён.
   - `F-001` (a4): setup-approval защёлкивает `ACTION_POSSIBLE` до receipt; после защёлкивания запрещён любой новый serve/exec.

2. **`REQ-MUSE-003` / `AD-003` (Ограниченный ретрай net-timeout):**
   - Единый цикл повторов в `Handler`: классификация только по маркерам сетевых таймаутов (`[net-timeout]`, `timed out waiting for response data`, `transport_connect_unreachable`, `network connection could not be opened`).
   - Пре-экшн барьер: повтор разрешён ТОЛЬКО до начала потенциально неидемпотентного действия (до первого байта записи `turn/start` в serve и до старта exec).
   - Не более 2 повторов (паузы 2с и 4с + джиттер <= 1с). Абсолютный дедлайн `D = t0 + min(TIMEOUT_S, 1800)`, `E = D - 35`, выдача ограничена `W = D - 12`.
   - Один слот на весь ход. При неподтверждённой смерти группы к дедлайну слот уходит в карантин без ложного освобождения (`F-005` a4).

3. **`REQ-MUSE-004` / `AD-004` (Live reasoning и ограниченный SSE-писатель):**
   - Префикс-монотонная публикация `reasoning_content` дельт `summary.0` на serve-пути через sink Handler до заморозки (первая дельта индекса > 0 или item/completed).
   - Финальное согласование: если полное reasoning `F` начинается с опубликованного префикса `P`, отдаётся хвост; при расхождении дубль запрещён, расхождение логируется.
   - Единый бюджет сокета `LIVE_WRITE_TIMEOUT_S=3` на монотонных часах под `_wlock` для всех писателей (role, keepalive, live-sink, терминал, [DONE]).

## Оцениваемый пакет и первичные артефакты (read-only)
1. Главный оцениваемый артефакт: `/Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/muse-wonder-approval-20261015/code-review-package.md` (sha256: `4d71af5825caa802431b4ac6f9af7212a8fe9469e0405c534d1c89fb2a5c18b6`)
2. Реализация моста: `/Users/aazhiry1/work/src/cli-agent-bridge/bridges/muse-bridge/server.py`
3. Набор тестов: `/Users/aazhiry1/work/src/cli-agent-bridge/tests/test_muse_bridge_killpg.py`
4. Архитектурная спецификация a4: `/Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/muse-wonder-approval-20261015/architecture/arch-spec.md`
5. Чек чистой верификации Clean-room L2: `/Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/muse-wonder-approval-20261015/receipts/verifier-receipt.json`
   - Unit-сьют `test_muse_bridge_killpg.py`: 111 passed из 111 (100% green)
   - Полный репозиторный сьют: 648 passed из 649 (1 известный pre-existing fail test_b_guard tm018, PASS_WITH_PREEXISTING)
   - Линтеры: ruff format/check 0 errors, basedpyright 0 errors
6. Handoff Coder: `/Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/muse-wonder-approval-20261015/coder.json`
7. Git-коммиты на ветке `bugfix/muse-wonder-approval-retry-liveness`:
   - `9f87eb0`: baseline принятого REQ-MUSE-001 (прунинг контекста 400k/320k/200k)
   - `4548dd3`: реализация REQ-MUSE-002/003/004

## Рубрика оценки (тимлид-приёмка, mode=code)
Оцени код со своей шляпой (Скептик) по всем 6 критериям:
1. КОРРЕКТНОСТЬ: соответствие задаче REQ-MUSE-002/003/004, архитектурным решениям AD-001..AD-007 и замечаниям a4.
2. ПОЛНОТА: читаемость кода, покрытие граничных условий (grace, ceiling, карантин, freeze, diverged reasoning).
3. РЕАЛИЗУЕМОСТЬ: устойчивость в рантайме, отсутствие дедлоков под `_wlock`, обработка зависших клиентов и сигналов process group.
4. РИСКИ: сохранение инвариантов, отсутствие регрессий, изоляция сетевых сбоев, корректность маскирования секретов.
5. АЛЬТЕРНАТИВЫ: оправданность выбранного решения (минимально достаточные изменения без раздувания).
6. СООТВЕТСТВИЕ КОНТЕКСТУ: неизменность внешнего контракта OpenAI API (/v1/chat/completions, /health, /v1/models), строгое соблюдение scope (только 2 разрешённых файла).

Обязательно включи в тело ответа строки подкатегорий:
- `SUB architecture: PASS|CONCERN|FAIL — <пояснение>`
- `SUB security: PASS|CONCERN|FAIL — <пояснение>`
- `SUB performance: PASS|CONCERN|FAIL — <пояснение>`
- `SUB tests: PASS|CONCERN|FAIL — <пояснение>`

## ЖЁСТКИЙ ФОРМАТ ОТВЕТА (проверяется автоматом verify_panel_proof.py)
1. **Первые две непустые строки твоего ответа ОБЯЗАНЫ быть дословно:**
PANEL-NONCE: <nonce>
ARTIFACT-SHA256: 4d71af5825caa802431b4ac6f9af7212a8fe9469e0405c534d1c89fb2a5c18b6
Никакого текста ДО этих двух строк!
2. В теле ответа дай обстоятельный технический разбор (не менее 600 символов собственного текста) со шляпой Скептик и строками `SUB ...`. НЕ используй разделители `---`, НЕ пиши строки короче 15 символов, НЕ используй слово `VERDICT:` в середине текста (пиши `Критерий N — PASS`), и НЕ добавляй JSON-блок в конце!
3. **Самая последняя непустая строка твоего ответа ОБЯЗАНЫ быть строго одной из трёх строк:**
ОБЩИЙ ВЕРДИКТ: ACCEPT
или
ОБЩИЙ ВЕРДИКТ: NEEDS_WORK
или
ОБЩИЙ ВЕРДИКТ: RED_FLAG
