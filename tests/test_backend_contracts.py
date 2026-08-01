#!/usr/bin/env python3
"""External CLI argv contracts must match the installed headless CLIs."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = (ROOT / "plugins" / "multi-agent-starter" / "skills" /
             "configure-multiagent" / "generator" / "templates")


def main() -> None:
    failures: list[str] = []
    for path in sorted(TEMPLATES.glob("*/_shared/backends.json")):
        flavor = path.parents[1].name
        workers = json.loads(path.read_text(encoding="utf-8"))["workers"]
        for role, rec in workers.items():
            if rec.get("call_type") != "cli":
                continue
            cli = rec["cli"]
            args = cli["args_template"]
            if cli["command"] == "claude":
                if "--prompt" in args or not ({"--print", "-p"} & set(args)):
                    failures.append(f"{flavor}/{role}: invalid Claude headless argv")
                if rec.get("model") == "host-default" and "--model" in args:
                    failures.append(f"{flavor}/{role}: host-default must not pin --model")
            if cli["command"] == "agy" and rec.get("model", "").startswith("gemini-"):
                try:
                    pinned = args[args.index("--model") + 1] == rec["model"]
                except (ValueError, IndexError):
                    pinned = False
                if not pinned:
                    failures.append(f"{flavor}/{role}: agy model is not pinned in argv")
        if flavor == "codex" and workers["claude-critic"].get("cwd_policy") != "isolated_tmp":
            failures.append("codex/claude-critic: cwd_policy must be isolated_tmp")
        if flavor == "codex":
            critic_args = workers["claude-critic"]["cli"]["args_template"]
            readonly = ("--disable-slash-commands" in critic_args and "--tools" in critic_args and
                        critic_args[critic_args.index("--tools") + 1] == "Read,Glob,Grep")
            if not readonly:
                failures.append("codex/claude-critic: read-only tool argv missing")
            isolated_target = ("--add-dir" in critic_args and
                               critic_args[critic_args.index("--add-dir") + 1] == "@target_repo")
            if not isolated_target:
                failures.append("codex/claude-critic: --add-dir @target_repo missing")

    for failure in failures:
        print(f"  FAIL {failure}")
    if failures:
        sys.exit(1)
    print("test_backend_contracts: all pass")


if __name__ == "__main__":
    main()
