# -*- coding: utf-8 -*-
"""校验分层、机器优先 AI_CONTEXT.json 的结构与安全边界。"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


SCHEMA_V3 = "ai-project-context/v3"
SCHEMA_V4 = "ai-project-context/v4"
SUPPORTED_SCHEMAS = {SCHEMA_V3, SCHEMA_V4}
AUTHORITY_ORDER = ["active", "profile", "git", "source", "context"]
TOP_LEVEL_FIELDS_V3 = {
    "schema",
    "scope",
    "authority_order",
    "summary",
    "hierarchy",
    "bootstrap",
    "components",
    "attention_routes",
    "concepts",
    "boundaries",
    "refresh",
}
TOP_LEVEL_FIELDS_V4 = {
    "schema",
    "scope",
    "authority_order",
    "reference_catalog",
    "summary",
    "hierarchy",
    "bootstrap",
    "components",
    "task_routes",
    "contracts",
    "semantic_nodes",
    "experiment_provenance",
    "do_not_assume",
    "boundaries",
    "refresh",
}
CONFIDENCE_VALUES = {"confirmed", "inferred", "unknown"}
ATTENTION_ROLES = {"entrypoint", "core_logic", "configuration", "data_contract", "test", "interface"}
EXPANSION_DIRECTIONS = {"callers", "callees", "configuration", "data_contracts", "tests", "interfaces"}
PATH_CATEGORIES = {
    "core",
    "contract",
    "entrypoint",
    "experiment",
    "test",
    "evidence",
    "maintained_dependency",
    "third_party",
    "reference",
    "historical",
    "generated_evidence",
    "generated_ephemeral",
    "local_only",
    "auxiliary",
}
SEMANTIC_KINDS = {
    "architecture",
    "control_flow",
    "data_flow",
    "interface",
    "invariant",
    "evidence_gate",
    "experiment",
}
COMPLETION_RULE = "all_required_evidence_or_explicit_gap"
FINGERPRINT_PATTERN = re.compile(r"sha256:[0-9a-f]{64}$")
ID_PATTERN = re.compile(r"[a-z0-9][a-z0-9._-]*$")
SENSITIVE_KEY_PATTERN = re.compile(r"(?:password|secret|token|api[_-]?key|credential)", re.IGNORECASE)


def read_json(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    """读取 JSON 对象，并将格式问题转换为确定性错误。"""

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        return None, [f"无法读取文件：{exc}"]
    except json.JSONDecodeError as exc:
        return None, [f"JSON 格式错误：{exc}"]
    if not isinstance(value, dict):
        return None, ["顶层必须是 JSON 对象"]
    return value, []


def is_relative_path(value: Any) -> bool:
    """限制路径为不越界的相对路径。"""

    if not isinstance(value, str) or not value:
        return False
    path = Path(value)
    return not path.is_absolute() and ".." not in path.parts


def validate_reference(value: Any, component_ids: set[str], location: str, errors: list[str]) -> None:
    """校验可移植的工作台或组件文件引用。"""

    if not isinstance(value, dict):
        errors.append(f"{location} 必须是引用对象")
        return
    scope = value.get("scope")
    if scope not in {"workspace", "component"}:
        errors.append(f"{location}.scope 必须是 workspace 或 component")
    if not is_relative_path(value.get("path")):
        errors.append(f"{location}.path 必须是不越界的相对路径")
    if scope == "component" and value.get("component") not in component_ids:
        errors.append(f"{location}.component 必须引用已声明组件")
    if scope == "workspace" and "component" in value:
        errors.append(f"{location} 的 workspace 引用不得包含 component")
    unexpected = set(value) - {"scope", "component", "path"}
    if unexpected:
        errors.append(f"{location} 含未定义字段：{', '.join(sorted(unexpected))}")


def validate_reference_list(value: Any, component_ids: set[str], location: str, errors: list[str]) -> None:
    """校验引用数组。"""

    if not isinstance(value, list):
        errors.append(f"{location} 必须是数组")
        return
    for index, reference in enumerate(value):
        validate_reference(reference, component_ids, f"{location}[{index}]", errors)


def validate_attention_list(value: Any, component_ids: set[str], location: str, errors: list[str]) -> None:
    """校验注意力锚点；它们只定义起点，不构成读取白名单。"""

    if not isinstance(value, list):
        errors.append(f"{location} 必须是数组")
        return
    for index, item in enumerate(value):
        item_location = f"{location}[{index}]"
        if not isinstance(item, dict) or set(item) != {"reference", "role"}:
            errors.append(f"{item_location} 必须包含且仅包含 reference、role")
            continue
        validate_reference(item.get("reference"), component_ids, f"{item_location}.reference", errors)
        if item.get("role") not in ATTENTION_ROLES:
            errors.append(f"{item_location}.role 必须是标准注意力角色")


def validate_components(value: Any, errors: list[str]) -> set[str]:
    """校验组件身份、定位和组件内相对路径。"""

    if not isinstance(value, list):
        errors.append("components 必须是数组")
        return set()
    component_ids: set[str] = set()
    fields = {"id", "role", "locator", "profile_path", "runtime_key", "source_roots", "entrypoints"}
    for index, component in enumerate(value):
        location = f"components[{index}]"
        if not isinstance(component, dict):
            errors.append(f"{location} 必须是对象")
            continue
        component_id = component.get("id")
        if not isinstance(component_id, str) or not component_id:
            errors.append(f"{location}.id 必须是非空字符串")
        elif component_id in component_ids:
            errors.append(f"{location}.id 重复：{component_id}")
        else:
            component_ids.add(component_id)
        if not isinstance(component.get("role"), str) or not component["role"]:
            errors.append(f"{location}.role 必须是非空字符串")
        locator = component.get("locator")
        if not isinstance(locator, dict):
            errors.append(f"{location}.locator 必须是对象")
        elif locator.get("kind") == "active_component":
            if not isinstance(locator.get("key"), str) or not locator["key"]:
                errors.append(f"{location}.locator.key 必须是非空 Active 组件键")
            if set(locator) != {"kind", "key"}:
                errors.append(f"{location}.locator 仅可包含 kind 和 key")
        elif locator.get("kind") == "relative":
            if not is_relative_path(locator.get("path")):
                errors.append(f"{location}.locator.path 必须是不越界的相对路径")
            if set(locator) != {"kind", "path"}:
                errors.append(f"{location}.locator 仅可包含 kind 和 path")
        else:
            errors.append(f"{location}.locator.kind 必须是 active_component 或 relative")
        if not is_relative_path(component.get("profile_path")):
            errors.append(f"{location}.profile_path 必须是不越界的相对路径")
        runtime_key = component.get("runtime_key")
        if runtime_key is not None and (not isinstance(runtime_key, str) or not runtime_key):
            errors.append(f"{location}.runtime_key 必须是字符串或 null")
        for field in ("source_roots", "entrypoints"):
            paths = component.get(field)
            if not isinstance(paths, list) or not all(is_relative_path(path) for path in paths):
                errors.append(f"{location}.{field} 必须是相对路径数组")
        unexpected = set(component) - fields
        if unexpected:
            errors.append(f"{location} 含未定义字段：{', '.join(sorted(unexpected))}")
    return component_ids


def validate_summary(value: Any, component_ids: set[str], allow_incomplete: bool, errors: list[str]) -> None:
    """校验面向理解的项目摘要和关键数据/控制流。"""

    if not isinstance(value, dict) or set(value) != {"purpose", "architecture", "key_flows"}:
        errors.append("summary 必须包含且仅包含 purpose、architecture、key_flows")
        return
    purpose = value.get("purpose")
    if not isinstance(purpose, str) or (not purpose and not allow_incomplete):
        errors.append("summary.purpose 必须是非空字符串")
    architecture = value.get("architecture")
    if not isinstance(architecture, list) or not all(isinstance(item, str) and item for item in architecture):
        errors.append("summary.architecture 必须是非空字符串数组")
    flows = value.get("key_flows")
    if not isinstance(flows, list):
        errors.append("summary.key_flows 必须是数组")
        return
    flow_ids: set[str] = set()
    for index, flow in enumerate(flows):
        location = f"summary.key_flows[{index}]"
        if not isinstance(flow, dict) or set(flow) != {"id", "summary", "attention", "evidence", "confidence"}:
            errors.append(f"{location} 必须包含且仅包含标准关键流字段")
            continue
        flow_id = flow.get("id")
        if not isinstance(flow_id, str) or not flow_id or flow_id in flow_ids:
            errors.append(f"{location}.id 必须是唯一非空字符串")
        else:
            flow_ids.add(flow_id)
        if not isinstance(flow.get("summary"), str) or not flow["summary"]:
            errors.append(f"{location}.summary 必须是非空字符串")
        if flow.get("confidence") not in CONFIDENCE_VALUES:
            errors.append(f"{location}.confidence 必须是标准置信度")
        validate_attention_list(flow.get("attention"), component_ids, f"{location}.attention", errors)
        validate_reference_list(flow.get("evidence"), component_ids, f"{location}.evidence", errors)


def validate_hierarchy(
        value: Any,
        scope: Any,
        component_ids: set[str],
        active_components: list[str] | None,
        errors: list[str],
) -> None:
    """校验工作台根与组件叶的完整层级关系。"""

    if not isinstance(value, dict) or set(value) != {"role", "child_contexts"}:
        errors.append("hierarchy 必须包含且仅包含 role、child_contexts")
        return
    role = value.get("role")
    children = value.get("child_contexts")
    if role not in {"workspace_root", "component_leaf"}:
        errors.append("hierarchy.role 必须是 workspace_root 或 component_leaf")
    if not isinstance(children, list):
        errors.append("hierarchy.child_contexts 必须是数组")
        return
    child_ids: list[str] = []
    for index, child in enumerate(children):
        location = f"hierarchy.child_contexts[{index}]"
        if not isinstance(child, dict) or set(child) != {"component", "path"}:
            errors.append(f"{location} 必须包含且仅包含 component、path")
            continue
        component = child.get("component")
        if component not in component_ids:
            errors.append(f"{location}.component 必须引用已声明组件")
        elif component in child_ids:
            errors.append(f"{location}.component 重复：{component}")
        else:
            child_ids.append(component)
        if not is_relative_path(child.get("path")):
            errors.append(f"{location}.path 必须是不越界的相对路径")
    if scope == "workspace" and role != "workspace_root":
        errors.append("workspace Context 必须使用 hierarchy.role=workspace_root")
    if scope == "component" and role != "component_leaf":
        errors.append("component Context 必须使用 hierarchy.role=component_leaf")
    if role == "workspace_root" and active_components is not None and set(child_ids) != set(active_components):
        errors.append("workspace hierarchy.child_contexts 必须覆盖全部 Active 组件")
    if role == "component_leaf" and children:
        errors.append("component_leaf 不得声明 child_contexts")
    if scope == "component" and (len(component_ids) != 1 or active_components is None or len(active_components) != 1):
        errors.append("component Context 必须只声明一个 Active 组件")


def validate_v3(value: dict[str, Any], allow_incomplete: bool) -> list[str]:
    """执行 v3 Schema 校验，不访问项目运行环境。"""

    errors: list[str] = []
    missing = TOP_LEVEL_FIELDS_V3 - set(value)
    unexpected = set(value) - TOP_LEVEL_FIELDS_V3
    if missing:
        errors.append(f"缺少顶层字段：{', '.join(sorted(missing))}")
    if unexpected:
        errors.append(f"含未定义顶层字段：{', '.join(sorted(unexpected))}")
    if value.get("schema") != SCHEMA_V3:
        errors.append(f"schema 必须为 {SCHEMA_V3}")
    scope = value.get("scope")
    if scope not in {"workspace", "component"}:
        errors.append("scope 必须为 workspace 或 component")
    if value.get("authority_order") != AUTHORITY_ORDER:
        errors.append("authority_order 必须严格遵循 active/profile/git/source/context")

    component_ids = validate_components(value.get("components"), errors)
    bootstrap = value.get("bootstrap")
    active_components: list[str] | None = None
    if not isinstance(bootstrap, dict) or set(bootstrap) != {"read_before_code", "active_components"}:
        errors.append("bootstrap 必须包含且仅包含 read_before_code、active_components")
    else:
        validate_reference_list(bootstrap.get("read_before_code"), component_ids, "bootstrap.read_before_code", errors)
        active_value = bootstrap.get("active_components")
        if isinstance(active_value, list) and all(isinstance(item, str) and item in component_ids for item in active_value):
            if len(active_value) != len(set(active_value)):
                errors.append("bootstrap.active_components 不得重复")
            active_components = active_value
        else:
            errors.append("bootstrap.active_components 必须是已声明组件 ID 数组")

    validate_summary(value.get("summary"), component_ids, allow_incomplete, errors)
    validate_hierarchy(value.get("hierarchy"), scope, component_ids, active_components, errors)

    routes = value.get("attention_routes")
    if not isinstance(routes, list):
        errors.append("attention_routes 必须是数组")
    else:
        route_fields = {"intent", "components", "attention", "expand"}
        for index, route in enumerate(routes):
            location = f"attention_routes[{index}]"
            if not isinstance(route, dict) or set(route) != route_fields:
                errors.append(f"{location} 必须包含且仅包含标准注意力路由字段")
                continue
            if not isinstance(route.get("intent"), str) or not route["intent"]:
                errors.append(f"{location}.intent 必须是非空字符串")
            route_components = route.get("components")
            if not isinstance(route_components, list) or not all(
                isinstance(item, str) and item in component_ids for item in route_components
            ):
                errors.append(f"{location}.components 必须是已声明组件 ID 数组")
            validate_attention_list(route.get("attention"), component_ids, f"{location}.attention", errors)
            expansion = route.get("expand")
            if not isinstance(expansion, list) or not all(item in EXPANSION_DIRECTIONS for item in expansion):
                errors.append(f"{location}.expand 必须是标准扩展方向数组")

    concepts = value.get("concepts")
    if not isinstance(concepts, list):
        errors.append("concepts 必须是数组")
    else:
        concept_ids: set[str] = set()
        for index, concept in enumerate(concepts):
            location = f"concepts[{index}]"
            if not isinstance(concept, dict) or set(concept) != {"id", "claim", "evidence", "confidence"}:
                errors.append(f"{location} 必须包含且仅包含标准概念字段")
                continue
            concept_id = concept.get("id")
            if not isinstance(concept_id, str) or not concept_id or concept_id in concept_ids:
                errors.append(f"{location}.id 必须是唯一非空字符串")
            else:
                concept_ids.add(concept_id)
            if not isinstance(concept.get("claim"), str) or not concept["claim"]:
                errors.append(f"{location}.claim 必须是非空字符串")
            if concept.get("confidence") not in CONFIDENCE_VALUES:
                errors.append(f"{location}.confidence 必须是标准置信度")
            validate_reference_list(concept.get("evidence"), component_ids, f"{location}.evidence", errors)

    boundaries = value.get("boundaries")
    boundary_fields = {"generated", "third_party", "historical", "auxiliary"}
    if not isinstance(boundaries, dict) or set(boundaries) != boundary_fields:
        errors.append("boundaries 必须包含且仅包含 generated、third_party、historical、auxiliary")
    elif isinstance(boundaries, dict):
        for field in sorted(boundary_fields):
            validate_reference_list(boundaries.get(field), component_ids, f"boundaries.{field}", errors)

    refresh = value.get("refresh")
    refresh_fields = {"profile_fingerprint", "active_fingerprint", "anchor_files"}
    if not isinstance(refresh, dict) or set(refresh) != refresh_fields:
        errors.append("refresh 必须包含且仅包含 profile_fingerprint、active_fingerprint、anchor_files")
    elif isinstance(refresh, dict):
        for field in ("profile_fingerprint", "active_fingerprint"):
            fingerprint = refresh.get(field)
            if fingerprint is None and allow_incomplete:
                continue
            if not isinstance(fingerprint, str) or not FINGERPRINT_PATTERN.fullmatch(fingerprint):
                errors.append(f"refresh.{field} 必须是 sha256:<64位十六进制> 指纹")
        anchors = refresh.get("anchor_files")
        if not isinstance(anchors, list):
            errors.append("refresh.anchor_files 必须是数组")
        else:
            for index, anchor in enumerate(anchors):
                location = f"refresh.anchor_files[{index}]"
                if not isinstance(anchor, dict) or set(anchor) != {"reference", "sha256"}:
                    errors.append(f"{location} 必须包含且仅包含 reference、sha256")
                    continue
                validate_reference(anchor.get("reference"), component_ids, f"{location}.reference", errors)
                if not isinstance(anchor.get("sha256"), str) or not FINGERPRINT_PATTERN.fullmatch(anchor["sha256"]):
                    errors.append(f"{location}.sha256 必须是 sha256:<64位十六进制> 指纹")

    def scan_sensitive_fields(item: Any, location: str = "$") -> None:
        if isinstance(item, dict):
            for key, nested in item.items():
                if SENSITIVE_KEY_PATTERN.search(key):
                    errors.append(f"{location}.{key} 疑似敏感字段，禁止写入 AI_CONTEXT")
                scan_sensitive_fields(nested, f"{location}.{key}")
        elif isinstance(item, list):
            for index, nested in enumerate(item):
                scan_sensitive_fields(nested, f"{location}[{index}]")

    scan_sensitive_fields(value)
    return errors


def validate_id(value: Any, location: str, errors: list[str]) -> str | None:
    """校验稳定、紧凑、可跨节点引用的机器 ID。"""

    if not isinstance(value, str) or not ID_PATTERN.fullmatch(value):
        errors.append(f"{location} 必须匹配 {ID_PATTERN.pattern}")
        return None
    return value


def validate_ref_ids(
        value: Any,
        reference_ids: set[str],
        location: str,
        errors: list[str],
        *,
        require_non_empty: bool = False,
) -> list[str]:
    """校验去重后的引用 ID 数组并返回有效值。"""

    if not isinstance(value, list):
        errors.append(f"{location} 必须是引用 ID 数组")
        return []
    if require_non_empty and not value:
        errors.append(f"{location} 不得为空")
    if len(value) != len(set(item for item in value if isinstance(item, str))):
        errors.append(f"{location} 不得包含重复引用")
    valid: list[str] = []
    for index, reference_id in enumerate(value):
        if not isinstance(reference_id, str) or reference_id not in reference_ids:
            errors.append(f"{location}[{index}] 必须引用 reference_catalog 中的 ID")
        else:
            valid.append(reference_id)
    return valid


def validate_reference_catalog(value: Any, component_ids: set[str], errors: list[str]) -> dict[str, dict[str, Any]]:
    """校验 v4 去重引用目录。"""

    if not isinstance(value, dict):
        errors.append("reference_catalog 必须是 ID→引用对象映射")
        return {}
    catalog: dict[str, dict[str, Any]] = {}
    for reference_id, reference in value.items():
        location = f"reference_catalog.{reference_id}"
        if validate_id(reference_id, location, errors) is None:
            continue
        if not isinstance(reference, dict):
            errors.append(f"{location} 必须是引用对象")
            continue
        local_errors: list[str] = []
        validate_reference(reference, component_ids, location, local_errors)
        errors.extend(local_errors)
        if not local_errors:
            catalog[reference_id] = reference
    return catalog


def validate_components_v4(
        value: Any,
        reference_ids: set[str],
        errors: list[str],
) -> set[str]:
    """校验 v4 组件目录，其中所有路径均通过引用目录复用。"""

    if not isinstance(value, list):
        errors.append("components 必须是数组")
        return set()
    fields = {"id", "role", "locator", "profile_ref", "runtime_key", "source_refs", "entrypoint_refs"}
    component_ids: set[str] = set()
    for index, component in enumerate(value):
        location = f"components[{index}]"
        if not isinstance(component, dict) or set(component) != fields:
            errors.append(f"{location} 必须包含且仅包含标准 v4 组件字段")
            continue
        component_id = validate_id(component.get("id"), f"{location}.id", errors)
        if component_id in component_ids:
            errors.append(f"{location}.id 重复：{component_id}")
        elif component_id is not None:
            component_ids.add(component_id)
        if not isinstance(component.get("role"), str) or not component["role"]:
            errors.append(f"{location}.role 必须是非空字符串")
        locator = component.get("locator")
        if not isinstance(locator, dict):
            errors.append(f"{location}.locator 必须是对象")
        elif locator.get("kind") == "active_component":
            if set(locator) != {"kind", "key"} or not isinstance(locator.get("key"), str) or not locator["key"]:
                errors.append(f"{location}.locator 必须仅包含 active_component kind 与非空 key")
        elif locator.get("kind") == "relative":
            if set(locator) != {"kind", "path"} or not is_relative_path(locator.get("path")):
                errors.append(f"{location}.locator 必须仅包含 relative kind 与相对 path")
        else:
            errors.append(f"{location}.locator.kind 必须是 active_component 或 relative")
        profile_ref = component.get("profile_ref")
        if profile_ref is None:
            if not isinstance(locator, dict) or locator.get("kind") != "relative":
                errors.append(f"{location}.profile_ref 仅可在独立 relative 组件中为 null")
        elif not isinstance(profile_ref, str) or profile_ref not in reference_ids:
            errors.append(f"{location}.profile_ref 必须为 null 或引用 reference_catalog")
        runtime_key = component.get("runtime_key")
        if runtime_key is not None and (not isinstance(runtime_key, str) or not runtime_key):
            errors.append(f"{location}.runtime_key 必须是非空字符串或 null")
        validate_ref_ids(component.get("source_refs"), reference_ids, f"{location}.source_refs", errors)
        validate_ref_ids(component.get("entrypoint_refs"), reference_ids, f"{location}.entrypoint_refs", errors)
    return component_ids


def validate_reference_affinity(
        catalog: dict[str, dict[str, Any]],
        components: list[Any],
        errors: list[str],
) -> None:
    """防止组件元数据引用另一个组件的源码路径。"""

    for index, component in enumerate(components):
        if not isinstance(component, dict) or not isinstance(component.get("id"), str):
            continue
        component_id = component["id"]
        for field in ("profile_ref", "source_refs", "entrypoint_refs"):
            values = [component.get(field)] if field == "profile_ref" else component.get(field, [])
            if not isinstance(values, list):
                continue
            for reference_id in values:
                reference = catalog.get(reference_id)
                if not isinstance(reference, dict):
                    continue
                if reference.get("scope") == "component" and reference.get("component") != component_id:
                    errors.append(f"components[{index}].{field} 引用了其他组件：{reference_id}")


def validate_hierarchy_v4(
        value: Any,
        scope: Any,
        component_ids: set[str],
        active_components: list[str] | None,
        reference_ids: set[str],
        errors: list[str],
) -> None:
    """校验工作台根、组件叶与可选语义分片的所有权关系。"""

    fields = {"role", "child_contexts", "shard_contexts"}
    if not isinstance(value, dict) or set(value) != fields:
        errors.append("hierarchy 必须包含且仅包含 role、child_contexts、shard_contexts")
        return
    role = value.get("role")
    expected_roles = {"workspace": "workspace_root", "component": "component_leaf", "shard": "semantic_shard"}
    if role != expected_roles.get(scope):
        errors.append(f"scope={scope} 必须使用 hierarchy.role={expected_roles.get(scope)}")
    children = value.get("child_contexts")
    shards = value.get("shard_contexts")
    if not isinstance(children, list) or not isinstance(shards, list):
        errors.append("hierarchy.child_contexts 与 shard_contexts 必须是数组")
        return
    child_components: list[str] = []
    for index, child in enumerate(children):
        location = f"hierarchy.child_contexts[{index}]"
        if not isinstance(child, dict) or set(child) != {"component", "context_ref"}:
            errors.append(f"{location} 必须仅包含 component、context_ref")
            continue
        component = child.get("component")
        if component not in component_ids or component in child_components:
            errors.append(f"{location}.component 必须唯一引用已声明组件")
        else:
            child_components.append(component)
        if child.get("context_ref") not in reference_ids:
            errors.append(f"{location}.context_ref 必须引用 reference_catalog")
    shard_ids: set[str] = set()
    for index, shard in enumerate(shards):
        location = f"hierarchy.shard_contexts[{index}]"
        if not isinstance(shard, dict) or set(shard) != {"id", "context_ref"}:
            errors.append(f"{location} 必须仅包含 id、context_ref")
            continue
        shard_id = validate_id(shard.get("id"), f"{location}.id", errors)
        if shard_id in shard_ids:
            errors.append(f"{location}.id 重复：{shard_id}")
        elif shard_id:
            shard_ids.add(shard_id)
        if shard.get("context_ref") not in reference_ids:
            errors.append(f"{location}.context_ref 必须引用 reference_catalog")
    if scope == "workspace":
        if active_components is not None and set(active_components) != component_ids:
            errors.append("workspace bootstrap.active_components 必须覆盖全部已声明组件")
        if active_components is not None and set(child_components) != set(active_components):
            errors.append("workspace child_contexts 必须覆盖全部 Active 组件")
        if shards:
            errors.append("workspace_root 不得声明 shard_contexts")
    elif scope == "component":
        if len(component_ids) != 1 or active_components is None or len(active_components) != 1:
            errors.append("component Context 必须只声明一个 Active 组件")
        if children:
            errors.append("component_leaf 不得声明 child_contexts")
    elif scope == "shard":
        if len(component_ids) != 1 or active_components is None or len(active_components) != 1:
            errors.append("shard Context 必须只声明一个所属组件")
        if children or shards:
            errors.append("semantic_shard 不得声明下级 Context")


def validate_task_routes_v4(
        value: Any,
        component_ids: set[str],
        reference_ids: set[str],
        errors: list[str],
) -> tuple[set[str], list[dict[str, Any]]]:
    """校验意图路由、证据门和源码扩展方向。"""

    if not isinstance(value, list):
        errors.append("task_routes 必须是数组")
        return set(), []
    fields = {
        "id",
        "intent",
        "components",
        "attention_refs",
        "expand",
        "semantic_nodes",
        "contract_ids",
        "required_evidence",
        "completion_rule",
    }
    route_ids: set[str] = set()
    valid_routes: list[dict[str, Any]] = []
    for index, route in enumerate(value):
        location = f"task_routes[{index}]"
        if not isinstance(route, dict) or set(route) != fields:
            errors.append(f"{location} 必须包含且仅包含标准 v4 路由字段")
            continue
        route_id = validate_id(route.get("id"), f"{location}.id", errors)
        if route_id in route_ids:
            errors.append(f"{location}.id 重复：{route_id}")
        elif route_id:
            route_ids.add(route_id)
        if not isinstance(route.get("intent"), str) or not route["intent"]:
            errors.append(f"{location}.intent 必须是非空字符串")
        components = route.get("components")
        if not isinstance(components, list) or not all(item in component_ids for item in components):
            errors.append(f"{location}.components 必须是已声明组件 ID 数组")
        elif len(components) != len(set(components)):
            errors.append(f"{location}.components 不得重复")
        validate_ref_ids(route.get("attention_refs"), reference_ids, f"{location}.attention_refs", errors)
        validate_ref_ids(route.get("required_evidence"), reference_ids, f"{location}.required_evidence", errors)
        expansion = route.get("expand")
        if not isinstance(expansion, list) or not all(item in EXPANSION_DIRECTIONS for item in expansion):
            errors.append(f"{location}.expand 必须是标准扩展方向数组")
        if route.get("completion_rule") != COMPLETION_RULE:
            errors.append(f"{location}.completion_rule 必须为 {COMPLETION_RULE}")
        for field in ("semantic_nodes", "contract_ids"):
            values = route.get(field)
            if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
                errors.append(f"{location}.{field} 必须是 ID 数组")
        valid_routes.append(route)
    return route_ids, valid_routes


def validate_contracts_v4(
        value: Any,
        reference_ids: set[str],
        errors: list[str],
) -> set[str]:
    """校验 producer→artifact→consumer→validator/test 跨组件契约。"""

    if not isinstance(value, list):
        errors.append("contracts 必须是数组")
        return set()
    fields = {
        "id",
        "summary",
        "producer_refs",
        "artifact_refs",
        "consumer_refs",
        "validator_refs",
        "test_refs",
        "confidence",
    }
    contract_ids: set[str] = set()
    for index, contract in enumerate(value):
        location = f"contracts[{index}]"
        if not isinstance(contract, dict) or set(contract) != fields:
            errors.append(f"{location} 必须包含且仅包含标准契约字段")
            continue
        contract_id = validate_id(contract.get("id"), f"{location}.id", errors)
        if contract_id in contract_ids:
            errors.append(f"{location}.id 重复：{contract_id}")
        elif contract_id:
            contract_ids.add(contract_id)
        if not isinstance(contract.get("summary"), str) or not contract["summary"]:
            errors.append(f"{location}.summary 必须是非空字符串")
        for field in ("producer_refs", "artifact_refs", "consumer_refs"):
            validate_ref_ids(contract.get(field), reference_ids, f"{location}.{field}", errors, require_non_empty=True)
        for field in ("validator_refs", "test_refs"):
            validate_ref_ids(contract.get(field), reference_ids, f"{location}.{field}", errors)
        if contract.get("confidence") not in CONFIDENCE_VALUES:
            errors.append(f"{location}.confidence 必须是标准置信度")
    return contract_ids


def validate_semantic_nodes_v4(
        value: Any,
        reference_ids: set[str],
        errors: list[str],
) -> set[str]:
    """校验可局部失效的语义图节点。"""

    if not isinstance(value, list):
        errors.append("semantic_nodes 必须是数组")
        return set()
    fields = {"id", "kind", "claim", "evidence_refs", "depends_on", "confidence"}
    node_ids: set[str] = set()
    valid_nodes: list[dict[str, Any]] = []
    for index, node in enumerate(value):
        location = f"semantic_nodes[{index}]"
        if not isinstance(node, dict) or set(node) != fields:
            errors.append(f"{location} 必须包含且仅包含标准语义节点字段")
            continue
        node_id = validate_id(node.get("id"), f"{location}.id", errors)
        if node_id in node_ids:
            errors.append(f"{location}.id 重复：{node_id}")
        elif node_id:
            node_ids.add(node_id)
        if node.get("kind") not in SEMANTIC_KINDS:
            errors.append(f"{location}.kind 必须是标准语义类型")
        if not isinstance(node.get("claim"), str) or not node["claim"]:
            errors.append(f"{location}.claim 必须是非空字符串")
        validate_ref_ids(node.get("evidence_refs"), reference_ids, f"{location}.evidence_refs", errors, require_non_empty=True)
        if not isinstance(node.get("depends_on"), list) or not all(isinstance(item, str) for item in node["depends_on"]):
            errors.append(f"{location}.depends_on 必须是语义节点 ID 数组")
        if node.get("confidence") not in CONFIDENCE_VALUES:
            errors.append(f"{location}.confidence 必须是标准置信度")
        valid_nodes.append(node)
    for index, node in enumerate(valid_nodes):
        for dependency in node.get("depends_on", []):
            if dependency not in node_ids or dependency == node.get("id"):
                errors.append(f"semantic_nodes[{index}].depends_on 含悬空或自引用 ID：{dependency}")
    return node_ids


def validate_summary_v4(
        value: Any,
        route_ids: set[str],
        reference_ids: set[str],
        allow_incomplete: bool,
        errors: list[str],
) -> None:
    """校验根级摘要；详细实现必须留在语义节点与组件叶。"""

    if not isinstance(value, dict) or set(value) != {"purpose", "architecture", "key_flows"}:
        errors.append("summary 必须包含且仅包含 purpose、architecture、key_flows")
        return
    if not isinstance(value.get("purpose"), str) or (not value["purpose"] and not allow_incomplete):
        errors.append("summary.purpose 必须是非空字符串")
    architecture = value.get("architecture")
    if (
            not isinstance(architecture, list)
            or (not architecture and not allow_incomplete)
            or not all(isinstance(item, str) and item for item in architecture)
    ):
        errors.append("summary.architecture 必须是非空字符串数组")
    flows = value.get("key_flows")
    if not isinstance(flows, list):
        errors.append("summary.key_flows 必须是数组")
        return
    flow_ids: set[str] = set()
    for index, flow in enumerate(flows):
        location = f"summary.key_flows[{index}]"
        if not isinstance(flow, dict) or set(flow) != {"id", "summary", "route_ids", "evidence_refs", "confidence"}:
            errors.append(f"{location} 必须包含且仅包含标准 v4 关键流字段")
            continue
        flow_id = validate_id(flow.get("id"), f"{location}.id", errors)
        if flow_id in flow_ids:
            errors.append(f"{location}.id 重复：{flow_id}")
        elif flow_id:
            flow_ids.add(flow_id)
        if not isinstance(flow.get("summary"), str) or not flow["summary"]:
            errors.append(f"{location}.summary 必须是非空字符串")
        flow_routes = flow.get("route_ids")
        if not isinstance(flow_routes, list) or not all(item in route_ids for item in flow_routes):
            errors.append(f"{location}.route_ids 必须引用 task_routes")
        validate_ref_ids(flow.get("evidence_refs"), reference_ids, f"{location}.evidence_refs", errors)
        if flow.get("confidence") not in CONFIDENCE_VALUES:
            errors.append(f"{location}.confidence 必须是标准置信度")


def validate_experiment_pointer_v4(value: Any, reference_ids: set[str], errors: list[str]) -> None:
    """校验独立实验溯源文件指针，不在 Context 中复制实验日志。"""

    if not isinstance(value, dict) or set(value) != {"path_ref", "required_states"}:
        errors.append("experiment_provenance 必须仅包含 path_ref、required_states")
        return
    path_ref = value.get("path_ref")
    if path_ref is not None and path_ref not in reference_ids:
        errors.append("experiment_provenance.path_ref 必须为 null 或引用 reference_catalog")
    expected = ["implemented", "configured", "executed", "reported"]
    if value.get("required_states") != expected:
        errors.append("experiment_provenance.required_states 必须依次声明 implemented/configured/executed/reported")


def validate_boundaries_v4(value: Any, reference_ids: set[str], errors: list[str]) -> None:
    """校验 Profile 或独立仓库来源的边界覆盖；完整分类不在 Context 中重复。"""

    if not isinstance(value, dict) or set(value) != {"policy_source", "overrides"}:
        errors.append("boundaries 必须仅包含 policy_source、overrides")
        return
    if value.get("policy_source") not in {
            "profile.path_policy",
            "profile.legacy_artifacts",
            "repository.layout",
    }:
        errors.append("boundaries.policy_source 必须指向 Profile 或独立仓库路径分类来源")
    overrides = value.get("overrides")
    if not isinstance(overrides, list):
        errors.append("boundaries.overrides 必须是数组")
        return
    seen_refs: set[str] = set()
    for index, override in enumerate(overrides):
        location = f"boundaries.overrides[{index}]"
        if not isinstance(override, dict) or set(override) != {"ref", "category", "reason"}:
            errors.append(f"{location} 必须仅包含 ref、category、reason")
            continue
        reference_id = override.get("ref")
        if reference_id not in reference_ids or reference_id in seen_refs:
            errors.append(f"{location}.ref 必须唯一引用 reference_catalog")
        elif isinstance(reference_id, str):
            seen_refs.add(reference_id)
        if override.get("category") not in PATH_CATEGORIES:
            errors.append(f"{location}.category 必须是标准路径类别")
        if not isinstance(override.get("reason"), str) or not override["reason"]:
            errors.append(f"{location}.reason 必须是非空字符串")


def validate_refresh_v4(
        value: Any,
        reference_ids: set[str],
        semantic_node_ids: set[str],
        require_profile_fingerprint: bool,
        require_active_fingerprint: bool,
        allow_incomplete: bool,
        errors: list[str],
) -> None:
    """校验 Profile/Active 与语义节点级证据指纹。"""

    fields = {"profile_fingerprint", "active_fingerprint", "semantic_fingerprints"}
    if not isinstance(value, dict) or set(value) != fields:
        errors.append("refresh 必须仅包含 profile_fingerprint、active_fingerprint、semantic_fingerprints")
        return
    fingerprint_requirements = {
        "profile_fingerprint": require_profile_fingerprint,
        "active_fingerprint": require_active_fingerprint,
    }
    for field, required in fingerprint_requirements.items():
        fingerprint = value.get(field)
        if fingerprint is None and (allow_incomplete or not required):
            continue
        if not isinstance(fingerprint, str) or not FINGERPRINT_PATTERN.fullmatch(fingerprint):
            errors.append(f"refresh.{field} 必须是 sha256:<64位十六进制> 指纹")
    records = value.get("semantic_fingerprints")
    if not isinstance(records, list):
        errors.append("refresh.semantic_fingerprints 必须是数组")
        return
    covered: set[str] = set()
    for index, record in enumerate(records):
        location = f"refresh.semantic_fingerprints[{index}]"
        if not isinstance(record, dict) or set(record) != {"semantic_node", "evidence"}:
            errors.append(f"{location} 必须仅包含 semantic_node、evidence")
            continue
        node_id = record.get("semantic_node")
        if node_id not in semantic_node_ids or node_id in covered:
            errors.append(f"{location}.semantic_node 必须唯一引用 semantic_nodes")
        elif isinstance(node_id, str):
            covered.add(node_id)
        evidence = record.get("evidence")
        if not isinstance(evidence, list) or (not evidence and not allow_incomplete):
            errors.append(f"{location}.evidence 必须是非空数组")
            continue
        for evidence_index, item in enumerate(evidence):
            item_location = f"{location}.evidence[{evidence_index}]"
            if not isinstance(item, dict) or set(item) != {"ref", "sha256"}:
                errors.append(f"{item_location} 必须仅包含 ref、sha256")
                continue
            if item.get("ref") not in reference_ids:
                errors.append(f"{item_location}.ref 必须引用 reference_catalog")
            if not isinstance(item.get("sha256"), str) or not FINGERPRINT_PATTERN.fullmatch(item["sha256"]):
                errors.append(f"{item_location}.sha256 必须是 sha256:<64位十六进制> 指纹")
    if not allow_incomplete and covered != semantic_node_ids:
        errors.append("refresh.semantic_fingerprints 必须覆盖全部 semantic_nodes")


def scan_sensitive_fields(value: Any, errors: list[str], location: str = "$") -> None:
    """递归拒绝疑似凭据字段名。"""

    if isinstance(value, dict):
        for key, nested in value.items():
            if SENSITIVE_KEY_PATTERN.search(key):
                errors.append(f"{location}.{key} 疑似敏感字段，禁止写入 AI_CONTEXT")
            scan_sensitive_fields(nested, errors, f"{location}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            scan_sensitive_fields(nested, errors, f"{location}[{index}]")


def validate_v4(value: dict[str, Any], allow_incomplete: bool) -> list[str]:
    """执行 v4 语义图、契约、证据门和局部新鲜度校验。"""

    errors: list[str] = []
    missing = TOP_LEVEL_FIELDS_V4 - set(value)
    unexpected = set(value) - TOP_LEVEL_FIELDS_V4
    if missing:
        errors.append(f"缺少顶层字段：{', '.join(sorted(missing))}")
    if unexpected:
        errors.append(f"含未定义顶层字段：{', '.join(sorted(unexpected))}")
    if value.get("schema") != SCHEMA_V4:
        errors.append(f"schema 必须为 {SCHEMA_V4}")
    scope = value.get("scope")
    if scope not in {"workspace", "component", "shard"}:
        errors.append("scope 必须为 workspace、component 或 shard")
    if value.get("authority_order") != AUTHORITY_ORDER:
        errors.append("authority_order 必须严格遵循 active/profile/git/source/context")

    raw_catalog = value.get("reference_catalog")
    reference_ids = set(raw_catalog) if isinstance(raw_catalog, dict) else set()
    component_ids = validate_components_v4(value.get("components"), reference_ids, errors)
    catalog = validate_reference_catalog(raw_catalog, component_ids, errors)
    components = value.get("components") if isinstance(value.get("components"), list) else []
    validate_reference_affinity(catalog, components, errors)

    bootstrap = value.get("bootstrap")
    active_components: list[str] | None = None
    if not isinstance(bootstrap, dict) or set(bootstrap) != {"read_before_code", "active_components"}:
        errors.append("bootstrap 必须仅包含 read_before_code、active_components")
    else:
        validate_ref_ids(bootstrap.get("read_before_code"), reference_ids, "bootstrap.read_before_code", errors)
        active = bootstrap.get("active_components")
        if isinstance(active, list) and all(item in component_ids for item in active) and len(active) == len(set(active)):
            active_components = active
        else:
            errors.append("bootstrap.active_components 必须是无重复的已声明组件 ID 数组")

    route_ids, valid_routes = validate_task_routes_v4(value.get("task_routes"), component_ids, reference_ids, errors)
    contract_ids = validate_contracts_v4(value.get("contracts"), reference_ids, errors)
    semantic_node_ids = validate_semantic_nodes_v4(value.get("semantic_nodes"), reference_ids, errors)
    for index, route in enumerate(valid_routes):
        for field, known_ids in (("semantic_nodes", semantic_node_ids), ("contract_ids", contract_ids)):
            for item in route.get(field, []):
                if item not in known_ids:
                    errors.append(f"task_routes[{index}].{field} 含悬空 ID：{item}")

    validate_summary_v4(value.get("summary"), route_ids, reference_ids, allow_incomplete, errors)
    validate_hierarchy_v4(value.get("hierarchy"), scope, component_ids, active_components, reference_ids, errors)
    validate_experiment_pointer_v4(value.get("experiment_provenance"), reference_ids, errors)
    do_not_assume = value.get("do_not_assume")
    if (
            not isinstance(do_not_assume, list)
            or (not do_not_assume and not allow_incomplete)
            or not all(isinstance(item, str) and item for item in do_not_assume)
    ):
        errors.append("do_not_assume 必须是非空字符串数组")
    validate_boundaries_v4(value.get("boundaries"), reference_ids, errors)
    profile_required = any(
        isinstance(component, dict) and component.get("profile_ref") is not None
        for component in components
    )
    active_required = any(
        isinstance(component, dict)
        and isinstance(component.get("locator"), dict)
        and component["locator"].get("kind") == "active_component"
        for component in components
    )
    validate_refresh_v4(
        value.get("refresh"),
        reference_ids,
        semantic_node_ids,
        profile_required,
        active_required,
        allow_incomplete,
        errors,
    )
    scan_sensitive_fields(value, errors)
    return errors


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""

    parser = argparse.ArgumentParser(description="校验 v3/v4 分层 AI_CONTEXT.json 的机器优先 Schema。")
    parser.add_argument("--path", required=True, help="AI_CONTEXT.json 路径")
    parser.add_argument("--allow-incomplete", action="store_true", help="允许模板中的空摘要和刷新指纹")
    parser.add_argument("--max-bytes", type=int, help="覆盖按节点角色推导的硬体积限制")
    return parser.parse_args()


def default_max_bytes(value: dict[str, Any] | None) -> int:
    """v3 固定 16 KiB；v4 仅对含语义分片的复杂组件叶放宽至 24 KiB。"""

    if not isinstance(value, dict) or value.get("schema") != SCHEMA_V4:
        return 16 * 1024
    hierarchy = value.get("hierarchy")
    if isinstance(hierarchy, dict) and hierarchy.get("role") == "component_leaf" and hierarchy.get("shard_contexts"):
        return 24 * 1024
    return 16 * 1024


def main() -> int:
    """输出确定性校验结果，并以退出码表示是否通过。"""

    args = parse_args()
    path = Path(args.path).expanduser()
    if args.max_bytes is not None and args.max_bytes <= 0:
        print("ERROR: --max-bytes 必须为正数")
        return 2
    try:
        size = path.stat().st_size
    except OSError as exc:
        print(f"ERROR: 无法读取文件大小：{exc}")
        return 1
    value, errors = read_json(path)
    max_bytes = args.max_bytes or default_max_bytes(value)
    if size > max_bytes:
        errors.append(f"文件大小 {size} bytes 超过限制 {max_bytes} bytes")
    if value is not None:
        schema = value.get("schema")
        if schema == SCHEMA_V3:
            errors.extend(validate_v3(value, args.allow_incomplete))
        elif schema == SCHEMA_V4:
            errors.extend(validate_v4(value, args.allow_incomplete))
        else:
            errors.append(f"schema 必须是受支持版本：{', '.join(sorted(SUPPORTED_SCHEMAS))}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"OK: {path} ({size} bytes, {value.get('schema') if value else 'unknown'}, limit={max_bytes})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
