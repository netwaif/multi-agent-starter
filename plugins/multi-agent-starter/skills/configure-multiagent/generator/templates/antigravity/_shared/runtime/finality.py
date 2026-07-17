"""v4 runtime W10 — A1b finality: quiescence + effect resolution 증거 생산자.

설계 정본: PLUGIN_CUSTOM_DESIGN_V8.md ("모든 final terminal에 quiescence+effect resolution 전제,
상태별 조건표, terminal이 resolution/quiescence/effect hash 참조"). 표준 라이브러리만.

W9 reducer는 finality evidence의 **소비자**(F9로 누락 검출)다. 이 모듈은 **생산자**:
final terminal event를 조립하려면 quiescence·effect·output 증거가 *실제로 확립*돼야 하며,
확립 안 된 축을 주장하면 FinalityError로 **fail-closed**(방어심층: reducer가 다시 검증).

핵심 불변식:
- final terminal은 FINALITY_REQUIREMENTS[state]의 evidence 축을 모두 확립해야 발행 가능.
- "timeout/cancel 관측 ≠ 종료" — quiescence는 process tree가 실제로 끝났다는 확인이어야 한다
  (A1b). 이 모듈은 quiescence 확인 콜백을 받되, 미확인이면 evidence를 만들지 않는다.
- effect_resolution_hash는 (effect_class, effect_outcome, delivery_semantics)를 봉인해 terminal이
  참조한다(재시도 안전성 판정의 근거).
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from typing import Optional

import schema as s


class FinalityError(RuntimeError):
    """확립되지 않은 finality 증거로 final terminal을 조립하려 할 때(fail-closed)."""


# ── quiescence 확인 (V8 (b): API는 구현 자유, 불변식만 강제) ────────────────
def process_group_quiescent(pgid: Optional[int]) -> bool:
    """best-effort: process group이 더 이상 살아있지 않은지. pgid=None이면 실행 자체 없음(quiescent).

    os.killpg(pgid, 0)이 ProcessLookupError면 그룹 소멸(quiescent). 살아있으면 False.
    권한 오류 등은 "확인 불가"이므로 보수적으로 False(=quiescent 아님)로 본다.
    """
    if pgid is None:
        return True
    try:
        os.killpg(pgid, 0)
        return False          # 신호 0 성공 = 그룹 아직 존재
    except ProcessLookupError:
        return True           # 그룹 없음 = quiescent
    except PermissionError:
        return False          # 존재하지만 권한 없음 → 살아있음으로 간주(보수적)
    except OSError:
        return False


# ── effect resolution 봉인 ──────────────────────────────────────────────────
def effect_resolution_hash(effect_class: str, effect_outcome: str, delivery_semantics: str) -> str:
    """effect 계약을 봉인한 해시(`sha256:` 접두). terminal이 이 값을 참조한다."""
    canon = json.dumps(
        {"effect_class": effect_class, "effect_outcome": effect_outcome,
         "delivery_semantics": delivery_semantics},
        sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(canon.encode("utf-8")).hexdigest()


_VALID_EFFECT_OUTCOMES = frozenset({"none", "succeeded", "failed", "compensated", "unknown"})
_VALID_OUTPUT_OUTCOMES = frozenset({"valid", "invalid", "unavailable"})


@dataclass(frozen=True)
class FinalityEvidence:
    terminal_state: str
    evidence_axes: tuple           # FINALITY_REQUIREMENTS를 충족하는 축들
    effect_resolution_hash: str
    effect_outcome: str
    output_outcome: str

    def to_terminal_fields(self) -> dict:
        """reducer가 받는 terminal event의 finality 관련 필드로 변환."""
        return {
            "terminal_state": self.terminal_state,
            "finality_evidence": list(self.evidence_axes),
            "effect_resolution_hash": self.effect_resolution_hash,
            "effect_outcome": self.effect_outcome,
            "output_outcome": self.output_outcome,
        }


def build_finality_evidence(
    terminal_state: str,
    *,
    quiescence_confirmed: bool,
    effect_class: str,
    effect_outcome: str,
    output_outcome: str,
    delivery_semantics: str = s.DeliverySemantics.AT_MOST_ONCE,
) -> FinalityEvidence:
    """final terminal의 증거를 조립. 요구 축이 실제로 확립되지 않으면 FinalityError(fail-closed).

    - local_quiescence: quiescence_confirmed=True 여야 확립.
    - effect_resolved: effect_outcome이 unknown이 아니어야 확립(미상 effect는 resolved 아님).
    - output_sealed: output_outcome이 valid/invalid/unavailable 중 하나로 분류돼야 확립.
    """
    if terminal_state not in s.FINAL_TERMINAL_STATES:
        raise FinalityError(f"final terminal 상태가 아님: {terminal_state!r}")
    if effect_outcome not in _VALID_EFFECT_OUTCOMES:
        raise FinalityError(f"effect_outcome 부적합: {effect_outcome!r}")
    if output_outcome not in _VALID_OUTPUT_OUTCOMES:
        raise FinalityError(f"output_outcome 부적합: {output_outcome!r}")

    required = set(s.FINALITY_REQUIREMENTS.get(terminal_state, ()))
    established = set()
    if quiescence_confirmed:
        established.add("local_quiescence")
    if effect_outcome != "unknown":
        established.add("effect_resolved")
    established.add("output_sealed")   # output_outcome이 유효분류면 sealed(위에서 검증)

    missing = required - established
    if missing:
        raise FinalityError(
            f"{terminal_state} 발행 불가 — 미확립 finality 증거: {sorted(missing)} "
            f"(quiescence={quiescence_confirmed}, effect_outcome={effect_outcome})")

    erhash = effect_resolution_hash(effect_class, effect_outcome, delivery_semantics)
    # 요구 축만 evidence로 봉인(required=() 상태면 빈 tuple — PRECHECK_REJECTED 등).
    axes = tuple(sorted(established & required))
    return FinalityEvidence(
        terminal_state=terminal_state,
        evidence_axes=axes,
        effect_resolution_hash=erhash,
        effect_outcome=effect_outcome,
        output_outcome=output_outcome,
    )


__all__ = [
    "FinalityError", "FinalityEvidence", "build_finality_evidence",
    "process_group_quiescent", "effect_resolution_hash",
]
