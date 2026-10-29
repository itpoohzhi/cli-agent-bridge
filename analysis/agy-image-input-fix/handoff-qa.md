# Handoff QA: agy image input

Stage 1, 2026-10-29. Продуктовые тесты здесь не запускались и не менялись; ниже спецификация проверки downstream, не протокол уже успешного исправления.
Требования: [handoff-architect.md](handoff-architect.md), REQ-001..REQ-010. Факты: [evidence-ledger.md](evidence-ledger.md), F-01..F-34. Допущения: [open-questions.md](open-questions.md).

## 1. Контуры и воспроизводимость

L1: валидатор, renderer, fake Run/argv capture, controlled filesystem и FakeClock; никакой случайной картинки или wall-clock гонки в unit oracle.
L2: HTTP handler JSON/SSE на тестовом порту с fake launcher/native-tool trace; проверять до spawn, не только helper return.
L3: реальный :9887, runtime копии из ~/.dsh/bridges/agy-bridge, DSH Desktop, существующий рабочий чат и cwd владельца. До L3 необходимы downstream разрешения/гейты; аналитик не вызывает production chat и не перезапускает сервис.
Повторить сценарии на gemini-4-argon и gemini-3.8-flash и каждом effort, который будет объявлен proof-proven. Матрица model×effort×format фиксирует фактический результат; единственный переданный PNG low probe не закрывает её (F-27).
Сохранить revision/hash пары server.py+fleet.json, binary identity/impl_version, model/effort/cid/turn, cwd, обезличенные request shape и file digests, status/error/log excerpt, cleanup result. Не сохранять секреты, исходный prompt, base64 и пользовательские скриншоты в публичных receipts.

## 2. AC-матрица

| Критерий | Связь | Уровень | Позитивный / негативный / граничный оракул | Доказательство |
|---|---|---|---|---|
| AC-001 | REQ-001 | L1/L2/L3 | Целевые модели принимают image при разрешённой capability; unsupported и flag-off отвергают только image, text успешен; fleet/health совпадают с действующей policy | catalog + health + captured zero/one spawn + L3 result |
| AC-002 | REQ-002 | L1/L2/L3 | Все count 1..16 для каждого из PNG/JPEG/GIF/WebP и смешанный набор; 17 images и byte границы отклоняются точными кодами | parameter matrix + HTTP type + number of spawns |
| AC-003 | REQ-003 | L1/L2 | Каждая строка таксономии ниже проверяет 400 до spool/spawn; proof mismatch не ломает text; неверный proof не даёт confirmed | reason/error/log + spawn count=0 + empty spool |
| AC-004 | REQ-004 | L1/L2/L3 | Cold, auto-hot и explicit conversation; «images → text», новые images после assistant, failed Turn1 history и hot→cold fallback | full/subset prompt mapping + all file hashes + successful second answer |
| AC-005 | REQ-005 | L1/L2/L3 | Пользовательский cwd не подменён, sess_key не изменён; add-dir получает точный уникальный путь, view_file читает указанное изображение | Popen cwd/argv + relative project read + native tool event |
| AC-006 | REQ-006 | L1/L2 | Каталог 0700/файлы 0600, живут во всех retry; удалены после success/error/exception/disconnect; spool failure не течёт | modes/digests during each attempt + filesystem after finally |
| AC-007 | REQ-007 | L1/L2/L3 | Все reason/event tokens видны; auth token, base64 и image bytes не попадают в logs | strict regex + negative secret/payload search |
| AC-008 | REQ-008 | L1/L2 | Sweep stale orphan >3600 s удаляет; =3600 s и fresh сохраняет; active и symlink targets не удаляет | FakeClock/mtime + file existence + isolation of concurrent turns |
| AC-009 | REQ-009 | L1/L2/profile | Resilience/text/SSE/auth/admission не регрессируют; no retry после delivery; resource gates численно замкнуты под нагрузкой | suite exit codes + resource profile + attempt count |
| AC-010 | REQ-010 | L3 | Поставленная пара соответствует ревизии, сервис перезапущен, реальные image и text ходы существующего чата успешны | hashes + :9887 + cid/turn/timestamps + native view_file + cleanup |

## 3. Позитивные и граничные image-кейсы

| TC | Вход / окружение | Ожидание |
|---|---|---|
| IMG-01 | По каждому MIME, количество n∈{1..16}, валидные небольшие изображения, user role | Успех, n marker/file соответствий, все байты совпадают с исходными fixtures, чтение native view_file. Матрица содержит 64 случая на model/effort. |
| IMG-02 | 16 изображений смешанного MIME, сумма ≤20971520 B | Успех, порядок по всей истории, расширения png/jpg/gif/webp соответствуют sniffed MIME. |
| IMG-03 | Ровно 17 маленьких картинок | 400 too_many_images; ни одного процесса/файла. |
| IMG-04 | Одна картинка ровно 20971520 B и сумма ровно 20971520 B | Валидатор принимает; использовать корректный container/padding либо fixture валидатора с явным ограничением, не объявлять native decoding доказанным по magic-only fixture. |
| IMG-05 | Одна картинка 20971521 B | 400 image_too_large; проверка individual precedes total. |
| IMG-06 | Две картинки, каждая ≤20971520 B; сумма 20971520 B / 20971521 B | На границе успех / 400 images_too_large. |
| IMG-07 | HTTP Content-Length ровно 33554432 B / 33554433 B, валидный JSON нужного размера | На границе body admission проходит к дальнейшей validation / 413 payload_too_large до decode и spawn; не путать HTTP байты с decoded bytes. |
| IMG-08 | Image-only user, без text | Не fallback PONG; image marker + attachments сохраняются. |
| IMG-09 | Не-image части, text-only история, пустые/неизвестные parts | Сохраняется старое поведение text и unknown non-image parts; не создаётся img_dir для отсутствующих images. |
| IMG-10 | Частично повреждённый файл с известной сигнатурой | Magic sniff не декодирует пиксели (F-14); при невозможности view_file модель явно сообщает ошибку, не утверждает, что видит изображение. |

## 4. Таксономия ImageReject C-08..C-11

Все строки ниже: HTTP 400, error.type=<reason>, message=`image rejected: <reason>`, error.code=400; reject reason виден дословно. Валидатор не материализует и не запускает CLI при отказе. Для нарушений HTTP body/admission — отдельные 413/503, не ImageReject.

| Reason | Отрицательный fixture | Приоритет / дополнение |
|---|---|---|
| image_input_not_supported | Валидный image у unsupported gpt-oss-120b; unverified; probe без разрешающего режима; подтверждённая модель с proof mismatch | Capability/proof проверяется первой; у text-only запроса те же обстоятельства не дают image-отказ. |
| image_url_not_allowed | http://, https://, file://, относительный путь либо иной non-data url | Ноль network fetch; никакого доступа к локальному file URL. |
| unsupported_image_type | data:image/bmp;base64,...; неизвестный magic; выключенный в allowlist известный MIME | Канонический types используется и collector, и proof; все четыре целевых MIME в positive fleet разрешены. |
| invalid_image_base64 | @@@@, пустой payload, padding error, посторонние символы | b64decode(validate=True); нет permissive decode. |
| image_type_mismatch | MIME image/png с JPEG сигнатурой; MIME image/webp с GIF сигнатурой | Известный sniffed MIME ≠ заявленный; неизвестная сигнатура даёт unsupported_image_type. |
| invalid_image_content | image_url строка вместо object, url missing/non-string, data URL без запятой/base64, role assistant/system/tool | Сохранить точный canonical order; не относить любой неверный payload к base64 error. |
| too_many_images | 17 valid small images | Лимит применяется к полной истории, включая старые части, а не только последнему user. |
| image_too_large | Одна valid image на 1 B больше individual limit | До total-limit проверки. |
| images_too_large | Несколько валидных individual-sized images, total на 1 B больше | Должен быть отдельный код. |

Proof cases: изменить binary identity, impl_version, proof.formats, efforts_proven по одному. После изменения image отвергается, диагностический `image_proof_invalid` и точный подreason видны, text остаётся работоспособным. Перезапуск/mtime cache не должен сохранять старое разрешение. Schema/static inconsistency fleet — отказ старта по FleetViolation, не случайный runtime 500. Одна успешная комбинация не подтверждает high effort или другую модель.

## 5. История, горячие сессии и fallback

| TC | Сценарий | Оракул |
|---|---|---|
| HIST-01 | Cold: Turn1 user с двумя различимыми images; assistant; Turn2 user text, весь messages массив передан повторно | Оба ответа успешны. На втором ходе исторические images валидируются; full prompt соответствует всем файлам, нет 400 image_input_not_supported. |
| HIST-02 | История точного инцидента: отклонённый ранее user с двумя images, затем новый user text, без assistant между ними | Полная история принимается capability-enabled моделью; last_asst=-1 не должен терять картинки. Это именно восстановление старого чата, не virgin conversation. |
| HIST-03 | tools>0, одинаковые model/cwd/effort: успешный Turn1 images, Turn2 text автоматически claims горячий cid | --conversation=<cid>; нет нового случайного cwd/session key; resumed prompt без несуществующих attachments. Нет отказа из-за старых image parts. |
| HIST-04 | Hot: старая история с images, assistant, новый user с новыми images | Каждый resumed marker связан с правильным текущим файлом и MIME. Различимые fixtures выявляют сдвиг индекса, пропуск и смешение old/new. |
| HIST-05 | HIST-04, первая resumed попытка даёт agy_error до delivery, есть retry token; вторая cold | Две попытки максимум; cid сброшен, full_prompt использован; все K image files доступны при второй попытке в том же img_dir либо эквивалентно доказанном mapping. |
| HIST-06 | Hot failure после content/tool_calls либо SSE reasoning delivery | Второй spawn не производится. Не дублируется ответ. Файлы удаляются после закрытия первого Run. |
| HIST-07 | Явный conversation_id; отдельно automatic hot claim | Тестирует реальную ветку F-10: explicit cid не обязан выставлять hot_resumed. Полный prompt и файлы согласованы в обоих случаях. |
| HIST-08 | Plain tools=0 и background запрос параллельно agentic session | Не крадут cid, не читают/пишут agentic session store, img_dir у каждого свой. |
| HIST-09 | Изменяется только cwd / model / effort, concurrent два запроса | Не делят один занятый cid; session keys различимы и cwd не заменён image directory. |
| HIST-10 | User cwd существует, содержит пробелы/Unicode; внутри относительный project-file; отдельно cwd отсутствует | Popen cwd = project path либо WORKSPACE по прежнему контракту. --add-dir передаётся argv парой без shell interpolation, attachments absolute. view_file image и project relative read успешны. |

Не требовать, чтобы старый файл прошлого хода существовал после его finally. На новом ходе история материализуется заново в новом каталоге; если модель пытается открыть старый удалённый путь, наличие memory без чтения не считается успехом. Проверять реальные native tool events по актуальным paths.

## 6. Lifecycle, isolation, логирование и ресурсы

| TC | Воздействие | Проверка |
|---|---|---|
| LIFE-01 | Success, generic error, raised exception, client disconnect, launcher unavailable | Каталог удалён при каждом terminal path, readers/процесс закрыты до удаления; слот возвращён. |
| LIFE-02 | Retry и hot→cold fallback | Одинаковые digests доступны на каждой попытке; после последней попытки img_dir отсутствует. Отсутствует cleanup внутри первой попытки. |
| LIFE-03 | Ошибка mkdir/chmod/write/ENOSPC на втором файле | Частично созданное удаляется в finally; нет попытки с неполными файлами и нет утечки чувствительных данных в error/log. |
| LIFE-04 | Два параллельных image request, один завершается раньше | Разные UUID каталоги, cleanup первого не трогает второй, mappings не смешаны. |
| LIFE-05 | Sweep: stale orphan, active >3600 s, fresh, exact age 3600 s, non-img, symlink | Удаляется только строго старый orphan внутри workspace; active и чужие пути сохранены; симлинк не ведёт к удалению внешней цели. |
| LOG-01 | Каждый canonical reason, длинный unsupported_reasoning_effort, image_proof_invalid и его subreason | Время/префикс логгера отделены; полезная часть соответствует `^reject reason=<expected> model=<expected> model_len=<N> client=<peer>$`, reason никогда не ***. |
| LOG-02 | Synthetic AUTH_KEY и уникальная длинная base64 marker во входе | Ключ, payload, bytes и полный prompt не обнаружены во всех log sinks; safe allowlist не становится правилом пропуска любых длинных токенов. |
| RES-01 | 8 runtime concurrent requests в лимитах 32 HTTP/64 MiB admission; image total 20 MiB per request | Измерить peak Python RSS, child RSS, FD, CPU, spool size; submitters превышающие лимиты корректно ограничиваются. Сопоставить согласованным HL budgets, а не произвольному числу из старого handoff. |
| RES-02 | Failure/retry storm + exhausted retry budget | Максимум 2 attempts/request, refill 0.2/request и burst 3 сохраняются; sleep cap 2 s не трактуется как Retry_Window_s. |
| RES-03 | Flag-off / proof mismatch / text SSE regression | Disabled image path не создаёт files; text, reasoning, health additive fields, auth и no-retry-after-delivery сохраняются. |

Не вводить test fixtures, которые проходят PNG magic, а затем выдавать это за доказательство визуальной поддержки всех форматов. Для L3 нужны настоящие декодируемые изображения. Crash процесса/SIGABRT или связанный crash-report означает FAIL независимо от зелёных unit tests.

## 7. L3: поставка и живой тяжёлый путь :9887

Исполнитель downstream фиксирует согласованную ревизию и приёмку кода. Проверка возможна только после реализации; в Stage 1 статус всех пунктов ниже NOT RUN.

1. Зафиксировать SHA256 и ревизию исходных `bridges/agy-bridge/{server.py,fleet.json}` и обеих текущих runtime-копий; сохранить пару предыдущей версии по разрешённому backup protocol. Не выводить token/env. Согласовать source kill-switch и capability promotion.
2. Поставить оба обновлённых файла в `~/.dsh/bridges/agy-bridge/`, сверить hashes, затем `launchctl kickstart -k gui/$(id -u)/com.user.dsh-agy-bridge`. Это инструкция будущему исполнителю, не выполненное действие аналитика.
3. Проверить PID/порт :9887, health/catalog и отсутствие startup FleetViolation. Это только лёгкий путь; отдельно проверить отсутствие старого процесса и корректное завершение активных ходов.
4. В том же существующем рабочем чате Desktop и реальном cwd knowledge-base отправить две различимые безопасные картинки (например, разное число/цвет фигур), попросить указать детали обеих. Использовать выбранные владельцем данные, не публиковать исходные скриншоты. Подтвердить native view_file по точным новым paths и правильный ответ; HTTP 200 сам по себе не доказывает vision.
5. Во втором ходе того же чата отправить только текст, проверить успешный ответ и отсутствие прежнего 400. Сверить, что DSH сохранил исходные image parts, а тест не заменил чат новым. Не редактировать историю ради прохождения.
6. Повторить cold и automatic hot варианты, добавление новой картинки на hot turn и контролируемый hot failure→cold fallback в разрешённом тестовом контуре с той же сборкой; не провоцировать боевой сбой произвольным убийством процессов. Явный cid проверить отдельно.
7. Реальные PNG/JPEG/GIF/WebP и 1..16 images проверять в пределах total/body limits; неподтверждённые модели/efforts не повышать до confirmed. Провести повторный и параллельный запрос, проверить cwd, duration и отсутствие cross-turn смешения.
8. Проверить modes/files во время хода и удаление после завершения/отмены. В логах :9887 причины видны, base64/ключи отсутствуют; crash reports отсутствуют. Не журналировать содержимое пользовательского скриншота ради доказательства.
9. При FAIL вернуть server+fleet предыдущей парой, перезапустить и проверить текстовый рабочий ход. Отдельно зафиксировать судьбу old hot slots, binary cache, runtime flag cache, orphan dirs и параллельных процессов — они не считаются проверенными по одному /health.

Итог L3 оформлять тремя строками:
`ПРОВЕРЕНО ЛЁГКИМ: hashes/health/catalog/...`
`ПРОВЕРЕНО ТЯЖЁЛЫМ: cid/turn/time, два изображения → текст, native view_file, cleanup, cwd/...`
`НЕ ПРОВЕРЕНО: конкретные остатки матрицы/...`
Пустые доказательства и NOT RUN не превращать в «работает». Пока L3 не выполнен, поставка/инцидент не сданы; успешный Stage 1 означает только вход для Архитектора.
