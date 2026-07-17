"""v4 runtime — W2 classifier (backend x version 신호 우선순위 5단, V8 §5 / V6 §5 승계).

설계 정본: PLUGIN_CUSTOM_DESIGN_V8.md §"V7에서 승계" → V6 §5 "classifier 신호 우선순위".
schema.py의 FailureClass / ClassificationStatus 상수를 그대로 쓴다. 표준 라이브러리만, 부작용 없음.

신호 우선순위(위에서부터, 첫 매치가 채택):
  1. provider/CLI structured status/error         — `structured_signal` 인자(훅, 아직 실제 발행자 없음)
  2. wrapper-owned spawn/timeout/signal/capture fact — `wrapper_signal` 인자(훅, 아직 실제 발행자 없음)
  3. exact documented exit-code mapping            — backend x version 레지스트리
  4. version-scoped stdout+stderr matcher          — stdout·stderr 둘 다 대상(V6 §5 강조)
  5. unclassified

confidence 규칙(V8 §5): 구체 failure_class(permission/auth/quota/rate_limited/transport)는
high confidence 매치일 때만 발행한다. low/medium 매치는 증거로 남기되(matched_rule_id에 기록)
failure_class는 UNKNOWN, status는 UNCLASSIFIED로 보수적으로 떨어진다.

미등록 backend 또는 미등록 version → ClassificationStatus.UNSUPPORTED_VERSION
(generic 추측 금지 — 어떤 tier도 시도하지 않는다. tier1/2 외부 훅만 예외적으로 여전히 존중한다:
 provider/wrapper가 이미 구조화된 고신뢰 신호를 준 경우에는 이 classifier가 CLI 텍스트를 몰라도
 판정 가능하기 때문).
"""

from __future__ import annotations

import re

import schema as s


# ── backend x version 레지스트리 ────────────────────────────────────────────
# 각 backend_id → 버전-스코프 항목 리스트. 항목 하나가 하나의 "classifier"(예: classify_agy_1_1_x)에
# 대응한다. version_prefixes는 "1.1" 같은 prefix 문자열 — cli_version이 prefix와 같거나
# "<prefix>."로 시작하면 그 항목을 채택한다(1.1.x 전부 커버).
#
# exit_code_map: {raw_rc: (failure_class, rule_id)} — exact documented exit-code만. 문서화되지
#   않은 rc는 여기 넣지 않는다(추측 금지) — tier4로 넘어간다.
# text_rules: [{"rule_id", "pattern": compiled regex, "failure_class", "confidence"}]
#   confidence는 "high" 아니면 "low"/"medium" — high만 발행된다(위 규칙).
#
# ★agy 1.1.x 실측 fixture(브리프 근거): stderr에
#   "a tool required the ... permission ... auto-denied" 류 문구가 있으면 permission/high.
_AGY_1_1_X = {
    "version_prefixes": ["1.1"],
    "classifier_id": "classify_agy_1_1_x",
    "exit_code_map": {},
    "text_rules": [
        {
            "rule_id": "agy_1_1_x_permission_auto_denied",
            "pattern": re.compile(
                r"a tool required the .*? permission.*?auto[-\s]?denied", re.IGNORECASE | re.DOTALL
            ),
            "failure_class": s.FailureClass.PERMISSION,
            "confidence": "high",
        },
        # 예시: "quota" 단어만으로는 저신뢰 — 구체적 고신뢰 문구가 아니면 발행 금지(§5 confidence 규칙).
        {
            "rule_id": "agy_1_1_x_quota_word_low_confidence",
            "pattern": re.compile(r"\bquota\b", re.IGNORECASE),
            "failure_class": s.FailureClass.QUOTA,
            "confidence": "low",
        },
    ],
}

# 실패 fixture가 아직 없는 backend를 위한 최소 등록. version_prefixes=["*"](버전 무관)로,
# 실패 rule은 비어 있다. 의미: "이 backend/CLI는 안다. 실패 시그니처 corpus는 아직 없다."
# 결과적으로 rc0 정상 종료는 실패 신호 부재로 none(성공), rc≠0/비정상은 unclassified(자동 성공
# 인정 안 함)로 떨어진다. 실측 fixture가 나오면 version-scoped entry를 이 앞에 추가한다.
def _generic_entry(classifier_id: str) -> dict:
    return {"version_prefixes": ["*"], "classifier_id": classifier_id,
            "exit_code_map": {}, "text_rules": []}


REGISTRY: dict[str, list[dict]] = {
    # agy는 1.1.x fixture가 있으므로 그 버전만 엄격 지원(다른 버전은 의도적으로 unsupported —
    # "미지원 버전 generic 추측 금지" V8 §5). generic fallback을 넣지 않는다.
    "agy": [_AGY_1_1_X],
    # codex/claude/grok은 실패 fixture 미확보 → generic 최소 등록(성공 판정은 가능, 실패는
    # unclassified). 실측 fixture 확보 시 version-scoped entry를 각 리스트 앞에 추가한다.
    "codex": [_generic_entry("classify_codex_generic")],
    "claude": [_generic_entry("classify_claude_generic")],
    "grok": [_generic_entry("classify_grok_generic")],
}


def _find_entry(backend_id: str, cli_version: str | None) -> dict | None:
    cli_version = cli_version or ""
    for entry in REGISTRY.get(backend_id, []):
        for prefix in entry["version_prefixes"]:
            if prefix == "*":                    # 버전 무관 최소 등록
                return entry
            if cli_version == prefix or cli_version.startswith(prefix + "."):
                return entry
    return None


def _from_external_signal(signal: dict | None, source_id: str) -> dict | None:
    """tier1/tier2 훅 공통 처리. signal={'failure_class':..., 'confidence':..., 'rule_id':...}.

    high confidence일 때만 채택한다(§5 confidence 규칙은 외부 신호에도 동일 적용).
    """
    if not signal:
        return None
    fc = signal.get("failure_class")
    conf = signal.get("confidence")
    if conf != "high" or not fc or fc == s.FailureClass.NONE:
        return None
    return {
        "status": s.ClassificationStatus.CLASSIFIED,
        "failure_class": fc,
        "classifier_id": source_id,
        "matched_rule_id": signal.get("rule_id", source_id),
        "confidence": "high",
    }


def classify(
    backend_id: str,
    cli_version: str,
    process_status: str,
    raw_rc: int | None,
    signal: str | None,
    stdout_text: str,
    stderr_text: str,
    structured_signal: dict | None = None,
    wrapper_signal: dict | None = None,
) -> dict:
    """5단 신호 우선순위로 failure_class를 판정한다. 순수 함수, 부작용 없음.

    반환: {status, failure_class, classifier_id, matched_rule_id, confidence}
    """
    stdout_text = stdout_text or ""
    stderr_text = stderr_text or ""

    # tier 1: provider/CLI structured status/error (현재는 훅 — 실제 발행자 미배선)
    hit = _from_external_signal(structured_signal, "structured_status_hook")
    if hit is not None:
        return hit

    # tier 2: wrapper-owned spawn/timeout/signal/capture fact (현재는 훅 — 실제 발행자 미배선)
    hit = _from_external_signal(wrapper_signal, "wrapper_fact_hook")
    if hit is not None:
        return hit

    entry = _find_entry(backend_id, cli_version)
    if entry is None:
        return {
            "status": s.ClassificationStatus.UNSUPPORTED_VERSION,
            "failure_class": s.FailureClass.UNKNOWN,
            "classifier_id": None,
            "matched_rule_id": None,
            "confidence": None,
        }

    classifier_id = entry["classifier_id"]

    # tier 3: exact documented exit-code mapping
    exit_map = entry.get("exit_code_map", {})
    if raw_rc is not None and raw_rc in exit_map:
        fc, rule_id = exit_map[raw_rc]
        return {
            "status": s.ClassificationStatus.CLASSIFIED,
            "failure_class": fc,
            "classifier_id": classifier_id,
            "matched_rule_id": rule_id,
            "confidence": "high",
        }

    # tier 4: version-scoped stdout+stderr matcher (stdout도 대상 — 오류를 stdout에 쓰는 CLI 존재)
    haystack = stdout_text + "\n" + stderr_text
    low_confidence_hit = None
    for rule in entry.get("text_rules", []):
        if rule["pattern"].search(haystack):
            if rule["confidence"] == "high":
                return {
                    "status": s.ClassificationStatus.CLASSIFIED,
                    "failure_class": rule["failure_class"],
                    "classifier_id": classifier_id,
                    "matched_rule_id": rule["rule_id"],
                    "confidence": "high",
                }
            if low_confidence_hit is None:
                low_confidence_hit = rule

    if low_confidence_hit is not None:
        # 증거는 있지만 high confidence가 아니므로 구체 failure_class를 발행하지 않는다.
        return {
            "status": s.ClassificationStatus.UNCLASSIFIED,
            "failure_class": s.FailureClass.UNKNOWN,
            "classifier_id": classifier_id,
            "matched_rule_id": low_confidence_hit["rule_id"],
            "confidence": low_confidence_hit["confidence"],
        }

    # tier 5: 실패 신호 매치 없음.
    #   지원 backend에서 실패 rule을 전부 적용했는데 매치가 없고 프로세스가 정상 종료(exited, rc0)
    #   했다면 = "실패 없음을 적극 확인" → classified / failure_class=none. (성공 attempt는 반드시
    #   failure_class==none이어야 is_ok가 될 수 있다 — V8 §5.) rc0인데 출력이 비었거나 whitespace뿐인
    #   경우는 여기서 none으로 두더라도 result_contract(W3)가 empty로 잡으므로 is_ok가 되지 않는다.
    if process_status == s.ProcessStatus.EXITED and raw_rc == 0:
        return {
            "status": s.ClassificationStatus.CLASSIFIED,
            "failure_class": s.FailureClass.NONE,
            "classifier_id": classifier_id,
            "matched_rule_id": None,
            "confidence": "high",
        }
    #   그 외(비정상 종료 / rc≠0인데 분류 실패) → unclassified. 자동 성공으로 인정하지 않는다.
    return {
        "status": s.ClassificationStatus.UNCLASSIFIED,
        "failure_class": s.FailureClass.UNKNOWN,
        "classifier_id": classifier_id,
        "matched_rule_id": None,
        "confidence": None,
    }
