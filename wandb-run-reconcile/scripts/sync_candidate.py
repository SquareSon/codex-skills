#!/usr/bin/env python3
"""Synchronize one verified offline candidate; never changes its embedded run ID."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def sanitize_proxy() -> None:
    all_proxy = os.environ.get("ALL_PROXY") or os.environ.get("all_proxy")
    has_http = any(os.environ.get(key) for key in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"))
    if all_proxy and all_proxy.lower().startswith("socks") and has_http:
        os.environ.pop("ALL_PROXY", None); os.environ.pop("all_proxy", None)
        print("[reconcile] ignored SOCKS ALL_PROXY; retained HTTP(S) proxy", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline-run-dir", type=Path, required=True)
    parser.add_argument("--apply", action="store_true", help="Perform the cloud upload after user approval.")
    args = parser.parse_args()
    directory = args.offline_run_dir.expanduser().resolve()
    if not directory.is_dir() or len(list(directory.glob("run-*.wandb"))) != 1:
        raise SystemExit("offline-run-dir must contain exactly one candidate .wandb transaction")
    marker = next(directory.glob("run-*.wandb.synced"), None)
    if marker:
        print(f"already synced: {marker}"); return
    command = [sys.executable, "-m", "wandb", "sync", "--include-offline", str(directory)]
    print("planned:", " ".join(command))
    if not args.apply:
        print("dry run: pass --apply only after user approves the fixed candidate ID"); return
    sanitize_proxy()
    subprocess.run(command, check=True)
    if not next(directory.glob("run-*.wandb.synced"), None):
        raise SystemExit("wandb sync returned without a synced marker; retry this same candidate ID")


if __name__ == "__main__":
    main()
