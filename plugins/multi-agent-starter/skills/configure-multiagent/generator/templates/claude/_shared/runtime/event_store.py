"""v4 runtime — event store 로더 (reducer 입력 준비, 통합 접착).

wal.py가 영속한 event marker 파일(`<attempt_id>.<kind>.json`)을 읽어 reducer가 받는 event dict
리스트로 만든다. 파일 IO만. 표준 라이브러리만.

reducer(W9)는 순수 함수라 event dict 리스트를 받는다. 이 모듈이 디스크↔reducer 경계를 잇는다.
"""

from __future__ import annotations

import json
import os
from typing import List


def load_events(events_dir: str) -> List[dict]:
    """events_dir의 모든 event marker(*.json)를 파싱해 event dict 리스트로.

    - `event_type` 키를 가진 JSON 객체만 event로 채택(임시파일 .wal-tmp-* 등 무시).
    - 디렉터리가 없으면 빈 리스트(operation 첫 실행 = 이벤트 없음).
    - 파싱 불가/객체 아님 파일은 조용히 건너뛴다(부분 손상이 로드를 죽이지 않음).
    """
    events: List[dict] = []
    if not os.path.isdir(events_dir):
        return events
    for name in sorted(os.listdir(events_dir)):
        if not name.endswith(".json") or name.startswith(".wal-tmp-"):
            continue
        try:
            with open(os.path.join(events_dir, name), "r", encoding="utf-8") as f:
                obj = json.load(f)
        except (ValueError, OSError):
            continue
        if isinstance(obj, dict) and "event_type" in obj:
            events.append(obj)
    return events


def next_attempt_number(events: List[dict], logical_operation_id: str) -> int:
    """이 operation의 다음 attempt 번호(기존 최대 +1, 없으면 1).

    attempt_id 규약 "<op>#a<N>"에서 N을 파싱한다. logical_operation_id로 필터.
    """
    nums = []
    prefix = f"{logical_operation_id}#a"
    for ev in events:
        if ev.get("logical_operation_id") != logical_operation_id:
            continue
        aid = ev.get("attempt_id", "")
        if isinstance(aid, str) and aid.startswith(prefix):
            tail = aid[len(prefix):]
            if tail.isdigit():
                nums.append(int(tail))
    return (max(nums) + 1) if nums else 1


__all__ = ["load_events", "next_attempt_number"]
