# System Invariants — 시스템 수정 후 자가 점검

> **로드 정책**: 평소 미로드. 시스템 파일 수정·검증 작업일 때만 (`orchestrator-rules.md` §2).
> 목적: 시스템 변경 후 **전면 멀티에이전트 재감사 대신** 이 점검만 돌려 모순 재발을 잡는다.
> 통과해야 커밋. 깨지면 고치거나, 의도된 변경이면 `design-basis.md` 결정(D*)·이 표를 함께 갱신.

## 불변식 목록

| ID | 불변식 | 깨지면 |
|---|---|---|
| INV1 | `write_scope` 값 집합이 CLAUDE.md(정의처)·routing.md·_templates/worker-brief.md·task-folder.md·매뉴얼에서 동일 (`none`/`tasks-only`/패턴) | D1 위반 — 어디든 한 곳만 다르면 시스템 자체 모순 |
| INV2 | codex-critic 선행조건에 "claude-main result.md 존재 필수" 같은 **전용 강제** 표현 없음 (일반화 표현이어야) | D2 위반 |
| INV3 | log 태그 = 정확히 `DECISION\|WORKER_CALL\|VERIFICATION\|ERROR\|APPROVAL\|COMPLETE` 6종 (_templates/log.md, 매뉴얼) | 파서·일관성 깨짐 |
| INV4 | context.md 한도 1500자, brief 한도 1200자 수치가 CLAUDE.md·매뉴얼·_templates 헤더에서 동일 | 한도 불일치 |
| INV5 | **(유지보수자 전용)** 외부 매뉴얼 메인 섹션 개수 == manual-repo `CLAUDE.md`의 메인 섹션 목록 개수 | 매뉴얼↔manual-repo 빌드 스펙 불일치 (현재 R3 미해소 시 의도적 FAIL) |
| INV6 | 매뉴얼 `workers_approved` 예시 스키마가 approval-policy.md와 일치 (`worker:`/date-only/`purpose:`/`approved_by:`, `HH:MM` 없음) | B1/B6 재발 |
| INV7 | 권위 우선순위 문구가 매뉴얼 §3과 design-basis.md §2에서 동일 (CLAUDE.md > routing/approval/orchestrator-rules > 매뉴얼) | Clash 해소 규칙 붕괴 |
| INV8 | 인터랙티브 전용 + worktree/백그라운드 세션 금지 규칙이 orchestrator-rules.md와 매뉴얼에 모두 존재 | D5 위반 |
| INV9 | gemini 백엔드가 `_shared/backends.json`에서 `agy` CLI(call_type cli·command agy)이고 기본 모델 `gemini-3.1-pro-high`, routing.md·D4가 backends를 정본으로 참조 | 정본이 폐기 프록시/known-bad 경로 호출 (D4 위반) |
| INV10 | 폐기 브리지 **`mcp__gemini__gemini_*`(CLI 래퍼) 및 `mcp__gemini-pro__*`(프록시)** 가 routing.md·task-folder.md·CLAUDE.md에 **활성 호출**로 없음. 잔여 언급은 **폐기 안내 문맥에서만** | C2 재발 — 폐기 브리지 잔존 호출이 즉시 실패 (D4 위반) |
| INV11 | 재진입 프로토콜이 orchestrator-rules.md §3 **와** CLAUDE.md Task Lifecycle 포인터에 **둘 다** 존재. routing.md 토폴로지표에 4패턴(Pipeline/Fan-out·in/Expert Pool/Producer-Reviewer) 모두 존재하고, Supervisor·Hierarchical은 "배제" 줄에만 등장(채택표 행으로 등장 금지) | D6 위반 — 재진입/패턴 규정 유실 또는 배제 패턴 부활 |
| INV12 | 카파시 4원칙: CLAUDE.md에 "운영 원칙 (Operating Principles)" 섹션 존재, _templates/worker-brief.md에 "Worker 행동 규약" 고정 블록 존재, **블록 안에 사용자질문 지시(질문/ask) 없음**, worker-result.md 체크리스트에 표면화 항목 존재 | D8 위반 — 층별 적용 붕괴(워커 one-shot 구조와 모순) 또는 워커 규약 유실 |
| INV13 | backends.json 실행계약 정합: codex-main sandbox = `workspace-write`(MCP·CLI 폴백 모두), codex-critic = `read-only`(모두), gemini `fallbacks` = 빈 배열(미구현 api 슬롯 비활성) | D11 위반 — 실행 정본↔권위문서 드리프트 재발 또는 거짓 안전신호(미구현 폴백) 부활 |

> ※ **매뉴얼(외부 repo) 비교 항목은 유지보수자 전용(optional)**. 공개 설치본에는 매뉴얼이 없으므로 핵심 점검(INV1–4·6–12)은 시스템 파일 자체 일관성만 본다. INV5와 각 INV의 매뉴얼 측 일치 검사, INV12e/f의 3 flavor 교차 점검은 아래 스크립트의 optional 블록에서 해당 자산이 있을 때만 실행된다.

## 자가 점검 실행

정본 러너 = `_shared/check-invariants.sh` (exit-code 판정 — 2026-07-24 수동 grep 나열에서 전환, 근거: 자체 리뷰 공통 발견 C2 "false PASS").

```bash
bash _shared/check-invariants.sh              # 핵심 INV1~13 전부 판정. 하나라도 FAIL → exit 비0 (커밋 금지)
bash _shared/check-invariants.sh --self-test  # 러너 자체 검증: 불변식을 하나씩 깨뜨린 fixture 사본이 FAIL하는지
```

- 이 문서의 표(정의)와 러너(판정)가 어긋나면 **표에 맞춰 러너를 고친다** — 표가 정의 정본, 러너가 판정 정본.
- 불변식을 추가·변경하면 러너에 해당 판정과 self-test fixture를 함께 추가한다.
- 유지보수자 전용 점검(외부 매뉴얼 INV5·generator 템플릿 INV12e/f·sync drift)은 해당 자산이 있을 때만 돌고 **WARN**으로 보고한다(exit 영향 없음). INV5는 R3 미해소 동안 의도적 불일치 가능. 매뉴얼 경로 override = `MULTIAGENT_MANUAL_DIR`.

## 전면 재감사가 필요한 경우 (이 점검으로 부족)

- 새 외부 개념·레퍼런스를 시스템에 도입할 때 (개념↔규칙 매핑 자체가 바뀜)
- worker pool 구성·역할이 바뀔 때
- 위 불변식으로 표현 불가한 구조 변경
→ 그때만 `tasks/<new>/`로 새 점검 작업 + 필요 시 codex-critic/gemini. 그 외 일반 수정은 이 스크립트로 충분.
