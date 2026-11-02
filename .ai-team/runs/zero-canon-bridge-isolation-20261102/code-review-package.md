# Teamlead Council Code Review Package — `zero-canon-bridge-isolation-20261102` (Cycle 2)

## 1. Задача и бизнес-контекст (Task Envelope)
- **Цель:** Внедрение системной изоляции под-мостов и блокировки канонических хуков (Zero-Canon Architecture) по итогам утверждения владельцем решений аналитической панели (`analyst-panel-zero-env-report.md`).
- **Бизнес-контекст:**
  - Устранить неконтролируемое чтение канонов (`AGENTS.md`, `CLAUDE.md`, `agents-global.md`), отнимающих до 13 000–30 000 входных токенов на каждом запросе к под-мостам (`claude-p-bridge`, `agy-bridge`).
  - Обеспечить исполнение субагентов с чистым окружением (Zero-Environment), где контекст формируется исключительно через бриф задачи, выжимая максимальную скорость и устраняя ритуальный шум ("прочитал канон...").
  - Сохранить 100% работоспособность авторизации CLI: доступ к Keychain, gcloud/jetski OAuth, pem-сертификатам и прокси-переменным.

## 2. Реализация замечаний коллегии судей (F-001, F-002)
1. **F-001 (BLOCKER-SAFETY — Race condition O_TRUNC и права 0700/0600 в claude-p-bridge):**
   - Устранена гонка параллельной записи: в `bridges/claude-p-bridge/server.py` добавлена потокобезопасная однократная инициализация под `threading.Lock()` (`_CLAUDE_HOME_LOCK`) с флагом `_CLAUDE_HOME_INITIALIZED`.
   - Каталог `claude_dir` создаётся с правами `0700`.
   - Копирование файлов профиля (`settings.json`, pem-сертификаты, файлы политик) производится через атомарную запись во временный файл с правами `0600` и вызовом `os.replace()` (POSIX atomic rename).
   - Дочерний процесс `claude` изолирован в `WORKSPACE/runtime/claude-home` с `BRIDGE_ZERO_CANON=1`, без доступа к `agents-global.md` и `CLAUDE.md`.
2. **F-002 (BLOCKER-OPINION — Устранение мёртвого кода в agy-bridge):**
   - Неиспользуемая функция `_prepare_agy_home()` (64 строки), признанная судьями опасной для целостности сессий/транскриптов и не вызывавшаяся в коде, полностью удалена из `bridges/agy-bridge/server.py`.
   - Утверждение по `agy-bridge` сужено до строго доказанного: передача `env["BRIDGE_ZERO_CANON"] = "1"` в `_launch_env()`, что на 100% надёжно глушит PreInvocation-хук `inject-agents-canon.py` без вмешательства в OAuth и Go-рантайм `agy.real`.
3. **P2 (Блокировка канонического PreInvocation хука):**
   - В `~/.gemini/config/hooks/inject-agents-canon.py` внедрена проверка флага `BRIDGE_ZERO_CANON == "1"`, возвращающая `{}` (exit 0) до чтения канонических файлов.

## 3. Candidate Manifest
```json
{
  "role": "Coder",
  "model": "gpt-6.1-sol",
  "effort": "high",
  "transport": "native:9882",
  "work_dir": "/tmp/worktree-zero-canon",
  "branch": "feat/zero-canon-isolation",
  "base_commit": "f96f883f36098ee3144a1e94441584ea0bc6b840",
  "head_commit": "0cd99f6b955743b23e8006e12e12814b62057d39",
  "patch": {
    "path": ".ai-team/runs/zero-canon-bridge-isolation-20261102/coder.diff",
    "sha256": "1215b456b9c8cb4d7b4aebcbf1fd28fccf022a3c36fc3b583d25c6b8c33b1393"
  },
  "files": [
    {
      "path": "bridges/agy-bridge/server.py",
      "sha256": "0f7ff884b0693e10c8fe7921c656336dd2570088c06b89fe139764b6434ca5bb"
    },
    {
      "path": "bridges/claude-p-bridge/server.py",
      "sha256": "e4fbc8e506761dbca840aae9abc6448be8b01e5dbeb87aac5982f266e5d2ade5"
    }
  ]
}
```

## 4. Верификация (Heavy Path + Unit Suite)
- **Unit Tests:**
  - `pytest tests/test_claude_bridge.py tests/test_bridges_speedup_resilience.py`: 92 passed in 9.15s (100% green).
  - `ruff check bridges/agy-bridge/server.py bridges/claude-p-bridge/server.py`: All checks passed.
- **Heavy Path Live Verification:**
  - Живой запрос к `claude-sonnet-5-5` через хаб :9882: чистый мгновенный ответ 'PONG' без чтения канона и без гонок.
  - Health check `agy-bridge` (порт 9887): `{"ok": true, ...}`.
