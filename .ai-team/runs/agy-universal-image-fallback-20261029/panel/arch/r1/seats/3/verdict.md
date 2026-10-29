PANEL-NONCE: bce97997943685ff
ARTIFACT-SHA256: f6c7a59500b8ece3b756c115b82eea5fd6de42de2825a7ed93b34345b4c49e6b

Подтверждение чтения правил: общий канон `~/Мой диск/Context/AGENTS.md` прочитан целиком до `<!-- КАНОН-КОНЕЦ -->`; в рабочей папке репозитория проектные файлы правил (`AGENTS.md`, `.agents/AGENTS.md`, `CLAUDE.md`) отсутствуют.

# Architecture Panel Review (R1) — `agy-universal-image-fallback-20261029`

## 1. Сводка проверки артефактов и кода

Проведена независимая read-only верификация [architecture-packet.json](file:///Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/.ai-team/runs/agy-universal-image-fallback-20261029/architecture/architecture-packet.json) (`SHA256: f6c7a59500b8ece3b756c115b82eea5fd6de42de2825a7ed93b34345b4c49e6b`) и [verification-surface.json](file:///Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/.ai-team/runs/agy-universal-image-fallback-20261029/teamlead/verification-surface.json) против:
- входных артефактов Stage 1 ([handoff-architect.md](file:///Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/analysis/agy-universal-image-fallback/handoff-architect.md), [handoff-qa.md](file:///Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/analysis/agy-universal-image-fallback/handoff-qa.md), [evidence-ledger.md](file:///Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/analysis/agy-universal-image-fallback/evidence-ledger.md));
- фактического кода [server.py](file:///Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/bridges/agy-bridge/server.py), каталога [fleet.json](file:///Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/bridges/agy-bridge/fleet.json) и тестового набора [test_agy_bridge_resilience.py](file:///Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/tests/test_agy_bridge_resilience.py) (6008 строк, `249933` байт).

### Трассировка ключевых архитектурных решений (`AD-001..AD-005`)

1. **`AD-001` (Universal Policy Flag & Dynamic Config Activation — `REQ-01`, `REQ-04`, `REQ-05`, `CON-04`, `INV-01`, `RISK-05`):**
   - Независимый fail-closed флаг `IMAGE_FALLBACK_ENABLED` в `dynamic_config.json` (TTL `1.0s`, отдельный замок `_image_fallback_flag_lock` и кэш `_image_fallback_flag_cache = (0.0, False)`, сбрасываемый в [`_reset_sqlite_guards_for_tests`](file:///Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/bridges/agy-bridge/server.py#L1230-L1262)) и env-переопределение `AGY_IMAGE_FALLBACK_ENABLED` полностью изолируют существующие strict-тесты (`_Fixture` и [`_ImgEnv.flag`](file:///Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/tests/test_agy_bridge_resilience.py#L4030-L4039) выставляют только `IMAGE_INPUT_ENABLED`).
   - `_image_gate_universal(model_id, effort)` проверяет принадлежность модели `FLEET_MODELS`, допустимый `effort` модели и `_is_image_input_enabled()`, не обращаясь к [`_image_proof_reason`](file:///Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/bridges/agy-bridge/server.py#L718-L768) и [`_file_sha256`](file:///Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/bridges/agy-bridge/server.py#L643-L679), при этом сохраняя все проверки безопасности (`<=16` изображений, `<=20 MiB`, `role == "user"`, `data:` base64, сигнатуры PNG/JPEG/GIF/WebP, запрет внешних/файловых URL).

2. **`AD-002` (Complete Media Normalization & Stripping — `REQ-06`, `INV-02..04`, `INV-07`):**
   - Устраняет уязвимость текущего [`_flatten_content`](file:///Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/bridges/agy-bridge/server.py#L589-L610), где `dict`-контент сериализуется через `str(content)`, а текстовое поле внутри медиа-объекта могло просочиться при проверке `"text" in item` раньше типа/ключей медиа.
   - Классификация медиа по `type` и payload-ключам (`image_url`, `image`, `input_image` -> `[image omitted]`; `input_audio`, `audio`, `video`, `video_url`, `file`, `document`, `inlineData`, `inline_data`, `fileData`, `file_data` -> `[media omitted]`) выполняется строго до чтения `text`, не мутирует входной `messages` и идемпотентна (`_strip_media_from_messages(N) == N`).
   - Предвычисление `ctx["stripped_full_prompt"]` гарантирует отсутствие маркеров `[image N]` и блока `[attachments]` при любом сценарии деградации.

3. **`AD-003` (Three Safe Downgrade Points — `REQ-02`, `REQ-03`, `INV-05..09`, `INV-11`, `INV-12`):**
   - **Point 1 (`do_POST`, `stage="collect"`):** перехватывает `not input_enabled`, [`ImageReject`](file:///Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/bridges/agy-bridge/server.py#L618-L625) и non-image media в [`do_POST`](file:///Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/bridges/agy-bridge/server.py#L3628-L3642), переключая `prompt` и `full_prompt` на `stripped_full_prompt`, обнуляя `images`/`img_dir` и запрещая resume грязной сессии.
   - **Point 2 (`_run_once`, `stage="post_slot"` / `stage="spool"`):** в [`_run_once`](file:///Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/bridges/agy-bridge/server.py#L3176-L3208) при `universal=True` перепроверяет только `_is_image_input_enabled()` после ожидания слота и перехватывает [`ImageSpoolError`](file:///Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/bridges/agy-bridge/server.py#L628-L629), очищая частичный каталог через [`_cleanup_img_dir`](file:///Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/bridges/agy-bridge/server.py#L966-L977), сбрасывая `hot_resumed`/`conversation_id` через [`_session_invalidate`](file:///Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/bridges/agy-bridge/server.py#L1129-L1133) и [`_cid_release`](file:///Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/bridges/agy-bridge/server.py#L1538-L1545), и выполняет `attempt == 1` как чистый текстовый ход (`add_dir=None`).
   - **Point 3 (`_run_once`, `stage="runtime"`):** размещён сразу после `run.close()` на `attempt == 1` **до** ветки `if ctx.get("hot_resumed"): ... continue` ([server.py:3280-3298](file:///Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/bridges/agy-bridge/server.py#L3280-L3298)) и **до** общей транзиентной ветки ([server.py:3300-3313](file:///Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/bridges/agy-bridge/server.py#L3300-L3313)). Однозначно соблюдает инвариант `attempt == 1 and universal and images and img_dir is not None and out["state"] not in ("done", "client_gone") and not delivered`, удаляет `img_dir` до конструктора второго `Run` и использует одноразовый per-request резерв деградации при исчерпанном `_retry_tenths`.

4. **`AD-004` & `AD-005` (Observability, Frozen Baseline & Verification Surface — `REQ-04`, `CON-05`, `INV-10`):**
   - Сохраняет булев тип `health["images"]` и `data[*]["images"]` в [`do_GET`](file:///Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/bridges/agy-bridge/server.py#L3418-L3475) (совместимо с [`test_ao01`](file:///Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/tests/test_agy_bridge_resilience.py#L5620-L5680) и [`test_ao06_health`](file:///Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/tests/test_agy_bridge_resilience.py#L2764-L2800)), добавляя отдельный объект `image_fallback`.
   - Сохраняет все 6008 строк (`249933` байт, `SHA256: f318d60537ad862b11313d303644ace3ff5ae74e5d581ceeba86bcf7bddeeff5`) [test_agy_bridge_resilience.py](file:///Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/tests/test_agy_bridge_resilience.py) как неизменный префикс (`VER-006`) и проверяет выполнение новых тестов `UniversalImageFallbackTests` (`test_uf01..test_uf10`) через `importlib` discovery (`VER-003`, `VER-005`, `VER-007`).
   - `HL-ENV/v1` честно фиксирует `BLOCKED_UNMEASURED_PRODUCTION` / `NOT_PROVEN` для неизмеренных production-метрик без фабрикации чисел.

---

## 2. Замечания (Findings)

Блокирующих замечаний (`BLOCKER-SAFETY`, `BLOCKER`, `MAJOR`) не обнаружено. Два `MINOR` уточнения для этапа реализации (Coder):

- **[MINOR-01] Очистка `_in_flight_cids` при прямом вызове `_run_once` в unit-тестах**
  - **Локация:** [architecture-packet.json](file:///Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/.ai-team/runs/agy-universal-image-fallback-20261029/architecture/architecture-packet.json#L819-L826) (`AD-003.details.downgrade_transition_order`), [server.py:1098-1134](file:///Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/bridges/agy-bridge/server.py#L1098-L1134), [server.py:3720-3726](file:///Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/bridges/agy-bridge/server.py#L3720-L3726).
  - **Суть:** В HTTP-пути [`do_POST`](file:///Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/bridges/agy-bridge/server.py#L3721-L3723) освобождает `_in_flight_cids.discard(use_cid)` в `finally`. При сбросе `old_cid` внутри `_run_once` (или внутри [`_session_invalidate`](file:///Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/bridges/agy-bridge/server.py#L1129-L1133)) рекомендуется также выполнять `_in_flight_cids.discard(old_cid)` под `_session_store_lock`, чтобы даже при прямом вызове `_run_once` в unit-тестах (мимо `do_POST`) старый `cid` не оставался в `_in_flight_cids`.

- **[MINOR-02] Защитный fallback для `ctx["stripped_full_prompt"]` при прямом вызове `_run_once`**
  - **Локация:** [architecture-packet.json](file:///Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/.ai-team/runs/agy-universal-image-fallback-20261029/architecture/architecture-packet.json#L755) (`AD-002.details.ctx_contract`), [tests/test_agy_bridge_resilience.py:4129-4150](file:///Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/tests/test_agy_bridge_resilience.py#L4129-L4150).
  - **Суть:** В `do_POST` поле `ctx["stripped_full_prompt"]` предвычисляется всегда. Для удобства прямых unit-тестов `_run_once` (по аналогии с `_img_ctx`) в helper'е деградации внутри `_run_once` стоит предусмотреть безопасный fallback (например, если в синтетическом `ctx` теста не передан `stripped_full_prompt`, использовать непустой безопасный промпт без `[attachments]` и `[image N]`), а в тестовом хелпере `UniversalImageFallbackTests` явно заполнять `stripped_full_prompt`.

---

## 3. Итоговый вердикт

Архитектурный пакет `AP/v1` полон, внутренне непротиворечив, строго соблюдает ограничения безопасности, обратной совместимости и append-only инварианты тестового набора.

VERDICT: PASS
