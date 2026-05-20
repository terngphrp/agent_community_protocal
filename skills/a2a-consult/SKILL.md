---
name: a2a-consult
description: Consult or delegate work to another AI (Claude Code, Codex, Grok, etc.) using the Agent Community Protocol (A2A over NATS). Especially powerful when working inside a specific project folder.
argument-hint: "<target> <prompt> [--workspace path] [--session name] [--council --max-rounds N]"
---

# a2a-consult — Cross-AI Consultation via A2A Protocol

> **Installation Guide**: See [docs/guides/install-a2a-consult-skill.md](https://github.com/terngphrp/agent_community_protocal/blob/main/docs/guides/install-a2a-consult-skill.md)

This skill lets you (Grok) easily hand off work to other AIs (especially Claude Code) while staying inside a project folder. It uses the full A2A infrastructure you built (`a2a_local`).

## When to use

- You want Claude Code to work on a specific codebase
- You want Codex to implement something while you (Grok) review
- You need multi-agent collaboration on a real project
- You want to "consult" another AI without losing project context

## Usage

```bash
a2a-consult claude "ช่วย refactor ไฟล์ auth.py ให้ใช้ dependency injection" --workspace /path/to/project

a2a-consult codex "เขียน unit test สำหรับ module นี้" 

a2a-consult claude-code "รีวิวโค้ดส่วนนี้และเสนอการปรับปรุง"

a2a-consult codex "ถก trade-off กับ agent อื่น" --council --max-rounds 5
```

### Parameters

| Parameter       | Description                                      | Default                  |
|-----------------|--------------------------------------------------|--------------------------|
| `target`        | AI to consult (`claude`, `claude-code`, `codex`, `grok`) | Required |
| `prompt`        | The task or question                             | Required |
| `--workspace`   | Project folder to work in                        | Current directory        |
| `--session`     | Session name used to find running agents         | `collab`                 |
| `--nats-url`    | NATS server URL                                  | `nats://localhost:4222`  |
| `--timeout`     | Target response timeout in seconds               | 300                      |
| `--council`     | Use the multi-agent council runner               | off                      |
| `--max-rounds`  | Maximum number of turns in `--council` mode      | 1                        |
| `--json`        | Emit machine-readable output                     | off                      |

## How it works

The skill calls `scripts/a2a_consult.py`, which talks to the selected A2A agent directly by default. Use `--council` when you explicitly want the existing multi-agent runner (`c2_council_runner.py`) to rotate between agents.

It follows the **Agent Community Protocol** you designed.

## Supported Targets

- `claude` / `claude-code` → Claude Code CLI
- `codex` → Codex CLI
- `grok` → Another Grok instance (experimental)
- Future: `aider`, `opencode`, custom agents

## Best Practices

- Always specify `--workspace` when working on a real project
- Use clear, scoped prompts ("ช่วยเขียน test สำหรับฟังก์ชัน X ในไฟล์ Y")
- For complex work, increase `--max-rounds`
- Combine with your normal workflow: you plan → delegate to Claude → you review

## Related Skills & Tools

- `claude` — direct Claude Code access (lower level)
- `discover_agents` — check which AIs are currently available on the bus
- Full A2A system lives in `/Users/terng/Downloads/work/a2a_local`

## Example Workflow

```bash
cd ~/projects/my-awesome-app

grok "ฉันอยากให้ Claude ช่วย implement feature ใหม่เรื่อง user onboarding โดยใช้ clean architecture ช่วย consult กับมันหน่อย"
# internally calls: a2a-consult claude "..." --workspace ~/projects/my-awesome-app
```

## Direct CLI Usage (for debugging)

You can also call it directly:

```bash
python ~/.grok/skills/a2a-consult/scripts/a2a_consult.py claude "ช่วย refactor ไฟล์นี้" --workspace .
```

This is the foundation for true multi-AI collaboration inside real codebases.
