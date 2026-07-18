"""v4 runtime W11 — A5b provenance + generation fencing (write-admission 게이트).

설계 정본: PLUGIN_CUSTOM_DESIGN_V8.md ("각 authoritative event provenance 필수: writer_identity ·
writer_role · runtime_attestation_id · operation_fencing_token(또는 generation) · parent_event_hash.
reducer 검증: event_type × writer_role × operation generation 불일치 시 event를 무시하지 않고
operation을 unresolved/corrupt로 정지"). 표준 라이브러리만.

A5b는 두 시점에서 실현된다:
- **write-admission(이 모듈)**: trusted writer/launcher가 event를 canonical store에 넣기 *전에*
  provenance를 검증한다 — 권한 없는 writer·stale generation·끊긴 parent 링크는 애초에 영속되지
  않는다(stale write 차단). 인증은 write 시점의 자연스러운 관문이다.
- **read-authority(W9 reducer)**: 이미 영속된 event 집합에서 event_type × writer_role 불일치(F1/F2)를
  다시 검출해 operation을 정지한다(방어심층: store가 뚫려도 reduce가 잡는다).

★ V8 (b) #5: provenance는 payload에 값을 적는 것만으론 미인증이다. writer_identity/generation은
별도 UID·broker socket·capability fd·signature·mount 정책이 보증한다 — 이 모듈은 그 인증 *결과*를
받아 계약(권한·generation·parent)을 강제하며, 인증 수단 자체를 대신하지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional

import schema as s


class ProvenanceViolation(RuntimeError):
    """provenance 계약 위반(권한 없는 writer·stale generation·끊긴 parent·미인증 값)."""


# 첫 event(operation의 최초 intent/preflight)는 parent가 없다. 그 외는 parent 링크 필수.
_ROOT_EVENTS = frozenset({
    s.EventType.ATTEMPT_INTENT,
    s.EventType.PREFLIGHT_REJECTION,
})


@dataclass(frozen=True)
class Provenance:
    """authoritative event의 출처 증명(인증 결과를 담는 계약 객체)."""
    writer_identity: str            # 인증된 writer 주체(UID/socket/서명 등이 보증)
    writer_role: str                # schema.WRITER_AUTHORITY의 role
    runtime_attestation_id: str     # 실행 런타임 attestation
    operation_fencing_token: int    # generation — 단조 증가, 낮으면 superseded/stale
    parent_event_hash: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


def authorized_writer(event_type: str, writer_role: str) -> bool:
    """event_type의 유일 trusted writer가 writer_role인가(schema.WRITER_AUTHORITY 단일정본)."""
    if writer_role in s.CONTESTANT_ROLES:
        return False                         # flavor/worker는 어떤 canonical event도 못 씀
    return s.WRITER_AUTHORITY.get(event_type) == writer_role


def verify_event_provenance(
    event_type: str,
    prov: Provenance,
    *,
    current_generation: int,
) -> None:
    """event를 store에 admit하기 전 provenance 계약을 강제. 위반 시 ProvenanceViolation.

    - event_type ∈ 알려진 타입.
    - 인증 값(writer_identity/runtime_attestation_id) 비어있지 않음(미인증 payload 차단).
    - writer_role이 event_type의 유일 trusted writer(권한 없으면 거부; contestant 포함).
    - operation_fencing_token ≥ current_generation(더 낮으면 superseded된 stale writer → 거부).
    - root event(최초 intent/preflight)가 아니면 parent_event_hash 필수(끊긴 인과 차단).
    """
    if event_type not in s.ALL_EVENT_TYPES:
        raise ProvenanceViolation(f"알 수 없는 event_type: {event_type!r}")
    if not prov.writer_identity or not prov.writer_identity.strip():
        raise ProvenanceViolation("writer_identity 미인증(빈 값)")
    if not prov.runtime_attestation_id or not prov.runtime_attestation_id.strip():
        raise ProvenanceViolation("runtime_attestation_id 미인증(빈 값)")
    if not authorized_writer(event_type, prov.writer_role):
        raise ProvenanceViolation(
            f"권한 없는 writer: event_type={event_type} writer_role={prov.writer_role!r} "
            f"(유일 trusted writer={s.WRITER_AUTHORITY.get(event_type)!r})")
    if prov.operation_fencing_token < current_generation:
        raise ProvenanceViolation(
            f"stale generation: token={prov.operation_fencing_token} < "
            f"current={current_generation} (superseded writer의 write 차단)")
    if event_type not in _ROOT_EVENTS and not prov.parent_event_hash:
        raise ProvenanceViolation(f"{event_type}는 parent_event_hash가 필수(끊긴 인과)")


def is_stale_generation(prov: Provenance, current_generation: int) -> bool:
    """편의 판정: 이 provenance가 stale generation인가(=admit 거부 대상)."""
    return prov.operation_fencing_token < current_generation


__all__ = [
    "Provenance", "ProvenanceViolation", "authorized_writer",
    "verify_event_provenance", "is_stale_generation",
]
