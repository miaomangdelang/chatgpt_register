#!/usr/bin/env bash
set -euo pipefail

# 批量注册入口（非交互）
# 使用方式：
#   export MAILU_API_TOKEN="你的token"
#   TOTAL_ACCOUNTS=10 MAX_WORKERS=3 ./scripts/batch_register.sh

TOTAL_ACCOUNTS="${TOTAL_ACCOUNTS:-1}"
MAX_WORKERS="${MAX_WORKERS:-1}"

if [[ -z "${MAILU_API_TOKEN:-}" ]]; then
  CONFIG_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/config.json"
  if [[ -f "${CONFIG_PATH}" ]]; then
    MAILU_API_TOKEN="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1], "r", encoding="utf-8")).get("mailu_api_token",""))' "${CONFIG_PATH}" 2>/dev/null || true)"
    export MAILU_API_TOKEN
  fi
fi

if [[ -z "${MAILU_API_TOKEN:-}" ]]; then
  echo "缺少 MAILU_API_TOKEN，请先 export MAILU_API_TOKEN=..."
  exit 1
fi

printf "%s\n%s\n" "$TOTAL_ACCOUNTS" "$MAX_WORKERS" | python3 chatgpt_register.py
