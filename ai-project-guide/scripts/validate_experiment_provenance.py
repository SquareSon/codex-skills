# -*- coding: utf-8 -*-
"""校验实验实现、配置、执行与论文报告的独立证据状态。"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


SCHEMA = "ai-project-experiment-provenance/v1"
STATES = ("implemented", "configured", "executed", "reported")
STATUS_VALUES = {"confirmed", "missing", "unknown"}
ID_PATTERN = re.compile(r"[a-z0-9][a-z0-9._-]*$")
SENSITIVE_KEY_PATTERN = re.compile(r"(?:password|secret|token|api[_-]?key|credential)", re.IGNORECASE)
EPHEMERAL_ROOTS = {"log", "logs", "wandb", "ckpt", "ckpts", "checkpoint", "checkpoints", "cache", "tmp", "pt"}


def read_json(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    """读取 JSON 对象并返回可合并的错误列表。"""

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        return None, [f"无法读取文件：{exc}"]
    except json.JSONDecodeError as exc:
        return None, [f"JSON 格式错误：{exc}"]
    return (value, []) if isinstance(value, dict) else (None, ["顶层必须是 JSON 对象"])


def is_relative_path(value: Any) -> bool:
    """限制证据路径为不越界的相对路径。"""

    if not isinstance(value, str) or not value:
        return False
    path = Path(value)
    return not path.is_absolute() and ".." not in path.parts


def validate_catalog(value: Any, component: str, errors: list[str]) -> set[str]:
    """校验证据引用目录并拒绝易失日志、缓存和模型权重根。"""

    if not isinstance(value, dict):
        errors.append("reference_catalog 必须是 ID→引用对象映射")
        return set()
    reference_ids: set[str] = set()
    for reference_id, reference in value.items():
        location = f"reference_catalog.{reference_id}"
        if not isinstance(reference_id, str) or not ID_PATTERN.fullmatch(reference_id):
            errors.append(f"{location} ID 格式非法")
            continue
        reference_ids.add(reference_id)
        if not isinstance(reference, dict):
            errors.append(f"{location} 必须是引用对象")
            continue
        scope = reference.get("scope")
        expected_fields = {"scope", "path"} if scope == "workspace" else {"scope", "component", "path"}
        if scope not in {"workspace", "component"} or set(reference) != expected_fields:
            errors.append(f"{location} 必须是标准 workspace/component 引用")
            continue
        if scope == "component" and reference.get("component") != component:
            errors.append(f"{location}.component 必须等于顶层 component")
        path_value = reference.get("path")
        if not is_relative_path(path_value):
            errors.append(f"{location}.path 必须是不越界的相对路径")
            continue
        path_parts = {part.lower() for part in Path(path_value).parts}
        if path_parts & EPHEMERAL_ROOTS:
            errors.append(f"{location}.path 指向易失日志、缓存或模型权重；请改用稳定清单/汇总证据")
    return reference_ids


def validate_experiment(
        value: Any,
        index: int,
        reference_ids: set[str],
        experiment_ids: set[str],
        allow_incomplete: bool,
        errors: list[str],
) -> None:
    """校验单个实验的四种状态，禁止用高阶段状态反推低阶段状态。"""

    location = f"experiments[{index}]"
    fields = {"id", "claim", "states", "limitations"}
    if not isinstance(value, dict) or set(value) != fields:
        errors.append(f"{location} 必须仅包含 id、claim、states、limitations")
        return
    experiment_id = value.get("id")
    if not isinstance(experiment_id, str) or not ID_PATTERN.fullmatch(experiment_id) or experiment_id in experiment_ids:
        errors.append(f"{location}.id 必须是唯一标准 ID")
    else:
        experiment_ids.add(experiment_id)
    if not isinstance(value.get("claim"), str) or (not value["claim"] and not allow_incomplete):
        errors.append(f"{location}.claim 必须是非空字符串")
    states = value.get("states")
    if not isinstance(states, dict) or set(states) != set(STATES):
        errors.append(f"{location}.states 必须分别声明 {', '.join(STATES)}")
    else:
        for state in STATES:
            state_location = f"{location}.states.{state}"
            record = states[state]
            if not isinstance(record, dict) or set(record) != {"status", "evidence_refs"}:
                errors.append(f"{state_location} 必须仅包含 status、evidence_refs")
                continue
            status = record.get("status")
            refs = record.get("evidence_refs")
            if status not in STATUS_VALUES:
                errors.append(f"{state_location}.status 必须是 confirmed、missing 或 unknown")
            if not isinstance(refs, list) or not all(isinstance(item, str) and item in reference_ids for item in refs):
                errors.append(f"{state_location}.evidence_refs 必须引用 reference_catalog")
                continue
            if len(refs) != len(set(refs)):
                errors.append(f"{state_location}.evidence_refs 不得重复")
            if status == "confirmed" and not refs:
                errors.append(f"{state_location} 为 confirmed 时必须提供证据")
            if status == "missing" and refs:
                errors.append(f"{state_location} 为 missing 时不得挂接证据")
    limitations = value.get("limitations")
    if not isinstance(limitations, list) or not all(isinstance(item, str) and item for item in limitations):
        errors.append(f"{location}.limitations 必须是非空字符串数组")


def scan_sensitive_fields(value: Any, errors: list[str], location: str = "$") -> None:
    """递归拒绝疑似凭据字段。"""

    if isinstance(value, dict):
        for key, nested in value.items():
            if SENSITIVE_KEY_PATTERN.search(key):
                errors.append(f"{location}.{key} 疑似敏感字段")
            scan_sensitive_fields(nested, errors, f"{location}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            scan_sensitive_fields(nested, errors, f"{location}[{index}]")


def validate(value: dict[str, Any], allow_incomplete: bool) -> list[str]:
    """执行实验溯源 Schema 与证据独立性校验。"""

    errors: list[str] = []
    fields = {"schema", "component", "reference_catalog", "experiments"}
    if set(value) != fields:
        errors.append("顶层必须仅包含 schema、component、reference_catalog、experiments")
    if value.get("schema") != SCHEMA:
        errors.append(f"schema 必须为 {SCHEMA}")
    component = value.get("component")
    if not isinstance(component, str) or (not component and not allow_incomplete):
        errors.append("component 必须是非空字符串")
        component = ""
    reference_ids = validate_catalog(value.get("reference_catalog"), component, errors)
    experiments = value.get("experiments")
    if not isinstance(experiments, list):
        errors.append("experiments 必须是数组")
    else:
        experiment_ids: set[str] = set()
        for index, experiment in enumerate(experiments):
            validate_experiment(experiment, index, reference_ids, experiment_ids, allow_incomplete, errors)
    scan_sensitive_fields(value, errors)
    return errors


def parse_args() -> argparse.Namespace:
    """解析实验溯源文件与体积预算。"""

    parser = argparse.ArgumentParser(description="校验 EXPERIMENT_PROVENANCE.json。")
    parser.add_argument("--path", required=True, help="EXPERIMENT_PROVENANCE.json 路径")
    parser.add_argument("--allow-incomplete", action="store_true", help="允许空模板")
    parser.add_argument("--max-bytes", type=int, default=16 * 1024, help="最大字节数，默认 16384")
    return parser.parse_args()


def main() -> int:
    """输出确定性结果并用退出码表示验证状态。"""

    args = parse_args()
    if args.max_bytes <= 0:
        print("ERROR: --max-bytes 必须为正数")
        return 2
    path = Path(args.path).expanduser()
    try:
        size = path.stat().st_size
    except OSError as exc:
        print(f"ERROR: 无法读取文件大小：{exc}")
        return 1
    value, errors = read_json(path)
    if size > args.max_bytes:
        errors.append(f"文件大小 {size} bytes 超过限制 {args.max_bytes} bytes")
    if value is not None:
        errors.extend(validate(value, args.allow_incomplete))
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"OK: {path} ({size} bytes, {SCHEMA})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
