#!/usr/bin/env python3
"""Audit W&B records and execute manifest-locked cleanup."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from wandb_transaction import audit


def json_write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit_local(args: argparse.Namespace) -> None:
    json_write(args.output, audit(args.run_dir).as_dict())


def audit_cloud(args: argparse.Namespace) -> None:
    anchors = json.loads(args.anchors.read_text(encoding="utf-8"))
    if not isinstance(anchors, list) or not all(isinstance(item, dict) and item.get("metric") for item in anchors):
        raise ValueError("anchors must be a JSON list of objects containing metric")
    import wandb
    run = wandb.Api(timeout=120).run(args.run_path)
    results = []
    for anchor in anchors:
        metric = str(anchor["metric"])
        steps = [int(row["_step"]) for row in run.scan_history(keys=["_step", metric], page_size=1000) if row.get("_step") is not None]
        expected_steps = anchor.get("expected_steps")
        expected_count = anchor.get("expected_count")
        ok = ((expected_count is None or len(steps) == int(expected_count)) and
              (expected_steps is None or steps == [int(value) for value in expected_steps]))
        results.append({"metric": metric, "count": len(steps), "steps": steps, "ok": ok,
                        "expected_count": expected_count, "expected_steps": expected_steps})
    payload = {"run_path": args.run_path, "state": str(run.state), "config": dict(run.config),
               "summary_key_count": len(list(run.summary.keys())), "anchors": results,
               "ok": str(run.state) == "finished" and all(item["ok"] for item in results)}
    json_write(args.output, payload)


def unsafe_local_target(path: Path) -> bool:
    resolved = path.resolve()
    forbidden = {Path("/"), Path.home().resolve(), Path.cwd().resolve()}
    return resolved in forbidden or len(resolved.parts) < 4


def cleanup(args: argparse.Namespace) -> None:
    manifest = args.manifest.resolve()
    digest = file_hash(manifest)
    if not args.apply:
        raise SystemExit("cleanup is a dry run by default; pass --apply and the manifest SHA after user approval")
    if args.approval_sha != digest:
        raise SystemExit("approval SHA does not match the exact cleanup manifest")
    data = json.loads(manifest.read_text(encoding="utf-8"))
    targets = data.get("cleanup_targets")
    if not isinstance(targets, list) or not targets:
        raise ValueError("cleanup manifest needs a non-empty cleanup_targets list")
    import wandb
    api = wandb.Api(timeout=120)
    completed = []
    for target in targets:
        local = Path(str(target.get("local_path", ""))).expanduser()
        remote = str(target.get("remote_run_path", ""))
        if not local.is_dir() or unsafe_local_target(local) or remote.count("/") != 2:
            raise ValueError(f"unsafe or invalid cleanup target: {target}")
        cloud = api.run(remote)
        if str(cloud.state).lower() == "running":
            raise RuntimeError(f"refuse to delete running cloud run: {remote}")
        cloud.delete()
        shutil.rmtree(local)
        completed.append({"local_path": str(local), "remote_run_path": remote})
    json_write(args.output, {"manifest": str(manifest), "manifest_sha256": digest, "deleted": completed})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(required=True)
    local = commands.add_parser("audit-local")
    local.add_argument("--run-dir", type=Path, required=True); local.add_argument("--output", type=Path, required=True); local.set_defaults(func=audit_local)
    cloud = commands.add_parser("audit-cloud")
    cloud.add_argument("--run-path", required=True); cloud.add_argument("--anchors", type=Path, required=True); cloud.add_argument("--output", type=Path, required=True); cloud.set_defaults(func=audit_cloud)
    clean = commands.add_parser("cleanup")
    clean.add_argument("--manifest", type=Path, required=True); clean.add_argument("--output", type=Path, required=True)
    clean.add_argument("--apply", action="store_true"); clean.add_argument("--approval-sha", default=""); clean.set_defaults(func=cleanup)
    args = parser.parse_args(); args.func(args)


if __name__ == "__main__":
    main()
