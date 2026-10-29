# Coder summary — agy-universal-image-fallback (Stage 4, iteration 1)

Ветка `feat/agy-universal-image-fallback`, base `012da99905ec27a6133afb4f3e768ff9b4426a8f`. Изменены только два разрешённых файла; `fleet.json`, `analysis/**`, прочие файлы репозитория не тронуты.

## Что сделано

`bridges/agy-bridge/server.py` (AD-001..AD-004):

- **AD-001.** Независимый fail-closed флаг `IMAGE_FALLBACK_ENABLED` (env `AGY_IMAGE_FALLBACK_ENABLED`: `1|true|yes` → True, остальное непустое → False; без env — строгий JSON-boolean, TTL 1.0 с, отдельные замок и кэш `_image_fallback_flag_cache`). Кэш сбрасывается в `_reset_sqlite_guards_for_tests()`. `_image_gate_universal(model_id, effort)`: input включён, модель из каталога, effort пуст/None или в `model["efforts"]`; proof, SHA и `efforts_proven` не читаются. Политика фиксируется один раз на запрос, после слота перепроверяется только input.
- **AD-002.** Классификация media по `type` и payload-ключам до чтения `text`; image: `image_url|image|input_image`; прочее: `input_audio|audio|video|video_url|file|document|inlineData|inline_data|fileData|file_data`. Функции `_flatten_content_stripped`, `_strip_media_from_messages` (не мутирует вход, идемпотентна), `_messages_to_stripped_prompt`, `_universal_render_messages` (канонизация алиасов в `image_url`, прочее media опускается), `_collect_images(..., universal=True)`. Dict-content обрабатывается как одна часть.
- **AD-003.** `_downgrade_to_text_in_run_once`: событие → cleanup собственного каталога → CAS `_session_invalidate` + `_cid_release` (+ discard из `_in_flight_cids` для hot) → `prompt`/`full_prompt` = `stripped_full_prompt`; запасной вариант `_text_only_prompt_fallback` без `[attachments]` и `[image N]`. Три точки: collect (do_POST: flag-off/ImageReject/non-image media → холодный text-only без resume явного и кэшированного CID), post_slot/spool (`_run_once`), runtime (после `run.close()`, ДО hot-continue и transient-ветки: attempt==1, реально прикреплены images, state не done/client_gone, delivered=false → ровно один text-only повтор, один `_retry_take()` либо разовый резерв, jitter).
- **AD-004.** `/health` и `/v1/models`: булевы `images` = effective (universal → `input_enabled` для всех моделей каталога; strict → прежний `_model_supports_images`), плюс аддитивный объект `image_fallback` (`mode`, `acceptance`, `fallback_enabled`, `input_enabled`, `method`, `limits`, `models`). Структурный лог `image_fallback stage=… reason=… model=… attempt=… images=…` через `_log_token` (только `A-Za-z0-9_.-`, ≤ 64) и существующий маскирующий `_log`.

`tests/test_agy_bridge_resilience.py` (AD-005): дописан `UniversalImageFallbackTests` (`test_uf01`..`test_uf10` + `test_uf03b`, `test_uf07b`), реальные малые PNG/JPEG/GIF/WebP, helper `_UniEnv` (оба ключа конфигурации пишутся вместе, env и кэши восстанавливаются; порядок strict→universal→strict не протекает). Исходные 249933 байта (6008 строк) не изменены.

## Результаты VER

| ID | Результат |
|---|---|
| VER-001 ruff check | exit 0 |
| VER-002 ruff format --check | exit 0 |
| VER-003 unittest Image*+AcceptanceOracle+UniversalImageFallbackTests | exit 0, Ran 58 OK |
| VER-004 basedpyright@1.40.2 delta vs BASE | exit 0, baseline 792 / candidate 787 / новых 0 |
| VER-005 pytest (весь репозиторий) | **exit 2** — 3 ошибки сбора несвязанных модулей (`tests/test_cache_usage.py`, `tests/test_fleet_v3.py`, `tests/test_tool_parser.py`); те же 3 ошибки на BASE (`logs/VER-005-on-BASE.log`) |
| VER-006 append-only + test_images_strict | exit 0 (`APPEND_ONLY_STRICT_PASS 249933`) |
| VER-007 AST-покрытие | exit 0 (`QA_ASSERT_COVERAGE_PASS 50`) |
| VER-008 scope/frozen | exit 0 (`SCOPE_FROZEN_PASS`) |
| VER-009 static contract | exit 0 (`STATIC_IMAGE_SECURITY_CONTRACT_PASS`) |
| VER-010 деплой + live-receipt | **exit 1** — не выполнено, вне scope Coder |

Дополнительно:

- 146 legacy-тестов файла на кандидате — OK (unittest).
- pytest 9.0.3 по `tests/test_agy_bridge_resilience.py` + `tests/test_images_strict.py`: **176 passed, 273 subtests passed**.
- Красный прогон: 12 новых тестов на BASE `server.py` — 12/12 падают (failures=36, errors=55); на кандидате 12/12 OK (red → green).

## НЕ ПРОВЕРЕНО / не PASS

- **VER-005** как заморожен — красный до моих правок (инфраструктура сбора, не код фичи). Заменён эквивалентными прогонами выше; решение о допустимости замены — Teamlead.
- **VER-010 / REQ-05:** деплой candidate server.py в `~/.dsh/bridges/agy-bridge/`, запись `IMAGE_INPUT_ENABLED=true` и `IMAGE_FALLBACK_ENABLED=true` в его `dynamic_config.json`, `teamlead/live-acceptance.json` и живая приёмка в существующем DSH-чате владельца — release/Teamlead; Coder в production не писал. Слова «готово»/«работает» для production неприменимы.
- Ресурсный профиль (квоты, p99, CPU/RSS/FD; до 2N CLI-запусков в худшем батче), exactly-once, pixel-decode — не измерялись (RISK-008/001, ASM-002).

## Отклонения и допущения

- Скилл `~/Мой диск/skils/ai-sdlc/universal/coder/SKILL.md` отсутствует на диске. Использованы `orchestrate-coder-reviewer-summarizer/SKILL.md`, `references/steps.md`, `aisdlc-gcge/skills/feature.md`.
- Строковый `image_url` (и `input_image` со строкой) в universal принимается канонизацией AD-002, поэтому taxonomy-кейс `string_image_url` не отклоняется, а уходит оптимистично; в strict поведение прежнее.
- `stripped_full_prompt` считается только при наличии структурного media (иначе совпадает с `full_prompt`).

## Артефакты

- `plans/coder-01.json` (after, sha256 `86e81369…`), `plans/coder-01.initial.json`
- `handoffs/coder-01.json` (`validate_handoff.py coder` → VALID)
- `fingerprints/coder-after.json` (`1729033c…`, files=168)
- `coder/logs/` — логи всех VER и сравнений


## Iteration 3 — residual F-001
- server.py: `_classify_part` (text None/'' + посторонние ключи -> unknown); `do_POST`: `_universal_render_messages` безусловно при universal, `full_prompt = stripped` при `force_cold or (universal and not images)`.
- tests: test_uf07 + F/G/H/K/I/J unit и HTTP JSON/SSE cold/hot (fake agy prompt без PAYLOAD_SECRET_99999 и dict-repr).
- VER-001/002/003/004/006/007/008/009 exit 0; fingerprint sha256 0efcb715f698e2d4ce3c6b08f6f4a48113e02e7790d16ac74575f82c24175ed5.
- pytest agy+strict: 175 passed, 1 failed (test_tc93 cpu-порог, идентично на BASE при load avg ~18).
