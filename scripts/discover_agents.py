#!/usr/bin/env python3
"""
Discover live agents on the NATS bus for the Agent Community Protocol.

Usage examples:
    python scripts/discover_agents.py --owner terng --session collab
    python scripts/discover_agents.py --owner terng --all-sessions
    python scripts/discover_agents.py --owner $USER --session demo --health-check
    python scripts/discover_agents.py --owner alice --session review --no-health-check

    # Run ping-pong protocol communication test between two agents
    python scripts/discover_agents.py --owner $USER --session collab --ping-pong
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

import nats
from synadia_ai.agents import Agents, DiscoverFilter, Envelope

# For protocol handoff analysis in ping-pong test
from protocol import analyze_handoff


@dataclass
class AgentStatus:
    name: str
    owner: str
    session: str
    discovered: bool
    healthy: Optional[bool] = None
    response_time_ms: Optional[int] = None
    sample_response: Optional[str] = None
    error: Optional[str] = None
    source: str = "a2a"
    pid: Optional[int] = None
    workspace: Optional[str] = None


def _session_from_workspace(workspace: str | None, pid: int) -> str:
    if not workspace:
        return f"grok-{pid}"
    name = Path(workspace).name.strip()
    return name or f"grok-{pid}"


def _process_cwd(pid: int) -> str | None:
    try:
        result = subprocess.run(
            ["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"],
            capture_output=True,
            text=True,
            timeout=2.0,
            check=False,
        )
    except Exception:
        return None

    if result.returncode != 0:
        return None

    for line in result.stdout.splitlines():
        if line.startswith("n"):
            return line[1:]
    return None


def _looks_like_grok_process(command: str, args: str) -> bool:
    command_name = Path(command).name.lower()
    if command_name.startswith("grok"):
        return True

    first_arg = args.split(maxsplit=1)[0] if args.strip() else ""
    return Path(first_arg).name.lower().startswith("grok")


def discover_local_grok_cli(owner: str, session: str | None = None) -> list[AgentStatus]:
    """Discover normal local Grok CLI processes by inspecting the process table.

    These entries are not NATS AgentService peers. They are useful for showing
    humans and scripts that a Grok CLI session exists, and for choosing the
    matching workspace/session name when starting a bridge adapter.
    """
    try:
        result = subprocess.run(
            ["ps", "-eo", "pid=,comm=,args="],
            capture_output=True,
            text=True,
            timeout=3.0,
            check=False,
        )
    except Exception:
        return []

    if result.returncode != 0:
        return []

    statuses: list[AgentStatus] = []
    seen_pids: set[int] = set()
    for line in result.stdout.splitlines():
        parts = line.strip().split(maxsplit=2)
        if len(parts) < 2:
            continue

        pid_text, command = parts[0], parts[1]
        args = parts[2] if len(parts) > 2 else command
        try:
            pid = int(pid_text)
        except ValueError:
            continue

        if pid in seen_pids or not _looks_like_grok_process(command, args):
            continue

        workspace = _process_cwd(pid)
        discovered_session = _session_from_workspace(workspace, pid)
        if session and discovered_session != session:
            continue

        seen_pids.add(pid)
        statuses.append(
            AgentStatus(
                name="grok",
                owner=owner,
                session=discovered_session,
                discovered=True,
                source="local-cli",
                pid=pid,
                workspace=workspace,
            )
        )

    return statuses


async def discover_live_agents(
    owner: str,
    session: str | None,
    url: str = "nats://localhost:4222",
    health_check: bool = True,
    health_prompt: str = "Respond with exactly: AGENT-OK",
    timeout: float = 25.0,
    discover_wait: float = 3.5,
    include_local_cli: bool = False,
) -> list[AgentStatus]:
    """Programmatic API: Discover agents and optionally health-check them.

    Returns list of AgentStatus. Use this from other scripts (e.g. runner).
    """
    nc = await nats.connect(url)
    bus = Agents(nc=nc)

    try:
        discover_filter = (
            DiscoverFilter(owner=owner, session_name=session)
            if session
            else DiscoverFilter(owner=owner)
        )

        discovered = await bus.discover(filter=discover_filter, max_wait=discover_wait)

        results: list[AgentStatus] = []

        for agent_info in discovered:
            agent_name = agent_info.agent
            discovered_owner = getattr(agent_info, "owner", owner)
            discovered_session = (
                getattr(agent_info, "session_name", None)
                or getattr(agent_info, "session", None)
                or session
                or "-"
            )
            status = AgentStatus(
                name=agent_name,
                owner=discovered_owner,
                session=discovered_session,
                discovered=True,
            )

            if health_check:
                start = time.time()
                try:
                    chunks: list[str] = []
                    async for chunk in agent_info.prompt(
                        Envelope(prompt=health_prompt), timeout=timeout
                    ):
                        if type(chunk).__name__ == "ResponseChunk":
                            text = getattr(chunk, "text", "") or ""
                            if text.strip():
                                chunks.append(text.strip())

                    response = " ".join(chunks).strip()
                    elapsed = int((time.time() - start) * 1000)

                    status.healthy = bool(response)
                    status.response_time_ms = elapsed
                    status.sample_response = response[:120] if response else "(empty)"

                except Exception as exc:
                    status.healthy = False
                    status.error = str(exc)[:150]
                    status.response_time_ms = int((time.time() - start) * 1000)

            results.append(status)

        if include_local_cli:
            existing = {(s.name, s.owner, s.session) for s in results}
            for local_status in discover_local_grok_cli(owner, session):
                key = (local_status.name, local_status.owner, local_status.session)
                if key not in existing:
                    results.append(local_status)
                    existing.add(key)

        return results
    finally:
        await bus.close()
        await nc.close()





def print_status_table(statuses: list[AgentStatus], *, all_sessions: bool = False):
    if not statuses:
        print("No agents discovered.")
        return

    if all_sessions:
        print(f"\nDiscovered agents (owner={statuses[0].owner}, all sessions)\n")
        print(f"{'Session':<22} {'Agent':<18} {'Status':<12} {'Time':>8} {'Response / Error'}")
        print("-" * 104)
    else:
        print(f"\nDiscovered agents (owner={statuses[0].owner}, session={statuses[0].session})\n")
        print(f"{'Agent':<18} {'Status':<12} {'Time':>8} {'Response / Error'}")
        print("-" * 80)

    for s in statuses:
        prefix = f"{s.session:<22} " if all_sessions else ""
        if not s.discovered:
            print(f"{prefix}{s.name:<18} {'NOT FOUND':<12} {'-':>8} {'-'}")
            continue

        if s.source == "local-cli":
            detail = s.workspace or f"pid={s.pid}"
            print(f"{prefix}{s.name:<18} {'LOCAL CLI':<12} {'-':>8} {detail}")
        elif s.healthy is None:
            # Discovery only, no health check
            print(f"{prefix}{s.name:<18} {'DISCOVERED':<12} {'-':>8} {'-'}")
        elif s.healthy:
            time_str = f"{s.response_time_ms}ms" if s.response_time_ms else "-"
            resp = s.sample_response or ""
            print(f"{prefix}{s.name:<18} {'✅ HEALTHY':<12} {time_str:>8} {resp}")
        else:
            time_str = f"{s.response_time_ms}ms" if s.response_time_ms else "-"
            err = s.error or "No response"
            print(f"{prefix}{s.name:<18} {'❌ UNHEALTHY':<12} {time_str:>8} {err}")

    print()


async def run_ping_pong_test(statuses: list[AgentStatus], url: str, timeout: float):
    """Run a simple ping-pong protocol test between two healthy agents.

    This verifies that:
    1. Agents can be invoked.
    2. Handoff via @mention works at the protocol level (the second agent receives the handoff request).
    """
    healthy = [s for s in statuses if s.healthy]

    if len(healthy) < 2:
        print("❌ Ping-pong test requires at least 2 healthy agents.")
        print(f"   Found only {len(healthy)} healthy agent(s).")
        return

    agent1 = healthy[0]
    agent2 = healthy[1]

    print("\n=== Ping-Pong Protocol Test ===")
    print(f"Agent 1: {agent1.name}")
    print(f"Agent 2: {agent2.name}")
    print()

    # Connect once for both calls
    nc = await nats.connect(url)
    bus = Agents(nc=nc)

    try:
        # Step 1: Ping from agent1, ask it to hand off to agent2
        ping_prompt = (
            f"This is a protocol ping test. "
            f"Please respond briefly and then hand off to @{agent2.name} "
            f"by writing exactly one mention: @{agent2.name}"
        )

        print(f"[Ping] Sending to {agent1.name} ...")
        start = time.time()

        target1 = await discover_agent_for_test(bus, agent1.name, agent1.owner, agent1.session, 3.0)
        chunks1: list[str] = []
        async for chunk in target1.prompt(Envelope(prompt=ping_prompt), timeout=timeout):
            if type(chunk).__name__ == "ResponseChunk":
                text = getattr(chunk, "text", "") or ""
                if text.strip():
                    chunks1.append(text.strip())

        response1 = " ".join(chunks1).strip()
        elapsed1 = int((time.time() - start) * 1000)
        print(f"[Ping] {agent1.name} responded in {elapsed1}ms")
        print(f"       Response: {response1[:150]}...")

        # Check if it mentioned agent2 (protocol handoff)
        from protocol import analyze_handoff
        handoff = analyze_handoff(response1, agent1.name)
        if handoff.requested_next == agent2.name:
            print(f"       ✅ Protocol handoff detected: @{agent2.name}")
        else:
            print(f"       ⚠️  No clear handoff to {agent2.name} detected")

        # Step 2: Pong from agent2
        print(f"\n[Pong] Sending to {agent2.name} ...")
        start2 = time.time()

        target2 = await discover_agent_for_test(bus, agent2.name, agent2.owner, agent2.session, 3.0)
        pong_prompt = "This is the pong response in the ping-pong protocol test. Please reply with 'PONG' and confirm you received the handoff."

        chunks2: list[str] = []
        async for chunk in target2.prompt(Envelope(prompt=pong_prompt), timeout=timeout):
            if type(chunk).__name__ == "ResponseChunk":
                text = getattr(chunk, "text", "") or ""
                if text.strip():
                    chunks2.append(text.strip())

        response2 = " ".join(chunks2).strip()
        elapsed2 = int((time.time() - start2) * 1000)
        print(f"[Pong] {agent2.name} responded in {elapsed2}ms")
        print(f"       Response: {response2[:150]}")

        print("\n✅ Ping-pong protocol test completed successfully!")
        print(f"   Total round-trip: {elapsed1 + elapsed2}ms")

    except Exception as e:
        print(f"\n❌ Ping-pong test failed: {e}")
    finally:
        await bus.close()
        await nc.close()


async def discover_agent_for_test(bus: Agents, agent_name: str, owner: str, session: str, max_wait: float):
    """Helper to discover a specific agent (reused from runner logic)."""
    from synadia_ai.agents import DiscoverFilter
    found = await bus.discover(
        filter=DiscoverFilter(agent=agent_name, owner=owner, session_name=session),
        max_wait=max_wait,
    )
    if not found:
        raise RuntimeError(f"Could not discover {agent_name}")
    return found[0]


async def main():
    parser = argparse.ArgumentParser(description="Discover live A2A agents on NATS")
    parser.add_argument("--owner", default=os.environ.get("OWNER", os.environ.get("USER", "local")))
    parser.add_argument("--session", default=os.environ.get("SESSION", "collab"))
    parser.add_argument("--all-sessions", action="store_true",
                        help="Discover every session for the owner instead of one session")
    parser.add_argument("--url", default=os.environ.get("NATS_URL", "nats://localhost:4222"))
    parser.add_argument("--health-check", action="store_true", default=True,
                        help="Send a test prompt to each agent (default: on)")
    parser.add_argument("--no-health-check", dest="health_check", action="store_false",
                        help="Only discover, do not invoke")
    parser.add_argument("--only-healthy", action="store_true",
                        help="Only return agents that passed health check")
    parser.add_argument("--json", action="store_true",
                        help="Output results as JSON (useful for scripting)")
    parser.add_argument("--timeout", type=float, default=25.0,
                        help="Timeout per agent health check (seconds)")
    parser.add_argument("--discover-wait", type=float, default=3.5,
                        help="How long to wait for discovery (seconds)")
    parser.add_argument("--ping-pong", action="store_true",
                        help="Run a simple ping-pong protocol test between two healthy agents")
    parser.add_argument("--include-local-cli", action="store_true",
                        help="Also list normal local Grok CLI processes as source=local-cli")

    args = parser.parse_args()

    statuses = await discover_live_agents(
        owner=args.owner,
        session=None if args.all_sessions else args.session,
        url=args.url,
        health_check=args.health_check,
        timeout=args.timeout,
        discover_wait=args.discover_wait,
        include_local_cli=args.include_local_cli,
    )

    if args.only_healthy:
        statuses = [s for s in statuses if s.healthy]

    if args.json:
        print(json.dumps([asdict(s) for s in statuses], indent=2, ensure_ascii=False))
        return

    if args.ping_pong:
        await run_ping_pong_test(statuses, args.url, args.timeout)
        return

    if args.all_sessions:
        print(f"Scanning NATS at {args.url} for owner={args.owner} across all sessions...")
    else:
        print(f"Scanning NATS at {args.url} for owner={args.owner} session={args.session}...")
    print_status_table(statuses, all_sessions=args.all_sessions)

    healthy_count = sum(1 for s in statuses if s.healthy is True)
    session_count = len({s.session for s in statuses})
    if args.all_sessions:
        print(f"Found {len(statuses)} agent(s), {session_count} session(s), {healthy_count} healthy.")
    else:
        print(f"Found {len(statuses)} agent(s), {healthy_count} healthy.")


if __name__ == "__main__":
    asyncio.run(main())
