"""W11 게이트 — A5b provenance + generation fencing (write-admission). 하우스 자체러너."""
import sys, pathlib
_GEN = pathlib.Path(__file__).resolve().parents[2] / \
    "plugins/multi-agent-starter/skills/configure-multiagent/generator/templates/claude/_shared/runtime"
sys.path.insert(0, str(_GEN))
import schema as s
import provenance as pv


def _raises(exc, fn, *a, **kw):
    try:
        fn(*a, **kw)
    except exc:
        return True
    return False


def _prov(**over):
    d = dict(writer_identity="uid:501", writer_role="launcher",
             runtime_attestation_id="att-1", operation_fencing_token=1, parent_event_hash=None)
    d.update(over)
    return pv.Provenance(**d)


# ── authorized_writer: schema.WRITER_AUTHORITY 단일정본 ─────────────────────
def test_authorized_writer_matrix():
    assert pv.authorized_writer(s.EventType.ATTEMPT_INTENT, "launcher")
    assert pv.authorized_writer(s.EventType.ATTEMPT_TERMINAL, "reducer")
    assert not pv.authorized_writer(s.EventType.ATTEMPT_TERMINAL, "launcher")  # 잘못된 writer

def test_contestant_never_authorized():
    for et in s.ALL_EVENT_TYPES:
        assert not pv.authorized_writer(et, "flavor")
        assert not pv.authorized_writer(et, "worker")


# ── verify: 권한 ────────────────────────────────────────────────────────────
def test_verify_ok_root_event():
    # 최초 intent는 parent 없이 OK
    pv.verify_event_provenance(s.EventType.ATTEMPT_INTENT, _prov(), current_generation=1)

def test_verify_rejects_contestant():
    p = _prov(writer_role="flavor")
    assert _raises(pv.ProvenanceViolation, pv.verify_event_provenance,
                   s.EventType.ATTEMPT_INTENT, p, current_generation=1)

def test_verify_rejects_wrong_writer():
    p = _prov(writer_role="launcher", parent_event_hash="sha256:x")
    assert _raises(pv.ProvenanceViolation, pv.verify_event_provenance,
                   s.EventType.ATTEMPT_TERMINAL, p, current_generation=1)  # terminal=reducer


# ── verify: 인증 값 ─────────────────────────────────────────────────────────
def test_verify_rejects_empty_identity():
    assert _raises(pv.ProvenanceViolation, pv.verify_event_provenance,
                   s.EventType.ATTEMPT_INTENT, _prov(writer_identity="  "), current_generation=1)

def test_verify_rejects_empty_attestation():
    assert _raises(pv.ProvenanceViolation, pv.verify_event_provenance,
                   s.EventType.ATTEMPT_INTENT, _prov(runtime_attestation_id=""), current_generation=1)


# ── verify: generation fencing ──────────────────────────────────────────────
def test_verify_rejects_stale_generation():
    p = _prov(operation_fencing_token=1)
    assert _raises(pv.ProvenanceViolation, pv.verify_event_provenance,
                   s.EventType.ATTEMPT_INTENT, p, current_generation=2)   # 1 < 2 stale

def test_verify_accepts_equal_or_newer_generation():
    pv.verify_event_provenance(s.EventType.ATTEMPT_INTENT, _prov(operation_fencing_token=3),
                               current_generation=3)
    pv.verify_event_provenance(s.EventType.ATTEMPT_INTENT, _prov(operation_fencing_token=5),
                               current_generation=3)

def test_is_stale_helper():
    assert pv.is_stale_generation(_prov(operation_fencing_token=1), 2)
    assert not pv.is_stale_generation(_prov(operation_fencing_token=2), 2)


# ── verify: parent 링크 ─────────────────────────────────────────────────────
def test_non_root_event_requires_parent():
    p = _prov(writer_role="wrapper", parent_event_hash=None)   # started는 parent 필수
    assert _raises(pv.ProvenanceViolation, pv.verify_event_provenance,
                   s.EventType.ATTEMPT_STARTED, p, current_generation=1)

def test_non_root_event_with_parent_ok():
    p = _prov(writer_role="wrapper", parent_event_hash="sha256:intent")
    pv.verify_event_provenance(s.EventType.ATTEMPT_STARTED, p, current_generation=1)

def test_unknown_event_type_rejected():
    assert _raises(pv.ProvenanceViolation, pv.verify_event_provenance,
                   "Bogus", _prov(), current_generation=1)


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
