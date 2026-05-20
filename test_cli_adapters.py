import importlib.util
import sys
import types
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).parent


def load_adapter(filename: str):
    fake_agent_service = types.ModuleType("synadia_ai.agent_service")
    fake_agent_service.AgentService = object
    fake_agent_service.PromptStream = object

    fake_agents = types.ModuleType("synadia_ai.agents")
    fake_agents.Envelope = object

    modules = {
        "nats": types.ModuleType("nats"),
        "synadia_ai": types.ModuleType("synadia_ai"),
        "synadia_ai.agent_service": fake_agent_service,
        "synadia_ai.agents": fake_agents,
    }
    with patch.dict(sys.modules, modules):
        spec = importlib.util.spec_from_file_location(filename.removesuffix(".py"), ROOT / filename)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module


class CliAdapterCommandTests(unittest.TestCase):
    def test_claude_resume_disables_no_session_persistence(self) -> None:
        mod = load_adapter("claude_cli_agent.py")
        args = Namespace(
            claude_bin="claude",
            resume="4166774a-efe8-4409-a7d4-50f04fa9f619",
            permission_mode="dontAsk",
            tools="",
            model=None,
            extra_arg=[],
        )

        cmd = mod.build_claude_command(args, "hello")

        self.assertEqual(cmd[:3], ["claude", "--resume", args.resume])
        self.assertIn("-p", cmd)
        self.assertNotIn("--no-session-persistence", cmd)

    def test_claude_default_keeps_no_session_persistence(self) -> None:
        mod = load_adapter("claude_cli_agent.py")
        args = Namespace(
            claude_bin="claude",
            resume=None,
            permission_mode="dontAsk",
            tools="",
            model=None,
            extra_arg=[],
        )

        cmd = mod.build_claude_command(args, "hello")

        self.assertIn("--no-session-persistence", cmd)

    def test_grok_resume_is_forwarded_before_prompt_mode(self) -> None:
        mod = load_adapter("grok_cli_agent.py")
        args = Namespace(
            grok_bin="grok",
            resume="019e4326-ab7f-7fd2-bafc-32a5cd93aeff",
            permission_mode="dontAsk",
            sandbox="read-only",
            model=None,
            extra_arg=[],
        )

        cmd = mod.build_grok_command(args, "hello", Path("/work/repo"))

        self.assertEqual(cmd[:3], ["grok", "--resume", args.resume])
        self.assertIn("--cwd", cmd)
        self.assertIn("/work/repo", cmd)


if __name__ == "__main__":
    unittest.main()
