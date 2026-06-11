# System Invariants — 시스템 수정 후 자가 점검

> **로드 정책**: 평소 미로드. 시스템 파일 수정·검증 작업일 때만 사용한다.

## 불변식 목록

| ID | 불변식 |
|----|--------|
| INV1 | `write_scope` 값 집합이 `AGENTS.md`, `routing.md`, `worker-brief.md`, `task-folder.md`에서 동일 |
| INV2 | 오케스트레이터가 Gemini(agy)이므로 **별도 `gemini` 워커·`gemini-critic` 자기검수 워커가 활성으로 없음** (멀티모달은 오케스트레이터가 직접) |
| INV3 | 비평 워커 `codex-critic`이 교차벤더(Codex)로 존재 — 선행조건이 특정 worker 결과에만 묶이지 않고 일반화 |
| INV4 | log 태그가 정확히 `DECISION | WORKER_CALL | VERIFICATION | ERROR | APPROVAL | COMPLETE` 6종 |
| INV5 | context 한도 1500자, brief 한도 1200자가 정본 문서와 템플릿에서 일치 |
| INV6 | 권위 우선순위가 `AGENTS.md` 기준으로 기록됨 |
| INV7 | 재진입 프로토콜이 `orchestrator-rules.md`와 `AGENTS.md` 포인터에 모두 존재 |
| INV8 | 토폴로지 4패턴(Pipeline, Fan-out/Fan-in, Expert Pool, Producer-Reviewer)이 routing에 존재 |
| INV9 | 오케스트레이터가 agy/Gemini 3.1 Pro High (`AGENTS.md` 명시), `backends.json` 역할(roles) = `claude-main`·`codex-main`·`codex-critic` (gemini 워커 없음) |
| INV10 | `gemini` 워커 호출(`call_worker.sh gemini`)·옛 `mcp__gemini-pro__*` 브리지가 활성 지침으로 없음 |
| INV11 | backends.json 2-테이블: `schema_version:"2"` + `providers`(레코드 카탈로그) + `roles`(role→provider+staffing+desk), 폐기 `workers` 키 없음, 모든 `roles[*].provider`가 `providers`에 존재 (`validate.py` C9 자동 강제, D7) |
| INV12 | Phase1 가드(D8): 모든 provider `family`; cli command ∈ `{agy,codex,claude,grok}`(call_worker ≡ validate `_CLI_ALLOWLIST`, C9c 강제); bridge 미승격이면 바인딩 거부·dispatch die(3); staffing(mode∈{auto,fixed}·max≥1·decided_by=orchestrator·auto는 provider `best_of_n` 필수)+class∈{main,aux,reviewer,scout,tool}·`awo_role`∈AWO 9-role(CT 매핑·필수); C10 reviewer resolved family ∉ {orchestrator_family ∪ 모든 main family}(validate+call_worker fail-closed, die9). 위반 시 권한 누수·자기검수·미승격 브리지 실행 |

## 자가 점검 스크립트

`<설치한-폴더>`에서 실행한다.

```bash
ROOT=<설치한-폴더>

echo "INV1 tasks-only 분포"
grep -l 'tasks-only' "$ROOT/AGENTS.md" "$ROOT/_shared/routing.md" \
  "$ROOT/_templates/worker-brief.md" "$ROOT/_templates/task-folder.md"

echo "INV2 gemini 워커/gemini-critic 활성 참조 (출력 없어야 PASS)"
grep -rn 'call_worker.sh gemini\|gemini-critic\|- \*\*gemini\*\*' \
  "$ROOT/AGENTS.md" "$ROOT/README.md" "$ROOT/_shared/routing.md" \
  "$ROOT/_shared/approval-policy.md" "$ROOT/_templates" || echo " 없음 PASS"

echo "INV3 codex-critic 비평 워커 존재"
grep -rn 'codex-critic' "$ROOT/AGENTS.md" "$ROOT/_shared/routing.md" "$ROOT/_templates"

echo "INV4 log 태그"
grep -n 'DECISION | WORKER_CALL | VERIFICATION | ERROR | APPROVAL | COMPLETE' "$ROOT/_templates/log.md" "$ROOT/AGENTS.md"

echo "INV5 한도 수치"
grep -rn '1500자\|1200자\|1500 chars\|1200 chars' "$ROOT/AGENTS.md" "$ROOT/_templates/context.md" "$ROOT/_templates/worker-brief.md"

echo "INV6 권위 우선순위"
grep -rn 'AGENTS.md.*routing.md' "$ROOT/_shared/design-basis.md" "$ROOT/_shared/orchestrator-rules.md"

echo "INV7 재진입"
grep -q '재진입 프로토콜' "$ROOT/_shared/orchestrator-rules.md" && echo " orchestrator-rules PASS" || echo " orchestrator-rules FAIL"
grep -q 're-entry protocol\|재진입 프로토콜' "$ROOT/AGENTS.md" && echo " AGENTS.md PASS" || echo " AGENTS.md FAIL"

echo "INV8 토폴로지 4패턴"
for p in 'Pipeline' 'Fan-out/Fan-in' 'Expert Pool' 'Producer-Reviewer'; do
  grep -q "$p" "$ROOT/_shared/routing.md" && echo " $p PASS" || echo " $p FAIL"
done

echo "INV9 오케스트레이터·워커셋 (Gemini 3.1 Pro High + claude-main/codex-main/codex-critic)"
grep -q 'Gemini 3.1 Pro High' "$ROOT/AGENTS.md" && echo " orchestrator PASS" || echo " orchestrator FAIL"
for w in claude-main codex-main codex-critic; do
  grep -q "\"$w\"" "$ROOT/_shared/backends.json" && echo " $w PASS" || echo " $w FAIL"
done

echo "INV10 gemini 워커 호출/옛 프록시 활성 (출력 없어야 PASS; 폐기문맥 제외)"
grep -rn 'call_worker.sh gemini\|mcp__gemini-pro__\|mcp__gemini__gemini_' \
  "$ROOT/_shared/routing.md" "$ROOT/_templates/task-folder.md" "$ROOT/AGENTS.md" "$ROOT/_shared/backends.json" \
  | grep -viE '폐기|deprecat' || echo " 없음 PASS"
```

## 전면 재감사가 필요한 경우

- 새 외부 개념·레퍼런스를 시스템에 도입할 때
- worker pool 구성·역할이 바뀔 때
- 위 불변식으로 표현 불가한 구조 변경이 생길 때
