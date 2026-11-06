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


# ---------------------------------------------------------------------------------------
# ADR-0015 (VER-004, L2): non-stream через внутренний SSE, живость, совместимость контрактов.
# Только loopback; флаги и числа — через env/limits, секретов нет.
# ---------------------------------------------------------------------------------------
import http.client  # noqa: E402
import time  # noqa: E402
from unittest import mock  # noqa: E402

_TESTS_DIR = Path(__file__).resolve().parent
# agy-bridge добавляет в sys.path свой каталог с собственным server.py: хабовый `server` из корня
# репозитория должен находиться первым (иначе `import server` вернёт мост agy).
for _path in (str(_REPO_ROOT), str(_TESTS_DIR)):
    while _path in sys.path:
        sys.path.remove(_path)
    sys.path.insert(0, _path)

import server as hub_server  # noqa: E402
from adapters import ADAPTER_KINDS  # noqa: E402
from adapters.passthrough_adapter import PassthroughLimits  # noqa: E402
from bridge_testlib import BridgeCase, install_droid_stand, load_raw_fleet  # noqa: E402
from core.backend_adapter import AdapterRegistry  # noqa: E402
from core.model_penalty import ModelPenaltyTracker  # noqa: E402
from core.liveness_registry import get_registry  # noqa: E402
from core.cli_runtime_config import NonstreamConfig  # noqa: E402
from core.liveness_signals import (  # noqa: E402
    FLAG_SOFT_LIVENESS,
    FLAG_TELEMETRY,
    FLAG_VIA_STREAM,
)

_FLAG_NEUTRAL = "BRIDGE_CLI_NEUTRAL_NAMES_ENABLED"
_ALL_FLAGS = (FLAG_VIA_STREAM, FLAG_SOFT_LIVENESS, FLAG_TELEMETRY, _FLAG_NEUTRAL)
_HEALTH_KEYS = frozenset(
    {"ok", "transport", "model", "active", "max_concurrent", "tool_emulation", "uptime_s"}
)
_GLUED = re.compile(r"[а-яёa-z]\.[А-ЯЁA-Z]")
_DONE_FRAME = b"data: [DONE]\n\n"
_HUB_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "invoke_subagent",
            "parameters": {
                "type": "object",
                "properties": {"Role": {"type": "string"}, "Prompt": {"type": "string"}},
                "required": ["Role", "Prompt"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
            },
        },
    },
]


def _frame(payload: dict[str, Any]) -> bytes:
    return b"data: " + json.dumps(payload, ensure_ascii=False).encode("utf-8") + b"\n\n"


def _delta_frame(delta: dict[str, Any], finish: str | None = None, **extra: Any) -> bytes:
    chunk: dict[str, Any] = {
        "id": "chatcmpl-ns-1",
        "object": "chat.completion.chunk",
        "created": 1700000000,
        "model": "gpt-6.1-terra",
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
    }
    chunk.update(extra)
    return _frame(chunk)


def _text_frame(text: str, key: str = "content") -> bytes:
    return _delta_frame({key: text})


def _send_sse(handler: Any, steps: list[Any]) -> None:
    """Сценарий upstream: bytes — запись, float — пауза, callable — хук (gate/event)."""
    handler.send_response(200)
    handler.send_header("Content-Type", "text/event-stream")
    handler.end_headers()
    try:
        for step in steps:
            if isinstance(step, (bytes, bytearray)):
                handler.wfile.write(bytes(step))
                handler.wfile.flush()
            elif isinstance(step, float):
                time.sleep(step)
            else:
                step()
    except OSError:  # клиент (мост) оборвал соединение: сценарий завершён
        return


class _ScriptedUpstream:
    """Локальный OpenAI-совместимый upstream (HTTP/1.0, SSE без Content-Length)."""

    def __init__(self) -> None:
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

        self.requests: list[dict[str, Any]] = []
        self.respond: Any = lambda handler, body: None
        outer = self

        class _Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.0"

            def log_message(self, *args: Any) -> None:
                return

            def do_POST(self) -> None:  # noqa: N802
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length)
                outer.requests.append(
                    {"path": self.path, "headers": dict(self.headers), "body": body}
                )
                outer.respond(self, body)

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


class NonstreamViaStreamHubE2ETests(BridgeCase):
    """Хаб + passthrough-бэкенд: внешний `stream=false` через внутренний SSE (AD-001..AD-004)."""

    def setUp(self) -> None:
        super().setUp()
        patcher = mock.patch.dict(os.environ, {}, clear=False)
        patcher.start()
        self.addCleanup(patcher.stop)
        # Штрафы моделей персистентны (~/.config/...): изолируем их во временный файл теста.
        tracker = ModelPenaltyTracker(storage_path=Path(self._tmp.name) / "penalties.json")
        penalty = mock.patch.object(hub_server, "_PENALTY_TRACKER", tracker)
        penalty.start()
        self.addCleanup(penalty.stop)
        self._tmp_cfg = Path(self._tmp.name) / "no-dynamic-config.json"  # не существует
        os.environ["BRIDGE_DYNAMIC_CONFIG_PATH"] = str(self._tmp_cfg)
        for name in _ALL_FLAGS:
            os.environ[name] = "false"
        self.upstream = _ScriptedUpstream()
        self.addCleanup(self.upstream.close)
        data = load_raw_fleet()
        data["backends"]["codex"]["enabled"] = True
        data["backends"]["codex"]["base_url"] = f"http://127.0.0.1:{self.upstream.port}/v1"
        data["backends"]["codex"].pop("api_key_env", None)
        hub_server.FLEET = hub_server._build_catalog(data)
        hub_server.BACKENDS = AdapterRegistry.from_fleet(
            hub_server.FLEET, ADAPTER_KINDS, lambda: hub_server.FLEET, hub_server
        )
        self.addCleanup(self._drain_registry)

    # -- helpers ----------------------------------------------------------------------
    def _drain_registry(self) -> None:
        registry = get_registry()
        for turn_id in list(registry._entries):  # noqa: SLF001 - страховка изоляции тестов
            registry.finish(turn_id)

    def wait_registry_empty(self, timeout: float = 5.0) -> None:
        """Ответ уходит клиенту до `finally` обработчика: запись реестра исчезает почти сразу."""
        registry = get_registry()
        deadline = time.monotonic() + timeout
        while registry.active_count() and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertEqual(registry.active_count(), 0, "утечка записи passthrough-реестра")

    def flags(self, **values: bool) -> None:
        """Динамические флаги читаются на каждом решении: меняем env без рестарта."""
        names = {
            "via_stream": FLAG_VIA_STREAM,
            "soft": FLAG_SOFT_LIVENESS,
            "telemetry": FLAG_TELEMETRY,
            "neutral": _FLAG_NEUTRAL,
        }
        for key, value in values.items():
            os.environ[names[key]] = "true" if value else "false"

    def codex(self) -> Any:
        return next(a for a in hub_server.BACKENDS.adapters() if a.id == "codex")

    def small_windows(
        self, first: float = 0.5, idle: float = 0.6, cap: float = 30.0
    ) -> None:
        ns = NonstreamConfig(
            first_progress_timeout_s=first,
            idle_timeout_s=idle,
            safety_cap_s=cap,
            poll_interval_s=0.01,
        )
        self.codex().limits = PassthroughLimits(poll_interval_s=0.01, nonstream=ns)

    def body(self, **extra: Any) -> dict[str, Any]:
        base = {
            "model": "gpt-6.1-terra",
            "reasoning_effort": "xhigh",
            "tools": _HUB_TOOLS,
            "messages": [{"role": "user", "content": "hi"}],
            "stream": False,
        }
        base.update(extra)
        return base

    def post(
        self,
        body: dict[str, Any],
        extra_headers: dict[str, str] | None = None,
        timeout: float = 30.0,
    ) -> tuple[int, dict[str, str], bytes]:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=timeout)
        try:
            headers = {"Content-Type": "application/json", "Authorization": "Bearer test-key"}
            headers.update(extra_headers or {})
            conn.request("POST", "/v1/chat/completions", body=json.dumps(body), headers=headers)
            resp = conn.getresponse()
            data = resp.read()
            return resp.status, {k.lower(): v for k, v in resp.getheaders()}, data
        finally:
            conn.close()

    def get(
        self, path: str, extra_headers: dict[str, str] | None = None
    ) -> tuple[int, dict[str, str], Any]:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        try:
            headers = {"Authorization": "Bearer test-key"}
            headers.update(extra_headers or {})
            conn.request("GET", path, headers=headers)
            resp = conn.getresponse()
            raw = resp.read()
            parsed = json.loads(raw) if raw else None
            return resp.status, {k.lower(): v for k, v in resp.getheaders()}, parsed
        finally:
            conn.close()

    def serve(self, steps: list[Any]) -> None:
        self.upstream.respond = lambda handler, body: _send_sse(handler, steps)

    # -- 1. шаги с разделителями \n\n, reasoning отделён, usage/finish на месте -----------
    def test_multistep_markdown_boundaries_reasoning_split_usage_finish(self) -> None:
        self.flags(via_stream=True)
        steps_text = ["Шаг 1: данные собраны.", "\n\n", "Шаг 2: результат проверен.", "\n\n", "Итог: всё готово."]
        reasoning = ["Анализирую данные.", "\n\n", "Проверяю результаты."]
        usage = {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18}
        self.serve(
            [_delta_frame({"role": "assistant"})]
            + [_text_frame(r, "reasoning_content") for r in reasoning]
            + [_text_frame(t) for t in steps_text]
            + [_delta_frame({}, "stop"), _frame(
                {"id": "chatcmpl-ns-1", "object": "chat.completion.chunk", "created": 1700000000,
                 "model": "gpt-6.1-terra", "choices": [], "usage": usage}), _DONE_FRAME]
        )
        status, headers, raw = self.post(self.body())
        self.assertEqual(status, 200, raw)
        self.assertIn("application/json", headers["content-type"])
        data = json.loads(raw)
        self.assertEqual(data["object"], "chat.completion")
        self.assertEqual(data["id"], "chatcmpl-ns-1")
        self.assertEqual(data["usage"], usage)
        choice = data["choices"][0]
        message = choice["message"]
        self.assertEqual(message["role"], "assistant")
        self.assertEqual(choice["finish_reason"], "stop")
        self.assertEqual(message["content"], "".join(steps_text))
        self.assertIn("данные собраны.\n\nШаг 2", message["content"])
        self.assertIn("проверен.\n\nИтог", message["content"])
        self.assertEqual(message["reasoning_content"], "".join(reasoning))
        # reasoning не просачивается в content и наоборот
        self.assertNotIn("Анализирую", message["content"])
        self.assertNotIn("Шаг 1", message["reasoning_content"])
        for text in (message["content"], message["reasoning_content"]):
            self.assertIsNone(_GLUED.search(text), text)
        # внутренний stream=true ушёл upstream, клиент получил один JSON
        sent = json.loads(self.upstream.requests[0]["body"])
        self.assertIs(sent["stream"], True)
        self.assertEqual(sent["messages"], [{"role": "user", "content": "hi"}])

    def test_aggregation_is_verbatim_and_never_inserts_or_strips_separators(self) -> None:
        """Контракт ADR: разделители принадлежат upstream; агрегатор их не чинит и не режет."""
        self.flags(via_stream=True)
        pieces = ["abc.", "Def", "\n\n\n", "тест.", "Ещё"]
        self.serve([_text_frame(p) for p in pieces] + [_delta_frame({}, "stop"), _DONE_FRAME])
        status, _, raw = self.post(self.body())
        self.assertEqual(status, 200)
        content = json.loads(raw)["choices"][0]["message"]["content"]
        self.assertEqual(content, "".join(pieces))
        self.assertIsNotNone(_GLUED.search(content))  # склейка на входе остаётся склейкой

    def test_flag_off_keeps_non_stream_body_and_json_response_unchanged(self) -> None:
        self.flags(via_stream=False)
        payload = {
            "id": "x", "object": "chat.completion", "created": 1, "model": "gpt-6.1-terra",
            "choices": [{"index": 0, "finish_reason": "stop",
                         "message": {"role": "assistant", "content": "A.\n\nB."}}],
        }

        def respond(handler: Any, body: bytes) -> None:
            data = json.dumps(payload).encode("utf-8")
            handler.send_response(200)
            handler.send_header("Content-Type", "application/json")
            handler.send_header("Content-Length", str(len(data)))
            handler.end_headers()
            handler.wfile.write(data)

        self.upstream.respond = respond
        request = self.body()
        status, headers, raw = self.post(request)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(raw)["choices"][0]["message"]["content"], "A.\n\nB.")
        self.assertEqual(json.loads(self.upstream.requests[0]["body"]), request)
        self.assertIs(json.loads(self.upstream.requests[0]["body"])["stream"], False)
        self.assertNotIn("x-turn-id", headers)

    # -- 2. защита от циклов префиксов --------------------------------------------------
    def test_orchestration_prefix_flood_is_aggregated_verbatim_without_divergence(self) -> None:
        self.flags(via_stream=True)
        prefix = "[гейт оркестрации: активен"
        pieces = [prefix] * 50
        self.serve([_text_frame(p) for p in pieces] + [_delta_frame({}, "stop"), _DONE_FRAME])
        status, _, raw = self.post(self.body())
        self.assertEqual(status, 200)
        content = json.loads(raw)["choices"][0]["message"]["content"]
        self.assertEqual(content, prefix * 50)  # итог == конкатенации
        self.assertEqual(content.count(prefix), 50)  # ни лавины, ни потерь
        self.assertEqual(len(raw), len(json.dumps(json.loads(raw), ensure_ascii=False).encode()))

    def test_status_changes_between_steps_keep_every_prefix_exactly_once(self) -> None:
        self.flags(via_stream=True)
        statuses = [
            f"[гейт оркестрации: активен | роль: {role}] шаг {i}"
            for i, role in enumerate(("lead", "explorer", "worker", "reviewer", "coder"))
        ]
        steps = []
        for status_text in statuses:
            steps += [_text_frame(status_text[:27]), _text_frame(status_text[27:]), _text_frame("\n\n")]
        self.serve(steps + [_delta_frame({}, "stop"), _DONE_FRAME])
        status, _, raw = self.post(self.body())
        self.assertEqual(status, 200)
        content = json.loads(raw)["choices"][0]["message"]["content"]
        self.assertEqual(content, "".join(s + "\n\n" for s in statuses))
        self.assertEqual(content.count("[гейт оркестрации: активен"), len(statuses))

    # -- 3. мультиагентный цикл ---------------------------------------------------------
    def _tool_delta_frame(self, calls: list[dict[str, Any]]) -> bytes:
        return _delta_frame({"tool_calls": calls})

    def test_parent_tool_calls_merge_by_choice_and_tool_index(self) -> None:
        self.flags(via_stream=True)
        sub_args = {"Role": "Coder", "Prompt": "Fix test"}
        cmd_args = {"command": "python3 launch_seat.py --seat tl1"}
        sub_json, cmd_json = json.dumps(sub_args), json.dumps(cmd_args)
        cut_a, cut_b = len(sub_json) // 2, len(cmd_json) // 3
        self.serve([
            _text_frame("Запускаю сабагентов.", "reasoning_content"),
            self._tool_delta_frame([
                {"index": 0, "id": "call_sub", "type": "function",
                 "function": {"name": "invoke_subagent", "arguments": sub_json[:cut_a]}},
                {"index": 1, "id": "call_seat", "type": "function",
                 "function": {"name": "run_command", "arguments": cmd_json[:cut_b]}},
            ]),
            self._tool_delta_frame([
                {"index": 1, "function": {"arguments": cmd_json[cut_b:]}},
                {"index": 0, "function": {"arguments": sub_json[cut_a:]}},
            ]),
            _delta_frame({}, "tool_calls"),
            _DONE_FRAME,
        ])
        status, _, raw = self.post(self.body())
        self.assertEqual(status, 200, raw)
        choice = json.loads(raw)["choices"][0]
        message = choice["message"]
        self.assertEqual(choice["finish_reason"], "tool_calls")
        self.assertIsNone(message["content"])  # служебная преамбула — только в reasoning
        self.assertEqual(message["reasoning_content"], "Запускаю сабагентов.")
        calls = message["tool_calls"]
        self.assertEqual([c["id"] for c in calls], ["call_sub", "call_seat"])
        self.assertEqual([c["function"]["name"] for c in calls], ["invoke_subagent", "run_command"])
        self.assertEqual(json.loads(calls[0]["function"]["arguments"]), sub_args)
        self.assertEqual(json.loads(calls[1]["function"]["arguments"]), cmd_args)

    def test_sequential_parent_requests_keep_stream_continuity(self) -> None:
        """Родитель делает три последовательных запроса через хаб; каждый стрим цел."""
        self.flags(via_stream=True)
        scripts = [
            [self._tool_delta_frame([{"index": 0, "id": "c1", "type": "function", "function": {
                "name": "invoke_subagent",
                "arguments": json.dumps({"Role": "Coder", "Prompt": "p1"})}}]),
             _delta_frame({}, "tool_calls"), _DONE_FRAME],
            [self._tool_delta_frame([{"index": 0, "id": "c2", "type": "function", "function": {
                "name": "run_command",
                "arguments": json.dumps({"command": "python3 launch_seat.py"})}}]),
             _delta_frame({}, "tool_calls"), _DONE_FRAME],
            [_text_frame("Сабагенты завершили работу."), _text_frame("\n\n"),
             _text_frame("Итог готов."), _delta_frame({}, "stop"), _DONE_FRAME],
        ]
        counter = {"n": 0}

        def respond(handler: Any, body: bytes) -> None:
            step = counter["n"]
            counter["n"] += 1
            _send_sse(handler, scripts[step])

        self.upstream.respond = respond
        messages: list[dict[str, Any]] = [{"role": "user", "content": "go"}]
        seen: list[dict[str, Any]] = []
        for turn in range(3):
            status, _, raw = self.post(self.body(messages=list(messages)))
            self.assertEqual(status, 200, (turn, raw))
            choice = json.loads(raw)["choices"][0]
            seen.append(choice)
            msg = choice["message"]
            messages.append({k: v for k, v in msg.items() if k in ("role", "content", "tool_calls")})
            for call in msg.get("tool_calls") or []:
                messages.append({"role": "tool", "tool_call_id": call["id"], "content": "ok"})
        self.assertEqual([c["finish_reason"] for c in seen], ["tool_calls", "tool_calls", "stop"])
        self.assertEqual(seen[0]["message"]["tool_calls"][0]["function"]["name"], "invoke_subagent")
        self.assertEqual(seen[1]["message"]["tool_calls"][0]["function"]["name"], "run_command")
        self.assertEqual(seen[2]["message"]["content"], "Сабагенты завершили работу.\n\nИтог готов.")
        sent = [json.loads(r["body"]) for r in self.upstream.requests]
        self.assertEqual(len(sent), 3)
        self.assertTrue(all(s["stream"] is True for s in sent))
        self.assertEqual([len(s["messages"]) for s in sent], [1, 3, 5])

    def test_parallel_parent_requests_do_not_cross_contaminate(self) -> None:
        self.flags(via_stream=True)

        def respond(handler: Any, body: bytes) -> None:
            marker = json.loads(body)["messages"][-1]["content"]
            _send_sse(handler, [_text_frame(f"[{marker}] "), 0.05, _text_frame(f"конец {marker}"),
                                _delta_frame({}, "stop"), _DONE_FRAME])

        self.upstream.respond = respond
        results: dict[str, tuple[int, Any]] = {}

        def worker(marker: str) -> None:
            status, _, raw = self.post(self.body(messages=[{"role": "user", "content": marker}]))
            results[marker] = (status, json.loads(raw))

        markers = [f"m{i}" for i in range(6)]
        threads = [threading.Thread(target=worker, args=(m,)) for m in markers]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        self.assertEqual(sorted(results), sorted(markers))
        for marker, (status, data) in results.items():
            self.assertEqual(status, 200)
            self.assertEqual(data["choices"][0]["message"]["content"], f"[{marker}] конец {marker}")

    # -- 4. optional liveness -----------------------------------------------------------
    def test_telemetry_off_has_no_turn_id_header_and_no_registry_entry(self) -> None:
        self.flags(via_stream=True, telemetry=False)
        gate_in, gate_out = threading.Event(), threading.Event()
        self.serve([gate_in.set, lambda: gate_out.wait(10), _text_frame("ok"),
                    _delta_frame({}, "stop"), _DONE_FRAME])
        holder: dict[str, Any] = {}
        thread = threading.Thread(target=lambda: holder.update(r=self.post(self.body())))
        thread.start()
        try:
            self.assertTrue(gate_in.wait(10))
            self.assertEqual(get_registry().active_count(), 0)
        finally:
            gate_out.set()
            thread.join(timeout=30)
        status, headers, _ = holder["r"]
        self.assertEqual(status, 200)
        self.assertNotIn("x-turn-id", headers)
        self.assertEqual(get_registry().active_count(), 0)

    def test_telemetry_on_exposes_liveness_to_owner_while_request_is_held(self) -> None:
        self.flags(via_stream=True, telemetry=True)
        gate_in, gate_mid_in, gate_mid_out = threading.Event(), threading.Event(), threading.Event()
        gate_out = threading.Event()
        self.serve([gate_in.set, lambda: gate_out.wait(10), _text_frame("первый токен"),
                    gate_mid_in.set, lambda: gate_mid_out.wait(10),
                    _delta_frame({}, "stop"), _DONE_FRAME])
        holder: dict[str, Any] = {}
        thread = threading.Thread(target=lambda: holder.update(r=self.post(self.body())))
        thread.start()
        try:
            self.assertTrue(gate_in.wait(10))
            registry = get_registry()
            deadline = time.monotonic() + 10
            while registry.active_count() == 0 and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertEqual(registry.active_count(), 1)
            turn_id = next(iter(registry._entries))  # noqa: SLF001
            self.assertTrue(turn_id.startswith("pt-"))
            # до первого S: ход виден владельцу, прогресса нет
            status, _, snap = self.get(f"/v1/turns/{turn_id}")
            self.assertEqual(status, 200, snap)
            live = snap["liveness"]
            self.assertEqual(snap["backend"], "passthrough")
            self.assertEqual(snap["turn_id"], turn_id)
            self.assertIs(live["internal_stream"], True)
            self.assertIs(live["stream_requested"], False)
            self.assertEqual(live["last_progress_kind"], "none")
            self.assertIsNone(live["last_token_age_s"])
            self.assertIsNone(live["process_alive"])
            self.assertIsNone(live["soft_budget_used_s"])
            self.assertIsNone(live["soft_budget_limit_s"])
            self.assertGreater(live["idle_remaining_s"], 0)
            self.assertGreater(live["safety_cap_remaining_s"], 0)
            self.assertNotIn("test-key", json.dumps(snap))  # токен/хеш наружу не уходят
            # чужой владелец: 403/404, наличие чужого хода не раскрывается
            status_other, _, _ = self.get(
                f"/v1/turns/{turn_id}", {"Authorization": "Bearer test-key",
                                          "X-Turn-Owner-Token": "someone-else"})
            self.assertIn(status_other, (403, 404))
            # после первого S: last_progress_kind == S
            gate_out.set()
            self.assertTrue(gate_mid_in.wait(10))
            deadline = time.monotonic() + 10
            live = {}
            while time.monotonic() < deadline:
                _, _, snap = self.get(f"/v1/turns/{turn_id}")
                live = snap["liveness"]
                if live["last_progress_kind"] == "S":
                    break
                time.sleep(0.02)
            self.assertEqual(live["last_progress_kind"], "S")
            self.assertIsNotNone(live["last_token_age_s"])
        finally:
            gate_out.set()
            gate_mid_out.set()
            thread.join(timeout=30)
        status, headers, raw = holder["r"]
        self.assertEqual(status, 200, raw)
        self.assertEqual(headers["x-turn-id"], turn_id)
        self.assertEqual(json.loads(raw)["choices"][0]["message"]["content"], "первый токен")
        self.wait_registry_empty()
        self.assertEqual(self.get(f"/v1/turns/{turn_id}")[0], 404)

    def test_telemetry_registry_is_cleaned_after_truncated_upstream(self) -> None:
        self.flags(via_stream=True, telemetry=True)
        self.serve([_text_frame("частичный ответ")])  # EOF без finish_reason и [DONE]
        status, headers, raw = self.post(self.body())
        self.assertEqual(status, 502, raw)
        self.assertEqual(json.loads(raw)["error"]["type"], "upstream_incomplete_stream")
        self.wait_registry_empty()

    def test_detached_mode_off_hides_turn_lookup(self) -> None:
        self.flags(via_stream=True, telemetry=True)
        os.environ["BRIDGE_DETACHED_TURNS_ENABLED"] = "false"
        self.assertEqual(self.get("/v1/turns/pt-0123456789abcdef")[0], 404)

    # -- 5. совместимость ---------------------------------------------------------------
    def test_health_keeps_exactly_seven_legacy_keys_for_every_flag_combination(self) -> None:
        import itertools

        for combo in itertools.product((False, True), repeat=len(_ALL_FLAGS)):
            for name, value in zip(_ALL_FLAGS, combo):
                os.environ[name] = "true" if value else "false"
            for path in ("/health", "/v1/health"):
                with self.subTest(flags=combo, path=path):
                    status, _, data = self.get(path, {})
                    self.assertEqual(status, 200)
                    self.assertEqual(set(data), _HEALTH_KEYS)
                    self.assertEqual(len(data), 7)
                    self.assertEqual(data["transport"], "droid-exec")
                    self.assertIs(data["tool_emulation"], True)

    def test_error_body_keeps_droid_error_type_for_all_neutral_flag_values(self) -> None:
        for neutral in (False, True):
            with self.subTest(neutral=neutral):
                self.flags(neutral=neutral)
                body = hub_server.Handler._error_body({"state": "droid_error", "err": ""})
                self.assertEqual(body["type"], "droid_error")
                self.assertEqual(body["code"], 502)
                self.assertIn("cli-exec" if neutral else "droid exec", body["message"])

    def test_cli_branch_http_error_keeps_droid_error_type(self) -> None:
        """Реальная CLI-ветка (FakeDroid): молчаливая подмена модели -> 502 droid_error."""
        install_droid_stand()  # claude-sonnet-5-5 обслуживает FakeDroid (CLI-ветка)
        self.hub.configure(substitute_model="some-default-model")
        for neutral in (False, True):
            with self.subTest(neutral=neutral):
                self.flags(neutral=neutral)
                status, body = self._post_json(
                    {"model": "claude-sonnet-5-5", "prompt_cache_key": f"chat-ns-{neutral}",
                     "messages": [{"role": "user", "content": "hi"}]}
                )
                self.assertEqual(status, 502, body)
                self.assertEqual(body["error"]["type"], "droid_error")

    # -- 6. sliding window --------------------------------------------------------------
    def test_sliding_window_survives_total_time_beyond_idle(self) -> None:
        self.flags(via_stream=True)
        self.small_windows(first=0.5, idle=0.6)
        pieces = [f"часть {i}. " for i in range(6)]
        steps: list[Any] = []
        for piece in pieces:
            steps += [_text_frame(piece), 0.25]
        self.serve(steps + [_delta_frame({}, "stop"), _DONE_FRAME])
        started = time.monotonic()
        status, _, raw = self.post(self.body())
        elapsed = time.monotonic() - started
        self.assertEqual(status, 200, raw)
        self.assertGreater(elapsed, 0.6)  # суммарно дольше idle, но пауза каждый раз короче
        self.assertEqual(json.loads(raw)["choices"][0]["message"]["content"], "".join(pieces))

    def test_heartbeat_comments_do_not_shift_idle_window(self) -> None:
        self.flags(via_stream=True)
        self.small_windows(first=0.5, idle=0.6)
        beats: list[Any] = []
        for _ in range(40):
            beats += [b": keepalive\n\n", 0.1]
        self.serve([_text_frame("начало")] + beats + [_delta_frame({}, "stop"), _DONE_FRAME])
        started = time.monotonic()
        status, _, raw = self.post(self.body())
        elapsed = time.monotonic() - started
        self.assertEqual(status, 504, raw)
        self.assertEqual(json.loads(raw)["error"]["type"], "upstream_timeout")
        self.assertLess(elapsed, 3.0)  # 4 с heartbeat не продлили окно 0.6 с

    def test_ping_literals_and_empty_events_do_not_shift_first_progress_window(self) -> None:
        self.flags(via_stream=True)
        self.small_windows(first=0.5, idle=0.6)
        beats: list[Any] = []
        for _ in range(40):
            beats += [b"data: ping\n\n", 0.05, b"data: {}\n\n", 0.05, b": c\n\n", 0.05]
        self.serve(beats + [_text_frame("поздно"), _delta_frame({}, "stop"), _DONE_FRAME])
        started = time.monotonic()
        status, _, raw = self.post(self.body())
        self.assertEqual(status, 504, raw)
        self.assertLess(time.monotonic() - started, 3.0)
        self.assertEqual(json.loads(raw)["error"]["type"], "upstream_timeout")

    def test_safety_cap_is_absolute_for_endless_useful_stream(self) -> None:
        self.flags(via_stream=True)
        self.small_windows(first=0.5, idle=0.6, cap=1.5)
        steps: list[Any] = []
        for i in range(60):
            steps += [_text_frame(f"x{i} "), 0.1]
        self.serve(steps + [_delta_frame({}, "stop"), _DONE_FRAME])
        started = time.monotonic()
        status, _, raw = self.post(self.body())
        elapsed = time.monotonic() - started
        # ADR AD-001: истечение safety cap детерминированно даёт 504 (обрыв сокета watcher'ом
        # после окна также трактуется как таймаут, а не 502).
        self.assertEqual(status, 504, raw)
        self.assertEqual(json.loads(raw)["error"]["type"], "upstream_timeout")
        self.assertGreaterEqual(elapsed, 1.2)
        self.assertLess(elapsed, 4.5)  # без потолка поток шёл бы ~6 с и дал 200


if __name__ == "__main__":
    unittest.main()
