PANEL-NONCE: 2a5472681c63596e
ARTIFACT-SHA256: 5ea11245c3546b12f1de9c303b0ace2ae267e271d264f328fe4565e904c024a9

Прочитал общий канон `~/Мой диск/Context/AGENTS.md` целиком (до `<!-- КАНОН-КОНЕЦ -->`) и проектные правила `AGENTS.md` (`cli-agent-bridge`).

## Архитектурная оценка (шляпа: ВИЗИОНЕР, раунд R1)

Решение в [`server.py`](file:///Users/aazhiry1/work/src/cli-agent-bridge/bridges/opencode-zen-bridge/server.py) и [`test_bridges_speedup_resilience.py`](file:///Users/aazhiry1/work/src/cli-agent-bridge/tests/test_bridges_speedup_resilience.py) чисто и минимально инвазивно разделяет монолитный дедлайн на три ортогональные фазы жизненного цикла генерации (`TTFT`, `Idle`, `Total`), сохраняя обратную совместимость (`_zen_execution_timeout` и фолбэк в `_attempts_t0` для тестовых заглушек без `t0`). Все инварианты конфигурируемости через переменные окружения и контракты ошибок соблюдены.

Ниже — две неблокирующие рекомендации для долгосрочной системной гармонии и расширяемости.

### F-001 NON_BLOCKING — Неявная связанность предиката целевой политики с числовым значением `TTFT`
- **Доказательство:** [`bridges/opencode-zen-bridge/server.py:367-381`](file:///Users/aazhiry1/work/src/cli-agent-bridge/bridges/opencode-zen-bridge/server.py#L367-L381), [`bridges/opencode-zen-bridge/server.py:7073`](file:///Users/aazhiry1/work/src/cli-agent-bridge/bridges/opencode-zen-bridge/server.py#L7073)
- **Суть:** Функции `_zen_idle_timeout` (`server.py:369`), `_zen_total_timeout` (`server.py:376`) и флаг `self._zen_targeted` (`server.py:7073`) определяют принадлежность запроса к целевой группе через условие `_zen_ttft_timeout(model, prompt) >= TIMEOUT_S`. Если в эксплуатации потребуется поднять `BRIDGE_ZEN_TTFT_TIMEOUT_S` до уровня `TIMEOUT_S`, сохранив жёсткий `BRIDGE_ZEN_IDLE_TIMEOUT_S=15`, проверка `>= TIMEOUT_S` неявно отключит и `idle_timeout`. Выделение явного предиката `_is_zen_timeout_targeted(model, prompt) -> bool` (или единого датакласса `ZenTimeoutPolicy(targeted, ttft_s, idle_s, total_s)`) сделает оси `TTFT`, `Idle` и `Total` полностью независимыми.

### F-002 NON_BLOCKING — Дублирование проверки `TTFT`/`Idle` в двух контурах исполнения и неточный лог при срабатывании `split_timeout`
- **Доказательство:** [`bridges/opencode-zen-bridge/server.py:4825-4834`](file:///Users/aazhiry1/work/src/cli-agent-bridge/bridges/opencode-zen-bridge/server.py#L4825-L4834), [`bridges/opencode-zen-bridge/server.py:8351-8367`](file:///Users/aazhiry1/work/src/cli-agent-bridge/bridges/opencode-zen-bridge/server.py#L8351-L8367), [`bridges/opencode-zen-bridge/server.py:8599-8601`](file:///Users/aazhiry1/work/src/cli-agent-bridge/bridges/opencode-zen-bridge/server.py#L8599-L8601)
- **Суть:** Логика сопоставления `(first_token_at, last_token_at)` с `(ttft_timeout, idle_timeout)` продублирована в `_serve_one_attempt` и в потоковом `watchdog`. Кроме того, при отсечке по `split_timeout[0]` в `server.py:8601` в лог выводится `f"stream timeout after {TIMEOUT_S:.0f}s, killing proc group"`, хотя реальная отсечка произошла по `ttft_timeout` (25с) или `idle_timeout` (15с). В следующих итерациях стоит вынести проверку фазового дедлайна в единый хелпер, возвращающий причину (`"ttft_timeout"` / `"idle_timeout"`), чтобы унифицировать оба контура и диагностику в логах.

VERDICT: ACCEPT
