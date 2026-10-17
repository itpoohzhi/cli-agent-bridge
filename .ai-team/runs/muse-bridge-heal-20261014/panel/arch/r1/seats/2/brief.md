# Бриф судьи Архитектурного Совета (ARCHITECTURE-REVIEW, R1, место k=2)

ВАЖНО: Ты — листовой судья Архитектурного Совета (НЕ оркестратор). НЕ открывай контур `cel`, НЕ создавай todo/таймеры и НЕ порождай вложенных сабагентов (`Task`, `invoke_subagent`, `muse`, `droid`, `claude`, `codex`) — прочитай артефакты из рабочего каталога и выдай финальный вердикт напрямую в этом ответе!

## Твоя роль и шляпа
- Место: `k=2`, модель/слот: `claude-sonnet-5-5-high` (`Anthropic`)
- Назначенная шляпа (по `SEED = f06b5ab5`, `int(SEED, 16) % 3 = 0`): **Реалист** — проверяй реализуемость, конкретику контрактов, наблюдаемость, миграции, обратную совместимость, тестовое покрытие и стоимость сопровождения.
- Оценивай решение по всем 6 критериям рубрики (шляпа задаёт твой главный фокус, но не сужает проверку).

## Цель задачи и Red Lines
Задача `muse-bridge-heal-20261014` (критичность `S2`, пресет `analyst-teamlead`): устранить три взаимосвязанных сбоя в локальном HTTP-мосте `bridges/muse-bridge/server.py` (порт `127.0.0.1:9886`, stdlib Python `ThreadingHTTPServer`, обслуживающий запросы `pi-ai` из DeepSeek Harness к `muse serve` / `muse exec`):
1. **Потеря ошибок в `bridge.log` (`REQ-01` / `AD-001`):** в `Handler._serve_json` три ветки раннего возврата (`launcher_missing`/`spawn_failed` на `1690-1701`, `state != "ok" or rc != 0` на `1702-1717`, `empty_output` на `1722-1735`) отдавали HTTP 502 клиенту без вызова `_log(...)`. Решение добавляет единый `_log("error model=... via=... rc=... state=... err=... stream=...")` во все 3 ветки перед `self._send(502, ...)`.
2. **Потеря первопричины `terminal_failed` из `muse serve` (`REQ-02` / `AD-002`):** в `ServeRun.execute` (`1188-1196`) при `turn/completed` с `terminal != "completed"` (в т.ч. `failed`) игнорировались поля `params.error` (`TurnError`: `kind`, `message`, `retryable`, `quota`) и `params.reason`. Решение защищённо извлекает `params.error` и недублирующий `params.reason` в `err_lines` до `err = "\n".join(err_lines[-6:])`.
3. **Разрыв стрима по `streamIdleTimeoutMs` (1900 с) в `pi-ai` (`REQ-03` / `AD-003`):** в `Handler._keepalive_loop` (`1347-1352`) комментарий `: keepalive\n\n` игнорировался парсером `eventsource-parser` в `pi-ai`, не сбрасывая таймер чтения из `for await (const event of stream)`. Решение заменяет комментарий на валидный SSE data-фрейм `self._sse_emit(self._sse_chunk({"content": ""}))` под `self._wlock` с проверкой `not self._client_gone and not stop.is_set()` и остановкой через `self._sse_stop_keepalive()` (`stop.set()` + `join(timeout=2)`) перед финальными чанками и `[DONE]`.
4. **Запрет опасных инструментов CLI в текстовом мосте (`REQ-04`, `REQ-05` / `AD-004`):** передача `--disable-write`, `--disable-shell` в `muse serve` и `--disable-write`, `--disable-shell`, `--disable-web-tools`, `--disable-reminders` в `muse exec` (сохраняя `--yolo` и реакцию на `approval/request` -> `ServeUnavailable` -> фоллбэк на `exec`).
5. **Синхронизация `ALLOWED_MODELS` (`REQ-06` / `AD-005`):** добавление `"muse-wonder-1.0"` и `"muse-wonder-full-1.0"` (`{"context_length": 1048576, "max_output": 131072}`) в репозиторный `bridges/muse-bridge/server.py` (приведение в соответствие с боевым `~/.dsh/bridges/muse-bridge/server.py`).

**Red lines (инварианты):**
- Модифицируются только `bridges/muse-bridge/server.py` и `tests/test_muse_bridge_killpg.py` (и боевая копия `~/.dsh/bridges/muse-bridge/server.py` при деплое); соседние мосты и внешние конфиги `billion-context` не трогаются (`NFR-05`, `NFR-07`).
- Никаких сторонних зависимостей вне stdlib Python (`NFR-06`).
- Потокобезопасность: все записи в `self.wfile` идут строго через `self._sse_emit` под `self._wlock`, а `_keepalive_loop` гарантированно останавливается до записи финальных чанков и `data: [DONE]\n\n` (`NFR-02`, `NFR-03`).
- Санитизация и ограничение длины логов (`err[:300]` с `!r` в `bridge.log`, `detail[:500]` в HTTP 502 JSON) без утечки секретов (`NFR-01`, `NFR-04`).

## Входные артефакты на диске (в текущем рабочем каталоге `run_dir`)
Прочитай с диска:
1. Главный оцениваемый артефакт: `arch-spec.md` (sha256: `7e13c7365419513345eb1bb576f2d9cc73b7b83e94e6e47479faf628e0e5be99`)
2. Машиночитаемый архитектурный пакет: `architecture-packet.json`
3. Замороженный конверт задачи: `task-envelope.json`
4. Входной handoff системного аналитика и таблица фактов: `context/handoff-architect.md`, `context/evidence-ledger.md`, `context/open-questions.md`
5. Целевые файлы кода и тестов (read-only копии): `context/server.py`, `context/test_muse_bridge_killpg.py`

## Независимая верификация против отчёта автора
- Проверки, уже выполненные оркестратором при `ARCH_GATE` (статический гейт): `validate_architecture_packet.py --phase approved` (`PASS`), `validate_role_plan.py --phase after` (`PASS`), сверка fingerprint рабочего дерева (`PASS`).
- Твоя задача — **независимый архитектурный аудит** по существу: сверь `arch-spec.md` и `architecture-packet.json` с реальным кодом `context/server.py` и требованиями `context/handoff-architect.md`. Не пересказывай отчёт автора — проверяй контракты, граничные случаи, потокобезопасность и план тестирования (`T-01..T-06`).

## Рубрика оценки (6 обязательных критериев)
Оцени каждый из 6 критериев (`PASS` / `NEEDS_WORK` / `RED_FLAG`) с конкретным обоснованием и ссылками на разделы `arch-spec.md` и строки `context/server.py`:
1. **Проблема и границы (`problem_and_boundaries`)**
2. **Контракты и инварианты (`contracts_and_invariants`)**
3. **Риски, отказы и деградация (`risks_and_degradation`)**
4. **Безопасность и секреты (`security_and_secrets`)**
5. **Наблюдаемость и эксплуатация (`observability_and_ops`)**
6. **План реализации, миграции и тестов (`implementation_and_test_plan`)**

Также выведи сводку субрибрик в формате:
- `SUB architecture: PASS|CONCERN|FAIL — <1 строка>`
- `SUB security: PASS|CONCERN|FAIL — <1 строка>`
- `SUB performance: PASS|CONCERN|FAIL — <1 строка>`
- `SUB tests: PASS|CONCERN|FAIL — <1 строка>`

## Калибровка и нейтральность
- Мы не знаем заранее, есть ли в архитектурном пакете дефекты: честный `ACCEPT` при отсутствии блокеров и честный `NEEDS_WORK` / `RED_FLAG` при найденном дефекте равноценны. Выдумывать замечания ради вида запрещено; замалчивать реальные дефекты запрещено.
- `RED_FLAG` — только при фундаментальной архитектурной дыре, нарушении безопасности или потере данных.
- `NEEDS_WORK` — если есть конкретный блокер, без исправления которого `Coder` не может безопасно реализовать задачу (укажи `Location`, `Symptom`, `Why it blocks`, `Minimal fix direction`).
- `ACCEPT` — если все 6 критериев `PASS` (допустимы неблокирующие `Recommendations`).

## ЖЁСТКИЙ ФОРМАТ ОТВЕТА (проверяется автоматом `verify_panel_proof.py`)
1. **Первые две непустые строки твоего ответа ОБЯЗАНЫ быть дословно:**
```
PANEL-NONCE: 3d81628ca6c9d4c1
ARTIFACT-SHA256: 7e13c7365419513345eb1bb576f2d9cc73b7b83e94e6e47479faf628e0e5be99
```
Никакого текста, приветствий или markdown-блоков ДО этих двух строк!
2. В теле ответа дай содержательный разбор (не менее 600 символов собственного текста) со шляпой `Реалист`, все 6 пунктов рубрики и строки `SUB ...`. Для промежуточных оценок критериев пиши `Критерий N — PASS` (без двоеточия после слова `VERDICT`), чтобы единственной строкой вида `ОБЩИЙ ВЕРДИКТ: <ЗНАЧЕНИЕ>` была финальная строка.
3. **Самая последняя непустая строка твоего ответа ОБЯЗАНЫ быть строго одной из трёх строк (без точек, кавычек, звёздочек и пояснений после значения):**
`ОБЩИЙ ВЕРДИКТ: ACCEPT`
или
`ОБЩИЙ ВЕРДИКТ: NEEDS_WORK`
или
`ОБЩИЙ ВЕРДИКТ: RED_FLAG`

---
PANEL-NONCE: 3d81628ca6c9d4c1
ARTIFACT-SHA256: 7e13c7365419513345eb1bb576f2d9cc73b7b83e94e6e47479faf628e0e5be99
Инструкция судье: первыми двумя строками ответа повтори дословно «PANEL-NONCE: 3d81628ca6c9d4c1» и «ARTIFACT-SHA256: 7e13c7365419513345eb1bb576f2d9cc73b7b83e94e6e47479faf628e0e5be99».
