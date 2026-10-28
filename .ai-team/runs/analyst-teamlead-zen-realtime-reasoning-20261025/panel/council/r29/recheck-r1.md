# Механический RECHECK после R1 Совета Тимлидов по коду (цикл 3, run analyst-teamlead-zen-realtime-reasoning-20261025)

- Проверяемый артефакт: `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/package.md` (`sha256=674edaca247fa44fb9639f81a52dbfe62235889400a00a99eec3f6c321db2b82`)
- Длина файлов кандидата: `server.py` = `6991` строк, `tests/test_realtime_reasoning.py` = `1577` строк, `tests/test_step_interruption.py` = `1088` строк.

RECHECK F-001 (skeptic skeptic-F-001, blocking): `server.py:2406` → `resp = active_conn.getresponse()` | **F-001 — барьер доставки остаётся немонотонным.**
RECHECK F-002 (skeptic skeptic-F-002, blocking): `server.py:5808` → `gate.acquire()` | **F-002 — первый статус теряется при ожидании spawn-limiter.**
RECHECK F-003 (skeptic skeptic-F-003, blocking): `server.py:2395` → `else http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)` | **F-003 [pre-existing] — общий deadline/cancellation не охватывает всю цепочку I/O.**
RECHECK F-004 (skeptic skeptic-F-004, blocking): `server.py:1738` → `state_dir = tempfile.mkdtemp(prefix="zen-serve-state-")` | **F-004 — RW-004 не закрывает ошибку создания state-dir.**
RECHECK F-005 (skeptic skeptic-F-005, blocking): `server.py:6477` → `if attempts.allow_retry(reason):` | **F-005 [pre-existing] — JSON-повторы теряют частичный вывод.**
RECHECK F-006 (skeptic skeptic-F-006, blocking): `server.py:5298` → `if attempts.allow_retry(f"prompt_status_{_ps_code}"):` | **F-006 [pre-existing] — SSE теряет usage некоторых повторов.**
RECHECK F-007 (skeptic skeptic-F-007, blocking): `server.py:2832` → `def _native_call_as_dsh(` | **F-007 [pre-existing] — native serve-путь обходит существующий адаптер схем инструментов.**
RECHECK F-008 (skeptic skeptic-F-008, blocking): `server.py:1115` → `if proc.poll() is not None:` | **F-008 [pre-existing] — legacy cleanup считает смерть лидера смертью группы.**
RECHECK F-009 (skeptic skeptic-F-009, blocking): `server.py:4732` → `def _execute_once(self) -> dict[str, Any]:` | **F-009 [pre-existing] — watchdog не распространяется на запасной JSON/run-путь.**
RECHECK F-010 (skeptic skeptic-F-010, blocking): `server.py:1700` → `data = _as_dict(_loads_object(target.read_text("utf-8")))` | **F-010 [pre-existing] — повреждённая кодировка dynamic config прерывает запрос.**
RECHECK F-011 (skeptic skeptic-F-011, blocking): `server.py:823` → `def _strip_interrupted(text: str) -> str:` | **F-011 [pre-existing] — очистка interruption-маркеров зависит от границы дельты.**
RECHECK F-012 (skeptic skeptic-F-012, blocking): `test_realtime_reasoning.py:545` → `self.saved_cfg = server.DYNAMIC_CONFIG_PATH` | **F-012 [pre-existing] — временной оракул не доказывает заявленные пределы и полноту.**
RECHECK F-013 (skeptic skeptic-F-013, blocking): `test_realtime_reasoning.py:424` → `def test_slow_upstream_gets_initial_status_before_1s(self) -> None:` | **F-013 [pre-existing] — измерительные проверки находятся в обычном компонентном контуре.**
RECHECK F-014 (skeptic skeptic-F-014, blocking): `server.py:5347` → `self._sse_error(_error_payload(f"serve error: {err.get('message')}"))` | **F-014 [pre-existing] — новые upstream-ошибки обходят маскирование.**
RECHECK F-015 (skeptic skeptic-F-015, non-blocking): проверка по полному тексту `package.md` (`candidate.diff` / `verification-traceability.md` / `execution-evidence.md`) | **F-015 [pre-existing] — независимый лог уже содержит ResourceWarning.**
RECHECK F-016 (skeptic skeptic-F-016, non-blocking): `server.py:3284` → `if result["first_token_at"] is None:` | **F-016 [pre-existing] — FU-004 закрыт не для всех tool-only завершений.**
RECHECK F-017 (skeptic skeptic-F-017, non-blocking): `test_realtime_reasoning.py:324` → `if not data:` | **F-017 — пояснения подавлений типов исправлены частично.**
RECHECK F-018 (realist realist-F-001, blocking): `server.py:5198` → `if not _limiter_ok:` | F-001
RECHECK F-019 (visionary visionary-F-01, blocking): проверка по полному тексту `package.md` (`candidate.diff` / `verification-traceability.md` / `execution-evidence.md`) | F-01 [blocking] КОРРЕКТНОСТЬ / Риски-прод.
RECHECK F-020 (visionary visionary-F-02, blocking): проверка по полному тексту `package.md` (`candidate.diff` / `verification-traceability.md` / `execution-evidence.md`) | F-02 [blocking] КОРРЕКТНОСТЬ / Полнота-ветки. RW-009 не закрыт.
RECHECK F-021 (visionary visionary-F-03, non-blocking): проверка по полному тексту `package.md` (`candidate.diff` / `verification-traceability.md` / `execution-evidence.md`) | F-03 [non-blocking] ПОЛНОТА / Корректность-границы.
RECHECK F-022 (visionary visionary-F-04, non-blocking): проверка по полному тексту `package.md` (`candidate.diff` / `verification-traceability.md` / `execution-evidence.md`) | F-04 [non-blocking] КОРРЕКТНОСТЬ-границы.
RECHECK F-023 (visionary visionary-F-05, non-blocking): проверка по полному тексту `package.md` (`candidate.diff` / `verification-traceability.md` / `execution-evidence.md`) | F-05 [non-blocking] СООТВЕТСТВИЕ КОНТЕКСТУ / Обработка ошибок.
RECHECK F-024 (visionary visionary-F-06, non-blocking): проверка по полному тексту `package.md` (`candidate.diff` / `verification-traceability.md` / `execution-evidence.md`) | F-06 [non-blocking] ПОЛНОТА / покрытие AC.
RECHECK F-025 (visionary visionary-F-07, non-blocking): проверка по полному тексту `package.md` (`candidate.diff` / `verification-traceability.md` / `execution-evidence.md`) | F-07 [non-blocking] РИСКИ-прод.
RECHECK F-026 (visionary visionary-F-08, non-blocking): проверка по полному тексту `package.md` (`candidate.diff` / `verification-traceability.md` / `execution-evidence.md`) | F-08 [non-blocking] СООТВЕТСТВИЕ КОНТЕКСТУ (директива про фичефлаги).
RECHECK F-027 (visionary visionary-F-09, non-blocking): проверка по полному тексту `package.md` (`candidate.diff` / `verification-traceability.md` / `execution-evidence.md`) | F-09 [non-blocking] СООТВЕТСТВИЕ КОНТЕКСТУ (testing.md, wall-clock).
RECHECK F-028 (visionary visionary-F-10, non-blocking): проверка по полному тексту `package.md` (`candidate.diff` / `verification-traceability.md` / `execution-evidence.md`) | F-10 [non-blocking] РИСКИ-scope-diff.
RECHECK F-029 (visionary visionary-F-11, non-blocking): проверка по полному тексту `package.md` (`candidate.diff` / `verification-traceability.md` / `execution-evidence.md`) | F-11 [non-blocking] СООТВЕТСТВИЕ КОНТЕКСТУ (FU-009 не закрыт).
RECHECK F-030 (visionary visionary-F-12, non-blocking): проверка по полному тексту `package.md` (`candidate.diff` / `verification-traceability.md` / `execution-evidence.md`) | F-12 [non-blocking] [sweep] КОРРЕКТНОСТЬ-данные.
