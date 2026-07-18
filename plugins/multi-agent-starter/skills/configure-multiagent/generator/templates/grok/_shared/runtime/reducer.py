"""v4 runtime W9 — event reducer + mandatory recovery gate (V8 A1/A5b/A6).

설계 정본: PLUGIN_CUSTOM_DESIGN_V8.md ("모든 신규 실행 전 필수: events 로드→검증→reduce→
unresolved active 탐지→eligibility→그 뒤 새 intent · 9 금지상태 · projection 무권위").
표준 라이브러리만. reduce()는 순수(event dict 리스트 → 상태). 파일 로드는 얇은 adapter.

핵심 불변식(여기서 코드화):
- **A6 mandatory recovery gate**: 어떤 새 AttemptIntent도 발행 전에 operation의 canonical event를
  로드·검증·reduce해서 미해결(occupying=비terminal) 시도가 없음을 확인해야 한다.
- **A5b writer-authority**: event_type × writer_role가 schema.WRITER_AUTHORITY와 불일치하거나
  contestant(flavor/worker)가 canonical event를 쓰면 → event를 **무시하지 않고** operation을
  corrupt로 정지(reducer가 판정, projection이 아니라 event가 권위).
- **A1 상태모델**: UNRESOLVED는 terminal이 아니다. occupying 시도가 있으면 새 실행 불가.
- **active ≤ 1 fencing**: 한 operation에 occupying 시도가 2개 이상이면 corrupt(F8).
- **A1b finality evidence**: 모든 final terminal event는 FINALITY_REQUIREMENTS의 evidence 축을
  모두 참조해야 한다. 누락 시 corrupt(F9).

event dict 계약(로더가 파일에서 파싱해 넘김; 여기선 해석만):
  { "event_type": <schema.EventType 값>,
    "writer_role": <인증된 writer role — payload가 아니라 인증 결과>,
    "attempt_id": <str; operation-level event는 없음>,
    "logical_operation_id": <str>,
    # ATTEMPT_TERMINAL 전용:
    "terminal_state": <schema.FINAL_TERMINAL_STATES 중 하나>,
    "finality_evidence": [<'local_quiescence'|'effect_resolved'|'output_sealed' ...>],
  }
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Sequence

import schema as s

# ── 9 금지조건 (reducer가 corrupt로 정지) ───────────────────────────────────
F1_CONTESTANT_WRITER = "F1_contestant_wrote_canonical_event"      # flavor/worker가 canonical write
F2_WRONG_TRUSTED_WRITER = "F2_wrong_trusted_writer_for_event_type"
F3_DUPLICATE_INTENT = "F3_duplicate_attempt_intent"
F4_DUPLICATE_TERMINAL = "F4_duplicate_attempt_terminal"          # A1b: terminal 재발행 금지
F5_STARTED_WITHOUT_INTENT = "F5_started_without_intent"
F6_TERMINAL_WITHOUT_INTENT = "F6_terminal_without_intent"
F7_ILLEGAL_TRANSITION = "F7_illegal_state_transition"
F8_MULTIPLE_ACTIVE = "F8_multiple_active_attempts"               # active≤1 fencing 위반
F9_FINAL_MISSING_EVIDENCE = "F9_final_terminal_missing_evidence" # A1b evidence 누락

FORBIDDEN_CODES = frozenset({
    F1_CONTESTANT_WRITER, F2_WRONG_TRUSTED_WRITER, F3_DUPLICATE_INTENT,
    F4_DUPLICATE_TERMINAL, F5_STARTED_WITHOUT_INTENT, F6_TERMINAL_WITHOUT_INTENT,
    F7_ILLEGAL_TRANSITION, F8_MULTIPLE_ACTIVE, F9_FINAL_MISSING_EVIDENCE,
})

# operation-level(특정 attempt에 속하지 않는) event 타입.
_OPERATION_LEVEL_EVENTS = frozenset({
    s.EventType.LOGICAL_OPERATION_RESOLUTION,
    s.EventType.OPERATOR_RESOLUTION_OVERRIDE,
})

# 한 attempt 안에서 event 처리 순서(인과). 파일 나열 순서는 인과가 아니므로 rank로 정렬.
# ★ uncertainty(2) < reconciliation(3): reconciliation 관측은 state==UNRESOLVED를 요구하는데
#   그 상태를 만드는 건 uncertainty다. 둘을 같은 rank로 두면 event_type 문자열 tiebreak가
#   "Reconciliation" < "Uncertainty"로 뒤집어 F7 위양성을 낸다(적대검증에서 발견).
_EVENT_RANK = {
    s.EventType.PREFLIGHT_REJECTION: 0,
    s.EventType.ATTEMPT_INTENT: 0,
    s.EventType.ATTEMPT_STARTED: 1,
    s.EventType.ATTEMPT_UNCERTAINTY_OBSERVED: 2,
    s.EventType.ATTEMPT_RECONCILIATION_OBSERVED: 3,
    s.EventType.ATTEMPT_TERMINAL: 4,
    s.EventType.ATTEMPT_RESOLUTION: 5,
}


class ReducerError(ValueError):
    """reduce 입력 자체가 형식 위반(event dict 필수 키 누락 등)."""


@dataclass
class AttemptView:
    attempt_id: str
    state: str                       # schema.AttemptState 값
    intents: int = 0
    terminals: int = 0

    @property
    def occupying(self) -> bool:
        """비terminal(진행중/미해결) — operation을 점유해 새 실행을 막는다."""
        return self.state not in s.FINAL_TERMINAL_STATES


@dataclass
class OperationState:
    logical_operation_id: str
    attempts: dict = field(default_factory=dict)     # attempt_id -> AttemptView
    corrupt: bool = False
    corrupt_reasons: list = field(default_factory=list)   # FORBIDDEN_CODES 부분집합
    operation_resolved: bool = False                 # LogicalOperationResolution 관측

    @property
    def occupying_attempt_ids(self) -> list:
        return [a.attempt_id for a in self.attempts.values() if a.occupying]

    def _flag(self, code: str) -> None:
        self.corrupt = True
        if code not in self.corrupt_reasons:
            self.corrupt_reasons.append(code)


def _require(ev: dict, key: str) -> object:
    if key not in ev:
        raise ReducerError(f"event에 필수 키 없음: {key!r} ({ev.get('event_type')})")
    return ev[key]


def _sort_key(ev: dict):
    et = ev.get("event_type")
    return (ev.get("attempt_id", ""), _EVENT_RANK.get(et, 9), et or "")


def reduce(events: Sequence[dict], logical_operation_id: str) -> OperationState:
    """canonical event 리스트를 operation 상태로 축약. 순수 함수(파일 IO 없음).

    9 금지조건 중 하나라도 걸리면 corrupt=True + corrupt_reasons에 코드 기록(정지 신호).
    projection이 아니라 이 reduce 결과가 admission의 권위다.
    """
    st = OperationState(logical_operation_id=logical_operation_id)

    for ev in sorted(events, key=_sort_key):
        et = _require(ev, "event_type")
        if et not in s.ALL_EVENT_TYPES:
            raise ReducerError(f"알 수 없는 event_type: {et!r}")
        writer = _require(ev, "writer_role")

        # ── A5b writer-authority: contestant 금지 + event_type별 유일 trusted writer ──
        if writer in s.CONTESTANT_ROLES:
            st._flag(F1_CONTESTANT_WRITER); continue
        if s.WRITER_AUTHORITY.get(et) != writer:
            st._flag(F2_WRONG_TRUSTED_WRITER); continue

        if et in _OPERATION_LEVEL_EVENTS:
            if et == s.EventType.LOGICAL_OPERATION_RESOLUTION:
                st.operation_resolved = True
            continue

        aid = _require(ev, "attempt_id")
        av = st.attempts.get(aid)
        if av is None:
            av = AttemptView(attempt_id=aid, state="<none>")
            st.attempts[aid] = av

        if et == s.EventType.PREFLIGHT_REJECTION:
            av.state = s.AttemptState.PRECHECK_REJECTED

        elif et == s.EventType.ATTEMPT_INTENT:
            av.intents += 1
            if av.intents > 1:
                st._flag(F3_DUPLICATE_INTENT); continue
            av.state = s.AttemptState.PREPARED

        elif et == s.EventType.ATTEMPT_STARTED:
            if av.intents == 0:
                st._flag(F5_STARTED_WITHOUT_INTENT); continue
            if not s.transition_allowed(av.state, s.AttemptState.STARTED):
                st._flag(F7_ILLEGAL_TRANSITION); continue
            av.state = s.AttemptState.STARTED

        elif et == s.EventType.ATTEMPT_UNCERTAINTY_OBSERVED:
            if not s.transition_allowed(av.state, s.AttemptState.UNRESOLVED):
                st._flag(F7_ILLEGAL_TRANSITION); continue
            av.state = s.AttemptState.UNRESOLVED

        elif et == s.EventType.ATTEMPT_RECONCILIATION_OBSERVED:
            # 관측 기록: UNRESOLVED 자기루프(상태 변화 없음). 비UNRESOLVED에서 오면 불법.
            if av.state != s.AttemptState.UNRESOLVED:
                st._flag(F7_ILLEGAL_TRANSITION); continue

        elif et == s.EventType.ATTEMPT_TERMINAL:
            if av.intents == 0:
                st._flag(F6_TERMINAL_WITHOUT_INTENT); continue
            av.terminals += 1
            if av.terminals > 1:
                st._flag(F4_DUPLICATE_TERMINAL); continue
            term = _require(ev, "terminal_state")
            if term not in s.FINAL_TERMINAL_STATES:
                st._flag(F7_ILLEGAL_TRANSITION); continue
            if not s.transition_allowed(av.state, term):
                st._flag(F7_ILLEGAL_TRANSITION); continue
            # A1b: final terminal은 요구 evidence 축을 모두 참조해야 한다.
            required = set(s.FINALITY_REQUIREMENTS.get(term, ()))
            have = set(ev.get("finality_evidence", []) or [])
            if not required.issubset(have):
                st._flag(F9_FINAL_MISSING_EVIDENCE); continue
            av.state = term

        elif et == s.EventType.ATTEMPT_RESOLUTION:
            # UNRESOLVED를 정확히 하나의 final로 해소. terminal_state 필수.
            if not s.transition_allowed(av.state, ev.get("terminal_state", "")):
                st._flag(F7_ILLEGAL_TRANSITION); continue
            term = ev["terminal_state"]
            required = set(s.FINALITY_REQUIREMENTS.get(term, ()))
            have = set(ev.get("finality_evidence", []) or [])
            if not required.issubset(have):
                st._flag(F9_FINAL_MISSING_EVIDENCE); continue
            av.state = term

    # ── active ≤ 1 fencing (operation 전체) ──
    if len(st.occupying_attempt_ids) > 1:
        st._flag(F8_MULTIPLE_ACTIVE)

    return st


# ── mandatory recovery gate (A6) ────────────────────────────────────────────
@dataclass
class AdmissionDecision:
    admissible: bool
    reason: str

    def __bool__(self) -> bool:
        return self.admissible


def admit_new_intent(
    state: OperationState,
    *,
    retry_cap: int,
    next_attempt_number: int,
) -> AdmissionDecision:
    """새 AttemptIntent 발행 가부(A6 recovery gate). reduce() 결과에만 근거한다.

    거부 조건(우선순위 순):
    - operation corrupt → 거부(사람/reconciliation 개입 필요).
    - occupying(비terminal) 시도 존재 → 거부(먼저 해소해야).
    - operation_resolved(논리적으로 종료) → 거부(closed operation 재개방 금지).
    - next_attempt_number > retry_cap → 거부(retry cap 소진).
    """
    if state.corrupt:
        return AdmissionDecision(False, f"operation corrupt: {','.join(state.corrupt_reasons)}")
    occ = state.occupying_attempt_ids
    if occ:
        return AdmissionDecision(False, f"미해결 occupying 시도 존재: {occ}")
    if state.operation_resolved:
        return AdmissionDecision(False, "operation이 이미 resolved(재개방 금지)")
    if next_attempt_number > retry_cap:
        return AdmissionDecision(False, f"retry cap {retry_cap} 소진(다음 #{next_attempt_number})")
    return AdmissionDecision(True, "admissible")


__all__ = [
    "reduce", "admit_new_intent", "OperationState", "AttemptView", "AdmissionDecision",
    "ReducerError", "FORBIDDEN_CODES",
    "F1_CONTESTANT_WRITER", "F2_WRONG_TRUSTED_WRITER", "F3_DUPLICATE_INTENT",
    "F4_DUPLICATE_TERMINAL", "F5_STARTED_WITHOUT_INTENT", "F6_TERMINAL_WITHOUT_INTENT",
    "F7_ILLEGAL_TRANSITION", "F8_MULTIPLE_ACTIVE", "F9_FINAL_MISSING_EVIDENCE",
]
