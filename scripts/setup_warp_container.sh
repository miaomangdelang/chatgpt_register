#!/usr/bin/env bash
set -euo pipefail

CONTAINER_NAME="${1:-ubuntu22-warp}"
IMAGE_NAME="${IMAGE_NAME:-ubuntu:22.04}"
WORKSPACE_SOURCE="${WORKSPACE_SOURCE:-/home/miaomangdelang/workspace}"
WORKSPACE_DEST="${WORKSPACE_DEST:-/workspace}"

if docker inspect "${CONTAINER_NAME}" >/dev/null 2>&1; then
  echo "Container already exists: ${CONTAINER_NAME}"
  echo "If you want a fresh one, remove it first or use a different name."
  exit 1
fi

docker run -d \
  --name "${CONTAINER_NAME}" \
  --restart unless-stopped \
  --cap-add=NET_ADMIN \
  --device=/dev/net/tun \
  -v "${WORKSPACE_SOURCE}:${WORKSPACE_DEST}" \
  "${IMAGE_NAME}" \
  tail -f /dev/null

docker exec "${CONTAINER_NAME}" bash -lc 'apt-get update'
docker exec "${CONTAINER_NAME}" bash -lc 'DEBIAN_FRONTEND=noninteractive apt-get install -y ca-certificates curl gnupg iproute2 procps lsb-release'
docker exec "${CONTAINER_NAME}" bash -lc 'set -e; install -d -m 0755 /usr/share/keyrings; curl -fsSL https://pkg.cloudflareclient.com/pubkey.gpg | gpg --dearmor -o /usr/share/keyrings/cloudflare-warp-archive-keyring.gpg; echo "deb [signed-by=/usr/share/keyrings/cloudflare-warp-archive-keyring.gpg] https://pkg.cloudflareclient.com/ $(lsb_release -cs) main" > /etc/apt/sources.list.d/cloudflare-client.list'
docker exec "${CONTAINER_NAME}" bash -lc 'apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y cloudflare-warp'
docker exec -d "${CONTAINER_NAME}" warp-svc
sleep 2
docker exec "${CONTAINER_NAME}" bash -lc 'warp-cli --accept-tos registration new'
docker exec "${CONTAINER_NAME}" bash -lc 'warp-cli --accept-tos connect'
docker exec "${CONTAINER_NAME}" bash -lc 'warp-cli --accept-tos status'
docker exec "${CONTAINER_NAME}" bash -lc 'curl -fsS https://www.cloudflare.com/cdn-cgi/trace | sed -n "1,20p"'
