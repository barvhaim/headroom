#!/usr/bin/env python3
"""Pre-cache Headroom's HuggingFace models at PINNED revisions into HF_HOME.

Why this exists
---------------
At runtime, Headroom downloads model files via ``hf_hub_download_local_first``
and ``transformers.from_pretrained`` WITHOUT a ``revision=`` argument, so a cold
cache fetches whatever ``main`` currently points to. For a controlled VM/image
deployment we want reproducible, audited weights. This script populates the HF
cache at build time; because the runtime tries ``local_files_only=True`` first
(and the image sets ``HF_HUB_OFFLINE=1``), it uses these cached files and never
reaches out for a newer ``main``.

How it pins (important)
-----------------------
Downloading a repo *by commit SHA* caches the blobs but does NOT create the
``refs/main`` pointer — so a later no-revision / offline lookup (which resolves
``main``) can't find anything without a network HEAD, and fails under
``HF_HUB_OFFLINE=1``. To make the pin work offline we instead:

  1. Assert that the repo's current ``main`` equals the pinned SHA (this fails
     the build loudly if upstream ``main`` has moved off the audited revision).
  2. Download by ``revision="main"`` so ``refs/main`` is populated AND the
     fetched snapshot is exactly the pinned SHA.

The runtime's no-revision lookups then resolve ``main`` -> pinned SHA from the
local cache with no network access.

The pins below are the commit SHAs that were reviewed for this deployment.
To update: bump the SHA (e.g. from ``huggingface-cli repo info <repo>``),
rebuild the image, and re-audit.

Run with HF_HOME / HF_HUB_CACHE pointing at the cache dir you intend to ship.
Honors HF_TOKEN if a repo ever requires auth (none of these do today).
"""

from __future__ import annotations

import sys

# repo_id -> pinned commit SHA (the audited revision for this deployment).
# Resolved from huggingface.co/api/models/<repo>/revision/main at pin time.
PINNED_REVISIONS: dict[str, str] = {
    # Core text compression (always used by [proxy]).
    "chopratejas/kompress-base": "1c9123429e4046d14bd400093d1520859a5e8085",
    "answerdotai/ModernBERT-base": "8949b909ec900327062f0ebf497f51aef5e6f0c8",
    # Technique router (text). Default for HEADROOM_TECHNIQUE_ROUTER.
    "chopratejas/technique-router": "639f08ab1fac0a0eb888bbeb80e752dbf8a780c1",
    # Image-compression feature (only used when [image] is enabled).
    "chopratejas/technique-router-onnx": "27b0b4bfa510a1cff66d888072c0b807082721a8",
    "chopratejas/siglip-image-encoder-onnx": "d0a9fbd66d4bd8c761bff592d44831f7c2ae184e",
    # ONNX embedder for persistent memory (only used when [memory] is enabled).
    "Qdrant/all-MiniLM-L6-v2-onnx": "5f1b8cd78bc4fb444dd171e59b18f3a3af89a079",
}


def main() -> int:
    from huggingface_hub import HfApi, snapshot_download

    api = HfApi()
    failures: list[str] = []
    for repo_id, pinned_sha in PINNED_REVISIONS.items():
        try:
            print(f"[precache] {repo_id}: checking main == {pinned_sha[:12]} ...", flush=True)
            # 1) Drift guard: refuse to build against an unaudited revision.
            current = api.model_info(repo_id, revision="main").sha
            if current != pinned_sha:
                raise RuntimeError(
                    f"main has drifted: upstream main={current} != pinned {pinned_sha}. "
                    f"Re-audit and update the pin in {__file__} before rebuilding."
                )
            # 2) Download by branch name so refs/main is populated for offline,
            #    no-revision lookups. The snapshot is exactly the pinned SHA.
            snapshot_download(repo_id=repo_id, revision="main")
        except Exception as exc:  # noqa: BLE001 - report all, fail at the end
            print(f"[precache] FAILED {repo_id}@{pinned_sha}: {exc}", file=sys.stderr)
            failures.append(repo_id)

    if failures:
        print(f"[precache] {len(failures)} repo(s) failed: {', '.join(failures)}", file=sys.stderr)
        return 1
    print("[precache] all models cached at pinned revisions (refs/main pinned)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
