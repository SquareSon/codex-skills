#!/usr/bin/env python3
"""Rebuild a complete local W&B transaction as a new offline candidate run."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Mapping

import yaml

from wandb_transaction import LocalAudit, audit, iter_history, record_path, run_metadata


COMPANION_SUFFIXES = (".filenames", ".captions", ".count", ".format", ".height", ".width", "._type")
RESERVED = {"_step", "_runtime", "_timestamp"}


def finite(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, Mapping):
        return {str(key): finite(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [finite(item) for item in value]
    return value


def config_from(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "files" / "config.yaml"
    if not path.is_file():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {str(key): item["value"] for key, item in (raw or {}).items()
            if key != "_wandb" and isinstance(item, Mapping) and "value" in item}


def summary_from(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "files" / "wandb-summary.json"
    if not path.is_file():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {str(key): finite(value) for key, value in raw.items()
            if not str(key).startswith("_") and not (isinstance(value, Mapping) and "_type" in value)}


def media_bases(row: Mapping[str, Any]) -> list[str]:
    return sorted(key[:-len(".filenames")] for key in row if key.endswith(".filenames"))


def payload(row: Mapping[str, Any]) -> dict[str, Any]:
    bases = media_bases(row)
    companions = {f"{base}{suffix}" for base in bases for suffix in COMPANION_SUFFIXES}
    return {key: finite(value) for key, value in row.items() if key not in RESERVED and key not in companions}


def images(base: str, row: Mapping[str, Any], files_dir: Path) -> list[Any]:
    import wandb
    paths = row.get(f"{base}.filenames", [])
    captions = row.get(f"{base}.captions", [])
    if not isinstance(paths, list):
        raise ValueError(f"invalid media filenames for {base}")
    result = []
    for index, relative in enumerate(paths):
        image_path = files_dir / str(relative)
        if not image_path.is_file():
            raise FileNotFoundError(f"missing source media: {image_path}")
        caption = str(captions[index]) if isinstance(captions, list) and index < len(captions) else None
        result.append(wandb.Image(str(image_path), caption=caption))
    return result


def equivalent(source: LocalAudit, candidate: LocalAudit) -> dict[str, Any]:
    fields = ("history_count", "min_step", "max_step", "missing_step_count", "media_rows", "media_files")
    return {field: {"source": getattr(source, field), "candidate": getattr(candidate, field)}
            for field in fields if getattr(source, field) != getattr(candidate, field)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-run-dir", type=Path, required=True)
    parser.add_argument("--candidate-id", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    source_dir = args.source_run_dir.expanduser().resolve()
    source = audit(source_dir)
    if source.missing_step_count or source.missing_media_files:
        raise SystemExit("source transaction is incomplete; refuse automatic recovery")
    source_meta = run_metadata(record_path(source_dir))
    report: dict[str, Any] = {"source": source.as_dict(), "candidate_id": args.candidate_id,
                               "output_root": str(args.output_root.expanduser().resolve()), "status": "dry_run"}
    if args.dry_run:
        args.report.parent.mkdir(parents=True, exist_ok=True); args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"); return
    output_root = args.output_root.expanduser().resolve()
    if list(output_root.rglob(f"run-{args.candidate_id}.wandb")):
        raise SystemExit("candidate ID already exists locally; reuse only after inspection")
    output_root.mkdir(parents=True, exist_ok=True)
    import wandb
    run = wandb.init(entity=source_meta["entity"], project=source_meta["project"], id=args.candidate_id,
                     resume="never", mode="offline", name=source_meta["name"], group=source_meta["group"],
                     job_type=source_meta["job_type"], tags=list(dict.fromkeys([*source_meta["tags"], "local-republished", f"replaces-{source_meta['run_id']}"])),
                     notes=f"Republished from complete local W&B transaction {source_meta['run_id']}; no model output was recomputed.",
                     config=config_from(source_dir), dir=str(output_root))
    try:
        files_dir = source_dir / "files"
        for row in iter_history(record_path(source_dir)):
            step = int(row["_step"]); base_payload = payload(row); bases = media_bases(row)
            if not bases:
                run.log(base_payload or {"reconcile/empty_row": 1}, step=step, commit=True); continue
            run.log(base_payload or {"reconcile/media_row": 1}, step=step, commit=False)
            for index, base in enumerate(bases):
                run.log({base: images(base, row, files_dir)}, step=step, commit=index == len(bases) - 1)
        run.summary.update(summary_from(source_dir))
    except BaseException:
        run.finish(exit_code=1); raise
    run.finish(exit_code=0)
    candidates = list(output_root.rglob(f"run-{args.candidate_id}.wandb"))
    if len(candidates) != 1:
        raise RuntimeError(f"expected one candidate transaction, found {len(candidates)}")
    candidate = audit(candidates[0].parent)
    mismatches = equivalent(source, candidate)
    report.update({"status": "offline_verified" if not mismatches else "rejected", "candidate": candidate.as_dict(), "mismatches": mismatches})
    args.report.parent.mkdir(parents=True, exist_ok=True); args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if mismatches:
        raise SystemExit("candidate transaction differs from source; do not sync")


if __name__ == "__main__":
    main()
