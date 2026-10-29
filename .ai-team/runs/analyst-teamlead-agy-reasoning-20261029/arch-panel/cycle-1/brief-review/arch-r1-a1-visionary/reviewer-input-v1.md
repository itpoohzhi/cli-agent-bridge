# Задача: Независимое ревью брифа судьи (`brief-review`, `run_kind="full"`, `panel=arch`, `round=R1`, `hat=visionary`)

Прочитай и проверь по чек-листу `checklist-g1.md` бриф судьи в каталоге `/Users/aazhiry1/tmp/cli-agent-bridge/agy-realtime-reasoning/.ai-team/runs/analyst-teamlead-agy-reasoning-20261029/arch-panel/cycle-1/brief-review/arch-r1-a1-visionary`:
- Проверяемый бриф: `/Users/aazhiry1/tmp/cli-agent-bridge/agy-realtime-reasoning/.ai-team/runs/analyst-teamlead-agy-reasoning-20261029/arch-panel/cycle-1/brief-review/arch-r1-a1-visionary/brief-v1.md` (`sha256=197b2f35aa587c5cf9729bd635068a3a6b276d2f144fff6fe98c0044161e0c63`)
- Чек-лист: `/Users/aazhiry1/tmp/cli-agent-bridge/agy-realtime-reasoning/.ai-team/runs/analyst-teamlead-agy-reasoning-20261029/arch-panel/cycle-1/brief-review/arch-r1-a1-visionary/checklist-g1.md` (`sha256=feddc9f2bad66dcbc99e7ff8f1b49d904a9dd3cffd2ff01d1d1f918be4263f0f`)
- Результаты пре-линта `[L]`: `/Users/aazhiry1/tmp/cli-agent-bridge/agy-realtime-reasoning/.ai-team/runs/analyst-teamlead-agy-reasoning-20261029/arch-panel/cycle-1/brief-review/arch-r1-a1-visionary/prelint-v1.md`

## Чек-лист `checklist-g1.md`:
```markdown
# Чек-лист brief-review: arch R1, cycle 1, run analyst-teamlead-agy-reasoning-20261029, поколение g1
## Пре-линт [L]
SK-A-02 [L] | обёртки D9 целых файлов Architecture Packet и receipt ARCH_GATE + sha256 == packet_sha256 | источник: brief-review/references/checklist-sources.md#SK-A
SK-A-12 [L] | сравнение строк seat_slot (gpt-6.1-sol-high) != architect_slot (claude-opus-5-5-high) | источник: brief-review/references/checklist-sources.md#SK-A
JD-01 [L] | побайтное сравнение начала brief-v1.md с prompt-visionary.txt + пустая строка | источник: brief-review/references/checklist-sources.md#JD
HY-01 [L] | N/A для CLI-слота gpt-6.1-sol-high | источник: brief-review/references/checklist-sources.md#HY
HY-03 [L] | отсутствие токенов закрытого списка плейсхолдеров вне блоков <<<ARTIFACT ... ARTIFACT_END>>> | источник: brief-review/references/checklist-sources.md#HY
## BR — бизнес-требования
BR-01 [P] | Реалтайм-стриминг размышлений (`reasoning_content`) `gemini-4-argon` через `agy-bridge (:9887)` в DSH из SQLite `conversations/<cid>.db` (`step_payload` 20.3) во время `status=8` (`RC-1`) | источник: /tmp/cel-runs/analyst-teamlead-agy-reasoning-20261029/goal.md#L7
BR-02 [P] | Устранение гонки финального дренирования `Run._pump` и `_TranscriptTail` (`RC-2`), учёт `reasoning` в `delivered` (`RC-3`), изоляция `sess_key` от фоновых запросов без `tools` (`RC-4`) | источник: analysis/agy-realtime-reasoning/handoff-architect.md#L14-L20
BR-03 [P] | Все 12 требований `REQ-001..REQ-012` и критерии `AC-001..AC-016` присутствуют в брифе | источник: analysis/agy-realtime-reasoning/handoff-architect.md#L53-L66
BR-04 [P] | Конверт `HL-ENV/v1` из 46 полей и инварианты Python-профиля `aisdlc-gcge/skills/architecture.md` | источник: analysis/agy-realtime-reasoning/handoff-architect.md#L135-L215
## JD — пункты места
JD-02 [N] | Нет промпта другой шляпы и нет двух ролей в одном брифе | источник: brief-review/references/checklist-sources.md#JD
JD-03 [P] | «суди ЗАНОВО, не подтверждай прошлый вердикт автоматически» | источник: brief-review/references/checklist-sources.md#JD
JD-04 [P] | Ровно один блок «ФОРМАТ ОТВЕТА (строго)» на весь brief-v1.md | источник: brief-review/references/checklist-sources.md#JD
JD-05 [P/N] | seed_recheck_duty: да | источник: brief-review/references/checklist-sources.md#JD
JD-06 [N] | R1: чужих вердиктов нет | источник: brief-review/references/checklist-sources.md#JD
JD-07 [P] | Факт-карта, строка `РЕЖИМ: architecture`, секция КОНТЕКСТ присутствуют | источник: brief-review/references/checklist-sources.md#JD
JD-08 [N] | Бриф самодостаточен, все первичные артефакты вложены целиком | источник: brief-review/references/checklist-sources.md#JD
## HY — гигиена
HY-02 [N] | Нет противоречий между разделами | источник: brief-review/references/checklist-sources.md#HY
HY-04 [N] | Нет секретов | источник: brief-review/references/checklist-sources.md#HY
HY-05 [N] | Нет следов brief-review | источник: brief-review/references/checklist-sources.md#HY
HY-06 [N] | Формулировки чек-листа не вставлены без первичного артефакта | источник: brief-review/references/checklist-sources.md#HY
## Параметры места
panel: arch | round: R1 | round_type: R1 | hat: visionary
hat_prompt: ~/work/universal-panel/prompt-visionary.txt
seat_slot: gpt-6.1-sol-high
seat_kind: panel-judge
seed_recheck_duty: да | ranked_position: 3 из 3
architect_slot: claude-opus-5-5-high

```

## Результаты пре-линта `prelint-v1.md`:
```markdown
# Пре-линт brief-review [L]: arch R1, cycle 1, a1, место visionary (v1)

| ID | Метод | Результат |
|---|---|---|
| SK-A-02 | D9 обёртки Architecture Packet и arch-gate.json (sha256 == f0471a6116bcea5831736dee36a85386c27f2758b7c41fdc354e96aa793229f4) | pass |
| SK-A-12 | seat_slot (gpt-6.1-sol-high) != architect_slot (claude-opus-5-5-high) | pass |
| JD-01 | prompt-visionary.txt + пустая строка, ФОРМАТ ОТВЕТА == 1 | pass |
| HY-01 | стримящий/CLI слот (gpt-6.1-sol-high), не hermes -z | N/A |
| HY-03 | закрытый список плейсхолдеров вне ARTIFACT | pass |

ИТОГ ПРЕ-ЛИНТА: PASS

```

## Начало и конец `brief-v1.md` (а также список вложенных `<<<ARTIFACT` блоков):
```markdown
Ты — Визионер. Твоя задача — оценить потенциал, масштаб, стратегическое влияние. Ключевой вопрос: «Насколько это меняет игру?»

Ты оцениваешь архитектуру, а не код. Фокусируйся на долгосрочной ценности: насколько решение масштабируемо, какие возможности открывает, насколько опережает альтернативы, есть ли потенциал для роста.

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

РЕШЕНИЕ ДЛЯ ОЦЕНКИ:
Ниже приложены целиком (без обрезки; раздел «Не вложено» пуст — все первичные артефакты даны полностью в этом брифе) проверяемый Architecture Packet и квитанция пройденного гейта `ARCH_GATE`:

<<<ARTIFACT .ai-team/runs/analyst-teamlead-agy-reasoning-20261029/architecture/architecture-packet.json sha256=f0471a6116bcea5831736dee36a85386c27f2758b7c41fdc354e96aa793229f4
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
    "sha256": "d17625f4424c6d8423f9f98142fa4153e12c0136a470d746082e7269b0225e23"
  },
  "summary": "Реалтайм-мышление agy-bridge (:9887) для gemini-4-argon: live-источник conversations/<cid>.db (steps.step_payload, поле 20 → подполе 3) на stdlib sqlite3 + pure-Python wire-парсер, fail-open и за фичефлагом SQLITE_REASONING_ENABLED (код default=false, runtime dynamic_config.json, env-override AGY_BRIDGE_SQLITE_REASONING); детерминированный ограниченный финальный drain источников до done (≤1.0 с); отданное reasoning считается выдачей (нет невидимого retry); изоляция горячих сессий по признаку tools и обход стора для one-shot фоновых запросов. Публичный HTTP/SSE контракт не меняется. Все решения two-way; пакет — кандидат для downstream Совета, не вердикт Совета.",
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
      "bridges/agy-bridge/fleet.json, bridges/agy-bridge/start.sh, ruff.toml (хеш
...
[Вложены целиком блоки <<<ARTIFACT: architecture-packet.json, arch-gate.json, goal.md, task.json, handoff-architect.md, evidence-ledger.md, research-plan.md, open-questions.md, handoff-qa.md, aisdlc-gcge/AGENTS.md, aisdlc-gcge/skills/architecture.md, aisdlc-gcge/agents/scope-and-contracts.md, arch-council.md#L25-L31, council.md#L95-L114]
...
IL без привязки к разделу пакета / `[F-NN]` / правилу не засчитывается.
- FAIL без оговорок: (1) пакет меняет согласованный внешний контракт без явного указания в постановке задачи (`scope-and-contracts.md`); (2) работа или пакет выходит за рамки текущей задачи.
- Оцени все 6 критериев `universal-panel` (1. КОРРЕКТНОСТЬ, 2. ПОЛНОТА, 3. РЕАЛИЗУЕМОСТЬ, 4. РИСКИ, 5. АЛЬТЕРНАТИВЫ, 6. СООТВЕТСТВИЕ КОНТЕКСТУ) по единому блоку формата ответа из промпта твоей роли в начале брифа.

<<<ARTIFACT ~/Мой диск/skils/ai-sdlc/universal/teamlead-with-architect/references/arch-council.md#L25-L31 sha256=2938e840cbd02bff4ae6fa9bbf158560ba506c615e302ed99fac607bf7a08dc7
- mode.txt = architecture; Альтернативы/Риски ×1.5, два усиленных FAIL = RED FLAG.
- ARCH_ROOT = <RUN>/arch-panel/cycle-<N>/a<A>/; A — arch_panel_to_architect, первый a1; тот же индекс в brief-review.
- Вердикт → summarizer → Architect, не Coder.

## 1a. Выход после R1 и обязательный маршрут (единый инвариант)

Вход: три валидных R1, достоверный consensus-ledger.md с lineage и transport proof PASS. PASS считается по вердиктам мест (APPROVE/ACCEPT); OPEN_BLOCKING/CONFLICT — по открытым находкам.
ARTIFACT_END>>>

<<<ARTIFACT ~/Мой диск/skils/ai-sdlc/universal/teamlead-gate/references/council.md#L95-L114 sha256=f83795a3eb87705bd3a1e9c766a286354f0717813c9f36842478fc661866f6d4
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
ARTIFACT_END>>>
Примечание для режима `arch`: в блоке «ПОЛНОТА ВЫДАЧИ» выше слово «diff» читается как «Architecture Packet», а вместо `file:line` используются допустимые якоря (а)–(г) из блока «ЯКОРЯ ПАКЕТА».

Итоговую строку общего вердикта выводи строго с одним из значений `PASS`, `NEEDS WORK` или `RED FLAG` (без точки и комментариев в той же строке), а сразу после неё — обязательные строки покрытия и числа находок из п.6 блока «ПОЛНОТА ВЫДАЧИ».

---
PANEL-NONCE: f59080f9c39fff6d
ARTIFACT-SHA256: f0471a6116bcea5831736dee36a85386c27f2758b7c41fdc354e96aa793229f4
Инструкция судье: первыми двумя строками ответа повтори дословно «PANEL-NONCE: f59080f9c39fff6d» и «ARTIFACT-SHA256: f0471a6116bcea5831736dee36a85386c27f2758b7c41fdc354e96aa793229f4».

```

Выдай ТОЛЬКО валидный JSON-объект со следующей структурой (без markdown-обёрток или в блоке ```json):
- `items`: массив объектов `{"id": "<ID из чек-листа BR-01..04, JD-02..08, HY-02..06>", "status": "covered"|"missing"|"violated", "evidence_quote": "<цитата из брифа для [P] или пустая строка для [N]>", "fix": ""}`
- `unmapped_requirements`: `[]`
- `bloat_flags`: `[]`
- `leakage_flags`: `[]`
- `model_verdict`: `"APPROVE"` или `"REJECT"`
