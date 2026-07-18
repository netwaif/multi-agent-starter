"""v4 runtime W8 — logical operation 계보 + fencing (V8 A3).

설계 정본: PLUGIN_CUSTOM_DESIGN_V8.md ("A3 logical_operation_id를 4.0 최초 intent부터 +
operation fencing", writer-authority provenance의 `operation_fencing_token(또는 generation)").
표준 라이브러리만. 부작용 없음(데이터/판정만).

핵심 불변식(여기서 코드화):
- **logical_operation_id는 4.0 최초 intent에서 발급되고 재시도를 가로질러 불변**. 재시도마다 새 id를
  만들면 retry-cap을 우회할 수 있으므로(각 시도가 "새 operation"으로 위장) 금지 — next_attempt는
  반드시 이전 계보의 id를 승계한다.
- **attempt_number 단조 증가**(1부터). previous_attempt_id로 직전 시도를 가리킨다.
- **retry cap**: attempt_number > cap이면 새 시도 발급 거부(RetryCapExceeded).
- **operation-level active ≤ 1 fencing**: 한 logical operation에 동시에 비terminal(active) 시도는
  최대 1개. fencing_token(generation)은 단조 증가하고, 더 낮은 token의 stale 시도는 canonical store에
  쓸 수 없다(newer wins). store에 active가 2개 이상 관측되면 fencing 위반 → reducer가 operation 정지.
- **request_id**: 이 시도를 촉발한 구체 요청(멱등성 경계). 동일 request_id 재제출은 새 시도가 아니다.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, replace
from typing import Optional, Sequence


class RetryCapExceeded(RuntimeError):
    """재시도 상한을 넘겨 새 시도 계보를 발급하려 할 때."""


class FencingViolation(RuntimeError):
    """한 logical operation에 active 시도가 2개 이상 관측될 때(reducer가 operation 정지)."""


class LineageError(ValueError):
    """계보 불변식(id 승계·단조성·링크) 위반."""


@dataclass(frozen=True)
class LogicalLineage:
    """한 attempt의 계보 좌표(불변)."""
    logical_operation_id: str          # 4.0 최초 intent부터 불변
    attempt_number: int                # 1부터 단조
    attempt_id: str                    # 결정적 파생: "{op}#a{n}"
    previous_attempt_id: Optional[str] # 직전 시도(첫 시도는 None)
    request_id: str                    # 이 시도를 촉발한 요청(멱등성 경계)
    fencing_token: int                 # generation, 단조; 낮으면 stale

    def to_dict(self) -> dict:
        return asdict(self)


def _attempt_id(logical_operation_id: str, attempt_number: int) -> str:
    return f"{logical_operation_id}#a{attempt_number}"


def new_operation(logical_operation_id: str, request_id: str) -> LogicalLineage:
    """4.0 최초 intent에서 logical operation의 첫 시도 계보를 발급한다."""
    if not logical_operation_id or not logical_operation_id.strip():
        raise LineageError("logical_operation_id는 비어있을 수 없다")
    if not request_id or not request_id.strip():
        raise LineageError("request_id는 비어있을 수 없다")
    return LogicalLineage(
        logical_operation_id=logical_operation_id,
        attempt_number=1,
        attempt_id=_attempt_id(logical_operation_id, 1),
        previous_attempt_id=None,
        request_id=request_id,
        fencing_token=1,
    )


def next_attempt(prev: LogicalLineage, request_id: str, *, retry_cap: int) -> LogicalLineage:
    """이전 계보로부터 다음 시도를 발급한다(id 승계 · 단조 · retry-cap 강제).

    호출 전제(reducer가 보장): 직전 시도가 이미 resolved/terminal이고 active가 0이어야 한다.
    이 함수는 계보 정합성과 retry-cap만 강제하며, active≤1은 fence_active로 별도 검증한다.
    """
    if retry_cap < 1:
        raise LineageError(f"retry_cap은 1 이상이어야: {retry_cap}")
    nxt = prev.attempt_number + 1
    if nxt > retry_cap:
        raise RetryCapExceeded(
            f"retry cap {retry_cap} 초과: op={prev.logical_operation_id} 다음 시도 #{nxt}")
    if not request_id or not request_id.strip():
        raise LineageError("request_id는 비어있을 수 없다")
    return LogicalLineage(
        logical_operation_id=prev.logical_operation_id,   # ★ id 승계(재발급 금지)
        attempt_number=nxt,
        attempt_id=_attempt_id(prev.logical_operation_id, nxt),
        previous_attempt_id=prev.attempt_id,
        request_id=request_id,
        fencing_token=prev.fencing_token + 1,             # generation 단조 증가
    )


def is_stale(lineage: LogicalLineage, current_fencing_token: int) -> bool:
    """이 계보가 stale한가(더 새 generation이 이미 있음) → canonical store에 쓰기 거부 대상."""
    return lineage.fencing_token < current_fencing_token


def fence_active(active_lineages: Sequence[LogicalLineage]) -> Optional[LogicalLineage]:
    """한 operation의 active(비terminal) 시도 목록에 active≤1 fencing을 강제.

    - 0개: None 반환(진행 가능).
    - 1개: 그 계보 반환.
    - 2개 이상: 서로 다른 시도가 동시에 active → FencingViolation(reducer가 operation 정지).
      (동일 logical_operation_id여야 하며, 아니면 애초에 섞인 입력 — LineageError.)
    """
    if not active_lineages:
        return None
    op_ids = {l.logical_operation_id for l in active_lineages}
    if len(op_ids) > 1:
        raise LineageError(f"fence_active에 서로 다른 operation 혼입: {op_ids}")
    if len(active_lineages) > 1:
        toks = sorted(l.fencing_token for l in active_lineages)
        raise FencingViolation(
            f"operation {next(iter(op_ids))}에 active 시도 {len(active_lineages)}개 "
            f"(fencing_token={toks}) — active≤1 위반")
    return active_lineages[0]


def validate_chain(lineages: Sequence[LogicalLineage]) -> None:
    """시도 계보 체인의 id 승계·단조성·링크·fencing 단조를 검증. 위반 시 LineageError.

    reducer/recovery gate(W9)가 계보 위조(재발급된 id로 retry-cap 우회 등)를 잡는 데 쓴다.
    """
    prev: Optional[LogicalLineage] = None
    for l in lineages:
        if l.attempt_id != _attempt_id(l.logical_operation_id, l.attempt_number):
            raise LineageError(f"attempt_id 파생 불일치: {l.attempt_id}")
        if prev is None:
            if l.attempt_number != 1 or l.previous_attempt_id is not None:
                raise LineageError("체인 시작은 attempt_number 1 + previous 없음이어야")
        else:
            if l.logical_operation_id != prev.logical_operation_id:
                raise LineageError("체인 내 logical_operation_id 불일치(재발급 금지)")
            if l.attempt_number != prev.attempt_number + 1:
                raise LineageError(
                    f"attempt_number 단조성 위반: {prev.attempt_number}→{l.attempt_number}")
            if l.previous_attempt_id != prev.attempt_id:
                raise LineageError(f"previous_attempt_id 링크 끊김(#{l.attempt_number})")
            if l.fencing_token <= prev.fencing_token:
                raise LineageError(
                    f"fencing_token 단조성 위반: {prev.fencing_token}→{l.fencing_token}")
        prev = l


__all__ = [
    "LogicalLineage", "RetryCapExceeded", "FencingViolation", "LineageError",
    "new_operation", "next_attempt", "is_stale", "fence_active", "validate_chain",
]
