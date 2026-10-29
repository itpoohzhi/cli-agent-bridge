# План исследования: agy image input, Stage 1

Дата: 2026-10-29, Europe/Moscow. Тип: As-Is + gap/feasibility, standard/S2.
Результат: проверяемый входной пакет архитектору и QA; реализация и приёмка продукта сюда не входят.
Владелец вывода: владелец задачи; потребители: Архитектор, QA и родительский analyst-teamlead.
Область: мост agy, его fleet, эталон корневого моста и воспроизведение инцидента.

## Источники и reuse brief

KEEP: предоставленные результаты Explorers A/B/C, логи двух отказов, существующая структура analysis/agy-realtime-reasoning/handoff-architect.md, эталон workspace-read и строгая таксономия C-08..C-11.
CHANGE: исследуем image-вход agy и горячую историю вместо источника reasoning; код не переносится.
BLOCKER для переиспользования структуры отсутствует. Сведения о результатах живого probe принимаются как переданное доказательство с указанными границами; повторный модельный вызов не выполнялся.
План спайков восстановлен из входного брифа до адресной сверки источников. Независимая разведка уже выполнена Explorers A/B/C; в этом Stage 1 переиспользована, а не объявлена новым запуском агентов.

## Спайки

Формат: ID / вопрос / источник / метод / таймбокс в минутах / deliverable / критерий закрытия / зависимости / статус / результат / фактические минуты адресной сверки / отметка. Длительности не включают предшествующую разведку из брифа.

INV-01 | Почему DSH допускает изображения, а мост отвечает 400? | desktop profile + agy server + fleet | адресная сверка кода и профиля / Explorer A reuse | 15 | evidence-ledger + handoff-architect | найден точный путь отказа до spawn | вход для REQ-001 | closed | F-01 | 3 | закрыто источниками
INV-02 | Почему текстовый ход после изображения тоже падает? | история инцидента + scan + resume + fallback | трассировка ветвей / Explorer B reuse | 15 | evidence-ledger + handoff-architect | описаны cold / hot / fallback и сохранение cwd | вход для REQ-004 и REQ-005 | closed | F-07 | 3 | закрыто кодом и переданным инцидентом
INV-03 | Какие валидация, MIME и хранение уже есть в эталоне? | server.py + core/tool_emulation.py + strict tests | сопоставление контрактов C-08..C-11 | 15 | handoff-architect + handoff-qa | перечислены taxonomy / лимиты / нумерация / lifecycle | вход для REQ-002 и REQ-003 | closed | F-14 | 4 | закрыто источниками
INV-04 | Почему reason скрыт и куда поставляется мост? | masking + reject + live logs + launchd | read-only сверка / Explorer C reuse | 15 | evidence-ledger + handoff-qa | установлены log-контракт и отдельная runtime-копия | вход для REQ-007 и REQ-010 | closed | F-22 | 2 | закрыто источниками
INV-05 | Достаточны ли probe и NFR для handoff? | предоставленный probe + architecture SSoT + runtime limits | разграничение доказанного и assumptions | 15 | open-questions + оба handoff | 46 полей брифа и 46 SSoT учтены, пробелы явные | вход для Architecture Packet | closed | F-27 | 4 | исследовательский вопрос закрыт / L3 остаётся downstream

## Выход и контроль

Пять выходов: research-plan.md, evidence-ledger.md, open-questions.md, handoff-architect.md, handoff-qa.md.
Критерий Stage 1: связность фактов, REQ/AC, отсутствие открытых блокеров аналитики, полнота обоих конвертов, SA-DOD-001..008 и ограниченный git scope.
Успех Stage 1 не означает ACCEPT пресета, прохождение ARCH_GATE, исправление инцидента, деплой или L3.
