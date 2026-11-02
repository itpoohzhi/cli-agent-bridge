"""tests/test_stream_formatting_and_subagents.py — Сквозные синтетические e2e-тесты (L2)

Проверяет:
1. Разграничение шагов Markdown (\\n\\n, отсутствие склейки слов вида "данных.Проверяю").
2. Исключение зацикливания префиксов оркестрации ("[гейт оркестрации: активен...").
3. Семантическую изоляцию reasoning при вызовах инструментов (сохранение блока <Think> в UI).
4. Жизненный цикл мультиагентных сессий (сабагенты, вызовы инструментов и непрерывность потока).
"""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import queue
import re
import sys
import threading
import unittest
from types import SimpleNamespace
from typing import Any, cast

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

_BRIDGE_PY = _REPO_ROOT / "bridges" / "agy-bridge" / "server.py"


def _load_bridge() -> Any:
    os.environ.setdefault("AGY_BRIDGE_KEY", "test-key-stream-e2e")
    spec = importlib.util.spec_from_file_location(
        "agy_bridge_server_e2e_under_test", _BRIDGE_PY
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


srv = _load_bridge()


class SyntheticE2EAgentStreamTests(unittest.TestCase):
    """Сквозные сценарные тесты стриминга агента, сабагентов и скиллов оркестрации."""

    def test_e2e_multi_step_markdown_boundary_separation(self) -> None:
        """Сквозная проверка: шаги агента разделяются \\n\\n, слова на стыках не склеиваются."""
        run = object.__new__(srv.Run)
        setattr(run, "_emit_lock", threading.Lock())
        setattr(run, "q", queue.Queue())
        setattr(run, "drain_closed", False)
        setattr(run, "_done_put", False)
        setattr(run, "_reasoning_bytes", 0)
        setattr(run, "_cap_logged", False)
        setattr(run, "_tail", SimpleNamespace(cid="cid-test-e2e"))
        setattr(run, "_arbiter", srv._ContentArbiter("turn-e2e-1"))
        setattr(run, "turn_id", "turn-e2e-1")
        setattr(run, "run_cid", "cid-test-e2e")
        setattr(run, "_last_step_index", None)
        setattr(run, "_content_emitted_wire", "")

        # Эмулируем шаги из скриншота пользователя:
        # Шаг 1: "Ищу в базе знаний и git посл"
        run.offer_content("stdout", 1, "Ищу в базе знаний и git посл")
        # Шаг 1 (продолжение): "Проверяю результаты поиска по переезду базы данных."
        run.offer_content("stdout", 1, "Ищу в базе знаний и git послПроверяю результаты поиска по переезду базы данных.")
        # Шаг 2: "Проверяю вывод лога задачи 349." (начинается с заглавной буквы)
        run.offer_content("stdout", 2, "Проверяю вывод лога задачи 349.")
        # Шаг 3: "Останавливаю фоновую задачу поиска. Читаю параллельно все об..."
        run.offer_content("stdout", 3, "Останавливаю фоновую задачу поиска. Читаю параллельно все об...")

        q = cast("queue.Queue[tuple[str, object]]", getattr(run, "q"))
        emitted_chunks: list[str] = []
        while not q.empty():
            item = q.get_nowait()
            if item[0] == "text":
                emitted_chunks.append(str(item[1]))

        full_stream = "".join(emitted_chunks)

        # 1. Проверяем, что нет дефекта склеивания точки и заглавной буквы без переноса строк
        glued_pattern = re.compile(r"[а-яёa-z]\.[А-ЯЁA-Z]")
        self.assertIsNone(
            glued_pattern.search(full_stream),
            f"Обнаружена склейка слов на стыке шагов: {full_stream!r}",
        )

        # 2. Проверяем наличие разделителя \n\n между шагами 1, 2 и 3
        self.assertIn("базы данных.\n\nПроверяю вывод", full_stream)
        self.assertIn("задачи 349.\n\nОстанавливаю фоновую", full_stream)

    def test_e2e_orchestration_gate_prefix_loop_prevention(self) -> None:
        """Сквозная проверка: повторение префиксов статусов оркестрации не приводит к лавине дублей."""
        arb = srv._ContentArbiter("turn-orch-1")

        # Агент меняет статусы оркестрации на протяжении 5 шагов
        statuses = [
            "[гейт оркестрации: активен | роль: lead-orchestrator] Инициализация контура",
            "[гейт оркестрации: активен | роль: explorer] Сбор контекста и чтение канона",
            "[гейт оркестрации: активен | роль: explorer] Поиск тестов в tests/",
            "[гейт оркестрации: активен | роль: worker] Запуск pytest",
            "[гейт оркестрации: активен | роль: reviewer] Анализ отчёта",
        ]

        emitted_deltas: list[str] = []
        for idx, status in enumerate(statuses, 1):
            # Эмулируем приход короткого префикса, затем полного текста
            short_prefix = status[:27]  # "[гейт оркестрации: активен"
            d1 = arb.offer("transcript", idx, short_prefix, "cid-orch")
            if d1:
                emitted_deltas.append(d1)
            d2 = arb.offer("transcript", idx, status, "cid-orch")
            if d2:
                emitted_deltas.append(d2)

        # Проверяем, что ни один шаг не был ошибочно заморожен из-за divergence
        self.assertEqual(arb.divergences, 0)

        # Полный текст не должен содержать патологического зацикливания "[гейт оркестрации: активен"
        full_text = "".join(emitted_deltas)
        count = full_text.count("[гейт оркестрации: активен")
        self.assertEqual(
            count,
            len(statuses),
            f"Префикс повторился {count} раз вместо {len(statuses)}: {full_text!r}",
        )

    def test_e2e_subagent_tool_preambles_isolated_to_reasoning(self) -> None:
        """Сквозная проверка: преамбулы запуска сабагентов изолируются в reasoning_content."""
        emitted_events: list[tuple[str, str]] = []

        def emit_reasoning(idx: int, delta: str, on_del: Any = None) -> bool:
            emitted_events.append(("reasoning", delta))
            if on_del is not None:
                on_del()
            return True

        def emit_content(idx: int | None, text: str) -> bool:
            emitted_events.append(("content", text))
            return True

        plan = srv._TurnPlan()
        plan.mode = "OFF"
        plan.base_idx = 0
        plan.offset = 0

        tail = srv._TranscriptTail(
            emit=emit_reasoning,
            stop_event=threading.Event(),
            done_event=threading.Event(),
            resumed=False,
            plan=plan,
            turn_id="turn-subagent-1",
            emit_content=emit_content,
            on_activity=None,
            usage_enabled=False,
            isolate_tool_preambles=True,
        )

        # Эмулируем транскрипт мультиагентного цикла:
        # Шаг 1: Оркестратор запускает сабагента Coder
        record_step1 = {
            "type": "PLANNER_RESPONSE",
            "step_index": 1,
            "content": "[гейт оркестрации: активен] Запускаю сабагента Coder для исправления тестов...",
            "thinking": "Анализ завершён. Необходимо делегировать кодогенерацию роли Coder.",
            "tool_calls": [
                {
                    "name": "invoke_subagent",
                    "args": {"Role": "Coder", "Prompt": "Fix test"},
                }
            ],
        }
        tail._emit_record(json.dumps(record_step1).encode("utf-8"))

        # Шаг 2: Финальный ответ после завершения сабагента
        record_step2 = {
            "type": "PLANNER_RESPONSE",
            "step_index": 2,
            "content": "Сабагент Coder завершил работу. Все тесты успешно пройдены.",
            "thinking": "Формирую итоговый статус для владельца.",
        }
        tail._emit_record(json.dumps(record_step2).encode("utf-8"))

        # Проверяем распределение:
        # 1. Преамбула шага 1 ушла в reasoning
        reasoning_pieces = [text for kind, text in emitted_events if kind == "reasoning"]
        self.assertTrue(any("Запускаю сабагента Coder" in r for r in reasoning_pieces))

        # 2. В content попал ТОЛЬКО финальный ответ шага 2 без сервисных преамбул вызова инструмента
        content_pieces = [text for kind, text in emitted_events if kind == "content"]
        self.assertEqual(len(content_pieces), 1)
        self.assertEqual(
            content_pieces[0],
            "Сабагент Coder завершил работу. Все тесты успешно пройдены.",
        )

    def test_e2e_reconcile_wire_sync_and_preamble_dedup(self) -> None:
        """Сквозная проверка: дедупликация преамбул в reasoning и синхронизация reconcile с wire."""
        # 1. Проверка дедупликации преамбулы при повторной записи шага
        emitted_events: list[tuple[str, str]] = []

        def emit_reasoning(idx: int, delta: str, on_del: Any = None) -> bool:
            emitted_events.append(("reasoning", delta))
            return True

        plan = srv._TurnPlan()
        plan.mode = "OFF"
        tail = srv._TranscriptTail(
            emit=emit_reasoning,
            stop_event=threading.Event(),
            done_event=threading.Event(),
            resumed=False,
            plan=plan,
            turn_id="turn-dedup-1",
            emit_content=lambda idx, t: True,
            isolate_tool_preambles=True,
        )

        rec = {
            "type": "PLANNER_RESPONSE",
            "step_index": 10,
            "content": "Запуск анализа...",
            "tool_calls": [{"name": "read_file", "args": {}}],
        }
        raw_bytes = json.dumps(rec).encode("utf-8")
        tail._emit_record(raw_bytes)
        # Повторная доставка того же шага (например при rewrite)
        tail._emit_record(raw_bytes)

        preambles = [t for k, t in emitted_events if "Запуск анализа..." in t]
        self.assertEqual(
            len(preambles),
            1,
            f"Преамбула эмитирована {len(preambles)} раз вместо 1: {preambles}",
        )

        # 2. Проверка отсутствия ложной дивергенции в Run.reconcile_result
        run = object.__new__(srv.Run)
        setattr(run, "_emit_lock", threading.Lock())
        setattr(run, "q", queue.Queue())
        setattr(run, "drain_closed", False)
        setattr(run, "_done_put", False)
        setattr(run, "_reasoning_bytes", 0)
        setattr(run, "_cap_logged", False)
        setattr(run, "_tail", SimpleNamespace(cid="cid-sync-1"))
        setattr(run, "_arbiter", srv._ContentArbiter("turn-sync-1"))
        setattr(run, "turn_id", "turn-sync-1")
        setattr(run, "run_cid", "cid-sync-1")
        setattr(run, "_last_step_index", None)
        setattr(run, "_content_emitted_wire", "")

        run.offer_content("transcript", 1, "Шаг 1 завершён.")
        run.offer_content("transcript", 2, "Шаг 2 завершён.")

        # Wire содержит разделитель \n\n
        wire_text = getattr(run, "_content_emitted_wire")
        self.assertEqual(wire_text, "Шаг 1 завершён.\n\nШаг 2 завершён.")

        # reconcile_result с тем же текстом не должен давать дивергенции
        delta = run.reconcile_result(wire_text)
        self.assertEqual(delta, "")
        self.assertFalse(
            getattr(run._arbiter, "last_result_diverged", False),
            "Ложное срабатывание дивергенции при точном совпадении wire_text",
        )

        # reconcile_result с дополнительным хвостом
        delta_extra = run.reconcile_result(wire_text + " Дополнительный итог.")
        self.assertEqual(delta_extra, " Дополнительный итог.")
        self.assertFalse(
            getattr(run._arbiter, "last_result_diverged", False),
            "Ложное срабатывание дивергенции при суффиксе wire_text",
        )
        # Повторный вызов reconcile_result идемпотентен и не дублирует хвост
        self.assertEqual(run.reconcile_result(wire_text + " Дополнительный итог."), "")

    def test_e2e_incremental_stdout_deltas_accumulate_without_freeze(self) -> None:
        """AD-001: инкрементальные text_delta из stdout накапливаются в _stdout_step_accum и не замораживают _ContentArbiter."""
        import io

        events = [
            {
                "event": "step_update",
                "step_update": {
                    "step_type": "agent_response",
                    "step_index": 1,
                    "text_delta": "Первый чанк. ",
                },
            },
            {
                "event": "step_update",
                "step_update": {
                    "step_type": "agent_response",
                    "step_index": 1,
                    "text_delta": "Второй чанк. ",
                },
            },
            {
                "event": "step_update",
                "step_update": {
                    "step_type": "agent_response",
                    "step_index": 1,
                    "text_delta": "Третий чанк.",
                },
            },
            {
                "event": "result",
                "result": {
                    "status": "success",
                    "response": "Первый чанк. Второй чанк. Третий чанк.",
                },
            },
        ]
        payload = b"".join(json.dumps(e).encode("utf-8") + b"\n" for e in events)
        run = object.__new__(srv.Run)
        setattr(
            run,
            "proc",
            SimpleNamespace(stdout=io.BytesIO(payload), wait=lambda timeout=None: 0),
        )
        setattr(run, "q", queue.Queue())
        setattr(run, "_text_seen", {})
        setattr(run, "_stdout_step_accum", {})
        setattr(
            run,
            "_tail",
            SimpleNamespace(
                cid="cid-inc-1",
                bind=lambda _c: None,
                drain_deadline=0.0,
                thread=SimpleNamespace(
                    join=lambda timeout=None: None, is_alive=lambda: False
                ),
            ),
        )
        setattr(run, "_proc_done", threading.Event())
        setattr(run, "_stop_watch", threading.Event())
        setattr(run, "_emit_lock", threading.Lock())
        setattr(run, "drain_closed", False)
        setattr(run, "_done_put", False)
        setattr(run, "_reasoning_bytes", 0)
        setattr(run, "_cap_logged", False)
        setattr(run, "got_event", False)
        setattr(run, "content_streaming", True)
        setattr(run, "isolate_tool_preambles", False)
        setattr(run, "mode", "ask")
        setattr(run, "_arbiter", srv._ContentArbiter("turn-inc-1"))
        setattr(run, "run_cid", "cid-inc-1")
        setattr(run, "turn_id", "turn-inc-1")
        setattr(run, "_last_step_index", None)
        setattr(run, "_content_emitted_wire", "")
        setattr(run, "_activity_lock", threading.Lock())
        setattr(run, "last_producer_activity_ts", 0.0)
        setattr(run, "transcript_activity_ts", None)
        setattr(run, "started", 0.0)
        setattr(run, "err_box", [])

        run._pump()

        q = cast("queue.Queue[tuple[str, object]]", getattr(run, "q"))
        text_chunks: list[str] = []
        while not q.empty():
            kind, item = q.get_nowait()
            if kind == "text":
                text_chunks.append(str(item))

        self.assertEqual(
            text_chunks,
            ["Первый чанк. ", "Второй чанк. ", "Третий чанк."],
        )
        self.assertEqual(run._arbiter.divergences, 0)
        self.assertEqual(
            run.reconcile_result("Первый чанк. Второй чанк. Третий чанк."),
            "",
        )

    def test_e2e_agent_mode_stdout_isolated_to_reasoning_and_final_reconciled(
        self,
    ) -> None:
        """AD-002 & AD-003: в режиме agent живые дельты stdout уходят в reasoning (не закрывая <Think>), а финал доставляется через reconcile_result."""
        import io

        events = [
            {
                "event": "step_update",
                "step_update": {
                    "step_type": "agent_response",
                    "step_index": 1,
                    "text_delta": "Проверяю файлы проекта...",
                },
            },
            {
                "event": "step_update",
                "step_update": {
                    "step_type": "tool",
                    "state": "DONE",
                    "tool_name": "read_file",
                    "step_index": 1,
                    "duration_seconds": 0.2,
                },
            },
            {
                "event": "step_update",
                "step_update": {
                    "step_type": "agent_response",
                    "step_index": 2,
                    "text_delta": "Итоговый ответ пользователю.",
                },
            },
            {
                "event": "result",
                "result": {
                    "status": "success",
                    "response": "Итоговый ответ пользователю.",
                },
            },
        ]
        payload = b"".join(json.dumps(e).encode("utf-8") + b"\n" for e in events)
        run = object.__new__(srv.Run)
        setattr(
            run,
            "proc",
            SimpleNamespace(stdout=io.BytesIO(payload), wait=lambda timeout=None: 0),
        )
        setattr(run, "q", queue.Queue())
        setattr(run, "_text_seen", {})
        setattr(run, "_stdout_step_accum", {})
        setattr(
            run,
            "_tail",
            SimpleNamespace(
                cid="cid-agent-1",
                bind=lambda _c: None,
                drain_deadline=0.0,
                thread=SimpleNamespace(
                    join=lambda timeout=None: None, is_alive=lambda: False
                ),
            ),
        )
        setattr(run, "_proc_done", threading.Event())
        setattr(run, "_stop_watch", threading.Event())
        setattr(run, "_emit_lock", threading.Lock())
        setattr(run, "drain_closed", False)
        setattr(run, "_done_put", False)
        setattr(run, "_reasoning_bytes", 0)
        setattr(run, "_cap_logged", False)
        setattr(run, "got_event", False)
        setattr(run, "content_streaming", True)
        setattr(run, "isolate_tool_preambles", True)
        setattr(run, "mode", "agent")
        setattr(run, "_arbiter", srv._ContentArbiter("turn-agent-1"))
        setattr(run, "run_cid", "cid-agent-1")
        setattr(run, "turn_id", "turn-agent-1")
        setattr(run, "_last_step_index", None)
        setattr(run, "_content_emitted_wire", "")
        setattr(run, "_activity_lock", threading.Lock())
        setattr(run, "last_producer_activity_ts", 0.0)
        setattr(run, "transcript_activity_ts", None)
        setattr(run, "started", 0.0)
        setattr(run, "err_box", [])

        run._pump()

        q = cast("queue.Queue[tuple[str, object]]", getattr(run, "q"))
        text_chunks: list[str] = []
        reasoning_chunks: list[str] = []
        done_payload: Any = None
        while not q.empty():
            kind, item = q.get_nowait()
            if kind == "text":
                text_chunks.append(str(item))
            elif kind == "reasoning":
                reasoning_chunks.append(str(item))
            elif kind == "done":
                done_payload = item

        # Во время работы инструментов ни один чанк не попал в content;
        # при смене step_index (1 -> 2) в _emit_reasoning добавлен разделитель \n\n
        self.assertEqual(text_chunks, [])
        self.assertEqual(
            reasoning_chunks,
            ["Проверяю файлы проекта...", "\n\nИтоговый ответ пользователю."],
        )
        self.assertIsNotNone(done_payload)
        _rc, final_text, _raw_res = done_payload
        # Финальный ответ надёжно доставляется через reconcile_result без дублей
        reconciled = run.reconcile_result(final_text)
        self.assertEqual(reconciled, "Итоговый ответ пользователю.")
        self.assertEqual(run.reconcile_result(final_text), "")

    def test_e2e_repeated_and_prefix_incremental_deltas_preserved_in_streaming_and_non_streaming(
        self,
    ) -> None:
        """F-001: повторяющиеся дельты ['ha', 'ha', '!'] и ['a', 'ab', '!'] сохраняют 100% токенов в streaming и non-streaming режимах."""
        import io

        cases: list[tuple[list[str], str]] = [
            (["ha", "ha", "!"], "haha!"),
            (["a", "ab", "!"], "aab!"),
        ]
        for deltas, expected in cases:
            for content_streaming in (True, False):
                with self.subTest(deltas=deltas, content_streaming=content_streaming):
                    events = [
                        {
                            "event": "step_update",
                            "step_update": {
                                "step_type": "agent_response",
                                "step_index": 1,
                                "text_delta": d,
                            },
                        }
                        for d in deltas
                    ] + [
                        {
                            "event": "result",
                            "result": {
                                "status": "success",
                                "response": expected,
                            },
                        }
                    ]
                    payload = b"".join(
                        json.dumps(e).encode("utf-8") + b"\n" for e in events
                    )
                    run = object.__new__(srv.Run)
                    setattr(
                        run,
                        "proc",
                        SimpleNamespace(
                            stdout=io.BytesIO(payload),
                            wait=lambda timeout=None: 0,
                        ),
                    )
                    setattr(run, "q", queue.Queue())
                    setattr(run, "_text_seen", {})
                    setattr(run, "_stdout_step_accum", {})
                    setattr(run, "_stdout_accum_bytes", 0)
                    setattr(run, "_preambles_emitted", set())
                    setattr(
                        run,
                        "_tail",
                        SimpleNamespace(
                            cid="cid-f001",
                            bind=lambda _c: None,
                            drain_deadline=0.0,
                            thread=SimpleNamespace(
                                join=lambda timeout=None: None,
                                is_alive=lambda: False,
                            ),
                        ),
                    )
                    setattr(run, "_proc_done", threading.Event())
                    setattr(run, "_stop_watch", threading.Event())
                    setattr(run, "_emit_lock", threading.Lock())
                    setattr(run, "drain_closed", False)
                    setattr(run, "_done_put", False)
                    setattr(run, "_reasoning_bytes", 0)
                    setattr(run, "_cap_logged", False)
                    setattr(run, "got_event", False)
                    setattr(run, "content_streaming", content_streaming)
                    setattr(run, "isolate_tool_preambles", False)
                    setattr(run, "mode", "ask")
                    setattr(run, "_arbiter", srv._ContentArbiter("turn-f001"))
                    setattr(run, "run_cid", "cid-f001")
                    setattr(run, "turn_id", "turn-f001")
                    setattr(run, "_last_step_index", None)
                    setattr(run, "_content_emitted_wire", "")
                    setattr(run, "_activity_lock", threading.Lock())
                    setattr(run, "last_producer_activity_ts", 0.0)
                    setattr(run, "transcript_activity_ts", None)
                    setattr(run, "started", 0.0)
                    setattr(run, "err_box", [])

                    run._pump()

                    q = cast("queue.Queue[tuple[str, object]]", getattr(run, "q"))
                    text_chunks: list[str] = []
                    done_payload: Any = None
                    while not q.empty():
                        kind, item = q.get_nowait()
                        if kind == "text":
                            text_chunks.append(str(item))
                        elif kind == "done":
                            done_payload = item

                    self.assertEqual(text_chunks, deltas)
                    self.assertEqual("".join(text_chunks), expected)
                    self.assertIsNotNone(done_payload)
                    _rc, final_text, _raw_res = done_payload
                    self.assertEqual(final_text, expected)
                    if content_streaming:
                        self.assertEqual(run._arbiter.divergences, 0)
                        self.assertEqual(run.reconcile_result(expected), "")

    def test_e2e_stdout_step_accum_respects_step_and_utf8_byte_caps_and_dedups_preambles(
        self,
    ) -> None:
        """F-002 & F-003: _stdout_step_accum соблюдает MAX_CONTENT_STEPS и MAX_CONTENT_BYTES_PER_TURN (UTF-8), а преамбулы не дублируются между stdout и _TranscriptTail."""
        import io
        from unittest import mock

        events = [
            {
                "event": "step_update",
                "step_update": {
                    "step_type": "agent_response",
                    "step_index": i,
                    "text_delta": "пр",  # 4 байта UTF-8
                },
            }
            for i in range(1, 6)
        ]
        payload = b"".join(json.dumps(e).encode("utf-8") + b"\n" for e in events)
        emitted_reasoning: list[str] = []

        plan = srv._TurnPlan()
        plan.mode = "OFF"
        preambles_shared: set[int] = set()
        tail = srv._TranscriptTail(
            emit=lambda _idx, delta, _cb=None: emitted_reasoning.append(delta) or True,
            stop_event=threading.Event(),
            done_event=threading.Event(),
            resumed=False,
            plan=plan,
            turn_id="turn-f002-f003",
            emit_content=lambda _idx, _t: True,
            isolate_tool_preambles=True,
            preambles_emitted=preambles_shared,
        )

        run = object.__new__(srv.Run)
        setattr(
            run,
            "proc",
            SimpleNamespace(stdout=io.BytesIO(payload), wait=lambda timeout=None: 0),
        )
        setattr(run, "q", queue.Queue())
        setattr(run, "_text_seen", {})
        setattr(run, "_stdout_step_accum", {})
        setattr(run, "_stdout_accum_bytes", 0)
        setattr(run, "_preambles_emitted", preambles_shared)
        setattr(run, "_tail", tail)
        setattr(run, "_proc_done", threading.Event())
        setattr(run, "_stop_watch", threading.Event())
        setattr(run, "_emit_lock", threading.Lock())
        setattr(run, "drain_closed", False)
        setattr(run, "_done_put", False)
        setattr(run, "_reasoning_bytes", 0)
        setattr(run, "_cap_logged", False)
        setattr(run, "got_event", False)
        setattr(run, "content_streaming", True)
        setattr(run, "isolate_tool_preambles", True)
        setattr(run, "mode", "agent")
        setattr(run, "_arbiter", srv._ContentArbiter("turn-f002-f003"))
        setattr(run, "run_cid", "cid-f002")
        setattr(run, "turn_id", "turn-f002-f003")
        setattr(run, "_last_step_index", None)
        setattr(run, "_content_emitted_wire", "")
        setattr(run, "_activity_lock", threading.Lock())
        setattr(run, "last_producer_activity_ts", 0.0)
        setattr(run, "transcript_activity_ts", None)
        setattr(run, "started", 0.0)
        setattr(run, "err_box", [])

        with (
            mock.patch.object(srv, "MAX_CONTENT_STEPS", 2),
            mock.patch.object(srv, "MAX_CONTENT_BYTES_PER_TURN", 8),
        ):
            run._pump()

        self.assertLessEqual(len(run._stdout_step_accum), 2)
        self.assertLessEqual(run._stdout_accum_bytes, 8)
        total_utf8 = sum(
            len(v.encode("utf-8")) for v in run._stdout_step_accum.values()
        )
        self.assertEqual(run._stdout_accum_bytes, total_utf8)
        self.assertLessEqual(total_utf8, 8)
        # Размер _preambles_emitted ограничен MAX_CONTENT_STEPS * 2 == 4 (шаги 2, 3, 4, 5)
        self.assertLessEqual(len(run._preambles_emitted), 4)
        self.assertEqual(set(run._preambles_emitted), {2, 3, 4, 5})

        # Порядок 1 (stdout -> transcript): шаг 4 уже был эмитирован из stdout -> _TranscriptTail не должен эмитить его повторно
        rec_step4 = {
            "type": "PLANNER_RESPONSE",
            "step_index": 4,
            "content": "пр",
            "tool_calls": [{"name": "read_file", "args": {}}],
        }
        tail._emit_record(json.dumps(rec_step4).encode("utf-8"))
        self.assertEqual(emitted_reasoning, [])

    def test_e2e_transcript_then_stdout_preamble_dedup_and_empty_delta_guard(
        self,
    ) -> None:
        """Блокер 2 (F-001) & Блокер 3: порядок transcript -> stdout не дублирует преамбулу в reasoning, а пустая/обрезанная дельта не попадает в _preambles_emitted."""
        import io
        from unittest import mock

        emitted_tail_reasoning: list[str] = []
        plan = srv._TurnPlan()
        plan.mode = "OFF"
        preambles_shared: set[int] = set()
        tail = srv._TranscriptTail(
            emit=lambda _idx, delta, _cb=None: emitted_tail_reasoning.append(delta)
            or True,
            stop_event=threading.Event(),
            done_event=threading.Event(),
            resumed=False,
            plan=plan,
            turn_id="turn-tr-first",
            emit_content=lambda _idx, _t: True,
            isolate_tool_preambles=True,
            preambles_emitted=preambles_shared,
        )

        # 1. Сначала приходит запись в transcript для шага 10
        rec_step10 = {
            "type": "PLANNER_RESPONSE",
            "step_index": 10,
            "content": "Преамбула из транскрипта.",
            "tool_calls": [{"name": "read_file", "args": {}}],
        }
        tail._emit_record(json.dumps(rec_step10).encode("utf-8"))
        self.assertEqual(emitted_tail_reasoning, ["Преамбула из транскрипта.\n\n"])
        self.assertIn(10, preambles_shared)

        # 2. Затем приходят чанки stdout для того же шага 10 + шаг 11 (который будет отсечён лимитом байт)
        events = [
            {
                "event": "step_update",
                "step_update": {
                    "step_type": "agent_response",
                    "step_index": 10,
                    "text_delta": "Преамбула ",
                },
            },
            {
                "event": "step_update",
                "step_update": {
                    "step_type": "agent_response",
                    "step_index": 10,
                    "text_delta": "из транскрипта.",
                },
            },
            {
                "event": "step_update",
                "step_update": {
                    "step_type": "agent_response",
                    "step_index": 11,
                    "text_delta": "Слишком длинный шаг сверх лимита",
                },
            },
        ]
        payload = b"".join(json.dumps(e).encode("utf-8") + b"\n" for e in events)
        run = object.__new__(srv.Run)
        setattr(
            run,
            "proc",
            SimpleNamespace(stdout=io.BytesIO(payload), wait=lambda timeout=None: 0),
        )
        setattr(run, "q", queue.Queue())
        setattr(run, "_text_seen", {})
        setattr(run, "_stdout_step_accum", {})
        setattr(run, "_stdout_accum_bytes", 0)
        setattr(run, "_preambles_emitted", preambles_shared)
        setattr(run, "_tail", tail)
        setattr(run, "_proc_done", threading.Event())
        setattr(run, "_stop_watch", threading.Event())
        setattr(run, "_emit_lock", threading.Lock())
        setattr(run, "drain_closed", False)
        setattr(run, "_done_put", False)
        setattr(run, "_reasoning_bytes", 0)
        setattr(run, "_cap_logged", False)
        setattr(run, "got_event", False)
        setattr(run, "content_streaming", True)
        setattr(run, "isolate_tool_preambles", True)
        setattr(run, "mode", "agent")
        setattr(run, "_arbiter", srv._ContentArbiter("turn-tr-first"))
        setattr(run, "run_cid", "cid-tr-first")
        setattr(run, "turn_id", "turn-tr-first")
        setattr(run, "_last_step_index", None)
        setattr(run, "_content_emitted_wire", "")
        setattr(run, "_activity_lock", threading.Lock())
        setattr(run, "last_producer_activity_ts", 0.0)
        setattr(run, "transcript_activity_ts", None)
        setattr(run, "started", 0.0)
        setattr(run, "err_box", [])

        # Лимит байт ровно под текст шага 10, чтобы дельта шага 11 обрезалась в ""
        step10_bytes = len("Преамбула из транскрипта.".encode("utf-8"))
        with mock.patch.object(srv, "MAX_CONTENT_BYTES_PER_TURN", step10_bytes):
            run._pump()

        q = cast("queue.Queue[tuple[str, object]]", getattr(run, "q"))
        stdout_reasoning: list[str] = []
        while not q.empty():
            kind, item = q.get_nowait()
            if kind == "reasoning":
                stdout_reasoning.append(str(item))

        # Шаг 10 уже был эмитирован транскриптом -> из stdout дублей в reasoning нет
        self.assertEqual(stdout_reasoning, [])
        # Шаг 11 был полностью отброшен лимитом байт -> не должен попасть в _preambles_emitted
        self.assertNotIn(11, preambles_shared)

    def test_e2e_fifo_eviction_decrements_accum_bytes_and_fallback_without_result(
        self,
    ) -> None:
        """Блокер 3 & Блокер 4: FIFO-вытеснение уменьшает _stdout_accum_bytes, а при отсутствии result финальный ответ (не-tool шаг) доставляется в content."""
        import io
        from unittest import mock

        # Сценарий 1: шаг 1 (инструмент) + шаг 2 (финальный ответ без result)
        events_no_result = [
            {
                "event": "step_update",
                "step_update": {
                    "step_type": "agent_response",
                    "step_index": 1,
                    "text_delta": "Читаю конфиг...",
                },
            },
            {
                "event": "step_update",
                "step_update": {
                    "step_type": "tool",
                    "state": "DONE",
                    "tool_name": "read_file",
                    "step_index": 1,
                    "duration_seconds": 0.1,
                },
            },
            {
                "event": "step_update",
                "step_update": {
                    "step_type": "agent_response",
                    "step_index": 2,
                    "text_delta": "Финальный ответ без события result.",
                },
            },
        ]
        payload = b"".join(
            json.dumps(e).encode("utf-8") + b"\n" for e in events_no_result
        )
        run = object.__new__(srv.Run)
        setattr(
            run,
            "proc",
            SimpleNamespace(stdout=io.BytesIO(payload), wait=lambda timeout=None: 0),
        )
        setattr(run, "q", queue.Queue())
        setattr(run, "_text_seen", {})
        setattr(run, "_stdout_step_accum", {})
        setattr(run, "_stdout_accum_bytes", 0)
        setattr(run, "_preambles_emitted", set())
        setattr(
            run,
            "_tail",
            SimpleNamespace(
                cid="cid-fb-1",
                bind=lambda _c: None,
                drain_deadline=0.0,
                thread=SimpleNamespace(
                    join=lambda timeout=None: None, is_alive=lambda: False
                ),
            ),
        )
        setattr(run, "_proc_done", threading.Event())
        setattr(run, "_stop_watch", threading.Event())
        setattr(run, "_emit_lock", threading.Lock())
        setattr(run, "drain_closed", False)
        setattr(run, "_done_put", False)
        setattr(run, "_reasoning_bytes", 0)
        setattr(run, "_cap_logged", False)
        setattr(run, "got_event", False)
        setattr(run, "content_streaming", True)
        setattr(run, "isolate_tool_preambles", True)
        setattr(run, "mode", "agent")
        setattr(run, "_arbiter", srv._ContentArbiter("turn-fb-1"))
        setattr(run, "run_cid", "cid-fb-1")
        setattr(run, "turn_id", "turn-fb-1")
        setattr(run, "_last_step_index", None)
        setattr(run, "_content_emitted_wire", "")
        setattr(run, "_activity_lock", threading.Lock())
        setattr(run, "last_producer_activity_ts", 0.0)
        setattr(run, "transcript_activity_ts", None)
        setattr(run, "started", 0.0)
        setattr(run, "err_box", [])

        step1_len = len("Читаю конфиг...".encode("utf-8"))
        step2_len = len("Финальный ответ без события result.".encode("utf-8"))
        # MAX_CONTENT_STEPS=1 гарантирует FIFO-вытеснение шага 1 при приходе шага 2;
        # если бы _stdout_accum_bytes не уменьшался при вытеснении, шаг 2 не поместился бы в budget = step2_len.
        with (
            mock.patch.object(srv, "MAX_CONTENT_STEPS", 1),
            mock.patch.object(
                srv, "MAX_CONTENT_BYTES_PER_TURN", max(step1_len, step2_len)
            ),
        ):
            run._pump()

        self.assertEqual(len(run._stdout_step_accum), 1)
        self.assertEqual(run._stdout_accum_bytes, step2_len)

        q = cast("queue.Queue[tuple[str, object]]", getattr(run, "q"))
        done_payload: Any = None
        while not q.empty():
            kind, item = q.get_nowait()
            if kind == "done":
                done_payload = item

        self.assertIsNotNone(done_payload)
        rc, final_text, _raw_res = done_payload
        self.assertEqual(rc, 0)
        self.assertEqual(final_text, "Финальный ответ без события result.")
        # Проверяем, что и прямой вызов reconcile_result("") (когда result.response пустой) отдаёт накопленный финал
        self.assertEqual(
            run.reconcile_result(""),
            "Финальный ответ без события result.",
        )
        self.assertEqual(
            run._content_emitted_wire,
            "Финальный ответ без события result.",
        )
        # Повторный вызов идемпотентен
        self.assertEqual(run.reconcile_result(""), "")

        # Сценарий 2: если последний шаг был вызовом инструмента, он НЕ должен утекать в content как fallback
        events_only_tool = events_no_result[:2]
        payload_tool = b"".join(
            json.dumps(e).encode("utf-8") + b"\n" for e in events_only_tool
        )
        run_tool = object.__new__(srv.Run)
        for k, v in run.__dict__.items():
            setattr(run_tool, k, v)
        setattr(
            run_tool,
            "proc",
            SimpleNamespace(
                stdout=io.BytesIO(payload_tool), wait=lambda timeout=None: 0
            ),
        )
        setattr(run_tool, "q", queue.Queue())
        setattr(run_tool, "_stdout_step_accum", {})
        setattr(run_tool, "_stdout_accum_bytes", 0)
        setattr(run_tool, "_preambles_emitted", set())
        setattr(run_tool, "_stdout_preamble_steps", set())
        setattr(run_tool, "_tool_step_indices", set())
        setattr(run_tool, "_arbiter", srv._ContentArbiter("turn-fb-tool"))
        setattr(run_tool, "_content_emitted_wire", "")
        setattr(run_tool, "drain_closed", False)
        setattr(run_tool, "_done_put", False)

        run_tool._pump()
        self.assertEqual(run_tool.reconcile_result(""), "")

    def test_e2e_concurrent_claim_preamble_atomicity(self) -> None:
        """RW-009: параллельные вызовы claim_preamble и _TranscriptTail._emit_record из нескольких потоков атомарны под _emit_lock (ровно один поток получает True)."""
        run = object.__new__(srv.Run)
        setattr(run, "_emit_lock", threading.Lock())
        setattr(run, "_preambles_emitted", set())

        num_threads = 16
        for target_step in (1, 42, None):
            barrier = threading.Barrier(num_threads)
            outcomes: list[bool] = []
            outcomes_lock = threading.Lock()

            def worker(step_val: int | None = target_step) -> None:
                barrier.wait()
                claimed = run.claim_preamble(step_val)
                with outcomes_lock:
                    outcomes.append(claimed)

            threads = [threading.Thread(target=worker) for _ in range(num_threads)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            self.assertEqual(len(outcomes), num_threads)
            self.assertEqual(
                outcomes.count(True),
                1,
                f"Ожидался ровно 1 True для step={target_step}, получено: {outcomes}",
            )
            self.assertEqual(outcomes.count(False), num_threads - 1)

        # Проверка гонки между _TranscriptTail._emit_record (через run_ref) и прямыми вызовами run.claim_preamble
        emitted_count = 0
        emitted_lock = threading.Lock()

        def count_emit(_idx: int, _delta: str, _cb: Any = None) -> bool:
            nonlocal emitted_count
            with emitted_lock:
                emitted_count += 1
            return True

        plan = srv._TurnPlan()
        plan.mode = "OFF"
        tail = srv._TranscriptTail(
            emit=count_emit,
            stop_event=threading.Event(),
            done_event=threading.Event(),
            resumed=False,
            plan=plan,
            turn_id="turn-rw009",
            emit_content=lambda _idx, _t: True,
            isolate_tool_preambles=True,
            preambles_emitted=run._preambles_emitted,
            run_ref=run,
        )

        race_step = 99
        race_barrier = threading.Barrier(num_threads)
        raw_rec = json.dumps(
            {
                "type": "PLANNER_RESPONSE",
                "step_index": race_step,
                "content": "Конкурентная преамбула",
                "tool_calls": [{"name": "read_file", "args": {}}],
            }
        ).encode("utf-8")

        def race_worker(tid: int) -> None:
            race_barrier.wait()
            if tid % 2 == 0:
                tail._emit_record(raw_rec)
            else:
                if run.claim_preamble(race_step):
                    count_emit(race_step, "Конкурентная преамбула\n\n")

        race_threads = [
            threading.Thread(target=race_worker, args=(i,))
            for i in range(num_threads)
        ]
        for t in race_threads:
            t.start()
        for t in race_threads:
            t.join()

        self.assertEqual(
            emitted_count,
            1,
            f"Преамбула шага {race_step} должна быть эмитирована ровно 1 раз, получено: {emitted_count}",
        )

    def test_e2e_multi_chunk_stdout_preamble_preserved_and_transcript_deduped(
        self,
    ) -> None:
        """Cycle 5 (F-001/F-007/F-009): многочанковый stdout (['Часть 1 ', 'Часть 2.']) в режиме agent (isolate_tool_preambles=True) доставляет все дельты шага в reasoning, а последующий _TranscriptTail не дублирует шаг."""
        import io

        for content_streaming in (True, False):
            with self.subTest(content_streaming=content_streaming):
                events = [
                    {
                        "event": "step_update",
                        "step_update": {
                            "step_type": "agent_response",
                            "step_index": 5,
                            "text_delta": "Часть 1 ",
                        },
                    },
                    {
                        "event": "step_update",
                        "step_update": {
                            "step_type": "agent_response",
                            "step_index": 5,
                            "text_delta": "Часть 2.",
                        },
                    },
                    {
                        "event": "step_update",
                        "step_update": {
                            "step_type": "tool",
                            "state": "DONE",
                            "tool_name": "read_file",
                            "step_index": 5,
                            "duration_seconds": 0.1,
                        },
                    },
                ]
                payload = b"".join(
                    json.dumps(e).encode("utf-8") + b"\n" for e in events
                )
                run = object.__new__(srv.Run)
                setattr(
                    run,
                    "proc",
                    SimpleNamespace(
                        stdout=io.BytesIO(payload), wait=lambda timeout=None: 0
                    ),
                )
                setattr(run, "q", queue.Queue())
                setattr(run, "_text_seen", {})
                setattr(run, "_stdout_step_accum", {})
                setattr(run, "_stdout_accum_bytes", 0)
                setattr(run, "_preambles_emitted", set())
                setattr(run, "_stdout_preamble_steps", set())
                setattr(run, "_tool_step_indices", set())
                setattr(run, "_proc_done", threading.Event())
                setattr(run, "_stop_watch", threading.Event())
                setattr(run, "_emit_lock", threading.Lock())
                setattr(run, "drain_closed", False)
                setattr(run, "_done_put", False)
                setattr(run, "_reasoning_bytes", 0)
                setattr(run, "_cap_logged", False)
                setattr(run, "got_event", False)
                setattr(run, "content_streaming", content_streaming)
                setattr(run, "isolate_tool_preambles", True)
                setattr(run, "mode", "agent")
                setattr(run, "_arbiter", srv._ContentArbiter("turn-mc-5"))
                setattr(run, "run_cid", "cid-mc-5")
                setattr(run, "turn_id", "turn-mc-5")
                setattr(run, "_last_step_index", None)
                setattr(run, "_content_emitted_wire", "")
                setattr(run, "_activity_lock", threading.Lock())
                setattr(run, "last_producer_activity_ts", 0.0)
                setattr(run, "transcript_activity_ts", None)
                setattr(run, "started", 0.0)
                setattr(run, "err_box", [])

                tail_emitted: list[str] = []
                plan = srv._TurnPlan()
                plan.mode = "OFF"
                tail = srv._TranscriptTail(
                    emit=lambda _idx, delta, _cb=None: tail_emitted.append(delta)
                    or True,
                    stop_event=run._stop_watch,
                    done_event=run._proc_done,
                    resumed=False,
                    plan=plan,
                    turn_id="turn-mc-5",
                    emit_content=lambda _idx, _t: True,
                    isolate_tool_preambles=True,
                    preambles_emitted=run._preambles_emitted,
                    run_ref=run,
                )
                setattr(run, "_tail", tail)

                run._pump()

                q = cast("queue.Queue[tuple[str, object]]", getattr(run, "q"))
                reasoning_chunks: list[str] = []
                text_chunks: list[str] = []
                while not q.empty():
                    kind, item = q.get_nowait()
                    if kind == "reasoning":
                        reasoning_chunks.append(str(item))
                    elif kind == "text":
                        text_chunks.append(str(item))

                # 1. Все дельты шага из stdout поступили в reasoning без обрезки после 1-го чанка
                self.assertEqual(reasoning_chunks, ["Часть 1 ", "Часть 2."])
                self.assertEqual("".join(reasoning_chunks), "Часть 1 Часть 2.")
                self.assertEqual(text_chunks, [])

                # 2. Последующая запись того же шага в _TranscriptTail не дублирует преамбулу
                rec_step5 = {
                    "type": "PLANNER_RESPONSE",
                    "step_index": 5,
                    "content": "Часть 1 Часть 2.",
                    "tool_calls": [{"name": "read_file", "args": {}}],
                }
                tail._emit_record(json.dumps(rec_step5).encode("utf-8"))
                self.assertEqual(tail_emitted, [])


if __name__ == "__main__":
    unittest.main()
