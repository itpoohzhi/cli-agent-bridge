# Реестр фактов и доказательств (Evidence Ledger)

## [F-01] Ошибка 502: `authentication failed or timed out`
- **Проявление:** В UI DeepSeek Harness ход с моделью `Gemini 4 Hydrogen` завершается ошибкой:
  `Этот ход завершился ошибкой 502: {"message":"authentication failed or timed out","type":"agy_error","code":502}`
- **Локализация:** `bridges/agy-bridge/server.py:1586-1600` (`_prepare_agy_home`), `server.py:3460-3490`.
- **Механизм сбоя:**
  1. Для изоляции Zero-Canon мост `agy-bridge` готовит изолированную директорию `$clean_home = ~/.dsh/bridges/agy-bridge/workspace/runtime/agy-home`.
  2. В `clean_gemini` копируется только устаревший токен `jetski-standalone-oauth-token` из `~/.gemini/`.
  3. В актуальной версии `agy.real` 1.5.9 авторизационный токен хранится в `~/.gemini/antigravity-cli/antigravity-oauth-token`. В `$clean_home/.gemini/antigravity-cli/` находился лишь `antigravity-oauth-token.bak`, а свежий токен отсутствовал.
  4. При запуске CLI `agy.real` процесс не находит валидный токен и переходит в интерактивный OAuth-режим:
     `Authentication required. Please visit the URL to log in... Waiting for authentication (timeout 60s)...`
  5. По истечении 60 секунд ожидания `agy.real` завершается с JSON-событием `status: ERROR, error: authentication failed or timed out`.
  6. Мост `:9887` транслирует это событие в HTTP 502 `agy_error`.

## [F-02] Дефект парсинга флага `-print-timeout` в `agy.real`
- **Проявление:** Аварийный сброс процесса `agy.real` с RC=2 при запуске:
  `invalid value "120" for flag -print-timeout: time: missing unit in duration "120"`
- **Локализация:** `bridges/agy-bridge/server.py:5392`:
  `cmd.append(f"--print-timeout={PRINT_TIMEOUT}")`
- **Механизм сбоя:** Флаг `-print-timeout` в Go-бинарнике `agy.real` требует строку типа `time.Duration` (с суффиксом `s`, `m` и т.д.). Передача безединичного числа `120` вызывает ошибку парсинга флагов командной строки в Go runtime.

## [F-03] Превышение лимита времени хода `338.166s` (Timeout)
- **Проявление:** В UI DeepSeek Harness выводится сообщение:
  `[⚠️ Превышен лимит времени хода agy (timeout, 338.166s). Частичный ответ сохранён без аварийного сброса сессии.]`
- **Локализация:** `bridges/agy-bridge/server.py:5575-5620`, `core/midstream_resilience.py`.
- **Механизм сбоя:**
  1. В логах сервиса `com.user.dsh-agy-bridge` зафиксированы сетевые обрывы апстрим-шлюза:
     `Post "http://127.0.0.1:10830/cloudcode/v1internal:streamGenerateContent?alt=sse": EOF` и `503 UNAVAILABLE`.
  2. При возникновении сетевой паузы или зависании стрима на стороне апстрима срабатывает защитный таймер хода (338.166 с).
  3. В нарушение инварианта *Sliding Activity Window* (`AGENTS.md`), адаптер не всегда корректно продлевал дедлайн при приеме фрагментов и падал по абсолютному лимиту, либо зависал при получении молчаливого EOF от локального туннеля :10830 без быстрой реконсиляции.

## [F-04] Ошибка 404: `model is not in the catalogue`
- **Проявление:** В UI DeepSeek Harness запрос к модели завершается ошибкой:
  `Этот ход завершился ошибкой 404: {"message":"model is not in the catalogue","type":"model_not_found","code":"model_not_found"}`
- **Локализация:** `core/http_post_routing.py:128-150` (`_provider_allowed`), `server.py:210-250`.
- **Механизм сбоя:**
  1. В профиле DSH `~/.dsh/profiles/desktop/cordis.patch.yml` указана модель `gemini-4-hydrogen`, но при определенных селекторах в UI DSH или при запросах через эндпоинт конкретного провайдера (`/v1/providers/<id>/chat/completions`) имя модели может передаваться с суффиксами/префиксами (например `gemini-4-hydrogen-high`) либо проверяться против каталога поставщика, не содержащего данную модель в `PROVIDER_SCOPES`.
  2. Функция `_provider_allowed` строго проверяет соответствие имени модели разрешенному списку провайдера и при несовпадении немедленно возвращает HTTP 404 `model_not_found`.
  3. Отсутствует гибкая нормализация алиасов и fallback на опубликованный глобальный каталог хаба.

## [F-05] Сессия DSH со скриншота
- **Файл сессии:** `/Users/aazhiry1/.dsh/storages/session_projcache/sessions/session-f114d56f-0bfd-4a1d-ba4d-f7b7a61a831b.json`
- **Траектория сессии:** Содержит последовательные попытки вызова Gemini 4 Hydrogen с чередованием ошибок 404, таймаута хода 338с и 502, что полностью совпадает со скриншотом пользователя.
