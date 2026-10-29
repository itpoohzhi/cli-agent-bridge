# Чек-лист brief-review: arch R1, cycle 1, run agy-image-input-fix-20261029, поколение g1
## Пре-линт [L]
SK-A-02 [L] | обёртки D9 целых файлов Architecture Packet и sha256 == packet_sha256 | источник: brief-review/references/checklist-sources.md#SK-A
SK-A-12 [L] | сравнение строк seat_slot != architect_slot (gpt-6.1-sol-high) | источник: brief-review/references/checklist-sources.md#SK-A
JD-01 [L] | ролевая подпись первой строки brief-v1.md | источник: brief-review/references/checklist-sources.md#JD
HY-03 [L] | отсутствие токенов закрытого списка плейсхолдеров вне блоков артефактов | источник: brief-review/references/checklist-sources.md#HY
## BR — бизнес-требования
BR-01 [P] | Включение приема изображений (image_url data:image/...) для gemini-4-argon и gemini-3.8-flash в agy-bridge (:9887) через метод workspace-read и --add-dir <img_dir> | источник: analysis/agy-image-input-fix/handoff-architect.md
BR-02 [P] | Глобальная 1-based нумерация вложений 1..K на всех путях (холодный, resumed, явный conversation_id, fallback hot->cold) без повторного прикрепления картинок прошлых ходов | источник: analysis/agy-image-input-fix/handoff-architect.md
BR-03 [P] | Все 12 требований REQ-001..REQ-012 и критерии AC-01..AC-12 присутствуют в брифе | источник: analysis/agy-image-input-fix/handoff-architect.md
BR-04 [P] | Конверт HL-ENV/v1 из 46 полей и инварианты Python-профиля aisdlc-gcge/skills/architecture.md | источник: analysis/agy-image-input-fix/handoff-architect.md
## JD — пункты места
JD-02 [N] | Нет промпта другой шляпы и нет двух ролей в одном брифе | источник: brief-review/references/checklist-sources.md#JD
JD-04 [P] | Строгий формат ответа PoL-V06/PoL-V07 (PANEL-NONCE, ARTIFACT-SHA256, COVERAGE, FINDINGS_COMPLETE, ОБЩИЙ ВЕРДИКТ) | источник: brief-review/references/checklist-sources.md#JD
JD-05 [P] | seed_recheck_duty присутствует с полной таблицей дайджестов select_round_seats.py | источник: brief-review/references/checklist-sources.md#JD
JD-06 [N] | R1: чужих вердиктов нет | источник: brief-review/references/checklist-sources.md#JD
JD-08 [N] | Бриф самодостаточен, все первичные артефакты D9 вложены целиком | источник: brief-review/references/checklist-sources.md#JD
## HY — гигиена
HY-02 [N] | Нет противоречий между разделами | источник: brief-review/references/checklist-sources.md#HY
HY-05 [N] | В самом проверяемом брифе судьи нет упоминания brief-review | источник: brief-review/references/checklist-sources.md#HY
