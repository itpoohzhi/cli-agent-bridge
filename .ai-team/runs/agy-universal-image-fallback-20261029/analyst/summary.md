# Stage 1 System Analyst — итог

Статус: аналитический пакет сформирован; реализация и production-приёмка не выполнялись.
Task: agy-universal-image-fallback-20261029.
Role: system-analyst; pinned user assignment gpt-6.1-sol high; transport native session.
Skill: ~/Мой диск/skils/ai-sdlc/universal/system-analyst/SKILL.md. Указанный в брифе старый путь отсутствует; актуальный найден внутри skils.
Repo: ~/tmp/cli-agent-bridge/agy-universal-image-fallback; branch feat/agy-universal-image-fallback.
Base/current HEAD: 012da99905ec27a6133afb4f3e768ff9b4426a8f.
RUN_DIR: .ai-team/runs/agy-universal-image-fallback-20261029 (env не задан; путь установлен по существующему state.json task/run_id).

## Артефакты

- analysis/agy-universal-image-fallback/research-plan.md — четыре закрытых spike, timeboxes и consumers.
- analysis/agy-universal-image-fallback/evidence-ledger.md — 61 воспроизводимый датированный факт.
- analysis/agy-universal-image-fallback/open-questions.md — восемь RESOLVED записей; незакрытых0.
- analysis/agy-universal-image-fallback/handoff-architect.md — REQ/CON/INV/RISK/ASSUMP, as-is Mermaid, compatibility alternatives, runtime transition constraints, reuse brief, все46 HL-ENV fields и ограничения capacity evidence.
- analysis/agy-universal-image-fallback/handoff-qa.md — AC/SCN, uf01..uf10 append-only coverage plan, negative/boundary/idempotency/resource/live scenarios.

## Основные выводы

1. Отдельная explicit runtime policy absent=false и production=true совместима со strict defaults: старый harness изолирует config и пишет только IMAGE_INPUT_ENABLED. Связывать universal с существующим input=true нельзя. Static fleet/proof и ao10 менять нельзя.
2. Production сейчас имеет IMAGE_INPUT_ENABLED=true без universal flag; deployed files отдельно от checkout. Для release нужны обновление runtime и explicit config activation, затем live DSH.
3. Image downgrade нужен до pre-collection400, post-slot gate/spool terminal result и обеих runtime retry-ветвей, включая ранний hot-session continue. Надо очистить историю, prompt и full_prompt, завершить Run/очистить каталог, CAS-инвалидировать только прежнюю session и снять свой CID claim.
4. Delivered guard включает text/tool_calls/stream reasoning; initial SSE200 не является success. Media retry bounded1; strict budget сохраняется. Generic budget0 требует отдельного universal-path решения.
5. Фактический image baseline46 test methods, а verifier40 IDs; «44» в брифе уточнено. Signature sniff не доказывает pixel-valid raster; старый img10 нельзя ломать. Sibling omission неполон для media.text/dict-content.

## Проверки SA-DOD-001..008

Композитная команда взята из skill reference и исполнена без правок в analysis directory:

```text
SA-DOD-001 PASS (61 facts)
SA-DOD-002 PASS (no guesses)
SA-DOD-003 PASS (4 spikes)
SA-DOD-004 PASS (8 open questions)
SA-DOD-006 PASS (no AC in handoff)
SA-DOD-008 PASS (timeboxes clean)
SA-DOD-005 PASS: все даты разобраны datetime.date.fromisoformat и соответствуют снимку2026-10-29.
SA-DOD-007 PASS: оба handoff содержат REQ-ID.
```

Дополнительно: все F-reference разрешаются; три независимых факта воспроизведены — delivered/early hot continue (server source), ImgEnv old-flag-only (fixture source), sanitized production projection IMAGE_INPUT_ENABLED=true. Все OPEN rows имеют RESOLVED. Schema46 HL fields посчитана. Роли соблюдены: нет выбора архитектуры, продуктовых правок или review-verdict; диаграмма as-is. Пакеты соответствуют двум consumers. Артефакты содержат только безопасные технические данные; auth/payload/PII не копировались.

## Baseline tests и неизменность

В фоне через run-guarded исполнялись две независимые local fake-CLI группы:
- 36 Image* tests,23.005s,OK,exit0; tool session17642.
- 10 AcceptanceOracleTests,9.759s,OK,exit0; tool session5402.
Итого46/46 на исходной версии. pytest отсутствует в system Python; import unittest discovery доступен. Negative body cases печатали server-thread ConnectionResetError после закрытия peer; тесты прошли и wrapper exit0.

Полное byte equality существующего test file с HEAD подтверждено. git diff по server/fleet/tests пуст. Numstat от 5a19559426de7508d525e2bd465eff648665a6a7:2205 added,0 deleted — существующий baseline, не новые изменения этого этапа.

ПРОВЕРЕНО ЛЁГКИМ: структура/источники/DoD,61 факт,46 baseline tests, source diff.
ПРОВЕРЕНО ТЯЖЁЛЫМ: новая функция на живом DSH Desktop не проверялась; Stage1 не менял production. Повторное чтение исходных точек, sanitized production config и fake CLI baseline подтверждает только исследовательские выводы.
НЕ ПРОВЕРЕНО: candidate implementation/uf tests/full project suite, active production universal policy, existing live DSH chat fallback, upstream quota/RPS/p99/RSS/FD capacity. Capacity gates не объявлены PASS.

Исследовательских вопросов0; отсутствие production SLA/квот установлено как release limitation, а не подменено выдуманными числами. Stage1 не выдаёт architecture council acceptance или PANEL PROOF и не запускает Coder/MR. Следующий этап — архитектура с учётом зафиксированных ограничений.

KB: deferred в рамках ограниченного Stage1; аналитические артефакты сохранены в заданном repo, без публикации в Outline и без изменения канона/skill.

Проверено: 2026-10-29T17:17:01+03:00
