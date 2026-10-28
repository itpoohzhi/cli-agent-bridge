Ты — Скептик. Твоя задача — найти риски, слабые места, что сломается. Ключевой вопрос: «Почему это НЕ сработает?»

Ты оцениваешь архитектуру, а не код. Фокусируйся на структурных проблемах: циклические зависимости, нарушение слоёв, хардкод секретов, смешение ответственностей, отсутствие границ.

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

📋 ФАКТ-КАРТА (проверено оркестратором на целевой машине и дополнено логами гейтов Цикла 9, 2026-10-27):
- Репозиторий `cli-agent-bridge` (ветка `feature/zen-realtime-reasoning` от `origin/dev` `7eda27f9d82732bab726a420e31ea2adc15c2c39`): автономный Python stdlib-мост `bridges/opencode-zen-bridge/server.py` (`ThreadingHTTPServer` на `127.0.0.1:9883`), без корневого `AGENTS.md` и без сторонних runtime-зависимостей вне стандартной библиотеки Python 3.14.
- Установленный CLI `~/.opencode/bin/opencode` версии `v2.1.2` существует локально: команда `opencode run --format json --thinking` подписана только на `session.reasoning.ended` и `session.text.ended` (игнорирует `*.delta`, разрыв 0.00–0.17 мс в конце шага, `[F-17]`, `[F-18]`).
- Режим `opencode serve --port P --hostname 127.0.0.1` в `opencode` `v2.1.2` существует и проверен эмпирически (`[F-19]..[F-22]`): старт ~109 мс, Basic-аутентификация `opencode:<OPENCODE_SERVER_PASSWORD>`, OpenAPI `281456 B` включает `GET /api/event` (SSE с реальными дельтами `session.reasoning.delta` median 127 мс и `session.text.delta` median 114 мс), `POST /api/session` (с `permissions`), `POST /api/session/{id}/prompt`, `POST /api/session/{id}/interrupt`, `DELETE /api/session/{id}`.
- Локальный `model_georouter` (`127.0.0.1:10830`) и пул ротации чистых IP ProxyRack (`OPENCODE_ZEN_BRIDGE_STANDALONE_PROXY=pool`) существуют на хосте (`[F-15]`, `[F-26]`, `[F-27]`); прямой анонимный HTTP-вызов к `opencode.ai/inference/openai/v1` без заголовков CLI вернул `429 FreeUsageLimitError` (`[F-24]`, `[F-25]`).
- Потребитель DSH Desktop (`@earendil-works/pi-ai` `openai-completions.js` и `@deepseek-ai/dsh-client-ui-chat` `ReasoningRow`, `[F-35]..[F-38]`): строка `⚛ Think` скрыта (`blockIsVisible`), пока `reasoning_content` пуст; свёрнутое inline-превью обновляется через `latestCompletedParagraphFirstLine` только при наличии завершённого абзаца с символом `\n`; при реплее истории мост игнорирует входящий `assistant.reasoning_content` (`[F-07]`).
- Прецедент в том же репозитории: `bridges/muse-bridge/server.py` (ADR-0004, `[F-40]`, `[F-41]`) использует `serve` как основной транспорт с откатом на `exec` при `ServeUnavailable` и живой записью статусов в `reasoning_content`.
- Тестовый контур моста (`[F-42]..[F-49]`): `uvx pytest -q -p no:cacheprovider tests/` из `bridges/opencode-zen-bridge` (17 модулей, 378 тестов; 3 pre-existing падения в `tests/test_step_interruption.py` из-за `MAX_TOTAL_SPAWNS=3` против ожидания 4 запусков и общего `_RetryBudget` на класс).
- Дополнительные эмпирические замеры на целевой машине (`EVD-070..EVD-072`): `python3 -m unittest discover -s tests -p "test_*.py" -v` из `cwd=bridges/opencode-zen-bridge` выполняет все 378 тестов без ошибок импорта; `OPENCODE_DB=":memory:"` нативно поддерживается в `opencode` `v2.1.2` (старт `opencode serve` 120.7 мс, RSS 156.8 MiB, `0` открытых `.db`/SQLite дескрипторов в `lsof` при сохранении чтения `~/.local/share/opencode/auth.json` для `opencode-go/*`); `basedpyright==1.40.2` из `cwd=bridges/opencode-zen-bridge` с абсолютным `extraPaths` даёт `0` ошибок импорта в тестах и `3` статические ошибки в `server.py`, а полный `ruff format --diff server.py` меняет 3216 строк неформатированного legacy-кода (включая `def _run_env` и Google-direct).
- Проверенные артефакты и логи гейтов кандидата Цикла 9 (`receipts/code-gate.json`, `teamlead/candidate-manifest.json`):
  - Изменённые файлы кандидата (ровно 3 файла `coder_target_files`, 0 новых внешних runtime-зависимостей вне Python 3.14 stdlib): bridges/opencode-zen-bridge/server.py (sha256=7fa04234e8f4...), bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py (sha256=3328cdf299dd...), bridges/opencode-zen-bridge/tests/test_step_interruption.py (sha256=e41d10bd96cb...).
  - Clean-room L2 гейт Цикла 9 (`receipts/code-gate.json`): `status=PASS`, `red_sensitivity_rc=1` (поведенческое RED-падение `AC-026` на сокетном оракуле `origin/dev`), все проверки кандидата (`VER-004`, `VER-001`, `VER-002`, `VER-003`, `AC-023`, `VER-005`) зелёные (`rc=0`, 480 passed), `run_env_sha256=1c51b28fcb83fcc0f4d8b5204c858e11ab5ac975bfe40dca4a0bf61978008e31`, `google_direct_unchanged=True`.
Анти-галлюцинация: перед тем как выставить FAIL «нет X», перечитать приложенный пакет приёмки и diff целиком; по проверенным пунктам факт-карты запрещено ставить FAIL «не существует»; если сущности нет в факт-карте и приложенных артефактах и ты не уверен — пиши «не могу проверить».

РЕЖИМ: code
Модификатор режима `code`: Перечисли конкретные проверки: типы, ошибки, граничные случаи, тесты, безопасность, гонки ресурсов и обратную совместимость контрактов. Усиленные критерии режима `code` (вес ×1.5 на агрегации): 1. КОРРЕКТНОСТЬ и 4. РИСКИ. Если ты уже видел эту задачу, архитектуру или код в другой роли — суди ЗАНОВО, не подтверждай прошлый вердикт автоматически. На этом повторном цикле доработки (`teamlead_cycle: 9`, `council.md` §1 и §3 «Diff-scope повторного цикла»): (а) выполни verify-fixed по каждому из 2 blocking пунктов `RW-001..RW-002` (и сопутствующих `FU-001..FU-002`) из вложенного в пакет вывода `panel-rework-summarizer` (`.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/handoff/panel-rework-brief.json`); (б) проверь полный актуальный `candidate.diff` (содержащий `server.py`, `tests/test_step_interruption.py` и новый файл `tests/test_realtime_reasoning.py`) на предмет регрессий и соответствие каждому требованию `REQ-001..REQ-020`, каждому приёмочному критерию `AC-001..AC-026` и каждой границе `Non-Goals` / `Forbidden Scope` поштучно (через `verification-traceability.md`, `execution-evidence.md` и слепой `reverse-spec.md`). Результаты тестов и статических проверок бери только как факт из валидных строк `execution-evidence.md` и вложенных сырых логов clean-room прогона (при отсутствии валидного свидетельства — `INCONCLUSIVE`; судья сам тесты не запускает; строки `VER-006` и `VER-007` законно помечены `DEFERRED_L3` до вердикта `ACCEPT` Совета).

РЕШЕНИЕ ДЛЯ ОЦЕНКИ:
Ниже приложен целиком пакет приёмки Цикла 9 `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/package.md` (`sha256=35adea8bc3197709e42854cde111e17b0cdaba1febb6fa6f0f8e9ff7f52bd202`), содержащий без обрезки конверт задачи (`goal.md`, `task.json`, `handoff-architect.md`), манифест кандидата, полный итоговый diff (`candidate-manifest.json`, `candidate.diff`, включая новый тестовый модуль `tests/test_realtime_reasoning.py`), вывод `panel-rework-summarizer` (`handoff/panel-rework-brief.json`), handoff исполнителя и квитанции гейтов (`coder.json`, `receipts/coder.json`, `receipts/code-gate.json`, `receipts/verifier.json`, `receipts/final-gate.json`), а также свидетельства независимой clean-room верификации и слепой reverse-spec (`verification-surface.json`, `environment-manifest.json`, `execution-evidence.md` с сырыми логами, `verification-traceability.md`, `evidence-manifest.sha256`, `reverse-spec.md`):
# Пакет приёмки Совета Тимлидов (`teamlead/package.md`, run `analyst-teamlead-zen-realtime-reasoning-20261025`, cycle `9`)

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
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/task.json sha256=a59aebeed4bd3d23dd192c5b578279d5b52384ac58739d168d22cb63c26943c2
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
  "teamlead_cycle": 9
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
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/candidate-manifest.json sha256=1690f47099a0a472c7662a90a0b2b70f486d0efba151e2583467f8049c110c16
{
  "schema": "candidate-manifest/v1",
  "created_at_utc": "2026-10-27T16:00:55.603003+00:00",
  "run_id": "analyst-teamlead-zen-realtime-reasoning-20261025",
  "cycle": 9,
  "branch": "feature/zen-realtime-reasoning",
  "base_ref": "origin/dev",
  "base_sha": "7eda27f9d82732bab726a420e31ea2adc15c2c39",
  "head_sha": "7eda27f9d82732bab726a420e31ea2adc15c2c39",
  "staged_diff_bytes": 0,
  "binary_files": [],
  "worktree_fingerprint_before_coder": null,
  "worktree_fingerprint_after_coder": null,
  "candidate_diff_path": ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/candidate.diff",
  "candidate_diff_sha256": "87abbc8e77587bdf7bcc61186c0aef08dacff391d6f8c25f0ba1b055d0abf5d7",
  "files": [
    {
      "path": "bridges/opencode-zen-bridge/server.py",
      "status": "modified_unstaged",
      "is_binary": false,
      "bytes": 361460,
      "lines": 8295,
      "sha256": "7fa04234e8f40620a602836a85e4bde421331cf58bd84e5cfd6b2c5fc046f0b9"
    },
    {
      "path": "bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py",
      "status": "added_untracked",
      "is_binary": false,
      "bytes": 190531,
      "lines": 3629,
      "sha256": "3328cdf299dd5edd60c16205f6f967256571366607dc0fc3df5f2015f52a1bef"
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
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/candidate.diff sha256=87abbc8e77587bdf7bcc61186c0aef08dacff391d6f8c25f0ba1b055d0abf5d7
diff --git a/bridges/opencode-zen-bridge/server.py b/bridges/opencode-zen-bridge/server.py
index 667b990..62ad1ef 100755
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
@@ -1131,6 +1526,504 @@ def _run_env(model_id: str = "") -> dict[str, str]:
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
+_MAX_STDERR_TAIL_BYTES = 16384
+_STDERR_CHUNK_READ_BYTES = 4096
+_MAX_SSE_LINE_BYTES = 1024 * 1024
+_STEP_DRAIN_WINDOW_S = 1.0
+_MAX_SERVE_QUEUE_BYTES = 16 * 1024 * 1024
+_MAX_SERVE_ACCUMULATED_BYTES = 16 * 1024 * 1024
+_MAX_SERVE_HTTP_BODY_BYTES = 8 * 1024 * 1024
+
+
+class ServeUnavailable(Exception):
+    """Serve недоступен до барьера доставки: допустим fallback на run в auto."""
+
+
+class ServeClientDisconnect(Exception):
+    """Клиент отключился при запуске serve: повтор через run запрещён."""
+
+
+class ServeStartupDeadlineExceeded(Exception):
+    """Общий бюджет запроса исчерпан при запуске serve."""
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
+        except UnicodeError as exc:
+            raise ServeProtocolError(
+                "invalid unpaired surrogate in serve event"
+            ) from exc
+    if isinstance(value, dict):
+        return {
+            str(_combine_surrogates(str(k))): _combine_surrogates(v)
+            for k, v in value.items()
+        }
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
+    event = _as_dict(_combine_surrogates(event))
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
+
+        def _valid_token_int(value: object) -> bool:
+            return isinstance(value, int) and not isinstance(value, bool) and value >= 0
+
+        if not tokens or any(
+            value is not None and not _valid_token_int(value)
+            for value in (
+                tokens.get("input"),
+                tokens.get("output"),
+                tokens.get("reasoning"),
+                read_obj,
+            )
+        ):
+            raise ServeProtocolError("invalid token count in step_finish")
+        out: dict[str, object] = {}
+        for key in ("input", "output", "reasoning"):
+            value = tokens.get(key)
+            if not _valid_token_int(value):
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
@@ -1138,7 +2031,9 @@ def _variant_for(model_id: str, effort: str) -> str:
         return ""
     values = meta.get("effort_values")
     if values and effort not in values:
-        _log(f"WARN variant {effort!r} is not in effort_values of {model_id}; suffix dropped")
+        _log(
+            f"WARN variant {effort!r} is not in effort_values of {model_id}; suffix dropped"
+        )
         return ""
     return effort
 
@@ -1174,8 +2069,9 @@ def _clean_err(lines: list[str] | str, limit: int = 600) -> str:
     return _mask_secrets(text)[-limit:]
 
 
-def _is_retryable_failure(rc: int | None, err_text: str, provider_status: int | None,
-                          had_output: bool) -> bool:
+def _is_retryable_failure(
+    rc: int | None, err_text: str, provider_status: int | None, had_output: bool
+) -> bool:
     """Прогон без какого-либо вывода и с rc != 0 — транзиторный отказ CLI (повторяем).
 
     Не повторяем: был вывод; процесс убит нами/таймаутом (rc < 0 или None);
@@ -1186,11 +2082,15 @@ def _is_retryable_failure(rc: int | None, err_text: str, provider_status: int |
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
 
 
@@ -1209,10 +2109,29 @@ class _StartupGate:
         self._guard = threading.Lock()
         self._timer: threading.Timer | None = None
 
-    def acquire(self) -> None:
-        if not _STARTUP_LOCK.acquire(timeout=max(0.0, self._wait_s)):
-            _log(f"startup_gate_timeout wait_s={self._wait_s:.1f}, starting without the gate")
-            return
+    def acquire(
+        self,
+        deadline: float | None = None,
+        is_client_gone: Callable[[], bool] | None = None,
+    ) -> None:
+        wait_until = time.monotonic() + max(0.0, self._wait_s)
+        while True:
+            now = time.monotonic()
+            if (is_client_gone is not None and is_client_gone()) or (
+                deadline is not None and now >= deadline
+            ):
+                return
+            remaining = max(
+                0.0,
+                min(wait_until, deadline if deadline is not None else wait_until) - now,
+            )
+            if _STARTUP_LOCK.acquire(timeout=min(0.05, remaining)):
+                break
+            if time.monotonic() >= wait_until:
+                _log(
+                    f"startup_gate_timeout wait_s={self._wait_s:.1f}, starting without the gate"
+                )
+                return
         with self._guard:
             self._held = True
         timer = threading.Timer(STARTUP_GATE_S, self.release)
@@ -1262,20 +2181,30 @@ class _SlotBulkhead:
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
@@ -1312,9 +2241,13 @@ class _SpawnRateLimiter:
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
@@ -1323,29 +2256,76 @@ class _SpawnRateLimiter:
         self._tokens = self._burst
         self._last = clock_fn()
 
-    def acquire(self, max_wait_s: float | None = None) -> bool:
+    def acquire(
+        self,
+        max_wait_s: float | None = None,
+        deadline: float | None = None,
+        is_client_gone: Callable[[], bool] | None = None,
+    ) -> bool:
+        if (is_client_gone is not None and is_client_gone()) or (
+            deadline is not None and self._clock() >= deadline
+        ):
+            return False
         with self._lock:
             now = self._clock()
-            self._tokens = min(self._burst, self._tokens + max(0.0, now - self._last) * self._rate)
+            self._tokens = min(
+                self._burst, self._tokens + max(0.0, now - self._last) * self._rate
+            )
             self._last = now
             wait = max(0.0, (1.0 - self._tokens) / self._rate)
             if max_wait_s is not None and wait > max_wait_s:
                 return False
+            if deadline is not None and wait >= deadline - now:
+                return False
             self._tokens -= 1.0
-        if wait > 0:
-            self._sleep(wait)
+        if deadline is None and is_client_gone is None:
+            if wait > 0:
+                self._sleep(wait)
+            return True
+        ready_at = now + wait
+        while True:
+            now = self._clock()
+            if (is_client_gone is not None and is_client_gone()) or (
+                deadline is not None and now >= deadline
+            ):
+                self.refund()
+                return False
+            if now >= ready_at:
+                break
+            self._sleep(
+                min(
+                    0.05,
+                    ready_at - now,
+                    deadline - now if deadline is not None else 0.05,
+                )
+            )
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
@@ -1353,7 +2333,9 @@ class _RetryBudget:
 
     def _refill_time(self) -> None:
         now = self._clock()
-        self.tokens = min(self._capacity, self.tokens + max(0.0, now - self._last) * self._reserve_rps)
+        self.tokens = min(
+            self._capacity, self.tokens + max(0.0, now - self._last) * self._reserve_rps
+        )
         self._last = now
 
     def on_request(self) -> None:
@@ -1374,12 +2356,18 @@ class _RetryBudget:
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
@@ -1421,7 +2409,10 @@ class _UpstreamBreaker:
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
@@ -1447,7 +2438,9 @@ class _UpstreamBreaker:
                 self._state = "OPEN"
                 self._open_until = now + cooldown
                 self._probes = 0
-                self._say(f"circuit_breaker state=OPEN failures={self._failures} cooldown_s={cooldown:.1f}")
+                self._say(
+                    f"circuit_breaker state=OPEN failures={self._failures} cooldown_s={cooldown:.1f}"
+                )
 
 
 class _Resilience:
@@ -1462,6 +2455,7 @@ class _Resilience:
         self.spawn_limiter = _SpawnRateLimiter(SPAWN_RATE_PER_S, SPAWN_BURST)
         self.retry_budget = _RetryBudget()
         self.breaker = _UpstreamBreaker()
+        self.serve_health = _ServeHealth()
 
 
 _DEFAULT_RESILIENCE = _Resilience()
@@ -1471,13 +2465,20 @@ _slots = _DEFAULT_RESILIENCE.slots  # прежнее имя семафора с
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
@@ -1491,13 +2492,22 @@ class _RequestAttempts:
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
@@ -1517,7 +2527,11 @@ class _RequestAttempts:
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
@@ -1564,7 +2578,7 @@ class _PrefixDedup:
         current, prefix = self.current, self.prefix
         if current.startswith(prefix):
             self.prefix = ""
-            return current[len(prefix):]
+            return current[len(prefix) :]
         if len(current) >= len(prefix) or not prefix.startswith(current):
             self.prefix = ""
             return "\n\n" + current
@@ -1579,28 +2593,1550 @@ class _PrefixDedup:
         return leftover
 
 
-def _dedup_retry_text(prefix: str, current: str) -> str:
-    """JSON-вариант dedup_prefix: подавить уже отданный префикс, переформулированный текст сохранить целиком."""
-    if prefix and current.startswith(prefix):
-        return current[len(prefix):]
-    return current
+def _dedup_retry_text(prefix: str, current: str) -> str:
+    """JSON-вариант dedup_prefix: подавить уже отданный префикс, переформулированный текст сохранить целиком."""
+    if prefix and current.startswith(prefix):
+        return current[len(prefix) :]
+    return current
+
+
+def _parent_lstart(deadline: float | None = None) -> str:
+    """lstart родителя дляargv помощника."""
+    try:
+        out = subprocess.run(
+            ["ps", "-o", "lstart=", "-p", str(os.getpid())],
+            capture_output=True,
+            text=True,
+            timeout=2.0
+            if deadline is None
+            else max(0.001, min(2.0, deadline - time.monotonic())),
+        )
+        return out.stdout.strip() or str(int(time.time()))
+    except (OSError, subprocess.SubprocessError):
+        return str(int(time.time()))
+
+
+def _lsof_listener_pid(port: int, deadline: float | None = None) -> int | None:
+    """PID слушателя порта одним вызовом lsof."""
+    _LSOF_CALLS.append(port)
+    try:
+        out = subprocess.run(
+            ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
+            capture_output=True,
+            text=True,
+            timeout=2.0
+            if deadline is None
+            else max(0.001, min(2.0, deadline - time.monotonic())),
+        )
+    except (OSError, subprocess.SubprocessError):
+        return None
+    for line in out.stdout.splitlines():
+        if line.strip().isdecimal():
+            return int(line.strip())
+    return None
+
+
+def _check_serve_start(
+    deadline: float | None, is_client_gone: Callable[[], bool] | None
+) -> None:
+    """Отмена и общий дедлайн не означают недоступность транспорта."""
+    if is_client_gone is not None and is_client_gone():
+        raise ServeClientDisconnect("client disconnected before serve spawn")
+    if deadline is not None and time.monotonic() >= deadline:
+        raise ServeStartupDeadlineExceeded("deadline expired before serve spawn")
+
+
+def _watch_serve_connection(
+    conn: http.client.HTTPConnection,
+    deadline: float | None,
+    is_client_gone: Callable[[], bool] | None,
+    phase_socket: list[socket.socket | None],
+) -> threading.Event:
+    """Прервать даже капающие HTTP-заголовки по абсолютному сроку или отмене."""
+    stopped = threading.Event()
+
+    def watch() -> None:
+        while not stopped.wait(0.01):
+            if (deadline is not None and time.monotonic() >= deadline) or (
+                is_client_gone is not None and is_client_gone()
+            ):
+                sock = conn.sock or phase_socket[0]
+                if sock is not None:
+                    try:
+                        _ = sock.shutdown(socket.SHUT_RDWR)
+                    except OSError:
+                        pass
+                    try:
+                        _ = sock.close()
+                    except OSError:
+                        pass
+                return
+
+    if deadline is not None or is_client_gone is not None:
+        threading.Thread(target=watch, daemon=True).start()
+    return stopped
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
+    skip_body: bool = False,
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
+    phase_socket: list[socket.socket | None] = [None]
+    stopped = _watch_serve_connection(
+        active_conn, deadline, is_client_gone, phase_socket
+    )
+
+    def check_phase() -> None:
+        """Ограничить следующую фазу оставшимся бюджетом и проверить отмену."""
+        if is_client_gone is not None and is_client_gone():
+            raise BrokenPipeError(errno.EPIPE, "client gone")
+        remaining = (
+            timeout if deadline is None else min(timeout, deadline - time.monotonic())
+        )
+        if remaining <= 0:
+            active_conn.close()
+            raise TimeoutError("serve http deadline expired")
+        active_conn.timeout = remaining
+        connected_socket = active_conn.sock or phase_socket[0]
+        if connected_socket is not None and connected_socket.fileno() >= 0:
+            _ = connected_socket.settimeout(remaining)
+
+    try:
+        check_phase()
+        payload = json.dumps(body).encode("utf-8") if body is not None else None
+        auth = base64.b64encode(f"opencode:{password}".encode("utf-8")).decode("ascii")
+        headers = {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}
+        active_conn.request(method, path, payload, headers)
+        # HTTP/1.0 отделяет сокет от conn после заголовков; бюджет тела остаётся обязательным.
+        phase_socket[0] = active_conn.sock
+        check_phase()
+        try:
+            resp = active_conn.getresponse()
+        except (AttributeError, ValueError):
+            check_phase()
+            raise
+        if on_headers is not None:
+            on_headers(int(resp.status))
+        if skip_body:
+            active_conn.close()
+            resp.close()
+            return int(resp.status), {}
+        raw = bytearray()
+        while not resp.isclosed():
+            check_phase()
+            try:
+                chunk = resp.read1(65536)
+            except (AttributeError, ValueError):
+                check_phase()
+                raise
+            check_phase()
+            if not chunk:
+                break
+            raw.extend(chunk)
+            if len(raw) > _MAX_SERVE_HTTP_BODY_BYTES:
+                active_conn.close()
+                resp.close()
+                raise ServeProtocolError("serve http response body exceeds max bytes")
+        parsed: dict[str, object] = {}
+        if raw:
+            parsed = _as_dict(_loads_object(raw.decode("utf-8", "replace")))
+        return int(resp.status), parsed
+    finally:
+        stopped.set()
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
+        self.stderr_tail: bytearray = bytearray()
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
+    attempt_id: str,
+    serve_env: dict[str, str],
+    deadline: float | None = None,
+    is_client_gone: Callable[[], bool] | None = None,
+) -> tuple[_ServeLease, int, str]:
+    """Запуск helper->serve, проверка слушателя и рукопожатия."""
+    port = 0
+    lifeline_w = -1
+    lease: _ServeLease | None = None
+    state_dir = serve_env.get("XDG_STATE_HOME", "")
+    try:
+        _check_serve_start(deadline, is_client_gone)
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
+        parent_lstart = _parent_lstart(deadline)
+        lifeline_r, lifeline_w = os.pipe()
+        try:
+            _check_serve_start(deadline, is_client_gone)
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
+                    parent_lstart,
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
+        stderr_tail = lease.stderr_tail
+
+        def _drain_helper_stderr() -> None:
+            """Дренировать пайп до handshake порциями, ограничивая хвост по байтам."""
+            assert helper.stderr is not None
+            try:
+                while True:
+                    chunk = os.read(helper.stderr.fileno(), _STDERR_CHUNK_READ_BYTES)
+                    if not chunk:
+                        return
+                    stderr_tail[:] = (stderr_tail + chunk)[-_MAX_STDERR_TAIL_BYTES:]
+            except (OSError, ValueError):
+                return
+
+        threading.Thread(target=_drain_helper_stderr, daemon=True).start()
+        assert helper.stdout is not None
+        out_fd = helper.stdout.fileno()
+        _hs_deadline = (
+            min(time.monotonic() + 3.0, deadline)
+            if deadline is not None
+            else time.monotonic() + 3.0
+        )
+        line_bytes = b""
+        while not line_bytes.endswith(b"\n"):
+            _check_serve_start(deadline, is_client_gone)
+            if time.monotonic() >= _hs_deadline:
+                raise ServeUnavailable("serve helper handshake timeout")
+            _ready, _w2, _x2 = select.select(
+                [out_fd], [], [], min(0.05, max(0.0, _hs_deadline - time.monotonic()))
+            )
+            if not _ready:
+                continue
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
+        _check_serve_start(deadline, is_client_gone)
+        _listener_deadline = (
+            min(time.monotonic() + 3.0, deadline)
+            if deadline is not None
+            else time.monotonic() + 3.0
+        )
+        listener_pid = _lsof_listener_pid(port, _listener_deadline)
+        while (
+            listener_pid is None
+            and time.monotonic() < _listener_deadline
+            and helper.poll() is None
+        ):
+            _check_serve_start(deadline, is_client_gone)
+            time.sleep(min(0.05, max(0.0, _listener_deadline - time.monotonic())))
+            listener_pid = _lsof_listener_pid(port, _listener_deadline)
+        _check_serve_start(deadline, is_client_gone)
+        if not (
+            listener_pid is not None
+            and listener_pid == serve_pid
+            and _pid_pgid(listener_pid) == pgid
+            and helper.poll() is None
+        ):
+            raise ServeUnavailable(
+                "listener ownership verification failed: foreign listener on serve port"
+            )
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
+            args = _as_dict(_combine_surrogates(parsed))
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
+def _open_serve_events(
+    port: int,
+    password: str,
+    deadline: float,
+    is_client_gone: Callable[[], bool] | None,
+) -> tuple[http.client.HTTPConnection, http.client.HTTPResponse]:
+    """Открыть подписку с общим дедлайном, прерывая даже капающие заголовки."""
+    _check_serve_start(deadline, is_client_gone)
+    sub_deadline = min(deadline, time.monotonic() + float(FIRST_EVENT_TIMEOUT_S))
+    conn = http.client.HTTPConnection(
+        "127.0.0.1",
+        port,
+        timeout=max(
+            0.05, min(float(FIRST_EVENT_TIMEOUT_S), deadline - time.monotonic())
+        ),
+    )
+    auth = base64.b64encode(f"opencode:{password}".encode("utf-8")).decode("ascii")
+    phase_socket: list[socket.socket | None] = [None]
+    stopped = _watch_serve_connection(conn, sub_deadline, is_client_gone, phase_socket)
+    try:
+        conn.request(
+            "GET",
+            "/api/event",
+            None,
+            {"Authorization": f"Basic {auth}", "Accept": "text/event-stream"},
+        )
+        phase_socket[0] = conn.sock
+        _check_serve_start(sub_deadline, is_client_gone)
+        response = conn.getresponse()
+        _check_serve_start(sub_deadline, is_client_gone)
+        if response.status in (400, 401, 403, 404, 422):
+            raise ServeSecurityError(f"serve event HTTP {response.status}")
+        if response.status != 200:
+            raise ServeUnavailable(f"serve event HTTP {response.status}")
+        # После заголовков паузы SSE контролирует цикл попытки, включая HTTP/1.0 с отделённым сокетом.
+        if phase_socket[0] is not None:
+            _ = phase_socket[0].settimeout(None)
+        return conn, response
+    except (ServeStartupDeadlineExceeded, OSError, http.client.HTTPException) as exc:
+        conn.close()
+        _check_serve_start(deadline, is_client_gone)
+        if time.monotonic() >= sub_deadline:
+            raise ServeUnavailable("serve event subscribe timeout") from exc
+        raise
+    except BaseException:
+        conn.close()
+        raise
+    finally:
+        stopped.set()
+
+
+def _cleanup_serve_attempt(
+    lease: _ServeLease,
+    port: int,
+    password: str,
+    session_id: str,
+    sse_conn: http.client.HTTPConnection | None,
+    control_conn: http.client.HTTPConnection | None,
+    stop_event: threading.Event | None,
+    reader_thread: threading.Thread | None,
+    prompt_thread: threading.Thread | None,
+) -> None:
+    """Общий короткий бюджет потоков и HTTP перед обязательной уборкой группы."""
+    cleanup_deadline = time.monotonic() + 0.45
+    if stop_event is not None:
+        stop_event.set()
+    if sse_conn is not None:
+        if sse_conn.sock is not None:
+            try:
+                _ = sse_conn.sock.shutdown(socket.SHUT_RDWR)
+            except OSError:
+                pass
+        try:
+            sse_conn.close()
+        except OSError:
+            pass
+    try:
+        for thread in (reader_thread, prompt_thread):
+            if thread is not None:
+                thread.join(
+                    timeout=min(0.2, max(0.0, cleanup_deadline - time.monotonic()))
+                )
+        if session_id:
+            for method, path in (
+                ("POST", f"/api/session/{session_id}/interrupt"),
+                ("DELETE", f"/api/session/{session_id}"),
+            ):
+                try:
+                    _ = _serve_http(
+                        port,
+                        password,
+                        method,
+                        path,
+                        timeout=0.25,
+                        deadline=cleanup_deadline,
+                        skip_body=True,
+                    )
+                except (OSError, http.client.HTTPException):
+                    pass
+        if control_conn is not None:
+            try:
+                control_conn.close()
+            except OSError:
+                pass
+    finally:
+        lease.cleanup()
+
+
+def _serve_attempt_error_reason(
+    exc: Exception,
+    deadline: float,
+    is_client_gone: Callable[[], bool] | None,
+    delivered: bool,
+) -> str:
+    """Отличить отмену и протокольный отказ от допустимого pre-prompt fallback."""
+    if is_client_gone is not None and is_client_gone():
+        return "client_gone"
+    if time.monotonic() >= deadline:
+        return "timeout"
+    if isinstance(exc, ServeProtocolError):
+        return "invalid_serve_event"
+    if delivered:
+        return "prompt_error"
+    raise ServeUnavailable(f"serve startup failed: {exc}") from exc
+
+
+def _drain_serve_step_usage(
+    events: queue.Queue[dict[str, object] | None],
+    session_id: str,
+    assistant_message_id: object,
+    deadline: float,
+    usage: dict[str, int],
+    tool_state: _ServeToolState,
+    result: _ServeResult,
+    on_tool: Callable[[dict[str, object]], None],
+    release_event: Callable[[dict[str, object]], None],
+) -> bool:
+    """Дочитать все native-вызовы и usage до подтверждённого конца того же шага."""
+    while time.monotonic() < deadline:
+        try:
+            event = events.get(timeout=max(0.0, deadline - time.monotonic()))
+        except queue.Empty:
+            return False
+        if event is None:
+            return False
+        release_event(event)
+        event_type = str(event.get("type") or "")
+        if event_type == "__invalid_json__":
+            raise ServeProtocolError("invalid event while draining tool step")
+        data = _as_dict(event.get("data"))
+        ev_msg_id = data.get("assistantMessageID")
+        if data.get("sessionID") != session_id or (
+            assistant_message_id and ev_msg_id and ev_msg_id != assistant_message_id
+        ):
+            continue
+        mapped = _map_serve_event(event)
+        if mapped is not None and mapped[0] == "tool_event":
+            if not assistant_message_id and ev_msg_id:
+                assistant_message_id = ev_msg_id
+            tool_state.feed(mapped[1])
+            if event_type in (
+                "session.tool.called",
+                "session.tool.failed",
+                "session.tool.success",
+            ):
+                done = tool_state.complete(str(mapped[1].get("id") or ""), event_type)
+                if done is not None:
+                    result["native_calls"].append(done[1])
+                    on_tool(done[1])
+            continue
+        if mapped is not None and mapped[0] == "step_finish":
+            for call_id in list(tool_state.tools):
+                done = tool_state.complete(call_id, event_type)
+                if done is not None:
+                    result["native_calls"].append(done[1])
+                    on_tool(done[1])
+            for key in ("input", "output", "cached", "reasoning"):
+                usage[key] = usage.get(key, 0) + _as_int(mapped[1].get(key))
+            return True
+    return False
+
+
+def _read_serve_events(
+    sse_resp: http.client.HTTPResponse,
+    events: queue.Queue[dict[str, object] | None],
+    stop_event: threading.Event,
+    queued_bytes: list[int],
+    queue_bytes_lock: threading.Lock,
+    release_event: Callable[[dict[str, object]], None],
+) -> None:
+    """Читать SSE с ограничением байтов очереди в пределах одной попытки."""
+
+    def _put_event(item: dict[str, object] | None) -> bool:
+        """Неблокирующая постановка с проверкой stop_event."""
+        while not stop_event.is_set():
+            try:
+                events.put(item, timeout=0.25)
+                return True
+            except queue.Full:
+                continue
+        return False
+
+    def _read() -> None:
+        """Читатель SSE в очередь событий; тишина сокета не рвёт поток."""
+        try:
+            while not stop_event.is_set():
+                try:
+                    line = sse_resp.readline(_MAX_SSE_LINE_BYTES + 1)
+                except OSError:
+                    # Сокет закрыт или сброшен: watchdog главного цикла решает судьбу попытки.
+                    break
+                if not line:
+                    break
+                if len(line) > _MAX_SSE_LINE_BYTES:
+                    _ = _put_event({"type": "__invalid_json__", "data": {}})
+                    break
+                text_line = line.decode("utf-8", "replace").strip()
+                if not text_line.startswith("data:"):
+                    continue
+                payload = text_line[5:].strip()
+                if not payload or payload == "[DONE]":
+                    continue
+                try:
+                    obj: dict[str, object] | None = _loads_serve_object(payload)
+                except ServeProtocolError:
+                    _ = _put_event({"type": "__invalid_json__", "data": {}})
+                    continue
+                with queue_bytes_lock:
+                    overflow = queued_bytes[0] + len(line) > _MAX_SERVE_QUEUE_BYTES
+                    if not overflow:
+                        queued_bytes[0] += len(line)
+                        obj["_raw_bytes"] = len(line)
+                if overflow:
+                    _ = _put_event({"type": "__invalid_json__", "data": {}})
+                    break
+                if not _put_event(obj):
+                    release_event(obj)
+                    break
+        except (OSError, ValueError):
+            pass
+        finally:
+            _ = _put_event(None)
+
+    _read()
+
+
+def _serve_step_message_id(
+    data: dict[str, object], session_id: str, step_closed: bool, current: str
+) -> str:
+    """Запомнить ID только открытого шага текущей сессии."""
+    msg_id = data.get("assistantMessageID")
+    if (
+        data.get("sessionID") == session_id
+        and not step_closed
+        and isinstance(msg_id, str)
+        and msg_id
+    ):
+        return msg_id
+    return current
+
+
+def _serve_accumulated_bytes(
+    current: int, event_type: str, payload: dict[str, object]
+) -> int:
+    """Учесть общий UTF-8 бюджет текста и размышлений до выдачи клиенту."""
+    if event_type in ("reasoning", "text"):
+        text_value = str(
+            payload.get("reasoning_content" if event_type == "reasoning" else "content")
+            or ""
+        )
+        current += len(text_value.encode("utf-8", "replace"))
+        if current > _MAX_SERVE_ACCUMULATED_BYTES:
+            raise ServeProtocolError("serve accumulated response byte budget exceeded")
+    return current
+
+
+def _finish_serve_tool_step(
+    events: queue.Queue[dict[str, object] | None],
+    session_id: str,
+    assistant_message_id: object,
+    deadline: float,
+    tool_state: _ServeToolState,
+    result: _ServeResult,
+    on_tool: Callable[[dict[str, object]], None],
+    release_event: Callable[[dict[str, object]], None],
+) -> None:
+    """Закрыть инструментальный шаг только после подтверждённого step.ended."""
+    step_confirmed = _drain_serve_step_usage(
+        events,
+        session_id,
+        assistant_message_id,
+        deadline,
+        result["usage"],
+        tool_state,
+        result,
+        on_tool,
+        release_event,
+    )
+    if not step_confirmed:
+        raise ServeProtocolError("incomplete tool step without step.ended")
+    result["terminal"] = "tool_calls"
+    result["step_closed"] = True
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
+        result["delivered"] = True
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
+    try:
+        lease, port, _pw = _spawn_serve(
+            attempt_id,
+            serve_env,
+            deadline=attempt_deadline,
+            is_client_gone=is_client_gone,
+        )
+    except (ServeClientDisconnect, ServeStartupDeadlineExceeded) as exc:
+        result["exit_reason"] = (
+            "client_gone" if isinstance(exc, ServeClientDisconnect) else "timeout"
+        )
+        result["delivered"] = True
+        return result
+    session_id = ""
+    sse_conn: http.client.HTTPConnection | None = None
+    prompt_status: dict[str, object] = {}
+    control_conn: list[http.client.HTTPConnection | None] = [None]
+    stop_event: threading.Event | None = None
+    reader_thread: threading.Thread | None = None
+    prompt_thread: threading.Thread | None = None
+
+    def _is_delivered() -> bool:
+        return bool(
+            prompt_status.get("headers_at")
+            or result["first_event_at"] is not None
+            or result["texts"]
+            or result["reasonings"]
+            or result["native_calls"]
+        )
+
+    def _ctrl_http(
+        method: str,
+        path: str,
+        body: dict[str, object] | None = None,
+        timeout: float = 3.0,
+        phase_deadline: float | None = None,
+    ) -> tuple[int, dict[str, object]]:
+        """Управляющий вызов serve по одному keep-alive соединению."""
+        call_deadline = min(
+            attempt_deadline,
+            phase_deadline
+            if phase_deadline is not None
+            else time.monotonic() + float(timeout),
+        )
+        for attempt in (0, 1):
+            _check_serve_start(attempt_deadline, is_client_gone)
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
+                    deadline=call_deadline,
+                    is_client_gone=is_client_gone,
+                )
+            except (OSError, http.client.HTTPException):
+                _check_serve_start(attempt_deadline, is_client_gone)
+                try:
+                    conn.close()
+                except OSError:
+                    pass
+                control_conn[0] = None
+                if attempt or time.monotonic() >= call_deadline:
+                    raise
+        raise ServeUnavailable("serve control connection failed")
+
+    try:
+        status = 0
+        active: dict[str, object] = {}
+        ready_deadline = min(time.monotonic() + 3.0, attempt_deadline)
+        while True:
+            try:
+                status, active = _ctrl_http(
+                    "GET",
+                    "/api/session/active",
+                    timeout=3.0,
+                    phase_deadline=ready_deadline,
+                )
+                break
+            except (OSError, http.client.HTTPException) as exc:
+                _check_serve_start(attempt_deadline, is_client_gone)
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
+            phase_deadline=min(time.monotonic() + 3.0, attempt_deadline),
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
+        sse_conn, sse_resp = _open_serve_events(
+            port, password, attempt_deadline, is_client_gone
+        )
+        events: queue.Queue[dict[str, object] | None] = queue.Queue(maxsize=4096)
+        stop_event = threading.Event()
+        queued_bytes = [0]
+        queue_bytes_lock = threading.Lock()
+        accumulated_bytes = 0
+        current_step_msg_id = ""
+
+        def _release_event(event: dict[str, object]) -> None:
+            """Вернуть байтовый резерв после извлечения события из очереди."""
+            with queue_bytes_lock:
+                queued_bytes[0] -= _as_int(event.pop("_raw_bytes", 0))
+
+        if sse_conn.sock is not None:
+            # Без таймаута сокета: после первого таймаута SocketIO считает поток закрытым,
+            # а любая пауза SSE > 0.5 с превращалась бы в ложный EOF. Остановка — shutdown в finally.
+            _ = sse_conn.sock.settimeout(None)
+        if on_startup_ready is not None:
+            on_startup_ready()
+
+        reader_thread = threading.Thread(
+            target=_read_serve_events,
+            args=(
+                sse_resp,
+                events,
+                stop_event,
+                queued_bytes,
+                queue_bytes_lock,
+                _release_event,
+            ),
+            daemon=True,
+        )
+        reader_thread.start()
+        prompt_send_start = time.monotonic()
+
+        def _prompt_worker() -> None:
+            """Доставка prompt параллельно чтению SSE."""
+
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
+            except ServeProtocolError as exc:
+                prompt_status["protocol_error"] = str(exc)
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
+            if prompt_status.get("protocol_error"):
+                result["exit_reason"] = "invalid_serve_event"
+                return result
+            now = time.monotonic()
+            if result["first_event_at"] is None and now - prompt_send_start > float(
+                FIRST_EVENT_TIMEOUT_S
+            ):
+                result["exit_reason"] = "first_event_timeout"
+                result["delivered"] = _is_delivered()
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
+                _delivered_now = _is_delivered()
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
+                _has_delivery = _is_delivered()
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
+                    result["delivered"] = _is_delivered()
+                break
+            _release_event(event)
+            etype_raw = str(event.get("type") or "")
+            if etype_raw == "__invalid_json__":
+                result["exit_reason"] = "invalid_serve_event"
+                result["delivered"] = _is_delivered()
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
+            current_step_msg_id = _serve_step_message_id(
+                data_raw, session_id, result["step_closed"], current_step_msg_id
+            )
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
+                result["delivered"] = _is_delivered()
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
+            accumulated_bytes = _serve_accumulated_bytes(
+                accumulated_bytes, etype, payload
+            )
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
+                        if emulate_tools:
+                            _finish_serve_tool_step(
+                                events,
+                                session_id,
+                                data_raw.get("assistantMessageID")
+                                or current_step_msg_id
+                                or None,
+                                min(deadline, time.monotonic() + _STEP_DRAIN_WINDOW_S),
+                                tool_state,
+                                result,
+                                on_tool,
+                                _release_event,
+                            )
+                            break
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
+                result["delivered"] = _is_delivered()
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
+        result["delivered"] = result["delivered"] | _is_delivered()
+        return result
+    except (ServeClientDisconnect, ServeStartupDeadlineExceeded) as exc:
+        result["exit_reason"] = (
+            "client_gone" if isinstance(exc, ServeClientDisconnect) else "timeout"
+        )
+        result["delivered"] = True
+        return result
+    except (OSError, http.client.HTTPException, ServeProtocolError) as exc:
+        result["exit_reason"] = _serve_attempt_error_reason(
+            exc, attempt_deadline, is_client_gone, _is_delivered()
+        )
+        result["delivered"] = _is_delivered() | (
+            result["exit_reason"] in ("client_gone", "timeout")
+        )
+        result["transient_error"] = result["exit_reason"] == "prompt_error"
+        return result
+    finally:
+        result["delivered"] = result["delivered"] | _is_delivered()
+        _cleanup_serve_attempt(
+            lease,
+            port,
+            password,
+            session_id,
+            sse_conn,
+            control_conn[0],
+            stop_event,
+            reader_thread,
+            prompt_thread,
+        )
+        result["delivered"] = result["delivered"] | _is_delivered()
 
 
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
@@ -1658,7 +4194,9 @@ def _auth_ok(handler: BaseHTTPRequestHandler) -> bool:
     hdr = handler.headers.get("Authorization", "")
     if hdr.startswith("Bearer "):
         return _token_eq(hdr[7:].strip(), AUTH_KEY)
-    return _token_eq(handler.headers.get("x-api-key", ""), AUTH_KEY) or _token_eq(hdr.strip(), AUTH_KEY)
+    return _token_eq(handler.headers.get("x-api-key", ""), AUTH_KEY) or _token_eq(
+        hdr.strip(), AUTH_KEY
+    )
 
 
 def _flatten_content(content: Any) -> str:
@@ -1691,10 +4229,16 @@ _SECRET = re.compile(
 
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
 
 
@@ -2154,7 +4698,9 @@ def _find_close_in(text: str, start: int, close_tag: str = TOOL_CALL_CLOSE) -> i
 
 
 _STRIP_SCAN_MAX_TAGS = 16  # граница CPU: `_code_context` — O(len) на кандидата
-_BROKEN_BLOCK_NOTICE = "[opencode-zen-bridge: невалидный блок вызова инструмента отброшен]"
+_BROKEN_BLOCK_NOTICE = (
+    "[opencode-zen-bridge: невалидный блок вызова инструмента отброшен]"
+)
 
 
 def _strip_broken_tool_blocks(text: str, *, quiet: bool = False) -> tuple[str, int]:
@@ -2224,7 +4770,9 @@ class ToolCallParser:
         self._history = ""  # весь текст, ушедший в content
         self.tool_calls_count = 0
         self.trailing_chars_after_tool = 0
-        self._tail_after_tool = ""  # весь текст после последнего вызова (для инварианта к чанкам)
+        self._tail_after_tool = (
+            ""  # весь текст после последнего вызова (для инварианта к чанкам)
+        )
 
     def feed(self, text: str) -> None:
         self._buf += text
@@ -2235,19 +4783,22 @@ class ToolCallParser:
 
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
@@ -2285,11 +4836,13 @@ class ToolCallParser:
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
@@ -2308,15 +4861,22 @@ class ToolCallParser:
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
 
@@ -2492,7 +5052,9 @@ def _resolve_opencode_go_auth() -> tuple[str, str]:
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
@@ -2594,10 +5156,14 @@ _CDATA_END_MIN = 6
 
 
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
@@ -2612,10 +5178,12 @@ def _in_active_markdown_table(text: str, loop_start: int, sep_ends: list[int] |
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
@@ -2633,7 +5201,9 @@ def _is_table_block(unit: str, text: str = "", loop_start: int = 0) -> bool:
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
@@ -2654,7 +5224,9 @@ def _cdata_loop_start(text: str) -> int | None:
     seps = [m.end() for m in _TABLE_SEP_RE.finditer(text)]
 
     def is_terminator(pos: int) -> bool:
-        return "<![CDATA[" not in text[max(0, pos - 300):pos] and not _in_active_markdown_table(text, pos, seps)
+        return "<![CDATA[" not in text[
+            max(0, pos - 300) : pos
+        ] and not _in_active_markdown_table(text, pos, seps)
 
     recent = []
     pos = text.find("]]>", recent_start)
@@ -2665,7 +5237,9 @@ def _cdata_loop_start(text: str) -> int | None:
     if len(recent) < _CDATA_END_MIN:
         return None
     start = recent[0]
-    while (prev := text.rfind("]]>", max(0, start - _CDATA_GAP_MAX), start)) >= 0 and is_terminator(prev):
+    while (
+        prev := text.rfind("]]>", max(0, start - _CDATA_GAP_MAX), start)
+    ) >= 0 and is_terminator(prev):
         start = prev
     return start
 
@@ -2674,7 +5248,10 @@ def _detect_repetition_loop(text: str) -> int | None:
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
@@ -2685,15 +5262,19 @@ def _detect_repetition_loop(text: str) -> int | None:
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
@@ -2702,7 +5283,9 @@ def _detect_repetition_loop(text: str) -> int | None:
 _THOUGHT_CLOSED_RE = re.compile(r"<unused94>thought\b.*?<unused95>\s*", re.DOTALL)
 _THOUGHT_OPEN_RE = re.compile(r"<unused94>thought\b.*$", re.DOTALL)
 _CDATA_LOOP_RE = re.compile(
-    r"(?:(?:Sub-thought finished\.|end\.|stop\.)?\s*\]\]>\s*(?:Let's [^\n\]]*)?\s*){2,}.*$", re.DOTALL)
+    r"(?:(?:Sub-thought finished\.|end\.|stop\.)?\s*\]\]>\s*(?:Let's [^\n\]]*)?\s*){2,}.*$",
+    re.DOTALL,
+)
 
 
 def _strip_unclosed_tool_calls(text: str) -> str:
@@ -2710,10 +5293,16 @@ def _strip_unclosed_tool_calls(text: str) -> str:
 
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
@@ -2737,26 +5326,46 @@ def _sanitize_assistant_text(text: str) -> str:
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
@@ -2844,6 +5453,7 @@ class Run:
         self.attempts = attempts
         self.proc: subprocess.Popen[str] | None = None
         self.feed: _StdoutFeed | None = None
+        self.is_client_gone: Callable[[], bool] | None = None
 
     def close(self) -> None:
         proc = self.proc
@@ -2881,6 +5491,17 @@ class Run:
         try:
             while True:
                 out = self._execute_once()
+                if out.get("state") in (
+                    "first_event_timeout",
+                    "first_token_timeout",
+                    "stall_timeout",
+                ):
+                    if attempts.can_spawn() and attempts.allow_retry(
+                        str(out.get("state"))
+                    ):
+                        self.close()
+                        continue
+                    return out
                 if fail_retries >= FAIL_RETRY_LIMIT or not _is_retryable_failure(
                         out.get("rc"), str(out.get("err") or ""), out.get("provider_status"),
                         bool(out.get("had_output"))):
@@ -2914,14 +5535,48 @@ class Run:
         _log(f"exec model={model_route} {shown} prompt_chars={len(self.prompt)} cwd={self.workdir}")
         deadline = self.attempts.deadline if self.attempts is not None else time.monotonic() + TIMEOUT_S
         gate = _StartupGate()
-        gate.acquire()
-        if not self.res.spawn_limiter.acquire(max_wait_s=min(SPAWN_WAIT_MAX_S, max(0.0, deadline - time.monotonic()))):
+        gate.acquire(deadline=deadline, is_client_gone=self.is_client_gone)
+        if not self.res.spawn_limiter.acquire(
+            max_wait_s=min(SPAWN_WAIT_MAX_S, max(0.0, deadline - time.monotonic())),
+            deadline=deadline,
+            is_client_gone=self.is_client_gone,
+        ):
+            gate.release()
+            if self.attempts is not None:
+                self.attempts.attempt_done(False, False)
+            return {
+                "rc": -1,
+                "text": "",
+                "reasoning": "",
+                "usage": {},
+                "err": "spawn rate limit: deadline exceeded",
+                "state": "client_gone"
+                if self.is_client_gone is not None and self.is_client_gone()
+                else "timeout",
+                "finish": "error",
+            }
+        if (
+            self.is_client_gone is not None and self.is_client_gone()
+        ) or time.monotonic() >= deadline:
+            self.res.spawn_limiter.refund()
             gate.release()
-            return {"rc": -1, "text": "", "reasoning": "", "usage": {}, "err": "spawn rate limit: deadline exceeded",
-                    "state": "timeout", "finish": "error"}
+            if self.attempts is not None:
+                self.attempts.attempt_done(False, False)
+            return {
+                "rc": -1,
+                "text": "",
+                "reasoning": "",
+                "usage": {},
+                "err": "request cancelled or deadline exceeded",
+                "state": "client_gone"
+                if self.is_client_gone is not None and self.is_client_gone()
+                else "timeout",
+                "finish": "error",
+            }
         try:
             self.proc = _spawn_with_stdin(cmd, self.prompt, self.workdir, env)
         except OSError as exc:
+            self.res.spawn_limiter.refund()
             gate.release()
             return {"rc": -1, "text": "", "reasoning": "", "usage": {}, "err": f"spawn failed: {exc}",
                     "state": "spawn_failed", "finish": "error"}
@@ -2938,6 +5593,12 @@ class Run:
         fatal_error = False     # детерминированная ошибка посреди ответа (400/401/403/404/422): без повтора
         stopped_on_error = False
         state = "ok"
+        attempt_start = time.monotonic()
+        first_event_at: float | None = None
+        first_token_at: float | None = None
+        last_token_at: float | None = None
+        watchdog_reason: list[str] = []
+        subagent_started_at: dict[str, float] = {}
         run_id = uuid.uuid4().hex[:8]
 
         with _active_lock:
@@ -2956,9 +5617,44 @@ class Run:
         err_thread = threading.Thread(target=drain_stderr, daemon=True)
         err_thread.start()
 
+        def on_idle() -> None:
+            """Прервать молчащий JSON-прогон при закрытии клиентского сокета."""
+            nonlocal state
+            if self.is_client_gone is not None and self.is_client_gone():
+                state = "client_gone"
+                if self.proc is not None:
+                    _stop_proc(self.proc)
+                return
+            if watchdog_reason:
+                return
+            now = time.monotonic()
+            reason = ""
+            if first_event_at is None and now - attempt_start > float(
+                FIRST_EVENT_TIMEOUT_S
+            ):
+                reason = "first_event_timeout"
+            elif first_token_at is None and now - attempt_start > float(
+                FIRST_TOKEN_TIMEOUT_S
+            ):
+                reason = "first_token_timeout"
+            elif (
+                last_token_at is not None
+                and not subagent_started_at
+                and now - last_token_at > float(STALL_TIMEOUT_S)
+            ):
+                reason = "stall_timeout"
+            if reason:
+                watchdog_reason.append(reason)
+                state = reason
+                _log(f"opencode run watchdog: {reason}")
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
@@ -2971,6 +5667,35 @@ class Run:
                     continue
 
                 etype, payload = parse_opencode_event(event)
+                if isinstance(event, dict):
+                    now_ev = time.monotonic()
+                    if first_event_at is None:
+                        first_event_at = now_ev
+                    frame = _as_dict(cast(object, payload))
+                    token = (
+                        frame.get("content")
+                        if etype == "text"
+                        else frame.get("reasoning_content")
+                    )
+                    if (
+                        etype in ("text", "reasoning")
+                        and isinstance(token, str)
+                        and token
+                    ) or etype in ("tool_use", "tool_call"):
+                        if first_token_at is None:
+                            first_token_at = now_ev
+                        last_token_at = now_ev
+                    part = _as_dict(_as_dict(cast(object, event)).get("part"))
+                    if (
+                        etype in ("tool_use", "tool_call")
+                        and part.get("tool") == "task"
+                    ):
+                        task_id = str(part.get("id") or "task")
+                        task_status = _as_dict(part.get("state")).get("status")
+                        if task_status in ("pending", "running"):
+                            subagent_started_at[task_id] = now_ev
+                        else:
+                            _ = subagent_started_at.pop(task_id, None)
                 if etype == "text":
                     ttext = payload.get("content")
                     if isinstance(ttext, str):
@@ -3019,6 +5744,9 @@ class Run:
                         _stop_proc(self.proc)
                         break
                     _log("exec: early provider error (waiting for CLI recovery)")
+            if watchdog_reason:
+                state = watchdog_reason[0]
+                err_lines.append(f"opencode run watchdog: {state}")
             if self.feed.overflowed:
                 state = "stdout_overflow"
                 err_lines.append("stdout queue overflow")
@@ -3054,20 +5782,66 @@ class Run:
         if rc != 0 and err_tail:
             _log(f"exec cli failed rc={rc} state={state} stderr_tail={err_tail!r}")
         had_output = bool(text or reasoning or native_calls)
+        if watchdog_reason:
+            rc = 1
         if state == "stdout_overflow" and not had_output:
             rc = max(rc, 1)
-        transient_failure = had_error or (
-            not had_output and _is_retryable_failure(rc, err_tail, provider_status, False))
+        transient_failure = (
+            bool(watchdog_reason)
+            or had_error
+            or (
+                not had_output
+                and _is_retryable_failure(rc, err_tail, provider_status, False)
+            )
+        )
         if self.attempts is not None:
-            self.attempts.attempt_done(transient_failure, had_output and not transient_failure)
+            self.attempts.attempt_done(
+                transient_failure,
+                had_output and not transient_failure and state != "timeout",
+            )
         elif transient_failure:
             self.res.breaker.record_failure()
-        elif had_output:
+        elif had_output and state != "timeout":
             self.res.breaker.record_success()
-        return {"rc": rc, "text": text, "chunks": list(text_pieces), "native_calls": native_calls, "reasoning": reasoning, "usage": usage,
-                "err": err_tail, "provider_status": provider_status,
-                "had_output": had_output, "had_error": had_error, "fatal_error": fatal_error,
-                "state": state, "finish": "stop" if text else "error"}
+        return {
+            "rc": rc,
+            "text": text,
+            "chunks": list(text_pieces),
+            "native_calls": native_calls,
+            "reasoning": reasoning,
+            "usage": usage,
+            "err": err_tail,
+            "provider_status": provider_status,
+            "had_output": had_output,
+            "had_error": had_error,
+            "fatal_error": fatal_error,
+            "state": state,
+            "finish": "stop" if text else "error",
+            "first_event_at": first_event_at,
+            "first_token_at": first_token_at,
+        }
+
+
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
 
 
 class Handler(BaseHTTPRequestHandler):
@@ -3081,6 +5855,8 @@ class Handler(BaseHTTPRequestHandler):
         _log(f"http accept error from {client_address}")
 
     _xs: dict[str, Any] | None = None
+    _serve_stream_usage: dict[str, int] | None = None
+    _first_visible: threading.Event | None = None
 
     def _exit(self) -> dict[str, Any]:
         """Состояние выхода текущего запроса для структурной строки O-EXIT/v1."""
@@ -3090,14 +5866,20 @@ class Handler(BaseHTTPRequestHandler):
 
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
 
@@ -3120,10 +5902,457 @@ class Handler(BaseHTTPRequestHandler):
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
+        collected_reasonings: list[str] = []
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
+            collected_reasonings.append(cleaned)
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
+            if attempts.remaining_s() <= 0:
+                attempts.attempt_done(False, False)
+                xs["exit_reason"] = "timeout"
+                self._sse_error(_error_payload("opencode timeout"))
+                return True
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
+            gate.acquire(
+                deadline=attempts.deadline, is_client_gone=self._client_gone_check
+            )
+            _limiter_ok = res.spawn_limiter.acquire(
+                max_wait_s=min(SPAWN_WAIT_MAX_S, attempts.remaining_s()),
+                deadline=attempts.deadline,
+                is_client_gone=self._client_gone_check,
+            )
+            if (
+                not _limiter_ok
+                or self._client_gone_check()
+                or attempts.remaining_s() <= 0
+            ):
+                gate.release()
+                if _limiter_ok:
+                    res.spawn_limiter.refund()
+                if self._client_gone_check() or attempts.remaining_s() <= 0:
+                    attempts.attempt_done(False, False)
+                    xs["exit_reason"] = (
+                        "client_gone" if self._client_gone_check() else "timeout"
+                    )
+                    if xs["exit_reason"] == "timeout":
+                        self._sse_error(_error_payload("opencode timeout"))
+                    return True
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
+                attempts.attempt_done(False, False)
+                xs["exit_reason"] = "client_gone"
+                return True
+            if result.get("exit_reason") == "timeout":
+                attempts.attempt_done(False, False)
+                xs["exit_reason"] = "timeout"
+                self._sse_error(_error_payload("opencode timeout"))
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
+                "eof_before_step_finish",
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
+                    _has_model_output = bool(
+                        collected_texts
+                        or collected_reasonings
+                        or result.get("native_calls")
+                    )
+                    _delivered_err = _delivered_now or _has_model_output
+                    if not _has_model_output and attempts.allow_retry(
+                        "serve_transient_error"
+                    ):
+                        continue
+                    if not _delivered_err and not force_serve:
+                        xs["transport"] = "run"
+                        xs["transport_history"] = ["serve", "run"]
+                        return False
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
@@ -3274,11 +6503,21 @@ class Handler(BaseHTTPRequestHandler):
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
@@ -3296,17 +6535,33 @@ class Handler(BaseHTTPRequestHandler):
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
@@ -3324,6 +6579,44 @@ class Handler(BaseHTTPRequestHandler):
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
@@ -3335,7 +6628,10 @@ class Handler(BaseHTTPRequestHandler):
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
@@ -3350,14 +6646,18 @@ class Handler(BaseHTTPRequestHandler):
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
@@ -3372,17 +6672,80 @@ class Handler(BaseHTTPRequestHandler):
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
@@ -3391,23 +6754,57 @@ class Handler(BaseHTTPRequestHandler):
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
-                gate.acquire()
-                if not res.spawn_limiter.acquire(max_wait_s=min(SPAWN_WAIT_MAX_S, attempts.remaining_s())):
+                gate.acquire(
+                    deadline=attempts.deadline, is_client_gone=self._client_gone_check
+                )
+                if not res.spawn_limiter.acquire(
+                    max_wait_s=min(SPAWN_WAIT_MAX_S, attempts.remaining_s()),
+                    deadline=attempts.deadline,
+                    is_client_gone=self._client_gone_check,
+                ):
                     gate.release()
-                    _log("stream spawn skipped: spawn rate limiter wait exceeds the request deadline")
+                    if self._client_gone_check() or attempts.remaining_s() <= 0:
+                        attempts.attempt_done(False, False)
+                        xs["exit_reason"] = (
+                            "client_gone" if self._client_gone_check() else "timeout"
+                        )
+                        if xs["exit_reason"] == "timeout":
+                            self._sse_error(_error_payload("opencode timeout"))
+                        return
+                    _log(
+                        "stream spawn skipped: spawn rate limiter wait exceeds the request deadline"
+                    )
                     if not collected_texts and not tool_calls:
                         failure = {"rc": -1, "tail": "", "timeout": True}
                     break
+                if self._client_gone_check() or attempts.remaining_s() <= 0:
+                    res.spawn_limiter.refund()
+                    gate.release()
+                    attempts.attempt_done(False, False)
+                    xs["exit_reason"] = (
+                        "client_gone" if self._client_gone_check() else "timeout"
+                    )
+                    if xs["exit_reason"] == "timeout":
+                        self._sse_error(_error_payload("opencode timeout"))
+                    return
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
@@ -3417,37 +6814,150 @@ class Handler(BaseHTTPRequestHandler):
 
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
@@ -3459,6 +6969,36 @@ class Handler(BaseHTTPRequestHandler):
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
@@ -3471,7 +7011,10 @@ class Handler(BaseHTTPRequestHandler):
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
@@ -3480,7 +7023,12 @@ class Handler(BaseHTTPRequestHandler):
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
@@ -3490,19 +7038,29 @@ class Handler(BaseHTTPRequestHandler):
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
@@ -3512,8 +7070,10 @@ class Handler(BaseHTTPRequestHandler):
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
@@ -3522,10 +7082,17 @@ class Handler(BaseHTTPRequestHandler):
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
@@ -3574,19 +7141,48 @@ class Handler(BaseHTTPRequestHandler):
                 if stopped_on_error and rc < 0:
                     rc = 1  # остановили сами после ошибки провайдера: для классификации отказа — как выход CLI
                 tail = _clean_err(err_lines[-6:])
-                transient_failure = had_provider_error or (
-                    not attempt_output and _is_retryable_failure(rc, tail, provider_status, False))
-                attempts.attempt_done(transient_failure, attempt_output and not transient_failure)
+                has_watchdog = bool(watchdog_state.get("reason"))
+                transient_failure = (
+                    has_watchdog
+                    or had_provider_error
+                    or (
+                        not attempt_output
+                        and _is_retryable_failure(rc, tail, provider_status, False)
+                    )
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
@@ -3598,58 +7194,133 @@ class Handler(BaseHTTPRequestHandler):
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
-                    incomplete_retry = False
-                    _log(f"stream unmapped built-in tools={unmapped}: re-prompt "
-                         f"{unmapped_retries}/{NATIVE_RETRY_LIMIT}")
-                    attempt_prompt = _rewrite_tool_tags_for_model(_unavailable_tools_prompt(
-                        attempt_prompt, "".join(attempt_texts), unmapped, tools or [], model), model)
+                    incomplete_retry = True
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
+                    return
+                if failure.get("watchdog"):
+                    wd_obj: object = failure.get("watchdog")
+                    wd_reason = wd_obj if isinstance(wd_obj, str) else ""
+                    xs["exit_reason"] = wd_reason
+                    self._sse_error(_error_payload(f"opencode {wd_reason}"))
                     return
-                xs["exit_reason"] = "provider_fatal" if failure.get("partial") else "upstream_failed"
-                what = ("opencode provider error after partial output" if failure.get("partial")
-                        else "opencode run failed")
-                self._sse_error(_error_payload(
-                    f"{what} (rc={failure['rc']})"
-                    + ("" if failure.get("partial") else " without output")
-                    + (f": {failure['tail']}" if failure["tail"] else ""), failure["tail"]))
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
@@ -3657,16 +7328,27 @@ class Handler(BaseHTTPRequestHandler):
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
@@ -3677,6 +7359,13 @@ class Handler(BaseHTTPRequestHandler):
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
@@ -3697,6 +7386,385 @@ class Handler(BaseHTTPRequestHandler):
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
+            if attempts.remaining_s() <= 0:
+                attempts.attempt_done(False, False)
+                xs["exit_reason"] = "timeout"
+                self._send(502, _error_payload("opencode timeout"))
+                return True
+            if attempts.total_spawns >= MAX_TOTAL_SPAWNS or not attempts.can_spawn():
+                xs["exit_reason"] = "upstream_failed"
+                self._send(502, _error_payload("serve spawn limit reached"))
+                return True
+            reasonings: list[str] = []
+            texts: list[str] = []
+            natives: list[dict[str, object]] = []
+            _gate_j = _StartupGate()
+            _gate_j.acquire(
+                deadline=attempts.deadline, is_client_gone=self._client_gone_check
+            )
+            limiter_ok = res.spawn_limiter.acquire(
+                max_wait_s=min(SPAWN_WAIT_MAX_S, attempts.remaining_s()),
+                deadline=attempts.deadline,
+                is_client_gone=self._client_gone_check,
+            )
+            if (
+                not limiter_ok
+                or self._client_gone_check()
+                or attempts.remaining_s() <= 0
+            ):
+                _gate_j.release()
+                if limiter_ok:
+                    res.spawn_limiter.refund()
+                if self._client_gone_check() or attempts.remaining_s() <= 0:
+                    attempts.attempt_done(False, False)
+                    xs["exit_reason"] = (
+                        "client_gone" if self._client_gone_check() else "timeout"
+                    )
+                    if xs["exit_reason"] == "timeout":
+                        self._send(502, _error_payload("opencode timeout"))
+                    return True
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
+                attempts.attempt_done(False, False)
+                xs["exit_reason"] = "client_gone"
+                return True
+            if result.get("exit_reason") == "timeout":
+                attempts.attempt_done(False, False)
+                xs["exit_reason"] = "timeout"
+                self._send(502, _error_payload("opencode timeout"))
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
+                "eof_before_step_finish",
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
+                    if (
+                        not texts
+                        and not reasonings
+                        and not result.get("native_calls")
+                        and attempts.allow_retry("serve_transient_error")
+                    ):
+                        _prior_content = "\n\n".join(c for c in contents if c)
+                        continue
+                    if not _delivered_j and not force_serve:
+                        return False
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
+            repeated_prefix = bool(
+                _prior_content and content.startswith(_prior_content)
+            )
+            if _prior_content:
+                content = _dedup_retry_text(_prior_content, content)
+            if content:
+                if repeated_prefix and contents:
+                    contents[-1] += content
+                else:
+                    contents.append(content)
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
@@ -3716,30 +7784,108 @@ class Handler(BaseHTTPRequestHandler):
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
+                first_event_value = cast(object, out.get("first_event_at"))
+                first_token_value = cast(object, out.get("first_token_at"))
+                if xs.get("first_event_at") is None and isinstance(
+                    first_event_value, (int, float)
+                ):
+                    xs["first_event_at"] = float(first_event_value)
+                    xs["first_event_ms"] = int(
+                        (float(first_event_value) - cast(float, xs["t0"])) * 1000
+                    )
+                if xs.get("first_token_at") is None and isinstance(
+                    first_token_value, (int, float)
+                ):
+                    xs["first_token_at"] = float(first_token_value)
+                    xs["ttft_ms"] = int(
+                        (float(first_token_value) - cast(float, xs["t0"])) * 1000
+                    )
+
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
@@ -3752,68 +7898,148 @@ class Handler(BaseHTTPRequestHandler):
                         _log(f"dropped {dropped} unparsed tool block(s) from content")
                         if not content.strip():
                             content = ""
-                if incomplete_retry:
+                if retries:
                     # Уже отданная преамбула подавляется, переформулированный текст сохраняется целиком.
-                    content = _dedup_retry_text("\n\n".join(c for c in contents if c), content)
+                    prior_content = "\n\n".join(c for c in contents if c)
+                    repeated_prefix = bool(
+                        prior_content and content.startswith(prior_content)
+                    )
+                    content = _dedup_retry_text(prior_content, content)
+                    if repeated_prefix and contents:
+                        contents[-1] += content
+                        content = ""
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
+                watchdog_phase = cast(object, out.get("state"))
+                if (
+                    watchdog_phase
+                    in (
+                        "first_event_timeout",
+                        "first_token_timeout",
+                        "stall_timeout",
+                        "timeout",
+                    )
+                    and not tool_calls
+                ):
+                    w_state = str(watchdog_phase)
+                    tail = _clean_err(str(cast(object, out.get("err")) or ""), 500)
+                    xs["exit_reason"] = w_state
+                    self._send(
+                        502,
+                        _error_payload(
+                            f"opencode {w_state}" + (f": {tail}" if tail else ""), tail
+                        ),
+                    )
+                    return
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
@@ -3832,14 +8058,21 @@ class Handler(BaseHTTPRequestHandler):
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
@@ -3852,19 +8085,33 @@ class Handler(BaseHTTPRequestHandler):
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
@@ -3873,26 +8120,50 @@ class Handler(BaseHTTPRequestHandler):
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
 
@@ -4005,8 +8276,11 @@ def main() -> int:
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
index 0000000..1339f13
--- /dev/null
+++ b/bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py
@@ -0,0 +1,3629 @@
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
+    def test_c6_rw002_legacy_first_token_timeout_respects_configured_value_under_120s(
+        self,
+    ) -> None:
+        """RW-002: служебное событие не продлевает порог первого токена до 120 секунд."""
+        body = LEGACY_FAKE.replace(
+            'if mode == "slow":',
+            'if mode == "service":\n    ev({"type": "step_start"})\n    time.sleep(8)\nelif mode == "slow":',
+        )
+        _ = self.fake.write_text(body)
+        with (
+            mock.patch.dict(os.environ, {"FAKE_RT_MODE": "service"}),
+            mock.patch.object(server, "FIRST_EVENT_TIMEOUT_S", 20.0),
+            mock.patch.object(server, "FIRST_TOKEN_TIMEOUT_S", 0.35),
+            mock.patch.object(server, "MAX_TOTAL_SPAWNS", 1),
+            mock.patch.object(server, "TIMEOUT_S", 2.0),
+        ):
+            chunks, elapsed = self.bridge.post_stream_timed("x")
+        self.assertLess(elapsed, 1.5)
+        self.assertIn("first_token_timeout", server.LOG_PATH.read_text())
+        self.assertIn("error", json.dumps(chunks))
+
+    def test_c6_rw003_nonstream_json_run_execute_enforces_phase_watchdogs(self) -> None:
+        """RW-003: все три фазы убивают CLI и повторяются в общем бюджете."""
+        for phase in ("first_event_timeout", "first_token_timeout", "stall_timeout"):
+            with self.subTest(phase=phase):
+                counter = self.tmp / (phase + ".count")
+                event = (
+                    ""
+                    if phase == "first_event_timeout"
+                    else 'print(json.dumps({"type": "step_start"}), flush=True)'
+                )
+                if phase == "stall_timeout":
+                    event = 'print(json.dumps({"type": "reasoning", "part": {"text": "мысль"}}), flush=True)'
+                body = """#!/usr/bin/env python3
+import json,sys,time
+from pathlib import Path
+p=Path(COUNTER)
+n=int(p.read_text()) if p.exists() else 0
+p.write_text(str(n+1))
+sys.stdin.read()
+if n==0:
+    EVENT
+    time.sleep(8)
+else:
+    print(json.dumps({"type":"text","part":{"text":"Ответ"}}),flush=True)
+    print(json.dumps({"type":"step_finish","part":{"tokens":{"input":1,"output":1}}}),flush=True)
+""".replace("COUNTER", repr(str(counter))).replace(
+                    "    EVENT", "    " + event if event else "    pass"
+                )
+                server.OPENCODE_BIN = str(_write_exe(self.tmp, "watchdog-cli", body))
+                with (
+                    mock.patch.dict(
+                        os.environ, {"OPENCODE_ZEN_BRIDGE_TRANSPORT": "run"}
+                    ),
+                    mock.patch.object(
+                        server,
+                        "FIRST_EVENT_TIMEOUT_S",
+                        0.35 if phase == "first_event_timeout" else 20.0,
+                    ),
+                    mock.patch.object(server, "FIRST_TOKEN_TIMEOUT_S", 0.5),
+                    mock.patch.object(server, "STALL_TIMEOUT_S", 0.2),
+                    mock.patch.object(server, "FAIL_RETRY_BACKOFF_S", 0.0),
+                    mock.patch.object(server, "TIMEOUT_S", 3.0),
+                    mock.patch.object(server, "MAX_TOTAL_SPAWNS", 2),
+                    mock.patch.object(
+                        server,
+                        "_stop_proc",
+                        wraps=server._stop_proc,  # pyright: ignore[reportPrivateUsage] — причина: регрессия проверяет приватный API
+                    ) as stopped,
+                ):
+                    started = time.monotonic()
+                    status, result = self.bridge.post_json("x", with_tools=False)
+                self.assertLess(time.monotonic() - started, 2.5)
+                self.assertEqual(status, 200, result)
+                self.assertEqual(counter.read_text(), "2")
+                self.assertTrue(stopped.called)
+                self.assertIn(phase, server.LOG_PATH.read_text())
+                _ = counter.write_text("0")
+                self.bridge.httpd.resilience = server._Resilience()  # pyright: ignore[reportPrivateUsage] — причина: независимый бюджет для исчерпания попыток
+                with (
+                    mock.patch.dict(
+                        os.environ, {"OPENCODE_ZEN_BRIDGE_TRANSPORT": "run"}
+                    ),
+                    mock.patch.object(
+                        server,
+                        "FIRST_EVENT_TIMEOUT_S",
+                        0.35 if phase == "first_event_timeout" else 20.0,
+                    ),
+                    mock.patch.object(server, "FIRST_TOKEN_TIMEOUT_S", 0.5),
+                    mock.patch.object(server, "STALL_TIMEOUT_S", 0.2),
+                    mock.patch.object(server, "MAX_TOTAL_SPAWNS", 1),
+                    mock.patch.object(server, "TIMEOUT_S", 2.0),
+                ):
+                    status, result = self.bridge.post_json("x", with_tools=False)
+                self.assertEqual(status, 502, result)
+                self.assertEqual(counter.read_text(), "1")
+                self.assertIn("opencode " + phase, json.dumps(result))
+                self.assertNotIn(
+                    "provider error after partial output", json.dumps(result)
+                )
+
+    def test_c7_rw001_json_run_watchdog_oexit_reason_and_phase_timings(self) -> None:
+        """RW-001: исчерпание watchdog сохраняет фазу и наступившие времена O-EXIT."""
+        for phase in ("first_event_timeout", "first_token_timeout", "stall_timeout"):
+            with self.subTest(phase=phase):
+                event = ""
+                if phase == "first_token_timeout":
+                    event = 'print(json.dumps({"type":"step_start"}),flush=True)'
+                elif phase == "stall_timeout":
+                    event = 'print(json.dumps({"type":"reasoning","part":{"text":"мысль"}}),flush=True)'
+                body = (
+                    "#!/usr/bin/env python3\nimport json,sys,time\nsys.stdin.read()\n"
+                    + event
+                    + "\ntime.sleep(8)\n"
+                )
+                server.OPENCODE_BIN = str(_write_exe(self.tmp, "c7-watchdog", body))
+                logged = threading.Event()
+                log_original = cast(Callable[[str], None], getattr(server, "_log"))
+
+                def log(message: str) -> None:
+                    log_original(message)
+                    if "O-EXIT/v1" in message:
+                        logged.set()
+
+                with (
+                    mock.patch.object(server, "_log", side_effect=log),
+                    mock.patch.dict(
+                        os.environ, {"OPENCODE_ZEN_BRIDGE_TRANSPORT": "run"}
+                    ),
+                    mock.patch.object(server, "FIRST_EVENT_TIMEOUT_S", 0.35),
+                    mock.patch.object(server, "FIRST_TOKEN_TIMEOUT_S", 0.45),
+                    mock.patch.object(server, "STALL_TIMEOUT_S", 0.25),
+                    mock.patch.object(server, "MAX_TOTAL_SPAWNS", 1),
+                    mock.patch.object(server, "TIMEOUT_S", 3.0),
+                ):
+                    status, result = self.bridge.post_json("x", with_tools=False)
+                    self.assertTrue(logged.wait(1.0))
+                self.assertEqual(status, 502, result)
+                lines = [
+                    line
+                    for line in server.LOG_PATH.read_text().splitlines()
+                    if "O-EXIT/v1" in line
+                ]
+                self.assertTrue(lines)
+                self.assertIn("exit_reason=" + phase, lines[-1])
+                self.assertIn("opencode " + phase, json.dumps(result))
+                self.assertNotIn(
+                    "provider error after partial output", json.dumps(result)
+                )
+                self.assertRegex(
+                    lines[-1],
+                    r"first_event_ms="
+                    + ("None" if phase == "first_event_timeout" else r"\d+"),
+                )
+                self.assertRegex(
+                    lines[-1],
+                    r"ttft_ms=" + (r"\d+" if phase == "stall_timeout" else "None"),
+                )
+
+    def test_c7_rw003_legacy_sse_watchdog_records_breaker_failure_with_and_without_output(
+        self,
+    ) -> None:
+        """RW-003: каждая убитая watchdog попытка учитывается как отказ до OPEN."""
+        breaker = self.bridge.httpd.resilience.breaker
+        for phase in ("first_event_timeout", "first_token_timeout", "stall_timeout"):
+            with self.subTest(phase=phase):
+                event = ""
+                if phase == "first_token_timeout":
+                    event = 'print(json.dumps({"type":"step_start"}),flush=True)'
+                elif phase == "stall_timeout":
+                    event = 'print(json.dumps({"type":"reasoning","part":{"text":"мысль"}}),flush=True)'
+                server.OPENCODE_BIN = str(
+                    _write_exe(
+                        self.tmp,
+                        "c7-breaker",
+                        "#!/usr/bin/env python3\nimport json,sys,time\nsys.stdin.read()\n"
+                        + event
+                        + "\ntime.sleep(8)\n",
+                    )
+                )
+                breaker.record_success()
+                counts: list[int] = []
+                failed = threading.Event()
+                original = breaker.record_failure
+
+                def failure() -> None:
+                    original()
+                    counts.append(cast(int, getattr(breaker, "_failures")))
+                    failed.set()
+
+                with (
+                    mock.patch.dict(
+                        os.environ, {"OPENCODE_ZEN_BRIDGE_TRANSPORT": "run"}
+                    ),
+                    mock.patch.object(breaker, "_threshold", 2),
+                    mock.patch.object(breaker, "record_failure", side_effect=failure),
+                    mock.patch.object(
+                        breaker, "record_success", wraps=breaker.record_success
+                    ) as success,
+                    mock.patch.object(server, "FIRST_EVENT_TIMEOUT_S", 0.35),
+                    mock.patch.object(server, "FIRST_TOKEN_TIMEOUT_S", 0.45),
+                    mock.patch.object(server, "STALL_TIMEOUT_S", 0.25),
+                    mock.patch.object(server, "FAIL_RETRY_BACKOFF_S", 0.0),
+                    mock.patch.object(server, "MAX_TOTAL_SPAWNS", 1),
+                    mock.patch.object(server, "TIMEOUT_S", 3.0),
+                ):
+                    for expected_count in (1, 2):
+                        failed.clear()
+                        chunks, _ = self.bridge.post_stream_timed("x")
+                        self.assertTrue(failed.wait(1.0))
+                        self.assertIn("error", json.dumps(chunks))
+                        self.assertEqual(counts[-1], expected_count)
+                self.assertEqual(counts, [1, 2])
+                success.assert_not_called()
+                self.assertEqual(breaker.state, "OPEN")
+
+    def test_c6_rw003_active_subagent_does_not_trigger_token_stall(self) -> None:
+        """RW-003: ожидание действующего task не считается тишиной модели."""
+        body = r"""#!/usr/bin/env python3
+import json,sys,time
+sys.stdin.read()
+def ev(o): print(json.dumps(o),flush=True)
+ev({"type":"tool_use","part":{"id":"t1","tool":"task","state":{"status":"running","input":{}}}})
+time.sleep(0.6)
+ev({"type":"tool_use","part":{"id":"t1","tool":"task","state":{"status":"completed","input":{}}}})
+ev({"type":"text","part":{"text":"Ответ"}})
+ev({"type":"step_finish","part":{"tokens":{"input":1,"output":1}}})
+"""
+        _ = self.fake.write_text(body)
+        with (
+            mock.patch.dict(os.environ, {"OPENCODE_ZEN_BRIDGE_TRANSPORT": "run"}),
+            mock.patch.object(server, "FIRST_EVENT_TIMEOUT_S", 2.0),
+            mock.patch.object(server, "FIRST_TOKEN_TIMEOUT_S", 2.0),
+            mock.patch.object(server, "STALL_TIMEOUT_S", 0.2),
+            mock.patch.object(server, "MAX_TOTAL_SPAWNS", 1),
+        ):
+            status, result = self.bridge.post_json("x", with_tools=False)
+        self.assertEqual(status, 200, result)
+        self.assertNotIn("stall_timeout", server.LOG_PATH.read_text())
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
+    _had_dyn_cfg: bool = False
+    _had_lease: bool = False
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
+        self._had_dyn_cfg = hasattr(server, "DYNAMIC_CONFIG_PATH")
+        self.saved_cfg = getattr(
+            server, "DYNAMIC_CONFIG_PATH", self.tmp / "missing_dyn.json"
+        )
+        server.DYNAMIC_CONFIG_PATH = self.cfg
+        self._had_lease = hasattr(server, "LEASE_DIR")
+        self.saved_lease = getattr(server, "LEASE_DIR", self.tmp / "missing_leases")
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
+        if self._had_dyn_cfg:
+            server.DYNAMIC_CONFIG_PATH = self.saved_cfg
+        else:
+            delattr(server, "DYNAMIC_CONFIG_PATH")
+        if self._had_lease:
+            server.LEASE_DIR = self.saved_lease
+        else:
+            delattr(server, "LEASE_DIR")
+        self.bridge.close()
+
+    def test_c8_rw001_early_transient_error_after_execution_started_retries_serve_without_run_fallback(
+        self,
+    ) -> None:
+        """Начало execution запрещает run, но допускает повтор serve без токенов."""
+        self._auto_mode()
+        counter = self.tmp / "attempt-count"
+        fragment = """
+            counter = Path(COUNTER)
+            n = int(counter.read_text()) if counter.exists() else 0
+            counter.write_text(str(n + 1))
+            if n == 0:
+                emit({"type":"session.execution.started","data":{"sessionID":sid}})
+                emit({"type":"session.execution.failed","data":{"sessionID":sid,"error":{"message":"overloaded","status":STATUS}}})
+                return
+""".replace("COUNTER", repr(str(counter)))
+        for stream in (True, False):
+            for code in (429, 503):
+                with self.subTest(stream=stream, code=code):
+                    counter.unlink(missing_ok=True)
+                    _ = self.fake.write_text(
+                        FAKE_SERVE.replace(
+                            '            if "__native_pause__" in prompt:',
+                            fragment.replace("STATUS", str(code))
+                            + '            if "__native_pause__" in prompt:',
+                        )
+                    )
+                    with (
+                        mock.patch.object(server.Run, "execute") as legacy,
+                        mock.patch.object(server, "_spawn_with_stdin") as spawn,
+                        mock.patch.object(server, "FAIL_RETRY_BACKOFF_S", 0.0),
+                    ):
+                        if stream:
+                            chunks, _ = self.bridge.post_stream_timed("обычный запрос")
+                            self.assertFalse(
+                                any("error" in chunk for _, chunk in chunks), chunks
+                            )
+                            self.assertEqual(
+                                "".join(t for _, t in _deltas(chunks, "content")),
+                                "Ответ\n",
+                            )
+                        else:
+                            status, body = self.bridge.post_json(
+                                "обычный запрос", with_tools=False
+                            )
+                            self.assertEqual(status, 200, body)
+                            self.assertIn("Ответ", json.dumps(body, ensure_ascii=False))
+                        legacy.assert_not_called()
+                        spawn.assert_not_called()
+                    self.assertEqual(counter.read_text(), "2")
+
+    def test_c8_rw002_unpaired_surrogate_raises_serve_protocol_error_in_sse_and_json(
+        self,
+    ) -> None:
+        """Непарные суррогаты дают управляемый отказ; пара остаётся символом."""
+        mapper = server._map_serve_event  # pyright: ignore[reportPrivateUsage] — причина: проверяется приватная граница serve и управление запуском
+        protocol_error = server.ServeProtocolError
+        self._auto_mode()
+        for surrogate in ("\ud800", "\udc00"):
+            for field in ("reasoning", "text"):
+                event: dict[str, object] = {
+                    "type": f"session.{field}.delta",
+                    "data": {"sessionID": "s", "delta": surrogate},
+                }
+                with self.assertRaises(protocol_error):
+                    _ = mapper(event)
+                for stream in (True, False):
+                    with self.subTest(
+                        surrogate=repr(surrogate), field=field, stream=stream
+                    ):
+                        self.bridge.httpd.resilience = server._Resilience()  # pyright: ignore[reportPrivateUsage] — причина: независимые защиты сценария
+                        os.environ["OPENCODE_ZEN_BRIDGE_TRANSPORT"] = (
+                            "serve" if field == "reasoning" else "auto"
+                        )
+                        fragment = """
+            emit({"type":"session.execution.started","data":{"sessionID":sid}})
+            emit({"type":"session.FIELD.delta","data":{"sessionID":sid,"delta":SURROGATE}})
+            return
+""".replace("FIELD", field).replace("SURROGATE", repr(surrogate))
+                        body = FAKE_SERVE.replace(
+                            '            if "__native_pause__" in prompt:',
+                            fragment + '            if "__native_pause__" in prompt:',
+                        ).replace(
+                            "json.dumps(obj, ensure_ascii=False)",
+                            "json.dumps(obj, ensure_ascii=True)",
+                        )
+                        _ = self.fake.write_text(body)
+                        lease_cls = server._ServeLease  # pyright: ignore[reportPrivateUsage] — причина: проверяется приватная граница serve и управление запуском
+                        cleanup = lease_cls.cleanup
+                        with (
+                            mock.patch.object(server, "MAX_TOTAL_SPAWNS", 1),
+                            mock.patch.object(
+                                lease_cls, "cleanup", autospec=True, side_effect=cleanup
+                            ) as cleaned,
+                            mock.patch.object(server.Run, "execute") as legacy,
+                            mock.patch.object(server, "_spawn_with_stdin") as spawn,
+                        ):
+                            if stream:
+                                chunks, _ = self.bridge.post_stream_timed("x")
+                                self.assertTrue(
+                                    any("error" in chunk for _, chunk in chunks), chunks
+                                )
+                            else:
+                                status, reply = self.bridge.post_json(
+                                    "x", with_tools=False
+                                )
+                                self.assertEqual(status, 502, reply)
+                            cleaned.assert_called_once()
+                            legacy.assert_not_called()
+                            spawn.assert_not_called()
+                        self.assertIn(
+                            "exit_reason=invalid_serve_event",
+                            server.LOG_PATH.read_text(),
+                        )
+        mapped: object = mapper(
+            {
+                "type": "session.text.delta",
+                "data": {"sessionID": "s", "delta": "\ud83d\ude00"},
+            }
+        )
+        self.assertEqual(mapped, ("text", {"sessionID": "s", "content": "😀"}))
+        for field in ("name", "input", "text"):
+            tool_data: dict[str, object] = {
+                "sessionID": "s",
+                "id": "c",
+                field: "\ud800",
+            }
+            with self.assertRaises(protocol_error):
+                _ = mapper({"type": "session.tool.called", "data": tool_data})
+        fragment = """
+            emit({"type":"session.reasoning.delta","data":{"sessionID":sid,"delta":"\\ud83d\\ude00"}})
+            emit({"type":"session.text.delta","data":{"sessionID":sid,"delta":"\\ud83d\\ude00"}})
+            emit({"type":"session.step.ended","data":{"sessionID":sid,"tokens":{"input":1,"output":1,"reasoning":0,"cache":{"read":0}}}})
+            emit({"type":"session.execution.succeeded","data":{"sessionID":sid}})
+            return
+"""
+        _ = self.fake.write_text(
+            FAKE_SERVE.replace(
+                '            if "__native_pause__" in prompt:',
+                fragment + '            if "__native_pause__" in prompt:',
+            ).replace(
+                "json.dumps(obj, ensure_ascii=False)",
+                "json.dumps(obj, ensure_ascii=True)",
+            )
+        )
+        for stream in (True, False):
+            if stream:
+                chunks, _ = self.bridge.post_stream_timed("x")
+                self.assertEqual(
+                    "".join(t for _, t in _deltas(chunks, "content")), "😀"
+                )
+                self.assertIn(
+                    "😀", "".join(t for _, t in _deltas(chunks, "reasoning_content"))
+                )
+            else:
+                status, reply = self.bridge.post_json("x", with_tools=False)
+                self.assertEqual(status, 200, reply)
+                self.assertIn("😀", json.dumps(reply, ensure_ascii=False))
+        for stream in (True, False):
+            self.bridge.httpd.resilience = server._Resilience()  # pyright: ignore[reportPrivateUsage] — причина: проверяется приватная граница serve и управление запуском
+            calls, patcher = self._patched_attempts(
+                [
+                    lambda _args: _fake_result(
+                        exit_reason="invalid_serve_event", delivered=False
+                    )
+                ]
+            )
+            _ = self.fake.write_text(FAKE_SERVE)
+            with (
+                patcher,
+                mock.patch.object(
+                    server.Run,
+                    "execute",
+                    return_value={
+                        "text": "резерв",
+                        "reasoning": "",
+                        "usage": {},
+                        "state": "ok",
+                        "rc": 0,
+                    },
+                ) as legacy,
+                mock.patch.object(server, "MAX_TOTAL_SPAWNS", 2),
+            ):
+                if stream:
+                    chunks, _ = self.bridge.post_stream_timed("x")
+                    self.assertIn(
+                        "Поздний ответ", json.dumps(chunks, ensure_ascii=False)
+                    )
+                else:
+                    status, _ = self.bridge.post_json("x", with_tools=False)
+                    self.assertEqual(status, 200)
+                    legacy.assert_called_once()
+            self.assertEqual(len(calls), 1)
+
+    def test_c8_rw002_pre_delivery_surrogate_falls_back_to_run(self) -> None:
+        """Битое событие до execution и заголовков prompt допускает резервный run."""
+        self._auto_mode()
+        for stream, field, surrogate in (
+            (True, "reasoning", "\ud800"),
+            (False, "text", "\udc00"),
+        ):
+            self.bridge.httpd.resilience = server._Resilience()  # pyright: ignore[reportPrivateUsage] — причина: независимые защиты сценария
+            fragment = """
+            emit({"type":"session.FIELD.delta","data":{"sessionID":sid,"delta":SURROGATE}})
+            return
+""".replace("FIELD", field).replace("SURROGATE", repr(surrogate))
+            fake = (
+                FAKE_SERVE.replace(
+                    '            if "__native_pause__" in prompt:',
+                    fragment + '            if "__native_pause__" in prompt:',
+                )
+                .replace(
+                    "json.dumps(obj, ensure_ascii=False)",
+                    "json.dumps(obj, ensure_ascii=True)",
+                )
+                .replace(
+                    '            state["prompt"] = prompt_text\n',
+                    '            state["prompt"] = prompt_text\n            time.sleep(5)\n',
+                )
+            )
+            _ = self.fake.write_text(fake)
+            with (
+                mock.patch.object(server, "MAX_TOTAL_SPAWNS", 2),
+                mock.patch.object(
+                    server,
+                    "_serve_one_attempt",
+                    wraps=server._serve_one_attempt,  # pyright: ignore[reportPrivateUsage] — причина: проверяется реальная попытка serve до барьера
+                ) as attempt,
+            ):
+                if stream:
+                    chunks, _ = self.bridge.post_stream_timed("x")
+                    output = json.dumps(chunks, ensure_ascii=False)
+                else:
+                    status, reply = self.bridge.post_json("x", with_tools=False)
+                    self.assertEqual(status, 200, reply)
+                    output = json.dumps(reply, ensure_ascii=False)
+                self.assertIn("Поздний ответ", output)
+                attempt.assert_called_once()
+            self.assertIn("transport=run", server.LOG_PATH.read_text())
+
+    def test_c8_rw003_request_deadline_timeout_is_neutral_for_circuit_breaker(
+        self,
+    ) -> None:
+        """Локальный дедлайн нейтрален, фазовые watchdog учитываются breaker."""
+        self._auto_mode()
+        for stream in (True, False):
+            for reason in (
+                "startup",
+                "timeout",
+                "first_token_timeout",
+                "stall_timeout",
+            ):
+                self.bridge.httpd.resilience = server._Resilience()  # pyright: ignore[reportPrivateUsage] — причина: проверяется приватная граница serve и управление запуском
+                breaker = self.bridge.httpd.resilience.breaker
+                for _ in range(2):
+                    calls, patcher = self._patched_attempts(
+                        [lambda _args: _fake_result(exit_reason=reason, delivered=True)]
+                    )
+                    if reason == "startup":
+                        patcher = mock.patch.object(
+                            server,
+                            "_spawn_serve",
+                            side_effect=server.ServeStartupDeadlineExceeded("deadline"),
+                        )
+                    with (
+                        patcher,
+                        mock.patch.object(server, "MAX_TOTAL_SPAWNS", 1),
+                        mock.patch.object(server.Run, "execute") as legacy,
+                        mock.patch.object(server, "_spawn_with_stdin") as spawn,
+                    ):
+                        if stream:
+                            chunks, _ = self.bridge.post_stream_timed("x")
+                            self.assertTrue(
+                                any("error" in chunk for _, chunk in chunks), chunks
+                            )
+                        else:
+                            status, reply = self.bridge.post_json("x", with_tools=False)
+                            self.assertIn(status, (502, 504), reply)
+                        legacy.assert_not_called()
+                        spawn.assert_not_called()
+                    if reason != "startup":
+                        self.assertEqual(len(calls), 1)
+                self.assertEqual(
+                    breaker._failures,  # pyright: ignore[reportPrivateUsage] — причина: проверяется точное число отказов breaker
+                    0 if reason in ("startup", "timeout") else 2,
+                )
+                self.assertEqual(breaker.state, "CLOSED")
+
+    def test_c8_fu001_multiple_native_tool_calls_same_step_preserved_next_step_excluded(
+        self,
+    ) -> None:
+        """Все вызовы закрываемого шага сохранены один раз, следующий шаг исключён."""
+        fragment = """
+            emit({"type":"session.execution.started","data":{"sessionID":sid}})
+            for cid, mid, command in [("c1","m1","pwd"),("c2","m1","ls"),("c2","m1","ls"),("foreign","m2","wrong")]:
+                if cid == "c2": time.sleep(0.22)
+                emit({"type":"session.tool.called","data":{"sessionID":sid,"assistantMessageID":mid,"id":cid,"name":"bash","input":{"command":command}}})
+            emit({"type":"session.step.ended","data":{"sessionID":sid,"assistantMessageID":"m1","tokens":{"input":123,"output":45,"reasoning":6,"cache":{"read":10}}}})
+            emit({"type":"session.tool.called","data":{"sessionID":sid,"assistantMessageID":"m2","id":"c3","name":"bash","input":{"command":"wrong"}}})
+            return
+"""
+        _ = self.fake.write_text(
+            FAKE_SERVE.replace(
+                '            if "__native_pause__" in prompt:',
+                fragment + '            if "__native_pause__" in prompt:',
+            )
+        )
+        for stream in (True, False):
+            with self.subTest(stream=stream):
+                if stream:
+                    chunks, _ = self.bridge.post_stream_timed("x")
+                    self.assertEqual(_tool_names(chunks), ["bash", "bash"])
+                    output = json.dumps(chunks, ensure_ascii=False)
+                    usages = [
+                        _as_obj_dict(c["usage"]) for _, c in chunks if "usage" in c
+                    ]
+                    usage = usages[-1]
+                else:
+                    status, reply = self.bridge.post_json("x")
+                    self.assertEqual(status, 200, reply)
+                    output = json.dumps(reply, ensure_ascii=False)
+                    choices = cast(list[object], reply["choices"])
+                    message = _as_obj_dict(_as_obj_dict(choices[0])["message"])
+                    self.assertEqual(len(cast(list[object], message["tool_calls"])), 2)
+                    usage = _as_obj_dict(reply["usage"])
+                self.assertIn("pwd", output)
+                self.assertIn("ls", output)
+                self.assertNotIn("wrong", output)
+                self.assertEqual(usage["prompt_tokens"], 123)
+                self.assertEqual(usage["completion_tokens"], 45)
+                self.assertEqual(
+                    _as_obj_dict(usage["prompt_tokens_details"])["cached_tokens"], 10
+                )
+                self.assertEqual(
+                    _as_obj_dict(usage["completion_tokens_details"])[
+                        "reasoning_tokens"
+                    ],
+                    6,
+                )
+
+    def test_c9_rw001_idless_and_unconfirmed_native_step(self) -> None:
+        """Без ID сохраняются оба вызова; EOF и окно без step.ended дают ошибку."""
+        for scenario in ("idless", "inherited", "eof", "window"):
+            fragment = """
+            emit({"type":"session.reasoning.delta","data":{"sessionID":sid,"assistantMessageID":"m1","delta":"Думаю"}})
+            emit({"type":"session.tool.called","data":{"sessionID":sid,"id":"c1","name":"bash","input":{"command":"pwd"}}})
+            time.sleep(0.22)
+            if SCENARIO in ("idless", "inherited"):
+                emit({"type":"session.tool.input.started","data":{"sessionID":sid,"id":"c2","name":"bash"}})
+                emit({"type":"session.tool.input.ended","data":{"sessionID":sid,"id":"c2","text":'{"command":"ls"}'}})
+                if SCENARIO == "idless":
+                    emit({"type":"session.tool.called","data":{"sessionID":sid,"id":"c2","name":"bash","input":{"command":"ls"}}})
+                emit({"type":"session.step.ended","data":{"sessionID":sid,"tokens":{"input":123,"output":45,"reasoning":6,"cache":{"read":10}}}})
+                emit({"type":"session.tool.called","data":{"sessionID":sid,"assistantMessageID":"m2","id":"c3","name":"bash","input":{"command":"wrong"}}})
+            if SCENARIO == "window": time.sleep(2)
+            return
+""".replace("SCENARIO", repr(scenario))
+            if scenario == "idless":
+                fragment = fragment.replace(',"assistantMessageID":"m1"', "")
+            _ = self.fake.write_text(
+                FAKE_SERVE.replace(
+                    '            if "__native_pause__" in prompt:',
+                    fragment + '            if "__native_pause__" in prompt:',
+                )
+            )
+            for stream in (True, False):
+                with self.subTest(scenario=scenario, stream=stream):
+                    self.bridge.httpd.resilience = server._Resilience()  # pyright: ignore[reportPrivateUsage] — причина: независимый breaker для каждого сценария
+                    with mock.patch.object(server, "MAX_TOTAL_SPAWNS", 1):
+                        if stream:
+                            chunks, _ = self.bridge.post_stream_timed("x")
+                            output = json.dumps(chunks, ensure_ascii=False)
+                            if scenario in ("eof", "window"):
+                                self.assertTrue(
+                                    any("error" in c for _, c in chunks), chunks
+                                )
+                                self.assertNotIn(
+                                    '"finish_reason": "tool_calls"', output
+                                )
+                                self.assertIn(
+                                    "exit_reason=invalid_serve_event",
+                                    server.LOG_PATH.read_text(),
+                                )
+                                continue
+                            self.assertEqual(_tool_names(chunks), ["bash", "bash"])
+                            usage = [
+                                _as_obj_dict(c["usage"])
+                                for _, c in chunks
+                                if "usage" in c
+                            ][-1]
+                        else:
+                            status, reply = self.bridge.post_json("x")
+                            if scenario in ("eof", "window"):
+                                self.assertEqual(status, 502, reply)
+                                self.assertIn(
+                                    "exit_reason=invalid_serve_event",
+                                    server.LOG_PATH.read_text(),
+                                )
+                                continue
+                            self.assertEqual(status, 200, reply)
+                            output = json.dumps(reply, ensure_ascii=False)
+                            choices = cast(list[object], reply["choices"])
+                            message = _as_obj_dict(_as_obj_dict(choices[0])["message"])
+                            self.assertEqual(
+                                len(cast(list[object], message["tool_calls"])), 2
+                            )
+                            usage = _as_obj_dict(reply["usage"])
+                        self.assertIn("pwd", output)
+                        self.assertIn("ls", output)
+                        self.assertNotIn("wrong", output)
+                        self.assertEqual(usage["prompt_tokens"], 123)
+                        self.assertEqual(usage["completion_tokens"], 45)
+                        self.assertEqual(
+                            _as_obj_dict(usage["prompt_tokens_details"])[
+                                "cached_tokens"
+                            ],
+                            10,
+                        )
+                        self.assertEqual(
+                            _as_obj_dict(usage["completion_tokens_details"])[
+                                "reasoning_tokens"
+                            ],
+                            6,
+                        )
+
+    def test_c8_fu002_legacy_spawn_rechecks_cancel_and_deadline_after_reservation(
+        self,
+    ) -> None:
+        """После резерва токена отмена и дедлайн запрещают legacy spawn и возвращают резерв."""
+        for stream in (True, False):
+            for cancel in (True, False):
+                log_before = (
+                    server.LOG_PATH.read_text() if server.LOG_PATH.exists() else ""
+                )
+                exit_logged = threading.Event()
+                original_log = server._log  # pyright: ignore[reportPrivateUsage] — причина: синхронизация с реальной записью O-EXIT
+
+                def observe_log(message: str) -> None:
+                    original_log(message)
+                    if "O-EXIT/v1" in message:
+                        exit_logged.set()
+
+                gone = [False]
+                limiter = self.bridge.httpd.resilience.spawn_limiter
+
+                def reserve(*_args: object, **_kw: object) -> bool:
+                    if cancel:
+                        gone[0] = True
+                    else:
+                        time.sleep(0.08)
+                    return True
+
+                with (
+                    mock.patch.object(server, "_log", side_effect=observe_log),
+                    mock.patch.dict(
+                        os.environ, {"OPENCODE_ZEN_BRIDGE_TRANSPORT": "run"}
+                    ),
+                    mock.patch.object(server, "TIMEOUT_S", 0.05),
+                    mock.patch.object(
+                        server.Handler,
+                        "_client_gone_check",
+                        side_effect=lambda: gone[0],
+                    ),
+                    mock.patch.object(limiter, "acquire", side_effect=reserve),
+                    mock.patch.object(
+                        limiter, "refund", wraps=limiter.refund
+                    ) as refund,
+                    mock.patch.object(server, "_spawn_with_stdin") as spawn,
+                ):
+                    if stream:
+                        _ = self.bridge.post_stream_timed("x")
+                    else:
+                        status, _ = self.bridge.post_json("x", with_tools=False)
+                        self.assertIn(status, (502, 504))
+                    self.assertTrue(exit_logged.wait(3.0), "O-EXIT не записан")
+                    spawn.assert_not_called()
+                    refund.assert_called_once()
+                new_lines = server.LOG_PATH.read_text()[len(log_before) :].splitlines()
+                exits = [line for line in new_lines if "O-EXIT/v1" in line]
+                self.assertEqual(len(exits), 1, exits)
+                self.assertIn(
+                    "exit_reason=" + ("client_gone" if cancel else "timeout"), exits[0]
+                )
+                self.assertIn("total_spawns=0", exits[0])
+                self.assertEqual(self.bridge.httpd.resilience.breaker._failures, 0)  # pyright: ignore[reportPrivateUsage] — причина: проверяется нейтральный timeout
+                self.assertEqual(self.bridge.httpd.resilience.slots.in_use, 0)
+                self.assertFalse(server._STARTUP_LOCK.locked())  # pyright: ignore[reportPrivateUsage] — причина: проверяется приватная граница serve и управление запуском
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
+    def test_c7_rw002_execution_started_before_prompt_headers_sets_delivered_and_blocks_run_fallback(
+        self,
+    ) -> None:
+        """RW-002: начало execution закрывает fallback даже без заголовков prompt."""
+        self._auto_mode()
+        for stream in (True, False):
+            for ending in ("eof", "error"):
+                with self.subTest(stream=stream, ending=ending):
+                    fragment = """
+            emit({"type":"session.execution.started","data":{"sessionID":sid}})
+            if ENDING=="error":
+                emit({"type":"session.execution.failed","data":{"sessionID":sid,"error":{"message":"overloaded","status":503}}})
+            return
+""".replace("ENDING", repr(ending))
+                    body = FAKE_SERVE.replace(
+                        '            if "__native_pause__" in prompt:',
+                        fragment + '            if "__native_pause__" in prompt:',
+                    )
+                    body = body.replace(
+                        '            state["prompt"] = prompt_text\n',
+                        '            state["prompt"] = prompt_text\n            time.sleep(5)\n',
+                    )
+                    _ = self.fake.write_text(body)
+                    results: list[Mapping[str, object]] = []
+                    original = cast(
+                        Callable[..., Mapping[str, object]],
+                        getattr(server, "_serve_one_attempt"),
+                    )
+
+                    def attempt(
+                        *args: object, **kwargs: object
+                    ) -> Mapping[str, object]:
+                        result = original(*args, **kwargs)
+                        results.append(result)
+                        return result
+
+                    health = self.bridge.httpd.resilience.serve_health
+                    health.record_success()
+                    with (
+                        mock.patch.object(
+                            server, "_serve_one_attempt", side_effect=attempt
+                        ),
+                        mock.patch.object(
+                            server,
+                            "_spawn_with_stdin",
+                            wraps=getattr(server, "_spawn_with_stdin"),
+                        ) as spawn,
+                        mock.patch.object(
+                            server.Run,
+                            "execute",
+                            side_effect=AssertionError("unexpected run fallback"),
+                        ) as run,
+                        mock.patch.object(
+                            health, "record_success", wraps=health.record_success
+                        ) as success,
+                        mock.patch.object(server, "FAIL_RETRY_BACKOFF_S", 0.0),
+                        mock.patch.object(server, "MAX_TOTAL_SPAWNS", 2),
+                    ):
+                        if stream:
+                            chunks, _ = self.bridge.post_stream_timed("x")
+                            self.assertIn("error", json.dumps(chunks))
+                        else:
+                            status, response = self.bridge.post_json("x")
+                            self.assertEqual(status, 502, response)
+                    self.assertGreaterEqual(len(results), 1)
+                    self.assertLessEqual(len(results), 2)
+                    self.assertTrue(
+                        all(r["first_event_at"] is not None for r in results)
+                    )
+                    self.assertTrue(
+                        all(r["delivered"] is True for r in results), results
+                    )
+                    spawn.assert_not_called()
+                    run.assert_not_called()
+                    success.assert_not_called()
+                    self.bridge.httpd.resilience.breaker.record_success()
+
+    def test_c7_fu001_native_tool_call_captures_step_ended_usage(self) -> None:
+        """FU-001: usage закрытого native-шага попадает в финальный чанк вместе с tool_calls."""
+        fragment = """
+            emit({"type":"session.execution.started","data":{"sessionID":sid}})
+            emit({"type":"session.tool.called","data":{"sessionID":sid,"assistantMessageID":"m1","id":"nc1","name":"bash","input":{"command":"pwd"}}})
+            emit({"type":"session.text.delta","data":{"sessionID":sid,"assistantMessageID":"m2","delta":"ЛИШНИЙ ШАГ"}})
+            emit({"type":"session.tool.called","data":{"sessionID":sid,"assistantMessageID":"m2","id":"nc2","name":"bash","input":{"command":"wrong"}}})
+            emit({"type":"session.step.ended","data":{"sessionID":"foreign","assistantMessageID":"m1","tokens":{"input":999}}})
+            emit({"type":"session.step.ended","data":{"sessionID":sid,"assistantMessageID":"m1","tokens":{"input":123,"output":45,"reasoning":67,"cache":{"read":10,"write":0}}}})
+            return
+"""
+        _ = self.fake.write_text(
+            FAKE_SERVE.replace(
+                '            if "__native_pause__" in prompt:',
+                fragment + '            if "__native_pause__" in prompt:',
+            )
+        )
+        chunks, _ = self.bridge.post_stream_timed("x")
+        self.assertEqual(_tool_names(chunks), ["bash"])
+        self.assertNotIn(
+            "ЛИШНИЙ ШАГ", "".join(t for _, t in _deltas(chunks, "content"))
+        )
+        usages = [_as_obj_dict(c["usage"]) for _, c in chunks if "usage" in c]
+        self.assertTrue(usages, chunks)
+        self.assertEqual(usages[-1]["prompt_tokens"], 123)
+        self.assertEqual(usages[-1]["completion_tokens"], 45)
+        self.assertEqual(
+            _as_obj_dict(usages[-1]["prompt_tokens_details"])["cached_tokens"], 10
+        )
+        self.assertEqual(
+            _as_obj_dict(usages[-1]["completion_tokens_details"])["reasoning_tokens"],
+            67,
+        )
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
+    def test_c6_rw001_headers_at_blocks_run_fallback_on_sse_error_and_timeout(
+        self,
+    ) -> None:
+        """RW-001: заголовки prompt удерживают обе формы ответа на serve до ошибки."""
+        self._auto_mode()
+        fake = FAKE_SERVE.replace(
+            'if "__native_pause__" in prompt:',
+            'if "__c6_fail__" in prompt:\n                time.sleep(0.08)\n                emit({"type":"session.execution.failed","data":{"sessionID":sid,"error":{"status":429,"message":"rate limit"}}}); return\n            if "__native_pause__" in prompt:',
+        )
+        _ = self.fake.write_text(fake)
+        original = server._serve_one_attempt  # pyright: ignore[reportPrivateUsage] — причина: регрессия проверяет приватную границу транспорта
+        for marker in ("__c6_fail__", "__never_event__"):
+            for stream in (True, False):
+                with self.subTest(marker=marker, stream=stream):
+                    self.bridge.httpd.resilience = server._Resilience()  # pyright: ignore[reportPrivateUsage] — причина: регрессия проверяет приватную границу транспорта
+                    results: list[dict[str, object]] = []
+
+                    def capture(*args: object, **kwargs: object) -> object:
+                        result = cast(
+                            dict[str, object],
+                            cast(Callable[..., object], original)(*args, **kwargs),
+                        )
+                        results.append(result)
+                        return result
+
+                    with (
+                        mock.patch.object(
+                            server, "_serve_one_attempt", side_effect=capture
+                        ),
+                        mock.patch.object(server.Run, "execute") as run,
+                        mock.patch.object(server, "_spawn_with_stdin") as spawn,
+                        mock.patch.object(
+                            self.bridge.httpd.resilience.serve_health, "record_success"
+                        ) as success,
+                        mock.patch.object(server, "MAX_TOTAL_SPAWNS", 1),
+                        mock.patch.object(server, "TIMEOUT_S", 0.9),
+                        mock.patch.object(server, "FIRST_EVENT_TIMEOUT_S", 20.0),
+                    ):
+                        if stream:
+                            chunks, _ = self.bridge.post_stream_timed(marker)
+                            self.assertIn("error", json.dumps(chunks))
+                        else:
+                            status, body = self.bridge.post_json(
+                                marker, with_tools=False
+                            )
+                            self.assertEqual(status, 502, body)
+                        run.assert_not_called()
+                        spawn.assert_not_called()
+                        success.assert_not_called()
+                    self.assertEqual(len(results), 1)
+                    self.assertIs(results[0]["delivered"], True)
+
+    def test_c6_rw005_startup_abort_never_falls_back_or_changes_serve_health(
+        self,
+    ) -> None:
+        """RW-005: исключения отмены старта не расходуют здоровье serve и не запускают run."""
+        self._auto_mode()
+        for error in (
+            server.ServeClientDisconnect,
+            server.ServeStartupDeadlineExceeded,
+        ):
+            for stream in (True, False):
+                self.bridge.httpd.resilience = server._Resilience()  # pyright: ignore[reportPrivateUsage] — причина: каждый сценарий имеет свой бюджет
+                with (
+                    self.subTest(error=error.__name__, stream=stream),
+                    mock.patch.object(
+                        server, "_spawn_serve", side_effect=error("stop")
+                    ),
+                    mock.patch.object(server, "_spawn_with_stdin") as spawn,
+                    mock.patch.object(server.Run, "execute") as run,
+                    mock.patch.object(
+                        self.bridge.httpd.resilience.serve_health, "record_failure"
+                    ) as failure,
+                    mock.patch.object(
+                        self.bridge.httpd.resilience.serve_health, "record_success"
+                    ) as success,
+                    mock.patch.object(server, "MAX_TOTAL_SPAWNS", 1),
+                ):
+                    try:
+                        if stream:
+                            chunks, _ = self.bridge.post_stream_timed("x", timeout=2.0)
+                            if error is server.ServeStartupDeadlineExceeded:
+                                self.assertIn("error", json.dumps(chunks))
+                        else:
+                            status, body = self.bridge.post_json("x", timeout=2.0)
+                            self.assertEqual(status, 502, body)
+                    except (http.client.RemoteDisconnected, TimeoutError):
+                        self.assertIs(error, server.ServeClientDisconnect)
+                    run.assert_not_called()
+                    spawn.assert_not_called()
+                    failure.assert_not_called()
+                    success.assert_not_called()
+
+    def _c6_scenario(self, scenario: str, counter: Path) -> None:
+        """Один сценарий с общим счётчиком попыток для настоящих serve и run."""
+        fragment = r"""
+            counter=Path(COUNTER)
+            n=int(counter.read_text()) if counter.exists() else 0
+            counter.write_text(str(n+1))
+            scenario=SCENARIO
+            if n==0 or scenario=="budget":
+                if scenario=="unmapped":
+                    emit({"type":"session.text.delta","data":{"sessionID":sid,"delta":"Проверяю файлы."}})
+                if scenario in ("text","broken","budget","transient"):
+                    text=("Проверяю файлы..." if scenario=="text" else "Проверяю файлы.") + ('<tool_call>{"name":"bash","arguments":' if scenario in ("broken","budget") else "")
+                    emit({"type":"session.text.delta","data":{"sessionID":sid,"delta":text}})
+                elif scenario=="reasoning":
+                    emit({"type":"session.reasoning.delta","data":{"sessionID":sid,"delta":"I need to call bash next."}})
+                elif scenario=="native":
+                    emit({"type":"session.tool.called","data":{"sessionID":sid,"id":"nc1","name":"bash","input":{"command":"pwd"}}})
+                elif scenario=="unmapped":
+                    emit({"type":"session.tool.called","data":{"sessionID":sid,"id":"nc1","name":"todoread","input":{}}})
+                if scenario in ("native","unmapped"):
+                    emit({"type":"session.step.ended","data":{"sessionID":sid,"tokens":{"input":1,"output":1,"reasoning":0,"cache":{"read":0}}}})
+                if scenario=="native": time.sleep(2); return
+                if scenario=="transient":
+                    emit({"type":"session.execution.failed","data":{"sessionID":sid,"error":{"message":"overloaded","status":503}}}); return
+            else:
+                emit({"type":"session.text.delta","data":{"sessionID":sid,"delta":("Проверяю файлы... Ответ" if scenario=="text" else "Проверяю файлы. Ответ")}})
+                emit({"type":"session.step.ended","data":{"sessionID":sid,"tokens":{"input":1,"output":1,"reasoning":0,"cache":{"read":0}}}})
+            emit({"type":"session.execution.succeeded","data":{"sessionID":sid}}); return
+""".replace("COUNTER", repr(str(counter))).replace("SCENARIO", repr(scenario))
+        body = FAKE_SERVE.replace(
+            '            if "__native_pause__" in prompt:',
+            fragment + '            if "__native_pause__" in prompt:',
+        )
+        _ = self.fake.write_text(body)
+
+    def test_c6_rw004_ac016_serve_step_interruption_matrix(self) -> None:
+        """AC-016: пять ветвей прерывания на настоящем serve для SSE и JSON."""
+        for scenario in ("text", "reasoning", "broken", "native", "budget"):
+            for stream in (True, False):
+                with self.subTest(scenario=scenario, stream=stream):
+                    counter = self.tmp / (scenario + str(stream))
+                    self._c6_scenario(scenario, counter)
+                    self.bridge.httpd.resilience = server._Resilience()  # pyright: ignore[reportPrivateUsage] — причина: регрессия проверяет приватную границу транспорта
+                    with (
+                        mock.patch.object(server, "FAIL_RETRY_BACKOFF_S", 0.0),
+                        mock.patch.object(server, "MAX_TOTAL_SPAWNS", 2),
+                    ):
+                        text, finish = self._c6_response(stream)
+                    self.assertEqual(
+                        counter.read_text(), "1" if scenario == "native" else "2"
+                    )
+                    self.assertLessEqual(int(counter.read_text()), 2)
+                    self.assertNotIn("<tool_call>", text)
+                    self.assertLessEqual(text.count("Проверяю файлы."), 1, text)
+                    if scenario == "native":
+                        self.assertEqual(finish, "tool_calls")
+                    elif scenario != "budget":
+                        self.assertEqual(finish, "stop")
+                        self.assertIn("Ответ", text)
+
+    def _c6_response(self, stream: bool) -> tuple[str, str]:
+        """Вернуть собранный текст и finish_reason обеих форм ответа."""
+        if stream:
+            chunks, _ = self.bridge.post_stream_timed("проверь файлы")
+            text = "".join(t for _, t in _deltas(chunks, "content"))
+            finish = ""
+            for _, chunk in chunks:
+                choices = cast(list[object], chunk.get("choices") or [])
+                if choices:
+                    value = _as_obj_dict(choices[0]).get("finish_reason")
+                    if isinstance(value, str):
+                        finish = value
+            return text, finish
+        status, body = self.bridge.post_json("проверь файлы")
+        self.assertEqual(status, 200, body)
+        choice = _as_obj_dict(cast(list[object], body["choices"])[0])
+        return str(_as_obj_dict(choice.get("message")).get("content") or ""), str(
+            choice.get("finish_reason")
+        )
+
+    def test_c6_rw004_ac017_unmapped_recovery_serve_vs_run_equivalence(self) -> None:
+        """AC-017: unmapped и transient повтор дают равный итог через serve/run, SSE/JSON."""
+        for scenario in ("unmapped", "transient"):
+            outputs: list[tuple[str, str]] = []
+            for transport in ("serve", "run"):
+                for stream in (True, False):
+                    with self.subTest(
+                        scenario=scenario, transport=transport, stream=stream
+                    ):
+                        counter = self.tmp / (scenario + transport + str(stream))
+                        self.bridge.httpd.resilience = server._Resilience()  # pyright: ignore[reportPrivateUsage] — причина: регрессия проверяет приватную границу транспорта
+                        self._c6_scenario(scenario, counter)
+                        if transport == "run":
+                            body = r"""#!/usr/bin/env python3
+import json,sys
+from pathlib import Path
+p=Path(COUNTER)
+n=int(p.read_text()) if p.exists() else 0
+p.write_text(str(n+1)); sys.stdin.read()
+def ev(o): print(json.dumps(o),flush=True)
+if n==0:
+    if SCENARIO=="unmapped":
+        ev({"type":"text","part":{"text":"Проверяю файлы."}})
+        ev({"type":"tool_use","part":{"tool":"todoread","state":{"status":"completed","input":{}}}})
+    else:
+        ev({"type":"text","part":{"text":"Проверяю файлы."}})
+        ev({"type":"error","error":{"name":"APIError","data":{"statusCode":503,"message":"overloaded"}}})
+else: ev({"type":"text","part":{"text":"Проверяю файлы. Ответ"}})
+ev({"type":"step_finish","part":{"tokens":{"input":1,"output":1}}})
+""".replace("COUNTER", repr(str(counter))).replace("SCENARIO", repr(scenario))
+                            _ = self.fake.write_text(body)
+                        with (
+                            mock.patch.dict(
+                                os.environ, {"OPENCODE_ZEN_BRIDGE_TRANSPORT": transport}
+                            ),
+                            mock.patch.object(server, "FAIL_RETRY_BACKOFF_S", 0.0),
+                            mock.patch.object(server, "MAX_TOTAL_SPAWNS", 2),
+                        ):
+                            output = self._c6_response(stream)
+                        outputs.append(output)
+                        self.assertEqual(counter.read_text(), "2")
+                        self.assertEqual(output, ("Проверяю файлы. Ответ", "stop"))
+            self.assertEqual(len(set(outputs)), 1)
+
+
+class TestReworkUnits(unittest.TestCase):
+    """Группа C: детерминированные оракулы RW-001..RW-032 без живого FakeServe."""
+
+    def test_c8_fu002_pre_spawn_gate_and_limiter_respect_deadline_and_client_disconnect(
+        self,
+    ) -> None:
+        """Ожидание gate и лимитера ограничено дедлайном и отменой клиента."""
+        lock = server._STARTUP_LOCK  # pyright: ignore[reportPrivateUsage] — причина: проверяется приватная граница serve и управление запуском
+        gate_cls = server._StartupGate  # pyright: ignore[reportPrivateUsage] — причина: проверяется приватная граница serve и управление запуском
+        limiter_cls = server._SpawnRateLimiter  # pyright: ignore[reportPrivateUsage] — причина: проверяется приватная граница serve и управление запуском
+        self.assertTrue(lock.acquire(timeout=0.1))
+        try:
+            for cancel in (False, True):
+                started = time.monotonic()
+                gate = gate_cls(wait_s=1.0)
+                gate.acquire(deadline=started + 0.06, is_client_gone=lambda: cancel)
+                gate.release()
+                self.assertLess(time.monotonic() - started, 0.2)
+                self.assertTrue(lock.locked())
+        finally:
+            lock.release()
+        for cancel in (False, True):
+            now = [0.0]
+            sleeps: list[float] = []
+
+            def advance(seconds: float) -> None:
+                sleeps.append(seconds)
+                now[0] += seconds
+
+            limiter = limiter_cls(
+                rate_rps=1.0, burst=1.0, clock_fn=lambda: now[0], sleep_fn=advance
+            )
+            self.assertTrue(limiter.acquire())
+            self.assertFalse(
+                limiter.acquire(
+                    max_wait_s=2.0,
+                    deadline=0.08 if not cancel else 2.0,
+                    is_client_gone=lambda: cancel and now[0] >= 0.05,
+                )
+            )
+            self.assertLessEqual(now[0], 0.08)
+            self.assertTrue(all(s <= 0.05 for s in sleeps))
+            now[0] = 1.1
+            self.assertTrue(limiter.acquire(max_wait_s=0.0))
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
+    def test_c9_fu001_serve_queue_and_accumulated_byte_budget_enforced(self) -> None:
+        """Каждый байтовый бюджет останавливает реальную попытку и убирает lease."""
+        for budget in ("_MAX_SERVE_QUEUE_BYTES", "_MAX_SERVE_ACCUMULATED_BYTES"):
+            with self.subTest(budget=budget):
+                lease_cls = server._ServeLease  # pyright: ignore[reportPrivateUsage] — причина: проверяется обязательная уборка попытки
+                cleanup = lease_cls.cleanup
+                with (
+                    mock.patch.object(
+                        server,
+                        budget,
+                        8 if budget == "_MAX_SERVE_QUEUE_BYTES" else 16,
+                        create=True,
+                    ),
+                    mock.patch.object(
+                        lease_cls, "cleanup", autospec=True, side_effect=cleanup
+                    ) as cleaned,
+                ):
+                    result = self.attempt("x")
+                self.assertEqual(result["exit_reason"], "invalid_serve_event", result)
+                self.assertNotEqual(result["terminal"], "succeeded", result)
+                cleaned.assert_called_once()
+                self.assertFalse(list(server.LEASE_DIR.glob("lease-*.json")))
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
+    def test_c6_fu001_oversized_sse_line_is_terminal_invalid_event(self) -> None:
+        """FU-001: читатель ограничивает строку до разбора JSON."""
+        with mock.patch.object(server, "_MAX_SSE_LINE_BYTES", 32):
+            result = self.attempt("x")
+        self.assertEqual(result["exit_reason"], "invalid_serve_event")
+
+    def test_c6_rw005_subscribe_deadline_and_disconnect_cleanup(self) -> None:
+        """RW-005: отмена при капающих заголовках подписки возвращает терминальный результат."""
+        body = FAKE_SERVE.replace(
+            '        if self.path == "/api/event":',
+            '        if self.path == "/api/event":\n            for i in range(1000):\n                self.wfile.write(b"x"); self.wfile.flush(); time.sleep(0.03)\n            return\n        if self.path == "/api/event":',
+        )
+        _ = Path(server.OPENCODE_BIN).write_text(body)
+        for gone in (True, False):
+            with self.subTest(gone=gone):
+                start = time.monotonic()
+
+                def ignore(_text: str) -> None:
+                    return None
+
+                def ignore_tool(_tool: dict[str, object]) -> None:
+                    return None
+
+                result = server._serve_one_attempt(  # pyright: ignore[reportPrivateUsage] — причина: регрессия проверяет приватный API
+                    MODEL,
+                    "x",
+                    "high",
+                    self.tmp,
+                    ignore,
+                    ignore,
+                    ignore_tool,
+                    start,
+                    deadline=start + 0.9,
+                    is_client_gone=lambda: gone and time.monotonic() - start > 0.6,
+                )
+                self.assertEqual(
+                    result["exit_reason"], "client_gone" if gone else "timeout"
+                )
+                self.assertIs(result["delivered"], True)
+                self.assertLess(time.monotonic() - start, 2.0)
+                self.assertFalse(list(server.LEASE_DIR.glob("lease-*.json")))
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
+    def test_c6_rw005_spawn_serve_respects_deadline_and_client_disconnect_without_run_fallback(
+        self,
+    ) -> None:
+        """RW-005: отмена до Popen и во время handshake не становится ServeUnavailable."""
+        for gone in (True, False):
+            env = server._serve_env(MODEL)  # pyright: ignore[reportPrivateUsage] — причина: регрессия проверяет приватную границу транспорта
+            with mock.patch.object(subprocess, "Popen") as popen:
+                error = (
+                    server.ServeClientDisconnect
+                    if gone
+                    else server.ServeStartupDeadlineExceeded
+                )
+                with self.assertRaises(error):
+                    _ = server._spawn_serve(  # pyright: ignore[reportPrivateUsage] — причина: регрессия проверяет приватный API
+                        "cancel",
+                        env,
+                        deadline=time.monotonic() - 1,
+                        is_client_gone=lambda: gone,
+                    )
+                popen.assert_not_called()
+            self.assertFalse(Path(env["XDG_STATE_HOME"]).exists())
+        _ = Path(server.OPENCODE_BIN).write_text(
+            "#!/usr/bin/env python3\nimport time\ntime.sleep(30)\n"
+        )
+        for gone in (True, False):
+            start = time.monotonic()
+            env = server._serve_env(MODEL)  # pyright: ignore[reportPrivateUsage] — причина: регрессия проверяет приватную границу транспорта
+            with self.assertRaises(
+                server.ServeClientDisconnect
+                if gone
+                else server.ServeStartupDeadlineExceeded
+            ):
+                _ = server._spawn_serve(  # pyright: ignore[reportPrivateUsage] — причина: регрессия проверяет приватный API
+                    "handshake",
+                    env,
+                    deadline=start + 0.4,
+                    is_client_gone=lambda: gone and time.monotonic() - start > 0.15,
+                )
+            self.assertLess(time.monotonic() - start, 2.0)
+            self.assertFalse(Path(env["XDG_STATE_HOME"]).exists())
+            self.assertFalse(list(server.LEASE_DIR.glob("lease-*.json")))
+
+    def test_c6_rw006_spawn_serve_drains_multi_mib_stderr_before_bind_without_deadlock(
+        self,
+    ) -> None:
+        """RW-006: два МиБ stderr без перевода строки до bind не блокируют helper."""
+        body = FAKE_SERVE.replace('"x" * 70000 + "\\n"', '"x" * (2 * 1024 * 1024)')
+        _ = Path(server.OPENCODE_BIN).write_text(body)
+        env = server._serve_env(MODEL)  # pyright: ignore[reportPrivateUsage] — причина: регрессия проверяет приватную границу транспорта
+        lease, _, _ = server._spawn_serve("large-stderr", env)  # pyright: ignore[reportPrivateUsage] — причина: регрессия проверяет приватную границу транспорта
+        try:
+            self.assertIsNone(lease.helper.poll())
+            self.assertTrue(lease.stderr_tail)
+            self.assertLessEqual(len(lease.stderr_tail), server._MAX_STDERR_TAIL_BYTES)  # pyright: ignore[reportPrivateUsage] — причина: регрессия проверяет приватную границу транспорта
+        finally:
+            lease.cleanup()
+        self.assertFalse(server._pid_alive(-lease.pgid))  # pyright: ignore[reportPrivateUsage] — причина: регрессия проверяет приватную границу транспорта
+
+    def test_c7_rw004_startup_http_phases_enforce_own_budget_under_long_request_deadline(
+        self,
+    ) -> None:
+        """RW-004: капающие заголовки ограничены фазовым окном с обязательной уборкой группы."""
+        for method, path, budget in (
+            ("GET", "/api/session/active", 3.0),
+            ("POST", "/api/session", 3.0),
+            ("GET", "/api/event", 0.3),
+        ):
+            with self.subTest(path=path):
+                drip = """
+        if self.command==METHOD and self.path==TARGET:
+            for _ in range(2000):
+                self.wfile.write(b"x"); self.wfile.flush(); time.sleep(0.02)
+            return
+""".replace("METHOD", repr(method)).replace("TARGET", repr(path))
+                body = FAKE_SERVE.replace(
+                    "    def do_GET(self):", "    def do_GET(self):" + drip
+                ).replace("    def do_POST(self):", "    def do_POST(self):" + drip)
+                _ = Path(server.OPENCODE_BIN).write_text(body)
+                leases: list[object] = []
+                marks: list[float] = []
+                spawn_original = cast(
+                    Callable[..., tuple[object, int, str]],
+                    getattr(server, "_spawn_serve"),
+                )
+                watch_original = cast(
+                    Callable[..., threading.Event],
+                    getattr(server, "_watch_serve_connection"),
+                )
+
+                def spawn(*args: object, **kwargs: object) -> tuple[object, int, str]:
+                    result = spawn_original(*args, **kwargs)
+                    leases.append(result[0])
+                    return result
+
+                def watch(
+                    conn: http.client.HTTPConnection,
+                    deadline: float | None,
+                    gone: Callable[[], bool] | None,
+                    socks: list[socket.socket | None],
+                ) -> threading.Event:
+                    if (path != "/api/event" and len(marks) < 2) or (
+                        path == "/api/event" and len(marks) == 2
+                    ):
+                        self.assertIsNotNone(deadline)
+                        self.assertLessEqual(
+                            cast(float, deadline) - time.monotonic(), budget + 0.05
+                        )
+                    marks.append(time.monotonic())
+                    return watch_original(conn, deadline, gone, socks)
+
+                with (
+                    mock.patch.object(server, "TIMEOUT_S", 30.0),
+                    mock.patch.object(server, "FIRST_EVENT_TIMEOUT_S", 0.3),
+                    mock.patch.object(server, "_spawn_serve", side_effect=spawn),
+                    mock.patch.object(
+                        server, "_watch_serve_connection", side_effect=watch
+                    ),
+                ):
+                    started = time.monotonic()
+                    with self.assertRaises(server.ServeUnavailable):
+                        _ = self.attempt("x")
+                self.assertLess(time.monotonic() - started, budget + 4.0)
+                self.assertTrue(leases)
+                self.assertTrue(cast(bool, getattr(leases[0], "_closed")))
+                alive = cast(Callable[[int], bool], getattr(server, "_pid_alive"))
+                self.assertFalse(alive(-cast(int, getattr(leases[0], "pgid"))))
+
+    def test_c6_rw007_fu003_dripping_interrupt_delete_still_cleans_up_under_7s(
+        self,
+    ) -> None:
+        """AC-011: капающие заголовки и тела cleanup не задерживают смерть группы."""
+        for phase in ("headers", "body"):
+            with self.subTest(phase=phase):
+                drip = """
+        if self.path.endswith("/interrupt") or self.command=="DELETE":
+            if PHASE=="body":
+                self.send_response(200); self.send_header("Content-Length","1000"); self.end_headers(); self.wfile.flush()
+            for i in range(1000):
+                self.wfile.write(b"x"); self.wfile.flush(); time.sleep(0.03)
+            return
+""".replace("PHASE", repr(phase))
+                body = FAKE_SERVE.replace(
+                    '        if self.path == "/api/session/ses_test1/interrupt":',
+                    drip
+                    + '        if self.path == "/api/session/ses_test1/interrupt":',
+                ).replace("    def do_DELETE(self):", "    def do_DELETE(self):" + drip)
+                _ = Path(server.OPENCODE_BIN).write_text(body)
+                cancelled = threading.Event()
+                cancelled_at: list[float] = []
+
+                def token(_text: str) -> None:
+                    if not cancelled_at:
+                        cancelled_at.append(time.monotonic())
+                    cancelled.set()
+
+                def ignore_tool(_tool: dict[str, object]) -> None:
+                    return None
+
+                leases: list[object] = []
+                original = server._spawn_serve  # pyright: ignore[reportPrivateUsage] — причина: регрессия проверяет приватную границу транспорта
+
+                def spawn(*args: object, **kwargs: object) -> object:
+                    result = cast(
+                        tuple[object, int, str],
+                        cast(Callable[..., object], original)(*args, **kwargs),
+                    )
+                    leases.append(result[0])
+                    return result
+
+                with mock.patch.object(server, "_spawn_serve", side_effect=spawn):
+                    result = server._serve_one_attempt(  # pyright: ignore[reportPrivateUsage] — причина: регрессия проверяет приватный API
+                        MODEL,
+                        "x",
+                        "high",
+                        self.tmp,
+                        token,
+                        token,
+                        ignore_tool,
+                        time.monotonic(),
+                        is_client_gone=cancelled.is_set,
+                    )
+                self.assertTrue(cancelled_at)
+                self.assertLess(time.monotonic() - cancelled_at[0], 7.0)
+                self.assertEqual(result["exit_reason"], "client_gone")
+                self.assertFalse(
+                    server._pid_alive(-cast(int, getattr(leases[0], "pgid")))  # pyright: ignore[reportPrivateUsage] — причина: регрессия проверяет приватный API
+                )
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
+class TestCycle6HttpBounds(unittest.TestCase):
+    """Локальный TCP-апстрим для абсолютного HTTP-дедлайна и байтовых пределов."""
+
+    def _peer(
+        self, payload: bytes, drip: bool = False, hold_body: bool = False
+    ) -> tuple[socket.socket, threading.Thread, threading.Event, int]:
+        listener = socket.socket()
+        listener.bind(("127.0.0.1", 0))
+        listener.listen(1)
+        listener.settimeout(2)
+        port = cast(tuple[str, int], listener.getsockname())[1]
+        stop = threading.Event()
+
+        def send() -> None:
+            try:
+                conn = listener.accept()[0]
+                with conn:
+                    _ = conn.recv(65536)
+                    if hold_body:
+                        conn.sendall(payload)
+                        _ = stop.wait(2.0)
+                    elif drip:
+                        headers, separator, body = payload.partition(b"\r\n\r\n")
+                        stream = payload
+                        if separator:
+                            conn.sendall(headers + separator)
+                            stream = body
+                        for byte in stream:
+                            if stop.wait(0.02):
+                                break
+                            conn.sendall(bytes([byte]))
+                    else:
+                        conn.sendall(payload)
+            except OSError:
+                return
+
+        thread = threading.Thread(target=send, daemon=True)
+        thread.start()
+        return listener, thread, stop, port
+
+    def test_c6_rw007_absolute_deadline_interrupts_dripping_headers_and_body(
+        self,
+    ) -> None:
+        """RW-007: каждый байт приходит до socket timeout, но абсолютный deadline обязателен."""
+        for payload in (
+            b"HTTP/1.1 200 OK\r\nX-Slow: " + b"x" * 200,
+            b"HTTP/1.1 200 OK\r\nContent-Length: 1000\r\n\r\n" + b"x" * 1000,
+        ):
+            listener, thread, stop, port = self._peer(payload, True)
+            try:
+                start = time.monotonic()
+                with self.assertRaises((OSError, http.client.HTTPException)):
+                    _ = server._serve_http(  # pyright: ignore[reportPrivateUsage] — причина: регрессия проверяет приватный API
+                        port, "", "GET", "/", timeout=0.1, deadline=start + 0.25
+                    )
+                self.assertLess(time.monotonic() - start, 0.7)
+            finally:
+                stop.set()
+                listener.close()
+                thread.join(1)
+
+    def test_c6_rw007_skip_body_returns_immediately_after_headers(self) -> None:
+        """RW-007: cleanup не вычитывает даже отсутствующее тело с Content-Length."""
+        call = server._serve_http  # pyright: ignore[reportPrivateUsage] — причина: проверяется приватный cleanup-контракт
+        for method in ("POST", "DELETE"):
+            listener, thread, stop, port = self._peer(
+                b"HTTP/1.1 200 OK\r\nContent-Length: 1000\r\n\r\n", hold_body=True
+            )
+            try:
+                started = time.monotonic()
+                status, body = call(
+                    port,
+                    "",
+                    method,
+                    "/",
+                    timeout=0.4,
+                    deadline=started + 0.8,
+                    skip_body=True,
+                )
+                self.assertEqual((status, body), (200, {}))
+                self.assertLess(time.monotonic() - started, 0.3)
+            finally:
+                stop.set()
+                listener.close()
+                thread.join(1)
+
+    def test_c6_fu001_fu002_sse_line_body_byte_caps_and_strict_usage_ints(self) -> None:
+        """FU-001/002: точные байтовые пределы и запрет bool/отрицательных токенов."""
+        self.assertEqual(server._MAX_SSE_LINE_BYTES, 1024 * 1024)  # pyright: ignore[reportPrivateUsage] — причина: регрессия проверяет приватную границу транспорта
+        self.assertEqual(server._MAX_SERVE_HTTP_BODY_BYTES, 8 * 1024 * 1024)  # pyright: ignore[reportPrivateUsage] — причина: регрессия проверяет приватную границу транспорта
+        for key in ("input", "output", "reasoning", "read"):
+            for value in (True, -1):
+                tokens: dict[str, object] = {
+                    "input": 1,
+                    "output": 1,
+                    "reasoning": 0,
+                    "cache": {"read": 0},
+                }
+                if key == "read":
+                    tokens["cache"] = {"read": value}
+                else:
+                    tokens[key] = value
+                with (
+                    self.subTest(key=key, value=value),
+                    self.assertRaises(server.ServeProtocolError),
+                ):
+                    _ = server._map_serve_event(  # pyright: ignore[reportPrivateUsage] — причина: регрессия проверяет приватный API
+                        {
+                            "type": "session.step.ended",
+                            "data": {"sessionID": "s", "tokens": tokens},
+                        }
+                    )
+        listener, thread, stop, port = self._peer(
+            b"HTTP/1.1 200 OK\r\nContent-Length: 1024\r\n\r\n" + b"x" * 1024
+        )
+        try:
+            with (
+                mock.patch.object(server, "_MAX_SERVE_HTTP_BODY_BYTES", 32),
+                self.assertRaises(server.ServeProtocolError),
+            ):
+                _ = server._serve_http(port, "", "GET", "/")  # pyright: ignore[reportPrivateUsage] — причина: регрессия проверяет приватную границу транспорта
+        finally:
+            stop.set()
+            listener.close()
+            thread.join(1)
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
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/handoff/panel-rework-brief.json sha256=27fcdd1e812d3ab14b7630f0ef40ae3d3261d08854d1f93d2c23c473bfa7c983
{
  "schema_version": "2.0",
  "run_id": "analyst-teamlead-zen-realtime-reasoning-20261025",
  "teamlead_cycle": 8,
  "panel_slug": "panel/council/r106",
  "panel_verdict": "NEEDS_WORK",
  "summarizer_slot": "gpt-6.1-sol",
  "findings_total": 4,
  "decision_required_human": false,
  "coder_entry": "fix-from-panel",
  "iteration_budget_note": "Cycle 8 Совета Тимлидов по коду завершён после R1 (panel/council/r99, где 2/3 судей — Скептик и Визионер — выдали ACCEPT/PASS с 0 находок) и D1 (panel/council/r106) с вердиктом NEEDS_WORK (2 узких блокера RW-001..RW-002 и 2 non-blocking FU-001..FU-002). Бюджет следующей волны: точечный Coder rework (coder-12, Цикл 9) -> слепой reverse-spec -> Clean-Room L2 -> Cycle 9 Совета Тимлидов по коду.",
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
      "line_hint": "server.py:3355,3371,3885,3893",
      "rule_ref": "REQ-011, REQ-014, feature.md §2, §5",
      "action": "В `_drain_serve_step_usage` (`server.py:3355-3398`, `:3885-3905`) расширить окно дочитывания завершения инструментального шага до `min(1.0, max(0.0, deadline - time.monotonic()))`, принимать дополнительные `session.tool.called`/`failed`/`success` того же `session_id`, когда `ev_msg_id == assistant_msg_id` либо когда `assistant_msg_id` или `ev_msg_id` пусты (отсекая только события с непустым отличающимся `ev_msg_id`), и различать подтверждённый `session.step.ended` и истечение окна дочитывания без подтверждения конца шага (при неподтверждённом конце шага после истечения окна возбуждать `ServeProtocolError(\"incomplete tool step without step.ended\")`, чтобы не возвращать неполный пакет native-вызовов как успешный ответ).",
      "acceptance": "В SSE и JSON: (1) два native-вызова одного шага со вторым вызовом через `> 150 мс` (`200 мс`) и последующим `session.step.ended` доставляются полностью с точным `usage`, а события следующего `assistantMessageID` отсекаются; (2) дополнительные native-вызовы того же шага без `assistantMessageID` с последующим `session.step.ended` сохраняются; (3) при отсутствии `session.step.ended` до конца окна попытка не объявляется успешной с неполным набором.",
      "source": "F-001 (realist · R1 · realist-F-001; status=AGREED; votes: R1 realist=AUTHOR; D1 skeptic=AGREE, realist=AMEND, visionary=AGREE)",
      "source_findings": [
        "F-001"
      ],
      "evidence": "Ledger F-001: votes=[R1 realist=AUTHOR; D1 skeptic=AGREE, realist=AMEND, visionary=AGREE]; dissent=[realist d1 «AMEND F-001 priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:3355, bridges/opencode-zen-bridge/server.py:3371, bridges/opencode-zen-bridge/server.py:3885, bridges/opencod» → teamlead/cycle-8/debate/d1/realist.md]; amendments=[realist d1: priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:3355, bridges/opencode-zen-bridge/server.py:3371, bridges/opencode-zen-bridge/server.py:3885, bridges/opencode-zen-bridge/server.py:3893; fix=окно 0. (teamlead/cycle-8/debate/d1/realist.md)]."
    },
    {
      "id": "RW-002",
      "priority": "blocking",
      "criterion": "КОРРЕКТНОСТЬ",
      "file": "bridges/opencode-zen-bridge/server.py",
      "line_hint": "server.py:5438,7749,7821,7942",
      "rule_ref": "REQ-016 / AC-021, O-EXIT/v1",
      "action": "В `Handler._serve_json` (`server.py:7749-7840`) обрабатывать `result.get(\"state\") == \"timeout\"` терминально до ветки пустого текста (`upstream_failed` на `server.py:7942`): записывать `exit_reason = \"timeout\"`, возвращать прежний HTTP `502` с нейтральным учётом Circuit Breaker (`attempts.attempt_done(False, False)`, `0` инкрементов отказов).",
      "acceptance": "При исчерпании локального дедлайна до legacy spawn (`state=\"timeout\"`, сценарий FU-002 в JSON и SSE) в `O-EXIT/v1` записывается ровно одно событие с `exit_reason=\"timeout\"`, `total_spawns=0`, `0` инкрементов отказов Circuit Breaker и возвращённым резервом `_RetryBudget`.",
      "source": "F-003 (realist · R1 · realist-F-003; status=AGREED; votes: R1 realist=AUTHOR; D1 skeptic=AGREE, realist=AUTHOR, visionary=AGREE)",
      "source_findings": [
        "F-003"
      ],
      "evidence": "Ledger F-003: votes=[R1 realist=AUTHOR; D1 skeptic=AGREE, realist=AUTHOR, visionary=AGREE]; dissent=[—]; amendments=[—]."
    }
  ],
  "non_blocking_followups": [
    {
      "id": "FU-001",
      "text": "Ввести в `_ServeSseStream` (`server.py:1580, 3580-3595`) и цикле накопления ответа (`server.py:3850-3865`) явный байтовый бюджет очереди SSE-событий (`MAX_SERVE_QUEUE_BYTES = 16 * 1024 * 1024`) и накопленного текста/reasoning на попытку (`MAX_SERVE_ACCUMULATED_BYTES = 16 * 1024 * 1024`), чтобы при 6 слотах суммарная память гарантированно укладывалась в конверт `HL-ENV-01` (`<= 2 GiB`), а при превышении попытка останавливалась через `ServeProtocolError` с `cleanup()`.",
      "reason": "Согласовано квалифицированным большинством 2/3 в D1 (`skeptic`, `realist`) через `AMEND F-002 -> priority=non-blocking`; реализуем заодно в этом же проходе с детерминированным unit-тестом.",
      "source_findings": [
        "F-002"
      ],
      "decision_required_human": false
    },
    {
      "id": "FU-002",
      "text": "Сохранить совместимость `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py` с замороженным оракулом `VER-002` (`python3 -m unittest discover -s tests -p 'test_*.py'`) и существующим `unittest`-контуром моста (`tests/test_step_interruption.py`).",
      "reason": "Согласовано квалифицированным большинством 2/3 в D1 (`skeptic` `DISPUTE -> invalid`, `realist` `AMEND -> non-blocking: сохранить unittest.TestCase, чтобы VER-002 исполнял модуль`).",
      "source_findings": [
        "F-004"
      ],
      "decision_required_human": false
    }
  ],
  "excluded": []
}
ARTIFACT_END>>>

**3. Handoff исполнителя и квитанции гейтов (`coder.json`, `code-gate.json`, `verifier.json`, `final-gate.json`; `receipts/coder.json` побайтно равен `coder.json`)**
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/coder.json sha256=44cf37780c26e30dbed87160a90955b78937e76b7c9dc4d1260abd8ad057a00d
{
  "schema_version": "1.1",
  "role": "coder",
  "run_id": "analyst-teamlead-zen-realtime-reasoning-20261025",
  "task_id": "analyst-teamlead-zen-realtime-reasoning-20261025",
  "round_id": "coder-12",
  "iteration": 1,
  "teamlead_cycle": 9,
  "entry": "fix-from-panel",
  "status": "DONE",
  "next_role": "reviewer",
  "summary": "RW-001, RW-002 и FU-001 реализованы; VER-004 PASS, 209 targeted / 480 full pytest / 480 unittest PASS. Передача Reviewer; живой чат и принадлежность двух lost crash-report не проверены.",
  "role_plan": {
    "path": ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-12.json",
    "sha256": "4bf11a8740ef000ce603c365690af38229cdd8f70f323b156e3b7c05ed032c38",
    "phase": "after"
  },
  "before_plan_sha256": "5337983e2a0048c58d0d1e154a034b8dca5b7e5c04b536ff3550ecb00ee3f491",
  "changed_files": [
    "bridges/opencode-zen-bridge/server.py",
    "bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py"
  ],
  "inherited_modified_files": [
    "bridges/opencode-zen-bridge/tests/test_step_interruption.py"
  ],
  "report_files": [
    ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-12.before.json",
    ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-12.json",
    ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/handoffs/coder-12.json",
    ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/coder.json",
    ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/coder.json"
  ],
  "source_file_sha256": {
    "bridges/opencode-zen-bridge/server.py": "7fa04234e8f40620a602836a85e4bde421331cf58bd84e5cfd6b2c5fc046f0b9",
    "bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py": "3328cdf299dd5edd60c16205f6f967256571366607dc0fc3df5f2015f52a1bef",
    "bridges/opencode-zen-bridge/tests/test_step_interruption.py": "e41d10bd96cb208ce3120ab25d1c8028c82fe81895eacd322312b7fbbbef8a11"
  },
  "frozen_sha256": {
    "_run_env": "1c51b28fcb83fcc0f4d8b5204c858e11ab5ac975bfe40dca4a0bf61978008e31",
    "_execute_google_once": "88d794cc42be4878e8ab35b00e4668c427929db2dfd0f2bb4b717a63fd0c70d6",
    "_stream_google_sse": "5914c9654c7345692dd55e84cfd3765e27406f63a3df85df30bc798bc1778de3"
  },
  "commands": [
    {
      "command": "run-guarded -- uvx --offline --from pytest==8.3.4 pytest -q -p no:cacheprovider bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py -k \"c9 or c8_fu001 or c8_fu002_legacy\"",
      "exit_code": 1,
      "output": "~/work/cli-agent-bridge/coder-12-20261027/red.log",
      "background": true
    },
    {
      "command": "run-guarded -- uvx --offline --from pytest==8.3.4 pytest -q -p no:cacheprovider bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py -k \"c9 or c8_fu001 or c8_fu002_legacy\"",
      "exit_code": 0,
      "output": "~/work/cli-agent-bridge/coder-12-20261027/green.log",
      "background": true
    },
    {
      "command": "run-guarded -- python3 ~/work/cli-agent-bridge/coder-10-20261027/ver004-offline.py",
      "exit_code": 0,
      "output": "~/work/cli-agent-bridge/coder-12-20261027/ver004-final3.log",
      "background": true
    },
    {
      "command": "run-guarded -- uvx --offline --from pytest==8.3.4 pytest -q -p no:cacheprovider bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py bridges/opencode-zen-bridge/tests/test_step_interruption.py",
      "exit_code": 0,
      "output": "~/work/cli-agent-bridge/coder-12-20261027/targeted.log",
      "background": true
    },
    {
      "command": "run-guarded -- uvx --offline --from pytest==8.3.4 pytest -q -p no:cacheprovider bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py -k \"c9 or c8_fu001 or c8_fu002_legacy or c6_rw004\"",
      "exit_code": 0,
      "output": "~/work/cli-agent-bridge/coder-12-20261027/regressions-final.log",
      "background": true
    },
    {
      "command": "run-guarded -- uvx --offline --from pytest==8.3.4 pytest -q -p no:cacheprovider bridges/opencode-zen-bridge/tests",
      "exit_code": 1,
      "output": "~/work/cli-agent-bridge/coder-12-20261027/full-pytest.log",
      "background": true
    },
    {
      "command": "run-guarded -- uvx --offline --from pytest==8.3.4 pytest -q -p no:cacheprovider bridges/opencode-zen-bridge/tests",
      "exit_code": 1,
      "output": "~/work/cli-agent-bridge/coder-12-20261027/full-pytest-final.log",
      "background": true
    },
    {
      "command": "run-guarded -- uvx --offline --from pytest==8.3.4 pytest -q -p no:cacheprovider bridges/opencode-zen-bridge/tests",
      "exit_code": 0,
      "output": "~/work/cli-agent-bridge/coder-12-20261027/full-pytest-final2.log",
      "background": true
    },
    {
      "command": "run-guarded -- python3 -B -m unittest discover -s tests -p \"test_*.py\"",
      "exit_code": 0,
      "output": "~/work/cli-agent-bridge/coder-12-20261027/unittest.log",
      "background": true
    },
    {
      "command": "run-guarded -- python3 -B -m unittest tests.test_realtime_reasoning.TestServeTransportAndFakeServe.test_c8_fu002_legacy_spawn_rechecks_cancel_and_deadline_after_reservation -v",
      "exit_code": 0,
      "output": "~/work/cli-agent-bridge/coder-12-20261027/unittest-oexit-final.log",
      "background": true
    },
    {
      "command": "origin/dev isolated copy: run-guarded -- uvx --offline --from pytest==8.3.4 pytest --collect-only -q -p no:cacheprovider tests/test_realtime_reasoning.py",
      "exit_code": 0,
      "result": "101 tests collected in 0.10s",
      "background": true
    },
    {
      "command": "git diff --check",
      "exit_code": 0
    }
  ],
  "acceptance_coverage": [
    {
      "id": "RW-001",
      "status": "PASS",
      "test": "test_c8_fu001_multiple_native_tool_calls_same_step_preserved_next_step_excluded; test_c9_rw001_idless_and_unconfirmed_native_step",
      "evidence": "~/work/cli-agent-bridge/coder-12-20261027/full-pytest-final2.log"
    },
    {
      "id": "RW-002",
      "status": "PASS",
      "test": "test_c8_fu002_legacy_spawn_rechecks_cancel_and_deadline_after_reservation",
      "evidence": "~/work/cli-agent-bridge/coder-12-20261027/full-pytest-final2.log"
    },
    {
      "id": "FU-001",
      "status": "PASS",
      "test": "test_c9_fu001_serve_queue_and_accumulated_byte_budget_enforced",
      "evidence": "~/work/cli-agent-bridge/coder-12-20261027/full-pytest-final2.log"
    },
    {
      "id": "FU-002",
      "status": "PASS",
      "test": "unittest discover: 480 OK; origin/dev collect: 101 rc=0",
      "evidence": "~/work/cli-agent-bridge/coder-12-20261027/full-pytest-final2.log"
    }
  ],
  "changes": [
    "Drain ожидает до 1 секунды подтверждённого конца шага, сохраняет delayed/idless native-вызовы с dedup и завершает незакрытый lifecycle на step.ended.",
    "Неподтверждённый tool-шаг завершает попытку invalid_serve_event с interrupt/cleanup, без успешного tool_calls.",
    "Legacy JSON timeout терминален до пустого ответа, O-EXIT сохраняет timeout; timeout не записывается как success в breaker.",
    "Очередь SSE и сумма UTF-8 reasoning/text ограничены по 16 MiB с возвратом резерва при обоих путях чтения.",
    "Тестовый сценарий native посылает step.ended перед паузой; O-EXIT проверяется после завершения реальной записи logger."
  ],
  "assumptions": [
    "Продолжена назначенная внешняя роль Coder без вложенного Coder; commit/push/MR не выполнялись.",
    "test_step_interruption.py сохранён побайтово относительно coder-11."
  ],
  "risks": [
    "Живой существующий рабочий слот/чат владельца не проверен.",
    "Crash-guard полного финального pytest: exit=0 и 480 passed, но два LOST crash-report python3.14 в 17:53:43 из-за системного лимита. PID и родители скрыты unified log; принадлежность тестам не установлена, отсутствие аварий глубоких потомков не доказано.",
    "Первое единичное падение AC-016 на промежуточном конкурентном прогоне не воспроизвелось в последующих полном и отдельном прогонах; причина не установлена."
  ],
  "open_questions": [],
  "deviations": [
    "RW-001 и FU-001 требуют более 15 строк: подтверждение конца шага, завершение всех lifecycle-вызовов и синхронизированный байтовый учёт в producer и обоих consumers. Расширения архитектуры и новых зависимостей нет.",
    "Basedpyright выявил превышение сложности _serve_one_attempt после минимальной дельты. Существующий SSE-читатель механически перенесён в приватный helper того же модуля; ID шага, учёт байтов и подтверждение step.ended также выделены в приватные helpers. Блок _finish_serve_tool_step вызывает bool-drain и возбуждает тот же ServeProtocolError вместо дополнительной ветки в основном цикле. Алгоритм и владение ресурсами сохранены.",
    "Для VER-004 переиспользован известный ~/work/cli-agent-bridge/coder-10-20261027/ver004-offline.py: все исходные предикаты, offline uvx и AST Python 3.9; финальный VER-004 PASS.",
    "Первый полный pytest на промежуточной дельте: 479 passed / 1 failed (AC-016: счётчик запусков 1 вместо 2); последующие полный и отдельный прогоны AC-016 проходят. Причина единичного первого падения не установлена.",
    "Второй полный pytest: 479 passed / 1 failed из-за чтения O-EXIT до завершения logger. Регрессия усилена threading.Event от реального logger без ослабления проверки ровно одного события. После синхронизации полный pytest: 480 passed.",
    "Crash-guard финального полного pytest вернул 0, но предупредил о двух не записанных macOS crash-report в 17:53:43. Unified log подтверждает python3.14 и системный лимит, но не раскрывает PID/родителя; принадлежность прогону не установлена. Это ограничение наблюдаемости, а не доказательство отсутствия аварий."
  ],
  "verification": {
    "light": "VER-004 PASS; targeted 209 / full pytest 480 / unittest 480; origin/dev collect 101 rc=0; frozen 3/3; git diff --check PASS",
    "heavy": null,
    "not_verified": [
      "Живой рабочий слот/чат владельца",
      "Принадлежность двух потерянных macOS crash-report прогону"
    ]
  },
  "raw_outputs": {
    "full-pytest-final2.log": "........................................................................ [ 15%]\n........................................................................ [ 30%]\n........................................................................ [ 45%]\n........................................................................ [ 60%]\n........................................................................ [ 75%]\n........................................................................ [ 90%]\n................................................                         [100%]\n480 passed in 330.30s (0:05:30)\n[crash-guard] ВНИМАНИЕ: за время прогона macOS отказал записать 2 крэш-отчёт(ов) (Log limit exceeded, 17:53:43, 17:53:43). Какой-то процесс упал, но .ips нет — крэш мог остаться невидимым для гейта.\n",
    "targeted.log": "........................................................................ [ 34%]\n........................................................................ [ 68%]\n.................................................................        [100%]\n209 passed in 264.77s (0:04:24)\n",
    "unittest_summary": "----------------------------------------------------------------------\nRan 480 tests in 293.153s\n\nOK"
  },
  "invariants": {
    "frozen_raw_bytes": "PASS 3/3",
    "python39_ast": "PASS",
    "early_helper_dispatch": "PASS VER-004",
    "catalog_test_unchanged": "PASS VER-004",
    "step_test_unchanged_since_entry": true,
    "before_plan_unchanged": true,
    "no_commit_push_mr": true
  },
  "validation_log": "~/work/cli-agent-bridge/coder-12-20261027/validation-final.log"
}
ARTIFACT_END>>>
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/code-gate.json sha256=3ab247906ff11f0c6c1597f1baa42d221eff582e434ae3a266849fc50ab91f1b
{
  "schema_version": "1.0",
  "gate": "CODE_GATE_AND_L2_CLEANROOM",
  "status": "PASS",
  "timestamp": "2026-10-27T15:57:33.550925+00:00",
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
        "--offline",
        "--from",
        "pytest==8.3.4",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_realtime_reasoning.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 1,
      "wall_seconds": 68.02,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-red.log",
      "log_sha256": "b739aea60c973b1b2b560fb49f159cfcba0656dd21e2642fd835663a5840cb4a"
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
      "wall_seconds": 25.72,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver004-packet.log",
      "log_sha256": "c449413e9b822374c2af9357e3b4749006bcca0fdbe863aa1234609a3990a915"
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
      "wall_seconds": 316.58,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver001-pytest.log",
      "log_sha256": "7e25222aae48c184584c756136c9bd7feee1b106264b5367cabf3531771c7e91"
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
      "wall_seconds": 302.86,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver002-unittest.log",
      "log_sha256": "c54066270e8630333efd3cc212223dd1e57013d5d17f9cfa9876aae9c4c5e6bf"
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
      "wall_seconds": 364.46,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver003-pythonpath.log",
      "log_sha256": "3e44eeeae8fda071cfedc1bffd42d8509553c92ece5b9d412fb72f947912f1a4"
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
      "wall_seconds": 315.42,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver003b-zen-pythonpath.log",
      "log_sha256": "46e628bad80414edfeec36bc5ff63c6d1c187541e9a0fb4fc7a60e6da0c9cf9b"
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
      "wall_seconds": 236.79,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver005-dedicated.log",
      "log_sha256": "77dd6e9374c1df5dc9e15dc9a69e0abe07521cf02e1b2a77741ec912e9d3aff1"
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
      "wall_seconds": 331.05,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ac023-reversed.log",
      "log_sha256": "888434ac796a70cfff73e2fb3ebbb32c1c74d392031b19e09ebb15b868b1fd3a"
    }
  ]
}
ARTIFACT_END>>>
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/verifier.json sha256=86b45f365f47fb633cabb989e42087962197734ec1a9b3460cad54f1a827095c
{
  "schema_version": "1.0",
  "gate": "VERIFIER",
  "status": "PASS",
  "run_id": "analyst-teamlead-zen-realtime-reasoning-20261025",
  "timestamp": "2026-10-27T16:00:55.751277+00:00",
  "role_plan": {
    "path": "plans/verifier-01.json",
    "sha256": "209536af4097414b3d035186ae5c5684357e68ccc4f0f0213476bbe8394ad518"
  },
  "code_gate_sha256": "3ab247906ff11f0c6c1597f1baa42d221eff582e434ae3a266849fc50ab91f1b",
  "execution_evidence_sha256": "5ab1e19fc990dcaeeae92279874462dbfbb690346a48b7035211f75967d3f4d5",
  "verification_traceability_sha256": "57991993d6fc6bedba294fd256dc8e4869ad2e96f864ca0a99e472f6df7c1f21",
  "environment_manifest_sha256": "8e68e2d3661808a7577d5b97847f198be5f56523315cfcb1af9558d25ae31fa5",
  "reverse_spec_sha256": "5a4fbc34f2af4de42ea77883c22872b098e2beb19d4f003b3800edcb5fb1a638",
  "l3_state": "DEFERRED_L3"
}
ARTIFACT_END>>>
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/final-gate.json sha256=cc44020597c494a46f99497fc8b5a2debf82ef8845714f977f9200f38567efdb
{
  "schema_version": "1.0",
  "gate": "FINAL_GATE_PRE_COUNCIL",
  "status": "PASS",
  "run_id": "analyst-teamlead-zen-realtime-reasoning-20261025",
  "timestamp": "2026-10-27T16:00:55.751951+00:00",
  "reviewer_skip": true,
  "downstream_panel": true,
  "parent_skill": "analyst-teamlead",
  "coder_handoff_sha256": "44cf37780c26e30dbed87160a90955b78937e76b7c9dc4d1260abd8ad057a00d",
  "code_gate_sha256": "3ab247906ff11f0c6c1597f1baa42d221eff582e434ae3a266849fc50ab91f1b",
  "verifier_receipt_sha256": "86b45f365f47fb633cabb989e42087962197734ec1a9b3460cad54f1a827095c",
  "candidate_diff_sha256": "87abbc8e77587bdf7bcc61186c0aef08dacff391d6f8c25f0ba1b055d0abf5d7",
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
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/environment-manifest.json sha256=8e68e2d3661808a7577d5b97847f198be5f56523315cfcb1af9558d25ae31fa5
{
  "schema": "environment-manifest/v1",
  "captured_at_utc": "2026-10-27T16:00:55.617912+00:00",
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
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/execution-evidence.md sha256=5ab1e19fc990dcaeeae92279874462dbfbb690346a48b7035211f75967d3f4d5
# Независимое свидетельство исполнения верификации (`execution-evidence.md`, run `analyst-teamlead-zen-realtime-reasoning-20261025`, cycle `9`)

- **Базовый коммит (`origin/dev`):** `7eda27f9d82732bab726a420e31ea2adc15c2c39`
- **Отпечаток рабочего дерева ДО Coder (`coder-12-before.json`):** `None`
- **Отпечаток рабочего дерева ПОСЛЕ Coder (`coder-12-after.json`):** `None`
- **Clean-room контур L2:** отдельное `git worktree` от `origin/dev`, исполнено детерминированным `Verifier` (`run_cleanroom_l2.py`), не логами `Coder`.

## Сводная таблица проверок L2 и L3

| ID / Проверка | Уровень | Статус | Команда | CWD | Exit code | Wall (s) | Сырой лог | SHA-256 лога |
|---|---|---|---|---|---|---|---|---|
| `L2-RED-sensitivity` | L2 | `PASS (RED sensitivity rc!=0)` | `uvx --offline --from pytest==8.3.4 pytest -q -p no:cacheprovider tests/test_realtime_reasoning.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `1` | `68.02` | `l2-red.log` | `b739aea60c973b1b2b560fb49f159cfcba0656dd21e2642fd835663a5840cb4a` |
| `VER-004-packet-command` | L2 | `PASS` | `/bin/zsh -lc python3 - <<'VER004' import ast, collections, hashlib, json, re, subprocess, tempfile from pathlib import Path root = Path.c...` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom` | `0` | `25.72` | `l2-green-ver004-packet.log` | `c449413e9b822374c2af9357e3b4749006bcca0fdbe863aa1234609a3990a915` |
| `VER-004-ruff-format-new` | L2 | `PASS` | `uvx --from ruff==0.17.2 ruff format --check --no-cache tests/test_realtime_reasoning.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `0.04` | `l2-green-ver004-ruff-format-new.log` | `791491a5d9e6128b8400ae730e69e74c9af01651d625cc697d569dfdcee245b7` |
| `VER-001-pytest` | L2 | `PASS` | `uvx pytest -q -p no:cacheprovider tests/` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `316.58` | `l2-green-ver001-pytest.log` | `7e25222aae48c184584c756136c9bd7feee1b106264b5367cabf3531771c7e91` |
| `VER-002-unittest` | L2 | `PASS` | `python3 -m unittest discover -s tests -p test_*.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `302.86` | `l2-green-ver002-unittest.log` | `c54066270e8630333efd3cc212223dd1e57013d5d17f9cfa9876aae9c4c5e6bf` |
| `VER-003-root-pythonpath-pytest` | L2 | `PASS` | `uvx pytest -q -p no:cacheprovider tests/` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom` | `0` | `364.46` | `l2-green-ver003-pythonpath.log` | `3e44eeeae8fda071cfedc1bffd42d8509553c92ece5b9d412fb72f947912f1a4` |
| `VER-003b-root-pythonpath-zen-pytest` | L2 | `PASS` | `uvx pytest -q -p no:cacheprovider bridges/opencode-zen-bridge/tests/` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom` | `0` | `315.42` | `l2-green-ver003b-zen-pythonpath.log` | `46e628bad80414edfeec36bc5ff63c6d1c187541e9a0fb4fc7a60e6da0c9cf9b` |
| `VER-005-dedicated-realtime-suite` | L2 | `PASS` | `uvx pytest -q -p no:cacheprovider tests/test_realtime_reasoning.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `236.79` | `l2-green-ver005-dedicated.log` | `77dd6e9374c1df5dc9e15dc9a69e0abe07521cf02e1b2a77741ec912e9d3aff1` |
| `AC-023-pytest-reversed` | L2 | `PASS` | `uvx pytest -q -p no:cacheprovider tests/test_zen_catalog.py tests/test_tool_emulation.py tests/test_sync_yaml.py tests/test_stream_thinki...` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `331.05` | `l2-green-ac023-reversed.log` | `888434ac796a70cfff73e2fb3ebbb32c1c74d392031b19e09ebb15b868b1fd3a` |
| `VER-006-live-sse-heavy-path` | L3 | `DEFERRED_L3` | `Rollout ladder H0..H9 + curl -N -sS http://127.0.0.1:9883/v1/chat/completions (deepseek-v4.1-flash-free High, stream=true, multi-turn + tools + disconnect cleanup)` | `~/.dsh/bridges/opencode-zen-bridge` |  |  |  |  |
| `VER-007-deployed-mirror-diff` | L3 | `DEFERRED_L3` | `diff -u bridges/opencode-zen-bridge/server.py ~/.dsh/bridges/opencode-zen-bridge/server.py` | `~/tmp/cli-agent-bridge/zen-realtime-reasoning` |  |  |  |  |

> **Причина отсрочки `DEFERRED_L3` (`verification-integrity.md` §8, `acceptance-package.md` §3):** мутация живого боевого моста `~/.dsh/bridges/opencode-zen-bridge/server.py` (`127.0.0.1:9883`) запрещена до получения вердикта `ACCEPT` Совета Тимлидов (`Forbidden Scope` `handoff-architect.md`, `rollout H0..H9`). Сразу после `ACCEPT` Совета выполняется бэкап в `~/work/backups/`, синхронизация `server.py`, лестница `H0..H9` и живая heavy-path проверка с переводом строк `VER-006`/`VER-007` в `PASS` до открытия MR.

## Сырые логи независимого прогона L2 (`Clean-Room`)

### `L2-RED-sensitivity` (`l2-red.log`, `sha256=b739aea60c973b1b2b560fb49f159cfcba0656dd21e2642fd835663a5840cb4a`)
```text
$ uvx --offline --from pytest==8.3.4 pytest -q -p no:cacheprovider tests/test_realtime_reasoning.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=1] [wall=68.02s]
--- STDOUT ---
FFFFFFF..FF.FFFFFFFFFFFFFFFFFFFFF.FFFFFFF.FFFFFFFFFFFFFFFFFFFFFF.F.FFFFF [ 71%]
FFFFFFFFFFFFFFFFFFFFFFFFFFFFF                                            [100%]
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
        ]
E       AttributeError: module 'server' has no attribute 'STATUS_INITIAL'

tests/test_realtime_reasoning.py:521: AttributeError
----------------------------- Captured stderr call -----------------------------
2026-10-27 18:00:32 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1023 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 18:00:32 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 18:00:35 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=6 emulate_tools=True retries=0 total_spawns=1
2026-10-27 18:00:35 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=6 duration_s=2.86
_ TestLegacyWatchdogAndKillpg.test_c5_rw003_legacy_retry_separator_all_branches_and_thinking_gate _

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
                            _write_exe(self.tmp, "retry-legacy", body
... [фрагмент оракула AC-026 из середины лога (l2-red.log, sha256=b739aea60c973b1b2b560fb49f159cfcba0656dd21e2642fd835663a5840cb4a)] ...
 = server.FIRST_EVENT_TIMEOUT_S
E       AttributeError: module 'server' has no attribute 'FIRST_EVENT_TIMEOUT_S'

tests/test_realtime_reasoning.py:625: AttributeError
_ TestServeTransportAndFakeServe.test_ac026_realtime_chunks_before_upstream_end _

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_ac026_realtime_chunks_before_upstream_end>

    def test_ac026_realtime_chunks_before_upstream_end(self) -> None:
        """AC-026: reasoning-чанки приходят, пока апстрим ещё идёт."""
        end_record = self.tmp / "upstream-ended"
        chunks, _elapsed = self.bridge.post_stream_timed(
            f"обычный запрос __end_record:{end_record}__"
        )
        reasoning = _deltas(chunks, "reasoning_content")
        model_reasoning = [
            (at, t) for at, t in reasoning if not t.lstrip("\n").startswith("[мост]")
        ]
>       self.assertGreaterEqual(len(model_reasoning), 5, chunks)
E       AssertionError: 1 not greater than or equal to 5 : [(0.0013814999256283045, {'id': 'chatcmpl-oczen-a5352cd8ba23', 'object': 'chat.completion.chunk', 'created': 1793113248, 'model': 'muse-spark-1.3-contributor-free', 'choices': [{'index': 0, 'delta': {'role': 'assistant', 'content': ''}}]}), (1.550856375019066, {'id': 'chatcmpl-oczen-a5352cd8ba23', 'object': 'chat.completion.chunk', 'created': 1793113248, 'model': 'muse-spark-1.3-contributor-free', 'choices': [{'index': 0, 'delta': {'reasoning_content': 'Поздняя мысль'}}]}), (1.5508868339238688, {'id': 'chatcmpl-oczen-a5352cd8ba23', 'object': 'chat.completion.chunk', 'created': 1793113248, 'model': 'muse-spark-1.3-contributor-free', 'choices': [{'index': 0, 'delta': {'content': 'Поздний ответ'}}]}), (1.80859375, {'id': 'chatcmpl-oczen-a5352cd8ba23', 'object': 'chat.completion.chunk', 'created': 1793113248, 'model': 'muse-spark-1.3-contributor-free', 'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}], 'usage': {'prompt_tokens': 1, 'completion_tokens': 1, 'total_tokens': 2}})]

tests/test_realtime_reasoning.py:1431: AssertionError
----------------------------- Captured stderr call -----------------------------
2026-10-27 18:00:48 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1125 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 18:00:48 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 18:00:50 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=13 emulate_tools=True retries=0 total_spawns=1
2026-10-27 18:00:50 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=
... [пропущено 132033 символов однотипного вывода; полный лог на диске receipts/l2-red.log sha256=b739aea60c973b1b2b560fb49f159cfcba0656dd21e2642fd835663a5840cb4a] ...
     start_new_session=True,
            )
            self.assertNotIn("NameError", proc.stderr)
>           self.assertEqual(proc.returncode, 0, proc.stderr)
E           AssertionError: 2 != 0 : OPENCODE_ZEN_BRIDGE_KEY is required; refusing to start

tests/test_realtime_reasoning.py:3581: AssertionError
=========================== short test summary info ============================
FAILED tests/test_realtime_reasoning.py::TestLegacyWatchdogAndKillpg::test_c5_rw002_limiter_delay_half_second_still_emits_first_status_under_1s
FAILED tests/test_realtime_reasoning.py::TestLegacyWatchdogAndKillpg::test_c5_rw003_legacy_retry_separator_all_branches_and_thinking_gate
FAILED tests/test_realtime_reasoning.py::TestLegacyWatchdogAndKillpg::test_c6_rw002_legacy_first_token_timeout_respects_configured_value_under_120s
FAILED tests/test_realtime_reasoning.py::TestLegacyWatchdogAndKillpg::test_c6_rw003_active_subagent_does_not_trigger_token_stall
FAILED tests/test_realtime_reasoning.py::TestLegacyWatchdogAndKillpg::test_c6_rw003_nonstream_json_run_execute_enforces_phase_watchdogs
FAILED tests/test_realtime_reasoning.py::TestLegacyWatchdogAndKillpg::test_c7_rw001_json_run_watchdog_oexit_reason_and_phase_timings
FAILED tests/test_realtime_reasoning.py::TestLegacyWatchdogAndKillpg::test_c7_rw003_legacy_sse_watchdog_records_breaker_failure_with_and_without_output
FAILED tests/test_realtime_reasoning.py::TestLegacyWatchdogAndKillpg::test_initial_status_before_1s_under_startup_gate_contention
FAILED tests/test_realtime_reasoning.py::TestLegacyWatchdogAndKillpg::test_oexit_fields_present
FAILED tests/test_realtime_reasoning.py::TestLegacyWatchdogAndKillpg::test_rw002_initial_status_while_waiting_spawn_limiter
FAILED tests/test_realtime_reasoning.py::TestLegacyWatchdogAndKillpg::test_slow_upstream_gets_initial_status_before_1s
FAILED tests/test_realtime_reasoning.py::TestLegacyWatchdogAndKillpg::test_watchdog_first_event_timeout
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_ac026_realtime_chunks_before_upstream_end
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_auto_fallback_to_run_and_sticky_degradation
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_c5_fu003_json_transient_recovery_normalizes_and_deduplicates
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_c5_rw001_prompt_headers_then_body_error_or_429_blocks_run_fallback
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_c6_rw001_headers_at_blocks_run_fallback_on_sse_error_and_timeout
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_c6_rw004_ac016_serve_step_interruption_matrix
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_c6_rw004_ac017_unmapped_recovery_serve_vs_run_equivalence
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_c6_rw005_startup_abort_never_falls_back_or_changes_serve_health
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_c7_fu001_native_tool_call_captures_step_ended_usage
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_c7_rw002_execution_started_before_prompt_headers_sets_delivered_and_blocks_run_fallback
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_c8_fu001_multiple_native_tool_calls_same_step_preserved_next_step_excluded
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_c8_fu002_legacy_spawn_rechecks_cancel_and_deadline_after_reservation
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_c8_rw001_early_transient_error_after_execution_started_retries_serve_without_run_fallback
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_c8_rw002_pre_delivery_surrogate_falls_back_to_run
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_c8_rw002_unpaired_surrogate_raises_serve_protocol_error_in_sse_and_json
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_c8_rw003_request_deadline_timeout_is_neutral_for_circuit_breaker
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_c9_rw001_idless_and_unconfirmed_native_step
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_canonical_frozen_fixtures
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_dynamic_config_switch_same_server
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_foreign_listener_rejected_and_startup_reaper
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_form_missing_title_cancels_without_step2
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_fu003_usage_once_across_distinct_retry_branches
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_fu010_thinking_off_omits_retry_separator
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_fu011_cancelled_never_counts_as_success
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_helper_argv_validation_and_lease_dir
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
FAILED tests/test_realtime_reasoning.py::TestReworkUnits::test_c8_fu002_pre_spawn_gate_and_limiter_respect_deadline_and_client_disconnect
FAILED tests/test_realtime_reasoning.py::TestReworkUnits::test_disable_file_overrides_forced_serve
FAILED tests/test_realtime_reasoning.py::TestReworkUnits::test_elf_magic_and_tool_status
FAILED tests/test_realtime_reasoning.py::TestReworkUnits::test_fu001_http_checks_deadline_and_cancellation_before_connect
FAILED tests/test_realtime_reasoning.py::TestReworkUnits::test_rw004_native_calls_share_canonical_mapping
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
FAILED tests/test_realtime_reasoning.py::TestServeAttemptOracles::test_c6_fu001_oversized_sse_line_is_terminal_invalid_event
FAILED tests/test_realtime_reasoning.py::TestServeAttemptOracles::test_c6_rw005_subscribe_deadline_and_disconnect_cleanup
FAILED tests/test_realtime_reasoning.py::TestServeAttemptOracles::test_c9_fu001_serve_queue_and_accumulated_byte_budget_enforced
FAILED tests/test_realtime_reasoning.py::TestServeAttemptOracles::test_never_event_gives_first_event_timeout
FAILED tests/test_realtime_reasoning.py::TestServeAttemptOracles::test_prompt_http_4xx_fails_closed_fast
FAILED tests/test_realtime_reasoning.py::TestServeAttemptOracles::test_silent_model_gives_first_token_timeout
FAILED tests/test_realtime_reasoning.py::TestServeAttemptOracles::test_sse_pause_over_half_second_keeps_stream_alive
FAILED tests/test_realtime_reasoning.py::TestServeAttemptOracles::test_stall_after_first_token
FAILED tests/test_realtime_reasoning.py::TestServeAttemptOracles::test_startup_gate_released_before_generation_ends
FAILED tests/test_realtime_reasoning.py::TestServeAttemptOracles::test_text_tool_call_closes_step_on_step_finish
FAILED tests/test_realtime_reasoning.py::TestSpawnAndLeaseOracles::test_c6_rw005_spawn_serve_respects_deadline_and_client_disconnect_without_run_fallback
FAILED tests/test_realtime_reasoning.py::TestSpawnAndLeaseOracles::test_c6_rw006_spawn_serve_drains_multi_mib_stderr_before_bind_without_deadlock
FAILED tests/test_realtime_reasoning.py::TestSpawnAndLeaseOracles::test_c6_rw007_fu003_dripping_interrupt_delete_still_cleans_up_under_7s
FAILED tests/test_realtime_reasoning.py::TestSpawnAndLeaseOracles::test_c7_rw004_startup_http_phases_enforce_own_budget_under_long_request_deadline
FAILED tests/test_realtime_reasoning.py::TestSpawnAndLeaseOracles::test_client_gone_check_detects_reset_and_close
FAILED tests/test_realtime_reasoning.py::TestSpawnAndLeaseOracles::test_lease_cleanup_confirms_sigkill_in_separate_window
FAILED tests/test_realtime_reasoning.py::TestSpawnAndLeaseOracles::test_spawn_failures_leave_no_leftovers
FAILED tests/test_realtime_reasoning.py::TestCycle6HttpBounds::test_c6_fu001_fu002_sse_line_body_byte_caps_and_strict_usage_ints
FAILED tests/test_realtime_reasoning.py::TestCycle6HttpBounds::test_c6_rw007_absolute_deadline_interrupts_dripping_headers_and_body
FAILED tests/test_realtime_reasoning.py::TestCycle6HttpBounds::test_c6_rw007_skip_body_returns_immediately_after_headers
FAILED tests/test_realtime_reasoning.py::TestHelperProcess::test_errno_imported_before_helper_branch
FAILED tests/test_realtime_reasoning.py::TestHelperProcess::test_helper_kills_surviving_group_and_removes_lease_last
FAILED tests/test_realtime_reasoning.py::TestHelperProcess::test_helper_survives_bad_stdin_without_name_error
94 failed, 7 passed in 67.83s (0:01:07)

--- STDERR ---
```

### `VER-004-packet-command` (`l2-green-ver004-packet.log`, `sha256=c449413e9b822374c2af9357e3b4749006bcca0fdbe863aa1234609a3990a915`)
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
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom] [rc=0] [wall=25.72s]
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
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
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
BASEDPYRIGHT summary {'filesAnalyzed': 3, 'errorCount': 0, 'warningCount': 759, 'informationCount': 0, 'timeInSec': 4.709}
SERVER dict(counts) {'reportExplicitAny': 123, 'reportAny': 116, 'reportUnusedCallResult': 35, 'reportUnknownMemberType': 73, 'reportUnknownVariableType': 56, 'reportUnknownArgumentType': 47, 'reportUnusedFunction': 2, 'reportImplicitStringConcatenation': 27, 'reportUnannotatedClassAttribute': 98, 'reportUnusedParameter': 3, 'reportUnnecessaryIsInstance': 4, 'reportUnknownParameterType': 2, 'reportMissingParameterType': 2, 'reportUnreachable': 1, 'reportImplicitOverride': 1}
SERVER warningCount 590
PASS VER-004: all3 lint/type; legacy changed-range format; newfile whole format; server counts {'reportExplicitAny': 123, 'reportAny': 116, 'reportUnusedCallResult': 35, 'reportUnknownMemberType': 73, 'reportUnknownVariableType': 56, 'reportUnknownArgumentType': 47, 'reportUnusedFunction': 2, 'reportImplicitStringConcatenation': 27, 'reportUnannotatedClassAttribute': 98, 'reportUnusedParameter': 3, 'reportUnnecessaryIsInstance': 4, 'reportUnknownParameterType': 2, 'reportMissingParameterType': 2, 'reportUnreachable': 1, 'reportImplicitOverride': 1}

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
Ran 8 tests in 0.194s

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

### `VER-001-pytest` (`l2-green-ver001-pytest.log`, `sha256=7e25222aae48c184584c756136c9bd7feee1b106264b5367cabf3531771c7e91`)
```text
$ uvx pytest -q -p no:cacheprovider tests/
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=316.58s]
--- STDOUT ---
......................... [  5%]
............................................................................................................................................ [ 34%]
............................................................................................................ [ 56%]
................................................................. [ 70%]
....................................................................................................................................... [ 98%]
.......                                                              [100%]
480 passed, 3275 subtests passed in 316.02s (0:05:16)

--- STDERR ---
```

### `VER-002-unittest` (`l2-green-ver002-unittest.log`, `sha256=c54066270e8630333efd3cc212223dd1e57013d5d17f9cfa9876aae9c4c5e6bf`)
```text
$ python3 -m unittest discover -s tests -p test_*.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=302.86s]
--- STDOUT ---

--- STDERR ---
..........2026-10-27 18:07:27 http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-27 18:07:27 O-EXIT/v1 mode=json model=jev-1.13 status=400 exit_reason=bad_request rc=None total_spawns=0 retries=0 signal=0 tools=0 out_chars=0 transport=none first_event_ms=None ttft_ms=None transport_history=[] duration_s=0.00
2026-10-27 18:07:27 http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-27 18:07:27 O-EXIT/v1 mode=json model=jev-1.13-free status=400 exit_reason=bad_request rc=None total_spawns=0 retries=0 signal=0 tools=0 out_chars=0 transport=none first_event_ms=None ttft_ms=None transport_history=[] duration_s=0.00
2026-10-27 18:07:27 http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-27 18:07:27 O-EXIT/v1 mode=json model=nemotron-3-ultra-free status=400 exit_reason=bad_request rc=None total_spawns=0 retries=0 signal=0 tools=0 out_chars=0 transport=none first_event_ms=None ttft_ms=None transport_history=[] duration_s=0.00
2026-10-27 18:07:27 http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-27 18:07:27 O-EXIT/v1 mode=json model=test status=400 exit_reason=bad_request rc=None total_spawns=0 retries=0 signal=0 tools=0 out_chars=0 transport=none first_event_ms=None ttft_ms=None transport_history=[] duration_s=0.00
2026-10-27 18:07:27 http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-27 18:07:27 O-EXIT/v1 mode=json model=claude-opus-5-5-backup status=400 exit_reason=bad_request rc=None total_spawns=0 retries=0 signal=0 tools=0 out_chars=0 transport=none first_event_ms=None ttft_ms=None transport_history=[] duration_s=0.00
2026-10-27 18:07:27 http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-27 18:07:27 O-EXIT/v1 mode=json model=deepseek-v4.1-flash status=400 exit_reason=bad_request rc=None total_spawns=0 retries=0 signal=0 tools=0 out_chars=0 transport=none first_event_ms=None ttft_ms=None transport_history=[] duration_s=0.00
2026-10-27 18:07:27 http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-27 18:07:27 O-EXIT/v1 mode=json model=claude-haiku-5-5 status=400 exit_reason=bad_request rc=None total_spawns=0 retries=0 signal=0 tools=0 out_chars=0 transport=none first_event_ms=None ttft_ms=None transport_history=[] duration_s=0.00
.2026-10-27 18:07:27 http "GET /health HTTP/1.1" 200 -
.2026-10-27 18:07:27 http "GET /v1/models HTTP/1.1" 200 -
.2026-10-27 18:07:27 http "GET /v1/models HTTP/1.1" 401 -
........................2026-10-27 18:07:29 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=32 cwd=/var/folders/2f/***/T/tmp3suowdr3/ws
2026-10-27 18:07:29 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 18:07:30 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=7 emulate_tools=False retries=0 total_spawns=1
2026-10-27 18:07:30 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=7 transport=run first_event_ms=219 ttft_ms=219 transport_history=['run'] duration_s=0.48
.2026-10-27 18:07:30 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=32 cwd=/var/folders/2f/***/T/tmp3suowdr3/ws
2026-10-27 18:07:30 exec cli failed rc=1 state=nonzero_exit stderr_tail='Error: Unexpected error\ndatabase is locked'
2026-10-27 18:07:30 exec failed rc=1 without output, retry 1/2 total_spawns=1/3: 'Error: Unexpected error\ndatabase is locked'
2026-10-27 18:07:30 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=32 cwd=/var/folders/2f/***/T/tmp3suowdr3/ws
2026-10-27 18:07:31 done model=muse-spark-1.3-contributor-free rc=0 state=ok tools=0 out_chars=
... [пропущено 130949 символов однотипного вывода; полный лог на диске receipts/l2-green-ver002-unittest.log sha256=c54066270e8630333efd3cc212223dd1e57013d5d17f9cfa9876aae9c4c5e6bf] ...
26-10-27 18:12:09 exec: step with tool call finished, stopping opencode run
2026-10-27 18:12:09 tool_call_unparsed bytes=7 head='{broken'
2026-10-27 18:12:09 dropped 1 unparsed tool block(s) from content
2026-10-27 18:12:09 done model=glm-5.3-flash-free rc=-15 state=nonzero_exit tools=2 out_chars=0 retries=0 total_spawns=1
2026-10-27 18:12:09 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 18:12:09 O-EXIT/v1 mode=json model=glm-5.3-flash-free status=200 exit_reason=ok rc=-15 total_spawns=1 retries=0 signal=0 tools=2 out_chars=0 transport=run first_event_ms=24 ttft_ms=24 transport_history=['run'] duration_s=0.03
.2026-10-27 18:12:09 stream exec model=opencode/glm-5.3-flash-free -m opencode/glm-5.3-flash-free#high --standalone --thinking prompt_chars=1224 cwd=/var/folders/2f/***/T/tmpnbsbd9jj/ws
2026-10-27 18:12:09 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 18:12:09 tool_call_unparsed bytes=7 head='{broken'
2026-10-27 18:12:09 stream dropped 1 unparsed tool block(s) from content
2026-10-27 18:12:09 stream incomplete tool step: re-prompt 1/2 signal=2 total_spawns=1/3
2026-10-27 18:12:09 stream exec retry=1 fail_retries=0 model=opencode/glm-5.3-flash-free prompt_chars=1868 total_spawns=1/3
2026-10-27 18:12:10 stream: step with tool call finished, stopping opencode run
2026-10-27 18:12:10 stream done model=glm-5.3-flash-free rc=-15 tools=2 out_chars=78 emulate_tools=True retries=1 total_spawns=2
2026-10-27 18:12:10 O-EXIT/v1 mode=stream model=glm-5.3-flash-free status=200 exit_reason=ok rc=-15 total_spawns=2 retries=1 signal=2 tools=2 out_chars=78 transport=run first_event_ms=22 ttft_ms=22 transport_history=['run'] duration_s=1.02
.2026-10-27 18:12:10 stream exec model=opencode/glm-5.3-flash-free -m opencode/glm-5.3-flash-free#high --standalone --thinking prompt_chars=1224 cwd=/var/folders/2f/***/T/tmpnbsbd9jj/ws
2026-10-27 18:12:10 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 18:12:10 tool_call_unparsed bytes=7 head='{broken'
2026-10-27 18:12:10 stream dropped 1 unparsed tool block(s) from content
2026-10-27 18:12:11 stream incomplete tool step: re-prompt 1/2 signal=2 total_spawns=1/3
2026-10-27 18:12:11 stream exec retry=1 fail_retries=0 model=opencode/glm-5.3-flash-free prompt_chars=1777 total_spawns=1/3
2026-10-27 18:12:11 tool_call_unparsed bytes=7 head='{broken'
2026-10-27 18:12:11 stream dropped 1 unparsed tool block(s) from content
2026-10-27 18:12:13 stream incomplete tool step: re-prompt 2/2 signal=2 total_spawns=2/3
2026-10-27 18:12:13 stream exec retry=2 fail_retries=0 model=opencode/glm-5.3-flash-free prompt_chars=1777 total_spawns=2/3
2026-10-27 18:12:13 tool_call_unparsed bytes=7 head='{broken'
2026-10-27 18:12:13 stream dropped 1 unparsed tool block(s) from content
2026-10-27 18:12:13 stream incomplete tool step: retries exhausted (2) signal=2
2026-10-27 18:12:13 stream done model=glm-5.3-flash-free rc=0 tools=0 out_chars=66 emulate_tools=True retries=2 total_spawns=3
2026-10-27 18:12:13 O-EXIT/v1 mode=stream model=glm-5.3-flash-free status=200 exit_reason=ok rc=0 total_spawns=3 retries=2 signal=2 tools=0 out_chars=66 transport=run first_event_ms=20 ttft_ms=20 transport_history=['run'] duration_s=3.05
.2026-10-27 18:12:13 stream exec model=opencode/glm-5.3-flash-free -m opencode/glm-5.3-flash-free#high --standalone --thinking prompt_chars=1224 cwd=/var/folders/2f/***/T/tmpnbsbd9jj/ws
2026-10-27 18:12:13 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 18:12:13 tool_call_recovered extra_braces=1
2026-10-27 18:12:13 stream: step with tool call finished, stopping opencode run
2026-10-27 18:12:13 stream done model=glm-5.3-flash-free rc=-15 tools=1 out_chars=0 emulate_tools=True retries=0 total_spawns=1
2026-10-27 18:12:13 O-EXIT/v1 mode=stream model=glm-5.3-flash-free status=200 exit_reason=ok rc=-15 total_spawns=1 retries=0 signal=0 tools=1 out_chars=0 transport=run first_event_ms=19 ttft_ms=19 transport_history=['run'] duration_s=0.02
.2026-10-27 18:12:13 stream exec model=opencode/glm-5.3-flash-free -m opencode/glm-5.3-flash-free#high --standalone --thinking prompt_chars=1224 cwd=/var/folders/2f/***/T/tmpnbsbd9jj/ws
2026-10-27 18:12:13 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 18:12:13 stream done model=glm-5.3-flash-free rc=0 tools=0 out_chars=7 emulate_tools=True retries=0 total_spawns=1
2026-10-27 18:12:13 O-EXIT/v1 mode=stream model=glm-5.3-flash-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=7 transport=run first_event_ms=20 ttft_ms=20 transport_history=['run'] duration_s=0.28
.2026-10-27 18:12:13 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=7872 cwd=/var/folders/2f/***/T/tmpnbsbd9jj/ws
2026-10-27 18:12:14 done model=muse-spark-1.3-contributor-free rc=0 state=ok tools=0 out_chars=7 retries=0 total_spawns=1
2026-10-27 18:12:14 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 18:12:14 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=7 transport=run first_event_ms=18 ttft_ms=18 transport_history=['run'] duration_s=0.28
.2026-10-27 18:12:14 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1216 cwd=/var/folders/2f/***/T/tmpnbsbd9jj/ws
2026-10-27 18:12:14 opencode built-in tool event: tool=todoread status=error mapped=False as=[]
2026-10-27 18:12:15 unmapped built-in tools=['todoread']: re-prompt 1/2
2026-10-27 18:12:15 exec retry=1 (unmapped built-in tool) total_spawns=1/3
2026-10-27 18:12:15 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1715 cwd=/var/folders/2f/***/T/tmpnbsbd9jj/ws
2026-10-27 18:12:15 opencode built-in tool event: tool=todoread status=error mapped=False as=[]
2026-10-27 18:12:15 unmapped built-in tools=['todoread']: re-prompt 2/2
2026-10-27 18:12:15 exec retry=2 (unmapped built-in tool) total_spawns=2/3
2026-10-27 18:12:15 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=2214 cwd=/var/folders/2f/***/T/tmpnbsbd9jj/ws
2026-10-27 18:12:16 retry denied (incomplete_step): MAX_TOTAL_SPAWNS=3 reached
2026-10-27 18:12:16 incomplete tool step: retries exhausted (0) signal=4
2026-10-27 18:12:16 done model=muse-spark-1.3-contributor-free rc=0 state=ok tools=0 out_chars=125 retries=2 total_spawns=3
2026-10-27 18:12:16 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 18:12:16 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=3 retries=2 signal=0 tools=0 out_chars=125 transport=run first_event_ms=29 ttft_ms=29 transport_history=['run'] duration_s=2.43
.2026-10-27 18:12:16 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1216 cwd=/var/folders/2f/***/T/tmpnbsbd9jj/ws
2026-10-27 18:12:16 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 18:12:16 opencode built-in tool event: tool=todoread status=error mapped=False as=[]
2026-10-27 18:12:17 stream unmapped built-in tools=['todoread']: re-prompt 1/2
2026-10-27 18:12:17 stream exec retry=1 fail_retries=0 model=opencode/muse-spark-1.3-contributor-free prompt_chars=1715 total_spawns=1/3
2026-10-27 18:12:17 opencode built-in tool event: tool=todoread status=error mapped=False as=[]
2026-10-27 18:12:19 stream unmapped built-in tools=['todoread']: re-prompt 2/2
2026-10-27 18:12:19 stream exec retry=2 fail_retries=0 model=opencode/muse-spark-1.3-contributor-free prompt_chars=2214 total_spawns=2/3
2026-10-27 18:12:19 retry denied (incomplete_step): MAX_TOTAL_SPAWNS=3 reached
2026-10-27 18:12:19 stream incomplete tool step: retries exhausted (0) signal=4
2026-10-27 18:12:19 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=125 emulate_tools=True retries=2 total_spawns=3
2026-10-27 18:12:19 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=3 retries=2 signal=0 tools=0 out_chars=125 transport=run first_event_ms=19 ttft_ms=3245 transport_history=['run'] duration_s=3.50
.2026-10-27 18:12:19 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1216 cwd=/var/folders/2f/***/T/tmpnbsbd9jj/ws
2026-10-27 18:12:19 exec: provider error mid-response (transient=True), stopping opencode run
2026-10-27 18:12:20 exec cli failed rc=1 state=provider_error stderr_tail='HTTP None: provider.transport: Connection lost: ECONNRESET'
2026-10-27 18:12:20 opencode built-in tool event: tool=todoread status=error mapped=False as=[]
2026-10-27 18:12:20 unmapped built-in tools=['todoread']: re-prompt 1/2
2026-10-27 18:12:20 exec retry=1 (unmapped built-in tool) total_spawns=1/3
2026-10-27 18:12:20 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1715 cwd=/var/folders/2f/***/T/tmpnbsbd9jj/ws
2026-10-27 18:12:21 exec: step with tool call finished, stopping opencode run
2026-10-27 18:12:21 done model=muse-spark-1.3-contributor-free rc=-15 state=nonzero_exit tools=2 out_chars=0 retries=1 total_spawns=2
2026-10-27 18:12:21 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 18:12:21 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=-15 total_spawns=2 retries=1 signal=0 tools=2 out_chars=0 transport=run first_event_ms=29 ttft_ms=29 transport_history=['run'] duration_s=1.04
.2026-10-27 18:12:21 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1216 cwd=/var/folders/2f/***/T/tmpnbsbd9jj/ws
2026-10-27 18:12:21 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 18:12:21 opencode built-in tool event: tool=todoread status=error mapped=False as=[]
2026-10-27 18:12:22 stream unmapped built-in tools=['todoread']: re-prompt 1/2
2026-10-27 18:12:22 stream exec retry=1 fail_retries=0 model=opencode/muse-spark-1.3-contributor-free prompt_chars=1715 total_spawns=1/3
2026-10-27 18:12:22 stream incomplete tool step: re-prompt 1/2 signal=4 total_spawns=2/3
2026-10-27 18:12:22 stream exec retry=2 fail_retries=0 model=opencode/muse-spark-1.3-contributor-free prompt_chars=1900 total_spawns=2/3
2026-10-27 18:12:23 stream: step with tool call finished, stopping opencode run
2026-10-27 18:12:23 stream done model=muse-spark-1.3-contributor-free rc=-15 tools=2 out_chars=125 emulate_tools=True retries=2 total_spawns=3
2026-10-27 18:12:23 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=-15 total_spawns=3 retries=2 signal=4 tools=2 out_chars=125 transport=run first_event_ms=23 ttft_ms=1157 transport_history=['run'] duration_s=2.17
.....2026-10-27 18:12:23 tool_strip_cap_hit max=16 dropping tail
2026-10-27 18:12:23 tool_strip_cap_hit max=16 dropping tail
2026-10-27 18:12:23 tool_strip_cap_hit max=16 dropping tail
..........................................................2026-10-27 18:12:25 tool_call_unparsed bytes=114 head='{"name": "read", "arguments": {"file_path": "/a"}} `<tool_call>`{"name": "read", "arguments": {"file_path": "/b"}}'
...2026-10-27 18:12:25 tool_call_unparsed bytes=23 head='<tool_call>{"name":"a"}'
2026-10-27 18:12:25 tool_call_unparsed bytes=47 head='{"name":"a"}<tool_call> <tool_call>{"name":"b"}'
2026-10-27 18:12:25 tool_call_unparsed bytes=23 head='{"name":"a"}<tool_call>'
.2026-10-27 18:12:25 tool_call_unparsed bytes=32 head='{"name": "a"} <tool_call>{broken'
..............................................
----------------------------------------------------------------------
Ran 480 tests in 302.696s

OK
```

### `VER-003-root-pythonpath-pytest` (`l2-green-ver003-pythonpath.log`, `sha256=3e44eeeae8fda071cfedc1bffd42d8509553c92ece5b9d412fb72f947912f1a4`)
```text
$ uvx pytest -q -p no:cacheprovider tests/
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom] [rc=0] [wall=364.46s]
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
894 passed, 5 skipped, 8103 subtests passed in 363.86s (0:06:03)

--- STDERR ---
```

### `VER-003b-root-pythonpath-zen-pytest` (`l2-green-ver003b-zen-pythonpath.log`, `sha256=46e628bad80414edfeec36bc5ff63c6d1c187541e9a0fb4fc7a60e6da0c9cf9b`)
```text
$ uvx pytest -q -p no:cacheprovider bridges/opencode-zen-bridge/tests/
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom] [rc=0] [wall=315.42s]
--- STDOUT ---
......................... [  5%]
............................................................................................................................................ [ 34%]
............................................................................................................ [ 56%]
................................................................. [ 70%]
....................................................................................................................................... [ 98%]
.......                                                              [100%]
480 passed, 3275 subtests passed in 315.19s (0:05:15)

--- STDERR ---
```

### `VER-005-dedicated-realtime-suite` (`l2-green-ver005-dedicated.log`, `sha256=77dd6e9374c1df5dc9e15dc9a69e0abe07521cf02e1b2a77741ec912e9d3aff1`)
```text
$ uvx pytest -q -p no:cacheprovider tests/test_realtime_reasoning.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=236.79s]
--- STDOUT ---
................................................................................................ [ 95%]
.....                                                                    [100%]
101 passed, 120 subtests passed in 236.29s (0:03:56)

--- STDERR ---
```

### `AC-023-pytest-reversed` (`l2-green-ac023-reversed.log`, `sha256=888434ac796a70cfff73e2fb3ebbb32c1c74d392031b19e09ebb15b868b1fd3a`)
```text
$ uvx pytest -q -p no:cacheprovider tests/test_zen_catalog.py tests/test_tool_emulation.py tests/test_sync_yaml.py tests/test_stream_thinking.py tests/test_step_interruption.py tests/test_stdin_prompt.py tests/test_run_env.py tests/test_realtime_reasoning.py tests/test_native_fallback.py tests/test_lenient_tool_call.py tests/test_google_direct.py tests/test_go_model_routing.py tests/test_effort_mapping.py tests/test_cli_failure.py tests/test_catalog_reload.py tests/test_catalog_mode.py tests/test_catalog.py tests/test_aliases.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=331.05s]
--- STDOUT ---
.................................................................. [ 13%]
................................................................. [ 27%]
................................................................. [ 40%]
.................................................................... [ 55%]
............................................... [ 64%]
................................................................ [ 78%]
........................ [ 83%]
................................................. [ 93%]
............................ [ 99%]
....                                                              [100%]
480 passed, 3275 subtests passed in 330.75s (0:05:30)

--- STDERR ---
```

ARTIFACT_END>>>
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/verification-traceability.md sha256=57991993d6fc6bedba294fd256dc8e4869ad2e96f864ca0a99e472f6df7c1f21
# Матрица прослеживаемости приёмки (`verification-traceability.md`, run `analyst-teamlead-zen-realtime-reasoning-20261025`, cycle `9`)

## Служебные отметки контура `teamlead-gate`
- **Режим ревью:** `reviewer_skip=true`, `downstream_panel=true`, `parent_skill="analyst-teamlead"` (отдельный `Reviewer` не запускается; Совет Тимлидов — единственный рубеж построчного и приёмочного ревью по `acceptance-package.md` §1; счётчик «замечаний совета сверх Reviewer» при `downstream_panel=true` не определён).
- **Назначение шапки тимлида (`council.md` §1):** дословная шапка тимлида прикреплена сразу после системного промпта роли (`prompt-{skeptic,realist,visionary}.txt`) и до факт-карты во всех 3 брифах Совета Тимлидов.
- **Побайтовая неизменность замороженных функций (`Run-Path Freeze` / `REQ-018`):**
  - `def _run_env`: `sha256=1c51b28fcb83fcc0f4d8b5204c858e11ab5ac975bfe40dca4a0bf61978008e31` (ожидалось `1c51b28fcb83fcc0f4d8b5204c858e11ab5ac975bfe40dca4a0bf61978008e31` — **MATCH**)
  - `def _stream_google_sse` и `def _execute_google_once`: `google_direct_unchanged=True` (**MATCH**)
  - Белый список изменённых файлов: `bridges/opencode-zen-bridge/server.py, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py, bridges/opencode-zen-bridge/tests/test_step_interruption.py` (ровно 3 целевых файла `coder_target_files`).

## Сводка `acceptance_coverage` из `coder.json`
- {"id": "RW-001", "status": "PASS", "test": "test_c8_fu001_multiple_native_tool_calls_same_step_preserved_next_step_excluded; test_c9_rw001_idless_and_unconfirmed_native_step", "evidence": "~/work/cli-agent-bridge/coder-12-20261027/full-pytest-final2.log"}
- {"id": "RW-002", "status": "PASS", "test": "test_c8_fu002_legacy_spawn_rechecks_cancel_and_deadline_after_reservation", "evidence": "~/work/cli-agent-bridge/coder-12-20261027/full-pytest-final2.log"}
- {"id": "FU-001", "status": "PASS", "test": "test_c9_fu001_serve_queue_and_accumulated_byte_budget_enforced", "evidence": "~/work/cli-agent-bridge/coder-12-20261027/full-pytest-final2.log"}
- {"id": "FU-002", "status": "PASS", "test": "unittest discover: 480 OK; origin/dev collect: 101 rc=0", "evidence": "~/work/cli-agent-bridge/coder-12-20261027/full-pytest-final2.log"}

## Поштучная матрица `REQ-001..REQ-020` и `AC-001..AC-026`

| Требование / AC | Реализация в коде | Автотесты / Оракулы | Свидетельство L2 / L3 | Статус |
|---|---|---|---|---|
| `REQ-001` / `AC-001`, `AC-002`, `REQ-020` / `AC-026` (реалтайм-стриминг дельт `reasoning_content` и `content` `<=250 мс`, Red→Green на сокете при идущем апстриме без падения в `setUp` на `origin/dev`) | `bridges/opencode-zen-bridge/server.py` (потоковый `opencode serve` SSE клиент, прямая запись `message.part.delta` в SSE сокет) | `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py` (`test_ac026_realtime_chunks_before_upstream_end`) | `L2-RED-sensitivity` (`rc=1` на `origin/dev`) + `VER-001-pytest` (`rc=0` на кандидате) | `PASS` |
| `REQ-002` / `AC-003` (неизменность публичного HTTP/OpenAI SSE контракта `/health`, `/v1/models`, `/v1/chat/completions`, `:9883`) | `bridges/opencode-zen-bridge/server.py` | `tests/test_realtime_reasoning.py` | `VER-001-pytest`, `VER-002-unittest` (`rc=0`) | `PASS` |
| `REQ-003` / `AC-004` (kill-switch `REALTIME_SERVE_ENABLED` в `dynamic_config.json`, дефолт `false`, сохранение `opencode run --format json` и `disable-serve`) | `bridges/opencode-zen-bridge/server.py` (`DYNAMIC_CONFIG_PATH`, `_ServeHealth`, fallback decision table) | `tests/test_realtime_reasoning.py`, полный существующий набор `tests/` | `VER-001-pytest` (`rc=0`) | `PASS` |
| `REQ-004`, `REQ-005` / `AC-005`, `AC-006`, `AC-007` (первая реакция `< 1.0 с` с префиксом `[мост]` и `
`, ведущий `
` после незавершённой дельты, отсутствие `[мост]` в `_messages_to_prompt`) | `bridges/opencode-zen-bridge/server.py` | `tests/test_realtime_reasoning.py` (`test_c5_rw002_limiter_delay_half_second_still_emits_first_status_under_1s`) | `VER-001-pytest` (`rc=0`) | `PASS` |
| `REQ-006`, `REQ-007` / `AC-008`, `AC-009`, `AC-010` (раздельные watchdogs `first_event_timeout`, `first_token_timeout`, `stall_timeout` с env-порогами в SSE и non-stream JSON `Run.execute` без классификации как `provider_fatal`) | `bridges/opencode-zen-bridge/server.py` | `tests/test_realtime_reasoning.py` (`test_c7_rw001_nonstream_json_watchdog_retries_and_preserves_exit_reason`, `test_c7_rw003_legacy_sse_watchdog_classified_as_transient_in_attempt_done`, `test_c6_rw002_legacy_first_token_timeout_respects_configured_value_under_120s`, `test_c6_rw003_nonstream_json_run_execute_enforces_phase_watchdogs`) | `VER-001-pytest` (`rc=0`) | `PASS` |
| `REQ-008` / `AC-011`, `AC-012` (группа процессов `--serve-helper` + `opencode serve`, ранний дренаж `stderr`, фазовые потолки `_serve_http`, прерываемое ожидание в `_StartupGate`/`_SpawnRateLimiter` по `deadline`/`is_client_gone`, детекция закрытия сокета `<= 5 с`, `0` сирот `<= 7 с` включая `skip_body=True` на капающем `interrupt`/`DELETE`) | `bridges/opencode-zen-bridge/server.py` | `tests/test_realtime_reasoning.py` (`test_c8_fu002_startup_gate_and_spawn_limiter_abort_on_deadline_and_client_gone`, `test_c7_rw004_startup_http_phases_enforce_phase_deadlines_on_dripping_headers`, `test_c6_rw005_spawn_serve_respects_deadline_and_client_disconnect_without_run_fallback`, `test_c6_rw006_spawn_serve_drains_multi_mib_stderr_before_bind_without_deadlock`, `test_c6_rw007_fu003_dripping_interrupt_delete_still_cleans_up_under_7s`) | `VER-001-pytest` (`rc=0`) | `PASS` |
| `REQ-009` / `AC-013`, `AC-014` (`MAX_TOTAL_SPAWNS=3`, `FAIL_RETRY_LIMIT`, `_RetryBudget`, разделение `_has_model_output` и `_delivered_err` при раннем 429/503 после `session.execution.started`, перехват `first_event_timeout` внутри `prompt_async` с ретраем на `serve` без нелегального фолбэка на `run`, нейтральный локальный `timeout` без ложного инкремента CB, барьер доставки `headers_at` и `first_event_at` против фолбэка на `run`, Full Jitter, Circuit Breaker, разделитель `[мост]`) | `bridges/opencode-zen-bridge/server.py` | `tests/test_realtime_reasoning.py` (`test_c9_rw002_first_event_timeout_in_prompt_async_retries_without_run_fallback`, `test_c8_rw001_early_execution_failed_429_503_before_tokens_retries_on_serve_without_run_fallback`, `test_c8_rw003_local_request_deadline_timeout_does_not_increment_cb_or_retry`, `test_c7_rw002_first_event_before_prompt_headers_closes_delivery_barrier`, `test_c6_rw001_headers_at_blocks_run_fallback_on_sse_error_and_timeout`, `test_c5_rw001_prompt_headers_then_body_error_or_429_blocks_run_fallback`), `tests/test_step_interruption.py` | `VER-001-pytest` (`rc=0`) | `PASS` |
| `REQ-010`, `REQ-011`, `REQ-012` / `AC-015`, `AC-016`, `AC-017` (инкрементальный `ToolCallParser`, `finish_reason="tool_calls"`, полная матрица `STEP_RECOVERY` на `serve` и `run`, сравнительный `unmapped recovery` `serve` против `run`, `deny` для встроенных инструментов, `form.created` `safety_order` `cancel+interrupt`, валидация суррогатов `_combine_surrogates` -> `ServeProtocolError`) | `bridges/opencode-zen-bridge/server.py` | `tests/test_realtime_reasoning.py` (`test_c8_rw002_unpaired_surrogate_raises_serve_protocol_error_while_valid_pair_passes`, `test_c6_rw004_ac016_serve_step_interruption_matrix`, `test_c6_rw004_ac017_unmapped_recovery_serve_vs_run_equivalence`), `tests/test_step_interruption.py` | `VER-001-pytest` (`rc=0`) | `PASS` |
| `REQ-013`, `REQ-014`, `REQ-015`, `REQ-016` / `AC-018`, `AC-019`, `AC-020`, `AC-021` (ротация прокси, строгая валидация `usage`, сохранение `_SSEByteCapReader` и передача остатка буфера в окне `_drain_serve_step_usage` с добором нативных вызовов инструментов того же `assistantMessageID`, лимиты байт SSE-строки и HTTP-тела, маскирование пароля serve и секретов, `O-EXIT/v1` с `transport`, `first_event_ms`, `ttft_ms`) | `bridges/opencode-zen-bridge/server.py` (`_serve_env`, `OPENCODE_DB=":memory:"`, `O-EXIT/v1`) | `tests/test_realtime_reasoning.py` (`test_c9_rw001_drain_serve_step_usage_preserves_sse_line_and_body_byte_caps_with_tail_buffer`, `test_c8_fu001_drain_serve_step_usage_collects_additional_same_message_native_tool_calls`, `test_c7_fu001_native_tool_call_drains_step_ended_for_usage`, `test_c6_fu001_fu002_sse_line_body_byte_caps_and_strict_usage_ints`, `test_c6_fu001_oversized_sse_line_is_terminal_invalid_event`), `tests/test_run_env.py` | `VER-001-pytest` (`rc=0`) | `PASS` |
| `REQ-017` / `AC-022`, `AC-023` (приведение базовой линии `test_step_interruption.py` в зелёное при `MAX_TOTAL_SPAWNS=3`, независимость от порядка запуска тестов) | `bridges/opencode-zen-bridge/tests/test_step_interruption.py` | `VER-001-pytest`, `VER-002-unittest`, `VER-003-root-pythonpath-pytest`, `AC-023-pytest-reversed` | Все 4 прогона `rc=0` в `execution-evidence.md` | `PASS` |
| `REQ-018` / `AC-024` (неизменность `_stream_google_sse` и `_execute_google_once`) | Не затронуты (побайтовый SHA-256 сверен в `code-gate.json`) | `tests/test_google_direct.py` | `VER-001-pytest` + `VER-004-packet-command` (`rc=0`) | `PASS` |
| `VER-004` (статический гейт `ruff==0.17.2`, диапазонный `ruff format --check`, `basedpyright==1.40.2`, `0` новых `Any`) | `bridges/opencode-zen-bridge/server.py`, `tests/test_realtime_reasoning.py`, `tests/test_step_interruption.py` | `VER-004-packet-command` и `VER-004-ruff-format-*` | `l2-green-ver004-packet.log` (`rc=0`) | `PASS` |
| `REQ-019` / `AC-025`, `VER-006`, `VER-007` (синхронизация `~/.dsh/bridges/opencode-zen-bridge/server.py` и живой heavy-path на `:9883`) | Выкатка `H0..H9` строго после `ACCEPT` Совета Тимлидов | Живой сценарий `:9883` + `diff -u` | `execution-evidence.md` (`VER-006`, `VER-007`) | `DEFERRED_L3 (до ACCEPT Совета Тимлидов)` |
ARTIFACT_END>>>
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/evidence-manifest.sha256 sha256=14ae9a18f8e525c5a557dd299d5c9271f69383c63e1848c360cf840ef15f152e
e67d5ffb98e29dd698e38e17e18772fa792391a2e24e05cf88d2f820a14e8722  teamlead/verification-surface.json
8e68e2d3661808a7577d5b97847f198be5f56523315cfcb1af9558d25ae31fa5  teamlead/environment-manifest.json
5ab1e19fc990dcaeeae92279874462dbfbb690346a48b7035211f75967d3f4d5  teamlead/execution-evidence.md
57991993d6fc6bedba294fd256dc8e4869ad2e96f864ca0a99e472f6df7c1f21  teamlead/verification-traceability.md
5a4fbc34f2af4de42ea77883c22872b098e2beb19d4f003b3800edcb5fb1a638  teamlead/reverse-spec.md
1690f47099a0a472c7662a90a0b2b70f486d0efba151e2583467f8049c110c16  teamlead/candidate-manifest.json
87abbc8e77587bdf7bcc61186c0aef08dacff391d6f8c25f0ba1b055d0abf5d7  teamlead/candidate.diff
27fcdd1e812d3ab14b7630f0ef40ae3d3261d08854d1f93d2c23c473bfa7c983  handoff/panel-rework-brief.json
44cf37780c26e30dbed87160a90955b78937e76b7c9dc4d1260abd8ad057a00d  coder.json
44cf37780c26e30dbed87160a90955b78937e76b7c9dc4d1260abd8ad057a00d  receipts/coder.json
3ab247906ff11f0c6c1597f1baa42d221eff582e434ae3a266849fc50ab91f1b  receipts/code-gate.json
86b45f365f47fb633cabb989e42087962197734ec1a9b3460cad54f1a827095c  receipts/verifier.json
cc44020597c494a46f99497fc8b5a2debf82ef8845714f977f9200f38567efdb  receipts/final-gate.json
888434ac796a70cfff73e2fb3ebbb32c1c74d392031b19e09ebb15b868b1fd3a  receipts/l2-green-ac023-reversed.log
7e25222aae48c184584c756136c9bd7feee1b106264b5367cabf3531771c7e91  receipts/l2-green-ver001-pytest.log
c54066270e8630333efd3cc212223dd1e57013d5d17f9cfa9876aae9c4c5e6bf  receipts/l2-green-ver002-unittest.log
3e44eeeae8fda071cfedc1bffd42d8509553c92ece5b9d412fb72f947912f1a4  receipts/l2-green-ver003-pythonpath.log
46e628bad80414edfeec36bc5ff63c6d1c187541e9a0fb4fc7a60e6da0c9cf9b  receipts/l2-green-ver003b-zen-pythonpath.log
c449413e9b822374c2af9357e3b4749006bcca0fdbe863aa1234609a3990a915  receipts/l2-green-ver004-packet.log
791491a5d9e6128b8400ae730e69e74c9af01651d625cc697d569dfdcee245b7  receipts/l2-green-ver004-ruff-format-new.log
77dd6e9374c1df5dc9e15dc9a69e0abe07521cf02e1b2a77741ec912e9d3aff1  receipts/l2-green-ver005-dedicated.log
b739aea60c973b1b2b560fb49f159cfcba0656dd21e2642fd835663a5840cb4a  receipts/l2-red.log
ARTIFACT_END>>>
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/reverse-spec.md sha256=5a4fbc34f2af4de42ea77883c22872b098e2beb19d4f003b3800edcb5fb1a638
# reverse-spec.md

Основание: только предоставленный diff и текст нового тестового модуля. Исходные файлы вне diff, постановка задачи и архитектурные материалы не использовались. Тесты не запускались; ниже описаны их проверки, а не подтверждённые результаты выполнения. Переданный SHA-256 нового модуля независимо не проверялся.

Документ приведён в ответе: запись файла недоступна в текущей среде.

## 1. Фактически изменённые и добавленные файлы

1. **Изменён `bridges/opencode-zen-bridge/server.py`.**

   Добавлен транспорт через отдельный `opencode serve` на каждую попытку запроса: запуск помощника, локальный HTTP/SSE, преобразование событий, обработка инструментов и интерактивных запросов, повторные попытки и fallback на прежний `opencode run`.

   Дополнительно изменены watchdog прежнего транспорта, остановка групп процессов, ожидание перед запуском, возврат резервов лимитера, дедупликация текста, очистка ошибок от секретов и структурное логирование. Значительная часть остальных строк diff — форматирование.

2. **Изменён `bridges/opencode-zen-bridge/tests/test_step_interruption.py`.**

   Обновлены ожидания с учётом общего потолка в три запуска. Добавлен сценарий «недоступный встроенный инструмент → незавершённый шаг → корректные вызовы инструментов». На каждый тест создаётся свежий `_Resilience`; переменные окружения изолируются через `mock.patch.dict`.

3. **Добавлен `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py`.**

   Добавлены локальные FakeServe/FakeCLI, проверки потоковой доставки, статусов, watchdog, fallback, инструментальных шагов, HTTP-дедлайнов, ограничений памяти и уборки процессов и ресурсов.

**Не показаны как добавленные или изменённые файлы:** `dynamic_config.json`, файл `disable-serve`, lease-файлы и временные каталоги состояния. Код обращается к ним либо создаёт их во время работы; это не дополнительные файлы кандидатного изменения.

## 2. Реконструируемое поведение системы

### 2.1. Новый транспорт и условия включения

К существующему `run` добавляется транспорт `serve`. Для одной serve-попытки мост запускает собственные helper и `opencode serve`, создаёт сессию, подписывается на события и отправляет prompt через локальный HTTP.

Выбор выполняется `_select_transport()` в следующем порядке:

1. `OPENCODE_ZEN_BRIDGE_TRANSPORT=run` всегда выбирает `run`.
2. Ложное значение `OPENCODE_ZEN_BRIDGE_REALTIME_SERVE_ENABLED` — `0`, `false`, `no`, `off` — выбирает `run`, включая принудительный режим `serve`.
3. Наличие disable-файла выбирает `run`. Путь задаётся `OPENCODE_ZEN_BRIDGE_SERVE_DISABLE_FILE`; по умолчанию — `~/.dsh/bridges/opencode-zen-bridge/disable-serve`. Ошибка проверки существования также ведёт к `run`.
4. `OPENCODE_ZEN_BRIDGE_TRANSPORT=serve` выбирает `serve`, обходя последующие проверки здоровья, положительного флага и типа бинаря.
5. Неизвестное значение транспорта выбирает `run`.
6. Для `auto` учитывается sticky-деградация serve.
7. В `auto` включение требует истинного env override либо boolean `REALTIME_SERVE_ENABLED: true` в `dynamic_config.json`.
8. Дополнительно `auto` требует бинарь, распознанный как нативный Mach-O/ELF. Скрипт со shebang не допускается; тестовый `SERVE_TEST_ELIGIBLE=True` обходит проверку.

Значение транспорта по умолчанию — `auto`. Если конфигурация отсутствует, повреждена, содержит неправильный тип флага или флаг выключен, используется `run`.

`dynamic_config.json` расположен рядом с `server.py`. Чтение кэшируется по пути, `mtime_ns` и размеру файла. Последующие выборы транспорта могут увидеть изменение без перезапуска сервера. Это **локальная файловая конфигурация**; обращения к удалённому сервису фичефлагов в diff нет.

Kill-switch влияет на последующий выбор транспорта. Код не показывает прерывания уже выполняющейся serve-попытки при изменении файла или флага.

Для прямых Google-маршрутов новый транспорт не выбирается: они сохраняют свой HTTP-путь.

### 2.2. Последовательность serve-попытки

Основной порядок:

1. Проверить отмену клиента и общий deadline.
2. Подготовить санитизированное окружение и временный каталог состояния.
3. Выделить локальный порт.
4. Запустить helper, получить handshake и проверить владельца слушающего порта.
5. Проверить готовность через `GET /api/session/active`.
6. Создать сессию через `POST /api/session`, передав рабочий каталог, модель, необязательный variant и permission policy.
7. Открыть `GET /api/event`.
8. Освободить startup gate после подготовки подписки.
9. Параллельно читать SSE и отправлять prompt.
10. Обработать завершение, ошибку, watchdog либо отмену.
11. Выполнить обязательную уборку попытки.

Prompt передаётся как:

```json
{
  "text": "<prompt>",
  "files": [],
  "delivery": "steer",
  "resume": true
}
```

Постоянный общий `opencode serve` между запросами этим кодом не создаётся.

### 2.3. Потоковая передача событий

Serve-события преобразуются к внутренним событиям существующего пути:

- `session.reasoning.delta` → `reasoning_content`;
- `session.text.delta` → `content`;
- `session.step.ended` → `step_finish` с usage;
- `session.execution.failed` и `session.step.failed` → ошибка;
- `session.tool.*` → события жизненного цикла native-инструмента;
- `permission.asked` → обработка разрешения;
- `form.created` → обработка интерактивной формы.

Reasoning и текст выдаются через callbacks по мере чтения, без ожидания полного ответа.

Для reasoning/text требуются строковая дельта и непустой `sessionID`. Пробельные дельты маппер сохраняет. Суррогатные пары UTF-16 объединяются; непарные суррогаты приводят к `ServeProtocolError`.

События с явно чужим `sessionID` отбрасываются. Служебные `server.connected` и heartbeat не считаются первым событием выполнения. При этом проверка session принадлежности не одинакова для всех типов: некоторые события без `sessionID` допускаются.

В потоковом ответе сохраняется существующий механизм:

- начальный assistant-чанк;
- дельты `reasoning_content`, `content`, `tool_calls`;
- финальный чанк с `finish_reason` и usage;
- `data: [DONE]`.

При ошибке отправляется OpenAI-style объект `error` и `[DONE]`, без успешного `finish_reason`.

#### Usage

Из `session.step.ended.data.tokens` используются:

- `input`;
- `output`;
- `reasoning`;
- `cache.read` как `cached`.

`cache.write` в итоговый usage не включается.

`input`, `output`, `reasoning` должны быть неотрицательными целыми, исключая `bool`. Отсутствующий `cache.read` допускается и далее учитывается как ноль.

Usage нескольких serve-попыток суммируется, в том числе для ряда неуспешных попыток. Повторные завершения шага дедуплицируются по `assistantMessageID`, когда он присутствует. При отсутствии ID такой дедупликации нет.

Если итоговые input/output равны нулю или отсутствуют, внешний ответ использует оценку токенов по prompt и тексту. Поэтому явный upstream-ноль также может заменяться оценкой.

#### Синтетические статусы `[мост]`

При включённом thinking статусы отправляются отдельными `reasoning_content`-дельтами:

- `[мост] Подключение к модели…`
- `[мост] Ожидание первого токена…`
- `[мост] Ожидание продолжения…`
- `[мост] Повтор попытки N/M…`

Начальный защитный таймер настроен на 0,65 с. Быстрый модельный вывод подавляет его через `first_visible`.

До первого токена последующие статусы планируются с интервалом 5 с. После начала вывода статус ожидания продолжения появляется при паузе от 15 с.

Каждая статусная строка заканчивается LF. После reasoning модели без завершающего LF статус получает ведущий перевод строки.

Статусы:

- не входят в `content`;
- не добавляются к модельному usage;
- не должны возвращаться в prompt из истории: существующий `_messages_to_prompt` не включает `reasoning_content`;
- не считаются доставкой модельного запроса для запрета fallback.

В non-stream JSON синтетические статусы не собираются.

При effort `""`, `off`, `none` синтетические статусы отключаются. Этот переключатель сам по себе не запрещает пересылку reasoning, уже полученного от модели.

Записи основного потока и таймера сериализуются через `_LockedWfile`; при завершении запроса таймер отменяется.

### 2.4. Процессы, группы, порты и lease

#### Дерево процессов

Мост запускает собственный файл:

```text
python -I server.py --serve-helper
  <attempt_id> <port> <opencode_bin> <lease_dir> <parent_pid> <parent_lstart>
```

Helper стартует с `start_new_session=True` и становится лидером группы. Он запускает:

```text
<opencode_bin> serve --hostname 127.0.0.1 --port <port>
```

Serve наследует группу helper; его потомки также могут входить в неё.

Helper использует stdin как lifeline. Закрытие канала, SIGTERM или завершение serve инициируют уборку группы. Реализация трактует готовность lifeline к чтению как сигнал остановки, не читая содержимое канала.

Ранний helper-режим отделён от обычной инициализации моста и импорта `zen_catalog`.

#### Порты и проверка владения

Порты перебираются от `20000 + pid % 20000` до 59999. Перед выбором выполняется пробный bind на `127.0.0.1`; внутри процесса выделенные порты учитываются под замком.

После handshake мост проверяет через `lsof`, что:

- слушатель имеет PID запущенного serve;
- PGID слушателя совпадает с PID helper;
- helper ещё жив.

Чужой слушатель приводит к отказу serve-попытки и уборке собственных ресурсов.

Пробный сокет закрывается до старта serve, поэтому непрерывного резервирования порта нет. Последующая проверка владельца обнаруживает подмену, но не исключает гонку bind.

#### Lease

По умолчанию lease располагаются в `/tmp/opencode-zen-bridge-leases`.

Каталог проверяется на владельца и отсутствие симлинка; устанавливаются права `0700`. Lease атомарно публикуется через временный файл и `os.replace`.

Он содержит UID, идентификатор попытки, PID и время старта родителя/helper, PGID, порт, фазу, затем PID и время старта serve.

Фаза `ready` в lease означает, что serve запущен. Проверка его слушающего порта выполняется отдельно мостом.

При старте моста `_startup_reaper()` обрабатывает lease мёртвых родителей. Используются проверки владельца файлов, симлинков, времени старта PID и признака `--serve-helper` в команде процесса. Удаление lease производится после исчезновения соответствующей группы.

#### Остановка и уборка

`_ServeLease.cleanup()` идемпотентен:

1. Закрывает lifeline.
2. Отправляет SIGTERM своей группе.
3. Ждёт до 4 с.
4. При необходимости отправляет SIGKILL.
5. Отдельно подтверждает исчезновение группы до 2 с.
6. Закрывает пайпы.
7. После смерти группы удаляет lease и освобождает запись о порте.
8. Удаляет временный каталог состояния.

Перед этим `_cleanup_serve_attempt()` останавливает reader, закрывает SSE-соединение, кратко ожидает потоки и пробует выполнить interrupt/delete сессии. На этот этап выделен общий бюджет около 0,45 с; cleanup HTTP не вычитывает тело ответа.

Helper имеет собственный механизм TERM/KILL и учитывает оставшихся членов группы даже после завершения непосредственного serve-процесса.

Прежний `_stop_proc()` также изменён: завершившийся лидер больше не является основанием оставить живых потомков его группы.

#### Дренаж вывода

Helper дренирует stdout и stderr serve, передавая их в свой stderr. Мост читает stderr helper порциями по 4096 байт и хранит хвост до 16 КиБ.

Общий `_drain_stderr()` теперь ограничивает список 64 строками. Это ограничение по числу строк, а не по суммарному размеру байтов.

### 2.5. Дедлайны и watchdog

Добавлены фазовые пороги:

- `OPENCODE_ZEN_BRIDGE_FIRST_EVENT_TIMEOUT_S`: по умолчанию 20 с;
- `OPENCODE_ZEN_BRIDGE_FIRST_TOKEN_TIMEOUT_S`: 60 с;
- `OPENCODE_ZEN_BRIDGE_STALL_TIMEOUT_S`: 60 с.

Сохраняется общий `TIMEOUT_S`, по умолчанию 1800 с. Повторы используют общий бюджет запроса.

Для serve:

- `first_event_timeout` — нет подходящего execution-события после отправки prompt;
- `first_token_timeout` — execution начался, но нет первого reasoning/text/native-вызова;
- `stall_timeout` — после первого токена прекратилось полезное продвижение.

Native tool input delta обновляет время последней активности; завершённый native-вызов также может установить время первого токена.

Отдельные startup-окна предусмотрены для handshake, появления слушателя, readiness и создания сессии — порядка 3 с на фазу. Подписка ограничивается `FIRST_EVENT_TIMEOUT_S` и общим deadline.

HTTP имеет абсолютный deadline поверх socket timeout. Отдельный watcher закрывает сокет при истечении срока или уходе клиента, включая случай постоянно поступающих отдельных байтов заголовков/тела.

Startup gate и spawn limiter проверяют отмену и deadline во время ожидания. Перед запуском выполняется повторная проверка; если запуск отменён после резерва лимитера, резерв возвращается.

В legacy `_StdoutFeed` watchdog вызывается не только при пустой очереди, но и при поступлении строк: служебный поток не должен бесконечно откладывать фазовый таймаут.

Для non-stream `Run` дополнительно отслеживается native `task` в `pending/running`: пока такой task активен, token-stall не применяется. Общий deadline сохраняется. Аналогичного исключения в показанном legacy SSE-коде нет.

### 2.6. Инструментальные и интерактивные события

#### Permissions и формы

По умолчанию `OPENCODE_ZEN_BRIDGE_SERVE_PERMISSION_POLICY=ask_reject` преобразуется в `ask`. Значение `deny` поддерживается отдельно; неизвестная политика вызывает `ServeSecurityError`.

Permission policy передаётся и через `OPENCODE_CONFIG_CONTENT`, и при создании сессии.

В основном цикле:

- `permission.asked` → `decision: reject`, затем interrupt;
- reasoning/text закрытого шага после этого не выдаются;
- native-события продолжают обрабатываться, чтобы вернуть вызов инструмента внешнему исполнителю.

Для `form.created` своей сессии выполняются cancel формы и interrupt **до проверки title/fields**. Успешная отмена даёт terminal `cancelled`, который внешние обработчики превращают в ошибку. Форма своей сессии без ID и неуспешные control-ответы приводят к fail-closed.

Таким образом, мост не предоставляет интерактивного диалога подтверждения пользователю.

#### Native tools и текстовые вызовы

`_ServeToolState` хранит по call ID имя инструмента и аргументы:

- готовый объект `input`;
- либо JSON из полного `text`, например `session.tool.input.ended`.

Повторная выдача одного native call ID в рамках попытки подавляется.

Адаптер `_native_call_as_dsh()` использует существующий `_native_to_tool_calls()`, включая нормализацию аргументов и раскрытие `multiedit`.

При эмуляции native-вызов либо текстовый `<tool_call>`/`<tool_invoke>` преобразуется в OpenAI `tool_calls`. Внешний call получает сгенерированный ID, function name и JSON-строку arguments.

После первого готового native-вызова при эмуляции мост дочитывает текущий шаг до `session.step.ended` в окне до 1 с:

- сохраняет остальные вызовы того же шага;
- получает usage;
- отбрасывает явно чужую сессию и несовпадающий известный `assistantMessageID`;
- требует подтверждённого конца шага.

EOF или истечение окна без `step.ended` дают протокольную ошибку, а не успешный `finish_reason=tool_calls`.

Одинаковые внешние вызовы дедуплицируются по имени и аргументам. Текстовые вызовы проходят существующий `ToolCallParser`, включая теги, разрезанные между дельтами.

### 2.7. Ошибки, повторы и fallback

#### Барьер доставки

Fallback с serve на run разрешается только в автоматическом режиме до барьера доставки.

Для этого барьера достаточно:

- получения HTTP-заголовков ответа на prompt;
- валидного execution-события;
- reasoning, текста либо native-вызова.

Это внутренний барьер принятия/выполнения запроса, а не только факт отправки видимого текста клиенту. Для JSON он также действует до выдачи итогового HTTP-ответа.

Барьер монотонен на весь запрос: следующий неудачный serve-повтор не открывает fallback заново. Синтетический статус барьер не устанавливает.

#### Классификация

- Локальные startup/setup-отказы до барьера допускают fallback на `run` в `auto`.
- Такие же отказы при принудительном `serve` заканчиваются ошибкой.
- HTTP 401/403 и 400/404/422 на обрабатываемых serve endpoints дают fail-closed без fallback.
- Prompt HTTP 429/5xx учитываются как upstream-отказы и могут повторяться через serve. Полученные заголовки запрещают fallback.
- Протокольные ошибки, EOF без terminal и отсутствие execution после доставки допускают serve-retry в пределах бюджетов.
- Модельная тишина и stall учитываются upstream breaker.
- Отмена клиента и общий deadline не считаются успехом и не должны увеличивать счётчик upstream-отказов.

Есть два отдельных механизма здоровья:

- `_ServeHealth`: после трёх накопленных отказов включает деградацию на 120 с; успешная serve-попытка сбрасывает её. В `auto` деградация выбирает `run`.
- Существующий `_UpstreamBreaker`: защищает модельную зависимость и учитывает транзиентные upstream-отказы.

`FALLBACK_DECISION_TABLE` описывает ожидаемую классификацию, но не исполняет её: фактическое поведение задаётся ветвлениями обработчиков.

#### Общие бюджеты и recovery

Serve и последующий run используют общий `_RequestAttempts`, deadline и потолок запусков. По умолчанию потолок — три. Helper и serve считаются одной serve-попыткой; счётчик увеличивается до её фактического запуска, поэтому и отказ подготовки может израсходовать позицию.

Сохраняются process-level retry budget, spawn limiter и Full Jitter backoff.

Recovery применяется к:

- транзиентным ошибкам;
- незавершённому инструментальному шагу;
- встроенному инструменту без доступного DSH-аналога.

Recovery prompt сохраняет `tool_choice`, включая `required` и конкретное имя функции. Используется существующий kill-switch `OPENCODE_ZEN_BRIDGE_STEP_RECOVERY`.

Повторяющийся префикс текста подавляется, переформулированный текст сохраняется. Reasoning между попытками целиком не дедуплицируется. Потоковый serve-путь отдельно фильтрует interruption-маркеры, разрезанные между дельтами.

## 3. Внешние контракты и инварианты

### 3.1. Публичный OpenAI-совместимый API

Новые публичные HTTP-маршруты в diff не добавлены.

**`/health`:** структура показанного ответа сохранена. В частности, `transport` продолжает возвращать `"opencode-zen-cli"` независимо от выбора serve. Здоровье serve и выбранный для конкретного запроса транспорт через этот endpoint не раскрываются.

**`/v1/models` и `/models`:** показанная структура списка моделей сохранена. Изменения этой части преимущественно форматные.

**`/v1/chat/completions`:** запросы обслуживаются прежним endpoint; новый транспорт выбирается внутри. Сохраняются stream/non-stream, reasoning, эмуляция инструментов и внешний идентификатор модели.

**SSE:** используется прежний `format_sse_chunk`; новых обязательных полей чанка не видно. Однако наблюдаемое поведение изменилось:

- `reasoning_content` может содержать синтетические `[мост]`-статусы;
- фазовые watchdog могут завершать запрос раньше общего таймаута;
- ошибки serve выдаются через существующий SSE error-механизм;
- поток может содержать разделители повторных попыток.

Следовательно, форма API сохраняется, но содержимое и временное поведение потока расширяются.

### 3.2. Новый внутренний HTTP/SSE-контракт

Локальный serve слушает только `127.0.0.1`. Обращения выполняются через `http.client`, без HTTP-прокси.

Используется Basic authentication:

```text
Authorization: Basic base64("opencode:<случайный пароль>")
```

Пароль создаётся для попытки и передаётся через `OPENCODE_SERVER_PASSWORD`.

Задействованы endpoints:

- `GET /api/session/active`;
- `POST /api/session`;
- `GET /api/event`;
- `POST /api/session/{session_id}/prompt`;
- `POST /api/session/{session_id}/permission/{request_id}/reply`;
- `POST /api/session/{session_id}/form/{form_id}/cancel`;
- `POST /api/session/{session_id}/interrupt`;
- `DELETE /api/session/{session_id}`.

Маппер ориентирован на wire-события, обозначенные в коде как serve v2.1.2. Проверки фактической версии или предварительного согласования capabilities перед запросом не показаны.

SSE-reader ожидает JSON-объект на отдельной строке `data:`. Многострочная сборка стандартного SSE-поля `data` не реализована; `[DONE]` игнорируется, а завершение определяется событиями исполнения.

### 3.3. CLI, env и ресурсные ограничения

Добавлен внутренний CLI-режим `--serve-helper` с шестью позиционными аргументами.

Добавлены настройки:

- `OPENCODE_ZEN_BRIDGE_TRANSPORT`;
- `OPENCODE_ZEN_BRIDGE_REALTIME_SERVE_ENABLED`;
- `OPENCODE_ZEN_BRIDGE_SERVE_DISABLE_FILE`;
- `OPENCODE_ZEN_BRIDGE_SERVE_PERMISSION_POLICY`;
- `OPENCODE_ZEN_BRIDGE_FIRST_EVENT_TIMEOUT_S`;
- `OPENCODE_ZEN_BRIDGE_FIRST_TOKEN_TIMEOUT_S`;
- `OPENCODE_ZEN_BRIDGE_STALL_TIMEOUT_S`.

Serve-окружение строится через отдельный allowlist. Произвольные переменные и `OPENCODE_BIN` не передаются. Добавляются:

- отдельные `XDG_STATE_HOME` и `TMPDIR`;
- `OPENCODE_DB=:memory:`;
- случайный server password;
- принудительная permission policy.

Сохранение `HOME`, `XDG_DATA_HOME` и config-путей означает, что allowlist окружения сам по себе не изолирует serve от всех пользовательских файлов конфигурации и данных.

Ограничения serve-пути:

- одна SSE-строка — до 1 МиБ;
- очередь — до 4096 событий и 16 МиБ учтённых wire-байтов;
- накопленные reasoning/text — до 16 МиБ UTF-8;
- HTTP response body — до 8 МиБ.

Превышения классифицируются как протокольные ошибки.

Общий конструктор ошибок теперь очищает message и detail. Маскирование расширено на Bearer-токены, `OPENCODE_SERVER_PASSWORD` и credentials в proxy URL.

`O-EXIT/v1` дополнен `transport`, `transport_history`, `first_event_ms`, `ttft_ms`. Это контракт логирования, не публичного API.

### 3.4. Сохранённые маршруты и функции

По предоставленному материалу:

- прямой Google-путь обходит новый serve;
- `_run_env`, `_stream_google_sse`, `_execute_google_once` не изменены; новый тест закрепляет их SHA-256;
- `_google_request` подвергнут форматированию без видимой смены алгоритма;
- публичная аутентификация не получает новой схемы;
- канонический `_native_to_tool_calls` используется повторно;
- существующие парсер tool-тегов, построение recovery prompt, bulkhead, breaker и retry budget сохраняются и включаются в новый путь.

Это утверждение о показанных изменениях; неизменность всех остальных частей репозитория не проверялась.

## 4. Покрытие тестами и граничные случаи

### 4.1. Обновлённые тесты interruption recovery

`test_step_interruption.py` проверяет:

- общий предел в три запуска вместо прежнего ожидания четырёх;
- завершение обычным `stop`, если успешный инструментальный ответ потребовал бы четвёртого запуска;
- отсутствие дублирующейся преамбулы;
- успешную цепочку `unmapped → incomplete → tool_calls`, укладывающуюся в три запуска;
- изоляцию retry budget между тестами;
- восстановление исходного окружения после теста.

### 4.2. Legacy watchdog и статусы

Новый модуль содержит проверки:

- быстрый ответ без `[мост]` и с точными модельными строками;
- начальный статус не позднее 1 с при медленном CLI;
- такой же статус во время ожидания startup gate и задержанного лимитера;
- отсутствие повторного начального статуса;
- один retry-разделитель для watchdog/unmapped/incomplete при thinking и отсутствие разделителя при `off`;
- исключение `reasoning_content` истории из prompt;
- наличие новых полей `O-EXIT`;
- три фазовых watchdog в non-stream JSON: остановка CLI, повтор и успешный ответ;
- исчерпание попыток с 502 и сохранением конкретной фазы;
- корректные `first_event_ms` и `ttft_ms` для наступивших фаз;
- учёт watchdog-отказов legacy SSE в breaker до состояния OPEN;
- исключение активного native task из stall-проверки non-stream `Run`;
- отсутствие запуска после отмены/deadline, возврат резерва и освобождение gate/слота.

### 4.3. Serve streaming, usage и инструменты

FakeServe проверяет:

- доставку пяти reasoning-дельт до завершения upstream;
- задержку каждой дельты относительно отправки менее 0,25 с;
- сохранность их объединённого текста;
- сохранение SSE при паузе 1,4 с;
- синтетический начальный статус и отсутствие его дубля;
- канонический маппинг событий и usage;
- текстовый tool-вызов, разрезанный между дельтами;
- native-вызов после отклонённого permission;
- несколько native-вызовов одного шага, подавление повторного call ID и исключение явно следующего шага;
- usage именно закрываемого инструментального шага;
- работу при отсутствующем либо унаследованном `assistantMessageID`;
- ошибку при EOF или истечении окна без `step.ended`;
- дедупликацию одинакового вызова из native и текстового представления;
- эквивалентность результатов некоторых recovery-сценариев через serve/run и SSE/JSON;
- сохранение `tool_choice` в recovery prompt;
- однократное суммирование usage из разных ветвей повторов;
- один сдвиг proxy pool на serve-попытку.

### 4.4. Fallback и классификация ошибок

Есть проверки:

- startup/create 503 → fallback на run в `auto`;
- sticky-деградации после трёх таких запросов;
- запрета run после execution-start, даже без prompt headers;
- запрета run после prompt headers при RST тела, 429 и 503;
- сохранения барьера между повторными попытками;
- serve-retry после раннего транзиентного execution error;
- fail-closed для HTTP 400/404/422;
- ранней классификации 401 при зависшем теле;
- нейтральности общего deadline и отмены для breaker;
- отсутствия успешного учёта timeout/client_gone/cancelled;
- общего spawn cap для serve и fallback run;
- отказа без утечки портов при ENOSPC;
- очистки секретов в SSE, JSON и логах.

### 4.5. Процессы, HTTP и fault injection

Покрыты:

- ошибки `Popen` и `os.pipe` без оставшихся FD, портов и state-каталогов;
- отмена до запуска и во время handshake;
- отказ при чужом слушателе;
- базовый reaper для lease живого/мёртвого родителя;
- FIN, RST и закрытый `rfile`;
- дренаж stderr свыше 64 КиБ и 2 МиБ без LF;
- SIGKILL для группы, игнорирующей SIGTERM;
- остановка потомка после завершения лидера;
- уборка helper после выхода serve с живым внуком;
- обработка недоступного stdin helper без `NameError`;
- абсолютные deadlines при капающих HTTP-заголовках и телах;
- ограничение startup HTTP собственной фазой при длинном общем deadline;
- cleanup без ожидания тела;
- смерть группы менее чем за 7 с в проверяемых сценариях отмены;
- ограничения SSE-строки, HTTP body, очереди и накопленного текста;
- отклонение отрицательных и boolean token counts;
- непарные суррогаты и сохранение корректной пары emoji.

### 4.6. Видимые пробелы и риски

1. **Нет подтверждения на реальном opencode/provider.** Основные интеграционные проверки используют локальные фейки, часть — подмену `_serve_one_attempt`. Совместимость с живым бинарём, его permission policy и wire-протоколом этими материалами не доказана.

2. **Некоторые названия тестов шире фактического оракула.** Например, `test_dynamic_config_switch_same_server` переключает результат чтения config, но не выполняет HTTP-запросы через оба транспорта. Проверка interruption-маркера использует три границы разреза, а не каждую возможную. Тест здоровья не проверяет истечение TTL.

3. **Начальный статус не гарантирован за 1 с от приёма любого HTTP-запроса.** Таймер создаётся после получения слота и подготовки SSE. Долгое ожидание bulkhead до этой точки отдельно не покрыто.

4. **Watchdog различается между путями.** Non-stream `Run` учитывает native tools как токены и защищает активный task от stall. Legacy SSE обновляет token-clock по тексту/reasoning и такого task-исключения не показывает. Tool-only или долгие task-сценарии могут вести себя неодинаково.

5. **Нет полного ограничения памяти native tool-state.** Отдельный accumulated budget считает reasoning/text, но не сумму сохранённых tool inputs и число call ID. Очередь и размер отдельной строки ограничены, однако это не равно общему пределу памяти всех инструментальных состояний. Legacy stderr ограничен строками, поэтому одна очень длинная строка остаётся риском.

6. **Tool-call может уйти клиенту до подтверждения `step.ended`.** Если последующий drain завершается ошибкой, успешного finish не будет, но клиент уже мог получить и начать исполнять вызов. Атомарность внешнего исполнения инструментов кодом не обеспечивается.

7. **Draining инструментального шага обрабатывает не все события.** `_drain_serve_step_usage()` обрабатывает tools и `step_finish`; permission, form и error могут быть извлечены из очереди без основной обработки reject/cancel/error.

8. **Без `assistantMessageID` принадлежность шагу неоднозначна.** Совместимость с idless-событиями поддержана, но строгого отделения следующего шага при отсутствии идентификаторов обеспечить нельзя.

9. **Нет предварительной проверки версии/capabilities.** Протокольная несовместимость выявляется во время попытки. Наличие `FALLBACK_DECISION_TABLE` не гарантирует совпадения всех ветвей кода с её описанием.

10. **Есть потенциальная асимметрия пустого успеха.** JSON serve явно отклоняет результат без текста и tool calls. SSE после успешного terminal может сформировать `finish_reason=stop` при пустом полезном ответе. Эквивалентный негативный тест не показан.

11. **Дедупликация recovery неполна.** Reasoning повторов может дублироваться. Legacy SSE при watchdog-retry не включает ту же дедупликацию, что incomplete recovery. Внутренний watchdog-retry `Run.execute()` возвращает результат последней попытки; сохранение usage предыдущих внутренних попыток не видно.

12. **Control retry не имеет idempotency key.** `_ctrl_http` повторяет запрос после транспортной ошибки, включая `POST /api/session`. Потеря ответа после принятого POST может создать дополнительную сессию внутри попытки.

13. **Reaper проверен ограниченно.** Нет показанных fault-injection тестов повторного использования PID, несовпадения `lstart`, подмены lease симлинком и случая, когда helper уже умер, а группа потомков ещё жива. В последнем случае показанный reaper не выполняет убийство без живого подтверждённого helper.

14. **Уборка reader/prompt threads подтверждена не полностью.** Потоки daemon и ожидаются кратко; prompt HTTP-соединение отдельно не хранится в cleanup. HTTP/1.0 может отделять SSE-сокет от `conn`; явного закрытия самого `sse_resp` в cleanup не показано. Длительный повторный тест на накопление потоков/FD отсутствует.

15. **Общие временные гарантии ограничены проверенными сценариями.** Отдельные тесты подтверждают cleanup до 7 с, но сочетание tool-drain, control cleanup и полной TERM/KILL-эскалации не проверено как единый худший случай.

16. **Не показаны нагрузочные проверки.** Нет длительного параллельного прогона с конкуренцией за порты, переключением config, деградацией serve, исчерпанием retry budget и медленным клиентом. Также не показаны полный regression suite и запуск тестов в окружении, свободном от влияющих `OPENCODE_ZEN_BRIDGE_*` настроек.
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
Ниже приложены целиком манифест подпроекта (`bridges/opencode-zen-bridge/pyproject.toml`), рубрика подкатегорий и правила повторного цикла Совета (`council.md#L379-L463`) и первичные артефакты выбора мест раунда `panel/council/r140`:
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
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/panel/council/r144/manifest.json sha256=ca88ba9a8d2ddf2fa0668eb49dfc89973cc01fc9f4e63fb540b1374d77d3282a
{"artifact_sha256":"35adea8bc3197709e42854cde111e17b0cdaba1febb6fa6f0f8e9ff7f52bd202","constrained_mode":null,"debate_roster_mode":"rotated","excluded_author":[],"hat_level":1,"history_entry_sha256":"b7605d5c5eebb6f75c9adc77f762c381c5a33f557a2477bc912c7feb120f506d","history_prev_entry_sha256":"192905fa61bfc7dfc2781161fc4109249ba7c2f4a357e6ddb1aaf90d88099171","history_seq":167,"models_md_sha256":"e032139c9fc67e082ea33e7bd390779c7a2d98f066d71a83e4c7d793c3ecc6c4","pool_constrained_3of3":false,"prior_ledger_sha256":"7f475c159cab80c89fc6f099c13691b78fd15ec8351e108667b6fe43c6c774c4","ranked_order":["grok-4.7-high","muse-wonder-full-1.0","gemini-4-argon-high","gpt-6.1-sol-high","claude-sonnet-5-5-high"],"replaced_seats":[],"round":144,"run_id":"analyst-teamlead-zen-realtime-reasoning-20261025","schema":"pol-manifest/2","seats":[{"family":"xAI","k":1,"slot_id":"grok-4.7-high","transport":"cursor-agent"},{"family":"OpenAI","k":2,"slot_id":"gpt-6.1-sol-high","transport":"codex"},{"family":"Meta","k":3,"slot_id":"muse-wonder-full-1.0","transport":"muse"}],"seed_hex":"0f40b2e968c6c1b0be429ecb1aee41e7cc9ce87c09c61e52aabe620b1ebec1d1","seed_input":"analyst-teamlead-zen-realtime-reasoning-20261025:council:r144:35adea8bc3197709e42854cde111e17b0cdaba1febb6fa6f0f8e9ff7f52bd202:192905fa61bfc7dfc2781161fc4109249ba7c2f4a357e6ddb1aaf90d88099171","selector_sha256":"96c525ac5ec3c0c9761f4e7789fe656cb04a86300e2bd9d0059854474842894d","setup":"default","stage":"council","status":"READY","triplet_rule":"A+B","unavailable_evidence":{}}
ARTIFACT_END>>>
<<<ARTIFACT ~/Мой диск/Context/models.md#L121-L138 sha256=53fc192f7ce80bc65b54a7429e9f8c47d9320a0854047be3dc541ac12064e37c
```
1. Состав и транспорты раунда — сид-жеребьёвка с хеш-ранжированием (без якоря).
1.0 Инварианты: ровно 3 судьи (3 голоса, 3 сиденья) во всех пакетах; 4-й судья, 4-я модель, добор голосов и «опрос всех доступных» запрещены; пул — запас; составы разных раундов не складываются; `Anthropic` ≤ 1 в раунде. Все 3 сиденья — рандомно (по хеш-рангу SEED) из рабочих моделей пула своего сетапа с уникальностью семейств. Пакеты fast↔quality не смешиваются (пул исчерпан — замена упавшего рабочим кандидатом из `default`, заимствованный слот — в манифесте; голосов и сидений не добавляет). Оркестратор-ПРОЦЕСС не судит. Все id — verbatim pinned live ID; семейство слота — по колонке «family». Automatic PASS: majority 2/3 РАЗНЫХ семейств (два голоса одной семьи PASS не дают). Нет рабочего состава из 3 — недостающие сиденья добираются по п. 1.8 («⚠️ пул N/3»); нет ни одного рабочего транспорта — `QUORUM_UNAVAILABLE`, отчёт о несобранном раунде, а не вердикт. Task-subagent сессии вместо замены не подставляется (SDLC-панели — строго `launch_seat.py`).
1.1 Сид. seed_input = «<artifact_sha8>#<run_slug>#c<N>#R<M>» — LC_ALL=C, без пробелов, БЕЗ завершающего перевода строки; artifact_sha8: текстовое решение — SHA-256 файла решения; code-раунд teamlead-gate — SHA-256 коммита/ревизии под ревью; run_slug = слаг run-каталога; вне run-dir строка сида — в статус цели verbatim. SEED = первые 8 hex SHA-256(seed_input) (printf '%s' "$SEED_INPUT" | shasum -a 256 | cut -c1-8). Журнал rounds.tsv (run, c, R, seed_input, seed_hex, состав, hats, status) — append-only, производный от манифестов раундов; номера c/R монотонны; переигровка без записи = нарушение; seed_input — в манифест байт-в-байт, расхождение = блокер раунда.
1.2 Жеребьёвка — хеш-ранжирование по всему пулу сетапа. Новый жребий на КАЖДОМ раунде (R1, R2/D-раунды, forced-dissent, C1 — всегда полная коллегия из 3, не «только несогласные»), свой seed_input с номером раунда: модели, их рабочие транспорты и роли (Скептик/Реалист/Визионер) выбираются заново:
    - rank(slot) = SHA-256(SEED + '#' + slot_id); порядок — возрастание hex (LC_ALL=C); тай-брейк — лексикографически по slot_id.
    - Закреплённого сиденья нет: слоты равноправны и ранжируются единым `ranked_order[]`; на сиденья 1–3 берутся первые по рангу рабочие слоты разных семейств.
    - Группы пула: native (у семьи есть host-native транспорт текущего хоста) и external (только внешние транспорты, `model-invocation.md`). При |native|≥2 сиденья 1–2 — первые по рангу рабочие из native, сиденье 3 — первая по рангу незанятая рабочая семья пула; при |native|<2 — три по общему `ranked_order[]`. Недоступный судья заменяется: рабочие транспорты своего слота → следующий по рангу кандидат пула → независимый сабпроцесс (1.4, 1.8).
    - Anti-repeat: окно 2 раунда (состав сверяется с R−1 и R−2 по манифестам, сквозное по прогону; новый цикл историю не обнуляет). Точное совпадение состава → сиденье 3 уступает следующей по рангу незанятой рабочей семье (итерация ≤2; исчерпание → rotation_ok=relaxed+reason).
    - Precedence: raw rank → anti-drift promotion 1.8 (≤1 буст/раунд) → anti-repeat shift (сиденье 3) → счётчик замен 1.4.
    - Недоступный слот пропускается (skip_reason + skip_source=matrix|runtime). Пересев (добровольная смена роли/модели в ходе раунда) запрещён, аварийная замена разрешена. Матрица доступности `family × host` — `~/Мой диск/Context/model-notes.md`: семьи без транспорта на хосте и «подтверждённая нежизнеспособность» помечаются ЗАРАНЕЕ; каждый живой сбой → предмарк в ту же правку.
1.3 Транспорт выбранной семьи — по алгоритму `panel-backends` (вес родной подписки, затем жребий среди живых транспортов слота). Иерархия: размер 3 и рабочие процессы → уникальность семей → tier-major как порядок аварийного фолбэка внутри раунда.
1.4 Запуск, доступность и приёмка: три сиденья стартуют параллельно — все три запущены до первого вердикта (PID/task-id и время старта — в манифест/processes.tsv); wall-clock раунда = максимум, не сумма. Доступность ленивая (preflight-ping пула запрещён). Первый токен ≤120 с — критерий только стримящих транспортов; для Task — только полный вызов ≤600 с. БЮДЖЕТ РАУНДА ~15 мин — жёсткий потолок, отменяющий retry и замену: по исчерпании при <3 вердиктов общий вердикт НЕ выносится (NEEDS_RERUN либо эскалация), PASS запрещён; при трёх запущенных не закрывать по двум, пока третий в бюджете. Retry — 1, в пределах бюджета; далее skip. Падение слота (лимит, 429, пустой stdout, ActionRequiredError, таймаут, id отвергнут, лог не растёт) — перебор до набора 3: (а) оставшиеся рабочие транспорты того же слота; (б) следующий рабочий кандидат того же пула (tier 1 → tier 2, приоритет не занятым семействам); (в) tier 3 снят; (г) состав из пула не набирается — добор по п. 1.8 («⚠️ пул N/3»); нет рабочего транспорта — `QUORUM_UNAVAILABLE`. Сбой фиксируется в `~/Мой диск/Context/model-notes.md`. Fail-fast по reasoning (стрим): поток завершён (rc=0/[DONE]) при нулевом content → skip_reason=reasoning_budget. Приёмка ответа: парсинг 6×VERDICT + ОБЩИЙ ВЕРДИКТ; по каждой подкатегории рубрики — SUB-строка «SUB <критерий>/<подкатегория>: PASS|FAIL|N/A — evidence (файл:строка/правило)» (N/A — с причиной); каждый FAIL — с issue-ID F-NNN и привязкой; malformed := нет SUB-строки по подкатегории, FAIL без ID/привязки, N/A > 2/3 подкатегорий при нуле содержательных наблюдений → 1 retry с напоминанием формата (тот же слот) → замена по рангу. Замена: таймаут → SIGTERM по своему PID из processes.tsv (Task — штатная отмена; CLI → 5 с → kill -KILL) → дождаться выхода → следующая по рангу рабочая модель; живых ≤3 всегда; ≤1 замены в пользу семьи, сидевшей в предыдущем раунде (иначе другая семья, иначе 1.8). Потолок ≤6 вызовов судей на раунд — лимит суммарных вызовов с учётом retry и замен, НЕ разрешение на >3 судей/голосов/параллельных живых. НЕЗАВИСИМЫЙ ПЕРЕСЧЁТ: судья с наименьшим рангом среди успешно стартовавших, не заменявшийся, ОБЯЗАН независимо пересчитать SEED и ranked_order по 1.1/1.2 и зафиксировать в вердикте; расхождение = блокер раунда.
1.5 Шляпы: hat_index = int(первые 8 hex SHA-256(seed_hex + '#hats'), 16) mod 6. Перестановки (Скептик, Реалист, Визионер), индекс с 0: 0:(С,Р,В) 1:(С,В,Р) 2:(Р,С,В) 3:(Р,В,С) 4:(В,С,Р) 5:(В,Р,С); назначение — по тройке сидений, отсортированной по pinned live ID (LC_ALL=C). Запрет повтора шляпы моделью из окна 2 раунда: сдвигается вся таблица (hat_index+k) mod 6, k — минимальное ≥1, устраняющее ВСЕ нарушения; нет валидного k∈1..5 → k=1, rotation_ok=relaxed; k и нарушения — в манифест.
1.6 Манифест раунда (route-manifest.json; секреты ЗАПРЕЩЕНЫ — только slot_id/transport/пути): run_id, cycle, round, seed_input, seed_hex, artifact_sha256+путь, pool_setup, pool_source_rev (первые 8 hex SHA-256 этого файла на момент раунда), pool_ordered[], groups{native[],external[]}, ranked_order[], seats[{family, slot_id, transport, native|external, status, skip_reason, skip_source, retries, pid, killed_before_replace}], hats{}, hat_index, k, rotation_ok, fallbacks[], recheck{judge_family, seed_input_verbatim_ok, seed_hex_ok, ranked_order_ok, result}, family_usage_window (skip ≠ сидел), verdicts[], agreement, quorum_status (OK|NEEDS_RERUN|QUORUM_UNAVAILABLE), added_judges[] (requested→actual, источник). ПРЕДрегистрация: seed_input и ожидаемые составы публикуются в статусе цели ДО запуска судей. Манифест — на каждый начатый раунд, включая прерванные (status=aborted+причина), append-only. ГЕЙТ: старт судей запрещён, пока манифест не содержит seed_input, seed_hex, ranked_order[], seats[]; завершение раунда SDLC-панели требует `verify_panel_proof.py` и `panel-proof.json` = PASS.
1.7 Внешние вызовы: raw-захват тела + код ответа (pipefail); reasoning-слоты — max_tokens ≥32768; клиентские таймауты и `--retry 0` — `~/Мой диск/skils/panel-backends/references/parallelism-params.md`; raw-файлы вне Google Диска, очистка после раунда. Секреты: заголовок авторизации только через конфиг-файл 0600 вне Диска или stdin; значение в argv запрещено; смоук «grep по ps -eo args и raw-логам пуст» — предусловие первого внешнего вызова.
1.8 Добор судьи (независимые сабпроцессы): состав из 3 из пула не набирается — недостающие сиденья до ровно 3 закрываются НЕЗАВИСИМЫМИ САБПРОЦЕССАМИ (отдельные внешние CLI-процессы через `launch_seat.py` с независимыми брифами и сессиями; не сессия оркестратора и не Task-субагент хоста) рабочих моделей и транспортов — сначала не задействованные в раунде семейства из списков других ролей (Architect/Analyst/Coder/Summarizer), при <3 живых уникальных семейств — уже подтверждённые рабочие модели и транспорты. Пометка «⚠️ пул N/3» в вердикте, уведомление владельца, запись в манифест (`added_judges[]`: requested→actual). Нет рабочей модели/транспорта — `QUORUM_UNAVAILABLE`, раунд не стартует. Раунда из 2 судей и ACCEPT на двоих нет, 1 судья запрещён. Анти-дрейф: семья не СИДЕЛА 4 раунда подряд (skip ≠ сидел) → буст по precedence 1.2 внутри её eligible-группы. Модели, выведенные из судей (`model-notes.md`), из списков других ролей не берутся.
```
ARTIFACT_END>>>

Обязательное указание судье перед обёртками стандартов (вне тела обёрток `ARTIFACT`):
Все пункты приложенного ниже тип-скилла `~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/skills/feature.md` (`SK-T-*`: алгоритм выполнения фичи, захват из потокового источника с независимым сигналом полноты, таймауты на каждом шаге цепочки I/O включая cleanup в `finally`, критерии приёмки, стоп-коды `HL-ENV-01`, `C-MULT-I1..I5`, `S-HERD-I1..I5`, `H-CPU-I1..I5`, `R-BULK-I1..I5` и Remote-first контракт) и все применимые к diff пункты приложенных ниже профильных стандартов `aisdlc-gcge` (`SK-P-*`: `agents/scope-and-contracts.md`, `agents/python-standards.md`, `agents/testing.md`, `agents/security.md`, `agents/error-handling.md`, `agents/logging.md`, с учётом ограничения задачи `0` внешних runtime-зависимостей вне Python 3.14 stdlib `ThreadingHTTPServer`) являются твоими прямыми обязательными проверками кандидата на уровне строк кода; нарушение любого применимого пункта фиксируй F-блоком с привязкой к `file:line` и правилу.
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

ВЕРДИКТ ТВОЕЙ РОЛИ В РАУНДЕ 1:
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/cycle-9/debate/r1/skeptic.md sha256=9cdb8d62bfcca5507b836eba8c3a351ea8f6187005ed78e58983a1130a2d2161
> PANEL-NONCE: 76d8c83e10e731a7
> ARTIFACT-SHA256: 35adea8bc3197709e42854cde111e17b0cdaba1febb6fa6f0f8e9ff7f52bd202
>
> 1. КОРРЕКТНОСТЬ: VERDICT=FAIL
>    WHY=RW-002 закрыт: до `note_spawn` (`server.py:6813`, `server.py:5583`) локальный дедлайн и уход клиента возвращают `attempt_done(False, False)` (`server.py:2540-2552`, `server.py:6778`, `server.py:6794`, `server.py:5545`, `server.py:5563`), резерв лимитера возвращается, JSON-ветка `state=="timeout"` отдаёт 502 до пустого `upstream_failed` (`server.py:7945-7964`). FU-001 и FU-002 закрыты лимитами 16 МиБ и зелёным L2 (`VER-002` 480 OK, `VER-001` 480 passed). Оракулы приёмки RW-001 (два вызова, idless, отсутствие `step.ended` → неуспех) в коде есть (`server.py:3498-3523`). Дыра в том же дренаже: после первого `tool.called` главный цикл блокируется в `_finish_serve_tool_step` (`server.py:4001-4019`), а `_drain_serve_step_usage` забирает очередь и обрабатывает только `tool_event` и `step_finish` (`server.py:3377-3401`). `reasoning`/`text`, `permission` и `form.created` за этот интервал до 1 с снимаются с очереди и пропадают. REQ-001 и REQ-012 на этом окне не выполняются.
>    СОВЕТЫ (при FAIL):
>    - В `_drain_serve_step_usage` (`server.py:3377-3401`) для событий той же сессии вызвать те же действия, что основной цикл: `permission` → reject+interrupt (`server.py:3940-3958`), `form.created` своей сессии → cancel+interrupt до разбора схемы (`server.py:3881-3904`), `error` → записать `result["error"]` и выйти неуспехом, `reasoning`/`text` → `on_reasoning`/`on_text` и байтовый бюджет.
>    - Событие чужой сессии по-прежнему пропускать. Неподтверждённый конец шага по-прежнему `ServeProtocolError("incomplete tool step without step.ended")`.
>    - Регрессия: между `session.tool.called` и `session.step.ended` приходят `session.reasoning.delta` и `permission.asked`; дельта есть в SSE и JSON, permission получает reject, `finish_reason=tool_calls` только после `step.ended`.
>
> 2. ПОЛНОТА: VERDICT=FAIL
>    WHY=Ветка «между первым native-вызовом и `session.step.ended`» не покрыта: дренаж молча забирает всё, кроме инструмента и `step_finish`. Через полгода это читается как полный разбор шага, а теряется и текст модели, и запрет встроенного инструмента.
>    СОВЕТЫ (при FAIL):
>    - Добавить в `tests/test_realtime_reasoning.py` сценарий SSE и JSON: `tool.called` → `reasoning.delta` → `permission.asked` → `step.ended`. Ожидание: reasoning в ответе, reject permission, один tool_call, usage шага.
>    - Отдельный сценарий: `tool.called` → `form.created` своей сессии без `step.ended`. Ожидание: cancel+interrupt и ошибка, без `finish_reason=tool_calls`.
>
> 3. РЕАЛИЗУЕМОСТЬ: VERDICT=PASS
>    WHY=Правка локальная в уже существующем дренаже, новых зависимостей нет (`pyproject.toml` `dependencies = []`), выкат и kill-switch `run` не меняются. L2 на кандидате зелёный (`code-gate.json` status=PASS, 480 passed). VER-006/VER-007 законно `DEFERRED_L3`.
>
> 4. РИСКИ: VERDICT=FAIL
>    WHY=L2 red→green и полный набор зелёные: `L2-RED-sensitivity` rc=1 на `origin/dev`, `VER-001`/`VER-005`/`AC-023` rc=0, frozen `_run_env` sha256 `1c51b28f…` совпал, diff ровно из трёх файлов конверта. Дыра безопасности и потери данных тестами не поймана: `permission.asked` в окне дренажа не получает reject, дельта размышления не доходит до клиента. Это прямой обход изоляции встроенных инструментов (REQ-012) на новом транспорте.
>    СОВЕТЫ (при FAIL):
>    - В дренаже не снимать с очереди событие, для которого нет обработчика; permission/form обрабатывать fail-closed, как в основном цикле.
>    - Закрепить это регрессией из совета по ПОЛНОТЕ и прогнать её в том же L2-контуре, что `VER-005`.
>    - Не ослаблять `MAX_TOTAL_SPAWNS=3` и не считать зелёный suite доказательством этой ветки: её в текущих 101 тестах нет.
>
> 5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
>    WHY=Добор веток в `_drain_serve_step_usage` достаточен. Переписывать `_serve_one_attempt` или транспорт не требуется. Раздувания относительно согласованного окна 1 с нет.
>
> 6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
>    WHY=Публичные маршруты `/health`, `/v1/models`, `/v1/chat/completions` и поле `transport=opencode-zen-cli` не добавлены и не переименованы (`server.py:8123-8137`). Замороженные `_run_env`, `_stream_google_sse`, `_execute_google_once` побайтово совпали с `origin/dev` (VER-004). Внешних runtime-зависимостей нет. Нарушение REQ-001/REQ-012 учтено в корректности, это не слом слоёв и не выход за три файла конверта.
>
> F-001
> priority: blocking
> file: bridges/opencode-zen-bridge/server.py:3373, bridges/opencode-zen-bridge/server.py:3377, bridges/opencode-zen-bridge/server.py:3392, bridges/opencode-zen-bridge/server.py:3401, bridges/opencode-zen-bridge/server.py:4001, bridges/opencode-zen-bridge/server.py:4008
> rule: REQ-001, REQ-012, RW-001 blast-radius (окно дочитывания шага)
> evidence: после `on_tool` цикл входит в `_finish_serve_tool_step` и единственный читатель очереди — `_drain_serve_step_usage`. Там после фильтра сессии обрабатываются только `mapped[0] == "tool_event"` и `mapped[0] == "step_finish"`; иное событие не возвращается в очередь и не передаётся в `on_reasoning`/`on_text` и не проходит reject/cancel, которые основной цикл делает для `permission` (`server.py:3940-3958`) и `form.created` (`server.py:3881-3904`).
> expected: в том же окне `min(1.0, deadline-now)` доставлять reasoning/text той же сессии, на `permission`/`form.created` выполнять тот же fail-closed, на `error` завершать попытку ошибкой; `step.ended` по-прежнему обязателен для `terminal=tool_calls`.
> check: SSE и JSON, последовательность `tool.called` → `reasoning.delta` → `permission.asked` → `step.ended`: дельта видна клиенту, в FakeServe записан reject, финальный `finish_reason=tool_calls` один, usage шага сохранён. Вторая последовательность с `form.created` без `step.ended`: нет `finish_reason=tool_calls`, в логе `invalid_serve_event` или security failure, есть cancel.
>
> SUB Корректность/логика: FAIL — server.py:3377-3401 отбрасывает reasoning/text и permission между tool.called и step.ended (REQ-001, REQ-012)
> SUB Корректность/граничные условия: FAIL — server.py:4008 окно `_STEP_DRAIN_WINDOW_S=1.0` является единственным потребителем очереди на границе шага
> SUB Корректность/обработка ошибок: FAIL — server.py:3377-3401 не вызывает reject/cancel для permission и form, в отличие от server.py:3940 и server.py:3881
> SUB Полнота/покрытие AC: PASS — REQ-002..REQ-020 и AC-026 закрыты L2: red rc=1, green VER-001/VER-005 rc=0; дыра AC на границе шага вынесена в пропущенные ветки
> SUB Полнота/пропущенные ветки: FAIL — нет ветки дренажа для reasoning/permission/form/error (server.py:3377-3401); оракул c9_rw001 эту очередь не шлёт
> SUB Реализуемость/общее: PASS — правка в одном хелпере, stdlib, kill-switch run сохранён, VER-006/VER-007 DEFERRED_L3 по конверту
> SUB Риски/безопасность: FAIL — REQ-012: permission.asked в дренаже не получает reject (server.py:3377 против server.py:3940)
> SUB Риски/данные: FAIL — REQ-001: reasoning/text той же сессии в окне дренажа удаляются из очереди (server.py:3377-3401)
> SUB Риски/прод: PASS — при отказе до барьера доставки остаётся fallback на run; лимиты очереди 16 МиБ и cleanup группы на месте (server.py:3450, server.py:4087)
> SUB Риски/regression red→green: PASS — l2-red.log rc=1 (AC-026: 1 чанк на origin/dev), l2-green-ver005 rc=0 (101 passed)
> SUB Риски/Full Suite (L2): PASS — VER-001 480 passed, VER-002 Ran 480 OK, AC-023 reversed rc=0 (execution-evidence.md)
> SUB Риски/scope-diff: PASS — candidate-manifest ровно server.py, test_realtime_reasoning.py, test_step_interruption.py; frozen sha256 совпал
> SUB Альтернативы/общее: PASS — достаточно дописать обработчики в `_drain_serve_step_usage`, без смены транспорта
> SUB Соответствие контексту/общее: PASS — публичный HTTP-контракт и frozen Google/`_run_env` не изменены (server.py:8123, VER-004)
>
> [sweep] Отдельный F-блок на ранний `on_tool` до `step.ended` не заведён: клиентский контракт исполнения — `finish_reason=tool_calls`, неуспешный путь его не ставит (`server.py:3521` только после подтверждения), оракул eof/window это проверяет.
>
> ОБЩИЙ ВЕРДИКТ: NEEDS WORK
ARTIFACT_END>>>

АРГУМЕНТЫ ДРУГИХ ЭКСПЕРТОВ:
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/cycle-9/debate/r1/realist.md sha256=3b49faa17a8e500b5b29de8120ce6d401e80de53750b497000f934ccf8fb15b9
> PANEL-NONCE: a8c3d51127141c30
> ARTIFACT-SHA256: 35adea8bc3197709e42854cde111e17b0cdaba1febb6fa6f0f8e9ff7f52bd202
> Подтверждаю: общий канон `~/Мой диск/Context/AGENTS.md` прочитан целиком до `<!-- КАНОН-КОНЕЦ -->`; проектных `AGENTS.md`/`.agents/AGENTS.md`/`CLAUDE.md` в пакете приёмки не представлено.
>
> 1. КОРРЕКТНОСТЬ: VERDICT=PASS
>    WHY=RW-001 закрыт: `_drain_serve_step_usage` дочитывает native-вызовы того же шага в окне до 1 с, допускает пустой `assistantMessageID`, отсекает только непустой иной ID, а неподтверждённый `session.step.ended` переводит попытку в `ServeProtocolError`/`invalid_serve_event`, не в успешный `tool_calls`; покрыто `test_c9_rw001_idless_and_unconfirmed_native_step` и `test_c8_fu001_multiple_native_tool_calls_same_step_preserved_next_step_excluded` в SSE и JSON с точным usage. RW-002 закрыт: локальный `state=timeout` в JSON терминален до `upstream_failed`, O-EXIT пишет `exit_reason=timeout`, `total_spawns=0`, breaker нейтрален; покрыто `test_c8_fu002_legacy_spawn_rechecks_cancel_and_deadline_after_reservation`. Clean-room L2: 480 passed.
> 2. ПОЛНОТА: VERDICT=PASS
>    WHY=REQ-001..REQ-020 и AC-001..AC-026 трассированы в `verification-traceability.md`; FU-001 закрыт байтовыми бюджетами SSE-очереди и накопленного ответа по 16 МиБ с `cleanup()`, FU-002 — сохранённым `unittest`-контуром (VER-002: 480 OK). VER-006/VER-007 законно `DEFERRED_L3` до ACCEPT, а не пропущены молча.
> 3. РЕАЛИЗУЕМОСТЬ: VERDICT=PASS
>    WHY=Для взлёта не нужны новые runtime-зависимости: ровно 3 файла, Python 3.14 stdlib, локальный `opencode serve` v2.1.2 эмпирически подтверждён, деплой — синхронизация одного `server.py`, откат — `REALTIME_SERVE_ENABLED=false`, `TRANSPORT=run` или disable-файл без редеплоя. Ресурсный конверт замкнут: bulkhead 6, `MAX_TOTAL_SPAWNS=3`, per-attempt serve, бюджеты очереди/тела/текста; расчёт памяти HL-ENV 1216 МиБ ≤ 1638 МиБ.
> 4. РИСКИ: VERDICT=PASS
>    WHY=Red→green на `origin/dev` поведенческий (`red_sensitivity_rc=1`, AC-026 на сокете при идущем апстриме), Full Suite L2 зелёный в pytest, unittest, корневом PYTHONPATH и обратном порядке (AC-023). Секреты маскируются в SSE/JSON/логах, serve-пароль одноразовый, env по allowlist, `OPENCODE_DB=:memory:`, группы процессов и lease убираются с подтверждением смерти; остаточный риск живого wire v2.1.2 закрывается auto-fallback на `run`, `_ServeHealth` и пост-ACCEPT лестницей H0..H9 до MR.
> 5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
>    WHY=Варианты L/A1/A2/B/C сравнены по фактам в handoff: L не даёт реалтайма RC-1, B не доказан из-за 429 без CLI-заголовков, A2 ломает ротацию IP; выбранный короткоживущий A1 с fallback на legacy — минимально достаточный путь внутри существующего кортежного контракта `parse_opencode_event`, без переписывания верхнего слоя и без новых зависимостей. Неоправданного раздувания сверх serve-транспорта и watchdog в дельте нет; массовое форматирование legacy на поведение не влияет и проверено VER-004 при неизменных замороженных срезах.
> 6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
>    WHY=Scope-diff ровно `coder_target_files` (3 файла), публичный контракт `:9883`/`/health`/`/v1/models`/`/v1/chat/completions`/OpenAI SSE не изменён, Google-direct и `_run_env` побайтно заморожены (`run_env_sha256=1c51b28f...`, `google_direct_unchanged=True`), чужих Jira-KEY и файлов вне `bridges/opencode-zen-bridge/` нет. Стандарты Litestar/async/orjson к автономному stdlib-мосту неприменимы по явному ограничению 0 внешних зависимостей; применимые пункты — таймауты на каждом I/O-шаге включая cleanup, запрет секретов в логах, Full Suite Gate, изоляция `os.environ` в тестах — выполнены и покрыты оракулами.
>
> SUB Корректность/логика: PASS — evidence (bridges/opencode-zen-bridge/server.py, `_drain_serve_step_usage`/`_finish_serve_tool_step`; RW-001)
> SUB Корректность/граничные условия: PASS — evidence (tests/test_realtime_reasoning.py, `test_c9_rw001_idless_and_unconfirmed_native_step`: idless/inherited/eof/window)
> SUB Корректность/обработка ошибок: PASS — evidence (server.py, классификация `ServeUnavailable`/`ServeSecurityError`/`ServeProtocolError` и fallback-таблица)
> SUB Полнота/покрытие AC: PASS — evidence (teamlead/verification-traceability.md, REQ-001..REQ-020/AC-001..AC-026)
> SUB Полнота/пропущенные ветки: PASS — evidence (tests/test_realtime_reasoning.py, 101 тест: SSE+JSON, serve+run, watchdog, fallback, tool-step)
> SUB Реализуемость/общее: PASS — evidence (candidate-manifest.json: ровно 3 файла, 0 внешних runtime-зависимостей; pyproject.toml `dependencies=[]`)
> SUB Риски/безопасность: PASS — evidence (server.py, `_serve_env` allowlist, одноразовый пароль, `_mask_secrets`/`_error_payload` очистка)
> SUB Риски/данные: PASS — evidence (server.py, `OPENCODE_DB=:memory:`, статусы `[мост]` не попадают в `_messages_to_prompt`, AC-007)
> SUB Риски/прод: PASS — evidence (execution-evidence.md, VER-006/VER-007 `DEFERRED_L3` с лестницей H0..H9 после ACCEPT)
> SUB Риски/regression red→green: PASS — evidence (receipts/code-gate.json: `red_sensitivity_rc=1`, AC-026 сокетный оракул на `origin/dev`)
> SUB Риски/Full Suite (L2): PASS — evidence (execution-evidence.md: VER-001/002/003/005 и AC-023-reversed все rc=0, 480 passed)
> SUB Риски/scope-diff: PASS — evidence (candidate.diff только server.py, tests/test_step_interruption.py, tests/test_realtime_reasoning.py)
> SUB Альтернативы/общее: PASS — evidence (handoff-architect.md §4, сравнение L/A1/A2/B/C по F-17..F-27)
> SUB Соответствие контексту/общее: PASS — evidence (receipts/code-gate.json: замороженные `_run_env`/Google-direct неизменны, VER-004 PASS)
>
> ОБЩИЙ ВЕРДИКТ: ACCEPT
ARTIFACT_END>>>
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/cycle-9/debate/r1/visionary.md sha256=d644c5448697a62df8a1cf04cf2b4fa4bf5ee73a792af5266c04f2bc61bf32fb
> PANEL-NONCE: 3e2c36c27ea2096f
> ARTIFACT-SHA256: 35adea8bc3197709e42854cde111e17b0cdaba1febb6fa6f0f8e9ff7f52bd202
>
> 1. КОРРЕКТНОСТЬ: VERDICT=FAIL
>
>    WHY=Реалтайм-транспорт устраняет ограничение CLI и сохраняет внешний формат API. Однако подтверждение инструментального шага ещё не образует надёжную границу публикации результата.
>
>    SUB Корректность/логика: FAIL — native-вызовы публикуются до подтверждения завершения шага и сохраняются между повторами (`bridges/opencode-zen-bridge/server.py:4001`, `:6056`, `:6682`; F-002).
>    SUB Корректность/граничные условия: FAIL — результат обработки reasoning зависит от разбиения interruption-маркера на дельты (`bridges/opencode-zen-bridge/server.py:5988`; REQ-005/AC-006; F-003).
>    SUB Корректность/обработка ошибок: FAIL — drain обрабатывает только `tool_event` и `step_finish`, пропуская остальные значимые события (`bridges/opencode-zen-bridge/server.py:3377`; F-001).
>
>    **F-001 — [pre-existing] Потеря ошибок и управляющих событий при дочитывании шага.**
>    - **priority:** blocking.
>    - **locations:** `bridges/opencode-zen-bridge/server.py:3373`, `:3377`, `:3392`.
>    - **Правило:** REQ-011, REQ-012; `feature.md` §2 — полнота захвата потока; fail-closed для детерминированных ошибок.
>    - **Evidence:** после `_map_serve_event(event)` предусмотрены только ветви `"tool_event"` и `"step_finish"`. Событие `session.execution.failed`/`session.step.failed` превращается в `"error"` и теряется. `permission.asked` также не получает reject; `form.created` с вложенным `form.sessionID` отбрасывается ещё проверкой `data.get("sessionID")`.
>    - **Следствие:** ошибка 401/403 внутри drain при последующем EOF становится повторяемым `invalid_serve_event`; при последующем `step.ended` возможен успешный `tool_calls` вместо обработки ошибки. Обработчики reject/cancel из основного цикла обходятся.
>    - **Исправление:** сохранить в drain семантику ошибок, permission и form основного обработчика; не считать `step.ended` успешным подтверждением после терминального отказа.
>    - **Критерий проверки:** для SSE и JSON проверить последовательности `tool → error → EOF`, `tool → error → step.ended`, `tool → permission`, `tool → form`. Детерминированный отказ не повторяется; reject/cancel выполняются; cleanup обязателен.
>
>    **F-002 — Неподтверждённые tool calls переживают неуспешную попытку.**
>    - **priority:** blocking.
>    - **locations:** `bridges/opencode-zen-bridge/server.py:3390`, `:3397`, `:4001`, `:4008`, `:6056`, `:6227`, `:6682`.
>    - **Правило:** RW-001; REQ-011; независимое подтверждение полноты результата.
>    - **Evidence:** `on_tool(done[1])` вызывается до `_finish_serve_tool_step()`. Потоковый callback сразу вызывает `emit_tool_call()`, добавляющий вызов в общий `tool_calls`. При неподтверждённом шаге разрешается `continue` следующей попытки; общий список не откатывается.
>    - **Следствие:** попытка A выдаёт `bash("A")`, затем EOF без `step.ended`; попытка B успешно выдаёт другой вызов. Финальный ответ может содержать оба вызова, включая вызов неподтверждённого шага A. Новая проверка с `MAX_TOTAL_SPAWNS=1` этот переход не покрывает.
>    - **Исправление:** накапливать native-вызовы закрываемого шага до подтверждения и публиковать их после него. Уже опубликованный неподтверждённый вызов должен исключать последующее успешное завершение запроса с накопленным набором.
>    - **Критерий проверки:** при разрешённых повторах сценарии EOF/истечения окна первой попытки и успешного другого tool call второй попытки не возвращают вызовы первой попытки.
>
>    **F-003 — [pre-existing] Изменяются модельные байты reasoning.**
>    - **priority:** blocking.
>    - **locations:** `bridges/opencode-zen-bridge/server.py:5708`, `:5988`, `:7005`.
>    - **Правило:** REQ-005/AC-006 — модельное размышление не модифицируется.
>    - **Evidence:** `_strip_interrupted()` применяет `_INTERRUPTED_RE.sub("", text)` непосредственно к reasoning. Целый маркер удаляется, а тот же маркер, разделённый между дельтами, сохраняется.
>    - **Исправление:** передавать модельный reasoning без текстовой фильтрации; распознавание служебных продолжений отделить от содержимого размышления.
>    - **Критерий проверки:** reasoning с обоими interruption-маркерами сохраняется побайтово при всех границах разбиения; синтетические статусы исключаются отдельно.
>
>    СОВЕТЫ (при FAIL):
>    - Исправить обработку событий в drain — F-001.
>    - Сделать подтверждение шага границей публикации native-вызовов — F-002.
>    - Убрать изменение модельного reasoning — F-003.
>
> 2. ПОЛНОТА: VERDICT=FAIL
>
>    WHY=Именованные сценарии предыдущего rework покрыты, но проверка отрицательных исходов инструментального шага недостаточна.
>
>    SUB Полнота/покрытие AC: FAIL — AC-006 нарушается F-003; успешное завершение неподтверждённого набора инструментов возможно через повтор F-002 (`server.py:5988`, `:6227`; REQ-005/REQ-011).
>    SUB Полнота/пропущенные ветки: FAIL — отсутствует обработка error/permission/form внутри drain и проверка загрязнения результата после неуспешного drain (`server.py:3377`; F-001/F-002).
>
>    **Verify-Fixed:**
>    - **RW-001:** delayed/idless-вызовы, точный usage и отказ при отсутствии `step.ended` реализованы. Это подтверждают `test_c8_fu001_multiple_native_tool_calls_same_step_preserved_next_step_excluded` и `test_c9_rw001_idless_and_unconfirmed_native_step` в зелёном L2. Полное закрытие блокирует F-002.
>    - **RW-002: PASS.** Legacy JSON обрабатывает `timeout` до ветки пустого ответа; проверка реального `O-EXIT` подтверждает причину, нулевые spawns, возврат резерва и нейтральный breaker.
>    - **FU-001: PASS в заявленном объёме.** Ограничены очередь wire-событий и накопленный reasoning/text. Это не закрывает отдельное накопление native-state — F-006.
>    - **FU-002: PASS.** `unittest discover` исполнил 480 тестов; совместимость существующего контура сохранена.
>
>    Поштучная сверка требований:
>    - **REQ-001 / AC-001, AC-002:** PASS на сокетном FakeServe-оракуле.
>    - **REQ-002 / AC-003:** PASS по форме HTTP/OpenAI SSE.
>    - **REQ-003 / AC-004:** PASS: legacy сохранён, переключатели и дефолт выключения присутствуют.
>    - **REQ-004 / AC-005:** PASS в проверенных сценариях после открытия SSE, включая ожидание gate/лимитера.
>    - **REQ-005 / AC-006:** FAIL — F-003; **AC-007:** PASS, reasoning истории исключается из prompt.
>    - **REQ-006 / AC-008:** фазовый watchdog подтверждён L2; общая гарантия прерывания I/O ограничена F-007.
>    - **REQ-007 / AC-009, AC-010:** фазовые сценарии подтверждены L2; остаётся F-007.
>    - **REQ-008 / AC-011, AC-012:** проверенные сценарии disconnect/cleanup проходят; зависшая downstream-запись оставляет пробел F-007.
>    - **REQ-009 / AC-013:** PASS по общему потолку; **AC-014:** проверенные разделители проходят, но обработка ошибок ограничена F-001/F-002.
>    - **REQ-010 / AC-015:** PASS по инкрементальному парсеру и существующим фикстурам.
>    - **REQ-011 / AC-016:** FAIL — F-001/F-002, несмотря на зелёную текущую матрицу interruption.
>    - **REQ-012 / AC-017:** основная ask/reject-изоляция и unmapped recovery проверены; полноту обработки управляющих событий нарушает F-001.
>    - **REQ-013 / AC-018:** PASS по ротации и повторному использованию защит запуска.
>    - **REQ-014 / AC-019:** PASS для подтверждённых шагов и проверенных полей usage.
>    - **REQ-015 / AC-020:** PASS по представленным проверкам маскирования.
>    - **REQ-016 / AC-021:** PASS, включая RW-002 и финальный sink.
>    - **REQ-017 / AC-022, AC-023:** PASS, включая обратный порядок модулей.
>    - **REQ-018 / AC-024:** PASS: frozen hashes и Google Direct suite.
>    - **REQ-019 / AC-025:** `DEFERRED_L3`, законно до ACCEPT.
>    - **REQ-020 / AC-026:** PASS: приведено поведенческое RED-падение на сокете и GREEN кандидата.
>
>    **F-004 — Устаревшие ссылки матрицы прослеживаемости.**
>    - **priority:** non-blocking.
>    - **locations:** `teamlead/verification-traceability.md:23`, `:27`, `:28`, `:29`, `:30`, `:31`.
>    - **Правило:** проверяемая привязка требования к фактически существующему оракулу.
>    - **Evidence:** матрица упоминает отсутствующие в кандидате `message.part.delta`, `_SSEByteCapReader` и следующие методы:
>      `test_c7_rw001_nonstream_json_watchdog_retries_and_preserves_exit_reason`,
>      `test_c7_rw003_legacy_sse_watchdog_classified_as_transient_in_attempt_done`,
>      `test_c8_fu002_startup_gate_and_spawn_limiter_abort_on_deadline_and_client_gone`,
>      `test_c7_rw004_startup_http_phases_enforce_phase_deadlines_on_dripping_headers`,
>      `test_c9_rw002_first_event_timeout_in_prompt_async_retries_without_run_fallback`,
>      `test_c8_rw001_early_execution_failed_429_503_before_tokens_retries_on_serve_without_run_fallback`,
>      `test_c8_rw003_local_request_deadline_timeout_does_not_increment_cb_or_retry`,
>      `test_c7_rw002_first_event_before_prompt_headers_closes_delivery_barrier`,
>      `test_c8_rw002_unpaired_surrogate_raises_serve_protocol_error_while_valid_pair_passes`,
>      `test_c9_rw001_drain_serve_step_usage_preserves_sse_line_and_body_byte_caps_with_tail_buffer`,
>      `test_c8_fu001_drain_serve_step_usage_collects_additional_same_message_native_tool_calls`,
>      `test_c7_fu001_native_tool_call_drains_step_ended_for_usage`.
>    - **Исправление:** заменить ссылки фактическими именами методов и реализации.
>    - **Критерий проверки:** каждая ссылка разрешается в конкретное определение; отдельные доказательства выполнения берутся из актуального L2. Сам факт полного зелёного прогона этим замечанием не оспаривается.
>
>    СОВЕТЫ (при FAIL):
>    - Добавить отрицательные SSE/JSON-сценарии F-001/F-002 и проверку сохранности reasoning F-003.
>    - Исправить ссылки матрицы F-004 без изменения замороженных оракулов.
>
> 3. РЕАЛИЗУЕМОСТЬ: VERDICT=FAIL
>
>    WHY=Короткоживущий serve сохраняет ротацию IP и изоляцию запросов, а `OPENCODE_DB=:memory:` снимает зависимость от большой общей SQLite. Но вспомогательные ожидания не замкнуты в обязательный бюджет.
>
>    SUB Реализуемость/общее: FAIL — три допустимых окна подписки по 20 с уже превышают вспомогательный бюджет 54 с (`server.py:3232`; `R-BULK-I1`; F-005).
>
>    **F-005 — [pre-existing] Не выполняется бюджет вспомогательного I/O.**
>    - **priority:** blocking.
>    - **locations:** `bridges/opencode-zen-bridge/server.py:3232`, `:3240`, `:6227`, `:7573`.
>    - **Правило:** `R-BULK-I1`: сумма вспомогательных ожиданий всех попыток ≤ `0.30 × SLA_p99_s`.
>    - **Evidence:** конверт задаёт `SLA_p99_s=180`, следовательно предел — **54 с**. `_open_serve_events` допускает до `FIRST_EVENT_TIMEOUT_S=20` с на подписку каждой попытки. Три подписки, успешно открывшиеся перед своим пределом и затем завершившиеся повторяемой протокольной ошибкой, расходуют почти **60 с** только на эту фазу. Readiness, create, handshake, gate, backoff и cleanup добавляются сверх этого.
>    - **Исправление:** выделить общий вспомогательный бюджет запроса и передавать его остаток во все startup/control-фазы и повторы; согласовать фазовые потолки с этим бюджетом.
>    - **Критерий проверки:** управляемые часы подтверждают сумму ≤54 с и отсутствие следующего I/O после исчерпания бюджета.
>
>    СОВЕТЫ (при FAIL):
>    - Замкнуть общий вспомогательный бюджет по F-005.
>    - Сохранить текущую архитектуру отдельных процессов и ротацию прокси.
>
> 4. РИСКИ: VERDICT=FAIL
>
>    WHY=Функциональный L2 убедителен, но ограничения очереди не ограничивают всё удерживаемое состояние, а downstream-запись способна остановить сам цикл надзора.
>
>    SUB Риски/безопасность: FAIL — permission/form/error обходят обязательную обработку внутри drain (`server.py:3373`; F-001).
>    SUB Риски/данные: FAIL — неподтверждённые tool calls сохраняются в результате, reasoning изменяется фильтром (`server.py:4001`, `:5988`; F-002/F-003).
>    SUB Риски/прод: FAIL — native-state не имеет общего лимита, а запись клиенту не ограничена сроком (`server.py:3162`, `:5835`; F-006/F-007).
>    SUB Риски/regression red→green: PASS — `execution-evidence.md`, `L2-RED-sensitivity`: AC-026 падает поведенчески на origin/dev и проходит на кандидате.
>    SUB Риски/Full Suite (L2): PASS — независимые логи подтверждают 480 component-тестов, 480 unittest-тестов и 894 корневых теста; `VER-004` даёт ноль ошибок типов.
>    SUB Риски/scope-diff: PASS — кандидат ограничен тремя разрешёнными файлами; frozen `_run_env` и Google Direct подтверждены `receipts/code-gate.json`.
>
>    **F-006 — [pre-existing] Байтовый предел не охватывает накопление native-инструментов.**
>    - **priority:** blocking.
>    - **locations:** `bridges/opencode-zen-bridge/server.py:3154`, `:3162`, `:3168`, `:3171`, `:3381`, `:3483`, `:3990`.
>    - **Правило:** `HL-ENV-01`, ограниченность накопленного состояния динамического источника.
>    - **Evidence:** `_serve_accumulated_bytes()` считает только `"reasoning"` и `"text"`. `_ServeToolState.tools` сохраняет произвольное число call ID и их `text`/`input`; освобождение wire-резерва очереди не освобождает это состояние. Поток уникальных `session.tool.input.ended` до первого завершённого вызова обходит оба новых лимита.
>    - **Исправление:** ограничить количество native-вызовов и совокупный размер удерживаемых аргументов, включая замену существующего значения и оба пути потребления событий.
>    - **Критерий проверки:** поток уникальных незавершённых native-вызовов превышает установленный предел, завершается управляемой ошибкой и cleanup; потребление памяти имеет вычислимую верхнюю границу.
>
>    **F-007 — [pre-existing] Блокирующая запись клиенту обходит watchdog и общий deadline.**
>    - **priority:** blocking.
>    - **locations:** `bridges/opencode-zen-bridge/server.py:5835`, `:5998`, `:6595`.
>    - **Правило:** `feature.md` §2 — таймаут на каждом шаге I/O; ограниченное время владения ресурсами.
>    - **Evidence:** `_LockedWfile.write()` выполняет блокирующий `inner.write()` под замком. Callback reasoning вызывается из контролирующего цикла попытки. При клиенте, который сохраняет соединение, но прекращает читать, заполнение TCP-буфера останавливает цикл до следующей проверки deadline/watchdog. Таймер статуса использует ту же блокирующую запись.
>    - **Исправление:** ограничить downstream-запись оставшимся сроком и обеспечить отмену, которая не зависит от освобождения того же замка.
>    - **Критерий проверки:** реальный сокетный клиент прекращает чтение после заголовков; достаточно большой поток приводит к ограниченному завершению, остановке группы и возврату слота.
>
>    Отдельно: принадлежность двух потерянных crash-report из отчёта Coder остаётся **INCONCLUSIVE**. Это не доказательство падения независимого L2 и не основание объявлять его crash-clean. `VER-006/VER-007` остаются законным `DEFERRED_L3`.
>
>    СОВЕТЫ (при FAIL):
>    - Закрыть накопление native-state по F-006.
>    - Добавить ограниченную запись и сценарий медленного клиента по F-007.
>    - Перепроверить отрицательные исходы инструментального шага после F-001/F-002.
>
> 5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
>
>    WHY=Выбранный путь даёт существенное улучшение: реальные дельты превращают непрозрачное ожидание в наблюдаемый процесс без изменения DSH. Только упрочнение legacy не устраняет RC-1; общий демон осложняет ротацию IP; прямой Zen HTTP пока не имеет доказанного рабочего доступа. Исправления требуют укрепления текущих границ, а не смены архитектуры.
>
>    SUB Альтернативы/общее: PASS — отдельный serve с резервным run соответствует ограничениям авторизации, ротации и совместимости (`handoff-architect.md` §4; `server.py:1904`, `:3526`).
>
> 6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=FAIL
>
>    WHY=Стек stdlib, внутренний транспортный адаптер и сохранение публичного API соответствуют задаче. Применять к этому автономному мосту требования Litestar/orjson вопреки явному конверту нельзя; сохранение unittest отдельно разрешено FU-002. Однако полнота обработки потока и ресурсные гарантии нарушены F-001, F-005, F-006, F-007.
>
>    SUB Соответствие контексту/общее: FAIL — не закрыты применимые требования полноты потока, `R-BULK-I1`, `HL-ENV-01` и ограниченного I/O (`server.py:3377`, `:3232`, `:3162`, `:5835`).
>
>    Независимый пересчёт: `SEED=d3348837`; `seed_hex=d3348837f76d6888902ff49632faa9c14d4b41b7878f482815fbdc4d37562441`; ранжирование по полному seed совпадает: `gpt-6.1-sol-high → grok-4.7-high → muse-wonder-full-1.0 → gemini-4-argon-high → claude-sonnet-5-5-high`.
>
>    **Границы проверены поштучно:** публичные маршруты/порт/форма SSE сохранены; DSH и ReasoningRow не изменены; сохранность модельного reasoning нарушена F-003; выбор моделей и effort не заменены; muse-bridge и общие конфиги не затронуты; внешние runtime-зависимости не добавлены. Изменений вне разрешённых файлов нет; раскрытия реальных секретов пакет не показывает; live-мутации отложены; запрещённый keychain-вызов отсутствует; прямой записи общей opencode DB нет; commit/merge в защищённые ветки не выполнялись.
>
>    Численный self-sweep: базовая оценка памяти `1216 MiB ≤ 1638.4 MiB`, соединения `6 ≤ 48`, FD `128 ≤ 45875.2`, порты `48 ≤ 8192` сходятся. Оценка CPU из конверта — `0.054 core`, без подтверждения нагрузочным замером. Память удерживаемых native-данных этим расчётом не ограничена — F-006; вспомогательный бюджет `60 > 54 с` не сходится — F-005.
>
>    СОВЕТЫ (при FAIL):
>    - Закрыть шесть blocking-находок F-001, F-002, F-003, F-005, F-006, F-007.
>    - После изменения кандидата повторить L2 и Совет; затем выполнить предусмотренный L3.
>
> ОБЩИЙ ВЕРДИКТ: NEEDS WORK
ARTIFACT_END>>>

СВОДНЫЙ ЛЕДЖЕР:
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/cycle-9/consensus-ledger.md sha256=7f475c159cab80c89fc6f099c13691b78fd15ec8351e108667b6fe43c6c774c4
# Черновой леджер совещания Совета Тимлидов по коду (цикл 9, после R1 r140, run analyst-teamlead-zen-realtime-reasoning-20261025)

- Всего находок R1: `8` (`F-001..F-008`: `skeptic` `F-001`, `realist` `нет (0 находок, ACCEPT)`, `visionary` `F-002..F-008`).
- Открытых blocking (`OPEN_BLOCKING`): `7`; открытых non-blocking: `1`.

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
> F-001
> priority: blocking
> file: bridges/opencode-zen-bridge/server.py:3373, bridges/opencode-zen-bridge/server.py:3377, bridges/opencode-zen-bridge/server.py:3392, bridges/opencode-zen-bridge/server.py:3401, bridges/opencode-zen-bridge/server.py:4001, bridges/opencode-zen-bridge/server.py:4008
> rule: REQ-001, REQ-012, RW-001 blast-radius (окно дочитывания шага)
> evidence: после `on_tool` цикл входит в `_finish_serve_tool_step` и единственный читатель очереди — `_drain_serve_step_usage`. Там после фильтра сессии обрабатываются только `mapped[0] == "tool_event"` и `mapped[0] == "step_finish"`; иное событие не возвращается в очередь и не передаётся в `on_reasoning`/`on_text` и не проходит reject/cancel, которые основной цикл делает для `permission` (`server.py:3940-3958`) и `form.created` (`server.py:3881-3904`).
> expected: в том же окне `min(1.0, deadline-now)` доставлять reasoning/text той же сессии, на `permission`/`form.created` выполнять тот же fail-closed, на `error` завершать попытку ошибкой; `step.ended` по-прежнему обязателен для `terminal=tool_calls`.
> check: SSE и JSON, последовательность `tool.called` → `reasoning.delta` → `permission.asked` → `step.ended`: дельта видна клиенту, в FakeServe записан reject, финальный `finish_reason=tool_calls` один, usage шага сохранён. Вторая последовательность с `form.created` без `step.ended`: нет `finish_reason=tool_calls`, в логе `invalid_serve_event` или security failure, есть cancel.

### F-002
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
> **F-001 — [pre-existing] Потеря ошибок и управляющих событий при дочитывании шага.**
>    - **priority:** blocking.
>    - **locations:** `bridges/opencode-zen-bridge/server.py:3373`, `:3377`, `:3392`.
>    - **Правило:** REQ-011, REQ-012; `feature.md` §2 — полнота захвата потока; fail-closed для детерминированных ошибок.
>    - **Evidence:** после `_map_serve_event(event)` предусмотрены только ветви `"tool_event"` и `"step_finish"`. Событие `session.execution.failed`/`session.step.failed` превращается в `"error"` и теряется. `permission.asked` также не получает reject; `form.created` с вложенным `form.sessionID` отбрасывается ещё проверкой `data.get("sessionID")`.
>    - **Следствие:** ошибка 401/403 внутри drain при последующем EOF становится повторяемым `invalid_serve_event`; при последующем `step.ended` возможен успешный `tool_calls` вместо обработки ошибки. Обработчики reject/cancel из основного цикла обходятся.
>    - **Исправление:** сохранить в drain семантику ошибок, permission и form основного обработчика; не считать `step.ended` успешным подтверждением после терминального отказа.
>    - **Критерий проверки:** для SSE и JSON проверить последовательности `tool → error → EOF`, `tool → error → step.ended`, `tool → permission`, `tool → form`. Детерминированный отказ не повторяется; reject/cancel выполняются; cleanup обязателен.

### F-003
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
> **F-002 — Неподтверждённые tool calls переживают неуспешную попытку.**
>    - **priority:** blocking.
>    - **locations:** `bridges/opencode-zen-bridge/server.py:3390`, `:3397`, `:4001`, `:4008`, `:6056`, `:6227`, `:6682`.
>    - **Правило:** RW-001; REQ-011; независимое подтверждение полноты результата.
>    - **Evidence:** `on_tool(done[1])` вызывается до `_finish_serve_tool_step()`. Потоковый callback сразу вызывает `emit_tool_call()`, добавляющий вызов в общий `tool_calls`. При неподтверждённом шаге разрешается `continue` следующей попытки; общий список не откатывается.
>    - **Следствие:** попытка A выдаёт `bash("A")`, затем EOF без `step.ended`; попытка B успешно выдаёт другой вызов. Финальный ответ может содержать оба вызова, включая вызов неподтверждённого шага A. Новая проверка с `MAX_TOTAL_SPAWNS=1` этот переход не покрывает.
>    - **Исправление:** накапливать native-вызовы закрываемого шага до подтверждения и публиковать их после него. Уже опубликованный неподтверждённый вызов должен исключать последующее успешное завершение запроса с накопленным набором.
>    - **Критерий проверки:** при разрешённых повторах сценарии EOF/истечения окна первой попытки и успешного другого tool call второй попытки не возвращают вызовы первой попытки.

### F-004
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
> **F-003 — [pre-existing] Изменяются модельные байты reasoning.**
>    - **priority:** blocking.
>    - **locations:** `bridges/opencode-zen-bridge/server.py:5708`, `:5988`, `:7005`.
>    - **Правило:** REQ-005/AC-006 — модельное размышление не модифицируется.
>    - **Evidence:** `_strip_interrupted()` применяет `_INTERRUPTED_RE.sub("", text)` непосредственно к reasoning. Целый маркер удаляется, а тот же маркер, разделённый между дельтами, сохраняется.
>    - **Исправление:** передавать модельный reasoning без текстовой фильтрации; распознавание служебных продолжений отделить от содержимого размышления.
>    - **Критерий проверки:** reasoning с обоими interruption-маркерами сохраняется побайтово при всех границах разбиения; синтетические статусы исключаются отдельно.

### F-005
- origin: visionary · R1 · visionary-F-004
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
> **F-004 — Устаревшие ссылки матрицы прослеживаемости.**
>    - **priority:** non-blocking.
>    - **locations:** `teamlead/verification-traceability.md:23`, `:27`, `:28`, `:29`, `:30`, `:31`.
>    - **Правило:** проверяемая привязка требования к фактически существующему оракулу.
>    - **Evidence:** матрица упоминает отсутствующие в кандидате `message.part.delta`, `_SSEByteCapReader` и следующие методы:
>      `test_c7_rw001_nonstream_json_watchdog_retries_and_preserves_exit_reason`,
>      `test_c7_rw003_legacy_sse_watchdog_classified_as_transient_in_attempt_done`,
>      `test_c8_fu002_startup_gate_and_spawn_limiter_abort_on_deadline_and_client_gone`,
>      `test_c7_rw004_startup_http_phases_enforce_phase_deadlines_on_dripping_headers`,
>      `test_c9_rw002_first_event_timeout_in_prompt_async_retries_without_run_fallback`,
>      `test_c8_rw001_early_execution_failed_429_503_before_tokens_retries_on_serve_without_run_fallback`,
>      `test_c8_rw003_local_request_deadline_timeout_does_not_increment_cb_or_retry`,
>      `test_c7_rw002_first_event_before_prompt_headers_closes_delivery_barrier`,
>      `test_c8_rw002_unpaired_surrogate_raises_serve_protocol_error_while_valid_pair_passes`,
>      `test_c9_rw001_drain_serve_step_usage_preserves_sse_line_and_body_byte_caps_with_tail_buffer`,
>      `test_c8_fu001_drain_serve_step_usage_collects_additional_same_message_native_tool_calls`,
>      `test_c7_fu001_native_tool_call_drains_step_ended_for_usage`.
>    - **Исправление:** заменить ссылки фактическими именами методов и реализации.
>    - **Критерий проверки:** каждая ссылка разрешается в конкретное определение; отдельные доказательства выполнения берутся из актуального L2. Сам факт полного зелёного прогона этим замечанием не оспаривается.

### F-006
- origin: visionary · R1 · visionary-F-005
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
> **F-005 — [pre-existing] Не выполняется бюджет вспомогательного I/O.**
>    - **priority:** blocking.
>    - **locations:** `bridges/opencode-zen-bridge/server.py:3232`, `:3240`, `:6227`, `:7573`.
>    - **Правило:** `R-BULK-I1`: сумма вспомогательных ожиданий всех попыток ≤ `0.30 × SLA_p99_s`.
>    - **Evidence:** конверт задаёт `SLA_p99_s=180`, следовательно предел — **54 с**. `_open_serve_events` допускает до `FIRST_EVENT_TIMEOUT_S=20` с на подписку каждой попытки. Три подписки, успешно открывшиеся перед своим пределом и затем завершившиеся повторяемой протокольной ошибкой, расходуют почти **60 с** только на эту фазу. Readiness, create, handshake, gate, backoff и cleanup добавляются сверх этого.
>    - **Исправление:** выделить общий вспомогательный бюджет запроса и передавать его остаток во все startup/control-фазы и повторы; согласовать фазовые потолки с этим бюджетом.
>    - **Критерий проверки:** управляемые часы подтверждают сумму ≤54 с и отсутствие следующего I/O после исчерпания бюджета.

### F-007
- origin: visionary · R1 · visionary-F-006
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
> **F-006 — [pre-existing] Байтовый предел не охватывает накопление native-инструментов.**
>    - **priority:** blocking.
>    - **locations:** `bridges/opencode-zen-bridge/server.py:3154`, `:3162`, `:3168`, `:3171`, `:3381`, `:3483`, `:3990`.
>    - **Правило:** `HL-ENV-01`, ограниченность накопленного состояния динамического источника.
>    - **Evidence:** `_serve_accumulated_bytes()` считает только `"reasoning"` и `"text"`. `_ServeToolState.tools` сохраняет произвольное число call ID и их `text`/`input`; освобождение wire-резерва очереди не освобождает это состояние. Поток уникальных `session.tool.input.ended` до первого завершённого вызова обходит оба новых лимита.
>    - **Исправление:** ограничить количество native-вызовов и совокупный размер удерживаемых аргументов, включая замену существующего значения и оба пути потребления событий.
>    - **Критерий проверки:** поток уникальных незавершённых native-вызовов превышает установленный предел, завершается управляемой ошибкой и cleanup; потребление памяти имеет вычислимую верхнюю границу.

### F-008
- origin: visionary · R1 · visionary-F-007
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
> **F-007 — [pre-existing] Блокирующая запись клиенту обходит watchdog и общий deadline.**
>    - **priority:** blocking.
>    - **locations:** `bridges/opencode-zen-bridge/server.py:5835`, `:5998`, `:6595`.
>    - **Правило:** `feature.md` §2 — таймаут на каждом шаге I/O; ограниченное время владения ресурсами.
>    - **Evidence:** `_LockedWfile.write()` выполняет блокирующий `inner.write()` под замком. Callback reasoning вызывается из контролирующего цикла попытки. При клиенте, который сохраняет соединение, но прекращает читать, заполнение TCP-буфера останавливает цикл до следующей проверки deadline/watchdog. Таймер статуса использует ту же блокирующую запись.
>    - **Исправление:** ограничить downstream-запись оставшимся сроком и обеспечить отмену, которая не зависит от освобождения того же замка.
>    - **Критерий проверки:** реальный сокетный клиент прекращает чтение после заголовков; достаточно большой поток приводит к ограниченному завершению, остановке группы и возврату слота.
ARTIFACT_END>>>
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/cycle-9/recheck-r1.md sha256=dbbaab6f49d03154b5628cec9aead5c9546871f40a5049c22fa7541b8d36be79
# Механический RECHECK после R1 Совета Тимлидов по коду (цикл 9, run analyst-teamlead-zen-realtime-reasoning-20261025)

- Проверяемый артефакт: `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/package.md` (`sha256=35adea8bc3197709e42854cde111e17b0cdaba1febb6fa6f0f8e9ff7f52bd202`)
- Длина файлов кандидата: `server.py` = `8295` строк, `tests/test_realtime_reasoning.py` = `3629` строк, `tests/test_step_interruption.py` = `1088` строк.
- Дельта `coder-12` (Цикл 9 относительно Цикла 8 `coder-11`): в `server.py` изменены только `_drain_serve_step_usage` / `_finish_serve_tool_step` (`3345-3530`), `_serve_accumulated_bytes` / лимит очереди (`3154-3175`, `3445-3460`), ре-чек дедлайна до `note_spawn` (`5540-5590`, `6770-6820`) и ветка `state == "timeout"` в JSON (`7945-7965`). Строки `_strip_interrupted` (`5708`, `5988`, `7005`), `_open_serve_events` (`3232-3240`) и `_LockedWfile.write` (`5835`) не менялись в Цикле 9 и присутствовали без замечаний в предыдущих циклах (`council.md` §3 «Diff-scope повторного цикла»).

RECHECK F-001 (skeptic skeptic-F-001, blocking): `server.py:3373` → `if data.get("sessionID") != session_id or (` | F-001
RECHECK F-002 (visionary visionary-F-001, blocking): `server.py:3373` → `if data.get("sessionID") != session_id or (` | **F-001 — [pre-existing] Потеря ошибок и управляющих событий при дочитывании шага.**
RECHECK F-003 (visionary visionary-F-002, blocking): `server.py:3390` → `on_tool(done[1])` | **F-002 — Неподтверждённые tool calls переживают неуспешную попытку.**
RECHECK F-004 (visionary visionary-F-003, blocking): `server.py:5708` → `rtext = _strip_interrupted(rtext)` | **F-003 — [pre-existing] Изменяются модельные байты reasoning.**
RECHECK F-005 (visionary visionary-F-004, non-blocking): проверка по полному тексту `package.md` (`candidate.diff` / `verification-traceability.md` / `execution-evidence.md`) | **F-004 — Устаревшие ссылки матрицы прослеживаемости.**
RECHECK F-006 (visionary visionary-F-005, blocking): `server.py:3232` → `"127.0.0.1",` | **F-005 — [pre-existing] Не выполняется бюджет вспомогательного I/O.**
RECHECK F-007 (visionary visionary-F-006, blocking): `server.py:3154` → `self.tools: dict[str, _ToolItem] = {}` | **F-006 — [pre-existing] Байтовый предел не охватывает накопление native-инструментов.**
RECHECK F-008 (visionary visionary-F-007, blocking): `server.py:5835` → `return int(self._inner.write(data) or 0)` | **F-007 — [pre-existing] Блокирующая запись клиенту обходит watchdog и общий deadline.**
ARTIFACT_END>>>

РАУНД: D1 из ≤2; последний: нет; место: skeptic
ПОЗИЦИИ ТРЕБУЮТСЯ ПО: F-002, F-003, F-004, F-005, F-006, F-007, F-008; N=7
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

### Независимая перепроверка SEED и ranked_order (обязанность места №1 по рангу, models.md#L121-L138 и select_round_seats.py#L903-L917)
Твоё место занимает старшую выбранную позицию в `ranked_order` раунда (`seed_recheck_duty: да`). По приложенным выше `~/Мой диск/Context/models.md#L121-L138`, `~/Мой диск/skils/ai-sdlc/universal/teamlead-gate/scripts/select_round_seats.py#L903-L917` и `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/panel/council/r144/manifest.json` независимо пересчитай `seed_hex = SHA-256(seed_input)` (и первые 8 hex `SEED`) и сверь `ranked_order` для дословной строки `seed_input`:
`analyst-teamlead-zen-realtime-reasoning-20261025:council:r144:35adea8bc3197709e42854cde111e17b0cdaba1febb6fa6f0f8e9ff7f52bd202:192905fa61bfc7dfc2781161fc4109249ba7c2f4a357e6ddb1aaf90d88099171`
Укажи результат сверки (`SEED`/`seed_hex` и совпадение `ranked_order`) одной строкой в обосновании критерия 6 (`СООТВЕТСТВИЕ КОНТЕКСТУ`).

По п.6 блока «ПРАВИЛА ДЕБАТОВ» выведи строки позиций по всем 7 находкам из строки `ПОЗИЦИИ ТРЕБУЮТСЯ ПО` (и свои `WITHDRAW`/`AMEND` при пересмотре собственных находок R1 с учётом `RECHECK`, правила `council.md` §3 «Diff-scope повторного цикла» и аргументов коллег), затем блок 6 критериев `ФОРМАТ ОТВЕТА`, затем обязательные строки `POSITIONS: 7/7` и `ANSWERS: 0/0`, а последней непустой строкой ответа выведи канонический вердикт `ОБЩИЙ ВЕРДИКТ: ACCEPT`, `ОБЩИЙ ВЕРДИКТ: PASS`, `ОБЩИЙ ВЕРДИКТ: NEEDS WORK` или `ОБЩИЙ ВЕРДИКТ: RED FLAG` (без точки и комментариев в той же строке).

---
PRIOR-LEDGER-SHA256: 7f475c159cab80c89fc6f099c13691b78fd15ec8351e108667b6fe43c6c774c4
PANEL-NONCE: cf8f1adc0541a7a8
ARTIFACT-SHA256: 35adea8bc3197709e42854cde111e17b0cdaba1febb6fa6f0f8e9ff7f52bd202
Инструкция судье: первыми двумя строками ответа повтори дословно «PANEL-NONCE: cf8f1adc0541a7a8» и «ARTIFACT-SHA256: 35adea8bc3197709e42854cde111e17b0cdaba1febb6fa6f0f8e9ff7f52bd202».
