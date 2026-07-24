# Worker Routing Rules

## 2층 라우팅 — 안정층/가변층

이 파일의 decision tree는 **작업 유형 → 능력 슬롯**을 정한다(안정층 — 모델 세대가 바뀌어도 유효).
**슬롯 → 담당 워커 배정**의 정본은 `_shared/capability-profile.md`(가변층)다.
신모델 출시·판정 변경 시 **프로필만 갱신**한다 — 이 파일의 슬롯 정의는 손대지 않는다.
아래 트리의 워커명은 현 프로필 배정의 병기(편의 사본)다 — 프로필과 어긋나면 **프로필이 이긴다**.

## Decision Tree

```
작업 성격 파악 → 능력 슬롯 → 담당 워커 (배정 정본: capability-profile.md)
│
├── [strategist] 기획 · 설계 · 아키텍처 · 요구사항 · 전략 · UI/UX 디자인 방향
│   · 문체가 중요한 글쓰기 · 까다로운 로직 설계 · 디버깅 원인 분석?
│   └── claude-main
│
├── [engineer] 대규모 구현 · 리팩토링 · 테스트 작성·실행 · diff · 로컬 CLI 검증 · 이미지 생성?
│   └── codex-main
│
├── [computer-use] 브라우저 조작 · 복잡한 도구 워크플로우 자동화?
│   └── codex-main
│
├── [reviewer] 산출물 리뷰 / 비판적 검증?
│   └── codex-critic   (Codex의 주된 역할)
│
├── [multimodal] 이미지 · 스크린샷 분석 / 50페이지+ 문서 / 제3자 시각의 검토?
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

## 토폴로지 패턴 (worker를 어떻게 엮을까)

decision tree로 "누구를" 고른 뒤, "어떻게 엮을지" 고른다. **단일 orchestrator 구조에 맞는 4패턴만** 쓴다.

| 패턴 | 언제 | 이 시스템에서 |
|------|------|-------------|
| Pipeline (순차) | 앞 결과가 뒤 입력 | 기본. claude-main → codex-critic → claude-main(반영) |
| Fan-out/Fan-in (병렬→통합) | 서로 독립된 산출물 여럿을 하나로 통합 | 예: claude-main(코드) ∥ gemini(이미지). 각 brief에 "타 worker 결과 미참조" 명시. 통합은 아래 Fan-in 규칙 |
| Expert Pool (전문가 선택) | 작업 성격에 맞는 worker만 | 새 실행 패턴이 아니라 **worker 선택 정책** — 위 decision tree + 최소 worker set이 곧 이 패턴 |
| Producer-Reviewer (생성+게이트) | 산출물 품질 검증 필요 | claude-main(생성) → codex-critic(adversarial 게이트) |

**금지**: 같은 입력에 같은 종류 worker 동시 호출 (예: claude-main 2개).
**배제**: Supervisor(별도 long-lived 조정자 worker/런타임 동적분배 계층 추가)·Hierarchical Delegation(worker가 worker를 부르는 재귀 위임)은 단일 orchestrator·worker간 무통신·file-as-memory와 충돌 → 미사용. 근거: design-basis D6.

### Fan-in 규칙 (병렬 결과 통합)

병렬 worker 결과를 orchestrator가 하나로 합칠 때:
1. 각 worker 원문을 `result.md`에 그대로 보존 (요약본만 남기지 말 것 — telephone game 방지)
2. 결과가 충돌하면 삭제 금지 → 양쪽 출처 병기, 권위 우선순위/사실검증으로 해소, `log.md` [DECISION]에 근거 기록
3. 통합 결론 한 줄을 `context.md`에 기록

## Worker 역할 상세

### claude-main
- **슬롯**: strategist
- **용도**: 기획, 요구사항 정의, 설계 문서, 사용자 스토리, 아키텍처, 전략 수립, UI/UX 디자인 방향, 문체가 중요한 글쓰기, 까다로운 로직 설계, 디버깅 원인 분석, (설계와 분리 곤란한) 핵심 구현
- **결과물**: 코드 (구현·수정·diff), 설계 문서, 구조도, 의사결정 근거
- **호출 명령**: Claude Code 내장 **Task tool (sub-agent)**
  - `subagent_type`: `claude-main` (`.claude/agents/claude-main.md`에 정의)
  - `prompt`: brief.md 내용 그대로 전달
  - `model`: agent 정의 파일 frontmatter의 `model: opus`가 자동 적용 (별칭 — 현재 환경의 Opus로 해석. 버전 문자열 핀하지 않음. 모델 정책 참조)
  - `description`: 짧은 작업명 (3~5 단어)
- **권한**: 메인 Claude Code 세션의 권한 모드 상속. `--dangerously-skip-permissions` (yolo) 모드면 sub-agent도 yolo로 작동. 단 MultiAgent 시스템 게이트(`workers_approved`, 외부 쓰기 4조건)는 별개로 유지된다
- **비용**: 있음 (Opus(`opus` 별칭) sub-agent 호출. 별도 모델 호출이며 비용·쿼터 대상) → 승인 필요
- **파일 쓰기**: ❌ 직접 X. Task tool이 반환한 텍스트를 Orchestrator가 받아 `result.md`에 기록
- ※ Orchestrator의 내부 추론과 다름.

### codex-main
- **슬롯**: engineer · computer-use
- **용도**: 대규모 구현·리팩토링 (claude-main 설계 기반 또는 단독), 코드베이스 분석, 테스트 작성·실행, diff 생성, 로컬 CLI 검증, 브라우저 조작·도구 워크플로우 자동화, 이미지 생성 (Codex 내장 `image_gen` 도구)
- **결과물**: 코드, diff, 테스트 결과, CLI 출력, PNG/SVG 이미지
- **호출 명령**: `mcp__codex__codex` MCP 도구
  - `prompt`: brief.md 내용 그대로 전달
  - `cwd`:
    - 기본: `~/VSCodeWorkspace/MultiAgent/tasks/<task>/` — 이 안에서 산출물·diff 직접 작성
    - 외부 쓰기 4조건 충족 시: brief.md의 `target_repo` 값으로 변경
  - `sandbox`: `workspace-write` 고정 (cwd 내부만 쓰기 가능. cwd 밖은 sandbox가 차단)
  - `approval-policy`: 헤드리스 호출은 `never`(backends.json 정본 — 승인 프롬프트를 받을 수 없는 환경에서 결정적 거부, fail-closed). 대화형 수동 호출 시에만 `on-failure` 선택 가능
- **MCP 실패 시 폴백 (정본 절차, 2026-07-10 실측)**: MCP 서버 stale(모델 버전 에러 등)이면 backends.json의 CLI 폴백과 동일 인자로 헤드리스 실행 — `codex exec --sandbox workspace-write "$(cat brief.md)"`, cwd=`tasks/<task>/`. 출력은 파일로 리다이렉트(`> raw-output.txt`) 후 결론부만 읽기. codex-critic 폴백은 `--sandbox read-only` 강제
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
- **슬롯**: reviewer
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
- **슬롯**: multimodal
- **용도**: 이미지/스크린샷/다이어그램 분석, 50페이지+ 문서 스캔, 제3자 시각의 검토
- **결과물**: 분석 텍스트, 요약
- **호출 명령**: `_shared/backends.json`의 `gemini` 항목이 정본. 디스패처로 호출:
  ```
  bash _shared/adapters/call_worker.sh gemini <brief-file>   # 결과 = JSON envelope
  ```
  백엔드 = Antigravity `agy` CLI(헤드리스), 기본 `gemini-3.1-pro-high`, 폴백 없음(아래 폴백 조건). 폐기: `mcp__gemini-pro__*`·`mcp__gemini__*` 프록시 브리지.
- **이미지/PDF 검수 (단일 정본 경로, 필독)**: brief.md **본문에 분석 대상의 절대경로를 직접 적고** `call_worker.sh gemini <brief>`로 호출한다. 디스패처가 본문 전체를 프롬프트로 싣고(`args_template: --prompt @brief_content` — agy 1.0.16에서 `-p` 제거, 2026-07-03 교정·실측) `</dev/null`을 보장(`stdin: /dev/null`)하므로 agy가 본문 경로의 파일을 연다. **agy를 손으로 부르거나 `--add-dir`·`--dangerously-skip-permissions`를 쓰지 말 것** — 각각 stdin hang(타임아웃)·auto-mode classifier 차단의 원인이며, 이를 "비전 구조적 불가"로 오진한 사례가 있다(2026-06-28). 실측: 본문 절대경로 brief → exit 0(~26s), 픽셀크기·텍스트·검증코드 정확 반향.
- **소스·다중파일 검토는 인라인 필수 (2026-07-04 실측, dayjs-bughunt)**: 소스 코드 발굴·검토를 시킬 땐 **디렉토리나 다수 파일 순회를 시키지 말 것** — agy 헤드리스가 300s 타임아웃(exit 124)으로 전멸한다. 필요한 스니펫을 orchestrator가 brief 본문에 **인라인**하고 "파일 열지 말 것"을 명시하라(동일 과제 인라인 재호출 실측 = 27s exit 0). 단일 이미지/PDF 경로 참조(위 항목)는 예외(~26s 정상). 시간 제한 작업에서 gemini에 의존하기 전 경량 스모크 1회로 가용성부터 확인.
- **폴백 조건**: api 폴백 슬롯(`adapters/gemini_api.sh`)은 **미구현·비활성**(spike S3 미완 — 키가 있어도 무조건 exit 4). backends.json `fallbacks`에서 제거됨(거짓 안전신호 방지, 2026-07-24 D11). agy(primary) 실패 시 폴백 없이 실패한다(사유는 envelope `stderr_sanitized`). Gemini REST 호출 구현 후에만 fallbacks 재등록.
- **비용**: agy 쿼터 소모 → 승인 필요. 빠른 경로는 backends에서 `model`을 flash/pro-low로.
- **파일 쓰기**: ❌ MCP 응답을 Orchestrator가 받아 기록

## 모델 정책

각 worker가 실제 어떤 모델로 도는지 정리. 사용자가 매번 명시할 필요는 없으며, 아래 기본이 자동 적용된다.

- **claude-main**: 별칭 **`opus`** (`.claude/agents/claude-main.md` frontmatter `model: opus`). 버전 문자열을 핀하지 않는다 — 별칭이 현재 환경의 최신 Opus로 자동 해석되므로 모델이 올라가도 갱신 불필요.
  - **추론 강도(effort)**: claude-main 정의엔 `effort` 필드가 **없음 → 세션 `/effort` 값을 상속**한다(현재 세션이 high면 high로 동작). 세션과 무관하게 고정하려면 frontmatter에 `effort: high` 등을 명시(상속 끔). 고정은 결정성↑이나 현재는 상속 유지가 기본.
- **codex-main / codex-critic**: 사용자의 `~/.codex/config.toml` 기본값이 자동 적용된다 (현재 예: 최신 gpt + reasoning effort `high`). config.toml이 정본이라 여기에 버전을 핀하지 않는다. MCP 호출 시 `model` 파라미터를 비워두면 config 기본값 사용.
  - 가벼운 작업은 `profile: lightweight`로 전환 가능 (config.toml의 가벼운 모델 프로필)
  - 작업 성격상 다른 모델이 필요하면 brief.md에 명시
- **gemini**: 백엔드 = Antigravity **`agy` CLI**(`_shared/backends.json` 정본, 디스패처 `call_worker.sh`). 기본 `gemini-3.1-pro-high`(agy에선 정상 — 옛 프록시 `400 INVALID_ARGUMENT`은 비해당), 빠른 경로 `gemini-3-flash`/`pro-low`, 폴백 없음(api 슬롯 미구현·비활성, D11). 옛 `mcp__gemini-pro__*` 프록시 브리지·CLI 래퍼 `mcp__gemini__*`는 **폐기**. agy 모델은 전역·계정단위(`/model`)라 per-call 핀 불가 → gemini 전용 전역을 pro-high로 둔다. 근거: `_shared/learnings.md` [2026-06-02] · `design-basis.md` D4.

이 정책은 사용자별 config에 따라 달라질 수 있다 — starter clone 받은 학습자는 본인의 `~/.codex/config.toml` 기본값을 한 번 확인하고 자기 환경에 맞게 조정한다.

## 최소 Worker Set 원칙

| 작업 유형 | 권장 최소 set |
|----------|------------|
| 문서/기획/전략만 | claude-main |
| 설계 + 소규모 구현 | claude-main (설계·구현 일괄) |
| 대규모 구현·테스트 | claude-main (설계) → codex-main (구현·테스트) |
| 브라우저 자동화 / 이미지 생성 | codex-main |
| 구현 + 비평 | 생성 워커 → codex-critic → 반영 |
| 대용량 문서 처리 | gemini |
| 전체 검토 | claude-main → codex-critic |

모든 worker를 기본 호출하지 말 것. 필요한 worker만 선택.

## Worker 추가 조건

- 이미 있는 worker 결과로 해결 가능하면 추가 호출 금지
- 이전 결과가 검증 미통과 시에만 동일 worker 재호출 가능
- gemini는 "제3자 시각의 검토"가 명시적으로 필요할 때만
