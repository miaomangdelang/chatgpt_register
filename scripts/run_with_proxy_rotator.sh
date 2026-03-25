#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ROTATOR_DIR_DEFAULT="${ROOT_DIR}/../proxy-rotator"
ROTATOR_DIR="${ROTATOR_DIR:-${ROTATOR_DIR_DEFAULT}}"
ROTATOR_CONFIG="${ROTATOR_CONFIG:-${ROTATOR_DIR}/config.yaml}"
REFRESH_ARGS=("--refresh")
LOG_DIR="${ROOT_DIR}/logs"
RUN_LOG="${RUN_LOG:-${LOG_DIR}/run_$(date +%Y%m%d_%H%M%S).log}"

TOTAL_ACCOUNTS="${TOTAL_ACCOUNTS:-1}"
MAX_WORKERS="${MAX_WORKERS:-1}"
MAX_ATTEMPTS="${MAX_ATTEMPTS:-3}"
RETRY_ON_REGISTRATION_DISALLOWED="${RETRY_ON_REGISTRATION_DISALLOWED:-1}"
RETRY_DELAY_SECONDS="${RETRY_DELAY_SECONDS:-5}"

OPENCLAW_BIN="${OPENCLAW_BIN:-/home/joing/.npm-global/bin/openclaw}"
TG_CHANNEL="${TG_CHANNEL:-telegram}"
TG_TARGET="${TG_TARGET:-1014334465}"
TG_ACCOUNT="${TG_ACCOUNT:-AUSUbot}"

CLI_PROXY_API_URL_DEFAULT="http://127.0.0.1:8317/v0/management/auth-files"
CLI_PROXY_API_URL="${CLI_PROXY_API_URL:-${CLI_PROXY_API_URL_DEFAULT}}"
CLI_PROXY_API_KEY="${CLI_PROXY_API_KEY:-${CLI_PROXY_MGMT_KEY:-}}"

usage() {
  cat <<'EOF'
Usage:
  ./scripts/run_with_proxy_rotator.sh [--config PATH] [--rotator-dir PATH] [--no-refresh] [--total N] [--workers N]

Env:
  MAILU_API_TOKEN, OAUTH_* (pass-through)
  CLI_PROXY_API_URL, CLI_PROXY_API_KEY (optional; map to UPLOAD_API_URL/UPLOAD_API_TOKEN)
  UPLOAD_API_URL, UPLOAD_API_TOKEN, UPLOAD_PROXY
  TOTAL_ACCOUNTS, MAX_WORKERS
  USE_FIXED_PROXY=0 (auto set by this script)
  MAX_ATTEMPTS, RETRY_ON_REGISTRATION_DISALLOWED, RETRY_DELAY_SECONDS
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --config)
      ROTATOR_CONFIG="$2"
      shift 2
      ;;
    --rotator-dir)
      ROTATOR_DIR="$2"
      shift 2
      ;;
    --no-refresh)
      REFRESH_ARGS=()
      shift
      ;;
    --refresh)
      REFRESH_ARGS=("--refresh")
      shift
      ;;
    --total)
      TOTAL_ACCOUNTS="$2"
      shift 2
      ;;
    --workers)
      MAX_WORKERS="$2"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      break
      ;;
  esac
done

if [[ ! -x "${ROTATOR_DIR}/run_with_selected_proxy.sh" ]]; then
  echo "[Error] proxy-rotator not found: ${ROTATOR_DIR}/run_with_selected_proxy.sh"
  exit 2
fi

export USE_FIXED_PROXY=0
export TOTAL_ACCOUNTS
export MAX_WORKERS
export TG_NOTIFY=0

if [[ -n "${CLI_PROXY_API_KEY}" ]]; then
  export UPLOAD_API_URL="${UPLOAD_API_URL:-${CLI_PROXY_API_URL}}"
  export UPLOAD_API_TOKEN="${UPLOAD_API_TOKEN:-${CLI_PROXY_API_KEY}}"
fi

if [[ -n "${UPLOAD_API_URL:-}" ]]; then
  case "${UPLOAD_API_URL}" in
    http://127.*|http://localhost*|http://[::1]*|https://127.*|https://localhost*|https://[::1]*)
      export NO_PROXY="${NO_PROXY:-127.0.0.1,localhost,::1}"
      ;;
  esac
fi

cd "${ROOT_DIR}"
mkdir -p "${LOG_DIR}"
echo "[Info] proxy-rotator dir: ${ROTATOR_DIR}"
echo "[Info] proxy-rotator config: ${ROTATOR_CONFIG}"
echo "[Info] total_accounts: ${TOTAL_ACCOUNTS} | max_workers: ${MAX_WORKERS}"
echo "[Info] log file: ${RUN_LOG}"
if [[ -n "${UPLOAD_API_URL:-}" && -n "${UPLOAD_API_TOKEN:-}" ]]; then
  echo "[Info] upload api: ${UPLOAD_API_URL}"
else
  echo "[Info] upload api: disabled (missing UPLOAD_API_URL/UPLOAD_API_TOKEN)"
fi

ATTEMPT=1
STATUS=1
LAST_START_LINE=0

while [[ ${ATTEMPT} -le ${MAX_ATTEMPTS} ]]; do
  if [[ -f "${RUN_LOG}" ]]; then
    LAST_START_LINE=$(wc -l < "${RUN_LOG}" | tr -d ' ')
  else
    LAST_START_LINE=0
  fi
  echo "[$(date)] Attempt ${ATTEMPT}/${MAX_ATTEMPTS} start" | tee -a "${RUN_LOG}"

  set +e
  "${ROTATOR_DIR}/run_with_selected_proxy.sh" \
    --config "${ROTATOR_CONFIG}" \
    "${REFRESH_ARGS[@]}" \
    -- \
    bash "${ROOT_DIR}/scripts/batch_register.sh" 2>&1 | tee -a "${RUN_LOG}"
  STATUS=${PIPESTATUS[0]}
  set -e

  if [[ ${STATUS} -eq 0 ]]; then
    echo "[$(date)] Attempt ${ATTEMPT} success" | tee -a "${RUN_LOG}"
    break
  fi

  BLOCK="$(sed -n "$((LAST_START_LINE+1)),\$p" "${RUN_LOG}")"
  if [[ "${RETRY_ON_REGISTRATION_DISALLOWED}" == "1" ]] && echo "${BLOCK}" | grep -q "registration_disallowed"; then
    if [[ ${ATTEMPT} -lt ${MAX_ATTEMPTS} ]]; then
      echo "[$(date)] Detected registration_disallowed, retrying with next proxy..." | tee -a "${RUN_LOG}"
      sleep "${RETRY_DELAY_SECONDS}"
      ATTEMPT=$((ATTEMPT + 1))
      continue
    fi
  fi

  echo "[$(date)] Attempt ${ATTEMPT} failed, no retry" | tee -a "${RUN_LOG}"
  break
done

SUMMARY_BLOCK="$(sed -n "$((LAST_START_LINE+1)),\$p" "${RUN_LOG}")"
SUMMARY_LINE="$(printf '%s\n' "${SUMMARY_BLOCK}" | grep -a "总数:" | tail -1 || true)"
SUCCESS="$(echo "${SUMMARY_LINE}" | sed -n 's/.*成功: \([0-9][0-9]*\).*/\1/p')"
FAILED="$(echo "${SUMMARY_LINE}" | sed -n 's/.*失败: \([0-9][0-9]*\).*/\1/p')"

if [[ -z "${SUCCESS}" ]]; then
  SUCCESS="$(printf '%s\n' "${SUMMARY_BLOCK}" | grep -c "注册成功" 2>/dev/null || echo 0)"
fi
if [[ -z "${FAILED}" ]]; then
  FAILED="$(printf '%s\n' "${SUMMARY_BLOCK}" | grep -c "注册失败" 2>/dev/null || echo 0)"
fi

PROXY_LINE="$(printf '%s\n' "${SUMMARY_BLOCK}" | grep -a "使用代理" | tail -1 || true)"

MSG="ChatGPT 注册任务完成
时间: $(date)
退出码: ${STATUS}
成功: ${SUCCESS}
失败: ${FAILED}
日志: ${RUN_LOG}"
if [[ -n "${PROXY_LINE}" ]]; then
  MSG="${MSG}
${PROXY_LINE}"
fi

if [[ -x "${OPENCLAW_BIN}" ]]; then
  if [[ -n "${TG_ACCOUNT}" ]]; then
    "${OPENCLAW_BIN}" message send --account "${TG_ACCOUNT}" --channel "${TG_CHANNEL}" --target "${TG_TARGET}" --message "${MSG}" >/dev/null 2>&1 || \
      "${OPENCLAW_BIN}" message send --channel "${TG_CHANNEL}" --target "${TG_TARGET}" --message "${MSG}" >/dev/null 2>&1 || true
  else
    "${OPENCLAW_BIN}" message send --channel "${TG_CHANNEL}" --target "${TG_TARGET}" --message "${MSG}" >/dev/null 2>&1 || true
  fi
fi

exit "${STATUS}"
