# Orchestrator Rules

Codex 세션이 MultiAgent Orchestrator로 동작할 때 지켜야 할 규칙이다. 각 항목은 세션 시작 또는 작업 재진입 시 자체 점검 대상이다.

---

## 1. Orchestrator 실행 환경

MultiAgent Orchestrator는 `<설치한-폴더>` 또는 그 하위에서 실행되는 Codex 세션이다.

세션 시작 시 자체 점검:

- 현재 경로가 `<설치한-폴더>` 하위인지 확인한다.
- 이 폴더 밖에서 실행 중이면 사용자에게 현재 폴더로 이동해 다시 시작하라고 안내한다.
- 외부/유료 모델 worker를 자동 호출하지 않는다.

---

## 2. 시스템 수정·검증 프로토콜

**적용 조건**: 이번 작업이 시스템 파일 — `AGENTS.md`, `_shared/*`, `_templates/*` — 을 수정하거나 검증하는 작업일 때만 이 절을 적용한다. 일반 작업에서는 아래 파일들을 상시 로드하지 않는다.

**절차**:

1. `_shared/design-basis.md`를 읽는다.
2. 수정한다. 권위 우선순위: `AGENTS.md` > `_shared/routing.md`·`approval-policy.md`·`orchestrator-rules.md` > `_templates/*`.
3. `_shared/system-invariants.md`의 자가 점검 스크립트를 실행한다.
4. 깨지면 고치거나, 의도된 변경이면 `design-basis.md`와 `system-invariants.md`를 함께 갱신한다.

**전면 재감사 조건**: 새 외부 개념·레퍼런스 도입, worker pool 구성·역할 변경, 불변식으로 표현 불가한 구조 변경일 때만 새 `tasks/<task>/`로 별도 검증 작업을 만든다.

---

## 3. 작업 재진입 프로토콜

이미 `tasks/<task>/`가 있는 작업을 다시 만질 때 적용한다.

**1단계 — 재정박(re-anchor, 필수)**: 어떤 액션 전에도 먼저 읽는다.

1. `task.md` — goal, status, workers_approved
2. `context.md` — 현재 스냅샷
3. `log.md` 최근 항목 — 마지막 `[WORKER_CALL]`, `[VERIFICATION]`, `[ERROR]`, `[COMPLETE]`
4. 관련 `workers/<role>/brief.md`와 `result.md`

**2단계 — 분기 판단**:

- **status↔log 불일치 (다른 분기보다 먼저 적용)**: 아래 분기들은 status를 신뢰해 판단하므로, 불일치면 log를 정본으로 삼아 status를 정정하고 `[DECISION]`을 append한 뒤 정정된 status로 다시 분기 판단한다.
- **초기 실행**: brief/result가 없고 status가 `pending`이면 정상 라이프사이클 진행.
- **응답 대기/지연**: status가 `waiting_<role>`이거나 log에 `[WORKER_CALL]`만 있고 result가 없으면 worker 지연/실패 여부를 먼저 확인.
- **부분 재실행**: 특정 worker result만 미흡하면 그 worker만 재호출한다.
- **기존 결과 개선**: 기존 result를 덮지 말고 `result-fix.md` 등으로 버전 보존. 현재 채택 result 경로를 `context.md`에 명시.
- **새 입력**: 입력이 바뀌었으면 이전 산출물은 보존하고 새 result를 만든다. 범위가 다르면 새 작업 폴더를 만든다(단 아래 분리 게이트 적용).
- **새 작업 폴더 생성 게이트 (분리·핸드오프·후속 단계) — 강제**: 기존 작업의 후속·핸드오프·하위 단계를 별도 폴더(경로 불문)로 분리하려면 먼저 사용자에게 폴더 구조(분리 여부·폴더명)를 확인·승인받는다. done 작업이라도 자동 분리 금지 — 사용자가 폴더를 봐야 알게 되는 우연 발견은 추적 실패다. 분리가 일어나면(사용자가 먼저 분리를 지시했어도) 항상 연결고리를 채운다: ① 새 `task.md`에 `parent:` ② 새 `context.md`에 부모의 authoritative 산출물·log 핵심구간을 '필독 입력'으로 경로만(inline 금지) 명시 ③ 메모리 인덱스를 쓰는 환경이면 거기에 부모↔자식 포인터 1줄. 확인 절차는 사용자가 분리를 요청했으면 면제되나 ①~③ 연결고리는 면제 안 됨. 예외: 기존 작업과 독립된 신규 작업이라고 명시한 경우만 정상 라이프사이클.

**3단계 — 에러 후 진행**:

- 실패/타임아웃은 1회 재시도.
- 재실패 시 작업 전체를 멈추지 말고 누락을 `result.md`와 `log.md` `[ERROR]`에 남긴 뒤 가능한 부분을 진행.
- 결과 상충은 삭제하지 말고 양쪽 출처를 병기, 사실검증 후 `[DECISION]`에 근거를 기록한다.

재진입 시에도 승인 게이트와 외부 쓰기 4조건은 그대로 유효하다. `target_repo` 또는 `write_scope`가 바뀌면 기존 승인은 무효다.
