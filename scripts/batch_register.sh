#!/usr/bin/env bash
set -euo pipefail

# 批量注册入口（非交互）
# 配置文件：config.json（项目根目录）
# 使用方式：
#   export MAILU_API_TOKEN="你的token"
#   TOTAL_ACCOUNTS=10 MAX_WORKERS=3 ./scripts/batch_register.sh

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_PATH="${ROOT_DIR}/config.json"

CONFIG_TOTAL_ACCOUNTS=""
CONFIG_MAX_WORKERS=""
CONFIG_PROXY_CHECK_ONLY=""
CONFIG_DIRECT_TEST_URL=""
CONFIG_DIRECT_TEST_TIMEOUT=""
CONFIG_DIRECT_TEST_INTERVAL=""
CONFIG_DIRECT_TEST_PROXY_RAW="__MISSING__"
CONFIG_DIRECT_TEST_PROXY_HAS="0"
CONFIG_PROXY_TEST_URL=""
CONFIG_PROXY_TEST_TIMEOUT=""
CONFIG_PROXY_TEST_INTERVAL=""
if [[ -f "${CONFIG_PATH}" ]]; then
  CONFIG_TOTAL_ACCOUNTS="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1], "r", encoding="utf-8")).get("total_accounts",""))' "${CONFIG_PATH}" 2>/dev/null || true)"
  CONFIG_MAX_WORKERS="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1], "r", encoding="utf-8")).get("max_workers",""))' "${CONFIG_PATH}" 2>/dev/null || true)"
  CONFIG_PROXY_CHECK_ONLY="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1], "r", encoding="utf-8")).get("proxy_check_only",""))' "${CONFIG_PATH}" 2>/dev/null || true)"
  CONFIG_DIRECT_TEST_URL="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1], "r", encoding="utf-8")).get("direct_test_url",""))' "${CONFIG_PATH}" 2>/dev/null || true)"
  CONFIG_DIRECT_TEST_TIMEOUT="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1], "r", encoding="utf-8")).get("direct_test_timeout",""))' "${CONFIG_PATH}" 2>/dev/null || true)"
  CONFIG_DIRECT_TEST_INTERVAL="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1], "r", encoding="utf-8")).get("direct_test_interval",""))' "${CONFIG_PATH}" 2>/dev/null || true)"
  CONFIG_DIRECT_TEST_PROXY_RAW="$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1], "r", encoding="utf-8")); print(d.get("direct_test_proxy","__MISSING__"))' "${CONFIG_PATH}" 2>/dev/null || echo "__MISSING__")"
  if [[ "${CONFIG_DIRECT_TEST_PROXY_RAW}" != "__MISSING__" ]]; then
    CONFIG_DIRECT_TEST_PROXY_HAS="1"
  fi
  CONFIG_PROXY_TEST_URL="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1], "r", encoding="utf-8")).get("proxy_test_url",""))' "${CONFIG_PATH}" 2>/dev/null || true)"
  CONFIG_PROXY_TEST_TIMEOUT="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1], "r", encoding="utf-8")).get("proxy_test_timeout",""))' "${CONFIG_PATH}" 2>/dev/null || true)"
  CONFIG_PROXY_TEST_INTERVAL="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1], "r", encoding="utf-8")).get("proxy_test_interval",""))' "${CONFIG_PATH}" 2>/dev/null || true)"
fi

TOTAL_ACCOUNTS="${TOTAL_ACCOUNTS:-}"
MAX_WORKERS="${MAX_WORKERS:-}"
if [[ -z "${TOTAL_ACCOUNTS}" ]]; then
  TOTAL_ACCOUNTS="${CONFIG_TOTAL_ACCOUNTS:-1}"
fi
if [[ -z "${MAX_WORKERS}" ]]; then
  MAX_WORKERS="${CONFIG_MAX_WORKERS:-1}"
fi

# 当所有邮箱创建失败时的重试控制（可通过环境变量覆盖）
RETRY_WAIT_SECONDS="${RETRY_WAIT_SECONDS:-600}"
RETRY_MAX_ATTEMPTS="${RETRY_MAX_ATTEMPTS:-5}"

# 直连/代理可用性检测（可通过环境变量覆盖）
DIRECT_TEST_URL="${DIRECT_TEST_URL:-}"
DIRECT_TEST_TIMEOUT="${DIRECT_TEST_TIMEOUT:-}"
DIRECT_TEST_INTERVAL="${DIRECT_TEST_INTERVAL:-}"
PROXY_TEST_URL="${PROXY_TEST_URL:-}"
PROXY_TEST_TIMEOUT="${PROXY_TEST_TIMEOUT:-}"
PROXY_TEST_INTERVAL="${PROXY_TEST_INTERVAL:-}"
PROXY_CHECK_ONLY="${PROXY_CHECK_ONLY:-}"
if [[ -z "${PROXY_CHECK_ONLY}" ]]; then
  PROXY_CHECK_ONLY="${CONFIG_PROXY_CHECK_ONLY:-0}"
fi
if [[ -z "${DIRECT_TEST_URL}" ]]; then
  DIRECT_TEST_URL="${CONFIG_DIRECT_TEST_URL:-}"
fi
if [[ -z "${DIRECT_TEST_URL}" ]]; then
  DIRECT_TEST_URL="https://mail.oracle.311200.xyz/"
fi
if [[ -z "${DIRECT_TEST_TIMEOUT}" ]]; then
  DIRECT_TEST_TIMEOUT="${CONFIG_DIRECT_TEST_TIMEOUT:-}"
fi
if [[ -z "${DIRECT_TEST_TIMEOUT}" ]]; then
  DIRECT_TEST_TIMEOUT="20"
fi
if [[ -z "${DIRECT_TEST_INTERVAL}" ]]; then
  DIRECT_TEST_INTERVAL="${CONFIG_DIRECT_TEST_INTERVAL:-}"
fi
if [[ -z "${DIRECT_TEST_INTERVAL}" ]]; then
  DIRECT_TEST_INTERVAL="60"
fi
if [[ "${DIRECT_TEST_PROXY+x}" == "x" ]]; then
  DIRECT_TEST_PROXY="${DIRECT_TEST_PROXY}"
else
  if [[ "${CONFIG_DIRECT_TEST_PROXY_HAS}" == "1" ]]; then
    DIRECT_TEST_PROXY="${CONFIG_DIRECT_TEST_PROXY_RAW}"
  else
    DIRECT_TEST_PROXY="http://192.168.1.108:7890"
  fi
fi
if [[ -z "${PROXY_TEST_URL}" ]]; then
  PROXY_TEST_URL="${CONFIG_PROXY_TEST_URL:-}"
fi
if [[ -z "${PROXY_TEST_URL}" ]]; then
  PROXY_TEST_URL="https://openai.com/robots.txt"
fi
if [[ -z "${PROXY_TEST_TIMEOUT}" ]]; then
  PROXY_TEST_TIMEOUT="${CONFIG_PROXY_TEST_TIMEOUT:-}"
fi
if [[ -z "${PROXY_TEST_TIMEOUT}" ]]; then
  PROXY_TEST_TIMEOUT="20"
fi
if [[ -z "${PROXY_TEST_INTERVAL}" ]]; then
  PROXY_TEST_INTERVAL="${CONFIG_PROXY_TEST_INTERVAL:-}"
fi
if [[ -z "${PROXY_TEST_INTERVAL}" ]]; then
  PROXY_TEST_INTERVAL="60"
fi

# 为 cron.log 统一加时间戳（可通过环境变量关闭）
LOG_PREFIX_ALL="${LOG_PREFIX_ALL:-1}"
if [[ "${LOG_PREFIX_ALL}" == "1" || "${LOG_PREFIX_ALL,,}" == "true" || "${LOG_PREFIX_ALL,,}" == "yes" || "${LOG_PREFIX_ALL,,}" == "on" ]]; then
  ts_regex='^\[[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}[+-][0-9]{4}\]'
  exec > >(
    while IFS= read -r line; do
      if [[ "${line}" =~ ${ts_regex} ]]; then
        printf '%s\n' "${line}"
      else
        printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S%z')" "${line}"
      fi
    done
  ) 2>&1
fi

_get_env() {
  local key="$1"
  local val=""
  set +e
  val="$(printenv "${key}" 2>/dev/null)"
  set -e
  printf '%s' "${val}"
}

_resolve_proxy_for_test() {
  local use_fixed="${USE_FIXED_PROXY:-false}"
  local fixed_proxy="${FIXED_PROXY:-}"

  # 优先使用 config.json 的 proxy
  local cfg="${ROOT_DIR}/config.json"
  if [[ -f "${cfg}" ]]; then
    local cfg_proxy=""
    cfg_proxy="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1], "r", encoding="utf-8")).get("proxy",""))' "${cfg}" 2>/dev/null || true)"
    if [[ -n "${cfg_proxy}" ]]; then
      echo "${cfg_proxy}"
      return 0
    fi
  fi

  if [[ "${use_fixed}" == "1" || "${use_fixed,,}" == "true" || "${use_fixed,,}" == "yes" || "${use_fixed,,}" == "on" ]]; then
    if [[ -n "${fixed_proxy}" ]]; then
      echo "${fixed_proxy}"
      return 0
    fi
  fi

  local key val
  for key in PROXY HTTP_PROXY http_proxy HTTPS_PROXY https_proxy ALL_PROXY all_proxy; do
    val="$(_get_env "${key}")"
    if [[ -n "${val}" ]]; then
      echo "${val}"
      return 0
    fi
  done

  echo ""
}

_build_curl_proxy_args() {
  local proxy="$1"
  if [[ -z "${proxy}" ]]; then
    return 0
  fi
  if [[ "${proxy}" == socks5h://* ]]; then
    local hp="${proxy#socks5h://}"
    CURL_PROXY_ARGS=(--socks5-hostname "${hp}")
    return 0
  fi
  if [[ "${proxy}" == socks5://* ]]; then
    local hp="${proxy#socks5://}"
    CURL_PROXY_ARGS=(--socks5 "${hp}")
    return 0
  fi
  CURL_PROXY_ARGS=(-x "${proxy}")
}

_test_url_once() {
  local tag="$1"
  local url="$2"
  local proxy="$3"
  local timeout="$4"
  local proxy_label="${proxy}"
  if [[ -z "${proxy_label}" ]]; then
    proxy_label="<none>"
  fi
  local CURL_PROXY_ARGS=()
  _build_curl_proxy_args "${proxy}"
  _log "[${tag}] 测试 ${url} ... (proxy=${proxy_label})"
  if curl -fsSL --max-time "${timeout}" "${CURL_PROXY_ARGS[@]}" "${url}" -o /dev/null; then
    _log "[${tag}] 测试成功"
    return 0
  fi
  _log "[${tag}] 测试失败"
  return 1
}

_wait_for_network_ready() {
  local direct_proxy="$1"
  local proxy_proxy="$2"
  while true; do
    local direct_ok="0"
    local proxy_ok="0"
    if _test_url_once "DirectCheck" "${DIRECT_TEST_URL}" "${direct_proxy}" "${DIRECT_TEST_TIMEOUT}"; then
      direct_ok="1"
    fi
    if [[ -z "${proxy_proxy}" ]]; then
      _log "[ProxyCheck] 未配置代理，跳过代理测试"
      proxy_ok="1"
    else
      if _test_url_once "ProxyCheck" "${PROXY_TEST_URL}" "${proxy_proxy}" "${PROXY_TEST_TIMEOUT}"; then
        proxy_ok="1"
      fi
    fi
    if [[ "${direct_ok}" == "1" && "${proxy_ok}" == "1" ]]; then
      _log "[NetCheck] 直连/代理均成功"
      break
    fi
    local sleep_for="0"
    if [[ "${direct_ok}" == "0" && "${DIRECT_TEST_INTERVAL}" -gt "${sleep_for}" ]]; then
      sleep_for="${DIRECT_TEST_INTERVAL}"
    fi
    if [[ "${proxy_ok}" == "0" && "${PROXY_TEST_INTERVAL}" -gt "${sleep_for}" ]]; then
      sleep_for="${PROXY_TEST_INTERVAL}"
    fi
    if [[ "${sleep_for}" -le 0 ]]; then
      sleep_for="60"
    fi
    _log "[NetCheck] 直连/代理有失败，${sleep_for}s 后重试"
    sleep "${sleep_for}"
  done
}

if [[ -z "${MAILU_API_TOKEN:-}" ]]; then
  if [[ -f "${CONFIG_PATH}" ]]; then
    MAILU_API_TOKEN="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1], "r", encoding="utf-8")).get("mailu_api_token",""))' "${CONFIG_PATH}" 2>/dev/null || true)"
    export MAILU_API_TOKEN
  fi
fi

if [[ -z "${MAILU_API_TOKEN:-}" ]]; then
  echo "缺少 MAILU_API_TOKEN，请先 export MAILU_API_TOKEN=..."
  exit 1
fi

_resolve_log_file() {
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

_analyze_last_batch() {
  local log_path="$1"
  local expected_total="$2"
  python3 - "${log_path}" "${expected_total}" <<'PY'
import json
import os
import sys

log_path = sys.argv[1]
try:
    expected_total = int(sys.argv[2])
except Exception:
    expected_total = 0

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

last_start = None
for i in range(len(events) - 1, -1, -1):
    if events[i].get("event") == "batch_start":
        last_start = i
        break

if last_start is None:
    sys.exit(0)

batch = events[last_start:]
success = None
failed = None
total = None
for ev in reversed(batch):
    if ev.get("event") == "batch_end":
        success = ev.get("success")
        failed = ev.get("failed")
        total = ev.get("total_accounts")
        break

if success is None:
    success = sum(1 for ev in batch if ev.get("event") == "register_success")
    failed = sum(1 for ev in batch if ev.get("event") == "register_fail")
    total = success + failed

if not total:
    total = expected_total

fail_errors = [ev.get("error", "") for ev in batch if ev.get("event") == "register_fail"]
mailbox_kw = [
    "Mailu 创建邮箱失败",
    "创建邮箱失败",
    "邮箱还没有创建",
    "邮箱未创建",
    "无法创建邮箱",
]
mailbox_fail = 0
for err in fail_errors:
    if any(k in (err or "") for k in mailbox_kw):
        mailbox_fail += 1

all_mailbox_fail = bool(fail_errors) and mailbox_fail == len(fail_errors) and int(success or 0) == 0

print(f"SUCCESS={int(success or 0)}")
print(f"FAILED={int(failed or 0)}")
print(f"TOTAL={int(total)}")
print(f"ALL_MAILBOX_FAIL={'1' if all_mailbox_fail else '0'}")
PY
}

LOG_FILE="$(_resolve_log_file)"

_ts() {
  date '+%Y-%m-%d %H:%M:%S%z'
}

_log() {
  local msg="$1"
  if [[ -n "${LOG_FILE:-}" ]]; then
    echo "[$(_ts)] ${msg}" | tee -a "${LOG_FILE}"
  else
    echo "[$(_ts)] ${msg}"
  fi
}

_run_once() {
  TOTAL_ACCOUNTS="${TOTAL_ACCOUNTS}" MAX_WORKERS="${MAX_WORKERS}" python3 "${ROOT_DIR}/chatgpt_register.py"
}

_log "[Config] TOTAL_ACCOUNTS=${TOTAL_ACCOUNTS} MAX_WORKERS=${MAX_WORKERS} PROXY_CHECK_ONLY=${PROXY_CHECK_ONLY} DIRECT_TEST_URL=${DIRECT_TEST_URL} DIRECT_TEST_PROXY=${DIRECT_TEST_PROXY:-} DIRECT_TEST_TIMEOUT=${DIRECT_TEST_TIMEOUT} DIRECT_TEST_INTERVAL=${DIRECT_TEST_INTERVAL} PROXY_TEST_URL=${PROXY_TEST_URL} PROXY_TEST_TIMEOUT=${PROXY_TEST_TIMEOUT} PROXY_TEST_INTERVAL=${PROXY_TEST_INTERVAL} LOG_FILE=${LOG_FILE}"

proxy_for_test="$(_resolve_proxy_for_test)"
direct_proxy_for_test="${DIRECT_TEST_PROXY:-}"
_wait_for_network_ready "${direct_proxy_for_test}" "${proxy_for_test}"

if [[ "${PROXY_CHECK_ONLY:-0}" == "1" || "${PROXY_CHECK_ONLY,,}" == "true" || "${PROXY_CHECK_ONLY,,}" == "yes" || "${PROXY_CHECK_ONLY,,}" == "on" ]]; then
  _log "[ProxyCheck] PROXY_CHECK_ONLY=1，结束测试，不继续注册流程"
  exit 0
fi

attempt=1
while true; do
  if [[ "${RETRY_MAX_ATTEMPTS}" -gt 1 ]]; then
    echo "[AutoRetry] 尝试 ${attempt}/${RETRY_MAX_ATTEMPTS}..."
  fi
  set +e
  _run_once
  exit_code=$?
  set -e

  success=0
  failed=0
  total="${TOTAL_ACCOUNTS}"
  all_mailbox_fail=0
  if [[ -n "${LOG_FILE}" && -f "${LOG_FILE}" ]]; then
    analysis="$(_analyze_last_batch "${LOG_FILE}" "${TOTAL_ACCOUNTS}" || true)"
    if [[ -n "${analysis}" ]]; then
      while IFS= read -r line; do
        case "${line}" in
          SUCCESS=*) success="${line#SUCCESS=}" ;;
          FAILED=*) failed="${line#FAILED=}" ;;
          TOTAL=*) total="${line#TOTAL=}" ;;
          ALL_MAILBOX_FAIL=*) all_mailbox_fail="${line#ALL_MAILBOX_FAIL=}" ;;
        esac
      done <<< "${analysis}"
    fi
  fi

  if [[ "${all_mailbox_fail}" == "1" && "${attempt}" -lt "${RETRY_MAX_ATTEMPTS}" ]]; then
    echo "[AutoRetry] 本次共 ${total} 个账号均在邮箱创建阶段失败，${RETRY_WAIT_SECONDS}s 后重试..."
    attempt=$((attempt + 1))
    sleep "${RETRY_WAIT_SECONDS}"
    continue
  fi

  exit "${exit_code}"
done
