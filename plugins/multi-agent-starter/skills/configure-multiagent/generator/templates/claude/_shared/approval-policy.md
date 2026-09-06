# Worker Approval Policy

## 원칙

**모든 worker 호출은 작업별로 명시적 승인 필요** (claude-main 포함 전체 pool 적용).  
`task.md`의 `workers_approved` 리스트에 없으면 호출 금지.

**예외**: Orchestrator의 내부 추론은 worker 호출이 아니므로 승인 불필요. 다만 별도 claude-main worker를 호출해 산출물을 `result.md`로 받는 것은 승인 대상.

## 승인 절차

1. Orchestrator가 worker 필요성 판단 (`_shared/routing.md` 참조)
2. 사용자에게 다음 정보와 함께 승인 요청:
   - 어떤 worker를
   - 무슨 목적으로
   - 예상 호출 횟수 (쿼터 영향 포함)
3. 승인 시 `task.md`의 `workers_approved`에 추가
4. `log.md`에 `[APPROVAL]` 태그로 승인 기록
5. 이후 해당 작업 내에서는 동일 worker 재승인 불필요

## 승인 예외

- **Orchestrator 내부 추론**: worker 호출이 아니므로 승인 불필요.
- **동일 작업 재호출**: `workers_approved`에 이미 있으면 재승인 불필요.
- **검증 실패 후 재시도**: 승인된 worker 범위 내에서 자동 허용.

## 비용·쿼터 가이드라인 (참고)

| Worker | 예상 비용 | 쿼터 부담 |
|--------|---------|----------|
| claude-main | 중간 | Claude API/구독 쿼터 차감 |
| codex-main | 중간 | Codex 호출 쿼터 |
| codex-critic | 낮음-중간 | Codex 호출 쿼터 |
| gemini flash | 낮음 | Gemini 쿼터 |
| gemini pro | 중간-높음 | Gemini 쿼터 |

claude-main이 "내부 추론"과 같은 모델이라도 별도 호출이므로 쿼터·비용 발생.

## 승인 기록 형식 (task.md에 기록)

```yaml
workers_approved:
  - worker: claude-main
    approved_at: <YYYY-MM-DD>      # 승인 당시 날짜로 교체
    purpose: 설계·아키텍처 초안 (strategist)
    approved_by: user
  - worker: codex-main
    approved_at: <YYYY-MM-DD>
    purpose: 설계 기반 대규모 구현·테스트 (engineer)
    approved_by: user
  - worker: codex-critic
    approved_at: <YYYY-MM-DD>
    purpose: 산출물 리뷰·비평 (reviewer)
    approved_by: user
```

외부 repo 쓰기 승인은 항목에 `target_repo`·`write_scope`를 **brief와 같은 값으로** 함께 기록한다 (`gate.sh` G5가 정확 일치를 검사 — 값이 바뀌면 재승인):

```yaml
  - worker: codex-main
    approved_at: <YYYY-MM-DD>
    purpose: 구현 (engineer) — 외부 repo 쓰기
    approved_by: user
    target_repo: /absolute/path/to/repo
    write_scope: "src/**, tests/**"
```

`log.md`의 `[APPROVAL]` 줄에도 같은 worker와 `write_scope` 값을 함께 적는다 (예: `[APPROVAL] codex-main 외부 쓰기 승인 write_scope="src/**, tests/**"`).

날짜 명령어: `date +%Y-%m-%d`
