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

## [2026-06-01] [codex-fork]
**교훈**: Codex가 Orchestrator인 fork에서는 산출물 리뷰 worker를 Codex 자기검수로 두지 말고 `claude-critic`으로 분리해야 독립 검토의 의미가 유지된다.
**근거**: 사용자 결정에 따라 원본 MultiAgent의 critic 역할을 Codex 버전에 맞게 재설계했다.
**worker**: orchestrator
