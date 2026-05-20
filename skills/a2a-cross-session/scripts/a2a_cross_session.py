#!/usr/bin/env python3
"""Discover A2A sessions, choose endpoints, and relay across sessions."""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import os
import sys
from dataclasses import dataclass
from pathlib import Path


DEFAULT_A2A_LOCAL_ROOT = "/Users/terng/Downloads/work/a2a_local"


@dataclass(frozen=True)
class AgentRef:
    agent: str
    owner: str
    session: str

    def spec(self) -> str:
        return f"{self.agent}@{self.session}"


def resolve_a2a_root() -> Path:
    env_root = os.environ.get("A2A_LOCAL_ROOT")
    if env_root:
        return Path(env_root).expanduser().resolve()

    script_path = Path(__file__).resolve()
    for parent in script_path.parents:
        if (parent / "c2_council_runner.py").exists():
            return parent

    return Path(DEFAULT_A2A_LOCAL_ROOT).expanduser().resolve()


A2A_LOCAL_ROOT = resolve_a2a_root()


def load_a2a_consult():
    script = A2A_LOCAL_ROOT / "skills" / "a2a-consult" / "scripts" / "a2a_consult.py"
    spec = importlib.util.spec_from_file_location("a2a_consult", script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def normalize_agent(raw: str) -> str:
    return {"claude": "claude-code"}.get(raw.strip().lower(), raw.strip().lower())


def parse_agent_spec(spec: str, owner: str) -> AgentRef:
    if "@" not in spec:
        raise ValueError("agent spec must use agent@session, for example grok@collab")
    agent, session = spec.split("@", 1)
    agent = normalize_agent(agent)
    session = session.strip()
    if not agent or not session:
        raise ValueError("agent spec must include both agent and session")
    return AgentRef(agent=agent, owner=owner, session=session)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Relay messages between A2A agents across sessions")
    parser.add_argument("prompt", nargs="?", help="Message/task to relay")
    parser.add_argument("--from", dest="from_spec", default=None, help="Source endpoint as agent@session")
    parser.add_argument("--to", dest="to_spec", default=None, help="Target endpoint as agent@session")
    parser.add_argument("--workspace", "-w", default=os.getcwd(), help="Project folder for the request")
    parser.add_argument("--owner", default=os.environ.get("USER", "local"))
    parser.add_argument("--nats-url", default=os.environ.get("NATS_URL", "nats://localhost:4222"))
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument("--discover-wait", type=float, default=3.5)
    parser.add_argument("--health-check", action="store_true", help="Invoke agents during discovery")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable output from a2a-consult")
    return parser.parse_args()


async def discover_refs(args: argparse.Namespace) -> list[AgentRef]:
    sys.path.insert(0, str(A2A_LOCAL_ROOT))
    from scripts.discover_agents import discover_live_agents

    if not args.json:
        print(
            f"[a2a-cross-session] discover owner={args.owner} all_sessions url={args.nats_url}",
            flush=True,
        )
    statuses = await discover_live_agents(
        owner=args.owner,
        session=None,
        url=args.nats_url,
        health_check=args.health_check,
        timeout=min(args.timeout, 60.0),
        discover_wait=args.discover_wait,
    )
    refs = [
        AgentRef(agent=s.name, owner=s.owner, session=s.session)
        for s in statuses
        if s.discovered and (s.healthy is not False)
    ]
    refs = sorted(refs, key=lambda r: (r.session, r.agent))
    if not args.json:
        print(
            f"[a2a-cross-session] discovered endpoints={len(refs)}",
            flush=True,
        )
    return refs


def print_refs(refs: list[AgentRef]) -> None:
    print("\nDiscovered A2A endpoints:\n")
    print(f"{'#':>3} {'Agent':<18} {'Owner':<16} {'Session'}")
    print("-" * 72)
    for index, ref in enumerate(refs, start=1):
        print(f"{index:>3} {ref.agent:<18} {ref.owner:<16} {ref.session}")
    print()


def require_discovered(ref: AgentRef, refs: list[AgentRef]) -> None:
    if ref in refs:
        return
    available = ", ".join(r.spec() for r in refs) or "(none)"
    raise RuntimeError(f"endpoint {ref.spec()} was not discovered. Available: {available}")


def choose_ref(label: str, refs: list[AgentRef], *, exclude: AgentRef | None = None) -> AgentRef:
    choices = [ref for ref in refs if ref != exclude]
    if not sys.stdin.isatty():
        raise RuntimeError(f"--{label} is required when stdin is not interactive")

    while True:
        raw = input(f"Choose {label} endpoint number: ").strip()
        try:
            index = int(raw)
        except ValueError:
            print("Enter a number from the table.")
            continue
        if 1 <= index <= len(refs):
            selected = refs[index - 1]
            if selected in choices:
                return selected
            print("Choose a different endpoint.")
            continue
        print("Number is out of range.")


def prompt_for_message(args: argparse.Namespace) -> str:
    if args.prompt:
        return args.prompt
    if not sys.stdin.isatty():
        raise RuntimeError("prompt is required when stdin is not interactive")
    return input("Message to relay: ").strip()


async def run(args: argparse.Namespace) -> str:
    workspace = Path(args.workspace).expanduser().resolve()
    if not workspace.is_dir():
        raise RuntimeError(f"workspace is not a directory: {workspace}")

    refs = await discover_refs(args)
    if not refs:
        raise RuntimeError(f"no A2A agents discovered for owner={args.owner!r}")

    if not args.json:
        print_refs(refs)

    source = parse_agent_spec(args.from_spec, args.owner) if args.from_spec else choose_ref("from", refs)
    target = (
        parse_agent_spec(args.to_spec, args.owner)
        if args.to_spec
        else choose_ref("to", refs, exclude=source)
    )
    require_discovered(source, refs)
    require_discovered(target, refs)
    message = prompt_for_message(args)
    if not args.json:
        print(
            f"[a2a-cross-session] selected source={source.spec()} target={target.spec()}",
            flush=True,
        )
        print(
            f"[a2a-cross-session] relay prompt_chars={len(message)} workspace={workspace}",
            flush=True,
        )

    consult = load_a2a_consult()
    relay_args = consult.argparse.Namespace(
        target=target.agent,
        prompt=message,
        workspace=str(workspace),
        max_rounds=1,
        session=source.session,
        target_session=target.session,
        target_owner=target.owner,
        from_agent=source.agent,
        from_session=source.session,
        from_owner=source.owner,
        owner=args.owner,
        nats_url=args.nats_url,
        timeout=args.timeout,
        discover_wait=args.discover_wait,
        no_preflight=False,
        council=False,
        json=args.json,
    )
    return await consult.consult_relay(relay_args, target.agent, workspace)


def main() -> None:
    args = parse_args()
    try:
        response = asyncio.run(run(args))
        if args.json:
            import json

            print(json.dumps({"ok": True, "response": response}, ensure_ascii=False))
        else:
            print("\n" + "=" * 60)
            print("A2A CROSS-SESSION RESULT")
            print("=" * 60)
            print(response)
    except Exception as exc:
        if args.json:
            import json

            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        else:
            print(f"[a2a-cross-session] Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
