# Защита веток, CI-гейты и синхронизация `launchd` (`cli-agent-bridge`)

Документ фиксирует обязательные CI-проверки GitHub для веток `dev` и `main`, локальную воспроизводимость проверок и операционный runbook синхронизации `launchd` `ExitTimeOut` на macOS (`RISK-001`).

## 1. Обязательные CI-проверки для веток `dev` и `main`

Workflow [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) запускается на `pull_request`, `push` в `dev`/`main` и `workflow_dispatch` (Python 3.13) и определяет два обязательных job-а:

| Check context (имя job) | Раннер | Состав проверок |
| --- | --- | --- |
| `lint-types-test` | `ubuntu-latest` | `python -m ruff check .`, `python -m basedpyright`, полный `python -m pytest -q` |
| `drain-macos` | `macos-latest` | macOS-набор drain/lifecycle/plist/stream-drain E2E + проверка kill-switch (`BRIDGE_DRAIN_POLICY_ENABLED=0`) |

### Настройка в GitHub UI (для администратора репозитория)

> Перед выбором статусов убедитесь, что workflow `.github/workflows/ci.yml` выполнился хотя бы один раз — иначе имена `lint-types-test` и `drain-macos` не появятся в поиске GitHub.

1. Откройте **Settings → Branches** (Classic branch protection rules) **или** **Settings → Rules → Rulesets** (рекомендуется для единого правила на обе ветки).
2. Создайте правило/ruleset для веток `dev` и `main`.
3. Включите **Require a pull request before merging** — это запрещает прямой `push` в `dev` и `main`.
4. Включите **Require status checks to pass before merging** (желательно также **Require branches to be up to date before merging**) и добавьте ровно два обязательных check context:
   - `lint-types-test`
   - `drain-macos`
5. Запретите переписывание истории и удаление веток:
   - в Classic: оставьте **Allow force pushes** и **Allow deletions** выключенными;
   - в Rulesets: включите **Block force pushes** и **Restrict deletions**.
6. Сохраните изменения.

### Read-only аудит после включения защиты

Скрипт [`scripts/check_branch_protection.py`](../scripts/check_branch_protection.py) выполняет только read-only `GET`-запросы через `gh api` (маскирует токены в выводе) и проверяет как Classic protection, так и Rulesets:

```bash
python scripts/check_branch_protection.py --branches dev main
```

- Ожидаемый результат: код возврата **`exit 0`**, статус `[OK]` для обеих веток с `checks=[drain-macos, lint-types-test]`.
- Дополнительные флаги: `--json` (машиночитаемый отчёт), `--repo owner/name`, `--required-checks ...`, таймаут задаётся через `GH_API_TIMEOUT_S` (по умолчанию `15` с).

## 2. Локальный `pre-commit` и воспроизводимый запуск тестов

Зависимости закреплены в [`pyproject.toml`](../pyproject.toml) (Python `>=3.13`, секции `dependencies` и `optional-dependencies.dev`).

```bash
# 1. Установка зависимостей из pyproject.toml (как в CI)
python -m pip install --upgrade pip
python -c "import pathlib, subprocess, sys, tomllib; p = tomllib.loads(pathlib.Path('pyproject.toml').read_text(encoding='utf-8'))['project']; deps = [*p.get('dependencies', []), *p.get('optional-dependencies', {}).get('dev', [])]; subprocess.check_call([sys.executable, '-m', 'pip', 'install', *deps])"

# 2. Установка и ручной прогон pre-commit (хуки ruff-check и drain-contract-tests)
python -m pip install pre-commit
pre-commit install
pre-commit run --all-files
```

Полный воспроизводимый прогон проверок, идентичный CI:

```bash
python -m ruff check .
python -m basedpyright
python -m pytest -q

# Набор drain-macos (drain, lifecycle, launchd plist, multi-step restart, stream drain)
python -m pytest \
  tests/test_drain_policy.py \
  tests/test_drain_contract_http.py \
  tests/test_drain_launchd_consistency.py \
  tests/test_drain_multistep_restart.py \
  tests/test_graceful_shutdown_drain.py \
  tests/test_subbridge_graceful_drain.py \
  tests/test_subbridge_lifecycle.py \
  tests/test_stream_drain_finish_reason.py -q

# Проверка kill-switch политики drain
BRIDGE_DRAIN_POLICY_ENABLED=0 python -m pytest tests/test_drain_contract_http.py -q -k kill_switch
```

## 3. Операционный runbook: синхронизация `launchd` `ExitTimeOut` на macOS (`RISK-001`)

### Почему возникает drift (`RISK-001`)

В шаблоне [`deploy/launchd/com.user.dsh-hub.plist`](../deploy/launchd/com.user.dsh-hub.plist) заданы `ExitTimeOut=180` и `EnvironmentVariables.BRIDGE_EXIT_TIMEOUT_S=180`. На живом macOS-хосте `launchd` кеширует определение агента из `~/Library/LaunchAgents/com.user.dsh-hub.plist` в момент загрузки. После `git pull` или перезапуска процесса без `bootout`/`bootstrap` активный юнит может оставаться со старым `exit timeout = 60`.

При таком drift `HubLifecycleManager` (дефолт `BRIDGE_DRAIN_TIMEOUT_S=110s`) не успеет завершить graceful drain за 60 секунд, и `launchd` принудительно убьёт процесс по `SIGKILL`, оборвав активные стримы.

Проверка фактического значения на хосте:

```bash
launchctl print "gui/$(id -u)/com.user.dsh-hub" | grep -i "exit timeout"
```

### Временные меры до перезагрузки LaunchAgent

1. **Ограничение бюджета drain под текущий `launchd` (`exit timeout = 60`):**
   добавьте в `~/.dsh/.env` (подхватывается `start.sh`, если переменная не задана в загруженном plist) или в окружение процесса:
   ```bash
   BRIDGE_EXIT_TIMEOUT_S=60
   ```
   Ядро `core/drain_policy.py` автоматически ограничит эффективный таймаут drain по формуле `ExitTimeOut - tail(7s) - margin(5s) = 48s`, исключив `SIGKILL` на 60-й секунде.
2. **Аварийный kill-switch политики drain/Retry-After:**
   ```bash
   BRIDGE_DRAIN_POLICY_ENABLED=0
   ```
   Отключает новую политику drain/Retry-After и возвращает legacy-поведение без отката кода.

### Безопасная перезагрузка LaunchAgent администратором после merge

Выполнять в окно обслуживания (вызывает штатный graceful drain и перезапуск `com.user.dsh-hub`):

```bash
# 1. Развернуть шаблон plist в ~/Library/LaunchAgents с подстановкой __HOME__ -> $HOME
sed "s|__HOME__|$HOME|g" deploy/launchd/com.user.dsh-hub.plist \
  > ~/Library/LaunchAgents/com.user.dsh-hub.plist
plutil -lint ~/Library/LaunchAgents/com.user.dsh-hub.plist

# 2. Выгрузить старое определение и загрузить обновлённый LaunchAgent
launchctl bootout "gui/$(id -u)" ~/Library/LaunchAgents/com.user.dsh-hub.plist || true
launchctl bootstrap "gui/$(id -u)" ~/Library/LaunchAgents/com.user.dsh-hub.plist

# 3. Подтвердить синхронизацию ExitTimeOut=180
launchctl print "gui/$(id -u)/com.user.dsh-hub" | grep -i "exit timeout"
```

После подтверждения `exit timeout = 180` удалите временный override `BRIDGE_EXIT_TIMEOUT_S=60` из `~/.dsh/.env` (если он выставлялся).
