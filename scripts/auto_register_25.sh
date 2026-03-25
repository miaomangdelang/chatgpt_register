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

TOTAL_ACCOUNTS="${TOTAL_ACCOUNTS:-1}"
MAX_WORKERS="${MAX_WORKERS:-5}"

LOG_DIR="$ROOT_DIR/logs"
mkdir -p "$LOG_DIR"
TS="$(date +%Y%m%d_%H%M%S)"
LOG_FILE="$LOG_DIR/auto_register_${TS}.log"

echo "[Auto] start: $(date)" | tee -a "$LOG_FILE"
echo "[Auto] total=${TOTAL_ACCOUNTS} workers=${MAX_WORKERS}" | tee -a "$LOG_FILE"

set +e
TOTAL_ACCOUNTS="$TOTAL_ACCOUNTS" MAX_WORKERS="$MAX_WORKERS" UPLOAD_API_URL="" UPLOAD_API_TOKEN="" ./scripts/batch_register.sh | tee -a "$LOG_FILE"
RUN_STATUS=${PIPESTATUS[0]}
set -e

echo "[Auto] done: $(date)" | tee -a "$LOG_FILE"

SUMMARY_LINE="$(grep -E '总数:' "$LOG_FILE" | tail -n1 || true)"
DONE_LINE="$(grep -E '注册完成' "$LOG_FILE" | tail -n1 || true)"
RESULT_TEXT="ChatGPT 批量注册完成\n时间: $(date)\n${SUMMARY_LINE}\n${DONE_LINE}\n退出码: ${RUN_STATUS}\n日志: ${LOG_FILE}"

echo "[Auto] CPA 上传已改为每日 06:00 批量处理（过去 24h 创建的账号）" | tee -a "$LOG_FILE"
RESULT_TEXT="${RESULT_TEXT}\nCPA上传: 每日06:00上传过去24小时创建的账号"

OPENCLAW_BIN="${OPENCLAW_BIN:-/usr/bin/openclaw}"
OPENCLAW_CHANNEL="${OPENCLAW_CHANNEL:-telegram}"
OPENCLAW_TARGET="${OPENCLAW_TARGET:-${TELEGRAM_CHAT_ID:-}}"
OPENCLAW_PROFILE="${OPENCLAW_PROFILE:-}"

OPENCLAW_ARGS=()
if [[ -n "$OPENCLAW_PROFILE" ]]; then
  OPENCLAW_ARGS+=(--profile "$OPENCLAW_PROFILE")
fi

if [[ -n "$OPENCLAW_TARGET" && -x "$OPENCLAW_BIN" ]]; then
  echo "[Auto] 通过 OpenClaw 发送 Telegram 通知..." | tee -a "$LOG_FILE"
  if "$OPENCLAW_BIN" "${OPENCLAW_ARGS[@]}" message send \
      --channel "$OPENCLAW_CHANNEL" \
      --target "$OPENCLAW_TARGET" \
      --message "$RESULT_TEXT" \
      --silent 2>>"$LOG_FILE"; then
    echo "[Auto] OpenClaw 通知发送成功" | tee -a "$LOG_FILE"
  else
    echo "[Auto] OpenClaw 通知发送失败" | tee -a "$LOG_FILE"
  fi
else
  echo "[Auto] OpenClaw 未配置或不可用，跳过 Telegram 通知" | tee -a "$LOG_FILE"
fi
