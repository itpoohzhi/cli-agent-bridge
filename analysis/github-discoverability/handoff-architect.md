# Handoff для Архитектора (`handoff-architect.md`) — GitHub About & Repository Discoverability

## 1. Контекст и цель изменения

Публичный репозиторий `https://github.com/itpoohzhi/cli-agent-bridge` представляет собой универсальный OpenAI-совместимый HTTP-шлюз и оркестратор для CLI-агентов (Claude Code, OpenAI Codex, Google Gemini / Antigravity, Factory Droid, Meta Muse, OpenCode Zen). По результатам инвентаризации (`[F-01]..[F-13]`):
1. Секция **About** на GitHub пуста (`description: null`, `homepage: null`, `topics: []`), что критически снижает индексацию проекта во внутреннем поиске GitHub и внешних поисковых системах (`[F-01]`, `[F-02]`, `[F-03]`).
2. Основной файл презентации проекта `README.md` не проходит гейт качества текста `anti-neuromarkers/scripts/check.sh` (`46` символов `—`, `3` стрелки `→`, `9` относительных путей к файлам без полного URL `https://github.com/itpoohzhi/cli-agent-bridge/blob/main/...`) и содержит устаревшие сведения о составе пакета `bridges/`, `core/`, `docs/adr/` и тестового контура (`[F-08]`, `[F-09]`, `[F-10]`, `[F-11]`).
3. В репозитории отсутствует единый версионируемый источник правды (SSOT) для метаданных GitHub About (`.github/repo-metadata.json`) и инструмент их проверки и идемпотентной синхронизации (`scripts/sync_github_about.py`) (`[F-12]`).

## 2. Нормативные метаданные GitHub About (на английском языке, профиль `anti-neuromarkers`)

- **Description (217 символов, лимит GitHub — 350 символов, 0 символов `—`, 0 символов `→`, 0 нейромаркеров):**
  `OpenAI-compatible HTTP gateway and proxy for CLI coding agents: Claude Code, Codex, Gemini Antigravity, Factory Droid, Meta Muse, OpenCode Zen. SSE streaming, XML tool-call emulation, session persistence, QoS routing.`
- **Homepage:**
  `https://github.com/itpoohzhi/cli-agent-bridge#readme`
- **Topics (20 тегов, lowercase hyphenated, лимит GitHub — 20 тегов по <=50 символов):**
  `openai-compatible`, `openai-api`, `api-gateway`, `http-proxy`, `llm-gateway`, `cli-coding-agents`, `ai-coding-agent`, `claude-code`, `codex`, `gemini`, `antigravity`, `factory-droid`, `meta-muse`, `opencode`, `sse-streaming`, `server-sent-events`, `tool-calling`, `session-persistence`, `qos-routing`, `python`

## 3. Функциональные и нефункциональные требования (`REQ-001..REQ-006`)

- **`REQ-001` (GitHub About description and homepage):**
  Метаданные репозитория `itpoohzhi/cli-agent-bridge` содержат утверждённое английское описание `description` (не более 240 символов, ключевые слова в начале строки: `OpenAI-compatible HTTP gateway and proxy for CLI coding agents`, перечисление `Claude Code, Codex, Gemini Antigravity, Factory Droid, Meta Muse, OpenCode Zen`, возможности `SSE streaming, XML tool-call emulation, session persistence, QoS routing`) и `homepage` (`https://github.com/itpoohzhi/cli-agent-bridge#readme`). Текст не содержит символов `—` (`U+2014`), `→` (`U+2192`), двойных дефисов `--` и слов из стоп-списка `anti-neuromarkers` (`seamlessly`, `empower`, `unlock`, `delve`, `tapestry`, `robust`, `comprehensive`, `cutting-edge`). Основание: `[F-01]`, `[F-02]`.
- **`REQ-002` (GitHub topics for search discoverability):**
  Метаданные репозитория определяют ровно 20 поисковых топиков (`about_topics`). Каждый топик записан в нижнем регистре через дефис (`^[a-z0-9][a-z0-9-]{0,49}$`), без дубликатов. Основание: `[F-03]`.
- **`REQ-003` (Single source of truth and idempotent sync script):**
  Метаданные секции About хранятся в версионируемом файле `.github/repo-metadata.json` (`description`, `homepage`, `topics`). Скрипт `scripts/sync_github_about.py` читает `.github/repo-metadata.json`, валидирует схему, длину и отсутствие запрещённых символов (`anti-neuromarkers`), поддерживает режимы `--validate` (локальная валидация без сети), `--check` (сравнение локального файла с живым GitHub API `GET /repos/{owner}/{repo}`), `--dry-run` и `--apply` (идемпотентное обновление через GitHub REST API `PATCH /repos/{owner}/{repo}` и `PUT /repos/{owner}/{repo}/topics` при наличии токена). Все сетевые тайм-ауты и URL конфигурируются через переменные окружения и CLI-флаги с безопасными значениями по умолчанию. Основание: `[F-12]`, `[F-13]`.
- **`REQ-004` (README anti-neuromarkers compliance):**
  Файл `README.md` на английском языке очищен от всех 46 длинных тире `—` (`U+2014`), всех 3 стрелок `→` (`U+2192`) и нейромаркерных клише. Скрипт `bash ~/Мой\ диск/skils/anti-neuromarkers/scripts/check.sh README.md` завершается с кодом `0` (`PASS`). Основание: `[F-05]`, `[F-11]`.
- **`REQ-005` (README factual accuracy, SEO header, and canonical GitHub URLs):**
  В `README.md` добавлены бейджи (MIT License, Python 3.10+, OpenAI API Compatible, QA Gates L1/L2/L3), актуализирована таблица архитектуры и компонентов (`core/stream_fsm`, `core/model_penalty.py`, `core/context_resilience.py`, `core/turn_session_manager.py`, `core/watchdog.py`, `core/qos.py`, `adapters/passthrough_adapter.py`), исправлено утверждение о внешних мостах (указаны встроенные мосты в `bridges/agy-bridge`, `bridges/claude-p-bridge`, `bridges/muse-bridge`, `bridges/opencode-zen-bridge`), обновлена секция тестирования (`77` тестовых модулей `pytest tests/ -v` с учётом нового `tests/test_github_about_sync.py` поверх `76` базовых модулей, гейты `scripts/qa_product_gate.py` и `scripts/smoke_models.py`, архив `docs/adr/` 0001..0023), а все 9 относительных упоминаний файлов репозитория в тексте оформлены полными ссылками `https://github.com/itpoohzhi/cli-agent-bridge/blob/main/<path>`. Основание: `[F-06]`, `[F-07]`, `[F-08]`, `[F-09]`, `[F-10]`, `[F-11]`.
- **`REQ-006` (Automated unit test coverage for metadata and sync utility):**
  Модульные тесты в `tests/test_github_about_sync.py` проверяют валидацию `.github/repo-metadata.json`, соответствие `README.md` и `.github/repo-metadata.json` ограничениям `REQ-001..REQ-005` (0 символов `—`, 0 символов `→`, 20 валидных топиков, длина `description <= 240`, отсутствие устаревших утверждений) и логику `scripts/sync_github_about.py` (`--validate`, `--check`, `--dry-run`, `--apply` с моком HTTP-транспорта). Основание: `[F-10]`, `[F-12]`.

## 4. Ограничения и инварианты проекта (`AGENTS.md`)

1. Полная конфигурируемость: в `scripts/sync_github_about.py` запрещён хардкод неконфигурируемых таймаутов и эндпоинтов; используются переменные окружения (`GITHUB_API_URL`, `GITHUB_REPO`, `GITHUB_HTTP_TIMEOUT_S`, `GITHUB_TOKEN` / `GH_TOKEN`) и аргументы CLI.
2. Нулевое влияние на рантайм HTTP-шлюза (`server.py`, `core/`, `adapters/` не модифицируются).
3. Соблюдение модульных границ `M-MOD-I1..I5`: затрагиваются ровно 2 продуктовых файла (`.github/repo-metadata.json` и `scripts/sync_github_about.py`), документация `README.md` и тестовый модуль `tests/test_github_about_sync.py`.

## 5. Анкета эксплуатационной среды `HL-ENV/v1` (46 полей)

Для задачи оформления репозитория, документации `README.md` и CLI-утилиты синхронизации метаданных GitHub About зафиксированы фактические параметры среды и применимые значения `N/A (static documentation & metadata CLI)`.

| Код | Параметр | Значение |
|---|---|---|
| 1.1 | Регионы / ДЦ / облако / on-prem | GitHub Cloud (github.com) + локальная среда разработки macOS |
| 1.2 | Топология развёртывания | Локальный CLI-скрипт и публичный Git-репозиторий itpoohzhi/cli-agent-bridge |
| 1.3 | Сетевые зоны и межсетевые экраны | Исходящий HTTPS (TCP 443) к api.github.com и SSH (TCP 22) к github.com |
| 1.4 | Балансировщики и ингресс | N/A (static documentation & metadata CLI) |
| 1.5 | Сервис-меш / mTLS | Стандартный TLS 1.3 до api.github.com |
| 1.6 | Квоты CPU / RAM / Disk | CPU <= 1 core, RAM <= 64 MB, Disk <= 1 MB для выполнения скрипта синхронизации |
| 1.7 | Хранилища и файловые системы | Локальная ФС POSIX (Git-репозиторий, файл .github/repo-metadata.json) |
| 1.8 | Внешние зависимости и API | GitHub REST API v3 (https://api.github.com/repos/itpoohzhi/cli-agent-bridge) |
| 2.1 | DAU / MAU / одновременные сессии | 1 оператор / CI-раннер при обновлении метаданных репозитория |
| 2.2 | Средний и пиковый RPS (read / write) | <= 1 RPS (разовый вызов GET и PATCH/PUT при синхронизации About) |
| 2.3 | Профиль трафика и сезонность | Событийный запуск при изменении .github/repo-metadata.json |
| 2.4 | Размер запроса и ответа (p50 / p99) | Запрос <= 2 KB JSON, ответ GitHub API <= 16 KB JSON |
| 2.5 | Доля тяжёлых запросов / батчей | 0% (только легковесные метаданные description, homepage, topics) |
| 2.6 | Рост нагрузки (горизонт 6-12 мес) | Постоянный объём (1 репозиторий, <= 20 топиков) |
| 2.7 | Ограничения rate-limit апстримов | GitHub API: 60 req/hr без токена (GET), 5000 req/hr с токеном (GET/PATCH/PUT) |
| 2.8 | Допустимая деградация при пиках | Отказ по коду возврата != 0 в режиме --check / --apply без повреждения файлов |
| 3.1 | Целевой SLA / SLO доступности | 99.9% для локальной валидации --validate (не зависит от сети) |
| 3.2 | Латентность p50 / p95 / p99 | Локальный --validate <= 50 ms; сетевой --check / --apply <= 5000 ms (p99) |
| 3.3 | RPO (допустимая потеря данных) | 0 байт (источник правды .github/repo-metadata.json хранится в Git) |
| 3.4 | RTO (время восстановления) | <= 1 минута (повторный прогон scripts/sync_github_about.py --apply) |
| 3.5 | Окна регламентных работ | Без простоев (обновление метаданных атомарно на стороне GitHub API) |
| 3.6 | Политика retry / timeout / circuit-breaker | Настраиваемый HTTP timeout (по умолчанию 15 с через GITHUB_HTTP_TIMEOUT_S), fail-fast при 401/403 |
| 3.7 | Идемпотентность операций | Полная идемпотентность: повторный --apply при совпадении данных не выполняет лишних мутаций |
| 4.1 | Объём БД и индексных структур | 1 JSON-файл (.github/repo-metadata.json, < 2 KB) |
| 4.2 | Прирост данных в сутки / год | < 10 KB в год (версионирование в Git) |
| 4.3 | Сроки хранения (retention) и архивация | Бессрочно в истории Git-коммитов ветки main |
| 4.4 | Требования к консистентности | Строгое совпадение .github/repo-metadata.json и ответа GitHub REST API |
| 4.5 | Миграции схемы и обратная совместимость | Обратная совместимость JSON-схемы (ключи description, homepage, topics) |
| 4.6 | Бэкапы и проверка восстановления | Стандартный распределённый клон Git (origin/main) |
| 4.7 | Кэширование и инвалидация | Без локального кэша; прямое чтение из файла и GitHub API |
| 4.8 | Полнотекстовый поиск и индексация | Индексация поисковым движком GitHub по полям description, topics и README.md |
| 5.1 | Классификация данных и PII | Публичные метаданные открытого MIT-репозитория (PII и секреты отсутствуют) |
| 5.2 | Аутентификация и авторизация | GitHub Personal Access Token через переменную окружения GITHUB_TOKEN / GH_TOKEN для записи |
| 5.3 | Управление секретами и ротация | Токен передаётся исключительно через окружение, в код и логи не записывается |
| 5.4 | Аудит-лог и неизменяемость | История коммитов Git и журнал событий репозитория GitHub |
| 5.5 | Шифрование в транзите и на диске | HTTPS (TLS) при вызовах api.github.com |
| 5.6 | Комплаенс и регуляторные требования | Лицензия MIT, соблюдение правил GitHub Acceptable Use и anti-neuromarkers |
| 5.7 | Защита от инъекций и валидация входов | Строгая JSON-схема и регулярные выражения для topics, запрет управляющих символов |
| 6.1 | Пайплайн сборки и деплоя (CI/CD) | Локальный гейт pytest tests/ -v, check.sh и qa_product_gate.py перед git push |
| 6.2 | Стратегия выката (canary / blue-green) | Прямой мерж в main после прохождения Совета Тимлидов (teamlead-gate) |
| 6.3 | План отката (rollback) | git revert коммита и повторный запуск scripts/sync_github_about.py --apply |
| 6.4 | Метрики и бизнес-индикаторы | Код возврата 0 для check.sh и sync_github_about.py --validate, 20 топиков в манифесте |
| 6.5 | Логирование и трассировка | Структурированный вывод статуса проверок в stdout/stderr без утечки токенов |
| 6.6 | Алертинг и дежурные (on-call) | N/A (static documentation & metadata CLI) |
| 6.7 | Тестовые контуры и нагрузочное тестирование | Изолированный клон $WORK, модульные тесты pytest tests/test_github_about_sync.py |
| 6.8 | Документация и runbooks | Секция в README.md и встроенная справка scripts/sync_github_about.py --help |

[ПРОВЕРЕНО ЛУПОМ: тройка R1→D1 OK (исправлено 6, отсеяно галлюцинаций 0)]

