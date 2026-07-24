#!/usr/bin/env bash
# check-invariants.sh — system-invariants.md 불변식 표의 실행 러너 (Antigravity flavor, exit-code 판정).
# 사용: bash _shared/check-invariants.sh   # 하나라도 FAIL → exit 비0 (커밋 금지)
set -u

SCRIPT_DIR="$(cd "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${MULTIAGENT_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"

PASS=0; FAIL=0
ok() { echo " PASS  $1"; PASS=$((PASS+1)); }
ng() { echo " FAIL  $1"; FAIL=$((FAIL+1)); }

INSTR="$ROOT/AGENTS.md"
RTG="$ROOT/_shared/routing.md"
DSB="$ROOT/_shared/design-basis.md"
ORC="$ROOT/_shared/orchestrator-rules.md"
BKD="$ROOT/_shared/backends.json"
LOGT="$ROOT/_templates/log.md"
CTXT="$ROOT/_templates/context.md"
WBR="$ROOT/_templates/worker-brief.md"
WRS="$ROOT/_templates/worker-result.md"
TFD="$ROOT/_templates/task-folder.md"

echo "system invariants (antigravity flavor) — ROOT=$ROOT"

# INV1 write_scope 값 집합 분포
if grep -q 'tasks-only' "$INSTR" && grep -q 'tasks-only' "$RTG" \
   && grep -q 'tasks-only' "$WBR" && grep -q 'tasks-only' "$TFD"; then
  ok "INV1 write_scope tasks-only 분포"; else ng "INV1 write_scope tasks-only 분포"; fi

# INV2 gemini 워커/gemini-critic 활성 참조 부재 (오케스트레이터=Gemini, 자기검수·중복 워커 금지)
if grep -rn 'call_worker.sh gemini\|gemini-critic\|- \*\*gemini\*\*' \
     "$INSTR" "$ROOT/README.md" "$RTG" "$ROOT/_shared/approval-policy.md" "$ROOT/_templates" 2>/dev/null \
     | grep -qviE '없음|금지|폐기|deprecat'; then
  ng "INV2 gemini 워커/gemini-critic 활성 참조 부재"; else ok "INV2 gemini 워커/gemini-critic 활성 참조 부재"; fi

# INV3 codex-critic 비평 워커 존재 (교차 벤더)
if grep -q 'codex-critic' "$INSTR" && grep -q 'codex-critic' "$RTG"; then
  ok "INV3 codex-critic 존재"; else ng "INV3 codex-critic 존재"; fi

# INV4 log 태그 6종
if grep -q 'DECISION | WORKER_CALL | VERIFICATION | ERROR | APPROVAL | COMPLETE' "$LOGT" \
   && grep -q 'DECISION | WORKER_CALL | VERIFICATION | ERROR | APPROVAL | COMPLETE' "$INSTR"; then
  ok "INV4 log 태그 6종"; else ng "INV4 log 태그 6종"; fi

# INV5 한도 수치
if grep -qE '1500자|1500 chars' "$INSTR" && grep -qE '1200자|1200 chars' "$INSTR" \
   && grep -qE '1500자|1500 chars' "$CTXT" && grep -qE '1200자|1200 chars' "$WBR"; then
  ok "INV5 한도 수치 1500/1200"; else ng "INV5 한도 수치 1500/1200"; fi

# INV6 권위 우선순위 (AGENTS.md 기준)
if grep -qE 'AGENTS.md.*routing.md' "$DSB" || grep -qE 'AGENTS.md.*routing.md' "$ORC"; then
  ok "INV6 권위 우선순위 (AGENTS.md 기준)"; else ng "INV6 권위 우선순위 (AGENTS.md 기준)"; fi

# INV7 재진입 프로토콜 이중 존재
if grep -q '재진입 프로토콜' "$ORC" && grep -qE 're-entry protocol|재진입 프로토콜' "$INSTR"; then
  ok "INV7 재진입 프로토콜 (rules+지침)"; else ng "INV7 재진입 프로토콜 (rules+지침)"; fi

# INV8 토폴로지 4패턴
miss=0
for p in 'Pipeline' 'Fan-out/Fan-in' 'Expert Pool' 'Producer-Reviewer'; do
  grep -q "$p" "$RTG" || miss=1
done
if [ "$miss" = 0 ]; then ok "INV8 토폴로지 4패턴"; else ng "INV8 토폴로지 4패턴"; fi

# INV9 오케스트레이터·워커셋
w_ok=1
grep -q 'Gemini 3.1 Pro High' "$INSTR" || w_ok=0
for w in claude-main codex-main codex-critic; do
  grep -q "\"$w\"" "$BKD" || w_ok=0
done
if [ "$w_ok" = 1 ]; then ok "INV9 오케스트레이터 agy + 워커셋 3종"; else ng "INV9 오케스트레이터 agy + 워커셋 3종"; fi

# INV10 gemini 워커 호출/옛 프록시 활성 부재 (폐기 문맥 제외)
if grep -rn 'call_worker.sh gemini\|mcp__gemini-pro__\|mcp__gemini__gemini_' \
     "$RTG" "$TFD" "$INSTR" "$BKD" 2>/dev/null | grep -qviE '폐기|deprecat|없음|금지'; then
  ng "INV10 gemini 호출/옛 프록시 활성 부재"; else ok "INV10 gemini 호출/옛 프록시 활성 부재"; fi

# INV11 카파시 4원칙 배선 + 블록 내 질문 지시 부재
if grep -q 'Operating Principles' "$INSTR" && grep -q 'Worker 행동 규약' "$WBR" \
   && grep -q '표면화' "$WRS"; then
  ok "INV11 카파시 4원칙 배선"; else ng "INV11 카파시 4원칙 배선"; fi
if sed -n '/^## Worker 행동 규약/,/^## Execution/p' "$WBR" | grep -qiE '질문|ask'; then
  ng "INV11b 규약 블록 내 질문 지시 부재"; else ok "INV11b 규약 블록 내 질문 지시 부재"; fi

echo "----------------------------------------"
echo "결과: PASS=$PASS FAIL=$FAIL"
if [ "$FAIL" = 0 ]; then echo "== ALL PASS =="; exit 0; else echo "== FAIL 존재 — 커밋 금지 (system-invariants.md 표 참조) =="; exit 1; fi
