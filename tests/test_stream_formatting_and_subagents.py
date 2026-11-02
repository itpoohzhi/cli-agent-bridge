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


if __name__ == "__main__":
    unittest.main()
