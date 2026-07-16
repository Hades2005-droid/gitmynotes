# AGENTS.md

## Cursor Cloud specific instructions

GitMyNotes is a **macOS-only** CLI (see `README.md`): it exports macOS Notes.app
notes to Markdown/GitHub via AppleScript (`osascript`). Key implications for the
Linux cloud VM:

- **The full end-to-end app cannot run here.** There is no `osascript`/Notes.app
  on Linux, so note *fetching* (`export_notes_to_markdown`) will not work. The
  platform-independent core — HTML→GFM conversion (`convert_html_to_markdown`,
  uses `pandoc`), YAML frontmatter, CSV audit trail, and the git backup steps —
  does run and is what to exercise/test here.

- **Python deps live in a venv at `.venv`.** Activate it before running anything:
  `source .venv/bin/activate`. Forgetting this yields `ModuleNotFoundError`
  (e.g. `ruamel`). The startup update script (re)creates and refreshes `.venv`.
  System packages `pandoc` and `python3.12-venv` come from the VM snapshot.

- **Tests:** three suites run cleanly from the repo root:
  `python -m pytest test_fable5_comfyui_unification.py test_persona_provenance.py tests/test_asana_adapter.py`.
  The fourth, `test_asana_connector.py`, targets the standalone `asana_connector.py`
  module but **cannot be collected from the repo root**: the `asana_connector/`
  *package* directory shadows the same-named `.py` module, so `import asana_connector`
  resolves to the package (which lacks `ENV_LIVE_TESTS`, `SyncReport`, etc.). This
  is a pre-existing repo name collision, not an environment problem. To run it,
  copy `asana_connector.py` + `test_asana_connector.py` into an isolated directory
  and run pytest there (24 pass, 1 live test skipped).

- **Lint:** the repo declares Datadog static analysis (`static-analysis.datadog.yml`);
  there is no local linter configured to run in-VM.

- **Run the CLI:** `python gitmynotes.py --help`. Config is `gmn_config.yaml`.
