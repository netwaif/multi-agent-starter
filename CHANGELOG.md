# Changelog

이 파일은 multi-agent-starter **패키지/배포**의 버전 이력이다.
**설치된 시스템의 동작** 변경 이력은 생성된 폴더의 `CHANGELOG.md`
(정본: `generator/templates/{claude,codex}/CHANGELOG.md`)를 참조한다.
형식은 [Keep a Changelog](https://keepachangelog.com/), 버전은 [Semantic Versioning](https://semver.org/lang/ko/)을 따른다.

## [3.6.0] - 2026-09-06

### Added
- **집행층 코드화 (D14)** — 기계로 판정 가능한 규칙을 산문에서 벤더중립 셸 스크립트로 이관(3 flavor 공유,
  호스트 훅 미도입). ① `_shared/adapters/gate.sh <brief>` 사전 게이트(fail-closed, exit 9):
  G0 인터랙티브 세션 · G1 brief 위치 · G2 workers_approved · G3 `[APPROVAL]` 로그 · G4 한도(한글 1200자/영문 240단어,
  한글 비율 판정) · G5 외부 쓰기 조건(승인 항목의 target_repo·write_scope가 brief와 정확 일치).
  ② `_shared/adapters/scope_check.sh` 사후 검사(보고만, exit 10): `--snapshot` + 실행 후 대조(porcelain -z +
  내용 해시 → dirty/untracked 재수정·rename 원본까지 검출). ③ `_shared/reentry-check.sh <task>` 재진입 정합
  (status↔log 불일치 검출, 정정은 오케스트레이터). 디스패처가 gate·scope_check를 자동 배선(역할 불일치 거부,
  scope별 cwd: none/tasks-only는 루트, 위반은 폴백 없는 최종 실패, envelope `scope_check`·`scope_violations`).
  native/mcp 호출은 지침 Lifecycle 6에 따라 호출 전 gate.sh 실행. INV14 + validate C9c + tests 3종 신설.
  발견 경위: harness-self-review 권고 6 채택 + astra(gpt-6-astra) 설계 리뷰 11건 반영.

### Changed
- **claude flavor 1.5.0 / codex flavor 0.6.0 / antigravity flavor 0.4.0** — 위 집행층 동봉, 승인 항목 스키마에
  외부 쓰기용 `target_repo`·`write_scope` 필드(approval-policy), 지침 Lifecycle 6·Approval Gate·쓰기 정책·재진입에
  집행 포인터.

## [3.5.0] - 2026-07-24

### Added
- **불변식 자가점검 러너 `_shared/check-invariants.sh`** (3 flavor) — 기존 "grep 출력을 눈으로
  판독"하던 자가점검을 exit-code 판정으로 전환(false PASS 방지). claude flavor는
  `--self-test`(불변식을 하나씩 깨뜨린 fixture가 FAIL하는지 러너 자체 검증) 포함.
  validate C1 필수 파일에 편입.
- **디스패처 payload 동봉** — `call_worker.sh <role> <brief> [payload]` 3번째 인자 +
  `--merged-preview`. gemini 소스 검토의 "brief 인라인 필수"와 brief 불변식(inline 금지·
  1200자)의 모순 해소: 자료는 `sources/gemini-packet.md`로 분리, 디스패처가 결합.

### Fixed
- **backends.json 미소비 선언 제거** — 디스패처가 읽지 않는 `write_policy`·`non_interactive`
  필드를 3 flavor에서 제거(희망사항 config = 거짓 안전신호).
- **claude flavor 1.4.0 / codex flavor 0.5.0 / antigravity flavor 0.3.1** — backends.json 실행계약 모순 교정
  (codex-main sandbox `read-only`→`workspace-write`, CLI 폴백 sandbox·cwd 명시) +
  미구현 gemini api 폴백 비활성(거짓 안전신호 제거) + INV13 신설(claude flavor).
  발견 경위: Fable5∥Sol 이중 독립 시스템 리뷰(공통 검출 C1·C3).

### Changed
- **루트↔claude 템플릿 sync 복원** — v3.3이 템플릿에만 넣은 2층 라우팅
  (capability-profile·슬롯 트리)을 루트(유지보수자 본체)에도 승격하고, 반대로 v1.3.0
  개편 때 템플릿에서 누락된 상세 규칙(gemini 이미지/PDF 검수 정본 경로·작업 폴더 분리
  게이트 상세 등)을 템플릿에 복원. design-basis·learnings는 audience 분기로 sync
  제외 명시(D 번호는 루트가 할당·공유: 2층 D9→D12, backends D10→D11 재정렬).
  `sync_claude_template.py` check 기준 drift 0 회복.

## [3.4.0] - 2026-07-19

### Fixed
- **update 모드 지침파일 유실 결함** — `init.py`가 기존 CLAUDE.md/AGENTS.md를 백업 없이
  덮어써 loadout store 조각(`<!-- store:*:start/end -->` 블록)이 유실되던 문제 수정.
  이제 덮어쓰기 전 원문을 `<지침파일>.multiagent-bak`으로 백업하고, store 블록을 새
  지침파일 끝에 재부착한다(`preserve_instruction`). 마커 밖 사용자 수기 내용은 자동
  병합하지 않음 — 백업에서 수동 복원.
- SKILL.md·init.py의 "보존" 안내 문구를 실제 동작(tasks/·_local/ + 지침파일 백업·재부착)에
  맞게 정정.

### Added
- `tests/test_update_preserve.py`에 store 블록 보존·백업 생성 검사 2건.

## [3.3.0] - 2026-07-13

### Added
- **라우팅 2층 분리 (3 flavor 전부)** — `_shared/capability-profile.md` 신설(가변층:
  능력 슬롯→담당 배정, 근거·날짜 필수·이력 append-only). routing.md는 안정층(작업 유형→
  능력 슬롯 strategist·engineer·computer-use·reviewer·multimodal)으로 재편 — 신모델 출시·
  판정 변경 시 프로필만 갱신하고 시스템 파일은 불변. 초기 배정 근거 = 2026-07-13 외부 리뷰
  10건 종합 판정(설계·디자인·전략·글쓰기 = Claude 우위 / 대규모 구현·테스트·브라우저 조작·
  비용·속도 = GPT 우위). 각 flavor design-basis에 결정 기록(claude D9, codex D8, antigravity D8).
- **computer-use 슬롯 신설** — 브라우저 조작·도구 워크플로우 자동화의 독립 라우팅 분기.
- **validate C5b** — 2층 라우팅 불변식(routing→profile 참조 + 프로필 슬롯 5종), C1에
  `_shared/capability-profile.md` 추가.

### Fixed
- **`.codex-plugin/plugin.json` 버전 방치(3.1.0) 교정** — 3.2.0 릴리스 시 범프 누락으로
  repo-check R2(version 일관)가 FAIL이던 기존 결함 해소. 3종 매니페스트 3.3.0 일괄.

## [3.2.0] - 2026-07-10

### Removed
- **`generator/guard/` 가드 자산 제거** — v3.0.0에 예정했던 이관의 완료.
  [loadout](https://github.com/netwaif/loadout) 0.4.0이 codex점을 열면서(`--flavor codex`)
  codex 워처(`codex_goal_watch.mjs`)·README 정본이 loadout guard 품목(`files.codex/`)으로
  이관됐다(claude Stop 훅 정본은 이미 loadout `hook.json`). 가드 설치·검증은 전부 loadout 소관:
  설치=`store.py --pick guard [--flavor codex]`, 검증=`store.py --doctor`(정본 대조).
- **validate C12(요금가드 배선 사후검증) 제거** — 대조할 정본이 loadout으로 갔으므로
  검증 소관도 loadout doctor로 이관. tests의 가드 기본부재 단언은 유지.

## [3.1.0] - 2026-07-08

### Removed
- **`skills/knot/` 능동 스킬 제거** — knot 능동 스킬(save/ingest/query/lint)은
  [netwaif/knot](https://github.com/netwaif/knot) 자체 플러그인(1.0.0)이 배포한다
  (마켓플레이스에 `netwaif/knot` 추가). v3.0.0 knot 이관의 마무리 — 스킬 정본·배포처 단일화.
  - **존치**: `knot_block.md` 정본 · `knot-vault/` 스캐폴드 · validate C10(관리블록 사후 검증).
  - v2.x 기존 설치자는 영향 없음. 플러그인 업데이트 시에만 스킬이 빠지며, knot 마켓 추가로 대체.

## [3.0.0] - 2026-07-06

### Removed (BREAKING)
- **`--with-knot` / `--with-guard` 옵트인 제거** — knot·요금가드의 *설치*는
  [loadout](https://github.com/netwaif/loadout) 카탈로그("CLAUDE.md 구성 골라 담아줘")
  담당으로 이관. configure-multiagent 절차의 knot·가드 질문/후속 안내 단계도 제거.
  - **존치**: `knot` 능동 스킬(플러그인 스킬, save/ingest/query/lint) ·
    `knot_block.md`/`knot-vault/` 스캐폴드 · `guard/`(codex 워처 + Stop 훅 정본) ·
    validate C10·C12(사후 검증 — loadout 설치물에도 유효).
  - codex 가드 워처 설치는 `generator/guard/README.md`의 수동 복사(loadout codex점 전까지).
  - **기존 설치자 영향 없음** — 기본 생성물 무변경, 이미 주입된 관리블록·훅은 그대로 동작.

## [2.2.2] - 2026-07-04

### Fixed
- **gemini 워커 폴백 실패 사유 유실** — `call_worker.sh`가 api 폴백의 필수 env
  (`GEMINI_API_KEY`) 부재 시 `die`로 죽어 실패 사유가 최종 envelope에 남지 않던 문제.
  에러 envelope(`stderr_sanitized`)로 반환하도록 수정 + 호출 시작 시 폴백 불가 사전 경고 추가.
  템플릿 3종(claude 1.2.2 / codex 0.3.2 / antigravity 0.2.2) 동일 반영.
  기존 설치자는 `_shared/adapters/call_worker.sh`를 새 버전으로 교체하면 된다.

### Changed
- **routing.md gemini 규칙 보강**(claude/codex flavor) — 소스·다중파일 검토는 brief에
  스니펫 **인라인 필수**(디렉토리 순회 시 agy 헤드리스 300s 타임아웃 실측), 폴백 조건
  (`GEMINI_API_KEY`) 명문화, 시간 제한 작업 전 경량 스모크 권장.

## [2.2.1] - 2026-07-03

### Fixed
- **gemini(agy) 워커 프롬프트 미전달** — Antigravity CLI 1.0.16에서 `-p` 단축 플래그 제거로
  backends.json `args_template`의 프롬프트가 조용히 무시되던 문제(모델 미호출·사용량 0).
  템플릿 3종(claude 1.2.1 / codex 0.3.1 / antigravity 0.2.1) 전부 `--prompt`로 교정.
  기존 설치자는 `_shared/backends.json`의 `"-p"`를 `"--prompt"`로 한 줄 수정하면 된다.
- task.md 작성 규칙 명문화(CLAUDE.md) — `## 메타` yaml 펜스 형식 강제(frontmatter 금지),
  mat 모니터 파싱 정본과 일치.

## [2.2.0] - 2026-06-28

### Added
- **opt-in goal 요금가드(`--with-guard`)** — `/goal` 자율 루프가 주간 사용량 한도에 닿으면 자동
  정지하는 벤더중립 안전장치. 기본 미설치. **정책=`coach`(usage-coach, codexbar 의존) 단일정본,
  하네스=배선만**. flavor별 주입: claude=`.claude/settings.json` Stop훅(`coach --hook`, inline
  `command -v coach … || true` fail-open), codex=`_shared/guard/` 워처(loopback WebSocket `ws://127.0.0.1:47931`→
  `thread/loaded/list`→`thread/goal/clear`). antigravity는 `/goal` 자율 루프 부재로 미지원(다음 버전).
  런타임 on/off=`coach guard on/off/status`. 미설치·플래그 off·조회실패는 모두 fail-open. generator
  결정성 불변(init.py 고정 정본 복사·병합만, knot `--with-knot`과 동형). `configure-multiagent` SKILL에
  opt-in 질문(4b)·후속안내(7b) 추가. 회귀보호=validate **C12** + test_generate guard_checks(3 flavor ×
  주입·멱등·기본부재). 설계근거 `_shared/design-basis.md` **D10**. coach 정책층 = 별도 핸드오프
  (usage-coach repo, tasks/harness-quota-guard/workers/handoff-usage-coach.md). (tasks/harness-quota-guard/)

## [2.1.1] - 2026-06-25

### Fixed
- **오케스트레이터가 기존 작업의 후속·핸드오프를 사용자 확인 없이 새 task 폴더로 분리하던 문제.**
  `_shared/orchestrator-rules.md` §3에 "새 작업 폴더 생성 게이트" 추가 — 분리 전 사용자 확인 강제 +
  분리 시 parent·context 필독입력·메모리 포인터 연결고리. CLAUDE.md Task Lifecycle·`_templates/task-folder.md`에
  포인터, generator 템플릿 3종(claude/codex/antigravity)에 전파. codex-critic/gemini 검수 반영
  (확인 절차와 연결고리 분리·예외를 '독립 신규작업'으로 한정·경로 불문). 회귀 GREEN(test_generate all pass, INV8/11a).

## [2.1.0] - 2026-06-17

매뉴얼 v2.1과 정렬. (이전까지 `plugin.json`이 2.0.0에 머물러 배포 매뉴얼 2.1과 버전이 어긋나 있던 것을 동기화.)

### Added
- **knot 배포(P1~P6)** — 벤더중립 standalone 지식 vault. 능동층=플러그인 최상위 스킬(claude·codex·agy
  네이티브 로드), 자동층=opt-in `--with-knot` 관리블록 주입(멱등). vault 경로=env `$KNOT_VAULT` +
  `~/.config/knot/vault` 파일 fallback. `configure-multiagent`에 설치 제안 진입점.

### Fixed
- knot `save` verb가 inbox 파일을 커밋(save↔ingest 갭). vault 게이트 env→포인터파일 fallback
  (GUI 호스트앱 진입장벽 제거). agy 능동 스킬을 플러그인 최상위로 승격(네이티브 로드).

## [2.0.0] - 미배포 (PR 머지 시 태깅)

**Breaking**: 배포 방식을 "clone → 루트 파일 그대로 사용"에서 **생성기 + 플러그인**으로
전환. 이제 repo는 시스템 그 자체가 아니라 시스템을 만들어 주는 도구다.

### Changed
- **지침파일 Task Lifecycle에 워커 산출물 경로 명시 (claude/CLAUDE.md, codex·antigravity/AGENTS.md).**
  기존엔 "brief.md/result.md 작성"이라고만 해 경로가 모호 → 오케스트레이터(특히 Gemini)가
  `tasks/<task>/workers/<role>/` 대신 `<role>_brief.md`처럼 평탄화해서 모니터 도구(mat)가
  워커를 못 읽는 문제. 5·6단계를 `tasks/<task>/workers/<role>/{brief,result}.md`로 못박고,
  8단계에 완료 시 `task.md status → done` 갱신을 추가. (제미나이 자가진단으로 원인 확인.)
- **플러그인 레이아웃: 루트 → `plugins/multi-agent-starter/` 하위 폴더로 이동.**
  루트는 마켓 카탈로그(`.claude-plugin/marketplace.json` + 신규 `.agents/plugins/marketplace.json`)만
  둔다. Codex가 로컬 마켓에서 플러그인 source가 repo 루트(`"./"`)인 걸 거부하기 때문
  ([openai/codex#17066](https://github.com/openai/codex/issues/17066) — Claude는 허용, Codex는 거부).
  이 구조로 Claude·Codex 양쪽에서 마켓 등록·설치가 동작함을 검증(`codex plugin add` → installed/enabled).
- **generator를 `skills/configure-multiagent/generator/` 안으로 이동(스킬 자기완결).**
  Antigravity(`agy`)는 플러그인 설치 시 인식하는 컴포넌트(skills/agents/…)만 복사하고 임의 폴더
  (`generator/`)는 버린다 → 설치돼도 스킬이 부를 생성기가 없어 동작 불가였음. 스킬 폴더 안에 두면
  스킬과 함께 복사된다. **3호스트 검증 완료**: `agy plugin install <경로>` / `codex plugin add` 모두
  설치 위치에 skill+generator 동거 확인, `tests/run.sh`·`build_zip` 3-flavor 자가검증 PASS.

### Added
- `generator/init.py` — flavor·대상 지정 결정적 생성기 (tasks/·_local/ 보존, dry-run, `--yes`, guard).
- `generator/validate.py` — flavor별 불변식 자가점검 (claude 10 / codex 11 / antigravity 12), `init`이 설치 후 자동 호출.
- `generator/build_zip.py` — 플러그인 없이 쓰는 자립형 ZIP(run.command/run.bat + 한글 README), 재현가능 빌드.
- `generator/templates/{claude,codex,antigravity}/` — 세 flavor 정본 템플릿.
- **Antigravity flavor** — Antigravity(Gemini 3.1 Pro High)를 오케스트레이터로, claude-main·codex-main·codex-critic을 워커로. 멀티모달·긴 문서는 오케스트레이터가 직접(동일 벤더 gemini 워커 없음).
- **연결 어댑터 레이어** (vendor/model-free 하네스의 토대):
  - `_shared/backends.json` — 역할→모델→연결방식(native·mcp·cli·api) 레지스트리(머신 검증되는 단일 진실원).
  - `_shared/adapters/call_worker.sh` — cli/api 디스패처(allowlist·옵션인젝션 방어·결과 envelope JSON·폴백·타임아웃). native/mcp는 오케스트레이터 직접 호출.
  - `_shared/adapters/_run.py` — 결정적 타임아웃 러너(coreutils timeout 부재 시 폴백, 프로세스그룹 TERM→KILL, 초과 시 124).
- gemini 백엔드를 폐기된 프록시에서 **Antigravity CLI `agy`**(gemini-3.1-pro-high)로 이전. API 연결은 슬롯으로 예약.
- `tests/` — 외부·유료 모델 호출 없는 결정적 회귀 테스트(`run.sh`): 3 flavor 생성·update 보존·디스패처 폴백/타임아웃/가드.
- `docs/ACCEPTANCE.md` — 3호스트(claude·codex·antigravity) 수용 체크리스트 + 4층 신뢰모델 + 테스트 시나리오 S1~S10 + 사인오프 표.
- `generator/sync_claude_template.py` — 루트(Claude 정본)에서 `templates/claude` 재생성 + drift 가드.
- `.claude-plugin/marketplace.json`, `.codex-plugin/plugin.json` — Claude Code·Codex 플러그인 매니페스트.
- `skills/configure-multiagent/` — "멀티 에이전트 시스템 구성해줘" front door.
- `LICENSE` — MIT.
- **카파시 4원칙(운영 원칙) 도입** — 3 flavor 지침파일(claude/CLAUDE.md, codex·antigravity/AGENTS.md)에
  "운영 원칙 (Operating Principles)" 섹션(verbatim 차용), `_templates/worker-brief.md`에 워커 번역형
  고정 블록("Worker 행동 규약"). 층별 적용 근거는 각 flavor design-basis(D8/D7/D7)·invariant(INV12/INV11/INV11).
  출처: multica-ai/andrej-karpathy-skills (MIT) — 표기 정본 `NOTICE`(루트 + 3 flavor).

### Changed
- 배포: clone → 플러그인(`/plugins` 마켓플레이스) / ZIP fallback.
- 루트 문서(README/CHANGELOG/KNOWN_ISSUES)를 repo front-page·패키지 이력으로 분리. 설치된 타깃용 동명 문서는 `templates/` 에 독립 정본으로 둔다.

### Fixed
- 디스패처 타임아웃이 자식 SIGTERM 사망코드(-15)를 반환해 timeout을 error로 오분류하던 버그 — 타임아웃 시 항상 124 반환(`_run.py`, root+템플릿 3벌).

### Note
- 이번 2.0.0은 *배포/패키징* 변경이지 시스템 규칙 변경이 아니다. 설치되는 시스템의 **동작** 버전은 flavor별로 다른 축을 잇는다:
  - `claude` flavor — **1.0.1 라인 계승** (기존 실사용 시스템의 연장; `generator/templates/claude/CHANGELOG.md`).
  - `codex` flavor — **0.1.0 신규 파생** (multi-agent-starter의 Codex orchestrator 버전; `generator/templates/codex/CHANGELOG.md`).
  - `antigravity` flavor — **0.1.0 신규 파생** (Antigravity orchestrator 버전; `generator/templates/antigravity/CHANGELOG.md`).

---

> 아래 1.0.x는 generator 전환 이전, **repo가 곧 시스템**이던 시기의 릴리스 이력이다.
> 설치 시스템 동작 이력은 이후 템플릿 CHANGELOG에서 이어진다.

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

[2.1.1]: https://github.com/netwaif/multi-agent-starter/releases/tag/v2.1.1
[2.1.0]: https://github.com/netwaif/multi-agent-starter/releases/tag/v2.1.0
[2.0.0]: https://github.com/netwaif/multi-agent-starter/releases/tag/v2.0.0
[1.0.1]: https://github.com/netwaif/multi-agent-starter/releases/tag/v1.0.1
[1.0.0]: https://github.com/netwaif/multi-agent-starter/releases/tag/v1.0.0
