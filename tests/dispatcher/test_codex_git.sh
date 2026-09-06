#!/usr/bin/env bash
# codex git 정책: 기본은 git 요구(여기선 git 설치돼 있으니 플래그 없음),
# 옵트아웃(MULTIAGENT_CODEX_SKIP_GIT=1) 시에만 exec 뒤에 --skip-git-repo-check 주입.
. "$(dirname "$0")/_lib.sh"
echo "codex git 정책 (A기본 + B옵트아웃)"

ROOT="$(new_root <<'JSON'
{"schema_version":"1","flavor":"antigravity","workers":{"c":{
  "call_type":"cli","model":"m","approval_class":"worker","result_capture":"stdout",
  "timeout":10,"brief_mode":"path","cli":{"command":"codex","args_template":["exec","@brief_content"]}}}}
JSON
)"
echo "BRIEF-TEXT" > "$ROOT/brief.txt"
B="$(place_brief "$ROOT" c "$ROOT/brief.txt")"   # gate.sh 통과용 정규 위치 + 승인 fixture
# 받은 인자를 그대로 출력하는 가짜 codex
{ echo '#!/usr/bin/env bash'; echo 'echo "ARGS: $*"'; echo 'exit 0'; } > "$ROOT/_shared/bin/codex"
chmod +x "$ROOT/_shared/bin/codex"

# 옵트아웃 ON → exec 바로 뒤에 --skip-git-repo-check 주입
OUT="$(MULTIAGENT_CODEX_SKIP_GIT=1 MULTIAGENT_ROOT="$ROOT" PATH="$ROOT/_shared/bin:$PATH" bash "$DISPATCHER" c "$B" 2>/dev/null)"; RC=$?
so="$(jq -r '.stdout' <<<"$OUT")"
assert_eq       "옵트아웃 exit 0"                 0                          "$RC"
assert_contains "exec 뒤 --skip-git-repo-check 주입" "exec --skip-git-repo-check" "$so"

# 기본(옵트아웃 OFF, git 설치됨) → 플래그 없음
OUT2="$(MULTIAGENT_ROOT="$ROOT" PATH="$ROOT/_shared/bin:$PATH" bash "$DISPATCHER" c "$B" 2>/dev/null)"
so2="$(jq -r '.stdout' <<<"$OUT2")"
case "$so2" in
  *"--skip-git-repo-check"*) echo "  FAIL: 기본인데 플래그 주입됨"; FAIL=$((FAIL+1));;
  *)                         echo "  PASS: 기본은 플래그 없음"; PASS=$((PASS+1));;
esac

rm -rf "$ROOT"
finish
