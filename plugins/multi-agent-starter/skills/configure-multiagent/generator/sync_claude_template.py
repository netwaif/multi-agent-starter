#!/usr/bin/env python3
"""Claude flavor 템플릿 재생성 — 루트(정본)에서 templates/claude를 derive.

이 repo의 **루트가 Claude flavor 정본**이다(작성자 실제 운영 환경). 배포용
`generator/templates/claude/`는 릴리스 때 루트에서 재생성한다. 단순 복사가 아니라
두 가지 변환을 적용한다:

  1) 경로 일반화 — 루트는 작성자 경로(`~/VSCodeWorkspace/MultiAgent`)가 맞지만,
     남의 폴더에 설치될 템플릿엔 부적절하므로 플레이스홀더로 치환.
     (GitHub URL의 `netwaif`는 실제 배포 자원 링크라 유지.)
  2) .gitignore — 루트의 repo-infra 전용 줄(dist/ 등, sentinel로 표시)을 제거.

drift 가드: `transform(루트) == 커밋된 templates/claude` 인지 검사한다.
templates/codex는 이 repo에 정본 소스가 없으므로 건드리지 않는다(커밋본 유지).

사용:
    python3 sync_claude_template.py            # check(기본): drift 있으면 diff 출력 + exit 1
    python3 sync_claude_template.py --write     # 실제 재생성(템플릿 덮어씀)
"""
from __future__ import annotations

import argparse
import difflib
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent          # plugins/<name>/skills/configure-multiagent/generator/
REPO_ROOT = SCRIPT_DIR.parents[4]                      # 실제 git 루트 (시스템 파일 _shared/·_templates/·CLAUDE.md 위치)
TEMPLATE_DIR = SCRIPT_DIR / "templates" / "claude"

# 시스템 템플릿이 아닌 repo 인프라 — 재생성 소스에서 제외.
# NOTE: 플러그인은 이제 plugins/ 하위에, 마켓 카탈로그는 .claude-plugin/·.agents/ 에 있다.
# (dev 전용 도구 — 런타임/테스트 경로 아님. 새 레이아웃에서 전체 정합성은 별도 검토 필요.)
INFRA_PREFIXES = ("plugins/", ".claude-plugin/", ".agents/", "dist/", "tests/", "docs/")

# front-page/패키지 문서 — 루트는 repo 첫 화면(설치 안내)·배포 버전 이력이고,
# 설치된 타깃용 동명 문서는 templates/claude/ 에 독립 정본으로 둔다(서로 audience가
# 달라 의도적으로 분기). 따라서 이 파일들은 sync 대상에서 제외한다.
# design-basis·learnings 도 audience 분기(2026-07-24): 루트엔 유지보수자 전용 결정
# (D9 knot·D10 요금가드)·전체 운영 이력이 쌓이고, 설치본은 해당 결정 결번 + 축약 이력.
# 단 D 결정 번호는 루트가 할당하고 양쪽이 공유한다(설치본 범위 밖 결정은 결번).
DECOUPLED_FILES = (
    "README.md", "CHANGELOG.md", "KNOWN_ISSUES.md",
    "_shared/design-basis.md", "_shared/learnings.md",
)

# 경로 일반화: 작성자 로컬 경로 → 플레이스홀더. (URL 안 netwaif 는 건드리지 않음)
# 더 긴/구체 경로를 먼저 둔다(접두어 충돌 방지). 현재 둘은 서로 접두어 관계가 아니라
# 순서 무관하지만, 새 규칙 추가 시 안전하도록 관례를 지킨다.
PATH_REPLACEMENTS = [
    ("~/VSCodeWorkspace/multi-agent-manual", "<매뉴얼-경로>"),
    ("~/VSCodeWorkspace/MultiAgent", "<설치한-폴더>"),
]

# .gitignore 에서 이 마커부터 끝까지 = repo-infra 전용 → 템플릿에서 제거.
GITIGNORE_INFRA_MARKER = "# >>> repo-infra-only"


def git_tracked(root: Path) -> list[str]:
    out = subprocess.run(
        ["git", "-C", str(root), "ls-files"],
        capture_output=True, text=True, check=True,
    ).stdout
    return [line for line in out.splitlines() if line]


def system_files() -> list[str]:
    """루트 tracked 파일 중 Claude 시스템 템플릿에 속하는 것만."""
    return sorted(
        f for f in git_tracked(REPO_ROOT)
        if not f.startswith(INFRA_PREFIXES) and f not in DECOUPLED_FILES
    )


def transform(rel: str, raw: bytes) -> bytes:
    """루트 파일 1개 → 템플릿용 바이트로 변환."""
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw  # 바이너리(현재 없음)면 그대로
    if rel == ".gitignore" and GITIGNORE_INFRA_MARKER in text:
        text = text[: text.index(GITIGNORE_INFRA_MARKER)].rstrip("\n") + "\n"
    for src, dst in PATH_REPLACEMENTS:
        text = text.replace(src, dst)
    return text.encode("utf-8")


def build_expected() -> dict[str, bytes]:
    """재생성됐을 때 templates/claude 가 가져야 할 (rel -> bytes)."""
    expected: dict[str, bytes] = {}
    for rel in system_files():
        raw = (REPO_ROOT / rel).read_bytes()
        expected[rel] = transform(rel, raw)
    return expected


def current_template() -> dict[str, bytes]:
    rels = [
        rel for p in TEMPLATE_DIR.rglob("*") if p.is_file()
        for rel in [str(p.relative_to(TEMPLATE_DIR).as_posix())]
        if rel not in DECOUPLED_FILES  # 분리된 문서는 sync 범위 밖(비교·삭제 안 함)
    ]
    return {rel: (TEMPLATE_DIR / rel).read_bytes() for rel in sorted(rels)}


def diff_report(expected: dict[str, bytes], current: dict[str, bytes]) -> list[str]:
    """변경될 내용을 사람이 읽을 unified diff 목록으로."""
    lines: list[str] = []
    for rel in sorted(set(expected) | set(current)):
        exp = expected.get(rel)
        cur = current.get(rel)
        if exp == cur:
            continue
        if cur is None:
            lines.append(f"  + 추가: {rel}")
            continue
        if exp is None:
            lines.append(f"  - 삭제: {rel} (루트에 더 이상 없음)")
            continue
        cur_t = cur.decode("utf-8", "replace").splitlines(keepends=True)
        exp_t = exp.decode("utf-8", "replace").splitlines(keepends=True)
        ud = difflib.unified_diff(
            cur_t, exp_t,
            fromfile=f"committed/{rel}", tofile=f"regenerated/{rel}",
        )
        lines.append("".join(ud).rstrip("\n"))
    return lines


def write_template(expected: dict[str, bytes], current: dict[str, bytes]) -> None:
    # 1) 갱신/추가
    for rel, data in expected.items():
        dest = TEMPLATE_DIR / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    # 2) 루트에서 사라진 파일은 템플릿에서도 제거(진짜 재생성)
    for rel in current:
        if rel not in expected:
            (TEMPLATE_DIR / rel).unlink()


def main() -> None:
    ap = argparse.ArgumentParser(description="Claude flavor 템플릿 재생성(루트 정본 derive)")
    ap.add_argument("--write", action="store_true", help="실제로 템플릿을 덮어씀(기본: check만)")
    args = ap.parse_args()

    if not TEMPLATE_DIR.is_dir():
        sys.exit(f"[error] 템플릿 폴더 없음: {TEMPLATE_DIR}")

    expected = build_expected()
    current = current_template()

    if args.write:
        write_template(expected, current)
        print(f"  재생성 완료: {len(expected)}개 파일 → {TEMPLATE_DIR.relative_to(REPO_ROOT)}")
        print("  (확인: 다시 check 모드로 drift 0 인지 검증하세요)")
        return

    # check 모드
    report = diff_report(expected, current)
    if not report:
        print(f"  drift 없음 — templates/claude 가 루트 정본과 일치 ({len(expected)}개 파일).")
        return
    print("  DRIFT 감지 — 재생성 시 다음이 바뀝니다:\n")
    print("\n\n".join(report))
    print(f"\n  → 반영하려면: python3 {Path(__file__).name} --write")
    sys.exit(1)


if __name__ == "__main__":
    main()
