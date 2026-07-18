"""W1 게이트 — canonical event schema + state machine 불변식 (V8 A1/A1b/A5b/A7)."""
import sys, pathlib
_GEN = pathlib.Path(__file__).resolve().parents[2] / \
    "plugins/multi-agent-starter/skills/configure-multiagent/generator/templates/claude/_shared/runtime"
sys.path.insert(0, str(_GEN))
import schema as s


def test_unresolved_not_terminal():
    assert not s.is_terminal(s.AttemptState.UNRESOLVED)
    assert s.AttemptState.UNRESOLVED not in s.FINAL_TERMINAL_STATES

def test_final_states_terminal():
    for t in (s.AttemptState.FINAL_SUCCEEDED, s.AttemptState.FINAL_TIMED_OUT, s.AttemptState.PRECHECK_REJECTED):
        assert s.is_terminal(t)

def test_transitions():
    A = s.AttemptState
    assert s.transition_allowed(A.PREPARED, A.STARTED)
    assert s.transition_allowed(A.PREPARED, A.FINAL_FAILED)      # spawn_failed (A2)
    assert s.transition_allowed(A.STARTED, A.UNRESOLVED)
    assert s.transition_allowed(A.UNRESOLVED, A.FINAL_SUCCEEDED)
    assert not s.transition_allowed(A.PREPARED, A.FINAL_SUCCEEDED)  # STARTED 거쳐야

def test_writer_authority():
    assert not s.CONTESTANT_ROLES & s.TRUSTED_WRITER_ROLES        # flavor/worker는 trusted 아님
    assert s.WRITER_AUTHORITY[s.EventType.ATTEMPT_TERMINAL] == "reducer"
    assert set(s.WRITER_AUTHORITY) == s.ALL_EVENT_TYPES           # 모든 event에 writer 지정

def test_finality_requires_quiescence():
    for t in (s.AttemptState.FINAL_TIMED_OUT, s.AttemptState.FINAL_CANCELLED,
              s.AttemptState.FINAL_FAILED, s.AttemptState.OUTPUT_LIMIT_EXCEEDED):
        assert "local_quiescence" in s.FINALITY_REQUIREMENTS[t]
    assert s.FINALITY_REQUIREMENTS[s.AttemptState.PRECHECK_REJECTED] == ()

def test_conservative_effect_composition():
    assert s.most_conservative_effect(
        [s.EffectClass.LOCAL_CONTENT_ADDRESSED, s.EffectClass.NON_IDEMPOTENT]) == s.EffectClass.NON_IDEMPOTENT
    assert s.most_conservative_effect([s.EffectClass.NONE, s.EffectClass.UNKNOWN]) == s.EffectClass.UNKNOWN


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
