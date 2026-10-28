# Механический RECHECK после R1 Совета Тимлидов по коду (цикл 1, run analyst-teamlead-zen-realtime-reasoning-20261025)

- Проверяемый артефакт: `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/package.md` (`sha256=5b0d1dea0cf4996f6d744e0eb2d82176578091bad35c943dde722c09d3784df4`)
- Длина файлов кандидата: `server.py` = `6287` строк, `tests/test_realtime_reasoning.py` = `717` строк, `tests/test_step_interruption.py` = `1065` строк.

RECHECK F-001 (skeptic skeptic-01, blocking): `server.py:4848` → `attempts.note_spawn()` | ### F-001
RECHECK F-002 (skeptic skeptic-02, blocking): `server.py:2552` → `while not line_bytes.endswith(b"\n"):` | ### F-002
RECHECK F-003 (skeptic skeptic-03, blocking): `server.py:72` → `"parent_start_ts": parent_lstart,` | ### F-003
RECHECK F-004 (skeptic skeptic-04, blocking): `server.py:5770` → `result = _serve_one_attempt(` | ### F-004
RECHECK F-005 (skeptic skeptic-05, blocking): `test_realtime_reasoning.py:99` → `if "__never_event__" in prompt:` | ### F-005
RECHECK F-006 (skeptic skeptic-06, blocking): `server.py:4950` → `tool_choice=None,` | ### F-006
RECHECK F-007 (skeptic skeptic-07, blocking): `test_step_interruption.py:188` → `# Изоляция REQ-017: свежий бюджет повторов на каждый тест, без сброса в проде.` | ### F-007
RECHECK F-008 (skeptic skeptic-08, blocking): `server.py:1675` → `if esc == "u":` | ### F-008
RECHECK F-009 (skeptic skeptic-09, blocking): `server.py:2879` → `prompt_status["status"] = st` | ### F-009
RECHECK F-010 (skeptic skeptic-10, blocking): `server.py:2464` → `_ = self.helper.wait(timeout=0.5)` | ### F-010
RECHECK F-011 (skeptic skeptic-11, non-blocking): `server.py:1791` → `or len(head) == 4` | ### F-011
RECHECK F-012 (skeptic skeptic-12, non-blocking): `server.py:1339` → `STATUS_INITIAL = "[мост] Подключение к модели…\n"` | ### F-012
RECHECK F-013 (skeptic skeptic-13, non-blocking): `server.py:2495` → `for candidate in range(20000 + (os.getpid() % 20000), 60000):` | ### F-013
RECHECK F-014 (skeptic skeptic-14, non-blocking): `server.py:2654` → `if isinstance(text_value, str):` | ### F-014
RECHECK F-015 (skeptic skeptic-15, non-blocking): `server.py:2569` → `# stderr помощника дренируется в лог, stdout после рукопожатия молчит.` | ### F-015
RECHECK F-016 (skeptic skeptic-16, non-blocking): `server.py:4877` → `xs["first_event_ms"] = result["first_event_ms"]` | ### F-016
RECHECK F-017 (skeptic skeptic-17, non-blocking): `server.py:1795` → `def _select_transport(res: _Resilience | None = None) -> str:` | ### F-017 [sweep]
RECHECK F-018 (skeptic skeptic-18, non-blocking): `test_realtime_reasoning.py:441` → `self.assertGreaterEqual(len(model_reasoning), 3, chunks)` | ### F-018
RECHECK F-019 (realist realist-01, blocking): `server.py:3018` → `if text_value.strip():` | **F-001 — priority=P1, blocking. Потеря пробельных дельт.**  
RECHECK F-020 (realist realist-02, blocking): `server.py:1560` → `class _JsonParser:` | **F-002 — priority=P1, blocking. Собственный JSON-парсер повреждает Unicode.**  
RECHECK F-021 (realist realist-03, blocking): `server.py:2718` → `on_status: Callable[[str], None] | None = None,` | **F-003 — priority=P1, blocking. Общий дедлайн не управляет serve-попыткой.**  
RECHECK F-022 (realist realist-04, blocking): `server.py:2827` → `sse_conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)` | **F-004 — priority=P1, blocking. Пять секунд тишины ошибочно обрывают serve.**  
RECHECK F-023 (realist realist-05, blocking): `server.py:2403` → `active_conn = (` | **F-005 — priority=P1, blocking. Timeout cleanup не применяется к существующему соединению.**  
RECHECK F-024 (realist realist-06, blocking): `server.py:2740` → `lease, port, _pw = _spawn_serve(attempt_id, serve_env)` | **F-006 — priority=P1, blocking. Первая видимая реакция отсутствует во время setup.**  
RECHECK F-025 (realist realist-07, blocking): `server.py:1096` → `def lines(self, deadline: float, idle_s: float = 0.0,` | **F-007 — priority=P1, blocking. Legacy-watchdog зависит от отсутствия stdout.**  
RECHECK F-026 (realist realist-08, blocking): `server.py:4848` → `attempts.note_spawn()` | **F-008 — priority=P1, blocking. Serve обходит защиты холодного старта.**  
RECHECK F-027 (realist realist-09, blocking): `server.py:4866` → `if not force_serve:` | **F-009 — priority=P1, blocking. Fallback может превысить потолок трёх запусков.**  
RECHECK F-028 (realist realist-10, blocking): `server.py:4914` → `res.serve_health.record_success()` | **F-010 — priority=P1, blocking. Успех serve не закрывает HALF_OPEN Circuit Breaker.**  
RECHECK F-029 (realist realist-11, blocking): `server.py:2413` → `resp = active_conn.getresponse()` | **F-011 — priority=P1, blocking. Prompt-response не управляет барьером доставки и классификацией ошибок.**  
RECHECK F-030 (realist realist-12, blocking): `server.py:3073` → `elif etype == "error":` | **F-012 — priority=P1, blocking. Ошибки провайдера обходят прежнюю recovery-семантику.**  
RECHECK F-031 (realist realist-13, blocking): `server.py:4753` → `def _run_serve_stream_attempts(` | **F-013 — priority=P1, blocking. Теряется `tool_choice`.**  
RECHECK F-032 (realist realist-14, blocking): `server.py:3046` → `done = tool_state.complete(call_id)` | **F-014 — priority=P1, blocking. Serve не останавливается после инструментального шага.**  
RECHECK F-033 (realist realist-15, blocking): `server.py:4843` → `parser_box[0] = (` | **F-015 — priority=P1, blocking. Повтор serve дублирует уже отданный текст.**  
RECHECK F-034 (realist realist-16, blocking): `server.py:4886` → `if result.get("exit_reason") in (` | **F-016 — priority=P2, blocking. Usage неуспешных попыток теряется.**  
RECHECK F-035 (realist realist-17, blocking): `server.py:1768` → `state_dir = tempfile.mkdtemp(prefix="zen-serve-state-")` | **F-017 — priority=P1, blocking. На ошибках запуска пропускается cleanup.**  
RECHECK F-036 (realist realist-18, blocking): `server.py:2842` → `events: queue.Queue[dict[str, object] | None] = queue.Queue(maxsize=4096)` | **F-018 — priority=P1, blocking. SSE-reader может навсегда остаться на заполненной очереди.**  
RECHECK F-037 (realist realist-19, blocking): `server.py:2570` → `threading.Thread(target=_drain_stderr, args=(helper, []), daemon=True).start()` | **F-019 — priority=P2, blocking. Дренаж stderr накапливает неограниченную память.**  
RECHECK F-038 (realist realist-20, blocking): `server.py:2374` → `def _lsof_listener_pid(port: int) -> int | None:` | **F-020 — priority=P1, blocking. Авторизация отправляется без обязательного ownership-proof слушателя.**  
RECHECK F-039 (realist realist-21, blocking): `server.py:74` → `"helper_lstart": str(int(time.time())),` | **F-021 — priority=P1, blocking. Reaper не проверяет идентичность процессов.**  
RECHECK F-040 (realist realist-22, blocking): `server.py:174` → `finally:` | **F-022 — priority=P1, blocking. Lifeline не гарантирует остановку всего дерева при смерти моста.**  
RECHECK F-041 (realist realist-23, blocking): `server.py:4750` → `except (OSError, ValueError):` | **F-023 — priority=P1, blocking. Отмена клиента реализована не во всех режимах.**  
RECHECK F-042 (realist realist-24, blocking): `test_realtime_reasoning.py:376` → `def test_watchdog_first_event_timeout(self) -> None:` | **F-024 — priority=P1, blocking. Матрица PASS не соответствует содержимому оракулов.**  
RECHECK F-043 (realist realist-25, blocking): `test_realtime_reasoning.py:2` → `# pyright: reportAny=false, reportPrivateUsage=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, re` | **F-025 — priority=P2, blocking. «Ноль диагностик» получен с подавленными правилами.**  
RECHECK F-044 (realist realist-26, blocking): `test_realtime_reasoning.py:299` → `self.env.stop()` | **F-026 — priority=P2, blocking [sweep]. Тест удаляет исходное значение окружения.**  
RECHECK F-045 (realist realist-27, blocking): `test_realtime_reasoning.py:279` → `class TestLegacyWatchdogAndKillpg(unittest.TestCase):` | **F-027 — priority=P2, blocking. Новый тестовый модуль нарушает прямой запрет TestCase.**  
RECHECK F-046 (realist realist-28, blocking): `test_realtime_reasoning.py:321` → `self.assertLessEqual(statuses[0][0], 1.0)` | **F-028 — priority=P2, blocking. Измерения времени смешаны с обычным тестовым контуром.**  
RECHECK F-047 (realist realist-29, blocking): `server.py:1326` → `DYNAMIC_CONFIG_PATH = Path(__file__).resolve().parent / "dynamic_config.json"` | **F-029 — priority=P2, blocking. Эксплуатационные изменения не документированы.**  
RECHECK F-048 (realist realist-30, blocking): `server.py:1844` → `return "reasoning", {"reasoning_content": delta}` | **F-030 — priority=P2, blocking. Фильтр чужих сессий применяется после потери sessionID.**  
RECHECK F-049 (realist realist-31, non-blocking): `server.py:1777` → `def _is_native_opencode_bin(path: str) -> bool:` | **F-031 — priority=P3, non-blocking. Проверка нативного бинарника почти всегда разрешающая.**  
RECHECK F-050 (realist realist-32, blocking): `server.py:4877` → `xs["first_event_ms"] = result["first_event_ms"]` | **F-032 — priority=P2, blocking [sweep]. Поля «первого события» переписываются последующими попытками.**  
RECHECK F-051 (visionary visionary-01, blocking): `server.py:2360` → `def _parent_lstart() -> str:` | F-01 [blocking] Whitespace-дельты не пересылаются клиенту
RECHECK F-052 (visionary visionary-02, blocking): `server.py:2360` → `def _parent_lstart() -> str:` | F-02 [blocking] Гонка выбора порта serve и отправка пароля не тому serve
RECHECK F-053 (visionary visionary-03, blocking): `server.py:5351` → `dedup[0] = (` | F-03 [blocking] Регрессия дефолтного пути `run`: watchdog первого токена 60 с
RECHECK F-054 (visionary visionary-04, blocking): `server.py:2360` → `def _parent_lstart() -> str:` | F-04 [blocking] REQ-013 не выполнен для serve
RECHECK F-055 (visionary visionary-05, blocking): `server.py:2360` → `def _parent_lstart() -> str:` | F-05 [blocking] Результат prompt-POST игнорируется, `FALLBACK_DECISION_TABLE` мёртва
RECHECK F-056 (visionary visionary-06, blocking): `server.py:4734` → `def _client_gone_check(self) -> bool:` | F-06 [blocking] Повтор после отданного контента дублирует text и tool_calls
RECHECK F-057 (visionary visionary-07, blocking): `server.py:5351` → `dedup[0] = (` | F-07 [blocking] Первый статус ≤1.0 с (REQ-004) не гарантирован
RECHECK F-058 (visionary visionary-08, blocking): `server.py:1800` → `)` | F-08 [blocking] Реальный wire v2.1.2 не проверен: события с пустым `data`
RECHECK F-059 (visionary visionary-09, blocking): `server.py:2360` → `def _parent_lstart() -> str:` | F-09 [blocking] Утечка tempdir и FD при сбое запуска serve
RECHECK F-060 (visionary visionary-10, blocking): проверка по полному тексту `package.md` (`verification-traceability.md` / `execution-evidence.md`) | F-10 [blocking] Пробелы покрытия AC и неточная матрица
RECHECK F-061 (visionary visionary-11, blocking): `server.py:1560` → `class _JsonParser:` | F-11 [blocking] Самописный `_JsonParser` / `_loads_object`, ошибки маскируются
RECHECK F-062 (visionary visionary-12, blocking): `test_realtime_reasoning.py:2` → `# pyright: reportAny=false, reportPrivateUsage=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, re` | F-12 [blocking] Подавления типов без обоснования
RECHECK F-063 (visionary visionary-13, non-blocking): проверка по полному тексту `package.md` (`verification-traceability.md` / `execution-evidence.md`) | F-13 [non-blocking] Тавтологичные и неустойчивые тесты
RECHECK F-064 (visionary visionary-14, non-blocking): `server.py:2360` → `def _parent_lstart() -> str:` | F-14 [non-blocking] Lease-каталог в `/tmp` без владельца и режима
RECHECK F-065 (visionary visionary-15, non-blocking): `server.py:1560` → `class _JsonParser:` | F-15 [non-blocking] Тестовый хук и вакуумная проверка нативного бинаря
RECHECK F-066 (visionary visionary-16, non-blocking): `test_step_interruption.py:67` → `FAKE_OPENCODE = r"""#!/usr/bin/env python3` | F-16 [non-blocking] Косметический реформат чужих областей
RECHECK F-067 (visionary visionary-17, non-blocking): проверка по полному тексту `package.md` (`verification-traceability.md` / `execution-evidence.md`) | F-17 [non-blocking] Размер функций и дубли
RECHECK F-068 (visionary visionary-18, non-blocking): проверка по полному тексту `package.md` (`verification-traceability.md` / `execution-evidence.md`) | F-18 [non-blocking] Изменённый оракул `test_step_interruption.py`
RECHECK F-069 (visionary visionary-19, non-blocking): `server.py:2360` → `def _parent_lstart() -> str:` | F-19 [non-blocking] Жизненный цикл потоков и очереди
RECHECK F-070 (visionary visionary-20, non-blocking): `server.py:2360` → `def _parent_lstart() -> str:` | F-20 [non-blocking] [sweep] Watchdog считает только reasoning/text/завершённый tool
RECHECK F-071 (visionary visionary-21, blocking): `test_step_interruption.py:188` → `# Изоляция REQ-017: свежий бюджет повторов на каждый тест, без сброса в проде.` | F-21 [blocking] [pre-existing] Прямая мутация `os.environ` в изменённом тестовом файле
