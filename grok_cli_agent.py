#!/usr/bin/env python3
"""
Grok CLI adapter for the Synadia Agent Protocol over NATS.

This process registers a local Grok peer at:

    agents.prompt.grok.<owner>.<session>

It receives prompt envelopes, runs `grok -p` non-interactively, and sends
the answer back to the caller as response chunks.
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


DEFAULT_SYSTEM_PROMPT = """You are Grok running as an A2A protocol peer.
Answer the remote agent's request directly.
Do not assume terminal transcript text reaches the caller.
Your final message is sent back over NATS.
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local Grok CLI as a NATS A2A agent")
    parser.add_argument("--url", default=os.getenv("NATS_URL", "nats://localhost:4222"))
    parser.add_argument("--agent", default="grok", help="Agent name on the bus")
    parser.add_argument("--owner", default=os.environ.get("USER", "anon"))
    parser.add_argument("--session-name", default="collab")
    parser.add_argument("--workspace", default=os.getcwd())
    parser.add_argument("--model", default=None, help="Optional Grok model override")
    parser.add_argument(
        "--sandbox",
        default="read-only",
        help="Passed to grok --sandbox",
    )
    parser.add_argument(
        "--permission-mode",
        default="dontAsk",
        help="Passed to grok --permission-mode",
    )
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument("--system", default=DEFAULT_SYSTEM_PROMPT)
    parser.add_argument("--grok-bin", default=os.getenv("GROK_BIN", "grok"))
    parser.add_argument("--extra-arg", action="append", default=[], help="Extra arg for grok")
    return parser.parse_args()


def build_prompt(system_prompt: str, remote_prompt: str) -> str:
    return (
        system_prompt.strip()
        + "\n\nRemote A2A request:\n"
        + remote_prompt.strip()
        + "\n"
    )


async def run_grok(args: argparse.Namespace, prompt: str) -> str:
    workspace = Path(args.workspace).expanduser().resolve()
    if not workspace.exists():
        raise RuntimeError(f"workspace does not exist: {workspace}")

    cmd = [
        args.grok_bin,
        "-p",
        prompt,
        "--cwd",
        str(workspace),
        "--permission-mode",
        args.permission_mode,
        "--sandbox",
        args.sandbox,
        "--output-format",
        "plain",
    ]
    if args.model:
        cmd.extend(["--model", args.model])
    if args.extra_arg:
        cmd.extend(args.extra_arg)

    proc = await asyncio.create_subprocess_exec(
        *cmd,
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
            f"grok timed out after {args.timeout}s\n"
            f"stdout:\n{stdout.decode('utf-8', errors='replace').strip()}\n\n"
            f"stderr:\n{stderr.decode('utf-8', errors='replace').strip()}"
        ) from exc

    stdout_text = stdout.decode("utf-8", errors="replace").strip()
    stderr_text = stderr.decode("utf-8", errors="replace").strip()
    if proc.returncode == 0 and stdout_text:
        return stdout_text

    raise RuntimeError(
        f"grok exited with {proc.returncode}\n"
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
        description="Grok CLI adapter for A2A over NATS",
        heartbeat_interval_s=8,
    )

    async def handler(envelope: Envelope, stream: PromptStream) -> None:
        prompt = build_prompt(args.system, envelope.prompt)
        print(f"[grok-agent] request bytes={len(prompt.encode('utf-8'))}", file=sys.stderr)
        try:
            result = await run_grok(args, prompt)
            for chunk in split_text(result):
                await stream.send(chunk)
        except Exception as exc:
            await stream.send(f"[grok-agent error] {exc}")

    agent.on_prompt(handler)
    await agent.start()

    print("Grok A2A agent live")
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
        print("\nGrok A2A agent stopped")


if __name__ == "__main__":
    asyncio.run(main())
