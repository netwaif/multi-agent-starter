# Changelog

이 파일은 multi-agent-starter (Antigravity flavor) orchestration 시스템의 주요 변경을 기록한다.

## [0.3.1] - 2026-07-24

### Added
- **불변식 자가점검 러너 `_shared/check-invariants.sh`** — exit-code 판정(false PASS 방지),
  system-invariants.md 수동 스크립트 블록 대체.
- **디스패처 payload 동봉** — `call_worker.sh <role> <brief> [payload]` + `--merged-preview`
  (대용량 자료는 `sources/` packet으로 동봉, brief 불변식 유지). design-basis D9.

### Fixed
- backends.json에서 디스패처가 읽지 않는 선언(`write_policy`·`non_interactive`) 제거
  (희망사항 config = 거짓 안전신호 방지).

## [0.3.0] - 2026-07-13

### Added
- **라우팅 2층 분리 — `_shared/capability-profile.md` 신설(가변층)** — 능력 슬롯
  (strategist·engineer·computer-use·reviewer·multimodal) → 담당 배정의 정본.
  신모델 출시·판정 변경 시 프로필만 갱신(근거·날짜 필수, 이력 append-only) — routing.md의
  슬롯 정의는 불변. 근거: design-basis D8 (2026-07-13 외부 리뷰 10건 종합 판정).
- **computer-use 슬롯 신설** — 브라우저 조작·도구 워크플로우 자동화를 독립 라우팅
  (현 배정: codex-main).

### Changed
- routing.md decision tree를 슬롯 기반으로 재편 — strategist(기획·설계·디자인·전략·문체)
  = claude-main, engineer(대규모 구현·테스트) = codex-main, multimodal = Orchestrator 직접.
- validate에 C5b(2층 라우팅: routing→profile 참조 + 슬롯 5종) 추가, C1에 프로필 포함.

## [0.2.2] - 2026-07-04

### Fixed
- **gemini 워커 폴백 실패 사유 유실** — 디스패처(`call_worker.sh`)가 api 폴백의 필수 env
  (`GEMINI_API_KEY`) 부재 시 실패 사유 없이 죽던 문제를 에러 envelope 반환으로 수정,
  호출 시작 시 폴백 불가 사전 경고 추가.

## [0.2.1] - 2026-07-03

### Fixed
- **gemini(agy) 워커 프롬프트 미전달 수정** — Antigravity CLI 1.0.16에서 `-p` 단축 플래그가
  제거되어 backends.json의 `args_template: ["-p", …]`가 프롬프트를 조용히 무시(모델 미호출·사용량 0).
  `["--prompt", …]`로 교정. 증상: gemini 워커가 온보딩 인사만 반환.

## [0.2.0] - 2026-06-10

카파시(Karpathy) 4원칙을 층별로 도입. 기존 규칙과 충돌 없음(보강).

### Added
- **AGENTS.md "Operating Principles" 섹션** — 4원칙 verbatim 차용 + 층별 적용 규칙(Orchestrator 전용 풀버전).
- **`_templates/worker-brief.md` "Worker 행동 규약" 고정 블록** — 워커층 번역형: ②③ 그대로, ①은 가정 명시·표면화(워커는 one-shot이라 사용자 질문 채널 없음), ④는 오케스트레이터 전용.
- **`_templates/worker-result.md` 체크리스트 항목** — "가정·불일치가 Issues/Caveats에 표면화됨".
- **design-basis D7 / system-invariants INV11** — 층별 적용 결정 명문화 + 자가점검.
- **`NOTICE`** — 출처·라이선스 표기 (multica-ai/andrej-karpathy-skills, MIT 선언·LICENSE 파일 부재).

## [0.1.0] - 2026-06-01

multi-agent-starter를 기반으로 Antigravity Orchestrator 버전을 생성했다.

### Added

- `AGENTS.md`: Antigravity 세션용 운영 규칙 정본.
- `_shared/routing.md`: `claude-main`, `codex-main`, `codex-critic` 기준 worker routing.
- `_shared/approval-policy.md`: worker 승인과 외부/유료 모델 승인 게이트.
- `_shared/orchestrator-rules.md`: Antigravity 세션 환경 점검, 시스템 수정·검증, 작업 재진입 프로토콜.
- `_shared/design-basis.md`: Antigravity flavor의 결정 기록.
- `_shared/system-invariants.md`: Antigravity 버전 자가 점검 스크립트.
- `_templates/*`: Antigravity worker pool 기준 task/context/log/brief/result/task-folder 템플릿.

### Changed

- Orchestrator를 Claude Code 세션에서 Antigravity 세션으로 변경.
- 리뷰 worker를 Gemini(오케스트레이터) 자기검수 구조에서 `codex-critic` 독립 검수 구조로 변경.

### Excluded

- 원본 `.claude/agents/`
- 원본 `_local/learnings.md`
- 원본의 기존 작업 이력 산출물
