# ВЕРДИКТ КОДОВОЙ ПАНЕЛИ ТЕХЛИДОВ (Code Review Panel) — Цикл 1, Раунд 1

- **Дата:** 2026-10-13 14:12 MSK
- **Предмет ревью:** Дифф реализации real-time streaming (`diff.patch`, SHA-256: `df43497ddc2758287e926ad7984b4a3f63cd46d896cb89213fd1285615f50832`)
- **Сид раунда:** `df43497d#dsh-realtime-streaming#c1#R1` (`seed_hex: 2efbe9be`)
- **Коллегия:**
  - Seat 1 (Якорь, OpenAI): `gpt-6.1-sol` — Реалист (`codex exec`) → **NEEDS WORK**
  - Seat 2 (DeepSeek): `deepseek-v4.1-flash` — Скептик (`droid exec -m deepseek-v4.1-flash -r max`) → **NEEDS WORK**
  - Seat 3 (Google): `gemini-3.8-flash-high` — Визионер (`droid exec -m gemini-3.8-flash -r high`) → **ACCEPT**

---

## Итоговый вердикт коллегии
**NEEDS WORK** (большинство 2/3 разных семейств: OpenAI + DeepSeek).

---

## Консолидированные блокирующие замечания (Blocking Findings)

1. **F-201 (Утечка таймаута в keepalive и нарушение RW-009):**  
   В `server.py` ветка `keepalive` в `Handler._execute` не проверяет флаг `client_write_dead` и отправляет кадры с таймаутом соединения (300 с). Если буфер сокета заполнен медленным клиентом, поток вычислений зависает, удерживая блокировки L и T.  
   *Действие:* Проверять `client_write_dead` перед отправкой keepalive и применять к нему тот же `LIVE_WRITE_TIMEOUT_S` (3 с).

2. **F-202 (Wire-формат чанка ошибки fail-close по AD-001):**  
   При сбое после отправки живого префикса мост отдаёт плоский JSON `{"error": ...}` вместо OpenAI `chat.completion.chunk` с объектом ошибки (`type: "stream_error", code: "live_prefix_invalidated", param: null`).  
   *Действие:* Обернуть чанк ошибки в формат `chat.completion.chunk` с сохранением `id`, `created`, `model` и `finish_reason: null`.

3. **F-203 (Тихая потеря данных у медленного клиента):**  
   При обрыве или таймауте живой записи клиенту дальнейшие куски текста отсекаются, но в конце хода всё равно отправляется успешный `finish_reason: "stop"` и `[DONE]`.  
   *Действие:* При сбое живой доставки не отправлять ложный `stop` и `usage`; завершать поток fail-close ошибкой или закрывать соединение.

4. **F-204 (Ограничение промежуточной очереди Run.q):**  
   Очередь `Run.q` осталась неограниченной (`queue.Queue()`), что нарушает рекомендацию F-103 Архитектурной панели.  
   *Действие:* Задать `maxsize=1024` и обработать overflow.

5. **F-205 (Identity и проверка префикса при complete):**  
   При получении финального сообщения `create_message` / `complete` срез `text[sent:]` не проверяет, что новый текст действительно начинается с уже отправленного префикса.  
   *Действие:* Проверять `text.startswith(sent_prefix)`; при несовпадении вызывать `live_invalidated`.

6. **F-206 (Бюджетирование в байтах UTF-8 и изоляция Droid):**  
   Резервировать бюджет доставки в реальных байтах UTF-8 (`len(piece.encode("utf-8"))`), а изменение `finish_reason: null` в usage ограничить стримингом Droid.

---

## Следующие шаги
1. Запуск `panel-rework-summarizer` (`gpt-6.1-sol`) для компиляции машиночитаемого `panel-rework-brief-code-c1.json`.
2. Передача брифа сабагенту Coder (`claude-sonnet-5-5`) для точечного устранения F-201..F-206.
3. Повторный прогон unit-тестов.
4. Проведение Раунда 2 Кодовой панели техлидов (c1r2).
