"""W14 — end-to-end fault-injection tests for the v4 runtime.

Unlike the per-module unit tests (test_reducer_w9.py, test_provenance_w11.py,
test_finality_w10.py), these scenarios drive the runtime through its real
seams: temp event-store directories, wal.py's write-once files, and the
recovery_gate CLI entry points (cmd_admit/cmd_commit) invoked in-process —
then let event_store.load_events()+reducer.reduce() discover the fault the
way a real recovery pass would, instead of hand-building an event list and
calling reduce() directly.

하우스 컨벤션: pytest 비의존, 자체 러너(__main__). 예외 기대는 _raises() 헬퍼로.
"""
import argparse
import contextlib
import io
import json
import os
import sys
import pathlib
import tempfile

_GEN = pathlib.Path(__file__).resolve().parents[2] / \
    "plugins/multi-agent-starter/skills/configure-multiagent/generator/templates/claude/_shared/runtime"
sys.path.insert(0, str(_GEN))
import schema as s
import reducer as r
import provenance as pv
import finality as fin
import recovery_gate as rg
import event_store as es
import wal


def _raises(exc, fn, *a, **kw):
    try:
        fn(*a, **kw)
    except exc:
        return True
    return False


FULL_EV = ["local_quiescence", "effect_resolved", "output_sealed"]


def _ns(**kw):
    return argparse.Namespace(**kw)


def _run(fn, ns):
    """cmd_admit/cmd_commit print JSON to stdout and return an exit code.
    Capture both so tests can assert on the CLI's actual output contract."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = fn(ns)
    return rc, json.loads(buf.getvalue())


def _bytes(d: dict) -> bytes:
    return json.dumps(d, ensure_ascii=False).encode("utf-8")


def _inject(d: str, name: str, ev: dict) -> None:
    """Simulate a fault landing directly in the event store, bypassing every
    wal.py/recovery_gate protection — e.g. a rogue writer, a crash-recovery
    replay bug, or a compromised worker writing where it has no authority."""
    with open(os.path.join(d, name), "w", encoding="utf-8") as f:
        json.dump(ev, f)


# ── canary: the happy path must stay green while every fault below is caught ─
def test_canary_clean_admit_commit_reaches_final_succeeded():
    with tempfile.TemporaryDirectory() as d:
        op = "op-canary"
        rc, out = _run(rg.cmd_admit, _ns(events_dir=d, logical_operation_id=op, retry_cap=3))
        assert rc == 0 and out["admissible"] is True
        aid = out["attempt_id"]

        rc2, out2 = _run(rg.cmd_commit,
                          _ns(events_dir=d, logical_operation_id=op, attempt_id=aid, raw_rc=0))
        assert rc2 == 0 and out2["state"] == s.AttemptState.FINAL_SUCCEEDED

        st = r.reduce(es.load_events(d), op)
        assert not st.corrupt, st.corrupt_reasons
        assert st.attempts[aid].state == s.AttemptState.FINAL_SUCCEEDED
        assert st.occupying_attempt_ids == []


# ── F1: contestant (flavor/worker) wrote a canonical event straight to disk ──
def test_fault_contestant_writer_corrupts_store():
    with tempfile.TemporaryDirectory() as d:
        op = "op-f1"
        aid = f"{op}#a1"
        _inject(d, "rogue.json", {
            "event_type": s.EventType.ATTEMPT_INTENT, "writer_role": "flavor",
            "attempt_id": aid, "logical_operation_id": op,
        })
        st = r.reduce(es.load_events(d), op)
        assert st.corrupt and r.F1_CONTESTANT_WRITER in st.corrupt_reasons
        # a corrupt store must also refuse any further admission.
        decision = r.admit_new_intent(st, retry_cap=3, next_attempt_number=1)
        assert not decision.admissible and "corrupt" in decision.reason


# ── F2: launcher wrote AttemptTerminal (only 'reducer' has that authority) ──
def test_fault_wrong_trusted_writer_for_terminal():
    with tempfile.TemporaryDirectory() as d:
        op = "op-f2"
        aid = f"{op}#a1"
        base = {"attempt_id": aid, "logical_operation_id": op}
        wal.write_intent(d, aid, _bytes({
            "event_type": s.EventType.ATTEMPT_INTENT, "writer_role": "launcher", **base}))
        wal.write_marker(d, aid, "started", _bytes({
            "event_type": s.EventType.ATTEMPT_STARTED, "writer_role": "wrapper", **base}))
        # fault: launcher (not reducer) publishes the terminal marker.
        wal.write_terminal(d, aid, _bytes({
            "event_type": s.EventType.ATTEMPT_TERMINAL, "writer_role": "launcher",
            "terminal_state": s.AttemptState.FINAL_SUCCEEDED, "finality_evidence": FULL_EV,
            **base}))
        st = r.reduce(es.load_events(d), op)
        assert st.corrupt and r.F2_WRONG_TRUSTED_WRITER in st.corrupt_reasons


# ── F3: a second AttemptIntent lands for the same attempt (replay/race bug) ──
def test_fault_duplicate_intent_bypassing_wal_writeonce():
    with tempfile.TemporaryDirectory() as d:
        op = "op-f3"
        aid = f"{op}#a1"
        intent = {"event_type": s.EventType.ATTEMPT_INTENT, "writer_role": "launcher",
                   "attempt_id": aid, "logical_operation_id": op}
        wal.write_intent(d, aid, _bytes(intent))
        # a genuine second write to the *same* attempt_id would raise
        # DuplicateAttemptError at the wal layer — confirm that guard still works...
        assert _raises(wal.DuplicateAttemptError, wal.write_intent, d, aid, _bytes(intent))
        # ...but a crash-recovery replay writing under a different marker name
        # can still smuggle a duplicate logical intent past wal's filename guard.
        wal.write_marker(d, aid, "intent-replay", _bytes(intent))
        st = r.reduce(es.load_events(d), op)
        assert st.corrupt and r.F3_DUPLICATE_INTENT in st.corrupt_reasons


# ── F4: a second AttemptTerminal lands for an already-terminated attempt ────
def test_fault_duplicate_terminal_bypassing_wal_writeonce():
    with tempfile.TemporaryDirectory() as d:
        op = "op-f4"
        rc, out = _run(rg.cmd_admit, _ns(events_dir=d, logical_operation_id=op, retry_cap=3))
        aid = out["attempt_id"]
        rc2, out2 = _run(rg.cmd_commit,
                          _ns(events_dir=d, logical_operation_id=op, attempt_id=aid, raw_rc=0))
        assert rc2 == 0 and out2["state"] == s.AttemptState.FINAL_SUCCEEDED
        # the real terminal path is now write-once-protected; confirm that...
        assert _raises(wal.DuplicateAttemptError, wal.write_terminal, d, aid, _bytes({
            "event_type": s.EventType.ATTEMPT_TERMINAL, "writer_role": "reducer",
            "attempt_id": aid, "logical_operation_id": op,
            "terminal_state": s.AttemptState.FINAL_SUCCEEDED, "finality_evidence": FULL_EV}))
        # ...but a stray second terminal marker under a different kind still gets in.
        wal.write_marker(d, aid, "terminal-replay", _bytes({
            "event_type": s.EventType.ATTEMPT_TERMINAL, "writer_role": "reducer",
            "attempt_id": aid, "logical_operation_id": op,
            "terminal_state": s.AttemptState.FINAL_SUCCEEDED, "finality_evidence": FULL_EV}))
        st = r.reduce(es.load_events(d), op)
        assert st.corrupt and r.F4_DUPLICATE_TERMINAL in st.corrupt_reasons


# ── F5: AttemptStarted with no preceding AttemptIntent in the store ─────────
def test_fault_started_without_intent():
    with tempfile.TemporaryDirectory() as d:
        op = "op-f5"
        aid = f"{op}#a1"
        wal.write_marker(d, aid, "started", _bytes({
            "event_type": s.EventType.ATTEMPT_STARTED, "writer_role": "wrapper",
            "attempt_id": aid, "logical_operation_id": op}))
        st = r.reduce(es.load_events(d), op)
        assert st.corrupt and r.F5_STARTED_WITHOUT_INTENT in st.corrupt_reasons


# ── F6: AttemptTerminal with no preceding AttemptIntent in the store ────────
def test_fault_terminal_without_intent():
    with tempfile.TemporaryDirectory() as d:
        op = "op-f6"
        aid = f"{op}#a1"
        wal.write_terminal(d, aid, _bytes({
            "event_type": s.EventType.ATTEMPT_TERMINAL, "writer_role": "reducer",
            "attempt_id": aid, "logical_operation_id": op,
            "terminal_state": s.AttemptState.FINAL_SUCCEEDED, "finality_evidence": FULL_EV}))
        st = r.reduce(es.load_events(d), op)
        assert st.corrupt and r.F6_TERMINAL_WITHOUT_INTENT in st.corrupt_reasons


# ── F7: terminal skips STARTED entirely (PREPARED -> FINAL_SUCCEEDED) ───────
def test_fault_illegal_transition_skips_started():
    with tempfile.TemporaryDirectory() as d:
        op = "op-f7"
        aid = f"{op}#a1"
        wal.write_intent(d, aid, _bytes({
            "event_type": s.EventType.ATTEMPT_INTENT, "writer_role": "launcher",
            "attempt_id": aid, "logical_operation_id": op}))
        wal.write_terminal(d, aid, _bytes({
            "event_type": s.EventType.ATTEMPT_TERMINAL, "writer_role": "reducer",
            "attempt_id": aid, "logical_operation_id": op,
            "terminal_state": s.AttemptState.FINAL_SUCCEEDED, "finality_evidence": FULL_EV}))
        st = r.reduce(es.load_events(d), op)
        assert st.corrupt and r.F7_ILLEGAL_TRANSITION in st.corrupt_reasons


# ── F8: two concurrent admits race and both leave an occupying attempt ──────
def test_fault_two_concurrent_intents_both_occupying():
    with tempfile.TemporaryDirectory() as d:
        op = "op-f8"
        # simulate two racing launchers that both believed they held the gate
        # and each durably wrote their own AttemptIntent before either started.
        for n in (1, 2):
            aid = f"{op}#a{n}"
            wal.write_intent(d, aid, _bytes({
                "event_type": s.EventType.ATTEMPT_INTENT, "writer_role": "launcher",
                "attempt_id": aid, "logical_operation_id": op}))
        st = r.reduce(es.load_events(d), op)
        assert st.corrupt and r.F8_MULTIPLE_ACTIVE in st.corrupt_reasons


# ── F9: terminal claims FINAL_SUCCEEDED but omits required evidence axes ────
def test_fault_final_terminal_missing_evidence():
    with tempfile.TemporaryDirectory() as d:
        op = "op-f9"
        aid = f"{op}#a1"
        wal.write_intent(d, aid, _bytes({
            "event_type": s.EventType.ATTEMPT_INTENT, "writer_role": "launcher",
            "attempt_id": aid, "logical_operation_id": op}))
        wal.write_marker(d, aid, "started", _bytes({
            "event_type": s.EventType.ATTEMPT_STARTED, "writer_role": "wrapper",
            "attempt_id": aid, "logical_operation_id": op}))
        # a buggy terminal writer claims success without effect/output resolution.
        wal.write_terminal(d, aid, _bytes({
            "event_type": s.EventType.ATTEMPT_TERMINAL, "writer_role": "reducer",
            "attempt_id": aid, "logical_operation_id": op,
            "terminal_state": s.AttemptState.FINAL_SUCCEEDED,
            "finality_evidence": ["local_quiescence"]}))
        st = r.reduce(es.load_events(d), op)
        assert st.corrupt and r.F9_FINAL_MISSING_EVIDENCE in st.corrupt_reasons


# ── provenance: a superseded writer retries with a stale fencing token ──────
def test_fault_stale_generation_write_rejected_at_admission():
    # scenario: operation generation was bumped to 3 (e.g. after an operator
    # override reopened it) but a slow contestant/launcher still believes it
    # holds generation 1 and tries to write under that stale fencing token.
    prov = pv.Provenance(
        writer_identity="uid:501", writer_role="launcher",
        runtime_attestation_id="att-slow-writer", operation_fencing_token=1,
        parent_event_hash=None)
    assert _raises(pv.ProvenanceViolation, pv.verify_event_provenance,
                   s.EventType.ATTEMPT_INTENT, prov, current_generation=3)


# ── finality producer: fail-closed when quiescence was never confirmed ──────
def test_fault_finality_evidence_fails_closed_without_quiescence():
    # scenario: a terminal committer tries to seal FINAL_SUCCEEDED before the
    # process group's exit was actually confirmed (A1b: "timeout observed" is
    # not the same as "process ended"). The producer must refuse to fabricate
    # the evidence rather than let a false-positive quiescence claim through.
    assert _raises(fin.FinalityError, fin.build_finality_evidence,
                   s.AttemptState.FINAL_SUCCEEDED,
                   quiescence_confirmed=False,
                   effect_class=s.EffectClass.IDEMPOTENT_REMOTE,
                   effect_outcome="succeeded", output_outcome="valid")


# ── recovery gate: retry cap exhausted after a legitimate failed attempt ────
def test_fault_retry_cap_exhausted_refuses_further_admits():
    with tempfile.TemporaryDirectory() as d:
        op = "op-cap"
        rc, out = _run(rg.cmd_admit, _ns(events_dir=d, logical_operation_id=op, retry_cap=1))
        assert rc == 0 and out["admissible"]
        aid = out["attempt_id"]
        rc2, out2 = _run(rg.cmd_commit,
                          _ns(events_dir=d, logical_operation_id=op, attempt_id=aid, raw_rc=1))
        assert rc2 == 0 and out2["state"] == s.AttemptState.FINAL_FAILED

        rc3, out3 = _run(rg.cmd_admit, _ns(events_dir=d, logical_operation_id=op, retry_cap=1))
        assert rc3 == 3 and not out3["admissible"]
        assert "retry cap" in out3["reason"]


# ── recovery gate: timeout leaves an occupying UNRESOLVED attempt ───────────
def test_fault_timeout_leaves_operation_occupied_until_reconciled():
    with tempfile.TemporaryDirectory() as d:
        op = "op-timeout"
        rc, out = _run(rg.cmd_admit, _ns(events_dir=d, logical_operation_id=op, retry_cap=3))
        aid = out["attempt_id"]

        rc2, out2 = _run(rg.cmd_commit,
                          _ns(events_dir=d, logical_operation_id=op, attempt_id=aid, raw_rc=124))
        assert rc2 == 0 and out2["resolved"] is False
        assert out2["state"] == s.AttemptState.UNRESOLVED

        st = r.reduce(es.load_events(d), op)
        assert not st.corrupt
        assert st.occupying_attempt_ids == [aid]

        # a fresh dispatch attempt must be refused while the timeout is unresolved.
        rc3, out3 = _run(rg.cmd_admit, _ns(events_dir=d, logical_operation_id=op, retry_cap=3))
        assert rc3 == 3 and not out3["admissible"]
        assert "occupying" in out3["reason"]


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
