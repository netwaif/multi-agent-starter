# [작업명]

## 메타

```yaml
status: pending
# 가능한 값:
#   pending          작업 정의 완료, 시작 전
#   in_progress      orchestrator 작업 진행 중
#   waiting_<role>   특정 worker 응답 대기 (예: waiting_claude-critic)
#   reviewing        worker 결과 검증 중
#   done             완료
created: <YYYY-MM-DD>
updated: <YYYY-MM-DD>
priority: medium  # high | medium | low
```

## Goal

한 문장으로. 무엇을 완료 상태로 볼 것인가.

## Constraints

- 제약 1
- 제약 2

## Acceptance Criteria

- [ ] 기준 1
- [ ] 기준 2

## Worker Plan

```yaml
# 모든 worker는 사용 전 승인 필요. 비어있으면 호출 금지.
workers_approved: []
# 승인 예시:
# - worker: claude-critic
#   approved_at: <YYYY-MM-DD>
#   purpose: Codex 산출물 리뷰·비평
#   approved_by: user

# routing.md 참조하여 최소 set만 명시. 기본은 빈 배열.
planned_workers: []
# 예시:
# - role: codex-main
#   purpose:
# - role: claude-critic
#   purpose:
# - role: gemini
#   purpose:
```

## Context Snapshot

<!-- context.md에서 핵심만 요약. 1500자(한글)/300단어(영문) 이하. -->
<!-- 전체 배경은 sources/에 두고 경로로 참조: sources/background.md -->

## Notes

<!-- 기타 orchestrator 판단에 필요한 메모 -->
