#!/usr/bin/env bash
# v4: runtime/이 배치된 ROOT에서 call_worker.sh가 envelope v2를 방출하는지 검증.
# (runtime이 없는 ROOT는 v1 폴백 — test_timeout/fallback/codex_git이 그 경로를 검증한다.)
. "$(dirname "$0")/_lib.sh"
echo "v4 디스패처 envelope v2 (runtime 배치 시)"

# generic 등록 backend(codex)는 버전 무관 매칭이라 fake_bin(버전 미노출)으로도 성공 판정 가능.
ROOT="$(new_root <<'JSON'
{"schema_version":"1","flavor":"claude","workers":{"c":{
  "call_type":"cli","model":"m","approval_class":"worker","result_capture":"envelope",
  "timeout":5,"brief_mode":"path","cli":{"command":"codex","args_template":["exec","@brief"]}}}}
JSON
)"
# runtime을 ROOT에 링크 → call_worker가 envelope.py를 찾아 v2 경로를 탄다.
ln -s "$REPO/_shared/runtime" "$ROOT/_shared/runtime"
echo "brief" > "$ROOT/brief.txt"

# 성공(rc0) → v2 envelope, legacy_status=ok, classification classified/none
fake_bin "$ROOT" codex 0
# codex 워커는 기본 git 요구 → 우회(fake 환경엔 git repo 없음)
MULTIAGENT_CODEX_SKIP_GIT=1 dispatch "$ROOT" c "$ROOT/brief.txt"
assert_eq "schema_version=2"  2    "$(jq -r '.schema_version'  <<<"$OUT")"
assert_eq "legacy_status=ok"  ok   "$(jq -r '.legacy_status'   <<<"$OUT")"
assert_eq "ok=true"           true "$(jq -r '.ok'              <<<"$OUT")"
assert_eq "class=classified"  classified "$(jq -r '.classification.status' <<<"$OUT")"
assert_eq "failure_class=none" none "$(jq -r '.classification.failure_class' <<<"$OUT")"
assert_eq "route_id"          codex-cli "$(jq -r '.identity.backend_route_id' <<<"$OUT")"
assert_contains "stdout_sha256 존재" true "$([ "$(jq -r '.output.stdout_sha256' <<<"$OUT")" != null ] && echo true || echo false)"

# 실패(rc≠0) → legacy_status=error
fake_bin "$ROOT" codex 1
MULTIAGENT_CODEX_SKIP_GIT=1 dispatch "$ROOT" c "$ROOT/brief.txt"
assert_eq "rc≠0 → legacy=error" error "$(jq -r '.legacy_status' <<<"$OUT")"

# timeout(rc124) → legacy_status=timeout, process=wrapper_timeout
fake_bin "$ROOT" codex 0 8    # 8s sleep > timeout 5s? 아니 timeout 5 — 조정: 워커 timeout을 1로 재설정
# timeout 케이스는 별도 backends로
ROOT2="$(new_root <<'JSON'
{"schema_version":"1","flavor":"claude","workers":{"c":{
  "call_type":"cli","model":"m","approval_class":"worker","result_capture":"envelope",
  "timeout":1,"brief_mode":"path","cli":{"command":"codex","args_template":["exec","@brief"]}}}}
JSON
)"
ln -s "$REPO/_shared/runtime" "$ROOT2/_shared/runtime"
echo "brief" > "$ROOT2/brief.txt"
fake_bin "$ROOT2" codex 0 3   # 3s > timeout 1s
MULTIAGENT_CODEX_SKIP_GIT=1 dispatch "$ROOT2" c "$ROOT2/brief.txt"
assert_eq "timeout → legacy=timeout"      timeout        "$(jq -r '.legacy_status'   <<<"$OUT")"
assert_eq "timeout → process=wrapper_timeout" wrapper_timeout "$(jq -r '.process.status' <<<"$OUT")"

rm -rf "$ROOT" "$ROOT2"
finish
