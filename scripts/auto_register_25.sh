#!/usr/bin/env bash
set -euo pipefail

# 配置文件：config.json（项目根目录）
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

LOCK_FILE="/tmp/chatgpt_register_auto.lock"
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  echo "[Auto] another run is in progress, exit."
  exit 0
fi

SECRETS_FILE="$ROOT_DIR/.secrets/mailu.env"
if [[ -f "$SECRETS_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$SECRETS_FILE"
  set +a
fi

TG_SECRETS_FILE="$ROOT_DIR/.secrets/telegram.env"
if [[ -f "$TG_SECRETS_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$TG_SECRETS_FILE"
  set +a
fi

if [[ -z "${MAILU_API_TOKEN:-}" && -f "$ROOT_DIR/config.json" ]]; then
  MAILU_API_TOKEN="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1], "r", encoding="utf-8")).get("mailu_api_token",""))' "$ROOT_DIR/config.json" 2>/dev/null || true)"
  export MAILU_API_TOKEN
fi

: "${MAILU_API_TOKEN:?missing MAILU_API_TOKEN}"

CONFIG_TOTAL_ACCOUNTS=""
CONFIG_MAX_WORKERS=""
if [[ -f "$ROOT_DIR/config.json" ]]; then
  CONFIG_TOTAL_ACCOUNTS="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1], "r", encoding="utf-8")).get("total_accounts",""))' "$ROOT_DIR/config.json" 2>/dev/null || true)"
  CONFIG_MAX_WORKERS="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1], "r", encoding="utf-8")).get("max_workers",""))' "$ROOT_DIR/config.json" 2>/dev/null || true)"
fi

TOTAL_ACCOUNTS="${TOTAL_ACCOUNTS:-}"
MAX_WORKERS="${MAX_WORKERS:-}"
if [[ -z "$TOTAL_ACCOUNTS" ]]; then
  TOTAL_ACCOUNTS="${CONFIG_TOTAL_ACCOUNTS:-}"
fi
if [[ -z "$MAX_WORKERS" ]]; then
  MAX_WORKERS="${CONFIG_MAX_WORKERS:-}"
fi

if [[ -z "$TOTAL_ACCOUNTS" || -z "$MAX_WORKERS" ]]; then
  echo "[Auto] missing TOTAL_ACCOUNTS/MAX_WORKERS (set in config.json or env)"
  exit 1
fi

LOG_DIR="$ROOT_DIR/logs"
mkdir -p "$LOG_DIR"
TS="$(date +%Y%m%d_%H%M%S)"
LOG_FILE="$LOG_DIR/auto_register_${TS}.log"

log_line() {
  local ts
  ts="$(date '+%F %T')"
  echo "[$ts] $*" | tee -a "$LOG_FILE"
}

IP_CHANGE_STATUS="unknown"
IP_CHANGE_DETAIL="未执行"

CRON_JITTER_MINUTES="${CRON_JITTER_MINUTES:-3}"
CRON_JITTER_MAX_MINUTES="${CRON_JITTER_MAX_MINUTES:-15}"

maybe_sleep_cron_jitter() {
  local min="${CRON_JITTER_MINUTES}"
  local max="${CRON_JITTER_MAX_MINUTES}"
  if ! [[ "${min}" =~ ^[0-9]+$ ]] || ! [[ "${max}" =~ ^[0-9]+$ ]]; then
    log_line "[Auto] cron jitter: invalid range min=${min} max=${max}, skip"
    return 0
  fi
  if [[ "${max}" -lt "${min}" ]]; then
    log_line "[Auto] cron jitter: max < min (${max} < ${min}), swap"
    local tmp="${min}"
    min="${max}"
    max="${tmp}"
  fi
  if [[ "${max}" -eq 0 ]]; then
    return 0
  fi
  local range=$((max - min + 1))
  if [[ "${range}" -le 0 ]]; then
    return 0
  fi
  local delay_minutes=$((RANDOM % range + min))
  if [[ "${delay_minutes}" -le 0 ]]; then
    return 0
  fi
  log_line "[Auto] cron jitter: sleep ${delay_minutes} min"
  sleep "$((delay_minutes * 60))"
}

TRIGGER_SOURCE="${TRIGGER_SOURCE:-}"
TRIGGER_PPID="${PPID}"
TRIGGER_PARENT_COMM="$(ps -o comm= -p "$PPID" 2>/dev/null | tr -d '\n' || true)"
TRIGGER_PARENT_ARGS="$(ps -o args= -p "$PPID" 2>/dev/null | tr '\n' ' ' | sed 's/[[:space:]]\+/ /g' | head -c 200 || true)"
TRIGGER_USER="$(id -un 2>/dev/null || echo "<unknown>")"
TRIGGER_TTY="$(tty 2>/dev/null || echo "n/a")"
TRIGGER_CWD="$(pwd)"
if [[ -z "$TRIGGER_SOURCE" ]]; then
  case "$TRIGGER_PARENT_COMM" in
    cron|crond)
      TRIGGER_SOURCE="cron"
      ;;
    systemd|systemd-run)
      TRIGGER_SOURCE="systemd"
      ;;
    sshd)
      TRIGGER_SOURCE="ssh"
      ;;
    bash|sh|zsh|dash)
      if [[ "$TRIGGER_TTY" == "not a tty" || "$TRIGGER_TTY" == "n/a" ]]; then
        TRIGGER_SOURCE="shell-noninteractive"
      else
        TRIGGER_SOURCE="shell-interactive"
      fi
      ;;
    python*|node*)
      TRIGGER_SOURCE="script-runner"
      ;;
    *)
      TRIGGER_SOURCE="unknown"
      ;;
  esac
fi
log_line "[Auto] trigger: source=${TRIGGER_SOURCE} ppid=${TRIGGER_PPID} parent=${TRIGGER_PARENT_COMM:-<unknown>} user=${TRIGGER_USER} tty=${TRIGGER_TTY} cwd=${TRIGGER_CWD}"
if [[ -n "$TRIGGER_PARENT_ARGS" ]]; then
  log_line "[Auto] trigger: parent_args=${TRIGGER_PARENT_ARGS}"
fi
if [[ "${TRIGGER_SOURCE}" == "cron" ]]; then
  maybe_sleep_cron_jitter
fi

echo "[Auto] start: $(date)" | tee -a "$LOG_FILE"
echo "[Auto] total=${TOTAL_ACCOUNTS} workers=${MAX_WORKERS}" | tee -a "$LOG_FILE"

set +e
TOTAL_ACCOUNTS="$TOTAL_ACCOUNTS" MAX_WORKERS="$MAX_WORKERS" ./scripts/batch_register.sh | tee -a "$LOG_FILE"
RUN_STATUS=${PIPESTATUS[0]}
set -e

echo "[Auto] done: $(date)" | tee -a "$LOG_FILE"

resolve_register_log_file() {
  if [[ -n "${REGISTER_LOG_FILE:-}" ]]; then
    echo "${REGISTER_LOG_FILE}"
    return 0
  fi
  local cfg="${ROOT_DIR}/config.json"
  local lf=""
  if [[ -f "${cfg}" ]]; then
    lf="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1], "r", encoding="utf-8")).get("log_file",""))' "${cfg}" 2>/dev/null || true)"
  fi
  if [[ -z "${lf}" ]]; then
    lf="logs/register.log"
  fi
  if [[ "${lf}" != /* ]]; then
    lf="${ROOT_DIR}/${lf}"
  fi
  echo "${lf}"
}

maybe_change_gcp_ip() {
  local min_total="${CHANGE_IP_MIN_TOTAL:-10}"
  local min_hours="${CHANGE_IP_MIN_HOURS:-10}"
  local mailu_url="${MAILU_CHECK_URL:-https://mail.oracle.311200.xyz/}"
  local change_script="${CHANGE_GCP_IP_SCRIPT:-/root/.openclaw/workspace/googleCloud/change_gcp_ip.sh}"
  local change_log="${CHANGE_GCP_IP_LOG:-}"

  _set_ip_skip() {
    local reason="$1"
    IP_CHANGE_STATUS="skipped"
    IP_CHANGE_DETAIL="未更换IP：${reason}"
    log_line "[Auto] skip IP change: ${reason}"
  }

  local reg_log
  reg_log="$(resolve_register_log_file)"

  if [[ ! -f "${reg_log}" ]]; then
    _set_ip_skip "register log not found (${reg_log})"
    return 0
  fi

  local analysis
  analysis="$(python3 - "${reg_log}" <<'PY' 2>/dev/null || true
import json
import os
import sys
from datetime import datetime, timezone

log_path = sys.argv[1]
if not log_path or not os.path.exists(log_path):
    sys.exit(0)

events = []
with open(log_path, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except Exception:
            continue

batch_ends = [(i, ev) for i, ev in enumerate(events) if ev.get("event") == "batch_end"]
if not batch_ends:
    sys.exit(0)

last_end_idx, last_end = batch_ends[-1]

success = last_end.get("success")
failed = last_end.get("failed")
total = last_end.get("total_accounts")

if success is None or failed is None or total is None:
    last_start_idx = None
    for i in range(last_end_idx, -1, -1):
        if events[i].get("event") == "batch_start":
            last_start_idx = i
            break
    batch_events = events[last_start_idx:] if last_start_idx is not None else events
    if success is None:
        success = sum(1 for ev in batch_events if ev.get("event") == "register_success")
    if failed is None:
        failed = sum(1 for ev in batch_events if ev.get("event") == "register_fail")
    if total is None:
        total = (success or 0) + (failed or 0)

print(f"SUCCESS={int(success or 0)}")
print(f"FAILED={int(failed or 0)}")
print(f"TOTAL={int(total or 0)}")
PY
)"

  if [[ -z "${analysis}" ]]; then
    _set_ip_skip "unable to analyze register log"
    return 0
  fi

  local success=0 failed=0 total=0
  while IFS= read -r line; do
    case "${line}" in
      SUCCESS=*) success="${line#SUCCESS=}" ;;
      FAILED=*) failed="${line#FAILED=}" ;;
      TOTAL=*) total="${line#TOTAL=}" ;;
    esac
  done <<< "${analysis}"

  local mailu_ok=0
  if curl -fsSL --max-time 10 "${mailu_url}" -o /dev/null; then
    mailu_ok=1
  fi

  if [[ "${mailu_ok}" != "1" ]]; then
    _set_ip_skip "mailu check failed (${mailu_url})"
    return 0
  fi

  if [[ "${total:-0}" -lt "${min_total}" ]]; then
    _set_ip_skip "total=${total} < ${min_total}"
    return 0
  fi

  if [[ "${success:-0}" -ne 0 ]]; then
    _set_ip_skip "success=${success} (not zero)"
    return 0
  fi

  if [[ -z "${change_log}" ]]; then
    local script_dir
    script_dir="$(cd "$(dirname "${change_script}")" && pwd)"
    change_log="${script_dir}/logs/change_gcp_ip_history.log"
  fi

  local last_change_hours=""
  local last_change_time=""
  if [[ -f "${change_log}" ]]; then
    change_info="$(python3 - "${change_log}" <<'PY' 2>/dev/null || true
import re
import sys
from datetime import datetime

path = sys.argv[1]
pattern = re.compile(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]")
last_ts = None
try:
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            m = pattern.match(line.strip())
            if not m:
                continue
            try:
                last_ts = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
            except Exception:
                continue
except Exception:
    last_ts = None

if not last_ts:
    sys.exit(0)

local_tz = datetime.now().astimezone().tzinfo
now = datetime.now().astimezone()
if last_ts.tzinfo is None:
    last_ts = last_ts.replace(tzinfo=local_tz)
delta = now - last_ts.astimezone(local_tz)
hours = int(delta.total_seconds() // 3600)
print(f"HOURS={hours}")
print(f"TIME={last_ts.astimezone().strftime('%Y-%m-%d %H:%M:%S %z')}")
PY
)"
    if [[ -n "${change_info}" ]]; then
      while IFS= read -r line; do
        case "${line}" in
          HOURS=*) last_change_hours="${line#HOURS=}" ;;
          TIME=*) last_change_time="${line#TIME=}" ;;
        esac
      done <<< "${change_info}"
    fi
  fi

  if [[ ! -f "${change_log}" ]]; then
    _set_ip_skip "change log not found (${change_log})"
    return 0
  fi

  if [[ -z "${last_change_hours}" ]]; then
    _set_ip_skip "last change time unknown (log=${change_log})"
    return 0
  fi

  if ! [[ "${last_change_hours}" =~ ^-?[0-9]+$ ]]; then
    _set_ip_skip "last_change_hours invalid (${last_change_hours}) (log=${change_log})"
    return 0
  fi

  if [[ "${last_change_hours}" -lt 0 ]]; then
    _set_ip_skip "last_change_hours negative (${last_change_hours}) (last_change_time=${last_change_time:-<unknown>} log=${change_log})"
    return 0
  fi

  if [[ "${last_change_hours}" -lt "${min_hours}" ]]; then
    _set_ip_skip "last_change_hours=${last_change_hours} < ${min_hours} (last_change_time=${last_change_time:-<unknown>} log=${change_log})"
    return 0
  fi

  if [[ ! -f "${change_script}" ]]; then
    _set_ip_skip "script not found (${change_script})"
    return 0
  fi

  IP_CHANGE_STATUS="running"
  IP_CHANGE_DETAIL="已触发更换IP：执行中"
  log_line "[Auto] conditions met -> change GCP IP (total=${total} success=${success} last_change_time=${last_change_time:-<unknown>} last_change_hours=${last_change_hours:-<unknown>})"
  set +e
  if [[ -x "${change_script}" ]]; then
    "${change_script}"
  else
    bash "${change_script}"
  fi
  local change_status=$?
  set -e
  if [[ "${change_status}" -eq 0 ]]; then
    log_line "[Auto] change_gcp_ip.sh finished ok"
    IP_CHANGE_STATUS="changed"
    IP_CHANGE_DETAIL="已更换IP：执行成功"
  else
    log_line "[Auto] change_gcp_ip.sh failed (exit=${change_status})"
    IP_CHANGE_STATUS="failed"
    IP_CHANGE_DETAIL="更换IP失败：exit=${change_status}"
  fi
}

maybe_change_gcp_ip

SUMMARY_LINE="$(grep -E '总数:' "$LOG_FILE" | tail -n1 || true)"
DONE_LINE="$(grep -E '注册完成' "$LOG_FILE" | tail -n1 || true)"
if [[ -z "${IP_CHANGE_DETAIL:-}" ]]; then
  IP_CHANGE_DETAIL="未更换IP：未执行"
fi
printf -v RESULT_TEXT '%s\n%s\n%s\n%s\n%s\n%s\n%s\n' \
  "ChatGPT 批量注册完成" \
  "时间: $(date)" \
  "${SUMMARY_LINE}" \
  "${DONE_LINE}" \
  "退出码: ${RUN_STATUS}" \
  "日志: ${LOG_FILE}" \
  "IP更换: ${IP_CHANGE_DETAIL}"

if [[ -n "${TELEGRAM_BOT_TOKEN:-}" && -n "${TELEGRAM_CHAT_ID:-}" ]]; then
  CURL_PROXY_ARGS=()
  if [[ -n "${TELEGRAM_PROXY_URL:-}" ]]; then
    CURL_PROXY_ARGS=(-x "$TELEGRAM_PROXY_URL")
  fi

  curl -sS "${CURL_PROXY_ARGS[@]}" \
    -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
    --data-urlencode "chat_id=${TELEGRAM_CHAT_ID}" \
    --data-urlencode "text=${RESULT_TEXT}" \
    >/dev/null || true
fi
