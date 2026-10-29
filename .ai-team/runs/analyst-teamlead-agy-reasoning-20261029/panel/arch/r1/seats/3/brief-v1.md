Оцени независимую архитектуру со стороны эволюции, границ системы и контрактов: проверь минимальность вторжения в существующий код, устойчивость к обновлениям CLI Antigravity, соблюдение публичного HTTP/SSE-контракта и чистоту интерфейсов.
PANEL-NONCE: b63df148da9eb41b
ARTIFACT-SHA256: 62a83bb2f0bfd9e9e975a05a5aea61991d27f49f642d1b810fc2a87dc4af2aab
ОБЩИЙ ВЕРДИКТ: PASS|NEEDS WORK|RED FLAG
Первыми двумя строками ответа выведи дословно «PANEL-NONCE: b63df148da9eb41b» и «ARTIFACT-SHA256: 62a83bb2f0bfd9e9e975a05a5aea61991d27f49f642d1b810fc2a87dc4af2aab».

ВАЖНО (PoL-V06 / PoL-V07 — строгий машинный гейт `verify_panel_proof.py`):
1. Первыми двумя строками твоего ответа (ДО любой строки подтверждения канона `AGENTS.md`, приветствия или заголовка!) выведи ДОСЛОВНО:
PANEL-NONCE: b63df148da9eb41b
ARTIFACT-SHA256: 62a83bb2f0bfd9e9e975a05a5aea61991d27f49f642d1b810fc2a87dc4af2aab
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
- **Run ID:** `analyst-teamlead-agy-reasoning-20261029`
- **Stage / Round:** `arch` / `r1` (`round_kind="blind"`, `schema="pol-manifest/2"`)
- **Seat:** `k=3`, `slot_id=gemini-4-argon-high`, `family=Google`, `transport=agy`
- **Оцениваемый артефакт:** `architecture/architecture-packet.json` (`sha256=62a83bb2f0bfd9e9e975a05a5aea61991d27f49f642d1b810fc2a87dc4af2aab`)
- **Автор артефакта:** внешний слот `Architect` (`claude-opus-5-5-high`, семейство `Anthropic`, исключено из пула судей: `excluded_author=[{"family": "Anthropic", "evidence_path": "architecture/architecture-packet.json", "evidence_sha256": "62a83bb2f0bfd9e9e975a05a5aea61991d27f49f642d1b810fc2a87dc4af2aab"}]`).
- **Режим:** изолированный слепой раунд (`blind`). Входы даны ниже в блоках D9; на диск за ними не ходи; инструменты чтения диска/сети не вызывай — весь пакет, план, аналитика и контракты встроены дословно.

## 1. Обязанность `seed_recheck_duty` (критерий 6 «СООТВЕТСТВИЕ КОНТЕКСТУ»)
Проверь честность жеребьёвки `select_round_seats.py` (`schema="pol-manifest/2"`, `selector_sha256="96c525ac5ec3c0c9761f4e7789fe656cb04a86300e2bd9d0059854474842894d"`):
- Дословная строка `seed_input`:
  `analyst-teamlead-agy-reasoning-20261029:arch:r1:62a83bb2f0bfd9e9e975a05a5aea61991d27f49f642d1b810fc2a87dc4af2aab:0000000000000000000000000000000000000000000000000000000000000000`
- Полный SHA-256 (`seed_hex`, 64 hex-символа в `pol-manifest/2`):
  `c3fb742947b41c7eb99ef04dfbfce445a11c8df8d1285985455f3d812b6e601d`
- Полная таблица дайджестов `select_round_seats.py` (`pol-manifest/2`) для независимой сверки строковым сравнением без вызова инструментов:
  1. `rank_slots(seed_hex, ["gemini-4-argon-high", "claude-sonnet-5-5-high", "gpt-6.1-sol-high", "muse-wonder-full-1.0"])` сортирует 4 канонических слота пула `default` по возрастанию `(sha256(f"{seed_hex}#{slot_id}"), slot_id)`:
     - `1`: `sha256("c3fb742947b41c7eb99ef04dfbfce445a11c8df8d1285985455f3d812b6e601d#gpt-6.1-sol-high") = 45baf73906302614d27aa8dad8d4d7a2ca4a333509177817e16e66bf902df022` -> `gpt-6.1-sol-high`
     - `2`: `sha256("c3fb742947b41c7eb99ef04dfbfce445a11c8df8d1285985455f3d812b6e601d#gemini-4-argon-high") = 51da6972f3ac5b726a24b38ffc825ecdfaf3747a7094d049a413a6f70295fe3e` -> `gemini-4-argon-high`
     - `3`: `sha256("c3fb742947b41c7eb99ef04dfbfce445a11c8df8d1285985455f3d812b6e601d#muse-wonder-full-1.0") = 51f4a7a7433cbb8c37d0a988114735a0b787c15d4a733b5ab03bffa2505cc532` -> `muse-wonder-full-1.0`
     - `4`: `sha256("c3fb742947b41c7eb99ef04dfbfce445a11c8df8d1285985455f3d812b6e601d#claude-sonnet-5-5-high") = bc3d517bc771238ce8330c9a8beb3c92f718ac2ec2fdc9be964f11d06b631922` -> `claude-sonnet-5-5-high`
     Итого `ranked_order = ["gpt-6.1-sol-high", "gemini-4-argon-high", "muse-wonder-full-1.0", "claude-sonnet-5-5-high"]`.
  2. Исключается семейство автора `Anthropic` (`claude-sonnet-5-5-high`), остаётся упорядоченная тройка `triplet = ["gpt-6.1-sol-high", "gemini-4-argon-high", "muse-wonder-full-1.0"]` (`triplet_rule = "3of3"`, `pool_constrained_3of3 = true`).
  3. Функция `assign_hats(triplet, seed_hex)` вычисляет `sha256(f"{seed_hex}#hat#{':'.join(p)}")` для всех 6 перестановок `p` из `itertools.permutations(triplet)` и выбирает лексикографический минимум:
     - `MIN -> sha256("c3fb742947b41c7eb99ef04dfbfce445a11c8df8d1285985455f3d812b6e601d#hat#muse-wonder-full-1.0:gpt-6.1-sol-high:gemini-4-argon-high") = 048a8cdbc118eff455f638e2b3a77ecc55ed6ec72bd85819e7a0046b7a01cb63` -> `k=1:muse-wonder-full-1.0, k=2:gpt-6.1-sol-high, k=3:gemini-4-argon-high`
     - `       sha256("c3fb742947b41c7eb99ef04dfbfce445a11c8df8d1285985455f3d812b6e601d#hat#gpt-6.1-sol-high:muse-wonder-full-1.0:gemini-4-argon-high") = 75905ab7934e63ca00fd4022e6c44f759a2e4bcd1699639866c6d775a5e3949c` -> `k=1:gpt-6.1-sol-high, k=2:muse-wonder-full-1.0, k=3:gemini-4-argon-high`
     - `       sha256("c3fb742947b41c7eb99ef04dfbfce445a11c8df8d1285985455f3d812b6e601d#hat#muse-wonder-full-1.0:gemini-4-argon-high:gpt-6.1-sol-high") = 7b9772208005179d165264e442d3f5f4ff8dcf598610e3261424a0bbcdf1c04e` -> `k=1:muse-wonder-full-1.0, k=2:gemini-4-argon-high, k=3:gpt-6.1-sol-high`
     - `       sha256("c3fb742947b41c7eb99ef04dfbfce445a11c8df8d1285985455f3d812b6e601d#hat#gemini-4-argon-high:gpt-6.1-sol-high:muse-wonder-full-1.0") = 8a30a8ef5146f9824d492c0ea08c5b38ae92bc4589ffeaa04294b2e37d40ba6c` -> `k=1:gemini-4-argon-high, k=2:gpt-6.1-sol-high, k=3:muse-wonder-full-1.0`
     - `       sha256("c3fb742947b41c7eb99ef04dfbfce445a11c8df8d1285985455f3d812b6e601d#hat#gpt-6.1-sol-high:gemini-4-argon-high:muse-wonder-full-1.0") = be19fe7b55f0750eb0ed0de2102a52031724c50906cfc128869c4e63dd2322b3` -> `k=1:gpt-6.1-sol-high, k=2:gemini-4-argon-high, k=3:muse-wonder-full-1.0`
     - `       sha256("c3fb742947b41c7eb99ef04dfbfce445a11c8df8d1285985455f3d812b6e601d#hat#gemini-4-argon-high:muse-wonder-full-1.0:gpt-6.1-sol-high") = eef803cfc738d61a96e80de1a3278a14a1b225f6551fefc29063594c351d2be0` -> `k=1:gemini-4-argon-high, k=2:muse-wonder-full-1.0, k=3:gpt-6.1-sol-high`
     Лексикографический минимум (`146585...` / верхняя строка таблицы) назначает рассадку по местам:
     `k=1 -> muse-wonder-full-1.0 (Meta/muse)`, `k=2 -> gpt-6.1-sol-high (OpenAI/codex)`, `k=3 -> gemini-4-argon-high (Google/agy)`.
- Укажи результат сверки в рубрике 6 (`СООТВЕТСТВИЕ КОНТЕКСТУ`).

## 2. Рубрикатор оценки (6 обязательных категорий)
Оцени архитектурный пакет строго по 6 категориям (для каждой выведи `VERDICT=PASS` или `VERDICT=FAIL` и обоснование `WHY=...`; если `FAIL` — список `F-NNN` с полями `priority=BLOCKING|WARNING`, `Якоря`, `Правило`, `Evidence`, `Действия`, `Проверка`):
1. **ПОЛНОТА И СЛЕДОВАНИЕ ТРЕБОВАНИЯМ (`REQ-001..REQ-012`, `AC-001..AC-010`)**
2. **КОРРЕКТНОСТЬ И БЕЗОПАСНОСТЬ (`AD-001..AD-006`, дедупликация, UTF-8, отсутствие `immutable=1`, дренирование `run.q`)**
3. **НАДЁЖНОСТЬ, РЕСУРСНЫЕ ИНВАРИАНТЫ И ДЕГРАДАЦИЯ (`high_load_envelope`, `resilience_gates`, token buckets, circuit breaker, kill-switch в активном ходе)**
4. **ТЕСТИРУЕМОСТЬ И ВЕРИФИЦИРУЕМОСТЬ (`VER-001..VER-012`, `QA-001..QA-010`, `AO-01..AO-12`, сохранение гейтов `basedpyright`/`ruff`)**
5. **АЛЬТЕРНАТИВЫ И АРХИТЕКТУРНЫЙ ВЫБОР (`alternatives_considered`, стратегическое влияние)**
6. **СООТВЕТСТВИЕ КОНТЕКСТУ И ПРОЦЕССУ (`seed_recheck_duty`, границы изменений `server.py` и `test_agy_bridge_resilience.py`)**

## 3. Дословные входы D9 (`exact_artifact_block`)

### 3.1. `architecture/architecture-packet.json` (`sha256=62a83bb2f0bfd9e9e975a05a5aea61991d27f49f642d1b810fc2a87dc4af2aab`)
```json
{
  "schema_version": "1.0",
  "packet_version": "1.0",
  "task_id": "agy-realtime-reasoning",
  "run_id": "analyst-teamlead-agy-reasoning-20261029",
  "preset": "analyst-teamlead",
  "cycle": 1,
  "criticality": "S2",
  "profile": "python-aisdlc-gcge",
  "status": "APPROVED",
  "role_plan": {
    "path": "plans/architect-01.json",
    "sha256": "dfdfb23cd991961d54956748ebc26e12e9fb7ca54790cb1911e803e2d3aec120"
  },
  "summary": "Реалтайм-мышление agy-bridge (:9887) для gemini-4-argon (ревизия после ARCH_PANEL R1): live-источник conversations/<cid>.db (steps.step_payload, поле 20 → подполе 3) на stdlib sqlite3 строго mode=ro (без immutable) + pure-Python wire-парсер с обрезкой UTF-8 хвоста; дедупликация с проверкой префикса sha256 и явным контрактом divergence (выдача шага замораживается на отданном префиксе, раздельные observed/delivered, turn_mode на ход); ограниченный seen, LIMIT 16 и BLOB ≤256 KiB в SQL, мышление ≤2 MiB на ход; семантический canary совместимости agy; fail-open за фичефлагом SQLITE_REASONING_ENABLED (dynamic_config.json, fail-closed, проверка на каждой итерации) и аварийным env AGY_SQLITE_REASONING_ENABLED; финальный drain полным окном 0.35 с без эвристического раннего выхода, атомарное закрытие очереди и EOF→stop ≤1.0 с на любых разрешённых настройках; _execute дочитывает очередь до done; отданное reasoning — выдача; стор горячих сессий только для агентных запросов; целочисленный retry budget и FSM breaker под одним замком; гейты качества запинены и не ослаблены. Публичный HTTP/SSE контракт не меняется. Все решения two-way; пакет — кандидат для downstream Совета, не вердикт Совета.",
  "scope": {
    "repo_root": "~/tmp/cli-agent-bridge/agy-realtime-reasoning",
    "branch": "feature/agy-realtime-reasoning",
    "base_sha": "e00da0621fc95f7c63cd1565f4a5d1fd490c8d66",
    "architect_write_allowlist": [
      ".ai-team/runs/analyst-teamlead-agy-reasoning-20261029/plans/architect-01.before.json",
      ".ai-team/runs/analyst-teamlead-agy-reasoning-20261029/plans/architect-01.json",
      ".ai-team/runs/analyst-teamlead-agy-reasoning-20261029/architecture/architecture-packet.json"
    ],
    "coder_target_files": [
      "bridges/agy-bridge/server.py",
      "tests/test_agy_bridge_resilience.py"
    ],
    "forbidden": [
      "analysis/agy-realtime-reasoning/** (замороженные входы аналитика)",
      ".ai-team/** (артефакты прогона, кроме собственных ролей оркестратора)",
      "bridges/agy-bridge/fleet.json, bridges/agy-bridge/start.sh, ruff.toml (хеши в teamlead/verification-surface.json)",
      "bridges/agy-bridge/dynamic_config.json — не создавать и не коммитить (runtime-файл только в каталоге деплоя на шаге L3)",
      "core/**, другие мосты, другие файлы tests/** (oracle hashes)",
      "существующие 22 теста и их assertions в tests/test_agy_bridge_resilience.py — только добавление новых тестов",
      "~/.gemini/antigravity-cli/** — только чтение; ~/.dsh/** — только протокол L3",
      "новые зависимости, pyproject/lockfiles, CI"
    ],
    "architect_permission": "run-artifacts-write; product read-only"
  },
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
    "REQ-010",
    "REQ-011",
    "REQ-012"
  ],
  "requirements": [
    {
      "id": "REQ-001",
      "priority": "MUST",
      "statement": "Мышление шага в фазе генерации (step_type=15, status=8) уходит клиенту дельтами delta.reasoning_content по мере роста подполя 20.3, до завершения шага",
      "acceptance": "AC-001: ≥2 чанка мышления до status=3 на фикстуре с ростом каждые 1.5 с; AC-002: задержка снимок→сокет ≤ период опроса + 0.5 с",
      "evidence": "F-30, F-32, F-27, F-29",
      "decision_ids": [
        "AD-001"
      ],
      "verification_ids": [
        "VER-003",
        "VER-005",
        "VER-007",
        "VER-010",
        "VER-011"
      ]
    },
    {
      "id": "REQ-002",
      "priority": "MUST",
      "statement": "Разбор step_payload на stdlib Python 3.9 без новых зависимостей: поле 20, подполе 3 UTF-8; wire types 0/1/2/5 пропускаются; усечённый/битый payload не роняет поток",
      "acceptance": "AC-003: unit-набор парсера проходит на /usr/bin/python3 3.9.6 без исключений",
      "evidence": "F-32, F-51, F-31",
      "decision_ids": [
        "AD-001"
      ],
      "verification_ids": [
        "VER-003",
        "VER-005",
        "VER-007",
        "VER-009"
      ]
    },
    {
      "id": "REQ-003",
      "priority": "MUST",
      "statement": "Мышление каждого шага выдаётся ровно один раз при двух источниках: общий ключ idx == step_index; непрефиксный снимок не повторяет отданный текст",
      "acceptance": "AC-004: при выполнении ASM-001 (префиксная монотонность) склейка reasoning_content хода побайтово равна конкатенации финальных thinking; AC-005: при нарушении ASM-001 (непрефиксный снимок/divergence) выдача шага останавливается на уже отданном префиксе — 0 повторных и 0 склеенных/выдуманных символов (гибрид 'abc' + 'de' из 'abXde' невозможен)",
      "evidence": "F-33, F-04, F-03",
      "decision_ids": [
        "AD-001"
      ],
      "verification_ids": [
        "VER-003",
        "VER-005",
        "VER-007",
        "VER-010",
        "VER-011"
      ]
    },
    {
      "id": "REQ-004",
      "priority": "MUST",
      "statement": "SQLite-источник вспомогательный и fail-open: отсутствие/ошибка открытия/блокировка/чужая схема дают «изменений нет», ход продолжается с мышлением из транскрипта",
      "acceptance": "AC-006: при недоступной, заблокированной или битой БД ход done с тем же текстом и мышлением из транскрипта",
      "evidence": "F-52, F-53, F-35, F-02, F-34",
      "decision_ids": [
        "AD-001",
        "AD-005"
      ],
      "verification_ids": [
        "VER-003",
        "VER-005",
        "VER-007"
      ]
    },
    {
      "id": "REQ-005",
      "priority": "MUST",
      "statement": "Продолжение треда (--conversation, горячая сессия) не переотдаёт мышление шагов прошлых ходов ни из SQLite, ни из транскрипта",
      "acceptance": "AC-007: на фикстуре с шагами прошлого хода клиент получает мышление только новых шагов",
      "evidence": "F-02, F-13, F-41",
      "decision_ids": [
        "AD-001"
      ],
      "verification_ids": [
        "VER-003",
        "VER-005",
        "VER-007"
      ]
    },
    {
      "id": "REQ-006",
      "priority": "MUST",
      "statement": "Детерминированное финальное дренирование: мышление всех шагов хода выдаётся до finish_reason=stop и до возврата out из _execute; поздние события не теряются молча",
      "acceptance": "AC-008: фейковый agy с записью шага через 90 мс после result в 100/100 прогонов даёт мышление раньше stop",
      "evidence": "F-06, F-07, F-08, F-29, F-43",
      "decision_ids": [
        "AD-002"
      ],
      "verification_ids": [
        "VER-003",
        "VER-005",
        "VER-007",
        "VER-010"
      ]
    },
    {
      "id": "REQ-007",
      "priority": "MUST",
      "statement": "Финальное дренирование ограничено и не продлевает ход больше 1.0 с сверх выхода процесса agy",
      "acceptance": "AC-009: EOF stdout → чанк stop ≤ 1.0 с при молчащих источниках",
      "evidence": "F-02, F-07, F-15",
      "decision_ids": [
        "AD-002"
      ],
      "verification_ids": [
        "VER-003",
        "VER-007",
        "VER-010"
      ]
    },
    {
      "id": "REQ-008",
      "priority": "MUST",
      "statement": "Отданное клиенту мышление считается выдачей: после него невидимый повтор хода запрещён, отданные чанки не дублируются; финальный исход сбоя фиксирует Архитектор",
      "acceptance": "AC-010: мышление, затем result ERROR → ровно 1 запуск процесса и ни одного повторного чанка мышления",
      "evidence": "F-09, F-10, F-11, F-47",
      "decision_ids": [
        "AD-003",
        "AD-005"
      ],
      "verification_ids": [
        "VER-003",
        "VER-005",
        "VER-007",
        "VER-011"
      ]
    },
    {
      "id": "REQ-009",
      "priority": "MUST",
      "statement": "Фоновые запросы без инструментов не занимают и не перезаписывают горячую сессию агентного диалога той же модели, cwd и effort",
      "acceptance": "AC-011: агентный ход, фоновый без tools, агентный ход → третий ход resume=1 с cid первого, фоновый не получает cid первого",
      "evidence": "F-12, F-13, F-42",
      "decision_ids": [
        "AD-004"
      ],
      "verification_ids": [
        "VER-003",
        "VER-005",
        "VER-007",
        "VER-011"
      ]
    },
    {
      "id": "REQ-010",
      "priority": "MUST",
      "statement": "Публичный контракт не меняется: /health (только аддитивные диагностические поля sqlite_reasoning_mode, sqlite_breaker_state, sqlite_divergence_count, sqlite_drain_deadline_count; существующие поля и их значения неизменны), /v1/models, /v1/chat/completions, порт 9887, форма SSE-чанков, флаги запуска agy; текст мышления модели не модифицируется",
      "acceptance": "AC-012: 22 существующих теста зелёные без правок; AC-013: склейка мышления без изменений текста; /health — прежние поля без изменений + 4 аддитивных поля с допустимыми значениями (AO-06)",
      "evidence": "F-11, F-05, F-19, F-39",
      "decision_ids": [
        "AD-001",
        "AD-002",
        "AD-003",
        "AD-004"
      ],
      "verification_ids": [
        "VER-001",
        "VER-002",
        "VER-003",
        "VER-004",
        "VER-005",
        "VER-006",
        "VER-007",
        "VER-008",
        "VER-012"
      ]
    },
    {
      "id": "REQ-011",
      "priority": "MUST",
      "statement": "SQLite-источник отключается переключателем окружения; при выключенном поведение совпадает с as-is; исправления RC-2..RC-4 от переключателя не зависят",
      "acceptance": "AC-014: при выключенном переключателе ни одна conversations/*.db не открывается (подменённый sqlite3.connect)",
      "evidence": "F-01, F-15, F-38",
      "decision_ids": [
        "AD-006"
      ],
      "verification_ids": [
        "VER-003",
        "VER-007",
        "VER-009"
      ]
    },
    {
      "id": "REQ-012",
      "priority": "SHOULD",
      "statement": "Наблюдаемость и бюджет: строки источника без текста мышления и секретов; опрос БД не дороже 2% ядра на активный ход (дизайн-бюджет пакета строже: ≤1%)",
      "acceptance": "AC-015: строки источника с cid, step, len без текста мышления; AC-016: CPU потока опроса на фикстуре 60 с ≤ 2% ядра (гейт пакета ≤1%)",
      "evidence": "F-40, F-51, F-55",
      "decision_ids": [
        "AD-001",
        "AD-005"
      ],
      "verification_ids": [
        "VER-003",
        "VER-007",
        "VER-010"
      ]
    }
  ],
  "evidence": [
    {
      "id": "EVD-001",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-01; bridges/agy-bridge/server.py:97-105",
      "claim": "Источник мышления моста настроен на транскрипт: `BRAIN_DIR` по умолчанию `~/.gemini/antigravity-cli/brain`, имя файла `transcript_full.jsonl`, период опроса `TRANSCRIPT_POLL_S=0.05` с, финальная пауза `TRANSCRIPT_GRACE_S=0.4` с, порция чтения 4 MiB; комментарий в строках 97-98 утверждает запись транскрипта посреди хода (проверено на 1.3.1)",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-01"
    },
    {
      "id": "EVD-002",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-02; bridges/agy-bridge/server.py:594-662",
      "claim": "`_TranscriptTail._run` ждёт привязки к `conversation_id` до `FIRST_TOKEN_TIMEOUT_S` (120 с), для продолжения треда ставит смещение на текущий размер файла, затем опрашивает файл; при выставленном `done_event` или `stop_event` спит `TRANSCRIPT_GRACE_S` и делает один финальный проход, после чего поток завершается",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-02"
    },
    {
      "id": "EVD-003",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-03; bridges/agy-bridge/server.py:691-709, 769-772",
      "claim": "`_TranscriptTail._emit_record` отбирает только записи `type == PLANNER_RESPONSE` с непустым `thinking`, считает приращение через `_reasoning_suffix` с ключом `str(step_index)` и отдаёт его в колбэк `emit`, который кладёт `(\"reasoning\", текст)` в очередь `Run.q`",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-03"
    },
    {
      "id": "EVD-004",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-04; bridges/agy-bridge/server.py:886-893",
      "claim": "`_reasoning_suffix` возвращает хвост сверх ранее виденного текста того же ключа, а если новый текст не начинается с прежнего, возвращает весь новый текст целиком и перезаписывает виденное",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-04"
    },
    {
      "id": "EVD-005",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-05; bridges/agy-bridge/server.py:720-776",
      "claim": "`Run.__init__` запускает лончер с флагами `--input-format stream-json --output-format stream-json --dangerously-skip-permissions --model --effort --print-timeout=0` (и `--conversation` при продолжении), в новой группе процессов, и стартует потоки stdin, stderr, `_pump` и `_TranscriptTail` с `resumed=bool(run_cid)`",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-05"
    },
    {
      "id": "EVD-006",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-06; bridges/agy-bridge/server.py:807-868",
      "claim": "`Run._pump` на `init` кладёт событие в очередь и привязывает хвост к `conversation_id`; на `step_update` с `agent_response` и `text_delta` кладёт `(\"text\", хвост)`; на `result` кладёт `(\"result\", ...)`; после EOF stdout ждёт процесс, спит 0.05 с, выставляет `_proc_done` и сразу кладёт `(\"done\", ...)` без ожидания потока хвоста",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-06"
    },
    {
      "id": "EVD-007",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-07; bridges/agy-bridge/server.py:981-1101",
      "claim": "`Handler._execute` читает только очередь `run.q` (таймаут 1.0 с) и возвращает `state(\"done\")` сразу по событию `done` (после паузы 0.05 с); на `result` со статусом `ERROR` возвращает `agy_error` немедленно; ожидания завершения потока `_TranscriptTail` в цикле нет",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-07"
    },
    {
      "id": "EVD-008",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-08; bridges/agy-bridge/server.py:870-883, 1148-1151",
      "claim": "`Run.close` выставляет `_stop_watch` и `_proc_done` и зачищает группу процессов; очередь `run.q` после выхода из `_execute` никем не читается, поэтому событие `reasoning`, положенное хвостом после финальной паузы, клиенту не попадает",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-08"
    },
    {
      "id": "EVD-009",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-09; bridges/agy-bridge/server.py:1126-1172",
      "claim": "В `Handler._run_once` после неуспешной попытки флаг `delivered = bool(out.get(\"text\") or out.get(\"tool_calls\"))` не учитывает `out[\"reasoning\"]`; при `not delivered` и состояниях `agy_error`, `pump_error`, `done` выполняется невидимый повтор (до 2 попыток, пауза `2*attempt` с), а горячая сессия при `agy_error` без выдачи переходит в холодный повтор с полной историей",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-09"
    },
    {
      "id": "EVD-010",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-10; bridges/agy-bridge/server.py:999-1006, 1015-1024",
      "claim": "`_execute` возвращает в `out` поле `reasoning` (склейка отданных клиенту кусков мышления), а `tool_calls` всегда пустой список, то есть `delivered` на практике зависит только от текста",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-10"
    },
    {
      "id": "EVD-011",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-11; bridges/agy-bridge/server.py:1438-1501",
      "claim": "`_serve_sse` шлёт первый чанк `{\"role\":\"assistant\",\"content\":\"\"}`, мышление отдаёт чанками `delta.reasoning_content`, а при ошибке после начала потока пишет кадр `data: {\"error\": ...}` и затем `data: [DONE]`",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-11"
    },
    {
      "id": "EVD-012",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-12; bridges/agy-bridge/server.py:1368-1385",
      "claim": "Ключ горячей сессии `sess_key = (model_id, cwd, effort)` не содержит признака наличия `tools`, числа сообщений или ключа кэша промпта; `_session_claim` вызывается для любого запроса без явного `conversation_id`, а `tools_count` вычисляется отдельно и в ключ не входит",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-12"
    },
    {
      "id": "EVD-013",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-13; bridges/agy-bridge/server.py:116-130, 477-516",
      "claim": "`_session_commit` перезаписывает запись хранилища, если `cid` завершившегося хода отличается от сохранённого; `_session_claim` пропускает занятую (`_in_flight_cids`) сессию и тогда запрос стартует холодным; TTL простоя 45 мин, жизни 24 ч, потолок 30 ходов",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-13"
    },
    {
      "id": "EVD-014",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-14; grep -rn _LAST_CONV bridges/agy-bridge/ core/ (0 строк); bridges/agy-bridge/server.py:128-130",
      "claim": "Глобальной переменной `_LAST_CONV` в мосте нет (0 совпадений grep по `bridges/agy-bridge/` и `core/`); роль «последнего разговора» выполняет словарь `_session_store` с ключом `sess_key`",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-14"
    },
    {
      "id": "EVD-015",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-15; bridges/agy-bridge/server.py:88-95, 336, 1029-1056; core/watchdog.py:27-30",
      "claim": "Таймауты моста: `KEEPALIVE_S=15`, `FIRST_TOKEN_TIMEOUT_S=120` (порог по первому любому JSON-событию stdout), `TIMEOUT_S=1800`, `QUEUE_TIMEOUT_S=900`, `MAX_CONCURRENT=4` по умолчанию; `IDLE_TIMEOUT_S` берётся из `core.watchdog` (300 с), проверка сторожа не чаще `WATCHDOG_INTERVAL_S=5` с",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-15"
    },
    {
      "id": "EVD-016",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-16; bridges/agy-bridge/server.py:1479-1480",
      "claim": "Keepalive моста — SSE-комментарий `: keepalive`, он не несёт ни `content`, ни `reasoning_content` и в UI ничего не показывает",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-16"
    },
    {
      "id": "EVD-017",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-17; bridges/agy-bridge/server.py:341, 1057-1058",
      "claim": "Событие `reasoning` входит в `_ACTIVITY_KINDS` и сбрасывает таймер неактивности сторожа через `controller.on_activity`",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-17"
    },
    {
      "id": "EVD-018",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-18; bridges/agy-bridge/server.py:807-813, 839-843; /tmp/cel-runs/agy-streaming-research-20261029/live_stream_json.jsonl строки 4-11",
      "claim": "Docstring `_pump` описывает `text_delta` как накопительный снимок, а живой поток 1.4.9 присылает непересекающиеся приращения (например, `Прочитан общий канон ~/Мо`, затем `й диск/`); корректный вывод сейчас обеспечивает ветка «не префикс → весь текст» из `_reasoning_suffix`",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-18"
    },
    {
      "id": "EVD-019",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-19; bridges/agy-bridge/server.py:1413-1436",
      "claim": "Нестриминговый путь `_serve_json` кладёт склеенное мышление в `message.reasoning_content`, то есть гонка финального дренирования затрагивает и ответ без `stream`",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-19"
    },
    {
      "id": "EVD-020",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-20; bridges/agy-bridge/server.py:1088-1101",
      "claim": "На `done` при пустом потоке текста `_execute` подставляет `final_text` из `result.response`, после чего ход считается `done`",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-20"
    },
    {
      "id": "EVD-021",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-21; ls bridges/agy-bridge/ (fleet.json, server.py, start.sh); grep -n \"def test_\" tests/test_agy_bridge_resilience.py",
      "claim": "Файла `bridges/agy-bridge/tests/test_agy_bridge.py` нет: каталога `tests` у моста нет, тесты моста лежат в корневом `tests/test_agy_bridge_resilience.py` (709 строк, классы IdleDetection, ExecuteLoop, KillSwitch, ErrorContract, KillGroup, FetchViaPlaywrightHotfix)",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-21"
    },
    {
      "id": "EVD-022",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-22; grep -n по словам TranscriptTail, reasoning, sess_key, delivered в tests/test_agy_bridge_resilience.py (строки 248, 354, 363)",
      "claim": "Тестов на `_TranscriptTail`, финальное дренирование, флаг `delivered` и `sess_key` нет: слово `reasoning` встречается только в тестах вида активности сторожа",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-22"
    },
    {
      "id": "EVD-023",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-23; /tmp/cel-runs/agy-realtime-reasoning-sa-20261029/baseline-unittest.log, baseline-pytest.log",
      "claim": "Базовая линия моста зелёная: `python3 -m unittest tests.test_agy_bridge_resilience` дал `Ran 22 tests in 2.082s OK` (exit 0); `python3 -m pytest` недоступен (в python3.14 нет модуля pytest)",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-23"
    },
    {
      "id": "EVD-024",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-24; /tmp/cel-runs/agy-realtime-reasoning-sa-20261029/baseline-full.log",
      "claim": "Полный прогон `uvx pytest -q -p no:cacheprovider tests/` без `PYTHONPATH` падает на сборке `tests/test_adaptive_idle_watchdog.py` с `ModuleNotFoundError: No module named 'core'` (exit 2); полный набор требует `PYTHONPATH=.`",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-24"
    },
    {
      "id": "EVD-025",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-25; ~/.local/bin/agy --version; ls -la ~/.local/bin/agy*; ls ~/.gemini/antigravity-cli/",
      "claim": "Установлен `agy` 1.4.9: `~/.local/bin/agy --version` печатает `1.4.9`, бинарь `~/.local/bin/agy.real` 193540240 байт от 2026-10-28 11:50; каталога `~/.gemini/antigravity-cli/releases/` нет",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-25"
    },
    {
      "id": "EVD-026",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-26; bridges/agy-bridge/fleet.json (technical_ref, models[0])",
      "claim": "`fleet.json` устарел относительно рантайма: `technical_ref.agy_version` равен `1.3.1`; `gemini-4-argon` имеет efforts low/medium/high и `default_effort=high`, `default_model` каталога `gemini-3.8-flash`",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-26"
    },
    {
      "id": "EVD-027",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-27; /tmp/cel-runs/agy-streaming-research-20261029/live_stream_json.jsonl",
      "claim": "Живой поток `stream-json` 1.4.9 (cid `c6910a34`): `init`, `step_update` user_input DONE, два шага `unknown` DONE, семь `agent_response` ACTIVE с `text_delta`, финальный DONE с `usage.thinking_tokens=1460`, затем `result` (`duration_seconds=19.8653`); ни одно событие не несёт текста мышления",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-27"
    },
    {
      "id": "EVD-028",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-28; KB tools/dsh-bridges-cli-agent-bridge.md строки 361-365 (дизассемблирование agy.real 1.4.9)",
      "claim": "В 1.4.9 Go-структура `steps.StepUpdatePayload` пакета printmode сериализует `text_delta` и `thinking_tokens`, но не поле `thinking` или `thinking_delta`, хотя в protobuf `StepUpdate` поле `thinking_delta` (field 10) объявлено",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-28"
    },
    {
      "id": "EVD-029",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-29; KB tools/dsh-bridges-cli-agent-bridge.md строки 369-373; /tmp/cel-runs/agy-streaming-research-20261029/checks.tsv строка step-3",
      "claim": "Живой замер `gemini-4-argon --effort high` (cid `82188e72`): stdout молчит с 4.81 с по 23.52 с; `transcript_full.jsonl` заморожен на 66213 байтах после `step_index=2`; запись `step_index=3` (`PLANNER_RESPONSE` с `thinking`) появилась в 23.87 с, на 90 мс позже события `result` (23.78 с); `Handler._execute` вышел по `done` в 23.83 с",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-29"
    },
    {
      "id": "EVD-030",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-30; KB tools/dsh-bridges-cli-agent-bridge.md строки 374-376; checks.tsv step-3-live-stream-probe",
      "claim": "В том же замере строка `idx=3, step_type=15, status=8` файла `~/.gemini/antigravity-cli/conversations/<cid>.db` обновлялась во время мышления: 10.66 с (523 B), 12.19 с (810 B), 14.97 с (1088 B), 20.06 с (1419 B), 23.36 с (2156 B), то есть интервалы 1.5-5.1 с",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-30"
    },
    {
      "id": "EVD-031",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-31; sqlite3 \"file:<db>?mode=ro&immutable=1\" \".tables\" \".schema steps\" (отчёт explorer Zone D); PRAGMA table_info(steps) в poc_pb.py",
      "claim": "Схема таблицы `steps`: `idx integer PRIMARY KEY, step_type integer, status integer, has_subtrajectory, metadata blob, error_details blob, permissions blob, task_details blob, render_info blob, step_payload blob, step_format integer`, индексы по `status` и `step_type`; в БД также таблицы `battle_mode_infos, executor_metadata, gen_metadata, parent_references, trajectory_meta, trajectory_metadata_blob`",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-31"
    },
    {
      "id": "EVD-032",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-32; python3 -I /tmp/cel-runs/agy-realtime-reasoning-sa-20261029/poc_pb.py 82188e72-6eca-4f23-a0b3-2257ec43bd60",
      "claim": "PoC-парсер wire-формата на stdlib (varint, wire types 0/1/2/5) извлёк из `82188e72` строки: idx 0 `step_type=14` (2020 B), idx 1 и 2 `step_type=90` (40132 B и 25094 B), idx 3 `step_type=15 status=3` (10068 B) с полем 20, в котором подполе 1 = 196 символов, подполе 3 = 1875 символов, подполе 6 встречается 1 раз, подполе 8 = 196 символов",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-32"
    },
    {
      "id": "EVD-033",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-33; python3 -I /tmp/cel-runs/agy-realtime-reasoning-sa-20261029/cmp2.py <cid>",
      "claim": "Финальный текст мышления из SQLite (`step_type=15`, поле 20.3) побайтово равен полю `thinking` записи `PLANNER_RESPONSE` транскрипта при `idx == step_index` на трёх разговорах: `82188e72` (1875 символов, есть не-ASCII), `fa92a264` (1080, есть не-ASCII), `57172100` (5561, только ASCII); в `4a1067cc` шагов `step_type=15` с мышлением нет ни в БД, ни в транскрипте",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-33"
    },
    {
      "id": "EVD-034",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-34; xxd -s 18 -l 2 <db>; file <db>; ls -la ~/.gemini/antigravity-cli/conversations (отчёт explorer Zone D)",
      "claim": "Файлы `conversations/*.db` в режиме WAL (байты 18-19 заголовка `0x02 0x02`, `last written using SQLite version 3053002, page size 32768`); у закрытых разговоров файлов `-wal` и `-shm` нет, в каталоге найдено только 4 таких файла от 2026-10-28",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-34"
    },
    {
      "id": "EVD-035",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-35; poc_pb.py вывод `sqlite 3.53.4`; отчёт explorer Zone D вопрос 5",
      "claim": "Python `sqlite3.connect(\"file:<db>?mode=ro\", uri=True)` (SQLite 3.53.4) читает закрытую БД разговора без ошибок, а CLI `sqlite3 -readonly <путь>` на той же БД вернул `unable to open database file (14)`",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-35"
    },
    {
      "id": "EVD-036",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-36; ls ~/.gemini/antigravity-cli/brain/82188e72-.../.system_generated/logs/chunks/*; ls ~/.gemini/antigravity/brain/82188e72-.../.system_generated/logs/ (No such file)",
      "claim": "Рядом с транскриптом CLI держит копии `chunks/transcript/00000000.jsonl` и `chunks/transcript_full/00000000.jsonl`; разговорный каталог мозга — `~/.gemini/antigravity-cli/brain/<cid>/`, а не `~/.gemini/antigravity/brain/<cid>/` (в последнем для `82188e72` каталога логов нет)",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-36"
    },
    {
      "id": "EVD-037",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-37; KB tools/dsh-bridges-cli-agent-bridge.md строка 359 (`~/.gemini/antigravity/builtin/skills/antigravity_guide/references/sdk.md`)",
      "claim": "Python SDK `google-antigravity` возвращает мысли только постфактум (`response.thoughts` после блокирующего `send()`), стримингового генератора мыслей нет",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-37"
    },
    {
      "id": "EVD-038",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-38; plutil -p ~/Library/LaunchAgents/com.user.dsh-agy-bridge.plist; readlink; shasum -a 256 (отчёт explorer Zone D)",
      "claim": "LaunchAgent `com.user.dsh-agy-bridge` запускает `/bin/bash ~/.dsh/bridges/agy-bridge/start.sh`, логи в `~/.dsh/bridges/agy-bridge/logs/bridge.err` и `bridge.out`, env `AGY_BRIDGE_MAX_CONCURRENT=8`, `AGY_BRIDGE_PORT=9887`, `AGY_BRIDGE_QUEUE_TIMEOUT=1800`; `~/.dsh/bridges/agy-bridge` — обычный каталог, не симлинк, и его `server.py` побайтово равен репозиторному (sha256 `c4e52312…e747`)",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-38"
    },
    {
      "id": "EVD-039",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-39; curl -s -m 3 http://127.0.0.1:9887/health",
      "claim": "`/health` моста: `ok=true`, `transport=agy-stream-json`, `model=gemini-3.8-flash`, `active=0`, `max_concurrent=8`, `hot_sessions=2`, `uptime_s=26273`",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-39"
    },
    {
      "id": "EVD-040",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-40; grep -cF по ~/.dsh/bridges/agy-bridge/logs/bridge.err",
      "claim": "`bridge.err` (2891 строк, без дат): `reasoning-emit` 888, `tail-emit` 893, `tail-timeout` 0, `tail-rewrite` 0, `exec model=` 301, `done model=` 266, `transient failure` 29, `hot session failed` 4; пять строк `tail-emit` не имеют парной `reasoning-emit`",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-40"
    },
    {
      "id": "EVD-041",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-41; grep/awk по bridge.err",
      "claim": "Из 301 запуска 156 с `tools=0` и 145 с `tools>0`; `resume=1` у 45, `resume=0` у 256",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-41"
    },
    {
      "id": "EVD-042",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-42; awk-группировка exec-строк bridge.err, строки 969-970, 1255-1256, 2792-2793",
      "claim": "В логе 21 пара запусков одной модели в одну секунду, где один `tools>0` с большим промптом и `effort_source=request`, а второй `tools=0` с промптом 492-721 байт и `effort_source=default` на соседнем клиентском порту (например, 01:09:38 `gemini-3.8-flash` 78282 B против 674 B; 23:20:29 и 19:09:44 `gemini-4-argon`)",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-42"
    },
    {
      "id": "EVD-043",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-43; awk по init/reasoning-emit/done в bridge.err; строки 965, 968, 986, 1337, 1804, 1875",
      "claim": "Среди ходов `gemini-4-argon` с `state=done`: без инструментов (`tool_events=0`) 28, из них 6 без единой строки `reasoning-emit` для своего cid; с инструментами 23, без мышления 0",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-43"
    },
    {
      "id": "EVD-044",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-44; bridge.err строки 2777-2782",
      "claim": "Одношаговый ход `926e03fa` (`gemini-4-argon`, wall 46.6 с): `tail-emit step=3 len=5342` и `reasoning-emit n=1` записаны в ту же секунду 01:08:22, что и `done`, то есть всё мышление пришло клиенту одним чанком в конце хода; так же ход `496587c9` (len 3935, wall 55.2 с)",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-44"
    },
    {
      "id": "EVD-045",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-45; bridge.err строки 2735, 2844, 2846, 2891 и подсчёт reasoning-emit",
      "claim": "Многошаговый ход `9ccb5526` с инструментами шёл 856.5 с и 1068.0 с (два хода, 52 и 46 событий инструментов) и отдал 37 и 22 куска мышления через транскрипт",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-45"
    },
    {
      "id": "EVD-046",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-46; bridge.err строки 2768, 2787, 2800 и done-строка 01:09:56",
      "claim": "2026-10-29 в 01:07-01:09 аккаунт agy получал `Individual quota reached ... Resets in 54h2xm` на `gemini-4-argon` и `gemini-3.8-flash`, а мост выполнял `transient failure ... retry 1` и `hot session failed ... cold fallback`",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-46"
    },
    {
      "id": "EVD-047",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-47; KB tools/dsh-bridges-cli-agent-bridge.md строки 377-380; bridge.err строки 2844, 2891",
      "claim": "База знаний фиксирует сценарий RC-3 на `cid=9ccb5526` (мышление Шага 1 затёрто кадром ошибки после сбоя квоты), а в `bridge.err` оба хода `9ccb5526` завершились `state=done rc=0`",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-47"
    },
    {
      "id": "EVD-048",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-48; /tmp/cel-runs/agy-streaming-research-20261029/close.md",
      "claim": "Ресерч 2026-10-29 закрыт со статусом ГОТОВО, источник реалтайма зафиксирован как SQLite `conversations/<cid>.db`, таблица `steps`, protobuf field 20.3",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-48"
    },
    {
      "id": "EVD-049",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-49; git log --oneline -5 -- bridges/agy-bridge/server.py; git log -1; git status --porcelain",
      "claim": "Последняя правка `bridges/agy-bridge/server.py` в истории — коммит `b9a9648` (resilience watchdog, process group kill, EYE-33873); ветка `feature/agy-realtime-reasoning` на HEAD `e00da06` (2026-10-28 03:32 MSK), рабочее дерево до анализа содержало только `.ai-team/runs/analyst-teamlead-agy-reasoning-20261029/`",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-49"
    },
    {
      "id": "EVD-050",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-50; bridges/agy-bridge/server.py:104, 594, 807, 1154, 1377",
      "claim": "Номера строк брифа расходятся с кодом: `_TranscriptTail` в 594-709 (в брифе 553-702), `Run._pump` в 807-868 (в брифе 920-935), `TRANSCRIPT_GRACE_S` в строке 104 (в брифе 626), период опроса 0.05 с (в брифе 0.15 с); строки `delivered` (1154) и `sess_key` (1377) совпадают",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-50"
    },
    {
      "id": "EVD-051",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-51; ps -o pid,rss,etime,command -p 45973; grep -n exec ~/.dsh/bridges/agy-bridge/start.sh (строка 23); lsof -p 45973 (36 строк); /usr/bin/python3 -c sqlite3.sqlite_version",
      "claim": "Боевой процесс моста (PID 45973, uptime 07:24:29) запущен `start.sh` строкой `exec /usr/bin/python3 server.py`, то есть системным Python 3.9.6 из CommandLineTools со встроенной SQLite 3.54.0; RSS 20512 KiB, открытых дескрипторов 36",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-51"
    },
    {
      "id": "EVD-052",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-52; /tmp/cel-runs/agy-realtime-reasoning-sa-20261029/ro_probe.py на dbcopy/t.db обоими интерпретаторами",
      "claim": "На копии закрытой WAL-БД разговора (без файлов `-wal` и `-shm`) системный Python 3.9.6 открывает её с `mode=ro` с ошибкой `unable to open database file`, с `mode=ro&immutable=1` читает 4 строки, с `mode=ro&nolock=1` падает; Homebrew Python 3.14.7 (SQLite 3.53.4) читает и с `mode=ro`, и с `immutable=1`",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-52"
    },
    {
      "id": "EVD-053",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-53; ro_probe.py, запущенный при живом rw-соединении к dbcopy/t.db",
      "claim": "Пока на ту же копию открыто читающе-пишущее соединение другого процесса (файл `-shm` существует), системный Python 3.9.6 открывает её с `mode=ro` и читает 4 строки",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-53"
    },
    {
      "id": "EVD-054",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-54; launchctl limit maxfiles; ulimit -n; sysctl net.inet.ip.portrange.first net.inet.ip.portrange.last net.inet.tcp.msl",
      "claim": "Лимиты хоста: `launchctl limit maxfiles` 65536 (soft) и unlimited (hard), `ulimit -n` в оболочке 1048576, диапазон эфемерных портов 49152-65535 (16384 порта), `net.inet.tcp.msl` 15000 мс (TIME_WAIT 30 с)",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-54"
    },
    {
      "id": "EVD-055",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-55; grep -F \" exec model=\" bridge.err, группировка по времени uniq -c",
      "claim": "Пиковая частота запусков по `bridge.err` — 6 строк `exec` в одну секунду (15:03:40), следующая — 4 (15:27:38)",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-55"
    },
    {
      "id": "EVD-056",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-56; /tmp/cel-runs/agy-realtime-reasoning-sa-20261029/baseline-full2.log",
      "claim": "Полный набор `PYTHONPATH=. uvx pytest -q -p no:cacheprovider tests/` на HEAD `e00da06`: 3 failed, 896 passed, 8103 subtests passed за 363.6 с; красные тесты вне `agy-bridge`: `test_b_guard.py::TestTm018Guard::test_tm018_live_check_subprocess`, `test_muse_bridge_killpg.py::AllowedModelsSyncTest::test_t00_models_and_health_include_wonder_models_400k`, `test_rpc_rework.py::TestRpcWriteDeadline::test_rw011_shutdown_all_within_budget_with_stuck_child`",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-56"
    },
    {
      "id": "EVD-057",
      "kind": "code",
      "ref": "bridges/agy-bridge/server.py:477-516 (_session_claim/_invalidate/_commit), 594-709 (_TranscriptTail), 807-868 (Run._pump), 870-893 (Run.close, _reasoning_suffix), 981-1101 (Handler._execute), 1103-1187 (_run_once), 1368-1400 (do_POST sess_key)",
      "claim": "Архитектор выборочно перепроверил символы ledger на HEAD e00da06: F-02..F-13 подтверждены (sleep 0.05 + done без join хвоста, grace 0.4 после done_event, delivered без reasoning, sess_key=(model_id,cwd,effort), _session_claim для любого запроса без conversation_id)",
      "collected_at": "2026-10-29"
    },
    {
      "id": "EVD-058",
      "kind": "command",
      "ref": "cd ~/tmp/cli-agent-bridge/agy-realtime-reasoning && PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -B -m unittest tests.test_agy_bridge_resilience",
      "claim": "Baseline моста на боевом интерпретаторе Python 3.9.6 (SQLite 3.54.0): Ran 22 tests in 2.076s OK, rc=0",
      "collected_at": "2026-10-29"
    },
    {
      "id": "EVD-059",
      "kind": "command",
      "ref": "uvx ruff check --no-cache bridges/agy-bridge/server.py tests/test_agy_bridge_resilience.py",
      "claim": "ruff 0.17.3 с ruff.toml (E4/E7/E9/F): All checks passed, rc=0 — порог 0 ошибок замораживается как есть",
      "collected_at": "2026-10-29"
    },
    {
      "id": "EVD-060",
      "kind": "command",
      "ref": "uvx basedpyright --outputjson bridges/agy-bridge/server.py tests/test_agy_bridge_resilience.py",
      "claim": "basedpyright 1.40.2 на baseline: 12 errors, 868 warnings (server.py 611, tests 257). Ошибки: server.py reportArgumentType×5 (строки 259, 282, 832, 1371, 1385), reportCallIssue×1 (259), reportIncompatibleMethodOverride×3 (928, 1529, 1544); tests reportUninitializedInstanceVariable×2 (165), reportPossiblyUnboundVariable×1 (557). Порог Teamlead basedpyright_errors=0 на baseline недостижим без правки чужого кода — замораживается baseline-aware гейт «не больше baseline по каждой паре (файл, правило)»",
      "collected_at": "2026-10-29"
    },
    {
      "id": "EVD-061",
      "kind": "document",
      "ref": ".ai-team/runs/analyst-teamlead-agy-reasoning-20261029/teamlead/verification-surface.json",
      "claim": "Замороженная поверхность Teamlead: base_sha e00da06, baseline 22 passed, новые тесты разрешены только в tests/test_agy_bridge_resilience.py, existing_oracle_assertions_mutable=false, хеши 39 oracle-файлов tests/, конфиги ruff.toml/fleet.json/start.sh; уровни L1 (ruff+basedpyright+pytest+unittest на /usr/bin/python3), L2 clean-room, L3 :9887 после ACCEPT и merge",
      "collected_at": "2026-10-29"
    },
    {
      "id": "EVD-062",
      "kind": "code",
      "ref": "bridges/agy-bridge/fleet.json:29-31 admission; bridges/agy-bridge/server.py:1511-1548 Server._conn_sem",
      "claim": "Ingress ограничен max_http_connections=32 (BoundedSemaphore, переполнение → raw 503), тело — max_inflight_body_bytes=67108864",
      "collected_at": "2026-10-29"
    },
    {
      "id": "EVD-063",
      "kind": "code",
      "ref": "bridges/agy-bridge/server.py:125, 969-979 (_slots, _acquire_slot), 1126-1172 (retry loop)",
      "claim": "Слоты исполнения — BoundedSemaphore(MAX_CONCURRENT); ожидание слота до QUEUE_TIMEOUT_S опросом по 1 с (код 900 с, деплой 1800 с по F-38); повтор хода — до 2 попыток с фиксированной паузой time.sleep(2*attempt), горячий срыв → холодный повтор без паузы; процессного retry budget нет",
      "collected_at": "2026-10-29"
    },
    {
      "id": "EVD-064",
      "kind": "code",
      "ref": "bridges/opencode-zen-bridge/server.py:1531 DYNAMIC_CONFIG_PATH, 1831-1858 _read_dynamic_config_enabled, 1913-1933 env override",
      "claim": "In-repo прецедент (влит в dev коммитом a269342): runtime-фичефлаг в dynamic_config.json рядом с server.py, stat-кэш (mtime_ns,size), кодовый default=false, env-override; принят Советом zen-realtime-reasoning как stdlib-аналог GigaRC без рестарта",
      "collected_at": "2026-10-29"
    },
    {
      "id": "EVD-065",
      "kind": "code",
      "ref": "core/context_resilience.py:254-300 (флаги GigaRC: Flags, FlagSource)",
      "claim": "Репозиторный аналог GigaRC — локальный атомарный JSON-снимок флагов, все флаги по умолчанию выключены; подтверждает канон «новое поведение за флагом, default=false»",
      "collected_at": "2026-10-29"
    },
    {
      "id": "EVD-066",
      "kind": "command",
      "ref": "python3 -I ~/Мой диск/skils/ai-sdlc/universal/orchestrate-coder-reviewer-summarizer/scripts/validate_role_plan.py plans/architect-01.before.json --role architect --phase before",
      "claim": "Установленный validate_role_plan.py не принимает --role (argparse: unrecognized arguments, rc=2); тот же файл без --role: PASS architect role plan valid for before. Роль проверяется внутри JSON",
      "collected_at": "2026-10-29"
    },
    {
      "id": "EVD-067",
      "kind": "command",
      "ref": "python3 -I ~/Мой диск/skils/ai-sdlc/universal/orchestrate-coder-reviewer-summarizer/scripts/worktree_fingerprint.py --root <repo> --exclude .ai-team/runs/analyst-teamlead-agy-reasoning-20261029 --compare fingerprints/architect-before.json",
      "claim": "Продуктовое дерево не изменено ролью: WORKTREE_UNCHANGED aed3274571859b39f08788443955470300be30a9dfd8ea5d0e994001433a0bbb files=12839 (промежуточная и финальная сверка)",
      "collected_at": "2026-10-29"
    },
    {
      "id": "EVD-068",
      "kind": "code",
      "ref": "bridges/agy-bridge/server.py:1107-1125, 1179-1187",
      "claim": "Строка O-EXIT `done model=...` пишется после try/finally; ранние выходы _run_once (no slot, launcher_unavailable) возвращаются без строки done — пробел телеметрии baseline",
      "collected_at": "2026-10-29"
    },
    {
      "id": "EVD-069",
      "kind": "code",
      "ref": "bridges/agy-bridge/server.py:47 (from __future__ import annotations), 1453 (dict | None)",
      "claim": "Модуль совместим с 3.9 только при сохранении отложенных аннотаций; новый код не может использовать runtime-синтаксис 3.10+ (match, X | Y вне аннотаций, zip(strict=))",
      "collected_at": "2026-10-29"
    },
    {
      "id": "EVD-070",
      "kind": "code",
      "ref": "bridges/agy-bridge/server.py:47-76 (imports)",
      "claim": "Корни импортов baseline: __future__, hashlib, json, os, queue, re, select, shutil, signal, socket, subprocess, sys, threading, time, uuid, http, pathlib, typing, core; дизайн добавляет только stdlib sqlite3 и random",
      "collected_at": "2026-10-29"
    },
    {
      "id": "EVD-071",
      "kind": "command",
      "ref": "git check-ignore -v bridges/agy-bridge/dynamic_config.json; grep -n dynamic_config .gitignore",
      "claim": ".gitignore игнорирует только __pycache__/; bridges/agy-bridge/dynamic_config.json не игнорируется — его отсутствие в git контролирует VER-008",
      "collected_at": "2026-10-29"
    },
    {
      "id": "EVD-072",
      "kind": "command",
      "ref": "dry-run замороженных команд VER-004/006/007/008/009 на HEAD e00da06",
      "claim": "Команды исполнимы: VER-004 errors 12 over_baseline {} rc=0; VER-006 OK rc=0; VER-007 MISSING 47 ids rc=1; VER-008 rc=1 (diff пуст); VER-009 FAIL no sqlite3.connect rc=1 — красные до реализации ожидаемо, зелёные обязаны стать после Coder",
      "collected_at": "2026-10-29"
    },
    {
      "id": "EVD-073",
      "kind": "command",
      "ref": "cd ~/tmp/cli-agent-bridge/agy-realtime-reasoning && uvx ruff@0.17.3 format --check --no-cache bridges/agy-bridge/server.py tests/test_agy_bridge_resilience.py",
      "claim": "Baseline e00da06: «1 file would be reformatted, 1 file already formatted», rc=1 — не отформатирован только bridges/agy-bridge/server.py (221 удаляемая строка в --diff), tests/test_agy_bridge_resilience.py уже отформатирован (0 строк в --diff)",
      "collected_at": "2026-10-29"
    },
    {
      "id": "EVD-074",
      "kind": "command",
      "ref": "dry-run запиненных команд VER-001..VER-005 на e00da06 (логи ~/work/tmp/agy-arch-r2/v1..v5)",
      "claim": "uvx ruff@0.17.3 check: All checks passed rc=0; uvx --from pytest==9.0.3 pytest: 22 passed, 19 subtests passed rc=0; /usr/bin/python3 -m unittest discover -s tests -p 'test_*agy*.py': Ran 22 tests OK rc=0; uvx basedpyright@1.40.2 --outputjson: errorCount 12 (server.py 9, tests 3), warningCount 868 (server.py 611, tests 257) rc=1",
      "collected_at": "2026-10-29"
    },
    {
      "id": "EVD-075",
      "kind": "document",
      "ref": ".ai-team/runs/analyst-teamlead-agy-reasoning-20261029/panel/arch/r1/seats/{1,2,3}/verdict.md (artifact_sha256 f0471a61…)",
      "claim": "ARCH_PANEL R1: все три места NEEDS WORK. Seat 1 (Google): result ERROR обходит join-before-done, ложный ранний выход drain, перехват plain-сессии на 2-м ходу, status=8 vs drain/LIMIT/strict UTF-8, float-бакет, незамкнутый HALF_OPEN, immutable при живом писателе, глобальный OPEN по одной divergence. Seat 2 (Meta): AO-04/C-MULT-I1 противоречат переподключениям, порог ≤5 с не выводится из F-30, процессные глобалы без замка, непиненные uvx-инструменты, нет владельца окна L3. Seat 3 (OpenAI): F-001..F-009 (префиксность/равный размер, полнота drain, бюджет 1.05 с, память seen/BLOB, семантическая совместимость версии, kill-switch активного хода, immutable, диапазон SQLITE_POLL_S, ослабление гейтов) и F-010 (жеребьёвка — зона оркестратора)",
      "collected_at": "2026-10-29"
    },
    {
      "id": "EVD-076",
      "kind": "command",
      "ref": "uvx basedpyright@1.40.2 --outputjson bridges/agy-bridge/server.py tests/test_agy_bridge_resilience.py на e00da06 (~/work/tmp/agy-arch-r2/v4.json; строки baseline до ruff format)",
      "claim": "errorCount 12 — точный список и исправления типизацией без `# type: ignore`/`# pyright: ignore` и без изменения поведения: (1,2) server.py:259 reportCallIssue + reportArgumentType `dict(technical_ref)`, technical_ref: Unknown|dict|None — сузить через локальную переменную: `technical_ref_raw = data.get(\"technical_ref\"); technical_ref: dict[str, Any] = technical_ref_raw if isinstance(technical_ref_raw, dict) else {}`; (3) server.py:282 reportArgumentType `hashlib.sha256(raw)`, raw: bytes|None — условие отказа `if catalog is None or raw is None:` (catalog не None ⇒ raw не None, поведение то же), raw сужается до bytes; (4) server.py:832 reportArgumentType `len(tools)` — `tools_raw = init.get(\"tools\"); tools: list[Any] = tools_raw if isinstance(tools_raw, list) else []` (так же init через локальную переменную + isinstance); (5) server.py:928 reportIncompatibleMethodOverride `log_message(self, fmt, *args)` — переименовать параметр в `format` как в BaseHTTPRequestHandler; (6,7) server.py:1371 и 1385 reportArgumentType messages: Unknown|list|None в _messages_to_prompt/_get_resumed_turn_prompt — `messages_raw = req.get(\"messages\"); messages: list[Any] = messages_raw if isinstance(messages_raw, list) else []`; (8,9) server.py:1529 process_request и 1544 process_request_thread reportIncompatibleMethodOverride (request: socket vs _RequestType) — аннотация `request: Union[socket.socket, Tuple[bytes, socket.socket]]` (typing, совместимо с 3.9) и сужение `sock = request if isinstance(request, socket.socket) else request[1]` перед _send_raw_503(sock); shutdown_request/super() получают исходный request; (10,11) tests/test_agy_bridge_resilience.py:165 reportUninitializedInstanceVariable `self.a`, `self.b` в _Sock — добавить объявления в тело класса `a: socket.socket` и `b: socket.socket` (только добавленные строки, VER-006); (12) tests/test_agy_bridge_resilience.py:557 reportPossiblyUnboundVariable `out` — добавить строку перед циклом `out = subprocess.CompletedProcess(args=[], returncode=0, stdout=\"\", stderr=\"\")` (только добавление, цикл всегда исполняется ≥1 раз). Итог: server.py 9, tests 3; после ruff format номера строк server.py сдвигаются — сопоставление по (файл, правило, сообщение)",
      "collected_at": "2026-10-29"
    },
    {
      "id": "EVD-077",
      "kind": "document",
      "ref": "бриф оркестратора architect R3-fix (находки ARCH_PANEL R2: Seat 1 gpt-6.1-sol-high F-001..F-012, Seat 2 muse-wonder-full-1.0 F-001..F-008; Seat 3 gemini-4-argon-high PASS 6/6) и sha256 замороженных analysis/agy-realtime-reasoning/*.md",
      "claim": "R2: Seat 1 — эвристический ранний выход drain (F-001), склейка хвоста на расходящийся префикс (F-002), смешение observed/delivered в SHADOW (F-003), владение cid и откат resumed на anchored=False (F-004, F-005), неограниченная работа итерации/без interrupt (F-006), reasoning после done (F-007), kill-switch > 5 с на SQLITE_POLL_S=2.0 (F-008), устаревшая проба HALF_OPEN (F-009), замыкание памяти/огибающая/наблюдаемость/гейты (F-010..F-012); Seat 2 — divergence-склейка (F-001), cold-open как отказ breaker'а (F-002), kill-switch (F-003), память/огибающая//health/VER-007/008/010/012 (F-004..F-007). sha256 analysis/agy-realtime-reasoning: research-plan.md 81dffc06ac79c490968e7efb8321f464d5963f414fcc6bd67a278a99d5985e32; evidence-ledger.md e9c8afb2684a7621e9fdb0455640e86f972aab600989142119fb440397842ff1; open-questions.md 47b16bab51b31bb06c35fb02d08dbd3409a9cfb057a52e828d079054a20d9202; handoff-architect.md cb1ecde9e00f06d72b75e43f973add3ab93ca27433d7145cbf8ec4f4800b17cd; handoff-qa.md 5ed84fc039f7fea5983404442461e734ec9dae03f57359e2bb441dfae6cb7afe",
      "collected_at": "2026-10-29"
    }
  ],
  "risk_triggers": [
    "trust-boundary"
  ],
  "assumptions": [
    {
      "id": "ASM-001",
      "class": "continuable",
      "source_open_ids": "OPEN-01",
      "statement": "Подполе 20.3 растёт префиксно между снимками status=8 (F-30, F-33 подтверждают рост и равенство финалов, но не префиксность промежуточных снимков). Корректность не зависит от допущения: при выполнении ASM-001 склейка побайтово равна final_thinking (AC-004); при нарушении — проверка префикса sha256 замораживает выдачу шага на уже отданном префиксе (0 повторных и 0 склеенных символов, AC-005), остаток хода transcript-only, отказ breaker'а и SHADOW (AD-001.dedup_and_emit). Допущение проверяется живьём: 0 строк divergence в L2 (VER-010) и на ≥5 многошаговых ходах L3 (VER-011)",
      "status": "ASSUMED",
      "evidence_ids": [
        "EVD-004",
        "EVD-030",
        "EVD-033",
        "EVD-075",
        "EVD-077"
      ]
    },
    {
      "id": "ASM-002",
      "class": "continuable",
      "source_open_ids": "OPEN-02, OPEN-12",
      "statement": "Во время хода agy держит БД разговора открытой (есть -shm), поэтому /usr/bin/python3 3.9.6 читает её с mode=ro. immutable=1 не используется ни при каких условиях (внешний CLI/фоновый писатель возможен, F-007). Если mode=ro не открывает БД (закрытая WAL-БД без -shm, F-52) — ход идёт на транскрипте, а resumed-ход без успешного pre-spawn SQLite-водяного знака идёт с turn_mode=OFF (только транскрипт с pre-spawn водяным знаком; выборка «только status=8 без якоря» удалена)",
      "status": "ASSUMED",
      "evidence_ids": [
        "EVD-052",
        "EVD-053",
        "EVD-030",
        "EVD-035"
      ]
    },
    {
      "id": "ASM-003",
      "class": "continuable",
      "source_open_ids": "OPEN-03",
      "statement": "Номера step_type=15, status=8/3, поле 20, подполе 3 привязаны к agy 1.4.9 (F-25, F-31). Смена бинаря agy (st_mtime_ns, st_size) переводит источник в SHADOW до canary-совпадения с транскриптом; несовпадение схемы (нет таблицы/колонок), divergence и пропажа live-источника выключают выдачу из SQLite, мышление идёт из транскрипта",
      "status": "ASSUMED",
      "evidence_ids": [
        "EVD-025",
        "EVD-028",
        "EVD-031"
      ]
    },
    {
      "id": "ASM-004",
      "class": "continuable",
      "source_open_ids": "OPEN-04",
      "statement": "6 одношаговых ходов argon без мышления объясняются гонкой drain и/или смещением хвоста при продолжении; AD-001 (водяной знак до spawn) и AD-002 закрывают обе причины",
      "status": "ASSUMED",
      "evidence_ids": [
        "EVD-043",
        "EVD-006",
        "EVD-002"
      ]
    },
    {
      "id": "ASM-005",
      "class": "continuable",
      "source_open_ids": "OPEN-05",
      "statement": "cwd фонового запроса DSH совпадает с основным; изоляция AD-004 не зависит от cwd",
      "status": "ASSUMED",
      "evidence_ids": [
        "EVD-042",
        "EVD-012",
        "EVD-013"
      ]
    },
    {
      "id": "ASM-006",
      "class": "continuable",
      "source_open_ids": "OPEN-06",
      "statement": "Сбой после отданного reasoning завершается кадром data:{error} + [DONE] (неизменный as-is контракт ошибок после старта потока), без невидимого повтора; альтернатива stop+частичный ответ ждёт решения владельца (Q-002)",
      "status": "ASSUMED",
      "evidence_ids": [
        "EVD-011",
        "EVD-047"
      ]
    },
    {
      "id": "ASM-007",
      "class": "continuable",
      "source_open_ids": "OPEN-07",
      "statement": "L3 выполняется на аккаунте agy с квотой (штатное переключение) или после сброса квоты; без L3 сдача не засчитывается",
      "status": "ASSUMED",
      "evidence_ids": [
        "EVD-046"
      ]
    },
    {
      "id": "ASM-008",
      "class": "continuable",
      "source_open_ids": "OPEN-08",
      "statement": "Цели отзывчивости: L2 (детерминированно) — коммит снимка → сокет ≤ SQLITE_POLL_S + 0.5 с (≤1.0 с при 0.5 с, AC-002); L3 — первый чанк ≤5.0 с от первой строки status=8 с непустым 20.3; интервал ≤6 с — наблюдение SHOULD (зависит от расписания записи agy, F-30); добавка drain ≤1.0 с (≤0.65 с при дефолтах, ≤0.85 с на максимумах)",
      "status": "ASSUMED",
      "evidence_ids": [
        "EVD-030"
      ]
    },
    {
      "id": "ASM-009",
      "class": "continuable",
      "source_open_ids": "OPEN-09, OPEN-10, OPEN-11, OPEN-16",
      "statement": "Вне объёма MR: fleet.json technical_ref (1.3.1) и комментарии про 1.3.1 (fleet.json защищён хешем Teamlead), трактовка text_delta в _pump (_reasoning_suffix для текста не меняется), agentapi не исследуется, 3 красных теста полного набора вне agy-bridge — набор красных до/после сравнивается",
      "status": "ASSUMED",
      "evidence_ids": [
        "EVD-026",
        "EVD-018",
        "EVD-056",
        "EVD-061"
      ]
    },
    {
      "id": "ASM-010",
      "class": "continuable",
      "source_open_ids": "brief architect-01 (пример AGY_SQLITE_REASONING=1)",
      "statement": "Переключатель SQLite-источника: кодовый default=false + runtime dynamic_config.json (SQLITE_REASONING_ENABLED, stat-кэш TTL 1.0 с, перепроверка каждые 0.25 с, kill-switch активного хода ≤1.30 с, fail-closed) AND env AGY_SQLITE_REASONING_ENABLED (только аварийное выключение 0/false/False); включение на :9887 — шаг L3. Отклонение от примера брифа (env default=1 как единственный переключатель) по канону «фича за флагом default=false, kill-switch без рестарта» и in-repo прецеденту zen; владелец может выбрать иначе (Q-004)",
      "status": "ASSUMED",
      "evidence_ids": [
        "EVD-064",
        "EVD-065",
        "EVD-038"
      ]
    },
    {
      "id": "ASM-011",
      "class": "continuable",
      "source_open_ids": "baseline debt",
      "statement": "Гейты не ослабляются: ruff check/format, basedpyright errorCount == 0 и 0 новых предупреждений на target-scope, 0 падений targeted-тестов (VER-001..VER-005). 12 baseline-ошибок basedpyright и неотформатированный server.py — внутри target-файлов и устраняются в этом MR без изменения поведения. Унаследованные файлы вне границы правки (bridges/claude-bridge/server.py и др., 3 красных теста полного набора F-56) не трогаются; их красный статус в VER-012 — решение владельца (Q-005), не PASS. Прочие baseline-отклонения (ожидание слота до 900/1800 с, ожидающие слота до 24 > 2M, неограниченная Run.q) этим MR не ухудшаются",
      "status": "ASSUMED",
      "evidence_ids": [
        "EVD-056",
        "EVD-060",
        "EVD-062",
        "EVD-063",
        "EVD-073",
        "EVD-074"
      ]
    }
  ],
  "drivers": [
    "RC-1: нет live-источника мышления — пустой UI 15-45 с (F-27..F-30, F-44)",
    "RC-2: гонка финального drain теряет мышление последнего шага (F-06..F-08, F-29, F-43)",
    "RC-3: отданное reasoning не считается выдачей → невидимый повтор/дубли (F-09..F-11, F-46, F-47)",
    "RC-4: sess_key без признака tools → фоновый запрос уводит conversation_id диалога (F-12..F-14, F-41, F-42)",
    "Ограничения: боевой /usr/bin/python3 3.9.6 + stdlib, неизменный HTTP/SSE контракт, только чтение файлов agy, fail-open (F-51..F-53, REQ-002/004/010)",
    "ARCH_PANEL R1 (EVD-075): Seat 1 #1..#5 + полнота/риски, Seat 2 #1..#3, Seat 3 F-001..F-009 — все закрыты ревизией AD-001..AD-006 и VER-001..VER-012"
  ],
  "verification_surface": [
    {
      "id": "VER-001",
      "requirement_ids": [
        "REQ-010"
      ],
      "kind": "command",
      "command": "uvx ruff@0.17.3 check --no-cache bridges/agy-bridge/server.py tests/test_agy_bridge_resilience.py",
      "expected": "exit 0; «All checks passed!» — 0 ошибок и 0 предупреждений ruff (ruff.toml репозитория, порог Teamlead ruff_check_errors=0; baseline зелёный EVD-059/EVD-074)",
      "environment": "cwd=repo_root, ruff 0.17.3 строго (uvx ruff@0.17.3); кэш uvx прогрет до clean-room (RISK-016), без записи .ruff_cache (--no-cache)",
      "owner": "Verifier"
    },
    {
      "id": "VER-002",
      "requirement_ids": [
        "REQ-010"
      ],
      "kind": "command",
      "command": "uvx ruff@0.17.3 format --check --no-cache bridges/agy-bridge/server.py tests/test_agy_bridge_resilience.py",
      "expected": "exit 0; «2 files already formatted» — 0 файлов к переформатированию. На baseline server.py не отформатирован (EVD-073): Coder выполняет механический uvx ruff@0.17.3 format bridges/agy-bridge/server.py отдельным коммитом style без изменения поведения; tests/test_agy_bridge_resilience.py уже отформатирован, поэтому VER-006 (только добавления в тестах) не задевается",
      "environment": "cwd=repo_root, ruff 0.17.3 строго, --no-cache",
      "owner": "Verifier"
    },
    {
      "id": "VER-003",
      "requirement_ids": [
        "AD-001",
        "AD-002",
        "AD-003",
        "AD-004",
        "AD-005",
        "AD-006",
        "REQ-001",
        "REQ-002",
        "REQ-003",
        "REQ-004",
        "REQ-005",
        "REQ-006",
        "REQ-007",
        "REQ-008",
        "REQ-009",
        "REQ-010",
        "REQ-011",
        "REQ-012"
      ],
      "kind": "command",
      "command": "PYTHONPATH=. uvx --from pytest==9.0.3 pytest -q -p no:cacheprovider tests/test_agy_bridge_resilience.py",
      "expected": "exit 0; 0 failed, 0 errors; passed ≥ 22 + все новые тесты TC/AO из VER-007; 22 существующих теста зелёные без правок (baseline EVD-074: 22 passed на pytest 9.0.3)",
      "environment": "Чистый clone/worktree кандидата, cwd=repo_root, pytest 9.0.3 строго (uvx --from pytest==9.0.3), кэш uvx прогрет; без сети, без ~/.gemini и ~/.dsh владельца: фикстурные AGY_BRIDGE_BRAIN/AGY_BRIDGE_CONVERSATIONS/AGY_BRIDGE_AGY_BIN/фейковый AGY_LAUNCHER во временном каталоге раннера; процессные guard'ы сбрасываются хелпером между тестами",
      "owner": "Verifier"
    },
    {
      "id": "VER-004",
      "requirement_ids": [
        "REQ-010",
        "RISK-011"
      ],
      "kind": "command",
      "command": "set -e; B=\"$(mktemp -d)\"; H=\"$(mktemp)\"; S=\"$(mktemp)\"; git worktree add -q --detach \"$B/base\" e00da0621fc95f7c63cd1565f4a5d1fd490c8d66; uvx basedpyright@1.40.2 --outputjson bridges/agy-bridge/server.py tests/test_agy_bridge_resilience.py > \"$H\" || true; (cd \"$B/base\" && uvx basedpyright@1.40.2 --outputjson bridges/agy-bridge/server.py tests/test_agy_bridge_resilience.py > \"$S\" || true); git worktree remove --force \"$B/base\"; python3 -I - \"$H\" \"$S\" <<'PY'\nimport json,sys,collections\nh=json.load(open(sys.argv[1])); s=json.load(open(sys.argv[2]))\ndef ms(x,sev): return collections.Counter((d['file'].rsplit('/',1)[-1],d.get('rule'),d['message']) for d in x['generalDiagnostics'] if d['severity']==sev)\nerr=h['summary']['errorCount']; new_w=ms(h,'warning')-ms(s,'warning')\nprint('version',h['version'],'errors',err,'warnings',h['summary']['warningCount'],'new_warnings',sum(new_w.values()))\n[print('NEW',k) for k in sorted(new_w)]\nsys.exit(0 if err==0 and not new_w and h['version'].startswith('1.40.2') else 1)\nPY",
      "expected": "exit 0; строка «errors 0 … new_warnings 0»: errorCount кандидата == 0 на target-scope (порог Teamlead basedpyright_errors=0 сохранён; 12 baseline-ошибок EVD-060 в target-файлах (точный список и исправления — EVD-076) устраняются в этом MR типизацией без изменения поведения, inline-подавления `# pyright: ignore`/`# type: ignore` запрещены); 0 новых предупреждений — мультимножество (файл, правило, сообщение) предупреждений кандидата ⊆ baseline e00da06 на той же версии 1.40.2, поэтому новая диагностика ловится даже при неизменном общем числе",
      "environment": "Clean-room clone кандидата с доступным e00da0621fc95f7c63cd1565f4a5d1fd490c8d66, cwd=repo_root, basedpyright 1.40.2 строго (uvx basedpyright@1.40.2), pyrightconfig.json репозитория, python3 -I для сравнения; временный git worktree базы удаляется командой",
      "owner": "Verifier"
    },
    {
      "id": "VER-005",
      "requirement_ids": [
        "AD-001",
        "REQ-001",
        "REQ-002",
        "REQ-003",
        "REQ-004",
        "REQ-005",
        "REQ-006",
        "REQ-008",
        "REQ-009",
        "REQ-010",
        "RISK-002",
        "RISK-012"
      ],
      "kind": "command",
      "command": "PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /usr/bin/python3 -B -m unittest discover -s tests -p \"test_*agy*.py\" && PYTHONPATH=. uvx --from pytest==9.0.3 pytest -q -p no:cacheprovider tests/test_agy_bridge_resilience.py",
      "expected": "exit 0; unittest «OK» на боевом /usr/bin/python3 3.9.6 (SQLite 3.54.x) и pytest 0 failed — 0 падений в обоих прогонах (baseline EVD-074: Ran 22 tests OK); зелёный прогон только на Python 3.14 не засчитывается",
      "environment": "macOS /usr/bin/python3 3.9.6 (CommandLineTools) + pytest 9.0.3, cwd=repo_root, PYTHONDONTWRITEBYTECODE=1",
      "owner": "Verifier"
    },
    {
      "id": "VER-006",
      "requirement_ids": [
        "REQ-010",
        "QA-006"
      ],
      "kind": "command",
      "command": "test \"$(git diff --unified=0 e00da0621fc95f7c63cd1565f4a5d1fd490c8d66 HEAD -- tests/test_agy_bridge_resilience.py | grep -cE '^-[^-]')\" = 0 && test -z \"$(git diff --name-only e00da0621fc95f7c63cd1565f4a5d1fd490c8d66 HEAD -- tests/ core/ | grep -vx 'tests/test_agy_bridge_resilience.py')\" && echo OK",
      "expected": "exit 0 и «OK»: в tests/test_agy_bridge_resilience.py нет удалённых/изменённых строк относительно e00da06 (только добавления), другие файлы tests/ и core/ не изменены",
      "environment": "git clone кандидата с доступным base e00da0621fc95f7c63cd1565f4a5d1fd490c8d66, HEAD = коммит кандидата",
      "owner": "Teamlead"
    },
    {
      "id": "VER-007",
      "requirement_ids": [
        "AD-005",
        "REQ-001",
        "REQ-002",
        "REQ-003",
        "REQ-004",
        "REQ-005",
        "REQ-006",
        "REQ-007",
        "REQ-008",
        "REQ-009",
        "REQ-010",
        "REQ-011",
        "REQ-012",
        "THREAT-001",
        "THREAT-002",
        "THREAT-003",
        "THREAT-004",
        "THREAT-005"
      ],
      "kind": "command",
      "command": "python3 -I - <<'PY'\nimport ast,re,sys,pathlib\ns=pathlib.Path('tests/test_agy_bridge_resilience.py').read_text(encoding='utf-8')\nt=ast.parse(s)\nneed={'tc%02d'%i for i in list(range(1,13))+[20,21,23,24,30,31,32,33,40,41,42,43,44,50,51,60,61,62,63,70,71,72,80,81,82,91,92]}|{'ao%02d'%i for i in range(1,13)}\ndef asserted(f):\n    for n in ast.walk(f):\n        if isinstance(n,ast.Assert): return True\n        if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr.startswith('assert'): return True\n    return False\ngot=set(); noassert=[]\nfor f in ast.walk(t):\n    if isinstance(f,(ast.FunctionDef,ast.AsyncFunctionDef)) and f.name.startswith('test_'):\n        ids=set(re.findall(r'(tc\\d{2}|ao\\d{2})',f.name))&need\n        if not ids: continue\n        if asserted(f): got|=ids\n        else: noassert.append(f.name)\nmiss=sorted(need-got)\nerrs=(['MISSING '+' '.join(miss)] if miss else [])+(['NO_ASSERT '+' '.join(sorted(noassert))] if noassert else [])\nprint('; '.join(errs) if errs else 'OK %d ids, all asserted'%len(need)); sys.exit(1 if errs else 0)\nPY",
      "expected": "exit 0; «OK 51 ids, all asserted»: имена тестовых функций покрывают TC-01..12, 20, 21, 23, 24, 30..33, 40..44, 50, 51, 60..63, 70..72, 80..82, 91, 92 и архитектурные оракулы AO-01..AO-12 (в имени test_..._tcNN / _aoNN, допускается несколько id в одном имени), и каждая тестовая функция с требуемым id содержит в AST ≥1 оператор assert или вызов *.assert*(...) (self.assertEqual, self.assertTrue, …); функция без проверок → FAIL «NO_ASSERT <имя>», непокрытый id → «MISSING <id>»",
      "environment": "cwd=repo_root, python3 -I",
      "owner": "Teamlead"
    },
    {
      "id": "VER-008",
      "requirement_ids": [
        "REQ-010",
        "RISK-011",
        "AD-006"
      ],
      "kind": "command",
      "command": "test \"$(git diff --name-only e00da0621fc95f7c63cd1565f4a5d1fd490c8d66 HEAD -- . ':(exclude).ai-team' ':(exclude)analysis' | sort | tr '\\n' ' ')\" = \"bridges/agy-bridge/server.py tests/test_agy_bridge_resilience.py \" && test -z \"$(git ls-files bridges/agy-bridge/dynamic_config.json)\" && printf '%s  %s\\n' 81dffc06ac79c490968e7efb8321f464d5963f414fcc6bd67a278a99d5985e32 analysis/agy-realtime-reasoning/research-plan.md e9c8afb2684a7621e9fdb0455640e86f972aab600989142119fb440397842ff1 analysis/agy-realtime-reasoning/evidence-ledger.md 47b16bab51b31bb06c35fb02d08dbd3409a9cfb057a52e828d079054a20d9202 analysis/agy-realtime-reasoning/open-questions.md cb1ecde9e00f06d72b75e43f973add3ab93ca27433d7145cbf8ec4f4800b17cd analysis/agy-realtime-reasoning/handoff-architect.md 5ed84fc039f7fea5983404442461e734ec9dae03f57359e2bb441dfae6cb7afe analysis/agy-realtime-reasoning/handoff-qa.md | shasum -a 256 -c --status - && echo OK",
      "expected": "exit 0 и «OK»: изменены ровно bridges/agy-bridge/server.py и tests/test_agy_bridge_resilience.py (вне .ai-team и analysis); bridges/agy-bridge/dynamic_config.json не в git; нет правок fleet.json/start.sh/ruff.toml/core/зависимостей; 5 замороженных входов аналитика analysis/agy-realtime-reasoning/{research-plan.md, evidence-ledger.md, open-questions.md, handoff-architect.md, handoff-qa.md} побайтово совпадают с sha256 EVD-077 (любое расхождение или отсутствие файла → exit ≠ 0)",
      "environment": "worktree кандидата (HEAD = коммит кандидата) с доступным base e00da06 и каталогом analysis/agy-realtime-reasoning/ (из коммита MR или рабочего worktree прогона), shasum (macOS)",
      "owner": "Teamlead"
    },
    {
      "id": "VER-009",
      "requirement_ids": [
        "AD-001",
        "AD-006",
        "BND-003",
        "REQ-002",
        "REQ-004",
        "REQ-011",
        "THREAT-003"
      ],
      "kind": "command",
      "command": "python3 -I - <<'PY'\nimport ast,sys,pathlib\nsrc=pathlib.Path('bridges/agy-bridge/server.py').read_text(encoding='utf-8')\nt=ast.parse(src)\nallowed={'__future__','hashlib','json','os','queue','re','select','shutil','signal','socket','subprocess','sys','threading','time','uuid','http','pathlib','typing','core','sqlite3','random'}\nroots=set()\nfor n in ast.walk(t):\n    if isinstance(n,ast.Import):\n        roots|={a.name.split('.')[0] for a in n.names}\n    elif isinstance(n,ast.ImportFrom) and n.level==0:\n        roots.add((n.module or '').split('.')[0])\ncalls=[n for n in ast.walk(t) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='connect' and isinstance(n.func.value,ast.Name) and n.func.value.id=='sqlite3']\nnouri=[c.lineno for c in calls if not any(k.arg=='uri' and isinstance(k.value,ast.Constant) and k.value.value is True for k in c.keywords)]\nrw=[n.lineno for n in ast.walk(t) if isinstance(n,ast.Constant) and isinstance(n.value,str) and ('mode=rw' in n.value or 'immutable' in n.value)]\nneed=[x for x in ('AGY_SQLITE_REASONING_ENABLED','SQLITE_REASONING_ENABLED','AGY_BRIDGE_CONVERSATIONS','mode=ro','query_only','busy_timeout') if x not in src]\nerrs=[]\nif sorted(roots-allowed): errs.append('non-stdlib imports %s'%sorted(roots-allowed))\nif not calls: errs.append('no sqlite3.connect call')\nif nouri: errs.append('sqlite3.connect without uri=True at %s'%nouri)\nif rw: errs.append('write-mode or immutable URI literal at %s'%rw)\nif 'immutable' in src: errs.append('substring immutable present in server.py')\nif need: errs.append('missing %s'%need)\nprint('FAIL: '+'; '.join(errs) if errs else 'OK'); sys.exit(1 if errs else 0)\nPY",
      "expected": "exit 0 и «OK»: корни импортов ⊆ stdlib baseline ∪ {sqlite3, random}; каждый sqlite3.connect с uri=True; нет URI mode=rw/rwc и подстроки immutable нигде в server.py (F-007); присутствуют AGY_SQLITE_REASONING_ENABLED, SQLITE_REASONING_ENABLED, AGY_BRIDGE_CONVERSATIONS, mode=ro, query_only, busy_timeout",
      "environment": "cwd=repo_root, python3 -I (ast)",
      "owner": "Verifier"
    },
    {
      "id": "VER-010",
      "requirement_ids": [
        "QA-001",
        "QA-002",
        "QA-003",
        "QA-008",
        "QA-010",
        "QA-012",
        "REQ-001",
        "REQ-003",
        "REQ-005",
        "REQ-006",
        "REQ-007",
        "REQ-010",
        "REQ-012",
        "RISK-005",
        "RISK-006",
        "RISK-007"
      ],
      "kind": "command",
      "command": "PYTHONPATH=. uvx --from pytest==9.0.3 pytest -q -p no:cacheprovider tests/test_agy_bridge_resilience.py -k \"tc93 or l2_harness\" && PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /usr/bin/python3 -B -m unittest discover -s tests -p \"test_agy_bridge_resilience.py\" -k tc93 -k l2_harness",
      "expected": "exit 0 в обоих прогонах; pytest выбрал ≥1 тест (0 выбранных → rc 5 = FAIL). Детерминированный L2-харнесс (test_..._tc93 и test_..._l2_harness): мост из кандидата в процессе теста с фейковым AGY_LAUNCHER (подпроцесс-писатель), фикстурами AGY_BRIDGE_BRAIN/AGY_BRIDGE_CONVERSATIONS/AGY_BRIDGE_AGY_BIN во временном каталоге и dynamic_config.json {\"SQLITE_REASONING_ENABLED\": true} рядом с server.py (env-форсирования нет); canary пройден прогревочным ходом; писатель многоходово обновляет WAL-БД 523→810→1088→1419→2156 байт. PASS только если одновременно: 8 параллельных ходов; RSS — resource.getrusage(RUSAGE_SELF).ru_maxrss (байты на macOS, KiB на Linux, нормализуется) ≤ 112 MiB; CPU — Δtime.process_time() / (Δwall · 8) ≤ 0.01 ядра на ход на минимальном SQLITE_POLL_S=0.5; задержка коммит снимка → сокет ≤ SQLITE_POLL_S + 0.5 с на каждом снимке; TC-20 ≥2 чанка до status=3; TC-60/TC-61 100/100; EOF→stop ≤0.65 с при дефолтах и ≤0.85 с при AGY_BRIDGE_TRANSCRIPT_GRACE=0.5, AGY_BRIDGE_DRAIN_JOIN=0.2, AGY_BRIDGE_DRAIN_MIN=0.25 (≤1.0 с гейт); kill-switch: запись false посреди хода → SELECT прекращаются и соединение закрыто ≤2.0 с (дизайн 1.30 с) при SQLITE_POLL_S 0.5 и 2.0; outcome=window_complete или complete в каждой строке drain; resumed-ход с внешним writer'ом — 0 переотданных шагов прошлых ходов, 0 SQLITE_CORRUPT/SQLITE_BUSY у писателя; 0 строк sqlite_snapshot_divergence; /health содержит 4 аддитивных поля; в stderr нет текста мышления фикстуры. Квитанция — вывод обеих команд в run_dir/teamlead/execution-evidence.md + evidence-manifest.sha256",
      "environment": "Clean-room worktree кандидата, cwd=repo_root, временные каталоги, без сети (кэш uvx прогрет заранее, RISK-016) и без доступа к ~/.gemini и ~/.dsh владельца; pytest 9.0.3 строго и боевой /usr/bin/python3 3.9.6; ~60 с, запускать в фоне",
      "owner": "Teamlead"
    },
    {
      "id": "VER-011",
      "requirement_ids": [
        "QA-001",
        "QA-002",
        "QA-005",
        "QA-007",
        "QA-010",
        "QA-012",
        "REQ-001",
        "REQ-003",
        "REQ-008",
        "REQ-009",
        "RISK-001",
        "RISK-003",
        "RISK-008",
        "THREAT-005"
      ],
      "kind": "manual",
      "command": null,
      "expected": "Бинарный гейт L3 (handoff-qa.md §6) на 127.0.0.1:9887 после ACCEPT Совета и merge MR. Входная зависимость: владелец переключает аккаунт agy с квотой или ждёт сброса квоты (≈2026-10-31 07:09 MSK, Q-003); без этого L3 не стартует. Бэкап ~/work/backups/agy-bridge-<ts>/, копия server.py + sha256, kickstart, /health. Фаза A (флаг выключен): S3 изоляция — второй агентный ход resume=1 с тем же cid, plain-запрос без tools не трогает стор; S4 у всех ходов есть мышление до stop; квотный/ошибочный ход без повторного чанка мышления. Фаза B: атомарная запись dynamic_config.json {SQLITE_REASONING_ENABLED: true} в каталог деплоя без рестарта; первый ход с мышлением после kickstart идёт в SHADOW (canary), S1 меряется со следующего: первый чанк reasoning_content ≤5.0 с от первой строки status=8 шага с непустым 20.3 (время коммита фиксирует внешний read-only наблюдатель mode=ro с опросом 0.1 с) и задержка снимок→сокет ≤ SQLITE_POLL_S+0.5 с; интервалы ≤6 с — наблюдение SHOULD; S2 блок Think обновляется по шагам, в bridge.err строки sqlite-emit без текста; 0 строк sqlite_snapshot_divergence/sqlite_transcript_divergence на ≥5 многошаговых ходах (живое подтверждение префиксности ASM-001; иначе флаг false и эскалация владельцу); kill-switch: запись false посреди долгого хода → sqlite-off reason=flag ≤2.0 с (дизайн 1.30 с, контракт ≤5.0 с), ход завершается штатно; /health показывает sqlite_reasoning_mode, sqlite_breaker_state, sqlite_divergence_count == 0, sqlite_drain_deadline_count. Откат: SQLITE_REASONING_ENABLED=false (≤1.30 с, без рестарта) или восстановление бэкапа + kickstart. Отчёт ПРОВЕРЕНО ЛЁГКИМ/ТЯЖЁЛЫМ/НЕ ПРОВЕРЕНО; непустое НЕ ПРОВЕРЕНО = не сдано",
      "environment": "Боевой LaunchAgent com.user.dsh-agy-bridge, существующий рабочий чат DSH, gemini-4-argon effort high, аккаунт agy с квотой; факты в ~/Мой диск/tmp/trace/<дата>/agy-realtime-reasoning/<run-id>/",
      "owner": "Teamlead"
    },
    {
      "id": "VER-012",
      "requirement_ids": [
        "REQ-010",
        "QA-006"
      ],
      "kind": "command",
      "command": "PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /usr/bin/python3 -B -m unittest discover -s tests -p \"test_*agy*.py\"",
      "expected": "exit 0; «OK», 0 failures и 0 errors на боевом /usr/bin/python3 3.9.6 по всем agy-тестам (22 существующих + все TC/AO tests/test_agy_bridge_resilience.py). Full Suite Gate канона (uvx --from pytest==9.0.3 pytest -q -p no:cacheprovider -rf tests/, 0 failed) не снят: он выполняется как pre-MR rollout checkpoint Q-005 — ровно 3 baseline-красных F-56 вне scope (EVD-056: test_b_guard.py::TestTm018Guard::test_tm018_live_check_subprocess, test_muse_bridge_killpg.py::AllowedModelsSyncTest::test_t00_models_and_health_include_wonder_models_400k, test_rpc_rework.py::TestRpcWriteDeadline::test_rw011_shutdown_all_within_budget_with_stuck_child) = BLOCKED: OWNER_DECISION_REQUIRED до MR; любой другой красный = FAIL",
      "environment": "Чистый clone кандидата, cwd=repo_root, /usr/bin/python3 3.9.6 (CommandLineTools), PYTHONDONTWRITEBYTECODE=1; pre-MR checkpoint Q-005 — pytest 9.0.3, ~6 мин, в фоне",
      "owner": "Teamlead"
    }
  ],
  "decisions": [
    {
      "id": "AD-001",
      "status": "APPROVED",
      "kind": "two-way",
      "question": "RC-1: откуда и как брать мышление шага в реальном времени, не ломая ход и контракт?",
      "choice": "Live-источник conversations/<cid>.db: stdlib sqlite3 строго file:…?mode=ro (immutable=1 запрещён при любых условиях) + pure-Python парсер wire-формата step_payload (поле 20 → подполе 3) с обрезкой незавершённого UTF-8 хвоста и проверкой stop_event; опрос в том же потоке, что и _TranscriptTail (единственный владелец seen), ≤16 строк и BLOB ≤256 KiB на опрос, conn.interrupt() при stop; режим хода turn_mode ∈ {LIVE, SHADOW, OFF} фиксируется один раз на старте хода; раздельное состояние observed_* (SQLite-снимки, любой режим) и delivered_* (отдано клиенту, только LIVE); дедупликация по idx == step_index с проверкой префикса sha256: при divergence выдача шага замораживается на уже отданном префиксе (0 склеенных символов), остаток хода — только транскрипт; владение cid через _active_cid_owners (cid → turn_id) под _session_store_lock и обязательный двойной pre-spawn водяной знак для resumed (иначе turn_mode=OFF); семантический canary совместимости agy (SHADOW→LIVE для будущих ходов); breaker с probe_gen и флаг AD-006 (TTL 1.0 с, перепроверка каждые 0.25 с); мышление ≤2 MiB на ход; fail-open на transcript_full.jsonl",
      "alternatives": [
        "B: только транскрипт с более частым опросом — запись шага появляется после DONE (F-29), реалтайма не даёт",
        "C: thinking_delta из stdout stream-json — не сериализуется в agy 1.4.9 (F-27, F-28)",
        "D: Python SDK google-antigravity — мысли только после блокирующего send() (F-37) и новая зависимость",
        "E: CLI sqlite3 подпроцессом — ошибка 14 на той же БД (F-35) и процесс на каждый опрос",
        "F: локальный agentapi — не исследован (OPEN-11), нет фактов",
        "G: immutable=1 для чтения закрытой WAL-БД (R1) — отвергнуто (F-007): отключает блокировки и детект изменений SQLite; внешний CLI/фоновый писатель даёт неконсистентное чтение или SQLITE_CORRUPT",
        "H: дедупликация только по length(step_payload) (R1) — отвергнуто (F-001): не видит изменений одинакового размера и изменений других полей protobuf",
        "I: при divergence выдавать невыданный хвост нового текста поверх уже отданного префикса (R2) — отвергнуто (Seat 1 F-002, Seat 2 F-001): клиент получает гибрид ('abc' + 'de' из 'abXde'), которого не было ни в одном источнике",
        "J: единое поле thinking_len/thinking_sha256 для SHADOW и LIVE (R2) — отвергнуто (Seat 1 F-003): в SHADOW наблюдённая длина выдаётся за отданную, и финал транскрипта теряет начало мышления"
      ],
      "drivers": [
        "REQ-001",
        "REQ-002",
        "REQ-003",
        "REQ-004",
        "REQ-005",
        "REQ-010",
        "REQ-012",
        "Python 3.9.6 stdlib (F-51)",
        "файлы agy только на чтение (handoff §10)"
      ],
      "consequences": [
        "Мост читает внутреннюю недокументированную схему agy 1.4.9: семантический canary держит новый/изменённый бинарь agy в SHADOW (без выдачи клиенту) до подтверждения на транскрипте; транскрипт — минимальный источник (N_floor=1)",
        "≤1 одновременного SQLite read-соединения на ход; огибающая прихода SELECT N(Δt) ≤ 3 + 2·Δt на ход (per-turn bucket, включая drain); ≤16 строк и BLOB ≤256 KiB на строку за опрос; CPU ≤1% ядра на ход (гейт L2 VER-010)",
        "Если mode=ro не открывает БД (закрытая WAL-БД без -shm на 3.9.6, F-52) — ход идёт на транскрипте без live-дельт; immutable как обход не используется",
        "AC-004 (склейка reasoning_content шага побайтово равна final_thinking) выполняется всегда, когда выполняется ASM-001 (префиксная монотонность 20.3); при нарушении ASM-001 (divergence, AC-005) выдача шага чисто останавливается на уже отданном префиксе: 0 повторных и 0 склеенных/выдуманных символов, событие видно в логе и в /health sqlite_divergence_count",
        "Правило выдачи мышления append-only (_reasoning_delta); _reasoning_suffix для text_delta в _pump не меняется",
        "Откат: SQLITE_REASONING_ENABLED=false (худший случай TTL 1.0 + срез 0.25 + busy_timeout 0.05 = 1.30 с ≤ 5.0 с, активный ход тоже) или env AGY_SQLITE_REASONING_ENABLED=0 + kickstart — поведение источника мышления as-is",
        "Выданное мышление хода ограничено MAX_REASONING_BYTES_PER_TURN = 2 MiB (UTF-8): Run.q + out['reasoning'] ≤ 4 MiB на ход, ≤32 MiB на 8 ходов; сверх лимита дельты не ставятся в очередь (одна строка reasoning-cap на ход), текст ответа не затрагивается",
        "/health получает 4 аддитивных диагностических поля (CD-003); существующие поля и hot_sessions неизменны"
      ],
      "approval_required": false,
      "evidence_ids": [
        "EVD-004",
        "EVD-018",
        "EVD-025",
        "EVD-030",
        "EVD-031",
        "EVD-032",
        "EVD-033",
        "EVD-045",
        "EVD-052",
        "EVD-053",
        "EVD-075",
        "EVD-077"
      ],
      "confirmation": {
        "kind": "test",
        "command": "PYTHONPATH=. uvx --from pytest==9.0.3 pytest -q -p no:cacheprovider tests/test_agy_bridge_resilience.py",
        "expected": "exit 0; TC-01..12, 20..24, 30..33, 40..44, 50, 51, 91, 92, AO-01, AO-04, AO-05, AO-06, AO-07, AO-08, AO-09, AO-10, AO-12 зелёные (каждая функция с ≥1 assert, VER-007); VER-005/VER-012 на /usr/bin/python3 зелёные; VER-009 OK"
      },
      "verification_ids": [
        "VER-003",
        "VER-005",
        "VER-007",
        "VER-009",
        "VER-010",
        "VER-011"
      ],
      "details": {
        "component": "Источник мышления хода — один daemon-поток на Run (развитие _TranscriptTail; имя класса — зона Coder). Логические функции _watch_transcript (transcript_full.jsonl каждые TRANSCRIPT_POLL_S=0.05 с, as-is) и _poll_sqlite_reasoning (conversations/<cid>.db каждые SQLITE_POLL_S) исполняются в этом потоке по очереди; поток — единственный писатель seen (без замков), эмитит только через emit-колбэк ('reasoning', str) в Run.q. Граница совместимости F-03/F-06/F-07 не меняется",
        "enablement": "Перед каждым SELECT (каждая итерация _poll_sqlite_reasoning и _drain_post_eof) вызывается _is_sqlite_reasoning_enabled() (AD-006, stat-кэш TTL 1.0 с) и проверяется разрешение breaker'а (AD-005; для пробного хода — совпадение probe_gen) и turn_mode хода; первая инструкция SQLite-пути — if not enabled: return (H-CPU-I3). Ожидание между SELECT нарезается срезами min(remaining_poll_sleep, 0.25) с, после каждого среза флаг перепроверяется (поток продолжает тик транскрипта 0.05 с). Если посреди хода результат стал False — немедленный conn.close() в finally, выход из SQLite-поллера (лог sqlite-off reason=flag|env|breaker|probe_stale|compat), ход бесшовно продолжается на transcript_full.jsonl. Худший случай на всём SQLITE_POLL_S ∈ [0.5, 2.0]: TTL 1.0 + срез 0.25 + busy_timeout 0.05 = 1.30 с ≤ 5.0 с (QA-010, AO-09)",
        "db_path": "CONV_DIR = Path(env AGY_BRIDGE_CONVERSATIONS) или ~/.gemini/antigravity-cli/conversations; путь CONV_DIR / (cid + '.db') строится только если cid fullmatch ^[0-9A-Fa-f-]{8,64}$ (regex — константа модуля) и resolved parent == CONV_DIR.resolve(); иначе источник выключен на ход + одна строка лога",
        "open": "Единственная разрешённая форма: sqlite3.connect(f\"file:{db_path}?mode=ro\", uri=True, timeout=0.05, isolation_level=None, check_same_thread=True) в потоке источника; сразу PRAGMA query_only = ON; PRAGMA busy_timeout = 50; PRAGMA cache_size = -1024. immutable=1, mode=rw/rwc запрещены в любом пути и при любой ошибке (AO-08, VER-009 ищет подстроку immutable). Любое sqlite3.Error (OperationalError unable to open/locked/busy/interrupted, DatabaseError) на connect/execute → handle закрывается в finally, опрос = «изменений нет», одна строка sqlite-open-fail cold=0|1 на ход; cold-open (нет <cid>.db или <cid>.db-wal, либо ошибка до первого успешного SELECT хода) отказом breaker'а не считается (AD-005). Ссылка на открытое соединение хранится в source._active_conn (под source._conn_lock) только на время итерации, чтобы Run.close/_pump могли вызвать conn.interrupt() из другого потока; conn.close() гарантирован в finally потока опроса; повторное открытие — не чаще раза в SQLITE_POLL_S и строго последовательно (≤1 одновременного соединения на ход, AO-04). Если до EOF БД так и не открылась — ход целиком на transcript_full.jsonl (AC-003, AC-006). Явных транзакций нет; строки читаются итерацией курсора по одной, курсор закрывается сразу после выборки — snapshot чтения живёт только на время одного SELECT",
        "query": "Один SELECT на опрос (K_calls=1) по фактической схеме F-31 (таблица steps, PK idx; имена trajectory_steps/step_idx из брифа R1 сопоставлены steps/idx): SELECT idx, status, length(step_payload) AS blob_len, CASE WHEN length(step_payload) <= 262144 THEN step_payload ELSE NULL END AS step_payload FROM steps WHERE step_type = 15 AND idx >= ? AND status IN (8, 3) ORDER BY idx ASC LIMIT 16. MAX_STEP_BLOB_BYTES = 262144 (256 KiB): BLOB больше не материализуется в Python (NULL из SQL) → лог sqlite-oversize cid step blob_len, шаг только из транскрипта. SQLite-опрос запускается только при anchored=True (свежий разговор base_idx=0 или resumed с успешным двойным pre-spawn водяным знаком, watermark_resume), поэтому выборка всегда (8, 3) от base_idx; форма «только status=8 без якоря» удалена. Нижняя граница poll_watermark = base_idx и сдвигается до наименьшего idx, ещё не финализированного в transcript_full.jsonl. LIMIT 16 ограничивает работу итерации; если вернулось 16 строк, остаток читается следующим опросом (через bucket). Строки читаются итерацией курсора по одной (в памяти ≤1 BLOB ≤256 KiB); перед обработкой каждой строки проверяется stop_event.is_set() → немедленный выход с закрытием курсора. Константы STEP_TYPE_PLANNER=15, STEP_STATUS_GENERATING=8, STEP_STATUS_DONE=3 привязаны к agy 1.4.9 и подтверждаются canary. Парсер вызывается только при смене пары (blob_len, sha256(BLOB)) — изменение одинакового размера распознаётся (AO-05)",
        "watermark_resume": "Владение cid (Seat 1 F-004): единственный замок _session_store_lock (никогда не вкладывается в _sqlite_guard_lock и наоборот — один порядок замков) защищает стор горячих сессий и _active_cid_owners: dict[str, str] (cid → turn_id, turn_id = uuid4 хода). Захват: _session_claim (агентный ход, AD-004) или ход с явным conversation_id клиента атомарно под замком проверяет _active_cid_owners.get(cid) in (None, turn_id) и записывает _active_cid_owners[cid] = turn_id; снятие — в finally _run_once, только если владелец == turn_id. Если cid уже принадлежит другому turn_id, второй одновременный запрос cid не разделяет: spawn со свежим cid без --resume (полный промпт истории, is_resume=False), лог cid-busy-fresh — два живых хода никогда не читают один <cid>.db. Унаследованный _in_flight_cids (L130/494) сохраняется и проверяется под тем же замком. Свежий разговор (cid из init, --conversation не передавался): base_idx=0, anchored=True. Resumed (is_resume == True, cid известен до Popen; Seat 1 F-005): до Popen выполняются ОБА водяных знака — (a) transcript_full.jsonl: наибольший step_index t_max (или число строк − 1) и байтовый/строчный offset файла; (b) SQLite: SELECT COALESCE(MAX(idx), -1) FROM steps (db_max) через ту же форму mode=ro. Только если (a) и (b) успешны: anchored=True, base_idx = max(t_max, db_max) + 1. Если pre-spawn SQLite open/query на resumed-ходе не удался (нет .db, sqlite3.Error, timeout) — turn_mode = \"OFF\" на весь ход: SQLite-опрос не запускается (sqlite-off reason=resume_unanchored), мышление из transcript_full.jsonl с pre-spawn байтовым/строчным водяным знаком. Откат к anchored=False со status=8 на resumed-ходе запрещён, поэтому зависшая status=8 строка упавшего прошлого хода не может быть выдана никогда (AO-08). Бюджет ≤0.1 с (timeout 0.05 + скан хвоста транскрипта). Транскрипт для resumed стартует с offset = размер файла ДО spawn (TC-51)",
        "parser": "Чистая функция _extract_thinking_from_step_blob(raw: bytes, final: bool, stop: threading.Event | None = None) -> str ('' = мышления нет), без I/O, логов и рекурсии; каждые 64 wire-тега проверяется stop.is_set() → немедленный возврат '' (частичный результат не выдаётся): varint ≤10 байт; tag = field<<3|wt; wt0/1/5 — пропуск; wt2 — длина varint ≤ остатка; wt3/4/6/7 или выход за границу → ''. Корневое поле 20 (wt2) → вложенный разбор → подполе 3 (wt2), последнее вхождение побеждает. Для нефинального снимка (status == 8) перед декодированием просматриваются последние 1–3 байта: если ведущий байт 0xC0..0xF4 не имеет требуемого числа продолжений 0x80..0xBF до конца буфера, он и его неполные продолжения отбрасываются — разрезанный кириллический символ выдаётся целиком следующим снимком (TC-04). Затем decode('utf-8', errors='replace'): невалидные байты внутри (TC-05, 0xFF 0xFE) дают U+FFFD без исключения; финальный снимок (status == 3) не обрезается. memoryview без копий; размер ≤256 KiB гарантирован SQL (MAX_STEP_BLOB_BYTES). Исключения наружу не выходят",
        "seen_state": "turn_mode: 'LIVE' | 'SHADOW' | 'OFF' фиксируется один раз в Run.__init__ (после водяного знака) из процессных compat, флага и breaker'а и до конца хода не повышается: промоут compat SHADOW → LIVE другим одновременным ходом на активный ход не влияет; OFF — ход без SQLite (флаг/env/breaker/cid/неудачный якорь resumed). Внутри хода режим может только понижаться до transcript-only (флаг выключен, divergence, seen_cap), лог turn_mode cid mode. seen: dict[int, StepState] — blob_len:int, blob_sha256:str; observed_len:int и observed_sha256:str (последний SQLite-снимок 20.3 шага; обновляются в LIVE и SHADOW); delivered_len:int (символы str, реально поставленные в Run.q из SQLite) и delivered_sha256 (hashlib-объект отданной склейки шага, инкрементальный) — обновляются ТОЛЬКО когда turn_mode == 'LIVE' и _emit_reasoning(run, idx, delta, track=True) вернул True (внутри run._emit_lock, AD-002); в SHADOW/OFF delivered_len == 0; diverged:bool (выдача шага заморожена); finalized:bool (финал шага обработан из transcript_full.jsonl). Текст мышления в seen не хранится (~0.4 KiB на шаг). Предел MAX_STEPS_TRACKED=128: при переполнении вытесняется наименьший idx с finalized=True и idx < poll_watermark (его не выберет ни SQLite, ни транскрипт, читающий только вперёд); если вытеснять нечего — SQLite-опрос выключается до конца хода (sqlite-off reason=seen_cap), транскрипт продолжает работу (F-004)",
        "dedup_and_emit": "SQLite-снимок шага idx с thinking длины L: в любом режиме observed_len = L, observed_sha256 = sha256(thinking). Выдача клиенту из SQLite — только при turn_mode == 'LIVE' и not seen[idx].diverged. (1) delivered_len == 0 → эмит thinking целиком. (2) L > delivered_len и sha256(thinking[:delivered_len].encode('utf-8')).hexdigest() == delivered_sha256 → эмит delta = thinking[delivered_len:]. (3) Префикс расходится (sha256(new_text[:delivered_len]) != delivered_sha256, в том числе L == delivered_len с другим sha256) → DIVERGENCE: seen[idx].diverged = True — выдача шага idx немедленно замораживается: 0 дальнейших эмитов для idx ни из SQLite, ни из транскрипта; лог sqlite_snapshot_divergence cid step len_prev len_new; отказ хода для breaker'а (AD-005, consecutive_failures); sqlite_divergence_count += 1; SQLite-опрос хода прекращается (conn.close(), sqlite-off reason=divergence), остаток хода transcript-only: шаги > idx выдаются из транскрипта по правилам финала ниже. (4) L < delivered_len при совпадающем префиксе → ничего (устаревший снимок). Финал из transcript_full.jsonl (PLANNER_RESPONSE, step_index = idx, final_thinking): (a) diverged → 0 эмитов, finalized=True; (b) delivered_len == 0 (шаг не стримился, в т. ч. любой шаг в SHADOW/OFF) → эмит final_thinking[0:] целиком; (c) delivered_len > 0 и sha256(final_thinking[:delivered_len].encode('utf-8')).hexdigest() == delivered_sha256 → эмит только final_thinking[delivered_len:] (если длиннее) — склейка шага побайтово равна final_thinking (AC-004); (d) delivered_len > 0 и префикс расходится или final короче delivered_len → DIVERGENCE: diverged = True, лог sqlite_transcript_divergence, отказ breaker'а, sqlite_divergence_count += 1, 0 эмитов — хвост final_thinking[delivered_len:] к чужому префиксу НЕ приклеивается (отдано 'abc', финал 'abXde' → клиент получил ровно 'abc', гибрид 'abcde' невозможен), остаток хода transcript-only. После финала finalized=True. Контракт: AC-004 (побайтовое равенство склейки шага и final_thinking) выполняется всегда, когда выполняется ASM-001 (префиксная монотонность); при нарушении ASM-001 (divergence, AC-005) выдача шага чисто останавливается на уже отданном префиксе — 0 повторных символов, 0 склеенных/выдуманных символов; клиент получает усечённое, но не искажённое мышление шага",
        "compat": "Семантический canary совместимости (F-005): процессное состояние compat ∈ {SHADOW, LIVE} под _sqlite_guard_lock с ключом — идентичность бинаря agy (st_mtime_ns, st_size) файла AGY_BRIDGE_AGY_BIN (по умолчанию ~/.local/bin/agy.real, F-25), один stat в Run.__init__. Неизвестная/изменившаяся идентичность или ошибка stat → SHADOW. turn_mode фиксируется на старте хода из compat (seen_state): промоут compat другим одновременным ходом не меняет режим активного хода. В SHADOW SQLite-поллер парсит и ведёт observed_*, но НЕ эмитит клиенту; delivered_len остаётся 0, поэтому финал из transcript_full.jsonl выдаётся клиенту целиком — final_thinking[0:] (100 % final_thinking), мышление as-is. Промоут SHADOW → LIVE (для будущих ходов): на шаге с финалом из транскрипта observed_sha256 последнего status=3 снимка 20.3 того же idx == sha256(final_thinking) при len > 0 (CANARY_STEPS=1, как F-33). Несовпадение observed с финалом в SHADOW — лог sqlite_transcript_divergence, отказ breaker'а, compat остаётся SHADOW (выдача клиенту не затронута). Пропажа live-источника (транскрипт дал непустой thinking, а status=3 снимок того же idx дал '') логируется отдельно sqlite-live-loss и переводит compat в SHADOW для следующих ходов. Любая divergence в LIVE → compat SHADOW для следующих ходов + отказ breaker'а. Синтаксически валидный, но семантически несовместимый формат новой версии agy клиенту не отправляется",
        "observability": "Строки stderr: sqlite-on/off cid=<8> reason=flag|env|breaker|probe_stale|compat|cid|cid_busy|seen_cap|resume_unanchored|divergence; turn_mode cid=<8> mode=LIVE|SHADOW|OFF; cid-busy-fresh cid=<8>; sqlite-emit cid=<8> step=N len=L; sqlite-gen cid=<8> step=N (первое наблюдение status=8 с непустым 20.3); sqlite-open-fail cid=<8> err=<класс> cold=0|1; sqlite-oversize cid=<8> step=N blob_len=B; sqlite-schema-mismatch; sqlite_snapshot_divergence; sqlite_transcript_divergence; sqlite-live-loss; compat state=SHADOW|LIVE; drain cid=<8> ms=… emitted=… outcome=complete|window_complete pending_steps=N exit=end_turn|planner_final|window; drain-timeout; reasoning-late-drop; reasoning-cap cid=<8> bytes=B; breaker state=… probe_gen=G. /health (аддитивно; существующие поля и hot_sessions неизменны; значения из процессных счётчиков под _sqlite_guard_lock, без SQLite-вызовов): \"sqlite_reasoning_mode\": \"live\" | \"shadow\" | \"off\" | \"breaker_open\" (off — флаг/env выключены; breaker_open — breaker OPEN; иначе compat), \"sqlite_breaker_state\": \"closed\" | \"open\" | \"half_open\", \"sqlite_divergence_count\": int (с рестарта), \"sqlite_drain_deadline_count\": int (drain с outcome=window_complete при pending_steps > 0 и drain-timeout). Без текста мышления, промптов и секретов (TC-92, THREAT-004)",
        "memory_bounds": "MAX_REASONING_BYTES_PER_TURN = 2 * 1024 * 1024 (2 MiB UTF-8 выданного мышления на ход, счётчик в Run под run._emit_lock): сверх лимита _emit_reasoning возвращает False, дельта в Run.q не ставится, одна строка reasoning-cap на ход; ответ и tool-события не затрагиваются. MAX_STEP_BLOB_BYTES = 262144 (256 KiB, SQL CASE). Отсюда Run.q + out['reasoning'] ≤ 2 + 2 = 4 MiB на ход, ≤32 MiB на 8 ходов; Mem_rss_worker_max = 112 MiB (HL-ENV, memory_closure_check)"
      }
    },
    {
      "id": "AD-002",
      "status": "APPROVED",
      "kind": "two-way",
      "question": "RC-2: как гарантировать, что мышление последнего шага (запись через ~90 мс после result) уходит до done, не продлевая ход больше 1.0 с?",
      "choice": "Join-before-done с абсолютным бюджетом и атомарным закрытием очереди: Run._pump после EOF stdout ждёт процесс не дольше PROC_EXIT_WAIT_S=0.05 с, ставит _proc_done, ждёт поток источника (окно drain, затем conn.interrupt() активного SELECT и join JOIN_TIMEOUT_S) и кладёт ('done', …) через _close_and_put_done под run._emit_lock; Handler._execute не выходит по result ERROR, а дочитывает Run.q до done. Drain: полное окно DRAIN_WINDOW_S=0.35 с (диапазон [0.20, 0.50], шаг 0.05 с, 7 тиков) без эвристического раннего выхода; досрочно — только по авторитетному маркеру конца хода после DRAIN_MIN_S=0.15 с",
      "alternatives": [
        "B: _execute после done ждёт поток источника и дочитывает очередь — размазывает ответственность lifecycle между Handler и Run",
        "C: отдельный маркер конца источника и ожидание двух маркеров в _execute — больше состояний в презентационном цикле и все ветки выхода _execute",
        "D: увеличить паузу _pump больше TRANSCRIPT_GRACE_S — остаётся гонкой по времени и добавляет фиксированную задержку всем ходам",
        "E: выход _execute по result ERROR с последующим join (R1) — отвергнуто (Seat 1 #1): Run.close в _run_once обрывает drain, мышление последнего шага не попадает в delivered и запускается запрещённый повтор",
        "F: ранний выход после DRAIN_MIN_S по эвристике «≥1 PLANNER_RESPONSE + все виденные SQLite-шаги в транскрипте» (R2) — отвергнуто (Seat 1 F-001): без авторитетного маркера конца хода шаг, ещё не записанный в SQLite, теряется"
      ],
      "drivers": [
        "REQ-006",
        "REQ-007",
        "REQ-010",
        "T-LIFE/v1",
        "R-BULK-I1"
      ],
      "consequences": [
        "EOF→done ≤ 0.05 + 0.05 + 0.35 + 0.15 = 0.60 с, EOF→stop ≤ 0.65 с при дефолтах; на максимумах разрешённых диапазонов 0.05 + 0.05 + 0.50 + 0.20 + 0.05 = 0.85 с ≤ 1.0 с (AC-009)",
        "Ход без авторитетного маркера конца хода (включая выключенный SQLite и ход без мышления) дренируется полное окно DRAIN_WINDOW_S (0.35 с) — цена полноты (RISK-007)",
        "outcome=complete только при pending_steps == 0 и наблюдённом финальном PLANNER_RESPONSE; истечение окна иначе — outcome=window_complete pending_steps=N; записи после окна (TC-63) не читаются — обещание сужено до документированного окна доставки",
        "Поток источника без bind и при stop_event выходит сразу — нет 120-секундного висения",
        "Ни одно ('reasoning', …) не попадает в Run.q после ('done', …): проверка drain_closed и put обоих событий под одним run._emit_lock"
      ],
      "approval_required": false,
      "evidence_ids": [
        "EVD-006",
        "EVD-007",
        "EVD-008",
        "EVD-029",
        "EVD-043",
        "EVD-075",
        "EVD-077"
      ],
      "confirmation": {
        "kind": "test",
        "command": "PYTHONPATH=. uvx --from pytest==9.0.3 pytest -q -p no:cacheprovider tests/test_agy_bridge_resilience.py",
        "expected": "exit 0; TC-60 (20 прогонов в L1), TC-61, TC-62, TC-63, AO-03, AO-04, AO-11 зелёные; L2 VER-010 100/100 и EOF→stop ≤1.0 с на дефолтах и максимумах"
      },
      "verification_ids": [
        "VER-003",
        "VER-005",
        "VER-007",
        "VER-010"
      ],
      "details": {
        "pump_order": "EOF stdout → t_eof = monotonic() → rc = proc.wait(timeout=PROC_EXIT_WAIT_S=0.05) (TimeoutExpired → rc=None, процесс добивает Run.close/_kill_group as-is; EOF при живом процессе не продлевает бюджет, F-003) → sleep 0.05 (stderr, as-is) → t_exit = monotonic(); _proc_done.set() → source.thread.join(timeout = max(0, t_exit + DRAIN_WINDOW_S − now)) → если поток жив: source.interrupt_active_query() (conn.interrupt() активного соединения, если есть) → source.thread.join(timeout=JOIN_TIMEOUT_S) → если поток всё ещё жив: лог drain-timeout, sqlite_drain_deadline_count += 1 → _close_and_put_done(run, payload). run._emit_lock = threading.Lock() создаётся в Run.__init__. _emit_reasoning(run, idx, delta, track) -> bool: под run._emit_lock — if run.drain_closed: return False (лог reasoning-late-drop вне замка); при превышении MAX_REASONING_BYTES_PER_TURN — return False (reasoning-cap); run.q.put(('reasoning', delta)); при track (SQLite-дельта в LIVE) seen[idx].delivered_len += len(delta) и delivered_sha256.update(delta.encode('utf-8')) внутри замка; return True. _close_and_put_done(run, payload): под run._emit_lock — run.drain_closed = True; run.q.put(('done', payload)). Поэтому ни одно ('reasoning', …) не может оказаться в Run.q после ('done', …). pump_error: _proc_done.set(), stop_event источника, под run._emit_lock drain_closed = True и постановка события ошибки as-is, без join",
        "drain_loop": "_drain_post_eof на _proc_done (не stop): окно deadline = t_exit + DRAIN_WINDOW_S (дефолт 0.35 с = 7 тиков по DRAIN_POLL_STEP_S=0.05 с; clamp [0.20, DRAIN_MAX_S=0.50]). На каждом тике: _watch_transcript; _poll_sqlite_reasoning — если флаг (AD-006) + breaker (AD-005, probe_gen) + turn_mode разрешают и в per-turn bucket есть токен (N(Δt) ≤ 3 + 2·Δt), только mode=ro без immutable, статусы (8, 3), LIMIT 16. Эвристический ранний выход на DRAIN_MIN_S без авторитетного маркера конца хода удалён (Seat 1 F-001). Досрочный выход после DRAIN_MIN_S=0.15 с разрешён ТОЛЬКО если transcript_full.jsonl текущего хода (step_index ≥ base_idx) содержит терминальный шаг конца хода: (i) END_TURN / TURN_COMPLETE (имена принимаются, если наблюдаются; на agy 1.4.9 фактами F-29/F-33 подтверждён только PLANNER_RESPONSE — при отсутствии таких записей путь (i) не срабатывает), либо (ii) PLANNER_RESPONSE с непустым текстом финального ответа И 0 строк status=8 с idx ≥ base_idx в SQLite на двух подряд тиках 0.05 с (оба SELECT успешны и вернули < 16 строк; при выключенном SQLite, turn_mode OFF/SHADOW без соединения или нехватке токена условие (ii) не доказуемо → drain до конца окна). Иначе drain идёт всё окно DRAIN_WINDOW_S. pending_steps — число idx ≥ base_idx, виденных SQLite (status 8 или 3), но не финализированных в транскрипте. Итог — строка drain cid ms emitted outcome=… pending_steps=N exit=end_turn|planner_final|window: outcome=complete только если pending_steps == 0 И наблюдался финальный PLANNER_RESPONSE (досрочно по (i)/(ii) или на истечении окна); иначе на истечении окна (не позже DRAIN_MAX_S = 0.50 с) — outcome=window_complete pending_steps=<count>; при pending_steps > 0 sqlite_drain_deadline_count += 1",
        "join_before_done": "Run._pump кладёт ('done', …) только через _close_and_put_done после join единого потока источника, который исполняет и _watch_transcript, и _poll_sqlite_reasoning: join окна (≤ DRAIN_WINDOW_S от t_exit), затем conn.interrupt() активного SELECT (если поток ещё жив) и join(timeout=JOIN_TIMEOUT_S=0.15). Работа одной итерации ограничена: ≤16 строк × BLOB ≤256 KiB; stop_event проверяется перед каждой строкой и каждые 64 wire-тега парсера; conn.interrupt() прерывает C-уровневый SELECT (sqlite3.OperationalError interrupted по собственному stop/interrupt — не отказ breaker'а), conn.close() — в finally потока опроса. FIFO Run.q и run._emit_lock гарантируют, что все ('reasoning', …) из drain стоят до done, а после done не ставится ни одно",
        "execute_drain": "Handler._execute: при ('result', …) со status == 'ERROR' НЕ выполняется return/break; событие сохраняется (result_ev, state agy_error), цикл while True продолжает вычитывать run.q до ('done', …) (или pump_error/client_gone/timeout as-is). Все ('reasoning', …) из _drain_post_eof и join_before_done попадают в out['reasoning'] и delivered['reasoning_chars'] (и в SSE через on_reasoning) ДО возврата в _run_once и вычисления should_retry_empty_turn/delivered (AD-003). Ожидание done ограничено бюджетом _pump (≤0.65 с после EOF при дефолтах, ≤0.85 с на максимумах)",
        "stop_path": "stop_event (Run.close: client_gone/timeout/ошибка) → stop_event.set() и source.interrupt_active_query() (conn.interrupt() активного SELECT) → немедленный выход без grace-сна; conn.close() гарантирован в finally потока опроса",
        "unbound": "Ожидание bind прерывается при _proc_done или stop_event (сейчас только stop/120 с) — join в _pump не может зависнуть",
        "late_events": "_emit_reasoning после drain_closed возвращает False и в очередь не ставит (проверка флага и put под одним run._emit_lock): лог reasoning-late-drop cid step len (REQ-006 «не теряются молча»). Записи, появившиеся после выхода потока источника (TC-63, через 1.5 с), никто не читает: обещание сужено до окна DRAIN_WINDOW_S (≤ DRAIN_MAX_S), неопределённость видна как outcome=window_complete pending_steps>0",
        "budget": "Константы и допустимые диапазоны (clamp при чтении env): DRAIN_WINDOW_S=0.35 ∈ [0.20, 0.50] (env AGY_BRIDGE_TRANSCRIPT_GRACE переосмыслен как окно drain), DRAIN_MAX_S=0.50 — жёсткая верхняя граница окна, DRAIN_MIN_S=0.15 ∈ [0.05, 0.25] (env AGY_BRIDGE_DRAIN_MIN), DRAIN_MIN_S = min(DRAIN_MIN_S, DRAIN_WINDOW_S), DRAIN_POLL_STEP_S=0.05 (7 тиков на дефолтном окне), JOIN_TIMEOUT_S=0.15 ∈ [0.05, 0.20] (env AGY_BRIDGE_DRAIN_JOIN), PROC_EXIT_WAIT_S=0.05. Пост-EOF drain+join: дефолт 0.35 + 0.15 = 0.50 с, максимум 0.50 + 0.20 = 0.70 с. Полный путь EOF→stop: дефолт 0.05 + 0.05 + 0.50 + 0.05 (_execute as-is) = 0.65 с; максимум 0.05 + 0.05 + 0.70 + 0.05 = 0.85 с ≤ 1.0 с (AC-009) при любых разрешённых настройках"
      }
    },
    {
      "id": "AD-003",
      "status": "APPROVED",
      "kind": "two-way",
      "question": "RC-3: как защитить уже отданный клиенту reasoning при сбое на следующем шаге?",
      "choice": "Отданное потоковое мышление — выдача: delivered = bool(text or tool_calls or (stream and reasoning)); после выдачи нет ни невидимого повтора, ни холодного fallback горячей сессии; исход — неизменный контракт ошибки после старта потока: data:{error} + [DONE]; отданные чанки не повторяются. JSON-режим не меняется (там мышление клиенту ещё не отдано). Handler._execute дочитывает Run.q до done и при result ERROR (AD-002.execute_drain), поэтому мышление последнего шага учтено в delivered до решения о повторе",
      "alternatives": [
        "B: явный флаг «байты отданы» из колбэков on_text/on_reasoning — точнее, но шире правка колбэков и тестовых заглушек; эквивалентен A для SSE",
        "C: stop с частичным ответом вместо кадра ошибки — сохраняет блок Think, но маскирует сбой и меняет контракт ошибки; вынесено владельцу (Q-002)",
        "D: учитывать reasoning и в JSON-режиме — лишает нестриминговые запросы безопасного повтора без пользы"
      ],
      "drivers": [
        "REQ-008",
        "REQ-010",
        "R-BULK-I2",
        "NON_IDEMPOTENT_RETRY"
      ],
      "consequences": [
        "При квотной ошибке после мышления клиент получает кадр error вместо повторного хода: 1 spawn вместо 2-3 (F-46)",
        "Горячая сессия после сбоя всё так же инвалидируется (as-is), но холодный повтор поверх отданного мышления не запускается",
        "Если DSH затирает Think кадром ошибки (F-47) — UX-риск RISK-008 остаётся до решения владельца"
      ],
      "approval_required": false,
      "evidence_ids": [
        "EVD-009",
        "EVD-010",
        "EVD-011",
        "EVD-046",
        "EVD-047",
        "EVD-076"
      ],
      "confirmation": {
        "kind": "test",
        "command": "PYTHONPATH=. uvx --from pytest==9.0.3 pytest -q -p no:cacheprovider tests/test_agy_bridge_resilience.py",
        "expected": "exit 0; TC-70 (1 запуск, 0 повторных чанков), TC-71 (нет холодного повтора), TC-72 (повтор до выдачи сохранён), AO-11 (reasoning после result ERROR учтён до решения о повторе) зелёные"
      },
      "verification_ids": [
        "VER-003",
        "VER-005",
        "VER-007",
        "VER-011"
      ]
    },
    {
      "id": "AD-004",
      "status": "APPROVED",
      "kind": "two-way",
      "question": "RC-4: как не дать фоновым и plain-запросам без инструментов занять, перезаписать или перехватить горячую сессию чужого диалога?",
      "choice": "use_session_store = (tools_count > 0) and (not is_bg): запросы без инструментов (plain) и фоновые не читают и не пишут _session_store вообще (ни _session_claim, ни _session_commit/_session_invalidate; ctx sess_key=None). is_bg — классификатор фонового запроса; единственный подтверждённый фактами признак фона DSH — отсутствие tools (F-42), поэтому сейчас is_bg ⇔ tools_count == 0, точка расширения оставлена. sess_key = (model_id, cwd, effort) — формат ключа as-is, используется только агентными запросами. Явный conversation_id клиента — как сейчас; владение cid — _active_cid_owners (cid → turn_id) под _session_store_lock для горячих и явных cid: cid, занятый другим turn_id, второй запрос не разделяет и получает свежий cid без --resume (AD-001.watermark_resume)",
      "alternatives": [
        "A: признак agentic в ключе + обход стора только для one-shot (R1) — отвергнуто (Seat 1 #3): на 2-м ходу нового plain-диалога _session_claim забирал cid прошлого plain-диалога и отрезал историю",
        "B: только признак tools в ключе — фоновые заголовки разных чатов продолжали бы разговоры друг друга",
        "C: хеш первой user-реплики в ключе plain-класса — поведение DSH для такого ключа не исследовано (F-12), выше риск ложных промахов; оставлено как будущая оптимизация"
      ],
      "drivers": [
        "REQ-009",
        "THREAT-005",
        "M-SEM/v1"
      ],
      "consequences": [
        "Фоновая генерация заголовка и plain-диалоги всегда холодные (полная история) и без коммита — их cid не попадает в стор, разные plain-диалоги никогда не делят cid",
        "Plain-чаты теряют горячие продолжения (RISK-009): корректность сохраняется ценой холодного запуска",
        "Формат ключа и API стора не меняются; после рестарта стор пуст (as-is)"
      ],
      "approval_required": false,
      "evidence_ids": [
        "EVD-012",
        "EVD-013",
        "EVD-041",
        "EVD-042",
        "EVD-075"
      ],
      "confirmation": {
        "kind": "test",
        "command": "PYTHONPATH=. uvx --from pytest==9.0.3 pytest -q -p no:cacheprovider tests/test_agy_bridge_resilience.py",
        "expected": "exit 0; TC-80, TC-81, TC-82 зелёные (в т.ч. два разных plain-диалога по 2 хода не получают cid друг друга и _session_claim не вызывается); лог exec содержит sess=agentic|plain|bg"
      },
      "verification_ids": [
        "VER-003",
        "VER-005",
        "VER-007",
        "VER-011"
      ]
    },
    {
      "id": "AD-005",
      "status": "APPROVED",
      "kind": "two-way",
      "question": "Какие resilience-guardrails нужны на изменяемых путях, чтобы закрыть R-BULK-I2/I3, S-HERD-I2 и O-EXIT без расширения объёма?",
      "choice": "(1) Процессный retry budget в целых десятых токена: capacity_tenths=30 (старт 30), +2 десятых на первичный запрос (не выше 30), повтор (включая hot→cold fallback) стоит 10 десятых; нет 10 — нет повтора + лог retry-budget-exhausted; float не используется. (2) Per-turn token bucket SQLite-опроса в целых десятых: capacity_tenths=30, пополнение 20 десятых/с (2.0 SELECT/с) по monotonic, стоимость 10 десятых на SELECT; владелец — поток источника хода, ограничивает и опрос в drain. Огибающая прихода: N(Δt) ≤ 3 + 2·Δt SELECT на ход на любом окне Δt (начальный всплеск ≤3, устойчиво ≤2.0 SELECT/с на ход, ≤16.0 SELECT/с суммарно на 8 ходов). (3) Пауза повтора Full Jitter U(0, min(2.0, 2.0·2^(a-1))) через инъецируемый RNG. (4) SQLite circuit breaker процесса CLOSED → OPEN → HALF_OPEN. Сбойный ход (инкремент consecutive_failures) — ТОЛЬКО: sqlite3.DatabaseError; ИЛИ sqlite3.OperationalError после ≥1 успешного SELECT этого хода на существующем <cid>.db-wal; ИЛИ схемная ошибка (нет таблицы/колонок steps); ИЛИ divergence префикса. Ожидаемый cold-open — нет <cid>.db или <cid>.db-wal, либо OperationalError на connect/до первого успешного SELECT хода — и OperationalError interrupted от собственного stop/conn.interrupt() отказом не считаются (лог sqlite-open-fail cold=1). Ход с ≥1 успешным SELECT и 0 ошибок сбрасывает consecutive_failures = 0. CLOSED → OPEN после K=3 подряд сбойных ходов (единичная divergence — отказ хода, не мгновенный OPEN); OPEN держится cooldown=30.0 с без connect; затем HALF_OPEN: первый ход атомарно под _sqlite_guard_lock берёт пробу — _breaker_probe_gen += 1, my_probe_gen = _breaker_probe_gen, _breaker_active_probe_gen = my_probe_gen, probe_started_at = monotonic(); остальные ходы идут без SQLite. Перед каждым SELECT пробного хода под _sqlite_guard_lock проверяется _breaker_state == 'HALF_OPEN' and _breaker_active_probe_gen == my_probe_gen; иначе (аренда 60.0 с истекла и пробу probe_gen + 1 взял другой ход) устаревшая проба немедленно прекращает SQLite-опрос (conn.close(), лог sqlite-off reason=probe_stale), а её finally — no-op, так как my_probe_gen != _breaker_active_probe_gen. finally актуальной пробы: ≥1 SELECT и 0 сбоев → CLOSED (consecutive_failures=0, _breaker_active_probe_gen=None); сбой → OPEN (opened_at=monotonic(), _breaker_active_probe_gen=None); ни одного SELECT (БД не появилась, быстрый ответ, stop, cold-open) → _breaker_active_probe_gen=None, остаётся HALF_OPEN для следующего хода. Аренда пробы старше 60.0 с истекает автоматически (следующий ход берёт probe_gen + 1). (5) Один threading.Lock _sqlite_guard_lock охватывает breaker (включая _breaker_probe_gen/_breaker_active_probe_gen), retry budget, compat-состояние, кэш dynamic_config и счётчики /health; без I/O под замком; тестовый хелпер _reset_sqlite_guards_for_tests() сбрасывает все процессные глобалы. (6) Одна строка O-EXIT done на каждом выходе _run_once, включая no-slot и launcher_unavailable",
      "alternatives": [
        "Оставить as-is: 1 повтор на каждый запрос без процессного бюджета — при квотном шторме (F-46) нагрузка на agy удваивается, R-BULK-I2 не закрыт",
        "Только per-request лимит без bucket — не ограничивает суммарные повторы за окно",
        "Без breaker — после автоапдейта agy каждый ход тратит опросы на неверную схему и может эмитить расходящийся текст",
        "Float-бакет (R1) — накопление +0.2 даёт 0.9999999999999999 < 1.0 и режет законный повтор (Seat 1 #5)",
        "Мгновенный OPEN по первой divergence на 600 с (R1) — единичная аномалия одного разговора гасит live-мышление всех 8 слотов (Seat 1, риски #2)",
        "Проба HALF_OPEN без поколения (R2) — отвергнуто (Seat 1 F-009): устаревшая проба после истечения аренды 60 с продолжает SELECT и в finally затирает исход новой пробы",
        "Любой sqlite3.OperationalError — отказ хода (R2) — отвергнуто (Seat 2 F-002): холодный старт нового разговора (<cid>.db/-wal ещё нет) на трёх свежих ходах открывал бы breaker для всех слотов"
      ],
      "drivers": [
        "R-BULK-I2",
        "R-BULK-I3",
        "S-HERD-I2",
        "O-EXIT/v1",
        "REQ-004",
        "REQ-008",
        "REQ-012"
      ],
      "consequences": [
        "Под штормом сбоев часть запросов вернёт ошибку без повтора (RISK-010)",
        "Пауза повтора случайна в [0, 2] с; тесты используют инъецированный RNG и FakeClock без wall-clock",
        "SQLite выключается для процесса только после 3 подряд проблемных ходов и на 30 с; HALF_OPEN не зависает при нерезультативной пробе",
        "Логи done появляются и на ранних выходах; существующий префикс `done model=` сохранён для grep (F-40)",
        "Холодные ходы (БД ещё не создана) не двигают breaker; устаревшая проба HALF_OPEN не может изменить FSM"
      ],
      "approval_required": false,
      "evidence_ids": [
        "EVD-046",
        "EVD-063",
        "EVD-068",
        "EVD-075",
        "EVD-077"
      ],
      "confirmation": {
        "kind": "test",
        "command": "PYTHONPATH=. uvx --from pytest==9.0.3 pytest -q -p no:cacheprovider tests/test_agy_bridge_resilience.py",
        "expected": "exit 0; AO-01 (FSM breaker: 10 одновременных ходов → ровно 1 проба с probe_gen, три исхода пробы, автоистечение 60 с и no-op устаревшей пробы, cold-open не считается отказом), AO-02 (целочисленный бюджет: ≤23 повторов на 100 сбоев, сценарий 0.2×N ровно 10 десятых), AO-05 (огибающая N(Δt) ≤ 3 + 2·Δt SELECT на ход включая drain), AO-06 зелёные"
      },
      "verification_ids": [
        "VER-003",
        "VER-007"
      ]
    },
    {
      "id": "AD-006",
      "status": "APPROVED",
      "kind": "two-way",
      "question": "Как включать/выключать SQLite-источник (REQ-011) с мгновенным kill-switch и без нарушения канона фичефлагов?",
      "choice": "Двухуровневый выключатель fail-closed: _is_sqlite_reasoning_enabled() = (os.environ.get('AGY_SQLITE_REASONING_ENABLED', '1') not in ('0', 'false', 'False')) AND runtime-флаг SQLITE_REASONING_ENABLED is True в bridges/agy-bridge/dynamic_config.json (рядом с server.py; деплой ~/.dsh/bridges/agy-bridge/dynamic_config.json; в git не коммитится). Чтение файла со stat-кэшем (mtime_ns, size) и TTL 1.0 с под _sqlite_guard_lock; при любом OSError (включая FileNotFoundError после ранее закэшированного true), ValueError, отсутствии ключа или не-boolean значении кэш немедленно сбрасывается в False. Кодовый default — False (файла нет → выключено). Функция вызывается перед каждым SELECT опроса и drain, а ожидание между SELECT в _poll_sqlite_reasoning нарезается срезами min(remaining_poll_sleep, 0.25) с с перепроверкой флага после каждого среза: выключение посреди хода закрывает соединение и переводит ход на транскрипт без рестарта. Худший случай на всём SQLITE_POLL_S ∈ [0.5, 2.0]: TTL 1.0 + срез 0.25 + busy_timeout 0.05 = 1.30 с ≤ 2.0 с (гейт) ≤ 5.0 с (контракт QA-010). Env — только аварийное выключение (через рестарт), принудительного включения env нет. RC-2..RC-4 и AD-005 от флага не зависят",
      "alternatives": [
        "Только env AGY_SQLITE_REASONING_ENABLED с default=1 (пример брифа) — новое поведение без флага default=false, kill-switch требует правки plist и рестарта",
        "Env с default=0 и включение через plist — включение и откат только через рестарт LaunchAgent",
        "Флаг читается один раз на ход (R1) — выключение не гасит уже идущий ход длительностью до 1800 с (F-006)",
        "Расширить core/context_resilience FlagSource — вне target_files и чужая зона core/",
        "Stat-кэш TTL 5.0 с и ожидание целым SQLITE_POLL_S (R2) — отвергнуто (Seat 1 F-008, Seat 2 F-003): при SQLITE_POLL_S=2.0 худший случай 5.0 + 2.0 + 0.05 = 7.05 с > 5.0 с"
      ],
      "drivers": [
        "REQ-011",
        "канон «фича за флагом default=false, kill-switch без рестарта» (EVD-065)",
        "REUSE in-repo прецедента zen (EVD-064)"
      ],
      "consequences": [
        "После деплоя server.py поведение мышления as-is до явного включения флага на шаге L3 (фаза B)",
        "Kill-switch — запись false в файл (или удаление файла) без рестарта, действует и на активный ход: худший случай 1.30 с на любом SQLITE_POLL_S (гейт ≤2.0 с, контракт ≤5.0 с); env 0 — аварийное выключение через kickstart",
        "L2 включает флаг файлом dynamic_config.json в каталоге моста clean-room (env-форсирования нет)",
        "Отклонение от примера брифа (env default=1 как единственный переключатель) вынесено владельцу (Q-004)"
      ],
      "approval_required": false,
      "evidence_ids": [
        "EVD-064",
        "EVD-065",
        "EVD-071",
        "EVD-075",
        "EVD-077"
      ],
      "confirmation": {
        "kind": "test",
        "command": "PYTHONPATH=. uvx --from pytest==9.0.3 pytest -q -p no:cacheprovider tests/test_agy_bridge_resilience.py",
        "expected": "exit 0; TC-91 (флаг выкл → sqlite3.connect call_count==0), AO-05 (json.loads один раз при неизменном stat в пределах TTL 1.0 с), AO-09 (выключение посреди хода → SELECT прекращаются ≤1.30 с FakeClock при SQLITE_POLL_S 0.5 и 2.0, соединение закрыто, ход done) зелёные; VER-009 и VER-008 зелёные"
      },
      "verification_ids": [
        "VER-003",
        "VER-007",
        "VER-008",
        "VER-009",
        "VER-011"
      ]
    }
  ],
  "quality_scenarios": [
    {
      "id": "QA-001",
      "quality": "performance",
      "source": "DSH client",
      "stimulus": "argon пишет мышление шага в БД снимками 523→2156 байт с интервалами 1.5-5.1 с",
      "environment": "здоровый ход, флаг включён, /usr/bin/python3",
      "artifact": "bridges/agy-bridge/server.py источник мышления",
      "response": "чанки reasoning_content до завершения шага",
      "response_measure": "≥2 чанка до status=3; L2 (детерминированно): коммит снимка → запись в SSE-сокет ≤ SQLITE_POLL_S + 0.5 с (≤1.0 с при 0.5 с, AC-002); L3: первый чанк ≤5.0 с от первой строки status=8 с непустым 20.3",
      "verification_ids": [
        "VER-003",
        "VER-010",
        "VER-011"
      ]
    },
    {
      "id": "QA-002",
      "quality": "usability",
      "source": "владелец в DSH",
      "stimulus": "фаза мышления 15-45 с",
      "environment": "боевой :9887, gemini-4-argon high",
      "artifact": "SSE-поток моста",
      "response": "блок Think обновляется во время мышления",
      "response_measure": "интервал между дельтами мышления ≤6 с (ASM-008)",
      "verification_ids": [
        "VER-010",
        "VER-011"
      ]
    },
    {
      "id": "QA-003",
      "quality": "reliability",
      "source": "agy 1.4.9",
      "stimulus": "запись PLANNER_RESPONSE через 90 мс после result и немедленный выход",
      "environment": "фейковый лончер",
      "artifact": "Run._pump + drain источника",
      "response": "мышление последнего шага до finish_reason=stop",
      "response_measure": "100/100 прогонов (L2), 20/20 в L1; EOF→stop ≤1.0 с (≤0.65 с при дефолтах, ≤0.85 с на максимумах диапазонов)",
      "verification_ids": [
        "VER-003",
        "VER-010"
      ]
    },
    {
      "id": "QA-004",
      "quality": "reliability",
      "source": "файловая система / agy",
      "stimulus": "БД отсутствует, не открывается mode=ro (закрытая WAL-БД на 3.9.6), заблокирована, битая, без таблицы steps, BLOB > 256 KiB",
      "environment": "флаг включён",
      "artifact": "SQLite-источник",
      "response": "fail-open: ход done, мышление из транскрипта",
      "response_measure": "0 исключений наружу; текст и мышление равны прогону без SQLite; ход не дольше REQ-007",
      "verification_ids": [
        "VER-003",
        "VER-005"
      ]
    },
    {
      "id": "QA-005",
      "quality": "reliability",
      "source": "agy",
      "stimulus": "Individual quota reached после отданного мышления",
      "environment": "SSE, горячая или холодная сессия",
      "artifact": "Handler._run_once",
      "response": "без невидимого повтора; data:{error}+[DONE]",
      "response_measure": "ровно 1 spawn; 0 повторных чанков мышления",
      "verification_ids": [
        "VER-003",
        "VER-011"
      ]
    },
    {
      "id": "QA-006",
      "quality": "compatibility",
      "source": "DSH и существующие тесты",
      "stimulus": "любой запрос после изменения",
      "environment": "кандидат MR",
      "artifact": "HTTP/SSE контракт :9887",
      "response": "форма чанков, эндпоинты, порт и флаги agy неизменны",
      "response_measure": "22 legacy теста зелёные без правок; targeted-гейты 0 падений; полный набор 0 failed (VER-012; ровно 3 baseline-красных F-56 → BLOCKED: OWNER_DECISION_REQUIRED, Q-005)",
      "verification_ids": [
        "VER-003",
        "VER-006",
        "VER-012"
      ]
    },
    {
      "id": "QA-007",
      "quality": "reliability",
      "source": "DSH",
      "stimulus": "агентный ход, параллельный фоновый запрос заголовка без tools, агентный ход",
      "environment": "одна модель/cwd/effort",
      "artifact": "_session_store / sess_key",
      "response": "агентный диалог продолжает свой разговор",
      "response_measure": "третий ход resume=1 с cid первого; фоновый не получает cid первого",
      "verification_ids": [
        "VER-003",
        "VER-011"
      ]
    },
    {
      "id": "QA-008",
      "quality": "cost",
      "source": "8 параллельных ходов",
      "stimulus": "опрос БД 60 с",
      "environment": "/usr/bin/python3, фикстуры",
      "artifact": "поток источника",
      "response": "ограниченное CPU",
      "response_measure": "≤1% ядра на ход (≤0.08 ядра на 8 ходов ≤0.05×2.0 ядра)",
      "verification_ids": [
        "VER-010"
      ]
    },
    {
      "id": "QA-009",
      "quality": "security",
      "source": "agy stdout / файлы agy",
      "stimulus": "cid с ../ или мусор в step_payload",
      "environment": "любой ход",
      "artifact": "путь БД и парсер",
      "response": "нет открытия вне CONV_DIR, нет записи, нет исключения",
      "response_measure": "0 вызовов connect для невалидного cid; парсер возвращает '' на всех усечениях; в логах нет текста мышления",
      "verification_ids": [
        "VER-003",
        "VER-009"
      ]
    },
    {
      "id": "QA-010",
      "quality": "operability",
      "source": "оператор",
      "stimulus": "аварийное выключение SQLite-источника, в том числе во время активного долгого хода",
      "environment": "боевой :9887",
      "artifact": "dynamic_config.json / env",
      "response": "SQLite-поллер активного хода закрывает соединение и выходит, ход продолжается на транскрипте; следующие ходы as-is",
      "response_measure": "≤1.30 с (TTL 1.0 + срез ожидания 0.25 + busy_timeout 0.05) на всём SQLITE_POLL_S ∈ [0.5, 2.0], гейт ≤2.0 с, контракт ≤5.0 с после записи SQLITE_REASONING_ENABLED=false или удаления dynamic_config.json, без рестарта и без обрыва ответа; env AGY_SQLITE_REASONING_ENABLED=0 — после kickstart",
      "verification_ids": [
        "VER-003",
        "VER-007",
        "VER-010",
        "VER-011"
      ]
    },
    {
      "id": "QA-011",
      "quality": "testability",
      "source": "Verifier",
      "stimulus": "прогон L1",
      "environment": "/usr/bin/python3 3.9.6 и uvx pytest",
      "artifact": "tests/test_agy_bridge_resilience.py",
      "response": "детерминированные оракулы без wall-clock флаков",
      "response_measure": "оба интерпретатора зелёные; тайминговые пороги только в L2",
      "verification_ids": [
        "VER-003",
        "VER-005"
      ]
    },
    {
      "id": "QA-012",
      "quality": "reliability",
      "source": "автоапдейт agy",
      "stimulus": "новый бинарь agy с синтаксически валидным, но семантически несовместимым полем 20.3",
      "environment": "флаг включён",
      "artifact": "compat canary источника мышления",
      "response": "SQLite-содержимое не отправляется клиенту в SHADOW; turn_mode фиксируется на старте хода; мышление идёт из транскрипта целиком; промоут LIVE — только для будущих ходов",
      "response_measure": "0 SQLite-эмитов клиенту при turn_mode == SHADOW; delivered_len == 0 и финал транскрипта выдан клиенту целиком (100 % final_thinking); промоут compat другим ходом посреди хода не меняет его turn_mode; промоут LIVE только по observed_sha256 == sha256(final_thinking); строка compat state=SHADOW; sqlite-live-loss отдельно от «мышления нет»",
      "verification_ids": [
        "VER-003",
        "VER-007",
        "VER-011"
      ]
    }
  ],
  "boundaries": [
    {
      "id": "BND-001",
      "component": "Handler.do_POST / _serve_sse / _serve_json",
      "responsibility": "OpenAI framing и единственный writer сокета; вычисляет use_session_store=(tools_count>0) and not is_bg; _execute дочитывает Run.q до done (в т.ч. после result ERROR); форму чанков не меняет",
      "allowed_dependencies": [
        "Run.q кортежи (init/text/reasoning/tool_trace/result/done/pump_error)",
        "API стора сессий",
        "_run_once"
      ],
      "forbidden_dependencies": [
        "прямой доступ к sqlite3/транскрипту",
        "новые поля SSE или synthetic status-текст",
        "текст мышления в логах"
      ],
      "verification_ids": [
        "VER-003",
        "VER-006"
      ]
    },
    {
      "id": "BND-002",
      "component": "Run (lifecycle процесса agy) и Run._pump",
      "responsibility": "spawn/stdout/stderr, порядок join-before-done, бюджет drain, close и зачистка группы",
      "allowed_dependencies": [
        "источник мышления (start/bind/join)",
        "AdaptiveTimeoutController",
        "_kill_group"
      ],
      "forbidden_dependencies": [
        "разбор step_payload",
        "сон сверх бюджета drain",
        "запись в Handler/wfile"
      ],
      "verification_ids": [
        "VER-003",
        "VER-007"
      ]
    },
    {
      "id": "BND-003",
      "component": "Источник мышления хода (транскрипт + SQLite)",
      "responsibility": "только чтение transcript_full.jsonl и conversations/<cid>.db (строго mode=ro, без immutable), владение ограниченным seen (≤128), append-only выдача с проверкой префикса, per-turn poll-bucket, проверка флага на каждой итерации, compat canary, fail-open, диагностические строки без текста",
      "allowed_dependencies": [
        "stdlib sqlite3/pathlib/json/re",
        "pure-парсер",
        "emit-колбэк",
        "_log"
      ],
      "forbidden_dependencies": [
        "запись в ~/.gemini",
        "Handler/wfile",
        "сторонние пакеты",
        "_reasoning_suffix для мышления",
        "URI immutable/mode=rw",
        "хранение текста мышления в seen"
      ],
      "verification_ids": [
        "VER-003",
        "VER-005",
        "VER-009"
      ]
    },
    {
      "id": "BND-004",
      "component": "Pure wire-парсер step_payload",
      "responsibility": "bytes → str|'' по полю 20.3 без исключений",
      "allowed_dependencies": [
        "встроенные типы, memoryview"
      ],
      "forbidden_dependencies": [
        "I/O",
        "логирование",
        "рекурсия",
        "глобальное состояние"
      ],
      "verification_ids": [
        "VER-003",
        "VER-005"
      ]
    },
    {
      "id": "BND-005",
      "component": "Стор горячих сессий (_session_claim/_commit/_invalidate)",
      "responsibility": "стор только для агентных запросов (tools_count>0 и не фоновых); plain и фоновые запросы стор не читают и не пишут; владение cid _active_cid_owners (cid → turn_id) под тем же _session_store_lock — один cid никогда не разделяют два одновременных хода",
      "allowed_dependencies": [
        "_session_store_lock",
        "_active_cid_owners (cid → turn_id)",
        "_in_flight_cids (as-is)"
      ],
      "forbidden_dependencies": [
        "доступ plain/фоновых запросов к стору",
        "переиспользование cid между диалогами без tools",
        "разделение одного cid двумя одновременными ходами",
        "вложенный захват _sqlite_guard_lock под _session_store_lock (и наоборот)",
        "SQLite-опрос resumed-хода без двойного pre-spawn водяного знака (anchored=False)"
      ],
      "verification_ids": [
        "VER-003",
        "VER-007"
      ]
    },
    {
      "id": "BND-006",
      "component": "Политика повтора в _run_once",
      "responsibility": "учёт выдачи (text/tool_calls/streamed reasoning, включая reasoning после result ERROR), retry budget в целых десятых, jitter, O-EXIT done на всех выходах",
      "allowed_dependencies": [
        "процессный retry bucket",
        "инъецируемый RNG",
        "_log"
      ],
      "forbidden_dependencies": [
        "повтор после выдачи",
        "бесконечные/небюджетные повторы"
      ],
      "verification_ids": [
        "VER-003",
        "VER-007"
      ]
    },
    {
      "id": "BND-007",
      "component": "Процессные guard'ы SQLite-источника (_sqlite_guard_lock)",
      "responsibility": "один threading.Lock на breaker (CLOSED/OPEN/HALF_OPEN, атомарная проба), retry budget, compat-состояние и кэш dynamic_config; тестовый сброс глобалов",
      "allowed_dependencies": [
        "threading.Lock",
        "time.monotonic (инъецируемые часы в тестах)",
        "os.stat/json для dynamic_config.json"
      ],
      "forbidden_dependencies": [
        "I/O SQLite под замком",
        "сон/ожидание под замком",
        "float-счётчики токенов"
      ],
      "verification_ids": [
        "VER-003",
        "VER-007"
      ]
    }
  ],
  "contract_deltas": [
    {
      "id": "CD-001",
      "type": "behavior",
      "producer": "agy-bridge SSE/JSON",
      "consumer": "DSH OpenAI reader",
      "change": "reasoning_content приходит раньше и большим числом чанков во время генерации шага (при включённом флаге); последний шаг больше не теряется гонкой drain. Разрешено текущей задачей REQ-001/REQ-006",
      "compatibility": "Форма чанка, порядок role→reasoning→content→stop→usage→[DONE], поля и текст мышления не меняются; при выключенном флаге — только исправление drain",
      "verification_ids": [
        "VER-003",
        "VER-010",
        "VER-011"
      ]
    },
    {
      "id": "CD-002",
      "type": "behavior",
      "producer": "Handler._run_once",
      "consumer": "DSH",
      "change": "Сбой после отданного в поток мышления даёт data:{error}+[DONE] вместо невидимого повтора/холодного fallback. Разрешено REQ-008",
      "compatibility": "Кадр ошибки после старта потока — существующий контракт (F-11); JSON-режим без изменений",
      "verification_ids": [
        "VER-003"
      ]
    },
    {
      "id": "CD-003",
      "type": "behavior",
      "producer": "стор горячих сессий",
      "consumer": "DSH диалоги",
      "change": "Горячие сессии только для агентных запросов (tools_count>0, не фоновых); plain и фоновые запросы стор не используют. Владение cid — _active_cid_owners (cid → turn_id) под _session_store_lock: второй одновременный запрос с cid, занятым другим turn_id (горячим или явным), получает свежий cid без --resume. /health получает аддитивные диагностические поля \"sqlite_reasoning_mode\": \"live\" | \"shadow\" | \"off\" | \"breaker_open\", \"sqlite_breaker_state\": \"closed\" | \"open\" | \"half_open\", \"sqlite_divergence_count\": int, \"sqlite_drain_deadline_count\": int. Разрешено REQ-009/REQ-010",
      "compatibility": "API и формат ключа неизменны; /health: hot_sessions и все существующие поля неизменны, 4 новых поля аддитивны (клиенты, игнорирующие неизвестные ключи, не затронуты); явный conversation_id клиента как раньше, кроме одновременного занятого cid (свежий холодный разговор вместо разделения файла); plain-чаты всегда холодные с полной историей; после рестарта стор пуст (as-is)",
      "verification_ids": [
        "VER-003",
        "VER-007",
        "VER-011"
      ]
    },
    {
      "id": "CD-004",
      "type": "behavior",
      "producer": "конфигурация моста",
      "consumer": "оператор / LaunchAgent",
      "change": "Новые необязательные env: AGY_SQLITE_REASONING_ENABLED (только аварийное выключение 0/false/False), AGY_BRIDGE_SQLITE_POLL (0.5 с, clamp 0.5..2.0), AGY_BRIDGE_CONVERSATIONS, AGY_BRIDGE_AGY_BIN (идентичность бинаря для canary), AGY_BRIDGE_DRAIN_MIN (0.15, clamp 0.05..0.25), AGY_BRIDGE_DRAIN_JOIN (0.15, clamp 0.05..0.20); AGY_BRIDGE_TRANSCRIPT_GRACE трактуется как окно drain DRAIN_WINDOW_S (0.35, clamp 0.20..0.50 = DRAIN_MAX_S); runtime-флаг SQLITE_REASONING_ENABLED в dynamic_config.json (stat-кэш TTL 1.0 с, перепроверка каждые 0.25 с, fail-closed). Разрешено REQ-011/REQ-007",
      "compatibility": "Аддитивно: без файла и env поведение источника мышления as-is; деплойный env (F-38) не меняется",
      "verification_ids": [
        "VER-003",
        "VER-009"
      ]
    },
    {
      "id": "CD-005",
      "type": "behavior",
      "producer": "Handler._run_once",
      "consumer": "DSH",
      "change": "Повторы ограничены процессным retry budget в целых десятых (30/+2/−10) и идут с Full Jitter паузой [0,2] с (AD-005)",
      "compatibility": "Одиночный сбой до выдачи по-прежнему повторяется один раз; под штормом часть запросов получает ошибку без повтора",
      "verification_ids": [
        "VER-003",
        "VER-007"
      ]
    }
  ],
  "views": [
    {
      "id": "VIEW-001",
      "type": "context",
      "question": "Кто взаимодействует с мостом и какие границы внешние?",
      "artifact_ref": "architecture/architecture-packet.json#views[0].diagram + scope + BND-001",
      "diagram": "graph LR; DSH-->|HTTP SSE Bearer loopback :9887|Bridge[agy-bridge]; Bridge-->|spawn stream-json|Agy[agy 1.4.9]; Agy-->|write|Transcript[(brain/<cid>/transcript_full.jsonl)]; Agy-->|write WAL|Db[(conversations/<cid>.db)]; Bridge-.->|read only|Transcript; Bridge-.->|read only mode=ro|Db; Op[оператор]-->|dynamic_config.json|Bridge"
    },
    {
      "id": "VIEW-002",
      "type": "component",
      "question": "Как распределены обязанности внутри server.py?",
      "artifact_ref": "architecture/architecture-packet.json#boundaries BND-001..BND-006 + views[1].diagram",
      "diagram": "graph TD; Handler-->RunOnce[_run_once: delivered, retry budget, O-EXIT]; RunOnce-->Run; Run-->Pump[_pump]; Run-->Src[источник мышления: _watch_transcript + _poll_sqlite_reasoning, seen ≤128, poll-bucket]; Src-->Parser[pure wire-парсер + UTF-8 trim]; Src-->Guards[_sqlite_guard_lock: breaker, compat, config cache, retry budget]; RunOnce-->Guards; Pump-->|join-before-done|Src; Src-->|emit reasoning|Q[(Run.q)]; Pump-->|text/result/done|Q; RunOnce-->|_execute читает до done|Q; Handler-->Store[стор сессий: только agentic]"
    },
    {
      "id": "VIEW-003",
      "type": "dynamic",
      "question": "Какой порядок событий гарантирует мышление до stop и ограничение 1.0 с?",
      "artifact_ref": "architecture/architecture-packet.json#AD-002.details + views[2].diagram",
      "diagram": "sequenceDiagram; agy->>Pump: result; Pump->>Q: result (ERROR не прерывает _execute); agy->>Transcript: PLANNER_RESPONSE (+90 мс); agy-->>Pump: EOF; Pump->>Pump: wait ≤0.05, sleep 0.05, _proc_done; Pump->>Src: join(≤ deadline drain + 0.15 с); Src->>Q: reasoning (drain 0.15..0.50 с, ранний выход только при полноте); Src-->>Pump: exit; Pump->>Q: done; Execute->>Q: result, reasoning, done (FIFO, до done); Execute->>Client: reasoning_content, stop|error"
    },
    {
      "id": "VIEW-004",
      "type": "dfd",
      "question": "Где проходят trust boundaries и куда идут чувствительные данные?",
      "artifact_ref": "architecture/architecture-packet.json#threat_model + views[3].diagram",
      "diagram": "graph LR; Client-->|prompt, Bearer|Bridge; Bridge-->|prompt stdin|Agy; Agy-->|thinking bytes|Db; Db-->|step_payload bytes, untrusted|Parser; Parser-->|thinking str|Client; Bridge-->|cid8, step, len, без текста|Log[(bridge.err)]"
    }
  ],
  "risks": [
    {
      "id": "RISK-001",
      "scenario": "Автоапдейт agy меняет номера полей/статусов: источник молчит или отдаёт не тот текст (F-25, F-28)",
      "probability": "medium",
      "impact": "medium",
      "mitigation": "Compat canary: смена (st_mtime_ns, st_size) бинаря agy → SHADOW без выдачи клиенту до совпадения с транскриптом; divergence и sqlite-live-loss → SHADOW + отказ breaker'а; транскрипт остаётся источником; L3 S1 после автоапдейта",
      "verification_ids": [
        "VER-003",
        "VER-007",
        "VER-011"
      ]
    },
    {
      "id": "RISK-002",
      "scenario": "mode=ro на 3.9.6 не открывает закрытую WAL-БД (F-52) — нет live-дельт",
      "probability": "medium",
      "impact": "medium",
      "mitigation": "Строго mode=ro (immutable запрещён); соединение на ход, последовательное переоткрытие не чаще SQLITE_POLL_S; fail-open на транскрипт; водяной знак resumed из транскрипта со статусом 8 при ошибке SQLite; L1/L2 на /usr/bin/python3",
      "verification_ids": [
        "VER-005",
        "VER-010"
      ]
    },
    {
      "id": "RISK-003",
      "scenario": "Квота аккаунта agy блокирует L3 (F-46)",
      "probability": "high",
      "impact": "medium",
      "mitigation": "Штатное переключение аккаунта или ожидание сброса; без L3 «готово» запрещено",
      "verification_ids": [
        "VER-011"
      ]
    },
    {
      "id": "RISK-004",
      "scenario": "Непрефиксный снимок дублирует или искажает мышление (F-04)",
      "probability": "low",
      "impact": "medium",
      "mitigation": "Проверка префикса sha256: divergence не переотдаёт выданное (0 дублей), отдаёт только невыданный хвост, логируется, считается отказом хода для breaker (K=3) и переводит compat в SHADOW; живая проверка 0 divergence в L2/L3",
      "verification_ids": [
        "VER-003",
        "VER-007",
        "VER-010",
        "VER-011"
      ]
    },
    {
      "id": "RISK-005",
      "scenario": "6-8 параллельных ходов умножают опросы файлов (F-55)",
      "probability": "low",
      "impact": "low",
      "mitigation": "огибающая N(Δt) ≤ 3 + 2·Δt SELECT на ход (SQLITE_POLL_S ∈ [0.5, 2.0] + per-turn bucket, включая drain), LIMIT 16 и BLOB ≤256 KiB на опрос, повторный парсинг только при смене (blob_len, sha256), бюджет CPU ≤1% на ход в L2 на минимальном периоде",
      "verification_ids": [
        "VER-010"
      ]
    },
    {
      "id": "RISK-006",
      "scenario": "Читатель мешает писателю agy (SQLITE_BUSY, рост WAL из-за удержания snapshot)",
      "probability": "low",
      "impact": "medium",
      "mitigation": "query_only, autocommit-SELECT с немедленным fetchall, нет явных транзакций, timeout 0.05 с; L2 проверяет отсутствие SQLITE_BUSY у writer",
      "verification_ids": [
        "VER-003",
        "VER-010"
      ]
    },
    {
      "id": "RISK-007",
      "scenario": "Drain удлиняет каждый ход",
      "probability": "low",
      "impact": "low",
      "mitigation": "Без авторитетного маркера конца хода — полное окно DRAIN_WINDOW_S 0.35 с (диапазон 0.20..0.50); досрочно после 0.15 с только по END_TURN/TURN_COMPLETE или финальному PLANNER_RESPONSE при 0 строк status=8 на двух тиках; EOF→stop ≤0.65 с при дефолтах, ≤0.85 с ≤1.0 с на любых разрешённых настройках",
      "verification_ids": [
        "VER-003",
        "VER-010"
      ]
    },
    {
      "id": "RISK-008",
      "scenario": "Кадр error после отданного мышления затирает блок Think в DSH (F-47, OPEN-06)",
      "probability": "medium",
      "impact": "medium",
      "mitigation": "Контракт ошибки неизменен и честен; альтернатива stop+частичный ответ — решение владельца Q-002; проверка в L3",
      "verification_ids": [
        "VER-011"
      ]
    },
    {
      "id": "RISK-009",
      "scenario": "Plain-чаты без tools теряют горячие продолжения (стор только для агентных)",
      "probability": "low",
      "impact": "low",
      "mitigation": "Корректность не страдает: холодный ход с полной историей; агентные диалоги сохраняют горячие сессии; хеш первой реплики — будущая оптимизация (AD-004 альтернатива C)",
      "verification_ids": [
        "VER-003"
      ]
    },
    {
      "id": "RISK-010",
      "scenario": "Retry budget отказывает в законном повторе после шторма",
      "probability": "low",
      "impact": "low",
      "mitigation": "Ёмкость 30 десятых (3 токена), +2 десятых на первичный запрос, целочисленная арифметика без дрейфа; лог retry-budget-exhausted",
      "verification_ids": [
        "VER-003",
        "VER-007"
      ]
    },
    {
      "id": "RISK-011",
      "scenario": "Устранение 12 baseline-ошибок basedpyright и форматирование server.py (221 строка) расширяет дифф MR и может нечаянно изменить поведение",
      "probability": "medium",
      "impact": "medium",
      "mitigation": "Только target-файлы (VER-008); форматирование отдельным механическим коммитом; типизация без изменения поведения, inline-подавления запрещены; невозможность исправить без изменения поведения → BLOCKED владельцу; 22 legacy теста и VER-004 (0 ошибок, 0 новых предупреждений) ловят регресс",
      "verification_ids": [
        "VER-002",
        "VER-003",
        "VER-004",
        "VER-008"
      ]
    },
    {
      "id": "RISK-012",
      "scenario": "Синтаксис 3.10+ в новом коде роняет мост на /usr/bin/python3 3.9.6",
      "probability": "low",
      "impact": "high",
      "mitigation": "Обязательный VER-005 на боевом интерпретаторе; from __future__ import annotations сохраняется",
      "verification_ids": [
        "VER-005"
      ]
    },
    {
      "id": "RISK-013",
      "scenario": "Текст мышления или секрет попадает в bridge.err",
      "probability": "low",
      "impact": "medium",
      "mitigation": "Строки источника только cid8/step/len/класс ошибки; TC-92 проверяет отсутствие текста фикстуры",
      "verification_ids": [
        "VER-003",
        "VER-007"
      ]
    },
    {
      "id": "RISK-014",
      "scenario": "Бинарный порог L3 по первой дельте зависит от неконтролируемого расписания записи agy (интервалы 1.5–5.1 с, F-30) — приёмка флакует при корректной реализации",
      "probability": "medium",
      "impact": "medium",
      "mitigation": "Детерминированный порог — L2 «коммит → сокет ≤ SQLITE_POLL_S+0.5 с»; L3 меряет от первой строки status=8 с непустым 20.3 (внешний read-only наблюдатель), интервалы ≤6 с — наблюдение SHOULD",
      "verification_ids": [
        "VER-010",
        "VER-011"
      ]
    },
    {
      "id": "RISK-015",
      "scenario": "Процессные глобалы (breaker, retry budget, compat, кэш конфига) при ThreadingHTTPServer и 8 одновременных ходах дают гонки (две пробы HALF_OPEN) и утечку состояния между тестами",
      "probability": "medium",
      "impact": "medium",
      "mitigation": "Один _sqlite_guard_lock, атомарный захват пробы, без I/O под замком; хелпер _reset_sqlite_guards_for_tests(); конкурентный оракул AO-01 (10 ходов → 1 проба)",
      "verification_ids": [
        "VER-003",
        "VER-007"
      ]
    },
    {
      "id": "RISK-016",
      "scenario": "Непиненные/непрогретые uvx-инструменты: clean-room без сети не стартует, дрейф версий меняет диагностики и ломает сравнение VER-004",
      "probability": "medium",
      "impact": "medium",
      "mitigation": "Версии запинены (ruff 0.17.3, basedpyright 1.40.2, pytest 9.0.3); прогрев кэша uvx до clean-room — предусловие VER-003/VER-010; VER-004 проверяет версию в выводе",
      "verification_ids": [
        "VER-001",
        "VER-003",
        "VER-004",
        "VER-010"
      ]
    },
    {
      "id": "RISK-017",
      "scenario": "SHADOW после рестарта моста или обновления agy задерживает live-мышление до первого шага с canary",
      "probability": "high",
      "impact": "low",
      "mitigation": "Один шаг с мышлением переводит в LIVE; в SHADOW мышление идёт из транскрипта as-is (не хуже текущего); S1 L3 меряется со второго хода",
      "verification_ids": [
        "VER-007",
        "VER-011"
      ]
    },
    {
      "id": "RISK-018",
      "scenario": "3 унаследованных красных теста полного набора вне agy-bridge (F-56) блокируют VER-012 при гейте 0 failed",
      "probability": "high",
      "impact": "medium",
      "mitigation": "Гейт не ослабляется: VER-012 (agy-набор, /usr/bin/python3) 0 failures; полный набор — pre-MR checkpoint Q-005, ровно эти 3 красных = BLOCKED: OWNER_DECISION_REQUIRED до MR; новые красные = FAIL",
      "verification_ids": [
        "VER-012"
      ]
    },
    {
      "id": "RISK-019",
      "scenario": "Нарушение префиксности 20.3 (ASM-001) замораживает выдачу шага: клиент видит усечённое мышление шага (без искажения), остаток хода — только транскрипт",
      "probability": "low",
      "impact": "low",
      "mitigation": "Лог sqlite_*_divergence и /health sqlite_divergence_count; отказ breaker'а и SHADOW для следующих ходов; L3 требует 0 divergence на ≥5 многошаговых ходах, иначе флаг false и эскалация",
      "verification_ids": [
        "VER-007",
        "VER-010",
        "VER-011"
      ]
    },
    {
      "id": "RISK-020",
      "scenario": "Мышление одного хода больше MAX_REASONING_BYTES_PER_TURN = 2 MiB усекается (reasoning-cap)",
      "probability": "low",
      "impact": "low",
      "mitigation": "Строка reasoning-cap с объёмом; текст ответа и tool-события не затрагиваются; предел — константа модуля, пересматривается по факту L3",
      "verification_ids": [
        "VER-003",
        "VER-007"
      ]
    }
  ],
  "threat_model": {
    "required": true,
    "assets": [
      "текст мышления и промпты пользователя",
      "целостность файлов разговоров agy (conversations/*.db, brain/*)",
      "AGY_BRIDGE_KEY (Bearer)",
      "соответствие горячая сессия → conversation_id (контекст диалога)"
    ],
    "trust_boundaries": [
      "DSH ↔ мост: HTTP loopback с Bearer (as-is)",
      "мост ↔ процесс agy: stdout NDJSON (cid из init — недоверенный вход для построения пути)",
      "мост ↔ файлы состояния agy: байты step_payload и транскрипт — недоверенный вход парсера; доступ только на чтение",
      "мост → bridge.err: журнал без текста и секретов"
    ],
    "threats": [
      {
        "id": "THREAT-001",
        "scenario": "Подделанный/битый step_payload (огромная длина varint, неподдерживаемые wire types, бесконечный цикл) роняет поток или съедает CPU/память",
        "mitigation": "Проверка длины ≤ остатка, varint ≤10 байт, BLOB > 256 KiB не материализуется, LIMIT 16, stop_event каждые 64 тега (SQL CASE → NULL), без рекурсии, линейный проход, все исключения поглощаются → ''; seen без текста и ≤128 записей",
        "verification_ids": [
          "VER-003",
          "VER-005",
          "VER-007"
        ]
      },
      {
        "id": "THREAT-002",
        "scenario": "cid с ../ или абсолютным путём ведёт к открытию файла вне conversations",
        "mitigation": "Константный regex ^[0-9A-Fa-f-]{8,64}$ и проверка resolved parent == CONV_DIR; иначе источник выключен на ход",
        "verification_ids": [
          "VER-003",
          "VER-007"
        ]
      },
      {
        "id": "THREAT-003",
        "scenario": "Мост пишет в БД agy или повреждает её (rw-режим, immutable при живом писателе)",
        "mitigation": "Только file:…?mode=ro + PRAGMA query_only=ON + busy_timeout 50 мс; immutable и mode=rw запрещены везде (VER-009 ищет подстроку); внешний писатель не нарушает консистентность чтения",
        "verification_ids": [
          "VER-007",
          "VER-009"
        ]
      },
      {
        "id": "THREAT-004",
        "scenario": "Утечка текста мышления/секретов в логи",
        "mitigation": "Диагностика только cid8/step/len/класс ошибки; _mask_secrets для ошибок as-is; TC-92",
        "verification_ids": [
          "VER-003",
          "VER-007"
        ]
      },
      {
        "id": "THREAT-005",
        "scenario": "Фоновый запрос получает контекст агентного диалога (утечка между чатами) или наоборот",
        "mitigation": "AD-004: стор только для агентных запросов; plain и фоновые не читают и не пишут стор",
        "verification_ids": [
          "VER-003",
          "VER-007",
          "VER-011"
        ]
      }
    ]
  },
  "evolution": {
    "compatibility": "HTTP/SSE/JSON контракт, порт 9887, флаги agy и текст мышления неизменны (REQ-010); новые env и runtime-флаг аддитивны; без флага источник мышления as-is, исправления RC-2..RC-4 действуют всегда",
    "migration": "NOT_APPLICABLE: у моста нет persisted state — _session_store в памяти (смена формата ключа без миграции, после рестарта стор пуст как и сейчас); файлы agy только читаются; схема agy не меняется мостом",
    "rollout": "L1 (VER-001..VER-009) → L2 clean-room (VER-010) → VER-012 (agy-набор 0 failures) → pre-MR checkpoint Q-005 (полный набор, решение владельца по 3 красным F-56) → downstream Совет (ACCEPT) → MR → merge человеком → L3 (VER-011). Входная зависимость L3: владелец переключает аккаунт agy с квотой или ждёт сброса квоты (≈2026-10-31 07:09 MSK, Q-003). L3: бэкап, копия server.py в ~/.dsh/bridges/agy-bridge/, sha256, kickstart; фаза A с выключенным флагом (RC-2..RC-4), фаза B — атомарная запись dynamic_config.json с SQLITE_REASONING_ENABLED=true без рестарта",
    "rollback": "Мгновенно: SQLITE_REASONING_ENABLED=false или удаление dynamic_config.json (активный ход переходит на транскрипт ≤1.30 с) либо env AGY_SQLITE_REASONING_ENABLED=0 + kickstart; полностью: восстановить бэкап server.py из ~/work/backups/agy-bridge-<ts>/, launchctl kickstart -k gui/$(id -u)/com.user.dsh-agy-bridge, /health и один живой ход",
    "feature_flag": "SQLITE_REASONING_ENABLED (runtime dynamic_config.json рядом с server.py, stat-кэш TTL 1.0 с, перепроверка каждые 0.25 с, fail-closed, кодовый default=false, проверка на каждой итерации опроса) AND env AGY_SQLITE_REASONING_ENABLED (только аварийное выключение); прецедент EVD-064/065",
    "mixed_version": "Один процесс, без rolling update: старая и новая версии не работают одновременно; при kickstart горячие сессии теряются (as-is)",
    "agy_version_pin": "Схема steps/step_type=15/status 8,3/20.3 подтверждена на agy 1.4.9 (F-25, F-31); compat canary по (st_mtime_ns, st_size) бинаря держит новую версию в SHADOW до совпадения с транскриптом; после автоапдейта agy — повтор L3 S1"
  },
  "approval": {
    "status": "APPROVED",
    "decision_ids": [],
    "approved_by": null,
    "evidence_ref": ".ai-team/runs/analyst-teamlead-agy-reasoning-20261029/route-manifest.json (routing_approval=auto, approved_by_user=true)",
    "rationale": "Все AD-001..AD-006 two-way, approval_required=false: человеческих one-way решений нет. status=APPROVED означает валидированный пакет-кандидат для downstream Архитектурного Совета (route-manifest downstream_panel=true), а не вердикт Совета и не ARCH_GATE_PASS. Вопросы владельцу Q-001..Q-005 — класса МОЖНО ПРОДОЛЖИТЬ"
  },
  "independent_review": {
    "required": false,
    "status": "NOT_REQUIRED",
    "reviewer": null,
    "evidence_ref": null,
    "rationale": "S2: схема не требует независимого review внутри пакета; downstream внешний Совет обязателен по route-manifest (downstream_panel=true). Автор не выносит PASS Совета и ARCH_GATE_PASS"
  },
  "open_questions": [
    {
      "id": "Q-001",
      "class": "continuable",
      "blocking": false,
      "question": "OPEN-08: принимаете ли цели — L2: коммит снимка → сокет ≤ SQLITE_POLL_S+0.5 с; L3: первая дельта ≤5.0 с от первой строки status=8 с непустым 20.3; интервал ≤6 с как наблюдение; добавка drain ≤1.0 с?",
      "disposition": "Допущение ASM-008 принято в VER-010/VER-011; ответ меняет только пороги L2/L3"
    },
    {
      "id": "Q-002",
      "class": "continuable",
      "blocking": false,
      "question": "OPEN-06: после отданного мышления при сбое показывать кадр ошибки (выбрано, as-is контракт) или stop с частичным ответом?",
      "disposition": "AD-003 выбирает кадр ошибки без невидимого повтора; смена — отдельный two-way delta"
    },
    {
      "id": "Q-003",
      "class": "continuable",
      "blocking": false,
      "question": "OPEN-07: L3 вести на другом аккаунте agy или ждать сброса квоты (~54 ч от 2026-10-29 01:09 MSK)?",
      "disposition": "Без L3 сдача не засчитывается (VER-011)"
    },
    {
      "id": "Q-004",
      "class": "continuable",
      "blocking": false,
      "question": "Флаг SQLite-источника: оставить кодовый default=false + включение через dynamic_config.json на L3 (выбрано по канону) или включить по умолчанию, как в примере брифа (default=1)?",
      "disposition": "AD-006; смена дефолта — одна константа и отдельный two-way delta"
    },
    {
      "id": "Q-005",
      "class": "continuable",
      "blocking": false,
      "question": "Pre-MR rollout checkpoint: 3 красных теста полного набора вне agy-bridge и вне границы правки (F-56/EVD-056: test_b_guard, test_muse_bridge_killpg, test_rpc_rework) — принять исключение владельцем, починить отдельной задачей до MR или включить в этот MR? Прочие baseline-отклонения (ожидание слота до 1800 с, ожидающие слота до 24 > 2M, Run.q без maxsize) — отдельной задачей?",
      "disposition": "ASM-011: гейты не ослаблены; 12 ошибок basedpyright (EVD-076) и форматирование server.py устраняются в этом MR (VER-002, VER-004); VER-012 — agy-набор на /usr/bin/python3 с 0 failures; Full Suite Gate выполняется до MR как checkpoint: ровно эти 3 красных = BLOCKED: OWNER_DECISION_REQUIRED (решение владельца до MR), любой другой красный = FAIL"
    }
  ],
  "protected_paths": [
    ".ai-team/",
    "analysis/agy-realtime-reasoning/",
    "bridges/agy-bridge/fleet.json",
    "bridges/agy-bridge/start.sh",
    "ruff.toml",
    "core/"
  ],
  "materialization": [],
  "deferred": [],
  "high_load_envelope": {
    "schema": "HL-ENV/v1",
    "ssot": "~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/architecture.md §3.0/§7.2",
    "field_count": 46,
    "units": "СИ: время s, CPU cores, память MiB, rates req/s|conn/s|stat/s, соединения, дескрипторы, токены; векторы [d] по d ∈ {conversations_db (на файл cid), transcript_file (на ход), agy_process_slots}, [c] по классам staleness, (s) по {node_ephemeral (loopback)}",
    "contour": "Один локальный демон LaunchAgent com.user.dsh-agy-bridge на рабочей станции (не k8s): «под» = процесс моста, W=1 (ThreadingHTTPServer, потоки)",
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
      "Mem_rss_worker_max": 112,
      "Mem_shared_max": 32,
      "RPS_peak": 6,
      "A_max": 2,
      "SLA_p99_s": 1800,
      "N_entities_max": 1000,
      "Limit_dep_share[d]": {
        "conversations_db": 4,
        "transcript_file": 4,
        "agy_process_slots": 8
      },
      "Limit_dep_rps[d]": {
        "conversations_db": 20,
        "transcript_file": 200
      },
      "W_fetchers[d]": {
        "conversations_db": 1,
        "transcript_file": 1
      },
      "J_init_s[d]": {
        "conversations_db": 0.0,
        "transcript_file": 0.0
      },
      "J_pod_s[d]": {
        "conversations_db": 0.0,
        "transcript_file": 0.0
      },
      "T_poll_s[d]": {
        "conversations_db": 0.5,
        "transcript_file": 0.05
      },
      "K_calls[d]": {
        "conversations_db": 1,
        "transcript_file": 1
      },
      "T_base_s[d]": {
        "conversations_db": 0.5,
        "turn_retry": 2.0
      },
      "T_cap_s[d]": {
        "conversations_db": 0.5,
        "turn_retry": 2.0
      },
      "Max_stale_age_s[c]": {
        "reasoning_snapshot": 5.6,
        "hot_session": 2700,
        "dynamic_config": 1.0,
        "auth_secret": 0
      },
      "Min_healthy_ratio": null,
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
        "Handler._serve_sse",
        "Handler._serve_json",
        "Handler._run_once",
        "Handler._execute (дочитывание до done)",
        "Run.__init__ (водяной знак, compat stat)",
        "Run._pump",
        "источник мышления: _watch_transcript/_read/_emit_record + _poll_sqlite_reasoning + _drain_post_eof",
        "pure wire-парсер step_payload + UTF-8 trim",
        "append-only выдача мышления с проверкой префикса",
        "_reasoning_suffix (text_delta)",
        "_is_sqlite_reasoning_enabled (stat-кэш TTL 1.0 с, перепроверка каждые 0.25 с)",
        "_sqlite_guard_lock: breaker, retry budget, compat",
        "_emit_reasoning / _close_and_put_done под run._emit_lock (drain_closed, MAX_REASONING_BYTES_PER_TURN)"
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
      "P_steady": "F-38: один процесс LaunchAgent (EVD-038)",
      "P_hpa_max": "F-38: автомасштабирования нет",
      "maxSurge_pct": "F-38: KeepAlive, без rolling update",
      "maxSurge_abs": "вычислено ceil(1×0.0)=0",
      "maxUnavailable_pct": "F-38",
      "maxUnavailable_abs": "вычислено floor(1×0.0)=0",
      "P_terminating_overlap": "F-38: рестарт launchctl kickstart, _kill_all при SIGTERM",
      "P_live": "вычислено 1+0+0=1",
      "P_avail_min": "вычислено max(1,1-0)=1",
      "W": "F-51: один процесс /usr/bin/python3",
      "N_proc": "вычислено 1×1",
      "N_proc_steady": "вычислено 1×1",
      "N_proc_avail_min": "вычислено 1×1",
      "CPU_limit_per_pod": "оценка: бюджет демона на рабочей станции (лимита ОС нет)",
      "κ_skew": "один процесс",
      "u_bg_worker": "дизайн: 8 ходов × (опрос транскрипта 0.005 + опрос БД 0.01) ядра; измерение — TC-93 в L2",
      "U_pod_sidecars": "F-05: agy — внешние процессы своей группы, не CPU моста",
      "Mem_limit_per_pod": "оценка: бюджет демона",
      "Mem_rss_worker_max": "F-51: 20 MiB idle + 8 ходов × (буфер транскрипта ≤4 MiB + кэш SQLite 1 MiB + одна строка BLOB ≤0.25 MiB (SQL CASE 262144, итерация курсора по одной) + декодированный str ≤1 MiB + seen ≤128×0.4 KiB ≈0.05 MiB + Run.q + out['reasoning'] ≤4 MiB (MAX_REASONING_BYTES_PER_TURN 2 MiB × 2)) = 20 + 8×10.30 = 102.4 ≤ 112",
      "Mem_shared_max": "оценка: -shm WAL-index на соединение (32 KiB×8) + запас",
      "RPS_peak": "F-55: 6 exec в одну секунду (всплеск)",
      "A_max": "F-09: 2 попытки",
      "SLA_p99_s": "F-15: TIMEOUT_S=1800 — потолок хода",
      "N_entities_max": "F-45: сотни шагов на разговор; на ход seen ≤ MAX_STEPS_TRACKED=128, выборка LIMIT 16 на опрос с нижней границей poll_watermark",
      "Limit_dep_share[d]": "conversations_db/transcript_file — бюджет моста на файл (дизайн-учёт, не квота вендора: писатель agy + читатель моста + диагностика + запас); agy_process_slots — MAX_CONCURRENT деплоя 8 (F-38, bulkhead, не пул соединений)",
      "Limit_dep_rps[d]": "дизайн-учёт локального файла (не внешняя квота): ограничивает долю времени, когда читатель держит snapshot; реальный предел — CPU (H-CPU-I5)",
      "W_fetchers[d]": "AD-001: один поток источника на активный ход и на файл",
      "J_init_s[d]": "AD-001: опрос стартует по init своего хода, общего старта нет",
      "J_pod_s[d]": "один процесс",
      "T_poll_s[d]": "AD-001: SQLITE_POLL_S=0.5, допустимый диапазон [0.5, 2.0] (clamp); per-turn bucket — огибающая N(Δt) ≤ 3 + 2·Δt SELECT на ход включая drain; транскрипт 0.05 as-is (F-01)",
      "K_calls[d]": "AD-001: один SELECT на опрос; транскрипт — один stat (+read при росте)",
      "T_base_s[d]": "SQLite — следующий опрос; повтор хода — AD-005 Full Jitter с базой 2.0",
      "T_cap_s[d]": "AD-005: U(0, min(2.0, 2.0·2^(a-1))), A_max=2",
      "Max_stale_age_s[c]": "reasoning_snapshot = 5.1 (F-30) + 0.5 опрос; hot_session = SESSION_IDLE_TTL_S 2700 (F-13); dynamic_config — stat-кэш TTL 1.0 с (AD-006; kill-switch активного хода ≤1.30 с); auth_secret статичен в env до рестарта (0)",
      "Min_healthy_ratio": "N/A: нет пула нод; минимальный источник мышления — транскрипт (N_floor=1)",
      "B_retry_max": "AD-005: процессный bucket 30 десятых = 3 токена (целочисленный)",
      "min_reserve_retry_rps": "AD-005: 0.0",
      "FD_worker": "F-51: 36 idle + 8 ходов × 8 (3 пайпа, транскрипт, db/-wal/-shm при ≤1 одновременном соединении, клиентский сокет) + до 32 ingress сокетов = 132",
      "ulimit_n": "F-54: launchctl limit maxfiles soft 65536",
      "λ_new_conn_per_pod(s)": "F-55: до 6 подключений DSH в секунду по loopback",
      "C_active_in_scope(s)": "EVD-062: max_http_connections=32",
      "N_pods_in_scope(s)": "один процесс на хосте",
      "Port_range_size(s)": "F-54: 49152-65535",
      "T_hold_s(s)": "F-54: TIME_WAIT 2×MSL 15 с",
      "SNAT_ips_count(s)": "loopback, без SNAT",
      "HOTPATH_MODULES": "F-03, F-06, F-07 + AD-001..AD-006"
    },
    "memory_closure_check": {
      "status": "PASS",
      "unit": "MiB",
      "lhs_mib": 144,
      "rhs_mib": 409.6,
      "substitution": "W·Mem_rss_worker_max + Mem_shared_max = 1·112 + 32 = 144 ≤ 0.80·512 = 409.6 MiB; запас 265.6 MiB; Run.q + out['reasoning'] ≤4 MiB на ход (MAX_REASONING_BYTES_PER_TURN = 2 MiB), ≤32 MiB на 8 ходов — внутри Mem_rss_worker_max",
      "evidence_level": "дизайн-оценка с жёсткими ограничениями размера (BLOB ≤256 KiB в SQL, LIMIT 16, мышление ≤2 MiB на ход, seen ≤128 без текста); измерено только 20 MiB idle (F-51); пик RSS при 8 ходах — L2 VER-010 (ru_maxrss ≤ 112 MiB)"
    },
    "operational_profile": {
      "active_turns_max": 8,
      "code_default_max_concurrent": 4,
      "deployed_max_concurrent": 8,
      "sqlite_connections_max": "≤1 одновременного соединения на активный ход (≤8 на процесс, разные файлы cid); последовательные переоткрытия закрывают прежний handle в finally; active_connections_after_done == 0",
      "sqlite_queries_per_s_max": "16 (8 ходов × 2.0/с, per-turn bucket) при любом допустимом SQLITE_POLL_S ∈ [0.5, 2.0]; огибающая на ход N(Δt) ≤ 3 + 2·Δt; ≤16 строк и BLOB ≤256 KiB на SELECT",
      "drain_budget_s": "окно drain 0.35 (диапазон 0.20..0.50) + join 0.15 (max 0.20); EOF→stop ≤0.65 при дефолтах, ≤0.85 на максимумах",
      "threads_per_turn": "stdin, stderr, pump, источник мышления — без нового потока",
      "sqlite_poll_s_range": "[0.5, 2.0], default 0.5"
    }
  },
  "resilience_gates": {
    "ssot": "~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/architecture.md §3.0-§3.4, §7.2-§7.3",
    "status_semantics": "PASS — проектная замкнутость инварианта для изменяемых путей; runtime-оракул обязателен в L1/L2 (VER-003/VER-005/VER-007/VER-010) и ещё не выполнен. N/A — только отсутствие функции на новом пути с двойным доказательством (git diff + граф вызовов), не waiver. BASELINE_DEBT — унаследованное отклонение вне изменяемого пути, не вносимое и не ухудшаемое этим MR (VER-008), вынесено владельцу (Q-005); гейты качества (VER-001..VER-005, VER-012) baseline-допусками не ослабляются; новое нарушение = FAIL = REJECT",
    "HL_ENV_v1": {
      "HL-ENV-01": {
        "status": "PASS",
        "substitution": "46/46 канонических ключей с field_units и field_sources; память 1·112+32=144 ≤ 409.6 MiB; N/A-гейты несут na_proof",
        "oracle": "set(required_hl_env_fields)==set(field_units)==set(field_sources)==46 канонических ключей SSoT §3.0; пересчёт неравенства памяти; каждый N/A содержит na_proof",
        "verification_ids": [
          "VER-007",
          "VER-010"
        ],
        "evidence_level": "design; семантические проверки пакета выполнены при сборке"
      }
    },
    "C_MULT": {
      "C-MULT-I1": {
        "status": "PASS",
        "substitution": "conversations_db (на файл): C = N_proc 1 × (G_reload 1 × pool 0 + dedicated 1) = 1 ≤ 0.60×4 = 2.4; transcript_file: 1 ≤ 2.4. ≤1 одновременного SQLite-соединения на активный ход (≤8 одновременно на процесс моста, разные файлы cid); последовательные переподключения внутри хода (после ошибки открытия, водяной знак до spawn) закрывают прежний handle в finally, поэтому active_connections_after_done == 0",
        "oracle": "AO-04: максимум одновременно открытых соединений хода == 1 при любом числе последовательных connect; каждый connect парный close; после 20 ходов открытых соединений 0",
        "verification_ids": [
          "VER-003",
          "VER-007"
        ]
      },
      "C-MULT-I2": {
        "status": "PASS",
        "substitution": "Новый путь не вводит пулов: одно соединение на ход, ожидания нет (timeout 0.05 с → «изменений нет»). Унаследованный bulkhead _slots — BASELINE_DEBT BD-002",
        "oracle": "AO-04: при блокировке БД опрос возвращается не позже timeout 0.05 с/busy_timeout 50 мс, параллельный второй connect не создаётся",
        "verification_ids": [
          "VER-003",
          "VER-007"
        ],
        "baseline_debt": "BD-002"
      },
      "C-MULT-I3": {
        "status": "PASS",
        "substitution": "fork() нет (Popen exec agy); соединение создаётся в потоке источника своего хода (check_same_thread=True), не в обработчике и не глобально; закрывается в finally",
        "oracle": "AO-04: id соединения один на ход, после выхода потока closed; глобальных соединений нет (VER-009 ast)",
        "verification_ids": [
          "VER-003",
          "VER-009"
        ]
      },
      "C-MULT-I4": {
        "status": "PASS",
        "substitution": "Отмена = stop_event (Run.close) или выключение флага: активный SELECT прерывается conn.interrupt() из другого потока, поток выходит ≤ DRAIN_POLL_STEP_S + busy_timeout 0.05 с (stop_event проверяется перед каждой строкой и каждые 64 wire-тега) и закрывает соединение в finally; join в _pump ограничен (окно drain + interrupt + JOIN_TIMEOUT_S)",
        "oracle": "AO-04: 50 циклов stop во время опроса → открытых соединений 0, живых потоков источника 0",
        "verification_ids": [
          "VER-003",
          "VER-007"
        ]
      },
      "C-MULT-I5": {
        "status": "PASS",
        "substitution": "FD 132 ≤ 0.70·65536 = 45875.2; порты 6·1·30 + 32 = 212 ≤ 0.50·(1·16384) = 8192",
        "oracle": "Расчётный тест по HL-ENV (AO-04 считает FD хода: +3 на SQLite и закрытие всех)",
        "verification_ids": [
          "VER-003",
          "VER-007"
        ]
      }
    },
    "S_HERD": {
      "S-HERD-I1": {
        "status": "PASS",
        "substitution": "Холодный старт моста не запускает поллеров (W_fetchers при t=0 равно 0); поллер стартует по init своего хода и опрашивает свой файл. Допустимый SQLITE_POLL_S ∈ [0.5, 2.0] (clamp): R_poll = K_calls·1/T_poll ≤ 1/0.5 = 2.0 ≤ 0.20·20 = 4.0 req/s на файл на всём диапазоне; per-turn bucket (30 десятых, +20/с, −10 за SELECT) ограничивает и drain — огибающая прихода N(Δt) ≤ 3 + 2·Δt SELECT на ход на любом окне Δt: всплеск B = 3 ≤ 0.50·20 = 10, устойчиво 2.0 ≤ 4.0; 8 ходов × 2.0 = 16 req/s по разным файлам; транскрипт 1/0.05 = 20 ≤ 0.20·200 = 40. Limit_dep_rps — дизайн-учёт локального файла, не внешняя квота",
        "oracle": "Расчётный тест по HL-ENV на границах диапазона 0.5 и 2.0; AO-05: один SELECT на опрос и N(Δt) ≤ 3 + 2·Δt на ход на FakeClock для любого окна Δt, включая drain с шагом 0.05 с",
        "verification_ids": [
          "VER-003",
          "VER-007"
        ]
      },
      "S-HERD-I2": {
        "status": "PASS",
        "substitution": "Пауза повтора хода — Full Jitter U(0, min(2.0, 2.0·2^(a-1))) через инъецируемый RNG (AD-005). Пересев CSPRNG после fork и джиттер периодического поллера неприменимы: fork() нет, каждый поллер опрашивает свой локальный файл без общей зависимости",
        "oracle": "AO-02: инъецированный RNG u∈{0.0,0.5,1.0} → паузы ровно {0.0,1.0,2.0} с",
        "verification_ids": [
          "VER-003",
          "VER-007"
        ]
      },
      "S-HERD-I3": {
        "status": "PASS",
        "substitution": "Аналог conditional fetch: неизменная пара (blob_len, sha256(BLOB)) → парсер не вызывается; изменение того же размера распознаётся по sha256 и парсится один раз",
        "oracle": "AO-05: 10 опросов неизменной строки → parser.call_count == 1; строка того же размера с другим содержимым → ещё ровно 1 вызов",
        "verification_ids": [
          "VER-003",
          "VER-007"
        ]
      },
      "S-HERD-I4": {
        "status": "N/A",
        "reason": "TTL-кэшей с сетевым дозапросом нет; на файл ровно один поллер-владелец (поток своего хода) — singleflight не нужен. Классификация ошибок соблюдена: ошибки открытия/блокировки не кэшируются (повтор на следующем опросе), детерминированные схемные ошибки выключают источник на ход и учитываются breaker'ом",
        "na_proof": {
          "current_git_diff_command": "git diff --name-only e00da0621fc95f7c63cd1565f4a5d1fd490c8d66 -- bridges/agy-bridge tests/test_agy_bridge_resilience.py",
          "current_git_diff_output": "",
          "current_product_fingerprint": "aed3274571859b39f08788443955470300be30a9dfd8ea5d0e994001433a0bbb",
          "git_diff_files": [
            "bridges/agy-bridge/server.py",
            "tests/test_agy_bridge_resilience.py"
          ],
          "transitive_call_graph": "Handler.do_POST -> {_serve_sse, _serve_json} -> _run_once -> {_acquire_slot, Run.__init__ -> {_launcher, Popen, источник мышления.start}, _execute -> Run.q, Run.close -> _kill_group}; Run._pump -> {Run.q, источник.bind/join}; источник мышления -> {transcript stat/read -> _emit_record, sqlite3.connect(mode=ro) -> SELECT steps -> wire-парсер -> append-only выдача -> emit}. Нет вызовов asyncio, fork, HTTP-клиентов, Redis/PG/Vault/Control Plane, TTL-кэшей с дозапросом, пулов нод/карантина/origin health; /health не зависит от SQLite",
          "future_diff_gate": "Текущий пустой diff доказывает read-only Stage 2, а не отсутствие будущих вызовов: VER-009 (ast импорты/connect/URI), VER-008 (allowlist файлов) и VER-003/VER-007 (AO-оракулы) повторно подтверждают N/A на диффе кандидата до ARCH-приёмки кода"
        },
        "verification_ids": [
          "VER-003",
          "VER-009"
        ]
      },
      "S-HERD-I5": {
        "status": "N/A",
        "reason": "Нет снапшота Control Plane/readiness-зависимости: /health получает только аддитивные счётчики из памяти процесса (без SQLite и сетевых вызовов); staleness мышления ≤5.6 с; секрет статичен в env",
        "na_proof": {
          "current_git_diff_command": "git diff --name-only e00da0621fc95f7c63cd1565f4a5d1fd490c8d66 -- bridges/agy-bridge tests/test_agy_bridge_resilience.py",
          "current_git_diff_output": "",
          "current_product_fingerprint": "aed3274571859b39f08788443955470300be30a9dfd8ea5d0e994001433a0bbb",
          "git_diff_files": [
            "bridges/agy-bridge/server.py",
            "tests/test_agy_bridge_resilience.py"
          ],
          "transitive_call_graph": "Handler.do_POST -> {_serve_sse, _serve_json} -> _run_once -> {_acquire_slot, Run.__init__ -> {_launcher, Popen, источник мышления.start}, _execute -> Run.q, Run.close -> _kill_group}; Run._pump -> {Run.q, источник.bind/join}; источник мышления -> {transcript stat/read -> _emit_record, sqlite3.connect(mode=ro) -> SELECT steps -> wire-парсер -> append-only выдача -> emit}. Нет вызовов asyncio, fork, HTTP-клиентов, Redis/PG/Vault/Control Plane, TTL-кэшей с дозапросом, пулов нод/карантина/origin health; /health не зависит от SQLite",
          "future_diff_gate": "Текущий пустой diff доказывает read-only Stage 2, а не отсутствие будущих вызовов: VER-009 (ast импорты/connect/URI), VER-008 (allowlist файлов) и VER-003/VER-007 (AO-оракулы) повторно подтверждают N/A на диффе кандидата до ARCH-приёмки кода"
        },
        "verification_ids": [
          "VER-003",
          "VER-006"
        ]
      }
    },
    "H_CPU": {
      "H-CPU-I1": {
        "status": "PASS",
        "substitution": "Нет routing Snapshot; выборка по индексу step_type + диапазону PK idx ≥ poll_watermark с LIMIT 16 и BLOB ≤256 KiB; seen — dict O(1) по ключу шага, ≤128 записей",
        "oracle": "AO-05: число запросов и вызовов парсера на опрос не растёт с числом строк steps (100 → 1000)",
        "verification_ids": [
          "VER-003",
          "VER-007"
        ]
      },
      "H-CPU-I2": {
        "status": "PASS",
        "substitution": "Regex cid и SQL — константы модуля; dynamic_config.json: stat не чаще раза в 1.0 с (TTL), json.loads только при смене (mtime_ns, size); парсер на memoryview без копий с проверкой stop каждые 64 тега; sha256 BLOB ≤256 KiB на изменившейся строке; deepcopy/pydantic нет",
        "oracle": "AO-05: при неизменном dynamic_config.json json.loads.call_count == 1 на 10 ходов; re.compile в цикле опроса не вызывается",
        "verification_ids": [
          "VER-003",
          "VER-007"
        ]
      },
      "H-CPU-I3": {
        "status": "PASS",
        "substitution": "Первая инструкция SQLite-пути — if not enabled: return (проверка перед каждым SELECT и каждые 0.25 с ожидания, кэш TTL 1.0 с); при выключенном флаге sqlite3.connect и парсер не вызываются; логи источника ограничены (одна строка ошибки открытия на ход)",
        "oracle": "TC-91: флаг выкл → connect.call_count == 0, parser.call_count == 0",
        "verification_ids": [
          "VER-003",
          "VER-007"
        ]
      },
      "H-CPU-I4": {
        "status": "N/A",
        "reason": "asyncio/event loop и горячего reload Snapshot нет: ThreadingHTTPServer + потоки; разбор payload ≤40 KB идёт в потоке источника своего хода",
        "na_proof": {
          "current_git_diff_command": "git diff --name-only e00da0621fc95f7c63cd1565f4a5d1fd490c8d66 -- bridges/agy-bridge tests/test_agy_bridge_resilience.py",
          "current_git_diff_output": "",
          "current_product_fingerprint": "aed3274571859b39f08788443955470300be30a9dfd8ea5d0e994001433a0bbb",
          "git_diff_files": [
            "bridges/agy-bridge/server.py",
            "tests/test_agy_bridge_resilience.py"
          ],
          "transitive_call_graph": "Handler.do_POST -> {_serve_sse, _serve_json} -> _run_once -> {_acquire_slot, Run.__init__ -> {_launcher, Popen, источник мышления.start}, _execute -> Run.q, Run.close -> _kill_group}; Run._pump -> {Run.q, источник.bind/join}; источник мышления -> {transcript stat/read -> _emit_record, sqlite3.connect(mode=ro) -> SELECT steps -> wire-парсер -> append-only выдача -> emit}. Нет вызовов asyncio, fork, HTTP-клиентов, Redis/PG/Vault/Control Plane, TTL-кэшей с дозапросом, пулов нод/карантина/origin health; /health не зависит от SQLite",
          "future_diff_gate": "Текущий пустой diff доказывает read-only Stage 2, а не отсутствие будущих вызовов: VER-009 (ast импорты/connect/URI), VER-008 (allowlist файлов) и VER-003/VER-007 (AO-оракулы) повторно подтверждают N/A на диффе кандидата до ARCH-приёмки кода"
        },
        "verification_ids": [
          "VER-009"
        ]
      },
      "H-CPU-I5": {
        "status": "PASS",
        "substitution": "t_req_total = 0.010 + 2·0.005 = 0.020 CPU-s (оценка); Util_worker = 1.0·6·0.020/(1·1) + 0.12 = 0.24 ≤ 0.70; Pod = 1·0.24 + 0 = 0.24 ≤ 0.80·2.0 = 1.6; Feature: для долгоживущих потоковых ходов RPS·Δt = N_active·u_poll (закон Литтла) = 8·0.01 = 0.08 ≤ 0.05·(1·2.0) = 0.10; худший случай — минимальный допустимый SQLITE_POLL_S=0.5 (TC-93 меряется именно на нём)",
        "oracle": "Расчётный тест по HL-ENV + L2 TC-93 измеряет ≤1% ядра на ход",
        "verification_ids": [
          "VER-007",
          "VER-010"
        ]
      }
    },
    "R_BULK": {
      "R-BULK-I1": {
        "status": "PASS",
        "substitution": "Изменяемый критический путь: T_crit_aux(a) = водяной знак resumed 0.1 + proc.wait 0.05 + 0.05 + окно drain 0.35 + join 0.15 = 0.70 с (на максимумах диапазонов 0.1 + 0.05 + 0.05 + 0.50 + 0.20 = 0.90 с); T_backoff(1) ≤ 2.0 с; Σ по A_max=2: 2·0.90 + 2.0 = 3.8 с ≤ 0.30·1800 = 540 с; при deadline-remaining ≤ 0 повтор не стартует (as-is TIMEOUT_S). Унаследованное ожидание слота QUEUE_TIMEOUT_S (900 код / 1800 деплой) — BASELINE_DEBT BD-001",
        "oracle": "AO-03: на FakeClock EOF→done ≤ 0.60 с при дефолтах и ≤ 0.80 с на максимумах; drain не дольше DRAIN_WINDOW_S ≤ DRAIN_MAX_S, join ограничен; статический пересчёт неравенства",
        "verification_ids": [
          "VER-003",
          "VER-007"
        ],
        "baseline_debt": "BD-001"
      },
      "R-BULK-I2": {
        "status": "PASS",
        "substitution": "Процессный token-bucket в целых десятых: capacity 30, +2 на первичный, −10 на повтор, reserve 0 → N_retries ≤ floor(2·N_req/10) + 3 без дрейфа float. Bulkhead-семафор _slots унаследован (ожидание вместо мгновенного fallback) — BASELINE_DEBT BD-002",
        "oracle": "AO-02: 100 падающих запросов → повторов ≤ 23; последовательность, дававшая 0.9999999999999999 во float, даёт ровно 10 десятых и разрешает повтор",
        "verification_ids": [
          "VER-003",
          "VER-007"
        ],
        "baseline_debt": "BD-002"
      },
      "R-BULK-I3": {
        "status": "PASS",
        "substitution": "Fail-open: SQLite и транскрипт; fail-closed: Bearer-авторизация (as-is) и флаг фичи. SQLite breaker под _sqlite_guard_lock: K=3 подряд сбойных хода (DatabaseError; OperationalError после ≥1 успешного SELECT на существующем <cid>.db-wal; схемная ошибка; divergence; cold-open не считается) → OPEN на 30.0 с без connect (0 с), затем HALF_OPEN с атомарной единственной пробой probe_gen; исходы пробы: успех → CLOSED, ошибка → OPEN, без SELECT → снятие пробы (остаётся HALF_OPEN); аренда 60 с истекает, устаревшая проба (probe_gen ≠ активного) прекращает SELECT и не меняет FSM в finally",
        "oracle": "AO-01: после 3 сбойных ходов connect.call_count не растёт; 3 холодных хода оставляют CLOSED; через 30 с FakeClock 10 одновременных ходов → ровно 1 пробный connect; три исхода пробы, автоистечение 60 с и no-op устаревшей пробы переводят FSM как специфицировано",
        "verification_ids": [
          "VER-003",
          "VER-007"
        ]
      },
      "R-BULK-I4": {
        "status": "N/A",
        "reason": "Нет пула нод/карантина/Panic-Open: единственный апстрим agy. Аналог N_floor=1 соблюдён: транскрипт никогда не выключается, выключается только вспомогательный SQLite",
        "na_proof": {
          "current_git_diff_command": "git diff --name-only e00da0621fc95f7c63cd1565f4a5d1fd490c8d66 -- bridges/agy-bridge tests/test_agy_bridge_resilience.py",
          "current_git_diff_output": "",
          "current_product_fingerprint": "aed3274571859b39f08788443955470300be30a9dfd8ea5d0e994001433a0bbb",
          "git_diff_files": [
            "bridges/agy-bridge/server.py",
            "tests/test_agy_bridge_resilience.py"
          ],
          "transitive_call_graph": "Handler.do_POST -> {_serve_sse, _serve_json} -> _run_once -> {_acquire_slot, Run.__init__ -> {_launcher, Popen, источник мышления.start}, _execute -> Run.q, Run.close -> _kill_group}; Run._pump -> {Run.q, источник.bind/join}; источник мышления -> {transcript stat/read -> _emit_record, sqlite3.connect(mode=ro) -> SELECT steps -> wire-парсер -> append-only выдача -> emit}. Нет вызовов asyncio, fork, HTTP-клиентов, Redis/PG/Vault/Control Plane, TTL-кэшей с дозапросом, пулов нод/карантина/origin health; /health не зависит от SQLite",
          "future_diff_gate": "Текущий пустой diff доказывает read-only Stage 2, а не отсутствие будущих вызовов: VER-009 (ast импорты/connect/URI), VER-008 (allowlist файлов) и VER-003/VER-007 (AO-оракулы) повторно подтверждают N/A на диффе кандидата до ARCH-приёмки кода"
        },
        "verification_ids": [
          "VER-003"
        ]
      },
      "R-BULK-I5": {
        "status": "N/A",
        "reason": "Нет прокси-нод и доменных origin: разделять origin_health и node_health нечего",
        "na_proof": {
          "current_git_diff_command": "git diff --name-only e00da0621fc95f7c63cd1565f4a5d1fd490c8d66 -- bridges/agy-bridge tests/test_agy_bridge_resilience.py",
          "current_git_diff_output": "",
          "current_product_fingerprint": "aed3274571859b39f08788443955470300be30a9dfd8ea5d0e994001433a0bbb",
          "git_diff_files": [
            "bridges/agy-bridge/server.py",
            "tests/test_agy_bridge_resilience.py"
          ],
          "transitive_call_graph": "Handler.do_POST -> {_serve_sse, _serve_json} -> _run_once -> {_acquire_slot, Run.__init__ -> {_launcher, Popen, источник мышления.start}, _execute -> Run.q, Run.close -> _kill_group}; Run._pump -> {Run.q, источник.bind/join}; источник мышления -> {transcript stat/read -> _emit_record, sqlite3.connect(mode=ro) -> SELECT steps -> wire-парсер -> append-only выдача -> emit}. Нет вызовов asyncio, fork, HTTP-клиентов, Redis/PG/Vault/Control Plane, TTL-кэшей с дозапросом, пулов нод/карантина/origin health; /health не зависит от SQLite",
          "future_diff_gate": "Текущий пустой diff доказывает read-only Stage 2, а не отсутствие будущих вызовов: VER-009 (ast импорты/connect/URI), VER-008 (allowlist файлов) и VER-003/VER-007 (AO-оракулы) повторно подтверждают N/A на диффе кандидата до ARCH-приёмки кода"
        },
        "verification_ids": [
          "VER-003"
        ]
      }
    },
    "T_LIFE_v1": {
      "status": "PASS",
      "substitution": "Поток источника живёт не дольше хода: выход при stop_event сразу (активный SELECT прерывается conn.interrupt()), при выключении флага — закрытие SQLite ≤1.30 с и продолжение на транскрипте, при _proc_done — после окна drain ≤0.35 с (≤0.50), без bind — сразу по _proc_done; соединение SQLite закрывается в finally; _pump ждёт поток с бюджетом окно drain + JOIN_TIMEOUT_S; Run.close зачищает группу as-is",
      "oracle": "AO-04: 20 ходов → threading.active_count() возвращается к исходному, открытых соединений 0",
      "verification_ids": [
        "VER-003",
        "VER-007"
      ]
    },
    "O_EXIT_v1": {
      "status": "PASS",
      "substitution": "Одна строка done model=… state=… на каждом выходе _run_once (включая no slot и launcher_unavailable) с полями rc, conversation, turns, tool_events, out_bytes, wall_s, err + reasoning_chunks, sqlite=on|off|breaker|open_fail, sqlite_emits, drain_ms, retries, retry_tokens",
      "oracle": "AO-06: перехват _log на всех ветках выхода → ровно одна строка done с обязательными полями",
      "verification_ids": [
        "VER-003",
        "VER-007"
      ]
    },
    "M_SEM_v1": {
      "status": "PASS",
      "substitution": "Семантическая изоляция горячих сессий: допустимое множество для claim — только агентные запросы (tools_count>0, не фоновые); plain и фоновые запросы стор не читают и не пишут, поэтому разные диалоги без tools не делят cid; новых пулов нет (_slots общий as-is)",
      "oracle": "TC-80..TC-82 (включая два разных plain-диалога по 2 хода без обращения к _session_claim)",
      "verification_ids": [
        "VER-003",
        "VER-007"
      ]
    },
    "dependency_failure_matrix": [
      {
        "dependency_operation": "conversations/<cid>.db SELECT (live)",
        "path": "bg (поток источника хода)",
        "timeout_budget": "connect timeout 0.05 с + busy_timeout 50 мс; период SQLITE_POLL_S ∈ [0.5, 2.0]; огибающая N(Δt) ≤ 3 + 2·Δt SELECT на ход (bucket); LIMIT 16, BLOB ≤256 KiB; conn.interrupt() при stop",
        "bulkhead": "≤1 одновременного соединения на ход, ≤8 на процесс",
        "circuit_breaker": "K=3 сбойных ходов (cold-open не считается) / cooldown 30.0 с / HALF_OPEN — 1 атомарная проба с probe_gen, аренда 60 с, устаревшая проба — no-op",
        "failure_mode_fallback": "Fail-Open: «изменений нет», мышление из транскрипта; без immutable"
      },
      {
        "dependency_operation": "conversations/<cid>.db водяной знак resumed (mode=ro, без immutable) + владение cid",
        "path": "control (до spawn)",
        "timeout_budget": "≤0.1 с",
        "bulkhead": "1 открытие на resumed-ход",
        "circuit_breaker": "общий SQLite breaker",
        "failure_mode_fallback": "resumed: оба водяных знака (транскрипт + SQLite) до Popen, иначе turn_mode=OFF — transcript-only с pre-spawn водяным знаком (anchored=False запрещён); cid занят другим turn_id → свежий cid без --resume"
      },
      {
        "dependency_operation": "transcript_full.jsonl stat/read",
        "path": "bg",
        "timeout_budget": "локальный read ≤4 MiB за проход; период 0.05 с",
        "bulkhead": "1 читатель на ход",
        "circuit_breaker": "нет (минимальный источник, N_floor)",
        "failure_mode_fallback": "Fail-Open: «мышления нет» (as-is)"
      },
      {
        "dependency_operation": "финальный drain источников",
        "path": "hot (между EOF и done)",
        "timeout_budget": "proc.wait ≤0.05 + 0.05 + окно drain 0.35 (0.20..0.50) + conn.interrupt() + join 0.15 (max 0.20)",
        "bulkhead": "поток своего хода",
        "circuit_breaker": "n/a (жёсткий deadline)",
        "failure_mode_fallback": "по окну — done с outcome=window_complete pending_steps; поздние события → reasoning-late-drop (run._emit_lock, drain_closed)"
      },
      {
        "dependency_operation": "процесс agy (spawn, stdout)",
        "path": "hot",
        "timeout_budget": "FIRST_TOKEN 120 с, idle 300 с, TIMEOUT 1800 с (as-is)",
        "bulkhead": "_slots MAX_CONCURRENT (as-is, BD-002)",
        "circuit_breaker": "retry budget 30 десятых + Full Jitter (AD-005)",
        "failure_mode_fallback": "до выдачи — один повтор при наличии токена; после выдачи — data:{error}+[DONE]"
      },
      {
        "dependency_operation": "dynamic_config.json",
        "path": "control (перед каждым SELECT и каждые 0.25 с ожидания, кэш TTL 1.0 с)",
        "timeout_budget": "stat не чаще раза в 1.0 с + json.loads только при смене",
        "bulkhead": "n/a",
        "circuit_breaker": "n/a",
        "failure_mode_fallback": "Fail-Closed для фичи: нет/битый файл, OSError/ValueError, нет ключа → кэш сразу False (поведение as-is, активный ход переходит на транскрипт ≤1.30 с)"
      }
    ],
    "baseline_debt": [
      {
        "id": "BD-001",
        "code": "R-BULK-I1",
        "fact": "Ожидание слота _acquire_slot до QUEUE_TIMEOUT_S 900 с (код) / 1800 с (деплой) > 0.30·1800 = 540 с",
        "evidence_ids": [
          "EVD-063",
          "EVD-038"
        ],
        "delta_effect": "не меняется (VER-008 + AO-03 не трогают _acquire_slot)"
      },
      {
        "id": "BD-002",
        "code": "C-MULT-I2 / R-BULK-I2",
        "fact": "_slots BoundedSemaphore(M) с ожидающими до 32−M (деплой 24 > 2·8; код 28 > 2·4), ожидание вместо мгновенного fallback",
        "evidence_ids": [
          "EVD-062",
          "EVD-063"
        ],
        "delta_effect": "не меняется"
      },
      {
        "id": "BD-003",
        "code": "канон gate basedpyright",
        "fact": "12 ошибок basedpyright на baseline в target-файлах (EVD-060, EVD-074)",
        "evidence_ids": [
          "EVD-060",
          "EVD-076"
        ],
        "delta_effect": "Не допуск: устраняются в этом MR типизацией по списку EVD-076 (VER-004 errorCount == 0 и 0 новых предупреждений, без # type: ignore); невозможность исправить без изменения поведения → BLOCKED владельцу"
      },
      {
        "id": "BD-004",
        "code": "UNBOUNDED_QUEUE",
        "fact": "Run.q = queue.Queue() без maxsize",
        "evidence_ids": [
          "EVD-057"
        ],
        "delta_effect": "Новые события мышления ограничены MAX_REASONING_BYTES_PER_TURN = 2 MiB на ход (Run.q + out['reasoning'] ≤4 MiB), без амплификации; сама очередь без maxsize — унаследовано"
      },
      {
        "id": "BD-005",
        "code": "Full Suite Gate",
        "fact": "3 красных теста полного набора вне agy-bridge (F-56)",
        "evidence_ids": [
          "EVD-056"
        ],
        "delta_effect": "Не засчитываются как PASS: VER-012 — agy-набор на /usr/bin/python3 (0 failures); полный набор — pre-MR rollout checkpoint Q-005, ровно эти 3 красных = BLOCKED: OWNER_DECISION_REQUIRED до MR; файлы вне границы правки не трогаются"
      }
    ],
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
    "summary": {
      "PASS": 19,
      "N/A": 5,
      "FAIL": 0,
      "BASELINE_DEBT_refs": [
        "BD-001",
        "BD-002"
      ],
      "meaning": "проектные инварианты; runtime-оракулы L1/L2 и L3 ещё не выполнены"
    }
  },
  "legacy_arch_antipattern_checks": {
    "ARCH_CYCLE_DETECTED": {
      "status": "PASS",
      "rationale": "DAG: Handler → _run_once → Run → {_pump, источник мышления → парсер}; парсер и стор без обратных зависимостей",
      "verification_ids": [
        "VER-003"
      ],
      "evidence_level": "design; L1 required"
    },
    "LAYER_VIOLATION": {
      "status": "PASS",
      "rationale": "Источник не пишет в сокет, Handler не читает файлы agy; парсер без I/O",
      "verification_ids": [
        "VER-003",
        "VER-009"
      ],
      "evidence_level": "design; L1 required"
    },
    "GOD_OBJECT": {
      "status": "PASS",
      "rationale": "SQLite-опрос и парсер — отдельные единицы рядом с _TranscriptTail; Handler не расширяется ветвлениями источников. Размер server.py унаследован",
      "verification_ids": [
        "VER-003"
      ],
      "evidence_level": "design; L1 required"
    },
    "TIGHT_COUPLING": {
      "status": "PASS",
      "rationale": "Оба источника сводятся к кортежу ('reasoning', str) в Run.q — граница F-03/F-06/F-07",
      "verification_ids": [
        "VER-003"
      ],
      "evidence_level": "design; L1 required"
    },
    "LEAKY_ABSTRACTION": {
      "status": "PASS",
      "rationale": "Клиент видит прежние SSE/JSON; внутренние idx/status/payload наружу не уходят",
      "verification_ids": [
        "VER-003",
        "VER-006"
      ],
      "evidence_level": "design; L1 required"
    },
    "MISSING_TIMEOUT": {
      "status": "PASS",
      "rationale": "SQLite timeout 0.05 с + busy_timeout 50 мс, водяной знак ≤0.1 с, proc.wait ≤0.05 с, окно drain 0.35 (≤0.50) с, conn.interrupt() и join ≤0.15 (≤0.20) с сверх окна drain, kill-switch ≤1.30 с; остальные таймауты as-is",
      "verification_ids": [
        "VER-003",
        "VER-007"
      ],
      "evidence_level": "design; L1 required"
    },
    "UNBOUNDED_RETRY": {
      "status": "PASS",
      "rationale": "A_max=2 и процессный bucket 30 десятых; SQLite-опрос — фиксированный период с per-turn bucket, без циклов повторов",
      "verification_ids": [
        "VER-003",
        "VER-007"
      ],
      "evidence_level": "design; L1 required"
    },
    "RETRY_STORM": {
      "status": "PASS",
      "rationale": "Retry budget + Full Jitter; после выдачи повторов нет",
      "verification_ids": [
        "VER-003",
        "VER-007"
      ],
      "evidence_level": "design; L1 required"
    },
    "THUNDERING_HERD": {
      "status": "PASS",
      "rationale": "Поллеры по ходам на разные файлы, старт по init; общего опрашиваемого ресурса нет",
      "verification_ids": [
        "VER-010"
      ],
      "evidence_level": "design; L2 required"
    },
    "UNBOUNDED_QUEUE": {
      "status": "PASS",
      "rationale": "Run.q без maxsize унаследована (BD-004); новые события ограничены длиной финального мышления (каждая позиция выдаётся не более одного раза), без амплификации",
      "verification_ids": [
        "VER-003"
      ],
      "evidence_level": "design; L1 required"
    },
    "MISSING_BACKPRESSURE": {
      "status": "PASS",
      "rationale": "Ingress 32 соединения, слоты MAX_CONCURRENT (as-is); источник не опережает писателя — опрос 0.5 с",
      "verification_ids": [
        "VER-003"
      ],
      "evidence_level": "design; L1 required"
    },
    "BLOCKING_IO_IN_ASYNC": {
      "status": "N/A",
      "rationale": "asyncio не используется: ThreadingHTTPServer и потоки",
      "verification_ids": [
        "VER-009"
      ],
      "evidence_level": "design",
      "na_proof": {
        "current_git_diff_command": "git diff --name-only e00da0621fc95f7c63cd1565f4a5d1fd490c8d66 -- bridges/agy-bridge tests/test_agy_bridge_resilience.py",
        "current_git_diff_output": "",
        "current_product_fingerprint": "aed3274571859b39f08788443955470300be30a9dfd8ea5d0e994001433a0bbb",
        "git_diff_files": [
          "bridges/agy-bridge/server.py",
          "tests/test_agy_bridge_resilience.py"
        ],
        "transitive_call_graph": "Handler.do_POST -> {_serve_sse, _serve_json} -> _run_once -> {_acquire_slot, Run.__init__ -> {_launcher, Popen, источник мышления.start}, _execute -> Run.q, Run.close -> _kill_group}; Run._pump -> {Run.q, источник.bind/join}; источник мышления -> {transcript stat/read -> _emit_record, sqlite3.connect(mode=ro) -> SELECT steps -> wire-парсер -> append-only выдача -> emit}. Нет вызовов asyncio, fork, HTTP-клиентов, Redis/PG/Vault/Control Plane, TTL-кэшей с дозапросом, пулов нод/карантина/origin health; /health не зависит от SQLite",
        "future_diff_gate": "Текущий пустой diff доказывает read-only Stage 2, а не отсутствие будущих вызовов: VER-009 (ast импорты/connect/URI), VER-008 (allowlist файлов) и VER-003/VER-007 (AO-оракулы) повторно подтверждают N/A на диффе кандидата до ARCH-приёмки кода"
      }
    },
    "CPU_SPIN_WAIT": {
      "status": "PASS",
      "rationale": "Опрос со sleep периода, ожидания через Event.wait/join с таймаутом; busy-loop нет",
      "verification_ids": [
        "VER-003",
        "VER-010"
      ],
      "evidence_level": "design; L1/L2 required"
    },
    "RESOURCE_LEAK": {
      "status": "PASS",
      "rationale": "≤1 одновременного SQLite-соединения, каждое переоткрытие закрывает прежний handle в finally; seen ≤128 без текста; файлы транскрипта через with; поток завершается по stop/drain/флагу",
      "verification_ids": [
        "VER-003",
        "VER-007"
      ],
      "evidence_level": "design; L1 required"
    },
    "ZOMBIE_SUBPROCESS": {
      "status": "PASS",
      "rationale": "Новых подпроцессов нет; _kill_group с reap лидера as-is",
      "verification_ids": [
        "VER-003"
      ],
      "evidence_level": "design; L1 required"
    },
    "RACE_CONDITION": {
      "status": "PASS",
      "rationale": "seen — единственный писатель (поток источника); процессные guard'ы под одним _sqlite_guard_lock с атомарной пробой HALF_OPEN; порядок reasoning→done через FIFO, join и дочитывание _execute до done; стор под замком; поздние emit после drain_closed логируются",
      "verification_ids": [
        "VER-003",
        "VER-007"
      ],
      "evidence_level": "design; L1 required"
    },
    "NON_IDEMPOTENT_RETRY": {
      "status": "PASS",
      "rationale": "Повтор хода только до выдачи (text/tool_calls/потоковое reasoning, включая reasoning после result ERROR — AO-11); после — кадр ошибки",
      "verification_ids": [
        "VER-003",
        "VER-007"
      ],
      "evidence_level": "design; L1 required"
    },
    "BREAKING_CONTRACT": {
      "status": "PASS",
      "rationale": "Эндпоинты, порт, форма чанков и флаги agy неизменны; поведенческие дельты CD-001..CD-005 разрешены текущими REQ",
      "verification_ids": [
        "VER-003",
        "VER-006",
        "VER-012"
      ],
      "evidence_level": "design; L1 required"
    },
    "SILENT_DATA_LOSS": {
      "status": "PASS",
      "rationale": "Drain до done с outcome=complete|window_complete pending_steps; поздние события (reasoning-late-drop), divergence (заморозка шага, /health sqlite_divergence_count), reasoning-cap и sqlite-live-loss логируются; fail-open не теряет транскрипт",
      "verification_ids": [
        "VER-003",
        "VER-010"
      ],
      "evidence_level": "design; L1/L2 required"
    },
    "UNHANDLED_UPSTREAM_ERROR": {
      "status": "PASS",
      "rationale": "Ошибки sqlite3/парсера поглощаются с классом в логе; ошибки agy — as-is классификатор и кадр ошибки",
      "verification_ids": [
        "VER-003",
        "VER-005"
      ],
      "evidence_level": "design; L1 required"
    },
    "HARDCODED_SECRET": {
      "status": "PASS",
      "rationale": "Новых секретов нет; ключ только из env; в логах без текста и токенов",
      "verification_ids": [
        "VER-003",
        "VER-007"
      ],
      "evidence_level": "design; L1 required"
    }
  },
  "status_protocol_examples": {
    "client_status_messages": "Мост не добавляет synthetic status-текст в поток (REQ-010: текст модели не модифицируется); примеры ниже — протокол статусов гейта для оркестратора/Teamlead",
    "gate_pass": "ARCH_GATE: PASS packet=architecture/architecture-packet.json stop_codes=21/21 (PASS 16, N/A 5, FAIL 0) + T-LIFE/O-EXIT/M-SEM PASS",
    "gate_blocked": "ARCH_GATE: BLOCKED ARCH_STOP_<код> — <инвариант>: <факт>; вердикт REJECT до исправления, техдолг не допускается",
    "stop_codes": {
      "ARCH_STOP_HL_ENV_01": {
        "code": "HL-ENV-01",
        "trigger": "нет любого из 46 полей, неравенство памяти нарушено или N/A без двойного доказательства",
        "example": "BLOCKED ARCH_STOP_HL_ENV_01 missing field T_poll_s[d]",
        "current": "PASS"
      },
      "ARCH_STOP_C_MULT_I1": {
        "code": "C-MULT-I1",
        "trigger": "C_dep(d) > 0.60·Limit_dep_share[d]",
        "example": "BLOCKED ARCH_STOP_C_MULT_I1 conversations_db C=3 > 2.4",
        "current": "PASS"
      },
      "ARCH_STOP_C_MULT_I2": {
        "code": "C-MULT-I2",
        "trigger": "пул без жёсткого предела/таймаута ожидания или max_waiters > 2M в новом коде",
        "example": "BLOCKED ARCH_STOP_C_MULT_I2 sqlite connect waits unbounded",
        "current": "PASS (BD-002 унаследован)"
      },
      "ARCH_STOP_C_MULT_I3": {
        "code": "C-MULT-I3",
        "trigger": "соединение создаётся глобально/в обработчике или до fork",
        "example": "BLOCKED ARCH_STOP_C_MULT_I3 module-level sqlite3.connect",
        "current": "PASS"
      },
      "ARCH_STOP_C_MULT_I4": {
        "code": "C-MULT-I4",
        "trigger": "stop/отмена оставляет открытое соединение или живой поток",
        "example": "BLOCKED ARCH_STOP_C_MULT_I4 open connections after close = 1",
        "current": "PASS"
      },
      "ARCH_STOP_C_MULT_I5": {
        "code": "C-MULT-I5",
        "trigger": "FD > 0.70·ulimit_n или порты > 50%",
        "example": "BLOCKED ARCH_STOP_C_MULT_I5 FD 50000 > 45875",
        "current": "PASS"
      },
      "ARCH_STOP_S_HERD_I1": {
        "code": "S-HERD-I1",
        "trigger": "пачечный залп или стационарный опрос выше 50%/20% лимита",
        "example": "BLOCKED ARCH_STOP_S_HERD_I1 R_poll 8 > 4 q/s",
        "current": "PASS"
      },
      "ARCH_STOP_S_HERD_I2": {
        "code": "S-HERD-I2",
        "trigger": "фиксированная пауза повтора без jitter / неинъецируемый RNG",
        "example": "BLOCKED ARCH_STOP_S_HERD_I2 retry sleep fixed 2s",
        "current": "PASS"
      },
      "ARCH_STOP_S_HERD_I3": {
        "code": "S-HERD-I3",
        "trigger": "повторный парсинг неизменных данных",
        "example": "BLOCKED ARCH_STOP_S_HERD_I3 parser.call_count 10 on unchanged row",
        "current": "PASS"
      },
      "ARCH_STOP_S_HERD_I4": {
        "code": "S-HERD-I4",
        "trigger": "появился TTL-кэш с дозапросом без singleflight или негативный кэш транзиентных ошибок",
        "example": "BLOCKED ARCH_STOP_S_HERD_I4 open-fail cached for turn",
        "current": "N/A"
      },
      "ARCH_STOP_S_HERD_I5": {
        "code": "S-HERD-I5",
        "trigger": "появилась readiness-зависимость от снапшота без политики staleness",
        "example": "BLOCKED ARCH_STOP_S_HERD_I5 /health depends on sqlite",
        "current": "N/A"
      },
      "ARCH_STOP_H_CPU_I1": {
        "code": "H-CPU-I1",
        "trigger": "линейный рост работы опроса с числом строк steps",
        "example": "BLOCKED ARCH_STOP_H_CPU_I1 full table scan per poll",
        "current": "PASS"
      },
      "ARCH_STOP_H_CPU_I2": {
        "code": "H-CPU-I2",
        "trigger": "re.compile/json.loads конфига/deepcopy на горячем пути",
        "example": "BLOCKED ARCH_STOP_H_CPU_I2 json.loads dynamic_config per chunk",
        "current": "PASS"
      },
      "ARCH_STOP_H_CPU_I3": {
        "code": "H-CPU-I3",
        "trigger": "выключенный флаг не даёт нулевую стоимость",
        "example": "BLOCKED ARCH_STOP_H_CPU_I3 connect called with flag off",
        "current": "PASS"
      },
      "ARCH_STOP_H_CPU_I4": {
        "code": "H-CPU-I4",
        "trigger": "появился event loop/reload-путь с блокировкой > 2 мс",
        "example": "BLOCKED ARCH_STOP_H_CPU_I4 asyncio loop blocked by parser",
        "current": "N/A"
      },
      "ARCH_STOP_H_CPU_I5": {
        "code": "H-CPU-I5",
        "trigger": "нарушено любое из трёх неравенств CPU",
        "example": "BLOCKED ARCH_STOP_H_CPU_I5 feature 0.16 > 0.10 cores",
        "current": "PASS"
      },
      "ARCH_STOP_R_BULK_I1": {
        "code": "R-BULK-I1",
        "trigger": "Σ вспомогательных ожиданий изменяемого пути > 0.30·SLA или drain без deadline",
        "example": "BLOCKED ARCH_STOP_R_BULK_I1 drain unbounded",
        "current": "PASS (BD-001 унаследован)"
      },
      "ARCH_STOP_R_BULK_I2": {
        "code": "R-BULK-I2",
        "trigger": "повторы без процессного бюджета",
        "example": "BLOCKED ARCH_STOP_R_BULK_I2 retries 100 > 23",
        "current": "PASS (BD-002 унаследован)"
      },
      "ARCH_STOP_R_BULK_I3": {
        "code": "R-BULK-I3",
        "trigger": "нет breaker/HALF_OPEN>1 или fail-closed вспомогательной зависимости",
        "example": "BLOCKED ARCH_STOP_R_BULK_I3 half-open probes 10",
        "current": "PASS"
      },
      "ARCH_STOP_R_BULK_I4": {
        "code": "R-BULK-I4",
        "trigger": "появился пул нод с карантином без post-eviction предиката",
        "example": "BLOCKED ARCH_STOP_R_BULK_I4 transcript source disabled",
        "current": "N/A"
      },
      "ARCH_STOP_R_BULK_I5": {
        "code": "R-BULK-I5",
        "trigger": "появились прокси-ноды без разделения origin/node health",
        "example": "BLOCKED ARCH_STOP_R_BULK_I5 node marked bad for origin error",
        "current": "N/A"
      }
    }
  },
  "architect_oracles": {
    "AO-01": "SQLite breaker FSM под _sqlite_guard_lock: 3 подряд сбойных хода → OPEN, connect не вызывается; сбойный ход = sqlite3.DatabaseError, ИЛИ sqlite3.OperationalError после ≥1 успешного SELECT хода на существующем <cid>.db-wal, ИЛИ схемная ошибка, ИЛИ divergence префикса; cold-open (нет <cid>.db/<cid>.db-wal или OperationalError на connect/до первого успешного SELECT) и interrupted от собственного stop не считаются — 3 холодных хода подряд оставляют CLOSED; ход с ≥1 успешным SELECT и 0 ошибок → consecutive_failures == 0; единичная divergence не открывает; через cooldown 30.0 с FakeClock 10 одновременных ходов → ровно 1 атомарная проба с probe_gen = G; исходы пробы: ≥1 SELECT без ошибок → CLOSED, ошибка → OPEN, без SELECT → снятие пробы и HALF_OPEN; проба старше 60.0 с истекает, следующий ход берёт probe_gen = G+1, устаревшая проба G перед следующим SELECT видит _breaker_active_probe_gen != G → conn.close(), SELECT больше не выполняет, её finally не меняет FSM; _reset_sqlite_guards_for_tests() изолирует тесты",
    "AO-02": "Retry budget в целых десятых: 100 падающих запросов → повторов ≤ floor(2·100/10)+3 = 23; последовательность +2×… даёт ровно 10 десятых и разрешает повтор (нет float-дрейфа); RNG u∈{0,0.5,1} → паузы {0.0,1.0,2.0} с; hot→cold fallback тратит 10 десятых",
    "AO-03": "Drain/join: на FakeClock EOF→done ≤ 0.60 с при дефолтах и ≤ 0.80 с на максимумах диапазонов; без авторитетного маркера конца хода drain идёт полное окно DRAIN_WINDOW_S (7 тиков по 0.05 с), в т. ч. при ≥1 PLANNER_RESPONSE и all-steps-in-transcript (эвристика R2 не даёт раннего выхода); досрочный выход после DRAIN_MIN_S только по END_TURN/TURN_COMPLETE или PLANNER_RESPONSE с непустым финальным ответом и 0 строк status=8 на двух подряд тиках; outcome=complete только при pending_steps == 0 и финальном PLANNER_RESPONSE, иначе outcome=window_complete pending_steps=N; proc.wait ≤0.05 при EOF с живым процессом; _pump ставит done через _close_and_put_done после join; конкурентный тест: эмиттер в цикле + _close_and_put_done → ни одного ('reasoning', …) после ('done', …) в Run.q на 1000 повторах, поздний _emit_reasoning → False и reasoning-late-drop; при зависшем SELECT conn.interrupt() вызывается до финального join, поток завершён, соединение закрыто",
    "AO-04": "T-LIFE/C-MULT: ≤1 одновременного SQLite-соединения на активный ход при любом числе последовательных переподключений; каждый connect парный close в finally; stop или выключение флага во время опроса → поток завершён и соединение закрыто; 20 ходов → active_count и active_connections_after_done == 0; stop во время зависшего SELECT → conn.interrupt() из другого потока, OperationalError interrupted не считается отказом breaker'а, соединение закрыто в finally",
    "AO-05": "H-CPU/S-HERD: один SELECT на опрос, LIMIT 16 и BLOB ≤256 KiB (больше → NULL); огибающая прихода SELECT на ход N(Δt) ≤ 3 + 2·Δt на любом окне Δt (всплеск ≤3, устойчиво ≤2.0/с, включая drain с шагом 0.05 с) на FakeClock; неизменная пара (blob_len, sha256) → парсер не вызывается; тот же размер с другим содержимым → 1 вызов; stop_event проверяется перед каждой строкой и каждые 64 wire-тега (stop посреди 16 строк → 0 дальнейших вызовов парсера); dynamic_config.json парсится один раз при неизменном stat в пределах TTL 1.0 с; выданное мышление хода ≤ MAX_REASONING_BYTES_PER_TURN = 2 MiB (сверх — reasoning-cap, 0 дальнейших reasoning в Run.q)",
    "AO-06": "O-EXIT: ровно одна строка done с обязательными полями на каждой ветке выхода _run_once (done, agy_error, pump_error, client_gone, timeout, no slot, launcher_unavailable); /health содержит аддитивные sqlite_reasoning_mode ∈ {live, shadow, off, breaker_open}, sqlite_breaker_state ∈ {closed, open, half_open}, sqlite_divergence_count:int, sqlite_drain_deadline_count:int (растёт при divergence/window_complete с pending_steps > 0), существующие поля неизменны",
    "AO-07": "Путь БД: cid с ../, /, пустой или не по regex → connect не вызывается; resolved parent == CONV_DIR",
    "AO-08": "Только чтение и якорь resume: каждый connect — file:…?mode=ro с uri=True, PRAGMA query_only=ON и busy_timeout=50; подстроки immutable нет ни в одном URI; ошибка mode=ro → транскрипт без второй формы URI; владение cid: два одновременных запроса с одним cid (горячая сессия или явный conversation_id) → второй получает свежий cid без --resume (cid-busy-fresh), _active_cid_owners[cid] снимается только своим turn_id; resumed с неудачным pre-spawn SQLite (нет .db / sqlite3.Error) → turn_mode=OFF, SELECT по steps за ход не выполняется ни разу, мышление из транскрипта с pre-spawn водяным знаком; фикстура с зависшей status=8 строкой упавшего прошлого хода и шагами status=3 + внешний writer — 0 переотданных исторических шагов; base_idx = max(t_max, db_max) + 1; явных BEGIN нет",
    "AO-09": "Kill-switch активного хода: запись false в dynamic_config.json, удаление файла или битый JSON посреди хода → на FakeClock SELECT прекращаются и соединение закрыто ≤1.30 с (TTL 1.0 + срез 0.25 + busy_timeout 0.05) при SQLITE_POLL_S = 0.5 и 2.0 (гейт ≤2.0 с, контракт ≤5.0 с), ход завершается done с мышлением из транскрипта; env AGY_SQLITE_REASONING_ENABLED=0 → connect не вызывается",
    "AO-10": "Compat canary и turn_mode: неизвестная или изменившаяся (st_mtime_ns, st_size) бинаря agy → SHADOW: 0 SQLite-эмитов клиенту, observed_* ведётся, delivered_len == 0, финал транскрипта выдан клиенту целиком (100 % final_thinking); observed_sha256 == sha256(final_thinking) → compat LIVE для следующих ходов; turn_mode зафиксирован на старте: ход A в SHADOW остаётся SHADOW после промоута compat ходом B посреди A (0 SQLite-эмитов A после промоута), ход C, начатый после промоута, — LIVE; несовпадение observed в SHADOW или divergence/sqlite-live-loss в LIVE → SHADOW и отказ breaker'а; семантически несовместимый, но синтаксически валидный 20.3 не уходит клиенту",
    "AO-11": "Handler._execute: последовательность result(status=ERROR) → reasoning → reasoning → done: все чанки попадают в out['reasoning'] и delivered['reasoning_chars'] до возврата в _run_once; повтор хода не запускается, кадр ошибки после мышления",
    "AO-12": "Дедупликация и divergence: 'abc'→'abX…' в SQLite → sqlite_snapshot_divergence, diverged=True, 0 последующих эмитов шага из SQLite и транскрипта, SQLite-опрос хода закрыт, шаги > idx из транскрипта; отдано 'abc', финал транскрипта 'abXde' → sqlite_transcript_divergence, клиент получил ровно 'abc' (не 'abcde'), 0 повторных и 0 склеенных символов; снимок того же размера с другим текстом распознан как divergence; укороченный снимок с совпадающим префиксом ничего не выдаёт; финал транскрипта с совпавшим префиксом → только хвост, склейка побайтово равна final_thinking (AC-004 при ASM-001); breaker consecutive_failures и sqlite_divergence_count +1; seen ≤128 с вытеснением только finalized ниже poll_watermark; разрезанный UTF-8 символ (TC-04) выдаётся целиком без U+FFFD"
  },
  "semantic_checks": {
    "canonical_hl_field_set": "46/46: ключи required_hl_env_fields == field_units == field_sources == таблица SSoT §3.0 (распарсена из architecture.md)",
    "memory_closure": "1·112+32=144 ≤ 409.6 MiB; Run.q + out['reasoning'] ≤4 MiB на ход (≤32 MiB на 8 ходов) внутри Mem_rss_worker_max 112",
    "stop_codes": "21 канонических кодов в resilience_gates ({'PASS': 16, 'N/A': 5}) + T-LIFE/O-EXIT/M-SEM; status_protocol_examples.stop_codes: 21 ARCH_STOP_* биективно",
    "legacy_antipatterns": "21 ключ в порядке эталонной схемы",
    "verification_owner": "{'Verifier': 6, 'Teamlead': 6}: Verifier — VER-001..VER-005, VER-009; Teamlead — VER-006, VER-007, VER-008, VER-010, VER-011, VER-012; Coder не владеет ни одной проверкой",
    "decisions": "6 решений, все two-way, ≥2 альтернатив, approval_required=false",
    "evidence_refs": "77 EVD (56 фактов аналитика F-01..F-56 + 21 собственное архитектора, включая EVD-073..075 ревизии R1 и EVD-076..077 ревизии R2); все verification_ids/evidence_ids разрешаются",
    "na_proof": "каждый N/A несёт git diff (пустой на Stage 2), fingerprint и транзитивный граф вызовов",
    "schema_vs_semantics": "Установленный validate_architecture_packet.py не проверяет high_load_envelope/resilience_gates/legacy/status_protocol — эти проверки выполнены сборочным скриптом архитектора; ни схема, ни дизайн-проверки не доказывают runtime PASS",
    "quality_gates": "VER-001..VER-005 с запиненными ruff 0.17.3 / basedpyright 1.40.2 / pytest 9.0.3 требуют 0 ошибок/0 падений; basedpyright — 0 ошибок (список EVD-076) и 0 новых предупреждений; VER-007 — 51 id и ≥1 assert в каждой функции; VER-008 — sha256 5 замороженных analysis-файлов; VER-010 — исполняемый L2-харнесс; VER-012 — agy-набор на /usr/bin/python3 0 failures + pre-MR checkpoint Q-005 для полного набора",
    "timing_budget": "EOF→stop: дефолт 0.05+0.05+0.35+0.15+0.05 = 0.65 с; максимумы 0.05+0.05+0.50+0.20+0.05 = 0.85 с ≤ 1.0 с; kill-switch активного хода 1.0+0.25+0.05 = 1.30 с ≤ 5.0 с на всём SQLITE_POLL_S ∈ [0.5, 2.0]"
  },
  "handoff_state": {
    "next_role": "Orchestrator → ARCH_PANEL R2 (downstream Архитектурный Совет, route-manifest downstream_panel=true) → Coder только после ARCH_GATE_PASS",
    "coder_must_read": [
      "architecture/architecture-packet.json (AD-001..AD-006 details, AO-01..AO-12, VER-001..VER-012)",
      "analysis/agy-realtime-reasoning/handoff-qa.md (TC-кейсы)",
      "teamlead/verification-surface.json",
      "panel/arch/r1/seats/{1,2,3}/verdict.md (EVD-075)",
      "EVD-076 (12 baseline-ошибок basedpyright и исправления), EVD-077 (находки ARCH_PANEL R2 и sha256 замороженных входов)"
    ],
    "red_green": "Регрессионные тесты TC/AO-01..AO-12 пишутся до фикса и красные на e00da06 (VER-007 MISSING на baseline); форматирование server.py — отдельный механический коммит до фич-коммитов"
  }
}

```

### 3.2. `plans/architect-01.json`
```json
{
  "schema_version": "1.0",
  "run_id": "analyst-teamlead-agy-reasoning-20261029",
  "task_id": "agy-realtime-reasoning",
  "role": "architect",
  "iteration": 3,
  "plan_kind": "full",
  "goal": "Точечная ревизия Architecture Packet agy-realtime-reasoning по находкам ARCH_PANEL R2 (Seat 1 F-001..F-012, Seat 2 F-001..F-008) с сохранением одобренного Seat 3 и без изменения продуктового worktree",
  "objective": "Architecture Packet S2 (python-aisdlc-gcge), закрывающий R2: полное окно drain 0.35 с без эвристического раннего выхода и outcome=window_complete; заморозка выдачи шага при divergence (0 склеенных символов, AC-004 при ASM-001 / AC-005 при нарушении); turn_mode на ход и раздельные observed/delivered; _active_cid_owners и обязательный двойной pre-spawn якорь resumed (иначе OFF); LIMIT 16, BLOB ≤256 KiB, stop-проверки и conn.interrupt(); run._emit_lock; kill-switch 1.30 с ≤ 5.0 с; probe_gen и определение cold-open; 2 MiB на ход, огибающая N(Δt) ≤ 3 + 2·Δt, поля /health, VER-007 с assert, VER-008 с sha256, исполняемый VER-010, VER-012 на /usr/bin/python3 и EVD-076",
  "scope_paths": [
    ".ai-team/runs/analyst-teamlead-agy-reasoning-20261029/architecture/architecture-packet.json",
    ".ai-team/runs/analyst-teamlead-agy-reasoning-20261029/plans/architect-01.json",
    "bridges/agy-bridge/server.py (только чтение)",
    "tests/test_agy_bridge_resilience.py (только чтение)"
  ],
  "inputs_read": [
    "бриф оркестратора architect R1-fix (обязательные исправления 1–6, в задаче)",
    ".ai-team/runs/analyst-teamlead-agy-reasoning-20261029/panel/arch/r1/seats/{1,2,3}/verdict.md и panel/arch/r1/manifest.json",
    ".ai-team/runs/analyst-teamlead-agy-reasoning-20261029/arch-panel/cycle-1/brief-review/*/verdict-v1.json",
    ".ai-team/runs/analyst-teamlead-agy-reasoning-20261029/architecture/architecture-packet.json (R1, sha256 f0471a61…)",
    ".ai-team/runs/analyst-teamlead-agy-reasoning-20261029/teamlead/verification-surface.json (пороги ruff_check_errors=0, basedpyright_errors=0)",
    "analysis/agy-realtime-reasoning/evidence-ledger.md (F-25, F-30..F-33, F-52, F-56) и handoff-qa.md (TC-04, TC-05, TC-20..TC-33, TC-60..TC-63, TC-91..TC-93)",
    "bridges/agy-bridge/server.py:104,130,477-515,807-868,981-1101,1129-1175,1370-1409 (TRANSCRIPT_GRACE_S, _in_flight_cids, стор, _pump, _execute result ERROR, _run_once, sess_key)",
    "pyrightconfig.json, ruff.toml",
    "~/Мой диск/skils/ai-sdlc/universal/orchestrate-coder-reviewer-summarizer/scripts/validate_role_plan.py",
    "~/Мой диск/skils/ai-sdlc/universal/architect-software-product/scripts/validate_architecture_packet.py",
    "бриф оркестратора architect R3-fix (8 обязательных хирургических правок; находки ARCH_PANEL R2 Seat 1 F-001..F-012, Seat 2 F-001..F-008; Seat 3 PASS 6/6)",
    "~/work/tmp/agy-arch-r2/v4.json (вывод basedpyright 1.40.2 на e00da06: 12 ошибок)",
    "bridges/agy-bridge/server.py:230-284,828-834,925-930,1355-1388,1526-1546 и tests/test_agy_bridge_resilience.py:160-168,545-560 (места 12 ошибок, только чтение)",
    "analysis/agy-realtime-reasoning/{research-plan,evidence-ledger,open-questions,handoff-architect,handoff-qa}.md (только shasum -a 256)"
  ],
  "stop_conditions": [
    "Любая запись вне architecture/architecture-packet.json и plans/architect-01.json запрещена; worktree_fingerprint обязан остаться aed3274571859b39f08788443955470300be30a9dfd8ea5d0e994001433a0bbb",
    "Факт о схеме/коде, не подтверждённый ledger или чтением server.py, в packet не попадает; при конфликте брифа с фактом приоритет у факта с записью в deviations",
    "FAIL любого валидатора или неустранённая находка R1 запрещают handoff; секреты и текст мышления в артефакты не пишутся"
  ],
  "steps": [
    {
      "id": "RP-01",
      "kind": "inspect",
      "action": "Сопоставить находки трёх мест ARCH_PANEL R1 и шесть пунктов брифа оркестратора с якорями packet (AD/QA/VER/RISK/HL-ENV/гейты); R3: сопоставить 8 пунктов брифа R3 (ARCH_PANEL R2 Seat 1 F-001..F-012, Seat 2 F-001..F-008) с якорями packet",
      "expected_evidence": "Карта находка → раздел packet для Seat 1 #1..#5, Seat 2 #1..#3, Seat 3 F-001..F-010",
      "status": "DONE",
      "actual_evidence": "Прочитаны panel/arch/r1/seats/{1,2,3}/verdict.md (все NEEDS WORK) и brief-review verdict-v1.json; карта: drain/join/_execute → AD-002/AD-003, plain-сессии → AD-004, query/UTF-8/dedup/seen/immutable/compat → AD-001, float/breaker/lock → AD-005, kill-switch → AD-006, AO-04/порог 5 с/пины/риски → VER/QA/RISK, F-009 → VER-001..005/012. F-010 (жеребьёвка) — зона оркестратора. Зафиксировано как EVD-075. R3: Карта: F-001 → AD-002.drain_loop/AO-03; F-002/S2 F-001 → AD-001.dedup_and_emit/AO-12/REQ-003/ASM-001; F-003 → AD-001.compat/seen_state/QA-012/AO-10; F-004/F-005 → AD-001.watermark_resume/BND-005/AD-004/AO-08; F-006/F-007 → AD-001.query/parser, AD-002.pump_order/join_before_done/late_events; F-008/S2 F-003 → AD-006/QA-010/AO-09; F-009/S2 F-002 → AD-005/AO-01/R-BULK-I3; F-010..F-012/S2 F-004..F-007 → HL-ENV, S-HERD-I1, CD-003, REQ-010, VER-007/008/010/012, EVD-076."
    },
    {
      "id": "RP-02",
      "kind": "inspect",
      "action": "Перепроверить факты, на которые опираются исправления: схему SQLite F-31, бинарь agy F-25, места server.py и baseline запиненных гейтов на e00da06; R3: снять список 12 ошибок basedpyright с контекстом кода и sha256 замороженных analysis-файлов",
      "expected_evidence": "Подтверждённые имена таблицы/колонок, строки server.py и вывод dry-run VER-001..VER-005",
      "status": "DONE",
      "actual_evidence": "F-31: таблица steps(idx, step_type, status, step_payload) — имена trajectory_steps/step_idx из брифа сопоставлены фактической схеме. F-25: ~/.local/bin/agy.real 1.4.9. server.py: result ERROR → немедленный выход _execute L1077-1085, _in_flight_cids L130/494, TRANSCRIPT_GRACE_S L104. Dry-run (EVD-073/074): ruff@0.17.3 check rc=0; format --check rc=1 (не отформатирован только server.py); pytest==9.0.3 22 passed; unittest discover на /usr/bin/python3 22 OK; basedpyright@1.40.2 errors 12, warnings 868. R3: ~/work/tmp/agy-arch-r2/v4.json — 12 ошибок (server.py 9: 259×2, 282, 832, 928, 1371, 1385, 1529, 1544; tests 3: 165×2, 557), места прочитаны, исправления — EVD-076; sha256 5 analysis/*.md сняты и проверены dry-run'ом VER-008 (SHA_OK) — EVD-077."
    },
    {
      "id": "RP-03",
      "kind": "decide",
      "action": "Переписать AD-001 и AD-002: mode=ro без immutable, водяной знак resumed под per-cid замком, SELECT с BLOB ≤1 MiB и статусами 8/3, UTF-8 trim, seen ≤128 с sha256-префиксом, контракт divergence, compat canary, drain 0.15/0.50 + join 0.15 и дочитывание _execute до done; R3: заморозка шага при divergence, turn_mode и observed/delivered, _active_cid_owners и двойной якорь resumed (иначе OFF), LIMIT 16/256 KiB/interrupt, 2 MiB, /health",
      "expected_evidence": "Обновлённые details AD-001/AD-002 с бюджетом EOF→stop ≤1.0 с на всех разрешённых настройках",
      "status": "DONE",
      "actual_evidence": "AD-001.details: enablement (проверка на каждой итерации), open, query, watermark_resume, parser, seen_state, dedup_and_emit, compat, observability. AD-002.details: pump_order (proc.wait ≤0.05), drain_loop (ранний выход только при a∧b), join_before_done, execute_drain, late_events, budget: дефолт 0.80 с, максимумы 0.95 с ≤ 1.0 с. R3: AD-001.details enablement/open/query/watermark_resume/parser/seen_state/dedup_and_emit/compat/observability переписаны, добавлен memory_bounds; AD-002 pump_order (_emit_lock, _close_and_put_done), drain_loop (окно 0.35 с, outcome=window_complete), join_before_done (interrupt), budget: EOF→stop 0.65/0.85 с."
    },
    {
      "id": "RP-04",
      "kind": "decide",
      "action": "Переписать AD-003..AD-006: учёт reasoning после result ERROR, стор только для агентных запросов, целочисленные retry/poll бакеты, FSM breaker K=3/30 с с атомарной пробой под одним замком, fail-closed флаг с кэшем 5 с и kill-switch активного хода; R3: probe_gen и определение cold-open в AD-005, TTL 1.0 с + срезы 0.25 с в AD-006, владение cid в AD-004",
      "expected_evidence": "AD-003..AD-006 с альтернативами R1 как отвергнутыми и confirmation на AO-01..AO-12",
      "status": "DONE",
      "actual_evidence": "AD-003 + AO-11; AD-004 use_session_store=(tools_count>0) and not is_bg; AD-005: 30/+2/−10 десятых, per-turn bucket 30/20 в с/10, FSM CLOSED→OPEN→HALF_OPEN с тремя исходами пробы и автоистечением 60 с, _sqlite_guard_lock и тестовый reset; AD-006: env AGY_SQLITE_REASONING_ENABLED (аварийное выключение) AND dynamic_config.json, сброс в False на любой ошибке. Все решения остаются two-way. R3: AD-005 — огибающая N(Δt) ≤ 3 + 2·Δt, сбойный ход только DatabaseError/OperationalError после успешного SELECT/схема/divergence, probe_gen с no-op устаревшей пробы; AD-006 — 1.0 + 0.25 + 0.05 = 1.30 с ≤ 5.0 с; AD-004 — _active_cid_owners; альтернативы R2 записаны отвергнутыми."
    },
    {
      "id": "RP-05",
      "kind": "decide",
      "action": "Перестроить verification surface VER-001..VER-012 с запиненными ruff/basedpyright/pytest и гейтами 0 ошибок/0 падений, пересчитать HL-ENV, resilience gates, риски RISK-014..018 и оракулы AO-01..AO-12; R3: VER-007 (assert в AST), VER-008 (sha256), VER-010 (kind=command), VER-012 (/usr/bin/python3 + checkpoint Q-005), HL-ENV 112 MiB, RISK-019/020",
      "expected_evidence": "Гейты Teamlead не ослаблены, неравенства памяти/опроса/бюджета пересчитаны, новые риски и оракулы заведены",
      "status": "DONE",
      "actual_evidence": "VER-001 ruff check, VER-002 format --check, VER-003 pytest, VER-004 basedpyright errorCount==0 и 0 новых предупреждений против baseline e00da06, VER-005 unittest 3.9.6 + pytest, VER-012 полный набор 0 failed (3 baseline-красных → BLOCKED владельцу); VER-007 = 51 id; VER-009 запрещает подстроку immutable. Память 1·112+32=144 ≤ 409.6 MiB; S-HERD-I1 2.0 ≤ 4.0 на всём SQLITE_POLL_S ∈ [0.5, 2.0]; R-BULK-I1 4.0 ≤ 540 с; C-MULT-I1 «≤1 одновременного соединения на ход». QA-001/QA-010/QA-012, RISK-014..018, BND-007, BD-005. R3: Скрипты правок ~/work/tmp/agy-arch-r3/update_packet_r3.py и update_packet_r3b.py (якорные замены с assert), бэкап R2 packet-r2.json sha256 e66a24b1…; контрольный поиск устаревших значений: 0 вхождений LIMIT 128, outcome=deadline, _reasoning_cids, кэш 5.0, 1·96; оставшиеся «≤5.0 с» — L3 S1 первый чанк и контракт QA-010. Бюджеты: EOF→stop 0.65/0.85 с, kill-switch 1.30 с, память 1·112+32=144 ≤ 409.6 MiB (HL-ENV-01 гармонизирован); VER-007 dry-run на baseline — MISSING по 51 id (red до фикса)."
    },
    {
      "id": "RP-06",
      "kind": "report",
      "action": "Записать architecture-packet.json, связать sha256 этого плана и прогнать validate_role_plan.py after и validate_architecture_packet.py approved",
      "expected_evidence": "PASS обоих валидаторов (rc=0) и согласованный role_plan.sha256",
      "status": "DONE",
      "actual_evidence": "Packet перезаписан скриптом вне репозитория (~/work/tmp/agy-arch-r2/update_packet.py), R1-копии сохранены там же; оба валидатора запущены с фактической сигнатурой (позиционный путь + --phase), результат и sha256 передаются в ответе оркестратору. R3: role_plan.sha256 пересвязан после записи плана; validate_role_plan.py --phase after и validate_architecture_packet.py --phase approved перезапущены, результат в ответе."
    },
    {
      "id": "RP-07",
      "kind": "report",
      "action": "Сверить fingerprint продуктового worktree с fingerprints/architect-before.json и git status, передать хеши артефактов оркестратору",
      "expected_evidence": "WORKTREE_UNCHANGED aed32745…, записи только в двух target-файлах run_dir",
      "status": "DONE",
      "actual_evidence": "worktree_fingerprint.py --compare fingerprints/architect-before.json выполнен после записи артефактов; git status показывает только неотслеживаемые .ai-team/runs/… и analysis/agy-realtime-reasoning/ как до работы. Результат сравнения передан в ответе. R3: повторно — git status и fingerprints/architect-before.json не изменялись; записаны только два target-файла."
    }
  ],
  "deviations": [
    "Команды валидаторов из брифа (--plan/--packet/--role) не соответствуют argparse установленных скриптов (позиционный путь + --phase, rc=2 на неизвестных аргументах); запуск выполнен с фактической сигнатурой, role=architect проверяется внутри JSON. Валидаторы не менялись.",
    "Бриф называет таблицу trajectory_steps и колонку step_idx; фактическая схема agy 1.4.9 (F-31) — steps(idx, step_type, status, step_payload). В AD-001.query использованы фактические имена и сохранён фильтр step_type = 15; семантика запроса брифа (BLOB ≤1 MiB в SQL, статусы 8 → 8/3 после якоря, LIMIT 128) сохранена.",
    "Пункт брифа «token bucket 30/20/10 десятых на опрос» и находка Seat 1 #5 (float retry budget) — разные механизмы: оба реализованы в целых десятых — процессный retry budget 30/+2/−10 (Seat 1) и per-turn bucket SQLite-опроса 30/+20 в с/−10 (бриф), иначе один процессный бакет 2 SELECT/с душил бы 8 параллельных ходов.",
    "VER-004: «0 errors / 0 warnings» для basedpyright реализован как errorCount == 0 (порог Teamlead basedpyright_errors=0) и 0 новых предупреждений против baseline e00da06 по мультимножеству (файл, правило, сообщение). Буквальный 0 предупреждений потребовал бы переписать 868 унаследованных предупреждений target-файлов (EVD-074) — это новый гейт, которого нет в порогах Teamlead, и расширение scope, против которого предупреждает F-009. Выбор вынесен владельцу (Q-005).",
    "Полный набор tests/ не удалён из поверхности: перенесён в VER-012 с гейтом 0 failed; ровно 3 baseline-красных F-56 дают BLOCKED: OWNER_DECISION_REQUIRED, а не PASS (F-009 — без самостоятельного допуска).",
    "Seat 3 F-010 (пересчёт SEED/ранжирования панели) — зона оркестратора и manifest панели, не Architecture Packet; в packet не исправлялся.",
    "Для F-005 выбран семантический canary по идентичности бинаря agy (st_mtime_ns, st_size, F-25) вместо проверки строки версии: запуск agy --version на каждом ходе добавил бы подпроцесс в горячий путь.",
    "independent_review NOT_REQUIRED (S2) и approval APPROVED без human decision_ids (все AD two-way): это пакет-кандидат для ARCH_PANEL R2, не вердикт Совета и не ARCH_GATE_PASS.",
    "R3: бриф называет 3 legacy-теста Q-005 «claude_bridge/start_stop»; фактические имена по EVD-056 — test_b_guard, test_muse_bridge_killpg, test_rpc_rework; в packet использованы фактические.",
    "R3: VER-012 переведён на /usr/bin/python3 unittest по agy-набору (по брифу); Full Suite Gate не удалён — перенесён в pre-MR rollout checkpoint Q-005 с тем же правилом «ровно 3 F-56 = BLOCKED, иначе FAIL».",
    "R3: END_TURN/TURN_COMPLETE как маркеры конца хода в transcript_full.jsonl фактами F-29/F-33 для agy 1.4.9 не подтверждены; в AD-002 они приняты условно (если наблюдаются), рабочий путь досрочного выхода — PLANNER_RESPONSE с непустым финальным ответом + 0 строк status=8 на двух тиках.",
    "R3: «join(timeout=0.15)» брифа реализован как conn.interrupt() по истечении окна drain перед финальным join(JOIN_TIMEOUT_S), а не перед каждым join, — иначе прерывался бы последний легальный SELECT окна.",
    "R3: VER-010 стал kind=command (pytest 9.0.3 -k \"tc93 or l2_harness\" + unittest на /usr/bin/python3); тесты tc93/l2_harness в обязательные 51 id VER-007 не добавлены (бриф фиксирует 51), их наличие гарантирует rc 5 pytest при пустом выборе.",
    "R3: DRAIN_WINDOW_S=0.35 (окно) и DRAIN_MAX_S=0.50 (жёсткая граница окна) трактуются как дефолт и верхний предел одного параметра AGY_BRIDGE_TRANSCRIPT_GRACE; бюджет EOF→stop пересчитан: 0.65 с дефолт, 0.85 с максимум."
  ]
}

```

### 3.3. `teamlead/verification-surface.json`
```json
{
  "schema": "verification-surface/v1",
  "created_at_utc": "2026-10-28T23:00:42.258669+00:00",
  "run_id": "analyst-teamlead-agy-reasoning-20261029",
  "risk_level": "medium",
  "criticality": "S2",
  "base_sha": "e00da0621fc95f7c63cd1565f4a5d1fd490c8d66",
  "worktree_fingerprint_before_coder": null,
  "worktree_file_count_before_coder": 12609,
  "runtime_toolchain": {
    "python3": "Python 3.14.7",
    "sys_python3": "Python 3.9.6",
    "uv": "uv 0.12.19 (bea138450 2026-09-24 aarch64-apple-darwin)",
    "ruff": "ruff (via uvx ruff)",
    "basedpyright": "basedpyright (via uvx basedpyright)",
    "agy": "agy 1.4.9 (~/.gemini/antigravity-cli/releases/1.4.9/agy)"
  },
  "container_image_digest": null,
  "lock_files": {},
  "config_and_ci_files": {
    "ruff.toml": "571ccfac063812ed2b0b7e134f3b3d227cc016c7f88bdbb2b8ccfbed1e8703b3",
    "bridges/agy-bridge/fleet.json": "4afce0e2ed3a8c381235fca73ea595e6ffb1aba27708c6aa69e4bfc431f3c6ad",
    "bridges/agy-bridge/start.sh": "ac4f2debc9bc930414608bf254a30593215d2561a1357a5552836c6fed8c003c"
  },
  "mandatory_ci_jobs": [],
  "oracle_test_hashes_before_coder": {
    "tests/bridge_testlib.py": "6a9b1131097b809dc48eb31c886f68c6eff4f5ed02603d73ce595f73f7064917",
    "tests/context_testlib.py": "ec4485b5c52c3ff4bd02d96b43f75d39f8e76132ec4fe0df5b847981bbccf758",
    "tests/fake_droid.py": "947bd4f65dddeb3a563c83be85115921f70c7f2528687a050903f72400d4c4af",
    "tests/rpc_testlib.py": "221d6b502b64b3cf503dc34759b0f4d7eae632f507b9e1c3dfaa5a2a876b7933",
    "tests/test_adaptive_idle_watchdog.py": "04ed486e7cf7c62cb4edd2e04ee34504cd61e710ce91f47d4edfd3c6c5f9f1db",
    "tests/test_agy_bridge_resilience.py": "e96c2871a51859e235b99236c8ade5712d6bd40db200bad5f3115b96d9781119",
    "tests/test_b_guard.py": "ec1ec30ed82353ba379c0ed0db860b9877de6a93849f9a4f764ed53703e351ed",
    "tests/test_backend_contract.py": "89d281bdd850f472cf1ee0888b4c60fa27e75c970a85553ae41a8f3128ab3abb",
    "tests/test_bridge_http.py": "b36c4987f41330eaadd9a4256bce4c868ae0770259ec8be5342da78d64ec1383",
    "tests/test_bridge_strict.py": "5ea51505c881b7a4022e51e26085b7adeaad45d7798b34768c4922387b4232cb",
    "tests/test_cache_usage.py": "5c53254f4d890f3e1281f882847757ef589761ce85e3de38d3b2e61c867420b3",
    "tests/test_context_resilience.py": "ee2b521278bea30881d5056443d90dd0dd873b321b6bf7d4ad2e75442a14bc87",
    "tests/test_context_resilience_failures.py": "978cf1362f7e88648758abb51c689cd85a6a78fa2903e593ef051cecc4bcb789",
    "tests/test_context_resilience_protocols.py": "3d77df00075bde4f359335576b7cd628b5692fd791e401d44b75b4f4527bd4fa",
    "tests/test_context_resilience_resident.py": "caaaf1e7a3e9f18f25a4b5ce09d6f862f622007d9e9638a06b65d86d18fb9d09",
    "tests/test_context_resilience_routing.py": "6c0bcd10c13f6299002982d43ab4e4ce57702af7d6472fcda8c6988ac6f3acd6",
    "tests/test_context_resilience_switching.py": "0c30e4f49efeaec87e5606322bb650bc95b1ae1c419c1c4242fae92380de42e0",
    "tests/test_cycle4_tools.py": "64c9c848ed9f25c9cde5414046b69753ba661e4f64e39b84db2b4ac00758713d",
    "tests/test_cycle5_rework.py": "88bba572ac4cb3f6d862c283ed9bc84d19f22c7068dc07825fe33acc3014194b",
    "tests/test_cycle6_rework.py": "2db840faa7348a057184e2b7800e08ede02c0f6df65595fae7331861e0fe1502",
    "tests/test_detached_turn_execution.py": "4e74fc98568e8e54347e303630a057435e0bc7ee9baf60dce6b4ec2ef0b30313",
    "tests/test_dsh_profile_config.py": "5a6a5a5a10b007e10735a02cca207dcc0f98414d228f2c82501f551c025a045b",
    "tests/test_fleet_v3.py": "26f8cab589f599aba7e66b028c70984c87036d0536f73128f5d18c5fa775c60e",
    "tests/test_framing_strict.py": "dcea631c22f481b841588bd3beefbc100df10ab25485cffa86d53ae5569f3305",
    "tests/test_graceful_shutdown_drain.py": "3a5ad0050b357b2b6a0b6d786192610f7660459bcd66d6a684589f80e3aa5860",
    "tests/test_hub_integration.py": "389fbcd9e1ab0cf25f854021f819302da548efcc5790c970d5a428df3d4e8b61",
    "tests/test_images_strict.py": "d9f63c9b4edad28278e98d60957cf7bfd354f870f515d921b632713c56bbb676",
    "tests/test_launch_env.py": "e7103c796f37bad9eab38d0a00db7a9acbc6f9d27198a143108094c3994fbce6",
    "tests/test_live_stream.py": "96fc008050cc260357cd582c60d3a6683bf94887b53b2adc3e0f8234eee69a37",
    "tests/test_muse_adapter.py": "f0f68113f86b5d995c3ef3aae225eb0a3c9b57088e5f35c3c57aeb00af41cf5b",
    "tests/test_muse_bridge_killpg.py": "05457d09213e0f965ed6fcdc238c628cd01be359154c5fb54b249ede5db01400",
    "tests/test_rpc_core.py": "0743cab97bb36610b970984d334a096ba146f8eb6add7faa38e989c4c7f34cda",
    "tests/test_rpc_cycle3.py": "95e54124c4e42e7d0d30d8ecb45eab68412e60b8771a1294a81ea286e3c88110",
    "tests/test_rpc_cycle4.py": "4c7cbc9cb43352fe35b632a466d0de889fdbf52c1bb596ac1c59fa3650e8738e",
    "tests/test_rpc_lifecycle.py": "c828843a100ae50408913d0ba1533736513f05aa4ea01b8dcb6b8ed9167d7171",
    "tests/test_rpc_rework.py": "1195cf1e0e8dfed253d12c1ef329252a86f6e743c85bc77fd9ee133d96f0a7b1",
    "tests/test_run_integration.py": "232998884333884d1fadc2d612f50b0ae1724066f0194fb5b264573901209628",
    "tests/test_tool_parser.py": "75418bbb4981d912138c68c88459f8b31a742122093b8d568b4a567dbecd9dca",
    "tests/test_turn_cancel_and_gap.py": "44238612a9b68b30fb75b2c92894e9cf4a366c2f369234b161745690bf588bac"
  },
  "testdata_golden_snapshot_hashes": {},
  "coverage_and_quality_thresholds": {
    "ruff_check_errors": 0,
    "basedpyright_errors": 0,
    "agy_bridge_unit_tests_min_passed": 22
  },
  "baseline": {
    "command": "PYTHONPATH=. uvx pytest -q -p no:cacheprovider tests/test_agy_bridge_resilience.py",
    "exit_code": 0,
    "passed": 22,
    "subtests_passed": 19,
    "failed": 0
  },
  "allowed_envelope_changes": {
    "new_test_functions_allowed_in": [
      "tests/test_agy_bridge_resilience.py"
    ],
    "existing_oracle_assertions_mutable": false
  },
  "levels": {
    "L1": "Static & Unit: uvx ruff check bridges/agy-bridge/server.py tests/test_agy_bridge_resilience.py && uvx basedpyright bridges/agy-bridge/server.py tests/test_agy_bridge_resilience.py && PYTHONPATH=. uvx pytest -q -p no:cacheprovider tests/test_agy_bridge_resilience.py && PYTHONPATH=. /usr/bin/python3 -m unittest tests/test_agy_bridge_resilience.py",
    "L2": "Clean-room worktree verification with SHA-256 manifest (execution-evidence.md + evidence-manifest.sha256)",
    "L3": "Live heavy verification on 127.0.0.1:9887/v1/chat/completions after Council ACCEPT and MR merge"
  },
  "acceptance_manifest_ref": "analysis/agy-realtime-reasoning/handoff-qa.md",
  "architecture_packet_sha256": "f0471a6116bcea5831736dee36a85386c27f2758b7c41fdc354e96aa793229f4"
}

```

### 3.4. `analysis/agy-realtime-reasoning/handoff-architect.md`
```markdown
# Handoff to Architect: реалтайм-размышление `agy-bridge` (:9887) для `gemini-4-argon` (agy-realtime-reasoning)

Дата: 2026-10-29 (MSK). Автор: System Analyst (Stage 1, preset `analyst-teamlead`). Потребитель: `architect-software-product` (Stage 2, класс S2, вход в разработку только через ARCH_GATE).
Факты — `evidence-ledger.md` (`F-01..F-56`), вопросы — `open-questions.md` (`OPEN-01..OPEN-16`, блокеров нет), план — `research-plan.md`.
Архитектура и стек здесь не выбираются: варианты сравниваются по фактам, решение за Архитектором.

## 1. Постановка и цепочка корневых причин

Запрос владельца: при работе `gemini-4-argon` (agy 1.4.9) через `agy-bridge` в DSH фаза размышления длится 15-45+ с, и всё это время UI пуст
(«висит как будто бы не работает»). Нужно видеть размышление в реальном времени, по мере генерации.

Подтверждены четыре причины. RC-1 определяет, есть ли реалтайм вообще; RC-2..RC-4 ломают уже существующую выдачу мышления.

| Код | Причина | Ключевые факты |
|---|---|---|
| RC-1 | Нет live-источника мышления на текущем пути. Stdout `stream-json` 1.4.9 не сериализует `thinking`/`thinking_delta` и молчит всю фазу мышления; `transcript_full.jsonl`, который опрашивает `_TranscriptTail`, получает запись `PLANNER_RESPONSE` только после завершения шага. При этом SQLite `~/.gemini/antigravity-cli/conversations/<cid>.db` (таблица `steps`, `step_type=15`, `status=8`) обновляется каждые 1.5-5.1 с, а подполе 20.3 `step_payload` содержит накопленное мышление | F-27, F-28, F-29, F-30, F-32, F-33, F-01, F-02, F-44 |
| RC-2 | Гонка финального дренирования. `Run._pump` после EOF ждёт 0.05 с и ставит `("done")`; `_execute` выходит по `done` немедленно, а `_TranscriptTail` после `done_event` спит 0.4 с и только потом дочитывает файл; событие, положенное в очередь после выхода `_execute`, никто не читает. Запись последнего шага ложится в транскрипт на 90 мс позже `result`. В логе 6 из 28 одношаговых ходов argon завершились без единого куска мышления, 5 `tail-emit` не дошли до `reasoning-emit` | F-06, F-07, F-08, F-02, F-29, F-40, F-43 |
| RC-3 | `delivered = bool(text or tool_calls)` не учитывает уже отданное клиенту мышление (`tool_calls` всегда пуст). После сбоя на следующем шаге мост выполняет невидимый повтор поверх отданного `reasoning_content` либо шлёт кадр `error` после него | F-09, F-10, F-11, F-46, F-47 |
| RC-4 | `sess_key = (model_id, cwd, effort)` не различает основной агентный диалог (`tools>0`) и фоновый запрос DSH без инструментов (генерация заголовка: `tools=0`, промпт 0.5-0.7 KB, `effort_source=default`), которые приходят в ту же секунду. Фоновый запрос либо забирает горячую сессию основного диалога и дописывает в неё свой ход, либо стартует холодным и перезаписывает запись `_session_store` своим `cid`, после чего следующий ход основного диалога продолжает чужой разговор | F-12, F-13, F-14, F-41, F-42 |

Цепочка следствий: RC-1 даёт пустой экран на 15-45 с даже на здоровом ходе, а мышление приходит одним куском в конце (F-44); RC-2 иногда
теряет и этот кусок; RC-3 портит уже показанное мышление при сбое квоты (F-46); RC-4 подменяет контекст диалога при параллельном фоновом
запросе. Реалтайм-источник без исправления RC-2..RC-4 проблему владельца не закрывает.

## 2. As-is карта потока (каждая связь — факт)

```
DSH (stream:true) --HTTP SSE--> Handler.do_POST (:9887)                                       F-38, F-39
  do_POST: sess_key=(model,cwd,effort) -> _session_claim -> ctx                               F-12, F-13
  _serve_sse: 200 + role-chunk -> _run_once -> _execute                                       F-11
  _run_once: attempt 1..2, delivered=text/tool_calls, hot->cold fallback                      F-09, F-10
  Run: launcher agy-cli.sh --input-format/--output-format stream-json (new pgid)              F-05
    stdout NDJSON -> _pump: init->bind(cid); agent_response.text_delta->("text");
                            result->("result"); EOF -> sleep 0.05 -> ("done")                 F-06, F-18
    _TranscriptTail: poll 0.05 s transcript_full.jsonl -> PLANNER_RESPONSE.thinking
                     -> _reasoning_suffix -> ("reasoning"); on done: sleep 0.4 -> 1 read      F-01, F-02, F-03, F-04
  _execute: q.get(1.0) -> on_reasoning/on_text -> SSE delta; "done" -> return               F-07, F-08, F-17
  keepalive ": keepalive" каждые 15 с тишины (невидим в UI)                                   F-16, F-15
agy 1.4.9 (вне моста):
  stdout: init ... [тишина всю фазу мышления] ... agent_response text_delta ... result         F-27, F-28, F-29
  transcript_full.jsonl: запись шага только после DONE, +90 мс после result                   F-29, F-36
  conversations/<cid>.db (WAL): steps(idx, step_type=15, status=8 -> 3, step_payload 20.3)   F-30, F-31, F-32, F-34
```

Граница совместимости (факт): всё, что выше очереди `Run.q`, оперирует кортежами `("reasoning", текст)`, `("text", текст)`, `("done", ...)`
(F-03, F-06, F-07). Любой новый источник, сводимый к тем же кортежам, не требует правки SSE-кадрирования и контракта клиента.

## 3. Верифицируемые требования

Приоритет `MUST`/`SHOULD`; критерии `AC-*` — краткие измеримые формулировки (полная матрица проверок — `handoff-qa.md`).
Пороги отзывчивости — рабочие допущения из `open-questions.md` (вопрос о числовых целях), до ответа владельца.

| REQ | Приоритет | Требование | Факты | AC |
|---|---|---|---|---|
| REQ-001 | MUST | Мышление шага в фазе генерации (`step_type=15`, `status=8`) уходит клиенту дельтами `delta.reasoning_content` по мере роста подполя 20.3, до завершения шага | F-30, F-32, F-27, F-29 | AC-001: при фикстуре БД, в которой подполе 20.3 растёт каждые 1.5 с, клиент получает не меньше 2 чанков мышления до перехода шага в `status=3`; AC-002: задержка от записи снимка в БД до записи чанка в сокет не больше периода опроса плюс 0.5 с |
| REQ-002 | MUST | Разбор `step_payload` выполняется на стандартной библиотеке Python 3.9 (без новых зависимостей): поле 20 корневого сообщения, подполе 3 как UTF-8; неизвестные поля и wire types 0/1/2/5 пропускаются; усечённый или битый payload не роняет поток и не даёт исключения наружу | F-32, F-51, F-31 | AC-003: unit-набор парсера (многобайтовый varint, кириллица UTF-8, wire types 0/1/2/5, усечение на каждой позиции) проходит на `/usr/bin/python3` 3.9.6 без исключений |
| REQ-003 | MUST | Мышление каждого шага выдаётся ровно один раз при работе двух источников (SQLite и `transcript_full.jsonl`): общий ключ `idx == step_index`, итоговая склейка равна финальному `thinking` шага; непрефиксный снимок не повторяет уже отданный текст | F-33, F-04, F-03 | AC-004: склейка всех чанков `reasoning_content` хода побайтово равна конкатенации финальных `thinking` шагов из транскрипта; AC-005: фикстура с непрефиксным снимком не даёт повторной выдачи отданного префикса |
| REQ-004 | MUST | SQLite-источник вспомогательный и fail-open: отсутствие БД, ошибка открытия (включая `unable to open database file` на системном Python), блокировка, неизвестная схема или поля дают «изменений нет», ход продолжается, мышление идёт из транскрипта как сейчас | F-52, F-53, F-35, F-02, F-34 | AC-006: при недоступной, заблокированной или битой БД ход завершается `done` с тем же текстом и мышлением из транскрипта, что и без SQLite-источника |
| REQ-005 | MUST | Продолжение треда (`--conversation`, горячая сессия) не переотдаёт мышление шагов прошлых ходов ни из SQLite, ни из транскрипта | F-02, F-13, F-41 | AC-007: на фикстуре БД с шагами прошлого хода клиент получает мышление только шагов, появившихся после старта текущего хода |
| REQ-006 | MUST | Детерминированное финальное дренирование: мышление всех шагов хода (включая последний, записанный до 90 мс после `result` и после выхода процесса) выдаётся клиенту до чанка `finish_reason="stop"` и до возврата `out` из `_execute`; события источников после выхода `_execute` не теряются молча | F-06, F-07, F-08, F-29, F-43 | AC-008: фейковый agy, пишущий запись шага через 90 мс после `result` и выходящий сразу, в 100 из 100 прогонов даёт чанк мышления раньше `finish_reason="stop"` |
| REQ-007 | MUST | Финальное дренирование ограничено по времени и не продлевает ход больше 1.0 с сверх момента выхода процесса agy | F-02, F-07, F-15 | AC-009: время от EOF stdout фейкового agy до чанка `stop` не больше 1.0 с при молчащих источниках мышления |
| REQ-008 | MUST | Отданное клиенту мышление считается выдачей: после него невидимый повтор хода запрещён и уже отданные чанки не дублируются; финальный исход сбоя после мышления определяет Архитектор (кадр ошибки или частичный ответ) | F-09, F-10, F-11, F-47 | AC-010: фейковый agy, отдавший мышление и затем `result` со статусом ERROR, даёт ровно 1 запуск процесса и ни одного повторного чанка мышления |
| REQ-009 | MUST | Фоновые запросы без инструментов (генерация заголовка DSH) не занимают и не перезаписывают горячую сессию агентного диалога с инструментами той же модели, `cwd` и effort | F-12, F-13, F-42 | AC-011: последовательность «агентный ход, фоновый ход без tools, агентный ход» даёт третьему ходу `resume=1` с `cid` первого хода, а фоновый ход не получает `cid` первого хода |
| REQ-010 | MUST | Публичный контракт не меняется: эндпоинты `/health`, `/v1/models`, `/v1/chat/completions`, порт 9887, форма SSE-чанков (`role`-чанк, `reasoning_content`, `content`, `stop`, `usage`, кадр `error`, `[DONE]`), флаги запуска agy; текст мышления модели не модифицируется | F-11, F-05, F-19, F-39 | AC-012: 22 существующих теста `tests/test_agy_bridge_resilience.py` зелёные без правок; AC-013: склейка мышления без изменений текста модели |
| REQ-011 | MUST | SQLite-источник отключается переключателем окружения (имя и дефолт задаёт Архитектор); при выключенном переключателе поведение моста совпадает с as-is, исправления RC-2..RC-4 от переключателя не зависят | F-01, F-15, F-38 | AC-014: при выключенном переключателе ни одна БД `conversations/*.db` не открывается (проверка через подменённый `sqlite3.connect`) |
| REQ-012 | SHOULD | Наблюдаемость и бюджет: диагностические строки источника (cid-префикс, шаг, длина, задержка дренирования, ошибка открытия) без текста мышления и секретов; опрос БД не дороже 2% одного ядра на активный ход | F-40, F-51, F-55 | AC-015: в `bridge.err` после хода есть строки источника с полями cid, step, len и нет текста мышления; AC-016: CPU потока опроса на фикстуре 60 с не больше 2% ядра |

## 4. Сравнение вариантов (по фактам, без выбора)

### 4.1. Live-источник мышления (RC-1)

| Вариант | Фактура | Вердикт |
|---|---|---|
| A. Опрос SQLite `conversations/<cid>.db` (`mode=ro`) с парсером wire-формата, транскрипт остаётся источником для DONE-шагов и fallback | Подполе 20.3 растёт в `status=8` каждые 1.5-5.1 с (F-30); парсер на stdlib работает на реальных БД (F-32); финальный текст равен транскрипту (F-33); боевой Python 3.9.6 открывает WAL-БД с `mode=ro` только при живом пишущем соединении (F-52, F-53); схема внутренняя и меняется автоапдейтом (OPEN-03) | выполнимо с условиями: fail-open, переключатель, учёт окна после выхода agy |
| B. Только транскрипт (as-is) с более частым опросом | Запись шага появляется только после DONE (F-29); частота опроса не влияет на отсутствие данных во время генерации | невыполнимо для реалтайма |
| C. Поле `thinking_delta` в stdout `stream-json` | Поле объявлено в protobuf, но не сериализуется printmode 1.4.9 (F-28); в живом потоке его нет (F-27) | невыполнимо на 1.4.9 |
| D. Python SDK `google-antigravity` | Мысли только после блокирующего `send()` (F-37) | невыполнимо для реалтайма |
| E. Чтение БД через CLI `sqlite3` подпроцессом | `sqlite3 -readonly` дал ошибку 14 на той же БД (F-35); подпроцесс на каждый опрос | выполнимо с условиями, уступает A по стоимости |
| F. Локальный `agentapi` из `~/.gemini/antigravity-cli/bin/` | Не исследовался (OPEN-11) | нет данных |

Параметры варианта A для решения Архитектора (факты, не выбор):
- Путь БД: `~/.gemini/antigravity-cli/conversations/<cid>.db`, где `cid` — из события `init` (F-06, F-30). Каталог мозга — `~/.gemini/antigravity-cli/brain/<cid>/` (F-36).
- Выборка: таблица `steps`, колонки `idx`, `step_type`, `status`, `step_payload`, индексы по `status` и `step_type` (F-31). Размер payload строки — от 2 до 40 KB (F-32), шагов в длинном ходе — сотни (F-45).
- Ключ дедупликации: `idx` БД равен `step_index` транскрипта (F-33); существующая функция `_reasoning_suffix` ведёт виденный текст по строковому ключу (F-04).
- Открытие: Python 3.9.6 + `mode=ro` на закрытой WAL-БД падает, при открытом writer работает; `immutable=1` читает закрытую БД (F-52, F-53, OPEN-02, OPEN-12).
- Поток опроса может быть отдельным или частью `_TranscriptTail` (общая очередь `Run.q`, F-03).

### 4.2. Синхронизация финального дренирования (RC-2)

| Вариант | Фактура | Вердикт |
|---|---|---|
| A. `_pump` перед `("done")` вызывает синхронный финальный проход источников с ограничением времени | Сейчас `_pump` ставит `done` через 0.05 с после EOF (F-06); запись шага приходит через 90 мс после `result` (F-29) | выполнимо |
| B. `_execute` после `done` ждёт сигнал завершения потоков источников (join с таймаутом) и дочитывает очередь | `_execute` читает очередь до `done` и выходит (F-07); `Run.close` останавливает хвост (F-08) | выполнимо |
| C. Отдельный маркер конца источника в очереди и ожидание двух маркеров (`done` и конец источника) | Очередь уже несёт типизированные кортежи (F-03, F-06) | выполнимо |
| D. Увеличить паузу `_pump` до значения больше `TRANSCRIPT_GRACE_S` | Остаётся гонкой по времени, добавляет задержку всем ходам (F-02, F-06) | выполнимо с условиями, недетерминировано |

### 4.3. Учёт выдачи (RC-3)

| Вариант | Фактура | Вердикт |
|---|---|---|
| A. Добавить `out.get("reasoning")` в условие `delivered` | Поле `reasoning` уже возвращается из `_execute` (F-10) | выполнимо |
| B. Явный флаг «байты отданы клиенту», выставляемый колбэками `on_text`/`on_reasoning` | Колбэки централизованы в `_serve_sse` (F-11) | выполнимо |

### 4.4. Изоляция горячих сессий (RC-4)

| Вариант | Фактура | Вердикт |
|---|---|---|
| A. Признак наличия инструментов в `sess_key` | `tools_count` уже вычислен до ключа (F-12); фоновые запросы имеют `tools=0` (F-42) | выполнимо |
| B. Не занимать и не коммитить горячую сессию для запросов без инструментов с одним сообщением | `_session_claim`/`_session_commit` вызываются условно уже сейчас (F-12, F-13) | выполнимо |
| C. Ключ по признаку диалога (хеш первого user-сообщения или `prompt_cache_key`) | KB фиксирует отсутствие `prompt_cache_key` в ключе (F-12); поле в запросах DSH не исследовалось | выполнимо с условиями |

## 5. Инвентарь контрактов (as-is)

| Интерфейс | Протокол | Направление | Контракт | Лимиты | Режимы отказа |
|---|---|---|---|---|---|
| `POST /v1/chat/completions` | HTTP/1.1, OpenAI SSE или JSON, Bearer | Ingress от DSH | `_serve_sse`, `_serve_json` (F-11, F-19) | тело до 32 MiB, 32 соединения, 8 слотов (F-38, F-39) | 503 overloaded, 504 timeout, 502 agy_error, кадр `error` в SSE (F-11) |
| `GET /health` | HTTP JSON без авторизации | Ingress | `ok`, `active`, `max_concurrent`, `hot_sessions` (F-39) | нет | нет |
| Лончер `agy-cli.sh` | подпроцесс, NDJSON stdin/stdout | Egress | флаги из F-05 | `MAX_CONCURRENT` (F-15, F-38) | `Individual quota reached` (F-46), `first_token_timeout`, `idle_timeout` (F-15) |
| `transcript_full.jsonl` | файл JSONL, только чтение | Egress (чтение) | `PLANNER_RESPONSE.thinking`, `step_index` (F-03, F-33) | порция 4 MiB (F-01) | файл отсутствует или переписан — «мышления нет» (F-02) |
| `conversations/<cid>.db` | SQLite WAL, только чтение | Egress (чтение), новый | `steps.step_payload`, поле 20.3 (F-31, F-32) | строки 2-40 KB (F-32) | ошибка открытия на Python 3.9.6 без `-shm` (F-52) |

## 6. NFR-набросок (наблюдаемые величины)

- Длительность фазы мышления `gemini-4-argon --effort high`: около 19 с тишины stdout в замере (F-29); одношаговые ходы 46.6-55.2 с (F-44).
- Частота записи мышления в БД: 1.5-5.1 с между снимками (F-30).
- Агентные ходы с инструментами: 856.5 с и 1068.0 с, 22-37 кусков мышления через транскрипт (F-45).
- Пик нагрузки: 6 запусков в одну секунду (F-55), `max_concurrent=8` (F-39).
- Ресурсы процесса моста: RSS 20 MiB, 36 дескрипторов (F-51).

## 7. Конверт `HL-ENV/v1`

Контур — один локальный демон LaunchAgent на рабочей станции, не k8s. Поля пода трактуются как «один процесс моста», значения без замера
помечены `оценка`. Единицы СИ.

### 7.1. Канонические 46 полей `REQUIRED_HL_ENV_FIELDS` (`architecture.md`, таблица 3.0)

| № | Поле | Значение | Источник |
|---|---|---|---|
| 1 | `P_steady` | 1 pod (один процесс LaunchAgent) | F-38 |
| 2 | `P_hpa_max` | 1 pod | F-38 |
| 3 | `maxSurge_pct` | 0.0 | F-38 (KeepAlive, без выкатки) |
| 4 | `maxSurge_abs` | 0 pods | вычислено |
| 5 | `maxUnavailable_pct` | 0.0 | F-38 |
| 6 | `maxUnavailable_abs` | 0 pods | вычислено |
| 7 | `P_terminating_overlap` | 0 pods (рестарт через launchctl, `_kill_all` при SIGTERM) | F-38 |
| 8 | `P_live` | 1 pod | вычислено |
| 9 | `P_avail_min` | 1 pod | вычислено |
| 10 | `W` | 1 proc/pod | F-51 |
| 11 | `N_proc` | 1 process | вычислено |
| 12 | `N_proc_steady` | 1 process | вычислено |
| 13 | `N_proc_avail_min` | 1 process | вычислено |
| 14 | `CPU_limit_per_pod` | 2.0 cores (бюджет рабочей станции, оценка) | оценка |
| 15 | `κ_skew` | 1.0 (один процесс) | F-51 |
| 16 | `u_bg_worker` | 0.02 cores на активный ход (опрос транскрипта 20 раз в секунду плюс опрос БД, оценка) | F-01, оценка |
| 17 | `U_pod_sidecars` | 0.0 cores в процессе моста (agy — внешние процессы в своей группе) | F-05 |
| 18 | `Mem_limit_per_pod` | 512 MiB (бюджет демона, оценка) | оценка |
| 19 | `Mem_rss_worker_max` | 64 MiB (измерено 20 MiB без нагрузки, запас на 8 ходов) | F-51 |
| 20 | `Mem_shared_max` | 32 MiB (буферы чтения транскрипта 4 MiB на ход, оценка) | F-01 |
| 21 | `RPS_peak` | 6 req/s (пик запусков в одну секунду) | F-55 |
| 22 | `A_max` | 2 attempts/req | F-09 |
| 23 | `SLA_p99_s` | 1800 s сквозной потолок хода; цель первой дельты мышления 5 s (допущение) | F-15, open-questions |
| 24 | `N_entities_max` | сотни шагов `steps` на разговор (в логе до 52 событий инструментов на ход) | F-45 |
| 25 | `Limit_dep_share[d]` | agy: 8 процессов; БД разговоров: 1 соединение только для чтения на активный ход, до 8 | F-38, F-39 |
| 26 | `Limit_dep_rps[d]` | БД: до 1/T_poll на ход, при 0.5 s до 16 открытий в секунду на 8 ходов (оценка) | оценка |
| 27 | `W_fetchers[d]` | 1 поток опроса на активный ход | F-02 |
| 28 | `J_init_s[d]` | 0 s (опрос стартует по `init`) | F-06 |
| 29 | `J_pod_s[d]` | 0 s (один процесс) | F-38 |
| 30 | `T_poll_s[d]` | транскрипт 0.05 s; БД — выбор Архитектора при интервале записи 1.5-5.1 s | F-01, F-30 |
| 31 | `K_calls[d]` | 1 SELECT на опрос | оценка |
| 32 | `T_base_s[d]` | 2 s (пауза перед повтором хода `2*attempt`) | F-09 |
| 33 | `T_cap_s[d]` | 2 s (одна пауза, второй попытки нет) | F-09 |
| 34 | `Max_stale_age_s[c]` | мышление: 6 s (интервал записи 5.1 s плюс опрос, допущение); горячая сессия: 2700 s простоя | F-30, F-13 |
| 35 | `Min_healthy_ratio` | N/A: один апстрим без пула кандидатов | F-05 |
| 36 | `B_retry_max` | 1 повтор на запрос | F-09 |
| 37 | `min_reserve_retry_rps` | 0.0 req/s | F-09 |
| 38 | `FD_worker` | 36 без нагрузки; плюс до 6 на ход (3 пайпа, транскрипт, БД, `-shm`, оценка) | F-51 |
| 39 | `ulimit_n` | 65536 (launchd soft) | F-54 |
| 40 | `λ_new_conn_per_pod(s)` | до 6 conn/s с loopback от DSH | F-55 |
| 41 | `C_active_in_scope(s)` | до 32 соединений (admission) | F-39 |
| 42 | `N_pods_in_scope(s)` | 1 | F-38 |
| 43 | `Port_range_size(s)` | 16384 ports (49152-65535) | F-54 |
| 44 | `T_hold_s(s)` | 30 s (TIME_WAIT = 2 × MSL 15 s) | F-54 |
| 45 | `SNAT_ips_count(s)` | 1 (loopback, без SNAT) | F-54 |
| 46 | `HOTPATH_MODULES` | `Handler.do_POST`, `_serve_sse`, `_run_once`, `_execute`, `Run._pump`, `_TranscriptTail._read`, `_TranscriptTail._emit_record`, `_reasoning_suffix`, новый опрос БД и парсер wire-формата | F-03, F-06, F-07 |

Замыкание памяти: `W × Mem_rss_worker_max + Mem_shared_max = 64 + 32 = 96 MiB ≤ 0.80 × 512 = 409.6 MiB` (PASS, оценка).

### 7.2. 46 идентификаторов из брифа (дословно)

| № | Поле | Значение | Источник |
|---|---|---|---|
| 1 | `W` | 1 процесс | F-51 |
| 2 | `P_pods` | 1 | F-38 |
| 3 | `G_reload` | 0 (горячей перезагрузки нет, рестарт через launchctl) | F-38 |
| 4 | `T_threads_per_worker` | до 32 потоков соединений плюс 4 потока на ход (stdin, stderr, pump, хвост) × 8 ходов | F-05, F-39 |
| 5 | `Limit_dep_total` | 8 одновременных процессов agy | F-38 |
| 6 | `Limit_dep_share` | 1.0 (весь лимит agy у одного моста) | F-38 |
| 7 | `Pool_app_size` | 8 слотов `_slots` | F-38, F-39 |
| 8 | `Pool_app_overflow` | 0; ожидание слота до 1800 s | F-38 |
| 9 | `Max_in_flight_per_worker` | 8 ходов | F-39 |
| 10 | `N_roles` | 1 | F-38 |
| 11 | `W_role` | 1 | F-51 |
| 12 | `Pool_role_size` | 8 | F-39 |
| 13 | `Pool_role_overflow` | 0 | F-38 |
| 14 | `M_other_apps_max` | другие мосты DSH на том же хосте, общих пулов с agy-bridge нет | F-38 |
| 15 | `Ephemeral_port_range_size` | 16384 | F-54 |
| 16 | `TIME_WAIT_s` | 30 s | F-54 |
| 17 | `ulimit_n` | 65536 | F-54 |
| 18 | `FD_non_socket_overhead` | до 6 на ход (пайпы, транскрипт, БД, `-shm`, оценка) | F-51 |
| 19 | `N_bg_tasks` | 4 потока на ход сейчас, плюс поток опроса БД, если он отдельный | F-05 |
| 20 | `T_poll_s` | 0.05 s транскрипт; БД — выбор Архитектора | F-01, F-30 |
| 21 | `Jitter_Ratio` | 0.0 | F-02 |
| 22 | `Startup_Delay_Range_s` | 0 s | F-06 |
| 23 | `K_calls` | 1 | оценка |
| 24 | `Limit_dep_rps` | БД: до 16 открытий в секунду на 8 ходов при опросе 0.5 s (оценка) | оценка |
| 25 | `Cold_start_concurrent_pods` | 1 | F-38 |
| 26 | `Singleflight_Scope` | ход (у каждого хода свой `cid` и свой файл БД) | F-02, F-30 |
| 27 | `Cache_TTL_s` | 2700 s (простой горячей сессии) | F-13 |
| 28 | `Max_stale_age_s` | 6 s для мышления (допущение) | F-30 |
| 29 | `Payload_bytes_max` | 40 KB на строку `steps` (наблюдено), тело HTTP до 32 MiB | F-32, F-38 |
| 30 | `N_items_max` | сотни шагов на разговор | F-45 |
| 31 | `Hot_path_call_rate_rps` | 20 опросов транскрипта в секунду на ход плюс опрос БД | F-01 |
| 32 | `CPU_budget_pct_per_core` | 2% ядра на активный ход для опроса БД | REQ-012 |
| 33 | `Serde_lib` | `json` и `sqlite3` из stdlib, собственный разбор wire-формата | F-32, F-51 |
| 34 | `P_avail_min` | 1 | F-38 |
| 35 | `Mem_limit_per_pod` | 512 MiB (оценка) | оценка |
| 36 | `Mem_rss_worker_max` | 64 MiB | F-51 |
| 37 | `Mem_shared_max` | 32 MiB | F-01 |
| 38 | `SLA_p99_s` | 1800 s потолок хода; первая дельта мышления 5 s (допущение) | F-15 |
| 39 | `T_connect_s` | N/A для файла БД; loopback HTTP без таймаута подключения | F-11 |
| 40 | `T_read_s` | 1.0 s ожидание очереди; первый JSON stdout 120 s; неактивность 300 s | F-07, F-15 |
| 41 | `Retries_max` | 1 | F-09 |
| 42 | `Retry_Budget_pct` | 100% (до одного повтора на каждый запрос) | F-09 |
| 43 | `Retry_Window_s` | 2 s | F-09 |
| 44 | `Min_Retry_Floor_rps` | 0.0 | F-09 |
| 45 | `N_candidates` | 2 источника мышления (SQLite, транскрипт) | F-30, F-29 |
| 46 | `N_floor` | 1 (транскрипт остаётся минимальным источником) | F-02 |

## 8. Гейты Highload & Resilience (as-is и ограничения для дизайна)

- `C-MULT/v1`: соединения к БД — по одному только для чтения на активный ход, не больше 8 (F-39); дескрипторы `36 + 8 × 6 = 84 ≤ 0.70 × 65536` (F-51, F-54) — PASS (оценка); соединение к БД закрывается вместе с ходом (`Run.close`, F-08).
- `S-HERD/v1`: поллеров внешних сервисов нет, опрос локальных файлов; одновременный старт 6 ходов (F-55) даёт 6 независимых опросов разных файлов, общего ресурса кроме CPU нет.
- `H-CPU/v1`: разбор payload до 40 KB (F-32) на каждый опрос; для ограничения CPU (REQ-012) выборка только строк шага в генерации и шагов после старта хода — решение Архитектора.
- `R-BULK/v1`: повтор хода — не более 1 (F-09); источник мышления в повторах не участвует.
- `T-LIFE/v1`: потоки источников живут не дольше хода и завершаются в `Run.close` (F-08); финальное дренирование ограничено 1.0 с (REQ-007).
- `O-EXIT/v1`: строка `done model=... state=...` уже есть на каждом ходе (F-40); расширение полями источника — REQ-012.
- `M-SEM/v1`: единый пул слотов `_slots` (F-38); новых пулов не появляется.
- Режимы отказа зависимостей: SQLite-источник — `Fail-Open` (REQ-004); транскрипт — `Fail-Open` (as-is, F-02); авторизация моста — `Fail-Closed` (as-is, F-11).

## 9. Non-Goals

- Не менять публичный HTTP-контракт, порт 9887 и форму SSE (REQ-010).
- Не менять DSH, лончер `agy-cli.sh`, бинарь agy и его файлы состояния (БД и транскрипт открываются только на чтение).
- Не модифицировать текст мышления модели.
- Не менять каталог моделей, efforts и логику выбора аккаунта.
- Не исправлять трактовку `text_delta` как накопительного снимка (риск зафиксирован в `open-questions.md`).
- Не вводить внешние зависимости Python: боевой интерпретатор — `/usr/bin/python3` 3.9.6 (F-51).

## 10. Forbidden Scope

- Запись в `~/.gemini/antigravity-cli/conversations/*.db`, `brain/`, создание файлов рядом с ними со стороны моста (кроме служебных файлов SQLite, создаваемых самим режимом чтения).
- Правка чужих мостов и `core/` без явного обоснования Архитектора.
- Запись секретов и текста мышления в логи и артефакты.
- Деплой в `~/.dsh/bridges/agy-bridge/` и рестарт LaunchAgent вне протокола L3 из `handoff-qa.md`; каталог деплоя — копия, а не симлинк (F-38).
- Коммит в `main`, `master`, `dev`; merge выполняет человек.

## 11. Маппинг в `architecture-packet.json`

- `evidence`: `F-01..F-56`.
- `blocking open questions`: пусто.
- `assumptions`: вопросы со статусом ASSUMPTION и DEFERRED из `open-questions.md` (префиксный рост 20.3, открытие WAL на Python 3.9.6, стабильность схемы, причины 6 ходов без мышления, `cwd` фонового запроса, финальный кадр после сбоя, квота для L3, числовые цели, `fleet.json`, `text_delta`, `agentapi`, `immutable=1`).
- `boundaries/contracts`: раздел 5.
- `quality scenarios` (baseline): тишина UI 15-45 с при мышлении (F-29, F-44); цель — первая дельта до 5 с от начала генерации шага, интервал до 6 с, дренирование до 1.0 с.
- `risks`: R1 — смена схемы protobuf после автоапдейта agy (F-25, F-28); R2 — `mode=ro` не открывает закрытую WAL-БД на боевом Python 3.9.6 (F-52); R3 — квота аккаунта блокирует L3 (F-46); R4 — повторная выдача мышления при непрефиксном снимке (F-04); R5 — 6 параллельных ходов удваивают опросы файлов (F-55).

## 12. Обратный канал в требования и бриф

Противоречий фактов с REQ-ID нет. Расхождения с брифом, не меняющие объём работ:
- Тесты моста лежат в `tests/test_agy_bridge_resilience.py`, файла `bridges/agy-bridge/tests/test_agy_bridge.py` нет (F-21).
- Каталог мозга — `~/.gemini/antigravity-cli/brain/<cid>/`, каталога релизов `~/.gemini/antigravity-cli/releases/1.4.9` нет (F-36, F-25).
- `_LAST_CONV` в коде нет, используется `_session_store` (F-14).
- Номера строк и период опроса в брифе устарели (F-50).
- Базовая линия полного набора уже содержит 3 красных теста вне `agy-bridge` (F-56); 22 теста моста зелёные (F-23).
- Stdout `stream-json` 1.4.9 несёт не только `init` и `result`: после фазы мышления идут `step_update` с `text_delta` видимого текста (F-27).

```

### 3.5. `analysis/agy-realtime-reasoning/evidence-ledger.md`
```markdown
# Evidence Ledger: agy-realtime-reasoning (agy-bridge :9887, реалтайм-размышление gemini-4-argon)

Дата сбора: 2026-10-29 (MSK). Ветка `feature/agy-realtime-reasoning` (HEAD `e00da06`). Роль: System Analyst (Stage 1, preset `analyst-teamlead`).
Формат факта: `[F-NN] утверждение | источник | YYYY-MM-DD`. Пути без `~/` — относительно корня репозитория
`~/tmp/cli-agent-bridge/agy-realtime-reasoning/`. Код продукта не менялся. PoC-скрипты и логи аналитика лежат вне репозитория:
`/tmp/cel-runs/agy-realtime-reasoning-sa-20261029/` (`poc_pb.py`, `cmp2.py`, `baseline-*.log`). Секреты не выносились:
значение `AGY_BRIDGE_KEY` не читалось, из логов взяты только счётчики и строки без токенов.

## 1. Код моста: источник мышления и транскрипт

[F-01] Источник мышления моста настроен на транскрипт: `BRAIN_DIR` по умолчанию `~/.gemini/antigravity-cli/brain`, имя файла `transcript_full.jsonl`, период опроса `TRANSCRIPT_POLL_S=0.05` с, финальная пауза `TRANSCRIPT_GRACE_S=0.4` с, порция чтения 4 MiB; комментарий в строках 97-98 утверждает запись транскрипта посреди хода (проверено на 1.3.1) | bridges/agy-bridge/server.py:97-105 | 2026-10-29
[F-02] `_TranscriptTail._run` ждёт привязки к `conversation_id` до `FIRST_TOKEN_TIMEOUT_S` (120 с), для продолжения треда ставит смещение на текущий размер файла, затем опрашивает файл; при выставленном `done_event` или `stop_event` спит `TRANSCRIPT_GRACE_S` и делает один финальный проход, после чего поток завершается | bridges/agy-bridge/server.py:594-662 | 2026-10-29
[F-03] `_TranscriptTail._emit_record` отбирает только записи `type == PLANNER_RESPONSE` с непустым `thinking`, считает приращение через `_reasoning_suffix` с ключом `str(step_index)` и отдаёт его в колбэк `emit`, который кладёт `("reasoning", текст)` в очередь `Run.q` | bridges/agy-bridge/server.py:691-709, 769-772 | 2026-10-29
[F-04] `_reasoning_suffix` возвращает хвост сверх ранее виденного текста того же ключа, а если новый текст не начинается с прежнего, возвращает весь новый текст целиком и перезаписывает виденное | bridges/agy-bridge/server.py:886-893 | 2026-10-29
[F-05] `Run.__init__` запускает лончер с флагами `--input-format stream-json --output-format stream-json --dangerously-skip-permissions --model --effort --print-timeout=0` (и `--conversation` при продолжении), в новой группе процессов, и стартует потоки stdin, stderr, `_pump` и `_TranscriptTail` с `resumed=bool(run_cid)` | bridges/agy-bridge/server.py:720-776 | 2026-10-29
[F-06] `Run._pump` на `init` кладёт событие в очередь и привязывает хвост к `conversation_id`; на `step_update` с `agent_response` и `text_delta` кладёт `("text", хвост)`; на `result` кладёт `("result", ...)`; после EOF stdout ждёт процесс, спит 0.05 с, выставляет `_proc_done` и сразу кладёт `("done", ...)` без ожидания потока хвоста | bridges/agy-bridge/server.py:807-868 | 2026-10-29
[F-07] `Handler._execute` читает только очередь `run.q` (таймаут 1.0 с) и возвращает `state("done")` сразу по событию `done` (после паузы 0.05 с); на `result` со статусом `ERROR` возвращает `agy_error` немедленно; ожидания завершения потока `_TranscriptTail` в цикле нет | bridges/agy-bridge/server.py:981-1101 | 2026-10-29
[F-08] `Run.close` выставляет `_stop_watch` и `_proc_done` и зачищает группу процессов; очередь `run.q` после выхода из `_execute` никем не читается, поэтому событие `reasoning`, положенное хвостом после финальной паузы, клиенту не попадает | bridges/agy-bridge/server.py:870-883, 1148-1151 | 2026-10-29
[F-09] В `Handler._run_once` после неуспешной попытки флаг `delivered = bool(out.get("text") or out.get("tool_calls"))` не учитывает `out["reasoning"]`; при `not delivered` и состояниях `agy_error`, `pump_error`, `done` выполняется невидимый повтор (до 2 попыток, пауза `2*attempt` с), а горячая сессия при `agy_error` без выдачи переходит в холодный повтор с полной историей | bridges/agy-bridge/server.py:1126-1172 | 2026-10-29
[F-10] `_execute` возвращает в `out` поле `reasoning` (склейка отданных клиенту кусков мышления), а `tool_calls` всегда пустой список, то есть `delivered` на практике зависит только от текста | bridges/agy-bridge/server.py:999-1006, 1015-1024 | 2026-10-29
[F-11] `_serve_sse` шлёт первый чанк `{"role":"assistant","content":""}`, мышление отдаёт чанками `delta.reasoning_content`, а при ошибке после начала потока пишет кадр `data: {"error": ...}` и затем `data: [DONE]` | bridges/agy-bridge/server.py:1438-1501 | 2026-10-29
[F-12] Ключ горячей сессии `sess_key = (model_id, cwd, effort)` не содержит признака наличия `tools`, числа сообщений или ключа кэша промпта; `_session_claim` вызывается для любого запроса без явного `conversation_id`, а `tools_count` вычисляется отдельно и в ключ не входит | bridges/agy-bridge/server.py:1368-1385 | 2026-10-29
[F-13] `_session_commit` перезаписывает запись хранилища, если `cid` завершившегося хода отличается от сохранённого; `_session_claim` пропускает занятую (`_in_flight_cids`) сессию и тогда запрос стартует холодным; TTL простоя 45 мин, жизни 24 ч, потолок 30 ходов | bridges/agy-bridge/server.py:116-130, 477-516 | 2026-10-29
[F-14] Глобальной переменной `_LAST_CONV` в мосте нет (0 совпадений grep по `bridges/agy-bridge/` и `core/`); роль «последнего разговора» выполняет словарь `_session_store` с ключом `sess_key` | grep -rn _LAST_CONV bridges/agy-bridge/ core/ (0 строк); bridges/agy-bridge/server.py:128-130 | 2026-10-29
[F-15] Таймауты моста: `KEEPALIVE_S=15`, `FIRST_TOKEN_TIMEOUT_S=120` (порог по первому любому JSON-событию stdout), `TIMEOUT_S=1800`, `QUEUE_TIMEOUT_S=900`, `MAX_CONCURRENT=4` по умолчанию; `IDLE_TIMEOUT_S` берётся из `core.watchdog` (300 с), проверка сторожа не чаще `WATCHDOG_INTERVAL_S=5` с | bridges/agy-bridge/server.py:88-95, 336, 1029-1056; core/watchdog.py:27-30 | 2026-10-29
[F-16] Keepalive моста — SSE-комментарий `: keepalive`, он не несёт ни `content`, ни `reasoning_content` и в UI ничего не показывает | bridges/agy-bridge/server.py:1479-1480 | 2026-10-29
[F-17] Событие `reasoning` входит в `_ACTIVITY_KINDS` и сбрасывает таймер неактивности сторожа через `controller.on_activity` | bridges/agy-bridge/server.py:341, 1057-1058 | 2026-10-29
[F-18] Docstring `_pump` описывает `text_delta` как накопительный снимок, а живой поток 1.4.9 присылает непересекающиеся приращения (например, `Прочитан общий канон ~/Мо`, затем `й диск/`); корректный вывод сейчас обеспечивает ветка «не префикс → весь текст» из `_reasoning_suffix` | bridges/agy-bridge/server.py:807-813, 839-843; /tmp/cel-runs/agy-streaming-research-20261029/live_stream_json.jsonl строки 4-11 | 2026-10-29
[F-19] Нестриминговый путь `_serve_json` кладёт склеенное мышление в `message.reasoning_content`, то есть гонка финального дренирования затрагивает и ответ без `stream` | bridges/agy-bridge/server.py:1413-1436 | 2026-10-29
[F-20] На `done` при пустом потоке текста `_execute` подставляет `final_text` из `result.response`, после чего ход считается `done` | bridges/agy-bridge/server.py:1088-1101 | 2026-10-29

## 2. Тесты и базовая линия

[F-21] Файла `bridges/agy-bridge/tests/test_agy_bridge.py` нет: каталога `tests` у моста нет, тесты моста лежат в корневом `tests/test_agy_bridge_resilience.py` (709 строк, классы IdleDetection, ExecuteLoop, KillSwitch, ErrorContract, KillGroup, FetchViaPlaywrightHotfix) | ls bridges/agy-bridge/ (fleet.json, server.py, start.sh); grep -n "def test_" tests/test_agy_bridge_resilience.py | 2026-10-29
[F-22] Тестов на `_TranscriptTail`, финальное дренирование, флаг `delivered` и `sess_key` нет: слово `reasoning` встречается только в тестах вида активности сторожа | grep -n по словам TranscriptTail, reasoning, sess_key, delivered в tests/test_agy_bridge_resilience.py (строки 248, 354, 363) | 2026-10-29
[F-23] Базовая линия моста зелёная: `python3 -m unittest tests.test_agy_bridge_resilience` дал `Ran 22 tests in 2.082s OK` (exit 0); `python3 -m pytest` недоступен (в python3.14 нет модуля pytest) | /tmp/cel-runs/agy-realtime-reasoning-sa-20261029/baseline-unittest.log, baseline-pytest.log | 2026-10-29
[F-24] Полный прогон `uvx pytest -q -p no:cacheprovider tests/` без `PYTHONPATH` падает на сборке `tests/test_adaptive_idle_watchdog.py` с `ModuleNotFoundError: No module named 'core'` (exit 2); полный набор требует `PYTHONPATH=.` | /tmp/cel-runs/agy-realtime-reasoning-sa-20261029/baseline-full.log | 2026-10-29

## 3. agy 1.4.9: stdout, транскрипт, SQLite

[F-25] Установлен `agy` 1.4.9: `~/.local/bin/agy --version` печатает `1.4.9`, бинарь `~/.local/bin/agy.real` 193540240 байт от 2026-10-28 11:50; каталога `~/.gemini/antigravity-cli/releases/` нет | ~/.local/bin/agy --version; ls -la ~/.local/bin/agy*; ls ~/.gemini/antigravity-cli/ | 2026-10-29
[F-26] `fleet.json` устарел относительно рантайма: `technical_ref.agy_version` равен `1.3.1`; `gemini-4-argon` имеет efforts low/medium/high и `default_effort=high`, `default_model` каталога `gemini-3.8-flash` | bridges/agy-bridge/fleet.json (technical_ref, models[0]) | 2026-10-29
[F-27] Живой поток `stream-json` 1.4.9 (cid `c6910a34`): `init`, `step_update` user_input DONE, два шага `unknown` DONE, семь `agent_response` ACTIVE с `text_delta`, финальный DONE с `usage.thinking_tokens=1460`, затем `result` (`duration_seconds=19.8653`); ни одно событие не несёт текста мышления | /tmp/cel-runs/agy-streaming-research-20261029/live_stream_json.jsonl | 2026-10-29
[F-28] В 1.4.9 Go-структура `steps.StepUpdatePayload` пакета printmode сериализует `text_delta` и `thinking_tokens`, но не поле `thinking` или `thinking_delta`, хотя в protobuf `StepUpdate` поле `thinking_delta` (field 10) объявлено | KB tools/dsh-bridges-cli-agent-bridge.md строки 361-365 (дизассемблирование agy.real 1.4.9) | 2026-10-29
[F-29] Живой замер `gemini-4-argon --effort high` (cid `82188e72`): stdout молчит с 4.81 с по 23.52 с; `transcript_full.jsonl` заморожен на 66213 байтах после `step_index=2`; запись `step_index=3` (`PLANNER_RESPONSE` с `thinking`) появилась в 23.87 с, на 90 мс позже события `result` (23.78 с); `Handler._execute` вышел по `done` в 23.83 с | KB tools/dsh-bridges-cli-agent-bridge.md строки 369-373; /tmp/cel-runs/agy-streaming-research-20261029/checks.tsv строка step-3 | 2026-10-29
[F-30] В том же замере строка `idx=3, step_type=15, status=8` файла `~/.gemini/antigravity-cli/conversations/<cid>.db` обновлялась во время мышления: 10.66 с (523 B), 12.19 с (810 B), 14.97 с (1088 B), 20.06 с (1419 B), 23.36 с (2156 B), то есть интервалы 1.5-5.1 с | KB tools/dsh-bridges-cli-agent-bridge.md строки 374-376; checks.tsv step-3-live-stream-probe | 2026-10-29
[F-31] Схема таблицы `steps`: `idx integer PRIMARY KEY, step_type integer, status integer, has_subtrajectory, metadata blob, error_details blob, permissions blob, task_details blob, render_info blob, step_payload blob, step_format integer`, индексы по `status` и `step_type`; в БД также таблицы `battle_mode_infos, executor_metadata, gen_metadata, parent_references, trajectory_meta, trajectory_metadata_blob` | sqlite3 "file:<db>?mode=ro&immutable=1" ".tables" ".schema steps" (отчёт explorer Zone D); PRAGMA table_info(steps) в poc_pb.py | 2026-10-29
[F-32] PoC-парсер wire-формата на stdlib (varint, wire types 0/1/2/5) извлёк из `82188e72` строки: idx 0 `step_type=14` (2020 B), idx 1 и 2 `step_type=90` (40132 B и 25094 B), idx 3 `step_type=15 status=3` (10068 B) с полем 20, в котором подполе 1 = 196 символов, подполе 3 = 1875 символов, подполе 6 встречается 1 раз, подполе 8 = 196 символов | python3 -I /tmp/cel-runs/agy-realtime-reasoning-sa-20261029/poc_pb.py 82188e72-6eca-4f23-a0b3-2257ec43bd60 | 2026-10-29
[F-33] Финальный текст мышления из SQLite (`step_type=15`, поле 20.3) побайтово равен полю `thinking` записи `PLANNER_RESPONSE` транскрипта при `idx == step_index` на трёх разговорах: `82188e72` (1875 символов, есть не-ASCII), `fa92a264` (1080, есть не-ASCII), `57172100` (5561, только ASCII); в `4a1067cc` шагов `step_type=15` с мышлением нет ни в БД, ни в транскрипте | python3 -I /tmp/cel-runs/agy-realtime-reasoning-sa-20261029/cmp2.py <cid> | 2026-10-29
[F-34] Файлы `conversations/*.db` в режиме WAL (байты 18-19 заголовка `0x02 0x02`, `last written using SQLite version 3053002, page size 32768`); у закрытых разговоров файлов `-wal` и `-shm` нет, в каталоге найдено только 4 таких файла от 2026-10-28 | xxd -s 18 -l 2 <db>; file <db>; ls -la ~/.gemini/antigravity-cli/conversations (отчёт explorer Zone D) | 2026-10-29
[F-35] Python `sqlite3.connect("file:<db>?mode=ro", uri=True)` (SQLite 3.53.4) читает закрытую БД разговора без ошибок, а CLI `sqlite3 -readonly <путь>` на той же БД вернул `unable to open database file (14)` | poc_pb.py вывод `sqlite 3.53.4`; отчёт explorer Zone D вопрос 5 | 2026-10-29
[F-36] Рядом с транскриптом CLI держит копии `chunks/transcript/00000000.jsonl` и `chunks/transcript_full/00000000.jsonl`; разговорный каталог мозга — `~/.gemini/antigravity-cli/brain/<cid>/`, а не `~/.gemini/antigravity/brain/<cid>/` (в последнем для `82188e72` каталога логов нет) | ls ~/.gemini/antigravity-cli/brain/82188e72-.../.system_generated/logs/chunks/*; ls ~/.gemini/antigravity/brain/82188e72-.../.system_generated/logs/ (No such file) | 2026-10-29
[F-37] Python SDK `google-antigravity` возвращает мысли только постфактум (`response.thoughts` после блокирующего `send()`), стримингового генератора мыслей нет | KB tools/dsh-bridges-cli-agent-bridge.md строка 359 (`~/.gemini/antigravity/builtin/skills/antigravity_guide/references/sdk.md`) | 2026-10-29

## 4. Рантайм и деплой :9887

[F-38] LaunchAgent `com.user.dsh-agy-bridge` запускает `/bin/bash ~/.dsh/bridges/agy-bridge/start.sh`, логи в `~/.dsh/bridges/agy-bridge/logs/bridge.err` и `bridge.out`, env `AGY_BRIDGE_MAX_CONCURRENT=8`, `AGY_BRIDGE_PORT=9887`, `AGY_BRIDGE_QUEUE_TIMEOUT=1800`; `~/.dsh/bridges/agy-bridge` — обычный каталог, не симлинк, и его `server.py` побайтово равен репозиторному (sha256 `c4e52312…e747`) | plutil -p ~/Library/LaunchAgents/com.user.dsh-agy-bridge.plist; readlink; shasum -a 256 (отчёт explorer Zone D) | 2026-10-29
[F-39] `/health` моста: `ok=true`, `transport=agy-stream-json`, `model=gemini-3.8-flash`, `active=0`, `max_concurrent=8`, `hot_sessions=2`, `uptime_s=26273` | curl -s -m 3 http://127.0.0.1:9887/health | 2026-10-29
[F-40] `bridge.err` (2891 строк, без дат): `reasoning-emit` 888, `tail-emit` 893, `tail-timeout` 0, `tail-rewrite` 0, `exec model=` 301, `done model=` 266, `transient failure` 29, `hot session failed` 4; пять строк `tail-emit` не имеют парной `reasoning-emit` | grep -cF по ~/.dsh/bridges/agy-bridge/logs/bridge.err | 2026-10-29
[F-41] Из 301 запуска 156 с `tools=0` и 145 с `tools>0`; `resume=1` у 45, `resume=0` у 256 | grep/awk по bridge.err | 2026-10-29
[F-42] В логе 21 пара запусков одной модели в одну секунду, где один `tools>0` с большим промптом и `effort_source=request`, а второй `tools=0` с промптом 492-721 байт и `effort_source=default` на соседнем клиентском порту (например, 01:09:38 `gemini-3.8-flash` 78282 B против 674 B; 23:20:29 и 19:09:44 `gemini-4-argon`) | awk-группировка exec-строк bridge.err, строки 969-970, 1255-1256, 2792-2793 | 2026-10-29
[F-43] Среди ходов `gemini-4-argon` с `state=done`: без инструментов (`tool_events=0`) 28, из них 6 без единой строки `reasoning-emit` для своего cid; с инструментами 23, без мышления 0 | awk по init/reasoning-emit/done в bridge.err; строки 965, 968, 986, 1337, 1804, 1875 | 2026-10-29
[F-44] Одношаговый ход `926e03fa` (`gemini-4-argon`, wall 46.6 с): `tail-emit step=3 len=5342` и `reasoning-emit n=1` записаны в ту же секунду 01:08:22, что и `done`, то есть всё мышление пришло клиенту одним чанком в конце хода; так же ход `496587c9` (len 3935, wall 55.2 с) | bridge.err строки 2777-2782 | 2026-10-29
[F-45] Многошаговый ход `9ccb5526` с инструментами шёл 856.5 с и 1068.0 с (два хода, 52 и 46 событий инструментов) и отдал 37 и 22 куска мышления через транскрипт | bridge.err строки 2735, 2844, 2846, 2891 и подсчёт reasoning-emit | 2026-10-29
[F-46] 2026-10-29 в 01:07-01:09 аккаунт agy получал `Individual quota reached ... Resets in 54h2xm` на `gemini-4-argon` и `gemini-3.8-flash`, а мост выполнял `transient failure ... retry 1` и `hot session failed ... cold fallback` | bridge.err строки 2768, 2787, 2800 и done-строка 01:09:56 | 2026-10-29
[F-47] База знаний фиксирует сценарий RC-3 на `cid=9ccb5526` (мышление Шага 1 затёрто кадром ошибки после сбоя квоты), а в `bridge.err` оба хода `9ccb5526` завершились `state=done rc=0` | KB tools/dsh-bridges-cli-agent-bridge.md строки 377-380; bridge.err строки 2844, 2891 | 2026-10-29
[F-48] Ресерч 2026-10-29 закрыт со статусом ГОТОВО, источник реалтайма зафиксирован как SQLite `conversations/<cid>.db`, таблица `steps`, protobuf field 20.3 | /tmp/cel-runs/agy-streaming-research-20261029/close.md | 2026-10-29
[F-49] Последняя правка `bridges/agy-bridge/server.py` в истории — коммит `b9a9648` (resilience watchdog, process group kill, EYE-33873); ветка `feature/agy-realtime-reasoning` на HEAD `e00da06` (2026-10-28 03:32 MSK), рабочее дерево до анализа содержало только `.ai-team/runs/analyst-teamlead-agy-reasoning-20261029/` | git log --oneline -5 -- bridges/agy-bridge/server.py; git log -1; git status --porcelain | 2026-10-29
[F-50] Номера строк брифа расходятся с кодом: `_TranscriptTail` в 594-709 (в брифе 553-702), `Run._pump` в 807-868 (в брифе 920-935), `TRANSCRIPT_GRACE_S` в строке 104 (в брифе 626), период опроса 0.05 с (в брифе 0.15 с); строки `delivered` (1154) и `sess_key` (1377) совпадают | bridges/agy-bridge/server.py:104, 594, 807, 1154, 1377 | 2026-10-29

## 5. Рантайм Python и ограничения хоста

[F-51] Боевой процесс моста (PID 45973, uptime 07:24:29) запущен `start.sh` строкой `exec /usr/bin/python3 server.py`, то есть системным Python 3.9.6 из CommandLineTools со встроенной SQLite 3.54.0; RSS 20512 KiB, открытых дескрипторов 36 | ps -o pid,rss,etime,command -p 45973; grep -n exec ~/.dsh/bridges/agy-bridge/start.sh (строка 23); lsof -p 45973 (36 строк); /usr/bin/python3 -c sqlite3.sqlite_version | 2026-10-29
[F-52] На копии закрытой WAL-БД разговора (без файлов `-wal` и `-shm`) системный Python 3.9.6 открывает её с `mode=ro` с ошибкой `unable to open database file`, с `mode=ro&immutable=1` читает 4 строки, с `mode=ro&nolock=1` падает; Homebrew Python 3.14.7 (SQLite 3.53.4) читает и с `mode=ro`, и с `immutable=1` | /tmp/cel-runs/agy-realtime-reasoning-sa-20261029/ro_probe.py на dbcopy/t.db обоими интерпретаторами | 2026-10-29
[F-53] Пока на ту же копию открыто читающе-пишущее соединение другого процесса (файл `-shm` существует), системный Python 3.9.6 открывает её с `mode=ro` и читает 4 строки | ro_probe.py, запущенный при живом rw-соединении к dbcopy/t.db | 2026-10-29
[F-54] Лимиты хоста: `launchctl limit maxfiles` 65536 (soft) и unlimited (hard), `ulimit -n` в оболочке 1048576, диапазон эфемерных портов 49152-65535 (16384 порта), `net.inet.tcp.msl` 15000 мс (TIME_WAIT 30 с) | launchctl limit maxfiles; ulimit -n; sysctl net.inet.ip.portrange.first net.inet.ip.portrange.last net.inet.tcp.msl | 2026-10-29
[F-55] Пиковая частота запусков по `bridge.err` — 6 строк `exec` в одну секунду (15:03:40), следующая — 4 (15:27:38) | grep -F " exec model=" bridge.err, группировка по времени uniq -c | 2026-10-29
[F-56] Полный набор `PYTHONPATH=. uvx pytest -q -p no:cacheprovider tests/` на HEAD `e00da06`: 3 failed, 896 passed, 8103 subtests passed за 363.6 с; красные тесты вне `agy-bridge`: `test_b_guard.py::TestTm018Guard::test_tm018_live_check_subprocess`, `test_muse_bridge_killpg.py::AllowedModelsSyncTest::test_t00_models_and_health_include_wonder_models_400k`, `test_rpc_rework.py::TestRpcWriteDeadline::test_rw011_shutdown_all_within_budget_with_stuck_child` | /tmp/cel-runs/agy-realtime-reasoning-sa-20261029/baseline-full2.log | 2026-10-29

```

### 3.6. `analysis/agy-realtime-reasoning/open-questions.md`
```markdown
# Open Questions: agy-realtime-reasoning

Дата: 2026-10-29 (MSK). Блокеров нет: ни один вопрос не останавливает ветку Архитектора, все вопросы класса «МОЖНО ПРОДОЛЖИТЬ».
Статус записан префиксом в поле «что мешает закрыть»: `CLOSED` — закрыт фактами ledger, `ASSUMPTION` — открыт, но закрыт рабочим допущением,
`DEFERRED` — отложен с рабочим допущением. Статусов `open` без допущения нет.
Формат строки — по канону скилла (`OPEN-NN | класс | вопрос | что мешает закрыть | кто нужен | риск | допущение`), а не markdown-таблица из брифа:
оракул `SA-DOD-004` принимает только такой формат строк. Смысловые колонки брифа сохранены: «Допущение / закрытие» — поля 4 и 7, «Статус» — префикс поля 4.

OPEN-01 | МОЖНО ПРОДОЛЖИТЬ | Растёт ли текст поля 20.3 строго префиксно между снимками строки в status=8 | ASSUMPTION: ряд промежуточных payload не сохранялся, подтверждены только монотонный рост размера (F-30) и равенство финального текста транскрипту (F-33) | Coder-спайк, QA | при непрефиксной перезаписи `_reasoning_suffix` отдаёт текст шага целиком повторно (F-04) | Рост префиксный; непрефиксный снимок не приводит к повторной выдаче уже отданного текста (REQ-003)
OPEN-02 | МОЖНО ПРОДОЛЖИТЬ | Держит ли agy БД разговора открытой (с файлом `-shm`) всё время хода, чтобы системный Python 3.9.6 мог читать её в режиме `mode=ro` | ASSUMPTION: боевой Python 3.9.6 не открывает закрытую WAL-БД с `mode=ro` (F-52), но открывает при живом пишущем соединении (F-53); живой опрос ресерча прошёл (F-30), интерпретатор того опроса не записан | Coder-спайк на `/usr/bin/python3` | на дренировании после выхода agy и до первого открытия БД чтение падает | Во время хода чтение `mode=ro` работает; ошибка открытия трактуется как «изменений нет», источник fail-open, а окно после выхода agy закрывает транскрипт или `immutable=1` по выбору Архитектора (REQ-004, REQ-006)
OPEN-03 | МОЖНО ПРОДОЛЖИТЬ | Стабильны ли номера полей (`step_type=15`, `status=8`, поле 20, подполе 3) между версиями agy | ASSUMPTION: схема внутренняя и не документирована, бинарь обновляется фоновым автоапдейтером (F-25, F-28) | владелец, Architect | после обновления agy источник молча перестанет давать дельты | Привязка к 1.4.9; несовпадение схемы распознаётся и логируется, мышление продолжает идти из транскрипта (REQ-004, REQ-012)
OPEN-04 | МОЖНО ПРОДОЛЖИТЬ | Чем вызваны 6 одношаговых ходов argon без мышления: гонкой дренирования, пустым мышлением модели или смещением хвоста при продолжении треда | ASSUMPTION: 4 из 6 случаев — продолжения (turns 2-3), лог не различает причины (F-43) | QA | неверная оценка вклада RC-2 | Все три причины закрываются требованиями REQ-005 и REQ-006 вместе
OPEN-05 | МОЖНО ПРОДОЛЖИТЬ | Совпадает ли `cwd` фонового запроса DSH (генерация заголовка) с `cwd` основного диалога | ASSUMPTION: `cwd` в `bridge.err` не пишется; пары запросов видны (F-42), коллизия ключа следует из кода (F-12, F-13) | QA на живом DSH | изоляция по одному признаку `tools` окажется неполной | Совпадает; изоляция обязательна независимо от `cwd`
OPEN-06 | МОЖНО ПРОДОЛЖИТЬ | Какой финальный SSE-исход нужен, если сбой случился после уже отданного мышления: кадр `error` или `stop` с частичным ответом | ASSUMPTION: KB фиксирует затирание блока мышления кадром ошибки (F-47), в `bridge.err` случай не подтверждён | владелец, Architect | регрессия отображения в DSH | Невидимый повтор после отданного мышления запрещён; выбор финального кадра за Архитектором
OPEN-07 | МОЖНО ПРОДОЛЖИТЬ | Можно ли провести живую приёмку L3 при исчерпанной квоте agy | ASSUMPTION: квота аккаунта сбрасывается примерно через 54 ч от 01:09 MSK 2026-10-29 (F-46) | владелец | L3 откладывается | L3 выполняется на аккаунте с квотой (переключение штатным `antigravity-account-switch.sh`) или после сброса
OPEN-08 | МОЖНО ПРОДОЛЖИТЬ | Какие числовые цели отзывчивости принимает владелец | ASSUMPTION: владелец сформулировал проблему без чисел | владелец | критерии приёмки останутся субъективными | Первая дельта мышления не позже 5 с после начала генерации шага; интервал между дельтами в фазе мышления не больше 6 с (максимум интервала записи в F-30 равен 5.1 с); добавка финального дренирования к времени хода не больше 1.0 с
OPEN-09 | МОЖНО ПРОДОЛЖИТЬ | Обновлять ли `fleet.json technical_ref.agy_version` и комментарии про 1.3.1 | DEFERRED: на поведение не влияет (F-26, F-01, F-18) | Architect | путаница в документации моста | Входит в MR как документационная правка
OPEN-10 | МОЖНО ПРОДОЛЖИТЬ | Исправлять ли трактовку `text_delta` как накопительного снимка | ASSUMPTION: вывод сейчас корректен благодаря ветке «не префикс → весь текст» (F-18, F-04); сбой возможен, только если новая дельта начинается с текста предыдущей | Architect | редкая потеря фрагмента видимого текста | Вне объёма этого MR, фиксируется как риск
OPEN-11 | МОЖНО ПРОДОЛЖИТЬ | Подходит ли локальный `~/.gemini/antigravity-cli/bin/agentapi` как альтернативный live-источник | DEFERRED: не исследовался в этом анализе | Architect | пропущен более устойчивый API | Не рассматривается, основной кандидат — чтение SQLite
OPEN-12 | МОЖНО ПРОДОЛЖИТЬ | Пригоден ли режим `immutable=1` для опроса БД | ASSUMPTION: на закрытой БД `immutable=1` читает на обоих интерпретаторах (F-52); `immutable=1` сообщает SQLite, что файл не меняется, поэтому для БД, в которую agy ещё пишет, он не годится | Coder-спайк | чтение устаревших страниц во время хода | Во время хода используется `mode=ro`; `immutable=1` допустим только после выхода процесса agy
OPEN-13 | МОЖНО ПРОДОЛЖИТЬ | Где лежат тесты моста и как запускать полный набор | CLOSED: тесты в `tests/test_agy_bridge_resilience.py` (F-21), набор моста зелёный через `unittest` (F-23), полный набор требует `PYTHONPATH=.` (F-24) | никто | нет | не требуется
OPEN-14 | МОЖНО ПРОДОЛЖИТЬ | Верны ли пути из брифа к `brain` и к релизу agy | CLOSED: каталог разговора — `~/.gemini/antigravity-cli/brain/<cid>/` (F-36), каталога `releases/` нет, бинарь — `~/.local/bin/agy.real` (F-25) | никто | нет | не требуется
OPEN-15 | МОЖНО ПРОДОЛЖИТЬ | Существует ли `_LAST_CONV`, упомянутый в брифе | CLOSED: переменной нет, её роль выполняет `_session_store` (F-14) | никто | нет | не требуется
OPEN-16 | МОЖНО ПРОДОЛЖИТЬ | Входят ли 3 красных теста полного набора вне `agy-bridge` в объём этого MR | DEFERRED: тесты относятся к `b_guard`, `muse-bridge` и `rpc`, на HEAD до изменений уже красные (F-56) | владелец, Architect | Full Suite Gate перед MR не будет полностью зелёным | Не входят; в отчёте MR фиксируется, что набор красных тестов до и после изменений совпадает

## ВОПРОСЫ ВЛАДЕЛЬЦУ

1. [МОЖНО ПРОДОЛЖИТЬ] Принимаете ли цели: первая дельта мышления до 5 с от начала генерации, интервал между дельтами до 6 с, добавка дренирования до 1.0 с? Почему нужен: от них зависят период опроса и критерии приёмки. Допущение: приняты. После ответа: QA фиксирует пороги в L3.
2. [МОЖНО ПРОДОЛЖИТЬ] Какой финальный кадр показывать, если сбой случился после отданного мышления: ошибку или частичный ответ со `stop`? Почему нужен: от этого зависит, сохранится ли блок Think в DSH. Допущение: выбор за Архитектором, невидимый повтор запрещён. После ответа: Архитектор фиксирует контракт.
3. [МОЖНО ПРОДОЛЖИТЬ] Живую приёмку L3 вести на другом аккаунте agy (квота текущего исчерпана) или ждать сброса около 54 ч? Почему нужен: без L3 сдача тяжёлым путём невозможна. Допущение: переключение аккаунта штатным скриптом. После ответа: QA планирует окно L3.

```

## 4. Финальное напоминание по формату ответа (`PoL-V06` / `PoL-V07`)
PANEL-NONCE: b63df148da9eb41b
ARTIFACT-SHA256: 62a83bb2f0bfd9e9e975a05a5aea61991d27f49f642d1b810fc2a87dc4af2aab
ОБЩИЙ ВЕРДИКТ: PASS|NEEDS WORK|RED FLAG
Первыми двумя строками ответа выведи дословно «PANEL-NONCE: b63df148da9eb41b» и «ARTIFACT-SHA256: 62a83bb2f0bfd9e9e975a05a5aea61991d27f49f642d1b810fc2a87dc4af2aab».
Перед финальной строкой вердикта выведи:
COVERAGE: 6/6 подкатегорий
FINDINGS_COMPLETE: <число>
И самой последней строкой ответа выведи ровно одну строку:
ОБЩИЙ ВЕРДИКТ: PASS|NEEDS WORK|RED FLAG
