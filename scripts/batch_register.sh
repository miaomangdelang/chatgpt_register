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
if [[ -f "${CONFIG_PATH}" ]]; then
  CONFIG_TOTAL_ACCOUNTS="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1], "r", encoding="utf-8")).get("total_accounts",""))' "${CONFIG_PATH}" 2>/dev/null || true)"
  CONFIG_MAX_WORKERS="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1], "r", encoding="utf-8")).get("max_workers",""))' "${CONFIG_PATH}" 2>/dev/null || true)"
fi

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

TOTAL_ACCOUNTS="${TOTAL_ACCOUNTS:-}"
MAX_WORKERS="${MAX_WORKERS:-}"
if [[ -z "${TOTAL_ACCOUNTS}" ]]; then
  TOTAL_ACCOUNTS="${CONFIG_TOTAL_ACCOUNTS:-1}"
fi
if [[ -z "${MAX_WORKERS}" ]]; then
  MAX_WORKERS="${CONFIG_MAX_WORKERS:-1}"
fi

echo "[Config] TOTAL_ACCOUNTS=${TOTAL_ACCOUNTS} MAX_WORKERS=${MAX_WORKERS}"
TOTAL_ACCOUNTS="${TOTAL_ACCOUNTS}" MAX_WORKERS="${MAX_WORKERS}" python3 "${ROOT_DIR}/chatgpt_register.py"
