# Installing the `a2a-consult` Grok Skill

This guide explains how to install the **a2a-consult** skill so you can easily ask Grok to consult or delegate work to other AIs (Claude Code, Codex, etc.) using the Agent Community Protocol.

## Prerequisites

Before installing the skill, make sure you have:

1. The **a2a_local** repository cloned on your machine:
   ```bash
   git clone https://github.com/terngphrp/agent_community_protocal.git ~/Downloads/work/a2a_local
   ```

2. The required Python packages installed in some environment:
   ```bash
   pip install nats-py synadia-ai-agents
   ```

3. **NATS** running locally (usually at `nats://localhost:4222`):
   ```bash
   nats-server -js
   ```

4. At least one target AI CLI installed and authenticated:
   - `claude` (Claude Code)
   - `codex`
   - `grok`

## Installation Steps

### 1. Copy the Skill to Your Grok Skills Directory

```bash
# Create the skill directory
mkdir -p ~/.grok/skills/a2a-consult

# Copy the skill files (example using the repo you cloned)
cp -r ~/Downloads/work/a2a_local/skills/a2a-consult/* ~/.grok/skills/a2a-consult/
```

> **Note**: If you haven't cloned the repo yet, you can manually create the folder structure and copy the files from this repository.

### 2. Make the Script Executable

```bash
chmod +x ~/.grok/skills/a2a-consult/scripts/a2a_consult.py
```

### 3. (Optional but Recommended) Set Environment Variable

Add this to your shell config (`.zshrc`, `.bashrc`, etc.) so Grok always knows where your a2a_local repo is:

```bash
export A2A_LOCAL_ROOT="$HOME/Downloads/work/a2a_local"
```

Then reload your shell:

```bash
source ~/.zshrc
```

### 4. Restart Grok

Completely quit and restart your Grok session so it picks up the new skill.

---

## Installation Methods

### Method 1: Automated Installation (Recommended)

We provide an installation script that handles everything automatically.

```bash
# From the a2a_local project root
./scripts/install-a2a-consult.sh

# Install as CLI tool too (creates `a2a-consult` command)
./scripts/install-a2a-consult.sh --cli

# For Docker users (shows Docker-specific instructions)
./scripts/install-a2a-consult.sh --docker
```

The script will:
- Copy the skill to `~/.grok/skills/a2a-consult`
- Make the script executable
- Suggest adding `A2A_LOCAL_ROOT` to your shell config
- Optionally create a global `a2a-consult` CLI command

**Using Makefile (Recommended - Even easier)**

```bash
# Install only the skill
make install-skill

# Install skill + make `a2a-consult` available as a global CLI command
make install-skill-cli

# Install only the Python dependencies (nats-py + synadia-ai-agents)
make install-deps
```

### Method 2: Manual Installation

Follow the steps in the sections above (Copy files → Make executable → Set environment variable).

### Method 3: Install as CLI Tool (`a2a-consult` command)

After installing the skill, you can make it available as a global command:

```bash
# Option A: Use the installer
./scripts/install-a2a-consult.sh --cli

# Option B: Manual symlink
mkdir -p ~/.local/bin
ln -sf ~/.grok/skills/a2a-consult/scripts/a2a_consult.py ~/.local/bin/a2a-consult
```

Then make sure `~/.local/bin` is in your PATH:

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

Now you can run:

```bash
a2a-consult claude "ช่วย refactor ไฟล์นี้" --workspace .
```

### Docker Support

If you are using the Docker setup (especially the **host .venv mount** method), you have two options:

#### Option A: Run the skill from inside the container (Recommended)

```bash
cd docker

# Run the skill inside the running container
docker compose exec app /app/.venv/bin/python \
  /app/.grok/skills/a2a-consult/scripts/a2a_consult.py \
  claude "ช่วย refactor ไฟล์นี้" --workspace /app
```

Or using `docker compose run`:

```bash
docker compose run --rm app \
  /app/.venv/bin/python /app/.grok/skills/a2a-consult/scripts/a2a_consult.py \
  claude "ช่วยวิเคราะห์โค้ดส่วนนี้" --workspace /app
```

#### Option B: Call from host using the container's Python

If your container is already running with the correct environment:

```bash
docker compose exec app /app/.venv/bin/python \
  /app/.grok/skills/a2a-consult/scripts/a2a_consult.py "$@"
```

**Tip**: You can create a small wrapper script on the host for convenience:

```bash
#!/usr/bin/env bash
# Save as ~/bin/docker-a2a-consult and make it executable
docker compose -f ~/Downloads/work/a2a_local/docker/docker-compose.yml \
  exec -T app /app/.venv/bin/python \
  /app/.grok/skills/a2a-consult/scripts/a2a_consult.py "$@"
```

Then use it like:

```bash
docker-a2a-consult claude "ช่วยอธิบายโค้ดส่วนนี้" --workspace .
```

---

### 5. Restart Grok

After any installation method, completely quit and restart Grok so it loads the new skill.

## Usage

Once installed, you can use it like this:

### From Grok (natural language)

```bash
cd ~/projects/my-project

grok "ช่วย refactor โมดูลนี้ โดย consult กับ Claude Code หน่อย"
```

Grok should automatically detect and use the `a2a-consult` skill.

### Direct Skill Invocation

```bash
a2a-consult claude "ช่วยเขียน unit test ให้ฟังก์ชันนี้" --workspace .

a2a-consult codex "implement feature login ด้วย clean architecture"

# Use the multi-agent runner explicitly when you want turn-taking.
a2a-consult codex "compare options with the other agents" --council --max-rounds 6
```

### With Custom Workspace

```bash
a2a-consult claude-code "รีวิวโค้ดส่วนนี้" --workspace /path/to/project-a

a2a-consult claude-code "รีวิวแล้วให้ agent อื่นถกต่อ" --workspace /path/to/project-a --council --max-rounds 4
```

## Configuration

| Environment Variable | Description | Default |
|----------------------|-------------|---------|
| `A2A_LOCAL_ROOT`     | Path to your cloned `a2a_local` repository | `/Users/terng/Downloads/work/a2a_local` |
| `NATS_URL`           | NATS server URL | `nats://localhost:4222` |
| `SESSION`            | A2A session name | `collab` |

You can override it per command:

```bash
A2A_LOCAL_ROOT=/path/to/your/a2a_local a2a-consult claude "..." 
```

## Troubleshooting

- **Skill not appearing**: Make sure you restarted Grok completely after copying the files.
- **"No module named 'nats'"**: Ensure `A2A_LOCAL_ROOT` points to a directory where you have `nats-py` and `synadia-ai-agents` installed in the active Python environment.
- **Target AI not found**: Make sure the adapter was started with the same `--owner`, `--session-name`, and `--workspace` you are consulting. Use `python $A2A_LOCAL_ROOT/scripts/discover_agents.py --owner $USER --session collab` to check which agents are currently running on NATS.
- **Need multi-agent turn-taking**: Add `--council --max-rounds N`. The default mode calls only the selected target agent.

## Related Tools

- `scripts/discover_agents.py --ping-pong` — Test if two agents can communicate
- `docker/` — Run the entire A2A system in Docker (with host CLI support)

---

After installation, you can ask Grok things like:

> "ไปที่โฟลเดอร์ Project A แล้ว consult กับ Claude ว่าเมื่อวานทำงานอะไรไปบ้าง"
