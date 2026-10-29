# Handoff QA: universal image/media fallback

Stage1, 2026-10-29; baseline `012da99905ec27a6133afb4f3e768ff9b4426a8f`. REQ/CON/INV/RISK identifiers находятся в [handoff-architect.md](handoff-architect.md); факты — [evidence-ledger.md](evidence-ledger.md). Это список QA-оракулов и исследованных рисков, не новая EARS/GWT спецификация и не отчёт о реализованных uf-тестах.

## Среда и сохранность baseline

F-202/F-203: `_Fixture` изолирует config и binaries, `_ImgEnv` пишет только IMAGE_INPUT_ENABLED. Новый тест обязан явно включить universal policy в **своём** config, сохранив input flag, сбросить новый cache и восстановить всё через context/patch. Не экспортировать новый fallback env на весь suite. Проверять strict, затем universal, затем strict в одном процессе и в обратном порядке. `_ImgEnv.flag()` перезаписывает весь файл: новый helper должен после вызова записать оба ключа, иначе universal будет случайно выключен.

F-217: старые images — magic+tag, не pixel-valid. Новые positive tests используют настоящие маленькие PNG/JPEG/GIF/WebP. Не переделывать старые fixtures, img10 и assertions. На resource boundaries применять `_small_limits` или другие ограниченные fixtures, не аллоцировать16×20MiB без надобности. Проверка именно body boundary остаётся настоящей HTTP-проверкой размера.

AC-01 / REQ-04: полный исходный тестовый файл является неизменным prefix. Сравнить bytes от HEAD с prefix нового файла, а также `git diff --numstat 5a19559426de7508d525e2bd465eff648665a6a7 -- tests/test_agy_bridge_resilience.py`: deleted=0. Одного numstat недостаточно для гарантии «ни одна старая строка не менялась», нужны prefix check и отсутствие замен/переносов. Не удалять `unittest.main` в конце. Appended classes выполнять import discovery: unittest discover или pytest, а не прямым запуском файла (F-218).

AC-02 / REQ-04: все146 существующих методов по полному файлу и отдельно46 image methods должны проходить, включая два log01 и пять f-methods (F-214). Старый VER-007 проверяет40 IDs с asserts, не44 и не execution. VER-006 включает ещё `test_images_strict.py`; его не пропускать (F-314/F-315). `ao10` фиксирует static fleet/defaults и должен остаться зелёным. Полный project suite нужен перед downstream review/MR, Stage1 его не заменяет.

AC-03 / REQ-01: policy отсутствует/false/malformed → strict. Policy=true,input=true → любой catalog model и допустимый effort может выполнить real image-attached fake CLI attempt без proof/SHA/efforts_proven. Никакого fabricated confirmed proof. Policy=true,input=false → text-only200 при успешном backend. Unknown model или invalid reasoning effort остаются обычной validation error, это не media fallback (F-130).

AC-04 / REQ-02/06: любое media admission/spool failure universal превращается в корректный text-only attempt, с сохранённым текстом и marker/nonempty prompt. В снимке CLI argv/prompt нет add-dir, attachments header, img-N paths, media data/base64/URL/inline objects и `[image N]`. Проверять весь prompt/full_prompt и downstream cold retry, а не только images=[] (F-111/F-124).

AC-05 / REQ-03: image-attached error без delivered → ровно две попытки; первая имеет files/attachments, вторая media-free/add_dir=None, clean old dir до запуска второй. JSON200 с реальным completion, SSE200 без error event и с нормальной terminal completion/[DONE]. No retry после delivered/client_gone. Нельзя принимать один SSE status200 за успех (F-126).

AC-06 / REQ-05: production deployment должен содержать candidate server/fleet и явный universal=true,input=true в config именно deployed ROOT. Затем живой существующий DSH Desktop чат: image→text fallback→следующий history turn, обе целевые модели и одна ранее text-only catalog запись, повтор и parallel scenario. Зафиксировать безопасный request/run id, model, timings, CLI attempts и response completion, log fallback и отсутствие каталога; не писать payload/auth в отчёт. Если upstream отклоняет даже text данной модели, честно зафиксировать backend limitation, а не назвать200 достигнутым.

AC-07 / REQ-06: stripping повторяемо и не мутирует исходный caller payload; после повторной нормализации rendered text и роли/порядок совпадают, placeholders не умножаются. Text-only запросы имеют прежние prompt/protocol и не порождают fallback logs/spool.

AC-08 / REQ-02/03: media fallback структурно логируется ровно при downgrade, reason/stage/attempt безопасны, нет auth/base64/URL/path/prompt. Старый strict reject log contract остаётся прежним (F-209).

## Append-only набор uf01..uf10

Каждый SCN — группа параметризованных/subTest проверок с явными assertions. После добавления их число может быть больше10; coverage oracle важнее числа имён. Все cases проверять JSON и SSE там, где меняется response-path; mocks должны контролировать _execute state и capture Run argv/prompt.

SCN-uf01 / AC-03 / REQ-01: universal enabled и input enabled, прогнать все шесть FLEET_MODELS и допустимые efforts. Убрать/испортить runtime proof SHA, impl_version, formats, efforts_proven без нарушения startup schema; проверить не вызывается strict eligibility gate для universal admission, первый spawn с нужными files и attachments, response200. Отдельно stale binary SHA и catalog unsupported модель. Static FLEET не менять глобально и восстановить patches.

SCN-uf02 / AC-03/04 / REQ-02: коллектор ImageReject taxonomy: image_url missing/неправильная структура, пустой URL, remote http/https/file/relative, SVG/BMP, corrupt/empty/padding base64, MIME mismatch, unknown magic, assistant/system/tool images,17 images, individual/total overflow. В universal media handling нет400, нет download/local-file read, нет partial image spawn: один stripped text run200 и image_fallback stage=collect. Это параметризованная новая ветка тех же данных `_taxonomy_cases`, старый strict outcome не менять.

SCN-uf03 / AC-03/04 / REQ-02: policy=true,input=false; затем очередь и flip input true→false после acquire; затем старый proof SHA меняется во время очереди. При выключенном staging только text, без mkdir/add-dir400; proof mismatch при input=true не блокирует universal image send. Во всех cases все slot доступны в конце. Policy malformed/string/int/oversize config → strict по согласованному контракту; re-enable проверяется после TTL/cache reset без process restart.

SCN-uf04 / AC-04/08 / REQ-02: ENOSPC/EACCES/O_EXCL collision/OSError во втором staged file и mkdir failure → ImageSpoolError. Text-only200, zero media CLI attempts, один text spawn, partial dir отсутствует, registry пуст, permissions не расширены, slots полностью возвращены, image_fallback stage=spool. Cleanup failure отдельно: bounded safe error log без повторного attachments; не утверждать физическое удаление файла без факта, фиксировать cleanup error.

SCN-uf05 / AC-05 / REQ-03: первый `_execute` agy_error/pump_error/timeout/idle_timeout/first_token_timeout при images, text/tool_calls/stream reasoning пусты; вторая успешна. Exactly2 Run, разные attach modes, файлы удалены **до** второго constructor, оба ctx prompts очищены. Generic retry budget0 и budget30 в universal дают bounded одну text деградацию по owner constraint, strict res03 остаётся прежним. Первый state done — guard не включается, третий run невозможен. Второй failure — честный error, не fabricated200.

SCN-uf06 / AC-04/05 / REQ-03/06: три хода с tools: cold image, hot new image с injected failure, успешный cold text fallback и следующий history text turn. Проверить ранний hot continue тоже downgrade; `_session_invalidate` вызывается с ожидаемым key/cid, собственный claim снят, hot_resumed=false и conversation_id пуст до text retry; новый CID commit только после success. В full prompt нет old/new attachments/media. Явный conversation_id тоже не должен resume загрязнённую сессию после downgrade.

SCN-uf07 / AC-04/07 / REQ-06: типы `image_url`, `image`, `input_image`, `input_audio`, `audio`, `video`, `file`, `document`, а также `inlineData`/`fileData` в type/key и dict-content. Media part с собственным `text` не проходит как текст. Unknown structured object не сериализуется. Mixed normal text/valid raster/audio: text сохранён, допустимое image отправляется на первой optimistic попытке, audio удалено; при последующем downgrade нет вообще медиа. Media-only сообщение остаётся безопасно непустым. Исходные messages равны deep copy после обработки.

SCN-uf08 / AC-05 / REQ-03: первый error после delivered text, tool_calls или SSE reasoning — один run и cleanup, без второго ответа. JSON reasoning-only ещё не delivered: text fallback допустим. Client disconnect не запускает fallback, убирает текущий Run/каталог и возвращает slot. Initial empty assistant delta/keepalive не блокирует допустимый retry. State done + bad rc/empty output и missing launcher/constructor OSError проверить как отдельные исключения RISK-03: ни двойных headers, ни fake success.

SCN-uf09 / AC-04/07 / REQ-02/06: повтор одинаковой mixed-media history и повторная normalization, роли system/user/assistant/tool и исходный Unicode/порядок/обычные текстовые URL сохраняются; placeholders стабильны. Hot→cold и cold→hot, images только в старой истории, отсутствующий assistant, latest image-only, empty content и все media rejected: ни новый attachments из full_prompt, ни зависание/empty output. После успешной деградации следующий request снова проходит policy, нет permanent model deny-cache.

SCN-uf10 / AC-01/02/06/08 / REQ-04/05: strict→universal→strict cache/config isolation; static ao10; effective health/models optimistic policy без fake proof; two concurrent tools requests с разными model/cwd и одинаковым cwd/CID CAS race; один media-fallback не удаляет чужие dirs/не инвалидирует обновлённый CID. Sweep во время staging и cleanup, повторные requests на фоне, rollback universal flag без restart, production config read-back. Structured logs sanitized, FD/dirs/children/slots после серии возвращаются к baseline. Запись production config и реальные DSH ходы — release, не unit тест и не Stage1.

## Boundary/resource/negative проверки вне happy-path

SCN-B01 / REQ-01/02:0/1/16/17 images; exactly byte cap и cap+1 для individual/total, base64 padding0/1/2, MIME case; invalid MIME → omission, не попытка decode произвольного формата. Global count учитывает всю историю. Count/encoded length rejection до expensive decode по прежнему контракту.

SCN-B02 / REQ-02: HTTP body cap±1, inflight body budget и connections cap. Для body/admission overflow сохраняются413/503 (F-130/F-310); universal не должен читать бесконечный body ради удаления images. Auth failures401, invalid JSON/framing400, unknown model400 и invalid reasoning_effort400 не переклассифицируются в image fallback.

SCN-R01 / REQ-03: две попытки ограничивают call amplification до2; при batch с проваленными images измерить длительность/CPU/RSS/FD и admission. Сравнить исходные/candidate значения, не обещать throughput по одному local fake run. Native tool side effects до failure не исключаются delivered guard; для неидемпотентного сценария необходим отдельный безопасный oracle, без внешней записи.

SCN-R02 / REQ-02/03: lifecycle permissions0700/0600, no symlink traversal, no overwrite O_EXCL, stale orphan cleanup, active protected, cancellation во время stage/run/fallback, cleanup errors. Проверять живое существование/отсутствие dir на каждой фазе, а не только возврат функции.

SCN-I01 / REQ-06: normalize(normalize(messages)) эквивалентен normalize(messages), повтор клиентского запроса может сделать второй CLI turn — не заявлять exactly-once без dedup контракта. No duplicate chunks в пределах одного запроса после fallback; tool-call delivery блокирует replay.

## Что уже выполнено и что предстоит

На исходном HEAD реально запущены в фоне через run-guarded:

- 36 Image* tests: `python3 -m unittest discover -s tests -p test_agy_bridge_resilience.py -k Image -q` → OK,23.005s.
- 10 AcceptanceOracleTests: `python3 -m unittest discover -s tests -p test_agy_bridge_resilience.py -k AcceptanceOracleTests -q` → OK,9.759s.

Суммарно46/46 текущих image-related tests на baseline. Это не результат будущего candidate. Python3.14 system environment не содержит pytest; unittest import discovery доступен и увидит appended classes. В процессе negative HTTP boundary tests сервер напечатал ConnectionResetError после намеренного закрытия peer; suite завершился OK, run-guarded exit0. Не скрывать такую diagnostic запись как crash продукта.

НЕ ПРОВЕРЕНО на этом этапе: будущие uf-тесты и candidate, полный project suite, установленный universal config, live DSH Desktop image downgrade, provider quota/SLA и нагрузочная устойчивость. Критерии сдачи фичи остаются у release/QA. Наличие описанных AC/SCN не является доказательством их выполнения.
