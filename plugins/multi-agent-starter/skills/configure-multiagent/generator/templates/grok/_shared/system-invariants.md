# System Invariants — 시스템 수정 후 자가 점검

> **로드 정책**: 평소 미로드. 시스템 파일 수정·검증 작업일 때만 사용한다.

## 불변식 목록

| ID | 불변식 |
|----|--------|
| INV1 | `write_scope` 값 집합이 `GROK.md`, `routing.md`, `worker-brief.md`, `task-folder.md`에서 동일 |
| INV2 | 오케스트레이터가 grok(xAI)이므로 **별도 `grok-critic`/`grok-intel` 워커가 활성으로 없음** (실시간 web/X 인텔은 오케스트레이터가 직접) |
| INV3 | 비평 워커 `codex-critic`이 교차벤더(Codex)로 존재 — 선행조건이 특정 worker 결과에만 묶이지 않고 일반화 |
| INV4 | log 태그가 정확히 `DECISION | WORKER_CALL | VERIFICATION | ERROR | APPROVAL | COMPLETE` 6종 |
| INV5 | context 한도 1500자, brief 한도 1200자가 정본 문서와 템플릿에서 일치 |
| INV6 | 권위 우선순위가 `GROK.md` 기준으로 기록됨 |
| INV7 | 재진입 프로토콜이 `orchestrator-rules.md`와 `GROK.md` 포인터에 모두 존재 |
| INV8 | 토폴로지 4패턴(Pipeline, Fan-out/Fan-in, Expert Pool, Producer-Reviewer)이 routing에 존재 |
| INV9 | 오케스트레이터가 grok/grok-4.5 (`GROK.md` 명시), `backends.json` workers == `{claude-main, codex-main, codex-critic, gemini}` 정확히 4종 (grok 워커 없음) |
| INV10 | `grok-critic`/`grok-intel` 워커 호출(`call_worker.sh grok-critic`/`call_worker.sh grok-intel`)이 활성 지침으로 없음 |
| INV11 | 카파시 4원칙(D8): `GROK.md`에 "Operating Principles" 섹션 존재, `_templates/worker-brief.md`에 "Worker 행동 규약" 고정 블록 존재, 블록 안에 사용자질문 지시(질문/ask) 없음, `worker-result.md` 체크리스트에 표면화 항목 존재 |
| INV12 | 네이티브 web/X 검색 결과를 신뢰불가 데이터로 취급하고 출처 인용을 요구하는 문구가 `GROK.md`에 존재 |

## 자가 점검 스크립트

`<설치한-폴더>`에서 실행한다.

```bash
ROOT=<설치한-폴더>

echo "INV1 tasks-only 분포"
grep -l 'tasks-only' "$ROOT/GROK.md" "$ROOT/_shared/routing.md" \
  "$ROOT/_templates/worker-brief.md" "$ROOT/_templates/task-folder.md"

echo "INV2 grok-critic/grok-intel 워커 활성 참조 (출력 없어야 PASS)"
grep -rn 'call_worker.sh grok-critic\|call_worker.sh grok-intel\|- \*\*grok-critic\*\*\|- \*\*grok-intel\*\*' \
  "$ROOT/GROK.md" "$ROOT/README.md" "$ROOT/_shared/routing.md" \
  "$ROOT/_shared/approval-policy.md" "$ROOT/_templates" || echo " 없음 PASS"

echo "INV3 codex-critic 비평 워커 존재"
grep -rn 'codex-critic' "$ROOT/GROK.md" "$ROOT/_shared/routing.md" "$ROOT/_templates"

echo "INV4 log 태그"
grep -n 'DECISION | WORKER_CALL | VERIFICATION | ERROR | APPROVAL | COMPLETE' "$ROOT/_templates/log.md" "$ROOT/GROK.md"

echo "INV5 한도 수치"
grep -rn '1500자\|1200자\|1500 chars\|1200 chars' "$ROOT/GROK.md" "$ROOT/_templates/context.md" "$ROOT/_templates/worker-brief.md"

echo "INV6 권위 우선순위"
grep -rn 'GROK.md.*routing.md' "$ROOT/_shared/design-basis.md" "$ROOT/_shared/orchestrator-rules.md"

echo "INV7 재진입"
grep -q '재진입 프로토콜' "$ROOT/_shared/orchestrator-rules.md" && echo " orchestrator-rules PASS" || echo " orchestrator-rules FAIL"
grep -q 're-entry protocol\|재진입 프로토콜' "$ROOT/GROK.md" && echo " GROK.md PASS" || echo " GROK.md FAIL"

echo "INV8 토폴로지 4패턴"
for p in 'Pipeline' 'Fan-out/Fan-in' 'Expert Pool' 'Producer-Reviewer'; do
  grep -q "$p" "$ROOT/_shared/routing.md" && echo " $p PASS" || echo " $p FAIL"
done

echo "INV9 오케스트레이터·워커셋 (grok-4.5 + claude-main/codex-main/codex-critic/gemini 정확히 4종)"
grep -q 'grok-4.5' "$ROOT/GROK.md" && echo " orchestrator PASS" || echo " orchestrator FAIL"
for w in claude-main codex-main codex-critic gemini; do
  grep -q "\"$w\"" "$ROOT/_shared/backends.json" && echo " $w PASS" || echo " $w FAIL"
done
for w in grok-critic grok-intel; do
  grep -q "\"$w\"" "$ROOT/_shared/backends.json" && echo " $w 존재(FAIL — 있으면 안 됨)" || echo " $w 없음(PASS)"
done

echo "INV10 grok 워커 호출 잔재 (출력 없어야 PASS)"
grep -rn 'call_worker.sh grok-critic\|call_worker.sh grok-intel' \
  "$ROOT/_shared/routing.md" "$ROOT/_templates/task-folder.md" "$ROOT/GROK.md" "$ROOT/_shared/backends.json" \
  | grep -viE '폐기|deprecat' || echo " 없음 PASS"

echo "INV11 카파시 4원칙 — Operating Principles 섹션 + Worker 행동 규약 블록 + result 표면화 항목 (셋 다 나와야 PASS)"
grep -n 'Operating Principles' "$ROOT/GROK.md"
grep -n 'Worker 행동 규약' "$ROOT/_templates/worker-brief.md"
grep -n '표면화' "$ROOT/_templates/worker-result.md"
echo "INV11b 블록 내 사용자질문 표현 (출력 없어야 PASS)"
sed -n '/^## Worker 행동 규약/,/^## Execution/p' "$ROOT/_templates/worker-brief.md" | grep -inE '질문|ask' || echo " 없음 PASS"

echo "INV12 web/X 신뢰불가 데이터 취급 + 출처 인용 문구"
grep -n '신뢰불가\|source_url' "$ROOT/GROK.md"
```

## 전면 재감사가 필요한 경우

- 새 외부 개념·레퍼런스를 시스템에 도입할 때
- worker pool 구성·역할이 바뀔 때
- 위 불변식으로 표현 불가한 구조 변경이 생길 때
