Ты — независимый ревьюер брифа судьи (`brief-review`, hat=visionary, slot=gemini-3.8-flash-medium).
Ниже даны:
1) Чек-лист `checklist-g1.md` (sha256=ee24542499f9f79f051e8740b37fae1d6eec2ffd1a1b54e1d6281bcb5782bfe1)
2) Результаты пре-линта `prelint-v1.md` (все [L] PASS)
3) Проверяемый бриф `brief-v1.md` (sha256=e0a1f747529d1e4ffefe5e32c401d0aaf6def753d5c41eb5df7906a9a1f102e9, размер 196508 символов; все блоки D9 3.1..3.6 вложены целиком без усечений; ниже приведены шапка, разделы 0..2 и концовка 4).

Проверь выполнение пунктов BR-01..BR-04, JD-02, JD-04, JD-05, JD-06, JD-08, HY-02, HY-05 и выдай короткий отчёт и финальную строку `VERDICT: APPROVE` (или `VERDICT: REJECT`, если есть блокер). Инструменты чтения диска НЕ вызывай.

### checklist-g1.md
# Чек-лист brief-review: arch R1, cycle 1, run agy-image-input-fix-20261029, поколение g1
## Пре-линт [L]
SK-A-02 [L] | обёртки D9 целых файлов Architecture Packet и sha256 == packet_sha256 | источник: brief-review/references/checklist-sources.md#SK-A
SK-A-12 [L] | сравнение строк seat_slot != architect_slot (gpt-6.1-sol-high) | источник: brief-review/references/checklist-sources.md#SK-A
JD-01 [L] | ролевая подпись первой строки brief-v1.md | источник: brief-review/references/checklist-sources.md#JD
HY-03 [L] | отсутствие токенов закрытого списка плейсхолдеров вне блоков артефактов | источник: brief-review/references/checklist-sources.md#HY
## BR — бизнес-требования
BR-01 [P] | Включение приема изображений (image_url data:image/...) для gemini-4-argon и gemini-3.8-flash в agy-bridge (:9887) через метод workspace-read и --add-dir <img_dir> | источник: analysis/agy-image-input-fix/handoff-architect.md
BR-02 [P] | Глобальная 1-based нумерация вложений 1..K на всех путях (холодный, resumed, явный conversation_id, fallback hot->cold) без повторного прикрепления картинок прошлых ходов | источник: analysis/agy-image-input-fix/handoff-architect.md
BR-03 [P] | Все 12 требований REQ-001..REQ-012 и критерии AC-01..AC-12 присутствуют в брифе | источник: analysis/agy-image-input-fix/handoff-architect.md
BR-04 [P] | Конверт HL-ENV/v1 из 46 полей и инварианты Python-профиля aisdlc-gcge/skills/architecture.md | источник: analysis/agy-image-input-fix/handoff-architect.md
## JD — пункты места
JD-02 [N] | Нет промпта другой шляпы и нет двух ролей в одном брифе | источник: brief-review/references/checklist-sources.md#JD
JD-04 [P] | Строгий формат ответа PoL-V06/PoL-V07 (PANEL-NONCE, ARTIFACT-SHA256, COVERAGE, FINDINGS_COMPLETE, ОБЩИЙ ВЕРДИКТ) | источник: brief-review/references/checklist-sources.md#JD
JD-05 [P] | seed_recheck_duty присутствует с полной таблицей дайджестов select_round_seats.py | источник: brief-review/references/checklist-sources.md#JD
JD-06 [N] | R1: чужих вердиктов нет | источник: brief-review/references/checklist-sources.md#JD
JD-08 [N] | Бриф самодостаточен, все первичные артефакты D9 вложены целиком | источник: brief-review/references/checklist-sources.md#JD
## HY — гигиена
HY-02 [N] | Нет противоречий между разделами | источник: brief-review/references/checklist-sources.md#HY
HY-05 [N] | В самом проверяемом брифе судьи нет упоминания brief-review | источник: brief-review/references/checklist-sources.md#HY


### Шапка и разделы 0..2 brief-v1.md
Оцени независимую архитектуру со стороны эволюции, границ системы и контрактов: проверь минимальность вторжения в существующий код, устойчивость к обновлениям CLI Antigravity, соблюдение публичного HTTP/SSE-контракта и чистоту интерфейсов.
PANEL-NONCE: d793d553b10a473c
ARTIFACT-SHA256: ddcbc69fd277d74079d3868eb245a3c05c7d7ea00ddae6369fdc563982433466
ОБЩИЙ ВЕРДИКТ: PASS|NEEDS WORK|RED FLAG
Первыми двумя строками ответа выведи дословно «PANEL-NONCE: d793d553b10a473c» и «ARTIFACT-SHA256: ddcbc69fd277d74079d3868eb245a3c05c7d7ea00ddae6369fdc563982433466».

ВАЖНО (PoL-V06 / PoL-V07 — строгий машинный гейт `verify_panel_proof.py`):
1. Первыми двумя строками твоего ответа (ДО любой строки подтверждения канона `AGENTS.md`, приветствия или заголовка!) выведи ДОСЛОВНО:
PANEL-NONCE: d793d553b10a473c
ARTIFACT-SHA256: ddcbc69fd277d74079d3868eb245a3c05c7d7ea00ddae6369fdc563982433466
2. В теле ответа перед финальной строкой обязательно укажи:
COVERAGE: 6/6 подкатегорий
FINDINGS_COMPLETE: <число находок, 0 если PASS>
3. Самой последней строкой твоего ответа выведи ДОСЛОВНО одну из трёх строк:
ОБЩИЙ ВЕРДИКТ: PASS
ОБЩИЙ ВЕРДИКТ: NEEDS WORK
ОБЩИЙ ВЕРДИКТ: RED FLAG
После строки `ОБЩИЙ ВЕРДИКТ: ...` НЕ ПИШИ ни одной строки или символа!

# Бриф судьи Архитектурного Совета (`ARCH_PANEL`, Round 1, Seat 3: `gemini-4-argon-high`)

## 0. Контекст запуска и твоя роль
- **Run ID:** `agy-image-input-fix-20261029`
- **Stage / Round:** `arch` / `r1` (`round_kind="blind"`, `schema="pol-manifest/2"`)
- **Seat:** `k=3`, `slot_id=gemini-4-argon-high`, `family=Google`, `transport=agy`
- **Оцениваемый артефакт:** `architecture/architecture-packet.json` (`sha256=ddcbc69fd277d74079d3868eb245a3c05c7d7ea00ddae6369fdc563982433466`)
- **Автор артефакта:** внешний слот `Architect` (`gpt-6.1-sol-high`, семейство `OpenAI`, исключено из пула судей: `excluded_author=[{"family": "OpenAI", "evidence_path": "architecture/architecture-packet.json", "evidence_sha256": "ddcbc69fd277d74079d3868eb245a3c05c7d7ea00ddae6369fdc563982433466"}]`).
- **Режим:** изолированный слепой раунд (`blind`). Входы даны ниже в блоках D9; на диск за ними не ходи; инструменты чтения диска/сети не вызывай — весь пакет, план, аналитика и контракты встроены дословно.

## 1. Обязанность `seed_recheck_duty` (критерий 6 «СООТВЕТСТВИЕ КОНТЕКСТУ»)
Проверь честность жеребьёвки `select_round_seats.py` (`schema="pol-manifest/2"`, `selector_sha256="96c525ac5ec3c0c9761f4e7789fe656cb04a86300e2bd9d0059854474842894d"`):
- Дословная строка `seed_input`:
  `agy-image-input-fix-20261029:arch:r1:ddcbc69fd277d74079d3868eb245a3c05c7d7ea00ddae6369fdc563982433466:0000000000000000000000000000000000000000000000000000000000000000`
- Полный SHA-256 (`seed_hex`, 64 hex-символа в `pol-manifest/2`):
  `aabb53b4a0a207b115631f7b662fb3d128c1939f1a61af8c28bd75dc697042d7`
- Полная таблица дайджестов `select_round_seats.py` (`pol-manifest/2`) для независимой сверки строковым сравнением без вызова инструментов:
  1. `rank_slots(seed_hex, ["claude-sonnet-5-5-high", "gemini-4-argon-high", "gpt-6.1-sol-high", "muse-wonder-full-1.0"])` сортирует 4 канонических слота пула `default` по возрастанию `(sha256(f"{seed_hex}#{slot_id}"), slot_id)`:
     - `1`: `sha256("aabb53b4a0a207b115631f7b662fb3d128c1939f1a61af8c28bd75dc697042d7#muse-wonder-full-1.0") = 575707e18bd5933090f646dc39bb6ea7928e605fd879b79be535d4b84f7ebe1e` -> `muse-wonder-full-1.0`
     - `2`: `sha256("aabb53b4a0a207b115631f7b662fb3d128c1939f1a61af8c28bd75dc697042d7#gemini-4-argon-high") = 622163df677f7d80e2e2e338c1be8113af1cb33e8c92dc18114e54149bc05324` -> `gemini-4-argon-high`
     - `3`: `sha256("aabb53b4a0a207b115631f7b662fb3d128c1939f1a61af8c28bd75dc697042d7#claude-sonnet-5-5-high") = cc365dc5c961de3f258f9cc66255004177cea049ce2b694cd78170f01e9d24f6` -> `claude-sonnet-5-5-high`
     - `4`: `sha256("aabb53b4a0a207b115631f7b662fb3d128c1939f1a61af8c28bd75dc697042d7#gpt-6.1-sol-high") = cffd31df239f1713f90118a8017a927f2312c62532dc0bed0667fe88e0ef9cfe` -> `gpt-6.1-sol-high`
     Итого `ranked_order = ["muse-wonder-full-1.0", "gemini-4-argon-high", "claude-sonnet-5-5-high", "gpt-6.1-sol-high"]`.
  2. Исключается семейство автора `OpenAI` (`gpt-6.1-sol-high`), остаётся упорядоченная тройка `triplet = ["muse-wonder-full-1.0", "gemini-4-argon-high", "claude-sonnet-5-5-high"]` (`triplet_rule = "3of3"`, `pool_constrained_3of3 = true`).
  3. Функция `assign_hats(triplet, seed_hex)` вычисляет `sha256(f"{seed_hex}#hat#{':'.join(p)}")` для всех 6 перестановок `p` из `itertools.permutations(triplet)` и выбирает лексикографический минимум:
     - `MIN -> sha256("aabb53b4a0a207b115631f7b662fb3d128c1939f1a61af8c28bd75dc697042d7#hat#muse-wonder-full-1.0:claude-sonnet-5-5-high:gemini-4-argon-high") = 09e444db8f0f3eb8c9d76b22ac1aab413799df9695671920767225d660c96e4b` -> `k=1:muse-wonder-full-1.0, k=2:claude-sonnet-5-5-high, k=3:gemini-4-argon-high`
     - `       sha256("aabb53b4a0a207b115631f7b662fb3d128c1939f1a61af8c28bd75dc697042d7#hat#claude-sonnet-5-5-high:gemini-4-argon-high:muse-wonder-full-1.0") = 53391fa87c820a3342ef4c150f5e2d158745e3c6b9900964eb8c74683c41d591` -> `k=1:claude-sonnet-5-5-high, k=2:gemini-4-argon-high, k=3:muse-wonder-full-1.0`
     - `       sha256("aabb53b4a0a207b115631f7b662fb3d128c1939f1a61af8c28bd75dc697042d7#hat#gemini-4-argon-high:claude-sonnet-5-5-high:muse-wonder-full-1.0") = 7472c2ef99024c7c7a3be1ed59d53741ddec46029cb8afa399ce8412ef4e9017` -> `k=1:gemini-4-argon-high, k=2:claude-sonnet-5-5-high, k=3:muse-wonder-full-1.0`
     - `       sha256("aabb53b4a0a207b115631f7b662fb3d128c1939f1a61af8c28bd75dc697042d7#hat#claude-sonnet-5-5-high:muse-wonder-full-1.0:gemini-4-argon-high") = 9411074de57f65c4a7ade42d04a9d117706cf017879612efb27b20990071d8dd` -> `k=1:claude-sonnet-5-5-high, k=2:muse-wonder-full-1.0, k=3:gemini-4-argon-high`
     - `       sha256("aabb53b4a0a207b115631f7b662fb3d128c1939f1a61af8c28bd75dc697042d7#hat#muse-wonder-full-1.0:gemini-4-argon-high:claude-sonnet-5-5-high") = ce3791124980462619c7e057662a9c56339964644af1b4686c037cc3476deffe` -> `k=1:muse-wonder-full-1.0, k=2:gemini-4-argon-high, k=3:claude-sonnet-5-5-high`
     - `       sha256("aabb53b4a0a207b115631f7b662fb3d128c1939f1a61af8c28bd75dc697042d7#hat#gemini-4-argon-high:muse-wonder-full-1.0:claude-sonnet-5-5-high") = fb031ff78c3689880ed5f3e9b0d652be6d05856cb1c2c690eaaaea9dd15f2c9d` -> `k=1:gemini-4-argon-high, k=2:muse-wonder-full-1.0, k=3:claude-sonnet-5-5-high`
     Лексикографический минимум (`09e444db8f0f...` / верхняя строка таблицы) назначает рассадку по местам:
     `k=1 -> muse-wonder-full-1.0 (Meta/muse)`, `k=2 -> claude-sonnet-5-5-high (Anthropic/claude-p)`, `k=3 -> gemini-4-argon-high (Google/agy)`.
- Укажи результат сверки в рубрике 6 (`СООТВЕТСТВИЕ КОНТЕКСТУ`).

## 2. Рубрикатор оценки (6 обязательных категорий)
Оцени архитектурный пакет строго по 6 категориям (для каждой выведи `VERDICT=PASS` или `VERDICT=FAIL` и обоснование `WHY=...`; если `FAIL` — список `F-NNN` с полями `priority=BLOCKING|WARNING`, `Якоря`, `Правило`, `Evidence`, `Действия`, `Проверка`):
1. **ПОЛНОТА И СЛЕДОВАНИЕ ТРЕБОВАНИЯМ (`REQ-001..REQ-012`, `AC-01..AC-12`)**
2. **КОРРЕКТНОСТЬ И БЕЗОПАСНОСТЬ (`AD-001..AD-006`, валидация MIME/magic bytes/base64, глобальная нумерация `1..K` при resume, `--add-dir <img_dir>` без подмены `cwd`/`sess_key`, маскирование секретов)**
3. **НАДЁЖНОСТЬ, РЕСУРСНЫЕ ИНВАРИАНТЫ И ДЕГРАДАЦИЯ (`high_load_envelope`, `resilience_gates`, квота спула до `_acquire_slot`, реестр `_active_img_dirs`, очистка `img-*`, kill-switch `IMAGE_INPUT_ENABLED`)**
4. **ТЕСТИРУЕМОСТЬ И ВЕРИФИЦИРУЕМОСТЬ (`VER-001..VER-009`, `TC-01..TC-17`, сохранение гейтов `basedpyright`/`ruff`/`unittest`/`pytest`)**
5. **АЛЬТЕРНАТИВЫ И АРХИТЕКТУРНЫЙ ВЫБОР (`alternatives_considered`, стратегическое влияние, two-way обратимость)**
6. **СООТВЕТСТВИЕ КОНТЕКСТУ И ПРОЦЕССУ (`seed_recheck_duty`, границы изменений `bridges/agy-bridge/server.py`, `bridges/agy-bridge/fleet.json`, `tests/test_agy_bridge_resilience.py`)**

## 3. Дословные входы D9 (`exact_artifact_block`)

### 3.1. `architecture/architecture-packet.json` (`sha256=ddcbc69fd277d74079d3868eb245a3c05c7d7ea00ddae6369fdc563982433466`)
```json
{
  "schema_version": "1.0",
  "packet_version": "1.0",
  "preset": "analyst-teamlead",
  "cycle": 1,
  "criticality": "S2",
  "profile": "python-aisdlc-gcge",
  "status": "APPROVED",
  "task_id": "agy-image-input-fix",
  "run_id": "agy-image-input-fix-20261029",
  "summary": "Workspace-read image input agy-bridge: fail-closed proof/flag/validation, global history numbering, isolated --add-dir, slot-bounded ephemeral spool and exact safe logging. Stage 2 design candidate; no panel verdict, implementation, deployment or runtime acceptance asserted.",
  "scope": {
    "repo_root": "~/tmp/cli-agent-bridge/agy-image-input-fix",
    "branch": "fix/agy-image-input-fix",
    "base_sha": "5a19559426de7508d525e2bd465eff648665a6a7",
    "architect_write_allowlist": [
      ".ai-team/runs/agy-image-input-fix-20261029/plans/architect-01.before.json",
      ".ai-team/runs/agy-image-input-fix-20261029/plans/architect-01.json",
      ".ai-team/runs/agy-image-input-fix-20261029/architecture/architecture-packet.json"
    ],
    "coder_target_files": [
      "bridges/agy-bridge/fleet.json",
      "bridges/agy-bridge/server.py",
      "tests/test_agy_bridge_resilience.py"
    ],
    "forbidden": [
      "analysis/agy-image-input-fix/** frozen",
      "core/**",

### Концовка раздела 4 brief-v1.md
`conversation_id=d6266547-4f77-4a4f-af67-b0ae1408a1fe`, `status=SUCCESS`, `duration_seconds=35.304594`.
Точный переданный ответ: `Размер: 1 × 1 пиксель, Формат: PNG (image/png, 8-bit/color RGBA, non-interlaced)`.
Модель открыла `img-1.png` нативным мультимодальным `view_file`. Это подтверждает техническую осуществимость file-read для одной комбинации binary/model/effort/format; raw NDJSON, sha256 бинаря и матрица иных комбинаций не приложены. Это не L3 через HTTP :9887.
```

### 3.6. `analysis/agy-image-input-fix/open-questions.md`
```markdown
# Вопросы и явные допущения

Stage 1 передаётся без открытых блокеров аналитики. Статус closed у ASSUMPTION означает закрытое решение о способе продолжения исследования, а не доказанность значения или разрешение на боевой rollout. Downstream-гейты и владельцы проверки перечислены явно; их нельзя отменить переименованием в допущение.

| ID | Класс | Вопрос | Допущение / закрытие | Статус |
|---|---|---|---|---|
| OPEN-01 | [FACT] | Почему второй текстовый ход получает image-ошибку? | F-02/F-07/F-08: сканируется вся история; конкретный сохранённый payload передан в брифе, повторного перехвата не было. QA воспроизводит массив точно, без выдуманного удаления старых частей. | closed |
| OPEN-02 | [ASSUMPTION] | Доказаны ли четыре MIME на всех мультимодальных моделях и efforts? | Нет: F-27 подтверждает только PNG, Argon, low. Архитектор определяет proof schema и probe/confirmed; QA проверяет все заявляемые комбинации до capability promotion, неподтверждённое не объявляется confirmed. | closed |
| OPEN-03 | [FACT] | Можно ли менять cwd ради картинок? | Нет: F-10/F-11. Дополнительный каталог через --add-dir и абсолютные пути сохраняет исходный cwd и ключ сессии. | closed |
| OPEN-04 | [ASSUMPTION] | Как нумеровать subset на resume? | Допустим общий индекс истории либо локальная перенумерация subset с отдельным mapping. Обязательна биекция markers→files для каждого prompt и полная история для cold fallback; выбор у Архитектора. | closed |
| OPEN-05 | [ASSUMPTION] | Какие реальные RSS, CPU, RPS, FD, порты и SLA? | Не измерены этим Stage 1. HL-ENV хранит явные UNKNOWN и измерительные obligations; нагрузочная приёмка блокируется до численного заполнения/замера. 1800 s — timeout, не p99 SLA; 35.304594 s — одна выборка. | closed |
| OPEN-06 | [FACT] | Как совместить разные 46-полевые конверты? | F-28: обе таблицы включены; текущая SSoT нормативна, список брифа сохранён отдельно без подмены. | closed |
| OPEN-07 | [ASSUMPTION] | Какой флаг и источник kill-switch применить? | Глобальный канон требует default-false GigaRC для runtime-изменения; схема его подключения для локального моста не установлена. Архитектор обязан разрешить контракт флага до Coder; нельзя выдать существующий SQLite flag за image flag. | closed |
| OPEN-08 | [FACT] | Верно ли перенести эталонный MIME lookup без изменений? | F-16: нет, types/max_types расходятся. Установить один ключ и проверить validation+proof+collector согласованно. | closed |
| OPEN-09 | [ASSUMPTION] | Можно ли считать строку historical proof актуальным image proof? | Нет: F-06/F-27. Нужны воспроизводимые binary identity, impl_version, formats и efforts; при несовпадении fail-closed только image-пути. | closed |
| OPEN-10 | [ASSUMPTION] | Кто и когда поставит runtime-копии и выполнит L3? | Исполнитель downstream после архитектурной и кодовой приёмки; этот Stage 1 не деплоит. Родительскому оркестратору передан обязательный сценарий живого чата :9887; без его результата инцидент не сдан. | closed |
| OPEN-11 | [ASSUMPTION] | Доступны ли источники headless/web и raw probe? | Имеются ссылки и выводы в брифе, текущая адресная сверка выполнена только для desktop и двух строк лога. Расширение на headless/web проверять перед rollout, raw probe и binary hash собрать перед confirmed. | closed |

## ВОПРОСЫ ВЛАДЕЛЬЦУ

Для Stage 1 ответа, блокирующего handoff, нет. До нагрузочной/боевой приёмки нужны согласованные SLA p99 и ресурсный бюджет рабочего мака (OPEN-05); остальные обязанности адресованы Архитектору и QA, не считаются выполненными здесь.
```

## 4. Финальное напоминание по формату ответа (`PoL-V06` / `PoL-V07`)
PANEL-NONCE: d793d553b10a473c
ARTIFACT-SHA256: ddcbc69fd277d74079d3868eb245a3c05c7d7ea00ddae6369fdc563982433466
ОБЩИЙ ВЕРДИКТ: PASS|NEEDS WORK|RED FLAG
Первыми двумя строками ответа выведи дословно «PANEL-NONCE: d793d553b10a473c» и «ARTIFACT-SHA256: ddcbc69fd277d74079d3868eb245a3c05c7d7ea00ddae6369fdc563982433466».
Перед финальной строкой вердикта выведи:
COVERAGE: 6/6 подкатегорий
FINDINGS_COMPLETE: <число>
И самой последней строкой ответа выведи ровно одну строку:
ОБЩИЙ ВЕРДИКТ: PASS|NEEDS WORK|RED FLAG
