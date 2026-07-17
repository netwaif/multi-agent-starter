"""v4 runtime — envelope v2 조립 (W6 dispatcher 배선점).

call_worker.sh(얇은 진입점)가 워커를 실행한 뒤 결과(rc/stdout/stderr/duration)를 이 모듈의
CLI로 넘긴다. 여기서 W2 classify + W3 outcome을 통합해 완전한 envelope v2를 만들고, 기존
v1 소비자를 위한 파생 legacy status(ok|error|timeout|empty)를 함께 방출한다.

설계 정본: PLUGIN_CUSTOM_DESIGN_V8.md §1.1(envelope v2 축) · §1.2(legacy 결정표) · §0(4.0은 물리
invocation마다 envelope v2 + aggregate/legacy summary). 표준 라이브러리만.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import schema as s
import classify as _classify
import outcome as _outcome

_PREVIEW_CAP = 2000  # sanitized preview 바이트 상한(원문은 artifact 파일에만)


def _file_stats(path: str | None):
    """이미 캡처된 stdout/stderr 파일에서 bytes·sha256·preview·text를 계산."""
    if not path:
        return {"bytes": 0, "sha256": None, "preview": "", "text": ""}
    p = Path(path)
    if not p.is_file():
        return {"bytes": 0, "sha256": None, "preview": "", "text": ""}
    data = p.read_bytes()
    text = data.decode("utf-8", errors="replace")
    return {
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "preview": text[:_PREVIEW_CAP],
        "text": text,
    }


def _process_status(raw_rc: int, timed_out: bool) -> str:
    # bash 래퍼가 줄 수 있는 최선 판정. 정확한 signal 구분은 (b) 구현 세부.
    if timed_out or raw_rc == 124:
        return s.ProcessStatus.WRAPPER_TIMEOUT
    if raw_rc is None:
        return s.ProcessStatus.WRAPPER_ERROR
    if raw_rc > 128:                    # 128+n = signal n으로 종료(관례)
        return s.ProcessStatus.SIGNALED
    return s.ProcessStatus.EXITED       # rc==0 이든 아니든 정상 종료(코드로 판정)


def build_envelope(
    *,
    worker_id: str,
    backend_route_id: str,
    call_type: str,
    cli_version: str | None,
    model_requested: str | None,
    model_observed: str | None,
    raw_rc: int,
    timed_out: bool,
    stdout_path: str | None,
    stderr_path: str | None,
    duration_s: int,
    result_contract: dict,
    preflight_status: str = s.PreflightStatus.ELIGIBLE,
    preflight_stage: str | None = None,
    preflight_reason: str = "none",
    structured_signal: dict | None = None,
    wrapper_signal: dict | None = None,
) -> dict:
    out = _file_stats(stdout_path)
    err = _file_stats(stderr_path)
    proc = _process_status(raw_rc, timed_out)

    # capture status: 파일이 존재하고 읽혔으면 ok(스트리밍 한계 초과 판정은 capture.py가
    # 라이브 캡처 시 담당; 여기 조립 단계는 이미 캡처 완료된 파일 기준).
    capture_status = s.CaptureStatus.OK if (stdout_path or stderr_path) else s.CaptureStatus.OK

    # output.status
    if preflight_status == s.PreflightStatus.INELIGIBLE:
        output_status = s.OutputStatus.NOT_PRODUCED
    elif out["bytes"] == 0:
        output_status = s.OutputStatus.OUTPUT_MISSING
    else:
        output_status = s.OutputStatus.PRESENT

    # W2 classify (신호 우선순위 5단)
    cls = _classify.classify(
        backend_id=backend_route_id.split("-")[0],  # route_id 접두 = backend family
        cli_version=cli_version,
        process_status=proc,
        raw_rc=raw_rc,
        signal=None,
        stdout_text=out["text"],
        stderr_text=err["text"],
        structured_signal=structured_signal,
        wrapper_signal=wrapper_signal,
    )

    # W3 result_contract 평가(preflight 거부·미실행이면 not_evaluated)
    if preflight_status == s.PreflightStatus.INELIGIBLE:
        rc_eval = {"status": s.ResultContractStatus.NOT_EVALUATED,
                   "validator_id": None, "reason": "output_not_produced"}
    else:
        rc_eval = _outcome.evaluate_result_contract(
            result_contract, out["bytes"] and out["text"].encode("utf-8") or None)

    envelope = {
        "schema_version": s.SCHEMA_VERSION,
        "identity": {
            "worker_id": worker_id,
            "backend_route_id": backend_route_id,
            "call_type": call_type,
            "cli_version": cli_version,
            "model_requested": model_requested,
            "model_observed": model_observed,   # 관측된 경우만(없으면 null)
        },
        "preflight": {
            "status": preflight_status,
            "stage": preflight_stage,
            "reason_code": preflight_reason,
            "reason_code_version": "1",
        },
        "process": {
            "status": proc,
            "raw_rc": None if preflight_status == s.PreflightStatus.INELIGIBLE else raw_rc,
            "signal": None,
        },
        "output": {
            "status": output_status,
            "stdout_path": stdout_path,
            "stdout_bytes": out["bytes"],
            "stdout_sha256": out["sha256"],
            "stdout_preview_sanitized": out["preview"],
            "stderr_path": stderr_path,
            "stderr_bytes": err["bytes"],
            "stderr_sha256": err["sha256"],
            "stderr_preview_sanitized": err["preview"],
        },
        "capture": {"status": capture_status, "reason": "none"},
        "result_contract": rc_eval,
        "classification": cls,
        "duration_s": duration_s,
    }

    # 파생 legacy status(기존 v1 소비자용, V8 §1.2 결정표)
    envelope["legacy_status"] = _outcome.legacy_status(envelope)
    envelope["ok"] = _outcome.is_ok(envelope)
    return envelope


def _main(argv=None):
    ap = argparse.ArgumentParser(description="build envelope v2 from an executed worker call")
    ap.add_argument("--worker-id", required=True)
    ap.add_argument("--backend-route-id", required=True)
    ap.add_argument("--call-type", required=True)
    ap.add_argument("--cli-version", default=None)
    ap.add_argument("--model-requested", default=None)
    ap.add_argument("--model-observed", default=None)
    ap.add_argument("--raw-rc", type=int, required=True)
    ap.add_argument("--timed-out", action="store_true")
    ap.add_argument("--stdout-path", default=None)
    ap.add_argument("--stderr-path", default=None)
    ap.add_argument("--duration-s", type=int, default=0)
    ap.add_argument("--min-non-whitespace", type=int, default=1)
    ap.add_argument("--preflight-status", default=s.PreflightStatus.ELIGIBLE)
    ap.add_argument("--preflight-stage", default=None)
    ap.add_argument("--preflight-reason", default="none")
    a = ap.parse_args(argv)

    env = build_envelope(
        worker_id=a.worker_id, backend_route_id=a.backend_route_id, call_type=a.call_type,
        cli_version=a.cli_version, model_requested=a.model_requested, model_observed=a.model_observed,
        raw_rc=a.raw_rc, timed_out=a.timed_out, stdout_path=a.stdout_path, stderr_path=a.stderr_path,
        duration_s=a.duration_s,
        result_contract={"mode": "text", "output_required": True,
                         "min_non_whitespace_chars": a.min_non_whitespace},
        preflight_status=a.preflight_status, preflight_stage=a.preflight_stage,
        preflight_reason=a.preflight_reason,
    )
    json.dump(env, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    sys.exit(_main())
