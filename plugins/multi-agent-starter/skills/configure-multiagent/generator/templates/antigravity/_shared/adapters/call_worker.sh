#!/usr/bin/env bash
# call_worker.sh — backends.json 디스패처 (cli/api 전용).
# native/mcp는 오케스트레이터가 직접 호출(디스패처 비경유).
# 사용: call_worker.sh [--out <envelope-file>] <role> <brief-file> [payload-file]
#   --out(선택): envelope(JSON)을 파일에 쓰고 stdout에는 사람이 읽는 요약(상태·시간·워커 최종 응답)만 출력.
#     오케스트레이터 화면용 — 종료코드는 동일. 진행 상황(시작·종료 한 줄)은 항상 stderr.
#   payload-file(선택): brief 한도(1200자)와 별도인 동봉 자료(예: sources/gemini-packet.md).
#   디스패처가 brief 뒤에 결합해 전달 — brief 본문 inline 금지 규칙과 충돌 없이 대용량 자료 전달.
#   미리보기: call_worker.sh --merged-preview <brief-file> <payload-file>  (백엔드 호출 없이 결합 결과 출력)
# 사전 게이트: gate.sh(승인·[APPROVAL]·brief 위치/한도·외부쓰기 조건·D5) 통과 못 하면 exit 9.
# 사후 검사: write_scope 패턴이면 scope_check.sh로 scope 밖 변경 보고(status=scope_violation, exit 10, 비파괴).
# 반환: stdout에 result envelope(JSON). exit 0=성공, 비0=실패/거부.
set -euo pipefail

# ── 임시자원 추적 + 강제 정리(die·인터럽트·정상 모두) ──
_TMPS=()
cleanup() { local p; for p in "${_TMPS[@]:-}"; do [ -n "$p" ] && rm -rf -- "$p"; done; return 0; }  # 항상 0: EXIT trap이 종료코드 덮어쓰지 않도록
trap cleanup EXIT INT TERM
mktmp()  { local t; t="$(mktemp)";    _TMPS+=("$t"); printf '%s' "$t"; }
mktmpd() { local t; t="$(mktemp -d)"; _TMPS+=("$t"); printf '%s' "$t"; }

die() { echo "call_worker: $1" >&2; exit "${2:-1}"; }

PREVIEW=0; OUTFILE=""
if [ "${1:-}" = "--out" ]; then OUTFILE="${2:-}"; [ -n "$OUTFILE" ] || die "--out 뒤에 파일 경로 필요" 64; shift 2; fi
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

# 사전 게이트(fail-closed): 승인·[APPROVAL]·brief 위치/한도·외부쓰기 조건·D5 (gate.sh 정본, preview는 비경유)
GATE_REPO="-"; GATE_SCOPE="none"
if [ "$PREVIEW" != 1 ]; then
  gate_json="$(MULTIAGENT_ROOT="$ROOT" bash "$SCRIPT_DIR/gate.sh" --json "$BRIEF")" || die "게이트 거부 (gate.sh exit $?)" 9
  GATE_TASK="$(jq -r .task <<<"$gate_json")"; GATE_ROLE="$(jq -r .role <<<"$gate_json")"
  GATE_REPO="$(jq -r .target_repo <<<"$gate_json")"; GATE_SCOPE="$(jq -r .write_scope <<<"$gate_json")"
  # 승인된 역할(brief 경로) == 호출 역할(첫 인자). 불일치 = 미승인 백엔드 실행이므로 거부
  [ "$GATE_ROLE" = "$ROLE" ] || die "역할 불일치: brief는 $GATE_ROLE 승인, 호출은 $ROLE" 9
fi

# payload(선택) — brief 한도 밖 동봉 자료. brief 뒤에 결합한 임시 brief로 치환.
if [ -n "$PAYLOAD" ]; then
  case "$PAYLOAD" in *..*) die "payload 경로에 '..' 금지" 6;; esac
  [ -f "$PAYLOAD" ] || die "payload 파일 없음: $PAYLOAD" 6
  MERGED="$(mktmp)"
  { cat -- "$BRIEF"
    printf '\n\n---\n\n# 동봉 자료 (payload — orchestrator가 결합. 이 자료만 사용하고 파일 열지 말 것)\n\n'
    cat -- "$PAYLOAD"
  } >"$MERGED"
  BRIEF="$MERGED"
fi
if [ "$PREVIEW" = 1 ]; then cat -- "$BRIEF"; exit 0; fi

rec="$(jq -c --arg r "$ROLE" '.workers[$r] // empty' "$BACKENDS")"
[ -n "$rec" ] || die "role 미정의: $ROLE" 2

# 폴백 가용성 사전 점검(경고만): primary가 죽고 나서야 폴백 불가를 아는 것을 방지
while IFS= read -r _fe; do
  [ -n "$_fe" ] && [ -z "${!_fe:-}" ] && \
    echo "call_worker: 경고 — 폴백 필수 env 미설정: $_fe (primary 실패 시 폴백 불가)" >&2
done < <(jq -r '.fallbacks[]?.api.required_env[]? // empty' <<<"$rec")

redact() { sed -E 's/[A-Za-z0-9_-]{32,}/[REDACTED]/g'; }

# 최종 envelope 출력: 기본=stdout에 JSON. --out이면 파일에 JSON + stdout에 요약.
emit() {  # emit <envelope-json>
  local e="$1" n
  if [ -z "$OUTFILE" ]; then printf '%s\n' "$e"; return 0; fi
  mkdir -p -- "$(dirname -- "$OUTFILE")"; printf '%s\n' "$e" >"$OUTFILE"
  jq -r --arg r "$ROLE" '"[call_worker] \($r) 결과: \(.status) (exit \(.exit_code), \(.duration_s)s, fallback \(if .fallback_used then "사용" else "없음" end), scope \(.scope_check // "-"))"' <<<"$e"
  echo "envelope: $OUTFILE"
  n="$(jq -r '.stdout' <<<"$e" | wc -l | tr -d ' ')"
  echo "──── 워커 최종 응답 ────"
  jq -r '.stdout' <<<"$e" | tail -n 60
  [ "$n" -gt 60 ] && echo "… (${n}줄 중 마지막 60줄 — 전문은 envelope .stdout)"
  if [ "$(jq -r .status <<<"$e")" != "ok" ]; then
    echo "──── stderr 끝 15줄 ────"; jq -r '.stderr_sanitized' <<<"$e" | tail -n 15
  fi
  return 0
}

# 단일 backend 실행 → envelope(JSON)을 stdout, exit code 반환
run_backend() {
  local spec="$1" ctype bmode tmo cwdp model wd sroot="" out err errd rc start dur
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
    # task: none/tasks-only는 cwd=tasks/<task>/(workspace-write 샌드박스가 작업 폴더 밖 쓰기를 막음),
    #       외부 쓰기 승인(write_scope 패턴)일 때만 target_repo. scope 검사 기준(sroot)은 루트/target_repo.
    task)         wd="$ROOT/tasks/$GATE_TASK"; sroot="$ROOT"
                  case "$GATE_SCOPE" in none|tasks-only) ;; *) [ "$GATE_REPO" != "-" ] && { wd="$GATE_REPO"; sroot="$GATE_REPO"; };; esac
                  [ -d "$wd" ] || { wd="$ROOT"; sroot="$ROOT"; };;
    # target: 외부 쓰기 승인(write_scope 패턴)이 있을 때만 brief의 target_repo(gate가 존재 보장). none/tasks-only는 항상 $ROOT.
    #         환경변수 fallback 없음(잔존 env로 승인 없는 repo에서 실행되는 것 방지).
    target)       wd="$ROOT"
                  case "$GATE_SCOPE" in none|tasks-only) ;; *) [ "$GATE_REPO" != "-" ] && wd="$GATE_REPO";; esac;;
    *)            wd="$ROOT";;
  esac
  [ -n "$sroot" ] || sroot="$wd"

  local -a cmd=()
  if [ "$ctype" = "cli" ]; then
    local command_bin args_json a
    command_bin="$(jq -r '.cli.command' <<<"$spec")"
    case "$command_bin" in agy|codex|claude) ;; *) die "command allowlist 위반: $command_bin" 7;; esac
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
      elif ! git -C "$wd" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        die "codex 워커는 git 저장소 안에서 실행됩니다(cwd=$wd). 설치 폴더에서 'git init' 후 재시도하거나, 위험을 감수하면 MULTIAGENT_CODEX_SKIP_GIT=1 로 우회하세요." 8
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
  # 실행 전 스냅샷(사후 scope_check용). git repo 아니면 검사 불가(skipped). git repo인데 스냅샷 실패면 fail-closed로 호출 거부.
  local snap="" scope_state="skipped"
  if git -C "$sroot" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    snap="$(mktmp)"
    if ! bash "$SCRIPT_DIR/scope_check.sh" --snapshot "$sroot" >"$snap" 2>"$snap.err"; then
      jq -n --arg model "$model" --arg backend "$ctype" --rawfile e "$snap.err" \
        '{status:"scope_error", exit_code:12, backend:$backend, model:$model, duration_s:0, stdout:"",
          stderr_sanitized:("실행 전 스냅샷 실패 — scope 검사 불가하므로 호출 거부: " + $e), scope_check:"error", scope_violations:[]}'
      rm -f "$snap.err"; return 12
    fi; rm -f "$snap.err"
  fi
  local shown="" _a; for _a in "${cmd[@]}"; do   # 진행 표시: 긴 인자(brief 본문 등)는 <brief>로 가림
    case "$_a" in *$'\n'*) _a="<brief>";; esac; [ "${#_a}" -gt 60 ] && _a="<brief>"; shown+=" $_a"; done
  echo "[call_worker] $ROLE 시작 —${shown} (cwd=${wd#"$ROOT"/}, timeout ${tmo}s)" >&2
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

  # 사후 scope 검사(보고만): scope 밖 변경이 있으면 status=scope_violation, exit 10. stdout은 보존.
  # 사후 검사 결과: ok / violation(status=scope_violation) / error(status=scope_error — 검사 자체 실패, 성공과 구분). 둘 다 exit 10=최종 실패
  local viol="[]"
  if [ -n "$snap" ]; then
    local vf src; vf="$(mktmp)"; scope_state="ok"
    if bash "$SCRIPT_DIR/scope_check.sh" "$sroot" "$GATE_SCOPE" "$snap" "$GATE_TASK" >"$vf" 2>"$vf.err"; then :; else src=$?
      if [ "$src" -eq 10 ]; then viol="$(jq -R . <"$vf" | jq -s .)"; status="scope_violation"; rc=10; scope_state="violation"
      else status="scope_error"; rc=10; scope_state="error"; cat "$vf.err" >>"$err"; fi
      rm -f "$vf.err"
    fi
  fi

  echo "[call_worker] $ROLE 종료 — $status (exit $rc, ${dur}s)" >&2
  redact <"$err" >"$errd"
  jq -n --arg status "$status" --argjson exit "$rc" \
        --rawfile stdout "$out" --rawfile stderr "$errd" \
        --argjson dur "$dur" --arg backend "$ctype" --arg model "$model" --argjson viol "$viol" --arg sc "$scope_state" \
        '{status:$status, exit_code:$exit, backend:$backend, model:$model,
          duration_s:$dur, stdout:$stdout, stderr_sanitized:$stderr, scope_check:$sc, scope_violations:$viol}'
  return "$rc"
}

# primary → 실패 시 fallbacks 순차 (set -e 우회: || prc=$?)
prc=0; env_primary="$(run_backend "$rec")" || prc=$?
if [ "$prc" -eq 0 ]; then
  emit "$(jq -n --argjson e "$env_primary" '$e + {fallback_used:false}')"
  exit 0
fi
# scope 위반(10)/검사 불가(12)는 재시도 대상이 아닌 최종 실패: 폴백 없이 해당 envelope 보존 (primary·fallback 동일)
if [ "$prc" -eq 10 ] || [ "$prc" -eq 12 ]; then
  emit "$(jq -n --argjson e "$env_primary" '$e + {fallback_used:false}')"
  exit "$prc"
fi
nf="$(jq '.fallbacks | length' <<<"$rec")"
env_fb=""; i=0
while [ "$i" -lt "${nf:-0}" ]; do
  fb="$(jq -c --argjson i "$i" '.fallbacks[$i]' <<<"$rec")"
  frc=0; env_fb="$(run_backend "$fb")" || frc=$?
  if [ "$frc" -eq 0 ]; then
    emit "$(jq -n --argjson e "$env_fb" '$e + {fallback_used:true}')"
    exit 0
  fi
  if [ "$frc" -eq 10 ] || [ "$frc" -eq 12 ]; then
    emit "$(jq -n --argjson e "$env_fb" '$e + {fallback_used:true}')"
    exit "$frc"
  fi
  i=$((i+1))
done
# 사전 검사 die(git 없음 등)는 envelope 없이 끝나므로 최소 envelope로 대체(사유는 위 stderr)
last="${env_fb:-$env_primary}"
[ -n "$last" ] || last="$(jq -n --argjson rc "$prc" '{status:"error", exit_code:$rc, backend:"-", model:"-", duration_s:0, stdout:"", stderr_sanitized:"디스패처 사전 검사 실패 — 사유는 stderr의 call_worker: 줄"}')"
emit "$(jq -n --argjson e "$last" --argjson fb "$( [ "${nf:-0}" -gt 0 ] && echo true || echo false )" '$e + {fallback_used:$fb}')"
exit 1
