import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).parent / "scripts" / "discover_agents.py"


def load_module():
    spec = importlib.util.spec_from_file_location("discover_agents", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class DiscoverAgentsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mod = load_module()

    def test_looks_like_grok_process_accepts_versioned_binary(self) -> None:
        self.assertTrue(self.mod._looks_like_grok_process("grok-0.1.13", "grok"))

    def test_looks_like_grok_process_rejects_adapter_python(self) -> None:
        self.assertFalse(
            self.mod._looks_like_grok_process(
                "python3",
                "python3 /repo/grok_cli_agent.py --session-name agent_talk",
            )
        )

    def test_discover_local_grok_cli_uses_cwd_basename_as_session(self) -> None:
        ps_output = (
            "87263 /Users/terng/.grok/bin/grok-0.1.13 grok\n"
            "10000 /usr/bin/python3 python3 /repo/grok_cli_agent.py\n"
        )

        def fake_run(cmd, **kwargs):
            if cmd[:3] == ["ps", "-eo", "pid=,comm=,args="]:
                return subprocess.CompletedProcess(cmd, 0, stdout=ps_output, stderr="")
            if cmd[:4] == ["lsof", "-a", "-p", "87263"]:
                return subprocess.CompletedProcess(
                    cmd,
                    0,
                    stdout="p87263\nn/Users/terng/Downloads/work/agent_talk\n",
                    stderr="",
                )
            raise AssertionError(f"unexpected command: {cmd}")

        with patch.object(self.mod.subprocess, "run", side_effect=fake_run):
            statuses = self.mod.discover_local_grok_cli("terng")

        self.assertEqual(len(statuses), 1)
        status = statuses[0]
        self.assertEqual(status.name, "grok")
        self.assertEqual(status.owner, "terng")
        self.assertEqual(status.session, "agent_talk")
        self.assertEqual(status.source, "local-cli")
        self.assertEqual(status.pid, 87263)
        self.assertEqual(status.workspace, "/Users/terng/Downloads/work/agent_talk")


if __name__ == "__main__":
    unittest.main()
