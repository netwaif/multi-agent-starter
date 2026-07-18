"""W9 게이트 — event reducer + mandatory recovery gate (V8 A1/A5b/A6, 9 금지조건).

하우스 컨벤션: pytest 비의존, 자체 러너(__main__). 예외 기대는 _raises() 헬퍼로.
"""
import sys, pathlib
_GEN = pathlib.Path(__file__).resolve().parents[2] / \
    "plugins/multi-agent-starter/skills/configure-multiagent/generator/templates/claude/_shared/runtime"
sys.path.insert(0, str(_GEN))
import schema as s
import reducer as r


def _raises(exc, fn, *a, **kw):
    try:
        fn(*a, **kw)
    except exc:
        return True
    return False


OP = "op-1"
A1 = "op-1#a1"
FULL_EV = ["local_quiescence", "effect_resolved", "output_sealed"]

def _ev(event_type, writer, attempt_id=A1, **extra):
    d = {"event_type": event_type, "writer_role": writer,
         "attempt_id": attempt_id, "logical_operation_id": OP}
    d.update(extra)
    return d

def _intent(aid=A1):   return _ev(s.EventType.ATTEMPT_INTENT, "launcher", aid)
def _started(aid=A1):  return _ev(s.EventType.ATTEMPT_STARTED, "wrapper", aid)
def _term_ok(aid=A1):  return _ev(s.EventType.ATTEMPT_TERMINAL, "reducer", aid,
                                  terminal_state=s.AttemptState.FINAL_SUCCEEDED, finality_evidence=FULL_EV)


# ── happy path ──────────────────────────────────────────────────────────────
def test_happy_path_not_occupying():
    st = r.reduce([_intent(), _started(), _term_ok()], OP)
    assert not st.corrupt
    assert st.attempts[A1].state == s.AttemptState.FINAL_SUCCEEDED
    assert st.occupying_attempt_ids == []

def test_file_order_independent():
    # 파일 나열 순서가 뒤섞여도 rank 정렬로 인과 복원.
    st = r.reduce([_term_ok(), _intent(), _started()], OP)
    assert not st.corrupt
    assert st.attempts[A1].state == s.AttemptState.FINAL_SUCCEEDED


# ── 9 금지조건 ───────────────────────────────────────────────────────────────
def test_F1_contestant_writer():
    st = r.reduce([_ev(s.EventType.ATTEMPT_TERMINAL, "flavor", terminal_state=s.AttemptState.FINAL_SUCCEEDED,
                       finality_evidence=FULL_EV)], OP)
    assert st.corrupt and r.F1_CONTESTANT_WRITER in st.corrupt_reasons

def test_F2_wrong_trusted_writer():
    # launcher가 AttemptTerminal을 씀(정당 writer=reducer)
    st = r.reduce([_intent(), _started(),
                   _ev(s.EventType.ATTEMPT_TERMINAL, "launcher",
                       terminal_state=s.AttemptState.FINAL_SUCCEEDED, finality_evidence=FULL_EV)], OP)
    assert st.corrupt and r.F2_WRONG_TRUSTED_WRITER in st.corrupt_reasons

def test_F3_duplicate_intent():
    st = r.reduce([_intent(), _intent()], OP)
    assert st.corrupt and r.F3_DUPLICATE_INTENT in st.corrupt_reasons

def test_F4_duplicate_terminal():
    st = r.reduce([_intent(), _started(), _term_ok(), _term_ok()], OP)
    assert st.corrupt and r.F4_DUPLICATE_TERMINAL in st.corrupt_reasons

def test_F5_started_without_intent():
    st = r.reduce([_started()], OP)
    assert st.corrupt and r.F5_STARTED_WITHOUT_INTENT in st.corrupt_reasons

def test_F6_terminal_without_intent():
    st = r.reduce([_term_ok()], OP)
    assert st.corrupt and r.F6_TERMINAL_WITHOUT_INTENT in st.corrupt_reasons

def test_F7_illegal_transition():
    # PREPARED에서 바로 FINAL_SUCCEEDED terminal → 불법(STARTED 거쳐야)
    st = r.reduce([_intent(),
                   _ev(s.EventType.ATTEMPT_TERMINAL, "reducer",
                       terminal_state=s.AttemptState.FINAL_SUCCEEDED, finality_evidence=FULL_EV)], OP)
    assert st.corrupt and r.F7_ILLEGAL_TRANSITION in st.corrupt_reasons

def test_F8_multiple_active():
    # 두 시도가 동시에 occupying(PREPARED) → active≤1 위반
    st = r.reduce([_intent("op-1#a1"), _intent("op-1#a2")], OP)
    assert st.corrupt and r.F8_MULTIPLE_ACTIVE in st.corrupt_reasons

def test_F9_final_missing_evidence():
    st = r.reduce([_intent(), _started(),
                   _ev(s.EventType.ATTEMPT_TERMINAL, "reducer",
                       terminal_state=s.AttemptState.FINAL_SUCCEEDED,
                       finality_evidence=["local_quiescence"])], OP)  # effect_resolved/output_sealed 누락
    assert st.corrupt and r.F9_FINAL_MISSING_EVIDENCE in st.corrupt_reasons


# ── spawn_failed / preflight 경로 (합법 terminal) ───────────────────────────
def test_prepared_to_failed_allowed():
    # A2 경우1: intent 후 spawn 실패 → PREPARED→FINAL_FAILED 합법
    st = r.reduce([_intent(),
                   _ev(s.EventType.ATTEMPT_TERMINAL, "reducer",
                       terminal_state=s.AttemptState.FINAL_FAILED, finality_evidence=FULL_EV)], OP)
    assert not st.corrupt and st.attempts[A1].state == s.AttemptState.FINAL_FAILED

def test_preflight_rejection_terminal_no_block():
    st = r.reduce([_ev(s.EventType.PREFLIGHT_REJECTION, "launcher")], OP)
    assert not st.corrupt
    assert st.attempts[A1].state == s.AttemptState.PRECHECK_REJECTED
    assert st.occupying_attempt_ids == []


# ── UNRESOLVED 경로 ─────────────────────────────────────────────────────────
def test_reconciliation_after_uncertainty_shuffled():
    # 적대검증 회귀: reconciliation은 uncertainty가 만든 UNRESOLVED를 요구.
    # 파일 순서가 뒤섞여도 rank가 uncertainty(2)<reconciliation(3)로 인과 복원 → F7 위양성 없음.
    unc = _ev(s.EventType.ATTEMPT_UNCERTAINTY_OBSERVED, "recovery_scanner")
    rec = _ev(s.EventType.ATTEMPT_RECONCILIATION_OBSERVED, "reconciliation_adapter")
    st = r.reduce([rec, _started(), unc, _intent()], OP)   # 일부러 역순
    assert not st.corrupt, st.corrupt_reasons
    assert st.attempts[A1].state == s.AttemptState.UNRESOLVED

def test_unresolved_occupies_then_resolves():
    unc = _ev(s.EventType.ATTEMPT_UNCERTAINTY_OBSERVED, "recovery_scanner")
    st = r.reduce([_intent(), _started(), unc], OP)
    assert not st.corrupt
    assert st.attempts[A1].state == s.AttemptState.UNRESOLVED
    assert st.occupying_attempt_ids == [A1]        # UNRESOLVED는 여전히 점유
    # resolution → final
    res = _ev(s.EventType.ATTEMPT_RESOLUTION, "reducer",
              terminal_state=s.AttemptState.FINAL_TIMED_OUT, finality_evidence=FULL_EV)
    st2 = r.reduce([_intent(), _started(), unc, res], OP)
    assert not st2.corrupt
    assert st2.attempts[A1].state == s.AttemptState.FINAL_TIMED_OUT
    assert st2.occupying_attempt_ids == []


# ── recovery gate (A6) ──────────────────────────────────────────────────────
def test_admit_ok_when_all_resolved():
    st = r.reduce([_intent(), _started(), _term_ok()], OP)
    d = r.admit_new_intent(st, retry_cap=3, next_attempt_number=2)
    assert d.admissible and bool(d) is True

def test_admit_blocked_by_occupying():
    st = r.reduce([_intent(), _started()], OP)   # STARTED, 미종료
    d = r.admit_new_intent(st, retry_cap=3, next_attempt_number=2)
    assert not d.admissible and "occupying" in d.reason

def test_admit_blocked_by_corrupt():
    st = r.reduce([_intent(), _intent()], OP)    # F3
    d = r.admit_new_intent(st, retry_cap=3, next_attempt_number=2)
    assert not d.admissible and "corrupt" in d.reason

def test_admit_blocked_by_retry_cap():
    st = r.reduce([_intent(), _started(), _term_ok()], OP)
    d = r.admit_new_intent(st, retry_cap=2, next_attempt_number=3)
    assert not d.admissible and "retry cap" in d.reason

def test_admit_blocked_when_operation_resolved():
    st = r.reduce([_intent(), _started(), _term_ok(),
                   {"event_type": s.EventType.LOGICAL_OPERATION_RESOLUTION,
                    "writer_role": "reducer", "logical_operation_id": OP}], OP)
    assert st.operation_resolved
    d = r.admit_new_intent(st, retry_cap=3, next_attempt_number=2)
    assert not d.admissible and "resolved" in d.reason


# ── 입력 형식 오류 ───────────────────────────────────────────────────────────
def test_missing_key_raises():
    assert _raises(r.ReducerError, r.reduce, [{"event_type": s.EventType.ATTEMPT_INTENT}], OP)

def test_unknown_event_type_raises():
    assert _raises(r.ReducerError, r.reduce,
                   [{"event_type": "Bogus", "writer_role": "launcher",
                     "attempt_id": A1, "logical_operation_id": OP}], OP)

def test_nine_forbidden_codes_count():
    assert len(r.FORBIDDEN_CODES) == 9


if __name__ == "__main__":
    import traceback
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    bad = 0
    for fn in fns:
        try:
            fn(); print(f"PASS {fn.__name__}")
        except Exception:
            bad += 1; print(f"FAIL {fn.__name__}"); traceback.print_exc()
    print(f"\n{len(fns)-bad}/{len(fns)} passed")
    sys.exit(1 if bad else 0)
