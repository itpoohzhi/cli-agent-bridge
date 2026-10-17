# Findings Ledger: Code Council R1

### F-001
- origin: skeptic · R1 · F-001
- rev: 1
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: r1
- votes: R1 skeptic=AUTHOR realist=AGREE visionary=AGREE
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> В bridges/muse-bridge/server.py:941 поиск результатов идёт по всей оставшейся истории. Первый вызов с id=call_0 поглощает результаты обоих эпизодов; второй assistant затем исключается из-за consumed_tools. Последний вызов и его результат теряются при прунинге. Связывать результаты с конкретным эпизодом вызова assistant.

### F-002
- origin: skeptic · R1 · F-002
- rev: 1
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: r1
- votes: R1 skeptic=AUTHOR realist=AGREE visionary=AGREE
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> В bridges/muse-bridge/server.py:289 сообщение ошибки усекается до 160 символов до проверки hard threshold. Маркер после длинного префикса удаляется и retry не запускается. Признак hard threshold извлекать до усечения ошибки.

### F-003
- origin: skeptic · R1 · F-003
- rev: 1
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: r1
- votes: R1 skeptic=AUTHOR realist=AGREE visionary=AGREE
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> В bridges/muse-bridge/server.py:232 сначала редактируется секрет, затем ищутся исходные части промпта. Сопоставление с исходным промптом ломается. Обеспечить корректное удаление отражённого промпта даже при наличии отредактированных ключей.

### F-004
- origin: skeptic · R1 · F-004
- rev: 1
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: r1
- votes: R1 skeptic=AUTHOR realist=AGREE visionary=AGREE
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> В bridges/muse-bridge/server.py:2267 fallback журналирует ServeUnavailable до удаления отражённого промпта. Очистить логирование на этой границе или исключить тело сообщения из лога.

### F-005
- origin: visionary · R1 · visionary-01
- rev: 1
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- resolved_in: r1
- votes: R1 visionary=AUTHOR realist=AGREE skeptic=AGREE
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> Алгоритм отбора Фазы C квадратичен O(n^2) при повторной сборке промпта на каждом шаге. Рекомендуется предвычислять размеры единиц O(n), чтобы исключить задержки на длинных историях.

### F-006
- origin: visionary · R1 · visionary-02
- rev: 1
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- resolved_in: r1
- votes: R1 visionary=AUTHOR realist=AGREE skeptic=AGREE
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> Развести консервативный оценщик бюджета прунинга и метрику usage.prompt_tokens, чтобы не завышать числа токенов для клиента.
