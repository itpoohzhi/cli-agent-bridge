PANEL-NONCE: 0159aaaa5637c66c
ARTIFACT-SHA256: e26ce551c7ff8ed5ab8220c339660271f43e1af0c9a20062d99a34cc854bdc30

### F-001 NON_BLOCKING — В `_serve_one_attempt` события `session.tool.input.started` и `session.tool.called` не обновляют `last_token_at`, если `first_token_at` уже установлен
- **Доказательство:** `bridges/opencode-zen-bridge/server.py:5068-5078` и `bridges/opencode-zen-bridge/server.py:4877-4881`.
- **Суть:** В ветке `elif etype == "tool_event":` переменная `last_token_at` обновляется только при `result["first_token_at"] is None` или при `etype_raw == "session.tool.input.delta"`. Если модель сначала выдала `reasoning`/`text` (`first_token_at is not None`), затем вызвала `session.tool.input.started` без промежуточных `delta`-событий, и вызов длился дольше `idle_timeout`, то в момент прихода `session.tool.called` вызов завершается (`tool_state.has_active()` становится `False`), но `last_token_at` остаётся равным времени до старта тула. На следующей итерации цикла `while time.monotonic() < deadline:` условие `_zen_idle_expired(now, last_token_at, idle_timeout, tool_state.has_active())` сработает немедленно после `session.tool.called`, оборвав многошаговую генерацию после тула.
- **Рекомендация:** Обновлять `last_token_at = time.monotonic()` на каждом `etype == "tool_event"` (включая `started` и `called`), аналогично тому, как это сделано в `Handler` (`bridges/opencode-zen-bridge/server.py:8528-8530`).

### F-002 NON_BLOCKING — Несимметричная защита TTFT и обновления `last_token_at` при `tool_use`/`tool_call` между `Run.execute` и потоковым `Handler`
- **Доказательство:** `bridges/opencode-zen-bridge/server.py:6787-6793`, `bridges/opencode-zen-bridge/server.py:6842` против `bridges/opencode-zen-bridge/server.py:4873-4875` и `bridges/opencode-zen-bridge/server.py:8528-8532`.
- **Суть:** В `_serve_one_attempt` условие TTFT явно защищено предикатом `not tool_state.has_active()`, а в потоковом `Handler` события `tool_use`/`tool_call` безусловно проставляют `first_token_at` и `last_token_at` до разбора `payload`. В `Run.execute` (`on_idle`, строка 6787) проверка `first_token_at is None and now - attempt_start > ttft_timeout` не проверяет `not bool(tool_activity)`, а в цикле событий (строка 6842) `tool_activity.observe(etype, event)` не сопровождается безусловным обновлением `first_token_at`/`last_token_at`, полагаясь только на непустой `frame.get("tool")` в `payload`.
- **Рекомендация:** Добавить `not bool(tool_activity)` в условие TTFT в `Run.on_idle` и `Handler` watchdog, а также синхронизировать обновление `first_token_at`/`last_token_at` при `etype in ("tool_use", "tool_call")` в `Run.execute`.

### F-003 NON_BLOCKING — Двойной инкремент счётчика `_anonymous` в `_ToolActivity.observe` при переходе `pending -> running` без `callID`/`id`
- **Доказательство:** `bridges/opencode-zen-bridge/server.py:406-429`.
- **Суть:** Для событий без `callID`/`id` (`call_id == ""`) оба статуса `"pending"` и `"running"` дают `running = True` и увеличивают `self._anonymous += 1`. Если для одного анонимного вызова последовательно придут события `pending`, затем `running`, а в конце одно событие `completed` (`self._anonymous -= 1`), счётчик `_anonymous` останется равным `1`, и `bool(tool_activity)` останется `True` до конца попытки, отключая `idle_timeout`.
- **Рекомендация:** Инкрементировать `_anonymous` только на один стартовый статус либо хранить состояние по имени `tool` в fallback-ветке без `callID`/`id`.

### F-004 NON_BLOCKING — В логах срабатывания `split_timeout` выводится глобальный `TIMEOUT_S` вместо фактического TTFT/Idle таймаута
- **Доказательство:** `bridges/opencode-zen-bridge/server.py:6943-6945` и `bridges/opencode-zen-bridge/server.py:8678-8680`.
- **Суть:** При срабатывании `split_timeout[0]` в `Run.execute` и `Handler` логируется строка `f"exec/stream timeout after {TIMEOUT_S:.0f}s, killing proc group"`, что при разборе логов создаёт видимость срабатывания полного `TIMEOUT_S`, а не `ttft_timeout` (25с) или `idle_timeout` (15с).

VERDICT: ACCEPT
