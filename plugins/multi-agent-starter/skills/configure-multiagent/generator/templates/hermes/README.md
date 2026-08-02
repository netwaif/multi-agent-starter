# MultiAgent — Hermes · Codex · Claude · Gemini Orchestration Starter

Hermes를 오케스트레이터로 두고 Codex·Claude·Gemini를 필요할 때 워커로 호출하는 **파일 기반 멀티에이전트 시스템**.

## 핵심 아이디어

- **Orchestrator = Hermes 세션** (이 폴더 안에서 실행 시 `AGENTS.md` 적용)
- **Workers** = 별도 worker/model 호출. 모두 승인 게이트 통과 필요.
  - `codex-main` — [engineer] 크고 분리 가능한 구현·코드 분석·테스트·로컬 검증·이미지 생성
  - `claude-critic` — [reviewer · strategist 품질 게이트] Codex 산출물 리뷰·비평 (strategist 산출은 Orchestrator, critic은 판단만)
  - `gemini` — [multimodal] 이미지·긴 문서·제3자 시각의 검토

  슬롯→담당 배정의 정본은 `_shared/capability-profile.md`(가변층) — 신모델 출시 시 프로필만 갱신. engineer·computer-use 슬롯의 기본 담당은 Orchestrator 자신.
- **Memory = filesystem.** 런타임 상태 없음. 모든 결정·승인·검증이 파일로 남는다.

## 폴더 구조

```
<설치한-폴더>/
├── AGENTS.md              # Hermes용 운영 규칙 전문
├── _shared/
│   ├── routing.md             # worker 선택 decision tree + 호출 방식
│   ├── approval-policy.md     # 승인 게이트 정책
│   ├── orchestrator-rules.md  # 세션 시작·재진입 자체 점검 규칙
│   ├── design-basis.md        # 시스템 결정 근거
│   ├── system-invariants.md   # 시스템 수정 후 자가 점검
│   └── learnings.md           # 시스템 일반 재사용 교훈
├── _templates/
│   ├── task.md
│   ├── context.md
│   ├── worker-brief.md
│   ├── worker-result.md
│   ├── log.md
│   └── task-folder.md
└── tasks/
    └── <task-name>/
        ├── task.md
        ├── context.md
        ├── log.md
        ├── sources/
        ├── workers/<role>/
        │   ├── brief.md
        │   └── result.md
        └── artifacts/
```

`_local/`은 git 추적하지 않는 프로젝트 특화 교훈 저장소다. 공개 starter에는 시스템 일반 교훈만 `_shared/learnings.md`로 둔다.

## 사용 시작

```bash
cd <설치한-폴더>
hermes --tui
```

자연어로 새 작업 요청:

> "새 작업 만들어줘. 목표는 ○○이고 claude-critic 검수가 필요할 것 같아."

Orchestrator가 `_templates/task-folder.md` 가이드에 따라 작업 폴더 생성 → worker 승인 요청 → 진행.

## 모니터링 (선택) — mat

작업 진행을 터미널에서 지켜보고 싶다면 **[mat](https://github.com/netwaif/mat)** (MultiAgent Tracker)를 함께 쓴다.
이 시스템은 파일 구조를 유지하므로 mat가 작업 상태, worker 상태, goal, log를 읽을 수 있다.

```bash
brew install netwaif/tap/mat
MAT_ROOT=<설치한-폴더> mat
```

## 핵심 원칙

| 원칙 | 강제 방식 |
|------|-----------|
| 모든 worker 호출 전 승인 | `task.md`의 `workers_approved` 필드 |
| 외부/유료 모델 호출 전 별도 승인 | `AGENTS.md` External/Paid Model Approval |
| 측정 가능한 컨텍스트 한도 | `wc -m` / `wc -w` |
| append-only 로그 | `log.md` 수정·삭제 금지 |
| 최소 worker set | `_shared/routing.md` decision tree |
| codex-main 외부 repo 쓰기 4조건 | `target_repo` + `write_scope` + 승인 + log `[APPROVAL]` |

자세한 규칙은 [`AGENTS.md`](./AGENTS.md) 참고.

## 라이선스

개인 사용 및 학습 목적.
