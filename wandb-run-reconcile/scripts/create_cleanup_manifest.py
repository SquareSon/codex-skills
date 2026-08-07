#!/usr/bin/env python3
"""Create a reviewable cleanup manifest; this script never deletes anything."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--targets", type=Path, required=True, help="JSON list of exact local_path and remote_run_path targets.")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    targets = json.loads(args.targets.read_text(encoding="utf-8"))
    if not isinstance(targets, list) or not targets:
        raise ValueError("targets must be a non-empty JSON list")
    normalized = []
    for item in targets:
        if not isinstance(item, dict) or not item.get("local_path") or not item.get("remote_run_path"):
            raise ValueError("each target requires local_path and remote_run_path")
        remote = str(item["remote_run_path"])
        if remote.count("/") != 2:
            raise ValueError(f"remote_run_path must be entity/project/run_id: {remote}")
        local = Path(str(item["local_path"])).expanduser().resolve()
        normalized.append({**item, "local_path": str(local), "remote_run_path": remote})
    payload = {"schema_version": "wandb-reconcile-cleanup-v1", "cleanup_targets": normalized,
               "approval": "User must explicitly approve this manifest SHA before --apply."}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(hashlib.sha256(args.output.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
