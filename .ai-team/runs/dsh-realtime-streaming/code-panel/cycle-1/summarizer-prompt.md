Read-only besides the one output file. Секреты не печатай. Субагентов не запускай.

Ты panel-rework-summarizer (слот gpt-6.1-sol).
Переведи NEEDS WORK Кодовой панели техлидов (Раунд 1) в ОДИН валидный JSON-объект для Coder.

Входы обязательные:
- .ai-team/runs/dsh-realtime-streaming/code-panel/cycle-1/verdict-c1r1.md
- .ai-team/runs/dsh-realtime-streaming/code-panel/cycle-1/findings-ledger.md
- .ai-team/runs/dsh-realtime-streaming/code-panel/cycle-1/diff.patch

Выход:
Запиши ровно один JSON object в:
.ai-team/runs/dsh-realtime-streaming/handoff/panel-rework-brief-code-c1.json

Без markdown fence, без второго объекта, без прозы вокруг.

Обязательные поля корня:
- schema_version: "1.0"
- run_id: "dsh-realtime-streaming"
- teamlead_cycle: 1
- panel_slug: "dsh-realtime-streaming-code-panel-1-r1"
- panel_verdict: "NEEDS_WORK"
- summarizer_slot: "gpt-6.1-sol"
- coder_entry: "fix-from-panel"
- iteration_budget_note: "Code panel round 1 returned NEEDS WORK. 6 blocking findings to be addressed by Coder."
- findings_total: 7
- instructions: список RW-NNN для 6 blocking находок (F-201..F-206).
  Каждый instruction:
  - id: "RW-201", "RW-202", ...
  - priority: "blocking"
  - criterion: один из ["КОРРЕКТНОСТЬ", "ПОЛНОТА", "ЧИТАЕМОСТЬ", "ПРОИЗВОДИТЕЛЬНОСТЬ", "ТЕСТИРУЕМОСТЬ", "СООТВЕТСТВИЕ АРХИТЕКТУРЕ"]
  - file: путь к файлу ("server.py", "tests/test_live_stream.py", etc.)
  - line_hint: место в коде
  - rule_ref: ссылка на правило/инвариант (RW-009, AD-001, AD-002, AD-003, etc.)
  - action: конкретное действие для Coder
  - acceptance: критерий приёмки
  - source: цитата/название замечания
  - evidence: ссылка file:line
  - source_findings: ["F-201"], ["F-202"], и т.д.
- non_blocking_followups: список FU-NNN для non-blocking находки F-207 (restore server.MAX_CONCURRENT в tearDown).
- excluded: []
- do_not_change: ["server.py:_serve_json nonstream flow", "core/metrics_normalizer.py:normalize_prompt_cache_details"]

Проверь файл скриптом:
python3 "/Users/aazhiry1/Мой диск/skils/ai-sdlc/universal/teamlead-gate/scripts/validate_panel_rework_brief.py" \
  .ai-team/runs/dsh-realtime-streaming/handoff/panel-rework-brief-code-c1.json \
  --expected-slot gpt-6.1-sol \
  --ledger .ai-team/runs/dsh-realtime-streaming/code-panel/cycle-1/findings-ledger.md
