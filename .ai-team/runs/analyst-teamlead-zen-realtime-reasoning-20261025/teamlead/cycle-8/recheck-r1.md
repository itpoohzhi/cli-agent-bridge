# Механический RECHECK после R1 Совета Тимлидов по коду (цикл 8, run analyst-teamlead-zen-realtime-reasoning-20261025)

- Проверяемый артефакт: `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/package.md` (`sha256=1cb20e1b18d6a48062fd61f800051ee19c65200e6b0fc1a272a41ec2651cd5f8`)
- Длина файлов кандидата: `server.py` = `8170` строк, `tests/test_realtime_reasoning.py` = `3499` строк, `tests/test_step_interruption.py` = `1088` строк.

RECHECK F-001 (realist realist-F-001, blocking): `server.py:3355` → `"""Дочитать usage и native-вызовы того же шага, не выдавая следующий шаг."""` | F-001
RECHECK F-002 (realist realist-F-002, blocking): `server.py:1580` → `_MAX_SSE_LINE_BYTES = 1024 * 1024` | F-002 [pre-existing]
RECHECK F-003 (realist realist-F-003, blocking): `server.py:5438` → `self.is_client_gone is not None and self.is_client_gone()` | F-003 [sweep]
RECHECK F-004 (realist realist-F-004, blocking): `test_realtime_reasoning.py:411` → `class TestLegacyWatchdogAndKillpg(unittest.TestCase):` | F-004 [pre-existing]
