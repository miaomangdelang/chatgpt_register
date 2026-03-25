#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

LOCK_FILE="/tmp/chatgpt_register_cpa_upload.lock"
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  echo "[CPA] another run is in progress, exit."
  exit 0
fi

TG_SECRETS_FILE="$ROOT_DIR/.secrets/telegram.env"
if [[ -f "$TG_SECRETS_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$TG_SECRETS_FILE"
  set +a
fi

LOG_DIR="$ROOT_DIR/logs"
mkdir -p "$LOG_DIR"
TS="$(date +%Y%m%d_%H%M%S)"
LOG_FILE="$LOG_DIR/cpa_upload_${TS}.log"

echo "[CPA] start: $(date)" | tee -a "$LOG_FILE"

TOKEN_DIR="$ROOT_DIR/codex_tokens"
CPA_TIME_WINDOW_MINUTES="${CPA_TIME_WINDOW_MINUTES:-1440}"

if [[ ! -d "$TOKEN_DIR" ]]; then
  echo "[CPA] token dir 不存在: $TOKEN_DIR" | tee -a "$LOG_FILE"
  exit 1
fi

mapfile -t TOKEN_FILES < <(find "$TOKEN_DIR" -type f -name "*.json" -mmin "-${CPA_TIME_WINDOW_MINUTES}" | sort)

if [[ ${#TOKEN_FILES[@]} -eq 0 ]]; then
  echo "[CPA] 最近 ${CPA_TIME_WINDOW_MINUTES} 分钟无新账号文件" | tee -a "$LOG_FILE"
  exit 0
fi

CPA_API_URL="${CPA_API_URL:-http://192.168.1.126:8317/v0/management/auth-files}"
CPA_API_TOKEN="${CPA_API_TOKEN:-helloworld}"
CPA_AUTH_DIR="${CPA_AUTH_DIR:-/root/.openclaw/workspace/cli-proxy-api/auth}"
CPA_VERIFY_CONNECT_TIMEOUT="${CPA_VERIFY_CONNECT_TIMEOUT:-3}"
CPA_VERIFY_MAX_TIME="${CPA_VERIFY_MAX_TIME:-8}"
CPA_VERIFY_HARD_TIMEOUT="${CPA_VERIFY_HARD_TIMEOUT:-10}"

CPA_UPLOADED=0
CPA_CONFIRMED=0
CPA_FAILED=0
CPA_LOCAL_WRITES=0
CPA_TOTAL=${#TOKEN_FILES[@]}

# CPA 文件存在性验证（存在返回 0，不存在返回 1，异常返回 2）
cpa_verify_exists() {
  local email="$1"
  local verify_url="${CPA_API_URL}/models"
  local result
  local exit_code
  set +e
  result=$(timeout "$CPA_VERIFY_HARD_TIMEOUT" curl -sS --get "$verify_url" \
    --connect-timeout "$CPA_VERIFY_CONNECT_TIMEOUT" \
    --max-time "$CPA_VERIFY_MAX_TIME" \
    -H "Authorization: Bearer $CPA_API_TOKEN" \
    --data-urlencode "name=${email}.json" 2>&1)
  exit_code=$?
  set -e
  if [[ $exit_code -ne 0 ]]; then
    echo "[CPA] CPA 验证失败: $email - $result" | tee -a "$LOG_FILE"
    return 2
  fi
  if echo "$result" | grep -E -q '"models"\s*:\s*\[\s*\]'; then
    return 1
  fi
  if echo "$result" | grep -q '"models"'; then
    return 0
  fi
  echo "[CPA] CPA 验证响应异常: $email - $result" | tee -a "$LOG_FILE"
  return 2
}

if [[ ! -d "$CPA_AUTH_DIR" ]]; then
  echo "[CPA] CPA auth dir 不存在: $CPA_AUTH_DIR" | tee -a "$LOG_FILE"
  CPA_FAILED=$CPA_TOTAL
else
  for json_file in "${TOKEN_FILES[@]}"; do
    email="$(basename "$json_file" .json)"
    echo "[CPA] 写入: $email" | tee -a "$LOG_FILE"
    dest="$CPA_AUTH_DIR/$(basename "$json_file")"
    if cp -f "$json_file" "$dest"; then
      ((CPA_LOCAL_WRITES++))
      echo "[CPA] 已写入 CPA auth dir: $dest" | tee -a "$LOG_FILE"
      sleep 2
      if cpa_verify_exists "$email"; then
        ((CPA_UPLOADED++))
        ((CPA_CONFIRMED++))
        echo "[CPA] CPA 已确认存在: $email" | tee -a "$LOG_FILE"
      else
        verify_rc=$?
        if [[ $verify_rc -eq 1 ]]; then
          echo "[CPA] CPA 验证未找到: $email" | tee -a "$LOG_FILE"
        else
          echo "[CPA] CPA 验证失败: $email" | tee -a "$LOG_FILE"
        fi
        ((CPA_FAILED++))
      fi
    else
      ((CPA_FAILED++))
      echo "[CPA] 写入 CPA auth dir 失败: $dest" | tee -a "$LOG_FILE"
    fi
  done
fi

echo "[CPA] 上传完成. 总数: $CPA_TOTAL 成功: $CPA_UPLOADED 确认: $CPA_CONFIRMED 失败: $CPA_FAILED 本地写入: $CPA_LOCAL_WRITES" | tee -a "$LOG_FILE"

RESULT_TEXT="CPA 上传完成\n时间: $(date)\n最近${CPA_TIME_WINDOW_MINUTES}分钟: ${CPA_TOTAL}\n成功: ${CPA_UPLOADED} 确认: ${CPA_CONFIRMED} 失败: ${CPA_FAILED} 本地写入: ${CPA_LOCAL_WRITES}\n日志: ${LOG_FILE}"

OPENCLAW_BIN="${OPENCLAW_BIN:-/usr/bin/openclaw}"
OPENCLAW_CHANNEL="${OPENCLAW_CHANNEL:-telegram}"
OPENCLAW_TARGET="${OPENCLAW_TARGET:-${TELEGRAM_CHAT_ID:-}}"
OPENCLAW_PROFILE="${OPENCLAW_PROFILE:-}"

OPENCLAW_ARGS=()
if [[ -n "$OPENCLAW_PROFILE" ]]; then
  OPENCLAW_ARGS+=(--profile "$OPENCLAW_PROFILE")
fi

if [[ -n "$OPENCLAW_TARGET" && -x "$OPENCLAW_BIN" ]]; then
  echo "[CPA] 通过 OpenClaw 发送 Telegram 通知..." | tee -a "$LOG_FILE"
  if "$OPENCLAW_BIN" "${OPENCLAW_ARGS[@]}" message send \
      --channel "$OPENCLAW_CHANNEL" \
      --target "$OPENCLAW_TARGET" \
      --message "$RESULT_TEXT" \
      --silent >/dev/null 2>&1; then
    echo "[CPA] OpenClaw 通知发送成功" | tee -a "$LOG_FILE"
  else
    echo "[CPA] OpenClaw 通知发送失败" | tee -a "$LOG_FILE"
  fi
else
  echo "[CPA] OpenClaw 未配置或不可用，跳过 Telegram 通知" | tee -a "$LOG_FILE"
fi
