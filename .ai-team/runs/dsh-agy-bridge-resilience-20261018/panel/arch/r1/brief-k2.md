# Бриф судьи Архитектурного Совета (ARCHITECTURE-REVIEW, раунд R1, место k=2)

ВАЖНО: Ты — листовой судья Архитектурного Совета (НЕ оркестратор). НЕ открывай контур `cel`, НЕ создавай todo/таймеры и НЕ порождай вложенных сабагентов (`Task`, `invoke_subagent`, `muse`, `droid`, `claude`, `codex`) — прочитай артефакты из рабочего каталога и выдай финальный вердикт напрямую в этом ответе!

## Твоя роль и шляпа
- Место: `k=2`, модель/слот: `claude-sonnet-5-5-high` (`Anthropic`)
- Назначенная шляпа: **Реалист** — проверяй эксплуатационную применимость, обратную совместимость с клиентами DSH, реалистичность таймингов (300с idle watchdog vs 1800с hard cap), корректность работы watchdog на macOS (поведение `ps -eo pid,ppid,cputime`, группы процессов, сигналы SIGTERM/SIGKILL), простоту сопровождения кода в монорепо.
- Оценивай решение по всем 6 критериям рубрики (шляпа задаёт твой главный фокус, но не сужает проверку).

## Цель задачи, Red Lines
Задача `dsh-agy-bridge-resilience-20261018` (`S2`, тикет `EYE-33873`, пресет `analyst-teamlead`): обеспечить отказоустойчивость моста Antigravity CLI (`bridges/agy-bridge`) и устранить 30-минутные зависания DSH (инцидент 1800s timeout):
1. **Интеграция моста в репозиторий:** перенос `bridges/agy-bridge/server.py` в состав монорепозитория `cli-agent-bridge` с переиспользованием общего слоя `core/watchdog.py` и `core/lifecycle.py`.
2. **Двухконтурный Watchdog:** `IDLE_TIMEOUT_S = 300s` (сброс по протокольным событиям или `cpu_delta_s > 0` в дереве процессов `pgid`) + `SAFETY_CAP_S = 1800s`. Прерывание зависших ходов за 300 секунд вместо 1800 секунд с кодом `idle_timeout`.
3. **Зачистка деревьев процессов:** вызов `os.killpg(pgid, signal.SIGKILL)` при остановке хода для гарантированного уничтожения потомков.
4. **Hotfix клиентского скрипта:** внедрение `asyncio.wait_for(..., timeout=60.0)` и `AbortSignal.timeout(15000)` в `scripts/fetch_via_playwright.py` (проект `aibunker-workshop`).
5. **Тестирование и поставка:** 100% покрытие в `tests/test_agy_bridge_resilience.py`, вливание в `dev` и `main`, локальный деплой и рестарт службы `com.user.dsh-agy-bridge`.

## Входные артефакты на диске (в рабочем каталоге)
1. Главный оцениваемый артефакт: `/Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/dsh-agy-bridge-resilience-20261018/architecture/architecture-packet.json` (sha256: `d570c88bc41324d1171a9d7a5bfa8c5db29a2e8573b9f0c2c219e98ac8dcab36`)
2. Спецификация: `/Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/dsh-agy-bridge-resilience-20261018/architecture/arch-spec.md`
3. ADR: `/Users/aazhiry1/work/src/cli-agent-bridge/docs/adr/0007-agy-bridge-resilience-watchdog.md`
4. Материалы системного анализа: `/Users/aazhiry1/work/src/cli-agent-bridge/analysis/agy-bridge-resilience/handoff-architect.md`, `evidence-ledger.md` (факты `[F-01]`..`[F-11]`)

## Рубрика оценки (6 обязательных критериев)
Оцени каждый из 6 критериев (`PASS` / `NEEDS_WORK` / `RED_FLAG`) с конкретным обоснованием:
1. **Проблема и границы (`problem_and_boundaries`)**
2. **Контракты и инварианты (`contracts_and_invariants`)**
3. **Риски, отказы и деградация (`risks_and_degradation`)**
4. **Безопасность и секреты (`security_and_secrets`)**
5. **Наблюдаемость и эксплуатация (`observability_and_ops`)**
6. **План реализации, миграции и тестов (`implementation_and_test_plan`)**

Выведи сводку субрибрик:
- `SUB architecture: PASS|CONCERN|FAIL — <1 строка>`
- `SUB security: PASS|CONCERN|FAIL — <1 строка>`
- `SUB performance: PASS|CONCERN|FAIL — <1 строка>`
- `SUB tests: PASS|CONCERN|FAIL — <1 строка>`

## ЖЁСТКИЙ ФОРМАТ ОТВЕТА (проверяется автоматом `verify_panel_proof.py`)
1. **Первые две непустые строки твоего ответа ОБЯЗАНЫ быть дословно:**
```
PANEL-NONCE: 989917c4ffaa8f78
ARTIFACT-SHA256: d570c88bc41324d1171a9d7a5bfa8c5db29a2e8573b9f0c2c219e98ac8dcab36
```
Никакого текста ДО этих двух строк!
2. В теле ответа дай содержательный разбор (не менее 600 символов собственного текста) со шляпой `Реалист`, все 6 пунктов рубрики и строки `SUB ...`. Для промежуточных оценок критериев пиши `Критерий N — PASS`.
3. **Самая последняя непустая строка твоего ответа ОБЯЗАНА быть строго одной из трёх строк:**
`ОБЩИЙ ВЕРДИКТ: ACCEPT`
или
`ОБЩИЙ ВЕРДИКТ: NEEDS_WORK`
или
`ОБЩИЙ ВЕРДИКТ: RED_FLAG`

---
PANEL-NONCE: 989917c4ffaa8f78
ARTIFACT-SHA256: d570c88bc41324d1171a9d7a5bfa8c5db29a2e8573b9f0c2c219e98ac8dcab36
Инструкция судье: первыми двумя строками ответа повтори дословно «PANEL-NONCE: 989917c4ffaa8f78» и «ARTIFACT-SHA256: d570c88bc41324d1171a9d7a5bfa8c5db29a2e8573b9f0c2c219e98ac8dcab36».
