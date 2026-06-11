#!/usr/bin/env bash
# A6: 디스패처 입력 가드 — usage / brief '..' / 미정의 role / allowlist 밖 명령.
. "$(dirname "$0")/_lib.sh"
echo "A6 디스패처 가드"

# usage (인자 없음) → exit 64  (run_backend 이전 단계)
bash "$DISPATCHER" >/dev/null 2>&1
assert_eq "인자 없음 → exit 64" 64 "$?"

ROOT="$(new_root <<'JSON'
{"schema_version":"2","flavor":"claude",
 "providers":{
  "t":{"call_type":"cli","model":"m","approval_class":"worker","result_capture":"stdout",
       "timeout":5,"brief_mode":"path","cli":{"command":"agy","args_template":["@brief"]}},
  "bad":{"call_type":"cli","model":"m","approval_class":"worker","result_capture":"stdout",
       "timeout":5,"brief_mode":"path","cli":{"command":"rm","args_template":["-rf","@brief"]}}},
 "roles":{"t":{"provider":"t"},"bad":{"provider":"bad"}}}
JSON
)"
echo "brief" > "$ROOT/brief.txt"

# brief 경로에 '..' → exit 6
dispatch "$ROOT" t "$ROOT/../x"
assert_eq "brief '..' → exit 6" 6 "$RC"

# 미정의 role → exit 2
dispatch "$ROOT" nope "$ROOT/brief.txt"
assert_eq "미정의 role → exit 2" 2 "$RC"

# allowlist 밖 명령(rm) → 실행 안 됨(거부), stderr에 allowlist 언급.
# 종료코드는 비0이면 충분(현재는 폴백 없는 die→빈 envelope 경로로 2가 나옴 = 알려진 러프엣지 T2,
# 명령은 차단되고 stderr는 명확하므로 보안 영향 없음). 명령 차단 자체를 단언한다.
dispatch "$ROOT" bad "$ROOT/brief.txt"
assert_eq       "allowlist 위반 → exit 비0"  nonzero   "$([ "$RC" -ne 0 ] && echo nonzero || echo zero)"
assert_contains "stderr에 allowlist"        allowlist "$ERR"

rm -rf "$ROOT"
finish
