# Worker Routing Rules

## Decision Tree

```
작업 성격 파악
│
├── 메인 코딩 / 디버깅 / 기획 · 설계 · 요구사항 · 전략 · 문서화?
│   └── claude-main
│
├── claude-main 산출물 리뷰 / 비판적 검증?
│   └── codex-critic   (Codex의 주된 역할)
│
├── 보조 구현 / 코드 분석 / 테스트 / 이미지 생성?
│   └── codex-main
│
├── 이미지 · 스크린샷 분석 / 50페이지+ 문서 / 제3자 시각의 검토?
│   └── gemini
│
└── 판단 어려움?
    └── claude-main으로 시작 후 필요 시 추가
```

## 복합 작업 우선순위

한 작업이 여러 분기에 해당할 때:

1. **선행 의존성 우선**: codex-critic은 리뷰 대상(보통 claude-main 결과)이 먼저 있어야 함 → 해당 산출물 뒤에 호출
2. **Orchestrator 내부 추론 우선**: 별도 worker 호출 전에 orchestrator 자체 추론으로 해결 가능한지 먼저 판단. 그래도 부족할 때만 claude-main 호출 (claude-main도 비용·쿼터 대상)
3. **검증은 한 번만**: codex-critic은 작업당 1회 원칙. 재호출은 검증 실패 시만
4. **gemini는 명시적 트리거 시만**: 멀티모달 또는 "제3자 시각의 검토 필요" 명시 없으면 호출 금지

## 병렬 / 순차 정책

| 패턴 | 적용 |
|------|------|
| 순차 (Pipeline) | 기본. claude-main → codex-critic → claude-main 처럼 결과 인계 |
| 병렬 (Parallel) | 서로 독립된 산출물일 때만. 예: claude-main(코드) + gemini(이미지 분석) |
| 금지 | 같은 입력에 같은 종류 worker 동시 호출 (예: claude-main 2개) |

병렬 호출 시: 각 worker `brief.md`에 다른 worker 결과를 참조하지 않음을 명시.

## Worker 역할 상세

### claude-main
- **용도**: 메인 코딩, 디버깅, 기획, 요구사항 정의, 설계 문서, 사용자 스토리, 아키텍처, 전략 수립
- **결과물**: 코드 (구현·수정·diff), 설계 문서, 구조도, 의사결정 근거
- **호출 명령**: Claude Code 내장 **Task tool (sub-agent)**
  - `subagent_type`: `claude-main` (`.claude/agents/claude-main.md`에 정의)
  - `prompt`: brief.md 내용 그대로 전달
  - `model`: agent 정의 파일 frontmatter의 `model: opus`가 자동 적용 (claude-opus-4-8)
  - `description`: 짧은 작업명 (3~5 단어)
- **권한**: 메인 Claude Code 세션의 권한 모드 상속. `--dangerously-skip-permissions` (yolo) 모드면 sub-agent도 yolo로 작동. 단 MultiAgent 시스템 게이트(`workers_approved`, 외부 쓰기 4조건)는 별개로 유지된다
- **비용**: 있음 (Opus 4.8 sub-agent 호출. 별도 모델 호출이며 비용·쿼터 대상) → 승인 필요
- **파일 쓰기**: ❌ 직접 X. Task tool이 반환한 텍스트를 Orchestrator가 받아 `result.md`에 기록
- ※ Orchestrator의 내부 추론과 다름.

### codex-main
- **용도**: 보조 구현 (claude-main 산출물 기반), 코드베이스 분석, 리팩토링, 테스트 작성, diff 생성, 로컬 CLI 검증, 이미지 생성 (Codex 내장 `image_gen` 도구)
- **결과물**: 코드, diff, 테스트 결과, CLI 출력, PNG/SVG 이미지
- **호출 명령**: `mcp__codex__codex` MCP 도구
  - `prompt`: brief.md 내용 그대로 전달
  - `cwd`:
    - 기본: `~/VSCodeWorkspace/MultiAgent/tasks/<task>/` — 이 안에서 산출물·diff 직접 작성
    - 외부 쓰기 4조건 충족 시: brief.md의 `target_repo` 값으로 변경
  - `sandbox`: `workspace-write` 고정 (cwd 내부만 쓰기 가능. cwd 밖은 sandbox가 차단)
  - `approval-policy`: `on-failure` 권장
- **brief 필수 필드** (오케스트레이터가 사용자에게 target_repo를 먼저 묻고 답을 받아 채운다 — 분석·리뷰·요약 작업은 예외):
  ```yaml
  target_repo: /absolute/path/to/repo                   # 작업 대상 절대 경로 (없으면 N/A)
  write_scope: none | tasks-only | "src/**, tests/**"   # none=쓰기금지 / tasks-only=tasks/<task>/ 내부만(codex-main 기본) / 패턴=외부 repo 해당 경로(외부는 4조건)
  ```
- **비용**: 있음 (Codex 호출 쿼터) → 승인 필요
- **파일 쓰기**:
  - 기본: cwd=`tasks/<task>/` + sandbox=`workspace-write` → 작업 폴더 내부 산출물·diff 직접 작성 가능 (외부 repo는 sandbox가 막음)
  - 외부 repo 쓰기 4조건 (CLAUDE.md "Worker 파일 쓰기 정책" 참조) 모두 충족 시에만 cwd를 `target_repo`로 변경하여 해당 scope 내 직접 쓰기 허용
  - 어느 경우에도 `_shared/`, `_templates/`, 다른 작업 폴더는 쓰지 말 것

### codex-critic
- **용도**: 리뷰 대상 산출물(주로 claude-main 코드·설계, 또는 brief에 명시된 기존 코드·문서·소스)을 실제 repo/파일/CLI 관점에서 리뷰·비평. 실현 가능성, 비용, 테스트 커버리지, 사이드 이펙트 검토. **Codex의 주된 역할.**
- **선행 조건**: 리뷰 대상 산출물 경로가 존재 — 보통 claude-main `result.md`, 또는 brief에 명시된 기존 코드·문서·소스
- **결과물**: 비평 리스트, 수정 제안
- **호출 명령**: codex-main과 동일 (`mcp__codex__codex` MCP). 단 다음 강제:
  - `sandbox`: `read-only` 고정 (쓰기 금지)
  - brief에 "비평 모드" 명시
  - brief의 `target_repo` 명시 (비평 대상 repo 컨텍스트), `write_scope: none`
- **비용**: 있음 → 승인 필요
- **파일 쓰기**: ❌ 직접 X. Orchestrator 경유

### gemini
- **용도**: 이미지/스크린샷/다이어그램 분석, 50페이지+ 문서 스캔, 제3자 시각의 검토
- **결과물**: 분석 텍스트, 요약
- **호출 명령** (예시 — MCP, 단일 브리지 `mcp__gemini-pro__*` 하나. 속도/정밀은 `model` 파라미터로):
  ```
  mcp__gemini-pro__gemini_pro_prompt   # 일반 텍스트
  mcp__gemini-pro__gemini_pro_vision   # 이미지/스크린샷
  # model: gemini-3-flash(빠름) | gemini-3.1-pro-low(기본·정밀). pro-high 제외(D4)
  ```
- **비용**: 모델별 — gemini-3-flash 낮음 / pro-low 중간 → 승인 필요
- **파일 쓰기**: ❌ MCP 응답을 Orchestrator가 받아 기록

## 모델 정책

각 worker가 실제 어떤 모델로 도는지 정리. 사용자가 매번 명시할 필요는 없으며, 아래 기본이 자동 적용된다.

- **claude-main**: `claude-opus-4-8` (기본). Task tool sub-agent로 호출하며 `.claude/agents/claude-main.md` frontmatter의 `model: opus`가 자동 적용된다.
- **codex-main / codex-critic**: 사용자의 `~/.codex/config.toml` 기본값이 자동 적용된다 (예: `gpt-5.5` + reasoning effort `high`). MCP 호출 시 `model` 파라미터를 비워두면 그대로 사용된다.
  - 가벼운 작업은 `profile: lightweight`로 전환 가능 (예: `gpt-5.4-mini`)
  - 작업 성격상 다른 모델이 필요하면 brief.md에 명시
- **gemini**: 단일 브리지 `mcp__gemini-pro__*` 하나만 사용 (CLI 래퍼 `mcp__gemini__*`는 폐기 — 잔존 참조 시 호출 실패). 기본 모델 `gemini-3.1-pro-low`, 빠른 응답은 같은 브리지에서 `model: gemini-3-flash`. `gemini-3.1-pro-high`는 로컬 프록시에서 `400 INVALID_ARGUMENT`가 재현되어 **기본·폴백 경로에서 제외**(사용자 명시 요청 시만). 근거: `_shared/learnings.md` [2026-05-15] · `design-basis.md` D4.

이 정책은 사용자별 config에 따라 달라질 수 있다 — starter clone 받은 학습자는 본인의 `~/.codex/config.toml` 기본값을 한 번 확인하고 자기 환경에 맞게 조정한다.

## 최소 Worker Set 원칙

| 작업 유형 | 권장 최소 set |
|----------|------------|
| 문서/기획만 | claude-main |
| 코드 구현 | claude-main |
| 설계 후 구현 | claude-main (설계·구현 일괄) |
| 구현 + 비평 | claude-main → codex-critic → claude-main (반영) |
| 보조 구현 / 이미지 생성 | codex-main |
| 대용량 문서 처리 | gemini |
| 전체 검토 | claude-main → codex-critic |

모든 worker를 기본 호출하지 말 것. 필요한 worker만 선택.

## Worker 추가 조건

- 이미 있는 worker 결과로 해결 가능하면 추가 호출 금지
- 이전 결과가 검증 미통과 시에만 동일 worker 재호출 가능
- gemini는 "제3자 시각의 검토"가 명시적으로 필요할 때만
