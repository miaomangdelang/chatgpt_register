#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-status}"
CONTAINER_NAME="${2:-ubuntu22-warp}"

exec_in_container() {
  docker exec "${CONTAINER_NAME}" bash -lc "$1"
}

wait_for_connected() {
  local status_output=""
  for _ in $(seq 1 15); do
    status_output="$(exec_in_container 'warp-cli --accept-tos status' || true)"
    if grep -q 'Connected' <<<"${status_output}"; then
      printf '%s\n' "${status_output}"
      return 0
    fi
    sleep 2
  done
  printf '%s\n' "${status_output}"
  return 1
}

start_service_if_needed() {
  if ! exec_in_container 'warp-cli --accept-tos status' >/dev/null 2>&1; then
    docker exec -d "${CONTAINER_NAME}" warp-svc
    sleep 2
  fi
}

print_trace() {
  echo "[Host]"
  curl -fsS https://www.cloudflare.com/cdn-cgi/trace | sed -n '1,20p'
  echo
  echo "[Container:${CONTAINER_NAME}]"
  exec_in_container 'curl -fsS https://www.cloudflare.com/cdn-cgi/trace | sed -n "1,20p"'
}

ensure_connected() {
  local status_output
  start_service_if_needed
  status_output="$(exec_in_container 'warp-cli --accept-tos status' || true)"
  if grep -q 'Registration Missing' <<<"${status_output}"; then
    exec_in_container 'warp-cli --accept-tos registration new'
  fi
  status_output="$(exec_in_container 'warp-cli --accept-tos status' || true)"
  if ! grep -q 'Connected' <<<"${status_output}"; then
    exec_in_container 'warp-cli --accept-tos connect'
  fi
  wait_for_connected
}

rotate_ip() {
  start_service_if_needed
  exec_in_container 'warp-cli --accept-tos disconnect || true'
  exec_in_container 'warp-cli --accept-tos registration delete || true'
  exec_in_container 'warp-cli --accept-tos registration new'
  exec_in_container 'warp-cli --accept-tos connect'
  wait_for_connected
  print_trace
}

case "${ACTION}" in
  status)
    start_service_if_needed
    exec_in_container 'warp-cli --accept-tos status'
    print_trace
    ;;
  ensure)
    ensure_connected
    print_trace
    ;;
  rotate)
    rotate_ip
    ;;
  disconnect)
    start_service_if_needed
    exec_in_container 'warp-cli --accept-tos disconnect'
    exec_in_container 'warp-cli --accept-tos status'
    print_trace
    ;;
  trace)
    print_trace
    ;;
  *)
    echo "Usage: $0 {status|ensure|rotate|disconnect|trace} [container_name]"
    exit 1
    ;;
esac
