# Evidence Ledger: Модернизация cli-agent-bridge (консолидация, b_guard и выпил Droid)

[F-01] Контракт адаптеров версионирован константой ADAPTER_API = 1 и абстрактным классом BackendAdapter | core/backend_adapter.py:21, 596 | 2026-10-31
[F-02] AdapterRegistry проверяет типы сигнатур execute_turn и qualify, агрегирует active_total и max_concurrent_total | core/backend_adapter.py:705-732, 777-782 | 2026-10-31
[F-03] Реестр видов ADAPTER_KINDS задан статически в коде и включает три вида: droid, muse, passthrough | adapters/__init__.py:7-11 | 2026-10-31
[F-04] fleet.json (schema 3) определяет 3 бэкенда (droid, muse, codex) и 11 моделей | fleet.json:2, 52-84, 85-356 | 2026-10-31
[F-05] В хабе server.py бэкенд определяется по полю "backend" выбранной модели из каталога FLEET["models"][model_id] | server.py:5286-5289, 5401, 5704 | 2026-10-31
[F-06] Маршрутизация на PassthroughAdapter перехватывает ход до клампа effort, контекстного гейта и инструкций, направляя запрос в upstream | server.py:5287-5299, 5833-5850 | 2026-10-31
[F-07] Для CLI-адаптеров (droid, muse) ход проходит проверку preflight(), контекстный гейт и _instr_gate с вызовом adapter.execute_turn() | server.py:5401-5415, 5647-5685, 5704-5775 | 2026-10-31
[F-08] В хабе :9882 активны 3 бэкенда (droid cap=4, muse cap=1, codex cap=4); суммарная емкость max_concurrent = 9 | server.py:4943; curl http://127.0.0.1:9882/health | 2026-10-31
[F-09] Модель gemini-3.8-flash в хабе :9882 привязана к бэкенду droid, а не к agy | fleet.json:115 | 2026-10-31
[F-10] Модель claude-sonnet-5-5 в хабе :9882 привязана к бэкенду droid, а не к claude -p | fleet.json:88 | 2026-10-31
[F-11] Бэкенд zen отсутствует в каталоге fleet.json и реестре ADAPTER_KINDS хаба :9882 | fleet.json:52-84; adapters/__init__.py:7-11 | 2026-10-31
[F-12] Отдельный мост claude-p-bridge активен на порту 9881 (PID 63977, com.user.dsh-claude-p-bridge.plist) | lsof -i :9881; ps -fp 63977 | 2026-10-31
[F-13] Отдельный мост opencode-zen-bridge активен на порту 9883 (PID 63978, com.user.dsh-opencode-zen-bridge.plist) | lsof -i :9883; ps -fp 63978 | 2026-10-31
[F-14] Отдельный мост agy-bridge активен на порту 9887 (PID 63979, com.user.dsh-agy-bridge.plist) | lsof -i :9887; ps -fp 63979 | 2026-10-31
[F-15] Legacy мост muse-bridge активен на порту 9886 (PID 64025, com.user.dsh-muse-bridge.plist), дублируя встроенный адаптер хаба :9882 | lsof -i :9886; ps -fp 64025 | 2026-10-31
[F-16] Размер канонического файла ~/Мой диск/Context/AGENTS.md составляет ровно 39 784 символа и 62 889 байт в кодировке UTF-8 | python3 -c "import os; p=os.path.expanduser('~/Мой диск/Context/AGENTS.md'); b=open(p,'rb').read(); print(len(b), len(b.decode('utf-8')))" | 2026-10-31
[F-17] Канон удовлетворяет проектному ограничению меньше 40 000 символов (39 784 < 40 000), но из-за кириллицы в UTF-8 (2 байта/символ) байтовый объем 62 889 Б превысил лимит 60 000 Б | ~/Мой диск/Context/AGENTS.md:17 | 2026-10-31
[F-18] В каталоге KB файл AGENTS.md является симлинком на канон, давая прогнозный размер блока 63 262 байта и строки журнала 64 317 байт | tools/b_guard.py:20,227,348,380; python3 tools/b_guard.py --check | 2026-10-31
[F-19] Размер блока 63 262 Б в KB превышает порог 60 000 Б, формируя причину REQ003_SIZE_EXCEEDED cwd=KB basis=block block=63262 limit=60000 и код выхода 2 | tools/b_guard.py:513-525,800,906 | 2026-10-31
[F-20] В tools/b_guard.py константа 60 000 зашита жестко на уровне модуля: BLOCK_LIMIT = 60000 без чтения переменных окружения | tools/b_guard.py:112,321,510,515,522,709 | 2026-10-31
[F-21] В server.py константа 60 000 задана как дефолт вендорной переменной INSTR_BLOCK_LIMIT = int(os.environ.get("DROID_DSH_BRIDGE_INSTR_LIMIT", "60000")) | server.py:396,2660 | 2026-10-31
[F-22] В server.py контур InstructionGuard._evaluate() вызывает b_guard.check_installed(maxbytes, b_guard.DEFAULT_CWDS, GUARD_CANON) без передачи лимита | server.py:2752-2754; tools/b_guard.py:874-909 | 2026-10-31
[F-23] Выход b_guard с кодом 2 из-за REQ003_SIZE_EXCEEDED переводит InstructionGuard в state = unsafe | server.py:2758-2767 | 2026-10-31
[F-24] Входной фильтр server.py:_prompt_guard() при guard_state == unsafe отклоняет новые чаты с кодом 503 launcher_unavailable: instruction guard is unsafe | server.py:5649-5672 | 2026-10-31
[F-25] Проверка _instr_violation() сопоставляет блок с INSTR_BLOCK_LIMIT = 60000 и отклоняет запрос с кодом 503 при превышении 60 000 Б | server.py:5673-5685 | 2026-10-31
[F-26] Окно [L..U] в tools/b_guard.py:evaluate() вычисляется как [115 949 .. 126 120] Б при текущих размерах файлов канона и проектов | tools/b_guard.py:472-503 | 2026-10-31
[F-27] При maxBytes = 118 784 в профилях DSH нижний запас составляет 2 835 Б < MARGIN_MIN (4 096 Б), вызывая предупреждение LOW_MARGIN_LOWER | tools/b_guard.py:533-537; server.py:2764-2765 | 2026-10-31
[F-28] При maxBytes = 121 034 и BLOCK_LIMIT = 120 000 охранник b_guard возвращает exit 0 без ошибок и предупреждений | tools/b_guard.py:check_installed; python3 test | 2026-10-31
[F-29] Тесты test_tm017_self_test_passes, test_rw004_block_boundary, test_rw004_cli_line_boundary, test_tm018_limit_boundary в tests/test_b_guard.py завязаны на границу 60 000 | tests/test_b_guard.py:286,402,425,577 | 2026-10-31
[F-30] Тест test_tm018_live_check_subprocess падает при проверке текущих файлов из-за роста канона выше 60 000 Б и maxbytes=106496 | tests/test_b_guard.py:682 | 2026-10-31
[F-31] Профиль DSH desktop объявляет 7 провайдеров (opencode-go, opencode-go-claude, opencode-zen-bridge, claude-p-bridge, codex, agy-bridge, muse-bridge) | ~/.dsh/profiles/desktop/cordis.patch.yml:124-481 | 2026-10-31
[F-32] Профиль DSH headless объявляет 6 провайдеров, включая cli-agent-bridge (:9882) и muse-bridge (:9882) | ~/.dsh/profiles/headless/cordis.patch.yml:14-177 | 2026-10-31
[F-33] Профиль DSH web объявляет 7 провайдеров с baseURL на порты :10830, :9883, :9881, :2455, :9887, :9882 | ~/.dsh/profiles/web/cordis.patch.yml:263-547 | 2026-10-31
[F-34] Во всех профилях провайдер muse-bridge указывает на порт :9882 и требует переменную DROID_DSH_BRIDGE_KEY | ~/.dsh/profiles/desktop/cordis.patch.yml:438-439 | 2026-10-31
[F-35] В профиле desktop провайдер codex настроен на хаб :9882, а в профиле web — на прямой порт :2455 | ~/.dsh/profiles/desktop/cordis.patch.yml:388; ~/.dsh/profiles/web/cordis.patch.yml:470 | 2026-10-31
[F-36] Во всех трех профилях DSH плагин agent-instructions настроен на maxBytes: 118784 | ~/.dsh/profiles/desktop/cordis.patch.yml:531; headless:234; web:58 | 2026-10-31
[F-37] Скрипт start.sh хаба задает DROID_DSH_BRIDGE_PORT=9882, читает DROID_DSH_BRIDGE_KEY из ~/.dsh/.env и FACTORY_API_KEY из ~/.zshenv | start.sh:8-20 | 2026-10-31
[F-38] В файле ~/.dsh/.env задана переменная DROID_DSH_BRIDGE_KEY, а FACTORY_API_KEY хранится в ~/.zshenv | ~/.dsh/.env:4,9; start.sh:15-16 | 2026-10-31
[F-39] Сервис LaunchAgent com.user.dsh-hub исполняет start.sh хаба, удерживая процесс Python на порту :9882 (PID 75403) | ~/Library/LaunchAgents/com.user.dsh-hub.plist; launchctl list | 2026-10-31
[F-40] Параллельно запущены отдельные LaunchAgents: claude-p-bridge (:9881), zen-bridge (:9883), muse-bridge (:9886), agy-bridge (:9887) | launchctl list; lsof -i :9881,:9883,:9886,:9887 | 2026-10-31
[F-41] Файл fleet.json хаба :9882 содержит 11 моделей для бэкендов droid, muse и codex | fleet.json:2-15; server.py:21 | 2026-10-31
[F-42] В server.py насчитывается более 30 вхождений переменных DROID_* и FACTORY_API_KEY | server.py:147-154,359,396,1848,6300 | 2026-10-31
[F-43] Каскадное чтение BRIDGE_* с fallback на DROID_* обеспечивает 100% обратную совместимость без простоя | start.sh:8-14; server.py:147-149,396 | 2026-10-31
[F-44] Адаптер DroidAdapter изолирован, и его деактивация не требует удаления кода при переводе receipt_required в false | adapters/droid_adapter.py:46-52; server.py:358-360 | 2026-10-31
[F-45] PassthroughAdapter валидирует loopback base_url по регэкспу http://127.0.0.1:([0-9]{1,5})/v1 и готов к подключению локальных бэкендов | core/backend_adapter.py:199, 241-246 | 2026-10-31
