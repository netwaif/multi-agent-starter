#!/usr/bin/env bash
# S6: 워커가 timeout 초과 → envelope status=timeout, exit_code=124.
. "$(dirname "$0")/_lib.sh"
echo "S6 디스패처 timeout (초과 → 124)"

ROOT="$(new_root <<'JSON'
{"schema_version":"2","flavor":"claude",
 "providers":{"t":{
  "call_type":"cli","model":"m","approval_class":"worker","result_capture":"stdout",
  "timeout":1,"brief_mode":"path","cli":{"command":"agy","args_template":["-p","@brief"]}}},
 "roles":{"t":{"provider":"t"}}}
JSON
)"
echo "brief" > "$ROOT/brief.txt"
fake_bin "$ROOT" agy 0 3      # 3초 sleep > timeout 1초

dispatch "$ROOT" t "$ROOT/brief.txt"
assert_eq "status=timeout" timeout "$(jq -r '.status'    <<<"$OUT")"
assert_eq "exit_code=124"  124     "$(jq -r '.exit_code' <<<"$OUT")"

rm -rf "$ROOT"
finish
