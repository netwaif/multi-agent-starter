# Task Folder Setup Guide

새 작업 시작 시 이 가이드대로 폴더와 파일을 생성한다.

## 폴더 구조

```
tasks/<task-name>/
├── task.md
├── context.md
├── log.md
├── sources/
├── workers/
│   └── <role>/          # claude-main | claude-main | codex-main | codex-critic
│       ├── brief.md
│       └── result.md
└── artifacts/
```

## 생성 절차

### Step 1: 작업 폴더 + 필수 파일

```bash
TASK=my-task-name
ROOT=<설치한-폴더>
mkdir -p "$ROOT/tasks/$TASK"
cp "$ROOT/_templates/task.md" "$ROOT/tasks/$TASK/task.md"
cp "$ROOT/_templates/log.md" "$ROOT/tasks/$TASK/log.md"
cp "$ROOT/_templates/context.md" "$ROOT/tasks/$TASK/context.md"
```

### Step 1.5: target_repo 확인

`codex-main`이 planned_workers에 포함되거나 코드·문서·이미지를 외부 repo에 만드는 작업이면, task.md 채우기 전에 사용자에게 묻는다:

> "이 작업의 산출물이 들어갈 외부 폴더(target_repo)가 있나요? 없으면 tasks/<task>/artifacts/에 diff로 남깁니다."

예외:
- 분석·리뷰·요약·기획만 하는 작업
- 사용자가 자연어 요청에 이미 target_repo 경로를 포함한 경우

### Step 2: task.md 채우기

- `status`, `goal`, `constraints`, `acceptance criteria` 작성
- `_shared/routing.md` 기준 최소 worker set만 `planned_workers`에 명시
- `workers_approved`는 승인 전 비워둔다

### Step 3: context.md 작성

- 현재 스냅샷만 기록
- 1500자 한글 / 300단어 영문 이하
- 긴 자료는 `sources/`에 두고 경로로만 참조

### Step 4: 자료 추가

```bash
mkdir -p "$ROOT/tasks/$TASK/sources"
```

### Step 5: Worker 호출 시 (승인 후)

#### 5-1. brief 생성

```bash
ROLE=claude-main  # 또는 codex-main, codex-critic
mkdir -p "$ROOT/tasks/$TASK/workers/$ROLE"
cp "$ROOT/_templates/worker-brief.md" "$ROOT/tasks/$TASK/workers/$ROLE/brief.md"
```

`codex-main` / `codex-critic` 호출 시 brief 상단 필수:

```yaml
target_repo: /absolute/path/to/repo
write_scope: none | tasks-only | "src/**" 같은 패턴
```

#### 5-2. brief 크기 측정

```bash
wc -m "$ROOT/tasks/$TASK/workers/$ROLE/brief.md"
wc -w "$ROOT/tasks/$TASK/workers/$ROLE/brief.md"
```

#### 5-3. worker 호출

모든 worker 호출은 `_shared/backends.json` 정본 + 디스패처 `bash _shared/adapters/call_worker.sh <role> <brief-file>` → **envelope v2**(JSON). Orchestrator는 envelope의 `output.stdout_path`가 가리키는 파일 내용을 `result.md`에 기록한다(원문이 짧으면 `output.stdout_preview_sanitized`도 가능). **성공 여부는 최상위 `ok`(true/false) 또는 파생 `legacy_status`(`ok`/`error`/`empty`/`timeout`)로 판정** — 옛 `.stdout` 키는 없어졌다(v4 breaking). 호출 전 승인. (gemini worker 없음 — Antigravity 오케스트레이터 자체가 Gemini 3.1 Pro High)
- **claude-main**: 백엔드 `claude` CLI. [strategist] 기획·설계·전략·디자인 방향.
- **codex-main**: 백엔드 `codex` CLI. [engineer·computer-use] 대규모 구현·분석·테스트·브라우저 자동화.
- **codex-critic**: 백엔드 `codex` CLI. 독립 비평(교차벤더). 멀티모달·긴 문서는 워커가 아니라 오케스트레이터(Gemini)가 직접.

`codex-main` 외부 repo 쓰기 조건:
- `target_repo` 명시
- `write_scope` 명시
- `task.md`의 `workers_approved`에 외부 쓰기 승인 기록
- `log.md`에 `[APPROVAL]` 별도 기록

조건 미충족 시 `tasks/<task>/artifacts/`에 diff·patch 형태로 산출한다.

#### 5-4. result.md 생성

worker 응답을 받은 후 생성한다.

```bash
cp "$ROOT/_templates/worker-result.md" "$ROOT/tasks/$TASK/workers/$ROLE/result.md"
```

### Step 6: Artifacts

큰 산출물은 `tasks/<task>/artifacts/`에 저장하고, `result.md`에는 경로만 기록한다.

### Step 7: 검증 → 로그

`result.md`의 Verification Checklist 실행 후 `log.md`에 `[VERIFICATION]` 태그로 기록한다.

### Step 8: 작업 완료

- `task.md`의 `status: done` 갱신
- 재사용 교훈이 있으면 `_shared/learnings.md` 또는 `_local/learnings.md`에 분류해 추가
- `log.md`에 `[COMPLETE]` 태그로 마무리

## 명명 규칙

- 작업 폴더명: `kebab-case` 또는 `YYYYMMDD-keyword` 권장
- 한글 가능하지만 영문 권장

## 안티패턴

- 작업 폴더 안에 별도 `AGENTS.md` 만들기
- `context.md`에 히스토리 누적
- `brief.md`에 파일 내용 inline
- 사용 안 할 worker 폴더 미리 생성
- `workers_approved` 비어있는데 worker 호출
