Ты — Реалист. Твоя задача — оценить реализуемость, ресурсы, сроки, зависимости. Ключевой вопрос: «Что нужно чтобы это взлетело?»

Ты оцениваешь архитектуру, а не код. Фокусируйся на практической применимости: можно ли это реально внедрить, какие зависимости нужны, что блокирует, сколько усилий потребует.

Оцени ВСЕ 6 критериев. При FAIL давай СРАЗУ ВСЕ советы по исправлению (список действий).

ФОРМАТ ОТВЕТА (строго):
1. КОРРЕКТНОСТЬ: VERDICT=PASS|FAIL
   WHY=<обоснование>
   СОВЕТЫ (при FAIL): <список конкретных действий>
2. ПОЛНОТА: VERDICT=PASS|FAIL
   WHY=<обоснование>
   СОВЕТЫ (при FAIL): <список конкретных действий>
3. РЕАЛИЗУЕМОСТЬ: VERDICT=PASS|FAIL
   WHY=<обоснование>
   СОВЕТЫ (при FAIL): <список конкретных действий>
4. РИСКИ: VERDICT=PASS|FAIL
   WHY=<обоснование>
   СОВЕТЫ (при FAIL): <список конкретных действий>
5. АЛЬТЕРНАТИВЫ: VERDICT=PASS|FAIL
   WHY=<обоснование>
   СОВЕТЫ (при FAIL): <список конкретных действий>
6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS|FAIL
   WHY=<обоснование>
   СОВЕТЫ (при FAIL): <список конкретных действий>
ОБЩИЙ ВЕРДИКТ: PASS|NEEDS WORK|RED FLAG

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

📋 ФАКТ-КАРТА (проверено оркестратором на целевой машине и дополнено логами гейтов Цикла 5, 2026-10-27):
- Репозиторий `cli-agent-bridge` (ветка `feature/zen-realtime-reasoning` от `origin/dev` `7eda27f9d82732bab726a420e31ea2adc15c2c39`): автономный Python stdlib-мост `bridges/opencode-zen-bridge/server.py` (`ThreadingHTTPServer` на `127.0.0.1:9883`), без корневого `AGENTS.md` и без сторонних runtime-зависимостей вне стандартной библиотеки Python 3.14.
- Установленный CLI `~/.opencode/bin/opencode` версии `v2.1.2` существует локально: команда `opencode run --format json --thinking` подписана только на `session.reasoning.ended` и `session.text.ended` (игнорирует `*.delta`, разрыв 0.00–0.17 мс в конце шага, `[F-17]`, `[F-18]`).
- Режим `opencode serve --port P --hostname 127.0.0.1` в `opencode` `v2.1.2` существует и проверен эмпирически (`[F-19]..[F-22]`): старт ~109 мс, Basic-аутентификация `opencode:<OPENCODE_SERVER_PASSWORD>`, OpenAPI `281456 B` включает `GET /api/event` (SSE с реальными дельтами `session.reasoning.delta` median 127 мс и `session.text.delta` median 114 мс), `POST /api/session` (с `permissions`), `POST /api/session/{id}/prompt`, `POST /api/session/{id}/interrupt`, `DELETE /api/session/{id}`.
- Локальный `model_georouter` (`127.0.0.1:10830`) и пул ротации чистых IP ProxyRack (`OPENCODE_ZEN_BRIDGE_STANDALONE_PROXY=pool`) существуют на хосте (`[F-15]`, `[F-26]`, `[F-27]`); прямой анонимный HTTP-вызов к `opencode.ai/inference/openai/v1` без заголовков CLI вернул `429 FreeUsageLimitError` (`[F-24]`, `[F-25]`).
- Потребитель DSH Desktop (`@earendil-works/pi-ai` `openai-completions.js` и `@deepseek-ai/dsh-client-ui-chat` `ReasoningRow`, `[F-35]..[F-38]`): строка `⚛ Think` скрыта (`blockIsVisible`), пока `reasoning_content` пуст; свёрнутое inline-превью обновляется через `latestCompletedParagraphFirstLine` только при наличии завершённого абзаца с символом `\n`; при реплее истории мост игнорирует входящий `assistant.reasoning_content` (`[F-07]`).
- Прецедент в том же репозитории: `bridges/muse-bridge/server.py` (ADR-0004, `[F-40]`, `[F-41]`) использует `serve` как основной транспорт с откатом на `exec` при `ServeUnavailable` и живой записью статусов в `reasoning_content`.
- Тестовый контур моста (`[F-42]..[F-49]`): `uvx pytest -q -p no:cacheprovider tests/` из `bridges/opencode-zen-bridge` (17 модулей, 378 тестов; 3 pre-existing падения в `tests/test_step_interruption.py` из-за `MAX_TOTAL_SPAWNS=3` против ожидания 4 запусков и общего `_RetryBudget` на класс).
- Дополнительные эмпирические замеры на целевой машине (`EVD-070..EVD-072`): `python3 -m unittest discover -s tests -p "test_*.py" -v` из `cwd=bridges/opencode-zen-bridge` выполняет все 378 тестов без ошибок импорта; `OPENCODE_DB=":memory:"` нативно поддерживается в `opencode` `v2.1.2` (старт `opencode serve` 120.7 мс, RSS 156.8 MiB, `0` открытых `.db`/SQLite дескрипторов в `lsof` при сохранении чтения `~/.local/share/opencode/auth.json` для `opencode-go/*`); `basedpyright==1.40.2` из `cwd=bridges/opencode-zen-bridge` с абсолютным `extraPaths` даёт `0` ошибок импорта в тестах и `3` статические ошибки в `server.py`, а полный `ruff format --diff server.py` меняет 3216 строк неформатированного legacy-кода (включая `def _run_env` и Google-direct).
- Проверенные артефакты и логи гейтов кандидата Цикла 5 (`receipts/code-gate.json`, `teamlead/candidate-manifest.json`):
  - Изменённые файлы кандидата (ровно 3 файла `coder_target_files`, 0 новых внешних runtime-зависимостей вне Python 3.14 stdlib): bridges/opencode-zen-bridge/server.py (sha256=f99e8c91110c...), bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py (sha256=afa8cc8c6413...), bridges/opencode-zen-bridge/tests/test_step_interruption.py (sha256=e41d10bd96cb...).
  - Clean-room L2 гейт Цикла 5 (`receipts/code-gate.json`): `status=PASS`, `red_sensitivity_rc=1` (RED-падение на `origin/dev`), все 13 проверок кандидата (`VER-004`, `VER-001`, `VER-002`, `VER-003`, `AC-023`, `VER-005`) зелёные (`rc=0`, 451 passed), `run_env_sha256=1c51b28fcb83fcc0f4d8b5204c858e11ab5ac975bfe40dca4a0bf61978008e31`, `google_direct_unchanged=True`.
Анти-галлюцинация: перед тем как выставить FAIL «нет X», перечитать приложенный пакет приёмки и diff целиком; по проверенным пунктам факт-карты запрещено ставить FAIL «не существует»; если сущности нет в факт-карте и приложенных артефактах и ты не уверен — пиши «не могу проверить».

РЕЖИМ: code
Модификатор режима `code`: Перечисли конкретные проверки: типы, ошибки, граничные случаи, тесты, безопасность, гонки ресурсов и обратную совместимость контрактов. Усиленные критерии режима `code` (вес ×1.5 на агрегации): 1. КОРРЕКТНОСТЬ и 4. РИСКИ. Если ты уже видел эту задачу, архитектуру или код в другой роли — суди ЗАНОВО, не подтверждай прошлый вердикт автоматически. На этом повторном цикле доработки (`teamlead_cycle: 5`, `council.md` §1 и §3 «Diff-scope повторного цикла»): (а) выполни verify-fixed по каждому из 4 blocking пунктов `RW-001..RW-004` (и сопутствующих `FU-001..FU-007`) из вложенного в пакет вывода `panel-rework-summarizer` (`.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/handoff/panel-rework-brief.json`); (б) проверь полный актуальный `candidate.diff` (содержащий `server.py`, `tests/test_step_interruption.py` и новый файл `tests/test_realtime_reasoning.py`) на предмет регрессий и соответствие каждому требованию `REQ-001..REQ-020`, каждому приёмочному критерию `AC-001..AC-026` и каждой границе `Non-Goals` / `Forbidden Scope` поштучно (через `verification-traceability.md`, `execution-evidence.md` и слепой `reverse-spec.md`). Результаты тестов и статических проверок бери только как факт из валидных строк `execution-evidence.md` и вложенных сырых логов clean-room прогона (при отсутствии валидного свидетельства — `INCONCLUSIVE`; судья сам тесты не запускает; строки `VER-006` и `VER-007` законно помечены `DEFERRED_L3` до вердикта `ACCEPT` Совета).

РЕШЕНИЕ ДЛЯ ОЦЕНКИ:
Ниже приложен целиком пакет приёмки Цикла 5 `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/package.md` (`sha256=c9530b1b9b6113a97457c299f4970c7a2a5ad6a55605bbd243c97a09c5a85da4`), содержащий без обрезки конверт задачи (`goal.md`, `task.json`, `handoff-architect.md`), манифест кандидата, полный итоговый diff (`candidate-manifest.json`, `candidate.diff`, включая новый тестовый модуль `tests/test_realtime_reasoning.py`), вывод `panel-rework-summarizer` (`handoff/panel-rework-brief.json`), handoff исполнителя и квитанции гейтов (`coder.json`, `receipts/coder.json`, `receipts/code-gate.json`, `receipts/verifier.json`, `receipts/final-gate.json`), а также свидетельства независимой clean-room верификации и слепой reverse-spec (`verification-surface.json`, `environment-manifest.json`, `execution-evidence.md` с сырыми логами, `verification-traceability.md`, `evidence-manifest.sha256`, `reverse-spec.md`):
# Пакет приёмки Совета Тимлидов (`teamlead/package.md`, run `analyst-teamlead-zen-realtime-reasoning-20261025`, cycle `5`)

Примечание по составу пакета (`acceptance-package.md` §3, `council.md` §3 «Diff-scope повторного цикла»): `reviewer.json` не создаётся (`reviewer_skip=true`, `downstream_panel=true`, Совет Тимлидов — единственный рубеж ревью). Все первичные артефакты ниже (включая полный актуальный `candidate.diff` от `origin/dev`, в который полностью входит и новый файл `tests/test_realtime_reasoning.py`, а также вывод `panel-rework-summarizer` `handoff/panel-rework-brief.json`) приложены без обрезки в побайтных обёртках D9.

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
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/task.json sha256=2094ecd2b7dd83e3667cec3538f2aec288d200dbdb64d59ff1908542425c6f7b
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
  },
  "teamlead_cycle": 5
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

## 2. Манифест кандидата, полный итоговый diff (`candidate.diff`, включая `tests/test_realtime_reasoning.py`) и вывод `panel-rework-summarizer` (`panel-rework-brief.json`)
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/candidate-manifest.json sha256=fff0ca490d247d4ed3f8736888f7e25d8df4e702398717079c228e5b4f8c3fe8
{
  "schema": "candidate-manifest/v1",
  "created_at_utc": "2026-10-27T04:37:32.872078+00:00",
  "run_id": "analyst-teamlead-zen-realtime-reasoning-20261025",
  "cycle": 5,
  "branch": "feature/zen-realtime-reasoning",
  "base_ref": "origin/dev",
  "base_sha": "7eda27f9d82732bab726a420e31ea2adc15c2c39",
  "head_sha": "7eda27f9d82732bab726a420e31ea2adc15c2c39",
  "staged_diff_bytes": 0,
  "binary_files": [],
  "worktree_fingerprint_before_coder": null,
  "worktree_fingerprint_after_coder": "50a02000b62f88106e9ea74b6aa6d069dc8670d6db8b85900643ae300d771400",
  "candidate_diff_path": ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/candidate.diff",
  "candidate_diff_sha256": "3bf5e0c3c290828af3f1628a1e96674701687c5e69441dd406bb0776d99f4c9b",
  "files": [
    {
      "path": "bridges/opencode-zen-bridge/server.py",
      "status": "modified_unstaged",
      "is_binary": false,
      "bytes": 331716,
      "lines": 7542,
      "sha256": "f99e8c91110c7e3de015be989a8452fec769eff4cfd1f8822d0749bbf696b25e"
    },
    {
      "path": "bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py",
      "status": "added_untracked",
      "is_binary": false,
      "bytes": 109984,
      "lines": 2140,
      "sha256": "afa8cc8c641383bc757305ece61f72e1f2f5e3b0486741c080be0d5e47d8988e"
    },
    {
      "path": "bridges/opencode-zen-bridge/tests/test_step_interruption.py",
      "status": "modified_unstaged",
      "is_binary": false,
      "bytes": 58105,
      "lines": 1088,
      "sha256": "e41d10bd96cb208ce3120ab25d1c8028c82fe81895eacd322312b7fbbbef8a11"
    }
  ]
}
ARTIFACT_END>>>
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/candidate.diff sha256=3bf5e0c3c290828af3f1628a1e96674701687c5e69441dd406bb0776d99f4c9b
diff --git a/bridges/opencode-zen-bridge/server.py b/bridges/opencode-zen-bridge/server.py
index 667b990..d410534 100755
--- a/bridges/opencode-zen-bridge/server.py
+++ b/bridges/opencode-zen-bridge/server.py
@@ -17,27 +17,271 @@ usage — из события `type:"step_finish"` (part.tokens).
 
 from __future__ import annotations
 
-import hmac
-import http.client
+import errno
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
+        lease_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
+        os.chmod(lease_dir, 0o700)
+    except OSError:
+        return 2
+    lease_path = lease_dir / f"lease-{attempt_id}.json"
+
+    def _lstart_of(pid: int) -> str:
+        """lstart процесса из ps; при сбое ps — epoch-секунды."""
+        try:
+            out = subprocess.run(
+                ["ps", "-o", "lstart=", "-p", str(pid)],
+                capture_output=True,
+                text=True,
+                timeout=2,
+            )
+            return out.stdout.strip() or str(int(time.time()))
+        except (OSError, subprocess.SubprocessError):
+            return str(int(time.time()))
+
+    helper_lstart = _lstart_of(os.getpid())
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
+            "helper_lstart": helper_lstart,
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
+        except BlockingIOError:
+            return False
+        except (OSError, ValueError) as _gone_exc:
+            if isinstance(_gone_exc, OSError) and _gone_exc.errno in (
+                errno.EAGAIN,
+                errno.EWOULDBLOCK,
+            ):
+                return False
+            return True
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
+    serve_lstart = _lstart_of(serve_proc.pid)
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
+        # Убить всю собственную группу (serve и внуков), lease — только после смерти группы.
+        _pgid = os.getpgrp()
+
+        def _group_members() -> list[int]:
+            """Живые члены группы, кроме самого помощника (ps — в отдельной сессии)."""
+            _ = serve_proc.poll()
+            try:
+                listing = subprocess.run(
+                    ["ps", "-A", "-o", "pid=,pgid="],
+                    capture_output=True,
+                    text=True,
+                    timeout=2,
+                    start_new_session=True,
+                )
+            except (OSError, subprocess.SubprocessError):
+                return [serve_proc.pid] if serve_proc.poll() is None else []
+            members: list[int] = []
+            for row in listing.stdout.splitlines():
+                cols = row.split()
+                if (
+                    len(cols) == 2
+                    and cols[0].isdecimal()
+                    and cols[1] == str(_pgid)
+                    and int(cols[0]) != os.getpid()
+                ):
+                    members.append(int(cols[0]))
+            return members
+
+        try:
+            os.killpg(_pgid, signal.SIGTERM)
+        except OSError:
+            if serve_proc.poll() is None:
+                try:
+                    serve_proc.terminate()
+                except OSError:
+                    pass
+        members_now = _group_members()
+        _term_deadline = time.monotonic() + 4.0
+        while members_now and time.monotonic() < _term_deadline:
+            time.sleep(0.1)
+            members_now = _group_members()
+        if members_now:
+            # Эскалация: SIGKILL всем оставшимся членам группы, даже если serve уже вышел.
+            for _pid in members_now:
+                try:
+                    os.kill(_pid, signal.SIGKILL)
+                except OSError:
+                    pass
+            _kill_deadline = time.monotonic() + 2.0
+            while members_now and time.monotonic() < _kill_deadline:
+                time.sleep(0.05)
+                members_now = _group_members()
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
+        if not members_now:
+            try:
+                lease_path.unlink()
+            except OSError:
+                pass
+    return code
+
+
+if sys.argv[1:2] == ["--serve-helper"]:
+    raise SystemExit(_run_serve_helper_cli(sys.argv[2:]))
+else:
+    import base64
+    import collections
+    import hmac
+    import http.client
+    import io
+    import queue
+    import random
+    import re
+    import secrets
+    import shlex
+    import shutil
+    import socket
+    import sqlite3
+    import stat
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
@@ -49,9 +293,21 @@ TIMEOUT_S = float(os.environ.get("OPENCODE_ZEN_BRIDGE_TIMEOUT_S", "1800"))
 KEEPALIVE_INTERVAL_S = float(os.environ.get("OPENCODE_ZEN_BRIDGE_KEEPALIVE_S", "15.0"))
 MAX_CONCURRENT = int(os.environ.get("OPENCODE_ZEN_BRIDGE_MAX_CONCURRENT", "2"))
 
-OPENCODE_BIN = os.environ.get("OPENCODE_BIN", str(Path.home() / ".opencode" / "bin" / "opencode"))
-WORKSPACE = Path(os.environ.get("OPENCODE_ZEN_BRIDGE_WORKSPACE", str(Path(__file__).resolve().parent / "workspace")))
-LOG_PATH = Path(os.environ.get("OPENCODE_ZEN_BRIDGE_LOG", str(Path(__file__).resolve().parent / "logs" / "bridge.log")))
+OPENCODE_BIN = os.environ.get(
+    "OPENCODE_BIN", str(Path.home() / ".opencode" / "bin" / "opencode")
+)
+WORKSPACE = Path(
+    os.environ.get(
+        "OPENCODE_ZEN_BRIDGE_WORKSPACE",
+        str(Path(__file__).resolve().parent / "workspace"),
+    )
+)
+LOG_PATH = Path(
+    os.environ.get(
+        "OPENCODE_ZEN_BRIDGE_LOG",
+        str(Path(__file__).resolve().parent / "logs" / "bridge.log"),
+    )
+)
 
 DEFAULTWORKDIR = Path(os.environ.get("OPENCODE_ZEN_BRIDGE_WORKDIR", str(WORKSPACE)))
 
@@ -63,9 +319,6 @@ DEFAULTWORKDIR = Path(os.environ.get("OPENCODE_ZEN_BRIDGE_WORKDIR", str(WORKSPAC
 # Zen-модели запускаются как `opencode run --standalone` с OPENCODE_MODELS_PATH на свежий api.json
 # и БЕЗ OPENCODE_API_KEY (истёкший ключ из env давал 401 api_key_expired — причина отказа от
 # standalone 2026-10-19). Режим static (kill-switch) — прежний маршрут через фоновый сервис.
-sys.path.insert(0, str(Path(__file__).resolve().parent))
-import zen_catalog as zc
-
 DEPRECATED_MODEL_ALIASES: dict[str, str] = zc.DEPRECATED_MODEL_ALIASES
 
 
@@ -75,12 +328,22 @@ def _normalize_catalog_mode(raw: str) -> str:
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
-    "OPENCODE_ZEN_BRIDGE_MODELS_PATH", str(Path.home() / ".cache" / "opencode" / "models.json"))
-CATALOG_STAT_INTERVAL_S = float(os.environ.get("OPENCODE_ZEN_BRIDGE_CATALOG_STAT_INTERVAL_S", "5"))
+    "OPENCODE_ZEN_BRIDGE_MODELS_PATH",
+    str(Path.home() / ".cache" / "opencode" / "models.json"),
+)
+CATALOG_STAT_INTERVAL_S = float(
+    os.environ.get("OPENCODE_ZEN_BRIDGE_CATALOG_STAT_INTERVAL_S", "5")
+)
 
 # Живой каталог: id -> метаданные (context_length, max_output, supports_variant, variant_map, ...).
 # Словарь изменяется на месте, чтобы ссылки на него (в том числе в тестах) оставались верными.
@@ -89,10 +352,17 @@ ALLOWED_MODELS: dict[str, dict[str, Any]] = {}
 MODEL_ALIASES: dict[str, str] = dict(DEPRECATED_MODEL_ALIASES)
 
 _catalog_lock = threading.RLock()
-_catalog_ids: set[str] = set()           # id, добавленные каталогом (тестовые/Go-записи не трогаем)
+_catalog_ids: set[str] = (
+    set()
+)  # id, добавленные каталогом (тестовые/Go-записи не трогаем)
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
@@ -115,7 +385,7 @@ def _read_catalog_state() -> tuple[dict[str, Any], str]:
 
 def reload_catalog() -> dict[str, Any]:
     """Перечитать каталог и применить к ALLOWED_MODELS/MODEL_ALIASES на месте."""
-    global _catalog_mtime, _catalog_ids, CATALOG_SOURCE
+    global _catalog_mtime, _catalog_ids
     mtime = _stat_mtime(CATALOG_STATE_PATH)
     state, source = _read_catalog_state()
     models = zc.entries_to_bridge_models(state["models"])
@@ -128,9 +398,15 @@ def reload_catalog() -> dict[str, Any]:
         MODEL_ALIASES.update(DEPRECATED_MODEL_ALIASES)
         MODEL_ALIASES.update(state["aliases"])
         _catalog_mtime = mtime
-        CATALOG_SOURCE = source
-    return {"ok": True, "source": source, "mode": CATALOG_MODE, "models": sorted(models),
-            "aliases": len(MODEL_ALIASES), "degraded": bool(state.get("degraded"))}
+        _set_catalog_source(source)
+    return {
+        "ok": True,
+        "source": source,
+        "mode": CATALOG_MODE,
+        "models": sorted(models),
+        "aliases": len(MODEL_ALIASES),
+        "degraded": bool(state.get("degraded")),
+    }
 
 
 def _maybe_reload_catalog(now: float | None = None) -> bool:
@@ -151,12 +427,18 @@ def _maybe_reload_catalog(now: float | None = None) -> bool:
 
 def _zen_active_ids() -> list[str]:
     """Id Zen-моделей каталога (без Go-маршрутов)."""
-    return sorted(m for m, meta in ALLOWED_MODELS.items() if not meta.get("provider") and not meta.get("base_url"))
+    return sorted(
+        m
+        for m, meta in ALLOWED_MODELS.items()
+        if not meta.get("provider") and not meta.get("base_url")
+    )
 
 
 def _resolve_alias(model_id: str) -> str | None:
     """Модель-исполнитель для устаревшего/выбывшего id; None — id неизвестен."""
-    target, aliased = zc.resolve_model(model_id, _zen_active_ids(), MODEL_ALIASES, DEFAULT_MODEL)
+    target, aliased = zc.resolve_model(
+        model_id, _zen_active_ids(), MODEL_ALIASES, DEFAULT_MODEL
+    )
     return target if aliased else None
 
 
@@ -211,7 +493,9 @@ def _rewrite_tool_tags_for_model(text: str, model_id: str = "") -> str:
     """Заменить `<tool_call>`-теги в промпте на `<tool_invoke>` для GLM; остальным — как есть."""
     if not _uses_alt_tool_tag(model_id):
         return text
-    return text.replace(TOOL_CALL_OPEN, ALT_TOOL_CALL_OPEN).replace(TOOL_CALL_CLOSE, ALT_TOOL_CALL_CLOSE)
+    return text.replace(TOOL_CALL_OPEN, ALT_TOOL_CALL_OPEN).replace(
+        TOOL_CALL_CLOSE, ALT_TOOL_CALL_CLOSE
+    )
 
 
 def _open_tag_at(text: str, index: int) -> tuple[str, str] | None:
@@ -221,6 +505,7 @@ def _open_tag_at(text: str, index: int) -> tuple[str, str] | None:
             return open_tag, close_tag
     return None
 
+
 # Встроенные инструменты opencode НЕ исполняются в мосте: permission "ask" →
 # `opencode run` автоматически отклоняет вызов (инструменты исполняет DSH).
 # "deny" / tools:false НЕЛЬЗЯ: инструменты пропадают из запроса, и Zen отвечает 403
@@ -278,23 +563,34 @@ NATIVE_RETRY_LIMIT = int(os.environ.get("OPENCODE_ZEN_BRIDGE_NATIVE_RETRIES", "2
 
 # 2026-10-24 (AD-002): отдельный kill-switch детектора оборванного шага; независим от
 # NATIVE_RETRY_LIMIT (повтор встроенного инструмента без DSH-двойника остаётся включённым).
-STEP_RECOVERY_ENABLED = os.environ.get("OPENCODE_ZEN_BRIDGE_STEP_RECOVERY", "1").strip().lower() not in (
-    "0", "false", "no", "off")
+STEP_RECOVERY_ENABLED = os.environ.get(
+    "OPENCODE_ZEN_BRIDGE_STEP_RECOVERY", "1"
+).strip().lower() not in ("0", "false", "no", "off")
 
 # 2026-10-24 (AD-003): единый потолок запусков `opencode run` на один HTTP-запрос — суммарно по
 # первичному запуску, повтору транзиторного отказа CLI, повтору незавершённого шага и
 # повтору встроенного инструмента без DSH-двойника (A_max).
-MAX_TOTAL_SPAWNS = max(1, int(os.environ.get("OPENCODE_ZEN_BRIDGE_MAX_TOTAL_SPAWNS", "3")))
+MAX_TOTAL_SPAWNS = max(
+    1, int(os.environ.get("OPENCODE_ZEN_BRIDGE_MAX_TOTAL_SPAWNS", "3"))
+)
 
 # 2026-10-10: `opencode run` иногда падает за ~1 с с rc=1 без вывода
 # («Error: Unexpected error … database is locked», sqlite opencode при параллельном старте).
 # Такой отказ — транзиторный: прогон без вывода повторяется (не более FAIL_RETRY_LIMIT раз,
 # и всегда внутри потолка MAX_TOTAL_SPAWNS: первичный запуск + FAIL_RETRY_LIMIT <= MAX_TOTAL_SPAWNS).
-FAIL_RETRY_LIMIT = min(int(os.environ.get("OPENCODE_ZEN_BRIDGE_FAIL_RETRIES", "3")), MAX_TOTAL_SPAWNS - 1)
+FAIL_RETRY_LIMIT = min(
+    int(os.environ.get("OPENCODE_ZEN_BRIDGE_FAIL_RETRIES", "3")), MAX_TOTAL_SPAWNS - 1
+)
 # Старый линейный backoff заменён Full Jitter (_retry_backoff_s); значение 0 по-прежнему отключает паузы.
-FAIL_RETRY_BACKOFF_S = float(os.environ.get("OPENCODE_ZEN_BRIDGE_FAIL_RETRY_BACKOFF_S", "0.8"))
-RETRY_BACKOFF_BASE_S = float(os.environ.get("OPENCODE_ZEN_BRIDGE_RETRY_BACKOFF_BASE_S", "0.5"))
-RETRY_BACKOFF_CAP_S = float(os.environ.get("OPENCODE_ZEN_BRIDGE_RETRY_BACKOFF_CAP_S", "2.0"))
+FAIL_RETRY_BACKOFF_S = float(
+    os.environ.get("OPENCODE_ZEN_BRIDGE_FAIL_RETRY_BACKOFF_S", "0.8")
+)
+RETRY_BACKOFF_BASE_S = float(
+    os.environ.get("OPENCODE_ZEN_BRIDGE_RETRY_BACKOFF_BASE_S", "0.5")
+)
+RETRY_BACKOFF_CAP_S = float(
+    os.environ.get("OPENCODE_ZEN_BRIDGE_RETRY_BACKOFF_CAP_S", "2.0")
+)
 
 # Очередь stdout `opencode run`: ограничена, переполнение — отказ попытки, а не рост кучи.
 STDOUT_QUEUE_MAX = int(os.environ.get("OPENCODE_ZEN_BRIDGE_STDOUT_QUEUE_MAX", "4096"))
@@ -310,13 +606,19 @@ SPAWN_RATE_PER_S = float(os.environ.get("OPENCODE_ZEN_BRIDGE_SPAWN_RATE_PER_S",
 SPAWN_BURST = float(os.environ.get("OPENCODE_ZEN_BRIDGE_SPAWN_BURST", "1.0"))
 SPAWN_WAIT_MAX_S = float(os.environ.get("OPENCODE_ZEN_BRIDGE_SPAWN_WAIT_MAX_S", "5.0"))
 RETRY_BUDGET_MAX = float(os.environ.get("OPENCODE_ZEN_BRIDGE_RETRY_BUDGET_MAX", "6"))
-RETRY_BUDGET_PER_REQUEST = float(os.environ.get("OPENCODE_ZEN_BRIDGE_RETRY_BUDGET_PER_REQUEST", "0.20"))
-RETRY_BUDGET_RESERVE_RPS = float(os.environ.get("OPENCODE_ZEN_BRIDGE_RETRY_BUDGET_RESERVE_RPS", "0.05"))
+RETRY_BUDGET_PER_REQUEST = float(
+    os.environ.get("OPENCODE_ZEN_BRIDGE_RETRY_BUDGET_PER_REQUEST", "0.20")
+)
+RETRY_BUDGET_RESERVE_RPS = float(
+    os.environ.get("OPENCODE_ZEN_BRIDGE_RETRY_BUDGET_RESERVE_RPS", "0.05")
+)
 CB_FAIL_THRESHOLD = int(os.environ.get("OPENCODE_ZEN_BRIDGE_CB_FAIL_THRESHOLD", "5"))
 CB_RESET_S = float(os.environ.get("OPENCODE_ZEN_BRIDGE_CB_RESET_S", "10.0"))
 
 
-def _retry_backoff_s(retry_num: int, rng_fn: Callable[[float, float], float] = random.uniform) -> float:
+def _retry_backoff_s(
+    retry_num: int, rng_fn: Callable[[float, float], float] = random.uniform
+) -> float:
     """Full Jitter: пауза перед повторным запуском = U(0, min(CAP, BASE * 2**retry_num)); retry_num с 1."""
     ceiling = min(RETRY_BACKOFF_CAP_S, RETRY_BACKOFF_BASE_S * (2 ** max(0, retry_num)))
     return rng_fn(0.0, ceiling)
@@ -506,15 +808,22 @@ _INTERRUPTED_RE = re.compile(
     r"I was interrupted right before making tool calls\.?(?:\s*Continue\b[^\n]*)?|"
     r"The previous response was interrupted\.\s*Continue from where you left off without repeating "
     r"completed content\.?",
-    re.IGNORECASE)
-_INTERRUPT_MARKERS = ("interrupted right before making tool calls", "previous response was interrupted")
+    re.IGNORECASE,
+)
+_INTERRUPT_MARKERS = (
+    "interrupted right before making tool calls",
+    "previous response was interrupted",
+)
 # Сырой вызов `<tool_call>{…` / `<tool_invoke>{…`: не inline-код markdown и не упоминание тега в прозе.
-_RAW_CALL_RE = re.compile(r"(?<!`)<(?:tool_call|tool_invoke)>\s*(?:(?:```|~~~)\w*\s*)?\{")
+_RAW_CALL_RE = re.compile(
+    r"(?<!`)<(?:tool_call|tool_invoke)>\s*(?:(?:```|~~~)\w*\s*)?\{"
+)
 # Модель явно сказала, что отвечает без инструментов.
 _NO_TOOLS_RE = re.compile(
     r"\bno tools?\b|\bwithout (?:any )?tools?\b|\bno need\b|\bnot (?:needed|required|necessary)\b|"
     r"\brule 0\b|правило 0|не требует инструмент|без инструмент|инструмент\w* не нужн",
-    re.IGNORECASE)
+    re.IGNORECASE,
+)
 # Намерение немедленного действия (преамбула шага без `<tool_call>`): явный глагол действия.
 _ACTION_INTENT_RE = re.compile(
     r"\b(?:забираю|читаю|собираю|правлю|проверяю|запускаю|выполняю|запрашиваю|стартую|продолжаю|начинаю|"
@@ -525,7 +834,8 @@ _ACTION_INTENT_RE = re.compile(
     r"\blet'?s (?:check|read|look|run|fetch|collect|gather|see|grab|update|fix|search)\b|"
     r"\bi(?:'ll| will) (?:check|read|look|run|fetch|collect|gather|update|fix|search)\b|"
     r"\b(?:collecting|checking|reading|running|fetching|gathering|updating|searching)\b",
-    re.IGNORECASE)
+    re.IGNORECASE,
+)
 _PROMISE_RE = _ACTION_INTENT_RE  # прежнее имя
 # Финальный вывод/ответ (а не преамбула шага): заголовок-вывод в начале текста или фраза-итог.
 _FINAL_CONCLUSION_RE = re.compile(
@@ -533,7 +843,8 @@ _FINAL_CONCLUSION_RE = re.compile(
     r"summary|conclusion|answer|result|done|готово)\b|"
     r"\b(?:ошибок нет|нет ошибок|всё в порядке|все в порядке|так задумано|тесты (?:зел[её]ные|прошли)|"
     r"no errors?|all (?:good|tests pass\w*)|everything is fine)\b",
-    re.IGNORECASE)
+    re.IGNORECASE,
+)
 # План пачки вызовов в reasoning текущего шага.
 _REASONING_TOOL_PLAN_RE = re.compile(
     r"let me batch|all in batch|\bone message\s*:|\bin one (?:message|batch|turn)\b|parallel calls|"
@@ -541,28 +852,43 @@ _REASONING_TOOL_PLAN_RE = re.compile(
     r"\btool calls? (?:now|next|in parallel)\b|"
     r"\bemit (?:the )?(?:tool[_\s]?(?:call|invoke)?\s*)?blocks?\b|\btool[_\s]?(?:call|invoke)?\s*blocks?\b|"
     r"\bcall (?:the )?tools\b|\btwo independent calls\b|\bindependent calls\b",
-    re.IGNORECASE)
+    re.IGNORECASE,
+)
 _PLAN_RE = _REASONING_TOOL_PLAN_RE  # прежнее имя
 # Мышление, где модель пишет «I need to call job_output…» без готовой фразы-плана.
 _CALL_INTENT_RE = re.compile(
-    r"\b(?:call|invoke|emit|parallel|batch|need to|let me|i'll|i will|should)\b", re.IGNORECASE)
+    r"\b(?:call|invoke|emit|parallel|batch|need to|let me|i'll|i will|should)\b",
+    re.IGNORECASE,
+)
 # Апстрим вырезал `<tool_call>…</tool_call>` из text, но токены в step_finish остались: столько
 # лишних токенов над оценкой видимого текста — признак проглоченного вызова.
 SWALLOWED_TOKENS_MIN = 35
 INCOMPLETE_STEP_MAX_TEXT = 1200  # дольше — это ответ, а не статусная преамбула
 INCOMPLETE_STEP_TAIL = 400
 TAIL_REMINDER_MIN_CHARS = 4000
-SWALLOWED_MAX_TEXT = 600   # признак 3
-PLAN_MAX_TEXT = 600        # признак 4
-PREAMBLE_MAX_CHARS = 420   # признак 5
+SWALLOWED_MAX_TEXT = 600  # признак 3
+PLAN_MAX_TEXT = 600  # признак 4
+PREAMBLE_MAX_CHARS = 420  # признак 5
 PREAMBLE_MAX_LINES = 6
 PREAMBLE_SHORT_CHARS = 220
 
 # Mid-stream `etype == "error"`: транзиентные сбои (повторяем) против детерминированных (Fail-Closed).
 _FATAL_STREAM_STATUSES = (400, 401, 403, 404, 422)
 _TRANSIENT_ERROR_MARKERS = (
-    "econnreset", "etimedout", "timeout", "timed out", "socket hang up", "interrupted", "overloaded",
-    "rate limit", "temporarily unavailable", "fetch failed", "network", "connection reset", "broken pipe", "eof",
+    "econnreset",
+    "etimedout",
+    "timeout",
+    "timed out",
+    "socket hang up",
+    "interrupted",
+    "overloaded",
+    "rate limit",
+    "temporarily unavailable",
+    "fetch failed",
+    "network",
+    "connection reset",
+    "broken pipe",
+    "eof",
 )
 
 
@@ -596,7 +922,8 @@ def _mentions_request_tool(text: str, names: Iterable[str]) -> bool:
         while start != -1:
             end = start + len(name)
             if (start == 0 or not _is_ident_char(text[start - 1])) and (
-                    end == len(text) or not _is_ident_char(text[end])):
+                end == len(text) or not _is_ident_char(text[end])
+            ):
                 return True
             start = text.find(name, start + 1)
     return False
@@ -658,7 +985,8 @@ def _is_transient_stream_error(ev: dict[str, Any]) -> bool:
 def _step_recovery_disabled() -> bool:
     """Kill-switch OPENCODE_ZEN_BRIDGE_STEP_RECOVERY (константа модуля и живое значение env)."""
     return not STEP_RECOVERY_ENABLED or os.environ.get(
-        "OPENCODE_ZEN_BRIDGE_STEP_RECOVERY", "1").strip().lower() in ("0", "false", "no", "off")
+        "OPENCODE_ZEN_BRIDGE_STEP_RECOVERY", "1"
+    ).strip().lower() in ("0", "false", "no", "off")
 
 
 def _visible_token_estimate(stripped: str) -> int:
@@ -666,7 +994,9 @@ def _visible_token_estimate(stripped: str) -> int:
     return max(len(stripped) // 2, _estimate_tokens(stripped)) if stripped else 0
 
 
-def _swallowed_tokens(stripped: str, output_tokens: int, reasoning_tokens: int = 0) -> int:
+def _swallowed_tokens(
+    stripped: str, output_tokens: int, reasoning_tokens: int = 0
+) -> int:
     """Токены вывода, не объяснённые видимым текстом: output включает reasoning — вычитаем его."""
     if reasoning_tokens > 0 and output_tokens >= reasoning_tokens:
         non_reasoning_output = max(0, output_tokens - reasoning_tokens)
@@ -687,7 +1017,9 @@ def _is_status_preamble(stripped: str, names: list[str]) -> bool:
         return False
     if stripped.endswith((":", "...", "…")):
         return True
-    return len(stripped) <= PREAMBLE_SHORT_CHARS and _mentions_request_tool(stripped, names)
+    return len(stripped) <= PREAMBLE_SHORT_CHARS and _mentions_request_tool(
+        stripped, names
+    )
 
 
 def _no_tools_overridden(body: str, thought: str, names: Iterable[str]) -> bool:
@@ -702,7 +1034,8 @@ def _no_tools_overridden(body: str, thought: str, names: Iterable[str]) -> bool:
         return False
     tail = thought[-400:]
     return bool(_REASONING_TOOL_PLAN_RE.search(thought[-600:])) or (
-        _mentions_request_tool(tail, names) and bool(_CALL_INTENT_RE.search(tail)))
+        _mentions_request_tool(tail, names) and bool(_CALL_INTENT_RE.search(tail))
+    )
 
 
 def _detect_incomplete_tool_step_signal(text: str, reasoning: str, tools: Any,
@@ -833,28 +1166,48 @@ def _call_key(name: str, arguments: Any) -> str:
     return name + "\x00" + json.dumps(arguments, ensure_ascii=False, sort_keys=True)
 
 
-def _drain_stderr(proc: subprocess.Popen[str], sink: list[str]) -> None:
-    """Вычитать stderr дочернего процесса построчно в `sink` (до EOF)."""
+def _drain_stderr(
+    proc: subprocess.Popen[str], sink: collections.deque[str] | list[str]
+) -> None:
+    """Вычитать stderr в ограниченный буфер (кольцо на 64 строки, без секретов в лог)."""
+    # Дренаж stderr помощника/CLI в ограниченный буфер; содержимое не логируется.
     try:
         assert proc.stderr is not None
         for line in proc.stderr:
-            line = line.strip()
+            line_text: str = cast(str, line).strip()
+            line = line_text
             if line:
-                sink.append(line)
+                if isinstance(sink, list):
+                    sink_list: list[str] = sink
+                    _ = sink_list.append(line)
+                    while len(sink_list) > 64:
+                        _ = sink_list.pop(0)
+                else:
+                    sink_deque: collections.deque[str] = sink
+                    _ = sink_deque.append(line)
     except (OSError, ValueError):
         pass
 
 
 def _stop_proc(proc: subprocess.Popen[str]) -> None:
     """Остановить группу `opencode run` (SIGTERM -> SIGKILL); процесс запущен со start_new_session."""
-    if proc.poll() is not None:
+    pgid = proc.pid  # start_new_session=True => pgid == pid лидера
+    if proc.poll() is not None and not _pid_alive(-pgid):
         return
     try:
-        os.killpg(proc.pid, signal.SIGTERM)
-        proc.wait(timeout=5)
+        os.killpg(pgid, signal.SIGTERM)
+        if proc.poll() is None:
+            _ = proc.wait(timeout=5)
+        else:
+            # Лидер вышел, но группа ещё жива: ждём SIGTERM до 0.5 с.
+            _dl = time.monotonic() + 0.5
+            while time.monotonic() < _dl and _pid_alive(-pgid):
+                time.sleep(0.05)
     except (OSError, subprocess.TimeoutExpired):
+        pass
+    if _pid_alive(-pgid):
         try:
-            os.killpg(proc.pid, signal.SIGKILL)
+            os.killpg(pgid, signal.SIGKILL)
         except OSError:
             pass
 
@@ -874,7 +1227,9 @@ class _StdoutFeed:
 
     def __init__(self, proc: subprocess.Popen[str], maxsize: int | None = None) -> None:
         self._proc = proc
-        self._queue: queue.Queue[str] = queue.Queue(maxsize=STDOUT_QUEUE_MAX if maxsize is None else maxsize)
+        self._queue: queue.Queue[str] = queue.Queue(
+            maxsize=STDOUT_QUEUE_MAX if maxsize is None else maxsize
+        )
         self.timed_out = False
         self.overflowed = False
         self.dropped_total = 0
@@ -892,8 +1247,10 @@ class _StdoutFeed:
                 except queue.Full:
                     self.dropped_total += 1
                     self.overflowed = True
-                    _log(f"stdout_overflow queue_max={self._queue.maxsize} dropped_total={self.dropped_total}, "
-                         "stopping opencode run")
+                    _log(
+                        f"stdout_overflow queue_max={self._queue.maxsize} dropped_total={self.dropped_total}, "
+                        "stopping opencode run"
+                    )
                     _stop_proc(self._proc)
                     break
         except (OSError, ValueError) as exc:
@@ -901,8 +1258,12 @@ class _StdoutFeed:
         finally:
             self._done.set()  # после всех put: потребитель, увидев флаг, дочитывает остаток очереди
 
-    def lines(self, deadline: float, idle_s: float = 0.0,
-              on_idle: Callable[[], None] | None = None) -> Iterator[str]:
+    def lines(
+        self,
+        deadline: float,
+        idle_s: float = 0.0,
+        on_idle: Callable[[], None] | None = None,
+    ) -> Iterator[str]:
         """Строки до EOF, переполнения или дедлайна; `on_idle` вызывается, если строк нет дольше `idle_s` (0 — выкл.)."""
         last_activity = time.monotonic()
         while True:
@@ -927,7 +1288,11 @@ class _StdoutFeed:
                         return
                 else:
                     now = time.monotonic()
-                    if idle_s > 0 and on_idle is not None and now - last_activity >= idle_s:
+                    if (
+                        idle_s > 0
+                        and on_idle is not None
+                        and now - last_activity >= idle_s
+                    ):
                         on_idle()
                         last_activity = now
                     continue
@@ -935,6 +1300,10 @@ class _StdoutFeed:
             if last_activity > deadline:
                 self.timed_out = True
                 return
+            if idle_s > 0 and on_idle is not None:
+                # Watchdog проверяется и при поступлении строк, а не только на Empty:
+                # служебный поток без токенов должен прерываться по тем же часам.
+                on_idle()
             yield item
 
     def close(self) -> None:
@@ -968,12 +1337,23 @@ def _uses_standalone(model_id: str) -> bool:
     return CATALOG_MODE == "dynamic" and _is_zen_route(model_id)
 
 
-_PROXY_VARS = ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy")
+_PROXY_VARS = (
+    "HTTP_PROXY",
+    "HTTPS_PROXY",
+    "http_proxy",
+    "https_proxy",
+    "ALL_PROXY",
+    "all_proxy",
+)
 _LOOPBACK_NO_PROXY = ("127.0.0.1", "localhost", "::1")
 # THREAT-003 + принятое отклонение DEV-02: к ключам пакета добавлены переменные прокси.
 _STANDALONE_ENV_ALLOWLIST = (
-    "PATH", "HOME", "TMPDIR", "LANG",
-    "NO_PROXY", "no_proxy",
+    "PATH",
+    "HOME",
+    "TMPDIR",
+    "LANG",
+    "NO_PROXY",
+    "no_proxy",
     *_PROXY_VARS,
 )
 
@@ -988,11 +1368,16 @@ def _merged_no_proxy(current: str) -> str:
 # Пул выделенных US-портов ProxyRack: каждый порт 10000..10999 даёт отдельный чистый IP, а анонимный
 # лимит opencode.ai (36 запросов в сутки на исходящий IP) считается по IP. Режим `pool` берёт
 # порты по кругу — по одному на каждый запуск дочернего процесса (включая ретраи).
-_DEFAULT_PROXYRACK_FILE = Path.home() / ".local/share/gigaexplorator-proxies/2026-08-31-volkov-proxy-manager/06-proxyrack-global-dc-1000.txt"
+_DEFAULT_PROXYRACK_FILE = (
+    Path.home()
+    / ".local/share/gigaexplorator-proxies/2026-08-31-volkov-proxy-manager/06-proxyrack-global-dc-1000.txt"
+)
 _PROXYRACK_FORWARD_LOG = Path.home() / "Library/Logs/Factory/proxyrack-forward.log"
 _DEFAULT_PROXYRACK_GATEWAY = "121.91.235.6"
 _PROXYRACK_LOG_TAIL_BYTES = 16 * 1024
-_IPV4_RE = re.compile(r"^(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(?:\.(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}$")
+_IPV4_RE = re.compile(
+    r"^(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(?:\.(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}$"
+)
 
 _proxy_pool_lock = threading.Lock()
 _proxy_pool_key: tuple[Any, ...] | None = None
@@ -1052,7 +1437,11 @@ def _next_standalone_proxy() -> str | None:
         return None
     if raw_proxy != "pool":
         return raw_proxy
-    pool_path = Path(os.environ.get("OPENCODE_ZEN_BRIDGE_PROXYRACK_FILE", str(_DEFAULT_PROXYRACK_FILE)))
+    pool_path = Path(
+        os.environ.get(
+            "OPENCODE_ZEN_BRIDGE_PROXYRACK_FILE", str(_DEFAULT_PROXYRACK_FILE)
+        )
+    )
     gateway = _resolve_proxyrack_gateway()
     offset = os.environ.get("OPENCODE_ZEN_BRIDGE_PROXYRACK_OFFSET", "")
     try:
@@ -1066,7 +1455,13 @@ def _next_standalone_proxy() -> str | None:
                 lines = pool_path.read_text("utf-8", errors="replace").splitlines()
             except OSError:
                 return None
-            entries = [e for e in (_parse_proxy_pool_line(ln, gateway) for ln in lines if ln.strip()) if e]
+            entries = [
+                e
+                for e in (
+                    _parse_proxy_pool_line(ln, gateway) for ln in lines if ln.strip()
+                )
+                if e
+            ]
             if not entries:
                 return None
             _proxy_pool_key = key
@@ -1131,6 +1526,471 @@ def _run_env(model_id: str = "") -> dict[str, str]:
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
+_LSOF_CALLS: collections.deque[int] = collections.deque(maxlen=64)
+_PORT_ALLOC_LOCK = threading.Lock()
+_ACTIVE_SERVE_PORTS: set[int] = set()
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
+        "event": "HTTP429/provider5xx prompt response headers_at received",
+        "DELIVERED": "any",
+        "action": "serve_retry_via_allow_retry_after_headers_at",
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
+    prompt_status: int | None
+    transient_error: bool
+
+
+def _as_dict(value: object) -> dict[str, object]:
+    """Объект как словарь с строковыми ключами, иначе пустой."""
+    if isinstance(value, dict):
+        return {str(k): v for k, v in value.items()}
+    return {}
+
+
+def _combine_surrogates(value: object) -> object:
+    """Склеить суррогатные пары UTF-16 в строках после json.loads."""
+    if isinstance(value, str):
+        try:
+            return value.encode("utf-16", "surrogatepass").decode("utf-16")
+        except (UnicodeError, ValueError):
+            return value
+    if isinstance(value, dict):
+        return {str(k): _combine_surrogates(v) for k, v in value.items()}
+    if isinstance(value, list):
+        return [_combine_surrogates(v) for v in value]
+    return value
+
+
+def _loads_object(raw: str) -> dict[str, object] | None:
+    """JSON-объект стандартным json.loads; не-объект или битый JSON — None."""
+    try:
+        parsed: object = cast(object, json.loads(raw))
+    except (ValueError, TypeError):
+        return None
+    if isinstance(parsed, dict):
+        combined = _combine_surrogates({str(k): v for k, v in parsed.items()})
+        return combined if isinstance(combined, dict) else None
+    return None
+
+
+def _loads_serve_object(raw: str) -> dict[str, object]:
+    """JSON-объект события serve; битый JSON — ServeProtocolError."""
+    parsed = _loads_object(raw)
+    if parsed is None:
+        raise ServeProtocolError("invalid_serve_event: json")
+    return parsed
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
+    except (OSError, ValueError) as exc:
+        _log(f"dynamic config unreadable: {_clean_err(str(exc))}")
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
+    return head[:2] in (b"\xcf\xfa", b"\xfa\xed") or head.startswith(b"\x7fELF")
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
+def _map_serve_event(
+    event: dict[str, object],
+) -> tuple[str, dict[str, object]] | None:
+    """Wire-событие serve v2.1.2 -> канонический кортеж legacy-пути или None для служебных."""
+    etype_obj = event.get("type")
+    etype = etype_obj if isinstance(etype_obj, str) else ""
+    data = _as_dict(event.get("data"))
+    if etype == "server.connected":
+        return etype, data
+    if not data:
+        # Служебные/неизвестные события serve без данных игнорируются, а не рвут попытку.
+        if etype in (
+            "server.heartbeat",
+            "integration.updated",
+            "session.idle",
+            "server.connected",
+        ) or not etype.startswith("session."):
+            return None
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
+            return "reasoning", {"reasoning_content": delta, "sessionID": session_id}
+        return "text", {"content": delta, "sessionID": session_id}
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
+        sid_obj = data.get("sessionID")
+        if isinstance(sid_obj, str):
+            out["sessionID"] = sid_obj
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
+        err_out: dict[str, object] = {"statusCode": status, "message": message}
+        sid_err = data.get("sessionID")
+        if isinstance(sid_err, str):
+            err_out["sessionID"] = sid_err
+        return "error", err_out
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
@@ -1138,7 +1998,9 @@ def _variant_for(model_id: str, effort: str) -> str:
         return ""
     values = meta.get("effort_values")
     if values and effort not in values:
-        _log(f"WARN variant {effort!r} is not in effort_values of {model_id}; suffix dropped")
+        _log(
+            f"WARN variant {effort!r} is not in effort_values of {model_id}; suffix dropped"
+        )
         return ""
     return effort
 
@@ -1174,8 +2036,9 @@ def _clean_err(lines: list[str] | str, limit: int = 600) -> str:
     return _mask_secrets(text)[-limit:]
 
 
-def _is_retryable_failure(rc: int | None, err_text: str, provider_status: int | None,
-                          had_output: bool) -> bool:
+def _is_retryable_failure(
+    rc: int | None, err_text: str, provider_status: int | None, had_output: bool
+) -> bool:
     """Прогон без какого-либо вывода и с rc != 0 — транзиторный отказ CLI (повторяем).
 
     Не повторяем: был вывод; процесс убит нами/таймаутом (rc < 0 или None);
@@ -1186,11 +2049,15 @@ def _is_retryable_failure(rc: int | None, err_text: str, provider_status: int |
     return provider_status not in _FATAL_HTTP
 
 
-def _error_payload(message: str, detail: str = "") -> dict[str, Any]:
+def _error_payload(message: str, detail: str = "") -> dict[str, object]:
     """Тело OpenAI-style ошибки (SSE-чанк `{"error":…}` и non-stream 502)."""
-    err: dict[str, Any] = {"message": message, "type": "proxy_error", "code": 502}
+    err: dict[str, object] = {
+        "message": _clean_err(message),
+        "type": "proxy_error",
+        "code": 502,
+    }
     if detail:
-        err["detail"] = detail
+        err["detail"] = _clean_err(detail)
     return {"error": err}
 
 
@@ -1211,7 +2078,9 @@ class _StartupGate:
 
     def acquire(self) -> None:
         if not _STARTUP_LOCK.acquire(timeout=max(0.0, self._wait_s)):
-            _log(f"startup_gate_timeout wait_s={self._wait_s:.1f}, starting without the gate")
+            _log(
+                f"startup_gate_timeout wait_s={self._wait_s:.1f}, starting without the gate"
+            )
             return
         with self._guard:
             self._held = True
@@ -1262,20 +2131,30 @@ class _SlotBulkhead:
     в `finally`/`release` на любом выходе (таймаут, исключение, отмена).
     """
 
-    def __init__(self, max_concurrent: int | None = None, max_waiters: int | None = None,
-                 wait_timeout_s: float | None = None,
-                 clock_fn: Callable[[], float] = time.monotonic) -> None:
+    def __init__(
+        self,
+        max_concurrent: int | None = None,
+        max_waiters: int | None = None,
+        wait_timeout_s: float | None = None,
+        clock_fn: Callable[[], float] = time.monotonic,
+    ) -> None:
         self._max = MAX_CONCURRENT if max_concurrent is None else max_concurrent
         self._max_waiters = MAX_SLOT_WAITERS if max_waiters is None else max_waiters
-        self._wait_timeout_s = SLOT_WAIT_TIMEOUT_S if wait_timeout_s is None else wait_timeout_s
+        self._wait_timeout_s = (
+            SLOT_WAIT_TIMEOUT_S if wait_timeout_s is None else wait_timeout_s
+        )
         self._clock = clock_fn
         self._cond = threading.Condition(threading.Lock())
         self.in_use = 0
         self.waiters = 0
 
     def acquire_ex(self, timeout: float | None = None) -> str:
-        """"ok" | "timeout" | "overflow" (все слоты заняты и очередь ждущих полна)."""
-        wait = self._wait_timeout_s if timeout is None else min(timeout, self._wait_timeout_s)
+        """ "ok" | "timeout" | "overflow" (все слоты заняты и очередь ждущих полна)."""
+        wait = (
+            self._wait_timeout_s
+            if timeout is None
+            else min(timeout, self._wait_timeout_s)
+        )
         with self._cond:
             if self.in_use < self._max:
                 self.in_use += 1
@@ -1312,9 +2191,13 @@ class _SpawnRateLimiter:
     по моменту резерва; `acquire` возвращает False без резерва, если ожидание превысит `max_wait_s`.
     """
 
-    def __init__(self, rate_rps: float = 1.0, burst: float = 1.0,
-                 clock_fn: Callable[[], float] = time.monotonic,
-                 sleep_fn: Callable[[float], None] = time.sleep) -> None:
+    def __init__(
+        self,
+        rate_rps: float = 1.0,
+        burst: float = 1.0,
+        clock_fn: Callable[[], float] = time.monotonic,
+        sleep_fn: Callable[[float], None] = time.sleep,
+    ) -> None:
         self._rate = max(rate_rps, 1e-9)
         self._burst = max(burst, 1.0)
         self._clock = clock_fn
@@ -1326,7 +2209,9 @@ class _SpawnRateLimiter:
     def acquire(self, max_wait_s: float | None = None) -> bool:
         with self._lock:
             now = self._clock()
-            self._tokens = min(self._burst, self._tokens + max(0.0, now - self._last) * self._rate)
+            self._tokens = min(
+                self._burst, self._tokens + max(0.0, now - self._last) * self._rate
+            )
             self._last = now
             wait = max(0.0, (1.0 - self._tokens) / self._rate)
             if max_wait_s is not None and wait > max_wait_s:
@@ -1336,16 +2221,31 @@ class _SpawnRateLimiter:
             self._sleep(wait)
         return True
 
+    def refund(self, amount: float = 1.0) -> None:
+        """Вернуть резерв, если дочерний процесс не был запущен."""
+        with self._lock:
+            self._tokens = min(self._burst, self._tokens + amount)
+
 
 class _RetryBudget:
     """Process-level бюджет повторных запусков: ёмкость `capacity`, +`per_request_refill` за запрос, +`reserve_rps` в секунду."""
 
-    def __init__(self, capacity: float | None = None, per_request_refill: float | None = None,
-                 reserve_rps: float | None = None,
-                 clock_fn: Callable[[], float] = time.monotonic) -> None:
+    def __init__(
+        self,
+        capacity: float | None = None,
+        per_request_refill: float | None = None,
+        reserve_rps: float | None = None,
+        clock_fn: Callable[[], float] = time.monotonic,
+    ) -> None:
         self._capacity = RETRY_BUDGET_MAX if capacity is None else capacity
-        self._per_request = RETRY_BUDGET_PER_REQUEST if per_request_refill is None else per_request_refill
-        self._reserve_rps = RETRY_BUDGET_RESERVE_RPS if reserve_rps is None else reserve_rps
+        self._per_request = (
+            RETRY_BUDGET_PER_REQUEST
+            if per_request_refill is None
+            else per_request_refill
+        )
+        self._reserve_rps = (
+            RETRY_BUDGET_RESERVE_RPS if reserve_rps is None else reserve_rps
+        )
         self._clock = clock_fn
         self._lock = threading.Lock()
         self.tokens = float(self._capacity)
@@ -1353,7 +2253,9 @@ class _RetryBudget:
 
     def _refill_time(self) -> None:
         now = self._clock()
-        self.tokens = min(self._capacity, self.tokens + max(0.0, now - self._last) * self._reserve_rps)
+        self.tokens = min(
+            self._capacity, self.tokens + max(0.0, now - self._last) * self._reserve_rps
+        )
         self._last = now
 
     def on_request(self) -> None:
@@ -1374,12 +2276,18 @@ class _RetryBudget:
 class _UpstreamBreaker:
     """Circuit Breaker зависимости `opencode run`: CLOSED -> OPEN (N подряд транзиентных отказов) -> HALF_OPEN (1 проба)."""
 
-    def __init__(self, fail_threshold: int | None = None, reset_timeout_s: float | None = None,
-                 clock_fn: Callable[[], float] = time.monotonic,
-                 rng_fn: Callable[[float, float], float] = random.uniform,
-                 max_half_open_probes: int = 1,
-                 log_fn: Callable[[str], None] | None = None) -> None:
-        self._threshold = CB_FAIL_THRESHOLD if fail_threshold is None else fail_threshold
+    def __init__(
+        self,
+        fail_threshold: int | None = None,
+        reset_timeout_s: float | None = None,
+        clock_fn: Callable[[], float] = time.monotonic,
+        rng_fn: Callable[[float, float], float] = random.uniform,
+        max_half_open_probes: int = 1,
+        log_fn: Callable[[str], None] | None = None,
+    ) -> None:
+        self._threshold = (
+            CB_FAIL_THRESHOLD if fail_threshold is None else fail_threshold
+        )
         self._reset_s = CB_RESET_S if reset_timeout_s is None else reset_timeout_s
         self._clock = clock_fn
         self._rng = rng_fn
@@ -1421,7 +2329,10 @@ class _UpstreamBreaker:
                 return True
             if self._state == "OPEN":
                 return False
-            if self._probes >= self._max_probes and now - self._probe_started < self._reset_s:
+            if (
+                self._probes >= self._max_probes
+                and now - self._probe_started < self._reset_s
+            ):
                 return False
             self._probes = 1 if self._probes >= self._max_probes else self._probes + 1
             self._probe_started = now
@@ -1447,7 +2358,9 @@ class _UpstreamBreaker:
                 self._state = "OPEN"
                 self._open_until = now + cooldown
                 self._probes = 0
-                self._say(f"circuit_breaker state=OPEN failures={self._failures} cooldown_s={cooldown:.1f}")
+                self._say(
+                    f"circuit_breaker state=OPEN failures={self._failures} cooldown_s={cooldown:.1f}"
+                )
 
 
 class _Resilience:
@@ -1462,6 +2375,7 @@ class _Resilience:
         self.spawn_limiter = _SpawnRateLimiter(SPAWN_RATE_PER_S, SPAWN_BURST)
         self.retry_budget = _RetryBudget()
         self.breaker = _UpstreamBreaker()
+        self.serve_health = _ServeHealth()
 
 
 _DEFAULT_RESILIENCE = _Resilience()
@@ -1471,13 +2385,20 @@ _slots = _DEFAULT_RESILIENCE.slots  # прежнее имя семафора с
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
@@ -1491,13 +2412,22 @@ class _RequestAttempts:
     def note_spawn(self) -> None:
         self.total_spawns += 1
 
+    def can_spawn(self) -> bool:
+        """Можно ли ещё запускать: суммарный потолок спавнов на запрос."""
+        return (
+            self.total_spawns < MAX_TOTAL_SPAWNS and self.total_spawns < self.max_total
+        )
+
     def remaining_s(self) -> float:
         return max(0.0, self.deadline - time.monotonic())
 
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
@@ -1517,7 +2447,11 @@ class _RequestAttempts:
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
@@ -1564,43 +2498,1169 @@ class _PrefixDedup:
         current, prefix = self.current, self.prefix
         if current.startswith(prefix):
             self.prefix = ""
-            return current[len(prefix):]
+            return current[len(prefix) :]
         if len(current) >= len(prefix) or not prefix.startswith(current):
             self.prefix = ""
             return "\n\n" + current
         return ""
 
-    def finish(self) -> str:
-        """Конец попытки: накопленный, но неотданный текст (кроме чистого повтора части префикса)."""
-        leftover = ""
-        if self.prefix and self.current and not self.prefix.startswith(self.current):
-            leftover = "\n\n" + self.current
-        self.prefix = ""
-        return leftover
+    def finish(self) -> str:
+        """Конец попытки: накопленный, но неотданный текст (кроме чистого повтора части префикса)."""
+        leftover = ""
+        if self.prefix and self.current and not self.prefix.startswith(self.current):
+            leftover = "\n\n" + self.current
+        self.prefix = ""
+        return leftover
+
+
+def _dedup_retry_text(prefix: str, current: str) -> str:
+    """JSON-вариант dedup_prefix: подавить уже отданный префикс, переформулированный текст сохранить целиком."""
+    if prefix and current.startswith(prefix):
+        return current[len(prefix) :]
+    return current
+
+
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
+    on_headers: Callable[[int], None] | None = None,
+    deadline: float | None = None,
+    is_client_gone: Callable[[], bool] | None = None,
+) -> tuple[int, dict[str, object]]:
+    """Один HTTP-вызов serve с Basic-авторизацией без прокси."""
+    own_conn = conn is None
+    active_conn = (
+        conn
+        if conn is not None
+        else http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
+    )
+    if conn is not None:
+        conn.timeout = timeout
+        if conn.sock is not None:
+            _ = conn.sock.settimeout(timeout)
+
+    phase_socket: socket.socket | None = None
+
+    def check_phase() -> None:
+        """Ограничить следующую фазу оставшимся бюджетом и проверить отмену."""
+        if is_client_gone is not None and is_client_gone():
+            raise BrokenPipeError(errno.EPIPE, "client gone")
+        remaining = (
+            timeout if deadline is None else min(timeout, deadline - time.monotonic())
+        )
+        if remaining <= 0:
+            raise TimeoutError("serve deadline exceeded")
+        active_conn.timeout = remaining
+        connected_socket = active_conn.sock or phase_socket
+        if connected_socket is not None:
+            _ = connected_socket.settimeout(remaining)
+
+    try:
+        check_phase()
+        payload = json.dumps(body).encode("utf-8") if body is not None else None
+        auth = base64.b64encode(f"opencode:{password}".encode("utf-8")).decode("ascii")
+        headers = {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}
+        active_conn.request(method, path, payload, headers)
+        # HTTP/1.0 отделяет сокет от conn после заголовков; бюджет тела остаётся обязательным.
+        phase_socket = active_conn.sock
+        check_phase()
+        resp = active_conn.getresponse()
+        if on_headers is not None:
+            on_headers(int(resp.status))
+        raw = bytearray()
+        while not resp.isclosed():
+            check_phase()
+            chunk = resp.read1(65536)
+            if not chunk:
+                break
+            raw.extend(chunk)
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
+        port: int = 0,
+    ) -> None:
+        self.helper = helper
+        self.serve_pid = serve_pid
+        self.pgid = pgid
+        self.lifeline_w = lifeline_w
+        self.lease_dir = lease_dir
+        self.attempt_id = attempt_id
+        self.state_dir = state_dir
+        self.port = port
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
+        _deadline = time.monotonic() + 4.0
+        if self.helper.poll() is None or _pid_alive(-self.pgid):
+            try:
+                if os.getpgid(self.pgid) == self.pgid:
+                    os.killpg(self.pgid, signal.SIGTERM)
+            except OSError:
+                pass
+            while time.monotonic() < _deadline:
+                if not _pid_alive(-self.pgid) and self.helper.poll() is not None:
+                    break
+                time.sleep(0.05)
+            if _pid_alive(-self.pgid) or self.helper.poll() is None:
+                try:
+                    os.killpg(self.pgid, signal.SIGKILL)
+                except OSError:
+                    pass
+                # Отдельное окно подтверждения смерти группы после SIGKILL (бюджет AC-011 <= 7 с).
+                _deadline = time.monotonic() + 2.0
+                while time.monotonic() < _deadline:
+                    if not _pid_alive(-self.pgid) and self.helper.poll() is not None:
+                        break
+                    time.sleep(0.05)
+            try:
+                _ = self.helper.wait(timeout=max(0.1, _deadline - time.monotonic()))
+            except (OSError, subprocess.SubprocessError):
+                pass
+        for stream in (self.helper.stdout, self.helper.stderr):
+            try:
+                if stream is not None:
+                    stream.close()
+            except OSError:
+                pass
+        if not _pid_alive(-self.pgid):
+            try:
+                (self.lease_dir / f"lease-{self.attempt_id}.json").unlink()
+            except OSError:
+                pass
+            if self.port:
+                with _PORT_ALLOC_LOCK:
+                    _ACTIVE_SERVE_PORTS.discard(self.port)
+        if self.state_dir and Path(self.state_dir).name.startswith("zen-serve-state-"):
+            shutil.rmtree(self.state_dir, ignore_errors=True)
+
+
+def _ensure_lease_dir(lease_dir: Path) -> None:
+    """Каталог lease: свой uid, не симлинк, права 0700."""
+    lease_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
+    try:
+        info = os.lstat(lease_dir)
+    except OSError as exc:
+        raise ServeUnavailable(f"lease dir unavailable: {exc}") from exc
+    if stat.S_ISLNK(info.st_mode) or info.st_uid != os.getuid():
+        raise ServeUnavailable("lease dir ownership check failed")
+    try:
+        os.chmod(lease_dir, 0o700)
+    except OSError:
+        pass
+
+
+def _discard_spawn_leftovers(port: int, lifeline_w: int, state_dir: str) -> None:
+    """Освободить ресурсы неудачного старта serve до создания _ServeLease."""
+    if lifeline_w >= 0:
+        try:
+            os.close(lifeline_w)
+        except OSError:
+            pass
+    if port:
+        with _PORT_ALLOC_LOCK:
+            _ACTIVE_SERVE_PORTS.discard(port)
+    if state_dir and Path(state_dir).name.startswith("zen-serve-state-"):
+        shutil.rmtree(state_dir, ignore_errors=True)
+
+
+def _spawn_serve(
+    attempt_id: str, serve_env: dict[str, str]
+) -> tuple[_ServeLease, int, str]:
+    """Запуск helper->serve, проверка слушателя и рукопожатия."""
+    port = 0
+    lifeline_w = -1
+    lease: _ServeLease | None = None
+    state_dir = serve_env.get("XDG_STATE_HOME", "")
+    try:
+        lease_dir = Path(LEASE_DIR)
+        _ensure_lease_dir(lease_dir)
+        with _PORT_ALLOC_LOCK:
+            for candidate in range(20000 + (os.getpid() % 20000), 60000):
+                if candidate in _ACTIVE_SERVE_PORTS:
+                    continue
+                probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
+                try:
+                    probe.bind(("127.0.0.1", candidate))
+                    port = candidate
+                    _ACTIVE_SERVE_PORTS.add(candidate)
+                    break
+                except OSError:
+                    continue
+                finally:
+                    probe.close()
+        if not port:
+            raise ServeUnavailable("no free serve port")
+        password = serve_env.get("OPENCODE_SERVER_PASSWORD", "")
+        lifeline_r, lifeline_w = os.pipe()
+        try:
+            helper: subprocess.Popen[str] = subprocess.Popen(
+                [
+                    sys.executable,
+                    "-I",
+                    str(Path(__file__).resolve()),
+                    "--serve-helper",
+                    attempt_id,
+                    str(port),
+                    str(OPENCODE_BIN),
+                    str(lease_dir),
+                    str(os.getpid()),
+                    _parent_lstart(),
+                ],
+                stdin=lifeline_r,
+                stdout=subprocess.PIPE,
+                stderr=subprocess.PIPE,
+                start_new_session=True,
+                close_fds=True,
+                env=serve_env,
+                text=True,
+            )
+        finally:
+            try:
+                os.close(lifeline_r)
+            except OSError:
+                pass
+        lease = _ServeLease(
+            helper,
+            0,
+            helper.pid,
+            lifeline_w,
+            lease_dir,
+            attempt_id,
+            state_dir,
+            port,
+        )
+        assert helper.stdout is not None
+        out_fd = helper.stdout.fileno()
+        _hs_deadline = time.monotonic() + 3.0
+        ready, _w, _x = select.select(
+            [out_fd], [], [], max(0.0, _hs_deadline - time.monotonic())
+        )
+        if not ready:
+            raise ServeUnavailable("serve helper handshake timeout")
+        line_bytes = b""
+        while not line_bytes.endswith(b"\n"):
+            if time.monotonic() >= _hs_deadline:
+                raise ServeUnavailable("serve helper handshake timeout")
+            _ready, _w2, _x2 = select.select(
+                [out_fd], [], [], max(0.0, _hs_deadline - time.monotonic())
+            )
+            if not _ready:
+                raise ServeUnavailable("serve helper handshake timeout")
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
+        _listener_deadline = time.monotonic() + 3.0
+        listener_pid = _lsof_listener_pid(port)
+        while (
+            listener_pid is None
+            and time.monotonic() < _listener_deadline
+            and helper.poll() is None
+        ):
+            time.sleep(0.2)
+            listener_pid = _lsof_listener_pid(port)
+        if not (
+            listener_pid is not None
+            and listener_pid == serve_pid
+            and _pid_pgid(listener_pid) == pgid
+            and helper.poll() is None
+        ):
+            raise ServeUnavailable(
+                "listener ownership verification failed: foreign listener on serve port"
+            )
+        # stderr помощника дренируется в ограниченный буфер без логирования секретов.
+        threading.Thread(
+            target=_drain_stderr,
+            args=(helper, collections.deque(maxlen=64)),
+            daemon=True,
+        ).start()
+        return lease, port, password
+    except BaseException as exc:
+        if lease is not None:
+            lease.cleanup()
+        else:
+            _discard_spawn_leftovers(port, lifeline_w, state_dir)
+        if isinstance(exc, ServeUnavailable):
+            raise
+        if isinstance(exc, (OSError, ValueError, subprocess.SubprocessError)):
+            raise ServeUnavailable(f"serve spawn os error: {exc}") from exc
+        raise
+
+
+def _startup_reaper(lease_dir: Path | None = None) -> int:
+    """Убрать осиротевшие lease мёртвого родителя при старте моста."""
+    target = Path(LEASE_DIR) if lease_dir is None else lease_dir
+    removed = 0
+    try:
+        _dir_info = os.lstat(target)
+        if stat.S_ISLNK(_dir_info.st_mode) or _dir_info.st_uid != os.getuid():
+            return 0
+        files = list(target.glob("lease-*.json"))
+    except OSError:
+        return 0
+    for path in files:
+        try:
+            _file_info = os.lstat(path)
+            if stat.S_ISLNK(_file_info.st_mode) or _file_info.st_uid != os.getuid():
+                continue
+            data = _as_dict(_loads_object(path.read_text("utf-8")))
+            parent_pid = _as_int(data.get("parent_pid"))
+            helper_pid = _as_int(data.get("helper_pid"))
+            pgid = _as_int(data.get("pgid"))
+        except (OSError, ValueError, TypeError):
+            continue
+        if _as_int(data.get("owner_uid")) != os.getuid():
+            continue
+        # Сверка lstart живого родителя/помощника с lease: переиспользованный PID не трогаем.
+        _lstart_ok = True
+        for _pid_key, _ts_key in (
+            ("parent_pid", "parent_start_ts"),
+            ("helper_pid", "helper_lstart"),
+        ):
+            _pid_v = _as_int(data.get(_pid_key))
+            _ts_v = str(data.get(_ts_key) or "")
+            if _pid_v > 0 and _ts_v and _pid_alive(_pid_v):
+                try:
+                    _live = subprocess.run(
+                        ["ps", "-o", "lstart=", "-p", str(_pid_v)],
+                        capture_output=True,
+                        text=True,
+                        timeout=2,
+                    ).stdout.strip()
+                except (OSError, subprocess.SubprocessError):
+                    _live = ""
+                # helper_lstart записан epoch-секундами, parent_start_ts — lstart: сверяем только lstart-формат.
+                if _live and not _ts_v.isdecimal() and _live != _ts_v:
+                    if _pid_key == "helper_pid":
+                        # PID помощника переиспользован: убивать группу нельзя.
+                        helper_pid = 0
+                    else:
+                        _lstart_ok = False
+        if not _lstart_ok:
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
+            _reap_deadline = time.monotonic() + 2.0
+            while _pid_alive(-pgid) and time.monotonic() < _reap_deadline:
+                time.sleep(0.05)
+            if _pid_alive(-pgid):
+                try:
+                    os.killpg(pgid, signal.SIGKILL)
+                except OSError:
+                    pass
+                while _pid_alive(-pgid) and time.monotonic() < _reap_deadline + 2.0:
+                    time.sleep(0.05)
+        if pgid <= 0 or not _pid_alive(-pgid):
+            try:
+                path.unlink()
+                removed += 1
+            except OSError:
+                pass
+    return removed
+
+
+def _pid_alive(pid: int) -> bool:
+    """Жив ли процесс; отрицательный pid — проверка группы через kill(-pgid, 0)."""
+    try:
+        os.kill(pid, 0)
+        return True
+    except OSError:
+        return False
+
+
+def _pid_pgid(pid: int) -> int:
+    """PGID процесса или -1 при ошибке."""
+    try:
+        return os.getpgid(pid)
+    except OSError:
+        return -1
+
+
+_find_listener_pid = _lsof_listener_pid
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
+    def complete(
+        self, call_id: str, event_type: str = ""
+    ) -> tuple[str, dict[str, object]] | None:
+        """Готовый вызов из called.input или input.ended.text; статус — из типа события."""
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
+        _status = (
+            "completed"
+            if any(
+                k in event_type for k in ("completed", "succeeded", "success", "called")
+            )
+            else "error"
+        )
+        return "tool_use", {
+            "part": {"tool": item["name"], "state": {"input": args, "status": _status}},
+            "call_id": call_id,
+        }
+
+
+_ToolInputAccumulator = _ServeToolState
+
+
+def _native_call_as_dsh(
+    payload: dict[str, object], tools: list[dict[str, object]] | None
+) -> list[dict[str, object]]:
+    """Native serve-вызов в DSH-вызов через канонический _native_to_tool_calls (fit_args + multiedit)."""
+    part = _as_dict(payload.get("part"))
+    state = _as_dict(part.get("state"))
+    tool = part.get("tool")
+    if not isinstance(tool, str) or not tool:
+        return []
+    args = _as_dict(state.get("input"))
+    return _native_to_tool_calls(tool, args, list(tools or []))
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
+    deadline: float | None = None,
+    proxy_url: str | None = None,
+    on_startup_ready: Callable[[], None] | None = None,
+    emulate_tools: bool = False,
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
+        "prompt_status": None,
+        "transient_error": False,
+    }
+    attempt_deadline = min(
+        deadline if deadline is not None else t0 + TIMEOUT_S, t0 + TIMEOUT_S
+    )
+    if is_client_gone is not None and is_client_gone():
+        result["exit_reason"] = "client_gone"
+        return result
+    try:
+        serve_env = _serve_env(model)
+    except OSError as exc:
+        raise ServeUnavailable(f"serve env failed: {exc}") from exc
+    if proxy_url:
+        serve_env["HTTP_PROXY"] = proxy_url
+        serve_env["HTTPS_PROXY"] = proxy_url
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
+                    port,
+                    password,
+                    method,
+                    path,
+                    body,
+                    timeout=timeout,
+                    conn=conn,
+                    deadline=attempt_deadline,
+                    is_client_gone=is_client_gone,
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
+        ready_deadline = min(time.monotonic() + 3.0, attempt_deadline)
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
+        stop_event = threading.Event()
+        if sse_conn.sock is not None:
+            # Без таймаута сокета: после первого таймаута SocketIO считает поток закрытым,
+            # а любая пауза SSE > 0.5 с превращалась бы в ложный EOF. Остановка — shutdown в finally.
+            _ = sse_conn.sock.settimeout(None)
+        if on_startup_ready is not None:
+            on_startup_ready()
+
+        def _put_event(item: dict[str, object] | None) -> bool:
+            """Неблокирующая постановка с проверкой stop_event."""
+            while not stop_event.is_set():
+                try:
+                    events.put(item, timeout=0.25)
+                    return True
+                except queue.Full:
+                    continue
+            return False
+
+        def _reader() -> None:
+            """Читатель SSE в очередь событий; тишина сокета не рвёт поток."""
+            try:
+                while not stop_event.is_set():
+                    try:
+                        line = sse_resp.readline()
+                    except OSError:
+                        # Сокет закрыт или сброшен: watchdog главного цикла решает судьбу попытки.
+                        break
+                    if not line:
+                        break
+                    text_line = line.decode("utf-8", "replace").strip()
+                    if not text_line.startswith("data:"):
+                        continue
+                    payload = text_line[5:].strip()
+                    if not payload or payload == "[DONE]":
+                        continue
+                    try:
+                        obj: dict[str, object] | None = _loads_serve_object(payload)
+                    except ServeProtocolError:
+                        _ = _put_event({"type": "__invalid_json__", "data": {}})
+                        continue
+                    _ = _put_event(obj)
+            except (OSError, ValueError):
+                pass
+            finally:
+                _ = _put_event(None)
+
+        reader_thread = threading.Thread(target=_reader, daemon=True)
+        reader_thread.start()
+        prompt_send_start = time.monotonic()
 
+        def _prompt_worker() -> None:
+            """Доставка prompt параллельно чтению SSE."""
 
-def _dedup_retry_text(prefix: str, current: str) -> str:
-    """JSON-вариант dedup_prefix: подавить уже отданный префикс, переформулированный текст сохранить целиком."""
-    if prefix and current.startswith(prefix):
-        return current[len(prefix):]
-    return current
+            def _on_headers(status_code: int = 200) -> None:
+                prompt_status["headers_at"] = time.monotonic()
+                prompt_status["status"] = status_code
+                if status_code in (401, 403):
+                    prompt_status["security"] = True
+
+            try:
+                st, _body = _serve_http(
+                    port,
+                    password,
+                    "POST",
+                    f"/api/session/{session_id}/prompt",
+                    {"text": prompt, "files": [], "delivery": "steer", "resume": True},
+                    timeout=65.0,
+                    on_headers=_on_headers,
+                    deadline=attempt_deadline,
+                    is_client_gone=is_client_gone,
+                )
+                prompt_status["status"] = st
+                if st in (401, 403):
+                    prompt_status["security"] = True
+            except (OSError, http.client.HTTPException) as exc:
+                prompt_status["error"] = str(exc)
+
+        prompt_thread = threading.Thread(target=_prompt_worker, daemon=True)
+        prompt_thread.start()
+        tool_state = _ServeToolState()
+        seen_steps: set[str] = set()
+        deadline = min(
+            deadline if deadline is not None else prompt_send_start + TIMEOUT_S,
+            prompt_send_start + TIMEOUT_S,
+        )
+        status_next = max(t0 + FIRST_STATUS_DELAY_S, prompt_send_start + 0.25)
+        _status_emitted = [0]
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
+            # Классификация HTTP-статуса prompt по FALLBACK_DECISION_TABLE до ожидания SSE-события.
+            _ps = prompt_status.get("status")
+            if isinstance(_ps, int) and _ps != 200 and result["prompt_status"] is None:
+                result["prompt_status"] = _ps
+                if _ps in (401, 403):
+                    raise ServeSecurityError(f"serve prompt HTTP {_ps}")
+                if _ps in (400, 404, 422):
+                    raise ServeSecurityError(f"serve prompt HTTP {_ps}")
+                _delivered_now = bool(
+                    prompt_status.get("headers_at")
+                    or result["texts"]
+                    or result["reasonings"]
+                    or result["native_calls"]
+                )
+                result["delivered"] = _delivered_now
+                if _ps == 429:
+                    result["exit_reason"] = "prompt_status_429"
+                    result["transient_error"] = True
+                    return result
+                if 500 <= _ps <= 599:
+                    result["exit_reason"] = f"prompt_status_{_ps}"
+                    return result
+            _prompt_err = prompt_status.get("error")
+            if isinstance(_prompt_err, str):
+                _has_delivery = bool(
+                    prompt_status.get("headers_at")
+                    or result["texts"]
+                    or result["reasonings"]
+                    or result["native_calls"]
+                )
+                if not _has_delivery:
+                    raise ServeUnavailable(f"serve prompt failed: {_prompt_err}")
+                result["delivered"] = True
+                result["exit_reason"] = "prompt_error"
+                result["transient_error"] = True
+                return result
+            if thinking_enabled and on_status is not None and now >= status_next:
+                if result["first_token_at"] is None:
+                    on_status(
+                        STATUS_INITIAL if _status_emitted[0] == 0 else STATUS_WAITING
+                    )
+                    _status_emitted[0] += 1
+                    status_next = now + STATUS_WAITING_INTERVAL_S
+                elif now - last_token_at >= float(STALL_HEARTBEAT_INTERVAL_S):
+                    on_status(STATUS_CONTINUATION)
+                    status_next = now + float(STALL_HEARTBEAT_INTERVAL_S)
+            try:
+                event = events.get(timeout=0.02)
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
+            if etype_raw == "__invalid_json__":
+                result["exit_reason"] = "invalid_serve_event"
+                result["delivered"] = True
+                return result
+            data_raw = _as_dict(event.get("data"))
+            _raw_sid = data_raw.get("sessionID")
+            if (
+                etype_raw not in ("server.connected", "form.created")
+                and isinstance(_raw_sid, str)
+                and _raw_sid
+                and _raw_sid != session_id
+            ):
+                continue
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
+                _mapped = _map_serve_event(event)
+            except ServeProtocolError:
+                result["exit_reason"] = "invalid_serve_event"
+                result["delivered"] = True
+                return result
+            if _mapped is None:
+                continue
+            etype, payload = _mapped
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
+                if text_value:
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
+                if text_value:
+                    if result["first_token_at"] is None:
+                        result["first_token_at"] = time.monotonic()
+                        result["ttft_ms"] = int(
+                            ((result["first_token_at"] or 0.0) - t0) * 1000
+                        )
+                    result["texts"].append(text_value)
+                    last_token_at = time.monotonic()
+                    on_text(text_value)
+            elif etype == "tool_event":
+                if etype_raw == "session.tool.input.delta":
+                    last_token_at = time.monotonic()
+                tool_state.feed(payload)
+                call_id = str(payload.get("id") or "")
+                if etype_raw in (
+                    "session.tool.called",
+                    "session.tool.failed",
+                    "session.tool.success",
+                ):
+                    done = tool_state.complete(call_id, etype_raw)
+                    if done is not None:
+                        last_token_at = time.monotonic()
+                        result["native_calls"].append(done[1])
+                        on_tool(done[1])
+                        if result["first_token_at"] is None:
+                            result["first_token_at"] = time.monotonic()
+                            result["ttft_ms"] = int(
+                                ((result["first_token_at"] or 0.0) - t0) * 1000
+                            )
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
+                    done = tool_state.complete(call_id, etype_raw)
+                    if done is not None:
+                        last_token_at = time.monotonic()
+                        result["native_calls"].append(done[1])
+                        on_tool(done[1])
+                if result["native_calls"] or (
+                    emulate_tools and _split_tool_calls(["".join(result["texts"])])[1]
+                ):
+                    if result["first_token_at"] is None and result["native_calls"]:
+                        result["first_token_at"] = time.monotonic()
+                        result["ttft_ms"] = int(
+                            ((result["first_token_at"] or 0.0) - t0) * 1000
+                        )
+                    result["terminal"] = "tool_calls"
+                    break
+            elif etype == "error":
+                result["error"] = payload
+                result["transient_error"] = _is_transient_stream_error(payload)
+                result["terminal"] = "failed"
+                break
+            elif etype_raw == "session.execution.succeeded":
+                result["terminal"] = "succeeded"
+                break
+        if (
+            not result["terminal"]
+            and not result["exit_reason"]
+            and time.monotonic() >= deadline
+        ):
+            result["exit_reason"] = "timeout"
+        return result
+    finally:
+        _se = locals().get("stop_event")
+        if isinstance(_se, threading.Event):
+            _se.set()
+        if sse_conn is not None:
+            if sse_conn.sock is not None:
+                try:
+                    _ = sse_conn.sock.shutdown(socket.SHUT_RDWR)
+                except OSError:
+                    pass
+            try:
+                sse_conn.close()
+            except OSError:
+                pass
+        for _th_name in ("reader_thread", "prompt_thread"):
+            _th = locals().get(_th_name)
+            if isinstance(_th, threading.Thread):
+                _th.join(timeout=0.5)
+        if session_id:
+            # Не более одной быстрой попытки interrupt/DELETE (<= 0.25 с), затем lease.cleanup().
+            try:
+                _ = _serve_http(
+                    port,
+                    password,
+                    "POST",
+                    f"/api/session/{session_id}/interrupt",
+                    None,
+                    timeout=0.25,
+                    deadline=time.monotonic() + 0.35,
+                )
+            except (OSError, http.client.HTTPException):
+                pass
+            try:
+                _ = _serve_http(
+                    port,
+                    password,
+                    "DELETE",
+                    f"/api/session/{session_id}",
+                    None,
+                    timeout=0.25,
+                    deadline=time.monotonic() + 0.35,
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
@@ -1658,7 +3718,9 @@ def _auth_ok(handler: BaseHTTPRequestHandler) -> bool:
     hdr = handler.headers.get("Authorization", "")
     if hdr.startswith("Bearer "):
         return _token_eq(hdr[7:].strip(), AUTH_KEY)
-    return _token_eq(handler.headers.get("x-api-key", ""), AUTH_KEY) or _token_eq(hdr.strip(), AUTH_KEY)
+    return _token_eq(handler.headers.get("x-api-key", ""), AUTH_KEY) or _token_eq(
+        hdr.strip(), AUTH_KEY
+    )
 
 
 def _flatten_content(content: Any) -> str:
@@ -1691,10 +3753,16 @@ _SECRET = re.compile(
 
 def _mask_secrets(text: str) -> str:
     """Длинные токеноподобные последовательности -> ***; id моделей каталога и алиасов не маскируются."""
+
     def keep_model_ids(match: re.Match[str]) -> str:
         token = match.group(0)
         return token if token in ALLOWED_MODELS or token in MODEL_ALIASES else "***"
 
+    text = re.sub(r"(?i)\b(Bearer\s+)[^\s,;\"']+", r"\1***", text)
+    text = re.sub(r"(?i)(OPENCODE_SERVER_PASSWORD\s*[=:]\s*)[^\s,;]+", r"\1***", text)
+    text = re.sub(
+        r"(?i)(\b(?:https?|socks[45]h?)://)[^/\s:@]+:[^/\s@]+@", r"\1***@", text
+    )
     return _SECRET.sub(keep_model_ids, text)
 
 
@@ -2154,7 +4222,9 @@ def _find_close_in(text: str, start: int, close_tag: str = TOOL_CALL_CLOSE) -> i
 
 
 _STRIP_SCAN_MAX_TAGS = 16  # граница CPU: `_code_context` — O(len) на кандидата
-_BROKEN_BLOCK_NOTICE = "[opencode-zen-bridge: невалидный блок вызова инструмента отброшен]"
+_BROKEN_BLOCK_NOTICE = (
+    "[opencode-zen-bridge: невалидный блок вызова инструмента отброшен]"
+)
 
 
 def _strip_broken_tool_blocks(text: str, *, quiet: bool = False) -> tuple[str, int]:
@@ -2224,7 +4294,9 @@ class ToolCallParser:
         self._history = ""  # весь текст, ушедший в content
         self.tool_calls_count = 0
         self.trailing_chars_after_tool = 0
-        self._tail_after_tool = ""  # весь текст после последнего вызова (для инварианта к чанкам)
+        self._tail_after_tool = (
+            ""  # весь текст после последнего вызова (для инварианта к чанкам)
+        )
 
     def feed(self, text: str) -> None:
         self._buf += text
@@ -2235,19 +4307,22 @@ class ToolCallParser:
 
     def has_open_tool_call(self) -> bool:
         """Тег открыт и ждёт закрытия (или его начало может прийти следующей дельтой)."""
-        return any(open_tag in self._buf for open_tag, _ in TOOL_CALL_TAGS) or self._pending_prefix() > 0
+        return (
+            any(open_tag in self._buf for open_tag, _ in TOOL_CALL_TAGS)
+            or self._pending_prefix() > 0
+        )
 
     def _classify_open(self, after: int, final: bool) -> str:
         """`<tool_call>` в буфере: "real" | "quoted" (inline-код markdown) | "wait" (нужен следующий символ)."""
-        context = _code_context(
-            self._history + self._buf, len(self._history), final
-        )
+        context = _code_context(self._history + self._buf, len(self._history), final)
         if context != "text":
             return "quoted" if context == "code" else "wait"
-        tail = self._buf[after:after + 3]
+        tail = self._buf[after : after + 3]
         if not tail:
             return "real" if final else "wait"
-        if tail[0] != "`" or tail == "```":  # ```json-обёртка внутри блока — настоящий вызов
+        if (
+            tail[0] != "`" or tail == "```"
+        ):  # ```json-обёртка внутри блока — настоящий вызов
             return "real"
         if not final and tail == "`" * len(tail) and len(tail) < 3:
             return "wait"
@@ -2285,11 +4360,13 @@ class ToolCallParser:
                     self._flush_all()  # незакрытый/невалидный блок отдаём текстом
                 return
             inner = self._buf[after:end]
-            self._buf = self._buf[end + len(close_tag):]
+            self._buf = self._buf[end + len(close_tag) :]
             calls = _parse_tool_call_blocks(inner)
             if calls is None:
-                _log(f"tool_call_unparsed bytes={len(inner.encode('utf-8'))} "
-                     f"head={_mask_secrets(inner[:120])!r}")
+                _log(
+                    f"tool_call_unparsed bytes={len(inner.encode('utf-8'))} "
+                    f"head={_mask_secrets(inner[:120])!r}"
+                )
                 self._emit(open_tag + inner + close_tag)
             else:
                 self._history += _OPAQUE_BLOCK
@@ -2308,15 +4385,22 @@ class ToolCallParser:
                 best = (pos, open_tag, close_tag)
         return best
 
-    def _find_close_outside_string(self, start: int, close_tag: str = TOOL_CALL_CLOSE) -> int:
+    def _find_close_outside_string(
+        self, start: int, close_tag: str = TOOL_CALL_CLOSE
+    ) -> int:
         """Позиция закрывающего тега вне строковых литералов JSON буфера, или -1 (см. `_find_close_in`)."""
         return _find_close_in(self._buf, start, close_tag)
 
     def _pending_prefix(self) -> int:
         """Длина хвоста — префикса открывающего тега (его нельзя отдать в content)."""
-        limit = min(max(len(open_tag) for open_tag, _ in TOOL_CALL_TAGS) - 1, len(self._buf))
+        limit = min(
+            max(len(open_tag) for open_tag, _ in TOOL_CALL_TAGS) - 1, len(self._buf)
+        )
         for length in range(limit, 0, -1):
-            if any(self._buf[-length:] == open_tag[:length] for open_tag, _ in TOOL_CALL_TAGS):
+            if any(
+                self._buf[-length:] == open_tag[:length]
+                for open_tag, _ in TOOL_CALL_TAGS
+            ):
                 return length
         return 0
 
@@ -2492,7 +4576,9 @@ def _resolve_opencode_go_auth() -> tuple[str, str]:
     org_id = os.environ.get("OPENCODE_ORG_ID", "org_01M4ZR9TJ6XN1X4MS79ADKQJ60").strip()
     db_path = Path.home() / ".local/share/opencode/opencode.db"
     try:
-        conn = sqlite3.connect(f"file:{quote(str(db_path))}?mode=ro", uri=True, timeout=5)
+        conn = sqlite3.connect(
+            f"file:{quote(str(db_path))}?mode=ro", uri=True, timeout=5
+        )
         try:
             try:
                 row = conn.execute(
@@ -2594,10 +4680,14 @@ _CDATA_END_MIN = 6
 
 
 _TABLE_SEP_RE = re.compile(
-    r"^[ \t]*\|?[ \t]*:?-{3,}:?[ \t]*(?:\|[ \t]*:?-{3,}:?[ \t]*)+\|?[ \t]*$", re.MULTILINE)
+    r"^[ \t]*\|?[ \t]*:?-{3,}:?[ \t]*(?:\|[ \t]*:?-{3,}:?[ \t]*)+\|?[ \t]*$",
+    re.MULTILINE,
+)
 
 
-def _in_active_markdown_table(text: str, loop_start: int, sep_ends: list[int] | None = None) -> bool:
+def _in_active_markdown_table(
+    text: str, loop_start: int, sep_ends: list[int] | None = None
+) -> bool:
     """Перед loop_start идёт строка-разделитель таблицы, а после неё нет пустой строки и все строки с «|».
 
     sep_ends — заранее посчитанные концы разделителей всего text (для многократных проверок без O(n) на вызов).
@@ -2612,10 +4702,12 @@ def _in_active_markdown_table(text: str, loop_start: int, sep_ends: list[int] |
     between = text[last_end:loop_start]
     for eol in ("\r\n", "\n"):  # перевод строки, завершающий сам разделитель
         if between.startswith(eol):
-            between = between[len(eol):]
+            between = between[len(eol) :]
             break
     lines = between.splitlines()
-    if lines and not between.endswith(("\n", "\r")):  # хвост до loop_start оборван посреди строки таблицы
+    if lines and not between.endswith(
+        ("\n", "\r")
+    ):  # хвост до loop_start оборван посреди строки таблицы
         lines.pop()
     # Пустая строка (в т.ч. из пробелов/табов, CRLF) завершает таблицу.
     return all(ln.strip() and "|" in ln and "||" not in ln for ln in lines)
@@ -2633,7 +4725,9 @@ def _is_table_block(unit: str, text: str = "", loop_start: int = 0) -> bool:
     if _in_active_markdown_table(text, loop_start):
         return True
     return all(
-        s.startswith("|") or s.endswith("|") or s.count("|") >= 2
+        s.startswith("|")
+        or s.endswith("|")
+        or s.count("|") >= 2
         or (" | " in s and not s.endswith((".", "!", "?", ";")))
         for s in lines
     )
@@ -2654,7 +4748,9 @@ def _cdata_loop_start(text: str) -> int | None:
     seps = [m.end() for m in _TABLE_SEP_RE.finditer(text)]
 
     def is_terminator(pos: int) -> bool:
-        return "<![CDATA[" not in text[max(0, pos - 300):pos] and not _in_active_markdown_table(text, pos, seps)
+        return "<![CDATA[" not in text[
+            max(0, pos - 300) : pos
+        ] and not _in_active_markdown_table(text, pos, seps)
 
     recent = []
     pos = text.find("]]>", recent_start)
@@ -2665,7 +4761,9 @@ def _cdata_loop_start(text: str) -> int | None:
     if len(recent) < _CDATA_END_MIN:
         return None
     start = recent[0]
-    while (prev := text.rfind("]]>", max(0, start - _CDATA_GAP_MAX), start)) >= 0 and is_terminator(prev):
+    while (
+        prev := text.rfind("]]>", max(0, start - _CDATA_GAP_MAX), start)
+    ) >= 0 and is_terminator(prev):
         start = prev
     return start
 
@@ -2674,7 +4772,10 @@ def _detect_repetition_loop(text: str) -> int | None:
     """Индекс начала зацикленного хвоста (кусок 4..80 символов >= 6 раз подряд, >= 120 символов) или None."""
     tail = text[-_LOOP_TAIL_CHARS:]
     base = len(text) - len(tail)
-    if "<![CDATA[" not in tail[-300:] and (cdata_idx := _cdata_loop_start(text)) is not None:
+    if (
+        "<![CDATA[" not in tail[-300:]
+        and (cdata_idx := _cdata_loop_start(text)) is not None
+    ):
         return cdata_idx
     size_total = len(tail)
     for size in range(4, 81):
@@ -2685,15 +4786,19 @@ def _detect_repetition_loop(text: str) -> int | None:
             continue
         pos = size_total - size
         reps = 1
-        while pos - size >= 0 and tail[pos - size:pos] == unit:
+        while pos - size >= 0 and tail[pos - size : pos] == unit:
             reps += 1
             pos -= size
         if reps < _LOOP_MIN_REPEATS or size * reps < _LOOP_MIN_BLOCK_CHARS:
             continue
-        full_pos = base + pos  # цикл мог начаться раньше хвоста — отматываем по всему тексту
-        while full_pos - size >= 0 and text[full_pos - size:full_pos] == unit:
+        full_pos = (
+            base + pos
+        )  # цикл мог начаться раньше хвоста — отматываем по всему тексту
+        while full_pos - size >= 0 and text[full_pos - size : full_pos] == unit:
             full_pos -= size
-        if _is_table_block(unit, text, full_pos):  # строки markdown-таблицы повторяются законно
+        if _is_table_block(
+            unit, text, full_pos
+        ):  # строки markdown-таблицы повторяются законно
             continue
         return full_pos
     return None
@@ -2702,7 +4807,9 @@ def _detect_repetition_loop(text: str) -> int | None:
 _THOUGHT_CLOSED_RE = re.compile(r"<unused94>thought\b.*?<unused95>\s*", re.DOTALL)
 _THOUGHT_OPEN_RE = re.compile(r"<unused94>thought\b.*$", re.DOTALL)
 _CDATA_LOOP_RE = re.compile(
-    r"(?:(?:Sub-thought finished\.|end\.|stop\.)?\s*\]\]>\s*(?:Let's [^\n\]]*)?\s*){2,}.*$", re.DOTALL)
+    r"(?:(?:Sub-thought finished\.|end\.|stop\.)?\s*\]\]>\s*(?:Let's [^\n\]]*)?\s*){2,}.*$",
+    re.DOTALL,
+)
 
 
 def _strip_unclosed_tool_calls(text: str) -> str:
@@ -2710,10 +4817,16 @@ def _strip_unclosed_tool_calls(text: str) -> str:
 
     Пачка блоков без промежуточных закрытий, закрытая в конце, не затрагивается.
     """
-    close_end = max((text.rfind(close_tag) + len(close_tag) for _, close_tag in TOOL_CALL_TAGS
-                     if close_tag in text), default=0)
+    close_end = max(
+        (
+            text.rfind(close_tag) + len(close_tag)
+            for _, close_tag in TOOL_CALL_TAGS
+            if close_tag in text
+        ),
+        default=0,
+    )
     match = _RAW_CALL_RE.search(text, close_end)
-    return text[:match.start()].rstrip() if match else text
+    return text[: match.start()].rstrip() if match else text
 
 
 def _sanitize_assistant_text(text: str) -> str:
@@ -2737,26 +4850,46 @@ def _sanitize_assistant_text(text: str) -> str:
 GoogleInput = tuple[list[dict[str, Any]], str]  # (contents, systemInstruction) из _messages_to_google_contents
 
 
-def _google_request(model: str, prompt: str, effort: str, stream: bool,
-                    google_input: GoogleInput | None = None):
+def _google_request(
+    model: str,
+    prompt: str,
+    effort: str,
+    stream: bool,
+    google_input: GoogleInput | None = None,
+):
     """Открыть HTTP напрямую: прокси из окружения здесь не используются."""
     meta = ALLOWED_MODELS[model]
     base = urlsplit(meta["base_url"].rstrip("/"))
     token, org_id = _resolve_opencode_go_auth()
     headers = {
-        "Content-Type": "application/json", "User-Agent": "curl/8.7.1",
-        "x-goog-api-key": token, "Authorization": f"Bearer {token}",
+        "Content-Type": "application/json",
+        "User-Agent": "curl/8.7.1",
+        "x-goog-api-key": token,
+        "Authorization": f"Bearer {token}",
         "x-opencode-session": "dsh",
     }
     if org_id:
         headers["x-opencode-org-id"] = org_id
-    contents, system_instruction = google_input if google_input is not None else (None, "")
-    body = json.dumps(_build_google_payload(prompt, effort, int(meta.get("max_output") or 65536),
-                                            contents, system_instruction),
-                      ensure_ascii=False).encode("utf-8")
+    contents, system_instruction = (
+        google_input if google_input is not None else (None, "")
+    )
+    body = json.dumps(
+        _build_google_payload(
+            prompt,
+            effort,
+            int(meta.get("max_output") or 65536),
+            contents,
+            system_instruction,
+        ),
+        ensure_ascii=False,
+    ).encode("utf-8")
     action = "streamGenerateContent?alt=sse" if stream else "generateContent"
     path = f"{base.path}/models/{quote(model, safe='')}:{action}"
-    cls = http.client.HTTPSConnection if base.scheme == "https" else http.client.HTTPConnection
+    cls = (
+        http.client.HTTPSConnection
+        if base.scheme == "https"
+        else http.client.HTTPConnection
+    )
     conn = cls(base.hostname or "127.0.0.1", base.port, timeout=TIMEOUT_S)
     try:
         conn.request("POST", path, body=body, headers=headers)
@@ -2844,6 +4977,7 @@ class Run:
         self.attempts = attempts
         self.proc: subprocess.Popen[str] | None = None
         self.feed: _StdoutFeed | None = None
+        self.is_client_gone: Callable[[], bool] | None = None
 
     def close(self) -> None:
         proc = self.proc
@@ -2922,6 +5056,7 @@ class Run:
         try:
             self.proc = _spawn_with_stdin(cmd, self.prompt, self.workdir, env)
         except OSError as exc:
+            self.res.spawn_limiter.refund()
             gate.release()
             return {"rc": -1, "text": "", "reasoning": "", "usage": {}, "err": f"spawn failed: {exc}",
                     "state": "spawn_failed", "finish": "error"}
@@ -2956,9 +5091,19 @@ class Run:
         err_thread = threading.Thread(target=drain_stderr, daemon=True)
         err_thread.start()
 
+        def on_idle() -> None:
+            """Прервать молчащий JSON-прогон при закрытии клиентского сокета."""
+            nonlocal state
+            if self.is_client_gone is not None and self.is_client_gone():
+                state = "client_gone"
+                if self.proc is not None:
+                    _stop_proc(self.proc)
+
         try:
             self.feed = _StdoutFeed(self.proc)
-            for raw in self.feed.lines(deadline):
+            for raw in self.feed.lines(
+                deadline, idle_s=_STDOUT_POLL_S, on_idle=on_idle
+            ):
                 gate.release()
                 raw = raw.strip()
                 if not raw:
@@ -3070,6 +5215,28 @@ class Run:
                 "state": state, "finish": "stop" if text else "error"}
 
 
+class _LockedWfile:
+    """wfile потокового запроса под общим замком: статус-таймер и основной поток не мешают друг другу."""
+
+    def __init__(self, inner: io.BufferedIOBase, lock: threading.Lock) -> None:
+        self._inner: io.BufferedIOBase = inner
+        self._lock: threading.Lock = lock
+
+    def write(self, data: bytes) -> int:
+        """Записать чанк целиком под замком."""
+        with self._lock:
+            return int(self._inner.write(data) or 0)
+
+    def flush(self) -> None:
+        """Сбросить буфер под замком."""
+        with self._lock:
+            self._inner.flush()
+
+    def __getattr__(self, name: str) -> object:
+        """Прочие атрибуты (closed, close, fileno) — у исходного wfile."""
+        return cast(object, getattr(self._inner, name))
+
+
 class Handler(BaseHTTPRequestHandler):
     protocol_version = "HTTP/1.1"
     timeout = 300
@@ -3081,6 +5248,8 @@ class Handler(BaseHTTPRequestHandler):
         _log(f"http accept error from {client_address}")
 
     _xs: dict[str, Any] | None = None
+    _serve_stream_usage: dict[str, int] | None = None
+    _first_visible: threading.Event | None = None
 
     def _exit(self) -> dict[str, Any]:
         """Состояние выхода текущего запроса для структурной строки O-EXIT/v1."""
@@ -3090,14 +5259,20 @@ class Handler(BaseHTTPRequestHandler):
 
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
         verdict = res.slots.acquire_ex()
         if verdict == "ok":
             return True
-        self._exit()["exit_reason"] = "slot_timeout" if verdict == "timeout" else "slot_overflow"
+        self._exit()["exit_reason"] = (
+            "slot_timeout" if verdict == "timeout" else "slot_overflow"
+        )
         self._send(503, {"error": {"message": "bridge busy", "type": "overloaded"}})
         return False
 
@@ -3120,10 +5295,421 @@ class Handler(BaseHTTPRequestHandler):
         (openai-node/ai-sdk) бросают исключение на чанке с полем error. finish_reason
         не отправляем: пустого успешного завершения быть не должно.
         """
-        self.wfile.write(("data: " + json.dumps(payload, ensure_ascii=False) + "\n\n").encode("utf-8"))
-        self.wfile.write(b"data: [DONE]\n\n")
+        _ = self.wfile.write(
+            ("data: " + json.dumps(payload, ensure_ascii=False) + "\n\n").encode(
+                "utf-8"
+            )
+        )
+        _ = self.wfile.write(b"data: [DONE]\n\n")
         self.wfile.flush()
 
+    def _client_gone_check(self) -> bool:
+        """Клиент закрыл сокет: FIN/RST виден peek без чтения данных."""
+        try:
+            dup_fd = os.dup(self.rfile.fileno())
+        except AttributeError:
+            return False
+        except (OSError, ValueError):
+            return True
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
+        except OSError as exc:
+            # EAGAIN/EWOULDBLOCK — данных нет; ECONNRESET/EPIPE/EBADF — клиент сброшен.
+            return exc.errno not in (errno.EAGAIN, errno.EWOULDBLOCK)
+        except ValueError:
+            return True
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
+        tool_choice: object = None,
+    ) -> bool:
+        """Serve-попытки для SSE; True — запрос завершён, False — fallback на run."""
+        thinking = effort.strip().lower() not in ("", "off", "none")
+        workdir = DEFAULTWORKDIR
+        workdir.mkdir(parents=True, exist_ok=True)
+        last_reasoning: list[str] = [""]
+        # Барьер доставки монотонен на весь запрос: модельный чанк, ушедший клиенту, не снимается.
+        delivered_any = [False]
+        first_visible = self._first_visible or threading.Event()
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
+            first_visible.set()
+            _ = self.wfile.write(chunk.encode("utf-8"))
+            self.wfile.flush()
+
+        def attempt_status(text: str) -> None:
+            """Статусы попытки; STATUS_INITIAL отдаёт только защитный таймер запроса."""
+            if text == STATUS_INITIAL and self._first_visible is not None:
+                return
+            on_status(text)
+
+        def on_reasoning(text: str) -> None:
+            """Модельное размышление клиенту без модификации байтов."""
+            cleaned = _strip_interrupted(text)
+            if not cleaned:
+                return
+            last_reasoning[0] = cleaned
+            delivered_any[0] = True
+            first_visible.set()
+            chunk = format_sse_chunk(
+                resp_id, created, shown_model, {"reasoning_content": cleaned}
+            )
+            _ = self.wfile.write(chunk.encode("utf-8"))
+            self.wfile.flush()
+
+        parser_box: list[ToolCallParser | None] = [None]
+        _inter_buf_text: list[str] = [""]  # буфер потокового фильтра split-маркеров
+
+        def on_text(text: str) -> None:
+            """Модельный текст через ToolCallParser при эмуляции (с потоковым фильтром маркеров)."""
+            _inter_buf_text[0] += text
+            buf = _inter_buf_text[0]
+            # Удерживаем только возможный префикс маркера либо его незавершённую строку.
+            cut = len(buf)
+            folded = buf.lower()
+            for marker in (
+                "i was interrupted right before making tool calls",
+                "the previous response was interrupted. continue from where you left off without repeating completed content",
+            ):
+                pos = folded.find(marker)
+                if pos >= 0 and "\n" not in buf[pos:]:
+                    cut = min(cut, pos)
+                for size in range(1, min(len(marker), len(buf)) + 1):
+                    if folded.endswith(marker[:size]):
+                        cut = min(cut, len(buf) - size)
+            cleaned = _strip_interrupted(buf[:cut])
+            _inter_buf_text[0] = buf[cut:]
+            if not cleaned:
+                return
+            if parser_box[0] is not None:
+                parser_box[0].feed(cleaned)
+            else:
+                emit_content(cleaned)
+
+        def _flush_inter_buf() -> None:
+            """Сброс остатка буфера после завершения попытки."""
+            if not _inter_buf_text[0]:
+                return
+            cleaned = _strip_interrupted(_inter_buf_text[0])
+            _inter_buf_text[0] = ""
+            if not cleaned:
+                return
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
+                delivered_any[0] = True
+                emit_tool_call(call)
+
+        def on_parsed_tool(call: dict[str, object]) -> None:
+            """Вызов из текста модели: учесть в счётчике эмиссии попытки."""
+            emitted_tools_in_attempt[0] += 1
+            delivered_any[0] = True
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
+            _inter_buf_text[0] = ""  # сброс буфера split-маркеров на каждую попытку
+            if parser_box[0] is not None:
+                parser_box[0].finish()
+            parser_box[0] = (
+                ToolCallParser(emit_parsed_content, on_parsed_tool)
+                if emulate_tools
+                else None
+            )
+            if attempts.total_spawns >= MAX_TOTAL_SPAWNS or not attempts.can_spawn():
+                xs["exit_reason"] = "upstream_failed"
+                self._sse_error(_error_payload("serve spawn limit reached"))
+                return True
+            _orig_reasoning, _orig_text = on_reasoning, on_text
+
+            _prior_text = "".join(collected_texts)
+            _dedup_text = (
+                _PrefixDedup(_prior_text) if serve_attempts and _prior_text else None
+            )
+
+            def _text_seen(text: str, _f: Callable[[str], None] = _orig_text) -> None:
+                if _dedup_text is not None:
+                    text = _dedup_text.push(text)
+                    if not text:
+                        return
+                delivered_any[0] = True
+                _f(text)
+
+            gate = _StartupGate()
+            gate.acquire()
+            _limiter_ok = res.spawn_limiter.acquire(
+                max_wait_s=min(SPAWN_WAIT_MAX_S, attempts.remaining_s())
+            )
+            if not _limiter_ok:
+                gate.release()
+                if not force_serve and not delivered_any[0]:
+                    return False
+                xs["exit_reason"] = "upstream_failed"
+                self._sse_error(_error_payload("serve spawn limiter timeout"))
+                return True
+            attempts.note_spawn()
+            if serve_attempts and first_visible.is_set() and thinking:
+                # Единая точка разделителя: ровно один на каждый повтор, только в thinking-режиме.
+                on_status(
+                    f"[мост] Повтор попытки {attempts.total_spawns}/{attempts.max_total}…\n"
+                )
+            serve_attempts += 1
+            try:
+                result = _serve_one_attempt(
+                    model,
+                    current_prompt,
+                    effort,
+                    workdir,
+                    _orig_reasoning,
+                    _text_seen,
+                    on_tool,
+                    attempts.deadline - TIMEOUT_S,
+                    is_client_gone=self._client_gone_check,
+                    on_status=attempt_status,
+                    thinking_enabled=thinking,
+                    deadline=attempts.deadline,
+                    on_startup_ready=gate.release,
+                    emulate_tools=emulate_tools,
+                )
+            except ServeUnavailable as exc:
+                res.serve_health.record_failure()
+                if not force_serve and not delivered_any[0]:
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
+            finally:
+                gate.release()
+            _flush_inter_buf()
+            usage_acc = self._serve_stream_usage or {}
+            for key in ("input", "output", "cached", "reasoning"):
+                usage_acc[key] = int(usage_acc.get(key) or 0) + int(
+                    result["usage"].get(key) or 0
+                )
+            self._serve_stream_usage = usage_acc
+            usage_cur = result["usage"]
+            if "first_event_ms" not in xs or xs.get("first_event_ms") is None:
+                xs["first_event_ms"] = result["first_event_ms"]
+            if "ttft_ms" not in xs or xs.get("ttft_ms") is None:
+                xs["ttft_ms"] = result["ttft_ms"]
+            if parser_box[0] is not None:
+                parser_box[0].finish()
+            if result.get("exit_reason") == "client_gone":
+                xs["exit_reason"] = "client_gone"
+                return True
+            if "first_event_ms" not in xs or xs.get("first_event_ms") is None:
+                xs["first_event_ms"] = result["first_event_ms"]
+            if "ttft_ms" not in xs or xs.get("ttft_ms") is None:
+                xs["ttft_ms"] = result["ttft_ms"]
+            _delivered_now = bool(
+                delivered_any[0]
+                or result.get("delivered")
+                or result["texts"]
+                or result["reasonings"]
+                or result["native_calls"]
+            )
+            delivered_any[0] = _delivered_now
+            if result.get("exit_reason") in (
+                "first_event_timeout",
+                "first_token_timeout",
+                "stall_timeout",
+                "invalid_serve_event",
+                "prompt_error",
+                "timeout",
+            ):
+                reason = str(result["exit_reason"])
+                if reason in ("first_event_timeout", "invalid_serve_event"):
+                    res.serve_health.record_failure()
+                else:
+                    attempts.attempt_done(True, False)
+                if not _delivered_now and not force_serve:
+                    xs["transport"] = "run"
+                    xs["transport_history"] = ["serve", "run"]
+                    return False
+                if attempts.allow_retry(reason):
+                    continue
+                xs["exit_reason"] = reason
+                self._sse_error(_error_payload(f"serve {reason}"))
+                return True
+            if result.get("prompt_status") is not None:
+                _ps_code = int(result["prompt_status"] or 0)
+                if _ps_code == 429 or 500 <= _ps_code <= 599:
+                    attempts.attempt_done(True, False)
+                if not _delivered_now and not force_serve:
+                    xs["transport"] = "run"
+                    xs["transport_history"] = ["serve", "run"]
+                    return False
+                if attempts.allow_retry(f"prompt_status_{_ps_code}"):
+                    continue
+                xs["exit_reason"] = f"prompt_status_{_ps_code}"
+                self._sse_error(_error_payload(f"serve prompt HTTP {_ps_code}"))
+                return True
+            if result.get("exit_reason") in ("prompt_status_429",):
+                attempts.attempt_done(True, False)
+                if attempts.allow_retry("prompt_status_429"):
+                    continue
+                xs["exit_reason"] = "prompt_status_429"
+                self._sse_error(_error_payload("serve prompt HTTP 429"))
+                return True
+            if result["error"] is not None:
+                err = result["error"]
+                if result.get("transient_error"):
+                    attempts.attempt_done(True, False)
+                    _delivered_err = _delivered_now or bool(collected_texts)
+                    if not _delivered_err and not force_serve:
+                        xs["transport"] = "run"
+                        xs["transport_history"] = ["serve", "run"]
+                        return False
+                    if not _delivered_err and attempts.allow_retry(
+                        "serve_transient_error"
+                    ):
+                        continue
+                    # После частичной доставки: step-interruption recovery ниже по incomplete-сигналу.
+                    signal_t = _incomplete_step_signal(
+                        "".join(result["texts"]),
+                        "".join(result["reasonings"]),
+                        tools or [],
+                        True,
+                        int(result["usage"].get("output") or 0),
+                        int(result["usage"].get("reasoning") or 0),
+                        tool_choice=tool_choice,
+                    )
+                    if signal_t and attempts.allow_retry("incomplete_step"):
+                        attempts.signal = signal_t
+                        current_prompt = _rewrite_tool_tags_for_model(
+                            _incomplete_tool_step_prompt(
+                                prompt,
+                                "".join(collected_texts),
+                                tools or [],
+                                tool_choice,
+                                model,
+                            ),
+                            model,
+                        )
+                        continue
+                xs["exit_reason"] = "upstream_failed"
+                self._sse_error(
+                    _error_payload(
+                        f"serve error: {_clean_err(str(err.get('message') or ''))}"
+                    )
+                )
+                return True
+            if result.get("terminal") == "cancelled":
+                xs["exit_reason"] = "cancelled"
+                self._sse_error(_error_payload("serve session cancelled"))
+                return True
+            res.serve_health.record_success()
+            attempts.attempt_done(False, True)
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
+                    tool_choice=tool_choice,
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
+                            prompt,
+                            "".join(collected_texts),
+                            tools or [],
+                            tool_choice,
+                            model,
+                        ),
+                        model,
+                    )
+                    continue
+            return True
+
     def _stream_google_sse(self, model: str, prompt: str, effort: str,
                            emulate_tools: bool = False,
                            google_input: GoogleInput | None = None) -> None:
@@ -3274,11 +5860,21 @@ class Handler(BaseHTTPRequestHandler):
             self._stream_google_sse(model, prompt, effort, emulate_tools, google_input)
             return
         xs = self._exit()
+        xs["transport"] = "run"
+        xs["transport_history"] = ["run"]
         launcher = _resolve_launcher()
         if not os.access(launcher, os.X_OK):
             xs["exit_reason"] = "launcher_missing"
-            self._send(502, {"error": {"message": f"opencode launcher not executable: {launcher}",
-                                       "type": "proxy_error", "code": 502}})
+            self._send(
+                502,
+                {
+                    "error": {
+                        "message": f"opencode launcher not executable: {launcher}",
+                        "type": "proxy_error",
+                        "code": 502,
+                    }
+                },
+            )
             return
 
         res = self._res()
@@ -3296,17 +5892,33 @@ class Handler(BaseHTTPRequestHandler):
         model_route = _model_route(model)
 
         cmd, shown = _build_cmd(launcher, model, effort)
-        _log(f"stream exec model={model_route} {shown} prompt_chars={len(prompt)} cwd={workdir}")
+        _log(
+            f"stream exec model={model_route} {shown} prompt_chars={len(prompt)} cwd={workdir}"
+        )
 
         proc: subprocess.Popen[str] | None = None
         feed: _StdoutFeed | None = None
         gate: _StartupGate | None = None
         run_id = uuid.uuid4().hex[:8]
+        # Записи в wfile сериализуются общим замком; first_visible подавляет таймер статуса.
+        wfile_lock = threading.Lock()
+        first_visible = threading.Event()
+        status_fired_at = [0.0]
+        raw_wfile = self.wfile
+        status_timer: threading.Timer | None = None
 
         try:
             if not attempts.begin_attempt():
                 xs["exit_reason"] = "circuit_open"
-                self._send(503, {"error": {"message": "upstream circuit open", "type": "overloaded"}})
+                self._send(
+                    503,
+                    {
+                        "error": {
+                            "message": "upstream circuit open",
+                            "type": "overloaded",
+                        }
+                    },
+                )
                 return
 
             # 1. Отправляются HTTP-заголовки 200 SSE
@@ -3324,6 +5936,44 @@ class Handler(BaseHTTPRequestHandler):
             )
             self.wfile.write(first_chunk.encode("utf-8"))
             self.wfile.flush()
+            self.wfile = cast(
+                io.BufferedIOBase, cast(object, _LockedWfile(raw_wfile, wfile_lock))
+            )
+            self._first_visible = first_visible
+
+            def _initial_status() -> None:
+                """Защитный таймер: первый видимый статус не позднее FIRST_STATUS_DELAY_S."""
+                with wfile_lock:
+                    if first_visible.is_set():
+                        return
+                    first_visible.set()
+                    status_fired_at[0] = time.monotonic()
+                    try:
+                        _ = raw_wfile.write(
+                            format_sse_chunk(
+                                resp_id,
+                                created,
+                                shown_model,
+                                {"reasoning_content": STATUS_INITIAL},
+                            ).encode("utf-8")
+                        )
+                        raw_wfile.flush()
+                    except (OSError, ValueError):
+                        pass
+
+            if effort.strip().lower() not in ("", "off", "none"):
+                status_timer = threading.Timer(
+                    max(
+                        0.0,
+                        attempts.deadline
+                        - TIMEOUT_S
+                        + FIRST_STATUS_DELAY_S
+                        - time.monotonic(),
+                    ),
+                    _initial_status,
+                )
+                status_timer.daemon = True
+                status_timer.start()
 
             collected_texts: list[str] = []
             usage: dict[str, Any] = {}
@@ -3335,7 +5985,10 @@ class Handler(BaseHTTPRequestHandler):
             dedup: list[_PrefixDedup | None] = [None]
 
             def send_text(text: str) -> None:
-                chunk = format_sse_chunk(resp_id, created, shown_model, {"content": text})
+                chunk = format_sse_chunk(
+                    resp_id, created, shown_model, {"content": text}
+                )
+                first_visible.set()
                 self.wfile.write(chunk.encode("utf-8"))
                 self.wfile.flush()
                 collected_texts.append(text)  # только реально отданное клиенту
@@ -3350,14 +6003,18 @@ class Handler(BaseHTTPRequestHandler):
                         return
                 send_text(text)
 
-            dropped_blocks = [0]  # вырезано нераспарсенных блоков вызова (счётчик на запрос)
+            dropped_blocks = [
+                0
+            ]  # вырезано нераспарсенных блоков вызова (счётчик на запрос)
 
             def emit_parsed_content(text: str) -> None:
                 # Нераспарсенный блок ToolCallParser отдаёт одним куском: сырой тег не уходит ни в SSE, ни в повтор.
                 cleaned, dropped = _strip_broken_tool_blocks(text)
                 if dropped:
                     dropped_blocks[0] += dropped
-                    _log(f"stream dropped {dropped} unparsed tool block(s) from content")
+                    _log(
+                        f"stream dropped {dropped} unparsed tool block(s) from content"
+                    )
                 emit_content(cleaned)
 
             seen_calls: set[str] = set()
@@ -3372,17 +6029,80 @@ class Handler(BaseHTTPRequestHandler):
                     "index": len(tool_calls),
                     "id": "call_" + uuid.uuid4().hex[:24],
                     "type": "function",
-                    "function": {"name": call["name"],
-                                 "arguments": json.dumps(call["arguments"], ensure_ascii=False)},
+                    "function": {
+                        "name": call["name"],
+                        "arguments": json.dumps(call["arguments"], ensure_ascii=False),
+                    },
                 }
                 tool_calls.append(tc)
-                chunk = format_sse_chunk(resp_id, created, shown_model, {"tool_calls": [tc]})
+                chunk = format_sse_chunk(
+                    resp_id, created, shown_model, {"tool_calls": [tc]}
+                )
+                first_visible.set()
                 self.wfile.write(chunk.encode("utf-8"))
                 self.wfile.flush()
 
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
+                    tool_choice=tool_choice
+                    if isinstance(tool_choice, (str, dict)) or tool_choice is None
+                    else None,
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
@@ -3391,23 +6111,35 @@ class Handler(BaseHTTPRequestHandler):
             incomplete_retry = False
             failure: dict[str, Any] | None = None
             while True:
+                if attempts.total_spawns >= MAX_TOTAL_SPAWNS:
+                    failure = {"rc": -1, "tail": "", "timeout": False}
+                    break
                 # 3. Запускается proc (повтор — встроенный инструмент без DSH-двойника,
                 #    незавершённый шаг или транзиторный отказ CLI без вывода) под потолком MAX_TOTAL_SPAWNS
                 if attempts.total_spawns:
-                    _log(f"stream exec retry={retries} fail_retries={fail_retries} model={model_route} "
-                         f"prompt_chars={len(attempt_prompt)} total_spawns={attempts.total_spawns}/{attempts.max_total}")
+                    _log(
+                        f"stream exec retry={retries} fail_retries={fail_retries} model={model_route} "
+                        f"prompt_chars={len(attempt_prompt)} total_spawns={attempts.total_spawns}/{attempts.max_total}"
+                    )
                 gate = _StartupGate()
                 gate.acquire()
-                if not res.spawn_limiter.acquire(max_wait_s=min(SPAWN_WAIT_MAX_S, attempts.remaining_s())):
+                if not res.spawn_limiter.acquire(
+                    max_wait_s=min(SPAWN_WAIT_MAX_S, attempts.remaining_s())
+                ):
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
+                    res.spawn_limiter.refund()
                     gate.release()
                     _log(f"stream spawn failed: {exc}")
                     xs["exit_reason"] = "spawn_failed"
@@ -3417,37 +6149,151 @@ class Handler(BaseHTTPRequestHandler):
 
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
+                first_status_due = attempts.deadline - TIMEOUT_S + FIRST_STATUS_DELAY_S
+                watchdog_state: _WatchdogState = {
+                    "reason": "",
+                    "first_event_at": None,
+                    "first_token_at": None,
+                    "last_token_at": attempt_start,
+                    "status_next": (
+                        first_status_due
+                        if attempts.total_spawns <= 1 and not status_fired_at[0]
+                        else attempt_start + FIRST_STATUS_DELAY_S
+                    ),
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
+                    first_visible.set()
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
+                        and now_s - attempt_start
+                        > max(float(FIRST_TOKEN_TIMEOUT_S), 120.0)
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
+                                if (
+                                    not first_visible.is_set()
+                                    and not status_fired_at[0]
+                                ):
+                                    _initial_status()
+                                    watchdog_state["status_next"] = (
+                                        now_s + STATUS_WAITING_INTERVAL_S
+                                    )
+                                elif (
+                                    status_fired_at[0]
+                                    and now_s - status_fired_at[0]
+                                    < STATUS_WAITING_INTERVAL_S
+                                ):
+                                    # Защитный таймер уже отдал STATUS_INITIAL: без дубля.
+                                    watchdog_state["status_next"] = (
+                                        status_fired_at[0] + STATUS_WAITING_INTERVAL_S
+                                    )
+                                else:
+                                    emit_synthetic(STATUS_WAITING)
+                                    watchdog_state["status_next"] = (
+                                        now_s + STATUS_WAITING_INTERVAL_S
+                                    )
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
@@ -3459,6 +6305,36 @@ class Handler(BaseHTTPRequestHandler):
                         continue
 
                     etype, payload = parse_opencode_event(event)
+                    if etype:
+                        if watchdog_state["first_event_at"] is None:
+                            watchdog_state["first_event_at"] = time.monotonic()
+                            if (
+                                "first_event_ms" not in xs
+                                or xs.get("first_event_ms") is None
+                            ):
+                                xs["first_event_ms"] = int(
+                                    (time.monotonic() - (attempts.deadline - TIMEOUT_S))
+                                    * 1000
+                                )
+                        _token_text = str(
+                            payload.get("reasoning_content")
+                            or payload.get("content")
+                            or ""
+                        )
+                        if _token_text.strip():
+                            if watchdog_state["first_token_at"] is None:
+                                watchdog_state["first_token_at"] = time.monotonic()
+                                if "ttft_ms" not in xs or xs.get("ttft_ms") is None:
+                                    xs["ttft_ms"] = int(
+                                        (
+                                            time.monotonic()
+                                            - (attempts.deadline - TIMEOUT_S)
+                                        )
+                                        * 1000
+                                    )
+                            watchdog_state["last_token_at"] = time.monotonic()
+                            if etype == "reasoning":
+                                watchdog_state["last_reasoning"] = _token_text
                     if etype == "reasoning":
                         rtext = payload.get("reasoning_content")
                         if isinstance(rtext, str):
@@ -3471,7 +6347,10 @@ class Handler(BaseHTTPRequestHandler):
                             attempt_output = True
                             if isinstance(rtext, str) and rtext:
                                 attempt_reasonings.append(rtext)
-                            chunk_str = format_sse_chunk(resp_id, created, shown_model, payload)
+                            chunk_str = format_sse_chunk(
+                                resp_id, created, shown_model, payload
+                            )
+                            first_visible.set()
                             self.wfile.write(chunk_str.encode("utf-8"))
                             self.wfile.flush()
                     elif etype == "text":
@@ -3480,7 +6359,12 @@ class Handler(BaseHTTPRequestHandler):
                             ttext = _strip_interrupted(ttext)
                         if isinstance(ttext, str) and ttext:
                             attempt_output = True
-                            if retries and not incomplete_retry and not attempt_texts and collected_texts:
+                            if (
+                                retries
+                                and not incomplete_retry
+                                and not attempt_texts
+                                and collected_texts
+                            ):
                                 emit_content("\n\n")
                             attempt_texts.append(ttext)
                             if parser is not None:
@@ -3490,19 +6374,29 @@ class Handler(BaseHTTPRequestHandler):
                     elif etype == "step_finish":
                         if payload:
                             for key in ("input", "output", "cached", "reasoning"):
-                                usage[key] = int(usage.get(key) or 0) + int(payload.get(key) or 0)
+                                usage[key] = int(usage.get(key) or 0) + int(
+                                    payload.get(key) or 0
+                                )
                             attempt_output_tokens += int(payload.get("output") or 0)
-                            attempt_reasoning_tokens += int(payload.get("reasoning") or 0)
+                            attempt_reasoning_tokens += int(
+                                payload.get("reasoning") or 0
+                            )
                         if emulate_tools and tool_calls:
                             # Следующие шаги — реакция на «отклонение» (повтор вызова): не нужны.
-                            _log("stream: step with tool call finished, stopping opencode run")
+                            _log(
+                                "stream: step with tool call finished, stopping opencode run"
+                            )
                             _stop_proc(proc)
                             break
                     elif etype == "error":
-                        _log(f"stream provider error: HTTP {payload.get('statusCode')}: {payload.get('message')}")
+                        _log(
+                            f"stream provider error: HTTP {payload.get('statusCode')}: {payload.get('message')}"
+                        )
                         if isinstance(payload.get("statusCode"), int):
                             provider_status = payload["statusCode"]
-                        err_lines.append(f"HTTP {payload.get('statusCode')}: {payload.get('message')}")
+                        err_lines.append(
+                            f"HTTP {payload.get('statusCode')}: {payload.get('message')}"
+                        )
                         if attempt_output:
                             # Оборванный ответ: иначе opencode сам запустит SYNTHETIC-шаг «Continue…» —
                             # останавливаем сразу. Транзиентная ошибка -> повтор шага, детерминированная
@@ -3512,8 +6406,10 @@ class Handler(BaseHTTPRequestHandler):
                                 had_provider_error = True
                             else:
                                 fatal_mid_error = True
-                            _log(f"stream: provider error mid-response (transient={had_provider_error}), "
-                                 "stopping opencode run")
+                            _log(
+                                f"stream: provider error mid-response (transient={had_provider_error}), "
+                                "stopping opencode run"
+                            )
                             stopped_on_error = True
                             _stop_proc(proc)
                             break
@@ -3522,10 +6418,17 @@ class Handler(BaseHTTPRequestHandler):
                         attempt_output = True
                         part = _dict_or_empty(event.get("part"))
                         tstate = _dict_or_empty(part.get("state"))
-                        calls = (_native_to_tool_calls(part.get("tool"), tstate.get("input"), tools or [])
-                                 if emulate_tools else [])
-                        _log(f"opencode built-in tool event: tool={part.get('tool')} status={tstate.get('status')} "
-                             f"mapped={bool(calls)} as={[c['name'] for c in calls]}")
+                        calls = (
+                            _native_to_tool_calls(
+                                part.get("tool"), tstate.get("input"), tools or []
+                            )
+                            if emulate_tools
+                            else []
+                        )
+                        _log(
+                            f"opencode built-in tool event: tool={part.get('tool')} status={tstate.get('status')} "
+                            f"mapped={bool(calls)} as={[c['name'] for c in calls]}"
+                        )
                         if calls:
                             if parser is not None:
                                 parser.finish()
@@ -3575,18 +6478,42 @@ class Handler(BaseHTTPRequestHandler):
                     rc = 1  # остановили сами после ошибки провайдера: для классификации отказа — как выход CLI
                 tail = _clean_err(err_lines[-6:])
                 transient_failure = had_provider_error or (
-                    not attempt_output and _is_retryable_failure(rc, tail, provider_status, False))
-                attempts.attempt_done(transient_failure, attempt_output and not transient_failure)
+                    not attempt_output
+                    and _is_retryable_failure(rc, tail, provider_status, False)
+                )
+                attempts.attempt_done(
+                    transient_failure, attempt_output and not transient_failure
+                )
+                if watchdog_state.get("reason"):
+                    reason_w = str(watchdog_state["reason"])
+                    if attempts.allow_retry(reason_w):
+                        if thinking_enabled and (attempt_reasonings or attempt_texts):
+                            emit_synthetic(
+                                f"[мост] Повтор попытки {attempts.total_spawns + 1}/{attempts.max_total}…\n"
+                            )
+                        continue
+                    xs["exit_reason"] = reason_w
+                    failure = {"rc": rc, "tail": "", "watchdog": reason_w}
+                    break
                 if timed_out:
                     failure = {"rc": rc, "tail": "", "timeout": True}
                     break
                 if rc != 0 and not attempt_output:
                     _log(f"stream cli failed rc={rc} stderr_tail={tail!r}")
-                    if (fail_retries < FAIL_RETRY_LIMIT and time.monotonic() < deadline
-                            and _is_retryable_failure(rc, tail, provider_status, bool(tool_calls))
-                            and attempts.allow_retry("cli_failure", charge_budget=provider_status is not None)):
+                    if (
+                        fail_retries < FAIL_RETRY_LIMIT
+                        and time.monotonic() < deadline
+                        and _is_retryable_failure(
+                            rc, tail, provider_status, bool(tool_calls)
+                        )
+                        and attempts.allow_retry(
+                            "cli_failure", charge_budget=provider_status is not None
+                        )
+                    ):
                         fail_retries += 1
-                        _log(f"stream retry {fail_retries}/{FAIL_RETRY_LIMIT} after cli failure without output")
+                        _log(
+                            f"stream retry {fail_retries}/{FAIL_RETRY_LIMIT} after cli failure without output"
+                        )
                         continue
                     if not collected_texts and not tool_calls:
                         failure = {"rc": rc, "tail": tail}
@@ -3598,58 +6525,133 @@ class Handler(BaseHTTPRequestHandler):
                 if not emulate_tools or tool_calls or time.monotonic() > deadline:
                     break
                 if unmapped:
-                    if unmapped_retries >= NATIVE_RETRY_LIMIT or not attempts.allow_retry("unmapped"):
-                        _log(f"stream unmapped built-in tools={unmapped}: retries exhausted ({unmapped_retries})")
-                        emit_content(f"\n\n[opencode-zen-bridge: модель вызывала недоступный встроенный "
-                                     f"инструмент ({', '.join(unmapped)}); повторы исчерпаны]")
+                    if (
+                        unmapped_retries >= NATIVE_RETRY_LIMIT
+                        or not attempts.allow_retry("unmapped")
+                    ):
+                        _log(
+                            f"stream unmapped built-in tools={unmapped}: retries exhausted ({unmapped_retries})"
+                        )
+                        emit_content(
+                            f"\n\n[opencode-zen-bridge: модель вызывала недоступный встроенный "
+                            f"инструмент ({', '.join(unmapped)}); повторы исчерпаны]"
+                        )
                         break
                     retries += 1
                     unmapped_retries += 1
                     incomplete_retry = False
-                    _log(f"stream unmapped built-in tools={unmapped}: re-prompt "
-                         f"{unmapped_retries}/{NATIVE_RETRY_LIMIT}")
-                    attempt_prompt = _rewrite_tool_tags_for_model(_unavailable_tools_prompt(
-                        attempt_prompt, "".join(attempt_texts), unmapped, tools or [], model), model)
+                    _log(
+                        f"stream unmapped built-in tools={unmapped}: re-prompt "
+                        f"{unmapped_retries}/{NATIVE_RETRY_LIMIT}"
+                    )
+                    attempt_prompt = _rewrite_tool_tags_for_model(
+                        _unavailable_tools_prompt(
+                            attempt_prompt,
+                            "".join(attempt_texts),
+                            unmapped,
+                            tools or [],
+                            model,
+                        ),
+                        model,
+                    )
+                    if thinking_enabled and (attempt_reasonings or attempt_texts):
+                        emit_synthetic(
+                            f"[мост] Повтор попытки {attempts.total_spawns + 1}/{attempts.max_total}…\n"
+                        )
                     continue
-                signal = 0 if provider_status in _FATAL_HTTP else _incomplete_step_signal(
-                    "".join(attempt_texts), "".join(attempt_reasonings), tools or [],
-                    had_provider_error, attempt_output_tokens, attempt_reasoning_tokens,
-                    tool_choice=tool_choice)
+                signal = (
+                    0
+                    if provider_status in _FATAL_HTTP
+                    else _incomplete_step_signal(
+                        "".join(attempt_texts),
+                        "".join(attempt_reasonings),
+                        tools or [],
+                        had_provider_error,
+                        attempt_output_tokens,
+                        attempt_reasoning_tokens,
+                        tool_choice=tool_choice,
+                    )
+                )
                 if not signal:
                     break
-                if incomplete_retries >= NATIVE_RETRY_LIMIT or not attempts.allow_retry("incomplete_step"):
-                    _log(f"stream incomplete tool step: retries exhausted ({incomplete_retries}) signal={signal}")
+                if incomplete_retries >= NATIVE_RETRY_LIMIT or not attempts.allow_retry(
+                    "incomplete_step"
+                ):
+                    _log(
+                        f"stream incomplete tool step: retries exhausted ({incomplete_retries}) signal={signal}"
+                    )
                     break
                 retries += 1
                 incomplete_retries += 1
                 incomplete_retry = True
                 attempts.signal = signal
-                _log(f"stream incomplete tool step: re-prompt {incomplete_retries}/{NATIVE_RETRY_LIMIT} "
-                     f"signal={signal} total_spawns={attempts.total_spawns}/{attempts.max_total}")
-                attempt_prompt = _rewrite_tool_tags_for_model(_incomplete_tool_step_prompt(
-                    prompt, "".join(collected_texts), tools or [], tool_choice, model), model)
+                _log(
+                    f"stream incomplete tool step: re-prompt {incomplete_retries}/{NATIVE_RETRY_LIMIT} "
+                    f"signal={signal} total_spawns={attempts.total_spawns}/{attempts.max_total}"
+                )
+                attempt_prompt = _rewrite_tool_tags_for_model(
+                    _incomplete_tool_step_prompt(
+                        prompt,
+                        "".join(collected_texts),
+                        tools or [],
+                        tool_choice,
+                        model,
+                    ),
+                    model,
+                )
+                if thinking_enabled and (attempt_reasonings or attempt_texts):
+                    emit_synthetic(
+                        f"[мост] Повтор попытки {attempts.total_spawns + 1}/{attempts.max_total}…\n"
+                    )
 
             if failure is not None:
-                _log(f"stream failed model={model} rc={failure['rc']} fail_retries={fail_retries} "
-                     f"total_spawns={attempts.total_spawns}")
+                _log(
+                    f"stream failed model={model} rc={failure['rc']} fail_retries={fail_retries} "
+                    f"total_spawns={attempts.total_spawns}"
+                )
                 if failure.get("timeout"):
                     xs["exit_reason"] = "timeout"
-                    self._sse_error(_error_payload(f"opencode timed out after {TIMEOUT_S:.0f}s"))
+                    self._sse_error(
+                        _error_payload(f"opencode timed out after {TIMEOUT_S:.0f}s")
+                    )
                     return
-                xs["exit_reason"] = "provider_fatal" if failure.get("partial") else "upstream_failed"
-                what = ("opencode provider error after partial output" if failure.get("partial")
-                        else "opencode run failed")
-                self._sse_error(_error_payload(
-                    f"{what} (rc={failure['rc']})"
-                    + ("" if failure.get("partial") else " without output")
-                    + (f": {failure['tail']}" if failure["tail"] else ""), failure["tail"]))
+                if failure.get("watchdog"):
+                    wd_obj: object = failure.get("watchdog")
+                    wd_reason = wd_obj if isinstance(wd_obj, str) else ""
+                    xs["exit_reason"] = wd_reason
+                    self._sse_error(_error_payload(f"opencode {wd_reason}"))
+                    return
+                xs["exit_reason"] = (
+                    "provider_fatal" if failure.get("partial") else "upstream_failed"
+                )
+                what = (
+                    "opencode provider error after partial output"
+                    if failure.get("partial")
+                    else "opencode run failed"
+                )
+                self._sse_error(
+                    _error_payload(
+                        f"{what} (rc={failure['rc']})"
+                        + ("" if failure.get("partial") else " without output")
+                        + (f": {failure['tail']}" if failure["tail"] else ""),
+                        failure["tail"] if isinstance(failure["tail"], str) else "",
+                    )
+                )
                 return
 
-            if dropped_blocks[0] and not tool_calls and not "".join(collected_texts).strip():
-                emit_content(_BROKEN_BLOCK_NOTICE)  # иначе клиент получил бы пустой ответ
+            if (
+                dropped_blocks[0]
+                and not tool_calls
+                and not "".join(collected_texts).strip()
+            ):
+                emit_content(
+                    _BROKEN_BLOCK_NOTICE
+                )  # иначе клиент получил бы пустой ответ
             full_text = "".join(collected_texts)
             prompt_tokens = int(usage.get("input") or 0) or _estimate_tokens(prompt)
-            completion_tokens = int(usage.get("output") or 0) or _estimate_tokens(full_text)
+            completion_tokens = int(usage.get("output") or 0) or _estimate_tokens(
+                full_text
+            )
 
             final_chunk = format_sse_chunk(
                 resp_id,
@@ -3657,16 +6659,27 @@ class Handler(BaseHTTPRequestHandler):
                 shown_model,
                 {},
                 finish_reason="tool_calls" if tool_calls else "stop",
-                usage=_build_openai_usage(prompt_tokens, completion_tokens,
-                                          int(usage.get("cached") or 0), int(usage.get("reasoning") or 0)),
+                usage=_build_openai_usage(
+                    prompt_tokens,
+                    completion_tokens,
+                    int(usage.get("cached") or 0),
+                    int(usage.get("reasoning") or 0),
+                ),
             )
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
@@ -3677,6 +6690,13 @@ class Handler(BaseHTTPRequestHandler):
                 except OSError:
                     pass
         finally:
+            # Таймер статуса не должен писать после завершения запроса.
+            first_visible.set()
+            if status_timer is not None:
+                status_timer.cancel()
+            with wfile_lock:
+                self.wfile = raw_wfile
+            self._first_visible = None
             if gate is not None:
                 gate.release()
             if proc is not None:
@@ -3697,6 +6717,344 @@ class Handler(BaseHTTPRequestHandler):
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
+        delivered_any = False
+        _prior_content = ""
+        _seen_call_keys: set[str] = set()
+
+        def _add_call(call: dict[str, object]) -> None:
+            """Вызов инструмента в итог: одинаковый (name, arguments) не дублируется."""
+            key = _call_key(str(call["name"]), call["arguments"])
+            if key in _seen_call_keys:
+                return
+            _seen_call_keys.add(key)
+            tool_calls_all.append(
+                {
+                    "index": len(tool_calls_all),
+                    "id": "call_" + uuid.uuid4().hex[:24],
+                    "type": "function",
+                    "function": {
+                        "name": call["name"],
+                        "arguments": json.dumps(call["arguments"], ensure_ascii=False),
+                    },
+                }
+            )
+
+        while True:
+            if attempts.total_spawns >= MAX_TOTAL_SPAWNS or not attempts.can_spawn():
+                xs["exit_reason"] = "upstream_failed"
+                self._send(502, _error_payload("serve spawn limit reached"))
+                return True
+            reasonings: list[str] = []
+            texts: list[str] = []
+            natives: list[dict[str, object]] = []
+            _gate_j = _StartupGate()
+            _gate_j.acquire()
+            if not res.spawn_limiter.acquire(
+                max_wait_s=min(SPAWN_WAIT_MAX_S, attempts.remaining_s())
+            ):
+                _gate_j.release()
+                _j_delivered = delivered_any or bool(
+                    contents
+                    or reasonings_all
+                    or tool_calls_all
+                    or texts
+                    or reasonings
+                    or natives
+                )
+                if not force_serve and not _j_delivered:
+                    return False
+                xs["exit_reason"] = "upstream_failed"
+                self._send(502, _error_payload("serve spawn limiter timeout"))
+                return True
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
+                    is_client_gone=self._client_gone_check,
+                    on_status=lambda _t: None,
+                    thinking_enabled=thinking,
+                    deadline=attempts.deadline,
+                    on_startup_ready=_gate_j.release,
+                    emulate_tools=emulate_tools,
+                )
+            except ServeUnavailable as exc:
+                res.serve_health.record_failure()
+                _j_delivered = delivered_any or bool(
+                    contents
+                    or reasonings_all
+                    or tool_calls_all
+                    or texts
+                    or reasonings
+                    or natives
+                )
+                if not force_serve and not _j_delivered:
+                    return False
+                xs["exit_reason"] = "upstream_failed"
+                self._send(502, _error_payload(f"serve unavailable: {exc}"))
+                return True
+            except ServeSecurityError as exc:
+                xs["exit_reason"] = "provider_fatal"
+                self._send(502, _error_payload(f"serve security failure: {exc}"))
+                return True
+            finally:
+                _gate_j.release()
+            if "first_event_ms" not in xs or xs.get("first_event_ms") is None:
+                xs["first_event_ms"] = result["first_event_ms"]
+            if "ttft_ms" not in xs or xs.get("ttft_ms") is None:
+                xs["ttft_ms"] = result["ttft_ms"]
+            if result.get("exit_reason") == "client_gone":
+                xs["exit_reason"] = "client_gone"
+                return True
+            # Токены неуспешных попыток тоже учитываются (как в потоковом пути).
+            for _tk in ("input", "output", "cached", "reasoning"):
+                tokens[_tk] = tokens.get(_tk, 0) + int(result["usage"].get(_tk) or 0)
+            _delivered_j = bool(
+                delivered_any
+                or contents
+                or reasonings_all
+                or tool_calls_all
+                or texts
+                or reasonings
+                or natives
+                or result.get("delivered")
+            )
+            delivered_any = _delivered_j
+            if result.get("exit_reason") in (
+                "first_event_timeout",
+                "first_token_timeout",
+                "stall_timeout",
+                "invalid_serve_event",
+                "prompt_error",
+                "timeout",
+            ):
+                reason = str(result["exit_reason"])
+                if reason in ("first_event_timeout", "invalid_serve_event"):
+                    res.serve_health.record_failure()
+                else:
+                    attempts.attempt_done(True, False)
+                if not _delivered_j and not force_serve:
+                    return False
+                if attempts.allow_retry(reason):
+                    continue
+                xs["exit_reason"] = reason
+                self._send(502, _error_payload(f"serve {reason}"))
+                return True
+            if result.get("prompt_status") is not None:
+                _ps_j = int(result["prompt_status"] or 0)
+                if _ps_j == 429 or 500 <= _ps_j <= 599:
+                    attempts.attempt_done(True, False)
+                if not _delivered_j and not force_serve:
+                    return False
+                if attempts.allow_retry(f"prompt_status_{_ps_j}"):
+                    continue
+                xs["exit_reason"] = f"prompt_status_{_ps_j}"
+                self._send(502, _error_payload(f"serve prompt HTTP {_ps_j}"))
+                return True
+            if result["error"] is not None:
+                err = result["error"]
+                if result.get("transient_error"):
+                    attempts.attempt_done(True, False)
+                    partial_content = "".join(texts)
+                    if emulate_tools and partial_content:
+                        partial_texts: list[str] = []
+                        partial_calls: list[dict[str, object]] = []
+                        partial_parser = ToolCallParser(
+                            partial_texts.append, partial_calls.append
+                        )
+                        partial_parser.feed(partial_content)
+                        partial_parser.finish()
+                        partial_content, _partial_dropped = _strip_broken_tool_blocks(
+                            "".join(partial_texts)
+                        )
+                    if _prior_content:
+                        partial_content = _dedup_retry_text(
+                            _prior_content, partial_content
+                        )
+                    if partial_content:
+                        contents.append(partial_content)
+                    reasonings_all.extend(reasonings)
+                    if not _delivered_j and not force_serve:
+                        return False
+                    if not texts and attempts.allow_retry("serve_transient_error"):
+                        _prior_content = "\n\n".join(c for c in contents if c)
+                        continue
+                    _sig_j = _incomplete_step_signal(
+                        "".join(texts),
+                        "".join(reasonings),
+                        tools or [],
+                        True,
+                        int(result["usage"].get("output") or 0),
+                        int(result["usage"].get("reasoning") or 0),
+                        tool_choice=tool_choice,
+                    )
+                    if _sig_j and attempts.allow_retry("incomplete_step"):
+                        _prior_content = "\n\n".join(c for c in contents if c)
+                        current_prompt = _rewrite_tool_tags_for_model(
+                            _incomplete_tool_step_prompt(
+                                prompt,
+                                "".join(contents),
+                                tools or [],
+                                tool_choice,
+                                model,
+                            ),
+                            model,
+                        )
+                        continue
+                xs["exit_reason"] = "upstream_failed"
+                self._send(
+                    502,
+                    _error_payload(
+                        f"serve error: {_clean_err(str(err.get('message') or ''))}"
+                    ),
+                )
+                return True
+            if result.get("terminal") == "cancelled":
+                xs["exit_reason"] = "cancelled"
+                self._send(502, _error_payload("serve session cancelled"))
+                return True
+            res.serve_health.record_success()
+            attempts.attempt_done(False, True)
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
+            if _prior_content:
+                content = _dedup_retry_text(_prior_content, content)
+            if content:
+                contents.append(content)
+            for call in calls:
+                _add_call(call)
+            unmapped: list[str] = []
+            for native in natives:
+                part = _as_dict(native.get("part"))
+                mapped = _native_call_as_dsh(native, tools) if emulate_tools else []
+                if not mapped and emulate_tools and part.get("tool"):
+                    unmapped.append(str(part.get("tool")))
+                for call in mapped:
+                    _add_call(call)
+            usage = result["usage"]
+            if not emulate_tools or tool_calls_all:
+                break
+            if unmapped:
+                if unmapped_retries >= NATIVE_RETRY_LIMIT or not attempts.allow_retry(
+                    "unmapped"
+                ):
+                    break
+                unmapped_retries += 1
+                _prior_content = "\n\n".join(c for c in contents if c)
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
+            _prior_content = "\n\n".join(c for c in contents if c)
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
+        if self._client_gone_check():
+            xs["exit_reason"] = "client_gone"
+            return True
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
@@ -3716,30 +7074,91 @@ class Handler(BaseHTTPRequestHandler):
         res = self._res()
         if not self._acquire_slot(res):
             return
-        attempts = _RequestAttempts(res, time.monotonic() + TIMEOUT_S,
-                                    use_breaker=not _is_google_direct_model(model))
+        attempts = _RequestAttempts(
+            res,
+            time.monotonic() + TIMEOUT_S,
+            use_breaker=not _is_google_direct_model(model),
+        )
         xs["attempts"] = attempts
         try:
             if not attempts.begin_attempt():
                 xs["exit_reason"] = "circuit_open"
-                self._send(503, {"error": {"message": "upstream circuit open", "type": "overloaded"}})
+                self._send(
+                    503,
+                    {
+                        "error": {
+                            "message": "upstream circuit open",
+                            "type": "overloaded",
+                        }
+                    },
+                )
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
+                    tool_choice
+                    if isinstance(tool_choice, (str, dict)) or tool_choice is None
+                    else None,
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
+                if not attempts.can_spawn():
+                    # Суммарный потолок serve + run: четвёртый спавн запрещён.
+                    xs["exit_reason"] = "upstream_failed"
+                    self._send(502, _error_payload("spawn limit reached"))
+                    return
                 if retries:
-                    _log(f"exec retry={retries} ({'incomplete tool step' if incomplete_retry else 'unmapped built-in tool'})"
-                         f" total_spawns={attempts.total_spawns}/{attempts.max_total}")
-                run = Run(model, attempt_prompt, effort, DEFAULTWORKDIR,
-                          tools=(tools or []) if emulate_tools else None, google_input=google_input,
-                          attempts=attempts, resilience=res)
+                    _log(
+                        f"exec retry={retries} ({'incomplete tool step' if incomplete_retry else 'unmapped built-in tool'})"
+                        f" total_spawns={attempts.total_spawns}/{attempts.max_total}"
+                    )
+                run = Run(
+                    model,
+                    attempt_prompt,
+                    effort,
+                    DEFAULTWORKDIR,
+                    tools=(tools or []) if emulate_tools else None,
+                    google_input=google_input,
+                    attempts=attempts,
+                    resilience=res,
+                )
+                run.is_client_gone = self._client_gone_check
                 try:
                     out = run.execute()
                 finally:
                     run.close()
 
-                if out.get("state") in ("launcher_missing", "spawn_failed", "client_gone"):
+                if out.get("state") in (
+                    "launcher_missing",
+                    "spawn_failed",
+                    "client_gone",
+                ):
                     xs["exit_reason"] = str(out["state"])
-                    self._send(502, {"error": {"message": out.get("err") or out["state"],
-                                               "type": "proxy_error", "code": 502}})
+                    self._send(
+                        502,
+                        {
+                            "error": {
+                                "message": out.get("err") or out["state"],
+                                "type": "proxy_error",
+                                "code": 502,
+                            }
+                        },
+                    )
                     return
                 content = out["text"]
                 if emulate_tools and content:
@@ -3754,66 +7173,120 @@ class Handler(BaseHTTPRequestHandler):
                             content = ""
                 if incomplete_retry:
                     # Уже отданная преамбула подавляется, переформулированный текст сохраняется целиком.
-                    content = _dedup_retry_text("\n\n".join(c for c in contents if c), content)
+                    content = _dedup_retry_text(
+                        "\n\n".join(c for c in contents if c), content
+                    )
                 if content:
                     contents.append(content)
                 if out.get("reasoning"):
                     reasonings.append(out["reasoning"])
                 for key in ("input", "output", "cached", "reasoning"):
-                    tokens[key] = tokens.get(key, 0) + int((out.get("usage") or {}).get(key) or 0)
+                    tokens[key] = tokens.get(key, 0) + int(
+                        (out.get("usage") or {}).get(key) or 0
+                    )
                 unmapped: list[str] = []
                 if emulate_tools:
                     for native in out.get("native_calls") or []:
-                        calls = _native_to_tool_calls(native.get("tool"), native.get("input"), tools or [])
-                        _log(f"opencode built-in tool event: tool={native.get('tool')} status={native.get('status')} "
-                             f"mapped={bool(calls)} as={[c['name'] for c in calls]}")
+                        calls = _native_to_tool_calls(
+                            native.get("tool"), native.get("input"), tools or []
+                        )
+                        _log(
+                            f"opencode built-in tool event: tool={native.get('tool')} status={native.get('status')} "
+                            f"mapped={bool(calls)} as={[c['name'] for c in calls]}"
+                        )
                         if not calls:
                             unmapped.append(str(native.get("tool")))
                         for call in calls:
-                            tool_calls.append({
-                                "index": len(tool_calls), "id": "call_" + uuid.uuid4().hex[:24], "type": "function",
-                                "function": {"name": call["name"],
-                                             "arguments": json.dumps(call["arguments"], ensure_ascii=False)}})
+                            tool_calls.append(
+                                {
+                                    "index": len(tool_calls),
+                                    "id": "call_" + uuid.uuid4().hex[:24],
+                                    "type": "function",
+                                    "function": {
+                                        "name": call["name"],
+                                        "arguments": json.dumps(
+                                            call["arguments"], ensure_ascii=False
+                                        ),
+                                    },
+                                }
+                            )
                 if out.get("fatal_error") and not tool_calls:
                     tail = _clean_err(str(out.get("err") or ""), 500)
                     xs["exit_reason"] = "provider_fatal"
-                    self._send(502, _error_payload(
-                        f"opencode provider error after partial output (HTTP {out.get('provider_status')})"
-                        + (f": {tail}" if tail else ""), tail))
+                    self._send(
+                        502,
+                        _error_payload(
+                            f"opencode provider error after partial output (HTTP {out.get('provider_status')})"
+                            + (f": {tail}" if tail else ""),
+                            tail,
+                        ),
+                    )
                     return
                 if not emulate_tools or tool_calls:
                     break
                 if unmapped:
-                    if unmapped_retries >= NATIVE_RETRY_LIMIT or not attempts.allow_retry("unmapped"):
-                        _log(f"unmapped built-in tools={unmapped}: retries exhausted ({unmapped_retries})")
-                        contents.append(f"[opencode-zen-bridge: модель вызывала недоступный встроенный "
-                                        f"инструмент ({', '.join(unmapped)}); повторы исчерпаны]")
+                    if (
+                        unmapped_retries >= NATIVE_RETRY_LIMIT
+                        or not attempts.allow_retry("unmapped")
+                    ):
+                        _log(
+                            f"unmapped built-in tools={unmapped}: retries exhausted ({unmapped_retries})"
+                        )
+                        contents.append(
+                            f"[opencode-zen-bridge: модель вызывала недоступный встроенный "
+                            f"инструмент ({', '.join(unmapped)}); повторы исчерпаны]"
+                        )
                         break
                     retries += 1
                     unmapped_retries += 1
                     incomplete_retry = False
-                    _log(f"unmapped built-in tools={unmapped}: re-prompt {unmapped_retries}/{NATIVE_RETRY_LIMIT}")
+                    _log(
+                        f"unmapped built-in tools={unmapped}: re-prompt {unmapped_retries}/{NATIVE_RETRY_LIMIT}"
+                    )
                     attempt_prompt = _rewrite_tool_tags_for_model(
                         _unavailable_tools_prompt(attempt_prompt, out["text"], unmapped, tools or [], model), model)
                     continue
                 run_usage = out.get("usage") or {}
-                signal = 0 if out.get("provider_status") in _FATAL_HTTP else _incomplete_step_signal(
-                    out["text"], str(out.get("reasoning") or ""), tools or [],
-                    bool(out.get("had_error")), int(run_usage.get("output") or 0),
-                    int(run_usage.get("reasoning") or 0), tool_choice=tool_choice)
+                signal = (
+                    0
+                    if out.get("provider_status") in _FATAL_HTTP
+                    else _incomplete_step_signal(
+                        out["text"],
+                        str(out.get("reasoning") or ""),
+                        tools or [],
+                        bool(out.get("had_error")),
+                        int(run_usage.get("output") or 0),
+                        int(run_usage.get("reasoning") or 0),
+                        tool_choice=tool_choice,
+                    )
+                )
                 if not signal:
                     break
-                if incomplete_retries >= NATIVE_RETRY_LIMIT or not attempts.allow_retry("incomplete_step"):
-                    _log(f"incomplete tool step: retries exhausted ({incomplete_retries}) signal={signal}")
+                if incomplete_retries >= NATIVE_RETRY_LIMIT or not attempts.allow_retry(
+                    "incomplete_step"
+                ):
+                    _log(
+                        f"incomplete tool step: retries exhausted ({incomplete_retries}) signal={signal}"
+                    )
                     break
                 retries += 1
                 incomplete_retries += 1
                 incomplete_retry = True
                 attempts.signal = signal
-                _log(f"incomplete tool step: re-prompt {incomplete_retries}/{NATIVE_RETRY_LIMIT} "
-                     f"signal={signal} total_spawns={attempts.total_spawns}/{attempts.max_total}")
-                attempt_prompt = _rewrite_tool_tags_for_model(_incomplete_tool_step_prompt(
-                    prompt, "\n\n".join(c for c in contents if c), tools or [], tool_choice, model), model)
+                _log(
+                    f"incomplete tool step: re-prompt {incomplete_retries}/{NATIVE_RETRY_LIMIT} "
+                    f"signal={signal} total_spawns={attempts.total_spawns}/{attempts.max_total}"
+                )
+                attempt_prompt = _rewrite_tool_tags_for_model(
+                    _incomplete_tool_step_prompt(
+                        prompt,
+                        "\n\n".join(c for c in contents if c),
+                        tools or [],
+                        tool_choice,
+                        model,
+                    ),
+                    model,
+                )
         finally:
             attempts.commit()
             res.slots.release()
@@ -3832,14 +7305,21 @@ class Handler(BaseHTTPRequestHandler):
             tc["index"] = i
         content = "\n\n".join(c for c in contents if c)
         if dropped_blocks and not content.strip() and not tool_calls:
-            content = _BROKEN_BLOCK_NOTICE  # иначе клиент получил бы пустой ответ или 502
+            content = (
+                _BROKEN_BLOCK_NOTICE  # иначе клиент получил бы пустой ответ или 502
+            )
         if not content and not tool_calls:
             # Пустой текст с ненулевым rc/ошибкой провайдера — честная 502, не выдуманный ответ.
             tail = _clean_err(str(out.get("err") or ""), 500)
             xs["exit_reason"] = "upstream_failed"
-            self._send(502, _error_payload(
-                f"opencode run produced no text (rc={out.get('rc')}, state={out.get('state')})"
-                + (f": {tail}" if tail else ""), tail))
+            self._send(
+                502,
+                _error_payload(
+                    f"opencode run produced no text (rc={out.get('rc')}, state={out.get('state')})"
+                    + (f": {tail}" if tail else ""),
+                    tail,
+                ),
+            )
             return
 
         prompt_tokens = int(tokens.get("input") or 0) or _estimate_tokens(prompt)
@@ -3852,19 +7332,33 @@ class Handler(BaseHTTPRequestHandler):
         if tool_calls:
             msg["tool_calls"] = tool_calls
             finish = "tool_calls"
-        xs.update(exit_reason="ok", tools=len(tool_calls), out_chars=len(content), rc=out.get("rc"))
-        _log(f"done model={model} rc={out.get('rc')} state={out.get('state')} tools={len(tool_calls)} "
-             f"out_chars={len(content)} retries={retries} total_spawns={attempts.total_spawns}")
-
-        self._send(200, {
-            "id": f"chatcmpl-oczen-{uuid.uuid4().hex[:12]}", "object": "chat.completion",
-            "created": int(time.time()), "model": reported_model or model,
-            "choices": [{"index": 0,
-                         "message": msg,
-                         "finish_reason": finish}],
-            "usage": _build_openai_usage(prompt_tokens, completion_tokens,
-                                         tokens.get("cached", 0), tokens.get("reasoning", 0)),
-        })
+        xs.update(
+            exit_reason="ok",
+            tools=len(tool_calls),
+            out_chars=len(content),
+            rc=out.get("rc"),
+        )
+        _log(
+            f"done model={model} rc={out.get('rc')} state={out.get('state')} tools={len(tool_calls)} "
+            f"out_chars={len(content)} retries={retries} total_spawns={attempts.total_spawns}"
+        )
+
+        self._send(
+            200,
+            {
+                "id": f"chatcmpl-oczen-{uuid.uuid4().hex[:12]}",
+                "object": "chat.completion",
+                "created": int(time.time()),
+                "model": reported_model or model,
+                "choices": [{"index": 0, "message": msg, "finish_reason": finish}],
+                "usage": _build_openai_usage(
+                    prompt_tokens,
+                    completion_tokens,
+                    tokens.get("cached", 0),
+                    tokens.get("reasoning", 0),
+                ),
+            },
+        )
 
     # ---- HTTP --------------------------------------------------------------------
     def do_GET(self) -> None:
@@ -3873,26 +7367,50 @@ class Handler(BaseHTTPRequestHandler):
             _maybe_reload_catalog()
             with _active_lock:
                 active = len(_active)
-            self._send(200, {
-                "ok": True, "transport": "opencode-zen-cli",
-                "models": sorted(ALLOWED_MODELS), "default_model": _effective_default_model(),
-                "catalog_mode": CATALOG_MODE, "catalog_source": CATALOG_SOURCE,
-                "active": active, "max_concurrent": MAX_CONCURRENT,
-                "stream": True, "tool_emulation": True,
-                "uptime_s": int(time.time() - _started),
-            })
+            self._send(
+                200,
+                {
+                    "ok": True,
+                    "transport": "opencode-zen-cli",
+                    "models": sorted(ALLOWED_MODELS),
+                    "default_model": _effective_default_model(),
+                    "catalog_mode": CATALOG_MODE,
+                    "catalog_source": CATALOG_SOURCE,
+                    "active": active,
+                    "max_concurrent": MAX_CONCURRENT,
+                    "stream": True,
+                    "tool_emulation": True,
+                    "uptime_s": int(time.time() - _started),
+                },
+            )
             return
         if not _auth_ok(self):
-            self._send(401, {"error": {"message": "unauthorized", "type": "auth_error"}})
+            self._send(
+                401, {"error": {"message": "unauthorized", "type": "auth_error"}}
+            )
             return
         if path in ("/v1/models", "/models"):
             _maybe_reload_catalog()
-            self._send(200, {"object": "list", "data": [
-                {"id": mid, "object": "model", "owned_by": "opencode-zen", "created": 0,
-                 "context_length": meta["context_length"], "max_output": meta["max_output"],
-                 "reasoning_efforts": list(meta.get("reasoning_efforts") or [])}
-                for mid, meta in sorted(ALLOWED_MODELS.items())
-            ]})
+            self._send(
+                200,
+                {
+                    "object": "list",
+                    "data": [
+                        {
+                            "id": mid,
+                            "object": "model",
+                            "owned_by": "opencode-zen",
+                            "created": 0,
+                            "context_length": meta["context_length"],
+                            "max_output": meta["max_output"],
+                            "reasoning_efforts": list(
+                                meta.get("reasoning_efforts") or []
+                            ),
+                        }
+                        for mid, meta in sorted(ALLOWED_MODELS.items())
+                    ],
+                },
+            )
             return
         self._send(404, {"error": {"message": f"not found: {path}"}})
 
@@ -4005,8 +7523,11 @@ def main() -> int:
         WORKSPACE.mkdir(parents=True, exist_ok=True)
     except OSError as exc:
         _log(f"workspace mkdir failed: {exc}")
-    _log(f"start host={HOST} port={PORT} catalog={CATALOG_MODE}/{CATALOG_SOURCE} "
-         f"models={sorted(ALLOWED_MODELS)} launcher={_resolve_launcher()}")
+    _ = _startup_reaper()
+    _log(
+        f"start host={HOST} port={PORT} catalog={CATALOG_MODE}/{CATALOG_SOURCE} "
+        f"models={sorted(ALLOWED_MODELS)} launcher={_resolve_launcher()}"
+    )
     server = Server((HOST, PORT), Handler, resilience=_DEFAULT_RESILIENCE)
     try:
         server.serve_forever()
diff --git a/bridges/opencode-zen-bridge/tests/test_step_interruption.py b/bridges/opencode-zen-bridge/tests/test_step_interruption.py
index 46df891..defcf65 100644
--- a/bridges/opencode-zen-bridge/tests/test_step_interruption.py
+++ b/bridges/opencode-zen-bridge/tests/test_step_interruption.py
@@ -21,9 +21,11 @@ import socket
 import tempfile
 import threading
 import unittest
+from unittest import mock
 import urllib.request
 from pathlib import Path
 from typing import Any
+from typing import Protocol, cast
 
 import server
 from tests._fake_cli import allow_child_env
@@ -64,7 +66,7 @@ INVOKE_CALLS = CALLS.replace("tool_call", "tool_invoke")
 # Реальный шаг glm-5.3-flash-free: апстрим вырезал `<tool_call>…` из text, а 97 токенов выставил.
 SWALLOWED_TEXT = "2026-10-24 (MSK) — статус: проверяю вывод джобы job_fetch_01 и читаю goal.md."
 
-FAKE_OPENCODE = r'''#!/usr/bin/env python3
+FAKE_OPENCODE = r"""#!/usr/bin/env python3
 import json, os, sys, time
 counter = os.environ["FAKE_OC_COUNTER"]
 n = int(open(counter).read()) if os.path.exists(counter) else 0
@@ -139,10 +141,29 @@ elif mode == "unmapped_then_promise" and n == 2:
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
+
+
+class _EnvPatcher(Protocol):
+    """Протокол patch.dict для изоляции окружения."""
+
+    def start(self) -> object:
+        """Запустить patch."""
+        ...
+
+    def stop(self) -> object:
+        """Остановить patch."""
+        ...
 
 
 class TestStepInterruptionLive(unittest.TestCase):
@@ -176,20 +197,29 @@ class TestStepInterruptionLive(unittest.TestCase):
         cls.tmp.cleanup()
 
     counter: Path = Path()
+    _fake_env: object = None
 
     def setUp(self) -> None:
+        # Изоляция REQ-017: свежий бюджет повторов на каждый тест, без сброса в проде.
+        self.httpd.resilience = server._Resilience()
         self.counter = Path(self.tmp.name) / f"counter-{self.id()}"
-        os.environ["FAKE_OC_COUNTER"] = str(self.counter)
-        os.environ["FAKE_OC_PLAN"] = PLAN
-        os.environ["FAKE_OC_PREAMBLE"] = PREAMBLE
-        os.environ["FAKE_OC_STATUS"] = STATUS_ONLY
-        os.environ["FAKE_OC_CALLS"] = CALLS
-        os.environ["FAKE_OC_SWALLOW"] = SWALLOWED_TEXT
+        # RW-032: все FAKE_OC_* изолированы patch.dict — предустановленные значения восстановятся.
+        self._fake_env = mock.patch.dict(
+            os.environ,
+            {
+                "FAKE_OC_COUNTER": str(self.counter),
+                "FAKE_OC_PLAN": PLAN,
+                "FAKE_OC_PREAMBLE": PREAMBLE,
+                "FAKE_OC_STATUS": STATUS_ONLY,
+                "FAKE_OC_CALLS": CALLS,
+                "FAKE_OC_SWALLOW": SWALLOWED_TEXT,
+            },
+            clear=False,
+        )
+        _ = cast(_EnvPatcher, self._fake_env).start()
 
     def tearDown(self) -> None:
-        for name in ("FAKE_OC_COUNTER", "FAKE_OC_MODE", "FAKE_OC_PLAN", "FAKE_OC_PREAMBLE",
-                     "FAKE_OC_STATUS", "FAKE_OC_CALLS", "FAKE_OC_SWALLOW", "FAKE_OC_RAW"):
-            os.environ.pop(name, None)
+        _ = cast(_EnvPatcher, self._fake_env).stop()
 
     def _post(self, stream: bool, model: str = "muse-spark-1.3-contributor-free",
               messages: list[dict[str, Any]] | None = None) -> bytes:
@@ -402,19 +432,51 @@ class TestStepInterruptionLive(unittest.TestCase):
     # --- Бюджеты повторов раздельные -----------------------------------------------------
 
     def test_unmapped_retries_do_not_exhaust_incomplete_budget_stream(self) -> None:
+        """REQ-017/MAX_TOTAL_SPAWNS=3: unmapped-повторы не исчерпывают бюджет шага (итого 3 запуска)."""
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
+        """REQ-017/MAX_TOTAL_SPAWNS=3: unmapped-повторы не исчерпывают бюджет шага (итого 3 запуска)."""
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
index 0000000..1cbc5c9
--- /dev/null
+++ b/bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py
@@ -0,0 +1,2140 @@
+#!/usr/bin/env python3
+"""Реалтайм-размышление serve-транспорта и watchdog legacy-пути (REQ-001..REQ-020)."""
+
+from __future__ import annotations
+
+import ast
+import hashlib
+import http.client
+import json
+import os
+import signal
+import shutil
+import socket
+import struct
+import subprocess
+import sys
+import tempfile
+import threading
+import time
+import unittest
+from collections.abc import Callable, Mapping
+from pathlib import Path
+from typing import Protocol, cast, override
+from unittest import mock
+
+import server
+from tests._fixtures import install_test_models
+
+_ = install_test_models(server)
+MODEL = "muse-spark-1.3-contributor-free"
+
+
+class _Patcher(Protocol):
+    """Минимальный протокол patch-объекта unittest.mock для тестов."""
+
+    def start(self) -> object:
+        """Запустить patch."""
+        ...
+
+    def stop(self) -> object:
+        """Остановить patch."""
+        ...
+
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
+import base64, json, os, re, socket, struct, sys, threading, time
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
+            if "__native_pause__" in prompt:
+                time.sleep(0.4)
+                emit({"id": "nt1", "type": "session.tool.input.started", "data": {"sessionID": sid, "id": "nc1", "name": "bash"}})
+                emit({"id": "nt2", "type": "session.tool.called", "data": {"sessionID": sid, "id": "nc1", "name": "bash", "input": {"command": "pwd"}}})
+                time.sleep(0.4)
+                emit({"id": "nt3", "type": "session.execution.succeeded", "data": {"sessionID": sid}}); return
+            if "__never_event__" in prompt:
+                time.sleep(10); return
+            emit({"id": "e1", "type": "session.execution.started", "data": {"sessionID": sid}})
+            if "__silent__" in prompt:
+                time.sleep(10); return
+            if "__stall__" in prompt:
+                emit({"id": "es", "type": "session.reasoning.delta", "data": {"sessionID": sid, "assistantMessageID": "m1", "delta": "Первая мысль"}})
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
+            sent_times = []
+            for i in range(5):
+                sent_times.append(time.monotonic())
+                emit({"id": f"er{i}", "type": "session.reasoning.delta", "data": {"sessionID": sid, "assistantMessageID": "m1", "delta": f"Мысль{i} "}}); time.sleep(0.12)
+            emit({"id": "et", "type": "session.text.delta", "data": {"sessionID": sid, "assistantMessageID": "m1", "delta": "Ответ\n"}})
+            emit({"id": "e9", "type": "session.step.ended", "data": {"sessionID": sid, "assistantMessageID": "m1", "tokens": {"input": 17, "output": 9, "reasoning": 4, "cache": {"read": 3, "write": 2}}}})
+            if "__end_record:" in prompt:
+                end_record = prompt.split("__end_record:", 1)[1].split("__", 1)[0]
+                with open(end_record, "w") as fh: fh.write(str(time.monotonic()))
+                with open(end_record + ".sent", "w") as fh: json.dump(sent_times, fh)
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
+            prompt_text = str(body.get("text") or "")
+            if "__prompt_reset__" in prompt_text or "__prompt_hang401__" in prompt_text:
+                self.send_response(401 if "hang401" in prompt_text else 200)
+                self.send_header("Content-Length", "100"); self.end_headers(); self.wfile.flush()
+                if "hang401" in prompt_text:
+                    time.sleep(5); return
+                time.sleep(0.1)
+                self.connection.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
+                self.connection.close(); return
+            forced = re.search(r"__prompt_status_(\d+)__", prompt_text)
+            if forced:
+                self.send_json(int(forced.group(1)), {"error": "forced"}); return
+            state["prompt"] = prompt_text
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
+    path.write_text(body, "utf-8")  # pyright: ignore[reportUnusedCallResult] — причина: результат вызова в тесте не используется
+    _ = path.chmod(0o755)
+    return path
+
+
+class _Bridge:
+    """Живой мост на эфемерном порту с сохранением глобалок."""
+
+    def __init__(self) -> None:
+        self.tmp: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
+        self.saved_bin: str = server.OPENCODE_BIN
+        self.saved_key: str = server.AUTH_KEY
+        self.stream_started: float = 0.0
+        self.saved_log: Path = server.LOG_PATH
+        server.AUTH_KEY = "test-key"
+        server.LOG_PATH = Path(self.tmp.name) / "bridge.log"
+        self.httpd: server.Server = server.Server(("127.0.0.1", 0), server.Handler)
+        self.port: int = int(self.httpd.server_address[1])
+        self.thread: threading.Thread = threading.Thread(
+            target=self.httpd.serve_forever, daemon=True
+        )
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
+    def post_json(
+        self, prompt: str, timeout: float = 20.0, with_tools: bool = True
+    ) -> tuple[int, dict[str, object]]:
+        """POST без stream: код и тело ответа (RemoteDisconnected — если мост ничего не отправил)."""
+        payload: dict[str, object] = {
+            "model": MODEL,
+            "messages": [{"role": "user", "content": prompt}],
+        }
+        if with_tools:
+            payload["tools"] = [
+                {
+                    "type": "function",
+                    "function": {
+                        "name": "bash",
+                        "description": "x",
+                        "parameters": {
+                            "type": "object",
+                            "properties": {"command": {"type": "string"}},
+                            "required": ["command"],
+                        },
+                    },
+                }
+            ]
+        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=timeout)
+        try:
+            conn.request(
+                "POST",
+                "/v1/chat/completions",
+                json.dumps(payload).encode(),
+                {
+                    "Authorization": f"Bearer {server.AUTH_KEY}",
+                    "Content-Type": "application/json",
+                },
+            )
+            resp = conn.getresponse()
+            parsed: object = json.loads(resp.read())  # pyright: ignore[reportAny] — причина: тело ответа моста — динамический JSON
+            return resp.status, _as_obj_dict(parsed)
+        finally:
+            conn.close()
+
+    def post_stream_timed(
+        self,
+        prompt: str,
+        timeout: float = 20.0,
+        tool_choice: object = None,
+        effort: str | None = None,
+    ) -> tuple[list[tuple[float, dict[str, object]]], float]:
+        """POST stream с метками времени каждого SSE-чанка."""
+        payload: dict[str, object] = {
+            "model": MODEL,
+            "stream": True,
+            "messages": [{"role": "user", "content": prompt}],
+            "tools": [
+                {
+                    "type": "function",
+                    "function": {
+                        "name": "bash",
+                        "description": "x",
+                        "parameters": {
+                            "type": "object",
+                            "properties": {
+                                "command": {"type": "string"},
+                                "description": {"type": "string"},
+                            },
+                            "required": ["command"],
+                        },
+                    },
+                }
+            ],
+        }
+        if tool_choice is not None:
+            payload["tool_choice"] = tool_choice
+        if effort is not None:
+            payload["reasoning_effort"] = effort
+        body = json.dumps(payload).encode()
+        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=timeout)
+        started = time.monotonic()
+        self.stream_started = started
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
+            raw_data: object = (
+                resp.read1() if hasattr(resp, "read1") else resp.read(4096)
+            )
+            data: bytes = raw_data if isinstance(raw_data, bytes) else b""  # pyright: ignore[reportUnnecessaryIsInstance] — причина: typeshed уже выводит bytes для read1/read; проверка сохраняет защиту адаптера
+            if not data:
+                end = time.monotonic()
+                break
+            buf += data  # pyright: ignore[reportUnknownVariableType] — причина: буфер SSE пополняется байтами динамического read1/read после проверки bytes
+            while b"\n\n" in buf:
+                raw, buf = buf.split(b"\n\n", 1)  # pyright: ignore[reportUnknownMemberType,reportUnknownVariableType] — причина: split делит накопленные байты SSE на кадр и хвост, тип буфера потерян в typeshed
+                for line in raw.decode("utf-8", "replace").splitlines():  # pyright: ignore[reportUnknownMemberType,reportUnknownVariableType] — причина: байтовый кадр SSE декодируется в строки, тип raw наследуется от динамического буфера
+                    if line.startswith("data: {"):  # pyright: ignore[reportUnknownMemberType] — причина: line — строка из decode/splitlines динамического SSE-буфера
+                        parsed_obj: object = json.loads(line[6:])  # pyright: ignore[reportAny,reportUnknownArgumentType] — причина: json.loads возвращает динамический объект, далее он проверяется как dict
+                        parsed_chunk: dict[str, object] = (  # pyright: ignore[reportUnknownVariableType] — причина: ответ моста — динамический JSON, тип сужается проверкой isinstance
+                            parsed_obj if isinstance(parsed_obj, dict) else {}
+                        )
+                        chunks.append((time.monotonic() - started, parsed_chunk))
+        conn.close()
+        return chunks, end - started
+
+
+def _as_obj_dict(value: object) -> dict[str, object]:
+    """Объект как словарь с строковыми ключами, иначе пустой."""
+    if isinstance(value, dict):
+        return {str(k): v for k, v in value.items()}  # pyright: ignore[reportUnknownArgumentType,reportUnknownVariableType] — причина: ответ моста — динамический JSON, тип сужается проверкой isinstance
+    return {}
+
+
+def _deltas(
+    chunks: list[tuple[float, dict[str, object]]], key: str
+) -> list[tuple[float, str]]:
+    """Дельты одного поля с метками."""
+    out: list[tuple[float, str]] = []
+    for at, chunk in chunks:
+        choices_obj: object = chunk.get("choices")
+        if not isinstance(choices_obj, list) or not choices_obj:
+            continue
+        first: dict[str, object] = _as_obj_dict(cast(list[object], choices_obj)[0])
+        delta: dict[str, object] = _as_obj_dict(first.get("delta"))
+        value_obj: object = delta.get(key)
+        if isinstance(value_obj, str):
+            out.append((at, value_obj))
+    return out
+
+
+def _tool_names(chunks: list[tuple[float, dict[str, object]]]) -> list[str]:
+    """Имена tool_calls из SSE-чанков."""
+    names: list[str] = []
+    for _at, chunk in chunks:
+        choices_obj: object = chunk.get("choices")
+        if not isinstance(choices_obj, list) or not choices_obj:
+            continue
+        first: dict[str, object] = _as_obj_dict(cast(list[object], choices_obj)[0])
+        delta: dict[str, object] = _as_obj_dict(first.get("delta"))
+        calls_obj: object = delta.get("tool_calls")
+        if not isinstance(calls_obj, list):
+            continue
+        for tc_obj in cast(list[object], calls_obj):
+            fn: dict[str, object] = _as_obj_dict(_as_obj_dict(tc_obj).get("function"))
+            name_obj: object = fn.get("name")
+            if isinstance(name_obj, str):
+                names.append(name_obj)
+    return names
+
+
+class TestLegacyWatchdogAndKillpg(unittest.TestCase):
+    """Группа A: legacy watchdog, статусы, O-EXIT без FakeServe."""
+
+    bridge: _Bridge = cast(_Bridge, None)  # pyright: ignore[reportInvalidCast] — причина: атрибут класса задаётся в setUp до первого обращения
+    tmp: Path = Path()
+    fake: Path = Path()
+    env: object = None
+    allow: object = None
+
+    @override
+    def setUp(self) -> None:
+        self.bridge = _Bridge()
+        self.tmp = Path(self.bridge.tmp.name)
+        self.fake = _write_exe(self.tmp, "opencode-legacy", LEGACY_FAKE)
+        server.OPENCODE_BIN = str(self.fake)
+        self.env = mock.patch.dict(os.environ, {"FAKE_RT_MODE": "fast"}, clear=False)
+        _ = cast(_Patcher, self.env).start()
+        # Белый список standalone пропускает FAKE_RT_MODE дочернему процессу.
+        self.allow = mock.patch.object(
+            server,
+            "_STANDALONE_ENV_ALLOWLIST",
+            (*server._STANDALONE_ENV_ALLOWLIST, "FAKE_RT_MODE"),  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
+        )
+        _ = cast(_Patcher, self.allow).start()
+
+    @override
+    def tearDown(self) -> None:
+        _ = cast(_Patcher, self.allow).stop()
+        _ = cast(_Patcher, self.env).stop()
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
+    def test_initial_status_before_1s_under_startup_gate_contention(self) -> None:
+        """RW-017: TRANSPORT=run и занятый StartupGate — первый статус не позднее 1.0 с."""
+        saved_wait = server.STARTUP_WAIT_S
+        server.STARTUP_WAIT_S = 2.5
+        self.assertTrue(server._STARTUP_LOCK.acquire(timeout=1.0))  # pyright: ignore[reportPrivateUsage] — причина: оракул обращается к приватному API моста
+        try:
+            chunks, _elapsed = self.bridge.post_stream_timed("привет")
+        finally:
+            server._STARTUP_LOCK.release()  # pyright: ignore[reportPrivateUsage] — причина: оракул обращается к приватному API моста
+            server.STARTUP_WAIT_S = saved_wait
+        reasoning = _deltas(chunks, "reasoning_content")
+        statuses = [at for at, t in reasoning if "[мост]" in t]
+        self.assertTrue(statuses, chunks)
+        self.assertLessEqual(statuses[0], 1.0)
+        model = [at for at, t in reasoning if "[мост]" not in t]
+        self.assertTrue(model and statuses[0] < model[0], chunks)
+        self.assertEqual(
+            len([t for _at, t in reasoning if server.STATUS_INITIAL.strip() in t]), 1
+        )
+
+    def test_rw002_initial_status_while_waiting_spawn_limiter(self) -> None:
+        """RW-002: свободный StartupGate и задержанный лимитер не гасят начальный статус."""
+
+        def delayed_acquire(*_args: object, **_kw: object) -> bool:
+            time.sleep(1.2)
+            return True
+
+        with mock.patch.object(
+            self.bridge.httpd.resilience.spawn_limiter,
+            "acquire",
+            side_effect=delayed_acquire,
+        ):
+            chunks, _ = self.bridge.post_stream_timed("привет")
+        statuses = [
+            (at, t)
+            for at, t in _deltas(chunks, "reasoning_content")
+            if server.STATUS_INITIAL.strip() in t
+        ]
+        self.assertEqual(len(statuses), 1, chunks)
+        self.assertLessEqual(statuses[0][0], 1.0)
+
+    def test_c5_rw002_limiter_delay_half_second_still_emits_first_status_under_1s(
+        self,
+    ) -> None:
+        """Cycle 5 RW-002: задержка слота 0.5 с сохраняет абсолютный срок статуса."""
+        os.environ["FAKE_RT_MODE"] = "slow"
+
+        def delayed(*_args: object, **_kw: object) -> bool:
+            time.sleep(0.5)
+            return True
+
+        with mock.patch.object(
+            self.bridge.httpd.resilience.spawn_limiter, "acquire", side_effect=delayed
+        ):
+            chunks, _ = self.bridge.post_stream_timed("жди")
+        initial = [
+            (at, text)
+            for at, text in _deltas(chunks, "reasoning_content")
+            if server.STATUS_INITIAL.strip() in text
+        ]
+        self.assertEqual(len(initial), 1, chunks)
+        self.assertLessEqual(initial[0][0], 1.0)
+
+    def test_c5_rw003_legacy_retry_separator_all_branches_and_thinking_gate(
+        self,
+    ) -> None:
+        """Cycle 5 RW-003: один разделитель трёх recovery-веток только при thinking."""
+        for branch in ("watchdog", "unmapped", "incomplete"):
+            for effort in ("high", "off"):
+                with self.subTest(branch=branch, effort=effort):
+                    counter = self.tmp / (branch + effort)
+                    body = """#!/usr/bin/env python3
+import json, sys, time
+from pathlib import Path
+p = Path(COUNTER)
+n = int(p.read_text()) if p.exists() else 0
+p.write_text(str(n + 1))
+prompt = sys.stdin.read()
+def ev(o): print(json.dumps(o), flush=True)
+if n == 0:
+    ev({"type": "reasoning", "part": {"text": "Первая мысль"}})
+    if BRANCH == "watchdog": time.sleep(3)
+    elif BRANCH == "unmapped":
+        ev({"type": "tool_use", "part": {"tool": "todoread", "state": {"status": "error", "input": {}}}})
+    else: ev({"type": "text", "part": {"text": "Проверяю файлы.<tool_call>{"}})
+else:
+    ev({"type": "text", "part": {"text": "Ответ"}})
+ev({"type": "step_finish", "part": {"tokens": {"input": 1, "output": 1}}})
+""".replace("COUNTER", repr(str(counter))).replace("BRANCH", repr(branch))
+                    server.OPENCODE_BIN = str(
+                        _write_exe(self.tmp, "retry-legacy", body)
+                    )
+                    with (
+                        mock.patch.object(server, "STALL_TIMEOUT_S", 0.3),
+                        mock.patch.object(server, "FAIL_RETRY_BACKOFF_S", 0.0),
+                    ):
+                        chunks, _ = self.bridge.post_stream_timed(
+                            "проверь файлы", effort=effort
+                        )
+                    output = "".join(
+                        text for _, text in _deltas(chunks, "reasoning_content")
+                    )
+                    self.assertEqual(counter.read_text(), "2", chunks)
+                    self.assertEqual(
+                        output.count("[мост] Повтор попытки"),
+                        1 if effort == "high" else 0,
+                        chunks,
+                    )
+
+    def test_reasoning_content_excluded_from_prompt(self) -> None:
+        """AC-007: reasoning истории не попадает в промпт."""
+        fn = server._messages_to_prompt  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
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
+        _ = self.bridge.post_stream_timed("привет")
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
+        old: float = server.FIRST_EVENT_TIMEOUT_S
+        old_tok: float = server.FIRST_TOKEN_TIMEOUT_S
+        try:
+            server.FIRST_EVENT_TIMEOUT_S = 1.0
+            server.FIRST_TOKEN_TIMEOUT_S = 2.0
+            started = time.monotonic()
+            chunks, _elapsed = self.bridge.post_stream_timed("тишина", timeout=30.0)
+            elapsed = time.monotonic() - started
+        finally:
+            server.FIRST_EVENT_TIMEOUT_S = old
+            server.FIRST_TOKEN_TIMEOUT_S = old_tok
+        self.assertLess(elapsed, 25.0)
+        has_error = any("error" in chunk for _at, chunk in chunks)
+        self.assertTrue(has_error, chunks)
+
+
+class TestServeTransportAndFakeServe(unittest.TestCase):
+    """Группа B: serve-транспорт на FakeServe."""
+
+    bridge: _Bridge = cast(_Bridge, None)  # pyright: ignore[reportInvalidCast] — причина: атрибут класса задаётся в setUp до первого обращения
+    tmp: Path = Path()
+    fake: Path = Path()
+    cfg: Path = Path()
+    saved_cfg: Path = Path()
+    saved_lease: Path = Path()
+    env: object = None
+
+    @override
+    def setUp(self) -> None:
+        self.bridge = _Bridge()
+        self.tmp = Path(self.bridge.tmp.name)
+        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
+        server.OPENCODE_BIN = str(self.fake)
+        self.cfg = self.tmp / "dynamic_config.json"
+        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
+        self.saved_cfg = server.DYNAMIC_CONFIG_PATH
+        server.DYNAMIC_CONFIG_PATH = self.cfg
+        self.saved_lease = server.LEASE_DIR
+        server.LEASE_DIR = self.tmp / "leases"
+        self.env = mock.patch.dict(
+            os.environ,
+            {
+                "OPENCODE_ZEN_BRIDGE_TRANSPORT": "serve",
+                "HOME": str(self.tmp / "empty-home"),
+            },
+            clear=False,
+        )
+        _ = cast(_Patcher, self.env).start()
+        (self.tmp / "empty-home").mkdir(exist_ok=True)
+
+    @override
+    def tearDown(self) -> None:
+        _ = cast(_Patcher, self.env).stop()
+        server.DYNAMIC_CONFIG_PATH = self.saved_cfg
+        server.LEASE_DIR = self.saved_lease
+        self.bridge.close()
+
+    def test_ac026_realtime_chunks_before_upstream_end(self) -> None:
+        """AC-026: reasoning-чанки приходят, пока апстрим ещё идёт."""
+        end_record = self.tmp / "upstream-ended"
+        chunks, _elapsed = self.bridge.post_stream_timed(
+            f"обычный запрос __end_record:{end_record}__"
+        )
+        reasoning = _deltas(chunks, "reasoning_content")
+        model_reasoning = [
+            (at, t) for at, t in reasoning if not t.lstrip("\n").startswith("[мост]")
+        ]
+        self.assertGreaterEqual(len(model_reasoning), 5, chunks)
+        sent_raw = cast(object, json.loads(Path(str(end_record) + ".sent").read_text()))
+        sent_times = [float(t) for t in cast(list[float], sent_raw)]
+        recv_times = [self.bridge.stream_started + at for at, _t in model_reasoning]
+        self.assertEqual(len(sent_times), len(recv_times))
+        for sent_t, recv_t in zip(sent_times, recv_times):
+            self.assertGreaterEqual(recv_t - sent_t, 0.0)
+            self.assertLess(recv_t - sent_t, 0.25)
+        r_times = [at for at, _t in model_reasoning]
+        c_times = [at for at, t in _deltas(chunks, "content") if t]
+        self.assertTrue(c_times, chunks)
+        self.assertLess(r_times[0], c_times[0])
+        self.assertGreaterEqual(r_times[-1] - r_times[0], 0.15)
+        self.assertLess(max(b - a for a, b in zip(r_times, r_times[1:])), 0.5)
+        first_reasoning_t = model_reasoning[0][0]
+        upstream_end_t = float(end_record.read_text()) - self.bridge.stream_started
+        self.assertLess(first_reasoning_t, upstream_end_t)
+        self.assertLess(model_reasoning[-1][0] - model_reasoning[0][0], 2.0)
+        joined = "".join(t for _at, t in model_reasoning)
+        self.assertEqual(joined, "Мысль0 Мысль1 Мысль2 Мысль3 Мысль4 ")
+
+    def test_dynamic_config_switch_same_server(self) -> None:
+        """Тот же Server: false -> run, true -> serve, битый JSON -> false."""
+        reader = server._read_dynamic_config_enabled  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
+        self.assertTrue(reader())
+        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": False}), "utf-8")
+        self.assertFalse(reader())
+        _ = self.cfg.write_text("{broken", "utf-8")
+        self.assertFalse(reader())
+        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": "yes"}), "utf-8")
+        self.assertFalse(reader())
+        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
+        self.assertTrue(reader())
+
+    def test_serve_env_sanitized_all_branches(self) -> None:
+        """_serve_env: :memory:, allowlist, без OPENCODE_BIN и секретов."""
+        with mock.patch.dict(
+            os.environ, {"SECRET_SENTINEL": "x", "MY_API_KEY": "y"}, clear=False
+        ):
+            env: dict[str, str] = server._serve_env(MODEL)  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
+        try:
+            self.assertEqual(env.get("OPENCODE_DB"), ":memory:")
+            self.assertNotIn("OPENCODE_BIN", env)
+            self.assertNotIn("SECRET_SENTINEL", env)
+            self.assertNotIn("MY_API_KEY", env)
+            self.assertTrue(env.get("OPENCODE_SERVER_PASSWORD"))
+            self.assertTrue(env.get("XDG_STATE_HOME"))
+            self.assertNotEqual(env.get("XDG_DATA_HOME"), env.get("XDG_STATE_HOME"))
+        finally:
+            shutil.rmtree(env["XDG_STATE_HOME"], ignore_errors=True)
+
+    def test_canonical_frozen_fixtures(self) -> None:
+        """Каноническое отображение замороженных wire-фикстур v2.1.2."""
+        mapper = server._map_serve_event  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
+        wire: dict[str, object] = {
+            "id": "evt1",
+            "type": "session.reasoning.delta",
+            "data": {
+                "sessionID": "ses_fixture_1",
+                "assistantMessageID": "msg1",
+                "delta": "Мысль без LF",
+            },
+        }
+        result = mapper(wire)
+        self.assertIsNotNone(result)
+        assert result is not None
+        etype, payload = result[0], result[1]
+        self.assertEqual(etype, "reasoning")
+        self.assertEqual(
+            payload, {"reasoning_content": "Мысль без LF", "sessionID": "ses_fixture_1"}
+        )
+        wire2: dict[str, object] = {
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
+        result2 = mapper(wire2)
+        self.assertIsNotNone(result2)
+        assert result2 is not None
+        etype2, payload2 = result2[0], result2[1]
+        self.assertEqual(etype2, "step_finish")
+        self.assertEqual(
+            payload2,
+            {
+                "input": 17,
+                "output": 9,
+                "cached": 3,
+                "reasoning": 4,
+                "sessionID": "ses_fixture_1",
+            },
+        )
+
+    def test_tool_text_split_across_deltas(self) -> None:
+        """ToolCallParser на разрезанных дельтах serve."""
+        chunks, _elapsed = self.bridge.post_stream_timed("__tool_text__ вызов")
+        self.assertEqual(_tool_names(chunks), ["bash"])
+
+    def test_native_tool_and_permission_reject(self) -> None:
+        """permission.asked -> reject, native tool -> DSH tool_call."""
+        chunks, _elapsed = self.bridge.post_stream_timed("__native_tool__ сделай")
+        self.assertIn("bash", _tool_names(chunks))
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
+        fn = server._run_serve_helper_cli  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
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
+        health = server._ServeHealth()  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
+        for _i in range(3):
+            health.record_failure()
+        self.assertTrue(health.is_degraded())
+        health.record_success()
+        self.assertFalse(health.is_degraded())
+        rows: list[dict[str, object]] = list(server.FALLBACK_DECISION_TABLE)
+        self.assertGreaterEqual(len(rows), 10)
+        by_event: dict[str, dict[str, object]] = {
+            str(r.get("event", "")): r for r in rows
+        }
+        silence_rows = [
+            r
+            for ev, r in by_event.items()
+            if "first_token_timeout" in ev and "silence" in ev
+        ]
+        self.assertEqual(len(silence_rows), 1)
+        self.assertEqual(silence_rows[0].get("action"), "serve_retry")
+        self.assertEqual(silence_rows[0].get("UpstreamBreaker_failure_increment"), 1)
+        auth_rows = [r for ev, r in by_event.items() if "HTTP401/403" in ev]
+        self.assertEqual(len(auth_rows), 1)
+        self.assertEqual(auth_rows[0].get("action"), "fail_closed")
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
+                    (*server._SERVE_ALLOWLIST, "FAKE_SERVE_SESSION_STATUS"),  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
+                ),
+                mock.patch.object(
+                    server,
+                    "_STANDALONE_ENV_ALLOWLIST",
+                    (
+                        *server._STANDALONE_ENV_ALLOWLIST,  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
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
+                _ = server._spawn_serve("att_foreign", server._serve_env(MODEL))  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
+        self.assertIn("foreign listener", str(ctx.exception))
+        lease_dir = self.tmp / "reaper-leases"
+        lease_dir.mkdir()
+        dead = lease_dir / "lease-dead.json"
+        alive = lease_dir / "lease-alive.json"
+        _ = dead.write_text(
+            json.dumps(
+                {
+                    "parent_pid": 999999,
+                    "helper_pid": 0,
+                    "pgid": 0,
+                    "owner_uid": os.getuid(),
+                }
+            ),
+            "utf-8",
+        )
+        _ = alive.write_text(
+            json.dumps(
+                {
+                    "parent_pid": os.getpid(),
+                    "helper_pid": 0,
+                    "pgid": 0,
+                    "owner_uid": os.getuid(),
+                }
+            ),
+            "utf-8",
+        )
+        _ = server._startup_reaper(lease_dir)  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
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
+                (*server._SERVE_ALLOWLIST, "FAKE_SERVE_SESSION_STATUS"),  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
+            ),
+            mock.patch.object(
+                server,
+                "_STANDALONE_ENV_ALLOWLIST",
+                (*server._STANDALONE_ENV_ALLOWLIST, "FAKE_SERVE_SESSION_STATUS"),  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
+            ),
+        ):
+            chunks, _elapsed = self.bridge.post_stream_timed("обычный запрос")
+        joined = json.dumps(chunks, ensure_ascii=False)
+        self.assertIn("serve security failure", joined)
+        self.assertEqual(health.failures, failures_before)
+        self.assertFalse(health.is_degraded())
+
+    def _auto_mode(self) -> None:
+        """auto + eligible: serve выбирается для скриптового FakeServe."""
+        saved = server.SERVE_TEST_ELIGIBLE
+        server.SERVE_TEST_ELIGIBLE = True
+        self.addCleanup(setattr, server, "SERVE_TEST_ELIGIBLE", saved)
+        # Окружение восстановит patch.dict из setUp: отдельный patch в cleanup вернул бы его устаревший снимок.
+        os.environ["OPENCODE_ZEN_BRIDGE_TRANSPORT"] = "auto"
+
+    def _patched_attempts(
+        self, plan: list[Callable[[tuple[object, ...]], dict[str, object]]]
+    ) -> tuple[list[tuple[object, ...]], mock._patch[mock.MagicMock]]:  # pyright: ignore[reportPrivateUsage] — причина: тип patch-объекта mock приватен в typeshed
+        """Подмена `_serve_one_attempt` сценарием по очереди; возвращает журнал аргументов."""
+        calls: list[tuple[object, ...]] = []
+        queue_plan = list(plan)
+
+        def fake(*args: object, **_kw: object) -> dict[str, object]:
+            calls.append(args)
+            return queue_plan.pop(0)(args)
+
+        return calls, mock.patch.object(server, "_serve_one_attempt", side_effect=fake)
+
+    def test_slow_pause_streams_all_deltas_and_single_initial_status(self) -> None:
+        """RW-008/RW-016: пауза SSE 1.4 с не рвёт поток; STATUS_INITIAL ровно один, чанки целы."""
+        chunks, _elapsed = self.bridge.post_stream_timed("__slow__ жди")
+        self.assertFalse(any("error" in chunk for _at, chunk in chunks), chunks)
+        content = "".join(t for _at, t in _deltas(chunks, "content"))
+        self.assertEqual(content, "Ответ\n")
+        initial = [
+            at
+            for at, t in _deltas(chunks, "reasoning_content")
+            if server.STATUS_INITIAL.strip() in t
+        ]
+        self.assertEqual(len(initial), 1, chunks)
+        self.assertLessEqual(initial[0], 1.0)
+
+    def test_prompt_http_4xx_fail_closed_without_run_fallback(self) -> None:
+        """RW-003: 400/404/422 prompt в auto — fail_closed: без run и без инкремента serve_health."""
+        self._auto_mode()
+        health = self.bridge.httpd.resilience.serve_health
+        for code in (400, 404, 422):
+            with self.subTest(code=code):
+                before = health.failures
+                chunks, _elapsed = self.bridge.post_stream_timed(
+                    f"__prompt_status_{code}__ запрос"
+                )
+                joined = json.dumps(chunks, ensure_ascii=False)
+                self.assertIn("serve security failure", joined)
+                self.assertNotIn("Поздний ответ", joined)
+                self.assertEqual(health.failures, before)
+
+    def test_timeout_and_client_gone_never_count_as_success(self) -> None:
+        """RW-002: exit_reason timeout/client_gone — не успех ни в SSE, ни в JSON."""
+        health = self.bridge.httpd.resilience.serve_health
+        for reason in ("timeout", "client_gone"):
+            for streaming in (True, False):
+                with (
+                    self.subTest(reason=reason, stream=streaming),
+                    mock.patch.object(health, "record_success") as ok,
+                    mock.patch.object(server, "FAIL_RETRY_BACKOFF_S", 0.0),
+                    mock.patch.object(
+                        server,
+                        "_serve_one_attempt",
+                        side_effect=lambda *_a, **_k: _fake_result(  # pyright: ignore[reportUnknownLambdaType] — причина: подмена попытки возвращает заготовленный результат
+                            exit_reason=reason, delivered=True
+                        ),
+                    ),
+                ):
+                    if streaming:
+                        chunks, _elapsed = self.bridge.post_stream_timed("x")
+                        finishes = [
+                            _as_obj_dict(
+                                cast(list[object], c.get("choices") or [{}])[0]
+                            ).get("finish_reason")
+                            for _at, c in chunks
+                            if c.get("choices")
+                        ]
+                        self.assertFalse(any(finishes), chunks)
+                        self.assertEqual(
+                            any("error" in c for _at, c in chunks), reason == "timeout"
+                        )
+                    elif reason == "timeout":
+                        status, _body = self.bridge.post_json("x")
+                        self.assertEqual(status, 502)
+                    else:
+                        with self.assertRaises(
+                            (
+                                TimeoutError,
+                                http.client.RemoteDisconnected,
+                                ConnectionError,
+                            )
+                        ):
+                            _ = self.bridge.post_json("x", timeout=2.5)
+                    ok.assert_not_called()
+
+    def test_retry_separator_once_and_delivery_barrier_is_monotonic(self) -> None:
+        """RW-009/RW-012: один разделитель на повтор; после reasoning нет тихого fallback на run."""
+        self._auto_mode()
+
+        def first(args: tuple[object, ...]) -> dict[str, object]:
+            _callback(args, 4)("мысль\n")
+            return _fake_result(
+                exit_reason="stall_timeout", delivered=True, reasonings=["мысль\n"]
+            )
+
+        def second(_args: tuple[object, ...]) -> dict[str, object]:
+            return _fake_result(exit_reason="first_event_timeout", delivered=False)
+
+        def third(args: tuple[object, ...]) -> dict[str, object]:
+            _callback(args, 5)("Готово")
+            return _fake_result(texts=["Готово"], terminal="succeeded")
+
+        calls, patcher = self._patched_attempts([first, second, third])
+        with patcher, mock.patch.object(server, "FAIL_RETRY_BACKOFF_S", 0.0):
+            chunks, _elapsed = self.bridge.post_stream_timed("x")
+        self.assertEqual(len(calls), 3)
+        joined = "".join(t for _at, t in _deltas(chunks, "content"))
+        self.assertEqual(joined, "Готово")
+        separators = [
+            t
+            for _at, t in _deltas(chunks, "reasoning_content")
+            if "Повтор попытки" in t
+        ]
+        self.assertEqual(len(separators), 2, chunks)
+
+    def test_json_tool_calls_are_deduplicated(self) -> None:
+        """RW-013: одинаковый (name, arguments) из native и из текста даёт один tool_call."""
+        call_text = '<tool_invoke>{"name": "bash", "arguments": {"command": "echo hi"}}</tool_invoke>'
+        native: dict[str, object] = {
+            "part": {
+                "tool": "bash",
+                "state": {"input": {"command": "echo hi"}, "status": "completed"},
+            }
+        }
+
+        def attempt(args: tuple[object, ...]) -> dict[str, object]:
+            _callback(args, 5)(call_text)
+            on_tool = cast(Callable[[dict[str, object]], None], args[6])
+            on_tool(native)
+            on_tool(native)
+            return _fake_result(terminal="succeeded")
+
+        _calls, patcher = self._patched_attempts([attempt])
+        with patcher:
+            status, body = self.bridge.post_json("x")
+        self.assertEqual(status, 200)
+        message = _as_obj_dict(
+            _as_obj_dict(cast(list[object], body["choices"])[0]).get("message")
+        )
+        self.assertEqual(len(cast(list[object], message["tool_calls"])), 1)
+
+    def test_json_run_fallback_respects_total_spawn_cap(self) -> None:
+        """RW-010: исчерпанный потолок спавнов serve не даёт четвёртый спавн run в JSON."""
+
+        def fake_serve(*args: object) -> bool:
+            attempts = cast("server._RequestAttempts", args[9])  # pyright: ignore[reportPrivateUsage] — причина: оракул обращается к приватному API моста
+            for _i in range(server.MAX_TOTAL_SPAWNS):
+                attempts.note_spawn()
+            return False
+
+        with (
+            mock.patch.object(
+                server.Handler,
+                "_serve_json_serve",
+                autospec=True,
+                side_effect=fake_serve,
+            ),
+            mock.patch.object(server, "Run") as run_cls,
+        ):
+            status, _body = self.bridge.post_json("x")
+        self.assertEqual(status, 502)
+        run_cls.assert_not_called()
+
+    def test_proxy_pool_advances_once_per_serve_attempt(self) -> None:
+        """RW-019: запрос с одной попыткой serve сдвигает пул прокси один раз."""
+        with (
+            mock.patch.object(
+                server, "_next_standalone_proxy", return_value=None
+            ) as rotate,
+            mock.patch.object(
+                server, "_spawn_serve", side_effect=server.ServeUnavailable("stop")
+            ),
+        ):
+            _chunks, _elapsed = self.bridge.post_stream_timed("x")
+        self.assertEqual(rotate.call_count, 1)
+
+    def test_tool_choice_preserved_in_step_recovery_prompt(self) -> None:
+        """RW-007: tool_choice попадает в промпт step-interruption recovery serve."""
+        for choice, phrase in (
+            ("required", "MUST call at least one tool"),
+            (
+                {"type": "function", "function": {"name": "bash"}},
+                'MUST call the tool "bash"',
+            ),
+        ):
+            with self.subTest(choice=choice):
+
+                def preamble(args: tuple[object, ...]) -> dict[str, object]:
+                    _callback(args, 5)("Сейчас проверю.")
+                    return _fake_result(texts=["Сейчас проверю."], terminal="succeeded")
+
+                def done(args: tuple[object, ...]) -> dict[str, object]:
+                    call = '<tool_invoke>{"name": "bash", "arguments": {"command": "ls"}}</tool_invoke>'
+                    _callback(args, 5)(call)
+                    return _fake_result(texts=[call], terminal="succeeded")
+
+                calls, patcher = self._patched_attempts([preamble, done])
+                with patcher, mock.patch.object(server, "FAIL_RETRY_BACKOFF_S", 0.0):
+                    _chunks, _elapsed = self.bridge.post_stream_timed(
+                        "x", tool_choice=choice
+                    )
+                self.assertEqual(len(calls), 2)
+                self.assertIn(phrase, str(calls[1][1]))
+
+    def test_fu003_usage_once_across_distinct_retry_branches(self) -> None:
+        """FU-003: timeout, prompt-status и успешная попытка учитываются по одному разу."""
+
+        def first(args: tuple[object, ...]) -> dict[str, object]:
+            _callback(args, 4)("мысль\n")
+            return _fake_result(
+                delivered=True,
+                reasonings=["мысль\n"],
+                exit_reason="stall_timeout",
+                usage={"output": 3},
+            )
+
+        def second(_args: tuple[object, ...]) -> dict[str, object]:
+            return _fake_result(delivered=True, prompt_status=429, usage={"output": 5})
+
+        def third(args: tuple[object, ...]) -> dict[str, object]:
+            _callback(args, 5)("Ответ.")
+            return _fake_result(
+                texts=["Ответ."], terminal="succeeded", usage={"output": 7}
+            )
+
+        calls, patcher = self._patched_attempts([first, second, third])
+        with (
+            patcher,
+            mock.patch.object(server, "FAIL_RETRY_BACKOFF_S", 0.0),
+            mock.patch.object(server, "STEP_RECOVERY_ENABLED", False),
+        ):
+            chunks, _ = self.bridge.post_stream_timed("x")
+        self.assertEqual(len(calls), 3)
+        usages = [
+            _as_obj_dict(chunk["usage"]) for _, chunk in chunks if "usage" in chunk
+        ]
+        self.assertTrue(usages, chunks)
+        self.assertEqual(usages[-1].get("completion_tokens"), 15)
+
+    def test_fu010_thinking_off_omits_retry_separator(self) -> None:
+        """FU-010: синтетический разделитель отключён вместе с thinking."""
+
+        def first(args: tuple[object, ...]) -> dict[str, object]:
+            _callback(args, 5)("начало ")
+            return _fake_result(
+                delivered=True, texts=["начало "], exit_reason="stall_timeout"
+            )
+
+        def second(args: tuple[object, ...]) -> dict[str, object]:
+            _callback(args, 5)("конец")
+            return _fake_result(texts=["конец"], terminal="succeeded")
+
+        _calls, patcher = self._patched_attempts([first, second])
+        with (
+            patcher,
+            mock.patch.object(server, "FAIL_RETRY_BACKOFF_S", 0.0),
+            mock.patch.object(server, "STEP_RECOVERY_ENABLED", False),
+        ):
+            chunks, _ = self.bridge.post_stream_timed("x", effort="off")
+        self.assertNotIn("Повтор попытки", json.dumps(chunks, ensure_ascii=False))
+
+    def test_rw001_delivery_survives_unavailable_or_limiter(self) -> None:
+        """RW-001: частичный ответ запрещает run при следующем отказе serve или лимитера."""
+        self._auto_mode()
+        unavailable = server.ServeUnavailable
+        for stream in (True, False):
+            for limited in (False, True):
+                with self.subTest(stream=stream, limited=limited):
+
+                    def first(args: tuple[object, ...]) -> dict[str, object]:
+                        _callback(args, 4)("частичная мысль\n")
+                        return _fake_result(
+                            exit_reason="stall_timeout",
+                            delivered=True,
+                            reasonings=["частичная мысль\n"],
+                        )
+
+                    def second(_args: tuple[object, ...]) -> dict[str, object]:
+                        raise unavailable("нет serve")
+
+                    calls, patcher = self._patched_attempts([first, second])
+                    health = self.bridge.httpd.resilience.serve_health
+                    limiter = self.bridge.httpd.resilience.spawn_limiter
+                    with (
+                        patcher,
+                        mock.patch.object(server, "FAIL_RETRY_BACKOFF_S", 0.0),
+                        mock.patch.object(health, "record_success") as success,
+                        mock.patch.object(server.Run, "execute") as legacy,
+                        mock.patch.object(server, "_spawn_with_stdin") as spawn,
+                        mock.patch.object(
+                            limiter,
+                            "acquire",
+                            side_effect=[True, False] if limited else [True, True],
+                        ),
+                    ):
+                        if stream:
+                            chunks, _ = self.bridge.post_stream_timed("x")
+                            output = json.dumps(chunks, ensure_ascii=False)
+                            self.assertLessEqual(output.count("Повтор попытки"), 1)
+                            self.assertIn("error", output)
+                        else:
+                            status, body = self.bridge.post_json("x", with_tools=False)
+                            self.assertEqual(status, 502, body)
+                        legacy.assert_not_called()
+                        spawn.assert_not_called()
+                        success.assert_not_called()
+                    self.assertEqual(len(calls), 1 if limited else 2)
+
+    def test_c5_rw001_prompt_headers_then_body_error_or_429_blocks_run_fallback(
+        self,
+    ) -> None:
+        """Cycle 5 RW-001: заголовки prompt запрещают run и успешный учёт."""
+        self._auto_mode()
+        for marker in (
+            "__prompt_reset__",
+            "__prompt_status_429__",
+            "__prompt_status_503__",
+        ):
+            for stream in (True, False):
+                with self.subTest(marker=marker, stream=stream):
+                    self.bridge.httpd.resilience = server._Resilience()  # pyright: ignore[reportPrivateUsage] — причина: каждый сценарий получает независимые бюджеты
+                    with (
+                        mock.patch.object(server.Run, "execute") as legacy,
+                        mock.patch.object(server, "_spawn_with_stdin") as spawn,
+                        mock.patch.object(
+                            self.bridge.httpd.resilience.serve_health, "record_success"
+                        ) as success,
+                        mock.patch.object(server, "FAIL_RETRY_BACKOFF_S", 0.0),
+                        mock.patch.object(server, "MAX_TOTAL_SPAWNS", 2),
+                        mock.patch.object(
+                            self.bridge.httpd.resilience.retry_budget,
+                            "try_acquire_retry",
+                            wraps=self.bridge.httpd.resilience.retry_budget.try_acquire_retry,
+                        ) as retry_budget,
+                    ):
+                        if stream:
+                            chunks, _ = self.bridge.post_stream_timed(marker)
+                            self.assertIn("error", json.dumps(chunks))
+                        else:
+                            status, body = self.bridge.post_json(
+                                marker, with_tools=False
+                            )
+                            self.assertEqual(status, 502, body)
+                        legacy.assert_not_called()
+                        spawn.assert_not_called()
+                        success.assert_not_called()
+                        self.assertEqual(retry_budget.call_count, 1)
+
+    def test_c5_fu003_json_transient_recovery_normalizes_and_deduplicates(self) -> None:
+        """Cycle 5 FU-003: частичный tool-блок не попадает в content и не дублирует преамбулу."""
+        preamble = "Проверяю файлы."
+
+        def first(args: tuple[object, ...]) -> dict[str, object]:
+            text = preamble + '<tool_call>{"name":"bash","arguments":'
+            _callback(args, 5)(text)
+            return _fake_result(
+                texts=[text],
+                delivered=True,
+                error={"message": "overloaded"},
+                transient_error=True,
+                terminal="failed",
+            )
+
+        def second(args: tuple[object, ...]) -> dict[str, object]:
+            text = preamble + " Ответ"
+            _callback(args, 5)(text)
+            return _fake_result(texts=[text], terminal="succeeded")
+
+        _calls, patcher = self._patched_attempts([first, second])
+        with patcher, mock.patch.object(server, "FAIL_RETRY_BACKOFF_S", 0.0):
+            status, body = self.bridge.post_json("проверь файлы")
+        self.assertEqual(status, 200, body)
+        output = json.dumps(body, ensure_ascii=False)
+        self.assertEqual(output.count(preamble), 1, body)
+        self.assertNotIn("<tool_call>", output)
+
+    def test_rw007_split_interrupted_marker_at_every_boundary(self) -> None:
+        """RW-007: маркер удаляется при любом разрезе, включая прежнюю границу буфера."""
+        marker = "I was interrupted right before making tool calls."
+        for split in (1, 19, len(marker) - 1):
+            with self.subTest(split=split):
+
+                def first(args: tuple[object, ...]) -> dict[str, object]:
+                    chunks = [
+                        "начало " + marker[:split],
+                        marker[split:] + " конец" + "x" * 100,
+                    ]
+                    for chunk in chunks:
+                        _callback(args, 5)(chunk)
+                    return _fake_result(texts=chunks, terminal="succeeded")
+
+                _calls, patcher = self._patched_attempts([first])
+                with patcher, mock.patch.object(server, "STEP_RECOVERY_ENABLED", False):
+                    chunks, _ = self.bridge.post_stream_timed("x")
+                text = "".join(t for _, t in _deltas(chunks, "content"))
+                self.assertEqual(text, "начало  конец" + "x" * 100)
+
+    def test_rw008_provider_secrets_hidden_in_sse_json_and_log(self) -> None:
+        """RW-008: ошибка провайдера не выдаёт секреты через SSE, JSON и лог."""
+        secret = "sk-" + "a" * 32
+        message = (
+            secret
+            + " Bearer hidden-token OPENCODE_SERVER_PASSWORD=hidden-pass http://u:proxy-pass@localhost:1080"
+        )
+        for stream in (True, False):
+
+            def failure(_args: tuple[object, ...]) -> dict[str, object]:
+                return _fake_result(error={"message": message}, terminal="failed")
+
+            _calls, patcher = self._patched_attempts([failure])
+            with patcher:
+                if stream:
+                    chunks, _ = self.bridge.post_stream_timed("x")
+                    output = json.dumps(chunks)
+                else:
+                    _status, body = self.bridge.post_json("x", with_tools=False)
+                    output = json.dumps(body)
+            output += server.LOG_PATH.read_text()
+            for sentinel in (secret, "hidden-token", "hidden-pass", "proxy-pass"):
+                self.assertNotIn(sentinel, output)
+
+    def test_rw006_invalid_utf8_falls_back_and_recovers(self) -> None:
+        """RW-006: повреждённый UTF-8 безопасен, восстановление JSON включает serve."""
+        self._auto_mode()
+        _ = self.cfg.write_bytes(b"\xff\xfe")
+        self.assertEqual(server._select_transport(), "run")  # pyright: ignore[reportPrivateUsage] — причина: проверяется выбор транспорта после повреждения файла
+        _ = self.cfg.write_text('{"REALTIME_SERVE_ENABLED": true}', encoding="utf-8")
+        self.assertEqual(server._select_transport(), "serve")  # pyright: ignore[reportPrivateUsage] — причина: проверяется восстановление транспорта без рестарта
+
+    def test_rw003_mkdtemp_failure_is_serve_unavailable(self) -> None:
+        """RW-003: ENOSPC при выделении каталога не оставляет портов и не уходит как client_gone."""
+        ports = server._ACTIVE_SERVE_PORTS.copy()  # pyright: ignore[reportPrivateUsage] — причина: сверяются ресурсы после отказа до запуска
+        attempt = server._serve_one_attempt  # pyright: ignore[reportPrivateUsage] — причина: оракул инъецирует отказ до запуска попытки
+        with mock.patch.object(
+            tempfile, "mkdtemp", side_effect=OSError(28, "нет места")
+        ):
+            with self.assertRaises(server.ServeUnavailable):
+                _ = attempt(
+                    MODEL,
+                    "x",
+                    "high",
+                    self.tmp,
+                    lambda _: None,
+                    lambda _: None,
+                    lambda _: None,
+                    time.monotonic(),
+                )
+        self.assertEqual(server._ACTIVE_SERVE_PORTS, ports)  # pyright: ignore[reportPrivateUsage] — причина: инвариант отсутствия занятых портов после отказа
+
+    def test_fu011_cancelled_never_counts_as_success(self) -> None:
+        """FU-011: отменённая form.created не считается успехом в обоих протоколах."""
+        for stream in (True, False):
+
+            def cancelled(_args: tuple[object, ...]) -> dict[str, object]:
+                return _fake_result(terminal="cancelled")
+
+            _calls, patcher = self._patched_attempts([cancelled])
+            with (
+                patcher,
+                mock.patch.object(
+                    self.bridge.httpd.resilience.serve_health, "record_success"
+                ) as success,
+            ):
+                if stream:
+                    chunks, _ = self.bridge.post_stream_timed("x")
+                    self.assertIn("cancelled", json.dumps(chunks))
+                else:
+                    status, body = self.bridge.post_json("x", with_tools=False)
+                    self.assertEqual(status, 502, body)
+                success.assert_not_called()
+
+
+class TestReworkUnits(unittest.TestCase):
+    """Группа C: детерминированные оракулы RW-001..RW-032 без живого FakeServe."""
+
+    def test_surrogate_pair_and_broken_json(self) -> None:
+        """RW-005: суррогатная пара декодируется, битый JSON serve — ServeProtocolError."""
+        parsed = server._loads_object('{"emoji": "\ud83d\ude00"}')  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
+        self.assertEqual(parsed, {"emoji": "\U0001f600"})
+        self.assertEqual(
+            json.dumps(parsed, ensure_ascii=False).encode("utf-8").decode("utf-8"),
+            '{"emoji": "\U0001f600"}',
+        )
+        self.assertIsNone(server._loads_object("{broken"))  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
+        with self.assertRaises(server.ServeProtocolError):
+            _ = server._loads_serve_object("{broken")  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
+
+    def test_service_events_ignored_and_foreign_session(self) -> None:
+        """RW-029/RW-031: служебные события — None, sessionID сохраняется в payload."""
+        self.assertIsNone(
+            server._map_serve_event({"type": "integration.updated", "data": {}})  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
+        )
+        self.assertIsNone(
+            server._map_serve_event({"type": "server.heartbeat", "data": {}})  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
+        )
+        mapped = server._map_serve_event(  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
+            {"type": "session.text.delta", "data": {"sessionID": "ses_a", "delta": " "}}
+        )
+        self.assertIsNotNone(mapped)
+        assert mapped is not None
+        self.assertEqual(mapped[1].get("sessionID"), "ses_a")
+        self.assertEqual(mapped[1].get("content"), " ")
+
+    def test_whitespace_delta_preserved_in_map(self) -> None:
+        """RW-007: пробельная дельта не отбрасывается маппером."""
+        mapped = server._map_serve_event(  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
+            {
+                "type": "session.reasoning.delta",
+                "data": {"sessionID": "s1", "delta": "\n\n"},
+            }
+        )
+        self.assertIsNotNone(mapped)
+        assert mapped is not None
+        self.assertEqual(mapped[1].get("reasoning_content"), "\n\n")
+
+    def test_half_open_to_closed_via_attempt_done(self) -> None:
+        """RW-014: успешный serve через attempt_done переводит breaker в CLOSED."""
+        res = server._Resilience()  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
+        res.breaker = server._UpstreamBreaker(fail_threshold=1, reset_timeout_s=0.01)  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
+        res.breaker.record_failure()
+        self.assertEqual(res.breaker.state, "OPEN")
+        time.sleep(0.03)
+        self.assertTrue(res.breaker.allow())
+        self.assertEqual(res.breaker.state, "HALF_OPEN")
+        attempts = server._RequestAttempts(res, time.monotonic() + 60.0)  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
+        attempts.attempt_done(False, True)
+        self.assertEqual(res.breaker.state, "CLOSED")
+
+    def test_transport_matrix(self) -> None:
+        """RW-025: TRANSPORT=run, override 0, disable-файл и опечатка дают run."""
+        with mock.patch.dict(
+            os.environ, {"OPENCODE_ZEN_BRIDGE_TRANSPORT": "run"}, clear=False
+        ):
+            self.assertEqual(server._select_transport(), "run")  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
+        with mock.patch.dict(
+            os.environ,
+            {
+                "OPENCODE_ZEN_BRIDGE_TRANSPORT": "serve",
+                "OPENCODE_ZEN_BRIDGE_REALTIME_SERVE_ENABLED": "0",
+            },
+            clear=False,
+        ):
+            self.assertEqual(server._select_transport(), "run")  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
+        with mock.patch.dict(
+            os.environ, {"OPENCODE_ZEN_BRIDGE_TRANSPORT": "serv"}, clear=False
+        ):
+            self.assertEqual(server._select_transport(), "run")  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
+
+    def test_disable_file_overrides_forced_serve(self) -> None:
+        """FU-013: файл отключения важнее принудительного выбора serve."""
+        with tempfile.TemporaryDirectory() as name:
+            disable = Path(name) / "disable-serve"
+            _ = disable.write_text("1")
+            with mock.patch.dict(
+                os.environ,
+                {
+                    "OPENCODE_ZEN_BRIDGE_TRANSPORT": "serve",
+                    "OPENCODE_ZEN_BRIDGE_SERVE_DISABLE_FILE": str(disable),
+                    "OPENCODE_ZEN_BRIDGE_REALTIME_SERVE_ENABLED": "1",
+                },
+            ):
+                self.assertEqual(server._select_transport(), "run")  # pyright: ignore[reportPrivateUsage] — причина: проверяется приоритет аварийного файла отключения
+
+    def test_fake_rt_mode_preset_preserved(self) -> None:
+        """RW-027: предустановленный FAKE_RT_MODE сохраняется после patch.dict."""
+        patcher = mock.patch.dict(
+            os.environ, {"FAKE_RT_MODE": "preset-value"}, clear=False
+        )
+        _ = patcher.start()  # pyright: ignore[reportAny] — причина: динамический результат запуска patch.dict не используется
+        try:
+            inner = mock.patch.dict(os.environ, {"FAKE_RT_MODE": "fast"}, clear=False)
+            _ = inner.start()  # pyright: ignore[reportAny] — причина: mock.patch.start возвращает динамический объект подмены, результат не используется
+            _ = inner.stop()  # pyright: ignore[reportAny] — причина: mock.patch.stop возвращает динамический результат восстановления, он не используется
+            self.assertEqual(os.environ.get("FAKE_RT_MODE"), "preset-value")
+        finally:
+            _ = patcher.stop()  # pyright: ignore[reportAny] — причина: динамический результат восстановления patch.dict не используется
+
+    def test_spawn_cap_and_proxy_rotation_helpers(self) -> None:
+        """RW-001/RW-013: can_spawn ограничен MAX_TOTAL_SPAWNS, пул прокси ротируется."""
+        res = server._Resilience()  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
+        attempts = server._RequestAttempts(res, time.monotonic() + 60.0)  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
+        for _i in range(server.MAX_TOTAL_SPAWNS):
+            self.assertTrue(attempts.can_spawn())
+            attempts.note_spawn()
+        self.assertFalse(attempts.can_spawn())
+        self.assertTrue(callable(server._next_standalone_proxy))  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
+
+    def test_elf_magic_and_tool_status(self) -> None:
+        """FU-001/FU-002: 4 случайных байта не ELF, статус tool из типа события."""
+        state = server._ServeToolState()  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
+        state.feed({"id": "c1", "name": "bash", "text": '{"command": "x"}'})
+        done = state.complete("c1", "session.tool.called")
+        self.assertIsNotNone(done)
+        assert done is not None
+        part_obj: object = done[1].get("part")
+        self.assertIsInstance(part_obj, dict)
+        self.assertEqual(
+            _as_obj_dict(_as_obj_dict(part_obj).get("state")).get("status"), "completed"
+        )
+        with tempfile.TemporaryDirectory() as name:
+            binary = Path(name) / "opencode"
+            with mock.patch.object(server, "SERVE_TEST_ELIGIBLE", False):
+                for magic, expected in (
+                    (b"xxxx", False),
+                    (b"#!/b", False),
+                    (b"\x7fELF", True),
+                    (b"\xcf\xfa\xed\xfe", True),
+                ):
+                    _ = binary.write_bytes(magic)
+                    native = server._is_native_opencode_bin  # pyright: ignore[reportPrivateUsage] — причина: проверяется сигнатура отдельно от тестового допуска
+                    self.assertEqual(native(str(binary)), expected)
+
+    def test_fu001_http_checks_deadline_and_cancellation_before_connect(self) -> None:
+        """FU-001: просроченный бюджет и ушедший клиент запрещают даже соединение HTTP."""
+        call = server._serve_http  # pyright: ignore[reportPrivateUsage] — причина: проверяется граница фазы управляющего HTTP-вызова
+        with self.assertRaises(TimeoutError):
+            _ = call(0, "", "GET", "/", deadline=time.monotonic() - 1)
+        with self.assertRaises(BrokenPipeError):
+            _ = call(0, "", "GET", "/", is_client_gone=lambda: True)
+
+    def test_rw004_native_calls_share_canonical_mapping(self) -> None:
+        """RW-004: bash/read/edit/list/multiedit используют ровно канонический fit_args."""
+        tools: list[dict[str, object]] = [
+            {
+                "type": "function",
+                "function": {
+                    "name": name,
+                    "parameters": {
+                        "type": "object",
+                        "properties": props,
+                        "required": list(props),
+                    },
+                },
+            }
+            for name, props in (
+                (
+                    "bash",
+                    {"command": {"type": "string"}, "description": {"type": "string"}},
+                ),
+                ("read", {"file_path": {"type": "string"}}),
+                (
+                    "edit",
+                    {
+                        "file_path": {"type": "string"},
+                        "old_string": {"type": "string"},
+                        "new_string": {"type": "string"},
+                    },
+                ),
+            )
+        ]
+        mapper = server._native_to_tool_calls  # pyright: ignore[reportPrivateUsage] — причина: канонический преобразователь run служит оракулом адаптера serve
+        canonical = cast(
+            Callable[
+                [object, object, list[dict[str, object]]], list[dict[str, object]]
+            ],
+            mapper,
+        )
+        for name, args in (
+            ("bash", {"command": "pwd"}),
+            ("read", {"filePath": "/tmp/a"}),
+            ("edit", {"filePath": "/tmp/a", "oldString": "a", "newString": "b"}),
+            ("list", {"path": "/tmp"}),
+            (
+                "multiedit",
+                {
+                    "filePath": "/tmp/a",
+                    "edits": [
+                        {"oldString": "a", "newString": "b"},
+                        {"oldString": "c", "newString": "d"},
+                    ],
+                },
+            ),
+        ):
+            with self.subTest(name=name):
+                expected = canonical(name, args, tools)
+                adapter = server._native_call_as_dsh  # pyright: ignore[reportPrivateUsage] — причина: сверяется адаптер serve с преобразователем run
+                actual = adapter(
+                    {"part": {"tool": name, "state": {"input": args}}}, tools
+                )
+                self.assertTrue(expected, name)
+                self.assertEqual(
+                    json.dumps(actual, sort_keys=True),
+                    json.dumps(expected, sort_keys=True),
+                )
+
+    def test_rw005_stop_group_after_leader_exit(self) -> None:
+        """RW-005: завершившийся лидер не мешает убить живого потомка его группы."""
+        with tempfile.TemporaryDirectory() as name:
+            pidfile = Path(name) / "child.pid"
+            code = (
+                "import os,signal,time; from pathlib import Path; "
+                "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
+                f"Path({str(pidfile)!r}).write_text(str(os.getpid())); time.sleep(30)"
+            )
+            parent = "import subprocess,sys,time; from pathlib import Path; subprocess.Popen([sys.executable,'-c',sys.argv[1]], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); p=Path(sys.argv[2]); deadline=time.monotonic()+3; "
+            parent += (
+                "\nwhile not p.exists() and time.monotonic()<deadline: time.sleep(0.01)"
+            )
+            proc = subprocess.Popen(
+                [sys.executable, "-c", parent, code, str(pidfile)],
+                text=True,
+                start_new_session=True,
+            )
+            try:
+                _ = proc.wait(timeout=5)
+                self.assertTrue(pidfile.exists())
+                child = int(pidfile.read_text())
+                server._stop_proc(proc)  # pyright: ignore[reportPrivateUsage] — причина: проверяется остановка осиротевшего потомка завершившегося лидера
+                deadline = time.monotonic() + 3
+                while time.monotonic() < deadline:
+                    try:
+                        os.kill(child, 0)
+                    except ProcessLookupError:
+                        break
+                    time.sleep(0.02)
+                else:
+                    self.fail("потомок пережил остановку группы")
+            finally:
+                try:
+                    os.killpg(proc.pid, signal.SIGKILL)
+                except ProcessLookupError:
+                    pass
+                _ = proc.wait(timeout=5)
+
+    def test_rw008_error_payload_masks_message_and_detail(self) -> None:
+        """RW-008: общий конструктор ошибки очищает оба поля до сериализации."""
+        secret = "sk-" + "b" * 32
+        payload = server._error_payload(secret, "Bearer hidden-detail")  # pyright: ignore[reportPrivateUsage] — причина: проверяется последняя граница очистки клиентской ошибки
+        encoded = json.dumps(payload)
+        self.assertNotIn(secret, encoded)
+        self.assertNotIn("hidden-detail", encoded)
+
+
+def _fake_result(**over: object) -> dict[str, object]:
+    """Результат попытки serve для подмены `_serve_one_attempt`."""
+    base: dict[str, object] = {
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
+        "prompt_status": None,
+        "transient_error": False,
+    }
+    base.update(over)
+    return base
+
+
+def _callback(args: tuple[object, ...], index: int) -> Callable[[str], None]:
+    """Колбэк `_serve_one_attempt` по позиции (4 reasoning, 5 text)."""
+    return cast(Callable[[str], None], args[index])
+
+
+class _AttemptCase(unittest.TestCase):
+    """База: FakeServe в tmp, пустой HOME и изолированный LEASE_DIR для прямых вызовов попытки."""
+
+    tmpdir: tempfile.TemporaryDirectory[str] = cast(
+        "tempfile.TemporaryDirectory[str]", None
+    )  # pyright: ignore[reportInvalidCast] — причина: значение задаётся в setUp до первого обращения
+    tmp: Path = Path()
+    saved_bin: str = ""
+    saved_lease: Path = Path()
+    env: object = None
+
+    @override
+    def setUp(self) -> None:
+        self.tmpdir = tempfile.TemporaryDirectory()
+        self.tmp = Path(self.tmpdir.name)
+        fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
+        self.saved_bin = server.OPENCODE_BIN
+        self.saved_lease = server.LEASE_DIR
+        server.OPENCODE_BIN = str(fake)
+        server.LEASE_DIR = self.tmp / "leases"
+        (self.tmp / "home").mkdir()
+        self.env = mock.patch.dict(
+            os.environ, {"HOME": str(self.tmp / "home")}, clear=False
+        )
+        _ = cast(_Patcher, self.env).start()
+
+    @override
+    def tearDown(self) -> None:
+        _ = cast(_Patcher, self.env).stop()
+        server.OPENCODE_BIN = self.saved_bin
+        server.LEASE_DIR = self.saved_lease
+        self.tmpdir.cleanup()
+
+    def attempt(
+        self,
+        prompt: str,
+        *,
+        reasoning: list[tuple[float, str]] | None = None,
+        on_ready: Callable[[], None] | None = None,
+        on_token: Callable[[], None] | None = None,
+        emulate_tools: bool = False,
+    ) -> Mapping[str, object]:
+        """Одна реальная попытка serve против FakeServe (метки времени — монотонные)."""
+        marks = reasoning if reasoning is not None else []
+        t0 = time.monotonic()
+
+        def on_reasoning(text: str) -> None:
+            marks.append((time.monotonic(), text))
+            if on_token is not None:
+                on_token()
+
+        def ignore(_text: str) -> None:
+            return None
+
+        def ignore_tool(_payload: dict[str, object]) -> None:
+            return None
+
+        return server._serve_one_attempt(  # pyright: ignore[reportPrivateUsage] — причина: оракул обращается к приватному API моста
+            MODEL,
+            prompt,
+            "high",
+            self.tmp,
+            on_reasoning,
+            ignore,
+            ignore_tool,
+            t0,
+            on_startup_ready=on_ready,
+            emulate_tools=emulate_tools,
+        )
+
+
+class TestServeAttemptOracles(_AttemptCase):
+    """Поведенческие оракулы `_serve_one_attempt` на FakeServe (RW-003/008/011/014/019)."""
+
+    def test_c5_rw004_native_call_updates_last_token_at_no_premature_stall(
+        self,
+    ) -> None:
+        """Cycle 5 RW-004: native-вызов обновляет начало окна stall."""
+        with mock.patch.object(server, "STALL_TIMEOUT_S", 0.6):
+            result = self.attempt("__native_pause__")
+        self.assertTrue(result["native_calls"], result)
+        self.assertEqual(result["terminal"], "succeeded", result)
+        self.assertEqual(result["exit_reason"], "", result)
+
+    def test_c5_fu002_prompt_401_headers_classified_before_hanging_body(self) -> None:
+        """Cycle 5 FU-002: 401 классифицируется до чтения зависшего тела."""
+        started = time.monotonic()
+        with mock.patch.object(server, "FIRST_EVENT_TIMEOUT_S", 0.8):
+            with self.assertRaises(server.ServeSecurityError):
+                _ = self.attempt("__prompt_hang401__")
+        self.assertLess(time.monotonic() - started, 3.0)
+
+    def test_never_event_gives_first_event_timeout(self) -> None:
+        """REQ-006: SSE без событий выполнения -> first_event_timeout."""
+        with mock.patch.object(server, "FIRST_EVENT_TIMEOUT_S", 0.8):
+            started = time.monotonic()
+            result = self.attempt("__never_event__ x")
+        self.assertEqual(result["exit_reason"], "first_event_timeout")
+        self.assertLess(time.monotonic() - started, 8.0)
+
+    def test_silent_model_gives_first_token_timeout(self) -> None:
+        """REQ-007: события есть, токенов нет -> first_token_timeout."""
+        with mock.patch.object(server, "FIRST_TOKEN_TIMEOUT_S", 0.8):
+            result = self.attempt("__silent__ x")
+        self.assertEqual(result["exit_reason"], "first_token_timeout")
+        self.assertIs(result["delivered"], True)
+
+    def test_stall_after_first_token(self) -> None:
+        """REQ-007: пауза после первого токена -> stall_timeout."""
+        reasoning: list[tuple[float, str]] = []
+        with mock.patch.object(server, "STALL_TIMEOUT_S", 0.8):
+            result = self.attempt("__stall__ x", reasoning=reasoning)
+        self.assertEqual(result["exit_reason"], "stall_timeout")
+        self.assertEqual([t for _at, t in reasoning], ["Первая мысль"])
+
+    def test_sse_pause_over_half_second_keeps_stream_alive(self) -> None:
+        """RW-008: пауза SSE 1.4 с не закрывает читатель и не даёт invalid_serve_event."""
+        reasoning: list[tuple[float, str]] = []
+        result = self.attempt("__slow__ x", reasoning=reasoning)
+        self.assertEqual(result["exit_reason"], "")
+        self.assertEqual(result["terminal"], "succeeded")
+        self.assertEqual(
+            "".join(t for _at, t in reasoning), "Мысль0 Мысль1 Мысль2 Мысль3 Мысль4 "
+        )
+
+    def test_startup_gate_released_before_generation_ends(self) -> None:
+        """RW-014: замок старта отпускается по готовности serve, а не по концу генерации."""
+        gate = server._StartupGate()  # pyright: ignore[reportPrivateUsage] — причина: оракул обращается к приватному API моста
+        gate.acquire()
+        self.assertTrue(server._STARTUP_LOCK.locked())  # pyright: ignore[reportPrivateUsage] — причина: оракул обращается к приватному API моста
+        locked_during_tokens: list[bool] = []
+        ready_calls: list[float] = []
+
+        def on_ready() -> None:
+            ready_calls.append(time.monotonic())
+            gate.release()
+
+        def on_token() -> None:
+            locked_during_tokens.append(server._STARTUP_LOCK.locked())  # pyright: ignore[reportPrivateUsage] — причина: оракул обращается к приватному API моста
+
+        reasoning: list[tuple[float, str]] = []
+        try:
+            result = self.attempt(
+                "__slow__ x", reasoning=reasoning, on_ready=on_ready, on_token=on_token
+            )
+        finally:
+            gate.release()
+        self.assertEqual(result["terminal"], "succeeded")
+        self.assertEqual(len(ready_calls), 1)
+        self.assertLess(ready_calls[0], reasoning[0][0])
+        self.assertEqual(len(locked_during_tokens), 5)
+        self.assertFalse(any(locked_during_tokens))
+
+    def test_prompt_http_4xx_fails_closed_fast(self) -> None:
+        """RW-003: 400/404/422 prompt -> fail_closed быстрее FIRST_EVENT_TIMEOUT при пустом SSE."""
+        for code in (400, 404, 422):
+            with (
+                self.subTest(code=code),
+                mock.patch.object(server, "FIRST_EVENT_TIMEOUT_S", 20.0),
+            ):
+                started = time.monotonic()
+                with self.assertRaises(server.ServeSecurityError):
+                    _ = self.attempt(f"__prompt_status_{code}__ x")
+                self.assertLess(time.monotonic() - started, 6.0)
+
+    def test_text_tool_call_closes_step_on_step_finish(self) -> None:
+        """RW-011: текстовый вызов инструмента закрывает шаг tool_calls при эмуляции."""
+        emulated = self.attempt("__tool_text__ x", emulate_tools=True)
+        self.assertEqual(emulated["terminal"], "tool_calls")
+        plain = self.attempt("__tool_text__ x", emulate_tools=False)
+        self.assertEqual(plain["terminal"], "succeeded")
+
+    def test_attempt_rotates_proxy_pool_once(self) -> None:
+        """RW-019: одна попытка serve сдвигает пул прокси ровно на один шаг."""
+        with (
+            mock.patch.object(
+                server, "_next_standalone_proxy", return_value=None
+            ) as rotate,
+            mock.patch.object(
+                server, "_spawn_serve", side_effect=server.ServeUnavailable("stop")
+            ),
+            self.assertRaises(server.ServeUnavailable),
+        ):
+            _ = self.attempt("x")
+        self.assertEqual(rotate.call_count, 1)
+
+
+class TestSpawnAndLeaseOracles(_AttemptCase):
+    """RW-004/RW-006/RW-015: атомарность старта, client_gone и бюджеты cleanup."""
+
+    def _fd_count(self) -> int:
+        return len(os.listdir("/dev/fd"))
+
+    def test_spawn_failures_leave_no_leftovers(self) -> None:
+        """RW-004: сбой Popen/pipe не оставляет FD, порт и каталог состояния."""
+        for name, target in (("popen", "Popen"), ("pipe", "pipe")):
+            with self.subTest(failure=name):
+                env = server._serve_env(MODEL)  # pyright: ignore[reportPrivateUsage] — причина: оракул обращается к приватному API моста
+                state_dir = Path(env["XDG_STATE_HOME"])
+                self.assertTrue(state_dir.is_dir())
+                ports_before = set(server._ACTIVE_SERVE_PORTS)  # pyright: ignore[reportPrivateUsage] — причина: оракул обращается к приватному API моста
+                fds_before = self._fd_count()
+                owner = subprocess if name == "popen" else os
+                with (
+                    mock.patch.object(owner, target, side_effect=OSError(24, "boom")),
+                    self.assertRaises(server.ServeUnavailable),
+                ):
+                    _ = server._spawn_serve("att_fail_" + name, env)  # pyright: ignore[reportPrivateUsage] — причина: оракул обращается к приватному API моста
+                self.assertFalse(state_dir.exists())
+                self.assertEqual(set(server._ACTIVE_SERVE_PORTS), ports_before)  # pyright: ignore[reportPrivateUsage] — причина: оракул обращается к приватному API моста
+                self.assertEqual(self._fd_count(), fds_before)
+
+    def test_lease_cleanup_confirms_sigkill_in_separate_window(self) -> None:
+        """RW-015: группа, игнорирующая SIGTERM, добивается SIGKILL; lease удаляется после смерти."""
+        script = (
+            "import signal,time;signal.signal(signal.SIGTERM, signal.SIG_IGN);"
+            "print('ready', flush=True);time.sleep(60)"
+        )
+        child: subprocess.Popen[str] = subprocess.Popen(
+            [sys.executable, "-I", "-c", script],
+            stdout=subprocess.PIPE,
+            stderr=subprocess.PIPE,
+            start_new_session=True,
+            text=True,
+        )
+        assert child.stdout is not None
+        ready_line = cast(str, child.stdout.readline())
+        self.assertEqual(ready_line.strip(), "ready")
+        lease_dir = self.tmp / "lease-cleanup"
+        lease_dir.mkdir()
+        lease_file = lease_dir / "lease-attC.json"
+        _ = lease_file.write_text("{}", "utf-8")
+        _read_fd, write_fd = os.pipe()
+        os.close(_read_fd)
+        lease = server._ServeLease(  # pyright: ignore[reportPrivateUsage] — причина: оракул обращается к приватному API моста
+            child, child.pid, child.pid, write_fd, lease_dir, "attC", ""
+        )
+        started = time.monotonic()
+        lease.cleanup()
+        elapsed = time.monotonic() - started
+        with self.assertRaises(ProcessLookupError):
+            os.killpg(child.pid, 0)
+        self.assertFalse(lease_file.exists())
+        self.assertGreaterEqual(elapsed, 3.9)
+        # SIGKILL уходит ровно после 4.0 с окна SIGTERM, смерть группы подтверждается во втором окне.
+        self.assertLessEqual(elapsed, 4.9)
+
+    def test_client_gone_check_detects_reset_and_close(self) -> None:
+        """RW-006: ECONNRESET, FIN и закрытый rfile — клиент ушёл; живой сокет — нет."""
+        listener = socket.socket()
+        listener.bind(("127.0.0.1", 0))
+        listener.listen(2)
+        addr = cast(tuple[str, int], listener.getsockname())
+        try:
+            for mode in ("alive", "reset", "fin", "closed"):
+                with self.subTest(mode=mode):
+                    client = socket.create_connection(addr)
+                    conn = listener.accept()[0]
+                    handler = server.Handler.__new__(server.Handler)
+                    handler.rfile = conn.makefile("rb")
+                    try:
+                        if mode == "reset":
+                            client.setsockopt(
+                                socket.SOL_SOCKET,
+                                socket.SO_LINGER,
+                                struct.pack("ii", 1, 0),
+                            )
+                            client.close()
+                            time.sleep(0.1)
+                        elif mode == "fin":
+                            client.close()
+                            time.sleep(0.1)
+                        elif mode == "closed":
+                            handler.rfile.close()
+                        self.assertEqual(
+                            handler._client_gone_check(),  # pyright: ignore[reportPrivateUsage] — причина: оракул проверяет приватный детектор ухода клиента
+                            mode != "alive",
+                        )
+                    finally:
+                        client.close()
+                        conn.close()
+        finally:
+            listener.close()
+
+
+FAKE_HELPER_SERVE = """#!/bin/sh
+trap '' TERM
+sleep 120 &
+echo $! > "$GRANDCHILD_FILE"
+exit 0
+"""
+
+
+class TestHelperProcess(unittest.TestCase):
+    """RW-001/RW-005: процесс --serve-helper (errno до ветки helper, добивание группы)."""
+
+    def _helper_cmd(self, tmp: Path, bin_path: str) -> list[str]:
+        return [
+            sys.executable,
+            "-I",
+            str(Path(server.__file__).resolve()),
+            "--serve-helper",
+            "attemptH",
+            "43211",
+            bin_path,
+            str(tmp / "leases"),
+            str(os.getpid()),
+            "Mon Jan  1 00:00:00 2024",
+        ]
+
+    def test_errno_imported_before_helper_branch(self) -> None:
+        """RW-001: errno связан до ветки --serve-helper."""
+        tree = ast.parse(Path(server.__file__).read_text("utf-8"))
+        branch = next(
+            n
+            for n in tree.body
+            if isinstance(n, ast.If)
+            and ast.unparse(n.test).endswith("['--serve-helper']")
+        )
+        early = {
+            a.name
+            for n in tree.body[: tree.body.index(branch)]
+            if isinstance(n, ast.Import)
+            for a in n.names
+        }
+        self.assertIn("errno", early)
+
+    def test_helper_survives_bad_stdin_without_name_error(self) -> None:
+        """RW-001: EBADF на select lifeline обрабатывается без NameError, lease снимается."""
+        with tempfile.TemporaryDirectory() as raw:
+            tmp = Path(raw)
+            argv = " ".join(f"'{a}'" for a in self._helper_cmd(tmp, "/bin/true"))
+            proc = subprocess.run(
+                ["/bin/sh", "-c", f"exec {argv} <&-"],
+                capture_output=True,
+                text=True,
+                timeout=20,
+                start_new_session=True,
+            )
+            self.assertNotIn("NameError", proc.stderr)
+            self.assertEqual(proc.returncode, 0, proc.stderr)
+            self.assertEqual(list((tmp / "leases").glob("lease-*.json")), [])
+
+    def test_helper_kills_surviving_group_and_removes_lease_last(self) -> None:
+        """RW-005: serve вышел, внук игнорирует SIGTERM -> SIGKILL группе, lease удалён после смерти."""
+        with tempfile.TemporaryDirectory() as raw:
+            tmp = Path(raw)
+            fake = _write_exe(tmp, "opencode-fake", FAKE_HELPER_SERVE)
+            gc_file = tmp / "grandchild.pid"
+            env = dict(os.environ)
+            env["GRANDCHILD_FILE"] = str(gc_file)
+            proc = subprocess.Popen(
+                self._helper_cmd(tmp, str(fake)),
+                stdin=subprocess.PIPE,
+                stdout=subprocess.PIPE,
+                stderr=subprocess.PIPE,
+                env=env,
+                text=True,
+                start_new_session=True,
+            )
+            try:
+                # lifeline (stdin) остаётся открытым: helper завершается сам, когда serve вышел.
+                _ = proc.wait(timeout=30)
+            finally:
+                if proc.poll() is None:
+                    proc.kill()
+                if proc.stdin is not None:
+                    proc.stdin.close()
+                for stream in (proc.stdout, proc.stderr):
+                    if stream is not None:
+                        stream.close()
+            self.assertEqual(proc.returncode, 0)
+            grandchild = int(gc_file.read_text("utf-8").strip())
+            deadline = time.monotonic() + 3.0
+            alive = True
+            while alive and time.monotonic() < deadline:
+                try:
+                    os.kill(grandchild, 0)
+                    time.sleep(0.05)
+                except ProcessLookupError:
+                    alive = False
+            if alive:
+                os.kill(grandchild, signal.SIGKILL)
+            self.assertFalse(alive, "внук группы пережил helper")
+            self.assertEqual(list((tmp / "leases").glob("lease-*.json")), [])
+
+
+if __name__ == "__main__":
+    unittest.main()  # pyright: ignore[reportUnusedCallResult] — причина: результат вызова в тесте не используется
ARTIFACT_END>>>
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/handoff/panel-rework-brief.json sha256=a461f6939bf14c7a656c2f87ecc7a349358857f1acc1c18ce4a77da286982c72
{
  "schema_version": "2.0",
  "run_id": "analyst-teamlead-zen-realtime-reasoning-20261025",
  "teamlead_cycle": 4,
  "panel_slug": "panel/council/r36",
  "panel_verdict": "NEEDS_WORK",
  "summarizer_slot": "gpt-6.1-sol",
  "findings_total": 13,
  "decision_required_human": false,
  "coder_entry": "fix-from-panel",
  "iteration_budget_note": "Cycle 4 Совета Тимлидов по коду завершён после R1 (panel/council/r30) и D1 (panel/council/r36) с вердиктом NEEDS_WORK (4 первичных блокера RW-001..RW-004, 7 non-blocking FU-001..FU-007, 2 excluded: 1 duplicate_of + 1 out_of_scope). Бюджет следующей волны: Coder rework (coder-07, Цикл 5) -> слепой reverse-spec -> Clean-Room L2 -> Cycle 5 Совета Тимлидов по коду.",
  "do_not_change": [
    "Разрешено модифицировать ТОЛЬКО 3 файла из allowed_envelope_changes: bridges/opencode-zen-bridge/server.py, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py, bridges/opencode-zen-bridge/tests/test_step_interruption.py.",
    "Запрещено менять замороженную функцию def _run_env в bridges/opencode-zen-bridge/server.py (sha256=1c51b28fcb83fcc0f4d8b5204c858e11ab5ac975bfe40dca4a0bf61978008e31).",
    "Запрещено менять замороженную функцию def _stream_google_sse в bridges/opencode-zen-bridge/server.py (sha256=5914c9654c7345692dd55e84cfd3765e27406f63a3df85df30bc798bc1778de3).",
    "Запрещено менять замороженную функцию def _execute_google_once в bridges/opencode-zen-bridge/server.py (sha256=88d794cc42be4878e8ab35b00e4668c427929db2dfd0f2bb4b717a63fd0c70d6).",
    "Запрещено добавлять любые внешние зависимости вне стандартной библиотеки Python 3.14 (dependencies = [] в pyproject.toml).",
    "Запрещено модифицировать zen_catalog.py, start.sh, muse-bridge, существующие тестовые модули вне конверта и коммитить dynamic_config.json в git."
  ],
  "instructions": [
    {
      "id": "RW-001",
      "priority": "blocking",
      "criterion": "КОРРЕКТНОСТЬ",
      "file": "bridges/opencode-zen-bridge/server.py",
      "line_hint": "server.py:3265-3266,3330-3333,3341-3345,5512-5517,5577-5584,6779-6790,6840-6845",
      "rule_ref": "RW-001, FALLBACK_DECISION_TABLE phase=DELIVERED, REQ-009",
      "action": "В `_serve_one_attempt` (`server.py:3330-3333`, `:3341-3345`) и внешних циклах SSE (`server.py:5512-5517`, `:5577-5584`) / JSON (`server.py:6779-6790`, `:6840-6845`) включать `prompt_status[\"headers_at\"] is not None` в расчёт `_delivered_now` и `result[\"delivered\"]` на всех путях выхода (включая ветку ошибки чтения тела `_prompt_err` и статусы HTTP `429`/`5xx`). Если `prompt_status[\"headers_at\"]` уже установлен, не выбрасывать `ServeUnavailable` из `_prompt_err`, а возвращать результат с `delivered=True` и `exit_reason=\"prompt_error\"` (или `prompt_http_{st}`), чтобы в режиме `auto` запрос шёл в `serve-retry` (либо завершался терминальной SSE/502 ошибкой при исчерпании бюджета) и никогда не переключался в `opencode run` и не вызывал `record_success()`. Синтетический `STATUS_INITIAL` барьер доставки не ставит.",
      "acceptance": "В режиме `auto` заголовки ответа `prompt_async` получены (`headers_at is not None`), затем происходит обрыв чтения тела ответа или возвращается HTTP 429/5xx до первого токена модели: `Run.execute` и `_spawn_with_stdin` не вызываются ни в SSE, ни в JSON; запрос остаётся на `serve-retry` (с эмиссией разделителя при повторе) или завершается явной ошибкой без `record_success()`.",
      "source_findings": [
        "F-001"
      ],
      "source": "F-001 (realist · R1 · realist-F-001; status=AGREED; votes: R1 realist=AUTHOR; D1 skeptic=AGREE, realist=AUTHOR, visionary=AGREE; duplicates merged: F-003)",
      "evidence": "Ledger F-001: votes=[R1 realist=AUTHOR; D1 skeptic=AGREE, realist=AUTHOR, visionary=AGREE]; dissent=[—]; amendments=[—]."
    },
    {
      "id": "RW-002",
      "priority": "blocking",
      "criterion": "ПОЛНОТА",
      "file": "bridges/opencode-zen-bridge/server.py",
      "line_hint": "server.py:5947-5959,6119-6121,6173,6179,6242",
      "rule_ref": "REQ-004, AC-005",
      "action": "В `Handler._stream_sse` не сбрасывать срок первого статуса на `attempt_start + FIRST_STATUS_DELAY_S` после отмены `status_timer` (либо сохранять `status_timer` до первого видимого чанка / использовать единый абсолютный дедлайн первого статуса `req_start + FIRST_STATUS_DELAY_S` в `send_keepalive`), чтобы при задержке `_StartupGate` / `spawn_limiter.acquire` на `0.4–0.6 с` и молчащем процессе первый видимый статус `[мост]` гарантированно эмитился не позднее `1.0 с` от начала запроса (`AC-005`) и ровно один раз.",
      "acceptance": "При задержке старта/лимитера `0.45–0.55 с` (меньше `0.65 с`) и последующем молчащем процессе первый видимый чанк `[мост]` приходит не позднее `1.0 с` от старта запроса (`AC-005`), начальный статус эмитится ровно один раз.",
      "source_findings": [
        "F-005"
      ],
      "source": "F-005 (visionary · R1 · visionary-F-003; status=AGREED; votes: R1 visionary=AUTHOR; D1 skeptic=AGREE, realist=AGREE, visionary=AUTHOR)",
      "evidence": "Ledger F-005: votes=[R1 visionary=AUTHOR; D1 skeptic=AGREE, realist=AGREE, visionary=AUTHOR]; dissent=[—]; amendments=[—]."
    },
    {
      "id": "RW-003",
      "priority": "blocking",
      "criterion": "ПОЛНОТА",
      "file": "bridges/opencode-zen-bridge/server.py",
      "line_hint": "server.py:6463-6464,6500,6521,6529,6545,6554,6560-6569",
      "rule_ref": "REQ-009, AC-014",
      "action": "На legacy-пути `Handler._stream_sse` централизовать эмиссию разделителя `[мост] Повтор попытки {attempts.total_spawns + 1}/{attempts.max_total}…\\n` перед фактическим запуском следующей попытки (покрывая `watchdog`, `unmapped` и `incomplete` recovery), эмитя ровно один разделитель между попытками только если `thinking_enabled` истинен и предыдущая попытка уже эмитила видимый вывод/размышление (а при `thinking_enabled=False` — не эмитить синтетический разделитель, закрывая одновременно `F-002`).",
      "acceptance": "На legacy-пути `run` при повторе по `watchdog`, `unmapped` и `incomplete` recovery эмитится ровно один разделитель `[мост] Повтор попытки` между попытками при `thinking on` и ноль синтетических разделителей при `thinking off`.",
      "source_findings": [
        "F-007"
      ],
      "source": "F-007 (visionary · R1 · visionary-F-005; status=AGREED; votes: R1 visionary=AUTHOR; D1 skeptic=AMEND, realist=AMEND, visionary=AMEND)",
      "evidence": "Ledger F-007: votes=[R1 visionary=AUTHOR; D1 skeptic=AMEND, realist=AMEND, visionary=AMEND]; dissent=[skeptic d1 «AMEND F-007 priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:6463; fix=обернуть legacy-разделитель в `thinking_enabled`, как в F-002 — причина: panel-rework-brief FU-010 » → teamlead/cycle-4/debate/d1/skeptic.md ; realist d1 «AMEND F-007 priority=blocking; locations=bridges/opencode-zen-bridge/server.py:6529, bridges/opencode-zen-bridge/server.py:6560-6569; fix=перед повтором unmapped и incomplete на legacy `run` э» → teamlead/cycle-4/debate/d1/realist.md ; visionary d1 «AMEND F-007 priority=blocking; locations=`bridges/opencode-zen-bridge/server.py:6463-6464,6500,6521,6545,6554`; fix=централизовать разделитель legacy-повтора после уже выданного reasoning пере» → teamlead/cycle-4/debate/d1/visionary.md]; amendments=[skeptic d1: priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:6463; fix=обернуть legacy-разделитель в `thinking_enabled`, как в F-002 — причина: panel-rework-brief FU-010 — этот же дефект прошлый цикл закрывал к (teamlead/cycle-4/debate/d1/skeptic.md) ; realist d1: priority=blocking; locations=bridges/opencode-zen-bridge/server.py:6529, bridges/opencode-zen-bridge/server.py:6560-6569; fix=перед повтором unmapped и incomplete на legacy `run` эмитить ровно одну строку `[мост] Повтор  (teamlead/cycle-4/debate/d1/realist.md) ; visionary d1: priority=blocking; locations=`bridges/opencode-zen-bridge/server.py:6463-6464,6500,6521,6545,6554`; fix=централизовать разделитель legacy-повтора после уже выданного reasoning перед фактическим следующим запуском; провер (teamlead/cycle-4/debate/d1/visionary.md)]."
    },
    {
      "id": "RW-004",
      "priority": "blocking",
      "criterion": "КОРРЕКТНОСТЬ",
      "file": "bridges/opencode-zen-bridge/server.py",
      "line_hint": "server.py:3296,3316,3486-3490,3502-3506",
      "rule_ref": "REQ-007, AC-009",
      "action": "В `_serve_one_attempt` при получении завершённого нативного вызова (`ev_kind == \"native_call\"`, `server.py:3502-3506`) обновлять `last_token_at = now_ev` одновременно с установкой `first_token_at` (и обновлять `last_token_at` при `tool_input_delta`, если шаг активен), чтобы окно `STALL_TIMEOUT_S` отсчитывалось от последнего полезного события, а не от момента отправки `prompt`.",
      "acceptance": "Если первый нативный вызов завершается через `35 с` после отправки `prompt` при `FIRST_TOKEN_TIMEOUT_S=90` и `STALL_TIMEOUT_S=60`, следующая итерация цикла не объявляет ложный `stall_timeout` на `60 с` от `prompt` (окно `stall` отсчитывается от момента `native_call`).",
      "source_findings": [
        "F-011"
      ],
      "source": "F-011 (visionary · R1 · visionary-F-009; status=AGREED; votes: R1 visionary=AUTHOR; D1 skeptic=AMEND, realist=AGREE, visionary=AUTHOR)",
      "evidence": "Ledger F-011: votes=[R1 visionary=AUTHOR; D1 skeptic=AMEND, realist=AGREE, visionary=AUTHOR]; dissent=[skeptic d1 «AMEND F-011 priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:3502; fix=при завершении native-вызова обновлять `last_token_at = time.monotonic()` рядом с установкой `first» → teamlead/cycle-4/debate/d1/skeptic.md]; amendments=[skeptic d1: priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:3502; fix=при завершении native-вызова обновлять `last_token_at = time.monotonic()` рядом с установкой `first_token_at` — причина: bridges/opencode-z (teamlead/cycle-4/debate/d1/skeptic.md)]."
    }
  ],
  "non_blocking_followups": [
    {
      "id": "FU-001",
      "text": "Обернуть эмиссию разделителя `[мост] Повтор попытки` на legacy watchdog-retry",
      "reason": "`server.py:6463-6464`) проверкой `thinking_enabled`. (Согласовано 3/3 в D1 как non-blocking (реализуется совместно с `RW-003` / `F-007`).",
      "source_findings": [
        "F-002"
      ],
      "decision_required_human": false
    },
    {
      "id": "FU-002",
      "text": "Публиковать HTTP-статус в callback `_on_headers` одновременно с `headers_at`",
      "reason": "`server.py:2604`, `:3266`), чтобы терминальные `400/401/403/404/422` классифицировались до завершения чтения тела. (Понижено большинством 2/3 (`skeptic` + `realist` AMEND non-blocking) в D1: при 4xx prompt не принят и второго вызова Zen нет; реализуем заодно в этом же проходе.",
      "source_findings": [
        "F-004"
      ],
      "decision_required_human": false
    },
    {
      "id": "FU-003",
      "text": "В `Handler._handle_chat_json` на ветке `transient_error`",
      "reason": "`server.py:6855`) пропускать частичные `texts` через `ToolCallParser` и `_strip_broken_tool_blocks` и обновлять `_prior_content` перед `continue`. (Понижено большинством 2/3 (`skeptic` + `realist` AMEND non-blocking) в D1: DSH ходит со `stream:true` (`F-35`); реализуем заодно в этом же проходе.",
      "source_findings": [
        "F-006"
      ],
      "decision_required_human": false
    },
    {
      "id": "FU-004",
      "text": "В `test_ac026_realtime_chunks_before_upstream_end` сопоставлять независимые отметки времени эмиссии каждой дельты на стороне `FakeServe` и получения чанка клиентом",
      "reason": "`< 0.25 с` на каждую дельту). (Согласовано 3/3 в D1 как non-blocking усиление оракула `AC-002`; реализуем заодно в этом же проходе.",
      "source_findings": [
        "F-008"
      ],
      "decision_required_human": false
    },
    {
      "id": "FU-005",
      "text": "При смене транспорта или повторе после принятых заголовков `prompt`",
      "reason": "`headers_at is not None`) на `429/5xx/transient` проводить повтор через `attempts.allow_retry()` с учётом `RetryBudget`. (Понижено большинством 2/3 (`skeptic` + `realist` AMEND non-blocking) в D1: закрывается фиксом `RW-001` (`F-001`), переводящим подтверждённый `prompt` в `serve-retry` через `attempts.allow_retry()`.",
      "source_findings": [
        "F-009"
      ],
      "decision_required_human": false
    },
    {
      "id": "FU-006",
      "text": "Передавать абсолютный `deadline` в `_serve_http` при `interrupt`/`DELETE` в cleanup",
      "reason": "`server.py:3574-3590`) и проверять `deadline`/`is_client_gone` в фазах старта `_spawn_serve`. (Понижено большинством 2/3 (`skeptic` + `realist` AMEND non-blocking) в D1; реализуем заодно в этом же проходе.",
      "source_findings": [
        "F-010"
      ],
      "decision_required_human": false
    },
    {
      "id": "FU-007",
      "text": "Оставить миграцию `tests/test_realtime_reasoning.py` с `unittest.TestCase` на чистые функции `pytest` в бэклоге без переписывания 2000 строк в рамках текущего MR.",
      "reason": "Отклонено/понижено большинством 2/3 (`skeptic` `DISPUTE invalid`, `realist` `AMEND non-blocking`) в D1: весь существующий тестовый набор моста и обязательный гейт `VER-002` (`python3 -m unittest discover`) используют `unittest.TestCase`.",
      "source_findings": [
        "F-012"
      ],
      "decision_required_human": false
    }
  ],
  "excluded": [
    {
      "id": "F-003",
      "reason": "duplicate_of:F-001"
    },
    {
      "id": "F-013",
      "reason": "out_of_scope"
    }
  ]
}
ARTIFACT_END>>>

**3. Handoff исполнителя и квитанции гейтов (`coder.json`, `code-gate.json`, `verifier.json`, `final-gate.json`; `receipts/coder.json` побайтно равен `coder.json`)**
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/coder.json sha256=d4bf82b2b9eec81550e8bcef7f33e42ecc7d760d3c6b8d2421df8a0e451dbd2a
{
  "schema_version": "1.1",
  "role": "coder",
  "task_id": "analyst-teamlead-zen-realtime-reasoning-20261025",
  "run_id": "analyst-teamlead-zen-realtime-reasoning-20261025",
  "round_id": "coder-07",
  "iteration": 1,
  "teamlead_cycle": 5,
  "entry": "fix-from-panel",
  "status": "DONE",
  "next_role": "reviewer",
  "summary": "Реворк Cycle 5: RW-001..RW-004 и FU-001..FU-006 внесены в разрешённые файлы. VER-004 PASS, целевой pytest 180/180, полный pytest 451/451, полный unittest 451/451, collect на origin/dev 72/72. Передача Reviewer; бизнес-приёмка не заявляется.",
  "role_plan": {
    "path": ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-07.json",
    "sha256": "8b83d16b3032f91e3f9e495f3d2a3a0ceec5032a00401d7a4153173571950a0a",
    "phase": "after"
  },
  "changed_files": [
    "bridges/opencode-zen-bridge/server.py",
    "bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py"
  ],
  "files_changed": [
    "bridges/opencode-zen-bridge/server.py",
    "bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py"
  ],
  "inherited_modified_files": [
    "bridges/opencode-zen-bridge/tests/test_step_interruption.py"
  ],
  "report_files": [
    ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-07.before.json",
    ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-07.json",
    ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/handoffs/coder-07.json",
    ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/coder.json",
    ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/coder.json"
  ],
  "commands": [
    {
      "command": "run-guarded -- uvx --from pytest==8.3.4 pytest -q -p no:cacheprovider bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py -k test_c5_ (до правки server.py)",
      "exit_code": 1,
      "result": "6 failed, 66 deselected in 14.34s — ожидаемый RED"
    },
    {
      "command": "run-guarded -- python3 ~/work/cli-agent-bridge/coder-07-20261027-8uvwzvk5/ver004.py",
      "exit_code": 0,
      "result": "PASS VER-004; 0 type errors; frozen 3/3; новый файл 0 diagnostics",
      "output_file": "~/work/cli-agent-bridge/coder-07-20261027-8uvwzvk5/ver004-final.log"
    },
    {
      "command": "run-guarded -- uvx --from pytest==8.3.4 pytest -q -p no:cacheprovider bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py bridges/opencode-zen-bridge/tests/test_step_interruption.py",
      "exit_code": 0,
      "result": "180 passed in 159.84s",
      "output_file": "~/work/cli-agent-bridge/coder-07-20261027-8uvwzvk5/target-pytest.log"
    },
    {
      "command": "run-guarded -- uvx --from pytest==8.3.4 pytest -q -p no:cacheprovider bridges/opencode-zen-bridge/tests",
      "exit_code": 0,
      "result": "451 passed in 208.70s",
      "output_file": "~/work/cli-agent-bridge/coder-07-20261027-8uvwzvk5/full-pytest.log"
    },
    {
      "command": "run-guarded -- python3 -m unittest discover -s tests -p 'test_*.py'",
      "cwd": "bridges/opencode-zen-bridge",
      "exit_code": 0,
      "result": "Ran 451 tests in 205.232s; OK",
      "output_file": "~/work/cli-agent-bridge/coder-07-20261027-8uvwzvk5/full-unittest-bridge.log"
    },
    {
      "command": "uvx --from pytest==8.3.4 pytest --collect-only -q -p no:cacheprovider tests/test_realtime_reasoning.py (изолированные файлы origin/dev + кандидат теста)",
      "exit_code": 0,
      "result": "72 tests collected in 0.07s",
      "output_file": "~/work/cli-agent-bridge/coder-07-20261027-8uvwzvk5/baseline-collect.log"
    },
    {
      "command": "git diff --check",
      "exit_code": 0,
      "result": "Без ошибок пробелов"
    }
  ],
  "acceptance_coverage": [
    {
      "id": "RW-001/FU-002/FU-005",
      "status": "PASS",
      "oracle": "test_c5_rw001_prompt_headers_then_body_error_or_429_blocks_run_fallback; test_c5_fu002_prompt_401_headers_classified_before_hanging_body",
      "evidence": "Headers 200 + reset / 429 / 503: SSE и JSON без run, без record_success, ровно одно списание RetryBudget; зависшее тело 401 классифицируется по заголовкам."
    },
    {
      "id": "RW-002",
      "status": "PASS",
      "oracle": "test_c5_rw002_limiter_delay_half_second_still_emits_first_status_under_1s",
      "evidence": "Лимитер задерживает старт на 0.5 с: STATUS_INITIAL ровно один и <=1.0 с от запроса."
    },
    {
      "id": "RW-003/FU-001",
      "status": "PASS",
      "oracle": "test_c5_rw003_legacy_retry_separator_all_branches_and_thinking_gate",
      "evidence": "watchdog/unmapped/incomplete: две попытки, один разделитель при high и ноль при off."
    },
    {
      "id": "RW-004",
      "status": "PASS",
      "oracle": "test_c5_rw004_native_call_updates_last_token_at_no_premature_stall",
      "evidence": "Первый native-call после 0.4 с, затем ещё 0.4 с при stall=0.6 с: succeeded без преждевременного stall."
    },
    {
      "id": "FU-003",
      "status": "PASS",
      "oracle": "test_c5_fu003_json_transient_recovery_normalizes_and_deduplicates",
      "evidence": "Частичный tool-блок удалён, преамбула в итоговом content встречается один раз."
    },
    {
      "id": "FU-004",
      "status": "PASS",
      "oracle": "test_ac026_realtime_chunks_before_upstream_end",
      "evidence": "Независимые sent_times и recv_times: каждая дельта передана за <0.25 с."
    },
    {
      "id": "FU-006",
      "status": "PASS",
      "oracle": "server.py: finally _serve_one_attempt; VER-004 и оба полных набора",
      "evidence": "interrupt и DELETE получают deadline=time.monotonic()+0.35 при timeout=0.25. Отдельный тест капающего cleanup-тела не добавлялся."
    }
  ],
  "assumptions": [],
  "risks": [
    "Живой существующий рабочий слот/чат владельца не вызывался; проверены FakeServe, локальные HTTP и процессы. Rollout и бизнес-приёмка не заявляются.",
    "FU-006 проверен наличием абсолютных дедлайнов и полными наборами; отдельный сценарий капающего cleanup-тела не выполнялся."
  ],
  "open_questions": [],
  "unresolved_risks": [],
  "source_file_sha256": {
    "bridges/opencode-zen-bridge/server.py": "f99e8c91110c7e3de015be989a8452fec769eff4cfd1f8822d0749bbf696b25e",
    "bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py": "afa8cc8c641383bc757305ece61f72e1f2f5e3b0486741c080be0d5e47d8988e",
    "bridges/opencode-zen-bridge/tests/test_step_interruption.py": "e41d10bd96cb208ce3120ab25d1c8028c82fe81895eacd322312b7fbbbef8a11"
  },
  "frozen_sha256": {
    "_run_env": "1c51b28fcb83fcc0f4d8b5204c858e11ab5ac975bfe40dca4a0bf61978008e31",
    "_stream_google_sse": "5914c9654c7345692dd55e84cfd3765e27406f63a3df85df30bc798bc1778de3",
    "_execute_google_once": "88d794cc42be4878e8ab35b00e4668c427929db2dfd0f2bb4b717a63fd0c70d6"
  },
  "delta_explanations": [
    "RW-001 требует >15 строк: согласованное изменение callback заголовков, классификации prompt_error и обоих циклов SSE/JSON; без любой из этих точек сохраняется fallback после доставки.",
    "FU-003 требует >15 строк: parser/finish, очистка повреждённого tool-блока, dedup и сохранение _prior_content в обеих ветках повторов. Общая архитектура и алгоритмы остальных путей сохранены."
  ],
  "background_checks": [
    "RED pytest (сессия 68609)",
    "GREEN Cycle 5 (25963) и retry-матрица (94598)",
    "Диапазонное форматирование (77350)",
    "Финальный VER-004 (46878)",
    "Целевой pytest (42646)",
    "Полный pytest (28864)",
    "Полный unittest из каталога моста (22299)"
  ],
  "deviations": [
    "Регрессионный incomplete-сценарий уточнён: короткая фраза без tool-блока не запускает recovery; используется незавершённый <tool_call>. Продуктовые эвристики не изменялись.",
    "Буквальный unittest discover из корня дал 18 ошибок импорта; повтор с PYTHONPATH из корня дал 16 ошибок из-за затенения модулем server.py корня. Из каталога bridges/opencode-zen-bridge полный discover прошёл 451/451. Конфиги и импорты проекта не менялись.",
    "Первый VER-004 нашёл одно reportAny в новом тесте на json.loads; явный cast(object, ...) устранил предупреждение. Финальный VER-004: PASS.",
    "Full-file форматирование server.py запрещено брифом: только закрытые изменённые диапазоны. Новый тестовый файл форматировался целиком. Коммит, push и MR не выполнялись.",
    "В дополнение к запрошенным целевому pytest и полному unittest выполнен полный pytest моста для Full Suite Gate.",
    "Before-план сохранил унаследованную опечатку в stop_conditions: отчётность coder-06 вместо coder-07. Фактический scope определялся явным allowlist брифа; before-план оставлен неизменным, after-план уточнён."
  ],
  "before_plan_sha256": "1488a221352ba477f0b6b34c46bf91052af156dceb159772de98f428f8cd2dfd",
  "verification": {
    "light": "VER-004, FakeServe, локальные процессы и HTTP, 180/180 и два полных набора 451/451",
    "heavy": null,
    "not_verified": "Существующий рабочий слот владельца; отдельный капающий cleanup-ответ"
  },
  "raw_outputs": {
    "ver004-final.log": "nchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\n1 file left unchanged\nAll checks passed!\nAll checks passed!\ntest_env_default_is_dynamic (tests.test_catalog_mode.ModeFromEnvironmentTest.test_env_default_is_dynamic) ... ok\ntest_env_static_and_legacy (tests.test_catalog_mode.ModeFromEnvironmentTest.test_env_static_and_legacy) ... ok\ntest_default_in_tests_is_dynamic (tests.test_catalog_mode.ModeNormalizationTest.test_default_in_tests_is_dynamic) ... ok\ntest_modes (tests.test_catalog_mode.ModeNormalizationTest.test_modes) ... ok\ntest_aliases_still_work_in_static (tests.test_catalog_mode.StaticModeTest.test_aliases_still_work_in_static) ... ok\ntest_static_never_reloads_by_mtime (tests.test_catalog_mode.StaticModeTest.test_static_never_reloads_by_mtime) ... ok\ntest_static_routes_through_background_service (tests.test_catalog_mode.StaticModeTest.test_static_routes_through_background_service) ... ok\ntest_static_uses_embedded_snapshot_and_ignores_state_file (tests.test_catalog_mode.StaticModeTest.test_static_uses_embedded_snapshot_and_ignores_state_file) ... ok\n\n----------------------------------------------------------------------\nRan 8 tests in 0.193s\n\nOK\nPASS write-mode frozen hashes {'_run_env': '1c51b28fcb83fcc0f4d8b5204c858e11ab5ac975bfe40dca4a0bf61978008e31', '_execute_google_once': '88d794cc42be4878e8ab35b00e4668c427929db2dfd0f2bb4b717a63fd0c70d6', '_stream_google_sse': '5914c9654c7345692dd55e84cfd3765e27406f63a3df85df30bc798bc1778de3'}\nBASEDPYRIGHT summary {'filesAnalyzed': 3, 'errorCount': 0, 'warningCount': 760, 'informationCount': 0, 'timeInSec': 3.995}\nSERVER dict(counts) {'reportExplicitAny': 123, 'reportAny': 117, 'reportUnusedCallResult': 35, 'reportUnknownMemberType': 72, 'reportUnknownVariableType': 56, 'reportUnknownArgumentType': 48, 'reportUnusedFunction': 2, 'reportImplicitStringConcatenation': 27, 'reportUnannotatedClassAttribute': 98, 'reportUnusedParameter': 3, 'reportUnnecessaryIsInstance': 4, 'reportUnknownParameterType': 2, 'reportMissingParameterType': 2, 'reportUnreachable': 1, 'reportImplicitOverride': 1}\nSERVER warningCount 591\nPASS VER-004: all3 lint/type; legacy changed-range format; newfile whole format; server counts {'reportExplicitAny': 123, 'reportAny': 117, 'reportUnusedCallResult': 35, 'reportUnknownMemberType': 72, 'reportUnknownVariableType': 56, 'reportUnknownArgumentType': 48, 'reportUnusedFunction': 2, 'reportImplicitStringConcatenation': 27, 'reportUnannotatedClassAttribute': 98, 'reportUnusedParameter': 3, 'reportUnnecessaryIsInstance': 4, 'reportUnknownParameterType': 2, 'reportMissingParameterType': 2, 'reportUnreachable': 1, 'reportImplicitOverride': 1}\n",
    "target-pytest.log": "........................................................................ [ 40%]\n........................................................................ [ 80%]\n....................................                                     [100%]\n180 passed in 159.84s (0:02:39)\n",
    "full-pytest.log": "........................................................................ [ 15%]\n........................................................................ [ 31%]\n........................................................................ [ 47%]\n........................................................................ [ 63%]\n........................................................................ [ 79%]\n........................................................................ [ 95%]\n...................                                                      [100%]\n451 passed in 208.70s (0:03:28)\n",
    "full-unittest-bridge.log": "encode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1216 cwd=/var/folders/2f/***/T/tmp9rpdm3c4/ws\n2026-10-27 07:06:48 http \"POST /v1/chat/completions HTTP/1.1\" 200 -\n2026-10-27 07:06:48 opencode built-in tool event: tool=todoread status=error mapped=False as=[]\n2026-10-27 07:06:49 stream unmapped built-in tools=['todoread']: re-prompt 1/2\n2026-10-27 07:06:49 stream exec retry=1 fail_retries=0 model=opencode/muse-spark-1.3-contributor-free prompt_chars=1715 total_spawns=1/3\n2026-10-27 07:06:49 opencode built-in tool event: tool=todoread status=error mapped=False as=[]\n2026-10-27 07:06:50 stream unmapped built-in tools=['todoread']: re-prompt 2/2\n2026-10-27 07:06:50 stream exec retry=2 fail_retries=0 model=opencode/muse-spark-1.3-contributor-free prompt_chars=2214 total_spawns=2/3\n2026-10-27 07:06:51 retry denied (incomplete_step): MAX_TOTAL_SPAWNS=3 reached\n2026-10-27 07:06:51 stream incomplete tool step: retries exhausted (0) signal=4\n2026-10-27 07:06:51 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=125 emulate_tools=True retries=2 total_spawns=3\n2026-10-27 07:06:51 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=3 retries=2 signal=0 tools=0 out_chars=125 transport=run first_event_ms=19 ttft_ms=2405 transport_history=['run'] duration_s=2.67\n.2026-10-27 07:06:51 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1216 cwd=/var/folders/2f/***/T/tmp9rpdm3c4/ws\n2026-10-27 07:06:51 exec: provider error mid-response (transient=True), stopping opencode run\n2026-10-27 07:06:51 exec cli failed rc=1 state=provider_error stderr_tail='HTTP None: provider.transport: Connection lost: ECONNRESET'\n2026-10-27 07:06:51 opencode built-in tool event: tool=todoread status=error mapped=False as=[]\n2026-10-27 07:06:51 unmapped built-in tools=['todoread']: re-prompt 1/2\n2026-10-27 07:06:51 exec retry=1 (unmapped built-in tool) total_spawns=1/3\n2026-10-27 07:06:51 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1715 cwd=/var/folders/2f/***/T/tmp9rpdm3c4/ws\n2026-10-27 07:06:52 exec: step with tool call finished, stopping opencode run\n2026-10-27 07:06:52 done model=muse-spark-1.3-contributor-free rc=-15 state=nonzero_exit tools=2 out_chars=0 retries=1 total_spawns=2\n2026-10-27 07:06:52 http \"POST /v1/chat/completions HTTP/1.1\" 200 -\n2026-10-27 07:06:52 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=-15 total_spawns=2 retries=1 signal=0 tools=2 out_chars=0 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=1.03\n.2026-10-27 07:06:52 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1216 cwd=/var/folders/2f/***/T/tmp9rpdm3c4/ws\n2026-10-27 07:06:52 http \"POST /v1/chat/completions HTTP/1.1\" 200 -\n2026-10-27 07:06:52 opencode built-in tool event: tool=todoread status=error mapped=False as=[]\n2026-10-27 07:06:53 stream unmapped built-in tools=['todoread']: re-prompt 1/2\n2026-10-27 07:06:53 stream exec retry=1 fail_retries=0 model=opencode/muse-spark-1.3-contributor-free prompt_chars=1715 total_spawns=1/3\n2026-10-27 07:06:54 stream incomplete tool step: re-prompt 1/2 signal=4 total_spawns=2/3\n2026-10-27 07:06:54 stream exec retry=2 fail_retries=0 model=opencode/muse-spark-1.3-contributor-free prompt_chars=1900 total_spawns=2/3\n2026-10-27 07:06:54 stream: step with tool call finished, stopping opencode run\n2026-10-27 07:06:54 stream done model=muse-spark-1.3-contributor-free rc=-15 tools=2 out_chars=125 emulate_tools=True retries=2 total_spawns=3\n2026-10-27 07:06:54 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=-15 total_spawns=3 retries=2 signal=4 tools=2 out_chars=125 transport=run first_event_ms=16 ttft_ms=1024 transport_history=['run'] duration_s=2.62\n.....2026-10-27 07:06:55 tool_strip_cap_hit max=16 dropping tail\n2026-10-27 07:06:55 tool_strip_cap_hit max=16 dropping tail\n2026-10-27 07:06:55 tool_strip_cap_hit max=16 dropping tail\n..........................................................2026-10-27 07:06:56 tool_call_unparsed bytes=114 head='{\"name\": \"read\", \"arguments\": {\"file_path\": \"/a\"}} `<tool_call>`{\"name\": \"read\", \"arguments\": {\"file_path\": \"/b\"}}'\n...2026-10-27 07:06:56 tool_call_unparsed bytes=23 head='<tool_call>{\"name\":\"a\"}'\n2026-10-27 07:06:56 tool_call_unparsed bytes=47 head='{\"name\":\"a\"}<tool_call> <tool_call>{\"name\":\"b\"}'\n2026-10-27 07:06:56 tool_call_unparsed bytes=23 head='{\"name\":\"a\"}<tool_call>'\n.2026-10-27 07:06:56 tool_call_unparsed bytes=32 head='{\"name\": \"a\"} <tool_call>{broken'\n..............................................\n----------------------------------------------------------------------\nRan 451 tests in 205.232s\n\nOK\n"
  }
}
ARTIFACT_END>>>
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/code-gate.json sha256=a6cc87b8e1e49bc58fae30a26d121cdbb4ea2b3a98117f9022e32b6a4b8ab6a6
{
  "schema_version": "1.0",
  "gate": "CODE_GATE_AND_L2_CLEANROOM",
  "status": "PASS",
  "timestamp": "2026-10-27T04:32:35.635362+00:00",
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
      "wall_seconds": 18.47,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-red.log",
      "log_sha256": "9aff29c1faaefa606bd347afcecc23a7b1c7202c543d5a8a6faaff7327a73774"
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
      "wall_seconds": 22.41,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver004-packet.log",
      "log_sha256": "153c06e3f5e23c7756f62a109e02d3ebdc5500eb80fbfb2ffe7dedb019b93bf1"
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
      "wall_seconds": 212.92,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver001-pytest.log",
      "log_sha256": "6d9590a036bc6663f658849946706267a71b20258ca5d0d4b33b793eacdf9798"
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
      "wall_seconds": 205.11,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver002-unittest.log",
      "log_sha256": "42b7fc5b435d91162cc18866c672fff4d58d95ce4119c28fb721dbb1061dcd60"
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
      "wall_seconds": 368.72,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver003-pythonpath.log",
      "log_sha256": "e513ea260ef23feefb1cb1080a0e14c344263f1e0660193ef5400397de24af85"
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
      "wall_seconds": 215.62,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver003b-zen-pythonpath.log",
      "log_sha256": "04432d097c2457beb2a0ed08ed2483bf46b8e6d78184cdc38730e4117bd0850d"
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
      "wall_seconds": 131.78,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver005-dedicated.log",
      "log_sha256": "0d584be48bafdc9b353bfa590b0a736c8b6fa723d3c96e920d788f9b65221f69"
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
      "wall_seconds": 212.34,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ac023-reversed.log",
      "log_sha256": "583ffb499f33aafdaa7908903c664af14dfd94ea3dc6fd0d55debf30e873a5de"
    }
  ],
  "ver004_ruff_format_ranges_passed": 216
}
ARTIFACT_END>>>
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/verifier.json sha256=f60147ee21f5cab8b9f863efdd76b568285c0deaa02078b6bf5a7e4e2a13d721
{
  "schema_version": "1.0",
  "gate": "VERIFIER",
  "status": "PASS",
  "run_id": "analyst-teamlead-zen-realtime-reasoning-20261025",
  "timestamp": "2026-10-27T04:37:32.995755+00:00",
  "role_plan": {
    "path": "plans/verifier-01.json",
    "sha256": "53311e10e2cf1e2cc562f1bdf5ff8ad768674358f0abccca7e946f9ff82442f7"
  },
  "code_gate_sha256": "a6cc87b8e1e49bc58fae30a26d121cdbb4ea2b3a98117f9022e32b6a4b8ab6a6",
  "execution_evidence_sha256": "f60f4bb6b184e951cd98b4c6ff4f6e6f23cd0cdd64048fa0d056ceedeb44d138",
  "verification_traceability_sha256": "6b408f0aaa787613a4c9e2ef354cd6178fdcbccfa6c5010c1259ed56854c519f",
  "environment_manifest_sha256": "bfbbe7ddfb3d5b275c99d5ab0673f0b8e46a17baea036ea65e48cd1dceb8bfa3",
  "reverse_spec_sha256": "91d223c36cceed54690e606de8bf07ef50784b40c135d1be77ba672b6f9c55af",
  "l3_state": "DEFERRED_L3"
}
ARTIFACT_END>>>
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/final-gate.json sha256=b41e0dfcee1cfaeae762da9affec98ea3b670e9a5e2431a9c0b7728def07dd01
{
  "schema_version": "1.0",
  "gate": "FINAL_GATE_PRE_COUNCIL",
  "status": "PASS",
  "run_id": "analyst-teamlead-zen-realtime-reasoning-20261025",
  "timestamp": "2026-10-27T04:37:32.996221+00:00",
  "reviewer_skip": true,
  "downstream_panel": true,
  "parent_skill": "analyst-teamlead",
  "coder_handoff_sha256": "d4bf82b2b9eec81550e8bcef7f33e42ecc7d760d3c6b8d2421df8a0e451dbd2a",
  "code_gate_sha256": "a6cc87b8e1e49bc58fae30a26d121cdbb4ea2b3a98117f9022e32b6a4b8ab6a6",
  "verifier_receipt_sha256": "f60147ee21f5cab8b9f863efdd76b568285c0deaa02078b6bf5a7e4e2a13d721",
  "candidate_diff_sha256": "3bf5e0c3c290828af3f1628a1e96674701687c5e69441dd406bb0776d99f4c9b",
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
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/environment-manifest.json sha256=bfbbe7ddfb3d5b275c99d5ab0673f0b8e46a17baea036ea65e48cd1dceb8bfa3
{
  "schema": "environment-manifest/v1",
  "captured_at_utc": "2026-10-27T04:37:32.885050+00:00",
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
    "worktree_fingerprint_after": "50a02000b62f88106e9ea74b6aa6d069dc8670d6db8b85900643ae300d771400",
    "external_runtime_dependencies_added": 0
  }
}
ARTIFACT_END>>>
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/execution-evidence.md sha256=f60f4bb6b184e951cd98b4c6ff4f6e6f23cd0cdd64048fa0d056ceedeb44d138
# Независимое свидетельство исполнения верификации (`execution-evidence.md`, run `analyst-teamlead-zen-realtime-reasoning-20261025`, cycle `5`)

- **Базовый коммит (`origin/dev`):** `7eda27f9d82732bab726a420e31ea2adc15c2c39`
- **Отпечаток рабочего дерева ДО Coder (`coder-07-before.json`):** `None`
- **Отпечаток рабочего дерева ПОСЛЕ Coder (`coder-07-after.json`):** `50a02000b62f88106e9ea74b6aa6d069dc8670d6db8b85900643ae300d771400`
- **Clean-room контур L2:** отдельное `git worktree` от `origin/dev`, исполнено детерминированным `Verifier` (`run_cleanroom_l2.py`), не логами `Coder`.

## Сводная таблица проверок L2 и L3

| ID / Проверка | Уровень | Статус | Команда | CWD | Exit code | Wall (s) | Сырой лог | SHA-256 лога |
|---|---|---|---|---|---|---|---|---|
| `L2-RED-sensitivity` | L2 | `PASS (RED sensitivity rc!=0)` | `uvx pytest -q -p no:cacheprovider tests/test_realtime_reasoning.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `1` | `18.47` | `l2-red.log` | `9aff29c1faaefa606bd347afcecc23a7b1c7202c543d5a8a6faaff7327a73774` |
| `VER-004-packet-command` | L2 | `PASS` | `/bin/zsh -lc python3 - <<'VER004' import ast, collections, hashlib, json, re, subprocess, tempfile from pathlib import Path root = Path.c...` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom` | `0` | `22.41` | `l2-green-ver004-packet.log` | `153c06e3f5e23c7756f62a109e02d3ebdc5500eb80fbfb2ffe7dedb019b93bf1` |
| `VER-004-ruff-format-new` | L2 | `PASS` | `uvx --from ruff==0.17.2 ruff format --check --no-cache tests/test_realtime_reasoning.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `0.04` | `l2-green-ver004-ruff-format-new.log` | `791491a5d9e6128b8400ae730e69e74c9af01651d625cc697d569dfdcee245b7` |
| `VER-001-pytest` | L2 | `PASS` | `uvx pytest -q -p no:cacheprovider tests/` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `212.92` | `l2-green-ver001-pytest.log` | `6d9590a036bc6663f658849946706267a71b20258ca5d0d4b33b793eacdf9798` |
| `VER-002-unittest` | L2 | `PASS` | `python3 -m unittest discover -s tests -p test_*.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `205.11` | `l2-green-ver002-unittest.log` | `42b7fc5b435d91162cc18866c672fff4d58d95ce4119c28fb721dbb1061dcd60` |
| `VER-003-root-pythonpath-pytest` | L2 | `PASS` | `uvx pytest -q -p no:cacheprovider tests/` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom` | `0` | `368.72` | `l2-green-ver003-pythonpath.log` | `e513ea260ef23feefb1cb1080a0e14c344263f1e0660193ef5400397de24af85` |
| `VER-003b-root-pythonpath-zen-pytest` | L2 | `PASS` | `uvx pytest -q -p no:cacheprovider bridges/opencode-zen-bridge/tests/` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom` | `0` | `215.62` | `l2-green-ver003b-zen-pythonpath.log` | `04432d097c2457beb2a0ed08ed2483bf46b8e6d78184cdc38730e4117bd0850d` |
| `VER-005-dedicated-realtime-suite` | L2 | `PASS` | `uvx pytest -q -p no:cacheprovider tests/test_realtime_reasoning.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `131.78` | `l2-green-ver005-dedicated.log` | `0d584be48bafdc9b353bfa590b0a736c8b6fa723d3c96e920d788f9b65221f69` |
| `AC-023-pytest-reversed` | L2 | `PASS` | `uvx pytest -q -p no:cacheprovider tests/test_zen_catalog.py tests/test_tool_emulation.py tests/test_sync_yaml.py tests/test_stream_thinki...` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `212.34` | `l2-green-ac023-reversed.log` | `583ffb499f33aafdaa7908903c664af14dfd94ea3dc6fd0d55debf30e873a5de` |
| `VER-006-live-sse-heavy-path` | L3 | `DEFERRED_L3` | `Rollout ladder H0..H9 + curl -N -sS http://127.0.0.1:9883/v1/chat/completions (deepseek-v4.1-flash-free High, stream=true, multi-turn + tools + disconnect cleanup)` | `~/.dsh/bridges/opencode-zen-bridge` |  |  |  |  |
| `VER-007-deployed-mirror-diff` | L3 | `DEFERRED_L3` | `diff -u bridges/opencode-zen-bridge/server.py ~/.dsh/bridges/opencode-zen-bridge/server.py` | `~/tmp/cli-agent-bridge/zen-realtime-reasoning` |  |  |  |  |

> **Причина отсрочки `DEFERRED_L3` (`verification-integrity.md` §8, `acceptance-package.md` §3):** мутация живого боевого моста `~/.dsh/bridges/opencode-zen-bridge/server.py` (`127.0.0.1:9883`) запрещена до получения вердикта `ACCEPT` Совета Тимлидов (`Forbidden Scope` `handoff-architect.md`, `rollout H0..H9`). Сразу после `ACCEPT` Совета выполняется бэкап в `~/work/backups/`, синхронизация `server.py`, лестница `H0..H9` и живая heavy-path проверка с переводом строк `VER-006`/`VER-007` в `PASS` до открытия MR.

## Сырые логи независимого прогона L2 (`Clean-Room`)

### `L2-RED-sensitivity` (`l2-red.log`, `sha256=9aff29c1faaefa606bd347afcecc23a7b1c7202c543d5a8a6faaff7327a73774`)
```text
$ uvx pytest -q -p no:cacheprovider tests/test_realtime_reasoning.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=1] [wall=18.47s]
--- STDOUT ---
F...FF.FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF.F..FFFFFFFFFFFF [ 84%]
FFFFFFFFFFF                                                              [100%]
=================================== FAILURES ===================================
_ TestLegacyWatchdogAndKillpg.test_c5_rw002_limiter_delay_half_second_still_emits_first_status_under_1s _

self = <tests.test_realtime_reasoning.TestLegacyWatchdogAndKillpg testMethod=test_c5_rw002_limiter_delay_half_second_still_emits_first_status_under_1s>

    def test_c5_rw002_limiter_delay_half_second_still_emits_first_status_under_1s(
        self,
    ) -> None:
        """Cycle 5 RW-002: задержка слота 0.5 с сохраняет абсолютный срок статуса."""
        os.environ["FAKE_RT_MODE"] = "slow"
    
        def delayed(*_args: object, **_kw: object) -> bool:
            time.sleep(0.5)
            return True
    
        with mock.patch.object(
            self.bridge.httpd.resilience.spawn_limiter, "acquire", side_effect=delayed
        ):
            chunks, _ = self.bridge.post_stream_timed("жди")
        initial = [
            (at, text)
            for at, text in _deltas(chunks, "reasoning_content")
>           if server.STATUS_INITIAL.strip() in text
               ^^^^^^^^^^^^^^^^^^^^^
        ]
E       AttributeError: module 'server' has no attribute 'STATUS_INITIAL'

tests/test_realtime_reasoning.py:521: AttributeError
----------------------------- Captured stderr call -----------------------------
2026-10-27 07:09:19 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1023 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 07:09:19 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:09:22 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=6 emulate_tools=True retries=0 total_spawns=1
2026-10-27 07:09:22 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=6 duration_s=2.70
_ TestLegacyWatchdogAndKillpg.test_c5_rw003_legacy_retry_separator_all_branches_and_thinking_gate (branch='watchdog', effort='high') _

self = <tests.test_realtime_reasoning.TestLegacyWatchdogAndKillpg testMethod=test_c5_rw003_legacy_retry_separator_all_branches_and_thinking_gate>

        def test_c5_rw003_legacy_retry_separator_all_branches_and_thinking_gate(
            self,
        ) -> None:
            """Cycle 5 RW-003: один разделитель трёх recovery-веток только при thinking."""
            for branch in ("watchdog", "unmapped", "incomplete"):
                for effort in ("high", "off"):
                    with self.subTest(branch=branch, effort=effort):
                        counter = self.tmp / (branch + effort)
                        body = """#!/usr/bin/env python3
    import json, sys, time
    from pathlib import Path
    p = Path(COUNTER)
    n = int(p.read_text()) if p.exists() else 0
    p.write_text(str(n + 1))
    prompt = sys.stdin.read()
    def ev(o): print(json.dumps(o), flush=True)
    if n == 0:
        ev({"type": "reasoning", "part": {"text": "Первая мысль"}})
        if BRANCH == "watchdog": time.sleep(3)
        elif BRANCH == "unmapped":
            ev({"type": "tool_use", "part": {"tool": "todoread", "state": {"status": "error", "input": {}}}})
        else: ev({"type": "text", "part": {"text": "Проверяю файлы.<tool_call>{"}})
    else:
        ev({"type": "text", "part": {"text": "Ответ"}})
    ev({"type": "step_finish", "part": {"tokens": {"input": 1, "output": 1}}})
    """.replace("COUNTER", repr(str(counter))).replace("BRANCH", repr(branch))
                        server.OPENCODE_BIN = str(
                            _write_exe(self.tmp, "retry-legacy", body)
                        )
                        with (
>                           mock.patch.object(server, "STALL_TIMEOUT_S", 0.3),
                            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                            mock.patch.object(server, "FAIL_RETRY_BACKOFF_S", 0.0),
                        ):

tests/test_realtime_reasoning.py:556: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/Users/aazhiry1/.local/share/uv/python/cpython-3.14.7-macos-x86_64-none/lib/python3.14/unittest/mock.py:1510: in __enter__
    original, local = self.get_original()
                      ^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

self = <unittest.mock._patch object at 0x10c465220>

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
E           AttributeError: <module 'server' from '/private/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge/server.py'> does not have the attribute 'STALL_TIMEOUT_S'

/Users/aazhiry1/.local/share/uv/python/cpython-3.14.7-macos-x86_64-none/lib/python3.14/unittest/mock.py:1480: AttributeError
_ TestLegacyWatchdogAndKillpg.test_c5_rw003_legacy_retry_separator_all_branches_and_thinking_gate (branch='watchdog', effort='off') _

self = <tests.test_realtime_reasoning.TestLegacyWatchdogAndKillpg testMethod=test_c5_rw003_legacy_retry_separator_all_branches_and_thinking_gate>

        def test_c5_rw003_legacy_retry_separator_all_branches_and_thinking_gate(
            self,
        ) -> None:
            """Cycle 5 RW-003: один разделитель трёх recovery-веток только при thinking."""
            for branch in ("watchdog", "unmapped", "incomplete"):
                for effort in ("high", "off"):
                    with self.subTest(branch=branch, effort=effort):
                        counter = self.tmp / (branch + effort)
                        body = """#!/usr/bin/env python3
    import json, sys, time
    from pathlib import Path
    p = Path(COUNTER)
    n = int(p.read_text()) if p.exists() else 0
    p.write_text(str(n + 1))
    prompt = sys.stdin.read()
    def ev(o): print(json.dumps(o), flush=True)
    if n == 0:
        ev({"type": "reasoning", "part": {"text": "Первая мысль"}})
        if BRANCH == "watchdog": time.sleep(3)
        elif BRANCH == "unmapped":
            ev({"type": "tool_use", "part": {"tool": "todoread", "state": {"status": "error", "input": {}}}})
        else: ev({"type": "text", "part": {"text": "Проверяю файлы.<tool_call>{"}})
    else:
        ev({"type": "text", "part": {"text": "Ответ"}})
    ev({"type": "step_finish", "part": {"tokens": {"input": 1, "output": 1}}})
    """.replace("COUNTER", repr(str(counter))).replace("BRANCH", repr(branch))
                        server.OPENCODE_BIN = str(
                            _write_exe(self.tmp, "retry-legacy", body)
                        )
                        with (
>                           mock.patch.object(server, "STALL_TIMEOUT_S", 0.3),
                            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                            mock.patch.object(server, "FAIL_RETRY_BACKOFF_S", 0.0),
                        ):

tests/test_realtime_reasoning.py:556: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/Users/aazhiry1/.local/share/uv/python/cpython-3.14.7-macos-x86_64-none/lib/python3.14/unittest/mock.py:1510: in __enter__
    original, local = self.get_original()
                      ^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

self = <unittest.mock._patch object at 0x10c465220>

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
E           AttributeError: <module 'server' from '/private/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge/server.py'> does not have the attribute 'STALL_TIMEOUT_S'

/Users/aazhiry1/.local/share/uv/python/cpython-3.14.7-macos-x86_64-none/lib/python3.14/unittest/mock.py:1480: AttributeError
_ TestLegacyWatchdogAndKillpg.test_c5_rw003_legacy_retry_separator_all_branches_and_thinking_gate (branch='unmapped', effort='high') _

self = <tests.test_realtime_reasoning.TestLegacyWatchdogAndKillpg testMethod=test_c5_rw003_legacy_retry_separator_all_branches_and_thinking_gate>

        def test_c5_rw003_legacy_retry_separator_all_branches_and_thinking_gate(
            self,
        ) -> None:
            """Cycle 5 RW-003: один разделитель трёх recovery-веток только при thinking."""
            for branch in ("watchdog", "unmapped", "incomplete"):
                for effort in ("high", "off"):
                    with self.subTest(branch=branch, effort=effort):
                        counter = self.tmp / (branch + effort)
                        body = """#!/usr/bin/env python3
    import json, sys, time
    from pathlib import Path
    p = Path(COUNTER)
    n = int(p.read_text()) if p.exists() else 0
    p.write_text(str(n + 1))
    prompt = sys.stdin.read()
    def ev(o): print(json.dumps(o), flush=True)
    if n == 0:
        ev({"type": "reasoning", "part": {"text": "Первая мысль"}})
        if BRANCH == "watchdog": time.sleep(3)
        elif BRANCH == "unmapped":
            ev({"type": "tool_use", "part": {"tool": "todoread", "state": {"status": "error", "input": {}}}})
        else: ev({"type": "text", "part": {"text": "Проверяю файлы.<tool_call>{"}})
    else:
        ev({"type": "text", "part": {"text": "Ответ"}})
    ev({"type": "step_finish", "part": {"tokens": {"input": 1, "output": 1}}})
    """.replace("COUNTER", repr(str(counter))).replace("BRANCH", repr(branch))
                        server.OPENCODE_BIN = str(
                            _write_exe(self.tmp, "retry-legacy", body)
                        )
                        with (
>                           mock.patch.object(server, "STALL_TIMEOUT_S", 0.3),
                            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                            mock.patch.object(server, "FAIL_RETRY_BACKOFF_S", 0.0),
                        ):

tests/test_realtime_reasoning.py:556: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/Users/aazhiry1/.local/share/uv/python/cpython-3.14.7-macos-x86_64-none/lib/python3.14/unittest/mock.py:1510: in __enter__
    original, local = self.get_original()
                      ^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

self = <unittest.mock._patch object at 0x10c3896d0>

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
E           AttributeError: <module 'server' from '/private/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge/server.py'> does not have the attribute 'STALL_TIMEOUT_S'

/Users/aazhiry1/.local/share/uv/python/cpython-3.14.7-macos-x86_64-none/lib/python3.14/unittest/mock.py:1480: AttributeError
_ TestLegacyWatchdogAndKillpg.test_c5_rw003_legacy_retry_separator_all_branches_and_thinking_gate (branch='unmapped', effort='off') _

self = <tests.test_realtime_reasoning.TestLegacyWatchdogAndKillpg testMethod=test_c5_rw003_legacy_retry_separator_all_branches_and_thinking_gate>

        def test_c5_rw003_legacy_retry_separator_all_branches_and_thinking_gate(
            self,
        ) -> None:
            """Cycle 5 RW-003: один разделитель трёх recovery-веток только при thinking."""
            for branch in ("watchdog", "unmapped", "incomplete"):
                for effort in ("high", "off"):
                    with self.subTest(branch=branch, effort=effort):
                        counter = self.tmp / (branch + effort)
                        body = """#!/usr/bin/env python3
    import json, sys, time
    from pathlib import Path
    p = Path(COUNTER)
    n = int(p.read_text()) if p.exists() else 0
    p.write_text(str(n + 1))
    prompt = sys.stdin.read()
    def ev(o): print(json.dumps(o), flush=True)
    if n == 0:
        ev({"type": "reasoning", "part": {"text": "Первая мысль"}})
        if BRANCH == "watchdog": time.sleep(3)
        elif BRANCH == "unmapped":
            ev({"type": "tool_use", "part": {"tool": "todoread", "state": {"status": "error", "input": {}}}})
        else: ev({"type": "text", "part": {"text": "Проверяю файлы.<tool_call>{"}})
    else:
        ev({"type": "text", "part": {"text": "Ответ"}})
    ev({"type": "step_finish", "part": {"tokens": {"input": 1, "output": 1}}})
    """.replace("COUNTER", repr(str(counter))).replace("BRANCH", repr(branch))
                        server.OPENCODE_BIN = str(
                            _write_exe(self.tmp, "retry-legacy", body)
                        )
                        with (
>                           mock.patch.object(server, "STALL_TIMEOUT_S", 0.3),
                            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                            mock.patch.object(server, "FAIL_RETRY_BACKOFF_S", 0.0),
                        ):

tests/test_realtime_reasoning.py:556: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/Users/aazhiry1/.local/share/uv/python/cpython-3.14.7-macos-x86_64-none/lib/python3.14/unittest/mock.py:1510: in __enter__
    original, local = self.get_original()
                      ^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

self = <unittest.mock._patch object at 0x10c696e00>

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
E           AttributeError: <module 'server' from '/private/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge/server.py'> does not have the attribute 'STALL_TIMEOUT_S'

/Users/aazhiry1/.local/share/uv/python/cpython-3.14.7-macos-x86_64-none/lib/python3.14/unittest/mock.py:1480: AttributeError
_ TestLegacyWatchdogAndKillpg.test_c5_rw003_legacy_retry_separator_all_branches_and_thinking_gate (branch='incomplete', effort='high') _

self = <tests.test_realtime_reasoning.TestLegacyWatchdogAndKillpg testMethod=test_c5_rw003_legacy_retry_separator_all_branches_and_thinking_gate>

        def test_c5_rw003_legacy_retry_separator_all_branches_and_thinking_gate(
            self,
        ) -> None:
            """Cycle 5 RW-003: один разделитель трёх recovery-веток только при thinking."""
            for branch in ("watchdog", "unmapped", "incomplete"):
                for effort in ("high", "off"):
                    with self.subTest(branch=branch, effort=effort):
                        counter = self.tmp / (branch + effort)
                        body = """#!/usr/bin/env python3
    import json, sys, time
    from pathlib import Path
    p = Path(COUNTER)
    n = int(p.read_text()) if p.exists() else 0
    p.write_text(str(n + 1))
    prompt = sys.stdin.read()
    def ev(o): print(json.dumps(o), flush=True)
    if n == 0:
        ev({"type": "reasoning", "part": {"text": "Первая мысль"}})
        if BRANCH == "watchdog": time.sleep(3)
        elif BRANCH == "unmapped":
            ev({"type": "tool_use", "part": {"tool": "todoread", "state": {"status": "error", "input": {}}}})
        else: ev({"type": "text", "part": {"text": "Проверяю файлы.<tool_call>{"}})
    else:
        ev({"type": "text", "part": {"text": "Ответ"}})
    ev({"type": "step_finish", "part": {"tokens": {"input": 1, "output": 1}}})
    """.replace("COUNTER", repr(str(counter))).replace("BRANCH", repr(branch))
                        server.OPENCODE_BIN = str(
                            _write_exe(self.tmp, "retry-legacy", body)
                        )
                        with (
>                           mock.patch.object(server, "STALL_TIMEOUT_S", 0.3),
                            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                            mock.patch.object(server, "FAIL_RETRY_BACKOFF_S", 0.0),
                        ):

tests/test_realtime_reasoning.py:556: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/Users/aazhiry1/.local/share/uv/python/cpython-3.14.7-macos-x86_64-none/lib/python3.14/unittest/mock.py:1510: in __enter__
    original, local = self.get_original()
                      ^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

self = <unittest.mock._patch object at 0x10c697680>

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
E           AttributeError: <module 'server' from '/private/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge/server.py'> does not have the attribute 'STALL_TIMEOUT_S'

/Users/aazhiry1/.local/share/uv/python/cpython-3.14.7-macos-x86_64-none/lib/python3.14/unittest/mock.py:1480: AttributeError
_ TestLegacyWatchdogAndKillpg.test_c5_rw003_legacy_retry_separator_all_branches_and_thinking_gate (branch='incomplete', effort='off') _

self = <tests.test_realtime_reasoning.TestLegacyWatchdogAndKillpg testMethod=test_c5_rw003_legacy_retry_separator_all_branches_and_thinking_gate>

        def test_c5_rw003_legacy_retry_separator_all_branches_and_thinking_gate(
            self,
        ) -> None:
            """Cycle 5 RW-003: один разделитель трёх recovery-веток только при thinking."""
            for branch in ("watchdog", "unmapped", "incomplete"):
                for effort in ("high", "off"):
                    with self.subTest(branch=branch, effort=effort):
                        counter = self.tmp / (branch + effort)
                        body = """#!/usr/bin/env python3
    import json, sys, time
    from pathlib import Path
    p = Path(COUNTER)
    n = int(p.read_text()) if p.exists() else 0
    p.write_text(str(n + 1))
    prompt = sys.stdin.read()
    def ev(o): print(json.dumps(o), flush=True)
    if n == 0:
        ev({"type": "reasoning", "part": {"text": "Первая мысль"}})
        if BRANCH == "watchdog": time.sleep(3)
        elif BRANCH == "unmapped":
            ev({"type": "tool_use", "part": {"tool": "todoread", "state": {"status": "error", "input": {}}}})
        else: ev({"type": "text", "part": {"text": "Проверяю файлы.<tool_call>{"}})
    else:
        ev({"type": "text", "part": {"text": "Ответ"}})
    ev({"type": "step_finish", "part": {"tokens": {"input": 1, "output": 1}}})
    """.replace("COUNTER", repr(str(counter))).replace("BRANCH", repr(branch))
                        server.OPENCODE_BIN = str(
                            _write_exe(self.tmp, "retry-legacy", body)
                        )
                        with (
>                           mock.patch.object(server, "STALL_TIMEOUT_S", 0.3),
                            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                            mock.patch.object(server, "FAIL_RETRY_BACKOFF_S", 0.0),
                        ):

tests/test_realtime_reasoning.py:556: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/Users/aazhiry1/.local/share/uv/python/cpython-3.14.7-macos-x86_64-none/lib/python3.14/unittest/mock.py:1510: in __enter__
    original, local = self.get_original()
                      ^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

self = <unittest.mock._patch object at 0x10c38f150>

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
E           AttributeError: <module 'server' from '/private/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge/server.py'> does not have the attribute 'STALL_TIMEOUT_S'

/Users/aazhiry1/.local/share/uv/python/cpython-3.14.7-macos-x86_64-none/lib/python3.14/unittest/mock.py:1480: AttributeError
_ TestLegacyWatchdogAndKillpg.test_initial_status_before_1s_under_startup_gate_contention _

self = <tests.test_realtime_reasoning.TestLegacyWatchdogAndKillpg testMethod=test_initial_status_before_1s_under_startup_gate_contention>

    def test_initial_status_before_1s_under_startup_gate_contention(self) -> None:
        """RW-017: TRANSPORT=run и занятый StartupGate — первый статус не позднее 1.0 с."""
        saved_wait = server.STARTUP_WAIT_S
        server.STARTUP_WAIT_S = 2.5
        self.assertTrue(server._STARTUP_LOCK.acquire(timeout=1.0))  # pyright: ignore[reportPrivateUsage] — причина: оракул обращается к приватному API моста
        try:
            chunks, _elapsed = self.bridge.post_stream_timed("привет")
        finally:
            server._STARTUP_LOCK.release()  # pyright: ignore[reportPrivateUsage] — причина: оракул обращается к приватному API моста
            server.STARTUP_WAIT_S = saved_wait
        reasoning = _deltas(chunks, "reasoning_content")
        statuses = [at for at, t in reasoning if "[мост]" in t]
>       self.assertTrue(statuses, chunks)
E       AssertionError: [] is not true : [(0.003245375002734363, {'id': 'chatcmpl-oczen-5572b74b02e8', 'object': 'chat.completion.chunk', 'created': 1793074164, 'model': 'muse-spark-1.3-contributor-free', 'choices': [{'index': 0, 'delta': {'role': 'assistant', 'content': ''}}]}), (2.6505842079641297, {'id': 'chatcmpl-oczen-5572b74b02e8', 'object': 'chat.completion.chunk', 'created': 1793074164, 'model': 'muse-spark-1.3-contributor-free', 'choices': [{'index': 0, 'delta': {'reasoning_content': 'Simple greeting.'}}]}), (2.6506275410065427, {'id': 'chatcmpl-oczen-5572b74b02e8', 'object': 'chat.completion.chunk', 'created': 1793074164, 'model': 'muse-spark-1.3-contributor-free', 'choices': [{'index': 0, 'delta': {'content': 'Привет!'}}]}), (2.903148957993835, {'id': 'chatcmpl-oczen-5572b74b02e8', 'object': 'chat.completion.chunk', 'created': 1793074164, 'model': 'muse-spark-1.3-contributor-free', 'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}], 'usage': {'prompt_tokens': 3, 'completion_tokens': 2, 'total_tokens': 5}})]

tests/test_realtime_reasoning.py:475: AssertionError
----------------------------- Captured stderr call -----------------------------
2026-10-27 07:09:24 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1026 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 07:09:24 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:09:26 startup_gate_timeout wait_s=2.5, starting without the gate
2026-10-27 07:09:27 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=7 emulate_tools=True retries=0 total_spawns=1
2026-10-27 07:09:27 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=7 duration_s=2.90
____________ TestLegacyWatchdogAndKillpg.test_oexit_fields_present _____________

self = <tests.test_realtime_reasoning.TestLegacyWatchdogAndKillpg testMethod=test_oexit_fields_present>

    def test_oexit_fields_present(self) -> None:
        """O-EXIT/v1 содержит transport/first_event_ms/ttft_ms."""
        _ = self.bridge.post_stream_timed("привет")
        log = Path(self.bridge.tmp.name, "bridge.log")
        text = log.read_text("utf-8") if log.exists() else ""
        if not text:
            text = Path(server.LOG_PATH).read_text("utf-8")
        oexit = [line for line in text.splitlines() if "O-EXIT/v1" in line]
        self.assertTrue(oexit)
>       self.assertIn("transport=", oexit[-1])
E       AssertionError: 'transport=' not found in '2026-10-27 07:09:27 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=7 duration_s=0.38'

tests/test_realtime_reasoning.py:618: AssertionError
----------------------------- Captured stderr call -----------------------------
2026-10-27 07:09:27 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1026 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 07:09:27 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:09:27 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=7 emulate_tools=True retries=0 total_spawns=1
2026-10-27 07:09:27 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=7 duration_s=0.38
_ TestLegacyWatchdogAndKillpg.test_rw002_initial_status_while_waiting_spawn_limiter _

self = <tests.test_realtime_reasoning.TestLegacyWatchdogAndKillpg testMethod=test_rw002_initial_status_while_waiting_spawn_limiter>

    def test_rw002_initial_status_while_waiting_spawn_limiter(self) -> None:
        """RW-002: свободный StartupGate и задержанный лимитер не гасят начальный статус."""
    
        def delayed_acquire(*_args: object, **_kw: object) -> bool:
            time.sleep(1.2)
            return True
    
        with mock.patch.object(
            self.bridge.httpd.resilience.spawn_limiter,
            "acquire",
            side_effect=delayed_acquire,
        ):
            chunks, _ = self.bridge.post_stream_timed("привет")
        statuses = [
            (at, t)
            for at, t in _deltas(chunks, "reasoning_content")
>           if server.STATUS_INITIAL.strip() in t
               ^^^^^^^^^^^^^^^^^^^^^
        ]
E       AttributeError: module 'server' has no attribute 'STATUS_INITIAL'

tests/test_realtime_reasoning.py:499: AttributeError
----------------------------- Captured stderr call -----------------------------
2026-10-27 07:09:28 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1026 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 07:09:28 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:09:30 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=7 emulate_tools=True retries=0 total_spawns=1
2026-10-27 07:09:30 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=7 duration_s=1.61
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

tests/test_realtime_reasoning.py:459: AssertionError
----------------------------- Captured stderr call -----------------------------
2026-10-27 07:09:30 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1028 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 07:09:30 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:09:32 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=6 emulate_tools=True retries=0 total_spawns=1
2026-10-27 07:09:32 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=6 duration_s=1.98
________ TestLegacyWatchdogAndKillpg.test_watchdog_first_event_timeout _________

self = <tests.test_realtime_reasoning.TestLegacyWatchdogAndKillpg testMethod=test_watchdog_first_event_timeout>

    def test_watchdog_first_event_timeout(self) -> None:
        """Тишина апстрима: watchdog срабатывает, а не TIMEOUT_S=1800."""
        os.environ["FAKE_RT_MODE"] = "silent"
>       old: float = server.FIRST_EVENT_TIMEOUT_S
                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'FIRST_EVENT_TIMEOUT_S'

tests/test_realtime_reasoning.py:625: AttributeError
_ TestServeTransportAndFakeServe.test_ac026_realtime_chunks_before_upstream_end _

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_ac026_realtime_chunks_before_upstream_end>

    @override
    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        server.OPENCODE_BIN = str(self.fake)
        self.cfg = self.tmp / "dynamic_config.json"
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
>       self.saved_cfg = server.DYNAMIC_CONFIG_PATH
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'DYNAMIC_CONFIG_PATH'

tests/test_realtime_reasoning.py:660: AttributeError
_ TestServeTransportAndFakeServe.test_auto_fallback_to_run_and_sticky_degradation _

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_auto_fallback_to_run_and_sticky_degradation>

    @override
    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        server.OPENCODE_BIN = str(self.fake)
        self.cfg = self.tmp / "dynamic_config.json"
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
>       self.saved_cfg = server.DYNAMIC_CONFIG_PATH
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'DYNAMIC_CONFIG_PATH'

tests/test_realtime_reasoning.py:660: AttributeError
_ TestServeTransportAndFakeServe.test_c5_fu003_json_transient_recovery_normalizes_and_deduplicates _

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_c5_fu003_json_transient_recovery_normalizes_and_deduplicates>

    @override
    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        server.OPENCODE_BIN = str(self.fake)
        self.cfg = self.tmp / "dynamic_config.json"
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
>       self.saved_cfg = server.DYNAMIC_CONFIG_PATH
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'DYNAMIC_CONFIG_PATH'

tests/test_realtime_reasoning.py:660: AttributeError
_ TestServeTransportAndFakeServe.test_c5_rw001_prompt_headers_then_body_error_or_429_blocks_run_fallback _

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_c5_rw001_prompt_headers_then_body_error_or_429_blocks_run_fallback>

    @override
    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        server.OPENCODE_BIN = str(self.fake)
        self.cfg = self.tmp / "dynamic_config.json"
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
>       self.saved_cfg = server.DYNAMIC_CONFIG_PATH
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'DYNAMIC_CONFIG_PATH'

tests/test_realtime_reasoning.py:660: AttributeError
________ TestServeTransportAndFakeServe.test_canonical_frozen_fixtures _________

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_canonical_frozen_fixtures>

    @override
    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        server.OPENCODE_BIN = str(self.fake)
        self.cfg = self.tmp / "dynamic_config.json"
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
>       self.saved_cfg = server.DYNAMIC_CONFIG_PATH
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'DYNAMIC_CONFIG_PATH'

tests/test_realtime_reasoning.py:660: AttributeError
_ TestServeTransportAndFakeServe.test_clean_room_fake_serve_via_monkeypatched_bin _

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_clean_room_fake_serve_via_monkeypatched_bin>

    @override
    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        server.OPENCODE_BIN = str(self.fake)
        self.cfg = self.tmp / "dynamic_config.json"
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
>       self.saved_cfg = server.DYNAMIC_CONFIG_PATH
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'DYNAMIC_CONFIG_PATH'

tests/test_realtime_reasoning.py:660: AttributeError
____ TestServeTransportAndFakeServe.test_dynamic_config_switch_same_server _____

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_dynamic_config_switch_same_server>

    @override
    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        server.OPENCODE_BIN = str(self.fake)
        self.cfg = self.tmp / "dynamic_config.json"
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
>       self.saved_cfg = server.DYNAMIC_CONFIG_PATH
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'DYNAMIC_CONFIG_PATH'

tests/test_realtime_reasoning.py:660: AttributeError
_ TestServeTransportAndFakeServe.test_foreign_listener_rejected_and_startup_reaper _

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_foreign_listener_rejected_and_startup_reaper>

    @override
    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        server.OPENCODE_BIN = str(self.fake)
        self.cfg = self.tmp / "dynamic_config.json"
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
>       self.saved_cfg = server.DYNAMIC_CONFIG_PATH
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'DYNAMIC_CONFIG_PATH'

tests/test_realtime_reasoning.py:660: AttributeError
_ TestServeTransportAndFakeServe.test_form_missing_title_cancels_without_step2 _

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_form_missing_title_cancels_without_step2>

    @override
    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        server.OPENCODE_BIN = str(self.fake)
        self.cfg = self.tmp / "dynamic_config.json"
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
>       self.saved_cfg = server.DYNAMIC_CONFIG_PATH
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'DYNAMIC_CONFIG_PATH'

tests/test_realtime_reasoning.py:660: AttributeError
_ TestServeTransportAndFakeServe.test_fu003_usage_once_across_distinct_retry_branches _

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_fu003_usage_once_across_distinct_retry_branches>

    @override
    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        server.OPENCODE_BIN = str(self.fake)
        self.cfg = self.tmp / "dynamic_config.json"
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
>       self.saved_cfg = server.DYNAMIC_CONFIG_PATH
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'DYNAMIC_CONFIG_PATH'

tests/test_realtime_reasoning.py:660: AttributeError
_ TestServeTransportAndFakeServe.test_fu010_thinking_off_omits_retry_separator _

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_fu010_thinking_off_omits_retry_separator>

    @override
    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        server.OPENCODE_BIN = str(self.fake)
        self.cfg = self.tmp / "dynamic_config.json"
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
>       self.saved_cfg = server.DYNAMIC_CONFIG_PATH
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'DYNAMIC_CONFIG_PATH'

tests/test_realtime_reasoning.py:660: AttributeError
_ TestServeTransportAndFakeServe.test_fu011_cancelled_never_counts_as_success __

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_fu011_cancelled_never_counts_as_success>

    @override
    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        server.OPENCODE_BIN = str(self.fake)
        self.cfg = self.tmp / "dynamic_config.json"
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
>       self.saved_cfg = server.DYNAMIC_CONFIG_PATH
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'DYNAMIC_CONFIG_PATH'

tests/test_realtime_reasoning.py:660: AttributeError
___ TestServeTransportAndFakeServe.test_helper_argv_validation_and_lease_dir ___

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_helper_argv_validation_and_lease_dir>

    @override
    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        server.OPENCODE_BIN = str(self.fake)
        self.cfg = self.tmp / "dynamic_config.json"
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
>       self.saved_cfg = server.DYNAMIC_CONFIG_PATH
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'DYNAMIC_CONFIG_PATH'

tests/test_realtime_reasoning.py:660: AttributeError
________ TestServeTransportAndFakeServe.test_helper_drains_large_stderr ________

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_helper_drains_large_stderr>

    @override
    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        server.OPENCODE_BIN = str(self.fake)
        self.cfg = self.tmp / "dynamic_config.json"
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
>       self.saved_cfg = server.DYNAMIC_CONFIG_PATH
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'DYNAMIC_CONFIG_PATH'

tests/test_realtime_reasoning.py:660: AttributeError
_ TestServeTransportAndFakeServe.test_json_run_fallback_respects_total_spawn_cap _

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_json_run_fallback_respects_total_spawn_cap>

    @override
    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        server.OPENCODE_BIN = str(self.fake)
        self.cfg = self.tmp / "dynamic_config.json"
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
>       self.saved_cfg = server.DYNAMIC_CONFIG_PATH
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'DYNAMIC_CONFIG_PATH'

tests/test_realtime_reasoning.py:660: AttributeError
_____ TestServeTransportAndFakeServe.test_json_tool_calls_are_deduplicated _____

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_json_tool_calls_are_deduplicated>

    @override
    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        server.OPENCODE_BIN = str(self.fake)
        self.cfg = self.tmp / "dynamic_config.json"
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
>       self.saved_cfg = server.DYNAMIC_CONFIG_PATH
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'DYNAMIC_CONFIG_PATH'

tests/test_realtime_reasoning.py:660: AttributeError
____ TestServeTransportAndFakeServe.test_native_tool_and_permission_reject _____

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_native_tool_and_permission_reject>

    @override
    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        server.OPENCODE_BIN = str(self.fake)
        self.cfg = self.tmp / "dynamic_config.json"
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
>       self.saved_cfg = server.DYNAMIC_CONFIG_PATH
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'DYNAMIC_CONFIG_PATH'

tests/test_realtime_reasoning.py:660: AttributeError
_ TestServeTransportAndFakeServe.test_prompt_http_4xx_fail_closed_without_run_fallback _

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_prompt_http_4xx_fail_closed_without_run_fallback>

    @override
    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        server.OPENCODE_BIN = str(self.fake)
        self.cfg = self.tmp / "dynamic_config.json"
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
>       self.saved_cfg = server.DYNAMIC_CONFIG_PATH
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'DYNAMIC_CONFIG_PATH'

tests/test_realtime_reasoning.py:660: AttributeError
_ TestServeTransportAndFakeServe.test_proxy_pool_advances_once_per_serve_attempt _

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_proxy_pool_advances_once_per_serve_attempt>

    @override
    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        server.OPENCODE_BIN = str(self.fake)
        self.cfg = self.tmp / "dynamic_config.json"
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
>       self.saved_cfg = server.DYNAMIC_CONFIG_PATH
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'DYNAMIC_CONFIG_PATH'

tests/test_realtime_reasoning.py:660: AttributeError
_ TestServeTransportAndFakeServe.test_retry_separator_once_and_delivery_barrier_is_monotonic _

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_retry_separator_once_and_delivery_barrier_is_monotonic>

    @override
    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        server.OPENCODE_BIN = str(self.fake)
        self.cfg = self.tmp / "dynamic_config.json"
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
>       self.saved_cfg = server.DYNAMIC_CONFIG_PATH
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'DYNAMIC_CONFIG_PATH'

tests/test_realtime_reasoning.py:660: AttributeError
_ TestServeTransportAndFakeServe.test_rw001_delivery_survives_unavailable_or_limiter _

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_rw001_delivery_survives_unavailable_or_limiter>

    @override
    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        server.OPENCODE_BIN = str(self.fake)
        self.cfg = self.tmp / "dynamic_config.json"
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
>       self.saved_cfg = server.DYNAMIC_CONFIG_PATH
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'DYNAMIC_CONFIG_PATH'

tests/test_realtime_reasoning.py:660: AttributeError
_ TestServeTransportAndFakeServe.test_rw003_mkdtemp_failure_is_serve_unavailable _

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_rw003_mkdtemp_failure_is_serve_unavailable>

    @override
    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        server.OPENCODE_BIN = str(self.fake)
        self.cfg = self.tmp / "dynamic_config.json"
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
>       self.saved_cfg = server.DYNAMIC_CONFIG_PATH
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'DYNAMIC_CONFIG_PATH'

tests/test_realtime_reasoning.py:660: AttributeError
_ TestServeTransportAndFakeServe.test_rw006_invalid_utf8_falls_back_and_recovers _

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_rw006_invalid_utf8_falls_back_and_recovers>

    @override
    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        server.OPENCODE_BIN = str(self.fake)
        self.cfg = self.tmp / "dynamic_config.json"
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
>       self.saved_cfg = server.DYNAMIC_CONFIG_PATH
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'DYNAMIC_CONFIG_PATH'

tests/test_realtime_reasoning.py:660: AttributeError
_ TestServeTransportAndFakeServe.test_rw007_split_interrupted_marker_at_every_boundary _

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_rw007_split_interrupted_marker_at_every_boundary>

    @override
    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        server.OPENCODE_BIN = str(self.fake)
        self.cfg = self.tmp / "dynamic_config.json"
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
>       self.saved_cfg = server.DYNAMIC_CONFIG_PATH
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'DYNAMIC_CONFIG_PATH'

tests/test_realtime_reasoning.py:660: AttributeError
_ TestServeTransportAndFakeServe.test_rw008_provider_secrets_hidden_in_sse_json_and_log _

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_rw008_provider_secrets_hidden_in_sse_json_and_log>

    @override
    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        server.OPENCODE_BIN = str(self.fake)
        self.cfg = self.tmp / "dynamic_config.json"
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
>       self.saved_cfg = server.DYNAMIC_CONFIG_PATH
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'DYNAMIC_CONFIG_PATH'

tests/test_realtime_reasoning.py:660: AttributeError
_ TestServeTransportAndFakeServe.test_serve_400_fails_closed_without_health_increment _

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_serve_400_fails_closed_without_health_increment>

    @override
    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        server.OPENCODE_BIN = str(self.fake)
        self.cfg = self.tmp / "dynamic_config.json"
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
>       self.saved_cfg = server.DYNAMIC_CONFIG_PATH
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'DYNAMIC_CONFIG_PATH'

tests/test_realtime_reasoning.py:660: AttributeError
_____ TestServeTransportAndFakeServe.test_serve_env_sanitized_all_branches _____

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_serve_env_sanitized_all_branches>

    @override
    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        server.OPENCODE_BIN = str(self.fake)
        self.cfg = self.tmp / "dynamic_config.json"
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
>       self.saved_cfg = server.DYNAMIC_CONFIG_PATH
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'DYNAMIC_CONFIG_PATH'

tests/test_realtime_reasoning.py:660: AttributeError
_____ TestServeTransportAndFakeServe.test_serve_health_and_fallback_table ______

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_serve_health_and_fallback_table>

    @override
    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        server.OPENCODE_BIN = str(self.fake)
        self.cfg = self.tmp / "dynamic_config.json"
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
>       self.saved_cfg = server.DYNAMIC_CONFIG_PATH
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'DYNAMIC_CONFIG_PATH'

tests/test_realtime_reasoning.py:660: AttributeError
_ TestServeTransportAndFakeServe.test_slow_pause_streams_all_deltas_and_single_initial_status _

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_slow_pause_streams_all_deltas_and_single_initial_status>

    @override
    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        server.OPENCODE_BIN = str(self.fake)
        self.cfg = self.tmp / "dynamic_config.json"
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
>       self.saved_cfg = server.DYNAMIC_CONFIG_PATH
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'DYNAMIC_CONFIG_PATH'

tests/test_realtime_reasoning.py:660: AttributeError
_ TestServeTransportAndFakeServe.test_slow_serve_gets_status_and_no_status_on_fast _

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_slow_serve_gets_status_and_no_status_on_fast>

    @override
    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        server.OPENCODE_BIN = str(self.fake)
        self.cfg = self.tmp / "dynamic_config.json"
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
>       self.saved_cfg = server.DYNAMIC_CONFIG_PATH
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'DYNAMIC_CONFIG_PATH'

tests/test_realtime_reasoning.py:660: AttributeError
_ TestServeTransportAndFakeServe.test_timeout_and_client_gone_never_count_as_success _

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_timeout_and_client_gone_never_count_as_success>

    @override
    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        server.OPENCODE_BIN = str(self.fake)
        self.cfg = self.tmp / "dynamic_config.json"
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
>       self.saved_cfg = server.DYNAMIC_CONFIG_PATH
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'DYNAMIC_CONFIG_PATH'

tests/test_realtime_reasoning.py:660: AttributeError
_ TestServeTransportAndFakeServe.test_tool_choice_preserved_in_step_recovery_prompt _

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_tool_choice_preserved_in_step_recovery_prompt>

    @override
    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        server.OPENCODE_BIN = str(self.fake)
        self.cfg = self.tmp / "dynamic_config.json"
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
>       self.saved_cfg = server.DYNAMIC_CONFIG_PATH
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'DYNAMIC_CONFIG_PATH'

tests/test_realtime_reasoning.py:660: AttributeError
______ TestServeTransportAndFakeServe.test_tool_text_split_across_deltas _______

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_tool_text_split_across_deltas>

    @override
    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        server.OPENCODE_BIN = str(self.fake)
        self.cfg = self.tmp / "dynamic_config.json"
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
>       self.saved_cfg = server.DYNAMIC_CONFIG_PATH
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'DYNAMIC_CONFIG_PATH'

tests/test_realtime_reasoning.py:660: AttributeError
___________ TestReworkUnits.test_disable_file_overrides_forced_serve ___________

self = <tests.test_realtime_reasoning.TestReworkUnits testMethod=test_disable_file_overrides_forced_serve>

    def test_disable_file_overrides_forced_serve(self) -> None:
        """FU-013: файл отключения важнее принудительного выбора serve."""
        with tempfile.TemporaryDirectory() as name:
            disable = Path(name) / "disable-serve"
            _ = disable.write_text("1")
            with mock.patch.dict(
                os.environ,
                {
                    "OPENCODE_ZEN_BRIDGE_TRANSPORT": "serve",
                    "OPENCODE_ZEN_BRIDGE_SERVE_DISABLE_FILE": str(disable),
                    "OPENCODE_ZEN_BRIDGE_REALTIME_SERVE_ENABLED": "1",
                },
            ):
>               self.assertEqual(server._select_transport(), "run")  # pyright: ignore[reportPrivateUsage] — причина: проверяется приоритет аварийного файла отключения
                                 ^^^^^^^^^^^^^^^^^^^^^^^^
E               AttributeError: module 'server' has no attribute '_select_transport'

tests/test_realtime_reasoning.py:1552: AttributeError
________________ TestReworkUnits.test_elf_magic_and_tool_status ________________

self = <tests.test_realtime_reasoning.TestReworkUnits testMethod=test_elf_magic_and_tool_status>

    def test_elf_magic_and_tool_status(self) -> None:
        """FU-001/FU-002: 4 случайных байта не ELF, статус tool из типа события."""
>       state = server._ServeToolState()  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
                ^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute '_ServeToolState'

tests/test_realtime_reasoning.py:1580: AttributeError
_ TestReworkUnits.test_fu001_http_checks_deadline_and_cancellation_before_connect _

self = <tests.test_realtime_reasoning.TestReworkUnits testMethod=test_fu001_http_checks_deadline_and_cancellation_before_connect>

    def test_fu001_http_checks_deadline_and_cancellation_before_connect(self) -> None:
        """FU-001: просроченный бюджет и ушедший клиент запрещают даже соединение HTTP."""
>       call = server._serve_http  # pyright: ignore[reportPrivateUsage] — причина: проверяется граница фазы управляющего HTTP-вызова
               ^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute '_serve_http'

tests/test_realtime_reasoning.py:1605: AttributeError
_ TestReworkUnits.test_rw004_native_calls_share_canonical_mapping (name='bash') _

self = <tests.test_realtime_reasoning.TestReworkUnits testMethod=test_rw004_native_calls_share_canonical_mapping>

    def test_rw004_native_calls_share_canonical_mapping(self) -> None:
        """RW-004: bash/read/edit/list/multiedit используют ровно канонический fit_args."""
        tools: list[dict[str, object]] = [
            {
                "type": "function",
                "function": {
                    "name": name,
                    "parameters": {
                        "type": "object",
                        "properties": props,
                        "required": list(props),
                    },
                },
            }
            for name, props in (
                (
                    "bash",
                    {"command": {"type": "string"}, "description": {"type": "string"}},
                ),
                ("read", {"file_path": {"type": "string"}}),
                (
                    "edit",
                    {
                        "file_path": {"type": "string"},
                        "old_string": {"type": "string"},
                        "new_string": {"type": "string"},
                    },
                ),
            )
        ]
        mapper = server._native_to_tool_calls  # pyright: ignore[reportPrivateUsage] — причина: канонический преобразователь run служит оракулом адаптера serve
        canonical = cast(
            Callable[
                [object, object, list[dict[str, object]]], list[dict[str, object]]
            ],
            mapper,
        )
        for name, args in (
            ("bash", {"command": "pwd"}),
            ("read", {"filePath": "/tmp/a"}),
            ("edit", {"filePath": "/tmp/a", "oldString": "a", "newString": "b"}),
            ("list", {"path": "/tmp"}),
            (
                "multiedit",
                {
                    "filePath": "/tmp/a",
                    "edits": [
                        {"oldString": "a", "newString": "b"},
                        {"oldString": "c", "newString": "d"},
                    ],
                },
            ),
        ):
            with self.subTest(name=name):
                expected = canonical(name, args, tools)
>               adapter = server._native_call_as_dsh  # pyright: ignore[reportPrivateUsage] — причина: сверяется адаптер serve с преобразователем run
                          ^^^^^^^^^^^^^^^^^^^^^^^^^^
E               AttributeError: module 'server' has no attribute '_native_call_as_dsh'

tests/test_realtime_reasoning.py:1666: AttributeError
_ TestReworkUnits.test_rw004_native_calls_share_canonical_mapping (name='read') _

self = <tests.test_realtime_reasoning.TestReworkUnits testMethod=test_rw004_native_calls_share_canonical_mapping>

    def test_rw004_native_calls_share_canonical_mapping(self) -> None:
        """RW-004: bash/read/edit/list/multiedit используют ровно канонический fit_args."""
        tools: list[dict[str, object]] = [
            {
                "type": "function",
                "function": {
                    "name": name,
                    "parameters": {
                        "type": "object",
                        "properties": props,
                        "required": list(props),
                    },
                },
            }
            for name, props in (
                (
                    "bash",
                    {"command": {"type": "string"}, "description": {"type": "string"}},
                ),
                ("read", {"file_path": {"type": "string"}}),
                (
                    "edit",
                    {
                        "file_path": {"type": "string"},
                        "old_string": {"type": "string"},
                        "new_string": {"type": "string"},
                    },
                ),
            )
        ]
        mapper = server._native_to_tool_calls  # pyright: ignore[reportPrivateUsage] — причина: канонический преобразователь run служит оракулом адаптера serve
        canonical = cast(
            Callable[
                [object, object, list[dict[str, object]]], list[dict[str, object]]
            ],
            mapper,
        )
        for name, args in (
            ("bash", {"command": "pwd"}),
            ("read", {"filePath": "/tmp/a"}),
            ("edit", {"filePath": "/tmp/a", "oldString": "a", "newString": "b"}),
            ("list", {"path": "/tmp"}),
            (
                "multiedit",
                {
                    "filePath": "/tmp/a",
                    "edits": [
                        {"oldString": "a", "newString": "b"},
                        {"oldString": "c", "newString": "d"},
                    ],
                },
            ),
        ):
            with self.subTest(name=name):
                expected = canonical(name, args, tools)
>               adapter = server._native_call_as_dsh  # pyright: ignore[reportPrivateUsage] — причина: сверяется адаптер serve с преобразователем run
                          ^^^^^^^^^^^^^^^^^^^^^^^^^^
E               AttributeError: module 'server' has no attribute '_native_call_as_dsh'

tests/test_realtime_reasoning.py:1666: AttributeError
_ TestReworkUnits.test_rw004_native_calls_share_canonical_mapping (name='edit') _

self = <tests.test_realtime_reasoning.TestReworkUnits testMethod=test_rw004_native_calls_share_canonical_mapping>

    def test_rw004_native_calls_share_canonical_mapping(self) -> None:
        """RW-004: bash/read/edit/list/multiedit используют ровно канонический fit_args."""
        tools: list[dict[str, object]] = [
            {
                "type": "function",
                "function": {
                    "name": name,
                    "parameters": {
                        "type": "object",
                        "properties": props,
                        "required": list(props),
                    },
                },
            }
            for name, props in (
                (
                    "bash",
                    {"command": {"type": "string"}, "description": {"type": "string"}},
                ),
                ("read", {"file_path": {"type": "string"}}),
                (
                    "edit",
                    {
                        "file_path": {"type": "string"},
                        "old_string": {"type": "string"},
                        "new_string": {"type": "string"},
                    },
                ),
            )
        ]
        mapper = server._native_to_tool_calls  # pyright: ignore[reportPrivateUsage] — причина: канонический преобразователь run служит оракулом адаптера serve
        canonical = cast(
            Callable[
                [object, object, list[dict[str, object]]], list[dict[str, object]]
            ],
            mapper,
        )
        for name, args in (
            ("bash", {"command": "pwd"}),
            ("read", {"filePath": "/tmp/a"}),
            ("edit", {"filePath": "/tmp/a", "oldString": "a", "newString": "b"}),
            ("list", {"path": "/tmp"}),
            (
                "multiedit",
                {
                    "filePath": "/tmp/a",
                    "edits": [
                        {"oldString": "a", "newString": "b"},
                        {"oldString": "c", "newString": "d"},
                    ],
                },
            ),
        ):
            with self.subTest(name=name):
                expected = canonical(name, args, tools)
>               adapter = server._native_call_as_dsh  # pyright: ignore[reportPrivateUsage] — причина: сверяется адаптер serve с преобразователем run
                          ^^^^^^^^^^^^^^^^^^^^^^^^^^
E               AttributeError: module 'server' has no attribute '_native_call_as_dsh'

tests/test_realtime_reasoning.py:1666: AttributeError
_ TestReworkUnits.test_rw004_native_calls_share_canonical_mapping (name='list') _

self = <tests.test_realtime_reasoning.TestReworkUnits testMethod=test_rw004_native_calls_share_canonical_mapping>

    def test_rw004_native_calls_share_canonical_mapping(self) -> None:
        """RW-004: bash/read/edit/list/multiedit используют ровно канонический fit_args."""
        tools: list[dict[str, object]] = [
            {
                "type": "function",
                "function": {
                    "name": name,
                    "parameters": {
                        "type": "object",
                        "properties": props,
                        "required": list(props),
                    },
                },
            }
            for name, props in (
                (
                    "bash",
                    {"command": {"type": "string"}, "description": {"type": "string"}},
                ),
                ("read", {"file_path": {"type": "string"}}),
                (
                    "edit",
                    {
                        "file_path": {"type": "string"},
                        "old_string": {"type": "string"},
                        "new_string": {"type": "string"},
                    },
                ),
            )
        ]
        mapper = server._native_to_tool_calls  # pyright: ignore[reportPrivateUsage] — причина: канонический преобразователь run служит оракулом адаптера serve
        canonical = cast(
            Callable[
                [object, object, list[dict[str, object]]], list[dict[str, object]]
            ],
            mapper,
        )
        for name, args in (
            ("bash", {"command": "pwd"}),
            ("read", {"filePath": "/tmp/a"}),
            ("edit", {"filePath": "/tmp/a", "oldString": "a", "newString": "b"}),
            ("list", {"path": "/tmp"}),
            (
                "multiedit",
                {
                    "filePath": "/tmp/a",
                    "edits": [
                        {"oldString": "a", "newString": "b"},
                        {"oldString": "c", "newString": "d"},
                    ],
                },
            ),
        ):
            with self.subTest(name=name):
                expected = canonical(name, args, tools)
>               adapter = server._native_call_as_dsh  # pyright: ignore[reportPrivateUsage] — причина: сверяется адаптер serve с преобразователем run
                          ^^^^^^^^^^^^^^^^^^^^^^^^^^
E               AttributeError: module 'server' has no attribute '_native_call_as_dsh'

tests/test_realtime_reasoning.py:1666: AttributeError
_ TestReworkUnits.test_rw004_native_calls_share_canonical_mapping (name='multiedit') _

self = <tests.test_realtime_reasoning.TestReworkUnits testMethod=test_rw004_native_calls_share_canonical_mapping>

    def test_rw004_native_calls_share_canonical_mapping(self) -> None:
        """RW-004: bash/read/edit/list/multiedit используют ровно канонический fit_args."""
        tools: list[dict[str, object]] = [
            {
                "type": "function",
                "function": {
                    "name": name,
                    "parameters": {
                        "type": "object",
                        "properties": props,
                        "required": list(props),
                    },
                },
            }
            for name, props in (
                (
                    "bash",
                    {"command": {"type": "string"}, "description": {"type": "string"}},
                ),
                ("read", {"file_path": {"type": "string"}}),
                (
                    "edit",
                    {
                        "file_path": {"type": "string"},
                        "old_string": {"type": "string"},
                        "new_string": {"type": "string"},
                    },
                ),
            )
        ]
        mapper = server._native_to_tool_calls  # pyright: ignore[reportPrivateUsage] — причина: канонический преобразователь run служит оракулом адаптера serve
        canonical = cast(
            Callable[
                [object, object, list[dict[str, object]]], list[dict[str, object]]
            ],
            mapper,
        )
        for name, args in (
            ("bash", {"command": "pwd"}),
            ("read", {"filePath": "/tmp/a"}),
            ("edit", {"filePath": "/tmp/a", "oldString": "a", "newString": "b"}),
            ("list", {"path": "/tmp"}),
            (
                "multiedit",
                {
                    "filePath": "/tmp/a",
                    "edits": [
                        {"oldString": "a", "newString": "b"},
                        {"oldString": "c", "newString": "d"},
                    ],
                },
            ),
        ):
            with self.subTest(name=name):
                expected = canonical(name, args, tools)
>               adapter = server._native_call_as_dsh  # pyright: ignore[reportPrivateUsage] — причина: сверяется адаптер serve с преобразователем run
                          ^^^^^^^^^^^^^^^^^^^^^^^^^^
E               AttributeError: module 'server' has no attribute '_native_call_as_dsh'

tests/test_realtime_reasoning.py:1666: AttributeError
___________ TestReworkUnits.test_rw005_stop_group_after_leader_exit ____________

self = <tests.test_realtime_reasoning.TestReworkUnits testMethod=test_rw005_stop_group_after_leader_exit>

    def test_rw005_stop_group_after_leader_exit(self) -> None:
        """RW-005: завершившийся лидер не мешает убить живого потомка его группы."""
        with tempfile.TemporaryDirectory() as name:
            pidfile = Path(name) / "child.pid"
            code = (
                "import os,signal,time; from pathlib import Path; "
                "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
                f"Path({str(pidfile)!r}).write_text(str(os.getpid())); time.sleep(30)"
            )
            parent = "import subprocess,sys,time; from pathlib import Path; subprocess.Popen([sys.executable,'-c',sys.argv[1]], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); p=Path(sys.argv[2]); deadline=time.monotonic()+3; "
            parent += (
                "\nwhile not p.exists() and time.monotonic()<deadline: time.sleep(0.01)"
            )
            proc = subprocess.Popen(
                [sys.executable, "-c", parent, code, str(pidfile)],
                text=True,
                start_new_session=True,
            )
            try:
                _ = proc.wait(timeout=5)
                self.assertTrue(pidfile.exists())
                child = int(pidfile.read_text())
                server._stop_proc(proc)  # pyright: ignore[reportPrivateUsage] — причина: проверяется остановка осиротевшего потомка завершившегося лидера
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline:
                    try:
                        os.kill(child, 0)
                    except ProcessLookupError:
                        break
                    time.sleep(0.02)
                else:
>                   self.fail("потомок пережил остановку группы")
E                   AssertionError: потомок пережил остановку группы

tests/test_realtime_reasoning.py:1707: AssertionError
______ TestReworkUnits.test_rw008_error_payload_masks_message_and_detail _______

self = <tests.test_realtime_reasoning.TestReworkUnits testMethod=test_rw008_error_payload_masks_message_and_detail>

    def test_rw008_error_payload_masks_message_and_detail(self) -> None:
        """RW-008: общий конструктор ошибки очищает оба поля до сериализации."""
        secret = "sk-" + "b" * 32
        payload = server._error_payload(secret, "Bearer hidden-detail")  # pyright: ignore[reportPrivateUsage] — причина: проверяется последняя граница очистки клиентской ошибки
        encoded = json.dumps(payload)
>       self.assertNotIn(secret, encoded)
E       AssertionError: 'sk-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb' unexpectedly found in '{"error": {"message": "sk-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb", "type": "proxy_error", "code": 502, "detail": "Bearer hidden-detail"}}'

tests/test_realtime_reasoning.py:1720: AssertionError
_______ TestReworkUnits.test_service_events_ignored_and_foreign_session ________

self = <tests.test_realtime_reasoning.TestReworkUnits testMethod=test_service_events_ignored_and_foreign_session>

    def test_service_events_ignored_and_foreign_session(self) -> None:
        """RW-029/RW-031: служебные события — None, sessionID сохраняется в payload."""
        self.assertIsNone(
>           server._map_serve_event({"type": "integration.updated", "data": {}})  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
            ^^^^^^^^^^^^^^^^^^^^^^^
        )
E       AttributeError: module 'server' has no attribute '_map_serve_event'

tests/test_realtime_reasoning.py:1481: AttributeError
__________ TestReworkUnits.test_spawn_cap_and_proxy_rotation_helpers ___________

self = <tests.test_realtime_reasoning.TestReworkUnits testMethod=test_spawn_cap_and_proxy_rotation_helpers>

    def test_spawn_cap_and_proxy_rotation_helpers(self) -> None:
        """RW-001/RW-013: can_spawn ограничен MAX_TOTAL_SPAWNS, пул прокси ротируется."""
        res = server._Resilience()  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
        attempts = server._RequestAttempts(res, time.monotonic() + 60.0)  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
        for _i in range(server.MAX_TOTAL_SPAWNS):
>           self.assertTrue(attempts.can_spawn())
                            ^^^^^^^^^^^^^^^^^^
E           AttributeError: '_RequestAttempts' object has no attribute 'can_spawn'

tests/test_realtime_reasoning.py:1573: AttributeError
_____________ TestReworkUnits.test_surrogate_pair_and_broken_json ______________

self = <tests.test_realtime_reasoning.TestReworkUnits testMethod=test_surrogate_pair_and_broken_json>

    def test_surrogate_pair_and_broken_json(self) -> None:
        """RW-005: суррогатная пара декодируется, битый JSON serve — ServeProtocolError."""
>       parsed = server._loads_object('{"emoji": "\ud83d\ude00"}')  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
                 ^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute '_loads_object'. Did you mean: '_loads_lenient'?

tests/test_realtime_reasoning.py:1468: AttributeError
____________________ TestReworkUnits.test_transport_matrix _____________________

self = <tests.test_realtime_reasoning.TestReworkUnits testMethod=test_transport_matrix>

    def test_transport_matrix(self) -> None:
        """RW-025: TRANSPORT=run, override 0, disable-файл и опечатка дают run."""
        with mock.patch.dict(
            os.environ, {"OPENCODE_ZEN_BRIDGE_TRANSPORT": "run"}, clear=False
        ):
>           self.assertEqual(server._select_transport(), "run")  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
                             ^^^^^^^^^^^^^^^^^^^^^^^^
E           AttributeError: module 'server' has no attribute '_select_transport'

tests/test_realtime_reasoning.py:1524: AttributeError
____________ TestReworkUnits.test_whitespace_delta_preserved_in_map ____________

self = <tests.test_realtime_reasoning.TestReworkUnits testMethod=test_whitespace_delta_preserved_in_map>

    def test_whitespace_delta_preserved_in_map(self) -> None:
        """RW-007: пробельная дельта не отбрасывается маппером."""
>       mapped = server._map_serve_event(  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
                 ^^^^^^^^^^^^^^^^^^^^^^^
            {
                "type": "session.reasoning.delta",
                "data": {"sessionID": "s1", "delta": "\n\n"},
            }
        )
E       AttributeError: module 'server' has no attribute '_map_serve_event'

tests/test_realtime_reasoning.py:1496: AttributeError
_________ TestServeAttemptOracles.test_attempt_rotates_proxy_pool_once _________

self = <tests.test_realtime_reasoning.TestServeAttemptOracles testMethod=test_attempt_rotates_proxy_pool_once>

    @override
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmpdir.name)
        fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        self.saved_bin = server.OPENCODE_BIN
>       self.saved_lease = server.LEASE_DIR
                           ^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'LEASE_DIR'

tests/test_realtime_reasoning.py:1769: AttributeError
_ TestServeAttemptOracles.test_c5_fu002_prompt_401_headers_classified_before_hanging_body _

self = <tests.test_realtime_reasoning.TestServeAttemptOracles testMethod=test_c5_fu002_prompt_401_headers_classified_before_hanging_body>

    @override
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmpdir.name)
        fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        self.saved_bin = server.OPENCODE_BIN
>       self.saved_lease = server.LEASE_DIR
                           ^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'LEASE_DIR'

tests/test_realtime_reasoning.py:1769: AttributeError
_ TestServeAttemptOracles.test_c5_rw004_native_call_updates_last_token_at_no_premature_stall _

self = <tests.test_realtime_reasoning.TestServeAttemptOracles testMethod=test_c5_rw004_native_call_updates_last_token_at_no_premature_stall>

    @override
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmpdir.name)
        fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        self.saved_bin = server.OPENCODE_BIN
>       self.saved_lease = server.LEASE_DIR
                           ^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'LEASE_DIR'

tests/test_realtime_reasoning.py:1769: AttributeError
______ TestServeAttemptOracles.test_never_event_gives_first_event_timeout ______

self = <tests.test_realtime_reasoning.TestServeAttemptOracles testMethod=test_never_event_gives_first_event_timeout>

    @override
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmpdir.name)
        fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        self.saved_bin = server.OPENCODE_BIN
>       self.saved_lease = server.LEASE_DIR
                           ^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'LEASE_DIR'

tests/test_realtime_reasoning.py:1769: AttributeError
________ TestServeAttemptOracles.test_prompt_http_4xx_fails_closed_fast ________

self = <tests.test_realtime_reasoning.TestServeAttemptOracles testMethod=test_prompt_http_4xx_fails_closed_fast>

    @override
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmpdir.name)
        fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        self.saved_bin = server.OPENCODE_BIN
>       self.saved_lease = server.LEASE_DIR
                           ^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'LEASE_DIR'

tests/test_realtime_reasoning.py:1769: AttributeError
_____ TestServeAttemptOracles.test_silent_model_gives_first_token_timeout ______

self = <tests.test_realtime_reasoning.TestServeAttemptOracles testMethod=test_silent_model_gives_first_token_timeout>

    @override
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmpdir.name)
        fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        self.saved_bin = server.OPENCODE_BIN
>       self.saved_lease = server.LEASE_DIR
                           ^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'LEASE_DIR'

tests/test_realtime_reasoning.py:1769: AttributeError
__ TestServeAttemptOracles.test_sse_pause_over_half_second_keeps_stream_alive __

self = <tests.test_realtime_reasoning.TestServeAttemptOracles testMethod=test_sse_pause_over_half_second_keeps_stream_alive>

    @override
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmpdir.name)
        fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        self.saved_bin = server.OPENCODE_BIN
>       self.saved_lease = server.LEASE_DIR
                           ^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'LEASE_DIR'

tests/test_realtime_reasoning.py:1769: AttributeError
_____________ TestServeAttemptOracles.test_stall_after_first_token _____________

self = <tests.test_realtime_reasoning.TestServeAttemptOracles testMethod=test_stall_after_first_token>

    @override
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmpdir.name)
        fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        self.saved_bin = server.OPENCODE_BIN
>       self.saved_lease = server.LEASE_DIR
                           ^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'LEASE_DIR'

tests/test_realtime_reasoning.py:1769: AttributeError
__ TestServeAttemptOracles.test_startup_gate_released_before_generation_ends ___

self = <tests.test_realtime_reasoning.TestServeAttemptOracles testMethod=test_startup_gate_released_before_generation_ends>

    @override
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmpdir.name)
        fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        self.saved_bin = server.OPENCODE_BIN
>       self.saved_lease = server.LEASE_DIR
                           ^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'LEASE_DIR'

tests/test_realtime_reasoning.py:1769: AttributeError
____ TestServeAttemptOracles.test_text_tool_call_closes_step_on_step_finish ____

self = <tests.test_realtime_reasoning.TestServeAttemptOracles testMethod=test_text_tool_call_closes_step_on_step_finish>

    @override
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmpdir.name)
        fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        self.saved_bin = server.OPENCODE_BIN
>       self.saved_lease = server.LEASE_DIR
                           ^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'LEASE_DIR'

tests/test_realtime_reasoning.py:1769: AttributeError
___ TestSpawnAndLeaseOracles.test_client_gone_check_detects_reset_and_close ____

self = <tests.test_realtime_reasoning.TestSpawnAndLeaseOracles testMethod=test_client_gone_check_detects_reset_and_close>

    @override
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmpdir.name)
        fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        self.saved_bin = server.OPENCODE_BIN
>       self.saved_lease = server.LEASE_DIR
                           ^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'LEASE_DIR'

tests/test_realtime_reasoning.py:1769: AttributeError
_ TestSpawnAndLeaseOracles.test_lease_cleanup_confirms_sigkill_in_separate_window _

self = <tests.test_realtime_reasoning.TestSpawnAndLeaseOracles testMethod=test_lease_cleanup_confirms_sigkill_in_separate_window>

    @override
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmpdir.name)
        fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        self.saved_bin = server.OPENCODE_BIN
>       self.saved_lease = server.LEASE_DIR
                           ^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'LEASE_DIR'

tests/test_realtime_reasoning.py:1769: AttributeError
_______ TestSpawnAndLeaseOracles.test_spawn_failures_leave_no_leftovers ________

self = <tests.test_realtime_reasoning.TestSpawnAndLeaseOracles testMethod=test_spawn_failures_leave_no_leftovers>

    @override
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmpdir.name)
        fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        self.saved_bin = server.OPENCODE_BIN
>       self.saved_lease = server.LEASE_DIR
                           ^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'LEASE_DIR'

tests/test_realtime_reasoning.py:1769: AttributeError
__________ TestHelperProcess.test_errno_imported_before_helper_branch __________

self = <tests.test_realtime_reasoning.TestHelperProcess testMethod=test_errno_imported_before_helper_branch>

    def test_errno_imported_before_helper_branch(self) -> None:
        """RW-001: errno связан до ветки --serve-helper."""
        tree = ast.parse(Path(server.__file__).read_text("utf-8"))
>       branch = next(
            n
            for n in tree.body
            if isinstance(n, ast.If)
            and ast.unparse(n.test).endswith("['--serve-helper']")
        )
E       StopIteration

tests/test_realtime_reasoning.py:2065: StopIteration
__ TestHelperProcess.test_helper_kills_surviving_group_and_removes_lease_last __

self = <tests.test_realtime_reasoning.TestHelperProcess testMethod=test_helper_kills_surviving_group_and_removes_lease_last>

    def test_helper_kills_surviving_group_and_removes_lease_last(self) -> None:
        """RW-005: serve вышел, внук игнорирует SIGTERM -> SIGKILL группе, lease удалён после смерти."""
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            fake = _write_exe(tmp, "opencode-fake", FAKE_HELPER_SERVE)
            gc_file = tmp / "grandchild.pid"
            env = dict(os.environ)
            env["GRANDCHILD_FILE"] = str(gc_file)
            proc = subprocess.Popen(
                self._helper_cmd(tmp, str(fake)),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                text=True,
                start_new_session=True,
            )
            try:
                # lifeline (stdin) остаётся открытым: helper завершается сам, когда serve вышел.
                _ = proc.wait(timeout=30)
            finally:
                if proc.poll() is None:
                    proc.kill()
                if proc.stdin is not None:
                    proc.stdin.close()
                for stream in (proc.stdout, proc.stderr):
                    if stream is not None:
                        stream.close()
>           self.assertEqual(proc.returncode, 0)
E           AssertionError: 2 != 0

tests/test_realtime_reasoning.py:2123: AssertionError
_____ TestHelperProcess.test_helper_survives_bad_stdin_without_name_error ______

self = <tests.test_realtime_reasoning.TestHelperProcess testMethod=test_helper_survives_bad_stdin_without_name_error>

    def test_helper_survives_bad_stdin_without_name_error(self) -> None:
        """RW-001: EBADF на select lifeline обрабатывается без NameError, lease снимается."""
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            argv = " ".join(f"'{a}'" for a in self._helper_cmd(tmp, "/bin/true"))
            proc = subprocess.run(
                ["/bin/sh", "-c", f"exec {argv} <&-"],
                capture_output=True,
                text=True,
                timeout=20,
                start_new_session=True,
            )
            self.assertNotIn("NameError", proc.stderr)
>           self.assertEqual(proc.returncode, 0, proc.stderr)
E           AssertionError: 2 != 0 : OPENCODE_ZEN_BRIDGE_KEY is required; refusing to start

tests/test_realtime_reasoning.py:2092: AssertionError
=========================== short test summary info ============================
FAILED tests/test_realtime_reasoning.py::TestLegacyWatchdogAndKillpg::test_c5_rw002_limiter_delay_half_second_still_emits_first_status_under_1s
SUBFAILED(branch='watchdog', effort='high') tests/test_realtime_reasoning.py::TestLegacyWatchdogAndKillpg::test_c5_rw003_legacy_retry_separator_all_branches_and_thinking_gate
SUBFAILED(branch='watchdog', effort='off') tests/test_realtime_reasoning.py::TestLegacyWatchdogAndKillpg::test_c5_rw003_legacy_retry_separator_all_branches_and_thinking_gate
SUBFAILED(branch='unmapped', effort='high') tests/test_realtime_reasoning.py::TestLegacyWatchdogAndKillpg::test_c5_rw003_legacy_retry_separator_all_branches_and_thinking_gate
SUBFAILED(branch='unmapped', effort='off') tests/test_realtime_reasoning.py::TestLegacyWatchdogAndKillpg::test_c5_rw003_legacy_retry_separator_all_branches_and_thinking_gate
SUBFAILED(branch='incomplete', effort='high') tests/test_realtime_reasoning.py::TestLegacyWatchdogAndKillpg::test_c5_rw003_legacy_retry_separator_all_branches_and_thinking_gate
SUBFAILED(branch='incomplete', effort='off') tests/test_realtime_reasoning.py::TestLegacyWatchdogAndKillpg::test_c5_rw003_legacy_retry_separator_all_branches_and_thinking_gate
FAILED tests/test_realtime_reasoning.py::TestLegacyWatchdogAndKillpg::test_initial_status_before_1s_under_startup_gate_contention
FAILED tests/test_realtime_reasoning.py::TestLegacyWatchdogAndKillpg::test_oexit_fields_present
FAILED tests/test_realtime_reasoning.py::TestLegacyWatchdogAndKillpg::test_rw002_initial_status_while_waiting_spawn_limiter
FAILED tests/test_realtime_reasoning.py::TestLegacyWatchdogAndKillpg::test_slow_upstream_gets_initial_status_before_1s
FAILED tests/test_realtime_reasoning.py::TestLegacyWatchdogAndKillpg::test_watchdog_first_event_timeout
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_ac026_realtime_chunks_before_upstream_end
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_auto_fallback_to_run_and_sticky_degradation
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_c5_fu003_json_transient_recovery_normalizes_and_deduplicates
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_c5_rw001_prompt_headers_then_body_error_or_429_blocks_run_fallback
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_canonical_frozen_fixtures
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_clean_room_fake_serve_via_monkeypatched_bin
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_dynamic_config_switch_same_server
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_foreign_listener_rejected_and_startup_reaper
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_form_missing_title_cancels_without_step2
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_fu003_usage_once_across_distinct_retry_branches
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_fu010_thinking_off_omits_retry_separator
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_fu011_cancelled_never_counts_as_success
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_helper_argv_validation_and_lease_dir
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_helper_drains_large_stderr
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_json_run_fallback_respects_total_spawn_cap
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_json_tool_calls_are_deduplicated
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_native_tool_and_permission_reject
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_prompt_http_4xx_fail_closed_without_run_fallback
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_proxy_pool_advances_once_per_serve_attempt
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_retry_separator_once_and_delivery_barrier_is_monotonic
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_rw001_delivery_survives_unavailable_or_limiter
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_rw003_mkdtemp_failure_is_serve_unavailable
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_rw006_invalid_utf8_falls_back_and_recovers
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_rw007_split_interrupted_marker_at_every_boundary
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_rw008_provider_secrets_hidden_in_sse_json_and_log
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_serve_400_fails_closed_without_health_increment
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_serve_env_sanitized_all_branches
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_serve_health_and_fallback_table
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_slow_pause_streams_all_deltas_and_single_initial_status
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_slow_serve_gets_status_and_no_status_on_fast
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_timeout_and_client_gone_never_count_as_success
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_tool_choice_preserved_in_step_recovery_prompt
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_tool_text_split_across_deltas
FAILED tests/test_realtime_reasoning.py::TestReworkUnits::test_disable_file_overrides_forced_serve
FAILED tests/test_realtime_reasoning.py::TestReworkUnits::test_elf_magic_and_tool_status
FAILED tests/test_realtime_reasoning.py::TestReworkUnits::test_fu001_http_checks_deadline_and_cancellation_before_connect
SUBFAILED(name='bash') tests/test_realtime_reasoning.py::TestReworkUnits::test_rw004_native_calls_share_canonical_mapping
SUBFAILED(name='read') tests/test_realtime_reasoning.py::TestReworkUnits::test_rw004_native_calls_share_canonical_mapping
SUBFAILED(name='edit') tests/test_realtime_reasoning.py::TestReworkUnits::test_rw004_native_calls_share_canonical_mapping
SUBFAILED(name='list') tests/test_realtime_reasoning.py::TestReworkUnits::test_rw004_native_calls_share_canonical_mapping
SUBFAILED(name='multiedit') tests/test_realtime_reasoning.py::TestReworkUnits::test_rw004_native_calls_share_canonical_mapping
FAILED tests/test_realtime_reasoning.py::TestReworkUnits::test_rw005_stop_group_after_leader_exit
FAILED tests/test_realtime_reasoning.py::TestReworkUnits::test_rw008_error_payload_masks_message_and_detail
FAILED tests/test_realtime_reasoning.py::TestReworkUnits::test_service_events_ignored_and_foreign_session
FAILED tests/test_realtime_reasoning.py::TestReworkUnits::test_spawn_cap_and_proxy_rotation_helpers
FAILED tests/test_realtime_reasoning.py::TestReworkUnits::test_surrogate_pair_and_broken_json
FAILED tests/test_realtime_reasoning.py::TestReworkUnits::test_transport_matrix
FAILED tests/test_realtime_reasoning.py::TestReworkUnits::test_whitespace_delta_preserved_in_map
FAILED tests/test_realtime_reasoning.py::TestServeAttemptOracles::test_attempt_rotates_proxy_pool_once
FAILED tests/test_realtime_reasoning.py::TestServeAttemptOracles::test_c5_fu002_prompt_401_headers_classified_before_hanging_body
FAILED tests/test_realtime_reasoning.py::TestServeAttemptOracles::test_c5_rw004_native_call_updates_last_token_at_no_premature_stall
FAILED tests/test_realtime_reasoning.py::TestServeAttemptOracles::test_never_event_gives_first_event_timeout
FAILED tests/test_realtime_reasoning.py::TestServeAttemptOracles::test_prompt_http_4xx_fails_closed_fast
FAILED tests/test_realtime_reasoning.py::TestServeAttemptOracles::test_silent_model_gives_first_token_timeout
FAILED tests/test_realtime_reasoning.py::TestServeAttemptOracles::test_sse_pause_over_half_second_keeps_stream_alive
FAILED tests/test_realtime_reasoning.py::TestServeAttemptOracles::test_stall_after_first_token
FAILED tests/test_realtime_reasoning.py::TestServeAttemptOracles::test_startup_gate_released_before_generation_ends
FAILED tests/test_realtime_reasoning.py::TestServeAttemptOracles::test_text_tool_call_closes_step_on_step_finish
FAILED tests/test_realtime_reasoning.py::TestSpawnAndLeaseOracles::test_client_gone_check_detects_reset_and_close
FAILED tests/test_realtime_reasoning.py::TestSpawnAndLeaseOracles::test_lease_cleanup_confirms_sigkill_in_separate_window
FAILED tests/test_realtime_reasoning.py::TestSpawnAndLeaseOracles::test_spawn_failures_leave_no_leftovers
FAILED tests/test_realtime_reasoning.py::TestHelperProcess::test_errno_imported_before_helper_branch
FAILED tests/test_realtime_reasoning.py::TestHelperProcess::test_helper_kills_surviving_group_and_removes_lease_last
FAILED tests/test_realtime_reasoning.py::TestHelperProcess::test_helper_survives_bad_stdin_without_name_error
76 failed, 7 passed in 18.03s

--- STDERR ---
```

### `VER-004-packet-command` (`l2-green-ver004-packet.log`, `sha256=153c06e3f5e23c7756f62a109e02d3ebdc5500eb80fbfb2ffe7dedb019b93bf1`)
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
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom] [rc=0] [wall=22.41s]
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
BASEDPYRIGHT summary {'filesAnalyzed': 3, 'errorCount': 0, 'warningCount': 760, 'informationCount': 0, 'timeInSec': 3.944}
SERVER dict(counts) {'reportExplicitAny': 123, 'reportAny': 117, 'reportUnusedCallResult': 35, 'reportUnknownMemberType': 72, 'reportUnknownVariableType': 56, 'reportUnknownArgumentType': 48, 'reportUnusedFunction': 2, 'reportImplicitStringConcatenation': 27, 'reportUnannotatedClassAttribute': 98, 'reportUnusedParameter': 3, 'reportUnnecessaryIsInstance': 4, 'reportUnknownParameterType': 2, 'reportMissingParameterType': 2, 'reportUnreachable': 1, 'reportImplicitOverride': 1}
SERVER warningCount 591
PASS VER-004: all3 lint/type; legacy changed-range format; newfile whole format; server counts {'reportExplicitAny': 123, 'reportAny': 117, 'reportUnusedCallResult': 35, 'reportUnknownMemberType': 72, 'reportUnknownVariableType': 56, 'reportUnknownArgumentType': 48, 'reportUnusedFunction': 2, 'reportImplicitStringConcatenation': 27, 'reportUnannotatedClassAttribute': 98, 'reportUnusedParameter': 3, 'reportUnnecessaryIsInstance': 4, 'reportUnknownParameterType': 2, 'reportMissingParameterType': 2, 'reportUnreachable': 1, 'reportImplicitOverride': 1}

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
Ran 8 tests in 0.185s

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

### `VER-001-pytest` (`l2-green-ver001-pytest.log`, `sha256=6d9590a036bc6663f658849946706267a71b20258ca5d0d4b33b793eacdf9798`)
```text
$ uvx pytest -q -p no:cacheprovider tests/
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=212.92s]
--- STDOUT ---
......................... [  5%]
............................................................................................................................................... [ 37%]
............................................................................................................ [ 61%]
.................................................................... [ 76%]
........................................................ [ 88%]
...................................................                         [100%]
451 passed, 3197 subtests passed in 212.45s (0:03:32)

--- STDERR ---
```

### `VER-002-unittest` (`l2-green-ver002-unittest.log`, `sha256=42b7fc5b435d91162cc18866c672fff4d58d95ce4119c28fb721dbb1061dcd60`)
```text
$ python3 -m unittest discover -s tests -p test_*.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=205.11s]
--- STDOUT ---

--- STDERR ---
..........2026-10-27 07:13:46 http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-27 07:13:46 O-EXIT/v1 mode=json model=jev-1.13 status=400 exit_reason=bad_request rc=None total_spawns=0 retries=0 signal=0 tools=0 out_chars=0 transport=none first_event_ms=None ttft_ms=None transport_history=[] duration_s=0.00
2026-10-27 07:13:47 http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-27 07:13:47 O-EXIT/v1 mode=json model=jev-1.13-free status=400 exit_reason=bad_request rc=None total_spawns=0 retries=0 signal=0 tools=0 out_chars=0 transport=none first_event_ms=None ttft_ms=None transport_history=[] duration_s=0.00
2026-10-27 07:13:47 http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-27 07:13:47 O-EXIT/v1 mode=json model=nemotron-3-ultra-free status=400 exit_reason=bad_request rc=None total_spawns=0 retries=0 signal=0 tools=0 out_chars=0 transport=none first_event_ms=None ttft_ms=None transport_history=[] duration_s=0.00
2026-10-27 07:13:47 http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-27 07:13:47 O-EXIT/v1 mode=json model=test status=400 exit_reason=bad_request rc=None total_spawns=0 retries=0 signal=0 tools=0 out_chars=0 transport=none first_event_ms=None ttft_ms=None transport_history=[] duration_s=0.00
2026-10-27 07:13:47 http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-27 07:13:47 O-EXIT/v1 mode=json model=claude-opus-5-5-backup status=400 exit_reason=bad_request rc=None total_spawns=0 retries=0 signal=0 tools=0 out_chars=0 transport=none first_event_ms=None ttft_ms=None transport_history=[] duration_s=0.00
2026-10-27 07:13:47 http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-27 07:13:47 O-EXIT/v1 mode=json model=deepseek-v4.1-flash status=400 exit_reason=bad_request rc=None total_spawns=0 retries=0 signal=0 tools=0 out_chars=0 transport=none first_event_ms=None ttft_ms=None transport_history=[] duration_s=0.00
2026-10-27 07:13:47 http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-27 07:13:47 O-EXIT/v1 mode=json model=claude-haiku-5-5 status=400 exit_reason=bad_request rc=None total_spawns=0 retries=0 signal=0 tools=0 out_chars=0 transport=none first_event_ms=None ttft_ms=None transport_history=[] duration_s=0.00
.2026-10-27 07:13:47 http "GET /health HTTP/1.1" 200 -
.2026-10-27 07:13:47 http "GET /v1/models HTTP/1.1" 200 -
.2026-10-27 07:13:47 http "GET /v1/models HTTP/1.1" 401 -
........................2026-10-27 07:13:49 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=32 cwd=/var/folders/2f/***/T/tmpz7smejs5/ws
2026-10-27 07:13:49 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:13:49 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=7 emulate_tools=False retries=0 total_spawns=1
2026-10-27 07:13:49 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=7 transport=run first_event_ms=112 ttft_ms=112 transport_history=['run'] duration_s=0.37
.2026-10-27 07:13:49 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=32 cwd=/var/folders/2f/***/T/tmpz7smejs5/ws
2026-10-27 07:13:50 exec cli failed rc=1 state=nonzero_exit stderr_tail='Error: Unexpected error\ndatabase is locked'
2026-10-27 07:13:50 exec failed rc=1 without output, retry 1/2 total_spawns=1/3: 'Error: Unexpected error\ndatabase is locked'
2026-10-27 07:13:50 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=32 cwd=/var/folders/2f/***/T/tmpz7smejs5/ws
2026-10-27 07:13:51 done model=muse-spark-1.3-contributor-free rc=0 state=ok tools=0 out_chars=7 retries=0 total_spawns=2
2026-10-27 07:13:51 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:13:51 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=2 retries=1 signal=0 tools=0 out_chars=7 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=1.93
.2026-10-27 07:13:51 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=32 cwd=/var/folders/2f/***/T/tmpz7smejs5/ws
2026-10-27 07:13:52 exec: early provider error (waiting for CLI recovery)
2026-10-27 07:13:52 exec cli failed rc=1 state=provider_error stderr_tail='HTTP 429: FreeUsageLimitError'
2026-10-27 07:13:52 exec failed rc=1 without output, retry 1/2 total_spawns=1/3: 'HTTP 429: FreeUsageLimitError'
2026-10-27 07:13:52 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=32 cwd=/var/folders/2f/***/T/tmpz7smejs5/ws
2026-10-27 07:13:53 exec: early provider error (waiting for CLI recovery)
2026-10-27 07:13:53 exec cli failed rc=1 state=provider_error stderr_tail='HTTP 429: FreeUsageLimitError'
2026-10-27 07:13:53 exec failed rc=1 without output, retry 2/2 total_spawns=2/3: 'HTTP 429: FreeUsageLimitError'
2026-10-27 07:13:53 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=32 cwd=/var/folders/2f/***/T/tmpz7smejs5/ws
2026-10-27 07:13:54 exec: early provider error (waiting for CLI recovery)
2026-10-27 07:13:54 exec cli failed rc=1 state=provider_error stderr_tail='HTTP 429: FreeUsageLimitError'
2026-10-27 07:13:54 http "POST /v1/chat/completions HTTP/1.1" 502 -
2026-10-27 07:13:54 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=502 exit_reason=upstream_failed rc=None total_spawns=3 retries=2 signal=0 tools=0 out_chars=0 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=2.99
.2026-10-27 07:13:54 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=32 cwd=/var/folders/2f/***/T/tmpz7smejs5/ws
2026-10-27 07:13:55 exec cli failed rc=1 state=nonzero_exit stderr_tail='Error: fatal boom xyz'
2026-10-27 07:13:55 exec failed rc=1 without output, retry 1/2 total_spawns=1/3: 'Error: fatal boom xyz'
2026-10-27 07:13:55 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=32 cwd=/var/folders/2f/***/T/tmpz7smejs5/ws
2026-10-27 07:13:56 exec cli failed rc=1 state=nonzero_exit stderr_tail='Error: fatal boom xyz'
2026-10-27 07:13:56 exec failed rc=1 without output, retry 2/2 total_spawns=2/3: 'Error: fatal boom xyz'
2026-10-27 07:13:56 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=32 cwd=/var/folders/2f/***/T/tmpz7smejs5/ws
2026-10-27 07:13:57 exec cli failed rc=1 state=nonzero_exit stderr_tail='Error: fatal boom xyz'
2026-10-27 07:13:57 http "POST /v1/chat/completions HTTP/1.1" 502 -
2026-10-27 07:13:57 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=502 exit_reason=upstream_failed rc=None total_spawns=3 retries=2 signal=0 tools=0 out_chars=0 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=2.98
.2026-10-27 07:13:57 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=32 cwd=/var/folders/2f/***/T/tmpz7smejs5/ws
2026-10-27 07:13:57 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:13:58 stream provider error: HTTP 403: free tier denied
2026-10-27 07:13:58 stream: early provider error (waiting for CLI recovery)
2026-10-27 07:13:58 stream cli failed rc=1 stderr_tail='HTTP 403: free tier denied'
2026-10-27 07:13:58 stream failed model=muse-spark-1.3-contributor-free rc=1 fail_retries=0 total_spawns=1
2026-10-27 07:13:58 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=upstream_failed rc=None total_spawns=1 retries=0 signal=0 tools=0 out_chars=0 transport=run first_event_ms=766 ttft_ms=None transport_history=['run'] duration_s=1.02
..2026-10-27 07:13:58 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free --standalone prompt_chars=8 cwd=/var/folders/2f/***/T/tmpz7smejs5/ws
2026-10-27 07:13:59 exec timeout after 1s, killing proc group
/private/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge/tests/test_cli_failure.py:267: ResourceWarning: unclosed file <_io.TextIOWrapper name=9 encoding='utf-8'>
  out = server.Run("muse-spark-1.3-contributor-free", "Проверка", "", Path(self.tmp.name) / "ws")._execute_once()
ResourceWarning: Enable tracemalloc to get the object allocation traceback
/private/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge/tests/test_cli_failure.py:267: ResourceWarning: unclosed file <_io.TextIOWrapper name=7 encoding='utf-8'>
  out = server.Run("muse-spark-1.3-contributor-free", "Проверка", "", Path(self.tmp.name) / "ws")._execute_once()
ResourceWarning: Enable tracemalloc to get the object allocation traceback
.2026-10-27 07:13:59 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=32 cwd=/var/folders/2f/***/T/tmpz7smejs5/ws
2026-10-27 07:13:59 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:13:59 stream cli failed rc=1 stderr_tail='Error: Unexpected error\ndatabase is locked'
2026-10-27 07:13:59 stream retry 1/2 after cli failure without output
2026-10-27 07:13:59 stream exec retry=0 fail_retries=1 model=opencode/muse-spark-1.3-contributor-free prompt_chars=32 total_spawns=1/3
2026-10-27 07:14:00 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=7 emulate_tools=False retries=0 total_spawns=2
2026-10-27 07:14:00 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=2 retries=1 signal=0 tools=0 out_chars=7 transport=run first_event_ms=1046 ttft_ms=1046 transport_history=['run'] duration_s=1.30
.2026-10-27 07:14:00 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=32 cwd=/var/folders/2f/***/T/tmpz7smejs5/ws
2026-10-27 07:14:00 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:14:01 stream cli failed rc=1 stderr_tail='Error: fatal boom xyz'
2026-10-27 07:14:01 stream retry 1/2 after cli failure without output
2026-10-27 07:14:01 stream exec retry=0 fail_retries=1 model=opencode/muse-spark-1.3-contributor-free prompt_chars=32 total_spawns=1/3
2026-10-27 07:14:02 stream cli failed rc=1 stderr_tail='Error: fatal boom xyz'
2026-10-27 07:14:02 stream retry 2/2 after cli failure without output
2026-10-27 07:14:02 stream exec retry=0 fail_retries=2 model=opencode/muse-spark-1.3-contributor-free prompt_chars=32 total_spawns=2/3
2026-10-27 07:14:03 stream cli failed rc=1 stderr_tail='Error: fatal boom xyz'
2026-10-27 07:14:03 stream failed model=muse-spark-1.3-contributor-free rc=1 fail_retries=2 total_spawns=3
2026-10-27 07:14:03 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=upstream_failed rc=None total_spawns=3 retries=2 signal=0 tools=0 out_chars=0 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=2.97
.2026-10-27 07:14:03 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=32 cwd=/var/folders/2f/***/T/tmpz7smejs5/ws
2026-10-27 07:14:03 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:14:04 stream cli failed rc=1 stderr_tail='Error: Unexpected error\ndatabase is locked'
2026-10-27 07:14:04 stream retry 1/2 after cli failure without output
2026-10-27 07:14:04 stream exec retry=0 fail_retries=1 model=opencode/muse-spark-1.3-contributor-free prompt_chars=32 total_spawns=1/3
2026-10-27 07:14:05 stream cli failed rc=1 stderr_tail='Error: Unexpected error\ndatabase is locked'
2026-10-27 07:14:05 stream retry 2/2 after cli failure without output
2026-10-27 07:14:05 stream exec retry=0 fail_retries=2 model=opencode/muse-spark-1.3-contributor-free prompt_chars=32 total_spawns=2/3
2026-10-27 07:14:06 stream cli failed rc=1 stderr_tail='Error: Unexpected error\ndatabase is locked'
2026-10-27 07:14:06 stream failed model=muse-spark-1.3-contributor-free rc=1 fail_retries=2 total_spawns=3
2026-10-27 07:14:06 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=upstream_failed rc=None total_spawns=3 retries=2 signal=0 tools=0 out_chars=0 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=3.00
.2026-10-27 07:14:06 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=32 cwd=/var/folders/2f/***/T/tmpz7smejs5/ws
2026-10-27 07:14:06 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:14:07 stream provider error: HTTP 429: FreeUsageLimitError
2026-10-27 07:14:07 stream: early provider error (waiting for CLI recovery)
2026-10-27 07:14:07 stream cli failed rc=1 stderr_tail='HTTP 429: FreeUsageLimitError'
2026-10-27 07:14:07 stream retry 1/2 after cli failure without output
2026-10-27 07:14:07 stream exec retry=0 fail_retries=1 model=opencode/muse-spark-1.3-contributor-free prompt_chars=32 total_spawns=1/3
2026-10-27 07:14:08 stream provider error: HTTP 429: FreeUsageLimitError
2026-10-27 07:14:08 stream: early provider error (waiting for CLI recovery)
2026-10-27 07:14:08 stream cli failed rc=1 stderr_tail='HTTP 429: FreeUsageLimitError'
2026-10-27 07:14:08 stream retry 2/2 after cli failure without output
2026-10-27 07:14:08 stream exec retry=0 fail_retries=2 model=opencode/muse-spark-1.3-contributor-free prompt_chars=32 total_spawns=2/3
2026-10-27 07:14:09 stream provider error: HTTP 429: FreeUsageLimitError
2026-10-27 07:14:09 stream: early provider error (waiting for CLI recovery)
2026-10-27 07:14:09 stream cli failed rc=1 stderr_tail='HTTP 429: FreeUsageLimitError'
2026-10-27 07:14:09 stream failed model=muse-spark-1.3-contributor-free rc=1 fail_retries=2 total_spawns=3
2026-10-27 07:14:09 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=upstream_failed rc=None total_spawns=3 retries=2 signal=0 tools=0 out_chars=0 transport=run first_event_ms=738 ttft_ms=None transport_history=['run'] duration_s=3.02
.2026-10-27 07:14:09 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=32 cwd=/var/folders/2f/***/T/tmpz7smejs5/ws
2026-10-27 07:14:09 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:14:10 stream cli failed rc=1 stderr_tail='Error: fatal boom xyz'
2026-10-27 07:14:10 stream retry 1/2 after cli failure without output
2026-10-27 07:14:10 stream exec retry=0 fail_retries=1 model=opencode/muse-spark-1.3-contributor-free prompt_chars=32 total_spawns=1/3
2026-10-27 07:14:11 stream cli failed rc=1 stderr_tail='Error: fatal boom xyz'
2026-10-27 07:14:11 stream retry 2/2 after cli failure without output
2026-10-27 07:14:11 stream exec retry=0 fail_retries=2 model=opencode/muse-spark-1.3-contributor-free prompt_chars=32 total_spawns=2/3
2026-10-27 07:14:12 stream cli failed rc=1 stderr_tail='Error: fatal boom xyz'
2026-10-27 07:14:12 stream failed model=muse-spark-1.3-contributor-free rc=1 fail_retries=2 total_spawns=3
2026-10-27 07:14:12 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=upstream_failed rc=None total_spawns=3 retries=2 signal=0 tools=0 out_chars=0 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=2.97
.2026-10-27 07:14:12 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=32 cwd=/var/folders/2f/***/T/tmpz7smejs5/ws
2026-10-27 07:14:12 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:14:14 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=7 emulate_tools=False retries=0 total_spawns=1
2026-10-27 07:14:14 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=7 transport=run first_event_ms=1153 ttft_ms=1153 transport_history=['run'] duration_s=1.41
.2026-10-27 07:14:14 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=32 cwd=/var/folders/2f/***/T/tmpz7smejs5/ws
2026-10-27 07:14:14 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:14:15 stream timeout after 1s, killing proc group
2026-10-27 07:14:15 stream failed model=muse-spark-1.3-contributor-free rc=-15 fail_retries=0 total_spawns=1
2026-10-27 07:14:15 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=timeout rc=None total_spawns=1 retries=0 signal=0 tools=0 out_chars=0 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=1.02
...............................................................................2026-10-27 07:14:23 tool_call_recovered extra_braces=1
.2026-10-27 07:14:23 tool_call_recovered extra_braces=1
.2026-10-27 07:14:23 tool_call_recovered extra_braces=1
2026-10-27 07:14:23 tool_call_recovered extra_braces=1
2026-10-27 07:14:23 tool_call_recovered extra_braces=1
2026-10-27 07:14:23 tool_call_recovered extra_braces=1
..2026-10-27 07:14:23 tool_call_recovered extra_braces=1
2026-10-27 07:14:23 tool_call_recovered extra_braces=1
2026-10-27 07:14:23 tool_call_recovered extra_braces=2
2026-10-27 07:14:23 tool_call_recovered extra_braces=2
2026-10-27 07:14:23 tool_call_recovered extra_braces=3
2026-10-27 07:14:23 tool_call_recovered extra_braces=3
2026-10-27 07:14:23 tool_call_recovered extra_braces=3
2026-10-27 07:14:23 tool_call_recovered extra_braces=3
2026-10-27 07:14:23 tool_call_recovered extra_braces=16
2026-10-27 07:14:23 tool_call_recovered extra_braces=16
............2026-10-27 07:14:23 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=13385 cwd=/var/folders/2f/***/T/tmp5hlrtp55/ws
2026-10-27 07:14:23 opencode built-in tool event: tool=todoread status=error mapped=False as=[]
2026-10-27 07:14:24 unmapped built-in tools=['todoread']: re-prompt 1/2
2026-10-27 07:14:24 exec retry=1 (unmapped built-in tool) total_spawns=1/3
2026-10-27 07:14:24 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=14047 cwd=/var/folders/2f/***/T/tmp5hlrtp55/ws
2026-10-27 07:14:24 exec: step with tool call finished, stopping opencode run
2026-10-27 07:14:24 opencode built-in tool event: tool=bash status=error mapped=True as=['bash']
2026-10-27 07:14:24 done model=muse-spark-1.3-contributor-free rc=-15 state=nonzero_exit tools=1 out_chars=15 retries=1 total_spawns=2
2026-10-27 07:14:24 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:14:24 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=-15 total_spawns=2 retries=1 signal=0 tools=1 out_chars=15 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=1.21
.2026-10-27 07:14:24 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=13385 cwd=/var/folders/2f/***/T/tmp5hlrtp55/ws
2026-10-27 07:14:25 exec: step with tool call finished, stopping opencode run
2026-10-27 07:14:25 opencode built-in tool event: tool=read status=error mapped=True as=['read']
2026-10-27 07:14:25 opencode built-in tool event: tool=todowrite status=error mapped=True as=['todo_write']
2026-10-27 07:14:25 opencode built-in tool event: tool=todowrite status=error mapped=True as=['todo_write']
2026-10-27 07:14:25 dropped duplicate tool call todo_write
2026-10-27 07:14:25 done model=muse-spark-1.3-contributor-free rc=-15 state=nonzero_exit tools=2 out_chars=0 retries=0 total_spawns=1
2026-10-27 07:14:25 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:14:25 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=-15 total_spawns=1 retries=0 signal=0 tools=2 out_chars=0 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=1.01
.2026-10-27 07:14:25 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=13385 cwd=/var/folders/2f/***/T/tmp5hlrtp55/ws
2026-10-27 07:14:25 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:14:26 opencode built-in tool event: tool=todoread status=error mapped=False as=[]
2026-10-27 07:14:27 stream unmapped built-in tools=['todoread']: re-prompt 1/2
2026-10-27 07:14:27 stream exec retry=1 fail_retries=0 model=opencode/muse-spark-1.3-contributor-free prompt_chars=14047 total_spawns=1/3
2026-10-27 07:14:27 opencode built-in tool event: tool=bash status=error mapped=True as=['bash']
2026-10-27 07:14:27 stream: step with tool call finished, stopping opencode run
2026-10-27 07:14:27 stream done model=muse-spark-1.3-contributor-free rc=-15 tools=1 out_chars=15 emulate_tools=True retries=1 total_spawns=2
2026-10-27 07:14:27 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=-15 total_spawns=2 retries=1 signal=0 tools=1 out_chars=15 transport=run first_event_ms=992 ttft_ms=992 transport_history=['run'] duration_s=2.00
.2026-10-27 07:14:27 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=13385 cwd=/var/folders/2f/***/T/tmp5hlrtp55/ws
2026-10-27 07:14:27 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:14:28 opencode built-in tool event: tool=read status=error mapped=True as=['read']
2026-10-27 07:14:28 opencode built-in tool event: tool=todowrite status=error mapped=True as=['todo_write']
2026-10-27 07:14:28 opencode built-in tool event: tool=todowrite status=error mapped=True as=['todo_write']
2026-10-27 07:14:28 stream dropped duplicate tool call todo_write
2026-10-27 07:14:28 stream: step with tool call finished, stopping opencode run
2026-10-27 07:14:28 stream done model=muse-spark-1.3-contributor-free rc=-15 tools=2 out_chars=0 emulate_tools=True retries=0 total_spawns=1
2026-10-27 07:14:28 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=-15 total_spawns=1 retries=0 signal=0 tools=2 out_chars=0 transport=run first_event_ms=994 ttft_ms=None transport_history=['run'] duration_s=1.00
....2026-10-27 07:14:32 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1023 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 07:14:32 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:14:35 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=6 emulate_tools=True retries=0 total_spawns=1
2026-10-27 07:14:35 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=6 transport=run first_event_ms=2327 ttft_ms=2327 transport_history=['run'] duration_s=2.58
.2026-10-27 07:14:35 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1033 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 07:14:35 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:14:36 stream exec retry=0 fail_retries=0 model=opencode/muse-spark-1.3-contributor-free prompt_chars=1033 total_spawns=1/3
2026-10-27 07:14:37 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=5 emulate_tools=True retries=0 total_spawns=2
2026-10-27 07:14:37 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=2 retries=1 signal=0 tools=0 out_chars=5 transport=run first_event_ms=215 ttft_ms=215 transport_history=['run'] duration_s=1.30
2026-10-27 07:14:37 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free --standalone prompt_chars=1033 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 07:14:37 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:14:38 stream exec retry=0 fail_retries=0 model=opencode/muse-spark-1.3-contributor-free prompt_chars=1033 total_spawns=1/3
2026-10-27 07:14:39 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=5 emulate_tools=True retries=0 total_spawns=2
2026-10-27 07:14:39 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=2 retries=1 signal=0 tools=0 out_chars=5 transport=run first_event_ms=735 ttft_ms=735 transport_history=['run'] duration_s=2.00
2026-10-27 07:14:39 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1033 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 07:14:39 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:14:40 opencode built-in tool event: tool=todoread status=error mapped=False as=[]
2026-10-27 07:14:40 stream unmapped built-in tools=['todoread']: re-prompt 1/2
2026-10-27 07:14:40 stream exec retry=1 fail_retries=0 model=opencode/muse-spark-1.3-contributor-free prompt_chars=1520 total_spawns=1/3
2026-10-27 07:14:41 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=5 emulate_tools=True retries=1 total_spawns=2
2026-10-27 07:14:41 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=2 retries=1 signal=0 tools=0 out_chars=5 transport=run first_event_ms=741 ttft_ms=741 transport_history=['run'] duration_s=1.98
2026-10-27 07:14:41 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free --standalone prompt_chars=1033 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 07:14:41 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:14:42 opencode built-in tool event: tool=todoread status=error mapped=False as=[]
2026-10-27 07:14:42 stream unmapped built-in tools=['todoread']: re-prompt 1/2
2026-10-27 07:14:42 stream exec retry=1 fail_retries=0 model=opencode/muse-spark-1.3-contributor-free prompt_chars=1520 total_spawns=1/3
2026-10-27 07:14:43 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=5 emulate_tools=True retries=1 total_spawns=2
2026-10-27 07:14:43 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=2 retries=1 signal=0 tools=0 out_chars=5 transport=run first_event_ms=759 ttft_ms=759 transport_history=['run'] duration_s=2.02
2026-10-27 07:14:43 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1033 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 07:14:43 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:14:44 stream dropped 1 unparsed tool block(s) from content
2026-10-27 07:14:44 stream incomplete tool step: re-prompt 1/2 signal=2 total_spawns=1/3
2026-10-27 07:14:44 stream exec retry=1 fail_retries=0 model=opencode/muse-spark-1.3-contributor-free prompt_chars=1596 total_spawns=1/3
2026-10-27 07:14:45 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=22 emulate_tools=True retries=1 total_spawns=2
2026-10-27 07:14:45 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=2 retries=1 signal=2 tools=0 out_chars=22 transport=run first_event_ms=726 ttft_ms=726 transport_history=['run'] duration_s=1.99
2026-10-27 07:14:45 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free --standalone prompt_chars=1033 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 07:14:45 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:14:46 stream dropped 1 unparsed tool block(s) from content
2026-10-27 07:14:46 stream incomplete tool step: re-prompt 1/2 signal=2 total_spawns=1/3
2026-10-27 07:14:46 stream exec retry=1 fail_retries=0 model=opencode/muse-spark-1.3-contributor-free prompt_chars=1596 total_spawns=1/3
2026-10-27 07:14:47 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=22 emulate_tools=True retries=1 total_spawns=2
2026-10-27 07:14:47 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=2 retries=1 signal=2 tools=0 out_chars=22 transport=run first_event_ms=736 ttft_ms=736 transport_history=['run'] duration_s=1.99
.2026-10-27 07:14:47 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1026 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 07:14:47 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:14:47 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=7 emulate_tools=True retries=0 total_spawns=1
2026-10-27 07:14:47 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=7 transport=run first_event_ms=126 ttft_ms=126 transport_history=['run'] duration_s=0.38
..2026-10-27 07:14:48 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1026 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 07:14:48 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:14:50 startup_gate_timeout wait_s=2.5, starting without the gate
2026-10-27 07:14:51 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=7 emulate_tools=True retries=0 total_spawns=1
2026-10-27 07:14:51 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=7 transport=run first_event_ms=2609 ttft_ms=2609 transport_history=['run'] duration_s=2.87
.2026-10-27 07:14:51 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1026 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 07:14:51 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:14:51 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=7 emulate_tools=True retries=0 total_spawns=1
2026-10-27 07:14:51 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=7 transport=run first_event_ms=114 ttft_ms=114 transport_history=['run'] duration_s=0.37
..2026-10-27 07:14:52 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1026 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 07:14:52 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:14:53 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=7 emulate_tools=True retries=0 total_spawns=1
2026-10-27 07:14:53 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=7 transport=run first_event_ms=1317 ttft_ms=1317 transport_history=['run'] duration_s=1.57
.2026-10-27 07:14:54 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1028 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 07:14:54 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:14:56 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=6 emulate_tools=True retries=0 total_spawns=1
2026-10-27 07:14:56 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=6 transport=run first_event_ms=1718 ttft_ms=1718 transport_history=['run'] duration_s=1.98
.2026-10-27 07:14:56 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1026 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 07:14:56 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:14:58 stream exec retry=0 fail_retries=0 model=opencode/muse-spark-1.3-contributor-free prompt_chars=1026 total_spawns=1/3
2026-10-27 07:15:00 stream exec retry=0 fail_retries=0 model=opencode/muse-spark-1.3-contributor-free prompt_chars=1026 total_spawns=2/3
2026-10-27 07:15:01 retry denied (first_event_timeout): MAX_TOTAL_SPAWNS=3 reached
2026-10-27 07:15:01 stream failed model=muse-spark-1.3-contributor-free rc=-15 fail_retries=0 total_spawns=3
2026-10-27 07:15:01 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=first_event_timeout rc=None total_spawns=3 retries=2 signal=0 tools=0 out_chars=0 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=5.05
.....2026-10-27 07:15:01 circuit_breaker state=OPEN failures=1 cooldown_s=0.0
2026-10-27 07:15:01 circuit_breaker state=HALF_OPEN
2026-10-27 07:15:01 circuit_breaker state=CLOSED
...................2026-10-27 07:15:21 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1125 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 07:15:21 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:15:22 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=6 transport=serve first_event_ms=461 ttft_ms=461 transport_history=['serve'] duration_s=1.34
.2026-10-27 07:15:22 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1034 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 07:15:22 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:15:23 stream exec retry=0 fail_retries=0 model=opencode/muse-spark-1.3-contributor-free prompt_chars=1034 total_spawns=1/3
2026-10-27 07:15:25 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=13 emulate_tools=True retries=0 total_spawns=2
2026-10-27 07:15:25 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=2 retries=0 signal=0 tools=0 out_chars=13 transport=run first_event_ms=2276 ttft_ms=2276 transport_history=['serve', 'run'] duration_s=2.53
2026-10-27 07:15:25 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1034 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 07:15:25 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:15:25 stream exec retry=0 fail_retries=0 model=opencode/muse-spark-1.3-contributor-free prompt_chars=1034 total_spawns=1/3
2026-10-27 07:15:27 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=13 emulate_tools=True retries=0 total_spawns=2
2026-10-27 07:15:27 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=2 retries=0 signal=0 tools=0 out_chars=13 transport=run first_event_ms=2276 ttft_ms=2276 transport_history=['serve', 'run'] duration_s=2.54
2026-10-27 07:15:27 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1034 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 07:15:27 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:15:28 stream exec retry=0 fail_retries=0 model=opencode/muse-spark-1.3-contributor-free prompt_chars=1034 total_spawns=1/3
2026-10-27 07:15:30 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=13 emulate_tools=True retries=0 total_spawns=2
2026-10-27 07:15:30 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=2 retries=0 signal=0 tools=0 out_chars=13 transport=run first_event_ms=2254 ttft_ms=2254 transport_history=['serve', 'run'] duration_s=2.51
.2026-10-27 07:15:31 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:15:31 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=2 retries=1 signal=0 tools=0 out_chars=23 transport=serve first_event_ms=None ttft_ms=None transport_history=['serve'] duration_s=1.01
.2026-10-27 07:15:32 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1036 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 07:15:32 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:15:34 retry denied (prompt_error): MAX_TOTAL_SPAWNS=2 reached
2026-10-27 07:15:34 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=prompt_error rc=None total_spawns=2 retries=1 signal=0 tools=0 out_chars=0 transport=serve first_event_ms=None ttft_ms=None transport_history=['serve'] duration_s=2.26
2026-10-27 07:15:36 retry denied (prompt_error): MAX_TOTAL_SPAWNS=2 reached
2026-10-27 07:15:36 http "POST /v1/chat/completions HTTP/1.1" 502 -
2026-10-27 07:15:36 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=502 exit_reason=prompt_error rc=None total_spawns=2 retries=1 signal=0 tools=0 out_chars=0 transport=serve first_event_ms=None ttft_ms=None transport_history=['serve'] duration_s=1.97
2026-10-27 07:15:36 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1041 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 07:15:36 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:15:38 retry denied (prompt_status_429): MAX_TOTAL_SPAWNS=2 reached
2026-10-27 07:15:38 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=prompt_status_429 rc=None total_spawns=2 retries=1 signal=0 tools=0 out_chars=0 transport=serve first_event_ms=None ttft_ms=None transport_history=['serve'] duration_s=1.92
2026-10-27 07:15:40 retry denied (prompt_status_429): MAX_TOTAL_SPAWNS=2 reached
2026-10-27 07:15:40 http "POST /v1/chat/completions HTTP/1.1" 502 -
2026-10-27 07:15:40 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=502 exit_reason=prompt_status_429 rc=None total_spawns=2 retries=1 signal=0 tools=0 out_chars=0 transport=serve first_event_ms=None ttft_ms=None transport_history=['serve'] duration_s=1.94
2026-10-27 07:15:40 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1041 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 07:15:40 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:15:42 retry denied (prompt_status_503): MAX_TOTAL_SPAWNS=2 reached
2026-10-27 07:15:42 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=prompt_status_503 rc=None total_spawns=2 retries=1 signal=0 tools=0 out_chars=0 transport=serve first_event_ms=None ttft_ms=None transport_history=['serve'] duration_s=1.92
2026-10-27 07:15:44 retry denied (prompt_status_503): MAX_TOTAL_SPAWNS=2 reached
2026-10-27 07:15:44 http "POST /v1/chat/completions HTTP/1.1" 502 -
2026-10-27 07:15:44 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=502 exit_reason=prompt_status_503 rc=None total_spawns=2 retries=1 signal=0 tools=0 out_chars=0 transport=serve first_event_ms=None ttft_ms=None transport_history=['serve'] duration_s=1.89
..2026-10-27 07:15:44 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1034 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 07:15:44 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:15:46 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=6 transport=serve first_event_ms=478 ttft_ms=478 transport_history=['serve'] duration_s=1.37
...2026-10-27 07:15:47 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1131 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 07:15:47 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:15:48 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=cancelled rc=None total_spawns=1 retries=0 signal=0 tools=0 out_chars=0 transport=serve first_event_ms=510 ttft_ms=None transport_history=['serve'] duration_s=1.26
.2026-10-27 07:15:49 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1021 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 07:15:49 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:15:51 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=3 retries=2 signal=0 tools=0 out_chars=6 transport=serve first_event_ms=None ttft_ms=None transport_history=['serve'] duration_s=2.01
.2026-10-27 07:15:51 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free --standalone prompt_chars=1021 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 07:15:51 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:15:52 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=2 retries=1 signal=0 tools=0 out_chars=14 transport=serve first_event_ms=None ttft_ms=None transport_history=['serve'] duration_s=1.01
.2026-10-27 07:15:53 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1021 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 07:15:53 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:15:53 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=cancelled rc=None total_spawns=1 retries=0 signal=0 tools=0 out_chars=0 transport=serve first_event_ms=None ttft_ms=None transport_history=['serve'] duration_s=0.00
2026-10-27 07:15:54 http "POST /v1/chat/completions HTTP/1.1" 502 -
2026-10-27 07:15:54 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=502 exit_reason=cancelled rc=None total_spawns=1 retries=0 signal=0 tools=0 out_chars=0 transport=serve first_event_ms=None ttft_ms=None transport_history=['serve'] duration_s=1.01
..2026-10-27 07:15:55 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1034 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 07:15:55 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:15:56 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=6 transport=serve first_event_ms=479 ttft_ms=479 transport_history=['serve'] duration_s=1.35
.2026-10-27 07:15:56 http "POST /v1/chat/completions HTTP/1.1" 502 -
2026-10-27 07:15:56 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=502 exit_reason=upstream_failed rc=None total_spawns=3 retries=0 signal=0 tools=0 out_chars=0 transport=run first_event_ms=None ttft_ms=None transport_history=['serve', 'run'] duration_s=0.00
.2026-10-27 07:15:57 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:15:57 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=1 out_chars=0 transport=serve first_event_ms=None ttft_ms=None transport_history=['serve'] duration_s=0.00
.2026-10-27 07:15:57 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1042 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 07:15:57 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:15:58 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=1 out_chars=0 transport=serve first_event_ms=467 ttft_ms=468 transport_history=['serve'] duration_s=0.65
.2026-10-27 07:15:58 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1048 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 07:15:58 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:15:59 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=provider_fatal rc=None total_spawns=1 retries=0 signal=0 tools=0 out_chars=0 transport=serve first_event_ms=None ttft_ms=None transport_history=['serve'] duration_s=1.19
2026-10-27 07:15:59 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1048 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 07:15:59 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:16:00 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=provider_fatal rc=None total_spawns=1 retries=0 signal=0 tools=0 out_chars=0 transport=serve first_event_ms=None ttft_ms=None transport_history=['serve'] duration_s=0.91
2026-10-27 07:16:00 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1048 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 07:16:00 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:16:01 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=provider_fatal rc=None total_spawns=1 retries=0 signal=0 tools=0 out_chars=0 transport=serve first_event_ms=None ttft_ms=None transport_history=['serve'] duration_s=1.02
.2026-10-27 07:16:02 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1021 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 07:16:02 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:16:02 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=upstream_failed rc=None total_spawns=1 retries=0 signal=0 tools=0 out_chars=0 transport=serve first_event_ms=None ttft_ms=None transport_history=['serve'] duration_s=0.00
.2026-10-27 07:16:02 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1021 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 07:16:02 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:16:04 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=3 retries=2 signal=0 tools=0 out_chars=6 transport=serve first_event_ms=None ttft_ms=None transport_history=['serve'] duration_s=2.01
.2026-10-27 07:16:05 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1021 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 07:16:05 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:16:05 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=upstream_failed rc=None total_spawns=2 retries=1 signal=0 tools=0 out_chars=0 transport=serve first_event_ms=None ttft_ms=None transport_history=['serve'] duration_s=0.00
2026-10-27 07:16:05 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1021 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 07:16:05 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:16:05 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=upstream_failed rc=None total_spawns=1 retries=1 signal=0 tools=0 out_chars=0 transport=serve first_event_ms=None ttft_ms=None transport_history=['serve'] duration_s=0.00
2026-10-27 07:16:05 http "POST /v1/chat/completions HTTP/1.1" 502 -
2026-10-27 07:16:05 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=502 exit_reason=upstream_failed rc=None total_spawns=2 retries=1 signal=0 tools=0 out_chars=0 transport=serve first_event_ms=None ttft_ms=None transport_history=['serve'] duration_s=0.00
2026-10-27 07:16:05 http "POST /v1/chat/completions HTTP/1.1" 502 -
2026-10-27 07:16:05 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=502 exit_reason=upstream_failed rc=None total_spawns=1 retries=1 signal=0 tools=0 out_chars=0 transport=serve first_event_ms=None ttft_ms=None transport_history=['serve'] duration_s=0.00
..2026-10-27 07:16:06 dynamic config unreadable: 'utf-8' codec can't decode byte 0xff in position 0: invalid start byte
.2026-10-27 07:16:06 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1021 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 07:16:06 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:16:06 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=113 transport=serve first_event_ms=None ttft_ms=None transport_history=['serve'] duration_s=0.00
2026-10-27 07:16:06 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1021 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 07:16:06 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:16:07 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=113 transport=serve first_event_ms=None ttft_ms=None transport_history=['serve'] duration_s=1.01
2026-10-27 07:16:07 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1021 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 07:16:07 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:16:08 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=113 transport=serve first_event_ms=None ttft_ms=None transport_history=['serve'] duration_s=0.99
.2026-10-27 07:16:08 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1021 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 07:16:08 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:16:08 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=upstream_failed rc=None total_spawns=1 retries=0 signal=0 tools=0 out_chars=0 transport=serve first_event_ms=None ttft_ms=None transport_history=['serve'] duration_s=0.00
2026-10-27 07:16:09 http "POST /v1/chat/completions HTTP/1.1" 502 -
2026-10-27 07:16:09 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=502 exit_reason=upstream_failed rc=None total_spawns=1 retries=0 signal=0 tools=0 out_chars=0 transport=serve first_event_ms=None ttft_ms=None transport_history=['serve'] duration_s=1.01
.2026-10-27 07:16:10 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1034 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 07:16:10 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:16:10 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=provider_fatal rc=None total_spawns=1 retries=0 signal=0 tools=0 out_chars=0 transport=serve first_event_ms=None ttft_ms=None transport_history=['serve'] duration_s=0.61
...2026-10-27 07:16:12 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1032 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 07:16:12 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:16:15 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=6 transport=serve first_event_ms=479 ttft_ms=1887 transport_history=['serve'] duration_s=2.76
.2026-10-27 07:16:15 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1032 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 07:16:15 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:16:18 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=6 transport=serve first_event_ms=482 ttft_ms=1883 transport_history=['serve'] duration_s=2.76
.2026-10-27 07:16:18 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1021 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 07:16:18 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:16:20 retry denied (timeout): MAX_TOTAL_SPAWNS=3 reached
2026-10-27 07:16:20 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=timeout rc=None total_spawns=3 retries=2 signal=0 tools=0 out_chars=0 transport=serve first_event_ms=None ttft_ms=None transport_history=['serve'] duration_s=2.01
2026-10-27 07:16:23 retry denied (timeout): MAX_TOTAL_SPAWNS=3 reached
2026-10-27 07:16:23 http "POST /v1/chat/completions HTTP/1.1" 502 -
2026-10-27 07:16:23 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=502 exit_reason=timeout rc=None total_spawns=3 retries=2 signal=0 tools=0 out_chars=0 transport=serve first_event_ms=None ttft_ms=None transport_history=['serve'] duration_s=2.99
2026-10-27 07:16:23 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1021 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 07:16:23 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:16:24 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=client_gone rc=None total_spawns=1 retries=0 signal=0 tools=0 out_chars=0 transport=serve first_event_ms=None ttft_ms=None transport_history=['serve'] duration_s=1.00
2026-10-27 07:16:25 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=0 exit_reason=client_gone rc=None total_spawns=1 retries=0 signal=0 tools=0 out_chars=0 transport=serve first_event_ms=None ttft_ms=None transport_history=['serve'] duration_s=0.99
.2026-10-27 07:16:26 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1058 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 07:16:26 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:16:27 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=2 retries=1 signal=1 tools=1 out_chars=17 transport=serve first_event_ms=None ttft_ms=None transport_history=['serve'] duration_s=1.01
2026-10-27 07:16:27 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1056 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 07:16:27 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:16:29 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=2 retries=1 signal=1 tools=1 out_chars=17 transport=serve first_event_ms=None ttft_ms=None transport_history=['serve'] duration_s=2.00
.2026-10-27 07:16:29 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1039 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 07:16:29 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:16:30 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=1 out_chars=0 transport=serve first_event_ms=470 ttft_ms=470 transport_history=['serve'] duration_s=0.87
....................................................2026-10-27 07:16:36 tool_call_unparsed bytes=7 head='{broken'
.........................................2026-10-27 07:16:36 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1216 cwd=/var/folders/2f/***/T/tmpn3kkq43r/ws
2026-10-27 07:16:36 exec: early provider error (waiting for CLI recovery)
2026-10-27 07:16:37 exec: step with tool call finished, stopping opencode run
2026-10-27 07:16:37 exec cli failed rc=-15 state=provider_error stderr_tail='HTTP None: provider.transport: Connection lost: ECONNRESET'
2026-10-27 07:16:37 done model=muse-spark-1.3-contributor-free rc=-15 state=provider_error tools=2 out_chars=0 retries=0 total_spawns=1
2026-10-27 07:16:37 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:16:37 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=-15 total_spawns=1 retries=0 signal=0 tools=2 out_chars=0 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=1.10
.2026-10-27 07:16:37 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1216 cwd=/var/folders/2f/***/T/tmpn3kkq43r/ws
2026-10-27 07:16:37 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:16:37 stream provider error: HTTP None: provider.transport: Connection lost: ECONNRESET
2026-10-27 07:16:37 stream: early provider error (waiting for CLI recovery)
2026-10-27 07:16:38 stream: step with tool call finished, stopping opencode run
2026-10-27 07:16:38 stream done model=muse-spark-1.3-contributor-free rc=-15 tools=2 out_chars=0 emulate_tools=True retries=0 total_spawns=1
2026-10-27 07:16:38 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=-15 total_spawns=1 retries=0 signal=0 tools=2 out_chars=0 transport=run first_event_ms=19 ttft_ms=1020 transport_history=['run'] duration_s=1.03
.2026-10-27 07:16:38 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1216 cwd=/var/folders/2f/***/T/tmpn3kkq43r/ws
2026-10-27 07:16:38 exec: early provider error (waiting for CLI recovery)
2026-10-27 07:16:39 done model=muse-spark-1.3-contributor-free rc=0 state=provider_error tools=0 out_chars=17 retries=0 total_spawns=1
2026-10-27 07:16:39 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:16:39 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=17 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=1.30
.2026-10-27 07:16:39 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1216 cwd=/var/folders/2f/***/T/tmpn3kkq43r/ws
2026-10-27 07:16:39 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:16:39 stream provider error: HTTP None: provider.transport: Connection lost: ECONNRESET
2026-10-27 07:16:39 stream: early provider error (waiting for CLI recovery)
2026-10-27 07:16:41 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=17 emulate_tools=True retries=0 total_spawns=1
2026-10-27 07:16:41 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=17 transport=run first_event_ms=37 ttft_ms=1039 transport_history=['run'] duration_s=1.29
.2026-10-27 07:16:41 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1216 cwd=/var/folders/2f/***/T/tmpn3kkq43r/ws
2026-10-27 07:16:41 exec: provider error mid-response (transient=True), stopping opencode run
2026-10-27 07:16:41 exec cli failed rc=1 state=provider_error stderr_tail='HTTP None: provider.transport: Connection lost while reading the response: ECONNRESET'
2026-10-27 07:16:41 incomplete tool step: re-prompt 1/2 signal=1 total_spawns=1/3
2026-10-27 07:16:41 exec retry=1 (incomplete tool step) total_spawns=1/3
2026-10-27 07:16:41 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1854 cwd=/var/folders/2f/***/T/tmpn3kkq43r/ws
2026-10-27 07:16:42 exec: step with tool call finished, stopping opencode run
2026-10-27 07:16:42 done model=muse-spark-1.3-contributor-free rc=-15 state=nonzero_exit tools=2 out_chars=78 retries=1 total_spawns=2
2026-10-27 07:16:42 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:16:42 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=-15 total_spawns=2 retries=1 signal=1 tools=2 out_chars=78 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=1.05
.2026-10-27 07:16:42 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1216 cwd=/var/folders/2f/***/T/tmpn3kkq43r/ws
2026-10-27 07:16:42 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:16:42 stream provider error: HTTP None: provider.transport: Connection lost while reading the response: ECONNRESET
2026-10-27 07:16:42 stream: provider error mid-response (transient=True), stopping opencode run
2026-10-27 07:16:42 stream incomplete tool step: re-prompt 1/2 signal=1 total_spawns=1/3
2026-10-27 07:16:42 stream exec retry=1 fail_retries=0 model=opencode/muse-spark-1.3-contributor-free prompt_chars=1854 total_spawns=1/3
2026-10-27 07:16:43 stream: step with tool call finished, stopping opencode run
2026-10-27 07:16:43 stream done model=muse-spark-1.3-contributor-free rc=-15 tools=2 out_chars=78 emulate_tools=True retries=1 total_spawns=2
2026-10-27 07:16:43 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=-15 total_spawns=2 retries=1 signal=1 tools=2 out_chars=78 transport=run first_event_ms=24 ttft_ms=24 transport_history=['run'] duration_s=1.05
.2026-10-27 07:16:43 stream exec model=opencode/glm-5.3-flash-free -m opencode/glm-5.3-flash-free#high --standalone --thinking prompt_chars=1375 cwd=/var/folders/2f/***/T/tmpn3kkq43r/ws
2026-10-27 07:16:43 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:16:43 stream: step with tool call finished, stopping opencode run
2026-10-27 07:16:43 stream done model=glm-5.3-flash-free rc=-15 tools=2 out_chars=0 emulate_tools=True retries=0 total_spawns=1
2026-10-27 07:16:43 O-EXIT/v1 mode=stream model=glm-5.3-flash-free status=200 exit_reason=ok rc=-15 total_spawns=1 retries=0 signal=0 tools=2 out_chars=0 transport=run first_event_ms=25 ttft_ms=25 transport_history=['run'] duration_s=0.03
.2026-10-27 07:16:43 stream exec model=opencode/glm-5.3-flash-free -m opencode/glm-5.3-flash-free#high --standalone --thinking prompt_chars=1224 cwd=/var/folders/2f/***/T/tmpn3kkq43r/ws
2026-10-27 07:16:43 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:16:43 stream: step with tool call finished, stopping opencode run
2026-10-27 07:16:43 stream done model=glm-5.3-flash-free rc=-15 tools=2 out_chars=0 emulate_tools=True retries=0 total_spawns=1
2026-10-27 07:16:43 O-EXIT/v1 mode=stream model=glm-5.3-flash-free status=200 exit_reason=ok rc=-15 total_spawns=1 retries=0 signal=0 tools=2 out_chars=0 transport=run first_event_ms=20 ttft_ms=20 transport_history=['run'] duration_s=0.02
.2026-10-27 07:16:43 exec model=opencode/glm-5.3-flash-free -m opencode/glm-5.3-flash-free#high --standalone --thinking prompt_chars=1224 cwd=/var/folders/2f/***/T/tmpn3kkq43r/ws
2026-10-27 07:16:43 incomplete tool step: re-prompt 1/2 signal=3 total_spawns=1/3
2026-10-27 07:16:43 exec retry=1 (incomplete tool step) total_spawns=1/3
2026-10-27 07:16:43 exec model=opencode/glm-5.3-flash-free -m opencode/glm-5.3-flash-free#high --standalone --thinking prompt_chars=1867 cwd=/var/folders/2f/***/T/tmpn3kkq43r/ws
2026-10-27 07:16:44 exec: step with tool call finished, stopping opencode run
2026-10-27 07:16:44 done model=glm-5.3-flash-free rc=-15 state=nonzero_exit tools=2 out_chars=77 retries=1 total_spawns=2
2026-10-27 07:16:44 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:16:44 O-EXIT/v1 mode=json model=glm-5.3-flash-free status=200 exit_reason=ok rc=-15 total_spawns=2 retries=1 signal=3 tools=2 out_chars=77 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=1.03
.2026-10-27 07:16:44 stream exec model=opencode/glm-5.3-flash-free -m opencode/glm-5.3-flash-free#high --standalone --thinking prompt_chars=1224 cwd=/var/folders/2f/***/T/tmpn3kkq43r/ws
2026-10-27 07:16:44 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:16:44 stream incomplete tool step: re-prompt 1/2 signal=3 total_spawns=1/3
2026-10-27 07:16:44 stream exec retry=1 fail_retries=0 model=opencode/glm-5.3-flash-free prompt_chars=1867 total_spawns=1/3
2026-10-27 07:16:45 stream: step with tool call finished, stopping opencode run
2026-10-27 07:16:45 stream done model=glm-5.3-flash-free rc=-15 tools=2 out_chars=77 emulate_tools=True retries=1 total_spawns=2
2026-10-27 07:16:45 O-EXIT/v1 mode=stream model=glm-5.3-flash-free status=200 exit_reason=ok rc=-15 total_spawns=2 retries=1 signal=3 tools=2 out_chars=77 transport=run first_event_ms=19 ttft_ms=19 transport_history=['run'] duration_s=1.05
.2026-10-27 07:16:45 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1216 cwd=/var/folders/2f/***/T/tmpn3kkq43r/ws
2026-10-27 07:16:45 done model=muse-spark-1.3-contributor-free rc=0 state=ok tools=0 out_chars=7 retries=0 total_spawns=1
2026-10-27 07:16:45 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:16:45 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=7 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=0.28
.2026-10-27 07:16:45 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1216 cwd=/var/folders/2f/***/T/tmpn3kkq43r/ws
2026-10-27 07:16:45 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:16:45 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=7 emulate_tools=True retries=0 total_spawns=1
2026-10-27 07:16:45 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=7 transport=run first_event_ms=21 ttft_ms=21 transport_history=['run'] duration_s=0.28
.2026-10-27 07:16:45 exec model=opencode/glm-5.3-flash-free -m opencode/glm-5.3-flash-free#high --standalone --thinking prompt_chars=1224 cwd=/var/folders/2f/***/T/tmpn3kkq43r/ws
2026-10-27 07:16:45 exec: step with tool call finished, stopping opencode run
2026-10-27 07:16:45 tool_call_unparsed bytes=7 head='{broken'
2026-10-27 07:16:45 dropped 1 unparsed tool block(s) from content
2026-10-27 07:16:46 incomplete tool step: re-prompt 1/2 signal=2 total_spawns=1/3
2026-10-27 07:16:46 exec retry=1 (incomplete tool step) total_spawns=1/3
2026-10-27 07:16:46 exec model=opencode/glm-5.3-flash-free -m opencode/glm-5.3-flash-free#high --standalone --thinking prompt_chars=1868 cwd=/var/folders/2f/***/T/tmpn3kkq43r/ws
2026-10-27 07:16:46 exec: step with tool call finished, stopping opencode run
2026-10-27 07:16:46 done model=glm-5.3-flash-free rc=-15 state=nonzero_exit tools=2 out_chars=78 retries=1 total_spawns=2
2026-10-27 07:16:46 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:16:46 O-EXIT/v1 mode=json model=glm-5.3-flash-free status=200 exit_reason=ok rc=-15 total_spawns=2 retries=1 signal=2 tools=2 out_chars=78 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=1.03
.2026-10-27 07:16:46 exec model=opencode/glm-5.3-flash-free -m opencode/glm-5.3-flash-free#high --standalone --thinking prompt_chars=1224 cwd=/var/folders/2f/***/T/tmpn3kkq43r/ws
2026-10-27 07:16:46 exec: step with tool call finished, stopping opencode run
2026-10-27 07:16:46 tool_call_recovered extra_braces=1
2026-10-27 07:16:46 done model=glm-5.3-flash-free rc=-15 state=nonzero_exit tools=1 out_chars=0 retries=0 total_spawns=1
2026-10-27 07:16:46 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:16:46 O-EXIT/v1 mode=json model=glm-5.3-flash-free status=200 exit_reason=ok rc=-15 total_spawns=1 retries=0 signal=0 tools=1 out_chars=0 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=0.02
.2026-10-27 07:16:46 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1216 cwd=/var/folders/2f/***/T/tmpn3kkq43r/ws
2026-10-27 07:16:47 done model=muse-spark-1.3-contributor-free rc=0 state=ok tools=0 out_chars=7 retries=0 total_spawns=1
2026-10-27 07:16:47 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:16:47 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=7 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=0.28
.2026-10-27 07:16:47 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1216 cwd=/var/folders/2f/***/T/tmpn3kkq43r/ws
2026-10-27 07:16:47 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:16:47 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=7 emulate_tools=True retries=0 total_spawns=1
2026-10-27 07:16:47 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=7 transport=run first_event_ms=21 ttft_ms=21 transport_history=['run'] duration_s=0.28
.2026-10-27 07:16:47 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1216 cwd=/var/folders/2f/***/T/tmpn3kkq43r/ws
2026-10-27 07:16:48 incomplete tool step: re-prompt 1/2 signal=4 total_spawns=1/3
2026-10-27 07:16:48 exec retry=1 (incomplete tool step) total_spawns=1/3
2026-10-27 07:16:48 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1900 cwd=/var/folders/2f/***/T/tmpn3kkq43r/ws
2026-10-27 07:16:48 exec: step with tool call finished, stopping opencode run
2026-10-27 07:16:48 done model=muse-spark-1.3-contributor-free rc=-15 state=nonzero_exit tools=2 out_chars=125 retries=1 total_spawns=2
2026-10-27 07:16:48 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:16:48 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=-15 total_spawns=2 retries=1 signal=4 tools=2 out_chars=125 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=1.04
.2026-10-27 07:16:48 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1216 cwd=/var/folders/2f/***/T/tmpn3kkq43r/ws
2026-10-27 07:16:48 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:16:48 stream incomplete tool step: re-prompt 1/2 signal=4 total_spawns=1/3
2026-10-27 07:16:48 stream exec retry=1 fail_retries=0 model=opencode/muse-spark-1.3-contributor-free prompt_chars=1900 total_spawns=1/3
2026-10-27 07:16:49 stream: step with tool call finished, stopping opencode run
2026-10-27 07:16:49 stream done model=muse-spark-1.3-contributor-free rc=-15 tools=2 out_chars=125 emulate_tools=True retries=1 total_spawns=2
2026-10-27 07:16:49 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=-15 total_spawns=2 retries=1 signal=4 tools=2 out_chars=125 transport=run first_event_ms=23 ttft_ms=23 transport_history=['run'] duration_s=1.04
.2026-10-27 07:16:49 exec model=opencode/glm-5.3-flash-free -m opencode/glm-5.3-flash-free#high --standalone --thinking prompt_chars=1224 cwd=/var/folders/2f/***/T/tmpn3kkq43r/ws
2026-10-27 07:16:49 exec: step with tool call finished, stopping opencode run
2026-10-27 07:16:49 tool_call_unparsed bytes=7 head='{broken'
2026-10-27 07:16:49 dropped 1 unparsed tool block(s) from content
2026-10-27 07:16:49 incomplete tool step: re-prompt 1/2 signal=2 total_spawns=1/3
2026-10-27 07:16:49 exec retry=1 (incomplete tool step) total_spawns=1/3
2026-10-27 07:16:49 exec model=opencode/glm-5.3-flash-free -m opencode/glm-5.3-flash-free#high --standalone --thinking prompt_chars=1777 cwd=/var/folders/2f/***/T/tmpn3kkq43r/ws
2026-10-27 07:16:50 exec: step with tool call finished, stopping opencode run
2026-10-27 07:16:50 tool_call_unparsed bytes=7 head='{broken'
2026-10-27 07:16:50 dropped 1 unparsed tool block(s) from content
2026-10-27 07:16:51 incomplete tool step: re-prompt 2/2 signal=2 total_spawns=2/3
2026-10-27 07:16:51 exec retry=2 (incomplete tool step) total_spawns=2/3
2026-10-27 07:16:51 exec model=opencode/glm-5.3-flash-free -m opencode/glm-5.3-flash-free#high --standalone --thinking prompt_chars=1777 cwd=/var/folders/2f/***/T/tmpn3kkq43r/ws
2026-10-27 07:16:51 exec: step with tool call finished, stopping opencode run
2026-10-27 07:16:51 tool_call_unparsed bytes=7 head='{broken'
2026-10-27 07:16:51 dropped 1 unparsed tool block(s) from content
2026-10-27 07:16:51 incomplete tool step: retries exhausted (2) signal=2
2026-10-27 07:16:51 done model=glm-5.3-flash-free rc=-15 state=nonzero_exit tools=0 out_chars=66 retries=2 total_spawns=3
2026-10-27 07:16:51 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:16:51 O-EXIT/v1 mode=json model=glm-5.3-flash-free status=200 exit_reason=ok rc=-15 total_spawns=3 retries=2 signal=2 tools=0 out_chars=66 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=2.05
.2026-10-27 07:16:51 exec model=opencode/glm-5.3-flash-free -m opencode/glm-5.3-flash-free#high --standalone --thinking prompt_chars=1224 cwd=/var/folders/2f/***/T/tmpn3kkq43r/ws
2026-10-27 07:16:51 exec: step with tool call finished, stopping opencode run
2026-10-27 07:16:51 tool_call_unparsed bytes=7 head='{broken'
2026-10-27 07:16:51 dropped 1 unparsed tool block(s) from content
2026-10-27 07:16:51 done model=glm-5.3-flash-free rc=-15 state=nonzero_exit tools=2 out_chars=0 retries=0 total_spawns=1
2026-10-27 07:16:51 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:16:51 O-EXIT/v1 mode=json model=glm-5.3-flash-free status=200 exit_reason=ok rc=-15 total_spawns=1 retries=0 signal=0 tools=2 out_chars=0 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=0.03
.2026-10-27 07:16:51 stream exec model=opencode/glm-5.3-flash-free -m opencode/glm-5.3-flash-free#high --standalone --thinking prompt_chars=1224 cwd=/var/folders/2f/***/T/tmpn3kkq43r/ws
2026-10-27 07:16:51 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:16:51 tool_call_unparsed bytes=7 head='{broken'
2026-10-27 07:16:51 stream dropped 1 unparsed tool block(s) from content
2026-10-27 07:16:52 stream incomplete tool step: re-prompt 1/2 signal=2 total_spawns=1/3
2026-10-27 07:16:52 stream exec retry=1 fail_retries=0 model=opencode/glm-5.3-flash-free prompt_chars=1868 total_spawns=1/3
2026-10-27 07:16:52 stream: step with tool call finished, stopping opencode run
2026-10-27 07:16:52 stream done model=glm-5.3-flash-free rc=-15 tools=2 out_chars=78 emulate_tools=True retries=1 total_spawns=2
2026-10-27 07:16:52 O-EXIT/v1 mode=stream model=glm-5.3-flash-free status=200 exit_reason=ok rc=-15 total_spawns=2 retries=1 signal=2 tools=2 out_chars=78 transport=run first_event_ms=20 ttft_ms=20 transport_history=['run'] duration_s=1.03
.2026-10-27 07:16:52 stream exec model=opencode/glm-5.3-flash-free -m opencode/glm-5.3-flash-free#high --standalone --thinking prompt_chars=1224 cwd=/var/folders/2f/***/T/tmpn3kkq43r/ws
2026-10-27 07:16:52 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:16:52 tool_call_unparsed bytes=7 head='{broken'
2026-10-27 07:16:52 stream dropped 1 unparsed tool block(s) from content
2026-10-27 07:16:53 stream incomplete tool step: re-prompt 1/2 signal=2 total_spawns=1/3
2026-10-27 07:16:53 stream exec retry=1 fail_retries=0 model=opencode/glm-5.3-flash-free prompt_chars=1777 total_spawns=1/3
2026-10-27 07:16:53 tool_call_unparsed bytes=7 head='{broken'
2026-10-27 07:16:53 stream dropped 1 unparsed tool block(s) from content
2026-10-27 07:16:55 stream incomplete tool step: re-prompt 2/2 signal=2 total_spawns=2/3
2026-10-27 07:16:55 stream exec retry=2 fail_retries=0 model=opencode/glm-5.3-flash-free prompt_chars=1777 total_spawns=2/3
2026-10-27 07:16:55 tool_call_unparsed bytes=7 head='{broken'
2026-10-27 07:16:55 stream dropped 1 unparsed tool block(s) from content
2026-10-27 07:16:55 stream incomplete tool step: retries exhausted (2) signal=2
2026-10-27 07:16:55 stream done model=glm-5.3-flash-free rc=0 tools=0 out_chars=66 emulate_tools=True retries=2 total_spawns=3
2026-10-27 07:16:55 O-EXIT/v1 mode=stream model=glm-5.3-flash-free status=200 exit_reason=ok rc=0 total_spawns=3 retries=2 signal=2 tools=0 out_chars=66 transport=run first_event_ms=19 ttft_ms=19 transport_history=['run'] duration_s=2.68
.2026-10-27 07:16:55 stream exec model=opencode/glm-5.3-flash-free -m opencode/glm-5.3-flash-free#high --standalone --thinking prompt_chars=1224 cwd=/var/folders/2f/***/T/tmpn3kkq43r/ws
2026-10-27 07:16:55 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:16:55 tool_call_recovered extra_braces=1
2026-10-27 07:16:55 stream: step with tool call finished, stopping opencode run
2026-10-27 07:16:55 stream done model=glm-5.3-flash-free rc=-15 tools=1 out_chars=0 emulate_tools=True retries=0 total_spawns=1
2026-10-27 07:16:55 O-EXIT/v1 mode=stream model=glm-5.3-flash-free status=200 exit_reason=ok rc=-15 total_spawns=1 retries=0 signal=0 tools=1 out_chars=0 transport=run first_event_ms=37 ttft_ms=37 transport_history=['run'] duration_s=0.04
.2026-10-27 07:16:55 stream exec model=opencode/glm-5.3-flash-free -m opencode/glm-5.3-flash-free#high --standalone --thinking prompt_chars=1224 cwd=/var/folders/2f/***/T/tmpn3kkq43r/ws
2026-10-27 07:16:55 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:16:55 stream done model=glm-5.3-flash-free rc=0 tools=0 out_chars=7 emulate_tools=True retries=0 total_spawns=1
2026-10-27 07:16:55 O-EXIT/v1 mode=stream model=glm-5.3-flash-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=7 transport=run first_event_ms=22 ttft_ms=22 transport_history=['run'] duration_s=0.28
.2026-10-27 07:16:55 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=7872 cwd=/var/folders/2f/***/T/tmpn3kkq43r/ws
2026-10-27 07:16:55 done model=muse-spark-1.3-contributor-free rc=0 state=ok tools=0 out_chars=7 retries=0 total_spawns=1
2026-10-27 07:16:55 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:16:55 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=7 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=0.28
.2026-10-27 07:16:55 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1216 cwd=/var/folders/2f/***/T/tmpn3kkq43r/ws
2026-10-27 07:16:56 opencode built-in tool event: tool=todoread status=error mapped=False as=[]
2026-10-27 07:16:56 unmapped built-in tools=['todoread']: re-prompt 1/2
2026-10-27 07:16:56 exec retry=1 (unmapped built-in tool) total_spawns=1/3
2026-10-27 07:16:56 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1715 cwd=/var/folders/2f/***/T/tmpn3kkq43r/ws
2026-10-27 07:16:57 opencode built-in tool event: tool=todoread status=error mapped=False as=[]
2026-10-27 07:16:59 unmapped built-in tools=['todoread']: re-prompt 2/2
2026-10-27 07:16:59 exec retry=2 (unmapped built-in tool) total_spawns=2/3
2026-10-27 07:16:59 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=2214 cwd=/var/folders/2f/***/T/tmpn3kkq43r/ws
2026-10-27 07:16:59 retry denied (incomplete_step): MAX_TOTAL_SPAWNS=3 reached
2026-10-27 07:16:59 incomplete tool step: retries exhausted (0) signal=4
2026-10-27 07:16:59 done model=muse-spark-1.3-contributor-free rc=0 state=ok tools=0 out_chars=125 retries=2 total_spawns=3
2026-10-27 07:16:59 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:16:59 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=3 retries=2 signal=0 tools=0 out_chars=125 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=3.46
.2026-10-27 07:16:59 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1216 cwd=/var/folders/2f/***/T/tmpn3kkq43r/ws
2026-10-27 07:16:59 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:16:59 opencode built-in tool event: tool=todoread status=error mapped=False as=[]
2026-10-27 07:16:59 stream unmapped built-in tools=['todoread']: re-prompt 1/2
2026-10-27 07:16:59 stream exec retry=1 fail_retries=0 model=opencode/muse-spark-1.3-contributor-free prompt_chars=1715 total_spawns=1/3
2026-10-27 07:17:00 opencode built-in tool event: tool=todoread status=error mapped=False as=[]
2026-10-27 07:17:00 stream unmapped built-in tools=['todoread']: re-prompt 2/2
2026-10-27 07:17:00 stream exec retry=2 fail_retries=0 model=opencode/muse-spark-1.3-contributor-free prompt_chars=2214 total_spawns=2/3
2026-10-27 07:17:01 retry denied (incomplete_step): MAX_TOTAL_SPAWNS=3 reached
2026-10-27 07:17:01 stream incomplete tool step: retries exhausted (0) signal=4
2026-10-27 07:17:01 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=125 emulate_tools=True retries=2 total_spawns=3
2026-10-27 07:17:01 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=3 retries=2 signal=0 tools=0 out_chars=125 transport=run first_event_ms=36 ttft_ms=2035 transport_history=['run'] duration_s=2.30
.2026-10-27 07:17:01 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1216 cwd=/var/folders/2f/***/T/tmpn3kkq43r/ws
2026-10-27 07:17:01 exec: provider error mid-response (transient=True), stopping opencode run
2026-10-27 07:17:01 exec cli failed rc=1 state=provider_error stderr_tail='HTTP None: provider.transport: Connection lost: ECONNRESET'
2026-10-27 07:17:01 opencode built-in tool event: tool=todoread status=error mapped=False as=[]
2026-10-27 07:17:02 unmapped built-in tools=['todoread']: re-prompt 1/2
2026-10-27 07:17:02 exec retry=1 (unmapped built-in tool) total_spawns=1/3
2026-10-27 07:17:02 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1715 cwd=/var/folders/2f/***/T/tmpn3kkq43r/ws
2026-10-27 07:17:02 exec: step with tool call finished, stopping opencode run
2026-10-27 07:17:02 done model=muse-spark-1.3-contributor-free rc=-15 state=nonzero_exit tools=2 out_chars=0 retries=1 total_spawns=2
2026-10-27 07:17:02 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:17:02 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=-15 total_spawns=2 retries=1 signal=0 tools=2 out_chars=0 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=1.05
.2026-10-27 07:17:02 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1216 cwd=/var/folders/2f/***/T/tmpn3kkq43r/ws
2026-10-27 07:17:02 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 07:17:02 opencode built-in tool event: tool=todoread status=error mapped=False as=[]
2026-10-27 07:17:03 stream unmapped built-in tools=['todoread']: re-prompt 1/2
2026-10-27 07:17:03 stream exec retry=1 fail_retries=0 model=opencode/muse-spark-1.3-contributor-free prompt_chars=1715 total_spawns=1/3
2026-10-27 07:17:05 stream incomplete tool step: re-prompt 1/2 signal=4 total_spawns=2/3
2026-10-27 07:17:05 stream exec retry=2 fail_retries=0 model=opencode/muse-spark-1.3-contributor-free prompt_chars=1900 total_spawns=2/3
2026-10-27 07:17:05 stream: step with tool call finished, stopping opencode run
2026-10-27 07:17:05 stream done model=muse-spark-1.3-contributor-free rc=-15 tools=2 out_chars=125 emulate_tools=True retries=2 total_spawns=3
2026-10-27 07:17:05 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=-15 total_spawns=3 retries=2 signal=4 tools=2 out_chars=125 transport=run first_event_ms=25 ttft_ms=1044 transport_history=['run'] duration_s=2.62
.....2026-10-27 07:17:05 tool_strip_cap_hit max=16 dropping tail
2026-10-27 07:17:05 tool_strip_cap_hit max=16 dropping tail
2026-10-27 07:17:05 tool_strip_cap_hit max=16 dropping tail
..........................................................2026-10-27 07:17:07 tool_call_unparsed bytes=114 head='{"name": "read", "arguments": {"file_path": "/a"}} `<tool_call>`{"name": "read", "arguments": {"file_path": "/b"}}'
...2026-10-27 07:17:07 tool_call_unparsed bytes=23 head='<tool_call>{"name":"a"}'
2026-10-27 07:17:07 tool_call_unparsed bytes=47 head='{"name":"a"}<tool_call> <tool_call>{"name":"b"}'
2026-10-27 07:17:07 tool_call_unparsed bytes=23 head='{"name":"a"}<tool_call>'
.2026-10-27 07:17:07 tool_call_unparsed bytes=32 head='{"name": "a"} <tool_call>{broken'
..............................................
----------------------------------------------------------------------
Ran 451 tests in 204.991s

OK
```

### `VER-003-root-pythonpath-pytest` (`l2-green-ver003-pythonpath.log`, `sha256=e513ea260ef23feefb1cb1080a0e14c344263f1e0660193ef5400397de24af85`)
```text
$ uvx pytest -q -p no:cacheprovider tests/
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom] [rc=0] [wall=368.72s]
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
894 passed, 5 skipped, 8103 subtests passed in 368.47s (0:06:08)

--- STDERR ---
2026-10-27T04:23:07Z transient failure rc=-15 err='', retry 1 client=127.0.0.1:56601 ua=-
```

### `VER-003b-root-pythonpath-zen-pytest` (`l2-green-ver003b-zen-pythonpath.log`, `sha256=04432d097c2457beb2a0ed08ed2483bf46b8e6d78184cdc38730e4117bd0850d`)
```text
$ uvx pytest -q -p no:cacheprovider bridges/opencode-zen-bridge/tests/
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom] [rc=0] [wall=215.62s]
--- STDOUT ---
......................... [  5%]
............................................................................................................................................... [ 37%]
............................................................................................................ [ 61%]
.................................................................... [ 76%]
........................................................ [ 88%]
...................................................                         [100%]
451 passed, 3197 subtests passed in 215.12s (0:03:35)

--- STDERR ---
```

### `VER-005-dedicated-realtime-suite` (`l2-green-ver005-dedicated.log`, `sha256=0d584be48bafdc9b353bfa590b0a736c8b6fa723d3c96e920d788f9b65221f69`)
```text
$ uvx pytest -q -p no:cacheprovider tests/test_realtime_reasoning.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=131.78s]
--- STDOUT ---
............................................ [ 61%]
............................                               [100%]
72 passed, 42 subtests passed in 131.62s (0:02:11)

--- STDERR ---
```

### `AC-023-pytest-reversed` (`l2-green-ac023-reversed.log`, `sha256=583ffb499f33aafdaa7908903c664af14dfd94ea3dc6fd0d55debf30e873a5de`)
```text
$ uvx pytest -q -p no:cacheprovider tests/test_zen_catalog.py tests/test_tool_emulation.py tests/test_sync_yaml.py tests/test_stream_thinking.py tests/test_step_interruption.py tests/test_stdin_prompt.py tests/test_run_env.py tests/test_realtime_reasoning.py tests/test_native_fallback.py tests/test_lenient_tool_call.py tests/test_google_direct.py tests/test_go_model_routing.py tests/test_effort_mapping.py tests/test_cli_failure.py tests/test_catalog_reload.py tests/test_catalog_mode.py tests/test_catalog.py tests/test_aliases.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=212.34s]
--- STDOUT ---
.................................................................. [ 14%]
................................................................. [ 29%]
................................................................. [ 43%]
......................................................... [ 56%]
............................................ [ 65%]
....................................... [ 74%]
...................................................................................................................                         [100%]
451 passed, 3197 subtests passed in 212.14s (0:03:32)

--- STDERR ---
```

ARTIFACT_END>>>
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/verification-traceability.md sha256=6b408f0aaa787613a4c9e2ef354cd6178fdcbccfa6c5010c1259ed56854c519f
# Матрица прослеживаемости приёмки (`verification-traceability.md`, run `analyst-teamlead-zen-realtime-reasoning-20261025`, cycle `5`)

## Служебные отметки контура `teamlead-gate`
- **Режим ревью:** `reviewer_skip=true`, `downstream_panel=true`, `parent_skill="analyst-teamlead"` (отдельный `Reviewer` не запускается; Совет Тимлидов — единственный рубеж построчного и приёмочного ревью по `acceptance-package.md` §1; счётчик «замечаний совета сверх Reviewer» при `downstream_panel=true` не определён).
- **Назначение шапки тимлида (`council.md` §1):** дословная шапка тимлида прикреплена сразу после системного промпта роли (`prompt-{skeptic,realist,visionary}.txt`) и до факт-карты во всех 3 брифах Совета Тимлидов.
- **Побайтовая неизменность замороженных функций (`Run-Path Freeze` / `REQ-018`):**
  - `def _run_env`: `sha256=1c51b28fcb83fcc0f4d8b5204c858e11ab5ac975bfe40dca4a0bf61978008e31` (ожидалось `1c51b28fcb83fcc0f4d8b5204c858e11ab5ac975bfe40dca4a0bf61978008e31` — **MATCH**)
  - `def _stream_google_sse` и `def _execute_google_once`: `google_direct_unchanged=True` (**MATCH**)
  - Белый список изменённых файлов: `bridges/opencode-zen-bridge/server.py, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py, bridges/opencode-zen-bridge/tests/test_step_interruption.py` (ровно 3 целевых файла `coder_target_files`).

## Сводка `acceptance_coverage` из `coder.json`
- {"id": "RW-001/FU-002/FU-005", "status": "PASS", "oracle": "test_c5_rw001_prompt_headers_then_body_error_or_429_blocks_run_fallback; test_c5_fu002_prompt_401_headers_classified_before_hanging_body", "evidence": "Headers 200 + reset / 429 / 503: SSE и JSON без run, без record_success, ровно одно списание RetryBudget; зависшее тело 401 классифицируется по заголовкам."}
- {"id": "RW-002", "status": "PASS", "oracle": "test_c5_rw002_limiter_delay_half_second_still_emits_first_status_under_1s", "evidence": "Лимитер задерживает старт на 0.5 с: STATUS_INITIAL ровно один и <=1.0 с от запроса."}
- {"id": "RW-003/FU-001", "status": "PASS", "oracle": "test_c5_rw003_legacy_retry_separator_all_branches_and_thinking_gate", "evidence": "watchdog/unmapped/incomplete: две попытки, один разделитель при high и ноль при off."}
- {"id": "RW-004", "status": "PASS", "oracle": "test_c5_rw004_native_call_updates_last_token_at_no_premature_stall", "evidence": "Первый native-call после 0.4 с, затем ещё 0.4 с при stall=0.6 с: succeeded без преждевременного stall."}
- {"id": "FU-003", "status": "PASS", "oracle": "test_c5_fu003_json_transient_recovery_normalizes_and_deduplicates", "evidence": "Частичный tool-блок удалён, преамбула в итоговом content встречается один раз."}
- {"id": "FU-004", "status": "PASS", "oracle": "test_ac026_realtime_chunks_before_upstream_end", "evidence": "Независимые sent_times и recv_times: каждая дельта передана за <0.25 с."}
- {"id": "FU-006", "status": "PASS", "oracle": "server.py: finally _serve_one_attempt; VER-004 и оба полных набора", "evidence": "interrupt и DELETE получают deadline=time.monotonic()+0.35 при timeout=0.25. Отдельный тест капающего cleanup-тела не добавлялся."}

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
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/evidence-manifest.sha256 sha256=9ad237182f0cf02d58596bbff74c5c59d45ef9c60713829d6d0baacda2944f8f
e67d5ffb98e29dd698e38e17e18772fa792391a2e24e05cf88d2f820a14e8722  teamlead/verification-surface.json
bfbbe7ddfb3d5b275c99d5ab0673f0b8e46a17baea036ea65e48cd1dceb8bfa3  teamlead/environment-manifest.json
f60f4bb6b184e951cd98b4c6ff4f6e6f23cd0cdd64048fa0d056ceedeb44d138  teamlead/execution-evidence.md
6b408f0aaa787613a4c9e2ef354cd6178fdcbccfa6c5010c1259ed56854c519f  teamlead/verification-traceability.md
91d223c36cceed54690e606de8bf07ef50784b40c135d1be77ba672b6f9c55af  teamlead/reverse-spec.md
fff0ca490d247d4ed3f8736888f7e25d8df4e702398717079c228e5b4f8c3fe8  teamlead/candidate-manifest.json
3bf5e0c3c290828af3f1628a1e96674701687c5e69441dd406bb0776d99f4c9b  teamlead/candidate.diff
a461f6939bf14c7a656c2f87ecc7a349358857f1acc1c18ce4a77da286982c72  handoff/panel-rework-brief.json
d4bf82b2b9eec81550e8bcef7f33e42ecc7d760d3c6b8d2421df8a0e451dbd2a  coder.json
d4bf82b2b9eec81550e8bcef7f33e42ecc7d760d3c6b8d2421df8a0e451dbd2a  receipts/coder.json
a6cc87b8e1e49bc58fae30a26d121cdbb4ea2b3a98117f9022e32b6a4b8ab6a6  receipts/code-gate.json
f60147ee21f5cab8b9f863efdd76b568285c0deaa02078b6bf5a7e4e2a13d721  receipts/verifier.json
b41e0dfcee1cfaeae762da9affec98ea3b670e9a5e2431a9c0b7728def07dd01  receipts/final-gate.json
583ffb499f33aafdaa7908903c664af14dfd94ea3dc6fd0d55debf30e873a5de  receipts/l2-green-ac023-reversed.log
6d9590a036bc6663f658849946706267a71b20258ca5d0d4b33b793eacdf9798  receipts/l2-green-ver001-pytest.log
42b7fc5b435d91162cc18866c672fff4d58d95ce4119c28fb721dbb1061dcd60  receipts/l2-green-ver002-unittest.log
e513ea260ef23feefb1cb1080a0e14c344263f1e0660193ef5400397de24af85  receipts/l2-green-ver003-pythonpath.log
04432d097c2457beb2a0ed08ed2483bf46b8e6d78184cdc38730e4117bd0850d  receipts/l2-green-ver003b-zen-pythonpath.log
153c06e3f5e23c7756f62a109e02d3ebdc5500eb80fbfb2ffe7dedb019b93bf1  receipts/l2-green-ver004-packet.log
a404c1d9581d7bdd63de163b752ca39827a407d087cfaab46177c02d692d9e60  receipts/l2-green-ver004-range-server-1.log
f47a003e699cccfaacea2281e74a8417b0e65e7e195564936047f0b0a68e0a48  receipts/l2-green-ver004-range-server-10.log
f72d210b39fa1c611c2ab31e838dbbbf590f4d573bf252cc03c259eeedcbad82  receipts/l2-green-ver004-range-server-100.log
259da303d1d415b53b4ed8cee5c834460d0a01ea0e492e2dd5d81593f64c5840  receipts/l2-green-ver004-range-server-101.log
fddb2fa73d248fa7ee54e6ad77b7242eb3b063bbcea83a1b66b1ab34ec3d4ea1  receipts/l2-green-ver004-range-server-102.log
eac0bde537b7323cf75fb992504c7b3e97220b573fb08553479b0e14bd2f71f7  receipts/l2-green-ver004-range-server-103.log
99b5d6be08f0a3263ebd0cfbcdcd13e99946f03d94cc7c82f0547644c625bb27  receipts/l2-green-ver004-range-server-104.log
d88875b82f81343bca022f27b5c24630c80621284ba5fe79264524277b51a8b4  receipts/l2-green-ver004-range-server-105.log
a1cc996607b0e4bf1b4e7e78906b3eaad888aaeda48d646f7c8868b3739b4213  receipts/l2-green-ver004-range-server-106.log
cf7a85ce9a689272ddb701f998037077ad51724c31a45b66d6a658ef3559da82  receipts/l2-green-ver004-range-server-107.log
b569e9ebf42dbc5d6a19c7095d3ca79604740c714e1b8e12b28dcf9d7fb341e9  receipts/l2-green-ver004-range-server-108.log
07e83c9d4478fff35b4b3b9cb873965434442fd5694086346bf42107bf023b46  receipts/l2-green-ver004-range-server-109.log
0803e87b0022a9bdd8665fcb9582160716b18c89361429d4f9ce924f6e77cadb  receipts/l2-green-ver004-range-server-11.log
fb999ceb5b55589a17b36d065fb8603ee0eee70bc19f2bcec5aebce7bedda1fe  receipts/l2-green-ver004-range-server-110.log
52207219dce3e2d0414e21b86839efa105d6c6c756593d1978c49fd876351314  receipts/l2-green-ver004-range-server-111.log
0aa543727bbadc426f147f935578c37cc3174c1cce5a1c1e7a7a0ec3a9fc94c4  receipts/l2-green-ver004-range-server-112.log
8e26e0ce01c375482f13a7e91d0e90ec16e523b46249bfa68f9a029d964df077  receipts/l2-green-ver004-range-server-113.log
2b410d2d609b2bda637cd56aadd94e517f555a10a568865326453cc250e116c1  receipts/l2-green-ver004-range-server-114.log
0db31703a3cd84920cfc2de382af754f1f171cde3d45b11aa7054d10027d2f75  receipts/l2-green-ver004-range-server-115.log
705d132e124b45126167549603c758cb44a61948d0c1100b2a2bb666af8574d5  receipts/l2-green-ver004-range-server-116.log
12c0f4e08a9c025a3ef9b59e50ee29c0e7fb94d85198105bb31d2f5d0882a546  receipts/l2-green-ver004-range-server-117.log
a441fff7fc38e930107cf89630714bf19faaa2677fa83af57805cf921e4cbfb6  receipts/l2-green-ver004-range-server-118.log
a75818bac9f276d83c4ebbc92403d6e5b5a3918ee75f60c8cb1282ecadb40561  receipts/l2-green-ver004-range-server-119.log
1c1b1d2c35319d764f075ea927bee42e89ccdf8f38cb89b6c909049717bd49f9  receipts/l2-green-ver004-range-server-12.log
4d2018b4d55d1982c99e0fe47d760f159d4b3108179ce3308bc84e5980cf449a  receipts/l2-green-ver004-range-server-120.log
8a15a9122a65c1317b27270c29d0c74abcfdfacd73e0574eced10035d38a3fb3  receipts/l2-green-ver004-range-server-121.log
837a70b8edfafb8d2d9bebd6bbf37e39c10b9de553309554af2827aa4c4e8767  receipts/l2-green-ver004-range-server-122.log
873a8f544984bef94db1bee88dad1fbbaf101f5a9f93322a8a21e060827dc288  receipts/l2-green-ver004-range-server-123.log
9b58b9db4c42d9e33b691822631e290b8164ea7fa0412a50d5fa7a3b34697e1d  receipts/l2-green-ver004-range-server-124.log
6bae884d8d38de9a632c1f6866a4a4b63fbfb9d7d07cb9ef4dc8cc4e05c91ea2  receipts/l2-green-ver004-range-server-125.log
3e6792f089e6aa9513142647ab54f44608e1a7c589b458bb2d87504c15447476  receipts/l2-green-ver004-range-server-126.log
3f167f07dcf355f539a2c158540dc81dbd722798fc16b7293a5ea06155f62ced  receipts/l2-green-ver004-range-server-127.log
1704f31fc1a8b7521a2bcec4677aad505e6c5933584b0fb1c5af5802e78c8df9  receipts/l2-green-ver004-range-server-128.log
ee2004760d985ca024bb5d7aa7c24d53022e8dcfa40d973330090ca30dbea764  receipts/l2-green-ver004-range-server-129.log
b5cfe664a46aacdb81a3e9e23fb0b34fc85011f91a5d76f7390446019daa0da6  receipts/l2-green-ver004-range-server-13.log
5aa29bd3a71c5d9639f8f5d6240b5df74030a48f9606736b18b0668e1f2050dd  receipts/l2-green-ver004-range-server-130.log
07a7e201910cd4e2ec1c47c6b7285866c88dedee01c45ae99fa7e87b9e66fd13  receipts/l2-green-ver004-range-server-131.log
23080c69d68cbb183d8f3edfa66772279da5f468fe44c78275d8c721975aade3  receipts/l2-green-ver004-range-server-132.log
098ec49841b296032e306b00d2d8eb2e8257d8b8fc23de2adb37a4f6646bf5f9  receipts/l2-green-ver004-range-server-133.log
1d3909886d955ec4d3b1dadc0edebcb276d5e9ebcf2139e44946fa9b67325348  receipts/l2-green-ver004-range-server-134.log
692a75e9e2d196a835f5139e0a1c414ec5a9ed9324db998a6439ad3535efd104  receipts/l2-green-ver004-range-server-135.log
c1103c0b87c5275833b75563d2378835eb069b0ce1f03d8d7678eb4271b6ef89  receipts/l2-green-ver004-range-server-136.log
ab0b96591ee35862b7348fcedec1dbf88c098d4c49cc730a01ff7c7ae5582b17  receipts/l2-green-ver004-range-server-137.log
4f6e2d20cc6779d82ad5f947237f55ad10e331b3de4ef33ef25e1c8bf48999d6  receipts/l2-green-ver004-range-server-138.log
a44876311e4a6643d5e75419d0154c201e199c095b765beed1c08eefc2e8a33f  receipts/l2-green-ver004-range-server-139.log
7bb7cf0ed99b37f4773d0d2bb983a0f17eee2147a02c8588b80092301286971a  receipts/l2-green-ver004-range-server-14.log
994afe39393159506d857489595b81236959a71dc8b8794badbb0a2401e41e21  receipts/l2-green-ver004-range-server-140.log
1d31e8cf765b7a7a3e2c2a3c811b5cc37d4740392dd7c511724d6a2e202eb852  receipts/l2-green-ver004-range-server-141.log
c9510d4ef5ecf9b27f74d02578d8cc3f8ba00936d2e5d0fe69dd761ed33920d6  receipts/l2-green-ver004-range-server-142.log
2dcbd1cfb7bf474662c1b0bc8ad303d8c722e456358b74b9547a23a085765826  receipts/l2-green-ver004-range-server-143.log
24ac0caf5138801b1751443e87e9652999186041c6eea53870e167f04a64a6e3  receipts/l2-green-ver004-range-server-144.log
0d2d2f53172514db8561f37d4074ed449d9da131e71c4301e60a2165b1b5c679  receipts/l2-green-ver004-range-server-145.log
92adb64581e8b8138be3e1817eff74c082765982c4dcf73d2c596ea935a8d862  receipts/l2-green-ver004-range-server-146.log
d91cf68b989dfe88f1594d415b0b6520278d18dc18fbcb0bd3c05c59d6c129f3  receipts/l2-green-ver004-range-server-147.log
ff8bbce27a27f253c4799ea64cad9c8a9d3ce26928104378fbbe6da4abc80894  receipts/l2-green-ver004-range-server-148.log
b1cb8051386e4b73b1ebf5fdcce48bfaf73c76c1f617c20a72d91d38f0dc979a  receipts/l2-green-ver004-range-server-149.log
73acb95336cb1ca5b8dc1c5300e108122e8e49e21617438118c7475d9fd9fce5  receipts/l2-green-ver004-range-server-15.log
34a8da065e7aac1e93fd56c8916469f1b4e9cc6f168d1dde9551fba64f167f5f  receipts/l2-green-ver004-range-server-150.log
29b6f2618d8eabd96c770a68a4364eaf18dde0fca43eb3feeded4109b8031e47  receipts/l2-green-ver004-range-server-151.log
69f6db4e25374c131fbd504c6ba2f6727c506d9fae72a58ee8e59de673964bdd  receipts/l2-green-ver004-range-server-152.log
1e5842b5c8c55c9bb02e8a7c661cb6eb28486d3a09576a4ef5b3c301397a27bb  receipts/l2-green-ver004-range-server-153.log
c55055fba770700536b80a0685a59cae29c7364a3572e4ecbb8d810203faa7ba  receipts/l2-green-ver004-range-server-154.log
599196bb9773ef89347d7d0c2f9722615e6ef271cf2c02095b4578cd64451e65  receipts/l2-green-ver004-range-server-155.log
f7114a4ec53a022c630c34caecc6fa242e274a71a9fe269f43f5682191b7427f  receipts/l2-green-ver004-range-server-156.log
d5e7d1c79d0a91581c5491dab956da8f623e072a56c15895b9f38dfaa210fba2  receipts/l2-green-ver004-range-server-157.log
cf5a0d45e60238a34c25b4b64277ffb63f3024e3ca20886ddeaa30bd6928e517  receipts/l2-green-ver004-range-server-158.log
cb2f81d822bfafd6e066e4c8542b54f78180dc03f40a8a3c873a042334b8de34  receipts/l2-green-ver004-range-server-159.log
897b3de85007942daa484b304a6d50852fc21240140f5efa5018ba7431e68d0e  receipts/l2-green-ver004-range-server-16.log
3effac0b45fec3b0dd3761bd24bf47c59ed45685fde7e76410f8742a2cae6435  receipts/l2-green-ver004-range-server-160.log
0346148bcc3c0c243acb4235825d0eb4357dddf72aba8bea87f5b19453260885  receipts/l2-green-ver004-range-server-161.log
e2f2804be51cc88600d10f5f6fea850dafcd9c5e7ccf60ee2435aff96f19131c  receipts/l2-green-ver004-range-server-162.log
ca4859c240855d5681e02c70fc22dd86b0b46921e90326e649961affcab97127  receipts/l2-green-ver004-range-server-163.log
3b0d60798042c9be4dadd11ef624c5cd82769b6371e768dadfe9e9ebc80da495  receipts/l2-green-ver004-range-server-164.log
a034675f7c705a51308081be50bea763df00bf34368853fcdacaae22102f17eb  receipts/l2-green-ver004-range-server-165.log
141d6705b0a38e0b41dc3f1ca087a2e6cefbe3286236c90b603dada8c2c50242  receipts/l2-green-ver004-range-server-166.log
c08a38d553452178c1e9e30e91e42b833d9d1ae239a3222914289eca25823e1b  receipts/l2-green-ver004-range-server-167.log
545a552371bda619186616942c0a9b9028c01a4939dc39f4142839ef4863d297  receipts/l2-green-ver004-range-server-168.log
b718b32226864fa22a7047bd6d9343522a8a3851c7d336b04179ab3b15764eb8  receipts/l2-green-ver004-range-server-169.log
baf7343422e05d2b13b1edb6d403ae46fbffbc0d745a8ce21243df39a19c207c  receipts/l2-green-ver004-range-server-17.log
6901ac149268cf3e334a44929a43e7a6a3f9bf03aca5d3a17497a17b8c8fee87  receipts/l2-green-ver004-range-server-170.log
e70d4aef915c90b0fc673ad2dd14c752f48c0d4d11c9ae14847e60a4e5a39050  receipts/l2-green-ver004-range-server-171.log
af9028f0663461265ef42ba226bde2f3da5a80ba6a4402f23295f69436e21675  receipts/l2-green-ver004-range-server-172.log
3e2b7b86b9d81e5dbeda1ff79bdbb0a2aad1f70848b00a4f7848bdd59e675127  receipts/l2-green-ver004-range-server-173.log
ba356c2c4b2700ad6ef2ed4cf1ec8584a9b74a2d79c6fa49d1c898d255dba815  receipts/l2-green-ver004-range-server-174.log
6b83c520605b4b5c09dbda7a2364ba4a70d1e9e82323e107a71bec68164c30b4  receipts/l2-green-ver004-range-server-175.log
f83906aaf12e1edf929e610c43b2ca93fa0ed87e4551594766c4b7f4e8e44537  receipts/l2-green-ver004-range-server-176.log
b8a5d9538975229c2a2ca97ae7bbf1dbb828c3873e5f5e71675bde691642b98f  receipts/l2-green-ver004-range-server-177.log
93ac9ed7515457787ee736b0840fb909259a36e8309957e5c4f1cdfa9fd9e0dd  receipts/l2-green-ver004-range-server-178.log
7d57364ccbc85b3ff105cf2975633371ffe89cfb4af4f3358ae684d6bac29b61  receipts/l2-green-ver004-range-server-179.log
0b22180adcb395c481b96271e0a2971ddd991303c1803a40937b11e06da6fe2f  receipts/l2-green-ver004-range-server-18.log
1b1c67648aca4626ce0a7f14c3b685034dab3285f7234516b7a455465780eb87  receipts/l2-green-ver004-range-server-180.log
2a8c55ccb7731e524f0b150e5d6df31235b55e00d24ced6d48a79a754de345f4  receipts/l2-green-ver004-range-server-181.log
8275bd3c7ceab42e9a5400322b77de2a4d8462ab4dd8b324894f3d04df18a36b  receipts/l2-green-ver004-range-server-182.log
8205a93896c60f16cc4843c38881e5b2fb938849854c2b8204505d92bdb5bd4d  receipts/l2-green-ver004-range-server-183.log
5ee95fb8a0e8856c7043336f738b009be298d9da62e54e0f0472de8326881e51  receipts/l2-green-ver004-range-server-184.log
1650b40c3a5055d686617a715d1eec80882e6ba47dc9c6eb56170f08e3755bbe  receipts/l2-green-ver004-range-server-185.log
77815a6d89cd5a0431eeafb65a3f766bc9cc4bde1ef62d392fd59e60565c9fc4  receipts/l2-green-ver004-range-server-186.log
138fc3ebb8bc0c6a2f3debda5068790e0fddfd7891f02611768680732eb41627  receipts/l2-green-ver004-range-server-187.log
bfa395a5dd40d6d5af7758ecd04ca49354db23e7c37797395045ede4a8d8c0a9  receipts/l2-green-ver004-range-server-188.log
f7f473f61b66351a8264bbe7d38147307f61f8cc89351b6c2915db3214ca6322  receipts/l2-green-ver004-range-server-189.log
302c0b90acbb79c825603aad446818ac55743b6544abe26daeabe1e94ffe3a7b  receipts/l2-green-ver004-range-server-19.log
20938c65ad09662823de69a9fbe4fbe18dab1e9e603695b7b92eee7f3244dfa2  receipts/l2-green-ver004-range-server-190.log
41f0320b8a790e1852b4d6a6e279487522b1eb4b12ecdba71dba15cabe742b35  receipts/l2-green-ver004-range-server-191.log
fbfa45c7ecaa7ca945f1f5e6f0f30fb815ba5fe2dfc37408ae8d1bb3af9e3000  receipts/l2-green-ver004-range-server-192.log
429a34e91e34fd98b98caa75243d249a956bab4d5fa832536f74084e03c53d18  receipts/l2-green-ver004-range-server-193.log
8ddfd62f785356bc7f137a0d4eadc02756c74030dc16e30a39ac57469074618c  receipts/l2-green-ver004-range-server-194.log
49b4c4c621d0bd16f2a73b6c38d8932fb47c167572a25e9722b4bb86dd092d3b  receipts/l2-green-ver004-range-server-195.log
66b85e95151260252318188a7eed9313695c9d599287f3d18c4f0454523e1404  receipts/l2-green-ver004-range-server-196.log
aa243a081289ed07669477bed48398a7d1f34a1b6e2cadde1877109ecefb5a88  receipts/l2-green-ver004-range-server-197.log
8afe2771c62502283378b03d6b4f764468e6d87dae9a62c54386eb23edda287e  receipts/l2-green-ver004-range-server-198.log
3035b7f8c18c4013d6dc83dc48b09ded37ac68a0be6061d46bdc3763f5df3589  receipts/l2-green-ver004-range-server-199.log
e44f59079a3c027ad3be2a804f21fc2d473b26f2fb92e310dc71a321e2378e76  receipts/l2-green-ver004-range-server-2.log
1d62380b67860bcea67418738d8078497ce351c91661b8a8f416a2bfa3b52ee9  receipts/l2-green-ver004-range-server-20.log
4c701510cf348366c162ccb031c4c2e05be25e8cd69c39d1aefc5aee529f1ea7  receipts/l2-green-ver004-range-server-200.log
8325bf1c54e05512792f6ead38f26f494bb1d3b5e045631a523b7d63d0d2dd7d  receipts/l2-green-ver004-range-server-201.log
8df55a9761ebc6bcdb9e5847882a7c7655666a7b1128b3c74772c1f9ed94462b  receipts/l2-green-ver004-range-server-202.log
7b051e55da212a7f97ecf6bbc5f6fc824cc5fcc8d78aace6348cc8bdb420a3ac  receipts/l2-green-ver004-range-server-203.log
38b38f27a0cc224e45bc95241eeb15e860970f49b69b098ffb8857bf0034c3f2  receipts/l2-green-ver004-range-server-21.log
4add685fcfaa1323e24db48e87eb6e91f277e75bddb174492f421fe08532e92d  receipts/l2-green-ver004-range-server-22.log
cb1e6e8c41133ac82bb3c2140ccecc3c7db365f821e3ecb318b3e2e2ab6a18fe  receipts/l2-green-ver004-range-server-23.log
04ed6aa6e1b8e3a628b7c34029c1de3bc270479a70c27815c48ce7763c77ba9c  receipts/l2-green-ver004-range-server-24.log
9b41188c7172afdf7c0dbcbeb4d58614c9e181174af7a266245e3295a08e1826  receipts/l2-green-ver004-range-server-25.log
da334bc326db1ba2c1b753a6af42c1c4f40bce2c2568566e94f3f7f655f62c24  receipts/l2-green-ver004-range-server-26.log
83bf3ef389e5b5c005a199cc74842e2269cd1bd7e27ecf7099486a874cc324d5  receipts/l2-green-ver004-range-server-27.log
ddbd4f924e1874f3af38f6070c4cc81c86fd6a51554a20fdd8d59eb736b3bf55  receipts/l2-green-ver004-range-server-28.log
062407b6d6e561b3462c064391f7e182ddb4718f53e06d28de3a81d3f93c3277  receipts/l2-green-ver004-range-server-29.log
199dd06b7f9709a65b2a65a77107646a7deb420819da89ded0a24b55f7c66014  receipts/l2-green-ver004-range-server-3.log
776e4c270234206422638d9b17b2145af725026bf46f248064db812ceebbc93c  receipts/l2-green-ver004-range-server-30.log
ad43b6e96ec857b29dcffb151becad6d037183bef729a6d1d180aa46a4c92687  receipts/l2-green-ver004-range-server-31.log
fed2fc86e165c014111cff799df4475cc3776e8680cce55c5b2ab450e48d37da  receipts/l2-green-ver004-range-server-32.log
eccb40bbad0e17fbe9691efdebe30db0e62860c9a39f95cc182b5914ad735194  receipts/l2-green-ver004-range-server-33.log
f0dd4169e7f6750fd3367800b1d2e4ff0a126e1551c5d653d5795db8025b248b  receipts/l2-green-ver004-range-server-34.log
c3f48a18857c8dffc7787947376542a9d61f3c8965fa831c59357771f2db9958  receipts/l2-green-ver004-range-server-35.log
5bade37fbf8629d055693d0dd12df8da2baca5bf856f67ba03d452892b0a335a  receipts/l2-green-ver004-range-server-36.log
bdecec546c6254c44d7b3b807747b7d5e77712b3faea300d21cdd36a20ae991f  receipts/l2-green-ver004-range-server-37.log
fbffeadaf23cdf9e6460a18b25802248ecd63396596fa2e6bbc6e4b294d21e0c  receipts/l2-green-ver004-range-server-38.log
7060f65716917769df0b3040e45c2cc5651b729368ad4804e70f8ecc4b203780  receipts/l2-green-ver004-range-server-39.log
46a8dda50db85802e7d6e2382de3b9cf5a3090559c497dc4623f669672731330  receipts/l2-green-ver004-range-server-4.log
75688ca1bf6d11c4549276635d1e8b1bce48c405ff56e45d95a1321c6f30dab6  receipts/l2-green-ver004-range-server-40.log
32b19dff1e70121b4015f163b002b125aaa5cab78b52ab01332d99f5e44803eb  receipts/l2-green-ver004-range-server-41.log
235b11a5d0c389ec3c32f3ead2bdaef4c7dc0580f5f05275db048b4382e22848  receipts/l2-green-ver004-range-server-42.log
c049751624a7f92dbea8abdf8f21f1cae125af5c9aa921ac9cac41479854cfe1  receipts/l2-green-ver004-range-server-43.log
c7f8b6ad167c7d142e0c03c2126bc63aca2990ef04837f994263baf6278353c4  receipts/l2-green-ver004-range-server-44.log
f05eec56f4a322c4ae29692950d3f7ee6ec9ef250b91cfefdd97c54f6e02bfab  receipts/l2-green-ver004-range-server-45.log
4e6032cb389904aac629dd8a550a1f78bf6b4638064e39e942b84c5363001b9b  receipts/l2-green-ver004-range-server-46.log
5428022ca833126347f28708930a80f0dfbe326afb8ee46db2a6d1a833586967  receipts/l2-green-ver004-range-server-47.log
ba626648917a5a238b221536ce165b4cd6a602169e81b15b94ea85755603b956  receipts/l2-green-ver004-range-server-48.log
c23ae89c7674f8df24faab1ae76e441bde67c903ee7dd405b096a8c8b003c57c  receipts/l2-green-ver004-range-server-49.log
5493d40657fa578225a17435e40a0f81f9e98ad9f43b927be234825c09923a28  receipts/l2-green-ver004-range-server-5.log
b1f64f35db3cfe4d3af34cfc48aed3010ffbc5732aa896666d1a84190e18adf5  receipts/l2-green-ver004-range-server-50.log
3e38ff9a218c7c171f89c52c3f7a779db64b7d1c776fe8c903c47e48fa8dc9f5  receipts/l2-green-ver004-range-server-51.log
c2da5898c933ffbef2ffc442409500061afa5a3f6092a39f8c2fe004d92e8b00  receipts/l2-green-ver004-range-server-52.log
4436bc58d39db089853dd7e122ddee922faa8262005c8bbb820bb7651cf782dd  receipts/l2-green-ver004-range-server-53.log
3a7676a967e7df75d22188471b025a8430a42952a03506d849b434704fc3f0c6  receipts/l2-green-ver004-range-server-54.log
b5e2a6edf616848e2d1959b643012ca8bfee430c069ad22c801e0c08f546ae3d  receipts/l2-green-ver004-range-server-55.log
c70f4a99ae24ce0c6ddb6cab2335af382d2abb9398a124b1849a048c27998dd8  receipts/l2-green-ver004-range-server-56.log
da3df42406dbb6d45ad1e88e38a28fc7ada6d793cd3daa8e78dc8157e29a0823  receipts/l2-green-ver004-range-server-57.log
35aeeb5b3c7996c96e1bfec4be8ec9170d045ac846aa99f9353872085f90c9e8  receipts/l2-green-ver004-range-server-58.log
3368122ebd1bb71d42a76aea108cbafc261ee2536028444f3d6a4e558660f0f3  receipts/l2-green-ver004-range-server-59.log
81a31dd77ecc417de950484eb37de15b05f68e328fe32efa2e64e047c24b8556  receipts/l2-green-ver004-range-server-6.log
a10723759acc9784c26c7223098e1dada0854f80ab6f9d2a562b3a7b31a27a39  receipts/l2-green-ver004-range-server-60.log
fd3d4861d3e3706d05d490995a331707938f0ac4fc51a36e31c2264913c22c28  receipts/l2-green-ver004-range-server-61.log
663062b6b0cb8e18747e3f5f5a0bbef9207ce2a1bb5e2df30123ed25dc9b639c  receipts/l2-green-ver004-range-server-62.log
6a735344a3682f9599d26ab22a6a69b4329a113f7dd40bd75ca62c72c1f7a024  receipts/l2-green-ver004-range-server-63.log
37ae44e4006e791ee3757076c6d5481bcad7db00f8f0971aab6e02462af7382b  receipts/l2-green-ver004-range-server-64.log
915ce799eb1ad3f217aaa66ce05edbcc107586915257cc84ea27ff03dfbe6cc8  receipts/l2-green-ver004-range-server-65.log
bb2bf626e55f076e9f3407b1e9123940a47fe03bac902dbf69f681c504b6e77d  receipts/l2-green-ver004-range-server-66.log
cf577429d34f6ca11bf7d9ced97a400373e77d5dc5491888de4135cdeba8ccea  receipts/l2-green-ver004-range-server-67.log
92939a26a13cbf62e4dddf06aaee55a4032d8a84c4f217e0d4652750289d3756  receipts/l2-green-ver004-range-server-68.log
199833623eeab4ff2de512cbcc67984b5185164b11888dd32fa92bd8325377f0  receipts/l2-green-ver004-range-server-69.log
43fd14cc36f69c883d847f894855494ea6972ae69ffc171540b7845cecf7cfd8  receipts/l2-green-ver004-range-server-7.log
4fc7f34046935e0d7e322278dc7d972e7d677f935a854899e8964d304dcaccf0  receipts/l2-green-ver004-range-server-70.log
4f768cd2d828ad66bb1b3df83f21fad29c57109b120d223b735ed051b669f3bc  receipts/l2-green-ver004-range-server-71.log
00c7ce56770fd3d48c2ae46d1163ef1d0203fdc19a99d781e90734979d1c078c  receipts/l2-green-ver004-range-server-72.log
e85be43875181e66446575be35c3519de8b7125ae8d9d513d333a40d405db688  receipts/l2-green-ver004-range-server-73.log
efdf3782035f8d66c20513e26d54aa34be795f3510f8ed51a040adc0248d67ac  receipts/l2-green-ver004-range-server-74.log
f8a1960bda1ad794d332723ffaba92e27c2e47ff361b8bcac8bcf52e06c6273f  receipts/l2-green-ver004-range-server-75.log
c54f4a4aa6a4ceabdce2fb1b546164214e1c6889a07a212e863bec4479df7a73  receipts/l2-green-ver004-range-server-76.log
b4494ae6ad5a307ed5c62ca7a7943c9fdafaf80fe6143c63742aa032e8920c4d  receipts/l2-green-ver004-range-server-77.log
d0bbf955f9e51733e0173a266ec99496475828d314e2c65007b122d3c003bb82  receipts/l2-green-ver004-range-server-78.log
d1bdeff29d702942ae5cb08d4c1d9b2b328abde1b48204128ab2d9ac6bfcfe0c  receipts/l2-green-ver004-range-server-79.log
dd1daff7b29cb0a2d0a3da9fa9f4b6792789e635d8a0a356017d11e263b026ac  receipts/l2-green-ver004-range-server-8.log
4e11db506f0d8cc828a179934cea4053cc434018ea6ece74388bc084794e9d0c  receipts/l2-green-ver004-range-server-80.log
e0ceb1a1888366f92f15ba11f5bb27c24398cc33864b4e9c9f793c1436456080  receipts/l2-green-ver004-range-server-81.log
504541851d4a8873e36191d7853596ea981b5b13c751c0500f1c453f7ebeef99  receipts/l2-green-ver004-range-server-82.log
2a3df9c1e3ada08fb408cd886603d183b1738c938c57bc46a173d37474ae2354  receipts/l2-green-ver004-range-server-83.log
faeb92e82396cb9b31b5230e0ba380e091857bb35427a228eedf9c9b6afc0f9d  receipts/l2-green-ver004-range-server-84.log
746ca683d37f39d144fd80dea531f62d2492369848a0240047ac20a6094cc091  receipts/l2-green-ver004-range-server-85.log
606e6af4523e521cc6a4446e79b4de480b8fd525081ab3820cb69839c8316170  receipts/l2-green-ver004-range-server-86.log
e57b1ccf96c4179c3078cfb70fc8c287e53eff1f23c527fa881fba9b82c53173  receipts/l2-green-ver004-range-server-87.log
14e5e8251ce12dfc30734a18af04cef62272c2f6bcb63b24420dca7a9374752e  receipts/l2-green-ver004-range-server-88.log
c87cf0e82ebae82a2bb634ba847ece71f5650074b57a965e371b61c853fc5264  receipts/l2-green-ver004-range-server-89.log
511b5113f00aeb7c5234fcce7026c7868e4a4e27e6fdf2b91a311652428b976a  receipts/l2-green-ver004-range-server-9.log
c3ea15f42007176a7ee1da36b39dc3369a701bad52f7a1c6850fcdc7387c7ff9  receipts/l2-green-ver004-range-server-90.log
8c1b18169b1361b02e9c13d9d97d918e66a8d7074e9f971bd4d311af194cce9d  receipts/l2-green-ver004-range-server-91.log
2b4d27bc8b9979d13bd2ecba54d01a8090a2dc2b70200b56e1764c83d0943629  receipts/l2-green-ver004-range-server-92.log
ca9f87baf5ac607f16a0e1f2e08570475f7787f95ac686f147661e2e02765166  receipts/l2-green-ver004-range-server-93.log
d10d71002edcc15882ecb7ad20a99d617f4384f51f3829394559246bb29469dc  receipts/l2-green-ver004-range-server-94.log
f531cf954783a45d2815a9e15743349cac8aa256f78e240bc4d4d6e0599ec635  receipts/l2-green-ver004-range-server-95.log
981cbfefa3e9c30f22d9f985326993a4f58c2054a33534e4a9a4dbcdf13a9824  receipts/l2-green-ver004-range-server-96.log
d2a33fd120b0c8df08402d2d6164a9c66def0bce5c8d72a7bcae6ca469c666df  receipts/l2-green-ver004-range-server-97.log
1b7991002fb119b2a9562d39b41d3068d02cd8275511c275a2508af415c2cea1  receipts/l2-green-ver004-range-server-98.log
87e7c296211062fbdc6a8a3ba9072630af8a4b7e306928cea53db77f4c7e4767  receipts/l2-green-ver004-range-server-99.log
c63e1288a625f3368d3343eb4bafe94fd928e5bf0071c3caa409811e5062af02  receipts/l2-green-ver004-range-test_step_interruption-1.log
a6f445e40c73ce63af979e1a5dfe3c65b07d9eb1ec35af3b9cd54417ab2f777e  receipts/l2-green-ver004-range-test_step_interruption-10.log
d6ea66f88862cbce25a6ce983c8b28649baab3f28ac177f8eb4f62d314ea67a5  receipts/l2-green-ver004-range-test_step_interruption-11.log
125ced14eb8211646a63bda744b0597376b998098f6cc32ab89fe238e676e83c  receipts/l2-green-ver004-range-test_step_interruption-12.log
705edf070cc82578d1409324a76a6adbaa3cd176d0b37830d5db368004b7fe08  receipts/l2-green-ver004-range-test_step_interruption-13.log
cce07e9ead13e270f11ace1b1ddd71805551632c86e9029a134aab29935ecf2a  receipts/l2-green-ver004-range-test_step_interruption-2.log
0ac29c83c651286ae55465d424a40d56462dffad60e90b2aa9a37708853b891c  receipts/l2-green-ver004-range-test_step_interruption-3.log
e92b5addd29594e236deb8f14732a3c0faa0e4c0f0b3cc7afcb22e320b7bfc03  receipts/l2-green-ver004-range-test_step_interruption-4.log
f6ac5a14a3c3f61dce8534d50dbfd32bebdb5e100e386aeb7fd8310fed2ec0c8  receipts/l2-green-ver004-range-test_step_interruption-5.log
542b5bf0e71ca6585eafe6554bda6a560f944a7f6b3ae75d8213a579d8f34025  receipts/l2-green-ver004-range-test_step_interruption-6.log
cedf4a5a738a6f18a120a772370cf4197398b3c73b5d86634b7d8df688e33c39  receipts/l2-green-ver004-range-test_step_interruption-7.log
8c244906ff328fddf800adf4652d91234b38caf17479853f4cb33243124a1df6  receipts/l2-green-ver004-range-test_step_interruption-8.log
2632f6d4d0c12d390560de2964670086ccf564b3e724d116e6ee6bebb157be8d  receipts/l2-green-ver004-range-test_step_interruption-9.log
791491a5d9e6128b8400ae730e69e74c9af01651d625cc697d569dfdcee245b7  receipts/l2-green-ver004-ruff-format-new.log
0d584be48bafdc9b353bfa590b0a736c8b6fa723d3c96e920d788f9b65221f69  receipts/l2-green-ver005-dedicated.log
9aff29c1faaefa606bd347afcecc23a7b1c7202c543d5a8a6faaff7327a73774  receipts/l2-red.log
ARTIFACT_END>>>
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/reverse-spec.md sha256=91d223c36cceed54690e606de8bf07ef50784b40c135d1be77ba672b6f9c55af
Файл не сохранён: файловая система доступна только для чтения. Ниже — содержимое `reverse-spec.md`.

# Reverse-Spec: realtime serve-транспорт OpenCode Zen Bridge

Документ реконструирован исключительно по предоставленным diff и новому тестовому модулю. Репозиторий, постановка задачи и архитектурные материалы не использовались. Тесты не запускались; описание покрытия означает наличие соответствующих проверок в коде, а не подтверждённое прохождение.

## 1. Фактически изменённые и добавленные файлы

1. **Изменён `bridges/opencode-zen-bridge/server.py`.**

   Добавлен альтернативный транспорт через отдельный `opencode serve` на каждую попытку. Реализованы локальные HTTP-вызовы, чтение upstream SSE, преобразование событий, выбор транспорта, fallback, watchdog, статусные сообщения, управление helper-процессом и его группой, lease-файлы и стартовая уборка.

   Дополнительно изменены остановка legacy-групп процессов, обнаружение отключения клиента, ограничение stderr-буфера, маскирование секретов, возврат резерва spawn limiter и диагностическая строка `O-EXIT/v1`. Значительная часть остальных изменений — форматирование.

2. **Изменён `bridges/opencode-zen-bridge/tests/test_step_interruption.py`.**

   Скорректированы ожидания общего потолка запусков: сценарии, ранее ожидавшие четыре запуска, теперь ожидают три и завершение без инструментальных вызовов. Добавлен сценарий «недоступный native-инструмент → незавершённый шаг → корректные вызовы» за три запуска.

   Для каждого теста создаётся свежий `_Resilience`; часть тестового окружения изолирована через `mock.patch.dict`.

3. **Добавлен `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py`.**

   Содержит legacy fake CLI, FakeServe, HTTP/SSE-клиент с временными метками, проверки транспорта, статусов, watchdog, инструментальных событий, fallback, бюджетов, очистки процессов и fault injection.

**Не представлены как изменения файлов:** `dynamic_config.json`, отдельный helper-скрипт, launcher, файлы каталога моделей и эксплуатационная документация. Helper реализован ранней CLI-веткой самого `server.py`.

## 2. Реконструируемое поведение системы

### 2.1. Новый транспорт и условие включения

Добавляется транспорт `serve` рядом с существующим `run`.

Для каждой serve-попытки мост:

1. Формирует отдельное окружение и каталог состояния.
2. Запускает helper, который запускает `opencode serve`.
3. Проверяет принадлежность слушателя своей группе процессов.
4. Проверяет готовность API, создаёт сессию и подписывается на события.
5. Отправляет prompt параллельно чтению SSE.
6. Преобразует события в существующий клиентский формат.
7. Прерывает и удаляет сессию, затем очищает процессы и ресурсы.

Общего долгоживущего serve-процесса между попытками здесь нет.

Выбор `_select_transport()` имеет следующий приоритет:

- `OPENCODE_ZEN_BRIDGE_TRANSPORT=run` всегда выбирает `run`.
- Отрицательное значение `OPENCODE_ZEN_BRIDGE_REALTIME_SERVE_ENABLED` — `0`, `false`, `no`, `off` — выбирает `run`, включая принудительный режим `serve`.
- Существующий disable-файл выбирает `run`. Путь по умолчанию: `~/.dsh/bridges/opencode-zen-bridge/disable-serve`; переопределяется через `OPENCODE_ZEN_BRIDGE_SERVE_DISABLE_FILE`.
- После этих проверок `TRANSPORT=serve` принудительно выбирает `serve`.
- Неизвестное значение `TRANSPORT` выбирает `run`.
- В режиме `auto`, используемом по умолчанию, sticky-деградация запрещает `serve`.
- Для `auto` дополнительно требуется положительный env override либо JSON boolean `REALTIME_SERVE_ENABLED: true` в `dynamic_config.json`.
- В `auto` бинарь должен пройти проверку сигнатуры нативного исполняемого файла. Shebang-скрипты исключены; тестовый `SERVE_TEST_ELIGIBLE` обходит эту проверку.

Принудительный `serve` обходит проверку бинаря, JSON-флага и sticky-деградации, но не два аварийных отключателя выше.

JSON-конфигурация перечитывается при изменении пары `(mtime_ns, size)`. Отсутствующий, нечитаемый или некорректный файл, повреждённый UTF-8 и значение другого типа означают `false`. Строка `"yes"` не включает флаг.

**Фактический дефолт:** при отсутствии включающей конфигурации используется `run`. Реализации удалённого GigaRC-конфига в diff нет: показан локальный JSON-файл.

Выбор выполняется при входе в обработку запроса. Изменение kill-switch не прерывает уже выполняющуюся serve-попытку.

### 2.2. Потоковая передача событий

Upstream-события преобразуются в канонические события моста:

- `session.reasoning.delta` → `reasoning_content`;
- `session.text.delta` → `content`;
- `session.step.ended` → usage шага;
- `session.execution.failed` и `session.step.failed` → ошибка;
- `permission.asked` → обработка разрешения;
- `form.created` → отмена формы;
- `session.tool.*` → накопление native-вызова.

Для reasoning/text обязательны строковая дельта и непустой `sessionID`. Пробельные дельты маппер сохраняет. События с явно чужим `sessionID` отбрасываются; для формы принадлежность определяется по вложенному `form.sessionID`. Для части других событий отсутствие `sessionID` допускается.

`server.connected` не считается началом выполнения модели. Пустые heartbeat и некоторые служебные события игнорируются.

SSE читается отдельным потоком в очередь размером 4096 элементов. Prompt отправляется другим потоком, поэтому reasoning может передаваться клиенту до завершения HTTP-ответа на prompt.

Входной парсер обрабатывает отдельные строки `data:` как самостоятельные JSON-объекты. Пустые payload и `[DONE]` игнорируются. Полная поддержка многострочных SSE-полей `data:` не показана.

### 2.3. Клиентские чанки, инструменты и usage

Для клиента сохраняется существующая упаковка через `format_sse_chunk()`:

- reasoning передаётся через `delta.reasoning_content`;
- текст — через `delta.content`;
- вызовы — через `delta.tool_calls`;
- успешное завершение содержит `finish_reason` и usage;
- затем отправляется `data: [DONE]`.

При ошибке после открытия SSE отправляются объект `{"error": ...}` и `[DONE]`, без успешного `finish_reason`.

Текстовые `<tool_call>` / `<tool_invoke>` блоки проходят через существующий `ToolCallParser`. Native-вызовы используют существующий `_native_to_tool_calls`, включая адаптацию аргументов и `multiedit`. Выполнение DSH-инструмента остаётся обязанностью клиента.

Usage складывается по шагам и попыткам, включая неуспешные попытки, вернувшие usage:

- `tokens.input` → `input`;
- `tokens.output` → `output`;
- `tokens.reasoning` → `reasoning`;
- `tokens.cache.read` → `cached`.

`cache.write` не учитывается. Повторный шаг подавляется по `assistantMessageID`, если он присутствует. Без этого идентификатора защиты от повторного учёта шага нет. При отсутствии или нулевом значении итоговых input/output используется оценка токенов по тексту.

### 2.4. Статусные строки `[мост]`

Синтетические статусы отправляются отдельными reasoning-дельтами:

- `[мост] Подключение к модели…\n`;
- `[мост] Ожидание первого токена…\n`;
- `[мост] Ожидание продолжения…\n`;
- `[мост] Повтор попытки N/M…\n`.

Они включены только при непустом effort, отличном от `off` и `none`. Это условие управляет синтетическими статусами; модельные reasoning-события отдельно им не блокируются.

Начальный статус обслуживает защитный таймер с целевым сроком 0,65 секунды от начала бюджета обработки. Уже появившийся модельный текст, reasoning или tool call подавляет его. Статусы ожидания повторяются с интервалом 5 секунд; при паузе после токена статус продолжения появляется после 15 секунд.

Если последняя модельная reasoning-дельта не завершена LF, перед статусом добавляется перевод строки. Записи основного потока и таймера сериализуются общим замком.

Начальный таймер создаётся после получения слота и открытия SSE. Поэтому код не гарантирует первый статус за одну секунду от HTTP-запроса при долгом ожидании свободного слота.

Маркеры обрыва ответа удаляются. В serve SSE для текста добавлен буфер, распознающий маркер, разрезанный между дельтами. Для reasoning аналогичного межчанкового буфера не показано.

### 2.5. Жизненный цикл процессов, портов и состояния

Helper запускается командой вида:

```text
python -I server.py --serve-helper <attempt_id> <port> <opencode_bin> <lease_dir> <parent_pid> <parent_lstart>
```

Он получает новую сессию процессов и становится лидером группы. Дочерний `opencode serve` запускается в той же группе:

```text
opencode serve --hostname 127.0.0.1 --port <port>
```

Связь с родителем поддерживает pipe, подключённый к stdin helper. EOF, ошибка lifeline, SIGTERM или завершение serve запускают уборку.

Helper:

- атомарно публикует lease через временный файл и `os.replace`;
- сообщает родителю `serve_pid` и PGID;
- дренирует stdout и stderr serve;
- при остановке посылает SIGTERM своей группе;
- ждёт до 4 секунд;
- посылает SIGKILL оставшимся членам группы;
- проверяет их исчезновение ещё до 2 секунд;
- удаляет lease только после исчезновения остальных членов группы.

Родительский `_ServeLease.cleanup()` идемпотентен. Он закрывает lifeline, завершает свою группу, закрывает потоки и удаляет состояние попытки. Порт из `_ACTIVE_SERVE_PORTS` освобождается после подтверждения исчезновения группы.

Порты выбираются перебором от `20000 + pid % 20000` до 59999. Внутрипроцессный lock и набор активных портов предотвращают повторное назначение внутри одного моста. Предварительный bind закрывается до старта serve, поэтому межпроцессная гонка остаётся; затем принадлежность слушателя проверяется через `lsof`, PID и PGID.

Lease-каталог по умолчанию — `/tmp/opencode-zen-bridge-leases`. Проверяются его владелец и отсутствие симлинка; устанавливаются права `0700`.

При старте моста `_startup_reaper()` проверяет оставшиеся lease. Живой родитель защищает запись от уборки. Для живых PID сверяется время запуска; перед убийством группы дополнительно проверяется наличие `--serve-helper` в командной строке.

Legacy `_stop_proc()` теперь завершает живую группу и после выхода её лидера.

### 2.6. Окружение и локальная авторизация

Serve-окружение строится на основе существующего `_run_env()`, затем фильтруется allowlist.

Добавляются:

- отдельный временный `XDG_STATE_HOME`;
- тот же каталог в `TMPDIR`;
- `OPENCODE_DB=:memory:`;
- случайный `OPENCODE_SERVER_PASSWORD`;
- политика permission в `OPENCODE_CONFIG_CONTENT`.

`OPENCODE_BIN` удаляется из окружения дочернего serve. Произвольные env-секреты не наследуются; разрешённые proxy/config-переменные сохраняются.

Локальный API вызывается напрямую через `http.client` на loopback, с Basic-авторизацией пользователя `opencode`. Эти локальные HTTP-вызовы не используют HTTP-прокси из окружения.

### 2.7. Таймауты и watchdog

Для serve введены настройки:

- `OPENCODE_ZEN_BRIDGE_FIRST_EVENT_TIMEOUT_S`: по умолчанию 20 секунд;
- `OPENCODE_ZEN_BRIDGE_FIRST_TOKEN_TIMEOUT_S`: 60 секунд;
- `OPENCODE_ZEN_BRIDGE_STALL_TIMEOUT_S`: 60 секунд.

Окна first-event и first-token отсчитываются от начала отправки prompt. First-token проверяется после появления первого события выполнения. Reasoning, текст и готовый native-вызов могут установить first-token; дельты native-input обновляют активность, но сами first-token не устанавливают.

Дополнительно действуют общий deadline запроса и отдельные ограничения setup-фаз: handshake, проверка слушателя, readiness и HTTP-вызовы.

В legacy SSE watchdog проверяется при тишине и при поступлении строк: служебный поток без токенов не должен бесконечно продлевать выполнение. Существенное отличие: first-token timeout здесь равен **максимуму конфигурации и 120 секунд**.

Для legacy non-stream JSON в diff добавлена проверка отключения клиента; аналогичные новые first-event/first-token/stall watchdog в `Run.execute()` не показаны.

Отключение клиента определяется через неблокирующий socket peek: FIN, RST и закрытый файловый объект считаются отменой.

### 2.8. Интерактивные и инструментальные события

Политика serve задаётся `OPENCODE_ZEN_BRIDGE_SERVE_PERMISSION_POLICY`:

- `ask_reject`, по умолчанию, передаёт permission `ask`;
- `deny` передаёт `deny`;
- другое значение вызывает `ServeSecurityError`.

На `permission.asked` мост:

1. Закрывает шаг для дальнейшего текста/reasoning.
2. Отправляет `decision: reject`.
3. Посылает interrupt.
4. Продолжает обрабатывать последующие инструментальные события.

На принадлежащую сессии `form.created` мост сначала отменяет форму и посылает interrupt, независимо от наличия title/fields. Результат — отменённая попытка с клиентской ошибкой. Отсутствующий ID своей формы также считается ошибкой безопасности.

Native tool state хранится по call ID. Аргументы берутся из готового `input` либо JSON в `text`; повторная выдача одного ID подавляется. Дельты input отдельно не склеиваются: предполагается последующий полный `text` или `input`.

При завершении шага наличие native-вызовов либо распознанного текстового вызова в режиме эмуляции завершает попытку как `tool_calls`.

### 2.9. Ошибки, ретраи и fallback

Serve и run используют общий объект попыток, deadline и потолок запусков. Значение `MAX_TOTAL_SPAWNS` по умолчанию — 3. Переход на run не начинает бюджет заново.

Используются существующие spawn limiter, retry budget, circuit breaker и jitter backoff. Для legacy spawn-ошибок добавлен возврат резерва limiter. Аналогичного возврата для serve setup/spawn-отказов не показано; serve-попытка учитывается до фактического запуска helper.

Fallback на run разрешён только в `auto` и до барьера доставки. Барьер учитывает модельный вывод, native-вызовы и, в некоторых ветках, получение prompt response headers. Он монотонен между попытками. Синтетический статус сам по себе барьер не устанавливает.

Основные ветки:

- setup/ownership/readiness failure до доставки → fallback в `auto`;
- first-event timeout без доставки → fallback;
- timeout или протокольный отказ после доставки → serve retry в пределах бюджетов;
- HTTP 401/403 и HTTP 400/404/422 на показанных API-фазах → fail-closed;
- prompt HTTP 429/5xx → повтор с учётом upstream breaker;
- transient stream error → fallback до доставки либо ограниченное recovery;
- client cancellation → прекращение обработки без успешного ответа.

Для недоступных native-инструментов и незавершённых инструментальных шагов используются существующие перепромпты и отдельные счётчики повторов под общим потолком. Текстовый префикс повторного ответа подавляется; JSON дополнительно дедуплицирует вызовы по имени и аргументам.

`_ServeHealth` после трёх зарегистрированных отказов отключает serve в `auto` на 120 секунд. Успешная попытка сбрасывает деградацию. Ошибки безопасности её не увеличивают.

**`FALLBACK_DECISION_TABLE` — декларативное описание.** Исполнение реализовано отдельными условными ветками; таблица сама ими не управляет.

## 3. Внешние контракты и инварианты

### 3.1. Добавленные внутренние HTTP/SSE-контракты

Мост зависит от следующих serve API:

- `GET /api/session/active`;
- `POST /api/session`;
- `GET /api/event`;
- `POST /api/session/{id}/prompt`;
- `POST /api/session/{id}/permission/{request_id}/reply`;
- `POST /api/session/{id}/form/{form_id}/cancel`;
- `POST /api/session/{id}/interrupt`;
- `DELETE /api/session/{id}`.

Создание сессии передаёт directory, provider/model/variant и permissions. Prompt передаётся как:

```json
{"text": "...", "files": [], "delivery": "steer", "resume": true}
```

Mapper и фикстуры ориентированы на wire-формат v2.1.2. Проверки версии реального serve через `/api/info` в production-коде не показано.

### 3.2. CLI, env и файловые контракты

Добавляются:

- CLI-режим `--serve-helper` с шестью позиционными аргументами;
- команда `opencode serve`;
- env-настройки транспорта, аварийного отключения, permission policy и watchdog;
- локальный `dynamic_config.json`;
- disable-файл;
- lease JSON с идентификаторами владельца, процессов, группы и порта;
- временный каталог состояния попытки.

Эксплуатационная среда должна предоставлять `ps`, `lsof`, process groups и POSIX-сигналы.

### 3.3. Публичный OpenAI-совместимый контракт

**Пути и основная форма ответов сохранены:**

- `/health`;
- `/v1/models` и `/models`;
- `/v1/chat/completions`;
- существующий SSE formatter и `[DONE]`;
- существующая клиентская авторизация.

В `/health` значение `transport` остаётся `"opencode-zen-cli"`, даже когда реально выбран serve. Новый транспорт и sticky-деградация там явно не отражаются. Инициализационное значение `CATALOG_SOURCE` изменено с `"init"` на `"static"`.

Схема SSE не заменена, но наблюдаемое поведение меняется:

- появляются синтетические reasoning-дельты;
- reasoning передаётся непосредственно из serve SSE;
- добавляются watchdog-ошибки;
- меняются временные характеристики и последовательность recovery.

Для non-stream serve сохраняется `chat.completion`, assistant message, tool calls и usage.

### 3.4. Сохранённые маршруты и функции

Прямой Google-маршрут обходит новый выбор serve. Для `_stream_google_sse`, `_execute_google_once` и `_run_env` добавлены тесты на фиксированные хеши исходного текста.

Переиспользуются существующие каталог моделей, alias resolution, variant selection, prompt construction, инструментальный parser, native mapping и recovery helpers. Их полная неизменность по отсутствующим частям исходника не устанавливается; в показанных местах значительная часть diff — форматирование.

Старый launcher остаётся зависимостью потокового пути: проверка его исполнимости выполняется **до** выбора serve.

В `O-EXIT/v1` добавлены `transport`, `transport_history`, `first_event_ms` и `ttft_ms`. Сообщения ошибок и детали дополнительно очищаются от Bearer-токенов, server password и proxy credentials.

## 4. Покрытие тестами и граничные случаи

### 4.1. Realtime, статусы и watchdog

Новые тесты проверяют:

- пять reasoning-дельт до завершения upstream;
- задержку передачи каждой дельты менее 0,25 секунды на FakeServe;
- порядок reasoning перед content;
- сохранение паузы SSE в 1,4 секунды;
- отсутствие синтетического статуса для быстрого legacy-ответа;
- начальный статус не позднее секунды при медленном ответе, занятом StartupGate и задержанном limiter;
- единственный начальный статус;
- разделители повторов для watchdog/unmapped/incomplete recovery;
- отключение разделителей при effort `off`;
- first-event, first-token и stall timeout;
- обновление активности native-вызовом;
- отсутствие успешного учёта timeout, client_gone и cancelled;
- исключение исторического `reasoning_content` из следующего prompt.

В тестах короткие watchdog-окна задаются подменой констант. Реальные дефолтные интервалы этим не измеряются.

### 4.2. Выбор транспорта и деградация

Проверяются:

- переключение boolean JSON-флага и восстановление после повреждения файла;
- выключенное значение при строковом флаге;
- `TRANSPORT=run`, отрицательный override, опечатка транспорта;
- приоритет disable-файла над forced serve;
- сигнатуры ELF/Mach-O и отклонение shebang/случайных байтов;
- setup HTTP 503 → auto fallback;
- sticky-деградация после трёх таких запросов;
- запрет fallback после reasoning или prompt headers;
- общий spawn cap для serve и run;
- единичное списание retry budget в показанных сценариях;
- закрытие upstream breaker после успешной HALF_OPEN-пробы.

Тест JSON-флага непосредственно проверяет reader; название «тот же Server: false → run, true → serve» шире фактических assertions этого отдельного теста.

### 4.3. Инструменты и интерактивные события

Покрыты:

- текстовый tool block, разрезанный между SSE-дельтами;
- native tool lifecycle;
- преобразование bash/read/edit/list/multiedit через канонический mapper;
- дедупликация одинаковых JSON tool calls из native и текста;
- сохранение `tool_choice` в recovery prompt;
- закрытие эмулированного инструментального шага;
- отмена формы без title и отсутствие `STEP2`;
- очистка частичного tool block при JSON recovery;
- подавление повторной преамбулы;
- удаление interruption-маркера при нескольких границах разреза.

Тест с названием `split_interrupted_marker_at_every_boundary` перебирает три разреза, а не все границы.

Тест permission/native проверяет наличие `bash` в клиентских вызовах. Он не утверждает напрямую, что FakeServe получил reject и что реальный встроенный инструмент не выполнился.

### 4.4. Fault injection и ресурсы

Проверяются:

- `mkdtemp` с ENOSPC;
- ошибки `pipe` и `Popen` без оставшихся FD, портов и state directory;
- подмена слушателя чужим PID;
- startup reaper для мёртвого и живого родителя;
- очистка группы, игнорирующей SIGTERM;
- остановка потомка после выхода лидера;
- surviving grandchild helper-группы;
- некорректный stdin helper;
- stderr больше 64 КиБ без блокировки FakeServe;
- FIN, RST и закрытый `rfile`;
- истёкший deadline и client cancellation до HTTP connect;
- prompt headers с последующим reset или зависшим телом;
- классификация 401 до завершения чтения тела;
- отсутствие секретов в SSE, JSON и логах;
- JSON decoding, surrogate pair и пробельные дельты;
- однократная ротация прокси на serve-попытку.

Обновлённые step-interruption тесты закрепляют общий лимит в три запуска и успешную комбинацию двух разных recovery-причин внутри этого лимита.

### 4.5. Видимые пробелы и риски

1. **Нет подтверждения на реальном OpenCode.** Основная интеграционная среда — FakeServe, реализующий ожидаемый протокол. Проверки версии и capability negotiation не показаны.

2. **Таблица fallback не гарантирует фактическую классификацию.** Например, ветка stream `error` не переносит факт prompt headers в `result["delivered"]`. При отсутствии модельного вывода auto-код может разрешить fallback, несмотря на ранее полученные заголовки. Тесты headers-barrier покрывают prompt HTTP failures, но не этот вариант SSE error.

3. **Общий deadline не охватывает все фазы одинаково.** `_serve_http()` проверяет оставшийся бюджет между фазами; `_spawn_serve()` использует собственные окна, а подключение `/api/event` имеет отдельный socket timeout. Gate, limiter и cleanup также могут увеличить итоговое время ответа.

4. **Prompt-поток может пережить основной цикл.** Join ограничен 0,5 секунды, а prompt connection принадлежит worker-потоку. Последующая остановка serve обычно оборвёт соединение, но немедленное завершение worker не доказано.

5. **Входные буферы ограничены не полностью.** Очередь SSE ограничена числом объектов, но размер отдельной SSE-строки и HTTP response body не ограничен. Кольцо stderr ограничено строками, а не байтами.

6. **Некоторые terminal-события принимаются без session ID.** Фильтрация защищает от явно чужой сессии, но не требует принадлежность для всех событий.

7. **Usage-валидация частичная.** Для input/output/reasoning исключён boolean, но `cache.read` принимает `bool` как `int`; отрицательные значения не запрещены. Без `assistantMessageID` повторный шаг может учитываться дважды.

8. **Результаты SSE и JSON различаются на пустом выводе.** JSON serve возвращает 502, если нет content и tool calls, даже при reasoning. SSE может завершиться успешным `stop` после terminal success без этих полей.

9. **Recovery сохраняет частичный вывод неодинаково.** SSE уже передаёт текст клиенту. JSON для некоторых timeout/protocol retry-веток не добавляет текст неуспешной попытки в итоговый content, хотя usage учитывает.

10. **Проверки безопасности процессов не исчерпывающие.** Нет показанных end-to-end тестов смерти настоящего родителя, PID reuse, symlink/foreign-owner lease, независимых bridge-процессов с гонкой порта и массовых параллельных отмен.

11. **Некоторые тестовые названия шире assertions.** Не доказаны успешный helper-запуск с произвольным lease-каталогом, TTL-восстановление деградации, отсутствие статуса именно у быстрого serve и полноценное отбрасывание чужой сессии на живом потоке.

12. **Часть тестов зависит от окружения.** Legacy-группа не фиксирует транспорт явно; тесты меняют глобальные переменные модуля и env. Их параллельное выполнение в одном процессе требует дополнительной изоляции.

13. **Kill-switch действует на следующие запросы.** Для уже запущенного serve нет показанного live-прерывания после изменения env, JSON или disable-файла.

Все перечисленные риски — наблюдения по предоставленному коду. Они не являются результатами запуска тестов или приёмки изменения.
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
Ниже приложены целиком реестр фактов и план исследования аналитического этапа (`evidence-ledger.md`, `research-plan.md`), манифест подпроекта (`bridges/opencode-zen-bridge/pyproject.toml`), рубрика подкатегорий и правила повторного цикла Совета (`council.md#L379-L463`) и первичные артефакты выбора мест раунда `panel/council/r56`:
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
<<<ARTIFACT ~/Мой диск/skils/ai-sdlc/universal/teamlead-gate/references/council.md#L379-L463 sha256=55fd356ed8631b68d5b472183870648c2929d6679e2908e5639f73be88eb87bd
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

### Полнота прохода: батч, не капельница

- Цель: один тимлид-цикл закрывает ВСЕ известные дефекты кандидата; режим «одна
  ошибка за итерацию» — дефект процесса.
- Судья: запреты и предписания блока «ПОЛНОТА ВЫДАЧИ» (§1).
- Malformed (дополнение к рубрике; в R1 — D-раунд и C1 по `council-consensus.md` §4): нет COVERAGE/FINDINGS_COMPLETE; k<K; N ≠ числу
  F-блоков; F-блок без file:line/evidence/priority; «и т.п.» вместо перечня мест.
  Один malformed-retry тем же слотом, как для SUB-строк.
- В батч идут все F-блоки леджера; перепроверка FAIL (universal-panel ШАГ 1)
  передаётся судьям строками RECHECK, находку вычёркивает только совещание
  (`council-consensus.md` §3, §6); отсев — `WITHDRAWN` и `outcome` excluded (причина —
  `invalid_after_recheck`/`duplicate_of`/`out_of_scope`/`foreign_key`), фиксируется в леджере.
- D-раунды (бывший R2) не для вброса отложенных находок: новые blocking после R1
  имеют метку [late-R2] и идут в отдельный счётчик `r2_late` (не в `late_miss`);
  метка прежняя, новых имён нет.
- Метрика цикла N≥2: `late_miss` = число новых blocking вне дельты (кроме регрессий
  самой правки). Регрессию правки (дефект, внесённый строками дельты sha-N..sha-N+1)
  классифицирует оркестратор по git-дельте. late_miss ≥1 → «пропуск судьи» в
  traceability; ≥1 два цикла подряд → эскалация владельцу.
- Словарь меток: `[pre-existing]` — замечание вне дельты цикла; `late_miss` — метрика
  (в SKILL.md и леджере то же событие зовётся «пропуск судьи»); `[late-R2]` →
  счётчик `r2_late`. Других имён (LATE-MISS и т.п.) не вводить.

### F-NNN и кумулятивный дедуп-леджер циклов

- Каждый finding судьи получает ID F-NNN; RW-NNN в `panel-rework-brief.json`
  наследует номера F. Классификацию повторов ведёт оркестратор по леджеру —
  судьи новых замечаний ID не знают.
- Леджер цикла `cycle-<N>/findings-ledger.md` содержит находки этого цикла
  (`findings_total` = их число) — не открытые на конец совещания, а все выданные в
  цикле, со статусами завершённого совещания (в том числе `WITHDRAWN` и `outcome`
  excluded, они уходят в `excluded[]`; `council-consensus.md` §9); кумулятивный
  дедуп-леджер хранит историю циклов и статусы open/closed. Закрытые находки прошлых
  циклов в леджер цикла не переносятся — их id встречаются лишь в прозе (`excluded` не нужен).
- Ключ дедупа: совпадение места (file:line-диапазон) И мета-класса/критерия И
  сути претензии; совпадение только места ≠ дубль (другой root cause в том же
  месте — НОВОЕ). Fail-safe: не уверен — считай НОВЫМ с пометкой «спорно».
  Спор об одном и том же ID два цикла подряд — эскалация владельцу.
- Finding гасится только «закрыто кодером И верифицировано повторным Советом»
  (verify-fixed зелёный); повторный FAIL по погашенному ID = «повтор без
  нового основания», в агрегацию не идёт.

### Diff-scope повторного цикла

- Каждый тимлид-цикл заканчивается коммитом, его SHA — в леджере; дельту
  sha-N..sha-N+1 готовит оркестратор чистой git-механикой (`git diff` +
  hunk-выжимка по каждому RW-NNN), это механика, не LLM-суждение.
- Цикл N+1: (а) verify-fixed по каждому RW-NNN предыдущего цикла —
  зелёный/красный + evidence; (б) новые проблемы — в изменённых строках дельты;
  замечания вне дельты выдаются только с меткой [pre-existing] (§1, «ПОЛНОТА ВЫДАЧИ» п.7):
  · в коде, не затронутом задачей (вне скоупа) → non-blocking follow-up или отдельная
    задача; NEEDS WORK не даёт, ACCEPT не блокирует;
  · в изменённом файле задачи, пропущенный судьями в Раунде 1 → blocking, идёт в
    `late_miss`.
  ACCEPT — когда открытых blocking нет: «0 новых blocking» не отменяет поиска вне дельты
  в изменённых файлах (п.7). Первый цикл — всегда полный diff. Clean-room execution-gate
  (Шаг 2 скилла) остаётся полным (L2 заново на новый SHA): diff-scope касается только обзора Совета.
- Полный повторный обзор всего артефакта — только при RED FLAG или смене
  архитектуры.

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
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/panel/council/r65/manifest.json sha256=50db0169340c7927aabba350e9c3e184a1a4c50e5c60962fc0d172d45203faf5
{"artifact_sha256":"c9530b1b9b6113a97457c299f4970c7a2a5ad6a55605bbd243c97a09c5a85da4","constrained_mode":null,"debate_roster_mode":"rotated","excluded_author":[],"hat_level":1,"history_entry_sha256":"73d63ca8467752ae196f71af247398b7d04c20a332d629dae48eddc1263aeacc","history_prev_entry_sha256":"c8a82e84a9d6e46f58a5c832f64bfdfc15b7881fe617dfec71eae3e32e3cd0ea","history_seq":88,"models_md_sha256":"e032139c9fc67e082ea33e7bd390779c7a2d98f066d71a83e4c7d793c3ecc6c4","pool_constrained_3of3":false,"prior_ledger_sha256":"0a7ff9a103dc59a5b65513c6978a0a11da4aa1e6a740e00721e9e0e9593fed69","ranked_order":["gpt-6.1-sol-high","grok-4.7-high","muse-wonder-full-1.0","claude-sonnet-5-5-high","gemini-4-argon-high"],"replaced_seats":[],"round":65,"run_id":"analyst-teamlead-zen-realtime-reasoning-20261025","schema":"pol-manifest/2","seats":[{"family":"Meta","k":1,"slot_id":"muse-wonder-full-1.0","transport":"muse"},{"family":"xAI","k":2,"slot_id":"grok-4.7-high","transport":"cursor-agent"},{"family":"OpenAI","k":3,"slot_id":"gpt-6.1-sol-high","transport":"codex"}],"seed_hex":"37c1ac06204c40dc152305bc9eca22bfff241059e553ab54fc4f1ac49e736ef5","seed_input":"analyst-teamlead-zen-realtime-reasoning-20261025:council:r65:c9530b1b9b6113a97457c299f4970c7a2a5ad6a55605bbd243c97a09c5a85da4:c8a82e84a9d6e46f58a5c832f64bfdfc15b7881fe617dfec71eae3e32e3cd0ea","selector_sha256":"96c525ac5ec3c0c9761f4e7789fe656cb04a86300e2bd9d0059854474842894d","setup":"default","stage":"council","status":"READY","triplet_rule":"A+B","unavailable_evidence":{}}
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
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/cycle-5/debate/r1/realist.md sha256=3962298cb5e150244c322a967931851bb425dcd27d5f4125234e95dfb04116b3
> PANEL-NONCE: 56b00e2947af04e8
> ARTIFACT-SHA256: c9530b1b9b6113a97457c299f4970c7a2a5ad6a55605bbd243c97a09c5a85da4
>
> 1. КОРРЕКТНОСТЬ: VERDICT=FAIL
>    WHY=RW-001 закрыт для HTTP-ошибок prompt, но остался обход через ошибку выполнения из SSE: полученные заголовки не сохраняются в `delivered`, после чего разрешается переход на `run`. Также legacy SSE принудительно увеличивает настроенный first-token timeout до 120 секунд.
>
>    СОВЕТЫ (при FAIL): сохранять барьер доставки независимо от способа завершения попытки; различать получение заголовков и выдачу модельного текста при выборе recovery; убрать нижнюю границу 120 секунд; добавить регрессионные сценарии F-001 и F-002.
>
>    SUB Корректность/логика: FAIL — после принятых заголовков SSE-ошибка может разрешить повтор через другой транспорт (`server.py:3552`, `server.py:5619`, `server.py:6911`; RW-001).
>    SUB Корректность/граничные условия: FAIL — значение FIRST_TOKEN_TIMEOUT_S меньше 120 секунд не соблюдается на legacy SSE (`server.py:6235`; REQ-007).
>    SUB Корректность/обработка ошибок: FAIL — ветка `etype == "error"` не переносит подтверждение доставки prompt в результат (`server.py:3553`; FALLBACK_DECISION_TABLE).
>
> 2. ПОЛНОТА: VERDICT=FAIL
>    WHY=RW-002, RW-003 и RW-004 принимаются по коду и включённым в зелёный L2 регрессионным тестам. Однако legacy JSON получил только проверку отключения клиента, без трёх требуемых watchdog. Свидетельство AC-016 также неполно: существующие сценарии step interruption исполняются через fake-CLI legacy-пути, а не все повторены на serve. Отдельного сравнительного сценария AC-017 для unmapped recovery нового транспорта в пакете нет.
>
>    СОВЕТЫ (при FAIL): добавить watchdog в JSON-путь `Run`; обеспечить одинаковую классификацию таймаутов в SSE и JSON; прогнать существующую матрицу step interruption на обоих транспортах; добавить serve-сценарий unmapped → повтор → итоговый `finish_reason`.
>
>    SUB Полнота/покрытие AC: FAIL — AC-016 и AC-017 не подтверждены требуемой матрицей нового транспорта (`tests/test_step_interruption.py:171`, `server.py:1911`; F-004).
>    SUB Полнота/пропущенные ветки: FAIL — JSON legacy контролирует client_gone, но не first-event/first-token/stall (`server.py:5094`; REQ-006, REQ-007).
>
>    Verify-Fixed:
>
>    - RW-001 — **FAIL, частично исправлен**: HTTP 200 + обрыв тела и HTTP 429/503 покрыты; SSE execution failure после заголовков остаётся F-001.
>    - RW-002 — **PASS**: защитный таймер сохраняется; тест задержки лимитера на 0,5 секунды проверяет единственный статус до секунды (`server.py:5964`; `tests/test_realtime_reasoning.py:504`).
>    - RW-003 — **PASS** для трёх заданных recovery-веток и thinking on/off (`tests/test_realtime_reasoning.py:526`).
>    - RW-004 — **PASS**: native input delta и готовый вызов обновляют активность (`server.py:3502`, `server.py:3512`; тест `:1826`).
>    - FU-001 — **PASS**, совместно с RW-003.
>    - FU-002 — **PASS**: статус публикуется из callback заголовков; зависшее тело 401 покрыто тестом `:1836`.
>    - FU-003 — **PASS** для указанного частичного tool-блока и дедупликации преамбулы, тест `:1339`.
>    - FU-004 — **PASS**: независимые времена отправки и получения каждой дельты, тест `:682`.
>    - FU-005 — **PARTIAL**: HTTP-ветки используют RetryBudget; обход F-001 сохраняется.
>    - FU-006 — **PARTIAL**: cleanup получил аргументы deadline, но старт их не получает, а блокирующие HTTP-фазы не обеспечивают жёсткий абсолютный предел — F-005, F-007.
>    - FU-007 — **принято в backlog**, переписывание unittest в этом цикле не требуется.
>
>    Поштучная сверка требований и AC:
>
>    - REQ-001 — PASS; AC-001 — PASS; AC-002 — PASS: socket oracle с независимыми timestamp, тест `:682`, VER-005.
>    - REQ-002 — PASS; AC-003 — PASS: публичные пути и формат сохранены; существующие проверки зелёные.
>    - REQ-003 — PASS; AC-004 — PASS: выключенный serve сохраняет legacy; полный компонентный набор — 451 passed.
>    - REQ-004 — PASS в заявленном окне после открытия SSE; AC-005 — PASS для проверенных задержек gate/limiter, тест `:504`.
>    - REQ-005 — PASS на представленных оракулах; AC-006 — PASS; AC-007 — PASS: модельные дельты сверяются, reasoning истории исключён, тесты `:682`, `:572`.
>    - REQ-006 — FAIL; AC-008 — FAIL для legacy JSON, F-003.
>    - REQ-007 — FAIL; AC-009 — FAIL для legacy JSON; AC-010 — FAIL для legacy JSON и настроек legacy SSE ниже 120 секунд, F-002/F-003.
>    - REQ-008 — FAIL по границам стартовых и cleanup-фаз; AC-011 — FAIL; AC-012 — FAIL для этих сценариев, F-005/F-007.
>    - REQ-009 — FAIL по сохранению delivery/retry-инварианта, F-001; AC-013 — PASS по общему потолку; AC-014 — PASS на проверенной матрице разделителей.
>    - REQ-010 — PASS; AC-015 — PASS: существующий parser и новые разрезанные tool-дельты, тест `:793`, полный L2.
>    - REQ-011 — INCONCLUSIVE в полном объёме; AC-016 — FAIL по полноте проверки serve, F-004.
>    - REQ-012 — INCONCLUSIVE по требуемой эквивалентности unmapped recovery; AC-017 — FAIL по доказательству, F-004. Наличие ask/reject обработки подтверждено.
>    - REQ-013 — PASS по коду сохранённой ротации и защит; AC-018 — PASS по композиции frozen `_run_env` и проверке одного обращения к пулу на попытку.
>    - REQ-014 — PASS; AC-019 — PASS по отображению полей usage и проверке суммирования попыток.
>    - REQ-015 — PASS на проверенных каналах; AC-020 — PASS: маскирование SSE/JSON/log, тест `:1388`.
>    - REQ-016 — PASS; AC-021 — PASS: обязательные поля присутствуют в реальных строках O-EXIT приложенного L2.
>    - REQ-017 — PASS; AC-022 — PASS; AC-023 — PASS: полный и обратный порядок — 451 passed.
>    - REQ-018 — PASS; AC-024 — PASS: frozen SHA и неизменённый Google-набор подтверждены VER-004.
>    - REQ-019 — DEFERRED_L3; AC-025 — DEFERRED_L3: законная отсрочка до ACCEPT.
>    - REQ-020 — PASS; AC-026 — PASS на кандидате: проверяется получение дельт до завершения FakeServe; baseline sensitivity имеет rc=1.
>
> 3. РЕАЛИЗУЕМОСТЬ: VERDICT=FAIL
>    WHY=Выбранный транспорт технически осуществим на подтверждённом окружении: Python stdlib, установленный opencode v2.1.2, POSIX process groups, ps/lsof. In-memory DB устраняет зависимость попытки от общей SQLite. Но rollout пока блокируют неполная отмена старта и взаимная блокировка диагностических пайпов при большом стартовом выводе.
>
>    СОВЕТЫ (при FAIL): передавать deadline и отмену через весь startup; проверять остаток бюджета до запуска helper; запускать stderr-дренаж сразу после Popen; добавить fault injection на отмену setup и многомегабайтный stderr до открытия порта.
>
>    SUB Реализуемость/общее: FAIL — старт не получает общий deadline/cancellation, а дренаж stderr начинается только после появления listener (`server.py:2731`, `server.py:2844`; F-005/F-006).
>
>    Практическая оценка оставшейся работы — примерно **2–3 инженерных дня** на исправления и расширение матрицы проверок, затем живой rollout. Это оценка, а не подтверждённый срок. Для L3 нужны существующий чат DSH, доступный upstream и проверка пикового RSS при шести параллельных запросах: измеренный idle RSS не доказывает рабочий максимум.
>
> 4. РИСКИ: VERDICT=FAIL
>    WHY=Clean-room свидетельства достаточны для признания выполненных прогонов зелёными: компонентный pytest/unittest — 451 тест, корневой pytest — 894 passed и 5 skipped, статический гейт — 0 ошибок типов. Однако эти результаты не покрывают найденные сценарии. Особенно существенно, что cleanup может задержать killpg: deadline проверяется между блокирующими HTTP-операциями, которые сами могут удерживаться капающим ответом.
>
>    СОВЕТЫ (при FAIL): обеспечить прерывание HTTP-фазы по абсолютному deadline; для cleanup не ждать ненужное тело ответа; добавить капающие заголовки/chunk framing и проверить освобождение группы/слота; дополнить тесты F-001..F-006. VER-006/VER-007 выполнять после ACCEPT; их законная отсрочка сама по себе не является замечанием.
>
>    SUB Риски/безопасность: PASS — случайный пароль, loopback Basic auth, allowlist окружения и маскирование проверены (`server.py:1848`; тест `:1388`; REQ-015).
>    SUB Риски/данные: PASS — проверены отображение usage, суммирование попыток и дедупликация JSON tool calls (`tests/test_realtime_reasoning.py:1106`; VER-005).
>    SUB Риски/прод: FAIL — startup и cleanup имеют сценарии превышения бюджета и удержания ресурсов (`server.py:2604`, `server.py:2610`, `server.py:2799`; F-005/F-007).
>    SUB Риски/regression red→green: PASS — baseline sensitivity rc=1 и кандидат 72 passed подтверждены execution-evidence; это не заменяет недостающие оракулы F-004.
>    SUB Риски/Full Suite (L2): PASS — компонентные 451 passed, корневые 894 passed, обратный порядок 451 passed (`execution-evidence.md`, VER-001/002/003, AC-023).
>    SUB Риски/scope-diff: PASS — ровно три разрешённых файла, frozen функции совпадают (`candidate-manifest.json`; VER-004).
>
> 5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
>    WHY=Короткоживущий serve с общей системой бюджетов и legacy kill-switch оправдан подтверждённой недоступностью дельт в `opencode run`. Прямой Zen HTTP остаётся недоказанным вариантом, а общий демон усложняет сохранение ротации IP. Найденные дефекты исправляются внутри выбранной схемы; оснований требовать новую архитектуру или переписывание моста нет.
>
>    SUB Альтернативы/общее: PASS — A1 сохраняет ротацию и использует проверенный SSE API; исправления локальны (`handoff-architect.md` §4; F-17..F-25).
>
> 6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=FAIL
>    WHY=Границы автономного stdlib-моста соблюдены, но требования сквозных deadline и проверки всех recovery-сценариев выполнены не полностью. Это конкретные нарушения feature.md и приёмочных критериев, а не претензия к стилю или требование перенести мост на Litestar.
>
>    СОВЕТЫ (при FAIL): закрыть F-004/F-005/F-007 поведенческими оракулами; исправить прослеживаемость, чтобы PASS не опирался на тесты другого транспорта; повторить полный clean-room L2 после исправлений.
>
>    SUB Соответствие контексту/общее: FAIL — остаточный deadline не передан в startup, cleanup не имеет гарантированного абсолютного предела (`server.py:3101`, `server.py:2604`, `server.py:2610`; feature.md §2, R-BULK-I1).
>
>    Non-Goals проверены поштучно: HTTP-контракт — PASS; отсутствие правок DSH/профиля — PASS; отсутствие новой переработки reasoning ради превью — PASS; сохранение моделей/effort — PASS; отсутствие правок других мостов и общих конфигов — PASS; отсутствие внешних runtime-зависимостей — PASS.
>
>    Forbidden Scope проверен по пакету: файловый allowlist — PASS; отсутствие реальных секретов в diff — PASS; отсутствие преждевременного rollout — PASS; запрещённая keychain-команда не использовалась в представленных командах — PASS; прямая правка общей opencode.db отсутствует — PASS; коммит/merge защищённых веток не заявлен — PASS.
>
> Все замечания после повторного self-sweep:
>
> **F-001 — остаток RW-001, priority=blocking**
>
> - **locations:** `bridges/opencode-zen-bridge/server.py:3553`, `bridges/opencode-zen-bridge/server.py:5564`, `bridges/opencode-zen-bridge/server.py:5619`, `bridges/opencode-zen-bridge/server.py:6846`, `bridges/opencode-zen-bridge/server.py:6911`.
> - **Правило:** RW-001, FALLBACK_DECISION_TABLE/DELIVERED, REQ-009.
> - **Evidence:** ветка SSE ошибки устанавливает `error`, `transient_error`, `terminal="failed"` и выходит, сохранив исходное `delivered=False`. При HTTP 200 headers, затем `session.execution.failed` с transient error до токенов оба внешних цикла разрешают fallback на `run`.
> - **Исправление:** сохранять подтверждение доставки на всех выходах; отдельно учитывать наличие модельного вывода, чтобы headers-only transient failure корректно проходил serve-retry через общий бюджет.
> - **Критерий проверки:** auto, SSE и JSON: prompt headers → transient SSE failure до токенов; `run` не вызывается, RetryBudget учитывается, успешного учёта нет.
>
> **F-002 [pre-existing] — priority=blocking**
>
> - **locations:** `bridges/opencode-zen-bridge/server.py:6235`.
> - **Правило:** REQ-007, AC-010.
> - **Evidence:** `max(float(FIRST_TOKEN_TIMEOUT_S), 120.0)` игнорирует заданные значения ниже 120 секунд, включая дефолтные 60.
> - **Исправление:** применять настроенный порог без скрытого увеличения.
> - **Критерий проверки:** legacy SSE получает служебное событие, затем молчит; first-token timeout срабатывает по заданному порогу и получает правильную классификацию.
>
> **F-003 [pre-existing] — priority=blocking**
>
> - **locations:** `bridges/opencode-zen-bridge/server.py:5094`, `bridges/opencode-zen-bridge/server.py:5104`, `bridges/opencode-zen-bridge/server.py:5118`.
> - **Правило:** REQ-006, REQ-007; AC-008..AC-010.
> - **Evidence:** JSON callback `on_idle` проверяет только `is_client_gone`; время первого события, первого токена и последнего токена здесь не отслеживается. Молчащий legacy JSON продолжает ждать общий TIMEOUT_S.
> - **Исправление:** добавить три watchdog и их классификацию/учёт повторов в JSON legacy.
> - **Критерий проверки:** `TRANSPORT=run`, `stream=false`: отсутствие событий, события без токенов и пауза после токена завершаются соответствующими timeout с остановкой группы.
>
> **F-004 [pre-existing] — priority=blocking**
>
> - **locations:** `bridges/opencode-zen-bridge/tests/test_step_interruption.py:171`, `bridges/opencode-zen-bridge/tests/test_step_interruption.py:181`, `bridges/opencode-zen-bridge/server.py:1911`.
> - **Правило:** AC-016, AC-017; testing.md — проверять требуемое поведение и полноту.
> - **Evidence:** существующая матрица устанавливает shebang fake-CLI в OPENCODE_BIN; auto выбирает для него `run`. Новые serve-тесты покрывают отдельные сценарии, но не все сценарии существующей матрицы и не требуемое сравнение unmapped recovery.
> - **Исправление:** параметризовать поведенческую матрицу транспортами либо добавить эквивалентную serve-матрицу без ослабления assertions.
> - **Критерий проверки:** каждый сценарий AC-016 проверен на serve-дельтах; AC-017 сравнивает unmapped-повтор и итоговый finish_reason с legacy. В traceability приведены конкретные test IDs.
>
> **F-005 [pre-existing] — priority=blocking**
>
> - **locations:** `bridges/opencode-zen-bridge/server.py:2731`, `bridges/opencode-zen-bridge/server.py:2799`, `bridges/opencode-zen-bridge/server.py:2825`, `bridges/opencode-zen-bridge/server.py:3101`, `bridges/opencode-zen-bridge/server.py:3196`.
> - **Правило:** FU-006; REQ-008; feature.md §2; R-BULK-I1.
> - **Evidence:** `_spawn_serve` не принимает deadline/cancellation и создаёт самостоятельные окна ожидания. Подписка `/api/event` также использует отдельный timeout=5. Просроченный request deadline не запрещает предварительный запуск helper.
> - **Исправление:** передавать остаток общего бюджета через startup и subscribe; проверять отмену между ожиданиями; cancellation/deadline не превращать в ServeUnavailable с последующим fallback.
> - **Критерий проверки:** при истёкшем deadline helper не запускается; отмена на handshake/listener/subscribe обнаруживается в пределах REQ-008, процессы и слоты освобождаются.
>
> **F-006 [pre-existing] — priority=blocking**
>
> - **locations:** `bridges/opencode-zen-bridge/server.py:181`, `bridges/opencode-zen-bridge/server.py:2826`, `bridges/opencode-zen-bridge/server.py:2844`.
> - **Правило:** управление ресурсами и независающий I/O, feature.md §2, T-LIFE/v1.
> - **Evidence:** helper синхронно пересылает вывод serve в собственный stderr, но родитель начинает читать его только после проверки listener. Вывод до bind, превышающий суммарную ёмкость пайпов, блокирует helper и serve; listener не появляется.
> - **Исправление:** запускать родительский stderr-дренаж сразу после Popen, до handshake/listener; хранить ограниченный объём диагностических байтов.
> - **Критерий проверки:** fake serve пишет несколько MiB до открытия порта, включая вариант без LF; startup завершается, память ограничена, после cleanup нет оставшихся процессов и FD. Текущий тест на 70 KB эту границу не доказывает.
>
> **F-007 [pre-existing] — priority=blocking**
>
> - **locations:** `bridges/opencode-zen-bridge/server.py:2604`, `bridges/opencode-zen-bridge/server.py:2610`, `bridges/opencode-zen-bridge/server.py:3595`, `bridges/opencode-zen-bridge/server.py:3607`.
> - **Правило:** FU-006; feature.md §2 — timeout на каждом шаге, включая cleanup; REQ-008.
> - **Evidence:** deadline проверяется перед `getresponse()`/`read1()`. Чтение HTTP-заголовков и chunk framing внутри этих операций может выполнять несколько recv. Капающие байты чаще socket timeout удерживают операцию дольше абсолютного deadline; до `lease.cleanup()` исполнение не доходит.
> - **Исправление:** обеспечить жёсткое прерывание текущей HTTP-фазы по deadline; в cleanup не читать ненужное тело ответа. Сохранить ограниченный путь к killpg независимо от поведения control API.
> - **Критерий проверки:** interrupt/DELETE с капающими заголовками и chunked framing не удерживают cleanup за установленным бюджетом; группа исчезает в пределах AC-011, слот возвращается.
>
> ОБЩИЙ ВЕРДИКТ: NEEDS WORK
> COVERAGE: 14/14 подкатегорий
> FINDINGS_COMPLETE: 7
ARTIFACT_END>>>

АРГУМЕНТЫ ДРУГИХ ЭКСПЕРТОВ:
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/cycle-5/debate/r1/skeptic.md sha256=8132c0e15cbcdef99b8160236a7ebc43bd8c22c03782c3deaa8c20b871abdab1
> PANEL-NONCE: 05162baa598974a7
> ARTIFACT-SHA256: c9530b1b9b6113a97457c299f4970c7a2a5ad6a55605bbd243c97a09c5a85da4
>
> 1. КОРРЕКТНОСТЬ: VERDICT=FAIL
>    WHY=RW-001 закрыт не на всех путях выхода (F-001): SSE-ошибка `etype="error"` (server.py:3553) и общий `timeout` (server.py:3565) не переносят `prompt_status["headers_at"]` в `result["delivered"]`, поэтому в auto при transient-ошибке без модельного вывода возможен тихий fallback на `opencode run` и второй вызов Zen после уже принятого prompt (потребители — server.py:5614-5618 SSE и server.py:6888-6911 JSON). Отдельно legacy-путь игнорирует порог первого токена ниже 120 с (F-002, server.py:6235).
>    СОВЕТЫ (при FAIL): 1) В `_serve_one_attempt` устанавливать `result["delivered"]=True` при `headers_at is not None` на ветках `error` и `timeout` (как сделано для `first_event_timeout` server.py:3309); 2) убрать `max(...,120.0)` в legacy `send_keepalive`, использовать ровно `FIRST_TOKEN_TIMEOUT_S`; 3) добавить регрессионные тесты: headers получены → SSE `session.execution.failed` (transient) без токенов и headers получены → deadline `timeout` — в обоих случаях ни в SSE, ни в JSON не вызываются `Run.execute`/`_spawn_with_stdin`, нет `record_success()`; legacy-тест с `FIRST_TOKEN_TIMEOUT_S=0.8` и служебными событиями без токенов даёт `first_token_timeout`, а не ожидание 120 с.
> 2. ПОЛНОТА: VERDICT=FAIL
>    WHY=Verify-fixed: RW-002 PASS (абсолютный `threading.Timer` первого статуса, оракул задержки лимитера 0.5 с), RW-003/FU-001 PASS (разделители watchdog/unmapped/incomplete только при thinking), RW-004 PASS (`last_token_at` при native-вызове), FU-002/FU-003/FU-004 PASS по оракулам coder.json и clean-room L2. Но RW-001 закрыт частично: ветки error/timeout после headers не покрыты оракулом (F-001), а AC-010 на legacy-пути при пороге 60 с фактически не выполняется (F-002); FU-006 подтверждён только наличием `deadline=`, оракула капающего cleanup-тела нет (F-005, coder.json прямо признаёт пробел).
>    СОВЕТЫ (при FAIL): 1) Добавить оракулы из F-001/F-002 выше (обе ветки × SSE+JSON); 2) добавить оракул FU-006: interrupt/DELETE с медленно капающим телом ответа — суммарная уборка попытки и смерть группы укладываются в бюджет AC-011 (≤7 с); 3) после исправления прогнать полный L2 (VER-001/002/003) заново.
> 3. РЕАЛИЗУЕМОСТЬ: VERDICT=PASS
>    WHY=Clean-room L2 PASS: 451 passed на VER-001 pytest, VER-002 unittest, VER-003 root PYTHONPATH и reversed AC-023 (execution-evidence.md, code-gate.json status=PASS); 0 внешних зависимостей вне Python 3.14 stdlib; kill-switch через env/disable-файл/dynamic_config с дефолтом run. VER-006/007 законно DEFERRED_L3 до ACCEPT, блокером реализуемости не считаю.
> 4. РИСКИ: VERDICT=FAIL
>    WHY=F-002 удваивает время немой деградации legacy-пути (120 с вместо конфигурируемых 60 с по REQ-007) до ретрая. F-001 создаёт риск двойного расхода квоты Zen и двойной генерации при уже принятом prompt. Дополнительно: неограниченный размер SSE-строки и тела управляющего ответа (F-003, server.py:3235,2613), неполная валидация usage (F-004, server.py:1949: `cache.read` принимает bool как int, отрицательные токены не отсекаются), худший случай cleanup может превысить 7 с AC-011 (F-005: join 2×0.5 с на server.py:3584 + два последовательных deadline по 0.35 с на server.py:3595,3607 до lease.cleanup с окнами 4+2 с). Секреты, permission reject, allowlist окружения и маскирование ошибок замечаний не вызвали.
>    СОВЕТЫ (при FAIL): 1) Исправить F-001/F-002 (blocking, см. п.1); 2) ограничить размер одной SSE-строки (`readline(limit)`) и тела `_serve_http` именованной константой с протокольной ошибкой при превышении; 3) в `_map_serve_event` отсекать bool и отрицательные значения для всех токенов включая `cache.read`; 4) начинать `lease.cleanup()` (закрытие lifeline/SIGTERM) до или параллельно HTTP interrupt/DELETE либо доказать тестом суммарный бюджет ≤7 с в худшем случае.
> 5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
>    WHY=Выбранный гибрид A1+fallback соответствует прецеденту muse-bridge (F-40,F-41) и факт-карте (run дельт не даёт F-17/F-18, serve даёт F-19); более дешёвый путь L реалтайм не закрывает (RC-1). Неоправданного переписывания без необходимости не вижу; массовое переформатирование legacy в diff — non-blocking замечание к ревьюируемости, при замороженных срезах и зелёном Full Suite FAIL по этому критерию на цикле 5 не ставлю.
> 6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
>    WHY=Ровно 3 файла из конверта (candidate-manifest.json), замороженные `_run_env`/`_stream_google_sse`/`_execute_google_once` побайтно совпали (code-gate.json `google_direct_unchanged=True`, sha проверены гейтом), публичный контракт /health, /v1/models, /v1/chat/completions и SSE-форма сохранены, чужих KEY и файлов вне bridges/opencode-zen-bridge в diff нет. Стиль unittest в новом модуле расходится с testing.md, но FU-007 Советом прошлого цикла сознательно оставлен non-blocking, а обязательный гейт VER-002 — unittest discover; FAIL не ставлю.
>
> SUB Корректность/логика: FAIL — F-001 (server.py:3553,3565, правило RW-001/FALLBACK_DECISION_TABLE DELIVERED), F-002 (server.py:6235, REQ-007)
> SUB Корректность/граничные условия: FAIL — server.py:6235 `max(float(FIRST_TOKEN_TIMEOUT_S), 120.0)` против REQ-007/AC-010 (порог 60 с, env-настраиваемый)
> SUB Корректность/обработка ошибок: FAIL — server.py:3553-3556 ветка `etype=="error"` не ставит `result["delivered"]` при полученном `headers_at` (server.py:3266)
> SUB Полнота/покрытие AC: FAIL — AC-010 на legacy не выполняется при дефолте 60 с (server.py:6235); остальные AC подтверждены verification-traceability.md PASS
> SUB Полнота/пропущенные ветки: FAIL — error/timeout после prompt headers без модельного вывода не покрыты оракулом (reverse-spec.md §4.5 п.2; server.py:5618,6911)
> SUB Реализуемость/общее: PASS — code-gate.json status=PASS, VER-001..005 и AC-023 rc=0, 451 passed (execution-evidence.md)
> SUB Риски/безопасность: PASS — _serve_env allowlist + OPENCODE_DB=":memory:" + случайный пароль (server.py, _SERVE_ALLOWLIST), _error_payload/_mask_secrets маскирование, permission reject+interrupt, нет хардкода секретов в diff
> SUB Риски/данные: FAIL — F-004 server.py:1949 `isinstance(read_obj, int)` пропускает bool; отрицательные tokens.* не отсекаются (_map_serve_event)
> SUB Риски/прод: FAIL — F-003 server.py:3235 `sse_resp.readline()` без лимита и server.py:2613 `raw.extend(chunk)` без потолка тела; F-005 худший cleanup >7 с (server.py:3584,3595,3607)
> SUB Риски/regression red→green: PASS — code-gate.json red_sensitivity_rc=1 на origin/dev, кандидат 451 passed; оракулы test_c5_* в tests/test_realtime_reasoning.py
> SUB Риски/Full Suite (L2): PASS — VER-001 pytest (451), VER-002 unittest, VER-003 root, reversed — все rc=0 (execution-evidence.md)
> SUB Риски/scope-diff: PASS — candidate-manifest.json: ровно 3 файла coder_target_files, frozen-slice sha256 MATCH, 0 новых внешних зависимостей
> SUB Альтернативы/общее: PASS — вариант C (serve+fallback) обоснован F-17..F-19 и прецедентом muse-bridge F-40; L не закрывает RC-1
> SUB Соответствие контексту/общее: PASS — REQ-002 публичный контракт сохранён, REQ-018 Google-direct не тронут (google_direct_unchanged=True), Forbidden Scope не нарушен
>
> F-001 | priority=blocking | критерий=КОРРЕКТНОСТЬ | locations=bridges/opencode-zen-bridge/server.py:3553, server.py:3565 (корень), server.py:5614-5618, server.py:6888-6911 (потребители) | правило=RW-001 (headers_at включается в delivered на всех путях выхода), FALLBACK_DECISION_TABLE phase=DELIVERED, REQ-009 | evidence=`elif etype == "error": result["error"] = payload; result["transient_error"] = ...; break` — без `result["delivered"] = bool(prompt_status.get("headers_at"))`, в отличие от server.py:3309; та же недостановка на `result["exit_reason"] = "timeout"` | исправление=ставить delivered из headers_at на ветках error и timeout | проверка=новый тест в auto: prompt headers 200 получены, затем transient SSE-error без токенов (и отдельно deadline-timeout) — Run.execute/_spawn_with_stdin не вызваны ни в SSE, ни в JSON, record_success не вызван
> F-002 | priority=blocking | критерий=КОРРЕКТНОСТЬ | locations=bridges/opencode-zen-bridge/server.py:6235 | правило=REQ-007/AC-010 (first_token_timeout с env-порогом, дефолт 60 с) | evidence=`> max(float(FIRST_TOKEN_TIMEOUT_S), 120.0)` в legacy send_keepalive | исправление=убрать пол 120.0, сравнивать ровно с FIRST_TOKEN_TIMEOUT_S (как serve-путь server.py:3316) | проверка=legacy-тест: первое событие есть, токенов нет, FIRST_TOKEN_TIMEOUT_S=0.8 — попытка завершается first_token_timeout за ~0.8 с, а не за 120 с
> F-003 | priority=non-blocking | критерий=РИСКИ | locations=bridges/opencode-zen-bridge/server.py:3235, server.py:2613 | правило=C-MULT-I2 (ограниченные буферы горячего пути), security.md §6 (ограничение размера ответа) | evidence=`line = sse_resp.readline()` без limit; `raw.extend(chunk)` в цикле _serve_http без потолка | исправление=именованные константы лимита строки SSE и тела управляющего ответа, при превышении — ServeProtocolError/ServeUnavailable | проверка=тест с SSE-строкой и телом больше лимита: попытка завершается протокольной ошибкой, RSS очереди ограничен
> F-004 | priority=non-blocking [sweep] | критерий=РИСКИ | locations=bridges/opencode-zen-bridge/server.py:1949 | правило=REQ-014/AC-019 (usage совпадает по полям), python-standards §3 (валидация на границе) | evidence=`if not tokens or not isinstance(read_obj, int)` — bool является int в Python; для tokens.input/output/reasoning проверяется только not bool, знак не проверяется | исправление=единая проверка `isinstance(v,int) and not isinstance(v,bool) and v>=0` для всех четырёх полей | проверка=unit-тесты _map_serve_event с cache.read=true и отрицательными tokens дают ServeProtocolError
> F-005 | priority=non-blocking [sweep] | критерий=РИСКИ | locations=bridges/opencode-zen-bridge/server.py:3584, server.py:3595, server.py:3607 | правило=REQ-008/AC-011 (0 сирот ≤7 с после закрытия сокета), feature.md (таймаут на каждом шаге цепочки I/O включая cleanup в finally), FU-006 | evidence=последовательно: два join(timeout=0.5), interrupt deadline +0.35, DELETE deadline +0.35, затем lease.cleanup с окнами SIGTERM 4 с + SIGKILL-подтверждение 2 с — худший случай >7 с; coder.json признаёт отсутствие оракула капающего cleanup-тела | исправление=закрывать lifeline/посылать SIGTERM группе до HTTP-cleanup либо ужать последовательные бюджеты; добавить сквозной оракул худшего случая | проверка=FakeServe, игнорирующий interrupt и капающий тело: после закрытия клиентского сокета группа процессов отсутствует ≤7 с
>
> ОБЩИЙ ВЕРДИКТ: NEEDS WORK
> COVERAGE: 14/14 подкатегорий
> FINDINGS_COMPLETE: 5
ARTIFACT_END>>>
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/cycle-5/debate/r1/visionary.md sha256=9823f7846307e3327aa01417f4695fad7639261deaf6e129dd755e845eb93a98
> PANEL-NONCE: d3bb3ab877289505
> ARTIFACT-SHA256: c9530b1b9b6113a97457c299f4970c7a2a5ad6a55605bbd243c97a09c5a85da4
>
> 1. КОРРЕКТНОСТЬ: VERDICT=FAIL
>    WHY=Цикл 5 закрывает ровно ту архитектуру, которая меняет игру: короткоживущий `opencode serve` на попытку отдаёт дельты, которых `opencode run` v2.1.2 не выдаёт, ротация IP и kill-switch с дефолтом `run` сохраняются, публичный SSE-конверт остаётся. Verify-fixed по имени приёмки: RW-001 на обрыве тела prompt и на HTTP 429/5xx (заголовки входят в `delivered`, `ServeUnavailable` после `headers_at` не бросается, L2: `exit_reason=prompt_error|prompt_status_429|prompt_status_503`, `transport=serve`); RW-002 (абсолютный срок `STATUS_INITIAL`, оракул 0.5 с ≤ 1.0 с); RW-003/FU-001 (один разделитель watchdog/unmapped/incomplete только при thinking); RW-004 (`last_token_at` на `session.tool.input.delta` и на завершённом native-вызове). Дыра — соседняя ветка того же инварианта. `FALLBACK_DECISION_TABLE` (server.py:1701-1708) для prompt с уже полученными заголовками требует `serve_retry`, а не `fallback_to_run`. Ветки `first_event_timeout` (server.py:3309) и `_prompt_err` (server.py:3349-3357) этот флаг ставят. Ветка `etype == "error"` (server.py:3552-3556) пишет `error` / `transient_error` / `terminal="failed"` и выходит без `result["delivered"]`. `_is_transient_stream_error` (server.py:976-980) считает транзиентными `status is None`, 408, 429 и `>= 500`, то есть `session.execution.failed` / `provider.free-limit` после HTTP 200 prompt. Внешний SSE-барьер (server.py:5564-5570, 5618-5622) и JSON-барьер (server.py:6846-6855, 6911-6912) смотрят только `result["delivered"]`, тексты и native-вызовы. При `TRANSPORT=auto`, заголовках prompt и ошибке модели до первого токена запрос уходит в `opencode run` и шлёт тот же prompt в Zen второй раз. Отдельно legacy SSE поднимает порог первого токена до `max(FIRST_TOKEN_TIMEOUT_S, 120)` (server.py:6235) при дефолте 60 с и при AC-010.
>    СОВЕТЫ (при FAIL):
>    - В `bridges/opencode-zen-bridge/server.py:3552` перед `break` выставить `result["delivered"]` из `prompt_status["headers_at"]` или уже накопленных `texts` / `reasonings` / `native_calls`, тем же предикатом, что `_prompt_err` на server.py:3349-3357.
>    - На server.py:5618 и server.py:6911 не возвращать fallback в `run`, пока этот флаг истинен: `serve-retry` через `attempts.allow_retry` либо терминальная SSE/502, без `Run.execute`, без `_spawn_with_stdin`, без `record_success()`.
>    - Оракул: prompt HTTP 200 с `headers_at`, затем `session.execution.failed` (429 / timeout / eof) до первого токена, `TRANSPORT=auto`, и stream, и JSON.
>    - На server.py:6235 убрать немой пол `120.0` либо завести отдельную legacy-переменную и покрыть тестом: `FIRST_TOKEN_TIMEOUT_S=60` и событие без токена дают `first_token_timeout` около 60 с, а не около 120 с.
>
> 2. ПОЛНОТА: VERDICT=FAIL
>    WHY=REQ-001..REQ-020 и AC-001..AC-026 на потоковом пути и на serve закрыты матрицей `verification-traceability.md` и зелёным L2 (451 pytest, 451 unittest, обратный порядок AC-023, VER-005 72). Статусы `[мост]` отделены префиксом и `\n`, `_messages_to_prompt` (server.py:3940) берёт только `_render_turn`, исторический `reasoning_content` в промпт не входит (AC-007, оракул зелёный). Google-срез и `_run_env` заморожены, `google_direct_unchanged=true`. Пропущенная ветка REQ-006/REQ-007: `Run.execute` для non-stream JSON (server.py:5094-5100, 5147) умеет только `client_gone`. Часы `first_event_timeout` / `first_token_timeout` / `stall_timeout` есть в `_serve_one_attempt` (server.py:3305-3324) и в legacy SSE `send_keepalive` (server.py:6225-6246), на JSON-прогоне их нет, потолок остаётся `TIMEOUT_S=1800`. Это прямой MUST, не спор о стиле. DSH ходит со `stream:true` (F-35), поэтому прод-потребитель закрыт, а JSON-ручка моста — нет.
>    СОВЕТЫ (при FAIL):
>    - В цикле чтения `Run.execute` завести тот же `_WatchdogState`, что у legacy SSE: нет события транспорта до `FIRST_EVENT_TIMEOUT_S` → убийство группы и `first_event_timeout`; нет токена до порога → `first_token_timeout`; пауза после токена дольше `STALL_TIMEOUT_S` → `stall_timeout`; всё внутри `MAX_TOTAL_SPAWNS`.
>    - Регрессия: `stream:false`, фейковый CLI без stdout, выход с `first_event_timeout` заметно раньше 1800 с, процесс группы мёртв.
>    - Либо явная фраза в конверте, что REQ-006/REQ-007 относятся только к SSE и serve. Пока её нет, ветка обязана работать.
>
> 3. РЕАЛИЗУЕМОСТЬ: VERDICT=PASS
>    WHY=Сопровождать это можно. Транспорт по умолчанию `run`, пока нет boolean `REALTIME_SERVE_ENABLED` или явного `TRANSPORT=serve`; disable-файл и override `0` остаются аварийными выключателями. На попытку один helper, одна группа, `OPENCODE_DB=:memory:`, lease `0700`, порт из процесса, `finally` делает interrupt/DELETE с дедлайном 0.35 с и `killpg`. Idle serve ~152 MiB при слоте 6 укладывается в оценку HL-ENV из конверта. Зависимости рантайма вне stdlib не добавлены. `ps`/`lsof` уже есть на целевом хосте (факт-карта). VER-006/VER-007 законно `DEFERRED_L3` до ACCEPT: живой `:9883` этим диффом не мутируется. Операционная цена — холодный serve на запрос и reaper при старте, она и есть способ сохранить ротацию IP.
>
> 4. РИСКИ: VERDICT=PASS
>    WHY=Секреты: пароль serve — `secrets.token_hex`, в lease не пишется; `_mask_secrets` и `_error_payload` режут Bearer, `OPENCODE_SERVER_PASSWORD` и userinfo прокси; оракул RW-008 зелёный. Инструменты: дефолт `ask_reject`, `permission.asked` → reject+interrupt, `form.created` отменяется до разбора схемы, 401/403/400/404/422 — `ServeSecurityError` без fallback. Данные: `OPENCODE_DB=:memory:`, usage копится по попыткам, повтор шага с `assistantMessageID` подавляется (server.py:3521-3529). Прод-контур L2 зелёный, живой heavy-path отложен регламентом. Red→green: `L2-RED-sensitivity` rc=1 на `origin/dev` (76 падений на отсутствии символов), VER-005 rc=0 на кандидате. Full suite: pytest 451, unittest 451, порядок AC-023, VER-003/003b. Scope: ровно 3 файла манифеста, 0 новых runtime-зависимостей, замороженные срезы совпали. Дыра F-001 этим набором не поймана: существующие оракулы бьют в HTTP-статус prompt, а не в `session.execution.failed` после заголовков. Это дыра логики, чинится вместе с F-001, набор L2 сам по себе регрессию не прячет.
>
> 5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
>    WHY=Короткоживущий serve на запрос — тот вариант, который одновременно даёт реалтайм (RC-1) и оставляет ротацию чистого IP на spawn (F-15, дневной лимит Zen). Общий демон дешевле по RSS и хуже по квоте: один IP на все запросы. Прямой HTTP к Zen на фактах анализа получил 429 без заголовков CLI. Откат на `run` до барьера доставки повторяет прецедент muse-bridge и нужен как kill-switch REQ-003. Объём `server.py` — след REQ-001..REQ-016 в одном файле конверта, не переписывание ради переписывания. Дешёвый путь «только watchdog и статусы на legacy» реалтайм размышления не даёт (F-17, F-18).
>
> 6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
>    WHY=Граница задачи удержана: изменены `bridges/opencode-zen-bridge/server.py`, `tests/test_realtime_reasoning.py`, `tests/test_step_interruption.py`. Чужие мосты, DSH, каталог Zen, `zen_catalog.py` и Google-маршрут не тронуты. `sha256(_run_env)=1c51b28fcb83fcc0f4d8b5204c858e11ab5ac975bfe40dca4a0bf61978008e31`, `google_direct_unchanged=true`. Публичные пути `/health`, `/v1/models`, `/v1/chat/completions` и форма OpenAI SSE сохранены; синтетические строки `[мост]` — явное требование REQ-004/REQ-005, не самовольный контракт. `CATALOG_SOURCE="static"` зафиксирован VER-004. Оракул `test_step_interruption` приведён к `MAX_TOTAL_SPAWNS=3` по REQ-017, потолок не ослаблен. Stdlib-only, `dependencies=[]`. Сверка сида: `seed_hex=9fc56e2918ce7c0cd76640cf97f8f8026b36f1f1f4870d9f746f7517a49c3ee2` совпал с манифестом r56, `SEED=9fc56e29`; `ranked_order` совпал с манифестом r56: grok-4.7-high, gpt-6.1-sol-high, muse-wonder-full-1.0, claude-sonnet-5-5-high, gemini-4-argon-high.
>
> SUB Корректность/логика: FAIL — server.py:3552 не ставит `delivered` с `headers_at` на `etype=="error"`, server.py:5619 и server.py:6911 уходят в `run` (FALLBACK_DECISION_TABLE server.py:1701, REQ-009)
> SUB Корректность/граничные условия: FAIL — server.py:6235 `max(FIRST_TOKEN_TIMEOUT_S, 120.0)` глушит дефолт 60 с на legacy SSE (REQ-007, AC-010)
> SUB Корректность/обработка ошибок: PASS — server.py:3329-3332 и server.py:3349-3357: 401/403/400/404/422 → `ServeSecurityError`, обрыв тела после заголовков → `prompt_error` без `ServeUnavailable` (RW-001, L2 `prompt_error`)
> SUB Полнота/покрытие AC: PASS — verification-traceability.md REQ-001..020 / AC-001..026, L2 VER-001 rc=0, VER-005 rc=0, VER-006/007 DEFERRED_L3
> SUB Полнота/пропущенные ветки: FAIL — server.py:5094-5100 и server.py:5147: JSON `Run.execute` без `first_event_timeout`/`first_token_timeout`/`stall_timeout` (REQ-006, REQ-007) [pre-existing]
> SUB Реализуемость/общее: PASS — kill-switch дефолт `run` (server.py:1888-1910), lease+killpg в `finally`, 0 зависимостей вне stdlib, живой деплой не мутирован
> SUB Риски/безопасность: PASS — server.py:1898 пароль `token_hex`, маскирование `_mask_secrets`/`_error_payload`, permission reject и form cancel до схемы, оракул секретов зелёный (REQ-015)
> SUB Риски/данные: PASS — `OPENCODE_DB=:memory:` в `_serve_env`, usage по попыткам, дедуп шага по `assistantMessageID` server.py:3521-3529
> SUB Риски/прод: PASS — code-gate.json L2 PASS, слот 6 и idle serve 152 MiB в оценке HL-ENV, H0..H9 отложены до ACCEPT
> SUB Риски/regression red→green: PASS — execution-evidence.md L2-RED rc=1 (76 failed на origin/dev), VER-005 rc=0 (72 passed)
> SUB Риски/Full Suite (L2): PASS — VER-001 451 pytest, VER-002 451 unittest, AC-023 reversed rc=0, VER-003/003b rc=0
> SUB Риски/scope-diff: PASS — candidate-manifest.json ровно 3 файла, frozen sha256 совпали, `dependencies=[]`
> SUB Альтернативы/общее: PASS — per-request serve сохраняет ротацию IP (F-15) и даёт дельты, которых нет у `opencode run` (F-17, F-18); общий демон и прямой Zen этой цели не закрывают
> SUB Соответствие контексту/общее: PASS — 3 файла конверта, REQ-002/REQ-018, seed_hex r56 совпал (`9fc56e29…3ee2`)
>
> F-001
> priority: blocking
> criterion: КОРРЕКТНОСТЬ
> locations: bridges/opencode-zen-bridge/server.py:3552, bridges/opencode-zen-bridge/server.py:3556, bridges/opencode-zen-bridge/server.py:5564, bridges/opencode-zen-bridge/server.py:5618, bridges/opencode-zen-bridge/server.py:5619, bridges/opencode-zen-bridge/server.py:6846, bridges/opencode-zen-bridge/server.py:6911
> rule: FALLBACK_DECISION_TABLE phase=PROMPT_RESPONSE (server.py:1701-1708), инвариант RW-001 «headers_at запрещает run», REQ-009
> evidence: `elif etype == "error": result["error"] = payload; result["transient_error"] = _is_transient_stream_error(payload); result["terminal"] = "failed"; break` — флага `delivered` нет. Классификатор (server.py:976-980) возвращает True для 429, `status is None` и `status >= 500`. Снаружи: `_delivered_err = _delivered_now or bool(collected_texts)` и `if not _delivered_err and not force_serve: return False` с `transport_history=["serve","run"]`. JSON: `if not _delivered_j and not force_serve: return False`.
> expected: на `etype=="error"` выставить `result["delivered"]` из `prompt_status["headers_at"]` или уже отданных токенов/вызовов; при истине — `serve_retry` или терминальная ошибка, без второго upstream-prompt.
> check: `TRANSPORT=auto`, заголовки prompt 200, затем `session.execution.failed` (free-limit/timeout/eof) до токена, stream и JSON: `Run.execute` и `_spawn_with_stdin` не вызываются, `record_success()` не вызывается, `allow_retry` не больше одного раза на попытку.
>
> F-002
> priority: blocking
> criterion: КОРРЕКТНОСТЬ
> locations: bridges/opencode-zen-bridge/server.py:6231, bridges/opencode-zen-bridge/server.py:6235
> rule: REQ-007, AC-010
> evidence: `now_s - attempt_start > max(float(FIRST_TOKEN_TIMEOUT_S), 120.0)` при дефолте `FIRST_TOKEN_TIMEOUT_S=60`. Serve-путь сравнивает с сырым порогом (server.py:3314-3316). На legacy SSE событие без токена живёт до 120 с, сколько бы ни стояло в окружении ниже 120.
> expected: сравнение с `float(FIRST_TOKEN_TIMEOUT_S)` на обоих транспортах, либо отдельная переменная с явным именем и тем же дефолтом, что в конверте.
> check: `FIRST_TOKEN_TIMEOUT_S=60`, legacy SSE, есть событие и нет токена: `exit_reason=first_token_timeout` около 60 с плюс допуск, не около 120 с.
>
> F-003
> priority: blocking
> criterion: ПОЛНОТА
> locations: bridges/opencode-zen-bridge/server.py:5094, bridges/opencode-zen-bridge/server.py:5100, bridges/opencode-zen-bridge/server.py:5147
> rule: REQ-006, REQ-007, AC-008, AC-009, AC-010
> evidence: [pre-existing] `on_idle` в `Run.execute` ставит только `state = "client_gone"` и зовёт `_stop_proc`. Ветка `etype == "error"` (server.py:5147) не классифицирует молчание. Часы первого события, первого токена и паузы в этом методе отсутствуют; их копии живут в SSE (server.py:6225-6246) и в `_serve_one_attempt` (server.py:3305-3324). Non-stream JSON упирается в `TIMEOUT_S=1800`.
> expected: те же три причины выхода и убийство группы внутри общего потолка спавнов на JSON-прогоне `opencode run`.
> check: `stream:false`, фейковый CLI без stdout: завершение с `first_event_timeout` за порог плюс единицы секунд, процессов группы нет. Аналогично первый токен и пауза после токена.
>
> [sweep] Повторный проход 1–14: новые корни сверх F-001..F-003 не найдены. RW-002/RW-003/RW-004 и FU-002..FU-006 подтверждены кодом и зелёными оракулами L2. FU-007 (оставить unittest) — вне FAIL. `_strip_interrupted` на reasoning режет только маркер обрыва, тот же приём уже на legacy-пути, AC-006 не ломает.
>
> ОБЩИЙ ВЕРДИКТ: NEEDS WORK
> COVERAGE: 14/14 подкатегорий
> FINDINGS_COMPLETE: 3
ARTIFACT_END>>>

СВОДНЫЙ ЛЕДЖЕР:
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/cycle-5/consensus-ledger.md sha256=0a7ff9a103dc59a5b65513c6978a0a11da4aa1e6a740e00721e9e0e9593fed69
# Черновой леджер совещания Совета Тимлидов по коду (цикл 5, после R1 r56, run analyst-teamlead-zen-realtime-reasoning-20261025)

- Всего находок R1: `15` (`F-001..F-015`: `skeptic` `F-001..F-005`, `realist` `F-006..F-012`, `visionary` `F-013..F-015`).
- Открытых blocking (`OPEN_BLOCKING`): `12`; открытых non-blocking: `3`.

### F-001
- origin: skeptic · R1 · skeptic-F-001
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
> F-001 | priority=blocking | критерий=КОРРЕКТНОСТЬ | locations=bridges/opencode-zen-bridge/server.py:3553, server.py:3565 (корень), server.py:5614-5618, server.py:6888-6911 (потребители) | правило=RW-001 (headers_at включается в delivered на всех путях выхода), FALLBACK_DECISION_TABLE phase=DELIVERED, REQ-009 | evidence=`elif etype == "error": result["error"] = payload; result["transient_error"] = ...; break` — без `result["delivered"] = bool(prompt_status.get("headers_at"))`, в отличие от server.py:3309; та же недостановка на `result["exit_reason"] = "timeout"` | исправление=ставить delivered из headers_at на ветках error и timeout | проверка=новый тест в auto: prompt headers 200 получены, затем transient SSE-error без токенов (и отдельно deadline-timeout) — Run.execute/_spawn_with_stdin не вызваны ни в SSE, ни в JSON, record_success не вызван

### F-002
- origin: skeptic · R1 · skeptic-F-002
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
> F-002 | priority=blocking | критерий=КОРРЕКТНОСТЬ | locations=bridges/opencode-zen-bridge/server.py:6235 | правило=REQ-007/AC-010 (first_token_timeout с env-порогом, дефолт 60 с) | evidence=`> max(float(FIRST_TOKEN_TIMEOUT_S), 120.0)` в legacy send_keepalive | исправление=убрать пол 120.0, сравнивать ровно с FIRST_TOKEN_TIMEOUT_S (как serve-путь server.py:3316) | проверка=legacy-тест: первое событие есть, токенов нет, FIRST_TOKEN_TIMEOUT_S=0.8 — попытка завершается first_token_timeout за ~0.8 с, а не за 120 с

### F-003
- origin: skeptic · R1 · skeptic-F-003
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
> F-003 | priority=non-blocking | критерий=РИСКИ | locations=bridges/opencode-zen-bridge/server.py:3235, server.py:2613 | правило=C-MULT-I2 (ограниченные буферы горячего пути), security.md §6 (ограничение размера ответа) | evidence=`line = sse_resp.readline()` без limit; `raw.extend(chunk)` в цикле _serve_http без потолка | исправление=именованные константы лимита строки SSE и тела управляющего ответа, при превышении — ServeProtocolError/ServeUnavailable | проверка=тест с SSE-строкой и телом больше лимита: попытка завершается протокольной ошибкой, RSS очереди ограничен

### F-004
- origin: skeptic · R1 · skeptic-F-004
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
> F-004 | priority=non-blocking [sweep] | критерий=РИСКИ | locations=bridges/opencode-zen-bridge/server.py:1949 | правило=REQ-014/AC-019 (usage совпадает по полям), python-standards §3 (валидация на границе) | evidence=`if not tokens or not isinstance(read_obj, int)` — bool является int в Python; для tokens.input/output/reasoning проверяется только not bool, знак не проверяется | исправление=единая проверка `isinstance(v,int) and not isinstance(v,bool) and v>=0` для всех четырёх полей | проверка=unit-тесты _map_serve_event с cache.read=true и отрицательными tokens дают ServeProtocolError

### F-005
- origin: skeptic · R1 · skeptic-F-005
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
> F-005 | priority=non-blocking [sweep] | критерий=РИСКИ | locations=bridges/opencode-zen-bridge/server.py:3584, server.py:3595, server.py:3607 | правило=REQ-008/AC-011 (0 сирот ≤7 с после закрытия сокета), feature.md (таймаут на каждом шаге цепочки I/O включая cleanup в finally), FU-006 | evidence=последовательно: два join(timeout=0.5), interrupt deadline +0.35, DELETE deadline +0.35, затем lease.cleanup с окнами SIGTERM 4 с + SIGKILL-подтверждение 2 с — худший случай >7 с; coder.json признаёт отсутствие оракула капающего cleanup-тела | исправление=закрывать lifeline/посылать SIGTERM группе до HTTP-cleanup либо ужать последовательные бюджеты; добавить сквозной оракул худшего случая | проверка=FakeServe, игнорирующий interrupt и капающий тело: после закрытия клиентского сокета группа процессов отсутствует ≤7 с

### F-006
- origin: realist · R1 · realist-F-001
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
> **F-001 — остаток RW-001, priority=blocking**
>
> - **locations:** `bridges/opencode-zen-bridge/server.py:3553`, `bridges/opencode-zen-bridge/server.py:5564`, `bridges/opencode-zen-bridge/server.py:5619`, `bridges/opencode-zen-bridge/server.py:6846`, `bridges/opencode-zen-bridge/server.py:6911`.
> - **Правило:** RW-001, FALLBACK_DECISION_TABLE/DELIVERED, REQ-009.
> - **Evidence:** ветка SSE ошибки устанавливает `error`, `transient_error`, `terminal="failed"` и выходит, сохранив исходное `delivered=False`. При HTTP 200 headers, затем `session.execution.failed` с transient error до токенов оба внешних цикла разрешают fallback на `run`.
> - **Исправление:** сохранять подтверждение доставки на всех выходах; отдельно учитывать наличие модельного вывода, чтобы headers-only transient failure корректно проходил serve-retry через общий бюджет.
> - **Критерий проверки:** auto, SSE и JSON: prompt headers → transient SSE failure до токенов; `run` не вызывается, RetryBudget учитывается, успешного учёта нет.

### F-007
- origin: realist · R1 · realist-F-002
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
> **F-002 [pre-existing] — priority=blocking**
>
> - **locations:** `bridges/opencode-zen-bridge/server.py:6235`.
> - **Правило:** REQ-007, AC-010.
> - **Evidence:** `max(float(FIRST_TOKEN_TIMEOUT_S), 120.0)` игнорирует заданные значения ниже 120 секунд, включая дефолтные 60.
> - **Исправление:** применять настроенный порог без скрытого увеличения.
> - **Критерий проверки:** legacy SSE получает служебное событие, затем молчит; first-token timeout срабатывает по заданному порогу и получает правильную классификацию.

### F-008
- origin: realist · R1 · realist-F-003
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
> **F-003 [pre-existing] — priority=blocking**
>
> - **locations:** `bridges/opencode-zen-bridge/server.py:5094`, `bridges/opencode-zen-bridge/server.py:5104`, `bridges/opencode-zen-bridge/server.py:5118`.
> - **Правило:** REQ-006, REQ-007; AC-008..AC-010.
> - **Evidence:** JSON callback `on_idle` проверяет только `is_client_gone`; время первого события, первого токена и последнего токена здесь не отслеживается. Молчащий legacy JSON продолжает ждать общий TIMEOUT_S.
> - **Исправление:** добавить три watchdog и их классификацию/учёт повторов в JSON legacy.
> - **Критерий проверки:** `TRANSPORT=run`, `stream=false`: отсутствие событий, события без токенов и пауза после токена завершаются соответствующими timeout с остановкой группы.

### F-009
- origin: realist · R1 · realist-F-004
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
> **F-004 [pre-existing] — priority=blocking**
>
> - **locations:** `bridges/opencode-zen-bridge/tests/test_step_interruption.py:171`, `bridges/opencode-zen-bridge/tests/test_step_interruption.py:181`, `bridges/opencode-zen-bridge/server.py:1911`.
> - **Правило:** AC-016, AC-017; testing.md — проверять требуемое поведение и полноту.
> - **Evidence:** существующая матрица устанавливает shebang fake-CLI в OPENCODE_BIN; auto выбирает для него `run`. Новые serve-тесты покрывают отдельные сценарии, но не все сценарии существующей матрицы и не требуемое сравнение unmapped recovery.
> - **Исправление:** параметризовать поведенческую матрицу транспортами либо добавить эквивалентную serve-матрицу без ослабления assertions.
> - **Критерий проверки:** каждый сценарий AC-016 проверен на serve-дельтах; AC-017 сравнивает unmapped-повтор и итоговый finish_reason с legacy. В traceability приведены конкретные test IDs.

### F-010
- origin: realist · R1 · realist-F-005
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
> **F-005 [pre-existing] — priority=blocking**
>
> - **locations:** `bridges/opencode-zen-bridge/server.py:2731`, `bridges/opencode-zen-bridge/server.py:2799`, `bridges/opencode-zen-bridge/server.py:2825`, `bridges/opencode-zen-bridge/server.py:3101`, `bridges/opencode-zen-bridge/server.py:3196`.
> - **Правило:** FU-006; REQ-008; feature.md §2; R-BULK-I1.
> - **Evidence:** `_spawn_serve` не принимает deadline/cancellation и создаёт самостоятельные окна ожидания. Подписка `/api/event` также использует отдельный timeout=5. Просроченный request deadline не запрещает предварительный запуск helper.
> - **Исправление:** передавать остаток общего бюджета через startup и subscribe; проверять отмену между ожиданиями; cancellation/deadline не превращать в ServeUnavailable с последующим fallback.
> - **Критерий проверки:** при истёкшем deadline helper не запускается; отмена на handshake/listener/subscribe обнаруживается в пределах REQ-008, процессы и слоты освобождаются.

### F-011
- origin: realist · R1 · realist-F-006
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
> **F-006 [pre-existing] — priority=blocking**
>
> - **locations:** `bridges/opencode-zen-bridge/server.py:181`, `bridges/opencode-zen-bridge/server.py:2826`, `bridges/opencode-zen-bridge/server.py:2844`.
> - **Правило:** управление ресурсами и независающий I/O, feature.md §2, T-LIFE/v1.
> - **Evidence:** helper синхронно пересылает вывод serve в собственный stderr, но родитель начинает читать его только после проверки listener. Вывод до bind, превышающий суммарную ёмкость пайпов, блокирует helper и serve; listener не появляется.
> - **Исправление:** запускать родительский stderr-дренаж сразу после Popen, до handshake/listener; хранить ограниченный объём диагностических байтов.
> - **Критерий проверки:** fake serve пишет несколько MiB до открытия порта, включая вариант без LF; startup завершается, память ограничена, после cleanup нет оставшихся процессов и FD. Текущий тест на 70 KB эту границу не доказывает.

### F-012
- origin: realist · R1 · realist-F-007
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
> **F-007 [pre-existing] — priority=blocking**
>
> - **locations:** `bridges/opencode-zen-bridge/server.py:2604`, `bridges/opencode-zen-bridge/server.py:2610`, `bridges/opencode-zen-bridge/server.py:3595`, `bridges/opencode-zen-bridge/server.py:3607`.
> - **Правило:** FU-006; feature.md §2 — timeout на каждом шаге, включая cleanup; REQ-008.
> - **Evidence:** deadline проверяется перед `getresponse()`/`read1()`. Чтение HTTP-заголовков и chunk framing внутри этих операций может выполнять несколько recv. Капающие байты чаще socket timeout удерживают операцию дольше абсолютного deadline; до `lease.cleanup()` исполнение не доходит.
> - **Исправление:** обеспечить жёсткое прерывание текущей HTTP-фазы по deadline; в cleanup не читать ненужное тело ответа. Сохранить ограниченный путь к killpg независимо от поведения control API.
> - **Критерий проверки:** interrupt/DELETE с капающими заголовками и chunked framing не удерживают cleanup за установленным бюджетом; группа исчезает в пределах AC-011, слот возвращается.

### F-013
- origin: visionary · R1 · visionary-F-001
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
> F-001
> priority: blocking
> criterion: КОРРЕКТНОСТЬ
> locations: bridges/opencode-zen-bridge/server.py:3552, bridges/opencode-zen-bridge/server.py:3556, bridges/opencode-zen-bridge/server.py:5564, bridges/opencode-zen-bridge/server.py:5618, bridges/opencode-zen-bridge/server.py:5619, bridges/opencode-zen-bridge/server.py:6846, bridges/opencode-zen-bridge/server.py:6911
> rule: FALLBACK_DECISION_TABLE phase=PROMPT_RESPONSE (server.py:1701-1708), инвариант RW-001 «headers_at запрещает run», REQ-009
> evidence: `elif etype == "error": result["error"] = payload; result["transient_error"] = _is_transient_stream_error(payload); result["terminal"] = "failed"; break` — флага `delivered` нет. Классификатор (server.py:976-980) возвращает True для 429, `status is None` и `status >= 500`. Снаружи: `_delivered_err = _delivered_now or bool(collected_texts)` и `if not _delivered_err and not force_serve: return False` с `transport_history=["serve","run"]`. JSON: `if not _delivered_j and not force_serve: return False`.
> expected: на `etype=="error"` выставить `result["delivered"]` из `prompt_status["headers_at"]` или уже отданных токенов/вызовов; при истине — `serve_retry` или терминальная ошибка, без второго upstream-prompt.
> check: `TRANSPORT=auto`, заголовки prompt 200, затем `session.execution.failed` (free-limit/timeout/eof) до токена, stream и JSON: `Run.execute` и `_spawn_with_stdin` не вызываются, `record_success()` не вызывается, `allow_retry` не больше одного раза на попытку.

### F-014
- origin: visionary · R1 · visionary-F-002
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
> F-002
> priority: blocking
> criterion: КОРРЕКТНОСТЬ
> locations: bridges/opencode-zen-bridge/server.py:6231, bridges/opencode-zen-bridge/server.py:6235
> rule: REQ-007, AC-010
> evidence: `now_s - attempt_start > max(float(FIRST_TOKEN_TIMEOUT_S), 120.0)` при дефолте `FIRST_TOKEN_TIMEOUT_S=60`. Serve-путь сравнивает с сырым порогом (server.py:3314-3316). На legacy SSE событие без токена живёт до 120 с, сколько бы ни стояло в окружении ниже 120.
> expected: сравнение с `float(FIRST_TOKEN_TIMEOUT_S)` на обоих транспортах, либо отдельная переменная с явным именем и тем же дефолтом, что в конверте.
> check: `FIRST_TOKEN_TIMEOUT_S=60`, legacy SSE, есть событие и нет токена: `exit_reason=first_token_timeout` около 60 с плюс допуск, не около 120 с.

### F-015
- origin: visionary · R1 · visionary-F-003
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
> F-003
> priority: blocking
> criterion: ПОЛНОТА
> locations: bridges/opencode-zen-bridge/server.py:5094, bridges/opencode-zen-bridge/server.py:5100, bridges/opencode-zen-bridge/server.py:5147
> rule: REQ-006, REQ-007, AC-008, AC-009, AC-010
> evidence: [pre-existing] `on_idle` в `Run.execute` ставит только `state = "client_gone"` и зовёт `_stop_proc`. Ветка `etype == "error"` (server.py:5147) не классифицирует молчание. Часы первого события, первого токена и паузы в этом методе отсутствуют; их копии живут в SSE (server.py:6225-6246) и в `_serve_one_attempt` (server.py:3305-3324). Non-stream JSON упирается в `TIMEOUT_S=1800`.
> expected: те же три причины выхода и убийство группы внутри общего потолка спавнов на JSON-прогоне `opencode run`.
> check: `stream:false`, фейковый CLI без stdout: завершение с `first_event_timeout` за порог плюс единицы секунд, процессов группы нет. Аналогично первый токен и пауза после токена.
ARTIFACT_END>>>
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/cycle-5/recheck-r1.md sha256=26192f9605364d3f6ec0e7fe8834471a64523bea74e85f3040af4f4546d7f9f0
# Механический RECHECK после R1 Совета Тимлидов по коду (цикл 5, run analyst-teamlead-zen-realtime-reasoning-20261025)

- Проверяемый артефакт: `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/package.md` (`sha256=c9530b1b9b6113a97457c299f4970c7a2a5ad6a55605bbd243c97a09c5a85da4`)
- Длина файлов кандидата: `server.py` = `7542` строк, `tests/test_realtime_reasoning.py` = `2140` строк, `tests/test_step_interruption.py` = `1088` строк.

RECHECK F-001 (skeptic skeptic-F-001, blocking): `server.py:3553` → `result["error"] = payload` | F-001 | priority=blocking | критерий=КОРРЕКТНОСТЬ | locations=bridges/opencode-zen-bridge/server.py:3553, serv
RECHECK F-002 (skeptic skeptic-F-002, blocking): `server.py:6235` → `> max(float(FIRST_TOKEN_TIMEOUT_S), 120.0)` | F-002 | priority=blocking | критерий=КОРРЕКТНОСТЬ | locations=bridges/opencode-zen-bridge/server.py:6235 | пра
RECHECK F-003 (skeptic skeptic-F-003, non-blocking): `server.py:3235` → `line = sse_resp.readline()` | F-003 | priority=non-blocking | критерий=РИСКИ | locations=bridges/opencode-zen-bridge/server.py:3235, server.
RECHECK F-004 (skeptic skeptic-F-004, non-blocking): `server.py:1949` → `if not tokens or not isinstance(read_obj, int):` | F-004 | priority=non-blocking [sweep] | критерий=РИСКИ | locations=bridges/opencode-zen-bridge/server.py:1949 
RECHECK F-005 (skeptic skeptic-F-005, non-blocking): `server.py:3584` → `_th.join(timeout=0.5)` | F-005 | priority=non-blocking [sweep] | критерий=РИСКИ | locations=bridges/opencode-zen-bridge/server.py:3584,
RECHECK F-006 (realist realist-F-001, blocking): `server.py:3553` → `result["error"] = payload` | **F-001 — остаток RW-001, priority=blocking**
RECHECK F-007 (realist realist-F-002, blocking): `server.py:6235` → `> max(float(FIRST_TOKEN_TIMEOUT_S), 120.0)` | **F-002 [pre-existing] — priority=blocking**
RECHECK F-008 (realist realist-F-003, blocking): `server.py:5094` → `def on_idle() -> None:` | **F-003 [pre-existing] — priority=blocking**
RECHECK F-009 (realist realist-F-004, blocking): `test_step_interruption.py:171` → `def setUpClass(cls) -> None:` | **F-004 [pre-existing] — priority=blocking**
RECHECK F-010 (realist realist-F-005, blocking): `server.py:2731` → `def _spawn_serve(` | **F-005 [pre-existing] — priority=blocking**
RECHECK F-011 (realist realist-F-006, blocking): `server.py:181` → `_ = sys.stderr.write(chunk.decode("utf-8", "replace"))` | **F-006 [pre-existing] — priority=blocking**
RECHECK F-012 (realist realist-F-007, blocking): `server.py:2604` → `resp = active_conn.getresponse()` | **F-007 [pre-existing] — priority=blocking**
RECHECK F-013 (visionary visionary-F-001, blocking): `server.py:3552` → `elif etype == "error":` | F-001
RECHECK F-014 (visionary visionary-F-002, blocking): `server.py:6231` → `if (` | F-002
RECHECK F-015 (visionary visionary-F-003, blocking): `server.py:5094` → `def on_idle() -> None:` | F-003
ARTIFACT_END>>>

РАУНД: D1 из ≤2; последний: нет; место: realist
ПОЗИЦИИ ТРЕБУЮТСЯ ПО: F-001, F-002, F-003, F-004, F-005, F-013, F-014, F-015; N=8
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

По п.6 блока «ПРАВИЛА ДЕБАТОВ» выведи строки позиций по всем 8 находкам из строки `ПОЗИЦИИ ТРЕБУЮТСЯ ПО` (и свои `WITHDRAW`/`AMEND` при пересмотре собственных находок R1 с учётом `RECHECK` и аргументов коллег), затем блок 6 критериев `ФОРМАТ ОТВЕТА`, затем обязательные строки `POSITIONS: 8/8` и `ANSWERS: 0/0`, а последней непустой строкой ответа выведи канонический вердикт `ОБЩИЙ ВЕРДИКТ: ACCEPT`, `ОБЩИЙ ВЕРДИКТ: PASS`, `ОБЩИЙ ВЕРДИКТ: NEEDS WORK` или `ОБЩИЙ ВЕРДИКТ: RED FLAG` (без точки и комментариев в той же строке).

---
PRIOR-LEDGER-SHA256: 0a7ff9a103dc59a5b65513c6978a0a11da4aa1e6a740e00721e9e0e9593fed69
PANEL-NONCE: 5f4c8610f7fae22d
ARTIFACT-SHA256: c9530b1b9b6113a97457c299f4970c7a2a5ad6a55605bbd243c97a09c5a85da4
Инструкция судье: первыми двумя строками ответа повтори дословно «PANEL-NONCE: 5f4c8610f7fae22d» и «ARTIFACT-SHA256: c9530b1b9b6113a97457c299f4970c7a2a5ad6a55605bbd243c97a09c5a85da4».
