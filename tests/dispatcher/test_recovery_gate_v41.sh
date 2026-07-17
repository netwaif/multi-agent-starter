#!/usr/bin/env bash
# v4 4.1: recovery gate가 call_worker.sh dispatch 경로에서 실제로 도는지 검증(통합 마일스톤).
# opt-in(MULTIAGENT_OP_ID) — 미설정 시 게이트 미가동은 다른 테스트가 커버.
. "$(dirname "$0")/_lib.sh"
echo "v4 4.1 recovery gate (dispatch 경로 배선)"

export MULTIAGENT_CODEX_SKIP_GIT=1   # fake 환경엔 git repo 없음

mkroot() {  # codex 워커, timeout $1
  new_root <<JSON
{"schema_version":"1","flavor":"claude","workers":{"c":{
  "call_type":"cli","model":"m","approval_class":"worker","result_capture":"envelope",
  "timeout":$1,"brief_mode":"path","cli":{"command":"codex","args_template":["exec","@brief"]}}}}
JSON
}

# ── 시나리오 A: 정상 성공 → AttemptTerminal(FINAL_SUCCEEDED) ─────────────────
ROOT="$(mkroot 5)"; ln -s "$REPO/_shared/runtime" "$ROOT/_shared/runtime"; echo brief > "$ROOT/brief.txt"
fake_bin "$ROOT" codex 0
export MULTIAGENT_OP_ID="opA"; export MULTIAGENT_EVENTS_DIR="$ROOT/eventsA"
dispatch "$ROOT" c "$ROOT/brief.txt"
assert_eq "A: dispatch rc0"            0 "$RC"
assert_eq "A: gate mode=commit"        commit             "$(jq -r '.recovery_gate.mode'  <<<"$OUT")"
assert_eq "A: gate resolved=true"      true               "$(jq -r '.recovery_gate.resolved' <<<"$OUT")"
assert_eq "A: gate state=SUCCEEDED"    FINAL_SUCCEEDED    "$(jq -r '.recovery_gate.state' <<<"$OUT")"
assert_eq "A: legacy_status=ok"        ok                 "$(jq -r '.legacy_status' <<<"$OUT")"
# durable 이벤트 3종(intent/started/terminal) 기록됨
assert_contains "A: intent 기록"   true "$([ -f "$MULTIAGENT_EVENTS_DIR/opA#a1.intent.json" ]   && echo true || echo false)"
assert_contains "A: started 기록"  true "$([ -f "$MULTIAGENT_EVENTS_DIR/opA#a1.started.json" ]  && echo true || echo false)"
assert_contains "A: terminal 기록" true "$([ -f "$MULTIAGENT_EVENTS_DIR/opA#a1.terminal.json" ] && echo true || echo false)"

# 같은 op 재dispatch: 직전 attempt resolved → #2 admit 되어 또 성공
dispatch "$ROOT" c "$ROOT/brief.txt"
assert_eq "A2: 재dispatch rc0"         0 "$RC"
assert_contains "A2: attempt #2 intent" true "$([ -f "$MULTIAGENT_EVENTS_DIR/opA#a2.intent.json" ] && echo true || echo false)"

# ── 시나리오 B: timeout → UNRESOLVED(A1b) → 다음 dispatch는 gate서 거부 ──────
ROOT2="$(mkroot 1)"; ln -s "$REPO/_shared/runtime" "$ROOT2/_shared/runtime"; echo brief > "$ROOT2/brief.txt"
fake_bin "$ROOT2" codex 0 3   # sleep 3 > timeout 1 → rc124
export MULTIAGENT_OP_ID="opB"; export MULTIAGENT_EVENTS_DIR="$ROOT2/eventsB"
dispatch "$ROOT2" c "$ROOT2/brief.txt"
assert_eq "B: gate resolved=false"     false              "$(jq -r '.recovery_gate.resolved' <<<"$OUT")"
assert_eq "B: gate state=UNRESOLVED"   UNRESOLVED         "$(jq -r '.recovery_gate.state' <<<"$OUT")"
assert_eq "B: legacy_status=timeout"   timeout            "$(jq -r '.legacy_status' <<<"$OUT")"

# 같은 op 재dispatch: 미해결 occupying 존재 → gate 거부(exit 4, spawn 없음)
fake_bin "$ROOT2" codex 0     # 이번엔 성공하게 해도 gate가 먼저 막아야
dispatch "$ROOT2" c "$ROOT2/brief.txt"
assert_eq "B2: gate 거부 rc=4"         4 "$RC"
assert_eq "B2: admissible=false"       false              "$(jq -r '.admissible' <<<"$OUT")"
assert_contains "B2: reason=occupying" occupying          "$(jq -r '.reason' <<<"$OUT")"

unset MULTIAGENT_OP_ID MULTIAGENT_EVENTS_DIR MULTIAGENT_CODEX_SKIP_GIT
rm -rf "$ROOT" "$ROOT2"
finish
