#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# Rhino Drishti — Render Start Script (Local DB mode via Tailscale)
# ─────────────────────────────────────────────────────────────────────────────
# Paste the CONTENTS of this file as the "Start Command" in Render:
# Dashboard → Your Service → Settings → Start Command
#
# Required Render environment variables:
#   TAILSCALE_AUTH_KEY  — from tailscale.com/admin/settings/keys (reusable + ephemeral)
#   MONGO_URL           — mongodb://rhinodrishti:<pass>@<tailscale-ip>:27017/rhino_drishti
# ─────────────────────────────────────────────────────────────────────────────

set -e

echo "=== Rhino Drishti Startup ==="
echo "Mode: Local DB via Tailscale VPN"

# ── Install Tailscale ─────────────────────────────────────────────────────────
if ! command -v tailscale &>/dev/null; then
    echo "Installing Tailscale..."
    curl -fsSL https://tailscale.com/install.sh | sh
fi

# ── Connect to Tailscale ──────────────────────────────────────────────────────
if [ -n "$TAILSCALE_AUTH_KEY" ]; then
    echo "Connecting to Tailscale..."
    tailscale up \
        --authkey="$TAILSCALE_AUTH_KEY" \
        --hostname="render-rhinodrishti-api" \
        --ephemeral \
        --accept-routes \
        2>&1 || true

    echo "Waiting for VPN tunnel to form..."
    sleep 6

    TAILSCALE_IP=$(tailscale ip -4 2>/dev/null || echo "unknown")
    echo "Render Tailscale IP: $TAILSCALE_IP"
else
    echo "WARNING: TAILSCALE_AUTH_KEY not set — using direct MONGO_URL (Atlas fallback)"
fi

# ── Start FastAPI ─────────────────────────────────────────────────────────────
echo "Starting FastAPI server on port ${PORT:-8001}..."
exec uvicorn server:app --host 0.0.0.0 --port "${PORT:-8001}"
