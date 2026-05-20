import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).parent
    / "skills"
    / "a2a-cross-session"
    / "scripts"
    / "a2a_cross_session.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("a2a_cross_session", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class A2ACrossSessionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mod = load_module()

    def test_parse_agent_spec_normalizes_claude(self) -> None:
        ref = self.mod.parse_agent_spec("claude@psims_daily_data_prep", "terng")

        self.assertEqual(ref.agent, "claude-code")
        self.assertEqual(ref.owner, "terng")
        self.assertEqual(ref.session, "psims_daily_data_prep")
        self.assertEqual(ref.spec(), "claude-code@psims_daily_data_prep")

    def test_parse_agent_spec_requires_session(self) -> None:
        with self.assertRaises(ValueError):
            self.mod.parse_agent_spec("grok", "terng")

    def test_require_discovered_accepts_existing_endpoint(self) -> None:
        ref = self.mod.AgentRef("grok", "terng", "collab")

        self.mod.require_discovered(ref, [ref])

    def test_require_discovered_rejects_missing_endpoint(self) -> None:
        ref = self.mod.AgentRef("grok", "terng", "missing")
        available = [self.mod.AgentRef("grok", "terng", "collab")]

        with self.assertRaisesRegex(RuntimeError, "was not discovered"):
            self.mod.require_discovered(ref, available)


if __name__ == "__main__":
    unittest.main()
