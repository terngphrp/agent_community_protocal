# Contributing to Agent Community Protocol

Thank you for your interest in the Agent Community Protocol! We welcome contributions of all kinds — new adapters, protocol improvements, documentation, tests, and ideas.

## Ways to Contribute

- **New Adapters** — Add support for other agents (`aider`, `opencode`, custom tools, etc.)
- **Protocol Improvements** — Structured handoff envelopes, better violation reporting, durable memory backends
- **Documentation & Specs** — Clarify the protocol, write interoperability tests, improve examples
- **Bug Reports & Feature Requests** — Open clear issues with reproduction steps

## Development Setup

```bash
# Clone the repo
git clone https://github.com/terngphrp/agent_community_protocal.git
cd agent_community_protocal

# Run protocol tests (no NATS required)
python -m unittest -v test_c2_council_runner.py

# Optional: install development tools
pip install -e ".[dev]"
```

## Code Style

- Follow PEP 8 + the `ruff` configuration in `pyproject.toml`
- Keep `protocol.py` dependency-free (this is critical)
- Write tests for new protocol logic in `test_c2_council_runner.py`
- Prefer small, focused functions

## Submitting Changes

1. Fork the repository
2. Create a feature branch (`feat/my-cool-adapter` or `fix/handoff-edge-case`)
3. Make your changes + add tests when applicable
4. Run `python -m unittest` and `ruff check .`
5. Open a Pull Request with a clear description

## Protocol Changes

If your contribution changes the core protocol (handoff rules, termination semantics, subject patterns, etc.), please:

- Update `protocol.py` and its tests
- Document the change in `docs/PROTOCOL.md` (or propose a new spec document)
- Discuss in an issue first when possible

## Code of Conduct

Be respectful and collaborative. We are building a community around reliable, auditable multi-agent systems.

---

Questions? Open an issue or start a discussion. We look forward to your contributions!