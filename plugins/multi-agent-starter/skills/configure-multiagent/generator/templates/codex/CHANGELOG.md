# Changelog

이 파일은 multi-agent-starter (Codex flavor) orchestration 시스템의 주요 변경을 기록한다.

## [0.6.0] - 2026-09-06

### Added
- **집행층 코드화 (D10)** — `_shared/adapters/gate.sh`(worker 호출 사전 게이트, fail-closed: 승인·`[APPROVAL]`
  로그·brief 위치/한도·외부 쓰기 조건 정확 일치·인터랙티브 세션) · `_shared/adapters/scope_check.sh`(write_scope
  사후 검사, 보고만) · `_shared/reentry-check.sh`(재진입 status↔log 정합). 디스패처 자동 배선(역할 불일치 거부,
  none/tasks-only는 cwd=루트, scope 위반은 폴백 없는 최종 실패). native/mcp 호출은 호출 전 gate.sh 실행(지침
  Lifecycle 6). INV14 신설.

### Changed
- 승인 항목 스키마: 외부 쓰기 승인은 `target_repo`·`write_scope`를 brief와 같은 값으로 기록(approval-policy).

## [0.5.0] - 2026-07-24

### Added
- **불변식 자가점검 러너 `_shared/check-invariants.sh`** — exit-code 판정(false PASS 방지),
  system-invariants.md 수동 스크립트 블록 대체. INV12(gemini 폴백 비활성) 신설.
- **디스패처 payload 동봉** — `call_worker.sh <role> <brief> [payload]` + `--merged-preview`.
  gemini 소스 검토 자료를 brief 인라인 대신 `sources/gemini-packet.md`로 동봉. design-basis D9.

### Fixed
- **gemini api 폴백 비활성** — 미구현 스텁(`gemini_api.sh`, 무조건 exit 4)이 `backends.json`
  fallbacks에 등록돼 "폴백 있음"이라는 거짓 안전신호를 내던 문제. fallbacks에서 제거하고
  routing.md·design-basis D4 문구 동기화(Gemini REST 구현 후 재등록).
- backends.json에서 디스패처가 읽지 않는 선언(`write_policy`·`non_interactive`) 제거.

## [0.4.0] - 2026-07-13

### Added
- **라우팅 2층 분리 — `_shared/capability-profile.md` 신설(가변층)** — 능력 슬롯
  (strategist·engineer·computer-use·reviewer·multimodal) → 담당 배정의 정본.
  신모델 출시·판정 변경 시 프로필만 갱신(근거·날짜 필수, 이력 append-only) — routing.md의
  슬롯 정의는 불변. 근거: design-basis D8 (2026-07-13 외부 리뷰 10건 종합 판정).
- **computer-use 슬롯 신설** — 브라우저 조작·도구 워크플로우 자동화를 독립 라우팅
  (현 배정: Orchestrator 직접).

### Changed
- routing.md decision tree를 슬롯 기반으로 재편 — engineer·computer-use는 Orchestrator
  직접(크고 분리 가능하면 codex-main), strategist 산출물(설계·디자인·전략·문체)은
  claude-critic 품질 게이트 권장.
- validate에 C5b(2층 라우팅: routing→profile 참조 + 슬롯 5종) 추가, C1에 프로필 포함.

## [0.3.2] - 2026-07-04

### Fixed
- **gemini 워커 폴백 실패 사유 유실** — 디스패처(`call_worker.sh`)가 api 폴백의 필수 env
  (`GEMINI_API_KEY`) 부재 시 실패 사유 없이 죽던 문제를 에러 envelope 반환으로 수정,
  호출 시작 시 폴백 불가 사전 경고 추가.

### Changed
- routing.md gemini — 소스·다중파일 검토 인라인 필수(agy 헤드리스 300s 타임아웃 실측),
  폴백 조건(`GEMINI_API_KEY`) 명문화, 시간 제한 작업 전 경량 스모크 권장.

## [0.3.1] - 2026-07-03

### Fixed
- **gemini(agy) 워커 프롬프트 미전달 수정** — Antigravity CLI 1.0.16에서 `-p` 단축 플래그가
  제거되어 backends.json의 `args_template: ["-p", …]`가 프롬프트를 조용히 무시(모델 미호출·사용량 0).
  `["--prompt", …]`로 교정. 증상: gemini 워커가 온보딩 인사만 반환.

## [0.3.0] - 2026-06-28

### Added
- **opt-in goal 요금가드 배선(`--with-guard`)** — 설치 시 `--with-guard`를 주면 `_shared/guard/`에
  워처(`codex_goal_watch.mjs`)와 README가 들어온다. `codex remote-control start`로 공유 데몬을 띄우고
  워처를 실행하면, `/goal` 루프가 주간 사용량 한도에 닿을 때 `app-server proxy`로 활성 goal thread를
  `thread/goal/clear`해 정지시킨다(Codex는 Stop훅으로 못 멈춰 외부 워처 필요). 기본 미설치, 런타임
  on/off=`coach guard on/off`. 정책은 `coach`(usage-coach, codexbar 의존)가 갖고 미설치·조회실패는
  fail-open. 상세=`_shared/guard/README.md`.

## [0.2.0] - 2026-06-10

카파시(Karpathy) 4원칙을 층별로 도입. 기존 규칙과 충돌 없음(보강).

### Added
- **AGENTS.md "Operating Principles" 섹션** — 4원칙 verbatim 차용 + 층별 적용 규칙(Orchestrator 전용 풀버전).
- **`_templates/worker-brief.md` "Worker 행동 규약" 고정 블록** — 워커층 번역형: ②③ 그대로, ①은 가정 명시·표면화(워커는 one-shot이라 사용자 질문 채널 없음), ④는 오케스트레이터 전용.
- **`_templates/worker-result.md` 체크리스트 항목** — "가정·불일치가 Issues/Caveats에 표면화됨".
- **design-basis D7 / system-invariants INV11** — 층별 적용 결정 명문화 + 자가점검.
- **`NOTICE`** — 출처·라이선스 표기 (multica-ai/andrej-karpathy-skills, MIT 선언·LICENSE 파일 부재).

## [0.1.0] - 2026-06-01

multi-agent-starter를 기반으로 Codex Orchestrator 버전을 생성했다.

### Added

- `AGENTS.md`: Codex 세션용 운영 규칙 정본.
- `_shared/routing.md`: `codex-main`, `claude-critic`, `gemini` 기준 worker routing.
- `_shared/approval-policy.md`: worker 승인과 외부/유료 모델 승인 게이트.
- `_shared/orchestrator-rules.md`: Codex 세션 환경 점검, 시스템 수정·검증, 작업 재진입 프로토콜.
- `_shared/design-basis.md`: Codex fork의 결정 기록.
- `_shared/system-invariants.md`: Codex 버전 자가 점검 스크립트.
- `_templates/*`: Codex worker pool 기준 task/context/log/brief/result/task-folder 템플릿.

### Changed

- Orchestrator를 Claude Code 세션에서 Codex 세션으로 변경.
- 리뷰 worker를 Codex 자기검수 구조에서 `claude-critic` 독립 검수 구조로 변경.

### Excluded

- 원본 `.claude/agents/`
- 원본 `_local/learnings.md`
- 원본의 기존 작업 이력 산출물
