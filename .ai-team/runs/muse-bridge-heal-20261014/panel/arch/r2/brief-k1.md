# Бриф судьи Архитектурного Совета (ARCHITECTURE-REVIEW, раунд R2 после дельта-доработки, место k=1)

ВАЖНО: Ты — листовой судья Архитектурного Совета (НЕ оркестратор). НЕ открывай контур `cel`, НЕ создавай todo/таймеры и НЕ порождай вложенных сабагентов (`Task`, `invoke_subagent`, `muse`, `droid`, `claude`, `codex`) — прочитай артефакты из рабочего каталога и выдай финальный вердикт напрямую в этом ответе!

## Твоя роль и шляпа
- Место: `k=1`, модель/слот: `claude-sonnet-5-5-high` (`Anthropic`)
- Назначенная шляпа (по `SEED = 68c84230`, `int(SEED, 16) % 3 = 1`): **Реалист** — проверяй реализуемость, конкретику контрактов, наблюдаемость, миграции, обратную совместимость, тестовое покрытие и стоимость сопровождения.
- Оценивай решение по всем 6 критериям рубрики (шляпа задаёт твой главный фокус, но не сужает проверку).

## Цель задачи, Red Lines и дельта после раунда R1
Задача `muse-bridge-heal-20261014` (`S2`, пресет `analyst-teamlead`): устранить три взаимосвязанных сбоя в локальном HTTP-мосте `bridges/muse-bridge/server.py` (порт `127.0.0.1:9886`, stdlib Python `ThreadingHTTPServer`, обслуживающий запросы `pi-ai` из DeepSeek Harness к `muse serve` / `muse exec`):
1. **`REQ-01` / `AD-001`:** логирование всех 3 ранних выходов с HTTP 502 в `Handler._serve_json` (`launcher_missing`/`spawn_failed` на `1690-1701`, `state != "ok" or rc != 0` на `1702-1717`, `empty_output` на `1722-1735`) через `_log(...)` с предварительной редакцией секретов `_redact_secrets(...)`.
2. **`REQ-02` / `AD-002`:** извлечение `TurnError` (`params.error`: `kind[:64]`, `message[:160]`, `retryable`, `quota[:120]`) и недублирующего `params.reason[:160]` в отдельный приоритетный носитель терминальной диагностики `turn_diag_lines` в `ServeRun.execute`, не вытесняемый шумным `stderr`.
3. **`REQ-03` / `AD-003`:** замена `: keepalive\n\n` в `Handler._keepalive_loop` на валидный SSE data-фрейм `self._sse_chunk({"content": ""})` с 3-фазным запечатыванием потока (`OPEN -> FINALIZING -> CLOSED`) под `self._wlock` и дефолтами атрибутов на уровне класса `Handler`.
4. **`REQ-04`, `REQ-05` / `AD-004`:** передача `--disable-write`, `--disable-shell` в `muse serve` и `--disable-write`, `--disable-shell`, `--disable-web-tools`, `--disable-reminders` в `muse exec` (сохраняя `--yolo` и реакцию `approval/request` -> `ServeUnavailable` -> фоллбэк на `exec`).
5. **`REQ-06` / `AD-005`:** синхронизация `ALLOWED_MODELS` (`"muse-wonder-1.0"` и `"muse-wonder-full-1.0"` с `context_length: 1048576, max_output: 131072`).

**Что было исправлено во второй итерации (`plans/architect-v2.json`) по замечаниям R1 (`B1..B4`):**
- **B1 (`AD-003` / `RISK-001`):** полностью синхронизированы `arch-spec.md` и `architecture-packet.json` по 3-фазной машине состояний SSE (`OPEN -> FINALIZING -> CLOSED`) под `self._wlock`, добавлены дефолты на уровне класса `Handler`, явно зафиксирована граница времени ожидания `_wlock` (`Handler.timeout = 300`).
- **B2 (`AD-002`):** полностью синхронизированы `arch-spec.md` и `architecture-packet.json` по отдельному носителю терминальной диагностики с приоритетом над `stderr`, зафиксированы покомпонентные лимиты (`kind[:64]`, `message[:160]`, `quota[:120]`, `reason[:160]`) и правило формирования `detail` в HTTP 502.
- **B3 (Безопасность / `_redact_secrets`):** добавлена спецификация stdlib-санитизатора `_redact_secrets(text: str) -> str`, маскирующего отражённые токены/ключи (`Bearer`, `Authorization`, `api_key`/`token`/`secret`/`password`/`bridge_key`, `sk-...`) в `[REDACTED]` ДО записи в `bridge.log` и HTTP 502 `error.detail`; обновлён security-оракул `ErrorLoggingTest` на проверку маскирования канареечного секрета.
- **B4 (`ASM-004`, `VER-005`, `AC-07`):** синхронизирован статус `ASM-004` (`ASSUMED`, `confidence: medium`) в `architecture-packet.json`, уточнены обязательные оракулы `VER-005` и `AC-07`.

**Red lines (инварианты):**
- Модифицируются только `bridges/muse-bridge/server.py` и `tests/test_muse_bridge_killpg.py` (и боевая копия `~/.dsh/bridges/muse-bridge/server.py` при деплое); никаких внешних зависимостей вне stdlib Python; полная потокобезопасность под `self._wlock`; отсутствие секретов в логах и HTTP 502 `detail`.

## Входные артефакты на диске (в текущем рабочем каталоге `run_dir`)
1. Главный оцениваемый артефакт: `arch-spec.md` (sha256: `2a51c65c057e5c573e50baa90a1d53b24ea1e98402b67c79538bdbddac4dfa5e`)
2. Машиночитаемый архитектурный пакет: `architecture-packet.json`
3. План дельта-доработки Архитектора: `plans/architect-v2.json`
4. Замороженный конверт задачи: `task-envelope.json`
5. Вердикты раунда R1: `panel/arch/r1/seats/1/verdict.md`, `panel/arch/r1/seats/2/verdict.md`, `panel/arch/r1/seats/3/verdict.md`
6. Первичные входы и копии кода: `context/handoff-architect.md`, `context/evidence-ledger.md`, `context/open-questions.md`, `context/server.py`, `context/test_muse_bridge_killpg.py`

## Независимая верификация против отчёта автора
- Статические гейты `ARCH_GATE` (`validate_architecture_packet.py --phase approved`, `validate_role_plan.py --phase after`, `validate_arch_gate.py`) пройдены со статусом `PASS`.
- Твоя задача — **независимый архитектурный аудит** по существу: проверь, устранены ли блокеры R1 (`B1..B4`) в `arch-spec.md` и `architecture-packet.json` и не появилось ли новых противоречий.

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

## Калибровка и нейтральность
- Честный `ACCEPT` при отсутствии блокеров и честный `NEEDS_WORK` / `RED_FLAG` при реальном дефекте равноценны. Выдумывать замечания ради вида запрещено; замалчивать реальные дефекты запрещено.

## ЖЁСТКИЙ ФОРМАТ ОТВЕТА (проверяется автоматом `verify_panel_proof.py`)
1. **Первые две непустые строки твоего ответа ОБЯЗАНЫ быть дословно:**
```
PANEL-NONCE: 5e9601125fb138fe
ARTIFACT-SHA256: 2a51c65c057e5c573e50baa90a1d53b24ea1e98402b67c79538bdbddac4dfa5e
```
Никакого текста ДО этих двух строк!
2. В теле ответа дай содержательный разбор (не менее 600 символов собственного текста) со шляпой `Реалист`, все 6 пунктов рубрики и строки `SUB ...`. Для промежуточных оценок критериев пиши `Критерий N — PASS` (без слова `VERDICT:` с двоеточием), чтобы единственной строкой вида `ОБЩИЙ ВЕРДИКТ: <ЗНАЧЕНИЕ>` была финальная строка.
3. **Самая последняя непустая строка твоего ответа ОБЯЗАНА быть строго одной из трёх строк (без точек, кавычек, звёздочек и пояснений после значения):**
`ОБЩИЙ ВЕРДИКТ: ACCEPT`
или
`ОБЩИЙ ВЕРДИКТ: NEEDS_WORK`
или
`ОБЩИЙ ВЕРДИКТ: RED_FLAG`

---
PANEL-NONCE: 5e9601125fb138fe
ARTIFACT-SHA256: 2a51c65c057e5c573e50baa90a1d53b24ea1e98402b67c79538bdbddac4dfa5e
Инструкция судье: первыми двумя строками ответа повтори дословно «PANEL-NONCE: 5e9601125fb138fe» и «ARTIFACT-SHA256: 2a51c65c057e5c573e50baa90a1d53b24ea1e98402b67c79538bdbddac4dfa5e».
