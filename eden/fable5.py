"""Fable 5 client — the native communication layer for the Shadow Garden / Eden stack.

Every repo in the Eden constellation talks to Anthropic's Claude Fable 5 model
through this one module, so the model id, refusal-fallback behaviour, and effort
setting stay identical everywhere.

Fable 5 specifics baked in here (per the current Anthropic API surface):
  * Thinking is always on — we never pass a ``thinking`` parameter.
  * Sampling params (temperature / top_p / top_k) are rejected — we never send them.
  * Safety classifiers can return ``stop_reason == "refusal"`` — we opt into a
    server-side fallback to ``claude-opus-4-8`` by default so a decline is
    re-served in the same call, and we raise :class:`Fable5Refused` if the whole
    chain still declines.

Auth: ``Anthropic()`` resolves ``ANTHROPIC_API_KEY`` / ``ANTHROPIC_AUTH_TOKEN`` /
an ``ant auth login`` profile automatically — set one of those before use.

Install the dependency with:  pip install anthropic
"""
from __future__ import annotations

import os
from typing import Optional

try:
    import anthropic
except ImportError as exc:  # pragma: no cover - dependency hint
    raise SystemExit(
        "The 'anthropic' package is required for Fable 5.\n"
        "Install it with:  pip install anthropic"
    ) from exc

FABLE_MODEL = "claude-fable-5"
FALLBACK_MODEL = "claude-opus-4-8"
_FALLBACK_BETA = "server-side-fallback-2026-06-01"


class Fable5Refused(RuntimeError):
    """Raised when Fable 5 (and its fallback) declined the request."""


def has_credentials() -> bool:
    """True if an API key / auth token is present in the environment."""
    return bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN"))


class Fable5:
    """A thin, opinionated wrapper around Anthropic's Claude Fable 5."""

    def __init__(self, api_key: Optional[str] = None, effort: str = "high") -> None:
        self._client = (
            anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
        )
        self.effort = effort

    def ask(
        self,
        prompt: str,
        *,
        system: Optional[str] = None,
        max_tokens: int = 8000,
        effort: Optional[str] = None,
    ) -> str:
        """Send one prompt to Fable 5 and return the text of the reply."""
        params = dict(
            model=FABLE_MODEL,
            max_tokens=max_tokens,
            betas=[_FALLBACK_BETA],
            fallbacks=[{"model": FALLBACK_MODEL}],
            output_config={"effort": effort or self.effort},
            messages=[{"role": "user", "content": prompt}],
        )
        if system:
            params["system"] = system

        resp = self._client.beta.messages.create(**params)

        if resp.stop_reason == "refusal":
            category = None
            if getattr(resp, "stop_details", None):
                category = getattr(resp.stop_details, "category", None)
            raise Fable5Refused(
                f"Fable 5 declined this request (category={category})."
            )

        return "".join(block.text for block in resp.content if block.type == "text")


if __name__ == "__main__":
    import sys

    if not has_credentials():
        print(
            "No ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN set — cannot reach Fable 5."
        )
        raise SystemExit(1)
    _prompt = " ".join(sys.argv[1:]) or "Say hello from Shadow Garden in one line."
    print(Fable5().ask(_prompt))
