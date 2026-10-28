PANEL-NONCE: d9cefaf0c40e1c72
ARTIFACT-SHA256: e620a689a0d665a2c7979eba5a7073af41d9ca9473ea906ff9cee316fa0c7e02

1. КОРРЕКТНОСТЬ: VERDICT=FAIL
   WHY=Каркас C/A1 верный: один канонический поток событий на SSE и JSON, run остаётся kill-switch, границы BND-001..004 без цикла, секреты не зашиты. Рабочий путь ломается на бюджете управления. `session_setup_budget_s=0.2` склеен с create+subscribe+prompt, а R-BULK-I1 сходится только как 53.7 с ≤ 54 с. Единственный живой замер serve (F-19) даёт `execution.started` на 233 мс при готовности около 109 мс (F-20): после ready остаётся меньше 80 мс запаса на коротком промпте, до sqlite 2.27 ГБ (F-28) и тела около 103 КБ (F-30). Таймаут prompt POST уже считается неизвестной доставкой, и silent fallback на run запрещён. Включение флага превращает медленный session create в три явные ошибки подряд, реалтайм не появляется.
   СОВЕТЫ (при FAIL): Поднять бюджет create+subscribe до ≥2.0 с по отдельному потолку; prompt POST вести по остатку first-event watchdog, а не по общим 0.2 с. Fallback на run разрешать, пока нет заголовков ответа prompt POST; после заголовков silent fallback по-прежнему запрещён. Пересчитать R-BULK-I1 с новым потолком и записать сумму. Если сумма >54 с, ужать наследие `startup_wait`/`spawn_wait` отдельным AC либо честно поставить R-BULK-I1 в FAIL. Потолок 0.2 с ради прохождения 53.7≤54 не оставлять. В VER-005 добавить FakeClock: session create дольше 0.2 с и отсутствие заголовков prompt дают ровно один run после cleanup и суммарно ≤3 Popen; заголовки prompt уже получены — run не стартует.

2. ПОЛНОТА: VERDICT=FAIL
   WHY=REQ-001..012 и REQ-014..020 разложены по AD, QA и VER. Дыры в том, без чего Coder собирает другой протокол. REQ-013 требует ротацию чистых IP, AC-018 проверяет только подмену `_next_standalone_proxy`. F-15 и F-27: модель ходит на loopback georouter, loopback мимо прокси, конфиг georouter менять запрещено. В AD-001 spawn нет способа узнать ephemeral port и доказать, что listener принадлежит PGID ребёнка. `event_contract.payload_validation` отдаёт field paths кодеру и его же FakeServe; в ledger есть имена событий (F-19, F-22), а не пути полей дельты, tokens и tool part.
   СОВЕТЫ (при FAIL): Переписать statement REQ-013 под фактическую гарантию AC-018: per-spawn env как у run; egress Zen этим env не управляется. Убрать «сохраняется ротация чистых IP» из drivers AD-001; A1 оставить из-за изоляции failure domain и дельт F-19. Зафиксировать выбор порта: bind `127.0.0.1:0`, `getsockname`, close, spawn с этим `--port`, повтор только при EADDRINUSE внутри ready-бюджета; Basic и prompt слать после проверки, что слушатель в собственном PGID. В `event_contract` вложить минимальный JSON-фикстур v2.1.2: reasoning delta, text delta, step.ended tokens (`input`/`output`/`cached`/`reasoning`), жизненный цикл tool, execution failed. VER-005 падает при расхождении адаптера или FakeServe с фикстуром.

3. РЕАЛИЗУЕМОСТЬ: VERDICT=FAIL
   WHY=FakeServe со временем ответа <1 мс делает зелёными и 0.2 с, и любой выдуманный JSON. Поднять session budget нельзя: +1.8 с на попытку добавляет 5.4 с к 53.7 и пробивает 0.30×180. Порт и схема событий в пакете не замкнуты, чистая комната не сходит на Zen и не поймает подмену. Итогом Stage 3 будет зелёный VER-005 и мёртвый serve на том же хосте, где ребёнок уже молчал дольше 780 с (F-30).
   СОВЕТЫ (при FAIL): Те же правки бюджета, порта и фикстура, что в пунктах 1 и 2, до старта Coder. В VER-005 держать медленный FakeServe: create не укладывается в новый потолок, порт занят чужим PID, поле дельты сдвинуто. Такой прогон обязан дать явную ошибку или один допустимый run, и не иметь права стать зелёным за счёт совпадения адаптера с собственным фейком. Живой H1 не заменяет этот оракул.

4. РИСКИ: VERDICT=FAIL
   WHY=При росте до 6 параллельных запросов пакет проходит гейты числом, которое на хосте не выполняется. Память: 6×192 МиБ + 256 МиБ = 1408 ≤ 1638.4 при том, что единственный долгий serve в F-20 занимает 439 МиБ RSS; 6×439 МиБ уже выше лимита 2048 МиБ. Доля sqlite `opencode_local_db=10` взята так, чтобы 6≤0.60×10; физического потолка нет (OPEN-08, F-28). Gate после 5 с открывается fail-open, дальше шесть процессов бьют один файл. Политика инструментов: базовый вариант `permission={"*":"deny"}`, а EVD-050 предупреждает о Zen 403 из-за потери tool schema. Ответ 403 и неизвестная доставка prompt закрывают run fallback. FakeServe отказ Zen не показывает. Отдельный риск порта: reserve-bind/release отдаёт пароль и промпт чужому loopback-listener (THREAT-001).
   СОВЕТЫ (при FAIL): Базовая политика — `ask` и немедленный API reject, никогда allow. `deny` включать только после H6 без 403 и без файла на диске. Один переход deny↔ask допустим только до принятия prompt; после принятия prompt 403 остаётся fail-closed. В FakeServe: запрос allow всегда reject; фикстура 403 на deny ожидает вторую безопасную политику или явную ошибку, не зависание. Включить serve запрещено, если измеренный RSS нарушает `1×parent + M×child > 0.8×Mem_limit_per_pod`. C-MULT-I1 по sqlite снять с PASS, пока H3 не покажет отсутствие `database is locked` вне `FAIL_RETRY_LIMIT`. Проверка владельца порта из пункта 2 обязательна до первой отправки Basic.

5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=AD-001 сравнивает A2 (общий демон: один IP и один failure domain), B (прямой Zen: 429 в F-24 и F-25, PoC нет) и L (только watchdog: RC-1 остаётся, F-17/F-18). AD-002..004 каждый отвергают ещё по два варианта с наблюдаемым эффектом. На нагрузке пакет уже называет предел: 6 детей, очередь 4096/1 МиБ, слоты и память. Отказ от A2 держится на изоляции процесса и на дельтах F-19; аргумент «A1 сохраняет чистый IP» фактами не подтверждён и снимается правкой REQ-013, сам выбор C/A1 из-за этого не рассыпается.

6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
   WHY=Письмо кодера ограничено `server.py` и двумя тестовыми модулями. Запрет на `muse-bridge`, Google route, общие конфиги opencode/georouter, `opencode.db`, lockfiles, `analysis/**` и `~/.dsh` в VER соблюдён. CD-001 и CD-002 — это поведение, которое уже требуют REQ-004 и REQ-006..016. Флаг по умолчанию выключен, новых зависимостей нет, worktree продукта не менялся (materialized_targets=0, отпечаток в квитанции ARCH_GATE). Чистая комната не монтирует дом владельца; живые H0..H9 вынесены за rollout.

SUB КОРРЕКТНОСТЬ/логика: FAIL — architecture-packet.json#AD-001 fallback_barrier + operational_profile.session_setup_budget_s=0.2 против F-19 233 мс
SUB КОРРЕКТНОСТЬ/граничные условия: FAIL — architecture-packet.json#R-BULK-I1 53.7≤54; запас 0.3 с съедается любым честным session budget
SUB КОРРЕКТНОСТЬ/обработка ошибок: FAIL — architecture-packet.json#AD-001: 403 и таймаут после старта prompt POST лишают run fallback
SUB ПОЛНОТА/покрытие AC: FAIL — architecture-packet.json#REQ-013 statement «чистых IP» vs AC-018 и F-15 loopback мимо прокси
SUB ПОЛНОТА/пропущенные ветки: FAIL — architecture-packet.json#AD-001 spawn без владельца порта; event_contract без путей полей F-22
SUB РИСКИ/безопасность: FAIL — architecture-packet.json#THREAT-001 и #RISK-001; EVD-050 deny→Zen 403, fail-closed
SUB РИСКИ/данные: PASS — architecture-packet.json#BND-003: status не входит в prompt/usage; overflow явный; маскирование в THREAT-003
SUB РИСКИ/прод: FAIL — architecture-packet.json#memory_closure_check 192 МиБ vs F-20 439 МиБ; C-MULT-I1 share=10 при неизвестном sqlite
SUB РЕАЛИЗУЕМОСТЬ: FAIL — поднятие 0.2 с ломает R-BULK-I1; FakeServe не отличается от адаптера без замороженного фикстура
SUB АЛЬТЕРНАТИВЫ: PASS — architecture-packet.json#AD-001 alternatives A2/B/L и AD-002..004, у каждого ≥2 отвергнутых варианта
SUB СООТВЕТСТВИЕ КОНТЕКСТУ: PASS — scope.forbidden, CD-001/CD-002 по REQ-004 и REQ-006..016, fingerprint worktree без правок продукта

F1. Бюджет 0.2 с и запрет fallback после старта prompt
locations: architecture-packet.json#AD-001, architecture-packet.json#R-BULK-I1, architecture-packet.json#high_load_envelope
правило: R-BULK-I1 (`T_crit_aux` по всем попыткам ≤ 0.30×SLA); REQ-001
evidence: «create+event-subscription+prompt-send<=.2s»; «53.7s<=.30×180=54s»; «Начиная с попытки отправки prompt … silent fallback запрещён». F-19: execution.started 233 мс при ready около 109 мс.
ожидаемое исправление: create+subscribe ≥2.0 с; prompt POST по остатку first-event; run fallback только до заголовков ответа POST; R-BULK-I1 пересчитан и записан.
критерий проверки: VER-005 FakeClock, медленный create без заголовков POST → один run, Popen≤3; с заголовками POST → run нет; статическая сумма ≤54 либо явный FAIL гейта.
priority: blocking

F2. deny как базовая политика при fail-closed 403
locations: architecture-packet.json#AD-001, architecture-packet.json#RISK-001, architecture-packet.json#EVD-050
правило: REQ-012; THREAT-002
evidence: «Основная безопасная конфигурация — scoped … permission={\"*\":\"deny\"}»; «HTTP 401/403 … fail-closed, никакого ослабления policy через run»; EVD-050: deny может вызвать Zen 403.
ожидаемое исправление: по умолчанию ask и немедленный reject; deny только после H6; смена политики только до принятия prompt.
критерий проверки: VER-005, фикстура 403 на deny не открывает run после принятого prompt и не делает allow; до prompt допускается один переход на ask-reject.
priority: blocking

F3. Нет протокола владения ephemeral port
locations: architecture-packet.json#AD-001, architecture-packet.json#THREAT-001
правило: THREAT-001; отсутствие границы доверия на loopback
evidence: «--port, ephemeral»; «если API не даёт port=0 … reserve-bind(0), release, spawn с ограниченным retry race».
ожидаемое исправление: порт выбирает родитель через bind 0 / getsockname; spawn с явным портом; Basic и prompt только после проверки PGID слушателя.
критерий проверки: VER-005, чужой PID на том же порту → ноль байт пароля и промпта на его сокете, попытка завершается ошибкой внутри ready-бюджета.
priority: blocking

F4. Схема событий serve не заморожена
locations: architecture-packet.json#AD-001
правило: REQ-001, REQ-010, REQ-014; проверяемость VER-005
evidence: «Конкретные field paths подтверждает Coder по v2 schema в FakeServe contract test». F-19/F-22 фиксируют имена событий и эндпоинты, не пути полей.
ожидаемое исправление: в packet вложен минимальный JSON v2.1.2 для delta, tokens, tool lifecycle и execution failed.
критерий проверки: VER-005 падает, если адаптер или FakeServe расходится с фикстуром на любом из этих пяти конвертов.
priority: blocking

F5. REQ-013 невыполним в запрещённом периметре
locations: architecture-packet.json#REQ-013, architecture-packet.json#AD-001, architecture-packet.json#RISK-002
правило: REQ-013 MUST; Forbidden Scope (конфиг georouter не трогать); F-15, F-27
evidence: statement «Ротация чистых IP на каждый новый запуск»; AC-018 проверяет только `_next_standalone_proxy`. F-15: loopback мимо прокси. F-27: baseURL `127.0.0.1:10830`.
ожидаемое исправление: statement REQ-013 совпадает с AC-018; drivers AD-001 больше не считают чистый IP доказанным свойством A1.
критерий проверки: в пакете нет утверждения, что env serve меняет IP Zen; AC-018 остаётся проверкой последовательности записей пула.
priority: blocking

F6. Конверт нагрузки проходит за счёт недоказанных констант
locations: architecture-packet.json#high_load_envelope, architecture-packet.json#C-MULT-I1, architecture-packet.json#RISK-003
правило: HL-ENV-01 memory closure; C-MULT-I1; что ломается при 6 параллельных запросах
evidence: «6×192MiB=1152MiB»; F-20: долгий serve RSS 439 МиБ; «opencode_local_db=10 — design logical-child share … НЕ доказанный sqlite pool»; F-28: db 2.27 ГБ.
ожидаемое исправление: enable запрещён, если измеренный RSS нарушает замыкание памяти; C-MULT-I1 для sqlite не PASS до H3 без `database is locked` вне бюджета ретраев.
критерий проверки: rollout-гейт H3 с формулой памяти и проверкой lock; при нарушении флаг serve остаётся выключенным, слоты деплоя 6/12 не завышаются.
priority: blocking

ОБЩИЙ ВЕРДИКТ: NEEDS WORK
