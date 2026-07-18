"""W7 게이트 — dispatch plan 불변 revision + mission 인과 + launcher seal (V8 A5b).

하우스 컨벤션: pytest 비의존, 자체 러너(__main__). 예외 기대는 _raises() 헬퍼로.
"""
import dataclasses, json, sys, pathlib
_GEN = pathlib.Path(__file__).resolve().parents[2] / \
    "plugins/multi-agent-starter/skills/configure-multiagent/generator/templates/claude/_shared/runtime"
sys.path.insert(0, str(_GEN))
import plan as p


def _raises(exc, fn, *a, **kw):
    try:
        fn(*a, **kw)
    except exc:
        return True
    return False


# ── mission-byte 인과 ──────────────────────────────────────────────────────
def test_mission_hash_json_canonical_stable():
    a = b'{"goal":"x","n":1}'
    b = b'{ "n": 1 ,  "goal":"x" }'   # 공백·키순서만 다른 의미상 동일 JSON
    assert p.mission_hash(a) == p.mission_hash(b)
    assert p.mission_hash(a).startswith("sha256:")

def test_mission_hash_raw_bytes_for_nonjson():
    assert p.mission_hash(b"# brief\ndo the thing") == p.mission_hash(b"# brief\ndo the thing")
    assert p.mission_hash(b"a") != p.mission_hash(b"b")

def test_canonicalize_mode():
    assert p.canonicalize_mission(b'{"k":1}')[1] == "json_canonical"
    assert p.canonicalize_mission(b"plain text")[1] == "raw_bytes"


# ── 불변 revision 구성 + 봉인 ──────────────────────────────────────────────
def _rev1(**over):
    kw = dict(plan_id="P1", revision=1, parent_hash=None, profile_sha256="sha256:prof",
              mission_hash="sha256:m", capability_slot="critic", role_label="codex-critic",
              selected_backend_route="codex-cli")
    kw.update(over)
    return p.build_plan_revision(**kw)

def test_build_seals_plan_hash():
    r = _rev1()
    assert r.plan_hash.startswith("sha256:")
    assert _rev1().plan_hash == r.plan_hash                     # 결정적

def test_plan_hash_changes_with_slot_or_label():
    base = _rev1().plan_hash
    assert _rev1(capability_slot="main").plan_hash != base
    assert _rev1(role_label="claude-main").plan_hash != base    # slot/label 분리 확인

def test_revision1_forbids_parent():
    assert _raises(p.PlanValidationError, _rev1, parent_hash="sha256:x")

def test_revision_gt1_requires_parent():
    assert _raises(p.PlanValidationError, _rev1, revision=2, parent_hash=None)

def test_empty_slot_or_label_rejected():
    assert _raises(p.PlanValidationError, _rev1, capability_slot="")
    assert _raises(p.PlanValidationError, _rev1, role_label="  ")


# ── launcher import 경계 (A5b) ─────────────────────────────────────────────
def _submission(**over):
    d = dict(plan_id="P1", profile_sha256="sha256:prof", mission_hash="sha256:m",
             capability_slot="critic", role_label="codex-critic",
             selected_backend_route="codex-cli")
    d.update(over)
    return json.dumps(d).encode("utf-8")

def test_launcher_imports_and_seals():
    r = p.import_plan_submission(_submission(), expected_profile_sha256="sha256:prof")
    assert r.revision == 1 and r.parent_hash is None
    assert r.created_by_role == "flavor"
    assert r.plan_hash == p.compute_plan_hash(r.to_dict())

def test_launcher_rejects_nonflavor_proposer():
    assert _raises(p.PlanValidationError, p.import_plan_submission, _submission(),
                   expected_profile_sha256="sha256:prof", submitter_role="reducer")

def test_launcher_rejects_profile_forgery():
    assert _raises(p.PlanValidationError, p.import_plan_submission,
                   _submission(profile_sha256="sha256:FAKE"),
                   expected_profile_sha256="sha256:prof")

def test_launcher_ignores_flavor_supplied_plan_hash():
    forged = _submission(plan_hash="sha256:LIE", schema_version="99")   # self-seal 시도
    r = p.import_plan_submission(forged, expected_profile_sha256="sha256:prof")
    assert r.plan_hash != "sha256:LIE"
    assert r.schema_version == p.SCHEMA_VERSION
    assert r.plan_hash == p.compute_plan_hash(r.to_dict())

def test_launcher_derives_revision_from_parent():
    r1 = p.import_plan_submission(_submission(), expected_profile_sha256="sha256:prof")
    r2 = p.import_plan_submission(_submission(), expected_profile_sha256="sha256:prof", parent=r1)
    assert r2.revision == 2 and r2.parent_hash == r1.plan_hash


# ── revision chain 무결성 ──────────────────────────────────────────────────
def test_verify_chain_ok():
    r1 = _rev1()
    r2 = _rev1(revision=2, parent_hash=r1.plan_hash)
    p.verify_revision_chain([r1, r2])   # 예외 없어야

def test_verify_chain_detects_broken_link():
    r1 = _rev1()
    r2 = _rev1(revision=2, parent_hash="sha256:wrong")
    assert _raises(p.PlanValidationError, p.verify_revision_chain, [r1, r2])

def test_verify_chain_detects_tampered_seal():
    r1 = _rev1()
    tampered = dataclasses.replace(r1, role_label="claude-main")   # 필드 변조, plan_hash 옛것
    assert _raises(p.PlanValidationError, p.verify_revision_chain, [tampered])

def test_verify_chain_detects_revision_gap():
    r1 = _rev1()
    r3 = _rev1(revision=3, parent_hash=r1.plan_hash)
    assert _raises(p.PlanValidationError, p.verify_revision_chain, [r1, r3])


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
