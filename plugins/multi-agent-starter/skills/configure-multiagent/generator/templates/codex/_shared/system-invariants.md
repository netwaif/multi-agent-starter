# System Invariants — 시스템 수정 후 자가 점검

> **로드 정책**: 평소 미로드. 시스템 파일 수정·검증 작업일 때만 사용한다.

## 불변식 목록

| ID | 불변식 |
|----|--------|
| INV1 | `write_scope` 값 집합이 `AGENTS.md`, `routing.md`, `worker-brief.md`, `task-folder.md`에서 동일 |
| INV2 | `codex-critic`이 실행 규칙·템플릿의 활성 worker로 남아 있지 않음 |
| INV3 | `claude-critic` 선행조건이 특정 worker 결과에만 묶이지 않고 일반화되어 있음 |
| INV4 | log 태그가 정확히 `DECISION | WORKER_CALL | VERIFICATION | ERROR | APPROVAL | COMPLETE` 6종 |
| INV5 | context 한도 1500자, brief 한도 1200자가 정본 문서와 템플릿에서 일치 |
| INV6 | 권위 우선순위가 `AGENTS.md` 기준으로 기록됨 |
| INV7 | 재진입 프로토콜이 `orchestrator-rules.md`와 `AGENTS.md` 포인터에 모두 존재 |
| INV8 | 토폴로지 4패턴(Pipeline, Fan-out/Fan-in, Expert Pool, Producer-Reviewer)이 routing에 존재 |
| INV9 | gemini 백엔드가 `_shared/backends.json`에서 `agy` CLI(command agy)이고 기본 모델 `gemini-3.1-pro-high`; routing.md·D4가 backends를 정본 참조, 옛 `mcp__gemini-pro__*` 활성호출 없음 |
| INV12 | gemini api 폴백 = 미구현 슬롯이므로 `backends.json` `fallbacks` 빈 배열(거짓 안전신호 금지, D9) |
| INV11 | 카파시 4원칙(D7): `AGENTS.md`에 "Operating Principles" 섹션 존재, `_templates/worker-brief.md`에 "Worker 행동 규약" 고정 블록 존재, 블록 안에 사용자질문 지시(질문/ask) 없음, `worker-result.md` 체크리스트에 표면화 항목 존재 |

## 자가 점검 실행

정본 러너 = `_shared/check-invariants.sh` (exit-code 판정).

```bash
bash _shared/check-invariants.sh   # 전 항목 판정. 하나라도 FAIL → exit 비0 (커밋 금지)
```

표(정의)와 러너(판정)가 어긋나면 표에 맞춰 러너를 고친다. 불변식 추가 시 러너에 판정을 함께 추가한다.

## 전면 재감사가 필요한 경우

- 새 외부 개념·레퍼런스를 시스템에 도입할 때
- worker pool 구성·역할이 바뀔 때
- 위 불변식으로 표현 불가한 구조 변경이 생길 때
