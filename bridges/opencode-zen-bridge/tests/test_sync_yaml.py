"""Синхронизатор: хирургия регионов cordis.patch.yml (копии реальных профилей), гарды, бэкап, откат."""

from __future__ import annotations

import copy
import hashlib
import json
import re
import stat
import tempfile
import unittest
from pathlib import Path
from typing import Any

import sync_dsh_models as sync
import zen_catalog as zc
from tests._fixtures import FIXTURES, fixture_text, load_json

GOLDEN = {e["id"]: e for e in load_json("golden_catalog.json")}
API = load_json("api_fixture.json")
ZEN = load_json("zen_fixture.json")
DESKTOP = fixture_text("cordis.desktop.yml")
WEB = fixture_text("cordis.web.yml")
TARGET = "deepseek-v4.1-flash-free"


def make_state(drop: tuple[str, ...] = (), previous: dict[str, Any] | None = None) -> dict[str, Any]:
    models = copy.deepcopy(zc.api_models(API))
    for model_id in drop:
        models[model_id]["status"] = "deprecated"
    state, violation = sync.build_state(models, set(zc.zen_ids(ZEN)), previous)
    assert violation is None
    return state


def region_lines(text: str, name: str) -> list[str]:
    lines = text.split("\n")
    start = next(i for i, ln in enumerate(lines) if f"# >>> zen-autosync:{name} (managed) >>>" in ln)
    end = next(i for i, ln in enumerate(lines) if f"# <<< zen-autosync:{name} <<<" in ln)
    return lines[start + 1:end]


def parse_cards(lines: list[str]) -> dict[str, dict[str, Any]]:
    cards: dict[str, dict[str, Any]] = {}
    current: dict[str, Any] = {}
    for line in lines:
        text = line.strip()
        if text.startswith("- id: "):
            current = {"id": text[6:]}
            cards[current["id"]] = current
        elif text.startswith("name: "):
            current["name"] = json.loads(text[6:])
        elif text.startswith("contextWindow: "):
            current["contextWindow"] = int(text[15:])
        elif text.startswith("maxTokens: "):
            current["maxTokens"] = int(text[11:])
        elif text.startswith("input: "):
            current["input"] = [p.strip() for p in text[8:-1].split(",")]
        elif text.startswith("reasoningEfforts: "):
            body = text[len("reasoningEfforts: {"):-1]
            pairs = (p.split(":", 1) for p in body.split(","))
            current["reasoningEfforts"] = {k.strip(): v.strip().strip('"') for k, v in pairs}
    return cards


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class RenderProfileTest(unittest.TestCase):
    def setUp(self) -> None:
        self.state = make_state()

    def test_cards_equal_golden_in_both_profiles(self) -> None:
        for label, text in (("desktop", DESKTOP), ("web", WEB)):
            with self.subTest(profile=label):
                cards = parse_cards(region_lines(sync.render_profile(text, self.state), "models"))
                for model_id, entry in GOLDEN.items():
                    card = cards[model_id]
                    for key in ("contextWindow", "maxTokens", "input", "reasoningEfforts"):
                        self.assertEqual(card[key], entry["cordis"][key], (model_id, key))
                    self.assertEqual(card["name"], zc.card_name(entry))

    def test_allowed_models_are_active_ids_only(self) -> None:
        for text in (DESKTOP, WEB):
            out = sync.render_profile(text, self.state)
            ids = re.findall(r"model: (\S+)", "\n".join(region_lines(out, "allowed")))
            self.assertEqual(ids, sorted(GOLDEN))
            self.assertEqual(region_lines(out, "allowed").count("      - provider: opencode-zen-bridge"), 8)

    def test_hidden_alias_cards_carry_target_metadata(self) -> None:
        out = sync.render_profile(WEB, self.state)
        cards = parse_cards(region_lines(out, "models"))
        for old in zc.DEPRECATED_MODEL_ALIASES:
            self.assertEqual(cards[old]["name"], f"{old} (deprecated -> {TARGET})")
            self.assertEqual(cards[old]["reasoningEfforts"], GOLDEN[TARGET]["cordis"]["reasoningEfforts"])
            self.assertEqual(cards[old]["contextWindow"], 200000)
        allowed = "\n".join(region_lines(out, "allowed"))
        self.assertNotIn("minimax-m3.1-flash-free", allowed)

    def test_js_tags_and_outside_bytes_are_untouched(self) -> None:
        for text in (DESKTOP, WEB):
            out = sync.render_profile(text, self.state)
            self.assertEqual(out.count("!!js"), text.count("!!js"))
            self.assertGreater(text.count("!!js"), 0)
            old_regions = sync.locate_regions(text.split("\n"))
            new_regions = sync.find_marked(out.split("\n"))
            self.assertEqual(
                sync._outside(text.split("\n"), old_regions), sync._outside(out.split("\n"), new_regions))

    def test_first_run_adds_exactly_four_marker_lines_and_is_idempotent(self) -> None:
        out = sync.render_profile(WEB, self.state)
        markers = [ln for ln in out.split("\n") if "zen-autosync:" in ln]
        self.assertEqual(len(markers), 4)
        self.assertEqual(sync.render_profile(out, self.state), out)

    def test_comments_before_region_survive(self) -> None:
        out = sync.render_profile(DESKTOP, self.state)
        self.assertIn("      # OpenCode Zen Free (:9883)", out)
        self.assertIn("      # CLI Agent Bridge (:9882)", out)

    def test_default_model_untouched_when_active(self) -> None:
        out = sync.render_profile(DESKTOP, self.state)
        self.assertIn("    model: mimo-v2.6-flash-free\n    reasoningEffort: high", out)
        self.assertEqual(out.count("model: mimo-v2.6-flash-free"), 2)   # default + allowedModels

    def test_default_model_replaced_when_it_left_the_catalog(self) -> None:
        state = make_state(drop=("mimo-v2.6-flash-free",))
        out = sync.render_profile(DESKTOP, state)
        self.assertIn(f"    model: {TARGET}\n    reasoningEffort: high", out)
        self.assertNotIn("mimo-v2.6-flash-free\n", "\n".join(region_lines(out, "allowed")))
        self.assertEqual(out.count("!!js"), DESKTOP.count("!!js"))

    def test_web_default_is_not_zen_and_stays(self) -> None:
        state = make_state(drop=("mimo-v2.6-flash-free",))
        out = sync.render_profile(WEB, state)
        self.assertIn("    provider: opencode-go\n    model: deepseek-v4.1-flash", out)

    def test_removed_model_disappears_from_allowed_but_gets_alias_card(self) -> None:
        state = make_state(drop=("beam-free",), previous=self.state)     # beam-free был активен -> retired
        out = sync.render_profile(WEB, state)
        self.assertNotIn("beam-free", "\n".join(region_lines(out, "allowed")))
        cards = parse_cards(region_lines(out, "models"))
        self.assertEqual(cards["beam-free"]["name"], f"beam-free (deprecated -> {TARGET})")
        self.assertEqual(cards["beam-free"]["contextWindow"], 200000)


class GuardTest(unittest.TestCase):
    def setUp(self) -> None:
        self.state = make_state()

    def test_region_with_js_is_refused(self) -> None:
        out = sync.render_profile(WEB, self.state)
        broken = out.replace("          # <<< zen-autosync:models <<<",
                             "          x: !!js 1\n          # <<< zen-autosync:models <<<")
        with self.assertRaisesRegex(sync.SyncError, "!!js"):
            sync.render_profile(broken, self.state)

    def test_provider_block_must_be_unique(self) -> None:
        doubled = WEB + "\n      opencode-zen-bridge:\n        models:\n          - id: x\n"
        with self.assertRaisesRegex(sync.SyncError, "exactly 1"):
            sync.render_profile(doubled, self.state)
        with self.assertRaisesRegex(sync.SyncError, "exactly 1"):
            sync.render_profile("providers:\n  other: {}\n", self.state)

    def test_allowed_group_must_be_contiguous(self) -> None:
        marker = "      - provider: opencode-go-claude\n        model: claude-haiku-5-5\n"
        self.assertIn(marker, WEB)
        split = WEB.replace(marker, marker + "      - provider: opencode-zen-bridge\n        model: stray\n", 1)
        with self.assertRaisesRegex(sync.SyncError, "separate groups"):
            sync.render_profile(split, self.state)

    def test_broken_markers_are_refused(self) -> None:
        out = sync.render_profile(WEB, self.state)
        for broken in (out.replace("# <<< zen-autosync:allowed <<<", "# end"),
                       out.replace("# >>> zen-autosync:models (managed) >>>", "# >>> zen-autosync:other (managed) >>>")):
            with self.subTest(), self.assertRaises(sync.SyncError):
                sync.render_profile(broken, self.state)

    def test_crlf_is_refused(self) -> None:
        with self.assertRaisesRegex(sync.SyncError, "CRLF"):
            sync.render_profile(WEB.replace("\n", "\r\n"), self.state)

    def test_yaml_injection_through_names_and_ids(self) -> None:
        entry = copy.deepcopy(GOLDEN["beam-free"])
        evil = 'Evil"\n    - id: pwned\n  x: !!js process.exit(1) #'
        lines = sync.card_lines(10, "beam-free", evil, entry)
        self.assertEqual(len(lines), 6)                       # перевод строки не вышел из значения
        self.assertEqual(json.loads(lines[1].split("name: ", 1)[1]), evil)
        for bad in ("beam-free\n- id: x", "Bad Id", "a: b", "x" * 80, "!!js x"):
            with self.subTest(model_id=bad), self.assertRaises(sync.SyncError):
                sync.card_lines(10, bad, "n", entry)


class DumpVerificationTest(unittest.TestCase):
    def test_real_dump_after_sync_matches(self) -> None:
        self.assertEqual(sync.verify_dump(fixture_text("dump_web_after.txt"), make_state()), [])

    def test_dump_before_sync_mismatches(self) -> None:
        problems = sync.verify_dump(fixture_text("dump_web_before.txt"), make_state())
        joined = "\n".join(problems)
        self.assertIn("flint-40b-free is missing", joined)
        self.assertIn("big-pickle differs", joined)

    def test_dump_without_provider_is_a_problem(self) -> None:
        self.assertTrue(sync.verify_dump("plain: text\n", make_state()))


# --------------------------------------------------------------------------- сквозной прогон

def _write_script(path: Path, body: str) -> Path:
    path.write_text("#!/bin/sh\n" + body + "\n", "utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


class RunSyncTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.paths = sync.Paths(bridge_dir=self.root / "bridge", home=self.root / "home")
        self.paths.models_json = self.root / "cache" / "models.json"
        for name, text in (("desktop", DESKTOP), ("web", WEB)):
            self.paths.profiles[name].parent.mkdir(parents=True)
            self.paths.profiles[name].write_text(text, "utf-8")
        self.good_dump = _write_script(self.root / "dsh-ok", f"cat {FIXTURES / 'dump_web_after.txt'}")
        self.bad_dump = _write_script(self.root / "dsh-bad", f"cat {FIXTURES / 'dump_web_before.txt'}")
        self.failing = _write_script(self.root / "dsh-fail", "echo boom >&2; exit 1")
        self.paths.dsh_bin = self.good_dump
        self.api_url = (FIXTURES / "api_fixture.json").as_uri()
        self.zen_url = (FIXTURES / "zen_fixture.json").as_uri()
        self.lines: list[str] = []

    def _run(self, *extra: str, api: str | None = None, zen: str | None = None) -> int:
        args = sync.parse_args(["--api-url", api or self.api_url, "--zen-url", zen or self.zen_url, *extra])
        return sync.run_sync(args, self.paths, self.lines.append)

    def _snapshot(self) -> dict[str, str]:
        files = [self.paths.models_json, self.paths.catalog, *self.paths.profiles.values()]
        return {str(p): sha(p) for p in files if p.exists()}

    def _backups(self) -> list[Path]:
        return sorted(self.paths.backup_root.rglob("*-cordis.patch.yml"))

    def test_first_run_writes_everything_and_second_is_noop(self) -> None:
        self.assertEqual(self._run(), 0)
        self.assertTrue(self.paths.models_json.exists())
        state = zc.load_state_file(self.paths.catalog)
        assert state is not None
        self.assertEqual(state["active"], sorted(GOLDEN))
        self.assertEqual(len(self._backups()), 2)
        self.assertEqual(len(re.findall(r"updated profile", "\n".join(self.lines))), 2)
        after = self._snapshot()
        self.lines.clear()
        self.assertEqual(self._run(), 0)
        self.assertEqual(self.lines, ["no changes"])
        self.assertEqual(self._snapshot(), after)
        self.assertEqual(len(self._backups()), 2)              # без изменений — без нового бэкапа
        self.assertTrue(self.paths.profiles["web"].read_text("utf-8").count("!!js") == WEB.count("!!js"))

    def test_backup_equals_original(self) -> None:
        self._run()
        by_name = {p.name.split("-")[1]: p for p in self._backups()}
        self.assertEqual(by_name["desktop"].read_text("utf-8"), DESKTOP)
        self.assertEqual(by_name["web"].read_text("utf-8"), WEB)

    def test_dry_run_and_print_golden_write_nothing(self) -> None:
        for flag in ("--dry-run", "--print-golden"):
            with self.subTest(flag=flag):
                self.assertEqual(self._run(flag), 0)
        self.assertFalse(self.paths.models_json.exists())
        self.assertFalse(self.paths.catalog.exists())
        self.assertFalse(self.paths.backup_root.exists())
        self.assertEqual(self.paths.profiles["web"].read_text("utf-8"), WEB)
        golden_lines = [ln for ln in self.lines if " | effort=" in ln]
        self.assertEqual(golden_lines, [zc.golden_line(e) for e in GOLDEN.values()])
        self.assertEqual(len(golden_lines), 8)

    def test_no_profiles_flag(self) -> None:
        self.assertEqual(self._run("--no-profiles"), 0)
        self.assertTrue(self.paths.catalog.exists())
        self.assertEqual(self.paths.profiles["desktop"].read_text("utf-8"), DESKTOP)
        self.assertFalse(self._backups())

    def test_unreachable_sources_write_nothing(self) -> None:
        self._run()
        before = self._snapshot()
        self.lines.clear()
        code = self._run(api="http://127.0.0.1:9/api.json", zen="http://127.0.0.1:9/m")
        self.assertEqual(code, sync.EXIT_NO_DATA)
        self.assertEqual(self._snapshot(), before)

    def test_garbage_api_is_rejected(self) -> None:
        bad = self.root / "bad.json"
        for payload in ("not json", "{}", json.dumps({"opencode": {"models": {"a": {"cost": {"input": 1}}}}})):
            with self.subTest(payload=payload[:12]):
                bad.write_text(payload, "utf-8")
                self.assertEqual(self._run(api=bad.as_uri()), sync.EXIT_NO_DATA)
        self.assertFalse(self.paths.catalog.exists())

    def test_zen_failure_degrades_to_previous_catalog(self) -> None:
        self._run()
        self.lines.clear()
        self.assertEqual(self._run(zen="http://127.0.0.1:9/m"), 0)
        state = zc.load_state_file(self.paths.catalog)
        assert state is not None
        self.assertTrue(state["degraded"])
        self.assertEqual(state["active"], sorted(GOLDEN))
        self.assertTrue(any("degraded" in ln for ln in self.lines))

    def test_zen_failure_on_first_run_uses_embedded_availability(self) -> None:
        self.assertEqual(self._run(zen="http://127.0.0.1:9/m", ), 0)
        state = zc.load_state_file(self.paths.catalog)
        assert state is not None
        self.assertEqual(state["active"], sorted(GOLDEN))

    def test_safety_rail_blocks_massive_shrink(self) -> None:
        self._run()
        before = self._snapshot()
        shrunk = copy.deepcopy(API)
        for model_id in list(GOLDEN)[:5]:
            shrunk["opencode"]["models"][model_id]["status"] = "deprecated"
        path = self.root / "shrunk.json"
        path.write_text(json.dumps(shrunk), "utf-8")
        self.lines.clear()
        self.assertEqual(self._run(api=path.as_uri()), sync.EXIT_SAFETY)
        self.assertEqual(self._snapshot(), before)
        self.assertTrue(any("safety rail" in ln for ln in self.lines))

    def test_empty_catalog_is_blocked(self) -> None:
        self._run()
        before = self._snapshot()
        empty_zen = self.root / "zen.json"
        empty_zen.write_text(json.dumps({"data": [{"id": "claude-sonnet-5-5"}]}), "utf-8")
        self.assertEqual(self._run(zen=empty_zen.as_uri()), sync.EXIT_SAFETY)
        self.assertEqual(self._snapshot(), before)

    def test_removed_model_becomes_retired_alias(self) -> None:
        self._run()
        smaller = copy.deepcopy(API)
        smaller["opencode"]["models"]["flint-40b-free"]["status"] = "deprecated"
        path = self.root / "smaller.json"
        path.write_text(json.dumps(smaller), "utf-8")
        self.paths.dsh_bin = None                              # дамп-заглушка описывает прежние 8 моделей
        self.assertEqual(self._run(api=path.as_uri()), 0)
        state = zc.load_state_file(self.paths.catalog)
        assert state is not None
        self.assertNotIn("flint-40b-free", state["active"])
        self.assertEqual(state["aliases"]["flint-40b-free"], TARGET)
        web = self.paths.profiles["web"].read_text("utf-8")
        self.assertNotIn("flint-40b-free", "\n".join(region_lines(web, "allowed")))
        self.assertIn("flint-40b-free", parse_cards(region_lines(web, "models")))     # скрытая карточка

    def test_post_check_failure_restores_profiles(self) -> None:
        for dsh in (self.bad_dump, self.failing):
            with self.subTest(dsh=dsh.name):
                self.paths.dsh_bin = dsh
                self.lines.clear()
                self.assertEqual(self._run(), sync.EXIT_PROFILE)
                self.assertEqual(self.paths.profiles["desktop"].read_text("utf-8"), DESKTOP)
                self.assertEqual(self.paths.profiles["web"].read_text("utf-8"), WEB)
                self.assertTrue(any("restored" in ln for ln in self.lines))

    def test_guard_failure_writes_nothing(self) -> None:
        broken = WEB.replace("      opencode-zen-bridge:\n", "      opencode-zen-bridge-renamed:\n")
        self.paths.profiles["web"].write_text(broken, "utf-8")
        self.assertEqual(self._run(), sync.EXIT_PROFILE)
        self.assertEqual(self.paths.profiles["web"].read_text("utf-8"), broken)
        self.assertEqual(self.paths.profiles["desktop"].read_text("utf-8"), DESKTOP)
        self.assertFalse(self._backups())

    def test_lock_prevents_parallel_run(self) -> None:
        import fcntl
        import os
        self.paths.state_dir.mkdir(parents=True)
        fd = os.open(str(self.paths.lock), os.O_CREAT | os.O_RDWR)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            self.assertEqual(self._run(), 0)
            self.assertEqual(self.lines, ["already running"])
            self.assertFalse(self.paths.catalog.exists())
        finally:
            os.close(fd)

    def test_verify_dump_command(self) -> None:
        self._run()
        out: list[str] = []
        self.assertEqual(sync.run_verify_dump(str(FIXTURES / "dump_web_after.txt"), self.paths, out.append), 0)
        self.assertEqual(sync.run_verify_dump(str(FIXTURES / "dump_web_before.txt"), self.paths, out.append), 1)
        self.assertEqual(sync.run_verify_dump(str(self.root / "missing"), self.paths, out.append), 1)

    def test_atomic_write_keeps_mode_and_leaves_no_temp_files(self) -> None:
        path = self.paths.profiles["web"]
        path.chmod(0o600)
        sync.atomic_write(path, b"x: 1\n")
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual([p.name for p in path.parent.iterdir()], [path.name])


if __name__ == "__main__":
    unittest.main()
