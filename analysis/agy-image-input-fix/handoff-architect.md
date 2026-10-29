# Handoff Архитектору: image input agy-bridge

Stage 1 `system-analyst`, 2026-10-29, branch `fix/agy-image-input-fix`.
repo_root: `~/tmp/cli-agent-bridge/agy-image-input-fix`.
run_dir: `~/tmp/cli-agent-bridge/agy-image-input-fix/.ai-team/runs/agy-image-input-fix-20261029`.
Все F-NN объявлены в [evidence-ledger.md](evidence-ledger.md); допущения — [open-questions.md](open-questions.md); AC и оракулы — [handoff-qa.md](handoff-qa.md).
Это входной пакет, не Architecture Packet, не ADR, не вердикт панели и не разрешение на Coder/деплой.

## 1. Постановка и цепочка причин

Пользователь прикрепляет два скриншота в DSH Desktop, но получает HTTP 400 image_input_not_supported. Следующий текстовый запрос в том же чате получает тот же отказ (F-01, F-07, F-08). Цель downstream — безопасно принять изображения там, где их допускает объявленная capability, и восстановить последовательные ходы существующего чата без удаления истории.

- **RC-1 — capability разошлась с реализацией.** DSH разрешает text/image (F-01), а agy catalog и handler безусловно запрещают изображения (F-02..F-06, F-24). Исторический запрет связан с прямыми image_url в NDJSON, а не с чтением файлов. Переданный эксперимент доказывает ограниченную осуществимость workspace-read через native view_file и --add-dir (F-27, F-32).
- **RC-2 — история делает отказ повторяемым.** Сканируется всё messages, включая ранее отклонённые части; сохранение DSH описано оператором, а логи доказывают два отказа, не payload (F-02, F-07, F-08). При снятии безусловного запрета нельзя потерять изображения на resumed subset либо cold fallback. Есть отдельные full_prompt/resume ветки и повтор до выдачи результата (F-09..F-12). Подмена cwd каталогом изображений разрушит рабочие относительные пути и изменит session identity (F-10, F-11).
- **RC-3 — MIME и наблюдаемость требуют отдельного контракта.** Текущий fleet имеет только PNG; целевой контракт задаёт PNG/JPEG/GIF/WebP и лимиты (F-04, F-14, F-31). Нельзя дословно скопировать lookup max_types при ключе types (F-16). Существующая маска скрывает длинные диагностические причины, поэтому два отказа дают reason=*** (F-07, F-22, F-23).
- **RC-4 — исправление репозитория не поставляет runtime.** Обычные файлы ~/.dsh/bridges/agy-bridge не связаны симлинками с веткой; LaunchAgent использует отдельный start.sh (F-25). Это причина риска неполной поставки, а не отдельное доказательство происхождения первых HTTP 400. Нужны доставка, рестарт и L3 через тот же Desktop чат.

## 2. As-Is карта потока

| Шаг / граница | Передаваемые данные и действие | Наблюдаемый отказ / ограничение | Факты |
|---|---|---|---|
| DSH Desktop → HTTP :9887/v1 | OpenAI messages с user content text/image_url; provider capability text/image | UI допускает вложение при text-only runtime | F-01, F-08 |
| Handler → admission/auth/body | Авторизация, Content-Length, JSON, max_body_bytes | 401/413/503 до запуска модели; лимит не равен лимиту decoded bytes | F-04, F-33 |
| Handler → image scan | _has_image_parts(messages) по всей истории | 400 до launcher, включая новый текстовый ход со старой image-частью | F-02, F-08 |
| Text renderer → session store | full_prompt, при tools>0 claim по (model,cwd,effort), resumed subset после assistant | image-маркеров нет; plain не делит автоматический session store | F-09, F-10 |
| Run → launcher → agy | текстовый NDJSON; исходный cwd; опциональный --conversation | прямой image_url исторически не поддержан parser | F-06, F-11, F-32 |
| Execute → retry/fallback | до двух попыток, full_prompt при hot failure, без повтора после выдачи | будущие файлы должны переживать обе попытки | F-12, F-30 |
| Termination / housekeeping | release semaphore; sweep run-* older 3600 s | img-* пока не охватываются sweep | F-13 |
| Runtime filesystem / launchd | start.sh из ~/.dsh; отдельная копия server/fleet | repo diff сам не изменяет живой сервис | F-25 |

## 3. Контракты и данные

Ingress: `POST /v1/chat/completions`, JSON, Bearer/x-api-key текущего моста; JSON и SSE ответы сохраняются. В image_url принимается объект с url в виде data:<MIME>;base64,<payload>, только role=user. Remote http(s), file и иные URL не загружаются (F-15, F-19, F-23, F-33).
CLI egress: текстовое stream-json через канонический launcher, нативные инструменты agy; внешнюю эмуляцию DSH tools не добавлять (F-09, F-11, F-24).
Модель данных: messages (история, 1:N частей) → validated images (упорядоченные bytes/MIME) → эфемерные файлы хода → prompt markers/attachments. Содержимое — потенциальные пользовательские конфиденциальные данные/PII; хранение только на время хода, не журналирование payload. conversation_id и session key — Internal; ключ авторизации — Secret, в артефакты не переносится.
Тестовые контуры: текущие строгие тесты корневого моста и agy resilience (F-20, F-21, F-29), PoC оператора (F-27), живой DSH на :9887 для downstream L3 (F-01, F-25). Новые agy-image tests ещё не реализованы.

## 4. Требования и критерии приёмки

Каждая строка — одно требование с приоритетом, доказательствами и измеримым AC. Уточнение проектного механизма остаётся Архитектору.

| ID | Приоритет | Требование | Основание | Измеримый критерий |
|---|---|---|---|---|
| REQ-001 | MUST | Реализовать проверяемую capability workspace-read для целевых gemini-4-argon/gemini-3.8-flash согласованно в server/fleet/health; unsupported модели остаются text-only. Promotion confirmed допустим только с валидным proof; kill-switch default false и источник по канону согласуются до Coder. | F-01, F-03, F-05, F-24, F-27 | AC-001: при разрешённой и доказанной capability обе целевые модели принимают image-запрос; gpt-oss-120b возвращает 400 image_input_not_supported до spawn; выключение флага возвращает прежний image-отказ, текст успешен. |
| REQ-002 | MUST | Единый MIME allowlist в validation/proof/fleet включает image/png,image/jpeg,image/gif,image/webp; не смешивать types/max_types. Лимиты count=16, per-image=20971520 B, total=20971520 B, body=33554432 B. | F-04, F-14..F-16, F-31 | AC-002: 1..16 валидных картинок четырёх MIME и смешанный набор принимаются в пределах суммы; count 17 и превышения на 1 B дают отдельные коды, body overflow даёт 413. |
| REQ-003 | MUST | Ввести fail-closed ImageReject C-08..C-11 с проверкой capability/proof, формы/роли, data URL, строгой base64, сигнатуры/MIME и лимитов до spool/spawn. | F-14, F-15, F-19..F-21 | AC-003: все 9 image reason из QA возвращают HTTP 400 с точным type/message, ноль CLI spawn и ноль файлов при отказе; текст без images не деградирует при image proof mismatch. |
| REQ-004 | MUST | Сохранить соответствие всех image-частей истории, markers и attachments на cold start, hot resume, explicit conversation и cold fallback; чисто текстовый следующий ход со старыми валидными image-частями не отвергать. | F-02, F-08..F-12, F-18 | AC-004: cold и hot сценарии «изображения → текст» успешны; новый image subset указывает на правильные байты, cold fallback читает все K файлов истории без повторного результата клиенту. |
| REQ-005 | MUST | Не менять пользовательский cwd и sess_key ради изображений; предоставить каталог через --add-dir <img_dir>, attachments используют разрешимые абсолютные пути; инструкция native view_file вместо Read другого моста. | F-10, F-11, F-18, F-27, F-32 | AC-005: captured Popen cwd равен исходному проекту, sess_key идентичен, argv содержит отдельные --add-dir/path, native view_file открывает точный img-N при cwd с пробелами. |
| REQ-006 | MUST | Материализовать только проверенные images в уникальный WORKSPACE/img-uuid, dir 0700/files 0600, сохранить их на всех попытках одного хода и удалить в finally после закрытия всех потребителей. | F-12, F-13, F-17, F-21 | AC-006: файл доступен в каждой попытке и отсутствует после success/error/exception/client disconnect; при частичной записи/ENOSPC нет утечки каталога, повторного spawn либо чужого удаления. |
| REQ-007 | MUST | Сохранить строгий reject log-контракт, добавить канонические безопасные reason/event имена в _LOG_EVENT_NAMES без отключения secret masking. | F-07, F-22, F-23 | AC-007: каждый reason и image_proof_invalid/unsupported_reasoning_effort виден дословно в логах, секрет и длинная base64 контрольного запроса отсутствуют, строка reject соответствует строгому шаблону. |
| REQ-008 | SHOULD | Расширить sweep на осиротевшие img-* старше 3600 s, не удаляя активные каталоги, свежие каталоги, чужие пути и цели симлинков. | F-13, F-17, F-26 | AC-008: контролируемые часы/mtime удаляют stale orphan, сохраняют active даже при возрасте >3600 s, fresh и symlink target; параллельные ходы не читают каталоги друг друга. |
| REQ-009 | MUST | Сохранить text/SSE/reasoning, authentication, admission, таймауты, cancel и policy no-retry-after-delivery; ограничить image CPU/memory/disk без обхода текущих guardrails. | F-12, F-26, F-29, F-30, F-33 | AC-009: существующий agy resilience и image regression suite зелёные, delivered reasoning даёт 1 attempt, concurrency не выше configured limit; numeric memory/FD/CPU gate проверен до production promotion. |
| REQ-010 | MUST | После downstream приёмки поставить оба файла в runtime-каталог с проверкой ревизий, перезапустить LaunchAgent, проверить рабочий DSH чат тяжёлым L3; предусмотреть возврат предыдущих server+fleet парой. | F-01, F-07, F-25, F-27 | AC-010: repo/runtime hashes совпадают для пары, :9887 после рестарта отдаёт актуальную capability, живые ход 1 с двумя различимыми images и ход 2 текст в том же чате успешны с evidence и cleanup. |

## 5. Варианты для архитектурного решения

| Вариант | Осуществимость / обоснование | Условия и риски |
|---|---|---|
| Прямые image_url в stream-json stdin | По имеющимся данным несовместим с parser (F-06, F-32) | Нельзя объявлять реализованной мультимодальность только правкой capability. |
| Workspace-read в agy server+fleet с --add-dir и absolute attachments | Осуществим с условиями: живой PNG/view_file probe (F-27), эталон validation/spool (F-14..F-18) | Сохранить cwd/session key; новые функции и proof привязать именно к agy, а не droid. Требуется полная матрица MIME/model/effort. |
| Перенести cwd в img_dir как в эталоне другого моста | Реализуем технически, конфликтует с требованием сохранения cwd (AC-005) (F-10, F-11, F-17) | Теряются относительные пути проекта, session identity и project instructions. Не соответствует заданному контракту. |
| Оставить text-only, скрыть image capability в DSH | Временный обход, не удовлетворяет цели AC-001/AC-004 (F-01, F-08) | Не восстанавливает текущую историю, меняет смежный компонент вне области Stage 1. |
| Материализовать только hot subset | Недостаточно для существующего cold fallback (F-12) | Full prompt ссылается на отсутствующие исторические файлы. Можно только с доказанной дополнительной материализацией перед fallback. |

Финальный выбор и ADR выпускает Архитектор; аналитик фиксирует ограничения вариантов.

### Нумерация и lifecycle для проверки дизайна

Cold prompt: K image parts всей истории в порядке обхода, marker [image N] связан с <img_dir>/img-N.<ext>. Источник files/markers обязан быть один, а не независимые счётчики с разным subset.
Hot prompt: только сообщения после последнего assistant (F-09). Допустимы стабильные глобальные индексы истории либо локальные индексы с явным отдельным mapping; attachments содержит ровно разрешимые соответствия этого prompt. Картинки всей истории материализованы до первой попытки либо гарантированно до fallback; первый вариант переиспользует один каталог между попытками. В том же каталоге не переименовывать файлы так, чтобы cold и resumed mapping противоречили друг другу.
Explicit conversation_id: фактическая ветка отличается от automatic hot claim (F-10); QA не должна предполагать is_resumed=True только по наличию cid.
После закрытия последнего Run и прекращения чтений — finally cleanup, включая failed spool, exception и client_gone. Ни finally одной попытки, ни backoff не должны удалять каталог преждевременно. Процессный аварийный выход компенсируется sweep; без active registry нельзя безопасно удалить aged active каталог при runtime >1 h с очередью.

### C-08..C-11 и proof

C-08: collect всех частей → capability/proof → role/shape/data URL → strict base64 → magic sniff → MIME allowlist → count/per-image/total. C-09: workspace-read, именование, права, mapping и native view_file. C-10: ImageReject reason и точный 400 error. C-11: журнал только счётчиков и безопасных кодов, без содержимого/ключей.
Зафиксировать приоритет причин для запроса с несколькими дефектами по эталонному порядку; не делать сетевых загрузок. PNG/JPEG/GIF/WebP signature sniff не гарантирует декодируемость изображения; файл с валидной сигнатурой и испорченным телом не следует объявлять визуально распознанным (F-14).
Историческую proof-строку заменить структурой, выбранной Архитектором: agy binary identity/версия метода/форматы/efforts, с fail-closed image при mismatch и рабочим text. Не приписывать подтверждение всех четырёх MIME и high effort единственному PNG low probe. Границы proof и статус promotion — OPEN-02/09.

## 6. HL-ENV/v1: нормативный конверт текущей SSoT

SSoT: `~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/architecture.md:111-165` (F-28). Ниже ровно 46 атомарных строк.
Процесс LaunchAgent моделируется как один pod только для расчётной модели. Факты не заменяются целевыми бюджетами. UNKNOWN — явное допущение OPEN-05 и обязанность замера до нагрузочной приёмки; это не PASS HL-ENV-01. Отсутствие вопроса-блокера Stage 1 не закрывает архитектурный ресурсный гейт.

| № | Поле | Значение / единица | Источник и статус |
|---|---|---|---|
| 1 | `P_steady` | 1 logical pod | F-25; модель одного LaunchAgent |
| 2 | `P_hpa_max` | 1 logical pod; HPA отсутствует | F-25; расчётное допущение |
| 3 | `maxSurge_pct` | 0 ratio | F-25; restart, не rolling deployment |
| 4 | `maxSurge_abs` | 0 pods | ceil(1×0); OPEN-05 |
| 5 | `maxUnavailable_pct` | 0 ratio в расчётной модели; restart даёт downtime | F-25; не обещание availability |
| 6 | `maxUnavailable_abs` | 0 pods в формуле | floor(1×0); OPEN-05 |
| 7 | `P_terminating_overlap` | 0 pods; требуется сверка завершения старого процесса | F-25; допущение до rollout |
| 8 | `P_live` | 1 pod | 1+0+0; условно по предыдущим строкам |
| 9 | `P_avail_min` | 1 pod по формуле; при kickstart фактически возможно 0 | max(1,1−0); OPEN-05 |
| 10 | `W` | 1 process/pod | F-25; один LaunchAgent |
| 11 | `N_proc` | 1 process | P_live×W |
| 12 | `N_proc_steady` | 1 process | P_steady×W |
| 13 | `N_proc_avail_min` | 1 process условно | P_avail_min×W; не гарантия рестарта |
| 14 | `CPU_limit_per_pod` | UNKNOWN cores, hard cap не установлен | OPEN-05; не копировать оценку старого handoff |
| 15 | `κ_skew` | 1 ratio для единственного worker | F-25; модель распределения |
| 16 | `u_bg_worker` | UNKNOWN cores | OPEN-05; измерить с image decode и reasoning polling |
| 17 | `U_pod_sidecars` | UNKNOWN cores, включает agy потомков если бюджет host-wide | F-11/F-25; OPEN-05 |
| 18 | `Mem_limit_per_pod` | UNKNOWN MiB | OPEN-05; согласовать host/process envelope |
| 19 | `Mem_rss_worker_max` | UNKNOWN MiB | OPEN-05; измерить 8 параллельных image ходов |
| 20 | `Mem_shared_max` | UNKNOWN MiB | OPEN-05; не подменять размером spool |
| 21 | `RPS_peak` | UNKNOWN req/s | OPEN-05; concurrency 8 не является RPS |
| 22 | `A_max` | 2 attempts/req максимум | F-12; actual retry ограничен budget |
| 23 | `SLA_p99_s` | UNKNOWN s; execution timeout 1800 s | F-26; OPEN-05, timeout не статистический SLA |
| 24 | `N_entities_max` | 16 images/request target; messages count UNKNOWN | F-31; OPEN-05 |
| 25 | `Limit_dep_share[d]` | agy: 8 active processes; HTTP:32 connections; body admission:64 MiB | F-04/F-25; разные единицы, не соединения к LLM |
| 26 | `Limit_dep_rps[d]` | UNKNOWN req/s для upstream | OPEN-05; локальный limiter не даёт внешнюю квоту |
| 27 | `W_fetchers[d]` | image remote fetch=0; локальные source readers на активный Run | F-15/F-26; image-путь не добавляет сетевой polling |
| 28 | `J_init_s[d]` | 0 s нового image poller; existing timers вне image delta | F-11/F-26; не объявлено соответствием S-HERD |
| 29 | `J_pod_s[d]` | 0 s для одного LaunchAgent | F-25; нет межподового fetch |
| 30 | `T_poll_s[d]` | transcript default 0.05 s; SQLite 0.5 s | F-26; server.py:129,143 |
| 31 | `K_calls[d]` | 0 network calls/image; 1 CLI spawn/attempt | F-11/F-12; native view_file calls измерить |
| 32 | `T_base_s[d]` | retry pause cap 2 s; base algorithm не выводится из cap | F-30; расчёт архитектуры |
| 33 | `T_cap_s[d]` | 2 s retry pause cap | F-30 |
| 34 | `Max_stale_age_s[c]` | image files: только текущий ход; hot idle=2700 s; total age=86400 s | F-26; image cache между ходами не требуется |
| 35 | `Min_healthy_ratio` | UNKNOWN ratio; image delta не вводит candidate pool | OPEN-05; применимость R-BULK доказать graph/diff |
| 36 | `B_retry_max` | 3 tokens/process | F-30: 30 tenths |
| 37 | `min_reserve_retry_rps` | 0 tokens/s time-based; refill=0.2 tokens/request | F-30; эквивалент req/s зависит от RPS |
| 38 | `FD_worker` | UNKNOWN descriptors | OPEN-05; новые image descriptors закрывать до spawn |
| 39 | `ulimit_n` | UNKNOWN descriptors runtime process | OPEN-05; shell limit нельзя считать launchd limit |
| 40 | `λ_new_conn_per_pod(s)` | UNKNOWN conn/s, upstream hidden behind CLI | OPEN-05; loopback отдельно от proxy egress |
| 41 | `C_active_in_scope(s)` | HTTP upper bound 32 connections; upstream UNKNOWN | F-04; OPEN-05 |
| 42 | `N_pods_in_scope(s)` | 1 logical bridge pod; other host apps UNKNOWN | F-25; OPEN-05 |
| 43 | `Port_range_size(s)` | UNKNOWN ports | OPEN-05; диапазон ОС в Stage 1 не измерялся |
| 44 | `T_hold_s(s)` | UNKNOWN s | OPEN-05; TIME_WAIT не измерялся |
| 45 | `SNAT_ips_count(s)` | UNKNOWN IPs upstream; loopback NAT не используется | F-01/F-11; OPEN-05 |
| 46 | `HOTPATH_MODULES` | Handler.do_POST / _collect_images planned / _messages_to_prompt / _get_resumed_turn_prompt / _run_once / Run / _mask_secrets | F-02/F-09/F-11/F-12/F-22; Архитектор дополняет graph |

Замыкание памяти пока НЕ ДОКАЗАНО: `W×Mem_rss_worker_max+Mem_shared_max <= 0.80×Mem_limit_per_pod` содержит три UNKNOWN. Бинарь/model memory следует учитывать отдельно от Python RSS.
Известная нижняя оценка добавочных buffers: 8 одновременных ходов × 20 MiB decoded = 160 MiB; 64 MiB body admission не ограничивает весь RSS. JSON string/base64/decoded copies и prompt copies добавляют память. 20 MiB decoded дают `4×ceil(20971520/3)=27962028` base64 bytes до JSON overhead, что меньше 33554432 B body limit для одной картинки. 16 картинок не означают 16×20 MiB: общий лимит 20 MiB. Размер диска активных spool при 8 ходах ≤160 MiB, без учёта orphan backlog; это целевой расчёт, не замер.

## 7. HL-ENV/v1: 46 идентификаторов брифа, совместимый дополнительный конверт

Этот список сохраняется дословно, но не заменяет нормативную таблицу раздела 6 (F-28). Источники UNKNOWN — OPEN-05, никаких выдуманных runtime измерений.

| № | Поле | Значение / единица | Источник и статус |
|---|---|---|---|
| 1 | `W` | 1 process | F-25 |
| 2 | `P_pods` | 1 logical pod | F-25 |
| 3 | `G_reload` | 1 одновременно живое поколение принято для расчёта; не 0 | F-25; отсутствие reload не означает нулевой budget |
| 4 | `T_threads_per_worker` | UNKNOWN threads; HTTP handler bound=32, плюс Run readers | F-04/F-11; OPEN-05 |
| 5 | `Limit_dep_total` | agy local active=8 processes; upstream global quota UNKNOWN | F-25; OPEN-05 |
| 6 | `Limit_dep_share` | 8 processes выделены local bridge; доля upstream UNKNOWN | F-25; не смешивать ratio и абсолютную квоту |
| 7 | `Pool_app_size` | 8 slots | F-25 |
| 8 | `Pool_app_overflow` | 0 extra execution slots | F-26; semaphore |
| 9 | `Max_in_flight_per_worker` | 8 active turns / 32 HTTP connections | F-04/F-25 |
| 10 | `N_roles` | 1 bridge role в текущем scope | F-25 |
| 11 | `W_role` | 1 process | F-25 |
| 12 | `Pool_role_size` | 8 slots | F-25 |
| 13 | `Pool_role_overflow` | 0 slots | F-26 |
| 14 | `M_other_apps_max` | UNKNOWN processes / shared resources | OPEN-05 |
| 15 | `Ephemeral_port_range_size` | UNKNOWN ports | OPEN-05 |
| 16 | `TIME_WAIT_s` | UNKNOWN s | OPEN-05 |
| 17 | `ulimit_n` | UNKNOWN descriptors | OPEN-05 |
| 18 | `FD_non_socket_overhead` | UNKNOWN descriptors | OPEN-05; files closed before spawn |
| 19 | `N_bg_tasks` | UNKNOWN peak threads/tasks; image pipeline adds no poller by requirement | F-11/F-26; OPEN-05 |
| 20 | `T_poll_s` | transcript 0.05 s; SQLite default 0.5 s | F-26; server.py:129,143 |
| 21 | `Jitter_Ratio` | UNKNOWN existing timers; image processing event-driven | F-30; OPEN-05 |
| 22 | `Startup_Delay_Range_s` | 0 s additional image delay target | AC-009; не runtime факт |
| 23 | `K_calls` | 1 CLI spawn/attempt; at most 2 attempts/request | F-11/F-12 |
| 24 | `Limit_dep_rps` | UNKNOWN req/s upstream | OPEN-05 |
| 25 | `Cold_start_concurrent_pods` | 1 logical pod | F-25 |
| 26 | `Singleflight_Scope` | cid/turn ownership; image spool per HTTP turn | F-10/F-12; не новый shared cache |
| 27 | `Cache_TTL_s` | 2700 s hot idle, max age 86400 s | F-26 |
| 28 | `Max_stale_age_s` | image refs не переживают ход; orphan cleanup age=3600 s target | F-13/F-26; AC-008 |
| 29 | `Payload_bytes_max` | 33554432 B HTTP / 20971520 B decoded total target | F-04/F-31 |
| 30 | `N_items_max` | 16 images target; messages count UNKNOWN | F-31; OPEN-05 |
| 31 | `Hot_path_call_rate_rps` | UNKNOWN req/s | OPEN-05 |
| 32 | `CPU_budget_pct_per_core` | UNKNOWN percent; профиль до promotion | OPEN-05 |
| 33 | `Serde_lib` | stdlib json/base64/binascii по эталону; решение reuse у Архитектора | F-15/F-23 |
| 34 | `P_avail_min` | 1 logical pod по формуле; restart допускает 0 live | F-25; OPEN-05 |
| 35 | `Mem_limit_per_pod` | UNKNOWN MiB | OPEN-05 |
| 36 | `Mem_rss_worker_max` | UNKNOWN MiB | OPEN-05 |
| 37 | `Mem_shared_max` | UNKNOWN MiB | OPEN-05 |
| 38 | `SLA_p99_s` | UNKNOWN s; 1800 s — execution timeout | F-26; OPEN-05 |
| 39 | `T_connect_s` | UNKNOWN s; CLI egress timeout скрыт | F-11; OPEN-05 |
| 40 | `T_read_s` | first token=120 s, execution=1800 s default, queue runtime=1800 s | F-25/F-26; не единый read timeout |
| 41 | `Retries_max` | 1 additional attempt | F-12 |
| 42 | `Retry_Budget_pct` | 20% refill/request + 3-token burst; не 100% sustained retries | F-30 |
| 43 | `Retry_Window_s` | UNKNOWN s; бюджет request-driven, pause cap 2 s не окно | F-30; OPEN-05 |
| 44 | `Min_Retry_Floor_rps` | 0 time-refill/s | F-30 |
| 45 | `N_candidates` | 1 выбранная model dependency; image delta не выбирает пул | F-10/F-11 |
| 46 | `N_floor` | 1 при условной одноэлементной модели; auth/proof нельзя fail-open | F-15; применимость решает Архитектор |

## 8. Гейты отказоустойчивости и риски

| Зависимость / режим | Поведение | Старение / изоляция | Проверка дизайна |
|---|---|---|---|
| Auth, MIME, bytes, count, binary proof | Fail-Closed для image-пути; запрещён remote URL fetch | Нет stale proof после смены binary; text не должен падать из-за image proof | C-08..C-11, AC-001..003, T-LIFE/v1 |
| Spool / filesystem | Fail-Closed текущего image-запроса при ENOSPC/permissions | Каталог одного хода; удалять только своё, закрыть readers до cleanup | AC-006/008; межходовой reuse не вводить |
| Hot conversation | Контролируемый cold fallback только до delivery | TTL 2700/86400 s, key model/cwd/effort, полный image mapping | F-10/F-12/F-26, AC-004/009 |
| agy launcher/upstream | Ошибка ответа, не притворяться, что изображение прочитано | Существующие semaphore/retry budget, новых background retries не добавлять | R-BULK-I1..I5; AC-009 |
| Diagnostic logging | Fail-Open относительно генерации при недоступной диагностике, но не относительно утечки секретов | Только фиксированные безопасные event names; без base64 и полного prompt | AC-007, O-EXIT/v1 |

`C-MULT-I1..I5`: количественные CPU/FD/ports budgets ещё не доказаны; image-файлы не создают новый сетевой пул, но нативный CLI использует egress, который нельзя исключить одним grep.
`S-HERD-I1..I5`: image-путь не вводит polling/cache; существующие source pollers и restart burst остаются частью общей нагрузки. Новые изменения требуют транзитивного callers/callees и git diff, а не бездоказательного N/A.
`H-CPU-I1..I5`: sniff — константный префикс, base64 decode линейный по bounded payload; full/resume prompt не должны умножать bytes по числу попыток. Нужен профиль 8 параллельных ходов; silent memory gate PASS запрещён.
`R-BULK-I1..I5`: сохранить максимум две попытки и процессный token budget, no retry after delivered reasoning; image-сбой не становится поводом обойти auth/capability.
`M-SEM/v1`: slot ownership и cwd/cid ownership не объединять с spool path. `O-EXIT/v1`: по каждому выходу итог и cleanup, причины видны, секреты нет. `T-LIFE/v1`: каталог и readers принадлежат ходу, переживают retry, завершаются до удаления.

Ключевые риски: неполный proof четырёх MIME/effort (OPEN-02), старый fleet version (F-06), нестабильная binary identity, base64 memory amplification, потеря full-history refs на fallback, отложенное чтение удалённого файла в resumed модели, гонка sweep и долгого активного хода, несколько параллельных cwd/моделей, рассинхронизация repo/runtime и незамеченный SIGABRT/другой crash в L3. Каждый риск имеет сценарий в QA; один успешный PNG не закрывает матрицу.

## 9. Ограничения и передача

Разрешённые будущие продуктовые зоны: bridges/agy-bridge/server.py и fleet.json, профильные agy-image/regression tests по решению Архитектора. Корневой server.py и core/tool_emulation.py — read-only эталон; DSH profiles, launcher, binary, другие мосты, проект владельца не менять без расширения scope. Аналитик записал только пять analysis-файлов и receipts в .ai-team.
Не выполнять в Stage 1 deploy, launchctl kickstart, запись в пользовательский чат, коммит, MR и переходы Jira. Родительский preset продолжает Архитектор → ARCH_GATE → внешняя панель → Coder; этот пакет не закрывает preset.
Маппинг Architecture Packet: evidence=F-01..F-34; blocking open questions Stage 1=[]; assumptions=OPEN-02/04/05/07/09/10/11; boundaries/contracts=разделы 2–3; quality scenarios=AC-001..010; risks=раздел 8. UNKNOWN числового HL-конверта не превращаются в approval; до кодового/нагрузочного гейта их должен разрешить Архитектор.
Обратный канал: capability в DSH противоречит runtime (F-01..F-05); types/max_types и разный набор HL полей — явные обнаруженные расхождения (F-16, F-28). Переданное доказательство не разрешает записать ложный proof.formats на все MIME.

## 10. ВОПРОСЫ ВЛАДЕЛЬЦУ

До эксплуатационной приёмки согласовать числовые SLA p99 и ресурсные бюджеты CPU/RSS/FD/RPS (OPEN-05). Stage 1 не ожидает ответа для передачи фактов; Архитектор не должен выдавать UNKNOWN за закрытый HL-ENV-01.
