PANEL-NONCE: 1cbd7c73b36b575b
ARTIFACT-SHA256: 171a1875f650cdc593ecdba1f3a5b3fc015691f7010673e5f3b0b7e34649c9ab

Пакет разобран по тексту, без чтения файлов и shell-команд, как требует бриф. Основной контракт выполнен, но есть два существенных замечания к тестам и профилю и несколько мелких.

**Что подтверждается по тексту пакета**
- **F-001 (medium→medium).** В diff `web` профиля обе модели AGY получают `medium: medium`, а `xhigh` и `max` клампятся в `high`. Фикстура содержит отрицательные проверки на возврат `medium->high` и на возврат effort-клона `gemini-3.8-flash-high`.
- **Парсер YAML.** `_ProfileSafeLoader` наследует `yaml.SafeLoader` и сводит `!!js` к `construct_scalar`. Выражения не исполняются, а литерал `'use !!js here'` не затрагивается. Конструктор добавлен в подклассе, поэтому глобальный `SafeLoader` не мутирует.
- **Ключ `off`.** Проблема YAML 1.1 (`off` читается как `False`) обработана нормализацией. Общий YAML-anchor `*agy` не ломает подмену значения: проверка присваивает новый dict, а не мутирует общий.
- **F-003/F-004 (реклама алиасов).** Дефолт `ADVERTISE_EFFORT_ALIASES` переключён на `"off"`, переопределение через env сохранено. Все 8 алиасов продолжают резолвиться на POST, для этого есть параметризованный тест.
- **F-002 / S3-R1-003 (`fleet.json`).** `efforts` приведены к `["low","medium","high"]`, индекс моделей строится один раз перед циклом (Seat 3 F-001).
- **CAS-бэкапы.** Права `0600`, `fcntl.flock` на `sync.lock`, `cas_post_sha256` отличается от `post_sha256` для desktop, это объяснено повторной сериализацией живым DSH.
- **S3-R1-001.** 18 падений `TestNativeHttp`/`TestPassthroughAuthFlagSource` воспроизводятся на чистом HEAD `b442c2e` один в один. Причина указана: утечка `server._shutting_down`.

**Замечания**
1. **Тестовый модуль падает при сборке без PyYAML (major).**
   - `tests/test_dsh_profile_config.py` делает `import yaml` и при отсутствии модуля добавляет в `sys.path` жёстко зашитый путь `/opt/homebrew/lib/python3.14/site-packages`.
   - Если директории нет, выполняется `raise`. В чистом CI это ошибка на этапе сбора для всего модуля, включая старый `DshProfileConfigTests`, а не skip.
   - Это же противоречит заявленному «skip в чистом CI», и это хардкод среды вопреки правилу 4 проекта.
   - Косвенный признак проблемы: `python3 -m pytest tests/ -v` дал exit=2. Зелёные прогоны выполнены только с `uv run --with pyyaml`, что маскирует дефект.
   - Нужно `pytest.importorskip("yaml")` (или объявить зависимость) и убрать правку `sys.path`.
2. **Дрейф вне заявленной дельты в `web` профиле и устаревший бэкап (major).**
   - В diff есть не относящиеся к задаче правки зоны opencode-zen: `glm-5.3-flash-free` перенесён и переименован в «deprecated -> deepseek-v4.1-flash-free», а из `allowedModels` удалена запись `opencode-zen-bridge/glm-5.3-flash-free`.
   - Бэкап снят в 23:40, живой файл записан в 01:22. Похоже, между ними писал синхронизатор Zen, а бэкап не соответствует состоянию непосредственно перед нашей записью.
   - Откат с этого бэкапа молча затрёт чужую синхронизацию.
   - Заявление «exact semantic delta проверена» с этим diff не согласуется. Нужны: объяснение происхождения Zen-дельты, бэкап непосредственно перед записью под замком, проверка `pre_sha256` внутри CAS.
3. **Baseline не на полном наборе (minor).**
   - На HEAD прогнан только подмножество `-k "TestNativeHttp or TestPassthroughAuthFlagSource"`.
   - Итоговый полный `pytest tests/` после исправлений трёх strict-тестов не приведён.
   - Тезис «0 регрессий в полном наборе» подтверждён косвенно: 225 passed по 6 модулям плюс историческая сводка 21 failed = 3 + 18.
4. **Runtime-доказательства из вторых рук (minor).** RT-01..RT-06 переданы владельцем, Coder их не повторял. Прямые логи есть только у RT-07 (`task-776.log`, `task-786.log`).
5. **Глобальный дефолт без аудита потребителей (minor).**
   - Дефолт `"off"` меняет `GET /v1/models` для всех потребителей шлюза.
   - Аудит клиентов, рассчитывавших на алиасы (синхронизация каталога Hermes, `claude-p-bridge`), и ADR про смену дефолта в пакете не показаны.
   - Дополнительно в `tests/test_bridge_strict.py` ruff-форматирование зацепило не относящиеся к задаче строки, что шумит в diff.

Замечания 1 и 2 блокируют ACCEPT. Остальные не блокирующие и решаются фиксацией или принятием риска.

```json
{
  "schema_version": "1.0",
  "task_id": "agy-picker-dedup-20261101",
  "run_id": "agy-picker-dedup-20261101",
  "stage": "COUNCIL",
  "round": "R1",
  "seat": 1,
  "hat": "Скептик (Skeptic)",
  "model": "claude-sonnet-5-5-high",
  "family": "Anthropic",
  "verdict": "NEEDS WORK",
  "summary": "Целевой контракт (2 карточки AGY, 3 Claude, 0 effort-клонов, medium->medium, обратная совместимость POST-алиасов, безопасный парсер !!js, CAS 0600) подтверждается по тексту пакета. Остаются два блокера качества: тестовый модуль test_dsh_profile_config.py роняет сбор при отсутствии PyYAML из-за хардкода homebrew sys.path и raise, а diff web-профиля содержит чужую Zen-дельту (glm-5.3-flash-free) при устаревшем бэкапе, что противоречит заявлению об exact semantic delta и делает откат небезопасным. Дополнительно: baseline на HEAD снят на подмножестве, runtime RT-01..RT-06 из вторых рук, глобальный дефолт рекламы алиасов без аудита потребителей.",
  "verified_invariants": [
    "F-001: medium->medium в reasoningEfforts обеих моделей AGY, xhigh/max клампятся в high; негативные проверки в фикстуре",
    "_ProfileSafeLoader (SafeLoader + construct_scalar для !!js) не исполняет выражения и не затрагивает литералы",
    "ADVERTISE_EFFORT_ALIASES=off по умолчанию, env-override сохранён, все 8 алиасов резолвятся на POST",
    "fleet.json и bridges/agy-bridge/fleet.json согласованы: efforts [low, medium, high]",
    "CAS-бэкапы 0600 под flock; на чистом HEAD b442c2e те же 18 pre-existing падений подмножества TestNativeHttp/TestPassthroughAuthFlagSource"
  ],
  "findings": [
    {
      "id": "SK-R1-001",
      "severity": "major",
      "file": "tests/test_dsh_profile_config.py",
      "summary": "import yaml с жёстким sys.path на /opt/homebrew и raise при отсутствии каталога: ошибка сбора всего модуля в окружении без PyYAML.",
      "failure_scenario": "CI или venv без PyYAML: collection error, pytest tests/ падает, включая старый DshProfileConfigTests. Зелёные прогоны только через uv run --with pyyaml, python3 -m pytest tests/ дал exit=2.",
      "required_fix": "pytest.importorskip('yaml') или объявленная тестовая зависимость; убрать правку sys.path."
    },
    {
      "id": "SK-R1-002",
      "severity": "major",
      "file": "~/.dsh/profiles/web/cordis.patch.yml",
      "summary": "В diff есть не относящаяся к задаче Zen-дельта (glm-5.3-flash-free перенесён и переименован, удалён из allowedModels); бэкап снят за 1ч40м до записи.",
      "failure_scenario": "Откат с бэкапа 23:40 затрёт синхронизацию opencode-zen, а заявление об exact semantic delta не подтверждается diff.",
      "required_fix": "Объяснить происхождение дельты; бэкап непосредственно перед записью под flock; проверка pre_sha256 в CAS; либо принятие риска владельцем."
    },
    {
      "id": "SK-R1-003",
      "severity": "minor",
      "file": "teamlead/package.md",
      "summary": "Baseline на HEAD снят на подмножестве -k; итогового полного pytest tests/ после правок нет.",
      "failure_scenario": "Скрытая регрессия вне 6 модулей не исключена прямым сравнением."
    },
    {
      "id": "SK-R1-004",
      "severity": "minor",
      "file": "handoff/coder.json",
      "summary": "RT-01..RT-06 переданы владельцем и не повторялись; прямые логи только у RT-07."
    },
    {
      "id": "SK-R1-005",
      "severity": "minor",
      "file": "server.py",
      "summary": "Глобальная смена дефолта рекламы алиасов без аудита потребителей GET /v1/models и без ADR; ruff-шум в test_bridge_strict.py."
    }
  ]
}
```

VERDICT: NEEDS WORK
