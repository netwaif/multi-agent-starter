#!/usr/bin/env bash
# gemini_api.sh — gemini worker의 API 폴백 어댑터(최악 대비 슬롯).
# 사용: gemini_api.sh <brief-file>   (call_worker.sh가 api 폴백 시 호출)
# stdout = 모델 응답 텍스트, exit 0=성공.
#
# 상태(2026-06-02): 슬롯만 정의됨(spike S3 미완). 실제 엔드포인트·인증 경로 미확정.
# 활성화하려면: 아래 ENDPOINT/요청 형식을 확정한 Gemini REST 호출로 교체하고
# GEMINI_API_KEY(또는 확정된 env)를 설정. 그 전까지는 명확히 실패한다(무한대기·오작동 방지).
set -euo pipefail

BRIEF="${1:?usage: gemini_api.sh <brief-file>}"
[ -f "$BRIEF" ] || { echo "gemini_api: brief 없음: $BRIEF" >&2; exit 6; }
: "${GEMINI_API_KEY:?gemini_api: GEMINI_API_KEY 필요}"

echo "gemini_api: API 백엔드 미구성(slot only, spike S3 미완). \
backends.json의 gemini cli(agy) 경로를 사용하거나, 이 스크립트를 실제 Gemini REST 호출로 교체하라." >&2
exit 4
