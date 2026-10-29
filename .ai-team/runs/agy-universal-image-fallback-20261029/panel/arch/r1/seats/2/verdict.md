PANEL-NONCE: 16b5fb5706ca88a7
ARTIFACT-SHA256: f6c7a59500b8ece3b756c115b82eea5fd6de42de2825a7ed93b34345b4c49e6b

Подтверждаю: общий канон `~/Мой диск/Context/AGENTS.md` загружен целиком до `<!-- КАНОН-КОНЕЦ -->`. Проектных файлов правил (`AGENTS.md`, `.agents/AGENTS.md`, `CLAUDE.md`) в корне репозитория и рабочей папке нет — ревью выполнено по заданию панели и артефактам прогона.

# ARCH_PANEL R1 — ревью AP/v1 `agy-universal-image-fallback-20261029`

## Проверка целостности входа

| Проверка | Результат |
|---|---|
| SHA256 пакета vs `verification-surface.json` | совпал: `f6c7a595…9e6b`, пересчитан мной |
| HEAD / ветка vs `baseline` пакета | `012da999…6a8f`, `feat/agy-universal-image-fallback` — совпало |
| Строк теста / сервера | 6008 / 3963 — совпало с `test_prefix_lines` |
| Ключевые символы в [server.py](/Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/bridges/agy-bridge/server.py) | `_session_invalidate` ([server.py](/Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/bridges/agy-bridge/server.py:1129)), `_cid_release(cid, turn_id)` ([server.py](/Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/bridges/agy-bridge/server.py:1538)), hot-ветка и transient-ветка ([server.py](/Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/bridges/agy-bridge/server.py:3280)) — EVD-ссылки пакета точны |

## Соответствие требованиям

- **REQ-01 / AD-001:** отдельный fail-closed флаг `IMAGE_FALLBACK_ENABLED` (default `False`) корректно разводит universal и staging. `_ImgEnv.flag()` пишет только старый ключ — существующие 46 strict-методов остаются зелёными без правок. `_image_gate_universal` реализуем: у каждой модели fleet есть список `efforts` ([fleet.json](/Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/bridges/agy-bridge/fleet.json)), ingress уже валидирует effort по каталогу. Proof/SHA не подделываются, fleet не мутируется.
- **REQ-02 / AD-003 точки 1–2:** все три точки даунгрейда привязаны к реальным местам кода. Post-slot в HEAD возвращает `image_reject`/`image_spool_error` терминально до цикла попыток ([server.py](/Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/bridges/agy-bridge/server.py:3176)) — пакет верно требует fallthrough в text attempt1 с `img_registered=False`. CON-06 соблюдён: auth/admission/model/effort остаются fail-closed до media-обработки.
- **REQ-03 / AD-003 точка 3:** guard поставлен после `done`-break и **до обеих** legacy-веток — раннего hot-`continue` ([server.py](/Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/bridges/agy-bridge/server.py:3291)) и transient-`_retry_take` ([server.py](/Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/bridges/agy-bridge/server.py:3306)). Формула `delivered` в пакете совпадает с кодом. Резерв при `_retry_tenths == 0` ограничен 1/запрос, цикл `(1,2)` исключает третью попытку. Исключения `done`+bad rc и constructor-ошибок честно зафиксированы в RISK-003 и покрыты uf08.
- **REQ-06 / AD-002:** классификация «media раньше `text`», отказ от `str(dict)`, неизвестные structured-объекты опускаются (fail-closed по умолчанию, а не passthrough по списку). Предвычисленный `stripped_full_prompt` закрывает F-111/F-124: в ctx исходных messages нет, простой `images=[]` оставил бы `[image N]`.
- **REQ-04 / AD-005:** префикс 249933 байта как точный blob + `0` удалённых строк против двух бейзлайнов (VER-006) сильнее одного numstat. Расхождение 6009/6008 задокументировано в самом пакете. `__main__`-guard до append учтён — VER-003/005 используют import discovery.
- **REQ-05:** активация только в deployed ROOT, пара хэшей server/fleet, живой чат владельца в VER-010 с явной пометкой «receipt presence is NOT itself proof». Лёгкий путь за тяжёлый не выдаётся.
- **Безопасность:** fetch/file-чтений нет и статически запрещено VER-009; лимиты 16/20MB/32MB, role=user, data:-только, MIME+signature сохранены (INV-01). `_log_token` с allowlist-символами и cap 64 закрывает INV-10. Ресурсный конверт: 46 полей UNKNOWN честно, capacity PASS не заявлен, `handoff_state` держит приёмку заблокированной до VER-010 — это гейт релиза, не дефект дизайна.

## Находки

**Блокеров нет.** `BLOCKER-SAFETY`: 0. `BLOCKER`: 0.

### MAJOR-1 — точка запрета resume на collect-этапе не закреплена за кодом
AD-003 `point1_collect` говорит «prohibit resume», но механика CID (`downgrade_transition_order`) описана в терминах `_run_once`. В `do_POST` explicit `conversation_id` из тела и `_cid_acquire`/`_session_claim` выполняются **после** collect ([server.py](/Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/bridges/agy-bridge/server.py:3669)). Если Coder пропустит именно этот участок, stripped-запрос возобновит грязную сессию. Требование и оракул uf06 есть, поэтому это MAJOR, а не BLOCKER. Рекомендация Coder/Reviewer: явный флаг в ctx, проверяемый в обоих местах захвата CID.

### MAJOR-2 — рендер оптимистичного prompt для alias-типов недоопределён
`_flatten_content` нумерует только `type=image_url` ([server.py](/Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/bridges/agy-bridge/server.py:589)). AD-002 канонизирует `input_image`/`image` в приватной копии для коллектора, но не говорит прямо, что оптимистичные `prompt`/`full_prompt` рендерятся **из той же канонизированной копии**. Рендер из оригинала даст расхождение `[image N]` ↔ порядок `[attachments]` при смешанных alias+canonical частях. Рекомендация: в uf07 добавить assert соответствия маркер↔файл для последовательности alias, затем canonical.

### MINOR-1 — env-лексемы нового флага расходятся с sibling-флагом
Существующий `_is_image_input_enabled` принимает `on`→True ([server.py](/Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/bridges/agy-bridge/server.py:695)). AD-001 `env_contract` для нового флага даёт `on`→False. Направление fail-closed (безопасно), production-путь — JSON-булевы, но операторская ловушка: пара env с одинаковым значением включит staging и молча выключит universal.

### MINOR-2 — `_image_gate_universal` при `effort=None` не специфицирован
Строгий `_image_proof_reason` пропускает проверку при `effort is None` ([server.py](/Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/bridges/agy-bridge/server.py:759)). Пакет не фиксирует то же правило для universal-гейта; Coder должен зеркалить sibling-семантику.

### MINOR-3 — VER-001/002/004 не исполнялись на Stage 2
`ruff format --check` по замороженному префиксу и нулевая дельта basedpyright достижимы только если бейзлайн уже чист под [ruff.toml](/Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/ruff.toml) и pinned-версиями. Пакет честно помечает «Not executed during Stage2»; риск недостижимого гейта снимается первым прогоном Verifier на бейзлайне до правок Coder.

## Итог

Пакет полон по AP/v1: REQ-01..06, CON-01..06, INV-01..12, RISK-001..008 трассированы в AD-001..005, QA-001..006 и VER-001..010 без разрывов. Все проверенные утверждения о коде подтвердились выборочным чтением. Дизайн реализуем без изменения frozen-тестов и fleet; production/capacity-приёмка корректно вынесена за VER-010 и не заявлена. MAJOR-1/2 закрываются на этапе Coder+Reviewer существующими оракулами uf06/uf07.

VERDICT: PASS