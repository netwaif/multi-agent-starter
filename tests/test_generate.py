#!/usr/bin/env python3
"""L1/A2: 각 flavor를 임시폴더에 생성 → validate가 전부 PASS인지.

외부 호출 없음, 결정적. validate 체크 *개수*는 하드코딩하지 않는다
(F4 등으로 체크가 늘어도 안 깨지도록 — "전부 PASS"와 exit 0만 단언).

knot·요금가드 설치는 v3.0.0부터 loadout 담당 — 주입 테스트는 제거했고,
기본 생성물에 그 잔재(관리블록·가드 배선)가 없다는 부재 단언만 남긴다.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GEN = REPO / "plugins" / "multi-agent-starter" / "skills" / "configure-multiagent" / "generator"
FLAVORS = sorted(p.name for p in (GEN / "templates").iterdir() if p.is_dir())
INSTRUCTION_FILE = {
    "claude": "CLAUDE.md",
    "codex": "AGENTS.md",
    "antigravity": "AGENTS.md",
    "hermes": "AGENTS.md",
}
KNOT_START, KNOT_END = "<!-- knot:start -->", "<!-- knot:end -->"


def run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True)


def init(tgt: Path, f: str) -> subprocess.CompletedProcess:
    return run([sys.executable, str(GEN / "init.py"),
                "--flavor", f, "--target", str(tgt), "--yes", "--no-validate"])


def _guard_artifact(tgt: Path, f: str) -> Path:
    """flavor별 가드 배선 산출물 경로(부재 단언용). antigravity는 산출물 없음(None)."""
    return {"claude": tgt / ".claude" / "settings.json",
            "codex": tgt / "_shared" / "guard" / "codex_goal_watch.mjs",
            "hermes": tgt / "_shared" / "guard" / "codex_goal_watch.mjs"}.get(f)


def validate_all_pass() -> int:
    fails = 0
    for f in FLAVORS:
        with tempfile.TemporaryDirectory() as d:
            tgt = Path(d) / f"sys-{f}"
            if init(tgt, f).returncode != 0:
                print(f"  FAIL [{f}] init exit nonzero"); fails += 1; continue
            shell_files = list(tgt.rglob("*.sh")) + list(tgt.rglob("*.command"))
            bad_eol = [p.relative_to(tgt) for p in shell_files if b"\r\n" in p.read_bytes()]
            lf_ok = not bad_eol
            print(f"  {'PASS' if lf_ok else 'FAIL'} [{f}] generated shell scripts LF")
            if not lf_ok:
                print(f"    CRLF files: {', '.join(map(str, bad_eol))}")
                fails += 1
            attrs = (tgt / ".gitattributes").read_text(encoding="utf-8")
            ignore = (tgt / ".gitignore").read_text(encoding="utf-8")
            metadata_ok = "*.sh text eol=lf" in attrs and "*.multiagent-bak" in ignore
            print(f"  {'PASS' if metadata_ok else 'FAIL'} [{f}] LF·backup metadata")
            fails += not metadata_ok
            v = run([sys.executable, str(GEN / "validate.py"),
                     "--flavor", f, "--target", str(tgt)])
            ok = v.returncode == 0 and "전부 PASS" in v.stdout
            print(f"  {'PASS' if ok else 'FAIL'} [{f}] validate exit {v.returncode}")
            if not ok:
                print(v.stdout); fails += 1
    return fails


def slim_checks() -> int:
    """기본 생성물에 knot 관리블록·가드 배선 잔재가 없는지 (v3 슬림화 회귀 방지)."""
    fails = 0
    for f in FLAVORS:
        with tempfile.TemporaryDirectory() as d:
            tgt = Path(d) / f"plain-{f}"
            init(tgt, f)
            txt = (tgt / INSTRUCTION_FILE[f]).read_text(encoding="utf-8")
            no_knot = KNOT_START not in txt and KNOT_END not in txt
            print(f"  {'PASS' if no_knot else 'FAIL'} [{f}] 기본 init 관리블록 부재")
            fails += not no_knot
            art = _guard_artifact(tgt, f)
            no_guard = art is None or not art.is_file()
            print(f"  {'PASS' if no_guard else 'FAIL'} [{f}] 기본 init 가드 산출물 부재")
            fails += not no_guard
    return fails


def main() -> None:
    fails = validate_all_pass() + slim_checks()
    print(f"test_generate: {'all pass' if not fails else f'{fails} fail'}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
