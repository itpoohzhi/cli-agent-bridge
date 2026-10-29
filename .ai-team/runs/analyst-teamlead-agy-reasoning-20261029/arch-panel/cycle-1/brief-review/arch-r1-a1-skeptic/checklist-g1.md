# Чек-лист brief-review: arch R1, cycle 1, run analyst-teamlead-agy-reasoning-20261029, поколение g1
## Пре-линт [L]
SK-A-02 [L] | обёртки D9 целых файлов Architecture Packet и receipt ARCH_GATE + sha256 == packet_sha256 | источник: brief-review/references/checklist-sources.md#SK-A
SK-A-12 [L] | сравнение строк seat_slot (gemini-4-argon-high) != architect_slot (claude-opus-5-5-high) | источник: brief-review/references/checklist-sources.md#SK-A
JD-01 [L] | побайтное сравнение начала brief-v1.md с prompt-skeptic.txt + пустая строка | источник: brief-review/references/checklist-sources.md#JD
HY-01 [L] | N/A для CLI-слота gemini-4-argon-high | источник: brief-review/references/checklist-sources.md#HY
HY-03 [L] | отсутствие токенов закрытого списка плейсхолдеров вне блоков <<<ARTIFACT ... ARTIFACT_END>>> | источник: brief-review/references/checklist-sources.md#HY
## BR — бизнес-требования
BR-01 [P] | Реалтайм-стриминг размышлений (`reasoning_content`) `gemini-4-argon` через `agy-bridge (:9887)` в DSH из SQLite `conversations/<cid>.db` (`step_payload` 20.3) во время `status=8` (`RC-1`) | источник: /tmp/cel-runs/analyst-teamlead-agy-reasoning-20261029/goal.md#L7
BR-02 [P] | Устранение гонки финального дренирования `Run._pump` и `_TranscriptTail` (`RC-2`), учёт `reasoning` в `delivered` (`RC-3`), изоляция `sess_key` от фоновых запросов без `tools` (`RC-4`) | источник: analysis/agy-realtime-reasoning/handoff-architect.md#L14-L20
BR-03 [P] | Все 12 требований `REQ-001..REQ-012` и критерии `AC-001..AC-016` присутствуют в брифе | источник: analysis/agy-realtime-reasoning/handoff-architect.md#L53-L66
BR-04 [P] | Конверт `HL-ENV/v1` из 46 полей и инварианты Python-профиля `aisdlc-gcge/skills/architecture.md` | источник: analysis/agy-realtime-reasoning/handoff-architect.md#L135-L215
## JD — пункты места
JD-02 [N] | Нет промпта другой шляпы и нет двух ролей в одном брифе | источник: brief-review/references/checklist-sources.md#JD
JD-03 [P] | «суди ЗАНОВО, не подтверждай прошлый вердикт автоматически» | источник: brief-review/references/checklist-sources.md#JD
JD-04 [P] | Ровно один блок «ФОРМАТ ОТВЕТА (строго)» на весь brief-v1.md | источник: brief-review/references/checklist-sources.md#JD
JD-05 [P/N] | seed_recheck_duty: нет | источник: brief-review/references/checklist-sources.md#JD
JD-06 [N] | R1: чужих вердиктов нет | источник: brief-review/references/checklist-sources.md#JD
JD-07 [P] | Факт-карта, строка `РЕЖИМ: architecture`, секция КОНТЕКСТ присутствуют | источник: brief-review/references/checklist-sources.md#JD
JD-08 [N] | Бриф самодостаточен, все первичные артефакты вложены целиком | источник: brief-review/references/checklist-sources.md#JD
## HY — гигиена
HY-02 [N] | Нет противоречий между разделами | источник: brief-review/references/checklist-sources.md#HY
HY-04 [N] | Нет секретов | источник: brief-review/references/checklist-sources.md#HY
HY-05 [N] | Нет следов brief-review | источник: brief-review/references/checklist-sources.md#HY
HY-06 [N] | Формулировки чек-листа не вставлены без первичного артефакта | источник: brief-review/references/checklist-sources.md#HY
## Параметры места
panel: arch | round: R1 | round_type: R1 | hat: skeptic
hat_prompt: ~/work/universal-panel/prompt-skeptic.txt
seat_slot: gemini-4-argon-high
seat_kind: panel-judge
seed_recheck_duty: нет | ranked_position: 2 из 3
architect_slot: claude-opus-5-5-high
