# droid-bridge (DSH)

OpenAI-совместимый мост DeepSeek Harness → Factory Droid CLI (`droid exec`) с
эмуляцией OpenAI function calling (tool_emulation). Порт **9882**.

- Один запрос `/v1/chat/completions` = один ход в долгоживущем процессе
  `droid exec --input-format stream-jsonrpc --output-format stream-jsonrpc`
  (по процессу на keyed-чат, см. «RPC-режим») через канонический лончер
  `~/.config/factory-launch/droid-cli.sh` (egress-пиннинг; голый droid-бинарь не
  используется — бьёт в WAF Factory; fallback на него удалён).
- Модели и уровни effort — из каталога `fleet.json` (6 моделей Droid-флота,
  только dev-контекст): sonnet-5-5, gemini-3.8-flash, grok-4.7,
  deepseek-v4.1-flash, gpt-6.1-sol, glm-5.3.
- `model`/`reasoning_effort` валидируются строго **до** SSE: не из каталога —
  HTTP 400 `model_not_allowed` / `unsupported_reasoning_effort`; никаких
  clamp, алиасов и silent fallback. `-r` передаётся всегда (из запроса либо
  `default_effort` модели). Автономность и effort задаются параметрами RPC
  (`autonomyLevel`, `reasoningEffort`); `--skip-permissions-unsafe` не
  используется никогда.
- `tools` в запросе → в промпт добавляется протокол
  `<tool_call>{"name":…,"arguments":{…}}</tool_call>` и схемы инструментов;
  потоковые блоки переводятся в `delta.tool_calls` + `finish_reason:"tool_calls"`,
  история `role:"tool"` рендерится как `[tool result <id>] (<name>)`.
- Транспорт droid — только текст; у модели нет встроенных tool-вызовов, эмуляция
  на стороне моста (дословно из `~/.dsh/bridges/claude-p-bridge/server.py`).

## Файлы

- `server.py` — сам мост (HTTP, `/health`, `/v1/models`, `/v1/chat/completions`,
  framing/admission, image-модуль).
- `fleet.json` — каталог флота: модели, allowed efforts, `default_effort`,
  `default_model`, лимиты изображений, admission, `policy_ref`, `technical_ref`.
  Мост читает его при старте (sha и число моделей пишутся в журнал строкой
  `fleet_sha256=… models=…`); `model-efforts.json` в рантайме не читается.
- `fleet_check.py` — read-only проверка каталога и профилей (`/opt/homebrew/bin/python3`,
  PyYAML; JSON в stdout, exit 0 только при полном успехе).
- `tests/` — stdlib `unittest` (см. «Тесты»).
- `start.sh` — запуск: читает ключ из окружения или `~/.dsh/.env`
  (строка `DROID_DSH_BRIDGE_KEY=…`), затем `exec /usr/bin/python3 server.py`.
- `tools/b_guard.py` — офлайн-охранник бюджета agent-instructions (см. «B: охранник»).
- `workspace/` — cwd для droid-процессов; `workspace/state/` — метаданные чатов
  (`conversations.v1/chats/<2hex>/<sha256>.json`, 0600/0700, только хеши) и
  `children.json`; `workspace/runtime/factory-home` — чистый Factory home детей;
  для image-запросов — per-run каталоги `img-<uuid32>` (0700, файлы 0600),
  удаляются при любом исходе. Свипер трогает только `prompt-*`/`img-*`.

## Env

| Переменная | Default | Назначение |
|---|---|---|
| `DROID_DSH_BRIDGE_HOST` | `127.0.0.1` | адрес |
| `DROID_DSH_BRIDGE_PORT` | `9882` | порт |
| `DROID_DSH_BRIDGE_KEY` | — (обязателен) | ключ авторизации (Bearer / x-api-key) |
| `FACTORY_API_KEY` | — | headless-вход `droid exec` без интерактивного логина; `start.sh` читает из `~/.zshenv` |
| `DROID_DSH_BRIDGE_MODEL` | `default_model` каталога | модель по умолчанию (обязана быть в каталоге) |
| `DROID_DSH_BRIDGE_MAX_CONCURRENT` | `4` | cap процессов droid (resident, стартующие, title, закрывающиеся) и одновременных ходов |
| `DROID_DSH_BRIDGE_IDLE_SECONDS` | `2700` | idle-гашение процесса чата, с (SID и файлы остаются, следующий ход — `load_session`) |
| `DROID_DSH_BRIDGE_QUEUE_TIMEOUT` | `900` | ожидание слота, с |
| `DROID_DSH_BRIDGE_KEEPALIVE` | `15` | keepalive SSE, с |
| `DROID_DSH_BRIDGE_FLEET` | `<каталог моста>/fleet.json` | путь к каталогу флота |
| `DROID_DSH_BRIDGE_IMAGE_PROBE` | — | `1` — включить `probe`-модели изображений (**только для копии моста**, не для боевого запуска) |
| `DROID_LAUNCHER` | `~/.config/factory-launch/droid-cli.sh` | канонический лончер droid |
| `DROID_DSH_BRIDGE_RECEIPT_REQUIRED` | `1` | допуск образа droid по receipt (`workspace/state/droid-binary-receipt.json`) на каждом spawn; `0` — только стенд/разработка |
| `DROID_DSH_BRIDGE_INSTR_LIMIT` | `60000` | жёсткий предел блока agent-instructions формы KB (cwd запроса = KB либо блок целиком из копий канона), Б (REQ-003): больше — 503 `launcher_unavailable` до spawn/add (внутреннее имя `REQ003_SIZE_EXCEEDED` только в журнале) |
| `DROID_DSH_BRIDGE_INSTR_MARGIN` | `2048` | запас для остальных блоков (WA/AB и т.п.): допустимый блок = `maxBytes` профиля − запас (при неизвестном `maxBytes` — 106496) |
| `DROID_DSH_BRIDGE_GUARD_TICK` | `30` | период автоматического контура b_guard внутри моста, с |
| `DROID_DSH_BRIDGE_PROFILES_DIR` / `DROID_DSH_BRIDGE_CANON` | `~/.dsh/profiles` / `~/Мой диск/Context/AGENTS.md` | профили DSH и канон, которые проверяет контур (только чтение) |
| `DROID_BRIDGE_MAX_RPC_LINE_BYTES` / `_MAX_STDERR_BYTES` / `_MAX_INBOX_BYTES` / `_MAX_TURN_TEXT_BYTES` / `_MAX_CHATS` | 8 МиБ / 64 КиБ / 4 МиБ / 10 МиБ / 4096 | байтовые бюджеты RPC-строки, stderr, очереди событий (каждая запись учитывается минимум 64 Б), text/thinking хода (дельта и итог одного блока считаются один раз) и индекса чатов (превышение — 502 `proxy_error`, процесс/слот возвращаются) |
| `DROID_BRIDGE_MAX_JSON_STRUCT_TOKENS` | `200000` | предел числа `{`/`[` вне строк в одной RPC-строке: строка из миллионов пустых объектов отклоняется до `json.loads` (502 `proxy_error`); глубокая вложенность — тоже контролируемая ошибка хода, читатель не падает |

Доставка ответа клиенту идёт срезами по 64 КиБ (JSON — с точным `Content-Length` без полной копии
экранированного текста, SSE — несколькими событиями), поэтому потолок памяти определяет бюджет хода
(10 МиБ), а не размер ответа; отдельный spool ответа на диск не используется: текст ограничен бюджетом
хода, а ENOSPC при spool картинок даёт 502 `proxy_error` (новых публичных кодов, в том числе 507, нет).

Модель и `reasoning_effort` берутся из запроса (effort передаётся как `-r`;
модель по умолчанию — каталог/env). Секретов в коде нет: только окружение.
`DROID_DSH_BRIDGE_IMAGE_PROBE` не добавляется ни в `start.sh`, ни в launchd plist.

## Каталог `fleet.json` (C-01)

- Инварианты (класс I) проверяются при старте: уникальные `id`, `efforts ⊆
  {minimal,low,medium,high,xhigh,max}`, `default_effort ∈ efforts`,
  `default_model ∈ ids`, `images.status ∈ {unsupported,unverified,probe,confirmed}`,
  `explicit_unsupported ⇒ status=unsupported`, `unsupported|unverified ⇒ method=null
  ∧ input=["text"]`, `confirmed ⇒ method≠null ∧ proof≠null ∧ "image" ∈ input`,
  `probe ⇒ method≠null ∧ "image" ∈ input ∧ DROID_DSH_BRIDGE_IMAGE_PROBE=1`,
  обязательные блоки `admission` и `image_limits`. Нарушение — отказ старта
  (rc=1, строка `fleet_invalid model=<id|-> reason=<slug>`, порт не слушается).
- Класс II (применимость proof к бинарю и effort) — **деградация модели**, не
  отказ старта: image-запросы получают 400 `image_input_not_supported` и строку
  `image_proof_invalid model=… reason=droid_binary_sha|impl_version|formats|effort`;
  текстовый путь и `/health` не затрагиваются.
- В Stage 1 все модели — `unverified` (glm-5.3 — `unsupported`), `input: [ text ]`:
  реклама image в профилях появляется только после подтверждения пар
  (`images.status=confirmed`) отдельным запуском.

## Валидация запроса (C-02)

Порядок отказов (все — до SSE): auth 401 → framing 400 `invalid_request` →
413 `payload_too_large` (тело > 32 MiB) → admission 503 `overloaded` → чтение
тела (короткое → 400) → JSON (не JSON / не объект → 400) → path 404 → модель
(400 `model_not_allowed`) → effort (400 `unsupported_reasoning_effort`) →
`reasoning`-объект (400 `unsupported_parameter`) → изображения → лончер (503
`launcher_unavailable`) → SSE/JSON. `Transfer-Encoding` и нечисловой/пустой/
отрицательный/конфликтующий `Content-Length` — 400 `invalid_request` с закрытием
соединения; остаток после 413 не разбирается как следующий запрос.
Admission: резерв байт по заявленному `Content-Length` под
`admission.max_inflight_body_bytes` до чтения тела и неблокирующий семафор
`admission.max_http_connections` на приёме соединений; нехватка — 503
`overloaded` немедленно.

## Изображения (C-08…C-11)

- Принимается только `{"type":"image_url","image_url":{"url":"data:image/png;base64,<payload>"}}`
  в сообщениях роли `user`; PNG по магическим байтам (декодирования пикселей нет,
  сторонних библиотек нет). JPEG/GIF/WebP с корректной сигнатурой →
  `unsupported_image_type`, несовпадение MIME и сигнатуры → `image_type_mismatch`.
- Модель обязана быть `confirmed` (в копии моста — `probe` при
  `DROID_DSH_BRIDGE_IMAGE_PROBE=1`) и иметь применимый proof; иначе 400
  `image_input_not_supported` до запуска — молчаливого отбрасывания нет.
- Лимиты — из `fleet.json.image_limits`: ≤16 изображений, ≤20971520 байт на
  изображение, ≤20971520 суммарно, тело ≤33554432 байт.
- Хранение (`workspace-read`, impl_version 1): per-run каталог
  `workspace/img-<uuid32>` (0700), файлы `img-<N>.png` (0600), `prompt.txt` (0600)
  внутри; процесс droid стартует с `cwd` = этот каталог. Каталог удаляется при
  любом исходе (успех, исключение, ретраи, обрыв клиента), устаревшие `img-*`
  свипаются при старте.
- В промпт добавляется хвост `[attachments]` с маркерами `[image N]` и правилом
  открывать файлы только через Read; при наличии `tools` строка протокола
  получает исключение «…, except Read on the attachment files listed under
  [attachments].».
- Таксономия ошибок (C-10): `image_input_not_supported`, `image_url_not_allowed`,
  `invalid_image_content`, `invalid_image_base64`, `unsupported_image_type`,
  `image_type_mismatch`, `image_too_large`, `images_too_large`, `too_many_images`,
  413 `payload_too_large`, framing 400 `invalid_request`, 503 `overloaded`.
- Журнал image-запросов — только счётчики:
  `exec … images=<n> image_bytes=<N> image_types=<csv> …` (без base64 и путей).

## Эндпоинты

- `GET /health` и `/v1/health` — без авторизации, ровно 7 ключей: `ok`,
  `transport`, `model`, `active`, `max_concurrent`, `tool_emulation`, `uptime_s`.
  `ok=false`, если допуск образа обязателен (`RECEIPT_REQUIRED`), а receipt отсутствует/не проходит проверку
  (ни один ход не будет обслужен); состояние контура b_guard в `/health` не выводится (контракт 7 ключей), оно
  видно только в журнале (`instr_guard_alert`).
- `GET /v1/models` и `/models` (с авторизацией) — `{"object":"list","data":[…6…]}`,
  первым `default_model`; запись `{"id","object":"model","owned_by":"factory-droid",
  "created":0,"context_length":…}`.
- `POST /v1/chat/completions` и `/chat/completions` — см. выше; `stream:true`
  отдаёт SSE (`delta.content`, `delta.reasoning_content`, `delta.tool_calls`,
  `finish_reason`, usage-чанк при ненулевых токенах, `[DONE]`).

## Журнал

`logs/` (JSON-строки stdout launchd). Формат ключевых строк:
`exec model=<id> effort=<lvl> effort_source=<request|default> autonomy=<lvl> autonomy_source=<request|default> prompt_bytes=… [images=…] <tag>`,
`usage sess=<sid8|-> raw=<in>/<out> rep=<in>/<out> resumed=<0|1> turns=<n>`,
`done model=<id> rc=<n> state=<s> … <tag>`,
`reject reason=<тип> model=<id каталога|unknown> model_len=<n> client=<ip:port>`.
Тела запросов, ключи, base64 и пути хранилища в журнал не попадают; в строке
`reject` — только каталожный id (или `unknown`) и длина клиентской строки.
Служебные строки вне строгих форматов: `session_rpc chat=<hash8> key=<1|0>
path=<hot|restore|rebase|cold|ephemeral> gen=<n> sid=<sid8|->` (по ходу),
`instr_guard sections=<N> omitted=<пути|-> bytes=<B>` (первый запрос нового чата),
`restore_integrity …` (повтор служебных блоков после load -> санитация),
`instr_guard_alert state=<ok|unsafe|unknown> warnings=<n> reasons=… max_bytes=…` (контур b_guard: смена состояния
профиля/канона; при `state=ok` и `warnings>0` — предупреждения `LOW_MARGIN_*`/`LINE_ORACLE_RISK`, трафик не
останавливается), `guard_state state=ok max_bytes=…`, `instr_gate_alert guard=unsafe refused=<0|1> bytes=… limit=…`
(гейт при небезопасном профиле) и `instr_gate_alert reason=REQ003_SIZE_EXCEEDED bytes=… limit=…` (блок сверх предела), `droid_receipt_invalid err=…` (старт без валидного receipt),
`session_rpc leader_exited_pipe_held pid=… rc=…` (лидер вышел, потомок держит pipe: группа добивается).

## Запуск и проверка

```bash
~/Library/LaunchAgents/com.user.dsh-droid-bridge.plist   # launchd (см. deploy/)
curl -s http://127.0.0.1:9882/health | python3 -m json.tool
curl -s -H "Authorization: Bearer $DROID_DSH_BRIDGE_KEY" \
  http://127.0.0.1:9882/v1/models | python3 -m json.tool
```

`/health` отвечает без авторизации и содержит `"tool_emulation": true`.

## fleet_check.py

Read-only проверка каталога и профилей; JSON в stdout, exit 0 только при полном
успехе (расхождение sha `models.md` → `policy.sha_match=false` + exit 1;
`default_compat.status` = `ok` / `not_applicable` / `BLOCKED-DEFAULT`).

```bash
/opt/homebrew/bin/python3 fleet_check.py                 # каталог + профили + policy
/opt/homebrew/bin/python3 fleet_check.py --live-droid    # + `--list-tools` по 6 id
/opt/homebrew/bin/python3 fleet_check.py --image-census /path/census-final.json
```

## Тесты

```bash
cd ~/.dsh/bridges/droid-bridge
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest discover -s tests -v
```

Набор — stdlib `unittest`, без сети и без реального droid. Процесс droid в тестах —
**настоящий subprocess** `tests/fake_droid.py` (stream-jsonrpc по stdin/stdout:
ACK `add_user_message` мгновенный и не завершает ход, нотификации, retract,
сбои), лончер подставляется через `DROID_LAUNCHER`. Покрыто: каталог (классы I/II),
строгая валидация model/effort, framing/413/admission, tool emulation, ретраи,
image-путь (таксономия C-10, лимиты, права 0700/0600, очистка, fail-closed proof),
журнал, а также `tests/test_rpc_*.py` (дельта истории, изоляция чатов, title, idle-реап
и restore того же SID, cap/вытеснение, таймауты, метаданные, остановка, дрейф droid)
`tests/test_rpc_rework.py` / `tests/test_rpc_cycle3.py` / `tests/test_rpc_cycle4.py` / `tests/test_cycle4_tools.py` (регрессии замечаний совета cycle-2/cycle-3/cycle-4: гейт и контур b_guard, ошибки записи состояния, изоляция ходов, бюджеты и доставка срезами, receipt schema 2, группы процессов, реапер, права каталогов) и `tests/test_b_guard.py`. Идентификаторы обязательств `TM-NNN` — в именах методов
(`-k tm001`) и docstring. `tests/baseline_inventory.json` — сопоставление 92 baseline-тестов
с текущими. Файлы — только во временных каталогах.

## RPC-режим (долгоживущий droid на чат)

- **Ключ чата** — `prompt_cache_key` запроса; в argv/путь не попадает, идентичность —
  `sha256(namespace + ключ)`. Без ключа (или с невалидным — нового 400 нет), для
  title-запросов (определяются по структуре: system-инструкция, 2 messages, без tools,
  `max_tokens=64`) и для запросов с изображениями — эфемерная чистая сессия с replay
  истории запроса под общим cap процессов.
- **Дельта истории.** DSH-запрос — авторитетная история. Мост хранит хеш-цепочку
  потреблённого префикса и проекцию выданных assistant-сообщений; префикс совпал —
  в RPC уходит только непросмотренный суффикс (все сообщения кроме последнего с
  `skipAgentLoop:true`, последнее запускает один цикл). Расхождение, форк, правка,
  компакция, смена system/tools/cwd, недоставленный ход — новая generation:
  `initialize_session` + replay всей истории запроса. Fuzzy-сопоставления нет.
- **Ресурсы и порядок** `L → P → T`: аренда чата (одновременные запросы одного ключа
  идут по очереди), ёмкость процессов `P` (cap 4, FIFO-очередь 900 с с keepalive 15 с,
  вытеснение только idle по LRU: SIGTERM → waitpid 2 с → SIGKILL) и разрешение хода `T`.
- **Idle** `DROID_DSH_BRIDGE_IDLE_SECONDS` (2700 с): процесс закрывается штатно, SID и
  метаданные остаются; следующий ход — `load_session` того же SID (не больше 5 restore
  на SID, затем свежая generation; после load — проверка целостности служебных блоков).
- **Допуск образа (AD-010).** Мост запускает droid только как `DROID_BIN=<образ из receipt>`:
  `tools/droid_image.py` копирует глобальный бинарь в `workspace/runtime/droid-image/<sha256>/droid`
  (0500), в изолированных `runtime/probe-home`/`probe-cwd` выполняет реальные пробы (spawn с чтением
  `factoryProtocolVersion` и model read-back, update — `list_tools` → отключение всех → read-back
  `settings_updated`, load — `load_session` того же SID вторым процессом) и только после них атомарно пишет
  receipt **schema 2**: `image_path`, `image_sha256`, `protocol` (`api_version`, `protocol_version`),
  `tools_policy` (`disabled_tool_ids` + digest), `settings_profile` (профиль безопасных настроек + digest),
  `probes`. На каждом spawn receipt читается заново: нет/schema≠2/sha образа не совпал/digest компонента
  не сошёлся/проба не `ok` — 503 `launcher_unavailable`; живой `factoryProtocolVersion` обязан совпасть с
  квалифицированным, а каталог `list_tools` живого процесса — с `tools_policy` (иначе 502 до `add_user_message`).
  Глобальный `~/.local/bin/droid` образ не меняет. Каталоги `state`/`runtime` внутри workspace принудительно
  приводятся к 0700 (чужой владелец — отказ старта), недоступный каталог состояния — отказ старта с сообщением.
- **Состояние чата и ошибки записи.** Перед первым `add_user_message` на диск пишется PENDING (у нового чата — сразу
  после `initialize_session`, с новым SID); сбой записи
  (ENOSPC, расхождение `rec_rev`) — 502 `proxy_error` без `add_user_message`, чат DIRTY. Сбой записи commit
  READY после хода — успех клиенту не выдаётся (502), процесс закрывается, чат DIRTY: на диске остаётся
  PENDING, после рестарта старый SID не продолжается, следующий ход — новая generation с replay. Слоты L/P/T
  освобождаются при любом исходе, в том числе при сбое Popen/запуска потоков/конструктора хода.
- **Изоляция ходов.** `turnId` реального droid присутствует только у `agent_turn_completed` и равен id
  user-сообщения хода (у ассистентских сообщений он же — `parentId`). Терминал без `turnId`, с неизвестным
  или уже завершённым `turnId` ход не завершает (пока id user-сообщения неизвестен, терминал не принимается вовсе);
  сообщение принадлежит ходу только по подтверждённой цепочке `parentId` от user-сообщения хода: события с
  неизвестным id/parent (в том числе на путях cold/restore, где списки завершённых пусты) не создают слот, не
  идут в ответ, не увеличивают счётчик истории и не продлевают watchdog тишины; дельты, пришедшие раньше своего
  `create_message`, ждут его в ограниченном буфере (входит в бюджет хода) и применяются после подтверждения. Набор завершённых turnId не вытесняется: при превышении 65536 процесс заменяется на границе
  хода (`retired` → новая generation).
- **Процессы и группы.** Дети — лидеры своих групп (`start_new_session`); закрытие всегда сигналит собственную
  группу независимо от состояния лидера. Если лидер вышел, а потомок держит pipe, сторож лидера публикует EOF и
  добивает группу (`leader_exited_pipe_held`). Эфемерные сессии (без ключа/title/images) закрываются SIGTERM без
  ожидания `close_session`. Реапер перепроверяет idle/busy/waiters/идентичность процесса уже под арендой чата.
- **Запись в stdin ребёнка** идёт срезами с дедлайном (`DROID_BRIDGE_RPC_CALL_TIMEOUT_S` охватывает и
  запись) и отменой; зависший (не читающий) ребёнок не держит interrupt и shutdown — они не ждут
  пишущий лок, дальше SIGTERM/SIGKILL.
- **Доставка отдельно от вычисления.** `_execute` только копит вывод; T и L освобождаются после
  terminal и checkpoint, SSE/JSON уходят клиенту после — медленный клиент не блокирует следующий ход.
- **Безопасность ребёнка.** Чистый Factory home (`FACTORY_HOME_OVERRIDE`; ошибка подготовки — отказ spawn),
  `disableBuiltinSkills`, `autoRejectPermissionRequests`, нативные tools отключаются по
  актуальному `list_tools` (ошибка, пустой/невалидный каталог, нет `settings_updated`,
  `disabledToolIds` или `autonomyLevel` — fail-closed, ход не начинается); model/effort/autonomy
  сверяются read-back, подмена модели — 502 `droid_error`; `disableBuiltinSkills` и
  `autoRejectPermissionRequests` сверяются, если droid их сообщает (реальный 1.248 не сообщает);
  ключ моста вырезан из env.
- **Вывод хода** удерживается до `agent_turn_completed`; `llm_retry` и
  `assistant_message_retracted` удаляют только незакоммиченное; usage — из
  `tokenUsage` терминального события по ходу (не кумулятив). Таймауты: первое событие 90 с,
  ход 1800 с (абсолютный), тишина без событий текущего хода 120 с (interrupt),
  keepalive 15 с. После неудачного хода чат инвалидируется (повтор строится из истории
  запроса, а не повтором user в старую сессию).
- **Остановка.** SIGTERM: приём прекращается, активные прерываются, дети закрываются
  параллельно в пределах 4,5 с, затем SIGKILL только собственных PGID; при SIGKILL
  родителя дети завершаются по EOF stdin; на старте добиваются только собственные
  осиротевшие дети (PID + start-signature из `workspace/state/children.json`).
  `flock` на `workspace/state/.writer.lock` не пускает второй экземпляр.

## B: охранник бюджета инструкций (`tools/b_guard.py`)

Офлайн (stdlib, читает только размеры файлов): расчёт блока agent-instructions по
формуле `279 + 32·N_секций + Σбайт` (+ метка при omitted/truncated), классы
`ALL/UG_OMITTED/TRUNCATED`.

```bash
/usr/bin/python3 tools/b_guard.py --self-test                 # границы zone-F (KB/AB/WA)
/usr/bin/python3 tools/b_guard.py --check --maxbytes 106496   # прогноз, запасы, рекомендуемый maxBytes
```

Коды выхода `--check`: 0 — оба запаса ≥ 4096 Б, 1 — запас меньше, 2 — канон теряется
в каком-либо cwd (`CANON_LOST`), дубль возвращается в KB (`DUPLICATE_RETURNED`) или блок/строка
KB > 60 000 Б (`REQ003_SIZE_EXCEEDED`, строгий режим включён в CLI). `--profiles [--profiles-dir PATH]`
только читает установленные профили DSH (`maxBytes` плагина agent-instructions; профиль с дублем плагина или
посторонним `maxBytes` считается нечитаемым) и прогоняет ту же проверку; профили утилита не правит —
применение `maxBytes=106496` остаётся шагом владельца. Источник user-global — настоящий `~/.dsh/AGENTS.md`
(симлинк на канон либо точная копия); удалён/изменён/перенацелен — `CANON_LOST`.

### Автоматический контур и гейт REQ-003 в мосте

Мост сам запускает проверку b_guard (`check_installed`: профили `DROID_DSH_BRIDGE_PROFILES_DIR`, канон
`DROID_DSH_BRIDGE_CANON`) на старте и каждые `DROID_DSH_BRIDGE_GUARD_TICK` с в фоновом потоке, без ручного CLI.
Состояния: `ok`; `unsafe` (`CANON_LOST`, `DUPLICATE_RETURNED`, `REQ003_SIZE_EXCEEDED` на профиле, нечитаемый
`maxBytes`, `PROFILES_LOST` — профили исчезли после того, как уже наблюдались); `unknown` (профилей не было с
самого старта). Смена состояния — строка `instr_guard_alert` в журнале; рестарт-петель нет. Предупреждения b_guard
(код 1: `LOW_MARGIN_*`, `LINE_ORACLE_RISK`) не отказ: состояние остаётся `ok`, а в журнал уходит один
`instr_guard_alert … warnings=<n>`.

Гейт входящих запросов (до spawn/`add_user_message`) проверяет **все** блоки agent-instructions во **всём**
тексте user-сообщений (маркер не ограничен началом сообщения):

- блок формы KB (cwd запроса = KB или его подкаталог, либо все секции — копии канона, в том числе прежнего:
  дайджесты виденных процессом канонов запоминаются) — не больше 60 000 Б, иначе 503 `launcher_unavailable`
  (в журнале `instr_gate_alert reason=REQ003_SIZE_EXCEEDED`);
- прочие блоки (WA/AB и т.п.) — не больше `maxBytes` профиля минус запас (по умолчанию 106496 − 2048), а не 60 000;
- при `unsafe` (выбранный вариант RW-001: управляемый отказ + alert, а не немой 400 по размеру) **новые** чаты
  с блоком получают 503 `launcher_unavailable` с пояснением про охранник и строкой `instr_gate_alert`;
  живые чаты (есть SID/запись) и запросы без блока продолжают обслуживаться. Новых публичных кодов ошибок нет:
  отказ по размеру и по охраннику идёт кодом из baseline-таксономии (503 `launcher_unavailable`).

## Подключение к DSH

Провайдер `droid-bridge` в `~/.dsh/profiles/desktop/cordis.patch.yml` и
`~/.dsh/profiles/web/cordis.patch.yml`: `baseURL http://127.0.0.1:9882/v1`,
`apiKeyEnv DROID_DSH_BRIDGE_KEY`. Совместимость профиля уже выставлена:
`supportsDeveloperRole: false`, `maxTokensField: max_tokens`,
`supportsReasoningEffort: true`. Список моделей в профилях — дословно из
`fleet.json` (6 моделей, только dev-уровни effort); сверка — `fleet_check.py`.

## Развёртывание (порядок обязателен)

Каждый шаг — предусловие следующего; без шагов 1–2 каждый spawn даёт 503 `launcher_unavailable`
(`/health` при этом `ok:false`, в журнале на старте `droid_receipt_invalid`).

1. `/usr/bin/python3 tools/droid_image.py [--source <путь к droid>]` — копия образа (0500) в
   `workspace/runtime/droid-image/<sha256>/`, реальные пробы (spawn / update / load), receipt schema 2.
   Exit 3 — проба провалена, receipt не записан.
2. Проверить receipt: `workspace/state/droid-binary-receipt.json` (`schema: 2`, все `probes: ok`,
   `protocol.protocol_version` = версия установленного droid).
3. Проверка плана до применения: `/usr/bin/python3 tools/b_guard.py --check --maxbytes 106496` — обязательно
   exit 0 (канон везде сохраняется, дубль не возвращается, KB-блок ≤ 60 000 Б). Установленные профили при этом
   ещё прежние (`maxBytes=262144`, блок ~111 114 Б), поэтому `--profiles` на этом шаге даёт exit 2 — это ожидаемо.
4. Владелец применяет `maxBytes=106496` в профилях DSH (утилита и мост профили не правят).
5. Проверка применённого: `/usr/bin/python3 tools/b_guard.py --profiles` — обязательно exit 0.
6. Рестарт моста (на старте в журнале не должно быть `droid_receipt_invalid` и `instr_guard_alert`;
   `guard_state state=ok`).
7. Проба: `/health` → `ok:true`, затем один ход из KB-cwd на копии моста (порт 9892, не боевой 9882) — без 503.

Откат: вернуть предыдущий коммит и перезапустить мост (`launchctl kickstart`). Прежний код принимает только
receipt `schema: 1`, поэтому перед откатом нужно перезаписать receipt прежней версией `tools/droid_image.py`
(на стенде — `DROID_DSH_BRIDGE_RECEIPT_REQUIRED=0`). Формат записей чатов в `workspace/state` (`schema: 1`)
не менялся; сомнительные записи прежний код перестраивает из истории запроса (history-fallback).

## Деплой

См. `../deploy/`: `commands.sh` (копирование в `~/.dsh/bridges/droid-bridge/`,
bootstrap launchd, перезапуск, health-check), `launchd.plist.txt`,
`cordis.patch.diff`.
