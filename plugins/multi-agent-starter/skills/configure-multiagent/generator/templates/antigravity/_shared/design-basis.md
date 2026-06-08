# Design Basis — 왜 이 시스템이 이렇게 생겼나

> **로드 정책**: 이 파일은 평소 작업에서 읽지 않는다. 시스템 파일(`AGENTS.md`, `_shared/*`, `_templates/*`)을 수정·검증할 때만 읽는다.

## 0. 출처

- 원본 starter: multi-agent-starter
- Antigravity flavor: multi-agent-starter의 Antigravity(Gemini) orchestrator 파생본
- 사용자 결정: Antigravity(agy/IDE, Gemini 3.1 Pro High)가 메인 오케스트레이터가 되며, 산출물 비평은 자기벤더(gemini) 자기검수가 아니라 교차벤더 독립성 있는 `codex-critic`이 맡는다. 메인 코딩은 `claude-main`.

## 1. 핵심 개념 → 시스템 규칙 매핑

| 개념 | 시스템 규칙 | 주의 |
|------|-------------|------|
| 컨텍스트 = 유한 attention budget | context.md <= 1500자, brief <= 1200자 | 한도 변경 시 불변식 갱신 |
| Progressive disclosure | sources/ 경로 참조, brief 최소화 | 긴 자료 inline 금지 |
| Filesystem = memory | task/context/log/brief/result | 런타임 상태에 의존하지 않음 |
| Append-only + provenance | log.md append-only, 태그 6종 | 로그 삭제·수정 금지 |
| Never trust upstream | worker result 검증 후 채택 | 모든 worker(claude-main/codex-main/codex-critic) 출력 사실검증 |
| Adversarial review | `codex-critic` | Gemini(오케스트레이터) 자기검수로 대체 금지 |
| 최소 worker set | routing.md decision tree | 모든 worker 기본 호출 금지 |
| Fan-in 충돌 해소 | 출처 병기, 사실검증, `[DECISION]` | 다수결 금지 |

## 2. 권위 우선순위

`AGENTS.md` > `_shared/routing.md`·`approval-policy.md`·`orchestrator-rules.md` > `_templates/*`.

충돌 발견 시 낮은 쪽을 높은 쪽에 맞추고, 작업 중인 task의 `log.md`에 `[DECISION]`으로 남긴다.

## 3. 결정 기록

- **D1 write_scope 값 집합** = `none | tasks-only | "패턴"`. `tasks-only`는 `tasks/<task>/` 내부만 쓰는 기본값이다.
- **D2 critic 역할** = Antigravity 버전에서 산출물 리뷰 worker는 `codex-critic`(교차벤더)다. 오케스트레이터가 Gemini라 gemini 자기검수(gemini-critic)는 독립성이 없어 사용하지 않는다.
- **D3 codex-critic 선행조건** = 리뷰 대상 산출물 경로가 존재해야 한다. 대상은 `claude-main`/`codex-main result.md`, Orchestrator 산출물, 기존 코드·문서·소스도 가능하다.
- **D4 gemini 정책** = gemini는 **워커가 아니라 오케스트레이터**(Antigravity agy/IDE, 전역 모델 `gemini-3.1-pro-high`). 멀티모달·긴 문서는 오케스트레이터가 직접 처리하고 **별도 gemini 워커는 두지 않는다**(같은 벤더라 독립성 이득 없음). agy 모델은 전역·계정단위(`/model`)라 gemini 전용 전역을 pro-high로 운용.
- **D5 Orchestrator** = Antigravity(agy/IDE, Gemini 3.1 Pro High) 현재 세션이 단일 Orchestrator다. 별도 long-lived supervisor worker나 worker 재귀 위임 계층은 쓰지 않는다.
- **D6 모델 식별자 표기** = 워커(claude-main/codex-main/codex-critic)는 환경 설정/별칭을 따르고 repo에 버전 문자열을 핀하지 않는다. 오케스트레이터 Gemini는 agy 전역 모델 = `gemini-3.1-pro-high`(전역·계정단위라 per-call 핀 불가).
- **D7 backends.json 2-테이블 (provider/role 분리)** = backends.json은 `schema_version:"2"`에서 **`providers`(백엔드 레코드 카탈로그) + `roles`(role→provider 바인딩 +staffing +desk)** 2-테이블 구조다. 디스패처(`call_worker.sh`)는 `roles[role].provider → providers[provider]`로 해석한다. 역할의 담당 프로바이더 교체 = `roles` 한 줄 수정(레코드·코드 불변). 폐기된 단일 `workers` 맵(role=레코드 1:1)은 금지(`validate.py` C9가 `workers` 키 잔존·미해결 provider 바인딩을 FAIL). 기본 바인딩은 이전 `workers`와 동일(행위 0)하게 identity 마이그레이션 — provider 정규화·family 분리·CT 역할 매핑은 후속 단계. 근거: 자유로운 프로바이더 교체(설정만으로 역할별 담당 변경) + 컨텍스트 관리(staffing). (2026-06-09, tasks/free-provider-swap/)
- **D8 자유 프로바이더 교체 + 가드 (provider 카탈로그·family·bridge·staffing·C10)** = 2-테이블(D7) 위에: (1)**providers 카탈로그 확장** — grok(cli·family xai·`best_of_n`)·hermes/openclaw(call_type `bridge`·`promotion_state:"inactive"`) + 모든 provider에 **`family`**(anthropic/openai/xai/google/hermes/openclaw). 역할은 `roles[r].provider` 한 줄로 카탈로그의 어느 provider로든 교체(free swapping). (2)**cli allowlist** `{agy,codex,claude,grok}` — call_worker.sh case + validate `_CLI_ALLOWLIST` 양쪽 하드코딩, **config로 못 넓힘**, C9c가 둘 동기화 강제. (3)**bridge fail-closed** — hermes/openclaw는 미승격이라 role 바인딩 시 validate FAIL + dispatch 시 call_worker die(exit 3); promotion gate(Phase 2) 후에만 활성. (4)**staffing(분신)** — `roles[r].staffing{mode,max,decided_by}`; mode=auto는 provider-native best_of_n(grok `--best-of-n N`)을 1 dispatcher 호출 내부 N→1 envelope(오케스트레이터 복제 아님, D6/routing.md:44 정합); 기본 fixed N=1. (5)**C10 family-disjoint(하중벽)** — `roles[r].class`(main/aux/reviewer/scout/tool) + `orchestrator_family`. reviewer 역할의 **resolved**(declared 아님) family ∉ {orchestrator_family ∪ 모든 main 역할 family} — 자기벤더 자기검수 금지, **validate(생성시)+call_worker(swap-then-run) 양쪽** fail-closed(die exit 9). C8b(이름기반 forbidden_worker)의 family 차원 일반화. ※role의 class를 reviewer 아닌 값(aux 등)으로 바꾸면 C10 면제 = **의도된 동작**(class=보안존 선언). CT 역할 restructure(기능slug rename·신규역할·Hermes 활성)는 governance라 별도 4-surface council 비준 — **만장일치 완료(2026-06-09): D1=B(현 이름 유지 + `awo_role`[AWO 9-role coverage] 필수 메타, rename 거부)·D2=현 dispatch역할 유지+CT는 awo_role 매핑(headless `scout`=grok 추가; Project-memory reviewer·Evidence custodian 영구 제외)·D3=Hermes fail-closed 유지·D4=Phase2 연기.** 가드는 이름 아닌 권위키(class·resolved family)를 읽음(조건 충족). 원장 council-ct-roles/COUNCIL-RESULT.md. (2026-06-09, tasks/free-provider-swap/)

## 4. 불변식

구체 항목과 점검 명령은 `_shared/system-invariants.md`에 둔다.
