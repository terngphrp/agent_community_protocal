#!/usr/bin/env python3
"""
C2 autonomous council runner for Codex, Claude, and Grok over NATS.

The runner is intentionally small: it keeps a light local history, sends the
latest context to one agent at a time, reads @mentions from each answer, and
hands the next turn to the mentioned agent. If no valid mention is present, it
uses a fallback rotation. It also caps repeated handoffs so the council cannot
loop forever on one edge.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import nats
from synadia_ai.agents import Agents, DiscoverFilter, Envelope

from protocol import AGENT_ORDER, VALID_MENTIONS, analyze_handoff, choose_next, is_adapter_error, is_done_signal

AGENTS = {
    "codex": {
        "label": "Codex",
        "role": (
            "You are Codex in a three-agent council. Your lens is pragmatic "
            "execution: make tradeoffs concrete, identify the next buildable "
            "step, and call out implementation risk."
        ),
    },
    "claude-code": {
        "label": "Claude",
        "role": (
            "You are Claude in a three-agent council. Your lens is humane and "
            "responsible: protect human agency, clarify ethical consequences, "
            "and keep the discussion careful without becoming vague."
        ),
    },
    "grok": {
        "label": "Grok",
        "role": (
            "You are Grok in a three-agent council. Your lens is first "
            "principles: be direct, test assumptions, and name the real "
            "constraint behind the question."
        ),
    },
}

@dataclass
class CouncilConfig:
    topic: str
    url: str
    owner: str
    session: str
    start: str
    max_rounds: int
    history_window: int
    timeout: float
    discover_wait: float
    max_edge_repeat: int
    history_file: Path
    transcript_file: Path


@dataclass
class Turn:
    round: int
    speaker: str
    prompt: str
    response: str
    requested_next: str | None
    selected_next: str | None
    protocol_violation: str | None
    created_at: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a C2 A2A council over NATS")
    parser.add_argument(
        "topic",
        nargs="?",
        default="AI + Human ควรเป็นอย่างไรในอนาคต",
        help="Council topic or opening question",
    )
    parser.add_argument("--url", default=os.getenv("NATS_URL", "nats://localhost:4222"))
    parser.add_argument("--owner", default=os.environ.get("USER", "local"))
    parser.add_argument("--session", default="collab")
    parser.add_argument("--start", default="codex", choices=AGENT_ORDER)
    parser.add_argument("--max-rounds", type=int, default=8)
    parser.add_argument("--history-window", type=int, default=6)
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--discover-wait", type=float, default=3.0)
    parser.add_argument("--max-edge-repeat", type=int, default=2)
    parser.add_argument("--log-dir", default="logs/council")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--history-file", default=None)
    parser.add_argument("--transcript-file", default=None)
    return parser.parse_args()


def config_from_args(args: argparse.Namespace) -> CouncilConfig:
    if args.max_rounds < 1:
        raise SystemExit("--max-rounds must be >= 1")
    if args.history_window < 1:
        raise SystemExit("--history-window must be >= 1")
    if args.max_edge_repeat < 1:
        raise SystemExit("--max-edge-repeat must be >= 1")

    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_dir = Path(args.log_dir).expanduser().resolve()
    history_file = Path(args.history_file).expanduser().resolve() if args.history_file else log_dir / f"{run_id}_history.json"
    transcript_file = (
        Path(args.transcript_file).expanduser().resolve()
        if args.transcript_file
        else log_dir / f"{run_id}_transcript.md"
    )

    return CouncilConfig(
        topic=args.topic,
        url=args.url,
        owner=args.owner,
        session=args.session,
        start=args.start,
        max_rounds=args.max_rounds,
        history_window=args.history_window,
        timeout=args.timeout,
        discover_wait=args.discover_wait,
        max_edge_repeat=args.max_edge_repeat,
        history_file=history_file,
        transcript_file=transcript_file,
    )


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def compact(text: str, limit: int = 1800) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 18].rstrip() + "\n...[truncated]"


def format_history(turns: list[Turn], window: int) -> str:
    selected = turns[-window:]
    if not selected:
        return "(no previous turns)"
    blocks = []
    for turn in selected:
        label = AGENTS[turn.speaker]["label"]
        blocks.append(f"Round {turn.round} - {label}:\n{compact(turn.response)}")
    return "\n\n".join(blocks)


def build_prompt(
    agent_name: str,
    topic: str,
    turns: list[Turn],
    round_no: int,
    history_window: int,
) -> str:
    role = AGENTS[agent_name]["role"]
    history = format_history(turns, history_window)
    return f"""You are participating in a C2 semi-autonomous multi-agent council.

Council topic:
{topic}

Your council role:
{role}

Recent council history:
{history}

Turn rules:
- This is round {round_no}. Respond as {AGENTS[agent_name]["label"]}.
- Advance the discussion; do not summarize unless it changes the decision.
- Keep the answer concise enough for another agent to continue.
- If another agent should speak next, include exactly one mention from: {VALID_MENTIONS}.
- If the council has reached a clear useful conclusion, put [DONE] on its own final line.
- Do not mention yourself as the next speaker unless you are explicitly correcting your own previous answer.
"""


async def discover_agent(
    bus: Agents,
    agent_name: str,
    owner: str,
    session: str,
    max_wait: float,
):
    found = await bus.discover(
        filter=DiscoverFilter(agent=agent_name, owner=owner, session_name=session),
        max_wait=max_wait,
    )
    if not found:
        raise RuntimeError(
            f"could not discover agent={agent_name!r} owner={owner!r} session={session!r}"
        )
    return found[0]


async def call_agent(
    bus: Agents,
    agent_name: str,
    prompt: str,
    owner: str,
    session: str,
    discover_wait: float,
    timeout: float,
) -> str:
    target = await discover_agent(bus, agent_name, owner, session, discover_wait)
    chunks: list[str] = []
    async for chunk in target.prompt(Envelope(prompt=prompt), timeout=timeout):
        ctype = type(chunk).__name__
        if ctype == "ResponseChunk":
            chunks.append(getattr(chunk, "text", "") or "")
        elif ctype == "StatusChunk":
            continue
        else:
            text = getattr(chunk, "text", getattr(chunk, "data", ""))
            if text:
                chunks.append(str(text))
    response = "".join(chunks).strip()
    if not response:
        raise RuntimeError(f"{agent_name} returned an empty response")
    return response


def write_history(path: Path, topic: str, turns: list[Turn]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "topic": topic,
        "updated_at": utc_now(),
        "turns": [asdict(turn) for turn in turns],
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_transcript(path: Path, topic: str, turns: list[Turn]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# C2 Council Transcript",
        "",
        f"Topic: {topic}",
        f"Updated: {utc_now()}",
        "",
    ]
    for turn in turns:
        label = AGENTS[turn.speaker]["label"]
        header = f"## Round {turn.round}: {label}"
        if turn.protocol_violation:
            header += f" - PROTOCOL_VIOLATION: {turn.protocol_violation}"
        lines.extend(
            [
                header,
                "",
                turn.response.strip(),
                "",
                f"Requested next: {turn.requested_next or '-'}",
                f"Selected next: {turn.selected_next or '-'}",
                f"Protocol violation: {turn.protocol_violation or '-'}",
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


async def run_turn(
    bus: Agents,
    config: CouncilConfig,
    current: str,
    round_no: int,
    turns: list[Turn],
    edge_counts: dict[tuple[str, str], int],
) -> Turn:
    prompt = build_prompt(
        current,
        config.topic,
        turns,
        round_no,
        config.history_window,
    )
    print(f"\n=== Round {round_no}: {AGENTS[current]['label']} ===", flush=True)
    response = await call_agent(
        bus,
        current,
        prompt,
        config.owner,
        config.session,
        config.discover_wait,
        config.timeout,
    )
    print(response, flush=True)

    protocol_violation = None
    if is_adapter_error(response):
        protocol_violation = "adapter error response"
        requested_next = None
    else:
        handoff = analyze_handoff(response, current)
        requested_next = handoff.requested_next
        protocol_violation = handoff.violation

    done = is_done_signal(response)
    if done and protocol_violation:
        done = False
        protocol_violation += "; done signal ignored because turn violated protocol"
    if done:
        requested_next = None
    elif protocol_violation:
        requested_next = None
    elif requested_next is None:
        protocol_violation = "missing handoff mention"

    selected_next = None
    if not done and round_no < config.max_rounds:
        selected_next = choose_next(
            current,
            requested_next,
            edge_counts,
            config.max_edge_repeat,
        )

    return Turn(
        round=round_no,
        speaker=current,
        prompt=prompt,
        response=response,
        requested_next=requested_next,
        selected_next=selected_next,
        protocol_violation=protocol_violation,
        created_at=utc_now(),
    )


async def run_council(config: CouncilConfig) -> int:
    nc = await nats.connect(config.url)
    bus = Agents(nc=nc)
    turns: list[Turn] = []
    edge_counts: dict[tuple[str, str], int] = {}
    current = config.start

    try:
        for round_no in range(1, config.max_rounds + 1):
            turn = await run_turn(bus, config, current, round_no, turns, edge_counts)
            turns.append(turn)
            write_history(config.history_file, config.topic, turns)
            write_transcript(config.transcript_file, config.topic, turns)

            if is_done_signal(turn.response):
                print("\nCouncil ended by [DONE].", file=sys.stderr)
                return 0
            if not turn.selected_next:
                print("\nCouncil ended by max rounds.", file=sys.stderr)
                return 0
            print(f"\n→ next: {turn.selected_next}", file=sys.stderr)
            current = turn.selected_next
        return 0
    finally:
        await bus.close()
        await nc.close()


def main() -> None:
    config = config_from_args(parse_args())
    raise SystemExit(asyncio.run(run_council(config)))


if __name__ == "__main__":
    main()
