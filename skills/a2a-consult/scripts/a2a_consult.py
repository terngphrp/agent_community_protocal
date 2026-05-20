#!/usr/bin/env python3
"""
a2a-consult skill entrypoint

Usage (from Grok):
    python scripts/a2a_consult.py claude "help me with this task" --workspace /path/to/project
    python scripts/a2a_consult.py codex "compare options" --council --max-rounds 4
"""

import argparse
import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

DEFAULT_A2A_LOCAL_ROOT = "/Users/terng/Downloads/work/a2a_local"


def resolve_a2a_root() -> Path:
    """Resolve the A2A repo when running from the repo or an installed skill."""
    env_root = os.environ.get("A2A_LOCAL_ROOT")
    if env_root:
        return Path(env_root).expanduser().resolve()

    script_path = Path(__file__).resolve()
    for parent in script_path.parents:
        if (parent / "c2_council_runner.py").exists():
            return parent

    return Path(DEFAULT_A2A_LOCAL_ROOT).expanduser().resolve()


A2A_LOCAL_ROOT = resolve_a2a_root()
RUNNER = A2A_LOCAL_ROOT / "c2_council_runner.py"
DISCOVER = A2A_LOCAL_ROOT / "scripts" / "discover_agents.py"


def normalize_target(raw_target: str) -> str:
    target_map = {
        "claude": "claude-code",
        "claude-code": "claude-code",
        "codex": "codex",
        "grok": "grok",
    }
    return target_map.get(raw_target.lower(), raw_target)


def build_remote_prompt(prompt: str, workspace: Path) -> str:
    return f"""A2A consultation request.

Workspace requested by caller:
{workspace}

Important:
- If you need to inspect or edit files, operate in that workspace.
- If your adapter process was started in a different workspace and cannot access this path, say so explicitly.
- Return the useful answer directly. Do not hand off to another agent unless the caller asked for a council.

Task:
{prompt}
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Consult another AI via A2A protocol")
    parser.add_argument("target", help="Target AI (claude, claude-code, codex, grok, etc.)")
    parser.add_argument("prompt", help="The task or question for the target AI")
    parser.add_argument("--workspace", "-w", default=os.getcwd(), help="Project folder to work in")
    parser.add_argument("--max-rounds", type=int, default=1, help="Maximum council turns in --council mode")
    parser.add_argument("--session", default=os.environ.get("SESSION", "collab"), help="A2A session name")
    parser.add_argument("--owner", default=os.environ.get("USER", "local"))
    parser.add_argument("--nats-url", default=os.environ.get("NATS_URL", "nats://localhost:4222"))
    parser.add_argument("--timeout", type=float, default=300.0, help="Target response timeout in seconds")
    parser.add_argument("--discover-wait", type=float, default=3.5, help="Agent discovery timeout in seconds")
    parser.add_argument("--no-preflight", action="store_true", help="Skip dependency/NATS/target checks")
    parser.add_argument("--council", action="store_true", help="Use the multi-agent council runner")
    parser.add_argument("--json", action="store_true", help="Print a machine-readable result envelope")
    return parser.parse_args()


def fail(message: str, *, json_output: bool = False, details: dict | None = None) -> None:
    if json_output:
        print(json.dumps({"ok": False, "error": message, "details": details or {}}, ensure_ascii=False))
    else:
        print(f"[a2a-consult] Error: {message}", file=sys.stderr)
    sys.exit(1)


async def discover_target(args: argparse.Namespace, target: str):
    try:
        import nats
        from synadia_ai.agents import Agents, DiscoverFilter
    except Exception as exc:
        raise RuntimeError(
            "missing runtime dependencies. Install with: pip install nats-py synadia-ai-agents"
        ) from exc

    nc = await nats.connect(servers=[args.nats_url])
    bus = Agents(nc=nc)
    try:
        found = await bus.discover(
            filter=DiscoverFilter(agent=target, owner=args.owner, session_name=args.session),
            max_wait=args.discover_wait,
        )
        return nc, bus, found
    except Exception:
        await bus.close()
        await nc.close()
        raise


async def preflight(args: argparse.Namespace, target: str, workspace: Path) -> None:
    if not A2A_LOCAL_ROOT.exists():
        raise RuntimeError(
            f"A2A_LOCAL_ROOT does not exist: {A2A_LOCAL_ROOT}. Set A2A_LOCAL_ROOT to the a2a_local repo."
        )
    if args.council and not RUNNER.exists():
        raise RuntimeError(f"council runner not found: {RUNNER}")
    if not workspace.is_dir():
        raise RuntimeError(f"workspace is not a directory: {workspace}")

    nc, bus, found = await discover_target(args, target)
    try:
        if not found:
            raise RuntimeError(
                f"target agent {target!r} was not discovered for owner={args.owner!r} "
                f"session={args.session!r} at {args.nats_url}. Start the adapter with the same "
                f"owner/session/workspace, for example: python {target_adapter(target)} "
                f"--owner {args.owner} --session-name {args.session} --workspace {workspace}"
            )
    finally:
        await bus.close()
        await nc.close()


def target_adapter(target: str) -> str:
    return {
        "claude-code": "claude_cli_agent.py",
        "codex": "codex_agent.py",
        "grok": "grok_cli_agent.py",
    }.get(target, "<adapter>.py")


async def consult_direct(args: argparse.Namespace, target: str, workspace: Path) -> str:
    from synadia_ai.agents import Envelope

    nc, bus, found = await discover_target(args, target)
    try:
        if not found:
            raise RuntimeError(
                f"target agent {target!r} was not discovered for owner={args.owner!r} "
                f"session={args.session!r}"
            )
        target_agent = found[0]
        chunks: list[str] = []
        async for chunk in target_agent.prompt(
            Envelope(prompt=build_remote_prompt(args.prompt, workspace)),
            timeout=args.timeout,
        ):
            ctype = type(chunk).__name__
            if ctype == "ResponseChunk":
                text = getattr(chunk, "text", "") or ""
                if text:
                    chunks.append(text)
            elif ctype != "StatusChunk":
                text = getattr(chunk, "text", getattr(chunk, "data", ""))
                if text:
                    chunks.append(str(text))
        response = "".join(chunks).strip()
        if not response:
            raise RuntimeError(f"{target} returned an empty response")
        return response
    finally:
        await bus.close()
        await nc.close()


def run_council(args: argparse.Namespace, target: str, workspace: Path) -> subprocess.CompletedProcess[str]:
    cmd = [
        sys.executable,
        str(RUNNER),
        build_remote_prompt(args.prompt, workspace),
        "--url",
        args.nats_url,
        "--owner",
        args.owner,
        "--session",
        args.session,
        "--start",
        target,
        "--max-rounds",
        str(args.max_rounds),
        "--timeout",
        str(args.timeout),
        "--discover-wait",
        str(args.discover_wait),
    ]
    return subprocess.run(
        cmd,
        cwd=str(A2A_LOCAL_ROOT),
        capture_output=True,
        text=True,
        timeout=args.timeout + 15,
    )


def main():
    args = parse_args()

    workspace = Path(args.workspace).expanduser().resolve()
    if not workspace.exists():
        fail(f"Workspace not found: {workspace}", json_output=args.json)
    if not workspace.is_dir():
        fail(f"Workspace is not a directory: {workspace}", json_output=args.json)

    target = normalize_target(args.target)

    if not args.json:
        mode = "council" if args.council else "direct"
        print(f"[a2a-consult] Consulting {target} in workspace: {workspace}")
        print(f"[a2a-consult] Mode: {mode}, owner={args.owner}, session={args.session}, url={args.nats_url}")
        print(f"[a2a-consult] Prompt: {args.prompt[:100]}{'...' if len(args.prompt) > 100 else ''}")

    # Optional: quick discovery to show user what's available
    if not args.no_preflight:
        try:
            asyncio.run(preflight(args, target, workspace))
        except Exception as exc:
            fail(str(exc), json_output=args.json)

    try:
        if args.council:
            if not RUNNER.exists():
                fail(f"council runner not found: {RUNNER}", json_output=args.json)
            if not args.json:
                print(f"[a2a-consult] Starting A2A council with target: {target}...")
            result = run_council(args, target, workspace)

            if args.json:
                print(
                    json.dumps(
                        {
                            "ok": result.returncode == 0,
                            "target": target,
                            "mode": "council",
                            "workspace": str(workspace),
                            "stdout": result.stdout,
                            "stderr": result.stderr,
                            "returncode": result.returncode,
                        },
                        ensure_ascii=False,
                    )
                )
            else:
                print("\n" + "=" * 60)
                print(f"RESULT FROM {target.upper()}")
                print("=" * 60)
                print(result.stdout)

                if result.stderr:
                    print("\n[stderr]")
                    print(result.stderr)

            if result.returncode != 0:
                sys.exit(result.returncode)
            return

        if not args.json:
            print(f"[a2a-consult] Calling target agent: {target}...")
        response = asyncio.run(consult_direct(args, target, workspace))
        if args.json:
            print(
                json.dumps(
                    {
                        "ok": True,
                        "target": target,
                        "mode": "direct",
                        "workspace": str(workspace),
                        "response": response,
                    },
                    ensure_ascii=False,
                )
            )
        else:
            print("\n" + "=" * 60)
            print(f"RESULT FROM {target.upper()}")
            print("=" * 60)
            print(response)

    except subprocess.TimeoutExpired:
        fail(f"request timed out after {args.timeout}s", json_output=args.json)
    except Exception as exc:
        fail(str(exc), json_output=args.json)


if __name__ == "__main__":
    main()
