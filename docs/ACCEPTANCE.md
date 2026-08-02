# MultiAgent v2 — 수용(Acceptance) 체크리스트 & 테스트 시나리오

> 대상: 배포되는 v2 시스템을 **claude / codex / antigravity / hermes** 네 호스트에서 검증.
> 자동화 가능한 항목은 `tests/`로 구현되어 있다 (`bash tests/run.sh`). 나머지는 수동.

---

## 0. 이 문서가 보장하는 것 (정직하게)

어떤 체크리스트도 "무조건 무문제"를 보장하진 못한다. 대신 **4개 층**을 통과하면
*배포 가능한 수준의 높은 신뢰*를 준다. 각 층이 보장하는 범위가 다르다.

| 층 | 무엇을 검사 | 자동/수동 | 보장 범위 |
|----|-------------|-----------|-----------|
| **L1 구조** | `validate.py` + `build_zip` 자가검증 + sync drift 0 | 자동(`tests/`) | 파일 **모양**(존재·불변식). 동작은 미보장 |
| **L2 스모크** | 지침 파일 로드, 디스패처 실행 가능 | 수동(빠름) | "켜지긴 한다" |
| **L3 기능** | task 라이프사이클 E2E, 워커 호출, 검증 루프 | 자동 일부 + 수동 | **실제 동작** |
| **L4 안전** | 승인 게이트·write_scope·디스패처 인젝션·timeout이 *실제로 막는지* | 자동 일부 + 수동 | **나쁜 입력 차단** |

**판정 기준**: 한 호스트에서 L1~L4를 모두 PASS = 그 호스트 배포 승인.
네 호스트 모두 승인 = 릴리스 가능.

### 자동화 매핑 (`tests/run.sh`)

| 테스트 | 커버 항목 | 종류 |
|--------|-----------|------|
| `tests/test_generate.py` | A2 / L1 — 4 flavor 생성 후 validate 전부 PASS | 자동·오프라인 |
| `tests/test_update_preserve.py` | S9 / A1 — update 모드 사용자 데이터 보존 | 자동·오프라인 |
| `tests/dispatcher/test_fallback.sh` | S5 — primary 실패 → fallback 성공, `fallback_used=true` | 자동·오프라인(가짜 bin) |
| `tests/dispatcher/test_timeout.sh` | S6 — timeout 초과 → `status=timeout`, `exit_code=124` | 자동·오프라인 |
| `tests/dispatcher/test_guards.sh` | A6 — usage/`..`/미정의 role/allowlist 차단 | 자동·오프라인 |
| **수동만** | A3 스모크, A4 실호출, S1/S2(워커·critic), S3 승인게이트, S4 write_scope, S7 컨텍스트, S8 재진입, antigravity 실설치 | — |

> 자동 테스트는 **외부·유료 모델을 호출하지 않는다**(가짜 `agy`/`claude`/`codex` 바이너리를 PATH로 주입).
> 따라서 회귀 검사로 매 빌드 안전하게 돌릴 수 있다.

---

## A. 호스트별 수용 체크리스트 (순서대로)

### A0. 사전 조건 (공통)
- [ ] `python3`, `jq` 사용 가능
- [ ] 대상 호스트 설치됨 (Claude Code / Codex / Antigravity IDE+`agy` / Hermes)
- [ ] 워커 백엔드 도달 가능 (flavor별, 아래)

| flavor | 오케스트레이터 | 필요한 워커 백엔드 |
|--------|----------------|--------------------|
| claude | Claude Code 세션 | `codex` MCP(`mcp__codex`), `agy`(PATH, 모델=gemini-3.1-pro-high), (선택) `GEMINI_API_KEY` |
| codex | Codex 세션 | `claude` CLI(PATH), `agy`(PATH, pro-high) |
| antigravity | `agy`/Antigravity IDE (Gemini 3.1 Pro High) | `claude` CLI, `codex` CLI (PATH) |
| hermes | Hermes Agent | `codex` CLI, `claude` CLI, `agy`(PATH, pro-high) |

> 모델 정책: `agy`는 모델이 전역/계정 단위(`/model`). 검증 전 **pro-high로 설정** 확인.

### A1. 설치 (세 경로 중 택1) + 즉시 검증
- [ ] **generator**: `python3 plugins/multi-agent-starter/skills/configure-multiagent/generator/init.py --flavor <X> --target <DIR> --yes` → 설치 후 validate 자동 실행
- [ ] **plugin**: 호스트 마켓플레이스 add → "멀티에이전트 구성해줘" → init.py 실행
- [ ] **zip**: 압축 해제 → `run.command`(mac)/`run.bat`(win)
- 통과: 필수 파일 존재 + 아래 A2 validate 통과

### A2. 구조 검증 (L1, 자동)
- [ ] `python3 plugins/multi-agent-starter/skills/configure-multiagent/generator/validate.py --flavor <X> --target <DIR>` → 0 FAIL ("전부 PASS")
- [ ] (유지보수자) `bash tests/run.sh` 전체 PASS
- [ ] (유지보수자) `build_zip` 3-flavor 자가검증 PASS / `sync_claude_template.py` drift 0

### A3. 스모크 (L2, 수동)
- [ ] `<DIR>`를 해당 호스트에서 열기 → 오케스트레이터에 "이 시스템 규칙 요약해" 요청
      → **승인 게이트 / log 태그 6종 / 워커풀**을 정확히 답해야 함 (지침 파일 자동 로드 증거)
- [ ] 디스패처 존재·실행: `bash _shared/adapters/call_worker.sh` (인자 없이 → usage 에러로 살아있음 확인)

### A4. 워커 디스패치 (L3, 실호출 — 승인 필요, 수동)
- [ ] 사소한 task 생성 → 워커 1개 승인 → `call_worker.sh <role> <brief>` 실행
      → 결과 envelope JSON `{status, exit_code, backend, model, duration_s, stdout, stderr_sanitized, fallback_used}` 수신

### A5. 전체 라이프사이클 (L3, 수동)
- [ ] `task.md`(pending) → `brief.md` → 워커 실행 → `result.md` 저장
      → result의 Verification Checklist 실행 → `log.md`에 `[VERIFICATION]` append

### A6. 네거티브 / 안전 (L4)
- [ ] **승인 안 된 워커 호출** → 오케스트레이터 거부 *(수동)*
- [ ] **4조건 없는 외부 repo 쓰기** → `tasks/<task>/` 내부에만 산출 *(수동)*
- [ ] **디스패처 가드**: usage / `..` / 미정의 role / allowlist 밖 명령 → 차단 *(자동: `test_guards.sh`)*
- [ ] **timeout**: 무한 워커 → `exit_code=124` *(자동: `test_timeout.sh`)*
- [ ] **폴백**: primary 실패 → fallback 성공 *(자동: `test_fallback.sh`)*

### A7. 재진입 (L3, 수동)
- [ ] 새 세션/`/compact` → 재진입 프로토콜(orchestrator-rules §3)대로 디스크에서 상태 복원

---

## B. 테스트 시나리오 (구체·호스트 교차)

| ID | 목표 | 핵심 단계 | 기대 결과 | 층 | 자동? |
|----|------|-----------|-----------|----|-------|
| **S1** | 단일 워커 happy path | task→approve 1 worker→dispatch | result envelope status=ok, log 기록 | L3 | 수동 |
| **S2** | Producer-Reviewer | 워커 산출 → critic 검수 | critic가 독립 벤더로 비평 반환 | L3 | 수동 |
| **S3** | 승인 게이트 위반(neg) | 미승인 워커 호출 시도 | 오케스트레이터 거부 | L4 | 수동 |
| **S4** | 외부쓰기 4조건(neg+pos) | (a)조건 누락 (b)4조건 충족 | (a) tasks/만 (b) target_repo 쓰기 + `[APPROVAL]` log | L4 | 수동 |
| **S5** | 디스패처 폴백 | primary 백엔드 실패 유도 | fallback 실행, `fallback_used=true`, exit 0 | L3/L4 | **자동** |
| **S6** | 디스패처 timeout | 워커가 timeout 초과 | `status=timeout`, `exit_code=124` | L4 | **자동** |
| **S7** | 컨텍스트 초과 | `context.md` `wc -m` > 한도 | 초과분 log로 archive, 스냅샷만 유지 | L3 | 수동 |
| **S8** | 재진입 | `/compact` 후 새 세션 | task/log 읽고 정확히 이어감 | L3 | 수동 |
| **S9** | update 모드 보존 | 기존 `tasks/`·`_local/` 있는 폴더에 재설치 | 사용자 데이터 무손실, 시스템 파일만 갱신 | L3 | **자동** |
| **S10** | 교차 호스트 매트릭스 | S1+S2를 4 flavor 전부 | 각 flavor 동일하게 통과 | L1~L4 | 부분 |

> 우선순위: **S3·S6·S5(안전) > S1·S8·S9(핵심) > S2·S4·S7 > S10(교차)**.

---

## C. 신뢰도 매핑 & 사인오프

**자동으로 보장**(매 빌드, `tests/run.sh`): 파일 구조·불변식, update 보존, 디스패처 폴백/타임아웃/가드.
**수동으로만 확인**: 실제 워커 호출 동작, 승인 게이트 *행동*, 오케스트레이터의 지침 준수,
컨텍스트 한도 운영, antigravity 실설치 로딩 경로.

### 호스트별 사인오프 표 (테스트 시 채움)

| flavor | L1 구조 | L2 스모크 | L3 기능 | L4 안전 | 설치경로 검증 | 승인 |
|--------|---------|-----------|---------|---------|---------------|------|
| claude | ✅ | ✅ | ☐ | ⚠️자동만 | gen ✅ / plugin ☐ / zip ☐ | ☐ |
| codex | ✅ | ✅ | ☐ | ⚠️자동만 | gen ✅ / plugin ☐ / zip ☐ | ☐ |
| antigravity | ✅ | ✅ | ☐ | ⚠️자동만 | gen ✅ / plugin ☐ / zip ☐ | ☐ |
| hermes | ✅ | ☐ | ☐ | ⚠️자동만 | gen ✅ / plugin 해당 없음 / zip ☐ | ☐ |

> **2026-06-03 검증 기록** (로컬, generator 경로):
> - **L1 구조**: 4 flavor 모두 `validate` PASS, `tests/run.sh` ALL PASS.
> - **L2 스모크**: 4 flavor 모두 생성 폴더를 해당 호스트에서 열어 "규칙 요약" 시 지침 자동 로드 + 승인게이트·log태그·컨텍스트한도·워커풀·외부쓰기4조건을 정확히 답함.
>   - claude: `CLAUDE.md`, codex 워커 = **MCP**(`mcp__codex`, 프로젝트 `.mcp.json` 동봉).
>   - codex: `AGENTS.md`, 워커 = claude-critic·gemini (codex-critic 비활성).
>   - antigravity: `AGENTS.md`, codex 워커 = **CLI**(`codex exec`). **실증**: Antigravity는 프로젝트-로컬 `.mcp.json`을 안 읽고 전역 `~/.gemini/antigravity-ide/mcp_config.json`만 봄 → CLI 기본이 유일한 zero-config 경로(설계 확정). codex MCP 전환은 그 전역 파일에 등록하는 1회성 업그레이드.
> - **⚠️ 미검증**: L3 기능(실제 워커 호출·전체 라이프사이클), L4 수동 안전(승인게이트 *행동*·write_scope) — L4 자동분(디스패처 폴백/타임아웃/가드)은 `tests/`로 PASS. plugin/zip 설치경로(마켓플레이스는 머지 후), 호스트별 최종 승인.

### 미해결 의존성 (배포 전 닫아야)
- [x] ~~antigravity 실설치 로딩 경로 확정~~ → **해결(2026-06-03)**: Antigravity는 폴더를 IDE에서 열면 `AGENTS.md`를 자동 로드(스모크 통과). 별도 루트 plugin.json 불요 = F1 핵심 닫힘. codex 워커는 CLI(`codex exec`)가 zero-config 기본.
- [ ] PR #13 main 머지 → 마켓플레이스(plugin) 설치 경로 검증 가능 (현재 generator 경로만 검증됨)
- [ ] L3 기능(실제 워커 호출·전체 라이프사이클) + L4 수동 안전(승인게이트 행동·write_scope) 호스트별 1회씩
- [ ] zip 설치 경로 1회 검증
- [ ] 각 호스트 워커 CLI/MCP 실제 PATH·인증 (사용자 환경)
