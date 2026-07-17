"""v4 runtime W12 — profile snapshot 2층 (V8 "profile snapshot 2층").

설계 정본: PLUGIN_CUSTOM_DESIGN_V8.md ("과거 snapshot(재현) + 현재 비가역 안전 overlay + CA archive").
표준 라이브러리만.

2층 구조:
- **층1 과거 snapshot(재현용)**: plan이 봉인한 시점의 capability profile. content-addressed
  (profile_sha256)로 archive에 보관 → 옛 plan을 재현할 때 정확히 그 프로필을 복원한다.
- **층2 현재 비가역 안전 overlay**: *지금* 유효한 안전 제약. 옛 프로필을 재현하더라도 항상 위에
  덧씌워진다 — 나중에 안전상 disable된 backend를 옛 프로필이 다시 켤 수 없다(단방향 제한).

핵심 불변식:
- overlay 적용은 **단조 제한적(monotone-restrictive)**: 결과는 절대 overlay보다 덜 제한적일 수
  없다. 안전은 조일 수만 있고 과거가 되돌릴 수 없다.
- content address는 canonical JSON SHA256 — plan.profile_sha256과 동일 규약(재현 정합).
- archive는 content-addressed: 같은 프로필 → 같은 주소, 재현 시 주소로 정확 복원.
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Optional


class ProfileError(ValueError):
    """프로필/overlay 형식 위반 또는 archive 무결성 위반."""


# ── content addressing (plan.profile_sha256과 동일 규약) ────────────────────
def content_address(profile: dict) -> str:
    """프로필의 content address(`sha256:` 접두). canonical JSON 기준."""
    canon = json.dumps(profile, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(canon.encode("utf-8")).hexdigest()


# ── 층2: 비가역 안전 overlay (단방향 제한) ──────────────────────────────────
def apply_safety_overlay(profile: dict, overlay: dict) -> dict:
    """과거 snapshot 위에 현재 안전 overlay를 덧씌운 effective 프로필을 반환(원본 불변).

    overlay 스키마:
      { "disabled_backends": [id...],          # 강제 enabled=False
        "forbidden_capabilities": [cap...] }   # 각 backend capabilities에서 강제 False

    단조 제한적: backend를 켜거나 capability를 되살리지 않는다 — 오직 끈다.
    """
    disabled = set(overlay.get("disabled_backends", []) or [])
    forbidden = set(overlay.get("forbidden_capabilities", []) or [])

    eff = json.loads(json.dumps(profile))   # deep copy(표준 라이브러리, 원본 보호)
    backends = eff.get("backends")
    if not isinstance(backends, dict):
        raise ProfileError("profile.backends는 객체여야 한다")

    for bid, spec in backends.items():
        if not isinstance(spec, dict):
            raise ProfileError(f"backend {bid} 스펙은 객체여야 한다")
        if bid in disabled:
            spec["enabled"] = False           # 안전 disable — 과거가 되돌릴 수 없음
        caps = spec.get("capabilities")
        if isinstance(caps, dict):
            for cap in forbidden:
                if cap in caps:
                    caps[cap] = False          # 금지 capability 강제 off
    return eff


def assert_overlay_satisfied(effective: dict, overlay: dict) -> None:
    """effective 프로필이 overlay 제약을 실제로 만족하는지 검증(방어심층). 위반 시 ProfileError."""
    disabled = set(overlay.get("disabled_backends", []) or [])
    forbidden = set(overlay.get("forbidden_capabilities", []) or [])
    backends = effective.get("backends", {})
    for bid in disabled:
        spec = backends.get(bid)
        if spec is not None and spec.get("enabled", False):
            raise ProfileError(f"overlay 위반: disabled backend {bid}가 enabled=True")
    for bid, spec in backends.items():
        caps = (spec or {}).get("capabilities", {}) or {}
        for cap in forbidden:
            if caps.get(cap, False):
                raise ProfileError(f"overlay 위반: backend {bid}의 금지 capability {cap}=True")


# ── content-addressed archive (재현용) ──────────────────────────────────────
class ProfileArchive:
    """content-addressed 프로필 보관소. 같은 프로필 → 같은 주소. 옛 plan 재현에 사용.

    dir_path가 있으면 파일 백엔드(`<sha>.json`), 없으면 인메모리(dict). 표준 라이브러리만.
    """

    def __init__(self, dir_path: Optional[str] = None):
        self._dir = dir_path
        self._mem: dict = {}
        if dir_path is not None:
            os.makedirs(dir_path, exist_ok=True)

    def _path(self, addr: str) -> str:
        # `sha256:` 접두를 파일명 안전하게.
        return os.path.join(self._dir, addr.replace(":", "_") + ".json")

    def put(self, profile: dict) -> str:
        """프로필을 저장하고 content address를 반환(멱등: 같은 내용은 덮어써도 무해)."""
        addr = content_address(profile)
        canon = json.dumps(profile, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        if self._dir is None:
            self._mem[addr] = canon
        else:
            with open(self._path(addr), "w", encoding="utf-8") as f:
                f.write(canon)
        return addr

    def get(self, addr: str) -> dict:
        """주소로 프로필을 복원. 저장 후 내용이 주소와 불일치하면 ProfileError(무결성)."""
        if self._dir is None:
            if addr not in self._mem:
                raise ProfileError(f"archive에 없음: {addr}")
            canon = self._mem[addr]
        else:
            p = self._path(addr)
            if not os.path.exists(p):
                raise ProfileError(f"archive에 없음: {addr}")
            with open(p, "r", encoding="utf-8") as f:
                canon = f.read()
        profile = json.loads(canon)
        if content_address(profile) != addr:
            raise ProfileError(f"archive 무결성 위반: 복원 주소 불일치 {addr}")
        return profile

    def reproduce_effective(self, addr: str, overlay: dict) -> dict:
        """옛 프로필(층1)을 주소로 복원하고 현재 안전 overlay(층2)를 덧씌운 effective 반환."""
        past = self.get(addr)
        eff = apply_safety_overlay(past, overlay)
        assert_overlay_satisfied(eff, overlay)
        return eff


__all__ = [
    "ProfileError", "content_address", "apply_safety_overlay",
    "assert_overlay_satisfied", "ProfileArchive",
]
