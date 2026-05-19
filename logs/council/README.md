# Council Logs

This directory stores generated C2 council artifacts.

Default runner output now uses timestamped files:

- `<run-id>_history.json`
- `<run-id>_transcript.md`

Older manually named test outputs are kept here as historical evidence of
protocol debugging and live agent runs.

Use `--run-id <name>` for a stable pair of filenames, or pass
`--history-file` / `--transcript-file` when a specific output path is needed.
