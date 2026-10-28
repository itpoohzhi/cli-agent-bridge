PANEL-NONCE: 831d3e05628a078e
ARTIFACT-SHA256: 88c02c37a7ca0be3d317217f23289dba07ddc681d922db207c7680a779128b6b

AMEND F-001 — priority=non-blocking; locations=architecture-packet.json#AD-001 (details.spawn, details.crash_recovery.registry, details.crash_recovery.creation, details.helper_cli_contract.validation), architecture-packet.json#THREAT-001, architecture-packet.json#VER-005 (clean_room_helper_oracle, orphan_oracles); fix=одним предложением в spawn и registry записать, что `/tmp/opencode-zen-bridge-leases/` — это только боевое значение по умолчанию позиционного `lease_dir`, которое родитель кладёт в argv. Единственный корень lease — переданный каталог. Reaper при старте сканирует только каталог, настроенный родителем (в тесте — тот же tmp-каталог). Добавить в VER-005 оракул с нестандартным `lease_dir` на запись lease и на подбор reaper-ом; причина: `AD-001.details.helper_cli_contract.validation` — «use only the passed isolated lease directory». Это нормативная строка, она однозначно разрешает неоднозначность, поэтому дефект редакционный: двух независимых корней в исполняемом контракте нет. Реальное расхождение есть только между словом «immediately creates /tmp/…» в spawn и этой строкой. Чинится правкой формулировки, механика не меняется. Дыра, мешающая Stage 3, не доказана, поэтому blocking не нужен: при бюджете 5/5 он отправил бы пакет к владельцу из-за одного предложения.

DISPUTE F-002 — класс: invalid — контр-evidence: `architecture-packet.json#high_load_envelope.field_sources.FD_worker`: «steady108=36baseline+18clients+18HTTP+12helperdrains+6reserve+6probe pipes+6lifeline_w+6leasehandles;transient6lifeline_r=>114». Те же поля есть в `AD-001.details.resource_accounting.fd`: поле `parent_watchdog_pipes: 6` — это и есть 6 write-концов `lifeline_w`. Они уже входят в сумму 108: 36+18+18+12+6+6+6+6=108. Прибавлять их второй раз нельзя. Правильный пик 108+6 transient `lifeline_r`=114≤128, как в пакете. Это двойной счёт со стороны находки.

AGREE F-003 rev=1 — проверил: в `architecture-packet.json#evidence[]` лежат EVD-001..EVD-064 (64 записи) и EVD-070..EVD-079 (10 записей), итого 74. `semantic_checks.evidence_refs` говорит «73 EVD records» и доходит до EVD-078. Это учётная ошибка v6, на архитектурный контракт она не влияет. Исправление: 74 и включить EVD-079. Non-blocking.

AGREE F-004 rev=1 — проверил: `architecture-packet.json#EVD-079.helper_cli_probe_source` содержит `proc.communicate()` после цикла `select` только по fd 0. Его докстринг: «не реализация Stage 3». Нормативный контракт `AD-001.details.helper_cli_contract.validation` требует иного: «Drain-ready pipes concurrently with fd0 EOF/TERM … no child pipe wait delaying EOF». Риск реален: Coder может скопировать код из `candidate_patch_from_origin_dev`. Блокером это не является, потому что норма уже записана. Нужна явная пометка, что копируется только ранний import-барьер и замер RSS, плюс тест со stderr serve больше 64 КиБ. Non-blocking.

1. КОРРЕКТНОСТЬ: VERDICT=PASS
   WHY=Топология parent→helper→serve в одной PGID, порядок lease→handshake→lsof→READY, шестиаргументный argv и ранний выход до `reload_catalog` согласованы по всем копиям. Арифметика FD верна, FD-находка F-002 не подтверждается. Остаётся редакционная неоднозначность корня lease (F-001, non-blocking), её снимает нормативная строка «use only the passed isolated lease directory».
   СОВЕТЫ: правки по F-001, F-003 и F-004 внести в Stage 3 или одним правочным коммитом пакета.

2. ПОЛНОТА: VERDICT=PASS
   WHY=REQ-001..020 и AC-001..026 привязаны к VER-001..005, есть HL-ENV (46 полей) и все гейты. Закрыты RW-001, RW-002, FU-001, FU-002. Учётный счётчик EVD отстаёт (F-003, non-blocking). Live-приёмка H0..H9 помечена NOT_RUN, для архитектурной стадии это допустимо.
   СОВЕТЫ: заменить 73 на 74 в `semantic_checks`.

3. РЕАЛИЗУЕМОСТЬ: VERDICT=PASS
   WHY=Три файла Coder, только stdlib, пробы EVD-075..079 исполнимы (VER-004 на копии с exit 0, helper RSS 31.72 MiB < 36.0). Стадии 3a→3b и `default=false` дают дешёвый откат. Что нужно, чтобы взлетело: пройти H3 и H6 до H7. Оба гейта блокирующие, без waiver.
   СОВЕТЫ: нет.

4. РИСКИ: VERDICT=PASS
   WHY=Листенер-takeover, parent-SIGKILL в пяти точках, reaper, fail-closed на 401/403 и раздельные `_ServeHealth`/`_UpstreamBreaker` предусмотрены. При росте нагрузки первой ломается память на слот (запас 15.2 MiB, H3 блокирует включение), затем FD и потоки (flood вне слотов пакет честно оговаривает). Остаточные риски (F-001, F-004) закрываются уточнением формулировок и тестом на дренаж stderr.
   СОВЕТЫ: добавить тест «serve пишет >64 КиБ в stderr до первого SSE → нет ложного `first_event_timeout`».

5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=В AD-001 рассмотрены L, A2, B (429 по [F-24]/[F-25]), `--stdio` (EVD-078), `--port 0`, общая БД и пустой XDG. У выбора A1+C есть причина: единственный путь с реальными `reasoning.delta`/`text.delta` ([F-17]..[F-19]) и откатом на legacy `run`.
   СОВЕТЫ: нет.

6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
   WHY=Пакет остаётся на stdlib `ThreadingHTTPServer`, публичный контракт :9883 и Google-срезы заморожены, `muse-bridge`, `~/.dsh` и `opencode.db` не затронуты, фичефлаг default=false с включением после H3/H6. Council PASS пакет не заявляет. Сверка seed: инструментов в этом проходе нет, поэтому SHA-256 сам не пересчитывал. По manifest r19 и history seq 20: `seed_input` совпадает дословно с заданной строкой, `seed_hex`=32e8fec3c4ef56e4dd55a9824c7555739e370bf3243d9ef74be1ec94fdd2eb5e (`SEED`=32e8fec3). `ranked_order` в manifest и history идентичен: claude-sonnet-5-5-high, muse-wonder-full-1.0, gpt-6.1-sol-high, gemini-4-argon-high, grok-4.7-high. Автор OpenAI исключён. Само вычисление хеша не подтверждено мной.
   СОВЕТЫ: нет.

ОБЩИЙ ВЕРДИКТ: PASS
