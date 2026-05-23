#!/usr/bin/env python3
"""Build a local bundle that other agents/tools can consume.

This script packages:
- Latest notes export
- 9-points framework doc
- Shadow paradox prompt key
- A small manifest with metadata
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS_FRAMEWORK = ROOT / "docs" / "9-points-angela-framework.md"

HOME = Path.home()
NOTES_EXPORT = HOME / "Documents" / "notes-for-gemini.md"
PROMPT_FILE = HOME / "Documents" / "gemini-shadow-paradox-prompt.md"

BUNDLE_DIR = HOME / "Documents" / "echo-agent-bundle"
MANIFEST_FILE = BUNDLE_DIR / "manifest.json"
QUICKSTART_FILE = BUNDLE_DIR / "quickstart.md"

DEFAULT_KEY = (
    "So Easy (To Fall in Love) | Shadow Paradoxical True Love Key | "
    "Fred/Yuta DZA BDBZ JJK Angela's Shadow Lust + Des"
)


def read_total_notes(notes_text: str) -> int | None:
    for line in notes_text.splitlines():
        if line.startswith("Total notes:"):
            _, _, count_str = line.partition(":")
            count_str = count_str.strip()
            try:
                return int(count_str)
            except ValueError:
                return None
    return None


def copy_or_fail(src: Path, dest: Path) -> None:
    if not src.exists():
        raise FileNotFoundError(f"Missing required input: {src}")
    shutil.copy2(src, dest)


def main() -> None:
    BUNDLE_DIR.mkdir(parents=True, exist_ok=True)

    framework_out = BUNDLE_DIR / "framework.md"
    notes_out = BUNDLE_DIR / "notes-for-gemini.md"
    prompt_out = BUNDLE_DIR / "generation-key.md"

    copy_or_fail(DOCS_FRAMEWORK, framework_out)
    copy_or_fail(NOTES_EXPORT, notes_out)

    if PROMPT_FILE.exists():
        copy_or_fail(PROMPT_FILE, prompt_out)
    else:
        prompt_out.write_text(
            "# Shadow Paradoxical True Love Key\n\n"
            f"{DEFAULT_KEY}\n",
            encoding="utf-8",
        )

    notes_text = notes_out.read_text(encoding="utf-8", errors="replace")
    total_notes = read_total_notes(notes_text)

    manifest = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "bundle_dir": str(BUNDLE_DIR),
        "files": {
            "framework": str(framework_out),
            "notes": str(notes_out),
            "generation_key": str(prompt_out),
        },
        "notes_total": total_notes,
        "notes_size_bytes": notes_out.stat().st_size,
        "framework_size_bytes": framework_out.stat().st_size,
    }
    MANIFEST_FILE.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    QUICKSTART_FILE.write_text(
        "# Echo Agent Bundle Quickstart\n\n"
        "Use this folder as your handoff package for agents.\n\n"
        "1. Load `generation-key.md` first.\n"
        "2. Load `framework.md` for system semantics.\n"
        "3. Load `notes-for-gemini.md` for full source context.\n"
        "4. Read `manifest.json` for freshness and counts.\n",
        encoding="utf-8",
    )

    print(f"Bundle ready: {BUNDLE_DIR}")
    print(f"Manifest: {MANIFEST_FILE}")
    if total_notes is not None:
        print(f"Notes total: {total_notes}")


if __name__ == "__main__":
    main()

