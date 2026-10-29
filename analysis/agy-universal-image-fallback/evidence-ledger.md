# Реестр доказательств

Снимок: 012da99905ec27a6133afb4f3e768ff9b4426a8f, ветка feat/agy-universal-image-fallback.
Источники прочитаны read-only тремя параллельными Explorer; выборочные факты перепроверены аналитиком.
Значения HTTP в строках описывают as-is, а не уже реализованный universal mode.

[F-101] Image flag: env имеет приоритет; strict JSON boolean true; default false и TTL 1 s | bridges/agy-bridge/server.py:681–715 _read_image_flag/_is_image_input_enabled | 2026-10-29
[F-102] Eligibility требует image input, confirmed/probe, method/proof version, formats, effort и binary SHA; _model_supports_images зависит от flag/proof | bridges/agy-bridge/server.py:718–786 _image_proof_reason/_image_gate | 2026-10-29
[F-104] Коллектор обнаруживает только type=image_url в list-content всей истории; прочие media-типы и dict-content не охватываются | bridges/agy-bridge/server.py:789–809 _collect_image_parts | 2026-10-29
[F-105] Gate предшествует count/role/URL/MIME/base64/size/signature проверкам; без image_url коллектор возвращает пустой список без gate | bridges/agy-bridge/server.py:835–930 _collect_images | 2026-10-29
[F-106] URL кроме data: не читаются/не скачиваются; image_url в non-user role отклоняется | bridges/agy-bridge/server.py:871–881 _collect_images | 2026-10-29
[F-107] Sniff проверяет только PNG/JPEG/GIF/WebP magic bytes, не декодируемость пикселей | bridges/agy-bridge/server.py:812–822 _sniff_image_type | 2026-10-29
[F-108] Collector не пишет файлы; хранит base64 и пути img-UUID/img-N.ext; размер проверяется до b64decode | bridges/agy-bridge/server.py:830–930 _new_img_dir/_collect_images | 2026-10-29
[F-109] Staging после acquire slot использует directory 0700 и files 0600/O_EXCL; частичный spool удаляется при OSError/ValueError | bridges/agy-bridge/server.py:933–963 _stage_images; :3125–3208 _run_once | 2026-10-29
[F-110] Cleanup best-effort удаляет каталог и всегда снимает его с active registry | bridges/agy-bridge/server.py:966–977 _cleanup_img_dir | 2026-10-29
[F-111] Пустой images убирает attachments, но не image N markers: _messages_to_prompt всегда передаёт img_counter | bridges/agy-bridge/server.py:589–610 _flatten_content; :1042–1066 _messages_to_prompt | 2026-10-29
[F-112] Renderer принимает любое list-part.text независимо от type, а dict-content превращает в str(content) | bridges/agy-bridge/server.py:589–610 _flatten_content | 2026-10-29
[F-113] Пустая rendered-история получает непустой fallback Reply with exactly: PONG | bridges/agy-bridge/server.py:1063–1067 _messages_to_prompt | 2026-10-29
[F-114] Attachments содержит file paths/MIME/size и instruction; Run передаёт отдельный --add-dir и сохраняет cwd | bridges/agy-bridge/server.py:980–1001 _attachments_block; :2517–2534 Run.__init__ | 2026-10-29
[F-115] Resume берёт сообщения после последнего assistant, attachments новых сообщений и глобальную нумерацию; full_prompt хранится отдельно | bridges/agy-bridge/server.py:1069–1095 _get_resumed_turn_prompt; :3661–3714 do_POST | 2026-10-29
[F-116] Store используется для tools-запросов с ключом model/cwd/effort; plain запрос не изменяет store | bridges/agy-bridge/server.py:3673–3691 do_POST | 2026-10-29
[F-117] Запрошенный invalidate helper отсутствует; CAS-helper в этом HEAD называется _session_invalidate(sess_key,cid) | bridges/agy-bridge/server.py:1129–1133 _session_invalidate; rg -n _invalidate_hot_session_if_matches bridges/agy-bridge/server.py → no matches | 2026-10-29
[F-118] Gate после ожидания slot возвращает image_reject, spool exception возвращает image_spool_error; текстового downgrade нет | bridges/agy-bridge/server.py:3176–3208 _run_once | 2026-10-29
[F-119] Две попытки используют тот же img_dir/images; outer finally удаляет каталог и освобождает slot | bridges/agy-bridge/server.py:3209–3227,3326–3330 _run_once | 2026-10-29
[F-120] Delivered равен text или tool_calls или stream reasoning; state done завершает цикл до retry | bridges/agy-bridge/server.py:3265–3279 _run_once | 2026-10-29
[F-121] Hot failure инвалидирует session, освобождает cid и заменяет prompt на full_prompt; agy_error без delivered имеет отдельный ранний continue с retry budget | bridges/agy-bridge/server.py:3280–3298 _run_once | 2026-10-29
[F-122] Общий retry ограничен agy_error/pump_error/done, delivered=false и retry budget; timeout states не повторяются | bridges/agy-bridge/server.py:3299–3313 _run_once; :1396–1410 _retry_take | 2026-10-29
[F-123] Run constructor OSError и LauncherUnavailable выходят через break до общей retry-ветки; launcher ещё вызывает HTTP reject | bridges/agy-bridge/server.py:3216–3264 _run_once | 2026-10-29
[F-124] do_POST до response ловит ImageReject и возвращает 400; ctx содержит prompt/full_prompt/images/img_dir, но не original messages | bridges/agy-bridge/server.py:3621–3644,3695–3714 do_POST | 2026-10-29
[F-125] Image reject отображается в 400, spool в 500, CLI/pump в 502, timeout в 504, launcher/queue в 503; done с bad rc или empty text тоже proxy_error | bridges/agy-bridge/server.py:3339–3417 _error_body | 2026-10-29
[F-126] JSON успех возвращает 200 после проверки; SSE заранее возвращает 200, а сбой кодирует error event и DONE | bridges/agy-bridge/server.py:3728–3828 _serve_json/_serve_sse | 2026-10-29
[F-128] State done с ненулевым rc возможен и не подпадает под точный owner guard state!=done | bridges/agy-bridge/server.py:3093–3103 _execute; :3407–3414 _error_body | 2026-10-29
[F-129] Health и models capability используют proof-and-flag eligibility; image_input_mode отражает только staging flag | bridges/agy-bridge/server.py:3420–3436,3454–3474 do_GET | 2026-10-29
[F-130] Auth/framing/body/admission/model/effort проверки находятся раньше image collection и имеют собственные 401/400/413/503 ответы | bridges/agy-bridge/server.py:3487–3620 do_POST | 2026-10-29
[F-132] Sweep не удаляет active/symlink dirs; возраст orphan 3600 s и период 600 s | bridges/agy-bridge/server.py:3889–3928 _sweep_workspace/_sweep_loop | 2026-10-29
[F-201] Import loader устанавливает тестовый AUTH_KEY и удаляет AGY_BRIDGE_FLEET, но не изолирует новый fallback env | tests/test_agy_bridge_resilience.py:65–78 _load_bridge | 2026-10-29
[F-202] Fixture подменяет DYNAMIC_CONFIG_PATH/AGY_BIN/LAUNCHER/WORKSPACE на temp; production config не участвует в test requests | tests/test_agy_bridge_resilience.py:934–964 _Fixture | 2026-10-29
[F-203] ImgEnv.flag пишет только IMAGE_INPUT_ENABLED, сбрасывает только старый cache и снимает старый env; нового fallback ключа нет | tests/test_agy_bridge_resilience.py:3983–4039 _ImgEnv | 2026-10-29
[F-204] f001 требует default false, strict bool/size/JSON semantics и env override | tests/test_agy_bridge_resilience.py:5439 test_f001_flag_defaults_false_and_follows_env_then_strict_config | 2026-10-29
[F-205] ao10 фиксирует static fleet version/SHA/method/limits/proofs/input и unsupported остальных моделей; без config eligibility false | tests/test_agy_bridge_resilience.py:5928–6005 test_ao10_repo_fleet_and_server_form_one_consistent_pair | 2026-10-29
[F-206] ao01 требует лишь две image-модели и 400 unsupported/flag-off; ao02/ao03 требуют 400 для image taxonomy до spool/spawn | tests/test_agy_bridge_resilience.py:5505 _taxonomy_cases; :5620–5742 ao01/ao02/ao03 | 2026-10-29
[F-208] life03 требует spool ENOSPC → 500, no spawn, no directories/registry и все четыре slot свободны | tests/test_agy_bridge_resilience.py:4976 test_life03_spool_failure_returns_500_and_leaves_no_directory | 2026-10-29
[F-209] log01/log02 требуют strict reject logs, 400 SHA/effort/MIME и отсутствие auth/payload | tests/test_agy_bridge_resilience.py:5143,5173,5210 ImageLogTests | 2026-10-29
[F-210] res02 фиксирует strict health/eligibility/400 поведение; f002 требует recheck flag/SHA после acquire до mkdir/spawn | tests/test_agy_bridge_resilience.py:5315 test_res02; :5383 test_f002 | 2026-10-29
[F-212] hist05/life02 требуют те же image dir/files на retry; life01 предполагает files на каждой попытке | tests/test_agy_bridge_resilience.py:4682 test_hist05; :4884 test_life01; :4940 test_life02 | 2026-10-29
[F-213] res03: retry budget 0 даёт одну попытку, 30 две; hist06/ao09 запрещают retry после delivered text/reasoning | tests/test_agy_bridge_resilience.py:5367 test_res03; :4710 test_hist06; :5887 test_ao09 | 2026-10-29
[F-214] Image section содержит 46 test methods: img10+hist10+life5+log3+res3+ao10+f5; весь файл содержит 146 | Python AST FunctionDef name.startswith(test_) counts for lineno>=3803 and full tests/test_agy_bridge_resilience.py | 2026-10-29
[F-215] Тестовый diff от baseline уже имеет 2205 added и 0 deleted lines | git diff --numstat 5a19559426de7508d525e2bd465eff648665a6a7 -- tests/test_agy_bridge_resilience.py → 2205 0 | 2026-10-29
[F-216] HttpBridge использует localhost/fake agy; post возвращает status/JSON, sse helper возвращает body без HTTP status | tests/test_agy_bridge_resilience.py:1872 _HttpBridge; :4205 _sse_post | 2026-10-29
[F-217] Image fixtures magic+tag не являются pixel-valid; img10 явно требует принимать truncated PNG без decoding | tests/test_agy_bridge_resilience.py:3884 _img_raw; :4441 test_img10 | 2026-10-29
[F-218] unittest.main стоит до будущего append; новые classes после guard доступны import discovery, но не direct script execution | tests/test_agy_bridge_resilience.py:6008 __main__ guard | 2026-10-29
[F-301] Production image projection содержит только IMAGE_INPUT_ENABLED=true; fallback ключ отсутствует | ~/.dsh/bridges/agy-bridge/dynamic_config.json; read-only sanitized JSON projection on 2026-10-29 | 2026-10-29
[F-302] Tracked bridge files: fleet.json/server.py/start.sh; tracked dynamic_config.json отсутствует | git ls-files bridges/agy-bridge | 2026-10-29
[F-303] DYNAMIC_CONFIG_PATH находится в resolve parent server.py; отдельная runtime-копия имеет отдельный config | bridges/agy-bridge/server.py:98,154 ROOT/DYNAMIC_CONFIG_PATH | 2026-10-29
[F-306] Runtime server/fleet обычные files и совпадают с checkout по SHA256 | read-only ls/hashlib repo and ~/.dsh/bridges/agy-bridge; server=3227e8ef769c5ebda5b4aa5647bbd651f4a9b28c784122c61c3e1f638be9e357; fleet=fe2564ea0eb1f17d681f8ccfb7224b4b44eb4c999cb5ac1cad518736a92b5baf | 2026-10-29
[F-307] start.sh не создаёт и не синхронизирует dynamic config | bridges/agy-bridge/start.sh:7–23 | 2026-10-29
[F-308] Только Argon/Flash 3.8 имеют confirmed workspace-read proof; четыре остальные записи text-only с историческим отказом inline agy1.3.1 | bridges/agy-bridge/fleet.json:45–203 models | 2026-10-29
[F-310] Лимиты: 16 images; individual/total 20971520 bytes; body33554432 bytes; admission32 connections/67108864 inflight bytes | bridges/agy-bridge/fleet.json:21–43 image_limits/admission | 2026-10-29
[F-312] Sibling omission обрабатывает image_url, но text проверяет раньше type и dict-content сериализует как str; полный media sanitizer переиспользовать нельзя | bridges/muse-bridge/server.py:633–650; bridges/opencode-zen-bridge/server.py:4677–4694 | 2026-10-29
[F-313] Предыдущий handoff требует strict400, defaultfalse, spool failure и сохранение images на retry | analysis/agy-image-input-fix/handoff-architect.md:44–49; handoff-qa.md sections4–6 | 2026-10-29
[F-314] VER-006 проверяет zero deleted относительно baseline и отдельно запускает test_images_strict.py | .ai-team/runs/agy-image-input-fix-20261029/teamlead/verification-surface.json object VER-006 | 2026-10-29
[F-315] VER-007 требует 40 ID с AST asserts; это не 44 и не полный подсчёт methods и не выполнение тестов | .ai-team/runs/agy-image-input-fix-20261029/teamlead/verification-surface.json object VER-007 | 2026-10-29
[F-401] Исходные 36 Image* tests прошли за23.005 s, run-guarded exit0; pytest в system Python отсутствует | run-guarded -- python3 -m unittest discover -s tests -p test_agy_bridge_resilience.py -k Image -q → Ran36 tests OK; exec session17642 | 2026-10-29
[F-402] Исходные10 AcceptanceOracleTests прошли за9.759 s, run-guarded exit0; совместно с F-401 покрыты все46 image-related methods | run-guarded -- python3 -m unittest discover -s tests -p test_agy_bridge_resilience.py -k AcceptanceOracleTests -q → Ran10 tests OK; exec session5402 | 2026-10-29
[F-403] После анализа server/fleet/test файл не изменены; strict baseline diff по-прежнему2205 added/0 deleted | git diff --exit-code -- bridges/agy-bridge/server.py bridges/agy-bridge/fleet.json tests/test_agy_bridge_resilience.py → exit0; git diff --numstat 5a19559426de7508d525e2bd465eff648665a6a7 -- tests/test_agy_bridge_resilience.py → 2205 0 | 2026-10-29
[F-404] Repo defaults: execution slots4, retry capacity3 tokens, credit0.2/request, cost1/retry и jitter cap2s; это default constants, не измеренные production env/throughput | bridges/agy-bridge/server.py:109,181–187,1396–1417 MAX_CONCURRENT/RETRY constants | 2026-10-29
[F-405] Repo timeout defaults: queue900s, execution1800s, first event120s; это controller ceilings, не SLA/p99 | bridges/agy-bridge/server.py:110–115 QUEUE_TIMEOUT_S/TIMEOUT_S/FIRST_TOKEN_TIMEOUT_S | 2026-10-29
