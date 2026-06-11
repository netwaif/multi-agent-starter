# Changelog

이 파일은 MultiAgent orchestration 시스템의 주요 변경을 기록한다.
형식은 [Keep a Changelog](https://keepachangelog.com/), 버전은 [Semantic Versioning](https://semver.org/lang/ko/)을 따른다.

## [1.2.0] - 2026-06-09

자유 프로바이더 교체 + 가드(grok·bridge·family·staffing·C10). 기존 역할 동작 불변(behavior-0).

### Added
- **grok provider**(cli, family xai, `best_of_n`) + **hermes/openclaw 브리지 스텁**(call_type `bridge`, 미승격 fail-closed)을 providers 카탈로그에. 역할은 `roles[r].provider` 한 줄로 카탈로그의 어느 provider로든 교체(free provider swapping).
- 모든 provider에 **`family`** 필드; `roles[r]`에 **`class`**(main/aux/reviewer/scout/tool) + backends top-level **`orchestrator_family`**.
- **C10 family-disjoint 가드(하중벽)**: reviewer 역할 resolved family ≠ orchestrator/모든 main family — `validate.py` + 디스패처(`call_worker.sh`) 양쪽 fail-closed(die 9).
- **staffing 분신**: `roles[r].staffing.mode=auto`면 provider-native best-of-n(`--best-of-n N`) 주입(1 dispatcher 호출 내부 N→1 envelope). 기본 fixed N=1.
- cli allowlist에 grok 추가(call_worker case ≡ validate `_CLI_ALLOWLIST`, C9c 동기화 단언). bridge dispatch die(exit 3).

### Verification
- `tests/run.sh` GREEN + 적대검증 Workflow(5축): C10 dispatch 다중-main 비대칭 gap 발견·수정(전체 main family 대조). design-basis D9 / system-invariants INV13.

### Note
- CT 역할 restructure(기능slug rename·신규역할·Hermes 활성 바인딩)는 governance라 별도 4-surface council 비준 대기. role의 class를 reviewer 아닌 값으로 바꾸면 C10 면제 = 의도된 동작(class=보안존).

## [1.1.0] - 2026-06-09

backends.json 2-테이블 스키마(provider/role 분리). 동작 변경 없음(기본 바인딩 = 이전과 동일).

### Changed
- **backends.json `schema_version` 1 → 2**: 단일 `workers` 맵을 `providers`(백엔드 레코드 카탈로그) + `roles`(role→provider 바인딩 + `staffing` + `desk`)로 분리. 디스패처 `call_worker.sh`는 `roles[role].provider → providers[provider]`로 해석. **역할의 담당 프로바이더 교체 = `roles` 한 줄 수정**(레코드·코드 불변). 폐기 `workers` 맵 금지.

### Verification
- `tests/run.sh` 전 항목 PASS(3 flavor 생성·디스패처). validate C9 2-테이블 자동 강제 + negative probe 7종 fail-closed. design-basis D8 / system-invariants INV12 동반.

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
