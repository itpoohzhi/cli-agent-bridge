Оцени независимую архитектуру со стороны эволюции, границ системы и контрактов: проверь минимальность вторжения в существующий код, устойчивость к обновлениям CLI Antigravity, соблюдение публичного HTTP/SSE-контракта и чистоту интерфейсов.
PANEL-NONCE: d356e9006d8c8956
ARTIFACT-SHA256: ddcbc69fd277d74079d3868eb245a3c05c7d7ea00ddae6369fdc563982433466
ОБЩИЙ ВЕРДИКТ: PASS|NEEDS WORK|RED FLAG
Первыми двумя строками ответа выведи дословно «PANEL-NONCE: d356e9006d8c8956» и «ARTIFACT-SHA256: ddcbc69fd277d74079d3868eb245a3c05c7d7ea00ddae6369fdc563982433466».

ВАЖНО (PoL-V06 / PoL-V07 — строгий машинный гейт `verify_panel_proof.py`):
1. Первыми двумя строками твоего ответа (ДО любой строки подтверждения канона `AGENTS.md`, приветствия или заголовка!) выведи ДОСЛОВНО:
PANEL-NONCE: d356e9006d8c8956
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
      "root server.py",
      "other bridges/tests",
      "dynamic_config.json in git",
      "runtime deployment at this stage"
    ],
    "architect_permission": "run-artifacts-write; product read-only"
  },
  "evidence": [
    {
      "id": "EVD-001",
      "kind": "document",
      "ref": "analysis/agy-image-input-fix/evidence-ledger.md#F-01",
      "claim": "DSH desktop объявляет input [text,image] для gemini-4-argon и gemini-3.8-flash, baseURL :9887/v1, таймаут 1800000 ms. | ~/.dsh/profiles/desktop/cordis.patch.yml:410-434, прочитано nl -ba | 2026-10-29",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-01"
    },
    {
      "id": "EVD-002",
      "kind": "document",
      "ref": "analysis/agy-image-input-fix/evidence-ledger.md#F-02",
      "claim": "Любое image_url во всём messages вызывает HTTP 400 image_input_not_supported до проверки launcher и запуска CLI. | bridges/agy-bridge/server.py:542-555,3066-3082 | 2026-10-29",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-02"
    },
    {
      "id": "EVD-003",
      "kind": "document",
      "ref": "analysis/agy-image-input-fix/evidence-ledger.md#F-03",
      "claim": "IMPLEMENTED_METHODS пуст; confirmed отвергается method_not_implemented, probe — probe_flag_missing, explicit_unsupported несовместим с другим статусом. | bridges/agy-bridge/server.py:185,311-338 | 2026-10-29",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-03"
    },
    {
      "id": "EVD-004",
      "kind": "document",
      "ref": "analysis/agy-image-input-fix/evidence-ledger.md#F-04",
      "claim": "Fleet schema_version=2: max_images=0, размеры=1 byte, body=33554432 bytes, types=[image/png]; admission=32 connections и 67108864 body bytes. | bridges/agy-bridge/fleet.json:1-40 | 2026-10-29",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-04"
    },
    {
      "id": "EVD-005",
      "kind": "document",
      "ref": "analysis/agy-image-input-fix/evidence-ledger.md#F-05",
      "claim": "Все шесть моделей fleet text-only, images unsupported и method=null, в том числе gpt-oss-120b. | bridges/agy-bridge/fleet.json:42-164 | 2026-10-29",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-05"
    },
    {
      "id": "EVD-006",
      "kind": "document",
      "ref": "analysis/agy-image-input-fix/evidence-ledger.md#F-06",
      "claim": "Историческое proof — строка о запрете image_url в stream-json agy 1.3.1 от 2026-10-07; это не доказательство невозможности workspace-read. | bridges/agy-bridge/fleet.json:10-18,56-60 | 2026-10-29",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-06"
    },
    {
      "id": "EVD-007",
      "kind": "document",
      "ref": "analysis/agy-image-input-fix/evidence-ledger.md#F-07",
      "claim": "Два отказа записаны в 13:53:41 и 14:17:10; оба reason=***, model=gemini-4-argon, model_len=14. Логи не содержат тела запроса. | ~/.dsh/bridges/agy-bridge/logs/bridge.err:4127,4307; адресное чтение sed -n | 2026-10-29",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-07"
    },
    {
      "id": "EVD-008",
      "kind": "document",
      "ref": "analysis/agy-image-input-fix/evidence-ledger.md#F-08",
      "claim": "Бриф сообщает: DSH сохраняет отклонённое image-сообщение и посылает его вместе с последующим текстовым ходом. Payload не перехватывался в текущем Stage 1; детерминированный эффект для такого массива следует из scan. | .ai-team/runs/agy-image-input-fix-20261029/briefs/analyst-01.md, раздел RC-2; bridges/agy-bridge/server.py:542-555 | 2026-10-29",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-08"
    },
    {
      "id": "EVD-009",
      "kind": "document",
      "ref": "analysis/agy-image-input-fix/evidence-ledger.md#F-09",
      "claim": "Resume выбирает сообщения после последнего assistant, иначе всю историю; текущий renderer берёт только text и не создаёт image-маркеров. | bridges/agy-bridge/server.py:522-535,558-623 | 2026-10-29",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-09"
    },
    {
      "id": "EVD-010",
      "kind": "document",
      "ref": "analysis/agy-image-input-fix/evidence-ledger.md#F-10",
      "claim": "Стор горячих сессий используется при tools_count>0; ключ (model_id,cwd,effort); при claim prompt заменяется на resumed. Явный conversation_id имеет отдельную ветку. | bridges/agy-bridge/server.py:3098-3145 | 2026-10-29",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-10"
    },
    {
      "id": "EVD-011",
      "kind": "document",
      "ref": "analysis/agy-image-input-fix/evidence-ledger.md#F-11",
      "claim": "Run сохраняет валидный пользовательский cwd либо WORKSPACE; CLI получает --dangerously-skip-permissions и --conversation при cid. | bridges/agy-bridge/server.py:2025-2065 | 2026-10-29",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-11"
    },
    {
      "id": "EVD-012",
      "kind": "document",
      "ref": "analysis/agy-image-input-fix/evidence-ledger.md#F-12",
      "claim": "После hot failure ctx.prompt заменяется full_prompt, cid сбрасывается; повтор возможен только до выдачи клиенту и при доступном retry budget. Максимум две попытки. | bridges/agy-bridge/server.py:2674-2675,2730-2778 | 2026-10-29",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-12"
    },
    {
      "id": "EVD-013",
      "kind": "document",
      "ref": "analysis/agy-image-input-fix/evidence-ledger.md#F-13",
      "claim": "Текущий finally _run_once освобождает слот; sweep удаляет только run-* старше 3600 s. | bridges/agy-bridge/server.py:2791-2792,3325-3333 | 2026-10-29",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-13"
    },
    {
      "id": "EVD-014",
      "kind": "document",
      "ref": "analysis/agy-image-input-fix/evidence-ledger.md#F-14",
      "claim": "Эталон распознаёт PNG/JPEG/GIF/WebP по сигнатурам, регистрирует workspace-read version 1 и использует ImageReject(reason). Полного декодирования пикселей нет. | server.py:180-195,618-633 | 2026-10-29",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-14"
    },
    {
      "id": "EVD-015",
      "kind": "document",
      "ref": "analysis/agy-image-input-fix/evidence-ledger.md#F-15",
      "claim": "Эталон собирает image_url по всей истории, допускает только user и data URL; base64 decode(validate=True), затем signature/MIME и count/byte/total лимиты. | server.py:636-732 | 2026-10-29",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-15"
    },
    {
      "id": "EVD-016",
      "kind": "document",
      "ref": "analysis/agy-image-input-fix/evidence-ledger.md#F-16",
      "claim": "В эталоне allowed читается из image_limits.max_types, тогда как текущий agy fleet задаёт types; прямой перенос lookup вернёт пустой allowlist. | server.py:693-718; bridges/agy-bridge/fleet.json:20-28 | 2026-10-29",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-16"
    },
    {
      "id": "EVD-017",
      "kind": "document",
      "ref": "analysis/agy-image-input-fix/evidence-ledger.md#F-17",
      "claim": "Эталон создаёт WORKSPACE/img-uuid, chmod 0700, файлы 0600 до попыток; ошибка spool имеет отдельный state. | server.py:4298-4334 | 2026-10-29",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-17"
    },
    {
      "id": "EVD-018",
      "kind": "document",
      "ref": "analysis/agy-image-input-fix/evidence-ledger.md#F-18",
      "claim": "Эталонный renderer создаёт сквозные [image N] и attachments с MIME, byte count, относительным путём и инструкцией Read; это инструмент другого моста. | core/tool_emulation.py:37-58,191-237 | 2026-10-29",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-18"
    },
    {
      "id": "EVD-019",
      "kind": "document",
      "ref": "analysis/agy-image-input-fix/evidence-ledger.md#F-19",
      "claim": "Эталонный HTTP handler ловит ImageReject и возвращает 400 с reason до backend preflight. | server.py:5240-5255 | 2026-10-29",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-19"
    },
    {
      "id": "EVD-020",
      "kind": "document",
      "ref": "analysis/agy-image-input-fix/evidence-ledger.md#F-20",
      "claim": "Strict image tests проверяют историю/раскладку, 16 изображений, image-only, taxonomy и лимиты. JPEG/GIF/WebP в PNG-only тестовом стенде ожидаемо отвергаются. | tests/test_images_strict.py:77-180,258-375 | 2026-10-29",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-20"
    },
    {
      "id": "EVD-021",
      "kind": "document",
      "ref": "analysis/agy-image-input-fix/evidence-ledger.md#F-21",
      "claim": "Strict tests проверяют cleanup success/exception/retries/client gone, proof по бинарю, impl_version, formats, effort и журнал без содержимого. Это тесты корневого моста, не доказательство agy. | tests/test_images_strict.py:377-555 | 2026-10-29",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-21"
    },
    {
      "id": "EVD-022",
      "kind": "document",
      "ref": "analysis/agy-image-input-fix/evidence-ledger.md#F-22",
      "claim": "_SECRET маскирует токены длиной от 24; allowlist содержит только sqlite_snapshot_divergence и sqlite_transcript_divergence. image_input_not_supported имеет 25 символов. | bridges/agy-bridge/server.py:230,453-470; Python len(\"image_input_not_supported\")=25 | 2026-10-29",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-22"
    },
    {
      "id": "EVD-023",
      "kind": "document",
      "ref": "analysis/agy-image-input-fix/evidence-ledger.md#F-23",
      "claim": "Контракт отказа: reject reason=<reason> model=<model> model_len=<N> client=<peer>; HTTP error содержит message,type,code. | bridges/agy-bridge/server.py:2411-2428 | 2026-10-29",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-23"
    },
    {
      "id": "EVD-024",
      "kind": "document",
      "ref": "analysis/agy-image-input-fix/evidence-ledger.md#F-24",
      "claim": "/health жёстко сообщает images=False и сохраняет native_tools=True, concurrency и hot_sessions. | bridges/agy-bridge/server.py:2875-2889 | 2026-10-29",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-24"
    },
    {
      "id": "EVD-025",
      "kind": "document",
      "ref": "analysis/agy-image-input-fix/evidence-ledger.md#F-25",
      "claim": "Runtime server.py и fleet.json в ~/.dsh/bridges/agy-bridge — существующие обычные файлы, не симлинки; LaunchAgent KeepAlive=True запускает /bin/bash и start.sh, cwd workspace, MAX_CONCURRENT=8 и QUEUE_TIMEOUT=1800. | read-only Python plistlib: ~/Library/LaunchAgents/com.user.dsh-agy-bridge.plist: ProgramArguments,WorkingDirectory,EnvironmentVariables; Path.is_symlink для runtime файлов | 2026-10-29",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-25"
    },
    {
      "id": "EVD-026",
      "kind": "document",
      "ref": "analysis/agy-image-input-fix/evidence-ledger.md#F-26",
      "claim": "Исходные default лимиты: concurrent=4, queue=900 s, execution=1800 s, first-token=120 s; session idle=2700 s, max age=86400 s, max turns=30; WORKSPACE=ROOT/workspace. | bridges/agy-bridge/server.py:89-107,189-193 | 2026-10-29",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-26"
    },
    {
      "id": "EVD-027",
      "kind": "document",
      "ref": "analysis/agy-image-input-fix/evidence-ledger.md#F-27",
      "claim": "Переданное живое доказательство: agy.real 1.4.9 через agy-cli.sh, PNG 1x1 68 bytes, --add-dir, gemini-4-argon effort low; conversation d6266547-4f77-4a4f-af67-b0ae1408a1fe, SUCCESS, 35.304594 s, нативный view_file прочитал изображение. В этом Stage 1 вызов не повторялся. | .ai-team/runs/agy-image-input-fix-20261029/briefs/analyst-01.md, раздел «Живое эмпирическое доказательство»; сообщение владельца 2026-10-29 | 2026-10-29",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-27"
    },
    {
      "id": "EVD-028",
      "kind": "document",
      "ref": "analysis/agy-image-input-fix/evidence-ledger.md#F-28",
      "claim": "Текущие 46 полей SSoT architecture.md таблицы 3.0 отличаются от 46 полей брифа. Образец предыдущего handoff содержит два отдельных набора. | ~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/architecture.md:111-165; analysis/agy-realtime-reasoning/handoff-architect.md, разделы 7.1 и 7.2 | 2026-10-29",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-28"
    },
    {
      "id": "EVD-029",
      "kind": "document",
      "ref": "analysis/agy-image-input-fix/evidence-ledger.md#F-29",
      "claim": "AGY resilience tests содержат сценарии resume, запрета cold retry после reasoning, фонового и plain session isolation, integer retry budget и health compatibility. | tests/test_agy_bridge_resilience.py:1601,1824-1833,1954-2010,2272,2763 | 2026-10-29",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-29"
    },
    {
      "id": "EVD-030",
      "kind": "document",
      "ref": "analysis/agy-image-input-fix/evidence-ledger.md#F-30",
      "claim": "Retry capacity=3 tokens, credit=0.2/request, cost=1/retry; pause cap=2 s. Это процессный бюджет, не фиксированные 100% повторов. | bridges/agy-bridge/server.py:168-178,2674,2755-2778 | 2026-10-29",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-30"
    },
    {
      "id": "EVD-031",
      "kind": "document",
      "ref": "analysis/agy-image-input-fix/evidence-ledger.md#F-31",
      "claim": "Бриф задаёт целевые лимиты: count=16, individual=20971520 bytes, total=20971520 bytes, HTTP=33554432 bytes и четыре MIME; это требования, не текущая конфигурация. | .ai-team/runs/agy-image-input-fix-20261029/briefs/analyst-01.md, RC-3; сообщение владельца | 2026-10-29",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-31"
    },
    {
      "id": "EVD-032",
      "kind": "document",
      "ref": "analysis/agy-image-input-fix/evidence-ledger.md#F-32",
      "claim": "Бриф передаёт сведения об agy.real parser image_url reject (offset 57498104), view_file/multimodal_view_file (55208733,56206397) и повторяемом --add-dir; бинарь в этом Stage 1 не разбирался. | .ai-team/runs/agy-image-input-fix-20261029/briefs/analyst-01.md, RC-1; ограниченное живое подтверждение F-27 | 2026-10-29",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-32"
    },
    {
      "id": "EVD-033",
      "kind": "document",
      "ref": "analysis/agy-image-input-fix/evidence-ledger.md#F-33",
      "claim": "Авторизация и размер body проверяются до image ветки; тело сверх max_body_bytes получает отдельный отказ, admission ограничивает число HTTP соединений. | bridges/agy-bridge/server.py:2940-2985,3290-3322 | 2026-10-29",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-33"
    },
    {
      "id": "EVD-034",
      "kind": "document",
      "ref": "analysis/agy-image-input-fix/evidence-ledger.md#F-34",
      "claim": "Назначенные пути и branch подтверждены: fix/agy-image-input-fix; до записи был untracked только текущий .ai-team run, analysis/agy-image-input-fix пуст. | git branch --show-current; git status --porcelain; ls -la analysis/agy-image-input-fix, выполнено 2026-10-29 | 2026-10-29",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-34"
    },
    {
      "id": "EVD-035",
      "kind": "document",
      "ref": "Owner Stage 2 brief §3 and §5, 2026-10-29",
      "claim": "Supplied binary SHA, host 18 cores/64 GiB, ephemeral 16384 ports, TIME_WAIT 30 s, shell ulimit 65536. These are supplied observations, not measurements repeated by Architect."
    },
    {
      "id": "EVD-036",
      "kind": "document",
      "ref": "analysis/agy-image-input-fix/handoff-architect.md §6; Stage 2 memory argument",
      "claim": "64 MiB HTTP body admission does not establish simultaneous Python RSS amplification bound: JSON strings, base64 strings, decoded images and queued requests can coexist. Clearing img[data] after slot acquisition does not bound pre-slot buffers. 176 MiB is an assumed design target pending RES-01, not proven strict upper bound."
    }
  ],
  "risk_triggers": [
    "trust-boundary",
    "external-attack-surface"
  ],
  "requirement_ids": [
    "REQ-001",
    "REQ-002",
    "REQ-003",
    "REQ-004",
    "REQ-005",
    "REQ-006",
    "REQ-007",
    "REQ-008",
    "REQ-009",
    "REQ-010"
  ],
  "requirements": [
    {
      "id": "REQ-001",
      "priority": "MUST",
      "statement": "Реализовать проверяемую capability workspace-read для целевых gemini-4-argon/gemini-3.8-flash согласованно в server/fleet/health; unsupported модели остаются text-only. Promotion confirmed допустим только с валидным proof; kill-switch default false и источник по канону согласуются до Coder.",
      "acceptance": "AC-001: при разрешённой и доказанной capability обе целевые модели принимают image-запрос; gpt-oss-120b возвращает 400 image_input_not_supported до spawn; выключение флага возвращает прежний image-отказ, текст успешен.",
      "evidence": "F-01, F-03, F-05, F-24, F-27",
      "decision_ids": [
        "AD-001"
      ],
      "verification_ids": [
        "VER-003",
        "VER-007",
        "VER-010"
      ]
    },
    {
      "id": "REQ-002",
      "priority": "MUST",
      "statement": "Единый MIME allowlist в validation/proof/fleet включает image/png,image/jpeg,image/gif,image/webp; не смешивать types/max_types. Лимиты count=16, per-image=20971520 B, total=20971520 B, body=33554432 B.",
      "acceptance": "AC-002: 1..16 валидных картинок четырёх MIME и смешанный набор принимаются в пределах суммы; count 17 и превышения на 1 B дают отдельные коды, body overflow даёт 413.",
      "evidence": "F-04, F-14..F-16, F-31",
      "decision_ids": [
        "AD-002"
      ],
      "verification_ids": [
        "VER-003",
        "VER-007"
      ]
    },
    {
      "id": "REQ-003",
      "priority": "MUST",
      "statement": "Ввести fail-closed ImageReject C-08..C-11 с проверкой capability/proof, формы/роли, data URL, строгой base64, сигнатуры/MIME и лимитов до spool/spawn.",
      "acceptance": "AC-003: все 9 image reason из QA возвращают HTTP 400 с точным type/message, ноль CLI spawn и ноль файлов при отказе; текст без images не деградирует при image proof mismatch.",
      "evidence": "F-14, F-15, F-19..F-21",
      "decision_ids": [
        "AD-002"
      ],
      "verification_ids": [
        "VER-003",
        "VER-007"
      ]
    },
    {
      "id": "REQ-004",
      "priority": "MUST",
      "statement": "Сохранить соответствие всех image-частей истории, markers и attachments на cold start, hot resume, explicit conversation и cold fallback; чисто текстовый следующий ход со старыми валидными image-частями не отвергать.",
      "acceptance": "AC-004: cold и hot сценарии «изображения → текст» успешны; новый image subset указывает на правильные байты, cold fallback читает все K файлов истории без повторного результата клиенту.",
      "evidence": "F-02, F-08..F-12, F-18",
      "decision_ids": [
        "AD-003"
      ],
      "verification_ids": [
        "VER-003",
        "VER-007",
        "VER-010"
      ]
    },
    {
      "id": "REQ-005",
      "priority": "MUST",
      "statement": "Не менять пользовательский cwd и sess_key ради изображений; предоставить каталог через --add-dir <img_dir>, attachments используют разрешимые абсолютные пути; инструкция native view_file вместо Read другого моста.",
      "acceptance": "AC-005: captured Popen cwd равен исходному проекту, sess_key идентичен, argv содержит отдельные --add-dir/path, native view_file открывает точный img-N при cwd с пробелами.",
      "evidence": "F-10, F-11, F-18, F-27, F-32",
      "decision_ids": [
        "AD-004"
      ],
      "verification_ids": [
        "VER-003",
        "VER-007",
        "VER-010"
      ]
    },
    {
      "id": "REQ-006",
      "priority": "MUST",
      "statement": "Материализовать только проверенные images в уникальный WORKSPACE/img-uuid, dir 0700/files 0600, сохранить их на всех попытках одного хода и удалить в finally после закрытия всех потребителей.",
      "acceptance": "AC-006: файл доступен в каждой попытке и отсутствует после success/error/exception/client disconnect; при частичной записи/ENOSPC нет утечки каталога, повторного spawn либо чужого удаления.",
      "evidence": "F-12, F-13, F-17, F-21",
      "decision_ids": [
        "AD-005"
      ],
      "verification_ids": [
        "VER-003",
        "VER-007"
      ]
    },
    {
      "id": "REQ-007",
      "priority": "MUST",
      "statement": "Сохранить строгий reject log-контракт, добавить канонические безопасные reason/event имена в _LOG_EVENT_NAMES без отключения secret masking.",
      "acceptance": "AC-007: каждый reason и image_proof_invalid/unsupported_reasoning_effort виден дословно в логах, секрет и длинная base64 контрольного запроса отсутствуют, строка reject соответствует строгому шаблону.",
      "evidence": "F-07, F-22, F-23",
      "decision_ids": [
        "AD-006"
      ],
      "verification_ids": [
        "VER-003",
        "VER-007"
      ]
    },
    {
      "id": "REQ-008",
      "priority": "SHOULD",
      "statement": "Расширить sweep на осиротевшие img-* старше 3600 s, не удаляя активные каталоги, свежие каталоги, чужие пути и цели симлинков.",
      "acceptance": "AC-008: контролируемые часы/mtime удаляют stale orphan, сохраняют active даже при возрасте >3600 s, fresh и symlink target; параллельные ходы не читают каталоги друг друга.",
      "evidence": "F-13, F-17, F-26",
      "decision_ids": [
        "AD-005"
      ],
      "verification_ids": [
        "VER-003",
        "VER-007"
      ]
    },
    {
      "id": "REQ-009",
      "priority": "MUST",
      "statement": "Сохранить text/SSE/reasoning, authentication, admission, таймауты, cancel и policy no-retry-after-delivery; ограничить image CPU/memory/disk без обхода текущих guardrails.",
      "acceptance": "AC-009: существующий agy resilience и image regression suite зелёные, delivered reasoning даёт 1 attempt, concurrency не выше configured limit; numeric memory/FD/CPU gate проверен до production promotion.",
      "evidence": "F-12, F-26, F-29, F-30, F-33",
      "decision_ids": [
        "AD-005"
      ],
      "verification_ids": [
        "VER-003",
        "VER-007"
      ]
    },
    {
      "id": "REQ-010",
      "priority": "MUST",
      "statement": "После downstream приёмки поставить оба файла в runtime-каталог с проверкой ревизий, перезапустить LaunchAgent, проверить рабочий DSH чат тяжёлым L3; предусмотреть возврат предыдущих server+fleet парой.",
      "acceptance": "AC-010: repo/runtime hashes совпадают для пары, :9887 после рестарта отдаёт актуальную capability, живые ход 1 с двумя различимыми images и ход 2 текст в том же чате успешны с evidence и cleanup.",
      "evidence": "F-01, F-07, F-25, F-27",
      "decision_ids": [
        "AD-001"
      ],
      "verification_ids": [
        "VER-003",
        "VER-007",
        "VER-010"
      ]
    }
  ],
  "decisions": [
    {
      "id": "AD-001",
      "status": "APPROVED",
      "kind": "two-way",
      "question": "Workspace-read capability, catalog v2, binary proof and independent kill-switch",
      "choice": "Workspace-read capability, catalog v2, binary proof and independent kill-switch",
      "alternatives": [
        "Direct image_url in NDJSON: rejected, parser incompatible F-06/F-32",
        "Hide DSH capability: rejects goal and expands scope"
      ],
      "drivers": [
        "REQ-001",
        "REQ-010"
      ],
      "consequences": [
        "Two-way rollback by image flag off, preserve text-only behavior; accepted image turn owns ephemeral files until terminal cleanup.",
        "Promotion and resource evidence required downstream; no runtime PASS inferred from schema validation."
      ],
      "approval_required": false,
      "evidence_ids": [
        "EVD-001",
        "EVD-003",
        "EVD-004",
        "EVD-005",
        "EVD-024",
        "EVD-027",
        "EVD-035"
      ],
      "confirmation": {
        "kind": "test",
        "command": "PYTHONPATH=. uvx --from pytest==9.0.3 pytest -q -p no:cacheprovider tests/test_agy_bridge_resilience.py",
        "expected": "AD-001 deterministic regression oracles pass plus required L2/L3 evidence before production"
      },
      "verification_ids": [
        "VER-003",
        "VER-007",
        "VER-010"
      ],
      "details": {
        "IMPLEMENTED_METHODS": {
          "workspace-read": 1
        },
        "METHOD_IMPL_VERSION": 1,
        "technical_ref": {
          "agy_version": "1.4.9",
          "agy_binary_path": "~/.local/bin/agy.real",
          "agy_binary_sha256": "35605054a9dc4591dd7e6ea83a9392238153d4c55d265512ed9b5b7f97cc0423"
        },
        "image_limits": {
          "max_images": 16,
          "max_image_bytes": 20971520,
          "max_total_image_bytes": 20971520,
          "max_body_bytes": 33554432,
          "types": [
            "image/png",
            "image/jpeg",
            "image/gif",
            "image/webp"
          ]
        },
        "target_models": {
          "gemini-4-argon": {
            "input": [
              "text",
              "image"
            ],
            "images": {
              "cli_registry": "implicit_supported",
              "status": "confirmed",
              "method": "workspace-read",
              "proof": {
                "agy_binary_sha256": "35605054a9dc4591dd7e6ea83a9392238153d4c55d265512ed9b5b7f97cc0423",
                "impl_version": 1,
                "formats": [
                  "image/png",
                  "image/jpeg",
                  "image/gif",
                  "image/webp"
                ],
                "efforts_proven": [
                  "low",
                  "medium",
                  "high"
                ],
                "verified_at": "2026-10-29"
              }
            }
          },
          "gemini-3.8-flash": {
            "input": [
              "text",
              "image"
            ],
            "images": {
              "cli_registry": "implicit_supported",
              "status": "confirmed",
              "method": "workspace-read",
              "proof": {
                "agy_binary_sha256": "35605054a9dc4591dd7e6ea83a9392238153d4c55d265512ed9b5b7f97cc0423",
                "impl_version": 1,
                "formats": [
                  "image/png",
                  "image/jpeg",
                  "image/gif",
                  "image/webp"
                ],
                "efforts_proven": [
                  "low",
                  "medium",
                  "high"
                ],
                "verified_at": "2026-10-29"
              }
            }
          }
        },
        "unsupported_models": {
          "gemini-3.7-flash": {
            "input": [
              "text"
            ],
            "images": {
              "status": "unsupported",
              "method": null
            }
          },
          "gemini-3.6-flash": {
            "input": [
              "text"
            ],
            "images": {
              "status": "unsupported",
              "method": null
            }
          },
          "gemini-3.1-pro": {
            "input": [
              "text"
            ],
            "images": {
              "status": "unsupported",
              "method": null
            }
          },
          "gpt-oss-120b": {
            "input": [
              "text"
            ],
            "images": {
              "status": "unsupported",
              "method": null
            }
          }
        },
        "promotion": "OPEN-02/09: target confirmed/proof entries above are desired post-verification state. Only F-27 PNG/Argon/low proven by supplied experiment; do not fabricate verification for other combinations. Keep disabled until 2 models × 3 efforts × 4 formats matrix passes L2/L3 and evidence recorded before production promotion; verified_at is verification date, update if later.",
        "proof_check": "_image_proof_reason(model, effort) returns nonempty reason on binary SHA mismatch, impl_version != 1, image_limits.types not subset of proof.formats, or effort absent from proof.efforts_proven. Log image_proof_invalid model=<id> reason=<subreason>; HTTP 400 image_input_not_supported, no spawn. Text-only bypasses proof.",
        "sha_algorithm": "_file_sha256(path): st=path.stat(); under _sha_cache_lock cache identity by path and (st.st_mtime_ns, st.st_size); hash via iter(lambda: f.read(1048576), b\"\") (1 MiB chunks), never read_bytes() on 193 MiB binary. Re-stat after hashing; if identity changed reject rather than cache stale digest. Hash once per unchanged binary.",
        "flag": {
          "key": "IMAGE_INPUT_ENABLED",
          "source": "dynamic_config.json",
          "default": false,
          "lock": "_sqlite_guard_lock",
          "stat_cache_ttl_s": 1.0,
          "invalid_policy": "absent/unreadable/invalid JSON/key not exactly true => False; not bool(value)",
          "emergency": "Immediately False if os.environ.get(\"AGY_IMAGE_INPUT_ENABLED\", \"1\").strip().lower() in (\"0\", \"false\", \"no\", \"off\") before using cached value",
          "independent": "Never reuse SQLITE_REASONING_ENABLED; share stat-cache refresh but store separate booleans",
          "production": "~/.dsh/bridges/agy-bridge/dynamic_config.json: IMAGE_INPUT_ENABLED=true alongside SQLITE_REASONING_ENABLED=true after matrix; local source explicitly authorized by Stage 2 brief instead of global GigaRC. Stat-cache TTL bounds next check to at most 1.0s, not strictly less than 1.0s; existing accepted turns finish/cleanup."
        },
        "health": {
          "images": "bool(_is_image_input_enabled() and any(m[\"images\"][\"status\"] == \"confirmed\" for m in FLEET[\"models\"].values()))",
          "image_input_mode": "enabled | disabled based on _is_image_input_enabled()"
        }
      }
    },
    {
      "id": "AD-002",
      "status": "APPROVED",
      "kind": "two-way",
      "question": "Fail-closed ordered validation and canonical image_limits.types",
      "choice": "Fail-closed ordered validation and canonical image_limits.types",
      "alternatives": [
        "Permissive URL fetch/base64 decode: unsafe and changes error contract",
        "Copy max_types lookup: empty allowed types F-16"
      ],
      "drivers": [
        "REQ-002",
        "REQ-003"
      ],
      "consequences": [
        "Two-way rollback by image flag off, preserve text-only behavior; accepted image turn owns ephemeral files until terminal cleanup.",
        "Promotion and resource evidence required downstream; no runtime PASS inferred from schema validation."
      ],
      "approval_required": false,
      "evidence_ids": [
        "EVD-014",
        "EVD-015",
        "EVD-016",
        "EVD-019",
        "EVD-020",
        "EVD-031",
        "EVD-033"
      ],
      "confirmation": {
        "kind": "test",
        "command": "PYTHONPATH=. uvx --from pytest==9.0.3 pytest -q -p no:cacheprovider tests/test_agy_bridge_resilience.py",
        "expected": "AD-002 deterministic regression oracles pass plus required L2/L3 evidence before production"
      },
      "verification_ids": [
        "VER-003",
        "VER-007",
        "VER-010"
      ],
      "details": {
        "entry": "_collect_images(request, model, effort)",
        "allowed": "allowed = [str(t).lower() for t in (limits.get(\"types\") or [])]; never max_types",
        "fast_path": "_collect_image_parts(messages) first; 0 image_url parts => [] with zero stat/hash/flag/uuid/disk/spawn image overhead",
        "ordered_validation": [
          "1 flag _is_image_input_enabled False => image_input_not_supported",
          "2 model images.status == confirmed OR status == probe and IMAGE_PROBE; else image_input_not_supported",
          "3 _image_proof_reason(model, effort) nonempty => log image_proof_invalid model=<id> reason=<subreason>, image_input_not_supported",
          "4 each part: role != user => invalid_image_content",
          "5 image_url not dict, url not nonempty str => invalid_image_content",
          "6 not url.startswith(\"data:\") => image_url_not_allowed",
          "7 _parse_data_url: missing comma/empty MIME/base64 absent from params => invalid_image_content",
          "8 MIME not KNOWN_IMAGE_MIMES => unsupported_image_type",
          "9 empty payload OR base64.b64decode(payload, validate=True) error => invalid_image_base64",
          "10 _sniff_image empty => unsupported_image_type; sniffed != declared MIME => image_type_mismatch; MIME not allowed => unsupported_image_type",
          "11 len(images)+1 > 16 => too_many_images",
          "12 len(data) > 20971520 => image_too_large",
          "13 total+len(data) > 20971520 => images_too_large"
        ],
        "sniff": {
          "png": "b\"\\x89PNG\\r\\n\\x1a\\n\" prefix",
          "jpeg": "b\"\\xff\\xd8\\xff\" prefix",
          "gif": "GIF87a or GIF89a prefix",
          "webp": "data[:4] == b\"RIFF\" and data[8:12] == b\"WEBP\""
        },
        "entry_shape": {
          "index": "1..K global traversal index",
          "msg_index": "0-based message index",
          "mime": "validated MIME",
          "data": "decoded bytes",
          "size": "len(data)",
          "name": "f\"img-{idx}.{ext}\"; ext png/jpg/gif/webp"
        },
        "errors": "ImageReject HTTP 400 error.message=\"image rejected: <reason>\", error.type=<reason>, error.code=400; before file materialization or CLI spawn. Feature/proof checks necessarily perform config/binary read I/O; per-part validation precedes spool I/O. HTTP auth/body/admission remain earlier 401/413/503.",
        "limits_scope": "All historical image parts count toward 16 and 20 MiB; strict magic sniff is not pixel decoding. No URL network fetch."
      }
    },
    {
      "id": "AD-003",
      "status": "APPROVED",
      "kind": "two-way",
      "question": "Global history indexing for cold/hot/explicit/fallback",
      "choice": "Global history indexing for cold/hot/explicit/fallback",
      "alternatives": [
        "Renumber hot subset locally: more mapping risk on fallback",
        "Stage only new images: missing full-history files on cold fallback"
      ],
      "drivers": [
        "REQ-004"
      ],
      "consequences": [
        "Two-way rollback by image flag off, preserve text-only behavior; accepted image turn owns ephemeral files until terminal cleanup.",
        "Promotion and resource evidence required downstream; no runtime PASS inferred from schema validation."
      ],
      "approval_required": false,
      "evidence_ids": [
        "EVD-008",
        "EVD-009",
        "EVD-010",
        "EVD-012",
        "EVD-018"
      ],
      "confirmation": {
        "kind": "test",
        "command": "PYTHONPATH=. uvx --from pytest==9.0.3 pytest -q -p no:cacheprovider tests/test_agy_bridge_resilience.py",
        "expected": "AD-003 deterministic regression oracles pass plus required L2/L3 evidence before production"
      },
      "verification_ids": [
        "VER-003",
        "VER-007",
        "VER-010"
      ],
      "details": {
        "indexing": "Global 1-Based History Indexing: every image_url in messages gets stable index 1..K, including images before last assistant.",
        "full": "_messages_to_prompt(messages, img_dir=None, images=None): replace every image part with [image N], preserve image-only user message (never drop/PONG), append all K attachments.",
        "resumed": "_get_resumed_turn_prompt(messages, img_dir=None, images=None): last_asst index or -1; render messages[last_asst+1:] with global indices (not local reindex); append only img.msg_index > last_asst. No assistant => render full history.",
        "attachment_template": "[attachments]\nThe user attached K image file(s) in the workspace directory (accessible via --add-dir). Open each with your view_file tool before answering:\n- [image 1] /abs/path/to/workspace/img-<uuid>/img-1.png (image/png, 68 bytes)",
        "history": "_collect_images validates ALL history each turn; enabled flag and valid capability/proof allow image→text turns. Turn 2 hot with no new images: only new text, no attachments; full prompt still has all historical images staged for cold/fallback. If flag disabled or proof invalid, history-containing requests fail closed; zero-image text-only unaffected.",
        "fallback": "Stage all K files once per HTTP turn before any attempt. On eligible hot failure before delivery: ctx[\"prompt\"]=ctx[\"full_prompt\"], clear cid, retry same img_dir. No retry after content/tool_calls/reasoning delivery. Explicit conversation_id branch handled independently from automatic hot_resumed; marker/file consistency in both."
      }
    },
    {
      "id": "AD-004",
      "status": "APPROVED",
      "kind": "two-way",
      "question": "--add-dir isolation while preserving cwd and session key",
      "choice": "--add-dir isolation while preserving cwd and session key",
      "alternatives": [
        "Set cwd=img_dir: breaks project paths and sess_key",
        "Embed bytes in NDJSON: parser incompatible"
      ],
      "drivers": [
        "REQ-005"
      ],
      "consequences": [
        "Two-way rollback by image flag off, preserve text-only behavior; accepted image turn owns ephemeral files until terminal cleanup.",
        "Promotion and resource evidence required downstream; no runtime PASS inferred from schema validation."
      ],
      "approval_required": false,
      "evidence_ids": [
        "EVD-010",
        "EVD-011",
        "EVD-027",
        "EVD-032"
      ],
      "confirmation": {
        "kind": "test",
        "command": "PYTHONPATH=. uvx --from pytest==9.0.3 pytest -q -p no:cacheprovider tests/test_agy_bridge_resilience.py",
        "expected": "AD-004 deterministic regression oracles pass plus required L2/L3 evidence before production"
      },
      "verification_ids": [
        "VER-003",
        "VER-007",
        "VER-010"
      ],
      "details": {
        "cwd": "Never replace cwd with img_dir; preserve sess_key=(model_id,cwd,effort) byte-for-byte.",
        "signature": "Run.__init__(..., img_dir: str | None = None)",
        "argv": "If img_dir nonempty append [\"--add-dir\", str(img_dir)] as discrete argv; shell=False; Popen(..., cwd=work_dir) remains user project or existing WORKSPACE fallback. Safe spaces/Unicode.",
        "native": "Only text NDJSON and native view_file; no image_url sent to CLI and no external tool emulation."
      }
    },
    {
      "id": "AD-005",
      "status": "APPROVED",
      "kind": "two-way",
      "question": "Ephemeral slot-bounded spool, active registry and orphan cleanup",
      "choice": "Ephemeral slot-bounded spool, active registry and orphan cleanup",
      "alternatives": [
        "Spool before slot: unbounded queued disk allocation",
        "Delete after each attempt: breaks retry and fallback"
      ],
      "drivers": [
        "REQ-006",
        "REQ-008",
        "REQ-009"
      ],
      "consequences": [
        "Two-way rollback by image flag off, preserve text-only behavior; accepted image turn owns ephemeral files until terminal cleanup.",
        "Promotion and resource evidence required downstream; no runtime PASS inferred from schema validation."
      ],
      "approval_required": false,
      "evidence_ids": [
        "EVD-012",
        "EVD-013",
        "EVD-017",
        "EVD-021",
        "EVD-025",
        "EVD-036"
      ],
      "confirmation": {
        "kind": "test",
        "command": "PYTHONPATH=. uvx --from pytest==9.0.3 pytest -q -p no:cacheprovider tests/test_agy_bridge_resilience.py",
        "expected": "AD-005 deterministic regression oracles pass plus required L2/L3 evidence before production"
      },
      "verification_ids": [
        "VER-003",
        "VER-007",
        "VER-010"
      ],
      "details": {
        "allocation": "If images nonempty pre-allocate img_dir=WORKSPACE / f\"img-{uuid.uuid4().hex}\" path only for prompt references; no mkdir in HTTP preparation.",
        "stage_location": "_run_once: after successful _acquire_slot() and before for attempt in range(max_attempts): call _stage_images(img_dir, images) once. 8 slots ×20 MiB =>160 MiB active disk spool excluding orphan backlog.",
        "registry": "Register str(img_dir) in _active_img_dirs under _active_lock BEFORE os.mkdir(img_dir, 0o700). Stage files os.open(path, os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600); close each descriptor before agy spawn. Clear img[\"data\"]=b\"\" immediately after writing; metadata size/MIME/name remains. Whole directory lifetime covers every retry.",
        "cleanup": "finally after all Run consumers closed: shutil.rmtree(img_dir, ignore_errors=True), then remove own str(img_dir) from active set under lock; always release slot. No-slot/launcher-unavailable/disconnect prior to staging: release request buffers and no filesystem artifact. Cleanup error must remain observable without leaking payload; orphan sweep recovers leftovers.",
        "spool_error": "OSError at mkdir/open/write/close => no CLI spawn, cleanup partial dir and active registry in finally; return state(\"image_spool_error\", \"image_spool_error\"), HTTP 500 image_spool_error.",
        "sweep": "_sweep_workspace(cutoff_s: float=3600.0): directories run-* and img-* only; skip entry.is_symlink(); never follow symlinks; skip paths in _active_img_dirs, even active >1h; remove only now - st_mtime > cutoff_s. Registry check and deletion selection must synchronize under _active_lock to avoid check/register race; staging registers before mkdir.",
        "memory": "No image descriptors remain open during agy run. Clear decoded refs before attempt loop. This alone does NOT prove decoded bytes <=20 MiB process-wide before slot: many requests validate/decode before acquiring slot. RES-01 must measure retained request/base64/JSON/decoded buffers incl waiters; failed bound blocks rollout without silently expanding scope."
      }
    },
    {
      "id": "AD-006",
      "status": "APPROVED",
      "kind": "two-way",
      "question": "Exact log token unmasking with strict secret masking",
      "choice": "Exact log token unmasking with strict secret masking",
      "alternatives": [
        "Disable masking: leaks secrets",
        "Keep current masking: reason=*** blocks diagnosis"
      ],
      "drivers": [
        "REQ-007"
      ],
      "consequences": [
        "Two-way rollback by image flag off, preserve text-only behavior; accepted image turn owns ephemeral files until terminal cleanup.",
        "Promotion and resource evidence required downstream; no runtime PASS inferred from schema validation."
      ],
      "approval_required": false,
      "evidence_ids": [
        "EVD-007",
        "EVD-022",
        "EVD-023"
      ],
      "confirmation": {
        "kind": "test",
        "command": "PYTHONPATH=. uvx --from pytest==9.0.3 pytest -q -p no:cacheprovider tests/test_agy_bridge_resilience.py",
        "expected": "AD-006 deterministic regression oracles pass plus required L2/L3 evidence before production"
      },
      "verification_ids": [
        "VER-003",
        "VER-007",
        "VER-010"
      ],
      "details": {
        "log_tokens": [
          "image_input_not_supported",
          "unsupported_reasoning_effort",
          "invalid_reasoning_effort",
          "unsupported_image_type",
          "invalid_image_content",
          "invalid_image_base64",
          "image_url_not_allowed",
          "image_type_mismatch",
          "image_proof_invalid",
          "images_too_large",
          "image_too_large",
          "too_many_images",
          "image_spool_error"
        ],
        "mask": "_SECRET = re.compile(r\"[A-Za-z0-9_\\-]{24,}\") remains active for all OTHER tokens. _LOG_EVENT_NAMES exact token allowlist only, not substring/prefix bypass.",
        "contract": "reject reason=<reason> model=<model> model_len=<N> client=<peer>; proof event image_proof_invalid model=<id> reason=<fixed subreason>; no prompt/data URL/base64/auth/image bytes. Logging failure cannot change successful model outcome."
      }
    }
  ],
  "verification_surface": [
    {
      "id": "VER-001",
      "requirement_ids": [
        "REQ-009"
      ],
      "kind": "command",
      "command": "uvx ruff@0.17.3 check --no-cache bridges/agy-bridge/server.py tests/test_agy_bridge_resilience.py",
      "expected": "exit 0; zero lint errors",
      "environment": "cwd=repo_root; pinned versions; clean-room no repo caches; not run during Stage 2",
      "owner": "Verifier"
    },
    {
      "id": "VER-002",
      "requirement_ids": [
        "REQ-009"
      ],
      "kind": "command",
      "command": "uvx ruff@0.17.3 format --check --no-cache bridges/agy-bridge/server.py tests/test_agy_bridge_resilience.py",
      "expected": "exit 0; format clean",
      "environment": "cwd=repo_root; pinned versions; clean-room no repo caches; not run during Stage 2",
      "owner": "Verifier"
    },
    {
      "id": "VER-003",
      "requirement_ids": [
        "REQ-009"
      ],
      "kind": "command",
      "command": "PYTHONPATH=. uvx --from pytest==9.0.3 pytest -q -p no:cacheprovider tests/test_agy_bridge_resilience.py",
      "expected": "exit 0; no failures",
      "environment": "cwd=repo_root; pinned versions; clean-room no repo caches; not run during Stage 2",
      "owner": "Verifier"
    },
    {
      "id": "VER-004",
      "requirement_ids": [
        "REQ-009"
      ],
      "kind": "command",
      "command": "uvx basedpyright@1.40.2 --outputjson bridges/agy-bridge/server.py tests/test_agy_bridge_resilience.py",
      "expected": "errorCount == 0 and 0 new warnings vs baseline 5a19559426de7508d525e2bd465eff648665a6a7 (compare multiset file/rule/message using same tool)",
      "environment": "cwd=repo_root; pinned versions; clean-room no repo caches; not run during Stage 2",
      "owner": "Verifier"
    },
    {
      "id": "VER-005",
      "requirement_ids": [
        "REQ-009"
      ],
      "kind": "command",
      "command": "PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /usr/bin/python3 -B -m unittest discover -s tests -p \"test_*agy*.py\"",
      "expected": "exit 0; full agy unittest suite passes",
      "environment": "cwd=repo_root; pinned versions; clean-room no repo caches; not run during Stage 2",
      "owner": "Verifier"
    },
    {
      "id": "VER-006",
      "requirement_ids": [
        "REQ-001",
        "REQ-002",
        "REQ-003",
        "REQ-004",
        "REQ-005",
        "REQ-006",
        "REQ-007",
        "REQ-008",
        "REQ-009",
        "REQ-010"
      ],
      "kind": "command",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B -c 'import subprocess; d=subprocess.check_output([\"git\",\"diff\",\"--numstat\",\"5a19559426de7508d525e2bd465eff648665a6a7\",\"--\",\"tests/test_agy_bridge_resilience.py\"],text=True).splitlines(); assert all(int(l.split()[1])==0 for l in d); subprocess.run([\"/usr/bin/python3\",\"-B\",\"-m\",\"unittest\",\"discover\",\"-s\",\"tests\",\"-p\",\"test_images_strict.py\"],check=True)'",
      "expected": "0 deleted test lines vs baseline; tests/test_images_strict.py passes",
      "environment": "cwd=repo_root; pinned versions; clean-room no repo caches; not run during Stage 2",
      "owner": "Teamlead"
    },
    {
      "id": "VER-007",
      "requirement_ids": [
        "REQ-001",
        "REQ-002",
        "REQ-003",
        "REQ-004",
        "REQ-005",
        "REQ-006",
        "REQ-007",
        "REQ-008",
        "REQ-009",
        "REQ-010"
      ],
      "kind": "command",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B -c 'import ast,re; from pathlib import Path; t=ast.parse(Path(\"tests/test_agy_bridge_resilience.py\").read_text()); expected={f\"{p}{i:02}\" for p,n in [(\"img\",10),(\"hist\",10),(\"life\",5),(\"log\",2),(\"res\",3),(\"ao\",10)] for i in range(1,n+1)}; found=set();\nfor f in ast.walk(t):\n if isinstance(f,(ast.FunctionDef,ast.AsyncFunctionDef)) and f.name.startswith(\"test_\") and any(isinstance(a,ast.Assert) or isinstance(a,ast.Call) and isinstance(a.func,ast.Attribute) and isinstance(a.func.value,ast.Name) and a.func.value.id==\"self\" and a.func.attr.startswith(\"assert\") for a in ast.walk(f)):\n  found.update(k for k in expected if re.search(r\"(?:^|_)\"+k+r\"(?:_|$)\",f.name))\nassert not expected-found,sorted(expected-found); print(\"QA_ASSERT_COVERAGE_PASS\",len(expected))'",
      "expected": "40 IDs img01..10/hist01..10/life01..05/log01..02/res01..03/ao01..10; each mapped test_* has assert or self.assert*",
      "environment": "cwd=repo_root; pinned versions; clean-room no repo caches; not run during Stage 2",
      "owner": "Teamlead"
    },
    {
      "id": "VER-008",
      "requirement_ids": [
        "REQ-001",
        "REQ-002",
        "REQ-003",
        "REQ-004",
        "REQ-005",
        "REQ-006",
        "REQ-007",
        "REQ-008",
        "REQ-009",
        "REQ-010"
      ],
      "kind": "command",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B -c 'import subprocess,hashlib; from pathlib import Path; b=\"5a19559426de7508d525e2bd465eff648665a6a7\"; expected={\"bridges/agy-bridge/fleet.json\",\"bridges/agy-bridge/server.py\",\"tests/test_agy_bridge_resilience.py\"}; names=subprocess.check_output([\"git\",\"diff\",\"--name-only\",b,\"HEAD\"],text=True).splitlines(); actual={n for n in names if not n.startswith((\".ai-team/\",\"analysis/\"))}; assert actual==expected,(actual,expected); tracked=subprocess.check_output([\"git\",\"ls-files\"],text=True).splitlines(); assert not any(Path(n).name==\"dynamic_config.json\" for n in tracked); frozen={'\"'\"'research-plan'\"'\"': '\"'\"'67f3bfffc4e9df6b95ee8571c34ded4a397ad164f86787b3b935fe51dcf1243a'\"'\"', '\"'\"'evidence-ledger'\"'\"': '\"'\"'aba34816b5cf6425d4fbf19187a09edd5f7158797e442d488d68626576f887a9'\"'\"', '\"'\"'open-questions'\"'\"': '\"'\"'63fe13ce25d80cb7bad68d25a57c8d1d6e58847b5b8be79dc395b555c55e5b76'\"'\"', '\"'\"'handoff-architect'\"'\"': '\"'\"'6c22f4a0ab4fc71d2e7cd88e1fe7d2df8c327193eb75bfc9d922af68a4710a8f'\"'\"', '\"'\"'handoff-qa'\"'\"': '\"'\"'007cdac728cdd6754c6617cd749ed3361f0d19c9e1adae16a3c31a90ee352cee'\"'\"'};\nfor n,h in frozen.items(): assert hashlib.sha256(Path(\"analysis/agy-image-input-fix\",n+\".md\").read_bytes()).hexdigest()==h,n\nprint(\"SCOPE_FROZEN_PASS\")'",
      "expected": "exact three product files in baseline..HEAD, no tracked dynamic_config.json, 5 frozen hashes pass",
      "environment": "cwd=repo_root; pinned versions; clean-room no repo caches; not run during Stage 2",
      "owner": "Teamlead"
    },
    {
      "id": "VER-009",
      "requirement_ids": [
        "REQ-001",
        "REQ-002",
        "REQ-003",
        "REQ-004",
        "REQ-005",
        "REQ-006",
        "REQ-007",
        "REQ-008",
        "REQ-009",
        "REQ-010"
      ],
      "kind": "command",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B -c 'import ast,sys; from pathlib import Path; s=Path(\"bridges/agy-bridge/server.py\").read_text(); t=ast.parse(s); allowed=set(getattr(sys,\"stdlib_module_names\",()))|{\"core\"}; assert allowed-{\"core\"},\"Use Python >=3.10 for stdlib inventory\"; roots={a.name.split(\".\")[0] for n in ast.walk(t) if isinstance(n,ast.Import) for a in n.names}|{n.module.split(\".\")[0] for n in ast.walk(t) if isinstance(n,ast.ImportFrom) and n.module}; assert roots<=allowed,roots-allowed; vals=[ast.literal_eval(n.value) for n in ast.walk(t) if isinstance(n,ast.Assign) and any(isinstance(a,ast.Name) and a.id==\"IMPLEMENTED_METHODS\" for a in n.targets)]; assert vals==[{\"workspace-read\":1}],vals; assert all(v in s for v in [\"IMAGE_INPUT_ENABLED\",\"AGY_IMAGE_INPUT_ENABLED\",\"--add-dir\"]); helpers={n.name:n for n in ast.walk(t) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}; todo=[n for n in helpers if \"image\" in n or \"data_url\" in n]; seen=set();\nwhile todo:\n n=todo.pop()\n if n in seen: continue\n seen.add(n); f=helpers[n]\n for a in ast.walk(f):\n  if isinstance(a,ast.Call):\n   name=ast.unparse(a.func); assert not any(v in name for v in [\"urlopen\",\"urlretrieve\",\"urllib.request\",\"http.client\",\"HTTPConnection\",\"HTTPSConnection\"]),name\n   if isinstance(a.func,ast.Name) and a.func.id in helpers: todo.append(a.func.id)\nprint(\"IMAGE_STDLIB_SECURITY_PASS\")'",
      "expected": "stdlib+core imports only, workspace-read v1, separate flags, --add-dir, no network image loaders; alias/manual AST review supplements closure",
      "environment": "cwd=repo_root; pinned versions; clean-room no repo caches; not run during Stage 2",
      "owner": "Verifier"
    },
    {
      "id": "VER-010",
      "requirement_ids": [
        "REQ-001",
        "REQ-002",
        "REQ-003",
        "REQ-004",
        "REQ-005",
        "REQ-006",
        "REQ-007",
        "REQ-008",
        "REQ-009",
        "REQ-010"
      ],
      "kind": "manual",
      "command": null,
      "expected": "Live :9887 existing owner conversation: Turn 1 two distinct real images, native view_file exact new paths and correct content; Turn 2 text-only same history/cid succeeds. Cold/hot/explicit/fallback and repeated/concurrent variants, all format/effort matrix, flag/proof regressions, cleanup and no crash. Hash deployed server/fleet pair; runtime flag true.",
      "environment": "Teamlead after ARCH_PANEL/code acceptance, deploy paired server.py/fleet.json to ~/.dsh/bridges/agy-bridge; enable IMAGE_INPUT_ENABLED in runtime dynamic_config.json only; 127.0.0.1:9887",
      "owner": "Teamlead"
    }
  ],
  "quality_scenarios": [
    {
      "id": "QA-001",
      "quality": "compatibility",
      "source": "DSH/Verifier/Teamlead",
      "stimulus": "Image capability enabled/disabled and binary/effort proof matrix",
      "environment": "flag/proof valid unless negative test; production-sized history; fake clocks for deterministic unit tests",
      "artifact": "bridges/agy-bridge/server.py + fleet.json",
      "response": "Confirmed valid image succeeds; unsupported/proof mismatch => 400, text-only succeeds",
      "response_measure": "0 spawns/files on rejects; flag absent/error false, TTL <=1.0s; no reused SQLite flag",
      "verification_ids": [
        "VER-003",
        "VER-007",
        "VER-010"
      ]
    },
    {
      "id": "QA-002",
      "quality": "security",
      "source": "DSH/Verifier/Teamlead",
      "stimulus": "Strict MIME/base64/count/body boundary matrix",
      "environment": "flag/proof valid unless negative test; production-sized history; fake clocks for deterministic unit tests",
      "artifact": "bridges/agy-bridge/server.py + fleet.json",
      "response": "Deterministic taxonomy per AD-002 with canonical types",
      "response_measure": "1..16 images, 20 MiB total, four MIME; +1 limits and 17 images reject; body >32 MiB 413",
      "verification_ids": [
        "VER-003",
        "VER-007"
      ]
    },
    {
      "id": "QA-003",
      "quality": "security",
      "source": "DSH/Verifier/Teamlead",
      "stimulus": "Role/shape/data URL invalid or mismatched signature",
      "environment": "flag/proof valid unless negative test; production-sized history; fake clocks for deterministic unit tests",
      "artifact": "bridges/agy-bridge/server.py + fleet.json",
      "response": "No fetch or materialization before accepted validation",
      "response_measure": "All 9 ImageReject codes exact; 0 files/spawns on reject",
      "verification_ids": [
        "VER-003",
        "VER-007"
      ]
    },
    {
      "id": "QA-004",
      "quality": "reliability",
      "source": "DSH/Verifier/Teamlead",
      "stimulus": "Full history cold/hot/explicit cid/hot-to-cold fallback",
      "environment": "flag/proof valid unless negative test; production-sized history; fake clocks for deterministic unit tests",
      "artifact": "bridges/agy-bridge/server.py + fleet.json",
      "response": "Global markers and exact byte/mime bijection; image-only preserved",
      "response_measure": "HIST-01..10; no attachments for text-only hot slice; all K files available to cold retry",
      "verification_ids": [
        "VER-003",
        "VER-007",
        "VER-010"
      ]
    },
    {
      "id": "QA-005",
      "quality": "compatibility",
      "source": "DSH/Verifier/Teamlead",
      "stimulus": "User project path with spaces/Unicode and relative file",
      "environment": "flag/proof valid unless negative test; production-sized history; fake clocks for deterministic unit tests",
      "artifact": "bridges/agy-bridge/server.py + fleet.json",
      "response": "Keep cwd/session key and native view_file via --add-dir",
      "response_measure": "Captured argv discrete pair; cwd and sess_key identical; relative project read still succeeds",
      "verification_ids": [
        "VER-003",
        "VER-007",
        "VER-010"
      ]
    },
    {
      "id": "QA-006",
      "quality": "privacy",
      "source": "DSH/Verifier/Teamlead",
      "stimulus": "success/error/exception/disconnect/partial ENOSPC/retry",
      "environment": "flag/proof valid unless negative test; production-sized history; fake clocks for deterministic unit tests",
      "artifact": "bridges/agy-bridge/server.py + fleet.json",
      "response": "Files stay through attempts then cleaned after readers/process closed",
      "response_measure": "dir 0700/files0600; open image FDs during run=0; no partial spawn; active set empty after exit",
      "verification_ids": [
        "VER-003",
        "VER-007"
      ]
    },
    {
      "id": "QA-007",
      "quality": "operability",
      "source": "DSH/Verifier/Teamlead",
      "stimulus": "All canonical rejects and synthetic long auth/base64 tokens",
      "environment": "flag/proof valid unless negative test; production-sized history; fake clocks for deterministic unit tests",
      "artifact": "bridges/agy-bridge/server.py + fleet.json",
      "response": "Exact safe diagnostic names, secret masking preserved",
      "response_measure": "LOG-01 strict regex; LOG-02 no token/base64/image bytes in any log sink",
      "verification_ids": [
        "VER-003",
        "VER-007"
      ]
    },
    {
      "id": "QA-008",
      "quality": "safety",
      "source": "DSH/Verifier/Teamlead",
      "stimulus": "Sweep stale/fresh/exact threshold/symlink/active old directory",
      "environment": "flag/proof valid unless negative test; production-sized history; fake clocks for deterministic unit tests",
      "artifact": "bridges/agy-bridge/server.py + fleet.json",
      "response": "Only orphan img-/run- strictly older than cutoff removed",
      "response_measure": "LIFE-05 FakeClock; active >3600s and symlink target unchanged; concurrent turn isolated",
      "verification_ids": [
        "VER-003",
        "VER-007"
      ]
    },
    {
      "id": "QA-009",
      "quality": "performance",
      "source": "DSH/Verifier/Teamlead",
      "stimulus": "8 concurrent image turns and queued requests under HTTP admission",
      "environment": "flag/proof valid unless negative test; production-sized history; fake clocks for deterministic unit tests",
      "artifact": "bridges/agy-bridge/server.py + fleet.json",
      "response": "Bound disk, profile total parent RSS plus children separately, FD and CPU",
      "response_measure": "RES-01 measured budgets incl queued JSON/base64/decoded copies; 160MiB active spool; assumed 176MiB parent RSS must be demonstrated, else block",
      "verification_ids": [
        "VER-003",
        "VER-007",
        "VER-010"
      ]
    },
    {
      "id": "QA-010",
      "quality": "testability",
      "source": "DSH/Verifier/Teamlead",
      "stimulus": "Paired runtime deployment and original owner chat image→text",
      "environment": "flag/proof valid unless negative test; production-sized history; fake clocks for deterministic unit tests",
      "artifact": "bridges/agy-bridge/server.py + fleet.json",
      "response": "Live correct native vision and text continuation; rollback possible",
      "response_measure": "AC-010 real :9887 same chat; model/effort/format matrix; source/runtime hashes; repeat/concurrent and crash report check",
      "verification_ids": [
        "VER-003",
        "VER-007",
        "VER-010"
      ]
    }
  ],
  "boundaries": [
    {
      "id": "BND-001",
      "component": "Handler / ingress and ImageReject",
      "responsibility": "Auth/admission/body first; global collection and ordered validation; map exact error; no spool before slot",
      "allowed_dependencies": [
        "fleet limits",
        "_collect_images",
        "prompt renderers",
        "_run_once"
      ],
      "forbidden_dependencies": [
        "network image fetch",
        "payload logs",
        "cwd mutation"
      ],
      "verification_ids": [
        "VER-003",
        "VER-009",
        "VER-010"
      ]
    },
    {
      "id": "BND-002",
      "component": "Fleet v2 and proof/flag readers",
      "responsibility": "Catalog capability tied to binary/method/formats/effort; independent default-false image flag",
      "allowed_dependencies": [
        "dynamic_config stat cache under _sqlite_guard_lock",
        "chunked SHA under _sha_cache_lock"
      ],
      "forbidden_dependencies": [
        "trust raw unverified matrix as evidence",
        "load 193MiB binary in heap",
        "reuse SQLite flag"
      ],
      "verification_ids": [
        "VER-003",
        "VER-009",
        "VER-010"
      ]
    },
    {
      "id": "BND-003",
      "component": "Full/resumed prompt renderer",
      "responsibility": "One global index source; full all K and resumed subset with absolute attachment paths",
      "allowed_dependencies": [
        "validated image metadata",
        "messages",
        "img_dir path"
      ],
      "forbidden_dependencies": [
        "disk writes",
        "renumbering hot subset",
        "drop image-only message"
      ],
      "verification_ids": [
        "VER-003",
        "VER-009",
        "VER-010"
      ]
    },
    {
      "id": "BND-004",
      "component": "Run process boundary",
      "responsibility": "Text NDJSON, discrete --add-dir argv; user cwd unchanged; existing cid/session contract",
      "allowed_dependencies": [
        "launcher",
        "Popen",
        "native agy view_file"
      ],
      "forbidden_dependencies": [
        "direct image_url stdin",
        "DSH tool emulation",
        "img_dir as cwd/sess_key"
      ],
      "verification_ids": [
        "VER-003",
        "VER-009",
        "VER-010"
      ]
    },
    {
      "id": "BND-005",
      "component": "_run_once spool/active registry/sweep",
      "responsibility": "Slot acquired before staging; stage once; keep files for retries; terminal cleanup after consumers; orphan sweep skips active/symlinks",
      "allowed_dependencies": [
        "os.mkdir/os.open",
        "shutil.rmtree",
        "_active_lock",
        "_active_img_dirs"
      ],
      "forbidden_dependencies": [
        "per-attempt deletion",
        "sweep active path",
        "follow symlinks",
        "spool before slot"
      ],
      "verification_ids": [
        "VER-003",
        "VER-009",
        "VER-010"
      ]
    },
    {
      "id": "BND-006",
      "component": "Logging and runtime promotion",
      "responsibility": "Exact safe event allowlist; preserve _SECRET; Teamlead paired deployment and live L3",
      "allowed_dependencies": [
        "fixed reason codes",
        "health additive fields",
        "frozen Verifier gates"
      ],
      "forbidden_dependencies": [
        "log keys/base64/prompts",
        "deploy by Architect",
        "claim panel PASS without proof"
      ],
      "verification_ids": [
        "VER-003",
        "VER-009",
        "VER-010"
      ]
    }
  ],
  "contract_deltas": [
    {
      "id": "CD-001",
      "type": "data",
      "producer": "fleet v2",
      "consumer": "catalog consumers",
      "change": "Two multimodal models workspace-read confirmed only after matrix; four MIME limits and binary proof; other four text-only",
      "compatibility": "schema_version 2 unchanged, proof structured as specified; default-disabled before promotion",
      "verification_ids": [
        "VER-003",
        "VER-007",
        "VER-010"
      ]
    },
    {
      "id": "CD-002",
      "type": "behavior",
      "producer": "HTTP image ingress",
      "consumer": "DSH",
      "change": "Accept verified data URL images; fail-closed nine reason taxonomy; image history no longer blanket-rejected",
      "compatibility": "JSON/SSE/auth/admission/no-retry-after-delivery unchanged; zero-image text bypass",
      "verification_ids": [
        "VER-003",
        "VER-007",
        "VER-010"
      ]
    },
    {
      "id": "CD-003",
      "type": "api",
      "producer": "/health",
      "consumer": "operators",
      "change": "images bool formula and additive image_input_mode enabled|disabled",
      "compatibility": "Preserve native_tools/concurrency/hot_sessions and existing reasoning fields",
      "verification_ids": [
        "VER-003",
        "VER-007",
        "VER-010"
      ]
    },
    {
      "id": "CD-004",
      "type": "behavior",
      "producer": "prompt + Run argv",
      "consumer": "agy 1.4.9 native view_file",
      "change": "Global [image N], attachment paths; --add-dir exact path; user cwd and sess_key unchanged",
      "compatibility": "Full/resumed/explicit/fallback have consistent mapping; no raw image_url NDJSON",
      "verification_ids": [
        "VER-003",
        "VER-007",
        "VER-010"
      ]
    },
    {
      "id": "CD-005",
      "type": "event",
      "producer": "logger",
      "consumer": "operator",
      "change": "Safe image reason/events unmasked and image_spool_error 500",
      "compatibility": "Only exact predefined tokens escape _SECRET; no payload logging",
      "verification_ids": [
        "VER-003",
        "VER-007",
        "VER-010"
      ]
    }
  ],
  "views": [
    {
      "id": "VIEW-001",
      "type": "context",
      "question": "Who crosses image trust boundaries?",
      "artifact_ref": "architecture/architecture-packet.json#boundaries",
      "diagram": "graph LR; DSH-->|loopback Bearer HTTP :9887 messages|Bridge; Bridge-->|text NDJSON and add-dir|Agy; Agy-->|native view_file|Spool; Bridge-->|SSE or JSON|DSH"
    },
    {
      "id": "VIEW-002",
      "type": "container",
      "question": "Where are state, private files and runtime controls?",
      "artifact_ref": "architecture/architecture-packet.json#decisions",
      "diagram": "graph LR; Handler-->Validation; Fleet-->Validation; Flag-->Validation; Validation-->Render; Render-->Slots; Slots-->Spool; Spool-->Run; Run-->Agy; Registry-->Sweep; Run-->Cleanup"
    },
    {
      "id": "VIEW-003",
      "type": "dynamic",
      "question": "How do hot resume and cold fallback preserve history?",
      "artifact_ref": "architecture/architecture-packet.json#decisions/AD-003",
      "sequence": [
        "collect ALL K",
        "allocate path only",
        "full all K + resumed subset retaining global indices",
        "acquire slot",
        "stage ALL K once and clear data refs",
        "hot attempt subset",
        "pre-delivery failure and token => cold full prompt same files",
        "close all consumers",
        "cleanup/release"
      ]
    },
    {
      "id": "VIEW-004",
      "type": "deployment",
      "question": "How is repo candidate promoted and rolled back?",
      "artifact_ref": "architecture/architecture-packet.json#evolution",
      "sequence": [
        "ARCH_PANEL proof by parent",
        "Coder red→green",
        "Verifier and Teamlead gates incl memory/matrix",
        "backup runtime pair",
        "deploy server+fleet paired hashes",
        "enable runtime image flag",
        "restart and L3 existing chat",
        "flag false and restore pair on FAIL"
      ]
    }
  ],
  "risks": [
    {
      "id": "RISK-001",
      "scenario": "Unverified model/effort/format falsely promoted",
      "probability": "medium",
      "impact": "high",
      "mitigation": "matrix evidence required before confirmed production; supplied F-27 proves PNG Argon low only",
      "verification_ids": [
        "VER-003",
        "VER-007",
        "VER-010"
      ]
    },
    {
      "id": "RISK-002",
      "scenario": "Auto-update changes binary identity",
      "probability": "medium",
      "impact": "medium",
      "mitigation": "chunked SHA identity cache + proof fail-closed images; text-only bypass",
      "verification_ids": [
        "VER-003",
        "VER-007",
        "VER-010"
      ]
    },
    {
      "id": "RISK-003",
      "scenario": "types/max_types drift",
      "probability": "medium",
      "impact": "medium",
      "mitigation": "single types lookup collector/proof/fleet and AST/regression",
      "verification_ids": [
        "VER-003",
        "VER-007",
        "VER-010"
      ]
    },
    {
      "id": "RISK-004",
      "scenario": "Base64/JSON/decoded concurrent amplification exceeds parent RSS",
      "probability": "medium",
      "impact": "high",
      "mitigation": "RES-01 include queued requests and max-sized bodies; 176MiB target is unproven; no production on exceeded/unknown bound",
      "verification_ids": [
        "VER-003",
        "VER-007",
        "VER-010"
      ]
    },
    {
      "id": "RISK-005",
      "scenario": "Historical marker misalignment on resume",
      "probability": "medium",
      "impact": "medium",
      "mitigation": "global 1..K + msg_index filter; distinct-image fixtures HIST-01..05",
      "verification_ids": [
        "VER-003",
        "VER-007",
        "VER-010"
      ]
    },
    {
      "id": "RISK-006",
      "scenario": "Cold fallback references unmaterialized history",
      "probability": "medium",
      "impact": "medium",
      "mitigation": "stage all K once before attempts and retain same directory until all attempts closed",
      "verification_ids": [
        "VER-003",
        "VER-007",
        "VER-010"
      ]
    },
    {
      "id": "RISK-007",
      "scenario": "Spool path replaces cwd/session identity",
      "probability": "medium",
      "impact": "medium",
      "mitigation": "Run argv only --add-dir; capture cwd and key; HIST-09/10",
      "verification_ids": [
        "VER-003",
        "VER-007",
        "VER-010"
      ]
    },
    {
      "id": "RISK-008",
      "scenario": "ENOSPC/permission partial spool",
      "probability": "medium",
      "impact": "high",
      "mitigation": "O_EXCL files + 0700/0600 + finally cleanup and image_spool_error 500 with 0 spawns",
      "verification_ids": [
        "VER-003",
        "VER-007",
        "VER-010"
      ]
    },
    {
      "id": "RISK-009",
      "scenario": "Sweep deletes active old turn or symlink target",
      "probability": "medium",
      "impact": "high",
      "mitigation": "active registry before mkdir; locked check; skip symlinks and strict cutoff; LIFE-05",
      "verification_ids": [
        "VER-003",
        "VER-007",
        "VER-010"
      ]
    },
    {
      "id": "RISK-010",
      "scenario": "Retry or disconnect premature cleanup",
      "probability": "medium",
      "impact": "medium",
      "mitigation": "outer finally only after consumers close; no retry after delivered content/tool/reasoning",
      "verification_ids": [
        "VER-003",
        "VER-007",
        "VER-010"
      ]
    },
    {
      "id": "RISK-011",
      "scenario": "Logging leaks tokens/payload after unmasking",
      "probability": "medium",
      "impact": "high",
      "mitigation": "exact token allowlist and unchanged _SECRET; LOG-01/02",
      "verification_ids": [
        "VER-003",
        "VER-007",
        "VER-010"
      ]
    },
    {
      "id": "RISK-012",
      "scenario": "Repo/runtime version mismatch and old hot slots",
      "probability": "medium",
      "impact": "medium",
      "mitigation": "paired hashes/backup/restart + same existing chat L3; inspect old slots and cache effects",
      "verification_ids": [
        "VER-003",
        "VER-007",
        "VER-010"
      ]
    },
    {
      "id": "RISK-013",
      "scenario": "Feature flag source/TTL or malformed config enables images",
      "probability": "medium",
      "impact": "medium",
      "mitigation": "local dynamic_config explicitly authorized here, independent key default false, exact true only, TTL<=1.0s; emergency env before cache; runtime no-restart test",
      "verification_ids": [
        "VER-003",
        "VER-007",
        "VER-010"
      ]
    },
    {
      "id": "RISK-014",
      "scenario": "Resource claim and admission boundary not mathematically closed",
      "probability": "medium",
      "impact": "high",
      "mitigation": "Arithmetic 208<=409.6 is conditional; queued decoded buffers outside slots can persist. Parent RSS ceiling, CPU/RPS/FD and launchd limit require measured obligations; retain rollout blocker instead of inventing strict proof",
      "verification_ids": [
        "VER-003",
        "VER-007",
        "VER-010"
      ]
    }
  ],
  "threat_model": {
    "required": true,
    "assets": [
      "user image bytes and prompt history",
      "Bearer/API key",
      "owner project files and cwd/session identity",
      "private ephemeral spool",
      "bridge availability"
    ],
    "trust_boundaries": [
      "DSH HTTP untrusted messages → authenticated bridge",
      "data URL → decoded bytes → private files",
      "bridge argv → native agy view_file",
      "workspace/active registry → orphan sweeper",
      "diagnostics → logs"
    ],
    "threats": [
      {
        "id": "THREAT-001",
        "scenario": "SSRF/LFI via image URL",
        "mitigation": "Only data: URL accepted, no network/file URL fetch; strict role/shape; zero spawns on reject",
        "verification_ids": [
          "VER-003",
          "VER-007",
          "VER-009",
          "VER-010"
        ]
      },
      {
        "id": "THREAT-002",
        "scenario": "Memory/disk DoS via image counts/bytes/concurrent decode",
        "mitigation": "32MiB body, 64MiB admission, 16 images/20MiB total; slots before disk; RES-01 unproven memory amplification blocks promotion",
        "verification_ids": [
          "VER-003",
          "VER-007",
          "VER-009",
          "VER-010"
        ]
      },
      {
        "id": "THREAT-003",
        "scenario": "Symlink/path collision or cross-turn reads",
        "mitigation": "UUID dir, constant generated names, 0700/0600 O_EXCL, active registry; no traversal from user names; skip symlinks on sweep",
        "verification_ids": [
          "VER-003",
          "VER-007",
          "VER-009",
          "VER-010"
        ]
      },
      {
        "id": "THREAT-004",
        "scenario": "Secret/payload exfiltration via logs",
        "mitigation": "_SECRET exact allowlisted reason tokens only; never bodies/base64/auth/full prompts",
        "verification_ids": [
          "VER-003",
          "VER-007",
          "VER-009",
          "VER-010"
        ]
      },
      {
        "id": "THREAT-005",
        "scenario": "Capability/proof tampering or stale binary validation",
        "mitigation": "default false independent flag; per-image-path proof model/effort/formats/version/binary identity checks; mismatch image-only fail closed",
        "verification_ids": [
          "VER-003",
          "VER-007",
          "VER-009",
          "VER-010"
        ]
      }
    ]
  },
  "assumptions": [
    {
      "id": "ASM-001",
      "source_open_ids": "OPEN-02/09",
      "statement": "Only PNG/Argon/low experiment currently supplied; full 24 combination matrix remains pre-promotion obligation, target proof not observation.",
      "status": "ASSUMED",
      "evidence_ids": [
        "EVD-027"
      ]
    },
    {
      "id": "ASM-002",
      "source_open_ids": "OPEN-04",
      "statement": "Global history indices chosen; new turn rematerializes history, hot subset lists only new images.",
      "status": "ASSUMED",
      "evidence_ids": [
        "EVD-009",
        "EVD-012",
        "EVD-018"
      ]
    },
    {
      "id": "ASM-003",
      "source_open_ids": "OPEN-05",
      "statement": "Host observations from owner:18 cores/64GiB/16384ports/TIME_WAIT30s/shell ulimit65536; launchd limit separately verify.",
      "status": "ASSUMED",
      "evidence_ids": [
        "EVD-035"
      ]
    },
    {
      "id": "ASM-004",
      "source_open_ids": "OPEN-05",
      "statement": "512MiB budget,176MiB worker RSS,32MiB shared are design targets; 64MiB body admission does not prove actual memory upper bound.",
      "status": "ASSUMED",
      "evidence_ids": [
        "EVD-036"
      ]
    },
    {
      "id": "ASM-005",
      "source_open_ids": "OPEN-07",
      "statement": "Explicit Stage 2 local dynamic_config flag instruction resolves source choice for this run; separate IMAGE_INPUT_ENABLED default false, no GigaRC connectivity asserted.",
      "status": "ASSUMED",
      "evidence_ids": [
        "EVD-035"
      ]
    },
    {
      "id": "ASM-006",
      "source_open_ids": "OPEN-10",
      "statement": "Teamlead deploys paired files and validates existing conversation only after all downstream gates.",
      "status": "ASSUMED",
      "evidence_ids": [
        "EVD-025"
      ]
    },
    {
      "id": "ASM-007",
      "source_open_ids": "OPEN-11",
      "statement": "Desktop evidence does not prove headless/web or all native decoder combinations; no expansion claimed.",
      "status": "ASSUMED",
      "evidence_ids": [
        "EVD-027",
        "EVD-032"
      ]
    },
    {
      "id": "ASM-008",
      "source_open_ids": "OPEN-05",
      "statement": "RPS6, CPU allocation2cores, u_bg0.12,FD132,p99 target1800s are planning budgets/assumptions, not fresh measurements. CPU18 hardware fact does not reserve cores; 1800 execution timeout not empirical p99.",
      "status": "ASSUMED",
      "evidence_ids": [
        "EVD-026",
        "EVD-035"
      ]
    }
  ],
  "drivers": [
    "DSH advertises two multimodal models but runtime blanket-rejects images",
    "Historical images poison later text turn",
    "Preserve cwd, session identity, native tools, public framing and strict secret policy",
    "No unverified production promotion or resource claim"
  ],
  "evolution": {
    "compatibility": "Add image path under default-false flag; preserve zero-image text, SSE, reasoning, sessions, auth/admission. Mixed history still requires flag/proof when images present.",
    "migration": "No database migration/new dependency. fleet v2 metadata and three product target files only. Runtime dynamic_config.json never tracked.",
    "rollout": "Parent ARCH_PANEL proof → Coder red→green → all pinned gates → measured resource closure incl queued bodies → full format/model/effort matrix → paired runtime hashes/backup → flag true and restart → existing Desktop two-image/text L3. Every stage needs real evidence, not packet status.",
    "rollback": "Set IMAGE_INPUT_ENABLED=false; new image requests fail within next cache refresh <=1.0s, emergency env false plus restart if needed. Text with zero images continues. Restore server+fleet previous pair, kickstart after accepted turns handled, verify real text turn; sweep orphan files. History containing images rejects while flag disabled.",
    "feature_flag": {
      "key": "IMAGE_INPUT_ENABLED",
      "source": "dynamic_config.json",
      "default": false,
      "lock": "_sqlite_guard_lock",
      "stat_cache_ttl_s": 1.0,
      "invalid_policy": "absent/unreadable/invalid JSON/key not exactly true => False; not bool(value)",
      "emergency": "Immediately False if os.environ.get(\"AGY_IMAGE_INPUT_ENABLED\", \"1\").strip().lower() in (\"0\", \"false\", \"no\", \"off\") before using cached value",
      "independent": "Never reuse SQLITE_REASONING_ENABLED; share stat-cache refresh but store separate booleans",
      "production": "~/.dsh/bridges/agy-bridge/dynamic_config.json: IMAGE_INPUT_ENABLED=true alongside SQLITE_REASONING_ENABLED=true after matrix; local source explicitly authorized by Stage 2 brief instead of global GigaRC. Stat-cache TTL bounds next check to at most 1.0s, not strictly less than 1.0s; existing accepted turns finish/cleanup."
    },
    "mixed_version": "No source/runtime proof assumed from git diff; pair hashes mandatory; old cid caches and concurrent processes verified in L3.",
    "agy_version_pin": "1.4.9 sha256 35605054a9dc4591dd7e6ea83a9392238153d4c55d265512ed9b5b7f97cc0423"
  },
  "approval": {
    "status": "APPROVED",
    "decision_ids": [],
    "approved_by": null,
    "evidence_ref": "Owner Stage 2 Role Brief §3",
    "rationale": "All AD two-way and no human one-way approval required; APPROVED means proposed design finalized for downstream panel, not external panel vote or runtime acceptance."
  },
  "independent_review": {
    "required": false,
    "status": "NOT_REQUIRED",
    "reviewer": null,
    "evidence_ref": null,
    "rationale": "S2 internal schema review optional; mandatory downstream 3-family ARCH_PANEL owned by parent, not simulated here."
  },
  "open_questions": [
    {
      "id": "Q-001",
      "blocking": false,
      "question": "Does measured parent RSS including queued pre-slot decoded requests fit 176MiB and closure under 512MiB?",
      "disposition": "Not a design handoff question; blocking pre-promotion obligation RISK-004/014 RES-01; cannot be marked verified by arithmetic."
    },
    {
      "id": "Q-002",
      "blocking": false,
      "question": "Are all 24 model/effort/format combinations verified?",
      "disposition": "L2/L3 obligation before production confirmed; supplied proof is only one combination."
    }
  ],
  "protected_paths": [
    "analysis/agy-image-input-fix/",
    "core/",
    "server.py",
    "other bridges",
    "dynamic_config.json"
  ],
  "materialization": [],
  "deferred": [],
  "high_load_envelope": {
    "schema": "HL-ENV/v1",
    "ssot": "~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/architecture.md §3.0/§7.2",
    "field_count": 46,
    "units": "s, cores, MiB, req/s, conn/s, descriptors, ports, tokens",
    "contour": "Local LaunchAgent one logical pod; W=1 process with threads and up to8 CLI children; parent RSS closure excludes child memory and must profile children separately.",
    "required_hl_env_fields": {
      "P_steady": 1,
      "P_hpa_max": 1,
      "maxSurge_pct": 0.0,
      "maxSurge_abs": 0,
      "maxUnavailable_pct": 0.0,
      "maxUnavailable_abs": 0,
      "P_terminating_overlap": 0,
      "P_live": 1,
      "P_avail_min": 1,
      "W": 1,
      "N_proc": 1,
      "N_proc_steady": 1,
      "N_proc_avail_min": 1,
      "CPU_limit_per_pod": 2.0,
      "κ_skew": 1.0,
      "u_bg_worker": 0.12,
      "U_pod_sidecars": 0.0,
      "Mem_limit_per_pod": 512,
      "Mem_rss_worker_max": 176,
      "Mem_shared_max": 32,
      "RPS_peak": 6,
      "A_max": 2,
      "SLA_p99_s": 1800,
      "N_entities_max": 16,
      "Limit_dep_share[d]": {
        "image_remote_fetch": 0
      },
      "Limit_dep_rps[d]": {
        "image_remote_fetch": 0
      },
      "W_fetchers[d]": {
        "image_remote_fetch": 0
      },
      "J_init_s[d]": {
        "image_remote_fetch": 0
      },
      "J_pod_s[d]": {
        "image_remote_fetch": 0
      },
      "T_poll_s[d]": {
        "image_remote_fetch": 0
      },
      "K_calls[d]": {
        "image_remote_fetch": 0
      },
      "T_base_s[d]": {
        "turn_retry": 2.0
      },
      "T_cap_s[d]": {
        "turn_retry": 2.0
      },
      "Max_stale_age_s[c]": {
        "dynamic_config": 1.0,
        "auth_secret": 0,
        "hot_session": 2700
      },
      "Min_healthy_ratio": 0.25,
      "B_retry_max": 3,
      "min_reserve_retry_rps": 0.0,
      "FD_worker": 132,
      "ulimit_n": 65536,
      "λ_new_conn_per_pod(s)": {
        "node_ephemeral": 6
      },
      "C_active_in_scope(s)": {
        "node_ephemeral": 32
      },
      "N_pods_in_scope(s)": {
        "node_ephemeral": 1
      },
      "Port_range_size(s)": {
        "node_ephemeral": 16384
      },
      "T_hold_s(s)": {
        "node_ephemeral": 30
      },
      "SNAT_ips_count(s)": {
        "node_ephemeral": 1
      },
      "HOTPATH_MODULES": [
        "Handler.do_POST",
        "_collect_image_parts",
        "_collect_images",
        "_parse_data_url",
        "_sniff_image",
        "_image_proof_reason",
        "_file_sha256",
        "_is_image_input_enabled",
        "_messages_to_prompt",
        "_get_resumed_turn_prompt",
        "_run_once",
        "_stage_images",
        "Run.__init__",
        "_sweep_workspace",
        "_mask_secrets"
      ]
    },
    "field_units": {
      "P_steady": "pods",
      "P_hpa_max": "pods",
      "maxSurge_pct": "ratio",
      "maxSurge_abs": "pods",
      "maxUnavailable_pct": "ratio",
      "maxUnavailable_abs": "pods",
      "P_terminating_overlap": "pods",
      "P_live": "pods",
      "P_avail_min": "pods",
      "W": "proc/pod",
      "N_proc": "processes",
      "N_proc_steady": "processes",
      "N_proc_avail_min": "processes",
      "CPU_limit_per_pod": "cores",
      "κ_skew": "ratio",
      "u_bg_worker": "cores",
      "U_pod_sidecars": "cores",
      "Mem_limit_per_pod": "MiB",
      "Mem_rss_worker_max": "MiB",
      "Mem_shared_max": "MiB",
      "RPS_peak": "req/s",
      "A_max": "attempts/req",
      "SLA_p99_s": "s",
      "N_entities_max": "items",
      "Limit_dep_share[d]": "connections",
      "Limit_dep_rps[d]": "req/s",
      "W_fetchers[d]": "proc/pod",
      "J_init_s[d]": "s",
      "J_pod_s[d]": "s",
      "T_poll_s[d]": "s",
      "K_calls[d]": "calls",
      "T_base_s[d]": "s",
      "T_cap_s[d]": "s",
      "Max_stale_age_s[c]": "s",
      "Min_healthy_ratio": "ratio",
      "B_retry_max": "tokens",
      "min_reserve_retry_rps": "req/s",
      "FD_worker": "descriptors",
      "ulimit_n": "descriptors",
      "λ_new_conn_per_pod(s)": "conn/s",
      "C_active_in_scope(s)": "connections",
      "N_pods_in_scope(s)": "pods",
      "Port_range_size(s)": "ports",
      "T_hold_s(s)": "s",
      "SNAT_ips_count(s)": "IPs",
      "HOTPATH_MODULES": "list[str]"
    },
    "field_sources": {
      "P_steady": "F-25 one LaunchAgent, no HPA/rolling deployment; derived one-process model, restart may temporarily have zero live processes",
      "P_hpa_max": "F-25 one LaunchAgent, no HPA/rolling deployment; derived one-process model, restart may temporarily have zero live processes",
      "maxSurge_pct": "F-25 one LaunchAgent, no HPA/rolling deployment; derived one-process model, restart may temporarily have zero live processes",
      "maxSurge_abs": "F-25 one LaunchAgent, no HPA/rolling deployment; derived one-process model, restart may temporarily have zero live processes",
      "maxUnavailable_pct": "F-25 one LaunchAgent, no HPA/rolling deployment; derived one-process model, restart may temporarily have zero live processes",
      "maxUnavailable_abs": "F-25 one LaunchAgent, no HPA/rolling deployment; derived one-process model, restart may temporarily have zero live processes",
      "P_terminating_overlap": "F-25 one LaunchAgent, no HPA/rolling deployment; derived one-process model, restart may temporarily have zero live processes",
      "P_live": "F-25 one LaunchAgent, no HPA/rolling deployment; derived one-process model, restart may temporarily have zero live processes",
      "P_avail_min": "F-25 one LaunchAgent, no HPA/rolling deployment; derived one-process model, restart may temporarily have zero live processes",
      "W": "F-25 one LaunchAgent, no HPA/rolling deployment; derived one-process model, restart may temporarily have zero live processes",
      "N_proc": "F-25 one LaunchAgent, no HPA/rolling deployment; derived one-process model, restart may temporarily have zero live processes",
      "N_proc_steady": "F-25 one LaunchAgent, no HPA/rolling deployment; derived one-process model, restart may temporarily have zero live processes",
      "N_proc_avail_min": "F-25 one LaunchAgent, no HPA/rolling deployment; derived one-process model, restart may temporarily have zero live processes",
      "CPU_limit_per_pod": "ASM-008 owner-approved planning target; validate RES-01 before production",
      "κ_skew": "ASM-008 owner-approved planning target; validate RES-01 before production",
      "u_bg_worker": "ASM-008 owner-approved planning target; validate RES-01 before production",
      "U_pod_sidecars": "ASM-008 owner-approved planning target; validate RES-01 before production",
      "Mem_limit_per_pod": "Stage 2 brief §5 target; ASM-004/EVD-036 retained-buffer bound NOT proven; RES-01 pre-promotion gate",
      "Mem_rss_worker_max": "Stage 2 brief §5 target; ASM-004/EVD-036 retained-buffer bound NOT proven; RES-01 pre-promotion gate",
      "Mem_shared_max": "Stage 2 brief §5 target; ASM-004/EVD-036 retained-buffer bound NOT proven; RES-01 pre-promotion gate",
      "RPS_peak": "ASM-008 owner-approved planning target; validate RES-01 before production",
      "A_max": "F-12/F-30 existing two attempts,3-token burst,0.2/request refill,zero time refill",
      "SLA_p99_s": "ASM-008 owner-approved planning target; validate RES-01 before production",
      "N_entities_max": "ASM-008 owner-approved planning target; validate RES-01 before production",
      "Limit_dep_share[d]": "AD-002/BND-001/004 image path performs no remote fetch/poller; zero component is deliberate, do not divide by zero; unchanged native CLI upstream unknown, not waived",
      "Limit_dep_rps[d]": "AD-002/BND-001/004 image path performs no remote fetch/poller; zero component is deliberate, do not divide by zero; unchanged native CLI upstream unknown, not waived",
      "W_fetchers[d]": "AD-002/BND-001/004 image path performs no remote fetch/poller; zero component is deliberate, do not divide by zero; unchanged native CLI upstream unknown, not waived",
      "J_init_s[d]": "AD-002/BND-001/004 image path performs no remote fetch/poller; zero component is deliberate, do not divide by zero; unchanged native CLI upstream unknown, not waived",
      "J_pod_s[d]": "AD-002/BND-001/004 image path performs no remote fetch/poller; zero component is deliberate, do not divide by zero; unchanged native CLI upstream unknown, not waived",
      "T_poll_s[d]": "AD-002/BND-001/004 image path performs no remote fetch/poller; zero component is deliberate, do not divide by zero; unchanged native CLI upstream unknown, not waived",
      "K_calls[d]": "AD-002/BND-001/004 image path performs no remote fetch/poller; zero component is deliberate, do not divide by zero; unchanged native CLI upstream unknown, not waived",
      "T_base_s[d]": "ASM-008 owner-approved planning target; validate RES-01 before production",
      "T_cap_s[d]": "ASM-008 owner-approved planning target; validate RES-01 before production",
      "Max_stale_age_s[c]": "ASM-008 owner-approved planning target; validate RES-01 before production",
      "Min_healthy_ratio": "ASM-008 owner-approved planning target; validate RES-01 before production",
      "B_retry_max": "F-12/F-30 existing two attempts,3-token burst,0.2/request refill,zero time refill",
      "min_reserve_retry_rps": "F-12/F-30 existing two attempts,3-token burst,0.2/request refill,zero time refill",
      "FD_worker": "ASM-008 owner-approved planning target; validate RES-01 before production",
      "ulimit_n": "Owner supplied 2026-10-29 host observations EVD-035; shell ulimit is not proof of launchd process limit",
      "λ_new_conn_per_pod(s)": "ASM-008 owner-approved planning target; validate RES-01 before production",
      "C_active_in_scope(s)": "ASM-008 owner-approved planning target; validate RES-01 before production",
      "N_pods_in_scope(s)": "ASM-008 owner-approved planning target; validate RES-01 before production",
      "Port_range_size(s)": "Owner supplied 2026-10-29 host observations EVD-035; shell ulimit is not proof of launchd process limit",
      "T_hold_s(s)": "Owner supplied 2026-10-29 host observations EVD-035; shell ulimit is not proof of launchd process limit",
      "SNAT_ips_count(s)": "ASM-008 owner-approved planning target; validate RES-01 before production",
      "HOTPATH_MODULES": "F-02/F-09/F-11/F-12/F-13/F-22 and AD-001..006 proposed call graph"
    },
    "memory_closure_check": {
      "status": "PASS",
      "unit": "MiB",
      "lhs_mib": 208,
      "rhs_mib": 409.6,
      "substitution": "1 * 176 + 32 = 208 <= 0.80 * 512 = 409.6",
      "evidence_level": "ARITHMETIC_ONLY_CONDITIONAL_ON_ASM_004",
      "runtime_bound_status": "UNPROVEN",
      "explanation": "Requested arithmetic passes. Body admission bounds HTTP bytes, not simultaneous strings/decoded buffers retained by requests waiting for slots. Decoded bytes cleared only after slot acquisition. Need measured parent RSS + retained-buffer accounting under all32 admitted handlers, or change resource design through parent before claiming strict closure.",
      "production_gate": "BLOCKED until RES-01 demonstrates bound; 208MiB is not measured RSS"
    },
    "operational_profile": {
      "active_turns_max": 8,
      "code_default_max_concurrent": 4,
      "deployed_max_concurrent": 8,
      "http_connections_max": 32,
      "http_inflight_body_bytes": 67108864,
      "decoded_total_per_request_bytes": 20971520,
      "max_active_disk_spool_mib": 160,
      "orphan_backlog": "not included; sweep recovery and disk monitoring required",
      "host_cpu_cores_supplied": 18,
      "host_memory_bytes_supplied": 68719476736,
      "sha_chunk_bytes": 1048576,
      "decoded_image_open_fds_during_agy": 0,
      "children_rss": "separate measured budget; no per-child bound supplied",
      "rps_peak_target": 6,
      "p99_target_s": 1800,
      "limit_note": "Planning targets are not enforced or measured maxima; native upstream connection behavior remains unknown"
    }
  },
  "resilience_gates": {
    "ssot": "~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/architecture.md §3/7",
    "status_semantics": "PASS is a prospective design/check condition, not executed runtime evidence; explicit unresolved findings override promotion. N/A covers image delta only and requires future candidate diff + transitive graph check.",
    "HL_ENV_v1": {
      "HL-ENV-01": {
        "status": "BLOCKED",
        "substitution": "46 canonical keys; arithmetic 208<=409.6 MiB under ASM-004; actual memory upper bound unproven, promotion blocked",
        "oracle": "Assert canonical 46 field/value/unit/source sets; recompute inequality; validate every na_proof; RES-01 retained buffers incl all admitted waiters",
        "verification_ids": [
          "VER-003",
          "VER-007",
          "VER-009",
          "VER-010"
        ],
        "evidence_level": "UNRESOLVED: production/resource acceptance blocked; structural packet approval is not gate acceptance"
      }
    },
    "C_MULT": {
      "C-MULT-I1": {
        "status": "N/A",
        "substitution": "No added network connection/pool on image path; image files add0 open handles during agy execution. Native agy upstream and existing pollers remain existing scope, not a proven cluster quota.",
        "oracle": "AO-05/09 count image handles zero during Run; inspect no network loaders",
        "verification_ids": [
          "VER-003",
          "VER-007",
          "VER-009",
          "VER-010"
        ],
        "evidence_level": "Prospective design condition; runtime oracle NOT RUN in Stage2",
        "reason": "No new network connection quota component in changed image code; native CLI upstream not covered by N/A",
        "na_proof": {
          "current_git_diff_command": "git diff --name-only 5a19559426de7508d525e2bd465eff648665a6a7 -- bridges/agy-bridge tests/test_agy_bridge_resilience.py",
          "current_git_diff_output": "",
          "current_product_fingerprint": "81388141296d03375a6a57b676d803059e36cd26bfe1522a20784a28fbb4e737",
          "git_diff_files": [
            "bridges/agy-bridge/server.py",
            "bridges/agy-bridge/fleet.json",
            "tests/test_agy_bridge_resilience.py"
          ],
          "transitive_call_graph": "Evidence F-02/F-09..13/F-22 and proposed AD: Handler.do_POST → auth/admission/body → _collect_images → {_collect_image_parts, _is_image_input_enabled, _image_proof_reason → _file_sha256, _parse_data_url, _sniff_image} → full/resumed render → _run_once → _acquire_slot → _stage_images → Run → Popen text NDJSON/native view_file → close consumers → rmtree/release. Sweep → locked active registry → age/is_symlink checks. No new Redis/PG/Vault/ControlPlane, asyncio loop, node selection/health/quarantine or network image fetch. Native CLI upstream is transitive external dependency and explicitly NOT waived by image-path N/A.",
          "future_diff_gate": "Empty current diff proves read-only Stage2 only. Teamlead/Verifier revalidate product candidate diff, AST aliases/call graph and tests before code acceptance; future newly introduced calls invalidate N/A. No claim that proposed graph was verified from code in this constrained stage."
        }
      },
      "C-MULT-I2": {
        "status": "BLOCKED",
        "substitution": "Existing 8 execution slots and32 HTTP admission retained; added spool waits only after slot acquired. Baseline32 total admitted may include24 waiters >2*8, unchanged baseline debt, do not claim global PASS.",
        "oracle": "AO-05 queued requests create zero dirs; verify inherited queue behavior unchanged and escalate >2M inherited mismatch to parent",
        "verification_ids": [
          "VER-003",
          "VER-007",
          "VER-009",
          "VER-010"
        ],
        "evidence_level": "UNRESOLVED: production/resource acceptance blocked; structural packet approval is not gate acceptance"
      },
      "C-MULT-I3": {
        "status": "N/A",
        "substitution": "No network client introduced; per-turn files are closed before process spawn. No global open image descriptor.",
        "oracle": "AST no added network client; AO-05 image file handles closed before Run",
        "verification_ids": [
          "VER-003",
          "VER-007",
          "VER-009",
          "VER-010"
        ],
        "evidence_level": "Prospective design condition; runtime oracle NOT RUN in Stage2",
        "reason": "No network client introduced; per-turn files are closed before process spawn. No global open image descriptor.",
        "na_proof": {
          "current_git_diff_command": "git diff --name-only 5a19559426de7508d525e2bd465eff648665a6a7 -- bridges/agy-bridge tests/test_agy_bridge_resilience.py",
          "current_git_diff_output": "",
          "current_product_fingerprint": "81388141296d03375a6a57b676d803059e36cd26bfe1522a20784a28fbb4e737",
          "git_diff_files": [
            "bridges/agy-bridge/server.py",
            "bridges/agy-bridge/fleet.json",
            "tests/test_agy_bridge_resilience.py"
          ],
          "transitive_call_graph": "Evidence F-02/F-09..13/F-22 and proposed AD: Handler.do_POST → auth/admission/body → _collect_images → {_collect_image_parts, _is_image_input_enabled, _image_proof_reason → _file_sha256, _parse_data_url, _sniff_image} → full/resumed render → _run_once → _acquire_slot → _stage_images → Run → Popen text NDJSON/native view_file → close consumers → rmtree/release. Sweep → locked active registry → age/is_symlink checks. No new Redis/PG/Vault/ControlPlane, asyncio loop, node selection/health/quarantine or network image fetch. Native CLI upstream is transitive external dependency and explicitly NOT waived by image-path N/A.",
          "future_diff_gate": "Empty current diff proves read-only Stage2 only. Teamlead/Verifier revalidate product candidate diff, AST aliases/call graph and tests before code acceptance; future newly introduced calls invalidate N/A. No claim that proposed graph was verified from code in this constrained stage."
        }
      },
      "C-MULT-I4": {
        "status": "PASS",
        "substitution": "Every acquired slot and created image resource belongs to outer finally, including cancel/no-spawn/spool error.",
        "oracle": "AO-06 50 deterministic abort points leave slot/active registry/files at baseline",
        "verification_ids": [
          "VER-003",
          "VER-007",
          "VER-009",
          "VER-010"
        ],
        "evidence_level": "Prospective design condition; runtime oracle NOT RUN in Stage2"
      },
      "C-MULT-I5": {
        "status": "BLOCKED",
        "substitution": "Planning parent FD132<=45875.2; new spool FD adds0 during run. Local ports target6*1*30+32=212<=8192; shell65536 supplied, launchd/CLI egress budget unmeasured.",
        "oracle": "AO-09 verify worker rlimit, FD and node ports; native upstream/shared SNAT cannot be asserted from loopback facts",
        "verification_ids": [
          "VER-003",
          "VER-007",
          "VER-009",
          "VER-010"
        ],
        "evidence_level": "UNRESOLVED: production/resource acceptance blocked; structural packet approval is not gate acceptance"
      }
    },
    "S_HERD": {
      "S-HERD-I1": {
        "status": "N/A",
        "substitution": "Image delta adds zero network fetch and no startup/poll loop; flag config shared1s stat cache; existing transcript/SQLite polling unchanged",
        "oracle": "AST/spy zero network calls in image helpers; concurrent same config/binary identity single parse/hash; existing regression suite",
        "verification_ids": [
          "VER-003",
          "VER-007",
          "VER-009",
          "VER-010"
        ],
        "evidence_level": "Prospective design condition; runtime oracle NOT RUN in Stage2",
        "reason": "Image delta adds zero network fetch and no startup/poll loop; flag config shared1s stat cache; existing transcript/SQLite polling unchanged",
        "na_proof": {
          "current_git_diff_command": "git diff --name-only 5a19559426de7508d525e2bd465eff648665a6a7 -- bridges/agy-bridge tests/test_agy_bridge_resilience.py",
          "current_git_diff_output": "",
          "current_product_fingerprint": "81388141296d03375a6a57b676d803059e36cd26bfe1522a20784a28fbb4e737",
          "git_diff_files": [
            "bridges/agy-bridge/server.py",
            "bridges/agy-bridge/fleet.json",
            "tests/test_agy_bridge_resilience.py"
          ],
          "transitive_call_graph": "Evidence F-02/F-09..13/F-22 and proposed AD: Handler.do_POST → auth/admission/body → _collect_images → {_collect_image_parts, _is_image_input_enabled, _image_proof_reason → _file_sha256, _parse_data_url, _sniff_image} → full/resumed render → _run_once → _acquire_slot → _stage_images → Run → Popen text NDJSON/native view_file → close consumers → rmtree/release. Sweep → locked active registry → age/is_symlink checks. No new Redis/PG/Vault/ControlPlane, asyncio loop, node selection/health/quarantine or network image fetch. Native CLI upstream is transitive external dependency and explicitly NOT waived by image-path N/A.",
          "future_diff_gate": "Empty current diff proves read-only Stage2 only. Teamlead/Verifier revalidate product candidate diff, AST aliases/call graph and tests before code acceptance; future newly introduced calls invalidate N/A. No claim that proposed graph was verified from code in this constrained stage."
        }
      },
      "S-HERD-I2": {
        "status": "PASS",
        "substitution": "No image poller/fork new; preserve existing Full-Jitter retry cap2s and injected RNG",
        "oracle": "AO-09 deterministic u=0,.5,1 produces0,1,2s where existing retry applies; no extra image retry loop",
        "verification_ids": [
          "VER-003",
          "VER-007",
          "VER-009",
          "VER-010"
        ],
        "evidence_level": "Prospective design condition; runtime oracle NOT RUN in Stage2"
      },
      "S-HERD-I3": {
        "status": "PASS",
        "substitution": "Config and binary stat identity cache: unchanged identity avoids JSON/hash rebuild. Config parsed only refresh/change; SHA1MiB chunks under lock.",
        "oracle": "AO-01 multiple concurrent proof checks hash once per identity; changed st_mtime_ns/size rehash; flag TTL expires on FakeClock",
        "verification_ids": [
          "VER-003",
          "VER-007",
          "VER-009",
          "VER-010"
        ],
        "evidence_level": "Prospective design condition; runtime oracle NOT RUN in Stage2"
      },
      "S-HERD-I4": {
        "status": "N/A",
        "substitution": "No network TTL cache introduced. Local stat/sha cache is serialized under existing guard/sha locks; never cache permissive state on parse errors.",
        "oracle": "AO-01 invalid config false, unchanged stat avoids rebuild; AST network closure inspection",
        "verification_ids": [
          "VER-003",
          "VER-007",
          "VER-009",
          "VER-010"
        ],
        "evidence_level": "Prospective design condition; runtime oracle NOT RUN in Stage2",
        "reason": "No network TTL cache introduced. Local stat/sha cache is serialized under existing guard/sha locks; never cache permissive state on parse errors.",
        "na_proof": {
          "current_git_diff_command": "git diff --name-only 5a19559426de7508d525e2bd465eff648665a6a7 -- bridges/agy-bridge tests/test_agy_bridge_resilience.py",
          "current_git_diff_output": "",
          "current_product_fingerprint": "81388141296d03375a6a57b676d803059e36cd26bfe1522a20784a28fbb4e737",
          "git_diff_files": [
            "bridges/agy-bridge/server.py",
            "bridges/agy-bridge/fleet.json",
            "tests/test_agy_bridge_resilience.py"
          ],
          "transitive_call_graph": "Evidence F-02/F-09..13/F-22 and proposed AD: Handler.do_POST → auth/admission/body → _collect_images → {_collect_image_parts, _is_image_input_enabled, _image_proof_reason → _file_sha256, _parse_data_url, _sniff_image} → full/resumed render → _run_once → _acquire_slot → _stage_images → Run → Popen text NDJSON/native view_file → close consumers → rmtree/release. Sweep → locked active registry → age/is_symlink checks. No new Redis/PG/Vault/ControlPlane, asyncio loop, node selection/health/quarantine or network image fetch. Native CLI upstream is transitive external dependency and explicitly NOT waived by image-path N/A.",
          "future_diff_gate": "Empty current diff proves read-only Stage2 only. Teamlead/Verifier revalidate product candidate diff, AST aliases/call graph and tests before code acceptance; future newly introduced calls invalidate N/A. No claim that proposed graph was verified from code in this constrained stage."
        }
      },
      "S-HERD-I5": {
        "status": "PASS",
        "substitution": "No new readiness snapshot; /health image fields additive; flag invalid => disabled while text service stays live. No stale proof accepted after binary identity change.",
        "oracle": "AO-01 health state matches flag and confirmed catalog; text-only unaffected by invalid image proof",
        "verification_ids": [
          "VER-003",
          "VER-007",
          "VER-009",
          "VER-010"
        ],
        "evidence_level": "Prospective design condition; runtime oracle NOT RUN in Stage2"
      }
    },
    "H_CPU": {
      "H-CPU-I1": {
        "status": "PASS",
        "substitution": "MIME sniff constant prefix and global index per image; unavoidable linear traversal of user history/base64 bounded by32MiB body and16 images, not a rule/node lookup.",
        "oracle": "AO-02 deterministic traversal counter once per part; sniff inspects<=12 bytes; input decode<=20MiB total; no repeated staging per attempt",
        "verification_ids": [
          "VER-003",
          "VER-007",
          "VER-009",
          "VER-010"
        ],
        "evidence_level": "Prospective design condition; runtime oracle NOT RUN in Stage2"
      },
      "H-CPU-I2": {
        "status": "PASS",
        "substitution": "No regex compile/deepcopy/model-validate per image; no whole193MiB binary materialization. Local dynamic config JSON only changed/stat-cache refresh; zero per-part config parsing.",
        "oracle": "AO-01 spy hash/read sizes and config parse count; existing HTTP JSON parse is protocol boundary, not rules parsing",
        "verification_ids": [
          "VER-003",
          "VER-007",
          "VER-009",
          "VER-010"
        ],
        "evidence_level": "Prospective design condition; runtime oracle NOT RUN in Stage2"
      },
      "H-CPU-I3": {
        "status": "PASS",
        "substitution": "0 image parts returns[] before any flag/stat/hash/uuid/stage calls. Flag-off image request rejects with no uuid/stage/spawn; only necessary flag check.",
        "oracle": "AO-02 text-only spies all0; disabled image branch no spool/proof hash after flag false; telemetry no added unbounded queue",
        "verification_ids": [
          "VER-003",
          "VER-007",
          "VER-009",
          "VER-010"
        ],
        "evidence_level": "Prospective design condition; runtime oracle NOT RUN in Stage2"
      },
      "H-CPU-I4": {
        "status": "N/A",
        "substitution": "ThreadingHTTPServer and synchronous local image preparation; no asyncio event loop/config snapshot rebuild added.",
        "oracle": "AST no new asyncio loop; config path stat cache; no claim GIL-heavy decode is free",
        "verification_ids": [
          "VER-003",
          "VER-007",
          "VER-009",
          "VER-010"
        ],
        "evidence_level": "Prospective design condition; runtime oracle NOT RUN in Stage2",
        "reason": "ThreadingHTTPServer and synchronous local image preparation; no asyncio event loop/config snapshot rebuild added.",
        "na_proof": {
          "current_git_diff_command": "git diff --name-only 5a19559426de7508d525e2bd465eff648665a6a7 -- bridges/agy-bridge tests/test_agy_bridge_resilience.py",
          "current_git_diff_output": "",
          "current_product_fingerprint": "81388141296d03375a6a57b676d803059e36cd26bfe1522a20784a28fbb4e737",
          "git_diff_files": [
            "bridges/agy-bridge/server.py",
            "bridges/agy-bridge/fleet.json",
            "tests/test_agy_bridge_resilience.py"
          ],
          "transitive_call_graph": "Evidence F-02/F-09..13/F-22 and proposed AD: Handler.do_POST → auth/admission/body → _collect_images → {_collect_image_parts, _is_image_input_enabled, _image_proof_reason → _file_sha256, _parse_data_url, _sniff_image} → full/resumed render → _run_once → _acquire_slot → _stage_images → Run → Popen text NDJSON/native view_file → close consumers → rmtree/release. Sweep → locked active registry → age/is_symlink checks. No new Redis/PG/Vault/ControlPlane, asyncio loop, node selection/health/quarantine or network image fetch. Native CLI upstream is transitive external dependency and explicitly NOT waived by image-path N/A.",
          "future_diff_gate": "Empty current diff proves read-only Stage2 only. Teamlead/Verifier revalidate product candidate diff, AST aliases/call graph and tests before code acceptance; future newly introduced calls invalidate N/A. No claim that proposed graph was verified from code in this constrained stage."
        }
      },
      "H-CPU-I5": {
        "status": "BLOCKED",
        "substitution": "Conditional target CPU2cores,RPS6,u_bg=.12, t_base_req_total=.04s,delta_feature=.01s => util .42<=.70, pod .42<=1.60, feature .06<=.10. These CPU seconds are acceptance ceilings, NOT measured.",
        "oracle": "AO-09 RES-01 measure CPU seconds max-sized images including binary-change hash; if limits exceeded block, no synthetic PASS",
        "verification_ids": [
          "VER-003",
          "VER-007",
          "VER-009",
          "VER-010"
        ],
        "evidence_level": "UNRESOLVED: production/resource acceptance blocked; structural packet approval is not gate acceptance"
      }
    },
    "R_BULK": {
      "R-BULK-I1": {
        "status": "BLOCKED",
        "substitution": "Do not call1800s timeout empirical SLA. Queue1800s alone exceeds30% of1800 target=540s; existing inherited budget is UNRESOLVED, not waived. Image staging adds filesystem I/O with no hard timeout supplied.",
        "oracle": "AO-09 measure queue/stage and existing end-to-end deadline behavior; parent resolves baseline budget before claiming full R-BULK pass",
        "verification_ids": [
          "VER-003",
          "VER-007",
          "VER-009",
          "VER-010"
        ],
        "evidence_level": "UNRESOLVED: production/resource acceptance blocked; structural packet approval is not gate acceptance"
      },
      "R-BULK-I2": {
        "status": "PASS",
        "substitution": "A_max2, burst3tokens, refill.2/request, no time reserve; stage once outside attempts; no cold retry after delivered content/tool/reasoning.",
        "oracle": "100 failing requests => retries<=23 under existing accounting; HIST-05/06 capture attempts and same file digests; inherited waiter mismatch reported, not fixed out of scope",
        "verification_ids": [
          "VER-003",
          "VER-007",
          "VER-009",
          "VER-010"
        ],
        "evidence_level": "Prospective design condition; runtime oracle NOT RUN in Stage2"
      },
      "R-BULK-I3": {
        "status": "N/A",
        "substitution": "No new network dependency breaker; deterministic invalid proof/flag fails closed for image request. Existing SQLite reasoning breaker unaffected.",
        "oracle": "AO-01 rejects without retry/spawn on proof/flag invalid; text-only succeeds; regression existing breaker tests",
        "verification_ids": [
          "VER-003",
          "VER-007",
          "VER-009",
          "VER-010"
        ],
        "evidence_level": "Prospective design condition; runtime oracle NOT RUN in Stage2",
        "reason": "New image control failures are deterministic request-local validation, no new remote auxiliary service; existing agy/SQLite dependencies still tested",
        "na_proof": {
          "current_git_diff_command": "git diff --name-only 5a19559426de7508d525e2bd465eff648665a6a7 -- bridges/agy-bridge tests/test_agy_bridge_resilience.py",
          "current_git_diff_output": "",
          "current_product_fingerprint": "81388141296d03375a6a57b676d803059e36cd26bfe1522a20784a28fbb4e737",
          "git_diff_files": [
            "bridges/agy-bridge/server.py",
            "bridges/agy-bridge/fleet.json",
            "tests/test_agy_bridge_resilience.py"
          ],
          "transitive_call_graph": "Evidence F-02/F-09..13/F-22 and proposed AD: Handler.do_POST → auth/admission/body → _collect_images → {_collect_image_parts, _is_image_input_enabled, _image_proof_reason → _file_sha256, _parse_data_url, _sniff_image} → full/resumed render → _run_once → _acquire_slot → _stage_images → Run → Popen text NDJSON/native view_file → close consumers → rmtree/release. Sweep → locked active registry → age/is_symlink checks. No new Redis/PG/Vault/ControlPlane, asyncio loop, node selection/health/quarantine or network image fetch. Native CLI upstream is transitive external dependency and explicitly NOT waived by image-path N/A.",
          "future_diff_gate": "Empty current diff proves read-only Stage2 only. Teamlead/Verifier revalidate product candidate diff, AST aliases/call graph and tests before code acceptance; future newly introduced calls invalidate N/A. No claim that proposed graph was verified from code in this constrained stage."
        }
      },
      "R-BULK-I4": {
        "status": "N/A",
        "substitution": "No image node candidate selection, quarantine or Panic-Open; model selected by caller; cannot fail-open proof/auth.",
        "oracle": "AO-01 unsupported model never admitted even on other failures; AST no pool routing added",
        "verification_ids": [
          "VER-003",
          "VER-007",
          "VER-009",
          "VER-010"
        ],
        "evidence_level": "Prospective design condition; runtime oracle NOT RUN in Stage2",
        "reason": "No image node candidate selection, quarantine or Panic-Open; model selected by caller; cannot fail-open proof/auth.",
        "na_proof": {
          "current_git_diff_command": "git diff --name-only 5a19559426de7508d525e2bd465eff648665a6a7 -- bridges/agy-bridge tests/test_agy_bridge_resilience.py",
          "current_git_diff_output": "",
          "current_product_fingerprint": "81388141296d03375a6a57b676d803059e36cd26bfe1522a20784a28fbb4e737",
          "git_diff_files": [
            "bridges/agy-bridge/server.py",
            "bridges/agy-bridge/fleet.json",
            "tests/test_agy_bridge_resilience.py"
          ],
          "transitive_call_graph": "Evidence F-02/F-09..13/F-22 and proposed AD: Handler.do_POST → auth/admission/body → _collect_images → {_collect_image_parts, _is_image_input_enabled, _image_proof_reason → _file_sha256, _parse_data_url, _sniff_image} → full/resumed render → _run_once → _acquire_slot → _stage_images → Run → Popen text NDJSON/native view_file → close consumers → rmtree/release. Sweep → locked active registry → age/is_symlink checks. No new Redis/PG/Vault/ControlPlane, asyncio loop, node selection/health/quarantine or network image fetch. Native CLI upstream is transitive external dependency and explicitly NOT waived by image-path N/A.",
          "future_diff_gate": "Empty current diff proves read-only Stage2 only. Teamlead/Verifier revalidate product candidate diff, AST aliases/call graph and tests before code acceptance; future newly introduced calls invalidate N/A. No claim that proposed graph was verified from code in this constrained stage."
        }
      },
      "R-BULK-I5": {
        "status": "N/A",
        "substitution": "No new origin/node health state or classification; image validation and spool errors never mark upstream origin/node unhealthy.",
        "oracle": "AO-06 errors isolated request-locally; AST no shared health mutation added",
        "verification_ids": [
          "VER-003",
          "VER-007",
          "VER-009",
          "VER-010"
        ],
        "evidence_level": "Prospective design condition; runtime oracle NOT RUN in Stage2",
        "reason": "No new origin/node health state or classification; image validation and spool errors never mark upstream origin/node unhealthy.",
        "na_proof": {
          "current_git_diff_command": "git diff --name-only 5a19559426de7508d525e2bd465eff648665a6a7 -- bridges/agy-bridge tests/test_agy_bridge_resilience.py",
          "current_git_diff_output": "",
          "current_product_fingerprint": "81388141296d03375a6a57b676d803059e36cd26bfe1522a20784a28fbb4e737",
          "git_diff_files": [
            "bridges/agy-bridge/server.py",
            "bridges/agy-bridge/fleet.json",
            "tests/test_agy_bridge_resilience.py"
          ],
          "transitive_call_graph": "Evidence F-02/F-09..13/F-22 and proposed AD: Handler.do_POST → auth/admission/body → _collect_images → {_collect_image_parts, _is_image_input_enabled, _image_proof_reason → _file_sha256, _parse_data_url, _sniff_image} → full/resumed render → _run_once → _acquire_slot → _stage_images → Run → Popen text NDJSON/native view_file → close consumers → rmtree/release. Sweep → locked active registry → age/is_symlink checks. No new Redis/PG/Vault/ControlPlane, asyncio loop, node selection/health/quarantine or network image fetch. Native CLI upstream is transitive external dependency and explicitly NOT waived by image-path N/A.",
          "future_diff_gate": "Empty current diff proves read-only Stage2 only. Teamlead/Verifier revalidate product candidate diff, AST aliases/call graph and tests before code acceptance; future newly introduced calls invalidate N/A. No claim that proposed graph was verified from code in this constrained stage."
        }
      }
    },
    "non_waivable_stop_codes": [
      "HL-ENV-01",
      "C-MULT-I1",
      "C-MULT-I2",
      "C-MULT-I3",
      "C-MULT-I4",
      "C-MULT-I5",
      "S-HERD-I1",
      "S-HERD-I2",
      "S-HERD-I3",
      "S-HERD-I4",
      "S-HERD-I5",
      "H-CPU-I1",
      "H-CPU-I2",
      "H-CPU-I3",
      "H-CPU-I4",
      "H-CPU-I5",
      "R-BULK-I1",
      "R-BULK-I2",
      "R-BULK-I3",
      "R-BULK-I4",
      "R-BULK-I5",
      "T-LIFE/v1",
      "O-EXIT/v1",
      "M-SEM/v1"
    ],
    "T_LIFE_v1": {
      "status": "PASS",
      "substitution": "Turn owns spool; all retry consumers closed before finally cleanup; active registry and slots released on every terminal branch; files closed before agy spawn",
      "oracle": "AO-05/06/07 + LIFE-01..05",
      "verification_ids": [
        "VER-003",
        "VER-007"
      ],
      "evidence_level": "design only"
    },
    "O_EXIT_v1": {
      "status": "PASS",
      "substitution": "Every image reject exact HTTP400/log reason; spool failure500 image_spool_error; preserve existing done diagnostics on every _run_once terminal branch; never payloads",
      "oracle": "AO-08 assert exact reject line and secret negative scan plus terminal outcomes",
      "verification_ids": [
        "VER-003",
        "VER-007"
      ],
      "evidence_level": "design only"
    },
    "M_SEM_v1": {
      "status": "PASS",
      "substitution": "cwd/sess_key preserved; unique img_dir per turn; plain/background do not steal agentic cid; capability/proof never bypassed",
      "oracle": "AO-03/04 HIST-07..10; captured argv/cwd/key; concurrent turns isolated",
      "verification_ids": [
        "VER-003",
        "VER-007"
      ],
      "evidence_level": "design only"
    },
    "dependency_failure_matrix": [
      {
        "dependency": "Image flag/proof/validator",
        "path": "hot",
        "timeout_budget": "stat cache TTL1s; binary chunk read no hard I/O bound proven",
        "bulkhead": "32 HTTP admission",
        "circuit_breaker": "deterministic fail-closed request gate; no retry",
        "failure_mode": "400 image_input_not_supported or exact validation reason; pure text bypass"
      },
      {
        "dependency": "Local spool",
        "path": "hot after slot",
        "timeout_budget": "filesystem latency profiling required; no hard deadline added here",
        "bulkhead": "8 slots;160MiB active disk target",
        "circuit_breaker": "request-local OSError, zero CLI spawns",
        "failure_mode": "500 image_spool_error + finally cleanup"
      },
      {
        "dependency": "agy native CLI + session",
        "path": "hot",
        "timeout_budget": "existing first-token120/execution1800/queue1800 limits, not p99 evidence",
        "bulkhead": "8 execution/32 HTTP, inherited waiter budget mismatch",
        "circuit_breaker": "existing retry budget and reasoning guards unchanged",
        "failure_mode": "existing response; hot→cold only before delivery; full files retained"
      },
      {
        "dependency": "Logging",
        "path": "hot",
        "timeout_budget": "no added blocking sink",
        "bulkhead": "existing logger",
        "circuit_breaker": "none added",
        "failure_mode": "fail-open to generation; never waive secret masking"
      }
    ],
    "baseline_debt": [
      {
        "id": "BD-001",
        "finding": "Runtime queue1800s > .30*1800p99 target; timeout is not proven SLA; no global R-BULK-I1 acceptance",
        "disposition": "Escalate parent before production; no silent waiver"
      },
      {
        "id": "BD-002",
        "finding": "32 HTTP admission vs8 slots allows24 potential waiters >2M16; inherited existing behavior",
        "disposition": "Do not modify unrelated admission scope here; parent resolves acceptance; no global C-MULT-I2 PASS"
      },
      {
        "id": "BD-003",
        "finding": "Parent retained-buffer/RSS, child RSS, launchd FD limit and upstream network profile unproven",
        "disposition": "RES-01 and resource design review before promotion"
      }
    ],
    "summary": {
      "canonical_codes": 21,
      "extra_codes": 3,
      "design_only": true,
      "production_resource_gate": "BLOCKED: unproven RSS bound, CPU/FD/upstream profiling and inherited deadline/waiter budgets",
      "new_image_dependencies": "filesystem only, no network loader"
    }
  },
  "legacy_arch_antipattern_checks": {
    "ARCH_CYCLE_DETECTED": {
      "status": "PASS",
      "rationale": "DAG Handler→validator/renderer→run_once→stage→Run; cleanup/sweep independent, no reverse import",
      "verification_ids": [
        "VER-003",
        "VER-007",
        "VER-009",
        "VER-010"
      ],
      "evidence_level": "design; no runtime claim"
    },
    "LAYER_VIOLATION": {
      "status": "PASS",
      "rationale": "HTTP framing stays Handler; isolated helpers validate/render/stage; no new repository/domain layer needed",
      "verification_ids": [
        "VER-003",
        "VER-007",
        "VER-009",
        "VER-010"
      ],
      "evidence_level": "design; no runtime claim"
    },
    "GOD_OBJECT": {
      "status": "PASS",
      "rationale": "Reuse local helpers; no new generic image subsystem or unrelated refactor",
      "verification_ids": [
        "VER-003",
        "VER-007",
        "VER-009",
        "VER-010"
      ],
      "evidence_level": "design; no runtime claim"
    },
    "TIGHT_COUPLING": {
      "status": "PASS",
      "rationale": "Proof binds explicit binary/method/version; native view_file only; root bridge reference read-only",
      "verification_ids": [
        "VER-003",
        "VER-007",
        "VER-009",
        "VER-010"
      ],
      "evidence_level": "design; no runtime claim"
    },
    "LEAKY_ABSTRACTION": {
      "status": "PASS",
      "rationale": "No raw images in NDJSON or spool path replacing cwd/session identity",
      "verification_ids": [
        "VER-003",
        "VER-007",
        "VER-009",
        "VER-010"
      ],
      "evidence_level": "design; no runtime claim"
    },
    "MISSING_TIMEOUT": {
      "status": "CONDITIONAL",
      "rationale": "Retain existing timeouts; filesystem hard deadline and inherited queue budget unresolved pre-promotion",
      "verification_ids": [
        "VER-003",
        "VER-007",
        "VER-009",
        "VER-010"
      ],
      "evidence_level": "design; no runtime claim"
    },
    "UNBOUNDED_RETRY": {
      "status": "PASS",
      "rationale": "A_max2/process burst3/refill.2 retained; no image-specific retries",
      "verification_ids": [
        "VER-003",
        "VER-007",
        "VER-009",
        "VER-010"
      ],
      "evidence_level": "design; no runtime claim"
    },
    "RETRY_STORM": {
      "status": "PASS",
      "rationale": "No post-delivery retry; deterministic invalid image/proof rejects zero spawns",
      "verification_ids": [
        "VER-003",
        "VER-007",
        "VER-009",
        "VER-010"
      ],
      "evidence_level": "design; no runtime claim"
    },
    "THUNDERING_HERD": {
      "status": "PASS",
      "rationale": "No image network poller; serialize config/hash cache refresh",
      "verification_ids": [
        "VER-003",
        "VER-007",
        "VER-009",
        "VER-010"
      ],
      "evidence_level": "design; no runtime claim"
    },
    "UNBOUNDED_QUEUE": {
      "status": "CONDITIONAL",
      "rationale": "No new image queue; inherited32 HTTP/8 slots waiter mismatch escalated",
      "verification_ids": [
        "VER-003",
        "VER-007",
        "VER-009",
        "VER-010"
      ],
      "evidence_level": "design; no runtime claim"
    },
    "MISSING_BACKPRESSURE": {
      "status": "CONDITIONAL",
      "rationale": "Body32MiB/admission64MiB/slots8 retained; decoded memory amplification remains a gate",
      "verification_ids": [
        "VER-003",
        "VER-007",
        "VER-009",
        "VER-010"
      ],
      "evidence_level": "design; no runtime claim"
    },
    "BLOCKING_IO_IN_ASYNC": {
      "status": "PASS",
      "rationale": "No asyncio loop; threaded server; chunked hash and FS profiling required",
      "verification_ids": [
        "VER-003",
        "VER-007",
        "VER-009",
        "VER-010"
      ],
      "evidence_level": "design; no runtime claim"
    },
    "CPU_SPIN_WAIT": {
      "status": "PASS",
      "rationale": "No new polling loops; retry clocks/RNG injected in tests",
      "verification_ids": [
        "VER-003",
        "VER-007",
        "VER-009",
        "VER-010"
      ],
      "evidence_level": "design; no runtime claim"
    },
    "RESOURCE_LEAK": {
      "status": "PASS",
      "rationale": "finally close consumers→rmtree→registry removal→slot release on every terminal path",
      "verification_ids": [
        "VER-003",
        "VER-007",
        "VER-009",
        "VER-010"
      ],
      "evidence_level": "design; no runtime claim"
    },
    "ZOMBIE_SUBPROCESS": {
      "status": "PASS",
      "rationale": "Preserve Run close/process-group termination before spool deletion; no extra process per image",
      "verification_ids": [
        "VER-003",
        "VER-007",
        "VER-009",
        "VER-010"
      ],
      "evidence_level": "design; no runtime claim"
    },
    "RACE_CONDITION": {
      "status": "PASS",
      "rationale": "Unique dirs; registration before mkdir and synchronized sweep; guarded hash/config caches",
      "verification_ids": [
        "VER-003",
        "VER-007",
        "VER-009",
        "VER-010"
      ],
      "evidence_level": "design; no runtime claim"
    },
    "NON_IDEMPOTENT_RETRY": {
      "status": "PASS",
      "rationale": "Stage once and use same files; no retry after delivery",
      "verification_ids": [
        "VER-003",
        "VER-007",
        "VER-009",
        "VER-010"
      ],
      "evidence_level": "design; no runtime claim"
    },
    "BREAKING_CONTRACT": {
      "status": "PASS",
      "rationale": "Exact taxonomy and additive health fields only; preserve cwd/key/native tooling/framing",
      "verification_ids": [
        "VER-003",
        "VER-007",
        "VER-009",
        "VER-010"
      ],
      "evidence_level": "design; no runtime claim"
    },
    "SILENT_DATA_LOSS": {
      "status": "PASS",
      "rationale": "Global markers and all-history files; image-only not PONG; mismatch and spool errors explicit",
      "verification_ids": [
        "VER-003",
        "VER-007",
        "VER-009",
        "VER-010"
      ],
      "evidence_level": "design; no runtime claim"
    },
    "UNHANDLED_UPSTREAM_ERROR": {
      "status": "PASS",
      "rationale": "Keep retry/error semantics; no pretend image content on native view_file decode failure",
      "verification_ids": [
        "VER-003",
        "VER-007",
        "VER-009",
        "VER-010"
      ],
      "evidence_level": "design; no runtime claim"
    },
    "HARDCODED_SECRET": {
      "status": "PASS",
      "rationale": "No secret copied/logged; only supplied public binary SHA and fixed reason codes",
      "verification_ids": [
        "VER-003",
        "VER-007",
        "VER-009",
        "VER-010"
      ],
      "evidence_level": "design; no runtime claim"
    }
  },
  "status_protocol_examples": {
    "client_status_messages": "No synthetic status text added to model answer; status examples are gate protocol only.",
    "gate_pass": "Example only: ARCH_GATE PASS requires actual downstream panel-proof verify exit0 and no unresolved non-waivable stop; not emitted as this run verdict.",
    "gate_blocked": "ARCH_GATE BLOCKED ARCH_STOP_<code>: <evidence>; runtime promotion prohibited until counter-evidence",
    "stop_codes": {
      "ARCH_STOP_HL_ENV_01": {
        "code": "HL-ENV-01",
        "trigger": "Violation or missing deterministic oracle for HL-ENV-01",
        "example": "BLOCKED HL-ENV-01 missing proof/oracle",
        "current": "BLOCKED"
      },
      "ARCH_STOP_C_MULT_I1": {
        "code": "C-MULT-I1",
        "trigger": "Violation or missing deterministic oracle for C-MULT-I1",
        "example": "BLOCKED C-MULT-I1 missing proof/oracle",
        "current": "N/A"
      },
      "ARCH_STOP_C_MULT_I2": {
        "code": "C-MULT-I2",
        "trigger": "Violation or missing deterministic oracle for C-MULT-I2",
        "example": "BLOCKED C-MULT-I2 missing proof/oracle",
        "current": "BLOCKED"
      },
      "ARCH_STOP_C_MULT_I3": {
        "code": "C-MULT-I3",
        "trigger": "Violation or missing deterministic oracle for C-MULT-I3",
        "example": "BLOCKED C-MULT-I3 missing proof/oracle",
        "current": "N/A"
      },
      "ARCH_STOP_C_MULT_I4": {
        "code": "C-MULT-I4",
        "trigger": "Violation or missing deterministic oracle for C-MULT-I4",
        "example": "BLOCKED C-MULT-I4 missing proof/oracle",
        "current": "PASS"
      },
      "ARCH_STOP_C_MULT_I5": {
        "code": "C-MULT-I5",
        "trigger": "Violation or missing deterministic oracle for C-MULT-I5",
        "example": "BLOCKED C-MULT-I5 missing proof/oracle",
        "current": "BLOCKED"
      },
      "ARCH_STOP_S_HERD_I1": {
        "code": "S-HERD-I1",
        "trigger": "Violation or missing deterministic oracle for S-HERD-I1",
        "example": "BLOCKED S-HERD-I1 missing proof/oracle",
        "current": "N/A"
      },
      "ARCH_STOP_S_HERD_I2": {
        "code": "S-HERD-I2",
        "trigger": "Violation or missing deterministic oracle for S-HERD-I2",
        "example": "BLOCKED S-HERD-I2 missing proof/oracle",
        "current": "PASS"
      },
      "ARCH_STOP_S_HERD_I3": {
        "code": "S-HERD-I3",
        "trigger": "Violation or missing deterministic oracle for S-HERD-I3",
        "example": "BLOCKED S-HERD-I3 missing proof/oracle",
        "current": "PASS"
      },
      "ARCH_STOP_S_HERD_I4": {
        "code": "S-HERD-I4",
        "trigger": "Violation or missing deterministic oracle for S-HERD-I4",
        "example": "BLOCKED S-HERD-I4 missing proof/oracle",
        "current": "N/A"
      },
      "ARCH_STOP_S_HERD_I5": {
        "code": "S-HERD-I5",
        "trigger": "Violation or missing deterministic oracle for S-HERD-I5",
        "example": "BLOCKED S-HERD-I5 missing proof/oracle",
        "current": "PASS"
      },
      "ARCH_STOP_H_CPU_I1": {
        "code": "H-CPU-I1",
        "trigger": "Violation or missing deterministic oracle for H-CPU-I1",
        "example": "BLOCKED H-CPU-I1 missing proof/oracle",
        "current": "PASS"
      },
      "ARCH_STOP_H_CPU_I2": {
        "code": "H-CPU-I2",
        "trigger": "Violation or missing deterministic oracle for H-CPU-I2",
        "example": "BLOCKED H-CPU-I2 missing proof/oracle",
        "current": "PASS"
      },
      "ARCH_STOP_H_CPU_I3": {
        "code": "H-CPU-I3",
        "trigger": "Violation or missing deterministic oracle for H-CPU-I3",
        "example": "BLOCKED H-CPU-I3 missing proof/oracle",
        "current": "PASS"
      },
      "ARCH_STOP_H_CPU_I4": {
        "code": "H-CPU-I4",
        "trigger": "Violation or missing deterministic oracle for H-CPU-I4",
        "example": "BLOCKED H-CPU-I4 missing proof/oracle",
        "current": "N/A"
      },
      "ARCH_STOP_H_CPU_I5": {
        "code": "H-CPU-I5",
        "trigger": "Violation or missing deterministic oracle for H-CPU-I5",
        "example": "BLOCKED H-CPU-I5 missing proof/oracle",
        "current": "BLOCKED"
      },
      "ARCH_STOP_R_BULK_I1": {
        "code": "R-BULK-I1",
        "trigger": "Violation or missing deterministic oracle for R-BULK-I1",
        "example": "BLOCKED R-BULK-I1 missing proof/oracle",
        "current": "BLOCKED"
      },
      "ARCH_STOP_R_BULK_I2": {
        "code": "R-BULK-I2",
        "trigger": "Violation or missing deterministic oracle for R-BULK-I2",
        "example": "BLOCKED R-BULK-I2 missing proof/oracle",
        "current": "PASS"
      },
      "ARCH_STOP_R_BULK_I3": {
        "code": "R-BULK-I3",
        "trigger": "Violation or missing deterministic oracle for R-BULK-I3",
        "example": "BLOCKED R-BULK-I3 missing proof/oracle",
        "current": "N/A"
      },
      "ARCH_STOP_R_BULK_I4": {
        "code": "R-BULK-I4",
        "trigger": "Violation or missing deterministic oracle for R-BULK-I4",
        "example": "BLOCKED R-BULK-I4 missing proof/oracle",
        "current": "N/A"
      },
      "ARCH_STOP_R_BULK_I5": {
        "code": "R-BULK-I5",
        "trigger": "Violation or missing deterministic oracle for R-BULK-I5",
        "example": "BLOCKED R-BULK-I5 missing proof/oracle",
        "current": "N/A"
      }
    }
  },
  "architect_oracles": {
    "AO-01": "Flag/proof/catalog: independent default false; invalid/missing config false, env off overrides immediately, TTL<=1s FakeClock. Two target/four unsupported models. Mutate SHA/version/formats/effort individually =>400/no spawn, zero-image text succeeds. Binary hash reads<=1048576 and unchanged stat hashes once under concurrent checks; changing identity invalidates cache. Full24 combo matrix evidence before promotion.",
    "AO-02": "Validation: exact strict order AD-002, known PNG/JPEG/GIF/WebP signatures, types not max_types, MIME mismatch taxonomy,16/17 count and20MiB/+1 individual/total boundaries,32MiB/+1 body. Zero-image fast path flag/stat/hash/uuid/spool call_count0. Every malformed part rejected before disk writes/CLI.",
    "AO-03": "Global history: cold/image-only/old rejected history with no assistant/hot text/hot new images. All markers1..K map distinct fixture digests; resumed subset retains global numbers and lists only msg_index>last_asst; no attachments on pure text hot slice; full history includes all images.",
    "AO-04": "Run/session: unchanged model/cwd/effort key, spaces/Unicode exact argv --add-dir/path, Popen user cwd, relative project read. Explicit cid separate from auto-hot. Plain/background/concurrent model/cwd/effort identities isolated; no shared img_dir.",
    "AO-05": "Staging: pre-slot path allocation only; queued requests no mkdir/write. After slot register before mkdir0700, files O_EXCL0600, descriptors closed before Run; allK staged once before retry loop; data refs cleared after write. During each attempt same file digests and full prompt references resolvable; active spool<=8*20MiB excluding orphan backlog.",
    "AO-06": "Lifecycle: success, generic error, exception, disconnect, launcher unavailable, no slot, ENOSPC at second file. No partial spawn on spool error; state/error500 image_spool_error; 50 abort cycles leave files/active set/slot counts baseline; consumers closed before deletion. No retry after delivered reasoning/content/tools.",
    "AO-07": "Sweeper FakeClock: stale orphan run-/img- deleted only age>3600s; exact3600/fresh/nonmatching/symlink targets untouched. Active older than3600 protected; two parallel turns independent and registration/sweep race deterministic interleaving safe.",
    "AO-08": "Logs: all13 canonical tokens exact via allowlist; reject payload anchored regex reason/model/model_len/client; image_proof_invalid safe reason. Synthetic AUTH_KEY/base64 marker not in any sink; _SECRET regex remains active for other>=24char tokens.",
    "AO-09": "Resilience/resources: preserve2 attempts, burst3,.2/request credit and full-jitter existing retry policy; 100 requests<=23 retries, no delivery retry. RES-01 profile all32 admitted/8 active including queued encoded+decoded copies, peak parent/child RSS separately, FD/launchd limit, CPU/time and ports; arithmetic target208<=409.6 only becomes true bound with independent measurements/accounting. Flag-off/proof mismatch leave text-only and existing reasoning/SSE/auth/admission unchanged.",
    "AO-10": "Frozen QA/scope plus live L3: all40 IMG/HIST/LIFE/LOG/RES/AO tests assert; test file additive0deleted, root strict suite unchanged/passes; exactly three product files, analysis5 hashes unchanged, dynamic_config untracked. Teamlead hashes deployed pair and verifies two distinct real images then text-only in SAME existing owner chat :9887 with native view_file fresh paths, actual correct answers, cwd, cleanup, repeated+parallel/cold/hot/fallback and format-effort matrix; no crash/SIGABRT reports. NOT RUN in Stage2."
  },
  "semantic_checks": {
    "canonical_hl_field_set": "46/46 exact keys in fields/units/sources parsed from SSoT",
    "memory_closure": "208<=409.6 algebra PASS; strict RSS bound UNPROVEN EVD-036; production blocked pending RES-01",
    "stop_codes": "21 canonical codes +3 lifecycle/isolation checks; unresolved resource/baseline evidence is BLOCKED; N/A scoped to image delta with proof obligations",
    "legacy_antipatterns": "21 keys",
    "verification_owner": "Verifier6 Teamlead4, no Coder",
    "decisions": "6 two-way APPROVED approval_required false; no panel acceptance implied",
    "na_proof": "Every N/A has actual current diff + baseline fingerprint + proposed transitive graph and future candidate recheck; excludes native CLI upstream from waiver",
    "schema_vs_semantics": "Validators enforce structure/ref integrity, not empirical vision or resource bounds",
    "quality_gates": "Pinned gates frozen; no product tests executed here",
    "timing_budget": "TTL<=1.0s next request evaluation; strictly<1.0s and active-turn interruption are NOT proven/promised"
  },
  "handoff_state": {
    "next_role": "Parent Orchestrator → external3-family ARCH_PANEL; Coder only after valid panel-proof. Resource/promotion blockers stay explicit.",
    "coder_must_read": [
      "architecture/architecture-packet.json AD-001..006 AO-01..10",
      "analysis/agy-image-input-fix/handoff-qa.md",
      "all5 frozen analysis files"
    ],
    "red_green": "Add regression tests before fix; all original resilience assertions retained; no broader scope edits",
    "production_promotion_blockers": [
      "Full24 combination model/effort/format verification evidence",
      "Retained-buffer memory proof including pre-slot waiters; peak parent+children RSS separately",
      "Measured CPU/RPS/FD/launchd limit/upstream profile and inherited queue/waiter budget disposition by parent",
      "Real L3 original owner chat and paired runtime hashes"
    ]
  },
  "role_plan": {
    "path": "plans/architect-01.json",
    "sha256": "1abb6d6c834c93876a5565b2e89df051deb836ad9f608de185ee2914d9c5d57a"
  }
}
```

### 3.2. `plans/architect-01.json`
```json
{
  "schema_version": "1.0",
  "run_id": "agy-image-input-fix-20261029",
  "task_id": "agy-image-input-fix",
  "role": "architect",
  "iteration": 1,
  "plan_kind": "full",
  "objective": "Finalize auditable Stage2 image-input architecture candidate and three allowlisted JSONs; frozen inputs and product fingerprint unchanged.",
  "inputs_read": [
    "~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/architecture.md",
    "analysis/agy-image-input-fix/research-plan.md sha256=67f3bfffc4e9df6b95ee8571c34ded4a397ad164f86787b3b935fe51dcf1243a",
    "analysis/agy-image-input-fix/evidence-ledger.md sha256=aba34816b5cf6425d4fbf19187a09edd5f7158797e442d488d68626576f887a9",
    "analysis/agy-image-input-fix/open-questions.md sha256=63fe13ce25d80cb7bad68d25a57c8d1d6e58847b5b8be79dc395b555c55e5b76",
    "analysis/agy-image-input-fix/handoff-architect.md sha256=6c22f4a0ab4fc71d2e7cd88e1fe7d2df8c327193eb75bfc9d922af68a4710a8f",
    "analysis/agy-image-input-fix/handoff-qa.md sha256=007cdac728cdd6754c6617cd749ed3361f0d19c9e1adae16a3c31a90ee352cee",
    "Owner Role Brief Stage2",
    "Prior accepted packet JSON schema only"
  ],
  "scope_paths": [
    ".ai-team/runs/agy-image-input-fix-20261029/plans/architect-01.before.json",
    ".ai-team/runs/agy-image-input-fix-20261029/plans/architect-01.json",
    ".ai-team/runs/agy-image-input-fix-20261029/architecture/architecture-packet.json"
  ],
  "stop_conditions": [
    "No writes except3 JSONs; generator only /tmp/cel-runs/agy-image-input-fix-20261029",
    "Frozen SHA mismatch, invalid role/packet schema or changed product fingerprint forbids handoff",
    "No panel vote/runtime PASS or unmeasured resource bound may be fabricated"
  ],
  "steps": [
    {
      "id": "RP-01",
      "kind": "inspect",
      "action": "Read frozen5 SystemAnalyst inputs and role architecture canon; verify supplied SHA256 list",
      "expected_evidence": "All5 exact SHA256 values; trace REQ001..010 and supplied facts",
      "status": "DONE",
      "actual_evidence": "Five frozen hashes verified by generator; role SSoT46 table keys parsed; analysis facts F01..34 retained with supplied host evidence distinguished."
    },
    {
      "id": "RP-02",
      "kind": "decide",
      "action": "Define6 two-way image decisions plus quality/boundary/contracts/threats/resource obligations",
      "expected_evidence": "AD001..006;46 canonical fields;21+3 stop codes;10 frozen Verifier/Teamlead gates",
      "status": "DONE",
      "actual_evidence": "Six specified ADs,10 REQs/QAs,6 boundaries,5 contracts,4 views,14 risks,5 threats,8 assumptions,10 gates/AOs produced. Memory arithmetic conditional; full resource proof not fabricated."
    },
    {
      "id": "RP-03",
      "kind": "report",
      "action": "Materialize only three authorized JSONs and link completed role plan SHA in packet",
      "expected_evidence": "Deterministic valid JSON and plan-reference SHA; no product changes",
      "status": "DONE",
      "actual_evidence": "Exactly three allowlisted artifacts generated; role plan hash linked. Four mandatory external validators executed by caller after generation; their actual results are reported separately, not preclaimed here."
    }
  ],
  "deviations": [
    "3-minute requested deadline exceeded while reading required canon/schema and producing complete packet; no repo scan/product tests performed.",
    "Cannot prove64MiB body admission bounds JSON/base64/decoded copies waiting before slots. Requested208<=409.6 arithmetic PASS explicitly conditional, runtime upper bound unproven; production gate blocked.",
    "Confirmed fleet structure is target post-matrix state; one PNG/Argon/low probe does not justify fabricated proofs for all24 combos.",
    "TTL1s implies <=1s next-check cache bound, not strict<1s; flag not retroactive cancel of accepted runs.",
    "Local dynamic_config source is explicit Stage2 override of global GigaRC source; no claim of GigaRC integration.",
    "Inherited queue1800 vs30%p99 target and possible24 waiters>2*8 remain unresolved pre-promotion findings, not silently waived."
  ]
}
```

### 3.3. `teamlead/verification-surface.json`
```json
{
  "architecture_packet_sha256": "ddcbc69fd277d74079d3868eb245a3c05c7d7ea00ddae6369fdc563982433466",
  "verifications": []
}
```

### 3.4. `analysis/agy-image-input-fix/handoff-architect.md`
```markdown
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
```

### 3.5. `analysis/agy-image-input-fix/evidence-ledger.md`
```markdown
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
PANEL-NONCE: d356e9006d8c8956
ARTIFACT-SHA256: ddcbc69fd277d74079d3868eb245a3c05c7d7ea00ddae6369fdc563982433466
ОБЩИЙ ВЕРДИКТ: PASS|NEEDS WORK|RED FLAG
Первыми двумя строками ответа выведи дословно «PANEL-NONCE: d356e9006d8c8956» и «ARTIFACT-SHA256: ddcbc69fd277d74079d3868eb245a3c05c7d7ea00ddae6369fdc563982433466».
Перед финальной строкой вердикта выведи:
COVERAGE: 6/6 подкатегорий
FINDINGS_COMPLETE: <число>
И самой последней строкой ответа выведи ровно одну строку:
ОБЩИЙ ВЕРДИКТ: PASS|NEEDS WORK|RED FLAG


---
Инструкция судье: первыми двумя строками ответа повтори дословно «PANEL-NONCE: d356e9006d8c8956» и «ARTIFACT-SHA256: ddcbc69fd277d74079d3868eb245a3c05c7d7ea00ddae6369fdc563982433466».
