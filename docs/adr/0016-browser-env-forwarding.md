# ADR-0016: Безопасный проброс сессионного runtime-окружения и универсальный CDP-хелпер для CLI-агентов (Ревизия A4)

## Статус
ПРИНЯТО (APPROVED, Ревизия A4 с учетом консенсуса Совета Тимлидов)

## Контекст и проблематика
При выполнении задач анализа дашбордов и мониторинга (скиллы `grafana-dashboard-build` и `grafana-dashboard-qa`) клиентские сессии DeepSeek Harness (DSH) сталкиваются с критическим ограничением функциональности:
1. В среде исполнения DSH отсутствуют плагины прямого управления браузером (доступны только `bash`, `fs`, `subagent`, `todo`, `tool-web` без DOM-управления).
2. Подпроцессы `bash` порождаются в изоляции и не наследуют переменные окружения `$AGENT_BROWSER_CDP` и `$GRAFANA_TOKEN`, необходимые для взаимодействия с авторизованной сессией Grafana или DevTools Chrome/Antigravity.
3. В шлюзе `cli-agent-bridge` окружение дочерних процессов формируется исключительно статически из `os.environ` процесса моста (`_launch_env`), а канал динамического проброса `extra_body.env` из входящего запроса `POST /v1/chat/completions` полностью игнорируется.
4. В passthrough-маршрутах (`codex`, `passthrough_adapter.py`) запрос пересылается в upstream без обогащения сессионным контекстом.

Попытка модификации конфигураций DSH (`~/.dsh/fleet.json`, патчи бинарников `app.asar`) категорически запрещена главным архитектурным принципом репозитория (`AGENTS.md`: «Категорически запрещено модифицировать, патчить или внедрять оверлеи во внешние вендорские приложения и среды... реализация только на нашем универсальном слое»).

## Архитектурное решение (Ревизия A4)

Решение реализуется строго на универсальном слое `cli-agent-bridge` и включает следующие спецификации:

### 1. Канал динамического сессионного окружения в фасаде моста (`server.py`)
- Добавляется извлечение и валидация блока `extra_body.env` из входящих JSON-запросов к `/v1/chat/completions`.
- **Строгий денилист безопасности (`DENIED_FORWARD_ENV`) для платформ macOS и Linux:**
  - Точные запрещенные имена:
    `BRIDGE_KEY`, `DROID_DSH_BRIDGE_KEY`, `*_BRIDGE_KEY`, `DROID_BIN`, `FACTORY_HOME_OVERRIDE`, `DROID_AUTO`, `PATH`, `HOME`, `SHELL`, `USER`, `IFS`, `ENV`, `BASH_ENV`, `SSL_CERT_FILE`, `SSL_CERT_DIR`, `NODE_EXTRA_CA_CERTS`, `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`, `NO_PROXY`.
  - Запрещенные префиксы (wildcards):
    `DYLD_*`, `LD_*`, `PYTHON*`, `NODE_*`, `BASH_FUNC_*`.
  - **Валидация формата ключей и значений:**
    - Ключ обязан соответствовать регулярному выражению `^[A-Za-z_][A-Za-z0-9_]{0,127}$` (без знаков `=`, пробелов или NUL-байтов).
    - Значение обязано быть строкой без NUL-байтов, длиной не более 32 768 символов.
- **Строгая валидация loopback для ВСЕХ CDP-адресов:**
  - Проверка применяется как к автоматически обнаруженным адресам, так и к переданным через `extra_body.env={"AGENT_BROWSER_CDP": "..."}`.
  - Разбор через `urllib.parse.urlparse`:
    - Схема: строго `ws`, `wss` или `http`.
    - Хост: строго `parsed.hostname in {"127.0.0.1", "localhost", "::1"}` (запрещены составные имена вроде `127.0.0.1.attacker.invalid`).
    - Порт: целое число в диапазоне `1024..65535`.
  - При обнаружении любого внешнего адреса переменная отбрасывается / возвращается HTTP 400.
- **Автоматический discovery DevTools CDP:**
  - Если `AGENT_BROWSER_CDP` не передан в запросе, мост считывает активный порт из `BRIDGE_CDP_DISCOVERY_PATH` (по умолчанию `~/Library/Application Support/Antigravity/DevToolsActivePort` или `~/.config/agy-launch/devtools_port`).
  - Проверяется существование и тип файла (регулярный файл), валидируется порт и loopback WebSocket URL `ws://127.0.0.1:<port>/devtools/browser/<id>`.
- **Инвалидация сессий и защита от перекрестных утечек (`chat.proc`):**
  - При изменении набора переданных переменных окружения или их значений для активного `chat_id` мост безопасно завершает дочерний процесс (`chat.proc.kill()`, `chat.proc = None`) и перезапускает его с новым окружением, исключая смешивание секретов между задачами.
- **Защита секретов в логах:**
  - Значения переменных, содержащих в имени `TOKEN`, `KEY`, `SECRET`, `AUTH`, `PASS`, маскируются при логировании (`***`).

### 2. Универсальная CLI-утилита `agent-browser` (`tools/agent_browser.py`)
- Легковесный CLI-инструмент (симлинк `~/.local/bin/agent-browser`), позволяющий штатному `tool-bash` исполнять команды управления браузером через WebSocket CDP:
  - `agent-browser --cdp "$AGENT_BROWSER_CDP" eval "<expression>"`
  - `agent-browser --cdp "$AGENT_BROWSER_CDP" title`
  - `agent-browser --cdp "$AGENT_BROWSER_CDP" navigate "<url>"`
  - `agent-browser --cdp "$AGENT_BROWSER_CDP" screenshot "<path>"`
- **Автономный fallback:** если флаг `--cdp` не передан и переменная `$AGENT_BROWSER_CDP` отсутствует в окружении, утилита сама выполняет безопасный discovery локального DevToolsActivePort на loopback.
- **Доставка в PATH:** мост при старте дочерних процессов добавляет абсолютный путь к `tools/` в начало `PATH`, а также создает симлинк `~/.local/bin/agent-browser`.
- **Зависимости:** реализация опирается на стандартную библиотеку Python (`sys`, `json`, `urllib.request`, `urllib.parse`, `socket`, `base64`, `hashlib`, `os`, `struct`, `argparse`) без тяжелых внешних библиотек (playwright/puppeteer).

### 3. Полная конфигурируемость и GigaRC Feature Flag (Правило 4 AGENTS.md)
- Все эксплуатационные параметры вынесены в настройки:
  - `BRIDGE_BROWSER_FORWARDING_ENABLED`: флаг активации функционала (по умолчанию `false` для 100% обратной совместимости, проверяется динамически);
  - `BRIDGE_CDP_DISCOVERY_PATH`: настраиваемый путь к DevToolsActivePort;
  - `BRIDGE_CDP_TIMEOUT_S`: таймаут ожидания ответа CDP (дефолт `5.0` секунд);
  - `BRIDGE_BROWSER_FORWARD_DENYLIST`: список дополнительных запрещенных ключей.
- При `BRIDGE_BROWSER_FORWARDING_ENABLED=false` поведение моста побайтово идентично (Zero Regression).

### 4. Hot-Path & HL-ENV Statement
- `Hot-Path & HL-ENV: N/A (cold-path only)`.
- Изменения затрагивают исключительно фасад диспетчеризации HTTP-запросов и запуск дочерних процессов; внутренний горячий цикл передачи чанков SSE (`_stream_response`, генераторы) не модифицируется, zero memory allocation на горячем пути.

## Поверхность верификации (DoD)
- Все тесты запускаются через канонический `pytest tests/ -v`.
- Включает 5 тестов из оракула:
  1. `test_o1_request_env_reaches_child` — проброс переменных в дочерний процесс;
  2. `test_o2_secret_values_never_in_prompt_or_response_or_stderr` — маскирование секретов в логах;
  3. `test_o3_denylist_not_overridable_by_request` — защита от подмены системных переменных (полный денилист macOS/Linux);
  4. `test_o4_no_cross_chat_leak` — изоляция между чатами A и B при повторном использовании сессий;
  5. `test_o5_default_off_flag` — проверка отключенного состояния флага (дефолт `false`).
- Тесты CLI-утилиты `agent-browser` (eval, title, navigate, help, loopback validation).

## Реализация (Rev A4): решения, уточняющие спецификацию
- **Флаг GigaRC** `BRIDGE_BROWSER_FORWARDING_ENABLED` читается динамически: JSON-снимок `BRIDGE_DYNAMIC_CONFIG_PATH` (по умолчанию `~/.config/cli-agent-bridge/dynamic_config.json`) с кэшем по `(dev, inode, size, mtime_ns)` — O(1) на вызов, рестарт моста не нужен. Нет файла/ключа — env-фолбэк (дефолт `false`); повреждённый файл — fail-closed (`false`).
- **Расширенный денилист** (сверх списка выше): префиксы `DROID_*`, `FACTORY_*`, `GIT_*`, `PERL*`, `RUBY*`, имена `PWD`, `TMPDIR`, `ZDOTDIR`, `CDPATH`, `PS4`, `PROMPT_COMMAND`, любой ключ моста (`is_bridge_secret_name`) и `BRIDGE_BROWSER_FORWARD_DENYLIST`. Запрещённые/невалидные ключи отбрасываются молча (в лог — только имена); не-loopback `AGENT_BROWSER_CDP` и не-объектный/чрезмерный (>64 ключей) `env` — HTTP 400.
- **Жизненный цикл процесса.** Окружение процесса == окружение запроса, иначе процесс завершается (`SIGTERM` без ожидания → `SIGKILL`), `chat.proc = None`, `chat.env` перезаписывается, ход идёт по пути `restore` того же SID. Это относится к смене env, к запросу без env у чата с env и к запросу с env у чата без env. Kill-switch (`_enforce_forward_kill_switch`) выполняется на каждом POST и в тике реапера и убивает все процессы с проброшенным env (включая эфемерные).
- **Zero disk leak.** `Chat.env` — только память, в `_write_record` не попадает; idle-реап, вытеснение и сбой хода стирают его. `TurnContext.fwd_env` скрыт из `repr`. Значения секретных имён и `ws://`-адреса вычищаются из stderr ребёнка и логов моста.
- **Discovery.** `discover_local_cdp_url` (единая реализация в `tools/agent_browser.py`, мост импортирует её) подставляет loopback CDP только в запросы, где клиент сам прислал непустой `env` без `AGENT_BROWSER_CDP`; запросы без env мост не обогащает (иначе правило «нет env — чистый процесс» не соблюдалось бы).
- **PATH.** `tools/` ставится в начало `PATH` только при включённом флаге (при `false` окружение побайтово прежнее). Симлинк `~/.local/bin/agent-browser` создаётся оператором: `ln -sfn <repo>/tools/agent_browser.py ~/.local/bin/agent-browser`.
- **Тесты.** `tests/test_dsh_env_forwarding.py` (O1–O11, жизненный цикл, kill-switch, loopback/discovery, флаг) и `tests/test_agent_browser.py` (CLI против фейкового CDP-сервера).
