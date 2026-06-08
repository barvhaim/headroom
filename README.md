# Headroom — Claude Code gateway fork

A private fork of [Headroom](https://github.com/chopratejas/headroom) configured for **one job**:
run the local compression proxy in front of an **Anthropic-compatible LLM gateway** so that
**Claude Code** sends fewer tokens upstream, with no data leaving the machine beyond the
LLM traffic itself.

```
Claude Code ──> http://127.0.0.1:8787  (Headroom proxy, local)
                     │  compresses tool outputs / context
                     ▼
            <your Anthropic-compatible gateway>
                     ▼
                 Claude models
```

Your `ANTHROPIC_AUTH_TOKEN` and the `anthropic-beta: context-1m-2025-08-07` header are
forwarded to the gateway **unchanged** — the proxy holds no credentials.

> This README documents only this fork's deployment. The full upstream feature set
> (other agents, integrations, MCP, hosted modes, benchmarks) is intentionally not
> covered here. See [upstream](https://github.com/chopratejas/headroom) for that.

## What this fork changes vs upstream

- **Telemetry is OFF by default** (opt-in). Upstream ships it on; here it never phones
  home unless `HEADROOM_TELEMETRY=on` is set explicitly.
- **Pinned, offline model cache.** The Docker image bakes the HuggingFace models at
  audited commit SHAs and runs with `HF_HUB_OFFLINE=1`, so it can never silently pull a
  newer model revision. See `docker/precache_models.py`.
- **`scripts/headroom-ete.sh`** — one-command launcher with the gateway upstream baked in.

## Install (build from this fork)

Build from source so the deployed code is exactly what's in this repo — do **not** pull
prebuilt PyPI/Docker artifacts.

```bash
git clone git@github.com:barvhaim/headroom.git && cd headroom
uv sync --extra proxy           # core proxy + text compression (Python 3.10+)
```

This builds the Rust extension (via maturin) and installs the proxy into a local
`.venv`. Prefix commands with `uv run` to use it (e.g. `uv run headroom --version`).

Or build the hardened Docker image (telemetry off, pinned offline models):

```bash
docker build -t headroom-gateway .
```

## Run

Set your gateway URL once, then start the proxy:

```bash
export ANTHROPIC_TARGET_API_URL="https://your-gateway.example.com"

scripts/headroom-ete.sh                       # starts the proxy on port 8787
HEADROOM_PORT=9000 scripts/headroom-ete.sh    # custom port
```

The launcher reads `ANTHROPIC_TARGET_API_URL` for the upstream, forces telemetry off,
uses the `anthropic` backend, and prints the exact `ANTHROPIC_BASE_URL` to configure. It
runs `headroom` from PATH if available, otherwise falls back to `uv run` against the
repo's `.venv` — so it works straight after `uv sync` with no activation needed.

## Point Claude Code at the proxy

In `~/.claude/settings.json`, change **only** the base URL — keep your token and headers:

```json
{
  "env": {
    "ANTHROPIC_BASE_URL": "http://127.0.0.1:8787",
    "ANTHROPIC_AUTH_TOKEN": "sk-...your gateway token...",
    "ANTHROPIC_CUSTOM_HEADERS": "anthropic-beta: context-1m-2025-08-07",
    "ANTHROPIC_BETAS": "context-1m-2025-08-07"
  }
}
```

## Verify it's working

```bash
curl -s http://127.0.0.1:8787/readyz                       # -> 200 when ready
curl -s http://127.0.0.1:8787/stats | python3 -m json.tool # tokens.saved > 0 after use
```

Verified end-to-end against the gateway: requests return `200`, auth + the 1M-context beta
are forwarded, and real Claude Code tool-output payloads compress (~23% on a sample
`tool_result`). Compression engages on tool outputs / large context — short prompts pass
through unchanged, which is expected.

## Notes & gotchas

- **Use a gateway-allowlisted model.** Gateways typically accept only specific model IDs
  (e.g. `claude-opus-4-8`, `claude-sonnet-4-6`, `claude-sonnet-4-5-20250929`,
  `claude-haiku-4-5-20251001`). A non-allowlisted name returns `401` from the gateway — the
  proxy forwards the model name unchanged, so this is a gateway constraint, not a proxy issue.
- **Keep prompt content on-prem:** do **not** set `HEADROOM_API_KEY` (that enables an
  opt-in hosted-compression mode that would POST message content off-box). Leave
  `HEADROOM_TELEMETRY` at its default `off`.
- **Models:** the runtime downloads `chopratejas/kompress-base` +
  `answerdotai/ModernBERT-base` from HuggingFace on first use (or uses the baked, pinned
  cache in the Docker image). To pin/update revisions, edit `docker/precache_models.py`.

## License

Apache 2.0 — see [LICENSE](LICENSE). Upstream: <https://github.com/chopratejas/headroom>.
