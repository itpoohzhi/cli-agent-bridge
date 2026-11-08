from __future__ import annotations

# Тестовые хелперы онбординга droid: сирота-процесс и изолированная копия tools/.

import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


ROOT = Path(__file__).resolve().parent.parent


def spawn_detached_orphan(seconds: int = 60) -> tuple[int, int]:
    """Запустить `sleep` настоящей сиротой: (pid сироты, pid уже завершившегося родителя).

    Промежуточный родитель стартует ребёнка в новой сессии, печатает его PID и сразу
    выходит, поэтому у сироты мёртвый родитель и проверка живого ppid её не защищает.
    """
    code = (
        "import subprocess,sys\n"
        "p=subprocess.Popen([sys.argv[1],sys.argv[2]],start_new_session=True)\n"
        "print(p.pid,flush=True)\n"
    )
    parent = subprocess.Popen(
        [sys.executable, "-c", code, "sleep", str(seconds)],
        stdout=subprocess.PIPE,
        text=True,
    )
    stdout = parent.stdout
    assert stdout is not None
    try:
        pid = int(stdout.readline())
    finally:
        parent.wait()
        stdout.close()
    return pid, parent.pid


# Единственные файлы tools/, от которых зависит droid_image (без server.py и fleet.json).
ISOLATED_TOOL_FILES = (
    "droid_image.py",
    "receipt_schema.py",
    "droid_receipt_verify.py",
    "droid_qualify_models.py",
)


def copy_isolated_tools(dest: str | Path) -> None:
    """Скопировать в `dest` только зависимости droid_image: проверка независимости от моста."""
    for name in ISOLATED_TOOL_FILES:
        shutil.copy(ROOT / "tools" / name, Path(dest) / name)
