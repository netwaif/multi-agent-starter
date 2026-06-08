#!/usr/bin/env bash
# S5: primary 백엔드 실패 → fallback 성공. (the hard-won EXIT-trap/set-e 회귀 가드)
. "$(dirname "$0")/_lib.sh"
echo "S5 디스패처 폴백 (primary 실패 → fallback 성공)"

ROOT="$(new_root <<'JSON'
{"schema_version":"2","flavor":"claude",
 "providers":{"t":{
  "call_type":"cli","model":"primary","approval_class":"worker","result_capture":"stdout",
  "timeout":10,"brief_mode":"path","cli":{"command":"agy","args_template":["-p","@brief"]},
  "fallbacks":[{"call_type":"cli","model":"fb","approval_class":"worker","result_capture":"stdout",
    "timeout":10,"brief_mode":"path","cli":{"command":"claude","args_template":["-p","@brief"]}}]}},
 "roles":{"t":{"provider":"t"}}}
JSON
)"
echo "brief" > "$ROOT/brief.txt"
fake_bin "$ROOT" agy    1     # primary 실패
fake_bin "$ROOT" claude 0     # fallback 성공

dispatch "$ROOT" t "$ROOT/brief.txt"
assert_eq       "전체 exit 0"        0    "$RC"
assert_eq       "fallback_used=true" true "$(jq -r '.fallback_used' <<<"$OUT")"
assert_eq       "fallback 모델=fb"   fb   "$(jq -r '.model' <<<"$OUT")"
assert_eq       "fallback status=ok" ok   "$(jq -r '.status' <<<"$OUT")"

rm -rf "$ROOT"
finish
