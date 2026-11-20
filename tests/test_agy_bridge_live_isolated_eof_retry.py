"""Live-Isolated E2E (W3-A, Гейт 3): `userinfo: EOF` после keepalive-коммита — невидимый повтор.

Реальный процесс `server.py` (копия кода во временном каталоге, `HOME=<tmp>`, свободный порт,
отдельный PGID) + стаб `agy`: спавн 0 — stall дольше `precommit_flush_s` и EOF (rc=1), спавн 1 —
успех. Порты живого контура и `~/.dsh`, `~/.config/*`, launchd не затрагиваются.
"""

from __future__ import annotations

from pathlib import Path

from live_isolated_harness import ALL_OFF, ALL_ON, API_KEY, running


def test_eof_after_keepalive_commit_is_retried_invisibly(tmp_path: Path) -> None:
    """Флаги вкл.: 2 спавна, HTTP 200, без error-chunk, один [DONE], сессия горячая, 0 утечек."""
    with running(tmp_path, "eof_then_ok", ALL_ON) as bridge:
        result = bridge.chat(chat_id="chat-a")
        spawns, health, log = bridge.spawn_count(), bridge.get("/health")[1], bridge.log_text()
    assert result.status == 200 and spawns == 2
    assert result.errors == [] and result.done_count == 1
    assert "Готово" in "".join(str(v) for v in result.delta_values("content"))
    assert ": keepalive" in result.raw  # коммит SSE действительно был до повтора
    assert "transient failure state=agy_error" in log and "turn-resolved" in log
    assert API_KEY not in result.raw and API_KEY not in log  # 0 утечек секретов
    assert health["hot_sessions"] == 1 and health["resilience_flags"]["BRIDGE_KEEPALIVE_ONLY_PRERETRY_ENABLED"] is True
    assert bridge.is_clean, bridge.leaks


def test_flags_off_is_byte_equivalent_to_base_error_chunk(tmp_path: Path) -> None:
    """Флаги выкл.: один спавн, error-chunk (коммит SSE запретил повтор), без turn-resolved."""
    with running(tmp_path, "eof_then_ok", ALL_OFF) as bridge:
        result = bridge.chat(tools=False)
        spawns, log = bridge.spawn_count(), bridge.log_text()
    assert result.status == 200 and spawns == 1
    assert len(result.errors) == 1 and result.done_count == 1
    assert "userinfo" in str(result.errors[0]) and "Готово" not in result.raw
    assert "turn-resolved" not in log and "transient failure" not in log
    assert bridge.is_clean, bridge.leaks


def test_both_spawns_fail_gives_one_terminal_error_bounded(tmp_path: Path) -> None:
    """FM-02: оба спавна упали — ровно max_retries+1 спавнов, одна терминальная ошибка, один [DONE]."""
    with running(tmp_path, "eof_always", ALL_ON) as bridge:
        result = bridge.chat(tools=False)
        spawns = bridge.spawn_count()
    assert result.status == 200 and spawns == 2
    assert len(result.errors) == 1 and result.done_count == 1
    assert "Готово" not in result.raw
    assert bridge.is_clean, bridge.leaks


def test_only_classifier_flag_does_not_change_committed_stream(tmp_path: Path) -> None:
    """Независимость флагов: без keepalive-only повтор после commit по-прежнему запрещён."""
    flags = {**ALL_OFF, "BRIDGE_TRANSPORT_FAILURE_CLASSIFIER_ENABLED": True}
    with running(tmp_path, "eof_then_ok", flags) as bridge:
        result = bridge.chat(tools=False)
        spawns = bridge.spawn_count()
    assert spawns == 1 and len(result.errors) == 1
    assert bridge.is_clean, bridge.leaks
