# Hermes MultiAgent Orchestration — Operating Rules

## External/Paid Model Approval

- Do not run external or paid model CLIs, MCPs, or agent bridges without explicit user approval for that specific task.
- This includes, but is not limited to, `claude`, `gemini`, `openai`, `llm`, Claude Code MCP, Gemini MCP, and similar tools.
- A request to translate, summarize, review, research, or process a large file does not imply approval to use external paid models.
- Before using an external paid model, state the exact tool/model, why it is needed, and that it may consume tokens, quota, or money. Wait for explicit approval.
- Local shell commands, file parsing, format validation, current Hermes reasoning, and edits inside this workspace are allowed unless the user says otherwise.

## Architecture

```
Orchestrator (Hermes session, internal reasoning)
└── Worker Pool (separate worker/model calls — approval required)
    ├── codex-main      [engineer] large, separable implementation · analysis · tests · local verification · image generation
    ├── claude-critic   [reviewer · strategist quality gate] Hermes output review · adversarial critique
    └── gemini          [multimodal] multimodal · long document · third-party perspective
```

Slot→assignee mapping is owned by `_shared/capability-profile.md` (variable layer — update only the profile when a new model generation shifts the verdict). The engineer and computer-use slots default to the Orchestrator itself.

**Important**: Hermes Orchestrator's internal reasoning is not a worker. A separate `codex-main`, `claude-critic`, or `gemini` call is a worker/model call and must pass the approval gate for the task.

## Operating Principles

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

### 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

### 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

**Layered application**: The full four principles above bind the Orchestrator (this session) only. The single source of truth for the worker layer is the fixed "Worker 행동 규약" block in `_templates/worker-brief.md` — principles ② and ③ as-is; principle ① translated (workers are one-shot/headless with no user-question channel → state assumptions, surface uncertainty and mismatches in result.md Issues/Caveats); the principle ④ loop is orchestrator-only (combined with the Verification Checklist loop). Never instruct a worker brief to ask the user.

> Source: [multica-ai/andrej-karpathy-skills](https://github.com/multica-ai/andrej-karpathy-skills) (MIT) — adapted. See `NOTICE`.

## Task Lifecycle

1. Create `tasks/<task-name>/task.md` (`status: pending`).
2. Read `_shared/routing.md` and choose the minimum worker set.
3. Confirm **target_repo** when the task will produce external files:
   - If `codex-main` is planned, or the task creates code, docs, or images for another repo, ask for `target_repo` before filling `task.md`.
   - If the user says there is no external target, or the task is analysis/review/planning only, keep outputs under `tasks/<task>/artifacts/`.
   - If the user already provided a path, do not ask again.
4. Record explicit worker approvals in `task.md` before any worker call.
5. Write each worker's brief **exactly at `tasks/<task>/workers/<role>/brief.md`** (Korean <= 1200 chars / English <= 240 words). Use a per-worker folder — do NOT flatten to `<role>_brief.md`.
6. Run the approved worker and save the original response **at `tasks/<task>/workers/<role>/result.md`** (same per-worker folder).
7. Execute the `result.md` Verification Checklist.
8. Append verification results to `log.md` with `[VERIFICATION]`. When the task is finished, update `status` in `task.md` to `done`.
9. On completion, append reusable lessons only when they are genuinely reusable:
   - System-level lessons: `_shared/learnings.md`
   - Project-specific lessons: `_local/learnings.md` (not loaded unless explicitly requested)

> When resuming an existing task, start with `_shared/orchestrator-rules.md` section 3 re-entry protocol, not step 1.

## Context Rules

| File | Limit | Purpose |
|------|-------|---------|
| `context.md` | Korean <= 1500 chars / English <= 300 words | Current snapshot only, not history |
| `brief.md` | Korean <= 1200 chars / English <= 240 words | Only what the worker needs |
| `sources/` | Unlimited | Source material, referenced by path |
| `artifacts/` | Unlimited | Raw outputs and generated files |

Measurement:

```bash
wc -m tasks/<task>/context.md
wc -w tasks/<task>/context.md
```

If `context.md` exceeds the limit, append history to `log.md`, then keep only the current snapshot. Never inline long source files into `context.md` or `brief.md`; pass paths.

## Approval Gate

- Never call a worker that is missing from `workers_approved`.
- Worker approval is task-specific and includes purpose and any external write scope.
- Hermes Orchestrator internal reasoning does not require approval.
- External paid model tools still require explicit user approval even if the task is already created.

## Verification

Before accepting a worker result, execute the `result.md` Verification Checklist and append the result to `log.md`.

Default checks:
- [ ] output matches `brief.md` `Output Format`
- [ ] referenced paths exist
- [ ] `task.md` constraints are satisfied
- [ ] `Do NOT` items are not violated

## log.md Rules

- Append-only. Do not edit or delete prior log entries.
- Format: `[YYYY-MM-DD HH:MM] [TAG] content`
- Allowed tags: `DECISION | WORKER_CALL | VERIFICATION | ERROR | APPROVAL | COMPLETE`

## Worker File Write Policy

| Worker | Default write permission | External repo write |
|--------|--------------------------|---------------------|
| codex-main | `tasks/<task>/` outputs/diffs | Conditional |
| claude-critic | None; Orchestrator records response | Never |
| gemini | None; Orchestrator records response | Never |

### `write_scope` Values

- `none` — no writes
- `tasks-only` — write only inside `tasks/<task>/`
- `"src/**, tests/**"` style patterns — external repo paths allowed only when all 4 conditions below are met

### codex-main External Repo Write Conditions

All 4 are required:

1. `brief.md` includes `target_repo: <absolute path>`.
2. `brief.md` includes `write_scope: <allowed path pattern>`.
3. `task.md` `workers_approved` includes `codex-main` and the approved `write_scope`.
4. `log.md` has a separate `[APPROVAL]` entry for external write approval.

If any condition is missing, `codex-main` writes only inside `tasks/<task>/`, preferably as a diff or patch for user/orchestrator application.

Workers must never edit `_shared/`, `_templates/`, or another task folder unless the current task is explicitly a system maintenance task.

## AGENTS.md Scope

These rules apply when Hermes is working in `<설치한-폴더>` or its subdirectories. Do not copy this orchestration policy into unrelated projects.
