# Docker Setup for Agent Community Protocol

This setup allows you to run the multi-agent council in a clean, reproducible environment while still being able to call your local `claude`, `codex`, and `grok` CLIs on the host machine (especially useful on macOS).

## Quick Start (Using Host .venv - Recommended for fast testing)

```bash
# On your host (one time)
python3 -m venv .venv
source .venv/bin/activate
pip install nats-py synadia-ai-agents

cd docker
docker compose up --build
```

**Note**: NATS is exposed on **localhost:4223** on your host machine (not 4222).  
If you want to connect to it from your host (e.g. using `nats` CLI), use:

```bash
nats --server nats://localhost:4223
```

The council will start automatically with a sample topic.

## Using with Host CLIs

The container is configured to see your host's:
- `claude`
- `codex` 
- `grok`

binaries through volume mounts.

This means:
- Your existing authentication (tokens, configs) will be used
- You don't need to install the CLIs inside the container

## Common Commands

```bash
# Run with auto-discovery first (recommended)
docker compose run --rm app \
  python scripts/run_c2_council.sh --discover "Your topic here" --max-rounds 6

# Run a specific command inside the container
docker compose run --rm app bash

# Stop everything
docker compose down
```

## Important Notes

- NATS runs as a separate service on port 4222 **inside the container**.
- On the host, it is exposed on port **4223** (to avoid conflict with any local NATS you may have running).

### Using Host Virtual Environment (Fast Testing - Option A)

By default, the container uses `/app/.venv/bin/python`.

This means:
- You must create and install dependencies in `.venv` **on your host machine first**.
- The container will automatically use the same packages (including `synadia-ai-agents` and `nats-py`).

Recommended setup on host:

```bash
# On your host machine
python3 -m venv .venv
source .venv/bin/activate
pip install nats-py synadia-ai-agents
```

Then run Docker as usual. The mounted project will bring your `.venv` into the container.
- The Python environment inside Docker has `nats-py` pre-installed.
- The correct package is `synadia-ai-agents` (not `synadia-ai`).
  ```bash
  pip install nats-py synadia-ai-agents
  ```

## Future Improvements

- Better handling of `synadia-ai`
- Support for running only specific agents
- One-command `make docker-up`

## Troubleshooting

If the container cannot find `claude` / `codex` / `grok`:

```bash
docker compose run --rm app which claude
docker compose run --rm app which codex
```

If they are not found, you may need to adjust the volume mounts in `docker-compose.yml` for your specific macOS setup.