"""v4 runtime — W3 result_contract + legacy status 결정표 (V8 확정설계 §1.2/§1.3 승계).

설계 정본: PLUGIN_CUSTOM_DESIGN_V8.md → "V7에서 승계" → V4 §1.2(legacy status 순서 결정표) /
§1.3(result_contract) — V6 §5에서 어휘만 `admission.*` → `preflight.*`로 개정, ok 완전조건에
`capture.status == ok`가 추가되었다(V5에서 누락됐던 축).

이 모듈은 데이터 검증만 담는다(부작용 없음). schema.py의 상수를 그대로 쓴다. 표준 라이브러리만.

핵심 불변식(여기서 코드화):
- text contract 충족 = UTF-8 decode 성공 ∧ trim 후 non-whitespace 길이 ≥ min_non_whitespace_chars.
  ("\n" 한 바이트가 present로 새는 것을 차단 — V4 §1.3.)
- legacy_status는 **순서 있는 결정표**다 — 위에서부터 첫 매치만 채택한다(V4 §1.2, GPT #2).
  rc0 + "권한이 거부되어 파일을 읽을 수 없었습니다" 같은 non-empty permission denial 응답이
  다시 ok로 위양성 판정되는 것(E3 계열)을 이 순서가 차단한다.
- is_ok는 legacy_status의 "ok"보다 **엄격한 완전조건**이다 — capture.status == ok가 legacy
  결정표에는 없지만 is_ok에는 반드시 있다(V6 §5, V5에서 빠졌던 축 보강).
"""

from __future__ import annotations

import schema as s

# ── (A) result_contract 검증 ────────────────────────────────────────────────

_TEXT_CONTRACT_VALIDATOR_ID = "text_contract_v1"


def evaluate_result_contract(contract: dict, stdout_bytes: bytes | None) -> dict:
    """result_contract를 stdout 원문 bytes로 검증한다. 순수 함수, 부작용 없음.

    contract: {"mode": "text", "output_required": bool, "min_non_whitespace_chars": int}
    stdout_bytes: 실제 캡처된 stdout 원문(존재하지 않으면 None — 프로세스가 output을
                  전혀 생산하지 못한 경우, whitespace-only와는 다른 사유로 구분한다).

    반환: {"status": ResultContractStatus.*, "validator_id": str, "reason": str | None}
    reason 값: None(satisfied) | "invalid_utf8" | "insufficient_non_whitespace" |
               "output_not_produced" | "unsupported_mode"
    """
    mode = contract.get("mode")

    if mode != "text":
        # 현재 이 runtime은 text contract만 안다 — 다른 mode는 미평가로 보수적 처리.
        return {
            "status": s.ResultContractStatus.NOT_EVALUATED,
            "validator_id": _TEXT_CONTRACT_VALIDATOR_ID,
            "reason": "unsupported_mode",
        }

    if stdout_bytes is None:
        # 실행 자체가 output을 만들지 못했다(≠ whitespace-only present output).
        return {
            "status": s.ResultContractStatus.UNSATISFIED,
            "validator_id": _TEXT_CONTRACT_VALIDATOR_ID,
            "reason": "output_not_produced",
        }

    try:
        text = stdout_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return {
            "status": s.ResultContractStatus.UNSATISFIED,
            "validator_id": _TEXT_CONTRACT_VALIDATOR_ID,
            "reason": "invalid_utf8",
        }

    min_non_whitespace_chars = contract.get("min_non_whitespace_chars", 1)
    non_whitespace_len = len(text.strip())
    if non_whitespace_len < min_non_whitespace_chars:
        # "\n" 한 바이트만 있어도 decode는 성공하고 present이지만, trim 후 길이 0이므로
        # 여기서 걸린다 — present로 새는 것을 차단하는 지점(V4 §1.3).
        return {
            "status": s.ResultContractStatus.UNSATISFIED,
            "validator_id": _TEXT_CONTRACT_VALIDATOR_ID,
            "reason": "insufficient_non_whitespace",
        }

    return {
        "status": s.ResultContractStatus.SATISFIED,
        "validator_id": _TEXT_CONTRACT_VALIDATOR_ID,
        "reason": None,
    }


# ── (B) legacy status 결정표 (V4 §1.2, 순서 있음 — 위에서부터 첫 매치) ──────


def _classification_is_high_confidence_failure(classification: dict) -> bool:
    failure_class = classification.get("failure_class")
    confidence = classification.get("confidence")
    return failure_class not in (None, s.FailureClass.NONE) and confidence == "high"


def legacy_status(envelope: dict) -> str:
    """envelope(v2) → legacy 4-way status ("ok"|"error"|"timeout"|"empty").

    순서 있는 결정표 — 위에서부터 첫 매치가 채택된다(V4 §1.2):
      1. preflight.ineligible                                  → error
      2. process.wrapper_timeout                                → timeout
      3. process ≠ exited 또는 raw_rc ≠ 0                        → error
      4. failure_class ≠ none (high confidence)                 → error
      5. result_contract 불충족(status != satisfied)             → empty
      6. 그 외                                                    → ok
    """
    preflight = envelope.get("preflight", {}) or {}
    process = envelope.get("process", {}) or {}
    classification = envelope.get("classification", {}) or {}
    result_contract = envelope.get("result_contract", {}) or {}

    # 1. preflight.ineligible → error
    if preflight.get("status") == s.PreflightStatus.INELIGIBLE:
        return "error"

    # 2. process.wrapper_timeout → timeout
    if process.get("status") == s.ProcessStatus.WRAPPER_TIMEOUT:
        return "timeout"

    # 3. process ≠ exited 또는 raw_rc ≠ 0 → error
    if process.get("status") != s.ProcessStatus.EXITED or process.get("raw_rc") != 0:
        return "error"

    # 4. failure_class ≠ none (high confidence) → error
    if _classification_is_high_confidence_failure(classification):
        return "error"

    # 5. result_contract 불충족 → empty
    if result_contract.get("status") != s.ResultContractStatus.SATISFIED:
        return "empty"

    # 6. 그 외 → ok
    return "ok"


# ── (C) ok 완전조건 (V6 §5 — legacy_status의 "ok"보다 엄격) ────────────────

_OK_CLASSIFICATION_STATUSES = frozenset(
    {s.ClassificationStatus.CLASSIFIED, s.ClassificationStatus.NOT_NEEDED}
)


def is_ok(envelope: dict) -> bool:
    """ok 완전조건(V6 §5, capture.status==ok 포함 — V5에서 빠졌던 축):

    preflight.eligible ∧ process.exited ∧ raw_rc==0 ∧ capture.status==ok ∧
    result_contract.status==satisfied ∧
    classification.status ∈ {classified, not_needed} ∧ failure_class==none.
    """
    preflight = envelope.get("preflight", {}) or {}
    process = envelope.get("process", {}) or {}
    capture = envelope.get("capture", {}) or {}
    result_contract = envelope.get("result_contract", {}) or {}
    classification = envelope.get("classification", {}) or {}

    return (
        preflight.get("status") == s.PreflightStatus.ELIGIBLE
        and process.get("status") == s.ProcessStatus.EXITED
        and process.get("raw_rc") == 0
        and capture.get("status") == s.CaptureStatus.OK
        and result_contract.get("status") == s.ResultContractStatus.SATISFIED
        and classification.get("status") in _OK_CLASSIFICATION_STATUSES
        and classification.get("failure_class", s.FailureClass.NONE) == s.FailureClass.NONE
    )
