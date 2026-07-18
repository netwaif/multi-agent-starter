"""게이트 — event_store 로더 + wal.write_marker(generic write-once). 하우스 자체러너."""
import json, os, sys, pathlib, tempfile, shutil
_GEN = pathlib.Path(__file__).resolve().parents[2] / \
    "plugins/multi-agent-starter/skills/configure-multiagent/generator/templates/claude/_shared/runtime"
sys.path.insert(0, str(_GEN))
import event_store as es
import wal


def _raises(exc, fn, *a, **kw):
    try:
        fn(*a, **kw)
    except exc:
        return True
    return False


class _Tmp:
    def __enter__(self):
        self.d = tempfile.mkdtemp(); return self.d
    def __exit__(self, *x):
        shutil.rmtree(self.d, ignore_errors=True)


def _ev(dir_, aid, kind, event_type, **extra):
    d = {"event_type": event_type, "attempt_id": aid, "logical_operation_id": "op", **extra}
    wal.write_marker(dir_, aid, kind, json.dumps(d).encode("utf-8"))


# ── load_events ─────────────────────────────────────────────────────────────
def test_load_missing_dir_empty():
    assert es.load_events("/nonexistent/xyz") == []

def test_load_reads_event_dicts_only():
    with _Tmp() as d:
        _ev(d, "op#a1", "intent", "AttemptIntent")
        _ev(d, "op#a1", "started", "AttemptStarted")
        # event_type 없는 잡파일은 무시
        with open(os.path.join(d, "notes.json"), "w") as f:
            json.dump({"hello": 1}, f)
        evs = es.load_events(d)
        assert len(evs) == 2
        assert {e["event_type"] for e in evs} == {"AttemptIntent", "AttemptStarted"}

def test_load_skips_non_json():
    with _Tmp() as d:
        _ev(d, "op#a1", "intent", "AttemptIntent")
        with open(os.path.join(d, "junk.txt"), "w") as f:
            f.write("not json")
        assert len(es.load_events(d)) == 1


# ── next_attempt_number ─────────────────────────────────────────────────────
def test_next_attempt_empty_is_1():
    assert es.next_attempt_number([], "op") == 1

def test_next_attempt_from_max():
    evs = [{"logical_operation_id": "op", "attempt_id": "op#a1"},
           {"logical_operation_id": "op", "attempt_id": "op#a3"},
           {"logical_operation_id": "other", "attempt_id": "other#a9"}]  # 다른 op 무시
    assert es.next_attempt_number(evs, "op") == 4

def test_next_attempt_ignores_malformed_ids():
    evs = [{"logical_operation_id": "op", "attempt_id": "op#aXX"},
           {"logical_operation_id": "op", "attempt_id": "op#a2"}]
    assert es.next_attempt_number(evs, "op") == 3


# ── wal.write_marker: write-once + kind 검증 ────────────────────────────────
def test_write_marker_once():
    with _Tmp() as d:
        wal.write_marker(d, "op#a1", "started", b'{"event_type":"AttemptStarted"}')
        assert os.path.exists(os.path.join(d, "op#a1.started.json"))
        assert _raises(wal.DuplicateAttemptError, wal.write_marker, d, "op#a1", "started", b'x')

def test_write_marker_rejects_bad_kind():
    with _Tmp() as d:
        assert _raises(wal.WalError, wal.write_marker, d, "op#a1", "bad/kind", b'x')
        assert _raises(wal.WalError, wal.write_marker, d, "op#a1", "dot.kind", b'x')


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
