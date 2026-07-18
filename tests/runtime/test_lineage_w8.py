"""W8 게이트 — logical operation 계보 + fencing (V8 A3).

하우스 컨벤션: pytest 비의존, 자체 러너(__main__). 예외 기대는 _raises() 헬퍼로.
"""
import sys, pathlib
_GEN = pathlib.Path(__file__).resolve().parents[2] / \
    "plugins/multi-agent-starter/skills/configure-multiagent/generator/templates/claude/_shared/runtime"
sys.path.insert(0, str(_GEN))
import lineage as ln


def _raises(exc, fn, *a, **kw):
    try:
        fn(*a, **kw)
    except exc:
        return True
    return False


# ── 최초 발급 ───────────────────────────────────────────────────────────────
def test_new_operation_first_attempt():
    l = ln.new_operation("op-1", "req-1")
    assert l.attempt_number == 1
    assert l.previous_attempt_id is None
    assert l.fencing_token == 1
    assert l.attempt_id == "op-1#a1"

def test_new_operation_rejects_empty():
    assert _raises(ln.LineageError, ln.new_operation, "", "req-1")
    assert _raises(ln.LineageError, ln.new_operation, "op-1", "  ")


# ── 재시도: id 승계 + 단조 + fencing generation ─────────────────────────────
def test_next_attempt_inherits_operation_id():
    l1 = ln.new_operation("op-1", "req-1")
    l2 = ln.next_attempt(l1, "req-2", retry_cap=3)
    assert l2.logical_operation_id == "op-1"        # ★ 재발급 아님
    assert l2.attempt_number == 2
    assert l2.previous_attempt_id == "op-1#a1"
    assert l2.fencing_token == 2                     # generation 증가

def test_next_attempt_monotonic_chain():
    l = ln.new_operation("op-1", "req-1")
    for n in range(2, 5):
        l = ln.next_attempt(l, f"req-{n}", retry_cap=10)
        assert l.attempt_number == n
        assert l.fencing_token == n

def test_retry_cap_enforced():
    l = ln.new_operation("op-1", "req-1")
    l = ln.next_attempt(l, "req-2", retry_cap=2)     # #2 == cap, 허용
    assert _raises(ln.RetryCapExceeded, ln.next_attempt, l, "req-3", retry_cap=2)  # #3 > cap

def test_retry_cap_bypass_blocked_by_stable_id():
    # id가 불변이므로 attempt_number가 계속 누적 → cap 우회 불가.
    l = ln.new_operation("op-1", "req-1")
    l = ln.next_attempt(l, "r2", retry_cap=3)
    l = ln.next_attempt(l, "r3", retry_cap=3)
    assert _raises(ln.RetryCapExceeded, ln.next_attempt, l, "r4", retry_cap=3)


# ── fencing: active ≤ 1 + stale 감지 ────────────────────────────────────────
def test_is_stale():
    l1 = ln.new_operation("op-1", "req-1")
    assert ln.is_stale(l1, current_fencing_token=2)      # token 1 < 2 → stale
    assert not ln.is_stale(l1, current_fencing_token=1)

def test_fence_active_zero_and_one():
    assert ln.fence_active([]) is None
    l1 = ln.new_operation("op-1", "req-1")
    assert ln.fence_active([l1]) is l1

def test_fence_active_two_active_violation():
    l1 = ln.new_operation("op-1", "req-1")
    l2 = ln.next_attempt(l1, "req-2", retry_cap=5)
    # 둘 다 active로 관측 → active≤1 위반
    assert _raises(ln.FencingViolation, ln.fence_active, [l1, l2])

def test_fence_active_mixed_operations_error():
    a = ln.new_operation("op-A", "r")
    b = ln.new_operation("op-B", "r")
    assert _raises(ln.LineageError, ln.fence_active, [a, b])


# ── 체인 무결성 ─────────────────────────────────────────────────────────────
def test_validate_chain_ok():
    l1 = ln.new_operation("op-1", "req-1")
    l2 = ln.next_attempt(l1, "req-2", retry_cap=5)
    l3 = ln.next_attempt(l2, "req-3", retry_cap=5)
    ln.validate_chain([l1, l2, l3])   # 예외 없어야

def test_validate_chain_detects_reissued_id():
    import dataclasses
    l1 = ln.new_operation("op-1", "req-1")
    l2 = ln.next_attempt(l1, "req-2", retry_cap=5)
    forged = dataclasses.replace(l2, logical_operation_id="op-2",
                                 attempt_id="op-2#a2")   # id 재발급 위조
    assert _raises(ln.LineageError, ln.validate_chain, [l1, forged])

def test_validate_chain_detects_broken_previous_link():
    import dataclasses
    l1 = ln.new_operation("op-1", "req-1")
    l2 = ln.next_attempt(l1, "req-2", retry_cap=5)
    forged = dataclasses.replace(l2, previous_attempt_id="op-1#a99")
    assert _raises(ln.LineageError, ln.validate_chain, [l1, forged])

def test_validate_chain_detects_number_gap():
    l1 = ln.new_operation("op-1", "req-1")
    l3 = ln.LogicalLineage("op-1", 3, "op-1#a3", "op-1#a1", "req", 3)
    assert _raises(ln.LineageError, ln.validate_chain, [l1, l3])

def test_validate_chain_detects_attempt_id_forgery():
    import dataclasses
    l1 = ln.new_operation("op-1", "req-1")
    forged = dataclasses.replace(l1, attempt_id="op-1#aXX")
    assert _raises(ln.LineageError, ln.validate_chain, [forged])

def test_validate_chain_detects_fencing_not_monotonic():
    import dataclasses
    l1 = ln.new_operation("op-1", "req-1")
    l2 = ln.next_attempt(l1, "req-2", retry_cap=5)
    forged = dataclasses.replace(l2, fencing_token=1)   # 단조성 위반(1→1)
    assert _raises(ln.LineageError, ln.validate_chain, [l1, forged])


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
