"""v4 runtime — W4 write-ahead log + atomic no-replace publish (V8 A1b/A4/A5b 승계).

설계 정본: PLUGIN_CUSTOM_DESIGN_V8.md → A4(atomic publish, 로컬 fs만, macOS F_FULLFSYNC) +
write-ahead 2단(attempt-intent O_EXCL+fsync → spawn → attempt-result) + "V7에서 승계" →
durability ordering(파일 fsync → **parent directory fsync** → spawn, atomic no-replace
publish, attempt-result를 terminal commit marker로).

이 모듈은 파일 IO만 한다(부작용 = 파일 IO만, 프로세스 spawn 없음). 표준 라이브러리만
(os, fcntl, hashlib, ctypes — 전부 stdlib) 사용한다.

핵심 불변식(여기서 코드화):
- attempt-intent는 정확히 1회 발행된다 — 같은 최종 경로가 이미 있으면 거부(O_EXCL 의미, A6의
  "AttemptIntent = accepted-preflight durable marker" 전제).
- attempt-result(terminal)는 정확히 1회 발행된다 — 같은 최종 경로가 이미 있으면 거부
  (A1b: 최종 terminal은 임의 writer가 재발행할 수 있는 사건이 아니다).
- publish 순서는 항상: 임시 파일에 전체 payload 기록 → file fsync → parent dir fsync →
  atomic no-replace publish(os.link, 대상 존재 시 FileExistsError) → parent dir fsync.
  이 순서가 아니면 partial write가 crash 후 최종 이름으로 보일 수 있다(A4).
- 로컬 파일시스템 전제 — 원격/네트워크 마운트가 감지되면 durability 보장이 약하다는 경고만
  낸다(비차단, best-effort 감지: 알 수 없는 fs는 조용히 통과, "안전 쪽으로 실패"는 조항이 아님 —
  로컬 fs 판별은 구현 세부(V8 (b))이므로 오탐이 쓰기를 막지 않는다).
"""

from __future__ import annotations

import ctypes
import ctypes.util
import fcntl
import os
import platform
import time
import warnings

WAL_SCHEMA_VERSION = "1"

INTENT_SUFFIX = ".intent.json"
TERMINAL_SUFFIX = ".terminal.json"


class WalError(Exception):
    """base error for this module."""


class DuplicateAttemptError(WalError):
    """final path already exists — write-once-per-final-name violated (attempt-intent
    또는 attempt-result가 두 번째로 발행됨). A1b/A6이 요구하는 exactly-once 보장의 위반이다."""


class NetworkFilesystemWarning(UserWarning):
    """dir이 로컬 fs가 아닌 것으로 감지됨 — durability ordering(fsync 등)의 보장이 약해진다."""


# ── platform helpers ────────────────────────────────────────────────────────

def _is_macos() -> bool:
    return platform.system() == "Darwin"


# known non-local (network/remote-backed) filesystem type names, by platform family.
_NETWORK_FSTYPES = frozenset({
    "nfs", "nfs4", "smbfs", "cifs", "afpfs", "webdav", "ftp", "sshfs", "fuse.sshfs",
})


class _MacStatfs(ctypes.Structure):
    # struct statfs (== statfs64 since macOS 10.6) from <sys/mount.h>. Field layout
    # is best-effort — any mismatch is caught by the caller and treated as unknown.
    _fields_ = [
        ("f_bsize", ctypes.c_uint32),
        ("f_iosize", ctypes.c_int32),
        ("f_blocks", ctypes.c_uint64),
        ("f_bfree", ctypes.c_uint64),
        ("f_bavail", ctypes.c_uint64),
        ("f_files", ctypes.c_uint64),
        ("f_ffree", ctypes.c_uint64),
        ("f_fsid", ctypes.c_uint8 * 8),
        ("f_owner", ctypes.c_uint32),
        ("f_type", ctypes.c_uint32),
        ("f_flags", ctypes.c_uint32),
        ("f_fssubtype", ctypes.c_uint32),
        ("f_fstypename", ctypes.c_char * 16),
        ("f_mntonname", ctypes.c_char * 1024),
        ("f_mntfromname", ctypes.c_char * 1024),
        ("f_reserved", ctypes.c_uint32 * 8),
    ]


def _detect_fstype(path: str) -> str | None:
    """best-effort filesystem type name for `path`'s containing mount, or None if
    undetectable. Never raises — detection failure means "unknown", not "network"."""
    if _is_macos():
        try:
            libc = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)
            libc.statfs.argtypes = [ctypes.c_char_p, ctypes.POINTER(_MacStatfs)]
            libc.statfs.restype = ctypes.c_int
            buf = _MacStatfs()
            rc = libc.statfs(os.fsencode(path), ctypes.byref(buf))
            if rc != 0:
                return None
            return buf.f_fstypename.decode("ascii", "replace").lower()
        except Exception:
            return None
    if platform.system() == "Linux":
        # /proc/mounts is file IO, not a process spawn — stays within "파일 IO만".
        try:
            real = os.path.realpath(path)
            best_match, best_type = "", None
            with open("/proc/mounts", "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    parts = line.split()
                    if len(parts) < 3:
                        continue
                    mnt_point, fstype = parts[1], parts[2]
                    if real.startswith(mnt_point) and len(mnt_point) >= len(best_match):
                        best_match, best_type = mnt_point, fstype
            return best_type.lower() if best_type else None
        except OSError:
            return None
    return None


def check_local_fs(dir_path: str) -> None:
    """best-effort local-fs guard (V8 A4: 로컬 fs만 지원). Warns (does not raise) when
    a known network filesystem type is detected; unknown/undetectable types pass
    silently — this is advisory, not a hard gate (durability semantics on unsupported
    fs are simply not guaranteed by this module)."""
    fstype = _detect_fstype(dir_path)
    if fstype is not None and fstype in _NETWORK_FSTYPES:
        warnings.warn(
            f"wal directory {dir_path!r} is on a network filesystem ({fstype!r}); "
            "fsync/F_FULLFSYNC durability ordering is not guaranteed on remote fs "
            "(V8 A4: local fs only).",
            NetworkFilesystemWarning,
            stacklevel=2,
        )


# ── durability primitives ───────────────────────────────────────────────────

def _fsync_fd(fd: int) -> None:
    """fsync with macOS F_FULLFSYNC preference. fsync(2) on macOS is documented as
    not necessarily flushing the drive's write cache; F_FULLFSYNC does. Falls back
    to plain fsync (with a warning) if F_FULLFSYNC is unavailable or fails — the
    write is not lost, but durability against power loss is weaker."""
    if _is_macos():
        try:
            fcntl.fcntl(fd, fcntl.F_FULLFSYNC)
            return
        except OSError as exc:
            warnings.warn(
                f"F_FULLFSYNC failed ({exc!r}); falling back to fsync(2) — "
                "durability guarantee is weaker on this filesystem/mount.",
                RuntimeWarning,
                stacklevel=3,
            )
    os.fsync(fd)


def fsync_dir(dir_path: str) -> None:
    """parent-directory durability. fsync(2) on a *file* fd does not guarantee the
    directory entry that names it (created by rename/link) is itself durable —
    POSIX requires fsync'ing the containing directory separately after a rename
    or link that must survive a crash (V8 durability ordering)."""
    fd = os.open(dir_path, os.O_RDONLY)
    try:
        _fsync_fd(fd)
    finally:
        os.close(fd)


def _write_temp_and_fsync(dir_path: str, payload: bytes) -> str:
    """write `payload` in full to a temp file inside dir_path, fsync the file,
    fsync the parent dir, and return the temp path. The temp name is never a
    valid final name (prefixed with '.' and a wal-specific tag + pid + monotonic
    counter) so a crash mid-write cannot leave a partial file visible under the
    final name."""
    tmp_name = f".wal-tmp-{os.getpid()}-{time.monotonic_ns()}"
    tmp_path = os.path.join(dir_path, tmp_name)
    fd = os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(payload)
            f.flush()
            _fsync_fd(f.fileno())
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
    fsync_dir(dir_path)
    return tmp_path


def _publish_no_replace(tmp_path: str, final_path: str, dir_path: str) -> None:
    """atomic no-replace publish: os.link never overwrites an existing target —
    it raises FileExistsError, which is exactly the O_EXCL semantics this module
    needs (attempt-intent/attempt-result must be write-once). The temp file is
    unlinked afterward regardless of outcome so it never accumulates."""
    try:
        os.link(tmp_path, final_path)
    except FileExistsError:
        raise DuplicateAttemptError(f"final path already exists: {final_path}") from None
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
    fsync_dir(dir_path)


def _write_once(dir_path: str, final_name: str, payload: bytes) -> str:
    check_local_fs(dir_path)
    final_path = os.path.join(dir_path, final_name)
    if os.path.exists(final_path):
        # fast-path rejection before doing any IO — still races safely with the
        # os.link no-replace check below, which is the real atomicity guarantee.
        raise DuplicateAttemptError(f"final path already exists: {final_path}")
    tmp_path = _write_temp_and_fsync(dir_path, payload)
    _publish_no_replace(tmp_path, final_path, dir_path)
    return final_path


# ── public API ───────────────────────────────────────────────────────────────

def write_intent(dir_path: str, attempt_id: str, payload: bytes) -> str:
    """write-ahead stage 1: AttemptIntent (= accepted-preflight durable marker, A6).

    Sequence: temp file full write → file fsync → parent dir fsync → atomic
    no-replace publish → parent dir fsync. Raises DuplicateAttemptError if an
    intent for this attempt_id was already published (write-once).

    `payload` must already be the fully-serialized bytes the caller wants durable
    (this module does no JSON encoding — schema.py owns the event shape).
    """
    if not isinstance(payload, (bytes, bytearray)):
        raise TypeError("payload must be bytes (caller serializes; wal.py does file IO only)")
    return _write_once(dir_path, f"{attempt_id}{INTENT_SUFFIX}", bytes(payload))


def write_terminal(dir_path: str, attempt_id: str, payload: bytes) -> str:
    """write-ahead stage 2: attempt-result as the terminal commit marker (A1b).

    Same durability sequence as write_intent. Raises DuplicateAttemptError if a
    terminal for this attempt_id was already published — terminal must be
    exactly 1 per attempt; this is the file-level enforcement of that invariant.
    Callers are responsible for embedding manifest/resolution hash references in
    `payload` per A1b (this module does not interpret payload contents).
    """
    if not isinstance(payload, (bytes, bytearray)):
        raise TypeError("payload must be bytes (caller serializes; wal.py does file IO only)")
    return _write_once(dir_path, f"{attempt_id}{TERMINAL_SUFFIX}", bytes(payload))


def write_marker(dir_path: str, attempt_id: str, kind: str, payload: bytes) -> str:
    """generic write-once event marker(started/uncertainty/resolution 등 3rd 이벤트용).

    intent/terminal과 동일한 durability sequence + write-once(같은 kind 재발행 시
    DuplicateAttemptError). `kind`는 파일명 안전한 토큰이어야 한다(경로 구분자 금지).
    payload는 caller가 직렬화한 event dict 바이트(이 모듈은 내용 해석 안 함).
    """
    if not isinstance(payload, (bytes, bytearray)):
        raise TypeError("payload must be bytes (caller serializes; wal.py does file IO only)")
    if not kind or "/" in kind or "." in kind or "\\" in kind:
        raise WalError(f"부적합 marker kind: {kind!r}")
    return _write_once(dir_path, f"{attempt_id}.{kind}.json", bytes(payload))


def intent_exists(dir_path: str, attempt_id: str) -> bool:
    return os.path.exists(os.path.join(dir_path, f"{attempt_id}{INTENT_SUFFIX}"))


def terminal_exists(dir_path: str, attempt_id: str) -> bool:
    return os.path.exists(os.path.join(dir_path, f"{attempt_id}{TERMINAL_SUFFIX}"))
