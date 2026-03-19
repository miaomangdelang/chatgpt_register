#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

SECRETS_FILE="$ROOT_DIR/.secrets/mailu.env"
if [[ -f "$SECRETS_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$SECRETS_FILE"
  set +a
fi

: "${MAILU_API_TOKEN:?missing MAILU_API_TOKEN}"

TOTAL_ACCOUNTS="${TOTAL_ACCOUNTS:-25}"
MAX_WORKERS="${MAX_WORKERS:-5}"

LOG_DIR="$ROOT_DIR/logs"
mkdir -p "$LOG_DIR"
TS="$(date +\"%Y%m%d_%H%M%S\")"
LOG_FILE="$LOG_DIR/auto_register_${TS}.log"

echo "[Auto] start: $(date)" | tee -a "$LOG_FILE"
echo "[Auto] total=${TOTAL_ACCOUNTS} workers=${MAX_WORKERS}" | tee -a "$LOG_FILE"

TOTAL_ACCOUNTS="$TOTAL_ACCOUNTS" MAX_WORKERS="$MAX_WORKERS" ./scripts/batch_register.sh | tee -a "$LOG_FILE"

echo "[Auto] done: $(date)" | tee -a "$LOG_FILE"
