"""Политика удержания горячей сессии при транзиентном сбое (AD-004, BND-001).

Сохранять можно только немутированную сессию: `NETWORK_TRANSIENT`, `turns == 0` и
`conversation == "-"`. Любой мутированный ход (шаги идут, есть conversation_id)
инвалидируется как в базе: повтор по мутированному conversation не идемпотентен.
"""

from __future__ import annotations

from core.transport_failure_contracts import FailureKind, HotSessionDecision, HotSessionFacts

NO_CONVERSATION = "-"


def should_retain_hot_session(facts: HotSessionFacts) -> HotSessionDecision:
    """Retain iff сбой транзиентный и сессия не мутирована; иначе invalidate с причиной."""
    if facts.kind is not FailureKind.NETWORK_TRANSIENT:
        return HotSessionDecision(False, "not_network_transient")
    if type(facts.turns) is not int or facts.turns != 0:
        return HotSessionDecision(False, "session_mutated_turns")
    if facts.conversation != NO_CONVERSATION:
        return HotSessionDecision(False, "session_mutated_conversation")
    return HotSessionDecision(True, "transient_untouched_session")
