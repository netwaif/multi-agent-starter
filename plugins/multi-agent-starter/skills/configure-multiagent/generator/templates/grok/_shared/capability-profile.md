# Capability Profile — 슬롯 → 담당 배정 (가변층)

`routing.md`의 decision tree가 정하는 **능력 슬롯을 현재 누가 맡는지**의 정본.
신모델 출시·판정 변경 시 **이 파일만 갱신**한다(근거·날짜 필수, 이력 append-only).
모델 식별자 자체의 표기·갱신은 `backends.json`·config 소관 — 여기서는 배정만 다룬다.

## 현재 배정

| 슬롯 | 담당 | 배정 근거 요약 |
|------|------|--------------|
| strategist | claude-main | 설계·UI/UX 디자인·전략·문체 우위 |
| engineer | codex-main | 대규모 구현·테스트 철저, 비용·속도·토큰 효율 우위 |
| computer-use | codex-main | 브라우저 조작·복잡 워크플로우 수행 우위 |
| reviewer | codex-critic | 오케스트레이터(grok)와 다른 벤더 — 독립 검증 |
| multimodal | gemini | 멀티모달·대용량 문서 처리 우위 |

## 배정 이력 (append-only)

- **2026-07-18** 초기 배정 (grok flavor 신설). 근거: 오케스트레이터가 grok(xAI)이므로 reviewer는
  교차벤더(Codex)인 `codex-critic`이 맡고, strategist/engineer/computer-use/multimodal은 기존
  claude/antigravity flavor와 동일 근거(design-basis 참조)로 claude-main/codex-main/gemini에 배정.
  realtime-web(최신성 인텔)은 능력 슬롯이 아니라 오케스트레이터의 네이티브 기능(grok-4.5
  web_search/x_search)이라 별도 워커 배정 없음.

## 갱신 절차

1. 새 판정 자료 확보 (리뷰 종합 · 벤치마크 · 자체 실측)
2. 「현재 배정」 표 갱신 + 「배정 이력」에 날짜·근거 추가 (기존 이력 삭제 금지)
3. 담당명 병기 사본을 **전부** 이 표와 동기화 — `routing.md`(트리 · Worker 역할 상세의 슬롯 표기 · 최소 Worker Set), `GROK.md`(Architecture 워커 풀), `README.md`(Workers 목록), `_templates/task-folder.md`(worker 호출 목록). 병기는 편의 사본 — 슬롯 정의는 불변
4. 시스템 구조 파일(orchestrator-rules·invariants 등)은 손대지 않는다
