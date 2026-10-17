PANEL-NONCE: 7ca14a734738a5ae
ARTIFACT-SHA256: 7ffec7e0b134308ae412ef1861fc8ba5b2ec222be2f33c0b538a7d1f5e55006e

### Экспертиза листа Совета по коду (Round R2, seat k=3, шляпа: Реалист)

С прагматичной точки зрения (**Реалист**) повторная доработка (`R2`) закрыла все четыре блокера первого раунда (`RW-001`..`RW-004`) и оба неблокирующих замечания (`FU-001`, `FU-002`) простыми, детерминированными механизмами на стандартной библиотеке Python без раздувания архитектуры, внешних зависимостей или нарушения обратной совместимости контракта OpenAI API.

---

#### Критерий 1 — PASS: Полнота реализации и закрытие находок R1 (`ADR-001.1`..`ADR-001.4`, `RW-001`..`RW-004`, `FU-001`..`FU-002`)

1. **`ADR-001.1` (Паспортная ёмкость контекста и целевые пороги)**:
   В `bridges/muse-bridge/server.py:93-104` для `muse-wonder-1.0` и `muse-wonder-full-1.0` зафиксировано `context_length: 400_000`. Функции `_context_limit` (`server.py:423-427`), `_context_target` (`server.py:430-432`, 80% = `320_000`) и `_context_retry_target` (`server.py:435-437`, 50% = `200_000`) вычисляют бюджеты строго от паспорта модели с безопасным fallback на `DEFAULT_CONTEXT_LENGTH`. Консервативная оценка `_estimate_tokens` (`server.py:406-412`) использует `max(len(text) // 3, len(text.encode("utf-8")) // 3)`.
2. **`ADR-001.2` и `RW-001` (Детерминированная компактификация без потери инвариантов эпизодов)**:
   В `_partition_units` (`server.py:552-603`) исправлен баг склейки при повторном `tool_call_id` между разными шагами: внутренний цикл сбора `tool`-ответов (`server.py:573-582`) теперь немедленно прерывается (`break`), как только встречается сообщение с `roles[j] != "tool"`. Тем самым `assistant(tool_calls)` захватывает только непосредственно следующие за ним `tool`-сообщения своего хода, а хвостовой обязательный эпизод (`mandatory_tail`) гарантированно сохраняется даже при коллизии `call_1` в старой истории. Сиротские `tool`-сообщения по-прежнему отсекаются (`server.py:591-593`), а фаза D (`_shrink_mandatory_Messages`, `server.py:667-766`) сохраняет приоритеты `tool content -> system/developer -> last user` и валидность JSON в `tool_calls[].function.arguments` (`_truncate_json_arguments`, `server.py:530-549`).
3. **`FU-001` (Линейная сложность фазы C)**:
   В `_prune_messages` (`server.py:800-866`) предварительный отбор кандидатов с хвоста переведён на $O(n)$ по числу юнитов за счёт предподсчёта символьных и UTF-8 байтовых длин каждого юнита (`unit_chars`, `unit_bytes`, `server.py:807-818`) и инкрементального учёта маркера пропуска `_OMITTED_HISTORY_MARKER` (`server.py:831-852`), после чего финальная проверка выполняется по точно собранному промпту (`server.py:854-866`).
4. **`ADR-001.3` и `RW-002` (Классификация `context hard threshold` до клиппинга и однократный retry)**:
   Добавлена функция `_has_hard_threshold_marker(text)` (`server.py:1244-1248`) и структурная проверка сырого `p.get("error")` / `p.get("reason")` в `_turn_diagnostics` (`server.py:1265-1305`) до усечения `msg[:160]` и `detail[:300]`. Оба раннера возвращают булево поле `"hard_threshold"` в словаре результата (`Run.execute` в `server.py:1229-1239` и `ServeRun.execute` в `server.py:1572-1582`), где дополнительно проверяется сырой буфер `err_lines`. В `Handler.chat` (`server.py:2171-2258`) буферизация первого прогона и однократный retry на `target_tokens = 200_000` опираются на `bool(res.get("hard_threshold")) or _is_hard_threshold_error(...)`, что исключает потерю маркера за пределами первых 160/300 символов ошибки.
5. **`ADR-001.4`, `RW-003`, `RW-004` и `FU-002` (Санитизация секретов/промптов и разделение оценки токенов)**:
   - `RW-003`: В `_sanitize_reflected` (`server.py:1630-1660`) и `_diagnostic_text` (`server.py:1663-1695`) вырезание отражённых промптов, частей промпта и `raw_messages` выполняется **и до, и после** `_redact_secrets` (включая кандидатов с уже отредактированными секретами, нормализованными управляющими символами и префиксами длины 160 символов). Это исключает утечку пользовательского текста вокруг секрета при частичной мутации строки регулярным выражением `_SECRET_VALUE_RE`.
   - `RW-004`: В `run_attempt` (`server.py:2148-2169`) текст исключения `ServeUnavailable` перед записью в `_log` проходит через `_sanitize_reflected(str(exc), prompt, raw_messages=messages)` и нормализацию управляющих символов, так что ни в `/tmp/muse-bridge.log`, ни в диагностику не попадает отражённое тело промпта при падении `serve` с fallback на `exec`.
   - `FU-002`: Для клиентской телеметрии `usage` в `exec`-режиме введена отдельная функция `_estimate_usage_tokens` (`server.py:415-420`, используется в `server.py:2303-2304`), сохраняющая прежнюю оценку по словам без искажения `usage` на кириллице, тогда как консервативная байтовая оценка `_estimate_tokens` применяется строго для бюджетирования контекста.

---

#### Критерий 2 — PASS: Качество кода, читаемость и поддерживаемость

Код в `bridges/muse-bridge/server.py` хорошо структурирован, разбит на чистые вспомогательные функции с явными аннотациями типов и понятными границами ответственности (`_partition_units`, `_shrink_mandatory_messages`, `_prune_messages`, `_has_hard_threshold_marker`, `_sanitize_reflected`, `_diagnostic_text`). Ветвления в `Handler.chat` (`server.py:2125-2320`) прозрачны: фаза подготовки и retry полностью завершается до отправки HTTP-заголовков клиенту (`self._hdr`), что гарантирует атомарность переключения между первой и второй попыткой как для обычного JSON-ответа, так и для SSE-стриминга.

---

#### Критерий 3 — PASS: Безопасность и отсутствие утечек данных

Все каналы вывода ошибок и логов защищены от инъекций в лог и от утечки секретов и приватного текста промптов:
- `_redact_secrets` (`server.py:1615-1627`) маскирует ключи и токены (`Authorization: Bearer`, `api_key`, `secret`, `password`, `sk-...`, `ghp_...`, `eyJ...`).
- `_sanitize_reflected` (`server.py:1630-1660`) удаляет как полные промпты, так и отдельные сообщения/строки/префиксы (от `_MIN_PROMPT_PART_STRIP_LEN = 12` символов) до и после редактирования секретов.
- Ошибки `ServeUnavailable` при fallback на `exec` (`server.py:2152-2166`), диагностика неуспешного хода (`server.py:2221-2258`) и терминальное сообщение исчерпания retry (`server.py:2225-2231`) проходят через единый контур очистки и усечения до `_MAX_DIAG_CHARS = 300`.

---

#### Критерий 4 — PASS: Покрытие тестами и верификация граничных случаев

В `tests/test_muse_bridge_killpg.py` реализованы все тесты матрицы `T-00`..`T-23` из архитектурной спецификации и добавлены целевые регрессионные тесты для всех замечаний первого раунда:
- `test_t24_duplicate_tool_call_id_across_episodes_and_linear_phase_c` (`test_muse_bridge_killpg.py:2396-2481`) проверяет сохранность хвостового `tool`-эпизода при дублировании `tool_call_id = "call_1"` в истории (`RW-001`) и проверяет $O(n)$ бюджет вызовов `_assemble_prompt` на 120 сообщениях (`FU-001`).
- `test_t25_hard_threshold_after_long_prefix_retries_in_exec_and_serve` (`test_muse_bridge_killpg.py:2483-2603`) проверяет срабатывание retry при маркере `context hard threshold` после 220-символьного префикса как в `exec`, так и в `serve` (`RW-002`).
- `test_t26_reflected_message_with_embedded_secret_leaves_neither_canary_nor_secret` (`test_muse_bridge_killpg.py:2605-2667`) проверяет отсутствие утечки и приватного текста (`BODY_PRIVATE_CANARY`), и встроенного секрета (`synthetic-secret`) в `stream=False`/`stream=True`, а также проверяет `usage` на кириллице (`FU-002`).
- `test_t27_serve_unavailable_with_reflected_prompt_does_not_leak_to_log` (`test_muse_bridge_killpg.py:2669-2707`) подтверждает, что при `ServeUnavailable` с отражённым промптом лог не содержит ни `SERVE_FALLBACK_PRIVATE_CANARY`, ни `fallback-secret-123` (`RW-004`).

---

#### Критерий 5 — PASS: Производительность и ресурсная дисциплина

После устранения квадратичного пересчёта `_assemble_prompt` в фазе C (`server.py:807-852`) компактификация работает за линейное время относительно размера входной истории. Повторный вызов `_assemble_prompt` выполняется только один раз для верификации выбранного суффикса (`server.py:854`) и при редкой граничной корректировке из-за округления целочисленного деления (`server.py:855-866`). Однократный retry строго ограничен `max_attempts = 2` и выполняется только при явном маркере переполнения контекста.

---

#### Критерий 6 — PASS: Контрактная совместимость и эксплуатационная надёжность

Внешний HTTP-контракт `/v1/models` и `/v1/chat/completions` (`stream=false` и `stream=true`) полностью сохранён. При успешном retry в `stream=true` клиент получает чистый поток SSE-чанков только успешной второй попытки без дублирования `role: assistant` и без артефактов первой попытки (`server.py:2171-2220`, `2260-2285`). При исчерпании обеих попыток корректно возвращается `HTTP 502` (`upstream_error`) для `stream=false` либо валидный SSE-чанк с `finish_reason: "error"` и завершающим `[DONE]` для `stream=true` (`server.py:2232-2258`).

---

SUB code: PASS — Линейная компактификация, изоляция соседних tool-эпизодов и retry реализованы чисто и без регрессий в `bridges/muse-bridge/server.py:552-603`, `bridges/muse-bridge/server.py:800-866`, `bridges/muse-bridge/server.py:2125-2258`.
SUB security: PASS — Двухфазное удаление отражённых промптов/сообщений до и после редактирования секретов и очистка `ServeUnavailable` предотвращают утечки в `bridges/muse-bridge/server.py:1630-1695`, `bridges/muse-bridge/server.py:2152-2166`.
SUB tests: PASS — Полная матрица `T-00..T-27` покрывает все ветки спецификации и регрессии R1 в `tests/test_muse_bridge_killpg.py:1572-2707`.
SUB contracts: PASS — Паспорт `context_length: 400_000`, семантика `usage` и OpenAI-совместимые ответы `stream=false`/`stream=true` соблюдены в `bridges/muse-bridge/server.py:93-104`, `bridges/muse-bridge/server.py:415-420`, `bridges/muse-bridge/server.py:2232-2320`.

ОБЩИЙ ВЕРДИКТ: ACCEPT
