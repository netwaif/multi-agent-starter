"""W2 게이트 — backend x version classifier 신호 우선순위 5단 (V8 §5 / V6 §5 승계)."""
import sys, pathlib
_GEN = pathlib.Path(__file__).resolve().parents[2] / \
    "plugins/multi-agent-starter/skills/configure-multiagent/generator/templates/claude/_shared/runtime"
sys.path.insert(0, str(_GEN))
import schema as s
import classify as c


def test_agy_auto_deny_permission_high():
    r = c.classify(
        backend_id="agy", cli_version="1.1.2",
        process_status=s.ProcessStatus.EXITED, raw_rc=1, signal=None,
        stdout_text="",
        stderr_text="Error: a tool required the write_file permission and it was auto-denied.",
    )
    assert r["status"] == s.ClassificationStatus.CLASSIFIED
    assert r["failure_class"] == s.FailureClass.PERMISSION
    assert r["confidence"] == "high"
    assert r["classifier_id"] == "classify_agy_1_1_x"
    assert r["matched_rule_id"] == "agy_1_1_x_permission_auto_denied"


def test_agy_auto_deny_signature_in_stdout_too():
    # ★V6 §5: stdout에 오류를 쓰는 CLI도 있으므로 stdout도 대상이어야 한다.
    r = c.classify(
        backend_id="agy", cli_version="1.1.0",
        process_status=s.ProcessStatus.EXITED, raw_rc=0, signal=None,
        stdout_text="a tool required the shell permission and it was auto-denied",
        stderr_text="",
    )
    assert r["status"] == s.ClassificationStatus.CLASSIFIED
    assert r["failure_class"] == s.FailureClass.PERMISSION
    assert r["confidence"] == "high"


def test_clean_exit_no_failure_signal_is_success():
    # 지원 backend + 정상 종료(exited, rc0) + 실패 신호 없음 = 실패 없음 확인 → classified/none.
    # (성공 attempt는 반드시 failure_class==none이어야 is_ok가 될 수 있다 — V8 §5. rc0인데 출력이
    #  비었으면 result_contract(W3)가 empty로 잡으므로 여기서 none이어도 is_ok는 되지 않는다.)
    r = c.classify(
        backend_id="agy", cli_version="1.1.5",
        process_status=s.ProcessStatus.EXITED, raw_rc=0, signal=None,
        stdout_text="VERDICT: CONSISTENT", stderr_text="",
    )
    assert r["status"] == s.ClassificationStatus.CLASSIFIED
    assert r["failure_class"] == s.FailureClass.NONE

def test_abnormal_exit_without_signal_is_unclassified():
    # 비정상 종료(rc≠0)인데 어떤 실패 rule에도 매치 안 되면 unclassified. 자동 성공 인정 안 함.
    r = c.classify(
        backend_id="agy", cli_version="1.1.5",
        process_status=s.ProcessStatus.EXITED, raw_rc=1, signal=None,
        stdout_text="", stderr_text="something went wrong in a way we don't recognize",
    )
    assert r["status"] == s.ClassificationStatus.UNCLASSIFIED
    assert r["failure_class"] == s.FailureClass.UNKNOWN


def test_unsupported_version_is_not_generic_guess():
    r = c.classify(
        backend_id="agy", cli_version="2.0.0",
        process_status=s.ProcessStatus.EXITED, raw_rc=1, signal=None,
        stdout_text="", stderr_text="some error text",
    )
    assert r["status"] == s.ClassificationStatus.UNSUPPORTED_VERSION
    assert r["failure_class"] == s.FailureClass.UNKNOWN
    assert r["classifier_id"] is None


def test_unregistered_backend_is_unsupported_version():
    r = c.classify(
        backend_id="never_registered_backend", cli_version="9.9.9",
        process_status=s.ProcessStatus.EXITED, raw_rc=0, signal=None,
        stdout_text="", stderr_text="",
    )
    assert r["status"] == s.ClassificationStatus.UNSUPPORTED_VERSION


def test_low_confidence_candidate_does_not_publish_specific_class():
    # "quota" 단어만 있고 고신뢰 문구가 아님 → unclassified/unknown으로 보수적으로 떨어져야 한다.
    r = c.classify(
        backend_id="agy", cli_version="1.1.3",
        process_status=s.ProcessStatus.EXITED, raw_rc=1, signal=None,
        stdout_text="", stderr_text="usage note: check your quota page for details",
    )
    assert r["status"] == s.ClassificationStatus.UNCLASSIFIED
    assert r["failure_class"] == s.FailureClass.UNKNOWN
    assert r["confidence"] == "low"
    assert r["matched_rule_id"] == "agy_1_1_x_quota_word_low_confidence"


def test_structured_signal_hook_high_confidence_short_circuits():
    r = c.classify(
        backend_id="agy", cli_version="1.1.1",
        process_status=s.ProcessStatus.EXITED, raw_rc=1, signal=None,
        stdout_text="a tool required the x permission and it was auto-denied",
        stderr_text="",
        structured_signal={"failure_class": s.FailureClass.AUTH, "confidence": "high", "rule_id": "provider_auth_error"},
    )
    # tier1이 tier4보다 우선이어야 한다.
    assert r["status"] == s.ClassificationStatus.CLASSIFIED
    assert r["failure_class"] == s.FailureClass.AUTH
    assert r["classifier_id"] == "structured_status_hook"


def test_structured_signal_hook_low_confidence_falls_through():
    r = c.classify(
        backend_id="agy", cli_version="1.1.1",
        process_status=s.ProcessStatus.EXITED, raw_rc=1, signal=None,
        stdout_text="a tool required the x permission and it was auto-denied",
        stderr_text="",
        structured_signal={"failure_class": s.FailureClass.AUTH, "confidence": "low"},
    )
    assert r["status"] == s.ClassificationStatus.CLASSIFIED
    assert r["failure_class"] == s.FailureClass.PERMISSION
    assert r["classifier_id"] == "classify_agy_1_1_x"


def test_classifier_names_are_version_scoped_not_current():
    for backend_entries in c.REGISTRY.values():
        for entry in backend_entries:
            assert "_current" not in entry["classifier_id"]


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
