#!/usr/bin/env bash
set -euo pipefail

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

: "${MAILU_API_TOKEN:?missing MAILU_API_TOKEN}"

TOTAL_ACCOUNTS="${TOTAL_ACCOUNTS:-25}"
MAX_WORKERS="${MAX_WORKERS:-5}"

LOG_DIR="$ROOT_DIR/logs"
mkdir -p "$LOG_DIR"
TS="$(date +%Y%m%d_%H%M%S)"
LOG_FILE="$LOG_DIR/auto_register_${TS}.log"

echo "[Auto] start: $(date)" | tee -a "$LOG_FILE"
echo "[Auto] total=${TOTAL_ACCOUNTS} workers=${MAX_WORKERS}" | tee -a "$LOG_FILE"

set +e
TOTAL_ACCOUNTS="$TOTAL_ACCOUNTS" MAX_WORKERS="$MAX_WORKERS" ./scripts/batch_register.sh | tee -a "$LOG_FILE"
RUN_STATUS=${PIPESTATUS[0]}
set -e

echo "[Auto] done: $(date)" | tee -a "$LOG_FILE"

SUMMARY_LINE="$(grep -E '总数:' "$LOG_FILE" | tail -n1 || true)"
DONE_LINE="$(grep -E '注册完成' "$LOG_FILE" | tail -n1 || true)"
RESULT_TEXT="ChatGPT 批量注册完成\n时间: $(date)\n${SUMMARY_LINE}\n${DONE_LINE}\n退出码: ${RUN_STATUS}\n日志: ${LOG_FILE}"

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
