#!/usr/bin/env bash
# Launch the Headroom proxy in front of the IBM ETE LiteLLM gateway.
#
# This bakes in the deployment config verified for ETE-backed Claude Code:
#   - upstream    : the ETE LiteLLM gateway (Anthropic-compatible /v1/messages)
#   - telemetry   : OFF (this fork defaults to off; set here too, belt-and-suspenders)
#   - backend     : anthropic
#
# The proxy forwards the inbound Authorization (your ANTHROPIC_AUTH_TOKEN) and
# the anthropic-beta header through to ETE unchanged, so the launcher itself
# holds NO secret — keep the token in ~/.claude/settings.json only.
#
# Usage:
#   scripts/headroom-ete.sh                 # start on port 8787
#   HEADROOM_PORT=9000 scripts/headroom-ete.sh
#   ANTHROPIC_TARGET_API_URL=https://other-gw scripts/headroom-ete.sh   # override upstream
#
# Then point Claude Code at the proxy (keep your token + headers as-is):
#   ~/.claude/settings.json:  "ANTHROPIC_BASE_URL": "http://127.0.0.1:8787"
set -euo pipefail

# Default ETE gateway (override by exporting ANTHROPIC_TARGET_API_URL).
ANTHROPIC_TARGET_API_URL="${ANTHROPIC_TARGET_API_URL:-https://ete-litellm.ai-models.vpc-int.res.ibm.com}"
HEADROOM_PORT="${HEADROOM_PORT:-8787}"

# Telemetry stays off for this deployment.
export HEADROOM_TELEMETRY="${HEADROOM_TELEMETRY:-off}"
export ANTHROPIC_TARGET_API_URL

echo "Headroom → ETE"
echo "  upstream:  ${ANTHROPIC_TARGET_API_URL}"
echo "  port:      ${HEADROOM_PORT}"
echo "  telemetry: ${HEADROOM_TELEMETRY}"
echo
echo "Point Claude Code at this proxy (keep your token + headers):"
echo "  ~/.claude/settings.json → \"ANTHROPIC_BASE_URL\": \"http://127.0.0.1:${HEADROOM_PORT}\""
echo

exec headroom proxy --port "${HEADROOM_PORT}" --backend anthropic "$@"
