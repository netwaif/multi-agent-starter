#!/usr/bin/env bash
# call_worker.sh — backends.json 디스패처 (cli/api 전용).
# native/mcp는 오케스트레이터가 직접 호출(디스패처 비경유).
# 사용: call_worker.sh <role> <brief-file>
# 반환: stdout에 result envelope(JSON). exit 0=성공, 비0=실패/거부.
set -euo pipefail

# ── 임시자원 추적 + 강제 정리(die·인터럽트·정상 모두) ──
_TMPS=()
cleanup() { local p; for p in "${_TMPS[@]:-}"; do [ -n "$p" ] && rm -rf -- "$p"; done; return 0; }  # 항상 0: EXIT trap이 종료코드 덮어쓰지 않도록
trap cleanup EXIT INT TERM
mktmp()  { local t; t="$(mktemp)";    _TMPS+=("$t"); printf '%s' "$t"; }
mktmpd() { local t; t="$(mktemp -d)"; _TMPS+=("$t"); printf '%s' "$t"; }

die() { echo "call_worker: $1" >&2; exit "${2:-1}"; }

ROLE="${1:-}"; BRIEF="${2:-}"
[ -n "$ROLE" ] && [ -n "$BRIEF" ] || die "usage: call_worker.sh <role> <brief-file>" 64

SCRIPT_DIR="$(cd "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${MULTIAGENT_ROOT:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
BACKENDS="$ROOT/_shared/backends.json"
RUNTIME="$ROOT/_shared/runtime"   # v4 런타임(있으면 envelope v2 + 4.1 recovery gate)

command -v jq >/dev/null 2>&1 || die "jq 필요(JSON 파싱)" 5
[ -f "$BACKENDS" ] || die "backends.json 없음: $BACKENDS" 5

# timeout: coreutils timeout/gtimeout 우선, 없으면 portable bash 폴백(둘 다 유한 보장)
TIMEOUT_BIN=""
command -v timeout  >/dev/null 2>&1 && TIMEOUT_BIN=timeout
[ -z "$TIMEOUT_BIN" ] && command -v gtimeout >/dev/null 2>&1 && TIMEOUT_BIN=gtimeout
run_limited() {  # run_limited <secs> -- <cmd...>
  local t="$1"; shift; [ "$1" = "--" ] && shift
  if [ -n "$TIMEOUT_BIN" ]; then "$TIMEOUT_BIN" -k 5 "$t" "$@"; return $?; fi
  # 폴백: python3 러너(결정적, 프로세스그룹 TERM→KILL). python3은 시스템 필수 의존성.
  command -v python3 >/dev/null 2>&1 || die "timeout 유틸 또는 python3 필요" 5
  python3 "$SCRIPT_DIR/_run.py" "$t" "$@"; return $?
}

# brief 절대경로화 + 검증 ('--'로 옵션 하이재킹 방어)
case "$BRIEF" in *..*) die "brief 경로에 '..' 금지" 6;; esac
[ -f "$BRIEF" ] || die "brief 파일 없음: $BRIEF" 6
BRIEF="$(cd "$(dirname -- "$BRIEF")" && pwd)/$(basename -- "$BRIEF")"

rec="$(jq -c --arg r "$ROLE" '.workers[$r] // empty' "$BACKENDS")"
[ -n "$rec" ] || die "role 미정의: $ROLE" 2

# 폴백 가용성 사전 점검(경고만): primary가 죽고 나서야 폴백 불가를 아는 것을 방지
while IFS= read -r _fe; do
  [ -n "$_fe" ] && [ -z "${!_fe:-}" ] && \
    echo "call_worker: 경고 — 폴백 필수 env 미설정: $_fe (primary 실패 시 폴백 불가)" >&2
done < <(jq -r '.fallbacks[]?.api.required_env[]? // empty' <<<"$rec")

redact() { sed -E 's/[A-Za-z0-9_-]{32,}/[REDACTED]/g'; }

# 단일 backend 실행 → envelope(JSON)을 stdout, exit code 반환
run_backend() {
  local spec="$1" ctype bmode tmo cwdp model wd out err errd rc start dur
  ctype="$(jq -r '.call_type' <<<"$spec")"
  model="$(jq -r '.model // "?"' <<<"$spec")"
  case "$ctype" in
    native|mcp) die "native/mcp는 오케스트레이터 직접 호출(디스패처 비경유)" 3 ;;
    cli|api) ;;
    *) die "잘못된 call_type: $ctype" 7 ;;
  esac
  bmode="$(jq -r '.brief_mode // "content"' <<<"$spec")"
  tmo="$(jq -r '.timeout // 300' <<<"$spec")"
  cwdp="$(jq -r '.cwd_policy // "repo_root"' <<<"$spec")"

  case "$cwdp" in
    isolated_tmp) wd="$(mktmpd)";;
    target)       wd="${TARGET_REPO:-$ROOT}";;
    *)            wd="$ROOT";;
  esac

  local -a cmd=()
  if [ "$ctype" = "cli" ]; then
    local command_bin args_json a
    command_bin="$(jq -r '.cli.command' <<<"$spec")"
    case "$command_bin" in agy|codex|claude|grok) ;; *) die "command allowlist 위반: $command_bin" 7;; esac
    cmd+=("$command_bin")
    args_json="$(jq -r '.cli.args_template[]' <<<"$spec")"   # jq 실패 시 set -e 트리거
    while IFS= read -r a; do
      case "$a" in
        "@brief")         cmd+=("$BRIEF");;
        "@brief_content") cmd+=("$(cat -- "$BRIEF")");;
        *)                cmd+=("$a");;
      esac
    done <<<"$args_json"
    # codex 워커: 기본은 git 요구(안전망). git 없으면 명확히 실패. 옵트아웃 시에만 우회.
    if [ "$command_bin" = "codex" ]; then
      if [ "${MULTIAGENT_CODEX_SKIP_GIT:-0}" = "1" ]; then
        local -a _nc=(); local _ins=0 _x
        for _x in "${cmd[@]}"; do
          _nc+=("$_x")
          if [ "$_ins" = 0 ] && [ "$_x" = "exec" ]; then _nc+=("--skip-git-repo-check"); _ins=1; fi
        done
        cmd=("${_nc[@]}")
      elif ! command -v git >/dev/null 2>&1; then
        die "codex 워커는 git이 필요합니다. git 설치 후 재시도하거나, 위험을 감수하면 MULTIAGENT_CODEX_SKIP_GIT=1 로 우회하세요." 8
      fi
    fi
  else
    local ref reqenv brief_pass
    ref="$(jq -r '.api.ref' <<<"$spec")"
    case "$ref" in adapters/*) ;; *) die "api.ref는 adapters/ 내부만" 7;; esac
    case "$ref" in *..*) die "api.ref에 '..' 금지" 7;; esac
    [ -f "$ROOT/_shared/$ref" ] || die "api 스크립트 없음: $ref" 4
    while IFS= read -r reqenv; do
      [ -n "$reqenv" ] || continue
      if [ -z "${!reqenv:-}" ]; then
        # die 대신 에러 envelope 반환: 폴백 체인에서 실패 사유가 최종 envelope에 남도록
        jq -n --arg model "$model" --arg e "$reqenv" \
          '{status:"error", exit_code:4, backend:"api", model:$model,
            duration_s:0, stdout:"", stderr_sanitized:("필수 env 없음: " + $e + " — 폴백 사용 불가")}'
        return 4
      fi
    done < <(jq -r '.api.required_env[]? // empty' <<<"$spec")
    brief_pass="$(jq -r '.api.brief_pass // "arg1"' <<<"$spec")"
    cmd+=("bash" "$ROOT/_shared/$ref")
    [ "$brief_pass" = "arg1" ] && cmd+=("$BRIEF")
    [ "$brief_pass" = "stdin" ] && bmode="stdin"
  fi

  out="$(mktmp)"; err="$(mktmp)"; errd="$(mktmp)"
  start=$(date +%s)
  rc=0
  (
    cd "$wd" || exit 70
    export CI=1 DEBIAN_FRONTEND=noninteractive
    if [ "$bmode" = "stdin" ]; then
      run_limited "$tmo" -- "${cmd[@]}" <"$BRIEF"
    else
      run_limited "$tmo" -- "${cmd[@]}" </dev/null
    fi
  ) >"$out" 2>"$err" || rc=$?
  dur=$(( $(date +%s) - start ))

  local status="ok"
  [ "$rc" -ne 0 ] && status="error"
  [ "$rc" -eq 124 ] && status="timeout"

  redact <"$err" >"$errd"

  # ── v4: envelope v2 조립을 runtime에 위임 (call_worker.sh는 얇은 진입점) ──
  local RUNTIME="$ROOT/_shared/runtime" bfam route_id toflag="" cver=""
  if [ "$ctype" = "cli" ]; then bfam="$command_bin"; else bfam="api"; fi
  route_id="${bfam}-${ctype}"
  [ "$rc" -eq 124 ] && toflag="--timed-out"
  if [ "$ctype" = "cli" ]; then
    cver="$("$command_bin" --version 2>/dev/null | head -1 | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' | head -1 || true)"
  fi
  if command -v python3 >/dev/null 2>&1 && [ -f "$RUNTIME/envelope.py" ]; then
    python3 "$RUNTIME/envelope.py" \
      --worker-id "$ROLE" --backend-route-id "$route_id" --call-type "$ctype" \
      --model-requested "$model" --raw-rc "$rc" $toflag \
      ${cver:+--cli-version "$cver"} \
      --stdout-path "$out" --stderr-path "$errd" --duration-s "$dur"
  else
    jq -n --arg status "$status" --argjson exit "$rc" \
          --rawfile stdout "$out" --rawfile stderr "$errd" \
          --argjson dur "$dur" --arg backend "$ctype" --arg model "$model" \
          '{status:$status, exit_code:$exit, backend:$backend, model:$model,
            duration_s:$dur, stdout:$stdout, stderr_sanitized:$stderr}'
  fi
  return "$rc"
}

# ── v4 4.1: recovery gate (opt-in — MULTIAGENT_OP_ID 있을 때만) ──────────────
# dispatch 전 A6 gate: events 로드→reduce→admit. 거부면 spawn 없이 PreflightRejection 방출.
# 통과면 AttemptIntent durable 후, 실행 결과를 commit(final terminal 또는 timeout→UNRESOLVED).
ATTEMPT_ID=""; EVENTS_DIR=""
if [ -n "${MULTIAGENT_OP_ID:-}" ] && command -v python3 >/dev/null 2>&1 && [ -f "$RUNTIME/recovery_gate.py" ]; then
  EVENTS_DIR="${MULTIAGENT_EVENTS_DIR:-$ROOT/.awo-events/$MULTIAGENT_OP_ID}"
  mkdir -p "$EVENTS_DIR"
  gate_admit=""; garc=0
  gate_admit="$(PYTHONPATH="$RUNTIME" python3 "$RUNTIME/recovery_gate.py" admit \
      --events-dir "$EVENTS_DIR" --logical-operation-id "$MULTIAGENT_OP_ID" \
      --retry-cap "${MULTIAGENT_RETRY_CAP:-3}")" || garc=$?
  if [ "$garc" -ne 0 ]; then
    # gate 거부: spawn 금지, refusal(PreflightRejection 성격) 그대로 방출.
    echo "$gate_admit"
    exit 4
  fi
  ATTEMPT_ID="$(jq -r '.attempt_id' <<<"$gate_admit")"
fi

# dispatch 종료 시 commit(gate active인 경우) + envelope 방출 후 exit.
finish_dispatch() {  # <envelope-json> <fallback_used-bool> <final-rc> <exit-code>
  local env="$1" fbused="$2" frc="$3" ec="$4" gate_commit=""
  if [ -n "$ATTEMPT_ID" ]; then
    gate_commit="$(PYTHONPATH="$RUNTIME" python3 "$RUNTIME/recovery_gate.py" commit \
        --events-dir "$EVENTS_DIR" --logical-operation-id "$MULTIAGENT_OP_ID" \
        --attempt-id "$ATTEMPT_ID" --raw-rc "$frc" 2>/dev/null || true)"
  fi
  if [ -n "$gate_commit" ]; then
    jq -n --argjson e "$env" --argjson fb "$fbused" --argjson g "$gate_commit" \
      '$e + {fallback_used:$fb, recovery_gate:$g}'
  else
    jq -n --argjson e "$env" --argjson fb "$fbused" '$e + {fallback_used:$fb}'
  fi
  exit "$ec"
}

# primary → 실패 시 fallbacks 순차 (set -e 우회: || prc=$?)
prc=0; env_primary="$(run_backend "$rec")" || prc=$?
if [ "$prc" -eq 0 ]; then
  finish_dispatch "$env_primary" false "$prc" 0
fi
nf="$(jq '.fallbacks | length' <<<"$rec")"
env_fb=""; i=0; final_rc="$prc"   # 폴백 없으면 primary rc가 최종(timeout 124 등 보존)
while [ "$i" -lt "${nf:-0}" ]; do
  fb="$(jq -c --argjson i "$i" '.fallbacks[$i]' <<<"$rec")"
  frc=0; env_fb="$(run_backend "$fb")" || frc=$?
  final_rc="$frc"
  if [ "$frc" -eq 0 ]; then
    finish_dispatch "$env_fb" true "$frc" 0
  fi
  i=$((i+1))
done
finish_dispatch "${env_fb:-$env_primary}" true "$final_rc" 1
