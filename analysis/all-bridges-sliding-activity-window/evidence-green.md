# Evidence Green — Контракт и варианты сквозного Sliding Activity Window (все мосты)

Шляпа: Зелёная (INV-03). Дата: 2026-11-02. Симптом: отсутствует (превентивная доработка).
Вход: `research-plan.md`, `evidence-white.md` [W-01..W-08], `evidence-black.md` [B-01..B-24].
Код сверен в рабочем дереве ветки `feature/bridge-resilience-patterns` (только чтение).

## 0. Опорные факты Зелёной шляпы (проверено в коде, дополняют W/B)

- GF-1 **Все мосты уже импортируют `core/`**: agy `bridges/agy-bridge/server.py:113–122` (`core.watchdog.AdaptiveTimeoutController`), zen `bridges/opencode-zen-bridge/server.py:288–291` (`core.tool_emulation`), claude-p `bridges/claude-p-bridge/server.py:61–65` (`core.stream_framing`, `core.tool_emulation`), muse `bridges/muse-bridge/server.py:64–70` (`core.turn_session_manager`). Значит, V2 не добавляет новую зависимость деплоя: `sys.path` до корня репо уже есть.
- GF-2 **В `core/` уже 4 параллельные реализации одной идеи**: `adapters/passthrough_adapter.py:642–726` (`_TimedSseReader`: `last_input`/`last_upstream`, `min(idle, safety)`), `core/watchdog.py:359–504` (`AdaptiveTimeoutController`: idle + `absolute_cap`, продление по CPU), `core/turn_session_manager.py:895–905` (своё чтение `BRIDGE_SAFETY_CAP_S`), `server.py:384–389` (`IDLE_TIMEOUT_S`/`SAFETY_CAP_S` хаба). Плюс пер-мостовые: agy `:6128–6163` (две ветки), zen `:1609–1654` и две копии first-token/stall (`:4895–4909`, `:8448–8464`), claude-p — ничего (F-1).
- GF-3 **Цепочка env cap уже унифицирована в 3 местах** одной формулой `BRIDGE_SAFETY_CAP_S` → `DROID_DSH_BRIDGE_SAFETY_CAP_S` → 3600 (`core/watchdog.py:384–390`, `core/turn_session_manager.py:900–903`, `server.py:387–389`); `BRIDGE_IDLE_TIMEOUT_S` читает только passthrough (`adapters/passthrough_adapter.py:224–226`, дефолт 300).
- GF-4 **Ловушка именования в agy**: `AGY_BRIDGE_IDLE_TIMEOUT_S` сейчас означает *расширенное* окно `ext_idle_timeout_s` (1800 с, `bridges/agy-bridge/server.py:334–342`), а базовое idle (300 с) — `AGY_BRIDGE_BASE_IDLE_TIMEOUT_S`. Переиспользовать имя под новую семантику нельзя (B-04).
- GF-5 **Поправка к B-18 (очереди)**: неограниченная очередь producer→consumer есть только в agy (`self.q = queue.Queue()`, `bridges/agy-bridge/server.py:5207`). В claude-p очередь уже ограничена (`queue.Queue(maxsize=QUEUE_MAXSIZE)`, `:400`; `CLAUDE_P_BRIDGE_QUEUE_MAXSIZE=1000`, `:182`; `put(..., timeout=POLL_INTERVAL_S)`, `:432`), в zen — `STDOUT_QUEUE_MAX` (`:1578–1580`) и `maxsize=4096` (`:4751`), в passthrough — `read_queue_max_entries=1` (`:186`, `:660–662`). Риск B-18 «блокирующий `write` не даёт проверить дедлайн» остаётся в силе для всех.
- GF-6 **Поправка к B-20 (claude-p)**: `_client_gone(self.connection)` проверяется в начале **каждой** итерации цикла, включая ветку с данными (`bridges/claude-p-bridge/server.py:600–601`), а не только между событиями. Пробел — в том, что сама итерация может стоять в блокирующем `write` (B-18).
- GF-7 muse-bridge имеет свою пару `MUSE_BRIDGE_TIMEOUT_S=3600` / `MUSE_BRIDGE_IDLE_TIMEOUT_S=300` (`bridges/muse-bridge/server.py:98–99`) и ходит через `core.turn_session_manager` → при V2 подтягивается автоматически через ядро.

## 1. Контрактные факты [G-NN]

### 1.1 Полезный чанк (useful chunk)

- [G-01] **Полезный чанк** — нормализованная дельта ответа (после `StreamNormalizer` / `_ContentArbiter`, до записи в сокет), у которой выполнено хотя бы одно:
  - `content` — непустая строка, не состоящая только из пробельных символов (`s and not s.isspace()`);
  - `reasoning_content` — то же правило;
  - `tool_calls` — непустой список, где хотя бы у одного элемента непусты `id`, `function.name` или `function.arguments` (дельта аргументов считается полезной даже без имени — B-13).
- [G-02] **Не являются полезными** (не сдвигают дедлайн тишины): собственные keepalive моста (`: keepalive\n\n`, claude-p `KEEPALIVE_S=15`, agy `keepalive_s=15`, passthrough `heartbeat_interval_s=12`); SSE-комментарии апстрима (строки на `:`); `server.heartbeat` zen (`:2425`); дельты только с `role`, пустым/whitespace-текстом или `finish_reason` без payload; служебные статусы/префиксы оркестрации, отброшенные арбитром как повтор (`content-divergence`, инвариант `_scan`); сырые байты/строки stdout до нормализации (закрывает B-05 и F-3). CPU-активность процесса (`metrics.has_progress`, `core/watchdog.py:476–491`) — тоже не полезный чанк: только ограниченная grace (B-07, см. G-07).
- [G-03] Классификация полезности — **одна чистая функция в `core/`** (`is_useful_delta(delta) -> bool`), без I/O и замков; адаптеры её не переопределяют. Терминальные события (`done`/`result` с usage) не продлевают окно, но **всегда дочитываются** до закрытия (B-10).

### 1.2 Два таймера и семантика окна

- [G-04] **Idle (скользящий)**: `idle_deadline = last_useful_ts + idle_timeout_s`; каждый полезный чанк делает `last_useful_ts = now` (инвариант AGENTS.md L2 «Sliding Activity Window»). До первого полезного чанка опорная точка — `started_at`.
- [G-05] **Safety cap (абсолютный)**: `cap_deadline = started_at + safety_cap_s`, не сдвигается ничем. Обязателен и включён во всех мостах (B-06). Валидация: `idle_timeout_s = min(idle_timeout_s, safety_cap_s)` (обобщение agy `:274`, F-7).
- [G-06] **Ожидание**: `remaining = min(idle_deadline, cap_deadline, next_keepalive) - now`, ожидание в очереди — не дольше `min(remaining, poll_interval_s)` (паттерн `_TimedSseReader.readline`, `passthrough_adapter.py:693–713`). Проверка дедлайнов — с частотой поллинга, а не на каждую строку (B-24).
- [G-07] **CPU/IO-grace** (`AdaptiveTimeoutController`) — отдельный, третий контур: после истечения idle при `is_waiting_io()` даёт отсрочку не более `BRIDGE_IO_WAIT_CAP_S` (900 с, `core/watchdog.py:392–394`) и **не переписывает** `last_useful_ts` (`has_io_grace`, `:495–504`). Продление `last_activity_ts` по `cpu_delta` в `check()` (`:476–483`) при V2 переводится в сигнал «процесс жив», а не в сдвиг idle полезного стрима (B-07).
- [G-08] **First-token** остаётся статическим (сдвигать нечего), но «первым событием» считается любой полезный чанк из G-01, включая `reasoning_content` и `tool_calls` (W-06, B-13). Это снимает обрыв deep-reasoning на 120 с без расширения лимита.
- [G-09] **Очередь admission** (`QUEUE_TIMEOUT_S=900`, claude-p `:179`, agy `queue_timeout_s`) — строго абсолютная, активностью соседей не продлевается (B-21; отклоняем предложение W-05).

### 1.3 Единые env-переменные

- [G-10] `BRIDGE_IDLE_TIMEOUT_S` — дефолт **300 с**; `BRIDGE_SAFETY_CAP_S` — дефолт **3600 с**. Нечисловое/≤0 → дефолт (как `_positive_float`, `passthrough_adapter.py`, и `positive_env`, `core/watchdog.py:39`).
- [G-11] Цепочка приоритета — одна и та же функция ядра для всех: **пер-мостовая → общая → legacy → дефолт**:
  - idle: `<BRIDGE>_IDLE_TIMEOUT_S` (claude-p: новое `CLAUDE_P_BRIDGE_IDLE_TIMEOUT_S`; zen: `OPENCODE_ZEN_BRIDGE_STALL_TIMEOUT_S`; agy: `AGY_BRIDGE_BASE_IDLE_TIMEOUT_S`, **не** `AGY_BRIDGE_IDLE_TIMEOUT_S` — GF-4; muse: `MUSE_BRIDGE_IDLE_TIMEOUT_S`) → `BRIDGE_IDLE_TIMEOUT_S` → 300;
  - cap: `<BRIDGE>_SAFETY_CAP_S` → `BRIDGE_SAFETY_CAP_S` → `DROID_DSH_BRIDGE_SAFETY_CAP_S` → 3600 (сохраняет GF-3).
  Эффективные значения и источник (имя env) — в `/health` каждого моста и в лог старта (B-04).
- [G-12] Прочие параметры окна — тоже env с дефолтами, без констант в коде (принцип 4 AGENTS.md): `BRIDGE_SSE_HEARTBEAT_INTERVAL_S` (12, уже есть), `BRIDGE_WINDOW_POLL_INTERVAL_S` (дефолт = текущий поллинг моста), `BRIDGE_IO_WAIT_CAP_S` (900, уже есть), `BRIDGE_STREAM_QUEUE_MAX` (bounded-очередь, G-17), `BRIDGE_LIVE_WRITE_TIMEOUT_S` (таймаут записи живого куска, G-18).
- [G-13] **Фичефлаг** (канон: смена runtime-поведения только под флагом GigaRC, дефолт `false`, B-16): `BRIDGE_SLIDING_WINDOW_ENABLED`. `false` → прежние таймауты каждого моста бит-в-бит; `true` → окно ядра. Флаг читается **один раз на ход** (B-23), а не в каждой итерации, как сейчас `_new_flag(...)` в agy `:6130`.

### 1.4 Причины завершения и терминальный кадр

- [G-14] Ядро возвращает каноническую причину: `first_token_timeout` | `idle_timeout` | `absolute_cap` | `client_gone`. Адаптер моста — тонкий транслятор — может отобразить её в исторически публикуемую строку (zen: `idle_timeout` → `stall_timeout`; agy без флага: `absolute_cap` → `timeout`), чтобы `error.type` и `FALLBACK_DECISION_TABLE` zen (`:2089–2097`) не сломались (B-01). Новые строки только добавляются.
- [G-15] Любой выход по G-14 идёт **одним путём закрытия**: дочитать буфер `get_nowait` до пустоты (B-10) → закрыть незакрытый `tool_calls` валидно или явной ошибкой → финальный chunk с `finish_reason` → `data: [DONE]` (`core/stream_framing.format_stream_error_sse`, коммит `20e8cb5`; B-02) → kill группы тем же путём, что и `client_gone` (B-08) → освобождение слота **только** в существующем `finally` (B-19).
- [G-16] После `delivered=True` ретрай по idle запрещён (B-11); до первого полезного чанка ретрай разрешён в рамках существующего Retry Budget.

## 2. Варианты изменения

### V1 — локальный (точечные правки в каждом мосту)

Суть: в каждом из `agy-bridge`, `opencode-zen-bridge` (две копии), `claude-p-bridge`, `muse-bridge` дописать своё скользящее окно по образцу `_TimedSseReader`.

- claude-p: в цикл `:600–631` добавить `last_useful_ts`, проверку idle/cap на ветке `queue.Empty` и после данных, `return state("idle_timeout"|"absolute_cap", …)`.
- zen: в `_StdoutReader.lines` (`:1609–1654`) сбрасывать `last_activity` не по любой строке, а по полезному чанку; убрать отброс строки после дедлайна (`:1648–1650`); синхронно поправить first-token/stall в `:4895–4909` и `:8448–8464`.
- agy: убрать ветку настенного `TIMEOUT_S` (`:6128–6163`) в пользу sliding, ограничить `self.q` (`:5207`).
- muse: заменить `TIMEOUT_S` на cap + idle локально.

Плюсы: малый радиус на одну правку, мосты деплоятся независимо, нет изменений в `core/`.
Минусы: 5 реализаций одной логики (+ 4 уже существующие в ядре, GF-2) → расхождение семантики «полезного чанка» и причин (B-01, B-05), env-цепочки разные (B-04), гонки и замки решаются каждым по-своему (B-10, B-12), тесты с фейковыми часами пишутся ×5 (B-15). Нарушает принцип 5 AGENTS.md («запрещено переносить общую логику на уровень конкретного агента»): решение агент-агностично, исключение не доказано.

### V2 — системный (core-level, рекомендуемый)

Суть: один примитив в ядре, адаптеры только скармливают ему события и исполняют вердикт.

Новый модуль `core/sliding_window.py` (или раздел `core/watchdog.py`, если Совет решит не плодить модули; рабочее имя из research-plan — `core/streaming_watchdog.py`):

```
WindowLimits.from_env(prefix: str, environ=None) -> WindowLimits      # G-10..G-12, клампинг G-05
is_useful_delta(delta: Mapping) -> bool                                # G-01..G-03
class ActivityWindow:                                                  # без замков на горячем пути
    __init__(limits, clock=time.monotonic)                             # инъекция часов (B-15)
    touch_useful(now=None) -> None      # одна запись float; first_useful_ts при первом вызове
    touch_input(now=None) -> None       # только каденс keepalive (last_input)
    verdict(now=None) -> Verdict        # (reason|None, wait_s, keepalive_due) — G-04..G-08, G-14
    snapshot() -> WindowSnapshot        # неизменяемый срез для /health и логов (B-12)
```

Точки подключения (каждая — тонкая):

| Потребитель | Что меняется | Что остаётся |
|---|---|---|
| `adapters/passthrough_adapter.py` `_TimedSseReader` | `readline` использует `ActivityWindow.verdict`; `last_input`/`last_upstream` переезжают в окно | bounded-очередь `maxsize=1`, поток-ридер, `relay_sse` |
| `core/watchdog.py` `AdaptiveTimeoutController` | idle/cap делегируются окну; CPU/descendants → только grace (G-07) | `ProcessWatchdog`, `child_exited`, `io_grace` |
| `core/turn_session_manager.py` (и через него muse) | читает лимиты через `WindowLimits.from_env` | TurnContext, буферизация ходов |
| `bridges/agy-bridge` | `note_producer_activity` → `touch_useful` по нормализованной дельте; две ветки `:6128–6163` → одна; `self.q` → bounded (G-17) | killpg `:2808`, `_cid_release`, Retry Budget |
| `bridges/opencode-zen-bridge` | `lines()` и обе копии first-token/stall → одно окно; маппинг `idle_timeout→stall_timeout` (G-14) | `_StdoutReader`, admission, fallback-таблица |
| `bridges/claude-p-bridge` | цикл `:600–631` получает `verdict()` на ветке Empty и после данных; выход через G-15 | `_slots`/`finally :685`, `_kill_group :340–344`, keepalive |

Плюсы: одна семантика полезного чанка и причин для всех (B-01, B-05), одна env-цепочка (B-04), снимок под одной точкой (B-12), один набор L1 на фейковых часах (B-15), cap обязателен конструктивно (B-06), консолидация 4 существующих реализаций ядра (GF-2). Прямо следует принципам 3 и 5 AGENTS.md.
Минусы: правка ядра задевает все мосты сразу → нужен фичефлаг G-13 и поэтапная раскатка; больше тестов на регресс в одной поставке (B-14); `AdaptiveTimeoutController` меняет семантику продления по CPU — заметно для DSH-пути.

Порядок раскатки V2 (каждый шаг — отдельный зелёный полный `uv run pytest -q`):
1. `core/sliding_window.py` + L1 на фейковых часах + `timeit`-оракул (NFR §3). Никто его ещё не использует.
2. passthrough переводится на окно (эталон W-08; 78 тестов стриминга — регресс-оракул эквивалентности).
3. claude-p (самый большой выигрыш: сейчас ни idle, ни cap — B-06) под `BRIDGE_SLIDING_WINDOW_ENABLED`.
4. zen, agy, затем `AdaptiveTimeoutController`/muse.

## 3. NFR-бюджет изменения

Источник: research-plan — `RPS_peak=50`, `T_budget ≤ 1 ms` overhead на запрос, `S_frame_max = 32 MB`.

### 3.1 Накладные расходы на чанк: < 1 µs, без блокировок на горячем пути

- [G-NFR-01] Горячий путь на один чанк = `is_useful_delta` (2–3 проверки истинности строк/списка) + `clock()` + одна запись атрибута float. Оценка CPython: `time.monotonic()` ~30–80 нс (B-22), атрибутная запись ~20–40 нс, проверки ~50–150 нс → **~0.1–0.3 µs**, порог приёмки **< 1 µs** на чанк для всей логики окна.
- [G-NFR-02] **Без `threading.Lock` на чанк**: запись `last_useful_ts` — единичное присваивание float (атомарно под GIL); составное состояние (reason, kind, счётчики) пишет только поток-владелец окна (consumer), а читатели берут `snapshot()` — замок, если нужен, только в `snapshot()` (вне горячего пути). Это снимает contention `_activity_lock` agy `:5297` (B-23).
- [G-NFR-03] `verdict()` и чтение флагов/конфига — не на каждый чанк, а с частотой поллинга (`BRIDGE_WINDOW_POLL_INTERVAL_S`) и один раз на ход соответственно (B-23, B-24).
- [G-NFR-04] Бюджет на запрос: 50 RPS × ~100 чанков/с × 0.3 µs ≈ 1.5 ms CPU/с на весь процесс — на один запрос ≪ 1 ms. Оракул L1: `timeit` 10⁶ вызовов `touch_useful`+`is_useful_delta` < 1 с (т.е. < 1 µs/вызов) на CI-раннере; тест падает при превышении.

### 3.2 Защита памяти

- [G-17] **Bounded queue везде**: очередь producer→consumer ограничена `BRIDGE_STREAM_QUEUE_MAX` (пер-мостовые `CLAUDE_P_BRIDGE_QUEUE_MAXSIZE`, `STDOUT_QUEUE_MAX` zen — первыми в цепочке). Единственная неограниченная сейчас — agy `:5207` (GF-5) — становится bounded. Политика при `Full`: producer ждёт `put(timeout=poll)` (backpressure, как claude-p `:432`), а при длительном `Full` дольше idle — окно выдаёт `idle_timeout` (consumer не читает → клиент не получает полезных чанков), путь G-15. Размер буфера текста/reasoning — тоже из env (принцип 4).
- [G-18] **Запись в сокет не блокирует проверку дедлайна** (B-18): запись живого куска ограничена `BRIDGE_LIVE_WRITE_TIMEOUT_S ≤ idle_timeout_s` (аналог RW-009 в `server.py` и `LIVE_WRITE_TIMEOUT_S` muse `:184`); таймаут записи трактуется как `client_gone`.
- [G-19] **Отсечка `client_gone`**: проверяется на каждой итерации, включая ветку с данными (как claude-p `:600–601`, GF-6), и по результату каждой записи/keepalive. При `client_gone`: стоп чтения → дренаж очереди без отправки → kill группы → освобождение слота в `finally` (G-15). Оракул B-19: после 100 ходов (idle / cap / client_gone) число свободных слотов == `MAX_CONCURRENT`, RSS процесса не растёт монотонно.
- [G-20] Фрейм до 32 MB (`S_frame_max`) не копируется окном: `is_useful_delta` проверяет только истинность полей, без конкатенации и `len` больших строк сверх O(1).

### 3.3 Ресурсный конверт (B-17) — что даёт V2, что остаётся открытым

- Мёртвые стримы освобождают слот быстрее: claude-p ∞ → 300 с; agy без флага 1800 с → 300 с.
- Живые длинные стримы держат слот дольше: до cap 3600 с вместо 1800 (agy) / 120 (zen first-token при deep reasoning).
- По закону Литтла `L = λ · W`: требуемые слоты = RPS моста × p95 длительности хода. Без p95 по мостам дефолтный cap нельзя считать доказанным — см. «Не проверено».

## 4. competing-options — V1 vs V2 против рисков Чёрной шляпы

Легенда: ✅ закрывается вариантом конструктивно · ⚠️ закрывается только дисциплиной/тестом в каждом мосту · ❌ вариант усиливает риск · ➖ нейтрально (нужна отдельная мера в любом варианте).

| Риск | Уровень | V1 (локальный) | V2 (core-level) | Мера в V2 |
|---|---|---|---|---|
| B-01 смена `finish_reason`/`error.type` | MAJOR | ⚠️ ×5 разных строк | ✅ | канон-причины + маппинг в адаптере (G-14) |
| B-02 терминальный кадр/`[DONE]` | MAJOR | ⚠️ новый выход в каждом мосту | ✅ | единый путь закрытия (G-15) |
| B-03 изоляция `<Think>` | MINOR | ⚠️ | ✅ | окно не пишет в `content`, keepalive — SSE-комментарий |
| B-04 имена env / приоритеты | MINOR | ❌ 5 цепочек, ловушка GF-4 | ✅ | `WindowLimits.from_env` (G-11) |
| B-05 продление паразитной активностью | **BLOCKER** | ⚠️ zen уже нарушает (F-3) | ✅ | `is_useful_delta` после нормализации (G-01..G-03) |
| B-06 обязательный safety cap | **BLOCKER** | ⚠️ легко забыть (claude-p) | ✅ | cap — обязательный параметр окна, клампинг (G-05) |
| B-07 ложная CPU-активность | MAJOR | ➖ | ✅ | CPU → только grace (G-07) |
| B-08 зомби на новом выходе | MAJOR | ⚠️ | ⚠️ | kill — в адаптере, но единый путь G-15 + оракул killpg |
| B-09 slow-drip | MINOR | ➖ | ➖ | принять риск; `BRIDGE_MIN_RATE` выкл. по умолчанию — опция |
| B-10 потеря буферизованных чанков | **BLOCKER** | ⚠️ ×5 | ✅ | дренаж `get_nowait` до закрытия (G-15) |
| B-11 дубли при retry | MAJOR | ⚠️ | ⚠️ | запрет ретрая после `delivered` (G-16); `_scan` без ослабления |
| B-12 несинхронное чтение состояния | MAJOR | ❌ каждый со своим замком | ✅ | один владелец записи + `snapshot()` (G-NFR-02) |
| B-13 first-token без reasoning/tool | MINOR | ⚠️ | ✅ | first-token по любому полезному чанку (G-08) |
| B-14 тесты с жёсткими таймаутами | MAJOR | ❌ правки разнесены, ассерты разные | ⚠️ | одна поставка правок, ассерт на причину; флаг G-13 сохраняет старые ожидания при `false` |
| B-15 тайминг-флаки | MAJOR | ❌ часы инжектируются ×5 | ✅ | `clock=` в окне, L1 без `sleep` |
| B-16 дефолты без фичефлага | MINOR | ⚠️ | ✅ | `BRIDGE_SLIDING_WINDOW_ENABLED=false` (G-13) |
| B-17 конверт слотов | **BLOCKER** | ➖ | ➖ | нужен замер p95 (не закрыт ни одним вариантом) |
| B-18 медленный клиент блокирует проверку | **BLOCKER** | ⚠️ | ⚠️ | bounded-очередь + write-timeout ≤ idle (G-17, G-18) — общая утилита, но запись в сокете у каждого моста своя |
| B-19 утечка/двойной release слота | MAJOR | ⚠️ | ⚠️ | release только в существующем `finally`; оракул 100 ходов (G-19) |
| B-20 keepalive vs proxy idle | MAJOR | ⚠️ | ✅ | `keepalive_due` в `verdict()`, `client_gone` на каждой итерации (G-19) |
| B-21 admission не продлевается | MINOR | ⚠️ | ✅ | окно применяется только к фазе стрима (G-09) |
| B-22 стоимость `monotonic()` | MINOR | ➖ | ✅ | `timeit`-оракул < 1 µs (G-NFR-04) |
| B-23 замок/флаги на горячем пути | MAJOR | ❌ agy `:5297`, `:6130` остаются | ✅ | без замков на чанк, флаг раз на ход (G-NFR-02/03) |
| B-24 `on_idle` на каждую строку | MINOR | ⚠️ | ✅ | `verdict()` с частотой поллинга (G-NFR-03) |

Итог по счёту: V2 конструктивно закрывает 17 из 24 рисков (из блокеров — B-05, B-06, B-10), ещё 5 (B-08, B-11, B-14, B-18, B-19) требуют дисциплины в адаптере при любом варианте, 2 (B-09, B-17) архитектурой не закрываются. V1 конструктивно не закрывает ни одного и усиливает 5 (B-04, B-12, B-14, B-15, B-23).

## 5. Рекомендация Зелёной шляпы

**V2** с поэтапной раскаткой (§2) под `BRIDGE_SLIDING_WINDOW_ENABLED=false`. Условия входа в реализацию: (1) оракулы B-02, B-08, B-10, B-19 и `timeit` из G-NFR-04 — в L1/L2 до кода (red → green); (2) расчёт конверта B-17 по p95 до включения флага на живом трафике; (3) таблица маппинга причин G-14 утверждена до изменения `error.type`.

## Не проверено

- Реальные `timeit`-цифры G-NFR-01 на этой машине/CI — оценки по порядку величины, замер не делал.
- p95/p50 длительности ходов по мостам (нужны для B-17, §3.3).
- Наличие и значение write-timeout живой записи в agy, zen, claude-p (G-18) — проверены только `server.py` (RW-009) и muse (`:184`).
- Внутренности muse-bridge за пределами `:64–99`, `:165–184` — предположение «подтягивается через `turn_session_manager`» не прослежено до цикла чтения.
- Механизм чтения фичефлага GigaRC в мостах вне agy (`_new_flag`) — не сверен.
