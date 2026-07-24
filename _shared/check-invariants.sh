#!/usr/bin/env bash
# check-invariants.sh — system-invariants.md 불변식 표의 실행 러너 (exit-code 판정).
# 사용: bash _shared/check-invariants.sh              # 핵심 INV1~13 판정. 하나라도 FAIL → exit 비0
#       bash _shared/check-invariants.sh --self-test  # 러너 자체 검증: 불변식을 하나씩 깨뜨린
#                                                     # fixture 사본이 실제로 FAIL하는지 확인
# 유지보수자 전용 점검(외부 매뉴얼·generator 템플릿·sync drift)은 자산이 있을 때만 돌고
# WARN으로 보고한다(exit 영향 없음). INV5는 R3 미해소 동안 의도적 불일치 가능.
set -u

SCRIPT_DIR="$(cd "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${MULTIAGENT_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"

PASS=0; FAIL=0; WARN=0
ok() { echo " PASS  $1"; PASS=$((PASS+1)); }
ng() { echo " FAIL  $1"; FAIL=$((FAIL+1)); }
wr() { echo " WARN  $1"; WARN=$((WARN+1)); }

INSTR="$ROOT/CLAUDE.md"
RTG="$ROOT/_shared/routing.md"
APP="$ROOT/_shared/approval-policy.md"
DSB="$ROOT/_shared/design-basis.md"
ORC="$ROOT/_shared/orchestrator-rules.md"
BKD="$ROOT/_shared/backends.json"
LOGT="$ROOT/_templates/log.md"
CTXT="$ROOT/_templates/context.md"
WBR="$ROOT/_templates/worker-brief.md"
WRS="$ROOT/_templates/worker-result.md"
TFD="$ROOT/_templates/task-folder.md"

core_checks() {
  # INV1 write_scope 값 집합 분포 (정의처 CLAUDE.md = 3값 모두, 나머지 = tasks-only 존재)
  if grep -q 'tasks-only' "$INSTR" && grep -q 'none' "$INSTR" \
     && grep -q 'tasks-only' "$RTG" && grep -q 'tasks-only' "$WBR" && grep -q 'tasks-only' "$TFD"; then
    ok "INV1 write_scope 값 집합 분포"; else ng "INV1 write_scope 값 집합 분포"; fi

  # INV2 codex-critic 전용 강제 표현 부재
  if grep -qE 'result.md. 존재 필수|claude-main 결과 필요 → 항상 후행' "$RTG"; then
    ng "INV2 codex-critic 전용 강제 표현 부재"; else ok "INV2 codex-critic 전용 강제 표현 부재"; fi

  # INV3 log 태그 6종 정의 라인
  if grep -q 'DECISION | WORKER_CALL | VERIFICATION | ERROR | APPROVAL | COMPLETE' "$LOGT"; then
    ok "INV3 log 태그 6종"; else ng "INV3 log 태그 6종"; fi

  # INV4 한도 수치 (1500/1200 값 자체가 패턴 — 값 불일치 = 미검출로 FAIL)
  if grep -q '1500자' "$INSTR" && grep -q '1200자' "$INSTR" \
     && grep -q '1500자' "$CTXT" && grep -q '1200자' "$WBR"; then
    ok "INV4 한도 수치 1500/1200"; else ng "INV4 한도 수치 1500/1200"; fi

  # INV6 workers_approved HH:MM 잔존 부재
  if grep -q 'approved_at: <YYYY-MM-DD HH:MM>' "$APP"; then
    ng "INV6 approved_at HH:MM 부재"; else ok "INV6 approved_at HH:MM 부재"; fi

  # INV7 권위 우선순위 문구
  if grep -qiE '권위 우선순위|CLAUDE.md가 가장 높|문서가 충돌' "$DSB"; then
    ok "INV7 권위 우선순위 존재"; else ng "INV7 권위 우선순위 존재"; fi

  # INV8 인터랙티브 전용/worktree 금지
  if grep -qiE 'worktree|백그라운드|background session' "$ORC"; then
    ok "INV8 worktree/백그라운드 금지 규칙"; else ng "INV8 worktree/백그라운드 금지 규칙"; fi

  # INV9 gemini 백엔드 정본 (agy + pro-high)
  if grep -q '"command": "agy"' "$BKD" && grep -q 'gemini-3.1-pro-high' "$BKD"; then
    ok "INV9 gemini 백엔드 agy·pro-high"; else ng "INV9 gemini 백엔드 agy·pro-high"; fi

  # INV10 폐기 브리지 활성 호출 부재
  if grep -q 'mcp__gemini__gemini_' "$RTG" "$TFD" "$INSTR"; then
    ng "INV10 폐기 브리지 활성호출 부재"; else ok "INV10 폐기 브리지 활성호출 부재"; fi

  # INV11a 재진입 프로토콜 이중 존재
  if grep -q '재진입 프로토콜' "$ORC" && grep -q '재진입 프로토콜' "$INSTR"; then
    ok "INV11a 재진입 프로토콜 (rules+지침)"; else ng "INV11a 재진입 프로토콜 (rules+지침)"; fi

  # INV11b 토폴로지 4패턴
  local p miss=0
  for p in 'Pipeline' 'Fan-out/Fan-in' 'Expert Pool' 'Producer-Reviewer'; do
    grep -q "$p" "$RTG" || miss=1
  done
  if [ "$miss" = 0 ]; then ok "INV11b 토폴로지 4패턴"; else ng "INV11b 토폴로지 4패턴"; fi

  # INV11c Supervisor/Hierarchical 은 배제 줄에만
  if grep -E 'Supervisor|Hierarchical' "$RTG" | grep -qv '배제'; then
    ng "INV11c Supervisor/Hierarchical 배제 줄에만"; else ok "INV11c Supervisor/Hierarchical 배제 줄에만"; fi

  # INV12 카파시 4원칙 배선
  if grep -q '운영 원칙 (Operating Principles)' "$INSTR" && grep -q 'Worker 행동 규약' "$WBR" \
     && grep -q '표면화' "$WRS"; then
    ok "INV12 카파시 4원칙 배선"; else ng "INV12 카파시 4원칙 배선"; fi

  # INV12c 워커 규약 블록 내 사용자질문 지시 부재
  if sed -n '/^## Worker 행동 규약/,/^## Execution/p' "$WBR" | grep -qiE '질문|ask'; then
    ng "INV12c 규약 블록 내 질문 지시 부재"; else ok "INV12c 규약 블록 내 질문 지시 부재"; fi

  # INV13 backends 실행계약 정합 (jq)
  if command -v jq >/dev/null 2>&1; then
    if jq -e '.workers["codex-main"].mcp.args_template.sandbox == "workspace-write"' "$BKD" >/dev/null 2>&1 \
       && jq -e '[.workers["codex-main"].fallbacks[]?.cli.args_template // [] | select(index("--sandbox")) | .[index("--sandbox")+1]] | all(. == "workspace-write")' "$BKD" >/dev/null 2>&1 \
       && jq -e '.workers["codex-critic"].mcp.args_template.sandbox == "read-only"' "$BKD" >/dev/null 2>&1 \
       && jq -e '[.workers["codex-critic"].fallbacks[]?.cli.args_template // [] | select(index("--sandbox")) | .[index("--sandbox")+1]] | all(. == "read-only")' "$BKD" >/dev/null 2>&1 \
       && jq -e '(.workers.gemini.fallbacks // []) | length == 0' "$BKD" >/dev/null 2>&1; then
      ok "INV13 backends 실행계약 정합"; else ng "INV13 backends 실행계약 정합"; fi
  else
    ng "INV13 backends 실행계약 정합 (jq 없음 — 디스패처 필수 의존이므로 설치 필요)"
  fi
}

maintainer_checks() {
  # 외부 매뉴얼 (있을 때만) — INV5 섹션 수 비교. 경로는 env로 override 가능(유지보수자 전용)
  local MDIR="${MULTIAGENT_MANUAL_DIR:-$HOME/VSCodeWorkspace/multi-agent-manual}"
  local MANUAL="$MDIR/multi-agent-manual.txt"
  local MANUAL_CLAUDE="$MDIR/CLAUDE.md"
  if [ -f "$MANUAL" ] && [ -f "$MANUAL_CLAUDE" ]; then
    local a b
    a=$(grep -cE '^[0-9]{1,2}\. ' "$MANUAL_CLAUDE" 2>/dev/null || echo 0)
    b=$(grep -E '^[0-9]{1,2}\. ' "$MANUAL" 2>/dev/null | grep -cvE 'brief에|task.md의|log.md에' || echo 0)
    if [ "$a" = "$b" ]; then ok "[유지보수자] INV5 매뉴얼 섹션 수 일치 ($a)"; else wr "[유지보수자] INV5 매뉴얼 섹션 수 불일치 (manual=$b vs repo=$a — R3 미해소 시 의도적)"; fi
    grep -q 'tasks-only' "$MANUAL" && ok "[유지보수자] INV1 매뉴얼 측" || wr "[유지보수자] INV1 매뉴얼 측 tasks-only 부재"
    grep -q 'approved_at: <YYYY-MM-DD HH:MM>' "$MANUAL" && wr "[유지보수자] INV6 매뉴얼 HH:MM 잔존" || ok "[유지보수자] INV6 매뉴얼 측"
  else
    echo " (외부 매뉴얼 없음 — 유지보수자 매뉴얼 점검 건너뜀. 설치본은 정상.)"
  fi

  # generator 템플릿 (있을 때만) — 3 flavor 카파시 배선 + sync drift
  local TPL="$ROOT/plugins/multi-agent-starter/skills/configure-multiagent/generator/templates"
  if [ -d "$TPL" ]; then
    if grep -q 'Operating Principles' "$TPL/codex/AGENTS.md" 2>/dev/null \
       && grep -q 'Operating Principles' "$TPL/antigravity/AGENTS.md" 2>/dev/null; then
      ok "[유지보수자] INV12e Operating Principles (codex·antigravity)"; else wr "[유지보수자] INV12e Operating Principles 누락"; fi
    if grep -q 'Worker 행동 규약' "$TPL/claude/_templates/worker-brief.md" 2>/dev/null \
       && grep -q 'Worker 행동 규약' "$TPL/codex/_templates/worker-brief.md" 2>/dev/null \
       && grep -q 'Worker 행동 규약' "$TPL/antigravity/_templates/worker-brief.md" 2>/dev/null; then
      ok "[유지보수자] INV12f Worker 행동 규약 (3 flavor)"; else wr "[유지보수자] INV12f Worker 행동 규약 누락"; fi
    if python3 "$TPL/../sync_claude_template.py" >/dev/null 2>&1; then
      ok "[유지보수자] sync drift 0 (root↔templates/claude)"; else wr "[유지보수자] sync drift 감지 — sync_claude_template.py 확인"; fi
  else
    echo " (generator 템플릿 없음 — 유지보수자 템플릿 점검 건너뜀. 설치본은 정상.)"
  fi
}

self_test() {
  command -v python3 >/dev/null 2>&1 || { echo "self-test는 python3 필요"; exit 5; }
  local SRC_FILES="CLAUDE.md _shared/routing.md _shared/approval-policy.md _shared/design-basis.md _shared/orchestrator-rules.md _shared/backends.json _templates/log.md _templates/context.md _templates/worker-brief.md _templates/worker-result.md _templates/task-folder.md"
  local TFAIL=0

  make_copy() {  # make_copy <destdir>
    local d="$1" f
    mkdir -p "$d/_shared" "$d/_templates"
    for f in $SRC_FILES; do cp "$ROOT/$f" "$d/$f"; done
  }
  replace_in() {  # replace_in <file> <old> <new> — 패턴 부재는 no-op(사본이 무결로 남아 fixture 단계가 잡음)
    python3 - "$1" "$2" "$3" <<'PYEOF'
import sys, pathlib
p = pathlib.Path(sys.argv[1]); t = p.read_text()
if sys.argv[2] in t:
    p.write_text(t.replace(sys.argv[2], sys.argv[3]))
PYEOF
  }
  run_case() {  # run_case <이름> — 사전에 mutate 함수형 인자 없이, 호출측이 WORK 준비
    local name="$1" rc=0
    MULTIAGENT_ROOT="$WORK" bash "$0" >/dev/null 2>&1 || rc=$?
    if [ "$rc" -ne 0 ]; then echo " PASS  fixture:$name (기대대로 FAIL 검출)"; else echo " FAIL  fixture:$name (깨뜨렸는데 통과함!)"; TFAIL=$((TFAIL+1)); fi
    rm -rf "$WORK"
  }

  # 0) 무결 사본 = 통과해야
  WORK="$(mktemp -d)"; make_copy "$WORK"
  if MULTIAGENT_ROOT="$WORK" bash "$0" >/dev/null 2>&1; then
    echo " PASS  fixture:pristine (무결 사본 통과)"; else echo " FAIL  fixture:pristine (무결 사본이 FAIL)"; TFAIL=$((TFAIL+1)); fi
  rm -rf "$WORK"

  # 각 불변식을 하나씩 깨뜨린 사본 = FAIL해야
  WORK="$(mktemp -d)"; make_copy "$WORK"; replace_in "$WORK/_templates/worker-brief.md" 'tasks-only' 'XXXX'; run_case "INV1"
  WORK="$(mktemp -d)"; make_copy "$WORK"; echo 'claude-main 결과 필요 → 항상 후행' >> "$WORK/_shared/routing.md"; run_case "INV2"
  WORK="$(mktemp -d)"; make_copy "$WORK"; replace_in "$WORK/_templates/log.md" 'APPROVAL | COMPLETE' 'APPROVAL'; run_case "INV3"
  WORK="$(mktemp -d)"; make_copy "$WORK"; replace_in "$WORK/_templates/worker-brief.md" '1200자' '1300자'; run_case "INV4"
  WORK="$(mktemp -d)"; make_copy "$WORK"; echo 'approved_at: <YYYY-MM-DD HH:MM>' >> "$WORK/_shared/approval-policy.md"; run_case "INV6"
  WORK="$(mktemp -d)"; make_copy "$WORK"; replace_in "$WORK/_shared/design-basis.md" '권위 우선순위' '권위순위'; run_case "INV7"
  WORK="$(mktemp -d)"; make_copy "$WORK"
  replace_in "$WORK/_shared/orchestrator-rules.md" 'worktree' 'wtree'
  replace_in "$WORK/_shared/orchestrator-rules.md" 'Worktree' 'Wtree'
  replace_in "$WORK/_shared/orchestrator-rules.md" '백그라운드' '비대화'
  replace_in "$WORK/_shared/orchestrator-rules.md" 'Background Session' 'BG Sess'; run_case "INV8"
  WORK="$(mktemp -d)"; make_copy "$WORK"; replace_in "$WORK/_shared/backends.json" '"command": "agy"' '"command": "zzz"'; run_case "INV9"
  WORK="$(mktemp -d)"; make_copy "$WORK"; echo 'mcp__gemini__gemini_ask 호출' >> "$WORK/_shared/routing.md"; run_case "INV10"
  WORK="$(mktemp -d)"; make_copy "$WORK"; replace_in "$WORK/CLAUDE.md" '재진입 프로토콜' '재진입 절차'; run_case "INV11a"
  WORK="$(mktemp -d)"; make_copy "$WORK"; replace_in "$WORK/_shared/routing.md" 'Expert Pool' 'Xpert Pool'; run_case "INV11b"
  WORK="$(mktemp -d)"; make_copy "$WORK"; echo '| Supervisor (채택) | 상시 | 조정자 추가 |' >> "$WORK/_shared/routing.md"; run_case "INV11c"
  WORK="$(mktemp -d)"; make_copy "$WORK"; replace_in "$WORK/CLAUDE.md" '운영 원칙 (Operating Principles)' '운영 지침'; run_case "INV12"
  WORK="$(mktemp -d)"; make_copy "$WORK"; replace_in "$WORK/_templates/worker-brief.md" '가정은 명시하고' '가정은 질문하고'; run_case "INV12c"
  WORK="$(mktemp -d)"; make_copy "$WORK"; replace_in "$WORK/_shared/backends.json" '"workspace-write"' '"read-only"'; run_case "INV13"

  echo "----------------------------------------"
  if [ "$TFAIL" = 0 ]; then echo "self-test: 전체 fixture 통과 (러너가 각 불변식 파손을 검출함)"; exit 0
  else echo "self-test: $TFAIL 건 실패 — 러너가 파손을 못 잡음"; exit 1; fi
}

if [ "${1:-}" = "--self-test" ]; then self_test; fi

echo "system invariants — ROOT=$ROOT"
core_checks
maintainer_checks
echo "----------------------------------------"
echo "결과: PASS=$PASS FAIL=$FAIL WARN=$WARN"
if [ "$FAIL" = 0 ]; then echo "== ALL PASS =="; exit 0; else echo "== FAIL 존재 — 커밋 금지 (system-invariants.md 표·design-basis 참조) =="; exit 1; fi
