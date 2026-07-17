# Changelog

이 파일은 multi-agent-starter (grok flavor) orchestration 시스템의 주요 변경을 기록한다.

## [0.1.0] - 2026-07-18

multi-agent-starter를 기반으로 grok(xAI, grok-4.5) Orchestrator 버전을 생성했다(Phase 2).

### Added

- `GROK.md`: grok CLI 세션용 운영 규칙 정본. 오케스트레이터의 네이티브 `web_search`+`x_search`를
  이용한 실시간 web/X-SNS 인텔 처리 규율(출처 인용·신뢰불가 데이터 취급·스냅샷 원칙) 포함.
- `_shared/routing.md`: `claude-main`, `codex-main`, `codex-critic`, `gemini` 기준 worker routing.
  5개 능력 슬롯(strategist·engineer·computer-use·reviewer·multimodal) + realtime-web(오케스트레이터 직접).
- `_shared/backends.json`: claude-main/codex-main/codex-critic/gemini 4-worker 레지스트리.
  grok-critic/grok-intel 워커 없음(동일벤더 자기검수 회피).
- `_shared/capability-profile.md`: 슬롯 → 담당 배정 정본(가변층).
- `_shared/approval-policy.md`: worker 승인과 외부/유료 모델 승인 게이트(4-worker pool).
- `_shared/orchestrator-rules.md`: grok CLI 세션 환경 점검, 시스템 수정·검증, 작업 재진입 프로토콜.
- `_shared/design-basis.md`: grok flavor의 결정 기록(D1~D9).
- `_shared/system-invariants.md`: grok 버전 자가 점검 스크립트.
- `_shared/runtime/` (15 모듈) · `_shared/adapters/`: `claude` flavor에서 verbatim 이식(flavor-agnostic).
- `_templates/*`: grok worker pool 기준 task/context/log/brief/result/task-folder 템플릿.

### Changed

- Orchestrator를 Claude Code/Antigravity 세션에서 grok CLI 세션으로 변경.
- 리뷰 worker는 기존 flavor들과 동일하게 `codex-critic`(교차벤더 독립 검수) 유지.
- 멀티모달은 antigravity flavor(오케스트레이터 직접)와 달리 **워커(`gemini`)**로 유지 —
  오케스트레이터가 grok이지 Gemini가 아니므로 배제 대상이 아니다.

### Excluded

- `grok-critic`/`grok-intel` 워커 (오케스트레이터 자체가 grok — 동일벤더 자기검수 회피).
- 원본 `.claude/agents/`
- 원본 `_local/learnings.md`
- 원본의 기존 작업 이력 산출물
