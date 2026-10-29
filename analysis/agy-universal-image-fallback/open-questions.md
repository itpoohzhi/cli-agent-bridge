# Реестр вопросов

Все исследовательские вопросы RESOLVED. Незакрытых: 0. «Решено» означает найденный факт или явно установленную границу исследования, а не production-приёмку.

OPEN-01 | БЛОКЕР | RESOLVED: где безопасные точки downgrade? | снято: F-118/F-121/F-124, pre-collection и post-slot и ранний hot continue | аналитик | учесть три пути и constructor failure | допущений нет
OPEN-02 | БЛОКЕР | RESOLVED: возможно ли сохранить строгие тесты? | снято: F-202/F-203/F-205/F-212, отдельный policy absent=false и explicit production true совместимы | аналитик | выбор имени и реализации остаётся архитектору | нет implicit test detection
OPEN-03 | БЛОКЕР | RESOLVED: universal уже включён в production? | снято: F-301/F-302/F-307, нет fallback key и нет config sync | аналитик | downstream обязан активировать deployed config | включение сейчас не выполнялось
OPEN-04 | БЛОКЕР | RESOLVED: как проверяется пакет? | снято: summary.md содержит фактический протокол SA-DOD и воспроизводимости | аналитик | formal DoD не является live acceptance | реализация вне Stage 1
OPEN-05 | МОЖНО ПРОДОЛЖИТЬ | RESOLVED: как понимать требование HTTP200? | F-125/F-126/F-130 доказывают независимые backend/auth/protocol failures; owner задал fallback на media failure | архитектор/QA | успешный text turn даёт200; второй сбой сохраняет truthful error | ASSUMP-01 явно ограничен media admission
OPEN-06 | МОЖНО ПРОДОЛЖИТЬ | RESOLVED: 44 теста и прежние verifier IDs совпадают? | F-214/F-315: 46 methods и40 IDs; сохранять весь baseline и оба verifier | QA | неполный список не заменяет полный suite | числа уточнены доказательством
OPEN-07 | МОЖНО ПРОДОЛЖИТЬ | RESOLVED: нужен ли полный pixel decoder? | F-107/F-217: нет в as-is; valid raster обязан пройти, strict fixture нельзя ломать | архитектор | отдельный security/resource вопрос decoder без изменения strict path | ASSUMP-02 не считать magic пиксельным proof
OPEN-08 | МОЖНО ПРОДОЛЖИТЬ | RESOLVED: известны ли production RPS/SLA и квоты upstream? | в предоставленных исходниках и config нет контрактных квот/RPS/p99; HL-ENV ниже фиксирует unknown | владелец release/архитектор | throughput/SLA acceptance ограничен до замеров и квот | никаких числовых SLA не предполагается
