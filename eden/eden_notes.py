#!/usr/bin/env python3
"""Eden notes hook — 'get my notes', distilled through Claude Fable 5.

Called by the Shadow Garden launcher with the one input, or standalone:

    python eden/eden_notes.py "<intent>"

It gathers this repo's current note(s) and asks Fable 5 to surface what matters
for the given intent. With no API key it falls back to printing the raw notes,
so the hook is always useful.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent      # .../gitmynotes/eden
REPO_ROOT = HERE.parent                      # .../gitmynotes
sys.path.insert(0, str(HERE))               # so `import fable5` works as a script

# Where this repo keeps live notes; add more filenames as the repo grows.
NOTE_SOURCES = ["currentnote.txt", "todo.md"]


def gather_notes() -> str:
    chunks = []
    for name in NOTE_SOURCES:
        path = REPO_ROOT / name
        if path.exists():
            chunks.append(f"# {name}\n{path.read_text(errors='replace')}")
    return "\n\n".join(chunks).strip()


def main(argv=None) -> None:
    argv = argv if argv is not None else sys.argv[1:]
    intent = " ".join(argv).strip() or "surface what matters now"

    notes = gather_notes()
    if not notes:
        print("[eden-notes] No notes found (" + ", ".join(NOTE_SOURCES) + ").")
        return

    try:
        from fable5 import Fable5, has_credentials

        if not has_credentials():
            raise RuntimeError("no ANTHROPIC_API_KEY set")

        digest = Fable5().ask(
            f"Intent: {intent}\n\nMy notes:\n{notes}\n\n"
            "Return the 3 most relevant items for this intent as a tight bullet list.",
            system="You surface notes for the Shadow Garden. Be concise and specific.",
            max_tokens=600,
        )
        print("[eden-notes] Fable 5 digest:\n" + digest.strip())
    except Exception as exc:  # network / no-key / refusal all fall back to raw
        print(f"[eden-notes] Fable 5 unavailable ({exc}); raw notes:\n{notes}")


if __name__ == "__main__":
    main()
