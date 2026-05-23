#!/usr/bin/env python3
"""Export all macOS Notes to one paste-friendly markdown file for Gemini."""

import html
import re
import subprocess
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path


class PlainTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self._skip = True
        elif tag in {"br", "p", "div", "li", "h1", "h2", "h3", "h4", "tr"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self._skip = False
        elif tag in {"p", "div", "li", "h1", "h2", "h3", "h4", "tr"}:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)

    def text(self):
        raw = "".join(self.parts)
        raw = html.unescape(raw)
        raw = re.sub(r"[ \t]+\n", "\n", raw)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        return raw.strip()


def html_to_text(body: str) -> str:
    parser = PlainTextExtractor()
    parser.feed(body or "")
    return parser.text() or "(empty note)"


def fetch_notes():
    script = r'''
    set out to ""
    set recordSep to "===GMN_RECORD==="
    set fieldSep to "===GMN_FIELD==="
    tell application "Notes"
        repeat with acct in accounts
            set acctName to name of acct
            repeat with fld in folders of acct
                set fldName to name of fld
                repeat with n in notes of fld
                    set noteTitle to name of n
                    set noteBody to body of n
                    set noteCreated to creation date of n as string
                    set noteModified to modification date of n as string
                    set out to out & recordSep & acctName & fieldSep & fldName & fieldSep & noteTitle & fieldSep & noteCreated & fieldSep & noteModified & fieldSep & noteBody
                end repeat
            end repeat
        end repeat
    end tell
    return out
    '''
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def main():
    raw = fetch_notes()
    records = [chunk for chunk in raw.split("===GMN_RECORD===") if chunk.strip()]

    lines = [
        "# macOS Notes export for Gemini",
        f"Exported: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Total notes: {len(records)}",
        "",
        "Paste this whole file into Gemini, or copy one note section at a time.",
        "",
        "---",
        "",
    ]

    toc = ["## Table of contents", ""]
    sections = []

    for idx, record in enumerate(records, start=1):
        parts = record.split("===GMN_FIELD===", 5)
        if len(parts) < 6:
            continue
        account, folder, title, created, modified, body = parts
        title = title.strip() or "(untitled)"
        plain = html_to_text(body)

        anchor = f"note-{idx}"
        toc.append(f"{idx}. [{title}](#{anchor}) — {folder}")
        sections.extend([
            f"<a id=\"{anchor}\"></a>",
            f"## {idx}. {title}",
            f"**Folder:** {account} / {folder}  ",
            f"**Created:** {created}  ",
            f"**Modified:** {modified}",
            "",
            plain,
            "",
            "---",
            "",
        ])

    output = "\n".join(lines + toc + ["", "---", ""] + sections)
    out_path = Path.home() / "Documents" / "notes-for-gemini.md"
    out_path.write_text(output, encoding="utf-8")

    print(f"Exported {len(records)} notes")
    print(f"File: {out_path}")
    print(f"Size: {out_path.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
