# Handoff-пакет для Архитектора: Модернизация cli-agent-bridge

## 1. Контекст и решаемая проблема (REQ-001, REQ-002, REQ-003)
1. **REQ-001 — Устранение ошибки 503 в DeepSeek Harness (REQ003_SIZE_EXCEEDED):**
   При отправке запросов в модель `muse-wonder-full-1.0` через хаб `:9882` клиенты DSH получают отказ `503 launcher_unavailable: instruction guard is unsafe (block=63262 limit=60000)` [F-18, F-24].
   Канон `~/Мой диск/Context/AGENTS.md` содержит 39 784 символа, но из-за UTF-8 кодировки кириллицы занимает 62 889 байт [F-16, F-17]. В `tools/b_guard.py` зашит жесткий лимит `BLOCK_LIMIT = 60000` [F-20], что нарушает правило 4 `AGENTS.md` (запрет хардкода параметров).
2. **REQ-002 — Консолидация моделей и мостов на едином хабе (:9882):**
   Исторически разные провайдеры запускались на отдельных портах (`agy-bridge` :9887, `muse-bridge` :9886, `opencode-zen-bridge` :9883, `claude-p-bridge` :9881) [F-12..F-15, F-40]. Хаб `cli-agent-bridge` на порту :9882 спроектирован как универсальный шлюз, способный маршрутизировать все CLI-бэкенды через единый порт :9882 через архитектуру `BackendAdapter` и `PassthroughAdapter` [F-01..F-07, F-45].
3. **REQ-003 — Полный выпил остаточных артефактов Factory Droid:**
   Пользователь выводит Droid из эксплуатации и не продлевает подписку. Необходимо устранить зависимость и очистить остаточные имена (`DROID_DSH_BRIDGE_*`, `FACTORY_API_KEY`) [F-37, F-42], обеспечив при этом обратную совместимость через каскадные алиасы `BRIDGE_*` [F-43, F-44].

## 2. Архитектурные драйверы (Architecture Drivers)
- **AD-01 (Zero-Hardcode & Dynamic Limits):** Все лимиты сторожа инструкций (`BLOCK_LIMIT`, `INSTR_BLOCK_LIMIT`, `MARGIN_MIN`) считываются из переменных окружения (`BRIDGE_INSTR_LIMIT`, дефолт 120 000 байт) с клампингом и безопасным fallback [F-20, F-21, F-28].
- **AD-02 (Multi-Backend Hub Routing):** Единый фасад `:9882` маршрутизирует запросы к `muse`, `zen`, `codex`, `claude`, `agy` на основе каталога `fleet.json` и `adapters/` [F-01..F-07, F-45].
- **AD-03 (Droid Decoupling & Neutral Naming):** Переменные окружения и скрипты запуска переводятся на канонический префикс `BRIDGE_*` с сохранением `DROID_*` в качестве fallback-алиасов [F-43].
- **AD-04 (Highload & Resilience):** Изоляция сессий, таймауты и семафоры соединений по контрактам ядра `cli-agent-bridge` [F-02, F-08].

## 3. Маппинг фактов (Evidence Ledger Mapping)
- `REQ-001` (b_guard 503 fix): опирается на факты `[F-16]`..`[F-30]`.
- `REQ-002` (консолидация хаба): опирается на факты `[F-01]`..`[F-15]`, `[F-31]`..`[F-36]`, `[F-45]`.
- `REQ-003` (выпил Droid): опирается на факты `[F-37]`..`[F-44]`.

## 4. Открытые вопросы (Open Questions)
- `OPEN-01` [МОЖНО ПРОДОЛЖИТЬ]: Сохранение портов standalone-мостов для безопасного перехода [F-40].
- `OPEN-02` [МОЖНО ПРОДОЛЖИТЬ]: Поддержка двойного чтения переменных `BRIDGE_*` / `DROID_*` [F-43].

## 5. Границы системы и контракты
- **Hot-Path (`HOTPATH_MODULES`):** HTTP-обработчик `POST /v1/chat/completions`, проверка `InstructionGuard`, SSE-стриминг `reasoning_content` и `content`.
- **Cold-Path:** Парсинг профилей DSH (`find_profiles`), периодический фоновый тик сторожа (`GUARD_TICK_S`), чтение конфигурации.

## 6. Таблица HL-ENV/v1 и конверт Highload & Resilience
| Поле HL-ENV/v1 | Значение | Источник |
|---|---|---|
| P_steady | 1 | server.py single daemon process |
| P_hpa_max | 1 | local macOS launchd service |
| maxSurge_pct | 0 | local single-instance service |
| maxSurge_abs | 0 | local single-instance service |
| maxUnavailable_pct | 0 | local single-instance service |
| maxUnavailable_abs | 0 | local single-instance service |
| P_terminating_overlap | 0 | local single-instance service |
| P_live | 1 | local single-instance service |
| P_avail_min | 1 | local single-instance service |
| W | 4 | admission worker concurrency |
| N_proc | 1 | local single-instance service |
| N_proc_steady | 1 | local single-instance service |
| N_proc_avail_min | 1 | local single-instance service |
| CPU_limit_per_pod | 8 | local host Apple Silicon M-series |
| κ_skew | 1.0 | single host execution |
| u_bg_worker | 0.05 | background guard check CPU load |
| U_pod_sidecars | 0 | no sidecars |
| Mem_limit_per_pod | 16GiB | host physical memory |
| Mem_rss_worker_max | 512MiB | peak python daemon memory |
| Mem_shared_max | 0 | no shared memory pools |
| RPS_peak | 10 | interactive local DSH usage |
| A_max | 4 | max concurrent HTTP turn requests |
| SLA_p99_s | 30.0 | local LLM CLI response turn start |
| N_entities_max | 1000 | max active sessions in memory |
| Limit_dep_share[d] | 1.0 | direct CLI execution |
| Limit_dep_rps[d] | 10 | direct CLI execution |
| W_fetchers[d] | 1 | single worker per backend |
| J_init_s[d] | 0.1 | local subprocess spawn jitter |
| J_pod_s[d] | 0.0 | local subprocess spawn jitter |
| T_poll_s[d] | 0.05 | stdio stream poll interval |
| K_calls[d] | 1 | calls per turn |
| T_base_s[d] | 0.5 | base timeout |
| T_cap_s[d] | 600.0 | turn timeout ceiling |
| Max_stale_age_s[c] | 300.0 | cache validity age |
| Min_healthy_ratio | 1.0 | single local process |
| B_retry_max | 1 | max retries on transient errors |
| min_reserve_retry_rps | 0.1 | retry capacity |
| FD_worker | 64 | file descriptors ceiling |
| ulimit_n | 10240 | host ulimit |
| λ_new_conn_per_pod(s) | 2 | connection rate |
| C_active_in_scope(s) | 4 | active connections |
| N_pods_in_scope(s) | 1 | local host |
| Port_range_size(s) | 1 | port 9882 |
| T_hold_s(s) | 15.0 | keepalive timeout |
| SNAT_ips_count(s) | 1 | 127.0.0.1 |
| HOTPATH_MODULES | server.py:Handler.do_POST, core.tool_emulation | hot path entry points |
