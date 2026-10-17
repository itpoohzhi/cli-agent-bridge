Read-only besides the one output file. Секреты не печатай. Субагентов не запускай.

Ты panel-rework-summarizer (слот gpt-6.1-sol).
Переведи NEEDS WORK Кодовой панели техлидов (Раунд 2) в ОДИН валидный JSON-объект для Coder.

Входы обязательные:
- .ai-team/runs/dsh-realtime-streaming/code-panel/cycle-1/verdict-c1r2.md
- .ai-team/runs/dsh-realtime-streaming/code-panel/cycle-1/findings-ledger-r2.md
- .ai-team/runs/dsh-realtime-streaming/code-panel/cycle-1/diff-r2.patch

Выход:
Запиши ровно один JSON object в:
.ai-team/runs/dsh-realtime-streaming/handoff/panel-rework-brief-code-c1r2.json

Без markdown fence, без второго объекта, без прозы вокруг.

Обязательные поля корня:
- schema_version: "1.0"
- run_id: "dsh-realtime-streaming"
- teamlead_cycle: 1
- panel_slug: "dsh-realtime-streaming-code-panel-1-r2"
- panel_verdict: "NEEDS_WORK"
- summarizer_slot: "gpt-6.1-sol"
- coder_entry: "fix-from-panel"
- iteration_budget_note: "Code panel round 2 returned NEEDS WORK. 3 blocking findings and 1 non-blocking followup to be addressed by Coder."
- findings_total: 4
- instructions: список RW-NNN для 3 blocking находок (F-203, F-208, F-211).
  Каждый instruction:
  - id: "RW-203", "RW-208", "RW-211"
  - priority: "blocking"
  - criterion: один из ["КОРРЕКТНОСТЬ", "ПОЛНОТА", "РЕАЛИЗУЕМОСТЬ", "РИСКИ", "СООТВЕТСТВИЕ КОНТЕКСТУ"]
  - file: путь к файлу ("server.py", etc.)
  - line_hint: место в коде
  - rule_ref: ссылка на правило/инвариант (AD-001, AD-003, RW-009, etc.)
  - action: конкретное действие для Coder
  - acceptance: критерий приёмки
  - source: цитата/название замечания
  - evidence: ссылка file:line
  - source_findings: ["F-203"], ["F-208"], ["F-211"]
- non_blocking_followups: список FU-NNN для non-blocking находки F-212 (тесты в tests/test_live_stream.py).
  Каждый followup:
  - id: "FU-212"
  - text: конкретное действие по расширению тестов
  - reason: обоснование
  - source_findings: ["F-212"]
- excluded: []
- do_not_change: ["server.py:_serve_json nonstream flow", "core/metrics_normalizer.py:normalize_prompt_cache_details", "adapters/muse_adapter.py"]

Проверь файл скриптом:
python3 "/Users/aazhiry1/Мой диск/skils/ai-sdlc/universal/teamlead-gate/scripts/validate_panel_rework_brief.py" \
  .ai-team/runs/dsh-realtime-streaming/handoff/panel-rework-brief-code-c1r2.json \
  --expected-slot gpt-6.1-sol \
  --ledger .ai-team/runs/dsh-realtime-streaming/code-panel/cycle-1/findings-ledger-r2.md
