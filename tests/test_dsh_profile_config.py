from __future__ import annotations

import unittest
from pathlib import Path


class DshProfileConfigTests(unittest.TestCase):
    def test_cordis_patch_yml_persona_suffix_does_not_contain_volatile_cwd(self) -> None:
        patch_path = Path.home() / ".dsh" / "profiles" / "web" / "cordis.patch.yml"
        if not patch_path.exists():
            self.skipTest(f"{patch_path} is not present on this machine")

        content = patch_path.read_text(encoding="utf-8")
        self.assertIn("id: deployment:persona-suffix", content)
        self.assertNotIn("{{cwd}}", content, "cordis.patch.yml must not inject volatile {{cwd}} into persona-suffix")


if __name__ == "__main__":
    unittest.main()
