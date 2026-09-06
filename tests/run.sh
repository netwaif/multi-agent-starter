#!/usr/bin/env bash
# v2 자동화 테스트 러너 — 결정적/오프라인 테스트만 (외부·유료 모델 호출 없음).
# 종료코드 0 = 전부 PASS, 비0 = 하나라도 FAIL.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fail=0

echo "== python tests =="
for t in "$HERE"/test_*.py; do
  [ -f "$t" ] || continue
  echo "-- $(basename "$t")"
  python3 "$t" || fail=1
done

echo
echo "== dispatcher tests =="
for t in "$HERE"/dispatcher/test_*.sh; do
  [ -f "$t" ] || continue
  echo "-- $(basename "$t")"
  bash "$t" || fail=1
done

echo "== script tests =="
for t in "$HERE"/scripts/test_*.sh; do
  [ -f "$t" ] || continue
  echo "-- $(basename "$t")"
  bash "$t" || fail=1
done

echo
if [ "$fail" -eq 0 ]; then echo "ALL TESTS PASS"; else echo "SOME TESTS FAILED"; fi
exit "$fail"
