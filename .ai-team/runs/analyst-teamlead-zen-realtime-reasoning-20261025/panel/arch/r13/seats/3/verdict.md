PANEL-NONCE: 53722cf794d916c9
ARTIFACT-SHA256: 15ea67e3215ceea9e84b9d79853677f4be86b959e87a21f24830d0c895f62657

AGREE F-001 rev=1 — проверил сам, измерение воспроизводится: `python3 -I` с импортом полного `bridges/opencode-zen-bridge/server.py` даёт ru_maxrss 26.86 MiB, голый stdlib-интерпретатор даёт 16.59 MiB. В `architecture-packet.json#AD-001` и `#VER-005` helper — это `python -I server.py --serve-helper`, то есть полный модуль. При этом во всех таблицах памяти остаётся `helper_estimate=12.0`. Реальная сумма: 156.8 (EVD-071) + 26.9 + 8.0 ≈ 191.7 MiB при `per_slot_ceiling=192`. Запаса нет даже в простое, а на 103 KB промпте и активном SSE слот гарантированно выше потолка. Гейт H3 прямо запрещает waiver. Значит, как написано, пакет не пройдёт собственный H3, и фичефлаг останется `false`. Priority остаётся blocking: исправление дешёвое (оценка helper ≥30 MiB и потолок слота около 210 MiB; 6·210+256=1516 ≤ 1638.4, либо ранний перехват `--serve-helper` до тяжёлых импортов) и должно быть внесено синхронно во все секции с памятью.

AGREE F-002 rev=1 — проверил по `server.py`: строка 52 `OPENCODE_BIN = os.environ.get("OPENCODE_BIN", …~/.opencode/bin/opencode)`, строка 54 `LOG_PATH` от `__file__`, строка 163 безусловный `reload_catalog()`, диспетчер `__main__` на строке 4020 (самый низ файла). Allowlist `serve_env_sanitization` не содержит `OPENCODE_BIN` и `OPENCODE_ZEN_BRIDGE_*`. Поэтому helper под очищенным `serve_env` пересчитывает `OPENCODE_BIN` в боевой путь и теряет подмену `server.OPENCODE_BIN` из тестов ([F-43]) и из FakeServe. Заодно он выполняет `reload_catalog()` и привязывает логи и состояние к дереву репозитория. Хвост argv в пакете записан как `...`, а скелет в EVD-077 разбирает только `args[:2]`. Это дыра в контракте (критерий 2) и в воспроизводимости VER-005 (критерий 3). Priority остаётся blocking. Fix: закрытый список позиционных аргументов helper с `opencode_bin`, lease-каталогом и идентичностью родителя; `--serve-helper <attempt_id> <port>` остаются первыми для reaper; в режиме helper не выполнять `reload_catalog()` и не создавать серверное состояние. Эти два пункта лучше решать вместе с F-001: перенос диспетчера в начало файла закрывает оба.

AGREE F-003 rev=1 — проверил: в `VER-004.command` write-mode `ruff format --range` идёт по `/tmp/zen-arch5-probe-format-*/server.py` без `--config`, а Ruff ищет конфиг от каталога файла вверх. В `ruff.toml` и `pyproject.toml` моста нет `line-length`, так что практический риск меньше, чем описан. Но привязка к конфигу пользователя или хоста остаётся. Priority остаётся non-blocking. Fix: `--config <root>/ruff.toml` на всех вызовах ruff и проверка идемпотентности.

AGREE F-004 rev=1 — проверил по шапке пакета: `cycle=5` и `role_plan=plans/architect-05.json`, но `scope.architect_write_allowlist` содержит `plans/architect-04*.json`. Дефект чисто метаданных, не продуктовый. Priority остаётся non-blocking.

1. КОРРЕКТНОСТЬ: VERDICT=FAIL
   WHY=Закрытие RW-001..RW-004 и FU-001..006 по `architecture-packet.json#rework_resolutions_a4` и дельте v4→v5 проверяемо. Но FU-004 (запуск helper как полного `server.py`) внёс два внутренних противоречия: потерю `OPENCODE_BIN` и побочные эффекты верхнего уровня (F-002), а также оценку памяти, опровергнутую измерением (F-001).
   СОВЕТЫ: ранний перехват `--serve-helper` до тяжёлых импортов и до `reload_catalog()`; закрытый argv с `opencode_bin`; пересчёт памяти helper на измеренном RSS.
2. ПОЛНОТА: VERDICT=FAIL
   WHY=Контракт `--serve-helper` неполон: хвост argv записан как `...` в `#AD-001`, `#VER-005`, `#THREAT-001`, а скелет EVD-077 разбирает лишь два аргумента (F-002). Покрытие REQ-001..020 и AC-001..026 полное.
   СОВЕТЫ: заменить `...` на замкнутую схему аргументов (opencode_bin, lease_dir, parent identity) единообразно во всех секциях.
3. РЕАЛИЗУЕМОСТЬ: VERDICT=FAIL
   WHY=Под очищенным `serve_env` clean-room FakeServe в VER-005 не получает подменённый бинарник (F-002). Слот ~191.7 MiB при потолке 192 MiB детерминированно проваливает H3 (F-001). Остальное (три целевых файла, нулевые новые зависимости, EVD-076/077 с exit 0) осуществимо.
   СОВЕТЫ: как в F-001 и F-002; в `VER-004.command` добавить явный `--config` (F-003).
4. РИСКИ: VERDICT=FAIL
   WHY=Главный риск при росте нагрузки: при 6 слотах каждая связка serve + полный helper + probe упирается в жёсткий потолок 192 MiB без waiver. Rollout встаёт на H3, прод остаётся на буферизующем `run` и RC-1 не решён (F-001). Безопасностный контур (proof listener, ask_reject, form-cancel, sanitization, `:memory:` DB, `_ServeHealth` отдельно от model breaker) закрыт корректно.
   СОВЕТЫ: измерить RSS связки helper+serve отдельным EVD и пересчитать потолок слота.
5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=Рассмотрены L, A2, B, `--port 0`, пустой XDG, общий SQLite и `serve --stdio` (EVD-078, [F-30]) с причинами отказа на фактах [F-15], [F-17]..[F-27]. Выбор C/A1 оставляет эволюцию: каноническая граница `(etype,payload)` позволяет позже заменить транспорт.
6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
   WHY=Внешний контракт :9883, Google-маршрут, `_run_env` и три целевых файла не затронуты. Фичефлаг соответствует канону: default=false, runtime JSON вне git, включение на H7 после H3 и H6. `CD-001` и `CD-002` прямо разрешены REQ-004..009 и REQ-016. Остаётся только F-004 (non-blocking, метаданные). Сверка seed для `r13`: `seed_hex=e04e257591334806861656fc56e5de2463f3b06d96444ef04837b37c146ce3f8`, SEED=`e04e2575`. Пересчёт `rank = SHA-256(seed_hex + '#' + slot_id)` по `select_round_seats.py#L235-L237` даёт порядок claude-sonnet-5-5-high, gemini-4-argon-high, grok-4.7-high, muse-wonder-full-1.0, gpt-6.1-sol-high. Он совпадает с `ranked_order` в манифесте.

ОБЩИЙ ВЕРДИКТ: NEEDS WORK
