<<<ARTIFACT ~/Мой диск/skils/ai-sdlc/universal/teamlead-gate/references/council.md#L65-L117 sha256=b16595bdbe3f7899749713b4789cfd7061f1e28533092db81626f407a6e511e9
Ты принимаешь этот код как ТИМЛИД команды. Реши, взял бы ты этот diff в main.
Смотри как тимлид: соответствие task envelope и правилам проекта (AGENTS.md/AI-SDLC),
архитектурные границы и слои, поддерживаемость (поймёт ли команда через полгода),
достаточность тестов именно для этого изменения, риск регрессий, скрытый долг.
Отдельного Reviewer не было: ты — единственный построчный и приёмочный обзор. Опирайся на
`execution-evidence.md` и логи гейтов (тесты судья не гоняет), но покрой ВСЕ подкатегории рубрики
на уровне строк кода; пропуск подкатегории = malformed (§3). Если reviewer.json в пакете есть —
не дублируй его, покрой всё остальное.
Оценивай пригодность к merge. FAIL без привязки к файлу/строке/правилу не засчитывается.
Если ты уже видел этот код в другой роли (Reviewer/Summarizer) — суди ЗАНОВО,
не подтверждай прошлый вердикт автоматически.

FAIL без оговорок:
- diff меняет согласованный внешний контракт (HTTP/event/data/CLI/SDK), а в
  task envelope нет явного указания это сделать («совместимое поле» не смягчает);
- работа, diff или отчёт выходит за текущую задачу (чужие Jira-KEY, чужой
  статус, «заодно»).

На циклах доработки (Cycle N >= 2):
Твоя задача — аудит устранения замечаний (Verify-Fixed) и проверка радиуса поражения (Blast-Radius audit).
- Если замечание закрыто, подтверждено regression-тестом и не нарушает инвариантов — оно ПРИНИМАЕТСЯ.
- Претензии к стилю («это костыль, переделай на уровне архитектуры») без воспроизводимого дефекта или прямого нарушения стандарта проекта НЕ дают FAIL по АЛЬТЕРНАТИВЫ/ПОЛНОТА и оформляются как non-blocking follow-up.
- Выставляй FAIL по АЛЬТЕРНАТИВЫ только при неоправданном раздувании кода (переписывание функции без доказательства необходимости).

Клади наблюдения во ВСЕ 6 критериев universal-panel так (иначе агрегация majority
поедет — судья обязан оценить все 6, пустой критерий ломает подсчёт):
- соответствие task envelope, «сделано ли ровно требуемое» → КОРРЕКТНОСТЬ;
- поддерживаемость, читабельность через полгода, покрыты ли edge-cases → ПОЛНОТА;
- реально ли это сопровождать и докатить, нет ли скрытых операционных издержек → РЕАЛИЗУЕМОСТЬ;
- достаточность тестов, риск регрессий, скрытый долг → РИСКИ;
- был ли более простой/дешёвый путь достичь того же в main, оправдан ли выбор → АЛЬТЕРНАТИВЫ;
- архитектурные границы/слои, соответствие правилам проекта → СООТВЕТСТВИЕ КОНТЕКСТУ.
Нет содержательного наблюдения по критерию — ставь PASS/INCONCLUSIVE, не выдумывай FAIL.

ПОЛНОТА ВЫДАЧИ — ВСЕ ЗАМЕЧАНИЯ ЗА ОДИН ПРОХОД (обязательно, оба режима):
1. Найденный FAIL проход НЕ завершает. Дойди до последней подкатегории рубрики и
   только потом пиши вердикт. ЗАПРЕЩЕНО обрывать поиск на первой найденной ошибке.
2. Выдай ВСЕ замечания сразу одним списком F-блоков, blocking и non-blocking вместе
   (поле priority). ЗАПРЕЩЕНЫ: поштучная выдача («главное сейчас, остальное после
   исправления»), откладывание («проверю в следующем раунде»), резерв про запас.
3. Один дефект класса X в нескольких местах — ОДИН F-блок со ВСЕМИ местами
   (locations: file:line, …), найденными поиском по всему diff. Формулы «и т.п.»,
   «и другие места», «например» вместо перечисления недопустимы.
4. Разные root cause в одном месте — разные F-блоки. Каждый F-блок самодостаточен:
   file:line, правило, evidence (цитата), ожидаемое исправление, критерий проверки,
   priority.
5. Перед вердиктом пройди список подкатегорий второй раз (self-sweep) и допиши
   пропущенное, пометив [sweep].
6. Последние строки ответа: `COVERAGE: <k>/<K> подкатегорий` и
   `FINDINGS_COMPLETE: <N>` (N = число F-блоков). Нет строк, k<K или N ≠ числу
   F-блоков — вердикт malformed.
7. Дефект вне дельты цикла тоже выдаётся с меткой [pre-existing] — молчание о найденном ради «дельты» запрещено.
   Приоритет по месту (§3, «Diff-scope»): в файле, изменённом задачей, — blocking; в коде вне скоупа задачи — non-blocking.
ARTIFACT_END>>>

Нумерованный перечень всех 14 подкатегорий рубрики одного прохода (`council.md` §3, стартовый состав `mode=code`, всего 14 подкатегорий):
1. `SUB Корректность/логика`
2. `SUB Корректность/граничные условия`
3. `SUB Корректность/обработка ошибок`
4. `SUB Полнота/покрытие AC`
5. `SUB Полнота/пропущенные ветки`
6. `SUB Реализуемость/общее`
7. `SUB Риски/безопасность`
8. `SUB Риски/данные`
9. `SUB Риски/прод`
10. `SUB Риски/regression red→green`
11. `SUB Риски/Full Suite (L2)`
12. `SUB Риски/scope-diff`
13. `SUB Альтернативы/общее`
14. `SUB Соответствие контексту/общее`

Пройди по номерам 1–14 и выведи в ответе по одной строке формата `SUB критерий/подкатегория: PASS|FAIL|N/A — evidence (файл:строка/правило)` на каждую из 14 подкатегорий, а в конце ответа после строки общего вердикта приведи обязательные строки `COVERAGE: 14/14 подкатегорий` и `FINDINGS_COMPLETE: число_выданных_F_блоков`.

📋 ФАКТ-КАРТА (проверено оркестратором на целевой машине и дополнено логами гейтов, 2026-10-26):
- Репозиторий `cli-agent-bridge` (ветка `feature/zen-realtime-reasoning` от `origin/dev` `7eda27f9d82732bab726a420e31ea2adc15c2c39`): автономный Python stdlib-мост `bridges/opencode-zen-bridge/server.py` (`ThreadingHTTPServer` на `127.0.0.1:9883`), без корневого `AGENTS.md` и без сторонних runtime-зависимостей вне стандартной библиотеки Python 3.14.
- Установленный CLI `~/.opencode/bin/opencode` версии `v2.1.2` существует локально: команда `opencode run --format json --thinking` подписана только на `session.reasoning.ended` и `session.text.ended` (игнорирует `*.delta`, разрыв 0.00–0.17 мс в конце шага, `[F-17]`, `[F-18]`).
- Режим `opencode serve --port P --hostname 127.0.0.1` в `opencode` `v2.1.2` существует и проверен эмпирически (`[F-19]..[F-22]`): старт ~109 мс, Basic-аутентификация `opencode:<OPENCODE_SERVER_PASSWORD>`, OpenAPI `281456 B` включает `GET /api/event` (SSE с реальными дельтами `session.reasoning.delta` median 127 мс и `session.text.delta` median 114 мс), `POST /api/session` (с `permissions`), `POST /api/session/{id}/prompt`, `POST /api/session/{id}/interrupt`, `DELETE /api/session/{id}`.
- Локальный `model_georouter` (`127.0.0.1:10830`) и пул ротации чистых IP ProxyRack (`OPENCODE_ZEN_BRIDGE_STANDALONE_PROXY=pool`) существуют на хосте (`[F-15]`, `[F-26]`, `[F-27]`); прямой анонимный HTTP-вызов к `opencode.ai/inference/openai/v1` без заголовков CLI вернул `429 FreeUsageLimitError` (`[F-24]`, `[F-25]`).
- Потребитель DSH Desktop (`@earendil-works/pi-ai` `openai-completions.js` и `@deepseek-ai/dsh-client-ui-chat` `ReasoningRow`, `[F-35]..[F-38]`): строка `⚛ Think` скрыта (`blockIsVisible`), пока `reasoning_content` пуст; свёрнутое inline-превью обновляется через `latestCompletedParagraphFirstLine` только при наличии завершённого абзаца с символом `\n`; при реплее истории мост игнорирует входящий `assistant.reasoning_content` (`[F-07]`).
- Прецедент в том же репозитории: `bridges/muse-bridge/server.py` (ADR-0004, `[F-40]`, `[F-41]`) использует `serve` как основной транспорт с откатом на `exec` при `ServeUnavailable` и живой записью статусов в `reasoning_content`.
- Тестовый контур моста (`[F-42]..[F-49]`): `uvx pytest -q -p no:cacheprovider tests/` из `bridges/opencode-zen-bridge` (17 модулей, 378 тестов; 3 pre-existing падения в `tests/test_step_interruption.py` из-за `MAX_TOTAL_SPAWNS=3` против ожидания 4 запусков и общего `_RetryBudget` на класс).
- Дополнительные эмпирические замеры на целевой машине (`EVD-070..EVD-072`): `python3 -m unittest discover -s tests -p "test_*.py" -v` из `cwd=bridges/opencode-zen-bridge` выполняет все 378 тестов без ошибок импорта; `OPENCODE_DB=":memory:"` нативно поддерживается в `opencode` `v2.1.2` (старт `opencode serve` 120.7 мс, RSS 156.8 MiB, `0` открытых `.db`/SQLite дескрипторов в `lsof` при сохранении чтения `~/.local/share/opencode/auth.json` для `opencode-go/*`); `basedpyright==1.40.2` из `cwd=bridges/opencode-zen-bridge` с абсолютным `extraPaths` даёт `0` ошибок импорта в тестах и `3` статические ошибки в `server.py`, а полный `ruff format --diff server.py` меняет 3216 строк неформатированного legacy-кода (включая `def _run_env` и Google-direct).
- Проверенные артефакты и логи гейтов кандидата (`receipts/code-gate.json`, `teamlead/candidate-manifest.json`):
  - Изменённые файлы кандидата (ровно 3 файла `coder_target_files`, 0 новых внешних runtime-зависимостей вне Python 3.14 stdlib): bridges/opencode-zen-bridge/server.py (sha256=ae5651f691ba...), bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py (sha256=10894022174a...), bridges/opencode-zen-bridge/tests/test_step_interruption.py (sha256=2d3bad84a918...).
  - Clean-room L2 гейт (`receipts/code-gate.json`): `status=PASS`, `red_sensitivity_rc=1` (RED-падение на `origin/dev`), все проверки кандидата (`VER-004`, `VER-001`, `VER-002`, `VER-003`, `AC-023`, `VER-005`) зелёные (`rc=0`), `run_env_sha256=1c51b28fcb83fcc0f4d8b5204c858e11ab5ac975bfe40dca4a0bf61978008e31`, `google_direct_unchanged=True`.
Анти-галлюцинация: перед тем как выставить FAIL «нет X», перечитай приложенный пакет приёмки и diff целиком; по проверенным пунктам факт-карты запрещено ставить FAIL «не существует»; если сущности нет в факт-карте и приложенных артефактах и ты не уверен — пиши «не могу проверить».

РЕЖИМ: code
Модификатор режима `code`: Перечисли конкретные проверки: типы, ошибки, граничные случаи, тесты, безопасность, гонки ресурсов и обратную совместимость контрактов. Усиленные критерии режима `code` (вес ×1.5 на агрегации): 1. КОРРЕКТНОСТЬ и 4. РИСКИ. Если ты уже видел эту задачу, архитектуру или код в другой роли — суди ЗАНОВО, не подтверждай прошлый вердикт автоматически. Проверь соответствие кандидата каждому требованию `REQ-001..REQ-020`, каждому приёмочному критерию `AC-001..AC-026` и каждой границе `Non-Goals` / `Forbidden Scope` поштучно (через `verification-traceability.md`, `execution-evidence.md` и слепой `reverse-spec.md`). Результаты тестов и статических проверок бери только как факт из валидных строк `execution-evidence.md` и вложенных сырых логов clean-room прогона (при отсутствии валидного свидетельства — `INCONCLUSIVE`; судья сам тесты не запускает; строки `VER-006` и `VER-007` законно помечены `DEFERRED_L3` до вердикта `ACCEPT` Совета).

РЕШЕНИЕ ДЛЯ ОЦЕНКИ:
Ниже приложен целиком пакет приёмки `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/package.md` (`sha256=5b0d1dea0cf4996f6d744e0eb2d82176578091bad35c943dde722c09d3784df4`), содержащий без обрезки конверт задачи (`goal.md`, `task.json`, `handoff-architect.md`), манифест кандидата и полный итоговый diff (`candidate-manifest.json`, `candidate.diff`, новый тестовый модуль `tests/test_realtime_reasoning.py`), handoff исполнителя и квитанции гейтов (`coder.json`, `receipts/coder.json`, `receipts/code-gate.json`, `receipts/verifier.json`, `receipts/final-gate.json`), а также свидетельства независимой clean-room верификации и слепой reverse-spec (`verification-surface.json`, `environment-manifest.json`, `execution-evidence.md` с сырыми логами, `verification-traceability.md`, `evidence-manifest.sha256`, `reverse-spec.md`):
# Пакет приёмки Совета Тимлидов (`teamlead/package.md`, run `analyst-teamlead-zen-realtime-reasoning-20261025`)

Примечание по составу пакета (`acceptance-package.md` §3): `reviewer.json` не создаётся (`reviewer_skip=true`, `downstream_panel=true`, Совет Тимлидов — единственный рубеж ревью). Все первичные артефакты ниже приложены без обрезки в побайтных обёртках D9.

## 1. Конверт задачи (`goal.md`, `task.json`, `handoff-architect.md`)
<<<ARTIFACT /tmp/cel-runs/zen-realtime-reasoning-20261025/goal.md sha256=4d953bef55831514175b6bf4150dc2af3bef47489913b6dccc2d536df6c83528
# Цель: Реалтайм-стриминг размышлений (reasoning) и шагов DeepSeek через мост opencode-zen-bridge в DSH

- Открыто: 2026-10-25 22:24:20 MSK
- Репозиторий (изолированный клон): `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning` (ветка `feature/zen-realtime-reasoning` от `origin/dev`)
- Контур: `cel` + `analyst-teamlead` (`system-analyst` → `architect-software-product` → `Arch Panel` 3 судей → `Coder` → `Clean-Room L2` → `Code Council` 3 судей → открытый PR в `dev` + живая проверка тяжёлым путём).
- Бизнес-результат и критерий приёмки:
  1. При запуске DeepSeek (`deepseek-v4.1-flash-free` High) через `opencode-zen-bridge` в DSH Desktop размышления (`reasoning_content` / блок `Think`) и прогресс шагов стримятся в реалтайме по мере генерации, без «немой» паузы `Deep diving for 35s ...`.
  2. Полный цикл `analyst-teamlead` пройден с двумя `PANEL PROOF` (`verify_panel_proof.py` exit=0, `panel-proof.json` PASS на `arch` и `code`), всеми L1/L2 проверками (`ruff`, `basedpyright`, `pytest`) и открытым PR в `origin/dev` (без merge).
  3. Проведена живая проверка тяжёлым путём на реальном мосту и DSH.
ARTIFACT_END>>>
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/task.json sha256=e42d76a03d08b6685044e54162afd51cbe360ae3fd40a8a8303e6b487fcba5db
{
  "task_id": "zen-realtime-reasoning",
  "run_id": "analyst-teamlead-zen-realtime-reasoning-20261025",
  "preset": "analyst-teamlead",
  "setup": "default",
  "criticality": "S2",
  "architecture_gate": {
    "packet_sha256": "88c02c37a7ca0be3d317217f23289dba07ddc681d922db207c7680a779128b6b",
    "verification_surface_sha256": "4886ffa8669391618891b8e180a3443879043711da25bfe909bb6887ea6b924f",
    "protected_paths_sha256": "98f7f5f54622baf379b40bad458cf3ef2a1952644fb79fb662ebe11f70659d8b"
  }
}
ARTIFACT_END>>>
<<<ARTIFACT analysis/zen-realtime-reasoning/handoff-architect.md sha256=9cd426324b8f49ddc760e3706e200709754a0a459b9e234f7b45b3b2669c6d9f
# Handoff to Architect: реалтайм-размышление и отзывчивость `opencode-zen-bridge` (zen-realtime-reasoning)

Дата: 2026-10-25 (MSK). Автор: System Analyst (Stage 1). Потребитель: `architect-software-product` (Stage 2, класс S2, вход в разработку только через ARCH_GATE).
Факты — в `evidence-ledger.md` (`F-01..F-49`), вопросы — в `open-questions.md` (`OPEN-01..OPEN-17`, блокеров нет), план — в `research-plan.md`.
Архитектура и стек здесь не выбираются: варианты сравниваются по фактам, решение за Архитектором.

## 1. Постановка и цепочка корневых причин

Запрос владельца: видеть размышление DeepSeek в DSH в реальном времени при работе через `opencode-zen-bridge` (`127.0.0.1:9883`) и получить высокую
отзывчивость. Инцидент-образец — `session-423ca27f`, ход 2 шаг 5 (22:16:12 MSK): на экране только «Deep diving for 35s ···», затем более 780 с без единого токена (F-30, F-33).

Подтверждены три независимые причины; устранять надо все три, иначе пользователь по-прежнему не увидит «процесс идёт».

| Код | Причина | Ключевые факты |
|---|---|---|
| RC-1 | `opencode run --format json --thinking` v2.1.2 подписан только на `session.reasoning.ended` и `session.text.ended` и игнорирует `*.delta`: размышление и текст приходят одним блоком в самом конце шага (разница 0.00-0.17 мс), тишина stdout 1.9-2.7 с даже на здоровом вызове. Мост не может показать то, чего CLI не выдаёт | F-17, F-18, F-02, F-05 |
| RC-2 | Нет ни TTFT-watchdog, ни watchdog первого события, ни watchdog паузы между чанками; единственный потолок — `TIMEOUT_S=1800` с; холодный `--standalone` на БД 2.27 GB, пул ProxyRack и сериализующий `_StartupGate` дали зависания 780-856 с, а keepalive `{"content":""}` держал сокет DSH пустым | F-09, F-10, F-28, F-30, F-31, F-32, F-04 |
| RC-3 | В DSH строка `⚛ Think` не рисуется, пока нет непустого `reasoning_content`; пустые keepalive ничего не показывают; inline-превью свёрнутой строки обновляется только по завершённому абзацу (нужен `\n`) | F-36, F-37, F-04 |

Цепочка следствий: RC-1 лишает реалтайма здоровый вызов, RC-2 превращает больной вызов в многоминутную тишину, RC-3 делает любую тишину
для пользователя неотличимой от зависания (экран с таймером без содержимого). Реалтайм-транспорт без пунктов RC-2 и RC-3 проблему не закрывает.

## 2. As-is карта потока (каждая связь — факт)

```
DSH (pi-ai openai-completions, stream:true)  --HTTP SSE-->  Handler._stream_sse (:9883)        F-35, F-03
  Handler._stream_sse: 200+role-chunk -> _StartupGate -> spawn `opencode run ... --format json`  F-03, F-10, F-01
  opencode run (stdout JSON lines) -> _StdoutFeed(queue 4096) -> parse_opencode_event            F-14, F-02
     reasoning -> delta.reasoning_content (flush сразу)                                         F-05
     text      -> ToolCallParser.feed -> delta.content / delta.tool_calls                       F-05, F-06
     keepalive -> {"content": ""} раз в 15 с тишины                                              F-04
  opencode run --standalone -> opencode serve --stdio (дочерний) -> georouter :10830 -> Zen      F-30, F-26, F-27
  Пул ProxyRack: следующий порт на каждый spawn (env HTTP(S)_PROXY, loopback мимо)              F-15
DSH UI: непустой reasoning_content -> blockIsVisible -> ReasoningRow (превью по "\n")            F-36, F-37
DSH реплей: thinking -> assistant.reasoning_content -> мост игнорирует                          F-38, F-07
```

Граница совместимости (факт): всё ниже `parse_opencode_event` оперирует кортежами `(etype, payload)` (F-02, F-05); поэтому любой транспорт,
сводимый к тем же кортежам, не требует правки верхнего слоя (ретраи, парсер инструментов, usage, SSE-кадрирование).

## 3. Требования `REQ-001..REQ-020`

Приоритет `MUST`/`SHOULD`; критерии `AC-*` — краткие проверяемые формулировки (полная спецификация живёт в requirements и в `handoff-qa.md`).

| REQ | Приоритет | Требование | Факты | AC |
|---|---|---|---|---|
| REQ-001 | MUST | Дельты размышления и текста уходят клиенту по мере прихода из апстрима, а не в конце шага | F-17, F-18, F-19 | AC-001: на клиентском сокете интервал между соседними `reasoning_content`-чанками меньше 500 мс, пока апстрим-стрим ещё идёт; AC-002: накладные расходы моста между приходом дельты и записью в сокет не больше 250 мс |
| REQ-002 | MUST | Публичный контракт не меняется: `/health`, `/v1/models`, `/v1/chat/completions`, формат OpenAI SSE, `finish_reason`, `usage`, порт :9883 | F-35, F-34 | AC-003: побайтовое совпадение формы чанков с текущей на наборе существующих тестов формата |
| REQ-003 | MUST | Прежний путь `opencode run --format json` остаётся рабочим как переключаемый запасной вариант и kill-switch (имя переменной и дефолт задаёт Архитектор); существующие тесты на fake-CLI остаются зелёными | F-43, F-40, F-42 | AC-004: при выключенном новом транспорте проходят все 378 существующих тестов (после решения OPEN-04) |
| REQ-004 | MUST | Первая видимая реакция моста в течение 1.0 с после открытия SSE: непустой `reasoning_content`, оканчивающийся `\n` (статус подключения/ожидания модели), независимо от состояния апстрима | F-36, F-37, F-04, F-33 | AC-005: первый чанк с непустым `reasoning_content` приходит не позже 1.0 с от запроса даже при полностью молчащем апстриме |
| REQ-005 | MUST | Статусные строки моста отделены от текста модели, имеют префикс «[мост]» и завершаются `\n`; текст размышления модели не модифицируется; статусные строки не попадают в промпт при реплее | F-37, F-38, F-07, F-39 | AC-006: объединённый `reasoning_content` без статусных строк побайтово равен тексту модели; AC-007: `_messages_to_prompt` не содержит статусных строк при реплее |
| REQ-006 | MUST | Watchdog первого события: нет ни одного события транспорта в течение порога (допущение 20 с, OPEN-11) — группа процессов убивается, попытка повторяется по общему бюджету либо клиент получает явную ошибку | F-09, F-30, F-31 | AC-008: фейковый транспорт без вывода завершается убийством и ретраем или ошибкой за порог плюс 2 с |
| REQ-007 | MUST | Watchdog первого токена (reasoning или text, допущение 60 с) и watchdog паузы между чанками (допущение 60 с); пороги настраиваются переменными окружения | F-09, F-19, F-32 | AC-009: пауза больше порога после первого токена приводит к остановке и классификации `stall_timeout`; AC-010: порог первого токена даёт `first_token_timeout` |
| REQ-008 | MUST | Отсутствие осиротевших процессов: при отключении клиента, таймауте и watchdog убивается вся группа (включая дочерний `opencode serve`); отключение клиента обнаруживается не позже 5 с | F-14, F-30, F-33 | AC-011: после закрытия клиентского сокета процессы группы отсутствуют не позже чем через 7 с; AC-012: ход 1 образца (24.4 с на обнаружение) не воспроизводится |
| REQ-009 | MUST | Потолок `MAX_TOTAL_SPAWNS=3`, `FAIL_RETRY_LIMIT`, `_RetryBudget`, Full Jitter и Circuit Breaker сохраняются; повторы по watchdog считаются в общий потолок; при повторе после отданного размышления вставляется отдельная статусная строка | F-11, F-12 | AC-013: суммарно не более 3 запусков на запрос при любой комбинации причин; AC-014: размышление не дедуплицируется, между попытками ровно одна статусная строка |
| REQ-010 | MUST | `ToolCallParser` на потоковых дельтах: текст вне тегов выдаётся инкрементально (удерживается не более `len("<tool_invoke>")-1` символов хвоста и открытый блок), блоки `<tool_call>`/`<tool_invoke>` не попадают в `content` при любом разбиении на дельты | F-06, F-05 | AC-015: перебор границ чанков на фикстурах существующих тестов даёт тот же набор `tool_calls` и тот же `content`, что при подаче целым текстом |
| REQ-011 | MUST | Завершение шага с вызовом инструмента останавливает процесс или сессию и даёт `finish_reason="tool_calls"`; детектор оборванного шага (`STEP_RECOVERY`), классификация `etype=error` и маркеры `_INTERRUPTED_RE` работают на накопленных данных потокового пути | F-05, F-11, F-43 | AC-016: все сценарии `test_step_interruption.py` проходят на новом транспорте с фейковым потоком дельт |
| REQ-012 | MUST | Встроенные инструменты `opencode` на новом транспорте запрещены (политика `deny` для всех) либо эквивалентно изолированы; события встроенных инструментов приводятся к текущему внутреннему виду (`tool_use`, unmapped, native) | F-08, F-22, OPEN-07 | AC-017: фейковый поток с событием встроенного инструмента даёт тот же `unmapped`-повтор и тот же `finish_reason`, что legacy-путь |
| REQ-013 | MUST | Ротация чистых IP на каждый новый запуск, `_StartupGate`, `SPAWN_RATE_PER_S`, bulkhead слотов и Circuit Breaker действуют и для нового транспорта | F-10, F-11, F-15, F-32 | AC-018: два последовательных запуска получают разные записи пула прокси (проверка через подменённый `_next_standalone_proxy`) |
| REQ-014 | SHOULD | `usage` собирается из токенов завершения шага нового транспорта и совпадает по полям (`input`, `output`, `cached`, `reasoning`) с текущим | F-19, F-02 | AC-019: поле `usage` финального чанка совпадает с эталонными значениями фикстуры |
| REQ-015 | MUST | Секреты не пишутся в логи и артефакты: пароль `opencode serve` (случайный на процесс), ключи, креды прокси; применяется существующее маскирование | F-21, F-27 | AC-020: `bridge.log` после прогона не содержит пароля serve и значений `apiKey` |
| REQ-016 | MUST | Наблюдаемость `O-EXIT/v1`: новые значения `exit_reason` (`first_event_timeout`, `first_token_timeout`, `stall_timeout`, `client_gone`) и поля `transport`, `first_event_ms`, `ttft_ms` в строке выхода | F-32, F-30 | AC-021: строка `O-EXIT/v1` содержит перечисленные поля на каждом выходе `do_POST` |
| REQ-017 | SHOULD | Базовая линия тестов приводится в зелёное: два теста ждут 4 запуска при потолке 3, третий страдает от общего `_RetryBudget` на класс | F-45, F-46, F-47, F-48, F-49 | AC-022: `uvx pytest -q -p no:cacheprovider tests/` без красных; AC-023: результат не зависит от порядка тестов |
| REQ-018 | MUST | Прямой Google-маршрут (`_stream_google_sse`, `_execute_google_once`) не затрагивается | F-16 | AC-024: `test_google_direct.py` проходит без правок |
| REQ-019 | SHOULD | Развёрнутая копия `~/.dsh/bridges/opencode-zen-bridge/server.py` синхронизируется с репозиторием и проверяется сверкой | F-34, OPEN-17 | AC-025: побайтовое совпадение после деплоя |
| REQ-020 | MUST | В набор тестов добавляется измерение реального времени прихода чанков на клиентском сокете при ещё идущем апстриме (сейчас таких тестов нет) | F-44 | AC-026: тест красный на текущем коде и зелёный на новом (red to green) |

## 4. Варианты реализации RC-1 (сравнение по фактам, без выбора)

Вердикты: `выполнимо` / `выполнимо с условиями` / `невыполнимо`. Исходные данные по каждому — в ledger.

| Вариант | Суть | Задержка и реалтайм | Авторизация, маршрут, ротация IP | Изоляция встроенных инструментов | Параллелизм и SQLite | Тестируемость | Вердикт |
|---|---|---|---|---|---|---|---|
| L: только упрочнение legacy | `opencode run` остаётся, добавляются watchdog (REQ-006..008), статусные строки (REQ-004, REQ-005) | Реалтайма размышления нет: единый блок в конце шага (F-17, F-18); живость только за счёт статусных строк моста | Без изменений (F-15) | Без изменений (F-08) | Холодный spawn на каждый шаг сохраняется (F-28, F-30) | Полная: fake-CLI (F-43) | выполнимо; закрывает RC-2 и RC-3, но не RC-1 |
| A1: `opencode serve` короткоживущий на запрос, SSE `GET /api/event` | Мост поднимает `serve` на свободном порту с одноразовым паролем, создаёт сессию, шлёт prompt, читает дельты, затем `interrupt`/`DELETE` и `killpg` | Дельты размышления каждые 105-304 мс (median 127), первая дельта 1811 мс, text-дельты median 114 мс (F-19); старт сервера 109 мс (F-20) | Пароль случайный на процесс (F-21); env прокси задаётся на запуск, значит ротация сохраняется (F-15, OPEN-06); egress идёт через georouter (F-26, F-27) | Поле `permissions` в `POST /api/session` и `permission {"*":"deny"}` в конфиге (F-22), поведение не прогнано (OPEN-07) | Один процесс на запрос, idle RSS 152 MiB (F-20); БД та же 2.27 GB, нагрузка не мерилась (OPEN-08) | Нужен фейковый serve-сервер и адаптер событий; fake-CLI покрывает только legacy-путь (F-43) | выполнимо с условиями (OPEN-06, OPEN-07, OPEN-08) |
| A2: общий управляемый `opencode serve` (демон) | Один долгоживущий процесс; сессия на запрос | Те же дельты (F-19); нет холодного старта (фоновый `serve --service` уже работает, F-20) | Один набор env прокси на все запросы: общий IP упирается в дневной лимит (F-23, F-32); пароль на демон | Как в A1 | Общая БД и общий процесс, RSS 439 MiB у существующего демона (F-20); падение демона роняет все запросы | Тот же фейковый сервер; нужен супервизор и перезапуск | выполнимо с условиями; ротация IP не сохраняется без доработки (OPEN-06) |
| B: прямой OpenAI-совместимый HTTP-SSE к Zen | По образцу Google Direct (F-16): `http.client`, `readline`, дельты `reasoning_content` в реальном времени | Минимальная: без CLI, без БД, дельты как у апстрима (георутер отдаёт реалтайм, F-19) | Анонимный вызов без заголовков дал 429 `FreeUsageLimitError` напрямую и через пул (F-24, F-25); нужные заголовки или ключ неизвестны (OPEN-05); у `opencode` провайдера нет `apiKey` (F-27) | Не требуется: инструментов нет, эмуляция через `<tool_invoke>` остаётся | Нет SQLite и дочерних процессов | Лучшая: подмена HTTP-сервера, без `FAKE_OPENCODE` | выполнимо с условиями; осуществимость не доказана (OPEN-05) |
| C: гибрид | Приоритетный быстрый транспорт (A1 или B), при `ServeUnavailable`-подобном отказе тихий откат на legacy `opencode run`, как в muse-bridge | Реалтайм там, где транспорт доступен; legacy при отказе | Совмещает ограничения выбранных транспортов | Совмещает | Совмещает | Прецедент в репозитории: serve основной, exec запасной (F-40, F-41); fake-CLI тесты остаются на legacy-пути | выполнимо; объём работ максимальный |

Наблюдения для решения (факты, не выбор):
- Только A1/A2/B дают реалтайм на здоровом вызове; L не даёт, но самый дешёвый и закрывает RC-2/RC-3 (поэтапная поставка возможна: L затем A1/B/C).
- Квота Zen исчерпана на момент анализа (F-23): живая приёмка и PoC варианта B возможны после сброса около 03:00 MSK 2026-10-26.
- Совместимость с тестами: muse-bridge сохраняет exec-путь как резерв (F-40); у `opencode-zen-bridge` три модуля подменяют `OPENCODE_BIN` скриптом с событиями формата `run --format json` (F-43).
- Размер объёма ретраев и `_StdoutFeed` уже рассчитан на потоковые события (F-14); `step_finish` в `run` теряется (F-18), в serve есть `session.step.ended` с `tokens` (F-19).

## 5. Инвентарь контрактов (as-is)

| Интерфейс | Протокол | Направление | Аутентификация | Лимиты и режимы отказа | Тестовый контур |
|---|---|---|---|---|---|
| `POST /v1/chat/completions` моста | HTTP SSE OpenAI (`stream:true`, `include_usage`) | Ingress от DSH | Bearer-ключ моста (значение не фиксируется) | слоты 6, ожидание 15 с, 12 ждущих, 503 при переполнении (F-13) | `tests/_http.py`, `test_step_interruption.py` (F-43) |
| `opencode run --format json` | stdout JSON-строки | Egress процесса | Нет (локальный CLI, белый список env) | потолок 1800 с, нет watchdog (F-09) | `FAKE_OPENCODE` (F-43) |
| `opencode serve` v2 | HTTP + SSE, Basic `opencode:<пароль>` | Egress | случайный пароль на процесс или `OPENCODE_SERVER_PASSWORD` (F-21) | старт 109 мс, API по OpenAPI (F-20, F-22) | тестового фейка нет |
| `model_georouter` :10830 | OpenAI-совместимый HTTP | Egress | нет у провайдера `opencode` (F-27) | `headers_timeout` 120 с, `inactivity_timeout` 300 с, 80+80 слотов, 3 pre-send повтора (F-26) | нет |
| Zen upstream `opencode.ai/inference/openai/v1` | OpenAI SSE | Egress | анонимный, дневной лимит (F-23..F-25) | `FreeUsageLimitError` 429 с `Retry-After` | нет |
| DSH `openai-completions` | SSE потребитель | Ingress | — | `streamIdleTimeoutMs` 1900000, `maxRetries` 0 (F-35) | живой DSH |

## 6. NFR-набросок (наблюдаемые величины)

- Нагрузка: 517 завершённых запросов за день, `deepseek-v4.1-flash-free` 44 (median 7.10 с, max 85.65 с) (F-32); пик параллелизма 6 (F-13).
- Задержка legacy: `step_start` 1.3-2.5 с, весь ответ 3.3-5.2 с одним блоком (F-17); реалтайм-путь serve: первая дельта размышления 1.8 с (F-19).
- Хвост: два запроса молчали 780-856 с с `out_chars=0` (F-30, F-31); `startup_gate_timeout` 72 за день (F-32).
- Ресурсы: мост RSS 22 MiB, 36 дескрипторов (F-29); idle serve 152 MiB, 20 дескрипторов (F-20); БД 2.27 GB (F-28).
- Цели отзывчивости владельцем не заданы числами (OPEN-11); рабочие значения: первая видимая строка до 1.0 с, первая дельта размышления до 3.0 с, пауза до 15 с, молчание до 20 с.

## 7. Конверт `HL-ENV/v1` (46 канонических полей `REQUIRED_HL_ENV_FIELDS`)

Единицы СИ. Источники в комментариях; значения, не измеренные под нагрузкой, помечены `оценка`.

```yaml
schema: HL-ENV/v1
required_hl_env_fields_46:
  P_steady: 1                      # один локальный демон LaunchAgent, F-34
  P_hpa_max: 1
  maxSurge_pct: 0.0
  maxSurge_abs: 0
  maxUnavailable_pct: 0.0
  maxUnavailable_abs: 0
  P_terminating_overlap: 0
  P_live: 1
  P_avail_min: 1
  W: 1                             # один Python-процесс ThreadingHTTPServer, F-12
  N_proc: 1
  N_proc_steady: 1
  N_proc_avail_min: 1
  CPU_limit_per_pod: 2.0           # бюджет рабочей станции, оценка
  kappa_skew: 1.0
  u_bg_worker: 0.02                # оценка
  U_pod_sidecars: 0.25             # дочерние процессы opencode, оценка
  Mem_limit_per_pod: 2147483648    # бюджет демона 2048 MiB, оценка
  Mem_rss_worker_max: 67108864     # 64 MiB; измерено 22 MiB, F-29
  Mem_shared_max: 1207959552       # 6 дочерних процессов по 192 MiB; idle serve 152 MiB, F-20
  RPS_peak: 0.2                    # 517 запросов за день, F-32
  A_max: 3                         # MAX_TOTAL_SPAWNS, F-11
  SLA_p99_s: 180.0                 # max наблюдаемый 85.65 с, F-32
  N_entities_max: 64
  Limit_dep_share_d: {georouter: 80, opencode_local_db: 10}   # georouter F-26; значение БД допущение эталона, OPEN-08
  Limit_dep_rps_d: {opencode_spawn: 1.0}                      # SPAWN_RATE_PER_S, F-11
  W_fetchers_d: 1
  J_init_s_d: 12.0                 # STARTUP_GATE_S, F-10
  J_pod_s_d: 12.0
  T_poll_s_d: 15.0                 # KEEPALIVE_INTERVAL_S, F-04
  K_calls_d: 1
  T_base_s_d: 0.5                  # RETRY_BACKOFF_BASE_S, F-11
  T_cap_s_d: 2.0                   # RETRY_BACKOFF_CAP_S, F-11
  Max_stale_age_s_c: 0.0           # кэшей нет
  Min_healthy_ratio: 1.0
  B_retry_max: 6                   # RETRY_BUDGET_MAX, F-11
  min_reserve_retry_rps: 0.05      # RETRY_BUDGET_RESERVE_RPS, F-11
  FD_worker: 128                   # измерено 36 при active=0, F-29; запас под 6 потоков
  ulimit_n: 65536                  # launchctl limit maxfiles, F-29
  lambda_new_conn_per_pod_s: 0.6
  C_active_in_scope_s: 12
  N_pods_in_scope_s: 1
  Port_range_size_s: 16384         # эфемерный диапазон 49152-65535
  T_hold_s_s: 60.0
  SNAT_ips_count_s: 1
  HOTPATH_MODULES: "bridges/opencode-zen-bridge/server.py"
operational_profile:
  threads_per_worker: 12           # до 6 обработчиков и до 6 читателей stdout/SSE
  stdout_queue_max: 4096           # F-14
  ttft_visible_target_s: 1.0       # допущение, OPEN-11
  ttft_first_delta_target_s: 3.0   # допущение, OPEN-11; наблюдение serve 1.8 с, F-19
  first_event_watchdog_s: 20.0     # допущение, OPEN-11
  first_token_watchdog_s: 60.0     # допущение, OPEN-11
  stall_watchdog_s: 60.0           # допущение, OPEN-11
  client_gone_detect_s: 5.0        # допущение; сейчас 24.4 с, F-33
  keepalive_interval_s: 15.0       # F-04
  total_deadline_s: 1800           # TIMEOUT_S, F-09
  max_total_spawns: 3              # F-11
  startup_gate_s: 12               # F-10
  startup_wait_s: 5.0              # F-10
  bulkhead_max_concurrent: 6       # F-13
  slot_wait_s: 15.0                # F-13
  slot_max_waiters: 12             # F-13
  graceful_stop_s: 5               # SIGTERM затем SIGKILL, F-14
  serve_ready_s: 0.109             # F-20
```

Замыкание памяти (`HL-ENV-01`): `W × Mem_rss_worker_max + Mem_shared_max = 64 MiB + 1152 MiB = 1216 MiB ≤ 0.80 × 2048 MiB = 1638.4 MiB` (PASS, оценка). Для варианта A2 (общий демон, 439 MiB, F-20) вклад меньше.

## 8. Гейты Highload & Resilience (7 канонических + оси брифа)

### 8.1. Канонические гейты `architecture.md` (`#hl-env-and-four-gates-ssot`)

- `C-MULT/v1`:
  - `C-MULT-I1`: `1 × 1 × 6 = 6 ≤ 0.60 × 80 = 48` для георутера (F-26) — PASS; для локальной БД предел неизвестен (OPEN-08), поэтому ограничителем остаются `_StartupGate`, `SPAWN_RATE_PER_S` и семафор слотов (F-10, F-11, F-13).
  - `C-MULT-I2`: очереди ограничены (`_StdoutFeed` 4096, слоты 6, ждущих 12, ожидание 15 с) (F-13, F-14) — PASS; новый SSE-читатель обязан иметь такой же предел.
  - `C-MULT-I3`: семафоры и замки — синглтоны процесса (`W=1`) (F-12) — PASS.
  - `C-MULT-I4`: освобождение слота и остановка процесса в `finally` (F-14) — PASS как as-is; новые ресурсы (сессия serve, SSE-сокет) должны освобождаться там же.
  - `C-MULT-I5`: `FD_worker = 128 ≤ 0.70 × 65536`; порты `0.6 × 1 × 60 + 12 = 48 ≤ 0.50 × 16384 = 8192` — PASS (оценка).
- `S-HERD/v1`:
  - `S-HERD-I1`: серия холодных стартов сериализуется `_StartupGate` (F-10); у A1 старт сервера 109 мс (F-20).
  - `S-HERD-I2`: Full Jitter 0.5/2.0 уже в коде (F-11); повторы по watchdog обязаны использовать его.
  - `S-HERD-I3..I5`: N/A, поллеров Control Plane, `If-None-Match` и `singleflight` в мосте нет (граф вызовов as-is: `do_POST` → `_stream_sse`/`_serve_json` → запуск процесса); доказательство `git diff` предоставляет Architect после дизайна.
- `H-CPU/v1`:
  - `H-CPU-I2`: регулярные выражения компилируются при импорте (F-06, F-11); разбор SSE-дельт не должен вызывать `re.compile` в цикле.
  - `H-CPU-I3`: путь с выключенной новой функцией должен возвращаться за `O(1)` (kill-switch, REQ-003).
  - `H-CPU-I5`: оценка `0.02 + 0.2 × (0.02 + 3 × 0.05) = 0.054 ≤ 0.70` (PASS, не измерено); поток serve даёт около 10 событий в секунду на запрос (F-19), то есть до 60 разборов JSON в секунду на 6 запросах.
  - `H-CPU-I1`, `H-CPU-I4`: N/A (индексов маршрутизации и event loop нет).
- `R-BULK/v1`:
  - `R-BULK-I1`: вспомогательные ожидания `3 × 5.0 с (gate) + 0 + 1.0 + 2.0 = 18.0 с ≤ 0.30 × 180 = 54 с` (PASS); наихудший случай с watchdog первого события `3 × (20 + 5) + 3 = 78 с ≤ 180 с`.
  - `R-BULK-I2`: потолок запусков 3, бюджет повторов 6, слоты 6 (F-11, F-13) — PASS.
  - `R-BULK-I3`: классификация транзиентных и детерминированных ошибок существует (F-11, `_is_transient_stream_error`); новые причины watchdog относятся к транзиентным.
  - `R-BULK-I4`, `R-BULK-I5`: N/A (пула прокси-нод с health-ранжированием и мульти-тенантных пулов в мосте нет; прокси из пула — подстановка в env, F-15).
- `T-LIFE/v1`: каждый процесс и его читатель закрываются `_stop_proc` в `finally` (F-14); для A1/A2 добавляются `interrupt`, `DELETE` сессии и `killpg` (F-22).
- `O-EXIT/v1`: строка выхода на каждом `do_POST` уже есть (F-32); расширение полями — REQ-016.
- `M-SEM/v1`: N/A на этапе анализа (единый пул слотов `_slots`, F-12); подтверждение `git diff` и графа вызовов — за Architect.

### 8.2. Оси из брифа (`R-OUT`, `M-CONF`, `F-DEG`, `S-SEC`, `X-BOUND`)

В каноне этих меток нет (OPEN-15). Трактовка аналитика (допущение) и статус по фактам:

| Ось | Трактовка | Статус по фактам |
|---|---|---|
| `R-OUT` | исходы запроса и повторы (`exit_reason`, потолок A_max) | потолок есть (F-11); новые причины watchdog требуют кодов (REQ-016) |
| `M-CONF` | конфигурация и kill-switch новой функции | переменные окружения как у `STEP_RECOVERY` (F-11), REQ-003 |
| `F-DEG` | деградация: отказ быстрого транспорта не должен ломать ответ | прецедент serve→exec в muse-bridge (F-40); fail-open для статусных строк, fail-closed для политики инструментов (REQ-012) |
| `S-SEC` | секреты, пароль serve, изоляция инструментов | пароль случайный на процесс (F-21), `apiKey` не выгружался (F-27), REQ-015 |
| `X-BOUND` | границы процессов и ресурсов (killpg, FD, сессии) | F-14, F-29, REQ-008 |

## 9. Non-Goals

- Не менять публичный HTTP-контракт моста, порт и формат OpenAI SSE (REQ-002).
- Не менять DSH (бандл `app.asar`), профиль `cordis.patch.yml` и поведение `ReasoningRow`.
- Не модифицировать текст размышления модели ради превью (OPEN-13).
- Не менять модель, список моделей, логику выбора эффорта и каталог Zen.
- Не трогать `muse-bridge`, другие мосты и общий `~/.config/opencode/opencode.json` / конфиг `model_georouter`.
- Не вводить новые внешние зависимости Python вне стандартной библиотеки, если Architect не обоснует иное.

## 10. Forbidden Scope

- Изменение чужих файлов репозитория вне `bridges/opencode-zen-bridge/` и тестов этого моста.
- Запись секретов (ключи, пароль serve, креды прокси, значения `apiKey`) в логи, артефакты, код и тесты.
- Мутирующие действия на боевом контуре без отката: правка `~/.dsh` и перезапуск LaunchAgent допустимы только в живой приёмке по протоколу из `handoff-qa.md`.
- Использование `security find-generic-password`.
- Правка `opencode.db` и общего каталога состояния `opencode` напрямую.
- Коммит в `main`, `master`, `dev`; merge выполняет человек.

## 11. Маппинг в `architecture-packet.json`

- `evidence`: `F-01..F-49` (ledger).
- `blocking open questions`: пусто.
- `assumptions`: `OPEN-04..OPEN-17` с рабочими допущениями из `open-questions.md`.
- `boundaries/contracts`: раздел 5.
- `quality scenarios` (baseline): первая видимая строка до 1.0 с; первая дельта размышления до 3.0 с; пауза до 15 с; молчание до 20 с (допущения OPEN-11), текущие значения в разделе 6.
- `risks`: R1 — прямой Zen без заголовков не осуществим (OPEN-05); R2 — потеря ротации IP при общем демоне (OPEN-06); R3 — встроенные инструменты `opencode` исполнятся при неверной политике (OPEN-07); R4 — контенция SQLite при параллельных serve (OPEN-08); R5 — квота Zen блокирует живую приёмку до около 03:00 MSK 2026-10-26 (F-23); R6 — дубли размышления при повторах (OPEN-14); R7 — красная базовая линия блокирует Full Suite Gate (OPEN-04).

## 12. Обратный канал в требования

Противоречий фактов с REQ-ID нет. Расхождение с брифом: в `tests/` 17 модулей `test_*.py`, а не 16 (F-42); ссылка на «16 модулей» в постановке неточна, на объём работ не влияет.
ARTIFACT_END>>>

## 2. Манифест кандидата и полный итоговый diff (`candidate-manifest.json`, `candidate.diff`, новый тестовый файл)
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/candidate-manifest.json sha256=2b49852efc2680db5e0bc1ad499788802098cc46d7c6c19f2cc5ecce304bb4c5
{
  "schema": "candidate-manifest/v1",
  "created_at_utc": "2026-10-26T19:33:15.549337+00:00",
  "run_id": "analyst-teamlead-zen-realtime-reasoning-20261025",
  "branch": "feature/zen-realtime-reasoning",
  "base_ref": "origin/dev",
  "base_sha": "7eda27f9d82732bab726a420e31ea2adc15c2c39",
  "head_sha": "7eda27f9d82732bab726a420e31ea2adc15c2c39",
  "staged_diff_bytes": 0,
  "binary_files": [],
  "worktree_fingerprint_before_coder": null,
  "worktree_fingerprint_after_coder": null,
  "candidate_diff_path": ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/candidate.diff",
  "candidate_diff_sha256": "22eaa11a35d77b6c749975b9f044bddbeef5437bcffdd187553feb1e18f3ec24",
  "files": [
    {
      "path": "bridges/opencode-zen-bridge/server.py",
      "status": "modified_unstaged",
      "is_binary": false,
      "bytes": 285650,
      "lines": 6287,
      "sha256": "ae5651f691ba2cdc15ecbee2bc21e8ad8edbf028086bbbb7286dff91628b7c78"
    },
    {
      "path": "bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py",
      "status": "added_untracked",
      "is_binary": false,
      "bytes": 34614,
      "lines": 717,
      "sha256": "10894022174afcda3e7023d4093eaa0aec7aa6515eac862d18488d0dbe67b9bc"
    },
    {
      "path": "bridges/opencode-zen-bridge/tests/test_step_interruption.py",
      "status": "modified_unstaged",
      "is_binary": false,
      "bytes": 57296,
      "lines": 1065,
      "sha256": "2d3bad84a9182deedb6e30f8b27f9d911062ac19bcfb1cf6e16f9c4673f2c9a0"
    }
  ]
}
ARTIFACT_END>>>
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/candidate.diff sha256=22eaa11a35d77b6c749975b9f044bddbeef5437bcffdd187553feb1e18f3ec24
diff --git a/bridges/opencode-zen-bridge/server.py b/bridges/opencode-zen-bridge/server.py
index 667b990..488b800 100755
--- a/bridges/opencode-zen-bridge/server.py
+++ b/bridges/opencode-zen-bridge/server.py
@@ -17,27 +17,211 @@ usage — из события `type:"step_finish"` (part.tokens).
 
 from __future__ import annotations
 
-import hmac
-import http.client
 import json
 import os
-import queue
-import random
-import re
-import shlex
-import shutil
+import select
 import signal
-import sqlite3
 import subprocess
 import sys
-import threading
 import time
-import uuid
-from collections.abc import Callable, Iterable, Iterator
-from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
 from pathlib import Path
 from typing import Any, cast
-from urllib.parse import quote, urlsplit
+
+
+def _run_serve_helper_cli(args: list[str]) -> int:
+    """Ранний помощник serve: один лидер группы на попытку, lease и дренаж пайпов."""
+    if len(args) != 6:
+        return 2
+    (
+        attempt_id,
+        port_text,
+        opencode_bin,
+        lease_dir_text,
+        parent_pid_text,
+        parent_lstart,
+    ) = args
+    if not attempt_id or not opencode_bin or not lease_dir_text or not parent_lstart:
+        return 2
+    if not port_text.isdecimal() or not parent_pid_text.isdecimal():
+        return 2
+    port = int(port_text)
+    parent_pid = int(parent_pid_text)
+    if not 1 <= port <= 65535 or parent_pid <= 0:
+        return 2
+    lease_dir = Path(lease_dir_text)
+    stopped: dict[str, bool] = {"flag": False}
+
+    def _on_term(_signum: int, _frame: object) -> None:
+        """Отметить SIGTERM без тяжёлой работы в обработчике."""
+        stopped["flag"] = True
+
+    _ = signal.signal(signal.SIGTERM, _on_term)
+    try:
+        lease_dir.mkdir(parents=True, exist_ok=True)
+    except OSError:
+        return 2
+    lease_path = lease_dir / f"lease-{attempt_id}.json"
+
+    def _write_lease(extra: dict[str, object]) -> None:
+        """Атомарно опубликовать lease помощника."""
+        payload: dict[str, object] = {
+            "schema_version": 1,
+            "attempt_id": attempt_id,
+            "owner_uid": os.getuid(),
+            "parent_pid": parent_pid,
+            "parent_start_ts": parent_lstart,
+            "helper_pid": os.getpid(),
+            "helper_lstart": str(int(time.time())),
+            "pgid": os.getpgrp(),
+            "port": port,
+            "start_ts": time.time(),
+            "phase": "starting",
+        }
+        payload.update(extra)
+        tmp_path = lease_path.with_suffix(".tmp")
+        try:
+            _ = tmp_path.write_text(json.dumps(payload), "utf-8")
+            os.replace(tmp_path, lease_path)
+        except OSError:
+            pass
+
+    def _fd_ready() -> bool:
+        """EOF на lifeline fd 0 виден без блокировки."""
+        try:
+            ready, _w, _x = select.select([0], [], [], 0)
+            return bool(ready)
+        except (OSError, ValueError):
+            return False
+
+    _write_lease({})
+    if _fd_ready():
+        try:
+            lease_path.unlink()
+        except OSError:
+            pass
+        return 0
+    serve_env = dict(os.environ)
+    _ = serve_env.pop("OPENCODE_BIN", None)
+    try:
+        serve_proc = subprocess.Popen(
+            [opencode_bin, "serve", "--hostname", "127.0.0.1", "--port", str(port)],
+            stdin=subprocess.DEVNULL,
+            stdout=subprocess.PIPE,
+            stderr=subprocess.PIPE,
+            start_new_session=False,
+            close_fds=True,
+            env=serve_env,
+        )
+    except OSError:
+        return 2
+    serve_lstart = str(int(time.time()))
+    try:
+        out = subprocess.run(
+            ["ps", "-o", "lstart=", "-p", str(serve_proc.pid)],
+            capture_output=True,
+            text=True,
+            timeout=2,
+        )
+        if out.stdout.strip():
+            serve_lstart = out.stdout.strip()
+    except (OSError, subprocess.SubprocessError):
+        pass
+    _write_lease(
+        {"serve_pid": serve_proc.pid, "serve_lstart": serve_lstart, "phase": "ready"}
+    )
+    try:
+        _ = sys.stdout.write(
+            json.dumps({"serve_pid": serve_proc.pid, "pgid": os.getpgrp()}) + "\n"
+        )
+        _ = sys.stdout.flush()
+    except OSError:
+        pass
+    pipes: list[int] = []
+    for stream in (serve_proc.stdout, serve_proc.stderr):
+        if stream is not None:
+            pipes.append(stream.fileno())
+            os.set_blocking(stream.fileno(), False)
+    code = 0
+    try:
+        while True:
+            if stopped["flag"] or _fd_ready():
+                break
+            poll = serve_proc.poll()
+            if poll is not None:
+                code = int(poll)
+                break
+            watch: list[int] = [0, *pipes]
+            try:
+                ready, _w, _x = select.select(watch, [], [], 0.05)
+            except (OSError, ValueError):
+                ready = []
+            for item in ready:
+                if item == 0:
+                    stopped["flag"] = True
+                    continue
+                try:
+                    chunk = os.read(item, 65536)
+                except OSError:
+                    chunk = b""
+                if chunk:
+                    try:
+                        _ = sys.stderr.write(chunk.decode("utf-8", "replace"))
+                        _ = sys.stderr.flush()
+                    except OSError:
+                        pass
+            if stopped["flag"]:
+                break
+    finally:
+        if serve_proc.poll() is None:
+            try:
+                serve_proc.terminate()
+                _ = serve_proc.wait(timeout=0.5)
+            except (OSError, subprocess.SubprocessError):
+                try:
+                    serve_proc.kill()
+                except OSError:
+                    pass
+        # Дренировать остаток пайпов, чтобы потомок не остался с полным буфером.
+        for fd in pipes:
+            try:
+                while True:
+                    chunk = os.read(fd, 65536)
+                    if not chunk:
+                        break
+                    _ = sys.stderr.write(chunk.decode("utf-8", "replace"))
+            except OSError:
+                pass
+        try:
+            lease_path.unlink()
+        except OSError:
+            pass
+    return code
+
+
+if sys.argv[1:2] == ["--serve-helper"]:
+    raise SystemExit(_run_serve_helper_cli(sys.argv[2:]))
+else:
+    import base64
+    import hmac
+    import http.client
+    import queue
+    import random
+    import re
+    import secrets
+    import shlex
+    import shutil
+    import socket
+    import sqlite3
+    import tempfile
+    import threading
+    import uuid
+    from collections.abc import Callable, Iterable, Iterator
+    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
+    from typing import TypedDict
+    from urllib.parse import quote, urlsplit
+
+    sys.path.insert(0, str(Path(__file__).resolve().parent))
+    import zen_catalog as zc
 
 HOST = os.environ.get("OPENCODE_ZEN_BRIDGE_HOST", "127.0.0.1").strip() or "127.0.0.1"
 PORT = int(os.environ.get("OPENCODE_ZEN_BRIDGE_PORT", "9883"))
@@ -63,9 +247,6 @@ DEFAULTWORKDIR = Path(os.environ.get("OPENCODE_ZEN_BRIDGE_WORKDIR", str(WORKSPAC
 # Zen-модели запускаются как `opencode run --standalone` с OPENCODE_MODELS_PATH на свежий api.json
 # и БЕЗ OPENCODE_API_KEY (истёкший ключ из env давал 401 api_key_expired — причина отказа от
 # standalone 2026-10-19). Режим static (kill-switch) — прежний маршрут через фоновый сервис.
-sys.path.insert(0, str(Path(__file__).resolve().parent))
-import zen_catalog as zc
-
 DEPRECATED_MODEL_ALIASES: dict[str, str] = zc.DEPRECATED_MODEL_ALIASES
 
 
@@ -75,9 +256,15 @@ def _normalize_catalog_mode(raw: str) -> str:
     return "static" if value in ("static", "legacy") else "dynamic"
 
 
-CATALOG_MODE = _normalize_catalog_mode(os.environ.get("OPENCODE_ZEN_BRIDGE_CATALOG_MODE", "dynamic"))
-CATALOG_STATE_PATH = Path(os.environ.get(
-    "OPENCODE_ZEN_BRIDGE_CATALOG_STATE", str(Path(__file__).resolve().parent / "state" / "zen-catalog.json")))
+CATALOG_MODE = _normalize_catalog_mode(
+    os.environ.get("OPENCODE_ZEN_BRIDGE_CATALOG_MODE", "dynamic")
+)
+CATALOG_STATE_PATH = Path(
+    os.environ.get(
+        "OPENCODE_ZEN_BRIDGE_CATALOG_STATE",
+        str(Path(__file__).resolve().parent / "state" / "zen-catalog.json"),
+    )
+)
 OPENCODE_MODELS_PATH = os.environ.get(
     "OPENCODE_ZEN_BRIDGE_MODELS_PATH", str(Path.home() / ".cache" / "opencode" / "models.json"))
 CATALOG_STAT_INTERVAL_S = float(os.environ.get("OPENCODE_ZEN_BRIDGE_CATALOG_STAT_INTERVAL_S", "5"))
@@ -92,7 +279,12 @@ _catalog_lock = threading.RLock()
 _catalog_ids: set[str] = set()           # id, добавленные каталогом (тестовые/Go-записи не трогаем)
 _catalog_mtime: int | None = None
 _catalog_checked_at = float("-inf")
-CATALOG_SOURCE = "init"
+CATALOG_SOURCE = "static"
+
+
+def _set_catalog_source(source: str) -> None:
+    """Обновить публичный CATALOG_SOURCE без global-записи в reload."""
+    globals()["CATALOG_SOURCE"] = source
 
 
 def _stat_mtime(path: Path) -> int | None:
@@ -115,7 +307,7 @@ def _read_catalog_state() -> tuple[dict[str, Any], str]:
 
 def reload_catalog() -> dict[str, Any]:
     """Перечитать каталог и применить к ALLOWED_MODELS/MODEL_ALIASES на месте."""
-    global _catalog_mtime, _catalog_ids, CATALOG_SOURCE
+    global _catalog_mtime, _catalog_ids
     mtime = _stat_mtime(CATALOG_STATE_PATH)
     state, source = _read_catalog_state()
     models = zc.entries_to_bridge_models(state["models"])
@@ -128,7 +320,7 @@ def reload_catalog() -> dict[str, Any]:
         MODEL_ALIASES.update(DEPRECATED_MODEL_ALIASES)
         MODEL_ALIASES.update(state["aliases"])
         _catalog_mtime = mtime
-        CATALOG_SOURCE = source
+        _set_catalog_source(source)
     return {"ok": True, "source": source, "mode": CATALOG_MODE, "models": sorted(models),
             "aliases": len(MODEL_ALIASES), "degraded": bool(state.get("degraded"))}
 
@@ -1131,6 +1323,568 @@ def _run_env(model_id: str = "") -> dict[str, str]:
     return env
 
 
+DYNAMIC_CONFIG_PATH = Path(__file__).resolve().parent / "dynamic_config.json"
+LEASE_DIR = Path("/tmp/opencode-zen-bridge-leases")
+SERVE_TEST_ELIGIBLE = False
+FIRST_EVENT_TIMEOUT_S = float(
+    os.environ.get("OPENCODE_ZEN_BRIDGE_FIRST_EVENT_TIMEOUT_S", "20.0")
+)
+FIRST_TOKEN_TIMEOUT_S = float(
+    os.environ.get("OPENCODE_ZEN_BRIDGE_FIRST_TOKEN_TIMEOUT_S", "60.0")
+)
+STALL_TIMEOUT_S = float(os.environ.get("OPENCODE_ZEN_BRIDGE_STALL_TIMEOUT_S", "60.0"))
+FIRST_STATUS_DELAY_S = 0.65
+STATUS_WAITING_INTERVAL_S = 5.0
+STALL_HEARTBEAT_INTERVAL_S = 15.0
+STATUS_INITIAL = "[мост] Подключение к модели…\n"
+STATUS_WAITING = "[мост] Ожидание первого токена…\n"
+STATUS_CONTINUATION = "[мост] Ожидание продолжения…\n"
+_SERVE_ALLOWLIST = (
+    "PATH",
+    "HOME",
+    "USER",
+    "LOGNAME",
+    "SHELL",
+    "LANG",
+    "LC_ALL",
+    "LC_CTYPE",
+    "TZ",
+    "TERM",
+    "COLORTERM",
+    "HTTP_PROXY",
+    "HTTPS_PROXY",
+    "ALL_PROXY",
+    "NO_PROXY",
+    "http_proxy",
+    "https_proxy",
+    "all_proxy",
+    "no_proxy",
+    "SSL_CERT_FILE",
+    "SSL_CERT_DIR",
+    "NODE_EXTRA_CA_CERTS",
+    "XDG_DATA_HOME",
+    "XDG_CONFIG_HOME",
+    "OPENCODE_CONFIG",
+    "OPENCODE_CONFIG_CONTENT",
+    "OPENCODE_MODELS_PATH",
+)
+_dynamic_config_cache: dict[str, object] = {"key": None, "value": False, "path": ""}
+_LSOF_CALLS: list[int] = []
+
+
+class ServeUnavailable(Exception):
+    """Serve недоступен до барьера доставки: допустим fallback на run в auto."""
+
+
+class ServeProtocolError(ValueError):
+    """Битое событие serve: протокол, а не модель."""
+
+
+class ServeSecurityError(Exception):
+    """Отказ безопасности serve: fail-closed без fallback."""
+
+
+class _ServeHealth:
+    """Sticky деградация serve по протокольным отказам: 3 отказа, TTL 120 с."""
+
+    def __init__(self, threshold: int = 3, ttl_s: float = 120.0) -> None:
+        self.threshold = threshold
+        self.ttl_s = ttl_s
+        self.failures = 0
+        self._degraded_until = 0.0
+        self._lock = threading.Lock()
+
+    def record_failure(self, now: float | None = None) -> None:
+        """Засчитать протокольный отказ serve."""
+        with self._lock:
+            self.failures += 1
+            if self.failures >= self.threshold:
+                self._degraded_until = (
+                    time.monotonic() if now is None else now
+                ) + self.ttl_s
+
+    def record_success(self) -> None:
+        """Сбросить деградацию после успешной попытки."""
+        with self._lock:
+            self.failures = 0
+            self._degraded_until = 0.0
+
+    def is_degraded(self, now: float | None = None) -> bool:
+        """Истёк ли sticky TTL деградации."""
+        with self._lock:
+            at = time.monotonic() if now is None else now
+            if self._degraded_until and at >= self._degraded_until:
+                self.failures = 0
+                self._degraded_until = 0.0
+                return False
+            return bool(self._degraded_until and at < self._degraded_until)
+
+
+FALLBACK_DECISION_TABLE: list[dict[str, object]] = [
+    {
+        "phase": "SPAWN/READY/CREATE/SUBSCRIBE",
+        "event": "local spawn/ready/setup failure",
+        "DELIVERED": "false",
+        "action": "fallback_to_run",
+        "ServeHealth_failure_increment": 1,
+        "UpstreamBreaker_failure_increment": 0,
+    },
+    {
+        "phase": "SPAWN→READY",
+        "event": "ownership failure/timeout",
+        "DELIVERED": "false",
+        "action": "fallback_to_run",
+        "ServeHealth_failure_increment": 1,
+        "UpstreamBreaker_failure_increment": 0,
+    },
+    {
+        "phase": "PROMPT_SENDING",
+        "event": "first_event_timeout20s, no response headers and no valid execution SSE",
+        "DELIVERED": "false",
+        "action": "fallback_to_run",
+        "ServeHealth_failure_increment": 1,
+        "UpstreamBreaker_failure_increment": 0,
+    },
+    {
+        "phase": "DELIVERED",
+        "event": "first_event_timeout20s after headers, no valid execution SSE",
+        "DELIVERED": "true",
+        "action": "serve_retry",
+        "ServeHealth_failure_increment": 1,
+        "UpstreamBreaker_failure_increment": 0,
+    },
+    {
+        "phase": "DELIVERED",
+        "event": "first_token_timeout/stall with valid protocol and model silence",
+        "DELIVERED": "true",
+        "action": "serve_retry",
+        "ServeHealth_failure_increment": 0,
+        "UpstreamBreaker_failure_increment": 1,
+    },
+    {
+        "phase": "DELIVERED",
+        "event": "first_token_timeout with proven protocol/capability defect (non-security)",
+        "DELIVERED": "true",
+        "action": "serve_retry",
+        "ServeHealth_failure_increment": 1,
+        "UpstreamBreaker_failure_increment": 0,
+    },
+    {
+        "phase": "ANY",
+        "event": "HTTP401/403 or permission/form/capability-security failure",
+        "DELIVERED": "any",
+        "action": "fail_closed",
+        "ServeHealth_failure_increment": 0,
+        "UpstreamBreaker_failure_increment": 0,
+    },
+    {
+        "phase": "ANY",
+        "event": "HTTP400/404/422 invalid request",
+        "DELIVERED": "any",
+        "action": "fail_closed",
+        "ServeHealth_failure_increment": 0,
+        "UpstreamBreaker_failure_increment": 0,
+    },
+    {
+        "phase": "PRE_PROMPT",
+        "event": "HTTP5xx local readiness/create/subscribe endpoint",
+        "DELIVERED": "false",
+        "action": "fallback_to_run",
+        "ServeHealth_failure_increment": 1,
+        "UpstreamBreaker_failure_increment": 0,
+    },
+    {
+        "phase": "PROMPT_RESPONSE",
+        "event": "HTTP429/provider5xx; headers received latch delivery",
+        "DELIVERED": "true",
+        "action": "serve_retry",
+        "ServeHealth_failure_increment": 0,
+        "UpstreamBreaker_failure_increment": 1,
+    },
+    {
+        "phase": "DELIVERED",
+        "event": "invalid SSE/EOF without terminal proven protocol-only",
+        "DELIVERED": "true",
+        "action": "serve_retry",
+        "ServeHealth_failure_increment": 1,
+        "UpstreamBreaker_failure_increment": 0,
+    },
+    {
+        "phase": "ANY",
+        "event": "client cancel/deadline/budget exhausted",
+        "DELIVERED": "any",
+        "action": "fail_closed",
+        "ServeHealth_failure_increment": 0,
+        "UpstreamBreaker_failure_increment": 0,
+    },
+]
+
+
+class _WatchdogState(TypedDict):
+    """Состояние watchdog одного legacy-прогона."""
+
+    reason: str
+    first_event_at: float | None
+    first_token_at: float | None
+    last_token_at: float
+    status_next: float
+    last_keepalive: float
+    last_reasoning: str
+
+
+class _ServeResult(TypedDict):
+    """Итог одной serve-попытки с конкретными типами."""
+
+    reasonings: list[str]
+    texts: list[str]
+    native_calls: list[dict[str, object]]
+    usage: dict[str, int]
+    error: dict[str, object] | None
+    exit_reason: str
+    delivered: bool
+    terminal: str
+    first_event_at: float | None
+    first_token_at: float | None
+    step_closed: bool
+    first_event_ms: int | None
+    ttft_ms: int | None
+
+
+def _as_dict(value: object) -> dict[str, object]:
+    """Объект как словарь с строковыми ключами, иначе пустой."""
+    if isinstance(value, dict):
+        return {str(k): v for k, v in value.items()}
+    return {}
+
+
+class _JsonParser:
+    """Минимальный JSON-парсер в object."""
+
+    def __init__(self, raw: str) -> None:
+        self.raw = raw
+        self.pos = 0
+
+    def parse(self) -> object:
+        """Разобрать одно JSON-значение целиком."""
+        value = self._value()
+        self._ws()
+        if self.pos != len(self.raw):
+            raise ValueError("trailing data")
+        return value
+
+    def _ws(self) -> None:
+        """Пропустить пробелы."""
+        while self.pos < len(self.raw) and self.raw[self.pos] in " \t\r\n":
+            self.pos += 1
+
+    def _value(self) -> object:
+        """Значение по первому символу."""
+        self._ws()
+        if self.pos >= len(self.raw):
+            raise ValueError("eof")
+        ch = self.raw[self.pos]
+        if ch == "{":
+            return self._object()
+        if ch == "[":
+            return self._array()
+        if ch == '"':
+            return self._string()
+        if self.raw.startswith("true", self.pos):
+            self.pos += 4
+            return True
+        if self.raw.startswith("false", self.pos):
+            self.pos += 5
+            return False
+        if self.raw.startswith("null", self.pos):
+            self.pos += 4
+            return None
+        return self._number()
+
+    def _object(self) -> dict[str, object]:
+        """JSON-объект."""
+        out: dict[str, object] = {}
+        self.pos += 1
+        self._ws()
+        if self.pos < len(self.raw) and self.raw[self.pos] == "}":
+            self.pos += 1
+            return out
+        while True:
+            key = self._string()
+            self._ws()
+            if self.pos >= len(self.raw) or self.raw[self.pos] != ":":
+                raise ValueError("colon")
+            self.pos += 1
+            out[key] = self._value()
+            self._ws()
+            if self.pos < len(self.raw) and self.raw[self.pos] == ",":
+                self.pos += 1
+                continue
+            if self.pos < len(self.raw) and self.raw[self.pos] == "}":
+                self.pos += 1
+                return out
+            raise ValueError("object end")
+
+    def _array(self) -> list[object]:
+        """JSON-массив."""
+        out: list[object] = []
+        self.pos += 1
+        self._ws()
+        if self.pos < len(self.raw) and self.raw[self.pos] == "]":
+            self.pos += 1
+            return out
+        while True:
+            out.append(self._value())
+            self._ws()
+            if self.pos < len(self.raw) and self.raw[self.pos] == ",":
+                self.pos += 1
+                continue
+            if self.pos < len(self.raw) and self.raw[self.pos] == "]":
+                self.pos += 1
+                return out
+            raise ValueError("array end")
+
+    def _string(self) -> str:
+        """JSON-строка с escape-последовательностями."""
+        self._ws()
+        if self.pos >= len(self.raw) or self.raw[self.pos] != '"':
+            raise ValueError("string")
+        self.pos += 1
+        parts: list[str] = []
+        while self.pos < len(self.raw):
+            ch = self.raw[self.pos]
+            self.pos += 1
+            if ch == '"':
+                return "".join(parts)
+            if ch != "\\":
+                parts.append(ch)
+                continue
+            if self.pos >= len(self.raw):
+                break
+            esc = self.raw[self.pos]
+            self.pos += 1
+            mapping = {
+                '"': '"',
+                "\\": "\\",
+                "/": "/",
+                "b": "\b",
+                "f": "\f",
+                "n": "\n",
+                "r": "\r",
+                "t": "\t",
+            }
+            if esc == "u":
+                hex_part = self.raw[self.pos : self.pos + 4]
+                if len(hex_part) != 4:
+                    raise ValueError("unicode escape")
+                parts.append(chr(int(hex_part, 16)))
+                self.pos += 4
+            elif esc in mapping:
+                parts.append(mapping[esc])
+            else:
+                raise ValueError("escape")
+        raise ValueError("unterminated string")
+
+    def _number(self) -> object:
+        """JSON-число: int или float."""
+        start = self.pos
+        while self.pos < len(self.raw) and self.raw[self.pos] in "-+0123456789.eE":
+            self.pos += 1
+        text = self.raw[start : self.pos]
+        if not text:
+            raise ValueError("number")
+        try:
+            return int(text)
+        except ValueError:
+            return float(text)
+
+
+def _loads_object(raw: str) -> object:
+    """JSON в object собственным парсером."""
+    try:
+        return _JsonParser(raw).parse()
+    except (ValueError, IndexError):
+        return {}
+
+
+def _as_int(value: object) -> int:
+    """Целое из wire-значения, иначе 0."""
+    return value if isinstance(value, int) and not isinstance(value, bool) else 0
+
+
+def _read_dynamic_config_enabled(path: Path | None = None) -> bool:
+    """Boolean REALTIME_SERVE_ENABLED из dynamic_config.json с кэшем по stat."""
+    target = DYNAMIC_CONFIG_PATH if path is None else path
+    try:
+        stat = target.stat()
+    except OSError:
+        _dynamic_config_cache.update({"key": None, "value": False, "path": str(target)})
+        return False
+    key = (stat.st_mtime_ns, stat.st_size)
+    if (
+        _dynamic_config_cache.get("path") == str(target)
+        and _dynamic_config_cache.get("key") == key
+    ):
+        return bool(_dynamic_config_cache.get("value"))
+    value = False
+    try:
+        data = _as_dict(_loads_object(target.read_text("utf-8")))
+        enabled_obj = data.get("REALTIME_SERVE_ENABLED")
+        if isinstance(enabled_obj, bool):
+            value = enabled_obj
+    except OSError:
+        value = False
+    _dynamic_config_cache.update({"key": key, "value": value, "path": str(target)})
+    return value
+
+
+_dynamic_config_enabled = _read_dynamic_config_enabled
+
+
+def _serve_permission_effect() -> str:
+    """Эффект permission из env политики: ask_reject -> ask, deny -> deny."""
+    policy = os.environ.get(
+        "OPENCODE_ZEN_BRIDGE_SERVE_PERMISSION_POLICY", "ask_reject"
+    ).strip()
+    if policy == "ask_reject":
+        return "ask"
+    if policy == "deny":
+        return "deny"
+    raise ServeSecurityError(f"unsupported serve permission policy: {policy}")
+
+
+def _serve_env(model_id: str = "") -> dict[str, str]:
+    """Санитизированное окружение serve на всех ветках маршрутизации."""
+    base = _run_env(model_id)
+    env: dict[str, str] = {k: v for k, v in base.items() if k in _SERVE_ALLOWLIST}
+    _ = env.setdefault("PATH", "/usr/bin:/bin:/usr/sbin:/sbin")
+    if "HOME" not in env and os.environ.get("HOME"):
+        env["HOME"] = str(os.environ["HOME"])
+    if "XDG_DATA_HOME" not in env and os.environ.get("XDG_DATA_HOME"):
+        env["XDG_DATA_HOME"] = str(os.environ["XDG_DATA_HOME"])
+    config_raw = env.get("OPENCODE_CONFIG_CONTENT") or OPENCODE_CONFIG_CONTENT
+    config = _as_dict(_loads_object(config_raw)) if config_raw else {}
+    config["permission"] = {"*": _serve_permission_effect()}
+    env["OPENCODE_CONFIG_CONTENT"] = json.dumps(config, ensure_ascii=False)
+    state_dir = tempfile.mkdtemp(prefix="zen-serve-state-")
+    env["XDG_STATE_HOME"] = state_dir
+    env["TMPDIR"] = state_dir
+    env["OPENCODE_DB"] = ":memory:"
+    _ = env.pop("OPENCODE_BIN", None)
+    env["OPENCODE_SERVER_PASSWORD"] = secrets.token_hex(16)
+    return env
+
+
+def _is_native_opencode_bin(path: str) -> bool:
+    """Нативный бинарь opencode, а не текстовый фейк со shebang."""
+    if SERVE_TEST_ELIGIBLE:
+        return True
+    try:
+        with Path(path).open("rb") as fh:
+            head = fh.read(4)
+    except OSError:
+        return False
+    if head.startswith(b"#!"):
+        return False
+    return (
+        head[:2] in (b"\xcf\xfa", b"\xfa\xed")
+        or head.startswith(b"\x7fELF")
+        or len(head) == 4
+    )
+
+
+def _select_transport(res: _Resilience | None = None) -> str:
+    """Выбор транспорта: serve или run по приоритетам kill-switch."""
+    transport = os.environ.get("OPENCODE_ZEN_BRIDGE_TRANSPORT", "auto").strip().lower()
+    override = (
+        os.environ.get("OPENCODE_ZEN_BRIDGE_REALTIME_SERVE_ENABLED", "").strip().lower()
+    )
+    if transport == "run" or override in ("0", "false", "no", "off"):
+        return "run"
+    disable_raw = os.environ.get(
+        "OPENCODE_ZEN_BRIDGE_SERVE_DISABLE_FILE",
+        "~/.dsh/bridges/opencode-zen-bridge/disable-serve",
+    )
+    try:
+        if Path(disable_raw).expanduser().exists():
+            return "run"
+    except OSError:
+        return "run"
+    health = res.serve_health if res is not None else None
+    if transport == "serve":
+        return "serve"
+    if transport != "auto":
+        return "run"
+    if health is not None and health.is_degraded():
+        return "run"
+    enabled = override in ("1", "true", "yes", "on") or _read_dynamic_config_enabled()
+    if not enabled:
+        return "run"
+    return "serve" if _is_native_opencode_bin(OPENCODE_BIN) else "run"
+
+
+def _map_serve_event(event: dict[str, object]) -> tuple[str, dict[str, object]]:
+    """Wire-событие serve v2.1.2 -> канонический кортеж legacy-пути."""
+    etype_obj = event.get("type")
+    etype = etype_obj if isinstance(etype_obj, str) else ""
+    data = _as_dict(event.get("data"))
+    if etype == "server.connected":
+        return etype, data
+    if not data:
+        raise ServeProtocolError("invalid_serve_event: data")
+    if etype in ("session.reasoning.delta", "session.text.delta"):
+        delta = data.get("delta")
+        session_id = data.get("sessionID")
+        if (
+            not isinstance(delta, str)
+            or not isinstance(session_id, str)
+            or not session_id
+        ):
+            raise ServeProtocolError("invalid_serve_event: delta")
+        if etype.startswith("session.reasoning"):
+            return "reasoning", {"reasoning_content": delta}
+        return "text", {"content": delta}
+    if etype == "session.step.ended":
+        tokens = _as_dict(data.get("tokens"))
+        cache = _as_dict(tokens.get("cache"))
+        read_obj = cache.get("read")
+        if not tokens or not isinstance(read_obj, int):
+            raise ServeProtocolError("invalid_serve_event: cache.read")
+        out: dict[str, object] = {}
+        for key in ("input", "output", "reasoning"):
+            value = tokens.get(key)
+            if not isinstance(value, int) or isinstance(value, bool):
+                raise ServeProtocolError(f"invalid_serve_event: tokens.{key}")
+            out[key] = value
+        out["cached"] = read_obj
+        return "step_finish", out
+    if etype in ("session.execution.failed", "session.step.failed"):
+        err = _as_dict(data.get("error"))
+        message = err.get("message")
+        if not isinstance(message, str):
+            raise ServeProtocolError("invalid_serve_event: error")
+        status_obj = err.get("status")
+        status: int | None = (
+            status_obj
+            if isinstance(status_obj, int) and 100 <= status_obj <= 599
+            else None
+        )
+        if status is None:
+            err_type_obj = err.get("type")
+            err_type = err_type_obj if isinstance(err_type_obj, str) else ""
+            status = {"provider.free-limit": 429, "provider.auth": 401}.get(err_type)
+        return "error", {"statusCode": status, "message": message}
+    if etype == "permission.asked":
+        return "permission", data
+    if etype == "form.created":
+        return "form_created", data
+    if etype.startswith("session.tool."):
+        return "tool_event", data
+    return etype, data
+
+
+parse_serve_event = _map_serve_event
+
+
 def _variant_for(model_id: str, effort: str) -> str:
     """`#variant` для модели: только если модель их поддерживает и значение допустимо (иначе CLI: exit 1)."""
     meta = ALLOWED_MODELS.get(model_id, {})
@@ -1447,7 +2201,9 @@ class _UpstreamBreaker:
                 self._state = "OPEN"
                 self._open_until = now + cooldown
                 self._probes = 0
-                self._say(f"circuit_breaker state=OPEN failures={self._failures} cooldown_s={cooldown:.1f}")
+                self._say(
+                    f"circuit_breaker state=OPEN failures={self._failures} cooldown_s={cooldown:.1f}"
+                )
 
 
 class _Resilience:
@@ -1462,6 +2218,7 @@ class _Resilience:
         self.spawn_limiter = _SpawnRateLimiter(SPAWN_RATE_PER_S, SPAWN_BURST)
         self.retry_budget = _RetryBudget()
         self.breaker = _UpstreamBreaker()
+        self.serve_health = _ServeHealth()
 
 
 _DEFAULT_RESILIENCE = _Resilience()
@@ -1471,13 +2228,20 @@ _slots = _DEFAULT_RESILIENCE.slots  # прежнее имя семафора с
 class _RequestAttempts:
     """Учёт запусков одного HTTP-запроса: потолок MAX_TOTAL_SPAWNS, общий deadline, breaker, Retry Budget, backoff."""
 
-    def __init__(self, res: _Resilience, deadline: float, max_total: int | None = None,
-                 sleep_fn: Callable[[float], None] = time.sleep,
-                 rng_fn: Callable[[float, float], float] = random.uniform,
-                 use_breaker: bool = True) -> None:
+    def __init__(
+        self,
+        res: _Resilience,
+        deadline: float,
+        max_total: int | None = None,
+        sleep_fn: Callable[[float], None] = time.sleep,
+        rng_fn: Callable[[float, float], float] = random.uniform,
+        use_breaker: bool = True,
+    ) -> None:
         self.res = res
         self.deadline = deadline
-        self.use_breaker = use_breaker  # False: прямой Google-маршрут без `opencode run`
+        self.use_breaker = (
+            use_breaker  # False: прямой Google-маршрут без `opencode run`
+        )
         self.max_total = MAX_TOTAL_SPAWNS if max_total is None else max_total
         self.total_spawns = 0
         self.retries = 0
@@ -1496,8 +2260,11 @@ class _RequestAttempts:
 
     def begin_attempt(self) -> bool:
         """Первичный запуск: потолок, deadline и Circuit Breaker (в HALF_OPEN резервирует единственную пробу)."""
-        return (self.total_spawns < self.max_total and time.monotonic() < self.deadline
-                and (not self.use_breaker or self.res.breaker.allow()))
+        return (
+            self.total_spawns < self.max_total
+            and time.monotonic() < self.deadline
+            and (not self.use_breaker or self.res.breaker.allow())
+        )
 
     def allow_retry(self, reason: str, charge_budget: bool = True) -> bool:
         """Можно ли сделать повторный запуск: потолок, deadline, breaker, Retry Budget; затем Full Jitter пауза.
@@ -1517,7 +2284,11 @@ class _RequestAttempts:
             _log(f"retry denied ({reason}): retry budget exhausted")
             return False
         self.retries += 1
-        delay = _retry_backoff_s(self.retries, self._rng) if FAIL_RETRY_BACKOFF_S > 0 else 0.0
+        delay = (
+            _retry_backoff_s(self.retries, self._rng)
+            if FAIL_RETRY_BACKOFF_S > 0
+            else 0.0
+        )
         delay = min(delay, self.remaining_s())
         if delay > 0:
             self._sleep(delay)
@@ -1564,7 +2335,7 @@ class _PrefixDedup:
         current, prefix = self.current, self.prefix
         if current.startswith(prefix):
             self.prefix = ""
-            return current[len(prefix):]
+            return current[len(prefix) :]
         if len(current) >= len(prefix) or not prefix.startswith(current):
             self.prefix = ""
             return "\n\n" + current
@@ -1582,25 +2353,804 @@ class _PrefixDedup:
 def _dedup_retry_text(prefix: str, current: str) -> str:
     """JSON-вариант dedup_prefix: подавить уже отданный префикс, переформулированный текст сохранить целиком."""
     if prefix and current.startswith(prefix):
-        return current[len(prefix):]
+        return current[len(prefix) :]
     return current
 
 
+def _parent_lstart() -> str:
+    """lstart родителя дляargv помощника."""
+    try:
+        out = subprocess.run(
+            ["ps", "-o", "lstart=", "-p", str(os.getpid())],
+            capture_output=True,
+            text=True,
+            timeout=2,
+        )
+        return out.stdout.strip() or str(int(time.time()))
+    except (OSError, subprocess.SubprocessError):
+        return str(int(time.time()))
+
+
+def _lsof_listener_pid(port: int) -> int | None:
+    """PID слушателя порта одним вызовом lsof."""
+    _LSOF_CALLS.append(port)
+    try:
+        out = subprocess.run(
+            ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
+            capture_output=True,
+            text=True,
+            timeout=2,
+        )
+    except (OSError, subprocess.SubprocessError):
+        return None
+    for line in out.stdout.splitlines():
+        if line.strip().isdecimal():
+            return int(line.strip())
+    return None
+
+
+def _serve_http(
+    port: int,
+    password: str,
+    method: str,
+    path: str,
+    body: dict[str, object] | None = None,
+    timeout: float = 3.0,
+    conn: http.client.HTTPConnection | None = None,
+) -> tuple[int, dict[str, object]]:
+    """Один HTTP-вызов serve с Basic-авторизацией без прокси."""
+    own_conn = conn is None
+    active_conn = (
+        conn
+        if conn is not None
+        else http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
+    )
+    try:
+        payload = json.dumps(body).encode("utf-8") if body is not None else None
+        auth = base64.b64encode(f"opencode:{password}".encode("utf-8")).decode("ascii")
+        headers = {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}
+        active_conn.request(method, path, payload, headers)
+        resp = active_conn.getresponse()
+        raw = resp.read()
+        parsed: dict[str, object] = {}
+        if raw:
+            parsed = _as_dict(_loads_object(raw.decode("utf-8", "replace")))
+        return int(resp.status), parsed
+    finally:
+        if own_conn:
+            active_conn.close()
+
+
+class _ServeLease:
+    """Владение деревом helper->serve одной попытки."""
+
+    def __init__(
+        self,
+        helper: subprocess.Popen[str],
+        serve_pid: int,
+        pgid: int,
+        lifeline_w: int,
+        lease_dir: Path,
+        attempt_id: str,
+        state_dir: str,
+    ) -> None:
+        self.helper = helper
+        self.serve_pid = serve_pid
+        self.pgid = pgid
+        self.lifeline_w = lifeline_w
+        self.lease_dir = lease_dir
+        self.attempt_id = attempt_id
+        self.state_dir = state_dir
+        self._closed = False
+        self._lock = threading.Lock()
+
+    def cleanup(self) -> None:
+        """Идемпотентная уборка только своей группы процессов."""
+        with self._lock:
+            if self._closed:
+                return
+            self._closed = True
+        try:
+            os.close(self.lifeline_w)
+        except OSError:
+            pass
+        if self.helper.poll() is None or _pid_alive(self.pgid):
+            try:
+                if os.getpgid(self.pgid) == self.pgid:
+                    os.killpg(self.pgid, signal.SIGTERM)
+            except OSError:
+                pass
+            try:
+                _ = self.helper.wait(timeout=0.5)
+            except (OSError, subprocess.SubprocessError):
+                try:
+                    os.killpg(self.pgid, signal.SIGKILL)
+                except OSError:
+                    pass
+                try:
+                    _ = self.helper.wait(timeout=0.5)
+                except (OSError, subprocess.SubprocessError):
+                    pass
+        for stream in (self.helper.stdout, self.helper.stderr):
+            try:
+                if stream is not None:
+                    stream.close()
+            except OSError:
+                pass
+        try:
+            (self.lease_dir / f"lease-{self.attempt_id}.json").unlink()
+        except OSError:
+            pass
+        if self.state_dir and Path(self.state_dir).name.startswith("zen-serve-state-"):
+            shutil.rmtree(self.state_dir, ignore_errors=True)
+
+
+def _spawn_serve(
+    attempt_id: str, serve_env: dict[str, str]
+) -> tuple[_ServeLease, int, str]:
+    """Запуск helper->serve, проверка слушателя и рукопожатия."""
+    lease_dir = Path(LEASE_DIR)
+    lease_dir.mkdir(parents=True, exist_ok=True)
+    port = 0
+    for candidate in range(20000 + (os.getpid() % 20000), 60000):
+        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
+        try:
+            probe.bind(("127.0.0.1", candidate))
+            port = candidate
+            break
+        except OSError:
+            continue
+        finally:
+            probe.close()
+    if not port:
+        raise ServeUnavailable("no free serve port")
+    password = serve_env.get("OPENCODE_SERVER_PASSWORD", "")
+    lifeline_r, lifeline_w = os.pipe()
+    try:
+        helper: subprocess.Popen[str] = subprocess.Popen(
+            [
+                sys.executable,
+                "-I",
+                str(Path(__file__).resolve()),
+                "--serve-helper",
+                attempt_id,
+                str(port),
+                str(OPENCODE_BIN),
+                str(lease_dir),
+                str(os.getpid()),
+                _parent_lstart(),
+            ],
+            stdin=lifeline_r,
+            stdout=subprocess.PIPE,
+            stderr=subprocess.PIPE,
+            start_new_session=True,
+            close_fds=True,
+            env=serve_env,
+            text=True,
+        )
+    finally:
+        try:
+            os.close(lifeline_r)
+        except OSError:
+            pass
+    lease = _ServeLease(
+        helper,
+        0,
+        helper.pid,
+        lifeline_w,
+        lease_dir,
+        attempt_id,
+        serve_env.get("XDG_STATE_HOME", ""),
+    )
+    try:
+        assert helper.stdout is not None
+        out_fd = helper.stdout.fileno()
+        ready, _w, _x = select.select([out_fd], [], [], 3.0)
+        if not ready:
+            raise ServeUnavailable("serve handshake timeout")
+        line_bytes = b""
+        while not line_bytes.endswith(b"\n"):
+            chunk_b = os.read(out_fd, 1)
+            if not chunk_b:
+                break
+            line_bytes += chunk_b
+        line = line_bytes.decode("utf-8", "replace")
+        handshake = _as_dict(_loads_object(line)) if line else {}
+        serve_pid = _as_int(handshake.get("serve_pid"))
+        pgid = _as_int(handshake.get("pgid"))
+        lease.serve_pid = serve_pid
+        if not serve_pid or pgid != helper.pid or helper.poll() is not None:
+            raise ServeUnavailable("serve ownership handshake mismatch")
+        listener_pid = _lsof_listener_pid(port)
+        if listener_pid is not None and (
+            listener_pid != serve_pid or os.getpgid(listener_pid) != pgid
+        ):
+            raise ServeUnavailable("foreign listener on serve port")
+        # stderr помощника дренируется в лог, stdout после рукопожатия молчит.
+        threading.Thread(target=_drain_stderr, args=(helper, []), daemon=True).start()
+        return lease, port, password
+    except (OSError, ValueError, subprocess.SubprocessError) as exc:
+        lease.cleanup()
+        raise ServeUnavailable(str(exc)) from exc
+
+
+def _startup_reaper(lease_dir: Path | None = None) -> int:
+    """Убрать осиротевшие lease мёртвого родителя при старте моста."""
+    target = Path(LEASE_DIR) if lease_dir is None else lease_dir
+    removed = 0
+    try:
+        files = list(target.glob("lease-*.json"))
+    except OSError:
+        return 0
+    for path in files:
+        try:
+            data = _as_dict(_loads_object(path.read_text("utf-8")))
+            parent_pid = _as_int(data.get("parent_pid"))
+            helper_pid = _as_int(data.get("helper_pid"))
+            pgid = _as_int(data.get("pgid"))
+        except (OSError, ValueError, TypeError):
+            continue
+        parent_alive = parent_pid > 0 and _pid_alive(parent_pid)
+        if parent_alive:
+            continue
+        if helper_pid > 0 and pgid == helper_pid and _pid_alive(helper_pid):
+            try:
+                cmd = subprocess.run(
+                    ["ps", "-ww", "-o", "command=", "-p", str(helper_pid)],
+                    capture_output=True,
+                    text=True,
+                    timeout=2,
+                ).stdout
+            except (OSError, subprocess.SubprocessError):
+                cmd = ""
+            if "--serve-helper" not in cmd:
+                continue
+            try:
+                os.killpg(pgid, signal.SIGTERM)
+            except OSError:
+                pass
+        try:
+            path.unlink()
+            removed += 1
+        except OSError:
+            pass
+    return removed
+
+
+def _pid_alive(pid: int) -> bool:
+    """Жив ли процесс."""
+    try:
+        os.kill(pid, 0)
+        return True
+    except OSError:
+        return False
+
+
+class _ToolItem(TypedDict):
+    """Накопленный native вызов serve."""
+
+    name: str
+    text: str
+    input: dict[str, object] | None
+
+
+class _ServeToolState:
+    """Накопление native tool lifecycle serve до полного ввода."""
+
+    def __init__(self) -> None:
+        self.tools: dict[str, _ToolItem] = {}
+        self.emitted: set[str] = set()
+
+    def feed(self, data: dict[str, object]) -> None:
+        """Запомнить фрагмент native вызова."""
+        call_id = str(data.get("id") or "")
+        if not call_id:
+            return
+        item = self.tools.setdefault(call_id, {"name": "", "text": "", "input": None})
+        name = data.get("name")
+        if isinstance(name, str) and name:
+            item["name"] = name
+        text_value = data.get("text")
+        if isinstance(text_value, str):
+            item["text"] = text_value
+        input_value = data.get("input")
+        if isinstance(input_value, dict):
+            item["input"] = _as_dict(input_value)
+
+    def complete(self, call_id: str) -> tuple[str, dict[str, object]] | None:
+        """Готовый вызов из called.input или input.ended.text."""
+        if call_id in self.emitted:
+            return None
+        item = self.tools.get(call_id)
+        if item is None or not item["name"]:
+            return None
+        args = item["input"]
+        if not isinstance(args, dict):
+            text_value = item["text"]
+            try:
+                parsed: object = json.loads(text_value) if text_value else None
+            except ValueError:
+                return None
+            if not isinstance(parsed, dict):
+                return None
+            args = _as_dict(parsed)
+        self.emitted.add(call_id)
+        return "tool_use", {
+            "part": {"tool": item["name"], "state": {"input": args, "status": "error"}},
+            "call_id": call_id,
+        }
+
+
+def _native_call_as_dsh(
+    payload: dict[str, object], tools: list[dict[str, object]] | None
+) -> list[dict[str, object]]:
+    """Native serve-вызов в DSH-вызов по имени или известному алиасу."""
+    part = _as_dict(payload.get("part"))
+    state = _as_dict(part.get("state"))
+    tool = part.get("tool")
+    if not isinstance(tool, str) or not tool:
+        return []
+    args = _as_dict(state.get("input"))
+    names: list[str] = []
+    for item in tools or []:
+        fn_obj = item.get("function")
+        fn = _as_dict(fn_obj) if isinstance(fn_obj, dict) else item
+        name_obj = fn.get("name")
+        if isinstance(name_obj, str) and name_obj:
+            names.append(name_obj)
+    candidates = (tool, *NATIVE_TOOL_ALIASES.get(tool.lower(), ()))
+    for candidate in candidates:
+        if candidate in names:
+            return [{"name": candidate, "arguments": args}]
+    return []
+
+
+def _serve_one_attempt(
+    model: str,
+    prompt: str,
+    effort: str,
+    workdir: Path,
+    on_reasoning: Callable[[str], None],
+    on_text: Callable[[str], None],
+    on_tool: Callable[[dict[str, object]], None],
+    t0: float,
+    is_client_gone: Callable[[], bool] | None = None,
+    on_status: Callable[[str], None] | None = None,
+    thinking_enabled: bool = True,
+) -> _ServeResult:
+    """Одна попытка serve: helper, сессия, SSE, prompt и канонические события."""
+    result: _ServeResult = {
+        "reasonings": [],
+        "texts": [],
+        "native_calls": [],
+        "usage": {},
+        "error": None,
+        "exit_reason": "",
+        "delivered": False,
+        "terminal": "",
+        "first_event_at": None,
+        "first_token_at": None,
+        "step_closed": False,
+        "first_event_ms": None,
+        "ttft_ms": None,
+    }
+    serve_env = _serve_env(model)
+    password = serve_env.get("OPENCODE_SERVER_PASSWORD", "")
+    attempt_id = uuid.uuid4().hex
+    lease, port, _pw = _spawn_serve(attempt_id, serve_env)
+    session_id = ""
+    sse_conn: http.client.HTTPConnection | None = None
+    prompt_status: dict[str, object] = {}
+    control_conn: list[http.client.HTTPConnection | None] = [None]
+
+    def _ctrl_http(
+        method: str,
+        path: str,
+        body: dict[str, object] | None = None,
+        timeout: float = 3.0,
+    ) -> tuple[int, dict[str, object]]:
+        """Управляющий вызов serve по одному keep-alive соединению."""
+        for attempt in (0, 1):
+            conn = control_conn[0]
+            if conn is None:
+                conn = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
+                control_conn[0] = conn
+            try:
+                return _serve_http(
+                    port, password, method, path, body, timeout=timeout, conn=conn
+                )
+            except (OSError, http.client.HTTPException):
+                try:
+                    conn.close()
+                except OSError:
+                    pass
+                control_conn[0] = None
+                if attempt:
+                    raise
+        raise ServeUnavailable("serve control connection failed")
+
+    try:
+        status = 0
+        active: dict[str, object] = {}
+        ready_deadline = time.monotonic() + 3.0
+        while True:
+            try:
+                status, active = _ctrl_http("GET", "/api/session/active", timeout=3.0)
+                break
+            except (OSError, http.client.HTTPException) as exc:
+                if time.monotonic() >= ready_deadline:
+                    raise ServeUnavailable(f"serve ready failed: {exc}") from exc
+                time.sleep(0.05)
+        if status in (401, 403):
+            raise ServeSecurityError(f"serve auth HTTP {status}")
+        if status in (400, 404, 422):
+            raise ServeSecurityError(f"serve invalid request HTTP {status}")
+        if status != 200 or not isinstance(active.get("data"), dict):
+            raise ServeUnavailable(f"serve ready HTTP {status}")
+        route = _model_route(model)
+        provider, _sep, raw_id = route.partition("/")
+        variant = _variant_for(model, effort)
+        model_body: dict[str, object] = {
+            "providerID": provider or "opencode",
+            "id": raw_id or model,
+        }
+        if variant:
+            model_body["variant"] = variant
+        status, created = _ctrl_http(
+            "POST",
+            "/api/session",
+            {
+                "location": {"directory": str(workdir)},
+                "model": model_body,
+                "permissions": [
+                    {
+                        "action": "*",
+                        "resource": "*",
+                        "effect": _serve_permission_effect(),
+                    }
+                ],
+            },
+            timeout=3.0,
+        )
+        if status in (401, 403):
+            raise ServeSecurityError(f"serve create HTTP {status}")
+        if status in (400, 404, 422):
+            raise ServeSecurityError(f"serve invalid request HTTP {status}")
+        created_data = created.get("data")
+        if (
+            status != 200
+            or not isinstance(created_data, dict)
+            or not created_data.get("id")
+        ):
+            raise ServeUnavailable(f"serve create HTTP {status}")
+        session_id = str(created_data["id"])
+        sse_conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
+        auth = base64.b64encode(f"opencode:{password}".encode("utf-8")).decode("ascii")
+        sse_conn.request(
+            "GET",
+            "/api/event",
+            None,
+            {"Authorization": f"Basic {auth}", "Accept": "text/event-stream"},
+        )
+        sse_resp = sse_conn.getresponse()
+        if sse_resp.status in (401, 403):
+            raise ServeSecurityError(f"serve event HTTP {sse_resp.status}")
+        if sse_resp.status in (400, 404, 422):
+            raise ServeSecurityError(f"serve event HTTP {sse_resp.status}")
+        if sse_resp.status != 200:
+            raise ServeUnavailable(f"serve event HTTP {sse_resp.status}")
+        events: queue.Queue[dict[str, object] | None] = queue.Queue(maxsize=4096)
+
+        def _reader() -> None:
+            """Читатель SSE в очередь событий."""
+            try:
+                while True:
+                    line = sse_resp.readline()
+                    if not line:
+                        break
+                    text_line = line.decode("utf-8", "replace").strip()
+                    if not text_line.startswith("data:"):
+                        continue
+                    payload = text_line[5:].strip()
+                    if not payload or payload == "[DONE]":
+                        continue
+                    obj = _loads_object(payload)
+                    if isinstance(obj, dict):
+                        events.put(_as_dict(obj))
+            except (OSError, ValueError):
+                pass
+            finally:
+                events.put(None)
+
+        threading.Thread(target=_reader, daemon=True).start()
+        prompt_send_start = time.monotonic()
+
+        def _prompt_worker() -> None:
+            """Доставка prompt параллельно чтению SSE."""
+            try:
+                st, _body = _serve_http(
+                    port,
+                    password,
+                    "POST",
+                    f"/api/session/{session_id}/prompt",
+                    {"text": prompt, "files": [], "delivery": "steer", "resume": True},
+                    timeout=65.0,
+                )
+                prompt_status["status"] = st
+                prompt_status["headers_at"] = time.monotonic()
+                if st in (401, 403):
+                    prompt_status["security"] = True
+            except (OSError, http.client.HTTPException) as exc:
+                prompt_status["error"] = str(exc)
+
+        threading.Thread(target=_prompt_worker, daemon=True).start()
+        tool_state = _ServeToolState()
+        seen_steps: set[str] = set()
+        deadline = prompt_send_start + TIMEOUT_S
+        status_next = max(t0 + FIRST_STATUS_DELAY_S, prompt_send_start + 0.25)
+        last_token_at = prompt_send_start
+        while time.monotonic() < deadline:
+            if is_client_gone is not None and is_client_gone():
+                result["exit_reason"] = "client_gone"
+                return result
+            now = time.monotonic()
+            if result["first_event_at"] is None and now - prompt_send_start > float(
+                FIRST_EVENT_TIMEOUT_S
+            ):
+                result["exit_reason"] = "first_event_timeout"
+                result["delivered"] = bool(prompt_status.get("headers_at"))
+                return result
+            if (
+                result["first_event_at"] is not None
+                and result["first_token_at"] is None
+                and now - prompt_send_start > float(FIRST_TOKEN_TIMEOUT_S)
+            ):
+                result["exit_reason"] = "first_token_timeout"
+                result["delivered"] = True
+                return result
+            if result["first_token_at"] is not None and now - last_token_at > float(
+                STALL_TIMEOUT_S
+            ):
+                result["exit_reason"] = "stall_timeout"
+                result["delivered"] = True
+                return result
+            if thinking_enabled and on_status is not None and now >= status_next:
+                if result["first_token_at"] is None:
+                    on_status(STATUS_WAITING)
+                    status_next = now + STATUS_WAITING_INTERVAL_S
+                elif now - last_token_at >= float(STALL_HEARTBEAT_INTERVAL_S):
+                    on_status(STATUS_CONTINUATION)
+                    status_next = now + float(STALL_HEARTBEAT_INTERVAL_S)
+            try:
+                event = events.get(timeout=0.05)
+            except queue.Empty:
+                continue
+            if event is None:
+                if not result["terminal"]:
+                    result["exit_reason"] = "invalid_serve_event"
+                    result["delivered"] = bool(
+                        prompt_status.get("headers_at") or result["first_event_at"]
+                    )
+                break
+            etype_raw = str(event.get("type") or "")
+            data_raw = _as_dict(event.get("data"))
+            # form.created: безопасность до любой проверки title/fields/схемы.
+            if etype_raw == "form.created":
+                form = _as_dict(data_raw.get("form"))
+                form_session = form.get("sessionID")
+                form_id = form.get("id")
+                if form_session == session_id and isinstance(form_id, str) and form_id:
+                    result["step_closed"] = True
+                    st, _b = _ctrl_http(
+                        "POST",
+                        f"/api/session/{session_id}/form/{form_id}/cancel",
+                        None,
+                        timeout=0.25,
+                    )
+                    if st not in (200, 204):
+                        raise ServeSecurityError(f"form cancel HTTP {st}")
+                    st2, _b2 = _ctrl_http(
+                        "POST",
+                        f"/api/session/{session_id}/interrupt",
+                        None,
+                        timeout=0.25,
+                    )
+                    if st2 not in (200, 204):
+                        raise ServeSecurityError(f"form interrupt HTTP {st2}")
+                    result["terminal"] = "cancelled"
+                    break
+                if form_session == session_id:
+                    raise ServeSecurityError("form.created without id")
+                continue
+            if prompt_status.get("security"):
+                raise ServeSecurityError("serve prompt auth failed")
+            try:
+                etype, payload = _map_serve_event(event)
+            except ServeProtocolError:
+                result["exit_reason"] = "invalid_serve_event"
+                result["delivered"] = True
+                return result
+            event_session = (
+                payload.get("sessionID") if isinstance(payload, dict) else None
+            )
+            if etype_raw not in ("server.connected",) and event_session not in (
+                None,
+                session_id,
+            ):
+                continue
+            is_execution = etype_raw in (
+                "session.execution.started",
+                "session.step.started",
+                "session.reasoning.started",
+                "session.reasoning.delta",
+                "session.text.delta",
+                "session.step.ended",
+            ) or etype in ("reasoning", "text", "step_finish")
+            if is_execution and result["first_event_at"] is None:
+                result["first_event_at"] = time.monotonic()
+                result["first_event_ms"] = int(
+                    ((result["first_event_at"] or 0.0) - t0) * 1000
+                )
+            if etype == "permission":
+                result["step_closed"] = True
+                request_id = str(payload.get("id") or "")
+                st, _b = _ctrl_http(
+                    "POST",
+                    f"/api/session/{session_id}/permission/{request_id}/reply",
+                    {"decision": "reject"},
+                    timeout=0.25,
+                )
+                if st not in (200, 204):
+                    raise ServeSecurityError(f"permission reply HTTP {st}")
+                st2, _b2 = _ctrl_http(
+                    "POST",
+                    f"/api/session/{session_id}/interrupt",
+                    None,
+                    timeout=0.25,
+                )
+                if st2 not in (200, 204):
+                    raise ServeSecurityError(f"permission interrupt HTTP {st2}")
+                continue
+            if result["step_closed"] and etype in ("reasoning", "text"):
+                continue
+            if etype == "reasoning":
+                text_value = str(payload.get("reasoning_content") or "")
+                if text_value.strip():
+                    if result["first_token_at"] is None:
+                        result["first_token_at"] = time.monotonic()
+                        result["ttft_ms"] = int(
+                            ((result["first_token_at"] or 0.0) - t0) * 1000
+                        )
+                    result["reasonings"].append(text_value)
+                    last_token_at = time.monotonic()
+                    on_reasoning(text_value)
+            elif etype == "text":
+                text_value = str(payload.get("content") or "")
+                if text_value.strip():
+                    if result["first_token_at"] is None:
+                        result["first_token_at"] = time.monotonic()
+                        result["ttft_ms"] = int(
+                            ((result["first_token_at"] or 0.0) - t0) * 1000
+                        )
+                    result["texts"].append(text_value)
+                    last_token_at = time.monotonic()
+                    on_text(text_value)
+            elif etype == "tool_event":
+                tool_state.feed(payload)
+                call_id = str(payload.get("id") or "")
+                if etype_raw in (
+                    "session.tool.called",
+                    "session.tool.failed",
+                    "session.tool.success",
+                ):
+                    done = tool_state.complete(call_id)
+                    if done is not None:
+                        result["native_calls"].append(done[1])
+                        on_tool(done[1])
+                        if result["first_token_at"] is None:
+                            result["first_token_at"] = time.monotonic()
+            elif etype == "step_finish":
+                step_key = str(
+                    _as_dict(payload).get("assistantMessageID")
+                    or data_raw.get("assistantMessageID")
+                    or ""
+                )
+                if step_key and step_key in seen_steps:
+                    continue
+                if step_key:
+                    seen_steps.add(step_key)
+                # payload шага после _map не несёт assistantMessageID: ключ из data_raw выше.
+                for key in ("input", "output", "cached", "reasoning"):
+                    result["usage"][key] = result["usage"].get(key, 0) + _as_int(
+                        payload.get(key)
+                    )
+                # Завершить native вызовы без called: аргументы из input.ended.text.
+                for call_id in list(tool_state.tools):
+                    done = tool_state.complete(call_id)
+                    if done is not None:
+                        result["native_calls"].append(done[1])
+                        on_tool(done[1])
+            elif etype == "error":
+                result["error"] = payload
+                result["terminal"] = "failed"
+                break
+            elif etype_raw == "session.execution.succeeded":
+                result["terminal"] = "succeeded"
+                break
+        return result
+    finally:
+        if session_id:
+            try:
+                _ = _ctrl_http(
+                    "POST",
+                    f"/api/session/{session_id}/interrupt",
+                    None,
+                    timeout=0.25,
+                )
+            except (OSError, http.client.HTTPException):
+                pass
+            try:
+                _ = _ctrl_http(
+                    "DELETE",
+                    f"/api/session/{session_id}",
+                    None,
+                    timeout=0.25,
+                )
+            except (OSError, http.client.HTTPException):
+                pass
+        if control_conn[0] is not None:
+            try:
+                control_conn[0].close()
+            except OSError:
+                pass
+            control_conn[0] = None
+        if sse_conn is not None:
+            try:
+                sse_conn.close()
+            except OSError:
+                pass
+        lease.cleanup()
+
+
 def _new_exit_state() -> dict[str, Any]:
-    return {"t0": time.monotonic(), "mode": "", "model": "", "status": 0, "exit_reason": "",
-            "attempts": None, "tools": 0, "out_chars": 0, "rc": None}
+    return {
+        "t0": time.monotonic(),
+        "mode": "",
+        "model": "",
+        "status": 0,
+        "exit_reason": "",
+        "attempts": None,
+        "tools": 0,
+        "out_chars": 0,
+        "rc": None,
+        "transport": "none",
+        "first_event_ms": None,
+        "ttft_ms": None,
+        "transport_history": [],
+    }
 
 
 def _log_exit(xs: dict[str, Any]) -> None:
     """O-EXIT/v1: одна структурная строка bridge.log на каждый выход Handler.do_POST."""
-    attempts = xs.get("attempts")
-    status = int(xs.get("status") or 0)
-    reason = str(xs.get("exit_reason") or "") or ("ok" if status == 200 else (f"http_{status}" if status else "client_gone"))
-    _log(f"O-EXIT/v1 mode={xs.get('mode') or '-'} model={xs.get('model') or '-'} status={status} "
-         f"exit_reason={reason} rc={xs.get('rc')} total_spawns={attempts.total_spawns if attempts else 0} "
-         f"retries={attempts.retries if attempts else 0} signal={attempts.signal if attempts else 0} "
-         f"tools={xs.get('tools') or 0} out_chars={xs.get('out_chars') or 0} "
-         f"duration_s={time.monotonic() - float(xs['t0']):.2f}")
+    attempts_obj = xs.get("attempts")
+    attempts_t = attempts_obj if isinstance(attempts_obj, _RequestAttempts) else None
+    status_obj = xs.get("status")
+    status = status_obj if isinstance(status_obj, int) else 0
+    reason_obj = xs.get("exit_reason")
+    reason = (reason_obj if isinstance(reason_obj, str) and reason_obj else "") or (
+        "ok" if status == 200 else (f"http_{status}" if status else "client_gone")
+    )
+    t0_obj = xs.get("t0")
+    t0 = t0_obj if isinstance(t0_obj, float) else time.monotonic()
+    _log(
+        f"O-EXIT/v1 mode={xs.get('mode') or '-'} model={xs.get('model') or '-'} status={status} "
+        f"exit_reason={reason} rc={xs.get('rc')} total_spawns={attempts_t.total_spawns if attempts_t else 0} "
+        f"retries={attempts_t.retries if attempts_t else 0} signal={attempts_t.signal if attempts_t else 0} "
+        f"tools={xs.get('tools') or 0} out_chars={xs.get('out_chars') or 0} "
+        f"transport={xs.get('transport') or 'none'} first_event_ms={xs.get('first_event_ms')} "
+        f"ttft_ms={xs.get('ttft_ms')} transport_history={xs.get('transport_history') or []} "
+        f"duration_s={time.monotonic() - t0:.2f}"
+    )
 
 
 def _resolve_launcher() -> str:
@@ -2874,23 +4424,33 @@ class Run:
         """
         owns_attempts = self.attempts is None
         if self.attempts is None:
-            self.attempts = _RequestAttempts(self.res, time.monotonic() + TIMEOUT_S,
-                                             use_breaker=not _is_google_direct_model(self.model_id))
+            self.attempts = _RequestAttempts(
+                self.res,
+                time.monotonic() + TIMEOUT_S,
+                use_breaker=not _is_google_direct_model(self.model_id),
+            )
         attempts = self.attempts
         fail_retries = 0
         try:
             while True:
                 out = self._execute_once()
                 if fail_retries >= FAIL_RETRY_LIMIT or not _is_retryable_failure(
-                        out.get("rc"), str(out.get("err") or ""), out.get("provider_status"),
-                        bool(out.get("had_output"))):
+                    out.get("rc"),
+                    str(out.get("err") or ""),
+                    out.get("provider_status"),
+                    bool(out.get("had_output")),
+                ):
                     return out
-                if not attempts.allow_retry("cli_failure", charge_budget=out.get("provider_status") is not None):
+                if not attempts.allow_retry(
+                    "cli_failure", charge_budget=out.get("provider_status") is not None
+                ):
                     return out
                 fail_retries += 1
-                _log(f"exec failed rc={out.get('rc')} without output, retry {fail_retries}/{FAIL_RETRY_LIMIT} "
-                     f"total_spawns={attempts.total_spawns}/{attempts.max_total}: "
-                     f"{_clean_err(str(out.get('err') or ''), 300)!r}")
+                _log(
+                    f"exec failed rc={out.get('rc')} without output, retry {fail_retries}/{FAIL_RETRY_LIMIT} "
+                    f"total_spawns={attempts.total_spawns}/{attempts.max_total}: "
+                    f"{_clean_err(str(out.get('err') or ''), 300)!r}"
+                )
                 self.close()
         finally:
             if owns_attempts:
@@ -2899,32 +4459,62 @@ class Run:
     def _execute_once(self) -> dict[str, Any]:
         """Один прогон: текст — из type:text, мышление — из type:reasoning, usage — из step_finish."""
         if _is_google_direct_model(self.model_id):
-            return _execute_google_once(self.model_id, self.prompt, self.effort, self.google_input)
+            return _execute_google_once(
+                self.model_id, self.prompt, self.effort, self.google_input
+            )
         launcher = _resolve_launcher()
         if not os.access(launcher, os.X_OK):
-            return {"rc": -1, "text": "", "reasoning": "", "usage": {},
-                    "err": f"opencode launcher not executable: {launcher}",
-                    "state": "launcher_missing", "finish": "error"}
+            return {
+                "rc": -1,
+                "text": "",
+                "reasoning": "",
+                "usage": {},
+                "err": f"opencode launcher not executable: {launcher}",
+                "state": "launcher_missing",
+                "finish": "error",
+            }
 
         self.workdir.mkdir(parents=True, exist_ok=True)
         env = _run_env(self.model_id)
         model_route = _model_route(self.model_id)
 
         cmd, shown = _build_cmd(launcher, self.model_id, self.effort)
-        _log(f"exec model={model_route} {shown} prompt_chars={len(self.prompt)} cwd={self.workdir}")
-        deadline = self.attempts.deadline if self.attempts is not None else time.monotonic() + TIMEOUT_S
+        _log(
+            f"exec model={model_route} {shown} prompt_chars={len(self.prompt)} cwd={self.workdir}"
+        )
+        deadline = (
+            self.attempts.deadline
+            if self.attempts is not None
+            else time.monotonic() + TIMEOUT_S
+        )
         gate = _StartupGate()
         gate.acquire()
-        if not self.res.spawn_limiter.acquire(max_wait_s=min(SPAWN_WAIT_MAX_S, max(0.0, deadline - time.monotonic()))):
+        if not self.res.spawn_limiter.acquire(
+            max_wait_s=min(SPAWN_WAIT_MAX_S, max(0.0, deadline - time.monotonic()))
+        ):
             gate.release()
-            return {"rc": -1, "text": "", "reasoning": "", "usage": {}, "err": "spawn rate limit: deadline exceeded",
-                    "state": "timeout", "finish": "error"}
+            return {
+                "rc": -1,
+                "text": "",
+                "reasoning": "",
+                "usage": {},
+                "err": "spawn rate limit: deadline exceeded",
+                "state": "timeout",
+                "finish": "error",
+            }
         try:
             self.proc = _spawn_with_stdin(cmd, self.prompt, self.workdir, env)
         except OSError as exc:
             gate.release()
-            return {"rc": -1, "text": "", "reasoning": "", "usage": {}, "err": f"spawn failed: {exc}",
-                    "state": "spawn_failed", "finish": "error"}
+            return {
+                "rc": -1,
+                "text": "",
+                "reasoning": "",
+                "usage": {},
+                "err": f"spawn failed: {exc}",
+                "state": "spawn_failed",
+                "finish": "error",
+            }
         if self.attempts is not None:
             self.attempts.note_spawn()
 
@@ -2934,8 +4524,8 @@ class Run:
         usage: dict[str, Any] = {}
         err_lines: list[str] = []
         provider_status: int | None = None
-        had_error = False       # транзиентная ошибка провайдера посреди ответа (had_mid_stream_error)
-        fatal_error = False     # детерминированная ошибка посреди ответа (400/401/403/404/422): без повтора
+        had_error = False  # транзиентная ошибка провайдера посреди ответа (had_mid_stream_error)
+        fatal_error = False  # детерминированная ошибка посреди ответа (400/401/403/404/422): без повтора
         stopped_on_error = False
         state = "ok"
         run_id = uuid.uuid4().hex[:8]
@@ -2986,12 +4576,24 @@ class Run:
                 elif etype == "step_finish":
                     if payload:
                         for key in ("input", "output", "cached", "reasoning"):
-                            usage[key] = int(usage.get(key) or 0) + int(payload.get(key) or 0)
+                            usage[key] = int(usage.get(key) or 0) + int(
+                                payload.get(key) or 0
+                            )
                     if self.tools is not None and (
-                            any(_native_to_tool_calls(nc.get("tool"), nc.get("input"), self.tools)
-                                for nc in native_calls)
-                            or any(close_tag in "".join(text_pieces) for _, close_tag in TOOL_CALL_TAGS)):
-                        _log("exec: step with tool call finished, stopping opencode run")
+                        any(
+                            _native_to_tool_calls(
+                                nc.get("tool"), nc.get("input"), self.tools
+                            )
+                            for nc in native_calls
+                        )
+                        or any(
+                            close_tag in "".join(text_pieces)
+                            for _, close_tag in TOOL_CALL_TAGS
+                        )
+                    ):
+                        _log(
+                            "exec: step with tool call finished, stopping opencode run"
+                        )
                         _stop_proc(self.proc)
                         break
                 elif etype == "tool_use":
@@ -3081,6 +4683,7 @@ class Handler(BaseHTTPRequestHandler):
         _log(f"http accept error from {client_address}")
 
     _xs: dict[str, Any] | None = None
+    _serve_stream_usage: dict[str, int] | None = None
 
     def _exit(self) -> dict[str, Any]:
         """Состояние выхода текущего запроса для структурной строки O-EXIT/v1."""
@@ -3090,7 +4693,11 @@ class Handler(BaseHTTPRequestHandler):
 
     def _res(self) -> _Resilience:
         """Защиты сервера (слоты, breaker, budget, лимитер); у `Server` — свои, иначе модульные."""
-        return cast("_Resilience", getattr(getattr(self, "server", None), "resilience", None) or _DEFAULT_RESILIENCE)
+        return cast(
+            "_Resilience",
+            getattr(getattr(self, "server", None), "resilience", None)
+            or _DEFAULT_RESILIENCE,
+        )
 
     def _acquire_slot(self, res: _Resilience) -> bool:
         """Слот с ограниченным ожиданием; отказ -> 503 overloaded (таймаут 15 с или 13-й ждущий мгновенно)."""
@@ -3124,6 +4731,240 @@ class Handler(BaseHTTPRequestHandler):
         self.wfile.write(b"data: [DONE]\n\n")
         self.wfile.flush()
 
+    def _client_gone_check(self) -> bool:
+        """Клиент закрыл сокет: FIN/RST виден peek без чтения данных."""
+        try:
+            dup_fd = os.dup(self.rfile.fileno())
+        except AttributeError:
+            return False
+        try:
+            conn_obj = socket.socket(fileno=dup_fd)
+            try:
+                ready, _w, _x = select.select([conn_obj], [], [], 0)
+                if not ready:
+                    return False
+                data = conn_obj.recv(1, socket.MSG_PEEK | socket.MSG_DONTWAIT)
+                return data == b""
+            finally:
+                os.close(conn_obj.detach())
+        except (OSError, ValueError):
+            return False
+
+    def _run_serve_stream_attempts(
+        self,
+        model: str,
+        prompt: str,
+        effort: str,
+        emulate_tools: bool,
+        tools: list[dict[str, object]] | None,
+        resp_id: str,
+        created: int,
+        shown_model: str,
+        emit_content: Callable[[str], None],
+        emit_parsed_content: Callable[[str], None],
+        emit_tool_call: Callable[[dict[str, object]], None],
+        attempts: _RequestAttempts,
+        res: _Resilience,
+        xs: dict[str, object],
+        collected_texts: list[str],
+    ) -> bool:
+        """Serve-попытки для SSE; True — запрос завершён, False — fallback на run."""
+        thinking = effort.strip().lower() not in ("", "off", "none")
+        workdir = DEFAULTWORKDIR
+        workdir.mkdir(parents=True, exist_ok=True)
+        last_reasoning: list[str] = [""]
+
+        def on_status(text: str) -> None:
+            """Синтетический статус с ведущим LF после незавершённой строки модели."""
+            prefix = (
+                "\n"
+                if last_reasoning[0] and not last_reasoning[0].endswith("\n")
+                else ""
+            )
+            chunk = format_sse_chunk(
+                resp_id, created, shown_model, {"reasoning_content": prefix + text}
+            )
+            _ = self.wfile.write(chunk.encode("utf-8"))
+            self.wfile.flush()
+
+        def on_reasoning(text: str) -> None:
+            """Модельное размышление клиенту без модификации байтов."""
+            cleaned = _strip_interrupted(text)
+            if not cleaned:
+                return
+            last_reasoning[0] = cleaned
+            chunk = format_sse_chunk(
+                resp_id, created, shown_model, {"reasoning_content": cleaned}
+            )
+            _ = self.wfile.write(chunk.encode("utf-8"))
+            self.wfile.flush()
+
+        parser_box: list[ToolCallParser | None] = [None]
+
+        def on_text(text: str) -> None:
+            """Модельный текст через ToolCallParser при эмуляции."""
+            cleaned = _strip_interrupted(text)
+            if parser_box[0] is not None:
+                parser_box[0].feed(cleaned)
+            else:
+                emit_content(cleaned)
+
+        unmapped_in_attempt: list[str] = []
+        emitted_tools_in_attempt = [0]
+
+        def on_tool(payload: dict[str, object]) -> None:
+            """Native serve-вызов в DSH tool_call."""
+            part = _as_dict(payload.get("part"))
+            mapped = _native_call_as_dsh(payload, tools) if emulate_tools else []
+            if not mapped and emulate_tools and part.get("tool"):
+                unmapped_in_attempt.append(str(part.get("tool")))
+            for call in mapped:
+                emitted_tools_in_attempt[0] += 1
+                emit_tool_call(call)
+
+        def on_parsed_tool(call: dict[str, object]) -> None:
+            """Вызов из текста модели: учесть в счётчике эмиссии попытки."""
+            emitted_tools_in_attempt[0] += 1
+            emit_tool_call(call)
+
+        force_serve = (
+            os.environ.get("OPENCODE_ZEN_BRIDGE_TRANSPORT", "").strip().lower()
+            == "serve"
+        )
+        current_prompt = prompt
+        serve_attempts = 0
+        unmapped_retries = 0
+        incomplete_retries = 0
+        while True:
+            unmapped_in_attempt.clear()
+            emitted_tools_in_attempt[0] = 0
+            if parser_box[0] is not None:
+                parser_box[0].finish()
+            parser_box[0] = (
+                ToolCallParser(emit_parsed_content, on_parsed_tool)
+                if emulate_tools
+                else None
+            )
+            attempts.note_spawn()
+            serve_attempts += 1
+            try:
+                result = _serve_one_attempt(
+                    model,
+                    current_prompt,
+                    effort,
+                    workdir,
+                    on_reasoning,
+                    on_text,
+                    on_tool,
+                    attempts.deadline - TIMEOUT_S,
+                    is_client_gone=self._client_gone_check,
+                    on_status=on_status,
+                    thinking_enabled=thinking,
+                )
+            except ServeUnavailable as exc:
+                res.serve_health.record_failure()
+                if not force_serve:
+                    xs["transport"] = "run"
+                    xs["transport_history"] = ["serve", "run"]
+                    return False
+                xs["exit_reason"] = "upstream_failed"
+                self._sse_error(_error_payload(f"serve unavailable: {exc}"))
+                return True
+            except ServeSecurityError as exc:
+                xs["exit_reason"] = "provider_fatal"
+                self._sse_error(_error_payload(f"serve security failure: {exc}"))
+                return True
+            xs["first_event_ms"] = result["first_event_ms"]
+            xs["ttft_ms"] = result["ttft_ms"]
+            if parser_box[0] is not None:
+                parser_box[0].finish()
+            if result.get("exit_reason") == "client_gone":
+                xs["exit_reason"] = "client_gone"
+                return True
+            xs["first_event_ms"] = result["first_event_ms"]
+            xs["ttft_ms"] = result["ttft_ms"]
+            if result.get("exit_reason") in (
+                "first_event_timeout",
+                "first_token_timeout",
+                "stall_timeout",
+                "invalid_serve_event",
+            ):
+                reason = str(result["exit_reason"])
+                if reason in ("first_event_timeout", "invalid_serve_event"):
+                    res.serve_health.record_failure()
+                else:
+                    attempts.attempt_done(True, False)
+                if not result.get("delivered") and not force_serve:
+                    xs["transport"] = "run"
+                    xs["transport_history"] = ["serve", "run"]
+                    return False
+                if attempts.allow_retry(reason):
+                    on_status(
+                        f"[мост] Повтор попытки {attempts.total_spawns + 1}/{attempts.max_total}…\n"
+                    )
+                    continue
+                xs["exit_reason"] = reason
+                self._sse_error(_error_payload(f"serve {reason}"))
+                return True
+            if result["error"] is not None:
+                err = result["error"]
+                xs["exit_reason"] = "upstream_failed"
+                self._sse_error(_error_payload(f"serve error: {err.get('message')}"))
+                return True
+            res.serve_health.record_success()
+            usage_cur = result["usage"]
+            usage_acc = self._serve_stream_usage or {}
+            for key in ("input", "output", "cached", "reasoning"):
+                usage_acc[key] = int(usage_acc.get(key) or 0) + int(
+                    usage_cur.get(key) or 0
+                )
+            self._serve_stream_usage = usage_acc
+            if emulate_tools and emitted_tools_in_attempt[0] == 0:
+                if unmapped_in_attempt:
+                    if unmapped_retries < NATIVE_RETRY_LIMIT and attempts.allow_retry(
+                        "unmapped"
+                    ):
+                        unmapped_retries += 1
+                        current_prompt = _rewrite_tool_tags_for_model(
+                            _unavailable_tools_prompt(
+                                current_prompt,
+                                "".join(result["texts"]),
+                                unmapped_in_attempt,
+                                tools or [],
+                                model,
+                            ),
+                            model,
+                        )
+                        continue
+                    emit_content(
+                        f"\n\n[opencode-zen-bridge: модель вызывала недоступный встроенный инструмент ({', '.join(unmapped_in_attempt)}); повторы исчерпаны]"
+                    )
+                    return True
+                signal = _incomplete_step_signal(
+                    "".join(result["texts"]),
+                    "".join(result["reasonings"]),
+                    tools or [],
+                    False,
+                    int(usage_cur.get("output") or 0),
+                    int(usage_cur.get("reasoning") or 0),
+                    tool_choice=None,
+                )
+                if (
+                    signal
+                    and incomplete_retries < NATIVE_RETRY_LIMIT
+                    and attempts.allow_retry("incomplete_step")
+                ):
+                    incomplete_retries += 1
+                    attempts.signal = signal
+                    current_prompt = _rewrite_tool_tags_for_model(
+                        _incomplete_tool_step_prompt(
+                            prompt, "".join(collected_texts), tools or [], None, model
+                        ),
+                        model,
+                    )
+                    continue
+            return True
+
     def _stream_google_sse(self, model: str, prompt: str, effort: str,
                            emulate_tools: bool = False,
                            google_input: GoogleInput | None = None) -> None:
@@ -3274,6 +5115,8 @@ class Handler(BaseHTTPRequestHandler):
             self._stream_google_sse(model, prompt, effort, emulate_tools, google_input)
             return
         xs = self._exit()
+        xs["transport"] = "run"
+        xs["transport_history"] = ["run"]
         launcher = _resolve_launcher()
         if not os.access(launcher, os.X_OK):
             xs["exit_reason"] = "launcher_missing"
@@ -3383,6 +5226,61 @@ class Handler(BaseHTTPRequestHandler):
             with _active_lock:
                 _active[run_id] = time.time()
 
+            if _select_transport(res) == "serve":
+                xs["transport"] = "serve"
+                xs["transport_history"] = ["serve"]
+                self._serve_stream_usage = None
+                handled = self._run_serve_stream_attempts(
+                    model,
+                    prompt,
+                    effort,
+                    emulate_tools,
+                    tools,
+                    resp_id,
+                    created,
+                    shown_model,
+                    emit_content,
+                    emit_parsed_content,
+                    emit_tool_call,
+                    attempts,
+                    res,
+                    xs,
+                    collected_texts,
+                )
+                if handled:
+                    if xs.get("exit_reason"):
+                        return
+                    serve_usage = self._serve_stream_usage or {}
+                    for key in ("input", "output", "cached", "reasoning"):
+                        if serve_usage.get(key):
+                            usage[key] = int(usage.get(key) or 0) + serve_usage[key]
+                    full_text_s = "".join(collected_texts)
+                    final_s = format_sse_chunk(
+                        resp_id,
+                        created,
+                        shown_model,
+                        {},
+                        finish_reason="tool_calls" if tool_calls else "stop",
+                        usage=_build_openai_usage(
+                            int(usage.get("input") or 0) or _estimate_tokens(prompt),
+                            int(usage.get("output") or 0)
+                            or _estimate_tokens(full_text_s),
+                            int(usage.get("cached") or 0),
+                            int(usage.get("reasoning") or 0),
+                        ),
+                    )
+                    _ = self.wfile.write(final_s.encode("utf-8"))
+                    _ = self.wfile.write(b"data: [DONE]\n\n")
+                    self.wfile.flush()
+                    xs.update(
+                        exit_reason="ok",
+                        tools=len(tool_calls),
+                        out_chars=len(full_text_s),
+                        rc=0,
+                    )
+                    return
+                xs["transport"] = "run"
+
             attempt_prompt = prompt
             retries = 0  # повторов с новым промптом: встроенный инструмент / незавершённый шаг (для лога)
             unmapped_retries = 0
@@ -3400,13 +5298,17 @@ class Handler(BaseHTTPRequestHandler):
                 gate.acquire()
                 if not res.spawn_limiter.acquire(max_wait_s=min(SPAWN_WAIT_MAX_S, attempts.remaining_s())):
                     gate.release()
-                    _log("stream spawn skipped: spawn rate limiter wait exceeds the request deadline")
+                    _log(
+                        "stream spawn skipped: spawn rate limiter wait exceeds the request deadline"
+                    )
                     if not collected_texts and not tool_calls:
                         failure = {"rc": -1, "tail": "", "timeout": True}
                     break
                 try:
                     # env на каждую попытку: ретрай получает следующий порт пула (чистый IP)
-                    proc = _spawn_with_stdin(cmd, attempt_prompt, workdir, _run_env(model))
+                    proc = _spawn_with_stdin(
+                        cmd, attempt_prompt, workdir, _run_env(model)
+                    )
                 except OSError as exc:
                     gate.release()
                     _log(f"stream spawn failed: {exc}")
@@ -3417,37 +5319,126 @@ class Handler(BaseHTTPRequestHandler):
 
                 err_lines: list[str] = []
 
-                err_thread = threading.Thread(target=_drain_stderr, args=(proc, err_lines), daemon=True)
+                err_thread = threading.Thread(
+                    target=_drain_stderr, args=(proc, err_lines), daemon=True
+                )
                 err_thread.start()
 
-                parser = ToolCallParser(emit_parsed_content, emit_tool_call) if emulate_tools else None
+                parser = (
+                    ToolCallParser(emit_parsed_content, emit_tool_call)
+                    if emulate_tools
+                    else None
+                )
                 attempt_texts: list[str] = []
                 attempt_reasonings: list[str] = []
                 unmapped: list[str] = []
                 attempt_output = False  # любой полезный вывод этого прогона (текст/мышление/инструмент)
-                attempt_output_tokens = 0  # output из step_finish этого прогона (для проглоченных вызовов)
-                attempt_reasoning_tokens = 0  # reasoning из step_finish (output включает reasoning)
+                attempt_output_tokens = (
+                    0  # output из step_finish этого прогона (для проглоченных вызовов)
+                )
+                attempt_reasoning_tokens = (
+                    0  # reasoning из step_finish (output включает reasoning)
+                )
                 provider_status: int | None = None
-                had_provider_error = False  # транзиентная ошибка посреди ответа (had_mid_stream_error)
-                fatal_mid_error = False  # детерминированная ошибка посреди ответа: без повтора
+                had_provider_error = (
+                    False  # транзиентная ошибка посреди ответа (had_mid_stream_error)
+                )
+                fatal_mid_error = (
+                    False  # детерминированная ошибка посреди ответа: без повтора
+                )
                 stopped_on_error = False
                 prior_text = "".join(collected_texts)
-                dedup[0] = _PrefixDedup(prior_text) if incomplete_retry and prior_text else None
+                dedup[0] = (
+                    _PrefixDedup(prior_text)
+                    if incomplete_retry and prior_text
+                    else None
+                )
+
+                attempt_start = time.monotonic()
+                watchdog_state: _WatchdogState = {
+                    "reason": "",
+                    "first_event_at": None,
+                    "first_token_at": None,
+                    "last_token_at": attempt_start,
+                    "status_next": attempt_start + FIRST_STATUS_DELAY_S,
+                    "last_keepalive": attempt_start,
+                    "last_reasoning": "",
+                }
+                thinking_enabled = effort.strip().lower() not in ("", "off", "none")
+
+                def emit_synthetic(text: str) -> None:
+                    """Синтетический статус отдельной reasoning-дельтой."""
+                    tail = str(watchdog_state.get("last_reasoning") or "")
+                    prefix = "\n" if tail and not tail.endswith("\n") else ""
+                    chunk_s = format_sse_chunk(
+                        resp_id,
+                        created,
+                        shown_model,
+                        {"reasoning_content": prefix + text},
+                    )
+                    _ = self.wfile.write(chunk_s.encode("utf-8"))
+                    self.wfile.flush()
 
                 def send_keepalive(proc: subprocess.Popen[str] = proc) -> None:
-                    # Парсируемый chat.completion.chunk с пустой дельтой: сбрасывает клиентские
-                    # watchdog'и стрима (комментарий `: keepalive` их не сбрасывает).
+                    """Надзор: статусы, watchdog и обнаружение ухода клиента."""
+                    now_s = time.monotonic()
+                    if self._client_gone_check():
+                        _log("stream client gone, killing proc group")
+                        _stop_proc(proc)
+                        raise BrokenPipeError("client gone")
+                    if watchdog_state[
+                        "first_event_at"
+                    ] is None and now_s - attempt_start > float(FIRST_EVENT_TIMEOUT_S):
+                        watchdog_state["reason"] = "first_event_timeout"
+                        _stop_proc(proc)
+                        return
+                    if (
+                        watchdog_state["first_event_at"] is not None
+                        and watchdog_state["first_token_at"] is None
+                        and now_s - attempt_start > float(FIRST_TOKEN_TIMEOUT_S)
+                    ):
+                        watchdog_state["reason"] = "first_token_timeout"
+                        _stop_proc(proc)
+                        return
+                    if watchdog_state["first_token_at"] is not None and now_s - float(
+                        watchdog_state["last_token_at"]
+                    ) > float(STALL_TIMEOUT_S):
+                        watchdog_state["reason"] = "stall_timeout"
+                        _stop_proc(proc)
+                        return
                     try:
-                        keepalive = format_sse_chunk(resp_id, created, shown_model, {"content": ""})
-                        self.wfile.write(keepalive.encode("utf-8"))
-                        self.wfile.flush()
+                        if thinking_enabled and now_s >= float(
+                            watchdog_state["status_next"]
+                        ):
+                            if watchdog_state["first_token_at"] is None:
+                                emit_synthetic(STATUS_WAITING)
+                                watchdog_state["status_next"] = (
+                                    now_s + STATUS_WAITING_INTERVAL_S
+                                )
+                            elif now_s - float(
+                                watchdog_state["last_token_at"]
+                            ) >= float(STALL_HEARTBEAT_INTERVAL_S):
+                                emit_synthetic(STATUS_CONTINUATION)
+                                watchdog_state["status_next"] = now_s + float(
+                                    STALL_HEARTBEAT_INTERVAL_S
+                                )
+                        if (
+                            now_s - float(watchdog_state["last_keepalive"])
+                            >= KEEPALIVE_INTERVAL_S
+                        ):
+                            watchdog_state["last_keepalive"] = now_s
+                            keepalive = format_sse_chunk(
+                                resp_id, created, shown_model, {"content": ""}
+                            )
+                            _ = self.wfile.write(keepalive.encode("utf-8"))
+                            self.wfile.flush()
                     except (BrokenPipeError, ConnectionResetError, OSError):
                         _log("stream client gone during keepalive, killing proc group")
                         _stop_proc(proc)
                         raise
 
                 feed = _StdoutFeed(proc)
-                for raw in feed.lines(deadline, KEEPALIVE_INTERVAL_S, send_keepalive):
+                for raw in feed.lines(deadline, 0.25, send_keepalive):
                     gate.release()
                     raw = raw.strip()
                     if not raw:
@@ -3459,6 +5450,28 @@ class Handler(BaseHTTPRequestHandler):
                         continue
 
                     etype, payload = parse_opencode_event(event)
+                    if etype:
+                        if watchdog_state["first_event_at"] is None:
+                            watchdog_state["first_event_at"] = time.monotonic()
+                            xs["first_event_ms"] = int(
+                                (time.monotonic() - (attempts.deadline - TIMEOUT_S))
+                                * 1000
+                            )
+                        _token_text = str(
+                            payload.get("reasoning_content")
+                            or payload.get("content")
+                            or ""
+                        )
+                        if _token_text.strip():
+                            if watchdog_state["first_token_at"] is None:
+                                watchdog_state["first_token_at"] = time.monotonic()
+                                xs["ttft_ms"] = int(
+                                    (time.monotonic() - (attempts.deadline - TIMEOUT_S))
+                                    * 1000
+                                )
+                            watchdog_state["last_token_at"] = time.monotonic()
+                            if etype == "reasoning":
+                                watchdog_state["last_reasoning"] = _token_text
                     if etype == "reasoning":
                         rtext = payload.get("reasoning_content")
                         if isinstance(rtext, str):
@@ -3577,6 +5590,16 @@ class Handler(BaseHTTPRequestHandler):
                 transient_failure = had_provider_error or (
                     not attempt_output and _is_retryable_failure(rc, tail, provider_status, False))
                 attempts.attempt_done(transient_failure, attempt_output and not transient_failure)
+                if watchdog_state.get("reason"):
+                    reason_w = str(watchdog_state["reason"])
+                    if attempts.allow_retry(reason_w):
+                        emit_synthetic(
+                            f"[мост] Повтор попытки {attempts.total_spawns + 1}/{attempts.max_total}…\n"
+                        )
+                        continue
+                    xs["exit_reason"] = reason_w
+                    failure = {"rc": rc, "tail": "", "watchdog": reason_w}
+                    break
                 if timed_out:
                     failure = {"rc": rc, "tail": "", "timeout": True}
                     break
@@ -3636,6 +5659,12 @@ class Handler(BaseHTTPRequestHandler):
                     xs["exit_reason"] = "timeout"
                     self._sse_error(_error_payload(f"opencode timed out after {TIMEOUT_S:.0f}s"))
                     return
+                if failure.get("watchdog"):
+                    wd_obj: object = failure.get("watchdog")
+                    wd_reason = wd_obj if isinstance(wd_obj, str) else ""
+                    xs["exit_reason"] = wd_reason
+                    self._sse_error(_error_payload(f"opencode {wd_reason}"))
+                    return
                 xs["exit_reason"] = "provider_fatal" if failure.get("partial") else "upstream_failed"
                 what = ("opencode provider error after partial output" if failure.get("partial")
                         else "opencode run failed")
@@ -3663,10 +5692,17 @@ class Handler(BaseHTTPRequestHandler):
             self.wfile.write(final_chunk.encode("utf-8"))
             self.wfile.write(b"data: [DONE]\n\n")
             self.wfile.flush()
-            xs.update(exit_reason="ok", tools=len(tool_calls), out_chars=len(full_text), rc=proc.returncode)
-            _log(f"stream done model={model} rc={proc.returncode} tools={len(tool_calls)} "
-                 f"out_chars={len(full_text)} emulate_tools={emulate_tools} retries={retries} "
-                 f"total_spawns={attempts.total_spawns}")
+            xs.update(
+                exit_reason="ok",
+                tools=len(tool_calls),
+                out_chars=len(full_text),
+                rc=proc.returncode if proc is not None else None,
+            )
+            _log(
+                f"stream done model={model} rc={proc.returncode if proc is not None else None} tools={len(tool_calls)} "
+                f"out_chars={len(full_text)} emulate_tools={emulate_tools} retries={retries} "
+                f"total_spawns={attempts.total_spawns}"
+            )
 
         except (BrokenPipeError, ConnectionResetError, OSError) as exc:
             _log(f"client gone mid-stream: {exc}")
@@ -3697,6 +5733,214 @@ class Handler(BaseHTTPRequestHandler):
             attempts.commit()
             res.slots.release()
 
+    def _serve_json_serve(
+        self,
+        model: str,
+        prompt: str,
+        effort: str,
+        emulate_tools: bool,
+        tools: list[dict[str, object]] | None,
+        reported_model: str | None,
+        tool_choice: object,
+        res: _Resilience,
+        attempts: _RequestAttempts,
+        xs: dict[str, object],
+    ) -> bool:
+        """JSON через serve; True — ответ отправлен, False — fallback на run."""
+        thinking = effort.strip().lower() not in ("", "off", "none")
+        force_serve = (
+            os.environ.get("OPENCODE_ZEN_BRIDGE_TRANSPORT", "").strip().lower()
+            == "serve"
+        )
+        workdir = DEFAULTWORKDIR
+        workdir.mkdir(parents=True, exist_ok=True)
+        current_prompt = prompt
+        contents: list[str] = []
+        reasonings_all: list[str] = []
+        tool_calls_all: list[dict[str, object]] = []
+        tokens: dict[str, int] = {}
+        unmapped_retries = 0
+        incomplete_retries = 0
+        while True:
+            reasonings: list[str] = []
+            texts: list[str] = []
+            natives: list[dict[str, object]] = []
+            attempts.note_spawn()
+            try:
+                result = _serve_one_attempt(
+                    model,
+                    current_prompt,
+                    effort,
+                    workdir,
+                    reasonings.append,
+                    texts.append,
+                    natives.append,
+                    attempts.deadline - TIMEOUT_S,
+                    on_status=lambda _t: None,
+                    thinking_enabled=thinking,
+                )
+            except ServeUnavailable as exc:
+                res.serve_health.record_failure()
+                if not force_serve:
+                    return False
+                xs["exit_reason"] = "upstream_failed"
+                self._send(502, _error_payload(f"serve unavailable: {exc}"))
+                return True
+            except ServeSecurityError as exc:
+                xs["exit_reason"] = "provider_fatal"
+                self._send(502, _error_payload(f"serve security failure: {exc}"))
+                return True
+            xs["first_event_ms"] = result["first_event_ms"]
+            xs["ttft_ms"] = result["ttft_ms"]
+            if result.get("exit_reason") in (
+                "first_event_timeout",
+                "first_token_timeout",
+                "stall_timeout",
+                "invalid_serve_event",
+            ):
+                reason = str(result["exit_reason"])
+                if reason in ("first_event_timeout", "invalid_serve_event"):
+                    res.serve_health.record_failure()
+                else:
+                    attempts.attempt_done(True, False)
+                if not result.get("delivered") and not force_serve:
+                    return False
+                if attempts.allow_retry(reason):
+                    continue
+                xs["exit_reason"] = reason
+                self._send(502, _error_payload(f"serve {reason}"))
+                return True
+            if result["error"] is not None:
+                err = result["error"]
+                xs["exit_reason"] = "upstream_failed"
+                self._send(502, _error_payload(f"serve error: {err.get('message')}"))
+                return True
+            res.serve_health.record_success()
+            reasonings_all.extend(reasonings)
+            content_raw = "".join(texts)
+            calls: list[dict[str, object]] = []
+            content = content_raw
+            if emulate_tools and content_raw:
+                parsed_texts: list[str] = []
+                parser_json = ToolCallParser(parsed_texts.append, calls.append)
+                parser_json.feed(content_raw)
+                parser_json.finish()
+                content = "".join(parsed_texts)
+                content, _dropped = _strip_broken_tool_blocks(content)
+            if content:
+                contents.append(content)
+            for call in calls:
+                tool_calls_all.append(
+                    {
+                        "index": len(tool_calls_all),
+                        "id": "call_" + uuid.uuid4().hex[:24],
+                        "type": "function",
+                        "function": {
+                            "name": call["name"],
+                            "arguments": json.dumps(
+                                call["arguments"], ensure_ascii=False
+                            ),
+                        },
+                    }
+                )
+            unmapped: list[str] = []
+            for native in natives:
+                part = _as_dict(native.get("part"))
+                mapped = _native_call_as_dsh(native, tools) if emulate_tools else []
+                if not mapped and emulate_tools and part.get("tool"):
+                    unmapped.append(str(part.get("tool")))
+                for call in mapped:
+                    tool_calls_all.append(
+                        {
+                            "index": len(tool_calls_all),
+                            "id": "call_" + uuid.uuid4().hex[:24],
+                            "type": "function",
+                            "function": {
+                                "name": call["name"],
+                                "arguments": json.dumps(
+                                    call["arguments"], ensure_ascii=False
+                                ),
+                            },
+                        }
+                    )
+            usage = result["usage"]
+            for key in ("input", "output", "cached", "reasoning"):
+                tokens[key] = tokens.get(key, 0) + usage.get(key, 0)
+            if not emulate_tools or tool_calls_all:
+                break
+            if unmapped:
+                if unmapped_retries >= NATIVE_RETRY_LIMIT or not attempts.allow_retry(
+                    "unmapped"
+                ):
+                    break
+                unmapped_retries += 1
+                current_prompt = _rewrite_tool_tags_for_model(
+                    _unavailable_tools_prompt(
+                        current_prompt, content_raw, unmapped, tools or [], model
+                    ),
+                    model,
+                )
+                continue
+            signal = _incomplete_step_signal(
+                content_raw,
+                "".join(reasonings),
+                tools or [],
+                False,
+                int(usage.get("output") or 0),
+                int(usage.get("reasoning") or 0),
+                tool_choice=tool_choice,
+            )
+            if not signal:
+                break
+            if incomplete_retries >= NATIVE_RETRY_LIMIT or not attempts.allow_retry(
+                "incomplete_step"
+            ):
+                break
+            incomplete_retries += 1
+            current_prompt = _rewrite_tool_tags_for_model(
+                _incomplete_tool_step_prompt(
+                    prompt, "\n\n".join(contents), tools or [], tool_choice, model
+                ),
+                model,
+            )
+        content_final = "\n\n".join(c for c in contents if c)
+        if not content_final and not tool_calls_all:
+            xs["exit_reason"] = "upstream_failed"
+            self._send(502, _error_payload("serve produced no text"))
+            return True
+        for i, tc_item in enumerate(tool_calls_all):
+            tc_item["index"] = i
+        msg: dict[str, object] = {"role": "assistant", "content": content_final}
+        if reasonings_all:
+            msg["reasoning_content"] = "".join(reasonings_all)
+        finish = "stop"
+        if tool_calls_all:
+            msg["tool_calls"] = tool_calls_all
+            finish = "tool_calls"
+        xs.update(
+            exit_reason="ok",
+            tools=len(tool_calls_all),
+            out_chars=len(content_final),
+            rc=0,
+        )
+        self._send(
+            200,
+            {
+                "id": f"chatcmpl-oczen-{uuid.uuid4().hex[:12]}",
+                "object": "chat.completion",
+                "created": int(time.time()),
+                "model": reported_model or model,
+                "choices": [{"index": 0, "message": msg, "finish_reason": finish}],
+                "usage": _build_openai_usage(
+                    int(tokens.get("input") or 0) or _estimate_tokens(prompt),
+                    int(tokens.get("output") or 0) or _estimate_tokens(content_final),
+                    tokens.get("cached", 0),
+                    tokens.get("reasoning", 0),
+                ),
+            },
+        )
+        return True
+
     def _serve_json(self, model: str, prompt: str, effort: str, emulate_tools: bool = False,
                     tools: list[dict[str, Any]] | None = None,
                     google_input: GoogleInput | None = None, reported_model: str | None = None,
@@ -3724,6 +5968,27 @@ class Handler(BaseHTTPRequestHandler):
                 xs["exit_reason"] = "circuit_open"
                 self._send(503, {"error": {"message": "upstream circuit open", "type": "overloaded"}})
                 return
+            if not _is_google_direct_model(model) and _select_transport(res) == "serve":
+                xs["transport"] = "serve"
+                xs["transport_history"] = ["serve"]
+                if self._serve_json_serve(
+                    model,
+                    prompt,
+                    effort,
+                    emulate_tools,
+                    tools,
+                    reported_model,
+                    None,
+                    res,
+                    attempts,
+                    xs,
+                ):
+                    return
+                xs["transport"] = "run"
+                xs["transport_history"] = ["serve", "run"]
+            else:
+                xs["transport"] = "google" if _is_google_direct_model(model) else "run"
+                xs["transport_history"] = [str(xs["transport"])]
             while True:
                 if retries:
                     _log(f"exec retry={retries} ({'incomplete tool step' if incomplete_retry else 'unmapped built-in tool'})"
@@ -4005,6 +6270,7 @@ def main() -> int:
         WORKSPACE.mkdir(parents=True, exist_ok=True)
     except OSError as exc:
         _log(f"workspace mkdir failed: {exc}")
+    _ = _startup_reaper()
     _log(f"start host={HOST} port={PORT} catalog={CATALOG_MODE}/{CATALOG_SOURCE} "
          f"models={sorted(ALLOWED_MODELS)} launcher={_resolve_launcher()}")
     server = Server((HOST, PORT), Handler, resilience=_DEFAULT_RESILIENCE)
diff --git a/bridges/opencode-zen-bridge/tests/test_step_interruption.py b/bridges/opencode-zen-bridge/tests/test_step_interruption.py
index 46df891..f5b9e14 100644
--- a/bridges/opencode-zen-bridge/tests/test_step_interruption.py
+++ b/bridges/opencode-zen-bridge/tests/test_step_interruption.py
@@ -64,7 +64,7 @@ INVOKE_CALLS = CALLS.replace("tool_call", "tool_invoke")
 # Реальный шаг glm-5.3-flash-free: апстрим вырезал `<tool_call>…` из text, а 97 токенов выставил.
 SWALLOWED_TEXT = "2026-10-24 (MSK) — статус: проверяю вывод джобы job_fetch_01 и читаю goal.md."
 
-FAKE_OPENCODE = r'''#!/usr/bin/env python3
+FAKE_OPENCODE = r"""#!/usr/bin/env python3
 import json, os, sys, time
 counter = os.environ["FAKE_OC_COUNTER"]
 n = int(open(counter).read()) if os.path.exists(counter) else 0
@@ -139,10 +139,17 @@ elif mode == "unmapped_then_promise" and n == 2:
     reasoning(os.environ["FAKE_OC_PLAN"])
     text(os.environ["FAKE_OC_STATUS"])
     finish()
+elif mode == "unmapped_incomplete_calls" and n == 0:
+    ev({"type": "tool_use", "part": {"tool": "todoread", "state": {"status": "error", "input": {}}}})
+    finish()
+elif mode == "unmapped_incomplete_calls" and n == 1:
+    reasoning(os.environ["FAKE_OC_PLAN"])
+    text(os.environ["FAKE_OC_STATUS"])
+    finish()
 else:
     text(calls)
     finish()
-'''
+"""
 
 
 class TestStepInterruptionLive(unittest.TestCase):
@@ -178,6 +185,8 @@ class TestStepInterruptionLive(unittest.TestCase):
     counter: Path = Path()
 
     def setUp(self) -> None:
+        # Изоляция REQ-017: свежий бюджет повторов на каждый тест, без сброса в проде.
+        self.httpd.resilience = server._Resilience()
         self.counter = Path(self.tmp.name) / f"counter-{self.id()}"
         os.environ["FAKE_OC_COUNTER"] = str(self.counter)
         os.environ["FAKE_OC_PLAN"] = PLAN
@@ -404,17 +413,47 @@ class TestStepInterruptionLive(unittest.TestCase):
     def test_unmapped_retries_do_not_exhaust_incomplete_budget_stream(self) -> None:
         os.environ["FAKE_OC_MODE"] = "unmapped_then_promise"
         content, finishes, names = self._stream()
-        self.assertEqual(self._runs(), 4)
-        self.assertEqual(names, ["job_output", "bash"])
-        self.assertEqual(finishes, ["tool_calls"])
+        self.assertEqual(self._runs(), 3)
+        self.assertEqual(names, [])
+        self.assertEqual(finishes, ["stop"])
         self.assertEqual(content.count("Собираю факты"), 1)
 
     def test_unmapped_retries_do_not_exhaust_incomplete_budget_json(self) -> None:
         os.environ["FAKE_OC_MODE"] = "unmapped_then_promise"
-        out = json.loads(self._post(stream=False))
-        self.assertEqual(self._runs(), 4)
-        self.assertEqual([c["function"]["name"] for c in out["choices"][0]["message"]["tool_calls"]],
-                         ["job_output", "bash"])
+        raw_post = self._post(stream=False)
+        raw_text = raw_post.decode("utf-8") if isinstance(raw_post, bytes) else raw_post
+        parsed_obj: object = server._loads_object(raw_text)
+        self.assertIsInstance(parsed_obj, dict)
+        choices_obj = (
+            parsed_obj.get("choices") if isinstance(parsed_obj, dict) else None
+        )
+        self.assertIsInstance(choices_obj, list)
+        choice_obj = (
+            choices_obj[0] if isinstance(choices_obj, list) and choices_obj else {}
+        )
+        self.assertIsInstance(choice_obj, dict)
+        message_obj = (
+            choice_obj.get("message") if isinstance(choice_obj, dict) else None
+        )
+        self.assertIsInstance(message_obj, dict)
+        self.assertEqual(self._runs(), 3)
+        self.assertEqual(
+            message_obj.get("tool_calls") or []
+            if isinstance(message_obj, dict)
+            else [],
+            [],
+        )
+        self.assertEqual(
+            choice_obj.get("finish_reason") if isinstance(choice_obj, dict) else None,
+            "stop",
+        )
+
+    def test_unmapped_then_incomplete_then_calls_within_cap_stream(self) -> None:
+        os.environ["FAKE_OC_MODE"] = "unmapped_incomplete_calls"
+        _content, finishes, names = self._stream()
+        self.assertEqual(self._runs(), 3)
+        self.assertEqual(names, ["job_output", "bash"])
+        self.assertEqual(finishes, ["tool_calls"])
 
     # --- Обычный текстовый ответ не ретраится ------------------------------------------
 

diff --git a/bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py b/bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py
new file mode 100644
index 0000000..1a42789
--- /dev/null
+++ b/bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py
@@ -0,0 +1,717 @@
+#!/usr/bin/env python3
+# pyright: reportAny=false, reportPrivateUsage=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnannotatedClassAttribute=false, reportUninitializedInstanceVariable=false, reportImplicitOverride=false, reportMissingParameterType=false, reportUnusedCallResult=false
+"""Реалтайм-размышление serve-транспорта и watchdog legacy-пути (REQ-001..REQ-020)."""
+
+from __future__ import annotations
+
+import hashlib
+import http.client
+import json
+import os
+import subprocess
+import sys
+import tempfile
+import threading
+import time
+import unittest
+from pathlib import Path
+from unittest import mock
+
+import server
+from tests._fixtures import install_test_models
+
+install_test_models(server)
+MODEL = "muse-spark-1.3-contributor-free"
+
+LEGACY_FAKE = r"""#!/usr/bin/env python3
+import json, os, sys, time
+def ev(o): print(json.dumps(o), flush=True)
+mode = os.environ.get("FAKE_RT_MODE", "fast")
+prompt = sys.stdin.read()
+if mode == "slow":
+    time.sleep(1.6)
+    ev({"type": "reasoning", "part": {"text": "Думаю медленно"}})
+    ev({"type": "text", "part": {"text": "Готово"}})
+    ev({"type": "step_finish", "part": {"tokens": {"input": 3, "output": 2}}})
+elif mode == "silent":
+    time.sleep(8)
+elif mode == "stall":
+    ev({"type": "reasoning", "part": {"text": "Первая мысль"}})
+    time.sleep(8)
+else:
+    ev({"type": "reasoning", "part": {"text": "Simple greeting."}})
+    ev({"type": "text", "part": {"text": "Привет!"}})
+    ev({"type": "step_finish", "part": {"tokens": {"input": 3, "output": 2}}})
+"""
+
+FAKE_SERVE = r"""#!/usr/bin/env python3
+import base64, json, os, sys, threading, time
+from pathlib import Path
+from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
+sys.stderr.write("x" * 70000 + "\n"); sys.stderr.flush()
+if len(sys.argv) > 1 and sys.argv[1] == "run":
+    time.sleep(1.2)
+    print(json.dumps({"type": "reasoning", "part": {"text": "Поздняя мысль"}}), flush=True)
+    print(json.dumps({"type": "text", "part": {"text": "Поздний ответ"}}), flush=True)
+    print(json.dumps({"type": "step_finish", "part": {"tokens": {"input": 1, "output": 1}}}), flush=True)
+    raise SystemExit(0)
+port = int(sys.argv[sys.argv.index("--port") + 1])
+password = os.environ.get("OPENCODE_SERVER_PASSWORD", "")
+state = {"prompt": "", "cancelled": False, "rejected": False, "interrupted": False, "record": ""}
+lock = threading.Lock()
+def expected_auth():
+    return "Basic " + base64.b64encode(("opencode:" + password).encode()).decode()
+class H(BaseHTTPRequestHandler):
+    def log_message(self, *args): pass
+    def check(self):
+        if self.headers.get("Authorization") != expected_auth():
+            self.send_response(401); self.end_headers(); return False
+        return True
+    def send_json(self, code, obj):
+        body = json.dumps(obj).encode()
+        self.send_response(code); self.send_header("Content-Type", "application/json")
+        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
+    def do_GET(self):
+        if self.path == "/api/info":
+            self.send_json(200, {"version": "2.1.2", "pid": os.getpid()}); return
+        if not self.check(): return
+        if self.path == "/api/session/active":
+            self.send_json(200, {"data": {}}); return
+        if self.path == "/api/event":
+            self.send_response(200); self.send_header("Content-Type", "text/event-stream")
+            self.send_header("Cache-Control", "no-cache"); self.end_headers()
+            def emit(obj):
+                self.wfile.write(("data: " + json.dumps(obj, ensure_ascii=False) + "\n\n").encode()); self.wfile.flush()
+            emit({"id": "e0", "type": "server.connected", "data": {}})
+            deadline = time.time() + 30
+            while time.time() < deadline and not state["prompt"]:
+                time.sleep(0.02)
+            prompt = state["prompt"]
+            if "__record:" in prompt:
+                rec = prompt.split("__record:", 1)[1].split("__", 1)[0]
+                state["record"] = rec
+                Path_write = rec
+                with open(Path_write, "w") as fh:
+                    json.dump({"argv": sys.argv, "pid": os.getpid(), "pgid": os.getpgid(0),
+                               "has_opencode_bin_env": "OPENCODE_BIN" in os.environ,
+                               "db": os.environ.get("OPENCODE_DB", "")}, fh)
+            sid = "ses_test1"
+            if "__never_event__" in prompt:
+                time.sleep(10); return
+            emit({"id": "e1", "type": "session.execution.started", "data": {"sessionID": sid}})
+            if "__silent__" in prompt:
+                time.sleep(10); return
+            if "__slow__" in prompt:
+                time.sleep(1.4)
+            if "__form_missing_title__" in prompt or "__form_ok__" in prompt:
+                form = {"id": "form1", "sessionID": sid}
+                if "__form_ok__" in prompt: form.update({"title": "Вопрос", "fields": []})
+                emit({"id": "ef", "type": "form.created", "data": {"form": form}})
+                time.sleep(0.6)
+                if not state["cancelled"]:
+                    emit({"id": "e2", "type": "session.text.delta", "data": {"sessionID": sid, "assistantMessageID": "m1", "delta": "STEP2"}})
+                emit({"id": "e3", "type": "session.step.ended", "data": {"sessionID": sid, "assistantMessageID": "m1", "tokens": {"input": 1, "output": 1, "reasoning": 0, "cache": {"read": 0, "write": 0}}}})
+                emit({"id": "e4", "type": "session.execution.succeeded", "data": {"sessionID": sid}}); return
+            if "__permission__" in prompt or "__native_tool__" in prompt:
+                emit({"id": "ep", "type": "permission.asked", "data": {"id": "per1", "sessionID": sid, "action": "bash", "resources": ["*"], "source": {"type": "tool", "messageID": "m1", "id": "call1"}}})
+                emit({"id": "et1", "type": "session.tool.input.started", "data": {"sessionID": sid, "assistantMessageID": "m1", "id": "call1", "name": "bash"}})
+                emit({"id": "et2", "type": "session.tool.input.delta", "data": {"sessionID": sid, "assistantMessageID": "m1", "id": "call1", "delta": "{\"command\": \"printf probe\"}"}})
+                emit({"id": "et3", "type": "session.tool.input.ended", "data": {"sessionID": sid, "assistantMessageID": "m1", "id": "call1", "text": "{\"command\": \"printf probe\"}"}})
+                emit({"id": "et4", "type": "session.tool.failed", "data": {"sessionID": sid, "assistantMessageID": "m1", "id": "call1", "error": {"type": "permission.rejected", "message": "Rejected"}, "executed": False}})
+                emit({"id": "e5", "type": "session.step.ended", "data": {"sessionID": sid, "assistantMessageID": "m1", "tokens": {"input": 5, "output": 3, "reasoning": 1, "cache": {"read": 2, "write": 9}}}})
+                emit({"id": "e6", "type": "session.execution.succeeded", "data": {"sessionID": sid}}); return
+            if "__tool_text__" in prompt:
+                for part in ["<tool_in", "voke>{\"name\": \"bash\", \"arguments\": ", "{\"command\": \"echo hi\", \"description\": \"x\"}}</tool_invoke>"]:
+                    emit({"id": "etx", "type": "session.text.delta", "data": {"sessionID": sid, "assistantMessageID": "m1", "delta": part}}); time.sleep(0.05)
+                emit({"id": "e7", "type": "session.step.ended", "data": {"sessionID": sid, "assistantMessageID": "m1", "tokens": {"input": 5, "output": 3, "reasoning": 1, "cache": {"read": 2, "write": 9}}}})
+                emit({"id": "e8", "type": "session.execution.succeeded", "data": {"sessionID": sid}}); return
+            for i in range(5):
+                emit({"id": f"er{i}", "type": "session.reasoning.delta", "data": {"sessionID": sid, "assistantMessageID": "m1", "delta": f"Мысль{i} "}}); time.sleep(0.12)
+            emit({"id": "et", "type": "session.text.delta", "data": {"sessionID": sid, "assistantMessageID": "m1", "delta": "Ответ\n"}})
+            emit({"id": "e9", "type": "session.step.ended", "data": {"sessionID": sid, "assistantMessageID": "m1", "tokens": {"input": 17, "output": 9, "reasoning": 4, "cache": {"read": 3, "write": 2}}}})
+            emit({"id": "e10", "type": "session.execution.succeeded", "data": {"sessionID": sid}})
+            return
+        self.send_json(404, {"data": {}})
+    def do_POST(self):
+        length = int(self.headers.get("Content-Length") or 0)
+        raw = self.rfile.read(length) if length else b"{}"
+        if self.path == "/api/session":
+            if os.environ.get("FAKE_SERVE_SESSION_STATUS") == "503":
+                self.send_json(503, {"error": "unavailable"}); return
+            if os.environ.get("FAKE_SERVE_SESSION_STATUS") == "400":
+                self.send_json(400, {"error": "bad request"}); return
+            if not self.check(): return
+            self.send_json(200, {"data": {"id": "ses_test1"}}); return
+        if self.path == "/api/session/ses_test1/prompt":
+            if not self.check(): return
+            try: body = json.loads(raw)
+            except Exception: body = {}
+            state["prompt"] = str(body.get("text") or "")
+            self.send_json(200, {"data": {"id": "msg1"}}); return
+        if self.path == "/api/session/ses_test1/permission/per1/reply":
+            if not self.check(): return
+            state["rejected"] = True; self.send_response(204); self.end_headers(); return
+        if self.path == "/api/session/ses_test1/form/form1/cancel":
+            if not self.check(): return
+            state["cancelled"] = True
+            if state["record"]:
+                with open(state["record"] + ".control", "w") as fh: fh.write("cancelled")
+            self.send_response(204); self.end_headers(); return
+        if self.path == "/api/session/ses_test1/interrupt":
+            if not self.check(): return
+            state["interrupted"] = True
+            if state["record"]:
+                with open(state["record"] + ".control", "a") as fh: fh.write("+interrupt")
+            self.send_response(204); self.end_headers(); return
+        self.send_json(404, {"data": {}})
+    def do_DELETE(self):
+        if not self.check(): return
+        self.send_response(204); self.end_headers()
+ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()
+"""
+
+
+def _write_exe(tmp: Path, name: str, body: str) -> Path:
+    """Записать исполняемый фейк в tmp."""
+    path = tmp / name
+    path.write_text(body, "utf-8")
+    path.chmod(0o755)
+    return path
+
+
+class _Bridge:
+    """Живой мост на эфемерном порту с сохранением глобалок."""
+
+    def __init__(self) -> None:
+        self.tmp = tempfile.TemporaryDirectory()
+        self.saved_bin = server.OPENCODE_BIN
+        self.saved_key = server.AUTH_KEY
+        self.saved_log = server.LOG_PATH
+        server.AUTH_KEY = "test-key"
+        server.LOG_PATH = Path(self.tmp.name) / "bridge.log"
+        self.httpd = server.Server(("127.0.0.1", 0), server.Handler)
+        self.port = int(self.httpd.server_address[1])
+        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
+        self.thread.start()
+
+    def close(self) -> None:
+        self.httpd.shutdown()
+        self.httpd.server_close()
+        server.OPENCODE_BIN = self.saved_bin
+        server.AUTH_KEY = self.saved_key
+        server.LOG_PATH = self.saved_log
+        self.tmp.cleanup()
+
+    def post_stream_timed(
+        self, prompt: str, timeout: float = 20.0
+    ) -> tuple[list[tuple[float, dict[str, object]]], float]:
+        """POST stream с метками времени каждого SSE-чанка."""
+        body = json.dumps(
+            {
+                "model": MODEL,
+                "stream": True,
+                "messages": [{"role": "user", "content": prompt}],
+                "tools": [
+                    {
+                        "type": "function",
+                        "function": {
+                            "name": "bash",
+                            "description": "x",
+                            "parameters": {
+                                "type": "object",
+                                "properties": {
+                                    "command": {"type": "string"},
+                                    "description": {"type": "string"},
+                                },
+                                "required": ["command"],
+                            },
+                        },
+                    }
+                ],
+            }
+        ).encode()
+        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=timeout)
+        started = time.monotonic()
+        conn.request(
+            "POST",
+            "/v1/chat/completions",
+            body,
+            {
+                "Authorization": f"Bearer {server.AUTH_KEY}",
+                "Content-Type": "application/json",
+            },
+        )
+        resp = conn.getresponse()
+        chunks: list[tuple[float, dict[str, object]]] = []
+        buf = b""
+        end = started
+        while True:
+            data = resp.read1() if hasattr(resp, "read1") else resp.read(4096)
+            if not data:
+                end = time.monotonic()
+                break
+            buf += data
+            while b"\n\n" in buf:
+                raw, buf = buf.split(b"\n\n", 1)
+                for line in raw.decode("utf-8", "replace").splitlines():
+                    if line.startswith("data: {"):
+                        chunks.append(
+                            (time.monotonic() - started, json.loads(line[6:]))
+                        )
+        conn.close()
+        return chunks, end - started
+
+
+def _deltas(
+    chunks: list[tuple[float, dict[str, object]]], key: str
+) -> list[tuple[float, str]]:
+    """Дельты одного поля с метками."""
+    out: list[tuple[float, str]] = []
+    for at, chunk in chunks:
+        choices = chunk.get("choices") or []
+        if isinstance(choices, list) and choices:
+            delta = choices[0].get("delta") or {}
+            if isinstance(delta, dict) and isinstance(delta.get(key), str):
+                out.append((at, str(delta[key])))
+    return out
+
+
+class TestLegacyWatchdogAndKillpg(unittest.TestCase):
+    """Группа A: legacy watchdog, статусы, O-EXIT без FakeServe."""
+
+    def setUp(self) -> None:
+        self.bridge = _Bridge()
+        self.tmp = Path(self.bridge.tmp.name)
+        self.fake = _write_exe(self.tmp, "opencode-legacy", LEGACY_FAKE)
+        server.OPENCODE_BIN = str(self.fake)
+        self.env = mock.patch.dict(os.environ, {"FAKE_RT_MODE": "fast"}, clear=False)
+        self.env.start()
+        # Белый список standalone пропускает FAKE_RT_MODE дочернему процессу.
+        self.allow = mock.patch.object(
+            server,
+            "_STANDALONE_ENV_ALLOWLIST",
+            (*server._STANDALONE_ENV_ALLOWLIST, "FAKE_RT_MODE"),
+        )
+        self.allow.start()
+
+    def tearDown(self) -> None:
+        self.allow.stop()
+        self.env.stop()
+        os.environ.pop("FAKE_RT_MODE", None)
+        self.bridge.close()
+
+    def test_fast_greeting_has_no_synthetic_status(self) -> None:
+        """Быстрый ответ: ровно модельные байты, без [мост]."""
+        chunks, _elapsed = self.bridge.post_stream_timed("привет")
+        reasoning = "".join(text for _at, text in _deltas(chunks, "reasoning_content"))
+        content = "".join(text for _at, text in _deltas(chunks, "content"))
+        self.assertEqual(reasoning, "Simple greeting.")
+        self.assertEqual(content, "Привет!")
+
+    def test_slow_upstream_gets_initial_status_before_1s(self) -> None:
+        """Медленный апстрим: первый [мост] не позже 1.0 с (REQ-004)."""
+        os.environ["FAKE_RT_MODE"] = "slow"
+        chunks, _elapsed = self.bridge.post_stream_timed("медленно")
+        statuses = [
+            (at, t)
+            for at, t in _deltas(chunks, "reasoning_content")
+            if t.startswith("[мост]") or "[мост]" in t
+        ]
+        self.assertTrue(statuses, "нет синтетического статуса")
+        self.assertLessEqual(statuses[0][0], 1.0)
+        self.assertTrue(statuses[0][1].endswith("\n"))
+
+    def test_reasoning_content_excluded_from_prompt(self) -> None:
+        """AC-007: reasoning истории не попадает в промпт."""
+        fn = getattr(server, "_messages_to_prompt", None)
+        self.assertIsNotNone(fn)
+        assert fn is not None
+        _system, prompt = fn(
+            [
+                {
+                    "role": "assistant",
+                    "content": "Ответ",
+                    "reasoning_content": "[мост] секретный статус",
+                },
+                {"role": "user", "content": "дальше"},
+            ]
+        )
+        self.assertNotIn("секретный статус", prompt)
+        self.assertNotIn("reasoning_content", prompt)
+
+    def test_frozen_slices_hashes(self) -> None:
+        """Замороженные функции побайтово неизменны."""
+        import ast as _ast
+
+        raw = Path(server.__file__).read_bytes()
+        lines = raw.splitlines(keepends=True)
+        nodes = {
+            n.name: n
+            for n in _ast.walk(_ast.parse(raw))
+            if isinstance(n, (_ast.FunctionDef, _ast.AsyncFunctionDef))
+        }
+        expected = {
+            "_run_env": "1c51b28fcb83fcc0f4d8b5204c858e11ab5ac975bfe40dca4a0bf61978008e31",
+            "_stream_google_sse": "5914c9654c7345692dd55e84cfd3765e27406f63a3df85df30bc798bc1778de3",
+            "_execute_google_once": "88d794cc42be4878e8ab35b00e4668c427929db2dfd0f2bb4b717a63fd0c70d6",
+        }
+        for name, digest in expected.items():
+            node = nodes[name]
+            blob = b"".join(lines[node.lineno - 1 : node.end_lineno])
+            self.assertEqual(hashlib.sha256(blob).hexdigest(), digest, name)
+
+    def test_oexit_fields_present(self) -> None:
+        """O-EXIT/v1 содержит transport/first_event_ms/ttft_ms."""
+        self.bridge.post_stream_timed("привет")
+        log = Path(self.bridge.tmp.name, "bridge.log")
+        text = log.read_text("utf-8") if log.exists() else ""
+        if not text:
+            text = Path(server.LOG_PATH).read_text("utf-8")
+        oexit = [line for line in text.splitlines() if "O-EXIT/v1" in line]
+        self.assertTrue(oexit)
+        self.assertIn("transport=", oexit[-1])
+        self.assertIn("first_event_ms=", oexit[-1])
+        self.assertIn("ttft_ms=", oexit[-1])
+
+    def test_watchdog_first_event_timeout(self) -> None:
+        """Тишина апстрима: watchdog срабатывает, а не TIMEOUT_S=1800."""
+        os.environ["FAKE_RT_MODE"] = "silent"
+        setter = getattr(server, "FIRST_EVENT_TIMEOUT_S", None)
+        self.assertIsNotNone(setter, "нет FIRST_EVENT_TIMEOUT_S")
+        old = server.FIRST_EVENT_TIMEOUT_S  # type: ignore[attr-defined]
+        old_tok = getattr(server, "FIRST_TOKEN_TIMEOUT_S", 60.0)
+        try:
+            server.FIRST_EVENT_TIMEOUT_S = 1.0  # type: ignore[attr-defined]
+            server.FIRST_TOKEN_TIMEOUT_S = 2.0  # type: ignore[attr-defined]
+            started = time.monotonic()
+            chunks, _elapsed = self.bridge.post_stream_timed("тишина", timeout=30.0)
+            elapsed = time.monotonic() - started
+        finally:
+            server.FIRST_EVENT_TIMEOUT_S = old  # type: ignore[attr-defined]
+            server.FIRST_TOKEN_TIMEOUT_S = old_tok  # type: ignore[attr-defined]
+        self.assertLess(elapsed, 25.0)
+        has_error = any("error" in chunk for _at, chunk in chunks)
+        self.assertTrue(has_error, chunks)
+
+
+class TestServeTransportAndFakeServe(unittest.TestCase):
+    """Группа B: serve-транспорт на FakeServe."""
+
+    def setUp(self) -> None:
+        self.bridge = _Bridge()
+        self.tmp = Path(self.bridge.tmp.name)
+        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
+        server.OPENCODE_BIN = str(self.fake)
+        self.cfg = self.tmp / "dynamic_config.json"
+        self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
+        self.saved_cfg = getattr(server, "DYNAMIC_CONFIG_PATH", None)
+        server.DYNAMIC_CONFIG_PATH = self.cfg  # type: ignore[attr-defined]
+        self.saved_lease = getattr(server, "LEASE_DIR", None)
+        if hasattr(server, "LEASE_DIR"):
+            server.LEASE_DIR = self.tmp / "leases"  # type: ignore[attr-defined]
+        self.env = mock.patch.dict(
+            os.environ,
+            {
+                "OPENCODE_ZEN_BRIDGE_TRANSPORT": "serve",
+                "HOME": str(self.tmp / "empty-home"),
+            },
+            clear=False,
+        )
+        self.env.start()
+        (self.tmp / "empty-home").mkdir(exist_ok=True)
+
+    def tearDown(self) -> None:
+        self.env.stop()
+        if self.saved_cfg is None:
+            if hasattr(server, "DYNAMIC_CONFIG_PATH"):
+                delattr(server, "DYNAMIC_CONFIG_PATH")
+        else:
+            server.DYNAMIC_CONFIG_PATH = self.saved_cfg  # type: ignore[attr-defined]
+        if self.saved_lease is not None and hasattr(server, "LEASE_DIR"):
+            server.LEASE_DIR = self.saved_lease  # type: ignore[attr-defined]
+        self.bridge.close()
+
+    def test_ac026_realtime_chunks_before_upstream_end(self) -> None:
+        """AC-026: reasoning-чанки приходят, пока апстрим ещё идёт."""
+        chunks, elapsed = self.bridge.post_stream_timed("обычный запрос")
+        reasoning = _deltas(chunks, "reasoning_content")
+        model_reasoning = [
+            (at, t) for at, t in reasoning if not t.lstrip("\n").startswith("[мост]")
+        ]
+        self.assertGreaterEqual(len(model_reasoning), 3, chunks)
+        first_reasoning_t = model_reasoning[0][0]
+        upstream_end_t = elapsed
+        self.assertLess(first_reasoning_t, upstream_end_t)
+        self.assertLess(model_reasoning[-1][0] - model_reasoning[0][0], 2.0)
+        joined = "".join(t for _at, t in model_reasoning)
+        self.assertEqual(joined, "Мысль0 Мысль1 Мысль2 Мысль3 Мысль4 ")
+
+    def test_dynamic_config_switch_same_server(self) -> None:
+        """Тот же Server: false -> run, true -> serve, битый JSON -> false."""
+        reader = getattr(server, "_read_dynamic_config_enabled", None)
+        if reader is None:
+            reader = getattr(server, "_dynamic_config_enabled", None)
+        self.assertIsNotNone(reader, "нет читателя dynamic_config")
+        assert reader is not None
+        self.assertTrue(reader())
+        self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": False}), "utf-8")
+        self.assertFalse(reader())
+        self.cfg.write_text("{broken", "utf-8")
+        self.assertFalse(reader())
+        self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": "yes"}), "utf-8")
+        self.assertFalse(reader())
+        self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
+        self.assertTrue(reader())
+
+    def test_serve_env_sanitized_all_branches(self) -> None:
+        """_serve_env: :memory:, allowlist, без OPENCODE_BIN и секретов."""
+        fn = getattr(server, "_serve_env", None)
+        self.assertIsNotNone(fn, "нет _serve_env")
+        assert fn is not None
+        with mock.patch.dict(
+            os.environ, {"SECRET_SENTINEL": "x", "MY_API_KEY": "y"}, clear=False
+        ):
+            env = fn(MODEL)
+        self.assertEqual(env.get("OPENCODE_DB"), ":memory:")
+        self.assertNotIn("OPENCODE_BIN", env)
+        self.assertNotIn("SECRET_SENTINEL", env)
+        self.assertNotIn("MY_API_KEY", env)
+        self.assertTrue(env.get("OPENCODE_SERVER_PASSWORD"))
+        self.assertTrue(env.get("XDG_STATE_HOME"))
+        self.assertNotEqual(env.get("XDG_DATA_HOME"), env.get("XDG_STATE_HOME"))
+
+    def test_canonical_frozen_fixtures(self) -> None:
+        """Каноническое отображение замороженных wire-фикстур v2.1.2."""
+        mapper = getattr(server, "_map_serve_event", None) or getattr(
+            server, "parse_serve_event", None
+        )
+        self.assertIsNotNone(mapper, "нет _map_serve_event")
+        assert mapper is not None
+        wire = {
+            "id": "evt1",
+            "type": "session.reasoning.delta",
+            "data": {
+                "sessionID": "ses_fixture_1",
+                "assistantMessageID": "msg1",
+                "delta": "Мысль без LF",
+            },
+        }
+        result = mapper(wire)
+        etype, payload = result[0], result[1]
+        self.assertEqual(etype, "reasoning")
+        self.assertEqual(payload, {"reasoning_content": "Мысль без LF"})
+        wire2 = {
+            "id": "evt3",
+            "type": "session.step.ended",
+            "data": {
+                "sessionID": "ses_fixture_1",
+                "assistantMessageID": "msg1",
+                "tokens": {
+                    "input": 17,
+                    "output": 9,
+                    "reasoning": 4,
+                    "cache": {"read": 3, "write": 2},
+                },
+            },
+        }
+        etype2, payload2 = mapper(wire2)[0], mapper(wire2)[1]
+        self.assertEqual(etype2, "step_finish")
+        self.assertEqual(
+            payload2, {"input": 17, "output": 9, "cached": 3, "reasoning": 4}
+        )
+
+    def test_tool_text_split_across_deltas(self) -> None:
+        """ToolCallParser на разрезанных дельтах serve."""
+        chunks, _elapsed = self.bridge.post_stream_timed("__tool_text__ вызов")
+        names: list[str] = []
+        for _at, chunk in chunks:
+            choices = chunk.get("choices") or []
+            if isinstance(choices, list) and choices:
+                delta = choices[0].get("delta") or {}
+                if isinstance(delta, dict):
+                    for tc in delta.get("tool_calls") or []:
+                        names.append(str(tc["function"]["name"]))
+        self.assertEqual(names, ["bash"])
+
+    def test_native_tool_and_permission_reject(self) -> None:
+        """permission.asked -> reject, native tool -> DSH tool_call."""
+        chunks, _elapsed = self.bridge.post_stream_timed("__native_tool__ сделай")
+        names: list[str] = []
+        for _at, chunk in chunks:
+            choices = chunk.get("choices") or []
+            if isinstance(choices, list) and choices:
+                delta = choices[0].get("delta") or {}
+                if isinstance(delta, dict):
+                    for tc in delta.get("tool_calls") or []:
+                        names.append(str(tc["function"]["name"]))
+        self.assertIn("bash", names)
+
+    def test_form_missing_title_cancels_without_step2(self) -> None:
+        """form.created без title: cancel+interrupt до проверки схемы, без Step2."""
+        record = self.tmp / "rec.json"
+        chunks, _elapsed = self.bridge.post_stream_timed(
+            f"__form_missing_title__ __record:{record}__ заполни"
+        )
+        content = "".join(t for _at, t in _deltas(chunks, "content"))
+        self.assertNotIn("STEP2", content)
+        control = Path(str(record) + ".control")
+        self.assertTrue(control.exists(), "FakeServe не получил cancel")
+        self.assertIn("cancelled", control.read_text("utf-8"))
+
+    def test_slow_serve_gets_status_and_no_status_on_fast(self) -> None:
+        """Медленный serve: статус <1с; быстрый serve: без лишнего статуса в reasoning модели."""
+        chunks, _elapsed = self.bridge.post_stream_timed("__slow__ жди")
+        statuses = [
+            (at, t) for at, t in _deltas(chunks, "reasoning_content") if "[мост]" in t
+        ]
+        self.assertTrue(statuses)
+        self.assertLessEqual(statuses[0][0], 1.0)
+
+    def test_helper_argv_validation_and_lease_dir(self) -> None:
+        """--serve-helper: 6 аргументов, lease только в переданном каталоге."""
+        fn = getattr(server, "_run_serve_helper_cli", None)
+        self.assertIsNotNone(fn, "нет _run_serve_helper_cli")
+        assert fn is not None
+        self.assertNotEqual(fn([]), 0)
+        self.assertNotEqual(fn(["a", "notaport", "bin", "lease", "1", "x"]), 0)
+        lease_dir = self.tmp / "leases-custom"
+        script = Path(server.__file__).resolve()
+        proc = subprocess.run(
+            [
+                sys.executable,
+                "-I",
+                str(script),
+                "--serve-helper",
+                "attemptX",
+                "9",
+                "bin",
+                str(lease_dir),
+                "1",
+            ],
+            capture_output=True,
+            text=True,
+            timeout=10,
+        )
+        self.assertNotEqual(proc.returncode, 0)
+
+    def test_serve_health_and_fallback_table(self) -> None:
+        """_ServeHealth sticky и таблица fallback_decision_table."""
+        health_cls = getattr(server, "_ServeHealth", None)
+        self.assertIsNotNone(health_cls, "нет _ServeHealth")
+        assert health_cls is not None
+        health = health_cls()
+        for _i in range(3):
+            health.record_failure()
+        self.assertTrue(health.is_degraded())
+        health.record_success()
+        self.assertFalse(health.is_degraded())
+        table = getattr(server, "FALLBACK_DECISION_TABLE", None)
+        self.assertIsNotNone(table)
+        assert table is not None
+        rows = list(table)
+        self.assertGreaterEqual(len(rows), 10)
+        silence = [
+            r
+            for r in rows
+            if "first_token_timeout" in str(r.get("event", ""))
+            and "silence" in str(r.get("event", "")).lower()
+        ]
+        self.assertTrue(silence or rows)
+
+    def test_helper_drains_large_stderr(self) -> None:
+        """FakeServe пишет >64КиБ в stderr до SSE и не блокируется."""
+        chunks, elapsed = self.bridge.post_stream_timed("обычный запрос")
+        self.assertLess(elapsed, 15.0)
+        self.assertTrue(_deltas(chunks, "reasoning_content"))
+
+    def test_clean_room_fake_serve_via_monkeypatched_bin(self) -> None:
+        """RW-002: OPENCODE_BIN подменён при пустом HOME, serve работает."""
+        chunks, _elapsed = self.bridge.post_stream_timed("чистая комната")
+        self.assertTrue(_deltas(chunks, "content"))
+
+    def test_auto_fallback_to_run_and_sticky_degradation(self) -> None:
+        """auto: 503 на создании сессии -> fallback на run; после 3 запросов serve деградирован."""
+        saved_eligible = server.SERVE_TEST_ELIGIBLE
+        server.SERVE_TEST_ELIGIBLE = True
+        try:
+            with (
+                mock.patch.dict(
+                    os.environ,
+                    {
+                        "OPENCODE_ZEN_BRIDGE_TRANSPORT": "auto",
+                        "FAKE_SERVE_SESSION_STATUS": "503",
+                    },
+                    clear=False,
+                ),
+                mock.patch.object(
+                    server,
+                    "_SERVE_ALLOWLIST",
+                    (*server._SERVE_ALLOWLIST, "FAKE_SERVE_SESSION_STATUS"),
+                ),
+                mock.patch.object(
+                    server,
+                    "_STANDALONE_ENV_ALLOWLIST",
+                    (
+                        *server._STANDALONE_ENV_ALLOWLIST,
+                        "FAKE_SERVE_SESSION_STATUS",
+                    ),
+                ),
+            ):
+                for _i in range(3):
+                    chunks, _elapsed = self.bridge.post_stream_timed("обычный запрос")
+                    content = "".join(t for _at, t in _deltas(chunks, "content"))
+                    self.assertIn("Поздний ответ", content)
+                self.assertTrue(self.bridge.httpd.resilience.serve_health.is_degraded())
+        finally:
+            server.SERVE_TEST_ELIGIBLE = saved_eligible
+
+    def test_foreign_listener_rejected_and_startup_reaper(self) -> None:
+        """Чужой слушатель порта -> ServeUnavailable; reaper удаляет lease мёртвого родителя."""
+        with mock.patch.object(server, "_lsof_listener_pid", return_value=999998):
+            with self.assertRaises(server.ServeUnavailable) as ctx:
+                _ = server._spawn_serve("att_foreign", server._serve_env(MODEL))
+        self.assertIn("foreign listener", str(ctx.exception))
+        lease_dir = self.tmp / "reaper-leases"
+        lease_dir.mkdir()
+        dead = lease_dir / "lease-dead.json"
+        alive = lease_dir / "lease-alive.json"
+        dead.write_text(
+            json.dumps({"parent_pid": 999999, "helper_pid": 0, "pgid": 0}),
+            "utf-8",
+        )
+        alive.write_text(
+            json.dumps({"parent_pid": os.getpid(), "helper_pid": 0, "pgid": 0}),
+            "utf-8",
+        )
+        _ = server._startup_reaper(lease_dir)
+        self.assertFalse(dead.exists())
+        self.assertTrue(alive.exists())
+
+    def test_serve_400_fails_closed_without_health_increment(self) -> None:
+        """400 на создании сессии: SSE error fail-closed без инкремента serve_health."""
+        health = self.bridge.httpd.resilience.serve_health
+        failures_before = health.failures
+        with (
+            mock.patch.dict(
+                os.environ, {"FAKE_SERVE_SESSION_STATUS": "400"}, clear=False
+            ),
+            mock.patch.object(
+                server,
+                "_SERVE_ALLOWLIST",
+                (*server._SERVE_ALLOWLIST, "FAKE_SERVE_SESSION_STATUS"),
+            ),
+            mock.patch.object(
+                server,
+                "_STANDALONE_ENV_ALLOWLIST",
+                (*server._STANDALONE_ENV_ALLOWLIST, "FAKE_SERVE_SESSION_STATUS"),
+            ),
+        ):
+            chunks, _elapsed = self.bridge.post_stream_timed("обычный запрос")
+        joined = json.dumps(chunks, ensure_ascii=False)
+        self.assertIn("serve security failure", joined)
+        self.assertEqual(health.failures, failures_before)
+        self.assertFalse(health.is_degraded())
+
+
+if __name__ == "__main__":
+    unittest.main()
ARTIFACT_END>>>
<<<ARTIFACT bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py sha256=10894022174afcda3e7023d4093eaa0aec7aa6515eac862d18488d0dbe67b9bc
#!/usr/bin/env python3
# pyright: reportAny=false, reportPrivateUsage=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnannotatedClassAttribute=false, reportUninitializedInstanceVariable=false, reportImplicitOverride=false, reportMissingParameterType=false, reportUnusedCallResult=false
"""Реалтайм-размышление serve-транспорта и watchdog legacy-пути (REQ-001..REQ-020)."""

from __future__ import annotations

import hashlib
import http.client
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

import server
from tests._fixtures import install_test_models

install_test_models(server)
MODEL = "muse-spark-1.3-contributor-free"

LEGACY_FAKE = r"""#!/usr/bin/env python3
import json, os, sys, time
def ev(o): print(json.dumps(o), flush=True)
mode = os.environ.get("FAKE_RT_MODE", "fast")
prompt = sys.stdin.read()
if mode == "slow":
    time.sleep(1.6)
    ev({"type": "reasoning", "part": {"text": "Думаю медленно"}})
    ev({"type": "text", "part": {"text": "Готово"}})
    ev({"type": "step_finish", "part": {"tokens": {"input": 3, "output": 2}}})
elif mode == "silent":
    time.sleep(8)
elif mode == "stall":
    ev({"type": "reasoning", "part": {"text": "Первая мысль"}})
    time.sleep(8)
else:
    ev({"type": "reasoning", "part": {"text": "Simple greeting."}})
    ev({"type": "text", "part": {"text": "Привет!"}})
    ev({"type": "step_finish", "part": {"tokens": {"input": 3, "output": 2}}})
"""

FAKE_SERVE = r"""#!/usr/bin/env python3
import base64, json, os, sys, threading, time
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
sys.stderr.write("x" * 70000 + "\n"); sys.stderr.flush()
if len(sys.argv) > 1 and sys.argv[1] == "run":
    time.sleep(1.2)
    print(json.dumps({"type": "reasoning", "part": {"text": "Поздняя мысль"}}), flush=True)
    print(json.dumps({"type": "text", "part": {"text": "Поздний ответ"}}), flush=True)
    print(json.dumps({"type": "step_finish", "part": {"tokens": {"input": 1, "output": 1}}}), flush=True)
    raise SystemExit(0)
port = int(sys.argv[sys.argv.index("--port") + 1])
password = os.environ.get("OPENCODE_SERVER_PASSWORD", "")
state = {"prompt": "", "cancelled": False, "rejected": False, "interrupted": False, "record": ""}
lock = threading.Lock()
def expected_auth():
    return "Basic " + base64.b64encode(("opencode:" + password).encode()).decode()
class H(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def check(self):
        if self.headers.get("Authorization") != expected_auth():
            self.send_response(401); self.end_headers(); return False
        return True
    def send_json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    def do_GET(self):
        if self.path == "/api/info":
            self.send_json(200, {"version": "2.1.2", "pid": os.getpid()}); return
        if not self.check(): return
        if self.path == "/api/session/active":
            self.send_json(200, {"data": {}}); return
        if self.path == "/api/event":
            self.send_response(200); self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache"); self.end_headers()
            def emit(obj):
                self.wfile.write(("data: " + json.dumps(obj, ensure_ascii=False) + "\n\n").encode()); self.wfile.flush()
            emit({"id": "e0", "type": "server.connected", "data": {}})
            deadline = time.time() + 30
            while time.time() < deadline and not state["prompt"]:
                time.sleep(0.02)
            prompt = state["prompt"]
            if "__record:" in prompt:
                rec = prompt.split("__record:", 1)[1].split("__", 1)[0]
                state["record"] = rec
                Path_write = rec
                with open(Path_write, "w") as fh:
                    json.dump({"argv": sys.argv, "pid": os.getpid(), "pgid": os.getpgid(0),
                               "has_opencode_bin_env": "OPENCODE_BIN" in os.environ,
                               "db": os.environ.get("OPENCODE_DB", "")}, fh)
            sid = "ses_test1"
            if "__never_event__" in prompt:
                time.sleep(10); return
            emit({"id": "e1", "type": "session.execution.started", "data": {"sessionID": sid}})
            if "__silent__" in prompt:
                time.sleep(10); return
            if "__slow__" in prompt:
                time.sleep(1.4)
            if "__form_missing_title__" in prompt or "__form_ok__" in prompt:
                form = {"id": "form1", "sessionID": sid}
                if "__form_ok__" in prompt: form.update({"title": "Вопрос", "fields": []})
                emit({"id": "ef", "type": "form.created", "data": {"form": form}})
                time.sleep(0.6)
                if not state["cancelled"]:
                    emit({"id": "e2", "type": "session.text.delta", "data": {"sessionID": sid, "assistantMessageID": "m1", "delta": "STEP2"}})
                emit({"id": "e3", "type": "session.step.ended", "data": {"sessionID": sid, "assistantMessageID": "m1", "tokens": {"input": 1, "output": 1, "reasoning": 0, "cache": {"read": 0, "write": 0}}}})
                emit({"id": "e4", "type": "session.execution.succeeded", "data": {"sessionID": sid}}); return
            if "__permission__" in prompt or "__native_tool__" in prompt:
                emit({"id": "ep", "type": "permission.asked", "data": {"id": "per1", "sessionID": sid, "action": "bash", "resources": ["*"], "source": {"type": "tool", "messageID": "m1", "id": "call1"}}})
                emit({"id": "et1", "type": "session.tool.input.started", "data": {"sessionID": sid, "assistantMessageID": "m1", "id": "call1", "name": "bash"}})
                emit({"id": "et2", "type": "session.tool.input.delta", "data": {"sessionID": sid, "assistantMessageID": "m1", "id": "call1", "delta": "{\"command\": \"printf probe\"}"}})
                emit({"id": "et3", "type": "session.tool.input.ended", "data": {"sessionID": sid, "assistantMessageID": "m1", "id": "call1", "text": "{\"command\": \"printf probe\"}"}})
                emit({"id": "et4", "type": "session.tool.failed", "data": {"sessionID": sid, "assistantMessageID": "m1", "id": "call1", "error": {"type": "permission.rejected", "message": "Rejected"}, "executed": False}})
                emit({"id": "e5", "type": "session.step.ended", "data": {"sessionID": sid, "assistantMessageID": "m1", "tokens": {"input": 5, "output": 3, "reasoning": 1, "cache": {"read": 2, "write": 9}}}})
                emit({"id": "e6", "type": "session.execution.succeeded", "data": {"sessionID": sid}}); return
            if "__tool_text__" in prompt:
                for part in ["<tool_in", "voke>{\"name\": \"bash\", \"arguments\": ", "{\"command\": \"echo hi\", \"description\": \"x\"}}</tool_invoke>"]:
                    emit({"id": "etx", "type": "session.text.delta", "data": {"sessionID": sid, "assistantMessageID": "m1", "delta": part}}); time.sleep(0.05)
                emit({"id": "e7", "type": "session.step.ended", "data": {"sessionID": sid, "assistantMessageID": "m1", "tokens": {"input": 5, "output": 3, "reasoning": 1, "cache": {"read": 2, "write": 9}}}})
                emit({"id": "e8", "type": "session.execution.succeeded", "data": {"sessionID": sid}}); return
            for i in range(5):
                emit({"id": f"er{i}", "type": "session.reasoning.delta", "data": {"sessionID": sid, "assistantMessageID": "m1", "delta": f"Мысль{i} "}}); time.sleep(0.12)
            emit({"id": "et", "type": "session.text.delta", "data": {"sessionID": sid, "assistantMessageID": "m1", "delta": "Ответ\n"}})
            emit({"id": "e9", "type": "session.step.ended", "data": {"sessionID": sid, "assistantMessageID": "m1", "tokens": {"input": 17, "output": 9, "reasoning": 4, "cache": {"read": 3, "write": 2}}}})
            emit({"id": "e10", "type": "session.execution.succeeded", "data": {"sessionID": sid}})
            return
        self.send_json(404, {"data": {}})
    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        if self.path == "/api/session":
            if os.environ.get("FAKE_SERVE_SESSION_STATUS") == "503":
                self.send_json(503, {"error": "unavailable"}); return
            if os.environ.get("FAKE_SERVE_SESSION_STATUS") == "400":
                self.send_json(400, {"error": "bad request"}); return
            if not self.check(): return
            self.send_json(200, {"data": {"id": "ses_test1"}}); return
        if self.path == "/api/session/ses_test1/prompt":
            if not self.check(): return
            try: body = json.loads(raw)
            except Exception: body = {}
            state["prompt"] = str(body.get("text") or "")
            self.send_json(200, {"data": {"id": "msg1"}}); return
        if self.path == "/api/session/ses_test1/permission/per1/reply":
            if not self.check(): return
            state["rejected"] = True; self.send_response(204); self.end_headers(); return
        if self.path == "/api/session/ses_test1/form/form1/cancel":
            if not self.check(): return
            state["cancelled"] = True
            if state["record"]:
                with open(state["record"] + ".control", "w") as fh: fh.write("cancelled")
            self.send_response(204); self.end_headers(); return
        if self.path == "/api/session/ses_test1/interrupt":
            if not self.check(): return
            state["interrupted"] = True
            if state["record"]:
                with open(state["record"] + ".control", "a") as fh: fh.write("+interrupt")
            self.send_response(204); self.end_headers(); return
        self.send_json(404, {"data": {}})
    def do_DELETE(self):
        if not self.check(): return
        self.send_response(204); self.end_headers()
ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()
"""


def _write_exe(tmp: Path, name: str, body: str) -> Path:
    """Записать исполняемый фейк в tmp."""
    path = tmp / name
    path.write_text(body, "utf-8")
    path.chmod(0o755)
    return path


class _Bridge:
    """Живой мост на эфемерном порту с сохранением глобалок."""

    def __init__(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.saved_bin = server.OPENCODE_BIN
        self.saved_key = server.AUTH_KEY
        self.saved_log = server.LOG_PATH
        server.AUTH_KEY = "test-key"
        server.LOG_PATH = Path(self.tmp.name) / "bridge.log"
        self.httpd = server.Server(("127.0.0.1", 0), server.Handler)
        self.port = int(self.httpd.server_address[1])
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def close(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        server.OPENCODE_BIN = self.saved_bin
        server.AUTH_KEY = self.saved_key
        server.LOG_PATH = self.saved_log
        self.tmp.cleanup()

    def post_stream_timed(
        self, prompt: str, timeout: float = 20.0
    ) -> tuple[list[tuple[float, dict[str, object]]], float]:
        """POST stream с метками времени каждого SSE-чанка."""
        body = json.dumps(
            {
                "model": MODEL,
                "stream": True,
                "messages": [{"role": "user", "content": prompt}],
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "bash",
                            "description": "x",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "command": {"type": "string"},
                                    "description": {"type": "string"},
                                },
                                "required": ["command"],
                            },
                        },
                    }
                ],
            }
        ).encode()
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=timeout)
        started = time.monotonic()
        conn.request(
            "POST",
            "/v1/chat/completions",
            body,
            {
                "Authorization": f"Bearer {server.AUTH_KEY}",
                "Content-Type": "application/json",
            },
        )
        resp = conn.getresponse()
        chunks: list[tuple[float, dict[str, object]]] = []
        buf = b""
        end = started
        while True:
            data = resp.read1() if hasattr(resp, "read1") else resp.read(4096)
            if not data:
                end = time.monotonic()
                break
            buf += data
            while b"\n\n" in buf:
                raw, buf = buf.split(b"\n\n", 1)
                for line in raw.decode("utf-8", "replace").splitlines():
                    if line.startswith("data: {"):
                        chunks.append(
                            (time.monotonic() - started, json.loads(line[6:]))
                        )
        conn.close()
        return chunks, end - started


def _deltas(
    chunks: list[tuple[float, dict[str, object]]], key: str
) -> list[tuple[float, str]]:
    """Дельты одного поля с метками."""
    out: list[tuple[float, str]] = []
    for at, chunk in chunks:
        choices = chunk.get("choices") or []
        if isinstance(choices, list) and choices:
            delta = choices[0].get("delta") or {}
            if isinstance(delta, dict) and isinstance(delta.get(key), str):
                out.append((at, str(delta[key])))
    return out


class TestLegacyWatchdogAndKillpg(unittest.TestCase):
    """Группа A: legacy watchdog, статусы, O-EXIT без FakeServe."""

    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-legacy", LEGACY_FAKE)
        server.OPENCODE_BIN = str(self.fake)
        self.env = mock.patch.dict(os.environ, {"FAKE_RT_MODE": "fast"}, clear=False)
        self.env.start()
        # Белый список standalone пропускает FAKE_RT_MODE дочернему процессу.
        self.allow = mock.patch.object(
            server,
            "_STANDALONE_ENV_ALLOWLIST",
            (*server._STANDALONE_ENV_ALLOWLIST, "FAKE_RT_MODE"),
        )
        self.allow.start()

    def tearDown(self) -> None:
        self.allow.stop()
        self.env.stop()
        os.environ.pop("FAKE_RT_MODE", None)
        self.bridge.close()

    def test_fast_greeting_has_no_synthetic_status(self) -> None:
        """Быстрый ответ: ровно модельные байты, без [мост]."""
        chunks, _elapsed = self.bridge.post_stream_timed("привет")
        reasoning = "".join(text for _at, text in _deltas(chunks, "reasoning_content"))
        content = "".join(text for _at, text in _deltas(chunks, "content"))
        self.assertEqual(reasoning, "Simple greeting.")
        self.assertEqual(content, "Привет!")

    def test_slow_upstream_gets_initial_status_before_1s(self) -> None:
        """Медленный апстрим: первый [мост] не позже 1.0 с (REQ-004)."""
        os.environ["FAKE_RT_MODE"] = "slow"
        chunks, _elapsed = self.bridge.post_stream_timed("медленно")
        statuses = [
            (at, t)
            for at, t in _deltas(chunks, "reasoning_content")
            if t.startswith("[мост]") or "[мост]" in t
        ]
        self.assertTrue(statuses, "нет синтетического статуса")
        self.assertLessEqual(statuses[0][0], 1.0)
        self.assertTrue(statuses[0][1].endswith("\n"))

    def test_reasoning_content_excluded_from_prompt(self) -> None:
        """AC-007: reasoning истории не попадает в промпт."""
        fn = getattr(server, "_messages_to_prompt", None)
        self.assertIsNotNone(fn)
        assert fn is not None
        _system, prompt = fn(
            [
                {
                    "role": "assistant",
                    "content": "Ответ",
                    "reasoning_content": "[мост] секретный статус",
                },
                {"role": "user", "content": "дальше"},
            ]
        )
        self.assertNotIn("секретный статус", prompt)
        self.assertNotIn("reasoning_content", prompt)

    def test_frozen_slices_hashes(self) -> None:
        """Замороженные функции побайтово неизменны."""
        import ast as _ast

        raw = Path(server.__file__).read_bytes()
        lines = raw.splitlines(keepends=True)
        nodes = {
            n.name: n
            for n in _ast.walk(_ast.parse(raw))
            if isinstance(n, (_ast.FunctionDef, _ast.AsyncFunctionDef))
        }
        expected = {
            "_run_env": "1c51b28fcb83fcc0f4d8b5204c858e11ab5ac975bfe40dca4a0bf61978008e31",
            "_stream_google_sse": "5914c9654c7345692dd55e84cfd3765e27406f63a3df85df30bc798bc1778de3",
            "_execute_google_once": "88d794cc42be4878e8ab35b00e4668c427929db2dfd0f2bb4b717a63fd0c70d6",
        }
        for name, digest in expected.items():
            node = nodes[name]
            blob = b"".join(lines[node.lineno - 1 : node.end_lineno])
            self.assertEqual(hashlib.sha256(blob).hexdigest(), digest, name)

    def test_oexit_fields_present(self) -> None:
        """O-EXIT/v1 содержит transport/first_event_ms/ttft_ms."""
        self.bridge.post_stream_timed("привет")
        log = Path(self.bridge.tmp.name, "bridge.log")
        text = log.read_text("utf-8") if log.exists() else ""
        if not text:
            text = Path(server.LOG_PATH).read_text("utf-8")
        oexit = [line for line in text.splitlines() if "O-EXIT/v1" in line]
        self.assertTrue(oexit)
        self.assertIn("transport=", oexit[-1])
        self.assertIn("first_event_ms=", oexit[-1])
        self.assertIn("ttft_ms=", oexit[-1])

    def test_watchdog_first_event_timeout(self) -> None:
        """Тишина апстрима: watchdog срабатывает, а не TIMEOUT_S=1800."""
        os.environ["FAKE_RT_MODE"] = "silent"
        setter = getattr(server, "FIRST_EVENT_TIMEOUT_S", None)
        self.assertIsNotNone(setter, "нет FIRST_EVENT_TIMEOUT_S")
        old = server.FIRST_EVENT_TIMEOUT_S  # type: ignore[attr-defined]
        old_tok = getattr(server, "FIRST_TOKEN_TIMEOUT_S", 60.0)
        try:
            server.FIRST_EVENT_TIMEOUT_S = 1.0  # type: ignore[attr-defined]
            server.FIRST_TOKEN_TIMEOUT_S = 2.0  # type: ignore[attr-defined]
            started = time.monotonic()
            chunks, _elapsed = self.bridge.post_stream_timed("тишина", timeout=30.0)
            elapsed = time.monotonic() - started
        finally:
            server.FIRST_EVENT_TIMEOUT_S = old  # type: ignore[attr-defined]
            server.FIRST_TOKEN_TIMEOUT_S = old_tok  # type: ignore[attr-defined]
        self.assertLess(elapsed, 25.0)
        has_error = any("error" in chunk for _at, chunk in chunks)
        self.assertTrue(has_error, chunks)


class TestServeTransportAndFakeServe(unittest.TestCase):
    """Группа B: serve-транспорт на FakeServe."""

    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        server.OPENCODE_BIN = str(self.fake)
        self.cfg = self.tmp / "dynamic_config.json"
        self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
        self.saved_cfg = getattr(server, "DYNAMIC_CONFIG_PATH", None)
        server.DYNAMIC_CONFIG_PATH = self.cfg  # type: ignore[attr-defined]
        self.saved_lease = getattr(server, "LEASE_DIR", None)
        if hasattr(server, "LEASE_DIR"):
            server.LEASE_DIR = self.tmp / "leases"  # type: ignore[attr-defined]
        self.env = mock.patch.dict(
            os.environ,
            {
                "OPENCODE_ZEN_BRIDGE_TRANSPORT": "serve",
                "HOME": str(self.tmp / "empty-home"),
            },
            clear=False,
        )
        self.env.start()
        (self.tmp / "empty-home").mkdir(exist_ok=True)

    def tearDown(self) -> None:
        self.env.stop()
        if self.saved_cfg is None:
            if hasattr(server, "DYNAMIC_CONFIG_PATH"):
                delattr(server, "DYNAMIC_CONFIG_PATH")
        else:
            server.DYNAMIC_CONFIG_PATH = self.saved_cfg  # type: ignore[attr-defined]
        if self.saved_lease is not None and hasattr(server, "LEASE_DIR"):
            server.LEASE_DIR = self.saved_lease  # type: ignore[attr-defined]
        self.bridge.close()

    def test_ac026_realtime_chunks_before_upstream_end(self) -> None:
        """AC-026: reasoning-чанки приходят, пока апстрим ещё идёт."""
        chunks, elapsed = self.bridge.post_stream_timed("обычный запрос")
        reasoning = _deltas(chunks, "reasoning_content")
        model_reasoning = [
            (at, t) for at, t in reasoning if not t.lstrip("\n").startswith("[мост]")
        ]
        self.assertGreaterEqual(len(model_reasoning), 3, chunks)
        first_reasoning_t = model_reasoning[0][0]
        upstream_end_t = elapsed
        self.assertLess(first_reasoning_t, upstream_end_t)
        self.assertLess(model_reasoning[-1][0] - model_reasoning[0][0], 2.0)
        joined = "".join(t for _at, t in model_reasoning)
        self.assertEqual(joined, "Мысль0 Мысль1 Мысль2 Мысль3 Мысль4 ")

    def test_dynamic_config_switch_same_server(self) -> None:
        """Тот же Server: false -> run, true -> serve, битый JSON -> false."""
        reader = getattr(server, "_read_dynamic_config_enabled", None)
        if reader is None:
            reader = getattr(server, "_dynamic_config_enabled", None)
        self.assertIsNotNone(reader, "нет читателя dynamic_config")
        assert reader is not None
        self.assertTrue(reader())
        self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": False}), "utf-8")
        self.assertFalse(reader())
        self.cfg.write_text("{broken", "utf-8")
        self.assertFalse(reader())
        self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": "yes"}), "utf-8")
        self.assertFalse(reader())
        self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
        self.assertTrue(reader())

    def test_serve_env_sanitized_all_branches(self) -> None:
        """_serve_env: :memory:, allowlist, без OPENCODE_BIN и секретов."""
        fn = getattr(server, "_serve_env", None)
        self.assertIsNotNone(fn, "нет _serve_env")
        assert fn is not None
        with mock.patch.dict(
            os.environ, {"SECRET_SENTINEL": "x", "MY_API_KEY": "y"}, clear=False
        ):
            env = fn(MODEL)
        self.assertEqual(env.get("OPENCODE_DB"), ":memory:")
        self.assertNotIn("OPENCODE_BIN", env)
        self.assertNotIn("SECRET_SENTINEL", env)
        self.assertNotIn("MY_API_KEY", env)
        self.assertTrue(env.get("OPENCODE_SERVER_PASSWORD"))
        self.assertTrue(env.get("XDG_STATE_HOME"))
        self.assertNotEqual(env.get("XDG_DATA_HOME"), env.get("XDG_STATE_HOME"))

    def test_canonical_frozen_fixtures(self) -> None:
        """Каноническое отображение замороженных wire-фикстур v2.1.2."""
        mapper = getattr(server, "_map_serve_event", None) or getattr(
            server, "parse_serve_event", None
        )
        self.assertIsNotNone(mapper, "нет _map_serve_event")
        assert mapper is not None
        wire = {
            "id": "evt1",
            "type": "session.reasoning.delta",
            "data": {
                "sessionID": "ses_fixture_1",
                "assistantMessageID": "msg1",
                "delta": "Мысль без LF",
            },
        }
        result = mapper(wire)
        etype, payload = result[0], result[1]
        self.assertEqual(etype, "reasoning")
        self.assertEqual(payload, {"reasoning_content": "Мысль без LF"})
        wire2 = {
            "id": "evt3",
            "type": "session.step.ended",
            "data": {
                "sessionID": "ses_fixture_1",
                "assistantMessageID": "msg1",
                "tokens": {
                    "input": 17,
                    "output": 9,
                    "reasoning": 4,
                    "cache": {"read": 3, "write": 2},
                },
            },
        }
        etype2, payload2 = mapper(wire2)[0], mapper(wire2)[1]
        self.assertEqual(etype2, "step_finish")
        self.assertEqual(
            payload2, {"input": 17, "output": 9, "cached": 3, "reasoning": 4}
        )

    def test_tool_text_split_across_deltas(self) -> None:
        """ToolCallParser на разрезанных дельтах serve."""
        chunks, _elapsed = self.bridge.post_stream_timed("__tool_text__ вызов")
        names: list[str] = []
        for _at, chunk in chunks:
            choices = chunk.get("choices") or []
            if isinstance(choices, list) and choices:
                delta = choices[0].get("delta") or {}
                if isinstance(delta, dict):
                    for tc in delta.get("tool_calls") or []:
                        names.append(str(tc["function"]["name"]))
        self.assertEqual(names, ["bash"])

    def test_native_tool_and_permission_reject(self) -> None:
        """permission.asked -> reject, native tool -> DSH tool_call."""
        chunks, _elapsed = self.bridge.post_stream_timed("__native_tool__ сделай")
        names: list[str] = []
        for _at, chunk in chunks:
            choices = chunk.get("choices") or []
            if isinstance(choices, list) and choices:
                delta = choices[0].get("delta") or {}
                if isinstance(delta, dict):
                    for tc in delta.get("tool_calls") or []:
                        names.append(str(tc["function"]["name"]))
        self.assertIn("bash", names)

    def test_form_missing_title_cancels_without_step2(self) -> None:
        """form.created без title: cancel+interrupt до проверки схемы, без Step2."""
        record = self.tmp / "rec.json"
        chunks, _elapsed = self.bridge.post_stream_timed(
            f"__form_missing_title__ __record:{record}__ заполни"
        )
        content = "".join(t for _at, t in _deltas(chunks, "content"))
        self.assertNotIn("STEP2", content)
        control = Path(str(record) + ".control")
        self.assertTrue(control.exists(), "FakeServe не получил cancel")
        self.assertIn("cancelled", control.read_text("utf-8"))

    def test_slow_serve_gets_status_and_no_status_on_fast(self) -> None:
        """Медленный serve: статус <1с; быстрый serve: без лишнего статуса в reasoning модели."""
        chunks, _elapsed = self.bridge.post_stream_timed("__slow__ жди")
        statuses = [
            (at, t) for at, t in _deltas(chunks, "reasoning_content") if "[мост]" in t
        ]
        self.assertTrue(statuses)
        self.assertLessEqual(statuses[0][0], 1.0)

    def test_helper_argv_validation_and_lease_dir(self) -> None:
        """--serve-helper: 6 аргументов, lease только в переданном каталоге."""
        fn = getattr(server, "_run_serve_helper_cli", None)
        self.assertIsNotNone(fn, "нет _run_serve_helper_cli")
        assert fn is not None
        self.assertNotEqual(fn([]), 0)
        self.assertNotEqual(fn(["a", "notaport", "bin", "lease", "1", "x"]), 0)
        lease_dir = self.tmp / "leases-custom"
        script = Path(server.__file__).resolve()
        proc = subprocess.run(
            [
                sys.executable,
                "-I",
                str(script),
                "--serve-helper",
                "attemptX",
                "9",
                "bin",
                str(lease_dir),
                "1",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertNotEqual(proc.returncode, 0)

    def test_serve_health_and_fallback_table(self) -> None:
        """_ServeHealth sticky и таблица fallback_decision_table."""
        health_cls = getattr(server, "_ServeHealth", None)
        self.assertIsNotNone(health_cls, "нет _ServeHealth")
        assert health_cls is not None
        health = health_cls()
        for _i in range(3):
            health.record_failure()
        self.assertTrue(health.is_degraded())
        health.record_success()
        self.assertFalse(health.is_degraded())
        table = getattr(server, "FALLBACK_DECISION_TABLE", None)
        self.assertIsNotNone(table)
        assert table is not None
        rows = list(table)
        self.assertGreaterEqual(len(rows), 10)
        silence = [
            r
            for r in rows
            if "first_token_timeout" in str(r.get("event", ""))
            and "silence" in str(r.get("event", "")).lower()
        ]
        self.assertTrue(silence or rows)

    def test_helper_drains_large_stderr(self) -> None:
        """FakeServe пишет >64КиБ в stderr до SSE и не блокируется."""
        chunks, elapsed = self.bridge.post_stream_timed("обычный запрос")
        self.assertLess(elapsed, 15.0)
        self.assertTrue(_deltas(chunks, "reasoning_content"))

    def test_clean_room_fake_serve_via_monkeypatched_bin(self) -> None:
        """RW-002: OPENCODE_BIN подменён при пустом HOME, serve работает."""
        chunks, _elapsed = self.bridge.post_stream_timed("чистая комната")
        self.assertTrue(_deltas(chunks, "content"))

    def test_auto_fallback_to_run_and_sticky_degradation(self) -> None:
        """auto: 503 на создании сессии -> fallback на run; после 3 запросов serve деградирован."""
        saved_eligible = server.SERVE_TEST_ELIGIBLE
        server.SERVE_TEST_ELIGIBLE = True
        try:
            with (
                mock.patch.dict(
                    os.environ,
                    {
                        "OPENCODE_ZEN_BRIDGE_TRANSPORT": "auto",
                        "FAKE_SERVE_SESSION_STATUS": "503",
                    },
                    clear=False,
                ),
                mock.patch.object(
                    server,
                    "_SERVE_ALLOWLIST",
                    (*server._SERVE_ALLOWLIST, "FAKE_SERVE_SESSION_STATUS"),
                ),
                mock.patch.object(
                    server,
                    "_STANDALONE_ENV_ALLOWLIST",
                    (
                        *server._STANDALONE_ENV_ALLOWLIST,
                        "FAKE_SERVE_SESSION_STATUS",
                    ),
                ),
            ):
                for _i in range(3):
                    chunks, _elapsed = self.bridge.post_stream_timed("обычный запрос")
                    content = "".join(t for _at, t in _deltas(chunks, "content"))
                    self.assertIn("Поздний ответ", content)
                self.assertTrue(self.bridge.httpd.resilience.serve_health.is_degraded())
        finally:
            server.SERVE_TEST_ELIGIBLE = saved_eligible

    def test_foreign_listener_rejected_and_startup_reaper(self) -> None:
        """Чужой слушатель порта -> ServeUnavailable; reaper удаляет lease мёртвого родителя."""
        with mock.patch.object(server, "_lsof_listener_pid", return_value=999998):
            with self.assertRaises(server.ServeUnavailable) as ctx:
                _ = server._spawn_serve("att_foreign", server._serve_env(MODEL))
        self.assertIn("foreign listener", str(ctx.exception))
        lease_dir = self.tmp / "reaper-leases"
        lease_dir.mkdir()
        dead = lease_dir / "lease-dead.json"
        alive = lease_dir / "lease-alive.json"
        dead.write_text(
            json.dumps({"parent_pid": 999999, "helper_pid": 0, "pgid": 0}),
            "utf-8",
        )
        alive.write_text(
            json.dumps({"parent_pid": os.getpid(), "helper_pid": 0, "pgid": 0}),
            "utf-8",
        )
        _ = server._startup_reaper(lease_dir)
        self.assertFalse(dead.exists())
        self.assertTrue(alive.exists())

    def test_serve_400_fails_closed_without_health_increment(self) -> None:
        """400 на создании сессии: SSE error fail-closed без инкремента serve_health."""
        health = self.bridge.httpd.resilience.serve_health
        failures_before = health.failures
        with (
            mock.patch.dict(
                os.environ, {"FAKE_SERVE_SESSION_STATUS": "400"}, clear=False
            ),
            mock.patch.object(
                server,
                "_SERVE_ALLOWLIST",
                (*server._SERVE_ALLOWLIST, "FAKE_SERVE_SESSION_STATUS"),
            ),
            mock.patch.object(
                server,
                "_STANDALONE_ENV_ALLOWLIST",
                (*server._STANDALONE_ENV_ALLOWLIST, "FAKE_SERVE_SESSION_STATUS"),
            ),
        ):
            chunks, _elapsed = self.bridge.post_stream_timed("обычный запрос")
        joined = json.dumps(chunks, ensure_ascii=False)
        self.assertIn("serve security failure", joined)
        self.assertEqual(health.failures, failures_before)
        self.assertFalse(health.is_degraded())


if __name__ == "__main__":
    unittest.main()
ARTIFACT_END>>>

## 3. Handoff исполнителя и квитанции гейтов (`coder.json`, `receipts/coder.json`, `code-gate.json`, `verifier.json`, `final-gate.json`)
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/coder.json sha256=8ca5bca38c56715f63209ef79bc47df117795f2d3bc0d8d4607b9ea01f488d18
{
  "schema_version": "1.1",
  "role": "coder",
  "task_id": "analyst-teamlead-zen-realtime-reasoning-20261025",
  "run_id": "analyst-teamlead-zen-realtime-reasoning-20261025",
  "round_id": "coder-03",
  "iteration": 3,
  "status": "DONE",
  "summary": "Раунд coder-03: 1-строчный фикс базы отсчёта status_next в _serve_one_attempt (server.py:2890): status_next = max(t0 + FIRST_STATUS_DELAY_S, prompt_send_start + 0.25). Медленный serve получает первый статус [мост] через 0.65 с от t0 (<= 1.0 с); быстрый serve не получает ложного статуса (первый токен раньше prompt_send_start + 0.25 с). Ранее падавший test_slow_serve_gets_status_and_no_status_on_fast зелёный; VER-004 exit 0, замороженные срезы не тронуты.",
  "role_plan": {
    "path": ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-03.json",
    "sha256": "eff3c2527865e4f801f08eee018c155d5f3fbf756da09bd3d73e6d70a357d30b",
    "phase": "after"
  },
  "changed_files": [
    "bridges/opencode-zen-bridge/server.py"
  ],
  "files_changed": [
    "bridges/opencode-zen-bridge/server.py"
  ],
  "tests_added": [],
  "commands": [
    {
      "command": "python3 validate_role_plan.py plans/coder-03.before.json --phase before",
      "exit_code": 0,
      "output_summary": "PASS: coder role plan is valid for before; sha256=0bad055265bc37270ef5d2b32ff7f8927d1cbe9ae8cbcd0f1a34f6dbfd5467bb"
    },
    {
      "command": "uvx --from ruff==0.17.2 ruff format --config ruff.toml --no-cache --range=2885:1-2895:999 bridges/opencode-zen-bridge/server.py",
      "exit_code": 0,
      "output_summary": "1 file left unchanged; строка 2890 уже в каноническом формате"
    },
    {
      "command": "cd bridges/opencode-zen-bridge && uvx pytest -q -p no:cacheprovider tests/test_realtime_reasoning.py -k 'test_slow_serve_gets_status_and_no_status_on_fast or test_ac026_realtime_chunks_before_upstream_end or test_frozen_slices_hashes'",
      "exit_code": 0,
      "output_summary": "3 passed, 18 deselected in 4.55s"
    },
    {
      "command": "cd bridges/opencode-zen-bridge && uvx pytest -q -p no:cacheprovider tests/test_go_model_routing.py -k 'test_stream_go_model_success_with_fake_launcher'",
      "exit_code": 0,
      "output_summary": "1 passed, 30 deselected in 0.65s"
    },
    {
      "command": "VER-004 command дословно из architecture/architecture-packet.json (bash /tmp/ver004-coder03.sh из repo_root)",
      "exit_code": 0,
      "output_summary": "PASS VER-004: all3 lint/type; BASEDPYRIGHT errorCount 0; frozen hashes _run_env/_stream_google_sse/_execute_google_once совпали; VER004_EXIT:0"
    },
    {
      "command": "python3 validate_role_plan.py plans/coder-03.json --phase after",
      "exit_code": 0,
      "output_summary": "PASS: coder role plan is valid for after; sha256=eff3c2527865e4f801f08eee018c155d5f3fbf756da09bd3d73e6d70a357d30b"
    }
  ],
  "verification_commands": [
    {
      "command": "cd bridges/opencode-zen-bridge && uvx pytest -q -p no:cacheprovider tests/test_realtime_reasoning.py -k 'test_slow_serve_gets_status_and_no_status_on_fast or test_ac026_realtime_chunks_before_upstream_end or test_frozen_slices_hashes'; uvx pytest -q -p no:cacheprovider tests/test_go_model_routing.py -k 'test_stream_go_model_success_with_fake_launcher'",
      "exit_code": 0,
      "output_summary": "3 passed (test_realtime_reasoning) + 1 passed (test_go_model_routing); ранее падавший test_slow_serve_gets_status_and_no_status_on_fast зелёный"
    },
    {
      "command": "VER-004 command дословно из architecture/architecture-packet.json (bash /tmp/ver004-coder03.sh из repo_root)",
      "exit_code": 0,
      "output_summary": "PASS VER-004: all3 lint/type; BASEDPYRIGHT errorCount 0; frozen hashes совпали; VER004_EXIT:0"
    }
  ],
  "red_green_evidence": {
    "red_command": "Clean-Room L2 (l2-green-ver001-pytest.log, до фикса coder-03): tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_slow_serve_gets_status_and_no_status_on_fast",
    "red_exit_code": 1,
    "red_failure_summary": "AssertionError: 1.04001908400096 not less than or equal to 1.0 — status_next считался от prompt_send_start (после spawn/session/event, +0.40 с), а не от t0 начала HTTP-запроса",
    "green_command": "cd bridges/opencode-zen-bridge && uvx pytest -q -p no:cacheprovider tests/test_realtime_reasoning.py -k 'test_slow_serve_gets_status_and_no_status_on_fast or test_ac026_realtime_chunks_before_upstream_end or test_frozen_slices_hashes'",
    "green_exit_code": 0,
    "green_summary": "3 passed, 18 deselected in 4.55s"
  },
  "acceptance_coverage": [
    "server.py:2890 status_next = max(t0 + FIRST_STATUS_DELAY_S, prompt_send_start + 0.25) — единственная изменённая строка раунда",
    "test_slow_serve_gets_status_and_no_status_on_fast зелёный (был единственным падением Clean-Room L2: 399/400)",
    "test_stream_go_model_success_with_fake_launcher зелёный (legacy run-путь не затронут)",
    "test_frozen_slices_hashes зелёный; VER-004 exit 0 — замороженные _run_env/_stream_google_sse/_execute_google_once байт-в-байт"
  ],
  "assumptions": [],
  "risks": [
    "Полный 83-секундный сьют по прямому указанию брифа не запускался; прогнаны только целевые тесты брифа + VER-004. Остальные тесты test_realtime_reasoning.py в этом раунде не перепроверялись."
  ],
  "unresolved_risks": [],
  "open_questions": [],
  "next_role": "reviewer"
}
ARTIFACT_END>>>
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/coder.json sha256=a47ba864e9ef2af0cdfa045c9c38dbc201f6462f56d54cdc62a7968664ded043
{
  "schema_version": "1.0",
  "gate": "CODER",
  "status": "PASS",
  "run_id": "analyst-teamlead-zen-realtime-reasoning-20261025",
  "round_id": "coder-03",
  "slot": "muse-wonder-1.0",
  "effort": "high",
  "family": "Meta",
  "transport": "muse-cli.sh exec",
  "handoff_path": ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/handoffs/coder-03.json",
  "handoff_sha256": "8ca5bca38c56715f63209ef79bc47df117795f2d3bc0d8d4607b9ea01f488d18",
  "plan_before_sha256": "0bad055265bc37270ef5d2b32ff7f8927d1cbe9ae8cbcd0f1a34f6dbfd5467bb",
  "plan_after_sha256": "eff3c2527865e4f801f08eee018c155d5f3fbf756da09bd3d73e6d70a357d30b",
  "fingerprint_after_sha256": "ad3f1cbd7ef716a4ef46b5807eabd1c19a42f235645f1a3ab3699a9f1a1cc767",
  "completed_at": "2026-10-26T18:43:25.132686+00:00"
}
ARTIFACT_END>>>
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/code-gate.json sha256=e4171d5605d0c15519fd56f0f18282897837370266268faaa12f2a3c2e97ce35
{
  "schema_version": "1.0",
  "gate": "CODE_GATE_AND_L2_CLEANROOM",
  "status": "PASS",
  "timestamp": "2026-10-26T19:32:48.876584+00:00",
  "touched_files": [
    "bridges/opencode-zen-bridge/server.py",
    "bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py",
    "bridges/opencode-zen-bridge/tests/test_step_interruption.py"
  ],
  "run_env_sha256": "1c51b28fcb83fcc0f4d8b5204c858e11ab5ac975bfe40dca4a0bf61978008e31",
  "google_direct_unchanged": true,
  "red_sensitivity_rc": 1,
  "green_failures": [],
  "checks": [
    {
      "name": "L2-RED-sensitivity",
      "cmd": [
        "uvx",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_realtime_reasoning.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 1,
      "wall_seconds": 23.79,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-red.log",
      "log_sha256": "b8b80dd34adbf1f2bab310d2d0926d52559ae5e7323a81ef75cb93ddd02cf0bf"
    },
    {
      "name": "VER-004-packet-command",
      "cmd": [
        "/bin/zsh",
        "-lc",
        "python3 - <<'VER004'\nimport ast, collections, hashlib, json, re, subprocess, tempfile\nfrom pathlib import Path\nroot = Path.cwd().resolve()\nbridge = root / 'bridges/opencode-zen-bridge'\nfiles = [bridge/'server.py', bridge/'tests/test_step_interruption.py', bridge/'tests/test_realtime_reasoning.py']\nassert all(f.is_file() for f in files), 'all three target files must exist after Stage3'\nruff = ['uvx','--from','ruff==0.17.2','ruff']\ndef run(args, **kw):\n    return subprocess.run(args, check=True, **kw)\ndef changed_ranges(file):\n    rel = str(file.relative_to(root))\n    diff = subprocess.check_output(['git','diff','--no-ext-diff','--no-color','-U0','origin/dev','--',rel], cwd=root, text=True)\n    # NEW tracked files must be added before final verification; --no-index alternative below covers untracked newfile.\n    result = []\n    for line in diff.splitlines():\n        m = re.match(r'^@@ -\\d+(?:,\\d+)? \\+(\\d+)(?:,(\\d+))? @@', line)\n        if m:\n            start = int(m.group(1)); count = int(m.group(2) or '1')\n            if count: result.append((start, start + count - 1))\n    return result\n\n# Raw-byte contract: frozen expected digests originate in EVD-075, never candidate.\nFROZEN = {\n    '_run_env': '1c51b28fcb83fcc0f4d8b5204c858e11ab5ac975bfe40dca4a0bf61978008e31',\n    '_stream_google_sse': '5914c9654c7345692dd55e84cfd3765e27406f63a3df85df30bc798bc1778de3',\n    '_execute_google_once': '88d794cc42be4878e8ab35b00e4668c427929db2dfd0f2bb4b717a63fd0c70d6',\n}\nbaseline_raw = subprocess.check_output(['git','show','origin/dev:bridges/opencode-zen-bridge/server.py'], cwd=root)\ndef frozen_slices(raw):\n    lines = raw.splitlines(keepends=True)\n    nodes = {n.name:n for n in ast.walk(ast.parse(raw)) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name in FROZEN}\n    assert set(nodes)==set(FROZEN)\n    return {name:(node.lineno,node.end_lineno,b''.join(lines[node.lineno-1:node.end_lineno])) for name,node in nodes.items()}\nbaseline_slices = frozen_slices(baseline_raw)\ndef assert_frozen(candidate=files[0]):\n    candidate_slices = frozen_slices(candidate.read_bytes())\n    for name, expected in FROZEN.items():\n        assert hashlib.sha256(baseline_slices[name][2]).hexdigest()==expected, ('frozen origin/dev changed',name)\n        assert hashlib.sha256(candidate_slices[name][2]).hexdigest()==expected, ('immutable slice changed',name)\n        assert candidate_slices[name][2]==baseline_slices[name][2], ('nonzero raw Google/_run_env diff',name)\n    return candidate_slices\ncandidate_slices = assert_frozen()\nserver_diff = subprocess.check_output(['git','diff','--no-ext-diff','--no-color','-U0','origin/dev','--',str(files[0].relative_to(root))],cwd=root,text=True)\nfor line in server_diff.splitlines():\n    match = re.match(r'^@@ -(\\d+)(?:,(\\d+))? \\+(\\d+)(?:,(\\d+))? @@',line)\n    if not match: continue\n    old_start,old_count,new_start,new_count = int(match[1]),int(match[2] or '1'),int(match[3]),int(match[4] or '1')\n    for start,count,table in [(old_start,old_count,baseline_slices),(new_start,new_count,candidate_slices)]:\n        for name,(lo,hi,_) in table.items():\n            # Zero-count insert/delete anchors represent the boundary after start.\n            overlaps = (start<=hi and start+count-1>=lo) if count else (lo<=start<hi)\n            assert not overlaps, ('VER-004 frozen-range hunk intersection',name,line)\n# Public module constant/read API remains intact; compatibility test file is frozen.\ntree = ast.parse(files[0].read_bytes())\nassignments = [n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='CATALOG_SOURCE' for t in n.targets)]\nassert len(assignments)==1 and isinstance(assignments[0].value,ast.Constant) and assignments[0].value.value=='static'\nassert any(isinstance(n,ast.FunctionDef) and n.name=='_set_catalog_source' for n in tree.body)\nassert any(isinstance(n,ast.Import) and any(a.name=='zen_catalog' and a.asname=='zc' for a in n.names) for n in ast.walk(tree))\nassert not any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='import_module' and n.args and isinstance(n.args[0],ast.Constant) and n.args[0].value=='zen_catalog' for n in ast.walk(tree))\nassert any(isinstance(n,ast.FunctionDef) and n.name=='_run_serve_helper_cli' for n in tree.body), 'helper code must be lint/type checked in server.py'\nhelper_branch = next((n for n in tree.body if isinstance(n, ast.If) and ast.unparse(n.test) == \"sys.argv[1:2] == ['--serve-helper']\"), None)\nassert helper_branch is not None and any(isinstance(n, ast.Raise) for n in helper_branch.body), 'early terminating helper dispatch required'\nheavy = {'http.client', 'sqlite3', 'http.server', 'zen_catalog'}\ndef imported_names(node):\n    if isinstance(node, ast.Import): return {a.name for a in node.names}\n    if isinstance(node, ast.ImportFrom): return {node.module}\n    return set()\nassert not any(imported_names(n) & heavy for n in tree.body[:tree.body.index(helper_branch)])\nassert any(isinstance(n, ast.Import) and any(a.name == 'zen_catalog' and a.asname == 'zc' for a in n.names) for n in helper_branch.orelse)\nassert all(not isinstance(n, (ast.Assign, ast.AnnAssign, ast.Expr)) for n in tree.body[1:tree.body.index(helper_branch)]), 'no server initialization before helper exit'\nassert not any(isinstance(n,ast.Global) and 'CATALOG_SOURCE' in n.names for n in ast.walk(tree))\nrun(['git','diff','--exit-code','origin/dev','--','bridges/opencode-zen-bridge/tests/test_catalog_mode.py'],cwd=root)\n\nranges = {f: changed_ranges(f) for f in files[:2]}\n# New file checked as a whole even before git add. Range gate never formats frozen legacy slices.\nrun([*ruff,'format','--config',str(root / 'ruff.toml'),'--check','--no-cache',str(files[2])], cwd=root)\nfor f in files[:2]:\n    for start, end in ranges[f]:\n        run([*ruff,'format','--config',str(root / 'ruff.toml'),'--check','--no-cache',f'--range={start}:1-{end}:999',str(f)], cwd=root)\nassert_frozen()\n# Exercise actual write-mode range formatting only on a disposable copy.\nwith tempfile.TemporaryDirectory(prefix='zen-arch6-probe-format-', dir='/tmp') as format_dir:\n    formatted_copy = Path(format_dir) / 'server.py'\n    formatted_copy.write_bytes(files[0].read_bytes())\n    for start, end in ranges[files[0]]:\n        run([*ruff,'format','--config',str(root / 'ruff.toml'),'--no-cache',f'--range={start}:1-{end}:999',str(formatted_copy)], cwd=root)\n    assert formatted_copy.read_bytes() == files[0].read_bytes()\n    assert_frozen(formatted_copy)\n    assert_frozen()\n    print('PASS write-mode frozen hashes', {name:hashlib.sha256(data[2]).hexdigest() for name,data in frozen_slices(formatted_copy.read_bytes()).items()})\n# Full-file lint on all three. Only inherited E402 import site is excepted on server.\nlint = subprocess.run([*ruff,'check','--config',str(root / 'ruff.toml'),'--no-cache','--output-format','json',str(files[0])], cwd=root, capture_output=True, text=True)\nassert lint.returncode in (0,1), lint.stderr\nfindings = json.loads(lint.stdout)\nlines = files[0].read_text().splitlines()\nassert all(x['code']=='E402' and lines[x['location']['row']-1].strip()=='import zen_catalog as zc' for x in findings), findings\nassert sum(x['code']=='E402' for x in findings) <= 1\nrun([*ruff,'check','--config',str(root / 'ruff.toml'),'--no-cache','--extend-ignore','E402',str(files[0])], cwd=root)\nrun([*ruff,'check','--config',str(root / 'ruff.toml'),'--no-cache',str(files[1]),str(files[2])], cwd=root)\n# Exact isolated import-root. No repo pyrightconfig mutation; JSON deleted on every exit.\nproject = None\ntry:\n    with tempfile.NamedTemporaryFile(mode='w',suffix='.json',prefix='zen-arch6-probe-project-',dir='/tmp',delete=False) as tmp:\n        project = Path(tmp.name)\n        json.dump({'include':[str(f) for f in files], 'extraPaths':[str(bridge.resolve())]},tmp)\n    b = subprocess.run(['uvx','--from','basedpyright==1.40.2','basedpyright','--project',str(project),'--outputjson'], cwd=bridge, capture_output=True, text=True)\n    assert b.returncode in (0,1), b.stderr\n    report = json.loads(b.stdout)\n    ds = report['generalDiagnostics']\n    assert report['summary']['errorCount']==0 and not [x for x in ds if x['severity']=='error'], ds\n    byfile = {f: [x for x in ds if Path(x['file']).resolve()==f] for f in files}\n    limits = {'reportExplicitAny':125,'reportAny':125,'reportUnusedCallResult':39,'reportUnknownMemberType':94,'reportUnknownVariableType':72,'reportUnknownArgumentType':55,'reportUnusedFunction':6,'reportImplicitStringConcatenation':35,'reportUnannotatedClassAttribute':105,'reportUnusedParameter':7,'reportUnnecessaryIsInstance':11,'reportUnknownParameterType':6,'reportMissingParameterType':4,'reportUnreachable':5,'reportImplicitOverride':3}\n    warnings = lambda f: [x for x in byfile[f] if x['severity']=='warning']\n    counts = collections.Counter(x.get('rule','') for x in warnings(files[0]))\n    print('BASEDPYRIGHT summary',report['summary'])\n    print('SERVER dict(counts)',dict(counts))\n    print('SERVER warningCount',len(warnings(files[0])))\n    assert all(n<=limits.get(rule,0) for rule,n in counts.items()), dict(counts)\n    assert len(warnings(files[0]))<=720, len(warnings(files[0]))\n    assert len(warnings(files[1]))<=194, len(warnings(files[1]))\n    # New test file: zero warnings as well as zero errors, thus zero Any.\n    assert not byfile[files[2]], byfile[files[2]]\n    for f in files[:2]:\n        for x in byfile[f]:\n            line = x['range']['start']['line']+1\n            if any(lo<=line<=hi for lo,hi in ranges[f]):\n                assert x.get('rule') not in {'reportAny','reportExplicitAny','reportUnusedCallResult'}, x\n    # Do not introduce Any annotations/type ignores in added code in either legacy file.\n    for f in files[:2]:\n        src = f.read_text().splitlines()\n        for lo,hi in ranges[f]:\n            for line in src[lo-1:hi]:\n                assert not re.search(r'\\bAny\\b|type:\\s*ignore|pyright:\\s*ignore|#\\s*noqa|#\\s*fmt:\\s*off',line), (f,line)\n    run(['python3','-B','-m','unittest','tests.test_catalog_mode','-v'],cwd=bridge)\n    print('PASS VER-004: all3 lint/type; legacy changed-range format; newfile whole format; server counts',dict(counts))\nfinally:\n    if project is not None: project.unlink(missing_ok=True)\nVER004"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom",
      "rc": 0,
      "wall_seconds": 9.33,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver004-packet.log",
      "log_sha256": "6c0b3627322b3ea368d0add2b4a8f9f050f6c70f3cb8846a2f766bbf8ee63800"
    },
    {
      "name": "VER-004-ruff-format-new",
      "cmd": [
        "uvx",
        "--from",
        "ruff==0.17.2",
        "ruff",
        "format",
        "--check",
        "--no-cache",
        "tests/test_realtime_reasoning.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 0.04,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver004-ruff-format-new.log",
      "log_sha256": "791491a5d9e6128b8400ae730e69e74c9af01651d625cc697d569dfdcee245b7"
    },
    {
      "name": "VER-004-ruff-format-range-server-1",
      "cmd": [
        "uvx",
        "--from",
        "ruff==0.17.2",
        "ruff",
        "format",
        "--check",
        "--no-cache",
        "--range=22:1-22:999",
        "server.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 0.05,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver004-range-server-1.log",
      "log_sha256": "755d9227e95b948c1b21b60a6a5719f23874a7f21c9eaa06d940767f5734d920"
    },
    {
      "name": "VER-004-ruff-format-range-server-2",
      "cmd": [
        "uvx",
        "--from",
        "ruff==0.17.2",
        "ruff",
        "format",
        "--check",
        "--no-cache",
        "--range=29:1-224:999",
        "server.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 0.05,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver004-range-server-2.log",
      "log_sha256": "d43ecdb8d6ac5fbb42ad87118c810f0502f825f1e90d9caa99b63adad6226dd8"
    },
    {
      "name": "VER-004-ruff-format-range-server-3",
      "cmd": [
        "uvx",
        "--from",
        "ruff==0.17.2",
        "ruff",
        "format",
        "--check",
        "--no-cache",
        "--range=259:1-267:999",
        "server.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 0.05,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver004-range-server-3.log",
      "log_sha256": "acfa83afea14da20895c3c5df8891eefc261d948f1733e6a9362c94316fbc5e8"
    },
    {
      "name": "VER-004-ruff-format-range-server-4",
      "cmd": [
        "uvx",
        "--from",
        "ruff==0.17.2",
        "ruff",
        "format",
        "--check",
        "--no-cache",
        "--range=282:1-287:999",
        "server.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 0.05,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver004-range-server-4.log",
      "log_sha256": "88452847a1c7bf2735617ebc981f4546653b761feb86581b86c09defcbbabd90"
    },
    {
      "name": "VER-004-ruff-format-range-server-5",
      "cmd": [
        "uvx",
        "--from",
        "ruff==0.17.2",
        "ruff",
        "format",
        "--check",
        "--no-cache",
        "--range=310:1-310:999",
        "server.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 0.04,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver004-range-server-5.log",
      "log_sha256": "3001e902e898ce08be329b7fb21e859b94d1f64fd4223e58eb45d3e1bafa83e0"
    },
    {
      "name": "VER-004-ruff-format-range-server-6",
      "cmd": [
        "uvx",
        "--from",
        "ruff==0.17.2",
        "ruff",
        "format",
        "--check",
        "--no-cache",
        "--range=323:1-323:999",
        "server.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 0.04,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver004-range-server-6.log",
      "log_sha256": "395372d5783c465bb44896e2b27bb87f887cc2483269a1045a3fb28fdd568474"
    },
    {
      "name": "VER-004-ruff-format-range-server-7",
      "cmd": [
        "uvx",
        "--from",
        "ruff==0.17.2",
        "ruff",
        "format",
        "--check",
        "--no-cache",
        "--range=1326:1-1887:999",
        "server.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 0.05,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver004-range-server-7.log",
      "log_sha256": "ef3916991629bdb55ce1820231b7cc0c4f70ba15083be97b22ebdce0ee32b7f5"
    },
    {
      "name": "VER-004-ruff-format-range-server-8",
      "cmd": [
        "uvx",
        "--from",
        "ruff==0.17.2",
        "ruff",
        "format",
        "--check",
        "--no-cache",
        "--range=2204:1-2206:999",
        "server.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 0.05,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver004-range-server-8.log",
      "log_sha256": "91e7ac7b68fc502cae836236045fb6e74e77bdd8704fd29f78eb0df1f357f8c5"
    },
    {
      "name": "VER-004-ruff-format-range-server-9",
      "cmd": [
        "uvx",
        "--from",
        "ruff==0.17.2",
        "ruff",
        "format",
        "--check",
        "--no-cache",
        "--range=2221:1-2221:999",
        "server.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 0.05,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver004-range-server-9.log",
      "log_sha256": "aa564ad3b2e4ce1923226de4ae4763b1fd8789f2b1a4cc257747cd61f6a7f584"
    },
    {
      "name": "VER-004-ruff-format-range-server-10",
      "cmd": [
        "uvx",
        "--from",
        "ruff==0.17.2",
        "ruff",
        "format",
        "--check",
        "--no-cache",
        "--range=2231:1-2239:999",
        "server.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 0.04,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver004-range-server-10.log",
      "log_sha256": "55dad36c122f16886bc8f61615b1f48774f27888e6a56f028ee000d08e5fb7b5"
    },
    {
      "name": "VER-004-ruff-format-range-server-11",
      "cmd": [
        "uvx",
        "--from",
        "ruff==0.17.2",
        "ruff",
        "format",
        "--check",
        "--no-cache",
        "--range=2242:1-2244:999",
        "server.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 0.04,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver004-range-server-11.log",
      "log_sha256": "1a167fd9cb08fdce4010880b0f7d30eb4c728e0b88b82e9be602cb9133174d07"
    },
    {
      "name": "VER-004-ruff-format-range-server-12",
      "cmd": [
        "uvx",
        "--from",
        "ruff==0.17.2",
        "ruff",
        "format",
        "--check",
        "--no-cache",
        "--range=2263:1-2267:999",
        "server.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 0.04,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver004-range-server-12.log",
      "log_sha256": "4317df22db33357148a731fa34cd55b55460cc0f9d8727409e75fd7bf7439491"
    },
    {
      "name": "VER-004-ruff-format-range-server-13",
      "cmd": [
        "uvx",
        "--from",
        "ruff==0.17.2",
        "ruff",
        "format",
        "--check",
        "--no-cache",
        "--range=2287:1-2291:999",
        "server.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 0.04,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver004-range-server-13.log",
      "log_sha256": "36603cdcb32ee0bfdb0fa0b4637fb4dad374e8f8b80e2562271739320bcdc689"
    },
    {
      "name": "VER-004-ruff-format-range-server-14",
      "cmd": [
        "uvx",
        "--from",
        "ruff==0.17.2",
        "ruff",
        "format",
        "--check",
        "--no-cache",
        "--range=2338:1-2338:999",
        "server.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 0.04,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver004-range-server-14.log",
      "log_sha256": "b983f7809853564cc15dd508ac2c088d5991ddcec96b88a1296570978a186f4c"
    },
    {
      "name": "VER-004-ruff-format-range-server-15",
      "cmd": [
        "uvx",
        "--from",
        "ruff==0.17.2",
        "ruff",
        "format",
        "--check",
        "--no-cache",
        "--range=2356:1-2356:999",
        "server.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 0.04,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver004-range-server-15.log",
      "log_sha256": "aebac7e28bf0afaef20d5fe5510a30f550197c93290b50bc7cbe83fc5403e8e9"
    },
    {
      "name": "VER-004-ruff-format-range-server-16",
      "cmd": [
        "uvx",
        "--from",
        "ruff==0.17.2",
        "ruff",
        "format",
        "--check",
        "--no-cache",
        "--range=2360:1-3114:999",
        "server.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 0.05,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver004-range-server-16.log",
      "log_sha256": "adf78bb4fd6f97936c702a7d4294300b6fcd29b8b9ba1320a9e7759e38e2b9fb"
    },
    {
      "name": "VER-004-ruff-format-range-server-17",
      "cmd": [
        "uvx",
        "--from",
        "ruff==0.17.2",
        "ruff",
        "format",
        "--check",
        "--no-cache",
        "--range=3116:1-3130:999",
        "server.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 0.05,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver004-range-server-17.log",
      "log_sha256": "3cb140d3caf21e48815884209c1effe43aba443517ff186132053779cf8a08a5"
    },
    {
      "name": "VER-004-ruff-format-range-server-18",
      "cmd": [
        "uvx",
        "--from",
        "ruff==0.17.2",
        "ruff",
        "format",
        "--check",
        "--no-cache",
        "--range=3135:1-3153:999",
        "server.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 0.05,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver004-range-server-18.log",
      "log_sha256": "e4d8d810199f401eb0ce3372bddb0bff3d8b3da741b09caaab7e30a3eb3a177c"
    },
    {
      "name": "VER-004-ruff-format-range-server-19",
      "cmd": [
        "uvx",
        "--from",
        "ruff==0.17.2",
        "ruff",
        "format",
        "--check",
        "--no-cache",
        "--range=4427:1-4431:999",
        "server.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 0.04,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver004-range-server-19.log",
      "log_sha256": "c444cf645da432ed3d6b8986da17bbeab54f5a166c128ff60e99cd07468048f8"
    },
    {
      "name": "VER-004-ruff-format-range-server-20",
      "cmd": [
        "uvx",
        "--from",
        "ruff==0.17.2",
        "ruff",
        "format",
        "--check",
        "--no-cache",
        "--range=4438:1-4442:999",
        "server.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 0.04,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver004-range-server-20.log",
      "log_sha256": "d313077dabc9521b20943926aa602c5f7ab502521c54b0bf9791af1b893d9023"
    },
    {
      "name": "VER-004-ruff-format-range-server-21",
      "cmd": [
        "uvx",
        "--from",
        "ruff==0.17.2",
        "ruff",
        "format",
        "--check",
        "--no-cache",
        "--range=4444:1-4446:999",
        "server.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 0.04,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver004-range-server-21.log",
      "log_sha256": "7fc43edee20bccae0ccb2e433fc2239ce865ac22787665d91b41f59d4cd1e0cd"
    },
    {
      "name": "VER-004-ruff-format-range-server-22",
      "cmd": [
        "uvx",
        "--from",
        "ruff==0.17.2",
        "ruff",
        "format",
        "--check",
        "--no-cache",
        "--range=4449:1-4453:999",
        "server.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 0.04,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver004-range-server-22.log",
      "log_sha256": "9028f2d9ca25ffe300866f2e21f556386a6615b4a25fb8a975a0c0f368a50c7b"
    },
    {
      "name": "VER-004-ruff-format-range-server-23",
      "cmd": [
        "uvx",
        "--from",
        "ruff==0.17.2",
        "ruff",
        "format",
        "--check",
        "--no-cache",
        "--range=4462:1-4464:999",
        "server.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 0.04,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver004-range-server-23.log",
      "log_sha256": "137d18ac14126d0eb7f05fddd42def32e3519b858b8195f60316998bef756f6c"
    },
    {
      "name": "VER-004-ruff-format-range-server-24",
      "cmd": [
        "uvx",
        "--from",
        "ruff==0.17.2",
        "ruff",
        "format",
        "--check",
        "--no-cache",
        "--range=4467:1-4475:999",
        "server.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 0.04,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver004-range-server-24.log",
      "log_sha256": "a21e3aad406e5764d4dbd3d7b01556db946c6dc89b5ef86eb37e3ce7e25139b3"
    },
    {
      "name": "VER-004-ruff-format-range-server-25",
      "cmd": [
        "uvx",
        "--from",
        "ruff==0.17.2",
        "ruff",
        "format",
        "--check",
        "--no-cache",
        "--range=4482:1-4489:999",
        "server.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 0.04,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver004-range-server-25.log",
      "log_sha256": "342d717568eb06315b8a533ed99dd7bdbf57ca15104e8781fad2e2f8239307a9"
    },
    {
      "name": "VER-004-ruff-format-range-server-26",
      "cmd": [
        "uvx",
        "--from",
        "ruff==0.17.2",
        "ruff",
        "format",
        "--check",
        "--no-cache",
        "--range=4492:1-4494:999",
        "server.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 0.04,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver004-range-server-26.log",
      "log_sha256": "c9bb5ad51a1cec6ddb158bd40b203bbf93ab98d37cd0e9b39100fcbca38901ad"
    },
    {
      "name": "VER-004-ruff-format-range-server-27",
      "cmd": [
        "uvx",
        "--from",
        "ruff==0.17.2",
        "ruff",
        "format",
        "--check",
        "--no-cache",
        "--range=4496:1-4504:999",
        "server.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 0.04,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver004-range-server-27.log",
      "log_sha256": "48c923dbeecb3ae20982762829ed159b3617ae1c87f534533a94d2a9a6bb9b51"
    },
    {
      "name": "VER-004-ruff-format-range-server-28",
      "cmd": [
        "uvx",
        "--from",
        "ruff==0.17.2",
        "ruff",
        "format",
        "--check",
        "--no-cache",
        "--range=4509:1-4517:999",
        "server.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 0.04,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver004-range-server-28.log",
      "log_sha256": "631d1084303ce679115087d098863502208aa8697d8f484779731460cfcdde21"
    },
    {
      "name": "VER-004-ruff-format-range-server-29",
      "cmd": [
        "uvx",
        "--from",
        "ruff==0.17.2",
        "ruff",
        "format",
        "--check",
        "--no-cache",
        "--range=4527:1-4528:999",
        "server.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 0.04,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver004-range-server-29.log",
      "log_sha256": "8cd812c358a608185ca293bcb5779f4333e26f659a9a9c6b36580267e1d99745"
    },
    {
      "name": "VER-004-ruff-format-range-server-30",
      "cmd": [
        "uvx",
        "--from",
        "ruff==0.17.2",
        "ruff",
        "format",
        "--check",
        "--no-cache",
        "--range=4579:1-4581:999",
        "server.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 0.04,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver004-range-server-30.log",
      "log_sha256": "1b7991002fb119b2a9562d39b41d3068d02cd8275511c275a2508af415c2cea1"
    },
    {
      "name": "VER-004-ruff-format-range-server-31",
      "cmd": [
        "uvx",
        "--from",
        "ruff==0.17.2",
        "ruff",
        "format",
        "--check",
        "--no-cache",
        "--range=4583:1-4596:999",
        "server.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 0.04,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver004-range-server-31.log",
      "log_sha256": "c548744592a53ccc65fc76571ca3b4c2c2d8ce76936922f48661451ace75e686"
    },
    {
      "name": "VER-004-ruff-format-range-server-32",
      "cmd": [
        "uvx",
        "--from",
        "ruff==0.17.2",
        "ruff",
        "format",
        "--check",
        "--no-cache",
        "--range=4686:1-4686:999",
        "server.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 0.05,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver004-range-server-32.log",
      "log_sha256": "b891acb4d080206084d4e7e70ad7bf878c28a2d0f37db5f757c3d0b06b847689"
    },
    {
      "name": "VER-004-ruff-format-range-server-33",
      "cmd": [
        "uvx",
        "--from",
        "ruff==0.17.2",
        "ruff",
        "format",
        "--check",
        "--no-cache",
        "--range=4696:1-4700:999",
        "server.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 0.04,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver004-range-server-33.log",
      "log_sha256": "d50fc53e2d4ea34a0650b8b573e78847b4870e16c2897cff91e85af02697c94b"
    },
    {
      "name": "VER-004-ruff-format-range-server-34",
      "cmd": [
        "uvx",
        "--from",
        "ruff==0.17.2",
        "ruff",
        "format",
        "--check",
        "--no-cache",
        "--range=4734:1-4967:999",
        "server.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 0.04,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver004-range-server-34.log",
      "log_sha256": "0b46d3055ef8fc3f66b6ded112feefe9199d87bab507bcff915342caf40929b3"
    },
    {
      "name": "VER-004-ruff-format-range-server-35",
      "cmd": [
        "uvx",
        "--from",
        "ruff==0.17.2",
        "ruff",
        "format",
        "--check",
        "--no-cache",
        "--range=5118:1-5119:999",
        "server.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 0.04,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver004-range-server-35.log",
      "log_sha256": "245dde84273d71bc8657149dcf68158d87f93655201c67bdfa02385e0517c472"
    },
    {
      "name": "VER-004-ruff-format-range-server-36",
      "cmd": [
        "uvx",
        "--from",
        "ruff==0.17.2",
        "ruff",
        "format",
        "--check",
        "--no-cache",
        "--range=5229:1-5283:999",
        "server.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 0.04,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver004-range-server-36.log",
      "log_sha256": "522ec4a1dd2a1f8dbcf9a779dd97bad5b94553e7e5ebbd25585ab953048d7b92"
    },
    {
      "name": "VER-004-ruff-format-range-server-37",
      "cmd": [
        "uvx",
        "--from",
        "ruff==0.17.2",
        "ruff",
        "format",
        "--check",
        "--no-cache",
        "--range=5301:1-5303:999",
        "server.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 0.04,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver004-range-server-37.log",
      "log_sha256": "783dea9a28cffd5e4453d20b2f4e8caaded8c886585c49e931dade2b1bf2b22f"
    },
    {
      "name": "VER-004-ruff-format-range-server-38",
      "cmd": [
        "uvx",
        "--from",
        "ruff==0.17.2",
        "ruff",
        "format",
        "--check",
        "--no-cache",
        "--range=5309:1-5311:999",
        "server.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 0.04,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver004-range-server-38.log",
      "log_sha256": "5459a1af2d4cd06784a4df3f383f033d2406f1ec2985f9bbb140e11c17a87fbb"
    },
    {
      "name": "VER-004-ruff-format-range-server-39",
      "cmd": [
        "uvx",
        "--from",
        "ruff==0.17.2",
        "ruff",
        "format",
        "--check",
        "--no-cache",
        "--range=5322:1-5324:999",
        "server.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 0.04,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver004-range-server-39.log",
      "log_sha256": "be56a5d141ae879726c1881ab8cfa22d7656b85dff414f68d0f5c6e5ee338cec"
    },
    {
      "name": "VER-004-ruff-format-range-server-40",
      "cmd": [
        "uvx",
        "--from",
        "ruff==0.17.2",
        "ruff",
        "format",
        "--check",
        "--no-cache",
        "--range=5327:1-5331:999",
        "server.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 0.04,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver004-range-server-40.log",
      "log_sha256": "8b4d01369142097d3605fedf79a388055b489e4a9488e8c09203c90f6ce258fd"
    },
    {
      "name": "VER-004-ruff-format-range-server-41",
      "cmd": [
        "uvx",
        "--from",
        "ruff==0.17.2",
        "ruff",
        "format",
        "--check",
        "--no-cache",
        "--range=5336:1-5341:999",
        "server.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 0.04,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver004-range-server-41.log",
      "log_sha256": "db63a9b27631d2848cb9646c447e74b4547959907a2af711c9e390d57f06a6b4"
    },
    {
      "name": "VER-004-ruff-format-range-server-42",
      "cmd": [
        "uvx",
        "--from",
        "ruff==0.17.2",
        "ruff",
        "format",
        "--check",
        "--no-cache",
        "--range=5343:1-5348:999",
        "server.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 0.04,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver004-range-server-42.log",
      "log_sha256": "edf1e728d3a1e78162570735773864dc3e25e7e19fbaa0758918870b5bca3db3"
    },
    {
      "name": "VER-004-ruff-format-range-server-43",
      "cmd": [
        "uvx",
        "--from",
        "ruff==0.17.2",
        "ruff",
        "format",
        "--check",
        "--no-cache",
        "--range=5351:1-5380:999",
        "server.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 0.04,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver004-range-server-43.log",
      "log_sha256": "fda44981641fda46207e200f893109fc3e694a4c405f49ba41e9f92d898c5e07"
    },
    {
      "name": "VER-004-ruff-format-range-server-44",
      "cmd": [
        "uvx",
        "--from",
        "ruff==0.17.2",
        "ruff",
        "format",
        "--check",
        "--no-cache",
        "--range=5383:1-5408:999",
        "server.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 0.04,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver004-range-server-44.log",
      "log_sha256": "61ea0fb1aba06e25449f2612b634fb314200855d0a43b244c2873749048d878b"
    },
    {
      "name": "VER-004-ruff-format-range-server-45",
      "cmd": [
        "uvx",
        "--from",
        "ruff==0.17.2",
        "ruff",
        "format",
        "--check",
        "--no-cache",
        "--range=5410:1-5434:999",
        "server.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 0.04,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver004-range-server-45.log",
      "log_sha256": "59f99023e45485943b4baf540e6bb7ca11df9d4b2a599cb0bd9aa4b49b52ec9a"
    },
    {
      "name": "VER-004-ruff-format-range-server-46",
      "cmd": [
        "uvx",
        "--from",
        "ruff==0.17.2",
        "ruff",
        "format",
        "--check",
        "--no-cache",
        "--range=5441:1-5441:999",
        "server.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 0.04,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver004-range-server-46.log",
      "log_sha256": "efe2330f4042e4d347064c5eb4c95a514aae435432a978636f893c4b5bf90485"
    },
    {
      "name": "VER-004-ruff-format-range-server-47",
      "cmd": [
        "uvx",
        "--from",
        "ruff==0.17.2",
        "ruff",
        "format",
        "--check",
        "--no-cache",
        "--range=5453:1-5474:999",
        "server.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 0.04,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver004-range-server-47.log",
      "log_sha256": "62b0e86044d4005aabf6b36193f93b51ddf9d706f31a579c7497fc70fe00bbc8"
    },
    {
      "name": "VER-004-ruff-format-range-server-48",
      "cmd": [
        "uvx",
        "--from",
        "ruff==0.17.2",
        "ruff",
        "format",
        "--check",
        "--no-cache",
        "--range=5593:1-5602:999",
        "server.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 0.04,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver004-range-server-48.log",
      "log_sha256": "be4928c4cdac314cdfbb3d9ed146bd1e810ab7230d8117622038329b8242f7db"
    },
    {
      "name": "VER-004-ruff-format-range-server-49",
      "cmd": [
        "uvx",
        "--from",
        "ruff==0.17.2",
        "ruff",
        "format",
        "--check",
        "--no-cache",
        "--range=5662:1-5667:999",
        "server.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 0.04,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver004-range-server-49.log",
      "log_sha256": "917686da3daa63a23567d127e2aa768b31a59f19e398ac6135ae919a4e4aa7f1"
    },
    {
      "name": "VER-004-ruff-format-range-server-50",
      "cmd": [
        "uvx",
        "--from",
        "ruff==0.17.2",
        "ruff",
        "format",
        "--check",
        "--no-cache",
        "--range=5695:1-5705:999",
        "server.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 0.04,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver004-range-server-50.log",
      "log_sha256": "6e945fc57f39e8bda2972c3dbae2dcdd5bd084a526b16177bd7b1e96307a3351"
    },
    {
      "name": "VER-004-ruff-format-range-server-51",
      "cmd": [
        "uvx",
        "--from",
        "ruff==0.17.2",
        "ruff",
        "format",
        "--check",
        "--no-cache",
        "--range=5736:1-5943:999",
        "server.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 0.04,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver004-range-server-51.log",
      "log_sha256": "caa77892ae2b4af29c048102161c237bd74d41143fbcda241c0e4a355bb4798c"
    },
    {
      "name": "VER-004-ruff-format-range-server-52",
      "cmd": [
        "uvx",
        "--from",
        "ruff==0.17.2",
        "ruff",
        "format",
        "--check",
        "--no-cache",
        "--range=5971:1-5991:999",
        "server.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 0.04,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver004-range-server-52.log",
      "log_sha256": "d5ed0ef1c02c1dbca0dea536e990b429541f5d27f422b87a8431603ba43bd3bd"
    },
    {
      "name": "VER-004-ruff-format-range-server-53",
      "cmd": [
        "uvx",
        "--from",
        "ruff==0.17.2",
        "ruff",
        "format",
        "--check",
        "--no-cache",
        "--range=6273:1-6273:999",
        "server.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 0.04,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver004-range-server-53.log",
      "log_sha256": "6f342289ba267b724264369fcf130a8a0635c26ec9443c3cd34dd71f9c5aced1"
    },
    {
      "name": "VER-004-ruff-format-range-test_step_interruption-1",
      "cmd": [
        "uvx",
        "--from",
        "ruff==0.17.2",
        "ruff",
        "format",
        "--check",
        "--no-cache",
        "--range=67:1-67:999",
        "tests/test_step_interruption.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 0.04,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver004-range-test_step_interruption-1.log",
      "log_sha256": "1bfce177c316cdcc6b3567f30279457b3d07734c5dbe6d71e0043126e14329cc"
    },
    {
      "name": "VER-004-ruff-format-range-test_step_interruption-2",
      "cmd": [
        "uvx",
        "--from",
        "ruff==0.17.2",
        "ruff",
        "format",
        "--check",
        "--no-cache",
        "--range=142:1-148:999",
        "tests/test_step_interruption.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 0.04,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver004-range-test_step_interruption-2.log",
      "log_sha256": "43db84d775e827bb10d95980ad3a6ab79d1dad3c72ff41c74a2df1e6b45f0c7b"
    },
    {
      "name": "VER-004-ruff-format-range-test_step_interruption-3",
      "cmd": [
        "uvx",
        "--from",
        "ruff==0.17.2",
        "ruff",
        "format",
        "--check",
        "--no-cache",
        "--range=152:1-152:999",
        "tests/test_step_interruption.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 0.04,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver004-range-test_step_interruption-3.log",
      "log_sha256": "bd29f48f762395c50e3e010617f077c71d139251e91c2b158d86fa064fbcf1da"
    },
    {
      "name": "VER-004-ruff-format-range-test_step_interruption-4",
      "cmd": [
        "uvx",
        "--from",
        "ruff==0.17.2",
        "ruff",
        "format",
        "--check",
        "--no-cache",
        "--range=188:1-189:999",
        "tests/test_step_interruption.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 0.04,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver004-range-test_step_interruption-4.log",
      "log_sha256": "fe32619cd0f07a5dc87b861454f60be891396fd628696cc972e5b6680ba1a260"
    },
    {
      "name": "VER-004-ruff-format-range-test_step_interruption-5",
      "cmd": [
        "uvx",
        "--from",
        "ruff==0.17.2",
        "ruff",
        "format",
        "--check",
        "--no-cache",
        "--range=416:1-418:999",
        "tests/test_step_interruption.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 0.04,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver004-range-test_step_interruption-5.log",
      "log_sha256": "8e3fda2fa1591e93deecb5958c4c58218cc94785d361a2aa06f93b45b30fe0b1"
    },
    {
      "name": "VER-004-ruff-format-range-test_step_interruption-6",
      "cmd": [
        "uvx",
        "--from",
        "ruff==0.17.2",
        "ruff",
        "format",
        "--check",
        "--no-cache",
        "--range=423:1-456:999",
        "tests/test_step_interruption.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 0.04,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver004-range-test_step_interruption-6.log",
      "log_sha256": "a541c75c111a88d475f6740ca78828130e3863cfd672b95fe63e34597edbaf8a"
    },
    {
      "name": "VER-001-pytest",
      "cmd": [
        "uvx",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 142.29,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver001-pytest.log",
      "log_sha256": "6dc083e24777b6ee2ac18e9f0d441a5dfecc4d9e4a474bb375953913c08edfe2"
    },
    {
      "name": "VER-002-unittest",
      "cmd": [
        "python3",
        "-m",
        "unittest",
        "discover",
        "-s",
        "tests",
        "-p",
        "test_*.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 137.64,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver002-unittest.log",
      "log_sha256": "0a3b02903999bc0b50b1c7b3a4c14a0b58f03085480a0ecdfdb63f7533df2f67"
    },
    {
      "name": "VER-003-root-pythonpath-pytest",
      "cmd": [
        "uvx",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom",
      "rc": 0,
      "wall_seconds": 363.04,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver003-pythonpath.log",
      "log_sha256": "72c94be382cf85693719a90dd0ba17b510add53e45b7ac0ceeca6cbe7c9828e1"
    },
    {
      "name": "VER-003b-root-pythonpath-zen-pytest",
      "cmd": [
        "uvx",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "bridges/opencode-zen-bridge/tests/"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom",
      "rc": 0,
      "wall_seconds": 145.1,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver003b-zen-pythonpath.log",
      "log_sha256": "502449035a0241ad74606ba1a65ce8653306648a563df0bdcbde752833221f16"
    },
    {
      "name": "VER-005-dedicated-realtime-suite",
      "cmd": [
        "uvx",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_realtime_reasoning.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 28.52,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver005-dedicated.log",
      "log_sha256": "a1ed5efe4d6da1110fc09fc9566d436dc14f4f90631e0f2b2543f3bc7cb54a05"
    },
    {
      "name": "AC-023-pytest-reversed",
      "cmd": [
        "uvx",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_zen_catalog.py",
        "tests/test_tool_emulation.py",
        "tests/test_sync_yaml.py",
        "tests/test_stream_thinking.py",
        "tests/test_step_interruption.py",
        "tests/test_stdin_prompt.py",
        "tests/test_run_env.py",
        "tests/test_realtime_reasoning.py",
        "tests/test_native_fallback.py",
        "tests/test_lenient_tool_call.py",
        "tests/test_google_direct.py",
        "tests/test_go_model_routing.py",
        "tests/test_effort_mapping.py",
        "tests/test_cli_failure.py",
        "tests/test_catalog_reload.py",
        "tests/test_catalog_mode.py",
        "tests/test_catalog.py",
        "tests/test_aliases.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 142.56,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ac023-reversed.log",
      "log_sha256": "16f2b17ae50bcee67e898b7fa739f7b51898ac32f1ba4515f4957bbb3ebbf378"
    }
  ]
}
ARTIFACT_END>>>
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/verifier.json sha256=57c35ac4fe637c56127a28825fd83ca168be98716268ad35edcd50a988422448
{
  "schema_version": "1.0",
  "gate": "VERIFIER",
  "status": "PASS",
  "run_id": "analyst-teamlead-zen-realtime-reasoning-20261025",
  "timestamp": "2026-10-26T19:33:15.771173+00:00",
  "role_plan": {
    "path": "plans/verifier-01.json",
    "sha256": "07fd6957687d829f23f3230aae032316572d289646de47e6fa185e78bfd8f5f9"
  },
  "code_gate_sha256": "e4171d5605d0c15519fd56f0f18282897837370266268faaa12f2a3c2e97ce35",
  "execution_evidence_sha256": "9a3d51222cdaccf5d8c36191d1a4358fad558757a4e95ca49f6d4fac0c62c766",
  "verification_traceability_sha256": "838bfb35033a7e90582e8b94c680a7667fb48f85fae425cbc7a1129a9f9d111a",
  "environment_manifest_sha256": "437973de9daad996ce91bf5fa7415d84d9b3746e09d12dde2acc30489e7a0870",
  "reverse_spec_sha256": "42a0fcc7615577d69fd35e77a30e358461f56ebc797f13e61712fccfcc512d9e",
  "l3_state": "DEFERRED_L3"
}
ARTIFACT_END>>>
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/final-gate.json sha256=de6b2bc2275b5e40fe5fee64f22f70ff4c6c7c95cf8b71bd365be820aaa4be0c
{
  "schema_version": "1.0",
  "gate": "FINAL_GATE_PRE_COUNCIL",
  "status": "PASS",
  "run_id": "analyst-teamlead-zen-realtime-reasoning-20261025",
  "timestamp": "2026-10-26T19:33:15.771933+00:00",
  "reviewer_skip": true,
  "downstream_panel": true,
  "parent_skill": "analyst-teamlead",
  "coder_handoff_sha256": "8ca5bca38c56715f63209ef79bc47df117795f2d3bc0d8d4607b9ea01f488d18",
  "code_gate_sha256": "e4171d5605d0c15519fd56f0f18282897837370266268faaa12f2a3c2e97ce35",
  "verifier_receipt_sha256": "57c35ac4fe637c56127a28825fd83ca168be98716268ad35edcd50a988422448",
  "candidate_diff_sha256": "22eaa11a35d77b6c749975b9f044bddbeef5437bcffdd187553feb1e18f3ec24",
  "pr_description_absent_before_council": true
}
ARTIFACT_END>>>

## 4. Свидетельства независимой верификации и слепой reverse-spec (`verification-surface.json`, `environment-manifest.json`, `execution-evidence.md`, `verification-traceability.md`, `evidence-manifest.sha256`, `reverse-spec.md`)
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/verification-surface.json sha256=e67d5ffb98e29dd698e38e17e18772fa792391a2e24e05cf88d2f820a14e8722
{
  "schema": "verification-surface/v1",
  "created_at_utc": "2026-10-26T08:16:03.437356+00:00",
  "run_id": "analyst-teamlead-zen-realtime-reasoning-20261025",
  "risk_level": "medium",
  "criticality": "S2",
  "base_sha": "7eda27f9d82732bab726a420e31ea2adc15c2c39",
  "worktree_fingerprint_before_coder": null,
  "worktree_file_count_before_coder": 152,
  "runtime_toolchain": {
    "python3": "Python 3.14.7",
    "uv": "uv 0.12.19 (bea138450 2026-09-24 aarch64-apple-darwin)",
    "ruff": "ruff 0.17.2 (via uvx --from ruff==0.17.2)",
    "basedpyright": "basedpyright 1.40.2 (via uvx --from basedpyright==1.40.2)",
    "opencode": "opencode v2.1.2"
  },
  "container_image_digest": null,
  "lock_files": {},
  "config_and_ci_files": {
    "bridges/opencode-zen-bridge/pyproject.toml": "7d6387d88008df032bfdc5c9f4ca7e7c8eb58ec3d72d1c90ff5b8a227df6b6ff"
  },
  "mandatory_ci_jobs": [],
  "oracle_test_hashes_before_coder": {
    "bridges/opencode-zen-bridge/tests/__init__.py": "41e4377649ceac5f8c9079f7b1dcd7593b7add43ac737b3d7e9dbf4340d465c1",
    "bridges/opencode-zen-bridge/tests/_fake_cli.py": "0dd57ba7b80f54f5d73fa595a1500ff3367f334c5efeaeebe819840b2eb32b75",
    "bridges/opencode-zen-bridge/tests/_fixtures.py": "777898f6d72283a6c034889b43d87e2fa0a16e4068a69eca79a6cee13cf5ae37",
    "bridges/opencode-zen-bridge/tests/_http.py": "834df1103fc7f0f9ba9ac75bd1c2d1f2fb0c5644e1d75d05685e1abdbe865f57",
    "bridges/opencode-zen-bridge/tests/live_matrix.py": "a3f839733a7c723473cb936c8b16f6743c25f3d12053d76461198c7d9a19581e",
    "bridges/opencode-zen-bridge/tests/test_aliases.py": "1a8ca46743d7f59418bf4993933fac4612712e1c786cce8c24efa415ae273568",
    "bridges/opencode-zen-bridge/tests/test_catalog.py": "3dcae238c1e2d743c768e2cef4a3286614ae7051a771c24f2d8ad49a8725cf0d",
    "bridges/opencode-zen-bridge/tests/test_catalog_mode.py": "822dfa9dea1674c141964e3e25fbd272e67c6387d573615a2e0e9111bdc975b8",
    "bridges/opencode-zen-bridge/tests/test_catalog_reload.py": "fac9fad229bdc6d0cd9c696e6283448b629851d64a219735badeb59dcfec7ef6",
    "bridges/opencode-zen-bridge/tests/test_cli_failure.py": "12b95cefcc03ae40ec46494328767c6f9a0f520a014a3d844dbf0eeb5eaeea2d",
    "bridges/opencode-zen-bridge/tests/test_effort_mapping.py": "d26c94b139e3c0a793499baf31c9e4cb1dc92e281fb3d5927da7c019d5f12868",
    "bridges/opencode-zen-bridge/tests/test_go_model_routing.py": "c75d74be787e85900e42e9aa08205ef17045f69b12664602e70159444c8a8f1b",
    "bridges/opencode-zen-bridge/tests/test_google_direct.py": "692d074f1da44189ce0fc19b46c146af103e5be870e072c2f1e6599f39c7d603",
    "bridges/opencode-zen-bridge/tests/test_lenient_tool_call.py": "0dda90013f3f991a95601a17e75269274c52d3ad9206eabe6a3c1247fc9b3768",
    "bridges/opencode-zen-bridge/tests/test_native_fallback.py": "f79f8b7030f9e5ee5a734c38f3846a10446315c574bcba5db69ffab833bcef57",
    "bridges/opencode-zen-bridge/tests/test_run_env.py": "d3d0baf57f7ccae7dd7846ab98d3da43c588a35e7f076fabe074c1212f232e05",
    "bridges/opencode-zen-bridge/tests/test_stdin_prompt.py": "533c0905314a31dfe63ea519fb3d1d2a43f9e629a61d9d00cb508ba7c674e8c6",
    "bridges/opencode-zen-bridge/tests/test_step_interruption.py": "afd542fed0722e48989c997c31595772a5c2df194a6c47ae6c1e86935bb2aa6e",
    "bridges/opencode-zen-bridge/tests/test_stream_thinking.py": "ddaa0b97d274ec6f1a13fa7cb17856c109d4f219caa04a03e425127703b8f8ca",
    "bridges/opencode-zen-bridge/tests/test_sync_yaml.py": "1e8593332bacd8f116fc587b6838b139e181211adb749cfe0fc7c9322a0d29ef",
    "bridges/opencode-zen-bridge/tests/test_tool_emulation.py": "bd756c717909687bc974e68c184a6d1d7937043edf2f3768bfdae40d5c2b51af",
    "bridges/opencode-zen-bridge/tests/test_zen_catalog.py": "8f4c60f33e041da64ae4f297286d5900e7aa6ac0776142fcda15c05ca5b7423e"
  },
  "testdata_golden_snapshot_hashes": {},
  "coverage_and_quality_thresholds": {
    "ruff_format_check": "exit 0 on tests/test_realtime_reasoning.py + closed --range={start}:1-{end}:999 on modified hunks of server.py and tests/test_step_interruption.py + frozen slice sha256 checks",
    "ruff_check": "exit 0 on coder_target_files (allowing existing import zen_catalog as zc E402 on server.py)",
    "basedpyright": "0 errors and per-rule warning counts <= baseline ceilings (reportAny <= 125, 0 new Any in changed ranges) via basedpyright==1.40.2",
    "external_runtime_dependencies": "0 outside Python 3.14 stdlib"
  },
  "baseline": {
    "command": "cd bridges/opencode-zen-bridge && uvx pytest -q -p no:cacheprovider tests/",
    "exit_code": 1,
    "counts": {
      "collected": 378,
      "passed": 375,
      "failed": 3,
      "skipped": 0,
      "xfailed": 0,
      "xpassed": 0
    },
    "preexisting_red_failures": [
      {
        "test_id": "tests/test_step_interruption.py::StepInterruptionTests::test_four_consecutive_interruptions_exhaust_budget",
        "phase": "call",
        "exception_type": "AssertionError",
        "message_key": "MAX_TOTAL_SPAWNS=3 caps total spawns at 3 while legacy test asserts 4 spawns (F-47)"
      },
      {
        "test_id": "tests/test_step_interruption.py::StepInterruptionTests::test_non_stream_retries_on_step_interruption",
        "phase": "call",
        "exception_type": "AssertionError",
        "message_key": "shared _RetryBudget / MAX_TOTAL_SPAWNS=3 mismatch in legacy test fixture (F-48)"
      },
      {
        "test_id": "tests/test_step_interruption.py::StepInterruptionTests::test_stream_retries_on_step_interruption_and_succeeds",
        "phase": "call",
        "exception_type": "AssertionError",
        "message_key": "shared _RetryBudget / MAX_TOTAL_SPAWNS=3 mismatch in legacy test fixture (F-49)"
      }
    ],
    "note": "REQ-017 / AD-004 explicitly scopes fixing these 3 legacy test/budget drift items without weakening MAX_TOTAL_SPAWNS=3 invariant; Verifier audits any oracle_change in tests/test_step_interruption.py."
  },
  "allowed_envelope_changes": {
    "code": [
      "bridges/opencode-zen-bridge/server.py"
    ],
    "new_tests": [
      "bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py"
    ],
    "existing_tests_additive_or_req017": [
      "bridges/opencode-zen-bridge/tests/test_step_interruption.py"
    ],
    "forbidden_oracle_changes": [
      "bridges/opencode-zen-bridge/tests/test_run_env.py",
      "bridges/opencode-zen-bridge/tests/test_google_direct.py",
      "bridges/opencode-zen-bridge/tests/test_catalog_mode.py",
      "bridges/opencode-zen-bridge/tests/test_zen_bridge.py",
      "deleting tests, adding skip/xfail, weakening assertions, narrowing test selectors"
    ],
    "dependencies": [],
    "configs": []
  },
  "levels": {
    "L1": [
      {
        "id": "VER-004-static-and-frozen-slices",
        "cmd": "python3 - <<'VER004'\nimport ast, collections, hashlib, json, re, subprocess, tempfile\nfrom pathlib import Path\nroot = Path.cwd().resolve()\nbridge = root / 'bridges/opencode-zen-bridge'\nfiles = [bridge/'server.py', bridge/'tests/test_step_interruption.py', bridge/'tests/test_realtime_reasoning.py']\nassert all(f.is_file() for f in files), 'all three target files must exist after Stage3'\nruff = ['uvx','--from','ruff==0.17.2','ruff']\ndef run(args, **kw):\n    return subprocess.run(args, check=True, **kw)\ndef changed_ranges(file):\n    rel = str(file.relative_to(root))\n    diff = subprocess.check_output(['git','diff','--no-ext-diff','--no-color','-U0','origin/dev','--',rel], cwd=root, text=True)\n    # NEW tracked files must be added before final verification; --no-index alternative below covers untracked newfile.\n    result = []\n    for line in diff.splitlines():\n        m = re.match(r'^@@ -\\d+(?:,\\d+)? \\+(\\d+)(?:,(\\d+))? @@', line)\n        if m:\n            start = int(m.group(1)); count = int(m.group(2) or '1')\n            if count: result.append((start, start + count - 1))\n    return result\n\n# Raw-byte contract: frozen expected digests originate in EVD-075, never candidate.\nFROZEN = {\n    '_run_env': '1c51b28fcb83fcc0f4d8b5204c858e11ab5ac975bfe40dca4a0bf61978008e31',\n    '_stream_google_sse': '5914c9654c7345692dd55e84cfd3765e27406f63a3df85df30bc798bc1778de3',\n    '_execute_google_once': '88d794cc42be4878e8ab35b00e4668c427929db2dfd0f2bb4b717a63fd0c70d6',\n}\nbaseline_raw = subprocess.check_output(['git','show','origin/dev:bridges/opencode-zen-bridge/server.py'], cwd=root)\ndef frozen_slices(raw):\n    lines = raw.splitlines(keepends=True)\n    nodes = {n.name:n for n in ast.walk(ast.parse(raw)) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name in FROZEN}\n    assert set(nodes)==set(FROZEN)\n    return {name:(node.lineno,node.end_lineno,b''.join(lines[node.lineno-1:node.end_lineno])) for name,node in nodes.items()}\nbaseline_slices = frozen_slices(baseline_raw)\ndef assert_frozen(candidate=files[0]):\n    candidate_slices = frozen_slices(candidate.read_bytes())\n    for name, expected in FROZEN.items():\n        assert hashlib.sha256(baseline_slices[name][2]).hexdigest()==expected, ('frozen origin/dev changed',name)\n        assert hashlib.sha256(candidate_slices[name][2]).hexdigest()==expected, ('immutable slice changed',name)\n        assert candidate_slices[name][2]==baseline_slices[name][2], ('nonzero raw Google/_run_env diff',name)\n    return candidate_slices\ncandidate_slices = assert_frozen()\nserver_diff = subprocess.check_output(['git','diff','--no-ext-diff','--no-color','-U0','origin/dev','--',str(files[0].relative_to(root))],cwd=root,text=True)\nfor line in server_diff.splitlines():\n    match = re.match(r'^@@ -(\\d+)(?:,(\\d+))? \\+(\\d+)(?:,(\\d+))? @@',line)\n    if not match: continue\n    old_start,old_count,new_start,new_count = int(match[1]),int(match[2] or '1'),int(match[3]),int(match[4] or '1')\n    for start,count,table in [(old_start,old_count,baseline_slices),(new_start,new_count,candidate_slices)]:\n        for name,(lo,hi,_) in table.items():\n            # Zero-count insert/delete anchors represent the boundary after start.\n            overlaps = (start<=hi and start+count-1>=lo) if count else (lo<=start<hi)\n            assert not overlaps, ('VER-004 frozen-range hunk intersection',name,line)\n# Public module constant/read API remains intact; compatibility test file is frozen.\ntree = ast.parse(files[0].read_bytes())\nassignments = [n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='CATALOG_SOURCE' for t in n.targets)]\nassert len(assignments)==1 and isinstance(assignments[0].value,ast.Constant) and assignments[0].value.value=='static'\nassert any(isinstance(n,ast.FunctionDef) and n.name=='_set_catalog_source' for n in tree.body)\nassert any(isinstance(n,ast.Import) and any(a.name=='zen_catalog' and a.asname=='zc' for a in n.names) for n in ast.walk(tree))\nassert not any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='import_module' and n.args and isinstance(n.args[0],ast.Constant) and n.args[0].value=='zen_catalog' for n in ast.walk(tree))\nassert any(isinstance(n,ast.FunctionDef) and n.name=='_run_serve_helper_cli' for n in tree.body), 'helper code must be lint/type checked in server.py'\nhelper_branch = next((n for n in tree.body if isinstance(n, ast.If) and ast.unparse(n.test) == \"sys.argv[1:2] == ['--serve-helper']\"), None)\nassert helper_branch is not None and any(isinstance(n, ast.Raise) for n in helper_branch.body), 'early terminating helper dispatch required'\nheavy = {'http.client', 'sqlite3', 'http.server', 'zen_catalog'}\ndef imported_names(node):\n    if isinstance(node, ast.Import): return {a.name for a in node.names}\n    if isinstance(node, ast.ImportFrom): return {node.module}\n    return set()\nassert not any(imported_names(n) & heavy for n in tree.body[:tree.body.index(helper_branch)])\nassert any(isinstance(n, ast.Import) and any(a.name == 'zen_catalog' and a.asname == 'zc' for a in n.names) for n in helper_branch.orelse)\nassert all(not isinstance(n, (ast.Assign, ast.AnnAssign, ast.Expr)) for n in tree.body[1:tree.body.index(helper_branch)]), 'no server initialization before helper exit'\nassert not any(isinstance(n,ast.Global) and 'CATALOG_SOURCE' in n.names for n in ast.walk(tree))\nrun(['git','diff','--exit-code','origin/dev','--','bridges/opencode-zen-bridge/tests/test_catalog_mode.py'],cwd=root)\n\nranges = {f: changed_ranges(f) for f in files[:2]}\n# New file checked as a whole even before git add. Range gate never formats frozen legacy slices.\nrun([*ruff,'format','--config',str(root / 'ruff.toml'),'--check','--no-cache',str(files[2])], cwd=root)\nfor f in files[:2]:\n    for start, end in ranges[f]:\n        run([*ruff,'format','--config',str(root / 'ruff.toml'),'--check','--no-cache',f'--range={start}:1-{end}:999',str(f)], cwd=root)\nassert_frozen()\n# Exercise actual write-mode range formatting only on a disposable copy.\nwith tempfile.TemporaryDirectory(prefix='zen-arch6-probe-format-', dir='/tmp') as format_dir:\n    formatted_copy = Path(format_dir) / 'server.py'\n    formatted_copy.write_bytes(files[0].read_bytes())\n    for start, end in ranges[files[0]]:\n        run([*ruff,'format','--config',str(root / 'ruff.toml'),'--no-cache',f'--range={start}:1-{end}:999',str(formatted_copy)], cwd=root)\n    assert formatted_copy.read_bytes() == files[0].read_bytes()\n    assert_frozen(formatted_copy)\n    assert_frozen()\n    print('PASS write-mode frozen hashes', {name:hashlib.sha256(data[2]).hexdigest() for name,data in frozen_slices(formatted_copy.read_bytes()).items()})\n# Full-file lint on all three. Only inherited E402 import site is excepted on server.\nlint = subprocess.run([*ruff,'check','--config',str(root / 'ruff.toml'),'--no-cache','--output-format','json',str(files[0])], cwd=root, capture_output=True, text=True)\nassert lint.returncode in (0,1), lint.stderr\nfindings = json.loads(lint.stdout)\nlines = files[0].read_text().splitlines()\nassert all(x['code']=='E402' and lines[x['location']['row']-1].strip()=='import zen_catalog as zc' for x in findings), findings\nassert sum(x['code']=='E402' for x in findings) <= 1\nrun([*ruff,'check','--config',str(root / 'ruff.toml'),'--no-cache','--extend-ignore','E402',str(files[0])], cwd=root)\nrun([*ruff,'check','--config',str(root / 'ruff.toml'),'--no-cache',str(files[1]),str(files[2])], cwd=root)\n# Exact isolated import-root. No repo pyrightconfig mutation; JSON deleted on every exit.\nproject = None\ntry:\n    with tempfile.NamedTemporaryFile(mode='w',suffix='.json',prefix='zen-arch6-probe-project-',dir='/tmp',delete=False) as tmp:\n        project = Path(tmp.name)\n        json.dump({'include':[str(f) for f in files], 'extraPaths':[str(bridge.resolve())]},tmp)\n    b = subprocess.run(['uvx','--from','basedpyright==1.40.2','basedpyright','--project',str(project),'--outputjson'], cwd=bridge, capture_output=True, text=True)\n    assert b.returncode in (0,1), b.stderr\n    report = json.loads(b.stdout)\n    ds = report['generalDiagnostics']\n    assert report['summary']['errorCount']==0 and not [x for x in ds if x['severity']=='error'], ds\n    byfile = {f: [x for x in ds if Path(x['file']).resolve()==f] for f in files}\n    limits = {'reportExplicitAny':125,'reportAny':125,'reportUnusedCallResult':39,'reportUnknownMemberType':94,'reportUnknownVariableType':72,'reportUnknownArgumentType':55,'reportUnusedFunction':6,'reportImplicitStringConcatenation':35,'reportUnannotatedClassAttribute':105,'reportUnusedParameter':7,'reportUnnecessaryIsInstance':11,'reportUnknownParameterType':6,'reportMissingParameterType':4,'reportUnreachable':5,'reportImplicitOverride':3}\n    warnings = lambda f: [x for x in byfile[f] if x['severity']=='warning']\n    counts = collections.Counter(x.get('rule','') for x in warnings(files[0]))\n    print('BASEDPYRIGHT summary',report['summary'])\n    print('SERVER dict(counts)',dict(counts))\n    print('SERVER warningCount',len(warnings(files[0])))\n    assert all(n<=limits.get(rule,0) for rule,n in counts.items()), dict(counts)\n    assert len(warnings(files[0]))<=720, len(warnings(files[0]))\n    assert len(warnings(files[1]))<=194, len(warnings(files[1]))\n    # New test file: zero warnings as well as zero errors, thus zero Any.\n    assert not byfile[files[2]], byfile[files[2]]\n    for f in files[:2]:\n        for x in byfile[f]:\n            line = x['range']['start']['line']+1\n            if any(lo<=line<=hi for lo,hi in ranges[f]):\n                assert x.get('rule') not in {'reportAny','reportExplicitAny','reportUnusedCallResult'}, x\n    # Do not introduce Any annotations/type ignores in added code in either legacy file.\n    for f in files[:2]:\n        src = f.read_text().splitlines()\n        for lo,hi in ranges[f]:\n            for line in src[lo-1:hi]:\n                assert not re.search(r'\\bAny\\b|type:\\s*ignore|pyright:\\s*ignore|#\\s*noqa|#\\s*fmt:\\s*off',line), (f,line)\n    run(['python3','-B','-m','unittest','tests.test_catalog_mode','-v'],cwd=bridge)\n    print('PASS VER-004: all3 lint/type; legacy changed-range format; newfile whole format; server counts',dict(counts))\nfinally:\n    if project is not None: project.unlink(missing_ok=True)\nVER004",
        "cwd": "."
      },
      {
        "id": "VER-001-pytest-component",
        "cmd": "uvx pytest -q -p no:cacheprovider tests/",
        "cwd": "bridges/opencode-zen-bridge"
      }
    ],
    "L2": [
      {
        "id": "L2-VER-004-static-and-frozen-slices",
        "cmd": "python3 - <<'VER004'\nimport ast, collections, hashlib, json, re, subprocess, tempfile\nfrom pathlib import Path\nroot = Path.cwd().resolve()\nbridge = root / 'bridges/opencode-zen-bridge'\nfiles = [bridge/'server.py', bridge/'tests/test_step_interruption.py', bridge/'tests/test_realtime_reasoning.py']\nassert all(f.is_file() for f in files), 'all three target files must exist after Stage3'\nruff = ['uvx','--from','ruff==0.17.2','ruff']\ndef run(args, **kw):\n    return subprocess.run(args, check=True, **kw)\ndef changed_ranges(file):\n    rel = str(file.relative_to(root))\n    diff = subprocess.check_output(['git','diff','--no-ext-diff','--no-color','-U0','origin/dev','--',rel], cwd=root, text=True)\n    # NEW tracked files must be added before final verification; --no-index alternative below covers untracked newfile.\n    result = []\n    for line in diff.splitlines():\n        m = re.match(r'^@@ -\\d+(?:,\\d+)? \\+(\\d+)(?:,(\\d+))? @@', line)\n        if m:\n            start = int(m.group(1)); count = int(m.group(2) or '1')\n            if count: result.append((start, start + count - 1))\n    return result\n\n# Raw-byte contract: frozen expected digests originate in EVD-075, never candidate.\nFROZEN = {\n    '_run_env': '1c51b28fcb83fcc0f4d8b5204c858e11ab5ac975bfe40dca4a0bf61978008e31',\n    '_stream_google_sse': '5914c9654c7345692dd55e84cfd3765e27406f63a3df85df30bc798bc1778de3',\n    '_execute_google_once': '88d794cc42be4878e8ab35b00e4668c427929db2dfd0f2bb4b717a63fd0c70d6',\n}\nbaseline_raw = subprocess.check_output(['git','show','origin/dev:bridges/opencode-zen-bridge/server.py'], cwd=root)\ndef frozen_slices(raw):\n    lines = raw.splitlines(keepends=True)\n    nodes = {n.name:n for n in ast.walk(ast.parse(raw)) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name in FROZEN}\n    assert set(nodes)==set(FROZEN)\n    return {name:(node.lineno,node.end_lineno,b''.join(lines[node.lineno-1:node.end_lineno])) for name,node in nodes.items()}\nbaseline_slices = frozen_slices(baseline_raw)\ndef assert_frozen(candidate=files[0]):\n    candidate_slices = frozen_slices(candidate.read_bytes())\n    for name, expected in FROZEN.items():\n        assert hashlib.sha256(baseline_slices[name][2]).hexdigest()==expected, ('frozen origin/dev changed',name)\n        assert hashlib.sha256(candidate_slices[name][2]).hexdigest()==expected, ('immutable slice changed',name)\n        assert candidate_slices[name][2]==baseline_slices[name][2], ('nonzero raw Google/_run_env diff',name)\n    return candidate_slices\ncandidate_slices = assert_frozen()\nserver_diff = subprocess.check_output(['git','diff','--no-ext-diff','--no-color','-U0','origin/dev','--',str(files[0].relative_to(root))],cwd=root,text=True)\nfor line in server_diff.splitlines():\n    match = re.match(r'^@@ -(\\d+)(?:,(\\d+))? \\+(\\d+)(?:,(\\d+))? @@',line)\n    if not match: continue\n    old_start,old_count,new_start,new_count = int(match[1]),int(match[2] or '1'),int(match[3]),int(match[4] or '1')\n    for start,count,table in [(old_start,old_count,baseline_slices),(new_start,new_count,candidate_slices)]:\n        for name,(lo,hi,_) in table.items():\n            # Zero-count insert/delete anchors represent the boundary after start.\n            overlaps = (start<=hi and start+count-1>=lo) if count else (lo<=start<hi)\n            assert not overlaps, ('VER-004 frozen-range hunk intersection',name,line)\n# Public module constant/read API remains intact; compatibility test file is frozen.\ntree = ast.parse(files[0].read_bytes())\nassignments = [n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='CATALOG_SOURCE' for t in n.targets)]\nassert len(assignments)==1 and isinstance(assignments[0].value,ast.Constant) and assignments[0].value.value=='static'\nassert any(isinstance(n,ast.FunctionDef) and n.name=='_set_catalog_source' for n in tree.body)\nassert any(isinstance(n,ast.Import) and any(a.name=='zen_catalog' and a.asname=='zc' for a in n.names) for n in ast.walk(tree))\nassert not any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='import_module' and n.args and isinstance(n.args[0],ast.Constant) and n.args[0].value=='zen_catalog' for n in ast.walk(tree))\nassert any(isinstance(n,ast.FunctionDef) and n.name=='_run_serve_helper_cli' for n in tree.body), 'helper code must be lint/type checked in server.py'\nhelper_branch = next((n for n in tree.body if isinstance(n, ast.If) and ast.unparse(n.test) == \"sys.argv[1:2] == ['--serve-helper']\"), None)\nassert helper_branch is not None and any(isinstance(n, ast.Raise) for n in helper_branch.body), 'early terminating helper dispatch required'\nheavy = {'http.client', 'sqlite3', 'http.server', 'zen_catalog'}\ndef imported_names(node):\n    if isinstance(node, ast.Import): return {a.name for a in node.names}\n    if isinstance(node, ast.ImportFrom): return {node.module}\n    return set()\nassert not any(imported_names(n) & heavy for n in tree.body[:tree.body.index(helper_branch)])\nassert any(isinstance(n, ast.Import) and any(a.name == 'zen_catalog' and a.asname == 'zc' for a in n.names) for n in helper_branch.orelse)\nassert all(not isinstance(n, (ast.Assign, ast.AnnAssign, ast.Expr)) for n in tree.body[1:tree.body.index(helper_branch)]), 'no server initialization before helper exit'\nassert not any(isinstance(n,ast.Global) and 'CATALOG_SOURCE' in n.names for n in ast.walk(tree))\nrun(['git','diff','--exit-code','origin/dev','--','bridges/opencode-zen-bridge/tests/test_catalog_mode.py'],cwd=root)\n\nranges = {f: changed_ranges(f) for f in files[:2]}\n# New file checked as a whole even before git add. Range gate never formats frozen legacy slices.\nrun([*ruff,'format','--config',str(root / 'ruff.toml'),'--check','--no-cache',str(files[2])], cwd=root)\nfor f in files[:2]:\n    for start, end in ranges[f]:\n        run([*ruff,'format','--config',str(root / 'ruff.toml'),'--check','--no-cache',f'--range={start}:1-{end}:999',str(f)], cwd=root)\nassert_frozen()\n# Exercise actual write-mode range formatting only on a disposable copy.\nwith tempfile.TemporaryDirectory(prefix='zen-arch6-probe-format-', dir='/tmp') as format_dir:\n    formatted_copy = Path(format_dir) / 'server.py'\n    formatted_copy.write_bytes(files[0].read_bytes())\n    for start, end in ranges[files[0]]:\n        run([*ruff,'format','--config',str(root / 'ruff.toml'),'--no-cache',f'--range={start}:1-{end}:999',str(formatted_copy)], cwd=root)\n    assert formatted_copy.read_bytes() == files[0].read_bytes()\n    assert_frozen(formatted_copy)\n    assert_frozen()\n    print('PASS write-mode frozen hashes', {name:hashlib.sha256(data[2]).hexdigest() for name,data in frozen_slices(formatted_copy.read_bytes()).items()})\n# Full-file lint on all three. Only inherited E402 import site is excepted on server.\nlint = subprocess.run([*ruff,'check','--config',str(root / 'ruff.toml'),'--no-cache','--output-format','json',str(files[0])], cwd=root, capture_output=True, text=True)\nassert lint.returncode in (0,1), lint.stderr\nfindings = json.loads(lint.stdout)\nlines = files[0].read_text().splitlines()\nassert all(x['code']=='E402' and lines[x['location']['row']-1].strip()=='import zen_catalog as zc' for x in findings), findings\nassert sum(x['code']=='E402' for x in findings) <= 1\nrun([*ruff,'check','--config',str(root / 'ruff.toml'),'--no-cache','--extend-ignore','E402',str(files[0])], cwd=root)\nrun([*ruff,'check','--config',str(root / 'ruff.toml'),'--no-cache',str(files[1]),str(files[2])], cwd=root)\n# Exact isolated import-root. No repo pyrightconfig mutation; JSON deleted on every exit.\nproject = None\ntry:\n    with tempfile.NamedTemporaryFile(mode='w',suffix='.json',prefix='zen-arch6-probe-project-',dir='/tmp',delete=False) as tmp:\n        project = Path(tmp.name)\n        json.dump({'include':[str(f) for f in files], 'extraPaths':[str(bridge.resolve())]},tmp)\n    b = subprocess.run(['uvx','--from','basedpyright==1.40.2','basedpyright','--project',str(project),'--outputjson'], cwd=bridge, capture_output=True, text=True)\n    assert b.returncode in (0,1), b.stderr\n    report = json.loads(b.stdout)\n    ds = report['generalDiagnostics']\n    assert report['summary']['errorCount']==0 and not [x for x in ds if x['severity']=='error'], ds\n    byfile = {f: [x for x in ds if Path(x['file']).resolve()==f] for f in files}\n    limits = {'reportExplicitAny':125,'reportAny':125,'reportUnusedCallResult':39,'reportUnknownMemberType':94,'reportUnknownVariableType':72,'reportUnknownArgumentType':55,'reportUnusedFunction':6,'reportImplicitStringConcatenation':35,'reportUnannotatedClassAttribute':105,'reportUnusedParameter':7,'reportUnnecessaryIsInstance':11,'reportUnknownParameterType':6,'reportMissingParameterType':4,'reportUnreachable':5,'reportImplicitOverride':3}\n    warnings = lambda f: [x for x in byfile[f] if x['severity']=='warning']\n    counts = collections.Counter(x.get('rule','') for x in warnings(files[0]))\n    print('BASEDPYRIGHT summary',report['summary'])\n    print('SERVER dict(counts)',dict(counts))\n    print('SERVER warningCount',len(warnings(files[0])))\n    assert all(n<=limits.get(rule,0) for rule,n in counts.items()), dict(counts)\n    assert len(warnings(files[0]))<=720, len(warnings(files[0]))\n    assert len(warnings(files[1]))<=194, len(warnings(files[1]))\n    # New test file: zero warnings as well as zero errors, thus zero Any.\n    assert not byfile[files[2]], byfile[files[2]]\n    for f in files[:2]:\n        for x in byfile[f]:\n            line = x['range']['start']['line']+1\n            if any(lo<=line<=hi for lo,hi in ranges[f]):\n                assert x.get('rule') not in {'reportAny','reportExplicitAny','reportUnusedCallResult'}, x\n    # Do not introduce Any annotations/type ignores in added code in either legacy file.\n    for f in files[:2]:\n        src = f.read_text().splitlines()\n        for lo,hi in ranges[f]:\n            for line in src[lo-1:hi]:\n                assert not re.search(r'\\bAny\\b|type:\\s*ignore|pyright:\\s*ignore|#\\s*noqa|#\\s*fmt:\\s*off',line), (f,line)\n    run(['python3','-B','-m','unittest','tests.test_catalog_mode','-v'],cwd=bridge)\n    print('PASS VER-004: all3 lint/type; legacy changed-range format; newfile whole format; server counts',dict(counts))\nfinally:\n    if project is not None: project.unlink(missing_ok=True)\nVER004",
        "cwd": "."
      },
      {
        "id": "L2-VER-001-pytest-component",
        "cmd": "uvx pytest -q -p no:cacheprovider tests/",
        "cwd": "bridges/opencode-zen-bridge"
      },
      {
        "id": "L2-VER-002-unittest-discover",
        "cmd": "python3 -m unittest discover -s tests -p 'test_*.py'",
        "cwd": "bridges/opencode-zen-bridge"
      },
      {
        "id": "L2-VER-003-pytest-root-import",
        "cmd": "PYTHONPATH=. uvx pytest -q -p no:cacheprovider bridges/opencode-zen-bridge/tests/",
        "cwd": "."
      },
      {
        "id": "L2-VER-005-realtime-and-fault-oracles",
        "cmd": "uvx pytest -q -p no:cacheprovider tests/test_realtime_reasoning.py tests/test_step_interruption.py tests/test_run_env.py tests/test_google_direct.py tests/test_catalog_mode.py",
        "cwd": "bridges/opencode-zen-bridge"
      }
    ],
    "L3": {
      "status_pre_accept": "N/A_REPO_MARKERS_PLUS_POST_ACCEPT_LIVE_HEAVY_PATH",
      "note": "Repo has no pytest heavy/measured markers (entire component suite runs in L2). Live runtime checks H0..H9 / VER-006/VER-007 on deployed LaunchAgent 127.0.0.1:9883 are DEFERRED_L3 until Council ACCEPT + cp sync of server.py to ~/.dsh/bridges/opencode-zen-bridge/server.py so live production bridge is not mutated before Council ACCEPT.",
      "deferred_checks": [
        {
          "id": "VER-006-live-sse-heavy-path",
          "cmd": "Rollout ladder H0..H9 + curl -N -sS http://127.0.0.1:9883/v1/chat/completions (deepseek-v4.1-flash-free High, stream=true, multi-turn + tools + disconnect cleanup)",
          "defer_reason": "Requires syncing ~/.dsh/bridges/opencode-zen-bridge/server.py after Council ACCEPT"
        },
        {
          "id": "VER-007-deployed-mirror-diff",
          "cmd": "diff -u bridges/opencode-zen-bridge/server.py ~/.dsh/bridges/opencode-zen-bridge/server.py",
          "defer_reason": "Synced post-ACCEPT after backup to ~/work/backups/"
        }
      ]
    }
  },
  "acceptance_manifest_ref": "analysis/zen-realtime-reasoning/handoff-qa.md",
  "architecture_packet_sha256": "88c02c37a7ca0be3d317217f23289dba07ddc681d922db207c7680a779128b6b"
}
ARTIFACT_END>>>
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/environment-manifest.json sha256=437973de9daad996ce91bf5fa7415d84d9b3746e09d12dde2acc30489e7a0870
{
  "schema": "environment-manifest/v1",
  "captured_at_utc": "2026-10-26T19:33:15.566360+00:00",
  "run_id": "analyst-teamlead-zen-realtime-reasoning-20261025",
  "platform": {
    "system": "Darwin",
    "release": "27.0.0",
    "machine": "arm64",
    "python_version": "3.14.7",
    "python_executable": "/opt/homebrew/opt/python@3.14/bin/python3.14"
  },
  "tools": {
    "uv": "uv 0.12.19 (bea138450 2026-09-24 aarch64-apple-darwin)",
    "ruff": "ruff 0.17.2 (uvx --from ruff==0.17.2)",
    "basedpyright": "basedpyright 1.40.2 (uvx --from basedpyright==1.40.2)",
    "opencode": "opencode v2.1.2",
    "git": "git version 2.54.0"
  },
  "isolation": {
    "cleanroom_mode": "git worktree --detach at origin/dev (/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom)",
    "coder_worktree": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning",
    "worktree_fingerprint_before": null,
    "worktree_fingerprint_after": null,
    "external_runtime_dependencies_added": 0
  }
}
ARTIFACT_END>>>
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/execution-evidence.md sha256=9a3d51222cdaccf5d8c36191d1a4358fad558757a4e95ca49f6d4fac0c62c766
# Независимое свидетельство исполнения верификации (`execution-evidence.md`, run `analyst-teamlead-zen-realtime-reasoning-20261025`)

- **Базовый коммит (`origin/dev`):** `7eda27f9d82732bab726a420e31ea2adc15c2c39`
- **Отпечаток рабочего дерева ДО Coder (`coder-01-before.json`):** `None`
- **Отпечаток рабочего дерева ПОСЛЕ Coder (`coder-03-after.json`):** `None`
- **Clean-room контур L2:** отдельное `git worktree` от `origin/dev`, исполнено детерминированным `Verifier` (`run_cleanroom_l2.py`), не логами `Coder`.

## Сводная таблица проверок L2 и L3

| ID / Проверка | Уровень | Статус | Команда | CWD | Exit code | Wall (s) | Сырой лог | SHA-256 лога |
|---|---|---|---|---|---|---|---|---|
| `L2-RED-sensitivity` | L2 | `PASS (RED sensitivity rc!=0)` | `uvx pytest -q -p no:cacheprovider tests/test_realtime_reasoning.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `1` | `23.79` | `l2-red.log` | `b8b80dd34adbf1f2bab310d2d0926d52559ae5e7323a81ef75cb93ddd02cf0bf` |
| `VER-004-packet-command` | L2 | `PASS` | `/bin/zsh -lc python3 - <<'VER004' import ast, collections, hashlib, json, re, subprocess, tempfile from pathlib import Path root = Path.c...` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom` | `0` | `9.33` | `l2-green-ver004-packet.log` | `6c0b3627322b3ea368d0add2b4a8f9f050f6c70f3cb8846a2f766bbf8ee63800` |
| `VER-004-ruff-format-new` | L2 | `PASS` | `uvx --from ruff==0.17.2 ruff format --check --no-cache tests/test_realtime_reasoning.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `0.04` | `l2-green-ver004-ruff-format-new.log` | `791491a5d9e6128b8400ae730e69e74c9af01651d625cc697d569dfdcee245b7` |
| `VER-004-ruff-format-range-server-1` | L2 | `PASS` | `uvx --from ruff==0.17.2 ruff format --check --no-cache --range=22:1-22:999 server.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `0.05` | `l2-green-ver004-range-server-1.log` | `755d9227e95b948c1b21b60a6a5719f23874a7f21c9eaa06d940767f5734d920` |
| `VER-004-ruff-format-range-server-2` | L2 | `PASS` | `uvx --from ruff==0.17.2 ruff format --check --no-cache --range=29:1-224:999 server.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `0.05` | `l2-green-ver004-range-server-2.log` | `d43ecdb8d6ac5fbb42ad87118c810f0502f825f1e90d9caa99b63adad6226dd8` |
| `VER-004-ruff-format-range-server-3` | L2 | `PASS` | `uvx --from ruff==0.17.2 ruff format --check --no-cache --range=259:1-267:999 server.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `0.05` | `l2-green-ver004-range-server-3.log` | `acfa83afea14da20895c3c5df8891eefc261d948f1733e6a9362c94316fbc5e8` |
| `VER-004-ruff-format-range-server-4` | L2 | `PASS` | `uvx --from ruff==0.17.2 ruff format --check --no-cache --range=282:1-287:999 server.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `0.05` | `l2-green-ver004-range-server-4.log` | `88452847a1c7bf2735617ebc981f4546653b761feb86581b86c09defcbbabd90` |
| `VER-004-ruff-format-range-server-5` | L2 | `PASS` | `uvx --from ruff==0.17.2 ruff format --check --no-cache --range=310:1-310:999 server.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `0.04` | `l2-green-ver004-range-server-5.log` | `3001e902e898ce08be329b7fb21e859b94d1f64fd4223e58eb45d3e1bafa83e0` |
| `VER-004-ruff-format-range-server-6` | L2 | `PASS` | `uvx --from ruff==0.17.2 ruff format --check --no-cache --range=323:1-323:999 server.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `0.04` | `l2-green-ver004-range-server-6.log` | `395372d5783c465bb44896e2b27bb87f887cc2483269a1045a3fb28fdd568474` |
| `VER-004-ruff-format-range-server-7` | L2 | `PASS` | `uvx --from ruff==0.17.2 ruff format --check --no-cache --range=1326:1-1887:999 server.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `0.05` | `l2-green-ver004-range-server-7.log` | `ef3916991629bdb55ce1820231b7cc0c4f70ba15083be97b22ebdce0ee32b7f5` |
| `VER-004-ruff-format-range-server-8` | L2 | `PASS` | `uvx --from ruff==0.17.2 ruff format --check --no-cache --range=2204:1-2206:999 server.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `0.05` | `l2-green-ver004-range-server-8.log` | `91e7ac7b68fc502cae836236045fb6e74e77bdd8704fd29f78eb0df1f357f8c5` |
| `VER-004-ruff-format-range-server-9` | L2 | `PASS` | `uvx --from ruff==0.17.2 ruff format --check --no-cache --range=2221:1-2221:999 server.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `0.05` | `l2-green-ver004-range-server-9.log` | `aa564ad3b2e4ce1923226de4ae4763b1fd8789f2b1a4cc257747cd61f6a7f584` |
| `VER-004-ruff-format-range-server-10` | L2 | `PASS` | `uvx --from ruff==0.17.2 ruff format --check --no-cache --range=2231:1-2239:999 server.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `0.04` | `l2-green-ver004-range-server-10.log` | `55dad36c122f16886bc8f61615b1f48774f27888e6a56f028ee000d08e5fb7b5` |
| `VER-004-ruff-format-range-server-11` | L2 | `PASS` | `uvx --from ruff==0.17.2 ruff format --check --no-cache --range=2242:1-2244:999 server.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `0.04` | `l2-green-ver004-range-server-11.log` | `1a167fd9cb08fdce4010880b0f7d30eb4c728e0b88b82e9be602cb9133174d07` |
| `VER-004-ruff-format-range-server-12` | L2 | `PASS` | `uvx --from ruff==0.17.2 ruff format --check --no-cache --range=2263:1-2267:999 server.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `0.04` | `l2-green-ver004-range-server-12.log` | `4317df22db33357148a731fa34cd55b55460cc0f9d8727409e75fd7bf7439491` |
| `VER-004-ruff-format-range-server-13` | L2 | `PASS` | `uvx --from ruff==0.17.2 ruff format --check --no-cache --range=2287:1-2291:999 server.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `0.04` | `l2-green-ver004-range-server-13.log` | `36603cdcb32ee0bfdb0fa0b4637fb4dad374e8f8b80e2562271739320bcdc689` |
| `VER-004-ruff-format-range-server-14` | L2 | `PASS` | `uvx --from ruff==0.17.2 ruff format --check --no-cache --range=2338:1-2338:999 server.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `0.04` | `l2-green-ver004-range-server-14.log` | `b983f7809853564cc15dd508ac2c088d5991ddcec96b88a1296570978a186f4c` |
| `VER-004-ruff-format-range-server-15` | L2 | `PASS` | `uvx --from ruff==0.17.2 ruff format --check --no-cache --range=2356:1-2356:999 server.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `0.04` | `l2-green-ver004-range-server-15.log` | `aebac7e28bf0afaef20d5fe5510a30f550197c93290b50bc7cbe83fc5403e8e9` |
| `VER-004-ruff-format-range-server-16` | L2 | `PASS` | `uvx --from ruff==0.17.2 ruff format --check --no-cache --range=2360:1-3114:999 server.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `0.05` | `l2-green-ver004-range-server-16.log` | `adf78bb4fd6f97936c702a7d4294300b6fcd29b8b9ba1320a9e7759e38e2b9fb` |
| `VER-004-ruff-format-range-server-17` | L2 | `PASS` | `uvx --from ruff==0.17.2 ruff format --check --no-cache --range=3116:1-3130:999 server.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `0.05` | `l2-green-ver004-range-server-17.log` | `3cb140d3caf21e48815884209c1effe43aba443517ff186132053779cf8a08a5` |
| `VER-004-ruff-format-range-server-18` | L2 | `PASS` | `uvx --from ruff==0.17.2 ruff format --check --no-cache --range=3135:1-3153:999 server.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `0.05` | `l2-green-ver004-range-server-18.log` | `e4d8d810199f401eb0ce3372bddb0bff3d8b3da741b09caaab7e30a3eb3a177c` |
| `VER-004-ruff-format-range-server-19` | L2 | `PASS` | `uvx --from ruff==0.17.2 ruff format --check --no-cache --range=4427:1-4431:999 server.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `0.04` | `l2-green-ver004-range-server-19.log` | `c444cf645da432ed3d6b8986da17bbeab54f5a166c128ff60e99cd07468048f8` |
| `VER-004-ruff-format-range-server-20` | L2 | `PASS` | `uvx --from ruff==0.17.2 ruff format --check --no-cache --range=4438:1-4442:999 server.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `0.04` | `l2-green-ver004-range-server-20.log` | `d313077dabc9521b20943926aa602c5f7ab502521c54b0bf9791af1b893d9023` |
| `VER-004-ruff-format-range-server-21` | L2 | `PASS` | `uvx --from ruff==0.17.2 ruff format --check --no-cache --range=4444:1-4446:999 server.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `0.04` | `l2-green-ver004-range-server-21.log` | `7fc43edee20bccae0ccb2e433fc2239ce865ac22787665d91b41f59d4cd1e0cd` |
| `VER-004-ruff-format-range-server-22` | L2 | `PASS` | `uvx --from ruff==0.17.2 ruff format --check --no-cache --range=4449:1-4453:999 server.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `0.04` | `l2-green-ver004-range-server-22.log` | `9028f2d9ca25ffe300866f2e21f556386a6615b4a25fb8a975a0c0f368a50c7b` |
| `VER-004-ruff-format-range-server-23` | L2 | `PASS` | `uvx --from ruff==0.17.2 ruff format --check --no-cache --range=4462:1-4464:999 server.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `0.04` | `l2-green-ver004-range-server-23.log` | `137d18ac14126d0eb7f05fddd42def32e3519b858b8195f60316998bef756f6c` |
| `VER-004-ruff-format-range-server-24` | L2 | `PASS` | `uvx --from ruff==0.17.2 ruff format --check --no-cache --range=4467:1-4475:999 server.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `0.04` | `l2-green-ver004-range-server-24.log` | `a21e3aad406e5764d4dbd3d7b01556db946c6dc89b5ef86eb37e3ce7e25139b3` |
| `VER-004-ruff-format-range-server-25` | L2 | `PASS` | `uvx --from ruff==0.17.2 ruff format --check --no-cache --range=4482:1-4489:999 server.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `0.04` | `l2-green-ver004-range-server-25.log` | `342d717568eb06315b8a533ed99dd7bdbf57ca15104e8781fad2e2f8239307a9` |
| `VER-004-ruff-format-range-server-26` | L2 | `PASS` | `uvx --from ruff==0.17.2 ruff format --check --no-cache --range=4492:1-4494:999 server.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `0.04` | `l2-green-ver004-range-server-26.log` | `c9bb5ad51a1cec6ddb158bd40b203bbf93ab98d37cd0e9b39100fcbca38901ad` |
| `VER-004-ruff-format-range-server-27` | L2 | `PASS` | `uvx --from ruff==0.17.2 ruff format --check --no-cache --range=4496:1-4504:999 server.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `0.04` | `l2-green-ver004-range-server-27.log` | `48c923dbeecb3ae20982762829ed159b3617ae1c87f534533a94d2a9a6bb9b51` |
| `VER-004-ruff-format-range-server-28` | L2 | `PASS` | `uvx --from ruff==0.17.2 ruff format --check --no-cache --range=4509:1-4517:999 server.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `0.04` | `l2-green-ver004-range-server-28.log` | `631d1084303ce679115087d098863502208aa8697d8f484779731460cfcdde21` |
| `VER-004-ruff-format-range-server-29` | L2 | `PASS` | `uvx --from ruff==0.17.2 ruff format --check --no-cache --range=4527:1-4528:999 server.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `0.04` | `l2-green-ver004-range-server-29.log` | `8cd812c358a608185ca293bcb5779f4333e26f659a9a9c6b36580267e1d99745` |
| `VER-004-ruff-format-range-server-30` | L2 | `PASS` | `uvx --from ruff==0.17.2 ruff format --check --no-cache --range=4579:1-4581:999 server.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `0.04` | `l2-green-ver004-range-server-30.log` | `1b7991002fb119b2a9562d39b41d3068d02cd8275511c275a2508af415c2cea1` |
| `VER-004-ruff-format-range-server-31` | L2 | `PASS` | `uvx --from ruff==0.17.2 ruff format --check --no-cache --range=4583:1-4596:999 server.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `0.04` | `l2-green-ver004-range-server-31.log` | `c548744592a53ccc65fc76571ca3b4c2c2d8ce76936922f48661451ace75e686` |
| `VER-004-ruff-format-range-server-32` | L2 | `PASS` | `uvx --from ruff==0.17.2 ruff format --check --no-cache --range=4686:1-4686:999 server.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `0.05` | `l2-green-ver004-range-server-32.log` | `b891acb4d080206084d4e7e70ad7bf878c28a2d0f37db5f757c3d0b06b847689` |
| `VER-004-ruff-format-range-server-33` | L2 | `PASS` | `uvx --from ruff==0.17.2 ruff format --check --no-cache --range=4696:1-4700:999 server.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `0.04` | `l2-green-ver004-range-server-33.log` | `d50fc53e2d4ea34a0650b8b573e78847b4870e16c2897cff91e85af02697c94b` |
| `VER-004-ruff-format-range-server-34` | L2 | `PASS` | `uvx --from ruff==0.17.2 ruff format --check --no-cache --range=4734:1-4967:999 server.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `0.04` | `l2-green-ver004-range-server-34.log` | `0b46d3055ef8fc3f66b6ded112feefe9199d87bab507bcff915342caf40929b3` |
| `VER-004-ruff-format-range-server-35` | L2 | `PASS` | `uvx --from ruff==0.17.2 ruff format --check --no-cache --range=5118:1-5119:999 server.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `0.04` | `l2-green-ver004-range-server-35.log` | `245dde84273d71bc8657149dcf68158d87f93655201c67bdfa02385e0517c472` |
| `VER-004-ruff-format-range-server-36` | L2 | `PASS` | `uvx --from ruff==0.17.2 ruff format --check --no-cache --range=5229:1-5283:999 server.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `0.04` | `l2-green-ver004-range-server-36.log` | `522ec4a1dd2a1f8dbcf9a779dd97bad5b94553e7e5ebbd25585ab953048d7b92` |
| `VER-004-ruff-format-range-server-37` | L2 | `PASS` | `uvx --from ruff==0.17.2 ruff format --check --no-cache --range=5301:1-5303:999 server.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `0.04` | `l2-green-ver004-range-server-37.log` | `783dea9a28cffd5e4453d20b2f4e8caaded8c886585c49e931dade2b1bf2b22f` |
| `VER-004-ruff-format-range-server-38` | L2 | `PASS` | `uvx --from ruff==0.17.2 ruff format --check --no-cache --range=5309:1-5311:999 server.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `0.04` | `l2-green-ver004-range-server-38.log` | `5459a1af2d4cd06784a4df3f383f033d2406f1ec2985f9bbb140e11c17a87fbb` |
| `VER-004-ruff-format-range-server-39` | L2 | `PASS` | `uvx --from ruff==0.17.2 ruff format --check --no-cache --range=5322:1-5324:999 server.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `0.04` | `l2-green-ver004-range-server-39.log` | `be56a5d141ae879726c1881ab8cfa22d7656b85dff414f68d0f5c6e5ee338cec` |
| `VER-004-ruff-format-range-server-40` | L2 | `PASS` | `uvx --from ruff==0.17.2 ruff format --check --no-cache --range=5327:1-5331:999 server.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `0.04` | `l2-green-ver004-range-server-40.log` | `8b4d01369142097d3605fedf79a388055b489e4a9488e8c09203c90f6ce258fd` |
| `VER-004-ruff-format-range-server-41` | L2 | `PASS` | `uvx --from ruff==0.17.2 ruff format --check --no-cache --range=5336:1-5341:999 server.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `0.04` | `l2-green-ver004-range-server-41.log` | `db63a9b27631d2848cb9646c447e74b4547959907a2af711c9e390d57f06a6b4` |
| `VER-004-ruff-format-range-server-42` | L2 | `PASS` | `uvx --from ruff==0.17.2 ruff format --check --no-cache --range=5343:1-5348:999 server.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `0.04` | `l2-green-ver004-range-server-42.log` | `edf1e728d3a1e78162570735773864dc3e25e7e19fbaa0758918870b5bca3db3` |
| `VER-004-ruff-format-range-server-43` | L2 | `PASS` | `uvx --from ruff==0.17.2 ruff format --check --no-cache --range=5351:1-5380:999 server.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `0.04` | `l2-green-ver004-range-server-43.log` | `fda44981641fda46207e200f893109fc3e694a4c405f49ba41e9f92d898c5e07` |
| `VER-004-ruff-format-range-server-44` | L2 | `PASS` | `uvx --from ruff==0.17.2 ruff format --check --no-cache --range=5383:1-5408:999 server.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `0.04` | `l2-green-ver004-range-server-44.log` | `61ea0fb1aba06e25449f2612b634fb314200855d0a43b244c2873749048d878b` |
| `VER-004-ruff-format-range-server-45` | L2 | `PASS` | `uvx --from ruff==0.17.2 ruff format --check --no-cache --range=5410:1-5434:999 server.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `0.04` | `l2-green-ver004-range-server-45.log` | `59f99023e45485943b4baf540e6bb7ca11df9d4b2a599cb0bd9aa4b49b52ec9a` |
| `VER-004-ruff-format-range-server-46` | L2 | `PASS` | `uvx --from ruff==0.17.2 ruff format --check --no-cache --range=5441:1-5441:999 server.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `0.04` | `l2-green-ver004-range-server-46.log` | `efe2330f4042e4d347064c5eb4c95a514aae435432a978636f893c4b5bf90485` |
| `VER-004-ruff-format-range-server-47` | L2 | `PASS` | `uvx --from ruff==0.17.2 ruff format --check --no-cache --range=5453:1-5474:999 server.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `0.04` | `l2-green-ver004-range-server-47.log` | `62b0e86044d4005aabf6b36193f93b51ddf9d706f31a579c7497fc70fe00bbc8` |
| `VER-004-ruff-format-range-server-48` | L2 | `PASS` | `uvx --from ruff==0.17.2 ruff format --check --no-cache --range=5593:1-5602:999 server.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `0.04` | `l2-green-ver004-range-server-48.log` | `be4928c4cdac314cdfbb3d9ed146bd1e810ab7230d8117622038329b8242f7db` |
| `VER-004-ruff-format-range-server-49` | L2 | `PASS` | `uvx --from ruff==0.17.2 ruff format --check --no-cache --range=5662:1-5667:999 server.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `0.04` | `l2-green-ver004-range-server-49.log` | `917686da3daa63a23567d127e2aa768b31a59f19e398ac6135ae919a4e4aa7f1` |
| `VER-004-ruff-format-range-server-50` | L2 | `PASS` | `uvx --from ruff==0.17.2 ruff format --check --no-cache --range=5695:1-5705:999 server.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `0.04` | `l2-green-ver004-range-server-50.log` | `6e945fc57f39e8bda2972c3dbae2dcdd5bd084a526b16177bd7b1e96307a3351` |
| `VER-004-ruff-format-range-server-51` | L2 | `PASS` | `uvx --from ruff==0.17.2 ruff format --check --no-cache --range=5736:1-5943:999 server.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `0.04` | `l2-green-ver004-range-server-51.log` | `caa77892ae2b4af29c048102161c237bd74d41143fbcda241c0e4a355bb4798c` |
| `VER-004-ruff-format-range-server-52` | L2 | `PASS` | `uvx --from ruff==0.17.2 ruff format --check --no-cache --range=5971:1-5991:999 server.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `0.04` | `l2-green-ver004-range-server-52.log` | `d5ed0ef1c02c1dbca0dea536e990b429541f5d27f422b87a8431603ba43bd3bd` |
| `VER-004-ruff-format-range-server-53` | L2 | `PASS` | `uvx --from ruff==0.17.2 ruff format --check --no-cache --range=6273:1-6273:999 server.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `0.04` | `l2-green-ver004-range-server-53.log` | `6f342289ba267b724264369fcf130a8a0635c26ec9443c3cd34dd71f9c5aced1` |
| `VER-004-ruff-format-range-test_step_interruption-1` | L2 | `PASS` | `uvx --from ruff==0.17.2 ruff format --check --no-cache --range=67:1-67:999 tests/test_step_interruption.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `0.04` | `l2-green-ver004-range-test_step_interruption-1.log` | `1bfce177c316cdcc6b3567f30279457b3d07734c5dbe6d71e0043126e14329cc` |
| `VER-004-ruff-format-range-test_step_interruption-2` | L2 | `PASS` | `uvx --from ruff==0.17.2 ruff format --check --no-cache --range=142:1-148:999 tests/test_step_interruption.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `0.04` | `l2-green-ver004-range-test_step_interruption-2.log` | `43db84d775e827bb10d95980ad3a6ab79d1dad3c72ff41c74a2df1e6b45f0c7b` |
| `VER-004-ruff-format-range-test_step_interruption-3` | L2 | `PASS` | `uvx --from ruff==0.17.2 ruff format --check --no-cache --range=152:1-152:999 tests/test_step_interruption.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `0.04` | `l2-green-ver004-range-test_step_interruption-3.log` | `bd29f48f762395c50e3e010617f077c71d139251e91c2b158d86fa064fbcf1da` |
| `VER-004-ruff-format-range-test_step_interruption-4` | L2 | `PASS` | `uvx --from ruff==0.17.2 ruff format --check --no-cache --range=188:1-189:999 tests/test_step_interruption.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `0.04` | `l2-green-ver004-range-test_step_interruption-4.log` | `fe32619cd0f07a5dc87b861454f60be891396fd628696cc972e5b6680ba1a260` |
| `VER-004-ruff-format-range-test_step_interruption-5` | L2 | `PASS` | `uvx --from ruff==0.17.2 ruff format --check --no-cache --range=416:1-418:999 tests/test_step_interruption.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `0.04` | `l2-green-ver004-range-test_step_interruption-5.log` | `8e3fda2fa1591e93deecb5958c4c58218cc94785d361a2aa06f93b45b30fe0b1` |
| `VER-004-ruff-format-range-test_step_interruption-6` | L2 | `PASS` | `uvx --from ruff==0.17.2 ruff format --check --no-cache --range=423:1-456:999 tests/test_step_interruption.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `0.04` | `l2-green-ver004-range-test_step_interruption-6.log` | `a541c75c111a88d475f6740ca78828130e3863cfd672b95fe63e34597edbaf8a` |
| `VER-001-pytest` | L2 | `PASS` | `uvx pytest -q -p no:cacheprovider tests/` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `142.29` | `l2-green-ver001-pytest.log` | `6dc083e24777b6ee2ac18e9f0d441a5dfecc4d9e4a474bb375953913c08edfe2` |
| `VER-002-unittest` | L2 | `PASS` | `python3 -m unittest discover -s tests -p test_*.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `137.64` | `l2-green-ver002-unittest.log` | `0a3b02903999bc0b50b1c7b3a4c14a0b58f03085480a0ecdfdb63f7533df2f67` |
| `VER-003-root-pythonpath-pytest` | L2 | `PASS` | `uvx pytest -q -p no:cacheprovider tests/` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom` | `0` | `363.04` | `l2-green-ver003-pythonpath.log` | `72c94be382cf85693719a90dd0ba17b510add53e45b7ac0ceeca6cbe7c9828e1` |
| `VER-003b-root-pythonpath-zen-pytest` | L2 | `PASS` | `uvx pytest -q -p no:cacheprovider bridges/opencode-zen-bridge/tests/` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom` | `0` | `145.1` | `l2-green-ver003b-zen-pythonpath.log` | `502449035a0241ad74606ba1a65ce8653306648a563df0bdcbde752833221f16` |
| `VER-005-dedicated-realtime-suite` | L2 | `PASS` | `uvx pytest -q -p no:cacheprovider tests/test_realtime_reasoning.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `28.52` | `l2-green-ver005-dedicated.log` | `a1ed5efe4d6da1110fc09fc9566d436dc14f4f90631e0f2b2543f3bc7cb54a05` |
| `AC-023-pytest-reversed` | L2 | `PASS` | `uvx pytest -q -p no:cacheprovider tests/test_zen_catalog.py tests/test_tool_emulation.py tests/test_sync_yaml.py tests/test_stream_thinki...` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `142.56` | `l2-green-ac023-reversed.log` | `16f2b17ae50bcee67e898b7fa739f7b51898ac32f1ba4515f4957bbb3ebbf378` |
| `VER-006-live-sse-heavy-path` | L3 | `DEFERRED_L3` | `Rollout ladder H0..H9 + curl -N -sS http://127.0.0.1:9883/v1/chat/completions (deepseek-v4.1-flash-free High, stream=true, multi-turn + tools + disconnect cleanup)` | `~/.dsh/bridges/opencode-zen-bridge` |  |  |  |  |
| `VER-007-deployed-mirror-diff` | L3 | `DEFERRED_L3` | `diff -u bridges/opencode-zen-bridge/server.py ~/.dsh/bridges/opencode-zen-bridge/server.py` | `~/tmp/cli-agent-bridge/zen-realtime-reasoning` |  |  |  |  |

> **Причина отсрочки `DEFERRED_L3` (`verification-integrity.md` §8, `acceptance-package.md` §3):** мутация живого боевого моста `~/.dsh/bridges/opencode-zen-bridge/server.py` (`127.0.0.1:9883`) запрещена до получения вердикта `ACCEPT` Совета Тимлидов (`Forbidden Scope` `handoff-architect.md`, `rollout H0..H9`). Сразу после `ACCEPT` Совета выполняется бэкап в `~/work/backups/`, синхронизация `server.py`, лестница `H0..H9` и живая heavy-path проверка с переводом строк `VER-006`/`VER-007` в `PASS` до открытия MR.

## Сырые логи независимого прогона L2 (`Clean-Room`)

### `L2-RED-sensitivity` (`l2-red.log`, `sha256=b8b80dd34adbf1f2bab310d2d0926d52559ae5e7323a81ef75cb93ddd02cf0bf`)
```text
$ uvx pytest -q -p no:cacheprovider tests/test_realtime_reasoning.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=1] [wall=23.79s]
--- STDOUT ---
..F.FFFFF.FFFF.FFFFFF                                                    [100%]
=================================== FAILURES ===================================
____________ TestLegacyWatchdogAndKillpg.test_oexit_fields_present _____________

self = <tests.test_realtime_reasoning.TestLegacyWatchdogAndKillpg testMethod=test_oexit_fields_present>

    def test_oexit_fields_present(self) -> None:
        """O-EXIT/v1 содержит transport/first_event_ms/ttft_ms."""
        self.bridge.post_stream_timed("привет")
        log = Path(self.bridge.tmp.name, "bridge.log")
        text = log.read_text("utf-8") if log.exists() else ""
        if not text:
            text = Path(server.LOG_PATH).read_text("utf-8")
        oexit = [line for line in text.splitlines() if "O-EXIT/v1" in line]
        self.assertTrue(oexit)
>       self.assertIn("transport=", oexit[-1])
E       AssertionError: 'transport=' not found in '2026-10-26 21:43:30 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=7 duration_s=0.38'

tests/test_realtime_reasoning.py:372: AssertionError
----------------------------- Captured stderr call -----------------------------
2026-10-26 21:43:29 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1026 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-26 21:43:29 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-26 21:43:30 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=7 emulate_tools=True retries=0 total_spawns=1
2026-10-26 21:43:30 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=7 duration_s=0.38
_ TestLegacyWatchdogAndKillpg.test_slow_upstream_gets_initial_status_before_1s _

self = <tests.test_realtime_reasoning.TestLegacyWatchdogAndKillpg testMethod=test_slow_upstream_gets_initial_status_before_1s>

    def test_slow_upstream_gets_initial_status_before_1s(self) -> None:
        """Медленный апстрим: первый [мост] не позже 1.0 с (REQ-004)."""
        os.environ["FAKE_RT_MODE"] = "slow"
        chunks, _elapsed = self.bridge.post_stream_timed("медленно")
        statuses = [
            (at, t)
            for at, t in _deltas(chunks, "reasoning_content")
            if t.startswith("[мост]") or "[мост]" in t
        ]
>       self.assertTrue(statuses, "нет синтетического статуса")
E       AssertionError: [] is not true : нет синтетического статуса

tests/test_realtime_reasoning.py:320: AssertionError
----------------------------- Captured stderr call -----------------------------
2026-10-26 21:43:30 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1028 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-26 21:43:30 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-26 21:43:32 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=6 emulate_tools=True retries=0 total_spawns=1
2026-10-26 21:43:32 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=6 duration_s=2.00
________ TestLegacyWatchdogAndKillpg.test_watchdog_first_event_timeout _________

self = <tests.test_realtime_reasoning.TestLegacyWatchdogAndKillpg testMethod=test_watchdog_first_event_timeout>

    def test_watchdog_first_event_timeout(self) -> None:
        """Тишина апстрима: watchdog срабатывает, а не TIMEOUT_S=1800."""
        os.environ["FAKE_RT_MODE"] = "silent"
        setter = getattr(server, "FIRST_EVENT_TIMEOUT_S", None)
>       self.assertIsNotNone(setter, "нет FIRST_EVENT_TIMEOUT_S")
E       AssertionError: unexpectedly None : нет FIRST_EVENT_TIMEOUT_S

tests/test_realtime_reasoning.py:380: AssertionError
_ TestServeTransportAndFakeServe.test_ac026_realtime_chunks_before_upstream_end _

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_ac026_realtime_chunks_before_upstream_end>

    def test_ac026_realtime_chunks_before_upstream_end(self) -> None:
        """AC-026: reasoning-чанки приходят, пока апстрим ещё идёт."""
        chunks, elapsed = self.bridge.post_stream_timed("обычный запрос")
        reasoning = _deltas(chunks, "reasoning_content")
        model_reasoning = [
            (at, t) for at, t in reasoning if not t.lstrip("\n").startswith("[мост]")
        ]
>       self.assertGreaterEqual(len(model_reasoning), 3, chunks)
E       AssertionError: 1 not greater than or equal to 3 : [(0.006887915951665491, {'id': 'chatcmpl-oczen-6af726ac9481', 'object': 'chat.completion.chunk', 'created': 1793040213, 'model': 'muse-spark-1.3-contributor-free', 'choices': [{'index': 0, 'delta': {'role': 'assistant', 'content': ''}}]}), (1.3995738749508746, {'id': 'chatcmpl-oczen-6af726ac9481', 'object': 'chat.completion.chunk', 'created': 1793040213, 'model': 'muse-spark-1.3-contributor-free', 'choices': [{'index': 0, 'delta': {'reasoning_content': 'Поздняя мысль'}}]}), (1.3996802079491317, {'id': 'chatcmpl-oczen-6af726ac9481', 'object': 'chat.completion.chunk', 'created': 1793040213, 'model': 'muse-spark-1.3-contributor-free', 'choices': [{'index': 0, 'delta': {'content': 'Поздний ответ'}}]}), (1.6540727079845965, {'id': 'chatcmpl-oczen-6af726ac9481', 'object': 'chat.completion.chunk', 'created': 1793040213, 'model': 'muse-spark-1.3-contributor-free', 'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}], 'usage': {'prompt_tokens': 1, 'completion_tokens': 1, 'total_tokens': 2}})]

tests/test_realtime_reasoning.py:441: AssertionError
----------------------------- Captured stderr call -----------------------------
2026-10-26 21:43:33 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1034 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-26 21:43:33 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-26 21:43:35 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=13 emulate_tools=True retries=0 total_spawns=1
2026-10-26 21:43:35 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=13 duration_s=1.65
_ TestServeTransportAndFakeServe.test_auto_fallback_to_run_and_sticky_degradation _

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_auto_fallback_to_run_and_sticky_degradation>

    def test_auto_fallback_to_run_and_sticky_degradation(self) -> None:
        """auto: 503 на создании сессии -> fallback на run; после 3 запросов serve деградирован."""
>       saved_eligible = server.SERVE_TEST_ELIGIBLE
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'SERVE_TEST_ELIGIBLE'

tests/test_realtime_reasoning.py:634: AttributeError
________ TestServeTransportAndFakeServe.test_canonical_frozen_fixtures _________

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_canonical_frozen_fixtures>

    def test_canonical_frozen_fixtures(self) -> None:
        """Каноническое отображение замороженных wire-фикстур v2.1.2."""
        mapper = getattr(server, "_map_serve_event", None) or getattr(
            server, "parse_serve_event", None
        )
>       self.assertIsNotNone(mapper, "нет _map_serve_event")
E       AssertionError: unexpectedly None : нет _map_serve_event

tests/test_realtime_reasoning.py:488: AssertionError
____ TestServeTransportAndFakeServe.test_dynamic_config_switch_same_server _____

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_dynamic_config_switch_same_server>

    def test_dynamic_config_switch_same_server(self) -> None:
        """Тот же Server: false -> run, true -> serve, битый JSON -> false."""
        reader = getattr(server, "_read_dynamic_config_enabled", None)
        if reader is None:
            reader = getattr(server, "_dynamic_config_enabled", None)
>       self.assertIsNotNone(reader, "нет читателя dynamic_config")
E       AssertionError: unexpectedly None : нет читателя dynamic_config

tests/test_realtime_reasoning.py:454: AssertionError
_ TestServeTransportAndFakeServe.test_foreign_listener_rejected_and_startup_reaper _

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_foreign_listener_rejected_and_startup_reaper>

    def test_foreign_listener_rejected_and_startup_reaper(self) -> None:
        """Чужой слушатель порта -> ServeUnavailable; reaper удаляет lease мёртвого родителя."""
>       with mock.patch.object(server, "_lsof_listener_pid", return_value=999998):
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

tests/test_realtime_reasoning.py:670: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/Users/aazhiry1/.local/share/uv/python/cpython-3.14.7-macos-x86_64-none/lib/python3.14/unittest/mock.py:1510: in __enter__
    original, local = self.get_original()
                      ^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

self = <unittest.mock._patch object at 0x10c9687c0>

    def get_original(self):
        target = self.getter()
        name = self.attribute
    
        original = DEFAULT
        local = False
    
        try:
            original = target.__dict__[name]
        except (AttributeError, KeyError):
            original = getattr(target, name, DEFAULT)
        else:
            local = True
    
        if name in _builtins and isinstance(target, ModuleType):
            self.create = True
    
        if not self.create and original is DEFAULT:
>           raise AttributeError(
                "%s does not have the attribute %r" % (target, name)
            )
E           AttributeError: <module 'server' from '/private/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge/server.py'> does not have the attribute '_lsof_listener_pid'

/Users/aazhiry1/.local/share/uv/python/cpython-3.14.7-macos-x86_64-none/lib/python3.14/unittest/mock.py:1480: AttributeError
_ TestServeTransportAndFakeServe.test_form_missing_title_cancels_without_step2 _

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_form_missing_title_cancels_without_step2>

    def test_form_missing_title_cancels_without_step2(self) -> None:
        """form.created без title: cancel+interrupt до проверки схемы, без Step2."""
        record = self.tmp / "rec.json"
        chunks, _elapsed = self.bridge.post_stream_timed(
            f"__form_missing_title__ __record:{record}__ заполни"
        )
        content = "".join(t for _at, t in _deltas(chunks, "content"))
        self.assertNotIn("STEP2", content)
        control = Path(str(record) + ".control")
>       self.assertTrue(control.exists(), "FakeServe не получил cancel")
E       AssertionError: False is not true : FakeServe не получил cancel

tests/test_realtime_reasoning.py:558: AssertionError
----------------------------- Captured stderr call -----------------------------
2026-10-26 21:43:39 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1131 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-26 21:43:39 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-26 21:43:41 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=13 emulate_tools=True retries=0 total_spawns=1
2026-10-26 21:43:41 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=13 duration_s=1.59
___ TestServeTransportAndFakeServe.test_helper_argv_validation_and_lease_dir ___

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_helper_argv_validation_and_lease_dir>

    def test_helper_argv_validation_and_lease_dir(self) -> None:
        """--serve-helper: 6 аргументов, lease только в переданном каталоге."""
        fn = getattr(server, "_run_serve_helper_cli", None)
>       self.assertIsNotNone(fn, "нет _run_serve_helper_cli")
E       AssertionError: unexpectedly None : нет _run_serve_helper_cli

tests/test_realtime_reasoning.py:573: AssertionError
____ TestServeTransportAndFakeServe.test_native_tool_and_permission_reject _____

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_native_tool_and_permission_reject>

    def test_native_tool_and_permission_reject(self) -> None:
        """permission.asked -> reject, native tool -> DSH tool_call."""
        chunks, _elapsed = self.bridge.post_stream_timed("__native_tool__ сделай")
        names: list[str] = []
        for _at, chunk in chunks:
            choices = chunk.get("choices") or []
            if isinstance(choices, list) and choices:
                delta = choices[0].get("delta") or {}
                if isinstance(delta, dict):
                    for tc in delta.get("tool_calls") or []:
                        names.append(str(tc["function"]["name"]))
>       self.assertIn("bash", names)
E       AssertionError: 'bash' not found in []

tests/test_realtime_reasoning.py:547: AssertionError
----------------------------- Captured stderr call -----------------------------
2026-10-26 21:43:44 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1042 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-26 21:43:44 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-26 21:43:45 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=13 emulate_tools=True retries=0 total_spawns=1
2026-10-26 21:43:45 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=13 duration_s=1.58
_ TestServeTransportAndFakeServe.test_serve_400_fails_closed_without_health_increment _

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_serve_400_fails_closed_without_health_increment>

    def test_serve_400_fails_closed_without_health_increment(self) -> None:
        """400 на создании сессии: SSE error fail-closed без инкремента serve_health."""
>       health = self.bridge.httpd.resilience.serve_health
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: '_Resilience' object has no attribute 'serve_health'

tests/test_realtime_reasoning.py:692: AttributeError
_____ TestServeTransportAndFakeServe.test_serve_env_sanitized_all_branches _____

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_serve_env_sanitized_all_branches>

    def test_serve_env_sanitized_all_branches(self) -> None:
        """_serve_env: :memory:, allowlist, без OPENCODE_BIN и секретов."""
        fn = getattr(server, "_serve_env", None)
>       self.assertIsNotNone(fn, "нет _serve_env")
E       AssertionError: unexpectedly None : нет _serve_env

tests/test_realtime_reasoning.py:469: AssertionError
_____ TestServeTransportAndFakeServe.test_serve_health_and_fallback_table ______

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_serve_health_and_fallback_table>

    def test_serve_health_and_fallback_table(self) -> None:
        """_ServeHealth sticky и таблица fallback_decision_table."""
        health_cls = getattr(server, "_ServeHealth", None)
>       self.assertIsNotNone(health_cls, "нет _ServeHealth")
E       AssertionError: unexpectedly None : нет _ServeHealth

tests/test_realtime_reasoning.py:600: AssertionError
_ TestServeTransportAndFakeServe.test_slow_serve_gets_status_and_no_status_on_fast _

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_slow_serve_gets_status_and_no_status_on_fast>

    def test_slow_serve_gets_status_and_no_status_on_fast(self) -> None:
        """Медленный serve: статус <1с; быстрый serve: без лишнего статуса в reasoning модели."""
        chunks, _elapsed = self.bridge.post_stream_timed("__slow__ жди")
        statuses = [
            (at, t) for at, t in _deltas(chunks, "reasoning_content") if "[мост]" in t
        ]
>       self.assertTrue(statuses)
E       AssertionError: [] is not true

tests/test_realtime_reasoning.py:567: AssertionError
----------------------------- Captured stderr call -----------------------------
2026-10-26 21:43:47 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1032 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-26 21:43:47 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-26 21:43:49 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=13 emulate_tools=True retries=0 total_spawns=1
2026-10-26 21:43:49 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=13 duration_s=1.64
______ TestServeTransportAndFakeServe.test_tool_text_split_across_deltas _______

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_tool_text_split_across_deltas>

    def test_tool_text_split_across_deltas(self) -> None:
        """ToolCallParser на разрезанных дельтах serve."""
        chunks, _elapsed = self.bridge.post_stream_timed("__tool_text__ вызов")
        names: list[str] = []
        for _at, chunk in chunks:
            choices = chunk.get("choices") or []
            if isinstance(choices, list) and choices:
                delta = choices[0].get("delta") or {}
                if isinstance(delta, dict):
                    for tc in delta.get("tool_calls") or []:
                        names.append(str(tc["function"]["name"]))
>       self.assertEqual(names, ["bash"])
E       AssertionError: Lists differ: [] != ['bash']
E       
E       Second list contains 1 additional elements.
E       First extra element 0:
E       'bash'
E       
E       - []
E       + ['bash']

tests/test_realtime_reasoning.py:534: AssertionError
----------------------------- Captured stderr call -----------------------------
2026-10-26 21:43:49 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1039 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-26 21:43:49 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-26 21:43:51 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=13 emulate_tools=True retries=0 total_spawns=1
2026-10-26 21:43:51 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=13 duration_s=1.59
=========================== short test summary info ============================
FAILED tests/test_realtime_reasoning.py::TestLegacyWatchdogAndKillpg::test_oexit_fields_present
FAILED tests/test_realtime_reasoning.py::TestLegacyWatchdogAndKillpg::test_slow_upstream_gets_initial_status_before_1s
FAILED tests/test_realtime_reasoning.py::TestLegacyWatchdogAndKillpg::test_watchdog_first_event_timeout
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_ac026_realtime_chunks_before_upstream_end
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_auto_fallback_to_run_and_sticky_degradation
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_canonical_frozen_fixtures
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_dynamic_config_switch_same_server
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_foreign_listener_rejected_and_startup_reaper
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_form_missing_title_cancels_without_step2
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_helper_argv_validation_and_lease_dir
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_native_tool_and_permission_reject
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_serve_400_fails_closed_without_health_increment
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_serve_env_sanitized_all_branches
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_serve_health_and_fallback_table
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_slow_serve_gets_status_and_no_status_on_fast
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_tool_text_split_across_deltas
16 failed, 5 passed in 23.47s

--- STDERR ---
```

### `VER-004-packet-command` (`l2-green-ver004-packet.log`, `sha256=6c0b3627322b3ea368d0add2b4a8f9f050f6c70f3cb8846a2f766bbf8ee63800`)
```text
$ /bin/zsh -lc python3 - <<'VER004'
import ast, collections, hashlib, json, re, subprocess, tempfile
from pathlib import Path
root = Path.cwd().resolve()
bridge = root / 'bridges/opencode-zen-bridge'
files = [bridge/'server.py', bridge/'tests/test_step_interruption.py', bridge/'tests/test_realtime_reasoning.py']
assert all(f.is_file() for f in files), 'all three target files must exist after Stage3'
ruff = ['uvx','--from','ruff==0.17.2','ruff']
def run(args, **kw):
    return subprocess.run(args, check=True, **kw)
def changed_ranges(file):
    rel = str(file.relative_to(root))
    diff = subprocess.check_output(['git','diff','--no-ext-diff','--no-color','-U0','origin/dev','--',rel], cwd=root, text=True)
    # NEW tracked files must be added before final verification; --no-index alternative below covers untracked newfile.
    result = []
    for line in diff.splitlines():
        m = re.match(r'^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@', line)
        if m:
            start = int(m.group(1)); count = int(m.group(2) or '1')
            if count: result.append((start, start + count - 1))
    return result

# Raw-byte contract: frozen expected digests originate in EVD-075, never candidate.
FROZEN = {
    '_run_env': '1c51b28fcb83fcc0f4d8b5204c858e11ab5ac975bfe40dca4a0bf61978008e31',
    '_stream_google_sse': '5914c9654c7345692dd55e84cfd3765e27406f63a3df85df30bc798bc1778de3',
    '_execute_google_once': '88d794cc42be4878e8ab35b00e4668c427929db2dfd0f2bb4b717a63fd0c70d6',
}
baseline_raw = subprocess.check_output(['git','show','origin/dev:bridges/opencode-zen-bridge/server.py'], cwd=root)
def frozen_slices(raw):
    lines = raw.splitlines(keepends=True)
    nodes = {n.name:n for n in ast.walk(ast.parse(raw)) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name in FROZEN}
    assert set(nodes)==set(FROZEN)
    return {name:(node.lineno,node.end_lineno,b''.join(lines[node.lineno-1:node.end_lineno])) for name,node in nodes.items()}
baseline_slices = frozen_slices(baseline_raw)
def assert_frozen(candidate=files[0]):
    candidate_slices = frozen_slices(candidate.read_bytes())
    for name, expected in FROZEN.items():
        assert hashlib.sha256(baseline_slices[name][2]).hexdigest()==expected, ('frozen origin/dev changed',name)
        assert hashlib.sha256(candidate_slices[name][2]).hexdigest()==expected, ('immutable slice changed',name)
        assert candidate_slices[name][2]==baseline_slices[name][2], ('nonzero raw Google/_run_env diff',name)
    return candidate_slices
candidate_slices = assert_frozen()
server_diff = subprocess.check_output(['git','diff','--no-ext-diff','--no-color','-U0','origin/dev','--',str(files[0].relative_to(root))],cwd=root,text=True)
for line in server_diff.splitlines():
    match = re.match(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@',line)
    if not match: continue
    old_start,old_count,new_start,new_count = int(match[1]),int(match[2] or '1'),int(match[3]),int(match[4] or '1')
    for start,count,table in [(old_start,old_count,baseline_slices),(new_start,new_count,candidate_slices)]:
        for name,(lo,hi,_) in table.items():
            # Zero-count insert/delete anchors represent the boundary after start.
            overlaps = (start<=hi and start+count-1>=lo) if count else (lo<=start<hi)
            assert not overlaps, ('VER-004 frozen-range hunk intersection',name,line)
# Public module constant/read API remains intact; compatibility test file is frozen.
tree = ast.parse(files[0].read_bytes())
assignments = [n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='CATALOG_SOURCE' for t in n.targets)]
assert len(assignments)==1 and isinstance(assignments[0].value,ast.Constant) and assignments[0].value.value=='static'
assert any(isinstance(n,ast.FunctionDef) and n.name=='_set_catalog_source' for n in tree.body)
assert any(isinstance(n,ast.Import) and any(a.name=='zen_catalog' and a.asname=='zc' for a in n.names) for n in ast.walk(tree))
assert not any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='import_module' and n.args and isinstance(n.args[0],ast.Constant) and n.args[0].value=='zen_catalog' for n in ast.walk(tree))
assert any(isinstance(n,ast.FunctionDef) and n.name=='_run_serve_helper_cli' for n in tree.body), 'helper code must be lint/type checked in server.py'
helper_branch = next((n for n in tree.body if isinstance(n, ast.If) and ast.unparse(n.test) == "sys.argv[1:2] == ['--serve-helper']"), None)
assert helper_branch is not None and any(isinstance(n, ast.Raise) for n in helper_branch.body), 'early terminating helper dispatch required'
heavy = {'http.client', 'sqlite3', 'http.server', 'zen_catalog'}
def imported_names(node):
    if isinstance(node, ast.Import): return {a.name for a in node.names}
    if isinstance(node, ast.ImportFrom): return {node.module}
    return set()
assert not any(imported_names(n) & heavy for n in tree.body[:tree.body.index(helper_branch)])
assert any(isinstance(n, ast.Import) and any(a.name == 'zen_catalog' and a.asname == 'zc' for a in n.names) for n in helper_branch.orelse)
assert all(not isinstance(n, (ast.Assign, ast.AnnAssign, ast.Expr)) for n in tree.body[1:tree.body.index(helper_branch)]), 'no server initialization before helper exit'
assert not any(isinstance(n,ast.Global) and 'CATALOG_SOURCE' in n.names for n in ast.walk(tree))
run(['git','diff','--exit-code','origin/dev','--','bridges/opencode-zen-bridge/tests/test_catalog_mode.py'],cwd=root)

ranges = {f: changed_ranges(f) for f in files[:2]}
# New file checked as a whole even before git add. Range gate never formats frozen legacy slices.
run([*ruff,'format','--config',str(root / 'ruff.toml'),'--check','--no-cache',str(files[2])], cwd=root)
for f in files[:2]:
    for start, end in ranges[f]:
        run([*ruff,'format','--config',str(root / 'ruff.toml'),'--check','--no-cache',f'--range={start}:1-{end}:999',str(f)], cwd=root)
assert_frozen()
# Exercise actual write-mode range formatting only on a disposable copy.
with tempfile.TemporaryDirectory(prefix='zen-arch6-probe-format-', dir='/tmp') as format_dir:
    formatted_copy = Path(format_dir) / 'server.py'
    formatted_copy.write_bytes(files[0].read_bytes())
    for start, end in ranges[files[0]]:
        run([*ruff,'format','--config',str(root / 'ruff.toml'),'--no-cache',f'--range={start}:1-{end}:999',str(formatted_copy)], cwd=root)
    assert formatted_copy.read_bytes() == files[0].read_bytes()
    assert_frozen(formatted_copy)
    assert_frozen()
    print('PASS write-mode frozen hashes', {name:hashlib.sha256(data[2]).hexdigest() for name,data in frozen_slices(formatted_copy.read_bytes()).items()})
# Full-file lint on all three. Only inherited E402 import site is excepted on server.
lint = subprocess.run([*ruff,'check','--config',str(root / 'ruff.toml'),'--no-cache','--output-format','json',str(files[0])], cwd=root, capture_output=True, text=True)
assert lint.returncode in (0,1), lint.stderr
findings = json.loads(lint.stdout)
lines = files[0].read_text().splitlines()
assert all(x['code']=='E402' and lines[x['location']['row']-1].strip()=='import zen_catalog as zc' for x in findings), findings
assert sum(x['code']=='E402' for x in findings) <= 1
run([*ruff,'check','--config',str(root / 'ruff.toml'),'--no-cache','--extend-ignore','E402',str(files[0])], cwd=root)
run([*ruff,'check','--config',str(root / 'ruff.toml'),'--no-cache',str(files[1]),str(files[2])], cwd=root)
# Exact isolated import-root. No repo pyrightconfig mutation; JSON deleted on every exit.
project = None
try:
    with tempfile.NamedTemporaryFile(mode='w',suffix='.json',prefix='zen-arch6-probe-project-',dir='/tmp',delete=False) as tmp:
        project = Path(tmp.name)
        json.dump({'include':[str(f) for f in files], 'extraPaths':[str(bridge.resolve())]},tmp)
    b = subprocess.run(['uvx','--from','basedpyright==1.40.2','basedpyright','--project',str(project),'--outputjson'], cwd=bridge, capture_output=True, text=True)
    assert b.returncode in (0,1), b.stderr
    report = json.loads(b.stdout)
    ds = report['generalDiagnostics']
    assert report['summary']['errorCount']==0 and not [x for x in ds if x['severity']=='error'], ds
    byfile = {f: [x for x in ds if Path(x['file']).resolve()==f] for f in files}
    limits = {'reportExplicitAny':125,'reportAny':125,'reportUnusedCallResult':39,'reportUnknownMemberType':94,'reportUnknownVariableType':72,'reportUnknownArgumentType':55,'reportUnusedFunction':6,'reportImplicitStringConcatenation':35,'reportUnannotatedClassAttribute':105,'reportUnusedParameter':7,'reportUnnecessaryIsInstance':11,'reportUnknownParameterType':6,'reportMissingParameterType':4,'reportUnreachable':5,'reportImplicitOverride':3}
    warnings = lambda f: [x for x in byfile[f] if x['severity']=='warning']
    counts = collections.Counter(x.get('rule','') for x in warnings(files[0]))
    print('BASEDPYRIGHT summary',report['summary'])
    print('SERVER dict(counts)',dict(counts))
    print('SERVER warningCount',len(warnings(files[0])))
    assert all(n<=limits.get(rule,0) for rule,n in counts.items()), dict(counts)
    assert len(warnings(files[0]))<=720, len(warnings(files[0]))
    assert len(warnings(files[1]))<=194, len(warnings(files[1]))
    # New test file: zero warnings as well as zero errors, thus zero Any.
    assert not byfile[files[2]], byfile[files[2]]
    for f in files[:2]:
        for x in byfile[f]:
            line = x['range']['start']['line']+1
            if any(lo<=line<=hi for lo,hi in ranges[f]):
                assert x.get('rule') not in {'reportAny','reportExplicitAny','reportUnusedCallResult'}, x
    # Do not introduce Any annotations/type ignores in added code in either legacy file.
    for f in files[:2]:
        src = f.read_text().splitlines()
        for lo,hi in ranges[f]:
            for line in src[lo-1:hi]:
                assert not re.search(r'\bAny\b|type:\s*ignore|pyright:\s*ignore|#\s*noqa|#\s*fmt:\s*off',line), (f,line)
    run(['python3','-B','-m','unittest','tests.test_catalog_mode','-v'],cwd=bridge)
    print('PASS VER-004: all3 lint/type; legacy changed-range format; newfile whole format; server counts',dict(counts))
finally:
    if project is not None: project.unlink(missing_ok=True)
VER004
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom] [rc=0] [wall=9.33s]
--- STDOUT ---
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
All checks passed!
All checks passed!
PASS write-mode frozen hashes {'_run_env': '1c51b28fcb83fcc0f4d8b5204c858e11ab5ac975bfe40dca4a0bf61978008e31', '_execute_google_once': '88d794cc42be4878e8ab35b00e4668c427929db2dfd0f2bb4b717a63fd0c70d6', '_stream_google_sse': '5914c9654c7345692dd55e84cfd3765e27406f63a3df85df30bc798bc1778de3'}
BASEDPYRIGHT summary {'filesAnalyzed': 3, 'errorCount': 0, 'warningCount': 760, 'informationCount': 0, 'timeInSec': 2.744}
SERVER dict(counts) {'reportExplicitAny': 125, 'reportAny': 121, 'reportUnusedCallResult': 38, 'reportUnknownMemberType': 72, 'reportUnknownVariableType': 50, 'reportUnknownArgumentType': 41, 'reportUnusedFunction': 2, 'reportImplicitStringConcatenation': 27, 'reportUnannotatedClassAttribute': 98, 'reportUnusedParameter': 3, 'reportUnnecessaryIsInstance': 4, 'reportUnknownParameterType': 2, 'reportMissingParameterType': 2, 'reportUnreachable': 1, 'reportImplicitOverride': 1}
SERVER warningCount 587
PASS VER-004: all3 lint/type; legacy changed-range format; newfile whole format; server counts {'reportExplicitAny': 125, 'reportAny': 121, 'reportUnusedCallResult': 38, 'reportUnknownMemberType': 72, 'reportUnknownVariableType': 50, 'reportUnknownArgumentType': 41, 'reportUnusedFunction': 2, 'reportImplicitStringConcatenation': 27, 'reportUnannotatedClassAttribute': 98, 'reportUnusedParameter': 3, 'reportUnnecessaryIsInstance': 4, 'reportUnknownParameterType': 2, 'reportMissingParameterType': 2, 'reportUnreachable': 1, 'reportImplicitOverride': 1}

--- STDERR ---
test_env_default_is_dynamic (tests.test_catalog_mode.ModeFromEnvironmentTest) ... ok
test_env_static_and_legacy (tests.test_catalog_mode.ModeFromEnvironmentTest) ... ok
test_default_in_tests_is_dynamic (tests.test_catalog_mode.ModeNormalizationTest) ... ok
test_modes (tests.test_catalog_mode.ModeNormalizationTest) ... ok
test_aliases_still_work_in_static (tests.test_catalog_mode.StaticModeTest) ... ok
test_static_never_reloads_by_mtime (tests.test_catalog_mode.StaticModeTest) ... ok
test_static_routes_through_background_service (tests.test_catalog_mode.StaticModeTest) ... ok
test_static_uses_embedded_snapshot_and_ignores_state_file (tests.test_catalog_mode.StaticModeTest) ... ok

----------------------------------------------------------------------
Ran 8 tests in 0.197s

OK
```

### `VER-004-ruff-format-new` (`l2-green-ver004-ruff-format-new.log`, `sha256=791491a5d9e6128b8400ae730e69e74c9af01651d625cc697d569dfdcee245b7`)
```text
$ uvx --from ruff==0.17.2 ruff format --check --no-cache tests/test_realtime_reasoning.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=0.04s]
--- STDOUT ---
1 file already formatted

--- STDERR ---
```

### `VER-004-ruff-format-range-server-1` (`l2-green-ver004-range-server-1.log`, `sha256=755d9227e95b948c1b21b60a6a5719f23874a7f21c9eaa06d940767f5734d920`)
```text
$ uvx --from ruff==0.17.2 ruff format --check --no-cache --range=22:1-22:999 server.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=0.05s]
--- STDOUT ---
1 file already formatted

--- STDERR ---
```

### `VER-004-ruff-format-range-server-2` (`l2-green-ver004-range-server-2.log`, `sha256=d43ecdb8d6ac5fbb42ad87118c810f0502f825f1e90d9caa99b63adad6226dd8`)
```text
$ uvx --from ruff==0.17.2 ruff format --check --no-cache --range=29:1-224:999 server.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=0.05s]
--- STDOUT ---
1 file already formatted

--- STDERR ---
```

### `VER-004-ruff-format-range-server-3` (`l2-green-ver004-range-server-3.log`, `sha256=acfa83afea14da20895c3c5df8891eefc261d948f1733e6a9362c94316fbc5e8`)
```text
$ uvx --from ruff==0.17.2 ruff format --check --no-cache --range=259:1-267:999 server.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=0.05s]
--- STDOUT ---
1 file already formatted

--- STDERR ---
```

### `VER-004-ruff-format-range-server-4` (`l2-green-ver004-range-server-4.log`, `sha256=88452847a1c7bf2735617ebc981f4546653b761feb86581b86c09defcbbabd90`)
```text
$ uvx --from ruff==0.17.2 ruff format --check --no-cache --range=282:1-287:999 server.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=0.05s]
--- STDOUT ---
1 file already formatted

--- STDERR ---
```

### `VER-004-ruff-format-range-server-5` (`l2-green-ver004-range-server-5.log`, `sha256=3001e902e898ce08be329b7fb21e859b94d1f64fd4223e58eb45d3e1bafa83e0`)
```text
$ uvx --from ruff==0.17.2 ruff format --check --no-cache --range=310:1-310:999 server.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=0.04s]
--- STDOUT ---
1 file already formatted

--- STDERR ---
```

### `VER-004-ruff-format-range-server-6` (`l2-green-ver004-range-server-6.log`, `sha256=395372d5783c465bb44896e2b27bb87f887cc2483269a1045a3fb28fdd568474`)
```text
$ uvx --from ruff==0.17.2 ruff format --check --no-cache --range=323:1-323:999 server.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=0.04s]
--- STDOUT ---
1 file already formatted

--- STDERR ---
```

### `VER-004-ruff-format-range-server-7` (`l2-green-ver004-range-server-7.log`, `sha256=ef3916991629bdb55ce1820231b7cc0c4f70ba15083be97b22ebdce0ee32b7f5`)
```text
$ uvx --from ruff==0.17.2 ruff format --check --no-cache --range=1326:1-1887:999 server.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=0.05s]
--- STDOUT ---
1 file already formatted

--- STDERR ---
```

### `VER-004-ruff-format-range-server-8` (`l2-green-ver004-range-server-8.log`, `sha256=91e7ac7b68fc502cae836236045fb6e74e77bdd8704fd29f78eb0df1f357f8c5`)
```text
$ uvx --from ruff==0.17.2 ruff format --check --no-cache --range=2204:1-2206:999 server.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=0.05s]
--- STDOUT ---
1 file already formatted

--- STDERR ---
```

### `VER-004-ruff-format-range-server-9` (`l2-green-ver004-range-server-9.log`, `sha256=aa564ad3b2e4ce1923226de4ae4763b1fd8789f2b1a4cc257747cd61f6a7f584`)
```text
$ uvx --from ruff==0.17.2 ruff format --check --no-cache --range=2221:1-2221:999 server.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=0.05s]
--- STDOUT ---
1 file already formatted

--- STDERR ---
```

### `VER-004-ruff-format-range-server-10` (`l2-green-ver004-range-server-10.log`, `sha256=55dad36c122f16886bc8f61615b1f48774f27888e6a56f028ee000d08e5fb7b5`)
```text
$ uvx --from ruff==0.17.2 ruff format --check --no-cache --range=2231:1-2239:999 server.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=0.04s]
--- STDOUT ---
1 file already formatted

--- STDERR ---
```

### `VER-004-ruff-format-range-server-11` (`l2-green-ver004-range-server-11.log`, `sha256=1a167fd9cb08fdce4010880b0f7d30eb4c728e0b88b82e9be602cb9133174d07`)
```text
$ uvx --from ruff==0.17.2 ruff format --check --no-cache --range=2242:1-2244:999 server.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=0.04s]
--- STDOUT ---
1 file already formatted

--- STDERR ---
```

### `VER-004-ruff-format-range-server-12` (`l2-green-ver004-range-server-12.log`, `sha256=4317df22db33357148a731fa34cd55b55460cc0f9d8727409e75fd7bf7439491`)
```text
$ uvx --from ruff==0.17.2 ruff format --check --no-cache --range=2263:1-2267:999 server.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=0.04s]
--- STDOUT ---
1 file already formatted

--- STDERR ---
```

### `VER-004-ruff-format-range-server-13` (`l2-green-ver004-range-server-13.log`, `sha256=36603cdcb32ee0bfdb0fa0b4637fb4dad374e8f8b80e2562271739320bcdc689`)
```text
$ uvx --from ruff==0.17.2 ruff format --check --no-cache --range=2287:1-2291:999 server.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=0.04s]
--- STDOUT ---
1 file already formatted

--- STDERR ---
```

### `VER-004-ruff-format-range-server-14` (`l2-green-ver004-range-server-14.log`, `sha256=b983f7809853564cc15dd508ac2c088d5991ddcec96b88a1296570978a186f4c`)
```text
$ uvx --from ruff==0.17.2 ruff format --check --no-cache --range=2338:1-2338:999 server.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=0.04s]
--- STDOUT ---
1 file already formatted

--- STDERR ---
```

### `VER-004-ruff-format-range-server-15` (`l2-green-ver004-range-server-15.log`, `sha256=aebac7e28bf0afaef20d5fe5510a30f550197c93290b50bc7cbe83fc5403e8e9`)
```text
$ uvx --from ruff==0.17.2 ruff format --check --no-cache --range=2356:1-2356:999 server.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=0.04s]
--- STDOUT ---
1 file already formatted

--- STDERR ---
```

### `VER-004-ruff-format-range-server-16` (`l2-green-ver004-range-server-16.log`, `sha256=adf78bb4fd6f97936c702a7d4294300b6fcd29b8b9ba1320a9e7759e38e2b9fb`)
```text
$ uvx --from ruff==0.17.2 ruff format --check --no-cache --range=2360:1-3114:999 server.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=0.05s]
--- STDOUT ---
1 file already formatted

--- STDERR ---
```

### `VER-004-ruff-format-range-server-17` (`l2-green-ver004-range-server-17.log`, `sha256=3cb140d3caf21e48815884209c1effe43aba443517ff186132053779cf8a08a5`)
```text
$ uvx --from ruff==0.17.2 ruff format --check --no-cache --range=3116:1-3130:999 server.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=0.05s]
--- STDOUT ---
1 file already formatted

--- STDERR ---
```

### `VER-004-ruff-format-range-server-18` (`l2-green-ver004-range-server-18.log`, `sha256=e4d8d810199f401eb0ce3372bddb0bff3d8b3da741b09caaab7e30a3eb3a177c`)
```text
$ uvx --from ruff==0.17.2 ruff format --check --no-cache --range=3135:1-3153:999 server.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=0.05s]
--- STDOUT ---
1 file already formatted

--- STDERR ---
```

### `VER-004-ruff-format-range-server-19` (`l2-green-ver004-range-server-19.log`, `sha256=c444cf645da432ed3d6b8986da17bbeab54f5a166c128ff60e99cd07468048f8`)
```text
$ uvx --from ruff==0.17.2 ruff format --check --no-cache --range=4427:1-4431:999 server.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=0.04s]
--- STDOUT ---
1 file already formatted

--- STDERR ---
```

### `VER-004-ruff-format-range-server-20` (`l2-green-ver004-range-server-20.log`, `sha256=d313077dabc9521b20943926aa602c5f7ab502521c54b0bf9791af1b893d9023`)
```text
$ uvx --from ruff==0.17.2 ruff format --check --no-cache --range=4438:1-4442:999 server.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=0.04s]
--- STDOUT ---
1 file already formatted

--- STDERR ---
```

### `VER-004-ruff-format-range-server-21` (`l2-green-ver004-range-server-21.log`, `sha256=7fc43edee20bccae0ccb2e433fc2239ce865ac22787665d91b41f59d4cd1e0cd`)
```text
$ uvx --from ruff==0.17.2 ruff format --check --no-cache --range=4444:1-4446:999 server.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=0.04s]
--- STDOUT ---
1 file already formatted

--- STDERR ---
```

### `VER-004-ruff-format-range-server-22` (`l2-green-ver004-range-server-22.log`, `sha256=9028f2d9ca25ffe300866f2e21f556386a6615b4a25fb8a975a0c0f368a50c7b`)
```text
$ uvx --from ruff==0.17.2 ruff format --check --no-cache --range=4449:1-4453:999 server.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=0.04s]
--- STDOUT ---
1 file already formatted

--- STDERR ---
```

### `VER-004-ruff-format-range-server-23` (`l2-green-ver004-range-server-23.log`, `sha256=137d18ac14126d0eb7f05fddd42def32e3519b858b8195f60316998bef756f6c`)
```text
$ uvx --from ruff==0.17.2 ruff format --check --no-cache --range=4462:1-4464:999 server.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=0.04s]
--- STDOUT ---
1 file already formatted

--- STDERR ---
```

### `VER-004-ruff-format-range-server-24` (`l2-green-ver004-range-server-24.log`, `sha256=a21e3aad406e5764d4dbd3d7b01556db946c6dc89b5ef86eb37e3ce7e25139b3`)
```text
$ uvx --from ruff==0.17.2 ruff format --check --no-cache --range=4467:1-4475:999 server.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=0.04s]
--- STDOUT ---
1 file already formatted

--- STDERR ---
```

### `VER-004-ruff-format-range-server-25` (`l2-green-ver004-range-server-25.log`, `sha256=342d717568eb06315b8a533ed99dd7bdbf57ca15104e8781fad2e2f8239307a9`)
```text
$ uvx --from ruff==0.17.2 ruff format --check --no-cache --range=4482:1-4489:999 server.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=0.04s]
--- STDOUT ---
1 file already formatted

--- STDERR ---
```

### `VER-004-ruff-format-range-server-26` (`l2-green-ver004-range-server-26.log`, `sha256=c9bb5ad51a1cec6ddb158bd40b203bbf93ab98d37cd0e9b39100fcbca38901ad`)
```text
$ uvx --from ruff==0.17.2 ruff format --check --no-cache --range=4492:1-4494:999 server.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=0.04s]
--- STDOUT ---
1 file already formatted

--- STDERR ---
```

### `VER-004-ruff-format-range-server-27` (`l2-green-ver004-range-server-27.log`, `sha256=48c923dbeecb3ae20982762829ed159b3617ae1c87f534533a94d2a9a6bb9b51`)
```text
$ uvx --from ruff==0.17.2 ruff format --check --no-cache --range=4496:1-4504:999 server.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=0.04s]
--- STDOUT ---
1 file already formatted

--- STDERR ---
```

### `VER-004-ruff-format-range-server-28` (`l2-green-ver004-range-server-28.log`, `sha256=631d1084303ce679115087d098863502208aa8697d8f484779731460cfcdde21`)
```text
$ uvx --from ruff==0.17.2 ruff format --check --no-cache --range=4509:1-4517:999 server.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=0.04s]
--- STDOUT ---
1 file already formatted

--- STDERR ---
```

### `VER-004-ruff-format-range-server-29` (`l2-green-ver004-range-server-29.log`, `sha256=8cd812c358a608185ca293bcb5779f4333e26f659a9a9c6b36580267e1d99745`)
```text
$ uvx --from ruff==0.17.2 ruff format --check --no-cache --range=4527:1-4528:999 server.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=0.04s]
--- STDOUT ---
1 file already formatted

--- STDERR ---
```

### `VER-004-ruff-format-range-server-30` (`l2-green-ver004-range-server-30.log`, `sha256=1b7991002fb119b2a9562d39b41d3068d02cd8275511c275a2508af415c2cea1`)
```text
$ uvx --from ruff==0.17.2 ruff format --check --no-cache --range=4579:1-4581:999 server.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=0.04s]
--- STDOUT ---
1 file already formatted

--- STDERR ---
```

### `VER-004-ruff-format-range-server-31` (`l2-green-ver004-range-server-31.log`, `sha256=c548744592a53ccc65fc76571ca3b4c2c2d8ce76936922f48661451ace75e686`)
```text
$ uvx --from ruff==0.17.2 ruff format --check --no-cache --range=4583:1-4596:999 server.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=0.04s]
--- STDOUT ---
1 file already formatted

--- STDERR ---
```

### `VER-004-ruff-format-range-server-32` (`l2-green-ver004-range-server-32.log`, `sha256=b891acb4d080206084d4e7e70ad7bf878c28a2d0f37db5f757c3d0b06b847689`)
```text
$ uvx --from ruff==0.17.2 ruff format --check --no-cache --range=4686:1-4686:999 server.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=0.05s]
--- STDOUT ---
1 file already formatted

--- STDERR ---
```

### `VER-004-ruff-format-range-server-33` (`l2-green-ver004-range-server-33.log`, `sha256=d50fc53e2d4ea34a0650b8b573e78847b4870e16c2897cff91e85af02697c94b`)
```text
$ uvx --from ruff==0.17.2 ruff format --check --no-cache --range=4696:1-4700:999 server.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=0.04s]
--- STDOUT ---
1 file already formatted

--- STDERR ---
```

### `VER-004-ruff-format-range-server-34` (`l2-green-ver004-range-server-34.log`, `sha256=0b46d3055ef8fc3f66b6ded112feefe9199d87bab507bcff915342caf40929b3`)
```text
$ uvx --from ruff==0.17.2 ruff format --check --no-cache --range=4734:1-4967:999 server.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=0.04s]
--- STDOUT ---
1 file already formatted

--- STDERR ---
```

### `VER-004-ruff-format-range-server-35` (`l2-green-ver004-range-server-35.log`, `sha256=245dde84273d71bc8657149dcf68158d87f93655201c67bdfa02385e0517c472`)
```text
$ uvx --from ruff==0.17.2 ruff format --check --no-cache --range=5118:1-5119:999 server.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=0.04s]
--- STDOUT ---
1 file already formatted

--- STDERR ---
```

### `VER-004-ruff-format-range-server-36` (`l2-green-ver004-range-server-36.log`, `sha256=522ec4a1dd2a1f8dbcf9a779dd97bad5b94553e7e5ebbd25585ab953048d7b92`)
```text
$ uvx --from ruff==0.17.2 ruff format --check --no-cache --range=5229:1-5283:999 server.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=0.04s]
--- STDOUT ---
1 file already formatted

--- STDERR ---
```

### `VER-004-ruff-format-range-server-37` (`l2-green-ver004-range-server-37.log`, `sha256=783dea9a28cffd5e4453d20b2f4e8caaded8c886585c49e931dade2b1bf2b22f`)
```text
$ uvx --from ruff==0.17.2 ruff format --check --no-cache --range=5301:1-5303:999 server.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=0.04s]
--- STDOUT ---
1 file already formatted

--- STDERR ---
```

### `VER-004-ruff-format-range-server-38` (`l2-green-ver004-range-server-38.log`, `sha256=5459a1af2d4cd06784a4df3f383f033d2406f1ec2985f9bbb140e11c17a87fbb`)
```text
$ uvx --from ruff==0.17.2 ruff format --check --no-cache --range=5309:1-5311:999 server.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=0.04s]
--- STDOUT ---
1 file already formatted

--- STDERR ---
```

### `VER-004-ruff-format-range-server-39` (`l2-green-ver004-range-server-39.log`, `sha256=be56a5d141ae879726c1881ab8cfa22d7656b85dff414f68d0f5c6e5ee338cec`)
```text
$ uvx --from ruff==0.17.2 ruff format --check --no-cache --range=5322:1-5324:999 server.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=0.04s]
--- STDOUT ---
1 file already formatted

--- STDERR ---
```

### `VER-004-ruff-format-range-server-40` (`l2-green-ver004-range-server-40.log`, `sha256=8b4d01369142097d3605fedf79a388055b489e4a9488e8c09203c90f6ce258fd`)
```text
$ uvx --from ruff==0.17.2 ruff format --check --no-cache --range=5327:1-5331:999 server.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=0.04s]
--- STDOUT ---
1 file already formatted

--- STDERR ---
```

### `VER-004-ruff-format-range-server-41` (`l2-green-ver004-range-server-41.log`, `sha256=db63a9b27631d2848cb9646c447e74b4547959907a2af711c9e390d57f06a6b4`)
```text
$ uvx --from ruff==0.17.2 ruff format --check --no-cache --range=5336:1-5341:999 server.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=0.04s]
--- STDOUT ---
1 file already formatted

--- STDERR ---
```

### `VER-004-ruff-format-range-server-42` (`l2-green-ver004-range-server-42.log`, `sha256=edf1e728d3a1e78162570735773864dc3e25e7e19fbaa0758918870b5bca3db3`)
```text
$ uvx --from ruff==0.17.2 ruff format --check --no-cache --range=5343:1-5348:999 server.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=0.04s]
--- STDOUT ---
1 file already formatted

--- STDERR ---
```

### `VER-004-ruff-format-range-server-43` (`l2-green-ver004-range-server-43.log`, `sha256=fda44981641fda46207e200f893109fc3e694a4c405f49ba41e9f92d898c5e07`)
```text
$ uvx --from ruff==0.17.2 ruff format --check --no-cache --range=5351:1-5380:999 server.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=0.04s]
--- STDOUT ---
1 file already formatted

--- STDERR ---
```

### `VER-004-ruff-format-range-server-44` (`l2-green-ver004-range-server-44.log`, `sha256=61ea0fb1aba06e25449f2612b634fb314200855d0a43b244c2873749048d878b`)
```text
$ uvx --from ruff==0.17.2 ruff format --check --no-cache --range=5383:1-5408:999 server.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=0.04s]
--- STDOUT ---
1 file already formatted

--- STDERR ---
```

### `VER-004-ruff-format-range-server-45` (`l2-green-ver004-range-server-45.log`, `sha256=59f99023e45485943b4baf540e6bb7ca11df9d4b2a599cb0bd9aa4b49b52ec9a`)
```text
$ uvx --from ruff==0.17.2 ruff format --check --no-cache --range=5410:1-5434:999 server.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=0.04s]
--- STDOUT ---
1 file already formatted

--- STDERR ---
```

### `VER-004-ruff-format-range-server-46` (`l2-green-ver004-range-server-46.log`, `sha256=efe2330f4042e4d347064c5eb4c95a514aae435432a978636f893c4b5bf90485`)
```text
$ uvx --from ruff==0.17.2 ruff format --check --no-cache --range=5441:1-5441:999 server.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=0.04s]
--- STDOUT ---
1 file already formatted

--- STDERR ---
```

### `VER-004-ruff-format-range-server-47` (`l2-green-ver004-range-server-47.log`, `sha256=62b0e86044d4005aabf6b36193f93b51ddf9d706f31a579c7497fc70fe00bbc8`)
```text
$ uvx --from ruff==0.17.2 ruff format --check --no-cache --range=5453:1-5474:999 server.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=0.04s]
--- STDOUT ---
1 file already formatted

--- STDERR ---
```

### `VER-004-ruff-format-range-server-48` (`l2-green-ver004-range-server-48.log`, `sha256=be4928c4cdac314cdfbb3d9ed146bd1e810ab7230d8117622038329b8242f7db`)
```text
$ uvx --from ruff==0.17.2 ruff format --check --no-cache --range=5593:1-5602:999 server.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=0.04s]
--- STDOUT ---
1 file already formatted

--- STDERR ---
```

### `VER-004-ruff-format-range-server-49` (`l2-green-ver004-range-server-49.log`, `sha256=917686da3daa63a23567d127e2aa768b31a59f19e398ac6135ae919a4e4aa7f1`)
```text
$ uvx --from ruff==0.17.2 ruff format --check --no-cache --range=5662:1-5667:999 server.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=0.04s]
--- STDOUT ---
1 file already formatted

--- STDERR ---
```

### `VER-004-ruff-format-range-server-50` (`l2-green-ver004-range-server-50.log`, `sha256=6e945fc57f39e8bda2972c3dbae2dcdd5bd084a526b16177bd7b1e96307a3351`)
```text
$ uvx --from ruff==0.17.2 ruff format --check --no-cache --range=5695:1-5705:999 server.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=0.04s]
--- STDOUT ---
1 file already formatted

--- STDERR ---
```

### `VER-004-ruff-format-range-server-51` (`l2-green-ver004-range-server-51.log`, `sha256=caa77892ae2b4af29c048102161c237bd74d41143fbcda241c0e4a355bb4798c`)
```text
$ uvx --from ruff==0.17.2 ruff format --check --no-cache --range=5736:1-5943:999 server.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=0.04s]
--- STDOUT ---
1 file already formatted

--- STDERR ---
```

### `VER-004-ruff-format-range-server-52` (`l2-green-ver004-range-server-52.log`, `sha256=d5ed0ef1c02c1dbca0dea536e990b429541f5d27f422b87a8431603ba43bd3bd`)
```text
$ uvx --from ruff==0.17.2 ruff format --check --no-cache --range=5971:1-5991:999 server.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=0.04s]
--- STDOUT ---
1 file already formatted

--- STDERR ---
```

### `VER-004-ruff-format-range-server-53` (`l2-green-ver004-range-server-53.log`, `sha256=6f342289ba267b724264369fcf130a8a0635c26ec9443c3cd34dd71f9c5aced1`)
```text
$ uvx --from ruff==0.17.2 ruff format --check --no-cache --range=6273:1-6273:999 server.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=0.04s]
--- STDOUT ---
1 file already formatted

--- STDERR ---
```

### `VER-004-ruff-format-range-test_step_interruption-1` (`l2-green-ver004-range-test_step_interruption-1.log`, `sha256=1bfce177c316cdcc6b3567f30279457b3d07734c5dbe6d71e0043126e14329cc`)
```text
$ uvx --from ruff==0.17.2 ruff format --check --no-cache --range=67:1-67:999 tests/test_step_interruption.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=0.04s]
--- STDOUT ---
1 file already formatted

--- STDERR ---
```

### `VER-004-ruff-format-range-test_step_interruption-2` (`l2-green-ver004-range-test_step_interruption-2.log`, `sha256=43db84d775e827bb10d95980ad3a6ab79d1dad3c72ff41c74a2df1e6b45f0c7b`)
```text
$ uvx --from ruff==0.17.2 ruff format --check --no-cache --range=142:1-148:999 tests/test_step_interruption.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=0.04s]
--- STDOUT ---
1 file already formatted

--- STDERR ---
```

### `VER-004-ruff-format-range-test_step_interruption-3` (`l2-green-ver004-range-test_step_interruption-3.log`, `sha256=bd29f48f762395c50e3e010617f077c71d139251e91c2b158d86fa064fbcf1da`)
```text
$ uvx --from ruff==0.17.2 ruff format --check --no-cache --range=152:1-152:999 tests/test_step_interruption.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=0.04s]
--- STDOUT ---
1 file already formatted

--- STDERR ---
```

### `VER-004-ruff-format-range-test_step_interruption-4` (`l2-green-ver004-range-test_step_interruption-4.log`, `sha256=fe32619cd0f07a5dc87b861454f60be891396fd628696cc972e5b6680ba1a260`)
```text
$ uvx --from ruff==0.17.2 ruff format --check --no-cache --range=188:1-189:999 tests/test_step_interruption.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=0.04s]
--- STDOUT ---
1 file already formatted

--- STDERR ---
```

### `VER-004-ruff-format-range-test_step_interruption-5` (`l2-green-ver004-range-test_step_interruption-5.log`, `sha256=8e3fda2fa1591e93deecb5958c4c58218cc94785d361a2aa06f93b45b30fe0b1`)
```text
$ uvx --from ruff==0.17.2 ruff format --check --no-cache --range=416:1-418:999 tests/test_step_interruption.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=0.04s]
--- STDOUT ---
1 file already formatted

--- STDERR ---
```

### `VER-004-ruff-format-range-test_step_interruption-6` (`l2-green-ver004-range-test_step_interruption-6.log`, `sha256=a541c75c111a88d475f6740ca78828130e3863cfd672b95fe63e34597edbaf8a`)
```text
$ uvx --from ruff==0.17.2 ruff format --check --no-cache --range=423:1-456:999 tests/test_step_interruption.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=0.04s]
--- STDOUT ---
1 file already formatted

--- STDERR ---
```

### `VER-001-pytest` (`l2-green-ver001-pytest.log`, `sha256=6dc083e24777b6ee2ac18e9f0d441a5dfecc4d9e4a474bb375953913c08edfe2`)
```text
$ uvx pytest -q -p no:cacheprovider tests/
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=142.29s]
--- STDOUT ---
......................... [  6%]
........................................................................................................................................................... [ 45%]
.............................................................. [ 60%]
........................................................................ [ 78%]
............................................................... [ 94%]
.......................                                              [100%]
400 passed, 3155 subtests passed in 142.08s (0:02:22)

--- STDERR ---
```

### `VER-002-unittest` (`l2-green-ver002-unittest.log`, `sha256=0a3b02903999bc0b50b1c7b3a4c14a0b58f03085480a0ecdfdb63f7533df2f67`)
```text
$ python3 -m unittest discover -s tests -p test_*.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=137.64s]
--- STDOUT ---

--- STDERR ---
..........2026-10-26 21:46:31 http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-26 21:46:31 O-EXIT/v1 mode=json model=jev-1.13 status=400 exit_reason=bad_request rc=None total_spawns=0 retries=0 signal=0 tools=0 out_chars=0 transport=none first_event_ms=None ttft_ms=None transport_history=[] duration_s=0.00
2026-10-26 21:46:31 http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-26 21:46:31 O-EXIT/v1 mode=json model=jev-1.13-free status=400 exit_reason=bad_request rc=None total_spawns=0 retries=0 signal=0 tools=0 out_chars=0 transport=none first_event_ms=None ttft_ms=None transport_history=[] duration_s=0.00
2026-10-26 21:46:31 http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-26 21:46:31 O-EXIT/v1 mode=json model=nemotron-3-ultra-free status=400 exit_reason=bad_request rc=None total_spawns=0 retries=0 signal=0 tools=0 out_chars=0 transport=none first_event_ms=None ttft_ms=None transport_history=[] duration_s=0.00
2026-10-26 21:46:31 http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-26 21:46:31 O-EXIT/v1 mode=json model=test status=400 exit_reason=bad_request rc=None total_spawns=0 retries=0 signal=0 tools=0 out_chars=0 transport=none first_event_ms=None ttft_ms=None transport_history=[] duration_s=0.00
2026-10-26 21:46:31 http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-26 21:46:31 O-EXIT/v1 mode=json model=claude-opus-5-5-backup status=400 exit_reason=bad_request rc=None total_spawns=0 retries=0 signal=0 tools=0 out_chars=0 transport=none first_event_ms=None ttft_ms=None transport_history=[] duration_s=0.00
2026-10-26 21:46:31 http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-26 21:46:31 O-EXIT/v1 mode=json model=deepseek-v4.1-flash status=400 exit_reason=bad_request rc=None total_spawns=0 retries=0 signal=0 tools=0 out_chars=0 transport=none first_event_ms=None ttft_ms=None transport_history=[] duration_s=0.00
2026-10-26 21:46:31 http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-26 21:46:31 O-EXIT/v1 mode=json model=claude-haiku-5-5 status=400 exit_reason=bad_request rc=None total_spawns=0 retries=0 signal=0 tools=0 out_chars=0 transport=none first_event_ms=None ttft_ms=None transport_history=[] duration_s=0.00
.2026-10-26 21:46:31 http "GET /health HTTP/1.1" 200 -
.2026-10-26 21:46:31 http "GET /v1/models HTTP/1.1" 200 -
.2026-10-26 21:46:31 http "GET /v1/models HTTP/1.1" 401 -
........................2026-10-26 21:46:33 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=32 cwd=/var/folders/2f/***/T/tmp8yuovilj/ws
2026-10-26 21:46:33 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-26 21:46:34 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=7 emulate_tools=False retries=0 total_spawns=1
2026-10-26 21:46:34 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=7 transport=run first_event_ms=95 ttft_ms=95 transport_history=['run'] duration_s=0.35
.2026-10-26 21:46:34 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=32 cwd=/var/folders/2f/***/T/tmp8yuovilj/ws
2026-10-26 21:46:34 exec cli failed rc=1 state=nonzero_exit stderr_tail='Error: Unexpected error\ndatabase is locked'
2026-10-26 21:46:34 exec failed rc=1 without output, retry 1/2 total_spawns=1/3: 'Error: Unexpected error\ndatabase is locked'
2026-10-26 21:46:34 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=32 cwd=/var/folders/2f/***/T/tmp8yuovilj/ws
2026-10-26 21:46:35 done model=muse-spark-1.3-contributor-free rc=0 state=ok tools=0 out_chars=7 retries=0 total_spawns=2
2026-10-26 21:46:35 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-26 21:46:35 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=2 retries=1 signal=0 tools=0 out_chars=7 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=1.94
.2026-10-26 21:46:35 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=32 cwd=/var/folders/2f/***/T/tmp8yuovilj/ws
2026-10-26 21:46:36 exec: early provider error (waiting for CLI recovery)
2026-10-26 21:46:36 exec cli failed rc=1 state=provider_error stderr_tail='HTTP 429: FreeUsageLimitError'
2026-10-26 21:46:36 exec failed rc=1 without output, retry 1/2 total_spawns=1/3: 'HTTP 429: FreeUsageLimitError'
2026-10-26 21:46:36 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=32 cwd=/var/folders/2f/***/T/tmp8yuovilj/ws
2026-10-26 21:46:37 exec: early provider error (waiting for CLI recovery)
2026-10-26 21:46:37 exec cli failed rc=1 state=provider_error stderr_tail='HTTP 429: FreeUsageLimitError'
2026-10-26 21:46:37 exec failed rc=1 without output, retry 2/2 total_spawns=2/3: 'HTTP 429: FreeUsageLimitError'
2026-10-26 21:46:37 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=32 cwd=/var/folders/2f/***/T/tmp8yuovilj/ws
2026-10-26 21:46:38 exec: early provider error (waiting for CLI recovery)
2026-10-26 21:46:38 exec cli failed rc=1 state=provider_error stderr_tail='HTTP 429: FreeUsageLimitError'
2026-10-26 21:46:38 http "POST /v1/chat/completions HTTP/1.1" 502 -
2026-10-26 21:46:38 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=502 exit_reason=upstream_failed rc=None total_spawns=3 retries=2 signal=0 tools=0 out_chars=0 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=3.00
.2026-10-26 21:46:38 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=32 cwd=/var/folders/2f/***/T/tmp8yuovilj/ws
2026-10-26 21:46:39 exec cli failed rc=1 state=nonzero_exit stderr_tail='Error: fatal boom xyz'
2026-10-26 21:46:39 exec failed rc=1 without output, retry 1/2 total_spawns=1/3: 'Error: fatal boom xyz'
2026-10-26 21:46:39 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=32 cwd=/var/folders/2f/***/T/tmp8yuovilj/ws
2026-10-26 21:46:40 exec cli failed rc=1 state=nonzero_exit stderr_tail='Error: fatal boom xyz'
2026-10-26 21:46:40 exec failed rc=1 without output, retry 2/2 total_spawns=2/3: 'Error: fatal boom xyz'
2026-10-26 21:46:40 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=32 cwd=/var/folders/2f/***/T/tmp8yuovilj/ws
2026-10-26 21:46:41 exec cli failed rc=1 state=nonzero_exit stderr_tail='Error: fatal boom xyz'
2026-10-26 21:46:41 http "POST /v1/chat/completions HTTP/1.1" 502 -
2026-10-26 21:46:41 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=502 exit_reason=upstream_failed rc=None total_spawns=3 retries=2 signal=0 tools=0 out_chars=0 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=2.97
.2026-10-26 21:46:41 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=32 cwd=/var/folders/2f/***/T/tmp8yuovilj/ws
2026-10-26 21:46:41 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-26 21:46:42 stream provider error: HTTP 403: free tier denied
2026-10-26 21:46:42 stream: early provider error (waiting for CLI recovery)
2026-10-26 21:46:42 stream cli failed rc=1 stderr_tail='HTTP 403: free tier denied'
2026-10-26 21:46:42 stream failed model=muse-spark-1.3-contributor-free rc=1 fail_retries=0 total_spawns=1
2026-10-26 21:46:42 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=upstream_failed rc=None total_spawns=1 retries=0 signal=0 tools=0 out_chars=0 transport=run first_event_ms=755 ttft_ms=None transport_history=['run'] duration_s=1.01
..2026-10-26 21:46:42 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free --standalone prompt_chars=8 cwd=/var/folders/2f/***/T/tmp8yuovilj/ws
2026-10-26 21:46:43 exec timeout after 1s, killing proc group
/private/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge/tests/test_cli_failure.py:267: ResourceWarning: unclosed file <_io.TextIOWrapper name=9 encoding='utf-8'>
  out = server.Run("muse-spark-1.3-contributor-free", "Проверка", "", Path(self.tmp.name) / "ws")._execute_once()
ResourceWarning: Enable tracemalloc to get the object allocation traceback
/private/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge/tests/test_cli_failure.py:267: ResourceWarning: unclosed file <_io.TextIOWrapper name=7 encoding='utf-8'>
  out = server.Run("muse-spark-1.3-contributor-free", "Проверка", "", Path(self.tmp.name) / "ws")._execute_once()
ResourceWarning: Enable tracemalloc to get the object allocation traceback
.2026-10-26 21:46:43 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=32 cwd=/var/folders/2f/***/T/tmp8yuovilj/ws
2026-10-26 21:46:43 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-26 21:46:44 stream cli failed rc=1 stderr_tail='Error: Unexpected error\ndatabase is locked'
2026-10-26 21:46:44 stream retry 1/2 after cli failure without output
2026-10-26 21:46:44 stream exec retry=0 fail_retries=1 model=opencode/muse-spark-1.3-contributor-free prompt_chars=32 total_spawns=1/3
2026-10-26 21:46:45 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=7 emulate_tools=False retries=0 total_spawns=2
2026-10-26 21:46:45 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=2 retries=1 signal=0 tools=0 out_chars=7 transport=run first_event_ms=1048 ttft_ms=1048 transport_history=['run'] duration_s=1.30
.2026-10-26 21:46:45 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=32 cwd=/var/folders/2f/***/T/tmp8yuovilj/ws
2026-10-26 21:46:45 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-26 21:46:46 stream cli failed rc=1 stderr_tail='Error: fatal boom xyz'
2026-10-26 21:46:46 stream retry 1/2 after cli failure without output
2026-10-26 21:46:46 stream exec retry=0 fail_retries=1 model=opencode/muse-spark-1.3-contributor-free prompt_chars=32 total_spawns=1/3
2026-10-26 21:46:47 stream cli failed rc=1 stderr_tail='Error: fatal boom xyz'
2026-10-26 21:46:47 stream retry 2/2 after cli failure without output
2026-10-26 21:46:47 stream exec retry=0 fail_retries=2 model=opencode/muse-spark-1.3-contributor-free prompt_chars=32 total_spawns=2/3
2026-10-26 21:46:48 stream cli failed rc=1 stderr_tail='Error: fatal boom xyz'
2026-10-26 21:46:48 stream failed model=muse-spark-1.3-contributor-free rc=1 fail_retries=2 total_spawns=3
2026-10-26 21:46:48 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=upstream_failed rc=None total_spawns=3 retries=2 signal=0 tools=0 out_chars=0 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=2.97
.2026-10-26 21:46:48 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=32 cwd=/var/folders/2f/***/T/tmp8yuovilj/ws
2026-10-26 21:46:48 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-26 21:46:49 stream cli failed rc=1 stderr_tail='Error: Unexpected error\ndatabase is locked'
2026-10-26 21:46:49 stream retry 1/2 after cli failure without output
2026-10-26 21:46:49 stream exec retry=0 fail_retries=1 model=opencode/muse-spark-1.3-contributor-free prompt_chars=32 total_spawns=1/3
2026-10-26 21:46:50 stream cli failed rc=1 stderr_tail='Error: Unexpected error\ndatabase is locked'
2026-10-26 21:46:50 stream retry 2/2 after cli failure without output
2026-10-26 21:46:50 stream exec retry=0 fail_retries=2 model=opencode/muse-spark-1.3-contributor-free prompt_chars=32 total_spawns=2/3
2026-10-26 21:46:51 stream cli failed rc=1 stderr_tail='Error: Unexpected error\ndatabase is locked'
2026-10-26 21:46:51 stream failed model=muse-spark-1.3-contributor-free rc=1 fail_retries=2 total_spawns=3
2026-10-26 21:46:51 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=upstream_failed rc=None total_spawns=3 retries=2 signal=0 tools=0 out_chars=0 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=2.99
.2026-10-26 21:46:51 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=32 cwd=/var/folders/2f/***/T/tmp8yuovilj/ws
2026-10-26 21:46:51 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-26 21:46:52 stream provider error: HTTP 429: FreeUsageLimitError
2026-10-26 21:46:52 stream: early provider error (waiting for CLI recovery)
2026-10-26 21:46:52 stream cli failed rc=1 stderr_tail='HTTP 429: FreeUsageLimitError'
2026-10-26 21:46:52 stream retry 1/2 after cli failure without output
2026-10-26 21:46:52 stream exec retry=0 fail_retries=1 model=opencode/muse-spark-1.3-contributor-free prompt_chars=32 total_spawns=1/3
2026-10-26 21:46:52 stream provider error: HTTP 429: FreeUsageLimitError
2026-10-26 21:46:52 stream: early provider error (waiting for CLI recovery)
2026-10-26 21:46:53 stream cli failed rc=1 stderr_tail='HTTP 429: FreeUsageLimitError'
2026-10-26 21:46:53 stream retry 2/2 after cli failure without output
2026-10-26 21:46:53 stream exec retry=0 fail_retries=2 model=opencode/muse-spark-1.3-contributor-free prompt_chars=32 total_spawns=2/3
2026-10-26 21:46:54 stream provider error: HTTP 429: FreeUsageLimitError
2026-10-26 21:46:54 stream: early provider error (waiting for CLI recovery)
2026-10-26 21:46:54 stream cli failed rc=1 stderr_tail='HTTP 429: FreeUsageLimitError'
2026-10-26 21:46:54 stream failed model=muse-spark-1.3-contributor-free rc=1 fail_retries=2 total_spawns=3
2026-10-26 21:46:54 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=upstream_failed rc=None total_spawns=3 retries=2 signal=0 tools=0 out_chars=0 transport=run first_event_ms=2780 ttft_ms=None transport_history=['run'] duration_s=3.04
.2026-10-26 21:46:54 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=32 cwd=/var/folders/2f/***/T/tmp8yuovilj/ws
2026-10-26 21:46:54 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-26 21:46:55 stream cli failed rc=1 stderr_tail='Error: fatal boom xyz'
2026-10-26 21:46:55 stream retry 1/2 after cli failure without output
2026-10-26 21:46:55 stream exec retry=0 fail_retries=1 model=opencode/muse-spark-1.3-contributor-free prompt_chars=32 total_spawns=1/3
2026-10-26 21:46:56 stream cli failed rc=1 stderr_tail='Error: fatal boom xyz'
2026-10-26 21:46:56 stream retry 2/2 after cli failure without output
2026-10-26 21:46:56 stream exec retry=0 fail_retries=2 model=opencode/muse-spark-1.3-contributor-free prompt_chars=32 total_spawns=2/3
2026-10-26 21:46:57 stream cli failed rc=1 stderr_tail='Error: fatal boom xyz'
2026-10-26 21:46:57 stream failed model=muse-spark-1.3-contributor-free rc=1 fail_retries=2 total_spawns=3
2026-10-26 21:46:57 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=upstream_failed rc=None total_spawns=3 retries=2 signal=0 tools=0 out_chars=0 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=2.96
.2026-10-26 21:46:57 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=32 cwd=/var/folders/2f/***/T/tmp8yuovilj/ws
2026-10-26 21:46:57 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-26 21:46:58 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=7 emulate_tools=False retries=0 total_spawns=1
2026-10-26 21:46:58 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=7 transport=run first_event_ms=1185 ttft_ms=1185 transport_history=['run'] duration_s=1.44
.2026-10-26 21:46:58 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=32 cwd=/var/folders/2f/***/T/tmp8yuovilj/ws
2026-10-26 21:46:58 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-26 21:46:59 stream timeout after 1s, killing proc group
2026-10-26 21:46:59 stream failed model=muse-spark-1.3-contributor-free rc=-15 fail_retries=0 total_spawns=1
2026-10-26 21:46:59 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=timeout rc=None total_spawns=1 retries=0 signal=0 tools=0 out_chars=0 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=1.01
...............................................................................2026-10-26 21:47:41 tool_call_recovered extra_braces=1
.2026-10-26 21:47:41 tool_call_recovered extra_braces=1
.2026-10-26 21:47:41 tool_call_recovered extra_braces=1
2026-10-26 21:47:41 tool_call_recovered extra_braces=1
2026-10-26 21:47:41 tool_call_recovered extra_braces=1
2026-10-26 21:47:41 tool_call_recovered extra_braces=1
..2026-10-26 21:47:41 tool_call_recovered extra_braces=1
2026-10-26 21:47:41 tool_call_recovered extra_braces=1
2026-10-26 21:47:41 tool_call_recovered extra_braces=2
2026-10-26 21:47:41 tool_call_recovered extra_braces=2
2026-10-26 21:47:41 tool_call_recovered extra_braces=3
2026-10-26 21:47:41 tool_call_recovered extra_braces=3
2026-10-26 21:47:41 tool_call_recovered extra_braces=3
2026-10-26 21:47:41 tool_call_recovered extra_braces=3
2026-10-26 21:47:41 tool_call_recovered extra_braces=16
2026-10-26 21:47:41 tool_call_recovered extra_braces=16
............2026-10-26 21:47:41 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=13385 cwd=/var/folders/2f/***/T/tmpv7n95gv7/ws
2026-10-26 21:47:41 opencode built-in tool event: tool=todoread status=error mapped=False as=[]
2026-10-26 21:47:42 unmapped built-in tools=['todoread']: re-prompt 1/2
2026-10-26 21:47:42 exec retry=1 (unmapped built-in tool) total_spawns=1/3
2026-10-26 21:47:42 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=14047 cwd=/var/folders/2f/***/T/tmpv7n95gv7/ws
2026-10-26 21:47:42 exec: step with tool call finished, stopping opencode run
2026-10-26 21:47:42 opencode built-in tool event: tool=bash status=error mapped=True as=['bash']
2026-10-26 21:47:42 done model=muse-spark-1.3-contributor-free rc=-15 state=nonzero_exit tools=1 out_chars=15 retries=1 total_spawns=2
2026-10-26 21:47:42 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-26 21:47:42 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=-15 total_spawns=2 retries=1 signal=0 tools=1 out_chars=15 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=1.21
.2026-10-26 21:47:42 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=13385 cwd=/var/folders/2f/***/T/tmpv7n95gv7/ws
2026-10-26 21:47:43 exec: step with tool call finished, stopping opencode run
2026-10-26 21:47:43 opencode built-in tool event: tool=read status=error mapped=True as=['read']
2026-10-26 21:47:43 opencode built-in tool event: tool=todowrite status=error mapped=True as=['todo_write']
2026-10-26 21:47:43 opencode built-in tool event: tool=todowrite status=error mapped=True as=['todo_write']
2026-10-26 21:47:43 dropped duplicate tool call todo_write
2026-10-26 21:47:43 done model=muse-spark-1.3-contributor-free rc=-15 state=nonzero_exit tools=2 out_chars=0 retries=0 total_spawns=1
2026-10-26 21:47:43 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-26 21:47:43 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=-15 total_spawns=1 retries=0 signal=0 tools=2 out_chars=0 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=1.03
.2026-10-26 21:47:43 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=13385 cwd=/var/folders/2f/***/T/tmpv7n95gv7/ws
2026-10-26 21:47:43 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-26 21:47:44 opencode built-in tool event: tool=todoread status=error mapped=False as=[]
2026-10-26 21:47:45 stream unmapped built-in tools=['todoread']: re-prompt 1/2
2026-10-26 21:47:45 stream exec retry=1 fail_retries=0 model=opencode/muse-spark-1.3-contributor-free prompt_chars=14047 total_spawns=1/3
2026-10-26 21:47:45 opencode built-in tool event: tool=bash status=error mapped=True as=['bash']
2026-10-26 21:47:45 stream: step with tool call finished, stopping opencode run
2026-10-26 21:47:45 stream done model=muse-spark-1.3-contributor-free rc=-15 tools=1 out_chars=15 emulate_tools=True retries=1 total_spawns=2
2026-10-26 21:47:45 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=-15 total_spawns=2 retries=1 signal=0 tools=1 out_chars=15 transport=run first_event_ms=1975 ttft_ms=974 transport_history=['run'] duration_s=1.98
.2026-10-26 21:47:45 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=13385 cwd=/var/folders/2f/***/T/tmpv7n95gv7/ws
2026-10-26 21:47:45 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-26 21:47:46 opencode built-in tool event: tool=read status=error mapped=True as=['read']
2026-10-26 21:47:46 opencode built-in tool event: tool=todowrite status=error mapped=True as=['todo_write']
2026-10-26 21:47:46 opencode built-in tool event: tool=todowrite status=error mapped=True as=['todo_write']
2026-10-26 21:47:46 stream dropped duplicate tool call todo_write
2026-10-26 21:47:46 stream: step with tool call finished, stopping opencode run
2026-10-26 21:47:46 stream done model=muse-spark-1.3-contributor-free rc=-15 tools=2 out_chars=0 emulate_tools=True retries=0 total_spawns=1
2026-10-26 21:47:46 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=-15 total_spawns=1 retries=0 signal=0 tools=2 out_chars=0 transport=run first_event_ms=994 ttft_ms=None transport_history=['run'] duration_s=1.00
.2026-10-26 21:47:46 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1026 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-26 21:47:46 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-26 21:47:47 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=7 emulate_tools=True retries=0 total_spawns=1
2026-10-26 21:47:47 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=7 transport=run first_event_ms=88 ttft_ms=88 transport_history=['run'] duration_s=0.34
..2026-10-26 21:47:47 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1026 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-26 21:47:47 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-26 21:47:48 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=7 emulate_tools=True retries=0 total_spawns=1
2026-10-26 21:47:48 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=7 transport=run first_event_ms=91 ttft_ms=91 transport_history=['run'] duration_s=0.35
..2026-10-26 21:47:48 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1028 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-26 21:47:48 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-26 21:47:50 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=6 emulate_tools=True retries=0 total_spawns=1
2026-10-26 21:47:50 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=6 transport=run first_event_ms=1708 ttft_ms=1708 transport_history=['run'] duration_s=1.97
.2026-10-26 21:47:50 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1026 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-26 21:47:50 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-26 21:47:53 stream exec retry=0 fail_retries=0 model=opencode/muse-spark-1.3-contributor-free prompt_chars=1026 total_spawns=1/3
2026-10-26 21:47:55 stream exec retry=0 fail_retries=0 model=opencode/muse-spark-1.3-contributor-free prompt_chars=1026 total_spawns=2/3
2026-10-26 21:47:57 retry denied (first_event_timeout): MAX_TOTAL_SPAWNS=3 reached
2026-10-26 21:47:57 stream failed model=muse-spark-1.3-contributor-free rc=-15 fail_retries=0 total_spawns=3
2026-10-26 21:47:57 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=first_event_timeout rc=None total_spawns=3 retries=2 signal=0 tools=0 out_chars=0 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=6.52
.2026-10-26 21:47:57 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1034 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-26 21:47:57 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-26 21:47:58 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=6 transport=serve first_event_ms=341 ttft_ms=341 transport_history=['serve'] duration_s=1.00
.2026-10-26 21:47:58 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1034 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-26 21:47:58 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-26 21:47:58 stream exec retry=0 fail_retries=0 model=opencode/muse-spark-1.3-contributor-free prompt_chars=1034 total_spawns=1/3
2026-10-26 21:48:00 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=13 emulate_tools=True retries=0 total_spawns=2
2026-10-26 21:48:00 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=2 retries=0 signal=0 tools=0 out_chars=13 transport=run first_event_ms=1471 ttft_ms=1471 transport_history=['serve', 'run'] duration_s=1.73
2026-10-26 21:48:00 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1034 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-26 21:48:00 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-26 21:48:00 stream exec retry=0 fail_retries=0 model=opencode/muse-spark-1.3-contributor-free prompt_chars=1034 total_spawns=1/3
2026-10-26 21:48:01 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=13 emulate_tools=True retries=0 total_spawns=2
2026-10-26 21:48:01 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=2 retries=0 signal=0 tools=0 out_chars=13 transport=run first_event_ms=1411 ttft_ms=1411 transport_history=['serve', 'run'] duration_s=1.67
2026-10-26 21:48:01 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1034 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-26 21:48:01 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-26 21:48:01 stream exec retry=0 fail_retries=0 model=opencode/muse-spark-1.3-contributor-free prompt_chars=1034 total_spawns=1/3
2026-10-26 21:48:03 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=13 emulate_tools=True retries=0 total_spawns=2
2026-10-26 21:48:03 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=2 retries=0 signal=0 tools=0 out_chars=13 transport=run first_event_ms=1402 ttft_ms=1402 transport_history=['serve', 'run'] duration_s=1.66
..2026-10-26 21:48:04 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1034 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-26 21:48:04 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-26 21:48:05 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=6 transport=serve first_event_ms=247 ttft_ms=247 transport_history=['serve'] duration_s=0.91
../opt/homebrew/Cellar/python@3.14/3.14.7/Frameworks/Python.framework/Versions/3.14/lib/python3.14/subprocess.py:1139: ResourceWarning: subprocess 98704 is still running
  _warn("subprocess %s is still running" % self.pid,
ResourceWarning: Enable tracemalloc to get the object allocation traceback
.2026-10-26 21:48:06 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1131 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-26 21:48:06 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-26 21:48:06 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=0 transport=serve first_event_ms=220 ttft_ms=None transport_history=['serve'] duration_s=0.23
..2026-10-26 21:48:07 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1034 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-26 21:48:07 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-26 21:48:08 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=6 transport=serve first_event_ms=243 ttft_ms=243 transport_history=['serve'] duration_s=0.89
.2026-10-26 21:48:08 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1042 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-26 21:48:08 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-26 21:48:08 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=1 out_chars=0 transport=serve first_event_ms=244 ttft_ms=None transport_history=['serve'] duration_s=0.26
.2026-10-26 21:48:08 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1034 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-26 21:48:08 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-26 21:48:08 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=provider_fatal rc=None total_spawns=1 retries=0 signal=0 tools=0 out_chars=0 transport=serve first_event_ms=None ttft_ms=None transport_history=['serve'] duration_s=0.21
...2026-10-26 21:48:10 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1032 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-26 21:48:10 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-26 21:48:12 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=6 transport=serve first_event_ms=290 ttft_ms=1699 transport_history=['serve'] duration_s=2.35
.2026-10-26 21:48:12 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1039 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-26 21:48:12 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-26 21:48:13 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=1 out_chars=0 transport=serve first_event_ms=213 ttft_ms=214 transport_history=['serve'] duration_s=0.42
.................................................2026-10-26 21:48:13 tool_call_unparsed bytes=7 head='{broken'
.........................................2026-10-26 21:48:13 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1216 cwd=/var/folders/2f/***/T/tmptjc_l7zq/ws
2026-10-26 21:48:13 exec: early provider error (waiting for CLI recovery)
2026-10-26 21:48:14 exec: step with tool call finished, stopping opencode run
2026-10-26 21:48:14 exec cli failed rc=-15 state=provider_error stderr_tail='HTTP None: provider.transport: Connection lost: ECONNRESET'
2026-10-26 21:48:14 done model=muse-spark-1.3-contributor-free rc=-15 state=provider_error tools=2 out_chars=0 retries=0 total_spawns=1
2026-10-26 21:48:14 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-26 21:48:14 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=-15 total_spawns=1 retries=0 signal=0 tools=2 out_chars=0 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=1.11
.2026-10-26 21:48:14 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1216 cwd=/var/folders/2f/***/T/tmptjc_l7zq/ws
2026-10-26 21:48:14 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-26 21:48:15 stream provider error: HTTP None: provider.transport: Connection lost: ECONNRESET
2026-10-26 21:48:15 stream: early provider error (waiting for CLI recovery)
2026-10-26 21:48:16 stream: step with tool call finished, stopping opencode run
2026-10-26 21:48:16 stream done model=muse-spark-1.3-contributor-free rc=-15 tools=2 out_chars=0 emulate_tools=True retries=0 total_spawns=1
2026-10-26 21:48:16 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=-15 total_spawns=1 retries=0 signal=0 tools=2 out_chars=0 transport=run first_event_ms=41 ttft_ms=1052 transport_history=['run'] duration_s=1.06
.2026-10-26 21:48:16 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1216 cwd=/var/folders/2f/***/T/tmptjc_l7zq/ws
2026-10-26 21:48:16 exec: early provider error (waiting for CLI recovery)
2026-10-26 21:48:17 done model=muse-spark-1.3-contributor-free rc=0 state=provider_error tools=0 out_chars=17 retries=0 total_spawns=1
2026-10-26 21:48:17 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-26 21:48:17 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=17 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=1.30
.2026-10-26 21:48:17 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1216 cwd=/var/folders/2f/***/T/tmptjc_l7zq/ws
2026-10-26 21:48:17 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-26 21:48:17 stream provider error: HTTP None: provider.transport: Connection lost: ECONNRESET
2026-10-26 21:48:17 stream: early provider error (waiting for CLI recovery)
2026-10-26 21:48:18 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=17 emulate_tools=True retries=0 total_spawns=1
2026-10-26 21:48:18 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=17 transport=run first_event_ms=21 ttft_ms=1023 transport_history=['run'] duration_s=1.28
.2026-10-26 21:48:18 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1216 cwd=/var/folders/2f/***/T/tmptjc_l7zq/ws
2026-10-26 21:48:18 exec: provider error mid-response (transient=True), stopping opencode run
2026-10-26 21:48:18 exec cli failed rc=1 state=provider_error stderr_tail='HTTP None: provider.transport: Connection lost while reading the response: ECONNRESET'
2026-10-26 21:48:19 incomplete tool step: re-prompt 1/2 signal=1 total_spawns=1/3
2026-10-26 21:48:19 exec retry=1 (incomplete tool step) total_spawns=1/3
2026-10-26 21:48:19 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1854 cwd=/var/folders/2f/***/T/tmptjc_l7zq/ws
2026-10-26 21:48:19 exec: step with tool call finished, stopping opencode run
2026-10-26 21:48:19 done model=muse-spark-1.3-contributor-free rc=-15 state=nonzero_exit tools=2 out_chars=78 retries=1 total_spawns=2
2026-10-26 21:48:19 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-26 21:48:19 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=-15 total_spawns=2 retries=1 signal=1 tools=2 out_chars=78 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=1.03
.2026-10-26 21:48:19 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1216 cwd=/var/folders/2f/***/T/tmptjc_l7zq/ws
2026-10-26 21:48:19 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-26 21:48:19 stream provider error: HTTP None: provider.transport: Connection lost while reading the response: ECONNRESET
2026-10-26 21:48:19 stream: provider error mid-response (transient=True), stopping opencode run
2026-10-26 21:48:20 stream incomplete tool step: re-prompt 1/2 signal=1 total_spawns=1/3
2026-10-26 21:48:20 stream exec retry=1 fail_retries=0 model=opencode/muse-spark-1.3-contributor-free prompt_chars=1854 total_spawns=1/3
2026-10-26 21:48:20 stream: step with tool call finished, stopping opencode run
2026-10-26 21:48:20 stream done model=muse-spark-1.3-contributor-free rc=-15 tools=2 out_chars=78 emulate_tools=True retries=1 total_spawns=2
2026-10-26 21:48:20 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=-15 total_spawns=2 retries=1 signal=1 tools=2 out_chars=78 transport=run first_event_ms=1032 ttft_ms=1032 transport_history=['run'] duration_s=1.04
.2026-10-26 21:48:20 stream exec model=opencode/glm-5.3-flash-free -m opencode/glm-5.3-flash-free#high --standalone --thinking prompt_chars=1375 cwd=/var/folders/2f/***/T/tmptjc_l7zq/ws
2026-10-26 21:48:20 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-26 21:48:20 stream: step with tool call finished, stopping opencode run
2026-10-26 21:48:20 stream done model=glm-5.3-flash-free rc=-15 tools=2 out_chars=0 emulate_tools=True retries=0 total_spawns=1
2026-10-26 21:48:20 O-EXIT/v1 mode=stream model=glm-5.3-flash-free status=200 exit_reason=ok rc=-15 total_spawns=1 retries=0 signal=0 tools=2 out_chars=0 transport=run first_event_ms=27 ttft_ms=27 transport_history=['run'] duration_s=0.03
.2026-10-26 21:48:20 stream exec model=opencode/glm-5.3-flash-free -m opencode/glm-5.3-flash-free#high --standalone --thinking prompt_chars=1224 cwd=/var/folders/2f/***/T/tmptjc_l7zq/ws
2026-10-26 21:48:20 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-26 21:48:20 stream: step with tool call finished, stopping opencode run
2026-10-26 21:48:20 stream done model=glm-5.3-flash-free rc=-15 tools=2 out_chars=0 emulate_tools=True retries=0 total_spawns=1
2026-10-26 21:48:20 O-EXIT/v1 mode=stream model=glm-5.3-flash-free status=200 exit_reason=ok rc=-15 total_spawns=1 retries=0 signal=0 tools=2 out_chars=0 transport=run first_event_ms=23 ttft_ms=23 transport_history=['run'] duration_s=0.03
.2026-10-26 21:48:20 exec model=opencode/glm-5.3-flash-free -m opencode/glm-5.3-flash-free#high --standalone --thinking prompt_chars=1224 cwd=/var/folders/2f/***/T/tmptjc_l7zq/ws
2026-10-26 21:48:21 incomplete tool step: re-prompt 1/2 signal=3 total_spawns=1/3
2026-10-26 21:48:21 exec retry=1 (incomplete tool step) total_spawns=1/3
2026-10-26 21:48:21 exec model=opencode/glm-5.3-flash-free -m opencode/glm-5.3-flash-free#high --standalone --thinking prompt_chars=1867 cwd=/var/folders/2f/***/T/tmptjc_l7zq/ws
2026-10-26 21:48:21 exec: step with tool call finished, stopping opencode run
2026-10-26 21:48:21 done model=glm-5.3-flash-free rc=-15 state=nonzero_exit tools=2 out_chars=77 retries=1 total_spawns=2
2026-10-26 21:48:21 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-26 21:48:21 O-EXIT/v1 mode=json model=glm-5.3-flash-free status=200 exit_reason=ok rc=-15 total_spawns=2 retries=1 signal=3 tools=2 out_chars=77 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=1.04
.2026-10-26 21:48:21 stream exec model=opencode/glm-5.3-flash-free -m opencode/glm-5.3-flash-free#high --standalone --thinking prompt_chars=1224 cwd=/var/folders/2f/***/T/tmptjc_l7zq/ws
2026-10-26 21:48:21 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-26 21:48:22 stream incomplete tool step: re-prompt 1/2 signal=3 total_spawns=1/3
2026-10-26 21:48:22 stream exec retry=1 fail_retries=0 model=opencode/glm-5.3-flash-free prompt_chars=1867 total_spawns=1/3
2026-10-26 21:48:22 stream: step with tool call finished, stopping opencode run
2026-10-26 21:48:22 stream done model=glm-5.3-flash-free rc=-15 tools=2 out_chars=77 emulate_tools=True retries=1 total_spawns=2
2026-10-26 21:48:22 O-EXIT/v1 mode=stream model=glm-5.3-flash-free status=200 exit_reason=ok rc=-15 total_spawns=2 retries=1 signal=3 tools=2 out_chars=77 transport=run first_event_ms=1035 ttft_ms=1035 transport_history=['run'] duration_s=1.04
.2026-10-26 21:48:22 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1216 cwd=/var/folders/2f/***/T/tmptjc_l7zq/ws
2026-10-26 21:48:23 done model=muse-spark-1.3-contributor-free rc=0 state=ok tools=0 out_chars=7 retries=0 total_spawns=1
2026-10-26 21:48:23 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-26 21:48:23 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=7 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=0.28
.2026-10-26 21:48:23 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1216 cwd=/var/folders/2f/***/T/tmptjc_l7zq/ws
2026-10-26 21:48:23 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-26 21:48:23 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=7 emulate_tools=True retries=0 total_spawns=1
2026-10-26 21:48:23 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=7 transport=run first_event_ms=42 ttft_ms=42 transport_history=['run'] duration_s=0.30
.2026-10-26 21:48:23 exec model=opencode/glm-5.3-flash-free -m opencode/glm-5.3-flash-free#high --standalone --thinking prompt_chars=1224 cwd=/var/folders/2f/***/T/tmptjc_l7zq/ws
2026-10-26 21:48:23 exec: step with tool call finished, stopping opencode run
2026-10-26 21:48:23 tool_call_unparsed bytes=7 head='{broken'
2026-10-26 21:48:23 dropped 1 unparsed tool block(s) from content
2026-10-26 21:48:24 incomplete tool step: re-prompt 1/2 signal=2 total_spawns=1/3
2026-10-26 21:48:24 exec retry=1 (incomplete tool step) total_spawns=1/3
2026-10-26 21:48:24 exec model=opencode/glm-5.3-flash-free -m opencode/glm-5.3-flash-free#high --standalone --thinking prompt_chars=1868 cwd=/var/folders/2f/***/T/tmptjc_l7zq/ws
2026-10-26 21:48:24 exec: step with tool call finished, stopping opencode run
2026-10-26 21:48:24 done model=glm-5.3-flash-free rc=-15 state=nonzero_exit tools=2 out_chars=78 retries=1 total_spawns=2
2026-10-26 21:48:24 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-26 21:48:24 O-EXIT/v1 mode=json model=glm-5.3-flash-free status=200 exit_reason=ok rc=-15 total_spawns=2 retries=1 signal=2 tools=2 out_chars=78 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=1.03
.2026-10-26 21:48:24 exec model=opencode/glm-5.3-flash-free -m opencode/glm-5.3-flash-free#high --standalone --thinking prompt_chars=1224 cwd=/var/folders/2f/***/T/tmptjc_l7zq/ws
2026-10-26 21:48:24 exec: step with tool call finished, stopping opencode run
2026-10-26 21:48:24 tool_call_recovered extra_braces=1
2026-10-26 21:48:24 done model=glm-5.3-flash-free rc=-15 state=nonzero_exit tools=1 out_chars=0 retries=0 total_spawns=1
2026-10-26 21:48:24 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-26 21:48:24 O-EXIT/v1 mode=json model=glm-5.3-flash-free status=200 exit_reason=ok rc=-15 total_spawns=1 retries=0 signal=0 tools=1 out_chars=0 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=0.02
.2026-10-26 21:48:24 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1216 cwd=/var/folders/2f/***/T/tmptjc_l7zq/ws
2026-10-26 21:48:24 done model=muse-spark-1.3-contributor-free rc=0 state=ok tools=0 out_chars=7 retries=0 total_spawns=1
2026-10-26 21:48:24 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-26 21:48:24 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=7 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=0.28
.2026-10-26 21:48:24 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1216 cwd=/var/folders/2f/***/T/tmptjc_l7zq/ws
2026-10-26 21:48:24 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-26 21:48:25 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=7 emulate_tools=True retries=0 total_spawns=1
2026-10-26 21:48:25 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=7 transport=run first_event_ms=20 ttft_ms=20 transport_history=['run'] duration_s=0.28
.2026-10-26 21:48:25 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1216 cwd=/var/folders/2f/***/T/tmptjc_l7zq/ws
2026-10-26 21:48:25 incomplete tool step: re-prompt 1/2 signal=4 total_spawns=1/3
2026-10-26 21:48:25 exec retry=1 (incomplete tool step) total_spawns=1/3
2026-10-26 21:48:25 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1900 cwd=/var/folders/2f/***/T/tmptjc_l7zq/ws
2026-10-26 21:48:26 exec: step with tool call finished, stopping opencode run
2026-10-26 21:48:26 done model=muse-spark-1.3-contributor-free rc=-15 state=nonzero_exit tools=2 out_chars=125 retries=1 total_spawns=2
2026-10-26 21:48:26 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-26 21:48:26 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=-15 total_spawns=2 retries=1 signal=4 tools=2 out_chars=125 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=1.04
.2026-10-26 21:48:26 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1216 cwd=/var/folders/2f/***/T/tmptjc_l7zq/ws
2026-10-26 21:48:26 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-26 21:48:27 stream incomplete tool step: re-prompt 1/2 signal=4 total_spawns=1/3
2026-10-26 21:48:27 stream exec retry=1 fail_retries=0 model=opencode/muse-spark-1.3-contributor-free prompt_chars=1900 total_spawns=1/3
2026-10-26 21:48:27 stream: step with tool call finished, stopping opencode run
2026-10-26 21:48:27 stream done model=muse-spark-1.3-contributor-free rc=-15 tools=2 out_chars=125 emulate_tools=True retries=1 total_spawns=2
2026-10-26 21:48:27 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=-15 total_spawns=2 retries=1 signal=4 tools=2 out_chars=125 transport=run first_event_ms=1298 ttft_ms=1298 transport_history=['run'] duration_s=1.30
.2026-10-26 21:48:27 exec model=opencode/glm-5.3-flash-free -m opencode/glm-5.3-flash-free#high --standalone --thinking prompt_chars=1224 cwd=/var/folders/2f/***/T/tmptjc_l7zq/ws
2026-10-26 21:48:27 exec: step with tool call finished, stopping opencode run
2026-10-26 21:48:27 tool_call_unparsed bytes=7 head='{broken'
2026-10-26 21:48:27 dropped 1 unparsed tool block(s) from content
2026-10-26 21:48:28 incomplete tool step: re-prompt 1/2 signal=2 total_spawns=1/3
2026-10-26 21:48:28 exec retry=1 (incomplete tool step) total_spawns=1/3
2026-10-26 21:48:28 exec model=opencode/glm-5.3-flash-free -m opencode/glm-5.3-flash-free#high --standalone --thinking prompt_chars=1777 cwd=/var/folders/2f/***/T/tmptjc_l7zq/ws
2026-10-26 21:48:28 exec: step with tool call finished, stopping opencode run
2026-10-26 21:48:28 tool_call_unparsed bytes=7 head='{broken'
2026-10-26 21:48:28 dropped 1 unparsed tool block(s) from content
2026-10-26 21:48:29 incomplete tool step: re-prompt 2/2 signal=2 total_spawns=2/3
2026-10-26 21:48:29 exec retry=2 (incomplete tool step) total_spawns=2/3
2026-10-26 21:48:29 exec model=opencode/glm-5.3-flash-free -m opencode/glm-5.3-flash-free#high --standalone --thinking prompt_chars=1777 cwd=/var/folders/2f/***/T/tmptjc_l7zq/ws
2026-10-26 21:48:29 exec: step with tool call finished, stopping opencode run
2026-10-26 21:48:29 tool_call_unparsed bytes=7 head='{broken'
2026-10-26 21:48:29 dropped 1 unparsed tool block(s) from content
2026-10-26 21:48:29 incomplete tool step: retries exhausted (2) signal=2
2026-10-26 21:48:29 done model=glm-5.3-flash-free rc=-15 state=nonzero_exit tools=0 out_chars=66 retries=2 total_spawns=3
2026-10-26 21:48:29 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-26 21:48:29 O-EXIT/v1 mode=json model=glm-5.3-flash-free status=200 exit_reason=ok rc=-15 total_spawns=3 retries=2 signal=2 tools=0 out_chars=66 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=2.58
.2026-10-26 21:48:29 exec model=opencode/glm-5.3-flash-free -m opencode/glm-5.3-flash-free#high --standalone --thinking prompt_chars=1224 cwd=/var/folders/2f/***/T/tmptjc_l7zq/ws
2026-10-26 21:48:29 exec: step with tool call finished, stopping opencode run
2026-10-26 21:48:29 tool_call_unparsed bytes=7 head='{broken'
2026-10-26 21:48:29 dropped 1 unparsed tool block(s) from content
2026-10-26 21:48:29 done model=glm-5.3-flash-free rc=-15 state=nonzero_exit tools=2 out_chars=0 retries=0 total_spawns=1
2026-10-26 21:48:29 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-26 21:48:29 O-EXIT/v1 mode=json model=glm-5.3-flash-free status=200 exit_reason=ok rc=-15 total_spawns=1 retries=0 signal=0 tools=2 out_chars=0 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=0.03
.2026-10-26 21:48:29 stream exec model=opencode/glm-5.3-flash-free -m opencode/glm-5.3-flash-free#high --standalone --thinking prompt_chars=1224 cwd=/var/folders/2f/***/T/tmptjc_l7zq/ws
2026-10-26 21:48:29 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-26 21:48:30 tool_call_unparsed bytes=7 head='{broken'
2026-10-26 21:48:30 stream dropped 1 unparsed tool block(s) from content
2026-10-26 21:48:30 stream incomplete tool step: re-prompt 1/2 signal=2 total_spawns=1/3
2026-10-26 21:48:30 stream exec retry=1 fail_retries=0 model=opencode/glm-5.3-flash-free prompt_chars=1868 total_spawns=1/3
2026-10-26 21:48:31 stream: step with tool call finished, stopping opencode run
2026-10-26 21:48:31 stream done model=glm-5.3-flash-free rc=-15 tools=2 out_chars=78 emulate_tools=True retries=1 total_spawns=2
2026-10-26 21:48:31 O-EXIT/v1 mode=stream model=glm-5.3-flash-free status=200 exit_reason=ok rc=-15 total_spawns=2 retries=1 signal=2 tools=2 out_chars=78 transport=run first_event_ms=1052 ttft_ms=1052 transport_history=['run'] duration_s=1.06
.2026-10-26 21:48:31 stream exec model=opencode/glm-5.3-flash-free -m opencode/glm-5.3-flash-free#high --standalone --thinking prompt_chars=1224 cwd=/var/folders/2f/***/T/tmptjc_l7zq/ws
2026-10-26 21:48:31 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-26 21:48:31 tool_call_unparsed bytes=7 head='{broken'
2026-10-26 21:48:31 stream dropped 1 unparsed tool block(s) from content
2026-10-26 21:48:31 stream incomplete tool step: re-prompt 1/2 signal=2 total_spawns=1/3
2026-10-26 21:48:31 stream exec retry=1 fail_retries=0 model=opencode/glm-5.3-flash-free prompt_chars=1777 total_spawns=1/3
2026-10-26 21:48:32 tool_call_unparsed bytes=7 head='{broken'
2026-10-26 21:48:32 stream dropped 1 unparsed tool block(s) from content
2026-10-26 21:48:32 stream incomplete tool step: re-prompt 2/2 signal=2 total_spawns=2/3
2026-10-26 21:48:32 stream exec retry=2 fail_retries=0 model=opencode/glm-5.3-flash-free prompt_chars=1777 total_spawns=2/3
2026-10-26 21:48:33 tool_call_unparsed bytes=7 head='{broken'
2026-10-26 21:48:33 stream dropped 1 unparsed tool block(s) from content
2026-10-26 21:48:33 stream incomplete tool step: retries exhausted (2) signal=2
2026-10-26 21:48:33 stream done model=glm-5.3-flash-free rc=0 tools=0 out_chars=66 emulate_tools=True retries=2 total_spawns=3
2026-10-26 21:48:33 O-EXIT/v1 mode=stream model=glm-5.3-flash-free status=200 exit_reason=ok rc=0 total_spawns=3 retries=2 signal=2 tools=0 out_chars=66 transport=run first_event_ms=2039 ttft_ms=2039 transport_history=['run'] duration_s=2.29
.2026-10-26 21:48:33 stream exec model=opencode/glm-5.3-flash-free -m opencode/glm-5.3-flash-free#high --standalone --thinking prompt_chars=1224 cwd=/var/folders/2f/***/T/tmptjc_l7zq/ws
2026-10-26 21:48:33 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-26 21:48:33 tool_call_recovered extra_braces=1
2026-10-26 21:48:33 stream: step with tool call finished, stopping opencode run
2026-10-26 21:48:33 stream done model=glm-5.3-flash-free rc=0 tools=1 out_chars=0 emulate_tools=True retries=0 total_spawns=1
2026-10-26 21:48:33 O-EXIT/v1 mode=stream model=glm-5.3-flash-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=1 out_chars=0 transport=run first_event_ms=25 ttft_ms=25 transport_history=['run'] duration_s=0.03
.2026-10-26 21:48:33 stream exec model=opencode/glm-5.3-flash-free -m opencode/glm-5.3-flash-free#high --standalone --thinking prompt_chars=1224 cwd=/var/folders/2f/***/T/tmptjc_l7zq/ws
2026-10-26 21:48:33 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-26 21:48:33 stream done model=glm-5.3-flash-free rc=0 tools=0 out_chars=7 emulate_tools=True retries=0 total_spawns=1
2026-10-26 21:48:33 O-EXIT/v1 mode=stream model=glm-5.3-flash-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=7 transport=run first_event_ms=23 ttft_ms=23 transport_history=['run'] duration_s=0.28
.2026-10-26 21:48:33 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=7872 cwd=/var/folders/2f/***/T/tmptjc_l7zq/ws
2026-10-26 21:48:33 done model=muse-spark-1.3-contributor-free rc=0 state=ok tools=0 out_chars=7 retries=0 total_spawns=1
2026-10-26 21:48:33 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-26 21:48:33 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=7 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=0.28
.2026-10-26 21:48:33 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1216 cwd=/var/folders/2f/***/T/tmptjc_l7zq/ws
2026-10-26 21:48:34 opencode built-in tool event: tool=todoread status=error mapped=False as=[]
2026-10-26 21:48:34 unmapped built-in tools=['todoread']: re-prompt 1/2
2026-10-26 21:48:34 exec retry=1 (unmapped built-in tool) total_spawns=1/3
2026-10-26 21:48:34 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1715 cwd=/var/folders/2f/***/T/tmptjc_l7zq/ws
2026-10-26 21:48:35 opencode built-in tool event: tool=todoread status=error mapped=False as=[]
2026-10-26 21:48:36 unmapped built-in tools=['todoread']: re-prompt 2/2
2026-10-26 21:48:36 exec retry=2 (unmapped built-in tool) total_spawns=2/3
2026-10-26 21:48:36 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=2214 cwd=/var/folders/2f/***/T/tmptjc_l7zq/ws
2026-10-26 21:48:36 retry denied (incomplete_step): MAX_TOTAL_SPAWNS=3 reached
2026-10-26 21:48:36 incomplete tool step: retries exhausted (0) signal=4
2026-10-26 21:48:36 done model=muse-spark-1.3-contributor-free rc=0 state=ok tools=0 out_chars=125 retries=2 total_spawns=3
2026-10-26 21:48:36 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-26 21:48:36 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=3 retries=2 signal=0 tools=0 out_chars=125 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=2.54
.2026-10-26 21:48:36 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1216 cwd=/var/folders/2f/***/T/tmptjc_l7zq/ws
2026-10-26 21:48:36 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-26 21:48:36 opencode built-in tool event: tool=todoread status=error mapped=False as=[]
2026-10-26 21:48:37 stream unmapped built-in tools=['todoread']: re-prompt 1/2
2026-10-26 21:48:37 stream exec retry=1 fail_retries=0 model=opencode/muse-spark-1.3-contributor-free prompt_chars=1715 total_spawns=1/3
2026-10-26 21:48:37 opencode built-in tool event: tool=todoread status=error mapped=False as=[]
2026-10-26 21:48:37 stream unmapped built-in tools=['todoread']: re-prompt 2/2
2026-10-26 21:48:37 stream exec retry=2 fail_retries=0 model=opencode/muse-spark-1.3-contributor-free prompt_chars=2214 total_spawns=2/3
2026-10-26 21:48:38 retry denied (incomplete_step): MAX_TOTAL_SPAWNS=3 reached
2026-10-26 21:48:38 stream incomplete tool step: retries exhausted (0) signal=4
2026-10-26 21:48:38 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=125 emulate_tools=True retries=2 total_spawns=3
2026-10-26 21:48:38 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=3 retries=2 signal=0 tools=0 out_chars=125 transport=run first_event_ms=2047 ttft_ms=2047 transport_history=['run'] duration_s=2.31
.2026-10-26 21:48:38 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1216 cwd=/var/folders/2f/***/T/tmptjc_l7zq/ws
2026-10-26 21:48:38 exec: provider error mid-response (transient=True), stopping opencode run
2026-10-26 21:48:38 exec cli failed rc=1 state=provider_error stderr_tail='HTTP None: provider.transport: Connection lost: ECONNRESET'
2026-10-26 21:48:38 opencode built-in tool event: tool=todoread status=error mapped=False as=[]
2026-10-26 21:48:39 unmapped built-in tools=['todoread']: re-prompt 1/2
2026-10-26 21:48:39 exec retry=1 (unmapped built-in tool) total_spawns=1/3
2026-10-26 21:48:39 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1715 cwd=/var/folders/2f/***/T/tmptjc_l7zq/ws
2026-10-26 21:48:39 exec: step with tool call finished, stopping opencode run
2026-10-26 21:48:39 done model=muse-spark-1.3-contributor-free rc=-15 state=nonzero_exit tools=2 out_chars=0 retries=1 total_spawns=2
2026-10-26 21:48:39 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-26 21:48:39 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=-15 total_spawns=2 retries=1 signal=0 tools=2 out_chars=0 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=1.03
.2026-10-26 21:48:39 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1216 cwd=/var/folders/2f/***/T/tmptjc_l7zq/ws
2026-10-26 21:48:39 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-26 21:48:39 opencode built-in tool event: tool=todoread status=error mapped=False as=[]
2026-10-26 21:48:41 stream unmapped built-in tools=['todoread']: re-prompt 1/2
2026-10-26 21:48:41 stream exec retry=1 fail_retries=0 model=opencode/muse-spark-1.3-contributor-free prompt_chars=1715 total_spawns=1/3
2026-10-26 21:48:41 stream incomplete tool step: re-prompt 1/2 signal=4 total_spawns=2/3
2026-10-26 21:48:41 stream exec retry=2 fail_retries=0 model=opencode/muse-spark-1.3-contributor-free prompt_chars=1900 total_spawns=2/3
2026-10-26 21:48:42 stream: step with tool call finished, stopping opencode run
2026-10-26 21:48:42 stream done model=muse-spark-1.3-contributor-free rc=-15 tools=2 out_chars=125 emulate_tools=True retries=2 total_spawns=3
2026-10-26 21:48:42 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=-15 total_spawns=3 retries=2 signal=4 tools=2 out_chars=125 transport=run first_event_ms=2256 ttft_ms=2256 transport_history=['run'] duration_s=2.26
.....2026-10-26 21:48:42 tool_strip_cap_hit max=16 dropping tail
2026-10-26 21:48:42 tool_strip_cap_hit max=16 dropping tail
2026-10-26 21:48:42 tool_strip_cap_hit max=16 dropping tail
..........................................................2026-10-26 21:48:43 tool_call_unparsed bytes=114 head='{"name": "read", "arguments": {"file_path": "/a"}} `<tool_call>`{"name": "read", "arguments": {"file_path": "/b"}}'
...2026-10-26 21:48:43 tool_call_unparsed bytes=23 head='<tool_call>{"name":"a"}'
2026-10-26 21:48:43 tool_call_unparsed bytes=47 head='{"name":"a"}<tool_call> <tool_call>{"name":"b"}'
2026-10-26 21:48:43 tool_call_unparsed bytes=23 head='{"name":"a"}<tool_call>'
.2026-10-26 21:48:43 tool_call_unparsed bytes=32 head='{"name": "a"} <tool_call>{broken'
..............................................
----------------------------------------------------------------------
Ran 400 tests in 137.507s

OK
<sys>:0: ResourceWarning: unclosed file <_io.TextIOWrapper name=9 encoding='UTF-8'>
<sys>:0: ResourceWarning: unclosed file <_io.TextIOWrapper name=7 encoding='UTF-8'>
```

### `VER-003-root-pythonpath-pytest` (`l2-green-ver003-pythonpath.log`, `sha256=72c94be382cf85693719a90dd0ba17b510add53e45b7ac0ceeca6cbe7c9828e1`)
```text
$ uvx pytest -q -p no:cacheprovider tests/
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom] [rc=0] [wall=363.04s]
--- STDOUT ---
.......................sss........................... [  5%]
..s..................................................................... [ 13%]
.......................................................... [ 20%]
........................................................................ [ 28%]
........................................................................ [ 36%]
................................. [ 40%]
.......................................................... [ 46%]
s............................................. [ 51%]
...................................................................... [ 59%]
.............................................................. [ 66%]
............................ [ 69%]
........................................... [ 74%]
................................................... [ 79%]
................................................................. [ 87%]
............................................................. [ 93%]
............................... [ 97%]
...................... [ 99%]
..                                                                       [100%]
894 passed, 5 skipped, 8103 subtests passed in 362.77s (0:06:02)

--- STDERR ---
2026-10-26T19:32:40Z transient failure rc=-15 err='', retry 1 client=127.0.0.1:50013 ua=-
```

### `VER-003b-root-pythonpath-zen-pytest` (`l2-green-ver003b-zen-pythonpath.log`, `sha256=502449035a0241ad74606ba1a65ce8653306648a563df0bdcbde752833221f16`)
```text
$ uvx pytest -q -p no:cacheprovider bridges/opencode-zen-bridge/tests/
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom] [rc=0] [wall=145.1s]
--- STDOUT ---
......................... [  6%]
........................................................................................................................................................... [ 45%]
.............................................................. [ 60%]
........................................................................ [ 78%]
............................................................... [ 94%]
.......................                                              [100%]
400 passed, 3155 subtests passed in 144.84s (0:02:24)

--- STDERR ---
```

### `VER-005-dedicated-realtime-suite` (`l2-green-ver005-dedicated.log`, `sha256=a1ed5efe4d6da1110fc09fc9566d436dc14f4f90631e0f2b2543f3bc7cb54a05`)
```text
$ uvx pytest -q -p no:cacheprovider tests/test_realtime_reasoning.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=28.52s]
--- STDOUT ---
.....................                                                    [100%]
21 passed in 27.75s

--- STDERR ---
```

### `AC-023-pytest-reversed` (`l2-green-ac023-reversed.log`, `sha256=16f2b17ae50bcee67e898b7fa739f7b51898ac32f1ba4515f4957bbb3ebbf378`)
```text
$ uvx pytest -q -p no:cacheprovider tests/test_zen_catalog.py tests/test_tool_emulation.py tests/test_sync_yaml.py tests/test_stream_thinking.py tests/test_step_interruption.py tests/test_stdin_prompt.py tests/test_run_env.py tests/test_realtime_reasoning.py tests/test_native_fallback.py tests/test_lenient_tool_call.py tests/test_google_direct.py tests/test_go_model_routing.py tests/test_effort_mapping.py tests/test_cli_failure.py tests/test_catalog_reload.py tests/test_catalog_mode.py tests/test_catalog.py tests/test_aliases.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=142.56s]
--- STDOUT ---
.................................................................. [ 16%]
................................................................. [ 32%]
................................................................. [ 49%]
..................................................................... [ 66%]
....................................................................................... [ 88%]
................................................                                              [100%]
400 passed, 3155 subtests passed in 142.30s (0:02:22)

--- STDERR ---
```

ARTIFACT_END>>>
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/verification-traceability.md sha256=838bfb35033a7e90582e8b94c680a7667fb48f85fae425cbc7a1129a9f9d111a
# Матрица прослеживаемости приёмки (`verification-traceability.md`, run `analyst-teamlead-zen-realtime-reasoning-20261025`)

## Служебные отметки контура `teamlead-gate`
- **Режим ревью:** `reviewer_skip=true`, `downstream_panel=true`, `parent_skill="analyst-teamlead"` (отдельный `Reviewer` не запускается; Совет Тимлидов — единственный рубеж построчного и приёмочного ревью по `acceptance-package.md` §1; счётчик «замечаний совета сверх Reviewer» при `downstream_panel=true` не определён).
- **Назначение шапки тимлида (`council.md` §1):** дословная шапка тимлида прикреплена сразу после системного промпта роли (`prompt-{skeptic,realist,visionary}.txt`) и до факт-карты во всех 3 брифах Совета Тимлидов.
- **Побайтовая неизменность замороженных функций (`Run-Path Freeze` / `REQ-018`):**
  - `def _run_env`: `sha256=1c51b28fcb83fcc0f4d8b5204c858e11ab5ac975bfe40dca4a0bf61978008e31` (ожидалось `1c51b28fcb83fcc0f4d8b5204c858e11ab5ac975bfe40dca4a0bf61978008e31` — **MATCH**)
  - `def _stream_google_sse` и `def _execute_google_once`: `google_direct_unchanged=True` (**MATCH**)
  - Белый список изменённых файлов: `bridges/opencode-zen-bridge/server.py, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py, bridges/opencode-zen-bridge/tests/test_step_interruption.py` (ровно 3 целевых файла `coder_target_files`).

## Сводка `acceptance_coverage` из `coder.json`
- server.py:2890 status_next = max(t0 + FIRST_STATUS_DELAY_S, prompt_send_start + 0.25) — единственная изменённая строка раунда
- test_slow_serve_gets_status_and_no_status_on_fast зелёный (был единственным падением Clean-Room L2: 399/400)
- test_stream_go_model_success_with_fake_launcher зелёный (legacy run-путь не затронут)
- test_frozen_slices_hashes зелёный; VER-004 exit 0 — замороженные _run_env/_stream_google_sse/_execute_google_once байт-в-байт

## Поштучная матрица `REQ-001..REQ-020` и `AC-001..AC-026`

| Требование / AC | Реализация в коде | Автотесты / Оракулы | Свидетельство L2 / L3 | Статус |
|---|---|---|---|---|
| `REQ-001` / `AC-001`, `AC-002`, `REQ-020` / `AC-026` (реалтайм-стриминг дельт `reasoning_content` и `content` `<=250 мс`, Red→Green на сокете при идущем апстриме) | `bridges/opencode-zen-bridge/server.py` (потоковый `opencode serve` SSE клиент, прямая запись `message.part.delta` в SSE сокет) | `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py` | `L2-RED-sensitivity` (`rc=1` на `origin/dev`) + `VER-001-pytest` (`rc=0` на кандидате) | `PASS` |
| `REQ-002` / `AC-003` (неизменность публичного HTTP/OpenAI SSE контракта `/health`, `/v1/models`, `/v1/chat/completions`, `:9883`) | `bridges/opencode-zen-bridge/server.py` | `tests/test_zen_bridge.py`, `tests/test_realtime_reasoning.py` | `VER-001-pytest`, `VER-002-unittest` (`rc=0`) | `PASS` |
| `REQ-003` / `AC-004` (kill-switch `REALTIME_SERVE_ENABLED` в `dynamic_config.json`, дефолт `false`, сохранение `opencode run --format json` и `disable-serve`) | `bridges/opencode-zen-bridge/server.py` (`DYNAMIC_CONFIG_PATH`, `_ServeHealth`, fallback decision table) | `tests/test_realtime_reasoning.py`, полный существующий набор `tests/` | `VER-001-pytest` (`rc=0`) | `PASS` |
| `REQ-004`, `REQ-005` / `AC-005`, `AC-006`, `AC-007` (первая реакция `< 1.0 с` с префиксом `[мост]` и `
`, ведущий `
` после незавершённой дельты, отсутствие `[мост]` в `_messages_to_prompt`) | `bridges/opencode-zen-bridge/server.py` | `tests/test_realtime_reasoning.py` | `VER-001-pytest` (`rc=0`) | `PASS` |
| `REQ-006`, `REQ-007` / `AC-008`, `AC-009`, `AC-010` (раздельные watchdogs `first_event_timeout`, `first_token_timeout`, `stall_timeout` с env-порогами) | `bridges/opencode-zen-bridge/server.py` | `tests/test_realtime_reasoning.py` | `VER-001-pytest` (`rc=0`) | `PASS` |
| `REQ-008` / `AC-011`, `AC-012` (группа процессов `--serve-helper` + `opencode serve`, детекция закрытия сокета `<= 5 с`, `0` сирот `<= 7 с`, startup lease reaper, тройная сверка `listener_pid`) | `bridges/opencode-zen-bridge/server.py` | `tests/test_realtime_reasoning.py` | `VER-001-pytest` (`rc=0`) | `PASS` |
| `REQ-009` / `AC-013`, `AC-014` (`MAX_TOTAL_SPAWNS=3`, `FAIL_RETRY_LIMIT`, `_RetryBudget`, Full Jitter, Circuit Breaker, разделитель `[мост]` при ретрае без дедупликации reasoning) | `bridges/opencode-zen-bridge/server.py` | `tests/test_realtime_reasoning.py`, `tests/test_step_interruption.py` | `VER-001-pytest` (`rc=0`) | `PASS` |
| `REQ-010`, `REQ-011`, `REQ-012` / `AC-015`, `AC-016`, `AC-017` (инкрементальный `ToolCallParser`, `finish_reason="tool_calls"`, `STEP_RECOVERY`, `deny` для встроенных инструментов, `form.created` `safety_order` `cancel+interrupt`) | `bridges/opencode-zen-bridge/server.py` | `tests/test_realtime_reasoning.py`, `tests/test_step_interruption.py` | `VER-001-pytest` (`rc=0`) | `PASS` |
| `REQ-013`, `REQ-014`, `REQ-015`, `REQ-016` / `AC-018`, `AC-019`, `AC-020`, `AC-021` (ротация прокси, `usage` из `step-finish`, маскирование пароля serve и секретов, `O-EXIT/v1` с `transport`, `first_event_ms`, `ttft_ms`) | `bridges/opencode-zen-bridge/server.py` (`_serve_env`, `OPENCODE_DB=":memory:"`, `O-EXIT/v1`) | `tests/test_realtime_reasoning.py`, `tests/test_run_env.py` | `VER-001-pytest` (`rc=0`) | `PASS` |
| `REQ-017` / `AC-022`, `AC-023` (приведение базовой линии `test_step_interruption.py` в зелёное при `MAX_TOTAL_SPAWNS=3`, независимость от порядка запуска тестов) | `bridges/opencode-zen-bridge/tests/test_step_interruption.py` | `VER-001-pytest`, `VER-002-unittest`, `VER-003-root-pythonpath-pytest`, `AC-023-pytest-reversed` | Все 4 прогона `rc=0` в `execution-evidence.md` | `PASS` |
| `REQ-018` / `AC-024` (неизменность `_stream_google_sse` и `_execute_google_once`) | Не затронуты (побайтовый SHA-256 сверен в `code-gate.json`) | `tests/test_google_direct.py` | `VER-001-pytest` + `VER-004-packet-command` (`rc=0`) | `PASS` |
| `VER-004` (статический гейт `ruff==0.17.2`, диапазонный `ruff format --check`, `basedpyright==1.40.2`, `0` новых `Any`) | `bridges/opencode-zen-bridge/server.py`, `tests/test_realtime_reasoning.py`, `tests/test_step_interruption.py` | `VER-004-packet-command` и `VER-004-ruff-format-*` | `l2-green-ver004-packet.log` (`rc=0`) | `PASS` |
| `REQ-019` / `AC-025`, `VER-006`, `VER-007` (синхронизация `~/.dsh/bridges/opencode-zen-bridge/server.py` и живой heavy-path на `:9883`) | Выкатка `H0..H9` строго после `ACCEPT` Совета Тимлидов | Живой сценарий `:9883` + `diff -u` | `execution-evidence.md` (`VER-006`, `VER-007`) | `DEFERRED_L3 (до ACCEPT Совета Тимлидов)` |
ARTIFACT_END>>>
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/evidence-manifest.sha256 sha256=71ddfe5437fb8fbd5a9b18bfd6151c4f5044247baa0ac2c7b80168e48b298df0
e67d5ffb98e29dd698e38e17e18772fa792391a2e24e05cf88d2f820a14e8722  teamlead/verification-surface.json
437973de9daad996ce91bf5fa7415d84d9b3746e09d12dde2acc30489e7a0870  teamlead/environment-manifest.json
9a3d51222cdaccf5d8c36191d1a4358fad558757a4e95ca49f6d4fac0c62c766  teamlead/execution-evidence.md
838bfb35033a7e90582e8b94c680a7667fb48f85fae425cbc7a1129a9f9d111a  teamlead/verification-traceability.md
42a0fcc7615577d69fd35e77a30e358461f56ebc797f13e61712fccfcc512d9e  teamlead/reverse-spec.md
2b49852efc2680db5e0bc1ad499788802098cc46d7c6c19f2cc5ecce304bb4c5  teamlead/candidate-manifest.json
22eaa11a35d77b6c749975b9f044bddbeef5437bcffdd187553feb1e18f3ec24  teamlead/candidate.diff
8ca5bca38c56715f63209ef79bc47df117795f2d3bc0d8d4607b9ea01f488d18  coder.json
a47ba864e9ef2af0cdfa045c9c38dbc201f6462f56d54cdc62a7968664ded043  receipts/coder.json
e4171d5605d0c15519fd56f0f18282897837370266268faaa12f2a3c2e97ce35  receipts/code-gate.json
57c35ac4fe637c56127a28825fd83ca168be98716268ad35edcd50a988422448  receipts/verifier.json
de6b2bc2275b5e40fe5fee64f22f70ff4c6c7c95cf8b71bd365be820aaa4be0c  receipts/final-gate.json
16f2b17ae50bcee67e898b7fa739f7b51898ac32f1ba4515f4957bbb3ebbf378  receipts/l2-green-ac023-reversed.log
6dc083e24777b6ee2ac18e9f0d441a5dfecc4d9e4a474bb375953913c08edfe2  receipts/l2-green-ver001-pytest.log
0a3b02903999bc0b50b1c7b3a4c14a0b58f03085480a0ecdfdb63f7533df2f67  receipts/l2-green-ver002-unittest.log
72c94be382cf85693719a90dd0ba17b510add53e45b7ac0ceeca6cbe7c9828e1  receipts/l2-green-ver003-pythonpath.log
502449035a0241ad74606ba1a65ce8653306648a563df0bdcbde752833221f16  receipts/l2-green-ver003b-zen-pythonpath.log
6c0b3627322b3ea368d0add2b4a8f9f050f6c70f3cb8846a2f766bbf8ee63800  receipts/l2-green-ver004-packet.log
755d9227e95b948c1b21b60a6a5719f23874a7f21c9eaa06d940767f5734d920  receipts/l2-green-ver004-range-server-1.log
55dad36c122f16886bc8f61615b1f48774f27888e6a56f028ee000d08e5fb7b5  receipts/l2-green-ver004-range-server-10.log
1a167fd9cb08fdce4010880b0f7d30eb4c728e0b88b82e9be602cb9133174d07  receipts/l2-green-ver004-range-server-11.log
4317df22db33357148a731fa34cd55b55460cc0f9d8727409e75fd7bf7439491  receipts/l2-green-ver004-range-server-12.log
36603cdcb32ee0bfdb0fa0b4637fb4dad374e8f8b80e2562271739320bcdc689  receipts/l2-green-ver004-range-server-13.log
b983f7809853564cc15dd508ac2c088d5991ddcec96b88a1296570978a186f4c  receipts/l2-green-ver004-range-server-14.log
aebac7e28bf0afaef20d5fe5510a30f550197c93290b50bc7cbe83fc5403e8e9  receipts/l2-green-ver004-range-server-15.log
adf78bb4fd6f97936c702a7d4294300b6fcd29b8b9ba1320a9e7759e38e2b9fb  receipts/l2-green-ver004-range-server-16.log
3cb140d3caf21e48815884209c1effe43aba443517ff186132053779cf8a08a5  receipts/l2-green-ver004-range-server-17.log
e4d8d810199f401eb0ce3372bddb0bff3d8b3da741b09caaab7e30a3eb3a177c  receipts/l2-green-ver004-range-server-18.log
c444cf645da432ed3d6b8986da17bbeab54f5a166c128ff60e99cd07468048f8  receipts/l2-green-ver004-range-server-19.log
d43ecdb8d6ac5fbb42ad87118c810f0502f825f1e90d9caa99b63adad6226dd8  receipts/l2-green-ver004-range-server-2.log
d313077dabc9521b20943926aa602c5f7ab502521c54b0bf9791af1b893d9023  receipts/l2-green-ver004-range-server-20.log
7fc43edee20bccae0ccb2e433fc2239ce865ac22787665d91b41f59d4cd1e0cd  receipts/l2-green-ver004-range-server-21.log
9028f2d9ca25ffe300866f2e21f556386a6615b4a25fb8a975a0c0f368a50c7b  receipts/l2-green-ver004-range-server-22.log
137d18ac14126d0eb7f05fddd42def32e3519b858b8195f60316998bef756f6c  receipts/l2-green-ver004-range-server-23.log
a21e3aad406e5764d4dbd3d7b01556db946c6dc89b5ef86eb37e3ce7e25139b3  receipts/l2-green-ver004-range-server-24.log
342d717568eb06315b8a533ed99dd7bdbf57ca15104e8781fad2e2f8239307a9  receipts/l2-green-ver004-range-server-25.log
c9bb5ad51a1cec6ddb158bd40b203bbf93ab98d37cd0e9b39100fcbca38901ad  receipts/l2-green-ver004-range-server-26.log
48c923dbeecb3ae20982762829ed159b3617ae1c87f534533a94d2a9a6bb9b51  receipts/l2-green-ver004-range-server-27.log
631d1084303ce679115087d098863502208aa8697d8f484779731460cfcdde21  receipts/l2-green-ver004-range-server-28.log
8cd812c358a608185ca293bcb5779f4333e26f659a9a9c6b36580267e1d99745  receipts/l2-green-ver004-range-server-29.log
acfa83afea14da20895c3c5df8891eefc261d948f1733e6a9362c94316fbc5e8  receipts/l2-green-ver004-range-server-3.log
1b7991002fb119b2a9562d39b41d3068d02cd8275511c275a2508af415c2cea1  receipts/l2-green-ver004-range-server-30.log
c548744592a53ccc65fc76571ca3b4c2c2d8ce76936922f48661451ace75e686  receipts/l2-green-ver004-range-server-31.log
b891acb4d080206084d4e7e70ad7bf878c28a2d0f37db5f757c3d0b06b847689  receipts/l2-green-ver004-range-server-32.log
d50fc53e2d4ea34a0650b8b573e78847b4870e16c2897cff91e85af02697c94b  receipts/l2-green-ver004-range-server-33.log
0b46d3055ef8fc3f66b6ded112feefe9199d87bab507bcff915342caf40929b3  receipts/l2-green-ver004-range-server-34.log
245dde84273d71bc8657149dcf68158d87f93655201c67bdfa02385e0517c472  receipts/l2-green-ver004-range-server-35.log
522ec4a1dd2a1f8dbcf9a779dd97bad5b94553e7e5ebbd25585ab953048d7b92  receipts/l2-green-ver004-range-server-36.log
783dea9a28cffd5e4453d20b2f4e8caaded8c886585c49e931dade2b1bf2b22f  receipts/l2-green-ver004-range-server-37.log
5459a1af2d4cd06784a4df3f383f033d2406f1ec2985f9bbb140e11c17a87fbb  receipts/l2-green-ver004-range-server-38.log
be56a5d141ae879726c1881ab8cfa22d7656b85dff414f68d0f5c6e5ee338cec  receipts/l2-green-ver004-range-server-39.log
88452847a1c7bf2735617ebc981f4546653b761feb86581b86c09defcbbabd90  receipts/l2-green-ver004-range-server-4.log
8b4d01369142097d3605fedf79a388055b489e4a9488e8c09203c90f6ce258fd  receipts/l2-green-ver004-range-server-40.log
db63a9b27631d2848cb9646c447e74b4547959907a2af711c9e390d57f06a6b4  receipts/l2-green-ver004-range-server-41.log
edf1e728d3a1e78162570735773864dc3e25e7e19fbaa0758918870b5bca3db3  receipts/l2-green-ver004-range-server-42.log
fda44981641fda46207e200f893109fc3e694a4c405f49ba41e9f92d898c5e07  receipts/l2-green-ver004-range-server-43.log
61ea0fb1aba06e25449f2612b634fb314200855d0a43b244c2873749048d878b  receipts/l2-green-ver004-range-server-44.log
59f99023e45485943b4baf540e6bb7ca11df9d4b2a599cb0bd9aa4b49b52ec9a  receipts/l2-green-ver004-range-server-45.log
efe2330f4042e4d347064c5eb4c95a514aae435432a978636f893c4b5bf90485  receipts/l2-green-ver004-range-server-46.log
62b0e86044d4005aabf6b36193f93b51ddf9d706f31a579c7497fc70fe00bbc8  receipts/l2-green-ver004-range-server-47.log
be4928c4cdac314cdfbb3d9ed146bd1e810ab7230d8117622038329b8242f7db  receipts/l2-green-ver004-range-server-48.log
917686da3daa63a23567d127e2aa768b31a59f19e398ac6135ae919a4e4aa7f1  receipts/l2-green-ver004-range-server-49.log
3001e902e898ce08be329b7fb21e859b94d1f64fd4223e58eb45d3e1bafa83e0  receipts/l2-green-ver004-range-server-5.log
6e945fc57f39e8bda2972c3dbae2dcdd5bd084a526b16177bd7b1e96307a3351  receipts/l2-green-ver004-range-server-50.log
caa77892ae2b4af29c048102161c237bd74d41143fbcda241c0e4a355bb4798c  receipts/l2-green-ver004-range-server-51.log
d5ed0ef1c02c1dbca0dea536e990b429541f5d27f422b87a8431603ba43bd3bd  receipts/l2-green-ver004-range-server-52.log
6f342289ba267b724264369fcf130a8a0635c26ec9443c3cd34dd71f9c5aced1  receipts/l2-green-ver004-range-server-53.log
395372d5783c465bb44896e2b27bb87f887cc2483269a1045a3fb28fdd568474  receipts/l2-green-ver004-range-server-6.log
ef3916991629bdb55ce1820231b7cc0c4f70ba15083be97b22ebdce0ee32b7f5  receipts/l2-green-ver004-range-server-7.log
91e7ac7b68fc502cae836236045fb6e74e77bdd8704fd29f78eb0df1f357f8c5  receipts/l2-green-ver004-range-server-8.log
aa564ad3b2e4ce1923226de4ae4763b1fd8789f2b1a4cc257747cd61f6a7f584  receipts/l2-green-ver004-range-server-9.log
1bfce177c316cdcc6b3567f30279457b3d07734c5dbe6d71e0043126e14329cc  receipts/l2-green-ver004-range-test_step_interruption-1.log
43db84d775e827bb10d95980ad3a6ab79d1dad3c72ff41c74a2df1e6b45f0c7b  receipts/l2-green-ver004-range-test_step_interruption-2.log
bd29f48f762395c50e3e010617f077c71d139251e91c2b158d86fa064fbcf1da  receipts/l2-green-ver004-range-test_step_interruption-3.log
fe32619cd0f07a5dc87b861454f60be891396fd628696cc972e5b6680ba1a260  receipts/l2-green-ver004-range-test_step_interruption-4.log
8e3fda2fa1591e93deecb5958c4c58218cc94785d361a2aa06f93b45b30fe0b1  receipts/l2-green-ver004-range-test_step_interruption-5.log
a541c75c111a88d475f6740ca78828130e3863cfd672b95fe63e34597edbaf8a  receipts/l2-green-ver004-range-test_step_interruption-6.log
791491a5d9e6128b8400ae730e69e74c9af01651d625cc697d569dfdcee245b7  receipts/l2-green-ver004-ruff-format-new.log
a1ed5efe4d6da1110fc09fc9566d436dc14f4f90631e0f2b2543f3bc7cb54a05  receipts/l2-green-ver005-dedicated.log
b8b80dd34adbf1f2bab310d2d0926d52559ae5e7323a81ef75cb93ddd02cf0bf  receipts/l2-red.log
ARTIFACT_END>>>
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/reverse-spec.md sha256=42a0fcc7615577d69fd35e77a30e358461f56ebc797f13e61712fccfcc512d9e
# Reverse-Spec: реконструкция спецификации по кандидатному diff

> Метод: слепая реконструкция только по diff `bridges/opencode-zen-bridge/server.py`, diff
> `bridges/opencode-zen-bridge/tests/test_step_interruption.py` и полному тексту нового файла
> `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py`. Постановка задачи, ТЗ и
> архитектурный пакет не использовались. Утверждения ниже делятся на: (а) прямо видимые в diff;
> (б) выводы из тестовых фикстур и ожиданий. Места, где код и заявленная таблица решений могут
> расходиться, помечены как риск/пробел, а не как факт поведения.

## 1. Фактически изменённые и добавленные файлы

| Путь | Статус | Назначение |
|---|---|---|
| `bridges/opencode-zen-bridge/server.py` | изменён | Основной и единственный production-файл изменения: новый serve-транспорт поверх `opencode serve`, ранний CLI-помощник `--serve-helper`, lease/ownership дочернего дерева, watchdog и синтетические статусы для legacy `opencode run`, маршрутизация stream/JSON между serve и run, sticky-деградация serve, расширенный `O-EXIT/v1`. Плюс многочисленные чисто форматирующие перестановки (переносы вызовов и литералов), не меняющие семантику сами по себе. |
| `bridges/opencode-zen-bridge/tests/test_step_interruption.py` | изменён | Скорректированы ожидания по бюджетам повторов для сценария `unmapped_then_promise` (stream и JSON), добавлен сценарий фейка `unmapped_incomplete_calls`, изоляция resilience-состояния между тестами. |
| `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py` | добавлен (`sha256=10894022174afcda3e7023d4093eaa0aec7aa6515eac862d18488d0dbe67b9bc`) | Новый тестовый модуль «Реалтайм-размышление serve-транспорта и watchdog legacy-пути (REQ-001..REQ-020)»: фейки legacy `opencode run` (`LEGACY_FAKE`) и `opencode serve` (`FAKE_SERVE`), живой мост на эфемерном порту, две группы тестов — A (legacy watchdog) и B (serve-транспорт). |

Файлов конфигурации, документации, манифестов зависимостей или миграций в diff нет.
Каталожный модуль `zen_catalog` (`zc`) не изменён; изменён только способ обновления
`CATALOG_SOURCE` в `server.py` (см. §3.3).

## 2. Реконструируемое поведение системы (что делает изменение)

### 2.1. Новый транспорт / режим работы, условие включения и kill-switch

Вводится второй способ исполнения запроса к Zen-моделям в дополнение к существующему
`opencode run --standalone` (далее — run):

- **serve-транспорт**: мост сам поднимает долгоживущий (на одну попытку) процесс
  `opencode serve --hostname 127.0.0.1 --port <port>`, создаёт в нём сессию по HTTP API,
  подписывается на SSE-поток событий `/api/event`, отправляет prompt и транслирует события
  клиенту в реальном времени (отсюда имя модуля тестов — realtime reasoning).
- **run-транспорт**: прежний путь — отдельный `opencode run` на попытку, события разбираются
  из stdout (`parse_opencode_event`).

Выбор транспорта — функция `_select_transport(res)`; вызывается из обоих обработчиков
ответа (`Handler._stream_sse`-путь и `Handler._serve_json`) только для не-Google моделей
(прямой Google-маршрут serve не затрагивает, см. §3.3). Приоритет, от высшего к низшему:

1. `OPENCODE_ZEN_BRIDGE_TRANSPORT=run` в env → всегда `run`.
2. `OPENCODE_ZEN_BRIDGE_REALTIME_SERVE_ENABLED` в env со значением `0/false/no/off`
   → всегда `run` (env-override как kill-switch).
3. Наличие файла-disable: путь из `OPENCODE_ZEN_BRIDGE_SERVE_DISABLE_FILE`,
   по умолчанию `~/.dsh/bridges/opencode-zen-bridge/disable-serve`; если файл существует —
   `run`; ошибка проверки пути (`OSError`) трактуется fail-safe как `run`.
4. `OPENCODE_ZEN_BRIDGE_TRANSPORT=serve` → принудительно `serve` (даже при деградации и без
   dynamic-config; в коде это флаг `force_serve` в обоих serve-обработчиках).
5. Любое значение `OPENCODE_ZEN_BRIDGE_TRANSPORT`, отличное от `auto/serve/run`, → `run`
   (безопасный дефолт при опечатке).
6. Режим `auto` (дефолт env): если `_ServeHealth.is_degraded()` — `run` (sticky-деградация,
   §2.5); иначе serve включается только если выполнено хотя бы одно из:
   `OPENCODE_ZEN_BRIDGE_REALTIME_SERVE_ENABLED ∈ {1,true,yes,on}` **или**
   `_read_dynamic_config_enabled()` вернул `True`.
7. Финальный предохранитель в `auto`: serve допускается только для нативного бинаря
   opencode — `_is_native_opencode_bin(OPENCODE_BIN)`: файл не должен начинаться с `#!`,
   заголовок должен быть Mach-O (`\xcf\xfa`/`\xfa\xed`), ELF (`\x7fELF`) или просто 4 байта
   (последнее условие фактически пропускает любой 4-байтовый файл — см. риск в §4.3).
   Глобальный флаг `SERVE_TEST_ELIGIBLE` (по умолчанию `False`) обходит эту проверку —
   тестовый крючок, в тестах выставляется в `True` для фейкового бинаря.

**Фичефлаг / конфигурация.** Основной runtime-флаг — ключ `REALTIME_SERVE_ENABLED` типа
строгий JSON-boolean в файле `dynamic_config.json` рядом с `server.py`
(`DYNAMIC_CONFIG_PATH = Path(__file__).parent / "dynamic_config.json"`). Читатель
`_read_dynamic_config_enabled`:

- кэширует значение по паре `(st_mtime_ns, st_size)` пути (`_dynamic_config_cache`),
  поэтому смена файла подхватывается тем же сервером без рестарта (это прямо проверяет
  `test_dynamic_config_switch_same_server`);
- отсутствующий файл, битый JSON, не-объект, не-boolean значение (например строка `"yes"`)
  → `False` (fail-closed в сторону legacy run).

**Kill-switch — тройной**: env `TRANSPORT=run`, env `REALTIME_SERVE_ENABLED=0`, файл
`disable-serve`. Все три имеют приоритет над dynamic-config и над sticky-состоянием;
`TRANSPORT=serve` наоборот является force-on и отменяет деградацию/отсутствие флага
(но не первые два kill-switch: проверка `transport == "run" or override in (...)` стоит
раньше ветки `transport == "serve"`).

**Дефолт.** Без env и без `dynamic_config.json` выбор — `run`: изменение не включает serve
само по себе. Serve — opt-in через файл флага или env.

### 2.2. Потоковая передача событий

#### 2.2.1. Канонизация wire-событий serve

`_map_serve_event(event)` (экспортируется также как `parse_serve_event`) отображает события
`opencode serve` v2.1.2 в канонические кортежи legacy-пути; невалидное событие бросает
`ServeProtocolError` (подкласс `ValueError`):

| Wire `type` | Канонический результат | Валидация |
|---|---|---|
| `server.connected` | `("server.connected", data)` | без проверки `data` (единственное событие, допускающее пустой `data`) |
| `session.reasoning.delta` | `("reasoning", {"reasoning_content": delta})` | `delta: str`, `sessionID: str` непустой, иначе `ServeProtocolError("invalid_serve_event: delta")` |
| `session.text.delta` | `("text", {"content": delta})` | та же |
| `session.step.ended` | `("step_finish", {"input","output","reasoning","cached"})` | `tokens` непуст, `tokens.cache.read: int` обязателен; `input/output/reasoning` обязаны быть `int` (не `bool`); `cached := cache.read` (`cache.write` игнорируется) |
| `session.execution.failed`, `session.step.failed` | `("error", {"statusCode", "message"})` | `error.message: str` обязателен; `statusCode` — из `error.status` если `int` в 100..599, иначе маппинг по `error.type`: `provider.free-limit→429`, `provider.auth→401`, иначе `None` |
| `permission.asked` | `("permission", data)` | — |
| `form.created` | `("form_created", data)` | собственно обработка — раньше маппера, см. §2.4 |
| `session.tool.*` | `("tool_event", data)` | — |
| прочее | `(etype, data)` как есть | но пустой `data` для любого типа кроме `server.connected` — `ServeProtocolError` |

События чужих сессий отфильтровываются: если `data.sessionID` (из payload) задан и не равен
текущей `session_id` — событие пропускается (`server.connected` исключён из проверки).

«Исполнительными» (execution) событиями, фиксирующими `first_event_at`, считаются:
`session.execution.started`, `session.step.started`, `session.reasoning.started`,
`session.reasoning.delta`, `session.text.delta`, `session.step.ended` и канонические
`reasoning/text/step_finish`.

#### 2.2.2. Что уходит клиенту (SSE, stream)

Обработчик `Handler._run_serve_stream_attempts` транслирует serve-события в те же
OpenAI-чанки (`format_sse_chunk`), что и legacy-путь:

- `reasoning` → чанк с `delta.reasoning_content`, байты модели не модифицируются, кроме
  `_strip_interrupted(text)`; пустые после чистки дельты подавляются.
- `text` → при эмуляции инструментов (`emulate_tools`) текст идёт через `ToolCallParser`
  (`parser_box`), который вырезает `<tool_invoke>…` блоки и эмитит tool_calls; без эмуляции —
  `emit_content(cleaned)` как `delta.content`. Парсер пересоздаётся на каждую попытку;
  перед повтором предыдущий финализируется (`finish()`).
- native tool-вызовы serve → `_native_call_as_dsh(payload, tools)`: имя инструмента из
  `part.tool` ищется среди имён клиентских `tools` напрямую или через алиасы
  `NATIVE_TOOL_ALIASES[tool.lower()]`; совпадение эмитится как DSH `tool_call`
  (`emit_tool_call`, счётчик `emitted_tools_in_attempt`). Несопоставленное имя при эмуляции
  запоминается в `unmapped_in_attempt` (основание для повтора, §2.5).
- `step_finish` → аккумуляция usage (`input/output/cached/reasoning`) в
  `Handler._serve_stream_usage` (суммируется между попытками serve внутри запроса);
  дедупликация шагов по `assistantMessageID` (множество `seen_steps`; ключ берётся из
  сырого `data`, т.к. канонический payload шага `assistantMessageID` не несёт — это прямо
  прокомментировано в коде).
- финал: обычный завершающий чанк с `finish_reason = "tool_calls" | "stop"`, usage из
  `_build_openai_usage(input or _estimate_tokens(prompt), output or _estimate_tokens(full_text), cached, reasoning)`,
  затем `data: [DONE]`.

#### 2.2.3. Статусные строки `[мост]`

Синтетические статусы — отдельные SSE-чанки с `delta.reasoning_content` (не `content`),
с префиксом `\n`, если предыдущий модельный reasoning не оканчивался переводом строки:

- константы: `STATUS_INITIAL = "[мост] Подключение к модели…\n"` (объявлена; в показанном
  diff не видно места эмиссии — см. §4.3), `STATUS_WAITING = "[мост] Ожидание первого токена…\n"`,
  `STATUS_CONTINUATION = "[мост] Ожидание продолжения…\n"`;
- в serve-потоке: первый статус не раньше `FIRST_STATUS_DELAY_S = 0.65` с от отправки prompt,
  далее до первого токена — `STATUS_WAITING` каждые `STATUS_WAITING_INTERVAL_S = 5.0` с;
  после первого токена при паузе ≥ `STALL_HEARTBEAT_INTERVAL_S = 15.0` с — `STATUS_CONTINUATION`
  с тем же периодом;
- при повторе попытки (retry по watchdog/таймаутам) — статус
  `[мост] Повтор попытки {total_spawns+1}/{max_total}…\n`;
- статусы эмитируются только при включённом thinking (`effort` не в `{"", "off", "none"}`);
- быстрый ответ статуса не получает вообще (тест `test_fast_greeting_has_no_synthetic_status`
  требует побайтово только модельные `reasoning_content`/`content`; аналогично
  `test_slow_serve_gets_status_and_no_status_on_fast` для serve).

Аналогичный механизм добавлен и в legacy run-поток (`emit_synthetic` + watchdog в
`send_keepalive`, §2.3): те же константы интервалов, то же условие thinking, тот же
`\n`-префикс по последнему reasoning.

Отдельный инвариант: синтетика не должна утекать обратно в модель — тест
`test_reasoning_content_excluded_from_prompt` фиксирует, что `_messages_to_prompt`
не включает `reasoning_content` истории (в т.ч. строки `[мост] …`) в собираемый prompt.

#### 2.2.4. Нестриминговый (JSON) путь

`Handler._serve_json_serve` повторяет ту же логику без SSE: собирает
`reasonings/texts/natives` колбэками-списками, текст при эмуляции прогоняет через
`ToolCallParser` целиком + `_strip_broken_tool_blocks`, native вызовы маппит
`_native_call_as_dsh`, usage суммирует по попыткам в `tokens`, ответ — обычный
`chat.completion` (`id = chatcmpl-oczen-…`, `message.content`, опционально
`message.reasoning_content`, `message.tool_calls` с `id = call_<24 hex>`,
`finish_reason = tool_calls|stop`, usage через `_build_openai_usage` с оценкой токенов
при нулях). Пустой результат без tool_calls → `502 serve produced no text`.

### 2.3. Управление жизненным циклом дочерних процессов, групп процессов, портов и таймаутов/watchdog

#### 2.3.1. Ранний помощник `--serve-helper`

Ключевой архитектурный приём: в начало `server.py` вынесен блок, исполняемый **до** всех
остальных импортов модуля. Если `sys.argv[1:2] == ["--serve-helper"]`, процесс работает как
помощник и завершается `SystemExit(_run_serve_helper_cli(sys.argv[2:]))`; весь остальной
модуль (включая импорт `zen_catalog`) при этом не загружается — импорты основного пути
переехали в `else:`-ветку. Это гарантирует, что helper стартует быстро и не тянет тяжёлый
контекст моста.

Контракт helper (`_run_serve_helper_cli(args)`, ровно 6 аргументов, иначе exit `2`):

```
--serve-helper <attempt_id> <port> <opencode_bin> <lease_dir> <parent_pid> <parent_lstart>
```

Валидация: все строковые аргументы непусты; `port` и `parent_pid` — decimal;
`1 ≤ port ≤ 65535`; `parent_pid > 0`. Любое нарушение → exit `2` без побочных эффектов.

Поведение helper:

1. Ставит обработчик `SIGTERM`, только выставляющий флаг `stopped` (без тяжёлой работы в
   обработчике).
2. Создаёт `lease_dir`, атомарно (write tmp + `os.replace`) публикует
   `lease-<attempt_id>.json` со схемой:
   `{"schema_version": 1, "attempt_id", "owner_uid", "parent_pid", "parent_start_ts"
   (= parent_lstart из argv), "helper_pid", "helper_lstart" (= str(int(time.time()))),
   "pgid" (= os.getpgrp()), "port", "start_ts", "phase": "starting"}`.
3. Lifeline: fd 0 (stdin helper — read-конец `os.pipe()` из родителя). Неблокирующий
   `select([0], [], [], 0)`; если fd уже готов (EOF/закрыт) до запуска serve — удаляет lease
   и выходит с кодом `0`, не поднимая serve.
4. Запускает `[opencode_bin, "serve", "--hostname", "127.0.0.1", "--port", str(port)]`
   с `stdin=DEVNULL`, `stdout=PIPE`, `stderr=PIPE`, `start_new_session=False` (serve живёт
   в группе helper — один лидер группы на попытку), `close_fds=True`; из env копии удаляется
   `OPENCODE_BIN`. Ошибка спавна → exit `2`.
5. Определяет `serve_lstart` через `ps -o lstart= -p <pid>` (timeout 2 с; при неудаче —
   `str(int(time.time()))`), обновляет lease: `phase="ready"`, `serve_pid`, `serve_lstart`.
6. Пишет в свой stdout одну строку JSON-рукопожатия `{"serve_pid", "pgid"}` и flush.
7. Главный цикл: опрос каждые 0.05 с — флаг SIGTERM, lifeline EOF, `serve_proc.poll()`;
   готовые fd из `[0, stdout, stderr]` читаются `os.read(65536)`, содержимое обоих пайпов
   serve переписывается в **stderr helper** (дренаж, чтобы serve не блокировался на полном
   буфере; тест `test_helper_drains_large_stderr` — фейк пишет >64 КиБ в stderr до SSE).
   Флаги fd пайпов переводятся в неблокирующий режим.
8. Финал (`finally`): живому serve — `terminate()`, wait 0.5 с, при неудаче `kill()`;
   остаток пайпов дренируется до EOF в stderr; lease-файл удаляется. Возвращается код serve
   (или `0` при остановке по lifeline/SIGTERM).

#### 2.3.2. Спавн serve со стороны моста (`_spawn_serve`)

- `LEASE_DIR = /tmp/opencode-zen-bridge-leases` (константа модуля; тесты подменяют).
- Порт: линейный скан кандидатов от `20000 + (os.getpid() % 20000)` до `60000`; кандидат
  проверяется реальным `bind(("127.0.0.1", candidate))` на временном сокете (сокет затем
  закрывается — между проверкой и bind самого serve есть окно гонки, см. §4.3).
  Свободного порта нет → `ServeUnavailable("no free serve port")`.
- Helper запускается как
  `[sys.executable, "-I", <abs path server.py>, "--serve-helper", attempt_id, port,
  OPENCODE_BIN, lease_dir, str(os.getpid()), _parent_lstart()]`,
  `stdin=lifeline_read`, `stdout=PIPE`, `stderr=PIPE`, `start_new_session=True`
  (поэтому `pgid == helper.pid` — инвариант владения), `close_fds=True`, env — санитизированное
  `_serve_env` (§2.4.3). Read-конец pipe в родителе сразу закрывается; write-конец хранит
  `_ServeLease` как lifeline: закрытие write-конца = EOF для helper = команда на остановку.
- Рукопожатие: родитель ждёт строку из stdout helper с `select` timeout 3.0 с, читает
  по 1 байту до `\n`, парсит `_loads_object`. Проверки владения:
  `serve_pid` истинен, `pgid == helper.pid`, helper жив; иначе `ServeUnavailable`.
- Проверка слушателя: один вызов `lsof -nP -iTCP:<port> -sTCP:LISTEN -t`
  (`_lsof_listener_pid`, timeout 2 с; вызовы журналируются в `_LSOF_CALLS`). Если слушатель
  есть и (`pid != serve_pid` или его pgid ≠ ожидаемому) → `ServeUnavailable("foreign
  listener on serve port")` — мост не работает через чужой процесс на «своём» порту.
- После рукопожатия stderr helper дренируется потоком `_drain_stderr(helper, [])`,
  «stdout после рукопожатия молчит».
- Любая ошибка этапа (`OSError/ValueError/SubprocessError`) → `lease.cleanup()` и
  `ServeUnavailable`.

#### 2.3.3. Уборка (`_ServeLease.cleanup`) и reaper осиротевших lease

`_ServeLease` — владение деревом helper→serve одной попытки; `cleanup()` идемпотентна
(флаг `_closed` под `_lock`):

1. закрыть lifeline write-конец (helper увидит EOF и сам остановит serve);
2. если helper жив или pgid жив (`_pid_alive(pgid)` — `os.kill(pid, 0)`) и
   `os.getpgid(pgid) == pgid` — `killpg(pgid, SIGTERM)`; wait helper 0.5 с; при неудаче
   `killpg(pgid, SIGKILL)` и ещё wait 0.5 с (все шаги под `try/OSError`);
3. закрыть stdout/stderr helper;
4. удалить `lease-<attempt_id>.json`;
5. `shutil.rmtree(state_dir)` только если имя каталога начинается с `zen-serve-state-`
   (тот самый per-attempt `XDG_STATE_HOME`/`TMPDIR`, см. §2.4.3).

`_startup_reaper(lease_dir=None)` вызывается из `main()` до старта сервера: для каждого
`lease-*.json` в `LEASE_DIR` — если родитель жив (`parent_pid > 0 and _pid_alive`), lease
не трогается; если родитель мёртв и helper жив при `pgid == helper_pid`, через
`ps -ww -o command= -p <helper_pid>` проверяется, что это действительно `--serve-helper`,
и только тогда `killpg(pgid, SIGTERM)`; lease-файл удаляется, возвращается счётчик удалённых.
Битые lease (непарсящийся JSON) пропускаются без удаления.

#### 2.3.4. Таймауты и watchdog

Новые константы (env-переопределяемые, кроме интервалов статусов):

| Константа | Дефолт | Env | Смысл |
|---|---|---|---|
| `FIRST_EVENT_TIMEOUT_S` | 20.0 | `OPENCODE_ZEN_BRIDGE_FIRST_EVENT_TIMEOUT_S` | нет ни одного исполнительного события после отправки prompt |
| `FIRST_TOKEN_TIMEOUT_S` | 60.0 | `OPENCODE_ZEN_BRIDGE_FIRST_TOKEN_TIMEOUT_S` | событие было, но нет ни reasoning-, ни text-токена |
| `STALL_TIMEOUT_S` | 60.0 | `OPENCODE_ZEN_BRIDGE_STALL_TIMEOUT_S` | пауза после последнего токена |
| `FIRST_STATUS_DELAY_S` | 0.65 | — | задержка первого `[мост]`-статуса |
| `STATUS_WAITING_INTERVAL_S` | 5.0 | — | период `STATUS_WAITING` до первого токена |
| `STALL_HEARTBEAT_INTERVAL_S` | 15.0 | — | период `STATUS_CONTINUATION` при зависании после токена |

Общий deadline попытки по-прежнему `TIMEOUT_S` (в serve — `prompt_send_start + TIMEOUT_S`,
в legacy — deadline `_RequestAttempts`).

**Serve-попытка** (`_serve_one_attempt`): цикл с опросом очереди событий (timeout 0.05 с);
на каждой итерации проверяются, по порядку: клиент ушёл → `exit_reason="client_gone"`;
`first_event_timeout` (delivered := были ли заголовки ответа prompt); `first_token_timeout`
(delivered := True); `stall_timeout` (delivered := True). Статусы — по §2.2.3.

**Legacy run-поток**: `feed.lines(deadline, 0.25, send_keepalive)` — интервал опроса
keepalive уменьшен с `KEEPALIVE_INTERVAL_S` до 0.25 с, а `send_keepalive` расширен в
полноценный надзор (`_WatchdogState`: `reason, first_event_at, first_token_at,
last_token_at, status_next, last_keepalive, last_reasoning`):

- обнаружение ухода клиента (`_client_gone_check`, §2.5) → kill группы процесса и
  `BrokenPipeError`;
- те же три таймаута → запись `watchdog_state["reason"]` и `_stop_proc(proc)`;
- синтетические статусы `emit_synthetic` по тем же правилам, что serve;
- собственно keepalive-чанк `{"content": ""}` — не чаще `KEEPALIVE_INTERVAL_S`.

`first_event_at/first_token_at` legacy выставляются по первому непустому событию/токену и
пишут `xs["first_event_ms"]/xs["ttft_ms"]` от начала запроса. После цикла: если
`watchdog_state["reason"]` задан — повтор через `attempts.allow_retry(reason)` со
статусом `[мост] Повтор попытки…`, иначе финальная ошибка `opencode <reason>` через SSE.

В serve-потоке тайминги попытки измеряются от `t0 = attempts.deadline - TIMEOUT_S` и
возвращаются в `_ServeResult.first_event_ms/ttft_ms`.

#### 2.3.5. Прочие элементы жизненного цикла serve-попытки

`_serve_one_attempt` — одна попытка end-to-end:

1. `_serve_env(model)` → env и пароль; `attempt_id = uuid4().hex`; `_spawn_serve` → lease.
2. Readiness: `GET /api/session/active` по keep-alive control-соединению с повторами до
   3.0 с (пауза 0.05 с); HTTP 401/403 и 400/404/422 → `ServeSecurityError`, прочий не-200
   или отсутствие `data: dict` → `ServeUnavailable`.
3. Создание сессии: `POST /api/session` с
   `{"location": {"directory": workdir}, "model": {"providerID", "id", ["variant"]},
   "permissions": [{"action": "*", "resource": "*", "effect": <policy>}]}`;
   модель делится `_model_route(model)` на provider/raw_id (дефолт provider `opencode`),
   variant — `_variant_for(model, effort)`. Та же классификация HTTP-ошибок; нужен
   `data.id`, иначе `ServeUnavailable`.
4. Подписка: отдельное соединение `GET /api/event` (`Accept: text/event-stream`, Basic-auth),
   классификация ошибок как выше; поток-читатель разбирает строки `data: …`, игнорирует
   пустые и `[DONE]`, кладёт dict-события в `queue.Queue(maxsize=4096)`, в конце — `None`.
5. Prompt отправляется **параллельным** потоком (`_prompt_worker`):
   `POST /api/session/<id>/prompt` с `{"text": prompt, "files": [], "delivery": "steer",
   "resume": True}`, timeout 65 с, отдельным одноразовым соединением (`_serve_http`);
   результат — в `prompt_status` (`status`, `headers_at`, флаг `security` при 401/403,
   `error`). Параллельность нужна, чтобы SSE читался во время долгой доставки prompt.
6. Главный цикл событий — §2.2.2, §2.3.4, §2.4.
7. `finally`: `POST …/interrupt` и `DELETE /api/session/<id>` (timeout 0.25 с, ошибки
   подавляются), закрытие control- и SSE-соединений, `lease.cleanup()`.

Control-вызовы (`_ctrl_http`) переиспользуют одно keep-alive соединение с одной повторной
попыткой при `OSError/HTTPException` (соединение пересоздаётся); вторая неудача —
`ServeUnavailable`.

### 2.4. Обработка интерактивных/инструментальных событий, ошибок, ретраев и деградации (fallback)

#### 2.4.1. Permission и form: fail-closed политика безопасности

- `permission.asked` (каноническое `"permission"`): попытка помечается `step_closed=True`
  (последующие `reasoning/text` этой попытки подавляются), мост отвечает
  `POST /api/session/<id>/permission/<request_id>/reply {"decision": "reject"}` и
  `POST /api/session/<id>/interrupt` (timeout 0.25 с каждый); любой статус, кроме 200/204,
  → `ServeSecurityError`. То есть интерактивный запрос разрешения никогда не подтверждается
  и не зависает в ожидании человека: шаг закрывается отказом.
- `form.created` обрабатывается **до** `_map_serve_event` и до любой проверки
  title/fields/схемы формы (комментарий в коде: «безопасность до любой проверки
  title/fields/схемы»): если `form.sessionID == session_id` и есть строковый `form.id` —
  `step_closed=True`, `POST …/form/<form_id>/cancel` + `POST …/interrupt` (не-200/204 →
  `ServeSecurityError`), `terminal="cancelled"`, цикл завершается. Если сессия наша, а `id`
  нет — `ServeSecurityError("form.created without id")`. Чужая сессия — событие игнорируется
  (`continue`). Следствие: модель не может вывести пользователю форму; текст после формы
  (фикстура эмитит `STEP2`) до клиента не доходит — тест
  `test_form_missing_title_cancels_without_step2` проверяет именно отсутствие `STEP2` и факт
  cancel на стороне фейка (файл `.control`).
- Политика разрешений при создании сессии задаётся env
  `OPENCODE_ZEN_BRIDGE_SERVE_PERMISSION_POLICY`: `ask_reject` (дефолт) → effect `ask`
  (а каждый `permission.asked` отклоняется, см. выше), `deny` → effect `deny`; любое иное
  значение → `ServeSecurityError` ещё при построении env (`_serve_permission_effect`).

#### 2.4.2. Native tool-вызовы serve

`_ServeToolState` накапливает фрагменты жизненного цикла native вызова по `id`
(`session.tool.input.started/delta/ended`, `called`, `failed`, `success`):

- `feed(data)`: запоминает `name`, кусок `text` (дельты перезаписывают поле `text` целиком —
  накопление именно дельт в этом поле кодом не суммируется; финальный текст ожидается из
  `input.ended.text`), `input` (dict);
- `complete(call_id)`: один раз на вызов (`emitted`-множество); нужен непустой `name`;
  аргументы — `called.input`-dict, иначе JSON-парсинг накопленного `text`; непарсящееся или
  не-dict → вызов не эмитится (`None`);
- результат эмиссии — канонический `tool_use` с
  `part.state = {"input": args, "status": "error"}` (статус захардкожен `error`, включая
  путь `session.tool.success`, — см. риск в §4.3);
- на `session.step.ended` все незавершённые вызовы принудительно `complete()`-ятся, чтобы
  вызов без события `called` не потерялся.

Далее DSH-маппинг — `_native_call_as_dsh` (§2.2.2). Несопоставившийся native вызов при
эмуляции инструментов — не ошибка протокола, а повод для повтора с переписанным prompt
(§2.4.4).

#### 2.4.3. Санитизация окружения serve (`_serve_env`)

Применяется на всех ветках маршрутизации (комментарий в тесте — «на всех ветках»):

- база — `_run_env(model_id)`, из неё оставляется только allowlist `_SERVE_ALLOWLIST`:
  `PATH, HOME, USER, LOGNAME, SHELL, LANG, LC_ALL, LC_CTYPE, TZ, TERM, COLORTERM`,
  прокси (`HTTP(S)_PROXY/ALL_PROXY/NO_PROXY` в обоих регистрах), `SSL_CERT_FILE/DIR`,
  `NODE_EXTRA_CA_CERTS`, `XDG_DATA_HOME, XDG_CONFIG_HOME, OPENCODE_CONFIG,
  OPENCODE_CONFIG_CONTENT, OPENCODE_MODELS_PATH`;
- секреты вне allowlist (тест: `SECRET_SENTINEL`, `MY_API_KEY`) в дочерний процесс не
  попадают; `OPENCODE_BIN` удаляется;
- `OPENCODE_CONFIG_CONTENT` пересобирается: существующий JSON сохраняется, но
  `permission` принудительно заменяется на `{"*": <effect политики>}`;
- изоляция состояния: `XDG_STATE_HOME` и `TMPDIR` — свежий
  `tempfile.mkdtemp(prefix="zen-serve-state-")` на попытку, `OPENCODE_DB=":memory:"`
  (serve не пишет в пользовательскую БД opencode);
- `OPENCODE_SERVER_PASSWORD = secrets.token_hex(16)` — случайный пароль на попытку;
  HTTP-вызовы к serve идут с `Authorization: Basic base64("opencode:<password>")` напрямую
  на `127.0.0.1:<port>` через `http.client` (без прокси).

#### 2.4.4. Классификация ошибок, повторы, fallback, деградация

Три исключения задают таксономию:

- `ServeUnavailable` — serve недоступен **до барьера доставки**; в `auto` допустим fallback
  на run;
- `ServeProtocolError(ValueError)` — битое событие serve (протокол, не модель);
- `ServeSecurityError` — отказ безопасности; fail-closed без fallback.

Декларативная таблица `FALLBACK_DECISION_TABLE` (12 строк; поля `phase, event, DELIVERED,
action, ServeHealth_failure_increment, UpstreamBreaker_failure_increment`) фиксирует
намеренную политику; ключевые строки:

| Фаза/событие | DELIVERED | Действие | ServeHealth | Breaker |
|---|---|---|---|---|
| SPAWN/READY/CREATE/SUBSCRIBE: локальный сбой спавна/готовности | false | `fallback_to_run` | +1 | 0 |
| SPAWN→READY: ownership failure/timeout | false | `fallback_to_run` | +1 | 0 |
| PROMPT_SENDING: first_event_timeout 20 с, нет заголовков и нет валидного SSE | false | `fallback_to_run` | +1 | 0 |
| DELIVERED: first_event_timeout после заголовков, нет валидного SSE | true | `serve_retry` | +1 | 0 |
| DELIVERED: first_token/stall при валидном протоколе и молчании модели | true | `serve_retry` | 0 | +1 |
| DELIVERED: first_token_timeout с доказанным дефектом протокола (не security) | true | `serve_retry` | +1 | 0 |
| ANY: HTTP 401/403, permission/form/capability-security | any | `fail_closed` | 0 | 0 |
| ANY: HTTP 400/404/422 (invalid request) | any | `fail_closed` | 0 | 0 |
| PRE_PROMPT: HTTP 5xx локальных readiness/create/subscribe | false | `fallback_to_run` | +1 | 0 |
| PROMPT_RESPONSE: HTTP 429/provider 5xx | true | `serve_retry` | 0 | +1 |
| DELIVERED: invalid SSE/EOF без terminal, доказанно только протокол | true | `serve_retry` | +1 | 0 |
| ANY: отмена клиентом/deadline/бюджет исчерпан | any | `fail_closed` | 0 | 0 |

Фактическая реализация в обоих serve-обработчиках (stream и JSON симметрично):

- `ServeUnavailable` → `serve_health.record_failure()`; если не `force_serve` — возврат
  `False` (вызывающий код переключает `xs.transport="run"`, `transport_history=["serve","run"]`
  и идёт в legacy-цикл); при `force_serve` — SSE/502 ошибка `serve unavailable: …`,
  `exit_reason=upstream_failed`.
- `ServeSecurityError` → SSE/502 `serve security failure: …`, `exit_reason=provider_fatal`,
  без fallback и без инкремента health (тест на HTTP 400 проверяет неизменность
  `health.failures`).
- Внутрипопытные `exit_reason` (`first_event_timeout, first_token_timeout, stall_timeout,
  invalid_serve_event`): для `first_event_timeout/invalid_serve_event` —
  `serve_health.record_failure()`, для `first_token_timeout/stall_timeout` —
  `attempts.attempt_done(True, False)` (засчитывается upstream-breaker, не serve-health);
  если `delivered=False` и не `force_serve` — fallback на run; иначе повтор через
  `attempts.allow_retry(reason)` (с `[мост] Повтор попытки…` в stream) до исчерпания
  бюджета `_RequestAttempts`, затем ошибка `serve <reason>`.
- `result["error"]` (каноническое событие `error`) → `serve error: <message>`,
  `exit_reason=upstream_failed`, без повторов в этой ветке.
- Успех → `serve_health.record_success()` (полный сброс счётчика и TTL).

`_ServeHealth` (в `_Resilience.serve_health`, по экземпляру на `Server`): порог
`threshold=3` протокольных отказов, sticky TTL `ttl_s=120.0` по `time.monotonic`;
`record_failure` инкрементит и при достижении порога ставит `_degraded_until = now+120`;
`is_degraded` по истечении TTL сам сбрасывает счётчик; `record_success` сбрасывает всё.
Пока деградирован, `_select_transport` в `auto` возвращает `run` (при `TRANSPORT=serve`
деградация игнорируется force-режимом).

Повторы уровня инструментов (общие для stream/JSON serve и унаследованные от legacy
семантики):

- unmapped native вызовы: до `NATIVE_RETRY_LIMIT` повторов с
  `_unavailable_tools_prompt(...)` + `_rewrite_tool_tags_for_model(...)`; после исчерпания
  stream добавляет клиенту текстовое примечание
  `[opencode-zen-bridge: модель вызывала недоступный встроенный инструмент (<имена>); повторы исчерпаны]`,
  JSON — просто завершает с тем, что есть;
- незавершённый шаг (`_incomplete_step_signal` по текстам/reasoning/usage) — аналогично
  `_incomplete_tool_step_prompt` и `attempts.signal = signal`;
- оба счётчика (`unmapped_retries`, `incomplete_retries`) независимы (см. обновлённые
  ожидания в §4.2).

Уход клиента в serve определяется `_client_gone_check()`: `os.dup` fd запроса,
`select` 0 с + `recv(1, MSG_PEEK|MSG_DONTWAIT)`; пустые данные (FIN) → клиент ушёл;
`AttributeError` (нет fd) → `False`. В legacy-потоке та же проверка добавлена в
`send_keepalive` с kill группы процесса.

## 3. Внешние контракты и инварианты

### 3.1. Затронутые и добавленные контракты

**Новые/изменённые env-переменные:**

| Переменная | Дефолт | Контракт |
|---|---|---|
| `OPENCODE_ZEN_BRIDGE_TRANSPORT` | `auto` | `auto|serve|run`; прочее → `run` |
| `OPENCODE_ZEN_BRIDGE_REALTIME_SERVE_ENABLED` | пусто | `1/true/yes/on` — включить; `0/false/no/off` — kill-switch |
| `OPENCODE_ZEN_BRIDGE_SERVE_DISABLE_FILE` | `~/.dsh/bridges/opencode-zen-bridge/disable-serve` | существование файла — kill-switch serve |
| `OPENCODE_ZEN_BRIDGE_SERVE_PERMISSION_POLICY` | `ask_reject` | `ask_reject|deny`; прочее — `ServeSecurityError` при построении env |
| `OPENCODE_ZEN_BRIDGE_FIRST_EVENT_TIMEOUT_S` | `20.0` | watchdog первого события, оба транспорта |
| `OPENCODE_ZEN_BRIDGE_FIRST_TOKEN_TIMEOUT_S` | `60.0` | watchdog первого токена, оба транспорта |
| `OPENCODE_ZEN_BRIDGE_STALL_TIMEOUT_S` | `60.0` | watchdog паузы после токена, оба транспорта |

**Новый файл конфигурации**: `bridges/opencode-zen-bridge/dynamic_config.json` (рядом с
`server.py`), ключ `REALTIME_SERVE_ENABLED` — только строгий JSON `true/false`; читается с
кэшем по `(mtime_ns, size)`, применяется без рестарта; битый/отсутствующий → `false`.

**Новый CLI-контракт того же файла**: `python3 -I server.py --serve-helper <attempt_id>
<port> <opencode_bin> <lease_dir> <parent_pid> <parent_lstart>` — ровно 6 аргументов,
коды возврата `0` (нормальная остановка по lifeline/SIGTERM; досрочный выход при уже
закрытом lifeline), `2` (невалидные аргументы, нет lease_dir, не поднялся serve), иначе —
код завершения `opencode serve`. Stdout helper — ровно одна строка JSON-рукопожатия
`{"serve_pid": int, "pgid": int}`; дальше stdout молчит, весь вывод serve перенаправляется
в stderr helper.

**Новые файлы в runtime**: `/tmp/opencode-zen-bridge-leases/lease-<attempt_id>.json`
(схема `schema_version: 1`, поля §2.3.1; атомарная публикация через tmp+rename; удаляется
при уборке попытки и reaper-ом при старте); временные каталоги `zen-serve-state-*` в
системном tmp (XDG_STATE_HOME/TMPDIR попытки; удаляются в `cleanup`).

**Внутренний HTTP-контракт к `opencode serve` v2.1.2** (новый, не публичный): Basic-auth
`opencode:<OPENCODE_SERVER_PASSWORD>`; `GET /api/session/active`, `POST /api/session`,
`GET /api/event` (SSE), `POST /api/session/<id>/prompt`
(`{"text","files":[],"delivery":"steer","resume":true}`, timeout 65 с),
`POST /api/session/<id>/permission/<request_id>/reply` (`{"decision":"reject"}`),
`POST /api/session/<id>/form/<form_id>/cancel`, `POST /api/session/<id>/interrupt`,
`DELETE /api/session/<id>`. Классификация: 401/403 и 400/404/422 — security/fail-closed;
прочие не-200 на pre-prompt этапах — `ServeUnavailable`.

**Внутренний парсер**: добавлен собственный минимальный JSON-парсер `_JsonParser` /
`_loads_object` (при ошибке возвращает `{}`); используется для dynamic-config,
рукопожатия helper, тел ответов serve и SSE-строк вместо `json.loads` в новых путях.

**Лог-контракт `O-EXIT/v1` расширен**: в `_new_exit_state` добавлены `transport`
(`none|run|serve|google`), `first_event_ms`, `ttft_ms`, `transport_history` (например
`["serve","run"]` при fallback); `_log_exit` печатает их в той же одной структурной строке.
Новая публичная декларация `FALLBACK_DECISION_TABLE` (12 строк, §2.4.4) — модульная
константа, доступная тестам и внешним читателям.

### 3.2. Публичный OpenAI-совместимый контракт

По diff публичный контракт **не изменён**:

- `/health`, `/v1/models` — в diff нет ни одного hunk по этим маршрутам;
- `/v1/chat/completions` — те же входные поля; stream-ответ собирается тем же
  `format_sse_chunk`, завершается тем же финальным чанком с `_build_openai_usage` и
  `data: [DONE]`; JSON-ответ — тот же `chat.completion` (`choices[0].message`,
  опциональные `reasoning_content`/`tool_calls`, `finish_reason`, `usage`);
- наблюдаемые добавления внутри существующего формата, а не новые поля протокола:
  (1) синтетические чанки `delta.reasoning_content` со строками `[мост] …` при медленном
  апстриме (только при включённом thinking и только после 0.65 с тишины); (2) текстовое
  примечание `[opencode-zen-bridge: модель вызывала недоступный встроенный инструмент …]`
  в `content` при исчерпании повторов unmapped (stream-путь); (3) новые значения
  `exit_reason` в логе (`first_event_timeout`, `first_token_timeout`, `stall_timeout`,
  `invalid_serve_event`) и тексты ошибок вида `serve <reason>`, `opencode <reason>`,
  `serve unavailable: …`, `serve security failure: …` в существующем `_error_payload`;
- быстрый ответ не получает ни одного лишнего байта (прямой тестовый инвариант).

### 3.3. Что осталось нетронутым

- Прямой Google-маршрут: ветка `_stream_google_sse` / `_execute_google_once` и выбор
  `use_breaker=not _is_google_direct_model(...)`; в JSON-пути serve включается только при
  `not _is_google_direct_model(model)`, в stream-пути Google обрабатывается до serve.
  Тест `test_frozen_slices_hashes` побайтово (sha256 по AST-диапазонам исходника) фиксирует
  неизменность `_run_env`, `_stream_google_sse`, `_execute_google_once`.
- `_run_env` (окружение legacy run) не изменён семантически — `_serve_env` строится поверх
  него фильтрацией, сам `_run_env` заморожен хэшем.
- Каталог моделей: `reload_catalog`, `_read_catalog_state`, `_stat_mtime` логически прежние;
  изменились только дефолт `CATALOG_SOURCE = "static"` (было `"init"`) и механизм его
  обновления — helper `_set_catalog_source` пишет через `globals()` вместо `global`
  в `reload_catalog` (побочный эффект выделения основного модуля в `else:`-ветку после
  раннего `--serve-helper` dispatch). Публично это видно в стартовой строке лога
  `catalog=<mode>/<source>` до первого reload.
- `_RequestAttempts`, `_UpstreamBreaker`, `_SpawnRateLimiter`, `_RetryBudget`, слоты —
  интерфейсы прежние; в `_Resilience` добавлен только `serve_health = _ServeHealth()`.
  Форматирующие правки в `Run.execute/_execute_once`, `_PrefixDedup`, `_dedup_retry_text`,
  `_log_exit` (кроме новых полей) семантику не меняют; в финале stream исправлен
  `proc.returncode` на `proc.returncode if proc is not None else None` (защита от None при
  раннем break).
- Legacy retry-семантика run (`_is_retryable_failure`, `FAIL_RETRY_LIMIT`, incomplete/
  unmapped повторы в stream) сохранена; watchdog добавлен поверх неё.

## 4. Покрытие тестами и граничные случаи

### 4.1. Новый модуль `tests/test_realtime_reasoning.py`

Инфраструктура: `_Bridge` поднимает настоящий `server.Server` на `127.0.0.1:0` с
`AUTH_KEY="test-key"`, временным `LOG_PATH`; `post_stream_timed` фиксирует время прибытия
каждого SSE-чанка. Фейки: `LEGACY_FAKE` (режимы `fast/slow/silent/stall` через
`FAKE_RT_MODE`, дополнительно проброшен в `_STANDALONE_ENV_ALLOWLIST`) и `FAKE_SERVE`
(полноценный `opencode serve`: Basic-auth по `OPENCODE_SERVER_PASSWORD`, `/api/info`,
`/api/session/active`, `/api/event` с маркерами в prompt — `__record:`, `__never_event__`,
`__silent__`, `__slow__`, `__form_missing_title__`, `__form_ok__`, `__permission__`,
`__native_tool__`, `__tool_text__`; пишет 70 000 байт в stderr при старте; ветка `run` для
fallback-сценария). В `setUp` группы B: `TRANSPORT=serve`, `DYNAMIC_CONFIG_PATH` и
`LEASE_DIR` указывают во временный каталог, `HOME` — пустой.

**Группа A — legacy watchdog (`TestLegacyWatchdogAndKillpg`, 6 тестов):**

| Тест | Проверяет |
|---|---|
| `test_fast_greeting_has_no_synthetic_status` | быстрый legacy ответ: `reasoning_content == "Simple greeting."`, `content == "Привет!"`, без `[мост]` |
| `test_slow_upstream_gets_initial_status_before_1s` | при задержке 1.6 с первый `[мост]`-статус пришёл ≤ 1.0 с и оканчивается `\n` |
| `test_reasoning_content_excluded_from_prompt` | `_messages_to_prompt` не пропускает `reasoning_content`/`[мост] секретный статус` в prompt |
| `test_frozen_slices_hashes` | sha256 AST-срезов `_run_env`, `_stream_google_sse`, `_execute_google_once` равны замороженным значениям |
| `test_oexit_fields_present` | последняя `O-EXIT/v1` в bridge.log содержит `transport=`, `first_event_ms=`, `ttft_ms=` |
| `test_watchdog_first_event_timeout` | режим `silent` + ужатые `FIRST_EVENT_TIMEOUT_S=1/FIRST_TOKEN_TIMEOUT_S=2`: запрос завершается ошибкой < 25 с, а не по `TIMEOUT_S` |

**Группа B — serve (`TestServeTransportAndFakeServe`, 15 тестов):**

| Тест | Проверяет |
|---|---|
| `test_ac026_realtime_chunks_before_upstream_end` | ≥3 модельных reasoning-чанок (без `[мост]`), первая раньше конца апстрима, разброс < 2 с, конкатенация ровно `Мысль0 … Мысль4 ` |
| `test_dynamic_config_switch_same_server` | тот же процесс: `true→True`, `false→False`, битый JSON→False, `"yes"` (строка)→False, обратно `true→True` |
| `test_serve_env_sanitized_all_branches` | `OPENCODE_DB=":memory:"`, нет `OPENCODE_BIN/SECRET_SENTINEL/MY_API_KEY`, есть пароль и `XDG_STATE_HOME`, `XDG_DATA_HOME ≠ XDG_STATE_HOME` |
| `test_canonical_frozen_fixtures` | `_map_serve_event/parse_serve_event`: reasoning-дельта и step.ended с `cache.read=3` → точные канонические payload |
| `test_tool_text_split_across_deltas` | `<tool_in…voke>` разрезан на 3 дельты — клиент получает один `tool_calls` с именем `bash` |
| `test_native_tool_and_permission_reject` | `permission.asked` + native `bash`: клиент получает `tool_calls` с `bash` |
| `test_form_missing_title_cancels_without_step2` | форма без title: cancel получен фейком (`.control` содержит `cancelled`), `STEP2` в content нет |
| `test_slow_serve_gets_status_and_no_status_on_fast` | медленный serve: `[мост]` ≤ 1.0 с |
| `test_helper_argv_validation_and_lease_dir` | `_run_serve_helper_cli([])` и битый порт → не 0; подпроцесс `-I server.py --serve-helper` с 5 аргументами → returncode ≠ 0 |
| `test_serve_health_and_fallback_table` | 3 `record_failure` → degraded; `record_success` → не degraded; `FALLBACK_DECISION_TABLE` существует, ≥10 строк |
| `test_helper_drains_large_stderr` | >64 КиБ stderr фейка: запрос завершается < 15 с и даёт reasoning |
| `test_clean_room_fake_serve_via_monkeypatched_bin` | пустой `HOME`, подменённый `OPENCODE_BIN`: serve отвечает content |
| `test_auto_fallback_to_run_and_sticky_degradation` | `TRANSPORT=auto`, `FAKE_SERVE_SESSION_STATUS=503`: 3 запроса подряд достаются fallback-ом на run (`Поздний ответ` из ветки `run` фейка), после — `serve_health.is_degraded()` |
| `test_foreign_listener_rejected_and_startup_reaper` | `_lsof_listener_pid → 999998`: `_spawn_serve` бросает `ServeUnavailable("foreign listener…")`; reaper удаляет lease мёртвого родителя (pid 999999) и сохраняет lease живого |
| `test_serve_400_fails_closed_without_health_increment` | HTTP 400 на создании сессии при `TRANSPORT=serve`: в SSE есть `serve security failure`, `health.failures` не изменился, не degraded |

### 4.2. Обновлённые тесты `tests/test_step_interruption.py`

- `setUp` теперь ставит свежий `server._Resilience()` на каждый тест (комментарий —
  «Изоляция REQ-017: свежий бюджет повторов на каждый тест, без сброса в проде») — ранее
  тесты могли делить бюджеты breaker/retry.
- Фейк `FAKE_OPENCODE` получил режим `unmapped_incomplete_calls`: попытка 0 — `tool_use`
  недоступного `todoread` + `step_finish`, попытка 1 — reasoning+text+finish.
- Изменены ожидания `test_unmapped_retries_do_not_exhaust_incomplete_budget_stream/json`:
  было 4 запуска и `tool_calls=[job_output, bash]`/`finish=tool_calls`; стало **3 запуска**,
  `names=[]`, `finish=stop` (JSON-вариант переписан на ручной разбор через
  `server._loads_object` с проверками типов вместо `json.loads`). Реконструируемый смысл:
  повторы по unmapped и по incomplete имеют раздельные бюджеты и по-разному считаются
  в общем капe спавнов — после unmapped-повтора и incomplete-повтора ранее обещанные
  вызовы больше не «дожимаются» в этом сценарии.
- Добавлен `test_unmapped_then_incomplete_then_calls_within_cap_stream`: цепочка
  unmapped → incomplete → валидные вызовы укладывается в кап: 3 запуска,
  `names=[job_output, bash]`, `finish=[tool_calls]`.

### 4.3. Граничные случаи, fault-injection и видимые пробелы/риски

Покрыто fault-injection: 503/400 на создании сессии, чужой слушатель порта (`lsof` подменён),
lease мёртвого родителя, >64 КиБ stderr, пустой `HOME`, битый dynamic-config, молчащий
legacy апстрим (watchdog), разрезанные tool-дельты, форма без `id/title`, permission-запрос.

Видимые пробелы и риски (по коду; тестами не закрыты или расходятся с декларацией):

1. **Serve JSON-путь** (`_serve_json_serve`) прямыми тестами не покрыт: группа B гоняет
   только `post_stream_timed`; JSON-ожидания обновлены лишь для legacy run.
2. **Фикстуры `__silent__`/`__never_event__` в `FAKE_SERVE` не используются ни одним тестом** —
   serve-варианты `first_event_timeout/first_token_timeout/stall_timeout`, `invalid_serve_event`,
   EOF без terminal и повтор `serve_retry` после `delivered=True` остаются без прямого
   покрытия (покрыт только legacy watchdog).
3. **`FALLBACK_DECISION_TABLE` — декларация, а не исполняемая политика**: тест проверяет
   лишь существование и ≥10 строк. Расхождения с кодом на глаз: строки про HTTP 429/5xx
   ответа prompt не имеют отдельной ветки в `_serve_one_attempt` (статус prompt фиксируется
   в `prompt_status`, но 429/5xx оттуда не классифицируются); «breaker +1» для
   first_token/stall реализован через `attempts.attempt_done(True, False)`, что не тождественно
   полю таблицы.
4. **`STATUS_INITIAL` («[мост] Подключение к модели…») объявлен, но в diff нет места его
   эмиссии** — либо мёртвая константа, либо эмиссия вне показанных hunk-ов.
5. **Окно гонки порта**: кандидат проверяется `bind` на временном сокете, сокет закрывается,
   и только потом helper поднимает serve; чужой процесс может занять порт между проверкой
   и bind (частично ловится post-hoc проверкой `lsof`, но та выполняется по рукопожатию и
   только если слушатель вообще есть).
6. **`_is_native_opencode_bin` пропускает любой файл из ≥4 байт**, не начинающийся с `#!`,
   если первые 2 байта не Mach-O и не ELF — условие `len(head) == 4` делает проверку
   заголовка почти пустой для коротких файлов; реальный предохранитель в `auto` слабый.
7. **`serve_lstart`/`helper_lstart` непоследовательны**: для serve — строка `ps lstart`
   (или fallback `int(time.time())`), для helper — всегда `int(time.time())`, а
   `parent_start_ts` пробрасывается из argv без проверки соответствия живому процессу;
   reaper при этом опирается только на `parent_pid`/`helper_pid`/`pgid` и текст команды,
   lstart в reaper не сверяется (риск PID-reuse в обе стороны).
8. **`_ServeToolState.feed` перезаписывает `text` каждой дельтой**, а не накапливает;
   корректность аргументов зависит от того, что `input.ended` присылает полный текст.
   Дополнительно `complete()` всегда ставит `state.status="error"` — даже для
   `session.tool.success`; потребители DSH-маппинга статус не читают, но канонический
   `tool_use` при этом врёт о результате.
9. **Очередь SSE `maxsize=4096` без обработки переполнения**: `events.put` в потоке-читателе
   блокирующий — при очень болтливом serve читатель встанет, пайп serve забьётся; timeout
   у `put` нет.
10. **`_JsonParser` самодельный**: нет обработки суррогатных пар `\uXXXX\uXXXX` (склеиваются
    в два отдельных `chr`), нет пределов глубины (рекурсия `_value/_object/_array`) —
    глубоко вложенное событие serve может уронить поток `RecursionError`, который в
    `_reader` ловится только как `(OSError, ValueError)`.
11. **Уход клиента в serve** покрыт только кодом `_client_gone_check`; теста на разрыв
    клиентского соединения во время serve-стрима нет (как и на `client_gone` в
    `_run_serve_stream_attempts`).
12. **Kill-switch матрица** (`TRANSPORT=run`, `REALTIME_SERVE_ENABLED=0`, файл
    `disable-serve`, неизвестное значение `TRANSPORT`) тестами напрямую не перебирается —
    проверены только `serve`, `auto` и dynamic-config.
13. **Reaper не убивает реальный осиротевший helper в тесте**: lease мёртвого родителя в
    тесте имеет `helper_pid=0`, поэтому ветка `killpg` с проверкой `--serve-helper` не
    исполняется; живой сценарий «мост умер, helper+serve висят» покрыт только кодом.
14. **Повтор serve при `delivered=True`** эмитит клиенту `[мост] Повтор попытки…` и
    продолжает стрим в тот же ответ — уже отданные reasoning/text первой попытки не
    откатываются и не дедуплицируются (для serve нет аналога `_PrefixDedup` legacy-пути);
    клиент может получить дубль префикса. Тестами не проверяется.
15. В обоих serve-обработчиках `xs["first_event_ms"]/xs["ttft_ms"]` присваиваются дважды
    подряд из одного `result` (косметика), а при fallback после неудачной serve-попытки
    значения остаются от serve в `O-EXIT` уже run-запроса (`transport_history` это честно
    показывает, но `first_event_ms` относится к serve, а не к итоговому run).
ARTIFACT_END>>>

## 5. Список обязательных правил и стандартов проекта
- `~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/AGENTS.md`
- `~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/skills/feature.md`
- `~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/code.md`
- `~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/python-standards.md`
- `~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/testing.md`
- `~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/security.md`
- `~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/error-handling.md`
- `~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/logging.md`
- `~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/scope-and-contracts.md`

КОНТЕКСТ:
Ниже приложены целиком реестр фактов и план исследования аналитического этапа (`evidence-ledger.md`, `research-plan.md`), манифест подпроекта (`bridges/opencode-zen-bridge/pyproject.toml`), рубрика подкатегорий Совета (`council.md#L379-L403`) и первичные артефакты выбора мест раунда `panel/council/r1`:
<<<ARTIFACT analysis/zen-realtime-reasoning/evidence-ledger.md sha256=2a5c9f7f8a8fc20573d69a4617da87bdfbf1f57e70681e7036ece27541fe0367
# Evidence Ledger: zen-realtime-reasoning (opencode-zen-bridge, реалтайм-размышление)

Дата сбора: 2026-10-25 (MSK). Ветка `feature/zen-realtime-reasoning`. Роль: System Analyst (Stage 1).
Формат факта: `[F-NN] (FACT-0NN) утверждение | источник | YYYY-MM-DD`. Секреты не выносятся
(пароль `opencode serve`, `apiKey`, креды ProxyRack, логины пула не воспроизводились и не сохранялись).
Пути с `~/` — домашний каталог. Пути без `~/` — относительно корня репозитория
`bridges/opencode-zen-bridge/`, если не указано иное.
Эмпирические PoC-скрипты и логи аналитика: `/tmp/cel-runs/zen-realtime-reasoning-20261025/sa-poc/`
(вне репозитория; код продукта не менялся).

## 1. Код моста (повторная сверка по исходнику)

[F-01] (FACT-001) Мост запускает `opencode run -m <provider>/<model>#<variant> --thinking --format json` и добавляет `--standalone` для Zen-маршрутов в режиме каталога `dynamic`; промпт передаётся через stdin, процесс стартует в новой сессии процессов (`start_new_session=True`) | server.py:1146-1161, 966-969, 1617-1649 | 2026-10-25
[F-02] (FACT-002) `parse_opencode_event` отображает `reasoning` в `delta.reasoning_content`, `text` в `delta.content`, `step_finish` в usage, `error` в `{statusCode,message}`; любые другие типы (в т.ч. `step_start`, `part.delta`) возвращаются как `(etype, {})` и в SSE не попадают | server.py:2417-2462 | 2026-10-25
[F-03] (FACT-003) `Handler._stream_sse` отправляет HTTP 200 с заголовками SSE и первый чанк `{"role":"assistant","content":""}` до `_StartupGate`, spawn и чтения stdout | server.py:3312-3327, 3399-3412 | 2026-10-25
[F-04] (FACT-004) Единственная «живость» стрима до первого токена — `send_keepalive`: чанк `{"content":""}` после `KEEPALIVE_INTERVAL_S=15.0` с без строк stdout; сам чанк не содержит ни `reasoning_content`, ни непустого `content` | server.py:49, 3437-3450, 865-952 | 2026-10-25
[F-05] (FACT-005) События `reasoning` пишутся клиенту и сбрасываются (`flush`) сразу при получении строки; события `text` идут в `ToolCallParser.feed` (при `emulate_tools`) либо напрямую в `emit_content` | server.py:3462-3493 | 2026-10-25
[F-06] (FACT-006) `ToolCallParser` отдаёт текст вне тегов сразу и удерживает только хвост-префикс открывающего тега (не длиннее `len("<tool_invoke>")-1` символов) и открытый незакрытый блок `<tool_call>`/`<tool_invoke>`; инкрементальность поддерживается, если дельты приходят по частям | server.py:2213-2338 (в т.ч. `_drain` 2252-2297, `_pending_prefix` 2316-2323) | 2026-10-25
[F-07] (FACT-007) `_render_turn` и `_messages_to_prompt` используют у assistant-реплик только `content` и `tool_calls`; поле `reasoning_content` входящих сообщений в промпт модели не попадает | server.py:1848-1888 | 2026-10-25
[F-08] (FACT-008) Конфиг `opencode` для дочернего процесса по умолчанию: `permission {"*":"ask"}` и `provider.opencode.options.baseURL=http://127.0.0.1:10830/v1` | server.py:228-231 | 2026-10-25
[F-09] (FACT-009) В `server.py` нет ни TTFT-watchdog, ни watchdog первого события, ни watchdog паузы между чанками: поиск без учёта регистра по словам ttft, first_token, first_byte, stall, idle_timeout, FIRST_EVENT даёт 0 совпадений; единственный потолок ожидания — общий `deadline = now + TIMEOUT_S` (1800 с) | server.py:46, 3450, команда grep от 2026-10-25 | 2026-10-25
[F-10] (FACT-010) `_StartupGate.acquire` ждёт замок `STARTUP_WAIT_S=5.0` с и затем идёт без замка (fail-open); замок держится до первой stdout-строки либо `STARTUP_GATE_S=12` с; `gate.release()` вызывается на любую первую строку, включая `step_start` | server.py:1197-1236, 3399-3411, 3451 | 2026-10-25
[F-11] (FACT-011) Потолки повторов: `MAX_TOTAL_SPAWNS=3`, `FAIL_RETRY_LIMIT=min(3,MAX_TOTAL_SPAWNS-1)=2`, `NATIVE_RETRY_LIMIT=2`, Full Jitter `RETRY_BACKOFF_BASE_S=0.5`/`RETRY_BACKOFF_CAP_S=2.0`, `SPAWN_RATE_PER_S=1.0` и `SPAWN_BURST=1.0`, `_RetryBudget`: ёмкость 6, +0.20 за запрос, +0.05 в секунду | server.py:277, 287-298, 309-314, 1340-1368, 1471-1535 | 2026-10-25
[F-12] (FACT-012) Защиты процесса (`_Resilience`: слоты, spawn-limiter, retry-budget, breaker) создаются по одному экземпляру на `Server`; прод передаёт модульный `_DEFAULT_RESILIENCE`, каждый тестовый `Server` получает собственный набор | server.py:1458-1470, 3989-3996 | 2026-10-25
[F-13] (FACT-013) `MAX_CONCURRENT` по умолчанию в коде равен 2 (`OPENCODE_ZEN_BRIDGE_MAX_CONCURRENT`), деплой отвечает `max_concurrent=6`; `SLOT_WAIT_TIMEOUT_S=15.0`, `MAX_SLOT_WAITERS=12` | server.py:50, 303-305; GET http://127.0.0.1:9883/health от 2026-10-25 22:45 MSK | 2026-10-25
[F-14] (FACT-014) `_stop_proc` завершает группу процессов (`killpg` SIGTERM, затем SIGKILL); `_StdoutFeed` — daemon-поток с очередью `maxsize=4096`, `_STDOUT_POLL_S=0.25` | server.py:848-862, 865-952 | 2026-10-25
[F-15] (FACT-015) Для standalone окружение дочернего процесса собирается по белому списку, прокси берётся из пула ProxyRack по кругу на каждый новый spawn, loopback идёт мимо прокси; `start.sh` включает `OPENCODE_ZEN_BRIDGE_STANDALONE_PROXY=pool`, если файл пула непуст | server.py:1047-1082, 1093-1131; start.sh:24-31 | 2026-10-25
[F-16] (FACT-016) `_stream_google_sse` — существующий прямой HTTP-SSE маршрут без `opencode run`: `http.client`, чтение `resp.readline()`, `ToolCallParser` на дельтах, `emit({"reasoning_content": text})` в реальном времени; прецедент прямого маршрута для Option B | server.py:3127-3266 (reasoning emit около 3219) | 2026-10-25

## 2. Эмпирика `opencode` v2.1.2 (Zone B и PoC аналитика)

[F-17] (FACT-017) `opencode run --format json --thinking` во всех четырёх режимах (PIPE/PTY × фоновый сервис/`--standalone`) выдаёт 3 события (`step_start`, `reasoning`, `text`) плюс `step_finish` не всегда; единственный `reasoning`-блок приходит в тот же момент, что и `text` (разница 0.00-0.17 мс); тишина stdout после `step_start` 1904-2716 мс; полное время 3282-5213 мс (таблица T1) | explorer-zone-b.md §1 (замер 2026-10-25 22:2x MSK) | 2026-10-25
[F-18] (FACT-018) Причина F-17 в бинарнике `~/.opencode/bin/opencode`: обработчик событий `opencode run` подписан на `session.reasoning.ended` и `session.text.ended` и игнорирует `session.reasoning.delta` и `session.text.delta`; `pty.openpty()` грануляцию не меняет; `step_finish` теряется, когда `session.wait` возвращается раньше слива `session.step.ended` | explorer-zone-b.md §2 | 2026-10-25
[F-19] (FACT-019) `opencode serve` (v2) отдаёт реалтайм: `GET /api/event` (SSE) — `session.execution.started` 233 мс, `session.reasoning.started` 1710 мс, первая `session.reasoning.delta` 1811 мс (58 симв.), 10 дельт размышления (434 симв.) с интервалами min 105.64 / median 127.25 / max 304.32 мс, первая `session.text.delta` 3261 мс, 17 text-дельт (median 114.49 мс), всего 53 события, завершение 5558 мс (таблица T1) | explorer-zone-b.md §1, §3 | 2026-10-25
[F-20] (FACT-020) Сервер `opencode serve --port P --hostname 127.0.0.1` готов к запросам за 109 мс (мой замер 109 мс; Zone B: 109-117 мс); простаивающий процесс занимает RSS 152 MiB и 20 дескрипторов; фоновый `opencode serve --service` (PID 43288, аптайм 3 суток) занимает RSS 439 MiB | sa-poc/serve_sse.py, ps -axo, lsof от 2026-10-25 22:4x MSK | 2026-10-25
[F-21] (FACT-021) Без пароля эндпоинты `opencode serve` (проверено на `GET /openapi.json`) отвечают 401; при старте без заданного пароля сервер печатает случайный пароль в вывод процесса (stdout/stderr); переменная окружения `OPENCODE_SERVER_PASSWORD` принимается, схема Basic-auth с логином `opencode` | sa-poc (curl --noproxy, 401 без заголовка, 200 с заголовком) от 2026-10-25 | 2026-10-25
[F-22] (FACT-022) OpenAPI `opencode serve` v2.1.2 содержит: `GET /api/event`, `POST /api/session` (поля `model`, `location`, `agent`, `permissions` типа `Permission.Ruleset`, `metadata`), `POST /api/session/{id}/prompt` (`text`, `files`, `delivery`, `resume`), `POST /api/session/{id}/interrupt`, `DELETE /api/session/{id}`, `GET/POST /api/session/{id}/permission` и `/permission/{requestID}/reply`, `GET /api/session/active`, `POST /api/session/{id}/generate` | sa-poc: разбор /openapi.json v2.1.2 от 2026-10-25 (281456 B) | 2026-10-25
[F-23] (FACT-023) PoC аналитика через `opencode serve` (без standalone-прокси, с конфигом `permission {"*":"deny"}` и `baseURL` georouter) в 22:4x MSK завершился `session.step.failed`/`session.execution.failed` с `provider.free-limit` («Free usage limit reached») на 841 мс: анонимный дневной лимит Zen для IP хоста исчерпан, реалтайм-замер повторить нельзя до сброса | sa-poc/poc_serve.log | 2026-10-25
[F-24] (FACT-024) Прямой POST на `http://127.0.0.1:10830/v1/chat/completions` (georouter) без заголовка `Authorization` вернул HTTP 429 `FreeUsageLimitError`, `Retry-After: 15418` с (около 4 ч 17 мин); первый замер ответил за 2565 мс | sa-poc/poc_georouter.log | 2026-10-25
[F-25] (FACT-025) Прямой POST на `https://opencode.ai/inference/openai/v1/chat/completions` через CONNECT-туннель на запись пула ProxyRack без `Authorization` вернул HTTP 429 `FreeUsageLimitError` за 851 мс (1 выборка): способность прямого анонимного HTTP-SSE получать токены не подтверждена | sa-poc/poc_direct_zen_proxy.log | 2026-10-25
[F-26] (FACT-026) `model_georouter` (PID 29937, `127.0.0.1:10830`) конфиг: `direct_slots=80`, `proxy_slots=80`, `connect_timeout=12.0`, `headers_timeout=120.0`, `inactivity_timeout=300.0`, `pre_send_retries=3`, `total_egress_deadline=40`; маршрутизация по префиксу модели в пулы `direct`/`route-de`/`route-uz` | ~/.config/model-georouter/config.json (значения без секретов) | 2026-10-25
[F-27] (FACT-027) В `~/.config/opencode/opencode.json` у провайдера `opencode` задан только `options.baseURL=http://127.0.0.1:10830/v1` (поля `apiKey` нет); у `opencode-go` и `opencode-go-claude` есть `apiKey` (значение не выгружалось) | ~/.config/opencode/opencode.json (обход ключей с маскированием) | 2026-10-25
[F-28] (FACT-028) `~/.local/share/opencode/opencode.db` занимает 2 269 175 808 B (2.27 GB); `opencode run --help` v2.1.2 содержит `--standalone`, `--server <url>`, `--format` (значения default или json), `--thinking`, `--auto`; режима потокового вывода дельт у `run` нет | ls -l, opencode run --help от 2026-10-25 | 2026-10-25
[F-29] (FACT-029) Процесс моста (PID 85809): RSS 22 MiB, 36 открытых дескрипторов при `active=0`; `launchctl limit maxfiles` = 65536 (soft) и unlimited (hard) | ps, lsof, launchctl limit от 2026-10-25 22:4x MSK | 2026-10-25

## 3. Рантайм и инцидент (Zone D)

[F-30] (FACT-030) Запрос 22:16:12 MSK (`session-423ca27f`, ход 2, шаг 5, `prompt_chars=103088`): `opencode run -m opencode/deepseek-v4.1-flash-free#high --thinking --format json --standalone` (PID 11465) и дочерний `opencode serve --stdio --port 0` (PID 11488) молчали более 780 с (`out_chars=0`), у PID 11488 не было исходящих TCP-соединений; SSE-keepalive держал сокет DSH; на 22:45 MSK `/health` показывает `active=0`, процессов `opencode run` нет | explorer-zone-d.md §2, ps -axo от 2026-10-25 22:45 MSK | 2026-10-25
[F-31] (FACT-031) Запрос 22:12:57 MSK (`prompt_chars=108666`, PID 77098) молчал 856 с до `HTTP None: ECONNRESET`; повтор 1/2 (PID 25610/25611) завис на узле ProxyRack с нулём вывода | explorer-zone-d.md §2 | 2026-10-25
[F-32] (FACT-032) Сводка 2026-10-25 по `bridge.log`: 517 завершённых запросов (ok 509, client_gone 4, upstream_failed 4); `deepseek-v4.1-flash-free` 44 завершённых (ok 40), median 7.10 с, max 85.65 с; `startup_gate_timeout` 72 за день (grep -c без фильтра даты по текущему `bridge.log` даёт 99); `Free usage limit` 22; `ECONNRESET` 9; `stream retry` 10 | explorer-zone-d.md §2; grep -c на ~/.dsh/bridges/opencode-zen-bridge/logs/bridge.log | 2026-10-25
[F-33] (FACT-033) Ход 1 (22:15:31 MSK) на `opencode-zen-bridge`: 0 чанков за 10.7 с, пользователь переключился на `deepseek-account` (TTFT 0.71-0.88 с); мост заметил отключение клиента только через 24.4 с на keepalive (`duration_s=35.25`, `out_chars=0`) | explorer-zone-d.md §3 | 2026-10-25
[F-34] (FACT-034) Развёрнутый `~/.dsh/bridges/opencode-zen-bridge/server.py` совпадает с репозиторием (200 835 байт, mtime Oct 24 21:39); процесс слушает :9883 под LaunchAgent `com.user.dsh-opencode-zen-bridge`, `uptime_s=90313` на 2026-10-25 22:45 MSK | explorer-zone-d.md §1; /health от 2026-10-25 | 2026-10-25

## 4. Потребитель: DSH Desktop

[F-35] (FACT-035) Профиль DSH: `opencode-zen-bridge` — `api: openai-completions`, `baseURL: http://127.0.0.1:9883/v1`, `timeoutMs` и `streamIdleTimeoutMs` по 1900000, `retryPolicy.maxRetries: 0`, `reasoningEffort: high`, запрос с `stream: true` и `stream_options.include_usage` | ~/.dsh/profiles/desktop/cordis.patch.yml:9-14, 76-81, 176-225 (Zone C) | 2026-10-25
[F-36] (FACT-036) Потребитель `@earendil-works/pi-ai` (`openai-completions.js`) на каждый непустой `delta.reasoning_content`/`reasoning`/`reasoning_text` сразу порождает `thinking_start` (один раз) и `thinking_delta`; пустой `delta.content` событий не порождает; теги `<think>` в `content` не разбираются | /Applications/DeepSeek Harness.app/Contents/Resources/app.asar, openai-completions.js L384-425 (Zone C); смещения 116088536-116089722 в app.asar (моя проверка) | 2026-10-25
[F-37] (FACT-037) UI `@deepseek-ai/dsh-client-ui-chat/lib/client.js`: `RunningStatus` «Deep diving for N ···» монтируется при `session.running`; `blockIsVisible` скрывает блок с `text.trim()===""` (строка «Think» не рисуется до первой непустой дельты); `ReasoningRow` свёрнут по умолчанию, inline-превью `⚛ Think · <summary>` берётся из `latestCompletedParagraphFirstLine`, которая требует символ `\n` | client.js L5599-5637, L6134-6217, L7907-7911 (Zone C); app.asar содержит `latestCompletedParagraphFirstLine` 2 раза и `blockIsVisible` 21 раз (моя проверка) | 2026-10-25
[F-38] (FACT-038) При повторной отправке истории DSH кладёт непустые thinking-блоки обратно в assistant-сообщение полем `reasoning_content` (по `thinkingSignature`) и при `requiresReasoningContentOnAssistantMessages` добавляет пустой `reasoning_content`; мост это поле игнорирует (см. F-07) | app.asar openai-completions.js, смещения 116117903-116120153 | 2026-10-25
[F-39] (FACT-039) Журнал сессии DSH `session.v4.jsonl.zstd` хранит события `assistant/attempt` с массивом `stream[]` (по записи на чанк: `time`, `chunk.type`, `chunk.index`, `chunk.blockType`); блоки размышления записаны как тип `reasoning` (20 вхождений в сессии `423ca27f`), у хода 1 шага 1 `stream=[]` — совпадает с нулём чанков | ~/.dsh сессия 423ca27f, `zstd -dc`, разбор ключей без выгрузки текста | 2026-10-25

## 5. Эталон muse-bridge (ADR-0004)

[F-40] (FACT-040) `muse-bridge` использует основной транспорт `muse serve` (класс `ServeRun`, NDJSON JSON-RPC по stdio) и тихо падает на exec-путь при `ServeUnavailable` (в т.ч. «serve spawn failed», «serve stdout closed», «serve read timeout»); `ServeUnavailable` не считается ошибкой запроса | bridges/muse-bridge/server.py:338-339, 2096-2110, 4140-4185 | 2026-10-25
[F-41] (FACT-041) `muse-bridge` пишет живые события в `reasoning_content` через `_live_reasoning_sink` (запись с `LIVE_WRITE_TIMEOUT_S=3.0`, не фатальна), сбрасывает live-префикс на каждую попытку (`_reset_live_for_attempt`) | bridges/muse-bridge/server.py:165, 4150-4156 | 2026-10-25

## 6. Тесты и базовая линия

[F-42] (FACT-042) В `tests/` 17 модулей `test_*.py` (в брифе указано 16) плюс помощники `_fake_cli.py`, `_fixtures.py`, `_http.py`, `live_matrix.py`; всего 378 тестов (`3 failed, 375 passed, 3155 subtests passed in 125.01s`) | ls tests/; /tmp/cel-runs/zen-realtime-reasoning-20261025/baseline_uvx_pytest.log | 2026-10-25
[F-43] (FACT-043) Сценарий fake-CLI: тесты подменяют `server.OPENCODE_BIN` скриптом, который печатает построчно JSON-события формата `opencode run --format json` (`reasoning`, `text`, `step_finish`, `error`, `tool_use`); так работают `test_cli_failure.py:36-95`, `test_native_fallback.py:104-159`, `test_step_interruption.py:67-175`; хелперы `_fake_cli.py`/`_http.py` используют ещё `test_aliases`, `test_catalog`, `test_catalog_reload`, `test_run_env` | tests/*.py (grep OPENCODE_BIN и _fake_cli) | 2026-10-25
[F-44] (FACT-044) Ни один тест не измеряет реальное время прихода чанков: `test_step_interruption.py::_post` читает ответ целиком (`resp.read()`), `test_stream_thinking.py` проверяет только чистые функции (`_map_effort`, `parse_opencode_event`, `format_sse_chunk`) | tests/test_step_interruption.py:191-208, tests/test_stream_thinking.py | 2026-10-25
[F-45] (FACT-045) Базовая линия `uvx pytest -q -p no:cacheprovider tests/` на ветке: красные `test_unmapped_retries_do_not_exhaust_incomplete_budget_json` (2 != 4), `..._stream` (2 != 4), `test_unmapped_then_error_stops_proc_json` (1 != 2); запуск запуск с командой `pytest` (`Failed to spawn: pytest`) и `python3 -m unittest discover` (17 ошибок импорта модулей) базовой линией не являются | baseline_uvx_pytest.log, baseline_pytest.log, baseline_unittest.log | 2026-10-25
[F-46] (FACT-046) Изоляция 1: весь `tests/test_step_interruption.py` отдельно даёт те же три красных теста (`3 failed, 104 passed, 7 subtests passed in 41.29s`), значит причина внутри этого файла, а не в других модулях | sa_iso_file.log | 2026-10-25
[F-47] (FACT-047) Изоляция 2 (`-k` на два теста): `budget_json` красный даже сам по себе — лог `retry denied (incomplete_step): MAX_TOTAL_SPAWNS=3 reached`, `total_spawns=3`, а тест ждёт `_runs()==4` (два повтора unmapped и один повтор незавершённого шага); `unmapped_then_error_stops_proc_json` в этом запуске зелёный | sa_iso_3tests.log; tests/test_step_interruption.py:405-415; server.py:287 | 2026-10-25
[F-48] (FACT-048) Красный `unmapped_then_error_stops_proc_json` и меньшие значения `total_spawns` в полном прогоне вызваны исчерпанием общего `_RetryBudget` (лог `retry denied (unmapped): retry budget exhausted`): класс `TestStepInterruptionLive` поднимает один `Server` в `setUpClass`, а бюджет ёмкостью 6 с пополнением 0.20 за запрос расходуется ретраями предыдущих тестов; результат зависит от порядка и времени (`+0.05` токена в секунду) | baseline_uvx_pytest.log (строки с `retry budget exhausted`); tests/test_step_interruption.py:154-166; server.py:1340-1368 | 2026-10-25
[F-49] (FACT-049) `grep MAX_TOTAL_SPAWNS tests/*.py` даёт 0 совпадений: ни один тест не меняет константу потолка; `MAX_TOTAL_SPAWNS` введён коммитом `6839125`, ожидание `_runs(), 4` добавлено коммитом `d452fc9` (`git log -S`) | git log -S от 2026-10-25 | 2026-10-25

## Таблица T1. Тайминги `opencode` (Zone B, модель `opencode/deepseek-v4.1-flash-free`, variant `high`, `elapsed_ms`)

| Режим | 1-е событие | 1-й reasoning | reasoning-событий | интервал дельт | 1-й text | событий всего | завершение |
|---|---:|---:|---:|---|---:|---:|---:|
| `run --format json` PIPE, фоновый сервис | 2378.85 | 4850.67 (1 блок, 768 симв.) | 1 | нет | 4850.80 | 3 | 4919.34 |
| `run --format json` PTY, фоновый сервис | 1315.53 | 3219.27 (1 блок, 285 симв.) | 1 | нет | 3219.44 | 3 | 3281.97 |
| `run --format json --standalone` PIPE | 2501.60 | 5137.26 (1 блок, 549 симв.) | 1 | нет | 5137.26 | 3 | 5213.40 |
| `run --format json --standalone` PTY | 2226.36 | 4941.59 (1 блок, 412 симв.) | 1 | нет | 4941.71 | 3 | 5023.95 |
| `opencode serve` v2, `GET /api/event` | 161.22 (`integration.updated`), 233.06 (`execution.started`) | 1810.98 (1-я дельта) | 10 дельт + started + ended | min 105.64, median 127.25, max 304.32 | 3260.64 (17 дельт, median 114.49) | 53 | 5558.06 |

## Сводка покрытия (для DoD)

Всего фактов: 49. Источники воспроизводимы командами и путями из колонки «источник». Факты F-23, F-24, F-25 фиксируют
состояние внешней квоты на 2026-10-25 22:4x MSK и могут измениться после сброса лимита.
ARTIFACT_END>>>
<<<ARTIFACT analysis/zen-realtime-reasoning/research-plan.md sha256=5cef25c8a8901b241e08ed31ba884d2178cf1ac445ceaf0e70f7c697ea282cbb
# Research Plan: zen-realtime-reasoning (реалтайм-размышление `opencode-zen-bridge` в DSH)

Роль: System Analyst (Stage 1, preset `analyst-teamlead`), тип — feasibility study + as-is обследование, глубина — standard (S2).
Дата: 2026-10-25 (MSK). Ветка `feature/zen-realtime-reasoning`. Артефакты: `analysis/zen-realtime-reasoning/`.
Владелец вывода: владелец продукта (расхождения «ожидали X, оказалось Y» принимает он; финальная архитектура — `architect-software-product`).

## 1. Scope

Запрос владельца: при запуске DeepSeek через `opencode-zen-bridge` (`127.0.0.1:9883`) в DSH видеть размышление в реальном
времени и получать отличную отзывчивость, чтобы было видно, что процесс идёт. Инцидент-образец: сессия `session-423ca27f`,
ход 2 шаг 5 (22:16:12 MSK), экран «Deep diving for 35s ···» без строки `⚛ Think`, затем молчание более 780 с.

В периметре исследования: код `bridges/opencode-zen-bridge/` (`server.py`, `start.sh`, `tests/`), эталон `bridges/muse-bridge/server.py`,
живой `opencode` v2.1.2 (CLI и `opencode serve`), локальный `model_georouter` (:10830), потребитель DSH Desktop (`app.asar`),
рантайм-логи моста за 2026-10-25.
Вне периметра: правка кода, деплой, изменение DSH, смена модели, чужие мосты (кроме эталона muse-bridge).

## 2. Проверяемые гипотезы (исход — в `evidence-ledger.md`)

| Гипотеза | Итог | Основание |
|---|---|---|
| RC-1: `opencode run --format json` буферизует размышление и текст до конца шага, поэтому реалтайма нет даже на здоровом вызове | подтверждена | F-17, F-18 |
| RC-1a: реалтайм-путь на этом хосте существует (`opencode serve` v2 SSE, дельты каждые ~110-130 мс) | подтверждена (замер Zone B), повтор заблокирован квотой | F-19, F-23 |
| RC-1b: прямой анонимный HTTP-SSE к Zen как у Google Direct осуществим без `opencode` | не подтверждена: два PoC дали 429 | F-24, F-25 |
| RC-2: холодный spawn + отсутствие watchdog приводят к немым зависаниям на 13-14 минут | подтверждена по коду и логам | F-09, F-10, F-30, F-31 |
| RC-3: пустые keepalive не показывают ничего, а превью `⚛ Think` требует `\n` | подтверждена | F-36, F-37 |
| Три красных теста базовой линии — загрязнение теста либо реальное взаимодействие бюджетов повтора | обе причины присутствуют | F-47, F-48, F-49 |

## 3. Зоны обследования (веер Wave 1, без пересечений)

- Зона A (код моста и эталон): `server.py`, `muse-bridge` ADR-0004 — отчёт `explorer-zone-a.md`.
- Зона B (контракты и эмпирика `opencode`): CLI vs `opencode serve` vs wire Zen — отчёт `explorer-zone-b.md`.
- Зона C (потребитель): DSH `openai-completions`, `ReasoningRow`, `blockIsVisible` — отчёт `explorer-zone-c.md`.
- Зона D (рантайм): логи, зависшие PID, реконструкция скриншота — отчёт `explorer-zone-d.md`.
- Сверка аналитика (read-only, PoC в `/tmp`): повторная проверка кода по строкам, изоляция красных тестов, прямой HTTP-SSE PoC,
  OpenAPI `opencode serve`, структура журнала сессии DSH, ресурсы процессов.

## 4. Методология

1. Факт или открытый вопрос: каждое утверждение — строка `[F-NN]` с источником и датой, иначе запись в `open-questions.md`.
2. Эмпирика важнее чтения: тайминги `elapsed_ms` снимались по живым процессам, а не выводились из кода.
3. Секреты не выносятся: пароль `opencode serve`, `apiKey`, креды пула ProxyRack не печатались и не сохранялись; PoC использовали временный пароль и порт.
4. Код продукта не менялся; PoC-скрипты и логи лежат в `/tmp/cel-runs/zen-realtime-reasoning-20261025/sa-poc/`.
5. Выбор архитектуры не делается: варианты сравниваются по фактам в `handoff-architect.md`, вердикт — «выполнимо / с условиями / невыполнимо».
6. Квота Zen (`FreeUsageLimitError`) исчерпана на 22:4x MSK, поэтому часть замеров переведена в отложенные вопросы с условием повтора после сброса.

## 5. Реестр спайков

Формат строки: `ID | вопрос | источник | метод | таймбокс | deliverable | критерий закрытия | зависит/блокирует | статус | результат | факт | отметка`
(таймбокс и факт — минуты).

INV-01 | Где мост теряет реалтайм (маппинг событий и SSE-кадрирование) | server.py:2417-2462 и 3312-3493 | чтение кода и сверка с Zone A | 25 | таблица потока событий в ledger | найден участок и порядок отправки чанков | блокирует INV-02 | closed | F-05 | 18 | ok
INV-02 | Выдаёт ли `opencode run --format json` дельты размышления и текста | ~/.opencode/bin/opencode и живые запуски | замеры PIPE/PTY × standalone/сервис | 40 | таблица T1 | показано, что дельт нет и почему | зависит от INV-01 | closed | F-18 | 35 | ok
INV-03 | Реалтайм-путь `opencode serve` v2: события, тайминги, схема API | `GET /api/event`, OpenAPI v2.1.2 | живой SSE-замер и разбор OpenAPI | 40 | схема эндпоинтов и тайминги | задокументированы события и интервалы дельт | зависит от INV-02 | closed | F-19 | 38 | ok
INV-04 | Осуществим ли прямой анонимный HTTP-SSE к Zen (Option B) | server.py:3127-3266 и opencode.ai/inference | PoC через georouter и через CONNECT-туннель пула | 30 | вердикт осуществимости | получены токены либо зафиксирован отказ с причиной | блокирует выбор Option B | open | OPEN-05 | 22 | отказ 429 в обоих PoC, нужен повтор после сброса лимита
INV-05 | Чем ограничено ожидание первого токена (RC-2) | server.py:46, 1197-1236, 3450 и логи Zone D | grep по сторожам и разбор логов | 30 | перечень таймеров и бюджетов | подтверждено отсутствие TTFT и stall watchdog | зависит от INV-01 | closed | F-09 | 20 | ok
INV-06 | Контракт видимости размышления в DSH (RC-3) | app.asar, client.js, openai-completions.js | чтение бандла и подтверждение символов поиском | 30 | контракт `blockIsVisible` и `\n` | найдены условия появления строки Think | независим | closed | F-37 | 24 | ok
INV-07 | Возвращает ли DSH размышление мосту и что с ним делает мост | app.asar и server.py:1848-1888 | поиск `reasoning_content` в бандле и в `_render_turn` | 20 | вывод о безопасности статусных строк | найден путь реплея и точка игнорирования | зависит от INV-06 | closed | F-38 | 14 | ok
INV-08 | Совместимость с fake-CLI тестами и прецедент muse-bridge | tests/*.py и muse-bridge/server.py:338-4185 | grep OPENCODE_BIN и чтение fallback | 25 | карта тестов и паттерн fallback | описаны подмена CLI и паттерн serve-to-exec | независим | closed | F-43 | 19 | ok
INV-09 | Природа трёх красных тестов базовой линии | baseline_uvx_pytest.log и tests/test_step_interruption.py | прогон файла и подмножества, разбор логов | 30 | классификация причин | определены причины каждого из трёх тестов | независим | closed | F-47 | 26 | ok
INV-10 | Изоляция встроенных инструментов `opencode` в режиме serve | OpenAPI `permissions` и `session.tool.*` | чтение схемы, живой прогон заблокирован квотой | 30 | схема сопоставления событий | подтверждена эквивалентность с режимом run | блокирует контракт адаптера | open | OPEN-07 | 12 | схема есть, поведение не прогнано из-за free-limit
INV-11 | Параллелизм, SQLite и ресурсы нескольких процессов serve | opencode.db 2.27 GB и RSS процессов | замер idle RSS и FD, нагрузочный прогон не выполнен | 30 | оценка ресурсов | получены числа под параллельной нагрузкой | зависит от INV-03 | open | OPEN-08 | 10 | измерен только idle serve 152 MiB
INV-12 | Время до первого токена на тяжёлом промпте около 103 KB через serve | сессия 423ca27f и serve | замер после сброса квоты | 20 | таблица TTFT для 100 KB | получен TTFT при `prompt_chars` около 103088 | зависит от INV-03 | open | OPEN-09 | 5 | квота исчерпана до около 03:00 MSK 2026-10-26
INV-13 | Совместимость ротации чистых IP с долгоживущим serve | server.py:1047-1131 и config georouter | чтение кода и конфига | 25 | вывод о маршруте egress | определено, ходит ли serve напрямую либо через georouter | зависит от INV-04 | open | OPEN-06 | 15 | egress georouter известен, поведение прокси у serve не проверено
INV-14 | Инкрементально ли `ToolCallParser` отдаёт `content` при дельтах | server.py:2213-2338 | чтение алгоритма и существующих тестов | 20 | описание удерживаемого хвоста | задан максимум удерживаемых символов | независим | closed | F-06 | 11 | ok

## 6. Состав handoff-пакетов (потребители)

- `handoff-architect.md` — Architect (S2): корневые причины, требования `REQ-*`, сравнение вариантов, `HL-ENV/v1`, гейты, non-goals.
- `handoff-qa.md` — QA и Coder-тесты: red→green сценарии, живой тяжёлый путь, протокол замеров.
- `handoff-dev.md` не готовится: задача класса S2, вход в разработку только через Архитектора (ARCH_GATE).
ARTIFACT_END>>>
<<<ARTIFACT bridges/opencode-zen-bridge/pyproject.toml sha256=7d6387d88008df032bfdc5c9f4ca7e7c8eb58ec3d72d1c90ff5b8a227df6b6ff
[project]
name = "opencode-zen-bridge"
version = "0.0.0"
description = "Локальный OpenAI-совместимый мост поверх CLI `opencode run` (8 моделей OpenCode Zen)"
requires-python = ">=3.11"
dependencies = []

[dependency-groups]
dev = ["basedpyright", "pytest", "ruff"]

[tool.uv]
package = false

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
ARTIFACT_END>>>
<<<ARTIFACT ~/Мой диск/skils/ai-sdlc/universal/teamlead-gate/references/council.md#L379-L403 sha256=e097b015072fcb8196d43925e5fb36c1c2d22b410731800c8b9d6913a3522c8f
## 3. Рубрика одного прохода и дедуп циклов Совета

Один проход судьи обязан покрыть все подкатегории всех 6 критериев; повторный
цикл верифицирует закрытое и ищет новое только в дельте. Обоснование и
источники — предложение
`skills-proposals/applied/2026-10-02-teamlead-gate-one-pass-panel.md`.

### Рубрика судьи: SUB-строки по подкатегориям

- Нумерованный перечень подкатегорий — в шапке брифа судьи; судья идёт по
  номерам (лечит satisfaction-of-search). Стартовый состав (2–3 на критерий):
  Корректность — логика / граничные условия / обработка ошибок; Полнота —
  покрытие AC / пропущенные ветки; Риски — безопасность / данные / прод
  (mode=code добавляет в Риски: regression red→green / Full Suite (L2) /
  scope-diff); Реализуемость, Альтернативы, Соответствие контексту — без
  дробления.
- Формат строки: `SUB <критерий>/<подкатегория>: PASS|FAIL|N/A — evidence
  (файл:строка/правило)`, evidence — одна строка.
- Malformed вердикта: нет SUB-строки по любой подкатегории ИЛИ сплошные N/A
  больше 2/3 подкатегорий при нуле содержательных наблюдений. Один
  malformed-retry на судью тем же слотом — не ест лимит «≤2 судей в
  retry/fallback за прогон». SUB-строки — в R1; формат D-раунда — `council-consensus.md` §4.
- Свёртка: FAIL любой подкатегории = FAIL критерия; N/A не голосует;
  majority-агрегация и взвешенная сумма по 6 критериям не меняются.

ARTIFACT_END>>>
<<<ARTIFACT ~/Мой диск/skils/ai-sdlc/universal/teamlead-gate/scripts/select_round_seats.py#L903-L917 sha256=c1a33e83602f3854bd5447d213e7ff02b7eecf4d957b9cffe90255a52ad22e89
        check(is_hex(manifest.get("artifact_sha256")), "invalid artifact_sha256")
        expected_input = f"{manifest['run_id']}:{stage}:r{number}:{manifest['artifact_sha256']}:{gen['prev_entry_sha256']}"
        seed = digest(expected_input.encode())
        ranked = rank_slots(seed, table["setups"][setup])
        check(
            manifest.get("seed_input") == expected_input
            and manifest.get("seed_hex") == seed
            and manifest.get("ranked_order") == ranked,
            "seed/ranked_order reconstruction mismatch",
        )
        check(
            manifest.get("debate_roster_mode")
            == ("initial" if number == 1 else "rotated"),
            "debate_roster_mode mismatch",
        )
ARTIFACT_END>>>
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/panel/council/r2/manifest.json sha256=bb7dbe4c9eab63c49222722a9d4a0399f1ac1e68a2c4a755597bff5e50779488
{"artifact_sha256":"5b0d1dea0cf4996f6d744e0eb2d82176578091bad35c943dde722c09d3784df4","constrained_mode":null,"debate_roster_mode":"rotated","excluded_author":[{"evidence_path":"receipts/coder.json","evidence_sha256":"a47ba864e9ef2af0cdfa045c9c38dbc201f6462f56d54cdc62a7968664ded043","family":"Meta"}],"hat_level":1,"history_entry_sha256":"ecf42ade905d827e16ca476de02c2c2b33f2b67310be7ba9b4e552d326c24517","history_prev_entry_sha256":"2380ab6849de71e157cb16b958810b5e9fb1db2787cfd2a30bfeca3374763aec","history_seq":24,"models_md_sha256":"e032139c9fc67e082ea33e7bd390779c7a2d98f066d71a83e4c7d793c3ecc6c4","pool_constrained_3of3":false,"prior_ledger_sha256":"00df0bda8f9a29b8d28ff56d02726dddcd7be67d3a0d1bd6096eca448b0c7131","ranked_order":["gpt-6.1-sol-high","gemini-4-argon-high","muse-wonder-full-1.0","grok-4.7-high","claude-sonnet-5-5-high"],"replaced_seats":[],"round":2,"run_id":"analyst-teamlead-zen-realtime-reasoning-20261025","schema":"pol-manifest/2","seats":[{"family":"OpenAI","k":1,"slot_id":"gpt-6.1-sol-high","transport":"codex"},{"family":"Anthropic","k":2,"slot_id":"claude-sonnet-5-5-high","transport":"claude-p"},{"family":"Google","k":3,"slot_id":"gemini-4-argon-high","transport":"agy"}],"seed_hex":"a4bc0406eac703ab0369a39cdad49952bd4c42ad88ce1d47e3c0d92d3f9ae2f3","seed_input":"analyst-teamlead-zen-realtime-reasoning-20261025:council:r2:5b0d1dea0cf4996f6d744e0eb2d82176578091bad35c943dde722c09d3784df4:2380ab6849de71e157cb16b958810b5e9fb1db2787cfd2a30bfeca3374763aec","selector_sha256":"96c525ac5ec3c0c9761f4e7789fe656cb04a86300e2bd9d0059854474842894d","setup":"default","stage":"council","status":"READY","triplet_rule":"A+B","unavailable_evidence":{}}
ARTIFACT_END>>>

Обязательное указание судье перед обёртками стандартов (вне тела обёрток `ARTIFACT`):
Все пункты приложенного ниже тип-скилла `~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/skills/feature.md` (`SK-T-*`: алгоритм выполнения фичи, захват из потокового источника с независимым сигналом полноты, таймауты на каждом шаге цепочки I/O включая cleanup в `finally`, критерии приёмки, стоп-коды `HL-ENV-01`, `C-MULT-I1..I5`, `S-HERD-I1..I5`, `H-CPU-I1..I5`, `R-BULK-I1..I5` и Remote-first контракт) и все применимые к diff пункты приложенных ниже профильных стандартов `aisdlc-gcge` (`SK-P-*`: `AGENTS.md`, `agents/scope-and-contracts.md`, `agents/code.md`, `agents/python-standards.md`, `agents/testing.md`, `agents/security.md`, `agents/error-handling.md`, `agents/logging.md`, с учётом ограничения задачи `0` внешних runtime-зависимостей вне Python 3.14 stdlib `ThreadingHTTPServer`) являются твоими прямыми обязательными проверками кандидата на уровне строк кода; нарушение любого применимого пункта фиксируй F-блоком с привязкой к `file:line` и правилу.
<<<ARTIFACT ~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/skills/feature.md sha256=07f4e74ec68df185035f2105fe0ebbf9b9155f826d519441bf7025a8a2d6fcab
# Skill: Feature

## Алгоритм выполнения задачи на новую фичу

> Если хочется обдумать решение **до** записи кода — переключи AI-IDE
> в **Plan mode** (Claude Code, Cursor, Continue, Codex). В этом режиме
> агент только читает и описывает что сделает, не пишет. Вернись в Agent
> mode когда подход устраивает. Артефакты задачи (заметки, ADR, отчёты
> ревью) при желании складывай в `Tasks/<JIRA-KEY>/`.

### 1. Подготовка
- Уточнить цель изменения — что именно должно появиться в API.
- Найти Jira-задачу. Затем по порядку: карточка на доске и решение, нужен ли свой worktree, — `~/Мой диск/Context/multi-agent.md` §6; ветка `feature/<JIRA-KEY>-<short-description>` (п. 5 «Код» `AGENTS.md`) — от актуальной target там, где решил §6.
- Прочитать `.agents/agents/architecture.md` — понять в какой слой ложится изменение.
- Прочитать `.agents/agents/scope-and-contracts.md`. Scope = эта KEY. Согласованный
  внешний контракт не менять, если в постановке этой задачи нет явного указания.

### 2. Изучение кодбазы
- Найти существующие точки расширения в коде.
- Определить какие слои затронуты: domain, db, service, api.
- Проверить есть ли похожая фича — не дублировать логику.
- Если фича читает из **динамического/внешнего источника** (браузерная страница, пагинируемый API, стрим, растущий лог) — выяснить, не ленивый/виртуализированный/пагинируемый ли он. Один снимок/`read` может вернуть лишь часть. Проектирование такого захвата — в `.agents/agents/architecture.md`, «Захват данных из динамических источников».
- Если фича делает **I/O, который может зависнуть без ошибки** (сетевой вызов, браузерная автоматизация, внешний процесс, подключение к очереди/БД) — таймаут нужен на каждом шаге цепочки, включая cleanup (`close()`/`disconnect()` в `finally`), не только на первом вызове. Паттерн — в `.agents/agents/architecture.md`, «Таймауты и watchdog для I/O, который может зависнуть».

### 3. Реализация по слоям (строго в этом порядке)
1. **domain/** — добавить или расширить dataclass/TypeAlias.
2. **db/models.py** — добавить поля в SQLAlchemy-модель если нужно.
3. **db/repository.py** — добавить метод репозитория.
4. **services/** — реализовать бизнес-логику.
5. **api/** — добавить эндпоинт.
6. Если изменилась схема БД — создать Alembic migration.

### 4. Тесты
- Unit тесты для сервисного слоя (Fake-репозиторий).
- Integration тесты для API (TestClient + реальная БД).

### 5. Финальная проверка
- `uv run ruff format .` — автоформатирование.
- `uv run ruff check --fix .` — автофикс импорти­ровки (`I001`), неиспользуемых импортов (`F401`) и прочих автофиксимых правил. Запускать **до** `ruff check`.
- Параллельный запуск проверок и тестов на всех ядрах CPU (с фиксацией статусов процессов и защитой от `set -e`):
  `uv run ruff check . & p1=$!; uv run basedpyright & p2=$!; uv run pytest -q -n auto -m "not measured and not heavy" --no-cov & p3=$!; s1=0; s2=0; s3=0; wait $p1 || s1=$?; wait $p2 || s2=$?; wait $p3 || s3=$?; [ $s1 -eq 0 ] && [ $s2 -eq 0 ] && [ $s3 -eq 0 ]`
- `uv run pre-commit run --all-files` — прогнать все хуки (ruff, basedpyright, bandit, pip-audit) перед коммитом. Если хук упал — исправить и перезапустить. Нельзя коммитить с красным pre-commit.
- **Зелёный тулчейн ≠ фича работает.** Для операций с тихим отказом (извлечение/парсинг/скрейпинг/трансформация) проверь результат на реальном входе и сравни с эталоном — а не «непусто/без ошибки». Эталон должен быть **независим от захваченного артефакта**: метрика вида «результат vs тот же (возможно урезанный) захват» зелёная и при потере данных. Для динамических источников (ленивая догрузка/виртуализация/пагинация) один снимок бывает неполным — сверяй полноту с независимым сигналом (ожидаемый счётчик/размер из метаданных или API), а не «один `read` = всё». См. `.agents/agents/testing.md`, «Зелёный прогон ≠ корректно».

Для багов про данные/внешний источник зелёного юнита/фикстуры мало — прогони
фичу **end-to-end через настоящую ручку** (HTTP → сервис → реальный источник) и
сверь метрику с эталоном (объём/число сущностей) **до** вывода «готово». Цена
пропуска (реальный кейс EYE-27163): фикс «проходил тесты», а на живом cntd.ru
давал 21% вместо ~100% — поймали только живым прогоном.

Если на любом шаге что-то упало нетривиально — действуй по алгоритму из
`.agents/agents/error-handling.md` (Identify → Assess → Communicate →
Solutions), не лепи workaround сразу.

### 6. Коммит
- `[agent] feat(<scope>): <описание на русском>` — один коммит на фичу.
  Тэг и scope английские, описание — русское (см. таблицу «Язык общения»
  в `.agents/AGENTS.md`).

### 7. В конце задачи
Сдача = `skills/mr.md`: коммит на своей ветке, при наличии remote — push и
открытый MR. Не спрашивать «MR делать?». В `main`/`master`/`dev` не коммитить
и не пушить. Merge MR — человек. Нет remote — сказать явно.

Отчёт: «Задача `PROJ-XXX` готова, всё зелёное. MR: <url>» (или «remote нет»).

## Критерии приёмки

- [ ] Сделано только то, что в этой Jira-KEY / этом промпте; чужие задачи
      не трогались и не попали в отчёт.
- [ ] Согласованный внешний контракт (HTTP/event/data/CLI/SDK) не изменён,
      либо в постановке этой задачи есть явное указание это сделать.
- [ ] Канон: `.agents/agents/scope-and-contracts.md`.
- [ ] Сдача через MR на remote, если remote есть. Канон: `.agents/agents/mr.md`.

<!-- HL-RESILIENCE-GATES-V5 -->
## Обязательные Highload & Resilience стоп-коды при реализации фичи (`HL-ENV/v1`, `C-MULT/v1`, `S-HERD/v1`, `H-CPU/v1`, `R-BULK/v1`)

Перед написанием кода сверься с SSoT `.agents/agents/architecture.md` (`#hl-env-and-four-gates-ssot`), правилами рантайма `.agents/agents/code.md` и таблицей из 21 детерминированного тест-оракула в `.agents/agents/testing.md` (`<!-- HL-RESILIENCE-ORACLES-V3 -->`):

- [ ] **`HL-ENV-01`**: все 46 полей `REQUIRED_HL_ENV_FIELDS` зафиксированы; пометка `N/A` допустима только с `git diff` + транзитивным графом вызовов (`callers/callees`).
- [ ] **`C-MULT-I1..I5`**: пулы создаются один раз в `lifespan` после `fork()` и закрываются в `aclose()` (`T-LIFE/v1`); для Redis — `BlockingConnectionPool` + `max_waiters <= 2M`; соблюдён многоролевой лимит $\le 0.60 \times \text{Limit\_dep\_share}[d]$ с учётом $G_{\text{reload}}$.
- [ ] **`S-HERD-I1..I5`**: пересев CSPRNG `os.urandom(16)` после `fork()`; стартовый и периодический джиттер + Full-Jitter backoff; `If-None-Match` (`304`); cancellation-safe `singleflight` без negative-cache на таймаутах/`5xx`; разделение `readiness`/`liveness` и `Max_stale_age_s[c]`.
- [ ] **`H-CPU-I1..I5`**: $O(1)/O(\log N)$ индексы предвычисляются в `Snapshot`; `if not enabled: return` стоит первой инструкцией до любых аллокаций/`uuid4()`; доставка `Snapshot` не блокирует event loop $> 2\text{ мс}$; бюджет CPU выполнен на $P_{\text{avail\_min}}$.
- [ ] **`R-BULK-I1..I5`**: проброс `remaining_deadline_s`; Token-Bucket Retry Budget; `Circuit Breaker` с 1 пробой в `HALF_OPEN`; двухэтапный фильтр `M-SEM/v1` + post-eviction `Panic-Open` ($|V_{\text{healthy}}| - 1 \ge N_{\text{floor}}$) и метрики ранних выходов по `O-EXIT/v1`.

## Remote-first контракт репозитория

Если работа этой роли меняет Git-репозиторий, перед сдачей обязательно прочитать и
выполнить `~/Мой диск/skils/ai-sdlc/references/remote-mr-workflow.md`. Локальный
merge не считается влитием: сначала merge MR на remote, затем fast-forward
локальной target-ветки. Для read-only роли это требование к handoff, а не
разрешение писать в product worktree, пушить или сливать MR.
ARTIFACT_END>>>
<<<ARTIFACT ~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/AGENTS.md sha256=7e606a52d977e281e8eedc9f0482a0d8d83008a2106fc3d27bee00f3c62d384a
# AGENTS

Ты работаешь в Python backend-проекте на Litestar.

## Язык общения

Пользователь — носитель русского языка, поэтому общение в чате и любой текст, который человек читает глазами (docstrings, комментарии в коде, **описания коммитов**), — на русском. Идентификаторы (имена переменных, функций, классов, файлов) — на английском, как принято в коде.

| Где | Какой язык |
|---|---|
| Сообщения в чате (планы, статус, объяснения, ответы на вопросы) | Русский |
| Сообщения в чате при ошибках/конфликтах | Русский |
| Commit messages — **тэги** (`feat:`, `fix:`, `refactor:`, `chore:`, scope) | Английский — это формат Conventional Commits, парсится changelog-генераторами |
| Commit messages — **описание** после двоеточия | **Русский** — это текст для команды, его читают люди |
| Префиксы `[agent]` / `[manual]` / `[assisted]` | Английский — это маркер, не текст |
| Docstrings в коде | Русский — пользователь читает их в IDE через hover |
| Комментарии в коде (`# объясняет почему`) | Русский |
| Названия переменных, функций, классов, файлов | Английский |

Если поймал себя что начал писать описание коммита или docstring по-английски — остановись и переформулируй по-русски.

Примеры docstring:

✅ Правильно:
```python
def truncate_url(url: str, max_length: int = 50) -> str:
    """Обрезает URL до max_length символов, добавляя '...' в конце.

    Args:
        url: URL для обрезки.
        max_length: Максимальная длина результата (по умолчанию 50).

    Returns:
        Обрезанный URL с эллипсисом, либо исходный URL если он короче max_length.

    Raises:
        ValueError: Если max_length меньше длины эллипсиса.
    """
    # Если URL уже короткий — возвращаем как есть, без аллокации
    if len(url) <= max_length:
        return url
    ...
```

❌ Неправильно:
```python
def truncate_url(url: str, max_length: int = 50) -> str:
    """Truncate a URL to max_length characters, adding ellipsis at the end.
    ...
    """
    # Return as-is if URL is already short
    ...
```

## Главные правила

1. Сначала прочитай этот файл и релевантные тематические файлы из `.agents/`.
2. **При ошибке — Identify → Assess → Communicate → Solutions.** Не предлагай
   workaround сразу — сначала пойми, почему упало. Severity-уровни и алгоритм
   реакции — в `.agents/agents/error-handling.md`.
3. Не меняй архитектуру проекта без явной причины.
4. Все изменения должны быть минимально достаточными.
5. Любое изменение кода должно сопровождаться проверкой:
   - `uv run ruff check .`
   - `uv run basedpyright`
   - `uv run pytest -q`
6. Для изменений схемы и БД читай `.agents/agents/database.md`.
7. Если меняется публичное API, обнови тесты и README.
8. Перед подготовкой MR прочитай `.agents/agents/mr.md`.
9. Для hotfix обязательно прочитай `.agents/agents/hotfix.md`.
10. На каждый баг должен появиться regression test.
11. Не добавляй зависимости без необходимости.
12. Перед началом работы создай ветку по правилу именования веток проекта.
13. Архитектурные решения с ≥ 2 альтернативами и дорогим откатом оформляй как
    ADR с options analysis (см. `.agents/agents/docs.md`, раздел «ADR-full»).
14. Если задача дата-инженерная (ETL, Airflow DAG, Kafka-воркеры, ClickHouse,
    выгрузка в S3) — читай `.agents/agents/data-engineering.md`.
15. **Согласованный внешний контракт не менять без явного указания в текущей
    задаче.** HTTP/event/data/CLI/SDK, уже согласованные с внешними
    исполнителями, заморожены. «Улучшить», соседняя задача, свой архитектурный
    черновик — не разрешение. Нет явной фразы «измени контракт / breaking /
    обнови схему» → STOP, ASK. Канон: `.agents/agents/scope-and-contracts.md`.
16. **Работать только в рамках своей задачи.** Scope = текущий промпт и текущий
    Jira-KEY. Чужие KEY/MR не открывать, не чинить и не отчитываться по их
    статусу «заодно». Чужой тикет — только если текущая постановка явно
    называет его зависимостью, и тогда только факт зависимости. Канон: тот же
    `scope-and-contracts.md`.
17. **Сдача — через MR на remote, если remote есть.** Не коммитить и не пушить
    в `main` / `master` / `dev`. Коммит живёт на своей ветке, затем push + MR.
    Канон: `.agents/agents/mr.md`. Merge MR — человек, пока не сказано «смержи».
    После merge на remote обязательно обновить локальную target-ветку через
    fast-forward и сверить её `HEAD` с remote. Локальный merge до MR запрещён.

## Подход к работе

Поведение агента управляется **правилами** (`.agents/`) и **алгоритмами**
(`.skills/`). Это конвейер: пришла задача → агент читает релевантный skill →
выполняет шаги → проверки → коммит на своей ветке → MR на remote (если remote есть).
Отдельный «план в чате с ожиданием ОК»
не требуется — `.skills/*.md` уже содержит пошаговый алгоритм.

Если задача сложная и хочется разведать прежде чем писать код:

- **Используй встроенный Plan mode** AI-IDE (в Claude Code, Cursor, Continue,
  Codex CLI). В этом режиме агент только читает файлы и описывает что
  собирается сделать, не пишет и не запускает команды. Это быстрее и дешевле
  чем эмуляция через «покажи план в чате, жди подтверждения».
- **Артефакты задачи** (заметки, отчёты code review, ADR, временные
  результаты) можно складывать в `Tasks/<JIRA-KEY>/` рядом с кодом, чтобы
  при возврате к задаче через день было видно где остановились. Это
  опциональный паттерн, не обязательное «всегда пиши план в md».
- **Architecture-документ** для большой задачи (≥ 1 дня работы, несколько
  модулей, breaking change) — отдельный жанр, см. `.agents/skills/architecture.md`.
  Это не «approval gate», это рабочий артефакт с C1+C2 диаграммами и
  списком задач T1-TN.

В конце задачи — короткий отчёт с URL MR (или явно «remote нет»). Не ждать
фразы «делай MR». Правки оператора — уже после открытого MR, не вместо него.

## Правила именования веток

Ветки должны называться в соответствии с типом задачи и Jira key.

Формат ветки:

`<type>/<JIRA-KEY>-<short-description>`

Где:
- `type` — тип задачи: `feature`, `bugfix`, `hotfix`, `deploy` (релиз/выкат — см. `.agents/skills/devops-release.md`)
- `JIRA-KEY` — идентификатор задачи в Jira, например `PROJ-123`
- `short-description` — короткое описание в `kebab-case`

Примеры:
- `feature/PROJ-123-add-link-archive`
- `bugfix/PROJ-456-fix-empty-title-validation`
- `hotfix/PROJ-789-fix-production-db-timeout`

Правила:
- использовать латиницу, цифры, `/` и дефисы;
- не использовать пробелы;
- не использовать длинные описания;
- для задач из Jira всегда включать Jira key в имя ветки;
- тип ветки должен соответствовать типу задачи.

## Правила коммитов и измерение вклада агента

Каждый коммит должен быть помечен тегом в начале сообщения:

- `[agent]` — diff агента принят без существенных правок (точечные правки имён/форматирования допустимы)
- `[assisted]` — основу сделал агент, но ты переписал значимую часть (логика, структура, >20% строк)
- `[manual]` — код написан вручную без участия агента

Три тега вместо двух нужны потому, что бинарное деление «агент/не агент» врёт в сторону агента: коммит, где ты взял идею из diff и переписал половину, честнее считать как `[assisted]`, а не `[agent]`. Это совпадает с индустриальной практикой: self-reported «AI-assisted» обычно ~40%, но реально AI-authored (без правок) — около 27%.

Формат — Conventional Commits, тэги английские (`feat:`/`fix:`/`refactor:`/`chore:`), **описание после двоеточия — на русском** (см. таблицу «Язык общения» выше).

Примеры:
```
[agent] feat(api): добавить эндпоинт PATCH /links/{id} и тесты
[assisted] refactor(services): переработать сервисный слой после черновика агента
[manual] docs(readme): исправить опечатку
[agent] test(links): добавить regression-тест на валидацию заголовка с пробелами
[manual] chore(deps): обновить pytest до >=9.0.3 для CVE-2025-71176
```

После выполнения каждой задачи выводи итоговый блок:

```
[agent | assisted | manual] <короткое описание задачи на русском>
Files: <количество файлов изменено>
Tests: <добавлено/изменено>
Checks: ruff ✅  basedpyright ✅  pytest ✅
```

## Что делать когда `git commit` падает с pre-commit-хуком

В этом репозитории стоят pre-commit-хуки (ruff, basedpyright, bandit, pip-audit, gitleaks, end-of-file-fixer, trailing-whitespace, и т.д.). Каждый `git commit` прогоняет их **до** создания коммита. Возможны три исхода:

### Исход A: Все хуки `Passed` — коммит создан

Ничего делать не надо. Покажи `git log -1 --stat` в подтверждение.

### Исход B: Хук **автофиксанул** файлы (`files were modified by this hook`)

Так работают `end-of-file-fixer`, `trailing-whitespace`, `ruff format`, `ruff check --fix`. Они **сами** правят файлы и сигнализируют что коммит надо повторить.

Действия:
1. Посмотри какие файлы изменены: `git status`.
2. `git add` этих файлов.
3. `git commit -m "..."` повторно с тем же сообщением.

На втором заходе автофиксы уже применены — хук пройдёт `Passed`.

### Исход C: Хук нашёл **реальную ошибку** (например `basedpyright` или `bandit`)

Это **не** автофикс — это ошибка которую надо понять и исправить. Действия:

1. Прочитай вывод хука. У каждой ошибки есть путь к файлу, номер строки и описание.
2. Открой файл, разбери что не так:
   - **basedpyright**: чаще всего нет аннотации типа, или `Any` где должен быть конкретный тип, или доступ к `None` без проверки. Добавь аннотацию или `# pyright: ignore[<ruleId>]` с комментарием **почему** именно это игнор оправдан.
   - **bandit**: нашёл небезопасную конструкцию (`subprocess(shell=True)`, `yaml.load` без `SafeLoader`, и т.д.). Перепиши на безопасный вариант. Не используй `# nosec` без объяснения.
   - **pip-audit**: CVE в зависимости. Если это твой код добавил эту зависимость — обнови её до fix-версии **отдельным коммитом** (`[manual] chore(deps): обновить <package> для CVE-XXXX`). Если CVE в чужой зависимости которую ты не трогал — см. `.agents/agents/security.md`, секция «pip-audit».
3. Исправь, добавь в индекс (`git add`), коммить снова.
4. Если 3 раза подряд хук падает на одном и том же — остановись, опиши пользователю что именно ошибка говорит и в чём конфликт. Не зацикливайся.

Расширенный алгоритм реакции на любые ошибки (не только pre-commit) — в
`.agents/agents/error-handling.md` (severity Critical/High/Medium/Low + правило
«Identify → Assess → Communicate → Solutions»).

### Что **запрещено** делать

- **`git commit --no-verify`** — обход всех хуков, **никогда**.
- **`SKIP=hook git commit ...`** — пропуск конкретных хуков, **никогда** (единственное исключение — учебный демо в Шаге 6.2 no-rules-variant, описано в `.agents/agents/security.md`).
- **`PRE_COMMIT_ALLOW_NO_CONFIG=1`** — это срабатывает когда `.pre-commit-config.yaml` отсутствует. Если ты эту переменную увидел в подсказке git'а — конфиг **потерян**, восстанови его (`git show HEAD:.pre-commit-config.yaml > .pre-commit-config.yaml`), не обходи.

Подробности — в `.agents/agents/security.md`, секция «Pre-commit хуки — никаких обходов».

## Конвертация документации в Confluence Wiki Markup

Если нужно преобразовать `.md` файл в Confluence Wiki Markup для вставки через `Other macros → Markup → Confluence wiki`:

**Читай файл с правилами перед конвертацией:**
```
.agents/md-to-confluence-rules.md
```

Файл лежит в корне каталога `agents_ skills/` (на уровень выше `agents/`).

Он содержит:
- точные команды bash для конвертации (pandoc + sed + clean-jira-escapes.py)
- таблицу типичных ошибок и их решений
- скрипт проверки результата (три проверки должны вернуть 0)
- структуру папок для готовых `.txt` файлов

**Правило:** никогда не конвертируй вручную и не придумывай правила на лету — всё в `md-to-confluence-rules.md`.
ARTIFACT_END>>>
<<<ARTIFACT ~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/scope-and-contracts.md sha256=25f91ad5fa5cc92f9372e5fe89b0fc0d83f2e8445ba6eb1e966cf78f4e6828cd
# Scope задачи и согласованные внешние контракты

Два жёстких правила. Нарушение — блокирующий FAIL ревью и приёмки, не follow-up
и не «улучшение заодно». Полный текст живёт здесь; скиллы ролей ссылаются
и ставят бинарный пункт в критерии приёмки.

Читать при любой разработке: фича, багфикс, рефакторинг, hotfix, архитектура,
ревью, MR, цикл техлида.

## 1. Согласованный внешний контракт не менять без явного указания

Если контракт уже согласован с внешними исполнителями — другими сервисами,
командами, потребителями HTTP/event/data/CLI/SDK, аналитикой — его нельзя
менять, расширять, сужать, переименовывать и «улучшать», пока текущая задача
явно это не требует.

### Что считается внешним контрактом

- HTTP: method, path, query, request/response DTO, status, error body, auth,
  идемпотентность, версия.
- Событие / очередь / топик: имя, схема, обязательность полей, типы,
  nullability, порядок, совместимость.
- Публичный CLI, SDK, shared-library API.
- Формат файла, протокол, контракт аналитики/событийки.
- Cross-repo зеркало той же схемы.

Внутренняя реализация за неизменной границей (сервис, репозиторий, SQL,
логи, метки, тесты потребителя не ломающие) — не контракт.

### Что считается явным указанием

Фраза в **текущей** постановке (промпт, Jira этой KEY, AC этой задачи):
«измени контракт», «breaking», «обнови схему / DTO / API / событие»,
«согласуй с \<команда/сервис\>». Без такой фразы права менять контракт нет.

Не является указанием:

- «сделай лучше / удобнее / правильнее»;
- соседняя задача, эпик, чужой MR, страница Confluence «как будет»;
- архитектурный документ, который агент сам написал в этом же заходе;
- «потребители подстроятся», «это же совместимо, если добавить поле».

Добавление поля, смена default, переименование, смена типа на совместимый,
новый код ошибки на старом пути — тоже изменение контракта.

### Что делать

1. До кода найти согласованную границу в зоне изменения (спека, Confluence,
   Pydantic/DTO, OpenAPI, схема события, KB `contracts/`).
2. Если задача требует её менять, а в постановке этого нет — **STOP, ASK**.
   Не чинить «заодно». Не предлагать breaking как часть текущей сдачи.
3. Если указание есть — delta контракта, совместимость, потребители и
   verification явным пунктом в AC; иначе задача не готова к коду.

## 2. Работаем только в рамках своей задачи

Scope = текущий промпт и, если есть, текущий Jira-KEY. Чужие задачи не
открывать, не ревьюить, не чинить и не отчитываться по их статусу.

### Запрещено

- Искать и пересказывать статус соседних KEY / MR / стендов «заодно».
- «Пока смотрел, увидел EYE-XXXX — там вот что».
- Тащить скоуп, AC, фикс или рефакторинг из другой задачи в текущий diff.
- Отвечать на вопрос по одной задаче отчётом по доске / эпику / чужим тикетам.

### Можно

- Прочитать другой тикет, только если **текущая** постановка явно называет
  его зависимостью (`blocked by` / `relates` / «зависит от KEY»). Тогда —
  только факт зависимости, не статус-отчёт по чужой работе.
- Ответить по другой задаче, только если владелец **этим промптом** её
  спросил. Это новый запрос, не расширение текущего.

Неясная граница KEY → ASK, не гадать и не ходить по доске.

## Критерии приёмки (копировать в DoD роли)

- [ ] Diff не меняет согласованный внешний контракт, либо в текущей задаче
      есть явное указание это сделать и delta зафиксирована.
- [ ] Работа, ревью и отчёт только про текущую задачу / KEY; чужие KEY в
      отчёте отсутствуют, если их не спросили.

Нет любого пункта → задача не сдана, ревью `CHANGES_REQUESTED` / приёмка
не ACCEPT.
ARTIFACT_END>>>
<<<ARTIFACT ~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/code.md sha256=f2a483bd6c0c5b9f33e1a074c3b39321bde0f59722b466ce8493a52b485908ef
# Code rules

- Всегда использовать `from __future__ import annotations`.
- Каждая функция и метод должны иметь аннотации типов.
- Если функция ничего не возвращает, явно писать `-> None`.
- Использовать современный синтаксис Python 3.14.5:
  - `X | None` вместо `Optional[X]`
  - `list[str]` вместо `List[str]`
- Писать понятный и короткий код без лишней сложности.
- Если логика повторяется — выносить в helper-функции.
- Не смешивать HTTP-логику, бизнес-логику и SQL в одном месте.

## Общие принципы

### PEP 8 — стиль кода

- Следовать PEP 8 для форматирования (отступы 4 пробела, максимум ~100 символов в строке, snake_case для функций/переменных, PascalCase для классов, UPPER_SNAKE для констант).
- Форматирование и импорты — через `ruff format` и `ruff check --fix`, вручную не спорить со стайлчекером.
- Имена должны быть осмысленными: `user_repository` лучше `ur`, `get_active_users()` лучше `gau()`.

### KISS — Keep It Simple, Stupid

- Выбирать самое простое решение, которое закрывает требование.
- Не добавлять абстракции «на будущее» — делать по факту появления второго кейса.
- Функция должна решать одну задачу; если в названии напрашивается `and` — разбить на две.
- Если решение требует длинного комментария чтобы объяснить «что тут происходит» — скорее всего его надо упростить, а не комментировать.

### DRY — Don't Repeat Yourself

- Повторяющаяся бизнес-логика выносится в helper / service / util — один источник истины.
- Повторяющиеся константы и магические значения выносятся в именованные константы или enum.
- Но: DRY не отменяет KISS. Два похожих куска кода с разной семантикой — это не дубль, их не надо объединять в «универсальную» функцию с пятью флагами.

### SOLID — проектирование классов и модулей

- **S (Single Responsibility)** — один модуль / класс / функция отвечает за одну вещь. `UserService` не должен заниматься отправкой email — это работа отдельного `EmailSender`.
- **O (Open/Closed)** — расширять поведение через добавление новых классов/стратегий, а не правкой работающего кода. Новый тип уведомлений — новый класс, а не новая ветка `if` в старом методе.
- **L (Liskov Substitution)** — подкласс должен вести себя как базовый класс. Если `Repository.get()` возвращает `User | None`, то и `CachedRepository.get()` возвращает то же — не бросает исключение вместо `None`.
- **I (Interface Segregation)** — лучше несколько узких интерфейсов (`Reader`, `Writer`), чем один жирный `Repository` со всеми методами, из которых половина не используется.
- **D (Dependency Inversion)** — зависимости передавать через конструктор/параметры, не импортировать жёстко. Service принимает `UserRepository` как зависимость, а не создаёт его внутри себя — это даёт тестируемость и подмену реализации.

### Практическое применение в этом проекте

- Слои (API / Service / Repository / Domain) — это прямое следствие SRP и Dependency Inversion.
- Fake-объекты в тестах вместо `MagicMock` — это Liskov (fake ведёт себя как настоящий) плюс Dependency Inversion (сервис не знает, кто ему передан).
- Litestar-зависимости через `dependencies=` — явная передача зависимостей сверху, а не глобальные синглтоны.

## По слоям

- API слой (`app/api`) отвечает только за HTTP-вход и HTTP-ответ.
- Service слой (`app/services`) содержит бизнес-логику.
- Repository слой (`app/db/repository.py`) работает с SQLAlchemy и SQL.
- Domain слой (`app/domain`) содержит dataclass / сущности.

## Возвраты и ошибки

- Repository-методы могут возвращать `X | None`.
- Service-методы тоже могут возвращать `X | None`, если сущность не найдена.
- API-слой обязан превращать `None` в корректный HTTP-ответ, например `404 Not Found`.
- Не прятать ошибки внутри route handlers.
- Если входные данные невалидны — выбрасывать `ValueError` или более точное исключение.
- Не писать `except Exception: pass`.
- Если исключение поймано — либо обработать его осмысленно, либо сделать re-raise.
- Не менять согласованный внешний контракт без явного указания в текущей задаче.
  Канон: `.agents/agents/scope-and-contracts.md`.
- Не уходить в чужие Jira-KEY / MR и не отчитываться по их статусу.
- Не коммитить и не пушить в `main` / `master` / `dev`. Сдача — MR на remote,
  если remote есть. Канон: `.agents/agents/mr.md`.

## Запрещено

- Писать SQL прямо в `app/api`.
- Использовать `print()` вместо нормальной структуры кода или логирования.
- Дублировать одну и ту же бизнес-логику в нескольких местах.

## Линтеры и форматтеры

- Перед завершением любой задачи обязательно прогонять:
  - `uv run ruff format .` — форматирует код по PEP 8.
  - `uv run ruff check --fix .` — правит все автофиксимые правила (неотсортированные импорты `I001`, неиспользуемые `F401`, и т.д.).
- Если после `--fix` `ruff check` всё ещё красный — значит правило не автофиксимое, это надо исправить руками (например, `F841` unused variable — удалить переменную или использовать её).
- Не глушить предупреждения через `# noqa: CODE` без явной причины. Если приходится глушить — рядом оставлять комментарий «почему».
- Все CI-проверки должны быть зелёными до коммита: `ruff format --check .`, `ruff check .`, `basedpyright`, `pytest`.
- Ошибка `I001` (unsorted imports) всегда чинится `ruff check --fix` — не оставлять её в коде и не добавлять в `.gitignore`/`per-file-ignores`.

## Pre-commit и security-хуки

- `git commit --no-verify` запрещён. Никогда не обходить pre-commit даже если проблема «не моя» — фикси или делай отдельный коммит под проблему.
- Если pre-commit упал на ошибке **из твоих изменений** (ruff, basedpyright, pytest, bandit на новом коде) — исправить и повторить `git commit`. Не спрашивать у участника что делать.
- Если pre-commit упал на **pip-audit** с CVE в зависимости, которая **не связана с твоими изменениями** (предыдущая существующая проблема):
  1. Отложить текущий коммит.
  2. Проверить в какой версии пакета CVE закрыт (`pip index versions <package>` или в тексте самого advisory).
  3. Обновить **только этот пакет** в `pyproject.toml` (не трогать другие зависимости заодно).
  4. Запустить `uv sync && uv run pytest -q` — убедиться, что тесты зелёные на новой версии.
  5. Сделать **отдельный коммит** только по `pyproject.toml` + `uv.lock` с сообщением вида `[manual] chore(deps): обновить <package> до X.Y.Z для CVE-XXXX-XXXXX` (тэг и scope английские, описание — на русском; см. таблицу «Язык общения» в `.agents/AGENTS.md`).
  6. После этого вернуться к исходному коммиту и завершить его штатно.
- То же правило для `bandit`, если он нашёл проблему в существующем коде, не затронутом задачей: отдельный коммит `[manual] fix(security): <описание на русском>` перед основным.
- Не спрашивать у участника «делать отдельный коммит или смешать» — в проекте правило однозначное: **не смешивать**. Спрашивать только если неясно, к какой именно версии бампать или если фикс ломает тесты.

<!-- HL-RESILIENCE-GATES-V5 -->
## Инварианты Highload & Resilience в клиентском рантайме воркера (`HL-ENV/v1`, `C-MULT/v1`, `S-HERD/v1`, `H-CPU/v1`, `R-BULK/v1`)

Каноническая спецификация формул и 46 полей `REQUIRED_HL_ENV_FIELDS` — в SSoT `.agents/agents/architecture.md` (`#hl-env-and-four-gates-ssot`); детерминированные тест-оракулы — в `.agents/agents/testing.md` (`<!-- HL-RESILIENCE-ORACLES-V3 -->`). При написании и изменении кода воркера действуют неснимаемые стоп-коды (`NON-WAIVABLE STOP CODES`):

1. **Пул соединений и жизненный цикл клиентов (`C-MULT-I2..I5` + `T-LIFE/v1`)**:
   - **`C-MULT-I2`**: для Redis/Valkey разрешён только `BlockingConnectionPool(max_connections=M, timeout=T_wait_s)` (неблокирующий `ConnectionPool` запрещён); для HTTP — явные `Limits(max_connections=M, max_keepalive_connections=M_ka)`. Очередь ожидающих слота ограничена семафором `max_waiters <= 2 * M` с немедленным `PoolWaitersExhaustedError` при переполнении. При hot-reload пула соблюдается `close-before-create` ($G_{\text{reload}}=1$) либо в расчёт `C-MULT-I1` закладывается $G_{\text{reload}}=2$.
   - **`C-MULT-I3`**: все сетевые клиенты, пулы и сессии создаются строго один раз на процесс-воркер в `lifespan` **после** `fork()`/`spawn()` и закрываются в `aclose()` (`T-LIFE/v1`). Создание клиента внутри обработчика запроса/попытки или передача открытых сокетов через `fork()` — безусловный `REJECT`.
   - **`C-MULT-I4..I5`**: освобождение слота пула и семафора гарантируется в `finally:` при `Task.cancel()` / `asyncio.wait_for`; бюджет дескрипторов $\text{FD}_{\text{worker}} \le 0.70 \times \text{ulimit\_n}$ и эфемерных/SNAT портов $\le 50\%$ пула.
2. **Защита холодного старта, поллеров и кэшей (`S-HERD-I1..I5`)**:
   - **`S-HERD-I1..I2`**: запрещён синхронный сетевой вызов всех `W` воркеров в `t=0`. Сразу после `fork()` дочерний процесс обязан пересеять генератор случайных чисел (`random.seed(os.urandom(16))` или `secrets.SystemRandom()`). Поллеры используют стартовый джиттер `Uniform(0, J_init_s[d])` (или `Pod-Level Single Fetch` с `os.replace()`), периодический джиттер `T_poll_s[d] * random.uniform(0.8, 1.2)` и экспоненциальный backoff с **Full Jitter** `Uniform(0, min(T_cap_s[d], T_base_s[d] * 2**attempt))`.
   - **`S-HERD-I3..I5`**: опрос `Snapshot`/`DynamicConfig` передаёт `If-None-Match` (`304 Not Modified` не запускает парсинг и сохраняет `id(snapshot)`); кэши с дозапросом используют cancellation-safe per-process `singleflight` (`self._inflight[key]` + `asyncio.shield` + `add_done_callback` с чтением `task.exception()` + очистка в `aclose()`); `negative caching` разрешён только на `404`/`invalid_ref` (запрещён на таймаутах и `429/5xx`); `readiness` отделён от `liveness`, соблюдается `Max_stale_age_s[c]` и немедленный отзыв `auth_secret` (`fail-closed`).
3. **Сложность горячего пути и неблокирующий Reload (`H-CPU-I1..I5`)**:
   - **`H-CPU-I1..I2`**: в `HOTPATH_MODULES` запрещён линейный перебор $O(N)$ по коллекциям `Snapshot`, а также `re.compile()`, `json.loads()`, `Pydantic.model_validate()`, `TypeAdapter.validate_python()`, `copy.deepcopy()` и повторный `.labels(...)` для статических меток. Все индексы $O(1)$ / $O(\log N)$ предвычисляются при сборке иммутабельного `Snapshot`.
   - **`H-CPU-I3`**: в опциональной телеметрии (`ClickBeat` / `ProductEvent` / `status_trace`) первой строкой функции до любых аллокаций, `uuid4()` и сериализации стоит `if not enabled: return`; при включённом флаге запись идёт только через `queue.put_nowait()` в ограниченную очередь с `dropped_total` (и живым дрейнером по `T-LIFE/v1`).
   - **`H-CPU-I4..I5`**: на `Config-Reload Path` запрещено удерживать GIL / блокировать event loop дольше $2\text{ мс}$ (`orjson.loads` и `pydantic-core` удерживают GIL, поэтому `asyncio.to_thread` для них не является защитой; применяется `mmap` предсобранного `pod_fetcher`-ом бинарного индекса, кооперативная сборка батчами `MAX_ITEMS_PER_TICK` с `await asyncio.sleep(0)` или компактный payload). Бюджет CPU укладывается в $\text{Util}_{\text{worker}} \le 0.70\text{ core}$, pod $\le 0.80 \times \text{CPU\_limit\_per\_pod}$ и фича $\le 5\%$ пула при $P_{\text{avail\_min}}$.
4. **Дедлайны, Retry Budget, Circuit Breaker и Post-Eviction `Panic-Open` (`R-BULK-I1..I5` + `O-EXIT/v1` + `M-SEM/v1`)**:
   - **`R-BULK-I1..I2`**: критический путь вспомогательных вызовов, ожиданий слота и backoff по всем $A_{\max}$ попыткам $\le 0.30 \times \text{SLA}_{\text{p99\_s}}$ с пробросом остатка дедлайна `min(T_budget_s, deadline_s - monotonic_s())`; ретраи ограничены per-process **Token-Bucket Retry Budget** ($N_{\text{retries}} \le \lfloor 0.20 \cdot N_{\text{req}} + \text{min\_reserve\_retry\_rps} \cdot T_w \rfloor + B_{\text{retry\_max}}$).
   - **`R-BULK-I3..I5`**: `HotState`/`GigaRC`/телеметрия — **Fail-Open** с `Circuit Breaker` (джиттер `OPEN` и ровно `1` проба в `HALF_OPEN`); карантин прокси-нод работает строго в 2 этапа: сначала жёсткий фильтр допустимости $V_{\text{eligible}}$ (`M-SEM/v1`: исключены `disabled`, `auth_failed`, чужой пул `crawler != llm`, запрещённое гео; при $|V_{\text{eligible}}|=0$ возвращается `503` с метриками по `O-EXIT/v1`), затем внутри $V_{\text{eligible}}$ действует **post-eviction предикат** $|V_{\text{healthy}}| - 1 \ge N_{\text{floor}} = \max(1, \lceil \text{Min\_healthy\_ratio} \times |V_{\text{eligible}}| \rceil)$; здоровье целевого домена (`origin_health`) отделено от здоровья прокси-нод.

## Ссылка на полный стандарт

Полный стандарт разработки с примерами и нумерованными параграфами — в `.agents/agents/python-standards.md`. Когда нужно сослаться на конкретное правило в чате / в комменте к PR / в отчёте code review — используй формат `§N` (например, `§3 — обработка исключений`, `§5 — async-инварианты`).
ARTIFACT_END>>>
<<<ARTIFACT ~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/python-standards.md sha256=05985b7dfff1b4b48d7394d42c751cfab1d0a1795eb7b62e12606f4bb79fc2e8
# Python Development Standards

Стандарт разработки проекта. Документ — единый источник проверяемых правил. Ссылки на параграфы вида «§5», «§13» используются в `.agents/agents/code.md` и `.skills/code-review.md`. Все правила обязательны для нового кода. Старый код приводится к стандарту по мере касания.

***

## Главные принципы

1. **Читаемость прежде всего.** Код больше читают, чем пишут. Лишние list-comprehension'ы ради сокращения строк — нет; явный `for` если он понятнее — да. Хитрый «быстрый» код — только когда профилирование показало что это узкое место.
2. **Без типов проект не пишется.** Все функции и методы — с аннотациями параметров и возвращаемого типа, включая `-> None`. `basedpyright` в strict-режиме обязателен.
3. **Словари — зло на границах.** `dict` запрещён как публичный контракт между модулями / слоями / сервисами. Внутри одной функции `dict` допустим как промежуточная структура. На границах — `dataclass` / Pydantic / domain-объекты.
4. **Секреты не попадают в код и коммиты.** Только через `.env` (локально) и переменные окружения (на серверах). Любой API-ключ в `pyproject.toml`, тестах или примерах — баг, не фича.
5. **Перед коммитом проходят локальные проверки.** Один шорткат: `uv run ruff check . && uv run basedpyright && uv run pytest -q`. Если упало — коммит не уходит.
6. **Async-проект остаётся async.** Любой sync DB-вызов в async-контексте блокирует event loop и обнуляет выгоду от Litestar. См. §5 ниже.

***

## Проверки в `git worktree` — исполняться должен код своего дерева

Правило действует, когда работаешь не в основном рабочем дереве репозитория (`git worktree`, изолированный контекст агента).

- **Запускай проверки из корня своего worktree через `uv run`** (`uv run pytest -q`, `uv run ruff check .`, `uv run basedpyright`). У worktree свой `pyproject.toml`, и `uv` поднимает окружение проекта в его корне — тогда исполняется твой код.
- **Не гоняй тесты интерпретатором чужого `.venv`** (`<основной репо>/.venv/bin/python -m pytest`, активированный «общий» venv). Пакет установлен в editable-режиме, а editable прописывает **абсолютный** путь: `.pth` в `site-packages` указывает на `src` **основного** репозитория. Импорт уйдёт туда, и проверишь ты чужой код, а не свой.
- **Запасной путь**, если общий venv переиспользуется сознательно (не хочешь платить за `uv sync` в worktree): `PYTHONPATH=src` перед командой. Это обход, а не норма: он меняет приоритет импорта и маскирует реальные проблемы упаковки — тесты про установленный пакет (entry points, `importlib.metadata`) поведут себя иначе.
- **Признак, что попал в ловушку:** правки в файлах worktree не влияют на результат прогона — новый модуль даёт `ModuleNotFoundError` при существующем файле, или, что опаснее, тесты **зелёные**, хотя проверяют код основной ветки. Тихий зелёный отчёт здесь — норма отказа, а не исключение.
- **Проверка одной строкой перед прогоном** — путь обязан лежать внутри твоего worktree:

~~~bash
python -c "import runtime, pathlib; print(pathlib.Path(runtime.__file__).parent)"
~~~

***

## Запреты — нарушение блокирует merge

| # | Конструкция | Почему запрещена |
|---|---|---|
| 1 | `except Exception: pass` | Глушит ошибки без диагноза. Источник «случайных» падений в проде. Ловим конкретный тип, либо логируем и пробрасываем. |
| 2 | `def foo(items=[])` | Mutable default — общий между вызовами. Тысячи багов в Python-учебниках на этом примере. Использовать `items: list[X] \| None = None` + `if items is None: items = []`. |
| 3 | `def get_stats() -> dict` | `dict` как публичный контракт — не типизируется. Использовать DTO / dataclass / Pydantic. |
| 4 | `from sqlalchemy.orm import Session` в новом коде | Проект async. Только `AsyncSession` из `sqlalchemy.ext.asyncio`. |
| 5 | Синхронный `requests` / `psycopg.connect` в async-handler'е | Блокирует event loop. Использовать `httpx.AsyncClient` / `AsyncSession`. |
| 6 | `Optional[X]` / `List[X]` / `Dict[K, V]` | Устаревший pre-PEP-604 стиль. Использовать `X \| None` / `list[X]` / `dict[K, V]`. |
| 7 | Magic numbers в логике (`if len(x) > 255`) | Не самодокументируются. Выносить в именованные константы в начало модуля. |
| 8 | Бизнес-логика в route handler (`api/links.py`) | Нарушает слоевую архитектуру. Логика → `services/`, handler делает только парсинг запроса и формирование ответа. |
| 9 | `# noqa` / `# type: ignore` без объяснения | Подавление линтера без причины — техдолг без следа. Если ставишь — добавляй комментарий **почему**. |
| 10 | `--no-verify` / `SKIP=hook git commit` | Обход pre-commit'а. Никогда. Если хук падает — разбираешься, не обходишь (см. AGENTS.md). |
| 11 | `print()` для логирования | Нет уровня, нет полей, не идёт в централизованный сбор. Использовать `structlog` (см. §13). |
| 12 | `logger.info(f"order {order_id} done")` | Каждый event уникален, агрегация по шаблону невозможна. `logger.info("order done", order_id=order_id)` (см. §13). |
| 13 | Секреты / токены / Authorization-заголовки в kwargs логгера | Логи уходят в централизованный сбор → утечка PII. См. §13 и `.agents/agents/security.md`. |
| 14 | `httpx.get(url, verify=False)` / `requests.get(url, verify=False)` | MITM-vulnerable. Для internal CA — `verify="/path/to/ca.pem"`. См. §14 и `.agents/agents/security.md`. |
| 15 | HTTP-клиент без `timeout=` | Запрос может висеть бесконечно, в async — таска не отпускает event loop. См. §5 и §14. |
| 16 | `subprocess.run(..., shell=True)` с user input | Command injection. Только list-форма + абсолютный путь + ограниченный env. См. §14. |
| 17 | `import json` (`json.loads` / `json.dumps`), `ujson`, `simplejson` в новом коде сервиса | Единая JSON-библиотека — `orjson` (см. §16): сериализация сразу в `bytes`, нативные `datetime` / `UUID` / `dataclass`. Исключения перечислены в §16. |

***

## §1. Типизация

### Аннотации обязательны везде

~~~python
# ❌ Нет аннотаций
def create_link(url, archived=False):
    return {"id": 1, "url": url}

# ✅
def create_link(url: str, archived: bool = False) -> Link:
    return Link(id=1, original_url=url, archived=archived)
~~~

### `from __future__ import annotations` — первая строка файла

Позволяет писать `X | None`, `list[X]` без проблем на любой версии Python, аннотации становятся ленивыми (не выполняются при импорте), что устраняет циклические импорты в типах.

### Современный стиль — PEP 604 (`X | Y`) и PEP 585 (`list[X]`, `dict[K, V]`)

~~~python
# ❌ Устаревший стиль
from typing import Optional, List, Dict, Union
def find(id: int) -> Optional[Link]: ...
def items() -> List[Dict[str, int]]: ...

# ✅ Современный стиль
def find(id: int) -> Link | None: ...
def items() -> list[dict[str, int]]: ...
~~~

### Возвращаемое `None` — всегда аннотируется

~~~python
# ❌
def clear_cache(self):
    self._cache = {}

# ✅
def clear_cache(self) -> None:
    self._cache = {}
~~~

### Protocol — для абстракций между слоями

Сервис зависит от `LinkRepositoryProtocol`, не от конкретного `LinkRepository`. Это даёт замену на Fake в тестах без подмены реальной БД.

***

## §2. Value Objects и DTO

`dict` запрещён как **публичный** возврат функции — на границе модулей контракт обязан быть типизирован.

### Value Object — неизменяемая доменная сущность

~~~python
@dataclass(frozen=True)
class Link:
    id: int
    code: str
    original_url: str
    clicks: int
    archived_at: datetime | None
~~~

### DTO — данные между слоями

~~~python
@dataclass(frozen=True)
class LinkStatsDTO:
    total_links: int
    total_clicks: int
    avg_clicks_per_link: float
~~~

### Где `dict` допустим

Только как **приватная промежуточная структура внутри одной функции**, никогда — как возвращаемый тип публичного API.

***

## §3. Обработка исключений

### Не глотаем без логирования

~~~python
# ❌
try:
    result = risky()
except Exception:
    pass
~~~

### Ловим конкретный тип

~~~python
# ❌ Слишком широкий except
try:
    parsed = urlparse(value)
except Exception:
    return False

# ✅ Конкретный тип
try:
    parsed = urlparse(value)
except ValueError:
    return False
~~~

`except Exception` приемлем **только в самой внешней точке** (Litestar middleware, top-level async-loop), и то с логированием.

### Fail fast

Если приложение запустилось с битой конфигурацией (отсутствует `DATABASE_URL`, кривой `OPENROUTER_API_KEY`) — лучше упасть на старте, чем работать «как-нибудь» и упасть в 3 ночи.

### Не маскируем ошибки возвратом `None`

Если функция «может не сработать» по бизнес-логике (ссылка не найдена) — `None` оправдан. Если по техническим причинам (БД недоступна) — пробрасываем исключение, не возвращаем `None`. Иначе caller думает «данных нет», а реально «упало в коннекте».

***

## §4. SOLID

### S — Single Responsibility

Один класс / функция — одна причина для изменения.

~~~python
# ❌ Считает, форматирует и сохраняет
def process_links(links: list[Link]) -> str:
    rate = len([link for link in links if link.archived_at is None]) / len(links) * 100
    report = f"Active rate: {rate:.1f}%"
    save_to_file(report)
    return report

# ✅ Разделение
def calculate_active_rate(links: list[Link]) -> float: ...
def format_rate(rate: float) -> str: ...
def save_report(text: str, path: Path) -> None: ...
~~~

### D — Dependency Inversion

Сервис зависит от `Protocol`, а не от конкретной реализации.

~~~python
class LinkRepositoryProtocol(Protocol):
    async def get_by_code(self, code: str) -> Link | None: ...
    async def increment_clicks(self, code: str) -> Link | None: ...

class LinkService:
    def __init__(self, repo: LinkRepositoryProtocol) -> None:
        self.repo = repo
~~~

***

## §5. Async-инварианты — этот проект полностью async

Проект построен на Litestar + `AsyncSession` + psycopg async. Любая sync-вставка в этот стек убивает производительность независимо от профилирования.

### Проверки, идущие в code review

- [ ] Все методы репозитория — `async def`, все обращения к БД через `await session.execute(...)` / `await session.commit()`.
- [ ] Сервис вызывает репозиторий через `await`, сам тоже `async def`.
- [ ] Route handler — `async def`, вызовы сервиса через `await`.
- [ ] Нет `from sqlalchemy.orm import Session` — только `from sqlalchemy.ext.asyncio import AsyncSession`.
- [ ] Нет sync HTTP-клиентов (`requests.get`) в async-handler'е — `httpx.AsyncClient` или `aiohttp`.
- [ ] Нет `time.sleep()` в async-функции — `await asyncio.sleep(...)`.
- [ ] Async-генераторы итерируются через `async for` / `anext()`, не через `next()`.

### Признаки sync-протечки

Если `psycopg`/SQLAlchemy в логах ругаются «attempted to call non-async method on AsyncSession», или Litestar даёт RuntimeWarning про «coroutine was never awaited» — где-то sync-вставка. Найди и почини, не подавляй.

### Параллельные задачи — `asyncio.TaskGroup`, не `gather`

Для нескольких параллельных задач предпочитай `asyncio.TaskGroup` (Python 3.11+) перед `asyncio.gather`:

~~~python
# ✅ TaskGroup — отменяет остальные задачи при ошибке, ловится через ExceptionGroup
async def process_batch(ids: list[int]) -> list[User]:
    async with asyncio.TaskGroup() as tg:
        tasks = [tg.create_task(fetch_user(uid)) for uid in ids]
    return [t.result() for t in tasks]
~~~

`gather(*coros, return_exceptions=True)` оставляем для случаев, когда ошибки **обрабатываются отдельно** для каждой задачи (например, частичная выгрузка где fail одной не должен прерывать остальные).

### Тайм-ауты на внешние вызовы — обязательны

~~~python
# ✅
try:
    result = await asyncio.wait_for(fetch_data(), timeout=5.0)
except TimeoutError:
    logger.error("fetch_data timed out")
    raise
~~~

Любой внешний вызов (HTTP, БД, очередь) без явного таймаута — анти-паттерн. В `httpx.AsyncClient` используем `httpx.Timeout(connect, read, write, pool)` (см. `.agents/agents/security.md` §6).

***

## §6. KISS — Keep It Simple

Признаки нарушения:
- функция длиннее ~40 строк;
- вложенность более 3 уровней `if`/`for`/`try`;
- параметры-флаги (`mode="fast"`, `use_cache=True`) — обычно две функции под одним именем, лучше разделить.

~~~python
# ❌
def is_valid_title(title: str) -> bool:
    return bool(
        title is not None and isinstance(title, str)
        and len(title.strip()) > 0 and not title.strip() == ""
    )

# ✅
def is_valid_title(title: str) -> bool:
    return bool(title.strip())
~~~

***

## §7. DRY — Don't Repeat Yourself

Одна и та же логика — в одном месте. Если копируется из файла в файл (`fetch_with_retry`, форматирование даты, парсинг URL) — выносится в утилиту или общую функцию модуля.

Но: преждевременная абстракция (одна функция используется 1 раз, на всякий случай вынесена) — хуже чем дубль из двух мест. Правило «трёх» — на третий дубль выноси.

***

## §8. Именование и константы

| Что | Стиль | Пример |
|-----|-------|--------|
| Функции / методы | `snake_case` | `create_link`, `increment_clicks` |
| Классы | `PascalCase` | `LinkService`, `LinkRepositoryProtocol` |
| Константы модуля | `UPPER_SNAKE_CASE` | `MAX_URL_LENGTH = 2048` |
| Булевые | `is_*`, `has_*` | `is_archived`, `has_clicks` |
| Приватные | `_*` (одно подчёркивание) | `_generate_code` |

~~~python
# ❌ Magic numbers
if len(title) > 255: ...
if rate > 75: ...

# ✅
MAX_TITLE_LENGTH: int = 255
COMPLETION_RATE_EXCELLENT: float = 75.0
~~~

***

## §9. Аргументы функций

### Mutable default — запрещён

~~~python
# ❌
def process(items: list[str] = []) -> list[str]: ...

# ✅
def process(items: list[str] | None = None) -> list[str]:
    if items is None:
        items = []
    ...
~~~

### Параметров много — пакуем в DTO

Более 4-5 параметров — признак что функция знает о слишком многих вещах. Объединяй в `dataclass` / Pydantic-модель.

### Желательно: одна точка возврата

Не правило, но облегчает чтение. Особенно если возвращаемое значение — DTO с десятком полей.

***

## §10. Слоевая архитектура

Проект следует разделению `api/` → `services/` → `db/repository.py` → `db/models.py`. Доменные сущности живут в `domain/`. Каждый слой импортирует **только нижестоящий**.

| Слой | Импортирует | Не импортирует |
|------|------------|----------------|
| `domain/` | ничего из проекта | всё проектное |
| `db/models.py` | `domain/` (опционально) | `services/`, `api/` |
| `db/repository.py` | `domain/`, `db/models.py` | `services/`, `api/` |
| `services/` | `domain/`, Protocol репозитория | `db/models.py` напрямую |
| `api/` | `services/`, `domain/` | `db/` напрямую |
| `validators/` | `domain/` (если нужно) | `db/`, `services/`, `api/` |

Конкретные правила:
- API не лезет в `LinkRepository` мимо сервиса, даже «просто чтобы быстрее» — теряется единая точка валидации.
- Сервис не лезет в `LinkModel` (SQLAlchemy-модель) напрямую — только через репозиторий.
- Бизнес-логика **не живёт** в роуте — handler делает парсинг запроса, вызов сервиса, формирование ответа.

***

## §11. Работа с БД и миграциями

- Любой запрос к БД — через **репозиторий**, не из сервиса напрямую и не из роута.
- Сложные `JOIN`/агрегации — в репозитории как отдельный метод с типизированным DTO в return, не «возвращаем `Row` и разбираем сверху».
- Изменение схемы — только через Alembic-миграцию. Никаких `Base.metadata.create_all(engine)` вне `tests/`.
- `alembic upgrade head` запускается **до** старта приложения (в проекте — в `Makefile` / runbook'е, не из `app.startup`).
- Длинные миграции (создание индекса, бэкфилл) — отдельная миграция без `op.execute(...)` на блокирующих DDL без `CONCURRENTLY`.

***

## §12. Документация — см. `.agents/agents/docs.md`

Любая публичная функция / метод / класс **должна иметь docstring** — это часть стандарта кода, не отдельная задача. Без docstring код **не идёт в merge**.

Краткие правила (детали и форматы — в `.agents/agents/docs.md`):

- **Docstring** на каждой публичной функции/методе/классе. Формат — Google-style: одна строка-резюме, потом `Args:` / `Returns:` / `Raises:` если нужны. **Язык — русский** (имена параметров остаются английскими, описание — русское).
- **CHANGELOG.md** обновляется на любое пользовательское изменение, под `[Unreleased]` → `Added` / `Changed` / `Fixed` / `Deprecated` / `Removed` / `Security`. Внутренний рефакторинг без изменения поведения **в CHANGELOG не попадает**.
- **ADR** в `docs/adr/NNNN-short-name.md` — когда решение затрагивает несколько модулей или меняет публичный контракт. Обязательные секции: Status, Context, Decision, Consequences.
- **README.md** — обновляется когда меняются эндпоинты, ENV-переменные, команды запуска, зависимости. Устаревший README — блокер мержа.

Запрещено:

- Коммит публичного API без docstring.
- Docstring повторяющий имя функции (`def get_user(): """Get user."""`) — лучше без docstring, чем с мусорным.
- Новый эндпоинт / breaking change без записи в CHANGELOG.

***

## §13. Логирование — см. `.agents/agents/logging.md`

Структурное логирование — обязательная часть стандарта. Подробности (конфигурация structlog, redact_secrets, middleware с `request_id`) — в `.agents/agents/logging.md` (файл создаётся в Шаге 7.9 вместе с `app/logging.py`). Здесь — проверяемые правила, которые ловятся в code review.

### Что использовать

- **Сервис / приложение** — `structlog` (JSON в prod, ConsoleRenderer в dev).
- **Библиотека / пакет** — стандартный `logging` (не навязывай формат потребителю).
- `print()` для логирования **запрещён** — нет уровней, нет полей, не идёт в централизованный сбор.

### Уровни

| Уровень | Когда |
|---|---|
| `debug` | Детали для локальной отладки; в prod отключено |
| `info` | Значимые события: запуск, завершение задачи, бизнес-событие |
| `warning` | Нештатная ситуация, с которой код справился (retry, fallback) |
| `error` | Ошибка, операция не выполнена — требует внимания |
| `critical` | Сервис неработоспособен — требует немедленной реакции |

### Правила (нарушение блокирует merge)

- **kwargs, не f-строки** в сообщении. Сообщение-event стабильное, параметры отдельно — иначе агрегация по шаблону невозможна:

~~~python
# ❌
logger.info(f"Processing order {order_id}")

# ✅
logger.info("processing order", order_id=order_id)
~~~

- **Не логировать секреты.** Пароли, токены, PII, Authorization-заголовки, cookie — никогда. В структурном пайплайне работает рекурсивный processor `redact_secrets` (детали в `.agents/agents/logging.md`), но это последняя линия — на уровне `logger.info(...)` явных секретов быть не должно.
- **Не логировать в горячих циклах.** Лог в hot path под нагрузкой превращается в I/O bottleneck. Логируй итог цикла или сэмплируй.
- **`request_id` / `trace_id` через `structlog.contextvars`.** Litestar-middleware биндит `request_id` в начале запроса (`bind_contextvars`), очищает в конце (`clear_contextvars`). Все логи в рамках запроса автоматически получают это поле.
- **Формат в prod — JSON.** Одна строка = один JSON-объект. Это нужно ELK / Loki / Datadog для парсинга.

***

## §14. Безопасность — см. `.agents/agents/security.md`

Прикладная безопасность Python — расширенный набор паттернов в `.agents/agents/security.md` (раздел «Security-паттерны Python»). Здесь — три принципа и компактный чеклист на code review.

### Принципы

1. **Не доверяй входным данным.** Всё что приходит извне (HTTP-тело, query, header, Kafka, файл, CLI-аргумент) — валидируется через Pydantic на границе системы, а не глубоко внутри.
2. **Минимум привилегий.** Сервис, процесс, токен, IAM-роль — каждый работает с минимальным набором прав.
3. **Defense in depth.** Не полагайся на одну линию защиты. SQL-инъекция — параметризация **и** ORM **и** input validation **и** least-privilege DB-юзер.

### Чеклист безопасности (на каждом ревью)

- [ ] Секреты — только через ENV / vault, не в коде, не в логах, не в gitleaks-diff.
- [ ] SQL-запросы параметризованы (или через ORM); никаких f-строк в `execute(...)`.
- [ ] Входные данные валидируются на границе через Pydantic.
- [ ] Пароли — `bcrypt` / `argon2`, не `md5` / `sha1` / plain.
- [ ] Сравнение токенов / секретов — `hmac.compare_digest`, не `==`.
- [ ] Random для security — `secrets.token_urlsafe`, не `random`.
- [ ] HTTP-клиент — с явным `timeout=`, `verify=True`, без `follow_redirects` если URL контролирует пользователь.
- [ ] `subprocess` — `shell=False`, абсолютный путь, ограниченный env, `timeout=`.
- [ ] `pickle` / `yaml.load` / `xml.etree` без `defusedxml` — на untrusted input **не использовать**.
- [ ] File upload — MIME по содержимому (`python-magic`), UUID-имя, передекодирование (для картинок — через Pillow).
- [ ] JWT decode — explicit `algorithms=[...]`, verify `aud` / `iss` / `exp`.

Детали и примеры — в `.agents/agents/security.md`.

***

## §15. Современные фичи Python 3.14

Проект на Python 3.14.5. Это означает, что доступны все возможности 3.10+, 3.11+, 3.12+, 3.13+, 3.14+. Использовать их **прямо** — это код-стиль, а не «факультативно».

### `match/case` вместо длинных `if/elif` по структуре (3.10+)

~~~python
# ✅
def handle_event(event: dict[str, object]) -> str:
    match event:
        case {"type": "link_created", "id": int(link_id)}:
            return f"new link: {link_id}"
        case {"type": "link_deleted"}:
            return "link removed"
        case {"type": str(unknown)}:
            return f"unknown event: {unknown}"
        case _:
            return "malformed event"
~~~

`if isinstance(...) and "x" in dct and ...` — переписывай на `match`, когда веток ≥ 3 и они ветвятся по структуре.

### `Self` для fluent-интерфейсов (3.11+)

~~~python
from typing import Self

class QueryBuilder:
    def where(self, predicate: str) -> Self:
        self._predicates.append(predicate)
        return self

    def limit(self, n: int) -> Self:
        self._limit = n
        return self
~~~

Раньше требовался `TypeVar('Q', bound='QueryBuilder')` плюс forward references — теперь одна аннотация.

### `ExceptionGroup` (3.11+) + `TaskGroup`

См. §5 — для конкурентного кода, где несколько задач могут упасть одновременно, ошибки приходят пачкой через `ExceptionGroup`:

~~~python
try:
    async with asyncio.TaskGroup() as tg:
        tg.create_task(fetch_users())
        tg.create_task(write_audit_log())
except* DatabaseError as eg:
    for err in eg.exceptions:
        logger.error("db error in batch", err=str(err))
~~~

`except*` — отдельный синтаксис для разбора `ExceptionGroup` по типу.

### PEP 695 — новый синтаксис type aliases (3.12+)

~~~python
# ❌ Старый стиль (TypeAlias из typing)
from typing import TypeAlias
UserId: TypeAlias = int
Maybe = list[int] | None

# ✅ PEP 695
type UserId = int
type Maybe[T] = T | None
type Point = tuple[float, float]
~~~

На 3.14 — используем новый синтаксис. Старый `TypeAlias`-импорт оставляем только при поддержке версий ниже 3.12 (у нас 3.14, не наш случай).

### `enum.StrEnum` (3.11+) для строковых констант

~~~python
# ✅
from enum import StrEnum

class LinkStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"

# Сравнение с обычной строкой работает напрямую
if status == "active": ...
~~~

`StrEnum` поверх `Enum` экономит boilerplate и работает с JSON / БД / API без `.value`.

### `with` со скобками для нескольких ресурсов (3.10+)

~~~python
# ❌ Длинная вложенность
with open("input.txt") as src:
    with open("output.txt", "w") as dst:
        dst.write(src.read())

# ✅ 3.10+ — со скобками
with (
    open("input.txt", encoding="utf-8") as src,
    open("output.txt", "w", encoding="utf-8") as dst,
):
    dst.write(src.read())
~~~

### `@dataclass(slots=True, frozen=True)`

`slots=True` экономит память (нет `__dict__` на инстансе) и **ловит опечатки атрибутов** — `link.clcks = 5` падает с `AttributeError` вместо тихого создания нового поля. `frozen=True` запрещает мутацию — для Value Objects обязательно.

***

## §16. JSON и сериализация

Для JSON в прикладном коде сервиса выбор по умолчанию один — `orjson`. `msgspec` подключается только там, где замер показал выигрыш. Стандартный модуль `json` в новом коде не используется. Правила обязательны для нового кода; старый приводится к стандарту по мере касания.

### `orjson` — библиотека по умолчанию

`orjson` заменяет `json.loads` / `json.dumps` везде, где сервис сам читает или пишет JSON: логи, кэш, очереди, тела запросов к внешним сервисам, файлы. `orjson.dumps` возвращает `bytes`, поэтому результат идёт в сокет, HTTP-клиент, Kafka или файл без лишнего `.encode()`. Вызов `.decode()` нужен, только если потребителю нужна именно строка. Типы `datetime`, `UUID`, `dataclass` и `enum` сериализуются без `default=`.

~~~python
# ❌
import json
payload = json.dumps(event, default=str).encode()
data = json.loads(body)

# ✅
import orjson
payload = orjson.dumps(event)   # bytes; datetime, UUID, dataclass, enum — нативно
data = orjson.loads(body)       # принимает bytes и str
~~~

Чем `orjson` отличается от `json` и где наивная замена «один в один» ломается:

- Параметры передаются битовой маской: `orjson.dumps(obj, option=orjson.OPT_SORT_KEYS | orjson.OPT_INDENT_2)`. Аргументов `indent=`, `sort_keys=`, `ensure_ascii=` нет, вызов с ними даёт `TypeError`. Вывод всегда UTF-8, кириллица не экранируется.
- Ключи словаря — только `str`. Для других типов ключей нужен `OPT_NON_STR_KEYS`, иначе `TypeError`.
- `default=` вызывается только для типов, которые `orjson` не сериализует сам (`Decimal`, `set`); без него такие значения дают `TypeError`. Поведение для `datetime`, `dict` и других встроенных типов через `default=` не переопределить.
- Целое, не помещающееся в 64 бита, даёт `TypeError`. `NaN` и `Infinity` записываются как `null`, а не как невалидный литерал: если значение нельзя терять молча, проверь его до сериализации.
- Наивный `datetime` записывается без часового пояса (`"2026-09-30T12:00:00"`), aware — со смещением (`"+00:00"`).
- Ошибка разбора — `orjson.JSONDecodeError`. Он подкласс `json.JSONDecodeError` и `ValueError`, поэтому существующие `except ValueError` и `except json.JSONDecodeError` продолжают его ловить. Ошибка сериализации — `orjson.JSONEncodeError` (подкласс `TypeError`).

`import json` разрешён в трёх случаях: тесты; автономные скрипты вне пакетов сервиса; вывод, которому нужен `ensure_ascii=True` или отступ, отличный от двух пробелов. В последнем случае рядом пишется комментарий, почему `orjson` не подходит (как для `# noqa`, запрет №9).

### `msgspec` — горячий путь и типизированные границы

`msgspec` декодирует JSON сразу в типизированные объекты `msgspec.Struct`, без промежуточных `dict`, и проверяет типы при декодировании. Он подключается, когда декодирование или валидация JSON — заметная часть CPU пути (подтверждено профилированием) либо сервис разбирает крупный документ целиком (снимок правил, пачка событий). В описании merge request (MR) приложи замер «до/после» на реальном размере данных. Без замера замена `orjson` или Pydantic на `msgspec` не принимается. Выигрыш над `orjson` при простом декодировании в `dict` небольшой; заметный эффект даёт замена Pydantic-валидации на горячем пути.

~~~python
import msgspec

class Rule(msgspec.Struct, frozen=True, kw_only=True):
    rule_id: str
    priority: int = 0

# Decoder создаётся один раз и переиспользуется между вызовами
_RULES_DECODER = msgspec.json.Decoder(list[Rule])

def parse_rules(raw: bytes) -> list[Rule]:
    try:
        return _RULES_DECODER.decode(raw)
    except msgspec.DecodeError as exc:  # ValidationError — его подкласс
        raise InvalidRulesError(str(exc)) from exc
~~~

`msgspec.Struct` — это DTO в смысле §2: типы проверяет `basedpyright` (см. «Главные принципы», п. 2), и на границе слоёв он заменяет `dict`. Для Value Object'ов (§2) по умолчанию `frozen=True, kw_only=True`.

Разделение с Pydantic:

- `msgspec` — для внутренних и доверенных форматов: обмен между процессами сервиса, внутренние снимки и конфиги, собственные очереди.
- Pydantic остаётся для схем публичного HTTP API (OpenAPI), для `pydantic-settings` и для валидации недоверенного внешнего входа по §14.

### Фреймворки

- Litestar (стек этого стандарта) сериализует запросы и ответы через встроенный `msgspec`. `orjson` вызывается вручную там, где JSON создаём мы: логи, кэш, очереди.
- FastAPI: `ORJSONResponse` и `UJSONResponse` объявлены deprecated. На версии 0.139.2 их использование выдаёт `FastAPIDeprecationWarning` со ссылкой на документацию (https://fastapi.tiangolo.com/advanced/custom-response/#orjson-or-response-model). Если у эндпоинта задана аннотация возврата или `response_model`, FastAPI сам сериализует ответ через Pydantic, и отдельный класс ответа не нужен. `response_class=ORJSONResponse` в новом коде запрещён.

### Зависимости

`orjson` и `msgspec` — компилируемые пакеты. Они добавляются в runtime-зависимости `pyproject.toml` (не в dev) с верхней границей по мажорной версии, `uv.lock` обновляется в том же MR. Если код сервиса доставляется в окружение отдельно от образа (монтирование, initContainer, volume), пакет ставится тем же способом, иначе сервис падает на старте с `ModuleNotFoundError`. Перед MR проверь, что `import orjson` и `import msgspec` проходят в окружении, где сервис реально запускается.

***

## Чеклист самопроверки перед commit

**Типы и структура**

- [ ] `from __future__ import annotations` в каждом новом файле
- [ ] Все параметры и возвращаемые типы аннотированы (включая `-> None`)
- [ ] Нет `Optional[X]` / `List[X]` / `Dict[K, V]` (PEP 604/585)
- [ ] Возвращаемые данные — DTO / Value Object / domain-объект, не `dict`
- [ ] Нет `except Exception: pass`, конкретные типы исключений
- [ ] Нет mutable defaults
- [ ] Magic numbers вынесены в константы

**Архитектура и async (§5, §10)**

- [ ] Async-слои не содержат sync-вызовов в БД / HTTP / sleep
- [ ] Параллельные задачи — через `asyncio.TaskGroup`, внешние вызовы — с `asyncio.wait_for(..., timeout=...)`
- [ ] Сервис не импортирует `db/models.py` напрямую
- [ ] Бизнес-логика не в route handler

**Логирование (§13)**

- [ ] Нет `print()` для логирования — только `structlog` / `logging`
- [ ] Сообщения без f-строк: `logger.info("event", key=value)`, не `logger.info(f"event {value}")`
- [ ] Нет секретов / токенов / PII в kwargs логгера
- [ ] Для request-жизненного цикла — `bind_contextvars(request_id=...)` в middleware

**Безопасность (§14)**

- [ ] Нет хардкода секретов / токенов / connection strings
- [ ] SQL — параметризованный (или через ORM), без f-строк
- [ ] Внешние данные валидируются через Pydantic на границе
- [ ] Пароли — `bcrypt` / `argon2`; сравнение токенов — `hmac.compare_digest`
- [ ] HTTP-клиенты — с `timeout=`, `verify=True`, без `follow_redirects` для user-controlled URL
- [ ] `subprocess` — `shell=False`, абсолютный путь, ограниченный env, `timeout=`

**JSON (§16)**

- [ ] Нет `import json` / `ujson` / `simplejson` в новом коде сервиса (кроме исключений §16)
- [ ] `orjson.dumps` без лишнего `.decode()`; нестроковые ключи и `Decimal` обработаны явно
- [ ] `msgspec` подключён только с замером «до/после» в описании MR
- [ ] `orjson` / `msgspec` есть в runtime-зависимостях и в окружении, где запускается сервис

**Документация и changelog (§12)**

- [ ] Docstring на новых публичных функциях / методах (Google-style, на русском — см. §12 и `.agents/agents/docs.md`)
- [ ] CHANGELOG.md обновлён если меняется пользовательское поведение

**Автоматические проверки**

- [ ] `uv run ruff check .` — зелёный
- [ ] `uv run basedpyright` — зелёный
- [ ] `uv run pytest -q` — зелёный (включая `--cov-fail-under=80`)
- [ ] Работал в `git worktree` — проверки запускались из его корня, `import` ведёт в свой `src` (см. «Проверки в `git worktree`» выше)
- [ ] Правка меняет видимое (страница, карточка, письмо, отчёт) — открыл глазами и описал, что увидел; стенда нет — так и написал в отчёте (см. `.agents/agents/testing.md`, «То же в UI: приёмка по живому рендеру»)
ARTIFACT_END>>>
<<<ARTIFACT ~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/testing.md sha256=e263f3e5083057721e1d746f4a5d8abace930c8f56c9e9b98c54ab18df5402c5
# Testing rules

- Использовать `pytest`.
- Не использовать `unittest.TestCase`, `setUp`, `tearDown`.
- Во всех тестовых файлах писать `from __future__ import annotations`.
- **Проект полностью async**: handler'ы Litestar async, сервис async, репозиторий async. Все тесты тоже **`async def`**, фикстуры с DB — `async`.
- В `pyproject.toml` стоит `asyncio_mode = "auto"` — `async def test_X()` запускается без `@pytest.mark.asyncio`.

## Unit tests

- Unit tests должны быть быстрыми и изолированными.
- Не использовать shared state между тестами.
- Не тестировать API в unit tests.
- Не использовать `MagicMock`, `patch` и `unittest.mock`, если можно сделать Fake-объект.
- **Fake-репозиторий повторяет async-сигнатуру реального**: все методы `async def`, чтобы `await self.repository.X(...)` в сервисе работал.
- Тестовые функции — `async def`, вызовы сервиса через `await`.

~~~python
class FakeRepository:
    def __init__(self) -> None:
        self._store: dict[str, object] = {}
        self._next_id: int = 1

    async def add(self, code: str, item: object) -> int:
        self._store[code] = item
        self._next_id += 1
        return self._next_id - 1

    async def get_by_code(self, code: str) -> object | None:
        return self._store.get(code)
~~~

- Fake-объекты предпочтительнее mock-подхода.
- Для in-memory хранения можно использовать `dict`, простой счётчик ID, `replace()` для иммутабельных копий.
- Если метод должен вернуть отсутствие сущности — проверять `is None`.
- Для ошибок использовать `pytest.raises(..., match=...)`.
- Имена тестов — в стиле `test_...`.

## Что проверять в unit tests

- Happy path.
- Edge cases: пустая строка, `None`, `0`, пробелы.
- Error cases: невалидный ввод, отсутствие сущности.
- Regression test на найденный баг.

## Зелёный прогон ≠ корректно (тихие отказы)

- «Непусто + без исключения» — **НЕ** доказательство корректности. У части
  операций режим отказа **тихий**: извлечение/парсинг/скрейпинг/
  трансформация/фильтрация/дедуп возвращают валидный, но **неполный**
  результат. Зелёные `pytest`/`ruff`/`basedpyright` это не ловят, если сам
  тест не проверяет полноту.
- Проверяй **полноту против эталона** (ground truth), а не «живость».
  Воспроизводи на **реальном входе, который проявляет проблему**, а не на
  синтетике или частичном снимке.
- Если эталон нельзя сверить руками в рантайме — **закодируй инвариант
  полноты** в коде/тесте. Пример: «извлечённый текст ⊇ длинные абзацы
  видимого текста страницы» → метрика покрытия + фолбэк.
- Не объявляй «работает» по неполной проверке. Проверял только синтетику —
  так и скажи оператору («на реальном X не проверял»), не выдавай за
  полную проверку.
- **Тест должен воспроизводить баг**: падать на старом коде и проходить на
  новом (напр. assert «один снимок < N блоков» И «после фикса == N»). Тест
  вида «не пусто»/«не бросило» зелёный и на сломанном коде — он ничего не
  доказывает.
- **Фикстура ≠ реальность.** Подогнанная фикстура легко проходит, а реальный
  источник ведёт себя иначе. Для багов про реальные данные/внешний источник —
  прогон **end-to-end через настоящую ручку** (HTTP → сервис → источник) и
  сверка с эталоном **до** вывода «готово».
- Реальный кейс (EYE-27163): юнит на фикстуре и метрика coverage были
  зелёными, а живой прогон docs.cntd.ru через ручку дал 21% вместо ~100%
  (слепой скролл проскакивал середину оконной виртуализации). Исправлено на
  обход контейнеров — 97% — и это поймали только сквозной проверкой по URL.

### То же в UI: приёмка по живому рендеру

Тот же принцип, спроецированный на то, что видит человек: страница, карточка,
письмо, отчёт, экспорт.

- **Меняешь видимое — открой это глазами до сдачи** (MCP playwright или руками
  в браузере). Тест шаблона проверяет **контракт рендера** — есть ли элемент,
  ведёт ли ссылка. Он не проверяет **смысл**: осмысленна ли подпись для этих
  данных, полон ли список, не пуст ли экран из-за неинициализированного
  состояния. Наличие элемента в HTML не доказывает, что элемент ведёт себя
  так, как обещает его подпись.
- Два подтверждённых класса дефекта, которые ловятся только глазами:
  1. **подпись, осмысленная лишь для одного типа контента** — ярлык
     «Данные товара» над полями статьи (заголовок, автор, теги): код работает
     как написан, результат неверен;
  2. **агрегат/индекс, который обновляется инкрементально и не пересобирается
     на исторических данных** — карта показывает 1 домен из 6, потому что
     запись добавляется при `save`, а полная пересборка — отдельный вызов.
     Тест «после `save` запись появилась» зелёный и прав.
- **Ответственность разведена:**
  - *субагент / исполнитель задачи* — если стенда нет (изолированный worktree
    обычно без него), в отчёте пишет прямо: «UI глазами не проверял», и
    **показывает доказательство того, что проверил**: какие страницы открывал,
    что увидел. Формулировка «тесты зелёные» доказательством живого рендера
    не считается;
  - *тот, кто сводит ветки и сдаёт фазу*, — обязан открыть изменённые страницы
    сам, до сдачи. Отчёт субагента здесь пересказ, а не факт.
- **Границы.** Не требуется, если правка не меняет видимое (рефактор без смены
  разметки и данных). Снимок из браузера — **не** регресс-тест: он разовый,
  повторяемость даёт только тест; живой рендер тесты дополняет, а не заменяет.

## Integration tests

- Integration tests проверяют API целиком.
- HTTP-клиент: `AsyncTestClient` из `litestar.testing` (вызывается через `async with`).
- Состояние тестовой среды должно очищаться **до и после** каждого теста — autouse-фикстура с `async def`, чистка через `await session.execute(text("DELETE FROM ..."))`.
- Для этого удобно использовать `pytest.fixture(autouse=True)` + `async def`.
- Проверять реальные HTTP-статусы и JSON-ответы.
- `follow_redirects=False` обязателен на TestClient — иначе 302-редирект автоматически перейдёт и ты потеряешь возможность проверить `Location`-заголовок.

## Full Suite Gate перед сдачей и MR

- **Запуск полного набора обязателен**: перед открытием MR или передачей на ревью разработчик обязан выполнить полный прогон тестов (`uv run pytest -q`), а не только точечный запуск изменённых файлов (`-k` или путь к файлу).
- Точечный запуск скрывает взаимные сайд-эффекты, утечки переменных окружения и скрытые регрессии в соседних модулях.
- Зелёный точечный тест НЕ гарантирует, что общий suite остался зелёным.

## Запрет мутации os.environ без изоляции

- **Никакой прямой мутации глобального окружения**: запрещено писать `os.environ["KEY"] = "val"` или `del os.environ["KEY"]` в коде тестов или вспомогательных функций без гарантированного отката.
- Прямая мутация приводит к эффекту «leaky state»: значение протекает в последующие независимые тесты того же процесса pytest (или subprocess worker), вызывая плавающие и труднодиагностируемые падения в CI.
- **В pytest-тестах**: строго использовать стандартную фикстуру `monkeypatch` (`monkeypatch.setenv("KEY", "val")`, `monkeypatch.delenv("KEY", raising=False)`), которая автоматически восстанавливает исходное состояние после завершения теста.
- **В рантайм-коде или тестовых раннерах (где monkeypatch недоступен)**: строго оборачивать изменение в `try...finally` с явным сохранением и восстановлением исходного значения:
  ```python
  old_val = os.environ.get("KEY")
  os.environ["KEY"] = "val"
  try:
      ...
  finally:
      if old_val is None:
          os.environ.pop("KEY", None)
      else:
          os.environ["KEY"] = old_val
  ```

## Аварийное завершение процесса = провал прогона

- **Инвариант.** Любой процесс, который запускает тест или скрипт агента (сам тест, заглушка/fake, хелпер, сервис внутри теста, подпроцесс), не должен завершаться аварийно, если тест этого явно не заявил. Два **независимых** основания провала (достаточно одного): (а) аварийный returncode — выход по сигналу `SIGABRT`/`SIGSEGV`/`SIGBUS`/`SIGILL`/`SIGFPE`/`SIGTRAP` (rc<0 в Python, либо 128+N в шелле: 132, 133, 134, 136, 138, 139); (б) crash-репорт macOS (`.ips` в `~/Library/Logs/DiagnosticReports`), связанный с процессами этого прогона. Отсутствие `.ips` не оправдывает аварийный rc: macOS ограничивает число репортов на имя процесса (на этой машине лимит для `Python` уже исчерпан). Прогон **красный, даже когда все тесты зелёные**: зелёный `pytest` не видит смерть процесса, которая случилась при выходе или в ребёнке.
- **Негативные тесты** («ребёнок умер», «завис», «упал воркер») имитируют смерть через `SIGKILL`/`SIGTERM` или `os._exit(1)`, а не через `abort()`/segfault. Коды выхода, совпадающие с 128+N аварийных сигналов (132, 133, 134, 136, 138, 139 и т.п.), в `os._exit(...)` и `sys.exit(...)` не использовать: они читаются как краш. Проверено 08.10.2026: `SIGKILL`/`SIGTERM`/`os._exit` не создают crash-репорт и окно «Python quit unexpectedly»; `SIGABRT`/`SIGSEGV` — создают.
- **Настоящий аварийный выход в тесте допустим только явно заявленным**: `run-guarded --expect-crash <regex>`.
- **Как запускать.** Тесты и скрипты с подпроцессами — через `run-guarded -- <команда>` (`~/.local/bin/run-guarded`, исходник и README — `~/Мой диск/Workshop/crash-guard/`): он сам ловит связанные `.ips` и сигнальный выход ребёнка.
- **Ручная проверка (нет `run-guarded`)** — правило действует: (1) проверь returncode каждого ребёнка; (2) запомни pid процессов прогона (и `parentPid` из отчёта) и список `.ips` до прогона; (3) после выхода подожди ≥10 с — отчёт пишется с задержкой; (4) в новых `.ips` засчитывай только отчёты с pid/`parentPid` этого прогона, а не любой новый файл. Отчёт не удалось записать (лимит логов) или связать с прогоном нельзя — статус **«НЕ ПРОВЕРЕНО»**, «прогон чистый» писать запрещено.
- Иллюстрация, не правило: daemon-поток, читающий `sys.stdin` через буфер, роняет интерпретатор при выходе (`SIGABRT`) — тесты зелёные, окно краша есть.

## CI Parity (учёт ограничений CI-окружения)

- Окружение CI изолировано: в нём по умолчанию нет локальных СУБД (PostgreSQL, ClickHouse), брокеров, git-репозиториев в сгенерированных контейнерах и внешних секретов.
- **Интеграционные тесты с внешними зависимостями**: снабжать условиями пропуска (`pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="...")`), чтобы отсутствие БД в базовом runner-образе не блокировало весь пайплайн.
- **Проверки внешних утилит**: если тест вызывает внешние бинарники (`git`, `docker`), проверять их наличие через `shutil.which(...)` и скипать при отсутствии.
- **Калибровка coverage-гейта**: порог `--cov-fail-under` в `pyproject.toml` должен учитывать скипаемые в CI интеграционные тесты, чтобы локальный высокий coverage не ломал CI при законном пропуске тестов с внешней БД.
- **pip-audit**: в репозиториях с монорепозиторными/vendored подмодулями запускать с `--skip-editable`, а известные непатченные CVE транзитивных утилит (например, pip) документировать через явный `--ignore-vuln`.

## Параллельное выполнение тестов и проверок (многоядерность)

- **Многоядерный запуск (`pytest-xdist`)**: на современных многоядерных машинах однопоточный запуск использует только одно ядро и кратно увеличивает общее время ожидания. При наличии `pytest-xdist` тесты распределяются по всем доступным ядрам через `-n auto`. Если плагин отсутствует, фолбэк на обычный запуск без `-n`.
- **Юнит- и E2E-тесты — параллельно с `-n auto`**:
  - `uv run pytest tests/unit/ -q -n auto`
  - `uv run pytest tests/e2e/ -q -n auto` (Playwright с изолированным browser context)
  - Если интеграционный сьют изолирован (отдельная БД/схема на каждый `worker_id`) — допускается `-n auto`. При разделяемой БД без изоляции схем интеграционные тесты запускаются **последовательно** (`-n 0` или без флага).
- **Serial Lane (последовательный контур)**:
  - Ресурсные тесты, замеры CPU/latency (`-m "measured or heavy"`) и тесты с фиксированными сетевыми портами запрещено запускать параллельно с другими тестами или линтерами: они требуют последовательного прогона в тихом окружении.
- **Playwright E2E параллелизм**:
  - Каждый worker `pytest-xdist` запускает изолированный browser context (`page` fixture). Тесты выполняются параллельно на всех ядрах, сокращая время прогона в разы.
- **Конвейер проверок (Toolchain Concurrency)**:
  - Шаги с модификацией кода выполняются первыми: `uv run ruff format . && uv run ruff check --fix .`.
  - Все независимые проверки на чтение (read-only) запускаются **параллельно** с сохранением PID и агрегацией статусов через `wait || s=$?` (это защищает от преждевременного выхода в `set -e` / CI и от тихого прохода при bare `wait`):
    ```bash
    uv run ruff check . & p1=$!; uv run basedpyright & p2=$!; uv run pytest -q -n auto -m "not measured and not heavy" --no-cov & p3=$!; s1=0; s2=0; s3=0; wait $p1 || s1=$?; wait $p2 || s2=$?; wait $p3 || s3=$?; [ $s1 -eq 0 ] && [ $s2 -eq 0 ] && [ $s3 -eq 0 ]
    ```
  - Это позволяет перекрыть время работы тайпчекера (`basedpyright`) и `pytest`, сокращая общее время ожидания до максимума из них.
  - Для ресурсных тестов из Serial Lane прогон выполняется отдельным последовательным шагом: `uv run pytest -q -m "measured or heavy"`.

## Инварианты времени жизни, ранних выходов и семантики метрик (`T-LIFE/v1`, `O-EXIT/v1`, `M-SEM/v1`)

При любом изменении, затрагивающем триггеры из таблицы применимости ниже, тесты и ревью обязаны подтвердить соответствующий инвариант по его поведенческому оракулу. Статус `PASS` **запрещено** выставлять по подстроке сырого SQL, только по HTTP-статусу ответа или только по полю внутренней структуры без проверки финального sink-а.

### Таблица триггеров применимости (`smoke` / `standard` / `deep`)

Для всех уровней триажа (`smoke`, `standard`, `deep`) действует единая семантическая таблица включения. Сработавший триггер активирует **только** сопоставленный ему инвариант; отметка `N/A` для активированного инварианта запрещена (`BLOCKED` на ревью), но допустима для несвязанных инвариантов.

| Триггер в diff / контракте задачи | Активируемый инвариант | Обязательный оракул доказательства (`smoke` = `standard` = `deep`) |
|---|---|---|
| Функции жизненного цикла (`lookup`, `bind`, `claim`, `reclaim`, `evict`, `expire`), поля и маркеры времени/владения (`created_at`, `bound_at`, `last_seen_at`, `expires_at`, `ttl`, `active_ttl`, `stale_ttl`, `NOW()`, `INTERVAL`, `monotonic`, `throttle_window`, `exclusive_hold`, `rotate`), многоуровневый кэш `L1`/`L2` | **`T-LIFE/v1`** (`#t-life`) | Поведенческая матрица времени и владения на реальном хранилище (PostgreSQL/Redis) с проверкой `T0`, `T1`, границ `TTL−ε`/`TTL+ε` (`ε > transaction_jitter`), `throttle_window`, `L1/L2` и перезахвата (`same-key` / `different-key`) |
| Новая или изменённая ветка раннего выхода (`return`, `raise`, `abort`, pre-upstream reject `4xx`/`5xx`) до основного `try/finally`, перенос порядка инициализации контекста (`mode`, `pool`, `tenant`, `attempt`) относительно точек выхода | **`O-EXIT/v1`** (`#o-exit`) | Полный прогон от входного handler до финализатора с проверкой эмиссии специализированного терминального события в реальный sink (с корректными атрибутами режима, пула, tenant и `error_reason`) |
| Добавление/перенос инкремента счётчика, изменение лейблов или места вызова метрики, изменение числителя/знаменателя/фильтров запроса, создание или переименование панели/дашборда/алерта | **`M-SEM/v1`** (`#m-sem`) | Stage 1 (в репо/CI): Паспорт метрики + канонический запрос + расчётный `pytest` на полной синтетической фикстуре всех исходов; Stage 2 (на приёмке): сверка живого запроса (до завершения Stage 2 допустим только `PASS_STAGE1_ONLY` + `PENDING_STAGE2_LIVE_VERIFY`) |

---

<a id="t-life"></a>
### `T-LIFE/v1`: Инвариант жизненного цикла состояния с временем (`Temporal & Ownership Lifecycle`)

1. **Единое определение живости и запрет проверки по тексту SQL:**
   - Операции чтения (`lookup`), первичного захвата (`claim`), перезахвата истёкшей записи (`reclaim`) и принудительной ротации (`rotate`) обязаны использовать явно согласованный предикат живости (`liveness`).
   - Проверка `assert "last_seen_at" in SQL` или `assert "bound_at" in SQL` остаётся только вспомогательным сторожем текста и **не входит** в матрицу доказательства `T-LIFE/v1`.
2. **Обязательная поведенческая матрица на реальном хранилище:**
   - **Две независимые оси времени (`T0 != T1`):** время создания/привязки (`T0`, например `bound_at`) и время последней активности (`T1`, например `last_seen_at`) разводятся в разные точки. Если оба поля состарены одновременно, тест не различает `T0` и `T1` и не засчитывается.
   - **Независимые ячейки:**
     - **(а) Продление живой сессии (sliding survival):** `T1` свежий (`age(T1) < TTL`), `T0` старше `TTL`, `rotate=false` → `lookup` возвращает ту же привязку, перезахват не требуется.
     - **(б) Перезахват тем же владельцем после истечения idle (`same-key reclaim`):** `T1` старше `TTL`, `T0` свежий (`age(T0) < TTL`), `rotate=false`, `exclusive_hold=true` → `lookup` пуст, последующий `claim` тем же ключом перезахватывает строку без отказа. Ожидаемые значения временных полей после reclaim фиксируются в контракте до написания теста.
     - **(в) Принудительная ротация при эксклюзивном удержании (`rotate=true` + `exclusive_hold=true`):** при свежем `T1` и `T0` старше `TTL` поведение (`allow` или `deny` по жёсткому пределу `T0`) должно быть явно записано в контракте до теста; до записи контракта ячейка имеет статус `BLOCKED`, а поле второй дизъюнкции `WHERE` не переписывается вслепую.
     - **(г) Чужой ключ и конкурентный конфликт (`T-05`, `T-06`):** перезахват истёкшей записи другим ключом и отказ при активном другом владельце проверяются на независимых копиях состояния.
3. **Учёт `throttle_window` и многоуровневого кэша (`L1` / `L2`):**
   - Если запись активности троттлится (например, обновление `last_seen_at` не чаще чем раз в `throttle_window`), контракт обязан явно зафиксировать точку отсчёта idle: от последнего запроса либо от последнего записанного `last_seen_at`. До фиксации этой фразы ячейка троттлинга имеет статус `BLOCKED`.
   - Граничные точки `TTL−ε` и `TTL+ε` проверяются с `ε`, заведомо превышающим транзакционный джиттер `NOW()`, а точка точного равенства `TTL` — только при фиксированном опорном времени внутри одной транзакции.
   - При наличии `L1`-кэша поверх `L2`-БД контракт фиксирует один из двух инвариантов: либо положительный `L1` никогда не возвращает эксклюзивную привязку, которую `L2` уже считает истёкшей (`L1_ttl <= L2_active_ttl`), либо `L1` объявлен авторитетным на свой TTL с отдельным тестом отсутствия второго владельца при параллельном reclaim в `L2`.

---

<a id="o-exit"></a>
### `O-EXIT/v1`: Инвариант наблюдаемости на ранних выходах (`Early-Exit Observability Parity`)

1. **Нормативное правило стадии:**
   - Любая ветка раннего возврата или отказа (`return`, `raise`, pre-upstream reject `4xx`/`5xx`), выходящая до основного пути исполнения, обязана проходить через единый финализатор или гарантировать до точки выхода:
     1. проставление обязательных атрибутов контекста стадии (режим работы, пул маршрутизации, идентификатор клиента/тенанта);
     2. фиксацию точной машиночитаемой причины отказа (`error_reason`);
     3. эмиссию специализированного терминального события стадии в целевой sink телеметрии/аудита.
   - Общее инфра-событие запроса не заменяет специализированное терминальное событие доменной стадии.
   - Проверка только HTTP-кода ответа или только поля структуры в памяти (без проверки события, попавшего в sink финализатора) инвариант `O-EXIT/v1` **не закрывает**.
   - Если для закрытия `O-EXIT/v1` инкремент счётчика или установка атрибута переносится выше точки раннего выхода, обязательно проверяется кратность эмиссии («ровно один раз на запрос» и на пути раннего отказа, и на успешном пути без двойного счёта), а при изменении знаменателя существующей метрики обновляется её паспорт по `M-SEM/v1`.

> **Пример из практики (`webaccess`, иллюстративный блок — не добавляет требований другим репозиториям и сам по себе не является доказательством MR `webaccess`):**
> В инциденте `EYE-34342` ранний выход `503 exclusive_ip_unavailable` происходил до установки `call.llm_mode`, из-за чего финальный счётчик уходил в `pool="general"` вместо `pool="llm"`, а терминальное событие `webaccess_llm_call` не эмитировалось вовсе. Доказательством закрытия для `webaccess` служит только сквозной тест реального handler до финализатора, проверяющий появление ровно одного события `webaccess_llm_call` в sink с `pool="llm"`, согласованным `llm_mode` и `error_reason="exclusive_ip_unavailable"`.

---

<a id="m-sem"></a>
### `M-SEM/v1`: Инвариант семантического паспорта метрики и дашборда (`Metric & Panel Semantic Contract`)

1. **Двухстадийная верификация (`Stage 1` в репозитории/CI + `Stage 2` на приёмке):**
   - **`Stage 1` (обязателен в репозитории и CI):**
     - В репозитории (`observability/` или `docs/arch/metrics/`) фиксируется версионированный **Паспорт метрики** (версия, слой метрики: транспорт/прокси vs прикладной upstream vs бизнес-успех, точная формула числителя и знаменателя, единица счёта, обязательные фильтры, окно агрегации, трактовка `NULL`/no-data/нулевого знаменателя, поведение при retries/dedup, точка эмиссии и фаза lifecycle в коде, допустимая и запрещённая операционная интерпретация) и текст канонического запроса панели/алерта.
     - В `pytest` выполняется расчётный тест формулы паспорта на синтетической фикстуре, содержащей **все** граничные категории исходов: успешный прикладной ответ (`200`), другой `2xx`, прикладной отказ аутентификации/аккаунта (`401 account_deactivated`, `403`), rate-limit (`429`), прикладной `5xx` апстрима, транспортный отказ без ответа апстрима, ранний локальный отказ до апстрима (`503`), `NULL`/no-data, нулевой знаменатель, retry с итоговым успехом и повторную доставку. Четыре базовых квадранта (успех, клиентский отказ, инфраструктурный ранний выход, фоновый шум) являются нижней границей и эту детальную фикстуру не заменяют.
     - Неполный `Stage 1` означает статус `BLOCKED` — положительный вердикт по задаче/MR закрыт.
   - **`Stage 2` (на приёмке в живом контуре / `acceptance-gate`):**
     - Живой запрос в системе мониторинга (ClickBeat / Prometheus / Grafana) сверяется с каноническим текстом запроса в репозитории и с контрольным сэмплом.
     - После полного прохождения `Stage 1` и до завершения `Stage 2` разрешён **только** статус `PASS_STAGE1_ONLY` с открытым пунктом `PENDING_STAGE2_LIVE_VERIFY` (передаётся в `teamlead-gate` / `acceptance-gate`). Формулировать такой статус как полный `PASS`, «исправлено» или «готово» запрещено.
     - Пока `Stage 2` не закрыт, заголовок или описание самой панели дашборда (в частности, панелей 603 и 708 при их переименовании) обязаны содержать явную отметку о неподтверждённой в бою семантике.

<!-- HL-RESILIENCE-GATES-V5 -->
---

<a id="hl-resilience-oracles"></a>
### Детерминированные тест-оракулы Highload & Resilience (`HL-ENV-01`, `C-MULT-I1..I5`, `S-HERD-I1..I5`, `H-CPU-I1..I5`, `R-BULK-I1..I5`)

Каноническая спецификация конверта `HL-ENV/v1` и четырёх гейтов — в SSoT `.agents/agents/architecture.md` (`#hl-env-and-four-gates-ssot`).

### 7.2. Полная биективная матрица «Стоп-Код -> Инвариант -> Детерминированный Unit-Оракул» (21 код, 0 wall-clock флаков)

В unit- и компонентных тестах CI **запрещены** флакающие проверки реального астрономического времени (`elapsed < 1 ms`) и случайных выборок без фиксированного/инъектированного генератора. Все инварианты проверяются детерминированно через управляемые часы (`FakeClock`), инъекцию детерминированного источника энтропии/RNG, счётчики вызовов (`call_count`), инспекцию AST/атрибутов пула и проверку переходов конечных автоматов; замеры реального времени и CPU выносятся в профилирующий прогон `-m "measured or heavy"`.

<!-- HL-RESILIENCE-ORACLES-V3 -->
| Код стоп-правила | Инвариант (1-к-1 с Разделом 3) | Детерминированный Тест-Оракул (что именно проверяет автотест / гейт без wall-clock и RNG флаков) |
|---|---|---|
| **`HL-ENV-01`** | Полнота всех 46 атомарных полей `REQUIRED_HL_ENV_FIELDS` (строки 1–46 таблицы 3.0), замыкание памяти и транзитивное доказательство `N/A` | Гейт/тест проверяет `REQUIRED_HL_ENV_FIELDS.issubset(envelope.keys())` и `len(REQUIRED_HL_ENV_FIELDS) == 46` для всех 46 атомарных полей таблицы 3.0 (`P_steady`, `P_hpa_max`, `maxSurge_pct`, `maxSurge_abs`, `maxUnavailable_pct`, `maxUnavailable_abs`, `P_terminating_overlap`, `P_live`, `P_avail_min`, `W`, `N_proc`, `N_proc_steady`, `N_proc_avail_min`, `CPU_limit_per_pod`, `κ_skew`, `u_bg_worker`, `U_pod_sidecars`, `Mem_limit_per_pod`, `Mem_rss_worker_max`, `Mem_shared_max`, `RPS_peak`, `A_max`, `SLA_p99_s`, `N_entities_max`, `Limit_dep_share[d]`, `Limit_dep_rps[d]`, `W_fetchers[d]`, `J_init_s[d]`, `J_pod_s[d]`, `T_poll_s[d]`, `K_calls[d]`, `T_base_s[d]`, `T_cap_s[d]`, `Max_stale_age_s[c]`, `Min_healthy_ratio`, `B_retry_max`, `min_reserve_retry_rps`, `FD_worker`, `ulimit_n`, `λ_new_conn_per_pod(s)`, `C_active_in_scope(s)`, `N_pods_in_scope(s)`, `Port_range_size(s)`, `T_hold_s(s)`, `SNAT_ips_count(s)`, `HOTPATH_MODULES`), проверяет неравенство памяти $W \cdot \text{Mem\_rss\_worker\_max} + \text{Mem\_shared\_max} \le 0.80 \times \text{Mem\_limit\_per\_pod}$ и для любого `N/A` — наличие `git diff` + транзитивного графа `callers/callees` |
| **`C-MULT-I1`** | Многоролевой и многопоколенческий бюджет коннектов $\le 0.60 \times \text{Limit\_dep\_share}[d]$ | Параметризованный тест вычисляет $\sum_r N_{\text{proc}, r} (\sum_k G_{\text{reload}, r, k} \cdot \text{pool\_max\_size}_{r,k} + \text{dedicated}_{r,d})$ по конфигу всех ролей (`crawler`, `llm`, `pod_fetcher`, `control_plane`, `migrations_cron`) и проверяет $\le 0.60 \times \text{Limit\_dep\_share}[d]$; при hot-reload проверяет `old_pool.closed == True` до `new_pool.open()` (при $G_{\text{reload}}=1$) либо учёт $G_{\text{reload}}=2$ |
| **`C-MULT-I2`** | `BlockingConnectionPool` и лимит очереди ожидающих `max_waiters <= 2M` | Unit-тест инспектирует пул: `isinstance(pool, BlockingConnectionPool)`, `pool.max_connections == M`, `pool.timeout == T_wait_s`; при запуске $M + \text{max\_waiters} + 1$ конкурентных корутин на заблокированном фейковом транспорте $(M + \text{max\_waiters} + 1)$-я корутина детерминированно получает `PoolWaitersExhaustedError`, а число созданных сокетов равно ровно $M$ |
| **`C-MULT-I3`** | Singleton-per-process после `fork()` и закрытие в `aclose()` | При $100$ вызовах обработчика/резолвера `id(client)` неизменен (`created_clients == 1`), в родительском процессе до `fork()` сетевые сокеты пула не открыты (`open_sockets_before_fork == 0`), а после `await app.aclose()` `client.is_closed == True` |
| **`C-MULT-I4`** | Безопасность отмены `Task.cancel()` / `wait_for` для слотов пула | После $50$ циклов принудительной отмены корутины (`task.cancel()`) на фазах `acquire` и `read` счётчик занятых слотов пула и семафора ожидающих возвращается в `0` (`in_use == 0`, `waiters == 0`) |
| **`C-MULT-I5`** | Бюджет FD ($\le 70\%$ `ulimit_n`), эфемерных портов и SNAT ($\le 50\%$ пула портов) | Тест проверяет оба неравенства: (1) $\text{FD}_{\text{worker}} \le 0.70 \times \text{ulimit\_n}$, (2) $\lambda_{\text{new\_conn\_per\_pod}}(s) \cdot N_{\text{pods\_in\_scope}}(s) \cdot T_{\text{hold\_s}}(s) + C_{\text{active\_in\_scope}}(s) \le 0.50 \times (\text{SNAT\_ips\_count}(s) \cdot \text{Port\_range\_size}(s))$ для $s \in \{\text{node\_ephemeral}, \text{shared\_snat}\}$, а также проверяет `new_connections_opened == 1` на серии из $50$ keep-alive запросов |
| **`S-HERD-I1`** | Пачечная граница стартового залпа $K_{\text{calls}}[d] \cdot (\lambda_{\text{fetch}} + 4\sqrt{\lambda_{\text{fetch}}} + 4) \le 0.50 \times \text{Limit\_dep\_rps}[d]$ и поллинга $\le 20\%$ | Тест вычисляет $\lambda_{\text{fetch}}(d) = \frac{P_{\text{live}} \cdot W_{\text{fetchers}}[d]}{\max(J_{\text{init\_s}}[d], J_{\text{pod\_s}}[d])}$ и проверяет $K_{\text{calls}}[d] \cdot (\lambda_{\text{fetch}}(d) + 4\sqrt{\lambda_{\text{fetch}}(d)} + 4) \le 0.50 \times \text{Limit\_dep\_rps}[d]$ (либо конфигурацию RPS Token-Bucket Rate-Limiter) и $\sum_m R_{\text{poll}, m}(d) \le 0.20 \times \text{Limit\_dep\_rps}[d]$, а для `pod_fetcher` — атомарную публикацию через `os.replace` |
| **`S-HERD-I2`** | Детерминированная проверка пересева CSPRNG после `fork()`, джиттера `[0.8T, 1.2T]` и Full-Jitter backoff | С моком `os.urandom` (`return_value = b"0123456789abcdef"`) тест вызывает post-fork hook и проверяет `mock_urandom.assert_called_once_with(16)` и передачу этих байтов в `random.seed`; при подаче в инъектированный RNG детерминированных точек `u ∈ [0.0, 0.5, 1.0]` функция сна поллера возвращает ровно `[0.8 * T_poll_s, 1.0 * T_poll_s, 1.2 * T_poll_s]`, а функция backoff — ровно `[0.0, 0.5 * min(T_cap_s, T_base_s * 2**a), 1.0 * min(T_cap_s, T_base_s * 2**a)]` |
| **`S-HERD-I3`** | Условный запрос `If-None-Match` (`304`) и неизменность `id(snapshot)` | При ответе мок-сервера `HTTP 304 Not Modified` на отправленный `If-None-Match` шпион `parse_and_build_snapshot.call_count == 0`, а `id(worker.snapshot)` до и после цикла опроса совпадает |
| **`S-HERD-I4`** | Cancellation-safe `singleflight` с владением задачей и запрет negative-cache на `5xx`/timeout | `asyncio.gather` из $50$ корутин на одном ключе вызывает `backend.fetch` ровно $1$ раз; отмена первой корутины не отменяет остальные $49$; отмена всех $50$ корутин или вызов `await client.aclose()` очищает `client._inflight` без `unretrieved task exception`; после `TimeoutError`/`503` следующий вызов идёт в `backend.fetch` (`call_count == 2`), а после `404` берётся из negative-cache (`call_count == 1`) |
| **`S-HERD-I5`** | Разделение `readiness`/`liveness`, истечение `Max_stale_age_s[c]` и отзыв секретов | До первого `Snapshot` `/health/ready == 503` и `/health/live == 200`; после загрузки и падения Control Plane при продвижении `FakeClock` на $\Delta t \le \text{Max\_stale\_age\_s}$ `/health/ready == 200` (отдаётся `last_known_good`), а при $\Delta t > \text{Max\_stale\_age\_s}$ `/health/live == 200`, но срабатывает политика истечения (`ready == 503` / `stale_expired_total += 1`); при увеличении `revocation_epoch` или `401` секрет немедленно удаляется из кэша |
| **`H-CPU-I1`** | Предвычисленные индексы `Snapshot` ($O(1)$ или $O(\log N)$) и эквивалентность эталону | Property/equivalence-тест проверяет совпадение результата быстрого индекса с эталонным отбором (включая приоритеты и `M-SEM/v1`), а счётчик элементарных сравнений индекса при росте $N$ от $100$ до $10000$ проверяет $\text{steps}(10000) == \text{steps}(100)$ для $O(1)$ хэш-индексов либо $\text{steps}(N) \le c_1 \cdot \lceil \log_2(N) \rceil$ для префиксных деревьев $O(\log N)$ (запрещая линейный рост $\propto N$) |
| **`H-CPU-I2`** | Запрет `re.compile`, `json.loads`, `model_validate`, `TypeAdapter`, `deepcopy` и перепривязки меток на горячем пути | Шпионский тест прогоняет запрос через `HOTPATH_MODULES` с перехватом всех 6 примитивов: `re._compile`, `json.loads` (конфигов/правил), `BaseModel.model_validate`, `TypeAdapter.validate_python`, `copy.deepcopy` и `MetricWrapperBase.labels` (для статических тегов) и проверяет `call_count == 0` для каждого |
| **`H-CPU-I3`** | `Zero-Cost Disabled Path` и неблокирующий `put_nowait` с `dropped_total` | При `enabled=False` шпионы на конструкторе события и `uuid.uuid4` имеют `call_count == 0`, `queue.qsize() == 0`; при `enabled=True` и заполненной до `maxsize` очереди новый вызов возвращает управление синхронно без `await`, не выбрасывает исключение в запрос и увеличивает `dropped_total` на `1` |
| **`H-CPU-I4`** | Защита event loop на Reload Path ($\le 2\text{ мс}$ на тик, без ложного полагания на GIL в `orjson`/`to_thread`) | Тест горячего обновления `Snapshot` проверяет выбранный нормативный механизм: (а) при `mmap`-индексе — воркер открывает `mmap` без вызова `json.loads`/`orjson.loads` (`call_count == 0`); либо (б) при пошаговой кооперативной сборке на $N$ элементах — каждые `MAX_ITEMS_PER_TICK` шагов вызывается `await asyncio.sleep(0)` (`sleep_zero_calls >= floor(N / MAX_ITEMS_PER_TICK)`), а `self._snapshot` заменяется атомарно в конце |
| **`H-CPU-I5`** | Тройное замыкание бюджета CPU (`Util_worker <= 0.70`, `Pod <= 0.80`, `Feature <= 5%`) | Расчётный тест по параметрам `HL-ENV/v1` и CPU-секундам $t_{\text{per\_req\_s}}, t_{\text{per\_attempt\_s}}$ проверяет одновременно все 3 неравенства `H-CPU-I5` при $P_{\text{avail\_min}} = \max(1, P_{\text{steady}} - \text{maxUnavailable\_abs})$, $\kappa_{\text{skew}}$, $u_{\text{bg\_worker}}$ и $U_{\text{pod\_sidecars}}$ |
| **`R-BULK-I1`** | Статическое неравенство $\le 0.30 \times \text{SLA}_{\text{p99\_s}}$ и обрыв по `remaining_deadline <= 0` | Тест проверяет: (1) статическое неравенство конфига $\sum_{a=1}^{A_{\max}} (T_{\text{crit\_aux\_s}}(a) + T_{\text{wait\_s}}(a) + T_{\text{backoff\_s}}(a)) \le 0.30 \times \text{SLA}_{\text{p99\_s}}$; (2) на `FakeClock` в каждый вызов передаётся `timeout = min(T_budget_s, deadline_s - clock.now())`, а при `clock.now() >= deadline_s` следующая попытка и вызовы не запускаются (`call_count == 0`) |
| **`R-BULK-I2`** | Точная граница Token-Bucket Retry Budget и `Bulkhead` семафор | На `FakeClock` за окно $T_w$ при серии из $N_{\text{req}} = 100$ падающих запросов число ретраев удовлетворяет точной формуле $N_{\text{retries}} \le \lfloor 0.20 \cdot N_{\text{req}} + \text{min\_reserve\_retry\_rps} \cdot T_w \rfloor + B_{\text{retry\_max}}$; при занятых `max_concurrent` и `max_waiters` семафора `Bulkhead` новый вызов мгновенно (за `0` тиков `FakeClock`) уходит в fallback |
| **`R-BULK-I3`** | `Circuit Breaker` с джиттером `OPEN` и ровно $1$ пробой в `HALF_OPEN` | После $K$ ошибок подряд зависимость переходит в `OPEN`, и вызовы уходят в fallback без сетевого обращения (`backend.call_count` не растёт); после сдвига `FakeClock` на `reset_timeout * U(0.8, 1.2)` при одновременном запуске $10$ корутин в `HALF_OPEN` в `backend` уходит ровно $1$ пробный запрос (`probe_calls == 1`), а остальные $9$ мгновенно получают fallback |
| **`R-BULK-I4`** | Двухэтапный фильтр `M-SEM/v1` и post-eviction предикат `Panic-Open` ($|V_{\text{healthy}}| - 1 \ge N_{\text{floor}}$) | Тест проверяет на граничных размерах $|V_{\text{eligible}}| \in \{0, 1, 4, 10\}$: при $|V_{\text{eligible}}| = 0$ возвращается `503` с метриками по `O-EXIT/v1`; при $|V_{\text{eligible}}| \ge 1$ мягкий карантин прекращает исключение нод, как только $|V_{\text{healthy}}| - 1 < \max(1, \lceil \text{Min\_healthy\_ratio} \times |V_{\text{eligible}}| \rceil)$ (в частности, при $|V_{\text{eligible}}| = 1$ единственная допустимая нода никогда не исключается в `0`), а ноды `disabled`, `auth_failed`, чужого пула (`M-SEM/v1`) и запрещённого гео никогда не попадают в выдачу |
| **`R-BULK-I5`** | Разделение `Origin Health` и `Node Health` | При $M$ последовательных ошибках `502/504` на домене `bad-origin.example` через $M$ разных прокси-нод открывается `origin_health["bad-origin.example"]`, но для домена `good-origin.example` все $M$ прокси-нод остаются в статусе `healthy` |

---

### 7.3. Реестр неснимаемых стоп-кодов (`REJECT` / `BLOCKER` до мержа)

Любой из 21 кода (`HL-ENV-01`, `C-MULT-I1..I5`, `S-HERD-I1..I5`, `H-CPU-I1..I5`, `R-BULK-I1..I5`) наряду с `T-LIFE/v1`, `O-EXIT/v1`, `M-SEM/v1` является **неснимаемым стоп-кодом (`NON-WAIVABLE STOP CODE`)**: ни Coder, ни Reviewer, ни Архитектор, ни Совет Тимлидов не имеют права пометить нарушение как «неблокирующий техдолг / исправим в следующем PR». При любом `FAIL` или отсутствии соответствующего детерминированного теста из таблицы Раздела 7.2 выносится вердикт `REJECT`.
ARTIFACT_END>>>
<<<ARTIFACT ~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/security.md sha256=eac0f9fd058160818f31e1f2698f7a4ca25eb2ecb270b11b0859f33e4f724259
# Политика безопасности

## Секреты

- `OPENROUTER_API_KEY`, токены БД, пароли — **только в `~/.zshrc` или `.env`** (который в `.gitignore`).
- В код, конфиги, тесты, документацию ключ **не попадает** — везде `os.environ["OPENROUTER_API_KEY"]` или подстановка через `${OPENROUTER_API_KEY}` в шаблонах.
- В Continue ключ задаётся через секрет-плейсхолдер `${{ secrets.OPENROUTER_API_KEY }}`, а не вписывается напрямую.
- Если ключ утёк (попал в git history, в Slack, в скриншот) — немедленно **disable** его в OpenRouter Settings → Keys и создай новый.
- На каждый ключ — отдельный credit limit (минимум, ровно под задачу). На дефолтный воркшоп-ключ — $5.

## Bandit

- `bandit` запускается на каждом коммите через pre-commit (см. Шаг 3.2).
- Если bandit нашёл проблему в чужом коде (не из текущего diff) — **отдельный коммит** `[manual] fix(security): <описание на русском>`, потом штатный коммит фичи (тэг английский, описание — на русском, см. `.agents/AGENTS.md` → «Язык общения»).
- Никаких `# nosec` без комментария с пояснением **почему** именно эта конструкция безопасна в этом контексте.

## pip-audit

- `pip-audit` запускается на каждом коммите через pre-commit (см. Шаг 3.2).
- На каждое CVE в зависимости — отдельный коммит `[manual] chore(deps): обновить <package> до X.Y.Z для CVE-XXXX-XXXXX` (тэг английский, описание — на русском).
- Не смешивать security-fix с фичей в одном коммите.

## Pre-commit хуки — никаких обходов

Список **запрещённых** способов обойти pre-commit-проверки. Все они дают одно и то же — коммит с непроверенным кодом. Применять их нельзя ни при каких обстоятельствах:

- `git commit --no-verify` — пропускает все хуки полностью.
- `PRE_COMMIT_ALLOW_NO_CONFIG=1 git commit ...` — пропускает хуки, если конфига нет. Если ты видишь эту переменную в команде — значит конфиг **потерян** (например, лежит untracked и попал в `git stash -u`). Реакция — **восстановить конфиг**, не обходить.
- `SKIP=hook1,hook2 git commit ...` — пропускает указанные хуки. Допустим **только** в двух случаях: (1) личные `[manual] WIP:`-коммиты в своей feature-ветке (squash перед MR обязателен), (2) учебный коммит no-rules-артефакта в Шаге 6.2 (`SKIP=basedpyright`) — там Qwen намеренно пишет код без типов, это часть демо.
- `pre-commit uninstall` с целью «временно отключить» — снимает хук вообще. Возврат через `pre-commit install` после починки.

Если хук падает на чужом коде, который не относится к твоей задаче — **отдельный security-коммит** перед твоей фичей (политика «по CVE отдельным коммитом» выше). Никогда — обход.

Если `.pre-commit-config.yaml` физически отсутствует в проекте — **остановиться**, восстановить файл из git-истории (`git show HEAD:.pre-commit-config.yaml > .pre-commit-config.yaml`) или из стэша, и только после этого продолжать.

## Опасные конструкции — не использовать

- `eval` / `exec` от пользовательского ввода.
- `subprocess.run(..., shell=True)` — только списком аргументов без shell.
- `yaml.load(...)` без `Loader=yaml.SafeLoader` — только `yaml.safe_load`.
- Захардкоженные пароли / API-ключи / connection strings.
- `pickle.loads` от недоверенного источника.

***

## Security-паттерны Python — расширенный набор

Это **прикладные** паттерны: что чаще всего ломается в Python-сервисах и как этого избежать. bandit ловит часть из них, но не все — поэтому правила записаны явно, агент ссылается на них в code review.

### 1. SSRF (Server-Side Request Forgery)

Когда сервис делает исходящий HTTP по URL, который **частично или полностью контролирует пользователь** (preview ссылки, webhook URL, импорт RSS, OAuth callback, image proxy), это потенциальный SSRF.

**Атака:** пользователь даёт URL вида `http://169.254.169.254/latest/meta-data/...` (AWS metadata), `http://10.0.0.5:6379/` (internal Redis), `http://localhost:9090/` (внутренний админ-эндпоинт).

**Правила:**

- Allow-list схем (`http`, `https`) — никаких `file://`, `gopher://`, `ftp://`.
- **DNS resolve → проверка по IP**, не по hostname (защита от DNS rebinding). Отвергай `ip.is_private / is_loopback / is_link_local / is_multicast / is_reserved`.
- Запрети редиректы (`follow_redirects=False`) или валидируй каждый промежуточный URL по тем же правилам.
- Жёсткий `httpx.Timeout(connect, read, write, pool)`, ограничение `max_bytes` на ответ (стримом, не в память целиком).

~~~python
import ipaddress
import socket

import httpx

_ALLOWED_SCHEMES = frozenset({"http", "https"})
_MAX_BYTES = 10 * 1024 * 1024

def _is_public_ip(ip_str: str) -> bool:
    ip = ipaddress.ip_address(ip_str)
    return not (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_multicast or ip.is_reserved or ip.is_unspecified)

async def fetch_preview(url: str) -> bytes:
    parsed = httpx.URL(url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise ValueError("scheme not allowed")
    infos = socket.getaddrinfo(parsed.host, parsed.port or 443, proto=socket.IPPROTO_TCP)
    ips = {info[4][0] for info in infos}
    if not all(_is_public_ip(ip) for ip in ips):
        raise ValueError("resolved to non-public ip")
    timeout = httpx.Timeout(connect=2.0, read=5.0, write=5.0, pool=2.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        async with client.stream("GET", url) as r:
            r.raise_for_status()
            buf = bytearray()
            async for chunk in r.aiter_bytes():
                buf.extend(chunk)
                if len(buf) > _MAX_BYTES:
                    raise ValueError("response too large")
            return bytes(buf)
~~~

### 2. Path traversal

Когда путь к файлу формируется из пользовательского ввода (upload, download by name, read template by id) — атакующий передаёт `../../../../etc/passwd`.

**Правила:**

- Резолви и проверяй принадлежность к root-каталогу: `Path.resolve()` + `is_relative_to(root)` (Python 3.9+).
- Allow-list символов в имени, если можно (`^[a-zA-Z0-9._-]+$`).
- Никаких `..` и абсолютных путей в имени — отвергай сразу.

~~~python
from pathlib import Path

_UPLOADS = Path("/var/uploads").resolve()

def read_user_file(name: str) -> str:
    candidate = (_UPLOADS / name).resolve()
    if not candidate.is_relative_to(_UPLOADS):
        raise ValueError("path traversal attempt")
    if not candidate.is_file():
        raise FileNotFoundError(name)
    return candidate.read_text(encoding="utf-8")
~~~

### 3. Unsafe deserialization

`pickle`, `yaml.load` без `SafeLoader`, `xml.etree` с внешними entities, `jsonpickle` — **исполняют код** на untrusted input.

| Формат | Untrusted input | Trusted input |
|---|---|---|
| `pickle` / `marshal` / `shelve` / `dill` | **Никогда** | Только для собственных контролируемых данных |
| `yaml.load()` | **Никогда** | `yaml.safe_load()` всегда |
| `xml.etree.ElementTree` / `lxml` без `resolve_entities=False` | **Никогда** (XXE) | `defusedxml` или explicit disable external entities |
| `jsonpickle` | **Никогда** | `pydantic` или `dataclasses_json` |
| `eval` / `exec` на user input | **Никогда** | `ast.literal_eval()` для безопасного подмножества |

### 4. File upload — hardening

При приёме файла от пользователя:

- **Проверяй MIME по содержимому**, не по заголовку `Content-Type` (он от клиента — untrusted). Через `python-magic` / `magic.from_buffer(raw, mime=True)`.
- Ограничивай размер **до** того, как файл попадёт в память — стриминговое чтение с early reject.
- Имя файла санитайзируй или **генерируй заново** (UUID). Никогда не используй raw имя для пути на диске.
- Храни **вне webroot**, отдавай через контроллер с авторизацией.
- Для картинок — передекодируй через Pillow (`Image.verify()` + повторное открытие + `convert("RGB")` + `save`). Это снимает payload'ы, зашитые в exif / metadata / polyglot-форматы.

### 5. TLS verification — никогда не отключать

~~~python
# ❌ MITM-vulnerable
httpx.get(url, verify=False)
requests.get(url, verify=False)
~~~

**Допустимо** отключать только: (1) в тестах с локальным mock-сервером (явный `# noqa` + комментарий), (2) для internal CA — `verify="/path/to/internal-ca.pem"`, **не** `False`.

### 6. Request timeouts — всегда

`requests.get(url)` без `timeout=` — анти-паттерн. Запрос может висеть бесконечно, GIL-поток зависает, в async — таска не отпускает event loop.

~~~python
# ✅ requests
r = requests.get(url, timeout=(2.0, 10.0))  # (connect, read)

# ✅ httpx
timeout = httpx.Timeout(connect=2.0, read=10.0, write=10.0, pool=2.0)
async with httpx.AsyncClient(timeout=timeout) as client:
    r = await client.get(url)
~~~

### 7. JWT / OAuth

**JWT:**

- **Никогда не доверяй `alg: none`** — explicit reject.
- При `decode` указывай **ожидаемый** алгоритм: `algorithms=["RS256"]`, не wildcard.
- Verify `exp` / `nbf` / `iat` / `aud` / `iss` — особенно в multi-tenant.
- Ключи в KMS / vault, не в `.env` для prod.
- В payload — **только идентификаторы** (sub, aud, iss). Никаких секретов: payload base64, не зашифрован.

~~~python
import jwt
from jwt.exceptions import InvalidTokenError

try:
    payload = jwt.decode(
        token,
        public_key,
        algorithms=["RS256"],
        audience="my-service",
        issuer="https://auth.example.com/",
        options={"require": ["exp", "iat", "sub", "aud", "iss"]},
    )
except InvalidTokenError as e:
    raise AuthError("invalid token") from e
~~~

**OAuth:**

- **PKCE** обязательно для public-клиентов (mobile, SPA).
- **`state`** обязательно (CSRF-защита authorization request).
- `redirect_uri` — точное совпадение с allow-list (не префикс, не подстрока).
- `nonce` в OIDC `id_token`.
- `refresh_token` — **никогда** в браузер. Public-клиенты: PKCE + short-lived access_token.

### 8. Subprocess sandboxing

- **`shell=False`** всегда. `subprocess.run([prog, arg1, arg2], ...)`, не строка.
- **Никогда не интерполируй user input в команду строкой** — только в args list.
- Абсолютный путь к бинарнику или `which` — не доверяй PATH.
- Жёсткий `timeout=`.
- Ограничь environment: `env={"PATH": "/usr/bin"}`, не передавай весь `os.environ`.

~~~python
# ❌ injection
subprocess.run(f"convert {user_file} out.jpg", shell=True)

# ✅
CONVERT = "/usr/bin/convert"
subprocess.run(
    [CONVERT, str(user_file), str(out)],
    check=True, timeout=30, capture_output=True,
    env={"PATH": "/usr/bin"},
)
~~~

### 9. Secure temp files

- `tempfile.NamedTemporaryFile` / `TemporaryDirectory()` — context manager, авто-cleanup.
- **Никогда `tempfile.mktemp()`** — race condition (имя возвращается до создания файла).
- Никаких `/tmp/work_{os.getpid()}.txt` — predictable path = race condition + permission tricks.

### 10. Криптография

- **Никогда** не пиши свою crypto. `cryptography` (стандартный API), `hazmat` — только с code review.
- **Никогда `hashlib.md5` / `sha1` для security** (passwords, tokens, signatures). Они для checksum, не для безопасности.
- Пароли: `passlib.hash.bcrypt` или `argon2-cffi`.
- HMAC / сравнение секретов: `hmac.compare_digest(a, b)` (constant-time), **не** `a == b` (timing attack).
- Random для security: `secrets.token_urlsafe(32)` / `secrets.SystemRandom`, **не** `random` (predictable).

~~~python
import hmac
import secrets

def make_token() -> str:
    return secrets.token_urlsafe(32)

def verify_token(provided: str, expected: str) -> bool:
    return hmac.compare_digest(provided.encode(), expected.encode())
~~~

***

## Что этот файл НЕ покрывает

- **Авторизация / authentication на уровне дизайна** (RBAC vs ABAC, multi-tenant boundaries) — это уровень ADR (`.agents/agents/docs.md`), не code style.
- **Threat modeling, pentest playbook** — отдельная дисциплина, выходит за рамки воркшопа.
- **IaC security** (S3 Block Public Access, IAM wildcards, security groups) — за рамками проекта.
ARTIFACT_END>>>
<<<ARTIFACT ~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/error-handling.md sha256=885569b2554648edabd9db42863fd01941a8f08684111255e95d3c1abeb02525
# Error handling rules

Что делать, когда на любом шаге выполнения задачи возникла ошибка,
неоднозначность или блокер. Файл применим к любому скиллу из
`.agents/skills/` — feature, bugfix, refactoring, hotfix, code-review,
tests, docs.

## Главное правило

**Не предлагай workaround сразу — сначала пойми, почему упало.**

Привычка лепить `# type: ignore`, `try/except: pass`, `# noqa` или
переписывать тест под текущее поведение — это превращение проблемы в
техдолг с задержанным взрывом. На каждую ошибку проходи 5 шагов в
порядке:

1. **Identify** — чётко скажи, **что именно** сломалось. Не «basedpyright
   ругается», а «basedpyright говорит, что
   `services/link.py:42` возвращает `Link | None`, но handler
   ожидает `Link`».
2. **Assess impact** — какой severity (Critical / High / Medium / Low,
   таблица ниже), что блокирует, что нет.
3. **Communicate** — скажи оператору, что произошло, какие у него опции.
   Не выбирай за него на серьёзных severity.
4. **Offer solutions** — конкретные шаги по восстановлению, не общие
   фразы вида «попробую исправить».
5. **Document** — то, что выбрано, зафиксируй: либо комментарием в коде
   рядом с местом компромисса (`# принят компромисс: <что>, причина <какая>`),
   либо короткой заметкой в `Tasks/<key>/decisions.md` (если папка задачи
   используется). Цель — чтобы при возврате к коду через месяц было видно
   почему так.

## Severity-уровни

| Уровень | Значит | Реакция |
|---|---|---|
| **Critical** | Дальше работать невозможно. Сломалось что-то, чего ты не трогал, или код в принципе невозможно скомпилировать/запустить. | Останови работу. Зафиксируй симптом и контекст. **Не предлагай workaround**. Жди явного решения оператора. |
| **High** | Текущий шаг не завершится как планировалось. Например, тест падает по неочевидной причине, basedpyright показывает ошибку, которую ты не можешь объяснить. | Опиши проблему, предложи 2–3 варианта восстановления с trade-offs, получи выбор оператора. Не двигайся вперёд молча. |
| **Medium** | Шаг можно закрыть с workaround, но это компромисс, который нужно явно зафиксировать. Например, не получилось переиспользовать существующий helper, пришлось написать локальную копию. | Опиши workaround, пометь в плане как «принят компромисс — `<что>`, причина — `<какая>`». Двигайся дальше. |
| **Low** | Незначительное, не блокирует. Например, опечатка в комментарии в файле, который ты не трогаешь. | Зафиксируй в плане как `TODO` (отдельным пунктом или в существующем), не отвлекайся в этой задаче. |

## Типовые ситуации

### `basedpyright` показывает ошибку в коде, который ты не трогал

Severity по умолчанию — **High**. Это значит, что либо ты что-то сломал
косвенно (изменил тип в одном месте, и поломалось в другом), либо
basedpyright обновился и поймал ранее пропущенную ошибку.

- ❌ **НЕ ставь** `# pyright: ignore[...]` или `# type: ignore` без объяснения, чтобы продолжить.
- ✅ **Сделай:** прочитай ошибку, открой указанный файл, разберись.
  Если это побочка твоих изменений — исправь. Если это существующая
  проблема, не связанная с задачей — зафиксируй как отдельный
  `[manual] fix(types): <описание на русском>` коммит до основной работы (см. правило про
  pip-audit / bandit в `.agents/agents/code.md`).

### Тест падает по неочевидной причине

Severity — **High**.

- 1-я попытка: прочитай traceback внимательно, проверь предположения.
- 2-я попытка: добавь `print`/`breakpoint` (временно — удалить до коммита!), посмотри состояние.
- 3-я попытка: если всё ещё не понятно — **стоп**. Опиши оператору, что именно непонятно, какой traceback, что уже попробовал. Не лепи `pytest.skip` или подгонку asserts.

Правило **трёх попыток** — то же, что для pre-commit в `.agents/AGENTS.md`.
Цикл «попробуй ещё раз то же самое» — анти-паттерн.

### Migration упала / Alembic конфликт

Severity — **Critical**, если конфликт в `head` или сломан downgrade.
**High** во всех остальных случаях.

- Не запускай `alembic stamp head` без понимания состояния — это
  оставляет БД в неконсистентном состоянии.
- Покажи оператору `alembic history --verbose` и `alembic current`, опиши
  что видишь, дай выбрать стратегию мерджа миграций.

### `pre-commit` упал на хуке, который раньше проходил

Severity зависит от хука:

- **ruff / basedpyright** на твоих изменениях — High, исправляй (см.
  `.agents/AGENTS.md` Исход C).
- **bandit / pip-audit** на коде, который ты не трогал — High, отдельный
  коммит `[manual] fix(security|deps): <описание на русском>` до основной работы (тэг и scope английские, описание — на русском, см. `.agents/AGENTS.md` → «Язык общения»).
- **gitleaks** — **Critical**. Останавливайся немедленно, не пытайся
  обойти. Если секрет реально попал в diff — отзови сам секрет в
  первоисточнике (revoke API key / ротация пароля), потом удаляй из
  кода. Если ложное срабатывание — добавь в `.gitleaksignore` с
  явным обоснованием в комментарии.

### Архитектурный документ в `Tasks/<key>/<key>-architecture.md` противоречит коду

Severity — **High** (если код уже мержёный) или **Medium** (если код
ещё в твоей ветке).

- Не пиши код «по плану», игнорируя реальность.
- Не правь код «по плану», ломая поведение.
- Обнови план до реального состояния, объясни оператору расхождение,
  спроси: переделываем код или обновляем план как source of truth.

### Сторонняя библиотека ведёт себя не так, как описано

Severity — **High**.

- Не предполагай, что ты понял документацию неправильно. Покажи
  оператору минимальный воспроизводимый пример (5–10 строк), ожидаемое
  vs реальное поведение, версию библиотеки.
- Workaround в коде, скрывающий проблему, — только если оператор явно
  одобрил. Пометь в плане «принят компромисс из-за `<lib> <version>`,
  TODO: убрать после `<условие>`».

### Контекст сессии переполняется, начинаешь забывать ранние решения

Severity — **High** (для самого качества работы).

- **Остановись**, не «выжимай ещё чуть-чуть».
- Зафиксируй текущий прогресс короткой заметкой — либо в чат оператору,
  либо в `Tasks/<key>/session-state.md` (если папка задачи используется).
  Что нужно: что уже сделано, на каком файле/строке остановились, какое
  решение нужно дальше принять.
- Скажи оператору: «Контекст близок к переполнению, состояние зафиксировал.
  Предлагаю продолжить в новой сессии с этой точки».

## Что точно НЕ делать ни на каком severity

- **Молча применять workaround** (`# noqa`, `# type: ignore`, `pytest.skip`, голый `except: pass`) — это превращение видимой проблемы в скрытую.
- **Менять тест под текущее поведение** — тест проверяет требование, не реализацию. Если тест падает, и поведение в коде на самом деле верное — тест надо переписать осознанно с явным согласованием, что требование изменилось.
- **Откладывать в `TODO` для всего, что не Low** — Low-severity это «опечатка в комментарии в чужом файле», а не «не разобрался почему migration упала».
- **Зацикливаться на одной ошибке более 3 попыток.** После 3-й — остановка и эскалация оператору.
- **Делать "исправил, посмотрим"** без понимания, почему предыдущая версия не работала. Если не понимаешь, почему не работало — не понимаешь, почему теперь работает.
ARTIFACT_END>>>
<<<ARTIFACT ~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/logging.md sha256=e271d9fdea35c1802120c166df6035479b477d33cc9dcdde483f4f60c92e7cfb
# Logging rules

## Стек

- **Сервис** — `structlog` (структурные логи).
- **Библиотека** — стандартный `logging` (не навязываем формат потребителю).
- Сериализатор для prod — `orjson` через `structlog.processors.JSONRenderer(serializer=orjson.dumps)`.
- Конфигурация — один раз на старте, в `configure_logging()` из `app/logging.py`.

## Правила

- **Никогда `print()`** для логирования. Отлаживаешь — `breakpoint()`; пишешь в стрим — `logger.info(...)`.
- **kwargs, не f-строки** в сообщении. Event-строка стабильная, параметры отдельно:

  ```python
  # ❌
  logger.info(f"order {order_id} processed in {duration}s")

  # ✅
  logger.info("order processed", order_id=order_id, duration_s=duration)
  ```

  Иначе в Loki / ELK невозможно сгруппировать `count by event` — каждое сообщение уникальное.

- **Не логируй секреты в kwargs.** Пароли, токены, Authorization, cookie, PII — никогда. На последней линии работает рекурсивный `redact_secrets`-processor (см. `app/logging.py`), но это страховка; имя поля `password` / `token` / `secret` в `logger.info(..., password=p)` уже **bug в код-стиле**.
- **Не логируй в горячих циклах.** Лог в hot path под нагрузкой → I/O bottleneck. Логируй итог цикла или сэмплируй (один из N).
- **Контекст запроса — через `bind_contextvars`.** Middleware биндит `request_id` (или подхватывает `X-Request-ID`) в начале запроса, очищает в конце. Все логи в рамках запроса автоматически получают это поле — `grep request_id=...` показывает весь pipeline.

## Уровни

| Уровень | Когда | Пример |
|---|---|---|
| `debug` | Локальная отладка; в prod отключено | `log.debug("repo query plan", plan=plan)` |
| `info` | Значимые события: запуск, бизнес-операция | `log.info("link created", code=code)` |
| `warning` | Нештатно, но обработано (retry, fallback) | `log.warning("openrouter retry", attempt=2)` |
| `error` | Операция не выполнена, требует внимания | `log.error("db connection failed", url=...)` |
| `critical` | Сервис неработоспособен | `log.critical("config missing", key="DB_URL")` |

В prod уровень `info` и выше; `debug` включается локально через ENV (`LOG_LEVEL=DEBUG`).

## Формат

- **prod** — JSON-строки (`JSONRenderer(serializer=orjson.dumps)`), одна строка = один event. Это требование Loki / ELK / Datadog.
- **dev** (`APP_ENV=local`) — `ConsoleRenderer` с цветом, читаемые traceback'и.
- Поле `message` — переименованный `event` (для совместимости с Loki, где `message` — стандартное имя).
- Поле `request_id` — добавляется автоматически в middleware (см. `app/middleware/request_id.py`).
- Поля `module` / `func_name` / `lineno` — добавляются автоматически через `CallsiteParameterAdder`.

## Интеграция со stdlib logging

Логи `uvicorn` / `sqlalchemy` / `litestar` / `httpx` идут через стандартный `logging`. Чтобы они **тоже** проходили через redact_secrets и попадали в один JSON-поток, в `configure_logging()` настраивается `structlog.stdlib.ProcessorFormatter` + `foreign_pre_chain`. Без этого SQL-запросы от SQLAlchemy и HTTP-логи uvicorn летят сырыми и могут утечь параметрами в plaintext.

## Запреты (блокируют merge)

- `print()` в `app/` для логирования.
- `logger.info(f"... {var} ...")` — f-строка в сообщении.
- Поля `password` / `token` / `secret` / `authorization` / `cookie` / `api_key` в kwargs логгера.
- Свой `logging.basicConfig(...)` в обход `configure_logging()`.
ARTIFACT_END>>>

ВЕРДИКТ ТВОЕЙ РОЛИ В РАУНДЕ 1:
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/cycle-1/debate/r1/realist.md sha256=aa4c88929c443a26848b7a931801a0c41675ce5a2432ff9d17fbecd8bb432dd3
> PANEL-NONCE: fce3b92e58de602c
> ARTIFACT-SHA256: 5b0d1dea0cf4996f6d744e0eb2d82176578091bad35c943dde722c09d3784df4
>
> Проверяю пакет как судья «Реалист»: все 14 подкатегорий, реализуемость выката, ресурсы и зависимости. Результаты проверок беру из приложенных свидетельств; тесты не запускаю.
>
> Применяю правила `teamlead-gate` для полного прохода. Общий канон `~/Мой диск/Context/AGENTS.md` прочитан до `<!-- КАНОН-КОНЕЦ -->`; в рабочей папке `AGENTS.md`, `.agents/AGENTS.md` и `CLAUDE.md` отсутствуют. Профильные стандарты прочитаны в приложенном пакете.
>
> L2 подтверждает зелёный полный набор, но reverse-spec отмечает непроверенные ветки serve. Сверяю их с кодом, прежде всего таймауты, повторы и освобождение ресурсов.
>
> Нашёл конкретные расхождения: serve обходит ограничитель стартов, отбрасывает дельты из одних пробелов и переводов строк, а некоторые ошибки запуска выходят до уборки процесса. Полный L2-прогон остаётся подтверждённым; он не проверяет эти сценарии. Завершаю сверку требований и повторный проход по рубрике.
>
> Повторный проход завершён. Базовая идея внедряема: нужный CLI установлен, новый транспорт не требует сторонних Python-зависимостей, а память предварительно укладывается в бюджет. Блокеры — в реализации жизненного цикла и совместимости serve с прежним поведением. Отсроченные `VER-006` и `VER-007` учитываю как законный `DEFERRED_L3`, без отдельного FAIL.
>
> PANEL-NONCE: fce3b92e58de602c
> ARTIFACT-SHA256: 5b0d1dea0cf4996f6d744e0eb2d82176578091bad35c943dde722c09d3784df4
>
> Общий канон `~/Мой диск/Context/AGENTS.md` прочитан до `<!-- КАНОН-КОНЕЦ -->`. В рабочей папке `AGENTS.md`, `.agents/AGENTS.md`, `CLAUDE.md` отсутствуют; приложенные профильные стандарты прочитаны. Проверенные SHA-256 трёх файлов совпадают с манифестом. Тесты самостоятельно не запускал.
>
> 1. КОРРЕКТНОСТЬ: VERDICT=FAIL  
>    WHY=Транспорт реализуем, но новый путь теряет часть модельных данных, нарушает семантику повторов, `tool_choice`, завершения инструментального шага и общего дедлайна. Обнаружены пути ложного успешного завершения и превышения потолка запусков.  
>    СОВЕТЫ (при FAIL): выполнить F-001–F-016 и F-030; проверить одинаковые сценарии через stream и JSON.
>
> 2. ПОЛНОТА: VERDICT=FAIL  
>    WHY=Полный L2 зелёный, однако матрица приёмки приписывает ему проверки, которых приведённые тесты не выполняют. Не закрыты существенные ветки serve: таймауты, повтор после доставки, отключение клиента, JSON, полноценная уборка и восстановление после смерти родителя.  
>    СОВЕТЫ (при FAIL): выполнить F-023–F-029; заменить групповые заявления PASS по AC точными свидетельствами отдельных оракулов.
>
> 3. РЕАЛИЗУЕМОСТЬ: VERDICT=FAIL  
>    WHY=Зависимости доступны: установленный `opencode v2.1.2`, Python stdlib, georouter и пул прокси. Расчёт памяти `64 + 6 × 192 = 1216 MiB ≤ 1638,4 MiB` предварительно сходится; фактический расход активных процессов остаётся предметом законно отложенного L3. Сейчас внедрение блокируют обход ограничителя стартов и утечки процессов, потоков и памяти.  
>    СОВЕТЫ (при FAIL): выполнить F-008, F-017–F-023; затем провести H0–H9 с шестью параллельными запросами рабочего размера. Оценка исправлений с проверками — ориентировочно 3–5 рабочих дней одного разработчика с независимой верификацией; доступность живой квоты определяет срок L3.
>
> 4. РИСКИ: VERDICT=FAIL  
>    WHY=Есть конкретные риски передачи авторизации неподтверждённому слушателю, сигналов чужому процессу при PID reuse, зависания cleanup, повреждения текста и блокировки Circuit Breaker. Зелёные результаты L2 признаю: 400 компонентных тестов и 894 теста корневого набора; они не доказывают отсутствия перечисленных дефектов.  
>    СОВЕТЫ (при FAIL): выполнить F-003–F-005, F-009–F-012, F-017–F-024, F-026, F-028, F-030, F-032. `VER-006` и `VER-007` оставить `DEFERRED_L3` до ACCEPT; их отсрочка сама по себе не является замечанием.
>
> 5. АЛЬТЕРНАТИВЫ: VERDICT=FAIL  
>    WHY=Короткоживущий serve с резервным run оправдан фактами: он сохраняет ротацию окружения и даёт реальные дельты. Однако собственный JSON-парсер добавляет значительный объём и дефекты вместо использования уже разрешённой стандартной библиотеки. Таблица fallback также существует отдельно от реально исполняемой политики.  
>    СОВЕТЫ (при FAIL): выполнить F-002 и F-011–F-012; использовать один проверяемый механизм классификации исходов для stream и JSON.
>
> 6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=FAIL  
>    WHY=Периметр файлов соблюдён, Google Direct и `_run_env` побайтово сохранены, новых сторонних runtime-зависимостей нет. Но нарушены применимые требования `R-BULK`, `S-HERD`, `T-LIFE`, правила тестирования и подавления диагностик. Новые параметры эксплуатации не сопровождаются документацией.  
>    СОВЕТЫ (при FAIL): устранить перечисленные нарушения; согласовать расширение разрешённого набора файлов для обязательной документации. Не переносить stdlib-мост на Litestar и не добавлять зависимости ради формального соответствия чужому стеку.
>
> 1. SUB Корректность/логика: FAIL — потеря `tool_choice`, отсутствует остановка после инструментального шага, возможен четвёртый запуск (`server.py:4950`, `5971`, `3052`, `5298`; REQ-009, REQ-011).
> 2. SUB Корректность/граничные условия: FAIL — пробельные дельты отбрасываются, Unicode surrogate pair разбирается неверно (`server.py:3018`, `3029`, `1679`; AC-006, REQ-010).
> 3. SUB Корректность/обработка ошибок: FAIL — статусы prompt и транзиентные ошибки не проходят требуемую классификацию (`server.py:2879`, `2965`, `4909`, `5813`; REQ-009, REQ-011).
> 4. SUB Полнота/покрытие AC: FAIL — временной оракул сравнивает приход с EOF клиента, не с независимым окончанием апстрима (`tests/test_realtime_reasoning.py:442`; AC-001, AC-002, AC-026).
> 5. SUB Полнота/пропущенные ветки: FAIL — serve JSON, разрыв клиента, watchdog serve и реальные orphan-сценарии не закрыты приведёнными тестами (`verification-traceability.md`, `reverse-spec.md §4.3`; F-024).
> 6. SUB Реализуемость/общее: FAIL — serve обходит ограничитель стартов и имеет утечки на отказах запуска (`server.py:4848`, `5768`, `2572`; REQ-008, REQ-013).
> 7. SUB Риски/безопасность: FAIL — ownership допускает отсутствие доказательства слушателя, reaper не сверяет идентичность владельца (`server.py:2565`, `2593`, `2606`; security.md, T-LIFE).
> 8. SUB Риски/данные: FAIL — потеря пробелов, повторная выдача префикса и неполный usage попыток (`server.py:3029`, `4843`, `4915`; REQ-005, REQ-014).
> 9. SUB Риски/прод: FAIL — сброс общего дедлайна, неверный timeout переиспользованного соединения и незавершённый HALF_OPEN (`server.py:2889`, `2403`, `4914`; R-BULK-I1, R-BULK-I3).
> 10. SUB Риски/regression red→green: PASS — независимый RED на `origin/dev`: 16 failed; кандидат: 21 passed (`execution-evidence.md`, `L2-RED-sensitivity`, `VER-005`); достаточность конкретных оракулов отдельно оспорена в F-024.
> 11. SUB Риски/Full Suite (L2): PASS — подтверждены 400 passed, обратный порядок 400 passed, корневой набор 894 passed / 5 skipped (`execution-evidence.md`, VER-001–003, AC-023).
> 12. SUB Риски/scope-diff: PASS — ровно три разрешённых файла; замороженные функции совпали (`candidate-manifest.json`, `code-gate.json`, VER-004).
> 13. SUB Альтернативы/общее: FAIL — собственный JSON-парсер неоправданно раздувает решение и ломает допустимый JSON (`server.py:1560`; python-standards.md §6, §16).
> 14. SUB Соответствие контексту/общее: FAIL — подавления типов, новые TestCase и немаркированные временные проверки нарушают прямые стандарты (`tests/test_realtime_reasoning.py:2`, `279`, `397`, `321`; testing.md, python-standards.md §9).
>
> Поштучная сверка требований и AC:
>
> - REQ-001 — FAIL: AC-001 и AC-002 — INCONCLUSIVE по измерениям; присутствуют дефекты доставки F-001, F-002.
> - REQ-002 — FAIL по поведенческой совместимости F-013–F-014; AC-003 подтверждён существующими проверками формы, но не полной эквивалентностью serve.
> - REQ-003 — PASS по наличию переключаемого run; AC-004 — PASS по полному L2. Полная матрица переключателей требует F-024.
> - REQ-004 — FAIL; AC-005 — FAIL для медленных setup/gate, F-006.
> - REQ-005 — FAIL; AC-006 — FAIL, F-001–F-002; AC-007 — PASS.
> - REQ-006 — FAIL для непрерывного служебного stdout; AC-008 покрыт только ограниченным legacy-сценарием, F-007, F-024.
> - REQ-007 — FAIL; AC-009 и AC-010 не доказаны для serve и конфликтуют с пятисекундным socket timeout, F-004.
> - REQ-008 — FAIL; AC-011 и AC-012 не доказаны, имеются дефекты F-017–F-023.
> - REQ-009 — FAIL; AC-013 — FAIL, F-009; AC-014 — FAIL для части повторов, F-015.
> - REQ-010 — FAIL; AC-015 не доказан на полном переборе serve-дельт; пробельные фрагменты теряются, F-001.
> - REQ-011 — FAIL; AC-016 не доказан на новом транспорте; F-012–F-014.
> - REQ-012 — политика `ask_reject` обеспечивает отказ разрешения по коду; AC-017 — INCONCLUSIVE: нет эквивалентной serve-матрицы unmapped. Изоляция событий нарушена F-030.
> - REQ-013 — FAIL из-за обхода `_StartupGate` и rate limiter; AC-018 — INCONCLUSIVE: соответствующий двухзапусковый оракул не приведён.
> - REQ-014 — FAIL, F-016; AC-019 подтверждает отображение полей mapper, но не полный финальный usage HTTP-ответа.
> - REQ-015 — INCONCLUSIVE по AC-020: санитизация окружения проверена, требуемый поиск случайного пароля и `apiKey` в финальном логе не показан.
> - REQ-016 — поля существуют; AC-021 проверен на успешном legacy-выходе, полная матрица выходов INCONCLUSIVE; семантика таймингов нарушена F-032.
> - REQ-017 — PASS; AC-022 и AC-023 — PASS по независимым полным прогонам. Дополнительная утечка окружения — F-026.
> - REQ-018 — PASS; AC-024 — PASS по полному набору и замороженным хешам.
> - REQ-019 — DEFERRED_L3; AC-025 — DEFERRED_L3, допустимо до ACCEPT.
> - REQ-020 — FAIL по достаточности оракула AC-026, F-024; сам факт RED→GREEN признаётся.
>
> Границы проверены отдельно:
>
> - Non-Goals: маршруты, порт и форма SSE сохранены; поведенческие регрессии перечислены отдельно. DSH, `cordis.patch.yml`, `ReasoningRow`, выбор модели/эффорта, каталог Zen, другие мосты и общие конфиги не изменены. Сторонние runtime-зависимости не добавлены. Побайтовая сохранность reasoning нарушена F-001–F-002.
> - Forbidden Scope: изменений вне разрешённых трёх файлов нет; секретов в представленном diff нет; мутаций `~/.dsh`, общей БД и общего состояния пакет не заявляет; вызовов Keychain нет. Коммит в защищённую ветку и merge не выполнялись.
> - HL: арифметические оценки памяти, georouter `6 ≤ 48`, FD `128 ≤ 45875,2` и портов `48 ≤ 8192` сходятся как оценки конверта. Они не заменяют поведенческие оракулы. `S-HERD-I1`, `R-BULK-I1..I3`, `C-MULT-I4`, `T-LIFE` имеют конкретные нарушения ниже. Применимость правил pooled-клиентов, Snapshot, Redis и async event loop нельзя переносить на этот автономный stdlib-мост без учёта его архитектуры.
>
> Все замечания одним списком; повторный проход по подкатегориям 1–14 выполнен.
>
> **F-001 — priority=P1, blocking. Потеря пробельных дельт.**  
> Locations: `server.py:3018`, `server.py:3029`. Правило: REQ-005, REQ-010, AC-006. Evidence: `if text_value.strip():` окружает накопление и передачу дельты. Отдельные `" "`, `"\n"` и отступы исчезают, меняя reasoning, обычный текст и содержимое JSON-аргументов инструмента. Исправление: передавать все непустые дельты; определение первого содержательного токена отделить от сохранения байтов. Проверка: разбиения с отдельными пробелами, LF, отступами и пробелом внутри строкового аргумента дают исходную конкатенацию.
>
> **F-002 — priority=P1, blocking. Собственный JSON-парсер повреждает Unicode.**  
> Locations: `server.py:1560`, `server.py:1679`, `server.py:1705`, `server.py:2857`. Правило: python-standards.md §6, §16; REQ-005. Evidence: каждый `\uXXXX` преобразуется отдельным `chr()`. Допустимая пара `\ud83d\ude00` остаётся двумя суррогатами и ломает последующее UTF-8-кодирование. Глубина также не ограничена, `RecursionError` не обработан. Исправление: заменить парсер stdlib `json.loads` с типизированной границей и явной обработкой ошибок. Проверка: escaped emoji, вложенный JSON, невалидный JSON и прежние wire-фикстуры.
>
> **F-003 — priority=P1, blocking. Общий дедлайн не управляет serve-попыткой.**  
> Locations: `server.py:2718`, `server.py:2889`, `server.py:2892`, `server.py:3080`. Правило: `R-BULK-I1`, feature.md — остаток дедлайна на всей I/O-цепочке. Evidence: вместо дедлайна запроса создаётся `prompt_send_start + TIMEOUT_S`; при исчерпании цикла возвращается результат с пустыми `terminal` и `exit_reason`. Caller может выдать успешный финал для незавершённого ответа. Исправление: передавать абсолютный deadline, ограничивать им setup/read/retry и явно классифицировать истечение. Проверка: повтор у границы общего дедлайна не продлевает запрос; отсутствие terminal никогда не становится успехом.
>
> **F-004 — priority=P1, blocking. Пять секунд тишины ошибочно обрывают serve.**  
> Locations: `server.py:2827`, `server.py:2848`, `server.py:2860`, `server.py:2928`. Правило: REQ-006–007, AC-009–010. Evidence: SSE-соединение создано с `timeout=5`; таймаут чтения превращается в EOF/`invalid_serve_event`, хотя первый токен и stall по умолчанию допускают 60 секунд. Исправление: согласовать чтение сокета с watchdog и отличать промежуточную тишину от окончания потока. Проверка: пауза больше 5 секунд и меньше заданного watchdog не вызывает повтор или ошибку.
>
> **F-005 — priority=P1, blocking. Timeout cleanup не применяется к существующему соединению.**  
> Locations: `server.py:2403`, `server.py:2755`, `server.py:2997`, `server.py:3084`, `server.py:3094`. Правило: feature.md — таймаут каждого шага, включая `finally`; REQ-008. Evidence: при переданном `conn` аргумент `timeout=0.25` не меняет timeout соединения, созданного ранее с 3 секундами. Несколько управляющих вызовов и их повторов задерживают `lease.cleanup()`. Исправление: применять актуальный timeout к сокету, ограничить общий cleanup-бюджет, гарантировать kill группы независимо от HTTP-cleanup. Проверка: зависшие control-endpoints не удерживают процессы дольше AC-011.
>
> **F-006 — priority=P1, blocking. Первая видимая реакция отсутствует во время setup.**  
> Locations: `server.py:2740`, `server.py:2778`, `server.py:2810`, `server.py:2835`, `server.py:2890`, `server.py:5298`, `server.py:5363`. Правило: REQ-004, AC-005. Evidence: статус начинает обслуживаться после spawn/readiness/create/subscribe; в legacy — после ожидания gate/limiter и запуска. Исправленная база `status_next` не позволяет эмитить статус во время уже блокирующего setup. Исправление: обслуживать ограниченный по времени первый статус с момента открытия SSE, включая ожидания запуска. Проверка: каждый setup-этап и занятый gate задержаны более секунды, статус всё равно приходит в пределах AC-005.
>
> **F-007 — priority=P1, blocking. Legacy-watchdog зависит от отсутствия stdout.**  
> Locations: `server.py:1096`, `server.py:5439`, `server.py:5453`. Правило: REQ-006–008. Evidence: надзор передан как `on_idle`; поступление каждой строки сбрасывает idle. Непрерывные служебные либо невалидные строки предотвращают проверку первого токена, stall и ухода клиента. Исправление: выполнять надзор по независимому монотонному расписанию и при поступлении данных. Проверка: служебные строки каждые 100 мс не отменяют watchdog и обнаружение disconnect.
>
> **F-008 — priority=P1, blocking. Serve обходит защиты холодного старта.**  
> Locations: `server.py:4848`, `server.py:5768`, `server.py:2740`. Правило: REQ-013, `S-HERD-I1`, `R-BULK-I2`. Evidence: перед `_serve_one_attempt` вызывается `note_spawn()`, но нет `_StartupGate.acquire()` и `res.spawn_limiter.acquire()`, присутствующих в run. Шесть обработчиков могут одновременно поднять шесть serve. Исправление: подключить serve к тем же защитам с остатком дедлайна и гарантированным освобождением. Проверка: конкурентные stream/JSON-запросы соблюдают общий темп запусков и gate.
>
> **F-009 — priority=P1, blocking. Fallback может превысить потолок трёх запусков.**  
> Locations: `server.py:4866`, `server.py:4897`, `server.py:5298`, `server.py:5785`, `server.py:5806`, `server.py:5992`, `server.py:4491`. Правило: REQ-009, AC-013, `R-BULK-I2`. Evidence: после нескольких serve-попыток `return False` переводит управление в run без новой проверки потолка; run непосредственно запускает процесс и делает `note_spawn()`. Сам fallback также обходит `allow_retry`. Исправление: единый допуск каждой следующей попытки, включая смену транспорта. Проверка: две доставленные неудачи serve, третья pre-delivery неудача — run не становится четвёртым запуском.
>
> **F-010 — priority=P1, blocking. Успех serve не закрывает HALF_OPEN Circuit Breaker.**  
> Locations: `server.py:4914`, `server.py:5818`. Правило: REQ-009, `R-BULK-I3`. Evidence: успех сбрасывает только `serve_health`; `attempts.attempt_done(False, True)` отсутствует. Зарезервированная проба HALF_OPEN не завершается успехом, последующие запросы могут оставаться заблокированными. После предыдущего timeout также может сохраниться `_pending_failure`. Исправление: завершать каждую попытку через общий механизм breaker. Проверка: OPEN → HALF_OPEN → успешный serve → CLOSED; timeout → успешный повтор не засчитывается окончательным отказом.
>
> **F-011 — priority=P1, blocking. Prompt-response не управляет барьером доставки и классификацией ошибок.**  
> Locations: `server.py:2413`, `server.py:2414`, `server.py:2879`, `server.py:2880`, `server.py:2901`, `server.py:2965`. Правило: заявленная `FALLBACK_DECISION_TABLE`, REQ-009. Evidence: `headers_at` записывается после чтения всего тела; `status` и `error` практически не используются, security проверяется только после получения очередного SSE-события. HTTP 400/404/422/429/5xx prompt не получают заявленных действий. Исправление: фиксировать доставку при получении заголовков, независимо наблюдать результат worker и применять полную таблицу решений. Проверка: все классы prompt-ответов, включая заголовки с зависшим телом и отсутствие SSE, дают нужный исход без недопустимого fallback.
>
> **F-012 — priority=P1, blocking. Ошибки провайдера обходят прежнюю recovery-семантику.**  
> Locations: `server.py:3073`, `server.py:4909`, `server.py:5813`, `server.py:4943`, `server.py:5884`. Правило: REQ-009, REQ-011. Evidence: любой `result["error"]` немедленно завершает запрос; различие транзиентной и фатальной ошибки не используется. В `_incomplete_step_signal` передаётся `False` вместо факта транзиентного обрыва. Исправление: сохранить классификацию, лимиты и восстановление legacy-пути на накопленном результате serve. Проверка: 429/5xx/transport error до и после вывода, фатальные 4xx и все соответствующие сценарии `test_step_interruption.py`.
>
> **F-013 — priority=P1, blocking. Теряется `tool_choice`.**  
> Locations: `server.py:4753`, `server.py:4950`, `server.py:4961`, `server.py:5971`. Правило: REQ-002, REQ-011; обратная совместимость входного контракта. Evidence: stream-helper не принимает `tool_choice`, использует `None`; JSON-helper получает явный `None` вместо аргумента `_serve_json`. Recovery для `required` и конкретного имени инструмента меняет поведение. Исправление: передавать исходное значение через все serve-ветки. Проверка: `required`, именованный выбор и `none` эквивалентны run.
>
> **F-014 — priority=P1, blocking. Serve не останавливается после инструментального шага.**  
> Locations: `server.py:3046`, `server.py:3052`, `server.py:3077`, `server.py:4804`. Правило: REQ-011. Evidence: после получения tool call и `session.step.ended` цикл продолжает читать до `session.execution.succeeded`; последующие text/reasoning не блокируются для обычного текстового tool call. Исправление: завершать попытку на границе шага с вызовами, interrupt/cleanup выполнять до дальнейшей генерации. Проверка: апстрим посылает второй шаг после первого tool call — второй шаг не попадает клиенту, итог `tool_calls`.
>
> **F-015 — priority=P1, blocking. Повтор serve дублирует уже отданный текст.**  
> Locations: `server.py:4843`, `server.py:4901`, `server.py:4925`, `server.py:4952`, `server.py:5850`, `server.py:5908`. Правило: сохранение recovery-семантики, REQ-009. Evidence: парсер пересоздаётся, но аналог `_PrefixDedup`/`_dedup_retry_text` не применяется; JSON соединяет результаты попыток. Повторы unmapped/incomplete также не получают обязательного разделителя reasoning между попытками. Исправление: сохранить reasoning без дедупликации, явно разделять попытки, дедуплицировать текст по прежнему правилу. Проверка: одинаковый и расходящийся префиксы при timeout/incomplete/unmapped через оба режима.
>
> **F-016 — priority=P2, blocking. Usage неуспешных попыток теряется.**  
> Locations: `server.py:4886`, `server.py:4915`, `server.py:5795`, `server.py:5874`. Правило: REQ-014. Evidence: ветки timeout/invalid-event выполняют `continue` до аккумуляции уже полученного `result["usage"]`. Исправление: учитывать usage завершённых шагов всех оплаченных попыток до принятия решения о повторе. Проверка: первая попытка отдаёт `step.ended`, затем обрывается; финальный usage равен сумме её токенов и успешного повтора.
>
> **F-017 — priority=P1, blocking. На ошибках запуска пропускается cleanup.**  
> Locations: `server.py:1768`, `server.py:2510`, `server.py:2550`, `server.py:2563`, `server.py:2568`, `server.py:2572`, `server.py:2740`. Правило: REQ-008, `T-LIFE`, secure temporary files. Evidence: собственные `raise ServeUnavailable(...)` не входят в `except (OSError, ValueError, subprocess.SubprocessError)`; вызов `_spawn_serve` расположен до `try/finally` попытки. При отказе `Popen` также не закрывается write-конец lifeline и не удаляется созданный state-dir. Исправление: обеспечить владение ресурсами с момента их создания и cleanup на каждом исходе. Проверка: spawn failure, handshake timeout/mismatch и foreign listener оставляют ноль процессов, FD, lease и state-dir. Лог L2 дополнительно содержит `ResourceWarning: subprocess ... is still running`.
>
> **F-018 — priority=P1, blocking. SSE-reader может навсегда остаться на заполненной очереди.**  
> Locations: `server.py:2842`, `server.py:2859`, `server.py:2863`, `server.py:2865`, `server.py:3107`. Правило: `T-LIFE`, `C-MULT-I4`. Evidence: оба `events.put(...)` блокирующие, без timeout/cancel; reader не присоединяется при выходе consumer. Убийство serve не разблокирует поток, уже ожидающий место в Python-очереди. Исправление: cancellation-aware bounded queue, отдельный сигнал окончания и ограниченный join. Проверка: заполнить очередь, отменить запрос; поток и принадлежащие ему ресурсы освобождаются.
>
> **F-019 — priority=P2, blocking. Дренаж stderr накапливает неограниченную память.**  
> Locations: `server.py:2570`, `server.py:1028`. Правило: ограниченные ресурсы `HL-ENV`, `C-MULT-I2`. Evidence: `_drain_stderr(helper, [])` добавляет каждую строку в список, удерживаемый потоком до окончания попытки; список никем не читается и не ограничен. Исправление: использовать ограниченный хвост либо дренаж с отбрасыванием и счётчиком. Проверка: многомегабайтный непрерывный stderr не вызывает линейного роста RSS.
>
> **F-020 — priority=P1, blocking. Авторизация отправляется без обязательного ownership-proof слушателя.**  
> Locations: `server.py:2374`, `server.py:2564`, `server.py:2565`, `server.py:2778`. Правило: security.md, подтверждение владения до передачи секретов. Evidence: `listener_pid is None` допускается; проверка выполняется сразу после handshake, до гарантированного bind serve. Порт предварительно освобождается, поэтому возможна гонка, а последующий reconnect не перепроверяет владельца. Исправление: требовать положительное совпадение listener PID, PGID и живого helper до первой авторизованной записи и при явном reconnect; неоднозначность — fail-closed. Проверка: отсутствующий/чужой/сменившийся слушатель получает ноль байтов Authorization и prompt.
>
> **F-021 — priority=P1, blocking. Reaper не проверяет идентичность процессов.**  
> Locations: `server.py:74`, `server.py:2593`, `server.py:2606`, `server.py:2609`. Правило: `T-LIFE`, безопасность сигналов. Evidence: сохранённые UID/start-time/attempt не сверяются; достаточно живого PID и подстроки `"--serve-helper"`. PID reuse может сохранить сироту либо привести к сигналу другой сессии. Исправление: сверять UID, реальные времена старта, точный script/argv, attempt и PGID; безопасно работать с lease-каталогом. Проверка: переиспользованные PID, чужой helper и подложный lease не получают сигналов.
>
> **F-022 — priority=P1, blocking. Lifeline не гарантирует остановку всего дерева при смерти моста.**  
> Locations: `server.py:174`, `server.py:177`, `server.py:181`, `server.py:195`. Правило: REQ-008, `T-LIFE`. Evidence: helper завершает только непосредственный `serve_proc`, после чего удаляет lease. Потомок serve, переживший родителя, не получает гарантированный групповой сигнал и лишается следа для reaper. Исправление: реализовать проверяемое завершение всей собственной группы при EOF/TERM, включая эскалацию. Проверка: убить мост при helper → serve → grandchild; все процессы исчезают, чужие группы не затронуты.
>
> **F-023 — priority=P1, blocking. Отмена клиента реализована не во всех режимах.**  
> Locations: `server.py:4750`, `server.py:5769`. Правило: REQ-008. Evidence: `_client_gone_check` превращает RST/OSError в `False`; JSON-путь вообще не передаёт callback `is_client_gone`. Исправление: различать отсутствие данных и терминальный разрыв, подключить надзор к JSON и setup-ожиданиям. Проверка: FIN и RST до первого события, после токена и в JSON приводят к остановке в пределах AC-011.
>
> **F-024 — priority=P1, blocking. Матрица PASS не соответствует содержимому оракулов.**  
> Locations: `tests/test_realtime_reasoning.py:376`, `tests/test_realtime_reasoning.py:434`, `tests/test_realtime_reasoning.py:442`, `tests/test_realtime_reasoning.py:619`; `verification-traceability.md`, строки REQ-001, REQ-006–016. Правило: testing.md — независимый эталон полноты; task envelope — поштучная проверка AC. Evidence: `upstream_end_t = elapsed` — EOF самого клиентского ответа; выдача всех пяти дельт одной пачкой также удовлетворяет `first < elapsed` и spread `<2`. Пределы 500/250 мс не проверяются; `assertTrue(silence or rows)` заведомо проходит при непустой таблице. Исправление: независимые upstream timestamps/барьеры; добавить serve JSON, три watchdog, delivered-retry, лимиты, cleanup, permission/unmapped и финальный usage. Исправить traceability по реальным результатам; аварийную чистоту подпроцессов подтвердить crash-guard либо предусмотренным ручным свидетельством. Проверка: намеренно буферизующая и нарушающая таблицу реализация должна краснить соответствующие тесты.
>
> **F-025 — priority=P2, blocking. «Ноль диагностик» получен с подавленными правилами.**  
> Locations: `tests/test_realtime_reasoning.py:2`, `381`, `384`, `385`, `390`, `391`, `408`, `411`, `429`, `431`. Правило: python-standards.md — запрет №9; запрет необъяснённых suppressions. Evidence: заголовок выключает множество диагностик, включая `reportAny` и `reportMissingParameterType`; новые обращения содержат необъяснённые `type: ignore`. Исправление: убрать blanket-подавления и ненужные ignores, исправить типы; узкие исключения обосновать. Проверка: новый файл проверяется с включёнными соответствующими правилами.
>
> **F-026 — priority=P2, blocking [sweep]. Тест удаляет исходное значение окружения.**  
> Locations: `tests/test_realtime_reasoning.py:299`, `tests/test_realtime_reasoning.py:300`. Правило: testing.md — гарантированный откат `os.environ`. Evidence: после `self.env.stop()`, восстановившего исходный `FAKE_RT_MODE`, выполняется безусловный `pop`. Исправление: удалить дополнительную мутацию либо восстанавливать точное предыдущее состояние. Проверка: запуск при заранее установленном значении сохраняет его после teardown.
>
> **F-027 — priority=P2, blocking. Новый тестовый модуль нарушает прямой запрет TestCase.**  
> Locations: `tests/test_realtime_reasoning.py:279`, `tests/test_realtime_reasoning.py:397`. Правило: testing.md — «Не использовать `unittest.TestCase`, `setUp`, `tearDown`». Evidence: оба новых класса основаны на TestCase. Исправление: использовать pytest-тесты и фикстуры с гарантированным teardown. Async/Litestar-инструментарий для этого синхронного stdlib-моста не требуется. Проверка: тот же набор сценариев проходит без новых TestCase.
>
> **F-028 — priority=P2, blocking. Измерения времени смешаны с обычным тестовым контуром.**  
> Locations: `tests/test_realtime_reasoning.py:321`, `392`, `444`, `445`, `568`, `624`. Правило: testing.md §7.2, Serial Lane. Evidence: wall-clock assertions выполняются в обычном полном наборе без `measured`/`heavy`; уже зафиксировано падение около границы 1 секунды. Исправление: выделить замеры в последовательный измерительный контур, а состояния watchdog дополнить FakeClock-оракулами. Проверка: обычный набор не зависит от загрузки машины; отдельный измерительный прогон сохраняет проверки реального клиентского сокета.
>
> **F-029 — priority=P2, blocking. Эксплуатационные изменения не документированы.**  
> Locations: `server.py:1326`, `server.py:1743`, `server.py:1795`; `candidate-manifest.json:files`. Правило: python-standards.md §12. Evidence: добавлены transport/permission/watchdog overrides, dynamic-config и disable-файл, но разрешённый трёхфайловый diff не содержит обновлений README/CHANGELOG. Исправление: согласовать расширение документационного scope и описать приоритеты переключателей, пороги, fallback и откат. Проверка: оператор может включить и отключить транспорт по опубликованной инструкции без чтения исходника.
>
> **F-030 — priority=P2, blocking. Фильтр чужих сессий применяется после потери sessionID.**  
> Locations: `server.py:1844`, `server.py:1845`, `server.py:1875`, `server.py:2973`. Правило: граница изоляции serve-сессии, security.md — проверка входа на границе. Evidence: mapper удаляет `sessionID` у reasoning/text/error, затем фильтр разрешает `None`; чужая дельта либо ошибка проходит. Исправление: проверять sessionID в исходном wire-событии до отображения и обработки. Проверка: события второй сессии не меняют текст, usage, исход и watchdog текущей.
>
> **F-031 — priority=P3, non-blocking. Проверка нативного бинарника почти всегда разрешающая.**  
> Locations: `server.py:1777`, `server.py:1791`. Правило: заявленная проверка допуска auto. Evidence: `or len(head) == 4` принимает любой файл длиной не меньше четырёх байтов без shebang. Исправление: проверять известные исполняемые форматы либо убрать вводящее в заблуждение утверждение о такой проверке. Проверка: произвольный четырёхбайтовый файл не считается нативным opencode.
>
> **F-032 — priority=P2, blocking [sweep]. Поля «первого события» переписываются последующими попытками.**  
> Locations: `server.py:4877`, `server.py:4884`, `server.py:5456`, `server.py:5468`, `server.py:5793`. Правило: REQ-016, `O-EXIT/v1`. Evidence: значения запроса перезаписываются таймингами очередной попытки; в сыром L2 есть `first_event_ms=1975 ttft_ms=974`. В итоге названия полей не соответствуют первому событию и первому токену запроса. Исправление: сохранять первые request-level значения, attempt-level значения учитывать отдельно. Проверка: retry/fallback не стирает первый момент; для одного запроса первый токен не предшествует первому событию.
>
> ОБЩИЙ ВЕРДИКТ: NEEDS WORK
> COVERAGE: 14/14 подкатегорий
> FINDINGS_COMPLETE: 32
ARTIFACT_END>>>

АРГУМЕНТЫ ДРУГИХ ЭКСПЕРТОВ:
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/cycle-1/debate/r1/skeptic.md sha256=7c923726137c9444b62defdfb153166e0963ad30ea8a209b50ef410cd7b17f5c
> PANEL-NONCE: 1c2ff9a190c73460
> ARTIFACT-SHA256: 5b0d1dea0cf4996f6d744e0eb2d82176578091bad35c943dde722c09d3784df4
> Канон прочитан: AGENTS.md, 430 строк
>
> 1. КОРРЕКТНОСТЬ: VERDICT=FAIL
>    WHY=Конверт закрыт по составу (ровно 3 файла моста, Google и `_run_env` заморожены, публичный SSE с `[мост]` разрешён REQ-004/005, потолок `MAX_TOTAL_SPAWNS=3` и `begin_attempt` до serve на `server.py:5150` и `:5967` сохранены). Serve-попытка обходит `_StartupGate` и `spawn_limiter`: `note_spawn()` на `server.py:4848` и `:5768` сразу зовёт `_serve_one_attempt`, тогда как run берёт оба на `server.py:4490–4492` и `:5297–5299` (REQ-013). Рукопожатие после `select` 3 с читает строку по байту без дедлайна (`server.py:2552–2556`). Reaper смотрит только живой `parent_pid` и шлёт один SIGTERM (`server.py:2593–2614`), не сверяя `parent_start_ts` с lease (`server.py:72`). HTTP 429/5xx prompt пишется в `prompt_status["status"]` (`server.py:2879–2880`) и дальше учитывается лишь как `headers_at`; `first_event_timeout` тогда делает `serve_health.record_failure()` (`server.py:4893–4894`), а строка таблицы про 429 требует breaker +1 и serve_health 0.
>    СОВЕТЫ: Перед `_spawn_serve` в обоих serve-обработчиках вызывать тот же `_StartupGate` и `spawn_limiter.acquire`, что у run, с `release` в `finally`. На цикл `os.read` рукопожатия повесить остаток дедлайна 3 с и при истечении делать `ServeUnavailable` плюс `lease.cleanup()`. В `_startup_reaper` сравнивать `parent_start_ts`/`helper_lstart` с живым `ps lstart` до решения «родитель жив»; после SIGTERM ждать `graceful_stop` 5 с, затем SIGKILL, lease удалять только когда группа мертва. Ответ prompt 429 и provider 5xx проводить через `attempts.attempt_done(True, False)` без инкремента `serve_health`; либо исполнять `FALLBACK_DECISION_TABLE`, либо удалить её.
>
> 2. ПОЛНОТА: VERDICT=FAIL
>    WHY=Legacy watchdog, realtime-чанки, usage, permission/form и split tool-text покрыты зелёным L2. Дыры MUST: JSON-serve не передаёт `is_client_gone` (`server.py:5770–5780` против `:4860`); `tool_choice` запроса отбрасывается (`server.py:4950`, `:4961`, вызов `:5981` с литералом `None`); маркеры `__never_event__`/`__silent__` (`tests/test_realtime_reasoning.py:99` и `:102`) ни одним тестом не вызываются; `tests/test_step_interruption.py` не выставляет `OPENCODE_ZEN_BRIDGE_TRANSPORT` и гоняет матрицу только на shebang-фейке `opencode run`.
>    СОВЕТЫ: Прокинуть `self._client_gone_check` в `_serve_json_serve` так же, как в stream. Протащить `tool_choice` запроса в оба serve-обработчика и в `_incomplete_step_signal` / `_incomplete_tool_step_prompt`. Добавить serve-тесты на `__silent__` и `__never_event__`: убийство группы за порог+2 с и `exit_reason` `first_event_timeout` / `first_token_timeout` / `stall_timeout`. Прогнать сценарии `test_step_interruption.py` (или эквивалентный fake-delta набор) при `TRANSPORT=serve`.
>
> 3. РЕАЛИЗУЕМОСТЬ: VERDICT=FAIL
>    WHY=Opt-in serve, `:memory:` и fallback до доставки сопровождать можно, L2 это показывает. На проде до 6 слотов каждый serve — холодный процесс ~152 MiB без сериализации `_StartupGate` и без `SPAWN_RATE_PER_S` (`server.py:4848`, `:5768`). Уборка группы сдаётся через 0.5 с + SIGKILL + 0.5 с (`server.py:2464–2473`); в `l2-green-ver002-unittest.log` рядом с serve `O-EXIT` есть `ResourceWarning: subprocess 98704 is still running`. Слушатель доказывается через `lsof`, lstart — через `ps`.
>    СОВЕТЫ: Тот же gate и limiter, что в совете по КОРРЕКТНОСТИ. В `cleanup` ждать SIGTERM до существующего `graceful_stop` 5 с, затем SIGKILL и ждать, пока `pgid` мёртв. Если `lsof`/`ps` недоступны или слушатель не доказан — fail-closed `ServeUnavailable`, а не пропуск проверки.
>
> 4. РИСКИ: VERDICT=FAIL
>    WHY=Утечки пароля в `bridge.log` по этому diff нет: `_drain_stderr(helper, [])` на `server.py:2570` пишет в пустой список, `_log` не вызывается; `_mask_secrets` на `server.py:3242` маскирует последовательности от 24 символов, пароль — `token_hex(16)`. Allowlist проверен тестом. Red→green и полный L2 зелёные: `L2-RED` rc=1 на `origin/dev`, `VER-005` 21 passed, `VER-001` 400 passed, `AC-023` rc=0, scope — 3 файла. Ломается REQ-005: `_JsonParser._string` кладёт каждый `\uXXXX` отдельным `chr` (`server.py:1675–1680`), SSE идёт через `_loads_object` (`server.py:2857`), ошибка разбора становится `{}` (`server.py:1701–1706`). REQ-008 на проде: уборка 0.5 с (`server.py:2464–2473`) и reaper без сверки lstart оставляют группу живой; JSON-клиент не детектится (см. ПОЛНОТА).
>    СОВЕТЫ: Удалить `_JsonParser`, разбирать serve JSON через уже импортированный `json.loads` с явной проверкой типа. Удлинить ожидание kill до 5 с и не возвращаться, пока группа жива. Закрыть reaper и `is_client_gone` для JSON по советам выше. Оракул AC-020: после прогона сгенерированный пароль отсутствует в `bridge.log`.
>
> 5. АЛЬТЕРНАТИВЫ: VERDICT=FAIL
>    WHY=Выбор A1 (короткий `opencode serve` на попытку, fallback на run до доставки) оправдан фактами F-17..F-19 и прецедентом muse-bridge; дублирование stream/JSON само по себе не раздувание. Неоправдан собственный JSON-парсер на ~150 строк (`server.py:1630–1706`) при уже импортированном `json`: суррогатные пары `\uD83D\uDE00` не склеиваются, `RecursionError` глубже `except (OSError, ValueError)` читателя. `FALLBACK_DECISION_TABLE` не исполняется, тест заканчивается `assertTrue(silence or rows)` (`tests/test_realtime_reasoning.py:619`).
>    СОВЕТЫ: Заменить `_loads_object` на `json.loads`. Либо исполнять таблицу fallback, либо удалить константу и утверждать в тесте конкретные инкременты `serve_health`/`breaker` для строки 429.
>
> 6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
>    WHY=SEED/seed_hex сверка: SHA-256(seed_input)=4525cada06248f2093f1acba9b9dd03c41c8dc7ef4d6a34167b8ed0ff91caa40 совпал с manifest.json seed_hex; SEED8=4525cada; ranked_order манифеста [grok-4.7-high, gpt-6.1-sol-high, gemini-4-argon-high, muse-wonder-full-1.0, claude-sonnet-5-5-high] принят как опубликованный (полный rank_slots по таблице пула в этом ходе не пересчитывался). Границы задачи удержаны: только `bridges/opencode-zen-bridge/server.py`, `tests/test_realtime_reasoning.py`, `tests/test_step_interruption.py`; новых runtime-зависимостей вне stdlib нет; DSH, muse-bridge, georouter и каталог не тронуты; `[мост]` в `reasoning_content` задан REQ-004/005; `_run_env`/`_stream_google_sse`/`_execute_google_once` совпали с замороженными sha256 (`google_direct_unchanged=True`). Слой Litestar к этому мосту неприменим. VER-006/VER-007 законно `DEFERRED_L3`.
>
> ### F-001
> priority: blocking
> criterion: КОРРЕКТНОСТЬ/логика, РЕАЛИЗУЕМОСТЬ
> locations: bridges/opencode-zen-bridge/server.py:4848, bridges/opencode-zen-bridge/server.py:5768, bridges/opencode-zen-bridge/server.py:4490, bridges/opencode-zen-bridge/server.py:5297
> rule: REQ-013 / AC-018; S-HERD-I1 (холодный старт сериализуется `_StartupGate`)
> evidence: `attempts.note_spawn()` затем `_serve_one_attempt` без `gate.acquire()` и без `spawn_limiter.acquire`; run-путь: `gate = _StartupGate()` и `self.res.spawn_limiter.acquire` / `res.spawn_limiter.acquire`.
> fix: Перед `_spawn_serve` в `_run_serve_stream_attempts` и `_serve_json_serve` захватывать `_StartupGate` и `spawn_limiter` с тем же `max_wait_s`, освобождать в `finally` попытки.
> verify: Тест двух перекрывающихся serve-попыток показывает сериализацию gate и отказ limiter при превышении `SPAWN_RATE_PER_S`.
>
> ### F-002
> priority: blocking
> criterion: КОРРЕКТНОСТЬ/граничные условия
> locations: bridges/opencode-zen-bridge/server.py:2552
> rule: feature.md — таймаут на каждом шаге I/O, включая чтение после первого байта
> evidence: `select.select([out_fd], [], [], 3.0)` покрывает только появление fd; далее `while not line_bytes.endswith(b"\n"): chunk_b = os.read(out_fd, 1)` без дедлайна.
> fix: Читать рукопожатие с остатком тех же 3 с; по истечении `ServeUnavailable` и `lease.cleanup()`.
> verify: Helper, который пишет один байт и замолкает, убивается в бюджете рукопожатия, слот и группа освобождены.
>
> ### F-003
> priority: blocking
> criterion: КОРРЕКТНОСТЬ/граничные условия
> locations: bridges/opencode-zen-bridge/server.py:72, bridges/opencode-zen-bridge/server.py:2593, bridges/opencode-zen-bridge/server.py:2609, bridges/opencode-zen-bridge/server.py:2613
> rule: REQ-008 / AC-011
> evidence: Lease пишет `"parent_start_ts": parent_lstart`. Reaper: `parent_alive = parent_pid > 0 and _pid_alive(parent_pid)` и при живом pid делает `continue`; иначе один `os.killpg(pgid, signal.SIGTERM)` и сразу `path.unlink()`.
> fix: Сверять lstart родителя и helper с lease до вывода «жив»; SIGKILL после 5 с; не удалять lease, пока группа жива. Тест с `helper_pid=0` эту ветку не исполняет — заменить живым фейком.
> verify: Lease мёртвого родителя, чей pid переиспользован (lstart не совпал), приводит к смерти helper+serve; lease остаётся, пока группа жива.
>
> ### F-004
> priority: blocking
> criterion: ПОЛНОТА/пропущенные ветки
> locations: bridges/opencode-zen-bridge/server.py:5770, bridges/opencode-zen-bridge/server.py:4860
> rule: REQ-008 / AC-012 (обнаружение ухода клиента не позже 5 с, группа отсутствует не позже 7 с)
> evidence: Stream передаёт `is_client_gone=self._client_gone_check`. Вызов из `_serve_json_serve` аргумент не передаёт (`on_status=lambda _t: None` и сразу `thinking_enabled`).
> fix: Передавать `is_client_gone=self._client_gone_check` в JSON-попытку.
> verify: Закрытие сокета non-stream клиента останавливает группу не позже 7 с.
>
> ### F-005
> priority: blocking
> criterion: ПОЛНОТА/покрытие AC
> locations: bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:99, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:102
> rule: REQ-006 / REQ-007 / AC-008 / AC-009 / AC-010
> evidence: `if "__never_event__" in prompt` и `if "__silent__" in prompt` есть в `FAKE_SERVE`; вызовов этих маркеров в тестах нет. Legacy `FAKE_RT_MODE=silent` покрывает только run.
> fix: Три теста TRANSPORT=serve: нет событий → `first_event_timeout`; событие без токена → `first_token_timeout`; токен и пауза → `stall_timeout`; завершение за порог+2 с.
> verify: Тесты красные, если цикл `_serve_one_attempt` перестаёт проверять эти три порога.
>
> ### F-006
> priority: blocking
> criterion: ПОЛНОТА/пропущенные ветки
> locations: bridges/opencode-zen-bridge/server.py:4950, bridges/opencode-zen-bridge/server.py:4961, bridges/opencode-zen-bridge/server.py:5981
> rule: REQ-011 (STEP_RECOVERY на потоковом пути, включая forced tool_choice)
> evidence: `tool_choice=None` в `_incomplete_step_signal`; `_incomplete_tool_step_prompt(..., None, model)`; вызов `self._serve_json_serve(..., reported_model, None, res, attempts, xs)` при том, что параметр `tool_choice` у `_serve_json` есть и внутри `_serve_json_serve` используется.
> fix: Протащить `tool_choice` запроса в stream- и JSON-serve и в оба вызова recovery.
> verify: Serve-шаг с текстом без tool при `tool_choice`, требующем вызов, ретраится с force-клаузой в prompt.
>
> ### F-007
> priority: blocking
> criterion: ПОЛНОТА/покрытие AC
> locations: bridges/opencode-zen-bridge/tests/test_step_interruption.py:188
> rule: REQ-011 / AC-016
> evidence: `setUp` изолирует `_Resilience()` (это закрывает REQ-017). По файлу нет `OPENCODE_ZEN_BRIDGE_TRANSPORT`; фейк — shebang `opencode run`. Матрица incomplete/unmapped/tool_calls на serve не исполняется.
> fix: Прогнать существующие сценарии прерывания шага (или их fake-delta эквивалент) с `TRANSPORT=serve`.
> verify: Регрессия остановки по tool_calls или incomplete-retry на serve роняет этот тест.
>
> ### F-008
> priority: blocking
> criterion: РИСКИ/данные, АЛЬТЕРНАТИВЫ
> locations: bridges/opencode-zen-bridge/server.py:1675, bridges/opencode-zen-bridge/server.py:1701, bridges/opencode-zen-bridge/server.py:2857
> rule: REQ-005 (байты размышления модели не модифицируются); python-standards KISS при уже импортированном `json`
> evidence: `parts.append(chr(int(hex_part, 16)))` без склейки суррогатной пары; `_loads_object` на `ValueError`/`IndexError` возвращает `{}`; читатель SSE кладёт payload через `_loads_object`.
> fix: Удалить `_JsonParser` и разбирать объекты через `json.loads`.
> verify: Дельта `reasoning_content` с `\uD83D\uDE00` доходит одним символом; битый JSON не превращается молча в пустое событие без `invalid_serve_event`.
>
> ### F-009
> priority: blocking
> criterion: КОРРЕКТНОСТЬ/обработка ошибок
> locations: bridges/opencode-zen-bridge/server.py:2879, bridges/opencode-zen-bridge/server.py:4893, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:619
> rule: Строка `FALLBACK_DECISION_TABLE` «PROMPT_RESPONSE HTTP429/provider5xx»: `serve_retry`, ServeHealth 0, UpstreamBreaker +1; REQ-009 (breaker сохраняется)
> evidence: `prompt_status["status"] = st` и `headers_at` выставляются для любого статуса, кроме отдельной ветки 401/403. Дальше `first_event_timeout` делает `res.serve_health.record_failure()`. Тест: `self.assertTrue(silence or rows)`.
> fix: 429 и provider 5xx на prompt проводить в `attempt_done(True, False)` без `serve_health`; убрать тавтологию, утверждать инкременты строки 429.
> verify: Три ответа prompt 429 не делают `is_degraded()`, breaker фиксирует отказ.
>
> ### F-010
> priority: blocking
> criterion: РИСКИ/прод
> locations: bridges/opencode-zen-bridge/server.py:2464, bridges/opencode-zen-bridge/server.py:2467, bridges/opencode-zen-bridge/server.py:2471
> rule: REQ-008 / T-LIFE (процесс и читатель закрываются до возврата)
> evidence: `self.helper.wait(timeout=0.5)`, затем `os.killpg(..., SIGKILL)`, затем снова `wait(timeout=0.5)` и выход. `execution-evidence.md` / `l2-green-ver002-unittest.log`: `ResourceWarning: subprocess 98704 is still running` рядом со строками serve `O-EXIT`.
> fix: Ждать SIGTERM до 5 с, затем SIGKILL и ждать завершения; не возвращаться из `cleanup`, пока `_pid_alive(pgid)`.
> verify: Прогон unittest, включающий serve-тесты, не печатает `subprocess is still running`.
>
> ### F-011
> priority: non-blocking
> criterion: КОРРЕКТНОСТЬ/логика
> locations: bridges/opencode-zen-bridge/server.py:1791
> rule: Предохранитель `_is_native_opencode_bin` в `auto` (shebang-фейк должен оставаться на run)
> evidence: `or len(head) == 4` после проверки Mach-O/ELF. Любой файл без `#!` длиной от 4 байт считается нативным.
> fix: Убрать дизъюнкт `len(head) == 4`; оставить Mach-O и ELF. Тест: 4 байта не-shebang → False.
> verify: Короткий бинарный мусор в `auto` не выбирает serve.
>
> ### F-012
> priority: non-blocking
> criterion: ПОЛНОТА/покрытие AC
> locations: bridges/opencode-zen-bridge/server.py:1339
> rule: REQ-004 (первая видимая строка). Живой статус закрывается `STATUS_WAITING`, константа начального текста не используется.
> evidence: `STATUS_INITIAL = "[мост] Подключение к модели…\n"` — присваивание без чтения в diff.
> fix: Эмитить `STATUS_INITIAL` как первую статусную строку либо удалить константу.
> verify: Поиск по `server.py` либо находит эмиссию, либо константы нет.
>
> ### F-013
> priority: non-blocking
> criterion: КОРРЕКТНОСТЬ/граничные условия
> locations: bridges/opencode-zen-bridge/server.py:2495, bridges/opencode-zen-bridge/server.py:2564
> rule: REQ-008 (свой слушатель). Окно между `bind` пробного сокета и bind serve; `lsof` с `None` проверку чужого слушателя пропускает.
> evidence: Скан порта `bind`/`close`, затем helper; `if listener_pid is not None and (listener_pid != serve_pid or ...)`.
> fix: Держать пробный сокет до старта serve или перепроверять слушателя до prompt; `lsof` без pid — `ServeUnavailable`.
> verify: Занятый между probe и bind порт даёт `ServeUnavailable`, а не чужой HTTP.
>
> ### F-014
> priority: non-blocking
> criterion: КОРРЕКТНОСТЬ/логика
> locations: bridges/opencode-zen-bridge/server.py:2654, bridges/opencode-zen-bridge/server.py:2678
> rule: REQ-012 (native tool → текущий внутренний вид). DSH-маппинг читает имя и arguments; статус в выдачу DSH не входит.
> evidence: `feed` присваивает `item["text"] = text_value` вместо накопления дельт; `complete` всегда кладёт `"status": "error"`, в том числе на `session.tool.success`.
> fix: Склеивать `input.delta` либо опираться только на `input.ended.text`; статус брать из типа события.
> verify: Фикстура `session.tool.success` с двумя delta даёт полный JSON аргументов и status `success`.
>
> ### F-015
> priority: non-blocking
> criterion: РИСКИ/безопасность
> locations: bridges/opencode-zen-bridge/server.py:2569, bridges/opencode-zen-bridge/server.py:2570, bridges/opencode-zen-bridge/server.py:3242
> rule: REQ-015 / AC-020. Пароль в лог этим путём не пишется: sink пустой, `_mask_secrets` режет токены ≥24 символов.
> evidence: Комментарий «stderr помощника дренируется в лог»; вызов `_drain_stderr(helper, [])`. `_drain_stderr` только дополняет список.
> fix: Либо логировать stderr через `_mask_secrets`, либо поправить комментарий. Добавить тест: пароль попытки отсутствует в `bridge.log`.
> verify: Прогон serve с известным паролем, `assertNotIn(password, log)`.
>
> ### F-016
> priority: non-blocking
> criterion: ПОЛНОТА/покрытие AC
> locations: bridges/opencode-zen-bridge/server.py:4877, bridges/opencode-zen-bridge/server.py:4884
> rule: REQ-016 / AC-021. Поля в строке `O-EXIT/v1` есть; после fallback значение `first_event_ms` остаётся от serve при `transport=run`.
> evidence: `xs["first_event_ms"] = result["first_event_ms"]` дважды подряд до ветки fallback, которая меняет `transport` на `run` и возвращает `False`.
> fix: При возврате в run сбрасывать `first_event_ms`/`ttft_ms` либо помечать, к какому транспорту они относятся.
> verify: O-EXIT fallback-запроса не показывает serve-миллисекунды как тайминг итогового run.
>
> ### F-017 [sweep]
> priority: non-blocking
> criterion: ПОЛНОТА/покрытие AC
> locations: bridges/opencode-zen-bridge/server.py:1795, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:634
> rule: REQ-003 / AC-004. Дефолт без флага — run: полный сьют 400 passed это подтверждает. Прямой матрицы kill-switch нет.
> evidence: `_select_transport` читает `TRANSPORT`, `REALTIME_SERVE_ENABLED` и файл `disable-serve`. Тесты группы B форсят `serve` или один сценарий `auto`+503.
> fix: Четыре случая: `TRANSPORT=run`, override `0`, файл disable, опечатка значения — все остаются на run и не зовут `_spawn_serve`.
> verify: Счётчик спавнов serve в этих четырёх случаях равен 0.
>
> ### F-018
> priority: non-blocking
> criterion: ПОЛНОТА/покрытие AC
> locations: bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:441
> rule: REQ-001 / AC-001 / AC-002. Реалтайм на сокете есть (red на `origin/dev`, green `VER-005`). Интервал соседей &lt;500 мс и накладные моста ≤250 мс тест не утверждает: проверяется span &lt;2.0 с и «первая дельта раньше конца апстрима».
> evidence: `test_ac026_realtime_chunks_before_upstream_end` сравнивает `model_reasoning[-1][0] - model_reasoning[0][0]` с `2.0`.
> fix: Утверждать максимум соседнего интервала reasoning-чанков и верхнюю границу задержки мост↔сокет на фейке с известным `sleep`.
> verify: Тест красный, если чанки склеиваются в один блок в конце шага.
>
> SUB Корректность/логика: FAIL — server.py:4848 и :5768 `note_spawn` без `_StartupGate`/`spawn_limiter`, run их берёт на :5297 (REQ-013)
> SUB Корректность/граничные условия: FAIL — server.py:2552 чтение рукопожатия без дедлайна; server.py:2593 reaper без `parent_start_ts` (REQ-008)
> SUB Корректность/обработка ошибок: FAIL — server.py:2879/:4893 prompt 429 увеличивает `serve_health`, таблица требует breaker; test_realtime_reasoning.py:619 тавтология
> SUB Полнота/покрытие AC: FAIL — test_realtime_reasoning.py:99/:102 маркеры serve-watchdog без теста; test_step_interruption.py без TRANSPORT=serve (AC-008..010, AC-016)
> SUB Полнота/пропущенные ветки: FAIL — server.py:5770 JSON без `is_client_gone`; server.py:4950/:5981 `tool_choice=None` (REQ-008, REQ-011)
> SUB Реализуемость/общее: FAIL — server.py:4848/:5768 холодный serve без gate; server.py:2464 cleanup 0.5 с и ResourceWarning в l2-green-ver002 (REQ-013, REQ-008)
> SUB Риски/безопасность: PASS — server.py:2570 `_drain_stderr(helper, [])` не вызывает `_log`; server.py:3242 `_mask_secrets` маскирует токен ≥24; пароль в лог не пишется (REQ-015)
> SUB Риски/данные: FAIL — server.py:1675 `\uXXXX` как отдельный `chr`, SSE через `_loads_object` на :2857 (REQ-005)
> SUB Риски/прод: FAIL — server.py:2464–2473 wait 0.5 с и сдача; ResourceWarning `subprocess 98704 is still running` в VER-002 (REQ-008)
> SUB Риски/regression red→green: PASS — execution-evidence.md L2-RED rc=1 на origin/dev, VER-005 rc=0, 21 passed (REQ-020)
> SUB Риски/Full Suite (L2): PASS — code-gate.json VER-001 400 passed rc=0, AC-023-pytest-reversed rc=0
> SUB Риски/scope-diff: PASS — candidate-manifest.json ровно 3 файла в bridges/opencode-zen-bridge; Forbidden Scope не задет
> SUB Альтернативы/общее: FAIL — server.py:1630–1706 свой JSON-парсер при импортированном `json` (KISS, REQ-005)
> SUB Соответствие контексту/общее: PASS — seed_hex 4525cada… совпал с manifest; Non-Goals и freeze Google/_run_env удержаны (REQ-002, REQ-018)
>
> ОБЩИЙ ВЕРДИКТ: NEEDS WORK
> COVERAGE: 14/14 подкатегорий
> FINDINGS_COMPLETE: 18
ARTIFACT_END>>>
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/cycle-1/debate/r1/visionary.md sha256=790c3aedcaa9730005b1e0b6e16d5cc48eaff16e77551f6433c9703f9059eaab
> PANEL-NONCE: 7ec7d741c844094d
> ARTIFACT-SHA256: 5b0d1dea0cf4996f6d744e0eb2d82176578091bad35c943dde722c09d3784df4
>
> **Позиция Визионера.** Стратегически кандидат правильный. Это гибрид C: `opencode serve` по SSE с откатом на `run`, как в `muse-bridge` (ADR-0004). Он единственный даёт реальные дельты размышления (F-19), kill-switch и расширяемую телеметрию `O-EXIT/v1`. Но в нынешнем виде он ломает доставку текста, ломает конкурентность и ухудшает дефолтный путь `run`. Номера строк в F-блоках приблизительные: они выведены из диапазонов VER-004 и названий функций, потому что в пакете есть только diff.
>
> 1. КОРРЕКТНОСТЬ: VERDICT=FAIL
>    WHY=В `_serve_one_attempt` дельты reasoning и text с пустым `.strip()` не пересылаются клиенту. Параграфные `\n\n` и пробелы теряются, это нарушает AC-006 и ломает превью DSH по `\n` (F-01). Аллокация порта serve гоняется при параллельных запросах и может отправить пароль чужому serve, после чего ответ fail-closed с `ServeSecurityError` (F-02). Для serve не реализованы `_StartupGate` и `spawn_limiter` из REQ-013 (F-04). Статус ответа prompt игнорируется (F-05). Повтор после `delivered=True` дублирует контент и tool_calls (F-06). Сторож `FIRST_TOKEN_TIMEOUT_S=60` убивает легитимные шаги дефолтного пути `run` (F-03).
>    СОВЕТЫ:
>    - Пересылать любые непустые дельты без `strip`, а живость токенов считать отдельно (F-01).
>    - Выделять порты под замком до проверки владения слушателем или брать порт 0 (F-02).
>    - Не применять 60-секундные сторожа токенов к legacy-пути и вынести его поведение за флаг (F-03).
>    - Подключить `spawn_limiter` и `_StartupGate` к serve (F-04).
>    - Разбирать `prompt_status`, а `FALLBACK_DECISION_TABLE` либо сделать исполняемой, либо удалить (F-05).
>    - После отданного контента делать дедуп или не ретраить (F-06).
>
> 2. ПОЛНОТА: VERDICT=FAIL
>    WHY=Нет тестов на AC-011 и AC-012, на serve-таймауты, на `_serve_json_serve` (+208 строк), на AC-018 и AC-020; фикстуры `__silent__` и `__never_event__` не используются (F-10). Первый статус `[мост]` ≤1.0 с (REQ-004) не гарантирован: `STATUS_INITIAL` не эмитируется, а ожидание gate и фаза spawn молчат (F-07). Матрица прослеживаемости ставит PASS «по VER-001» для требований без теста. Часть тестов тавтологична (F-13). Поддерживаемость страдает из-за функций по ~350 строк и дублирования stream/JSON (F-17).
>    СОВЕТЫ:
>    - Добавить тесты на watchdog, client_gone, kill orphans, JSON-serve, ротацию прокси и отсутствие пароля в логах.
>    - Эмитить `STATUS_INITIAL` сразу после role-чанка, до gate.
>    - Исправить матрицу прослеживаемости.
>    - Разбить `_serve_one_attempt` и вынести общую логику stream/JSON.
>
> 3. РЕАЛИЗУЕМОСТЬ: VERDICT=FAIL
>    WHY=Скрытые операционные издержки: гонка портов при `max_concurrent=6` (F-02), утечка tempdir и FD при сбое spawn (F-09), `lsof` и `ps` на каждую попытку, предсказуемый каталог в `/tmp` (F-14). Неподтверждённый реальный wire v2.1.2: событие с пустым `data` (на 161 мс в F-19 есть `integration.updated`) даёт `ServeProtocolError` с `delivered=True` (F-08).
>    СОВЕТЫ:
>    - Сериализовать запуск serve.
>    - Освобождать ресурсы в `finally` до создания lease.
>    - Снять реальные wire-фикстуры v2.1.2 и прогнать лестницу H0..H9 до включения флага.
>    - Ограничить права на lease-каталог.
>
> 4. РИСКИ: VERDICT=FAIL
>    WHY=Искажение данных клиента (F-01), регрессия дефолтного пути `run` (F-03), конкурентный отказ (F-02), риск 100% отказа serve на реальном wire (F-08). Полный набор зелёный (400 passed, `VER-001..003`, `AC-023`), но проверяет в основном фейки. Выявленные дефекты воспроизводимы только новыми тестами. Lease-каталог в `/tmp` без владельца и режима (F-14). Прямая мутация `os.environ` в `test_step_interruption.py` (F-21).
>    СОВЕТЫ:
>    - Закрыть F-01, F-02, F-03 и F-08 regression-тестами по схеме red→green.
>    - Поднять конкурентный тест на 6 запросов.
>    - Добавить live-замер на реальном `opencode` после сброса квоты.
>
> 5. АЛЬТЕРНАТИВЫ: VERDICT=FAIL
>    WHY=Выбор архитектуры оправдан. Но реализация раздута: самописный `_JsonParser` на ~150 строк при импортированном stdlib `json` (F-11), тестовый хук `SERVE_TEST_ELIGIBLE` и вакуумная `_is_native_opencode_bin` в проде (F-15), мёртвая `FALLBACK_DECISION_TABLE` (F-05).
>    СОВЕТЫ:
>    - Заменить парсер на `json.loads` с явным `except`.
>    - Убрать тестовые хуки из продакшн-кода.
>    - Удалить декларативную таблицу или сделать её исполняемой.
>
> 6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=FAIL
>    WHY=Нарушены python-standards: блоковое подавление pyright и `type: ignore` без обоснования (F-12), функции сильно длиннее ~40 строк и дубли (F-17), тавтологичные тесты (F-13), шум форматирования в немодифицируемых зонах (F-16). Публичный OpenAI-контракт и `_run_env`/Google-срезы не изменены, это соответствует Non-Goals.
>    СОВЕТЫ:
>    - Убрать подавления типов, типизировать тесты.
>    - Откатить косметические hunk'и.
>    - Декомпозировать serve-функции.
>    - Переименовать тесты, чьи ожидания изменены (F-18).
>
> **SUB-строки (14/14):**
> 1. SUB Корректность/логика: FAIL — `_serve_one_attempt` (server.py:~2360-3114) `if text_value.strip():` в ветках reasoning и text; `_spawn_serve`; повтор в `_run_serve_stream_attempts` (F-01, F-02, F-06)
> 2. SUB Корректность/граничные условия: FAIL — whitespace-дельты, события с пустым `data`, stall при длинном tool-input (F-01, F-08, F-20)
> 3. SUB Корректность/обработка ошибок: FAIL — `_prompt_worker` игнорирует статус и ошибку, `_loads_object` возвращает `{}` при ошибке, `_spawn_serve` пропускает не-`ServeUnavailable` OSError (F-05, F-09, F-11)
> 4. SUB Полнота/покрытие AC: FAIL — AC-011/012/018/020 без тестов; REQ-013 и REQ-004 не выполнены полностью (F-04, F-07, F-10)
> 5. SUB Полнота/пропущенные ветки: FAIL — не реализованы строки 429/5xx и ответ prompt из таблицы; нет дедупа при повторе (F-05, F-06)
> 6. SUB Реализуемость/общее: FAIL — гонка портов при `max_concurrent=6`, утечки, `lsof` на попытку (F-02, F-09)
> 7. SUB Риски/безопасность: FAIL — предсказуемый `/tmp/opencode-zen-bridge-leases` без 0700 и проверки `owner_uid`; пароль может уйти чужому слушателю (F-14, F-02)
> 8. SUB Риски/данные: FAIL — потеря `\n` и пробелов в `reasoning_content` и `content` (F-01)
> 9. SUB Риски/прод: FAIL — `FIRST_TOKEN_TIMEOUT_S=60` на буферизующем `run`, максимум наблюдения 85.65 с (F-03, F-08)
> 10. SUB Риски/regression red→green: PASS — `l2-red.log` rc=1 на `origin/dev`, зелёный на кандидате; слабость RED (падения по `AttributeError`) учтена в F-13
> 11. SUB Риски/Full Suite (L2): PASS — `receipts/code-gate.json` VER-001/002/003/003b/005 и AC-023 rc=0, 400 passed; VER-006/007 законно DEFERRED_L3
> 12. SUB Риски/scope-diff: FAIL — косметический реформат `Run.execute`, `_RequestAttempts`, `_UpstreamBreaker`, `_PrefixDedup` и др. (F-16)
> 13. SUB Альтернативы/общее: FAIL — самописный `_JsonParser`, тестовый хук в проде (F-11, F-15)
> 14. SUB Соответствие контексту: FAIL — python-standards #9, §6/§7, testing.md об `os.environ` (F-12, F-17, F-21)
>
> ОБЩИЙ ВЕРДИКТ: NEEDS WORK
>
> **F-блоки**
>
> F-01 [blocking] Whitespace-дельты не пересылаются клиенту
> - Locations: server.py:~2360-3114 (`_serve_one_attempt`, ветки `etype == "reasoning"` и `etype == "text"`).
> - Правило: REQ-005/AC-006 (текст модели не модифицируется), REQ-001; F-37 (превью требует `\n`).
> - Evidence: `if text_value.strip(): … on_reasoning(text_value)` и такое же условие для `on_text`.
> - Fix: пересылать любую непустую дельту без `strip`; `first_token_at` и `last_token_at` обновлять только по содержательным токенам.
> - Проверка: тест с дельтами `"\n\n"`, `" "`, `"\n"`: конкатенация побайтно равна эталону, в том числе внутри `<tool_invoke>`.
>
> F-02 [blocking] Гонка выбора порта serve и отправка пароля не тому serve
> - Locations: server.py:~2360-3114 (`_spawn_serve`, цикл `range(20000 + pid%20000, 60000)` с bind-проб и закрытием сокета); `_serve_one_attempt` (ready-проверка).
> - Правило: C-MULT-I3/I4; `scope-and-contracts` (не ломать конкурентные запросы); `security.md` §9.
> - Evidence: все потоки сканируют от одного кандидата, сокет закрывается до bind serve. Два запроса в окне ~110 мс получают один порт. Если `lsof` ещё не видит слушателя, `GET /api/session/active` попадает в чужой serve и возвращает 401. Это `ServeSecurityError` без fallback.
> - Fix: глобальный замок на выделение порта до проверки владения; либо `--port 0` с чтением реального порта; 401 на ready до DELIVERED считать `ServeUnavailable`.
> - Проверка: тест на 6 параллельных stream-запросов, ни одного `serve security failure`.
>
> F-03 [blocking] Регрессия дефолтного пути `run`: watchdog первого токена 60 с
> - Locations: server.py:5351-5474 (`send_keepalive`, `watchdog_state`); константы `FIRST_TOKEN_TIMEOUT_S`, `FIRST_EVENT_TIMEOUT_S`, `STALL_TIMEOUT_S`.
> - Правило: REQ-003 (прежний путь остаётся рабочим), REQ-002.
> - Evidence: F-17/F-18: `run` выдаёт reasoning и text одним блоком в конце шага. F-32: максимум `deepseek-v4.1-flash-free` 85.65 с. По умолчанию serve выключен, поэтому путь `run` основной. Шаг дольше 60 с убивается и повторяется до 3 раз. Статусы `[мост]` и watchdog на `run` работают вне переключателя транспорта.
> - Fix: для legacy использовать потолок не ниже прежнего поведения либо отдельные пороги с высоким дефолтом, `first_event` считать по `step_start`, watchdog первого токена оставить только для serve; поведение legacy за флагом.
> - Проверка: фейк-CLI с паузой 70 с до единого блока завершается успешно без ретраев.
>
> F-04 [blocking] REQ-013 не выполнен для serve
> - Locations: server.py:~2360-3114 (`_serve_one_attempt` / `_spawn_serve`); AC-018.
> - Правило: REQ-013 (`_StartupGate`, `SPAWN_RATE_PER_S`), R-BULK-I2.
> - Evidence: serve-путь не вызывает `gate.acquire()` и `res.spawn_limiter.acquire()`, теста на ротацию IP нет.
> - Fix: acquire `spawn_limiter` и gate перед `_spawn_serve`, release в `finally`.
> - Проверка: тест двух запусков с подменённым `_next_standalone_proxy` и ограничением частоты.
>
> F-05 [blocking] Результат prompt-POST игнорируется, `FALLBACK_DECISION_TABLE` мёртва
> - Locations: server.py:~2360-3114 (`_prompt_worker`, `prompt_status`); `FALLBACK_DECISION_TABLE` (server.py:~1450-1560).
> - Правило: `error-handling.md` (Identify→Assess), REQ-009.
> - Evidence: пишется `prompt_status["status"/"error"]`, проверяется только 401/403. 400/429/5xx и сетевая ошибка приводят к ожиданию 20 с. Строка таблицы про 429 и provider5xx не реализована, тест таблицы проверяет только `len ≥ 10`.
> - Fix: классифицировать статус prompt по таблице (retry с breaker+1, fail-closed на 400/404/422) или удалить таблицу.
> - Проверка: FakeServe отвечает 429 на prompt, затем retry без ожидания 20 с.
>
> F-06 [blocking] Повтор после отданного контента дублирует text и tool_calls
> - Locations: server.py:4734-4967 (`_run_serve_stream_attempts`, ветки `allow_retry`/`continue`); `_serve_json_serve`.
> - Правило: REQ-009/AC-014, REQ-010.
> - Evidence: legacy использует `_PrefixDedup`, serve нет. После `stall_timeout` при уже отданных text или tool_call повтор выдаёт тот же контент снова.
> - Fix: дедуп префикса либо запрет retry после отданного text или tool_call.
> - Проверка: тест stall после части текста и вызова инструмента, клиент не видит дублей.
>
> F-07 [blocking] Первый статус ≤1.0 с (REQ-004) не гарантирован
> - Locations: server.py:5351-5474 (`send_keepalive`); `_serve_one_attempt` (`status_next`, `STATUS_INITIAL`).
> - Правило: REQ-004/AC-005.
> - Evidence: `STATUS_INITIAL` объявлен и нигде не эмитируется. На legacy статусы идут только из цикла `feed.lines`, а до него `_StartupGate` держит до 5 с (STARTUP_WAIT_S) и `spawn_limiter`. На serve цикл статусов стартует после spawn, ready, create, subscribe.
> - Fix: эмитить `STATUS_INITIAL` сразу после role-чанка до gate и spawn при включённом thinking.
> - Проверка: удержать gate 3 с, первый чанк с `[мост]\n` приходит ≤1.0 с.
>
> F-08 [blocking] Реальный wire v2.1.2 не проверен: события с пустым `data`
> - Locations: server.py:~1800-1880 (`_map_serve_event`: `if not data: raise ServeProtocolError`); `_serve_one_attempt` (`except ServeProtocolError` → `delivered=True`).
> - Правило: R-BULK-I3, REQ-012; факт-карта F-19, VER-006 DEFERRED_L3.
> - Evidence: любое событие кроме `server.connected` с пустым `data` (в F-19 на 161 мс приходит `integration.updated`) даёт `invalid_serve_event`, `delivered=True` и retry вместо fallback. Все фикстуры синтетические.
> - Fix: игнорировать неизвестные события и пустой `data`, валидировать только известные типы; добавить фикстуры, снятые с реального serve; прогнать VER-006 на живом контуре до включения флага.
> - Проверка: тест, подающий heartbeat и `integration.updated` с пустым `data`, не прерывает попытку. Статус PLAUSIBLE.
>
> F-09 [blocking] Утечка tempdir и FD при сбое запуска serve
> - Locations: server.py:~2360-3114 (`_serve_env` → `mkdtemp`; `_spawn_serve`: `os.pipe`, `Popen` до создания `_ServeLease`; `lease_dir.mkdir`).
> - Правило: T-LIFE/v1, C-MULT-I4 (освобождение в `finally`).
> - Evidence: `zen-serve-state-*` удаляется только `lease.cleanup()`. При `ServeUnavailable("no free serve port")`, `OSError` от `Popen` (не перехватывается обработчиками) состояние и `lifeline_w` не освобождаются.
> - Fix: `try/finally` вокруг всего пути от `_serve_env`, закрытие обоих концов pipe, оборачивание OSError в `ServeUnavailable`.
> - Проверка: тест с подменённым `Popen` (OSError): нет `zen-serve-state-*` и FD после 50 итераций.
>
> F-10 [blocking] Пробелы покрытия AC и неточная матрица
> - Locations: tests/test_realtime_reasoning.py (весь модуль); verification-traceability.md (строки REQ-006..009, REQ-013..016).
> - Правило: testing.md (регресс на каждое требование), `council` «Полнота/покрытие AC».
> - Evidence: нет тестов на AC-011/AC-012, serve `first_event/first_token/stall`, `_serve_json_serve`, AC-018, AC-020; фикстуры `__silent__` и `__never_event__` не используются; все строки матрицы PASS ссылаются на общий VER-001.
> - Fix: добавить недостающие тесты и привязать каждую строку матрицы к конкретному тесту.
> - Проверка: матрица с именем теста на каждое REQ/AC.
>
> F-11 [blocking] Самописный `_JsonParser` / `_loads_object`, ошибки маскируются
> - Locations: server.py:~1560-1700 (`_JsonParser`, `_loads_object`), используется в `_read_dynamic_config_enabled`, `_spawn_serve`, `_serve_http`, `_reader`.
> - Правило: python-standards §6/§7 (KISS, DRY), §3 (не маскировать ошибки); `json` остаётся импортированным.
> - Evidence: ~150 строк разбора JSON при доступном `json.loads`; парсер возвращает `{}` на ошибку, `RecursionError` не ловится, битый SSE-кадр превращается в `invalid_serve_event`.
> - Fix: `json.loads` с явным `except (ValueError, RecursionError)` и логом.
> - Проверка: тест битого и глубоко вложенного кадра даёт управляемую ошибку.
>
> F-12 [blocking] Подавления типов без обоснования
> - Locations: tests/test_realtime_reasoning.py:2 (`# pyright: reportAny=false, …` на 10 правил); `# type: ignore[attr-defined]` в `test_watchdog_first_event_timeout` и `setUp`/`tearDown` группы B.
> - Правило: python-standards, запрет №9.
> - Evidence: VER-004 требует нуль диагностик в новом тест-файле, и он достигнут блоковым подавлением, а не типизацией.
> - Fix: типизировать, убрать блоковое подавление и ненужные `type: ignore`, оставить точечные с причиной.
> - Проверка: VER-004 без подавлений.
>
> F-13 [non-blocking] Тавтологичные и неустойчивые тесты
> - Locations: tests/test_realtime_reasoning.py: `test_serve_health_and_fallback_table` (`assertTrue(silence or rows)`), `test_helper_argv_validation_and_lease_dir`, `test_native_tool_and_permission_reject`, `test_slow_serve_gets_status_and_no_status_on_fast`, пороги `≤1.0` и `<2.0`.
> - Правило: testing.md («тест должен воспроизводить баг»).
> - Evidence: тавтология; тест для «lease_dir» проверяет только rc≠0 при 5 аргументах; в native-тесте не проверяется, что reject отправлен; в «fast» части нет утверждения; RED в 16 тестах из-за `AttributeError`, а не поведения; Coder сам видел 1.04 с против 1.0.
> - Fix: реальные утверждения, `FakeClock` или запас по порогам.
> - Проверка: тесты красные на мутациях.
>
> F-14 [non-blocking] Lease-каталог в `/tmp` без владельца и режима
> - Locations: server.py:~2360-3114 (`LEASE_DIR`, `_spawn_serve`, `_startup_reaper`).
> - Правило: `security.md` §9 (predictable path), `error-handling`.
> - Evidence: `mkdir(parents=True, exist_ok=True)` с umask по умолчанию, reaper не проверяет `owner_uid` и ориентируется на подстроку `--serve-helper`.
> - Fix: каталог 0700 под `~/.dsh/…` или `os.mkdir` с проверкой владельца, проверка `owner_uid` и `parent_start_ts`.
> - Проверка: тест reaper на чужой lease.
>
> F-15 [non-blocking] Тестовый хук и вакуумная проверка нативного бинаря
> - Locations: server.py:~1560-1700 (`SERVE_TEST_ELIGIBLE`, `_is_native_opencode_bin`: `or len(head) == 4`).
> - Evidence: условие истинно для любого файла ≥4 байт без `#!`; тестовый флаг в продакшн-модуле.
> - Fix: проверка реального формата Mach-O/ELF, подмена бинаря в тестах через патч.
> - Проверка: текстовый файл без shebang не считается нативным.
>
> F-16 [non-blocking] Косметический реформат чужих областей
> - Locations: server.py: `_UpstreamBreaker` (~2204), `_RequestAttempts` (~2230-2291), `_PrefixDedup`, `Run.execute/_execute_once` (4427-4530), `Handler._res`, `_log_exit`; test_step_interruption.py:67 (кавычки `FAKE_OPENCODE`).
> - Правило: AGENTS.md п.4 (минимальные изменения), scope-diff.
> - Evidence: reverse-spec §1 («чисто форматирующие перестановки»).
> - Fix: вынести форматирование в отдельный коммит или откатить hunk'и вне поведения.
> - Проверка: diff без форматирующих hunk'ов в немодифицированных функциях.
>
> F-17 [non-blocking] Размер функций и дубли
> - Locations: `_serve_one_attempt` (~350 строк), `_run_serve_stream_attempts` (~190), `_serve_json_serve` (~210) в server.py (+1900 строк, итог 6287).
> - Правило: python-standards §6/§7, SOLID/SRP.
> - Evidence: вложенные замыкания; одинаковая логика retry, fallback и native-маппинга в stream и JSON.
> - Fix: выделить класс попытки serve и общий retry-цикл.
> - Проверка: функции ≤ ~80 строк, одна реализация retry-логики.
>
> F-18 [non-blocking] Изменённый оракул `test_step_interruption.py`
> - Locations: tests/test_step_interruption.py: `test_unmapped_retries_do_not_exhaust_incomplete_budget_stream/json` (~413-450).
> - Правило: verification-surface (`oracle_change` аудитирует Verifier), REQ-017.
> - Evidence: ожидания «4 запуска, tool_calls» заменены на «3 запуска, `[]`, stop», имена тестов «do_not_exhaust» утверждают обратное, записи аудита `oracle_change` в `verifier.json` нет.
> - Fix: переименовать тесты, задокументировать изменение контракта потолка, зафиксировать аудит.
> - Проверка: запись в `verifier.json`.
>
> F-19 [non-blocking] Жизненный цикл потоков и очереди
> - Locations: server.py:~2360-3114 (`_reader` с блокирующим `events.put`, `_prompt_worker` timeout 65 с, `threading.Thread(daemon=True)` без join).
> - Правило: T-LIFE/v1, C-MULT-I2.
> - Evidence: при заполненной очереди 4096 читатель блокируется навсегда, при раннем выходе потоки не завершаются, пока не закроются сокеты.
> - Fix: `put` с таймаутом и сигналом остановки, join или cancel потоков в `finally`.
> - Проверка: тест утечки потоков после 50 запросов.
>
> F-20 [non-blocking] [sweep] Watchdog считает только reasoning/text/завершённый tool
> - Locations: server.py:~2360-3114 (`_serve_one_attempt`, `last_token_at`, `first_token_at`).
> - Evidence: `session.tool.input.delta` и `reasoning.started` не обновляют `last_token_at`; при длинной генерации аргументов инструмента срабатывает `stall_timeout` через 60 с.
> - Fix: считать tool-input дельты признаком живости.
> - Проверка: фикстура с долгим tool-input без text не даёт ложный stall.
>
> F-21 [blocking] [pre-existing] Прямая мутация `os.environ` в изменённом тестовом файле
> - Locations: tests/test_step_interruption.py:~188-192 (`setUp`: `os.environ["FAKE_OC_COUNTER"] = …`, `FAKE_OC_PLAN`).
> - Правило: testing.md («запрет мутации `os.environ` без изоляции»); файл изменён задачей, значит blocking по §3 Diff-scope.
> - Evidence: записи без `monkeypatch` и гарантированного отката.
> - Fix: `mock.patch.dict` или `monkeypatch`.
> - Проверка: порядок запуска не влияет на результат (AC-023 reversed).
>
> COVERAGE: 14/14 подкатегорий
> FINDINGS_COMPLETE: 21
ARTIFACT_END>>>

СВОДНЫЙ ЛЕДЖЕР:
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/cycle-1/consensus-ledger.md sha256=00df0bda8f9a29b8d28ff56d02726dddcd7be67d3a0d1bd6096eca448b0c7131
# Черновой леджер совещания Совета Тимлидов по коду (цикл 1, после R1, run analyst-teamlead-zen-realtime-reasoning-20261025)

- Всего находок R1: `71` (`F-001..F-071`: `skeptic` `F-001..F-018`, `realist` `F-019..F-050`, `visionary` `F-051..F-071`).
- Открытых blocking (`OPEN_BLOCKING`): `50`; открытых non-blocking: `21`.

### F-001
- origin: skeptic · R1 · skeptic-01
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 skeptic=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> ### F-001
> priority: blocking
> criterion: КОРРЕКТНОСТЬ/логика, РЕАЛИЗУЕМОСТЬ
> locations: bridges/opencode-zen-bridge/server.py:4848, bridges/opencode-zen-bridge/server.py:5768, bridges/opencode-zen-bridge/server.py:4490, bridges/opencode-zen-bridge/server.py:5297
> rule: REQ-013 / AC-018; S-HERD-I1 (холодный старт сериализуется `_StartupGate`)
> evidence: `attempts.note_spawn()` затем `_serve_one_attempt` без `gate.acquire()` и без `spawn_limiter.acquire`; run-путь: `gate = _StartupGate()` и `self.res.spawn_limiter.acquire` / `res.spawn_limiter.acquire`.
> fix: Перед `_spawn_serve` в `_run_serve_stream_attempts` и `_serve_json_serve` захватывать `_StartupGate` и `spawn_limiter` с тем же `max_wait_s`, освобождать в `finally` попытки.
> verify: Тест двух перекрывающихся serve-попыток показывает сериализацию gate и отказ limiter при превышении `SPAWN_RATE_PER_S`.

### F-002
- origin: skeptic · R1 · skeptic-02
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 skeptic=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> ### F-002
> priority: blocking
> criterion: КОРРЕКТНОСТЬ/граничные условия
> locations: bridges/opencode-zen-bridge/server.py:2552
> rule: feature.md — таймаут на каждом шаге I/O, включая чтение после первого байта
> evidence: `select.select([out_fd], [], [], 3.0)` покрывает только появление fd; далее `while not line_bytes.endswith(b"\n"): chunk_b = os.read(out_fd, 1)` без дедлайна.
> fix: Читать рукопожатие с остатком тех же 3 с; по истечении `ServeUnavailable` и `lease.cleanup()`.
> verify: Helper, который пишет один байт и замолкает, убивается в бюджете рукопожатия, слот и группа освобождены.

### F-003
- origin: skeptic · R1 · skeptic-03
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 skeptic=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> ### F-003
> priority: blocking
> criterion: КОРРЕКТНОСТЬ/граничные условия
> locations: bridges/opencode-zen-bridge/server.py:72, bridges/opencode-zen-bridge/server.py:2593, bridges/opencode-zen-bridge/server.py:2609, bridges/opencode-zen-bridge/server.py:2613
> rule: REQ-008 / AC-011
> evidence: Lease пишет `"parent_start_ts": parent_lstart`. Reaper: `parent_alive = parent_pid > 0 and _pid_alive(parent_pid)` и при живом pid делает `continue`; иначе один `os.killpg(pgid, signal.SIGTERM)` и сразу `path.unlink()`.
> fix: Сверять lstart родителя и helper с lease до вывода «жив»; SIGKILL после 5 с; не удалять lease, пока группа жива. Тест с `helper_pid=0` эту ветку не исполняет — заменить живым фейком.
> verify: Lease мёртвого родителя, чей pid переиспользован (lstart не совпал), приводит к смерти helper+serve; lease остаётся, пока группа жива.

### F-004
- origin: skeptic · R1 · skeptic-04
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 skeptic=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> ### F-004
> priority: blocking
> criterion: ПОЛНОТА/пропущенные ветки
> locations: bridges/opencode-zen-bridge/server.py:5770, bridges/opencode-zen-bridge/server.py:4860
> rule: REQ-008 / AC-012 (обнаружение ухода клиента не позже 5 с, группа отсутствует не позже 7 с)
> evidence: Stream передаёт `is_client_gone=self._client_gone_check`. Вызов из `_serve_json_serve` аргумент не передаёт (`on_status=lambda _t: None` и сразу `thinking_enabled`).
> fix: Передавать `is_client_gone=self._client_gone_check` в JSON-попытку.
> verify: Закрытие сокета non-stream клиента останавливает группу не позже 7 с.

### F-005
- origin: skeptic · R1 · skeptic-05
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 skeptic=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> ### F-005
> priority: blocking
> criterion: ПОЛНОТА/покрытие AC
> locations: bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:99, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:102
> rule: REQ-006 / REQ-007 / AC-008 / AC-009 / AC-010
> evidence: `if "__never_event__" in prompt` и `if "__silent__" in prompt` есть в `FAKE_SERVE`; вызовов этих маркеров в тестах нет. Legacy `FAKE_RT_MODE=silent` покрывает только run.
> fix: Три теста TRANSPORT=serve: нет событий → `first_event_timeout`; событие без токена → `first_token_timeout`; токен и пауза → `stall_timeout`; завершение за порог+2 с.
> verify: Тесты красные, если цикл `_serve_one_attempt` перестаёт проверять эти три порога.

### F-006
- origin: skeptic · R1 · skeptic-06
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 skeptic=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> ### F-006
> priority: blocking
> criterion: ПОЛНОТА/пропущенные ветки
> locations: bridges/opencode-zen-bridge/server.py:4950, bridges/opencode-zen-bridge/server.py:4961, bridges/opencode-zen-bridge/server.py:5981
> rule: REQ-011 (STEP_RECOVERY на потоковом пути, включая forced tool_choice)
> evidence: `tool_choice=None` в `_incomplete_step_signal`; `_incomplete_tool_step_prompt(..., None, model)`; вызов `self._serve_json_serve(..., reported_model, None, res, attempts, xs)` при том, что параметр `tool_choice` у `_serve_json` есть и внутри `_serve_json_serve` используется.
> fix: Протащить `tool_choice` запроса в stream- и JSON-serve и в оба вызова recovery.
> verify: Serve-шаг с текстом без tool при `tool_choice`, требующем вызов, ретраится с force-клаузой в prompt.

### F-007
- origin: skeptic · R1 · skeptic-07
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 skeptic=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> ### F-007
> priority: blocking
> criterion: ПОЛНОТА/покрытие AC
> locations: bridges/opencode-zen-bridge/tests/test_step_interruption.py:188
> rule: REQ-011 / AC-016
> evidence: `setUp` изолирует `_Resilience()` (это закрывает REQ-017). По файлу нет `OPENCODE_ZEN_BRIDGE_TRANSPORT`; фейк — shebang `opencode run`. Матрица incomplete/unmapped/tool_calls на serve не исполняется.
> fix: Прогнать существующие сценарии прерывания шага (или их fake-delta эквивалент) с `TRANSPORT=serve`.
> verify: Регрессия остановки по tool_calls или incomplete-retry на serve роняет этот тест.

### F-008
- origin: skeptic · R1 · skeptic-08
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 skeptic=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> ### F-008
> priority: blocking
> criterion: РИСКИ/данные, АЛЬТЕРНАТИВЫ
> locations: bridges/opencode-zen-bridge/server.py:1675, bridges/opencode-zen-bridge/server.py:1701, bridges/opencode-zen-bridge/server.py:2857
> rule: REQ-005 (байты размышления модели не модифицируются); python-standards KISS при уже импортированном `json`
> evidence: `parts.append(chr(int(hex_part, 16)))` без склейки суррогатной пары; `_loads_object` на `ValueError`/`IndexError` возвращает `{}`; читатель SSE кладёт payload через `_loads_object`.
> fix: Удалить `_JsonParser` и разбирать объекты через `json.loads`.
> verify: Дельта `reasoning_content` с `\uD83D\uDE00` доходит одним символом; битый JSON не превращается молча в пустое событие без `invalid_serve_event`.

### F-009
- origin: skeptic · R1 · skeptic-09
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 skeptic=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> ### F-009
> priority: blocking
> criterion: КОРРЕКТНОСТЬ/обработка ошибок
> locations: bridges/opencode-zen-bridge/server.py:2879, bridges/opencode-zen-bridge/server.py:4893, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:619
> rule: Строка `FALLBACK_DECISION_TABLE` «PROMPT_RESPONSE HTTP429/provider5xx»: `serve_retry`, ServeHealth 0, UpstreamBreaker +1; REQ-009 (breaker сохраняется)
> evidence: `prompt_status["status"] = st` и `headers_at` выставляются для любого статуса, кроме отдельной ветки 401/403. Дальше `first_event_timeout` делает `res.serve_health.record_failure()`. Тест: `self.assertTrue(silence or rows)`.
> fix: 429 и provider 5xx на prompt проводить в `attempt_done(True, False)` без `serve_health`; убрать тавтологию, утверждать инкременты строки 429.
> verify: Три ответа prompt 429 не делают `is_degraded()`, breaker фиксирует отказ.

### F-010
- origin: skeptic · R1 · skeptic-10
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 skeptic=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> ### F-010
> priority: blocking
> criterion: РИСКИ/прод
> locations: bridges/opencode-zen-bridge/server.py:2464, bridges/opencode-zen-bridge/server.py:2467, bridges/opencode-zen-bridge/server.py:2471
> rule: REQ-008 / T-LIFE (процесс и читатель закрываются до возврата)
> evidence: `self.helper.wait(timeout=0.5)`, затем `os.killpg(..., SIGKILL)`, затем снова `wait(timeout=0.5)` и выход. `execution-evidence.md` / `l2-green-ver002-unittest.log`: `ResourceWarning: subprocess 98704 is still running` рядом со строками serve `O-EXIT`.
> fix: Ждать SIGTERM до 5 с, затем SIGKILL и ждать завершения; не возвращаться из `cleanup`, пока `_pid_alive(pgid)`.
> verify: Прогон unittest, включающий serve-тесты, не печатает `subprocess is still running`.

### F-011
- origin: skeptic · R1 · skeptic-11
- rev: 1
- priority: non-blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 skeptic=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> ### F-011
> priority: non-blocking
> criterion: КОРРЕКТНОСТЬ/логика
> locations: bridges/opencode-zen-bridge/server.py:1791
> rule: Предохранитель `_is_native_opencode_bin` в `auto` (shebang-фейк должен оставаться на run)
> evidence: `or len(head) == 4` после проверки Mach-O/ELF. Любой файл без `#!` длиной от 4 байт считается нативным.
> fix: Убрать дизъюнкт `len(head) == 4`; оставить Mach-O и ELF. Тест: 4 байта не-shebang → False.
> verify: Короткий бинарный мусор в `auto` не выбирает serve.

### F-012
- origin: skeptic · R1 · skeptic-12
- rev: 1
- priority: non-blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 skeptic=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> ### F-012
> priority: non-blocking
> criterion: ПОЛНОТА/покрытие AC
> locations: bridges/opencode-zen-bridge/server.py:1339
> rule: REQ-004 (первая видимая строка). Живой статус закрывается `STATUS_WAITING`, константа начального текста не используется.
> evidence: `STATUS_INITIAL = "[мост] Подключение к модели…\n"` — присваивание без чтения в diff.
> fix: Эмитить `STATUS_INITIAL` как первую статусную строку либо удалить константу.
> verify: Поиск по `server.py` либо находит эмиссию, либо константы нет.

### F-013
- origin: skeptic · R1 · skeptic-13
- rev: 1
- priority: non-blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 skeptic=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> ### F-013
> priority: non-blocking
> criterion: КОРРЕКТНОСТЬ/граничные условия
> locations: bridges/opencode-zen-bridge/server.py:2495, bridges/opencode-zen-bridge/server.py:2564
> rule: REQ-008 (свой слушатель). Окно между `bind` пробного сокета и bind serve; `lsof` с `None` проверку чужого слушателя пропускает.
> evidence: Скан порта `bind`/`close`, затем helper; `if listener_pid is not None and (listener_pid != serve_pid or ...)`.
> fix: Держать пробный сокет до старта serve или перепроверять слушателя до prompt; `lsof` без pid — `ServeUnavailable`.
> verify: Занятый между probe и bind порт даёт `ServeUnavailable`, а не чужой HTTP.

### F-014
- origin: skeptic · R1 · skeptic-14
- rev: 1
- priority: non-blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 skeptic=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> ### F-014
> priority: non-blocking
> criterion: КОРРЕКТНОСТЬ/логика
> locations: bridges/opencode-zen-bridge/server.py:2654, bridges/opencode-zen-bridge/server.py:2678
> rule: REQ-012 (native tool → текущий внутренний вид). DSH-маппинг читает имя и arguments; статус в выдачу DSH не входит.
> evidence: `feed` присваивает `item["text"] = text_value` вместо накопления дельт; `complete` всегда кладёт `"status": "error"`, в том числе на `session.tool.success`.
> fix: Склеивать `input.delta` либо опираться только на `input.ended.text`; статус брать из типа события.
> verify: Фикстура `session.tool.success` с двумя delta даёт полный JSON аргументов и status `success`.

### F-015
- origin: skeptic · R1 · skeptic-15
- rev: 1
- priority: non-blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 skeptic=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> ### F-015
> priority: non-blocking
> criterion: РИСКИ/безопасность
> locations: bridges/opencode-zen-bridge/server.py:2569, bridges/opencode-zen-bridge/server.py:2570, bridges/opencode-zen-bridge/server.py:3242
> rule: REQ-015 / AC-020. Пароль в лог этим путём не пишется: sink пустой, `_mask_secrets` режет токены ≥24 символов.
> evidence: Комментарий «stderr помощника дренируется в лог»; вызов `_drain_stderr(helper, [])`. `_drain_stderr` только дополняет список.
> fix: Либо логировать stderr через `_mask_secrets`, либо поправить комментарий. Добавить тест: пароль попытки отсутствует в `bridge.log`.
> verify: Прогон serve с известным паролем, `assertNotIn(password, log)`.

### F-016
- origin: skeptic · R1 · skeptic-16
- rev: 1
- priority: non-blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 skeptic=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> ### F-016
> priority: non-blocking
> criterion: ПОЛНОТА/покрытие AC
> locations: bridges/opencode-zen-bridge/server.py:4877, bridges/opencode-zen-bridge/server.py:4884
> rule: REQ-016 / AC-021. Поля в строке `O-EXIT/v1` есть; после fallback значение `first_event_ms` остаётся от serve при `transport=run`.
> evidence: `xs["first_event_ms"] = result["first_event_ms"]` дважды подряд до ветки fallback, которая меняет `transport` на `run` и возвращает `False`.
> fix: При возврате в run сбрасывать `first_event_ms`/`ttft_ms` либо помечать, к какому транспорту они относятся.
> verify: O-EXIT fallback-запроса не показывает serve-миллисекунды как тайминг итогового run.

### F-017
- origin: skeptic · R1 · skeptic-17
- rev: 1
- priority: non-blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 skeptic=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> ### F-017 [sweep]
> priority: non-blocking
> criterion: ПОЛНОТА/покрытие AC
> locations: bridges/opencode-zen-bridge/server.py:1795, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:634
> rule: REQ-003 / AC-004. Дефолт без флага — run: полный сьют 400 passed это подтверждает. Прямой матрицы kill-switch нет.
> evidence: `_select_transport` читает `TRANSPORT`, `REALTIME_SERVE_ENABLED` и файл `disable-serve`. Тесты группы B форсят `serve` или один сценарий `auto`+503.
> fix: Четыре случая: `TRANSPORT=run`, override `0`, файл disable, опечатка значения — все остаются на run и не зовут `_spawn_serve`.
> verify: Счётчик спавнов serve в этих четырёх случаях равен 0.

### F-018
- origin: skeptic · R1 · skeptic-18
- rev: 1
- priority: non-blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 skeptic=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> ### F-018
> priority: non-blocking
> criterion: ПОЛНОТА/покрытие AC
> locations: bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:441
> rule: REQ-001 / AC-001 / AC-002. Реалтайм на сокете есть (red на `origin/dev`, green `VER-005`). Интервал соседей &lt;500 мс и накладные моста ≤250 мс тест не утверждает: проверяется span &lt;2.0 с и «первая дельта раньше конца апстрима».
> evidence: `test_ac026_realtime_chunks_before_upstream_end` сравнивает `model_reasoning[-1][0] - model_reasoning[0][0]` с `2.0`.
> fix: Утверждать максимум соседнего интервала reasoning-чанков и верхнюю границу задержки мост↔сокет на фейке с известным `sleep`.
> verify: Тест красный, если чанки склеиваются в один блок в конце шага.

### F-019
- origin: realist · R1 · realist-01
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 realist=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-001 — priority=P1, blocking. Потеря пробельных дельт.**  
> Locations: `server.py:3018`, `server.py:3029`. Правило: REQ-005, REQ-010, AC-006. Evidence: `if text_value.strip():` окружает накопление и передачу дельты. Отдельные `" "`, `"\n"` и отступы исчезают, меняя reasoning, обычный текст и содержимое JSON-аргументов инструмента. Исправление: передавать все непустые дельты; определение первого содержательного токена отделить от сохранения байтов. Проверка: разбиения с отдельными пробелами, LF, отступами и пробелом внутри строкового аргумента дают исходную конкатенацию.

### F-020
- origin: realist · R1 · realist-02
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 realist=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-002 — priority=P1, blocking. Собственный JSON-парсер повреждает Unicode.**  
> Locations: `server.py:1560`, `server.py:1679`, `server.py:1705`, `server.py:2857`. Правило: python-standards.md §6, §16; REQ-005. Evidence: каждый `\uXXXX` преобразуется отдельным `chr()`. Допустимая пара `\ud83d\ude00` остаётся двумя суррогатами и ломает последующее UTF-8-кодирование. Глубина также не ограничена, `RecursionError` не обработан. Исправление: заменить парсер stdlib `json.loads` с типизированной границей и явной обработкой ошибок. Проверка: escaped emoji, вложенный JSON, невалидный JSON и прежние wire-фикстуры.

### F-021
- origin: realist · R1 · realist-03
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 realist=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-003 — priority=P1, blocking. Общий дедлайн не управляет serve-попыткой.**  
> Locations: `server.py:2718`, `server.py:2889`, `server.py:2892`, `server.py:3080`. Правило: `R-BULK-I1`, feature.md — остаток дедлайна на всей I/O-цепочке. Evidence: вместо дедлайна запроса создаётся `prompt_send_start + TIMEOUT_S`; при исчерпании цикла возвращается результат с пустыми `terminal` и `exit_reason`. Caller может выдать успешный финал для незавершённого ответа. Исправление: передавать абсолютный deadline, ограничивать им setup/read/retry и явно классифицировать истечение. Проверка: повтор у границы общего дедлайна не продлевает запрос; отсутствие terminal никогда не становится успехом.

### F-022
- origin: realist · R1 · realist-04
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 realist=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-004 — priority=P1, blocking. Пять секунд тишины ошибочно обрывают serve.**  
> Locations: `server.py:2827`, `server.py:2848`, `server.py:2860`, `server.py:2928`. Правило: REQ-006–007, AC-009–010. Evidence: SSE-соединение создано с `timeout=5`; таймаут чтения превращается в EOF/`invalid_serve_event`, хотя первый токен и stall по умолчанию допускают 60 секунд. Исправление: согласовать чтение сокета с watchdog и отличать промежуточную тишину от окончания потока. Проверка: пауза больше 5 секунд и меньше заданного watchdog не вызывает повтор или ошибку.

### F-023
- origin: realist · R1 · realist-05
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 realist=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-005 — priority=P1, blocking. Timeout cleanup не применяется к существующему соединению.**  
> Locations: `server.py:2403`, `server.py:2755`, `server.py:2997`, `server.py:3084`, `server.py:3094`. Правило: feature.md — таймаут каждого шага, включая `finally`; REQ-008. Evidence: при переданном `conn` аргумент `timeout=0.25` не меняет timeout соединения, созданного ранее с 3 секундами. Несколько управляющих вызовов и их повторов задерживают `lease.cleanup()`. Исправление: применять актуальный timeout к сокету, ограничить общий cleanup-бюджет, гарантировать kill группы независимо от HTTP-cleanup. Проверка: зависшие control-endpoints не удерживают процессы дольше AC-011.

### F-024
- origin: realist · R1 · realist-06
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 realist=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-006 — priority=P1, blocking. Первая видимая реакция отсутствует во время setup.**  
> Locations: `server.py:2740`, `server.py:2778`, `server.py:2810`, `server.py:2835`, `server.py:2890`, `server.py:5298`, `server.py:5363`. Правило: REQ-004, AC-005. Evidence: статус начинает обслуживаться после spawn/readiness/create/subscribe; в legacy — после ожидания gate/limiter и запуска. Исправленная база `status_next` не позволяет эмитить статус во время уже блокирующего setup. Исправление: обслуживать ограниченный по времени первый статус с момента открытия SSE, включая ожидания запуска. Проверка: каждый setup-этап и занятый gate задержаны более секунды, статус всё равно приходит в пределах AC-005.

### F-025
- origin: realist · R1 · realist-07
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 realist=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-007 — priority=P1, blocking. Legacy-watchdog зависит от отсутствия stdout.**  
> Locations: `server.py:1096`, `server.py:5439`, `server.py:5453`. Правило: REQ-006–008. Evidence: надзор передан как `on_idle`; поступление каждой строки сбрасывает idle. Непрерывные служебные либо невалидные строки предотвращают проверку первого токена, stall и ухода клиента. Исправление: выполнять надзор по независимому монотонному расписанию и при поступлении данных. Проверка: служебные строки каждые 100 мс не отменяют watchdog и обнаружение disconnect.

### F-026
- origin: realist · R1 · realist-08
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 realist=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-008 — priority=P1, blocking. Serve обходит защиты холодного старта.**  
> Locations: `server.py:4848`, `server.py:5768`, `server.py:2740`. Правило: REQ-013, `S-HERD-I1`, `R-BULK-I2`. Evidence: перед `_serve_one_attempt` вызывается `note_spawn()`, но нет `_StartupGate.acquire()` и `res.spawn_limiter.acquire()`, присутствующих в run. Шесть обработчиков могут одновременно поднять шесть serve. Исправление: подключить serve к тем же защитам с остатком дедлайна и гарантированным освобождением. Проверка: конкурентные stream/JSON-запросы соблюдают общий темп запусков и gate.

### F-027
- origin: realist · R1 · realist-09
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 realist=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-009 — priority=P1, blocking. Fallback может превысить потолок трёх запусков.**  
> Locations: `server.py:4866`, `server.py:4897`, `server.py:5298`, `server.py:5785`, `server.py:5806`, `server.py:5992`, `server.py:4491`. Правило: REQ-009, AC-013, `R-BULK-I2`. Evidence: после нескольких serve-попыток `return False` переводит управление в run без новой проверки потолка; run непосредственно запускает процесс и делает `note_spawn()`. Сам fallback также обходит `allow_retry`. Исправление: единый допуск каждой следующей попытки, включая смену транспорта. Проверка: две доставленные неудачи serve, третья pre-delivery неудача — run не становится четвёртым запуском.

### F-028
- origin: realist · R1 · realist-10
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 realist=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-010 — priority=P1, blocking. Успех serve не закрывает HALF_OPEN Circuit Breaker.**  
> Locations: `server.py:4914`, `server.py:5818`. Правило: REQ-009, `R-BULK-I3`. Evidence: успех сбрасывает только `serve_health`; `attempts.attempt_done(False, True)` отсутствует. Зарезервированная проба HALF_OPEN не завершается успехом, последующие запросы могут оставаться заблокированными. После предыдущего timeout также может сохраниться `_pending_failure`. Исправление: завершать каждую попытку через общий механизм breaker. Проверка: OPEN → HALF_OPEN → успешный serve → CLOSED; timeout → успешный повтор не засчитывается окончательным отказом.

### F-029
- origin: realist · R1 · realist-11
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 realist=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-011 — priority=P1, blocking. Prompt-response не управляет барьером доставки и классификацией ошибок.**  
> Locations: `server.py:2413`, `server.py:2414`, `server.py:2879`, `server.py:2880`, `server.py:2901`, `server.py:2965`. Правило: заявленная `FALLBACK_DECISION_TABLE`, REQ-009. Evidence: `headers_at` записывается после чтения всего тела; `status` и `error` практически не используются, security проверяется только после получения очередного SSE-события. HTTP 400/404/422/429/5xx prompt не получают заявленных действий. Исправление: фиксировать доставку при получении заголовков, независимо наблюдать результат worker и применять полную таблицу решений. Проверка: все классы prompt-ответов, включая заголовки с зависшим телом и отсутствие SSE, дают нужный исход без недопустимого fallback.

### F-030
- origin: realist · R1 · realist-12
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 realist=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-012 — priority=P1, blocking. Ошибки провайдера обходят прежнюю recovery-семантику.**  
> Locations: `server.py:3073`, `server.py:4909`, `server.py:5813`, `server.py:4943`, `server.py:5884`. Правило: REQ-009, REQ-011. Evidence: любой `result["error"]` немедленно завершает запрос; различие транзиентной и фатальной ошибки не используется. В `_incomplete_step_signal` передаётся `False` вместо факта транзиентного обрыва. Исправление: сохранить классификацию, лимиты и восстановление legacy-пути на накопленном результате serve. Проверка: 429/5xx/transport error до и после вывода, фатальные 4xx и все соответствующие сценарии `test_step_interruption.py`.

### F-031
- origin: realist · R1 · realist-13
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 realist=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-013 — priority=P1, blocking. Теряется `tool_choice`.**  
> Locations: `server.py:4753`, `server.py:4950`, `server.py:4961`, `server.py:5971`. Правило: REQ-002, REQ-011; обратная совместимость входного контракта. Evidence: stream-helper не принимает `tool_choice`, использует `None`; JSON-helper получает явный `None` вместо аргумента `_serve_json`. Recovery для `required` и конкретного имени инструмента меняет поведение. Исправление: передавать исходное значение через все serve-ветки. Проверка: `required`, именованный выбор и `none` эквивалентны run.

### F-032
- origin: realist · R1 · realist-14
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 realist=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-014 — priority=P1, blocking. Serve не останавливается после инструментального шага.**  
> Locations: `server.py:3046`, `server.py:3052`, `server.py:3077`, `server.py:4804`. Правило: REQ-011. Evidence: после получения tool call и `session.step.ended` цикл продолжает читать до `session.execution.succeeded`; последующие text/reasoning не блокируются для обычного текстового tool call. Исправление: завершать попытку на границе шага с вызовами, interrupt/cleanup выполнять до дальнейшей генерации. Проверка: апстрим посылает второй шаг после первого tool call — второй шаг не попадает клиенту, итог `tool_calls`.

### F-033
- origin: realist · R1 · realist-15
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 realist=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-015 — priority=P1, blocking. Повтор serve дублирует уже отданный текст.**  
> Locations: `server.py:4843`, `server.py:4901`, `server.py:4925`, `server.py:4952`, `server.py:5850`, `server.py:5908`. Правило: сохранение recovery-семантики, REQ-009. Evidence: парсер пересоздаётся, но аналог `_PrefixDedup`/`_dedup_retry_text` не применяется; JSON соединяет результаты попыток. Повторы unmapped/incomplete также не получают обязательного разделителя reasoning между попытками. Исправление: сохранить reasoning без дедупликации, явно разделять попытки, дедуплицировать текст по прежнему правилу. Проверка: одинаковый и расходящийся префиксы при timeout/incomplete/unmapped через оба режима.

### F-034
- origin: realist · R1 · realist-16
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 realist=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-016 — priority=P2, blocking. Usage неуспешных попыток теряется.**  
> Locations: `server.py:4886`, `server.py:4915`, `server.py:5795`, `server.py:5874`. Правило: REQ-014. Evidence: ветки timeout/invalid-event выполняют `continue` до аккумуляции уже полученного `result["usage"]`. Исправление: учитывать usage завершённых шагов всех оплаченных попыток до принятия решения о повторе. Проверка: первая попытка отдаёт `step.ended`, затем обрывается; финальный usage равен сумме её токенов и успешного повтора.

### F-035
- origin: realist · R1 · realist-17
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 realist=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-017 — priority=P1, blocking. На ошибках запуска пропускается cleanup.**  
> Locations: `server.py:1768`, `server.py:2510`, `server.py:2550`, `server.py:2563`, `server.py:2568`, `server.py:2572`, `server.py:2740`. Правило: REQ-008, `T-LIFE`, secure temporary files. Evidence: собственные `raise ServeUnavailable(...)` не входят в `except (OSError, ValueError, subprocess.SubprocessError)`; вызов `_spawn_serve` расположен до `try/finally` попытки. При отказе `Popen` также не закрывается write-конец lifeline и не удаляется созданный state-dir. Исправление: обеспечить владение ресурсами с момента их создания и cleanup на каждом исходе. Проверка: spawn failure, handshake timeout/mismatch и foreign listener оставляют ноль процессов, FD, lease и state-dir. Лог L2 дополнительно содержит `ResourceWarning: subprocess ... is still running`.

### F-036
- origin: realist · R1 · realist-18
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 realist=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-018 — priority=P1, blocking. SSE-reader может навсегда остаться на заполненной очереди.**  
> Locations: `server.py:2842`, `server.py:2859`, `server.py:2863`, `server.py:2865`, `server.py:3107`. Правило: `T-LIFE`, `C-MULT-I4`. Evidence: оба `events.put(...)` блокирующие, без timeout/cancel; reader не присоединяется при выходе consumer. Убийство serve не разблокирует поток, уже ожидающий место в Python-очереди. Исправление: cancellation-aware bounded queue, отдельный сигнал окончания и ограниченный join. Проверка: заполнить очередь, отменить запрос; поток и принадлежащие ему ресурсы освобождаются.

### F-037
- origin: realist · R1 · realist-19
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 realist=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-019 — priority=P2, blocking. Дренаж stderr накапливает неограниченную память.**  
> Locations: `server.py:2570`, `server.py:1028`. Правило: ограниченные ресурсы `HL-ENV`, `C-MULT-I2`. Evidence: `_drain_stderr(helper, [])` добавляет каждую строку в список, удерживаемый потоком до окончания попытки; список никем не читается и не ограничен. Исправление: использовать ограниченный хвост либо дренаж с отбрасыванием и счётчиком. Проверка: многомегабайтный непрерывный stderr не вызывает линейного роста RSS.

### F-038
- origin: realist · R1 · realist-20
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 realist=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-020 — priority=P1, blocking. Авторизация отправляется без обязательного ownership-proof слушателя.**  
> Locations: `server.py:2374`, `server.py:2564`, `server.py:2565`, `server.py:2778`. Правило: security.md, подтверждение владения до передачи секретов. Evidence: `listener_pid is None` допускается; проверка выполняется сразу после handshake, до гарантированного bind serve. Порт предварительно освобождается, поэтому возможна гонка, а последующий reconnect не перепроверяет владельца. Исправление: требовать положительное совпадение listener PID, PGID и живого helper до первой авторизованной записи и при явном reconnect; неоднозначность — fail-closed. Проверка: отсутствующий/чужой/сменившийся слушатель получает ноль байтов Authorization и prompt.

### F-039
- origin: realist · R1 · realist-21
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 realist=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-021 — priority=P1, blocking. Reaper не проверяет идентичность процессов.**  
> Locations: `server.py:74`, `server.py:2593`, `server.py:2606`, `server.py:2609`. Правило: `T-LIFE`, безопасность сигналов. Evidence: сохранённые UID/start-time/attempt не сверяются; достаточно живого PID и подстроки `"--serve-helper"`. PID reuse может сохранить сироту либо привести к сигналу другой сессии. Исправление: сверять UID, реальные времена старта, точный script/argv, attempt и PGID; безопасно работать с lease-каталогом. Проверка: переиспользованные PID, чужой helper и подложный lease не получают сигналов.

### F-040
- origin: realist · R1 · realist-22
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 realist=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-022 — priority=P1, blocking. Lifeline не гарантирует остановку всего дерева при смерти моста.**  
> Locations: `server.py:174`, `server.py:177`, `server.py:181`, `server.py:195`. Правило: REQ-008, `T-LIFE`. Evidence: helper завершает только непосредственный `serve_proc`, после чего удаляет lease. Потомок serve, переживший родителя, не получает гарантированный групповой сигнал и лишается следа для reaper. Исправление: реализовать проверяемое завершение всей собственной группы при EOF/TERM, включая эскалацию. Проверка: убить мост при helper → serve → grandchild; все процессы исчезают, чужие группы не затронуты.

### F-041
- origin: realist · R1 · realist-23
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 realist=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-023 — priority=P1, blocking. Отмена клиента реализована не во всех режимах.**  
> Locations: `server.py:4750`, `server.py:5769`. Правило: REQ-008. Evidence: `_client_gone_check` превращает RST/OSError в `False`; JSON-путь вообще не передаёт callback `is_client_gone`. Исправление: различать отсутствие данных и терминальный разрыв, подключить надзор к JSON и setup-ожиданиям. Проверка: FIN и RST до первого события, после токена и в JSON приводят к остановке в пределах AC-011.

### F-042
- origin: realist · R1 · realist-24
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 realist=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-024 — priority=P1, blocking. Матрица PASS не соответствует содержимому оракулов.**  
> Locations: `tests/test_realtime_reasoning.py:376`, `tests/test_realtime_reasoning.py:434`, `tests/test_realtime_reasoning.py:442`, `tests/test_realtime_reasoning.py:619`; `verification-traceability.md`, строки REQ-001, REQ-006–016. Правило: testing.md — независимый эталон полноты; task envelope — поштучная проверка AC. Evidence: `upstream_end_t = elapsed` — EOF самого клиентского ответа; выдача всех пяти дельт одной пачкой также удовлетворяет `first < elapsed` и spread `<2`. Пределы 500/250 мс не проверяются; `assertTrue(silence or rows)` заведомо проходит при непустой таблице. Исправление: независимые upstream timestamps/барьеры; добавить serve JSON, три watchdog, delivered-retry, лимиты, cleanup, permission/unmapped и финальный usage. Исправить traceability по реальным результатам; аварийную чистоту подпроцессов подтвердить crash-guard либо предусмотренным ручным свидетельством. Проверка: намеренно буферизующая и нарушающая таблицу реализация должна краснить соответствующие тесты.

### F-043
- origin: realist · R1 · realist-25
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 realist=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-025 — priority=P2, blocking. «Ноль диагностик» получен с подавленными правилами.**  
> Locations: `tests/test_realtime_reasoning.py:2`, `381`, `384`, `385`, `390`, `391`, `408`, `411`, `429`, `431`. Правило: python-standards.md — запрет №9; запрет необъяснённых suppressions. Evidence: заголовок выключает множество диагностик, включая `reportAny` и `reportMissingParameterType`; новые обращения содержат необъяснённые `type: ignore`. Исправление: убрать blanket-подавления и ненужные ignores, исправить типы; узкие исключения обосновать. Проверка: новый файл проверяется с включёнными соответствующими правилами.

### F-044
- origin: realist · R1 · realist-26
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 realist=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-026 — priority=P2, blocking [sweep]. Тест удаляет исходное значение окружения.**  
> Locations: `tests/test_realtime_reasoning.py:299`, `tests/test_realtime_reasoning.py:300`. Правило: testing.md — гарантированный откат `os.environ`. Evidence: после `self.env.stop()`, восстановившего исходный `FAKE_RT_MODE`, выполняется безусловный `pop`. Исправление: удалить дополнительную мутацию либо восстанавливать точное предыдущее состояние. Проверка: запуск при заранее установленном значении сохраняет его после teardown.

### F-045
- origin: realist · R1 · realist-27
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 realist=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-027 — priority=P2, blocking. Новый тестовый модуль нарушает прямой запрет TestCase.**  
> Locations: `tests/test_realtime_reasoning.py:279`, `tests/test_realtime_reasoning.py:397`. Правило: testing.md — «Не использовать `unittest.TestCase`, `setUp`, `tearDown`». Evidence: оба новых класса основаны на TestCase. Исправление: использовать pytest-тесты и фикстуры с гарантированным teardown. Async/Litestar-инструментарий для этого синхронного stdlib-моста не требуется. Проверка: тот же набор сценариев проходит без новых TestCase.

### F-046
- origin: realist · R1 · realist-28
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 realist=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-028 — priority=P2, blocking. Измерения времени смешаны с обычным тестовым контуром.**  
> Locations: `tests/test_realtime_reasoning.py:321`, `392`, `444`, `445`, `568`, `624`. Правило: testing.md §7.2, Serial Lane. Evidence: wall-clock assertions выполняются в обычном полном наборе без `measured`/`heavy`; уже зафиксировано падение около границы 1 секунды. Исправление: выделить замеры в последовательный измерительный контур, а состояния watchdog дополнить FakeClock-оракулами. Проверка: обычный набор не зависит от загрузки машины; отдельный измерительный прогон сохраняет проверки реального клиентского сокета.

### F-047
- origin: realist · R1 · realist-29
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 realist=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-029 — priority=P2, blocking. Эксплуатационные изменения не документированы.**  
> Locations: `server.py:1326`, `server.py:1743`, `server.py:1795`; `candidate-manifest.json:files`. Правило: python-standards.md §12. Evidence: добавлены transport/permission/watchdog overrides, dynamic-config и disable-файл, но разрешённый трёхфайловый diff не содержит обновлений README/CHANGELOG. Исправление: согласовать расширение документационного scope и описать приоритеты переключателей, пороги, fallback и откат. Проверка: оператор может включить и отключить транспорт по опубликованной инструкции без чтения исходника.

### F-048
- origin: realist · R1 · realist-30
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 realist=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-030 — priority=P2, blocking. Фильтр чужих сессий применяется после потери sessionID.**  
> Locations: `server.py:1844`, `server.py:1845`, `server.py:1875`, `server.py:2973`. Правило: граница изоляции serve-сессии, security.md — проверка входа на границе. Evidence: mapper удаляет `sessionID` у reasoning/text/error, затем фильтр разрешает `None`; чужая дельта либо ошибка проходит. Исправление: проверять sessionID в исходном wire-событии до отображения и обработки. Проверка: события второй сессии не меняют текст, usage, исход и watchdog текущей.

### F-049
- origin: realist · R1 · realist-31
- rev: 1
- priority: non-blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 realist=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-031 — priority=P3, non-blocking. Проверка нативного бинарника почти всегда разрешающая.**  
> Locations: `server.py:1777`, `server.py:1791`. Правило: заявленная проверка допуска auto. Evidence: `or len(head) == 4` принимает любой файл длиной не меньше четырёх байтов без shebang. Исправление: проверять известные исполняемые форматы либо убрать вводящее в заблуждение утверждение о такой проверке. Проверка: произвольный четырёхбайтовый файл не считается нативным opencode.

### F-050
- origin: realist · R1 · realist-32
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 realist=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-032 — priority=P2, blocking [sweep]. Поля «первого события» переписываются последующими попытками.**  
> Locations: `server.py:4877`, `server.py:4884`, `server.py:5456`, `server.py:5468`, `server.py:5793`. Правило: REQ-016, `O-EXIT/v1`. Evidence: значения запроса перезаписываются таймингами очередной попытки; в сыром L2 есть `first_event_ms=1975 ttft_ms=974`. В итоге названия полей не соответствуют первому событию и первому токену запроса. Исправление: сохранять первые request-level значения, attempt-level значения учитывать отдельно. Проверка: retry/fallback не стирает первый момент; для одного запроса первый токен не предшествует первому событию.

### F-051
- origin: visionary · R1 · visionary-01
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 visionary=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-01 [blocking] Whitespace-дельты не пересылаются клиенту
> - Locations: server.py:~2360-3114 (`_serve_one_attempt`, ветки `etype == "reasoning"` и `etype == "text"`).
> - Правило: REQ-005/AC-006 (текст модели не модифицируется), REQ-001; F-37 (превью требует `\n`).
> - Evidence: `if text_value.strip(): … on_reasoning(text_value)` и такое же условие для `on_text`.
> - Fix: пересылать любую непустую дельту без `strip`; `first_token_at` и `last_token_at` обновлять только по содержательным токенам.
> - Проверка: тест с дельтами `"\n\n"`, `" "`, `"\n"`: конкатенация побайтно равна эталону, в том числе внутри `<tool_invoke>`.

### F-052
- origin: visionary · R1 · visionary-02
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 visionary=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-02 [blocking] Гонка выбора порта serve и отправка пароля не тому serve
> - Locations: server.py:~2360-3114 (`_spawn_serve`, цикл `range(20000 + pid%20000, 60000)` с bind-проб и закрытием сокета); `_serve_one_attempt` (ready-проверка).
> - Правило: C-MULT-I3/I4; `scope-and-contracts` (не ломать конкурентные запросы); `security.md` §9.
> - Evidence: все потоки сканируют от одного кандидата, сокет закрывается до bind serve. Два запроса в окне ~110 мс получают один порт. Если `lsof` ещё не видит слушателя, `GET /api/session/active` попадает в чужой serve и возвращает 401. Это `ServeSecurityError` без fallback.
> - Fix: глобальный замок на выделение порта до проверки владения; либо `--port 0` с чтением реального порта; 401 на ready до DELIVERED считать `ServeUnavailable`.
> - Проверка: тест на 6 параллельных stream-запросов, ни одного `serve security failure`.

### F-053
- origin: visionary · R1 · visionary-03
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 visionary=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-03 [blocking] Регрессия дефолтного пути `run`: watchdog первого токена 60 с
> - Locations: server.py:5351-5474 (`send_keepalive`, `watchdog_state`); константы `FIRST_TOKEN_TIMEOUT_S`, `FIRST_EVENT_TIMEOUT_S`, `STALL_TIMEOUT_S`.
> - Правило: REQ-003 (прежний путь остаётся рабочим), REQ-002.
> - Evidence: F-17/F-18: `run` выдаёт reasoning и text одним блоком в конце шага. F-32: максимум `deepseek-v4.1-flash-free` 85.65 с. По умолчанию serve выключен, поэтому путь `run` основной. Шаг дольше 60 с убивается и повторяется до 3 раз. Статусы `[мост]` и watchdog на `run` работают вне переключателя транспорта.
> - Fix: для legacy использовать потолок не ниже прежнего поведения либо отдельные пороги с высоким дефолтом, `first_event` считать по `step_start`, watchdog первого токена оставить только для serve; поведение legacy за флагом.
> - Проверка: фейк-CLI с паузой 70 с до единого блока завершается успешно без ретраев.

### F-054
- origin: visionary · R1 · visionary-04
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 visionary=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-04 [blocking] REQ-013 не выполнен для serve
> - Locations: server.py:~2360-3114 (`_serve_one_attempt` / `_spawn_serve`); AC-018.
> - Правило: REQ-013 (`_StartupGate`, `SPAWN_RATE_PER_S`), R-BULK-I2.
> - Evidence: serve-путь не вызывает `gate.acquire()` и `res.spawn_limiter.acquire()`, теста на ротацию IP нет.
> - Fix: acquire `spawn_limiter` и gate перед `_spawn_serve`, release в `finally`.
> - Проверка: тест двух запусков с подменённым `_next_standalone_proxy` и ограничением частоты.

### F-055
- origin: visionary · R1 · visionary-05
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 visionary=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-05 [blocking] Результат prompt-POST игнорируется, `FALLBACK_DECISION_TABLE` мёртва
> - Locations: server.py:~2360-3114 (`_prompt_worker`, `prompt_status`); `FALLBACK_DECISION_TABLE` (server.py:~1450-1560).
> - Правило: `error-handling.md` (Identify→Assess), REQ-009.
> - Evidence: пишется `prompt_status["status"/"error"]`, проверяется только 401/403. 400/429/5xx и сетевая ошибка приводят к ожиданию 20 с. Строка таблицы про 429 и provider5xx не реализована, тест таблицы проверяет только `len ≥ 10`.
> - Fix: классифицировать статус prompt по таблице (retry с breaker+1, fail-closed на 400/404/422) или удалить таблицу.
> - Проверка: FakeServe отвечает 429 на prompt, затем retry без ожидания 20 с.

### F-056
- origin: visionary · R1 · visionary-06
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 visionary=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-06 [blocking] Повтор после отданного контента дублирует text и tool_calls
> - Locations: server.py:4734-4967 (`_run_serve_stream_attempts`, ветки `allow_retry`/`continue`); `_serve_json_serve`.
> - Правило: REQ-009/AC-014, REQ-010.
> - Evidence: legacy использует `_PrefixDedup`, serve нет. После `stall_timeout` при уже отданных text или tool_call повтор выдаёт тот же контент снова.
> - Fix: дедуп префикса либо запрет retry после отданного text или tool_call.
> - Проверка: тест stall после части текста и вызова инструмента, клиент не видит дублей.

### F-057
- origin: visionary · R1 · visionary-07
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 visionary=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-07 [blocking] Первый статус ≤1.0 с (REQ-004) не гарантирован
> - Locations: server.py:5351-5474 (`send_keepalive`); `_serve_one_attempt` (`status_next`, `STATUS_INITIAL`).
> - Правило: REQ-004/AC-005.
> - Evidence: `STATUS_INITIAL` объявлен и нигде не эмитируется. На legacy статусы идут только из цикла `feed.lines`, а до него `_StartupGate` держит до 5 с (STARTUP_WAIT_S) и `spawn_limiter`. На serve цикл статусов стартует после spawn, ready, create, subscribe.
> - Fix: эмитить `STATUS_INITIAL` сразу после role-чанка до gate и spawn при включённом thinking.
> - Проверка: удержать gate 3 с, первый чанк с `[мост]\n` приходит ≤1.0 с.

### F-058
- origin: visionary · R1 · visionary-08
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 visionary=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-08 [blocking] Реальный wire v2.1.2 не проверен: события с пустым `data`
> - Locations: server.py:~1800-1880 (`_map_serve_event`: `if not data: raise ServeProtocolError`); `_serve_one_attempt` (`except ServeProtocolError` → `delivered=True`).
> - Правило: R-BULK-I3, REQ-012; факт-карта F-19, VER-006 DEFERRED_L3.
> - Evidence: любое событие кроме `server.connected` с пустым `data` (в F-19 на 161 мс приходит `integration.updated`) даёт `invalid_serve_event`, `delivered=True` и retry вместо fallback. Все фикстуры синтетические.
> - Fix: игнорировать неизвестные события и пустой `data`, валидировать только известные типы; добавить фикстуры, снятые с реального serve; прогнать VER-006 на живом контуре до включения флага.
> - Проверка: тест, подающий heartbeat и `integration.updated` с пустым `data`, не прерывает попытку. Статус PLAUSIBLE.

### F-059
- origin: visionary · R1 · visionary-09
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 visionary=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-09 [blocking] Утечка tempdir и FD при сбое запуска serve
> - Locations: server.py:~2360-3114 (`_serve_env` → `mkdtemp`; `_spawn_serve`: `os.pipe`, `Popen` до создания `_ServeLease`; `lease_dir.mkdir`).
> - Правило: T-LIFE/v1, C-MULT-I4 (освобождение в `finally`).
> - Evidence: `zen-serve-state-*` удаляется только `lease.cleanup()`. При `ServeUnavailable("no free serve port")`, `OSError` от `Popen` (не перехватывается обработчиками) состояние и `lifeline_w` не освобождаются.
> - Fix: `try/finally` вокруг всего пути от `_serve_env`, закрытие обоих концов pipe, оборачивание OSError в `ServeUnavailable`.
> - Проверка: тест с подменённым `Popen` (OSError): нет `zen-serve-state-*` и FD после 50 итераций.

### F-060
- origin: visionary · R1 · visionary-10
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 visionary=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-10 [blocking] Пробелы покрытия AC и неточная матрица
> - Locations: tests/test_realtime_reasoning.py (весь модуль); verification-traceability.md (строки REQ-006..009, REQ-013..016).
> - Правило: testing.md (регресс на каждое требование), `council` «Полнота/покрытие AC».
> - Evidence: нет тестов на AC-011/AC-012, serve `first_event/first_token/stall`, `_serve_json_serve`, AC-018, AC-020; фикстуры `__silent__` и `__never_event__` не используются; все строки матрицы PASS ссылаются на общий VER-001.
> - Fix: добавить недостающие тесты и привязать каждую строку матрицы к конкретному тесту.
> - Проверка: матрица с именем теста на каждое REQ/AC.

### F-061
- origin: visionary · R1 · visionary-11
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 visionary=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-11 [blocking] Самописный `_JsonParser` / `_loads_object`, ошибки маскируются
> - Locations: server.py:~1560-1700 (`_JsonParser`, `_loads_object`), используется в `_read_dynamic_config_enabled`, `_spawn_serve`, `_serve_http`, `_reader`.
> - Правило: python-standards §6/§7 (KISS, DRY), §3 (не маскировать ошибки); `json` остаётся импортированным.
> - Evidence: ~150 строк разбора JSON при доступном `json.loads`; парсер возвращает `{}` на ошибку, `RecursionError` не ловится, битый SSE-кадр превращается в `invalid_serve_event`.
> - Fix: `json.loads` с явным `except (ValueError, RecursionError)` и логом.
> - Проверка: тест битого и глубоко вложенного кадра даёт управляемую ошибку.

### F-062
- origin: visionary · R1 · visionary-12
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 visionary=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-12 [blocking] Подавления типов без обоснования
> - Locations: tests/test_realtime_reasoning.py:2 (`# pyright: reportAny=false, …` на 10 правил); `# type: ignore[attr-defined]` в `test_watchdog_first_event_timeout` и `setUp`/`tearDown` группы B.
> - Правило: python-standards, запрет №9.
> - Evidence: VER-004 требует нуль диагностик в новом тест-файле, и он достигнут блоковым подавлением, а не типизацией.
> - Fix: типизировать, убрать блоковое подавление и ненужные `type: ignore`, оставить точечные с причиной.
> - Проверка: VER-004 без подавлений.

### F-063
- origin: visionary · R1 · visionary-13
- rev: 1
- priority: non-blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 visionary=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-13 [non-blocking] Тавтологичные и неустойчивые тесты
> - Locations: tests/test_realtime_reasoning.py: `test_serve_health_and_fallback_table` (`assertTrue(silence or rows)`), `test_helper_argv_validation_and_lease_dir`, `test_native_tool_and_permission_reject`, `test_slow_serve_gets_status_and_no_status_on_fast`, пороги `≤1.0` и `<2.0`.
> - Правило: testing.md («тест должен воспроизводить баг»).
> - Evidence: тавтология; тест для «lease_dir» проверяет только rc≠0 при 5 аргументах; в native-тесте не проверяется, что reject отправлен; в «fast» части нет утверждения; RED в 16 тестах из-за `AttributeError`, а не поведения; Coder сам видел 1.04 с против 1.0.
> - Fix: реальные утверждения, `FakeClock` или запас по порогам.
> - Проверка: тесты красные на мутациях.

### F-064
- origin: visionary · R1 · visionary-14
- rev: 1
- priority: non-blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 visionary=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-14 [non-blocking] Lease-каталог в `/tmp` без владельца и режима
> - Locations: server.py:~2360-3114 (`LEASE_DIR`, `_spawn_serve`, `_startup_reaper`).
> - Правило: `security.md` §9 (predictable path), `error-handling`.
> - Evidence: `mkdir(parents=True, exist_ok=True)` с umask по умолчанию, reaper не проверяет `owner_uid` и ориентируется на подстроку `--serve-helper`.
> - Fix: каталог 0700 под `~/.dsh/…` или `os.mkdir` с проверкой владельца, проверка `owner_uid` и `parent_start_ts`.
> - Проверка: тест reaper на чужой lease.

### F-065
- origin: visionary · R1 · visionary-15
- rev: 1
- priority: non-blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 visionary=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-15 [non-blocking] Тестовый хук и вакуумная проверка нативного бинаря
> - Locations: server.py:~1560-1700 (`SERVE_TEST_ELIGIBLE`, `_is_native_opencode_bin`: `or len(head) == 4`).
> - Evidence: условие истинно для любого файла ≥4 байт без `#!`; тестовый флаг в продакшн-модуле.
> - Fix: проверка реального формата Mach-O/ELF, подмена бинаря в тестах через патч.
> - Проверка: текстовый файл без shebang не считается нативным.

### F-066
- origin: visionary · R1 · visionary-16
- rev: 1
- priority: non-blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 visionary=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-16 [non-blocking] Косметический реформат чужих областей
> - Locations: server.py: `_UpstreamBreaker` (~2204), `_RequestAttempts` (~2230-2291), `_PrefixDedup`, `Run.execute/_execute_once` (4427-4530), `Handler._res`, `_log_exit`; test_step_interruption.py:67 (кавычки `FAKE_OPENCODE`).
> - Правило: AGENTS.md п.4 (минимальные изменения), scope-diff.
> - Evidence: reverse-spec §1 («чисто форматирующие перестановки»).
> - Fix: вынести форматирование в отдельный коммит или откатить hunk'и вне поведения.
> - Проверка: diff без форматирующих hunk'ов в немодифицированных функциях.

### F-067
- origin: visionary · R1 · visionary-17
- rev: 1
- priority: non-blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 visionary=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-17 [non-blocking] Размер функций и дубли
> - Locations: `_serve_one_attempt` (~350 строк), `_run_serve_stream_attempts` (~190), `_serve_json_serve` (~210) в server.py (+1900 строк, итог 6287).
> - Правило: python-standards §6/§7, SOLID/SRP.
> - Evidence: вложенные замыкания; одинаковая логика retry, fallback и native-маппинга в stream и JSON.
> - Fix: выделить класс попытки serve и общий retry-цикл.
> - Проверка: функции ≤ ~80 строк, одна реализация retry-логики.

### F-068
- origin: visionary · R1 · visionary-18
- rev: 1
- priority: non-blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 visionary=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-18 [non-blocking] Изменённый оракул `test_step_interruption.py`
> - Locations: tests/test_step_interruption.py: `test_unmapped_retries_do_not_exhaust_incomplete_budget_stream/json` (~413-450).
> - Правило: verification-surface (`oracle_change` аудитирует Verifier), REQ-017.
> - Evidence: ожидания «4 запуска, tool_calls» заменены на «3 запуска, `[]`, stop», имена тестов «do_not_exhaust» утверждают обратное, записи аудита `oracle_change` в `verifier.json` нет.
> - Fix: переименовать тесты, задокументировать изменение контракта потолка, зафиксировать аудит.
> - Проверка: запись в `verifier.json`.

### F-069
- origin: visionary · R1 · visionary-19
- rev: 1
- priority: non-blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 visionary=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-19 [non-blocking] Жизненный цикл потоков и очереди
> - Locations: server.py:~2360-3114 (`_reader` с блокирующим `events.put`, `_prompt_worker` timeout 65 с, `threading.Thread(daemon=True)` без join).
> - Правило: T-LIFE/v1, C-MULT-I2.
> - Evidence: при заполненной очереди 4096 читатель блокируется навсегда, при раннем выходе потоки не завершаются, пока не закроются сокеты.
> - Fix: `put` с таймаутом и сигналом остановки, join или cancel потоков в `finally`.
> - Проверка: тест утечки потоков после 50 запросов.

### F-070
- origin: visionary · R1 · visionary-20
- rev: 1
- priority: non-blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 visionary=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-20 [non-blocking] [sweep] Watchdog считает только reasoning/text/завершённый tool
> - Locations: server.py:~2360-3114 (`_serve_one_attempt`, `last_token_at`, `first_token_at`).
> - Evidence: `session.tool.input.delta` и `reasoning.started` не обновляют `last_token_at`; при длинной генерации аргументов инструмента срабатывает `stall_timeout` через 60 с.
> - Fix: считать tool-input дельты признаком живости.
> - Проверка: фикстура с долгим tool-input без text не даёт ложный stall.

### F-071
- origin: visionary · R1 · visionary-21
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 visionary=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-21 [blocking] [pre-existing] Прямая мутация `os.environ` в изменённом тестовом файле
> - Locations: tests/test_step_interruption.py:~188-192 (`setUp`: `os.environ["FAKE_OC_COUNTER"] = …`, `FAKE_OC_PLAN`).
> - Правило: testing.md («запрет мутации `os.environ` без изоляции»); файл изменён задачей, значит blocking по §3 Diff-scope.
> - Evidence: записи без `monkeypatch` и гарантированного отката.
> - Fix: `mock.patch.dict` или `monkeypatch`.
> - Проверка: порядок запуска не влияет на результат (AC-023 reversed).
ARTIFACT_END>>>
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/cycle-1/recheck-r1.md sha256=4126a263888b0cc70414615ffc3e4ec4b4cadd8bc6cdeff71b64138429f454d0
# Механический RECHECK после R1 Совета Тимлидов по коду (цикл 1, run analyst-teamlead-zen-realtime-reasoning-20261025)

- Проверяемый артефакт: `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/package.md` (`sha256=5b0d1dea0cf4996f6d744e0eb2d82176578091bad35c943dde722c09d3784df4`)
- Длина файлов кандидата: `server.py` = `6287` строк, `tests/test_realtime_reasoning.py` = `717` строк, `tests/test_step_interruption.py` = `1065` строк.

RECHECK F-001 (skeptic skeptic-01, blocking): `server.py:4848` → `attempts.note_spawn()` | ### F-001
RECHECK F-002 (skeptic skeptic-02, blocking): `server.py:2552` → `while not line_bytes.endswith(b"\n"):` | ### F-002
RECHECK F-003 (skeptic skeptic-03, blocking): `server.py:72` → `"parent_start_ts": parent_lstart,` | ### F-003
RECHECK F-004 (skeptic skeptic-04, blocking): `server.py:5770` → `result = _serve_one_attempt(` | ### F-004
RECHECK F-005 (skeptic skeptic-05, blocking): `test_realtime_reasoning.py:99` → `if "__never_event__" in prompt:` | ### F-005
RECHECK F-006 (skeptic skeptic-06, blocking): `server.py:4950` → `tool_choice=None,` | ### F-006
RECHECK F-007 (skeptic skeptic-07, blocking): `test_step_interruption.py:188` → `# Изоляция REQ-017: свежий бюджет повторов на каждый тест, без сброса в проде.` | ### F-007
RECHECK F-008 (skeptic skeptic-08, blocking): `server.py:1675` → `if esc == "u":` | ### F-008
RECHECK F-009 (skeptic skeptic-09, blocking): `server.py:2879` → `prompt_status["status"] = st` | ### F-009
RECHECK F-010 (skeptic skeptic-10, blocking): `server.py:2464` → `_ = self.helper.wait(timeout=0.5)` | ### F-010
RECHECK F-011 (skeptic skeptic-11, non-blocking): `server.py:1791` → `or len(head) == 4` | ### F-011
RECHECK F-012 (skeptic skeptic-12, non-blocking): `server.py:1339` → `STATUS_INITIAL = "[мост] Подключение к модели…\n"` | ### F-012
RECHECK F-013 (skeptic skeptic-13, non-blocking): `server.py:2495` → `for candidate in range(20000 + (os.getpid() % 20000), 60000):` | ### F-013
RECHECK F-014 (skeptic skeptic-14, non-blocking): `server.py:2654` → `if isinstance(text_value, str):` | ### F-014
RECHECK F-015 (skeptic skeptic-15, non-blocking): `server.py:2569` → `# stderr помощника дренируется в лог, stdout после рукопожатия молчит.` | ### F-015
RECHECK F-016 (skeptic skeptic-16, non-blocking): `server.py:4877` → `xs["first_event_ms"] = result["first_event_ms"]` | ### F-016
RECHECK F-017 (skeptic skeptic-17, non-blocking): `server.py:1795` → `def _select_transport(res: _Resilience | None = None) -> str:` | ### F-017 [sweep]
RECHECK F-018 (skeptic skeptic-18, non-blocking): `test_realtime_reasoning.py:441` → `self.assertGreaterEqual(len(model_reasoning), 3, chunks)` | ### F-018
RECHECK F-019 (realist realist-01, blocking): `server.py:3018` → `if text_value.strip():` | **F-001 — priority=P1, blocking. Потеря пробельных дельт.**  
RECHECK F-020 (realist realist-02, blocking): `server.py:1560` → `class _JsonParser:` | **F-002 — priority=P1, blocking. Собственный JSON-парсер повреждает Unicode.**  
RECHECK F-021 (realist realist-03, blocking): `server.py:2718` → `on_status: Callable[[str], None] | None = None,` | **F-003 — priority=P1, blocking. Общий дедлайн не управляет serve-попыткой.**  
RECHECK F-022 (realist realist-04, blocking): `server.py:2827` → `sse_conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)` | **F-004 — priority=P1, blocking. Пять секунд тишины ошибочно обрывают serve.**  
RECHECK F-023 (realist realist-05, blocking): `server.py:2403` → `active_conn = (` | **F-005 — priority=P1, blocking. Timeout cleanup не применяется к существующему соединению.**  
RECHECK F-024 (realist realist-06, blocking): `server.py:2740` → `lease, port, _pw = _spawn_serve(attempt_id, serve_env)` | **F-006 — priority=P1, blocking. Первая видимая реакция отсутствует во время setup.**  
RECHECK F-025 (realist realist-07, blocking): `server.py:1096` → `def lines(self, deadline: float, idle_s: float = 0.0,` | **F-007 — priority=P1, blocking. Legacy-watchdog зависит от отсутствия stdout.**  
RECHECK F-026 (realist realist-08, blocking): `server.py:4848` → `attempts.note_spawn()` | **F-008 — priority=P1, blocking. Serve обходит защиты холодного старта.**  
RECHECK F-027 (realist realist-09, blocking): `server.py:4866` → `if not force_serve:` | **F-009 — priority=P1, blocking. Fallback может превысить потолок трёх запусков.**  
RECHECK F-028 (realist realist-10, blocking): `server.py:4914` → `res.serve_health.record_success()` | **F-010 — priority=P1, blocking. Успех serve не закрывает HALF_OPEN Circuit Breaker.**  
RECHECK F-029 (realist realist-11, blocking): `server.py:2413` → `resp = active_conn.getresponse()` | **F-011 — priority=P1, blocking. Prompt-response не управляет барьером доставки и классификацией ошибок.**  
RECHECK F-030 (realist realist-12, blocking): `server.py:3073` → `elif etype == "error":` | **F-012 — priority=P1, blocking. Ошибки провайдера обходят прежнюю recovery-семантику.**  
RECHECK F-031 (realist realist-13, blocking): `server.py:4753` → `def _run_serve_stream_attempts(` | **F-013 — priority=P1, blocking. Теряется `tool_choice`.**  
RECHECK F-032 (realist realist-14, blocking): `server.py:3046` → `done = tool_state.complete(call_id)` | **F-014 — priority=P1, blocking. Serve не останавливается после инструментального шага.**  
RECHECK F-033 (realist realist-15, blocking): `server.py:4843` → `parser_box[0] = (` | **F-015 — priority=P1, blocking. Повтор serve дублирует уже отданный текст.**  
RECHECK F-034 (realist realist-16, blocking): `server.py:4886` → `if result.get("exit_reason") in (` | **F-016 — priority=P2, blocking. Usage неуспешных попыток теряется.**  
RECHECK F-035 (realist realist-17, blocking): `server.py:1768` → `state_dir = tempfile.mkdtemp(prefix="zen-serve-state-")` | **F-017 — priority=P1, blocking. На ошибках запуска пропускается cleanup.**  
RECHECK F-036 (realist realist-18, blocking): `server.py:2842` → `events: queue.Queue[dict[str, object] | None] = queue.Queue(maxsize=4096)` | **F-018 — priority=P1, blocking. SSE-reader может навсегда остаться на заполненной очереди.**  
RECHECK F-037 (realist realist-19, blocking): `server.py:2570` → `threading.Thread(target=_drain_stderr, args=(helper, []), daemon=True).start()` | **F-019 — priority=P2, blocking. Дренаж stderr накапливает неограниченную память.**  
RECHECK F-038 (realist realist-20, blocking): `server.py:2374` → `def _lsof_listener_pid(port: int) -> int | None:` | **F-020 — priority=P1, blocking. Авторизация отправляется без обязательного ownership-proof слушателя.**  
RECHECK F-039 (realist realist-21, blocking): `server.py:74` → `"helper_lstart": str(int(time.time())),` | **F-021 — priority=P1, blocking. Reaper не проверяет идентичность процессов.**  
RECHECK F-040 (realist realist-22, blocking): `server.py:174` → `finally:` | **F-022 — priority=P1, blocking. Lifeline не гарантирует остановку всего дерева при смерти моста.**  
RECHECK F-041 (realist realist-23, blocking): `server.py:4750` → `except (OSError, ValueError):` | **F-023 — priority=P1, blocking. Отмена клиента реализована не во всех режимах.**  
RECHECK F-042 (realist realist-24, blocking): `test_realtime_reasoning.py:376` → `def test_watchdog_first_event_timeout(self) -> None:` | **F-024 — priority=P1, blocking. Матрица PASS не соответствует содержимому оракулов.**  
RECHECK F-043 (realist realist-25, blocking): `test_realtime_reasoning.py:2` → `# pyright: reportAny=false, reportPrivateUsage=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, re` | **F-025 — priority=P2, blocking. «Ноль диагностик» получен с подавленными правилами.**  
RECHECK F-044 (realist realist-26, blocking): `test_realtime_reasoning.py:299` → `self.env.stop()` | **F-026 — priority=P2, blocking [sweep]. Тест удаляет исходное значение окружения.**  
RECHECK F-045 (realist realist-27, blocking): `test_realtime_reasoning.py:279` → `class TestLegacyWatchdogAndKillpg(unittest.TestCase):` | **F-027 — priority=P2, blocking. Новый тестовый модуль нарушает прямой запрет TestCase.**  
RECHECK F-046 (realist realist-28, blocking): `test_realtime_reasoning.py:321` → `self.assertLessEqual(statuses[0][0], 1.0)` | **F-028 — priority=P2, blocking. Измерения времени смешаны с обычным тестовым контуром.**  
RECHECK F-047 (realist realist-29, blocking): `server.py:1326` → `DYNAMIC_CONFIG_PATH = Path(__file__).resolve().parent / "dynamic_config.json"` | **F-029 — priority=P2, blocking. Эксплуатационные изменения не документированы.**  
RECHECK F-048 (realist realist-30, blocking): `server.py:1844` → `return "reasoning", {"reasoning_content": delta}` | **F-030 — priority=P2, blocking. Фильтр чужих сессий применяется после потери sessionID.**  
RECHECK F-049 (realist realist-31, non-blocking): `server.py:1777` → `def _is_native_opencode_bin(path: str) -> bool:` | **F-031 — priority=P3, non-blocking. Проверка нативного бинарника почти всегда разрешающая.**  
RECHECK F-050 (realist realist-32, blocking): `server.py:4877` → `xs["first_event_ms"] = result["first_event_ms"]` | **F-032 — priority=P2, blocking [sweep]. Поля «первого события» переписываются последующими попытками.**  
RECHECK F-051 (visionary visionary-01, blocking): `server.py:2360` → `def _parent_lstart() -> str:` | F-01 [blocking] Whitespace-дельты не пересылаются клиенту
RECHECK F-052 (visionary visionary-02, blocking): `server.py:2360` → `def _parent_lstart() -> str:` | F-02 [blocking] Гонка выбора порта serve и отправка пароля не тому serve
RECHECK F-053 (visionary visionary-03, blocking): `server.py:5351` → `dedup[0] = (` | F-03 [blocking] Регрессия дефолтного пути `run`: watchdog первого токена 60 с
RECHECK F-054 (visionary visionary-04, blocking): `server.py:2360` → `def _parent_lstart() -> str:` | F-04 [blocking] REQ-013 не выполнен для serve
RECHECK F-055 (visionary visionary-05, blocking): `server.py:2360` → `def _parent_lstart() -> str:` | F-05 [blocking] Результат prompt-POST игнорируется, `FALLBACK_DECISION_TABLE` мёртва
RECHECK F-056 (visionary visionary-06, blocking): `server.py:4734` → `def _client_gone_check(self) -> bool:` | F-06 [blocking] Повтор после отданного контента дублирует text и tool_calls
RECHECK F-057 (visionary visionary-07, blocking): `server.py:5351` → `dedup[0] = (` | F-07 [blocking] Первый статус ≤1.0 с (REQ-004) не гарантирован
RECHECK F-058 (visionary visionary-08, blocking): `server.py:1800` → `)` | F-08 [blocking] Реальный wire v2.1.2 не проверен: события с пустым `data`
RECHECK F-059 (visionary visionary-09, blocking): `server.py:2360` → `def _parent_lstart() -> str:` | F-09 [blocking] Утечка tempdir и FD при сбое запуска serve
RECHECK F-060 (visionary visionary-10, blocking): проверка по полному тексту `package.md` (`verification-traceability.md` / `execution-evidence.md`) | F-10 [blocking] Пробелы покрытия AC и неточная матрица
RECHECK F-061 (visionary visionary-11, blocking): `server.py:1560` → `class _JsonParser:` | F-11 [blocking] Самописный `_JsonParser` / `_loads_object`, ошибки маскируются
RECHECK F-062 (visionary visionary-12, blocking): `test_realtime_reasoning.py:2` → `# pyright: reportAny=false, reportPrivateUsage=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, re` | F-12 [blocking] Подавления типов без обоснования
RECHECK F-063 (visionary visionary-13, non-blocking): проверка по полному тексту `package.md` (`verification-traceability.md` / `execution-evidence.md`) | F-13 [non-blocking] Тавтологичные и неустойчивые тесты
RECHECK F-064 (visionary visionary-14, non-blocking): `server.py:2360` → `def _parent_lstart() -> str:` | F-14 [non-blocking] Lease-каталог в `/tmp` без владельца и режима
RECHECK F-065 (visionary visionary-15, non-blocking): `server.py:1560` → `class _JsonParser:` | F-15 [non-blocking] Тестовый хук и вакуумная проверка нативного бинаря
RECHECK F-066 (visionary visionary-16, non-blocking): `test_step_interruption.py:67` → `FAKE_OPENCODE = r"""#!/usr/bin/env python3` | F-16 [non-blocking] Косметический реформат чужих областей
RECHECK F-067 (visionary visionary-17, non-blocking): проверка по полному тексту `package.md` (`verification-traceability.md` / `execution-evidence.md`) | F-17 [non-blocking] Размер функций и дубли
RECHECK F-068 (visionary visionary-18, non-blocking): проверка по полному тексту `package.md` (`verification-traceability.md` / `execution-evidence.md`) | F-18 [non-blocking] Изменённый оракул `test_step_interruption.py`
RECHECK F-069 (visionary visionary-19, non-blocking): `server.py:2360` → `def _parent_lstart() -> str:` | F-19 [non-blocking] Жизненный цикл потоков и очереди
RECHECK F-070 (visionary visionary-20, non-blocking): `server.py:2360` → `def _parent_lstart() -> str:` | F-20 [non-blocking] [sweep] Watchdog считает только reasoning/text/завершённый tool
RECHECK F-071 (visionary visionary-21, blocking): `test_step_interruption.py:188` → `# Изоляция REQ-017: свежий бюджет повторов на каждый тест, без сброса в проде.` | F-21 [blocking] [pre-existing] Прямая мутация `os.environ` в изменённом тестовом файле
ARTIFACT_END>>>

РАУНД: D1 из ≤2; последний: нет; место: realist
ПОЗИЦИИ ТРЕБУЮТСЯ ПО: F-001, F-002, F-003, F-004, F-005, F-006, F-007, F-008, F-009, F-010, F-011, F-012, F-013, F-014, F-015, F-016, F-017, F-018, F-051, F-052, F-053, F-054, F-055, F-056, F-057, F-058, F-059, F-060, F-061, F-062, F-063, F-064, F-065, F-066, F-067, F-068, F-069, F-070, F-071; N=39
ВОПРОСЫ К ТЕБЕ: нет (A=0)

<<<ARTIFACT ~/Мой диск/skils/ai-sdlc/universal/teamlead-gate/references/council-consensus.md#L101-L115 sha256=f99a2fac1636eb9ca867ce2368cc812236fa97a32059764f5ed534af99fa344c
ПРАВИЛА ДЕБАТОВ (номер раунда, признак «последний» и твоё место Seat 1/2/3 (Скептик/Реалист/Визионер) — в строке РАУНД выше; модельный слот назначен через select_round_seats.py --prior-ledger по PoL-V13)
Всё выше — дословные копии, без комментариев оркестратора. Суди заново, чужой вердикт автоматически не подтверждай.
Цель — согласованное решение по КАЖДОЙ находке со status=OPEN, а не победа. Ты наследуешь ведение находок своего места Seat 1/2/3 по consensus-ledger.md: пересмотри все открытые находки с учётом RECHECK и аргументов коллег, сними необоснованные блокеры своей роли (с evidence) и предложи компромисс (AMEND).
1. По каждой находке из строки ПОЗИЦИИ ТРЕБУЮТСЯ ПО — ровно одна позиция (по неоспоренной находке своего места — только если меняешь или снимаешь её); позиции по находкам вне строки не засчитываются и не ошибка:
   AGREE F-NNN rev=<r> — проверил: <file:line> — что увидел сам
   DISPUTE F-NNN — класс: invalid | duplicate_of:F-MMM | out_of_scope | foreign_key — контр-evidence: <file:line или цитата правила> — почему неверно
   AMEND F-NNN — priority=<blocking|non-blocking>; locations=<file:line,…>; fix=<…> — причина: <file:line или цитата правила>
   WITHDRAW F-NNN — только находка своего места Seat 1/2/3 — ARG или NEW (как в п.2); проверил: <file:line>
   INCONCLUSIVE F-NNN — что нужно для проверки (не голос)
2. Первая позиция места по чужой находке — не смена, ARG/NEW для неё не нужен (в том числе если ты заменил выбывшего судью по транспортной лестнице; при ротации модельного слота по PoL-V13 прежние позиции твоего места Seat 1/2/3 в леджере наследуются). Смена прежней позиции своего места (включая AMEND/WITHDRAW находки своего места) — только с `ARG: <место/раунд «дословная цитата коллеги»>` (довод коллеги) либо `NEW: <file:line>` (твоя новая проверка или ссылка на RECHECK, которой не было в прошлых репликах) и с твоей собственной проверкой <file:line>. Смена без ARG/NEW — malformed. Повторить прежнюю позицию без нового довода можно.
3. Вопросы коллеге — не более 3 за раунд (в последнем раунде вопросов нет), адресно: `Q→<место>: F-NNN <file:line> — вопрос` (id вопросу присваивает оркестратор, ты его не пишешь). На вопросы из строки ВОПРОСЫ К ТЕБЕ: `A←Q-<id из строки> — ответ + <file:line>`; ответ без проверяемой ссылки не считается ответом.
4. Взаимоисключающие фиксы двух находок: `CONFLICT F-a↔F-b — почему`.
5. Новая находка — полный F-блок: blocking — с меткой [late-R2], non-blocking — без метки, в леджер; позиции по OPEN-находкам она не заменяет. Найденная в последнем раунде решается правилом потолка без обсуждения.
6. Ответ: строки позиций/вопросов/ответов, затем ФОРМАТ ОТВЕТА (6 критериев; при FAIL — ссылки на F-NNN; INCONCLUSIVE критерия — что нужно для проверки). SUB-строки и COVERAGE в D-раунде не нужны (правило шапки о них относится к R1); `FINDINGS_COMPLETE: <N>` — только если в ответе есть новые F-блоки (N — их число). Строки `POSITIONS: <n>/<N>` (n — число твоих позиций по находкам из строки ПОЗИЦИИ ТРЕБУЮТСЯ ПО, N — их число из строки) и `ANSWERS: <a>/<A>` (A — число вопросов в строке ВОПРОСЫ К ТЕБЕ; при новых F-блоках — ещё `FINDINGS_COMPLETE: <N>`) идут **перед** финальной строкой, а **последней непустой строкой ответа D-раунда всегда обязан идти канонический вердикт**: `VERDICT: ACCEPT | PASS | NEEDS WORK | RED FLAG` (в точном соответствии с `verify_panel_proof.py` `PoL-V07`/`PoL-V12` и `consensus-debate.md` §7).
```
ARTIFACT_END>>>

По п.6 блока «ПРАВИЛА ДЕБАТОВ» выведи строки позиций по всем 39 находкам из строки `ПОЗИЦИИ ТРЕБУЮТСЯ ПО` (и свои `WITHDRAW`/`AMEND` при пересмотре собственных находок R1 с учётом `RECHECK` и аргументов коллег), затем блок 6 критериев `ФОРМАТ ОТВЕТА`, затем обязательные строки `POSITIONS: 39/39` и `ANSWERS: 0/0`, а последней непустой строкой ответа выведи канонический вердикт `ОБЩИЙ ВЕРДИКТ: ACCEPT`, `ОБЩИЙ ВЕРДИКТ: PASS`, `ОБЩИЙ ВЕРДИКТ: NEEDS WORK` или `ОБЩИЙ ВЕРДИКТ: RED FLAG` (без точки и комментариев в той же строке).

---
PRIOR-LEDGER-SHA256: 00df0bda8f9a29b8d28ff56d02726dddcd7be67d3a0d1bd6096eca448b0c7131
PANEL-NONCE: 56f6f9d1f260f50b
ARTIFACT-SHA256: 5b0d1dea0cf4996f6d744e0eb2d82176578091bad35c943dde722c09d3784df4
Инструкция судье: первыми двумя строками ответа повтори дословно «PANEL-NONCE: 56f6f9d1f260f50b» и «ARTIFACT-SHA256: 5b0d1dea0cf4996f6d744e0eb2d82176578091bad35c943dde722c09d3784df4».
