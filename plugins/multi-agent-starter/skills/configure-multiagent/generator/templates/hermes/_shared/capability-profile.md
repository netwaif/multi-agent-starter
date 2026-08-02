# Capability Profile — 슬롯 → 담당 배정 (가변층)

`routing.md`의 decision tree가 정하는 **능력 슬롯을 현재 누가 맡는지**의 정본.
신모델 출시·판정 변경 시 **이 파일만 갱신**한다(근거·날짜 필수, 이력 append-only).
모델 식별자 자체의 표기·갱신은 `backends.json`·config 소관(design-basis D6) — 여기서는 배정만 다룬다.

## 현재 배정

| 슬롯 | 담당 | 배정 근거 요약 |
|------|------|--------------|
| strategist | Orchestrator 산출 + claude-critic 품질 게이트 권장 | 설계·UI/UX 디자인·전략·문체 판단은 Claude 우위 — 이 flavor엔 Claude 생산 워커가 없어 게이트로 보완 |
| engineer | Orchestrator 직접, 크고 분리 가능하면 codex-main | 대규모 구현·테스트 철저, 비용·속도·토큰 효율 우위 |
| computer-use | Orchestrator 직접 | 브라우저 조작·복잡 워크플로우 수행 우위 |
| reviewer | claude-critic | 교차 벤더 독립 검증 (자기검수 회피) |
| multimodal | gemini | 멀티모달·대용량 문서 처리 |

## 배정 이력 (append-only)

- **2026-07-13** 초기 배정 + computer-use 슬롯 신설. 근거: 외부 리뷰 10건 종합 판정
  (Anthropic 최신 플래그십 vs OpenAI 최신 플래그십) — 디자인·전략·글쓰기 = Claude 우위,
  대규모 구현·테스트·브라우저 조작·비용·속도 = GPT 우위로 수렴. 요지는 design-basis D8.

## 갱신 절차

1. 새 판정 자료 확보 (리뷰 종합 · 벤치마크 · 자체 실측)
2. 「현재 배정」 표 갱신 + 「배정 이력」에 날짜·근거 추가 (기존 이력 삭제 금지)
3. 담당명 병기 사본을 **전부** 이 표와 동기화 — `routing.md`(트리 · Worker 역할 상세의 슬롯 표기 · 최소 Worker Set), `AGENTS.md`(Architecture 워커 풀), `README.md`(Workers 목록). 병기는 편의 사본 — 슬롯 정의는 불변
4. 시스템 구조 파일(orchestrator-rules·invariants 등)은 손대지 않는다
