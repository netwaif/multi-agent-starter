<p align="center">
  <img src="./assets/brand/harness-multiagent-banner.png" alt="Harness MultiAgent" width="100%">
</p>

# multi-agent-starter

파일 기반 멀티에이전트 오케스트레이션 시스템 **생성기**. Claude Code · Codex · Antigravity · Hermes
어느 쪽이든 오케스트레이터로 두는 file-as-memory 멀티에이전트 시스템을 원하는 폴더에 결정적으로 만든다.
**어느 벤더·모델에도 매이지 않는 하네스**가 목표 — 워커는 역할이고, 모델·연결 방식은 교체 가능한 설정이다.

> v2부터 "clone 후 그대로 사용"이 아니라 **플러그인/생성기**로 배포한다.
> 설치 후 자연어 한 마디 — "멀티 에이전트 시스템 구성해줘" — 면 끝.

> **동작 환경**: macOS·Linux에서 개발·검증됨. Windows는 **실험적** — 설치·시스템 구성·클로드 워커·코덱스 워커는 동작하지만, 제미나이 워커는 WSL 등 POSIX 환경(bash·jq·agy)이 필요하며 **아직 검증 전**이다. 정식 Windows 지원은 후속 버전 목표. (자세히는 KNOWN_ISSUES.md KI-3)

## 무엇을 만들어 주나

선택한 **flavor**에 맞는 시스템 파일 한 세트를 대상 폴더에 생성한다:

| flavor | 오케스트레이터 | 워커 풀 |
|--------|----------------|---------|
| `claude` | Claude Code 세션 | claude-main · codex-main · codex-critic · gemini |
| `codex`  | Codex 세션 | codex-main · claude-critic · gemini |
| `antigravity` | Antigravity 세션 (Gemini 3.1 Pro High) | claude-main · codex-main · codex-critic (멀티모달은 오케스트레이터 직접) |

생성되는 시스템에 포함되는 것:

- **승인 게이트** — 모든 워커(외부 모델) 호출 전 명시 승인
- **연결 어댑터 레이어** — `_shared/backends.json`(역할→모델→연결방식 native·mcp·cli·api 레지스트리)
  + `_shared/adapters/call_worker.sh` 디스패처. 모델·벤더를 바꿔도 시스템 규칙은 그대로 (vendor/model-free)
- **작업 재진입 프로토콜** — 콜드세션 복귀 시 재정박 → 분기 판단 → 에러 후 진행
- **토폴로지 4패턴** — Pipeline / Fan-out·Fan-in / Expert Pool / Producer-Reviewer
- **불변식 자가점검** — 생성 직후 `validate.py`가 구조를 검증(PASS/FAIL)
- **file-as-memory** — 런타임 상태 0, 모든 결정·승인·검증이 파일로 남는다

생성은 **결정적**이다 — 번들 템플릿을 그대로 복사하며, 모델이 시스템 파일을 창작하지 않는다.

## 설치 & 사용

Claude Code·Codex 모두 **동일한 플러그인 흐름**이다:

1. 호스트에서 `/plugins` 실행
2. **Add Marketplace** 선택 → 저장소 `netwaif/multi-agent-starter` 입력
3. 목록에서 **multi-agent-starter** 를 Enter로 설치·활성화
4. `멀티 에이전트 시스템 구성해줘` → flavor·대상 폴더를 묻고 생성

### ZIP (플러그인 없이 — 최소 기술)

1. [Releases](https://github.com/netwaif/multi-agent-starter/releases)에서 `multi-agent-starter-<버전>.zip` 받아 압축 해제
2. macOS `run.command` / Windows `run.bat` 더블클릭 (또는 폴더에서 `python3 init.py`)
3. 메뉴에서 flavor·대상 폴더 선택

### 직접(개발자) — 생성기 호출

```bash
python3 plugins/multi-agent-starter/skills/configure-multiagent/generator/init.py --flavor <claude|codex|antigravity|hermes> --target "<대상폴더>" --yes
```

설치가 끝나면 자동으로 `validate.py`가 돌며 PASS/FAIL을 보여준다.

## 설치 후

생성된 폴더로 이동해 해당 도구를 실행하고 자연어로 작업을 요청한다:

```
> 새 작업 만들어줘. 목표는 ○○이고 ○○ worker가 필요할 것 같아.
```

Orchestrator가 작업 폴더를 만들고 → 워커 승인을 요청한 뒤 → 진행한다.
운영 규칙 전문은 생성된 폴더의 `CLAUDE.md`(claude) / `AGENTS.md`(codex·antigravity·hermes) 참조.

## v1 → v2 마이그레이션 (기존 clone 사용자)

v1은 이 repo를 clone해 루트 파일을 그대로 썼다. v2에서는 **같은 폴더에 생성기를 다시 돌려**
시스템 파일만 최신화하면 된다 — 작업 데이터는 보존된다.

1. 플러그인 설치(위 "설치 & 사용") 또는 ZIP 다운로드
2. 기존 폴더를 대상으로 생성기 실행:
   ```bash
   python3 <plugin-or-zip>/generator/init.py --flavor claude --target "<기존-폴더>" --yes
   ```
3. **update 모드**로 동작 — `tasks/`·`_local/` 사용자 데이터는 보존하고
   시스템 파일(`CLAUDE.md`, `_shared/*`, `_templates/*` 등)만 덮어쓴다.
4. 끝에 `validate.py`가 자동 실행 — PASS 확인 후 사용

> ⚠️ 시스템 파일을 직접 커스터마이즈했다면 덮이기 전에 백업/커밋해 둔다.
> 생성기는 번들 템플릿으로 덮어쓰며 로컬 수정은 유지하지 않는다.

## 필수 도구 & 문제 해결

대부분의 실패는 **명확한 메시지와 함께 멈춘다**(조용히 깨지지 않음). 아래만 갖추면 된다.

- **Python 3** — 생성기 실행에 필요(`python3`). Windows는 `python`·`py`일 수 있다. 없으면 생성 단계가 안 된다.
- **jq** — 제미나이 워커(gemini/api 디스패처)의 JSON 파싱에 필요. 없으면 `call_worker: jq 필요`로 멈춘다. (macOS는 기본 미설치 — `brew install jq`)
- **agy (Antigravity CLI)** — 제미나이 워커 백엔드. 설치·로그인 후 PATH에 있어야 한다.
- **codex CLI** — 코덱스 워커 백엔드. 정상 경로는 MCP 서버(`codex mcp-server`, `.mcp.json`)다.
- **git** — 권장(필수 아님). (1) 클로드 워커의 작업 격리(worktree)에 쓰인다 — 없으면 격리 없이 동작(폴백). (2) 코덱스를 **CLI 폴백**으로 부를 때만 기본 요구된다(**정상 MCP 경로는 무관**). 우회: `MULTIAGENT_CODEX_SKIP_GIT=1`. 새 작업 폴더면 `git init` 권장.

> 에러가 나면 `call_worker: …` 메시지가 가리키는 도구를 설치하고 재시도하면 대부분 해결된다.

## 모니터링 (선택) — mat

작업 진행을 터미널에서 지켜보고 싶다면 **[mat](https://github.com/netwaif/mat)** (MultiAgent Tracker)를 함께 쓴다.
한 작업의 워커 상태(대기·실행 중·완료·에러)·goal·로그를 한 화면에서 본다.
시스템을 **읽기만** 하므로 켜두거나 꺼도 진행에 영향이 없다.

```bash
brew install netwaif/tap/mat
MAT_ROOT=<생성된-폴더> mat
```

설치·키 조작 등 자세한 내용은 [mat 저장소](https://github.com/netwaif/mat) 참고.

## 저장소 구조

```
multi-agent-starter/                 # 마켓플레이스 카탈로그 (루트)
├── .claude-plugin/marketplace.json  # Claude Code 마켓 카탈로그 → plugins/multi-agent-starter
├── .agents/plugins/marketplace.json # Codex 마켓 카탈로그 → plugins/multi-agent-starter
├── plugins/
│   └── multi-agent-starter/         # ← 플러그인 본체 (각 호스트가 설치하는 단위)
│       ├── .claude-plugin/plugin.json
│       ├── .codex-plugin/plugin.json
│       └── skills/configure-multiagent/   # "구성해줘" front door (자기완결 스킬)
│           ├── SKILL.md
│           └── generator/          # ← 스킬과 한 몸으로 동봉 (agy가 스킬째 복사해도 따라옴)
│               ├── init.py         # 결정적 생성기 (flavor·대상·tasks 보존·dry-run·guard)
│               ├── validate.py     # flavor별 불변식 자가점검
│               ├── build_zip.py    # 자립형 ZIP 빌더 (재현가능)
│               └── templates/{claude,codex,antigravity,hermes}/   # 네 flavor 정본
├── tests/                          # 오프라인 결정적 회귀 테스트 (run.sh)
└── docs/ACCEPTANCE.md              # 4호스트 수용 체크리스트 + 테스트 시나리오
```

> **generator가 스킬 안에 있는 이유**: Antigravity(agy)는 플러그인 설치 시 인식하는 컴포넌트(skills/agents/…)만 복사하고 임의 폴더(generator/)는 버린다. 스킬 폴더 안에 두면 스킬과 함께 복사돼 Claude·Codex·Antigravity·Hermes 모두에서 "구성해줘"가 동작한다.

> **플러그인이 하위 폴더에 있는 이유**: Codex는 로컬 마켓에서 플러그인 source가 repo 루트(`"./"`)인 걸 거부한다([openai/codex#17066](https://github.com/openai/codex/issues/17066)). 그래서 루트는 마켓 카탈로그만 두고 플러그인은 `plugins/multi-agent-starter/`에 둔다 — Claude·Codex 양쪽에서 설치된다.

## 품질 — 테스트 & 수용 검증

- **자동 회귀 테스트**(외부·유료 모델 호출 0): `bash tests/run.sh`
  - 4 flavor 생성→`validate` 전부 PASS, update 모드 사용자 데이터 보존,
    디스패처 폴백·타임아웃·입력 가드(가짜 백엔드 주입). 매 빌드 안전 실행.
- **수용 체크리스트**: [`docs/ACCEPTANCE.md`](./docs/ACCEPTANCE.md) — claude·codex·antigravity·hermes
  네 호스트별 설치→구조→스모크→기능→안전 4층 검증 + 사인오프 표. 배포 전 호스트별로 채운다.

## 알려진 이슈

해결·보류 중인 알려진 결함은 [`KNOWN_ISSUES.md`](./KNOWN_ISSUES.md)에 추적한다.

## 라이선스

[MIT](./LICENSE)
