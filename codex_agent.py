#!/usr/bin/env python3
"""
Codex adapter for the Synadia Agent Protocol over NATS.

This process registers a Codex peer at:

    agents.prompt.codex.<owner>.<session>

It receives prompt envelopes, runs `codex exec` non-interactively, and
streams the final answer back to the caller as response chunks.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import signal
import sys
import tempfile
from pathlib import Path

import nats
from synadia_ai.agent_service import AgentService, PromptStream
from synadia_ai.agents import Envelope


DEFAULT_SYSTEM_PROMPT = """You are Codex running as an A2A protocol peer.
Answer the remote agent's request directly.
Do not assume terminal transcript text reaches the caller.
Your final message is sent back over NATS.
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Codex as a NATS A2A agent")
    parser.add_argument("--url", default=os.getenv("NATS_URL", "nats://localhost:4222"))
    parser.add_argument("--agent", default="codex", help="Agent name on the bus")
    parser.add_argument("--owner", default=os.environ.get("USER", "anon"))
    parser.add_argument("--session-name", default="collab")
    parser.add_argument("--workspace", default=os.getcwd())
    parser.add_argument("--model", default=None, help="Optional Codex model override")
    parser.add_argument(
        "--sandbox",
        default="workspace-write",
        choices=["read-only", "workspace-write", "danger-full-access"],
    )
    parser.add_argument(
        "--approval-policy",
        default="never",
        choices=["untrusted", "on-request", "on-failure", "never"],
        help="Passed to codex --ask-for-approval before the exec subcommand",
    )
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument("--system", default=DEFAULT_SYSTEM_PROMPT)
    parser.add_argument("--codex-bin", default=os.getenv("CODEX_BIN", "codex"))
    parser.add_argument("--extra-arg", action="append", default=[], help="Extra arg for codex exec")
    return parser.parse_args()


def build_prompt(system_prompt: str, remote_prompt: str) -> str:
    return (
        system_prompt.strip()
        + "\n\nRemote A2A request:\n"
        + remote_prompt.strip()
        + "\n"
    )


async def run_codex(args: argparse.Namespace, prompt: str) -> str:
    workspace = Path(args.workspace).expanduser().resolve()
    if not workspace.exists():
        raise RuntimeError(f"workspace does not exist: {workspace}")

    with tempfile.NamedTemporaryFile("w+", encoding="utf-8", delete=False) as f:
        output_path = Path(f.name)

    global_args = [
        "--ask-for-approval",
        args.approval_policy,
    ]
    if args.model:
        global_args.extend(["--model", args.model])
    if args.extra_arg:
        global_args.extend(args.extra_arg)

    cmd = [
        args.codex_bin,
        *global_args,
        "exec",
        "--cd",
        str(workspace),
        "--sandbox",
        args.sandbox,
        "--skip-git-repo-check",
        "--output-last-message",
        str(output_path),
        "-",
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(prompt.encode("utf-8")),
                timeout=args.timeout,
            )
        except asyncio.TimeoutError as exc:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            stdout, stderr = await proc.communicate()
            raise RuntimeError(
                f"codex exec timed out after {args.timeout}s\n"
                f"stdout:\n{stdout.decode('utf-8', errors='replace').strip()}\n\n"
                f"stderr:\n{stderr.decode('utf-8', errors='replace').strip()}"
            ) from exc

        final_text = output_path.read_text(encoding="utf-8").strip()
        if final_text:
            return final_text

        stdout_text = stdout.decode("utf-8", errors="replace").strip()
        stderr_text = stderr.decode("utf-8", errors="replace").strip()
        if proc.returncode == 0 and stdout_text:
            return stdout_text

        raise RuntimeError(
            f"codex exec exited with {proc.returncode}\n"
            f"stdout:\n{stdout_text}\n\nstderr:\n{stderr_text}"
        )
    finally:
        try:
            output_path.unlink()
        except FileNotFoundError:
            pass


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
        description="Codex CLI adapter for A2A over NATS",
        heartbeat_interval_s=8,
    )

    async def handler(envelope: Envelope, stream: PromptStream) -> None:
        prompt = build_prompt(args.system, envelope.prompt)
        print(f"[codex-agent] request bytes={len(prompt.encode('utf-8'))}", file=sys.stderr)
        try:
            result = await run_codex(args, prompt)
            for chunk in split_text(result):
                await stream.send(chunk)
        except Exception as exc:
            await stream.send(f"[codex-agent error] {exc}")

    agent.on_prompt(handler)
    await agent.start()

    print("Codex A2A agent live")
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
        print("\nCodex A2A agent stopped")


if __name__ == "__main__":
    asyncio.run(main())
