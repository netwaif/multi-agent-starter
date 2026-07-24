# Task Folder Setup Guide

새 작업 시작 시 이 가이드대로 폴더와 파일을 생성한다.

## 폴더 구조

```
tasks/<task-name>/
├── task.md              # 필수. _templates/task.md 복사
├── context.md           # 필수. 현재 스냅샷, ≤ 1500자 한글 / 300단어 영문
├── log.md               # 필수. _templates/log.md 복사. append-only
├── sources/             # 선택. 원본 자료 (긴 문서, 참고 spec 등)
│   └── *.md, *.pdf, *.txt
├── workers/             # worker 호출 시 동적 생성
│   └── <role>/          # claude-main | codex-main | codex-critic | gemini
│       ├── brief.md     # _templates/worker-brief.md 복사. ≤ 1200자 한글 / 240단어 영문
│       └── result.md    # _templates/worker-result.md 복사
└── artifacts/           # 선택. worker 산출물 원본 (생성된 코드, 다이어그램 등)
    └── *
```

## 생성 절차

### Step 1: 작업 폴더 + 필수 파일

> 새 폴더가 기존 작업의 후속·핸드오프·하위 단계라면 생성 전에 `_shared/orchestrator-rules.md` §3 "새 작업 폴더 생성 게이트"를 먼저 적용한다(사용자 확인 + parent/context/메모리 연결).

```bash
TASK=my-task-name
ROOT=<설치한-폴더>
mkdir -p "$ROOT/tasks/$TASK"
cp "$ROOT/_templates/task.md"    "$ROOT/tasks/$TASK/task.md"
cp "$ROOT/_templates/log.md"     "$ROOT/tasks/$TASK/log.md"
cp "$ROOT/_templates/context.md" "$ROOT/tasks/$TASK/context.md"
```

### Step 1.5: target_repo 확인 (외부 산출물 작업인 경우)

codex-main이 planned_workers에 포함되거나 코드·문서·이미지를 만드는 작업이면, task.md 채우기 전에 사용자에게 짧게 묻는다:

> "이 작업의 산출물이 들어갈 외부 폴더(target_repo)가 있나요?
> (예: ~/projects/my-app. 없으면 tasks/<task>/artifacts/에 diff로 남깁니다)"

답을 task.md의 메모 또는 후속 brief.md의 `target_repo` 필드에 기록한다.

**예외 (묻지 않음)**:
- 분석·리뷰·요약·기획만 하는 작업 (gemini 단독 또는 claude-main 단독 문서 작성)
- 사용자가 자연어 요청에 이미 target_repo 경로를 포함한 경우

### Step 2: task.md 채우기

- `status: pending` → 작업 진행에 따라 갱신
- `goal`, `constraints`, `acceptance criteria` 작성
- `planned_workers`에 `_shared/routing.md` 참조하여 최소 set만 명시
- `workers_approved`는 비워두고 승인 후 채움

### Step 3: context.md 작성

- 현재 시점 스냅샷만 (히스토리 X)
- 1500자 한글 / 300단어 영문 이하 강제 (`wc -m` / `wc -w`로 측정)
- 긴 자료는 `sources/`에 두고 경로로 참조

### Step 4: 자료 추가 (선택)

```bash
mkdir -p "$ROOT/tasks/$TASK/sources"
# 원본 자료 복사 또는 작성
```

### Step 5: Worker 호출 시 (승인 후)

#### 5-1. brief 먼저 생성·작성
```bash
ROLE=claude-main  # 또는 codex-main, codex-critic, gemini
mkdir -p "$ROOT/tasks/$TASK/workers/$ROLE"
cp "$ROOT/_templates/worker-brief.md" "$ROOT/tasks/$TASK/workers/$ROLE/brief.md"
# brief.md 작성 (≤ 1200자/240단어)
```

**codex-main / codex-critic 호출 시 brief 상단에 다음 필드 필수**:
```yaml
target_repo: /absolute/path/to/repo    # 작업 대상 절대 경로 (없으면 N/A)
write_scope: none                      # none | tasks-only | "src/**" 같은 패턴
```

#### 5-2. brief 크기 측정
```bash
wc -m "$ROOT/tasks/$TASK/workers/$ROLE/brief.md"   # 한글 글자수 ≤ 1200
wc -w "$ROOT/tasks/$TASK/workers/$ROLE/brief.md"   # 영문 단어수 ≤ 240
```
초과 시 brief 압축 후 재시도.

#### 5-3. worker 호출 (`_shared/routing.md`의 호출 명령 참조)

- **claude-main**: Claude Code 내장 **Task tool (sub-agent)** 호출
  - `subagent_type`: `claude-main` (`.claude/agents/claude-main.md`에 정의)
  - `prompt`: brief.md 내용 그대로
  - `model`: agent frontmatter `model: opus` 자동 적용
  - 응답 텍스트를 Orchestrator가 받아 `result.md`에 기록
- **gemini**: `_shared/backends.json`의 `gemini`(백엔드 = Antigravity `agy` CLI, 기본 `gemini-3.1-pro-high`). 디스패처 `bash _shared/adapters/call_worker.sh gemini <brief-file>` → JSON envelope. Orchestrator가 envelope의 stdout을 `result.md`에 기록. (옛 `mcp__gemini-pro__*` 브리지 폐기)
- **codex-main / codex-critic**: `mcp__codex__codex` MCP 도구 호출
  - `prompt`: brief.md 내용 그대로
  - `cwd`:
    - codex-main 기본: `<설치한-폴더>/tasks/<task>/` (작업 폴더 안에서 산출물 작성)
    - codex-main 외부 쓰기 4조건 충족 시: brief.md의 `target_repo` 값
    - codex-critic: brief.md의 `target_repo` 값 (비평 대상 repo 컨텍스트)
  - `sandbox`:
    - codex-main: `workspace-write` 고정 (cwd 내부만 쓰기 가능. 외부 repo 쓰기는 cwd를 `target_repo`로 변경한 경우에만 해당 패턴 내 쓰기)
    - codex-critic: `read-only` 고정
  - `approval-policy`: `on-failure` 권장
- **codex-main 외부 repo 쓰기 조건**: `target_repo` + `write_scope` 명시 + `task.md`의 `workers_approved`에 외부 쓰기 승인 기록 + `log.md`에 `[APPROVAL]` 별도 기록 (4개 모두 충족 시에만 cwd를 `target_repo`로 변경)
- 위 조건 미충족 시 cwd는 작업 폴더로 두고, codex-main이 `tasks/<task>/artifacts/`에 diff·patch 형태로 산출. 사용자가 직접 적용

#### 5-4. result.md 생성
**worker 응답을 받은 후** 생성 (사전 빈 파일 생성 금지):
```bash
cp "$ROOT/_templates/worker-result.md" "$ROOT/tasks/$TASK/workers/$ROLE/result.md"
# worker 응답 채워 넣기
```
codex-main이 직접 쓴 경우는 형식만 worker-result.md 템플릿에 맞게 정리.

### Step 6: Artifacts (선택)

worker가 큰 산출물(코드 파일, 이미지 등)을 만들면:

```bash
mkdir -p "$ROOT/tasks/$TASK/artifacts"
# worker 산출물 저장
```

`result.md`에는 경로만 기록.

### Step 7: 검증 → 로그

`result.md`의 Verification Checklist 실행 → `log.md`에 `[VERIFICATION]` 태그로 기록.

### Step 8: 작업 완료

- `task.md`의 `status: done` 갱신
- 재사용 교훈 추가 (없으면 생략) — **시스템 일반**: `_shared/learnings.md`(추적·공개) / **프로젝트 특화**: `_local/learnings.md`(git 추적 안 함, 없으면 생성). `_local/learnings.md`는 명시 요청 없이는 읽지 않는다.
- `log.md`에 `[COMPLETE]` 태그로 마무리

## 명명 규칙

- 작업 폴더명: `kebab-case` 또는 `YYYYMMDD-keyword` 권장
- 한글 가능하지만 영문 권장 (Bash/도구 호환성)

## 안티패턴

- ❌ 작업 폴더 안에 별도 `CLAUDE.md` 만들기 (root CLAUDE.md만 사용)
- ❌ `context.md`에 히스토리 누적 (그건 `log.md` 역할)
- ❌ `brief.md`에 파일 내용 inline (경로만 전달)
- ❌ 사용 안 할 worker 폴더 미리 생성 (동적 생성 원칙)
- ❌ `workers_approved` 비어있는데 worker 호출
