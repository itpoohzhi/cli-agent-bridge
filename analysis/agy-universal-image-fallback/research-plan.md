# План исследования

Задача: agy-universal-image-fallback-20261029. Роль: Stage 1 System Analyst.
Глубина: standard, gap-анализ S2; производственный код и боевой контур не меняются.
Цель: воспроизводимые факты о строгом image-gate, безопасном downgrade и совместимости тестов для архитектора и QA.
Критерий: пять артефактов, ноль незакрытых исследовательских вопросов, SA-DOD-001..008 проверены командами; никаких заявлений о реализации или живой приёмке.
Владелец решения: владелец задачи; потребители: архитектор и QA.
Вход: branch feat/agy-universal-image-fallback, HEAD 012da99905ec27a6133afb4f3e768ff9b4426a8f.
Три независимые read-only зоны исполняются параллельно native collaboration explorers; аналитик сводит пакет.

INV-01 | Где гейты и безопасные точки image downgrade? | bridges/agy-bridge/server.py | code inspection runtime_facts | 30 | ledger и runtime handoff | прослежены pre-stage и обе retry-ветви | REQ-01/REQ-03 | closed | F-118 | 10 | проверено по источникам
INV-02 | Как сохранить неизменными строгие тесты? | tests/test_agy_bridge_resilience.py | code inspection test_facts | 30 | ledger и QA handoff | посчитаны тесты и установлены изоляция конфигов и ao10 | REQ-04 | closed | F-203 | 10 | проверено по источникам
INV-03 | Как активируется production и что можно переиспользовать? | fleet.json и dynamic_config.json и sibling bridges и analysis/agy-image-input-fix | inspection config_facts | 30 | ledger и конфигурационные ограничения | установлены реальные defaults и loader и эталон | REQ-01/REQ-05 | closed | F-301 | 10 | проверено по источникам
INV-04 | Полон ли пакет и воспроизводимы ли выводы? | пять аналитических файлов и git | composite DoD и выборочная сверка источников | 30 | summary и протокол проверки | SA-DOD-001..008 и три факта и diff проверены | после INV-01/02/03 | closed | F-403 | 10 | проверено по источникам
