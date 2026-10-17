PANEL-NONCE: 946b85b2e74b8d6d
ARTIFACT-SHA256: 45905654733fd19ee8911b86033bd395b14c6f3ad5066803c58d0cb4b7f2f0ed

# Рецензия Совета Тимлидов — Seat k=1 (Реалист)

- `artifact_sha256: 45905654733fd19ee8911b86033bd395b14c6f3ad5066803c58d0cb4b7f2f0ed`
- `VERDICT: ACCEPT`

## 1. Соответствие реализации `AD-001..AD-005` и `F-001` (`bridges/muse-bridge/server.py`)

1. **`AD-001` и `CD-001` (Журналирование ранних выходов HTTP 502 / SSE error в `Handler._serve_json`):**
   - Все три ранние ветки отказа (`launcher_missing`/`spawn_failed` на строках 1870–1884, `state != "ok" or rc != 0` на строках 1885–1901, пустой вывод `not content and not tool_calls` с `state=empty_output` на строках 1906–1927) перед вызовом `self._send(502, ...)` и `return` записывают в `bridge.log` одну структурированную строку через `_format_err_log(...)`.
   - Поле `error.detail` формируется как `_redact_secrets(str(out.get("err") or ""))[:500]`; при `err=None` возвращается `""`, а не `"None"`. Успешная ветка `done ...` (строка 1973) и ранний выход при `self._client_gone` (строка 1855) сохранены без регрессий.

2. **`AD-002` и `CD-002` (Извлечение `TurnError` и `reason` из `turn/completed` в `ServeRun.execute`):**
   - В `ServeRun.execute` заведён отдельный список `turn_diag_lines: list[str] = []` (строка 1137), не конкурирующий с потоком `drain_stderr` (`err_lines`).
   - Функция `_turn_diagnostics(params, prompt)` (строки 231–282) защитно разбирает `params.error` (`kind[:64]`, `message[:160]`, булев `retryable`, компактно сериализованный и предварительно очищенный `quota[:120]`, либо недиктовый `error` как `message[:160]`) и недублирующий `params.reason[:160]`.
   - Выдерживается детерминированный бюджет приоритетного блока `<= 300` символов с усечением в порядке `("quota", "reason", "message", "kind")` и сохранением минимума `min(16, len(reason))`.
   - Перед сборкой `err` поток `err_thread` присоединяется (`err_thread.join(timeout=5)` с флагом `stderr_joined = True`, исключающим двойной `join` в `finally`), после чего `turn_diag_lines` помещаются в начало `err`, а хвост `err_lines[-6:]` добавляется только в остаток бюджета до 500 символов (`_clip_diagnostic(stderr_tail, 499 - len(err))`).

3. **`F-001` и `NFR-03` (Редакция секретов `_redact_secrets` и `_redact_quota` до обрезки):**
   - `_redact_secrets` (строки 177–194) маскирует буквальное значение `AUTH_KEY`, заголовки `Authorization:`, `Bearer`, JSON-поля и кавычечные многословные секреты (`api_key`, `token`, `secret`, `password`, `bridge_key`), а также токены `sk-[A-Za-z0-9_-]{12,}`.
   - `_redact_quota` (строки 214–228) рекурсивно очищает чувствительные ключи и строковые значения внутри `error.quota` до `json.dumps`.
   - `_clip_diagnostic` (строки 197–202) предотвращает разрезание маркера `[REDACTED]` на границах усечения полей, а на границе `Handler._serve_json` (строки 1858–1866) дополнительно удаляются отражённый `prompt` и `messages[*].content`.

4. **`AD-003` (SSE keepalive пустыми data-чанками и 3-фазное запечатывание потока под `self._wlock`):**
   - На уровне класса `Handler` заданы безопасные значения по умолчанию (`_sse_phase: str = "OPEN"`, `_keepalive_stop: threading.Event | None = None`, `_client_gone: bool = False`), не разделяющие мутабельных `Event` между экземплярами при `Handler.__new__(Handler)`.
   - `_keepalive_loop` (строки 1511–1517) отправляет валидный кадр `self._sse_emit(self._sse_chunk({"content": ""}), keepalive=True)`.
   - В `_sse_write` (строки 1439–1464) проверка фазы (`OPEN` для keepalive, не `CLOSED` для финальных кадров), запись в `self.wfile`, `flush()` и терминальный переход в `CLOSED` при записи `"data: [DONE]\n\n"` (в блоке `finally`) выполняются внутри одного удержания нерекурсивного `self._wlock`.
   - В `_sse_stop_keepalive` (строки 1519–1528) устанавливается `_keepalive_stop.set()`, под `self._wlock` выполняется идемпотентный переход `OPEN -> FINALIZING`, а `self._ka_thread.join(timeout=2)` вызывается вне замка.

5. **`AD-004` (Флаги `--disable-*` и сохранение fallback по `approval/request`):**
   - В `ServeRun.execute` добавлены `--disable-write` и `--disable-shell` (строки 1113–1114).
   - В `Run.execute` добавлены `--disable-write`, `--disable-shell`, `--disable-web-tools`, `--disable-reminders` с сохранением `--yolo` (строки 852–855).
   - Реакция `ServeUnavailable` на `approval/request` и `userInput/request` в `ServeRun._handle_event` (строки 1221–1222) и переход на `exec` сохранены.

6. **`AD-005` (Синхронизация `ALLOWED_MODELS`):**
   - В `ALLOWED_MODELS` (строки 77–78) добавлены `"muse-wonder-1.0"` и `"muse-wonder-full-1.0"` с `{"context_length": 1048576, "max_output": 131072}`.

## 2. Проверка на гонки, утечки секретов и обратную совместимость

- **Потокобезопасность и отсутствие дедлоков:** `self._wlock` захватывается ровно один раз на операцию записи или смены фазы; `join(timeout=2)` и обработка ошибок сокета (`_log`, `_kill_current_run`) выполняются вне `self._wlock`, поэтому порядок захвата замков (`_wlock`, `_LOG_LOCK`, `_cleanup_lock`) не нарушается. Запись любого кадра после `data: [DONE]\n\n` невозможна по построению.
- **Обратная совместимость:** все 8 защищённых функций управления группами процессов и карантином слотов (`_kill_group`, `_wait_group_exit`, `_terminate_run`, `_quarantine_slot`, `Run.close`, `ServeRun.close`, `_client_gone_probe`, `_watch_client`) не затронуты. Внешний OpenAI wire-контракт сохранён.

## 3. Оценка тестового покрытия и верификации (`tests/test_muse_bridge_killpg.py`)

- В `tests/test_muse_bridge_killpg.py` сохранены все 18 baseline-тестов и добавлены 15 новых тестов (всего 33 теста):
  - `ErrorLoggingTest` (4 теста): проверка всех 3 ранних веток ошибок в режимах JSON и SSE, отсутствия логов `error` на успешном ходе, пустого `detail` при `err=None`, маскировки всех типов секретных канареек (включая многословные кавычечные секреты, `AUTH_KEY`, вложенные ключи `quota` и пересечение границ 300/500 символов).
  - `ServeTurnErrorExtractionTest` (4 теста): проверка извлечения типизированного `TurnError` и `reason`, дедупликации `reason == message`, устойчивости к невалидным типам `error`/`reason`, приоритета над шумным `stderr` (>500 символов), 6-строчного fallback при отсутствии `error`/`reason` и покомпонентных/общих лимитов (`64`/`160`/`120`/`300`) без разрезания `[REDACTED]`.
  - `SseDataKeepaliveTest` (4 теста): проверка классовых атрибутов `Handler.__new__(Handler)` и сценариев `S1` (интеграционные data-тики и сохранность текста/tool_calls), `S2` (блокирующий `flush()` с синхронизацией через `threading.Event` до финализации), `S3` (подавление тиков после `FINALIZING` и дублирующего `[DONE]` после `CLOSED`), а также перехода в `CLOSED` при `OSError` на записи `[DONE]`.
  - `CliDisableFlagsAndApprovalFallbackTest` (2 теста): проверка фактического `argv` для `serve` и `exec` и отсутствия `approval/decide` при fallback по `approval/request`.
  - `AllowedModelsSyncTest` (1 тест): проверка `muse-wonder-1.0` и `muse-wonder-full-1.0` в `ALLOWED_MODELS`, `/health` и `/v1/models`.
- Все проверки в clean-room `VERIFIER` (`receipts/verifier-receipt.json`: `VER-001` unittest 33 теста, `VER-002` `py_compile`, `VER-003` `ruff format --check`, `ruff check`, `basedpyright --level error`, `VER-004` `muse serve/exec --help`, `git diff --check`) завершились с `exit_code: 0`.
- *Примечание (неблокирующее):* в таблице трассировки раздела 2 `code-review-package.md` указаны черновые имена вспомогательных функций и тестов (`_scrub_quota_value`, `_format_turn_completed_diag`), тогда как в диффе раздела 5 и в самом коде используются финальные имена (`_redact_quota`, `_turn_diagnostics`). На корректность кода и тестов не влияет.

```json
{
  "artifact_sha256": "45905654733fd19ee8911b86033bd395b14c6f3ad5066803c58d0cb4b7f2f0ed",
  "verdict": "ACCEPT",
  "seat_k": 1,
  "findings": []
}
```
