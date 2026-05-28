# Shared Learnings

작업 완료 후 재사용 가능한 교훈만 추가. append-only.  
중복·일회성·작업 특화 내용은 기록하지 말 것.

## 분류 규칙 (어디에 적을지)

- **시스템 운영 자체**에 대한, 어떤 작업에든 적용되는 교훈 → **이 파일** (`_shared/learnings.md`, git 추적·공개).
- **특정 외부 프로젝트/repo에 묶인** 교훈(예: mat·hwpx 내부) → **`_local/learnings.md`** (git 추적 안 함·미배포. 없으면 새로 생성. 오케스트레이터는 명시 요청 없이는 로드하지 않음).

## 형식

```
## [YYYY-MM-DD] [작업명]
**교훈**: 한 문장. 다음 작업에 그대로 적용 가능한 형태로.
**근거**: 왜 그런지, 어떤 작업에서 발견했는지.
**worker**: [관련 worker명]
```

---

<!-- 이 아래부터 교훈 추가 -->

## [2026-05-13] [mat-mvp]
**교훈**: orchestrator-cwd가 git이 아니면 Task tool sub-agent 호출에서 worktree 격리가 실패할 수 있다. 다른 git repo를 다룰 때는 그 repo로 `cd` 후 claude를 시작하거나, worktree를 요구하지 않는 일반 에이전트로 폴백.
**근거**: claude-test(비-git) cwd에서 `subagent_type: claude` 호출 시 "Cannot create agent worktree" 에러. `general-purpose`로 재시도하니 격리 없이 성공.
**worker**: claude-main 호출 경로

## [2026-05-14] [mat-mvp]
**교훈**: `task.md`는 ` ```yaml ` 블록을 2개 갖는 게 표준 패턴(메타 + Worker Plan)이다. 어떤 키든 첫 yaml fence만 보는 파서는 깨진다 — 문서 전체의 모든 yaml block을 스캔하도록 작성할 것.
**근거**: mat의 `readPlannedWorkers`가 첫 fence 닫는 ``` 에서 return하는 바람에 `planned_workers`(두 번째 블록)를 못 봤다. codex-critic이 MAJOR로 잡고 fix iter로 수정.
**worker**: codex-critic (지적), claude-main (수정)

## [2026-05-14] [mat-mvp]
**교훈**: 같은 worker의 재호출(fix iter)은 별도 폴더 만들지 말고 같은 worker 폴더 안에서 `brief-fix.md` / `result-fix.md` 명명으로 진행. 1차 산출물·승인 기록을 보존하면서 변경 이력이 시각적으로 드러난다.
**근거**: codex-critic 리뷰 후 claude-main에 MAJOR 2건 패치 재호출 시 적용. `workers_approved`는 그대로 두고 brief/result 한 쌍을 추가하는 것만으로 충분했고 깔끔했다.
**worker**: claude-main (fix iter)

## [2026-05-14] [yt-thumbnail-multiagent]
**교훈**: MultiAgent 작업은 worktree 진입 금지. orchestration 산출물(`tasks/<task>/`)은 gitignore라 worktree에 만들어도 본체로 옮기려면 수동 복사 사족이 생긴다. tracked 시스템 파일도 단순 append/수정에 worktree+commit+merge는 과한 오버헤드.
**근거**: 배경 세션 harness가 자동으로 EnterWorktree를 강제해 task 폴더와 시스템 파일 수정 양쪽에서 `cp -R` 또는 머지 사족이 발생했다. 외부 `target_repo` 쓰기는 codex-main의 cwd로 따로 격리되므로 MultiAgent repo 자체에 워크트리는 불필요. 인터랙티브 세션에서는 EnterWorktree를 자발적으로 호출하지 말 것.
**worker**: orchestrator (세션 초기화 시 EnterWorktree 호출 안 함)

## [2026-05-14] [yt-thumbnail-spring]
**교훈**: log.md는 표준 형식 엄수 — (a) 태그는 정해진 6종(`DECISION | WORKER_CALL | VERIFICATION | ERROR | APPROVAL | COMPLETE`)만 사용, (b) 타임스탬프 `[YYYY-MM-DD HH:MM]`까지 기록, (c) 작업 완료 시 마지막 줄에 `[COMPLETE]` 엔트리 필수.
**근거**: yt-thumbnail-spring log에서 `INIT/BRIEF/CALL/RESULT` 새 태그 사용, HH:MM 누락, [COMPLETE] 부재. mat 같은 도구가 표준 형식 가정하고 파싱하면 일관성 깨짐.
**worker**: orchestrator (로그 작성 규율)

## [2026-05-15] [hwpx-math-final]
**교훈**: codex MCP 호출이 비정상적으로 길어질 때(>2-3분) 첫 의심은 외부 MCP 도구 hang이지 모델·reasoning이 아니다. `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl`의 event timestamp gap을 보면 어느 function_call에서 막혔는지 즉시 식별 가능.
**근거**: 표면 원인(reasoning=high, brief 길이, AGENTS preamble)으로 잘못 짚었다가 사용자 재질문 후 turn timing 분석으로 진단. 탐색·normalize는 50초, hang난 function_call→output 사이가 399초로 명확. session jsonl이 정답지.
**worker**: orchestrator (디버깅 절차)

## [2026-05-15] [hwpx-math-final]
**교훈**: `mcp__codex__codex`의 reject 응답이 codex backend 작업을 중단시키지 않는다. 사용자 거부 후에도 backend는 끝까지 실행되어 파일·부수 효과가 남을 수 있음. 거부한 호출 직후엔 대상 디렉토리 상태를 반드시 확인.
**근거**: reject된 codex MCP 호출 두 건이 backend에서 작업을 계속해 cwd에 산출 파일 생성. orchestrator는 처음에 그 파일들이 어디서 왔는지 추적 못 함. `~/.codex/sessions/` 세션 jsonl로 확인 가능.
**worker**: orchestrator (MCP reject 의미 이해)

## [2026-05-15] [manual-final-review]
**교훈**: `mcp__gemini-pro__*`(로컬 프록시 기반 gemini-pro 브리지)가 `Proxy 400 INVALID_ARGUMENT`를 내면 프롬프트 크기 문제가 아니라 모델 티어 문제일 수 있다 — 압축 재시도로 시간 쓰지 말고 폴백 순서를 `pro-high → pro-low(같은 프록시, 종종 정상) → Flash 브리지`로 단계 강등하라. 어느 경우든 model deviation을 result.md·리포트에 명시한다. gemini는 FS 접근이 없어 brief "경로 참조"가 안 통하므로 필요한 자료는 orchestrator가 MCP prompt에 직접 inline하고 그 사실을 brief·log에 적는다. FS 미접근 모델이 낸 *시스템 사실 주장*은 codex-critic/권위문서로 교차검증 후에만 채택한다(never-trust-upstream — 리뷰어 출력에도 동일 적용).
**근거**: pro-high가 큰/압축 프롬프트 모두 동일 400. Flash는 1회 성공했으나 문서 우선순위를 오추정, 같은 프롬프트로 pro-low는 정상 동작하며 더 날카로운 비평을 냈다(같은 프록시인데 pro-high만 막힘). pro-low조차 매뉴얼 용도(런타임 미적재 사람용 문서)를 오판해 "이론=토큰낭비"라는 틀린 전제로 소절 삭제를 권고 → 사실검증으로 불채택했다.
**worker**: gemini (프록시 장애·FS 미접근), codex-critic (사실 교차검증), orchestrator (폴백 강등·리뷰어 출력 검증)

## [2026-05-19] [repo-consistency-audit]
**교훈**: 다중 repo 일관성 감사에서 claude-main·codex-main을 **추상화 레이어로 분담**시키면(claude-main=의미·규칙 레벨, codex-main=파일·파서·코드 레벨) 같은 입력 중복 호출 대신 상호보완 커버리지가 나온다 — 이번에 codex만 검출(표준 brief→mat 파서가 worker 목적을 ` ```yaml `로 표시)·claude만 검출(manual↔mat 상태 우선순위 순서/단계 불일치)이 각각 진성 크리티컬이었고 둘 다 독립 검출한 항목(gemini 기본 모델 pro-high 충돌)은 신뢰도 최상으로 분류. 병렬 brief에 "다른 worker 결과 미참조" 명시는 codex result checklist에 그대로 확인됨. 또한 claude-main이 초기 가설 2건을 self-retract했어도 orchestrator가 인용 라인을 sources에 **직접 재대조**(never-trust-upstream을 worker 출력에도 적용)해야 false-positive·false-negative 둘 다 막힌다.
**근거**: 단일 worker였으면 크리티컬 3건 중 1건씩 누락. orchestrator 재검증에서 firstMeaningfulLine(task.go:499)·.mcp.json·routing.md:111을 직접 확인해 codex/claude 주장과 retraction을 모두 사실검증 후 취합.
**worker**: claude-main(의미·규칙 레이어), codex-main(파일·파서 레이어), orchestrator(레이어 분담 설계·인용 직접 재대조·취합)

## [2026-05-28] [routing-summary-review]
**교훈**: gemini 브리지를 routing.md 표기만 믿고 호출하지 말 것 — 실제 등록된 MCP 서버(`.mcp.json`)와 라이브 도구 목록·스키마를 먼저 대조한다. 정본 문서와 실제 구현이 어긋날 수 있다(이번엔 문서=`mcp__gemini-pro__*`+model 파라미터, 실제=`mcp__gemini-agy__*`(Antigravity CLI)+model 파라미터 없음). ToolSearch로 도구 스키마의 파라미터 유무까지 확인하면 호출 실패·잘못된 모델 가정을 사전 차단.
**근거**: gemini 호출 시 routing.md의 `mcp__gemini-pro__*`가 환경에 없어 `mcp__gemini-agy__*`로 폴백. agy 도구 4종 전부 model 파라미터가 없어 승인받은 pro-low 지정 불가. `.mcp.json`·`server.mjs` 직접 확인으로 D4 전환 결정. vision/summarize/code는 `file_path`로 agy가 직접 FS 접근(구 "gemini FS 미접근" 가정 일부 폐기).
**worker**: gemini (호출), orchestrator (브리지-문서 불일치 검출·D4 갱신)
