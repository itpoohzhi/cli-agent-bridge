Ваша ролевая шляпа — РЕАЛИСТ. Сфокусируйтесь на реализуемости, простоте внедрения, минимальности диффа и эксплуатационных нюансах.
РАУНД: R1 (слепой, независимый)

Ты — независимый судья экспертной панели. Проверь пакет ниже заново,
не опираясь на чужие выводы: их в этом брифе нет.
Каждую находку оформи отдельным блоком вида:
### F-001 BLOCKER-SAFETY|BLOCKER-OPINION|NON_BLOCKING — суть одной строкой
с доказательством file:line. BLOCKER-SAFETY — только доказанный дефект
безопасности, утечка данных или сбой обязательных тестов.
Первыми двумя строками ответа повтори PANEL-NONCE и ARTIFACT-SHA256
из конца этого брифа. Последняя непустая строка ответа — строго
VERDICT: ACCEPT | PASS | NEEDS WORK | RED FLAG.

ПАКЕТ:
# Acceptance Package: WebP/GIF Support & Zen Quota Error Recovery

## 1. Task Envelope
- **Run ID**: claude-bridge-webp-image-fix-20261102
- **Goal**: Исправление ошибки `unsupported_image_type` при передаче WebP/GIF изображений (скриншоты macOS в DeepSeek Harness) и восстановление ротации прокси при ошибках квот в OpenCode Zen.
- **Criterion**: Приём 4 форматов изображений (PNG, JPEG, GIF, WebP) в `core/tool_emulation.py`, корректная маршрутизация квот в `bridges/opencode-zen-bridge/server.py`, 100% зелёные тесты L1/L2, вердикт ACCEPT Советом Тимлидов.
- **Architectural Reference**: ADR-0023, Architecture Packet r2 (`receipts/arch-panel-receipt.json`, exit 0).

## 2. Candidate Manifest
- **Modified Files**:
  - `core/tool_emulation.py`
  - `bridges/opencode-zen-bridge/server.py`
  - `bridges/claude-p-bridge/server.py`
  - `tests/test_claude_bridge.py`
  - `tests/test_opencode_zen_bridge.py`
- **Diff SHA256**: `0057ea7035fdc73e6d3f5d19dad85a21997f363301e30cae49d21e1759d1d178`

## 3. Git Diff
```diff
diff --git a/bridges/claude-p-bridge/server.py b/bridges/claude-p-bridge/server.py
index 4edc9b8..54d681f 100644
--- a/bridges/claude-p-bridge/server.py
+++ b/bridges/claude-p-bridge/server.py
@@ -20,7 +20,7 @@ AD-002: этот файл в репозитории — SSOT, локальных
 попадает в `content`, fallback на терминальный `result` исключён, ошибка
 потока — корректный `502 proxy_error`.
 
-Изображения (`image_url` data URI PNG/JPEG) мост материализует в изолированный
+Изображения (`image_url` data URI PNG/JPEG/GIF/WebP) мост материализует в изолированный
 сессионный каталог `/tmp/claude-img-<uuid>/` (0700, файлы 0600) и запускает
 Claude с `--allowedTools "Read(<каталог>/**)"`, `--restricted` и
 `--add-dir <каталог>` (AD-003, workspace-read);
diff --git a/bridges/opencode-zen-bridge/server.py b/bridges/opencode-zen-bridge/server.py
index 9c140eb..f43129f 100755
--- a/bridges/opencode-zen-bridge/server.py
+++ b/bridges/opencode-zen-bridge/server.py
@@ -1228,6 +1228,8 @@ def _is_transient_stream_error(ev: dict[str, Any]) -> bool:
     `ev` — сырое событие `{"type":"error","error":{…}}` или разобранный payload `{statusCode, message}`.
     400/401/403/404/422 — детерминированный отказ (False, без повтора, Fail-Closed). Нет статуса, 0, 408,
     429, >=500 либо маркер сетевого сбоя в сообщении — транзиентна (True).
+    Исключение: исчерпанная квота транзиентна при любом статусе (проверка ДО
+    fatal-статусов) — иначе прокси не уйдёт в карантин и ротации не будет.
     """
     containers: list[dict[str, Any]] = [ev]
     messages: list[str] = []
@@ -1252,6 +1254,12 @@ def _is_transient_stream_error(ev: dict[str, Any]) -> bool:
             value = container.get(key)
             if isinstance(value, str):
                 messages.append(value)
+    if (
+        _is_free_quota_error(ev)
+        or any(_is_free_quota_error(container) for container in containers)
+        or any(_is_free_quota_error(message) for message in messages)
+    ):
+        return True
     if status in _FATAL_STREAM_STATUSES:
         return False
     if status is None or status in (0, 408, 429) or status >= 500:
@@ -1754,6 +1762,9 @@ def _is_free_quota_error(err: object) -> bool:
             "free usage limit reached",
             "usage limit reached",
             "provider.free-limit",
+            "quota exhausted",
+            "request quota exhausted",
+            "subscription quota exhausted",
         )
     )
 
diff --git a/core/tool_emulation.py b/core/tool_emulation.py
index 13eebeb..479ecf2 100644
--- a/core/tool_emulation.py
+++ b/core/tool_emulation.py
@@ -1362,11 +1362,16 @@ _ORPHAN_SERVICE_TAGS = (
     "<arg_value>",
     "</arg_value>",
 )
-# (MIME, магические байты, расширение файла) — принимаемые форматы вложений.
+# (MIME, магический префикс, расширение файла) — принимаемые форматы вложений.
+# Для GIF/WebP префикс — только ориентир таблицы расширений: точную сигнатуру
+# (GIF87a/GIF89a; RIFF+WEBP в [8:12]) проверяет `_sniff_image_mime`.
 _IMAGE_FORMATS = (
     ("image/png", b"\x89PNG\r\n\x1a\n", "png"),
     ("image/jpeg", b"\xff\xd8\xff", "jpg"),
+    ("image/gif", b"GIF8", "gif"),
+    ("image/webp", b"RIFF", "webp"),
 )
+_SUPPORTED_IMAGE_MIMES = tuple(mime for mime, _magic, _ext in _IMAGE_FORMATS)
 
 
 class ImageInputError(ValueError):
@@ -1378,10 +1383,19 @@ class ImageInputError(ValueError):
 
 
 def _sniff_image_mime(data: bytes) -> str:
-    """MIME по магическим байтам ('' — сигнатура неизвестна)."""
-    for mime, magic, _ext in _IMAGE_FORMATS:
-        if data.startswith(magic):
-            return mime
+    """MIME по магическим байтам ('' — сигнатура неизвестна).
+
+    WebP — составной контейнер RIFF: одного префикса мало, нужен маркер
+    `WEBP` в байтах [8:12] (RIFF/WAVE и обрезанные заголовки отклоняются).
+    """
+    if len(data) >= 8 and data.startswith(b"\x89PNG\r\n\x1a\n"):
+        return "image/png"
+    if len(data) >= 3 and data.startswith(b"\xff\xd8\xff"):
+        return "image/jpeg"
+    if len(data) >= 6 and (data.startswith(b"GIF87a") or data.startswith(b"GIF89a")):
+        return "image/gif"
+    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
+        return "image/webp"
     return ""
 
 
@@ -1394,7 +1408,7 @@ def extract_data_url_images(
 ) -> list[dict]:
     """Все `image_url`-части истории -> [{"name", "mime", "data"}] в порядке появления.
 
-    Принимаются только data URI с base64 PNG/JPEG: строгая проверка кодировки и
+    Принимаются только data URI с base64 PNG/JPEG/GIF/WebP: строгая проверка кодировки и
     соответствия MIME сигнатуре; URL не скачиваются, `file://` не читается,
     пользовательские пути не используются (имена генерируются: `image_N.<ext>`).
     Любое нарушение — `ImageInputError` до запуска CLI (fail-closed).
diff --git a/tests/test_claude_bridge.py b/tests/test_claude_bridge.py
index 997b21b..ed9d088 100644
--- a/tests/test_claude_bridge.py
+++ b/tests/test_claude_bridge.py
@@ -32,6 +32,9 @@ BRIDGE_SERVER = BRIDGE_DIR / "server.py"
 PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
 JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 16
 GIF_BYTES = b"GIF89a" + b"\x00" * 16
+GIF87_BYTES = b"GIF87a" + b"\x00" * 16
+WEBP_BYTES = b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"\x00" * 16
+RIFF_WAVE_BYTES = b"RIFF\x00\x00\x00\x00WAVEfmt " + b"\x00" * 16
 
 TOOLS = [
     {
@@ -355,6 +358,41 @@ def test_image_extract_rejects_url_bad_base64_and_mismatch():
         )
 
 
+def test_image_extract_webp_and_gif_names():
+    messages = [
+        {"role": "user", "content": [_image_part("image/webp", WEBP_BYTES)]},
+        {"role": "user", "content": [_image_part("image/gif", GIF_BYTES)]},
+        {"role": "user", "content": [_image_part("image/gif", GIF87_BYTES)]},
+    ]
+    images = core_te.extract_data_url_images(messages)
+    assert [im["name"] for im in images] == [
+        "image_1.webp",
+        "image_2.gif",
+        "image_3.gif",
+    ]
+    assert images[0]["data"] == WEBP_BYTES and images[0]["mime"] == "image/webp"
+    assert images[1]["data"] == GIF_BYTES and images[1]["mime"] == "image/gif"
+    assert images[2]["data"] == GIF87_BYTES
+
+
+def test_image_extract_rejects_non_webp_riff_and_webp_mismatch():
+    with pytest.raises(core_te.ImageInputError) as wave:
+        core_te.extract_data_url_images(
+            [{"role": "user", "content": [_image_part("image/webp", RIFF_WAVE_BYTES)]}]
+        )
+    assert wave.value.code == "unsupported_image_type"
+    with pytest.raises(core_te.ImageInputError) as mismatch:
+        core_te.extract_data_url_images(
+            [{"role": "user", "content": [_image_part("image/png", WEBP_BYTES)]}]
+        )
+    assert mismatch.value.code == "image_type_mismatch"
+    with pytest.raises(core_te.ImageInputError) as truncated:
+        core_te.extract_data_url_images(
+            [{"role": "user", "content": [_image_part("image/webp", b"RIFF\x00\x00")]}]
+        )
+    assert truncated.value.code == "unsupported_image_type"
+
+
 def test_image_only_prompt_keeps_marker_not_pong():
     messages = [{"role": "user", "content": [_image_part()]}]
     images = core_te.extract_data_url_images(messages)
diff --git a/tests/test_opencode_zen_bridge.py b/tests/test_opencode_zen_bridge.py
index e69c7cc..aa64f06 100644
--- a/tests/test_opencode_zen_bridge.py
+++ b/tests/test_opencode_zen_bridge.py
@@ -312,6 +312,10 @@ def test_proxy_pool_quarantine_skips_burned_port_and_falls_back_when_all_quarant
         ({"message": "Free usage limit reached"}, True),
         ("USAGE LIMIT REACHED", True),
         ("provider.free-limit", True),
+        ("Request quota exhausted.", True),
+        ("Request quota exhausted. QUOTA", True),
+        ({"message": "subscription quota exhausted"}, True),
+        ("QUOTA EXHAUSTED", True),
         ({"message": "Connection lost"}, False),
         (None, False),
     ],
@@ -320,6 +324,32 @@ def test_is_free_quota_error(bridge: Any, err: object, expected: bool) -> None:
     assert bridge._is_free_quota_error(err) is expected
 
 
+@pytest.mark.parametrize(
+    "ev",
+    [
+        {"statusCode": 400, "message": "Request quota exhausted."},
+        {
+            "type": "error",
+            "error": {"statusCode": 400, "message": "subscription quota exhausted"},
+        },
+        {"type": "error", "error": "Request quota exhausted. QUOTA", "status": 400},
+    ],
+)
+def test_quota_stream_error_is_transient_despite_fatal_status(
+    bridge: Any, ev: dict[str, Any]
+) -> None:
+    assert bridge._is_transient_stream_error(ev) is True
+
+
+def test_fatal_stream_error_without_quota_stays_fatal(bridge: Any) -> None:
+    assert (
+        bridge._is_transient_stream_error(
+            {"statusCode": 400, "message": "invalid request body"}
+        )
+        is False
+    )
+
+
 def test_map_serve_event_preserves_quota_type(bridge: Any) -> None:
     mapped = bridge._map_serve_event(
         {

```

## 4. Verification Evidence (L1 / L2)
- Unit & Stream Suite: `pytest tests/test_images_strict.py tests/test_opencode_zen_bridge.py tests/test_claude_bridge.py tests/test_stream_formatting_and_subagents.py tests/test_agy_bridge_resilience.py -v`
- Result: **428 passed, 737 subtests passed in 240.40s, 0 failures, 0 errors**
- Linter: `ruff check` on modified files: **All checks passed!**
- L3: Deferred to post-ACCEPT heavy path test on live bridge.

## 5. Architectural Compliance
- **Universal Layer Invariant**: All image sniff and validation logic resides in `core/tool_emulation.py`.
- **Quota Error Precedence**: `_is_transient_stream_error` inspects quota error conditions BEFORE checking fatal status codes (400), ensuring proxy quarantine and rotation happen deterministically.



---
PANEL-NONCE: e1ed9eb54a837317
ARTIFACT-SHA256: b07eff26038e56e4eecdacfb46657cef17dbc4441031e6a7ffbdac36a1d9d759
Инструкция судье: первыми двумя строками ответа повтори дословно «PANEL-NONCE: e1ed9eb54a837317» и «ARTIFACT-SHA256: b07eff26038e56e4eecdacfb46657cef17dbc4441031e6a7ffbdac36a1d9d759».
