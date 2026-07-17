"""v4 runtime — W4 bounded output capture (V8 §7 output byte limits + overflow +
capture_status 승계).

설계 정본: PLUGIN_CUSTOM_DESIGN_V8.md → §7(output byte limits + overflow + capture_status).
schema.py의 CaptureStatus 상수를 그대로 쓴다. 표준 라이브러리만(os, fcntl, hashlib 및
필요한 순수-stdlib 모듈: re, signal, warnings — 전부 프로세스 spawn·네트워크 없음).

이 모듈은 스트림 하나(이미 열린 fd)를 읽어 **bounded record**를 만든다 — 원문 전체를
영구 저장하는 것은 이 모듈의 일이 아니다(그건 output-drop/wrapper 몫, A1b `output_sealed`
축). 여기서 만드는 건: byte_count(생산된 총 바이트) · streaming sha256(캡처된 구간의
해시) · bounded preview(민감정보 redact 후) · capture_status.

핵심 불변식(여기서 코드화):
- limit 이내로 끝난 스트림은 status=ok, sha256은 전체 내용의 sha256과 정확히 일치한다
  (스트리밍 해시가 전체 해시와 다르면 안 됨 — 이게 이 모듈의 정확성 기준이다).
- overflow_action="truncate": max_bytes를 넘는 바이트는 캡처(해시/미리보기)하지 않는다
  (그래서 이름이 truncated — 캡처된 접두 구간만큼의 해시), 단 상위 writer 데드락을 피하기
  위해 fd는 EOF까지 계속 drain한다(카운트는 계속 증가).
- overflow_action="terminate": limit 도달 즉시 읽기를 멈추고 process-group 종료 훅을 호출한다
  (호출자가 pid 또는 커스텀 훅을 넘김) — 이 경로는 fd를 끝까지 drain하지 않는다.
- read 중 OSError는 status=failed로 흡수한다(예외를 올리지 않음) — 캡처 실패가 WAL 발행
  자체를 막지 않도록.
"""

from __future__ import annotations

import hashlib
import os
import re
import signal

import schema as s

CAPTURE_SCHEMA_VERSION = "1"

DEFAULT_CHUNK_SIZE = 65536
DEFAULT_PREVIEW_BYTES = 4096

_OVERFLOW_ACTIONS = frozenset({"truncate", "terminate"})

# ── secret redaction (best-effort, applied to the bounded preview only) ─────
_REDACT_PATTERNS = [
    re.compile(r"(?i)(authorization:\s*bearer\s+)[A-Za-z0-9\-._~+/]+=*"),
    re.compile(r"(?i)(api[_-]?key\s*[:=]\s*['\"]?)[A-Za-z0-9\-._~+/]{12,}"),
    re.compile(r"sk-[A-Za-z0-9]{16,}"),                      # OpenAI/Anthropic-style secret keys
    re.compile(r"AKIA[0-9A-Z]{16}"),                          # AWS access key id
    re.compile(r"(?i)(secret|token|password)\s*[:=]\s*['\"]?[A-Za-z0-9\-._~+/]{8,}"),
]
_REDACTED = "[REDACTED]"


def redact(text: str) -> str:
    """best-effort secret redaction over preview text. Not a security boundary by
    itself — it reduces the odds a bounded preview leaks an obvious credential,
    nothing more. Full output stays wherever the wrapper's output-drop artifact
    lives, governed separately."""
    out = text
    for pattern in _REDACT_PATTERNS:
        if pattern.groups:
            out = pattern.sub(lambda m: m.group(1) + _REDACTED, out)
        else:
            out = pattern.sub(_REDACTED, out)
    return out


# ── process-group termination hook ──────────────────────────────────────────

def _default_terminate(pid: int) -> None:
    """SIGTERM the process group rooted at pid. Caller must have started the
    process in its own group (e.g. via start_new_session/os.setsid) for this to
    only affect the intended tree. Failures (already dead, no permission) are
    swallowed — the goal is best-effort stop, not a guarantee."""
    try:
        pgid = os.getpgid(pid)
        os.killpg(pgid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError, OSError):
        pass


# ── core bounded capture ────────────────────────────────────────────────────

def capture_stream(
    fd: int,
    max_bytes: int,
    *,
    preview_bytes: int = DEFAULT_PREVIEW_BYTES,
    overflow_action: str = "truncate",
    pid: int | None = None,
    on_limit_exceeded=None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> dict:
    """read `fd` to EOF (or until a limit-triggered stop) producing a bounded
    capture record.

    max_bytes: hard cap on how many bytes are captured (hashed + previewed).
               Bytes beyond this are counted but not captured when
               overflow_action == "truncate"; when overflow_action ==
               "terminate", reading stops at the limit instead.
    overflow_action: "truncate" (keep draining, don't capture past max_bytes)
                      or "terminate" (stop reading, kill the producer).
    pid: if given and overflow_action == "terminate", os.killpg(pid's pgid) is
         called on limit. Ignored for "truncate".
    on_limit_exceeded: optional callable(byte_count) invoked once when the
         limit is first crossed, in addition to (or instead of, if pid is
         None) the pid-based termination. Never raises past this function —
         hook errors are swallowed (a broken hook must not corrupt capture).

    Returns:
      {
        "capture_status": CaptureStatus.OK | TRUNCATED | LIMIT_EXCEEDED | FAILED,
        "byte_count": int,            # total bytes observed on the stream
        "captured_byte_count": int,   # bytes actually hashed/previewed (<= max_bytes)
        "sha256": str,                # hex digest over the captured prefix
        "preview_sanitized": str,     # bounded, redacted, utf-8-decoded preview
        "overflow": bool,             # byte_count > max_bytes
        "error": str | None,          # set only when capture_status == failed
      }
    """
    if overflow_action not in _OVERFLOW_ACTIONS:
        raise ValueError(f"overflow_action must be one of {_OVERFLOW_ACTIONS!r}")

    hasher = hashlib.sha256()
    byte_count = 0
    captured_byte_count = 0
    preview_parts: list[bytes] = []
    preview_len = 0
    limit_hook_fired = False
    status = s.CaptureStatus.OK
    error: str | None = None

    def _fire_limit_hook() -> None:
        nonlocal limit_hook_fired
        if limit_hook_fired:
            return
        limit_hook_fired = True
        if pid is not None:
            _default_terminate(pid)
        if on_limit_exceeded is not None:
            try:
                on_limit_exceeded(byte_count)
            except Exception:
                pass  # a broken caller hook must not corrupt the capture result

    try:
        while True:
            # Cap the request size near the remaining capacity so a single
            # os.read() doesn't blow far past max_bytes in one gulp — without
            # this, "terminate" couldn't stop reading "near the limit" (a
            # single read() can return an entire already-buffered pipe's
            # contents). Once at/over capacity, request just a small probe
            # chunk purely to detect further data / decide truncate-drain vs
            # terminate-stop.
            request_size = (
                min(chunk_size, max_bytes - captured_byte_count + 1)
                if captured_byte_count < max_bytes
                else min(chunk_size, DEFAULT_CHUNK_SIZE)
            )
            try:
                chunk = os.read(fd, max(request_size, 1))
            except OSError as exc:
                status = s.CaptureStatus.FAILED
                error = repr(exc)
                break

            if not chunk:
                break  # EOF

            n = len(chunk)
            remaining_capacity = max_bytes - captured_byte_count
            if remaining_capacity > 0:
                to_capture = chunk[:remaining_capacity]
                hasher.update(to_capture)
                captured_byte_count += len(to_capture)
                if preview_len < preview_bytes:
                    take = to_capture[: preview_bytes - preview_len]
                    preview_parts.append(take)
                    preview_len += len(take)

            byte_count += n

            if byte_count > max_bytes:
                if overflow_action == "terminate":
                    status = s.CaptureStatus.LIMIT_EXCEEDED
                    _fire_limit_hook()
                    break  # do not drain further — producer is being stopped
                else:
                    status = s.CaptureStatus.TRUNCATED
                    # keep looping to drain the fd (avoid upstream writer deadlock);
                    # bytes beyond max_bytes are counted but never captured.
    except Exception as exc:  # defensive: any unexpected failure -> failed, not a crash
        status = s.CaptureStatus.FAILED
        error = repr(exc)

    preview_raw = b"".join(preview_parts)
    preview_text = preview_raw.decode("utf-8", errors="replace")

    return {
        "capture_status": status,
        "byte_count": byte_count,
        "captured_byte_count": captured_byte_count,
        "sha256": hasher.hexdigest(),
        "preview_sanitized": redact(preview_text),
        "overflow": byte_count > max_bytes,
        "error": error,
    }


def capture_combined(
    stdout_fd: int,
    stderr_fd: int,
    *,
    max_stdout_bytes: int,
    max_stderr_bytes: int,
    max_combined_bytes: int,
    preview_bytes: int = DEFAULT_PREVIEW_BYTES,
    overflow_action: str = "truncate",
    pid: int | None = None,
    on_limit_exceeded=None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> dict:
    """capture stdout and stderr each under their own per-stream cap, then apply
    a combined cap on top. Streams are drained sequentially (stdout fully, then
    stderr) — callers feeding this from a *live* process must have already
    multiplexed/drained concurrently upstream (e.g. via select/poll or one
    thread per fd) to avoid pipe-buffer deadlock; this function's job is
    bounding + hashing + redaction, not process IO scheduling.

    Returns {"stdout": <capture_stream() result>, "stderr": <capture_stream()
    result>, "capture_status": combined status, "combined_byte_count": int}.
    combined capture_status is the worst of (stdout, stderr, combined-limit
    check) using priority failed > limit_exceeded > truncated > ok.
    """
    stdout_result = capture_stream(
        stdout_fd, max_stdout_bytes,
        preview_bytes=preview_bytes, overflow_action=overflow_action,
        pid=pid, on_limit_exceeded=on_limit_exceeded, chunk_size=chunk_size,
    )
    stderr_result = capture_stream(
        stderr_fd, max_stderr_bytes,
        preview_bytes=preview_bytes, overflow_action=overflow_action,
        pid=pid, on_limit_exceeded=on_limit_exceeded, chunk_size=chunk_size,
    )

    combined_byte_count = stdout_result["byte_count"] + stderr_result["byte_count"]
    combined_over = combined_byte_count > max_combined_bytes

    _PRIORITY = {
        s.CaptureStatus.FAILED: 3,
        s.CaptureStatus.LIMIT_EXCEEDED: 2,
        s.CaptureStatus.TRUNCATED: 1,
        s.CaptureStatus.OK: 0,
    }
    worst = max(
        stdout_result["capture_status"], stderr_result["capture_status"],
        key=lambda st: _PRIORITY[st],
    )
    if combined_over and _PRIORITY[worst] < _PRIORITY[s.CaptureStatus.TRUNCATED]:
        worst = s.CaptureStatus.TRUNCATED

    return {
        "stdout": stdout_result,
        "stderr": stderr_result,
        "capture_status": worst,
        "combined_byte_count": combined_byte_count,
        "combined_overflow": combined_over,
    }
