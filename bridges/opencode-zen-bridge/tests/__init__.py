"""Тесты моста Zen герметичны: боевой state/zen-catalog.json и kill-switch из окружения не влияют."""

import os
import tempfile

# До первого `import server`: мост читает эти переменные при импорте.
os.environ.pop("OPENCODE_ZEN_BRIDGE_CATALOG_MODE", None)
os.environ["OPENCODE_ZEN_BRIDGE_CATALOG_STATE"] = os.path.join(
    tempfile.gettempdir(), "zen-bridge-tests-no-such-dir", "zen-catalog.json")
