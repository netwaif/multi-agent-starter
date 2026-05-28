# System Invariants — 시스템 수정 후 자가 점검

> **로드 정책**: 평소 미로드. 시스템 파일 수정·검증 작업일 때만 (`orchestrator-rules.md` §2).
> 목적: 시스템 변경 후 **전면 멀티에이전트 재감사 대신** 이 점검만 돌려 모순 재발을 잡는다.
> 통과해야 커밋. 깨지면 고치거나, 의도된 변경이면 `design-basis.md` 결정(D*)·이 표를 함께 갱신.

## 불변식 목록

| ID | 불변식 | 깨지면 |
|---|---|---|
| INV1 | `write_scope` 값 집합이 CLAUDE.md(정의처)·routing.md·_templates/worker-brief.md·task-folder.md·매뉴얼에서 동일 (`none`/`tasks-only`/패턴) | D1 위반 — 어디든 한 곳만 다르면 시스템 자체 모순 |
| INV2 | codex-critic 선행조건에 "claude-main result.md 존재 필수" 같은 **전용 강제** 표현 없음 (일반화 표현이어야) | D2 위반 |
| INV3 | log 태그 = 정확히 `DECISION\|WORKER_CALL\|VERIFICATION\|ERROR\|APPROVAL\|COMPLETE` 6종 (_templates/log.md, 매뉴얼) | 파서·일관성 깨짐 |
| INV4 | context.md 한도 1500자, brief 한도 1200자 수치가 CLAUDE.md·매뉴얼·_templates 헤더에서 동일 | 한도 불일치 |
| INV5 | 외부 매뉴얼 메인 섹션 개수 == manual-repo `CLAUDE.md`의 메인 섹션 목록 개수 | 매뉴얼↔manual-repo 빌드 스펙 불일치 (현재 R3 미해소 시 의도적 FAIL) |
| INV6 | 매뉴얼 `workers_approved` 예시 스키마가 approval-policy.md와 일치 (`worker:`/date-only/`purpose:`/`approved_by:`, `HH:MM` 없음) | B1/B6 재발 |
| INV7 | 권위 우선순위 문구가 매뉴얼 §3과 design-basis.md §2에서 동일 (CLAUDE.md > routing/approval/orchestrator-rules > 매뉴얼) | Clash 해소 규칙 붕괴 |
| INV8 | 인터랙티브 전용 + worktree/백그라운드 세션 금지 규칙이 orchestrator-rules.md와 매뉴얼에 모두 존재 | D5 위반 |
| INV9 | gemini 브리지가 routing.md·task-folder.md·design-basis.md D4에서 `mcp__gemini-agy__*`(Antigravity CLI 기반)로 일치하고, **model 파라미터 없음(모델 agy CLI 고정)**이 명시됨. per-call 모델 선택(`model: gemini-3-flash`/`기본 모델 pro-low`)이 정본에 없음 | 정본이 실재하지 않는 model 파라미터를 안내 → 혼선·실패 (D4 위반) |
| INV10 | 폐기 브리지의 **호출형** `mcp__gemini__gemini_*` 및 `mcp__gemini-pro__gemini_*`(prompt/vision 등)가 routing.md·task-folder.md·CLAUDE.md에 없음. 두 폐기 브리지(`mcp__gemini__*`·`mcp__gemini-pro__*`) 잔여 언급은 **폐기 안내 문맥에서만** (호출 명령·예시·「또는」 선택지로 등장 금지). 살아있는 호출형은 `mcp__gemini-agy__*`만 | C2/C3 재발 — 폐기 브리지 잔존 호출 참조가 즉시 실패 (D4 위반) |

## 자가 점검 스크립트

`~/VSCodeWorkspace/MultiAgent`에서 실행. MANUAL은 외부 매뉴얼 경로.

```bash
ROOT=~/VSCodeWorkspace/MultiAgent
MANUAL=~/VSCodeWorkspace/multi-agent-manual/multi-agent-manual.txt

echo "INV1 tasks-only 분포 (CLAUDE/routing/templates/매뉴얼 모두 존재해야)"
grep -l 'tasks-only' "$ROOT/CLAUDE.md" "$ROOT/_shared/routing.md" \
  "$ROOT/_templates/worker-brief.md" "$ROOT/_templates/task-folder.md" "$MANUAL"

echo "INV2 codex-critic 전용 강제 표현 (출력 없어야 PASS)"
grep -n 'result.md. 존재 필수\|claude-main 결과 필요 → 항상 후행' "$ROOT/_shared/routing.md"

echo "INV3 log 태그 (_templates/log.md 에 6종 정의 라인 확인)"
grep -n 'DECISION | WORKER_CALL | VERIFICATION | ERROR | APPROVAL | COMPLETE' "$ROOT/_templates/log.md"

echo "INV4 한도 수치 (1500 / 1200 각 파일)"
grep -rn '1500자\|1200자' "$ROOT/CLAUDE.md" "$MANUAL" "$ROOT/_templates/context.md" "$ROOT/_templates/worker-brief.md"

echo "INV5 매뉴얼 섹션 수 vs manual-repo CLAUDE.md 목록 수 (두 숫자 같아야; design-basis 현재값=10)"
grep -nE '^[0-9]{1,2}\. ' "$MANUAL" | grep -viE 'brief에|task.md의|log.md에'   # 4조건 번호목록 제외 → 메인 섹션만
grep -cE '^[0-9]{1,2}\. ' ~/VSCodeWorkspace/multi-agent-manual/CLAUDE.md

echo "INV6 workers_approved HH:MM 잔존 (출력 없어야 PASS)"
grep -n 'approved_at: <YYYY-MM-DD HH:MM>' "$MANUAL"

echo "INV7 권위 우선순위 문구 (manual + design-basis 둘 다 나와야)"
grep -liE '권위 우선순위|CLAUDE.md가 가장 높|문서가 충돌' "$MANUAL" "$ROOT/_shared/design-basis.md"

echo "INV8 인터랙티브/worktree 금지 (두 파일 모두 나와야)"
grep -lin 'worktree\|배경\|백그라운드\|background session' "$ROOT/_shared/orchestrator-rules.md" "$MANUAL"

echo "INV9 gemini 브리지 = gemini-agy + model 파라미터 없음 (routing/task-folder/D4 일치해야)"
grep -n 'mcp__gemini-agy__' "$ROOT/_shared/routing.md" "$ROOT/_templates/task-folder.md" "$ROOT/_shared/design-basis.md"
grep -n 'model 파라미터 없음\|model 파라미터·' "$ROOT/_shared/routing.md" "$ROOT/_templates/task-folder.md" "$ROOT/_shared/design-basis.md"
echo "INV9b 폐기된 per-call 모델 선택 잔존 (출력 없어야 PASS)"
grep -n 'model: gemini-3-flash\|기본 모델 .*pro-low\|기본 모델 `gemini-3.1-pro-low`' "$ROOT/_shared/routing.md" "$ROOT/_templates/task-folder.md"

echo "INV10 폐기 브리지 호출형 mcp__gemini__gemini_* / mcp__gemini-pro__gemini_* (출력 없어야 PASS)"
grep -rn 'mcp__gemini__gemini_\|mcp__gemini-pro__gemini_' "$ROOT/_shared/routing.md" "$ROOT/_templates/task-folder.md" "$ROOT/CLAUDE.md"
echo "INV10b mcp__gemini__* / mcp__gemini-pro__* 잔여 언급 — 전부 '폐기' 안내 문맥이어야 (호출·예시·「또는」 선택지면 FAIL)"
grep -rn 'mcp__gemini__\|mcp__gemini-pro__' "$ROOT/_shared/routing.md" "$ROOT/_templates/task-folder.md" "$ROOT/CLAUDE.md"
```

## 전면 재감사가 필요한 경우 (이 점검으로 부족)

- 새 외부 개념·레퍼런스를 시스템에 도입할 때 (개념↔규칙 매핑 자체가 바뀜)
- worker pool 구성·역할이 바뀔 때
- 위 불변식으로 표현 불가한 구조 변경
→ 그때만 `tasks/<new>/`로 새 점검 작업 + 필요 시 codex-critic/gemini. 그 외 일반 수정은 이 스크립트로 충분.
