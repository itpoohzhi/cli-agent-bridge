# Механический RECHECK после R1 Совета Тимлидов по коду (цикл 2, run analyst-teamlead-zen-realtime-reasoning-20261025)

- Проверяемый артефакт: `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/package.md` (`sha256=2d0d7f1d6497ff00ecaf12bada3461971b497877a4619e28fee098123ad26e80`)
- Длина файлов кандидата: `server.py` = `6793` строк, `tests/test_realtime_reasoning.py` = `885` строк, `tests/test_step_interruption.py` = `1088` строк.

RECHECK F-001 (skeptic skeptic-01, blocking): `server.py:98` → `errno.EAGAIN,` | F-1
RECHECK F-002 (skeptic skeptic-02, blocking): `server.py:3254` → `result["exit_reason"] = "timeout"` | F-2
RECHECK F-003 (skeptic skeptic-03, blocking): `server.py:3022` → `if result["first_event_at"] is None and now - prompt_send_start > float(` | F-3
RECHECK F-004 (skeptic skeptic-04, blocking): `server.py:6370` → `# Неуспешная попытка не должна дублировать tool_calls при повторе.` | F-4
RECHECK F-005 (skeptic skeptic-05, blocking): `server.py:6203` → `_gate_j.acquire()` | F-5
RECHECK F-006 (skeptic skeptic-06, blocking): `server.py:1718` → `state_dir = tempfile.mkdtemp(prefix="zen-serve-state-")` | F-6
RECHECK F-007 (skeptic skeptic-07, blocking): `server.py:231` → `if serve_proc.poll() is not None:` | F-7
RECHECK F-008 (skeptic skeptic-08, blocking): `server.py:4954` → `except (OSError, ValueError):` | F-8
RECHECK F-009 (skeptic skeptic-09, blocking): `test_realtime_reasoning.py:112` → `if "__never_event__" in prompt:` | F-9
RECHECK F-010 (skeptic skeptic-10, non-blocking): проверка по полному тексту `package.md` (`candidate-cycle1-to-cycle2.diff` / `verification-traceability.md` / `execution-evidence.md`) | F-10
RECHECK F-011 (skeptic skeptic-11, non-blocking): `server.py:6260` → `if attempts.allow_retry(reason):` | F-11
RECHECK F-012 (skeptic skeptic-12, non-blocking): `server.py:75` → `"helper_lstart": str(int(time.time())),` | F-12
RECHECK F-013 (skeptic skeptic-13, non-blocking): `server.py:3215` → `if result["first_token_at"] is None:` | F-13
RECHECK F-014 (realist realist-01, blocking): `server.py:3252` → `and time.monotonic() >= deadline` | **F-001 — priority=blocking — незавершённая попытка может считаться успешной.**  
RECHECK F-015 (realist realist-02, blocking): `server.py:2941` → `if sse_conn.sock is not None:` | **F-002 — priority=blocking — SSE не восстанавливается после socket timeout.**  
RECHECK F-016 (realist realist-03, blocking): `server.py:3053` → `event = events.get(timeout=0.05)` | **F-003 — priority=blocking — HTTP-ошибка prompt зависит от наличия SSE-события.**  
RECHECK F-017 (realist realist-04, blocking): `server.py:2385` → `active_conn.request(method, path, payload, headers)` | **F-004 — priority=blocking — барьер доставки не является необратимым.**  
RECHECK F-018 (realist realist-05, blocking): `server.py:6194` → `while True:` | **F-005 — priority=blocking — общий потолок запусков не защищает JSON fallback.**  
RECHECK F-019 (realist realist-06, blocking): `server.py:3236` → `result["native_calls"].append(done[1])` | **F-006 — priority=blocking — текстовый tool call не закрывает serve-шаг.**  
RECHECK F-020 (realist realist-07, blocking): `server.py:5211` → `# После частичной доставки: step-interruption recovery ниже по incomplete-сигналу.` | **F-007 — priority=blocking — не все повторы reasoning разделены статусом.**  
RECHECK F-021 (realist realist-08, blocking): `server.py:6323` → `contents.append(content)` | **F-008 — priority=blocking — JSON способен вернуть одинаковый инструмент дважды [pre-existing].**  
RECHECK F-022 (realist realist-09, blocking): `server.py:1713` → `env["XDG_DATA_HOME"] = str(os.environ["XDG_DATA_HOME"])` | **F-009 — priority=blocking — ранние ошибки запуска обходят уборку.**  
RECHECK F-023 (realist realist-10, blocking): `server.py:5092` → `gate.acquire()` | **F-010 — priority=blocking — startup gate удерживается дольше startup-фазы.**  
RECHECK F-024 (realist realist-11, blocking): `server.py:195` → `except (OSError, subprocess.SubprocessError):` | **F-011 — priority=blocking — после смерти родителя могут остаться внуки serve.**  
RECHECK F-025 (realist realist-12, blocking): `server.py:2432` → `_deadline = time.monotonic() + 5.0` | **F-012 — priority=blocking — бюджет cleanup исчерпан до проверки результата SIGKILL.**  
RECHECK F-026 (realist realist-13, blocking): `server.py:4938` → `def _client_gone_check(self) -> bool:` | **F-013 — priority=blocking — RST не считается отключением клиента [pre-existing].**  
RECHECK F-027 (realist realist-14, blocking): `server.py:3042` → `if thinking_enabled and on_status is not None and now >= status_next:` | **F-014 — priority=blocking — статусный timer не принадлежит жизненному циклу запроса.**  
RECHECK F-028 (realist realist-15, blocking): `server.py:5649` → `gate = _StartupGate()` | **F-015 — priority=blocking — legacy не гарантирует первый видимый статус за секунду [pre-existing].**  
RECHECK F-029 (realist realist-16, blocking): `server.py:78` → `"start_ts": time.time(),` | **F-016 — priority=blocking — защита reaper от переиспользования helper PID неполна.**  
RECHECK F-030 (realist realist-17, blocking): `server.py:99` → `errno.EWOULDBLOCK,` | **F-017 — priority=blocking — ранняя helper-ветка обращается к неимпортированному errno.**  
RECHECK F-031 (realist realist-18, blocking): `server.py:5180` → `if _ps_code == 429:` | **F-018 — priority=blocking — transient upstream-события обходят Circuit Breaker.**  
RECHECK F-032 (realist realist-19, blocking): `test_realtime_reasoning.py:489` → `self.bridge.close()` | **F-019 — priority=blocking — оракулы не подтверждают заявленную полноту исправлений.**  
RECHECK F-033 (realist realist-20, non-blocking): `server.py:5167` → `_acc = self._serve_stream_usage or {}` | **F-020 — priority=non-blocking — usage не всех попыток попадает в итог.**  
RECHECK F-034 (realist realist-21, blocking): `test_realtime_reasoning.py:773` → `class TestReworkUnits(unittest.TestCase):` | **F-021 — priority=blocking — новый тестовый код нарушает явный запрет TestCase.**  
RECHECK F-035 (realist realist-22, blocking): `server.py:1696` → `"OPENCODE_ZEN_BRIDGE_SERVE_PERMISSION_POLICY", "ask_reject"` | **F-022 — priority=blocking — прокси-пул продвигается дважды на одну serve-попытку.**  
RECHECK F-036 (realist realist-23, non-blocking): `server.py:1433` → `_LSOF_CALLS: list[int] = []` | **F-023 — priority=non-blocking — диагностическая история lsof растёт без ограничения [pre-existing].**  
RECHECK F-037 (visionary visionary-01, blocking): проверка по полному тексту `package.md` (`candidate-cycle1-to-cycle2.diff` / `verification-traceability.md` / `execution-evidence.md`) | F-01 [blocking, КОРРЕКТНОСТЬ/РЕАЛИЗУЕМОСТЬ]
RECHECK F-038 (visionary visionary-02, blocking): проверка по полному тексту `package.md` (`candidate-cycle1-to-cycle2.diff` / `verification-traceability.md` / `execution-evidence.md`) | F-02 [blocking, КОРРЕКТНОСТЬ/ПОЛНОТА]
RECHECK F-039 (visionary visionary-03, blocking): проверка по полному тексту `package.md` (`candidate-cycle1-to-cycle2.diff` / `verification-traceability.md` / `execution-evidence.md`) | F-03 [blocking, РЕАЛИЗУЕМОСТЬ/РИСКИ]
RECHECK F-040 (visionary visionary-04, blocking): проверка по полному тексту `package.md` (`candidate-cycle1-to-cycle2.diff` / `verification-traceability.md` / `execution-evidence.md`) | F-04 [blocking, РЕАЛИЗУЕМОСТЬ/РИСКИ]
RECHECK F-041 (visionary visionary-05, blocking): проверка по полному тексту `package.md` (`candidate-cycle1-to-cycle2.diff` / `verification-traceability.md` / `execution-evidence.md`) | F-05 [blocking, КОРРЕКТНОСТЬ]
RECHECK F-042 (visionary visionary-06, blocking): проверка по полному тексту `package.md` (`candidate-cycle1-to-cycle2.diff` / `verification-traceability.md` / `execution-evidence.md`) | F-06 [blocking, ПОЛНОТА/РИСКИ]
RECHECK F-043 (visionary visionary-07, blocking): проверка по полному тексту `package.md` (`candidate-cycle1-to-cycle2.diff` / `verification-traceability.md` / `execution-evidence.md`) | F-07 [blocking, ПОЛНОТА/РИСКИ]
RECHECK F-044 (visionary visionary-08, non-blocking): проверка по полному тексту `package.md` (`candidate-cycle1-to-cycle2.diff` / `verification-traceability.md` / `execution-evidence.md`) | F-08 [non-blocking, РИСКИ]
RECHECK F-045 (visionary visionary-09, non-blocking): проверка по полному тексту `package.md` (`candidate-cycle1-to-cycle2.diff` / `verification-traceability.md` / `execution-evidence.md`) | F-09 [non-blocking, РЕАЛИЗУЕМОСТЬ]
RECHECK F-046 (visionary visionary-10, non-blocking): `test_step_interruption.py:67` → `SWALLOWED_TEXT = "2026-10-24 (MSK) — статус: проверяю вывод джобы job_fetch_01 и читаю goal.md."` | F-10 [non-blocking, scope-diff]
RECHECK F-047 (visionary visionary-11, non-blocking): проверка по полному тексту `package.md` (`candidate-cycle1-to-cycle2.diff` / `verification-traceability.md` / `execution-evidence.md`) | F-11 [non-blocking, СООТВЕТСТВИЕ КОНТЕКСТУ]
RECHECK F-048 (visionary visionary-12, non-blocking): проверка по полному тексту `package.md` (`candidate-cycle1-to-cycle2.diff` / `verification-traceability.md` / `execution-evidence.md`) | F-12 [non-blocking, КОРРЕКТНОСТЬ]
RECHECK F-049 (visionary visionary-13, non-blocking): проверка по полному тексту `package.md` (`candidate-cycle1-to-cycle2.diff` / `verification-traceability.md` / `execution-evidence.md`) | F-13 [non-blocking, ПОЛНОТА]
RECHECK F-050 (visionary visionary-14, non-blocking): проверка по полному тексту `package.md` (`candidate-cycle1-to-cycle2.diff` / `verification-traceability.md` / `execution-evidence.md`) | F-14 [non-blocking, ПОЛНОТА] [sweep]
