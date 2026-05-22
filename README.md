# GitMyNotes
## GitMyNotes adds convenient version control, off-site backups, and optional collaboration to your macOS Notes.

A lightweight macOS utility using Python and AppleScript to sync your macOS Notes to your public or private GitHub repos (or, optionally, a local only backup). The GitMyNotes solution exports Notes to Markdown in a local directory, while preserving folder organization and formatting. It features out-of-the-box common sense defaults or user-driven customization, a local audit trail file with checkpoint features for interrupted backups, and secure GitHub integration. All processing happens on your machine, with the only external data transmission secured by your enterprise-grade GitHub authentication credentials.


# GitMyNotes is for me?

Do you use Notes? Do you use GitHub? Then undoubtedly yes!

Do you use Notes and could [start with GitHub](https://docs.github.com/en/get-started/start-your-journey)? Then also yes!

`writing is re-writing`
Transform your macOS Notes into a version-controlled archive on GitHub. Use GitMyNotes to preserve and maintain your most excellent lines via versioning to track the full evolution of your work. Learn how to GitHub using branches and forks to explore your ideas, in trusted collabs, or on your own.


`IT team gotta keep copies`
Concerned about a fleet of MacBooks, and all the useful, non-shareable, and non-collaborative notes just one cup of coffee away from disaster? Use GitMyNotes on a cronjob on every Mac to keep versioned copies of valuable Notes.


`prepared tech workers win`
No one can predict the future. Losing a job or a role shouldn't mean losing your personal MacOS Notes as well. Set up a free GitHub repo and use GitMyNotes to back up the folders that hold your personal reminders, thoughts, and plans.


`but... I dont use Github (yet?)`
Simply set '--local-only' when you run the command to create, surprise, local-only backups. No GitHub required. But, really, you should [set up](https://docs.github.com/en/get-started/start-your-journey) a free GitHub repo.


## Getting Started

### Prerequisites
1. MacOS with Notes app and AppleScript (ships with every Mac)
2. Python 3.x+
3. Install Python dependencies: `pip install -r requirements.txt` (just `ruamel.yaml`, used for round-trip-safe config edits)
4. **pandoc** (default output format only): `brew install pandoc`. GitMyNotes uses pandoc to convert each note's HTML body to GitHub-flavored markdown. If you don't want to install pandoc, see the "Output format" section below — there's a one-line config flip that disables the conversion and writes raw HTML inside the `.md` files instead.
5. GitHub repo (eg, `https://github.com/<MYUSERNAME>/gitmynotes`) accessible from the Mac running this script. Can be public or private, must be configured working auth credentials, etc.


## Steps 1-2-3
1. First, clone the repo: `git clone https://github.com/mariochampion/gitmynotes.git`

2. Next, `cd` into gitmynotes dir: `cd path/to/gitmynotes`

3. Then, in file `gmn_config.yaml`, set the required Github url to your Github url

	-- REQUIRED TO CHANGE--
	
	set `DEFAULT_GITHUB_URL` to the the repo where you want to store Notes.
	
	example: `'DEFAULT_GITHUB_URL': 'https://github.com/<ChangeMe>/gitmynotes'`
	
	OPTIONAL: The additional `DEFAULT_*` configs: Leave as-is or change them.
	



## Usage

That's it! Now run the script:

`python gitmynotes.py` to run against default "Notes" folder. 

Or be more specific with:

`python gitmynotes.py [--folder='<notesFolderName>' --max-notes=<N> --print-level=results]`

Learn more with:

`python gitmynotes.py --help`



## Better usage

Do this once: set an [alias in your bash profile](https://www.google.com/search?q=set+up+alias+in+mac+bash+profile):`alias gitmynotes='python gitmynotes.py'`

From then on, just use `gitmynotes` as in `gitmynotes --folder='myPythonNotes' --maxnotes=20`

or `gitmynotes --help`


## Auto mode (for unattended / scheduled runs)

`--auto` walks every folder GitMyNotes already knows about and backs up only what's changed since each folder's last successful run. It pairs with `--yes` to make GitMyNotes safe to run unattended from cron, a Cowork routine, or any other scheduler.

The workflow is two steps:

1. **Seed each folder once.** Run `gitmynotes --folder=<name> --max-notes=1` for each folder you want auto mode to manage. The first successful run records a per-folder modification-date watermark in `gmn_config.yaml`'s `USAGE_FOLDERS_PROCESSED`.
2. **From then on, use `--auto`.** Each subsequent run checks each known folder, skips folders with no changes since their watermark, processes the rest, and advances each folder's watermark on success. Folders with a still-null watermark are skipped with a yellow warning telling you which `--folder=<name>` to run to seed them.

Per-folder failures are isolated — one folder hitting an error (e.g. a folder you renamed or deleted in Notes.app) doesn't stop the others. The aggregate exit code reflects the worst per-folder outcome: `0` if every folder was clean (or had nothing to do), `2` if any folder ended partial or hit a hard failure.

For an unattended cron / Claude Co-work-routine run, the typical command is:

```
gitmynotes --auto --yes
```

If you know you've only been editing one specific folder and don't want `--auto` to walk every folder, narrow the run with `--folder=NAME`:

```
gitmynotes --auto --folder=myPythonNotes --yes
```

This still uses the watermark to skip notes that haven't changed since the last successful run — it just limits the scope to that one folder. The folder must already be in `USAGE_FOLDERS_PROCESSED` (i.e. seeded with one prior `--folder=NAME` run); otherwise the script hard-fails with a clear remediation message. A `DEFAULT_NOTES_FOLDER` set in config does NOT trigger this narrowing — you have to pass `--folder` explicitly on the CLI for it to take effect under `--auto`.


**Note: The reddit_<x>.py are WorkInProgress. Full guidance forthcoming.**


## 
#### Output Artifacts
-- Local --

1. New Notes folder: `<notesFolderName>_GitMyNotes` to store processed notes
2. New GitMyNotes audit file: `<notesFolderName>.csv` to track processed notes. The "Last Modified" column is recorded as `YYYY-MM-DD HH:MM:SS` (a locale-independent ISO timestamp) so it sorts and parses cleanly. (Audit files generated by versions of GitMyNotes prior to mid-2026 used a locale-formatted date string in this column; if you upgrade an existing repo, your CSV will hold a mix of formats — older rows in the original style, newer rows in ISO. Each row is internally consistent.)
3. Markdown copy of Notes from folder: `DEFAULT_EXPORT_PATH/<my-exported-note.md>`
4. POTENTIALLY: Unsupported notes (often a note with JUST an image) will be moved to `<notesFolderName>_unsupported`

-- Remote --
1. New GitHub directory: `DEFAULT_GITHUB_URL/DEFAULT_NOTES_WRAPPERDIR`
2. New Github sub-dir mapped to Notes folders: `DEFAULT_GITHUB_URL/DEFAULT_NOTES_WRAPPERDIR/<notesFolderName>`
3. Github copy of Notes from folder: `DEFAULT_GITHUB_URL/DEFAULT_NOTES_WRAPPERDIR/<notesFolderName>/<a-note.md>`
4. OPTIONAL - GitMyNotes audit file: `<notesFolderName>.csv`



## Output format

By default, each exported note is committed as proper GitHub-flavored markdown with a YAML frontmatter header. The frontmatter carries three fields, recovered directly from Notes.app:

```
---
title: 'Original note title (with whatever characters Notes.app allowed)'
creation_date: '2024-06-01T10:00:00'
modification_date: '2026-05-09T12:34:56'
---

The body of your note as real markdown.
```

The frontmatter is parseable by anything that reads YAML (Python, Obsidian, Hugo, Jekyll, Astro, plain `yaml.safe_load`, etc.) — useful both for downstream tooling and for AI-assisted analysis of your own notes. The `title` field preserves the original unsanitized note title from Notes.app, which is otherwise lost in the GitMyNotes filename sanitization (lowercased, non-alphanumerics replaced with dashes).

Markdown conversion happens via pandoc (`pandoc -f html-native_divs -t gfm`), which handles paragraphs, lists, tables, inline formatting (bold, italic, code), and links cleanly. Notes.app attachment placeholders (drawings, embedded images) cannot survive the round trip — they reference internal Notes.app IDs that aren't part of the exported HTML — so those will appear as broken or absent in the output regardless of conversion.

**If you don't want or can't install pandoc**, set the simple boolean in `gmn_config.yaml`:

```
# Set to False to skip pandoc conversion and output raw HTML inside the .md files
CONVERT_TO_MARKDOWN: false
```

This disables the pandoc step entirely and falls back to the pre-2026 output: each `.md` file contains the raw HTML body with two `<div>` headers for Creation Date and Modification Date prepended. GitHub still renders this acceptably (markdown allows raw HTML) but downstream parseability is lost. You can flip back to `true` later — existing committed files won't be re-processed automatically; they'll migrate gradually as each note is edited and re-exported.

The older string key `'DEFAULT_BODY_FORMAT': 'html'` (or `'markdown'`) is still honored if `CONVERT_TO_MARKDOWN` is not present in your yaml. The boolean form is now the recommended way to choose output style.



## A note on locked notes (important)

macOS Notes distinguishes two states for password-protected notes: **closed** (currently showing the lock screen, body hidden) and **open** (unlocked in your current Notes.app session, body visible). GitMyNotes handles these differently:

- **Locked and closed** — AppleScript returns an empty body. GitMyNotes commits a stub file (title + dates + a marker saying the content wasn't exported) to GitHub. No cleartext leaves your Mac.
- **Locked and open** — AppleScript returns the real content, same as any unlocked note. GitMyNotes has no way to tell this case apart, so the cleartext body **will be committed to GitHub**.

macOS does not expose a "locked" status to AppleScript, so GitMyNotes cannot detect this automatically. If you want to keep a locked note's contents private, close it (click away so it re-locks, or close the Notes app) before running GitMyNotes. A note currently showing its lock screen is safe; a note you've unlocked in this session is not.



## HELP and COMMAND list


```
Export macOS Notes to GitHub repo (or local-only directory)

usage: gitmynotes.py [--folder FOLDER] [--maxnotes MAX_NOTES] [--restore RESTORE_NOTES]
                        [--force] [--batch-size BATCH_SIZE] [--export-path EXPORT_PATH]
                        [--github-url GITHUB_URL] [--newline-delimiter NEWLINE_DELIMITER] 
                        [--audit-file-ending AUDIT_FILE_ENDING] or [-h]


options:
FREQUENTLY USED
  -h, --help            show this help message and exit
  
  --folder FOLDER       [str] Specific Notes folder to export.
                        (default: 'Notes')
  
  --max-notes, --maxnotes, --max MAX_NOTES
                        [int] Maximum number of notes to process in this run.
  
  --restore-notes RESTORE_NOTES, --restorenotes RESTORE_NOTES, --restore RESTORE_NOTES
                        [str] Options: 'empty' or 'always' or 'never'. 
                        Determines when to move  notes from '<FOLDER>___GitMyNotes' back 
                        to their original source folder. 
                        Set 'empty' to restore when notecount is 0 in source folder, 
                        Set 'always' to restore at the end of each GitMyNotes run. 
                        Set to 'never' to, well, never move notes back to source folder.
                        (default: 'empty')                        
  
  --print PRINT, --print-level PRINT
                        [str] Optional set to 'none', 'results', 'debug', 'all' for increasing 
                        details. Useful for tracking code flow and general debugging.
                        (default: 'all')

  --auto                [bool] Use as '--auto' (no value allowed) to back up every folder
                        GitMyNotes already knows about (those listed in 'USAGE_FOLDERS_PROCESSED'
                        in 'gmn_config.yaml'), but only the notes that have changed since each
                        folder's last successful run.  Skips folders with no recorded watermark
                        (instructs you to seed them with one manual '--folder=NAME' run first).
                        Suppresses the 5x-batch confirmation entirely. Per-folder failures are
                        isolated -- one stale folder doesn't stop the others. Combine with
                        '--yes' for unattended scheduled / cron / Cowork-routine runs.
                        Combine with '--folder=NAME' to narrow the auto run to a single known
                        folder (still watermark-aware) instead of walking every folder.
                        (default: off)

                        
LESS FREQUENTLY USED                        
  --batch-size BATCH_SIZE
                        [int] The number of notes to convert, and git add/commit/push per loop, 
                        calculated a max-notes/batch-size. Especially useful for initial runs.
                        (default: 10)
  
  --export-path EXPORT_PATH, --exportpath EXPORT_PATH
                        [str] Path to export the notes (default: ~/Documents/gitmynotes)
  
  --force               [bool] Use as '--force' (no 'true' or 'false' value allowed) 
                        Use to over-ride to the default required user confirmation to process 
                        the full count of Notes in the specified folder when it exceed 
                        5x the batch size -- which could be hundreds of notes and 
                        could take a looooong time.(default: confirmation will be required)                        
  
  --yes, --non-interactive
                        [bool] Use as '--yes' or '--non-interactive' (no value allowed)
                        for scheduled / non-terminal runs (cron, Cowork routines, CI).
                        Implies '--force' (skips the 5x-batch confirmation) and also
                        fails fast with a clear error if 'DEFAULT_GITHUB_URL' still
                        contains the '<ChangeMe>' placeholder, instead of hanging on
                        the interactive setup prompt.
                        (default: interactive prompting is allowed)
  
  --local-only          [bool] Use as '--local-only' (no 'true' or 'false' value allowed) 
                        Use to over-ride to the default action of backing up notes to GitHub. 
                        When set, only a local copy of notes will be made. 
                        (DEFAULT: Send notes to GitHub repo)
  
  --github-url GITHUB_URL, --githuburl GITHUB_URL
                        [str] GitHub repository URL. 
                        (default: https://github.com/<ChangeMe>/gitmynotes)

  --notes-account NOTES_ACCOUNT, --notesaccount NOTES_ACCOUNT
                        [str] macOS Notes account name (e.g. 'iCloud', 
                        'On My Mac'). Used to scope every AppleScript op to a 
                        single account. Most users want 'iCloud'.
                        (default from config: 'iCloud')
  
  --newline-delimiter NEWLINE_DELIMITER, --newlinedelimiter NEWLINE_DELIMITER
                        [str] Default CSV newline delimiter (default: '|||')
  
  --audit-file-ending AUDIT_FILE_ENDING, --auditfileending AUDIT_FILE_ENDING
                        [str] The audit file extension (default: '.csv')

```


## Exit codes

GitMyNotes exits with one of three codes so you can chain it cleanly in shell scripts and scheduled / non-interactive runs (cron, Cowork routines, CI). Check with `echo $?` after a run.

- `0` — full success. The run did everything it set out to do. Includes happy-path runs, no-op runs (empty folder, `--max-notes 0`), runs whose only "issue" was closed-locked notes committed as stubs (that's the documented behavior, not a partial outcome), `--local-only` runs that completed the local export, and runs where you typed `x` at the 5x-batch confirmation prompt (clean user-initiated abort -- nothing happened).

- `1` — hard failure. The run could not proceed. Triggers: `DEFAULT_GITHUB_URL` still contains `<ChangeMe>` and `--yes` is set; `--folder` was omitted and `DEFAULT_NOTES_FOLDER` is empty in the config; or other config / startup errors that make any further work pointless. No useful work was done.

- `2` — partial success. The run did some work but didn't complete cleanly. Triggers: an unsupported (image-bearing) note aborted a batch mid-flight (notes before it were exported and committed; the bad note went to `<folder>_unsupported`; remaining notes are left for the next run); the git push failed after a successful local commit (work is committed locally and recoverable on the next run); or moving the processed notes back into `<folder>__GitMyNotes` failed after a successful export and commit.

A partial-success run is safe to re-run -- the same notes won't be duplicated, and the work that already landed stays landed.


### copyright 2026 mariochampion.com all rights reserved.
