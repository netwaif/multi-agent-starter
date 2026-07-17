"""W4 게이트 — write-ahead log(atomic no-replace publish) + bounded output capture
(V8 A1b/A4/A5b 승계, §7). 실제 파일 IO(tempfile.mkdtemp)로 검증한다."""
import hashlib
import os
import pathlib
import shutil
import sys
import tempfile

_GEN = pathlib.Path(__file__).resolve().parents[2] / \
    "plugins/multi-agent-starter/skills/configure-multiagent/generator/templates/claude/_shared/runtime"
sys.path.insert(0, str(_GEN))
import schema as s   # noqa: E402
import wal           # noqa: E402
import capture        # noqa: E402


# ── test harness helpers ────────────────────────────────────────────────────

class _TmpDir:
    def __enter__(self):
        self.path = tempfile.mkdtemp(prefix="wal-w4-test-")
        return self.path

    def __exit__(self, *exc):
        shutil.rmtree(self.path, ignore_errors=True)


# ── (A) write_intent — write-once (O_EXCL semantics) ────────────────────────

def test_write_intent_creates_final_file():
    with _TmpDir() as d:
        path = wal.write_intent(d, "attempt-1", b'{"attempt_id": "attempt-1"}')
        assert os.path.exists(path)
        assert path == os.path.join(d, "attempt-1.intent.json")
        with open(path, "rb") as f:
            assert f.read() == b'{"attempt_id": "attempt-1"}'


def test_write_intent_second_write_rejected():
    with _TmpDir() as d:
        wal.write_intent(d, "attempt-1", b"first")
        try:
            wal.write_intent(d, "attempt-1", b"second")
            raised = False
        except wal.DuplicateAttemptError:
            raised = True
        assert raised, "second write_intent for the same attempt_id must be rejected"
        # first write's content must be untouched by the rejected second attempt
        with open(os.path.join(d, "attempt-1.intent.json"), "rb") as f:
            assert f.read() == b"first"


# ── (B) write_terminal — write-once, independent namespace from intent ──────

def test_write_terminal_creates_final_file():
    with _TmpDir() as d:
        path = wal.write_terminal(d, "attempt-1", b'{"state": "FINAL_SUCCEEDED"}')
        assert os.path.exists(path)
        assert path == os.path.join(d, "attempt-1.terminal.json")


def test_write_terminal_duplicate_rejected():
    with _TmpDir() as d:
        wal.write_terminal(d, "attempt-1", b"first-terminal")
        try:
            wal.write_terminal(d, "attempt-1", b"second-terminal")
            raised = False
        except wal.DuplicateAttemptError:
            raised = True
        assert raised, "terminal must be exactly 1 per attempt — second write must be rejected"


def test_intent_and_terminal_do_not_collide():
    with _TmpDir() as d:
        # same attempt_id, different final names (.intent.json vs .terminal.json) —
        # writing both must succeed since they don't share a final path.
        wal.write_intent(d, "attempt-1", b"intent-payload")
        wal.write_terminal(d, "attempt-1", b"terminal-payload")
        assert wal.intent_exists(d, "attempt-1")
        assert wal.terminal_exists(d, "attempt-1")


# ── (C) partial file never visible under the final name (temp-file proof) ───

def test_no_partial_file_visible_at_final_name_after_write():
    with _TmpDir() as d:
        wal.write_intent(d, "attempt-2", b"x" * 10000)
        entries = os.listdir(d)
        # only the final published name should remain — no leftover .wal-tmp-* file.
        assert entries == ["attempt-2.intent.json"], entries


def test_temp_file_used_and_cleaned_on_duplicate_rejection():
    with _TmpDir() as d:
        wal.write_intent(d, "attempt-3", b"first")
        try:
            wal.write_intent(d, "attempt-3", b"second")
        except wal.DuplicateAttemptError:
            pass
        entries = os.listdir(d)
        # rejection must not leave a temp file behind, and must not create a
        # second/partial visible entry under (or near) the final name.
        assert entries == ["attempt-3.intent.json"], entries


def test_fsync_dir_does_not_raise_on_real_dir():
    with _TmpDir() as d:
        wal.fsync_dir(d)  # must not raise


# ── (D) bounded output capture — within-limit content hashes match full hash ─

def test_capture_stream_hash_matches_full_content_hash_when_within_limit():
    payload = b"hello world\n" * 100  # well within limits
    r_fd, w_fd = os.pipe()
    os.write(w_fd, payload)
    os.close(w_fd)
    try:
        result = capture.capture_stream(r_fd, max_bytes=1_000_000)
    finally:
        os.close(r_fd)

    assert result["capture_status"] == s.CaptureStatus.OK
    assert result["byte_count"] == len(payload)
    assert result["captured_byte_count"] == len(payload)
    assert result["sha256"] == hashlib.sha256(payload).hexdigest()
    assert "hello world" in result["preview_sanitized"]


def test_capture_stream_truncated_when_over_limit():
    payload = b"A" * 5000
    max_bytes = 1000
    r_fd, w_fd = os.pipe()
    os.write(w_fd, payload)
    os.close(w_fd)
    try:
        result = capture.capture_stream(r_fd, max_bytes=max_bytes, overflow_action="truncate")
    finally:
        os.close(r_fd)

    assert result["capture_status"] == s.CaptureStatus.TRUNCATED
    assert result["overflow"] is True
    assert result["byte_count"] == len(payload)           # full stream still drained/counted
    assert result["captured_byte_count"] == max_bytes     # but only the prefix was captured
    assert result["sha256"] == hashlib.sha256(payload[:max_bytes]).hexdigest()


def test_capture_stream_limit_exceeded_with_terminate_stops_reading():
    payload = b"B" * 5000
    max_bytes = 1000
    r_fd, w_fd = os.pipe()
    os.write(w_fd, payload)
    os.close(w_fd)
    hook_calls = []
    try:
        result = capture.capture_stream(
            r_fd, max_bytes=max_bytes, overflow_action="terminate",
            on_limit_exceeded=lambda n: hook_calls.append(n),
        )
    finally:
        os.close(r_fd)

    assert result["capture_status"] == s.CaptureStatus.LIMIT_EXCEEDED
    assert len(hook_calls) == 1
    # terminate path stops reading at/near the limit rather than draining to EOF —
    # captured_byte_count is capped at max_bytes and byte_count did not reach the
    # full 5000 bytes written (reading stopped early).
    assert result["captured_byte_count"] == max_bytes
    assert result["byte_count"] < len(payload)


def test_capture_stream_empty_stream_is_ok():
    r_fd, w_fd = os.pipe()
    os.close(w_fd)  # immediate EOF, no data
    try:
        result = capture.capture_stream(r_fd, max_bytes=100)
    finally:
        os.close(r_fd)
    assert result["capture_status"] == s.CaptureStatus.OK
    assert result["byte_count"] == 0
    assert result["sha256"] == hashlib.sha256(b"").hexdigest()


def test_redact_masks_bearer_token_in_preview():
    payload = b"Authorization: Bearer sk-abcdefghijklmnopqrstuvwx\nok"
    r_fd, w_fd = os.pipe()
    os.write(w_fd, payload)
    os.close(w_fd)
    try:
        result = capture.capture_stream(r_fd, max_bytes=1_000_000)
    finally:
        os.close(r_fd)
    assert "sk-abcdefghijklmnopqrstuvwx" not in result["preview_sanitized"]
    assert "[REDACTED]" in result["preview_sanitized"]


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
