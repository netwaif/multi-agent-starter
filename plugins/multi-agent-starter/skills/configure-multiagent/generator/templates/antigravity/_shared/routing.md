# Worker Routing Rules

## 2층 라우팅 — 안정층/가변층

이 파일의 decision tree는 **작업 유형 → 능력 슬롯**을 정한다(안정층 — 모델 세대가 바뀌어도 유효).
**슬롯 → 담당 배정**의 정본은 `_shared/capability-profile.md`(가변층)다.
신모델 출시·판정 변경 시 **프로필만 갱신**한다 — 이 파일의 슬롯 정의는 손대지 않는다.
아래 트리의 담당명은 현 프로필 배정의 병기(편의 사본)다 — 프로필과 어긋나면 **프로필이 이긴다**.

## Decision Tree

```
작업 성격 파악 → 능력 슬롯 → 담당 (배정 정본: capability-profile.md)
│
├── [multimodal] 현재 Antigravity Orchestrator(Gemini 3.1 Pro High)가 직접 처리 가능한 단일 작업?
│   └── worker 호출 없이 진행 (멀티모달·긴 문서·제3자 시각 검토는 오케스트레이터가 직접)
│
├── [strategist] 기획 · 설계 · 아키텍처 · 전략 수립 · UI/UX 디자인 방향
│   · 문체가 중요한 글쓰기 · 까다로운 로직 설계 · 디버깅 원인 분석?
│   └── claude-main
│
├── [engineer] 대규모 구현 · 코드 분석 · 테스트 작성·실행 / diff / 로컬 검증이 크고 분리 가능?
│   └── codex-main
│
├── [computer-use] 브라우저 조작 · 복잡한 도구 워크플로우 자동화?
│   └── codex-main
│
├── [reviewer] 산출물의 독립 리뷰 / 비판적 검증?
│   └── codex-critic
│
└── 판단 어려움?
    └── Orchestrator가 먼저 범위를 좁히고, 필요한 worker만 사용자 승인 후 추가
```

## 복합 작업 우선순위

1. **Orchestrator 우선**: 별도 worker 호출 전에 현재 Antigravity 세션의 추론·멀티모달·로컬 도구로 해결 가능한지 판단한다.
2. **최소 worker set**: 필요한 worker만 고른다. 모든 worker를 기본 호출하지 않는다.
3. **선행 의존성 우선**: `codex-critic`은 리뷰 대상 산출물 경로가 먼저 있어야 한다.
4. **검증은 한 번만**: `codex-critic`은 작업당 1회 원칙. 재호출은 검증 실패나 입력 변경 시만.
5. **설계와 구현의 분업**: 설계·전략·까다로운 로직은 claude-main(strategist), 대규모 구현·테스트·브라우저 자동화는 codex-main(engineer·computer-use).

## 토폴로지 패턴

| 패턴 | 언제 | 이 시스템에서 |
|------|------|---------------|
| Pipeline (순차) | 앞 결과가 뒤 입력 | claude-main -> codex-critic -> Orchestrator 반영 |
| Fan-out/Fan-in (병렬→통합) | 서로 독립된 산출물 여럿을 통합 | claude-main(설계) ∥ codex-main(테스트). 통합은 Orchestrator |
| Expert Pool (전문가 선택) | 작업 성격에 맞는 worker만 | decision tree + 최소 worker set |
| Producer-Reviewer (생성+게이트) | 산출물 품질 검증 필요 | claude-main 또는 codex-main 생성 -> codex-critic |

**금지**: 같은 입력에 같은 종류 worker 동시 호출.
**배제**: 별도 long-lived supervisor worker나 worker가 worker를 부르는 재귀 위임 계층은 쓰지 않는다. 단일 Orchestrator, worker간 무통신, file-as-memory 원칙과 충돌한다.

### Fan-in 규칙

1. 각 worker 원문을 `result.md`에 그대로 보존한다.
2. 결과가 충돌하면 삭제하지 말고 양쪽 출처를 병기한 뒤, 권위 우선순위와 사실검증으로 해소한다.
3. 통합 결론 한 줄을 `context.md`에 기록하고, 근거를 `log.md` `[DECISION]`에 남긴다.

## Worker 호출 방식

모든 worker 호출은 `_shared/backends.json`이 정본이고, 디스패처를 거친다:
```
bash _shared/adapters/call_worker.sh <role> <brief-file>   # 결과 = JSON envelope
```
Orchestrator는 envelope의 stdout을 `result.md`에 기록한다. (claude-main=`claude` CLI, codex-main/codex-critic=`codex` CLI)

## Worker 역할 상세

### claude-main

- **슬롯**: strategist
- **용도**: 기획, 설계 문서, 아키텍처, 전략 수립, UI/UX 디자인 방향, 문체가 중요한 글쓰기, 까다로운 로직 설계, 디버깅 원인 분석, (설계와 분리 곤란한) 핵심 구현.
- **결과물**: 설계·아키텍처 문서, 전략, 디버깅 분석, 핵심 코드.
- **호출 방식**: `backends.json`의 `claude-main`(백엔드 = `claude` CLI). 외부/유료 모델이므로 호출 전 승인.
- **brief 필수 필드**:

```yaml
target_repo: /absolute/path/to/repo
write_scope: none | tasks-only | "src/**, tests/**"
```

- **기본 쓰기**: `tasks/<task>/` 내부 산출물·diff.
- **외부 repo 쓰기**: `AGENTS.md`의 4조건을 모두 충족할 때만.
- **금지**: `_shared/`, `_templates/`, 다른 작업 폴더 수정.

### codex-main

- **슬롯**: engineer · computer-use
- **용도**: 대규모 구현·리팩토링 (claude-main 설계 기반 또는 단독), 코드베이스 분석, 테스트 작성·실행, diff 생성, 로컬 CLI 검증, 브라우저 조작·도구 워크플로우 자동화.
- **결과물**: 코드, diff, 테스트 결과, CLI 출력.
- **호출 방식**: `backends.json`의 `codex-main`(백엔드 = `codex exec --sandbox workspace-write -c approval_policy=never -`, brief stdin, cwd=`tasks/<task>/` — 외부 쓰기 4조건 때만 target_repo). 호출 전 승인.
- **brief 필수 필드**: 위 claude-main과 동일(`target_repo`, `write_scope`).
- **기본 쓰기**: `tasks/<task>/` 내부. 외부 repo는 4조건 충족 시만. **금지**: `_shared/`, `_templates/`, 다른 작업 폴더.

### codex-critic

- **슬롯**: reviewer
- **용도**: Antigravity Orchestrator·claude-main·codex-main 산출물의 독립 리뷰·비평. 실현 가능성, 테스트 커버리지, 사이드 이펙트, 누락 요구사항을 adversarial하게 점검한다. **Gemini 오케스트레이터와 다른 벤더(Codex)라 독립성 확보** — gemini 자기검수로 대체 금지.
- **선행 조건**: 리뷰 대상 산출물 경로가 존재해야 한다(`claude-main`/`codex-main result.md`, Orchestrator 문서, 기존 코드 등).
- **결과물**: 중요도별 비평 리스트, 수정 제안, 수락/보류 판단 근거.
- **호출 방식**: `backends.json`의 `codex-critic`(백엔드 = `codex exec --sandbox read-only -c approval_policy=never -`, cwd=`tasks/<task>/`). 호출 전 승인.
- **쓰기 권한**: 없음. Orchestrator가 응답을 `result.md`에 기록한다.
- **brief 필수 필드**: `target_repo` 또는 리뷰 대상 경로, `write_scope: none`, "비평 모드" 명시.

## 모델 정책

- **Antigravity Orchestrator**: agy/IDE의 현재 모델 = **Gemini 3.1 Pro High**(전역·계정단위 `/model`). 멀티모달·긴 문서도 오케스트레이터가 직접.
- **claude-main**: 승인된 `claude` CLI의 현재 기본/별칭 모델. 버전 문자열을 repo에 핀하지 않는다.
- **codex-main / codex-critic**: 현재 Codex 환경(`~/.codex/config.toml`) 기본값을 상속. repo에 버전 핀 금지.
- **gemini 워커 없음**: 오케스트레이터가 Gemini라 별도 gemini 워커는 두지 않는다(같은 벤더 독립성 무의미).

## 최소 Worker Set

| 작업 유형 | 권장 최소 set |
|-----------|---------------|
| 작고 명확한 구현/문서/멀티모달 | worker 없음, Orchestrator 직접 처리 |
| 기획/설계/전략 | claude-main |
| 대규모 구현/분석/테스트 | codex-main (설계 필요 시 claude-main 선행) |
| 브라우저 자동화 | codex-main |
| 구현 + 독립 비평 | claude-main(또는 codex-main) -> codex-critic |
| 전체 검토 | codex-critic |

## Worker 추가 조건

- 기존 결과로 해결 가능하면 추가 호출 금지.
- 이전 결과가 검증 미통과이거나 입력이 바뀐 경우에만 동일 worker 재호출.
- 모든 worker(claude-main·codex-main·codex-critic)는 외부/유료 모델이므로 매 호출 전 승인 경계를 분명히 한다.
