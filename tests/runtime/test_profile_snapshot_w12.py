"""W12 게이트 — profile snapshot 2층 (재현 + 비가역 안전 overlay). 하우스 자체러너."""
import sys, pathlib, tempfile, shutil
_GEN = pathlib.Path(__file__).resolve().parents[2] / \
    "plugins/multi-agent-starter/skills/configure-multiagent/generator/templates/claude/_shared/runtime"
sys.path.insert(0, str(_GEN))
import profile_snapshot as ps


def _raises(exc, fn, *a, **kw):
    try:
        fn(*a, **kw)
    except exc:
        return True
    return False


def _profile():
    return {"backends": {
        "gemini": {"enabled": True, "capabilities": {"tool_use": True, "file_read": False}},
        "codex": {"enabled": True, "capabilities": {"tool_use": True}},
    }}


# ── content address (plan.profile_sha256 규약) ──────────────────────────────
def test_content_address_deterministic_and_order_independent():
    a = ps.content_address({"backends": {"x": {"enabled": True}}})
    b = ps.content_address({"backends": {"x": {"enabled": True}}})
    assert a == b and a.startswith("sha256:")

def test_content_address_changes_with_content():
    assert ps.content_address(_profile()) != ps.content_address(
        {"backends": {"gemini": {"enabled": False}}})


# ── 층2 안전 overlay: 단방향 제한 ───────────────────────────────────────────
def test_overlay_disables_backend():
    eff = ps.apply_safety_overlay(_profile(), {"disabled_backends": ["gemini"]})
    assert eff["backends"]["gemini"]["enabled"] is False
    assert eff["backends"]["codex"]["enabled"] is True     # 무관 backend 불변

def test_overlay_forbids_capability():
    eff = ps.apply_safety_overlay(_profile(), {"forbidden_capabilities": ["tool_use"]})
    assert eff["backends"]["gemini"]["capabilities"]["tool_use"] is False
    assert eff["backends"]["codex"]["capabilities"]["tool_use"] is False

def test_overlay_does_not_mutate_original():
    prof = _profile()
    ps.apply_safety_overlay(prof, {"disabled_backends": ["gemini"]})
    assert prof["backends"]["gemini"]["enabled"] is True   # 원본 보존

def test_overlay_cannot_reenable():
    # 과거가 안전 disable을 되돌릴 수 없음: overlay가 disable하면 결과는 항상 disabled.
    prof = _profile()   # gemini enabled=True
    eff = ps.apply_safety_overlay(prof, {"disabled_backends": ["gemini"]})
    assert eff["backends"]["gemini"]["enabled"] is False

def test_assert_overlay_satisfied_ok_and_violation():
    eff = ps.apply_safety_overlay(_profile(), {"disabled_backends": ["gemini"]})
    ps.assert_overlay_satisfied(eff, {"disabled_backends": ["gemini"]})   # OK
    # 위조된 effective(강제로 되살림) → 위반 검출
    eff["backends"]["gemini"]["enabled"] = True
    assert _raises(ps.ProfileError, ps.assert_overlay_satisfied, eff, {"disabled_backends": ["gemini"]})

def test_overlay_rejects_bad_profile():
    assert _raises(ps.ProfileError, ps.apply_safety_overlay, {"backends": "nope"}, {})


# ── CA archive: 재현 ────────────────────────────────────────────────────────
def test_archive_roundtrip_memory():
    ar = ps.ProfileArchive()
    addr = ar.put(_profile())
    assert ar.get(addr) == _profile()

def test_archive_roundtrip_file():
    d = tempfile.mkdtemp()
    try:
        ar = ps.ProfileArchive(dir_path=d)
        addr = ar.put(_profile())
        ar2 = ps.ProfileArchive(dir_path=d)      # 새 인스턴스로도 복원
        assert ar2.get(addr) == _profile()
    finally:
        shutil.rmtree(d, ignore_errors=True)

def test_archive_missing_raises():
    ar = ps.ProfileArchive()
    assert _raises(ps.ProfileError, ar.get, "sha256:deadbeef")

def test_reproduce_effective_applies_current_overlay():
    # 층1 옛 프로필을 주소로 복원 + 층2 현재 overlay 적용.
    ar = ps.ProfileArchive()
    addr = ar.put(_profile())                    # 과거: gemini enabled
    eff = ar.reproduce_effective(addr, {"disabled_backends": ["gemini"]})
    assert eff["backends"]["gemini"]["enabled"] is False   # 현재 안전이 이김
    # 원본 archive는 불변(재현은 여전히 과거 그대로).
    assert ar.get(addr)["backends"]["gemini"]["enabled"] is True

def test_put_idempotent():
    ar = ps.ProfileArchive()
    assert ar.put(_profile()) == ar.put(_profile())


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
