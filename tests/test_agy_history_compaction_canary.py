"""W0: red-repro потери контекста legacy pruning и золотые фикстуры legacy.

Группа ``red_repro`` фиксирует согласованный дефект cold replay на base-коде:
при переполнении бюджета 96 КиБ legacy head-pruning теряет ранний факт
пользователя и бесследно отбрасывает пару tool-call/tool-result. На base
эти тесты обязаны падать с ``AssertionError`` (VER-001); зелёными их делает
компакция при ``AGY_HISTORY_COMPACTION_ENABLED=true`` (волна W3, VER-004).

Группа ``legacy_equivalence`` закрепляет побайровый эталон legacy-выхода
(SHA-256 и длину UTF-8) при выключенном флаге компакции (VER-003): эталон
снят на base-коде и обязан совпадать после волн W1-W2 при ``false``.
"""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
_AGY_DIR = str(_ROOT / "bridges/agy-bridge")
if _AGY_DIR not in sys.path:
    sys.path.append(_AGY_DIR)

_CANARY = "CANARY_FACT_ALPHA_7391"
_CODENAME = "LARCH-7391"
_PAIR_ID = "call_pair_42"
_LIMIT_BYTES = 98304
_TOOL_BODY_CHARS = 4200
_FLAG_ENV = "AGY_HISTORY_COMPACTION_ENABLED"


def _load_agy_server() -> ModuleType:
    cached = sys.modules.get("agy_srv_canary_w0")
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(
        "agy_srv_canary_w0", _ROOT / "bridges/agy-bridge/server.py"
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod.__name__] = mod
    spec.loader.exec_module(mod)
    return mod


def _pin_env(monkeypatch: pytest.MonkeyPatch, compaction: str | None) -> ModuleType:
    """Зафиксировать бюджет и флаг компакции; вернуть модуль моста."""
    monkeypatch.setenv("AGY_BRIDGE_MAX_PROMPT_BYTES", str(_LIMIT_BYTES))
    monkeypatch.setenv("AGY_BRIDGE_MAX_PROMPT_BYTES_CAP", str(_LIMIT_BYTES))
    monkeypatch.setenv("AGY_TRUNCATION_NOTICE_ENABLED", "false")
    if compaction is None:
        monkeypatch.delenv(_FLAG_ENV, raising=False)
    else:
        monkeypatch.setenv(_FLAG_ENV, compaction)
    srv = _load_agy_server()
    monkeypatch.setattr(srv, "AGY_BRIDGE_ENABLE_HEAD_PRUNING", True)
    return srv


def _tool_turn(index: int) -> list[dict[str, object]]:
    call_id = "call_%02d" % index
    return [
        {"role": "user", "content": "step %d: read chunk %d" % (index, index)},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": call_id,
                    "type": "function",
                    "function": {
                        "name": "read_chunk",
                        "arguments": '{"chunk_id": %d}' % index,
                    },
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": call_id,
            "content": "result-%02d-" % index + "x" * _TOOL_BODY_CHARS,
        },
    ]


def _system_block() -> dict[str, object]:
    return {
        "role": "system",
        "content": "You are a test assistant. Follow the conversation.",
    }


def _canary_history() -> list[dict[str, object]]:
    """Канарейка в первом user-сообщении + 32 хода крупных tool-результатов."""
    messages: list[dict[str, object]] = [
        _system_block(),
        {
            "role": "user",
            "content": "Remember this fact: %s project codename is %s."
            % (_CANARY, _CODENAME),
        },
    ]
    for index in range(32):
        messages.extend(_tool_turn(index))
    messages.append(
        {
            "role": "user",
            "content": "What is the project codename from the first message?",
        }
    )
    return messages


def _pair_history() -> list[dict[str, object]]:
    """Ранняя пара call_pair_42 + 32 хода, переполняющих бюджет 96 КиБ."""
    messages: list[dict[str, object]] = [
        _system_block(),
        {"role": "user", "content": "start the paired tool scenario"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": _PAIR_ID,
                    "type": "function",
                    "function": {
                        "name": "lookup_pair",
                        "arguments": '{"key": "pair-42"}',
                    },
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": _PAIR_ID,
            "content": "PAIR_RESULT_42 value=quokka-42 " + "y" * 2000,
        },
    ]
    for index in range(32):
        messages.extend(_tool_turn(index))
    messages.append({"role": "user", "content": "Report the paired lookup value."})
    return messages


def _huge_user_history() -> list[dict[str, object]]:
    """Один якорный user-блок сверх лимита: путь _middle_prune_text."""
    return [
        _system_block(),
        {"role": "user", "content": "HUGE-HEAD " + "a" * 150000 + " HUGE-TAIL"},
    ]


def _huge_tool_history() -> list[dict[str, object]]:
    """Активный tool-результат сверх лимита с юникодом и экранированием JSON."""
    return [
        _system_block(),
        {"role": "user", "content": "dump the file"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_dump",
                    "type": "function",
                    "function": {"name": "dump", "arguments": "{}"},
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "call_dump",
            "content": 'строка "q" \\n ' * 12000,
        },
    ]


def _golden_history(name: str) -> list[dict[str, object]]:
    builders = {
        "canary_drop": _canary_history,
        "huge_user": _huge_user_history,
        "huge_tool": _huge_tool_history,
    }
    return builders[name]()


def test_red_repro_early_canary_preserved_under_compaction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    srv = _pin_env(monkeypatch, "true")
    prompt = srv._messages_to_prompt(_canary_history())
    assert srv._ndjson_bytes(prompt) <= _LIMIT_BYTES
    assert _CANARY in prompt, "compaction lost the early canary fact"
    assert _CODENAME in prompt, "compaction lost the canary key-value"


def test_red_repro_tool_pair_not_split_under_compaction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    srv = _pin_env(monkeypatch, "true")
    prompt = srv._messages_to_prompt(_pair_history())
    assert srv._ndjson_bytes(prompt) <= _LIMIT_BYTES
    has_call = "[tool call %s]" % _PAIR_ID in prompt
    has_result = "[tool result %s]" % _PAIR_ID in prompt
    assert has_call == has_result, "tool pair %s was split" % _PAIR_ID
    if not has_call:
        # Пара целиком ушла в дайджест: идентификатор вызова обязан остаться
        # в структурированной сводке (AD-001), а не только слепой маркер.
        assert _PAIR_ID in prompt, "digest does not mention digested tool call"
        assert prompt.strip() != srv.HISTORY_PRUNED_MARKER


# name -> (sha256 UTF-8 промпта, длина UTF-8 в байтах, атрибут маркера модуля).
_GOLDEN = {
    "canary_drop": (
        "9c8e61af733fac5f998deefd07ad2321bf6230dca7442831bc6f1df61345de01",
        96018,
        "HISTORY_PRUNED_MARKER",
    ),
    "huge_user": (
        "d04c7dc760a71a22f80a646590c29310d8619477c918682e736c70e92b8131bc",
        98208,
        "MIDDLE_PRUNED_MARKER",
    ),
    "huge_tool": (
        "94257c06bfeb620546ad8a40b7c510489e9402772e0745f0193bfa3d55f75d7e",
        85437,
        "MIDDLE_PRUNED_MARKER",
    ),
}


@pytest.mark.parametrize("fixture_name", sorted(_GOLDEN))
@pytest.mark.parametrize("compaction", [None, "false"], ids=["unset", "false"])
def test_legacy_equivalence_golden_prompt_bytes(
    monkeypatch: pytest.MonkeyPatch, fixture_name: str, compaction: str | None
) -> None:
    srv = _pin_env(monkeypatch, compaction)
    prompt = srv._messages_to_prompt(_golden_history(fixture_name))
    raw = prompt.encode("utf-8")
    expected_sha256, expected_bytes, marker_attr = _GOLDEN[fixture_name]
    assert len(raw) == expected_bytes
    assert hashlib.sha256(raw).hexdigest() == expected_sha256
    assert srv._ndjson_bytes(prompt) <= _LIMIT_BYTES
    assert getattr(srv, marker_attr) in prompt


def _pin_compaction(
    monkeypatch: pytest.MonkeyPatch, limit: int, notice: bool = True
) -> ModuleType:
    monkeypatch.setenv("AGY_BRIDGE_MAX_PROMPT_BYTES", str(limit))
    monkeypatch.setenv("AGY_BRIDGE_MAX_PROMPT_BYTES_CAP", str(limit))
    monkeypatch.setenv(_FLAG_ENV, "true")
    monkeypatch.setenv("AGY_TRUNCATION_NOTICE_ENABLED", str(notice).lower())
    srv = _load_agy_server()
    monkeypatch.setattr(srv, "AGY_BRIDGE_ENABLE_HEAD_PRUNING", True)
    return srv


def _sized_multiline(head: str, size: int, fill: str = "x") -> str:
    prefix = head + "\n"
    return prefix + fill * (size - len(prefix.encode("utf-8")))


def test_session_3a8cf9f1_first_turn_user_body_survives(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    limit = 72850
    srv = _pin_compaction(monkeypatch, limit)
    approval = "The user approved the bash command.".ljust(124)
    real_user = _sized_multiline("REAL_USER_TURN_1\nline two", 6000, "u")
    skill_catalog = _sized_multiline("<system-reminder>skill catalog", 7000, "s")
    skill_catalog = skill_catalog[:-len("</system-reminder>")] + "</system-reminder>"
    messages = [
        {"role": "system", "content": "S" * 65000},
        {"role": "user", "content": approval},
        {"role": "user", "content": real_user},
        {"role": "user", "content": "# AGENTS.md\nFollow repository instructions."},
        {
            "role": "user",
            "content": "Current runtime context. This snapshot supersedes earlier "
            "runtime-context snapshots.",
        },
        {"role": "user", "content": skill_catalog},
    ]
    assert len(messages) == 6 and len(approval.encode()) == 124
    prompt = srv._messages_to_prompt(messages)
    assert real_user in prompt
    assert srv._ndjson_bytes(prompt) <= limit


def test_digest_transition_keeps_first_real_user_anchor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import agy_runtime.history_compaction_domain as domain

    srv = _pin_compaction(monkeypatch, 12000)
    anchor = _sized_multiline("REAL_USER_TURN_1_ANCHOR", 3000, "a")
    blocks = [
        (0, "system", "### 0. system\nsystem"),
        (
            1,
            "user",
            "### 1. user\n[model changed: assistant turns above this point were "
            "generated by old; the session continues with new]",
        ),
        (2, "user", "### 2. user\n" + anchor),
    ]
    assert srv._is_synthetic_user_block(blocks[1][2])
    blocks.extend(
        (index, "assistant", f"### {index}. assistant\nold block " + "x" * 200)
        for index in range(3, 406)
    )
    calls = 0
    original = domain._compact_digest

    def counted(*args: object) -> str:
        nonlocal calls
        calls += 1
        return original(*args)  # type: ignore[arg-type]

    monkeypatch.setattr(domain, "_compact_digest", counted)
    prompt = srv._prune_or_compact(blocks, "", 12000)
    assert calls > 0 and "[сжатая история ходов " in prompt
    assert anchor in prompt
    assert srv._ndjson_bytes(prompt) <= 12000


def test_multi_turn_users_survive_synthetic_tail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    limit = 20000
    srv = _pin_compaction(monkeypatch, limit)
    first_user = _sized_multiline("REAL_USER_TURN_1", 4000, "f")
    current_user = _sized_multiline("REAL_USER_TURN_K", 4000, "k")
    messages: list[dict[str, object]] = [
        {"role": "system", "content": "system " + "s" * 1000},
        {"role": "user", "content": first_user},
        {"role": "assistant", "content": "acknowledged"},
    ]
    messages.extend(
        {"role": "assistant", "content": f"historic {i} " + "h" * 150}
        for i in range(200)
    )
    messages.extend(
        [
            {"role": "user", "content": current_user},
            {
                "role": "user",
                "content": "<system-reminder>" + "r" * 25000 + "</system-reminder>",
            },
            {
                "role": "user",
                "content": "[model changed: assistant turns above this point were "
                "generated by old; the session continues with new]",
            },
        ]
    )
    prompt = srv._messages_to_prompt(messages)
    assert first_user in prompt and current_user in prompt
    assert srv._ndjson_bytes(prompt) <= limit


def test_notice_reprune_keeps_anchor_and_stable_prefix_hash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    srv = _pin_compaction(monkeypatch, limit := 16384)
    anchor = _sized_multiline("REAL_USER_TURN_1_NOTICE", 5000, "n")
    logs: list[str] = []
    monkeypatch.setattr(srv, "_log", logs.append)
    messages = [
        {"role": "system", "content": "system"},
        {"role": "user", "content": anchor},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_large",
                    "type": "function",
                    "function": {"name": "read", "arguments": "{}"},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call_large", "content": "t" * 50000},
    ]
    prompt = srv._messages_to_prompt(messages)
    hashes = [
        field.split("=", 1)[1]
        for line in logs
        for field in line.split()
        if field.startswith("prompt_prefix_sha256=")
    ]
    budgets = [
        int(field.split("=", 1)[1])
        for line in logs
        for field in line.split()
        if field.startswith("limit=")
    ]
    assert "[truncation-notice]" in prompt and anchor in prompt
    assert len(hashes) >= 2 and len(set(hashes)) == 1
    assert max(budgets) - min(budgets) == 276
    assert srv._ndjson_bytes(prompt) <= limit
