#!/usr/bin/env bash
# reentry-check.sh — 작업 재진입 정합 검사 (orchestrator-rules §3 "status↔log 불일치" 기계화). 보고만.
# 사용: bash _shared/reentry-check.sh tasks/<task>
# 출력: status·log 요약 + 역할별 표(brief/result/승인/마지막 log 태그). 불일치 있으면 MISMATCH 나열 후 exit 11.
#   정정은 하지 않는다 — 정정 판단·[DECISION] 기록은 오케스트레이터.
set -u

TDIR="${1:-}"
[ -n "$TDIR" ] && [ -d "$TDIR" ] || { echo "usage: reentry-check.sh <task-dir>" >&2; exit 64; }
TASKMD="$TDIR/task.md"; LOGMD="$TDIR/log.md"
[ -f "$TASKMD" ] || { echo "reentry: task.md 없음: $TASKMD" >&2; exit 11; }

STATUS="$(grep -m1 -E '^status:' "$TASKMD" | sed -E 's/^status:[[:space:]]*//; s/[[:space:]]+#.*$//; s/[[:space:]]+$//')"
# log 항목의 ACTION 태그 = "[timestamp] [TAG]" 의 두 번째 대괄호만 (본문에 인용된 [TAG]는 무시)
tags() { [ -f "$LOGMD" ] && sed -nE 's/^\[[^]]*\][[:space:]]*\[([A-Z_]+)\].*/\1/p' "$LOGMD"; }
has_tag() { tags | grep -qx "$1"; }
MIS=()

case "$STATUS" in
  pending|in_progress|reviewing|done|handoff|waiting_*) ;;
  *) MIS+=("status 값이 허용 집합 밖: '${STATUS:-<없음>}'");;
esac
CHK=()
[ "$STATUS" = done ] && ! has_tag COMPLETE && MIS+=("status=done 인데 log에 [COMPLETE] 없음")
# [COMPLETE]가 마지막 항목인데 status≠done → 불일치. 뒤에 항목이 있으면 정상 재개(§3: 재개 시 [DECISION] 기록)로 본다
if has_tag COMPLETE && [ "$STATUS" != done ]; then
  last_tag="$(tags | tail -1)"
  [ "$last_tag" = "COMPLETE" ] && MIS+=("log 마지막이 [COMPLETE]인데 status=$STATUS")
fi
[ "$STATUS" = pending ] && has_tag WORKER_CALL && MIS+=("status=pending 인데 log에 [WORKER_CALL] 있음")
case "$STATUS" in waiting_*)
  r="${STATUS#waiting_}"
  [ -f "$TDIR/workers/$r/result.md" ] && CHK+=("status=$STATUS 인데 workers/$r/result.md 존재 — 이전 결과(재호출)면 result-fix.md 등으로 보존됐는지, 응답이 이미 도착한 것인지 확인");;
esac

echo "reentry — $TDIR"
echo " status: ${STATUS:-<없음>}"
if [ -f "$LOGMD" ]; then
  echo " log 마지막: $(grep -E '^\[' "$LOGMD" | tail -1 | cut -c1-120)"
else
  echo " log.md 없음"; MIS+=("log.md 없음")
fi
if [ -d "$TDIR/workers" ]; then
  printf ' %-14s %-6s %-7s %-6s %s\n' role brief result approv last_log
  for d in "$TDIR"/workers/*/; do
    [ -d "$d" ] || continue
    r="$(basename "$d")"
    b=$([ -f "$d/brief.md" ] && echo Y || echo -)
    s=$([ -f "$d/result.md" ] && echo Y || echo -)
    a=$(awk '/^workers_approved:/{f=1;next} f&&(/^planned_workers:/||/^```/){exit} f' "$TASKMD" | grep -q "worker:[[:space:]]*$r[[:space:]]*$" && echo Y || echo -)
    l=$([ -f "$LOGMD" ] && grep -F -- "$r" "$LOGMD" | sed -nE 's/^\[[^]]*\][[:space:]]*\[([A-Z_]+)\].*/[\1]/p' | tail -1 || true)
    printf ' %-14s %-6s %-7s %-6s %s\n' "$r" "$b" "$s" "$a" "${l:--}"
  done
fi
if [ "${#CHK[@]}" -gt 0 ]; then echo " CHECK (${#CHK[@]}) — 판단 필요:"; printf '  - %s\n' "${CHK[@]}"; fi
if [ "${#MIS[@]}" -gt 0 ]; then
  echo " MISMATCH (${#MIS[@]}) — log(append-only 정본) 기준으로 status 정정 후 [DECISION] 기록:"
  printf '  - %s\n' "${MIS[@]}"; exit 11
fi
echo " OK — status↔log 정합"
