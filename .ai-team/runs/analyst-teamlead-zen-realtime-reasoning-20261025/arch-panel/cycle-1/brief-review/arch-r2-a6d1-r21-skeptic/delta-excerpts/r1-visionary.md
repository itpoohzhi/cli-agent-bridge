> PANEL-NONCE: fb077b9e5d4f6cf5
> ARTIFACT-SHA256: 88c02c37a7ca0be3d317217f23289dba07ddc681d922db207c7680a779128b6b
>
> **Closure check (verify-fixed, v5→v6):**
> - **RW-001 (память helper):** закрыт. `helper_estimate` повышен с 12.0 до 36.0 MiB. EVD-079 измерил реальный `--serve-helper` с полным шестиаргументным argv: peak 31.71875 MiB (`ps` и `ru_maxrss`, перевод в MiB указан). Резерв Stage 3 равен 4.28125 MiB.
>   - Арифметика сходится: 156.8+36+8=200.8; 216−200.8=15.2 ≥ 15; 6·216=1296; 1296+256=1552 ≤ 1638.4.
>   - Старые 12.0 / 12–14 MiB в действующих секциях не встречаются: `memory_ssot`, `capacity_formula`, QA-009, RISK-003, `H3_rollout_gate`, `rework_summary`.
>   - Ранний диспатчер стоит до тяжёлых импортов. E402 новых нет (EVD-076/077/079: 0 findings).
>   - Три замороженных SHA не изменены, VER-004 это проверяет.
> - **RW-002 (argv):** закрыт. Во всех секциях единый замкнутый argv из 6 позиционных аргументов. Есть `_run_serve_helper_cli(args: list[str]) -> int` с валидацией до spawn, `opencode_bin` приходит от родителя, `OPENCODE_BIN` в `serve_env` не попадает. Есть clean-room оракул (пустой HOME, monkeypatch `OPENCODE_BIN`, audit hook на `state/log/dynamic_config`). EVD-079 содержит 11 негативных argv-кейсов с exit=2.
> - **FU-001 (ruff):** закрыт. Явный `--config str(root/'ruff.toml')` стоит на каждом вызове. Есть проверка `formatted_copy.read_bytes()==files[0].read_bytes()`. Нормальный и «hostile XDG» прогоны оба exit 0.
> - **FU-002 (cycle 6):** закрыт. `cycle=6`, `role_plan` → `architect-06.json`, оба пути allowlist обновлены, адресат — a6/r15. Council PASS пакет не заявляет.
>
> 1. КОРРЕКТНОСТЬ: VERDICT=PASS
>    WHY=Внутренняя согласованность подтверждена по якорям `architecture-packet.json#EVD-079`, `#VER-005`, `#AD-001`, `rework_resolutions_a5`.
>    - Топология parent → helper(новая сессия) → serve (та же PGID) единообразна.
>    - Порядок «lease → handshake → lsof → READY» сохранён.
>    - FD-арифметика сходится: 36+18+18+12+6+6+6+6=108, +6 lifeline_r = 114 ≤ 128.
>    - Потоки: 1+18+6+6+6+12+6=55.
>    - Публичный контракт :9883, Google-маршрут и `_run_env` не тронуты.
>    - `contract_deltas` содержит только допустимые поведенческие изменения (CD-001/002) из брифа.
>
>    Замечание без блокировки: REQ-004 сужен grace-логикой до thinking-enabled slow-старта. Сужение явно оформлено в AD-002/CD-001 и проверяется в VER-005, а не скрыто.
>
>    СОВЕТЫ (при FAIL): не требуются.
>
> 2. ПОЛНОТА: VERDICT=PASS
>    WHY=Покрыты REQ-001..020 с привязкой к VER-001..005. Есть 46 полей HL-ENV, гейты C-MULT/S-HERD/H-CPU/R-BULK, T-LIFE, O-EXIT и M-SEM (с двойным доказательством для N/A). Есть fallback decision table, threat model с 5 угрозами, матрицы верификации, rollout H0..H9 и откат без рестарта.
>    - Эталонные источники указаны: muse-bridge, F-40/F-41.
>    - Живые H0..H9, Stage 3 и H3/H6 честно помечены NOT_RUN. Это допустимо для архитектурной стадии.
>
>    Замечание без блокировки: ADR-0005 отложен вне замороженного allowlist. Основание записано в `deferred`.
>
>    СОВЕТЫ (при FAIL): не требуются.
>
> 3. РЕАЛИЗУЕМОСТЬ: VERDICT=PASS
>    WHY=Ключевые механики подтверждены изолированными пробами на целевой машине (Python 3.14.7, ruff 0.17.2, basedpyright 1.40.2):
>    - минимальный helper-skeleton;
>    - полный VER-004 (exit 0, catalog 8/8, errors 0, reportAny 125);
>    - запись форматтера на копии без изменения замороженных срезов.
>
>    Объём сосредоточен в одном 4000+-строчном `server.py` плюс два тестовых файла, как требует allowlist. Стратегически это самый трудоёмкий кусок (helper, lease, reaper, terminal_quiescence, ServeHealth, динамический конфиг). Поставка поэтапная (Group A → Group B), kill-switch по умолчанию выключен (`default=false`), включение только после H3/H6.
>
>    Замечание без блокировки (стратегическое): резерв на код Stage 3 helper — 4.28 MiB (~13%), запас слота — 0.2 MiB сверх 15 MiB. Проба `drain/lease/SIGSTOP-quiescence` не нагружена, а оценки probe=8 MiB и serve idle=156.8 MiB не нагрузочные. Риск ловит гейт H3 (превышение блокирует H7 без waiver). Пакет это прямо фиксирует, поэтому это не дефект.
>
>    СОВЕТЫ (при FAIL): не требуются.
>
> 4. РИСКИ: VERDICT=PASS
>    WHY=Заложены:
>    - листенер-takeover (listener_pid==serve_pid, PGID, 0 байт секретов чужому);
>    - parent-SIGKILL на пяти точках, helper/reaper, PID/PGID reuse;
>    - permission/form → reject/cancel → interrupt с барьером Step2;
>    - fail-closed на 401/403;
>    - раздельные `_ServeHealth` и `_UpstreamBreaker`;
>    - потолки cap=3, `_RetryBudget`, слоты 6/12;
>    - sanitization env на всех трёх ветках;
>    - явный non-exactly-once для окна «до заголовков prompt».
>
>    При росте нагрузки главные точки отказа названы:
>    - RSS на слот (216 MiB, H3);
>    - FD/потоки (поток-flood вне слотов, пакет это оговаривает);
>    - SQLite — снят `:memory:`;
>    - квота Zen и egress IP, ротация которого не доказана (RISK-002 честно сформулирован).
>
>    Остаточные риски: вся live-приёмка NOT_RUN, а реальная совместимость deny/ask_reject с Zen доказывается только H6. Это явно отражено в Q-002 и RISK-001.
>
>    СОВЕТЫ (при FAIL): не требуются.
>
> 5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
>    WHY=В AD-001 рассмотрены:
>    - L (только watchdog/status);
>    - A2 (общий демон);
>    - B (прямой Zen HTTP, 429 по F-24/F-25);
>    - `--port 0`;
>    - `serve --stdio` (EVD-078, без публичной схемы);
>    - общая БД + `_StartupGate`;
>    - пустой `XDG_DATA_HOME`;
>    - разделение 3a/3b.
>
>    Причины выбора A1+C указаны. Выбранный путь стратегически выигрывает: он единственный даёт настоящие `reasoning.delta` и `text.delta` (F-17..F-19) и оставляет обратимость через legacy `run`. Он открывает дальнейшее развитие — потоковый прогресс шагов, вынос transport-слоя, а при появлении доказанной квоты и миграцию на B или A2 — без смены публичного контракта.
>
>    Замечание без блокировки: дословное многократное дублирование helper-контракта (~15 копий) повышает риск будущего расхождения. Сейчас копии идентичны. Рекомендуется при реализации опираться на единственный источник `AD-001.details.helper_cli_contract`.
>
>    СОВЕТЫ (при FAIL): не требуются.
>
> 6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
>    WHY=Пакет учитывает реальный stdlib-стек (`ThreadingHTTPServer`) и не навязывает Litestar/FastAPI. Он не меняет внешний контракт без указания в задаче и не выходит за scope: `muse-bridge`, `~/.dsh`, `opencode.db` и Google-маршрут не затрагиваются.
>    - `coder_target_files` — ровно три файла.
>    - Нет новых зависимостей и suppressions.
>    - Фичефлаг соответствует директиве GigaRC: код `default=false`, runtime-JSON, включение только на H7 после H3/H6.
>    - Пакет не заявляет Council PASS/ARCH_GATE_PASS; бюджет 5/5 сохранён.
>
>    СОВЕТЫ (при FAIL): не требуются.
>
> ОБЩИЙ ВЕРДИКТ: PASS
