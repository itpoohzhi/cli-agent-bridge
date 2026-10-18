# Бриф Архитектора: Доработка архитектурного пакета по замечаниям Совета (раунд a2)

Ты — сабагент роли Architect (`gemini-4-argon-high`).
Твоя задача — доработать архитектурный пакет задачи `dsh-bridge-resilience-20261017` в соответствии с согласованным брифом доработок от Архитектурного Совета:
`.ai-team/runs/dsh-bridge-resilience-20261017/handoff/panel-rework-brief-arch-a1.json`

## Входные файлы:
1. Согласованный бриф доработок: `.ai-team/runs/dsh-bridge-resilience-20261017/handoff/panel-rework-brief-arch-a1.json`
2. Леджер замечаний: `.ai-team/runs/dsh-bridge-resilience-20261017/arch-panel/cycle-1/a1/findings-ledger.md`
3. Спецификация: `.ai-team/runs/dsh-bridge-resilience-20261017/architecture/arch-spec.md`
4. ADR 0005: `docs/adr/0005-resilient-hub-lifecycle-and-detached-turns.md`
5. Архитектурный пакет: `.ai-team/runs/dsh-bridge-resilience-20261017/architecture/architecture-packet.json`

## Обязательные доработки (все 10 blocking-пунктов RW-001..RW-010):
1. **RW-001 (F-001): Явная отмена хода.**
   - Специфицировать в `arch-spec.md` и ADR эндпоинт `POST /v1/turns/<turn_id>/cancel` (или `DELETE /v1/turns/<turn_id>`).
   - При вызове статус хода переходит в `CANCELLED`, фоновая группа процессов останавливается (`SIGTERM` -> 2с -> `SIGKILL`), слот семафора `MAX_CONCURRENT=2` немедленно освобождается, отдаётся ответ `200 {"ok": true, "turn_id": turn_id, "status": "cancelled"}`.
2. **RW-002 (F-002): Модель угроз и безопасность.**
   - Установить `threat_model.required = true` в `architecture-packet.json`.
   - Заполнить раздел `security`: валидация `turn_id` по регулярному выражению `^[a-zA-Z0-9_-]{1,64}$` против path traversal; проверка Bearer-токена / клиента на эндпоинтах чтения и отмены ходов; права `0600` на файлы дампов в каталоге с правами `0700`.
3. **RW-003 (F-003): Точный состав `turn_key`.**
   - Зафиксировать структуру `turn_key`: кортеж/хеш `(workspace, model_id, session_id/rid, digest_history_including_last_user_message)`.
   - Исключить ложную дедупликацию при повторных генерациях с тем же контекстом.
4. **RW-004 (F-004): Уборка сирот (Orphan reaper).**
   - Описать в `HubLifecycleManager` процедуру зачистки сирот при старте хаба: чтение `children.json`, проверка наличия PID через `os.kill(pid, 0)` и отправка `SIGKILL` зависшим процессам от упавших предыдущих инстансов моста.
5. **RW-005 (F-005): Точный подсчёт активности в `ProcessWatchdog`.**
   - В алгоритме watchdog отслеживать изменение CPU-времени (`cputime` в `ps -o pid=,ppid=,pgid=,stat=,cputime=,command= -g <pgid>`) и события протокола.
   - Спящие процессы без приращения CPU не сбрасывают `idle_timeout`.
6. **RW-006 (F-006): Семантика Gap Replay.**
   - При запросе клиентом `from_seq`, который уже был вытеснен из кольцевого буфера (10 МиБ), возвращать HTTP 410 Gone с кодом ошибки `GAP_DETECTED`, заголовком `X-Oldest-Available-Seq` и ссылкой на дамп состояния.
7. **RW-007 (F-007): Неблокирующая обработка сигналов.**
   - Обработчик `SIGTERM`/`SIGINT` в главном потоке выставляет `threading.Event` (`shutdown_requested`) без захвата замков. Процедура drain и `server.shutdown()` запускается в выделенном потоке-воркере.
8. **RW-008 (F-008): Поставка `core.*` для `bridges/muse-bridge/server.py`.**
   - Зафиксировать способ разрешения импортов `core.*` в изолированном мосте: автоматическое добавление корня `cli-agent-bridge` в `sys.path` при старте `bridges/muse-bridge/server.py`.
9. **RW-009 (F-009): Фичефлаги и аварийное отключение.**
   - Добавить переменные окружения:
     - `DSH_BRIDGE_DETACHED_ENABLED` (по умолчанию `true`)
     - `DSH_BRIDGE_WATCHDOG_ENABLED` (по умолчанию `true`)
     - `DSH_BRIDGE_DRAIN_ENABLED` (по умолчанию `true`)
   - При значении `false` хаб переходит в консервативный режим без отката кода.
10. **RW-010 (F-011): Версионирование и расширяемость событий.**
    - В `BufferedTurnEvent` разрешить passthrough неизвестных типов событий (`kind: str`).
    - В дисковые дампы добавить поле `"schema_version": "1.0"`.

Также учесть неблокирующие предложения:
- FU-001 (F-010): выравнивание трассируемости REQ -> AD -> VER.
- FU-002 (F-012): канонический заголовок `X-Turn-Id` и SSE-поле `id:` (совместимость с `Last-Event-ID`).
- FU-003 (F-013): очистка абстракции `TurnSessionManager` от `core.tool_emulation`.
- FU-004 (F-014): fail-closed при сбое/таймауте `ps` на Darwin.

## Результат работы:
1. Обновить `.ai-team/runs/dsh-bridge-resilience-20261017/architecture/arch-spec.md`.
2. Обновить `docs/adr/0005-resilient-hub-lifecycle-and-detached-turns.md`.
3. Обновить `.ai-team/runs/dsh-bridge-resilience-20261017/architecture/architecture-packet.json`.
4. Проверить валидатором:
   `python3 "/Users/aazhiry1/Мой диск/skils/ai-sdlc/universal/architect-software-product/scripts/validate_architecture_packet.py" --phase draft .ai-team/runs/dsh-bridge-resilience-20261017/architecture/architecture-packet.json --run-dir .ai-team/runs/dsh-bridge-resilience-20261017`
