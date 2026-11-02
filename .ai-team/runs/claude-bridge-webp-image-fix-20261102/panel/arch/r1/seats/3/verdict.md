PANEL-NONCE: e3bf0ebdb3692fca
ARTIFACT-SHA256: a63c0fc62f291f23726fcd23dd621d2a9bb658e2fc95dccc5ded54b1367e1707

Прочитан общий канон `~/Мой диск/Context/AGENTS.md` целиком (до `<!-- КАНОН-КОНЕЦ -->`) и проектный файл правил `/Users/aazhiry1/work/src/cli-agent-bridge/AGENTS.md`.

## Архитектурная оценка (Роль: ВИЗИОНЕР, Раунд R1)

Архитектурный пакет `pol-architecture-packet/1` выдержан в соответствии с главным принципом проекта (`AGENTS.md` §1, §3, §5): нормализация MIME-типов и строгая сигнатурная проверка контейнеров `WebP`/`GIF` вносятся в универсальное агент-агностическое ядро (`core/tool_emulation.py`), устраняя рассинхронизацию с HTTP-фасадом, а классификация ошибок квоты апстрима локализована в транспортном слое `opencode-zen-bridge` с сохранением контракта `allow_quota_rotation()` и карантина прокси. Матрица верификации `VER-001`..`VER-007` полностью покрывает как позитивные сценарии, так и fail-closed отсев невалидных RIFF-контейнеров (`RIFF....WAVE`).

Ниже приведены неблокирующие архитектурные наблюдения для долгосрочной системной гармонии.

---

### F-001 NON_BLOCKING — Дублирование таблиц сигнатур и логики MIME-сниффинга между `server.py` и `core/tool_emulation.py`

- **Доказательство:** [`core/tool_emulation.py:1366-1385`](file:///Users/aazhiry1/work/src/cli-agent-bridge/core/tool_emulation.py#L1366-L1385) и [`server.py:460-475`](file:///Users/aazhiry1/work/src/cli-agent-bridge/server.py#L460-L475), [`server.py:1492-1499`](file:///Users/aazhiry1/work/src/cli-agent-bridge/server.py#L1492-L1499).
- **Суть:** В фасаде `server.py:460-475` уже определены `IMAGE_SIGNATURES`, `KNOWN_IMAGE_MIMES`, `IMAGE_EXTENSIONS` и функция `_sniff_image(data: bytes)` (`server.py:1492-1499`), тогда как в `core/tool_emulation.py:1366-1385` поддерживается параллельный реестр `_IMAGE_FORMATS` и `_sniff_image_mime(data: bytes)`. Именно это дублирование стало корневой причиной инцидента (в `server.py` `image/webp` и `image/gif` присутствовали, а в `core/tool_emulation.py` — нет; кроме того, в `server.py:1495` проверка GIF использует менее строгий префикс `b"GIF8"`, тогда как в пакете для `core/tool_emulation.py` вводится строгая проверка `GIF87a`/`GIF89a`).
- **Рекомендация на перспективу:** Вынести канонический реестр форматов и функцию `_sniff_image_mime` в `core/tool_emulation.py` как единственный источник истины (Single Source of Truth) и импортировать их в `server.py`, чтобы исключить повторный дрейф поддерживаемых форматов между фасадом и ядром.

---

### F-002 NON_BLOCKING — Неиспользуемое поле сигнатуры `magic` в кортеже `_IMAGE_FORMATS` после перехода на составные сигнатуры

- **Доказательство:** [`core/tool_emulation.py:1366-1385`](file:///Users/aazhiry1/work/src/cli-agent-bridge/core/tool_emulation.py#L1366-L1385) и [`core/tool_emulation.py:1430`](file:///Users/aazhiry1/work/src/cli-agent-bridge/core/tool_emulation.py#L1430).
- **Суть:** В предлагаемом разделе 2.1 пакета таблица `_IMAGE_FORMATS` хранит тройки `(mime, magic, ext)`, где для WebP указано `("image/webp", b"RIFF", "webp")`, а для GIF — `("image/gif", b"GIF8", "gif")`. Поскольку `b"RIFF"` не является достаточной сигнатурой WebP (требуется проверка `data[8:12] == b"WEBP"`), функция `_sniff_image_mime` больше не итерируется по полю `magic` из `_IMAGE_FORMATS`, а в `extract_data_url_images` (`core/tool_emulation.py:1430`) второе поле кортежа игнорируется (`{mime: ext for mime, _, ext in _IMAGE_FORMATS}`).
- **Рекомендация на перспективу:** Либо хранить в `_IMAGE_FORMATS` декларативное правило/предикат сопоставления сигнатуры (чтобы `_sniff_image_mime` оставалась таблично-управляемой), либо при следующем рефакторинге упростить структуру до маппинга `mime -> ext`, чтобы поле `b"RIFF"` не вводило в заблуждение при чтении кода.

---

### F-003 NON_BLOCKING — Избыточность частных подстрок квоты при наличии общего маркера `"quota exhausted"` в `_is_free_quota_error`

- **Доказательство:** [`bridges/opencode-zen-bridge/server.py:1741-1758`](file:///Users/aazhiry1/work/src/cli-agent-bridge/bridges/opencode-zen-bridge/server.py#L1741-L1758), места вызова в [`bridges/opencode-zen-bridge/server.py:7631`](file:///Users/aazhiry1/work/src/cli-agent-bridge/bridges/opencode-zen-bridge/server.py#L7631) и [`bridges/opencode-zen-bridge/server.py:9220`](file:///Users/aazhiry1/work/src/cli-agent-bridge/bridges/opencode-zen-bridge/server.py#L9220).
- **Суть:** В списке маркеров `_is_free_quota_error` одновременно добавляются `"quota exhausted"`, `"request quota exhausted"` и `"subscription quota exhausted"`. Поскольку проверка выполняется через оператор подстроки `marker in message`, маркер `"quota exhausted"` математически поглощает оба более длинных маркера. Функционально это полностью безопасно и наглядно документирует известные варианты ответов провайдера, но в долгосрочной перспективе (согласно `AGENTS.md` §4 о конфигурируемости) набор маркеров квоты целесообразно позволить расширять через конфигурацию/переменную окружения без необходимости правки кода при очередном переименовании текста ошибки апстримом.

VERDICT: ACCEPT
