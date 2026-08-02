#!/usr/bin/env bash
# call_worker.sh — backends.json 디스패처 (cli/api 전용).
# native/mcp는 오케스트레이터가 직접 호출(디스패처 비경유).
# 사용: call_worker.sh <role> <brief-file> [payload-file]
#   payload-file(선택): brief 한도(1200자)와 별도인 동봉 자료(예: sources/gemini-packet.md).
#   디스패처가 brief 뒤에 결합해 전달 — brief 본문 inline 금지 규칙과 충돌 없이 대용량 자료 전달.
#   미리보기: call_worker.sh --merged-preview <brief-file> <payload-file>  (백엔드 호출 없이 결합 결과 출력)
# 반환: stdout에 result envelope(JSON). exit 0=성공, 비0=실패/거부.
set -euo pipefail

# ── 임시자원 추적 + 강제 정리(die·인터럽트·정상 모두) ──
_TMPS=()
cleanup() { local p; for p in "${_TMPS[@]:-}"; do [ -n "$p" ] && rm -rf -- "$p"; done; return 0; }  # 항상 0: EXIT trap이 종료코드 덮어쓰지 않도록
trap cleanup EXIT INT TERM
mktmp()  { TMP_PATH="$(mktemp)";    _TMPS+=("$TMP_PATH"); }
mktmpd() { TMP_PATH="$(mktemp -d)"; _TMPS+=("$TMP_PATH"); }

die() { echo "call_worker: $1" >&2; exit "${2:-1}"; }

PREVIEW=0
if [ "${1:-}" = "--merged-preview" ]; then PREVIEW=1; shift; set -- "_preview" "$@"; fi

ROLE="${1:-}"; BRIEF="${2:-}"; PAYLOAD="${3:-}"
[ -n "$ROLE" ] && [ -n "$BRIEF" ] || die "usage: call_worker.sh <role> <brief-file> [payload-file]" 64

SCRIPT_DIR="$(cd "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${MULTIAGENT_ROOT:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
BACKENDS="$ROOT/_shared/backends.json"

command -v jq >/dev/null 2>&1 || die "jq 필요(JSON 파싱)" 5
[ "$PREVIEW" = 1 ] || [ -f "$BACKENDS" ] || die "backends.json 없음: $BACKENDS" 5

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

# payload(선택) — brief 한도 밖 동봉 자료. brief 뒤에 결합한 임시 brief로 치환.
if [ -n "$PAYLOAD" ]; then
  case "$PAYLOAD" in *..*) die "payload 경로에 '..' 금지" 6;; esac
  [ -f "$PAYLOAD" ] || die "payload 파일 없음: $PAYLOAD" 6
  mktmp; MERGED="$TMP_PATH"
  { cat -- "$BRIEF"
    printf '\n\n---\n\n# 동봉 자료 (payload — orchestrator가 결합. 이 자료만 사용하고 파일 열지 말 것)\n\n'
    cat -- "$PAYLOAD"
  } >"$MERGED"
  BRIEF="$MERGED"
fi
if [ "$PREVIEW" = 1 ]; then cat -- "$BRIEF"; exit 0; fi

rec="$(jq -c --arg r "$ROLE" '.workers[$r] // empty' "$BACKENDS")"
[ -n "$rec" ] || die "role 미정의: $ROLE" 2
if jq -e '[.cli.args_template[]?, .fallbacks[]?.cli.args_template[]?] | index("@target_repo") != null' <<<"$rec" >/dev/null \
   && [ -z "${TARGET_REPO:-}" ]; then
  die "@target_repo 사용 시 TARGET_REPO 환경변수가 필요합니다" 6
fi

# 폴백 가용성 사전 점검(경고만): primary가 죽고 나서야 폴백 불가를 아는 것을 방지
while IFS= read -r _fe; do
  _fe="${_fe%$'\r'}"
  [ -n "$_fe" ] && [ -z "${!_fe:-}" ] && \
    echo "call_worker: 경고 — 폴백 필수 env 미설정: $_fe (primary 실패 시 폴백 불가)" >&2
done < <(jq -r '.fallbacks[]?.api.required_env[]? // empty' <<<"$rec")

redact() { sed -E 's/[A-Za-z0-9_-]{32,}/[REDACTED]/g'; }

# 단일 backend 실행 → envelope(JSON)을 stdout, exit code 반환
run_backend() {
  trap cleanup EXIT INT TERM  # command substitution subshell에서도 임시자원 정리 보장
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
    isolated_tmp) mktmpd; wd="$TMP_PATH";;
    target)       wd="${TARGET_REPO:-$ROOT}";;
    *)            wd="$ROOT";;
  esac

  local -a cmd=()
  if [ "$ctype" = "cli" ]; then
    local command_bin args_json a
    command_bin="$(jq -r '.cli.command' <<<"$spec")"
    case "$command_bin" in agy|codex|claude) ;; *) die "command allowlist 위반: $command_bin" 7;; esac
    cmd+=("$command_bin")
    args_json="$(jq -r '.cli.args_template[]' <<<"$spec")"   # jq 실패 시 set -e 트리거
    while IFS= read -r a; do
      a="${a%$'\r'}"
      case "$a" in
        "@brief")         cmd+=("$BRIEF");;
        "@brief_content") cmd+=("$(cat -- "$BRIEF")");;
        "@target_repo")
          [ -n "${TARGET_REPO:-}" ] || die "@target_repo 사용 시 TARGET_REPO 환경변수가 필요합니다" 6
          cmd+=("$TARGET_REPO")
          ;;
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
      reqenv="${reqenv%$'\r'}"
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

  mktmp; out="$TMP_PATH"; mktmp; err="$TMP_PATH"; mktmp; errd="$TMP_PATH"
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
  jq -n --arg status "$status" --argjson exit "$rc" \
        --rawfile stdout "$out" --rawfile stderr "$errd" \
        --argjson dur "$dur" --arg backend "$ctype" --arg model "$model" \
        '{status:$status, exit_code:$exit, backend:$backend, model:$model,
          duration_s:$dur, stdout:$stdout, stderr_sanitized:$stderr}'
  return "$rc"
}

# primary → 실패 시 fallbacks 순차 (set -e 우회: || prc=$?)
prc=0; env_primary="$(run_backend "$rec")" || prc=$?
if [ "$prc" -eq 0 ]; then
  jq -n --argjson e "$env_primary" '$e + {fallback_used:false}'
  exit 0
fi
nf="$(jq '.fallbacks | length' <<<"$rec")"
env_fb=""; i=0
while [ "$i" -lt "${nf:-0}" ]; do
  fb="$(jq -c --argjson i "$i" '.fallbacks[$i]' <<<"$rec")"
  frc=0; env_fb="$(run_backend "$fb")" || frc=$?
  if [ "$frc" -eq 0 ]; then
    jq -n --argjson e "$env_fb" '$e + {fallback_used:true}'
    exit 0
  fi
  i=$((i+1))
done
jq -n --argjson e "${env_fb:-$env_primary}" '$e + {fallback_used:true}'
exit 1
