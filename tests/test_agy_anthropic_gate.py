import unittest

from core.agy_anthropic_gate import (
    ALLOWED_AGY_CLAUDE_IDS,
    CANONICAL_FAMILY_IDS,
    ENABLED_FLAG_VALUES,
    canonicalize_claude_model,
    is_anthropic_flag_enabled,
    is_forbidden_claude_id,
    parse_agy_models_output,
    resolve_exact_5_5_upstream,
    validate_claude_effort,
)

REAL_AGY_MODELS_46_FIXTURE = (
    "\r\x1b[2K\u280b Fetching available models...\r"
    "Available models:\n"
    "  gemini-3.8-flash          Gemini 3.8 Flash\n"
    "  gemini-4-neon             Gemini 4 Neon [default]\n"
    "  claude-sonnet-4-6         Claude Sonnet 4.6\n"
    "  claude-opus-4-6-thinking  Claude Opus 4.6 Thinking\n"
)

REAL_AGY_MODELS_55_FIXTURE = (
    "\r\x1b[2K\u280b Fetching available models...\r"
    "Available models:\n"
    "  gemini-4-neon             Gemini 4 Neon [default]\n"
    "  claude-sonnet-5-5-low     Claude Sonnet 5.5 (Low)\n"
    "  claude-sonnet-5-5-medium  Claude Sonnet 5.5 (Medium)\n"
    "  claude-sonnet-5-5-high    Claude Sonnet 5.5 (High)\n"
    "  claude-opus-5-5-high      Claude Opus 5.5 (High)\n"
)


class ClaudeModelGateTests(unittest.TestCase):
    def test_exact_allowlist_constants_and_flag_values(self):
        self.assertEqual(ENABLED_FLAG_VALUES, frozenset({"1", "true", "yes", "on"}))
        self.assertEqual(
            ALLOWED_AGY_CLAUDE_IDS,
            (
                "claude-sonnet-5-5",
                "claude-sonnet-5-5-low",
                "claude-sonnet-5-5-medium",
                "claude-sonnet-5-5-high",
                "claude-sonnet-5-5-thinking",
                "claude-opus-5-5",
                "claude-opus-5-5-low",
                "claude-opus-5-5-medium",
                "claude-opus-5-5-high",
                "claude-opus-5-5-thinking",
            ),
        )
        self.assertEqual(set(CANONICAL_FAMILY_IDS), {"claude-sonnet-5-5", "claude-opus-5-5"})

    def test_flag_truthy_and_falsy_matrix(self):
        for raw in ("1", "true", "TRUE", "yes", "Yes", "on", " ON "):
            with self.subTest(raw=raw):
                self.assertTrue(is_anthropic_flag_enabled(raw))
        for raw in (None, "", "0", "false", "no", "off", "2", "enabled"):
            with self.subTest(raw=raw):
                self.assertFalse(is_anthropic_flag_enabled(raw))

    def test_canonicalize_allows_only_exact_5_5_variants(self):
        for model_id in ALLOWED_AGY_CLAUDE_IDS:
            expected = (
                "claude-sonnet-5-5"
                if model_id.startswith("claude-sonnet-")
                else "claude-opus-5-5"
            )
            with self.subTest(model_id=model_id):
                self.assertEqual(canonicalize_claude_model(model_id), expected)
                self.assertFalse(is_forbidden_claude_id(model_id))

    def test_rejects_4_6_haiku_and_other_claude_ids(self):
        rejected = (
            "claude-sonnet-4-6",
            "claude-opus-4-6-thinking",
            "claude-haiku-5-5",
            "claude-haiku-4-5",
            "claude-sonnet-5-5-preview",
            "claude-sonnet-5-5-xhigh",
            "claude-opus-5-5-thinking-extra",
            "claude-unknown",
            "",
            "gpt-5",
            "gemini-3-pro",
        )
        for model_id in rejected:
            with self.subTest(model_id=model_id):
                self.assertIsNone(canonicalize_claude_model(model_id))
                self.assertTrue(is_forbidden_claude_id(model_id))
                decision = resolve_exact_5_5_upstream(model_id, ALLOWED_AGY_CLAUDE_IDS)
                self.assertFalse(decision.available)
                self.assertIsNone(decision.upstream_model)
                self.assertEqual(decision.reason, "forbidden_or_unknown_model")

    def test_parse_models_output_handles_spinner_cr_pipes_and_comments(self):
        raw = (
            "\n"
            "  # generated model list\n"
            "Fetching available models...\rclaude-sonnet-5-5\n"
            "  claude-opus-5-5-thinking   extra metadata\n"
            "| claude-sonnet-5-5-high | Claude Sonnet 5.5 (High) |\n"
            "| --- | --- |\n"
            "# claude-opus-4-6\n"
            "\tclaude-sonnet-5-5-thinking\r\n"
            "   \n"
        )
        self.assertEqual(
            parse_agy_models_output(raw),
            (
                "claude-sonnet-5-5",
                "claude-opus-5-5-thinking",
                "claude-sonnet-5-5-high",
                "claude-sonnet-5-5-thinking",
            ),
        )

    def test_parse_real_format_fixtures(self):
        parsed_46 = parse_agy_models_output(REAL_AGY_MODELS_46_FIXTURE)
        self.assertEqual(
            parsed_46,
            (
                "gemini-3.8-flash",
                "gemini-4-neon",
                "claude-sonnet-4-6",
                "claude-opus-4-6-thinking",
            ),
        )
        parsed_55 = parse_agy_models_output(REAL_AGY_MODELS_55_FIXTURE)
        self.assertEqual(
            parsed_55,
            (
                "gemini-4-neon",
                "claude-sonnet-5-5-low",
                "claude-sonnet-5-5-medium",
                "claude-sonnet-5-5-high",
                "claude-opus-5-5-high",
            ),
        )

    def test_each_exact_variant_is_available_when_listed(self):
        for model_id in ALLOWED_AGY_CLAUDE_IDS:
            with self.subTest(model_id=model_id):
                decision = resolve_exact_5_5_upstream(model_id, [model_id])
                self.assertTrue(decision.available)
                self.assertEqual(decision.upstream_model, model_id)
                self.assertEqual(
                    decision.canonical_model, canonicalize_claude_model(model_id)
                )

    def test_non_thinking_wins_and_effort_selects_suffixed_variant(self):
        live = parse_agy_models_output(REAL_AGY_MODELS_55_FIXTURE)
        for effort, expected in (
            (None, "claude-sonnet-5-5-high"),
            ("", "claude-sonnet-5-5-high"),
            ("off", "claude-sonnet-5-5-high"),
            ("high", "claude-sonnet-5-5-high"),
            ("medium", "claude-sonnet-5-5-medium"),
            ("low", "claude-sonnet-5-5-low"),
        ):
            with self.subTest(effort=effort):
                decision = resolve_exact_5_5_upstream(
                    "claude-sonnet-5-5", live, requested_effort=effort
                )
                self.assertTrue(decision.available)
                self.assertEqual(decision.upstream_model, expected)
                self.assertEqual(decision.effective_effort, "off")

    def test_bare_wins_over_effort_and_thinking(self):
        for canonical in CANONICAL_FAMILY_IDS:
            thinking = f"{canonical}-thinking"
            high = f"{canonical}-high"
            for requested in (canonical, thinking):
                for live in ([canonical, high, thinking], [thinking, high, canonical]):
                    decision = resolve_exact_5_5_upstream(requested, live)
                    self.assertTrue(decision.available)
                    self.assertEqual(decision.upstream_model, canonical)

    def test_thinking_fallback_and_account_without_5_5(self):
        for canonical in CANONICAL_FAMILY_IDS:
            thinking = f"{canonical}-thinking"
            decision = resolve_exact_5_5_upstream(canonical, [thinking])
            self.assertTrue(decision.available)
            self.assertEqual(decision.upstream_model, thinking)
        live_46 = parse_agy_models_output(REAL_AGY_MODELS_46_FIXTURE)
        for requested in ALLOWED_AGY_CLAUDE_IDS:
            decision = resolve_exact_5_5_upstream(requested, live_46)
            self.assertFalse(decision.available)
            self.assertIsNone(decision.upstream_model)
            self.assertEqual(decision.reason, "missing_5_5_on_account")

    def test_live_models_hash_is_order_independent_and_content_sensitive(self):
        forward = ["claude-sonnet-5-5", "claude-sonnet-5-5-thinking"]
        first = resolve_exact_5_5_upstream("claude-sonnet-5-5", forward)
        second = resolve_exact_5_5_upstream("claude-sonnet-5-5", list(reversed(forward)))
        changed = resolve_exact_5_5_upstream(
            "claude-sonnet-5-5", forward + ["gemini-3-pro"]
        )
        self.assertEqual(first.live_models_hash, second.live_models_hash)
        self.assertNotEqual(first.live_models_hash, changed.live_models_hash)


class ClaudeEffortTests(unittest.TestCase):
    def test_supported_efforts_are_clamped_off(self):
        for effort in (None, "", "off", "low", "medium", "high"):
            with self.subTest(effort=effort):
                self.assertEqual(
                    validate_claude_effort(effort), (True, "off", "ok_clamped_off")
                )

    def test_xhigh_and_max_are_unsupported(self):
        for effort in ("xhigh", "max"):
            with self.subTest(effort=effort):
                self.assertEqual(
                    validate_claude_effort(effort),
                    (False, None, "unsupported_reasoning_effort"),
                )
                decision = resolve_exact_5_5_upstream(
                    "claude-sonnet-5-5",
                    ["claude-sonnet-5-5-high"],
                    requested_effort=effort,
                )
                self.assertFalse(decision.available)
                self.assertIsNone(decision.upstream_model)
                self.assertEqual(decision.reason, "unsupported_reasoning_effort")

    def test_other_efforts_are_invalid(self):
        for effort in ("MAX", "auto", "ultra", " high ", "1"):
            with self.subTest(effort=effort):
                self.assertEqual(
                    validate_claude_effort(effort), (False, None, "invalid_effort")
                )
