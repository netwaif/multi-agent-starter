# Log — [작업명]

<!-- append-only. 수정/삭제 금지. -->
<!-- 형식: [YYYY-MM-DD HH:MM] [TAG] 내용 -->
<!-- TAG: DECISION | WORKER_CALL | VERIFICATION | ERROR | APPROVAL | COMPLETE -->
<!-- timestamp 명령어: date +"%Y-%m-%d %H:%M" -->

<!--
========================================
형식 예시 (이 블록은 사용 시 삭제)
========================================
[2026-06-01 14:30] [DECISION] routing.md 참조 -> codex-main + claude-critic 선택. gemini 제외 (이미지 없음)
[2026-06-01 14:31] [APPROVAL] codex-main 사용자 승인. purpose: 구현 및 로컬 검증
[2026-06-01 14:45] [WORKER_CALL] codex-main brief 전달. input: context.md + sources/spec.md
[2026-06-01 15:10] [VERIFICATION] codex-main result 검토 - output_format PASS, constraints PASS, paths PASS
[2026-06-01 15:11] [DECISION] claude-critic 호출 결정. Codex 산출물 독립 리뷰 필요
[2026-05-11 16:00] [COMPLETE] 작업 완료. 교훈: 시스템 일반→_shared/learnings.md, 프로젝트 특화→_local/learnings.md
========================================
-->

<!-- 이 아래부터 실제 로그 기록 -->
