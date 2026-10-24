"""Тестовые модели вне боевого каталога моста и общие загрузчики фикстур.

Боевой каталог теперь динамический (state/zen-catalog.json или встроенный снимок
`zen_catalog.STATIC_FALLBACK_CATALOG`; в тестах — всегда снимок). Тесты общих путей кода
(нативный Google-протокол Go, CLI-вариант `#effort`, маршрутизация провайдера)
по-прежнему нуждаются в моделях с этими свойствами, поэтому подмешиваем их только
в тестовом процессе. Снимок боевого каталога — PRODUCTION_MODELS.
"""

from __future__ import annotations

import atexit
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

FIXTURES = Path(__file__).resolve().parent / "fixtures"
GO_BASE_URL = "http://127.0.0.1:10830/go/v1/v1beta"

TEST_ONLY_MODELS = {
    "gemini-4-argon-contributor": {
        "context_length": 1048576,
        "max_output": 65536,
        "supports_variant": True,
        "provider": "opencode-go",
        "base_url": GO_BASE_URL,
    },
    "muse-spark-1.3-contributor-free": {
        "context_length": 1048576,
        "max_output": 131072,
        "supports_variant": True,
    },
}

_state: dict[str, frozenset[str]] = {}


def load_json(name: str) -> Any:
    """Фикстура из tests/fixtures."""
    return json.loads((FIXTURES / name).read_text("utf-8"))


def fixture_text(name: str) -> str:
    return (FIXTURES / name).read_text("utf-8")


def install_test_models(server: Any) -> frozenset[str]:
    """Подмешать тестовые модели; вернуть снимок боевого каталога (до подмешивания).

    Заодно уводит `server.LOG_PATH` во временный каталог: тесты не должны дописывать
    в боевой `logs/bridge.log`.
    """
    if "production" not in _state:
        _state["production"] = frozenset(server.ALLOWED_MODELS)
        log_dir = tempfile.mkdtemp(prefix="zen-bridge-tests-")
        atexit.register(shutil.rmtree, log_dir, ignore_errors=True)
        server.LOG_PATH = Path(log_dir) / "bridge.log"
    for model_id, meta in TEST_ONLY_MODELS.items():
        server.ALLOWED_MODELS.setdefault(model_id, dict(meta))
    return _state["production"]
