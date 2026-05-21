#!/usr/bin/env python3
"""
a2a-talk-to — Better cross-session communication tool for humans and Grok.

Goal (MVP):
- ทำ cross-session ให้ใช้งานง่ายผ่าน CLI
- รองรับทั้ง human (interactive + approve) และ Grok (non-interactive + --json)
- ดีกว่า a2a-cross-session เดิมในด้าน UX และ agent-friendliness

Usage examples:
    # แบบ interactive (แนะนำสำหรับมนุษย์)
    a2a-talk-to "ช่วยรีวิวแผนงานหน่อย" --workspace .

    # แบบตรง (ดีสำหรับ Grok)
    a2a-talk-to "สรุปงานวันนี้" --from grok@feature-x --to grok@daily-review --json

    # ดู sessions ที่ active
    a2a-talk-to --list
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import os
import signal
import subprocess
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


DEFAULT_A2A_LOCAL_ROOT = "/Users/terng/Downloads/work/a2a_local"


@dataclass(frozen=True)
class AgentEndpoint:
    name: str           # ชื่อที่ normalize แล้ว (grok, claude-code, codex)
    owner: str
    session: str
    raw_name: str = ""  # ชื่อดิบที่ได้จาก discovery (เช่น claude, codex, grok)
    source: str = "a2a"
    pid: int | None = None
    workspace: str | None = None

    def spec(self) -> str:
        return f"{self.name}@{self.session}"

    def __str__(self) -> str:
        return self.spec()

    @property
    def agent_type(self) -> str:
        return self.name


def normalize_agent_name(raw_name: str) -> str:
    """แปลงชื่อ agent ที่ได้จาก discovery ให้เป็นชื่อมาตรฐาน"""
    name = raw_name.strip().lower()
    if name in ("claude", "claude-code"):
        return "claude-code"
    elif name in ("codex",):
        return "codex"
    elif name in ("grok",):
        return "grok"
    else:
        return name  # ปล่อยไว้ถ้าไม่รู้จัก (เผื่อมี agent ใหม่)


def endpoints_to_dict_list(endpoints: list[AgentEndpoint]) -> list[dict]:
    """แปลง list ของ AgentEndpoint เป็น list of dict สำหรับ JSON output"""
    result = []
    for ep in endpoints:
        result.append({
            "name": ep.name,
            "raw_name": ep.raw_name,
            "session": ep.session,
            "owner": ep.owner,
            "spec": ep.spec(),
            "source": ep.source,
            "pid": ep.pid,
            "workspace": ep.workspace,
        })
    return result


def endpoints_to_grouped_dict(endpoints: list[AgentEndpoint]) -> dict:
    """แปลง endpoints เป็น dict ที่จัดกลุ่มตามประเภท agent (เหมาะสำหรับ agent ใช้เลือก)"""
    from collections import defaultdict
    groups = defaultdict(list)
    for ep in endpoints:
        groups[ep.name].append({
            "name": ep.name,
            "session": ep.session,
            "owner": ep.owner,
            "spec": ep.spec(),
            "raw_name": ep.raw_name,
            "source": ep.source,
            "pid": ep.pid,
            "workspace": ep.workspace,
        })
    return {
        "ok": True,
        "total": len(endpoints),
        "groups": dict(groups),
        "usage_hint": "เรียก a2a-talk-to อีกครั้งด้วย --from <your-spec> --to <target-spec> --json --yes เพื่อส่งงาน"
    }


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


def load_module(module_name: str, relative_path: str):
    """Dynamically load another script as module (e.g. discover_agents, a2a_consult)."""
    full_path = A2A_LOCAL_ROOT / relative_path
    if not full_path.exists():
        raise RuntimeError(f"Cannot find module at {full_path}")

    import importlib.util
    spec = importlib.util.spec_from_file_location(module_name, str(full_path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load spec for {module_name}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Talk to another Grok (or A2A agent) in a different session."
    )
    parser.add_argument("prompt", nargs="?", help="Message or task to send")
    parser.add_argument("--from", dest="from_spec", help="Source as name@session (e.g. grok@feature-x)")
    parser.add_argument("--to", dest="to_spec", help="Target as name@session (e.g. grok@daily-review)")
    parser.add_argument("--workspace", "-w", default=os.getcwd())
    parser.add_argument("--owner", default=os.environ.get("USER", "local"))
    parser.add_argument("--nats-url", default=os.environ.get("NATS_URL", "nats://localhost:4222"))
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument("--discover-wait", type=float, default=4.0)
    parser.add_argument("--list", action="store_true", help="List all active agents across sessions")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    parser.add_argument("--yes", "-y", action="store_true", help="Auto-approve (non-interactive mode)")
    parser.add_argument("--no-preflight", action="store_true")
    return parser.parse_args()


async def discover_all_endpoints(args: argparse.Namespace) -> list[AgentEndpoint]:
    """Discover all active agents across every session."""
    discover = load_module("discover_agents", "scripts/discover_agents.py")

    statuses = await discover.discover_live_agents(
        owner=args.owner,
        session=None,  # all sessions
        url=args.nats_url,
        health_check=False,
        timeout=min(args.timeout, 45.0),
        discover_wait=args.discover_wait,
        include_local_cli=True,
    )

    endpoints = []
    for s in statuses:
        if s.discovered:
            normalized = normalize_agent_name(s.name)
            endpoints.append(
                AgentEndpoint(
                    name=normalized,
                    owner=s.owner,
                    session=s.session,
                    raw_name=s.name,
                    source=getattr(s, "source", "a2a"),
                    pid=getattr(s, "pid", None),
                    workspace=getattr(s, "workspace", None),
                )
            )

    return sorted(endpoints, key=lambda e: (e.session, e.name, e.source))


def print_endpoints(endpoints: list[AgentEndpoint], title: str = "Active A2A Endpoints"):
    if not endpoints:
        print("No active A2A agents found.")
        return

    # จัดกลุ่มตามประเภท agent
    groups = defaultdict(list)
    for ep in endpoints:
        groups[ep.name].append(ep)

    # เรียงลำดับประเภท agent ให้สวยงาม (grok, claude-code, codex)
    ordered_types = ["grok", "claude-code", "codex"]
    for agent_type in sorted(groups.keys()):
        if agent_type not in ordered_types:
            ordered_types.append(agent_type)

    print(f"\n{title}\n")

    counter = 1
    for agent_type in ordered_types:
        if agent_type not in groups:
            continue
        eps = groups[agent_type]
        print(f"--- {agent_type} ---")
        for ep in sorted(eps, key=lambda x: x.session):
            detail = ep.owner
            if ep.source != "a2a":
                suffix = ep.workspace or f"pid={ep.pid}"
                detail = f"{ep.owner}  [{ep.source}: {suffix}]"
            print(f"{counter:>3}. {ep.spec():<32} {detail}")
            counter += 1
        print()


def select_endpoint(label: str, endpoints: list[AgentEndpoint], exclude: Optional[AgentEndpoint] = None) -> Optional[AgentEndpoint]:
    candidates = [e for e in endpoints if e != exclude]
    if not candidates:
        raise RuntimeError("No suitable endpoints available.")

    if len(candidates) == 1:
        return candidates[0]

    print(f"\nSelect {label} (enter number, or type 'cancel' / 'back'):")
    for i, ep in enumerate(candidates, 1):
        print(f"  {i}. {ep.spec()}  (owner={ep.owner})")

    while True:
        raw = input(f"\n> Number for {label}: ").strip().lower()
        if raw in ("cancel", "c", "exit", "quit"):
            return None
        if raw in ("back", "b"):
            return "back"  # special signal

        try:
            choice = int(raw)
            if 1 <= choice <= len(candidates):
                return candidates[choice - 1]
        except ValueError:
            pass
        print("Invalid input. Enter a number, 'back', or 'cancel'.")


def find_endpoint(endpoints: list[AgentEndpoint], wanted: AgentEndpoint) -> AgentEndpoint | None:
    for ep in endpoints:
        if ep.name == wanted.name and ep.owner == wanted.owner and ep.session == wanted.session:
            return ep
    return None


async def call_local_grok_cli(
    args: argparse.Namespace,
    *,
    source: AgentEndpoint,
    target: AgentEndpoint,
) -> str:
    if not target.workspace:
        raise RuntimeError(f"local Grok endpoint {target.spec()} has no workspace metadata")

    prompt = args.prompt
    cmd = [
        "grok",
        "-p",
        prompt,
        "--cwd",
        target.workspace,
        "--permission-mode",
        "dontAsk",
        "--sandbox",
        "read-only",
        "--output-format",
        "plain",
    ]

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
            f"grok local-cli target {target.spec()} timed out after {args.timeout}s\n"
            f"stdout:\n{stdout.decode('utf-8', errors='replace').strip()}\n\n"
            f"stderr:\n{stderr.decode('utf-8', errors='replace').strip()}"
        ) from exc

    stdout_text = stdout.decode("utf-8", errors="replace").strip()
    stderr_text = stderr.decode("utf-8", errors="replace").strip()
    if stdout_text:
        return stdout_text

    raise RuntimeError(
        f"grok local-cli target {target.spec()} exited with {proc.returncode}\n"
        f"stdout:\n{stdout_text}\n\nstderr:\n{stderr_text}"
    )


@contextlib.contextmanager
def temporary_grok_bridge(
    endpoint: AgentEndpoint,
    *,
    nats_url: str,
    timeout: float,
):
    if endpoint.name != "grok" or endpoint.source != "local-cli":
        yield
        return

    workspace = endpoint.workspace
    if not workspace:
        yield
        return

    cmd = [
        sys.executable,
        str(A2A_LOCAL_ROOT / "grok_cli_agent.py"),
        "--url",
        nats_url,
        "--owner",
        endpoint.owner,
        "--session-name",
        endpoint.session,
        "--workspace",
        workspace,
        "--timeout",
        str(timeout),
    ]
    proc = subprocess.Popen(
        cmd,
        cwd=str(A2A_LOCAL_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    try:
        time.sleep(2.0)
        yield
    finally:
        if proc.poll() is None:
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=3.0)
            except subprocess.TimeoutExpired:
                proc.kill()


async def run_interactive(args: argparse.Namespace, endpoints: list[AgentEndpoint]) -> str:
    """Human-friendly flow with clear approval step (User → Approve → Auto)."""
    if not args.prompt:
        args.prompt = input("Enter message or task to send: ").strip()

    print_endpoints(endpoints, title="Discovered Active Agents (All Sessions)")

    # เลือก Source
    source = select_endpoint("source (sender)", endpoints)
    if source is None:
        print("Operation cancelled.")
        sys.exit(0)

    # เลือก Target
    target = select_endpoint("target (receiver)", endpoints, exclude=source)
    while target == "back":
        source = select_endpoint("source (sender)", endpoints)
        if source is None:
            print("Operation cancelled.")
            sys.exit(0)
        target = select_endpoint("target (receiver)", endpoints, exclude=source)

    if target is None:
        print("Operation cancelled.")
        sys.exit(0)

    # === สรุป + ขอ Approve ชัดเจน (ตาม requirement) ===
    print("\n" + "=" * 70)
    print("CROSS-SESSION MESSAGE SUMMARY")
    print("=" * 70)
    print(f"  From   : {source.spec()}   (owner: {source.owner})")
    print(f"  To     : {target.spec()}   (owner: {target.owner})")
    print(f"  Workspace : {Path(args.workspace).resolve()}")
    print("-" * 70)
    print("Message / Task:")
    print(args.prompt)
    print("=" * 70)

    if not args.yes:
        confirm = input("\nSend this message to the target session? [Y/n]: ").strip().lower()
        if confirm not in ("", "y", "yes"):
            print("Cancelled by user.")
            sys.exit(0)
    else:
        print("\n[Auto-approved with --yes]")

    print("\nSending via A2A protocol...")

    # Delegate to a2a-consult relay logic
    consult = load_module("a2a_consult", "skills/a2a-consult/scripts/a2a_consult.py")

    relay_args = consult.argparse.Namespace(
        target=target.name,
        prompt=args.prompt,
        workspace=str(Path(args.workspace).expanduser().resolve()),
        max_rounds=1,
        session=source.session,
        target_session=target.session,
        target_owner=target.owner,
        from_agent=source.name,
        from_session=source.session,
        from_owner=source.owner,
        owner=args.owner,
        nats_url=args.nats_url,
        timeout=args.timeout,
        discover_wait=args.discover_wait,
        no_preflight=args.no_preflight,
        council=False,
        json=args.json,
    )

    return await consult.consult_relay(relay_args, target.name, Path(args.workspace))


async def run_direct(args: argparse.Namespace, endpoints: list[AgentEndpoint]) -> str:
    """Non-interactive path (good for Grok and scripts)."""
    if not args.from_spec or not args.to_spec:
        raise RuntimeError("--from and --to are required in non-interactive mode")

    # Parse "grok@session-name"
    def parse_spec(spec: str) -> AgentEndpoint:
        if "@" not in spec:
            raise ValueError(f"Invalid spec '{spec}', expected 'agent@session'")
        raw_name, session = spec.split("@", 1)
        normalized = normalize_agent_name(raw_name.strip())
        return AgentEndpoint(
            name=normalized,
            owner=args.owner,
            session=session.strip(),
            raw_name=raw_name.strip(),
        )

    source = parse_spec(args.from_spec)
    target = parse_spec(args.to_spec)
    discovered_target = find_endpoint(endpoints, target) or target

    if not args.prompt:
        raise RuntimeError("Prompt is required")

    consult = load_module("a2a_consult", "skills/a2a-consult/scripts/a2a_consult.py")

    relay_args = consult.argparse.Namespace(
        target=target.name,
        prompt=args.prompt,
        workspace=str(Path(args.workspace).expanduser().resolve()),
        max_rounds=1,
        session=source.session,
        target_session=target.session,
        target_owner=target.owner,
        from_agent=None,
        from_session=None,
        from_owner=None,
        owner=args.owner,
        nats_url=args.nats_url,
        timeout=args.timeout,
        discover_wait=args.discover_wait,
        no_preflight=args.no_preflight,
        council=False,
        json=args.json,
    )

    source_context = f"""Message from another Grok/A2A session.

Source:
- agent: {source.name}
- owner: {source.owner}
- session: {source.session}

User request:
{args.prompt}

Respond directly to the source session. Do not hand off unless asked.
"""
    relay_args.prompt = source_context

    if discovered_target.name == "grok" and discovered_target.source == "local-cli":
        return await call_local_grok_cli(
            args,
            source=source,
            target=discovered_target,
        )

    with temporary_grok_bridge(
        discovered_target,
        nats_url=args.nats_url,
        timeout=args.timeout,
    ):
        return await consult.consult_direct(relay_args, target.name, Path(args.workspace))


async def main_async():
    args = parse_args()
    workspace = Path(args.workspace).expanduser().resolve()

    if args.list:
        endpoints = await discover_all_endpoints(args)
        if args.json:
            # ใช้ grouped dict เพื่อให้ agent เลือกได้ง่ายขึ้น (จัดกลุ่มตามประเภท)
            grouped = endpoints_to_grouped_dict(endpoints)
            print(json.dumps(grouped, ensure_ascii=False, indent=2))
        else:
            print_endpoints(endpoints, title=f"Active A2A Endpoints (owner={args.owner})")
        return

    endpoints = await discover_all_endpoints(args)
    if not endpoints:
        raise RuntimeError(
            f"No active A2A agents found for owner={args.owner}. "
            f"ใช้ 'a2a-talk-to --list --json' เพื่อดูรายชื่อ agents ที่กำลังรันอยู่"
        )

    # === Near-Automatic logic ===
    # ถ้าเป็น --json และไม่ได้ระบุ --from --to ให้คืนค่า discovery (grouped) แทน
    # เพื่อให้ agent สามารถเรียกเพื่อดูรายชื่อแล้วตัดสินใจส่งต่อเองได้
    if args.json and not (args.from_spec and args.to_spec):
        grouped = endpoints_to_grouped_dict(endpoints)
        print(json.dumps(grouped, ensure_ascii=False, indent=2))
        return

    # Decide flow ปกติ
    if args.from_spec and args.to_spec:
        # Direct non-interactive
        result = await run_direct(args, endpoints)
    else:
        # Interactive with approval
        result = await run_interactive(args, endpoints)

    if args.json:
        print(json.dumps({"ok": True, "response": result}, ensure_ascii=False))
    else:
        print("\n" + "=" * 60)
        print("a2a-talk-to RESULT")
        print("=" * 60)
        print(result)


def main():
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\nCancelled by user.", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        if "--json" in sys.argv or "-json" in sys.argv:
            print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        else:
            print(f"[a2a-talk-to] Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
