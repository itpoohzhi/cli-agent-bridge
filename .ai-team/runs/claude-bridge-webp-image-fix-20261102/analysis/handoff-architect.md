# Handoff для Архитектора (handoff-architect.md)

## 1. Цель архитектурной проработки
Сформировать Architecture Packet и ADR-0023 по расширению мультимодальных форматов ядра `core/tool_emulation.py` (WebP, GIF) и отказоустойчивости ротации квот `opencode-zen-bridge`.

## 2. Ссылки на свидетельства
- [E-01], [E-02], [W-01]: Ограничение `_IMAGE_FORMATS` и `_sniff_image_mime` в `core/tool_emulation.py`.
- [E-03], [W-03]: Реальный сбой DSH с WebP (отказ 400).
- [E-04], [W-02]: Существующий прецедент поддержки WebP в `server.py:464`.
- [E-05], [E-06], [W-04]: Нераспознанный маркер `Request quota exhausted.` в `bridges/opencode-zen-bridge/server.py:1751`.

## 3. Границы изменений
- `core/tool_emulation.py`: добавление WebP и GIF в `_IMAGE_FORMATS` и двухпозиционный сниффинг `RIFF....WEBP`.
- `bridges/opencode-zen-bridge/server.py`: добавление маркеров `"quota exhausted"`, `"request quota exhausted"`, `"subscription quota exhausted"` в `_is_free_quota_error`.
- `tests/test_claude_bridge.py`, `tests/test_images_strict.py`, `tests/test_opencode_zen_bridge.py`.

## 4. NFR-Scale Card
```text
Hot-Path & HL-ENV: N/A (cold-path only)
Точки входа: HTTP admission /v1/chat/completions до запуска CLI.
T_budget на проверку сигнатуры: ≤ 0.05 мс (O(1) срезы байт).
M_budget: 0 дополнительных аллокаций.
S_frame_max: сохранены действующие лимиты (10 МБ на файл, 20 МБ на запрос).
```

## 5. DoD аналитической фазы (SA-DOD)
- SA-DOD-001 PASS: `research-plan.md` с Карточкой задачи в наличии.
- SA-DOD-002 PASS: `evidence-white.md` содержит прямые цитаты кода и факты логов.
- SA-DOD-003 PASS: `evidence-black.md` сопоставлен с классами блокеров.
- SA-DOD-004 PASS: `evidence-green.md` содержит проверяемые контракты.
- SA-DOD-005 PASS: `evidence-ledger.md` с идентификаторами E-01..E-06.
- SA-DOD-006 PASS: `competing-options.md` содержит варианты V1/V2 с матрицей 6 классов.
- SA-DOD-007 PASS: `consolidated-rca-decision.md` содержит четкую рекомендацию.
- SA-DOD-008 PASS: `handoff-architect.md` сформирован с NFR-Scale Card.
