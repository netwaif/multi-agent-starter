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

## [2026-05-25] [autokakao-dup-guard]
**교훈**: 안전장치 코드의 codex-critic 비평을 반영할 때, Orchestrator가 비평을 **직접 재현 검증**하면(순수함수=단위테스트로, 구조적 결함=정적 grep/인덱스 비교로) 2차 worker 검수 호출 없이도 루프를 신뢰성 있게 종료할 수 있다 — 비평 맹신·맹기각 둘 다 회피. 이번엔 #3(정규화 충돌 `verify_room('스터디 2','스터디')=True`)을 단위로, #2(제목 후보 수집범위=메인창 전체→거짓양성)·#1(Enter가 포커스검증보다 먼저)을 정적으로 재현해 진성임을 확정하고, v2도 같은 방식으로 재검증(9케이스+정적 8항목 PASS) 후 사용자가 2차 검수 대신 수락. 더불어 안전장치는 **미확정 의존성(여기선 열린 방 헤더 AX 위치)을 파라미터+TODO로 외부화하고 미설정 기본값을 fail-closed**(전부 거부)로 두면, 라이브 검증 전 단계에서 절대 오발송이 안 나는 안전한 중간 산출물이 된다.
**근거**: codex High 3건이 모두 진성이었고 Orchestrator 재현으로 확정. read_open_room_title이 expected와 일치하는 후보를 메인창 어디서든 신뢰하던 v1은 "거짓 음성 방향" 주장과 달리 거짓 양성(오발송) 경로였음 — worker 자기평가도 never-trust-upstream로 교차검증해야 함. v2는 HEADER_* 미설정=항상 None=fail-closed로 안전하게 게이트.
**worker**: claude-main(구현·v2 반영), codex-critic(High3 비평), orchestrator(비평 직접 재현검증·fail-closed 수락 판단)

## [2026-05-25] [autokakao-jobs-demo]
**교훈**: 외부 GUI 자동화에서 "설계 단계의 가정"은 **라이브 테스트 전까지 미검증**으로 취급하라. 동명이인 안전장치를 브레인스토밍 때 전략 A(열린 방 헤더 제목 읽기)로 골랐지만, 라이브 probe 결과 KakaoTalk이 단일 창이라 헤더가 구분 가능한 AX 요소로 노출되지 않아 A는 원천 불가였다. 진짜 해법은 라이브 probe가 알려줬다 — ⌘F 검색 결과 셀(AXCell)의 `AXSelected`로 하이라이트를 읽어, room_title과 정확 일치하는 결과가 선택될 때까지 ↓ 후 Enter(전략 B). "첫 결과 ↓1회+Enter"는 '테스트' 검색이 '테스트1234'를 먼저 열어 오발송함을 라이브로 실증. 즉 GUI 자동화는 (1) 설계 가정에 과투자 말고 빨리 라이브 probe로 실제 AX 구조를 확인하고, (2) 안전장치는 '열고 나서 검증'(abort만 가능)보다 '정확한 대상을 애초에 선택'(B)이 더 강하다.
**근거**: 헤더 probe가 메인창 단일 창만 찾고(별도 창 없음) 열린 방 제목을 단일 요소로 못 줌. 반면 검색결과 probe에서 ↓1=테스트1234 selected, ↓2=테스트 selected가 깔끔히 노출돼 전략 B가 바로 구현됨. staging→--send 2/2 성공.
**worker**: orchestrator(라이브 probe·전략 전환·전략 B 구현), gemini(영수증·회의록 비전 정리)

## [2026-06-01] [harness-vup-reentry]
**교훈**: 외부 레퍼런스(harness)를 시스템에 도입하는 v-up에서, 6패턴을 통째로 받지 말고 **이 시스템 불변식으로 환원되는 것만 흡수하고 충돌하는 것은 "배제 근거를 design-basis(D6)에 명문화"**하는 방식이 정체성을 지킨다 — Pipeline/Fan-out·in/Expert Pool/Producer-Reviewer는 흡수(대부분 기존 암묵 구현, Fan-in 충돌해소만 신규), Supervisor·Hierarchical은 단일 orchestrator·worker간 무통신·file-as-memory와 충돌해 배제. codex-critic adversarial 리뷰가 진성 결함 2건(치명)을 잡음: ①재진입 분기를 result.md 유무로만 판단하면 status=waiting_<role>·늦은 응답·status↔log 불일치·외부 write_scope 재승인을 놓침 → 재정박에 brief+status 추가·분기 확장으로 해소, ②신설 불변식(INV11)의 grep이 `grep -lin`이라 "둘 중 하나만 맞아도 통과" → per-file `grep -q`+4패턴 positive+배제 negative check로 자동 FAIL 판정 가능하게 교정. 배제 근거 문구도 "Supervisor 개념 배제"가 아니라 "기존 orchestrator 위에 별도 long-lived 조정자/재귀 위임 **계층 추가**를 배제"로 정밀화해야 정확(orchestrator 자신이 이미 중앙 조정자이므로).
**근거**: orchestrator가 critic ISSUE 6건을 사실검증(never-trust-upstream을 리뷰어에도 적용) → #3만 PASS, 5건 진성 → 전부 반영. 자가점검 INV11a/b/c 신규 PASS, INV1~10 회귀 없음. 새 상시로드 비용은 CLAUDE.md 1줄 포인터뿐, 본문은 orchestrator-rules(온디맨드)·routing(라우팅시)·design-basis/invariants(게이트)에 배치.
**worker**: orchestrator(흡수/배제 설계·라이브 파일 편집·ISSUE 사실검증·자가점검), codex-critic(변경안 adversarial 리뷰 5 ISSUE)

## [2026-06-01] [model-policy-cleanup]
문서 일관성 변경(예: 모델 버전 문자열 → 별칭화)은 "정책 섹션"만 고치면 안 된다. 같은 식별자가 워커 상세·비용 설명·예시 등 여러 위치에 흩어져 있어, 한 곳만 바꾸면 같은 파일 안에서 정책↔본문이 모순된다. codex-critic이 routing.md의 잔존 핀(:62 claude-opus-4-7, :65 Opus 4.7, :120 gpt-5.4-mini)을 잡았다. → 표기 정책을 바꿀 땐 `grep`으로 그 식별자의 전 등장 위치를 먼저 훑고 일괄 처리할 것. 또한 "결정적/영속" 같은 단정어는 환경 설정(config·env·profile)으로 바뀔 수 있는 값엔 과장이므로 피한다.

## [2026-06-02] [gemini-backend-agy]
"pro-high 쓰지 마라"(D4/INV9) 같은 **환경 한계발 금지 규칙**은 그 환경(백엔드)이 바뀌면 근거가 사라진다. pro-high 제외 사유는 옛 antigravity-claude-proxy의 `400 INVALID_ARGUMENT`였는데, 백엔드를 `agy` CLI로 바꾸니 pro-high가 정상 작동(spike 실증). → 금지 규칙엔 **"무엇 때문에 금지인지(원인 계층)"를 함께 적어야**, 원인이 사라졌을 때 안전하게 해제할 수 있다. 또 모델 셀렉션이 도구마다 다름을 확인: agy는 모델이 **전역·계정단위**(`/model`)라 per-call 핀 불가 → worker별 다른 모델 동시 사용은 안 되고, gemini 전용 전역을 pro-high로 고정해 운용. 마이그레이션은 D4·INV9·INV10·routing·validate C6를 **한 묶음으로** 갱신해야 내부 모순(validate가 새 정본을 FAIL)이 안 생긴다.
**근거**: agy spike S1 GREEN + 3자 검수(codex #8이 "옛 정책과 충돌" 지적 → 검증하니 정책을 갱신해야 하는 것이었음). backends.json이 gemini 호출 정본, mcp__gemini-pro__/mcp__gemini__ 브리지 폐기.
**worker**: orchestrator(마이그레이션·라이브 편집), codex-critic+gemini=agy(검수)

## [2026-06-14] [agy-skill-discovery]
**교훈**: agy(Antigravity CLI)의 스킬 디스커버리는 **글로벌 플러그인 경로(`~/.gemini/config/plugins/<plugin>/skills/<name>/SKILL.md`)의 최상위 스킬만** 가용 목록(`<skills>`)에 주입한다. **워크스페이스-로컬 `.{flavor}/skills/`는 스캔하지 않는다.** 또 스킬로 인식되려면 `skills/<name>/SKILL.md` **최상위 폴더**여야 한다 — 다른 스킬 하위에 중첩된 SKILL.md(`configure-multiagent/generator/knot-skill/SKILL.md`)는 파일이 따라가도 별도 스킬로 등록 안 됨. 그래서 generator가 knot을 워크스페이스에 바이트복사하던 옛 방식은 claude/codex에선 됐지만(워크스페이스 스킬 스캔 지원) agy에선 **죽은 파일**이었다. 수정: knot을 플러그인 최상위 스킬 `skills/knot/`로 승격 → 3개 도구 모두 네이티브 로드(워크스페이스 복사·C11 결합불변식 폐기, opt-in `--with-knot`은 passive 관리블록만). claude/codex도 플러그인 스킬로 동일 로드되므로 워크스페이스 복사는 애초에 중복이었다.
**디버깅 방법론 교훈(값진 실패)**: ① 가설의 *substance*(agy=글로벌 로드)는 맞았으나 *경로*를 틀리게 봄(`~/.agents/skills/` ≠ 실제 `~/.gemini/config/plugins/`) → 정황증거로 결론 단정 말고 **실측으로 경로까지 확정**해야. ② **테스트 방식 자체가 틀리면 결론도 틀린다** — headless `agy -p` 단발 호출은 인증 불안정("not logged into Antigravity")·실행간 동작 불일치를 일으켜 오판을 키웠다. 결정타는 **agy 대화형 세션을 띄우고 gemini에게 "네 가용 스킬 목록 보여줘"라고 직접 물어본 것**("자기 시스템이니 그 정도는 안다"). 에이전트 자기보고 > 외부 추론. ③ 우회책(AGENTS.md 포인터)으로 빠지려 했으나, 사용자가 "configure-multiagent는 antigravity에서 되는데?"라는 반례로 정본 메커니즘(플러그인 스킬)을 가리켜줌 — **작동하는 예와 안 되는 예의 차이를 먼저 규명**하는 게 우회보다 빠르다.
**근거**: live agy 세션에서 글로벌 경로에 knot 설치 후 Gemini 3.1 Pro가 `<skills>` 목록에 `configure-multiagent` + `knot` 둘 다 나열·확인. test_generate(3 flavor 관리블록 주입·멱등·기본부재) + run.sh ALL PASS. D9 갱신, C11 폐기.
**worker**: orchestrator(systematic-debugging·라이브 agy probe·repo 리팩터·테스트)

## [2026-06-24] 컷오프 이후 기능·경쟁자 주장은 1차 출처로 검증 (youtube-topic-2026-06-24)
**교훈**: 영상 주제선정 중 두 번 "내 추론·2차 요약"이 틀릴 뻔함 → 둘 다 1차 출처로 잡음. ① **컷오프 이후 기능(`/goal`·Stop hook)은 공식 문서로 확인.** 메모리·노트북 요약으로 단정하니 "평가자 무조건 Haiku"(→설정가능)·"이미지 못 봄"(→문서에 없는 추론) 같은 과장이 나옴. 사용자가 "문서로 다 확인된거?"로 압박 → 재fetch해 정정. ② **경쟁 영상 주장은 yt-dlp로 자막 받아 직접 정독 > NotebookLM 요약(2차).** 세션1 노트북이 "개발동생=Loop Engineering 점유"라 기록했으나, 채널 직접 확인하니 그 제목은 Austin Marchese(해외)였고 개발동생 실제 영상은 다른 것. 자막 정독으로 경쟁 지형·인용문까지 정확히 확보.
**근거**: WebFetch(code.claude.com/docs/en/goal) 원문 인용으로 평가자 사실 3건 정정. yt-dlp 자막 정독으로 Berman(F4a8aMLb678)·개발동생(QI1FNnUfiZg) 메커니즘·요금 미점유 직접 확인. 추론→문서/1차 전환 후 차별화 근거가 "추론"에서 "문서·실측"으로 단단해짐.
**worker**: orchestrator(WebFetch·yt-dlp 자막·헤드리스 claude -p /goal 실측)

## [2026-07-03] 워커 코드 산출물은 JSONL에서 추출·검증 (subway-runner-game)
**교훈**: claude-main worker가 큰 코드(HTML 700+줄)를 텍스트로 반환할 때, 응답 본문에 **정체불명 오타 토큰**이 섞일 수 있다(실측: `background: ...#ffb game 300...`, `color: 0xffc górze` — 둘 다 로드 깨짐). 워커가 Issues에 정직하게 자기신고했다(brief의 "불확실·불일치는 result에 표면화" 규약 작동). 대응 원칙: ① 700줄을 **손으로 옮기지 말 것**(전사 중 오타 재유입). agent output JSONL(`tasks/<id>.output`)에서 python으로 assistant text→코드블록 추출→`html.unescape`(필요시)→치환 수정→파일 저장. 컨텍스트에 덤프 안 함(오버플로 방지). ② 저장 전 **기계 검증**: 알려진 garbage 토큰 부재 assert + `{}`/`()` 균형 + 기대 기능 키워드 grep + `node --check`. ③ 재호출(반영 라운드) 산출물도 같은 파이프라인 — 2차엔 오타 0이었으나 검증은 매번. 
**imagegen 교훈**: codex imagegen의 "seamless/tileable"은 신뢰 불가 — gemini 검수가 track.png 경계 불연속(크랙·얼룩 패턴)을 잡음. 대응: 큰 랜드마크 얼룩 대신 **균질 미세패턴**으로 재생성 요청 + 인엔진 완화(중앙 주행레인은 다크 스트립 오버레이가 덮어 텍스처 이음매를 가림). 완벽 seamless가 필요하면 imagegen 단독으론 부족.
**검증 환경 교훈**: Playwright MCP는 `file://` 차단 → `python3 -m http.server`로 서빙 후 `http://localhost`. macOS엔 `timeout` 없음(gtimeout 또는 그냥 bg). 게임류 검증은 스크린샷 + `browser_evaluate`로 상태(점수 라이브 증가·게임오버·grace 생존)를 **프로그램적으로 단언** — 스크린샷만으론 로직 미검증.
**worker**: codex-main(imagegen×2)·claude-main(구현+반영)·codex-critic(리뷰)·gemini(이미지 검수). Producer→Reviewer→반영→재검증 파이프라인 완주.
**검증 false-pass 교훈(중요)**: 위 Playwright http 검증은 텍스처가 "적용됨"으로 PASS를 냈으나, 사용자는 `file://`(더블클릭)로 열어 **전부 단색 폴백**이었다. WebGL은 `file://`에서 로컬 이미지를 텍스처로 로드하는 걸 CORS로 차단하는데, http 서빙은 이를 우회하므로 **검증 환경(http)이 실제 사용 환경(file://)과 달라 결함을 못 잡았다.** 원칙: ① "단일 HTML" 산출물은 **실제 배포/사용 방식으로 검증**하라(더블클릭이면 file://). ② 진짜 자체완결 단일 파일이 목표면 에셋을 **base64 data URI로 임베드**(프로토콜 독립·CORS 무관·오프라인 동작). 외부 `assets/*.png` 참조는 http 서버 전제라 "단일 파일"의 이점을 깬다. 폴백 색상 로직은 결함을 조용히 감춰 오진을 키운다 — 폴백이 있어도 "의도한 에셋이 실제로 떴는지"를 별도 단언하라.

## agy(gemini worker) 헤드리스 호출 — CLI 버전업으로 플래그 조용히 사망 (2026-07-03, 심판 세션 정정)
- **근본 원인**: agy 1.0.16에서 `-p` 단축 플래그가 **제거**됨(1.0.13엔 있었음). 미인식 플래그라 프롬프트가 조용히 무시 → 온보딩 인사만 반환, 모델 호출 0·사용량 0. 디스패처 정본(backends.json)도 `-p`라서 같이 죽어 있었음 → `--prompt`로 교정(2026-07-03).
- **오진 정정**: 당시 세션이 "등호(`--prompt=`) 필수"로 기록했으나 실측상 **공백형 `--prompt "..."`도 정상**(등호/공백 무관, `-p`가 죽은 것). 또한 `--dangerously-skip-permissions`·`--add-dir` 권장은 **routing.md 금지 사항**(auto-mode classifier 차단·stdin hang 원인) — 손 호출 말고 `call_worker.sh gemini <brief>` 정본 경로를 쓸 것.
- **일반 교훈**: 외부 CLI 백엔드는 버전업으로 플래그가 소리 없이 부러진다. ① 증상="응답은 오는데 내용 무관/사용량 0"이면 프롬프트 미전달 의심 → `--help`에서 플래그 존재부터 확인. ② 워커 백엔드 이상 시 스모크는 정본 경로(`call_worker.sh`)로 1회 — 손 호출로 우회 진단하면 정본이 죽은 걸 놓친다.
- `-i`(interactive)는 /dev/tty 필요 → 헤드리스 불가. 모델명은 `agy models`의 정확한 라벨.

## gemini(agy) 워커 — 다중파일 헤드리스 순회 타임아웃 + API 폴백 키 부재 (2026-07-04, dayjs-bughunt)
- **증상**: gemini worker에 "디렉토리 절대경로 + 파일 10개 정독" brief를 주자 agy CLI가 **300s 타임아웃**(exit 124, envelope status=timeout). 이어 api 폴백도 `필수 env 없음: GEMINI_API_KEY`로 즉사 → **gemini worker 전체 불가**. (2026-07-03 `-p` 플래그 이슈와 별개 — 이번엔 `--prompt` 정본이라 온보딩이 아니라 순수 타임아웃.)
- **진단**: agy는 `cwd_policy: isolated_tmp`에서 돌며 brief 본문의 절대경로 파일을 연다. 이미지/PDF 1건(≈26s)은 정상이지만, **소스 디렉토리 순회 + 다수 파일 열람은 300s 안에 못 끝냄**(헤드리스 auto-mode에서 파일 다수 접근이 느림/행).
- **효과 있던 우회(정본화 권장)**: brief를 **자체 완결형**으로 재작성 — 관련 코드 스니펫을 brief 본문에 **인라인**하고 "파일 열지 말 것" 명시 → **27s exit 0, 정상 판정 반환.** 즉 gemini에 발굴·리뷰를 시킬 땐 **디렉토리를 가리키지 말고 필요한 소스를 orchestrator가 inline**하라(FS-미접근 모델 원칙 [gemini FS 미접근]과 동일 선상).
- **고쳐야 할 것(harness)**: ① `GEMINI_API_KEY` 미설정 시 agy 타임아웃 → 폴백까지 동반 실패로 **gemini 완전 상실**. 키를 설정하거나, 폴백 부재를 조기 감지해 orchestrator에 경고. ② gemini 다중파일 작업은 backends.json timeout(300) 상향 또는 청크·인라인 강제. ③ 시간 제한 대결에선 **의존 전에 경량 스모크 1회**로 가용성 확인(안 그러면 발굴 단계에서 통째로 날림).
- **대결 영향(공정성 메모)**: 이번 seg2-bughunt B측(하네스)은 gemini를 **발굴에 못 쓰고 후반 리뷰 1패스만** 사용 — 3모델 균등 대비 핸디캡. A측(fable5-solo)과의 자원·성능 비교 해석 시 이 제약을 반영하고, **재실험 전 위 ①~③ 수정 권장.**
**worker**: orchestrator(agy 타임아웃 진단·자체완결 brief 우회·교차검증)

## codex worker — 서버 구성 롤아웃 × CLI 회귀로 도구 호출 전멸 (2026-07-09, codex-toolcall-unsupported)
- **증상**: standalone codex(tui/exec/MCP 전부)에서 GPT의 shell 도구 호출이 전부 `unsupported call: exec_command`로 거부. 사용자 config·훅·shim 아무것도 안 바꿨는데 어느 날 아침부터 발생.
- **근본 원인**: OpenAI 서버가 계정에 multi_agent v2 도구 구성(comp_hash 2911→3000)을 롤아웃 + codex 0.143.0의 "multi-agent v2 도구 재정리" 회귀가 겹침. 같은 바이너리가 v1 구성에선 정상, Desktop 0.142.5는 v2 구성도 정상 → 조합 버그.
- **진단 정본 절차**: ① `~/.codex/sessions/<날짜>/rollout-*.jsonl`에서 function_call/function_call_output으로 실제 에러 문자열 확보 → ② 세션 전수 진실표(originator·cli_version·turn_context의 comp_hash·multi_agent_version × 에러 유무)로 상관관계 특정 → ③ 정상↔에러 세션 turn_context 필드 diff. **"어느 날 갑자기"는 로컬 변경 없이도 서버 플래그 롤아웃일 수 있다** — comp_hash 변화가 그 지문.
- **워크어라운드**: config.toml `[features] multi_agent_v2 = false`(플래그명은 바이너리 `strings | grep features.`로 발굴) → v1 구성 복귀, 검증 GREEN. **CLI 업데이트 후 플래그 제거+재테스트 필요**(협업 기능 계속 꺼짐).
- **일반 교훈**: 외부 CLI 워커는 버전업뿐 아니라 **서버 측 구성 롤아웃으로도** 소리 없이 부러진다(agy `-p` 교훈의 서버판). 워커 이상 시 해당 CLI의 세션/rollout 로그가 1차 증거원 — 재현 호출(쿼터 소모) 전에 로그부터.
**worker**: orchestrator 단독(로그 분석·웹 확인·config 수정·검증 codex exec 1회)

## codex-critic — MCP 서버 stale로 신모델 400, codex exec 헤드리스 폴백 (2026-07-10, loadout-doctor-codex)
- **증상**: `mcp__codex__codex` 호출이 `The 'gpt-5.6-terra' model requires a newer version of Codex`(400). CLI는 0.144.0으로 최신인데 MCP 경유만 실패 — MCP 서버 프로세스가 세션 시작 시점의 구버전 바이너리로 떠 있는 stale 문제. `model` 파라미터로 다른 모델 지정도 ChatGPT 계정 제약으로 거부될 수 있음.
- **폴백 정본**: `codex exec --sandbox read-only "$(cat brief.md)"` 헤드리스 — cwd를 target_repo로, 출력은 파일로 리다이렉트(`> raw-output.txt`) 후 결론부만 읽기(전체 트랜스크립트가 수만 토큰). read-only 강제라 critic 규약(쓰기 금지)도 유지됨. 백그라운드 실행 + 완료 알림으로 대기.
- **일반 교훈**: MCP 도구가 모델 버전 에러를 내면 CLI 직접 호출과 버전을 대조하라 — 같은 바이너리라도 long-lived MCP 서버는 재시작 전까지 구버전. codex MCP 실패 ≠ codex 불능.
**worker**: codex-critic(codex exec 폴백, read-only) 1회

## 집행층 코드화 — 산문 규칙을 스크립트로 옮길 때의 함정 (2026-09-06, harness-enforcement-v3.6)
- **리뷰어 2패스가 실질적**: astra(gpt-6-astra) 설계 리뷰 11건 → 구현 리뷰 9건. 2차의 절반이 "1차 지적 부분 반영"(fallback 경로 누락·env 우회 잔존·로그 연결 미흡). **설계 지적을 반영했다고 끝이 아니라 구현 diff를 같은 리뷰어에게 다시 보여야** 반쪽 반영이 드러난다. 스레드 이어쓰기(codex-reply)로 맥락 유지.
- **bash 집행기 함정 3종**: ① `grep -F "$ROLE"`은 부분일치 — role `w`가 `write_scope`에 매칭. 단어경계 정규식 필수. ② macOS BSD grep은 `-z`+`-f` 조합이 깨짐(byte-identical 파일도 차이로 보고) → NUL 레코드 대신 hex 인코딩 한 줄 형식. ③ `sed -E 's/x=([^ ]*)/'` 파싱은 공백 경로에서 잘림 → 구조화 출력(`--json`)으로 경계 보존.
- **fail-closed의 빈틈은 "실패 경로"에 있다**: primary만 막고 fallback을 안 막으면 성공한 fallback이 위반을 덮는다. 스냅샷 실패를 빈 스냅샷으로 취급하면 "변경 없음"으로 통과한다. 게이트를 넣을 때 정상 경로보다 **에러·폴백·빈 입력 경로**를 먼저 fixture로 잡을 것.
- **게이트는 오케스트레이터 자신에게도 걸린다**: 2차 리뷰 brief(1356자·241단어)를 gate.sh가 거부 → 줄여서 통과. 규칙이 코드가 되면 "이번만 예외"가 사라진다 — 그게 목적.
- **문자열 존재 검사는 배선 검사가 아니다**: INV14를 `grep 'gate.sh'`로 하면 헤더 주석만 남아도 통과. 비주석 줄의 실제 호출 패턴을 검사하고, self-test는 **호출 줄만 제거**하는 변이로 검증.
**worker**: codex-critic(astra) 2회(MCP, read-only) · orchestrator 구현
