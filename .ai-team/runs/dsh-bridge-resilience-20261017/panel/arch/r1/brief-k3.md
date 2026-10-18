# Бриф судьи Архитектурного Совета (ARCHITECTURE-REVIEW, раунд R1, место k=3)

ВАЖНО: Ты — листовой судья Архитектурного Совета (НЕ оркестратор). НЕ открывай контур `cel`, НЕ создавай todo/таймеры и НЕ порождай вложенных сабагентов (`Task`, `invoke_subagent`, `muse`, `droid`, `claude`, `codex`) — прочитай артефакты из рабочего каталога и выдай финальный вердикт напрямую в этом ответе!

## Твоя роль и шляпа
- Место: `k=3`, модель/слот: `muse-wonder-full-1.0` (`Meta`)
- Назначенная шляпа: **Визионер** — проверяй расширяемость архитектуры на будущие бэкенды (не только `muse`, но и Claude/Codex/OpenCode/Kimi), чистоту абстракций `TurnSessionManager` и `LifecycleManager`, эволюцию API повторного подключения (`X-Turn-ID`, SSE reconnection), сохранение состояния при миграциях и долгосрочную поддерживаемость.
- Оценивай решение по всем 6 критериям рубрики (шляпа задаёт твой главный фокус, но не сужает проверку).

## Цель задачи, Red Lines
Задача `dsh-bridge-resilience-20261017` (`S2`, тикет `EYE-33873`, пресет `analyst-teamlead`): обеспечить сквозную отказоустойчивость в общем слое хаба `cli-agent-bridge` (`core/`, `server.py`) для DeepSeek Harness:
1. **`AD-001` (REQ-003):** Централизация жизненного цикла ходов, буферизации, watchdog и drain в общем слое хаба (`core/turn_session_manager.py`, `core/watchdog.py`, `core/lifecycle.py`, `server.py`).
2. **`AD-002` (REQ-001):** Фоновая автономия ходов (Detached Execution): при обрыве клиентского сокета вызов `_kill_current_run()` и `SIGKILL` запрещены. Ход переходит в `RUNNING_DETACHED` и доводится до конца в фоне с буферизацией событий в `TurnSessionManager` (in-memory кольцевой буфер до 10 МиБ на ход, дамп в `workspace/state/turns/<turn_id>.json`).
3. **`AD-003` (REQ-002):** Адаптивный таймер неактивности (`IDLE_TIMEOUT_S = 300s`) + `ProcessWatchdog` (опрос CPU и дочерних процессов инструментов) + мягкий потолок (`SAFETY_CAP_S = 3600s`, резерв 35с).
4. **`AD-004` (REQ-004):** Плавная остановка (Graceful Shutdown & Drain): перехват `SIGTERM`/`SIGINT`, статус `draining`, отказ новым запросам кодом `503 Retry-After: 5`, доведение активных ходов в окне `DRAIN_TIMEOUT_S = 110s` (`ExitTimeOut = 120s` в plist), терминальный SSE error кадр и `[DONE]` при сбросе по дедлайну.
5. **`AD-005` (REQ-005):** Удаление неподдерживаемой переменной `{{cwd}}` из `deployment:persona-suffix` в `~/.dsh/profiles/web/cordis.patch.yml`.

**Red lines (инварианты):**
- Полная потокобезопасность (`threading.Lock`); реализация в рамках Python stdlib без внешних зависимостей (Redis, SQLite и т.д.); обратная совместимость интерфейса `BackendAdapter`.

## Входные артефакты на диске (в рабочем каталоге)
1. Главный оцениваемый артефакт: `/Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/dsh-bridge-resilience-20261017/architecture/architecture-packet.json` (sha256: `af748f7bada2dc24d0b720c3e1763bdd1a0c6cbf5c7ac2e729500e35a8382183`)
2. Спецификация: `/Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/dsh-bridge-resilience-20261017/architecture/arch-spec.md`
3. ADR: `/Users/aazhiry1/work/src/cli-agent-bridge/docs/adr/0005-resilient-hub-lifecycle-and-detached-turns.md`
4. Материалы системного анализа: `/Users/aazhiry1/work/src/cli-agent-bridge/analysis/bridge-resilience/handoff-architect.md`, `evidence-ledger.md` (факты `[F-01]`..`[F-34]`)

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
PANEL-NONCE: cedf53b3af90ad65
ARTIFACT-SHA256: af748f7bada2dc24d0b720c3e1763bdd1a0c6cbf5c7ac2e729500e35a8382183
```
Никакого текста ДО этих двух строк!
2. В теле ответа дай содержательный разбор (не менее 600 символов собственного текста) со шляпой `Визионер`, все 6 пунктов рубрики и строки `SUB ...`. Для промежуточных оценок критериев пиши `Критерий N — PASS`.
3. **Самая последняя непустая строка твоего ответа ОБЯЗАНЫ быть строго одной из трёх строк:**
`ОБЩИЙ ВЕРДИКТ: ACCEPT`
или
`ОБЩИЙ ВЕРДИКТ: NEEDS_WORK`
или
`ОБЩИЙ ВЕРДИКТ: RED_FLAG`

---
PANEL-NONCE: cedf53b3af90ad65
ARTIFACT-SHA256: af748f7bada2dc24d0b720c3e1763bdd1a0c6cbf5c7ac2e729500e35a8382183
Инструкция судье: первыми двумя строками ответа повтори дословно «PANEL-NONCE: cedf53b3af90ad65» и «ARTIFACT-SHA256: af748f7bada2dc24d0b720c3e1763bdd1a0c6cbf5c7ac2e729500e35a8382183».
