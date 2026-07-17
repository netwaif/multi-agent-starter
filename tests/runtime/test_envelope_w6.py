"""W6 게이트 — envelope v2 조립 통합 (classify+outcome+result_contract 맞물림).

단위 컴포넌트가 각자 통과해도 조립 단계에서 성공 판정 경로가 깨질 수 있다(실제로 초기 통합에서
정상 성공이 unclassified→ok=False로 잘못 떨어졌고, classify tier5에 '정상 종료+무신호=none' 경로를
추가해 고침). 이 테스트가 그 회귀를 잡는다.
"""
import sys, pathlib, tempfile, os, json
_RUNTIME = pathlib.Path(__file__).resolve().parents[2] / \
    "plugins/multi-agent-starter/skills/configure-multiagent/generator/templates/claude/_shared/runtime"
sys.path.insert(0, str(_RUNTIME))
import envelope as e


def _build(rc, stdout, *, timed_out=False, preflight_status="eligible", preflight_reason="none"):
    d = tempfile.mkdtemp()
    op, ep = os.path.join(d, "o"), os.path.join(d, "e")
    with open(op, "w") as f: f.write(stdout)
    open(ep, "w").close()
    env = e.build_envelope(
        worker_id="gemini", backend_route_id="agy-cli", call_type="cli",
        cli_version="1.1.3", model_requested="gemini-3.1-pro-high", model_observed=None,
        raw_rc=rc, timed_out=timed_out, stdout_path=op, stderr_path=ep, duration_s=1,
        result_contract={"mode": "text", "output_required": True, "min_non_whitespace_chars": 1},
        preflight_status=preflight_status, preflight_reason=preflight_reason,
    )
    return env


def test_clean_success_is_ok():
    env = _build(0, "VERDICT: CONSISTENT\n")
    assert env["ok"] is True
    assert env["legacy_status"] == "ok"
    assert env["classification"]["failure_class"] == "none"
    assert env["output"]["stdout_sha256"]                      # 원문 hash 존재

def test_rc0_nonempty_permission_denial_is_error():
    # E3 계열 위양성: rc0 + 비어있지 않은 권한거부 응답 → 성공 아님
    env = _build(0, "a tool required the read_file permission ... so it was auto-denied\n")
    assert env["ok"] is False
    assert env["legacy_status"] == "error"
    assert env["classification"]["failure_class"] == "permission"

def test_rc0_empty_is_empty_not_ok():
    env = _build(0, "")
    assert env["ok"] is False
    assert env["legacy_status"] == "empty"
    assert env["output"]["status"] == "output_missing"

def test_rc0_whitespace_only_is_empty():
    env = _build(0, "   \n\t ")
    assert env["ok"] is False
    assert env["legacy_status"] == "empty"          # min_non_whitespace 차단

def test_timeout_maps_to_timeout():
    env = _build(124, "", timed_out=True)
    assert env["legacy_status"] == "timeout"
    assert env["process"]["status"] == "wrapper_timeout"

def test_preflight_ineligible_is_not_produced():
    env = _build(0, "", preflight_status="ineligible", preflight_reason="inline_only_file_reference")
    assert env["legacy_status"] == "error"
    assert env["output"]["status"] == "not_produced"     # 실행 자체 없음 ≠ output_missing
    assert env["process"]["raw_rc"] is None

def test_envelope_is_schema_v2_and_json_serializable():
    env = _build(0, "ok\n")
    assert env["schema_version"] == "2"
    json.dumps(env)                                   # 직렬화 가능(bash가 stdout으로 방출)


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
