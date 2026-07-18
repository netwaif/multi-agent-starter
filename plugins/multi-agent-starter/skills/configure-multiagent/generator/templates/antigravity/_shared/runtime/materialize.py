"""W5 brief materializer.

Structures a task brief for dispatch to a backend worker. `file_references`
are NEVER an LLM's self-report — they are derived here, deterministically,
from the real attachment paths the orchestrator selected for this dispatch.

Backends whose capability record declares `input_mode: inline_only` (e.g.
`file_read: false`) must never receive:
  - a `file_references` entry (that would imply the worker can read files
    it has no capability to read), or
  - an attachment/materialized-file object on disk, or
  - any path that exposes the worker cwd's original source tree.

For those backends this module only ever inlines approved, size-capped,
secret-scanned file *content* directly into the brief, with provenance
(source_path + sha256) attached to every inlined artifact.

Standard library only. Pure logic — the only I/O is reading the files named
in `task_paths` (this module never writes files).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

# --- size / safety limits -------------------------------------------------

MAX_ARTIFACT_BYTES = 200_000        # per-artifact inline cap
MAX_TOTAL_INLINE_BYTES = 800_000    # total inline budget per brief

# Crude, dependency-free secret scan: flags common credential shapes before
# they get baked into an inline artifact. Not a substitute for a real
# secret scanner — a conservative tripwire only.
_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"AKIA[0-9A-Z]{16}"),                 # AWS access key id
    re.compile(r"ghp_[A-Za-z0-9]{36}"),               # GitHub PAT
    re.compile(r"sk-[A-Za-z0-9]{20,}"),               # OpenAI-style secret key
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),      # Slack token
    re.compile(r"(?i)\bpassword\b\s*[:=]\s*\S+"),
)


class SecretScanError(ValueError):
    """Raised when an artifact matches a probable-secret pattern."""


def scan_for_secrets(text: str) -> list[str]:
    """Return matched secret-pattern strings for `text`. Empty list = clean."""
    return [pat.pattern for pat in _SECRET_PATTERNS if pat.search(text)]


def sha256_of(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


@dataclass
class InlineArtifact:
    source_path: str
    sha256: str
    content: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_path": self.source_path,
            "sha256": self.sha256,
            "content": self.content,
        }


def _is_inline_only(backend_capabilities: dict[str, Any]) -> bool:
    input_mode = backend_capabilities.get("input_mode", "file_read")
    file_read_allowed = bool(backend_capabilities.get("file_read", False))
    return input_mode == "inline_only" or not file_read_allowed


def materialize_brief(
    task_paths: Iterable[str],
    backend_capabilities: dict[str, Any],
    *,
    mission: str = "",
    approved_paths: Iterable[str] | None = None,
    max_artifact_bytes: int = MAX_ARTIFACT_BYTES,
    max_total_inline_bytes: int = MAX_TOTAL_INLINE_BYTES,
) -> dict[str, Any]:
    """Build `{mission, inline_artifacts, file_references}` from real files.

    `task_paths` must be the actual attachment paths the orchestrator
    selected for this dispatch (never an LLM's self-reported file list).
    `backend_capabilities` is the target worker's capability record from
    backends.json, e.g. `{"input_mode": "inline_only", "file_read": False,
    "tool_use": False}`.

    Contract:
    - `input_mode == "inline_only"` (or `file_read: false`) backends get
      ONLY inline artifacts, built from paths in `approved_paths` (defaults
      to all of `task_paths`), subject to per-artifact and total size caps
      and a secret scan. No attachment object is created and no path
      outside the approved set is ever written into the brief in any form
      — the worker's cwd must never see the original source tree.
    - Other (file_read/tool_use-capable) backends may receive
      `file_references` — paths the worker is permitted to read itself.
    - Every inline artifact carries provenance: `source_path` + `sha256`.

    Raises `SecretScanError` if an inline-only artifact trips the secret
    scan (fail closed rather than silently dropping or leaking it).
    """
    task_paths = list(task_paths)
    approved = set(approved_paths) if approved_paths is not None else set(task_paths)
    inline_only = _is_inline_only(backend_capabilities)

    inline_artifacts: list[dict[str, Any]] = []
    file_references: list[str] = []
    total_inline_bytes = 0

    for raw_path in task_paths:
        if raw_path not in approved:
            # Not admitted for this dispatch: never surfaced to the worker,
            # inline or by reference.
            continue

        if inline_only:
            path = Path(raw_path)
            if not path.is_file():
                continue
            data = path.read_bytes()
            if len(data) > max_artifact_bytes:
                continue
            if total_inline_bytes + len(data) > max_total_inline_bytes:
                continue
            text = data.decode("utf-8", errors="replace")
            hits = scan_for_secrets(text)
            if hits:
                raise SecretScanError(
                    f"materialize_brief: refusing to inline {raw_path!r} — "
                    f"matched secret pattern(s): {hits}"
                )
            total_inline_bytes += len(data)
            inline_artifacts.append(
                InlineArtifact(
                    source_path=str(raw_path),
                    sha256=sha256_of(text),
                    content=text,
                ).to_dict()
            )
        else:
            file_references.append(str(raw_path))

    return {
        "mission": mission,
        "inline_artifacts": inline_artifacts,
        "file_references": file_references,
    }


def check_admission(brief: dict[str, Any], backend_capabilities: dict[str, Any]) -> dict[str, Any]:
    """Gate a materialized brief against a backend's declared capabilities.

    Inspects fields the materializer itself populated (never an LLM's
    self-report). An `inline_only` backend cannot be admitted with a brief
    that still carries `file_references` — that would mean the worker is
    expected to read files it has no capability to read.

    Returns `{"status": "eligible", "reason": None}` or
    `{"status": "ineligible", "reason": "inline_only_file_reference"}`.
    """
    inline_only = _is_inline_only(backend_capabilities)
    file_references = brief.get("file_references") or []

    if inline_only and len(file_references) > 0:
        return {"status": "ineligible", "reason": "inline_only_file_reference"}

    return {"status": "eligible", "reason": None}
