# Design Basis — 왜 이 시스템이 이렇게 생겼나

> **로드 정책**: 이 파일은 평소 작업에서 읽지 않는다. **시스템 파일(_shared/·_templates/·CLAUDE.md·외부 매뉴얼)을 수정·검증하는 작업일 때만** orchestrator가 읽는다. (progressive disclosure — `orchestrator-rules.md` §2 프로토콜 참조)
> 목적: 시스템을 고치거나 검증할 때 GitHub 레퍼런스부터 바닥 재분석하지 않기 위함. 결정의 "왜"를 여기 박아둔다.

## 0. 출처

- 개념 출처: https://github.com/muratcankoylan/Agent-Skills-for-Context-Engineering (MIT)
- 4원칙(운영 원칙) 출처: https://github.com/multica-ai/andrej-karpathy-skills (MIT 선언, LICENSE 파일 부재 — 표기는 `NOTICE` 참조)
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
| Fan-out/Fan-in + 작업 재진입 | routing.md 토폴로지표·Fan-in 규칙, orchestrator-rules §3 | 병렬 통합·재진입 분기는 기존 append-only+provenance·never-trust-upstream 재사용. 새 원칙 아님 |

## 2. 권위 우선순위 (Context Clash 해소 규칙)

`CLAUDE.md` > `_shared/routing.md`·`approval-policy.md`·`orchestrator-rules.md` > 외부 매뉴얼(multi-agent-manual.txt).
충돌 발견 시 낮은 쪽을 높은 쪽에 맞추고 log.md에 남긴다. 매뉴얼은 항상 시스템 권위문서에 종속.

## 3. 이미 내린 결정 (재논의 금지, 뒤집으려면 근거 갱신)

- **D1 (B2) write_scope 값 집합** = `none | tasks-only | "패턴"`. `tasks-only`=codex-main 기본(tasks/<task>/ 내부만). CLAUDE.md가 정식 정의처. routing.md·_templates·매뉴얼 동일해야 함. (2026-05-15 R1)
- **D2 (B7) codex-critic 선행조건** = "리뷰 대상 산출물 경로 존재 — 보통 claude-main result.md, 또는 brief에 명시된 기존 코드·문서·소스". claude-main 전용 아님. (2026-05-15 R2)
- **D3 (R5) context.md 구조** = 4섹션 유지. 레퍼런스 5단(Intent/Files/Decisions/State/Next)은 *압축/핸드오프 체크리스트*지 context.md 템플릿 아님. `Files Modified/Decisions Made` 헤딩 도입 금지(히스토리 변질 → log.md 역할 침범). codex-critic 검증 완료. (2026-05-15)
- **D4** gemini 백엔드 = **Antigravity `agy` CLI**(`_shared/backends.json` 정본, 디스패처 `_shared/adapters/call_worker.sh`). 기본 모델 = `gemini-3.1-pro-high`, 빠른 경로 = `gemini-3-flash`/`pro-low`, 폴백 없음(api 슬롯 미구현·비활성 — D11로 fallbacks에서 제거, 2026-07-24. 구현 후 재등록). 옛 단일 브리지 `mcp__gemini-pro__*`(antigravity-claude-proxy 의존)·CLI 래퍼 `mcp__gemini__*`는 **폐기**(잔존 활성 참조는 호출 실패). `pro-high`를 기본·폴백에서 제외했던 사유(로컬 프록시 `400 INVALID_ARGUMENT` 재현, learnings 2026-05-15)는 **agy 백엔드엔 비해당** — agy로 pro-high 정상 실증(2026-06-02). agy 모델은 전역·계정단위(`/model`)라 per-call 핀 불가 → gemini 전용 전역을 pro-high로 운용. 폴백 모델의 시스템 사실 주장은 권위문서로 교차검증 후 채택. (근거 갱신 2026-06-02: tasks/v2-harness-adapter-build/ — agy 백엔드 전환 spike+3자검수. 이전: 2026-05-19~20 단일 mcp__gemini-pro__ 브리지·pro-low 기본·pro-high 제외, 프록시 의존)
- **D5** MultiAgent 작업은 인터랙티브 세션 전용, worktree/백그라운드 세션 금지. (orchestrator-rules.md §1)
- **D6** 작업 재진입 프로토콜(orchestrator-rules §3) + 토폴로지 4패턴(routing.md) 채택, Supervisor·Hierarchical Delegation **배제**. 배제 대상은 *개념*이 아니라 *추가 계층*임에 유의 — 기존 단일 orchestrator를 Supervisor로 재명명하는 게 아니라, 그 위에 (Supervisor) 별도 long-lived 조정자 worker/런타임 동적분배 계층, (Hierarchical) worker가 worker를 부르는 재귀 위임 트리를 추가하는 것을 배제한다. 근거: (a) 단일 orchestrator, (b) worker간 무통신(전부 orchestrator 경유+승인 게이트), (c) file-as-memory(런타임 0). 추가 계층은 (b)(c)와 승인·비용·감사를 무너뜨림. 재진입 프로토콜은 콜드세션 재정박 공백(사용자 보고 통증)을 메움. 부분재실행·에러처리·Fan-in 충돌해소는 모두 기존 불변식(append-only+provenance, never-trust-upstream, 최소 worker set)의 재배치 — 새 원칙 아님. 출처: harness(revfactory) 6패턴 중 4개 선별, tasks/harness-vup-reentry/ (codex-critic 검토 반영). 매뉴얼 동기화는 후속(manual sync pending). (2026-06-01)
- **D7** 모델 식별자 표기 정책 = **휘발성 높은 식별자는 별칭으로, 안정적인 핀만 핀으로**. 근거: "현재 모델 식별자"는 시스템이 아니라 *환경*이 소유하는 사실이며 워커마다 변동성이 다르다. (a) **claude-main** = 별칭 `opus`(Anthropic이 최신 Opus로 해석) — 버전 문자열 핀 금지. (b) **codex** = `~/.codex/config.toml` 기본값이 정본 — repo에 버전 핀 금지(routing은 "예시"로만). (c) **gemini** = 백엔드 `agy` CLI, 기본 `gemini-3.1-pro-high` **핀 유지** — agy 모델은 전역·계정단위(`/model`)라 per-call 핀 불가하므로 backends.json에 명시 핀이 정본(별칭화 부적합). 모델 전환은 드문·의도적 이벤트. **gemini 세부 정책(백엔드·기본·폴백)의 정본은 D4** — D7은 표기 원칙만 다룬다. (옛 `pro-low`+프록시 핀은 D4 마이그레이션으로 폐기, 2026-06-02) **추론 강도(effort)**: claude-main은 `effort` 핀 없이 세션 `/effort` 상속(운영자 종속)이 현 기본 — 세션과 무관하게 고정하려면 frontmatter `effort:` 명시(상속 끔). codex는 config.toml에 `model_reasoning_effort: high`가 **지속 기본값**으로 박혀 있음(운영자 환경 기준 고정적이나 config·profile·brief·MCP 파라미터로 바뀔 수 있음 — "결정적"은 아님). claude-main 세션 상속과의 비대칭은 의도된 현 상태. 출처: tasks/model-policy-cleanup/ (codex-critic 검수 반영). (2026-06-01)

- **D8 카파시 4원칙 층별 적용** = 오케스트레이터 지침(CLAUDE.md "운영 원칙 (Operating Principles)" 섹션) 풀버전 verbatim 차용(도입 tradeoff·말미 성공지표 포함) / 워커층 유일 정본은 `_templates/worker-brief.md`의 "Worker 행동 규약" 고정 블록 — ②단순함·③외과수술식 그대로 + ①추측전질문은 **번역형**(워커는 one-shot/headless라 사용자 질문 채널 없음 → 가정 명시·불확실/불일치를 result.md Issues/Caveats에 표면화) / ④목표기반 loop은 오케스트레이터 전용(Verification Checklist 루프와 결합). 워커 brief·agent 정의에 "사용자에게 질문" 지시 금지, agent 정의에 규약 중복 금지(brief가 모든 워커에 닿는 유일 운반체 — call_worker.sh가 brief를 통째로 전달). 기존 D와 무충돌·동방향 보강(②=최소 worker set·토큰경제, ③=write_scope 4조건, ④=never-trust-upstream 검증, D6 구조 불변). 출처: multica-ai/andrej-karpathy-skills — MIT는 README·plugin.json 선언 기준이며 상류에 LICENSE 파일 없음(2026-06-10 확인), 재배포 표기는 `NOTICE` 정본. (2026-06-10, tasks/karpathy-wiki-upgrade/)

- **D12 라우팅 2층 분리** = `routing.md`(안정층: 작업 유형→능력 슬롯 strategist·engineer·computer-use·reviewer·multimodal)와 `_shared/capability-profile.md`(가변층: 슬롯→담당 배정, 근거·날짜 필수, 이력 append-only). 트리의 담당명 병기는 편의 사본 — 프로필이 정본. 근거: 모델별 강점 우열은 신모델 출시마다 바뀌는 *환경 소유 사실*(D7 동방향)이라 시스템 파일에 구우면 세대마다 개정 부채가 된다. 초기 배정 근거 = 2026-07-13 외부 리뷰 10건 종합 판정(Anthropic vs OpenAI 최신 플래그십): 설계·UI/UX 디자인·전략·글쓰기 = Claude 우위, 대규모 구현·테스트·브라우저 조작·비용·속도·토큰 효율 = GPT 우위로 수렴 — computer-use 슬롯 신설 동근거. 갱신은 판정 자료 확보 시 프로필만(절차는 프로필 파일이 정본). 검증: validate C1(프로필 존재)+C5b(routing→profile 참조, 슬롯 5종). (2026-07-13)
- **D13 payload 분리(brief 한도 밖 동봉 자료)** = 디스패처 `call_worker.sh <role> <brief> [payload]` 3번째 인자. gemini 소스 검토의 "brief 인라인 필수"(2026-07-04 실측)가 brief 불변식(inline 금지·1200자, CLAUDE.md Context Rules)과 정면 모순이던 것을 해소 — 자료는 `tasks/<task>/sources/gemini-packet.md`로 분리하고 디스패처가 "동봉 자료" 헤더로 결합(`--merged-preview`로 사전 검증). brief 규칙에 예외를 만들지 않는다. FS-미접근·헤드리스 순회 불가 백엔드 일반에 적용. (2026-07-24)

- **D11 backends.json 실행계약 정합 + 미구현 폴백 비활성** = `backends.json`은 실행 정본이므로 권위문서(routing.md)의 워커 계약과 **항상 일치**해야 한다(INV13). ① **codex sandbox 정본**: codex-main = `workspace-write`(MCP·CLI 폴백 동일 — CLAUDE.md 쓰기표 "tasks/<task>/ 내부 산출물 직접 작성"의 전제), codex-critic = `read-only`(비평 모드 쓰기 금지). 종전 backends의 codex-main `read-only`는 routing.md·CLAUDE.md와 모순된 드리프트였음(2026-07-24 이중 독립 리뷰 공통 검출). 번호 주의: D9·D10은 유지보수자 저장소 전용 결정(knot·요금가드 배포 구조)이라 설치본에선 결번 — 결정 번호는 루트 정본과 공유(v3.3 당시 D9였던 2층 분리는 D12로 재정렬). ② **approval-policy**: 헤드리스 호출은 `never`(승인 프롬프트 불가 환경에서 결정적 거부, fail-closed). "on-failure 권장"은 대화형 수동 호출 한정. ③ **MCP stale 폴백 정본화**: codex MCP 실패(모델 버전 에러 등) 시 `codex exec --sandbox <계약값>` 헤드리스가 정본 폴백 — backends CLI 폴백에 sandbox·`cwd_policy: target` 명시(디스패처 기본 cwd=루트로 새는 것 방지). ④ **미구현 폴백은 등록 금지**: gemini api 폴백 슬롯(`gemini_api.sh`)은 무조건 exit 4인 스텁인데 fallbacks에 등록돼 "폴백 있음"이라는 거짓 안전신호를 냈음 → fallbacks `[]` + note로 비활성. 일반 원칙: **선언된 능력(capability)은 구현이 존재할 때만 backends에 등록**한다. **(2026-07-24 후속: 디스패처가 읽지 않는 선언 `write_policy`·`non_interactive` 제거 — approval_class·result_capture는 오케스트레이터·validate가, cwd_policy·timeout·brief_mode는 디스패처가 실제 소비하므로 존치.)** (2026-07-24)

## 4. 불변식

구체 항목·검증 명령은 `_shared/system-invariants.md`. 시스템 수정 후 그 자가점검을 돌린다.
