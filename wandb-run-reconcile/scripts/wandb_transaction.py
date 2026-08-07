"""Stable local W&B transaction helpers used by this skill's scripts."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class LocalAudit:
    record: str
    history_count: int
    min_step: int | None
    max_step: int | None
    missing_step_count: int
    metric_counts: dict[str, int]
    media_rows: int
    media_files: int
    missing_media_files: list[str]
    record_sha256: str
    config_sha256: str | None
    summary_sha256: str | None
    metadata: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def record_path(run_dir: Path) -> Path:
    records = sorted(run_dir.glob("*.wandb"))
    if len(records) != 1:
        raise ValueError(f"expected exactly one .wandb record in {run_dir}; found {len(records)}")
    return records[0]


def _api():
    try:
        from wandb.proto import wandb_internal_pb2 as pb
        from wandb.sdk.internal.datastore import DataStore
    except ImportError as error:
        raise RuntimeError("W&B SDK transaction reader is unavailable in this Python environment") from error
    return pb, DataStore


def iter_records(record: Path) -> Iterator[Any]:
    pb, datastore_type = _api()
    store = datastore_type()
    store.open_for_scan(str(record))
    while (data := store.scan_data()) is not None:
        item = pb.Record()
        item.ParseFromString(data)
        yield item


def key_of(item: Any) -> str:
    return str(item.key) if item.key else ".".join(str(value) for value in item.nested_key)


def decode(items: Sequence[Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for item in items:
        try:
            result[key_of(item)] = json.loads(item.value_json)
        except json.JSONDecodeError:
            result[key_of(item)] = item.value_json
    return result


def iter_history(record: Path) -> Iterator[dict[str, Any]]:
    for item in iter_records(record):
        if item.WhichOneof("record_type") == "history":
            yield decode(item.history.item)


def run_metadata(record: Path) -> dict[str, Any]:
    latest: dict[str, Any] = {}
    for item in iter_records(record):
        if item.WhichOneof("record_type") == "run":
            run = item.run
            latest = {
                "run_id": str(run.run_id), "entity": str(run.entity),
                "project": str(run.project), "name": str(run.display_name),
                "group": str(run.run_group), "job_type": str(run.job_type),
                "tags": [str(tag) for tag in run.tags],
            }
    if not latest:
        raise ValueError(f"transaction has no run record: {record}")
    return latest


def audit(run_dir: Path) -> LocalAudit:
    run_dir = run_dir.expanduser().resolve()
    record = record_path(run_dir)
    files_dir = run_dir / "files"
    steps: list[int] = []
    metric_counts: dict[str, int] = {}
    media_rows = media_files = 0
    missing_media: list[str] = []
    for row in iter_history(record):
        if "_step" not in row:
            raise ValueError(f"history row has no _step: {record}")
        steps.append(int(row["_step"]))
        for key in row:
            if not key.startswith("_") and not key.endswith((".filenames", ".captions", ".count", ".format", ".height", ".width", "._type")):
                metric_counts[key] = metric_counts.get(key, 0) + 1
        file_lists = [value for key, value in row.items() if key.endswith(".filenames") and isinstance(value, list)]
        if file_lists:
            media_rows += 1
            for paths in file_lists:
                media_files += len(paths)
                missing_media.extend(str(files_dir / str(path)) for path in paths if not (files_dir / str(path)).is_file())
    if steps != sorted(steps) or len(steps) != len(set(steps)):
        raise ValueError("history steps are not strictly increasing; refuse automatic recovery")
    expected = set(range(steps[0], steps[-1] + 1)) if steps else set()
    config = files_dir / "config.yaml"
    summary = files_dir / "wandb-summary.json"
    return LocalAudit(
        record=str(record), history_count=len(steps), min_step=steps[0] if steps else None,
        max_step=steps[-1] if steps else None, missing_step_count=len(expected - set(steps)),
        metric_counts=dict(sorted(metric_counts.items())), media_rows=media_rows, media_files=media_files,
        missing_media_files=missing_media, record_sha256=sha256(record),
        config_sha256=sha256(config) if config.is_file() else None,
        summary_sha256=sha256(summary) if summary.is_file() else None, metadata=run_metadata(record),
    )
