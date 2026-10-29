PANEL-NONCE: 9b80b6c7836f0083
ARTIFACT-SHA256: e1e894009f252e6413925d0585c51c093a63cbca054149965783b932c15c5bcc

Канон `~/Мой диск/Context/AGENTS.md` прочитан целиком до `<!-- КАНОН-КОНЕЦ -->`; проектных `AGENTS.md`/`.agents/AGENTS.md`/`CLAUDE.md` в корне репозитория нет (проверено `ls`). Ревью read-only: пакет, diff `server.py` (778 строк), архитектурный пакет (AD/INV/AC), тесты uf01–uf10, независимая проба чистых функций.

## Находки

**BLOCKER-SAFETY — unknown-only structured media обходит нормализацию целиком (AD-002, INV-02, REQ-06).**
[_media_part_counts()](/Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/bridges/agy-bridge/server.py:909) считает только классы `image`/`media`; класс `unknown` из [_classify_part()](/Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/bridges/agy-bridge/server.py:870) не учитывается. Поэтому в `do_POST` гейт `if image_parts or other_media:` ([server.py](/Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/bridges/agy-bridge/server.py:4092)) не срабатывает: `render_messages` остаётся исходным ([server.py](/Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/bridges/agy-bridge/server.py:4087)), `stripped_full_prompt` не строится, `force_cold=False`, события `collect/unsupported_media` нет, а промпт рендерится legacy-утём [_flatten_content()](/Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/bridges/agy-bridge/server.py:592): dict-content — `str(content)` (строка 613), list-part — `str(item["text"])` без проверки `type` (строки 610–611). Это ровно отвергнутая в AD-002 альтернатива «str(content)/text-first renderer» и прямое нарушение `normal_universal_render`: «ONLY unknown structured parts → stripped placeholders, stage=collect reason=unsupported_media». Сами хелперы [_flatten_content_stripped()](/Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/bridges/agy-bridge/server.py:966) и [_universal_render_messages()](/Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/bridges/agy-bridge/server.py:1025) безопасны — дефект только в гейтинге вызова. L2 это не ловит: `test_uf07` проверяет unknown только на уровне хелперов, HTTP-кейса unknown-only нет ([test_agy_bridge_resilience.py](/Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/tests/test_agy_bridge_resilience.py:6979)).

Независимая проба (импорт модуля, чистые функции) подтвердила утечку маркера `PAYLOAD_SECRET_12345` в legacy-промпт во всех вариантах при `counts=(0,0)`:

```text
A counts (0, 0) classify unknown
A legacy prompt contains SECRET: True    # dict-content {"type":"input_video","data":...}
B counts (0, 0)
B legacy prompt contains SECRET: True    # list-part {"type":"input_video","text":...}
C classify unknown counts (0, 0)
C legacy prompt contains SECRET: True    # {"type":"text","text":{"inlineData":...}}
D counts (0, 0) legacy leaks: True       # dict-content {"InlineData":...}
E counts (0, 1) stripped: '### 1. user\n[media omitted]'  # контроль: enumerated video безопасен
```

Минимальный фикс: считать unknown structured parts медиа для гейтинга в `do_POST` (stripped prompt + `collect/unsupported_media` + `force_cold`) и добавить HTTP-регрессию unknown-only.

**MINOR — VER-005 в замороженной форме не зелёный.** Полный `pytest` падает на сборе трёх несвязанных модулей (`test_cache_usage.py`, `test_fleet_v3.py`, `test_tool_parser.py`); по пакету те же ошибки на BASE, scoped-эквиваленты L2 зелёные (176 passed / 273 subtests; unittest 158/158). Регрессией кандидата не считаю, фиксирую как процессный долг.

**Не проверено (вне этого вердикта):** VER-010 / REQ-05 — production rollout и живая DSH-приёмка по брифу пост-советные; ресурсный профиль 2N и exactly-once не измерялись (RISK-008/001 из пакета).

## Подтверждено по коду

AD-001: fail-closed флаг, отдельный кэш/замок и сброс в `_reset_sqlite_guards_for_tests`, [_image_gate_universal()](/Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/bridges/agy-bridge/server.py:830) без proof/SHA; валидация INV-01 (data:-only, MIME/base64/размер до decode, sniff, non-user reject) сохранена в [_collect_images()](/Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/bridges/agy-bridge/server.py:1177). AD-003: runtime-гард после `run.close()`, до hot-continue и transient, ровно один повтор с резервом ([server.py](/Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/bridges/agy-bridge/server.py:3702)); [_downgrade_to_text_in_run_once()](/Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/bridges/agy-bridge/server.py:1303) — лог → cleanup → CAS [_session_invalidate()](/Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/bridges/agy-bridge/server.py:1492) → оба промпта; слот освобождается один раз в `finally`. AD-004/AD-005 и enumerated-таксономия AD-002 замечаний не вызвали; scope ровно 2 файла (`+573/−56`, `+1437/−0`), префикс 249933 байта подтверждён L2 VER-006.

Итог: один неустранённый BLOCKER-SAFETY по INV-02/AD-002 при в целом корректной реализации остальных инвариантов.

VERDICT: REJECT