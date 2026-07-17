# Shared Learnings

작업 완료 후 재사용 가능한 교훈만 추가한다. 중복·일회성·작업 특화 내용은 기록하지 않는다.

## 분류 규칙

- **시스템 운영 자체**에 대한, 어떤 작업에든 적용되는 교훈 → 이 파일 (`_shared/learnings.md`).
- **특정 외부 프로젝트/repo에 묶인** 교훈 → `_local/learnings.md` (git 추적 안 함, 명시 요청 없이는 로드하지 않음).

## 형식

```
## [YYYY-MM-DD] [작업명]
**교훈**: 한 문장. 다음 작업에 그대로 적용 가능한 형태로.
**근거**: 왜 그런지, 어떤 작업에서 발견했는지.
**worker**: [관련 worker명 또는 orchestrator]
```

---

<!-- 이 아래부터 교훈 추가 -->

## [2026-07-18] [grok-flavor]
**교훈**: grok(xAI)이 Orchestrator인 flavor에서는 산출물 리뷰 worker를 grok(오케스트레이터) 자기검수로 두지 말고 `codex-critic`으로 분리해야 독립 검토의 의미가 유지된다. 마찬가지로 오케스트레이터가 이미 갖는 네이티브 능력(grok의 web_search/x_search)은 별도 워커로 중복 배치하지 않는다.
**근거**: antigravity flavor의 "오케스트레이터=Gemini라 gemini 워커 배제" 원칙과 동형 — 같은 벤더 워커는 독립성 이득이 없다.
**worker**: orchestrator
