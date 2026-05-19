#!/usr/bin/env python3
"""
Claude CLI adapter for the Synadia Agent Protocol over NATS.

This process registers an automatic Claude peer at:

    agents.prompt.claude-code.<owner>.<session>

It receives prompt envelopes, runs `claude -p` non-interactively, and sends
the answer back to the caller as response chunks. This avoids the interactive
Claude Code NATS plugin issue where the plugin receives the request but waits
for the assistant to call the `reply` tool.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import signal
import sys
from pathlib import Path

import nats
from synadia_ai.agent_service import AgentService, PromptStream
from synadia_ai.agents import Envelope


DEFAULT_SYSTEM_PROMPT = """You are Claude Code running as an A2A protocol peer.
Answer the remote agent's request directly.
Do not assume terminal transcript text reaches the caller.
Your final message is sent back over NATS.
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Claude CLI as a NATS A2A agent")
    parser.add_argument("--url", default=os.getenv("NATS_URL", "nats://localhost:4222"))
    parser.add_argument("--agent", default="claude-code", help="Agent name on the bus")
    parser.add_argument("--owner", default=os.environ.get("USER", "anon"))
    parser.add_argument("--session-name", default="collab")
    parser.add_argument("--workspace", default=os.getcwd())
    parser.add_argument("--model", default=None, help="Optional Claude model override")
    parser.add_argument(
        "--permission-mode",
        default="dontAsk",
        choices=["acceptEdits", "auto", "bypassPermissions", "default", "dontAsk", "plan"],
    )
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument("--system", default=DEFAULT_SYSTEM_PROMPT)
    parser.add_argument("--claude-bin", default=os.getenv("CLAUDE_BIN", "claude"))
    parser.add_argument("--tools", default="", help='Passed to claude --tools. Empty disables tools.')
    parser.add_argument("--extra-arg", action="append", default=[], help="Extra arg for claude")
    return parser.parse_args()


def build_prompt(system_prompt: str, remote_prompt: str) -> str:
    return (
        system_prompt.strip()
        + "\n\nRemote A2A request:\n"
        + remote_prompt.strip()
        + "\n"
    )


async def run_claude(args: argparse.Namespace, prompt: str) -> str:
    workspace = Path(args.workspace).expanduser().resolve()
    if not workspace.exists():
        raise RuntimeError(f"workspace does not exist: {workspace}")

    cmd = [
        args.claude_bin,
        "-p",
        prompt,
        "--permission-mode",
        args.permission_mode,
        "--output-format",
        "text",
        "--no-session-persistence",
        "--tools",
        args.tools,
    ]
    if args.model:
        cmd.extend(["--model", args.model])
    if args.extra_arg:
        cmd.extend(args.extra_arg)

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(workspace),
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=args.timeout)
    except asyncio.TimeoutError as exc:
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        stdout, stderr = await proc.communicate()
        raise RuntimeError(
            f"claude timed out after {args.timeout}s\n"
            f"stdout:\n{stdout.decode('utf-8', errors='replace').strip()}\n\n"
            f"stderr:\n{stderr.decode('utf-8', errors='replace').strip()}"
        ) from exc

    stdout_text = stdout.decode("utf-8", errors="replace").strip()
    stderr_text = stderr.decode("utf-8", errors="replace").strip()
    if proc.returncode == 0 and stdout_text:
        return stdout_text

    raise RuntimeError(
        f"claude exited with {proc.returncode}\n"
        f"stdout:\n{stdout_text}\n\nstderr:\n{stderr_text}"
    )


def split_text(text: str, max_chars: int = 12000) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    return [text[i : i + max_chars] for i in range(0, len(text), max_chars)]


async def main() -> None:
    args = parse_args()

    nc = await nats.connect(servers=[args.url])
    agent = AgentService(
        agent=args.agent,
        owner=args.owner,
        session_name=args.session_name,
        nc=nc,
        description="Claude CLI adapter for A2A over NATS",
        heartbeat_interval_s=8,
    )

    async def handler(envelope: Envelope, stream: PromptStream) -> None:
        prompt = build_prompt(args.system, envelope.prompt)
        print(f"[claude-agent] request bytes={len(prompt.encode('utf-8'))}", file=sys.stderr)
        try:
            result = await run_claude(args, prompt)
            for chunk in split_text(result):
                await stream.send(chunk)
        except Exception as exc:
            await stream.send(f"[claude-agent error] {exc}")

    agent.on_prompt(handler)
    await agent.start()

    print("Claude A2A agent live")
    print(f"  url={args.url}")
    print(f"  subject={agent.subject.prompt}")
    print(f"  workspace={Path(args.workspace).expanduser().resolve()}")
    print("  Ctrl+C to stop")

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    try:
        await stop.wait()
    finally:
        await agent.stop()
        await nc.close()
        print("\nClaude A2A agent stopped")


if __name__ == "__main__":
    asyncio.run(main())
