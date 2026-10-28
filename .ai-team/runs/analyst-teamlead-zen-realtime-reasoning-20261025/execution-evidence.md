# L3 — выкатка :9883 и тяжёлая проверка H0..H9

Начало: 2026-10-28T00:02:06.241890+00:00; завершение: 2026-10-28T00:05:36.159021+00:00.
Итог: **FAIL_ROLLED_BACK**.

## Допуск
PANEL PROOF: ~/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/panel/council/r266/panel-proof.json sha256=0f8b685cac3b1e65ee06bced04b90690d61ee5efc840c809a8a8ce6b8cac56e7 verify_panel_proof exit=0.
ACCEPT — существующий итоговый консенсус-леджер teamlead/final-panel-verdict.md, решение владельца 2026-10-28 02:51 MSK.

## H0–H9
### H0: PASS
```json
{
  "status": "PASS",
  "backups": [
    {
      "source": "~/.dsh/bridges/opencode-zen-bridge/server.py",
      "backup": "~/work/backups/opencode-zen-bridge-20261028/server.py.bak-20261028",
      "existed": true,
      "sha256": "538ba1948bbd87c6bba806dd37b42106c9654544966a9ce8927973c979b3b36f"
    },
    {
      "source": "~/.dsh/bridges/opencode-zen-bridge/dynamic_config.json",
      "existed": false
    },
    {
      "source": "~/.dsh/bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py",
      "existed": false
    },
    {
      "source": "~/.dsh/bridges/opencode-zen-bridge/tests/test_step_interruption.py",
      "backup": "~/work/backups/opencode-zen-bridge-20261028/test_step_interruption.py.bak-20261028",
      "existed": true,
      "sha256": "afd542fed0722e48989c997c31595772a5c2df194a6c47ae6c1e86935bb2aa6e"
    }
  ],
  "at": "2026-10-28T00:02:06.318831+00:00"
}
```

### H1: PASS
```json
{
  "status": "PASS",
  "synced": [
    {
      "source": "~/tmp/cli-agent-bridge/zen-realtime-reasoning/bridges/opencode-zen-bridge/server.py",
      "deployed": "~/.dsh/bridges/opencode-zen-bridge/server.py",
      "sha256": "7eef6ac552863d8e4c499296fdcbf5165e4bd89e70ef084398852051669226bb",
      "diff_rc": 0
    },
    {
      "source": "~/tmp/cli-agent-bridge/zen-realtime-reasoning/bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py",
      "deployed": "~/.dsh/bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py",
      "sha256": "408bc144512f8acaf5d87a32d210175fda778cd61096e0eb7d073a2f06b05c97",
      "diff_rc": 0
    },
    {
      "source": "~/tmp/cli-agent-bridge/zen-realtime-reasoning/bridges/opencode-zen-bridge/tests/test_step_interruption.py",
      "deployed": "~/.dsh/bridges/opencode-zen-bridge/tests/test_step_interruption.py",
      "sha256": "2b177a32290adfebeffad700b1c3c3251619e83cba90032217576c777beb80ef",
      "diff_rc": 0
    }
  ],
  "dynamic_config": {
    "path": "~/.dsh/bridges/opencode-zen-bridge/dynamic_config.json",
    "sha256": "a59f4df8c878ef24c5f42b6b573667dc6fbffcabb3e550a58a1048f05b1c72d8",
    "enabled_flags": {
      "OPENCODE_ZEN_REALTIME_REASONING_ENABLED": true,
      "REALTIME_SERVE_ENABLED": true
    }
  },
  "repo_dynamic_config_absent": true,
  "at": "2026-10-28T00:02:06.335871+00:00"
}
```

### H2: PASS
```json
{
  "status": "PASS",
  "health": {
    "http_status": 200,
    "ok": true,
    "transport": "opencode-zen-cli",
    "models": [
      "beam-free",
      "big-pickle",
      "deepseek-v4.1-flash-free",
      "flint-40b-free",
      "glm-5.3-flash-free",
      "mimo-v2.6-flash-free",
      "nemotron-3.5-lightning-free",
      "nemotron-3.5-super-vl-free"
    ],
    "default_model": "deepseek-v4.1-flash-free",
    "catalog_mode": "dynamic",
    "catalog_source": "file",
    "active": 0,
    "max_concurrent": 6,
    "stream": true,
    "tool_emulation": true,
    "uptime_s": 71
  },
  "lsof": "COMMAND   PID     USER   FD   TYPE             DEVICE SIZE/OFF NODE NAME\nPython  14166 aazhiry1    4u  IPv4 0x44865c081f2f10cf      0t0  TCP 127.0.0.1:9883 (LISTEN)\n",
  "at": "2026-10-28T00:03:26.541235+00:00"
}
```

### H3: FAIL
```json
{
  "status": "FAIL",
  "headers_ms": null
}
```

### H4: FAIL
```json
{
  "status": "FAIL",
  "ttfr_ms": null,
  "reasoning_chunks_count": null
}
```

### H5: FAIL
```json
{
  "status": "FAIL",
  "ttft_ms": null
}
```

### H6: FAIL
```json
{
  "status": "FAIL",
  "finish_reason": null,
  "usage": null,
  "done": null
}
```

### H7: PASS
```json
{
  "status": "PASS",
  "http_status": 200,
  "total_ms": 20220.86,
  "usage": {
    "prompt_tokens": 18485,
    "completion_tokens": 1016,
    "total_tokens": 19501,
    "cached_tokens": 4096,
    "prompt_tokens_details": {
      "cached_tokens": 4096
    },
    "completion_tokens_details": {
      "reasoning_tokens": 1951
    }
  }
}
```

### H8: FAIL
```json
{
  "status": "FAIL",
  "request_count": 5,
  "requests_passed": 1,
  "early_disconnect_ms": null,
  "final_health": {
    "http_status": 200,
    "ok": true,
    "transport": "opencode-zen-cli",
    "models": [
      "beam-free",
      "big-pickle",
      "deepseek-v4.1-flash-free",
      "flint-40b-free",
      "glm-5.3-flash-free",
      "mimo-v2.6-flash-free",
      "nemotron-3.5-lightning-free",
      "nemotron-3.5-super-vl-free"
    ],
    "default_model": "deepseek-v4.1-flash-free",
    "catalog_mode": "dynamic",
    "catalog_source": "file",
    "active": 0,
    "max_concurrent": 6,
    "stream": true,
    "tool_emulation": true,
    "uptime_s": 106
  },
  "new_opencode_processes": [],
  "structured_o_exit": true,
  "o_exit_count": 7,
  "client_gone_logged": true,
  "log_path": "~/.dsh/bridges/opencode-zen-bridge/logs/bridge.log",
  "log_offset_start": 3210031,
  "at": "2026-10-28T00:04:01.845912+00:00"
}
```

### H9: PASS
```json
{
  "status": "PASS",
  "receipt_path": "~/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l3-heavy-verification.json",
  "execution_evidence_path": "~/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/execution-evidence.md",
  "at": "2026-10-28T00:04:01.845939+00:00"
}
```

## Особенности выкатки
- Указанный в брифе ключ OPENCODE_ZEN_REALTIME_REASONING_ENABLED не читается кодом. В live dynamic_config.json сохранены оба ключа; действующий REALTIME_SERVE_ENABLED=true. Репозиторный dynamic_config.json отсутствует.
- /health возвращает ok:true (не status:ok).
- Бэкап server.py и существующего теста сохранён; исходный dynamic_config.json отсутствовал.

## Живые запросы
```json
{
  "name": "single-sse",
  "status": "FAIL",
  "total_ms": 19.879
}
```
```json
{
  "name": "single-json",
  "status": "PASS",
  "http_status": 200,
  "headers_ms": 20220.717,
  "usage": {
    "prompt_tokens": 18485,
    "completion_tokens": 1016,
    "total_tokens": 19501,
    "cached_tokens": 4096,
    "prompt_tokens_details": {
      "cached_tokens": 4096
    },
    "completion_tokens_details": {
      "reasoning_tokens": 1951
    }
  },
  "valid_usage": true,
  "total_ms": 20220.86
}
```

## O-EXIT/v1
```
2026-10-28 03:03:26 O-EXIT/v1 mode=stream model=deepseek-v4.1-flash-free status=0 exit_reason=client_gone rc=None total_spawns=0 retries=0 signal=0 tools=0 out_chars=0 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=0.00
2026-10-28 03:03:46 O-EXIT/v1 mode=json model=deepseek-v4.1-flash-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=2451 transport=serve first_event_ms=895 ttft_ms=3583 transport_history=['serve'] duration_s=20.22
2026-10-28 03:03:46 O-EXIT/v1 mode=stream model=deepseek-v4.1-flash-free status=0 exit_reason=client_gone rc=None total_spawns=0 retries=0 signal=0 tools=0 out_chars=0 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=0.00
2026-10-28 03:03:46 O-EXIT/v1 mode=stream model=deepseek-v4.1-flash-free status=0 exit_reason=client_gone rc=None total_spawns=0 retries=0 signal=0 tools=0 out_chars=0 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=0.00
2026-10-28 03:03:46 O-EXIT/v1 mode=stream model=deepseek-v4.1-flash-free status=0 exit_reason=client_gone rc=None total_spawns=0 retries=0 signal=0 tools=0 out_chars=0 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=0.00
2026-10-28 03:03:46 O-EXIT/v1 mode=stream model=deepseek-v4.1-flash-free status=0 exit_reason=client_gone rc=None total_spawns=0 retries=0 signal=0 tools=0 out_chars=0 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=0.00
2026-10-28 03:04:01 O-EXIT/v1 mode=json model=deepseek-v4.1-flash-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=1665 transport=serve first_event_ms=894 ttft_ms=2816 transport_history=['serve'] duration_s=14.93
```

## Ограничения
Проверены реальные запросы к развернутому мосту, включая 5 одновременных запросов и ранний обрыв. DSH Desktop UI и существующий пользовательский чат в рамках этого брифа не проверялись. Другие модели и выключение флага на живом запросе не проверялись. Результат H0..H9 не подменяет эти проверки.

## Артефакты
Полные метрики, SSE timeline и ответы: ~/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l3-heavy-verification.json.
Фоновый guarded-прогон, по одному файлу на запрос: /tmp/cel-runs/zen-rollout-20261028-0302.

## Откат после провала L3

Развернутая версия нарушила SSE на Python 3.9. По журналу bridge.err: server.py:7171, TypeError: unsupported operand type(s) for |: type and NoneType. start.sh содержит exec /usr/bin/python3 server.py и не изменялся (вне конверта).

Возвращены исходный server.py и test_step_interruption.py; созданные dynamic_config.json и test_realtime_reasoning.py удалены. Хеши каждого объекта и результаты реального SSE после отката — в receipt.rollback.

Итог выкатки: FAIL_ROLLED_BACK. VER-007 был PASS непосредственно после копирования; после защитного отката зеркало ожидаемо отличается, финальный VER-007=FAIL_ROLLED_BACK.

```json
{
  "status": "PASS",
  "reason": "Live SSE failed with TypeError socket.socket | None on Python 3.9; start.sh hardcodes /usr/bin/python3 and is outside rollout file envelope.",
  "restart_rc": 0,
  "at": "2026-10-28T00:04:55.192699+00:00",
  "objects": [
    {
      "path": "~/.dsh/bridges/opencode-zen-bridge/server.py",
      "action": "restored_backup",
      "sha256": "538ba1948bbd87c6bba806dd37b42106c9654544966a9ce8927973c979b3b36f"
    },
    {
      "path": "~/.dsh/bridges/opencode-zen-bridge/dynamic_config.json",
      "action": "removed_created_file",
      "absent": true
    },
    {
      "path": "~/.dsh/bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py",
      "action": "removed_created_file",
      "absent": true
    },
    {
      "path": "~/.dsh/bridges/opencode-zen-bridge/tests/test_step_interruption.py",
      "action": "restored_backup",
      "sha256": "afd542fed0722e48989c997c31595772a5c2df194a6c47ae6c1e86935bb2aa6e"
    }
  ],
  "server_error_evidence": {
    "path": "~/.dsh/bridges/opencode-zen-bridge/logs/bridge.err",
    "exception": "TypeError: unsupported operand type(s) for |: type and NoneType",
    "frame": "server.py:7171"
  },
  "probe": {
    "name": "rollback-sse",
    "model": "deepseek-v4.1-flash-free",
    "reasoning_effort": "high",
    "stream": true,
    "cancel_requested": false,
    "started_at": "2026-10-28T00:05:23.878324+00:00",
    "chunks": [
      {
        "t_ms": 1.505,
        "reasoning_chars": 0,
        "content_chars": 0
      },
      {
        "t_ms": 11877.067,
        "reasoning_chars": 3213,
        "content_chars": 0
      },
      {
        "t_ms": 11877.208,
        "reasoning_chars": 0,
        "content_chars": 1841
      },
      {
        "t_ms": 12201.551,
        "reasoning_chars": 0,
        "content_chars": 0,
        "finish_reason": "stop",
        "usage": {
          "prompt_tokens": 100,
          "completion_tokens": 408,
          "total_tokens": 508
        }
      }
    ],
    "http_status": 200,
    "headers_ms": 1.462,
    "content_type": "text/event-stream; charset=utf-8",
    "reasoning_chunks_count": 1,
    "content_chunks_count": 1,
    "done": true,
    "finish_reason": "stop",
    "usage": {
      "prompt_tokens": 100,
      "completion_tokens": 408,
      "total_tokens": 508
    },
    "ttfr_ms": 11877.067,
    "ttft_ms": 11877.208,
    "finish_ms": 12201.551,
    "usage_ms": 12201.551,
    "done_ms": 12201.598,
    "reasoning_content": "The user asks a planning problem, no tools. But the canon demands a confirmation line that I read the canon... The canon is loaded in full (ends with <!-- КАНОН-КОНЕЦ -->). I must include a confirmation line at the start of the first response. Also JIRA? block — is this a work task? It's a question/computation, not a work artifact. \"Не задача: вопрос, объяснение, статус, консультация\" → block JIRA? not output.\n\nAlso variant check \"rollback-sse\" — probably a distractor / irrelevant token. Ignore or note it.\n\nLet's compute.\n\n3 servers × 10 tasks/s = 30 tasks/s capacity. Arrival 18 tasks/s. Service time 0.08 s.\n\nUtilization before failure: 18/30 = 0.60 = 60%.\nAfter one failure: capacity 20 tasks/s. Traffic remains 18, plus retries +15% → 18 × 1.15 = 20.7 tasks/s. Utilization = 20.7/20 = 1.035 → 103.5% > 100%. Overload.\n\nWithout retries after failure: 18/20 = 0.90 = 90%.\n\nLittle's law: L = λW. Before: 18 × 0.08 = 1.44 concurrent requests. After failure without retries: 18 × 0.08 = 1.44 (same, but service per server capacity 20). With retries: 20.7 × 0.08 = 1.656 — but that's only valid if system stable; at ρ>1 queue grows unbounded, so 1.656 is not achievable steady state — requests in system diverge. Mention that.\n\nThreshold 80%: 0.8 × 20 = 16 tasks/s sustainable. Before: 60% ≤ 80% OK, headroom 20% (6 tasks/s). After, with retries at 20.7: need capacity ≥ 20.7/0.8 = 25.875 tasks/s → ~26 tasks/s. With 2 servers at 20 tasks/s, deficit 5.875 → need 3 servers at... Actually minimum additional capacity: total capacity needed 25.875 tasks/s → additional servers = ceil(25.875/10) - 2 = 3 - 2 = 1 additional server, but adding a server gives 30 total = initial. Hmm, minimal additional capacity in the sense \"how much capacity must be added beyond the 20 tasks/s of remaining servers\": 25.875 - 20 = 5.875 ≈ 5.9 tasks/s, i.e., one server of 10 tasks/s (restoring to 30). That gives 20.7/30 = 69% ≤ 80%, headroom.\n\nAlso mention that with 2 servers at 20 and 80% threshold, max admissible traffic = 16 tasks/s < 20.7 → deficit 4.7 tasks/s even without the 80% margin.\n\nLet's structure 8-12 lines. Include verification: numbers reproducible, e.g. 18×1.15=20.7.\n\nAlso note \"вариант проверки: rollback-sse\" — I should acknowledge it's not a computational parameter; it doesn't change the math. Keep concise.\n\nAlso need the canon confirmation line. Let me write it.\n\nFormat: confirmation line, then the answer 8-12 lines, plus maybe a small table. Table counts as lines... keep compact.\n\nI'll include \"ПРОВЕРЕНО\" block? That's for сдача правок. This is a computation — arguably not needed. I'll skip heavy-path since no changes made. But being safe, I could add a short \"ПРОВЕРЕНО ЛЁГКИМ\" line. Hmm, the second gate applies to \"любой сдаваемой правки\". No edits → not applicable. I'll skip but mention arithmetic check.\n\nLet me write ~11 lines of substance.\n\nCompute exactness: λ=18; C=30; ρ=0.6; after: C'=20; λ'=20.7; ρ'=1.035 (103.5%). Little: L=λW=1.44; L'=1.656 nominal but unstable. 80% target: 0.8·20=16 <20.7. Required C ≥ 20.7/0.8=25.875 ≈26. Add: 25.875−20=5.875≈6 tasks/s → one whole server (10) → ρ=20.7/30=69%, L=1.656, headroom 11%.\n\nVerification line: multiply back 30·0.69=20.7 ✓.\n\nGood.",
    "content": "**Подтверждение канона:** прочитал общий канон `~/Мой диск/Context/AGENTS.md` целиком (до `<!-- КАНОН-КОНЕЦ -->`); проектных файлов правил (`AGENTS.md`, `.agents/AGENTS.md`, `CLAUDE.md`) в рабочей папке `~/.dsh/bridges/opencode-zen-bridge/workspace` нет — файловых правил проекта не читал.\n\nСчитаю без инструментов; «rollback-sse» — метка варианта проверки, в формулы не входит и результат не меняет.\n\n1. **Ёмкость и базовая загрузка.** C = 3 × 10 = 30 задач/с; λ = 18 задач/с; ρ = 18/30 = **0,60 (60%)**.\n2. **После отказа одного сервера.** C′ = 2 × 10 = 20 задач/с; λ′ = 18 × 1,15 = **20,7 задач/с** (18 без повторов = 90%, но с повторами ρ′ = 20,7/20 = **1,035 → 103,5%**).\n3. **Закон Литтла.** L = λ·W. До: 18 × 0,08 = **1,44** одновременных запроса. После: 20,7 × 0,08 = **1,656** — но только как «мгновенная» оценка: при ρ′ > 1 это не стационар, очередь и L растут линейно во времени.\n4. **Порог 80%.** До: 60% ≤ 80% — запас 20 п.п. (6 задач/с до порога). После: допустимо 0,8 × 20 = **16 задач/с**, а приходит 20,7 → дефицит **4,7 задач/с** уже без учёта запаса.\n5. **Минимальная доп. ёмкость.** Нужно C ≥ 20,7/0,8 = **25,875 ≈ 26 задач/с** → добавить 25,875 − 20 = **5,875 ≈ 6 задач/с**, то есть **один сервер (10 задач/с)**.\n6. **Проверка.** С третьим сервером C = 30: ρ = 20,7/30 = **69%** ≤ 80%, запас 11 п.п. (3,3 задачи/с), L = 1,656. Обратно: 30 × 0,69 = 20,7 ✓.\n7. **Итог:** 60% → 103,5% после отказа с повторами; 1,44 → 1,656 (нестабильно); порог 80% нарушен, дефицит 4,7 задач/с; минимум +1 сервер (или +6 задач/с), при этом 69% и запас 11 п.п.\n\nОговорки: W = 0,08 с взято как среднее время обслуживания, модель — M/M/c-подобная без учёта хвостов; при ρ ≥ 1 расчёт L по Литтлу показывает лишь нижнюю границу, реальные задержки и ретраи будут расти (риск ретрай-шторма: 15% — оценка, при таймаутах доля повторов обычно выше).",
    "reasoning_before_content": true,
    "live_progress_first_seconds": false,
    "valid_usage": true,
    "status": "FAIL",
    "total_ms": 12201.615
  },
  "health": {
    "http_status": 200,
    "ok": true,
    "transport": "opencode-zen-cli",
    "models": [
      "beam-free",
      "big-pickle",
      "deepseek-v4.1-flash-free",
      "flint-40b-free",
      "glm-5.3-flash-free",
      "mimo-v2.6-flash-free",
      "nemotron-3.5-lightning-free",
      "nemotron-3.5-super-vl-free"
    ],
    "default_model": "deepseek-v4.1-flash-free",
    "catalog_mode": "dynamic",
    "catalog_source": "file",
    "active": 0,
    "max_concurrent": 6,
    "stream": true,
    "tool_emulation": true,
    "uptime_s": 31
  },
  "opencode_processes": [],
  "sse_content_and_done": true
}
```

## Проверка достоверности квитанции

- Источник Python: `/usr/bin/python3` (Python 3.9.6); минимум проекта `>=3.11`.
- `client_gone` в O-EXIT после TypeError не доказывает запрошенный ранний обрыв. Клиентский таймер 1.5 с не успел сработать; H8 = FAIL.
- После отката старый SSE: HTTP 200, content 1841 символ, finish_reason и [DONE], 12.20 с, active=0, opencode-процессов нет. Старый realtime-оракул ожидаемо FAIL (один буферизованный reasoning chunk); это не приёмка новой функции.
- Источники server.py и обоих тестов не менялись этим прогоном; SHA совпадают с H1.
- Фоном: guarded L3 PID/PGID 29022, rc=1; guarded проверка отката PID/PGID 50321, rc=0.
