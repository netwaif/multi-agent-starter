#!/usr/bin/env bash
# reentry-check.sh: 정합/불일치 판정 + 재개 오탐 방지.
. "$(dirname "$0")/../dispatcher/_lib.sh"
echo "reentry-check.sh 재진입 정합"
RC_SH="$REPO/_shared/reentry-check.sh"
mk() { # mk <status> <log-lines...>
  local d; d="$(mktemp -d)"; mkdir -p "$d/workers/x"
  { echo '```yaml'; echo "status: $1"; echo 'workers_approved:'; echo '  - worker: x'; echo '```'; } > "$d/task.md"; shift
  printf '%s\n' "$@" > "$d/log.md"; printf '%s' "$d"; }
run() { OUT="$(bash "$RC_SH" "$1" 2>&1)"; RC=$?; rm -rf "$1"; }
run "$(mk in_progress '[2026-01-01 00:00] [DECISION] 시작')";                 assert_eq "정합 → 0" 0 "$RC"
run "$(mk done '[2026-01-01 00:00] [DECISION] 시작')";                        assert_eq "done인데 COMPLETE 없음 → 11" 11 "$RC"
run "$(mk done '[d] [DECISION] a' '[d] [COMPLETE] 끝')";                      assert_eq "done+COMPLETE → 0" 0 "$RC"
run "$(mk in_progress '[d] [DECISION] a' '[d] [COMPLETE] 끝')";               assert_eq "COMPLETE가 마지막인데 in_progress → 11" 11 "$RC"
run "$(mk in_progress '[d] [COMPLETE] 끝' '[d] [DECISION] 재개')";            assert_eq "COMPLETE 뒤 재개 항목 → 0(정상 재개)" 0 "$RC"
run "$(mk in_progress '[d] [COMPLETE] 끝' '[d] [DECISION] 재개: 이전 [COMPLETE] 이후 새 입력')"; assert_eq "본문에 인용된 [COMPLETE]는 무시 → 0" 0 "$RC"
run "$(mk done '[d] [DECISION] 참고: 아직 [COMPLETE] 아님')";                 assert_eq "본문 인용만 있고 실제 COMPLETE 없음 → 11" 11 "$RC"
run "$(mk pending '[d] [WORKER_CALL] x 호출')";                                assert_eq "pending인데 WORKER_CALL → 11" 11 "$RC"
run "$(mk bogus '[d] [DECISION] a')";                                          assert_eq "허용 밖 status → 11" 11 "$RC"
D="$(mk waiting_x '[d] [WORKER_CALL] x')"; echo r > "$D/workers/x/result.md"; run "$D"
assert_eq "waiting인데 result 존재 → 0 + CHECK" 0 "$RC"; assert_contains "CHECK 표시" "CHECK" "$OUT"
D="$(mk in_progress '[d] [WORKER_CALL] x 호출')"; echo b > "$D/workers/x/brief.md"; run "$D"
assert_contains "역할 표에 brief Y" "x              Y" "$OUT"
finish
