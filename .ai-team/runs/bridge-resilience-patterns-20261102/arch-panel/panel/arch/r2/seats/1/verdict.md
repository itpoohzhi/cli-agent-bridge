PANEL-NONCE: 52fa8797a546c616
ARTIFACT-SHA256: f11926370796cb83074b1ddfce74de7ba251ee15b25a83a6621cb07ebaee77aa
AGREE RW-001 — проверил: seats/1/brief.md:64 — при выходе без исключения и без записанного исхода вызывается только close(), освобождающий Bulkhead; record_discard() для занятой HALF_OPEN-пробы не вызывается.
AGREE RW-002 — проверил: seats/1/brief.md:68 — любое незаписанное исключение становится failure, включая клиентский ConnectionResetError; нейтральная классификация из ADR не применена в этом пути, поэтому повторные обрывы одного клиента могут открыть общий брейкер.
AGREE RW-003 — проверил: docs/adr/0020-universal-backend-circuit-breaker-bulkhead-and-retries.md:55 — should_retry проверяет доставку ответа, число попыток и transient-ошибку, но не безопасность повторного исполнения; выполненный побочный эффект с потерянным ответом допускает повтор.
AMEND RW-004 — priority=BLOCKER-OPINION; fix=согласовать формулу Bulkhead в пакете с конфигурируемым пределом ADR — причина: seats/1/brief.md:26 задаёт буквальный предел 64, тогда как docs/adr/0020-universal-backend-circuit-breaker-bulkhead-and-retries.md:47 уже использует BRIDGE_BULKHEAD_MAX_PASSTHROUGH; дефект — противоречие контрактов, а не полное отсутствие настройки.
AGREE RW-005 — проверил: seats/1/brief.md:81 — показан только acquire(), без порядка резервирования и отката частичного захвата; при резервировании пробы перед отказом Bulkhead возврат пробы не гарантирован, поскольку lease ещё не передан в with.
VERDICT: NEEDS WORK
