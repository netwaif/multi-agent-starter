# Changelog

이 파일은 multi-agent-starter (Antigravity flavor) orchestration 시스템의 주요 변경을 기록한다.

## [0.3.0] - 2026-06-09

자유 프로바이더 교체 + 가드. 기존 역할 동작 불변(behavior-0).

### Added
- grok provider + hermes/openclaw 브리지 스텁(미승격 fail-closed); 모든 provider `family`; `roles[r].class` + `orchestrator_family`; **C10 family-disjoint**(reviewer resolved family ≠ orchestrator/main, validate+dispatcher die9); staffing best-of-n(`--best-of-n N` 주입); cli allowlist +grok(C9c 동기화). (design-basis D8 / system-invariants INV12. CT 역할 restructure는 council 비준 대기.)

## [0.2.0] - 2026-06-09

backends.json 2-테이블 스키마(provider/role 분리). 동작 변경 없음.

### Changed
- **backends.json `schema_version` 1 → 2**: `workers` 맵 → `providers` + `roles`(provider 바인딩 + `staffing` + `desk`). 디스패처는 `roles→providers` 해석. 역할별 프로바이더 교체 = `roles` 한 줄. 폐기 `workers` 맵 금지. (design-basis D7 / system-invariants INV11)

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
