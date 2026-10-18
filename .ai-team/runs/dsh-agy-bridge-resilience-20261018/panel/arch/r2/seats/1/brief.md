# Бриф судьи Архитектурного Совета (ARCHITECTURE-REVIEW, раунд R2, место k=1)

ВАЖНО: Ты — листовой судья Архитектурного Совета (НЕ оркестратор). НЕ открывай контур `cel`, НЕ создавай todo/таймеры и НЕ порождай вложенных сабагентов (`Task`, `invoke_subagent`, `muse`, `droid`, `claude`, `codex`) — прочитай артефакты из рабочего каталога и выдай финальный вердикт напрямую в этом ответе!

## Твоя роль и шляпа
- Место: `k=1`, модель/слот: `gpt-6.1-sol` (`OpenAI`)
- Назначенная шляпа: **Скептик** — проверяй устранение замечаний Раунда 1 (Verify-Fixed по RW-001..RW-008), отсутствие регрессий, граничные условия при остановке процессов, предотвращение zombie (`wait()` после `SIGKILL`), корректность работы с `AdaptiveTimeoutController`.
- Оценивай решение по всем 6 критериям рубрики.

## Контекст Раунда 2 (R2)
В Раунде 1 Совет Тимлидов выдал 8 обязательных требований (RW-001..RW-008). Архитектор переработал архитектурный пакет (ревизия `REVISED_R2`, ADR-0007 r2, спецификация `arch-spec.md` r2):
1. **RW-001 (API):** Точное следование реальному контракту `AdaptiveTimeoutController(idle_timeout_s=IDLE_TIMEOUT_S, safety_cap_s=TIMEOUT_S, finish_reserve_s=0.0, log_fn=_log)`: вызов `register_pgid(self.proc.pid)` в `Run.__init__`, сброс по `controller.on_activity(kind)` при событиях очереди, троттлинг `controller.check(run.proc.pid)` (в `except queue.Empty:` и не чаще раз в 5.0 с), `controller.close()` в `Run.close()`.
2. **RW-002 (Safety Cap):** Явная передача `safety_cap_s=TIMEOUT_S` (1800.0 с) вместо дефолтного значения 3600.0 с.
3. **RW-003 (Kill-Switch):** Поддержка `_is_watchdog_enabled()` через `BRIDGE_ENABLE_ADAPTIVE_WATCHDOG`.
4. **RW-004 (Контракт ошибок):** Маппинг `st == "idle_timeout"` в HTTP 504 Gateway Timeout (`type: "idle_timeout"`) и SSE-кадр `{"error": ...}` + `[DONE]`.
5. **RW-005 (Зачистка и зомби):** Эскалация SIGTERM -> SIGKILL и обязательный `proc.wait(timeout=5.0)` для гарантированной зачистки зомби.
6. **RW-006 (Деплой и импорт):** Bootstrap `sys.path` через `_REPO_ROOT = Path(__file__).resolve().parents[2]`, деплой симлинком `~/.dsh/bridges/agy-bridge` (с экспортом PYTHONPATH в `start.sh`), перенос `fleet.json`, регистрация `"agy"`, `"agy-cli.sh"` в `KNOWN_CHILD_BINARIES` в `core/lifecycle.py`.
7. **RW-007 (Hotfix fetch_via_playwright.py):** Оборачивание `fn(...)` в `asyncio.wait_for(..., timeout=60.0)` с перехватом `(asyncio.TimeoutError, TimeoutError)` и возвратом ошибки источника без срыва `asyncio.gather()`, плюс таймаут 5.0 с на закрытие страниц в `finally:`.
8. **RW-008 (Тест-план):** 15 конкретных сценариев тестов в `tests/test_agy_bridge_resilience.py` на мок-часах.

## Входные артефакты на диске (в рабочем каталоге)
1. Главный оцениваемый артефакт: `/Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/dsh-agy-bridge-resilience-20261018/architecture/architecture-packet.json` (sha256: `f8c6c18e746af5cd92d39f12886354608aa099591845a851b6f66bdd722149e6`)
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
PANEL-NONCE: 55c505d376778239
ARTIFACT-SHA256: f8c6c18e746af5cd92d39f12886354608aa099591845a851b6f66bdd722149e6
```
Никакого текста ДО этих двух строк!
2. В теле ответа дай содержательный разбор со шляпой `Скептик`, подтверди устранение замечаний R1 (Verify-Fixed), оцени все 6 пунктов рубрики и выведи строки `SUB ...`. Для оценок критериев пиши `Критерий N — PASS`.
3. **Самая последняя непустая строка твоего ответа ОБЯЗАНА быть строго одной из трёх строк:**
`ОБЩИЙ ВЕРДИКТ: ACCEPT`
или
`ОБЩИЙ ВЕРДИКТ: NEEDS_WORK`
или
`ОБЩИЙ ВЕРДИКТ: RED_FLAG`

---
PANEL-NONCE: 55c505d376778239
ARTIFACT-SHA256: f8c6c18e746af5cd92d39f12886354608aa099591845a851b6f66bdd722149e6
Инструкция судье: первыми двумя строками ответа повтори дословно «PANEL-NONCE: 55c505d376778239» и «ARTIFACT-SHA256: f8c6c18e746af5cd92d39f12886354608aa099591845a851b6f66bdd722149e6».
