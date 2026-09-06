#!/usr/bin/env bash
# gate.sh: G0~G5 각 실패 fixture + 통과 + 디스패처 배선(역할 불일치·exit 9·preview 비경유).
. "$(dirname "$0")/_lib.sh"
echo "gate.sh 사전 게이트"
GATE="$REPO/_shared/adapters/gate.sh"

ROOT="$(new_root <<'JSON'
{"schema_version":"1","flavor":"claude","workers":{"w":{
  "call_type":"cli","model":"m","approval_class":"worker","result_capture":"stdout",
  "timeout":5,"brief_mode":"path","cli":{"command":"agy","args_template":["@brief"]}}}}
JSON
)"
fake_bin "$ROOT" agy 0
gate() { MULTIAGENT_ROOT="$ROOT" bash "$GATE" "$1" 2>"$ROOT/err"; RC=$?; ERR="$(cat "$ROOT/err")"; }
echo "brief 본문" > "$ROOT/b.md"
B="$(place_brief "$ROOT" w "$ROOT/b.md")"

gate "$B";                                   assert_eq "정상 → exit 0" 0 "$RC"
CLAUDE_JOB_DIR=/x gate "$B";                 assert_eq "G0 백그라운드 → 9" 9 "$RC"; assert_contains "G0 메시지" "G0" "$ERR"
gate "$ROOT/b.md";                           assert_eq "G1 위치 밖 → 9" 9 "$RC"; assert_contains "G1 메시지" "G1" "$ERR"
sed -i.bak 's/worker: w/worker: other/' "$ROOT/tasks/t/task.md"; gate "$B"
assert_eq "G2 미승인 → 9" 9 "$RC"; assert_contains "G2 메시지" "G2" "$ERR"; mv "$ROOT/tasks/t/task.md.bak" "$ROOT/tasks/t/task.md"
: > "$ROOT/tasks/t/log.md"; gate "$B";       assert_eq "G3 [APPROVAL] 없음 → 9" 9 "$RC"; assert_contains "G3 메시지" "G3" "$ERR"
approve "$ROOT" w
python3 -c "print('가'*1201)" > "$B"; gate "$B"; assert_eq "G4 한글 1201자 → 9" 9 "$RC"; assert_contains "G4 한글" "한글" "$ERR"
python3 -c "print('word '*241)" > "$B"; gate "$B"; assert_eq "G4 영문 241단어 → 9" 9 "$RC"; assert_contains "G4 영문" "영문" "$ERR"
python3 -c "print('word '*240)" > "$B"; gate "$B"; assert_eq "G4 영문 240단어 → 0" 0 "$RC"
# G5: 패턴 scope
EXT="$(mktemp -d)"
printf 'write_scope: "src/**"\n' > "$B"; gate "$B";       assert_eq "G5 target_repo 없음 → 9" 9 "$RC"; assert_contains "G5 target_repo" "target_repo" "$ERR"
printf 'target_repo: %s\nwrite_scope: "src/**"\n' "$EXT" > "$B"; gate "$B"
assert_eq "G5 승인값 없음 → 9" 9 "$RC"; assert_contains "G5 승인" "승인" "$ERR"
approve "$ROOT" w "$EXT" "tests/**"; gate "$B";           assert_eq "G5 승인값≠brief → 9" 9 "$RC"; assert_contains "G5 재승인" "재승인" "$ERR"
approve "$ROOT" w "$EXT" "src/**"; gate "$B";             assert_eq "G5 승인 일치 → 0" 0 "$RC"
sed -i.bak 's/외부 쓰기 write_scope=src\/\*\*//' "$ROOT/tasks/t/log.md"; gate "$B"
assert_eq "G5 로그에 외부쓰기 승인 없음 → 9" 9 "$RC"
# 다른 워커의 외부 쓰기 승인 로그만 있으면 무효 / 같은 워커의 이전 범위 로그만 있어도 무효
echo "[d] [APPROVAL] other 승인 (외부 쓰기 write_scope=src/**)" >> "$ROOT/tasks/t/log.md"; gate "$B"
assert_eq "G5 다른 워커의 외부쓰기 로그 → 9" 9 "$RC"
echo "[d] [APPROVAL] w 승인 (외부 쓰기 write_scope=tests/**)" >> "$ROOT/tasks/t/log.md"; gate "$B"
assert_eq "G5 같은 워커 이전 범위 로그 → 9" 9 "$RC"
approve "$ROOT" w "$EXT" "src/**"
# --json 출력 + 공백 경로 보존
SP="$(mktemp -d)/My Repo"; mkdir -p "$SP"; printf 'target_repo: %s\nwrite_scope: "src/**"\n' "$SP" > "$B"; approve "$ROOT" w "$SP" "src/**"
J="$(MULTIAGENT_ROOT="$ROOT" bash "$GATE" --json "$B")"; assert_eq "--json target_repo 공백 보존" "$SP" "$(jq -r .target_repo <<<"$J")"
printf 'target_repo: %s\nwrite_scope: "src/**"\n' "$EXT" > "$B"; approve "$ROOT" w "$EXT" "src/**"; rm -rf "$(dirname "$SP")"
# 디스패처 배선
dispatch "$ROOT" w "$B";                      assert_eq "디스패처 통과 → 0" 0 "$RC"
: > "$ROOT/tasks/t/log.md"; dispatch "$ROOT" w "$B"; assert_eq "디스패처 게이트 거부 → 9" 9 "$RC"; assert_contains "게이트 거부 메시지" "게이트 거부" "$ERR"
approve "$ROOT" w "$EXT" "src/**"
# other 역할도 승인된 상태(게이트 자체는 통과)에서 호출 역할만 다른 경우
mkdir -p "$ROOT/tasks/t/workers/other"; cp "$B" "$ROOT/tasks/t/workers/other/brief.md"
sed -i.bak 's/^planned_workers/  - worker: other\n    target_repo: '"$(sed 's/[\/&]/\\&/g' <<<"$EXT")"'\n    write_scope: src\/**\nplanned_workers/' "$ROOT/tasks/t/task.md"
echo "[d] [APPROVAL] other 승인 (외부 쓰기 write_scope=src/**)" >> "$ROOT/tasks/t/log.md"
OUT="$(MULTIAGENT_ROOT="$ROOT" PATH="$ROOT/_shared/bin:$PATH" bash "$DISPATCHER" w "$ROOT/tasks/t/workers/other/brief.md" 2>"$ROOT/err")"; RC=$?
assert_eq "역할 불일치(brief=other, 호출=w) → 9" 9 "$RC"; assert_contains "역할 불일치 메시지" "역할 불일치" "$(cat "$ROOT/err")"
OUT="$(MULTIAGENT_ROOT="$ROOT" bash "$DISPATCHER" --merged-preview "$ROOT/b.md" "$ROOT/b.md" 2>/dev/null)"; RC=$?
assert_eq "preview는 게이트 비경유 → 0" 0 "$RC"
rm -rf "$ROOT" "$EXT"
finish
