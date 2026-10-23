# 알려진 이슈

해결되지 않은 알려진 결함을 추적한다. 고쳐지면 해당 항목을 닫고(✅) PR 링크를 단다.
시스템이 깨지는 크리티컬은 즉시 수정 대상, 표시·미관 한정은 보류 가능.

출처: `repo-consistency-audit` (2026-05-19, claude-main·codex-main 병렬 + Orchestrator 교차검증).
상세 근거표(`repo-consistency-audit`)는 공개 배포본에 미포함 — 유지보수자 전용.

---

## KI-1 (audit C3) — 표준 `worker-brief.md`를 쓰면 mat이 워커 목적을 ` ```yaml `로 표시

- **상태**: 열림 / **보류** (경미·표시 한정. 크리티컬 C1·C2는 PR #3·#5에서 해소됨)
- **심각도**: 낮음 — 시스템·워커 호출·데이터에 영향 없음. [mat](https://github.com/netwaif/mat) **모니터 화면 표시만** 오염. mat 미사용 시 영향 0.
- **재현**: 항상. `_templates/worker-brief.md` 표준 구조를 그대로 채운 brief를 쓰는 모든 작업. (이 audit의 codex-main brief에서도 실증됨.)

### 증상

mat의 핵심 화면 요소인 "워커 한 줄 목적"이 실제 Objective가 아니라 문자열 ` ```yaml `로 표시된다.

### 근본 원인

| repo | 파일·라인 | 내용 |
|------|-----------|------|
| starter | `_templates/worker-brief.md` | 1행 `# Brief`(heading), 2–4행 `<!-- -->`(comment), 6행 `## Execution Context`(heading), **8행 ` ```yaml ` fence** |
| mat | `internal/parser/task.go:280` | brief 존재 시 무조건 `w.Purpose = firstMeaningfulLine(brief 내용)` |
| mat | `internal/parser/task.go:499–515` | `firstMeaningfulLine`은 **빈 줄·`#`시작·`<!--`시작만 skip**, 그 다음 줄을 그대로 반환 |
| mat | `internal/parser/task.go:71–76` | `w.Purpose == ""`일 때만 `planned_workers.purpose`로 fallback |

표준 brief에서 heading·comment를 건너뛴 첫 "의미 있는" 줄은 `## Execution Context` 다음의 ` ```yaml ` fence다. 이 값이 비어있지 않으므로 `planned_workers.purpose` fallback도 발동하지 않는다.

### 수정 후보 (택1, 미결정)

- **(a) starter 템플릿** — `_templates/worker-brief.md`를 첫 의미 있는 줄이 실제 한 줄 목적이 되도록 재구성 (예: Execution Context yaml 위에 평문 목적 1줄, 또는 Objective를 평문으로 선두 배치).
  - 장점: starter 단독 수정, mat 재빌드 불필요, 자기완결.
  - 단점: 전 worker 공용 템플릿 변경. 1200자 한도·codex Execution Context yaml 요구와 양립해야.
- **(b) mat 파서** — `firstMeaningfulLine`이 코드펜스(` ``` `/` ```yaml `)도 skip하거나, 명시적 purpose 필드를 우선.
  - 장점: 임의 brief에 견고.
  - 단점: mat 재빌드·재배포 필요(`go build -o mat .` + 재실행). mat은 선택적 외부 도구라 비-mat 환경엔 무의미.

### 참고

- 공개 흔적: `_shared/learnings.md` [2026-05-19] (곁다리 언급), PR #5 본문.
- 크리티컬 해소 이력: PR #3 (C1 gemini 기본 모델), PR #5 (C2 gemini 단일 브리지).

---

## KI-2 — Antigravity 호스트 설치 경로 미확정 (루트 `plugin.json` 미동봉)

- **상태**: 열림 / **보류** (생성 코어엔 영향 없음. 머지 전 실설치 검증 대상)
- **심각도**: 중간 — `antigravity` flavor **생성·validate(12/12)·ZIP**은 호스트 독립으로 PASS. 영향 범위는 Antigravity를 **오케스트레이터 호스트로 두고 플러그인을 설치**하는 경로 한정.

### 증상

이 repo는 `.claude-plugin/`(Claude Code)·`.codex-plugin/`(Codex) 매니페스트만 동봉한다. 설계서(`design.md` Part A)가 Antigravity 호스트용으로 명시한 **루트 `plugin.json`은 repo에 없다**. 따라서 Antigravity 호스트의 로컬·마켓플레이스 설치 행은 매니페스트 없이 미검증 상태다.

### 실증된 것 / 미확정인 것

- **실증(2026-06-02, agy v1.0.4)**: agy로 플러그인을 로컬 사용 → "구성해줘" → 생성기 → validate PASS, end-to-end 동작. → agy가 플러그인+스킬을 **읽고 트리거**하는 것은 확인됨. (당시 antigravity flavor 추가 전이라 claude flavor로 실증.)
- **미확정**: agy/Antigravity IDE가 실제로 **어떤 매니페스트를 소비**하는지(skills/ 자동탐색 vs 루트 매니페스트 vs `.codex-plugin` 재사용). 루트 `plugin.json`의 정확한 스키마도 미확인.

### 다음 (머지 전)

- 사용자 Antigravity IDE 실설치로 (a)로컬 설치를 먼저 검증. (b)마켓플레이스 설치는 **PR 머지 전 검증 불가**(마켓플레이스는 main을 pull하므로) — 머지 후에만 가능.
- 실제 로딩 경로 확인 후, 필요하면 루트 `plugin.json`을 올바른 스키마로 추가하고 본 항목을 닫는다(✅).
- 그 전까지 매니페스트·README는 Antigravity를 **설치 호스트로 보장하지 않고**(생성 flavor로만 광고) 보수적으로 둔다.

---

## KI-3 — Windows 네이티브 미지원 (gemini/api 워커가 POSIX bash 디스패처에 의존)

- **상태**: 열림 / **보류** (출시 후 대응. 디스패처 Python 이식은 v2.1 로드맵)
- **심각도**: 중간 — 생성기·파일 코어·native(claude Task) 워커는 크로스플랫폼으로 동작. 차단점은 디스패처 경유 워커 — **gemini 워커(+api 폴백)**, 그리고 v3.7.0부터 **codex 워커**(`codex exec`도 디스패처 경유, D15).

### 증상

네이티브 Windows(cmd/PowerShell)에서 gemini 워커 호출 시 디스패처가 실행되지 않는다.

### 근본 원인

- `_shared/adapters/call_worker.sh`(+ `gemini_api.sh`)가 **bash·jq·timeout·mktemp·`/dev/null`** 등 POSIX 전용 요소를 사용.
- `_shared/backends.json`의 gemini 항목도 `stdin:"/dev/null"`, `cwd_policy:"isolated_tmp"` 등 POSIX 형태.
- native(claude)는 디스패처를 거치지 않아 영향 없음. codex 워커는 v3.7.0부터 디스패처 경유(옛 MCP 경로는 `codex mcp-server` 제거로 폐기)라 같은 제약을 받는다.

### 우회 / 미확정

- 우회: **WSL 또는 Git Bash + jq + agy**. 단 **`agy`(Antigravity CLI)의 Windows/WSL 지원 자체가 미검증** — Git Bash는 리눅스 바이너리를 못 돌리므로 더 불확실. → 우회로도 완전 보장 아님.
- 설치 자체가 bash 인스톨러(`curl … | bash`)라 agy는 맥/리눅스 지향으로 보임(네이티브 Windows 빌드 미확인).

### 다음 (출시 후)

- 실제 Windows 기기에서 풀 체인 검증: agy Windows/WSL 가용성 → jq·python3 → `call_worker.sh` 1회 실행.
- 필요 시 디스패처를 Python(`_shared/adapters/_run.py`)으로 이식해 OS 독립화(C안). 단 이식만으로 "네이티브 Windows 완전 지원" 보장은 아님(호스트 도구·agy 의존).
