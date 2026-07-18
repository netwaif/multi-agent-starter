"""v4 runtime — canonical event schema + state machine (V8 확정설계).

이 모듈은 데이터 정의만 담는다(부작용 없음). WAL·reducer·classifier가 여기 상수를 참조한다.
설계 정본: PLUGIN_CUSTOM_DESIGN_V8.md. 표준 라이브러리만 사용.

핵심 불변식(여기서 코드화):
- attempt 하나에 AttemptIntent 정확히 1 · AttemptStarted 최대 1 · terminal 정확히 1.
- UNRESOLVED(in_doubt/orphan_suspected/reconciliation_required)는 terminal이 아니다(A1).
- 모든 final terminal은 quiescence+effect-resolution evidence를 참조해야 한다(A1b).
- 권위 있는 event는 event_type별 유일 trusted writer만 쓴다(A5b).
"""

from __future__ import annotations

SCHEMA_VERSION = "2"

# ── 이벤트 타입 (canonical control-plane) ──────────────────────────────────
class EventType:
    PREFLIGHT_REJECTION = "PreflightRejectionReceipt"
    ATTEMPT_INTENT = "AttemptIntent"                 # = accepted-preflight durable marker (A6)
    ATTEMPT_STARTED = "AttemptStarted"
    ATTEMPT_TERMINAL = "AttemptTerminal"
    ATTEMPT_UNCERTAINTY_OBSERVED = "AttemptUncertaintyObserved"
    ATTEMPT_RECONCILIATION_OBSERVED = "AttemptReconciliationObserved"
    ATTEMPT_RESOLUTION = "AttemptResolution"
    LOGICAL_OPERATION_RESOLUTION = "LogicalOperationResolution"
    OPERATOR_RESOLUTION_OVERRIDE = "OperatorResolutionOverride"

ALL_EVENT_TYPES = frozenset(
    v for k, v in vars(EventType).items() if not k.startswith("_") and isinstance(v, str)
)

# ── A5b writer-authority matrix: event_type → 유일 trusted writer role ──────
# reducer가 event_type × writer_role 불일치를 발견하면 event를 무시하지 않고
# operation을 unresolved/corrupt로 정지한다(V8 A5b).
WRITER_AUTHORITY = {
    EventType.PREFLIGHT_REJECTION: "launcher",
    EventType.ATTEMPT_INTENT: "launcher",
    EventType.ATTEMPT_STARTED: "wrapper",
    EventType.ATTEMPT_TERMINAL: "reducer",
    EventType.ATTEMPT_UNCERTAINTY_OBSERVED: "recovery_scanner",
    EventType.ATTEMPT_RECONCILIATION_OBSERVED: "reconciliation_adapter",
    EventType.ATTEMPT_RESOLUTION: "reducer",             # 또는 승인된 reconciliation authority
    EventType.LOGICAL_OPERATION_RESOLUTION: "reducer",   # policy enforcer/reducer
    EventType.OPERATOR_RESOLUTION_OVERRIDE: "operator",
}
# flavor·worker는 어떤 canonical event도 쓸 수 없다. plan은 submission drop에만.
CONTESTANT_ROLES = frozenset({"flavor", "worker"})
TRUSTED_WRITER_ROLES = frozenset(WRITER_AUTHORITY.values())

# ── attempt 상태 머신 (V8 A1) ──────────────────────────────────────────────
class AttemptState:
    PRECHECK_REJECTED = "PRECHECK_REJECTED"          # terminal, 프로세스 미실행
    PREPARED = "PREPARED"                             # intent durable, spawn 전
    STARTED = "STARTED"
    # final terminals
    FINAL_SUCCEEDED = "FINAL_SUCCEEDED"
    FINAL_FAILED = "FINAL_FAILED"
    FINAL_TIMED_OUT = "FINAL_TIMED_OUT"
    FINAL_CANCELLED = "FINAL_CANCELLED"
    OUTPUT_LIMIT_EXCEEDED = "OUTPUT_LIMIT_EXCEEDED"
    # 비terminal 관측 (A1: reconciliation으로 이어짐)
    UNRESOLVED = "UNRESOLVED"

UNRESOLVED_KINDS = frozenset({"in_doubt", "orphan_suspected", "reconciliation_required"})

FINAL_TERMINAL_STATES = frozenset({
    AttemptState.PRECHECK_REJECTED,
    AttemptState.FINAL_SUCCEEDED,
    AttemptState.FINAL_FAILED,
    AttemptState.FINAL_TIMED_OUT,
    AttemptState.FINAL_CANCELLED,
    AttemptState.OUTPUT_LIMIT_EXCEEDED,
})
# UNRESOLVED는 여기 없다 — terminal이 아니다(A1의 핵심 수정).

# 허용된 상태 전이. (from → {to}). resolution 경로는 UNRESOLVED에서 다시 final로.
ALLOWED_TRANSITIONS = {
    AttemptState.PREPARED: frozenset({
        AttemptState.PRECHECK_REJECTED,   # (안 B에서는 preflight 거부가 별도 event지만 방어적으로 허용)
        AttemptState.FINAL_FAILED,        # spawn_failed (A2 경우1)
        AttemptState.STARTED,
    }),
    AttemptState.STARTED: frozenset({
        AttemptState.FINAL_SUCCEEDED,
        AttemptState.FINAL_FAILED,
        AttemptState.FINAL_TIMED_OUT,
        AttemptState.FINAL_CANCELLED,
        AttemptState.OUTPUT_LIMIT_EXCEEDED,
        AttemptState.UNRESOLVED,
    }),
    AttemptState.UNRESOLVED: frozenset({   # resolution 후 정확히 하나의 final로
        AttemptState.FINAL_SUCCEEDED,
        AttemptState.FINAL_FAILED,
        AttemptState.FINAL_TIMED_OUT,
        AttemptState.FINAL_CANCELLED,
        AttemptState.UNRESOLVED,           # 추가 관측(uncertainty→reconciliation)은 자기루프
    }),
}

def is_terminal(state: str) -> bool:
    return state in FINAL_TERMINAL_STATES

def transition_allowed(src: str, dst: str) -> bool:
    return dst in ALLOWED_TRANSITIONS.get(src, frozenset())

# ── A1b: final terminal 발행 전제 = quiescence + effect resolution ──────────
# 각 final terminal이 발행되려면 아래 evidence 축이 충족돼야 한다. reducer/terminal
# committer가 검증한다. (V8 A1b 상태별 조건표를 기계 판정용으로 코드화.)
#   local_quiescence: process tree 종료 확인 (또는 route가 "no local exec remains" 증명)
#   effect_resolved:  봉인된 effect/delivery 계약 하에 external effect 충분히 resolved
#   output_sealed:    output-drop이 control-plane에 sealed/import 또는 unavailable 분류
FINALITY_REQUIREMENTS = {
    AttemptState.FINAL_SUCCEEDED:     ("local_quiescence", "effect_resolved", "output_sealed"),
    AttemptState.FINAL_FAILED:        ("local_quiescence", "effect_resolved", "output_sealed"),
    AttemptState.FINAL_TIMED_OUT:     ("local_quiescence", "effect_resolved", "output_sealed"),
    AttemptState.FINAL_CANCELLED:     ("local_quiescence", "effect_resolved", "output_sealed"),
    AttemptState.OUTPUT_LIMIT_EXCEEDED: ("local_quiescence",),  # process group 종료 확인
    AttemptState.PRECHECK_REJECTED:   (),                       # 실행 자체가 없었음
}

# ── envelope v2 관측 축 (V8 §1.1). 성공 판정은 outcome.py가 이 값들로 한다. ──
class PreflightStatus:
    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"

class ProcessStatus:
    NOT_STARTED = "not_started"
    EXITED = "exited"
    SIGNALED = "signaled"
    WRAPPER_TIMEOUT = "wrapper_timeout"
    SPAWN_FAILED = "spawn_failed"
    CANCELLED = "cancelled"
    WRAPPER_ERROR = "wrapper_error"

class OutputStatus:
    NOT_PRODUCED = "not_produced"   # 실행 자체가 없었음(≠ output_missing)
    PRESENT = "present"
    OUTPUT_MISSING = "output_missing"
    CAPTURE_FAILED = "capture_failed"

class CaptureStatus:
    OK = "ok"
    TRUNCATED = "truncated"
    LIMIT_EXCEEDED = "limit_exceeded"
    FAILED = "failed"

class ResultContractStatus:
    SATISFIED = "satisfied"
    UNSATISFIED = "unsatisfied"
    NOT_EVALUATED = "not_evaluated"

class ClassificationStatus:
    NOT_NEEDED = "not_needed"          # 구조화 upstream success 신호가 있을 때만(V8 A5b/§5)
    CLASSIFIED = "classified"
    UNSUPPORTED_VERSION = "unsupported_version"
    UNCLASSIFIED = "unclassified"

class FailureClass:
    NONE = "none"
    PERMISSION = "permission"
    AUTH = "auth"
    QUOTA = "quota"
    RATE_LIMITED = "rate_limited"
    TRANSPORT = "transport"
    UNKNOWN = "unknown"

# effect/delivery 계약 (V8 A7 §4) — binary replay_safety 대체.
class EffectClass:
    NONE = "none"
    LOCAL_CONTENT_ADDRESSED = "local_content_addressed"
    IDEMPOTENT_REMOTE = "idempotent_remote"
    COMPENSATABLE = "compensatable"
    NON_IDEMPOTENT = "non_idempotent"
    UNKNOWN = "unknown"

class DeliverySemantics:
    AT_MOST_ONCE = "at_most_once"
    AT_LEAST_ONCE = "at_least_once"
    EFFECTIVELY_ONCE = "effectively_once_with_idempotency_key"
    MANUAL_RECONCILIATION = "manual_reconciliation"

# 보수적 합성(V8 A7): 가장 위험한 dimension이 자동 retry 가능성을 결정.
# 낮을수록 안전. non_idempotent/unknown이면 자동 재시도 금지.
EFFECT_CLASS_RISK = {
    EffectClass.NONE: 0,
    EffectClass.LOCAL_CONTENT_ADDRESSED: 1,
    EffectClass.IDEMPOTENT_REMOTE: 2,
    EffectClass.COMPENSATABLE: 3,
    EffectClass.NON_IDEMPOTENT: 4,
    EffectClass.UNKNOWN: 5,
}

def most_conservative_effect(classes) -> str:
    """여러 effect_class 중 가장 위험한 것을 반환(V8 A7 합성 규칙)."""
    worst, worst_risk = EffectClass.UNKNOWN, -1
    for c in classes:
        r = EFFECT_CLASS_RISK.get(c, EFFECT_CLASS_RISK[EffectClass.UNKNOWN])
        if r > worst_risk:
            worst, worst_risk = c, r
    return worst
