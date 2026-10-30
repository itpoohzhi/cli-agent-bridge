# Coder backlog — ADR 0009 (dsh-subagent-empty-provider-fix-20261030, дельта A2)

Источник истины: `.ai-team/runs/dsh-subagent-empty-provider-fix-20261030/architecture/architecture-packet.json`.
Команды проверок VER-001..VER-010 заморожены в пакете. Здесь они не дублируются, их нельзя
менять или ослаблять. Coder не владеет verification surface (owner — Verifier).

Запуск Coder возможен только после ACCEPT повторного прохода Совета Тимлидов по дельте A2.

## CB-01. Подготовить baseline кандидата (MAT-P01)
- Рабочий каталог: `~/work/tmp/dsh-tool-subagent-overlay/candidate/`. Не Google Drive и не репозиторий.
- Извлечь из `app.asar` все файлы пакета `dsh/node_modules/@deepseek-ai/dsh-tool-subagent/`:
  `package.json`, `lib/**`, `locale/**`.
  - Способ — разбор заголовка asar, как в `materialization_plan[MAT-P01].baseline_extract_command`.
  - Для каждого файла сверить sha256 с `integrity.hash` в заголовке.
  - Ожидаемый sha256 для `lib/index.js`: `de7b10aaf52b1b1616d13a831a9ece1f820b8a6302fe94667f31b6d641b2f46e`.
- Отдельно сохранить `~/work/tmp/dsh-tool-subagent-overlay/baseline-index.js` — это отрицательный
  контроль для VER-001..004.
- Критерий: на baseline VER-001 даёт exit 3, VER-004 — exit 1 (`NORMALIZER_DECL`), VER-005 — exit 0.

## CB-02. Реализовать AD-001 в `lib/index.js` кандидата
- Добавить чистую функцию `normalizeDelegationModelRequest(args)` в регион model-selection: после
  `function modelRouteKey(` и до первого `//#endregion`. Только там её найдут оракулы через `node:vm`.
  - Для строковых `provider`, `model`, `reasoning_effort` — `trim()`; пустая строка → `undefined`.
  - Значения других типов, включая `null`, не трогать.
  - Остальные поля `args` скопировать без изменений. Исходный `args` не мутировать.
  - Без новых import, без `require(`/`import(`, без `process.env` (VER-005).
- В `execute` заменить `const modelRequest = args;` на
  `const modelRequest = normalizeDelegationModelRequest(args);`.
  Строку оставить до `const requiresRoutePreflight = …` (VER-004 сверяет текст дословно).
- Не менять `hasDelegationModelRequest`, `assertNonEmpty`, `requestedAgentOptions`,
  `assertAllowedModelSelection`, `preflightChildLlmRoute`.
  - Сохранить ровно 3 вызова `hasDelegationModelRequest` и по одному вызову
    `requestedAgentOptions` и `assertAllowedModelSelection`.
  - Аргументы вызовов: `request` / `modelRequest`.
- Регресс-проверку запускать до фикса (red), затем после (green):
  `TS_UNDER_TEST=~/work/tmp/dsh-tool-subagent-overlay/candidate/lib/index.js` + команды
  VER-001..VER-005 из пакета.

## CB-03. Метаданные overlay в `package.json` кандидата
- Добавить `"dshOverlay": {"baseAsarSha256": "<integrity.hash lib/index.js из app.asar>", "adr": "docs/adr/0009-dsh-subagent-empty-route-normalization.md"}`.
- `name` и `exports` не менять. `version` можно дополнить build-меткой, например `0.2.1-rc.5+adr0009`.

## CB-04. Передать кандидата Verifier (Coder в профиль не пишет)
- Передать:
  - путь кандидата;
  - sha256 каждого файла;
  - вывод VER-001..005 на кандидате и на baseline;
  - diff `baseline-index.js` ↔ `candidate/lib/index.js`. Ожидаются только новая функция и одна строка в `execute`.
- Материализация в `~/.dsh/profiles/desktop/node_modules/@deepseek-ai/dsh-tool-subagent/` и гейт DG-001
  (VER-006..VER-010) — зона Verifier/владельца. Порядок — `evolution.rollout` пакета.

## Запреты
- Не трогать `app.asar` и `~/.dsh/profiles/desktop/{cordis.patch.yml,package.json,pnpm-lock.yaml}`.
- Не создавать отдельный тестовый модуль и не менять команды VER: они самодостаточны.
- Не объявлять доставку подтверждённой без VER-007 с отрицательным контролем (ASM-001 — PENDING_DELIVERY_GATE).
- `list_subagent_models` — вне scope (Q-002).
