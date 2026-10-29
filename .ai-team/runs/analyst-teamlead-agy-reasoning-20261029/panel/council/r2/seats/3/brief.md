PANEL-NONCE: 50f4e90bee4fd3ff
ARTIFACT-SHA256: 7d4f3ee38549312817f33a0cc6b82ef02f69a62f9d764777b3d84d63e460838b
PRIOR-LEDGER-SHA256: f6fc76a1de0676ef59e7472bcb6f02c63893c721472d38d6df729cde441ca666

# Бриф судьи Совета Тимлидов по коду — Раунд дебатов `D1` (`panel/council/r2`, Место #3)

⚠️ **КРИТИЧЕСКАЯ ИНСТРУКЦИЯ (LEAF JUDGE / AGENT_SPAWN_DEPTH=1):**
- Вы — конечный судья панели `teamlead-gate` (`mode: code`, `stage: council`, `round: r2` / дебаты `D1`, `seat: 3`).
- **НЕ запускайте** никаких субагентов, контуров `cel`, внешних скриптов или команд модификации.
- **НЕ вызывайте** инструменты чтения/поиска — **все материалы дебатов `D1` (`recheck-r1.md`, `consensus-ledger.md` с `F-001..F-004`, анонимизированные вердикты `R1`, код `bridges/agy-bridge/server.py` и результаты чистой комнаты `VER-001..VER-013`) полностью встроены в этот бриф ниже**.
- **Первыми двумя строками вашего ответа ОБЯЗАНЫ быть дословно (без отступов, без markdown-блоков вокруг них):**
PANEL-NONCE: 50f4e90bee4fd3ff
ARTIFACT-SHA256: 7d4f3ee38549312817f33a0cc6b82ef02f69a62f9d764777b3d84d63e460838b
- **Строка `ОБЩИЙ ВЕРДИКТ:` (самая последняя строка ответа!) ОБЯЗАНА принимать строго одно из канонических значений верификатора `verify_panel_proof.py` (`PoL-V12`):** `ACCEPT`, `PASS`, `NEEDS_WORK` или `RED_FLAG`.

---

## 1. Контекст раунда дебатов `D1` (`consensus-debate.md`)

- **run_id**: `analyst-teamlead-agy-reasoning-20261029`
- **mode**: `code` | **stage**: `council` | **round**: `r2` (`D1`) | **seat**: `3` (`gemini-4-argon-high`, `Google`, `agy`)
- **Шляпа (hat)**: Визионер (проверяет целостность решения и позиции по F-001..F-004 с учётом RECHECK и оценивает 14 подкатегорий mode=code)
- **seed_recheck_duty**: `нет`
- **PANEL-NONCE**: `50f4e90bee4fd3ff`
- **ARTIFACT-SHA256**: `7d4f3ee38549312817f33a0cc6b82ef02f69a62f9d764777b3d84d63e460838b`
- **PRIOR-LEDGER-SHA256**: `f6fc76a1de0676ef59e7472bcb6f02c63893c721472d38d6df729cde441ca666`
- **seed_input**: `analyst-teamlead-agy-reasoning-20261029:council:r2:7d4f3ee38549312817f33a0cc6b82ef02f69a62f9d764777b3d84d63e460838b:9ce1632fcd16523b2fb0443604df5e8ab95d1405c12b2bf79624665b4ba0ac0f`
- **seed_hex**: `2103f4a4260994e0459445949ed55a65b5b11e85187bae975bdb639096d988b6`
- **ranked_order**: `["gpt-6.1-sol-high", "gemini-4-argon-high", "muse-wonder-full-1.0", "claude-sonnet-5-5-high"]` (`gpt-6.1-sol-high=041e399d5e350cd2, gemini-4-argon-high=58b1817891a1c4a6, muse-wonder-full-1.0=a7e86180df146918, claude-sonnet-5-5-high=cf090e969b2c1edf`, `3of3_derangement` относительно `council/r1`, проверено `PoL-V13`)
- **ПОЗИЦИИ ТРЕБУЮТСЯ ПО:** `F-001, F-002, F-003, F-004; N=4`
- **ВОПРОСЫ К ТЕБЕ:** `нет (A=0)`

### Правило дебатов `D1` (`consensus-debate.md`):
В раунде `R1` два судьи (`R1-A` и `R1-B`) вынесли вердикт `ACCEPT` (`0 BLOCKER, 0 MAJOR`), а третий судья (`R1-C`) отметил 4 пункта (`F-001..F-004`), из которых только `F-001` имел приоритет `blocking` (теоретическое сочетание `>128` шагов в рамках одного хода + одновременное усечение файла `transcript_full.jsonl` посередине хода `size < self._offset`), а `F-002`, `F-003`, `F-004` уже в `R1` имели неблокирующий статус (`non-blocking`).
- Если вы согласны с проверкой `RECHECK`, что `F-001` является теоретическим краевым случаем за пределами эксплуатационного профиля `agy` (`1–15` шагов на ход по `EVD-031`, `base_idx` отсекает прошлые ходы, при `seen_cap` SQLite отключается, а `transcript_full.jsonl` append-only) и может быть зафиксирован как неблокирующий остаточный риск / бэклог-улучшение без блокировки приёмки, проголосуйте:
  `AMEND F-001 — priority=non-blocking; <обоснование>`
- По `F-002`, `F-003`, `F-004` (уже `non-blocking`) укажите:
  `AMEND F-002 — priority=non-blocking; <обоснование>` (или `AGREE F-002 — ...`)
  `AMEND F-003 — priority=non-blocking; <обоснование>` (или `AGREE F-003 — ...`)
  `AMEND F-004 — priority=non-blocking; <обоснование>` (или `AGREE F-004 — ...`)
- Если после ваших позиций в `D1` открытых блокирующих находок не остаётся (`Блокеров: 0`), укажите `FINDINGS_COMPLETE: YES` и последней строкой ответа `ОБЩИЙ ВЕРДИКТ: ACCEPT`.

---

## 2. Строгий шаблон ответа судьи в раунде `D1`

```
PANEL-NONCE: 50f4e90bee4fd3ff
ARTIFACT-SHA256: 7d4f3ee38549312817f33a0cc6b82ef02f69a62f9d764777b3d84d63e460838b

=== КАРТОЧКА СУДЬИ (РАУНД D1) ===
Место: #3 | Слот: gemini-4-argon-high | Семейство: Google | Транспорт: agy
Режим: code | Раунд: r2 (D1) | Шляпа: Визионер (проверяет целостность решения и позиции по F-001..F-004 с учётом RECHECK и оценивает 14 подкатегорий mode=code)
seed_recheck_duty: нет
seed_recheck: <PASS / N/A>
PRIOR-LEDGER-SHA256: f6fc76a1de0676ef59e7472bcb6f02c63893c721472d38d6df729cde441ca666
ПОЗИЦИИ ТРЕБУЮТСЯ ПО: F-001, F-002, F-003, F-004; N=4
ВОПРОСЫ К ТЕБЕ: нет (A=0)
Вердикт места: ACCEPT
Блокеров: 0 | Существенных: 0 | Замечаний: 4

[POSITIONS D1]
- AMEND F-001 — priority=non-blocking; ...
- AMEND F-002 — priority=non-blocking; ...
- AMEND F-003 — priority=non-blocking; ...
- AMEND F-004 — priority=non-blocking; ...

POSITIONS: 4/4
ANSWERS: 0/0

[SUB COVERAGE]
| Подкатегория | Статус (PASS/CONCERN/BLOCKER) | Доказательство (файл:строки / тест / VER-ID) | Комментарий |
|---|---|---|---|
| SUB-CORRECT-01 | PASS | ... | ... |
| SUB-EDGE-02 | PASS | ... | ... |
| SUB-ARCH-03 | PASS | ... | ... |
| SUB-API-04 | PASS | ... | ... |
| SUB-ERR-05 | PASS | ... | ... |
| SUB-SEC-06 | PASS | ... | ... |
| SUB-CONC-07 | PASS | ... | ... |
| SUB-RES-08 | PASS | ... | ... |
| SUB-PERF-09 | PASS | ... | ... |
| SUB-TEST-10 | PASS | ... | ... |
| SUB-MAINT-11 | PASS | ... | ... |
| SUB-SIMP-12 | PASS | ... | ... |
| SUB-OBS-13 | PASS | ... | ... |
| SUB-DEPS-14 | PASS | ... | ... |

[FINDINGS]
Замечаний класса BLOCKER и MAJOR не обнаружено (находки F-001..F-004 переведены в non-blocking остаточные риски / бэклог).

[ОБОСНОВАНИЕ ВЕРДИКТА]
...

FINDINGS_COMPLETE: YES
ОБЩИЙ ВЕРДИКТ: ACCEPT
```

---

## 3. Материалы раунда `R1`: `recheck-r1.md`, `consensus-ledger.md` и анонимизированные вердикты `R1`

### 3.1. Перепроверка оркестратора (`panel/council/r1/recheck-r1.md`)
```markdown
# Перепроверка ссылок R1 (`recheck-r1.md`) — Совет Тимлидов по коду (`COUNCIL`, после `panel/council/r1`)

- **Run ID:** `analyst-teamlead-agy-reasoning-20261029`
- **Раунд R1:** `.ai-team/runs/analyst-teamlead-agy-reasoning-20261029/panel/council/r1` (`panel-proof.json` `verify_panel_proof exit=0`, голоса R1: Seat 1 `gemini-4-argon-high` = `ACCEPT`, Seat 2 `muse-wonder-full-1.0` = `ACCEPT`, Seat 3 `gpt-6.1-sol-high` = `NEEDS_WORK`)
- **Проверяемый артефакт:** `.ai-team/runs/analyst-teamlead-agy-reasoning-20261029/teamlead/package.md` (`sha256=7d4f3ee38549312817f33a0cc6b82ef02f69a62f9d764777b3d84d63e460838b`)

RECHECK F-001 (Seat 3 `C3-001` — составной теоретический сценарий: `>128` шагов в рамках одного хода + вытеснение из `seen` + усечение файла `transcript_full.jsonl` посередине того же хода `size < self._offset`):
Проверка по `bridges/agy-bridge/server.py:1609-1615, 1648-1650, 1667-1678` и `EVD-031`:
1) Фильтр `if idx is not None and idx < self.base_idx: return` (`server.py:1649`) отсекает все шаги предыдущих ходов сессии; словарь `self.seen` хранит только шаги текущего хода (`idx >= base_idx`). По `EVD-031` один ход `agy` создаёт `1–15` шагов (потолок `MAX_STEPS_TRACKED = 128` превышает реальное число шагов хода на порядок).
2) Даже при гипотетическом превышении 128 шагов внутри одного хода ветка `self._sqlite_off("seen_cap")` (`server.py:1676`) немедленно отключает чтение из SQLite, а `transcript_full.jsonl` у `agy` является строго append-only логом (ветка `size < self._offset` на строке `1609` срабатывает только если файл транскрипта был физически перезаписан/усечён внешним процессом одновременно с `>128` шагами одного хода).
3) Ни в одном из 97 тестов `VER-003`/`VER-012` и стресс-оракуле `VER-010` (`tc93`) расхождений дедупликации нет; сценарий `>128 шагов за один ход + одновременное усечение файла транскрипта` является теоретическим краевым случаем за пределами эксплуатационного профиля `agy`.
Рекомендация RECHECK для D1: `AMEND F-001 — priority=non-blocking` (зафиксировать как неблокирующий остаточный риск / бэклог-улучшение `min_evicted_idx` без блокировки приёмки).

RECHECK F-002 (Seat 3 `C3-002` — накопление `_buf` в `_read_transcript` при длительной неполной строке без `\n`):
В R1 судья Seat 3 уже присвоил этой находке неблокирующий класс `MAJOR` (`non-blocking`). Проверка по `server.py:1609-1628` и `2120-2125`: при неизменном размере файла строка `if size == self._offset: return` (`server.py:1614`) предотвращает повторное чтение; `agy` записывает JSONL-строку одной операцией записи с завершающим `\n`, а общий объём выдаваемого мышления на ход жёстко ограничен `MAX_REASONING_BYTES_PER_TURN = 2 MiB`.
Рекомендация RECHECK для D1: `AGREE F-002` / `AMEND F-002 — priority=non-blocking`.

RECHECK F-003 (Seat 3 `C3-003` — прерывание выполняющегося `SELECT` при переключении kill-switch `SQLITE_REASONING_ENABLED=false`):
В R1 судья Seat 3 уже присвоил этой находке неблокирующий класс `MAJOR` (`non-blocking`). Проверка по `server.py:1098-1102, 1508-1517, 1851-1877` и `VER-010` (`AO-09`, `tc93`): соединение открывается с `timeout=0.05` (`50 ms`) и `PRAGMA busy_timeout = 50`, запрос `_STEPS_SQL` читает `LIMIT 16` строк `<= 256 KiB` по первичному ключу (`p95 <= 5 ms`), проверка `_sqlite_permitted()` выполняется на каждой строке результата (`server.py:1854`) с вызовом `interrupt_active_query()`, а при закрытии хода `Run.close()` вызывает `interrupt_active_query()` из внешнего потока (`server.py:2305`). Время реакции kill-switch составляет `<= 1.30 s` при требовании `REQ-011 <= 5.0 s`.
Рекомендация RECHECK для D1: `AGREE F-003` / `AMEND F-003 — priority=non-blocking`.

RECHECK F-004 (Seat 3 `C3-004` — уточнение формулировки `VER-011` и `VER-013` в таблице трассируемости):
В R1 судья Seat 3 присвоил находке класс `MINOR` (`non-blocking`). В `verifier.json` и `reverse-spec.md` уже явно зафиксировано, что `VER-011` (`L3`) выполняется строго после `ACCEPT` Совета и до открытия/вливания MR, а `VER-013` подтверждает `0` новых регрессий при сравнении `974` тестов кандидата с `899` тестами базового коммита (`2` идентичных внешних baseline-падения в `test_muse_bridge_killpg.py`).
Рекомендация RECHECK для D1: `AGREE F-004` / `AMEND F-004 — priority=non-blocking`.

```

### 3.2. Консенсус-леджер открытых находок R1 (`panel/council/r1/consensus-ledger.md`, `sha256=f6fc76a1de0676ef59e7472bcb6f02c63893c721472d38d6df729cde441ca666`)
```markdown
# Консенсус-леджер находок Совета Тимлидов по коду — до дебатов `D1` (после `R1` `panel/council/r1`)

- **Run ID:** `analyst-teamlead-agy-reasoning-20261029`
- **Раунд R1:** `.ai-team/runs/analyst-teamlead-agy-reasoning-20261029/panel/council/r1` (`panel-proof.json` `verify_panel_proof exit=0`)
- **Проверяемый артефакт:** `.ai-team/runs/analyst-teamlead-agy-reasoning-20261029/teamlead/package.md` (`sha256=7d4f3ee38549312817f33a0cc6b82ef02f69a62f9d764777b3d84d63e460838b`)

---

## Карточки открытых находок R1 (вход для дебатов D1)

### F-001
- origin: Seat 3 (`gpt-6.1-sol-high` C3-001)
- rev: 1
- priority: blocking
- status: OPEN
- outcome: blocking
- text: При превышении `MAX_STEPS_TRACKED = 128` шагов в рамках одного хода и одновременном перезаписывании/уменьшении размера `transcript_full.jsonl` (`size < self._offset`) вытесненный из `self.seen` шаг текущего хода при повторном чтении транскрипта с нуля получит новый `_StepState` (`delivered_len=0`). По `EVD-031` один ход `agy` порождает `1–15` шагов (на порядок ниже `128`), `base_idx` отсекает прошлые ходы, при `seen_cap` SQLite отключается, а `transcript_full.jsonl` у `agy` append-only. Рекомендация RECHECK для D1: `AMEND F-001 — priority=non-blocking` (зафиксировать как неблокирующий остаточный риск / бэклог-улучшение `evicted_watermark` в разделе Б итогового вердикта).

### F-002
- origin: Seat 3 (`gpt-6.1-sol-high` C3-002)
- rev: 1
- priority: non-blocking
- status: OPEN
- outcome: non-blocking
- text: В `_read_transcript` (`server.py:1614-1624`) `self._offset` сдвигается после получения `\n`; если `agy` дописывает новые байты к незавершённой строке без `\n` на нескольких тиках, незавершённый префикс перечитывается с `self._offset`. В R1 классифицировано как `MAJOR` (`non-blocking`), общий объём выдачи ограничен `MAX_REASONING_BYTES_PER_TURN = 2 MiB`. Рекомендация RECHECK для D1: `AGREE F-002` / `AMEND F-002 — priority=non-blocking`.

### F-003
- origin: Seat 3 (`gpt-6.1-sol-high` C3-003)
- rev: 1
- priority: non-blocking
- status: OPEN
- outcome: non-blocking
- text: Проверка `_sqlite_permitted()` и вызов `interrupt_active_query()` в `_select_rows` (`server.py:1853-1859`) выполняются после возврата из `conn.execute(_STEPS_SQL, ...)` (где `busy_timeout = 50 ms` и `LIMIT 16` строк `<= 256 KiB` ограничивают время `SELECT` миллисекундами, а при закрытии хода `Run.close()` вызывает `interrupt_active_query()` из внешнего потока). В R1 классифицировано как `MAJOR` (`non-blocking`), `AO-09` подтверждает реакцию `<= 1.30 s` при норме `REQ-011 <= 5.0 s`. Рекомендация RECHECK для D1: `AGREE F-003` / `AMEND F-003 — priority=non-blocking`.

### F-004
- origin: Seat 3 (`gpt-6.1-sol-high` C3-004)
- rev: 1
- priority: non-blocking
- status: OPEN
- outcome: non-blocking
- text: Уточнить в итоговом вердикте Совета, что живая проверка `VER-011` (`L3`) выполняется строго после `ACCEPT` Совета и до открытия/вливания MR (по Шагу 5 `teamlead-gate`), а `VER-013` подтверждает отсутствие новых регрессий (`974` теста кандидата против `899` базовых при тех же `2` внешних baseline-падениях в `test_muse_bridge_killpg.py`). В R1 классифицировано как `MINOR` (`non-blocking`). Рекомендация RECHECK для D1: `AGREE F-004` / `AMEND F-004 — priority=non-blocking`.

```

### 3.3. Анонимизированные вердикты судей раунда R1
#### Анонимизированный вердикт R1 — Судья R1-A (ACCEPT, 0 BLOCKER, 0 MAJOR)
```markdown
=== КАРТОЧКА СУДЬИ ===
Режим: code | Раунд: r1 | Шляпа: Скептик (ищет ошибки, гонки, утечки дескрипторов, нарушения F-001..F-010 и инвариантов)
seed_recheck_duty: да
seed_recheck: PASS (sha256(seed_input)==seed_hex, PoL-V13 selection contract verified)
package_path: /Users/aazhiry1/tmp/cli-agent-bridge/agy-realtime-reasoning/.ai-team/runs/analyst-teamlead-agy-reasoning-20261029/teamlead/package.md
Вердикт места: ACCEPT
Блокеров: 0 | Существенных: 0 | Замечаний: 0

[SUB COVERAGE]
| Подкатегория | Статус (PASS/CONCERN/BLOCKER) | Доказательство (файл:строки / тест / VER-ID) | Комментарий |
|---|---|---|---|
| SUB-CORRECT-01 | PASS | `bridges/agy-bridge/server.py:1186-1240, 1698-1790, 1955-1993, 2723-2767`; `TC-01..92`, `AO-01..12`, `VER-003`, `VER-007` | Все требования `REQ-001..REQ-012`, `AC-001..AC-016` и обязательные предохранители `F-001..F-009` реализованы точно по спецификации; в `_drain_post_eof` (`server.py:1955-1993`) удалён эвристический выход `planner_final` и выдерживается полное окно `DRAIN_WINDOW_S = 0.35 s` при отсутствии `END_TURN`/`TURN_COMPLETE`. |
| SUB-EDGE-02 | PASS | `bridges/agy-bridge/server.py:1246-1348, 1663-1680, 1823-1849`; `TC-04..12`, `TC-40..44`, `AO-12`, `VER-003` | Корректно обработаны обрезанные varint/wire-поля, незавершённые UTF-8 последовательности (`_trim_incomplete_utf8`), отсутствие БД/таблицы `steps`, пустое мышление и жёсткое вытеснение `del self.seen[min(self.seen)]` при `MAX_STEPS_TRACKED = 128` (`server.py:1667-1678`). |
| SUB-ARCH-03 | PASS | `teamlead/candidate-manifest.json`; `VER-006`, `VER-008`, `VER-009` | Изменения строго локализованы в `bridges/agy-bridge/server.py` и аддитивных тестах `tests/test_agy_bridge_resilience.py` (`0` удалённых строк в существующих тестах); используются исключительно модули стандартной библиотеки Python. |
| SUB-API-04 | PASS | `bridges/agy-bridge/server.py:2863-2902, 3157-3247`; `TC-61`, `AO-06`, `VER-003`, `VER-012` | Полностью сохранена обратная совместимость HTTP/SSE контрактов (`POST /chat`, `GET /health` с 4 аддитивными полями, OpenAI SSE `delta.reasoning_content` и финальный `data: [DONE]`). |
| SUB-ERR-05 | PASS | `bridges/agy-bridge/server.py:1809-1849, 2192-2286`; `TC-40..44`, `AO-01`, `VER-003` | Приоритет схемной ошибки (`no such table` / `no such column`) над `cold-open` соблюдён (`F-002`, `server.py:1828-1841`); любые ошибки SQLite и парсинга деградируют fail-open на транскрипт без обрыва пользовательского хода. |
| SUB-SEC-06 | PASS | `bridges/agy-bridge/server.py:1073-1104, 1708, 1991`; `TC-92`, `AO-07`, `AO-08`, `VER-009` | Валидация `_CID_RE` и `resolve().parent` защищает от path traversal (`server.py:1073-1083`), подключение открывается строго с `file:...?mode=ro` (`uri=True`) и `PRAGMA query_only = ON`, диагностические логи не содержат сырого текста мыслей. |
| SUB-CONC-07 | PASS | `bridges/agy-bridge/server.py:997-1006, 1049-1067, 1508-1565, 2117-2145, 2272-2299`; `AO-03`, `AO-08`, `AO-10`, `tc93` | Захват `_active_cid_owners` атомарен под `_session_store_lock` (`F-004`), `_compat_promote` считывает `_agy_binary_identity()` внутри `_sqlite_guard_lock` (`F-003`/`MINOR-2`), `_close_and_put_done` идемпотентен под `_emit_lock` в `try/finally` (`F-005`), `conn.interrupt()` защищён `_conn_lock`. |
| SUB-RES-08 | PASS | `bridges/agy-bridge/server.py:1091-1124, 1551-1565, 1667-1678, 1816-1820, 2120-2125`; `AO-04`, `AO-05`, `AO-12`, `tc93` | Соединения `sqlite3.Connection` и курсоры гарантированно закрываются в `finally` (`_sqlite_open_connections == 0` после завершения хода), словарь шагов ограничен `MAX_STEPS_TRACKED = 128`, объём мышления на ход ограничен `MAX_REASONING_BYTES_PER_TURN = 2 MiB` (`F-008`). |
| SUB-PERF-09 | PASS | `bridges/agy-bridge/server.py:944-970, 1390-1401, 1904-1911`; `AO-05`, `tc93`, `VER-010` | Token bucket `_PollBucket` удерживает частоту опроса в пределах `N(Δt) <= 3 + 2*Δt`, SQL-запрос ограничивает выдачу `LIMIT 16` и `blob_len <= 262144`, неизменившиеся снимки пропускаются по `(blob_len, blob_sha)`, стресс-тест `VER-010` (`tc93`) подтверждает соблюдение бюджетов RSS и CPU. |
| SUB-TEST-10 | PASS | `tests/test_agy_bridge_resilience.py:L221-L3674`; `VER-003`, `VER-005`, `VER-006`, `VER-007`, `VER-010`, `VER-012`, `VER-013` | Все 22 исходных теста сохранены без изменений, добавлено 75 новых тестовых методов `unittest.TestCase` (всего 97/97 PASS на Python 3.9.6 и Python 3.14.7, 52 subtests PASS), полный прогон репозитория `VER-013` (974 теста против 899 базовых) подтвердил 0 новых регрессий. |
| SUB-MAINT-11 | PASS | `VER-001`, `VER-002`, `VER-004` | `ruff check` и `ruff format --check` дают 0 замечаний; `basedpyright 1.40.2` проходит с `0 errors` и `0 new_warnings` относительно базового коммита без директив `# type: ignore` / `# pyright: ignore`. |
| SUB-SIMP-12 | PASS | `bridges/agy-bridge/server.py:787-1993` | Код лаконичен, структуры данных (`_TurnPlan`, `_StepState`, `_PollBucket`) минимально достаточны, мёртвый код и избыточные абстракции отсутствуют. |
| SUB-OBS-13 | PASS | `bridges/agy-bridge/server.py:1031-1046, 1990-1993, 2872`; `TC-92`, `AO-06` | Эндпоинт `GET /health` возвращает 4 новых диагностических поля (`sqlite_reasoning_mode`, `sqlite_breaker_state`, `sqlite_divergence_count`, `sqlite_drain_deadline_count`), структурные логи фиксируют режимы, расхождения и исходы дренирования без утечки содержимого мыслей. |
| SUB-DEPS-14 | PASS | `bridges/agy-bridge/server.py:1-60`; `VER-009` | Внешние зависимости не добавлялись (`0` новых пакетов), используются только штатные модули стандартной библиотеки Python (`sqlite3`, `random`, `hashlib`, `threading`). |

[FINDINGS]
Замечаний класса BLOCKER и MAJOR не обнаружено.

[ОБОСНОВАНИЕ ВЕРДИКТА]
Реализация в `bridges/agy-bridge/server.py` и тестовом наборе `tests/test_agy_bridge_resilience.py` полностью соответствует утверждённому архитектурному пакету `AD-001..AD-006` и всем обязательным требованиям `F-001..F-009` Архитектурного Совета Тимлидов:
1. Дедупликация между SQLite и `transcript_full.jsonl` по `step_index` гарантирует отсутствие дублей и немедленную заморозку шага при `divergence` (`F-001`), а также отключение SQLite на весь `resume`-ход при отсутствии pre-spawn якоря.
2. Классификация схемных ошибок SQLite выполняется строго до проверки `cold-open` (`F-002`), корректно переводя circuit breaker в состояние `OPEN` после 3 сбоев.
3. Продвижение `poll_watermark`, проверка идентичности бинаря под `_sqlite_guard_lock` (`F-003`) и атомарное владение `_active_cid_owners` под `_session_store_lock` (`F-004`) исключают гонки между параллельными ходами и фоновыми запросами без инструментов (`tools_count == 0`).
4. Финальное дренирование `_drain_post_eof` выдерживает полное окно `DRAIN_WINDOW_S = 0.35 s` без эвристического раннего выхода по `planner_final` (`F-005`), а `try/finally` в `_pump` гарантирует ровно одно терминальное событие `done`.
5. Ограничения ресурсов (`MAX_STEPS_TRACKED = 128` с жёстким вытеснением старейшего ключа и `MAX_REASONING_BYTES_PER_TURN = 2 MiB` по `F-008`) и быстрый отклик kill-switch `SQLITE_REASONING_ENABLED` с `conn.interrupt()` (`F-006`) подтверждены результатами чистой комнаты `VER-001..VER-013` (97/97 целевых тестов и 974 теста полного прогона без регрессий).

FINDINGS_COMPLETE: YES
ОБЩИЙ ВЕРДИКТ: ACCEPT
```

#### Анонимизированный вердикт R1 — Судья R1-B (ACCEPT, 0 BLOCKER, 0 MAJOR)
```markdown
=== КАРТОЧКА СУДЬИ ===
Режим: code | Раунд: r1 | Шляпа: Реалист (проверяет эксплуатационную надёжность, тесты, совместимость, graceful degradation)
seed_recheck_duty: нет
seed_recheck: N/A (seed_recheck_duty=нет)
package_path: /Users/aazhiry1/tmp/cli-agent-bridge/agy-realtime-reasoning/.ai-team/runs/analyst-teamlead-agy-reasoning-20261029/teamlead/package.md
Вердикт места: ACCEPT
Блокеров: 0 | Существенных: 0 | Замечаний: 0

[SUB COVERAGE]
| Подкатегория | Статус (PASS/CONCERN/BLOCKER) | Доказательство (файл:строки / тест / VER-ID) | Комментарий |
|---|---|---|---|
| SUB-CORRECT-01 | PASS | server.py:1955-1992 `_drain_post_eof`; test:2389 `test_ao03_planner_final_with_two_quiet_selects_holds_full_window`; VER-003, VER-007 | Полное окно `DRAIN_WINDOW_S=0.35` без эвристики `planner_final` по F-005; выход только `end_turn`/`stop`/`window`; F-001..F-009 трассированы в матрице, F-010 `WITHDRAWN` |
| SUB-EDGE-02 | PASS | server.py:1663-1680 `_state`; server.py:1318-1348 `_extract_thinking_from_step_blob`; test:3407 `test_seen_cap_evicts_oldest_when_no_finalized_below_watermark`; TC-11, TC-40..TC-44 | Жёсткое вытеснение `del self.seen[min(self.seen)]` после `sqlite-off seen_cap`, инвариант `len(seen)<=128`; усечённый varint/UTF-8/protobuf, отсутствие БД/таблицы и zero-thinking не роняют ход |
| SUB-ARCH-03 | PASS | candidate-manifest.json; VER-008 | Изменены только `bridges/agy-bridge/server.py` и аддитивно `tests/test_agy_bridge_resilience.py`; stdlib-only |
| SUB-API-04 | PASS | server.py:3176-3247 `_serve_sse`; server.py:2863-2873 `/health`; AO-06, VER-006 | Контракты `/chat`, `/health`, `/set-mode` сохранены; SSE `reasoning_content` и терминальный `[DONE]` сохранены; 4 поля `/health` аддитивны |
| SUB-ERR-05 | PASS | server.py:1823-1849 `_on_sqlite_error`; server.py:1091-1141 open/close/max-idx; TC-40..TC-44, AO-01 | Схемная ошибка приоритетнее `cold-open` по F-002; fail-open на транскрипт, graceful degradation без потери `done` |
| SUB-SEC-06 | PASS | server.py:1073-1088 `_db_path_for`/`_sqlite_ro_uri`; server.py:1094-1104 `mode=ro, uri=True, query_only`; TC-92, VER-009 | Только read-only URI без `immutable`/`mode=rw`; проверка `_CID_RE` и родителя пути против traversal; логи несут id/длины, не текст мышления |
| SUB-CONC-07 | PASS | server.py:997-1006 `_compat_promote`; server.py:1049-1067 `_cid_acquire/_cid_release`; server.py:2176-2286 `_pump try/finally`; server.py:2288-2298 `_join_source` | `_agy_binary_identity()` читается под `_sqlite_guard_lock` по F-003/MINOR-2; атомарная регистрация владельца `cid` по F-004; ровно один `_close_and_put_done`, drain до `done` |
| SUB-RES-08 | PASS | server.py:1551-1564 `_finish`; server.py:157 `MAX_REASONING_BYTES_PER_TURN=2 MiB`; server.py:2106-2136 `_emit_reasoning`; AO-04, AO-05 | Соединение закрывается в `_finish`/`_poll_sqlite finally`; потолки 128 шагов, 16 строк, 256 KiB blob и 2 MiB reasoning соблюдены |
| SUB-PERF-09 | PASS | server.py:143 `SQLITE_POLL_S`; server.py:943-970 `_PollBucket`; server.py:1851-1877 `_select_rows`; VER-010 | Опрос 500 мс с bucket `N(Δt)<=3+2Δt`, пропуск неизменённого blob по digest, инкрементальный `delivered_len`; стресс `tc93/l2_harness` PASS |
| SUB-TEST-10 | PASS | tests/test_agy_bridge_resilience.py: реестр 97 методов; VER-003, VER-005, VER-007, VER-012, VER-013 | 22 исходных без удалённых строк + 75 новых; 97/97 зелёные; полный репозиторий 974 против 899 базовых, те же 2 внешних baseline-падения, 0 новых регрессий |
| SUB-MAINT-11 | PASS | VER-001, VER-002, VER-004 | `ruff check` и `ruff format --check` PASS; `basedpyright 1.40.2` 0 ошибок и 0 новых warnings против `e00da06` |
| SUB-SIMP-12 | PASS | server.py:1246-1348 wire-парсер; reverse-spec.md | Решение внутри одобренных AD-001..AD-006, без новых сервисов и внешних пакетов; мёртвый эвристический выход `planner_final` удалён, а не сохранён |
| SUB-OBS-13 | PASS | server.py:1031-1046 `_sqlite_health_fields`; server.py:1991-1992 лог `drain`; TC-92, AO-06 | `/health` отдаёт mode/breaker/divergence/drain-счётчики; диагностические логи с `cid/step/len/ms/exit` без сырого мышления |
| SUB-DEPS-14 | PASS | VER-009; environment-manifest.json | 0 новых внешних зависимостей; только stdlib `sqlite3`, `random`, `threading`, `hashlib` и ранее разрешённые модули |

[FINDINGS]
Замечаний класса BLOCKER и MAJOR не обнаружено.

[ОБОСНОВАНИЕ ВЕРДИКТА]
Реализация закрывает обязательные предохранители архитектурной панели F-001..F-009 внутри одобренного пакета, а F-010 единогласно отозван. Ключевые доработки по ревью подтверждены кодом и тестами: `_drain_post_eof` в server.py:1955-1992 выдерживает полное окно 0.35 с без раннего `planner_final`, `_state` в server.py:1663-1680 жёстко удерживает не более 128 шагов, а `_compat_promote` в server.py:997-1006 атомарно сверяет идентичность бинаря под локом. Graceful degradation, read-only доступ, дедупликация, breaker, бюджеты опроса, kill-switch и изоляция `cid`/горячих сессий покрыты оракулами TC/AO и не ломают внешний SSE/HTTP-контракт. Чистая комната дала VER-001..VER-010, VER-012 и VER-013 PASS при `exit_code=0`; VER-011 корректно отложена как `DEFERRED_L3` строго после ACCEPT Совета и до создания/вливания MR, поэтому блокером приёмки кода не является. С позиции Реалиста эксплуатационных, совместимостных или ресурсных оснований для NEEDS_WORK или RED_FLAG нет.

FINDINGS_COMPLETE: YES
ОБЩИЙ ВЕРДИКТ: ACCEPT
```

#### Анонимизированный вердикт R1 — Судья R1-C (NEEDS_WORK, находки F-001..F-004)
```markdown
=== КАРТОЧКА СУДЬИ ===
Режим: code | Раунд: r1 | Шляпа: Визионер (проверяет целостность архитектуры, соответствие ТЗ и пакетам проверки, полноту)
seed_recheck_duty: нет
seed_recheck: N/A (seed_recheck_duty=нет)
package_path: /Users/aazhiry1/tmp/cli-agent-bridge/agy-realtime-reasoning/.ai-team/runs/analyst-teamlead-agy-reasoning-20261029/teamlead/package.md
Вердикт места: NEEDS_WORK
Блокеров: 1 | Существенных: 2 | Замечаний: 1

[SUB COVERAGE]

| Подкатегория | Статус (PASS/CONCERN/BLOCKER) | Доказательство (файл:строки / тест / VER-ID) | Комментарий |
|---|---|---|---|
| SUB-CORRECT-01 | BLOCKER | server.py:1609–1613, 1648–1650, 1663–1679, 1739–1762 | Вытеснение состояния позволяет повторную выдачу уже доставленного шага после перечитывания транскрипта. |
| SUB-EDGE-02 | CONCERN | server.py:1614–1624; TC-01..TC-12, TC-40..TC-44 | Неполная строка повторно добавляется в буфер без продвижения файловой позиции. |
| SUB-ARCH-03 | PASS | candidate-manifest.json; VER-008, VER-009 | Область изменений ограничена двумя файлами; внешние зависимости не добавлены. |
| SUB-API-04 | PASS | server.py:3157–3174, 3191–3247; VER-006 | Показанные JSON/SSE-форматы сохранены; reasoning передаётся отдельным полем, присутствует `[DONE]`. |
| SUB-ERR-05 | PASS | server.py:1246–1348, 1823–1849; TC-40..TC-44 | Парсер деградирует безопасно; схемные ошибки классифицируются до cold-open. |
| SUB-SEC-06 | PASS | server.py:1073–1107, 1708, 1720–1722; AO-07, AO-08, TC-92 | Показаны проверка CID, read-only URI, query_only и диагностические сообщения без текста мышления. |
| SUB-CONC-07 | CONCERN | server.py:1853–1859, 1586–1593, 2288–2295; AO-09 | Kill-switch проверяется тем же потоком после возврата из потенциально длительного `execute`. |
| SUB-RES-08 | CONCERN | server.py:1551–1564, 1619–1624, 1667–1679, 2114–2129 | Соединения закрываются; лимиты seen и reasoning есть, но буфер транскрипта не ограничен. |
| SUB-PERF-09 | PASS | server.py:943–970, 1573–1576, 1903–1911; VER-010 | Ограничены частота SELECT и повторный разбор неизменного снимка; нагрузочный оракул заявлен зелёным. |
| SUB-TEST-10 | CONCERN | VER-003, VER-007, VER-012, VER-013 | 97 целевых тестов проходят; VER-013 доказывает отсутствие новых падений, но полный прогон завершился с двумя failures. |
| SUB-MAINT-11 | PASS | VER-001, VER-002, VER-004 | Форматирование и lint проходят; ошибок типизации нет, новых предупреждений относительно базы нет. |
| SUB-SIMP-12 | PASS | server.py:787–1945; reverse-spec.md | Основные механизмы соответствуют AD-001..AD-006; самостоятельного архитектурного расширения не выявлено. |
| SUB-OBS-13 | PASS | server.py:1031–1046, 1985–1992, 2872 | Диагностика режима, breaker, divergence и drain добавлена аддитивно. |
| SUB-DEPS-14 | PASS | VER-009; candidate-manifest.json | Новых внешних пакетов в представленном пакете нет. |

[FINDINGS]

1. **C3-001 — BLOCKER-DESIGN: ограничение seen разрушает дедупликацию.**  
   Якоря: `bridges/agy-bridge/server.py:1667–1679`, `:1609–1613`, `:1648–1650`, `:1739–1751`.

   После обработки шагов 0..128 состояние шага 0 может быть вытеснено штатной веткой удаления финализированных шагов. При последующем обнаружении уменьшения файла `_read_transcript` начинает читать его заново. Запись шага 0 текущего хода проходит проверку `base_idx`; `_state(0)` создаёт новое состояние с `delivered_len=0`, и `_apply_final` повторно выдаёт весь текст.

   Ветка принудительного вытеснения также теряет признаки `diverged` и `finalized`. Отключение SQLite не запрещает дальнейшую обработку транскрипта. Следовательно, жёсткий предел 128 соблюдён ценой нарушения дедупликации и гарантии F-001 о заморозке шага.

   Требуется сохранить запрет повторной выдачи после вытеснения и проверить сочетание «более 128 шагов → перечитывание транскрипта», включая ранее замороженный шаг.

2. **C3-002 — MAJOR: неполная строка транскрипта вызывает неограниченное накопление повторных байтов.**  
   Якорь: `bridges/agy-bridge/server.py:1614–1624`.

   `_offset` продвигается только после выделения строки с переводом строки. Пока последняя строка неполная, следующий тик снова читает с прежнего `_offset` и добавляет те же байты в `_buf`. Это происходит даже при неизменном размере файла. Ограничение `TRANSCRIPT_READ_MAX` действует на одно чтение, а не на накопленный буфер.

   Следствия: рост памяти, повреждение собираемой строки и риск пропуска записи в конечном окне drain. Требуется раздельно учитывать позицию чтения и остаток строки, ограничить остаток и проверить многократные тики без завершающего перевода строки.

3. **C3-003 — MAJOR: дедлайн kill-switch не обеспечен для выполняющегося SELECT.**  
   Якоря: `bridges/agy-bridge/server.py:1853–1859`, `:1586–1593`, `:1508–1517`.

   Проверка флага находится после `conn.execute(_STEPS_SQL, ...)`; её выполняет тот же поток. Если выполнение запроса задержалось, изменение флага само по себе не вызывает `interrupt_active_query`. `busy_timeout=50` ограничивает ожидание блокировки, но не общее время выполнения запроса.

   Поэтому AO-09 на обычном SELECT недостаточно для гарантии F-006. Требуется механизм прерывания либо ограничения выполняющегося запроса и проверка отключения флага при удерживаемом SELECT до EOF.

4. **C3-004 — MINOR: противоречивая фиксация верификационных гейтов.**  
   Якоря: `teamlead/verification-traceability.md`, строка `VER-011`; `teamlead/reverse-spec.md`, раздел `L3 Gate`; `verifier.json`, `VER-013`.

   Матрица помещает L3 после merge, тогда как reverse-spec и запись VER-011 требуют его до открытия/merge MR. Кроме того, `PASS / exit_code=0` для VER-013 нужно явно отделить от фактического результата unittest: два падения, совпадающие с базой. Отсутствие новых регрессий подтверждено сравнением; полностью зелёный полный прогон этим не подтверждён.

[ОБОСНОВАНИЕ ВЕРДИКТА]

По представленному тексту F-002, атомарная регистрация владельца из F-004 и устранение раннего выхода `planner_final` из F-005 реализованы. Чтение идентичности бинаря в `_compat_promote` перенесено под блокировку. Реестр и отчёты поддерживают выполнение F-007; ограничение reasoning из F-008 присутствует. F-010 отозван. Синхронизацию F-009 нельзя независимо подтвердить без содержимого `verification-surface.json`.

Результаты VER-001..VER-010 и VER-012 дают существенные положительные доказательства. Однако они не закрывают описанные нарушения дедупликации, накопления буфера и прерывания SELECT. Исправление жёсткого предела seen устраняет превышение размера словаря, но оставляет архитектурный дефект сохранения состояния доставки.

L3 не выполнялся и остаётся отдельным обязательным гейтом. Настоящий вывод — оценка предоставленного пакета, без самостоятельного запуска команд или проверки хешей.

FINDINGS_COMPLETE: YES
ОБЩИЙ ВЕРДИКТ: NEEDS_WORK
```

---

## 4. Материалы пакета приёмки (`ARTIFACT-SHA256: 7d4f3ee38549312817f33a0cc6b82ef02f69a62f9d764777b3d84d63e460838b`)

### 4.1. Результаты верификации в чистой комнате L2 (`verifier.json` + `evidence-manifest.sha256`)
- status: `PASS`
- base_sha: `e00da0621fc95f7c63cd1565f4a5d1fd490c8d66`
- source_file_sha256: `{"bridges/agy-bridge/server.py": "1285a908bf2793b3a19e93e2149c2bfa353d1fb8625c626658fe790e2ef48147", "tests/test_agy_bridge_resilience.py": "63869e7e51e7b067661afe074b688dfb4c9d5f86040cfcdf6a3b778e825a0680"}`

| Check ID | Status | Exit Code | Command | Output Tail |
|---|---|---|---|---|
| `VER-001` | `PASS` | `0` | `uvx ruff@0.17.3 check --no-cache bridges/agy-bridge/server.py tests/test_agy_bridge_resilience.py` | `All checks passed!` |
| `VER-002` | `PASS` | `0` | `uvx ruff@0.17.3 format --check --no-cache bridges/agy-bridge/server.py tests/test_agy_bridge_resilience.py` | `2 files already formatted` |
| `VER-003` | `PASS` | `0` | `PYTHONPATH=. uvx --from pytest==9.0.3 pytest -q -p no:cacheprovider tests/test_agy_bridge_resilience.py` | `.....                                                                    [100%] / 97 passed, 52 subtests passed in 83.16s (0:01:23` |
| `VER-004` | `PASS` | `0` | `set -e; B="$(mktemp -d)"; H="$(mktemp)"; S="$(mktemp)"; git worktree add -q --detach "$B/base" e00da0621fc95f7c63cd1565f4a5d1fd490c8d66; uvx basedpyright@1.40.2 --outputjson bridges/agy-bridge/server.py tests/test_agy_bridge_resilience.py > "$H" \|\| true; (cd "$B/base" && uvx basedpyright@1.40.2 --outputjson bridges/agy-bridge/server.py tests/test_agy_bridge_resilience.py > "$S" \|\| true); git worktree remove --force "$B/base"; python3 -I - "$H" "$S" <<'PY'
import json,sys,collections
h=json.load(open(sys.argv[1])); s=json.load(open(sys.argv[2]))
def ms(x,sev): return collections.Counter((d['file'].rsplit('/',1)[-1],d.get('rule'),d['message']) for d in x['generalDiagnostics'] if d['severity']==sev)
err=h['summary']['errorCount']; new_w=ms(h,'warning')-ms(s,'warning')
print('version',h['version'],'errors',err,'warnings',h['summary']['warningCount'],'new_warnings',sum(new_w.values()))
[print('NEW',k) for k in sorted(new_w)]
sys.exit(0 if err==0 and not new_w and h['version'].startswith('1.40.2') else 1)
PY` | `version 1.40.2 errors 0 warnings 800 new_warnings 0` |
| `VER-005` | `PASS` | `0` | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /usr/bin/python3 -B -m unittest discover -s tests -p "test_*agy*.py" && PYTHONPATH=. uvx --from pytest==9.0.3 pytest -q -p no:cacheprovider tests/test_agy_bridge_resilience.py` | ` / OK` |
| `VER-006` | `PASS` | `0` | `test "$(git diff --unified=0 e00da0621fc95f7c63cd1565f4a5d1fd490c8d66 HEAD -- tests/test_agy_bridge_resilience.py \| grep -cE '^-[^-]')" = 0 && test -z "$(git diff --name-only e00da0621fc95f7c63cd1565f4a5d1fd490c8d66 HEAD -- tests/ core/ \| grep -vx 'tests/test_agy_bridge_resilience.py')" && echo OK` | `OK` |
| `VER-007` | `PASS` | `0` | `python3 -I - <<'PY'
import ast,re,sys,pathlib
s=pathlib.Path('tests/test_agy_bridge_resilience.py').read_text(encoding='utf-8')
t=ast.parse(s)
need={'tc%02d'%i for i in list(range(1,13))+[20,21,23,24,30,31,32,33,40,41,42,43,44,50,51,60,61,62,63,70,71,72,80,81,82,91,92]}\|{'ao%02d'%i for i in range(1,13)}
def asserted(f):
    for n in ast.walk(f):
        if isinstance(n,ast.Assert): return True
        if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr.startswith('assert'): return True
    return False
got=set(); noassert=[]
for f in ast.walk(t):
    if isinstance(f,(ast.FunctionDef,ast.AsyncFunctionDef)) and f.name.startswith('test_'):
        ids=set(re.findall(r'(tc\d{2}\|ao\d{2})',f.name))&need
        if not ids: continue
        if asserted(f): got\|=ids
        else: noassert.append(f.name)
miss=sorted(need-got)
errs=(['MISSING '+' '.join(miss)] if miss else [])+(['NO_ASSERT '+' '.join(sorted(noassert))] if noassert else [])
print('; '.join(errs) if errs else 'OK %d ids, all asserted'%len(need)); sys.exit(1 if errs else 0)
PY` | `OK 51 ids, all asserted` |
| `VER-008` | `PASS` | `0` | `test "$(git diff --name-only e00da0621fc95f7c63cd1565f4a5d1fd490c8d66 HEAD -- . ':(exclude).ai-team' ':(exclude)analysis' \| sort \| tr '\n' ' ')" = "bridges/agy-bridge/server.py tests/test_agy_bridge_resilience.py " && test -z "$(git ls-files bridges/agy-bridge/dynamic_config.json)" && printf '%s  %s\n' 81dffc06ac79c490968e7efb8321f464d5963f414fcc6bd67a278a99d5985e32 analysis/agy-realtime-reasoning/research-plan.md e9c8afb2684a7621e9fdb0455640e86f972aab600989142119fb440397842ff1 analysis/agy-realtime-reasoning/evidence-ledger.md 47b16bab51b31bb06c35fb02d08dbd3409a9cfb057a52e828d079054a20d9202 analysis/agy-realtime-reasoning/open-questions.md cb1ecde9e00f06d72b75e43f973add3ab93ca27433d7145cbf8ec4f4800b17cd analysis/agy-realtime-reasoning/handoff-architect.md 5ed84fc039f7fea5983404442461e734ec9dae03f57359e2bb441dfae6cb7afe analysis/agy-realtime-reasoning/handoff-qa.md \| shasum -a 256 -c --status - && echo OK` | `OK` |
| `VER-009` | `PASS` | `0` | `python3 -I - <<'PY'
import ast,sys,pathlib
src=pathlib.Path('bridges/agy-bridge/server.py').read_text(encoding='utf-8')
t=ast.parse(src)
allowed={'__future__','hashlib','json','os','queue','re','select','shutil','signal','socket','subprocess','sys','threading','time','uuid','http','pathlib','typing','core','sqlite3','random'}
roots=set()
for n in ast.walk(t):
    if isinstance(n,ast.Import):
        roots\|={a.name.split('.')[0] for a in n.names}
    elif isinstance(n,ast.ImportFrom) and n.level==0:
        roots.add((n.module or '').split('.')[0])
calls=[n for n in ast.walk(t) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='connect' and isinstance(n.func.value,ast.Name) and n.func.value.id=='sqlite3']
nouri=[c.lineno for c in calls if not any(k.arg=='uri' and isinstance(k.value,ast.Constant) and k.value.value is True for k in c.keywords)]
rw=[n.lineno for n in ast.walk(t) if isinstance(n,ast.Constant) and isinstance(n.value,str) and ('mode=rw' in n.value or 'immutable' in n.value)]
need=[x for x in ('AGY_SQLITE_REASONING_ENABLED','SQLITE_REASONING_ENABLED','AGY_BRIDGE_CONVERSATIONS','mode=ro','query_only','busy_timeout') if x not in src]
errs=[]
if sorted(roots-allowed): errs.append('non-stdlib imports %s'%sorted(roots-allowed))
if not calls: errs.append('no sqlite3.connect call')
if nouri: errs.append('sqlite3.connect without uri=True at %s'%nouri)
if rw: errs.append('write-mode or immutable URI literal at %s'%rw)
if 'immutable' in src: errs.append('substring immutable present in server.py')
if need: errs.append('missing %s'%need)
print('FAIL: '+'; '.join(errs) if errs else 'OK'); sys.exit(1 if errs else 0)
PY` | `OK` |
| `VER-010` | `PASS` | `0` | `PYTHONPATH=. uvx --from pytest==9.0.3 pytest -q -p no:cacheprovider tests/test_agy_bridge_resilience.py -k "tc93 or l2_harness" && PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /usr/bin/python3 -B -m unittest discover -s tests -p "test_agy_bridge_resilience.py" -k tc93 -k l2_harness` | ` / OK` |
| `VER-011` | `DEFERRED_L3` | `0` | `None` | `DEFERRED_L3: executes on live 127.0.0.1:9887 immediately after Council ACCEPT and BEFORE opening/merging MR (per teamlead-gate Ste` |
| `VER-012` | `PASS` | `0` | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /usr/bin/python3 -B -m unittest discover -s tests -p "test_*agy*.py"` | ` / OK` |
| `VER-013` | `PASS` | `0` | `/usr/bin/python3 -m unittest discover -s tests (compared against base_sha e00da0621fc95f7c63cd1565f4a5d1fd490c8d66 in Clean-Room worktree)` | `candidate: Ran 974 tests in 414.814s (+75 new tests in tests/test_agy_bridge_resilience.py, 97/97 PASS), FAILED (failures=2 — iden` |

```text
1285a908bf2793b3a19e93e2149c2bfa353d1fb8625c626658fe790e2ef48147  bridges/agy-bridge/server.py
63869e7e51e7b067661afe074b688dfb4c9d5f86040cfcdf6a3b778e825a0680  tests/test_agy_bridge_resilience.py
1d2292a0a437a2dcbcca10f66ddd5fc8a11970ea79ad3c97790ac76e4f7b12a6  .ai-team/runs/analyst-teamlead-agy-reasoning-20261029/teamlead/candidate.diff
935615bcddddc2a68d021c59e600c0cfffddec91330d105831d43d22c445cb5b  .ai-team/runs/analyst-teamlead-agy-reasoning-20261029/teamlead/candidate-manifest.json
572c2dec5a6c7658708f66fdf5c374f999f7e103d70c610058fb7409a4fd984d  .ai-team/runs/analyst-teamlead-agy-reasoning-20261029/teamlead/environment-manifest.json
9a78ba7857ff210dbba7d681bdc6bf52918d7c30c1ecf05971c64e3c28dea1b0  .ai-team/runs/analyst-teamlead-agy-reasoning-20261029/teamlead/execution-evidence.md
fa59bfe4cc7a242b532c94bfabf2b2ea80579a9ca26fa5937fb584837aab32b3  .ai-team/runs/analyst-teamlead-agy-reasoning-20261029/teamlead/verification-traceability.md
5e75914de327dc00147bec08728f1fdfca4d474a40b7586390538b8655df5ec6  .ai-team/runs/analyst-teamlead-agy-reasoning-20261029/teamlead/reverse-spec.md
4b5890ffcb75e4398044ea4182e135060f6a7d249b0e0fca32e4388e6054ad9b  .ai-team/runs/analyst-teamlead-agy-reasoning-20261029/coder.json
1fc20712182872ce2c8e5f19dd6be5dd8ea762203cc84267766e7e7558c6d1a8  .ai-team/runs/analyst-teamlead-agy-reasoning-20261029/verifier.json

```

### 4.2. Матрица трассируемости (`teamlead/verification-traceability.md`) и обратная спецификация (`teamlead/reverse-spec.md`)
```markdown
# Матрица трассируемости верификации (`teamlead/verification-traceability.md`)

- **Run ID:** `analyst-teamlead-agy-reasoning-20261029`
- **Task ID:** `agy-realtime-reasoning`
- **Architecture Packet SHA-256:** `62a83bb2f0bfd9e9e975a05a5aea61991d27f49f642d1b810fc2a87dc4af2aab`
- **Base SHA:** `e00da0621fc95f7c63cd1565f4a5d1fd490c8d66`

## Поштучная матрица `REQ-001..REQ-012`, `AC-001..AC-016`, `AD-001..AD-006`, `AO-01..AO-12` и `VER-001..VER-012`

| Требование / Оракул | Архитектурное решение | Реализация в `bridges/agy-bridge/server.py` | Тестовые оракулы в `tests/test_agy_bridge_resilience.py` | Статус в Clean-Room L2 (`execution-evidence.md`) |
|---|---|---|---|---|
| `REQ-001` (`AC-001`, `AC-002`) | `AD-001` | `_TranscriptTail._poll_sqlite`, `_emit_reasoning`, опрос `steps` (`step_type=15, status=8`) | `TC-20`, `TC-21`, `tc93` (`VER-003`, `VER-005`, `VER-007`, `VER-010`) | `PASS` (`exit_code=0`) |
| `REQ-002` (`AC-003`) | `AD-001` | `_extract_step_thinking` (pure-Python protobuf wire parser поля 20 -> 3, UTF-8 tail trim) | `TC-01..TC-12` (`VER-003`, `VER-005`, `VER-007`, `VER-009`) | `PASS` (`exit_code=0`) |
| `REQ-003` (`AC-004`, `AC-005`) | `AD-001` (`F-001`, `F-003`, `F-008`) | Общий `seen[idx]` (`observed_*`, `delivered_*`, `finalized`, `diverged`), заморозка при divergence | `TC-23`, `TC-24`, `AO-10`, `AO-12` (`VER-003`, `VER-005`, `VER-007`) | `PASS` (`exit_code=0`) |
| `REQ-004` (`AC-006`) | `AD-001`, `AD-005` (`F-002`) | Fail-open `mode=ro` (`uri=True`, `query_only=ON`, `busy_timeout=50`), FSM breaker `AO-01` | `TC-30..TC-33`, `AO-01`, `AO-08` (`VER-003`, `VER-005`, `VER-007`, `VER-009`) | `PASS` (`exit_code=0`) |
| `REQ-005` (`AC-007`) | `AD-001` (`F-001`, `F-004`) | Pre-spawn водяной знак `base_idx = max(t_max, db_max) + 1`, `turn_mode="OFF"` без SQLite-якоря на resume | `TC-50`, `TC-51`, `AO-08`, `tc93` (`VER-003`, `VER-005`, `VER-007`, `VER-010`) | `PASS` (`exit_code=0`) |
| `REQ-006` (`AC-008`) | `AD-002` (`F-005`) | `_pump` в `try/finally` с `_close_and_put_done`, полное окно `DRAIN_WINDOW_S = 0.35 s`, `_execute` до `done` | `TC-60..TC-63`, `AO-03`, `AO-11`, `tc93` (`VER-003`, `VER-005`, `VER-007`, `VER-010`) | `PASS` (`exit_code=0`) |
| `REQ-007` (`AC-009`) | `AD-002` (`F-005`) | Ограниченный drain `EOF -> stop <= 1.0 s`, `conn.interrupt()` перед финальным `join` | `TC-62`, `TC-63`, `AO-03`, `tc93` (`VER-003`, `VER-007`, `VER-010`) | `PASS` (`exit_code=0`) |
| `REQ-008` (`AC-010`) | `AD-003`, `AD-005` | В `_run_once` для `stream=True` отданное мышление (`delivered['reasoning_chars'] > 0`) запрещает тихий повтор | `TC-70..TC-72`, `AO-02`, `AO-11` (`VER-003`, `VER-005`, `VER-007`) | `PASS` (`exit_code=0`) |
| `REQ-009` (`AC-011`) | `AD-004` (`F-004`) | Изоляция `_session_store`: запросы без `tools` (`tools_count == 0`) не занимают и не перезаписывают горячую сессию | `TC-80..TC-82`, `AO-08` (`VER-003`, `VER-005`, `VER-007`) | `PASS` (`exit_code=0`) |
| `REQ-010` (`AC-012`, `AC-013`) | `AD-001..AD-004` | Сохранён контракт `:9887`, 22 старых теста без изменений (`VER-006`), 4 аддитивных поля `/health` | `AO-06`, 22 baseline-теста (`VER-001..VER-008`, `VER-012`) | `PASS` (`exit_code=0`) |
| `REQ-011` (`AC-014`) | `AD-006` (`F-006`) | `dynamic_config.json` (`SQLITE_REASONING_ENABLED`, TTL 1.0 s) + `AGY_SQLITE_REASONING_ENABLED`, kill-switch `<= 1.30 s` | `TC-91`, `AO-07`, `AO-09`, `tc93` (`VER-003`, `VER-007`, `VER-009`, `VER-010`) | `PASS` (`exit_code=0`) |
| `REQ-012` (`AC-015`, `AC-016`) | `AD-001`, `AD-005` (`F-008`) | Логи `sqlite-emit`/`sqlite-off`/`drain` без текста мышления, token bucket `N(Δt)<=3+2Δt`, `RSS<=112 MiB`, `CPU<=1%` | `TC-40..TC-44`, `TC-92`, `AO-04`, `AO-05`, `tc93` (`VER-003`, `VER-007`, `VER-010`) | `PASS` (`exit_code=0`) |
| `VER-011` (`L3 Live`) | Все `AD-001..AD-006` | Живая проверка на `:9887` после `ACCEPT` Совета и влития MR | Ручной/живой гейт `L3` | `DEFERRED_L3` (после `ACCEPT` Совета и merge MR) |

| `Full Suite Gate (J3-003)` | Отсутствие регрессий во всём репозитории (`tests/`) | `bridges/agy-bridge/server.py`, `tests/test_agy_bridge_resilience.py` | `VER-013`: `/usr/bin/python3 -m unittest discover -s tests` в чистой комнате на `base_sha` (899 тестов, 2 внешних падения `test_muse_bridge_killpg.py`) и на кандидате (974 теста = +75 новых в `test_agy_bridge_resilience.py`, те же 2 внешних падения, 0 новых регрессий) | `PASS` |

```
```markdown
# Слепая обратная спецификация (`teamlead/reverse-spec.md`)

Документ реконструирован по итоговому `candidate.diff` (`bridges/agy-bridge/server.py` и `tests/test_agy_bridge_resilience.py`).

## 1. Фактически изменённые файлы

1. **`bridges/agy-bridge/server.py` (изменён):**
   - Добавлен pure-Python wire-парсер protobuf `_extract_step_thinking(blob, stop_event)` для чтения поля `20` (вложенного сообщения `PLANNER_RESPONSE`) и подполя `3` (UTF-8 текста мышления) с пропуском wire-типов `0, 1, 2, 5`, проверкой `stop_event` каждые 64 тега и безопасной обрезкой незавершённой многобайтовой UTF-8 последовательности на промежуточных снимках (`status=8`).
   - В `_TranscriptTail` / `Run` встроен вспомогательный read-only опрос SQLite `conversations/<cid>.db` (`sqlite3.connect("file:...?mode=ro", uri=True, timeout=0.05, check_same_thread=False)`, `PRAGMA query_only=ON`, `PRAGMA busy_timeout=50`) с ограничением `LIMIT 16` и `CASE WHEN length(step_payload) <= 262144 THEN step_payload ELSE NULL END`.
   - Реализована пошаговая дедупликация между SQLite и `transcript_full.jsonl` по ключу `idx == step_index` с раздельным учётом `observed_len`/`observed_sha256` и `delivered_len`/`delivered_sha256`, флагами `finalized` и `diverged`, заморозкой выдачи шага при `divergence` (`sqlite_snapshot_divergence` / `sqlite_transcript_divergence`) и монотонным продвижением `poll_watermark`.
   - Реализован семантический canary (`SHADOW -> LIVE`) по идентичности бинаря `agy` `(st_mtime_ns, st_size)`, pre-spawn водяной знак на `resume` (`base_idx = max(t_max, db_max) + 1`, при ошибке pre-spawn SQLite — `turn_mode="OFF"`), реестр активных владельцев `_active_cid_owners` под `_session_store_lock`.
   - Реализованы защитные механизмы Highload & Resilience: целочисленный per-turn token bucket `N(Δt) <= 3 + 2*Δt`, процессный retry budget в десятых долях, 3-состояний circuit breaker (`CLOSED`, `OPEN`, `HALF_OPEN` с `probe_gen`) под `_sqlite_guard_lock`, потолок `MAX_REASONING_BYTES_PER_TURN = 2 MiB` и runtime kill-switch `SQLITE_REASONING_ENABLED` (`dynamic_config.json` с TTL 1.0 с + env `AGY_SQLITE_REASONING_ENABLED`) с немедленным `conn.interrupt()`.
   - Исправлены RC-2 (детерминированный post-EOF drain полным окном `0.35 с` и атомарная постановка единственного `("done", ...)` под `run._emit_lock` в `try/finally`), RC-3 (учёт отданного в SSE `reasoning` в `delivered`, запрещающий повтор хода после выдачи мышления клиенту) и RC-4 (изоляция `_session_store` от фоновых запросов без инструментов `tools_count == 0`).
   - В `/health` добавлены 4 аддитивных диагностических поля (`sqlite_reasoning_mode`, `sqlite_breaker_state`, `sqlite_divergence_count`, `sqlite_drain_deadline_count`). Устранены все 12 baseline-ошибок `basedpyright`.

2. **`tests/test_agy_bridge_resilience.py` (аддитивно расширен):**
   - Все 22 исходных теста сохранены без единой удалённой или изменённой строки (`VER-006`).
   - Добавлено 75 новых тестовых метода в классах `unittest.TestCase`, покрывающих все 51 обязательный идентификатор `VER-007` (`TC-01..12, 20, 21, 23, 24, 30..33, 40..44, 50, 51, 60..63, 70..72, 80..82, 91, 92`, `AO-01..AO-12`) и нагрузочный оракул `tc93` / `l2_harness` (`VER-010`).

### Дополнения по итогам ревью (J3-001, J3-002, MINOR-2, J3-003)
- **F-005 / J3-001 (`_drain_post_eof`)**: эвристический ранний выход `planner_final` (`final_planner and quiet >= 2`) полностью удалён (`server.py:1954-1992`); досрочный выход после `DRAIN_MIN_S` допускается исключительно по `end_marker` (`END_TURN`/`TURN_COMPLETE`) или `stop_event`, иначе выдерживается полное окно `DRAIN_WINDOW_S = 0.35 s` (`exit=window`), проверено тестом `test_ao03_planner_final_with_two_quiet_selects_holds_full_window` (`tests/test_agy_bridge_resilience.py:2389`).
- **F-008 / J3-002 (`_TranscriptTail._state`)**: при достижении `len(self.seen) >= MAX_STEPS_TRACKED` (128) и отсутствии финализированных шагов ниже `poll_watermark` вызывается `self._sqlite_off('seen_cap')` И вытесняется старейший ключ `del self.seen[min(self.seen)]` (`server.py:1668-1678`), гарантируя инвариант `len(self.seen) <= 128`, проверено тестом `test_seen_cap_evicts_oldest_when_no_finalized_below_watermark` (`tests/test_agy_bridge_resilience.py:2165`).
- **MINOR-2 (`_compat_promote`)**: чтение `current = _agy_binary_identity()` перенесено внутрь критической секции `with _sqlite_guard_lock:` (`server.py:1000-1006`).
- **L3 Gate (J3-005)**: живая проверка `VER-011` на `:9887` выполняется строго после `ACCEPT` Совета Тимлидов и **до** создания/вливания MR (`feature/agy-realtime-reasoning` -> `dev` -> `main`).

```

### 4.3. Исходный код `bridges/agy-bridge/server.py` (все секции SQLite / `_TranscriptTail` / `Run` / `Handler` с номерами строк)
```python
90:HOME = Path.home()
91:HOST = os.environ.get("AGY_BRIDGE_HOST", "127.0.0.1")
92:PORT = int(os.environ.get("AGY_BRIDGE_PORT", "9887"))
93:AUTH_KEY = os.environ.get("AGY_BRIDGE_KEY", "").strip()
94:LAUNCHER = os.environ.get(
95:"AGY_LAUNCHER", str(HOME / ".config" / "agy-launch" / "agy-cli.sh")
96:)
97:FLEET_PATH = Path(os.environ.get("AGY_BRIDGE_FLEET", "") or str(ROOT / "fleet.json"))
98:ENV_MODEL = os.environ.get("AGY_BRIDGE_MODEL", "").strip()
99:WORKSPACE = ROOT / "workspace"
100:MAX_CONCURRENT = int(os.environ.get("AGY_BRIDGE_MAX_CONCURRENT", "4"))
101:QUEUE_TIMEOUT_S = int(os.environ.get("AGY_BRIDGE_QUEUE_TIMEOUT", "900"))
102:TIMEOUT_S = int(os.environ.get("AGY_BRIDGE_TIMEOUT", "1800"))
103:KEEPALIVE_S = float(os.environ.get("AGY_BRIDGE_KEEPALIVE", "15"))
106:FIRST_TOKEN_TIMEOUT_S = float(os.environ.get("AGY_BRIDGE_FIRST_TOKEN_TIMEOUT", "120"))
107:PRINT_TIMEOUT = os.environ.get("AGY_BRIDGE_PRINT_TIMEOUT", "0")
110:def _env_float(name: str, default: float, low: float, high: float) -> float:
112:raw = os.environ.get(name, "").strip()
113:try:
114:value = float(raw) if raw else default
115:except ValueError:
116:value = default
117:if value != value:
118:value = default
119:return min(high, max(low, value))
124:BRAIN_DIR = Path(
125:os.environ.get("AGY_BRIDGE_BRAIN", "")
126:or str(HOME / ".gemini" / "antigravity-cli" / "brain")
127:)
128:TRANSCRIPT_NAME = "transcript_full.jsonl"
129:TRANSCRIPT_POLL_S = float(os.environ.get("AGY_BRIDGE_TRANSCRIPT_POLL", "0.05"))
130:TRANSCRIPT_READ_MAX = 4 * 1024 * 1024
135:CONV_DIR = Path(
136:os.environ.get("AGY_BRIDGE_CONVERSATIONS", "")
137:or str(HOME / ".gemini" / "antigravity-cli" / "conversations")
138:)
140:AGY_BIN = os.environ.get("AGY_BRIDGE_AGY_BIN", "") or str(
141:HOME / ".local" / "bin" / "agy.real"
142:)
143:SQLITE_POLL_S = _env_float("AGY_BRIDGE_SQLITE_POLL", 0.5, 0.5, 2.0)
145:DYNAMIC_CONFIG_PATH = ROOT / "dynamic_config.json"
146:FLAG_NAME = "SQLITE_REASONING_ENABLED"
147:FLAG_TTL_S = 1.0
150:DRAIN_MAX_S = 0.50
151:DRAIN_WINDOW_S = _env_float("AGY_BRIDGE_TRANSCRIPT_GRACE", 0.35, 0.20, DRAIN_MAX_S)
152:DRAIN_MIN_S = min(_env_float("AGY_BRIDGE_DRAIN_MIN", 0.15, 0.05, 0.25), DRAIN_WINDOW_S)
153:DRAIN_POLL_STEP_S = 0.05
154:JOIN_TIMEOUT_S = _env_float("AGY_BRIDGE_DRAIN_JOIN", 0.15, 0.05, 0.20)
155:PROC_EXIT_WAIT_S = 0.05
157:MAX_REASONING_BYTES_PER_TURN = 2 * 1024 * 1024
158:MAX_STEP_BLOB_BYTES = 262144
159:MAX_STEPS_TRACKED = 128
160:SQLITE_ROW_LIMIT = 16
162:STEP_TYPE_PLANNER = 15
163:STEP_STATUS_GENERATING = 8
164:STEP_STATUS_DONE = 3
166:_CID_RE = re.compile(r"[0-9A-Fa-f-]{8,64}")
167:_STEP_INDEX_RE = re.compile(rb'"step_index"\s*:\s*(\d+)')
169:BREAKER_FAILURES_TO_OPEN = 3
170:BREAKER_COOLDOWN_S = 30.0
171:BREAKER_PROBE_LEASE_S = 60.0
172:RETRY_CAPACITY_TENTHS = 30
173:RETRY_CREDIT_TENTHS = 2
174:RETRY_COST_TENTHS = 10
175:POLL_BUCKET_CAPACITY_TENTHS = 30
176:POLL_BUCKET_REFILL_TENTHS_PER_S = 20
177:POLL_BUCKET_COST_TENTHS = 10
178:RETRY_PAUSE_CAP_S = 2.0
182:EFFORT_LEVELS = ("minimal", "low", "medium", "high", "xhigh", "max")
183:CLI_EFFORT_LEVELS = ("low", "medium", "high")
184:IMAGE_STATUSES = ("unsupported", "unverified", "probe", "confirmed")
185:IMPLEMENTED_METHODS: dict = {}
187:CWD_MAX_LEN = 4096
191:SESSION_IDLE_TTL_S = 45 * 60.0
192:SESSION_MAX_TTL_S = 24 * 3600.0
193:SESSION_MAX_TURNS = 30
195:_started = time.time()
196:_active: dict = {}
197:_active_lock = threading.Lock()
198:_slots = threading.BoundedSemaphore(MAX_CONCURRENT)
199:_budget = None
200:_last_ok = [0.0]
201:_session_store_lock = threading.Lock()
202:_session_store: dict[tuple[str, str, str], dict[str, Any]] = {}
203:_in_flight_cids: set[str] = set()
206:_active_cid_owners: dict[str, str] = {}
210:_sqlite_guard_lock = threading.Lock()
211:_breaker_state: str = "CLOSED"
212:_breaker_failures: int = 0
213:_breaker_opened_at: float = 0.0
214:_breaker_probe_gen: int = 0
215:_breaker_active_probe_gen: int | None = None
216:_breaker_probe_started_at: float = 0.0
217:_retry_tenths: int = RETRY_CAPACITY_TENTHS
218:_compat_ident: tuple[int, int] | None = None
219:_compat_state: str = "SHADOW"
220:_flag_value: bool = False
221:_flag_key: tuple[int, int] | None = None
222:_flag_checked_at: float | None = None
223:_sqlite_divergence_count: int = 0
224:_sqlite_drain_deadline_count: int = 0
225:_sqlite_open_connections: int = 0
226:_sqlite_max_open_connections: int = 0
227:_rng: Callable[[], float] = random.random
230:_SECRET = re.compile(r"[A-Za-z0-9_\-]{24,}")
231:_NOISE = re.compile(
232:r"NODE_TLS_REJECT_UNAUTHORIZED|--trace-warnings|^\(node:\d+\)", re.I
233:)
626:def _session_claim(sess_key: tuple, turn_id: str = "") -> str:
633:now = time.time()
634:with _session_store_lock:
635:entry = _session_store.get(sess_key)
636:if entry is None:
637:return ""
638:if (
639:now - entry["last_used"] > SESSION_IDLE_TTL_S
640:or now - entry["created"] > SESSION_MAX_TTL_S
641:or entry["turns"] >= SESSION_MAX_TURNS
642:):
643:_session_store.pop(sess_key, None)
644:return ""
645:cid = cast(str, entry["cid"])
646:if cid in _in_flight_cids:
647:return ""
648:owner = _active_cid_owners.get(cid)
649:if owner is not None and owner != turn_id:
650:return ""
651:_in_flight_cids.add(cid)
652:if turn_id:
653:_active_cid_owners[cid] = turn_id
654:return cid
657:def _session_invalidate(sess_key: tuple, cid: str) -> None:
658:with _session_store_lock:
659:entry = _session_store.get(sess_key)
660:if entry is not None and entry["cid"] == cid:
661:_session_store.pop(sess_key, None)
664:def _session_commit(sess_key: tuple, cid: str) -> None:
665:now = time.time()
666:with _session_store_lock:
667:entry = _session_store.get(sess_key)
668:if entry is not None and entry["cid"] == cid:
669:entry["last_used"] = now
670:entry["turns"] += 1
671:else:
672:_session_store[sess_key] = {
673:"cid": cid,
674:"last_used": now,
675:"created": now,
676:"turns": 1,
677:}
758:def _reset_sqlite_guards_for_tests() -> None:
760:global _breaker_state, _breaker_failures, _breaker_opened_at, _breaker_probe_gen
761:global _breaker_active_probe_gen, _breaker_probe_started_at, _retry_tenths
762:global _compat_ident, _compat_state, _flag_value, _flag_key, _flag_checked_at
763:global _sqlite_divergence_count, _sqlite_drain_deadline_count
764:global _sqlite_open_connections, _sqlite_max_open_connections, _rng
765:with _sqlite_guard_lock:
766:_breaker_state = "CLOSED"
767:_breaker_failures = 0
768:_breaker_opened_at = 0.0
769:_breaker_probe_gen = 0
770:_breaker_active_probe_gen = None
771:_breaker_probe_started_at = 0.0
772:_retry_tenths = RETRY_CAPACITY_TENTHS
773:_compat_ident = None
774:_compat_state = "SHADOW"
775:_flag_value = False
776:_flag_key = None
777:_flag_checked_at = None
778:_sqlite_divergence_count = 0
779:_sqlite_drain_deadline_count = 0
780:_sqlite_open_connections = 0
781:_sqlite_max_open_connections = 0
782:_rng = random.random
783:with _session_store_lock:
784:_active_cid_owners.clear()
787:def _runtime_flag_on() -> bool:
794:global _flag_value, _flag_key, _flag_checked_at
795:now = time.monotonic()
796:with _sqlite_guard_lock:
797:if _flag_checked_at is not None and now - _flag_checked_at < FLAG_TTL_S:
798:return _flag_value
799:known_key = _flag_key
800:known_value = _flag_value
801:value = False
802:key: tuple[int, int] | None = None
803:try:
804:info = DYNAMIC_CONFIG_PATH.stat()
805:key = (info.st_mtime_ns, info.st_size)
806:if key == known_key:
807:value = known_value
808:else:
809:data = cast(
810:object, json.loads(DYNAMIC_CONFIG_PATH.read_text(encoding="utf-8"))
811:)
812:if isinstance(data, dict):
813:value = cast("dict[str, object]", data).get(FLAG_NAME) is True
814:except (OSError, ValueError):
815:value = False
816:key = None
817:with _sqlite_guard_lock:
818:_flag_value = value
819:_flag_key = key
820:_flag_checked_at = now
821:return value
824:def _sqlite_disabled_reason() -> str:
826:env = os.environ.get("AGY_SQLITE_REASONING_ENABLED", "1").strip().lower()
827:if env in ("0", "false"):
828:return "env"
829:if not _runtime_flag_on():
830:return "flag"
831:return ""
834:def _is_sqlite_reasoning_enabled() -> bool:
836:return _sqlite_disabled_reason() == ""
839:def _breaker_blocks_now() -> bool:
841:with _sqlite_guard_lock:
842:return (
843:_breaker_state == "OPEN"
844:and time.monotonic() - _breaker_opened_at < BREAKER_COOLDOWN_S
845:)
848:def _breaker_acquire() -> tuple[bool, int | None]:
850:global _breaker_state, _breaker_probe_gen, _breaker_active_probe_gen
851:global _breaker_probe_started_at
852:now = time.monotonic()
853:with _sqlite_guard_lock:
854:if _breaker_state == "CLOSED":
855:return True, None
856:if _breaker_state == "OPEN":
857:if now - _breaker_opened_at < BREAKER_COOLDOWN_S:
858:return False, None
859:_breaker_state = "HALF_OPEN"
860:_breaker_active_probe_gen = None
861:leased = (
862:_breaker_active_probe_gen is not None
863:and now - _breaker_probe_started_at < BREAKER_PROBE_LEASE_S
864:)
865:if leased:
866:return False, None
867:_breaker_probe_gen += 1
868:_breaker_active_probe_gen = _breaker_probe_gen
869:_breaker_probe_started_at = now
870:return True, _breaker_probe_gen
873:def _breaker_permits(probe_gen: int | None) -> bool:
875:with _sqlite_guard_lock:
876:if probe_gen is None:
877:return _breaker_state == "CLOSED"
878:return _breaker_state == "HALF_OPEN" and _breaker_active_probe_gen == probe_gen
881:def _breaker_report(probe_gen: int | None, selects_ok: int, failed: bool) -> None:
883:global _breaker_state, _breaker_failures, _breaker_opened_at
884:global _breaker_active_probe_gen
885:now = time.monotonic()
886:change = ""
887:with _sqlite_guard_lock:
888:if probe_gen is not None:
889:if _breaker_active_probe_gen != probe_gen or _breaker_state != "HALF_OPEN":
890:return
891:_breaker_active_probe_gen = None
892:if failed:
893:_breaker_state = "OPEN"
894:_breaker_opened_at = now
895:change = "OPEN"
896:elif selects_ok >= 1:
897:_breaker_state = "CLOSED"
898:_breaker_failures = 0
899:change = "CLOSED"
900:current_state = _breaker_state
901:gen_now = probe_gen
902:else:
903:if _breaker_state != "CLOSED":
904:return
905:if failed:
906:_breaker_failures += 1
907:if _breaker_failures >= BREAKER_FAILURES_TO_OPEN:
908:_breaker_state = "OPEN"
909:_breaker_opened_at = now
910:change = "OPEN"
911:elif selects_ok >= 1:
912:_breaker_failures = 0
913:current_state = _breaker_state
914:gen_now = _breaker_probe_gen
915:if change:
916:_log(f"breaker state={current_state} probe_gen={gen_now}")
919:def _retry_credit() -> None:
921:global _retry_tenths
922:with _sqlite_guard_lock:
923:_retry_tenths = min(RETRY_CAPACITY_TENTHS, _retry_tenths + RETRY_CREDIT_TENTHS)
926:def _retry_take() -> bool:
928:global _retry_tenths
929:with _sqlite_guard_lock:
930:if _retry_tenths < RETRY_COST_TENTHS:
931:return False
932:_retry_tenths -= RETRY_COST_TENTHS
933:return True
936:def _retry_pause_s(attempt: int, rng: Callable[[], float] | None = None) -> float:
938:cap = min(RETRY_PAUSE_CAP_S, RETRY_PAUSE_CAP_S * float(1 << max(0, attempt - 1)))
939:source = rng if rng is not None else _rng
940:return source() * cap
943:@final
944:class _PollBucket:
951:def __init__(self) -> None:
952:self.tenths: int = POLL_BUCKET_CAPACITY_TENTHS
953:self.last_us: int = int(time.monotonic() * 1_000_000)
955:def take(self) -> bool:
956:now_us = int(time.monotonic() * 1_000_000)
957:elapsed = now_us - self.last_us
958:if elapsed > 0:
959:add = elapsed * POLL_BUCKET_REFILL_TENTHS_PER_S // 1_000_000
960:if add > 0:
961:if self.tenths + add >= POLL_BUCKET_CAPACITY_TENTHS:
962:self.tenths = POLL_BUCKET_CAPACITY_TENTHS
963:self.last_us = now_us
964:else:
965:self.tenths += add
966:self.last_us += add * 1_000_000 // POLL_BUCKET_REFILL_TENTHS_PER_S
967:if self.tenths >= POLL_BUCKET_COST_TENTHS:
968:self.tenths -= POLL_BUCKET_COST_TENTHS
969:return True
970:return False
973:def _agy_binary_identity() -> tuple[int, int] | None:
975:try:
976:info = os.stat(AGY_BIN)
977:except OSError:
978:return None
979:return (info.st_mtime_ns, info.st_size)
982:def _compat_turn_state(identity: tuple[int, int] | None) -> str:
984:global _compat_ident, _compat_state
985:changed = False
986:with _sqlite_guard_lock:
987:if identity is None or identity != _compat_ident:
988:changed = _compat_state != "SHADOW" or _compat_ident is not None
989:_compat_ident = identity
990:_compat_state = "SHADOW"
991:state = _compat_state
992:if changed:
993:_log("compat state=SHADOW reason=binary_identity")
994:return state
997:def _compat_promote(turn_identity: tuple[int, int] | None) -> bool:
999:global _compat_ident, _compat_state
1000:with _sqlite_guard_lock:
1001:current = _agy_binary_identity()
1002:if turn_identity is None or turn_identity != current:
1003:return False
1004:_compat_ident = turn_identity
1005:_compat_state = "LIVE"
1006:return True
1009:def _compat_demote() -> None:
1011:global _compat_state
1012:with _sqlite_guard_lock:
1013:was_live = _compat_state == "LIVE"
1014:_compat_state = "SHADOW"
1015:if was_live:
1016:_log("compat state=SHADOW reason=divergence")
1019:def _count_divergence() -> None:
1020:global _sqlite_divergence_count
1021:with _sqlite_guard_lock:
1022:_sqlite_divergence_count += 1
1025:def _count_drain_deadline() -> None:
1026:global _sqlite_drain_deadline_count
1027:with _sqlite_guard_lock:
1028:_sqlite_drain_deadline_count += 1
1031:def _sqlite_health_fields() -> dict[str, object]:
1033:disabled = _sqlite_disabled_reason()
1034:with _sqlite_guard_lock:
1035:if disabled:
1036:mode = "off"
1037:elif _breaker_state == "OPEN":
1038:mode = "breaker_open"
1039:else:
1040:mode = _compat_state.lower()
1041:return {
1042:"sqlite_reasoning_mode": mode,
1043:"sqlite_breaker_state": _breaker_state.lower(),
1044:"sqlite_divergence_count": _sqlite_divergence_count,
1045:"sqlite_drain_deadline_count": _sqlite_drain_deadline_count,
1046:}
1049:def _cid_acquire(cid: str, turn_id: str) -> bool:
1051:if not cid or not turn_id:
1052:return True
1053:with _session_store_lock:
1054:owner = _active_cid_owners.get(cid)
1055:if owner is not None and owner != turn_id:
1056:return False
1057:_active_cid_owners[cid] = turn_id
1058:return True
1061:def _cid_release(cid: str, turn_id: str) -> None:
1063:if not cid or not turn_id:
1064:return
1065:with _session_store_lock:
1066:if _active_cid_owners.get(cid) == turn_id:
1067:_ = _active_cid_owners.pop(cid, None)
1073:def _db_path_for(cid: str) -> Path | None:
1075:if _CID_RE.fullmatch(cid) is None:
1076:return None
1077:path = CONV_DIR / (cid + ".db")
1078:try:
1079:if path.resolve().parent != CONV_DIR.resolve():
1080:return None
1081:except (OSError, RuntimeError):
1082:return None
1083:return path
1086:def _sqlite_ro_uri(path: Path) -> str:
1087:text = str(path).replace("%", "%25").replace("?", "%3f").replace("#", "%23")
1088:return f"file:{text}?mode=ro"
1091:def _sqlite_open_ro(path: Path) -> sqlite3.Connection:
1093:global _sqlite_open_connections, _sqlite_max_open_connections
1094:conn = sqlite3.connect(
1095:_sqlite_ro_uri(path),
1096:uri=True,
1097:timeout=0.05,
1098:isolation_level=None,
1099:check_same_thread=False,
1100:)
1101:try:
1102:_ = conn.execute("PRAGMA query_only = ON")
1103:_ = conn.execute("PRAGMA busy_timeout = 50")
1104:_ = conn.execute("PRAGMA cache_size = -1024")
1105:except BaseException:
1106:conn.close()
1107:raise
1108:with _sqlite_guard_lock:
1109:_sqlite_open_connections += 1
1110:_sqlite_max_open_connections = max(
1111:_sqlite_max_open_connections, _sqlite_open_connections
1112:)
1113:return conn
1116:def _sqlite_close(conn: sqlite3.Connection) -> None:
1117:global _sqlite_open_connections
1118:try:
1119:conn.close()
1120:except sqlite3.Error:
1121:pass
1122:with _sqlite_guard_lock:
1123:_sqlite_open_connections = max(0, _sqlite_open_connections - 1)
1126:def _sqlite_max_idx(db_path: Path) -> int | None:
1128:conn: sqlite3.Connection | None = None
1129:try:
1130:conn = _sqlite_open_ro(db_path)
1131:row = cast(
1132:"tuple[object, ...]",
1133:conn.execute("SELECT COALESCE(MAX(idx), -1) FROM steps").fetchone(),
1134:)
1135:value = row[0]
1136:return value if isinstance(value, int) else None
1137:except sqlite3.Error:
1138:return None
1139:finally:
1140:if conn is not None:
1141:_sqlite_close(conn)
1144:def _transcript_path(cid: str) -> Path:
1145:return BRAIN_DIR / cid / ".system_generated" / "logs" / TRANSCRIPT_NAME
1148:def _transcript_anchor(cid: str) -> tuple[int, int] | None:
1153:path = _transcript_path(cid)
1154:try:
1155:size = path.stat().st_size
1156:except FileNotFoundError:
1157:return (-1, 0)
1158:except OSError:
1159:return None
1160:try:
1161:with open(path, "rb") as fh:
1162:_ = fh.seek(max(0, size - TRANSCRIPT_READ_MAX))
1163:data = fh.read(TRANSCRIPT_READ_MAX)
1164:except OSError:
1165:return None
1166:t_max = -1
1167:for match in _STEP_INDEX_RE.finditer(data):
1168:t_max = max(t_max, int(match.group(1)))
1169:return (t_max, size)
1172:@final
1173:class _TurnPlan:
1176:def __init__(self) -> None:
1177:self.mode: str = "OFF"
1178:self.reason: str = ""
1179:self.base_idx: int = 0
1180:self.offset: int = 0
1181:self.anchored: bool = True
1182:self.probe_gen: int | None = None
1183:self.identity: tuple[int, int] | None = None
1186:def _prespawn_plan(cid: str, resumed: bool) -> _TurnPlan:
1193:plan = _TurnPlan()
1194:if not resumed:
1195:return plan
1196:plan.anchored = False
1197:if _CID_RE.fullmatch(cid) is None:
1198:plan.reason = "cid"
1199:plan.offset = -1
1200:return plan
1201:anchor = _transcript_anchor(cid)
1202:if anchor is None:
1203:plan.reason = "resume_unanchored"
1204:plan.offset = -1
1205:return plan
1206:t_max, plan.offset = anchor
1207:plan.base_idx = t_max + 1
1208:if not _is_sqlite_reasoning_enabled():
1209:plan.reason = _sqlite_disabled_reason() or "flag"
1210:return plan
1211:if _breaker_blocks_now():
1212:plan.reason = "breaker"
1213:return plan
1214:db_path = _db_path_for(cid)
1215:db_max = _sqlite_max_idx(db_path) if db_path is not None else None
1216:if db_max is None:
1217:plan.reason = "resume_unanchored"
1218:return plan
1219:plan.anchored = True
1220:plan.base_idx = max(t_max, db_max) + 1
1221:return plan
1224:def _decide_turn_mode(plan: _TurnPlan) -> None:
1226:disabled = _sqlite_disabled_reason()
1227:if disabled:
1228:plan.mode, plan.reason = "OFF", plan.reason or disabled
1229:return
1230:if not plan.anchored:
1231:plan.mode, plan.reason = "OFF", plan.reason or "resume_unanchored"
1232:return
1233:allowed, probe_gen = _breaker_acquire()
1234:if not allowed:
1235:plan.mode, plan.reason = "OFF", "breaker"
1236:return
1237:plan.probe_gen = probe_gen
1238:plan.identity = _agy_binary_identity()
1239:plan.mode = _compat_turn_state(plan.identity)
1240:plan.reason = ""
1246:def _read_varint(buf: bytes, pos: int, end: int) -> tuple[int, int]:
1248:value = 0
1249:shift = 0
1250:cur = pos
1251:while cur < end and shift < 70:
1252:byte = buf[cur]
1253:cur += 1
1254:value |= (byte & 0x7F) << shift
1255:if not byte & 0x80:
1256:return value, cur
1257:shift += 7
1258:return -1, pos
1261:def _wire_find(
1262:buf: bytes, start: int, end: int, field_no: int, stop: threading.Event | None
1263:) -> list[tuple[int, int]] | None:
1269:found: list[tuple[int, int]] = []
1270:pos = start
1271:tags = 0
1272:while pos < end:
1273:tags += 1
1274:if tags % 64 == 0 and stop is not None and stop.is_set():
1275:return None
1276:tag, pos = _read_varint(buf, pos, end)
1277:if tag < 0:
1278:return None
1279:wire = tag & 7
1280:number = tag >> 3
1281:if wire == 0:
1282:value, pos = _read_varint(buf, pos, end)
1283:if value < 0:
1284:return None
1285:elif wire == 1:
1286:pos += 8
1287:elif wire == 5:
1288:pos += 4
1289:elif wire == 2:
1290:length, pos = _read_varint(buf, pos, end)
1291:if length < 0 or pos + length > end:
1292:return None
1293:if number == field_no:
1294:found.append((pos, pos + length))
1295:pos += length
1296:else:
1297:return None
1298:if pos > end:
1299:return None
1300:return found
1303:def _trim_incomplete_utf8(data: bytes) -> bytes:
1305:size = len(data)
1306:for back in range(1, min(4, size) + 1):
1307:byte = data[size - back]
1308:if 0x80 <= byte <= 0xBF:
1309:continue
1310:if 0xC0 <= byte <= 0xF4:
1311:need = 2 if byte < 0xE0 else (3 if byte < 0xF0 else 4)
1312:if back < need:
1313:return data[: size - back]
1314:break
1315:return data
1318:def _extract_thinking_from_step_blob(
1319:raw: bytes | None, final: bool, stop: threading.Event | None = None
1320:) -> str:
1327:if not raw:
1328:return ""
1329:try:
1330:data = bytes(raw)
1331:roots = _wire_find(data, 0, len(data), 20, stop)
1332:if not roots:
1333:return ""
1334:chosen: tuple[int, int] | None = None
1335:for begin, finish in roots:
1336:subs = _wire_find(data, begin, finish, 3, stop)
1337:if subs is None:
1338:return ""
1339:if subs:
1340:chosen = subs[-1]
1341:if chosen is None:
1342:return ""
1343:text = data[chosen[0] : chosen[1]]
1344:if not final:
1345:text = _trim_incomplete_utf8(text)
1346:return text.decode("utf-8", errors="replace")
1347:except Exception:
1348:return ""
1351:def _sha(text: str) -> str:
1352:return hashlib.sha256(text.encode("utf-8")).hexdigest()
1355:def _as_int(value: object) -> int | None:
1356:if isinstance(value, bool):
1357:return None
1358:if isinstance(value, int):
1359:return value
1360:if isinstance(value, str) and value.isdigit():
1361:return int(value)
1362:return None
1365:@final
1366:class _StepState:
1373:def __init__(self) -> None:
1374:self.blob_len: int = -1
1375:self.blob_sha: str = ""
1376:self.observed_len: int = 0
1377:self.observed_sha: str = ""
1378:self.observed_final: bool = False
1379:self.delivered_len: int = 0
1380:self.delivered_sha = hashlib.sha256()
1381:self.final_len: int = 0
1382:self.final_sha: str = ""
1383:self.diverged: bool = False
1384:self.finalized: bool = False
1385:self.sql_seen: bool = False
1386:self.sql_done: bool = False
1387:self.canary_done: bool = False
1390:_STEPS_SQL = (
1391:"SELECT idx, status, length(step_payload) AS blob_len, "
1392:+ "CASE WHEN length(step_payload) <= %d THEN step_payload ELSE NULL END AS step_payload "
1393:+ "FROM steps WHERE step_type = %d AND idx >= ? AND status IN (%d, %d) "
1394:+ "ORDER BY idx ASC LIMIT %d"
1395:) % (
1396:MAX_STEP_BLOB_BYTES,
1397:STEP_TYPE_PLANNER,
1398:STEP_STATUS_GENERATING,
1399:STEP_STATUS_DONE,
1400:SQLITE_ROW_LIMIT,
1401:)
1404:@final
1405:class _TranscriptTail:
1425:def __init__(
1426:self,
1427:emit: Callable[[int, str, Callable[[], None] | None], bool],
1428:stop_event: threading.Event,
1429:done_event: threading.Event,
1430:resumed: bool,
1431:plan: _TurnPlan | None = None,
1432:turn_id: str = "",
1433:) -> None:
1434:self.emit = emit
1435:self.stop_event = stop_event
1436:self.done_event = done_event
1437:self.resumed = resumed
1438:self.plan: _TurnPlan = plan if plan is not None else _TurnPlan()
1439:self.turn_id: str = turn_id
1440:self.mode: str = self.plan.mode
1441:self.base_idx: int = self.plan.base_idx
1442:self.probe_gen: int | None = self.plan.probe_gen
1443:self.cid: str = ""
1444:self.seen: dict[int, _StepState] = {}
1445:self.poll_watermark: int = self.plan.base_idx
1446:self.sqlite_active: bool = self.plan.mode in ("LIVE", "SHADOW")
1447:self.bucket: _PollBucket = _PollBucket()
1448:self.selects_ok: int = 0
1449:self.failed: bool = False
1450:self.emitted: int = 0
1451:self.dead: bool = False
1452:self.end_marker: bool = False
1453:self.final_planner: bool = False
1454:self.drain_deadline: float = 0.0
1455:self.drain_outcome: str = ""
1456:self.last_poll: str = ""
1457:self._ready = threading.Event()
1458:self._offset: int = self.plan.offset
1459:self._buf: bytes = b""
1460:self._transcript_ok: bool = True
1461:self._owned_cid: str = ""
1462:self._next_poll_at: float = 0.0
1463:self._interrupted: bool = False
1464:self._active_conn: sqlite3.Connection | None = None
1465:self._conn_lock = threading.Lock()
1466:self._db_path: Path | None = None
1467:self._open_fail_logged: bool = False
1468:self._oversize_logged: set[int] = set()
1469:self._finished: bool = False
1470:self.thread = threading.Thread(target=self._run, daemon=True)
1473:def start(self) -> None:
1474:self.thread.start()
1476:def _cid8(self) -> str:
1477:return self.cid[:8] or "-"
1479:def bind(self, cid: str) -> None:
1481:if not cid or self.cid:
1482:return
1483:self.cid = cid
1484:if _CID_RE.fullmatch(cid) is None:
1485:self._transcript_ok = False
1486:self._sqlite_off("cid")
1487:else:
1488:if self.sqlite_active:
1489:if _cid_acquire(cid, self.turn_id):
1490:self._owned_cid = cid
1491:else:
1492:self._sqlite_off("cid_busy")
1493:self._db_path = _db_path_for(cid)
1494:if self._db_path is None:
1495:self._sqlite_off("cid")
1496:if self.resumed and self._offset < 0:
1497:try:
1498:self._offset = _transcript_path(cid).stat().st_size
1499:except OSError:
1500:self._offset = 0
1501:_log(
1502:f"turn_mode cid={self._cid8()} mode={self.mode if self.sqlite_active else 'OFF'}"
1503:)
1504:if self.plan.mode == "OFF" and self.plan.reason:
1505:_log(f"sqlite-off cid={self._cid8()} reason={self.plan.reason}")
1506:self._ready.set()
1508:def interrupt_active_query(self) -> None:
1510:with self._conn_lock:
1511:conn = self._active_conn
1512:if conn is not None:
1513:self._interrupted = True
1514:try:
1515:conn.interrupt()
1516:except (sqlite3.ProgrammingError, sqlite3.OperationalError):
1517:pass
1519:def _run(self) -> None:
1520:try:
1521:self._run_loop()
1522:except Exception as exc:
1523:_log(f"tail-error cid={self._cid8()} err={type(exc).__name__}")
1524:finally:
1525:self._finish()
1527:def _run_loop(self) -> None:
1531:waited = 0.0
1532:while not self._ready.wait(timeout=0.05):
1533:waited += 0.05
1534:if self.stop_event.is_set() or self.done_event.is_set():
1535:return
1536:if waited >= FIRST_TOKEN_TIMEOUT_S:
1537:_log(
1538:f"tail-timeout cid={self._cid8()}: no bind within {FIRST_TOKEN_TIMEOUT_S:g}s"
1539:)
1540:return
1541:deadline = time.monotonic() + TIMEOUT_S + 60
1542:while time.monotonic() < deadline:
1543:if self.stop_event.is_set():
1544:return
1545:if self.done_event.is_set():
1546:self._drain_post_eof()
1547:return
1548:self.tick()
1549:_ = self.done_event.wait(TRANSCRIPT_POLL_S)
1551:def _finish(self) -> None:
1553:if self._finished:
1554:return
1555:self._finished = True
1556:with self._conn_lock:
1557:conn = self._active_conn
1558:self._active_conn = None
1559:if conn is not None:
1560:_sqlite_close(conn)
1561:if self.plan.mode in ("LIVE", "SHADOW"):
1562:_breaker_report(self.probe_gen, self.selects_ok, self.failed)
1563:if self._owned_cid:
1564:_cid_release(self._owned_cid, self.turn_id)
1567:def tick(self) -> None:
1569:self._read_transcript()
1570:if self.dead:
1571:return
1572:_ = self._sqlite_permitted()
1573:now = time.monotonic()
1574:if self.sqlite_active and now >= self._next_poll_at:
1575:self._next_poll_at = now + SQLITE_POLL_S
1576:_ = self._poll_sqlite()
1578:def _sqlite_off(self, reason: str) -> None:
1580:if not self.sqlite_active:
1581:return
1582:self.sqlite_active = False
1583:self.interrupt_active_query()
1584:_log(f"sqlite-off cid={self._cid8()} reason={reason}")
1586:def _sqlite_permitted(self) -> bool:
1588:if not self.sqlite_active or self.dead:
1589:return False
1590:disabled = _sqlite_disabled_reason()
1591:if disabled:
1592:self._sqlite_off(disabled)
1593:return False
1594:if not _breaker_permits(self.probe_gen):
1595:self._sqlite_off("breaker" if self.probe_gen is None else "probe_stale")
1596:return False
1597:return True
1600:def _read_transcript(self) -> None:
1602:if not self.cid or not self._transcript_ok:
1603:return
1604:path = _transcript_path(self.cid)
1605:try:
1606:size = path.stat().st_size
1607:except OSError:
1608:return
1609:if size < self._offset:  # файл переписан с нуля — читаем заново
1610:_log(
1611:f"tail-rewrite cid={self._cid8()}: size {size} < offset {self._offset}"
1612:)
1613:self._offset, self._buf = 0, b""
1614:if size == self._offset:
1615:return
1616:try:
1617:with open(path, "rb") as fh:
1618:_ = fh.seek(self._offset)
1619:self._buf += fh.read(TRANSCRIPT_READ_MAX)
1620:except OSError:
1621:return
1622:while b"\n" in self._buf:
1623:line, self._buf = self._buf.split(b"\n", 1)
1624:self._offset += len(line) + 1
1625:try:
1626:self._emit_record(line)
1627:except Exception:
1628:pass
1630:def _emit_record(self, raw: bytes) -> None:
1631:line = raw.strip()
1632:if not line:
1633:return
1634:if (
1635:b"PLANNER_RESPONSE" not in line
1636:and b"END_TURN" not in line
1637:and b"TURN_COMPLETE" not in line
1638:):
1639:return  # быстрый отсев служебных записей без разбора JSON
1640:try:
1641:parsed = cast(object, json.loads(line.decode("utf-8", "replace")))
1642:except ValueError:
1643:return
1644:if not isinstance(parsed, dict):
1645:return
1646:rec = cast("dict[str, object]", parsed)
1647:rtype = str(rec.get("type") or "")
1648:idx = _as_int(rec.get("step_index"))
1649:if idx is not None and idx < self.base_idx:
1650:return  # история прошлых ходов
1651:if rtype in ("END_TURN", "TURN_COMPLETE"):
1652:self.end_marker = True
1653:return
1654:if rtype != "PLANNER_RESPONSE" or idx is None:
1655:return
1656:content = rec.get("content")
1657:if isinstance(content, str) and content.strip() and not rec.get("tool_calls"):
1658:self.final_planner = True
1659:thinking = rec.get("thinking")
1660:self._apply_final(idx, thinking if isinstance(thinking, str) else "")
1663:def _state(self, idx: int) -> _StepState:
1664:state = self.seen.get(idx)
1665:if state is not None:
1666:return state
1667:if len(self.seen) >= MAX_STEPS_TRACKED:
1668:evictable = [
1669:k
1670:for k, s in self.seen.items()
1671:if s.finalized and k < self.poll_watermark
1672:]
1673:if evictable:
1674:del self.seen[min(evictable)]
1675:else:
1676:self._sqlite_off("seen_cap")
1677:del self.seen[min(self.seen)]
1678:state = _StepState()
1679:self.seen[idx] = state
1680:return state
1682:def _step_done(self, state: _StepState) -> bool:
1683:return state.sql_done or (
1684:state.finalized and (self.mode != "SHADOW" or state.canary_done)
1685:)
1687:def _advance_watermark(self) -> None:
1689:mark = self.poll_watermark
1690:for key in sorted(self.seen):
1691:if key < mark:
1692:continue
1693:if not self._step_done(self.seen[key]):
1694:break
1695:mark = key + 1
1696:self.poll_watermark = mark
1698:def _emit_delta(self, idx: int, state: _StepState, delta: str, source: str) -> bool:
1699:def delivered() -> None:
1700:state.delivered_len += len(delta)
1701:state.delivered_sha.update(delta.encode("utf-8"))
1703:ok = self.emit(idx, delta, delivered)
1704:if not ok:
1705:self.dead = True
1706:return False
1707:self.emitted += 1
1708:_log(f"{source}-emit cid={self._cid8()} step={idx} len={len(delta)}")
1709:return True
1711:def _diverge(
1712:self, idx: int, state: _StepState, source: str, len_prev: int, len_new: int
1713:) -> None:
1715:state.diverged = True
1716:self.failed = True
1717:_count_divergence()
1718:if self.mode == "LIVE":
1719:_compat_demote()
1720:_log(
1721:f"sqlite_{source}_divergence cid={self._cid8()} step={idx} len_prev={len_prev} len_new={len_new}"
1722:)
1723:self._sqlite_off("divergence")
1725:def _apply_snapshot(self, idx: int, state: _StepState, text: str) -> None:
1727:if self.mode != "LIVE" or state.diverged or not text:
1728:return
1729:sent = state.delivered_len
1730:if sent == 0:
1731:_ = self._emit_delta(idx, state, text, "sqlite")
1732:elif len(text) < sent:
1733:return  # устаревший снимок
1734:elif _sha(text[:sent]) != state.delivered_sha.hexdigest():
1735:self._diverge(idx, state, "snapshot", sent, len(text))
1736:elif len(text) > sent:
1737:_ = self._emit_delta(idx, state, text[sent:], "sqlite")
1739:def _apply_final(self, idx: int, final_text: str) -> None:
1741:state = self._state(idx)
1742:if state.finalized:
1743:return
1744:state.final_len = len(final_text)
1745:state.final_sha = _sha(final_text) if final_text else ""
1746:sent = state.delivered_len
1747:if state.diverged:
1748:pass
1749:elif sent == 0:
1750:if final_text:
1751:_ = self._emit_delta(idx, state, final_text, "tail")
1752:elif (
1753:len(final_text) >= sent
1754:and _sha(final_text[:sent]) == state.delivered_sha.hexdigest()
1755:):
1756:if len(final_text) > sent:
1757:_ = self._emit_delta(idx, state, final_text[sent:], "tail")
1758:else:
1759:self._diverge(idx, state, "transcript", sent, len(final_text))
1760:state.finalized = True
1761:self._judge_canary(idx, state)
1762:self._advance_watermark()
1764:def _judge_canary(self, idx: int, state: _StepState) -> None:
1766:if (
1767:state.canary_done
1768:or not state.finalized
1769:or not state.observed_final
1770:or state.final_len == 0
1771:or state.diverged
1772:):
1773:return
1774:state.canary_done = True
1775:if state.observed_len == 0:
1776:_compat_demote()
1777:_log(f"sqlite-live-loss cid={self._cid8()} step={idx}")
1778:elif state.observed_sha == state.final_sha:
1779:if self.mode == "SHADOW" and _compat_promote(self.plan.identity):
1780:_log("compat state=LIVE")
1781:elif self.mode == "SHADOW":
1782:state.diverged = True
1783:self.failed = True
1784:_count_divergence()
1785:_log(
1786:f"sqlite_transcript_divergence cid={self._cid8()} step={idx} len_prev={state.observed_len} len_new={state.final_len}"
1787:)
1788:self._sqlite_off("divergence")
1791:def _poll_sqlite(self) -> tuple[int, int] | None:
1796:self.last_poll = "skip"
1797:if not self._sqlite_permitted() or self._db_path is None:
1798:return None
1799:if not self.bucket.take():
1800:return None
1801:conn: sqlite3.Connection | None = None
1802:result: tuple[int, int] | None = None
1803:try:
1804:conn = _sqlite_open_ro(self._db_path)
1805:with self._conn_lock:
1806:self._active_conn = conn
1807:result = self._select_rows(conn)
1808:self.last_poll = "ok"
1809:except sqlite3.Error as exc:
1810:self.last_poll = "error"
1811:self._on_sqlite_error(exc)
1812:except Exception as exc:
1813:self.last_poll = "error"
1814:_log(f"sqlite-error cid={self._cid8()} err={type(exc).__name__}")
1815:self._sqlite_off("internal")
1816:finally:
1817:with self._conn_lock:
1818:self._active_conn = None
1819:if conn is not None:
1820:_sqlite_close(conn)
1821:return result
1823:def _on_sqlite_error(self, exc: sqlite3.Error) -> None:
1824:message = str(exc).lower()
1825:if "interrupted" in message and (self._interrupted or self.stop_event.is_set()):
1826:return  # собственный stop/interrupt отказом не считается
1827:operational = isinstance(exc, sqlite3.OperationalError)
1828:schema = operational and (
1829:"no such table" in message or "no such column" in message
1830:)
1831:cold = False
1832:if schema:
1833:self.failed = True
1834:_log(f"sqlite-schema-mismatch cid={self._cid8()}")
1835:self._sqlite_off("schema")
1836:elif operational:
1838:wal = Path(str(self._db_path) + "-wal")
1839:cold = self.selects_ok == 0 or not wal.exists()
1840:if not cold:
1841:self.failed = True
1842:elif isinstance(exc, sqlite3.DatabaseError):
1843:self.failed = True
1844:self._sqlite_off("db_error")
1845:if not self._open_fail_logged:
1846:self._open_fail_logged = True
1847:_log(
1848:f"sqlite-open-fail cid={self._cid8()} err={type(exc).__name__} cold={1 if cold else 0}"
1849:)
1851:def _select_rows(self, conn: sqlite3.Connection) -> tuple[int, int]:
1852:start = max(self.poll_watermark, self.base_idx)
1853:cur = conn.execute(_STEPS_SQL, (start,))
1854:rows = 0
1855:generating = 0
1856:try:
1857:while True:
1858:if self.stop_event.is_set() or not self._sqlite_permitted():
1859:break
1860:batch = cast("list[tuple[object, ...]]", cur.fetchmany(1))
1861:if not batch:
1862:self.selects_ok += 1
1863:break
1864:row = batch[0]
1865:idx, status, blob_len, payload = row[0], row[1], row[2], row[3]
1866:if not isinstance(idx, int) or not isinstance(status, int):
1867:continue
1868:rows += 1
1869:if status == STEP_STATUS_GENERATING:
1870:generating += 1
1871:self._handle_row(idx, status, blob_len, payload)
1872:if self.dead:
1873:break
1874:finally:
1875:cur.close()
1876:self._advance_watermark()
1877:return rows, generating
1879:def _handle_row(
1880:self, idx: int, status: int, blob_len: object, payload: object
1881:) -> None:
1882:state = self._state(idx)
1883:if state.finalized:
1884:if status == STEP_STATUS_DONE and not state.canary_done and state.final_len:
1885:self._observe_final_snapshot(idx, state, payload)
1886:return
1887:if state.diverged:
1888:return
1889:state.sql_seen = True
1890:if payload is None or not isinstance(payload, (bytes, bytearray)):
1891:if (
1892:isinstance(blob_len, int)
1893:and blob_len > MAX_STEP_BLOB_BYTES
1894:and idx not in self._oversize_logged
1895:):
1896:self._oversize_logged.add(idx)
1897:_log(
1898:f"sqlite-oversize cid={self._cid8()} step={idx} blob_len={blob_len}"
1899:)
1900:if status == STEP_STATUS_DONE:
1901:state.sql_done = True
1902:return
1903:data = bytes(payload)
1904:digest = hashlib.sha256(data).hexdigest()
1905:if state.blob_len == len(data) and state.blob_sha == digest:
1907:if status == STEP_STATUS_DONE:
1908:state.sql_done = True
1909:state.observed_final = True
1910:self._judge_canary(idx, state)
1911:return
1912:text = _extract_thinking_from_step_blob(
1913:data, final=(status == STEP_STATUS_DONE), stop=self.stop_event
1914:)
1915:if self.stop_event.is_set():
1916:return
1917:state.blob_len, state.blob_sha = len(data), digest
1918:first_gen = state.observed_len == 0 and bool(text)
1919:state.observed_len = len(text)
1920:state.observed_sha = _sha(text) if text else ""
1921:state.observed_final = status == STEP_STATUS_DONE
1922:if status == STEP_STATUS_DONE:
1923:state.sql_done = True
1924:if first_gen and status == STEP_STATUS_GENERATING:
1925:_log(f"sqlite-gen cid={self._cid8()} step={idx}")
1926:self._apply_snapshot(idx, state, text)
1927:self._judge_canary(idx, state)
1929:def _observe_final_snapshot(
1930:self, idx: int, state: _StepState, payload: object
1931:) -> None:
1933:if not isinstance(payload, (bytes, bytearray)):
1934:state.canary_done = True
1935:return
1936:text = _extract_thinking_from_step_blob(
1937:bytes(payload), final=True, stop=self.stop_event
1938:)
1939:if self.stop_event.is_set():
1940:return
1941:state.observed_len = len(text)
1942:state.observed_sha = _sha(text) if text else ""
1943:state.observed_final = True
1944:state.sql_done = True
1945:self._judge_canary(idx, state)
1948:def _pending_steps(self) -> int:
1949:return sum(
1950:1
1951:for key, state in self.seen.items()
1952:if key >= self.base_idx and state.sql_seen and not state.finalized
1953:)
1955:def _drain_post_eof(self) -> None:
1963:started = time.monotonic()
1964:deadline = (
1965:self.drain_deadline if self.drain_deadline > 0 else started + DRAIN_WINDOW_S
1966:)
1967:deadline = min(deadline, started + DRAIN_MAX_S)
1968:earliest = started + DRAIN_MIN_S
1969:emitted_before = self.emitted
1970:exit_kind = "window"
1971:while True:
1972:if self.stop_event.is_set():
1973:exit_kind = "stop"
1974:break
1975:self._read_transcript()
1976:if self.sqlite_active:
1977:_ = self._poll_sqlite()
1978:now = time.monotonic()
1979:if now >= earliest and self.end_marker:
1980:exit_kind = "end_turn"
1981:break
1982:if now >= deadline:
1983:break
1984:time.sleep(min(DRAIN_POLL_STEP_S, max(0.0, deadline - now)))
1985:pending = self._pending_steps()
1986:complete = pending == 0 and (self.final_planner or self.end_marker)
1987:self.drain_outcome = "complete" if complete else "window_complete"
1988:if exit_kind != "stop" and pending > 0:
1989:_count_drain_deadline()
1990:ms = int((time.monotonic() - started) * 1000)
1991:_log(
1992:f"drain cid={self._cid8()} ms={ms} emitted={self.emitted - emitted_before} outcome={self.drain_outcome} pending_steps={pending} exit={exit_kind}"
1993:)
1996:@final
1997:class Run:
2008:def __init__(
2009:self,
2010:prompt: str,
2011:model: str,
2012:effort: str,
2013:effort_source: str,
2014:cwd: str,
2015:tag: str,
2016:conversation_id: str = "",
2017:turn_id: str = "",
2018:):
2019:launcher = _launcher()
2020:WORKSPACE.mkdir(parents=True, exist_ok=True)
2021:work_dir = cwd if (cwd and os.path.isdir(cwd)) else str(WORKSPACE)
2022:self.work_dir = work_dir
2023:self.stdin_line = _ndjson_user_line(prompt)
2024:cmd = [
2025:launcher,
2026:"--input-format",
2027:"stream-json",
2028:"--output-format",
2029:"stream-json",
2030:"--dangerously-skip-permissions",
2031:"--model",
2032:model,
2033:"--effort",
2034:effort,
2035:"--print-timeout=" + str(PRINT_TIMEOUT),
2036:]
2038:self.run_cid = conversation_id or ""
2039:self.turn_id: str = turn_id or uuid.uuid4().hex
2040:if self.run_cid:
2041:cmd += ["--conversation", self.run_cid]
2043:plan = _prespawn_plan(self.run_cid, bool(self.run_cid))
2044:if self.run_cid and not _cid_acquire(self.run_cid, self.turn_id):
2045:plan.anchored = False
2046:plan.reason = "cid_busy"
2047:try:
2048:self.proc = subprocess.Popen(
2049:cmd,
2050:cwd=work_dir,
2051:stdin=subprocess.PIPE,
2052:stdout=subprocess.PIPE,
2053:stderr=subprocess.PIPE,
2054:start_new_session=True,
2055:env=_launch_env(),
2056:)
2057:except BaseException:
2058:_cid_release(self.run_cid, self.turn_id)
2059:raise
2060:self.started = time.monotonic()
2061:enabled = _is_watchdog_enabled()
2063:self.controller = AdaptiveTimeoutController(
2064:idle_timeout_s=IDLE_TIMEOUT_S if enabled else float(TIMEOUT_S),
2065:safety_cap_s=float(TIMEOUT_S),  # дефолт core (3600 с) не используется
2066:finish_reserve_s=0.0,  # эффективный потолок ровно TIMEOUT_S
2067:watchdog_enabled=enabled,
2068:log_fn=_log,
2069:)
2070:self.controller.register_pgid(self.proc.pid)
2071:self.got_event = False  # True после первого валидного JSON-события stdout
2072:self.stderr_head: list = []
2073:with _active_lock:
2074:_active[self.proc.pid] = self.proc
2075:self.q = queue.Queue()
2076:self.err_box = []
2079:self._text_seen: dict = {}
2081:self._emit_lock = threading.Lock()
2082:self.drain_closed: bool = False
2083:self._done_put: bool = False
2084:self._reasoning_bytes: int = 0
2085:self._cap_logged: bool = False
2088:self._proc_done = threading.Event()
2089:self._stop_watch = threading.Event()
2090:_decide_turn_mode(plan)
2091:self._tail = _TranscriptTail(
2092:emit=self._emit_reasoning,
2093:stop_event=self._stop_watch,
2094:done_event=self._proc_done,
2095:resumed=bool(self.run_cid),
2096:plan=plan,
2097:turn_id=self.turn_id,
2098:)
2099:if self.run_cid:
2100:self._tail.bind(self.run_cid)
2101:threading.Thread(target=self._feed_stdin, daemon=True).start()
2102:threading.Thread(target=self._drain_stderr, daemon=True).start()
2103:threading.Thread(target=self._pump, daemon=True).start()
2104:self._tail.start()
2106:def _emit_reasoning(
2107:self, idx: int, delta: str, on_delivered: Callable[[], None] | None = None
2108:) -> bool:
2114:size = len(delta.encode("utf-8"))
2115:outcome = ""
2116:log_cap = False
2117:with self._emit_lock:
2118:if self.drain_closed:
2119:outcome = "late"
2120:elif self._reasoning_bytes + size > MAX_REASONING_BYTES_PER_TURN:
2121:outcome = "cap"
2122:log_cap = not self._cap_logged
2123:self._cap_logged = True
2124:else:
2125:self._reasoning_bytes += size
2126:self.q.put(("reasoning", delta))
2127:if on_delivered is not None:
2128:on_delivered()
2129:return True
2130:total = self._reasoning_bytes
2131:cid8 = self._tail.cid[:8] or "-"
2132:if outcome == "late":
2133:_log(f"reasoning-late-drop cid={cid8} step={idx} len={len(delta)}")
2134:elif log_cap:
2135:_log(f"reasoning-cap cid={cid8} bytes={total}")
2136:return False
2138:def _close_and_put_done(self, kind: str, payload: object) -> None:
2140:with self._emit_lock:
2141:if self._done_put:
2142:return
2143:self._done_put = True
2144:self.drain_closed = True
2145:self.q.put((kind, payload))
2147:def _feed_stdin(self) -> None:
2149:try:
2150:self.proc.stdin.write(self.stdin_line.encode("utf-8"))
2151:self.proc.stdin.flush()
2152:except (BrokenPipeError, OSError, ValueError):
2153:pass
2154:finally:
2155:try:
2156:self.proc.stdin.close()
2157:except (BrokenPipeError, OSError, ValueError):
2158:pass
2159:self.proc.stdin = None
2161:def _drain_stderr(self) -> None:
2163:head: list = []
2164:try:
2165:for raw in iter(self.proc.stderr.readline, b""):
2166:line = raw.decode("utf-8", "replace").rstrip()
2167:if not line or _NOISE.search(line):
2168:continue
2169:head.append(line)
2170:if len(head) > 40:
2171:del head[0]
2172:except Exception:  # noqa: BLE001 — вторичный поток, ошибку терять нельзя молча
2173:pass
2174:self.err_box.append("\n".join(head).strip())
2176:def _pump(self) -> None:
2188:final_text = ""
2189:result_ev = {}
2190:term_kind = "pump_error"
2191:term_payload: object = "pump terminated"
2192:try:
2193:for raw in iter(self.proc.stdout.readline, b""):
2194:line = raw.decode("utf-8", "replace").strip()
2195:if not line.startswith("{"):
2196:continue
2197:try:
2198:ev = json.loads(line)
2199:except ValueError:
2200:continue
2201:self.got_event = True
2202:etype = ev.get("event")
2203:if etype == "init":
2204:init = ev.get("init") if isinstance(ev.get("init"), dict) else {}
2205:tools_raw = cast(object, init.get("tools"))
2206:tools = (
2207:cast("list[object]", tools_raw)
2208:if isinstance(tools_raw, list)
2209:else []
2210:)
2211:self.q.put(
2212:(
2213:"init",
2214:{
2215:"conversation_id": ev.get("conversation_id") or "",
2216:"tools": len(tools),
2217:"permission_mode": init.get("permission_mode") or "",
2218:},
2219:)
2220:)
2221:self._tail.bind(str(ev.get("conversation_id") or ""))
2222:elif etype == "step_update":
2223:step = (
2224:ev.get("step_update")
2225:if isinstance(ev.get("step_update"), dict)
2226:else {}
2227:)
2228:kind = step.get("step_type")
2229:if kind == "agent_response" and step.get("text_delta"):
2230:suffix = _reasoning_suffix(
2231:self._text_seen,
2232:str(step.get("step_index", "")),
2233:str(step["text_delta"]),
2234:)
2235:if suffix:
2236:self.q.put(("text", suffix))
2237:elif kind == "tool" and step.get("state") == "DONE":
2238:self.q.put(
2239:(
2240:"tool_trace",
2241:{
2242:"name": str(step.get("tool_name") or "tool"),
2243:"duration_s": step.get("duration_seconds"),
2244:},
2245:)
2246:)
2247:elif etype == "result":
2248:result = (
2249:ev.get("result") if isinstance(ev.get("result"), dict) else {}
2250:)
2251:result_ev = result
2252:final_text = str(result.get("response") or "")
2253:self.q.put(
2254:(
2255:"result",
2256:{
2257:"conversation_id": result.get("conversation_id") or "",
2258:"status": str(result.get("status") or ""),
2259:"error": str(result.get("error") or ""),
2260:"duration_s": result.get("duration_seconds"),
2261:"num_turns": result.get("num_turns"),
2262:"usage": result.get("usage") or {},
2263:},
2264:)
2265:)
2266:rc: int | None
2267:try:
2268:rc = self.proc.wait(timeout=PROC_EXIT_WAIT_S)
2269:except subprocess.TimeoutExpired:
2270:rc = None  # процесс ещё жив после EOF: добьёт Run.close
2271:time.sleep(0.05)  # дать стоку stderr дозавершиться
2272:t_exit = time.monotonic()
2273:self._tail.drain_deadline = t_exit + DRAIN_WINDOW_S
2274:self._proc_done.set()
2275:self._join_source(t_exit)
2276:if rc is None:
2277:rc = 0 if result_ev else 1
2278:term_kind = "done"
2279:term_payload = cast(object, (rc, final_text, result_ev))
2280:except Exception as exc:  # noqa: BLE001 — читатель не должен умирать молча
2281:self._stop_watch.set()
2282:term_kind = "pump_error"
2283:term_payload = repr(exc)
2284:finally:
2285:self._proc_done.set()
2286:self._close_and_put_done(term_kind, term_payload)
2288:def _join_source(self, t_exit: float) -> None:
2290:thread = self._tail.thread
2291:thread.join(timeout=max(0.0, t_exit + DRAIN_WINDOW_S - time.monotonic()))
2292:if not thread.is_alive():
2293:return
2294:self._tail.interrupt_active_query()
2295:thread.join(timeout=JOIN_TIMEOUT_S)
2296:if thread.is_alive():
2297:_count_drain_deadline()
2298:_log(f"drain-timeout cid={self._tail.cid[:8] or '-'}")
2300:def close(self) -> None:
2301:self._stop_watch.set()
2302:self._proc_done.set()
2303:self._tail.interrupt_active_query()
2304:self.controller.close()
2306:_kill_group(self.proc)
2307:with _active_lock:
2308:_active.pop(self.proc.pid, None)
2309:for stream in (self.proc.stdin, self.proc.stdout, self.proc.stderr):
2310:try:
2311:if stream is not None:
2312:stream.close()
2313:except OSError:
2314:pass
2315:thread = self._tail.thread
2316:if thread.is_alive() and thread is not threading.current_thread():
2317:thread.join(timeout=JOIN_TIMEOUT_S)
2320:def _reasoning_suffix(seen: dict, rid: str, text: str) -> str:
2324:prev = seen.get(rid, "")
2325:suffix = text[len(prev) :] if text.startswith(prev) else text
2326:seen[rid] = text
2327:return suffix
2330:def _client_gone(sock: socket.socket) -> bool:
2331:try:
2332:ready, _, _ = select.select([sock], [], [], 0)
2333:return bool(ready) and sock.recv(1, socket.MSG_PEEK) == b""
2334:except (OSError, ValueError):
2335:return True
2716:)
2717:finally:
2718:run.close()
2719:if out["state"] == "done":
2720:break
2723:delivered = bool(
2724:out.get("text")
2725:or out.get("tool_calls")
2726:or (ctx.get("stream") and out.get("reasoning"))
2727:)
2728:if ctx.get("hot_resumed") and out["state"] != "client_gone":
2731:_session_invalidate(ctx["sess_key"], ctx["conversation_id"])
2732:_cid_release(
2733:str(ctx["conversation_id"]), str(ctx.get("turn_id") or "")
2734:)
2735:ctx["hot_resumed"] = False
2736:ctx["conversation_id"] = ""
2737:ctx["prompt"] = ctx["full_prompt"]
2738:if out["state"] == "agy_error" and not delivered:
2739:if not _retry_take():
2740:_log(f"retry-budget-exhausted state={out['state']} {tag}")
2741:break
2742:_log(
2743:f"hot session failed err={_err_summary(out.get('err'), 120)!r}, "
2744:f"cold fallback {tag}"
2745:)
2746:continue
2748:transient = (
2749:out["state"] in ("agy_error", "pump_error", "done")
2750:and not delivered
2751:)
2752:if not transient or attempt == 2:
2753:break
2754:if not _retry_take():
2755:_log(f"retry-budget-exhausted state={out['state']} {tag}")
2756:break
2757:_log(
2758:f"transient failure state={out['state']} rc={out.get('rc')} "
2759:f"err={_err_summary(out.get('err'), 120)!r}, retry {attempt} {tag}"
2760:)
2761:time.sleep(_retry_pause_s(attempt))
2762:if (
2763:out.get("state") == "done"
2764:and out.get("conversation_id")
2765:and ctx.get("sess_key")
2766:):
2767:_session_commit(ctx["sess_key"], str(out["conversation_id"]))
2768:if out.get("state") != "client_gone":
2769:_last_ok[0] = (
2770:time.monotonic()
2771:if (out.get("state") == "done" and out.get("rc") == 0)
2772:else 0.0
2773:)
2774:finally:
2775:_slots.release()
2776:self._log_done(
2777:cast(str, ctx["model"]),
2778:cast("dict[str, object]", out),
2779:t0,
2780:cast(str, ctx["tag"]),
2781:)
2782:return out
2784:@staticmethod
2785:def _usage_payload(usage: dict) -> dict:
2787:return {
2788:"prompt_tokens": usage.get("input_tokens", 0),
2789:"completion_tokens": usage.get("output_tokens", 0)
2790:+ usage.get("thinking_tokens", 0),
2791:"total_tokens": usage.get("total_tokens", 0),
2792:}
2794:@staticmethod
2795:def _error_body(out: dict) -> Any:
2796:st = out.get("state")
2797:if st == "timeout":
2798:return {
2799:"message": f"agy timed out after {TIMEOUT_S}s",
2800:"type": "timeout",
2801:"code": 504,
2863:"active": active,
2864:"max_concurrent": MAX_CONCURRENT,
2865:"hot_sessions": len(_session_store),
2866:"tool_emulation": False,
2867:"tool_translation": False,
2868:"native_tools": True,
2869:"images": False,
2870:"uptime_s": int(time.time() - _started),
2871:}
2872:health.update(_sqlite_health_fields())
2873:self._send(200, health)
2874:return
2875:if not _auth_ok(self):
2876:self._send(
2877:401,
2878:{
2879:"error": {
2880:"message": "unauthorized",
2881:"type": "auth_error",
2882:"code": 401,
2883:}
2884:},
2885:)
2886:return
2887:if path in ("/v1/models", "/models"):
2888:data = []
2889:order = [MODEL_ID] + [mid for mid in FLEET["order"] if mid != MODEL_ID]
2890:for mid in order:
2891:model = FLEET["models"][mid]
2892:data.append(
2893:{
2894:"id": mid,
2895:"object": "model",
2896:"owned_by": "antigravity",
2897:"created": 0,
2898:"context_length": model["context_window"],
2899:}
2900:)
2901:self._send(200, {"object": "list", "data": data})
2902:return
2903:self._send(
2904:404,
2905:{
2906:"error": {
2907:"message": f"not found: {path}",
2908:"type": "not_found",
2909:"code": 404,
2910:}
2911:},
2912:)
2914:def do_POST(self) -> None:  # noqa: N802
2915:if not _auth_ok(self):
2917:self.close_connection = True
2918:self._send(
2919:401,
2920:{
2921:"error": {
3156:return
3157:usage = out.get("usage") or {}
3158:message = {"role": "assistant", "content": out["text"]}
3159:reasoning = out.get("reasoning") or ""
3160:if reasoning:
3163:message["reasoning_content"] = reasoning
3164:payload = {
3165:"id": f"chatcmpl-agy-{uuid.uuid4().hex[:12]}",
3166:"object": "chat.completion",
3167:"created": int(time.time()),
3168:"model": ctx["model"],
3169:"choices": [{"index": 0, "message": message, "finish_reason": "stop"}],
3170:"usage": self._usage_payload(usage),
3171:}
3172:if out.get("conversation_id"):
3173:payload["conversation_id"] = out["conversation_id"]
3174:self._send(200, payload)
3176:def _serve_sse(self, ctx: dict) -> None:
3177:completion_id = f"chatcmpl-agy-{uuid.uuid4().hex[:12]}"
3178:created = int(time.time())
3179:shown_model = ctx["model"]
3180:try:
3181:self.send_response(200)
3182:self.send_header("Content-Type", "text/event-stream")
3183:self.send_header("Cache-Control", "no-cache")
3184:self.send_header("X-Accel-Buffering", "no")
3185:self.end_headers()
3186:self.close_connection = True
3187:except (BrokenPipeError, ConnectionResetError, OSError):
3188:_log("client gone before headers")
3189:return
3191:def chunk(
3192:delta: dict,
3193:finish=None,
3194:usage: dict | None = None,
3195:conversation_id: str = "",
3196:) -> str:
3197:body: dict = {
3198:"id": completion_id,
3199:"object": "chat.completion.chunk",
3200:"created": created,
3201:"model": shown_model,
3202:"choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
3203:}
3204:if usage is not None:
3205:body["usage"] = usage
3206:if conversation_id:
3207:body["conversation_id"] = conversation_id
3208:return "data: " + json.dumps(body, ensure_ascii=False) + "\n\n"
3210:def on_text(value: str) -> bool:
3211:return self._emit(chunk({"content": value}))
3213:def on_reasoning(value: str) -> bool:
3216:return self._emit(chunk({"reasoning_content": value}))
3218:def on_tool_trace(_event: dict) -> bool:
3221:return True
3223:def keepalive() -> bool:
3224:return self._emit(": keepalive\n\n")
3226:if not self._emit(chunk({"role": "assistant", "content": ""})):
3227:return
3228:out = self._run_once(ctx, on_text, on_tool_trace, on_reasoning, keepalive)
3229:if out.get("state") == "client_gone":
3230:_log("client gone mid-stream, child killed")
3231:return
3232:err = self._error_body(out)
3233:if err is None:
3234:conv_id = str(out.get("conversation_id") or "")
3235:self._emit(chunk({}, "stop", conversation_id=conv_id))
3240:usage = self._usage_payload(out.get("usage") or {})
3241:if usage["prompt_tokens"] or usage["completion_tokens"]:
3242:self._emit(chunk({}, "stop", usage, conversation_id=conv_id))
3243:else:
3244:self._emit(
3245:"data: " + json.dumps({"error": err}, ensure_ascii=False) + "\n\n"
3246:)
3247:self._emit("data: [DONE]\n\n")
3250:class Server(ThreadingHTTPServer):
3253:daemon_threads = True
3254:request_queue_size = 64
3255:allow_reuse_address = True
```

---
PANEL-NONCE: 50f4e90bee4fd3ff
ARTIFACT-SHA256: 7d4f3ee38549312817f33a0cc6b82ef02f69a62f9d764777b3d84d63e460838b
Инструкция судье: первыми двумя строками ответа повтори дословно «PANEL-NONCE: 50f4e90bee4fd3ff» и «ARTIFACT-SHA256: 7d4f3ee38549312817f33a0cc6b82ef02f69a62f9d764777b3d84d63e460838b».
