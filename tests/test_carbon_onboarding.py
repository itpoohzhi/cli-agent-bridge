"""Контракты онбординга Carbon и переносимого запуска AGY bridge."""

from pathlib import Path

from tools import fleet_compile


ROOT = Path(__file__).resolve().parent.parent


def test_agy_start_uses_configurable_python_fallback() -> None:
    """Стартовый скрипт предпочитает параметр и безопасно находит Python в PATH."""
    lines = (ROOT / "bridges/agy-bridge/start.sh").read_text(encoding="utf-8").splitlines()
    tail = lines[-3:]
    assert tail == [
        'PYTHON_BIN="${PYTHON_BIN:-$HOME/.local/bin/python3}"',
        '[[ -x "$PYTHON_BIN" ]] || PYTHON_BIN="$(command -v python3)"',
        'exec "$PYTHON_BIN" server.py',
    ]


def test_fleet_compiler_honors_explicit_state_dir(
    monkeypatch, tmp_path: Path
) -> None:
    """Явный state-dir не должен обращаться к пользовательскому каталогу состояния."""
    monkeypatch.setattr(fleet_compile, "resolve_state_dir", lambda: (_ for _ in ()).throw(AssertionError("fallback")))
    monkeypatch.setattr(fleet_compile, "_compile_state", lambda args, state: 1)
    assert fleet_compile.main(["--state-dir", str(tmp_path)]) == 1
