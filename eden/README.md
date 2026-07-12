# Eden hook — gitmynotes

This folder wires **gitmynotes** into the **Eden constellation**: 'get my notes',
distilled through **Claude Fable 5**, fired by the Shadow Garden launcher's one
input.

```
eden/
  fable5.py      →  native communication layer to Claude Fable 5
  eden_notes.py  →  gathers your notes and surfaces what matters via Fable 5
```

## Run it

Standalone:

```bash
python eden/eden_notes.py "what should I focus on today"
```

Or let the Shadow Garden launcher call it — from `../shadow-garden-launcher`:

```bash
python eden/launch.py "what should I focus on today"
```

The hook reads this repo's live notes (`currentnote.txt`, `todo.md`) and asks
Fable 5 for the three most relevant items for your intent. With no API key set it
prints the raw notes instead, so it always does something useful.

## Fable 5 native comms

`fable5.py` is identical to `eden/fable5.py` in the sibling repos — one shared
way to talk to `claude-fable-5`, with an opt-in **server-side refusal fallback**
to `claude-opus-4-8`.

```bash
pip install anthropic
export ANTHROPIC_API_KEY=sk-ant-...   # or: ant auth login
```

## Honest scope

- Reads notes from **your local clone**; it does not reach any external note
  store you have not configured.
- Fable 5 distillation needs **your own API key**; without one it degrades to a
  plain notes dump.
