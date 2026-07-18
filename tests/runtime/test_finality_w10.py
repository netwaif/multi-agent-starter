"""W10 게이트 — A1b finality 증거 생산자 (fail-closed). 하우스 자체러너 컨벤션."""
import sys, pathlib
_GEN = pathlib.Path(__file__).resolve().parents[2] / \
    "plugins/multi-agent-starter/skills/configure-multiagent/generator/templates/claude/_shared/runtime"
sys.path.insert(0, str(_GEN))
import schema as s
import finality as f
import reducer as r


def _raises(exc, fn, *a, **kw):
    try:
        fn(*a, **kw)
    except exc:
        return True
    return False


# ── quiescence 확인 ─────────────────────────────────────────────────────────
def test_quiescent_none_pgid():
    assert f.process_group_quiescent(None) is True    # 실행 자체 없음

def test_quiescent_dead_group():
    # 존재 불가능한 pgid(매우 큰 값) → ProcessLookupError → quiescent
    assert f.process_group_quiescent(2**30) is True


# ── fail-closed: 미확립 증거로 final 조립 거부 ──────────────────────────────
def test_success_requires_all_axes():
    # quiescence 미확인 → 거부
    assert _raises(f.FinalityError, f.build_finality_evidence, s.AttemptState.FINAL_SUCCEEDED,
                   quiescence_confirmed=False, effect_class="none", effect_outcome="succeeded",
                   output_outcome="valid")

def test_success_effect_unknown_rejected():
    # effect_outcome=unknown → effect_resolved 미확립 → 거부
    assert _raises(f.FinalityError, f.build_finality_evidence, s.AttemptState.FINAL_SUCCEEDED,
                   quiescence_confirmed=True, effect_class="unknown", effect_outcome="unknown",
                   output_outcome="valid")

def test_success_full_evidence_ok():
    fe = f.build_finality_evidence(s.AttemptState.FINAL_SUCCEEDED, quiescence_confirmed=True,
                                   effect_class="local_content_addressed", effect_outcome="succeeded",
                                   output_outcome="valid")
    assert set(fe.evidence_axes) == set(s.FINALITY_REQUIREMENTS[s.AttemptState.FINAL_SUCCEEDED])
    assert fe.effect_resolution_hash.startswith("sha256:")

def test_invalid_terminal_state_rejected():
    assert _raises(f.FinalityError, f.build_finality_evidence, "BOGUS",
                   quiescence_confirmed=True, effect_class="none", effect_outcome="none",
                   output_outcome="valid")

def test_bad_effect_or_output_outcome_rejected():
    assert _raises(f.FinalityError, f.build_finality_evidence, s.AttemptState.FINAL_FAILED,
                   quiescence_confirmed=True, effect_class="none", effect_outcome="weird",
                   output_outcome="valid")
    assert _raises(f.FinalityError, f.build_finality_evidence, s.AttemptState.FINAL_FAILED,
                   quiescence_confirmed=True, effect_class="none", effect_outcome="failed",
                   output_outcome="weird")


# ── 상태별 요구 축 차이 ─────────────────────────────────────────────────────
def test_output_limit_only_needs_quiescence():
    # OUTPUT_LIMIT_EXCEEDED는 local_quiescence만 요구 — effect unknown이어도 통과
    fe = f.build_finality_evidence(s.AttemptState.OUTPUT_LIMIT_EXCEEDED, quiescence_confirmed=True,
                                   effect_class="unknown", effect_outcome="unknown",
                                   output_outcome="unavailable")
    assert fe.evidence_axes == ("local_quiescence",)

def test_precheck_rejected_needs_nothing():
    fe = f.build_finality_evidence(s.AttemptState.PRECHECK_REJECTED, quiescence_confirmed=False,
                                   effect_class="none", effect_outcome="unknown",
                                   output_outcome="unavailable")
    assert fe.evidence_axes == ()


# ── 생산자→소비자 왕복: reducer가 evidence 수용 ─────────────────────────────
def test_producer_output_accepted_by_reducer():
    fe = f.build_finality_evidence(s.AttemptState.FINAL_SUCCEEDED, quiescence_confirmed=True,
                                   effect_class="none", effect_outcome="succeeded",
                                   output_outcome="valid")
    tf = fe.to_terminal_fields()
    events = [
        {"event_type": s.EventType.ATTEMPT_INTENT, "writer_role": "launcher",
         "attempt_id": "op#a1", "logical_operation_id": "op"},
        {"event_type": s.EventType.ATTEMPT_STARTED, "writer_role": "wrapper",
         "attempt_id": "op#a1", "logical_operation_id": "op"},
        {"event_type": s.EventType.ATTEMPT_TERMINAL, "writer_role": "reducer",
         "attempt_id": "op#a1", "logical_operation_id": "op", **tf},
    ]
    st = r.reduce(events, "op")
    assert not st.corrupt, st.corrupt_reasons
    assert st.attempts["op#a1"].state == s.AttemptState.FINAL_SUCCEEDED

def test_effect_hash_deterministic():
    a = f.effect_resolution_hash("none", "succeeded", "at_most_once")
    b = f.effect_resolution_hash("none", "succeeded", "at_most_once")
    c = f.effect_resolution_hash("non_idempotent", "succeeded", "at_most_once")
    assert a == b and a != c


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
