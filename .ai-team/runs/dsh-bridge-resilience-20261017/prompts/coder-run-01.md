~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/skills/feature.md

# Задача разработчика (Coder): Отказоустойчивость хаба и жизненный цикл ходов DSH

Задача: реализовать архитектурную спецификацию отказоустойчивости общего слоя хаба `cli-agent-bridge` (согласована Архитектурным Советом, receipt `receipts/arch-panel.json`, `status=PASS`).
Критерий приёмки: все новые компоненты (`core/turn_session_manager.py`, `core/watchdog.py`, `core/lifecycle.py`) реализованы в рамках Python stdlib без внешних зависимостей, интегрированы в `server.py` и `bridges/muse-bridge/server.py`, профиль `~/.dsh/profiles/web/cordis.patch.yml` очищен от `{{cwd}}`, все новые автотесты и существующий сьют тестов `python3 -m unittest discover tests` зелёные (exit 0).
Scope:
- Создать `core/turn_session_manager.py` (ManagedTurn, TurnBuffer, TurnSessionManager, Gap Replay 410, отмена хода, версионирование 1.0, права 0600).
- Создать `core/watchdog.py` (AdaptiveTimeoutController 300s/3600s, ProcessWatchdog на macOS Darwin с учётом cputime, fail-closed).
- Создать `core/lifecycle.py` (HubLifecycleManager, неблокирующий перехват сигналов SIGTERM/SIGINT через threading.Event, 503 Retry-After, drain 110s, orphan reaper).
- Интегрировать в `server.py` и `bridges/muse-bridge/server.py` (маршруты /v1/turns/*, валидация turn_id regex, kill-switch флаги окружения, sys.path bootstrap).
- Удалить `{{cwd}}` из `deployment:persona-suffix` в `~/.dsh/profiles/web/cordis.patch.yml`.
- Написать тесты: `tests/test_detached_turn_execution.py`, `tests/test_adaptive_idle_watchdog.py`, `tests/test_graceful_shutdown_drain.py`, `tests/test_turn_cancel_and_gap.py`.
Тяжёлый путь: запуск тестов, смоук-проверка фонового доведения хода и отмены, проверка чистоты `python3 -m unittest discover tests`.

Входные спецификации:
- Спецификация: `.ai-team/runs/dsh-bridge-resilience-20261017/architecture/arch-spec.md`
- ADR 0005: `docs/adr/0005-resilient-hub-lifecycle-and-detached-turns.md`
- Пакет: `.ai-team/runs/dsh-bridge-resilience-20261017/architecture/architecture-packet.json`
- Леджер доработок: `.ai-team/runs/dsh-bridge-resilience-20261017/handoff/panel-rework-brief-arch-a1.json`

Перед началом изменений создай `.ai-team/runs/dsh-bridge-resilience-20261017/plans/coder-01.json` (ROLE PLAN на 4-6 шагов) и выполни реализацию строго по архитектурным контрактам.
