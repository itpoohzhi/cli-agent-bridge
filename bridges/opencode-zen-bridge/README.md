# opencode-zen-bridge

Локальный OpenAI-совместимый мост поверх CLI `~/.opencode/bin/opencode run`.
Каждый запрос к `/v1/chat/completions` — один headless-ход
`opencode run -m opencode/<id> --format json` с промптом через stdin
(не argv: история чата > ~1 МБ пробивает macOS ARG_MAX → `Argument list too long`).

Ответ собирается из JSON-событий CLI:

| событие | что берём |
|---|---|
| `type: "text"` | `part.text` — конкатенируется в ответ |
| `type: "step_finish"` | `part.tokens` → `prompt_tokens` / `completion_tokens` |
| `type: "error"` | `error.data.statusCode` / `.message` → честная 502 |

- Порт: `127.0.0.1:9883` (переопределяется `OPENCODE_ZEN_BRIDGE_PORT`).
- Авторизация: `Authorization: Bearer $OPENCODE_ZEN_BRIDGE_KEY`; без этой переменной
  мост не стартует. `/health` открыт, `/v1/*` требуют ключ.
- Только stdlib (`/usr/bin/python3`), параллелизм 2, сквозной таймаут хода 1800 с.
- Стрим (SSE) реализован: дельты text/reasoning идут по мере событий CLI; `/health` → `"tool_emulation": true`.
  
## Модели

`ALLOWED_MODELS` (2026-10-19) — ровно 8 моделей OpenCode Zen:

| id | context | max output | `#effort` (supports_variant) |
|---|---|---|---|
| `deepseek-v4.1-flash-free` | 200000 | 32000 | да |
| `glm-5.3-flash-free` | 200000 | 32000 | нет |
| `minimax-m3.1-flash-free` | 1000000 | 512000 | нет |
| `beam-free` | 1048576 | 131072 | нет |
| `nemotron-3.5-super-vl-free` | 1048576 | 131072 | нет |
| `longcat-2.5-preview-free` | 1000000 | 131072 | нет |
| `mimo-v2.6-flash-free` | 200000 | 32000 | нет |
| `big-pickle` | 200000 | 32000 | нет |

Любой другой `model` в `/v1/chat/completions` → HTTP 400 `model_not_found`; `/v1/models` отдаёт
только эти 8. Исключены: `jev-1.13`, `jev-1.13-free`, `nemotron-3-ultra-free`,
`nemotron-3.5-lightning-free`.

4 модели **OpenCode Go** (`deepseek-v4.1-flash`, `glm-5.3-flash`, `qwen3.8-flash`,
`claude-haiku-5-5`) через этот мост НЕ ходят: клиенты обращаются к ним напрямую через
`model-georouter` (`http://127.0.0.1:10830/go/v1`; Claude Haiku — `http://127.0.0.1:10830/go`,
Anthropic Messages). Мост на такие id отвечает 400.

## Конвертация истории и tools (с 2026-10-08)

CLI принимает один текстовый аргумент, поэтому история разворачивается в размеченный
текст: `System:` уходит в блок `[system]` в начале, реплики — `User:` / `Assistant:`;
`assistant.tool_calls` и `role:"tool"` рендерятся блоками `<tool_call>{…}</tool_call>` и
`[tool result <id>] (<name>)`.

**Function calling эмулируется** (порт из muse-bridge/droid-bridge): при непустом `tools`
(и `tool_choice` ≠ `"none"`) в промпт добавляется протокол + схемы, модель отвечает блоками
`<tool_call>{"name":…,"arguments":{…}}</tool_call>`; `ToolCallParser` вырезает их из текста и
отдаёт `delta.tool_calls` (SSE) / `message.tool_calls` (non-stream) с `finish_reason:"tool_calls"`.

Почему это нужно: до 08.10 мост отдавал только текст и `finish_reason:"stop"`, а при наличии
system-сообщения tools вообще не попадали в промпт → DSH завершал ход после первой реплики
(«Локализую — смотрю…», «Completed in 11s»), а модель пыталась звать встроенные инструменты
opencode внутри CLI.

Встроенные инструменты opencode в мосте не исполняются: `opencode run` запускается с
`OPENCODE_CONFIG_CONTENT='{"permission":{"*":"ask"}}'` (переменная
`OPENCODE_ZEN_BRIDGE_OPENCODE_CONFIG`) — CLI сам отклоняет вызов («auto-rejecting»), а мост
переводит отклонённый `tool_use` (bash/read/edit/write/glob/grep — имена совпадают с DSH) в
`tool_calls` DSH: ключи `filePath→file_path`, `oldString→old_string`, `newString→new_string`,
`replaceAll→replace_all`, `timeout→timeoutMs`, фильтр по схеме, недостающий `description` у bash
подставляется. Замер 08.10: Muse почти всегда зовёт встроенный инструмент, а не маркер
`<tool_call>` — основной путь именно этот.

Грабля: `"deny"` или `tools:{bash:false}` НЕЛЬЗЯ — инструменты пропадают из запроса, и Zen отвечает
403 «OpenCode's free tier can only be used from within OpenCode». Параллельные `opencode run`
(>2) иногда падают «database is locked» (sqlite opencode) — держать `MAX_CONCURRENT=2`.

Встроенный инструмент с другим именем (08.10, живой сбой `todowrite mapped=False` → DSH
остановил ход) переводится в DSH-двойник из запроса по таблице `NATIVE_TOOL_ALIASES`:
todowrite→todo_write, webfetch→web_fetch, websearch/codesearch→web_search или MCP `*web_search*`,
list/ls→bash `ls -la` (или glob), task→subagent, multiedit→N×edit, patch→apply_patch,
skill→skill, question→ask_user_question, plan_exit→exit_plan_mode. Аргументы приводятся к схеме
запроса (алиасы ключей, strict-объекты, enum `cancelled→completed`). Двойника нет — мост
перезапускает `opencode run` с сообщением «инструмент недоступен» и списком DSH-инструментов
(`OPENCODE_ZEN_BRIDGE_NATIVE_RETRIES`, по умолчанию 2); повторы исчерпаны — в content пометка
`[opencode-zen-bridge: …повторы исчерпаны]`, а не молчаливый stop. Шаг, давший вызов для DSH,
завершает прогон (`step_finish` → SIGTERM группы): дальше Muse лишь повторяет «отклонённый»
вызов; одинаковые вызовы в одном ответе дедуплицируются.

Тесты (из корня моста, `tests/` — пакет): `uv run pytest -q` или
`python3 -m unittest discover -s tests -t .`. Проверки: `uv run ruff check server.py tests/`,
`uv run basedpyright server.py tests/`. Тесты уводят `LOG_PATH` во временный каталог — боевой
`logs/bridge.log` не пишется.
Перезапуск: `launchctl kickstart -k gui/$(id -u)/com.user.dsh-opencode-zen-bridge`.

## Запуск

`./start.sh` (ключ подхватывается из `~/.dsh/.env`).

Проверка:

```bash
curl -s http://127.0.0.1:9883/health
curl -s http://127.0.0.1:9883/v1/chat/completions \
  -H "Authorization: Bearer $OPENCODE_ZEN_BRIDGE_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"model":"big-pickle","messages":[{"role":"user","content":"Ответь ровно PONG"}]}'
```

## Использование в DSH

Провайдер `opencode-zen-bridge` в `~/.dsh/profiles/{desktop,web,headless}/cordis.patch.yml`
(`api: openai-completions`, `baseURL: http://127.0.0.1:9883/v1`,
`apiKeyEnv: OPENCODE_ZEN_BRIDGE_KEY`, `timeoutMs: 1900000`), 8 моделей и записи
в `subagent-model-selection-settings.allowedModels` (вместе с 4 моделями Go — всего 12).
