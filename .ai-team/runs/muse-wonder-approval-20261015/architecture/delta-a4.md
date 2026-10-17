# Delta a4 — архитектурные контракты F-001(a3), F-002(a3)

Статус: архитектурная переработка выполнена; структурный approved validator проверяется отдельным gate ниже. Новая архитектурная панель a4 PENDING. Это не panel verdict, не закрытие исходного ledger и не сдача runtime.

| Находка | Изменение | Проверка (будущая реализация Coder) |
|---|---|---|
| F-001(a3), owner-blocking | Request-wide APPROVAL_SEEN до receipt в setup; ACTION_POSSIBLE до approval/allowing decide/turn-start, запрет любого нового serve/exec в обеих retry_scope и для context retry | VER-001/002, T-A16/T-R11: setup approval → decide → эффект → transient до turn/start; один процесс/эффект/исход |
| F-002(a3), owner-blocking | D всего запроса=t0+min(TIMEOUT_S,1800); E=D−35; W=D−12, локальный L=min(s+3,W); все N кадров/flush/паузы/lock/keepalive/join до W, независимое закрытие W и cleanup D | VER-002/003, T-L09/T-R12: slow-steady N кадров каждый <3 с, сумма >W; закрытие W, смерть/слот D либо карантин, no retry/late DONE; контроль полного успеха малого N |

Нормативные подробности и red→green oracle: `delta-a4.contracts.md` и §9 `arch-spec.md`. Точные команды: `uv run --no-project --with pytest python -m pytest -q tests/test_muse_bridge_killpg.py -k 'Approval or TransientRetry'`; `uv run --no-project --with pytest python -m pytest -q tests/test_muse_bridge_killpg.py -k 'LiveReasoning or TransientRetry'`.

Новые тесты НЕ созданы/НЕ запускались. Они заморожены как контракты Coder: сначала red на a3, затем green. Структурные validators не доказывают runtime.

## Цена и assumptions

ASM-013 (continuable): REQUEST_CAP_S=1800 и CLOSE_RESERVE_S=12 — выбранные обратимые budgets по известным default1800/client1900/cleanup5+5+2 (EVD-013/016/026), не новый измеренный NFR. Около E на финальную выдачу максимум 23 с до других затрат. Доставка произвольного N не обещается: даже читающий клиент получит усечение по W без позднего успешного DONE. Общий deadline прекращает вывод и no retry независимо от content_started. При неподтверждённой смерти к D слот карантин, ложный свободный слот запрещён. Закрытие ASM — T-L09/T-R12, loopback slow-reader и VER-009 на живой рабочей сессии, число/размер кадров и длительность финала. Числа не выданы за факты измерения.

## Nonblocking r18

Места 1/2: FINDINGS_COMPLETE: 0, самостоятельных nonblocking F нет. Приняты текстовые remarks о строгой pre-action области и её цене, двух слотах/очереди, внешнем upstream, стоимости детерминированных time/lock тестов. Queue-writer и prewarmed pool остаются альтернативами: основания менять архитектуру при двух слотах отсутствуют. Их исторические утверждения о достаточности 35 с/3 с не считаются доказательством N-кадровой выдачи — заменены W/D и ASM-013. Исторический r18 PASS не присвоен новой панели.

## Неизменность и границы handoff

AD-001 и AD-005, delta_a2 и delta_a3 сохранены JSON-значениями; прежние решения RW-001/002/003 не пересматриваются, a4 уточняет крайние ветки RW-001/002. Исходный a3 ledger не менялся и не закрыт. Внешний API, sandbox, --disable-write --disable-shell и REQ-MUSE-001 400000/320000/200000 сохранены. independent_review S2 остаётся NOT_REQUIRED; отдельный mandatory architecture-panel a4 PENDING. Coder, продуктовые правки, MR, панель и материализация ADR этим исполнителем не запускались.

ПРОВЕРЕНО ЛЁГКИМ: JSON invariants, hashes, роль-план и структурные validators (вывод ниже).
ПРОВЕРЕНО ТЯЖЁЛЫМ: нет; архитектурная роль, runtime read-only.
НЕ ПРОВЕРЕНО: будущие regression tests/Coder red→green, loopback slow-reader, живой ход владельца, материализация нового ADR, ARCH_GATE/новая панель a4.

## Механические diffs и hashes

- `architecture-packet.a3.json` SHA256 `38f4662021162360c22138888a86cc2d2156faba7b61ee95cda18468c952754c` → `architecture-packet.json` SHA256 `9ddc18254368aa868db6bdff1df2fcb91426f87bc6c4fe90fd7be90f73b830c6`; полный diff: `delta-a4.packet.diff`, SHA256 `6326e4c5f6222003c3f8a8694bab249b45bed34cb7da42821af36db5f616f428`.
- `arch-spec.a3.md` SHA256 `d7034e48dfff640e4d2e3d77dc3a458ae3cdcfebad197b8a21fc0ad85db4311a` → `arch-spec.md` SHA256 `1b66622035d122d2cf18c80df0ff54c3285830158478580ddd9942218429b8af`; полный diff: `delta-a4.spec.diff`, SHA256 `5a0443bf6bcb482d60e733a98d100a5571ed2bd1a66580946fd089f1c2e88fc4`.
- `0003-adr.a3.md` SHA256 `721ba63d70a47d85bde9d364c48703273fae9fe43d41c7c57613aacef1b90b24` → `proposals/docs/adr/0003-muse-serve-approval-allowall.md` SHA256 `0dd71c8e22761021ead29643acb05d2fa7d602d92f0248769889dc4e1755d25d`; полный diff: `delta-a4.adr.diff`, SHA256 `26131941a231a6e02ad7de25ddeff4c68204a48b124dd520caab5a26d53a0761`.

Parent architect-03.json SHA256 `2a305b66a592611de9f2c9103513c1989384bb595078d8e6b30d8bb4b454f3fb`; closed architect-04.json SHA256 `ed8fa4d4d9b5eea7b7db0c18576f94faf643e378f72e25d4b30a4920d2f57a41`, совпадает packet.role_plan.

Материализованный продуктовый ADR остался SHA256 `721ba63d70a47d85bde9d364c48703273fae9fe43d41c7c57613aacef1b90b24`; новый proposal SHA256 `0dd71c8e22761021ead29643acb05d2fa7d602d92f0248769889dc4e1755d25d`; target тот же, отдельная exact-bytes операция оркестратора после gate.

## Фактические validators

Before: PASS exit=0 (SHA planned `86be833d843c4b1863c9844940ac322ccf68fc73a346a2639306628acd123423`). Промежуточные schema diagnostic FAIL и исправления записаны в `receipts/architect-04-validation.log`; corrected draft PASS. Финально:

- PASS: architect role plan is valid for after; sha256=ed8fa4d4d9b5eea7b7db0c18576f94faf643e378f72e25d4b30a4920d2f57a41; exit=0
- PASS: architecture packet is valid for approved; sha256=9ddc18254368aa868db6bdff1df2fcb91426f87bc6c4fe90fd7be90f73b830c6; exit=0

Полный inventory файлов/sha256: `../receipts/architect-04-files.sha256` (self-hash отдельно в handoff).
