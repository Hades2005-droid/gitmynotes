# Away Mode Automation

Use away mode to keep your local agent context fresh while you're gone.

## What it does each cycle

1. Runs `export_notes_for_gemini.py` to refresh:
   - `~/Documents/notes-for-gemini.md`
2. Runs `scripts/build_echo_agent_bundle.py` to refresh:
   - `~/Documents/echo-agent-bundle/framework.md`
   - `~/Documents/echo-agent-bundle/notes-for-gemini.md`
   - `~/Documents/echo-agent-bundle/generation-key.md`
   - `~/Documents/echo-agent-bundle/manifest.json`
   - `~/Documents/echo-agent-bundle/quickstart.md`

## Commands

```bash
cd ~/Desktop/Eden/gitmynotes
./scripts/away_mode.sh start
./scripts/away_mode.sh status
./scripts/away_mode.sh stop
```

## Interval

Default interval is every 15 minutes.

Override with env var:

```bash
ECHO_AWAY_INTERVAL_SECONDS=600 ./scripts/away_mode.sh start
```

## Logs

Logs are written to:

`~/Documents/framework-demos/automation-logs/away_mode.log`

