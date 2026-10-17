Read-only besides the one output file. Секреты не печатай. Субагентов не запускай.

Ты panel-rework-summarizer (слот gemini-4-argon-high).
Переведи NEEDS WORK совета в ОДИН JSON-объект для Coder.

Контракт и пример валидного объекта:
/Users/aazhiry1/Мой диск/skils/ai-sdlc/references/panel-rework-brief.md
(в teamlead-gate критерий ACCEPT brief — PASS проверки из references/council-gates.md,
раздел «Проверка контракта brief»; роль скрипта — контракт, «Критерий ACCEPT brief»;
раскладка council-consensus §10 имеет приоритет над общим правилом трансляции контракта «замечание
с file/line/правилом → instructions blocking»: согласованный non-blocking → non_blocking_followups,
excluded → excluded[])

Входы обязательные (прочитай):
- /Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/muse-wonder-foreign-session-20261014/task.json
- /Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/muse-wonder-foreign-session-20261014/panel/council/r1/verdict.md
- /Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/muse-wonder-foreign-session-20261014/panel/council/r1/seats/1/verdict.md
- /Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/muse-wonder-foreign-session-20261014/panel/council/r1/seats/2/verdict.md
- /Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/muse-wonder-foreign-session-20261014/panel/council/r1/seats/3/verdict.md
- /Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/muse-wonder-foreign-session-20261014/panel/council/r1/findings-ledger.md
- diff: /Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/muse-wonder-foreign-session-20261014/code-diff.patch

Правила трансляции — из контракта. Не сглаживай противоречия судей.
ПОЛНОТА БАТЧА: вход — ВСЕ F-NNN судей из r1/r2/minority/verdict. Один бриф на весь
батч. Запрещен отсев топ-N, отсрочка или склейка разных причин. Каждый F-NNN леджера
должен быть отражен РОВНО ОДИН раз: в source_findings пункта instructions[] или
non_blocking_followups[], либо в excluded[] с reason из перечня: invalid_after_recheck |
out_of_scope | foreign_key | duplicate_of:F-NNN (id обязан быть в леджере). Покрытие
считается только по source_findings и excluded[].id (упоминание в тексте source не
покрывает); один F-NNN не может быть и в instructions/follow-ups, и в excluded.
findings_total равен числу F-NNN леджера (не меньше и не больше).
Координатор замечания сам не переводит — это твоя единственная работа.

Выход:
1. Запиши ровно один JSON object в
   /Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/muse-wonder-foreign-session-20261014/handoff/panel-rework-brief.json.tmp
   Без markdown fence, без второго объекта, без прозы вокруг.
2. Обязательные поля корня и instructions[] — как в контракте:
   schema_version "1.0",
   run_id "muse-wonder-foreign-session-20261014",
   teamlead_cycle 1,
   panel_slug "muse-wonder-foreign-session-20261014-council-1",
   panel_verdict "NEEDS_WORK",
   summarizer_slot "gemini-4-argon-high",
   coder_entry "fix-from-panel",
   iteration_budget_note "teamlead cycle 1 rework for Coder; blocking items from instructions[]",
   do_not_change: ["ALLOWED_MODELS context length 400000", "desktop/web cordis.patch.yml contextWindow 400000"],
   instructions: [ ... ],
   non_blocking_followups: [ ... ],
   findings_total 6
3. Сразу проверь файл по 9 критериям «Проверка контракта brief»
   (/Users/aazhiry1/Мой диск/skils/ai-sdlc/universal/teamlead-gate/references/council-gates.md,
   раздел «Проверка контракта brief»; леджер — /Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/muse-wonder-foreign-session-20261014/panel/council/r1/findings-ledger.md,
   слот — gemini-4-argon-high). Необязательный способ получить факт — скрипт:
   python3 "/Users/aazhiry1/Мой диск/skils/ai-sdlc/universal/teamlead-gate/scripts/validate_panel_rework_brief.py" \
     /Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/muse-wonder-foreign-session-20261014/handoff/panel-rework-brief.json.tmp \
     --expected-slot gemini-4-argon-high \
     --ledger /Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/muse-wonder-foreign-session-20261014/panel/council/r1/findings-ledger.md \
     --repo-root /Users/aazhiry1/work/src/cli-agent-bridge
4. Все критерии выполнены → атомарно замени целевой
   /Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/muse-wonder-foreign-session-20261014/handoff/panel-rework-brief.json
   иначе целевой путь не трогай и верни INVALID + список нарушенных критериев.

stdout: VALID n_instructions=N
