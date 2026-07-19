#!/usr/bin/env python3
"""Opt-in, offline Grok/xAI mesh readiness cue for the party-round slice.

Playtest cue only ("is the Grok/xAI lane ready?"), not core play. Deterministic
local reads only: the ``grok`` CLI version line, xAI env var *names* (never their
values), and two local telemetry pointer files. No network calls, no secret
values, no identity inference.

This is an *internal* open-door read under the sovereign boundary: it reads local
state and returns metadata. It never sends to xAI, never reads a secret value into
its output, and degrades gracefully when the CLI or pointer files are absent.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Optional

SCHEMA = "wha_spell_simulator.mesh_status.v1"

_HOME = Path.home()
# Local telemetry pointers (read metadata-only; may be absent, which is fine).
JING_POWER_POINTER = _HOME / "ShadowGarden/live/spacetime_alchemy/jing_power_latest.json"
ASUNA_POINT0_POINTER = _HOME / "ShadowGarden/live/spacetime_alchemy/github_asuna_point0_latest.json"

# xAI env var NAMES only. Values are never read into any output.
XAI_ENV_NAMES = ("XAI_API_KEY",)

# Local loopback runtime surfaces (match the unification manifest endpoints).
RUNTIME_SURFACE_POINTERS = {
    "fable5_game": "http://127.0.0.1:5619/",
    "comfyui": "http://127.0.0.1:8188",
}


def grok_cli_status(timeout_s: float = 3.0) -> dict[str, Any]:
    """Local CLI presence + version line. Never calls the xAI API.

    Runs only ``grok --version`` (a local, offline command) and only if the CLI
    is on PATH. Any failure degrades to a null version rather than raising.
    """
    path = shutil.which("grok")
    if not path:
        return {"present": False, "path": None, "version": None}
    try:
        proc = subprocess.run(
            [path, "--version"],
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
        lines = (proc.stdout or proc.stderr or "").strip().splitlines()
        return {"present": True, "path": path, "version": lines[0] if lines else None}
    except (OSError, subprocess.SubprocessError):
        return {"present": True, "path": path, "version": None}


def xai_env_ready() -> dict[str, Any]:
    """Booleans keyed by env var *name*; values are never read into output."""
    by_name = {name: bool(os.environ.get(name)) for name in XAI_ENV_NAMES}
    return {
        "env_names": list(XAI_ENV_NAMES),
        "ready": all(by_name.values()),
        "by_name": by_name,
    }


def _pointer_meta(path: Path, fields: tuple[str, ...]) -> dict[str, Any]:
    """Read only the named top-level fields from a local JSON pointer file."""
    if not path.exists():
        return {"ok": False, "pointer": str(path)}
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return {"ok": False, "pointer": str(path)}
    out: dict[str, Any] = {"ok": True, "pointer": str(path)}
    for field in fields:
        out[field] = data.get(field)
    return out


def jing_power_pointer(path: Optional[Path] = None) -> dict[str, Any]:
    """Metadata-only read of the local jing_power telemetry pointer."""
    return _pointer_meta(
        path or JING_POWER_POINTER,
        ("jing_power", "sampled_at", "grok_ok", "comfyui_ok", "summary"),
    )


def asuna_point0_pointer(path: Optional[Path] = None) -> dict[str, Any]:
    """Metadata-only read of the Asuna point-0 unification artifact."""
    return _pointer_meta(
        path or ASUNA_POINT0_POINTER,
        ("schema", "generated_at", "phase"),
    )


def mesh_status(
    jing_pointer: Optional[Path] = None,
    asuna_pointer: Optional[Path] = None,
) -> dict[str, Any]:
    """Aggregate the offline readiness cue. Pure-ish: local reads only, no network."""
    grok = grok_cli_status()
    xai = xai_env_ready()
    jing = jing_power_pointer(jing_pointer)
    asuna = asuna_point0_pointer(asuna_pointer)
    return {
        "schema": SCHEMA,
        "role": "opt_in_playtest_cue",
        "offline": True,
        "secretsPolicy": "env_names_only_never_values",
        "grokCli": grok,
        "xaiEnv": xai,
        "jingPower": jing,
        "asunaPoint0": asuna,
        "runtimeSurfacePointers": dict(RUNTIME_SURFACE_POINTERS),
        # Lane is "ready" only if the CLI is present AND the env name is set.
        "grokLaneReady": bool(grok["present"] and xai["ready"]),
        "sources": {
            "version": "local grok CLI --version (no API call)",
            "env": "environment variable names only",
            "pointer": "local telemetry files, metadata-only",
        },
    }


if __name__ == "__main__":
    print(json.dumps(mesh_status(), indent=2, sort_keys=True))
