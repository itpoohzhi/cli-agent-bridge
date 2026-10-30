PRIOR-LEDGER-SHA256: f7df9461edf63585634d9b831c31a5afbd27afe84c0b89b9569fe3ea26ef630b
РАУНД: D1 (анонимизированные дебаты)

{
  "schema_version": "1.0",
  "task_id": "universal-tool-sanitizer-20261030",
  "run_id": "universal-tool-sanitizer-20261030",
  "criticality": "S2",
  "profile": "python-aisdlc-gcge",
  "status": "PROPOSED",
  "delta": "A1",
  "title": "Универсальная нормализация аргументов tool_calls и распаковка parallel в cli-agent-bridge",
  "requirements": [
    {
      "id": "REQ-01",
      "text": "Изоляция от вендорских сред (Vendor Zero-Touch): Никаких модификаций или оверлеев во внешние вендорские приложения (DSH и др.). Все изменения — строго в нашем репозитории cli-agent-bridge на универсальном слое.",
      "source": "Инвариант владельца в AGENTS.md",
      "verification_ids": ["VER-001", "VER-004"]
    },
    {
      "id": "REQ-02",
      "text": "Универсальная санитизация пустых строковых аргументов: Очистка пустых строк (\"\") из необязательных параметров вызова инструментов (provider, model, reasoning_effort, justification и др.) в исходящих tool_calls перед отправкой клиенту.",
      "source": "Session 38008581 rca: Error: child LLM provider must be non-empty",
      "verification_ids": ["VER-002", "VER-003"]
    },
    {
      "id": "REQ-03",
      "text": "Распаковка синтетического инструмента parallel: Вызовы name='parallel' с массивом tool_uses автоматически распаковываются в стандартные независимые ToolCall первого уровня.",
      "source": "Session 38008581 rca: Error: unknown tool parallel",
      "verification_ids": ["VER-002"]
    },
    {
      "id": "REQ-04",
      "text": "Безопасный fallback для justification: При наличии sandbox_permissions и пустом justification подставлять безопасный дефолт, предотвращая ошибку invalid justification.",
      "source": "Session 38008581 rca: Error: invalid justification: expected a non-empty sentence",
      "verification_ids": ["VER-002"]
    },
    {
      "id": "REQ-05",
      "text": "Поддержка non-streaming и SSE streaming: Санитизация работает одинаково корректно в обоих режимах генерации.",
      "source": "Архитектурный контракт server.py",
      "verification_ids": ["VER-003", "VER-005"]
    }
  ],
  "decisions": [
    {
      "id": "AD-001",
      "status": "PROPOSED",
      "kind": "two-way",
      "question": "На каком слое реализовать очистку пустых аргументов и распаковку parallel?",
      "choice": "В модуле core/tool_emulation.py как универсальный чистый конвейер sanitize_tool_call / sanitize_tool_calls_list, не зависящий от конкретного бэкенда или клиента.",
      "alternatives": [
        "A: В core/tool_emulation.py (выбрано: централизованно, переиспользуемо всеми бэкендами и фасадом)",
        "B: В отдельных адаптерах бэкендов (дублирование логики между droid, muse, codex)",
        "C: Через патчинг клиентского DSH (запрещено владельцем)"
      ],
      "drivers": ["REQ-01", "REQ-02", "REQ-03", "Инвариант AGENTS.md"],
      "consequences": ["Все исходящие вызовы инструментов автоматически санитизируются до попадания к клиенту"],
      "verification_ids": ["VER-002"]
    },
    {
      "id": "AD-002",
      "status": "PROPOSED",
      "kind": "two-way",
      "question": "Как интегрировать санитизацию в фасад server.py?",
      "choice": "Применять sanitize_tool_calls_list в ChatCompletionResponse перед сериализацией JSON, а также в потоковом цикле SSE перед отправкой финальных дельт tool_calls.",
      "alternatives": [
        "A: Фасадный хук на сериализации ответа (выбрано)",
        "B: Модификация входящих запросов (не решает проблему генерации модели)"
      ],
      "drivers": ["REQ-05"],
      "consequences": ["Клиент гарантированно получает валидный OpenAI-совместимый JSON без пустых опциональных строк"],
      "verification_ids": ["VER-003", "VER-005"]
    },
    {
      "id": "AD-003",
      "status": "PROPOSED",
      "kind": "one-way",
      "question": "Политика модификации вендорских компонентов (DSH, Claude Code, Cursor)?",
      "choice": "Zero-Touch: внешний софт не модифицируется, файлы ~/.dsh, app.asar и чужие профили остаются нетронутыми.",
      "alternatives": [
        "A: Zero-Touch (выбрано)",
        "B: Overlay в ~/.dsh (отклонено владельцем)"
      ],
      "drivers": ["REQ-01", "Принцип независимости от вендоров в AGENTS.md"],
      "consequences": ["Обновления DSH или смена клиента больше не ломают работоспособность решения"],
      "verification_ids": ["VER-001", "VER-004"]
    }
  ],
  "risks": [
    {
      "id": "RISK-001",
      "scenario": "Инструмент легитимно ожидает пустую строку в качестве валидного аргумента.",
      "probability": "LOW",
      "impact": "MEDIUM",
      "mitigation": "Удалять пустые строки только если поле не входит в required-схему инструмента, либо является известным опциональным параметром (provider, model, reasoning_effort, justification)."
    }
  ]
}


НАХОДКИ К ДЕБАТАМ (авторы и модели скрыты):
- RW-001 [BLOCKER-OPINION]: RW-001 BLOCKER-OPINION — Необязательность поля не означает допустимость удаления пустого значения
- RW-002 [BLOCKER-OPINION]: RW-002 BLOCKER-OPINION — Предложенный хук не охватывает все пути SSE и повторной доставки
- RW-003 [BLOCKER-OPINION]: RW-003 BLOCKER-OPINION — Контракт распаковки parallel допускает неоднозначную интерпретацию
- RW-004 [BLOCKER-OPINION]: RW-004 BLOCKER-OPINION — Ссылки VER-001…VER-005 не имеют определений проверок
- RW-005 [BLOCKER-OPINION]: RW-005 BLOCKER-OPINION — Отсутствует обязательный механизм выключения нового поведения
- RW-006 [BLOCKER-OPINION]: RW-006 BLOCKER-OPINION — Безопасность fallback justification заявлена без определённой политики

По каждой находке — ровно одна позиция одной строкой:
AGREE RW-NNN — проверил: <file:line> — что увидел сам
DISPUTE RW-NNN — контр-evidence: <file:line> — почему неверно
AMEND RW-NNN — priority=<...>; fix=<...> — причина: <file:line> (не более одной правки)
REFUTE RW-NNN COUNTER-EVIDENCE: <проверяемое контр-доказательство> — только так
закрывается BLOCKER-SAFETY; большинством и переклассификацией он не снимается.
Первыми двумя строками ответа повтори PANEL-NONCE и ARTIFACT-SHA256 из конца брифа.
Последняя непустая строка ответа — VERDICT: ACCEPT | PASS | NEEDS WORK | RED FLAG.


---
PANEL-NONCE: 2739386984ccc2d4
ARTIFACT-SHA256: aae42c18b3702cd397ed5c32b69459bb31e2e4b22276fe4611ff823d522a7146
Инструкция судье: первыми двумя строками ответа повтори дословно «PANEL-NONCE: 2739386984ccc2d4» и «ARTIFACT-SHA256: aae42c18b3702cd397ed5c32b69459bb31e2e4b22276fe4611ff823d522a7146».
