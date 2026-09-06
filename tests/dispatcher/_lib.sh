#!/usr/bin/env bash
# 디스패처 테스트 공용 헬퍼. 각 test_*.sh 첫 줄: . "$(dirname "$0")/_lib.sh"
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DISPATCHER="$REPO/_shared/adapters/call_worker.sh"
PASS=0; FAIL=0

assert_eq() {       # assert_eq <desc> <expected> <actual>
  if [ "$2" = "$3" ]; then echo "  PASS: $1"; PASS=$((PASS+1))
  else echo "  FAIL: $1 (expected [$2] got [$3])"; FAIL=$((FAIL+1)); fi
}
assert_contains() { # assert_contains <desc> <needle> <haystack>
  case "$3" in *"$2"*) echo "  PASS: $1"; PASS=$((PASS+1));;
            *) echo "  FAIL: $1 (missing [$2])"; FAIL=$((FAIL+1));; esac
}
finish() { echo "  ($PASS pass / $FAIL fail)"; [ "$FAIL" -eq 0 ]; }

new_root() {        # stdin=backends.json → echoes temp root path
  local d; d="$(mktemp -d)"; mkdir -p "$d/_shared/bin"
  cat > "$d/_shared/backends.json"; printf '%s' "$d"
}
fake_bin() {        # fake_bin <root> <name> <exit> [sleep_secs]
  local r="$1" n="$2" rc="$3" s="${4:-0}"
  { echo '#!/usr/bin/env bash'; echo "sleep $s"; echo "echo fake-$n-out"; echo "exit $rc"; } \
    > "$r/_shared/bin/$n"
  chmod +x "$r/_shared/bin/$n"
}
approve() {         # approve <root> <role> [target_repo] [write_scope] — gate.sh 통과용 승인 fixture (task.md·log.md)
  local r="$1" role="$2" repo="${3:-}" scope="${4:-}"
  mkdir -p "$r/tasks/t/workers/$role"
  { echo '```yaml'; echo 'status: in_progress'; echo 'workers_approved:'; echo "  - worker: $role"
    [ -n "$repo" ]  && echo "    target_repo: $repo"
    [ -n "$scope" ] && echo "    write_scope: $scope"
    echo 'planned_workers: []'; echo '```'; } > "$r/tasks/t/task.md"
  echo "[2026-01-01 00:00] [APPROVAL] $role 승인${scope:+ (외부 쓰기 write_scope=$scope)}" > "$r/tasks/t/log.md"
}
place_brief() {     # place_brief <root> <role> <brief-src> → echoes 정규 위치 brief 경로
  approve "$1" "$2"
  cp "$3" "$1/tasks/t/workers/$2/brief.md"; printf '%s' "$1/tasks/t/workers/$2/brief.md"
}
dispatch() {        # dispatch <root> <role> <brief> → sets OUT, ERR, RC
  # brief가 이미 tasks/<task>/workers/<role>/brief.md 형태가 아니면 승인 fixture로 옮긴다('..' 등 가드 fixture는 그대로).
  local b="$3"
  if [ -f "$b" ] && [[ "$b" != */tasks/*/workers/*/brief.md ]]; then b="$(place_brief "$1" "$2" "$b")"; fi
  local ef; ef="$(mktemp)"
  OUT="$(MULTIAGENT_ROOT="$1" PATH="$1/_shared/bin:$PATH" bash "$DISPATCHER" "$2" "$b" 2>"$ef")"; RC=$?
  ERR="$(cat "$ef")"; rm -f "$ef"
}
