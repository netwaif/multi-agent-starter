#!/usr/bin/env bash
# codex 워커 = codex exec (D15): 실제 backends.json 계약(인자·stdin·cwd=tasks/<task>/·외부 쓰기 시 target_repo)
# + --out 요약 출력 + stderr 진행 표시. 가짜 codex가 받은 인자·stdin·pwd를 그대로 출력.
. "$(dirname "$0")/_lib.sh"
echo "codex exec 기본 경로 (D15)"

ROOT="$(new_root < "$REPO/_shared/backends.json")"; git -C "$ROOT" init -q
{ echo '#!/usr/bin/env bash'; echo 'echo "ARGS: $*"'; echo 'echo "PWD: $(pwd -P)"'; echo 'echo "STDIN: $(cat)"'; echo 'exit 0'; } > "$ROOT/_shared/bin/codex"
chmod +x "$ROOT/_shared/bin/codex"
EF_ERR="$(mktemp)"   # stderr 캡처는 ROOT 밖(ROOT 안 쓰기 = scope 위반)
run() { OUT="$(MULTIAGENT_ROOT="$ROOT" PATH="$ROOT/_shared/bin:$PATH" bash "$DISPATCHER" "$@" 2>"$EF_ERR")"; RC=$?; ERR="$(cat "$EF_ERR")"; }

for pair in "codex-main:workspace-write" "codex-critic:read-only"; do
  role="${pair%%:*}"; sb="${pair#*:}"
  approve "$ROOT" "$role"; printf 'write_scope: tasks-only\n작은 과제 BRIEF-%s\n' "$role" > "$ROOT/tasks/t/workers/$role/brief.md"
  run "$role" "$ROOT/tasks/t/workers/$role/brief.md"; so="$(jq -r .stdout <<<"$OUT")"
  assert_eq       "$role exit 0"                      0 "$RC"
  assert_contains "$role 인자 = exec --sandbox $sb -c approval_policy=never -" "ARGS: exec --sandbox $sb -c approval_policy=never -" "$so"
  assert_contains "$role brief는 stdin"               "BRIEF-$role" "$so"
  assert_contains "$role cwd = tasks/<task>/"         "PWD: $(cd "$ROOT/tasks/t" && pwd -P)" "$so"
  assert_eq       "$role 폴백 없음"                    false "$(jq -r .fallback_used <<<"$OUT")"
  assert_contains "$role stderr 시작 표시"             "[call_worker] $role 시작" "$ERR"
  assert_contains "$role stderr 종료 표시"             "[call_worker] $role 종료 — ok" "$ERR"
done

# 외부 쓰기 4조건(write_scope 패턴) → cwd = target_repo
EXT="$(mktemp -d)"; git -C "$EXT" init -q
approve "$ROOT" codex-main "$EXT" "src/**"; printf 'target_repo: %s\nwrite_scope: "src/**"\n' "$EXT" > "$ROOT/tasks/t/workers/codex-main/brief.md"
run codex-main "$ROOT/tasks/t/workers/codex-main/brief.md"
assert_contains "외부 쓰기 → cwd=target_repo" "PWD: $(cd "$EXT" && pwd -P)" "$(jq -r .stdout <<<"$OUT")"

# --out: 파일엔 envelope JSON, 화면엔 요약(상태·응답)만
approve "$ROOT" codex-critic; printf 'write_scope: none\nBRIEF-OUT\n' > "$ROOT/tasks/t/workers/codex-critic/brief.md"
EF="$ROOT/tasks/t/workers/codex-critic/envelope.json"
run --out "$EF" codex-critic "$ROOT/tasks/t/workers/codex-critic/brief.md"
assert_eq       "--out exit 0"                   0 "$RC"
assert_contains "--out 요약 상태 줄"              "[call_worker] codex-critic 결과: ok" "$OUT"
assert_contains "--out 요약에 워커 최종 응답"      "BRIEF-OUT" "$OUT"
assert_eq       "--out 파일 = envelope JSON"      ok "$(jq -r .status "$EF")"
case "$OUT" in *'"stderr_sanitized"'*) echo "  FAIL: --out인데 JSON이 화면에"; FAIL=$((FAIL+1));; *) echo "  PASS: --out 화면에 JSON 없음"; PASS=$((PASS+1));; esac

# --out + 실패 → 같은 exit, 요약에 stderr 끝
{ echo '#!/usr/bin/env bash'; echo 'echo "boom-err" >&2'; echo 'exit 3'; } > "$ROOT/_shared/bin/codex"
run --out "$EF" codex-critic "$ROOT/tasks/t/workers/codex-critic/brief.md"
assert_eq       "--out 실패 exit 비0"             1 "$RC"
assert_contains "--out 실패 요약에 stderr"        "boom-err" "$OUT"

rm -rf "$ROOT" "$EXT" "$EF_ERR"
finish
