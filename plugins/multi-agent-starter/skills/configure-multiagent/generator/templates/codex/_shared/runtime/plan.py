"""v4 runtime W7 — dispatch plan 불변 revision + mission-byte 인과 + launcher seal.

설계 정본: PLUGIN_CUSTOM_DESIGN_V8.md (writer-authority matrix · A5b · "plan 불변 revision +
mission hash 인과 · capability_slot/role_label 분리 · selected_backend_route"). 표준 라이브러리만.

핵심 불변식(여기서 코드화):
- **A5b writer-authority**: dispatch plan은 flavor(contestant)가 유일하게 *제안*할 수 있는 것이되,
  flavor는 canonical control-plane에 **직접 쓰지 못한다**. flavor는 submission drop(자유 편집 영역)에
  JSON을 놓고, **launcher가** schema/profile을 검증한 뒤 canonical revision으로 import·재해시·봉인한다.
  flavor가 적어 넣은 `plan_hash`는 **절대 신뢰하지 않는다**(launcher가 항상 재계산).
- **불변 revision**: 한 번 봉인된 revision은 바뀌지 않는다. 수정 = parent_hash로 이어지는 새 revision.
  `plan_id`는 revision들을 가로질러 안정, `revision`은 1부터 단조 증가, revision 1만 parent_hash 없음.
- **mission-byte 인과**: plan은 정확한 mission 바이트에 묶인다. JSON이면 canonical 재직렬화 후 해시
  (공백·키순서 차이를 흡수), 아니면 raw 바이트 해시 — 어느 쪽이든 결정적.
- **capability_slot ↔ role_label 분리**: 추상 슬롯(무엇을 시키나)과 라우팅/표시 라벨(누구로 보이나)은
  별도 필드다. 둘을 합치면 프로필 재바인딩 시 인과가 깨진다(V8).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, asdict
from typing import Optional, Sequence

SCHEMA_VERSION = "2"

# flavor는 plan을 *제안*만 한다(submission drop). 아래 role만 제안 주체로 인정.
CONTESTANT_PROPOSER_ROLES = frozenset({"flavor"})


class PlanValidationError(ValueError):
    """flavor 제안 plan이 schema/profile/불변식을 위반했을 때(launcher가 거부)."""


# ── mission-byte 인과 해시 ──────────────────────────────────────────────────
def canonicalize_mission(raw: bytes) -> tuple[bytes, str]:
    """mission 바이트를 결정적 canonical 형태로. (canonical_bytes, mode) 반환.

    JSON으로 decode되면 sort_keys+무공백 재직렬화(UTF-8) → 의미상 동일한 mission이 동일 해시.
    아니면 raw 바이트 그대로(여전히 결정적). brief.md 같은 텍스트는 raw 경로를 탄다.
    """
    try:
        obj = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return raw, "raw_bytes"
    canon = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return canon.encode("utf-8"), "json_canonical"


def mission_hash(raw: bytes) -> str:
    """mission 바이트의 인과 해시(canonical 후 SHA256, `sha256:` 접두)."""
    canon, _mode = canonicalize_mission(raw)
    return "sha256:" + hashlib.sha256(canon).hexdigest()


# ── 불변 revision ───────────────────────────────────────────────────────────
# 봉인 대상 필드(이 순서·집합이 plan_hash를 결정). plan_hash 자체는 봉인 대상이 아니다.
_SEALED_FIELDS = (
    "schema_version",
    "plan_id",
    "revision",
    "parent_hash",
    "profile_sha256",
    "mission_hash",
    "capability_slot",
    "role_label",
    "selected_backend_route",
    "created_by_role",
)


@dataclass(frozen=True)
class DispatchPlanRevision:
    """봉인된 dispatch plan revision(불변). `plan_hash`는 launcher가 계산한 seal."""
    schema_version: str
    plan_id: str
    revision: int
    parent_hash: Optional[str]
    profile_sha256: str
    mission_hash: str
    capability_slot: str
    role_label: str
    selected_backend_route: str
    created_by_role: str
    plan_hash: str

    def to_dict(self) -> dict:
        return asdict(self)


def _sealed_view(fields: dict) -> dict:
    return {k: fields[k] for k in _SEALED_FIELDS}


def compute_plan_hash(fields: dict) -> str:
    """봉인 필드의 canonical JSON에 대한 SHA256(`sha256:` 접두). launcher만 호출해 seal 생성."""
    canon = json.dumps(_sealed_view(fields), sort_keys=True,
                       separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(canon.encode("utf-8")).hexdigest()


def _validate_core(fields: dict) -> None:
    if fields["schema_version"] != SCHEMA_VERSION:
        raise PlanValidationError(f"schema_version 불일치: {fields['schema_version']!r}")
    rev = fields["revision"]
    if not isinstance(rev, int) or rev < 1:
        raise PlanValidationError(f"revision은 1 이상 정수여야: {rev!r}")
    parent = fields["parent_hash"]
    if rev == 1 and parent not in (None, ""):
        raise PlanValidationError("revision 1은 parent_hash가 없어야 한다")
    if rev > 1 and not parent:
        raise PlanValidationError("revision>1은 parent_hash(이전 seal)를 참조해야 한다")
    # capability_slot ↔ role_label 분리 강제: 둘 다 비어있지 않은 별도 값.
    for k in ("plan_id", "profile_sha256", "mission_hash",
              "capability_slot", "role_label", "selected_backend_route", "created_by_role"):
        v = fields.get(k)
        if not isinstance(v, str) or not v.strip():
            raise PlanValidationError(f"필드 {k}는 비어있지 않은 문자열이어야: {v!r}")


def build_plan_revision(
    *,
    plan_id: str,
    revision: int,
    parent_hash: Optional[str],
    profile_sha256: str,
    mission_hash: str,
    capability_slot: str,
    role_label: str,
    selected_backend_route: str,
    created_by_role: str = "flavor",
) -> DispatchPlanRevision:
    """검증된 필드로 revision을 만들고 plan_hash로 봉인한다(내부/테스트용 구성자).

    실전 flavor→launcher 경로는 `import_plan_submission`를 쓴다(제안 검증 포함).
    """
    fields = {
        "schema_version": SCHEMA_VERSION,
        "plan_id": plan_id,
        "revision": revision,
        "parent_hash": (parent_hash or None),
        "profile_sha256": profile_sha256,
        "mission_hash": mission_hash,
        "capability_slot": capability_slot,
        "role_label": role_label,
        "selected_backend_route": selected_backend_route,
        "created_by_role": created_by_role,
    }
    _validate_core(fields)
    fields["plan_hash"] = compute_plan_hash(fields)
    return DispatchPlanRevision(**fields)


# ── launcher import 경계 (A5b) ──────────────────────────────────────────────
def import_plan_submission(
    raw_submission: bytes,
    *,
    expected_profile_sha256: str,
    submitter_role: str = "flavor",
    parent: Optional[DispatchPlanRevision] = None,
) -> DispatchPlanRevision:
    """flavor가 submission drop에 놓은 JSON 제안을 launcher가 검증·봉인해 canonical revision으로.

    flavor는 신뢰되지 않는다:
    - `submitter_role`은 contestant 제안자여야 한다(flavor). 다른 role의 plan 제안은 거부.
    - flavor가 적은 `profile_sha256`은 launcher가 아는 값과 일치해야 한다(프로필 위조 차단).
    - flavor가 적은 `plan_hash`/`schema_version`은 무시하고 launcher가 재계산·강제한다.
    - `revision`/`parent_hash`는 launcher가 아는 parent와 정합해야 한다(chain 위조 차단).
    """
    if submitter_role not in CONTESTANT_PROPOSER_ROLES:
        raise PlanValidationError(f"plan 제안 권한 없음(role={submitter_role!r}) — flavor만 제안 가능")
    try:
        sub = json.loads(raw_submission.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as e:
        raise PlanValidationError(f"제안 JSON 파싱 실패: {e}") from e
    if not isinstance(sub, dict):
        raise PlanValidationError("제안은 JSON 객체여야 한다")

    # 프로필 위조 차단: flavor가 뭐라 적었든 launcher가 아는 프로필로 강제.
    claimed_profile = sub.get("profile_sha256")
    if claimed_profile is not None and claimed_profile != expected_profile_sha256:
        raise PlanValidationError(
            f"profile_sha256 위조 감지: 제안={claimed_profile!r} ≠ launcher={expected_profile_sha256!r}")

    # revision/parent를 launcher가 아는 parent로부터 도출(flavor 값은 참고만).
    if parent is None:
        revision, parent_hash = 1, None
    else:
        revision, parent_hash = parent.revision + 1, parent.plan_hash

    return build_plan_revision(
        plan_id=str(sub.get("plan_id", "")),
        revision=revision,
        parent_hash=parent_hash,
        profile_sha256=expected_profile_sha256,   # launcher 값으로 봉인
        mission_hash=str(sub.get("mission_hash", "")),
        capability_slot=str(sub.get("capability_slot", "")),
        role_label=str(sub.get("role_label", "")),
        selected_backend_route=str(sub.get("selected_backend_route", "")),
        created_by_role=submitter_role,
    )


# ── revision chain 무결성 검증 ──────────────────────────────────────────────
def verify_revision_chain(revisions: Sequence[DispatchPlanRevision]) -> None:
    """revision 목록의 seal·parent 링크·단조성을 검증. 위반 시 PlanValidationError.

    reducer/recovery gate(W9)가 새 실행 전 plan 계보 위조를 잡는 데 쓴다.
    """
    prev: Optional[DispatchPlanRevision] = None
    for r in revisions:
        # 각 revision의 plan_hash가 봉인 필드로부터 실제 재계산되는지(self-seal 위조 차단).
        recomputed = compute_plan_hash(r.to_dict())
        if recomputed != r.plan_hash:
            raise PlanValidationError(
                f"plan_hash 봉인 불일치(rev={r.revision}): 저장={r.plan_hash} 재계산={recomputed}")
        if prev is None:
            if r.revision != 1 or r.parent_hash not in (None, ""):
                raise PlanValidationError("chain 시작은 revision 1 + parent 없음이어야")
        else:
            if r.plan_id != prev.plan_id:
                raise PlanValidationError("chain 내 plan_id 불일치")
            if r.revision != prev.revision + 1:
                raise PlanValidationError(
                    f"revision 단조성 위반: {prev.revision}→{r.revision}")
            if r.parent_hash != prev.plan_hash:
                raise PlanValidationError(
                    f"parent_hash 링크 끊김(rev={r.revision})")
        prev = r
