"""W3 게이트 — result_contract 검증 + legacy status 순서 결정표 + ok 완전조건 (V8 §1.2/§1.3)."""
import sys, pathlib
_GEN = pathlib.Path(__file__).resolve().parents[2] / \
    "plugins/multi-agent-starter/skills/configure-multiagent/generator/templates/claude/_shared/runtime"
sys.path.insert(0, str(_GEN))
import schema as s
import outcome as o


# ── 공용 envelope 빌더 (기본값 = 완전 성공) ─────────────────────────────────

def _envelope(**overrides) -> dict:
    base = {
        "preflight": {"status": s.PreflightStatus.ELIGIBLE, "reason": "none"},
        "process": {"status": s.ProcessStatus.EXITED, "raw_rc": 0, "signal": None},
        "capture": {"status": s.CaptureStatus.OK},
        "result_contract": {"status": s.ResultContractStatus.SATISFIED, "reason": None},
        "classification": {
            "status": s.ClassificationStatus.NOT_NEEDED,
            "failure_class": s.FailureClass.NONE,
            "confidence": None,
        },
    }
    for k, v in overrides.items():
        merged = dict(base.get(k, {}))
        merged.update(v)
        base[k] = merged
    return base


# ── (A) evaluate_result_contract ────────────────────────────────────────────

def test_result_contract_satisfied():
    r = o.evaluate_result_contract(
        {"mode": "text", "output_required": True, "min_non_whitespace_chars": 1}, b"hello"
    )
    assert r["status"] == s.ResultContractStatus.SATISFIED
    assert r["reason"] is None

def test_result_contract_newline_only_insufficient():
    # "\n" 한 바이트가 present로 새는 것 차단 — V4 §1.3의 핵심 케이스.
    r = o.evaluate_result_contract(
        {"mode": "text", "output_required": True, "min_non_whitespace_chars": 1}, b"\n"
    )
    assert r["status"] == s.ResultContractStatus.UNSATISFIED
    assert r["reason"] == "insufficient_non_whitespace"

def test_result_contract_invalid_utf8():
    r = o.evaluate_result_contract(
        {"mode": "text", "output_required": True, "min_non_whitespace_chars": 1}, b"\xff\xfe\x00\x99"
    )
    assert r["status"] == s.ResultContractStatus.UNSATISFIED
    assert r["reason"] == "invalid_utf8"

def test_result_contract_output_not_produced():
    r = o.evaluate_result_contract(
        {"mode": "text", "output_required": True, "min_non_whitespace_chars": 1}, None
    )
    assert r["status"] == s.ResultContractStatus.UNSATISFIED
    assert r["reason"] == "output_not_produced"


# ── (B) legacy_status — 네거티브 케이스 필수 (V8 브리프 지정) ───────────────

def test_rc0_nonempty_permission_denial_is_error():
    # 위양성 차단 케이스(E3 계열): rc==0 이지만 고신뢰 permission denial 응답 → error, ok 아님.
    env = _envelope(
        classification={
            "status": s.ClassificationStatus.CLASSIFIED,
            "failure_class": s.FailureClass.PERMISSION,
            "confidence": "high",
        },
        result_contract={"status": s.ResultContractStatus.SATISFIED},
    )
    assert env["process"]["raw_rc"] == 0
    assert o.legacy_status(env) == "error"
    assert o.is_ok(env) is False

def test_rc0_whitespace_only_is_empty():
    contract_result = o.evaluate_result_contract(
        {"mode": "text", "output_required": True, "min_non_whitespace_chars": 1}, b"   \n\t "
    )
    env = _envelope(result_contract=contract_result)
    assert o.legacy_status(env) == "empty"
    assert o.is_ok(env) is False

def test_wrapper_timeout_is_timeout():
    env = _envelope(
        process={"status": s.ProcessStatus.WRAPPER_TIMEOUT, "raw_rc": None, "signal": None},
        result_contract={"status": s.ResultContractStatus.NOT_EVALUATED},
    )
    assert o.legacy_status(env) == "timeout"
    assert o.is_ok(env) is False

def test_admission_ineligible_is_error():
    env = _envelope(
        preflight={"status": s.PreflightStatus.INELIGIBLE, "reason": "unsupported_cli_version"},
        process={"status": s.ProcessStatus.NOT_STARTED, "raw_rc": None, "signal": None},
        result_contract={"status": s.ResultContractStatus.NOT_EVALUATED},
    )
    assert o.legacy_status(env) == "error"
    assert o.is_ok(env) is False

def test_capture_failed_blocks_is_ok_but_not_legacy_decision_table():
    # V6 §5 보강: capture.status==ok는 legacy_status 결정표엔 없지만 is_ok의 필수 축이다.
    env = _envelope(capture={"status": s.CaptureStatus.FAILED})
    assert o.legacy_status(env) == "ok"   # 결정표는 capture를 안 봄 — 의도된 차이
    assert o.is_ok(env) is False          # is_ok는 capture.status==ok를 반드시 요구

def test_full_success_is_ok():
    env = _envelope()
    assert o.legacy_status(env) == "ok"
    assert o.is_ok(env) is True


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
