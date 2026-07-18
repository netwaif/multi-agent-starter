"""v4 runtime — recovery gate CLI (통합 마일스톤: dispatch 경로에 A6 gate 배선).

call_worker.sh가 dispatch 전후로 호출한다(opt-in: MULTIAGENT_OP_ID 있을 때만).
표준 라이브러리만. W7~W12 순수 모듈 + wal(파일 IO)를 조립하는 얇은 진입점.

두 모드:
- **admit** (spawn 전): events 로드→reduce→admit_new_intent(A6). 통과 시 AttemptIntent를 durable
  기록(wal.write_intent)한 뒤 attempt_id를 방출·exit 0. 거부 시 refusal JSON·exit 3(spawn 금지).
- **commit** (실행 후): AttemptStarted 기록 후, rc로 종료를 판정 —
  · rc0/일반오류 → finality 증거 조립(A1b) 후 AttemptTerminal(final) 기록.
  · **rc124(timeout) → effect 미상이므로 final 아님. AttemptUncertaintyObserved(UNRESOLVED) 기록**
    ("timeout 관측 ≠ 종료" A1b). 이 operation은 occupying으로 남아 다음 dispatch가 gate서 거부됨.
"""

from __future__ import annotations

import argparse
import json
import sys

import schema as s
import wal
import event_store as es
import reducer as rd
import finality as fin


def _event_bytes(d: dict) -> bytes:
    return json.dumps(d, ensure_ascii=False).encode("utf-8")


def _emit(obj: dict, code: int) -> int:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False))
    return code


def cmd_admit(a) -> int:
    events = es.load_events(a.events_dir)
    st = rd.reduce(events, a.logical_operation_id)
    n = es.next_attempt_number(events, a.logical_operation_id)
    decision = rd.admit_new_intent(st, retry_cap=a.retry_cap, next_attempt_number=n)
    if not decision.admissible:
        return _emit({
            "gate": "recovery_gate", "mode": "admit", "admissible": False,
            "reason": decision.reason, "logical_operation_id": a.logical_operation_id,
            "corrupt_reasons": st.corrupt_reasons,
        }, 3)
    attempt_id = f"{a.logical_operation_id}#a{n}"
    intent = {
        "event_type": s.EventType.ATTEMPT_INTENT, "writer_role": "launcher",
        "attempt_id": attempt_id, "logical_operation_id": a.logical_operation_id,
        "attempt_number": n,
    }
    # write-once: 같은 attempt intent 재발행이면 DuplicateAttemptError → 거부로 취급.
    try:
        wal.write_intent(a.events_dir, attempt_id, _event_bytes(intent))
    except wal.DuplicateAttemptError:
        return _emit({"gate": "recovery_gate", "mode": "admit", "admissible": False,
                      "reason": f"AttemptIntent 이미 존재: {attempt_id}"}, 3)
    return _emit({
        "gate": "recovery_gate", "mode": "admit", "admissible": True,
        "attempt_id": attempt_id, "attempt_number": n,
        "logical_operation_id": a.logical_operation_id,
    }, 0)


def cmd_commit(a) -> int:
    aid = a.attempt_id
    op = a.logical_operation_id
    base = {"attempt_id": aid, "logical_operation_id": op}

    # 프로세스는 실제로 시작됐다(call_worker가 spawn함) → AttemptStarted.
    started = {"event_type": s.EventType.ATTEMPT_STARTED, "writer_role": "wrapper", **base}
    try:
        wal.write_marker(a.events_dir, aid, "started", _event_bytes(started))
    except wal.DuplicateAttemptError:
        pass  # 재진입 시 이미 있으면 무해(write-once)

    if a.raw_rc == 124:
        # timeout: provider effect 미상 → final 아님. UNRESOLVED로 남긴다(A1b).
        unc = {"event_type": s.EventType.ATTEMPT_UNCERTAINTY_OBSERVED,
               "writer_role": "recovery_scanner", "kind": "in_doubt", **base}
        try:
            wal.write_marker(a.events_dir, aid, "uncertainty", _event_bytes(unc))
        except wal.DuplicateAttemptError:
            pass
        return _emit({"gate": "recovery_gate", "mode": "commit", "resolved": False,
                      "state": s.AttemptState.UNRESOLVED, "attempt_id": aid,
                      "note": "timeout → UNRESOLVED (effect 미상, A1b)"}, 0)

    if a.raw_rc == 0:
        term, effect_out, out_out = s.AttemptState.FINAL_SUCCEEDED, "succeeded", "valid"
    else:
        term, effect_out, out_out = s.AttemptState.FINAL_FAILED, "failed", "invalid"

    fe = fin.build_finality_evidence(
        term, quiescence_confirmed=True, effect_class=s.EffectClass.IDEMPOTENT_REMOTE,
        effect_outcome=effect_out, output_outcome=out_out)
    terminal = {"event_type": s.EventType.ATTEMPT_TERMINAL, "writer_role": "reducer",
                **base, **fe.to_terminal_fields()}
    try:
        wal.write_terminal(a.events_dir, aid, _event_bytes(terminal))
    except wal.DuplicateAttemptError:
        return _emit({"gate": "recovery_gate", "mode": "commit", "resolved": True,
                      "state": term, "attempt_id": aid, "note": "terminal 이미 존재(write-once)"}, 0)
    return _emit({"gate": "recovery_gate", "mode": "commit", "resolved": True,
                  "state": term, "attempt_id": aid}, 0)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="v4 recovery gate (A6) CLI")
    sub = p.add_subparsers(dest="mode", required=True)

    pa = sub.add_parser("admit")
    pa.add_argument("--events-dir", required=True)
    pa.add_argument("--logical-operation-id", required=True)
    pa.add_argument("--retry-cap", type=int, default=3)
    pa.set_defaults(func=cmd_admit)

    pc = sub.add_parser("commit")
    pc.add_argument("--events-dir", required=True)
    pc.add_argument("--logical-operation-id", required=True)
    pc.add_argument("--attempt-id", required=True)
    pc.add_argument("--raw-rc", type=int, required=True)
    pc.set_defaults(func=cmd_commit)

    a = p.parse_args(argv)
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
