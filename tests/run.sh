#!/usr/bin/env bash
# v2 자동화 테스트 러너 — 결정적/오프라인 테스트만 (외부·유료 모델 호출 없음).
# 종료코드 0 = 전부 PASS, 비0 = 하나라도 FAIL.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fail=0

# Windows 네이티브 python3가 /d/... MSYS 경로를 인식하지 못하므로 Windows 경로로 변환
_to_native() { command -v cygpath >/dev/null 2>&1 && cygpath -w "$1" 2>/dev/null || echo "$1"; }

echo "== python tests =="
for t in "$HERE"/test_*.py; do
  [ -f "$t" ] || continue
  echo "-- $(basename "$t")"
  python3 "$(_to_native "$t")" || fail=1
done

echo
echo "== dispatcher tests =="
for t in "$HERE"/dispatcher/test_*.sh; do
  [ -f "$t" ] || continue
  echo "-- $(basename "$t")"
  bash "$t" || fail=1
done

echo
if [ "$fail" -eq 0 ]; then echo "ALL TESTS PASS"; else echo "SOME TESTS FAILED"; fi
exit "$fail"
