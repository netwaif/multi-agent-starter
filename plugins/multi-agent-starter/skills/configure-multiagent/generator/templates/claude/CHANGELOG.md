# Changelog

이 파일은 MultiAgent orchestration 시스템의 주요 변경을 기록한다.
형식은 [Keep a Changelog](https://keepachangelog.com/), 버전은 [Semantic Versioning](https://semver.org/lang/ko/)을 따른다.

## [1.4.0] - 2026-07-24

### Fixed
- **codex sandbox 실행계약 모순 교정** — `backends.json`의 codex-main이 `read-only`로
  선언돼 routing.md(`workspace-write` 고정)·CLAUDE.md 쓰기 정책 표(tasks/ 내부 직접 작성)와
  모순되던 드리프트 수정. codex-main = `workspace-write`, codex-critic = `read-only`로
  통일하고 CLI 폴백에도 `--sandbox`·`cwd_policy: target` 명시. 근거: design-basis D10.
- **gemini api 폴백 비활성** — 미구현 스텁(`gemini_api.sh`, 무조건 exit 4)이 fallbacks에
  등록돼 "폴백 있음"이라는 거짓 안전신호를 내던 문제. fallbacks에서 제거(구현 후 재등록).

### Added
- **INV13(backends 실행계약 정합)** — codex sandbox 계약·gemini 폴백 비활성을 jq 기반
  PASS/FAIL로 자가점검. codex MCP stale 시 `codex exec` 헤드리스 폴백 절차를 routing.md에 정본화.
- **불변식 자가점검 러너 `_shared/check-invariants.sh`** — 자가점검을 "grep 눈 판독"에서
  exit-code 판정으로 전환(false PASS 방지). `--self-test` = 불변식을 하나씩 깨뜨린 fixture가
  FAIL하는지 러너 자체 검증. system-invariants.md의 수동 스크립트 블록 대체.
- **디스패처 payload 동봉** — `call_worker.sh <role> <brief> [payload]` + `--merged-preview`.
  gemini 소스 검토 자료를 brief 인라인 대신 `sources/gemini-packet.md`로 동봉(디스패처 결합) —
  brief 불변식(inline 금지·1200자)과의 모순 해소. design-basis D13.
- backends.json에서 디스패처가 읽지 않는 선언(`write_policy`·`non_interactive`) 제거
  (희망사항 config = 거짓 안전신호 방지, D11 후속).

### Changed
- **design-basis 결정 번호 재정렬** — 라우팅 2층 분리 D9→D12, backends 실행계약 D10→D11.
  결정 번호를 유지보수자 루트 정본과 공유하기 위함(설치본 범위 밖 결정 D9·D10은 결번 표기).
- **v1.3.0 개편 때 누락된 상세 규칙 복원** — gemini 이미지/PDF 검수 단일 정본 경로(필독 절)·
  새 작업 폴더 생성 게이트 상세(orchestrator-rules §3·task-folder 안내)·worker-brief의
  gemini 경로 주석 등 유지보수자 루트에만 남아 있던 규칙을 재수록.

## [1.3.0] - 2026-07-13

### Added
- **라우팅 2층 분리 — `_shared/capability-profile.md` 신설(가변층)** — 능력 슬롯
  (strategist·engineer·computer-use·reviewer·multimodal) → 담당 워커 배정의 정본.
  신모델 출시·판정 변경 시 프로필만 갱신(근거·날짜 필수, 이력 append-only) — routing.md의
  슬롯 정의는 불변. 근거: design-basis D9 (2026-07-13 외부 리뷰 10건 종합 판정).
- **computer-use 슬롯 신설** — 브라우저 조작·도구 워크플로우 자동화를 독립 라우팅
  (현 배정: codex-main).

### Changed
- routing.md decision tree를 슬롯 기반으로 재편 — strategist(기획·설계·디자인·전략·문체)
  = claude-main, engineer(대규모 구현·테스트) = codex-main. 종전 "메인 코딩=claude-main,
  보조 구현=codex-main" 구도에서 무게중심 이동. 최소 worker set 표 동기화.
- validate에 C5b(2층 라우팅: routing→profile 참조 + 슬롯 5종) 추가, C1에 프로필 포함.

## [1.2.2] - 2026-07-04

### Fixed
- **gemini 워커 폴백 실패 사유 유실** — 디스패처(`call_worker.sh`)가 api 폴백의 필수 env
  (`GEMINI_API_KEY`) 부재 시 실패 사유 없이 죽던 문제를 에러 envelope 반환으로 수정,
  호출 시작 시 폴백 불가 사전 경고 추가.

### Changed
- routing.md gemini — 소스·다중파일 검토 인라인 필수(agy 헤드리스 300s 타임아웃 실측),
  폴백 조건(`GEMINI_API_KEY`) 명문화, 시간 제한 작업 전 경량 스모크 권장.

## [1.2.1] - 2026-07-03

### Fixed
- **gemini(agy) 워커 프롬프트 미전달 수정** — Antigravity CLI 1.0.16에서 `-p` 단축 플래그가
  제거되어 backends.json의 `args_template: ["-p", …]`가 프롬프트를 조용히 무시(모델 미호출·사용량 0).
  `["--prompt", …]`로 교정. 증상: gemini 워커가 온보딩 인사만 반환.

## [1.2.0] - 2026-06-28

### Added
- **opt-in goal 요금가드 배선(`--with-guard`)** — 설치 시 `--with-guard`를 주면 `.claude/settings.json`에
  Stop 훅(`coach --hook`)이 주입된다. `/goal` 자율 루프가 주간 사용량 한도에 닿으면 자동 정지(루프
  중에만 — `stop_hook_active` 게이트). 기본 미설치, 런타임 on/off=`coach guard on/off`. 정책은 `coach`
  (usage-coach, codexbar 의존)가 갖고 미설치·조회실패는 fail-open(작업 안 죽임).

## [1.1.0] - 2026-06-10

카파시(Karpathy) 4원칙을 층별로 도입. 기존 규칙과 충돌 없음(보강).

### Added
- **CLAUDE.md "운영 원칙 (Operating Principles)" 섹션** — 4원칙(Think Before Coding / Simplicity First / Surgical Changes / Goal-Driven Execution) verbatim 차용 + 층별 적용 규칙. Orchestrator 전용 풀버전.
- **`_templates/worker-brief.md` "Worker 행동 규약" 고정 블록** — 워커층 번역형: ②③ 그대로, ①은 가정 명시·표면화(워커는 one-shot이라 사용자 질문 채널 없음), ④는 오케스트레이터 전용.
- **`_templates/worker-result.md` 체크리스트 항목** — "가정·불일치가 Issues/Caveats에 표면화됨".
- **design-basis D8 / system-invariants INV12** — 층별 적용 결정 명문화 + 자가점검.
- **`NOTICE`** — 출처·라이선스 표기 (multica-ai/andrej-karpathy-skills, MIT 선언·LICENSE 파일 부재).

## [1.0.1] - 2026-06-01

모델·추론 정책 표기 정리(문서 patch). 동작 변경 없음.

### Changed
- **모델 식별자 별칭화** (`_shared/routing.md`): claude-main을 버전 문자열(`claude-opus-4-7` 등) 대신 별칭 `opus`로 표기 — 모델이 올라가도 문서 갱신 불필요. codex 예시 일반화, gemini는 `gemini-3.1-pro-low` 핀 유지 + "프록시 업그레이드 시에만 갱신" 노트.
- **claude-main 추론 강도(effort) 명문화**: `effort` 핀 없음 → 세션 `/effort` 상속(현 기본). 고정하려면 frontmatter `effort:`.

### Added
- **design-basis D7**: 모델 식별자 표기 정책(별칭 원칙 / gemini 핀 예외·세부는 D4 정본 / effort 비대칭 근거).

### Verification
- codex-critic adversarial 검수: 치명 0, 권장 3 반영(잔존 핀 제거 포함). INV9/INV10/INV11 PASS, 회귀 없음.

## [1.0.0] - 2026-06-01

첫 버전 태깅. 기존 실사용 시스템을 1.0.0 기준선으로 고정하고, harness(revfactory) 참고 버전 업그레이드를 함께 반영한다.

### Added
- **작업 재진입 프로토콜** (`_shared/orchestrator-rules.md` §3): 콜드세션이 끝난 작업에 다시 들어갈 때 재정박(re-anchor) → 6분기 판단 → 에러 후 진행. `status↔log 불일치`는 다른 분기보다 먼저 적용하는 정규화 단계로 명시.
- **토폴로지 4패턴표** (`_shared/routing.md`): Pipeline / Fan-out·Fan-in / Expert Pool / Producer-Reviewer + Fan-in 규칙.
- **CLAUDE.md** Task Lifecycle에 재진입 프로토콜 포인터.
- **불변식 INV11** (`_shared/system-invariants.md`): 재진입·토폴로지 규정 자동 자가점검(11a/b/c).
- **design-basis D6**: 4패턴 채택 + Supervisor·Hierarchical Delegation 배제 근거.

### Excluded (설계 결정)
- Supervisor·Hierarchical Delegation 패턴: 단일 orchestrator·worker간 무통신·file-as-memory와 충돌하여 미채택 (근거 D6).

### Baseline (1.0.0 시점 핵심 구조)
- 고정 4-worker pool (claude-main / codex-main / codex-critic / gemini), Claude Code 세션 = orchestrator.
- file-as-memory (런타임 상태 0): task / context / log / brief / result.
- 승인 게이트(`workers_approved`), 외부 쓰기 4조건, progressive disclosure(게이트 로드), 권위 우선순위(CLAUDE.md > routing/approval/orchestrator-rules > 매뉴얼).

### Verification
- 배선(INV11a/b/c) PASS · 회귀 없음, 탁상 분기 커버리지, 실전 콜드세션 3/3 PASS, codex-critic adversarial 리뷰 5 ISSUE 반영.

[1.0.1]: https://github.com/netwaif/multi-agent-starter/releases/tag/v1.0.1
[1.0.0]: https://github.com/netwaif/multi-agent-starter/releases/tag/v1.0.0
