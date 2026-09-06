#!/usr/bin/env bash
# scope_check.sh: 안/밖/rename 양쪽/dirty 재수정/untracked 재수정/none/tasks-only/비git + 디스패처 배선(위반 exit 10·폴백 없음).
. "$(dirname "$0")/_lib.sh"
echo "scope_check.sh 사후 검사"
SC="$REPO/_shared/adapters/scope_check.sh"

mkrepo() { local r; r="$(mktemp -d)"; git -C "$r" init -q; mkdir -p "$r/src" "$r/config" "$r/tasks/t" "$r/tasks/u"
  echo a>"$r/src/a.c"; echo p>"$r/config/prod.yml"; echo d>"$r/dirty.txt"; git -C "$r" add -A; git -C "$r" -c user.email=t@t -c user.name=t commit -qm i
  echo d2>>"$r/dirty.txt"; echo u>"$r/untracked.txt"; printf '%s' "$r"; }
R="$(mkrepo)"; bash "$SC" --snapshot "$R" > "$R.before"
echo b>>"$R/src/a.c"; echo d3>>"$R/dirty.txt"; echo u2>>"$R/untracked.txt"; git -C "$R" mv config/prod.yml src/prod.yml; echo n>"$R/tasks/u/new.md"
V="$(bash "$SC" "$R" "src/**" "$R.before")"; RC=$?
assert_eq "위반 exit 10" 10 "$RC"
assert_contains "dirty 재수정 검출" "dirty.txt" "$V"
assert_contains "untracked 재수정 검출" "untracked.txt" "$V"
assert_contains "rename 원본(범위 밖) 검출" "config/prod.yml" "$V"
case "$V" in *"src/a.c"*|*"src/prod.yml"*) echo "  FAIL: 범위 안 변경이 위반으로"; FAIL=$((FAIL+1));; *) echo "  PASS: 범위 안 변경은 통과"; PASS=$((PASS+1));; esac
assert_eq "중복 없음" 1 "$(grep -c '^dirty.txt$' <<<"$V")"
V="$(bash "$SC" "$R" tasks-only "$R.before" t)"; RC=$?
assert_eq "tasks-only 위반 exit 10" 10 "$RC"; assert_contains "다른 task 폴더 검출" "tasks/u/new.md" "$V"
bash "$SC" "$R" tasks-only "$R.before" >/dev/null 2>&1; assert_eq "tasks-only task 인자 없음 → 64" 64 "$?"
rm -rf "$R" "$R.before"
R="$(mkrepo)"; bash "$SC" --snapshot "$R" > "$R.before"; echo x>"$R/tasks/t/r.md"
bash "$SC" "$R" tasks-only "$R.before" t >/dev/null; assert_eq "현재 task 안만 변경 → 0" 0 "$?"
bash "$SC" "$R" none "$R.before" >/dev/null;         assert_eq "none 인데 변경 → 10" 10 "$?"
rm -rf "$R" "$R.before"
R="$(mkrepo)"; bash "$SC" --snapshot "$R" > "$R.before"
bash "$SC" "$R" none "$R.before" >/dev/null;         assert_eq "none 변경 없음 → 0" 0 "$?"
NG="$(mktemp -d)"; bash "$SC" "$NG" "src/**" "$R.before" 2>/dev/null; assert_eq "비git → 12(검사 불가)" 12 "$?"
chmod 000 "$R/.git/index"; bash "$SC" --snapshot "$R" >/dev/null 2>&1; assert_eq "git status 실패 → snapshot 12" 12 "$?"; chmod 644 "$R/.git/index"
rm -rf "$R" "$R.before" "$NG"
# 서브디렉터리 target(공백 경로) + 탭 파일명 + repo 밖 변경
SR="$(mktemp -d)/My Repo"; mkdir -p "$SR/sub/src" "$SR/other"; git -C "$SR" init -q; echo a>"$SR/sub/src/a.c"; echo o>"$SR/other/o.txt"
git -C "$SR" add -A; git -C "$SR" -c user.email=t@t -c user.name=t commit -qm i; bash "$SC" --snapshot "$SR/sub" > "$SR.before"
echo b>>"$SR/sub/src/a.c"; printf 'x' > "$SR/sub/src/tab	name"; echo z>"$SR/sub/zz.txt"; echo o2>>"$SR/other/o.txt"
V="$(bash "$SC" "$SR/sub" "src/**" "$SR.before")"; RC=$?
assert_eq "서브디렉터리 target 위반 exit 10" 10 "$RC"
assert_contains "서브디렉터리 기준 상대경로" "zz.txt" "$V"; assert_contains "repo 밖 변경은 위반" "../other/o.txt" "$V"
case "$V" in *"src/a.c"*|*"tab"*) echo "  FAIL: 범위 안(탭 파일명 포함)이 위반으로"; FAIL=$((FAIL+1));; *) echo "  PASS: 서브디렉터리 범위 안·탭 파일명 통과"; PASS=$((PASS+1));; esac
bash "$SC" --snapshot "$SR/sub" > "$SR.before2"; printf 'y' > "$SR/sub/tab	out"; V="$(bash "$SC" "$SR/sub" "src/**" "$SR.before2")"
assert_contains "탭 파일명 손실 없이 위반 검출" "tab	out" "$V"
rm -rf "$(dirname "$SR")"

# 디스패처 배선: 워커가 scope 밖에 쓰면 status=scope_violation, exit 10, 폴백 미실행
EXT="$(mkrepo)"
ROOT="$(new_root <<'JSON'
{"schema_version":"1","flavor":"claude","workers":{"w":{
  "call_type":"cli","model":"m","approval_class":"worker","result_capture":"stdout","cwd_policy":"target",
  "timeout":5,"brief_mode":"path","cli":{"command":"codex","args_template":["exec","@brief"]},
  "fallbacks":[{"call_type":"cli","model":"fb","timeout":5,"brief_mode":"path","cwd_policy":"target","cli":{"command":"agy","args_template":["@brief"]}}]}}}
JSON
)"
{ echo '#!/usr/bin/env bash'; echo 'echo hacked > outside.txt; echo ok > src/in.c; echo worker-out'; } > "$ROOT/_shared/bin/codex"; chmod +x "$ROOT/_shared/bin/codex"
fake_bin "$ROOT" agy 0
approve "$ROOT" w "$EXT" "src/**"; mkdir -p "$ROOT/tasks/t/workers/w"
printf 'target_repo: %s\nwrite_scope: "src/**"\n' "$EXT" > "$ROOT/tasks/t/workers/w/brief.md"
dispatch "$ROOT" w "$ROOT/tasks/t/workers/w/brief.md"
assert_eq "scope 위반 → exit 10" 10 "$RC"
assert_eq "status=scope_violation" scope_violation "$(jq -r .status <<<"$OUT")"
assert_eq "위반 목록" outside.txt "$(jq -r '.scope_violations[0]' <<<"$OUT")"
assert_eq "폴백 미사용" false "$(jq -r .fallback_used <<<"$OUT")"
assert_contains "워커 stdout 보존" "worker-out" "$(jq -r .stdout <<<"$OUT")"
[ -f "$EXT/outside.txt" ] && { echo "  PASS: 비파괴(파일 revert 안 함)"; PASS=$((PASS+1)); } || { echo "  FAIL: 파일이 사라짐"; FAIL=$((FAIL+1)); }
# fallback에서 발생한 위반도 exit 10 + 다음 fallback 미실행
{ echo '#!/usr/bin/env bash'; echo 'exit 1'; } > "$ROOT/_shared/bin/codex"
{ echo '#!/usr/bin/env bash'; echo 'echo hacked2 > outside2.txt; echo fb-out'; } > "$ROOT/_shared/bin/agy"; chmod +x "$ROOT/_shared/bin/agy"
dispatch "$ROOT" w "$ROOT/tasks/t/workers/w/brief.md"
assert_eq "fallback scope 위반 → exit 10" 10 "$RC"
assert_eq "fallback 위반 status" scope_violation "$(jq -r .status <<<"$OUT")"
assert_eq "fallback 위반 envelope 보존" outside2.txt "$(jq -r '.scope_violations[0]' <<<"$OUT")"
{ echo '#!/usr/bin/env bash'; echo 'echo hacked > outside.txt; echo ok > src/in.c; echo worker-out'; } > "$ROOT/_shared/bin/codex"; fake_bin "$ROOT" agy 0
# none scope면 cwd=$ROOT (외부 repo에 안 씀)
printf 'target_repo: %s\nwrite_scope: none\n' "$EXT" > "$ROOT/tasks/t/workers/w/brief.md"; approve "$ROOT" w
{ echo '#!/usr/bin/env bash'; echo 'pwd'; } > "$ROOT/_shared/bin/codex"
dispatch "$ROOT" w "$ROOT/tasks/t/workers/w/brief.md"
assert_eq "none scope cwd=ROOT" "$(cd "$ROOT" && pwd -P)" "$(jq -r .stdout <<<"$OUT" | tr -d '\n' | xargs -I{} sh -c 'cd {} && pwd -P')"
# 잔존 TARGET_REPO env는 무시 (none/tasks-only)
OUT="$(TARGET_REPO="$EXT" MULTIAGENT_ROOT="$ROOT" PATH="$ROOT/_shared/bin:$PATH" bash "$DISPATCHER" w "$ROOT/tasks/t/workers/w/brief.md" 2>/dev/null)"
assert_eq "TARGET_REPO env 무시(cwd=ROOT)" "$(cd "$ROOT" && pwd -P)" "$(jq -r .stdout <<<"$OUT" | tr -d '\n' | xargs -I{} sh -c 'cd {} && pwd -P')"
# 실행 전 스냅샷 실패(git repo인데 status 불가) → 호출 거부 exit 12
printf 'target_repo: %s\nwrite_scope: "src/**"\n' "$EXT" > "$ROOT/tasks/t/workers/w/brief.md"; approve "$ROOT" w "$EXT" "src/**"
chmod 000 "$EXT/.git/index"; dispatch "$ROOT" w "$ROOT/tasks/t/workers/w/brief.md"; assert_eq "스냅샷 실패 → 호출 거부 12" 12 "$RC"; chmod 644 "$EXT/.git/index"
rm -rf "$ROOT" "$EXT"
finish
