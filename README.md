# droid-bridge (DSH)

OpenAI-совместимый мост DeepSeek Harness → Factory Droid CLI (`droid exec`) с
эмуляцией OpenAI function calling (tool_emulation). Порт **9882**.

- Один запрос `/v1/chat/completions` = один headless-ход
  `droid exec -o stream-json -m <model> --cwd <workspace> --tag droid-dsh-bridge -f <prompt_file> -r <effort>`
  через канонический лончер `~/.config/factory-launch/droid-cli.sh` (egress-пиннинг;
  голый droid-бинарь не используется — бьёт в WAF Factory; fallback на него удалён).
- Модели и уровни effort — из каталога `fleet.json` (6 моделей Droid-флота,
  только dev-контекст): sonnet-5-5, gemini-3.8-flash, grok-4.7,
  deepseek-v4.1-flash, gpt-6.1-sol, glm-5.3.
- `model`/`reasoning_effort` валидируются строго **до** SSE: не из каталога —
  HTTP 400 `model_not_allowed` / `unsupported_reasoning_effort`; никаких
  clamp, алиасов и silent fallback. `-r` передаётся всегда (из запроса либо
  `default_effort` модели). Флаги `--auto` / `--skip-permissions-unsafe` не
  передаются никогда.
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
- `workspace/` — cwd для droid-процессов и промпт-файлы `prompt-<hex>.txt`
  (удаляются после хода); для image-запросов — per-run каталоги `img-<uuid32>`
  (0700, файлы 0600), удаляются при любом исходе.

## Env

| Переменная | Default | Назначение |
|---|---|---|
| `DROID_DSH_BRIDGE_HOST` | `127.0.0.1` | адрес |
| `DROID_DSH_BRIDGE_PORT` | `9882` | порт |
| `DROID_DSH_BRIDGE_KEY` | — (обязателен) | ключ авторизации (Bearer / x-api-key) |
| `FACTORY_API_KEY` | — | headless-вход `droid exec` без интерактивного логина; `start.sh` читает из `~/.zshenv` |
| `DROID_DSH_BRIDGE_MODEL` | `default_model` каталога | модель по умолчанию (обязана быть в каталоге) |
| `DROID_DSH_BRIDGE_MAX_CONCURRENT` | `4` | параллельных droid-процессов |
| `DROID_DSH_BRIDGE_QUEUE_TIMEOUT` | `900` | ожидание слота, с |
| `DROID_DSH_BRIDGE_KEEPALIVE` | `15` | keepalive SSE, с |
| `DROID_DSH_BRIDGE_FLEET` | `<каталог моста>/fleet.json` | путь к каталогу флота |
| `DROID_DSH_BRIDGE_IMAGE_PROBE` | — | `1` — включить `probe`-модели изображений (**только для копии моста**, не для боевого запуска) |
| `DROID_LAUNCHER` | `~/.config/factory-launch/droid-cli.sh` | канонический лончер droid |

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
- `GET /v1/models` и `/models` (с авторизацией) — `{"object":"list","data":[…6…]}`,
  первым `default_model`; запись `{"id","object":"model","owned_by":"factory-droid",
  "created":0,"context_length":…}`.
- `POST /v1/chat/completions` и `/chat/completions` — см. выше; `stream:true`
  отдаёт SSE (`delta.content`, `delta.reasoning_content`, `delta.tool_calls`,
  `finish_reason`, usage-чанк при ненулевых токенах, `[DONE]`).

## Журнал

`logs/` (JSON-строки stdout launchd). Формат ключевых строк:
`exec model=<id> effort=<lvl> effort_source=<request|default> prompt_bytes=… [images=…] <tag>`,
`done model=<id> rc=<n> state=<s> … <tag>`,
`reject reason=<тип> model=<id каталога|unknown> model_len=<n> client=<ip:port>`.
Тела запросов, ключи, base64 и пути хранилища в журнал не попадают; в строке
`reject` — только каталожный id (или `unknown`) и длина клиентской строки.

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

84 теста: каталог и его классы I/II/III, строгая валидация model/effort, argv
(один `-m`/`-r`, без `--auto`), framing/413/admission, tool emulation, ретраи,
sweep, image-путь (таксономия C-10, лимиты, права 0700/0600, очистка,
fail-closed proof), журнал. Тесты не ходят в сеть и к droid: `Run` подменяется
фейком, а argv/раскладка проверяются на локальной заглушке лончера; файлы — только
во временных каталогах.

## Подключение к DSH

Провайдер `droid-bridge` в `~/.dsh/profiles/desktop/cordis.patch.yml` и
`~/.dsh/profiles/web/cordis.patch.yml`: `baseURL http://127.0.0.1:9882/v1`,
`apiKeyEnv DROID_DSH_BRIDGE_KEY`. Совместимость профиля уже выставлена:
`supportsDeveloperRole: false`, `maxTokensField: max_tokens`,
`supportsReasoningEffort: true`. Список моделей в профилях — дословно из
`fleet.json` (6 моделей, только dev-уровни effort); сверка — `fleet_check.py`.

## Деплой

См. `../deploy/`: `commands.sh` (копирование в `~/.dsh/bridges/droid-bridge/`,
bootstrap launchd, перезапуск, health-check), `launchd.plist.txt`,
`cordis.patch.diff`.
