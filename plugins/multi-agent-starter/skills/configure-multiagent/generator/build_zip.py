#!/usr/bin/env python3
"""ZIP fallback 빌더 — 플러그인 설치 없이 쓰는 자립형 패키지.

최소 기술 사용자를 위한 front door. 플러그인/마켓플레이스 없이 ZIP만 내려받아
압축을 풀고 `python3 init.py` 한 줄(또는 run.command/run.bat 더블클릭)이면
멀티에이전트 시스템을 만들 수 있게 한다.

ZIP 내부는 generator/ 내용을 루트로 평탄화한다 (init.py가 SCRIPT_DIR 기준으로
templates/·validate.py를 찾으므로 한 폴더에 모이면 그대로 동작):

    multi-agent-starter-<version>/
    ├── README.txt        # 한글 quickstart
    ├── init.py           # generator/init.py 사본
    ├── validate.py       # generator/validate.py 사본
    ├── templates/        # claude · codex · antigravity · hermes 네 flavor
    ├── run.command       # macOS 더블클릭용
    └── run.bat           # Windows 더블클릭용

결정적: 엔트리를 정렬하고 mtime을 고정해 같은 입력 → 같은 바이트(재현 가능).

사용:
    python3 build_zip.py                 # dist/ 에 빌드 + 자가검증
    python3 build_zip.py --out dist      # 출력 폴더 지정
    python3 build_zip.py --no-self-test  # 추출·설치 검증 건너뜀
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent          # skills/configure-multiagent/generator/
REPO_ROOT = SCRIPT_DIR.parents[2]                      # plugin root (plugins/multi-agent-starter/)
TEMPLATES_DIR = SCRIPT_DIR / "templates"
PLUGIN_JSON = REPO_ROOT / ".claude-plugin" / "plugin.json"

# 재현 가능한 zip: 모든 엔트리 mtime을 이 값으로 고정 (zip 최소 연도 1980).
FIXED_DATE = (1980, 1, 1, 0, 0, 0)

README_TXT = """\
MultiAgent 시스템 생성기 — 오프라인 ZIP 버전 (v{version})
=========================================================

플러그인 설치 없이, 이 ZIP만으로 파일 기반 멀티에이전트 오케스트레이션
시스템을 원하는 폴더에 만들어 줍니다.

[필요한 것]
- Python 3.8 이상. 터미널에서 다음으로 확인:  python3 --version
  · macOS: 대개 기본 설치됨. 없으면 https://www.python.org 에서 설치.
  · Windows: https://www.python.org 설치 시 "Add Python to PATH" 체크.

[가장 쉬운 방법 — 더블클릭]
- macOS:   run.command  더블클릭
           (처음엔 "확인되지 않은 개발자" 경고가 날 수 있음 →
            우클릭 → 열기, 또는 시스템 설정 > 개인정보 보호 및 보안에서 허용)
- Windows: run.bat       더블클릭
           (SmartScreen 경고 시 "추가 정보" → "실행")
메뉴가 뜨면 flavor와 설치 폴더를 고르면 됩니다.

[터미널에서 직접]
이 폴더 안에서:
    python3 init.py
비대화형으로 한 번에:
    python3 init.py --flavor claude --target "/설치할/폴더" --yes

[flavor 란?]
- claude : Claude Code가 오케스트레이터
           (워커: claude-main / codex-main / codex-critic / gemini)
- codex  : Codex가 오케스트레이터
           (워커: codex-main / claude-critic / gemini)
- antigravity : Antigravity가 오케스트레이터
                (워커: claude-main / codex-main / codex-critic)
- hermes : Hermes가 오케스트레이터
           (워커: codex-main / claude-critic / gemini)

[안전]
- 설치 폴더에 이미 tasks/ 또는 _local/ 작업 데이터가 있으면 지우지 않고
  보존합니다(update 모드 = 시스템 파일만 갱신).
- 설치가 끝나면 자동으로 자가점검(validate)을 돌려 PASS/FAIL을 보여줍니다.
  FAIL이 있으면 생성 결과가 불완전한 것이니 다시 시도하세요.

생성 후: 만들어진 폴더로 이동해 해당 도구(claude, codex, agy 또는 hermes)를 실행하세요.
"""

RUN_COMMAND = """\
#!/bin/bash
# macOS 더블클릭용 — 이 스크립트 위치에서 생성기를 대화형으로 실행
cd "$(dirname "$0")" || exit 1
python3 init.py
echo
echo "끝났습니다. 이 창은 닫아도 됩니다."
"""

RUN_BAT = """\
@echo off
REM Windows 더블클릭용 — 이 스크립트 위치에서 생성기를 대화형으로 실행
cd /d "%~dp0"
python3 init.py
echo.
echo 끝났습니다. 아무 키나 누르면 닫힙니다.
pause >nul
"""


def read_version() -> str:
    data = json.loads(PLUGIN_JSON.read_text(encoding="utf-8"))
    return data["version"]


def collect_payload() -> list[tuple[str, bytes, bool]]:
    """ZIP에 담을 (arcname, bytes, is_executable) 목록을 정렬해 반환."""
    root = "multi-agent-starter"  # 버전은 호출부에서 접두어로 붙임
    items: list[tuple[str, bytes, bool]] = []

    # 1) 평탄화 대상: generator/init.py, generator/validate.py
    items.append(("init.py", (SCRIPT_DIR / "init.py").read_bytes(), False))
    items.append(("validate.py", (SCRIPT_DIR / "validate.py").read_bytes(), False))

    # 2) templates/ 전체 (build_zip.py 자신·캐시는 포함 안 됨 — templates 밖이라)
    for src in sorted(TEMPLATES_DIR.rglob("*")):
        if src.is_dir() or src.name == ".DS_Store" or "__pycache__" in src.parts:
            continue
        rel = src.relative_to(TEMPLATES_DIR)
        items.append((f"templates/{rel.as_posix()}", src.read_bytes(), False))

    # 3) 동봉 보조 파일
    items.append(("README.txt", README_TXT.format(version=read_version()).encode(), False))
    items.append(("run.command", RUN_COMMAND.encode(), True))
    items.append(("run.bat", RUN_BAT.encode(), False))

    items.sort(key=lambda t: t[0])
    return [(f"{root}/{name}", data, ex) for name, data, ex in items]


def build(out_dir: Path, version: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = out_dir / f"multi-agent-starter-{version}.zip"
    payload = collect_payload()

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for arcname, data, is_exec in payload:
            info = zipfile.ZipInfo(arcname, date_time=FIXED_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            # 실행권한(755) vs 일반(644)을 external_attr 상위 16비트에 기록
            info.external_attr = (0o755 if is_exec else 0o644) << 16
            zf.writestr(info, data)
    return zip_path


def self_test(zip_path: Path) -> None:
    """ZIP을 임시 폴더에 풀고 네 flavor를 실제 설치해 validate까지 통과하는지 확인."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(tmp_path)
        pkg = next(tmp_path.glob("multi-agent-starter-*")) if list(
            tmp_path.glob("multi-agent-starter-*")
        ) else tmp_path / "multi-agent-starter"
        init_py = pkg / "init.py"
        if not init_py.is_file():
            sys.exit(f"[self-test FAIL] ZIP 안에 init.py 없음: {init_py}")

        for flavor in ("claude", "codex", "antigravity", "hermes"):
            target = tmp_path / f"out-{flavor}"
            rc = subprocess.run(
                [sys.executable, str(init_py), "--flavor", flavor,
                 "--target", str(target), "--yes"],
                capture_output=True, text=True,
            )
            tail = (rc.stdout + rc.stderr).strip().splitlines()[-3:]
            if rc.returncode != 0:
                print("\n".join(tail))
                sys.exit(f"[self-test FAIL] flavor={flavor} 설치/validate 실패 (exit {rc.returncode})")
            print(f"   [self-test PASS] flavor={flavor} → 설치 + validate OK")


def main() -> None:
    ap = argparse.ArgumentParser(description="MultiAgent ZIP fallback 빌더")
    ap.add_argument("--out", default=str(REPO_ROOT / "dist"), help="출력 폴더 (기본 dist/)")
    ap.add_argument("--no-self-test", action="store_true", help="추출·설치 자가검증 건너뜀")
    args = ap.parse_args()

    if not (SCRIPT_DIR / "init.py").is_file() or not TEMPLATES_DIR.is_dir():
        sys.exit("[error] generator/init.py 또는 templates/ 를 찾을 수 없습니다.")

    version = read_version()
    out_dir = Path(args.out).expanduser().resolve()
    zip_path = build(out_dir, version)
    size_kb = zip_path.stat().st_size / 1024
    print(f"  빌드 완료: {zip_path}  ({size_kb:.1f} KB)")

    if not args.no_self_test:
        print("  자가검증(추출 → 네 flavor 설치 → validate)...")
        self_test(zip_path)
        print("  자가검증 통과.")


if __name__ == "__main__":
    main()
