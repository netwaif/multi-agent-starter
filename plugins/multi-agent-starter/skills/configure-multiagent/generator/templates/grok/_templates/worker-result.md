# Result — [worker-role] / [작업명]

<!-- 이 파일은 worker 응답을 받은 후 생성. brief 작성과 동시에 미리 생성하지 말 것. -->

```yaml
worker: claude-main | codex-main | codex-critic | gemini
task: [작업명]
status: draft | complete | failed
completed_at: <YYYY-MM-DD HH:MM>   # date +"%Y-%m-%d %H:%M"
tokens_used: (선택)
```

## Summary

한 문장. 무엇을 했는가.

## Output

<!-- 실제 결과물. 코드는 코드 블록, 문서는 Markdown, 분석은 섹션으로. -->
<!-- 대용량 산출물은 artifacts/에 저장하고 경로만 기록. -->

## Verification Checklist

- [ ] output_format과 일치
- [ ] 파일 경로 실존 확인
- [ ] task.md constraints 충족
- [ ] Do NOT 항목 위반 없음
- [ ] 가정·불일치가 Issues/Caveats에 표면화됨

## Issues / Caveats

<!-- 결과에 포함된 불확실성, 한계, 후속 확인 필요 사항 -->

## Artifacts

```
# 별도 파일로 저장된 산출물
tasks/<task-name>/artifacts/<file>
```
