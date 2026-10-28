PANEL-NONCE: f7dfb4010f8a6be7
ARTIFACT-SHA256: 88c02c37a7ca0be3d317217f23289dba07ddc681d922db207c7680a779128b6b
Подтверждение канона: общий канон ~/Мой диск/Context/AGENTS.md прочитан целиком (до <!-- КАНОН-КОНЕЦ -->); проектные файлы правил в рабочей папке отсутствуют.

AMEND F-001 — priority=non-blocking; locations=architecture-packet.json#AD-001 (`details.spawn`, `details.crash_recovery.registry`, `details.crash_recovery.creation`), architecture-packet.json#THREAT-001, architecture-packet.json#VER-005; fix=одной редакторской фразой закрепить, что `lease_dir` в argv есть единственный корень lease, а `/tmp/opencode-zen-bridge-leases/` — только его боевое значение по умолчанию. Startup reaper сканирует тот же `lease_dir`; negative-оракул VER-005 с нестандартным `lease_dir` проверяет и запись, и подбор при следующем старте. — причина: NEW: проверил строки 1987, 2568, 2589, 2767 пакета (RECHECK). Родитель сам кладёт `str(lease_dir)` в позиционный argv. Фиксированный путь стоит в `registry` именно как значение по умолчанию. Помощник пишет только в переданный каталог. Реальный второй корень отсутствует, остаётся неоднозначная формулировка, которую Coder читает однозначно. Лишь формулировка допускает прочтение «helper хардкодит /tmp-путь, reaper смотрит в другой каталог». Это правка текста, не архитектурный дефект, поэтому blocking я снимаю.

WITHDRAW F-002 — NEW: architecture-packet.json:3633 (поле `FD_worker`) расшифровывает steady 108 как «36baseline+18clients+18HTTP+12helperdrains+6reserve+6probe pipes+6lifeline_w+6leasehandles». `lifeline_w` уже входят в 108 (в `fd` они названы `parent_watchdog_pipes: 6`). Поэтому 108 + 6 transient `lifeline_r` = 114 ≤ 128 верно, а пик 120 из моей находки считал `lifeline_w` дважды. Проверил сам: 36+18+18+12+6+6+6+6 = 108.

AGREE F-003 rev=1 — проверил: python-проверка из RECHECK. В `evidence[]` 74 записи EVD-001..EVD-079 с учётом EVD-070+, а в `semantic_checks.evidence_refs` (около строки 4540) осталось «73 EVD records». Это учётная неточность, non-blocking, правится одной цифрой.

AGREE F-004 rev=1 — проверил: architecture-packet.json:1455 и 2767. Тело `_run_serve_helper_cli` в EVD-079 помечено docstring как «проба, не реализация Stage 3». Нормативный контракт (строка 2767) требует неблокирующий дренаж stdout/stderr serve в том же тике, что и EOF/TERM. Дефекта в контракте нет, остаётся риск, что Coder перенесёт `communicate()` из пробы. Поэтому non-blocking: в Stage 3 дополнить VER-005 тестом на более чем 64 КиБ в stderr до первого SSE.

1. КОРРЕКТНОСТЬ: VERDICT=PASS
   WHY=RW-001 и RW-002 закрыты проверяемыми изменениями (architecture-packet.json#EVD-079, #AD-001, rework_resolutions_a5). Топология parent→helper→serve в одной PGID, порядок lease→handshake→lsof→READY, арифметика FD (108+6=114≤128) и потоков (55) согласованы. Остаётся только неоднозначность корня lease (F-001, non-blocking).

2. ПОЛНОТА: VERDICT=PASS
   WHY=REQ-001..020 привязаны к VER-001..005, HL-ENV из 46 полей, гейты C-MULT/S-HERD/H-CPU/R-BULK/T-LIFE/O-EXIT/M-SEM, модель угроз и rollout H0..H9 присутствуют. Живые прогоны честно помечены NOT_RUN. FU-001 (`--config` у каждого вызова ruff) и FU-002 (cycle 6, architect-06) закрыты.

3. РЕАЛИЗУЕМОСТЬ: VERDICT=PASS
   WHY=Механика подтверждена пробами EVD-075..079: helper peak 31.72 MiB при оценке 36.0, VER-004 exit 0 в обычном и hostile-конфиге, три замороженных SHA не изменены. Реализация идёт в трёх файлах, поэтапно (Group A → Group B), с kill-switch по умолчанию false.

4. РИСКИ: VERDICT=PASS
   WHY=Покрыты takeover листенера, parent-SIGKILL в пяти точках, form/permission → cancel/reject → interrupt, раздельные `_ServeHealth` и `_UpstreamBreaker`, cap=3, слоты 6/12. Запас по памяти на слот узкий (15.2 MiB), но его ловит H3 с блокировкой H7 без waiver. Нормативный дренаж pipe см. F-004 (non-blocking).

5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=В AD-001 разобраны L, A2, B (429 по F-24/F-25), `--port 0`, `serve --stdio` (EVD-078), общая БД, пустой XDG и разделение 3a/3b. Выбор A1+C обоснован. При росте нагрузки первыми упираются RSS на слот и FD; оба закрыты гейтом H3 без повышения лимитов.

6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
   WHY=Пакет остаётся на stdlib `ThreadingHTTPServer`, публичный контракт :9883 и Google-срезы не затронуты, scope ограничен тремя файлами. Фичефлаг default=false с runtime-JSON, включение только на H7 после H3/H6. Council PASS пакет не заявляет.

ОБЩИЙ ВЕРДИКТ: PASS
