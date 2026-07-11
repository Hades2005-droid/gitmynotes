#!/usr/bin/env python
"""GitMyNotes -- back up Apple Notes (Notes.app) folders to a GitHub repo as Markdown.

For each configured folder, the script drives Notes.app via AppleScript /
osascript to export every note's HTML body, optionally converts it to GFM
Markdown via pandoc (R8), writes a per-note .md file with YAML frontmatter,
commits the result to a local git repo, and pushes to a configured GitHub
remote. A per-folder CSV append-only audit log is appended on every run.

Configuration lives in `gmn_config.yaml` next to this script. The file is
edited in-place to advance per-folder mod-date watermarks and run-count
usage totals (see update_yaml_config_multi for the single-write-per-run
guarantee). Every DEFAULT_* value can be overridden per run via CLI flags;
see `python gitmynotes.py --help` for the full list, and the USING THIS
SCRIPT block below for common invocations.

Entry points worth knowing:
  - main()                      -- single CLI run; orchestrates everything.
  - process_one_folder()        -- the per-folder pipeline (count -> export
                                   -> commit/push -> audit -> move -> restore
                                   -> watermark advance); called once
                                   normally or repeatedly under --auto.
  - export_notes_to_markdown()  -- the AppleScript driver that does the
                                   actual Notes.app export per batch.
  - applescript_escape()        -- single source of truth for escaping any
                                   user-supplied string before it's embedded
                                   into an AppleScript "..." literal

macOS-only (depends on Notes.app + osascript). External deps: `ruamel.yaml`
(pinned in requirements.txt) for round-trip config edits, and `pandoc` (a
hard prereq when CONVERT_TO_MARKDOWN is true / DEFAULT_BODY_FORMAT is 'markdown',
the default). Set CONVERT_TO_MARKDOWN: false (or the legacy 'html' value) to
remove the pandoc prereq at the cost of raw-HTML-in-.md file.

Operational notes:
  - Non-interactive / unattended runs (Cowork routines, cron, CI): pair
    --auto with --yes. Exit codes follow the cross-cutting
    taxonomy: 0 = clean, 1 = hard failure, 2 = partial success.
  - Side-channel files (`currentnote.txt`, `metadata_rows.txt`) live next
    to this script; both are .gitignored. 
  - The append-only audit CSV per folder doubles as a backup index using ISO
    formatted dates(YYYY-MM-DD HH:MM:SS).

License: AGPL-3.0. See the LICENSE banner below for full credits.
"""
## ===================================================================
## GitMyNotes - LICENSE AND CREDITS
## This app/collection of scripts at https://github.com/mariochampion/gitmynotes
## released under the GNU Affero General Public License v3.0
##
## 
## GitMyNotes scripts crafted and copyright 2025-2026 by mario champion (mariochampion.com)
##
## please open issues and pull requests and comments
## thanks and always remember: this robot loves you. 
## boop boop!!!
## ===================================================================


#### USING THIS SCRIPT

## Export up to 10 notes from a specific folder
#  python gitmynotes.py --folder="somefolder" --max-notes=10

## Export all notes from a specific folder
#  python gitmynotes.py --folder="somefolder"

## Specify to restore notes folder even if not emptied
#  python gitmynotes.py --folder="somefolder" --max-notes=10 --restore=always

## Long runs: every N batches (DEFAULT_LOOPCOUNT_BEFORE_CONFIRM, default 5) GitMyNotes pauses
## for a y/N/x confirmation before the next batch. Suppress with --force for interactive runs.
#  python gitmynotes.py --folder="somefolder" --max-notes=100 --force

## Unattended runs (Cowork routines, cron, CI): --yes / --non-interactive implies --force AND
## fails fast (exit 1) if gmn_config.yaml still has the <ChangeMe> GitHub URL placeholder.
#  python gitmynotes.py --folder="somefolder" --max-notes=100 --yes

## Watermark-aware backup of every folder GitMyNotes already knows about
#  python gitmynotes.py --auto --yes

## Watermark-aware backup of just one specific folder you know you've been editing
#  python gitmynotes.py --auto --folder="somefolder" --yes

## go crazy and specify nothing, to get all the defaults!
#  python gitmynotes.py


import subprocess
import os, sys
import re
import shutil
import argparse
import math
import csv
import logging
import time
from datetime import datetime
from typing import Tuple
from ruamel.yaml import YAML
from enum import Enum

class PrintLevel(Enum):
    NONE = 0
    RESULTS = 1
    DEBUG = 2
    ALL = 3


# Exit code taxonomy (cross-cutting, paired with logging to make
# non-interactive runs -- Cowork routines, cron, CI -- parseable):
#   EXIT_SUCCESS         = 0  -- run completed all intended work cleanly. Includes
#                                no-op runs (loop_count == 0), runs whose only
#                                "issue" was closed-locked notes committed as
#                                stubs (by design, not a partial outcome), runs
#                                with --local-only that complete the local work,
#                                and 'x' typed at the 5x-batch confirm prompt
#                                (clean user-initiated abort -- nothing happened).
#   EXIT_HARD_FAILURE    = 1  -- run could not proceed at all. Bad config, such as
#                                <ChangeMe> fail-fast under --yes), missing
#                                required args, invalid argparse value,
#                                or first-step setup failure that
#                                makes any further work pointless. No useful
#                                work was done.
#   EXIT_PARTIAL_SUCCESS = 2  -- run did some work but didn't complete cleanly.
#                                Mainly unsupported note aborted batch -- the
#                                notes before the bad one were exported, the rest
#                                are left for next run), git push failures after
#                                successful local commits (work is recoverable on
#                                next run, just not on GitHub yet), and
#                                move_processed_notes failures after a successful
#                                export+commit (notes are committed but still in
#                                the source folder, will re-export next run).
EXIT_SUCCESS = 0
EXIT_HARD_FAILURE = 1
EXIT_PARTIAL_SUCCESS = 2



# UNSUPPORTED_NOTE_ERROR_CODE: substring osascript prints to stderr when a
#  note's body can't be read (typically image-bearing notes).
# CHANGEME_PLACEHOLDER: sentinel left in DEFAULT_GITHUB_URL until the user
#  edits gmn_config.yaml. Drives the first-run interactive setup prompt and
#  the --yes fail-fast.
# USAGE_FOLDERS_PROCESSED:
# is a mapping rather than a list, and an empty mapping is the natural seed
# value -- no sentinel needed.
UNSUPPORTED_NOTE_ERROR_CODE = "type 100002"
CHANGEME_PLACEHOLDER = "<ChangeMe>"


# module-level logger. setup_logging() in main() attaches a
# FileHandler at <script_dir>/gitmynotes.log so info / warning / error events
# flow to a parseable record alongside the existing colored TTY output. Colored
# print_color() callsites are preserved as-is; logger.warning / logger.error /
# logger.exception calls are added in paired form at each warning/error site so
# non-interactive runs (Cowork routines, cron) get a structured log without
# ANSI codes. Chatty debug_print / results_print are deliberately untouched.
#
# Set the file handler / logger level from WARNING to INFO so the
# per-batch timing lines around osascript and pandoc land in the log. Filter
# with `grep '\[INFO\]' gitmynotes.log` for timing-only / `\[WARNING\]` or
# `\[ERROR\]` for problem events.
logger = logging.getLogger("gitmynotes")


# Optional Asana reporting connector (opt-in, non-blocking). Imported guardedly
# so a missing/broken asana_connector.py can never stop a notes backup. Enabled
# only when ASANA_ACCESS_TOKEN are set. All calls go through Asana adapter,
# which never raises and gracefully degrades if token not configured.
try:
    from asana_connector import AsanaConfig
    from adapters.asana_adapter import GitMyNotesAsanaReporter, SyncMetrics
    _asana_available = True
except Exception:  # noqa: BLE001 -- reporting is strictly optional
    _asana_available = False


def report_sync_to_asana(folder_name, notes_processed, notes_failed, sync_duration_ms, git_success, audit_file=None):
    """Best-effort, non-blocking Asana report of sync outcome.

    No-op unless the connector is importable and ASANA_ACCESS_TOKEN is set.
    Any failure is logged and swallowed so the run's exit code is unaffected.
    """
    if not _asana_available:
        return
    try:
        config = AsanaConfig.from_env()
        # Airtight guard: do nothing unless a token AND workspace are set.
        # Without this, no network call is ever attempted (no-op + local log).
        if not config.enabled:
            return
        reporter = GitMyNotesAsanaReporter(config)
        metrics = SyncMetrics(
            timestamp=datetime.now().isoformat(),
            folder_name=folder_name,
            notes_processed=notes_processed,
            notes_failed=notes_failed,
            sync_duration_ms=sync_duration_ms,
            success=git_success and notes_failed == 0,
        )
        audit_entries = [f"audit file: {audit_file}"] if audit_file else []
        reporter.report_sync(metrics, audit_entries=audit_entries)
        logger.info(f"Asana report sent for folder '{folder_name}': {notes_processed} notes, success={git_success}")
    except Exception as exc:  # noqa: BLE001 -- reporting must never break the run
        logger.warning(f"Asana sync reporting failed (non-fatal): {exc}")




#### USER CONFIGS

PRINT_LEVEL = PrintLevel.ALL

def load_configs_from_file():
    """Load gmn_config.yaml from the current working directory and return it
    as a plain dict (safe loader -- no round-trip metadata preserved). Used
    once at startup by main() to populate DEFAULT_* values and usage counters;
    in-run mutations go through update_yaml_config / update_yaml_config_multi
    instead, which use ruamel's round-trip loader to preserve comments and
    formatting on the way back out.
    """
    yaml=YAML(typ='safe')   # default, if not specfied, is 'rt' (round-trip)
    loaded_configs = yaml.load(open("gmn_config.yaml"))

    return loaded_configs


# centralize escaping of user-supplied strings (folder names, account names,
# note titles, config-derived paths) before they're embedded into AppleScript
# string literals.
#
# Order matters: backslash MUST be escaped before doublequote. Otherwise the
# backslash we inserted to escape a quote gets re-escaped into '\\"', which
# AppleScript reads as a literal backslash followed by an unterminated string.
def applescript_escape(s):
    """Escape a Python string for safe embedding inside an AppleScript "..."
    string literal.

    Handles, in order: backslash (\\ -> \\\\), doublequote (" -> \\"), and the
    three whitespace chars that can terminate or otherwise confuse a literal
    on the macOS AppleScript parser (newline, carriage return, tab) -- each
    rewritten to its AppleScript escape sequence so the resulting literal is
    always on one line.

    Args:
        s: Any value. None / empty / non-str inputs return ''.

    Returns:
        str: escape-safe string, ready to drop between doublequotes inside an
        f-string-built AppleScript block.
    """
    if not s:
        return ''
    return (str(s)
        .replace('\\', '\\\\')   # MUST be first
        .replace('"',  '\\"')
        .replace('\n', '\\n')
        .replace('\r', '\\r')
        .replace('\t', '\\t'))


def setup_git_repo(repo_path, DEFAULT_GITHUB_URL):
    """Initialize a git repo at `repo_path` if one doesn't already exist there,
    set `origin` to `DEFAULT_GITHUB_URL`, force-rename the default branch to
    `main`, and pull any pre-existing remote content so subsequent commits
    rebase cleanly.

    Best-effort: every git subprocess call is wrapped in try/except. Failures
    are logged via logger.exception / logger.warning and surfaced in the TTY
    via print_color, but this function never raises -- the caller (main())
    continues into the export pipeline regardless. The rationale is that a
    repo that already exists locally will trip the `init` step harmlessly, and
    a missing-remote condition only matters at push time, which has its own
    error handling in git_add_commit_push.

    Args:
        repo_path (str): absolute path to the local export root that should be
            (or already is) a git repo.
        DEFAULT_GITHUB_URL (str): the configured GitHub remote URL. Used only
            on the first-run init path; not validated here.
    """
    
    if not os.path.exists(os.path.join(repo_path, '.git')):
        try:
            subprocess.run(['git', 'init'], cwd=repo_path)
            print_color(textcolor="green",msg=f"SUCCESS: GIT INIT with {repo_path}")
        except:
            logger.exception(f"ERROR: Did not GIT INIT {repo_path}")
            print_color(textcolor="red",msg=f"ERROR: Did not GIT INIT {repo_path}")
        try:
            subprocess.run(['git', 'remote', 'add', 'origin', DEFAULT_GITHUB_URL], cwd=repo_path)
            print_color(textcolor="green",msg=f"SUCCESS: GIT REMOTE ADD ORIGIN with {repo_path}")
        except:
            logger.exception(f"ERROR: Did not GIT REMOTE ADD ORIGIN with {repo_path}")
            print_color(textcolor="RED",msg=f"ERROR: Did not GIT REMOTE ADD ORIGIN with {repo_path}")
        try:
            subprocess.run(['git', 'branch', '-m', 'main'], cwd=repo_path)
            print_color(textcolor="green",msg=f"SUCCESS: GIT BRANCH -M MAIN with {repo_path}")
        except:
            logger.exception(f"ERROR: GIT BRANCH -M MAIN with {repo_path}")
            print_color(textcolor="red",msg=f"ERROR: GIT BRANCH -M MAIN with {repo_path}")


        # Add this to handle remote repository state
        try:
            subprocess.run(['git', 'pull', 'origin', 'main'], cwd=repo_path)
            print_color(textcolor="green",msg=f"Remote content pulled")
        except:
            logger.warning(f"No remote content to pull from {repo_path}")
            print_color(textcolor="magenta",msg=f"No remote content to pull")



def export_notes_to_markdown(DEFAULT_CURRENTNOTE_FILE, DEFAULT_METADATA_ROWS_FILE, export_path, notes_account, unsupported_folder_ending, body_format, folder_name=None, max_notes=None, wrapper_dir=None):
    """Export Notes using applescript/osascript with folder and count limits.

    notes_account scopes every Notes lookup (folder + iteration) to the specified
    account (e.g. 'iCloud', 'On My Mac'). Threaded through from --notes-account /
    DEFAULT_NOTES_ACCOUNT (R6).

    unsupported_folder_ending is the suffix appended to folder_name when the
    partial-export recovery path moves an image-bearing note to a sibling folder
    (e.g. folder 'plans' + ending '_unsupported' -> 'plans_unsupported'). Threaded
    through from DEFAULT_UNSUPPORTED_FOLDER_ENDING.

    body_format is 'markdown' or 'html' . In 'markdown' mode AppleScript writes
    each note's raw HTML body to a per-note '<cleanTitle>.html' temp file in the
    export path (no date <div> headers prepended); the caller's Python sweep then
    converts the .html to the final '<cleanTitle>.md' via pandoc and prepends YAML
    frontmatter. In 'html' mode AppleScript writes the HTML output
    directly: '<cleanTitle>.md' with the original <div>Creation/Modification
    Date</div> headers + raw HTML body, no Python conversion sweep needed.
    Either way the metadata-rows file (and thus the audit CSV) records the .md
    name, so downstream consumers stay agnostic to the mode.

    DEFAULT_METADATA_ROWS_FILE is the absolute path to the side-channel CSV file
    the AppleScript loop appends one row to per successfully-exported note
    ('title,quoted_title.md,YYYY-MM-DD HH:MM:SS'). Caller reads this file after
    the function returns and uses it to write the audit CSV. Truncated at
    function entry so stale rows from a prior batch can't pollute this one. On
    the type-100002 recovery path the file already contains rows for the
    goodnotes (1..i-1); on the success path it contains rows for all exported
    notes including stubs.
    """

    # clear any stale metadata rows from a prior batch / crashed run before
    # the AppleScript loop appends fresh rows. Same defensive truncation pattern
    # we use for currentnote.txt by virtue of always-overwriting.
    try:
        with open(DEFAULT_METADATA_ROWS_FILE, 'w') as f:
            f.write('')
    except OSError as exc:
        logger.warning(
            f"Could not truncate metadata rows file '{DEFAULT_METADATA_ROWS_FILE}' "
            f"before export ({exc}); audit row collection may be unreliable."
        )

    ## tell the people some information
    if (max_notes > 0 and folder_name !="" and wrapper_dir !=""):
        print_color(textcolor="white",msg=f"Starting export of {max_notes} Notes from '{folder_name}' into '{wrapper_dir}/{folder_name}'...")
    elif (max_notes > 0 and folder_name !="" and wrapper_dir==None):
        print_color(textcolor="white",msg=f"Starting export of {max_notes} Notes from '{folder_name}'...")
    elif (max_notes > 0 and folder_name==None and wrapper_dir==None):
        print_color(textcolor="white",msg=f"Starting export of {max_notes} Notes...")
    elif (max_notes==None and folder_name==None and wrapper_dir==None):
        print_color(textcolor="white",msg=f"Starting export of all Notes...")

    # escape every user-supplied string we're about to embed into AppleScript
    # string literals via applescript_escape (handles backslash, doublequote,
    # newline, CR, tab).
    notes_account_escaped = applescript_escape(notes_account)
    folder_name_escaped = applescript_escape(folder_name)
    export_path_escaped = applescript_escape(export_path)
    wrapper_dir_escaped = applescript_escape(wrapper_dir)
    currentnote_file_escaped = applescript_escape(DEFAULT_CURRENTNOTE_FILE)
    metadata_rows_file_escaped = applescript_escape(DEFAULT_METADATA_ROWS_FILE)

    # body_format selects which file the AppleScript repeat-loop writes per
    # note. 'markdown' mode writes raw HTML body to <cleanTitle>.html (no date
    # <div>s prepended) so the Python sweep can convert it via pandoc. 'html'
    # mode writes the legacy output directly to <cleanTitle>.md (date
    # <div>s + raw HTML body) -- byte-identical to what shipped before.
    if body_format == 'markdown':
        write_line = (
            'do shell script "echo " & quoted form of noteContent '
            '& " > " & quoted form of export_path_full & "/" & cleanTitle & ".html"'
        )
    else:
        # html mode -- legacy pre-R8 output exactly.
        write_line = (
            'do shell script "echo " & quoted form of noteCreateDate '
            '& quoted form of linebreaker & quoted form of noteModDate '
            '& quoted form of linebreaker & quoted form of noteContent '
            '& " > " & quoted form of export_path_full & "/" & fileName'
        )

    applescript = f'''
    tell application "Notes"
        set targetAccount to "{notes_account_escaped}"
        tell account targetAccount
        if length of "{folder_name_escaped}" > 0 then
            try
                set targetFolder to folder "{folder_name_escaped}"
                set allNotes to every note in targetFolder
                set export_path_full to "{export_path_escaped}/{wrapper_dir_escaped}/{folder_name_escaped}"
            on error
                log "Folder {folder_name_escaped} not found"
                return 0
            end try
        else
            set allNotes to every note
            set export_path_full to "{export_path_escaped}/{wrapper_dir_escaped}"
        end if
        
        set noteCount to (count of allNotes)
        if {max_notes} > 0 then
            set maxToProcess to {max_notes}
        else
            set maxToProcess to noteCount
        end if

        if maxToProcess < noteCount then
            set notesToProcess to maxToProcess
        else
            set notesToProcess to noteCount
        end if

        -- track empty/locked notes so caller can report them to the user.
        set lockedCount to 0
        set lockedMarker to "<div><i>[empty or locked note -- no content exported by GitMyNotes]</i></div>"

        repeat with i from 1 to notesToProcess
            set currentNote to item i of allNotes
            set noteTitle to the name of currentNote
            -- Write to file and track title for when unsupported note breaks.
            -- B9: use the absolute path the Python caller resolved for us (config
            -- value is anchored to the script dir in main() if it wasn't already
            -- absolute). Otherwise osascript's shell cwd (usually the user's home)
            -- and Python's cwd could disagree, leaving get_currentnote_data to
            -- silently read stale data from a previous run.
            do shell script "echo " & i & "++++" & quoted form of noteTitle & " > " & quoted form of "{currentnote_file_escaped}"
            --log ("Exporting note: " & noteTitle)

            set linebreaker to "\n"
            -- R5: capture the modification date once so we can build BOTH the
            -- HTML version (for the .md body) and a locale-independent ISO
            -- version (for the audit-row append below). Pre-R5 we re-fetched
            -- it inline twice; capturing once is cleaner and avoids any
            -- microsecond-window inconsistency.
            set theModDate to modification date of currentNote
            set noteCreateDate to "<div><b>Creation Date:</b> " & creation date of currentNote & "<br></div>"
            set noteModDate to "<div><b>Modification Date:</b> " & theModDate & "<br></div>"
            -- B4: fetching `body of` on a locked/password-protected note returns "" (not
            -- an error). Wrap in try as a belt-and-suspenders guard anyway, and substitute
            -- a stub marker for any empty body so the committed .md is self-explanatory
            -- instead of silently mostly-empty.
            try
                set noteContent to the body of currentNote
            on error
                set noteContent to ""
            end try
            if noteContent is "" then
                set noteContent to lockedMarker
                set lockedCount to lockedCount + 1
            end if

            -- Clean the title for use as filename
            set cleanTitle to do shell script "echo " & quoted form of noteTitle & " | sed 's/[^a-zA-Z0-9.]/-/g' | tr '[:upper:]' '[:lower:]'"
            set fileName to cleanTitle & ".md"

            -- Write to file. line built Python-side from body_format
            -- ('markdown' -> raw HTML body to <cleanTitle>.html for pandoc to
            -- convert; 'html' -> legacy date-divs + HTML body to <cleanTitle>.md).
            {write_line}

            -- build a locale-independent ISO date string from theModDate's
            -- components (mirrors the snippet that used to live in
            -- export_notes_metadata) and append a CSV-shaped row to the
            -- side-channel metadata file. Python reads this after osascript
            -- completes (success path AND type-100002 partial-bail) and
            -- uses it to write the per-folder audit CSV without firing a
            -- second osascript pass over the same notes (R5).
            set isoYear to year of theModDate as string
            set isoMonth to text -2 thru -1 of ("0" & ((month of theModDate) as integer))
            set isoDay to text -2 thru -1 of ("0" & day of theModDate)
            set isoHour to text -2 thru -1 of ("0" & hours of theModDate)
            set isoMin to text -2 thru -1 of ("0" & minutes of theModDate)
            set isoSec to text -2 thru -1 of ("0" & seconds of theModDate)
            set isoModDate to isoYear & "-" & isoMonth & "-" & isoDay & " " & isoHour & ":" & isoMin & ":" & isoSec
            -- R8: mirror the same component-build for the creation date so the
            -- per-note metadata side-channel carries both dates. Python uses
            -- the creation_date in YAML frontmatter; the audit CSV continues
            -- to record only modification_date in its 'Last Modified' column.
            set theCreateDate to creation date of currentNote
            set isoCreateYear to year of theCreateDate as string
            set isoCreateMonth to text -2 thru -1 of ("0" & ((month of theCreateDate) as integer))
            set isoCreateDay to text -2 thru -1 of ("0" & day of theCreateDate)
            set isoCreateHour to text -2 thru -1 of ("0" & hours of theCreateDate)
            set isoCreateMin to text -2 thru -1 of ("0" & minutes of theCreateDate)
            set isoCreateSec to text -2 thru -1 of ("0" & seconds of theCreateDate)
            set isoCreateDate to isoCreateYear & "-" & isoCreateMonth & "-" & isoCreateDay & " " & isoCreateHour & ":" & isoCreateMin & ":" & isoCreateSec
            -- Comma-strip the title for safe CSV embedding (matches the legacy
            -- export_notes_metadata cleaning). The original noteTitle is left
            -- alone so currentnote.txt + the B1 move_one_note path keep using
            -- the unmodified Notes.app name.
            set auditTitle to do shell script ("echo " & quoted form of noteTitle & " | sed 's/,/-/g'")
            -- R8 metadata-row format: title,quoted_title.md,iso_mod_date,iso_creation_date
            -- (extended from the R5 3-field shape; read_metadata_rows handles both
            -- shapes for backward-compat with any leftover pre-R8 file).
            set auditRow to auditTitle & "," & fileName & "," & isoModDate & "," & isoCreateDate
            do shell script "echo " & quoted form of auditRow & " >> " & quoted form of "{metadata_rows_file_escaped}"
        end repeat

        -- compound return value so Python can report locked count without needing a
        -- side-channel file or stderr (stderr would trip the "type 100002" branch).
        return (notesToProcess as string) & "|" & (lockedCount as string)
        end tell
    end tell
    '''
    # R20: wrap just the osascript subprocess.run in a perf-counter delta so
    # we can log per-batch wall-clock for the AppleScript export pass. Don't
    # include the surrounding parse/error-handling -- those are negligible
    # next to the AppleScript driver itself, and a tighter wrap means the
    # logged number isolates the actual Notes.app interaction cost.
    _t0_osascript = time.perf_counter()
    result = subprocess.run(['osascript', '-e', applescript], capture_output=True, text=True)
    _osascript_elapsed = time.perf_counter() - _t0_osascript

    if result.stdout:
        results_print(f"EXPORT NOTES stdout: {result.stdout}")
        
    if result.stderr:
        results_print(f"Error in EXPORT NOTES:")
        results_print(f"{result.stderr}")
        
        
        ### LOOK FOR ERROR OF UNSPPORTED (usually image) IN NOTE,
        ### AND MOVE THIS TO <foldername>_UNSUPPORTED
        
        searchstring = UNSUPPORTED_NOTE_ERROR_CODE
        if searchstring in result.stderr:
            # currentnote.txt is written by AppleScript immediately before each note's
            # export, so its 1-based index points at the failing note. Notes 1..(i-1)
            # were already exported successfully to disk -- we must return that count
            # so the caller commits + audits + moves them. Returning 0 here would
            # orphan those files on disk with no audit row and leave the originals in
            # the source folder, creating duplicates on the next run (the "zombie
            # exports" bug, B1).
            noteCount, noteTitle = get_currentnote_data(DEFAULT_CURRENTNOTE_FILE)
            print(f"{searchstring} is present for note '{noteTitle}'.")
            folder_dest = folder_name + unsupported_folder_ending
            move_one_note(noteTitle, folder_name, folder_dest, notes_account, create=True)
            goodnotes = noteCount - 1
            logger.warning(
                f"Unsupported note '{noteTitle}' (folder '{folder_name}', index {noteCount}) aborted batch; "
                f"exported {goodnotes} note(s) before the failure."
            )
            print_color(textcolor="cyan", msg=f"Exported {goodnotes} note(s) successfully before hitting unsupported content; continuing with those.")
            # R20: timing line for the partial-success B1 path. Log only if at
            # least one note made it out; otherwise the count==0 line is noise.
            if goodnotes > 0:
                _avg_ms = int(round(1000.0 * _osascript_elapsed / goodnotes))
                logger.info(
                    f"osascript: exported {goodnotes} note(s) in {_osascript_elapsed:.1f}s "
                    f"(avg {_avg_ms} ms/note) [folder '{folder_name}', B1 partial]"
                )
            return goodnotes

        else:
            debug_print(f"{searchstring} is not present.")
        
        return 0


    # B4: stdout is a compound "exported|lockedCount" string (see AppleScript `return`).
    # The `type 100002` branch above still returns a plain int directly, so this parser
    # only runs on the success path.
    stdout_val = result.stdout.strip() if result.stdout else ""
    if not stdout_val:
        return 0
    if '|' in stdout_val:
        try:
            exported_str, locked_str = stdout_val.split('|', 1)
            exported_count = int(exported_str.strip())
            locked_count = int(locked_str.strip())
        except ValueError:
            debug_print(f"Could not parse compound export result: {stdout_val!r}")
            return 0
        if locked_count > 0:
            plural = "s" if locked_count != 1 else ""
            logger.warning(
                f"{locked_count} empty or locked note{plural} committed as stub{plural} "
                f"in folder '{folder_name}' (title + dates only; no content available from Notes.app)."
            )
            print_color(
                textcolor="yellow",
                msg=f"NOTE: {locked_count} empty or locked note{plural} committed as stub{plural} (title + dates only; no content available from Notes.app).",
            )
        # R20: timing line for the success path. Logged only when at least one
        # note was exported (skip-on-zero per the per-batch contract); the
        # count includes any locked-note stubs since they consume osascript
        # time the same as a normal note.
        if exported_count > 0:
            _avg_ms = int(round(1000.0 * _osascript_elapsed / exported_count))
            logger.info(
                f"osascript: exported {exported_count} note(s) in {_osascript_elapsed:.1f}s "
                f"(avg {_avg_ms} ms/note) [folder '{folder_name}']"
            )
        return exported_count
    # Backwards-compatible fallback: plain int return (shouldn't happen post-B4 but safe).
    try:
        return int(stdout_val)
    except ValueError:
        return 0



def git_add_commit_push(repo_path, folder_name=None, wrapper_dir=None):
    """Stage, commit, and push the per-folder export subdir to GitHub.

    Run once per batch from process_one_folder, after the AppleScript export
    has written .html temps (markdown mode) or .md files (html mode) and the
    pandoc sweep (markdown mode) has finalized the .md set. Runs `git add
    <wrapper_dir>` rather than `git add .` so unrelated working-tree changes
    aren't accidentally captured. Commit message includes the folder name and
    timestamp.

    The "nothing to commit" case (re-exporting notes whose content is
    byte-identical to what's already in git) is classified as benign (B11):
    we still attempt a push afterward to drain any prior unpushed commits.

    Args:
        repo_path (str): absolute path to the local git repo root (the export
            path, same value setup_git_repo was called with).
        folder_name (str, optional): Notes folder being committed. Threaded
            into the commit message for traceability.
        wrapper_dir (str, optional): subdir under repo_path being staged
            (e.g. 'macosnotes'). `git add` runs against this path; falsy
            means no subdir which would `git add` literally the string ''
            -- caller should always set it.

    Returns:
        bool: True if every git step ran cleanly (add ok, commit ok or benign
            'nothing to commit', push ok including 'Everything up-to-date').
            False if any step failed -- caller (main()) flips partial_success
            so the run exits with EXIT_PARTIAL_SUCCESS. Per the exit-code
            taxonomy decision, push-failed-after-good-commits is partial
            (work is committed locally and recoverable on the next run);
            commit-failed-after-good-export is also partial since the export
            already wrote files to disk that just didn't reach git.
    """
    # Always operate from the git root directory

    all_clean = True

    result_gitadd = subprocess.run(['git', 'add', f'{wrapper_dir}'], cwd=repo_path)
    if result_gitadd.returncode == 0:
        print_color(textcolor="green",msg=f"Successful GIT ADD to origin/main.")
        results_print(f"1 result_gitadd: {result_gitadd}")
    else:
        all_clean = False
        logger.error(f"GIT ADD failed (returncode={result_gitadd.returncode}) in repo '{repo_path}', wrapper_dir='{wrapper_dir}'.")
        print_color(textcolor="red",msg=f"Error GIT ADD to origin/main:")
        results_print(f"2 result_gitadd: {result_gitadd}")
    
    folder_info = f"from folder '{folder_name}'" if folder_name else ""
    commit_message = f"Backed up {folder_info} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
    result_gitcommit = subprocess.run(['git', 'commit', '-m', commit_message], cwd=repo_path, capture_output=True, text=True)

    # Classify the commit result.
    # Git returns nonzero with a "nothing to commit" message when the staging area is empty.
    # This happens naturally when re-exporting notes whose content hasn't changed since the
    # last backup -- the exported .md is byte-identical to what's already committed. Treat
    # that case as benign (not a real error) so we still attempt the push below, which
    # drains any prior unpushed commits from earlier runs.
    nothing_to_commit = (
        result_gitcommit.returncode != 0
        and ("nothing to commit" in result_gitcommit.stdout
             or "nothing added to commit" in result_gitcommit.stdout)
    )
    commit_ok = (result_gitcommit.returncode == 0) or nothing_to_commit

    commit_print_msg = f'''    - repo path: {repo_path}
    - folder name:{folder_name}
    - commit message:{commit_message}
    '''

    if result_gitcommit.returncode == 0:
        print_color(textcolor="green",msg=f"Successful GIT COMMIT to origin/main.")
        print_color(textcolor="white",msg=f"{commit_print_msg}")
    elif nothing_to_commit:
        print_color(textcolor="cyan",msg=f"No changes to commit -- note content is identical to what's already in git. (Normal when re-exporting unchanged notes.)")
        print_color(textcolor="white",msg=f"{commit_print_msg}")
    else:
        all_clean = False
        logger.error(
            f"GIT COMMIT failed (returncode={result_gitcommit.returncode}) in repo '{repo_path}'. "
            f"folder='{folder_name}'. stdout={result_gitcommit.stdout!r} stderr={result_gitcommit.stderr!r}"
        )
        print_color(textcolor="red",msg=f"Error GIT COMMIT to origin/main:")
        print_color(textcolor="white",msg=f"{commit_print_msg}")
        results_print(f"result_gitcommit: {result_gitcommit}")


    if commit_ok:
        # Try to pull and rebase before pushing
        try:
            subprocess.run(['git', 'pull', '--rebase', 'origin', 'main'], cwd=repo_path, capture_output=True, text=True)
        except:
            logger.warning(f"git pull --rebase failed before push in repo '{repo_path}'; continuing to push.")
            print_color(textcolor="magenta",msg=f"No remote changes to pull")

        result_push = subprocess.run(['git', 'push', 'origin', 'main'], cwd=repo_path, capture_output=True, text=True)

        if result_push.returncode == 0:
            # Note: git emits "Everything up-to-date" on stderr with returncode 0 when
            # there's nothing new to push -- treated the same as a real push here.
            print_color(textcolor="green",msg=f"Successful GIT PUSH to origin/main.")
            results_print(f"1 result_push: {result_push}")
            print(" ")
        else:
            all_clean = False
            logger.error(
                f"GIT PUSH failed (returncode={result_push.returncode}) in repo '{repo_path}'. "
                f"stdout={result_push.stdout!r} stderr={result_push.stderr!r}"
            )
            print_color(textcolor="red",msg=f"Error GIT PUSH to origin/main:")
            results_print(f"2 result_push: {result_push}")
            print(" ")
            # Optionally, try force push if regular push fails
            # result = subprocess.run(['git', 'push', '-f', 'origin', 'main'], cwd=repo_path, capture_output=True, text=True)
    else:
        all_clean = False
        logger.error(f"Skipping GIT PUSH due to upstream commit error in repo '{repo_path}'.")
        print_color(textcolor="red",msg=f"Commit error so no GIT PUSH to origin/main:")
        print(" ")

    return all_clean



# R5: helpers replacing export_notes_metadata's CSV-write half. The metadata
# now flows in through the side-channel file written by export_notes_to_markdown's
# AppleScript loop (one CSV-shaped row per successfully-exported note); the
# CSV-write half lives here. Together they obsolete the second osascript pass
# the old export_notes_metadata used to fire.
def read_metadata_rows(metadata_rows_file, expected_count, folder, current_datetime=None):
    """Read the side-channel metadata file and return rows in the audit shape.

    Each line in the file is
    'title,quoted_title.md,YYYY-MM-DD HH:MM:SS,YYYY-MM-DD HH:MM:SS' post-R8
    (the trailing field is creation_date, used by the YAML frontmatter step).
    Pre-R8 lines lacked the trailing creation_date and are still accepted via
    a length-2-or-3 fallback split; the missing field defaults to '' so
    callers that ignore it (write_audit_rows, max_mod_date_from_rows) keep
    working unchanged. Title is already comma-stripped on the AppleScript
    side via `sed 's/,/-/g'`, so split(',', 3) cleanly recovers four fields.

    Args:
        metadata_rows_file (str): absolute path to the side-channel file.
        expected_count (int): how many rows the export reported as
            successfully written. A mismatch with the file's row count gets
            logged as a warning -- usually means the AppleScript bailed
            mid-iteration (B1 partial-success), or the file truncation at
            start of export failed.
        folder (str): Notes folder name (echoed into each row).
        current_datetime (datetime, optional): timestamp for the 'Exported
            Date' column. Defaults to datetime.now() at call time.

    Returns:
        List of rows in the shape
        [folder, title, formatted_date, quoted_title, current_datetime,
         formatted_creation_date].
        formatted_date is '%Y-%m-%d %H:%M:%S' on the success path (validated
        via strptime); on a parse failure the raw AppleScript value is kept
        and a warning is logged so max_mod_date_from_rows can skip it cleanly
        (matches the legacy 5-field audit-CSV layout preserved for backward
        compat with older committed audit files).
        formatted_creation_date is the same shape as formatted_date and is
        used by R8's YAML frontmatter step. Older audit-only consumers
        (write_audit_rows, max_mod_date_from_rows) only read indices 0-4.
    """
    if current_datetime is None:
        current_datetime = datetime.now()
    rows = []
    try:
        with open(metadata_rows_file, 'r', encoding='utf-8') as f:
            lines = [line.rstrip('\n') for line in f if line.strip()]
    except OSError as exc:
        logger.warning(
            f"Could not read metadata rows file '{metadata_rows_file}' "
            f"after export ({exc}); audit CSV will be empty for folder '{folder}'."
        )
        return rows

    if len(lines) != expected_count:
        logger.warning(
            f"Metadata rows file row count mismatch in folder '{folder}': "
            f"expected {expected_count}, found {len(lines)}. Continuing with "
            f"what's actually in the file."
        )

    for line in lines:
        # R8: post-R8 rows have 4 fields (split=3); pre-R8 rows had 3 (split=2).
        # Try the 4-field shape first; fall back to 3-field if creation_date is
        # absent (shouldn't happen on a fresh export but guards against any
        # leftover file from a pre-R8 run).
        parts = line.split(',', 3)
        creation_date = ''
        if len(parts) == 4:
            title, quoted_title, mod_date, creation_date = (p.strip() for p in parts)
        elif len(parts) == 3:
            title, quoted_title, mod_date = (p.strip() for p in parts)
        else:
            logger.warning(
                f"Malformed metadata row in folder '{folder}': {line!r}. Skipping."
            )
            continue

        # Validate the ISO format strptime'd cleanly (mirrors the post-R18 fix
        # in the old export_notes_metadata Python parser). Fall back to the
        # raw value with a warning so a malformed AppleScript output surfaces
        # in the log instead of silently corrupting the audit CSV.
        try:
            datetime.strptime(mod_date, '%Y-%m-%d %H:%M:%S')
            formatted_date = mod_date
        except ValueError:
            logger.warning(
                f"Unexpected mod_date format from AppleScript for note '{title}' "
                f"in folder '{folder}': {mod_date!r}. Using raw value; watermark "
                f"advance for this row will be skipped."
            )
            formatted_date = mod_date

        # Validate creation_date the same way (R8). On parse failure keep the
        # raw value and log; the YAML frontmatter will still embed it as a
        # quoted string scalar so downstream consumers won't choke.
        formatted_creation_date = creation_date
        if creation_date:
            try:
                datetime.strptime(creation_date, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                logger.warning(
                    f"Unexpected creation_date format from AppleScript for note "
                    f"'{title}' in folder '{folder}': {creation_date!r}. Using raw value."
                )

        print_color(textcolor="white", msg=f"Adding row to audit file for folder '{folder}': '{title}', ModDate: '{formatted_date}', Markdown title: '{quoted_title}', Exported Date: '{current_datetime}'")

        rows.append([folder, title, formatted_date, quoted_title, current_datetime, formatted_creation_date])

    return rows


def write_audit_rows(output_file, rows):
    """Append rows to the per-folder audit CSV (R5).

    Replaces the CSV-write half of the legacy export_notes_metadata. Header is
    written only when creating a new file; existing audit CSVs grow by append,
    preserving their full history -- the dedupe pass proposed in R3 was
    retired in favor of this audit-trail-via-version-history behavior, so
    duplicate rows on re-export are by design.

    R8: each row from read_metadata_rows now carries a 6th element
    (formatted_creation_date) used by the YAML frontmatter step. The audit CSV
    is intentionally limited to its original 5-column shape, so each row is
    sliced to [:5] before writing -- preserves the existing CSV header layout
    and keeps downstream-readers (incl. older spreadsheet imports) unchanged.

    Args:
        output_file (str): path to the audit CSV (e.g. './_pythons.csv').
        rows: list as produced by read_metadata_rows -- each item is
            [folder, title, formatted_date, quoted_title, current_datetime,
             formatted_creation_date]. The CSV write only consumes [:5].

    Returns:
        The rows list passed in (unchanged), so callers can chain
        `processednotes_data = write_audit_rows(...)` and downstream consumers
        (`max_mod_date_from_rows`, the move-step gate) keep working with the
        same shape they used to get from export_notes_metadata.
    """
    if not rows:
        return rows
    mode = 'a' if os.path.exists(output_file) else 'w'
    with open(output_file, mode, newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if mode == 'w':
            writer.writerow(['Folder', 'Original Title', 'Last Modified', 'Exported Title', 'Exported Date'])
        # R8: slice to [:5] so the new creation_date 6th element doesn't leak
        # into the audit CSV (which has a fixed 5-column header).
        writer.writerows(row[:5] for row in rows)
    print_color(textcolor="green", msg=f"22 SUCCESS: Exported {len(rows)} notes to '{output_file}'", addseparator=True)
    return rows



# R8: helpers for the per-batch HTML->markdown conversion sweep. Used in
# 'markdown' body_format mode (the default). 'html' mode skips this code path
# entirely -- AppleScript writes the .md directly with embedded HTML, no
# pandoc invocation, no frontmatter prepended.

def _yaml_single_quote(s):
    """Format a value as a single-quoted YAML scalar string.

    Single-quoted YAML strings only require doubling embedded single quotes;
    every other character (colons, backslashes, double-quotes, special chars)
    is taken literally. Cleaner than double-quoting for user-supplied note
    titles, which can contain almost anything.
    """
    s = str(s).replace("'", "''")
    return f"'{s}'"


def convert_html_to_markdown(html_path, md_path, frontmatter):
    """Convert a single .html temp file to a final .md file via pandoc (R8).

    Pandoc invocation uses explicit format flags
    ('-f html-native_divs -t gfm') so the output doesn't drift if pandoc's
    defaults change in a future release. The 'html-native_divs' (= disable
    pandoc's HTML-native-div extension) tells pandoc to fold Notes.app's
    ubiquitous <div> wrappers into native paragraphs instead of preserving
    them as raw HTML in the markdown -- significantly cleaner output for
    Notes.app's HTML shape, where every paragraph and even <br>-only blank
    lines are wrapped in <div>. Lists, tables, inline formatting (bold,
    italic, code), and links convert into idiomatic GFM regardless.

    YAML frontmatter is hand-emitted with single-quoted scalars (only embedded
    single quotes need escaping) -- avoids pulling ruamel.yaml into the
    per-note hot path.

    Args:
        html_path (str): path to the AppleScript-written <cleanTitle>.html
            temp file.
        md_path (str): path where the final <cleanTitle>.md should be written.
        frontmatter (dict): keys 'title', 'creation_date', 'modification_date'.
            Title is the original unsanitized note title from Notes.app
            (recovers information that's otherwise lost in the sanitized
            filename). Dates are ISO 'YYYY-MM-DDTHH:MM:SS' (naive local time,
            matches the R18 watermark format).

    Returns:
        True if pandoc converted cleanly; False if conversion failed and the
        .md was written as raw HTML with a marker comment instead. Caller
        should treat False as a partial-success signal so the run exits
        EXIT_PARTIAL_SUCCESS.
    """
    frontmatter_block = (
        "---\n"
        f"title: {_yaml_single_quote(frontmatter.get('title', ''))}\n"
        f"creation_date: {_yaml_single_quote(frontmatter.get('creation_date', ''))}\n"
        f"modification_date: {_yaml_single_quote(frontmatter.get('modification_date', ''))}\n"
        "---\n\n"
    )

    try:
        result = subprocess.run(
            ['pandoc', '-f', 'html-native_divs', '-t', 'gfm', '-i', html_path, '-o', md_path],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        # pandoc was on PATH at startup but is gone now -- extremely unlikely
        # but guard against it cleanly.
        logger.error(
            f"pandoc disappeared from PATH during conversion of '{html_path}'. "
            f"Falling back to raw HTML for this note."
        )
        return _fallback_write_html_as_md(html_path, md_path, frontmatter_block)

    if result.returncode != 0:
        logger.warning(
            f"pandoc conversion failed for '{html_path}' "
            f"(returncode={result.returncode}, stderr={(result.stderr or '').strip()!r}). "
            f"Writing raw HTML with marker comment to '{md_path}' as fallback."
        )
        return _fallback_write_html_as_md(html_path, md_path, frontmatter_block)

    # Conversion succeeded -- pandoc wrote the converted body to md_path.
    # Read it back, prepend frontmatter, write again. Two-step so we don't
    # have to capture pandoc's stdout (which is text-mode-encoding-fragile
    # for non-ASCII content -- some notes have smart quotes, em-dashes, etc).
    try:
        with open(md_path, 'r', encoding='utf-8') as f:
            converted_body = f.read()
        # R8 post-processing pass 1: pandoc converts <br> tags to GFM
        # hard-line-break syntax (backslash at end of line). When <br> appears
        # with no preceding text -- common in Notes.app HTML like
        # <div><br></div> -- pandoc emits a lone '\' as the entire line, which
        # renders as a literal backslash on GitHub. Replace those orphaned
        # backslash-only lines with empty lines.
        converted_body = re.sub(r'(?m)^\\$', '', converted_body)
        # R8 post-processing pass 2: markdown renderers collapse 2+ consecutive
        # blank lines to a single paragraph break. Notes users often separate
        # sections with multiple blank lines. Preserve that spacing by inserting
        # an &nbsp; paragraph for each Notes-blank-line in the run -- &nbsp;
        # renders on GitHub as a near-invisible short paragraph that maintains
        # the visual gap without mixing raw HTML tags into the body.
        #
        # Counting math: Notes.app encodes a blank line as <div><br></div>.
        # With html-native_divs, each becomes a paragraph holding just <br>,
        # which pandoc emits as a standalone '\' (GFM hard break) surrounded by
        # blank lines (paragraph separators). After pass 1 strips the lone '\'
        # chars, N user-blank-lines collapse into 2*N+2 consecutive newlines
        # (the surrounding paragraph break plus two newlines per blank line).
        # So nbsp count = (len - 2) // 2 -> one nbsp per Notes-blank-line.
        # Pre-fix this was (len - 2), which double-counted and produced 2x the
        # expected vertical spacing (e.g. 6 blank lines -> 12 nbsp).
        converted_body = re.sub(
            r'\n{3,}',
            lambda m: '\n\n' + '&nbsp;\n\n' * ((len(m.group()) - 2) // 2),
            converted_body,
        )
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(frontmatter_block + converted_body)
    except OSError as exc:
        logger.warning(
            f"Could not prepend frontmatter to '{md_path}' ({exc}); "
            f"file may exist without frontmatter. Run is still considered partial."
        )
        try:
            os.remove(html_path)
        except OSError:
            pass
        return False

    # Success path: delete the .html temp.
    try:
        os.remove(html_path)
    except OSError as exc:
        logger.warning(f"Could not delete temp HTML '{html_path}' after conversion ({exc}).")
    return True


def _fallback_write_html_as_md(html_path, md_path, frontmatter_block):
    """Write raw HTML to .md with a marker comment when pandoc fails (R8).

    Used as a fallback path so a single bad-input note doesn't kill the batch.
    The .md will contain frontmatter + a marker comment + the original HTML.
    Caller treats the False return as a partial-success signal.
    """
    try:
        with open(html_path, 'r', encoding='utf-8') as f:
            raw_html = f.read()
    except OSError as exc:
        logger.error(
            f"Fallback write also failed: could not read '{html_path}' ({exc}). "
            f"Note will not be committed for this run."
        )
        return False
    marker = (
        "<!-- [pandoc conversion failed; raw HTML preserved -- "
        "see gitmynotes.log for details] -->\n\n"
    )
    try:
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(frontmatter_block + marker + raw_html)
    except OSError as exc:
        logger.error(f"Fallback write to '{md_path}' failed ({exc}).")
        return False
    try:
        os.remove(html_path)
    except OSError:
        pass
    return False


def run_pandoc_conversion_sweep(metadata_rows, export_path, folder, wrapper_dir):
    """Convert all per-note .html temp files for a batch to final .md (R8).

    Called once per batch in 'markdown' body_format mode, after
    read_metadata_rows and before git_add_commit_push (so the .md files exist
    when git stages them). Iterates the metadata rows, computes the .html
    temp path and final .md path for each, and calls convert_html_to_markdown
    per file. Returns False if any conversion fell back to the raw-HTML write
    path (caller treats as a partial-success signal so the run exits
    EXIT_PARTIAL_SUCCESS).

    Args:
        metadata_rows: list as produced by read_metadata_rows -- each row is
            [folder, title, formatted_date, quoted_title, current_datetime,
             formatted_creation_date]. quoted_title is the sanitized .md
            filename (e.g. 'my-note.md'); we swap the '.md' suffix for
            '.html' to find the AppleScript-written temp.
        export_path (str): the GitMyNotes export root (args.export_path).
        folder (str): the Notes folder being processed (path component).
        wrapper_dir (str): the wrapper subdir (DEFAULT_NOTES_WRAPPERDIR);
            falsy means no wrapper (paths land directly under export_path).

    Returns:
        True if every conversion succeeded; False if any failed and
        triggered the raw-HTML fallback path.
    """
    if not metadata_rows:
        return True

    if wrapper_dir:
        export_path_w_folder = f"{export_path}/{wrapper_dir}/{folder}"
    else:
        export_path_w_folder = f"{export_path}/{folder}"

    # R20: wall-clock the conversion sweep so the per-batch pandoc cost lands
    # in gitmynotes.log alongside the osascript timing. fallback_count
    # increments on either a missing temp .html (caller's problem) or a
    # convert_html_to_markdown returning False (pandoc itself failed and the
    # raw-HTML fallback was written). One log line at the end of the sweep,
    # gated on metadata_rows being non-empty (handled by the early-return
    # above).
    _t0_pandoc = time.perf_counter()
    fallback_count = 0

    all_clean = True
    for row in metadata_rows:
        # row layout post-R8:
        # [folder, title, mod_date, quoted_title, current_datetime, creation_date]
        _, title, mod_date, quoted_title, _, creation_date = row
        md_filename = quoted_title  # already ends in .md per AppleScript
        if md_filename.endswith('.md'):
            html_filename = md_filename[:-3] + '.html'
        else:
            # Defensive: shouldn't happen given AppleScript always appends .md.
            html_filename = md_filename + '.html'
        html_path = f"{export_path_w_folder}/{html_filename}"
        md_path = f"{export_path_w_folder}/{md_filename}"

        # Frontmatter dates: ISO 8601 with 'T' separator. The metadata-row
        # values are 'YYYY-MM-DD HH:MM:SS' per read_metadata_rows validation;
        # swap the space for 'T' so they parse cleanly as YAML timestamps /
        # ISO datetimes. Empty strings stay empty.
        creation_date_iso = creation_date.replace(' ', 'T') if creation_date else ''
        mod_date_iso = mod_date.replace(' ', 'T') if mod_date else ''

        frontmatter = {
            'title': title,
            'creation_date': creation_date_iso,
            'modification_date': mod_date_iso,
        }

        if not os.path.exists(html_path):
            logger.warning(
                f"Pandoc sweep: expected temp HTML '{html_path}' not found for note "
                f"'{title}' in folder '{folder}'. Skipping conversion for this row."
            )
            all_clean = False
            fallback_count += 1
            continue

        success = convert_html_to_markdown(html_path, md_path, frontmatter)
        if not success:
            all_clean = False
            fallback_count += 1

    # R20: per-batch pandoc timing line. Counts every row attempted (including
    # missing-temp fallbacks); fallback_count surfaces how many rows didn't
    # produce a clean GFM .md. avg_ms is per-row total time, not per-clean-
    # conversion -- that's the right denominator for "is the sweep too slow."
    _pandoc_elapsed = time.perf_counter() - _t0_pandoc
    _row_count = len(metadata_rows)
    _avg_ms = int(round(1000.0 * _pandoc_elapsed / _row_count)) if _row_count else 0
    logger.info(
        f"pandoc: converted {_row_count} note(s) in {_pandoc_elapsed:.1f}s "
        f"(avg {_avg_ms} ms/note, {fallback_count} fallback(s)) [folder '{folder}']"
    )

    return all_clean



def get_currentnote_data(filename):
    with open(filename, 'r') as file:
        line = file.readline().strip()
        notecount, notetitle = line.split("++++")
        return int(notecount), notetitle



def move_one_note(note_name, folder_source, folder_dest, notes_account, create=True):
    """Move a single named note from `folder_source` to `folder_dest` via
    AppleScript. Used exclusively on the B1 unsupported-note recovery path:
    when export_notes_to_markdown bails on a `type 100002` error, the offending
    note's title is read from currentnote.txt and passed here so the next
    re-run can skip past it.

    `note_name` is matched against the AppleScript `name of` property of each
    note in `folder_source` (`first note ... whose name is "..."`). R9 routes
    every embedded string (name, source, dest, account) through
    applescript_escape so titles containing quotes / backslashes / etc. don't
    corrupt the script.

    Args:
        note_name (str): exact title of the note to move. Comes from
            currentnote.txt, written by AppleScript inside the export loop.
        folder_source (str): folder the note currently lives in (typically
            the user's working folder).
        folder_dest (str): folder to move it to (typically
            <folder_source><unsupported_folder_ending>, e.g. 'plans_unsupported').
        notes_account (str): macOS Notes account name to scope the lookup to (R6).
        create (bool): if True, ensure `folder_dest` exists by calling
            create_gitnotes_folder first. Defaults True.

    Returns:
        int: always 0 (the caller -- export_notes_to_markdown's B1 branch --
            uses this only for side effects; the int return is historical).
            Side effects: AppleScript move, logger.warning + red print_color
            telling the user to re-run to drain remaining notes in the batch.
    """

    # if processed_notes exists, then that stage was a success, so next step:
    # create_gitmynotes_folder(folder_dest) so we have a place to move notes
    if create:
        success, message = create_gitnotes_folder(folder_dest, notes_account)

        if success:
            print_color(textcolor="green",msg=f"Create notes folder Success: {message}")
        else:
            logger.error(f"Failed to create Notes folder '{folder_dest}' (account '{notes_account}'): {message}")
            print_color(textcolor="red",msg=f"Create notes folder Failed: {message}")


    debug_print(f"Now to move UNSUPPORTED note '{note_name}' from '{folder_source}' to '{folder_dest}'")

    # R9: escape folder names, account name, AND the note title (the title comes
    # from currentnote.txt -- it's user content and can contain anything,
    # including the doublequotes that would otherwise break this AppleScript).
    folder_source_escaped = applescript_escape(folder_source)
    folder_dest_escaped = applescript_escape(folder_dest)
    notes_account_escaped = applescript_escape(notes_account)
    note_name_escaped = applescript_escape(note_name)

    applescript_moveonenote = f'''
    tell application "Notes"
        set targetAccount to "{notes_account_escaped}"
        tell account targetAccount
            try
                set sourceFolder to folder "{folder_source_escaped}"
                set destFolder to folder "{folder_dest_escaped}"
                set theNote to first note of sourceFolder whose name is "{note_name_escaped}"
                
                -- Check if we have notes to move
                if theNote is missing value then
                    return "No such note found in source folder"
                end if
                
                -- Do the move
                try
                    move theNote to destFolder
                on error errMsg
                    return "Error moving note " & theNote & " : " & errMsg
                end try
                
                return "SUCCESS: Moved one note '" & theNote & "' to "  & destFolder
            on error errMsg
               return "Error: " & errMsg
            end try
        end tell
    end tell
    '''
    
    result_onemove, output_onemove = process_applescript(applescript_moveonenote)
    debug_print(f"applescript_moveonenote result: {result_onemove} {output_onemove}")

    logger.warning(
        f"Unsupported note '{note_name}' moved from '{folder_source}' to '{folder_dest}'. "
        f"Re-run command to drain remaining notes in this batch."
    )
    print_color(textcolor='red', msg=f'''    uh oh, unsupported note encountered: '{note_name}'
    Note moved to notes folder: '{folder_dest}'.
    Previous notes will be moved in this loop, but.
    please run your command again to ensure all notes are moved.''', addseparator=True)
    return 0
   




def move_processed_notes(folder_source, folder_dest, max_notes, notes_account, create=True):
    """Bulk-move up to `max_notes` notes from `folder_source` to `folder_dest`
    via AppleScript. Two callers:

    1. Normal post-export move in process_one_folder: after a successful
       export + commit + push, move the just-exported notes from the user's
       working folder into <folder_source><processed_folder_ending> (default
       '__GitMyNotes' suffix) so the next run doesn't re-process them.
    2. --restore-notes restoration in restore_source_foldernote: move notes
       back the other direction when the working folder is empty / on every
       run, depending on the --restore-notes mode.

    Args:
        folder_source (str): Notes folder to move notes out of.
        folder_dest (str): Notes folder to move them into. Created via
            create_gitnotes_folder if `create=True`.
        max_notes (int): upper bound on the move. The AppleScript clamps to
            the actual note count if fewer exist; iteration order is whatever
            `every note of folder` returns (no explicit sort).
        notes_account (str): macOS Notes account name to scope the lookup to (R6).
        create (bool): ensure `folder_dest` exists first. Defaults True.

    Returns:
        bool: True if the AppleScript reported success (process_applescript's
            success flag). False on any failure -- callers in
            process_one_folder treat False after a real export as a
            partial-success signal.
    """

    # if processed_notes exists, then that stage was a success, so next step:
    # create_gitmynotes_folder(folder_dest) so we have a place to move notes
    if create:
        success, message = create_gitnotes_folder(folder_dest, notes_account)

        if success:
            print_color(textcolor="green",msg=f"Create notes folder Success: {message}")
        else:
            logger.error(f"Failed to create Notes folder '{folder_dest}' (account '{notes_account}'): {message}")
            print_color(textcolor="red",msg=f"Create notes folder Failed: {message}")


    debug_print(f"Now to move up to {max_notes} notes from '{folder_source}' to '{folder_dest}'")

    # R9: full applescript_escape (backslash + quote + newline/CR/tab) on the
    # three user-supplied strings before embedding into the AppleScript block.
    folder_source_escaped = applescript_escape(folder_source)
    folder_dest_escaped = applescript_escape(folder_dest)
    notes_account_escaped = applescript_escape(notes_account)

    applescript_movenote = f'''
    tell application "Notes"
        set targetAccount to "{notes_account_escaped}"
        tell account targetAccount
            try
                set sourceFolder to folder "{folder_source_escaped}"
                set destFolder to folder "{folder_dest_escaped}"
                set theNotes to every note of sourceFolder
                set noteCount to (count of theNotes)
                
                -- Check if we have notes to move
                if noteCount is 0 then
                    return "No notes found in source folder"
                end if
                
                -- Determine how many notes to actually move
                if {max_notes} ≤ noteCount then
                    set notesToMove to {max_notes}
                else
                    set notesToMove to noteCount
                end if
                
                repeat with i from 1 to notesToMove
                    try
                        move item i of theNotes to destFolder
                    on error errMsg
                        return "Error moving note " & i & ": " & errMsg
                    end try
                end repeat
                
                return "SUCCESS: Moved " & notesToMove & " notes"
            on error errMsg
                return "Error: " & errMsg
            end try
        end tell
    end tell
    '''
    
    result_move, output_move = process_applescript(applescript_movenote)
    results_print(f"applescript_movenote result: {result_move} {output_move}")
    return result_move
   



def create_gitnotes_folder(folder: str, notes_account: str) -> Tuple[bool, str]:
    """
    Create a folder in macOS Notes app under the configured Notes account.

    Args:
        folder (str): Name of the folder to create
        notes_account (str): Notes account to scope the create to (e.g. 'iCloud',
            'On My Mac'). Threaded through from --notes-account / DEFAULT_NOTES_ACCOUNT (R6).

    Returns:
        Tuple[bool, str]: (success status, message/error details)
    """
    print_color(textcolor="white",msg=f"Attempting to create Notes folder: {folder}")

    # R9: applescript_escape covers backslash + quote + newline/CR/tab.
    folder_escaped = applescript_escape(folder)
    notes_account_escaped = applescript_escape(notes_account)

    applescript = f'''
    tell application "Notes"
        try
            set targetAccount to "{notes_account_escaped}"
            tell account targetAccount
                if not (exists folder "{folder_escaped}") then
                    make new folder with properties {{name:"{folder_escaped}"}}
                    return "Folder created successfully"
                else
                    return "Folder already exists"
                end if
            end tell
        on error errMsg
            return "Error: " & errMsg
        end try
    end tell
    '''
    
    return process_applescript(applescript)



def process_applescript(applescript):
    """Run an AppleScript block via `osascript -e` and classify the outcome.

    Generic wrapper used by every AppleScript-touching function except
    export_notes_to_markdown (which needs custom B1 / B4 / R20 handling
    inline). Captures stdout + stderr, treats any stderr output as failure,
    treats stdout containing the literal substring "Error:" as failure, and
    returns (False, error_text) in those cases. Otherwise returns
    (True, stripped_stdout).

    CalledProcessError from osascript itself (non-zero exit) is caught and
    returned as (False, "Process Error: <stderr>"). Any other exception is
    caught and returned as (False, "Unexpected Error: <str>"). The function
    never raises -- AppleScript-touching code is expected to inspect the
    returned tuple.

    Args:
        applescript (str): the raw AppleScript source to execute. Caller is
            responsible for routing any embedded user-supplied strings through
            applescript_escape (R9) before assembling this block.

    Returns:
        Tuple[bool, str]: (success, output_or_error). On success the output
            is the stripped stdout of osascript (often the AppleScript
            function's `return` value); on failure it's an error message.
    """
    # print_color(textcolor='white', msg=f"Processing AppleScript...")
    
    try:
        result = subprocess.run(
            ['osascript', '-e', applescript],
            capture_output=True,
            text=True,
            check=True  # This will raise CalledProcessError if osascript fails
        )
        
        ## Set the applescript blank so process_applescript can be used repeatedly
        applescript = ""
        
        # Check for any stderr output
        if result.stderr:
            return False, f"AppleScript Error: {result.stderr}"
            
        # Check the actual output
        output = result.stdout.strip()
        if "Error:" in output:
            return False, output
        else:
            return True, output
            
    except subprocess.CalledProcessError as e:
        return False, f"Process Error: {e.stderr}"
    except Exception as e:
        return False, f"Unexpected Error: {str(e)}"



def get_foldernotecount(folder, notes_account):

    if folder:
        debug_print(f"Getting count of notes in folder: {folder}")
        # R9: applescript_escape covers backslash + quote + newline/CR/tab.
        folder_escaped = applescript_escape(folder)
        notes_account_escaped = applescript_escape(notes_account)

        applescript_notecount = f'''
        tell application "Notes"
            set targetAccount to "{notes_account_escaped}"
            tell account targetAccount
                if length of "{folder_escaped if folder_escaped else ''}" > 0 then
                    try
                        set folderToCount to folder "{folder_escaped}"
                        set folderNotes to every note in folderToCount
                        set folderNoteCount to (count of folderNotes)
                        return folderNoteCount
                    on error
                        log "Folder {folder_escaped} not found"
                        return 0
                    end try
                end if
            end tell
         end tell
        '''
        
        result,output_count = process_applescript(applescript_notecount)
        results_print(f"'{folder_escaped}' notecount: {output_count}")
        print("")
        return int(output_count)
        
    else:
        print("No folder set.")



def restore_source_foldernote(folder_source, folder_bkup, restore_notes, notes_account):
    ## if count of notes in folder_source is 0, and count of folder_dest is > 0
    ## then move all the notes from dest back to source. (as it was in the beginning, so shall...)
    ## notes_account scopes every Notes lookup to the configured account (R6).

    if restore_notes != 'empty' and restore_notes != 'always':
        return


    source_count = get_foldernotecount(folder_source, notes_account)
    bkup_count = get_foldernotecount(folder_bkup, notes_account)



    if restore_notes == 'empty':
       if source_count == 0:
            if bkup_count > 0:
                results_print(f"Source folder {folder_source} notecount is {source_count}!")
                results_print(f"Option '--restore-notes={restore_notes}' so processed notes in '{folder_bkup}' will be moved back.")
                restore_result = move_processed_notes(folder_bkup, folder_source, bkup_count, notes_account, create=False)

                return restore_result

    if restore_notes == 'always':
        if bkup_count > 0:
            results_print(f"Source folder {folder_source} not empty! Contains {source_count} un-backed-up notes.") #this may sometime be not clear
            results_print(f"Option --restore-notes={restore_notes} so processed notes in {folder_bkup} will be moved back.")
            results_print(f"WARNING: This non-'empty' setting can cause some notes to never be backed up.")
            restore_result = move_processed_notes(folder_bkup, folder_source, bkup_count, notes_account, create=False)

            return restore_result
    else:
        return



def update_yaml_config(file_path, key, value):
    """
    Updates a specific key-value pair in a YAML config file while preserving comments and formatting.

    Args:
        file_path (str): Path to the YAML configuration file
        key (str): The key to update
        value: The new value for the specified key
    """
    # Use ruamel.yaml to preserve comments and formatting
    yaml_handler = YAML()
    yaml_handler.preserve_quotes = True  # Preserve existing quote styles
    yaml_handler.width = 4096  # Prevent automatic line wrapping

    # Read the existing file
    with open(file_path, 'r') as file:
        config = yaml_handler.load(file)

    # Update the specific key
    config[key] = value

    # Write back to the file, preserving original structure
    with open(file_path, 'w') as file:
        yaml_handler.dump(config, file)


def update_yaml_config_multi(file_path, updates):
    """
    Updates multiple key-value pairs in a YAML config file in a single read+write
    cycle, preserving comments and formatting. Used to flush per-run usage counter
    updates atomically (R10) instead of one yaml round-trip per key.

    Args:
        file_path (str): Path to the YAML configuration file
        updates (dict): Mapping of {key: new_value} pairs to apply. An empty dict
            is a no-op (the file isn't touched).
    """
    if not updates:
        return
    yaml_handler = YAML()
    yaml_handler.preserve_quotes = True
    yaml_handler.width = 4096

    with open(file_path, 'r') as file:
        config = yaml_handler.load(file)

    for key, value in updates.items():
        config[key] = value

    with open(file_path, 'w') as file:
        yaml_handler.dump(config, file)


# R18 data layer: helpers for the per-folder mod-date watermark stored in
# USAGE_FOLDERS_PROCESSED. Watermarks are ISO 8601 naive-local-time strings of
# the form 'YYYY-MM-DDTHH:MM:SS'. β semantics: each new value only replaces the
# existing watermark if it is strictly greater (advances only).
def parse_watermark_iso(watermark_str):
    """Parse an ISO 8601 watermark string back to a naive datetime, or return
    None for null / empty / unparseable input. A None result is treated by the
    feature layer as 'folder seeded but never successfully run' -- '--auto'
    skips those folders with a yellow warning."""
    if not watermark_str:
        return None
    try:
        return datetime.fromisoformat(watermark_str)
    except (TypeError, ValueError):
        return None


def max_mod_date_from_rows(rows):
    """Walk a metadata-row list (as produced by read_metadata_rows) and
    return the maximum parsed modification-date as a naive datetime, or
    None if no row had a parseable date.

    Each row is the 6-element shape
    [folder, title, formatted_date, quoted_title, current_datetime,
     formatted_creation_date] (the trailing creation_date was added in R8
     for the YAML frontmatter step; older audit-only consumers ignore it).
    Only index 2 (formatted_date, i.e. modification date) is read here.
    formatted_date is '%Y-%m-%d %H:%M:%S' on the success path (validated via
    strptime in read_metadata_rows). Rows whose date didn't parse cleanly
    there carry the raw AppleScript string and are skipped here -- a partial
    sample still gives us a usable max.
    """
    if not rows:
        return None
    parsed = []
    for row in rows:
        try:
            parsed.append(datetime.strptime(row[2], '%Y-%m-%d %H:%M:%S'))
        except (TypeError, ValueError, IndexError):
            continue
    return max(parsed) if parsed else None


# R18 feature layer: count how many notes in a folder have been modified
# strictly after the given watermark. Used by --auto mode to decide whether a
# folder needs processing this run, and to bound the per-folder max_notes so
# the existing batch pipeline doesn't churn through unchanged notes.
#
# The watermark is built into an AppleScript date object via component setters
# (year/month/day/time-in-seconds) rather than via a string-based date literal,
# because AppleScript's `date "<string>"` parsing is locale-dependent. The
# component approach is portable across user locale settings.
#
# Returns 0 on any failure (folder missing, AppleScript error, parse failure).
# Callers in --auto mode treat 0 as "no work to do" and skip the folder; that
# matches the behavior we'd want for a transient AppleScript hiccup as well as
# a genuinely-unchanged folder, since either way there's nothing to back up.
def count_notes_modified_since(folder, watermark_iso, notes_account):
    """Return int count of notes in `folder` whose modification date is
    strictly greater than `watermark_iso` (an ISO 8601 string of the form
    'YYYY-MM-DDTHH:MM:SS' produced by R18's data layer).

    Args:
        folder (str): Notes folder name. Required.
        watermark_iso (str): ISO 8601 watermark string, or None / empty if the
            folder has no recorded watermark yet (caller should normally check
            this before calling and skip-with-warning rather than ask us to
            count -- but be defensive).
        notes_account (str): macOS Notes account to scope the lookup to (R6).

    Returns:
        int: count of notes with mod date > watermark. 0 on any failure or
            unparseable watermark.
    """
    if not watermark_iso:
        return 0
    wm = parse_watermark_iso(watermark_iso)
    if wm is None:
        return 0

    # R9: applescript_escape covers backslash + quote + newline/CR/tab.
    folder_escaped = applescript_escape(folder)
    notes_account_escaped = applescript_escape(notes_account)

    applescript = f'''
    tell application "Notes"
        set targetAccount to "{notes_account_escaped}"
        tell account targetAccount
            try
                set targetFolder to folder "{folder_escaped}"
            on error
                return 0
            end try
            set folderNotes to every note in targetFolder
            -- Build watermark date from components (locale-independent).
            set wm to current date
            set year of wm to {wm.year}
            set month of wm to {wm.month}
            set day of wm to {wm.day}
            set time of wm to ({wm.hour} * 3600 + {wm.minute} * 60 + {wm.second})
            set modifiedCount to 0
            repeat with theNote in folderNotes
                if (modification date of theNote) > wm then
                    set modifiedCount to modifiedCount + 1
                end if
            end repeat
            return modifiedCount
        end tell
    end tell
    '''
    success, output = process_applescript(applescript)
    if not success:
        return 0
    try:
        return int(output)
    except (TypeError, ValueError):
        return 0


## PRINT OPTIONS
def debug_print(*args, **kwargs):
    """print() wrapper gated on PRINT_LEVEL >= DEBUG. Prefixes 'DEBUG:' so
    grep can separate chatty trace lines from RESULT-level output. Intentionally
    stdout-only -- the R4 logger captures warning/error events; this is for
    interactive tracing during development."""
    if PRINT_LEVEL.value >= PrintLevel.DEBUG.value:
        print("DEBUG:", *args, **kwargs)

def results_print(*args, **kwargs):
    """print() wrapper gated on PRINT_LEVEL >= RESULTS. Prefixes 'RESULT:' for
    the everyday outcome lines (per-folder summaries, audit-row notices) that
    a non-debug interactive run still wants to see. Stdout-only by design --
    see debug_print's note on the logger split."""
    if PRINT_LEVEL.value >= PrintLevel.RESULTS.value:
        print("RESULT:", *args, **kwargs)


def setup_logging():
    """Configure the gitmynotes logger (R4, incremental; R20 level drop).

    Attaches a FileHandler to '<script_dir>/gitmynotes.log' at INFO level
    (R20: dropped from WARNING so per-batch timing logs around the osascript
    export pass and the pandoc conversion sweep land in the file -- semantic
    separation between 'timing data' and 'things that went wrong'). Uses
    append mode (default) so each run extends the same file -- no size-based
    rotation in this pass; can swap in RotatingFileHandler later if the file
    grows uncomfortably. Format includes a timestamp and level so non-
    interactive consumers (Cowork routines, post-mortem inspection) can parse
    the file without dealing with ANSI codes from the TTY-oriented prints.

    Idempotent: skips re-adding the handler if a FileHandler already points at
    the same path (defensive against any future re-entry into main()).
    """
    log_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "gitmynotes.log",
    )

    for existing in logger.handlers:
        if (isinstance(existing, logging.FileHandler)
                and getattr(existing, "baseFilename", None) == log_path):
            return

    handler = logging.FileHandler(log_path)
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)




def build_initial_msg(this_msg=None, folder=None, max_notes=None, export_path=None, github_url=None, print_level=None, local_only=None):
    # get some values for an initial msg
    
    if this_msg:
        initial_msg = f'''{this_msg}
'''    
    else:
        initial_msg = f'''    Welcome, 'tis a good day to GitMyNotes

    NOTE: locked notes unlocked in this Notes.app session export as cleartext.
    Close them before running if that's not what you want. (See README.)

'''
    if folder:
        initial_msg += f'''    - Notes folder: {folder}
'''
    if print_level:
        initial_msg += f'''    - print-level: {print_level}
'''
    if max_notes:
        initial_msg += f'''    - max-notes: {max_notes}
'''
    if export_path:
        initial_msg += f'''    - Export to: {export_path}
'''
    if local_only:
        initial_msg += f'''    - Local Only option set via '--local'. 
        DO NOT SEND TO:
'''
    if github_url:
        initial_msg += f'''    - GitHub repo: {github_url}
'''
    
    return initial_msg



def build_final_msg(gitnotes_url, audit_file, usage_totals, share_url):
    # get some values for an initial msg
    
    
    final_msg = f'''    GitMyNotes actions complete!

'''
    if gitnotes_url:
        final_msg += f'''    - Check your GitMyNotes: {gitnotes_url}
'''
    if audit_file:
        final_msg += f'''    - Check your audit file: {audit_file}
'''
    if usage_totals:
        final_msg += f'    - Runs::Folders::Notes: '+str(usage_totals[0])+'::'+str(usage_totals[1])+'::'+str(usage_totals[2])
    final_msg += f'''
'''
    if share_url:
        final_msg += f'''    - Tell your friends, learn more: https://GitMyNotes.com/
    
'''
    
    return final_msg




def process_one_folder(folder, max_notes_request, args, run_config, run_state, skip_5x_confirm=False):
    """Process a single Notes folder end-to-end.

    R18 feature-layer refactor: the per-folder pipeline (count -> optional 5x
    confirm -> batch loop -> export -> commit/push -> audit -> move -> restore
    -> per-folder watermark advance) now lives here so main() can call it once
    in normal mode or repeatedly under --auto without duplicating the logic.

    Args:
        folder (str): Notes folder to process. Required (caller has already
            handled the no-folder case via the B10 guard or by iterating
            USAGE_FOLDERS_PROCESSED).
        max_notes_request (int|None): user's --max-notes intent for this
            folder, or under --auto the count returned by
            count_notes_modified_since() so the loop is bounded by what's
            actually changed.
        args (argparse.Namespace): parsed CLI args. Read for batch_size,
            export_path, github_url, local_only, force, restore_notes,
            newline_delimiter, audit_file_ending, notes_account. Not mutated.
        run_config (dict): per-run config values pulled from gmn_config.yaml
            once in main() and threaded in. Required keys:
                'currentnote_file' (str, absolute path post-B9),
                'metadata_rows_file' (str, absolute path post-R5),
                'unsupported_folder_ending' (str),
                'processed_folder_ending' (str),
                'wrapper_dir' (str),
                'loopcount_before_confirm' (int),
                'body_format' (str, 'markdown' or 'html', R8). 'markdown' runs
                    the pandoc conversion sweep before git_add_commit_push;
                    'html' is the legacy pass-through (AppleScript writes .md
                    directly, no Python conversion).
        run_state (dict): mutable run-level state. This function MUTATES:
                'USAGE_NOTES_PROCESSED' (int): incremented by total
                    notes_processed in this folder pass.
                'USAGE_FOLDERS_PROCESSED' (dict): the watermark for `folder`
                    is advanced if a strictly-greater max mod-date was
                    observed (R18 data layer's beta semantics).
                'folders_dirty' (bool): flipped True on any change to
                    USAGE_FOLDERS_PROCESSED.
        skip_5x_confirm (bool): True for --auto runs (5x-batch confirmation
            suppressed entirely per R18 design). False for normal interactive
            runs, which keep the existing prompt behavior.

    Returns:
        dict with keys:
            'folder' (str): the folder processed (echoed back for the auto
                loop's summary).
            'partial' (bool): True if any partial-success signal fired in this
                folder pass (B1 short-export, git_add_commit_push False,
                move_processed_notes falsy after real export work).
            'aborted_by_user' (bool): True if user typed 'x' at the 5x-batch
                confirmation prompt (only possible when skip_5x_confirm=False
                AND --force / --yes is not set).
            'notes_processed' (int): total notes exported across this folder's
                batches (used by the auto loop's summary).
            'loop_count' (int): how many batches actually ran (0 means no-op,
                e.g. empty folder, --max-notes=0, or --auto count=0).
            'audit_file' (str): the audit CSV path for this folder.
            'gitnotes_url' (str): GitHub URL pointing at this folder's subdir.
    """
    partial_for_folder = False
    aborted_by_user = False
    wrapper_dir = run_config['wrapper_dir']
    audit_file = f"./{folder}{args.audit_file_ending}"

    # gitnotes_url for the per-folder summary (matches the legacy build_final_msg
    # construction: with wrapper_dir if set, otherwise direct).
    if wrapper_dir:
        gitnotes_url = f"{args.github_url}/tree/main/{wrapper_dir}/{folder}"
    else:
        gitnotes_url = f"{args.github_url}/tree/main/{folder}"

    # Make sure this folder's local export subdir exists (was hoisted out of the
    # batch loop in main() pre-refactor; per-folder under R18 it has to live
    # here so each folder's subdir gets created).
    export_path_w_folder = f"{args.export_path}/{wrapper_dir}/{folder}"
    os.makedirs(export_path_w_folder, exist_ok=True)

    # Mark folder dirty if we've never seen it before (data-layer pre-loop block
    # used to live in main; in --auto mode the caller already iterated
    # USAGE_FOLDERS_PROCESSED so the folder will already be there, but a
    # manual --folder=NEWFOLDER run is always possible so handle it here too).
    if folder not in run_state['USAGE_FOLDERS_PROCESSED']:
        run_state['USAGE_FOLDERS_PROCESSED'][folder] = None
        run_state['folders_dirty'] = True

    # Folder note count + 5x-batch decision
    folder_count = get_foldernotecount(folder, args.notes_account)
    if max_notes_request:
        if max_notes_request > folder_count:
            notes_to_process = folder_count
        else:
            notes_to_process = max_notes_request
    else:
        notes_to_process = folder_count

    if not skip_5x_confirm and notes_to_process > (args.batch_size * run_config['loopcount_before_confirm']):
        if args.force:
            print(f"In the original command --force was set, continuing without confirm...")
        else:
            confirm_warn = f'''WHOA. {notes_to_process} notes to process in '{folder}' folder!

    <<<< Confirmation Required.>>>>

Add '--force' to skip confirmation in the future.'''
            logger.warning(
                f"Large batch confirmation triggered: {notes_to_process} notes in '{folder}' "
                f"(>{args.batch_size}*{run_config['loopcount_before_confirm']}). Awaiting interactive confirmation."
            )
            print_color(textcolor='magenta', msg=f"{confirm_warn}", addseparator=True)
            confirm_msg = f'''Please input:
  a number up to {notes_to_process} of notes to process,
  or 'x' to eXit
  [Or 'enter' to process all {notes_to_process} notes] : '''

            confirm_num = input(f"{confirm_msg}") or f"{notes_to_process}"
            if confirm_num == 'x' or confirm_num == '0':
                # Clean user-initiated abort. Nothing has happened yet -- no export,
                # no git ops -- so this is a successful no-op for this folder.
                # Caller (main()) will sys.exit(EXIT_SUCCESS) on this signal in
                # non-auto mode. Under --auto the prompt is suppressed entirely
                # so this branch is unreachable.
                print_color(textcolor='red', msg="    Exiting GitMyNotes...", addseparator=True)
                aborted_by_user = True
                return {
                    'folder': folder,
                    'partial': False,
                    'aborted_by_user': True,
                    'notes_processed': 0,
                    'loop_count': 0,
                    'audit_file': audit_file,
                    'gitnotes_url': gitnotes_url,
                }
            confirm_num = int(confirm_num)
            if confirm_num > notes_to_process:
                confirm_num = notes_to_process
            debug_print(f"aa Notes to process: {confirm_num}")
            notes_to_process = confirm_num

    # Loop math
    loop_count = math.ceil(notes_to_process / args.batch_size) if notes_to_process > 0 else 0

    debug_print("IN process_one_folder")
    debug_print(f"folder {folder}")
    debug_print(f"notes_to_process {notes_to_process}")
    debug_print(f"args.batch_size {args.batch_size}")

    if notes_to_process == args.batch_size:
        final_loop_size = args.batch_size
    else:
        final_loop_size = notes_to_process % args.batch_size
        if final_loop_size == 0:
            final_loop_size = args.batch_size

    debug_print(f"final_loop_size {final_loop_size}")

    notes_processed = 0
    processednotes_data = 0
    notes_processed_total = 0
    # R18 data layer: track running max mod-date across this folder's batches.
    new_watermark_dt = None

    for x in range(1, loop_count + 1):
        print_color(textcolor="cyan", msg=f"    Begin export of Notes with batch {x} of {loop_count}", addseparator=True)

        if loop_count == 1:
            notes_to_export = notes_to_process
        if x < loop_count:
            notes_to_export = args.batch_size
        if x == loop_count:
            notes_to_export = final_loop_size
        print(f"batch size for this loop: {notes_to_export}")

        if notes_to_export > 0:
            notes_processed = export_notes_to_markdown(
                run_config['currentnote_file'],
                run_config['metadata_rows_file'],
                args.export_path,
                args.notes_account,
                run_config['unsupported_folder_ending'],
                run_config['body_format'],
                folder,
                notes_to_export,
                wrapper_dir,
            )
            # B1 partial-success signal: when an unsupported (image-bearing)
            # note aborts the batch mid-flight, export_notes_to_markdown returns
            # the count of notes successfully exported BEFORE the bad one.
            if notes_processed < notes_to_export:
                partial_for_folder = True

        if notes_processed > 0:
            notes_processed_total += notes_processed
            print_color(textcolor="green", msg=f"SUCCESS: Exported {notes_processed} Notes to local folder {args.export_path}")

            # R5/R8: read the metadata side-channel file BEFORE git so we can
            # (R8) run the pandoc HTML->markdown sweep on the per-note temp
            # .html files BEFORE git stages them. The audit-row WRITE stays
            # below (post-git) -- the read just had to happen earlier so the
            # sweep has its iteration list.
            metadata_rows = read_metadata_rows(
                metadata_rows_file=run_config['metadata_rows_file'],
                expected_count=notes_processed,
                folder=folder,
            )

            # R8: in 'markdown' mode, convert each note's per-batch
            # <cleanTitle>.html temp file to its final <cleanTitle>.md via
            # pandoc, prepending YAML frontmatter (title + creation_date +
            # modification_date). Pure pass-through in 'html' mode --
            # AppleScript already wrote the .md directly with embedded HTML.
            # A failure on any one note flips partial_for_folder so the run
            # exits EXIT_PARTIAL_SUCCESS.
            if run_config['body_format'] == 'markdown':
                sweep_clean = run_pandoc_conversion_sweep(
                    metadata_rows, args.export_path, folder, wrapper_dir,
                )
                if not sweep_clean:
                    partial_for_folder = True

            ## SEND TO GITHUB BY DEFAULT, UNLESS 'LOCAL' OPTION SET TRUE
            if args.local_only:
                print_color(textcolor="magenta", msg=f"The --local-only flag is set. No notes sent to Github", addseparator=True)
                git_clean = False
            else:
                git_start = time.time()
                git_clean = git_add_commit_push(args.export_path, folder, wrapper_dir)
                git_duration_ms = (time.time() - git_start) * 1000

                # Report sync metrics to Asana (if configured)
                if notes_processed > 0:
                    report_sync_to_asana(
                        folder_name=folder,
                        notes_processed=notes_processed,
                        notes_failed=0,
                        sync_duration_ms=git_duration_ms,
                        git_success=git_clean,
                        audit_file=audit_file,
                    )

                if not git_clean:
                    partial_for_folder = True

        else:
            metadata_rows = []
            logger.warning(f"No notes were processed in batch {x}/{loop_count} for folder '{folder}'; skipping git commit.")
            print_color(textcolor="magenta", msg=f"No notes were processed, skipping git commit")

        ## if notes were processed to git, then create the audit trail and move the notes
        if notes_processed > 0:
            debug_print(f"NOTES PROCESSED > 0: {notes_processed}")
            print_color(textcolor="white", msg=f"Notes to export to markdown: {notes_processed}")
            debug_print(f'''BEFORE audit-row build:
output_file={audit_file}
folder={folder}
notes_processed={notes_processed}
metadata_rows_file={run_config['metadata_rows_file']}''')

            # R5/R8: metadata_rows was read above (pre-git, so the pandoc
            # sweep had its iteration list). Reuse here for the audit CSV
            # write -- replaces the second osascript pass the legacy
            # export_notes_metadata used to fire.
            processednotes_data = write_audit_rows(audit_file, metadata_rows)

            # R18 data layer: feed this batch's max mod-date into the running
            # max for the folder. Used post-loop to advance the folder's
            # watermark in USAGE_FOLDERS_PROCESSED if strictly greater.
            batch_max = max_mod_date_from_rows(processednotes_data)
            if batch_max is not None and (new_watermark_dt is None or batch_max > new_watermark_dt):
                new_watermark_dt = batch_max

        if processednotes_data:
            move_result = move_processed_notes(
                folder_source=folder,
                folder_dest=f"{folder}{run_config['processed_folder_ending']}",
                max_notes=notes_processed,
                notes_account=args.notes_account,
                create=True,
            )
        else:
            move_result = 0
            print_color(textcolor="magenta", msg=f"No Notes to Move")

        if move_result:
            print_color(textcolor="green", msg=f"SUCCESS: Moved notes to Notes folder: '{folder}{run_config['processed_folder_ending']}'", addseparator=True)
        else:
            # Only treat this as a partial-success signal when we actually
            # expected a move to happen (i.e., we had processednotes_data).
            if processednotes_data:
                partial_for_folder = True
            logger.error(
                f"Failed to move processed notes from '{folder}' to "
                f"'{folder}{run_config['processed_folder_ending']}' (batch {x}/{loop_count})."
            )
            print_color(textcolor="red", msg=f"    !!! FAILED to MOVE notes !!!", addseparator=True)

        ######## ----  update usage counts (in-memory; flushed once at end of run, R10)  ---- #######
        results_print(f"++++++++++  Update config yaml usage stats  +++++++++++++")
        debug_print(f"(before)USAGE_NOTES_PROCESSED: {run_state['USAGE_NOTES_PROCESSED']}")
        debug_print(f"notes_processed: {notes_processed}")

        run_state['USAGE_NOTES_PROCESSED'] = int(run_state['USAGE_NOTES_PROCESSED']) + int(notes_processed)
        debug_print(f"(after)USAGE_NOTES_PROCESSED: {run_state['USAGE_NOTES_PROCESSED']}")
        debug_print(f"++++++++++++++++++++++++++++++++++++++++++++++")

    # R18 data layer: post-loop, advance this folder's watermark if a strictly-
    # greater max mod-date was observed (beta semantics: only advances). Skip
    # the advance entirely on a no-op run (loop_count == 0).
    if loop_count > 0 and new_watermark_dt is not None:
        existing_dt = parse_watermark_iso(run_state['USAGE_FOLDERS_PROCESSED'].get(folder))
        if existing_dt is None or new_watermark_dt > existing_dt:
            run_state['USAGE_FOLDERS_PROCESSED'][folder] = new_watermark_dt.isoformat(timespec='seconds')
            run_state['folders_dirty'] = True

    if processednotes_data:
        ## check for restore-empty-source-folder to decide what to do with contents of folder_GitMyNotes backup folders
        debug_print(f"Option --restore-notes is '{args.restore_notes}'")

        restore_result = 0
        restore_result = restore_source_foldernote(
            folder_source=folder,
            folder_bkup=f"{folder}{run_config['processed_folder_ending']}",
            restore_notes=args.restore_notes,
            notes_account=args.notes_account,
        )

        if restore_result:
            print_color(textcolor="green", msg=f"SUCCESS: RESTORED notes to {folder} from {folder}{run_config['processed_folder_ending']}", addseparator=True)
        else:
            restore_declined_msg = f'''    << Notes not restored to '{folder}' >>
        Set --restore-notes=empty to move notes back to '{folder}' when notecount is 0
        Set --restore-notes=always to move notes back to '{folder}' after every backup'''
            print_color(textcolor="red", msg=f"{restore_declined_msg}", addseparator=True)

    return {
        'folder': folder,
        'partial': partial_for_folder,
        'aborted_by_user': aborted_by_user,
        'notes_processed': notes_processed_total,
        'loop_count': loop_count,
        'audit_file': audit_file,
        'gitnotes_url': gitnotes_url,
    }


def main():
    """CLI entry point. Orchestrates one GitMyNotes run end-to-end.

    Pipeline (high-level):
      1. Wire up the file logger (R4) so warning/error events from any later
         stage land in <script_dir>/gitmynotes.log.
      2. Load gmn_config.yaml via load_configs_from_file and pull every
         DEFAULT_* value into a local. Resolve DEFAULT_CURRENTNOTE_FILE (B9)
         and DEFAULT_METADATA_ROWS_FILE (R5) to absolute paths anchored to
         the script directory if the config values are relative.
      3. Validate DEFAULT_BODY_FORMAT (R8) and, in 'markdown' mode, verify
         pandoc is on PATH -- missing pandoc hard-fails the run with
         EXIT_HARD_FAILURE before any work happens.
      4. Build the argparse parser, parse args, apply --yes implications (B8:
         --yes implies --force and converts the ChangeMe-on-first-run prompt
         into a fail-fast).
      5. If DEFAULT_GITHUB_URL is still the <ChangeMe> placeholder, either
         prompt the user interactively (and update gmn_config.yaml in place)
         or fail fast under --yes / --non-interactive (B8).
      6. setup_git_repo on the export root.
      7. Bundle per-run config + mutable run_state into dicts for
         process_one_folder, then either:
           - --auto: walk USAGE_FOLDERS_PROCESSED (or the single folder named
             via --auto --folder=NAME, R18b), call count_notes_modified_since
             for each, skip folders with null watermarks (yellow warning),
             and call process_one_folder per folder with per-folder failure
             isolation (one stale folder doesn't black-hole the others).
           - non-auto: run B10 folder guard, then a single process_one_folder
             call. R18-era refactor; pre-R18 the batch loop lived inline here.
      8. After all folders, write the per-run usage counter updates to
         gmn_config.yaml in a single update_yaml_config_multi call (R10) --
         one yaml round-trip per run regardless of batch / folder count.
      9. Exit with EXIT_SUCCESS / EXIT_PARTIAL_SUCCESS per the cross-cutting
         taxonomy. Hard-failure paths sys.exit(EXIT_HARD_FAILURE) directly
         earlier and never reach this final exit.

    No args, no return value. Side effects: log writes, git operations,
    AppleScript invocations, file writes under DEFAULT_EXPORT_PATH, in-place
    edits to gmn_config.yaml.
    """

    # R4 (incremental): wire up the file logger first so any subsequent
    # warning- / error-level event in this run lands in <script_dir>/gitmynotes.log
    # alongside the existing colored TTY prints. Hardcoded log location for now;
    # CLI override can be added later if needed.
    setup_logging()

    # Optional Asana reporting: capture a run-start stamp so reports can show
    # duration. ISO-8601 UTC; only used if the connector is enabled at exit.
    run_started_at = datetime.now().astimezone().isoformat(timespec="seconds")

    # Exit-code taxonomy: track whether anything in this run was less-than-clean
    # so we can pick between EXIT_SUCCESS and EXIT_PARTIAL_SUCCESS at end of run.
    # Hard-failure paths (bad config, B10 guard, B8 fail-fast) sys.exit() directly
    # with EXIT_HARD_FAILURE before they can flip this flag. Sites that flip it:
    #   - B1 short-export (notes_processed < notes_to_export when batch was nonzero)
    #   - git_add_commit_push() returns False (commit error or push failure)
    #   - move_processed_notes() falsy result after a real export+commit
    partial_success = False

    ######## ----  Get DEFAULT_& vars from config file     ---- #######
    DEFAULT_NOTES_FOLDER_FORCE = None ##special case not in config file because... reasons.
    DEFAULT_LOCAL_ONLY = None ##special case not in config file to turn OFF sending to github
    
    cfg = load_configs_from_file()
    DEFAULT_GITHUB_URL = cfg['DEFAULT_GITHUB_URL']
    
    DEFAULT_NOTES_FOLDER = cfg['DEFAULT_NOTES_FOLDER']
    DEFAULT_EXPORT_PATH = cfg['DEFAULT_EXPORT_PATH']
    DEFAULT_BATCH_SIZE = cfg['DEFAULT_BATCH_SIZE']
    DEFAULT_NOTES_WRAPPERDIR = cfg['DEFAULT_NOTES_WRAPPERDIR']
    DEFAULT_PROCESSED_FOLDER_ENDING = cfg['DEFAULT_PROCESSED_FOLDER_ENDING']
    # R14: cfg.get fallback covers users who upgrade without updating their yaml
    # (the historic literal '_unsupported' is preserved as the default).
    DEFAULT_UNSUPPORTED_FOLDER_ENDING = cfg.get('DEFAULT_UNSUPPORTED_FOLDER_ENDING', '_unsupported')
    DEFAULT_AUDIT_FILE_ENDING = cfg['DEFAULT_AUDIT_FILE_ENDING']
    DEFAULT_LOOPCOUNT_BEFORE_CONFIRM = cfg['DEFAULT_LOOPCOUNT_BEFORE_CONFIRM']
    DEFAULT_NEWLINE_DELIMITER = cfg['DEFAULT_NEWLINE_DELIMITER']
    DEFAULT_RESTORE_NOTES = cfg['DEFAULT_RESTORE_NOTES']
    DEFAULT_CURRENTNOTE_FILE = cfg['DEFAULT_CURRENTNOTE_FILE']
    # B9: resolve DEFAULT_CURRENTNOTE_FILE to an absolute path so AppleScript's
    # shell (osascript cwd is usually $HOME) and Python (cwd = wherever the user
    # invoked the script) agree on where the side-channel file lives. If the
    # config value is already absolute, respect it; otherwise anchor to the
    # directory containing this script, which keeps the existing .gitignore
    # entry valid and keeps the file inspectable while debugging.
    if not os.path.isabs(DEFAULT_CURRENTNOTE_FILE):
        DEFAULT_CURRENTNOTE_FILE = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            DEFAULT_CURRENTNOTE_FILE,
        )
    # R5: side-channel file for inline metadata collection during the
    # export_notes_to_markdown AppleScript pass (replaces the separate
    # export_notes_metadata pass). Same absolute-path treatment as
    # DEFAULT_CURRENTNOTE_FILE (B9) for the same reason: osascript's shell cwd
    # and Python's cwd can disagree, so anchor to the script directory unless
    # the config value is already absolute. cfg.get fallback covers users who
    # upgrade without updating their yaml.
    DEFAULT_METADATA_ROWS_FILE = cfg.get('DEFAULT_METADATA_ROWS_FILE', 'metadata_rows.txt')
    if not os.path.isabs(DEFAULT_METADATA_ROWS_FILE):
        DEFAULT_METADATA_ROWS_FILE = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            DEFAULT_METADATA_ROWS_FILE,
        )
    # Read PRINT_LEVEL from config; default to 'ALL' if missing. CLI '--print' can override.
    cfg_print_level = cfg.get('PRINT_LEVEL', 'ALL')

    # R6: macOS Notes account name. cfg.get fallback covers users who upgrade
    # without updating their yaml. CLI --notes-account overrides per-run.
    DEFAULT_NOTES_ACCOUNT = cfg.get('DEFAULT_NOTES_ACCOUNT', 'iCloud')

    # R8+: body format control (preferred new key is the simple boolean).
    # CONVERT_TO_MARKDOWN: true   -> convert each note's HTML body to GitHub-flavored
    #                                 markdown via pandoc + write clean YAML frontmatter.
    # CONVERT_TO_MARKDOWN: false  -> skip pandoc entirely; emit raw HTML body inside
    #                                 the .md file (plus legacy <div> date headers).
    # If CONVERT_TO_MARKDOWN is absent, fall back to the legacy string key for
    # backward compatibility with existing gmn_config.yaml files.
    convert_flag = cfg.get('CONVERT_TO_MARKDOWN', None)
    if convert_flag is not None:
        if not isinstance(convert_flag, bool):
            logger.error("CONVERT_TO_MARKDOWN must be a boolean (true or false).")
            print_color(
                textcolor="red",
                msg="ERROR: 'CONVERT_TO_MARKDOWN' in 'gmn_config.yaml' must be true or false (boolean).",
                addseparator=True,
            )
            sys.exit(EXIT_HARD_FAILURE)
        DEFAULT_BODY_FORMAT = 'markdown' if convert_flag else 'html'
    else:
        # legacy fallback (still supported)
        DEFAULT_BODY_FORMAT = cfg.get('DEFAULT_BODY_FORMAT', 'markdown')
        if DEFAULT_BODY_FORMAT not in ('markdown', 'html'):
            logger.error(
                f"Invalid DEFAULT_BODY_FORMAT '{DEFAULT_BODY_FORMAT}' in gmn_config.yaml; "
                f"must be 'markdown' or 'html' (or use the preferred 'CONVERT_TO_MARKDOWN' boolean)."
            )
            print_color(
                textcolor="red",
                msg=(
                    f"ERROR: 'DEFAULT_BODY_FORMAT' in 'gmn_config.yaml' is set to '{DEFAULT_BODY_FORMAT}'.\n"
                    f"    Allowed values are 'markdown' or 'html', or (preferred) set CONVERT_TO_MARKDOWN: true/false.\n"
                    f"    Edit gmn_config.yaml and re-run."
                ),
                addseparator=True,
            )
            sys.exit(EXIT_HARD_FAILURE)

    # R8: in 'markdown' mode pandoc is a hard prerequisite -- the per-note .html
    # files written by AppleScript are converted to .md by a Python sweep that
    # shells out to `pandoc -f html -t gfm`. Fail-fast here (before any folder
    # iteration, AppleScript invocation, or git work) with a remediation message
    # pointing at both ways out. 'html' mode (CONVERT_TO_MARKDOWN: false) has no
    # external dependencies.
    if DEFAULT_BODY_FORMAT == 'markdown' and not shutil.which('pandoc'):
        logger.error(
            "CONVERT_TO_MARKDOWN=true (or legacy DEFAULT_BODY_FORMAT='markdown') requires pandoc on PATH but it was not found."
        )
        print_color(
            textcolor="red",
            msg=(
                "ERROR: 'pandoc' is required when CONVERT_TO_MARKDOWN is true (the default).\n"
                "    Two ways to resolve:\n"
                "      1. Install pandoc:    brew install pandoc\n"
                "      2. Or disable conversion by editing 'gmn_config.yaml':\n"
                "             CONVERT_TO_MARKDOWN: false\n"
                "         (Produces the same raw-HTML-inside-.md output as before R8.)\n"
                "    Then re-run. Exiting."
            ),
            addseparator=True,
        )
        sys.exit(EXIT_HARD_FAILURE)
    
    USAGE_GITMYNOTES_TOTAL = cfg['USAGE_GITMYNOTES_TOTAL']
    USAGE_FOLDERS_PROCESSED = cfg['USAGE_FOLDERS_PROCESSED']
    USAGE_NOTES_PROCESSED = cfg['USAGE_NOTES_PROCESSED']
    
    ######## ----  Parse the args provided on CLI    ---- #######    
    parser = argparse.ArgumentParser(description="Export macOS Notes to GitHub.")
    # R18b/auto-folder: default is None (sentinel) so we can distinguish a
    # user-supplied --folder=X on the CLI from a quiet fallback to the config's
    # DEFAULT_NOTES_FOLDER. The distinction matters under --auto: an explicit
    # CLI --folder narrows auto-mode to that single folder, while a defaulted
    # value (no --folder on the CLI) leaves auto-mode walking every known
    # folder in USAGE_FOLDERS_PROCESSED. Resolution to the config default
    # happens in the args_folder line below.
    parser.add_argument('--folder', type=str,
                      default=None,
                      help=f"[str] Specific Notes folder to export. If unset, falls back to 'DEFAULT_NOTES_FOLDER' in 'gmn_config.yaml' (currently: '{DEFAULT_NOTES_FOLDER}'). Combine with '--auto' to do a watermark-aware backup of just that one folder instead of every known folder.")

    parser.add_argument('--force', action='store_true',
                      default=DEFAULT_NOTES_FOLDER_FORCE,
                      help=f"[bool] Use as '--force' (no 'true' or 'false' value allowed) to over-ride to the default required user confirmation to process the full count of Notes in the specified folder when it exceed 5x the batch size -- which could be hundreds of notes and could take a looooong time.(default: confirmation will be required)")

    parser.add_argument('--yes', '--non-interactive', action='store_true',
                      default=False,
                      help=f"[bool] Use as '--yes' or '--non-interactive' (no value allowed) for scheduled / non-terminal runs (cron, Cowork routines, CI). Implies '--force' (skips the 5x-batch confirmation) and also fails fast with a clear error if 'DEFAULT_GITHUB_URL' still contains the '<ChangeMe>' placeholder, instead of hanging on the interactive setup prompt. (default: interactive prompting is allowed)")

    # R18 feature layer: --auto walks USAGE_FOLDERS_PROCESSED and backs up
    # only what's changed since the per-folder watermark was last advanced.
    # Pairs naturally with --yes / --non-interactive for unattended scheduled
    # runs. Folders with a null watermark (seeded via a single manual run but
    # never successfully populated) are skipped with a yellow warning.
    parser.add_argument('--auto', action='store_true',
                      default=False,
                      help=f"[bool] Use as '--auto' (no value allowed) to back up every folder GitMyNotes already knows about (those listed in 'USAGE_FOLDERS_PROCESSED' in 'gmn_config.yaml'), but only the notes that have changed since each folder's last successful run. Skips folders with no recorded watermark (instructs you to seed them with one manual '--folder=NAME' run first). Suppresses the 5x-batch confirmation entirely. Per-folder failures are isolated -- one stale folder doesn't stop the others. Combine with '--yes' for unattended scheduled / cron / Cowork-routine runs. Combine with '--folder=NAME' to narrow the auto run to a single known folder (watermark-aware) instead of walking every folder. (default: off)")

    parser.add_argument('--local-only', action='store_true',
                      default=DEFAULT_LOCAL_ONLY,
                      help=f"[bool] Use as '--local-only' (no 'true' or 'false' value allowed) to over-ride to the default action of backing up notes to GitHub. When set, only a local copy of notes will be made. (DEFAULT: Send notes to GitHub repo)")                      

    parser.add_argument('--max-notes', '--maxnotes', '--max', type=int, 
                      help=f'[int] Maximum number of notes to process.')

    parser.add_argument('--batch-size', type=int,
                      default=DEFAULT_BATCH_SIZE,
                      help=f'[int] The number of notes to convert, and git add/commit/push per loop, calculated a max-notes/batch-size. Especially useful for initial runs.(default: {DEFAULT_BATCH_SIZE})')  

    parser.add_argument('--print', '--print-level', type=str,
                      default=cfg_print_level,
                      help=f"[str] Optional set to 'none', 'results', 'debug', 'all' for different in tracking code flow and general debugging. (default from config: '{cfg_print_level}')")
                      
    parser.add_argument('--export-path', '--exportpath',type=str, 
                      default=os.path.expanduser(f"{DEFAULT_EXPORT_PATH}"),
                      help=f'[str] Path to export the notes (default: {DEFAULT_EXPORT_PATH})')

    parser.add_argument('--github-url','--githuburl', type=str,
                      default=DEFAULT_GITHUB_URL,
                      help=f'[str] GitHub repository URL. (default: {DEFAULT_GITHUB_URL})')                       

    parser.add_argument('--newline-delimiter', '--newlinedelimiter',type=str, 
                      default=DEFAULT_NEWLINE_DELIMITER,
                      help=f"[str] Default CSV newline delimiter (default: '{DEFAULT_NEWLINE_DELIMITER}')")

    parser.add_argument('--audit-file-ending','--auditfileending', type=str, 
                      default=DEFAULT_AUDIT_FILE_ENDING,
                      help=f"[str] The audit file extension (default: '{DEFAULT_AUDIT_FILE_ENDING}')")

    parser.add_argument('--restore-notes','--restorenotes', '--restore', type=str,
                      default=DEFAULT_RESTORE_NOTES,
                      help=f"[str] Options: 'empty' or 'always' or 'never'. Determines when to move notes from '<folder>___GitMyNotes' back to their original source folder. The option 'empty' will not restore notes until notecount is 0 in source folder, while 'always' will restore at the end of each GitMyNotes run. Set to 'never' to never move notes back to source folder. (default: 'empty') ")

    parser.add_argument('--notes-account', '--notesaccount', type=str,
                      default=DEFAULT_NOTES_ACCOUNT,
                      help=f"[str] macOS Notes account name (e.g. 'iCloud', 'On My Mac'). Used to scope every AppleScript op to a single account. Most users want 'iCloud'. (default from config: '{DEFAULT_NOTES_ACCOUNT}')")



    args = parser.parse_args()

    # B8: --yes / --non-interactive implies --force so the existing 5x-batch
    # confirmation handler takes its skip-the-prompt branch automatically. The
    # --ChangeMe fail-fast below keys off args.yes separately.
    if args.yes:
        args.force = True

    ## Set up vars to use later
    args_max_notes = args.max_notes
    # R18b/auto-folder: split "explicit CLI --folder=X" from "fell back to
    # config's DEFAULT_NOTES_FOLDER." argparse default is now None so a missing
    # --folder is unambiguous. Both args_folder (the resolved value used by all
    # downstream code) and folder_from_cli (the explicit-pass flag, only
    # consulted by the --auto branch below) are computed here in one place.
    folder_from_cli = (args.folder is not None)
    args_folder = args.folder if args.folder is not None else DEFAULT_NOTES_FOLDER
    args_wrapper_dir = DEFAULT_NOTES_WRAPPERDIR
    args_local_only = args.local_only

    ## Apply --print (or its config default) to the module-level PRINT_LEVEL
    ## so debug_print() and results_print() honor it for the rest of this run.
    global PRINT_LEVEL
    try:
        PRINT_LEVEL = PrintLevel[str(args.print).upper()]
    except (KeyError, AttributeError):
        logger.warning(f"Invalid --print value '{args.print}'. Falling back to ALL.")
        print_color(textcolor="red", msg=f"WARNING: Invalid --print value '{args.print}'. Falling back to ALL.")
        PRINT_LEVEL = PrintLevel.ALL

    # R18 feature layer: B10 folder guard only fires in non-auto mode. In --auto
    # the "folder" is implicit (each known folder in USAGE_FOLDERS_PROCESSED),
    # so requiring an explicit --folder would defeat the purpose.
    #
    # R18b/auto-folder: if the user passes BOTH --folder=X and --auto on the
    # CLI, --folder is honored as a narrowing filter -- auto mode runs only
    # for folder X (still watermark-aware). The detection uses folder_from_cli
    # so that a config-defaulted DEFAULT_NOTES_FOLDER does NOT silently narrow
    # an --auto run; only an explicit CLI --folder triggers the single-folder
    # auto path. The actual narrowing happens inside the `if args.auto:` block
    # further down.
    if not args.auto:
        # B10: guard against folder==None / empty-string. Multi-folder "export
        # all" mode was advertised in the top-of-file docstring and help text
        # but has never actually worked end-to-end -- get_foldernotecount(None)
        # returns None and the next comparison throws TypeError, and multiple
        # downstream paths (audit file naming, __GitMyNotes folder creation,
        # USAGE tracking) assume a real folder name. Rather than leave a broken
        # path silently present, fail fast with a clear remediation. R18's
        # --auto is the proper multi-folder solution; for users not using
        # --auto, the per-folder run is still required.
        if not args_folder:
            logger.error(
                "Refusing to run: no folder specified. Pass --folder <name>, set DEFAULT_NOTES_FOLDER in gmn_config.yaml, or use --auto. (B10 guard.)"
            )
            print_color(
                textcolor="red",
                msg=(
                    "ERROR: GitMyNotes requires an explicit folder to back up.\n"
                    "    Please either pass '--folder <folderName>' on the command line, set\n"
                    "    'DEFAULT_NOTES_FOLDER' in 'gmn_config.yaml' to a real folder name,\n"
                    "    or use '--auto' to back up every folder GitMyNotes already knows about."
                ),
                addseparator=True,
            )
            sys.exit(EXIT_HARD_FAILURE)

    ## set up the initial msg to let people know setup details
    if args.auto:
        # In --auto mode the per-folder "Notes folder: X" line in the banner
        # would be misleading for the walk-all path; we'll print per-folder
        # banners inside process_one_folder + an aggregate summary at the end.
        # The run-level banner just says we're in auto mode -- and, in the
        # R18b/auto-folder narrowing case, names the single folder.
        if folder_from_cli and args_folder:
            auto_mode_line = f"    - Mode: --auto --folder='{args_folder}' (single-folder, watermark-aware)\n"
        else:
            auto_mode_line = "    - Mode: --auto (walking USAGE_FOLDERS_PROCESSED)\n"
        initial_msg = build_initial_msg(this_msg="", folder=None, max_notes=None, export_path=args.export_path, github_url=args.github_url, print_level=PRINT_LEVEL, local_only=args_local_only)
        print_color(textcolor='cyan', msg=f"{initial_msg}{auto_mode_line}", addseparator=True)
    else:
        initial_msg = build_initial_msg(this_msg="", folder=args_folder, max_notes=args_max_notes, export_path=args.export_path, github_url=args.github_url, print_level=PRINT_LEVEL, local_only=args_local_only)
        print_color(textcolor='cyan', msg=f"{initial_msg}", addseparator=True)


    ######## ----  Do INIT work, ensure DEFAULT_GITHUB_URL has been changed    ---- #######
    if USAGE_GITMYNOTES_TOTAL == 0:
        # First-timer block. R18 data layer retired the placeholder-swap that used
        # to live here; with the new mapping shape, an empty USAGE_FOLDERS_PROCESSED
        # is the natural seed value, and the per-folder seeding (with a null
        # watermark) happens just before the batch loop in the folders_dirty block.
        # Kept as a hook for future first-time-user UX (welcome message, etc.).
        results_print(f"USAGE_FOLDERS_PROCESSED : {USAGE_FOLDERS_PROCESSED}")

    if CHANGEME_PLACEHOLDER in DEFAULT_GITHUB_URL:
        changeme_msg = "WHOA, the 'DEFAULT_GITHUB_URL' setting in 'gmn.config.yaml' has not been updated to your Github username"
        logger.warning("DEFAULT_GITHUB_URL still contains '<ChangeMe>' placeholder; will prompt for setup unless --yes is set.")
        print_color(textcolor="magenta", msg=f"{changeme_msg}")

        # B8: in non-interactive mode we cannot prompt -- fail fast with a clear
        # remediation so a scheduled/cron/Cowork-routine run sees a nonzero exit
        # instead of hanging on input() forever.
        if args.yes:
            logger.error(
                "Refusing to run in non-interactive mode: DEFAULT_GITHUB_URL still contains '<ChangeMe>'. "
                "Update gmn_config.yaml before re-running with --yes. (B8 fail-fast.)"
            )
            print_color(
                textcolor="red",
                msg=(
                    "Cannot prompt for GitHub username: '--yes' / '--non-interactive' is set.\n"
                    "    Edit 'gmn_config.yaml' and change 'DEFAULT_GITHUB_URL' from the '<ChangeMe>'\n"
                    "    placeholder to your real GitHub repo URL, e.g.:\n"
                    "        'DEFAULT_GITHUB_URL': 'https://github.com/<yourname>/gitmynotes'\n"
                    "    Then re-run. Exiting."
                ),
                addseparator=True,
            )
            sys.exit(EXIT_HARD_FAILURE)

        usage_github_username = input("Please enter your GitHub username: ")
        print(f"The 'DEFAULT_GITHUB_URL' will be updated to 'https://github.com/{usage_github_username}/gitmynotes'")
        ## now update the yaml file
        update_yaml_config('gmn_config.yaml', 'DEFAULT_GITHUB_URL', f"https://github.com/{usage_github_username}/gitmynotes")
        cfg = load_configs_from_file()
        DEFAULT_GITHUB_URL = cfg['DEFAULT_GITHUB_URL']
        # Keep args.github_url consistent with the just-saved DEFAULT so every
        # downstream consumer (process_one_folder's gitnotes_url, the final_msg
        # builder) sees the same value.
        args.github_url = DEFAULT_GITHUB_URL


        ## RE-DO the initial msg to let people know setup details have changed
        if args.auto:
            if folder_from_cli and args_folder:
                auto_mode_line = f"    - Mode: --auto --folder='{args_folder}' (single-folder, watermark-aware)\n"
            else:
                auto_mode_line = "    - Mode: --auto (walking USAGE_FOLDERS_PROCESSED)\n"
            initial_msg = build_initial_msg(this_msg="", folder=None, max_notes=None, export_path=args.export_path, github_url=args.github_url, print_level=PRINT_LEVEL, local_only=args_local_only)
            print_color(textcolor='cyan', msg=f"{initial_msg}{auto_mode_line}", addseparator=True)
        else:
            initial_msg = build_initial_msg(this_msg="", folder=args_folder, max_notes=args_max_notes, export_path=args.export_path, github_url=args.github_url, print_level=PRINT_LEVEL, local_only=args_local_only)
            print_color(textcolor='cyan', msg=f"{initial_msg}", addseparator=True)



    ######## ----  BUILD initial dirs per args and DEFAULTS    ---- #######
    # The export_path root is always needed; per-folder subdirs get created
    # inside process_one_folder.
    os.makedirs(args.export_path, exist_ok=True)



    ######## ----  Setup the git repo per args and DEFAULTs    ---- #######
    # Single git repo for the whole run regardless of how many folders are
    # processed -- each folder lands in its own subdir under wrapper_dir.
    setup_git_repo(args.export_path, DEFAULT_GITHUB_URL)


    ######## ----  R18 feature layer: bundle per-run config + state for process_one_folder ---- #######
    run_config = {
        'currentnote_file': DEFAULT_CURRENTNOTE_FILE,
        'metadata_rows_file': DEFAULT_METADATA_ROWS_FILE,
        'unsupported_folder_ending': DEFAULT_UNSUPPORTED_FOLDER_ENDING,
        'processed_folder_ending': DEFAULT_PROCESSED_FOLDER_ENDING,
        'wrapper_dir': args_wrapper_dir,
        'loopcount_before_confirm': DEFAULT_LOOPCOUNT_BEFORE_CONFIRM,
        # R8: body_format ('markdown' or 'html') drives the AppleScript
        # output branch in export_notes_to_markdown and gates the post-export
        # pandoc conversion sweep in process_one_folder. Validated + pandoc
        # availability checked at the top of main().
        'body_format': DEFAULT_BODY_FORMAT,
    }
    run_state = {
        'USAGE_NOTES_PROCESSED': int(USAGE_NOTES_PROCESSED),
        'USAGE_FOLDERS_PROCESSED': USAGE_FOLDERS_PROCESSED,
        'folders_dirty': False,
    }

    # Per-folder outcomes collected for the end-of-run summary (and for the
    # cross-folder partial_success aggregation under --auto).
    folder_outcomes = []

    if args.auto:
        ######## ----  R18 feature layer: --auto mode ---- #######
        # R18b/auto-folder: build the iteration list once. If the user passed
        # an explicit --folder=X on the CLI alongside --auto, narrow to a
        # single (folder, watermark) tuple. If the named folder is not in
        # USAGE_FOLDERS_PROCESSED, fail fast with the same seeding remediation
        # we use for the null-watermark case -- a folder we've never seen
        # cannot be processed watermark-aware, and the user named it
        # explicitly so a silent no-op would be confusing. Otherwise, walk
        # every known folder (the original R18 behavior).
        if folder_from_cli and args_folder:
            if args_folder not in USAGE_FOLDERS_PROCESSED:
                logger.error(
                    f"--auto --folder='{args_folder}': folder is not in USAGE_FOLDERS_PROCESSED. "
                    f"Seed it with one manual run first (gitmynotes --folder={args_folder} --max-notes=1)."
                )
                print_color(
                    textcolor="red",
                    msg=(
                        f"ERROR: '--auto --folder={args_folder}' but '{args_folder}' is not a known folder.\n"
                        f"    GitMyNotes only knows about folders it has successfully run against at\n"
                        f"    least once. Seed this folder with one manual run first:\n"
                        f"        gitmynotes --folder={args_folder} --max-notes=1\n"
                        f"    Then '--auto --folder={args_folder}' will work watermark-aware."
                    ),
                    addseparator=True,
                )
                sys.exit(EXIT_HARD_FAILURE)
            auto_iter = [(args_folder, USAGE_FOLDERS_PROCESSED[args_folder])]
        elif not USAGE_FOLDERS_PROCESSED:
            # Brand-new install -- nothing to walk. Not a failure; just an
            # informational no-op. Only reachable when --auto was invoked
            # WITHOUT --folder; the explicit-folder path above hard-fails
            # earlier with a more targeted message.
            logger.warning("--auto invoked but USAGE_FOLDERS_PROCESSED is empty; nothing to do. Seed folders with one manual --folder=NAME run first.")
            print_color(
                textcolor="yellow",
                msg=(
                    "NOTE: --auto invoked but no folders are seeded yet.\n"
                    "    Seed each folder with one manual run first:\n"
                    "        gitmynotes --folder=YourFolder --max-notes=1\n"
                    "    Then '--auto' will pick up changes from there onward."
                ),
                addseparator=True,
            )
            auto_iter = []
        else:
            auto_iter = list(USAGE_FOLDERS_PROCESSED.items())

        for folder, watermark_iso in auto_iter:
            print_color(textcolor="cyan", msg=f"\n>>> --auto: finding new notes in folder '{folder}' (date>{watermark_iso or 'none'})", addseparator=True)
            if not watermark_iso:
                # Null-watermark folder -- skip with a yellow warning per
                # the R18 design. User must seed manually first so we know
                # what window of changes we should be looking at.
                logger.warning(f"--auto: skipping folder '{folder}' -- watermark is null (seed with: gitmynotes --folder={folder}).")
                print_color(
                    textcolor="yellow",
                    msg=(
                        f"SKIP: '{folder}' has no recorded watermark.\n"
                        f"    Seed it with one manual run first:\n"
                        f"        gitmynotes --folder={folder} --max-notes=1\n"
                        f"    Then this folder will be picked up by --auto."
                    ),
                )
                folder_outcomes.append({'folder': folder, 'status': 'skipped-null-watermark', 'partial': False, 'notes_processed': 0})
                continue

            count_modified = count_notes_modified_since(folder, watermark_iso, args.notes_account)
            if count_modified == 0:
                print_color(textcolor="cyan", msg=f"    No changes since watermark for '{folder}'; nothing to do.")
                folder_outcomes.append({'folder': folder, 'status': 'no-changes', 'partial': False, 'notes_processed': 0})
                continue

            print_color(textcolor="white", msg=f"    {count_modified} note(s) modified since watermark in '{folder}'.")
            try:
                outcome = process_one_folder(
                    folder=folder,
                    max_notes_request=count_modified,
                    args=args,
                    run_config=run_config,
                    run_state=run_state,
                    skip_5x_confirm=True,
                )
            except Exception as exc:
                # R18 design: per-folder failure isolation under --auto.
                # One stale folder shouldn't black-hole the others. Log
                # with traceback, mark as hard-failed-demoted (counts as
                # partial in the aggregate exit code), and continue to the
                # next folder.
                logger.exception(f"--auto: hard failure processing folder '{folder}': {exc}")
                print_color(
                    textcolor="red",
                    msg=f"FAILED: '{folder}' raised an exception during processing -- skipping to next folder. Check gitmynotes.log for traceback.",
                    addseparator=True,
                )
                folder_outcomes.append({'folder': folder, 'status': 'hard-failed-demoted', 'partial': True, 'notes_processed': 0})
                continue

            status = 'partial' if outcome['partial'] else 'clean'
            folder_outcomes.append({
                'folder': folder,
                'status': status,
                'partial': outcome['partial'],
                'notes_processed': outcome['notes_processed'],
            })
    else:
        ######## ----  Non-auto path: single folder per the original CLI contract ---- #######
        outcome = process_one_folder(
            folder=args_folder,
            max_notes_request=args_max_notes,
            args=args,
            run_config=run_config,
            run_state=run_state,
            skip_5x_confirm=False,
        )

        if outcome['aborted_by_user']:
            # Clean user-initiated abort at the 5x-batch confirm. Nothing was
            # exported, no git ops, no yaml writes. Exit 0 per the cross-cutting
            # taxonomy.
            sys.exit(EXIT_SUCCESS)

        status = 'partial' if outcome['partial'] else 'clean'
        folder_outcomes.append({
            'folder': args_folder,
            'status': status,
            'partial': outcome['partial'],
            'notes_processed': outcome['notes_processed'],
        })


    ######## ----  Run-level usage updates + single yaml write    ---- #######
    # B6 + R10: increment USAGE_GITMYNOTES_TOTAL once per run that did real
    # work, then flush all usage counters in a single yaml write per run. The
    # "did real work" gate is now "any folder processed >0 notes." A run that
    # touched zero notes (empty folder, --max-notes 0, --auto with all folders
    # null/no-changes) doesn't bump the run counter or touch the yaml, matching
    # the prior behavior.
    total_notes_this_run = sum(o['notes_processed'] for o in folder_outcomes)
    USAGE_GITMYNOTES_TOTAL_NEW = int(USAGE_GITMYNOTES_TOTAL)
    USAGE_NOTES_PROCESSED_NEW = run_state['USAGE_NOTES_PROCESSED']

    if total_notes_this_run > 0:
        USAGE_GITMYNOTES_TOTAL_NEW = int(USAGE_GITMYNOTES_TOTAL) + 1
        usage_updates = {
            'USAGE_GITMYNOTES_TOTAL': USAGE_GITMYNOTES_TOTAL_NEW,
            'USAGE_NOTES_PROCESSED': USAGE_NOTES_PROCESSED_NEW,
        }
        if run_state['folders_dirty']:
            usage_updates['USAGE_FOLDERS_PROCESSED'] = run_state['USAGE_FOLDERS_PROCESSED']
        update_yaml_config_multi('./gmn_config.yaml', usage_updates)
    elif run_state['folders_dirty']:
        # Edge case: an --auto run might have advanced folders_dirty (e.g. a
        # newly-seeded folder added to the mapping with null watermark) without
        # actually exporting any notes. Flush the folder-mapping change without
        # bumping the run counter.
        update_yaml_config_multi('./gmn_config.yaml', {'USAGE_FOLDERS_PROCESSED': run_state['USAGE_FOLDERS_PROCESSED']})


    ######## ----  Final messaging + exit code    ---- #######
    # partial_success aggregates across all folders. Any partial signal -- B1,
    # git, move, or a hard-failed-demoted folder under --auto -- flips it to
    # True so the run exits with EXIT_PARTIAL_SUCCESS.
    partial_success = any(o['partial'] for o in folder_outcomes)

    share_url = "Get More with GitMyNotes Pro: https://GitMyNotes.com"

    if args.auto:
        # Aggregate auto-mode summary. Lists each folder's outcome plus the
        # usage totals so the user (or a Cowork routine reading the output)
        # can see at a glance what happened.
        summary_lines = ["GitMyNotes --auto run complete!\n"]
        if folder_outcomes:
            summary_lines.append("    Per-folder outcomes:")
            for o in folder_outcomes:
                summary_lines.append(f"      - {o['notes_processed']} note(s) exported from {o['folder']}")
                summary_lines.append(f"      - {o['status']:<24}")  
                summary_lines.append(f"      - {DEFAULT_GITHUB_URL}/tree/main/{args_wrapper_dir}/{o['folder']}")
                summary_lines.append(f"   ")
        else:
            summary_lines.append("    No folders processed (USAGE_FOLDERS_PROCESSED is empty).")
        summary_lines.append("")
        summary_lines.append(f"    Runs::Folders::Notes: {int(USAGE_GITMYNOTES_TOTAL_NEW)}::{len(USAGE_FOLDERS_PROCESSED)}::{int(USAGE_NOTES_PROCESSED_NEW)}")
        summary_lines.append("")
        if share_url:
            summary_lines.append("Tell your friends, learn more: https://GitMyNotes.com/")
        print_color(textcolor="cyan", msg="\n".join(summary_lines), addseparator=True)
    else:
        # Non-auto: existing single-folder final_msg.
        single = folder_outcomes[0] if folder_outcomes else None
        if single:
            if args_wrapper_dir:
                final_gitnotes_url = f"{DEFAULT_GITHUB_URL}/tree/main/{args_wrapper_dir}/{single['folder']}"
            else:
                final_gitnotes_url = f"{DEFAULT_GITHUB_URL}/tree/main/{single['folder']}"
            audit_file = f"./{single['folder']}{args.audit_file_ending}"
            usage_totals = [int(USAGE_GITMYNOTES_TOTAL_NEW), len(USAGE_FOLDERS_PROCESSED), int(USAGE_NOTES_PROCESSED_NEW)]
            final_msg = build_final_msg(gitnotes_url=f"{final_gitnotes_url}", audit_file=f"{audit_file}", usage_totals=usage_totals, share_url=f"{share_url}")
            print_color(textcolor="cyan", msg=f"{final_msg}", addseparator=True)

    # Optional, non-blocking Asana report of this run's per-folder outcomes.
    # No-op unless GMN_ASANA_ENABLED=1 + credentials are set; never raises.
    report_run_to_asana(folder_outcomes, run_started_at)

    # Final exit per the cross-cutting taxonomy. Hard-failure paths (B10 guard,
    # B8 ChangeMe fail-fast) sys.exit(EXIT_HARD_FAILURE) directly and never
    # reach here. The 'x' confirm-exit also routes around this with
    # EXIT_SUCCESS. So at this point the run did its work; we just need to
    # tell the caller whether anything was less-than-clean.
    sys.exit(EXIT_PARTIAL_SUCCESS if partial_success else EXIT_SUCCESS)




############# END OF MAIN





##### ADD SOME COLORs
# pinched and tweaked from https://github.com/impshum/Multi-Quote/blob/master/run.py
class color:
    white, cyan, blue, red, green, yellow, magenta, black, gray, bold = '\033[0m', '\033[96m','\033[94m', '\033[91m','\033[92m','\033[93m','\033[95m', '\033[30m', '\033[30m', "\033[1m"  


# maybe add bks, bolds, etc from https://godoc.org/github.com/whitedevops/colors
class bkcolor:
  resetall = "\033[0m"
  default      = "\033[49m"
  black        = "\033[40m"
  red          = "\033[41m"
  green        = "\033[42m"
  yellow       = "\033[43m"
  blue         = "\033[44m"
  magenta      = "\033[45m"
  cyan         = "\033[46m"
  lightgray    = "\033[47m"
  darkgray     = "\033[100m"
  lightred     = "\033[101m"
  lightgreen   = "\033[102m"
  lightyellow  = "\033[103m"
  lightblue    = "\033[104m"
  lightmagenta = "\033[105m"
  lightcyan    = "\033[106m"
  white        = "\033[107m"
  
  
  
  
def print_color(textcolor='white', msg=None, addseparator=False, textdefault='white', bkcolor=None):
    '''Pass a NEW color, then a string to print and this function will set msg back to textdefault'''
    
    # Get color codes using getattr()
    selected_color = getattr(color, textcolor)
    default_color = getattr(color, textdefault)
    
    if addseparator:
        print(selected_color + "------------------------------------------------" + default_color)
    
    # now the msg
    print(selected_color + f"{msg}" + default_color)
    
    if addseparator:
        print(selected_color + "------------------------------------------------" + default_color)
    
    print(f" ")
    return



            
if __name__ == "__main__":
    main()