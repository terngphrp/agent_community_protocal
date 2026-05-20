import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).parent / "skills" / "a2a-consult" / "scripts" / "a2a_consult.py"


def load_module():
    spec = importlib.util.spec_from_file_location("a2a_consult", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class A2AConsultTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mod = load_module()

    def test_normalize_target_aliases_claude(self) -> None:
        self.assertEqual(self.mod.normalize_target("claude"), "claude-code")
        self.assertEqual(self.mod.normalize_target("Claude-Code"), "claude-code")
        self.assertEqual(self.mod.normalize_target("codex"), "codex")

    def test_parse_args_uses_collab_session_and_env_nats_url(self) -> None:
        with patch.dict("os.environ", {"NATS_URL": "nats://example:4222"}, clear=False):
            with patch.object(sys, "argv", ["a2a-consult", "codex", "hello"]):
                args = self.mod.parse_args()

        self.assertEqual(args.session, "collab")
        self.assertEqual(args.nats_url, "nats://example:4222")
        self.assertEqual(args.max_rounds, 1)
        self.assertFalse(args.council)
        self.assertIsNone(args.target_session)
        self.assertIsNone(args.from_agent)

    def test_parse_args_accepts_cross_session_relay(self) -> None:
        argv = [
            "a2a-consult",
            "claude",
            "send update",
            "--target-session",
            "claude-main",
            "--from-agent",
            "grok",
            "--from-session",
            "grok-sidecar",
        ]
        with patch.object(sys, "argv", argv):
            args = self.mod.parse_args()

        self.assertEqual(args.target_session, "claude-main")
        self.assertEqual(args.from_agent, "grok")
        self.assertEqual(args.from_session, "grok-sidecar")

    def test_remote_prompt_contains_workspace_and_task(self) -> None:
        prompt = self.mod.build_remote_prompt("fix the tests", Path("/tmp/project"))

        self.assertIn("Workspace requested by caller:\n/tmp/project", prompt)
        self.assertIn("fix the tests", prompt)
        self.assertIn("Do not hand off to another agent", prompt)

    def test_run_council_forwards_url_session_timeout_and_no_workspace_flag(self) -> None:
        args = self.mod.argparse.Namespace(
            prompt="review this",
            nats_url="nats://nats:4222",
            owner="alice",
            session="feature",
            target_owner=None,
            target_session=None,
            max_rounds=3,
            timeout=42.0,
            discover_wait=1.5,
        )
        completed = subprocess.CompletedProcess(args=[], returncode=0, stdout="ok", stderr="")

        with patch.object(self.mod.subprocess, "run", return_value=completed) as run:
            result = self.mod.run_council(args, "codex", Path("/work/repo"))

        self.assertIs(result, completed)
        cmd = run.call_args.args[0]
        self.assertIn("--url", cmd)
        self.assertIn("nats://nats:4222", cmd)
        self.assertIn("--session", cmd)
        self.assertIn("feature", cmd)
        self.assertIn("--timeout", cmd)
        self.assertIn("42.0", cmd)
        self.assertNotIn("--workspace", cmd)
        self.assertIn("/work/repo", cmd[2])

    def test_run_council_uses_target_session_when_present(self) -> None:
        args = self.mod.argparse.Namespace(
            prompt="review this",
            nats_url="nats://nats:4222",
            owner="alice",
            session="feature",
            target_owner="bob",
            target_session="dest",
            max_rounds=3,
            timeout=42.0,
            discover_wait=1.5,
        )
        completed = subprocess.CompletedProcess(args=[], returncode=0, stdout="ok", stderr="")

        with patch.object(self.mod.subprocess, "run", return_value=completed) as run:
            self.mod.run_council(args, "codex", Path("/work/repo"))

        cmd = run.call_args.args[0]
        self.assertEqual(cmd[cmd.index("--owner") + 1], "bob")
        self.assertEqual(cmd[cmd.index("--session") + 1], "dest")


if __name__ == "__main__":
    unittest.main()
