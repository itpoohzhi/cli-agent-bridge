# Архитектурное решение (Architecture Decision Record - ADR)

## Статус: APPROVED (sha256: 1fd39d4bb1e07d6e7d39cc524900910f2e5c52f77deb29f05190311dccfa0f73)

## Контекст и проблематика
При обращении к модели `Gemini 4 Hydrogen` через шлюз `cli-agent-bridge` (:9882) в интерфейсе DeepSeek Harness возникают 3 дефекта:
1. HTTP 502 `{"message":"authentication failed or timed out","type":"agy_error","code":502}`.
2. Превышение лимита времени хода `338.166s` с частичным сохранением ответа.
3. HTTP 404 `{"message":"model is not in the catalogue","type":"model_not_found","code":"model_not_found"}`.

## Архитектурные решения

### 1. AD-001: Синхронизация OAuth токена в `bridges/agy-bridge/server.py` (`_prepare_agy_home`)
- **Проблема:** В изолированном окружении `$clean_home` копировался только старый токен `jetski-standalone-oauth-token`. Актуальный токен `~/.gemini/antigravity-cli/antigravity-oauth-token` (и метаданные `antigravity-account.json`) не синхронизировался, из-за чего CLI `agy.real` 1.5.9 уходил в ожидание интерактивной веб-авторизации (60с) и падал по таймауту.
- **Решение:** В функции `_prepare_agy_home` добавить проверку и копирование файлов `antigravity-oauth-token` и `antigravity-account.json` из `~/.gemini/antigravity-cli/` в `$clean_home/.gemini/antigravity-cli/` с валидацией mtime и размера файлов.

### 2. AD-002: Валидация формата аргумента `--print-timeout` в `bridges/agy-bridge/server.py`
- **Проблема:** Передача значения `PRINT_TIMEOUT` без суффикса единицы времени (например `--print-timeout=120`) вызывала аварийный сбой Go-парсера duration в `agy.real` с ошибкой `missing unit in duration` (RC=2).
- **Решение:** Обеспечить, чтобы любое непустое значение `PRINT_TIMEOUT` форматировалось с суффиксом `s` (если суффикс `s`, `m`, `h` отсутствует), например `f"{PRINT_TIMEOUT}s"`, либо передавать `0s` при отключении.

### 3. AD-003: Реализация Sliding Activity Window и устойчивость к EOF/503
- **Проблема:** Статический дедлайн хода (338.166с) прерывал длинные активные сессии генерации или зависал при внезапном сетевом EOF/503 от апстрима.
- **Решение:** При чтении SSE потока из CLI адаптер обновляет `deadline = now + idle_timeout_s` при поступлении каждого полезного чанка (`content`, `reasoning_content`, `tool_calls`). При обнаружении аварийного завершения процесса или ошибки апстрима выполняется быстрая корректная финализация и сохранение накопленного контекста без искусственного ожидания настенного таймера.

### 4. AD-004: Устойчивость маршрутизации моделей к суффиксам режимов в `core/http_post_routing.py`
- **Проблема:** Запросы от DSH с суффиксами усилий (`gemini-4-hydrogen-high`) или через эндпоинты провайдеров отклонялись функцией `_provider_allowed` с ошибкой HTTP 404 `model is not in the catalogue`.
- **Решение:** В `core/http_post_routing.py` нормализовать имя модели, отсекая суффиксы режимов/усилий (`-high`, `-low`, `-none`) при поиске в каталоге провайдера и проверяя глобальные опубликованные алиасы моделей.

## Соответствие AGENTS.md
- **Универсальность:** Никаких правок вендорского кода DSH или бинарников `agy.real`. Все доработки выполняются исключительно на уровне моста и ядра `cli-agent-bridge`.
- **Конфигурируемость:** Параметры таймаутов настраиваются через переменные окружения (`AGY_BRIDGE_PRINT_TIMEOUT`, `AGY_BRIDGE_IDLE_TIMEOUT_S`) с безопасными значениями по умолчанию.
