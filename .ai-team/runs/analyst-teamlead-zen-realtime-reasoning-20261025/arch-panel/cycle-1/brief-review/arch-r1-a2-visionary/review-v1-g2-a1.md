{
  "items": [
    {"id": "BR-48", "evidence_quote": "Если работа этой роли меняет Git-репозиторий, перед сдачей обязательно прочитать и\nвыполнить `~/Мой диск/skils/ai-sdlc/references/remote-mr-workflow.md`. Локальный\nmerge не считается влитием: сначала merge MR на remote, затем fast-forward\nлокальной target-ветки.", "status": "covered", "fix": ""}
  ],
  "unmapped_requirements": [
    {"source": "/tmp/cel-runs/zen-realtime-reasoning-20261025/goal.md", "quote": "Проведена живая проверка тяжёлым путём на реальном мосту и DSH.", "fix": "Добавить строку BR-чек-листа по критерию приёмки владельца №3 (живая проверка тяжёлым путём)."},
    {"source": "/tmp/cel-runs/zen-realtime-reasoning-20261025/goal.md", "quote": "размышления (`reasoning_content` / блок `Think`) и прогресс шагов стримятся в реалтайме по мере генерации", "fix": "Добавить строку BR-чек-листа по критерию приёмки №1 (реалтайм-стриминг reasoning и шагов)."},
    {"source": "analysis/zen-realtime-reasoning/handoff-architect.md", "quote": "Дельты размышления и текста уходят клиенту по мере прихода из апстрима, а не в конце шага", "fix": "Добавить BR-строку для REQ-001 (AC-001, AC-002)."},
    {"source": "analysis/zen-realtime-reasoning/handoff-architect.md", "quote": "Публичный контракт не меняется", "fix": "Добавить BR-строку для REQ-002 (AC-003)."},
    {"source": "analysis/zen-realtime-reasoning/handoff-architect.md", "quote": "Прежний путь `opencode run --format json` остаётся рабочим как переключаемый запасной вариант и kill-switch", "fix": "Добавить BR-строку для REQ-003 (AC-004)."},
    {"source": "analysis/zen-realtime-reasoning/handoff-architect.md", "quote": "Первая видимая реакция моста в течение 1.0 с после открытия SSE", "fix": "Добавить BR-строку для REQ-004 (AC-005)."},
    {"source": "analysis/zen-realtime-reasoning/handoff-architect.md", "quote": "Статусные строки моста отделены от текста модели", "fix": "Добавить BR-строку для REQ-005 (AC-006, AC-007)."},
    {"source": "analysis/zen-realtime-reasoning/handoff-architect.md", "quote": "Watchdog первого события", "fix": "Добавить BR-строку для REQ-006 (AC-008)."},
    {"source": "analysis/zen-realtime-reasoning/handoff-architect.md", "quote": "Watchdog первого токена (reasoning или text, допущение 60 с) и watchdog паузы между чанками (допущение 60 с)", "fix": "Добавить BR-строку для REQ-007 (AC-009, AC-010)."},
    {"source": "analysis/zen-realtime-reasoning/handoff-architect.md", "quote": "Отсутствие осиротевших процессов", "fix": "Добавить BR-строку для REQ-008 (AC-011, AC-012)."},
    {"source": "analysis/zen-realtime-reasoning/handoff-architect.md", "quote": "Потолок `MAX_TOTAL_SPAWNS=3`", "fix": "Добавить BR-строку для REQ-009 (AC-013, AC-014)."},
    {"source": "analysis/zen-realtime-reasoning/handoff-architect.md", "quote": "`ToolCallParser` на потоковых дельтах", "fix": "Добавить BR-строку для REQ-010 (AC-015)."},
    {"source": "analysis/zen-realtime-reasoning/handoff-architect.md", "quote": "Завершение шага с вызовом инструмента останавливает процесс или сессию", "fix": "Добавить BR-строку для REQ-011 (AC-016)."},
    {"source": "analysis/zen-realtime-reasoning/handoff-architect.md", "quote": "Встроенные инструменты `opencode` на новом транспорте запрещены", "fix": "Добавить BR-строку для REQ-012 (AC-017)."},
    {"source": "analysis/zen-realtime-reasoning/handoff-architect.md", "quote": "Ротация чистых IP на каждый новый запуск", "fix": "Добавить BR-строку для REQ-013 (AC-018)."},
    {"source": "analysis/zen-realtime-reasoning/handoff-architect.md", "quote": "`usage` собирается из токенов завершения шага нового транспорта", "fix": "Добавить BR-строку для REQ-014 (AC-019)."},
    {"source": "analysis/zen-realtime-reasoning/handoff-architect.md", "quote": "Секреты не пишутся в логи и артефакты", "fix": "Добавить BR-строку для REQ-015 (AC-020)."},
    {"source": "analysis/zen-realtime-reasoning/handoff-architect.md", "quote": "Наблюдаемость `O-EXIT/v1`", "fix": "Добавить BR-строку для REQ-016 (AC-021)."},
    {"source": "analysis/zen-realtime-reasoning/handoff-architect.md", "quote": "Базовая линия тестов приводится в зелёное", "fix": "Добавить BR-строку для REQ-017 (AC-022, AC-023)."},
    {"source": "analysis/zen-realtime-reasoning/handoff-architect.md", "quote": "Прямой Google-маршрут (`_stream_google_sse`, `_execute_google_once`) не затрагивается", "fix": "Добавить BR-строку для REQ-018 (AC-024)."},
    {"source": "analysis/zen-realtime-reasoning/handoff-architect.md", "quote": "Развёрнутая копия `~/.dsh/bridges/opencode-zen-bridge/server.py` синхронизируется с репозиторием", "fix": "Добавить BR-строку для REQ-019 (AC-025)."},
    {"source": "analysis/zen-realtime-reasoning/handoff-architect.md", "quote": "В набор тестов добавляется измерение реального времени прихода чанков на клиентском сокете", "fix": "Добавить BR-строку для REQ-020 (AC-026)."},
    {"source": "analysis/zen-realtime-reasoning/handoff-architect.md", "quote": "Изменение чужих файлов репозитория вне `bridges/opencode-zen-bridge/` и тестов этого моста.", "fix": "Добавить BR-строку для границы Forbidden Scope и Non-Goals."}
  ],
  "bloat_flags": [],
  "leakage_flags": [],
  "verdict": "REJECT"
}
