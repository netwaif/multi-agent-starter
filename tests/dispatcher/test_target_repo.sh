#!/usr/bin/env bash
# @target_repo는 절대경로를 argv로 전달하되 worker cwd는 격리 임시 폴더여야 한다.
. "$(dirname "$0")/_lib.sh"

ROOT="$(new_root <<'JSON'
{
  "workers": {
    "claude-critic": {
      "model": "host-default",
      "call_type": "cli",
      "brief_mode": "content",
      "cli": {
        "command": "claude",
        "args_template": ["--add-dir", "@target_repo", "--print", "@brief_content"]
      },
      "cwd_policy": "isolated_tmp",
      "timeout": 10
    }
  }
}
JSON
)"
TRACE_DIR="$(mktemp -d)"
TARGET="$(mktemp -d)"
BRIEF="$ROOT/brief.md"
printf '%s\n' 'review this target' > "$BRIEF"

cat > "$ROOT/_shared/bin/claude" <<'SH'
#!/usr/bin/env bash
pwd > "$TRACE_DIR/pwd"
printf '%s\n' "$@" > "$TRACE_DIR/args"
echo critic-ok
SH
chmod +x "$ROOT/_shared/bin/claude"

ERR_FILE="$TRACE_DIR/missing.err"
MULTIAGENT_ROOT="$ROOT" PATH="$ROOT/_shared/bin:$PATH" \
  bash "$DISPATCHER" claude-critic "$BRIEF" >/dev/null 2>"$ERR_FILE"
RC=$?
assert_eq "TARGET_REPO 누락은 fail-closed" "6" "$RC"
assert_contains "누락 오류가 원인을 설명" "TARGET_REPO" "$(cat "$ERR_FILE")"

TARGET_REPO="$TARGET" TRACE_DIR="$TRACE_DIR" MULTIAGENT_ROOT="$ROOT" \
  PATH="$ROOT/_shared/bin:$PATH" bash "$DISPATCHER" claude-critic "$BRIEF" >/dev/null
RC=$?
assert_eq "격리 호출 성공" "0" "$RC"
ARGS="$(cat "$TRACE_DIR/args")"
assert_contains "대상 경로가 --add-dir 인자로 확장" "$TARGET" "$ARGS"
WORKER_PWD="$(cat "$TRACE_DIR/pwd")"
if [ "$WORKER_PWD" != "$ROOT" ] && [ "$WORKER_PWD" != "$TARGET" ]; then
  echo "  PASS: worker cwd가 원본과 대상에서 격리"; PASS=$((PASS+1))
else
  echo "  FAIL: worker cwd 격리 실패 [$WORKER_PWD]"; FAIL=$((FAIL+1))
fi
if [ ! -e "$WORKER_PWD" ]; then
  echo "  PASS: 격리 임시 폴더 호출 후 제거"; PASS=$((PASS+1))
else
  echo "  FAIL: 격리 임시 폴더 잔존 [$WORKER_PWD]"; FAIL=$((FAIL+1))
fi

rm -rf -- "$ROOT" "$TRACE_DIR" "$TARGET"
finish
