# План исследования: сбои Gemini 4 Hydrogen / agy-bridge в DeepSeek Harness

## 1. Цели исследования
1. Детерминированно локализовать и воспроизвести три типа сбоев, зафиксированных в DSH:
   - 404 `model_not_found: model is not in the catalogue`
   - Таймаут хода `timeout, 338.166s` с частичным сохранением ответа
   - 502 `agy_error: authentication failed or timed out`
2. Собрать фактологическую базу (Evidence Ledger) со ссылками на исходный код `cli-agent-bridge`, `bridges/agy-bridge`, сессии DSH и логи `com.user.dsh-agy-bridge`.
3. Сформулировать требования к архитектурным изменениям с сохранением принципа универсальности и независимости от вендоров (AGENTS.md).

## 2. Методология исследования
1. **Инспекция сессий DSH:** извлечение трассировки, параметров запроса и структуры сообщений из `~/.dsh/storages/session_projcache/sessions/session-f114d56f-0bfd-4a1d-ba4d-f7b7a61a831b.json`.
2. **Анализ конфигураций DSH и профилей:** проверка `~/.dsh/profiles/desktop/cordis.patch.yml`, сопоставление моделей и маршрутов `:9882` и `:9887`.
3. **Изоляция рантайма agy CLI:** анализ подготовки окружения `_prepare_agy_home` в `bridges/agy-bridge/server.py`, структуры токенов `~/.gemini/` vs `clean_home/.gemini/`.
4. **Анализ потока SSE и таймаутов:** инспекция `_stream_reader`, sliding window, `PRINT_TIMEOUT` и обработки обрывов соединений к апстриму Google (EOF / 503).
5. **Анализ каталога моделей и скоупов:** инспекция `core/http_post_routing.py` и `server.py` на предмет валидации `model_not_found`.
