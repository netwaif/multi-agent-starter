# Design Basis — 왜 이 시스템이 이렇게 생겼나

> **로드 정책**: 이 파일은 평소 작업에서 읽지 않는다. 시스템 파일(`AGENTS.md`, `_shared/*`, `_templates/*`)을 수정·검증할 때만 읽는다.

## 0. 출처

- 원본 starter: multi-agent-starter
- Codex flavor: multi-agent-starter의 Codex orchestrator 파생본
- 4원칙(Operating Principles) 출처: https://github.com/multica-ai/andrej-karpathy-skills (MIT 선언, LICENSE 파일 부재 — 표기는 `NOTICE` 참조)
- 사용자 결정: Codex가 메인 오케스트레이터가 되며, Codex 산출물 비평은 자기검수인 `codex-critic`이 아니라 독립성 있는 `claude-critic`이 맡는다.

## 1. 핵심 개념 → 시스템 규칙 매핑

| 개념 | 시스템 규칙 | 주의 |
|------|-------------|------|
| 컨텍스트 = 유한 attention budget | context.md <= 1500자, brief <= 1200자 | 한도 변경 시 불변식 갱신 |
| Progressive disclosure | sources/ 경로 참조, brief 최소화 | 긴 자료 inline 금지 |
| Filesystem = memory | task/context/log/brief/result | 런타임 상태에 의존하지 않음 |
| Append-only + provenance | log.md append-only, 태그 6종 | 로그 삭제·수정 금지 |
| Never trust upstream | worker result 검증 후 채택 | critic/gemini 출력도 사실검증 |
| Adversarial review | `claude-critic` | Codex 자기검수로 대체 금지 |
| 최소 worker set | routing.md decision tree | 모든 worker 기본 호출 금지 |
| Fan-in 충돌 해소 | 출처 병기, 사실검증, `[DECISION]` | 다수결 금지 |

## 2. 권위 우선순위

`AGENTS.md` > `_shared/routing.md`·`approval-policy.md`·`orchestrator-rules.md` > `_templates/*`.

충돌 발견 시 낮은 쪽을 높은 쪽에 맞추고, 작업 중인 task의 `log.md`에 `[DECISION]`으로 남긴다.

## 3. 결정 기록

- **D1 write_scope 값 집합** = `none | tasks-only | "패턴"`. `tasks-only`는 `tasks/<task>/` 내부만 쓰는 기본값이다.
- **D2 critic 역할** = Codex 버전에서 산출물 리뷰 worker는 `claude-critic`이다. Codex가 자기 산출물을 다시 검수하는 `codex-critic` 구조는 사용하지 않는다.
- **D3 claude-critic 선행조건** = 리뷰 대상 산출물 경로가 존재해야 한다. 대상은 `codex-main result.md`로 한정하지 않고, Orchestrator 산출물·기존 코드·문서·소스도 가능하다.
- **D4 gemini 정책** = 백엔드 Antigravity `agy` CLI(`_shared/backends.json` 정본, 디스패처 `call_worker.sh`). 기본 `gemini-3.1-pro-high`를 `--model`로 per-call 고정하고 폴백은 두지 않는다. 옛 프록시 브리지는 폐기한다.
- **D5 Orchestrator** = Codex 현재 세션이 단일 Orchestrator다. 별도 long-lived supervisor worker나 worker 재귀 위임 계층은 쓰지 않는다.
- **D6 모델 식별자 표기** = Codex와 Claude는 환경 설정/별칭을 따른다. Gemini는 `backends.json` 선언과 agy `--model` argv를 함께 `gemini-3.1-pro-high`로 핀한다. 세부는 D4.
- **D10 claude-critic 실행 계약** = `model: host-default`는 Claude CLI 계정 기본값을 의도하므로 `--model`을 전달하지 않는다. Claude 시작 플러그인의 cwd 쓰기 부작용을 차단하기 위해 `cwd_policy: isolated_tmp`에서 실행하고 대상 저장소는 `--add-dir @target_repo`로만 읽게 한다. `--tools Read,Glob,Grep`와 slash-command 비활성으로 write_scope none을 명령 차원에서 강제한다.
- **D7 카파시 4원칙 층별 적용** = 오케스트레이터 지침(AGENTS.md "Operating Principles" 섹션) 풀버전 verbatim 차용 / 워커층 유일 정본은 `_templates/worker-brief.md`의 "Worker 행동 규약" 고정 블록 — ②단순함·③외과수술식 그대로 + ①추측전질문은 번역형(워커는 one-shot/headless라 사용자 질문 채널 없음 → 가정 명시·불확실/불일치를 result.md Issues/Caveats에 표면화) / ④목표기반 loop은 오케스트레이터 전용(Verification Checklist 루프와 결합). 워커 brief에 "사용자에게 질문" 지시 금지. 출처: multica-ai/andrej-karpathy-skills (MIT 선언, LICENSE 파일 부재 — `NOTICE` 정본, 2026-06-10 확인).
- **D8 라우팅 2층 분리** = `routing.md`(안정층: 작업 유형→능력 슬롯 strategist·engineer·computer-use·reviewer·multimodal)와 `_shared/capability-profile.md`(가변층: 슬롯→담당 배정, 근거·날짜 필수, 이력 append-only). 트리의 담당명 병기는 편의 사본 — 프로필이 정본. 근거: 모델별 강점 우열은 신모델 출시마다 바뀌는 *환경 소유 사실*(D6 동방향)이라 시스템 파일에 구우면 세대마다 개정 부채가 된다. 초기 배정 근거 = 2026-07-13 외부 리뷰 10건 종합 판정(Anthropic vs OpenAI 최신 플래그십): 설계·UI/UX 디자인·전략·글쓰기 = Claude 우위, 대규모 구현·테스트·브라우저 조작·비용·속도·토큰 효율 = GPT 우위로 수렴 — computer-use 슬롯 신설 및 이 flavor의 strategist 게이트(claude-critic) 동근거. 갱신은 판정 자료 확보 시 프로필만(절차는 프로필 파일이 정본). 검증: validate C1(프로필 존재)+C5b(routing→profile 참조, 슬롯 5종). (2026-07-13)
- **D9 payload 분리(brief 한도 밖 동봉 자료)** = 디스패처 `call_worker.sh <role> <brief> [payload]` 3번째 인자. gemini 소스 검토의 "인라인 필수"(2026-07-04 실측)가 brief 불변식(inline 금지·1200자)과 모순이던 것을 해소 — 자료는 `sources/gemini-packet.md`로 분리하고 디스패처가 결합(`--merged-preview`로 검증). brief 규칙에 예외 없음. 아울러 backends.json에서 디스패처가 읽지 않는 선언(`write_policy`·`non_interactive`)과 미구현 api 폴백을 제거 — 선언된 능력은 구현이 있을 때만 등록(거짓 안전신호 금지, INV12). (2026-07-24)

## 4. 불변식

구체 항목과 점검 명령은 `_shared/system-invariants.md`에 둔다.
