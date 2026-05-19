#!/usr/bin/env python3
"""
Discover live agents on the NATS bus for the Agent Community Protocol.

Usage examples:
    python scripts/discover_agents.py --owner terng --session collab
    python scripts/discover_agents.py --owner $USER --session demo --health-check
    python scripts/discover_agents.py --owner alice --session review --no-health-check
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from dataclasses import asdict, dataclass
from typing import Optional

import nats
from synadia_ai.agents import Agents, DiscoverFilter, Envelope


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


async def discover_live_agents(
    owner: str,
    session: str,
    url: str = "nats://localhost:4222",
    health_check: bool = True,
    health_prompt: str = "Respond with exactly: AGENT-OK",
    timeout: float = 25.0,
    discover_wait: float = 3.5,
) -> list[AgentStatus]:
    """Programmatic API: Discover agents and optionally health-check them.

    Returns list of AgentStatus. Use this from other scripts (e.g. runner).
    """
    nc = await nats.connect(url)
    bus = Agents(nc=nc)

    try:
        discovered = await bus.discover(
            filter=DiscoverFilter(owner=owner, session_name=session),
            max_wait=discover_wait,
        )

        results: list[AgentStatus] = []

        for agent_info in discovered:
            agent_name = agent_info.agent
            status = AgentStatus(name=agent_name, owner=owner, session=session, discovered=True)

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

        return results
    finally:
        await bus.close()
        await nc.close()





def print_status_table(statuses: list[AgentStatus]):
    if not statuses:
        print("No agents discovered.")
        return

    print(f"\nDiscovered agents (owner={statuses[0].owner}, session={statuses[0].session})\n")
    print(f"{'Agent':<18} {'Status':<12} {'Time':>8} {'Response / Error'}")
    print("-" * 80)

    for s in statuses:
        if not s.discovered:
            print(f"{s.name:<18} {'NOT FOUND':<12} {'-':>8} {'-'}")
            continue

        if s.healthy is None:
            # Discovery only, no health check
            print(f"{s.name:<18} {'DISCOVERED':<12} {'-':>8} {'-'}")
        elif s.healthy:
            time_str = f"{s.response_time_ms}ms" if s.response_time_ms else "-"
            resp = s.sample_response or ""
            print(f"{s.name:<18} {'✅ HEALTHY':<12} {time_str:>8} {resp}")
        else:
            time_str = f"{s.response_time_ms}ms" if s.response_time_ms else "-"
            err = s.error or "No response"
            print(f"{s.name:<18} {'❌ UNHEALTHY':<12} {time_str:>8} {err}")

    print()


async def main():
    parser = argparse.ArgumentParser(description="Discover live A2A agents on NATS")
    parser.add_argument("--owner", default=os.environ.get("OWNER", os.environ.get("USER", "local")))
    parser.add_argument("--session", default=os.environ.get("SESSION", "collab"))
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

    args = parser.parse_args()

    statuses = await discover_live_agents(
        owner=args.owner,
        session=args.session,
        url=args.url,
        health_check=args.health_check,
        timeout=args.timeout,
        discover_wait=args.discover_wait,
    )

    if args.only_healthy:
        statuses = [s for s in statuses if s.healthy]

    if args.json:
        print(json.dumps([asdict(s) for s in statuses], indent=2, ensure_ascii=False))
        return

    print(f"Scanning NATS at {args.url} for owner={args.owner} session={args.session}...")
    print_status_table(statuses)

    healthy_count = sum(1 for s in statuses if s.healthy is True)
    print(f"Found {len(statuses)} agent(s), {healthy_count} healthy.")


if __name__ == "__main__":
    asyncio.run(main())
