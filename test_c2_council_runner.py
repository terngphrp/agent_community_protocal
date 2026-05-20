import unittest

from protocol import (
    analyze_handoff,
    choose_next,
    is_adapter_error,
    is_done_signal,
    parse_turn,
)

from envelope import (
    Envelope,
    new_envelope,
    format_envelope_block,
    parse_response,
)


class CouncilProtocolTests(unittest.TestCase):
    def test_done_signal_requires_final_standalone_line(self) -> None:
        self.assertFalse(is_done_signal("Discuss the token [DONE] but continue."))
        self.assertFalse(is_done_signal("[DONE]\nMore text"))
        self.assertTrue(is_done_signal("Final answer\n[DONE]"))

    def test_handoff_accepts_one_unique_non_self_target(self) -> None:
        result = analyze_handoff("please ask @grok", "claude-code")
        self.assertTrue(result.valid)
        self.assertIsNone(result.violation)
        self.assertEqual(result.requested_next, "grok")

    def test_handoff_uses_last_target_but_records_multiple_mentions(self) -> None:
        result = analyze_handoff("ask @grok or maybe @claude-code", "codex")
        self.assertFalse(result.valid)
        self.assertIsNone(result.requested_next)
        self.assertIn("multiple handoff targets", result.violation or "")

    def test_handoff_records_self_only_mention(self) -> None:
        result = analyze_handoff("I should continue @codex", "codex")
        self.assertFalse(result.valid)
        self.assertIsNone(result.requested_next)
        self.assertIn("tried to hand off to itself", result.violation or "")

    def test_handoff_records_self_plus_valid_mention(self) -> None:
        result = analyze_handoff("I think @codex then @grok", "codex")
        self.assertFalse(result.valid)
        self.assertIsNone(result.requested_next)
        self.assertIn("tried to hand off to itself", result.violation or "")

    def test_loop_prevention_falls_back_to_next_candidate(self) -> None:
        counts = {("claude-code", "grok"): 2}
        selected = choose_next("claude-code", "grok", counts, max_edge_repeat=2)
        self.assertEqual(selected, "codex")
        self.assertEqual(counts[("claude-code", "codex")], 1)

    def test_adapter_error_detection(self) -> None:
        self.assertTrue(is_adapter_error("[grok-agent error] timed out"))
        self.assertFalse(is_adapter_error("normal answer with [grok-agent error] inside"))


class EnvelopeV1DualModeTests(unittest.TestCase):
    """Tests for a2a-envelope v0.1 + legacy fallback (parse_turn)"""

    def test_parse_turn_prefers_envelope(self) -> None:
        env = new_envelope(
            from_agent="grok",
            content="We should let codex implement the validator.",
            handoff_to="codex",
        )
        block = format_envelope_block(env)
        text = "Some reasoning...\n\n" + block

        envelope, handoff, done, violations = parse_turn(text, "grok")
        self.assertIsNotNone(envelope)
        self.assertEqual(envelope.from_agent, "grok")  # type: ignore
        self.assertEqual(handoff.requested_next, "codex")
        self.assertEqual(violations, [])

    def test_parse_turn_falls_back_to_legacy_mention(self) -> None:
        text = "I need help from codex on this.\n@codex"
        envelope, handoff, done, violations = parse_turn(text, "grok", allow_envelope=True)
        self.assertIsNone(envelope)
        self.assertEqual(handoff.requested_next, "codex")
        self.assertEqual(violations, [])

    def test_envelope_detects_self_handoff(self) -> None:
        env = new_envelope("codex", "I'll do it myself", "codex")
        block = format_envelope_block(env)
        envelope, handoff, done, violations = parse_turn(block, "codex")

        self.assertIsNotNone(envelope)
        self.assertIn("self", " ".join(violations).lower())

    def test_envelope_done_vs_handoff_conflict(self) -> None:
        # Manually construct conflicting envelope
        bad = Envelope(
            from_agent="grok",
            content="Done and also handing off",
            handoff={"to": "codex", "reason": "nope"},  # type: ignore
            done=True,
        )
        block = format_envelope_block(bad)
        envelope, handoff, done, violations = parse_turn(block, "grok")

        self.assertIsNotNone(envelope)
        self.assertIn("both", " ".join(violations).lower())

    def test_parse_turn_records_correction_attempt(self) -> None:
        env = new_envelope("grok", "Second try after mistake", "codex", correction_attempt=1)
        block = format_envelope_block(env)
        envelope, _, _, _ = parse_turn(block, "grok")
        self.assertEqual(envelope.correction_attempt, 1)  # type: ignore

    def test_legacy_done_still_works_through_dual_parser(self) -> None:
        text = "Final conclusion here.\n[DONE]"
        envelope, handoff, done, violations = parse_turn(text, "claude-code")
        self.assertIsNone(envelope)
        self.assertIsNone(handoff.requested_next)


if __name__ == "__main__":
    unittest.main()
