import unittest

from protocol import (
    analyze_handoff,
    choose_next,
    is_adapter_error,
    is_done_signal,
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


if __name__ == "__main__":
    unittest.main()
