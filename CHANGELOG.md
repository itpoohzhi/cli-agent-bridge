# Changelog

Формат — [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added
- **Мульти-бинарный хаб (ADR 0002):** `core/backend_adapter.py` (контракт `BackendAdapter`,
  `AdapterRegistry`, единый валидатор записей `backends` schema 3), `adapters/` (`ADAPTER_KINDS`,
  `DroidAdapter` как оболочка над прежним RPC-путём, `MuseAdapter` — Muse CLI через
  `~/.config/muse-launch/muse-cli.sh`), каталог `fleet.json` schema 3: 8 моделей (6 droid +
  2 muse — `muse-spark-1.3`, `muse-spark-1.3-contributor`), `model → backend` строго по
  каталогу, per-backend ёмкость, `children.json` с тегом вида. Документация — ADR 0002
  (`docs/adr/0002-multi-binary-hub.md`), разделы README «Мульти-бинарный хаб», «Muse:
  безопасность и компенсаторы», «Как добавить бэкенд», «Запуск и откат».
- Ходы muse изолированы per-turn каталогом `workspace/muse/turn-<uuid>/` (0700, prompt 0600
  внутри, удаляется в `finally`), `max_concurrent: 1`; допуск образа Muse — обязательный
  sha256-pin `technical_ref`; `MUSE_BIN` вычищается из окружения ребёнка, `MUSE_PROXY_PORT`
  нормализуется из каталога (RW-001, RW-002, RW-011).
- Наследие ходов muse (`muse/prompt-*.txt`, `muse/turn-*`) подметается `_sweep_workspace`
  (порог 1 ч, на остановке — безусловно); собственные дети muse регистрируются в
  `workspace/state/children.json` (`kind: muse`) и добиваются `reconcile_children()` на
  старте после аварии хаба (RW-010).
- Тесты хаба: `tests/test_backend_contract.py`, `tests/test_fleet_v3.py` (включая паритет
  валидатора с `fleet_check.py`), `tests/test_muse_adapter.py`, `tests/test_hub_integration.py`
  (фасадный шов через настоящий HTTP-handler с fake droid/muse) — всего в сьюте 459 тестов.
- Долгоживущий процесс `droid exec` (stream-jsonrpc) на keyed-чат: resume того же SID через `load_session`, idle-гашение
  (`DROID_DSH_BRIDGE_IDLE_SECONDS`), ресурсы L/P/T, персистентность состояния чатов (ADR 0001).
- Допуск образа droid по receipt schema 2 (`tools/droid_image.py` с реальными пробами spawn/update/load), проверка версии
  протокола и каталога tools живого процесса.
- Автоматический контур b_guard внутри моста (старт + период): alert `instr_guard_alert`, управляемый отказ для новых чатов
  при небезопасном профиле DSH; переменные `DROID_DSH_BRIDGE_INSTR_MARGIN`, `_GUARD_TICK`, `_PROFILES_DIR`, `_CANON`.
- README: раздел «Развёртывание» с обязательным порядком шагов и откатом; ADR 0001 и индекс ADR.

### Changed
- Предел блока agent-instructions: форма KB (cwd = KB либо блок из копий канона, в том числе прежнего) — 60 000 Б, прочие блоки —
  `maxBytes` профиля минус запас; проверяются все блоки во всём тексте сообщений. Отказ по размеру и по охраннику — 503
  `launcher_unavailable` (раньше 400 `REQ003_SIZE_EXCEEDED`; внутреннее имя осталось в журнале `instr_gate_alert`).
- Receipt schema 2: константы и отпечатки вынесены в `tools/receipt_schema.py`; `tools/droid_image.py` не импортирует мост и не
  читает `fleet.json`. В receipt добавлен `settings_profile.readback` (подтверждённые и непроверяемые поля).
- README «Развёртывание»: до применения профиля владельцем проверяется план (`b_guard --check --maxbytes 106496`, exit 0),
  после применения — установленное (`b_guard --profiles`, exit 0).
- Значения по умолчанию байтовых бюджетов: RPC-строка 8 МиБ, inbox 4 МиБ, текст хода 10 МиБ; ответ клиенту отдаётся срезами по 64 КиБ.
- `/health.ok` равен `false`, если допуск образа обязателен, а receipt невалиден (набор из 7 ключей не менялся).
- Каталог `fleet.json` — schema 3 (`backends`, поле `backend` у моделей, muse `max_concurrent: 1`);
  `/v1/models` объединяет модели включённых бэкендов, `/health` суммирует `active`/`max_concurrent`
  по бэкендам и берёт `ok` по `required`-бэкендам (ключи не менялись). README: разделы хаба, ADR 0002,
  актуальный статус гейтов (`basedpyright` — 13 baseline-ошибок, файлы хаба чистые).

### Fixed
- Замечания Совета Тимлидов Cycle 1 по хабу: автоматический replay промпта muse убран
  (повтор мог продублировать уже исполненные native-действия), успех требует
  `terminal.completed`, failure reasons и текст входят в общий байтовый бюджет, сырой
  backend-текст не пишется в журнал; завершение группы процессов ограничено по времени и
  потомки добиваются `killpg` до освобождения слота (RW-003, RW-004, RW-006, RW-007, RW-009).
- `_chat_known` учитывает только резидентные сессии: ключ существующего droid-чата не
  открывает muse-ход в обход `unsafe` (RW-008). Единая проверка schema 3 в `server._build_backends`
  и `fleet_check.py` (вложенные типы, `wrapper`, `proxy_port`, `max_concurrent`, неизвестные
  ключи, обязательный pin для muse) вместо AttributeError на `.get()` (RW-005).
- basedpyright по хабу: устранены 4 новые ошибки (`muse_adapter.py` ×3, `tool_emulation.py` ×1),
  остаются 13 baseline-ошибок в `fleet_check.py`/`server.py` (RW-012); dead code `split_tool_calls`
  удалён (FU-002), docstring `DroidAdapter` приведён к фактическому поведению (FU-009).
- Замечания Совета Cycle 5: счёт истории моста исключает user-вставки с пустым `content` (корень `HISTORY_MISMATCH droid=5
  bridge=8` после idle); `DROID_BRIDGE_MAX_JSON_STRUCT_TOKENS` по умолчанию 50000 (счёт `{ [ , :` до `json.loads`);
  сбой `Thread.start` не выходит из `close()`, сбой закрытия одного ребёнка не прерывает `shutdown_all` и финальный
  `force_kill`; бюджет доставки считает память CPython (обе копии текста), а не UTF-8; `b_guard` отклоняет повтор `config`
  в любой форме (flow/quoted); сбой записи `canon_seen.json` — fail-closed (503 `launcher_unavailable`, без записи в памяти);
  типизация дельты (`basedpyright`: новых ошибок нет, 3 baseline перечислены в README); `droid_image` закрывает stdin/stdout
  и в фоне закрывает stdout при живом читателе; тест-харнесс закрывает handle `.writer.lock`.
- Cycle-4 (RW-005…RW-023): события неизвестных id/parent не создают слот и не попадают в ответ на путях cold/hot/restore;
  терминал не принимается, пока неизвестен id user-сообщения хода; поздний `create_message` завершённого сообщения не меняет
  счётчик истории; сбой `Thread.start` при закрытии процесса закрывает его синхронно; цепочка освобождения L/T/P независима по
  звеньям; область KB-лимита не зависит от текущего содержимого канона; строка из миллионов `{}` и глубокая вложенность
  отклоняются без падения читателя; ошибка `chmod` spool картинок — 502 вместо молчаливого пропуска; короткий `*_complete` не
  занижает учтённый размер; PENDING пишется до первого `add_user_message` и у нового чата; потеря профилей после `ok` — `unsafe`
  (`PROFILES_LOST`); предупреждения охранника попадают в журнал; terminal до ACK не вызывает interrupt и ожидание grace;
  охранник проверяет настоящий `~/.dsh/AGENTS.md`, отвергает профиль с дублями `maxBytes`; `droid_image` берёт read-back
  `settings_updated` из notes и сверяет фактические настройки.
- Замечания Совета RW-003…RW-014: события сообщений без `messageId` уходят в карантин; удерживаемые события считаются по
  реальному размеру (id, дельта, текст) и не копят лишние поля; предел структурных токенов строки RPC учитывает `,` и `:`;
  готовые ответы резервируют общий бюджет памяти выдачи (`DROID_BRIDGE_MAX_DELIVERY_BYTES`, при исчерпании 502 `proxy_error`),
  `arguments` вызовов инструментов выдаются срезами; `b_guard` читает `maxBytes` только по пути `agent-instructions → config`;
  дайджесты виденных канонов сохраняются в `state/canon_seen.json`; `droid_image` закрывает stdout дочернего процесса;
  при сбое запуска потока закрытие процесса возвращает слот P.
- Ошибка записи состояния чата (ENOSPC, расхождение `rec_rev`) больше не даёт успешный ответ: 502 `proxy_error`, чат DIRTY.
- Терминалы, сообщения и дельты чужих/неизвестных/пустых ходов не завершают и не загрязняют текущий ход.
- Закрытие процесса сигналит всю группу: потомок, удерживающий pipe после выхода лидера, не зависает и не утекает.
- Гонка реапера: закрытие по устаревшему снимку idle не затрагивает свежий процесс.
- Возврат слотов P/T и аренды L при сбое Popen, запуска потоков и конструктора хода.
- Права 0700 для заранее созданных каталогов `state`/`runtime`; понятный отказ старта при недоступном каталоге состояния.
- ENOSPC при spool картинок отдаётся как 502 `proxy_error` (публичного 507 нет).
