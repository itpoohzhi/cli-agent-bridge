# Реестр доказательств

Дата сверки: 2026-10-29. Пути продукта относительны repo_root `~/tmp/cli-agent-bridge/agy-image-input-fix`. Runtime пути начинаются с `~/`. Строки относятся к текущему снимку ветки fix/agy-image-input-fix; перед реализацией проверять символы при сдвиге строк. «Переданное» означает источник брифа, а не повторно выполненный эксперимент. Тексты скриншотов и секреты не копируются.

[F-01] DSH desktop объявляет input [text,image] для gemini-4-argon и gemini-3.8-flash, baseURL :9887/v1, таймаут 1800000 ms. | ~/.dsh/profiles/desktop/cordis.patch.yml:410-434, прочитано nl -ba | 2026-10-29
[F-02] Любое image_url во всём messages вызывает HTTP 400 image_input_not_supported до проверки launcher и запуска CLI. | bridges/agy-bridge/server.py:542-555,3066-3082 | 2026-10-29
[F-03] IMPLEMENTED_METHODS пуст; confirmed отвергается method_not_implemented, probe — probe_flag_missing, explicit_unsupported несовместим с другим статусом. | bridges/agy-bridge/server.py:185,311-338 | 2026-10-29
[F-04] Fleet schema_version=2: max_images=0, размеры=1 byte, body=33554432 bytes, types=[image/png]; admission=32 connections и 67108864 body bytes. | bridges/agy-bridge/fleet.json:1-40 | 2026-10-29
[F-05] Все шесть моделей fleet text-only, images unsupported и method=null, в том числе gpt-oss-120b. | bridges/agy-bridge/fleet.json:42-164 | 2026-10-29
[F-06] Историческое proof — строка о запрете image_url в stream-json agy 1.3.1 от 2026-10-07; это не доказательство невозможности workspace-read. | bridges/agy-bridge/fleet.json:10-18,56-60 | 2026-10-29
[F-07] Два отказа записаны в 13:53:41 и 14:17:10; оба reason=***, model=gemini-4-argon, model_len=14. Логи не содержат тела запроса. | ~/.dsh/bridges/agy-bridge/logs/bridge.err:4127,4307; адресное чтение sed -n | 2026-10-29
[F-08] Бриф сообщает: DSH сохраняет отклонённое image-сообщение и посылает его вместе с последующим текстовым ходом. Payload не перехватывался в текущем Stage 1; детерминированный эффект для такого массива следует из scan. | .ai-team/runs/agy-image-input-fix-20261029/briefs/analyst-01.md, раздел RC-2; bridges/agy-bridge/server.py:542-555 | 2026-10-29
[F-09] Resume выбирает сообщения после последнего assistant, иначе всю историю; текущий renderer берёт только text и не создаёт image-маркеров. | bridges/agy-bridge/server.py:522-535,558-623 | 2026-10-29
[F-10] Стор горячих сессий используется при tools_count>0; ключ (model_id,cwd,effort); при claim prompt заменяется на resumed. Явный conversation_id имеет отдельную ветку. | bridges/agy-bridge/server.py:3098-3145 | 2026-10-29
[F-11] Run сохраняет валидный пользовательский cwd либо WORKSPACE; CLI получает --dangerously-skip-permissions и --conversation при cid. | bridges/agy-bridge/server.py:2025-2065 | 2026-10-29
[F-12] После hot failure ctx.prompt заменяется full_prompt, cid сбрасывается; повтор возможен только до выдачи клиенту и при доступном retry budget. Максимум две попытки. | bridges/agy-bridge/server.py:2674-2675,2730-2778 | 2026-10-29
[F-13] Текущий finally _run_once освобождает слот; sweep удаляет только run-* старше 3600 s. | bridges/agy-bridge/server.py:2791-2792,3325-3333 | 2026-10-29
[F-14] Эталон распознаёт PNG/JPEG/GIF/WebP по сигнатурам, регистрирует workspace-read version 1 и использует ImageReject(reason). Полного декодирования пикселей нет. | server.py:180-195,618-633 | 2026-10-29
[F-15] Эталон собирает image_url по всей истории, допускает только user и data URL; base64 decode(validate=True), затем signature/MIME и count/byte/total лимиты. | server.py:636-732 | 2026-10-29
[F-16] В эталоне allowed читается из image_limits.max_types, тогда как текущий agy fleet задаёт types; прямой перенос lookup вернёт пустой allowlist. | server.py:693-718; bridges/agy-bridge/fleet.json:20-28 | 2026-10-29
[F-17] Эталон создаёт WORKSPACE/img-uuid, chmod 0700, файлы 0600 до попыток; ошибка spool имеет отдельный state. | server.py:4298-4334 | 2026-10-29
[F-18] Эталонный renderer создаёт сквозные [image N] и attachments с MIME, byte count, относительным путём и инструкцией Read; это инструмент другого моста. | core/tool_emulation.py:37-58,191-237 | 2026-10-29
[F-19] Эталонный HTTP handler ловит ImageReject и возвращает 400 с reason до backend preflight. | server.py:5240-5255 | 2026-10-29
[F-20] Strict image tests проверяют историю/раскладку, 16 изображений, image-only, taxonomy и лимиты. JPEG/GIF/WebP в PNG-only тестовом стенде ожидаемо отвергаются. | tests/test_images_strict.py:77-180,258-375 | 2026-10-29
[F-21] Strict tests проверяют cleanup success/exception/retries/client gone, proof по бинарю, impl_version, formats, effort и журнал без содержимого. Это тесты корневого моста, не доказательство agy. | tests/test_images_strict.py:377-555 | 2026-10-29
[F-22] _SECRET маскирует токены длиной от 24; allowlist содержит только sqlite_snapshot_divergence и sqlite_transcript_divergence. image_input_not_supported имеет 25 символов. | bridges/agy-bridge/server.py:230,453-470; Python len("image_input_not_supported")=25 | 2026-10-29
[F-23] Контракт отказа: reject reason=<reason> model=<model> model_len=<N> client=<peer>; HTTP error содержит message,type,code. | bridges/agy-bridge/server.py:2411-2428 | 2026-10-29
[F-24] /health жёстко сообщает images=False и сохраняет native_tools=True, concurrency и hot_sessions. | bridges/agy-bridge/server.py:2875-2889 | 2026-10-29
[F-25] Runtime server.py и fleet.json в ~/.dsh/bridges/agy-bridge — существующие обычные файлы, не симлинки; LaunchAgent KeepAlive=True запускает /bin/bash и start.sh, cwd workspace, MAX_CONCURRENT=8 и QUEUE_TIMEOUT=1800. | read-only Python plistlib: ~/Library/LaunchAgents/com.user.dsh-agy-bridge.plist: ProgramArguments,WorkingDirectory,EnvironmentVariables; Path.is_symlink для runtime файлов | 2026-10-29
[F-26] Исходные default лимиты: concurrent=4, queue=900 s, execution=1800 s, first-token=120 s; session idle=2700 s, max age=86400 s, max turns=30; WORKSPACE=ROOT/workspace. | bridges/agy-bridge/server.py:89-107,189-193 | 2026-10-29
[F-27] Переданное живое доказательство: agy.real 1.4.9 через agy-cli.sh, PNG 1x1 68 bytes, --add-dir, gemini-4-argon effort low; conversation d6266547-4f77-4a4f-af67-b0ae1408a1fe, SUCCESS, 35.304594 s, нативный view_file прочитал изображение. В этом Stage 1 вызов не повторялся. | .ai-team/runs/agy-image-input-fix-20261029/briefs/analyst-01.md, раздел «Живое эмпирическое доказательство»; сообщение владельца 2026-10-29 | 2026-10-29
[F-28] Текущие 46 полей SSoT architecture.md таблицы 3.0 отличаются от 46 полей брифа. Образец предыдущего handoff содержит два отдельных набора. | ~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/architecture.md:111-165; analysis/agy-realtime-reasoning/handoff-architect.md, разделы 7.1 и 7.2 | 2026-10-29
[F-29] AGY resilience tests содержат сценарии resume, запрета cold retry после reasoning, фонового и plain session isolation, integer retry budget и health compatibility. | tests/test_agy_bridge_resilience.py:1601,1824-1833,1954-2010,2272,2763 | 2026-10-29
[F-30] Retry capacity=3 tokens, credit=0.2/request, cost=1/retry; pause cap=2 s. Это процессный бюджет, не фиксированные 100% повторов. | bridges/agy-bridge/server.py:168-178,2674,2755-2778 | 2026-10-29
[F-31] Бриф задаёт целевые лимиты: count=16, individual=20971520 bytes, total=20971520 bytes, HTTP=33554432 bytes и четыре MIME; это требования, не текущая конфигурация. | .ai-team/runs/agy-image-input-fix-20261029/briefs/analyst-01.md, RC-3; сообщение владельца | 2026-10-29
[F-32] Бриф передаёт сведения об agy.real parser image_url reject (offset 57498104), view_file/multimodal_view_file (55208733,56206397) и повторяемом --add-dir; бинарь в этом Stage 1 не разбирался. | .ai-team/runs/agy-image-input-fix-20261029/briefs/analyst-01.md, RC-1; ограниченное живое подтверждение F-27 | 2026-10-29
[F-33] Авторизация и размер body проверяются до image ветки; тело сверх max_body_bytes получает отдельный отказ, admission ограничивает число HTTP соединений. | bridges/agy-bridge/server.py:2940-2985,3290-3322 | 2026-10-29
[F-34] Назначенные пути и branch подтверждены: fix/agy-image-input-fix; до записи был untracked только текущий .ai-team run, analysis/agy-image-input-fix пуст. | git branch --show-current; git status --porcelain; ls -la analysis/agy-image-input-fix, выполнено 2026-10-29 | 2026-10-29

## Переданное эмпирическое доказательство workspace-read

Источник: бриф Stage 1, раздел живого замера. Изображение: `bridges/agy-bridge/workspace/img-probe-test/img-1.png`, PNG 1×1, 68 bytes. Содержимое и base64 в отчёт не включаются.
Команда исходного оператора (не запускалась аналитиком):

```sh
printf '%s\n' "$NDJSON" | ~/.config/agy-launch/agy-cli.sh --input-format stream-json --output-format stream-json --dangerously-skip-permissions --model gemini-4-argon --effort low --print-timeout=0 --add-dir "$PROBE_DIR"
```

`conversation_id=d6266547-4f77-4a4f-af67-b0ae1408a1fe`, `status=SUCCESS`, `duration_seconds=35.304594`.
Точный переданный ответ: `Размер: 1 × 1 пиксель, Формат: PNG (image/png, 8-bit/color RGBA, non-interlaced)`.
Модель открыла `img-1.png` нативным мультимодальным `view_file`. Это подтверждает техническую осуществимость file-read для одной комбинации binary/model/effort/format; raw NDJSON, sha256 бинаря и матрица иных комбинаций не приложены. Это не L3 через HTTP :9887.
