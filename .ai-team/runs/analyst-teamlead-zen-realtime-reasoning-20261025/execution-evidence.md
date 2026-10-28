# L3 — выкатка :9883 и тяжёлая проверка H0..H9

Начало: 2026-10-28T00:28:10.360661+00:00; завершение: 2026-10-28T00:29:16.281399+00:00.
Итог: **PASS**.

## Допуск
Допуск: прямое указание владельца 2026-10-28 02:51 MSK. Архивная panel proof не перепроверялась; PASS ей этим прогоном не присваивается.
Основание продолжения — прямое решение владельца в брифе; панель этим прогоном не оценивалась.

## H0–H9
### H0: PASS
```json
{
  "status": "PASS",
  "backups": [
    {
      "source": "~/.dsh/bridges/opencode-zen-bridge/server.py",
      "backup": "~/work/backups/opencode-zen-bridge-20261028/server.py.bak-20261028",
      "sha256": "538ba1948bbd87c6bba806dd37b42106c9654544966a9ce8927973c979b3b36f",
      "exists": true
    },
    {
      "source": "~/.dsh/bridges/opencode-zen-bridge/dynamic_config.json",
      "exists": false
    },
    {
      "source": "~/.dsh/bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py",
      "exists": false
    },
    {
      "source": "~/.dsh/bridges/opencode-zen-bridge/tests/test_step_interruption.py",
      "backup": "~/work/backups/opencode-zen-bridge-20261028/test_step_interruption.py.bak-20261028",
      "sha256": "afd542fed0722e48989c997c31595772a5c2df194a6c47ae6c1e86935bb2aa6e",
      "exists": true
    }
  ],
  "at": "2026-10-28T00:28:10.361972+00:00"
}
```

### H1: PASS
```json
{
  "status": "PASS",
  "synced": [
    {
      "source": "~/tmp/cli-agent-bridge/zen-realtime-reasoning/bridges/opencode-zen-bridge/server.py",
      "destination": "~/.dsh/bridges/opencode-zen-bridge/server.py",
      "source_sha256": "02f2b8990fb9c961060c9d78f4047bbfed7afcb1c926190f9cb1dc5931ad4a8b",
      "live_sha256": "02f2b8990fb9c961060c9d78f4047bbfed7afcb1c926190f9cb1dc5931ad4a8b",
      "diff_rc": 0
    },
    {
      "source": "~/tmp/cli-agent-bridge/zen-realtime-reasoning/bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py",
      "destination": "~/.dsh/bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py",
      "source_sha256": "0380cfd32922f2279f98a24bd91cf5d98f88782ae9f33778611e1a5ac2845f14",
      "live_sha256": "0380cfd32922f2279f98a24bd91cf5d98f88782ae9f33778611e1a5ac2845f14",
      "diff_rc": 0
    },
    {
      "source": "~/tmp/cli-agent-bridge/zen-realtime-reasoning/bridges/opencode-zen-bridge/tests/test_step_interruption.py",
      "destination": "~/.dsh/bridges/opencode-zen-bridge/tests/test_step_interruption.py",
      "source_sha256": "2b177a32290adfebeffad700b1c3c3251619e83cba90032217576c777beb80ef",
      "live_sha256": "2b177a32290adfebeffad700b1c3c3251619e83cba90032217576c777beb80ef",
      "diff_rc": 0
    }
  ],
  "dynamic_config": {
    "OPENCODE_ZEN_REALTIME_REASONING_ENABLED": true,
    "REALTIME_SERVE_ENABLED": true
  },
  "dynamic_config_path": "~/.dsh/bridges/opencode-zen-bridge/dynamic_config.json",
  "at": "2026-10-28T00:28:10.378327+00:00"
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
    "uptime_s": 2
  },
  "lsof": "COMMAND   PID     USER   FD   TYPE             DEVICE SIZE/OFF NODE NAME\nPython  97564 aazhiry1    4u  IPv4 0x1ae5a4f4df9673c9      0t0  TCP 127.0.0.1:9883 (LISTEN)\n",
  "at": "2026-10-28T00:28:16.741085+00:00"
}
```

### H3: PASS
```json
{
  "status": "PASS",
  "headers_ms": 4.873
}
```

### H4: PASS
```json
{
  "status": "PASS",
  "ttfr_ms": 698.827,
  "reasoning_chunks_count": 48
}
```

### H5: PASS
```json
{
  "status": "PASS",
  "ttft_ms": 11215.731
}
```

### H6: PASS
```json
{
  "status": "PASS",
  "finish_reason": "stop",
  "usage": {
    "prompt_tokens": 18319,
    "completion_tokens": 926,
    "total_tokens": 19245,
    "cached_tokens": 4096,
    "prompt_tokens_details": {
      "cached_tokens": 4096
    },
    "completion_tokens_details": {
      "reasoning_tokens": 1204
    }
  },
  "done": true
}
```

### H7: PASS
```json
{
  "status": "PASS",
  "http_status": 200,
  "total_ms": 30580.835,
  "usage": {
    "prompt_tokens": 18320,
    "completion_tokens": 1691,
    "total_tokens": 20011,
    "cached_tokens": 4096,
    "prompt_tokens_details": {
      "cached_tokens": 4096
    },
    "completion_tokens_details": {
      "reasoning_tokens": 3147
    }
  }
}
```

### H8: PASS
```json
{
  "status": "PASS",
  "request_count": 5,
  "requests_passed": 4,
  "early_disconnect_ms": 1505.063,
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
    "uptime_s": 62
  },
  "new_opencode_processes": [],
  "structured_o_exit": true,
  "o_exit_count": 7,
  "client_gone_logged": true,
  "log_path": "~/.dsh/bridges/opencode-zen-bridge/logs/bridge.log",
  "log_offset_start": 3217508,
  "at": "2026-10-28T00:29:16.281388+00:00"
}
```

### H9: PASS
```json
{
  "status": "PASS",
  "receipt_path": "~/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l3-heavy-verification.json",
  "execution_evidence_path": "~/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/execution-evidence.md",
  "at": "2026-10-28T00:29:16.281410+00:00"
}
```

## Особенности выкатки
- Указанный в брифе ключ OPENCODE_ZEN_REALTIME_REASONING_ENABLED не читается кодом. В live dynamic_config.json сохранены оба ключа; действующий REALTIME_SERVE_ENABLED=true. Репозиторный dynamic_config.json отсутствует.
- /health возвращает ok:true (не status:ok).
- H0 содержит точный список бэкапов и SHA-256. Предыдущие квитанции сохранены в каталоге этого прогона.

## Живые запросы
```json
{
  "name": "single-sse",
  "status": "PASS",
  "http_status": 200,
  "headers_ms": 4.873,
  "ttfr_ms": 698.827,
  "ttft_ms": 11215.731,
  "reasoning_chunks_count": 48,
  "content_chunks_count": 31,
  "finish_reason": "stop",
  "usage": {
    "prompt_tokens": 18319,
    "completion_tokens": 926,
    "total_tokens": 19245,
    "cached_tokens": 4096,
    "prompt_tokens_details": {
      "cached_tokens": 4096
    },
    "completion_tokens_details": {
      "reasoning_tokens": 1204
    }
  },
  "done": true,
  "valid_usage": true,
  "total_ms": 15891.186
}
```
```json
{
  "name": "single-json",
  "status": "PASS",
  "http_status": 200,
  "headers_ms": 30580.65,
  "usage": {
    "prompt_tokens": 18320,
    "completion_tokens": 1691,
    "total_tokens": 20011,
    "cached_tokens": 4096,
    "prompt_tokens_details": {
      "cached_tokens": 4096
    },
    "completion_tokens_details": {
      "reasoning_tokens": 3147
    }
  },
  "valid_usage": true,
  "total_ms": 30580.835
}
```

## O-EXIT/v1
```
2026-10-28 03:28:32 O-EXIT/v1 mode=stream model=deepseek-v4.1-flash-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=2211 transport=serve first_event_ms=1845 ttft_ms=4701 transport_history=['serve'] duration_s=15.89
2026-10-28 03:28:47 O-EXIT/v1 mode=json model=deepseek-v4.1-flash-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=4145 transport=serve first_event_ms=939 ttft_ms=3738 transport_history=['serve'] duration_s=30.58
2026-10-28 03:28:49 O-EXIT/v1 mode=stream model=deepseek-v4.1-flash-free status=200 exit_reason=client_gone rc=None total_spawns=1 retries=0 signal=0 tools=0 out_chars=0 transport=serve first_event_ms=None ttft_ms=None transport_history=['serve'] duration_s=1.98
2026-10-28 03:29:03 O-EXIT/v1 mode=json model=deepseek-v4.1-flash-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=1898 transport=serve first_event_ms=760 ttft_ms=4016 transport_history=['serve'] duration_s=16.40
2026-10-28 03:29:05 O-EXIT/v1 mode=stream model=deepseek-v4.1-flash-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=1600 transport=serve first_event_ms=3792 ttft_ms=5703 transport_history=['serve'] duration_s=18.40
2026-10-28 03:29:14 O-EXIT/v1 mode=stream model=deepseek-v4.1-flash-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=1992 transport=serve first_event_ms=4756 ttft_ms=6812 transport_history=['serve'] duration_s=26.67
2026-10-28 03:29:16 O-EXIT/v1 mode=stream model=deepseek-v4.1-flash-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=1969 transport=serve first_event_ms=2971 ttft_ms=5514 transport_history=['serve'] duration_s=28.81
```

## Ограничения
Проверены реальные запросы к развернутому мосту, включая 5 одновременных запросов и ранний обрыв. DSH Desktop UI и существующий пользовательский чат в рамках этого брифа не проверялись. Другие модели и выключение флага на живом запросе не проверялись. Результат H0..H9 не подменяет эти проверки.

## Артефакты
Полные метрики, SSE timeline и ответы: ~/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l3-heavy-verification.json.
Фоновый guarded-прогон, по одному файлу на запрос: /tmp/cel-runs/zen-rollout-20261028-0328.

## Финальный read-back и целостность

- Guarded rc=0; stderr пуст.
- Повторный /health: active=0; opencode serve/run отсутствуют.
- SHA-256 server.py: 02f2b8990fb9c961060c9d78f4047bbfed7afcb1c926190f9cb1dc5931ad4a8b; все три source SHA неизменны; все mirror diff rc=0.
- Реальный shutdown сокета на 1505.063 мс, O-EXIT client_gone подтверждён.
- Первый reasoning_content (698.827 мс) — явный прогресс моста; всего 48 reasoning-чанков. Прогресс не выдаётся за нативный токен модели.
- VER-006 live SSE/JSON: PASS; VER-007 parallel load/cleanup: PASS.
- Изменены live server.py, tests/test_realtime_reasoning.py, tests/test_step_interruption.py и dynamic_config.json; точные пути и SHA — в H1 квитанции.
- Исходники bridges/ и analysis/ этим исполнителем не менялись; git commit/push/PR этим исполнителем не выполнялись.
