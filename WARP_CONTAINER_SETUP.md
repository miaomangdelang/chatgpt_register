# WARP Container Setup Notes

## Goal

Provide a Docker container whose outbound traffic can use Cloudflare WARP without changing the host machine's outbound IP, while keeping the project workspace mounted into the container.

## Initial Findings

- The original `ubuntu22` container mounts `/home/miaomangdelang/workspace` to `/workspace`.
- That container runs in normal Docker bridge mode.
- It was created without `NET_ADMIN`.
- It was created without `/dev/net/tun`.

These two missing pieces mean Cloudflare WARP cannot be enabled inside the existing container without recreating it.

## Why A New Container Was Created

The requirement was to change the container's egress IP without affecting the host.

Running WARP on the host would change host networking and violate that requirement. Because the original container lacked the required networking capability and TUN device, a second container was created instead:

- container name: `ubuntu22-warp`
- image: `ubuntu:22.04`
- mount: `/home/miaomangdelang/workspace:/workspace`
- extra capability: `NET_ADMIN`
- device passthrough: `/dev/net/tun`

This keeps host networking separate from container networking while allowing WARP to manage the container's own outbound path.

## Packages Installed In The WARP Container

Base system packages were installed first:

- `ca-certificates`
- `curl`
- `gnupg`
- `iproute2`
- `procps`
- `lsb-release`
- `python3-pip`

Cloudflare's official apt repository was then added, and `cloudflare-warp` was installed.

Because this container image does not use `systemctl`, the WARP daemon is started manually with `warp-svc`.

## Files Added To The Repo

- `requirements.txt`
  - Declares Python dependencies needed by the current project entrypoints.
- `scripts/setup_warp_container.sh`
  - Creates a WARP-capable Docker container and performs first-time setup.
- `scripts/warp_container.sh`
  - Helper for checking WARP status and container egress state.
- `WARP_CONTAINER_SETUP.md`
  - This document.

## Validation Performed

### WARP Connectivity

The `ubuntu22-warp` container was registered with WARP and connected successfully.

Validation used:

- `warp-cli status`
- `https://www.cloudflare.com/cdn-cgi/trace`

Observed result:

- Host remained `warp=off`
- WARP container reported `warp=on`

This confirmed the host IP path stayed unchanged while the container used a WARP egress path.

### Egress Separation

The host and container were checked independently against Cloudflare trace output.

The host continued to use its own public IP, while the WARP container used a different IP and reported `warp=on`.

This verified that the container routing change stayed scoped to the container.

### Project Runtime Validation In The WARP Container

Inside `ubuntu22-warp`:

1. `python3-pip` was installed.
2. `requirements.txt` was installed with `pip`.
3. The project was executed from `/workspace/chatgpt_register`.

A minimal single-account validation run was performed to confirm:

- the workspace mount is usable
- Python dependencies are available
- outbound requests go through the WARP-enabled container
- the application can reach Mailu and OpenAI endpoints from inside the container

## Current Runtime Limitation

The runtime environment works, but the registration flow is still blocked by the remote service at:

- `POST https://auth.openai.com/api/accounts/user/register`

Observed response during the validation run:

- HTTP `400`
- message: `Failed to create account. Please try again.`

This means the current blocker is not container setup, not Python dependency installation, and not WARP connectivity. The remaining issue is in the remote registration step itself or in the request/flow expected by that endpoint.

## Notes About Existing Repo State

This repository already had unrelated uncommitted changes before the WARP work started. Those pre-existing modifications were intentionally not included in the WARP commit.
