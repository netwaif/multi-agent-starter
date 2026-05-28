# Design Basis — 왜 이 시스템이 이렇게 생겼나

> **로드 정책**: 이 파일은 평소 작업에서 읽지 않는다. **시스템 파일(_shared/·_templates/·CLAUDE.md·외부 매뉴얼)을 수정·검증하는 작업일 때만** orchestrator가 읽는다. (progressive disclosure — `orchestrator-rules.md` §2 프로토콜 참조)
> 목적: 시스템을 고치거나 검증할 때 GitHub 레퍼런스부터 바닥 재분석하지 않기 위함. 결정의 "왜"를 여기 박아둔다.

## 0. 출처

- 개념 출처: https://github.com/muratcankoylan/Agent-Skills-for-Context-Engineering (MIT)
- 코드 starter: https://github.com/netwaif/multi-agent-starter
- 1차 전면 점검: `tasks/manual-final-review/` (2026-05-15) — review-report.md / sources/github-reference-digest.md 에 상세

## 1. 핵심 개념 → 시스템 규칙 매핑 (재분석 금지, 이 표를 신뢰)

| 레퍼런스 개념 | 시스템에서 구현된 규칙 | 건드릴 때 주의 |
|---|---|---|
| 컨텍스트 = 유한 attention budget | context.md ≤1500자, brief ≤1200자 | 한도 숫자는 근거 있는 값. 바꾸려면 design 근거부터 |
| Progressive disclosure | sources/ 경로참조, brief 최소화, design-basis 게이트 로드 | 새 상시로드 자산 추가 금지 |
| Filesystem = 오버플로 메모리 | task/context/log/brief/result, 런타임 상태 0 | "메모리=파일" 깨는 변경 금지 |
| Lost-in-the-middle | 핵심 제약은 앞, 금지는 끝 (매뉴얼 §3/§6) | 긴 규칙 추가 시 위치 고려 |
| Append-only + provenance | log.md append-only, 태그 6종 | 태그 집합·append-only 불변 |
| 재사용 메모리 기준 | learnings.md (재사용 교훈만) | 일회성·작업특화 적재 금지 |
| Orchestrator 패턴 / 컨텍스트 격리 | Orchestrator=세션, worker별 깨끗한 brief | brief에 타작업 찌꺼기 금지 |
| Telephone game (paraphrase 손실) | worker 원문을 result.md 보존 | 요약본만 저장 금지 |
| Output validation (never trust upstream) | result.md Verification Checklist, 검증 전 전달 금지 | 리뷰어(gemini/codex) 출력도 사실검증 후 채택 |
| Consensus: 다수결 금지, adversarial | codex-critic의 adversarial 리뷰 | critic을 단순 확인용으로 격하 금지 |
| 토큰경제 ~15x | 승인 게이트 + 최소 worker set | "전 worker 기본 호출" 금지 |
| Latent briefing (task-guided 압축) | brief = 그 worker의 그 작업용으로 재구성 (텍스트 근사, KV 불가) | "앞 작업 요약 그대로 전달" 금지 |
| Context degradation: Clash | 문서 충돌 시 권위 우선순위로 해소 | 권위순위(§3) 유지 |
| project-development: single→multi 승격 | routing.md 최소 set, 판단 어려우면 claude-main부터 | 기본 단일, 필요 시만 확장 |

## 2. 권위 우선순위 (Context Clash 해소 규칙)

`CLAUDE.md` > `_shared/routing.md`·`approval-policy.md`·`orchestrator-rules.md` > 외부 매뉴얼(multi-agent-manual.txt).
충돌 발견 시 낮은 쪽을 높은 쪽에 맞추고 log.md에 남긴다. 매뉴얼은 항상 시스템 권위문서에 종속.

## 3. 이미 내린 결정 (재논의 금지, 뒤집으려면 근거 갱신)

- **D1 (B2) write_scope 값 집합** = `none | tasks-only | "패턴"`. `tasks-only`=codex-main 기본(tasks/<task>/ 내부만). CLAUDE.md가 정식 정의처. routing.md·_templates·매뉴얼 동일해야 함. (2026-05-15 R1)
- **D2 (B7) codex-critic 선행조건** = "리뷰 대상 산출물 경로 존재 — 보통 claude-main result.md, 또는 brief에 명시된 기존 코드·문서·소스". claude-main 전용 아님. (2026-05-15 R2)
- **D3 (R5) context.md 구조** = 4섹션 유지. 레퍼런스 5단(Intent/Files/Decisions/State/Next)은 *압축/핸드오프 체크리스트*지 context.md 템플릿 아님. `Files Modified/Decisions Made` 헤딩 도입 금지(히스토리 변질 → log.md 역할 침범). codex-critic 검증 완료. (2026-05-15)
- **D4** gemini는 **단일 브리지 `mcp__gemini-agy__*` 하나만** 사용 — Antigravity 공식 CLI `agy`를 PTY로 감싼 로컬 MCP(도구 4종 `gemini_prompt`/`vision`/`summarize`/`code`). 구 브리지 `mcp__gemini-pro__*`(로컬 프록시)·CLI 래퍼 `mcp__gemini__*`는 모두 폐기 — 잔존 호출 참조 시 도구 미발견으로 즉시 실패. **model 파라미터 없음**: 모델은 agy CLI의 로그인/설정으로 고정되며 호출 시점 선택 불가. FS 접근: vision/summarize/code는 `file_path`로 agy가 파일을 직접 읽음(구 브리지의 "gemini FS 미접근" 가정 일부 폐기), `gemini_prompt`는 인라인 텍스트만 → 검토 자료는 Orchestrator가 prompt에 inline. 리뷰어(gemini) 출력의 시스템 사실 주장은 권위문서로 교차검증 후 채택(never-trust-upstream). (이력: 초기 2-브리지[`mcp__gemini__*` Flash + `mcp__gemini-pro__*` Pro], 폴백 pro-high→pro-low→Flash → 2026-05-19 C1: pro-high 로컬 프록시 `400 INVALID_ARGUMENT` 재현·pro-low 정상[learnings.md 2026-05-15] → 2026-05-20 C2: gemini-mcp(CLI) 폐기, 단일 gemini-pro 브리지+Flash model 파라미터 → **2026-05-28**: 로컬 프록시 브리지 자체 폐기, Antigravity CLI 기반 단일 `gemini-agy` 브리지로 전환. model 파라미터·pro-low/flash 선택 정책 폐기[모델 agy CLI 고정])
- **D5** MultiAgent 작업은 인터랙티브 세션 전용, worktree/백그라운드 세션 금지. (orchestrator-rules.md §1)

## 4. 불변식

구체 항목·검증 명령은 `_shared/system-invariants.md`. 시스템 수정 후 그 자가점검을 돌린다.
