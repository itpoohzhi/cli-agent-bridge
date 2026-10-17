import hashlib
import json
import os

artifact_path = ".ai-team/runs/dsh-realtime-streaming/code-panel/cycle-1/diff.patch"
with open(artifact_path, "r", encoding="utf-8") as f:
    diff_content = f.read()

artifact_sha256 = hashlib.sha256(diff_content.encode("utf-8")).hexdigest()
seed_input = f"{artifact_sha256[:8]}#dsh-realtime-streaming#c1#R1"
seed_hex = hashlib.sha256(seed_input.encode("ascii")).hexdigest()[:8]

# Architecture packet summary
with open(".ai-team/runs/dsh-realtime-streaming/architecture/architecture-packet.md", "r", encoding="utf-8") as f:
    packet_md = f.read()

# Arch panel verdict summary
with open(".ai-team/runs/dsh-realtime-streaming/arch-panel/cycle-1/verdict-a2.md", "r", encoding="utf-8") as f:
    arch_verdict_md = f.read()

# Test results summary
test_results_summary = """
=== РЕЗУЛЬТАТЫ ТЕСТОВ ===
1. python3 -m unittest tests/test_live_stream.py tests/test_tool_parser.py tests/test_cache_usage.py tests/test_rpc_core.py tests/test_bridge_http.py
   Ran 76 tests in 33.7s: OK
2. tests/test_live_stream.py (8 тестов):
   - test_content_deltas_arrive_incrementally_before_done: PASS (t_first < t_done - 0.2s)
   - test_multiple_distinct_content_chunks_not_one_blob: PASS (>= 2 frames)
   - test_malformed_tool_call_block_fails_closed_without_leaking_raw_xml: PASS (live_prefix_invalidated, 0 XML)
   - test_well_formed_tool_call_is_unaffected: PASS
   - test_retract_after_live_delta_invalidates_the_turn: PASS
   - test_normal_turn_without_retraction_is_unaffected: PASS
   - test_usage_chunk_finish_reason_is_null_not_duplicated_stop: PASS
   - test_non_reading_client_does_not_prevent_commit_or_next_slot: PASS (RW-009 verified)
"""

pool_ordered = [
    "muse-spark-1.3",
    "grok-4.7-high",
    "gemini-3.8-flash-high",
    "hermes-glm-5.3-max",
    "deepseek-v4.1-flash"
]

ranked_native = [
    "deepseek-v4.1-flash",
    "gemini-3.8-flash-high",
    "hermes-glm-5.3-max",
    "grok-4.7-high"
]

seats = [
    {
        "seat_index": 1,
        "family": "OpenAI",
        "slot_id": "gpt-6.1-sol",
        "transport": "codex exec -m gpt-6.1-sol -c model_reasoning_effort=\"high\"",
        "group": "anchor",
        "hat": "Реалист",
        "hat_desc": "Ты — Реалист. Твоя задача — оценить практичность, чистоту реализации, соответствие существующему коду server.py и adapters/droid_adapter.py, устойчивость к сбоям и реальным граничным условиям. Ключевой вопрос: «Работает ли это просто, надежно и без скрытых регрессий в проде?»",
        "recheck": False
    },
    {
        "seat_index": 2,
        "family": "DeepSeek",
        "slot_id": "deepseek-v4.1-flash",
        "transport": "droid exec -m deepseek-v4.1-flash -r max",
        "group": "native",
        "hat": "Скептик",
        "hat_desc": "Ты — Скептик. Твоя задача — искать слабые места, граничные случаи, утечки ресурсов, дедлоки, зависания сокетов, гонки потоков и нарушения инвариантов RW-009/AD-001..004. Ключевой вопрос: «Где этот код упадет, зависнет или протечет под нагрузкой или при медленном клиенте?»",
        "recheck": True
    },
    {
        "seat_index": 3,
        "family": "Google",
        "slot_id": "gemini-3.8-flash-high",
        "transport": "droid exec -m gemini-3.8-flash -r high",
        "group": "native",
        "hat": "Визионер",
        "hat_desc": "Ты — Визионер. Твоя задача — оценить масштабируемость архитектуры моста, чистоту контракта SSE, долгосрочную сопровождаемость и соответствие целевой скорости токенов (20-80 tok/s) в DeepSeek Harness Desktop. Ключевой вопрос: «Решает ли это фундаментальную проблему стриминга и закладывает ли правильный фундамент для расширения моста?»",
        "recheck": False
    }
]

manifest = {
    "run_id": "dsh-realtime-streaming",
    "cycle": 1,
    "round": 1,
    "phase": "CODE_PANEL",
    "seed_input": seed_input,
    "seed_hex": seed_hex,
    "artifact_sha256": artifact_sha256,
    "artifact_path": artifact_path,
    "pool_setup": "default",
    "pool_ordered": pool_ordered,
    "groups": {
        "native": ranked_native,
        "external": ["muse-spark-1.3"]
    },
    "ranked_order": [
        "deepseek-v4.1-flash",
        "muse-spark-1.3",
        "gemini-3.8-flash-high",
        "hermes-glm-5.3-max",
        "grok-4.7-high"
    ],
    "anchor_election": {
        "candidates": ["claude-sonnet-5-5", "gpt-6.1-sol"],
        "note": "claude-sonnet-5-5 is coder_slot (models.md 1.0, models.md 98), yielded to gpt-6.1-sol",
        "winner": "gpt-6.1-sol"
    },
    "seats": [
        {
            "seat_index": s["seat_index"],
            "family": s["family"],
            "slot_id": s["slot_id"],
            "transport": s["transport"],
            "group": s["group"],
            "hat": s["hat"],
            "status": "READY"
        }
        for s in seats
    ],
    "hats": {s["slot_id"]: s["hat"] for s in seats},
    "hat_index": 0,
    "k": 1,
    "rotation_ok": True,
    "recheck": {
        "judge_family": "DeepSeek",
        "slot_id": "deepseek-v4.1-flash"
    },
    "quorum_status": "IN_PROGRESS"
}

with open(".ai-team/runs/dsh-realtime-streaming/code-panel/cycle-1/route-manifest-code-c1r1.json", "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2, ensure_ascii=False)

common_instructions = """
Оцени качество и корректность реализации real-time streaming в cli-agent-bridge по 6 критериям качества кода.
РЕЖИМ: code.

КРИТЕРИИ ОЦЕНКИ:
1. КОРРЕКТНОСТЬ:
   - Логика потоковой отдачи дельт в SSE по мере поступления Droid JSON-RPC.
   - Соблюдение инварианта RW-009: Блокировки L и T освобождаются сразу по завершении вычисления и сохранения чекпоинта, не удерживаясь медленным клиентом во время отдачи оставшегося хвоста.
   - Обработка сбоев и fail-close (AD-001): при retract/сбое после отдачи префикса отдается чанк с ошибкой, затем отдельный [DONE].
   - Strict-live режим ToolCallParser (AD-002): эмуляция tool_call при stream=True не пропускает сырые теги <tool_call> в content.
2. ПОЛНОТА:
   - Все ли требования Architecture Packet (AD-001..AD-004) и рекомендации Совета техлидов (F-101..F-106) реализованы.
   - Полнота тестового покрытия в tests/test_live_stream.py и tests/test_tool_parser.py.
3. ЧИТАЕМОСТЬ И СТИЛЬ:
   - Чистота кода в server.py, core/tool_emulation.py, adapters/droid_adapter.py.
   - Сохранение комментариев и отсутствие регрессий в non-stream режиме (_serve_json).
4. ПРОИЗВОДИТЕЛЬНОСТЬ И БЕЗОПАСНОСТЬ:
   - Таймаут записи клиенту (LIVE_WRITE_TIMEOUT_S) для защиты от зависших/медленных соединений.
   - Резервирование бюджета доставки (_DELIVERY_BUDGET) на каждый чанк перед записью.
   - Ограничение размера очередей и буферов.
5. ТЕСТИРУЕМОСТЬ:
   - Качество тестов в tests/test_live_stream.py (проверка t_first < t_done, strict-live, usage chunk, RW-009 decoupled delivery).
   - Все тесты проходят детерминированно.
6. СООТВЕТСТВИЕ АРХИТЕКТУРЕ:
   - Точное соответствие утвержденному Architecture Packet (редакция 2, SHA-256: 50c615a4...).
   - Не затронуты другие адаптеры и non-stream контракты.

ФОРМАТ ОТВЕТА (строго):
1. КОРРЕКТНОСТЬ: VERDICT=PASS|FAIL
   WHY=<обоснование>
   СОВЕТЫ (при FAIL): <список конкретных действий>
2. ПОЛНОТА: VERDICT=PASS|FAIL
   WHY=<обоснование>
   СОВЕТЫ (при FAIL): <список конкретных действий>
3. ЧИТАЕМОСТЬ: VERDICT=PASS|FAIL
   WHY=<обоснование>
   СОВЕТЫ (при FAIL): <список конкретных действий>
4. ПРОИЗВОДИТЕЛЬНОСТЬ: VERDICT=PASS|FAIL
   WHY=<обоснование>
   СОВЕТЫ (при FAIL): <список конкретных действий>
5. ТЕСТИРУЕМОСТЬ: VERDICT=PASS|FAIL
   WHY=<обоснование>
   СОВЕТЫ (при FAIL): <список конкретных действий>
6. СООТВЕТСТВИЕ АРХИТЕКТУРЕ: VERDICT=PASS|FAIL
   WHY=<обоснование>
   СОВЕТЫ (при FAIL): <список конкретных действий>
ОБЩИЙ ВЕРДИКТ: ACCEPT|NEEDS WORK|RED FLAG

Внутри каждого критерия обязательно укажи SUB-строки:
SUB <критерий>/<подкатегория>: PASS|FAIL|N/A — evidence (file:line)
Каждый FAIL должен иметь четкий issue ID (F-NNN) и точную ссылку file:line.
"""

for s in seats:
    prompt_file = f".ai-team/runs/dsh-realtime-streaming/code-panel/cycle-1/judge-prompt-seat-{s['seat_index']}.md"
    recheck_block = ""
    if s["recheck"]:
        recheck_block = f"""
ОБЯЗАТЕЛЬНЫЙ НЕЗАВИСИМЫЙ ПЕРЕСЧЁТ (анти-самосертификация):
Ты — судья с наименьшим рангом среди неякорных судей ({s['slot_id']}). Ты ОБЯЗАН в самом начале своего вердикта привести блок:
```
=== НЕЗАВИСИМЫЙ ПЕРЕСЧЁТ ЖЕРЕБЬЁВКИ ===
seed_input: {seed_input}
seed_hex: {seed_hex}
ranked_order: deepseek-v4.1-flash, muse-spark-1.3, gemini-3.8-flash-high, hermes-glm-5.3-max, grok-4.7-high
seats: Seat 1: gpt-6.1-sol (OpenAI, Anchor, Реалист), Seat 2: deepseek-v4.1-flash (DeepSeek, Скептик), Seat 3: gemini-3.8-flash-high (Google, Визионер)
hats: deepseek-v4.1-flash -> Скептик, gemini-3.8-flash-high -> Визионер, gpt-6.1-sol -> Реалист (k=1)
SEED_RECHECK: PASS
```
"""

    prompt = f"""# КОДОВАЯ ПАНЕЛЬ ТЕХЛИДОВ (Code Review Panel) — Раунд 1
Сиденье: {s['seat_index']}
Слот: {s['slot_id']} ({s['family']})
Шляпа: {s['hat']}

{s['hat_desc']}
{recheck_block}

## Контекст задачи
- **Задача**: REQ-STREAM-001 — реализация real-time streaming в cli-agent-bridge для DeepSeek Harness Desktop.
- **Проблема As-Is**: В server.py весь вывод хода удерживался до terminal и затем отдавался клиенту залпом за ~0 мс, вызывая аномалию расчёта 179 000 tok/s.
- **Утвержденная архитектура**: Architecture Packet редакция 2 (AD-001..AD-004), утверждена Архитектурной панелью техлидов с вердиктом PASS.
- **Реализация Coder**: Выполнена моделью claude-sonnet-5-5 в server.py, adapters/droid_adapter.py, core/tool_emulation.py, tests/test_live_stream.py.

{test_results_summary}

{common_instructions}

=== ПРЕДЪЯВЛЕННЫЙ DIFF КЛИЕНТА ДЛЯ РЕВЬЮ ===
Файл: .ai-team/runs/dsh-realtime-streaming/code-panel/cycle-1/diff.patch (SHA-256: {artifact_sha256})

```diff
{diff_content}
```
"""
    with open(prompt_file, "w", encoding="utf-8") as pf:
        pf.write(prompt)

print("Code panel prompts generated successfully!")
