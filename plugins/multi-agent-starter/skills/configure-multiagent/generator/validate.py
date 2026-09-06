#!/usr/bin/env python3
"""생성된 MultiAgent 시스템 자가점검 — flavor별 불변식 검사.

init.py가 설치 후 호출하거나 단독 실행 가능:
    python3 validate.py --flavor codex --target /path/to/system

각 flavor의 system-invariants.md 의도를 구조 검사로 옮긴 것.
PASS/FAIL을 출력하고, 하나라도 FAIL이면 비정상 종료(exit 1).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent  # generator/

# flavor별 차이 = 데이터로. (검사 로직은 공유)
FLAVOR = {
    "claude": {
        "instruction": "CLAUDE.md",
        "main_worker": "claude-main",          # routing에 있어야
        "forbidden_worker": None,
        "extra_files": [".claude/agents/claude-main.md", ".mcp.json"],
    },
    "codex": {
        "instruction": "AGENTS.md",
        "main_worker": "claude-critic",         # 리뷰 워커(독립성)
        "forbidden_worker": "codex-critic",     # 자기검수 구조 = 비활성이어야
        "extra_files": [],
    },
    "antigravity": {
        "instruction": "AGENTS.md",            # agy가 자동 로드(spike S1 확인)
        "main_worker": "claude-main",          # strategist 워커(교차 벤더) — routing에 있어야
        "forbidden_worker": "gemini-critic",   # gemini 오케스트레이터 자기검수 금지
        "extra_files": [],
    },
}

TOPOLOGY = ("Pipeline", "Fan-out/Fan-in", "Expert Pool", "Producer-Reviewer")
SLOTS = ("strategist", "engineer", "computer-use", "reviewer", "multimodal")
LOG_TAGS = "DECISION | WORKER_CALL | VERIFICATION | ERROR | APPROVAL | COMPLETE"

# knot 자동층(v3.0.0부터 loadout 카탈로그가 주입). 미설치(마커 부재)는 정상 PASS.
KNOT_BLOCK = SCRIPT_DIR / "knot_block.md"
KNOT_START, KNOT_END = "<!-- knot:start -->", "<!-- knot:end -->"
# knot 능동 스킬은 v3.1.0부터 knot 자체 플러그인(github.com/netwaif/knot)이 배포 — 이 저장소·생성물
# 검증 대상 아님. C10(관리블록 정본)만 사후 검사한다.


# goal 요금가드: v3.2.0부터 배선 자산·사후검증(구 C12) 전부 loadout guard 품목 소관
# (설치=loadout store.py, 검증=loadout doctor 정본 대조). 이 저장소는 가드 파일을 갖지 않는다.


def _knot_check(instr_txt: str) -> tuple[bool, str]:
    """C10: knot 마커가 있으면 (a)짝 맞고 (b)본문이 knot_block.md와 일치하고
    (c)중복 마커 없음. 마커가 없으면 PASS(미설치 정상)."""
    starts, ends = instr_txt.count(KNOT_START), instr_txt.count(KNOT_END)
    if starts == 0 and ends == 0:
        return True, "knot 마커 없음(미설치 — 정상)"
    if starts != 1 or ends != 1:
        return False, f"knot 마커 짝/중복 오류(start={starts}, end={ends})"
    m = re.search(re.escape(KNOT_START) + r".*?" + re.escape(KNOT_END), instr_txt, re.S)
    if not m:
        return False, "knot 마커 순서 오류(start가 end보다 뒤)"
    if not KNOT_BLOCK.is_file():
        return False, "knot_block.md 없음(정본 부재)"
    canonical = KNOT_BLOCK.read_text(encoding="utf-8").strip("\n")
    if m.group(0).strip("\n") != canonical:
        return False, "knot 블록 본문이 knot_block.md와 불일치"
    return True, "knot 블록 정본 일치"


def read(target: Path, rel: str) -> str | None:
    p = target / rel
    return p.read_text(encoding="utf-8") if p.is_file() else None


def run_checks(target: Path, flavor: str) -> list[tuple[bool, str]]:
    cfg = FLAVOR[flavor]
    results: list[tuple[bool, str]] = []

    def check(ok: bool, msg: str) -> None:
        results.append((bool(ok), msg))

    instr = cfg["instruction"]

    # C1 필수 파일 존재
    required = [
        instr, ".gitignore", "tasks/.gitkeep",
        "_shared/routing.md", "_shared/capability-profile.md",
        "_shared/orchestrator-rules.md",
        "_shared/design-basis.md", "_shared/system-invariants.md",
        "_shared/check-invariants.sh",
        "_templates/log.md", "_templates/context.md", "_templates/worker-brief.md",
    ] + cfg["extra_files"]
    missing = [r for r in required if not (target / r).is_file()]
    check(not missing, f"C1 필수 파일 존재 (없음: {missing or '-'})")

    routing = read(target, "_shared/routing.md") or ""
    orch = read(target, "_shared/orchestrator-rules.md") or ""
    instr_txt = read(target, instr) or ""
    log_tpl = read(target, "_templates/log.md") or ""
    brief_tpl = read(target, "_templates/worker-brief.md") or ""

    # C2 log 태그 6종
    check(LOG_TAGS in log_tpl, "C2 log 태그 6종 (_templates/log.md)")

    # C3 컨텍스트/brief 한도 수치
    ctx = read(target, "_templates/context.md") or ""
    check(("1500" in ctx) and ("1200" in brief_tpl), "C3 한도 수치 1500/1200")

    # C4 재진입 프로토콜 (orchestrator-rules + 지침파일 양쪽)
    reentry = ("재진입 프로토콜" in orch) and (("재진입" in instr_txt) or ("re-entry" in instr_txt.lower()))
    check(reentry, "C4 재진입 프로토콜 (orchestrator-rules + 지침파일)")

    # C5 토폴로지 4패턴
    miss_topo = [t for t in TOPOLOGY if t not in routing]
    check(not miss_topo, f"C5 토폴로지 4패턴 (없음: {miss_topo or '-'})")

    # C5b 2층 라우팅 — routing(안정층) 트리가 각 슬롯을 분기 태그([slot], [a·b] 허용)로 갖고,
    # capability-profile(가변층)의 「현재 배정」 표가 슬롯당 정확히 1행. substring 우연 일치로는
    # PASS 못 하게 구조 검사. (담당명 대응까지는 비교하지 않음 — 배정 서술은 자유 산문이라
    # 기계 대조가 과제약. 병기 동기화는 프로필 갱신 절차가 소관)
    profile = read(target, "_shared/capability-profile.md") or ""
    tree_tokens: set[str] = set()
    for m in re.finditer(r"\[([^\]\n]+)\]", routing):
        tree_tokens.update(t.strip() for t in m.group(1).split("·"))
    miss_tree = [s for s in SLOTS if s not in tree_tokens]
    row_counts = {s: len(re.findall(rf"^\|\s*{re.escape(s)}\s*\|", profile, re.M)) for s in SLOTS}
    bad_rows = [f"{s}×{n}" for s, n in row_counts.items() if n != 1]
    link_ok = "capability-profile" in routing
    check(link_ok and not miss_tree and not bad_rows,
          f"C5b 2층 라우팅 (routing→profile 참조: {'OK' if link_ok else '없음'}, "
          f"트리 슬롯 태그 누락: {miss_tree or '-'}, 프로필 배정행 이상: {bad_rows or '-'})")

    # C6 gemini 정책. claude/codex: gemini 워커가 cli/agy + pro-high. antigravity: 오케스트레이터가
    # agy(Gemini Pro High)이므로 별도 gemini 워커 없음 — 지침이 agy/pro-high 오케스트레이터를 명시하는지.
    if flavor == "antigravity":
        c6_ok = ("Gemini 3.1 Pro High" in instr_txt) and (("agy" in instr_txt) or ("Antigravity" in instr_txt))
        c6_why = "AGENTS.md가 agy/Gemini 3.1 Pro High 오케스트레이터 명시해야"
    else:
        c6_ok, c6_why = _gemini_policy_ok(read(target, "_shared/backends.json"))
    check(c6_ok, f"C6 gemini 정책 {('— ' + c6_why) if not c6_ok else '(OK)'}")

    # C6b antigravity 전용: 워커셋이 정확히 {claude-main,codex-main,codex-critic}이고
    # gemini 워커 호출 잔재 없음. subset 검사는 워커 누락(예: codex-critic 빠짐)을 통과시키므로
    # 정확집합으로 조인다. (schema 1 'workers' 맵 기준 — 스키마 전환 아님)
    if flavor == "antigravity":
        try:
            ws = set((json.loads(read(target, "_shared/backends.json") or "{}").get("workers") or {}).keys())
        except Exception:  # noqa: BLE001
            ws = set()
        tf = read(target, "_templates/task-folder.md") or ""
        no_gem = all("call_worker.sh gemini" not in t for t in (routing, tf, instr_txt))
        set_ok = ws == {"claude-main", "codex-main", "codex-critic"}
        check(no_gem and set_ok,
              f"C6b 워커셋 {sorted(ws)} == 정확집합 {{claude-main,codex-main,codex-critic}} + gemini 워커 호출 잔재 없음")

    # C7 write_scope 값 일관 (tasks-only 가 지침/routing/brief에 존재)
    ws = all("tasks-only" in t for t in (instr_txt, routing, brief_tpl))
    check(ws, "C7 write_scope tasks-only 분포 (지침/routing/brief)")

    # C8 flavor 워커풀 일관성
    check(cfg["main_worker"] in routing, f"C8 주 워커 '{cfg['main_worker']}' routing에 존재")
    if cfg["forbidden_worker"]:
        active = (cfg["forbidden_worker"] in routing) or (cfg["forbidden_worker"] in instr_txt)
        check(not active, f"C8b 금지 워커 '{cfg['forbidden_worker']}' 활성 참조 없음")

    # C9 backends.json 어댑터 레지스트리 스키마 (구조 + api.ref 파일 존재)
    raw = read(target, "_shared/backends.json")
    problems = _backends_problems(raw, flavor, target) if raw is not None else ["_shared/backends.json 없음"]
    check(not problems, f"C9 backends.json 스키마 (문제: {problems[0] if problems else '-'})")
    check((target / "_shared/adapters/call_worker.sh").is_file(),
          "C9b 디스패처 _shared/adapters/call_worker.sh 존재")
    # C9c 집행층 스크립트 (gate·scope_check·reentry-check) 존재 + 디스패처 배선
    enf = ["_shared/adapters/gate.sh", "_shared/adapters/scope_check.sh", "_shared/reentry-check.sh"]
    enf_missing = [e for e in enf if not (target / e).is_file()]
    cw = read(target, "_shared/adapters/call_worker.sh") or ""
    cw_code = "\n".join(l for l in cw.splitlines() if not l.lstrip().startswith("#"))
    check(not enf_missing and 'bash "$SCRIPT_DIR/gate.sh"' in cw_code and 'bash "$SCRIPT_DIR/scope_check.sh"' in cw_code,
          f"C9c 집행층 스크립트·배선 (없음: {enf_missing or '-'})")

    # C10 knot 자동층(선택). 마커 부재 = 미설치 정상 PASS, 존재 시 짝·정본·중복 검사.
    k_ok, k_why = _knot_check(instr_txt)
    check(k_ok, f"C10 knot 관리블록 — {k_why}")

    # (구 C12 요금가드 배선 검증은 v3.2.0부터 loadout doctor 소관 — 정본 이관)

    return results


_CALL_TYPES = {"native", "mcp", "cli", "api"}
_APPROVAL = {"worker", "orchestrator"}
_CAPTURE = {"orchestrator", "tool-return", "stdout", "envelope"}
_BRIEF_MODES = {"path", "content", "stdin", "file-arg"}
_CLI_ALLOWLIST = {"agy", "codex", "claude"}


def _backend_record_problems(rec: dict, where: str, target: Path, *, is_fallback: bool) -> list[str]:
    p: list[str] = []
    ct = rec.get("call_type")
    if ct not in _CALL_TYPES:
        return [f"{where}: call_type 무효({ct})"]
    if "model" not in rec:
        p.append(f"{where}: model 누락")
    if rec.get("approval_class") not in _APPROVAL:
        p.append(f"{where}: approval_class 무효")
    if rec.get("result_capture") not in _CAPTURE:
        p.append(f"{where}: result_capture 무효")
    if ct in ("cli", "api"):
        tmo = rec.get("timeout")
        if not isinstance(tmo, int) or tmo <= 0:
            p.append(f"{where}: timeout 양의정수 필수")
    if ct == "cli" and rec.get("brief_mode") not in _BRIEF_MODES:
        p.append(f"{where}: brief_mode 무효/누락(cli)")
    if ct == "native" and "native" not in rec:
        p.append(f"{where}: native 블록 누락")
    if ct == "mcp":
        if not rec.get("mcp", {}).get("tool"):
            p.append(f"{where}: mcp.tool 누락")
    if ct == "cli":
        cli = rec.get("cli", {})
        if cli.get("command") not in _CLI_ALLOWLIST:
            p.append(f"{where}: cli.command allowlist 위반({cli.get('command')})")
        if not isinstance(cli.get("args_template"), list):
            p.append(f"{where}: cli.args_template 배열 필수")
    if ct == "api":
        api = rec.get("api", {})
        ref = api.get("ref", "")
        if not ref.startswith("adapters/") or ".." in ref:
            p.append(f"{where}: api.ref는 adapters/ 내부·'..' 금지")
        elif not (target / "_shared" / ref).is_file():
            p.append(f"{where}: api.ref 파일 없음(_shared/{ref})")
        if api.get("brief_pass") not in {"arg1", "stdin", "env"}:
            p.append(f"{where}: api.brief_pass 무효/누락(arg1|stdin|env)")
    if not is_fallback:
        for i, fb in enumerate(rec.get("fallbacks", []) or []):
            p += _backend_record_problems(fb, f"{where}.fallback[{i}]", target, is_fallback=True)
    return p


def _gemini_policy_ok(raw: str | None) -> tuple[bool, str]:
    """C6: gemini 워커가 cli/agy + gemini-3.1-pro-high 인지 레코드 직접 검사."""
    if raw is None:
        return False, "backends.json 없음"
    try:
        g = (json.loads(raw).get("workers") or {}).get("gemini")
    except Exception as e:  # noqa: BLE001
        return False, f"파싱 실패: {e}"
    if not isinstance(g, dict):
        return False, "gemini 워커 없음"
    if g.get("call_type") != "cli" or g.get("cli", {}).get("command") != "agy":
        return False, "gemini call_type cli·command agy 아님"
    if g.get("model") != "gemini-3.1-pro-high":
        return False, f"gemini model이 pro-high 아님({g.get('model')})"
    return True, ""


def _backends_problems(raw: str, flavor: str, target: Path) -> list[str]:
    try:
        data = json.loads(raw)
    except Exception as e:  # noqa: BLE001
        return [f"JSON 파싱 실패: {e}"]
    if "mcp__gemini__gemini_" in raw:
        return ["폐기 도구 호출형 mcp__gemini__gemini_* 잔존"]
    p: list[str] = []
    if not data.get("schema_version"):
        p.append("schema_version 누락")
    if data.get("flavor") != flavor:
        p.append(f"flavor 불일치(파일={data.get('flavor')}, 기대={flavor})")
    workers = data.get("workers")
    if not isinstance(workers, dict) or not workers:
        return p + ["workers 비어있음"]
    for role, rec in workers.items():
        if not isinstance(rec, dict):
            p.append(f"{role}: 레코드 형식 오류"); continue
        p += _backend_record_problems(rec, role, target, is_fallback=False)
    return p


# 분리 레이아웃(#17066 대응): 플러그인 본체는 plugins/<name>/ 하위, 마켓 카탈로그는
# git 루트(.claude-plugin/marketplace.json + .agents/plugins/marketplace.json)에 있다.
PLUGIN_ROOT = SCRIPT_DIR.parents[2]   # generator → configure-multiagent → skills → 플러그인 루트
CATALOG_ROOT = SCRIPT_DIR.parents[4]  # git 루트 (카탈로그·front-page)


def _desc_text(rel: str, data: dict) -> str:
    """매니페스트의 사람용 서술 필드만 추출(name/url/keywords 제외 — flavor 광고 검사용.
    raw JSON 전체를 쓰면 URL·키워드의 우연한 substring으로 거짓 PASS 가능)."""
    parts: list[str] = []
    if data.get("description"):
        parts.append(str(data["description"]))
    iface = data.get("interface") or {}
    for k in ("shortDescription", "longDescription"):
        if iface.get(k):
            parts.append(str(iface[k]))
    for pl in data.get("plugins", []) or []:  # marketplace 항목
        if isinstance(pl, dict) and pl.get("description"):
            parts.append(str(pl["description"]))
    return " ".join(parts)


def _versions_with_holes(rel: str, data: dict) -> list:
    """매니페스트가 가진 version 목록(누락은 None으로 보존 — '존재'까지 검사)."""
    if rel.endswith("marketplace.json"):
        plugins = data.get("plugins") or []
        return [pl.get("version") if isinstance(pl, dict) else None for pl in plugins] or [None]
    return [data.get("version")]


def run_repo_checks(catalog: Path, plugin: Path) -> list[tuple[str, str]]:
    """플러그인 repo 자체(배포 표면) 점검 — 생성 타깃이 아니라 매니페스트·레이아웃.

    분리 레이아웃: 카탈로그(marketplace.json 2종)는 git 루트(catalog), 플러그인
    매니페스트(plugin.json 2종)·skills/ 는 plugins/<name>/(plugin) 하위.
    PASS/FAIL/WARN 3-state. 루트 plugin.json(Antigravity 호스트)은 로딩 경로
    미확정이라 부재 시 WARN(KNOWN_ISSUES KI-2). 머지 전 실설치로 검증."""
    out: list[tuple[str, str]] = []

    def emit(status: str, msg: str) -> None:
        out.append((status, msg))

    # 동봉 매니페스트(보장 호스트): Claude Code marketplace(루트 카탈로그)+plugin, Codex plugin.
    # 라벨은 git 루트 기준 상대경로 — 아래에서 catalog / rel 로 읽는다.
    mkt_rel = ".claude-plugin/marketplace.json"
    plugin_rels = [str((plugin / d / "plugin.json").relative_to(catalog))
                   for d in (".claude-plugin", ".codex-plugin")]
    manifests = [mkt_rel] + plugin_rels
    loaded: dict[str, dict] = {}
    bad: list[str] = []
    for rel in manifests:
        p = catalog / rel
        if not p.is_file():
            bad.append(f"{rel} 없음"); continue
        try:
            loaded[rel] = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            bad.append(f"{rel} JSON 파싱 실패({e})")
    # R1 구조까지: marketplace plugins[] 비어있지 않고 각 항목 name·source·version
    # (로컬 "./" source는 실제 폴더 존재까지), plugin.json은 name·version
    mkt = loaded.get(mkt_rel, {})
    mkt_plugins = mkt.get("plugins") or []
    if mkt_rel in loaded:
        if not mkt_plugins:
            bad.append("marketplace.plugins 비어있음")
        for i, pl in enumerate(mkt_plugins):
            miss = [k for k in ("name", "source", "version") if not (isinstance(pl, dict) and pl.get(k))]
            if miss:
                bad.append(f"marketplace.plugins[{i}] 필드 누락{miss}")
            src = pl.get("source") if isinstance(pl, dict) else None
            if isinstance(src, str) and src.startswith("./") and not (catalog / src).is_dir():
                bad.append(f"marketplace.plugins[{i}] source 폴더 없음({src})")
    for rel in plugin_rels:
        d = loaded.get(rel)
        if d is not None:
            miss = [k for k in ("name", "version") if not d.get(k)]
            if miss:
                bad.append(f"{rel} 필드 누락{miss}")
    emit("PASS" if not bad else "FAIL", f"R1 매니페스트 3종 valid+구조 ({bad[0] if bad else '-'})")

    # R1b Codex 카탈로그(.agents/plugins/marketplace.json) — Codex 호스트가 소비.
    # 스키마에 version 필드가 없어 R2(version 일관) 대상에서는 제외한다.
    ab: list[str] = []
    agents_cat = catalog / ".agents/plugins/marketplace.json"
    if not agents_cat.is_file():
        ab.append(".agents/plugins/marketplace.json 없음")
    else:
        try:
            apl = json.loads(agents_cat.read_text(encoding="utf-8")).get("plugins") or []
            if not apl:
                ab.append("plugins 비어있음")
            for i, pl in enumerate(apl):
                miss = [k for k in ("name", "source") if not (isinstance(pl, dict) and pl.get(k))]
                if miss:
                    ab.append(f"plugins[{i}] 필드 누락{miss}")
                src = pl.get("source") if isinstance(pl, dict) else None
                path = src.get("path") if isinstance(src, dict) else None
                if isinstance(path, str) and path.startswith("./") and not (catalog / path).is_dir():
                    ab.append(f"plugins[{i}] source.path 폴더 없음({path})")
        except Exception as e:  # noqa: BLE001
            ab.append(f"JSON 파싱 실패({e})")
    emit("PASS" if not ab else "FAIL", f"R1b Codex 카탈로그(.agents) 구조 ({ab[0] if ab else '-'})")

    # R2 version 존재 + 일관 (누락 None 도 실패 — discard 금지)
    allv = [v for rel in manifests if rel in loaded for v in _versions_with_holes(rel, loaded[rel])]
    holes = any(v is None for v in allv)
    distinct = sorted({v for v in allv if v is not None})
    r2_ok = bool(allv) and not holes and len(distinct) == 1
    why = "누락 있음" if holes else (f"불일치 {distinct}" if len(distinct) != 1 else distinct)
    emit("PASS" if r2_ok else "FAIL", f"R2 매니페스트 version 존재+일관 ({why})")

    # R3 공용 스킬 + frontmatter: 선두 --- 블록 안에 name·description
    skill = plugin / "skills/configure-multiagent/SKILL.md"
    skill_txt = skill.read_text(encoding="utf-8") if skill.is_file() else ""
    fm = re.match(r"^---\n(.*?)\n---\n", skill_txt, re.S)
    fm_body = fm.group(1) if fm else ""
    fm_ok = bool(re.search(r"^name:\s*\S", fm_body, re.M)) and \
        bool(re.search(r"^description:\s*\S", fm_body, re.M))
    emit("PASS" if skill.is_file() and fm_ok else "FAIL",
         "R3 SKILL.md frontmatter(--- 블록 내 name·description)")

    # R4 모든 템플릿 flavor를 광고(F2 회귀 가드) — 파일별·서술필드별·word-boundary.
    #    raw JSON blob 합본 금지(파일간 가림·URL substring 거짓 PASS 방지).
    tdir = SCRIPT_DIR / "templates"
    if not tdir.is_dir():
        emit("FAIL", "R4 generator/templates 디렉토리 없음")
    else:
        tmpl_flavors = sorted(d.name for d in tdir.iterdir() if d.is_dir())
        sources: dict[str, str] = {rel: _desc_text(rel, loaded[rel]) for rel in manifests if rel in loaded}
        sources["SKILL.md"] = skill_txt
        gaps: list[str] = []
        for src, text in sources.items():
            for fl in tmpl_flavors:
                if not re.search(rf"\b{re.escape(fl)}\b", text):
                    gaps.append(f"{src}:{fl}")
        emit("PASS" if not gaps else "FAIL",
             f"R4 flavor {tmpl_flavors} 전부 각 매니페스트/스킬 서술에 광고 (누락: {gaps or '-'})")

    # R5 루트 plugin.json(Antigravity 호스트) — 로딩 경로 미확정이라 부재 시 WARN
    emit("PASS" if (catalog / "plugin.json").is_file() else "WARN",
         "R5 루트 plugin.json (Antigravity 호스트; 부재 시 KI-2 — 머지 전 실설치 검증)")

    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="생성된 MultiAgent 시스템 / 플러그인 repo 자가점검")
    ap.add_argument("--flavor", choices=tuple(FLAVOR), help="생성 타깃 점검 (--repo-check 시 불요)")
    ap.add_argument("--target", help="설치 대상 폴더 (--repo-check 시 불요)")
    ap.add_argument("--repo-check", action="store_true",
                    help="생성 타깃이 아니라 플러그인 repo 자체(매니페스트·레이아웃) 점검")
    args = ap.parse_args()

    if args.repo_check:
        rresults = run_repo_checks(CATALOG_ROOT, PLUGIN_ROOT)
        print(f"  validate(repo): {CATALOG_ROOT} (plugin: {PLUGIN_ROOT.relative_to(CATALOG_ROOT)})")
        failed = warned = 0
        for status, msg in rresults:
            print(f"   [{status}] {msg}")
            failed += status == "FAIL"
            warned += status == "WARN"
        if failed:
            print(f"\n  {failed}개 FAIL — 배포 표면이 불완전합니다.")
            sys.exit(1)
        tail = f" (WARN {warned}개)" if warned else ""
        print(f"\n  repo 점검 PASS ({len(rresults)}개){tail}.")
        return

    if not args.flavor or not args.target:
        sys.exit("[error] --flavor 와 --target 필요 (또는 --repo-check)")

    target = Path(args.target).expanduser().resolve()
    if not target.is_dir():
        sys.exit(f"[error] target 폴더 없음: {target}")

    results = run_checks(target, args.flavor)
    print(f"  validate: flavor={args.flavor} target={target}")
    failed = 0
    for ok, msg in results:
        print(f"   [{'PASS' if ok else 'FAIL'}] {msg}")
        failed += not ok
    if failed:
        print(f"\n  {failed}개 FAIL — 생성 결과가 불완전합니다.")
        sys.exit(1)
    print(f"\n  전부 PASS ({len(results)}개).")


if __name__ == "__main__":
    main()
