# -*- coding: utf-8 -*-
"""按任务意图生成临时、只读、可机读的最小代码库理解包。"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from collect_orientation_context import collect_context


BUNDLE_SCHEMA = "codebase-orientation-bundle/v1"
GLOBAL_MARKERS = {"global", "overall", "workspace", "全局", "整体", "所有", "总览", "项目脉络"}


def read_json(path: Path) -> dict[str, Any] | None:
    """读取 Context 对象；缺失或损坏节点保留为不可用状态。"""

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def text_tokens(value: str) -> set[str]:
    """提取英文标识符与中文短语，供确定性的轻量意图匹配。"""

    return set(re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]{2,}", value.lower()))


def route_score(intent: str, route: dict[str, Any]) -> int:
    """按完整子串和词元交集对任务路由排序。"""

    route_intent = route.get("intent")
    if not isinstance(route_intent, str):
        return 0
    normalized_intent = intent.lower().strip()
    normalized_route = route_intent.lower().strip()
    score = 4 if normalized_route and normalized_route in normalized_intent else 0
    score += len(text_tokens(normalized_intent) & text_tokens(normalized_route))
    return score


def context_routes(context: dict[str, Any] | None) -> list[dict[str, Any]]:
    """统一读取 v3 attention_routes 与 v4 task_routes。"""

    if not isinstance(context, dict):
        return []
    field = "task_routes" if context.get("schema") == "ai-project-context/v4" else "attention_routes"
    routes = context.get(field)
    return [route for route in routes if isinstance(route, dict)] if isinstance(routes, list) else []


def select_routes(intent: str, context: dict[str, Any] | None) -> list[dict[str, Any]]:
    """返回最高分路由；无命中时不伪造路由。"""

    scored = [(route_score(intent, route), route) for route in context_routes(context)]
    best = max((score for score, _ in scored), default=0)
    return [route for score, route in scored if score == best] if best else []


def compact_git(value: Any) -> dict[str, Any] | None:
    """保留复现所需 Git 身份，移除长状态清单和远程细节。"""

    if not isinstance(value, dict):
        return None
    return {key: value.get(key) for key in ("root", "branch", "head", "describe", "dirty")}


def compact_component(component: dict[str, Any]) -> dict[str, Any]:
    """压缩组件库存，同时保留路径分类漂移和 Context 位置。"""

    profile = component.get("profile") if isinstance(component.get("profile"), dict) else {}
    classification = component.get("path_classification")
    classification = classification if isinstance(classification, dict) else {}
    return {
        "key": component.get("key") or profile.get("component"),
        "resolved_root": component.get("resolved_root"),
        "profile": {
            "path": profile.get("path"),
            "version": profile.get("version"),
            "environment_key": profile.get("environment_key"),
            "entrypoints": profile.get("entrypoints", []),
        },
        "git": compact_git(component.get("git")),
        "context_path": (component.get("ai_context_inputs") or {}).get("expected_path"),
        "context_freshness": (component.get("ai_context_inputs") or {}).get("freshness"),
        "classification_diagnostics": classification.get("diagnostics", []),
    }


def references_used_by_v4(context: dict[str, Any], routes: list[dict[str, Any]]) -> set[str]:
    """收集已选路由、语义节点和契约直接依赖的引用 ID。"""

    reference_ids: set[str] = set()
    route_node_ids: set[str] = set()
    route_contract_ids: set[str] = set()
    for route in routes:
        for field in ("attention_refs", "required_evidence"):
            values = route.get(field, [])
            if isinstance(values, list):
                reference_ids.update(value for value in values if isinstance(value, str))
        route_node_ids.update(value for value in route.get("semantic_nodes", []) if isinstance(value, str))
        route_contract_ids.update(value for value in route.get("contract_ids", []) if isinstance(value, str))

    semantic_nodes = context.get("semantic_nodes")
    if isinstance(semantic_nodes, list):
        for node in semantic_nodes:
            if not isinstance(node, dict) or node.get("id") not in route_node_ids:
                continue
            reference_ids.update(value for value in node.get("evidence_refs", []) if isinstance(value, str))
    contracts = context.get("contracts")
    if isinstance(contracts, list):
        for contract in contracts:
            if not isinstance(contract, dict) or contract.get("id") not in route_contract_ids:
                continue
            for field in ("producer_refs", "artifact_refs", "consumer_refs", "validator_refs", "test_refs"):
                reference_ids.update(value for value in contract.get(field, []) if isinstance(value, str))
    return reference_ids


def compact_context(context: dict[str, Any] | None, intent: str) -> dict[str, Any] | None:
    """提取任务相关语义，不把整个持久 Context 复制进临时包。"""

    if not isinstance(context, dict):
        return None
    routes = select_routes(intent, context)
    result: dict[str, Any] = {
        "schema": context.get("schema"),
        "scope": context.get("scope"),
        "summary": context.get("summary"),
        "matched_routes": routes,
        "do_not_assume": context.get("do_not_assume", []),
    }
    if context.get("schema") != "ai-project-context/v4":
        result["concepts"] = context.get("concepts", [])
        return result

    node_ids = {
        value
        for route in routes
        for value in route.get("semantic_nodes", [])
        if isinstance(value, str)
    }
    contract_ids = {
        value
        for route in routes
        for value in route.get("contract_ids", [])
        if isinstance(value, str)
    }
    semantic_nodes = context.get("semantic_nodes", [])
    contracts = context.get("contracts", [])
    result["semantic_nodes"] = [
        node for node in semantic_nodes if isinstance(node, dict) and node.get("id") in node_ids
    ]
    result["contracts"] = [
        contract for contract in contracts if isinstance(contract, dict) and contract.get("id") in contract_ids
    ]
    catalog = context.get("reference_catalog")
    catalog = catalog if isinstance(catalog, dict) else {}
    reference_ids = references_used_by_v4(context, routes)
    result["reference_catalog"] = {key: catalog[key] for key in sorted(reference_ids) if key in catalog}
    return result


def workspace_nodes(inventory: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, dict[str, Any]]]:
    """读取工作台根 Context 与 Active 组件 Context。"""

    workspace = inventory.get("workspace")
    if not isinstance(workspace, dict):
        return None, {}
    tree = workspace.get("ai_context_tree")
    tree = tree if isinstance(tree, dict) else {}
    root_record = tree.get("root") if isinstance(tree.get("root"), dict) else {}
    root_path = root_record.get("expected_path")
    root_context = read_json(Path(root_path)) if isinstance(root_path, str) else None
    child_contexts: dict[str, dict[str, Any]] = {}
    for child in tree.get("children", []):
        if not isinstance(child, dict):
            continue
        key, path = child.get("key"), child.get("expected_path")
        context = read_json(Path(path)) if isinstance(path, str) else None
        if isinstance(key, str) and context is not None:
            child_contexts[key] = context
    return root_context, child_contexts


def select_component_keys(
        intent: str,
        requested: list[str],
        available: list[str],
        root_context: dict[str, Any] | None,
) -> tuple[list[str], list[dict[str, Any]]]:
    """优先采用显式组件；否则从根路由推导，最后保守选择全部 Active 组件。"""

    if requested:
        unknown = sorted(set(requested) - set(available))
        if unknown:
            raise ValueError(f"未知 Active 组件：{', '.join(unknown)}")
        return sorted(set(requested)), select_routes(intent, root_context)
    root_routes = select_routes(intent, root_context)
    if any(marker in intent.lower() for marker in GLOBAL_MARKERS):
        return available, root_routes
    routed = {
        component
        for route in root_routes
        for component in route.get("components", [])
        if isinstance(component, str) and component in available
    }
    return (sorted(routed) if routed else available), root_routes


def shrink_bundle(bundle: dict[str, Any], max_bytes: int) -> dict[str, Any]:
    """超过预算时按可恢复顺序压缩，绝不伪造被省略的事实。"""

    def encoded_size() -> int:
        return len(json.dumps(bundle, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))

    if encoded_size() <= max_bytes:
        return bundle
    bundle["truncated_sections"].append("component.git")
    for component in bundle["components"]:
        component.pop("git", None)
    if encoded_size() <= max_bytes:
        return bundle
    bundle["truncated_sections"].append("context.summary.architecture")
    for context in bundle["contexts"]:
        summary = context.get("content", {}).get("summary")
        if isinstance(summary, dict):
            summary["architecture"] = []
    if encoded_size() <= max_bytes:
        return bundle
    bundle["truncated_sections"].append("unmatched concepts")
    for context in bundle["contexts"]:
        content = context.get("content")
        if isinstance(content, dict) and not content.get("matched_routes"):
            content.pop("concepts", None)
    bundle["over_budget"] = encoded_size() > max_bytes
    return bundle


def build_bundle(path: Path, intent: str, requested_components: list[str], max_bytes: int) -> dict[str, Any]:
    """构建任务特定理解包；其中所有持久事实仍需回到当前源码验证。"""

    inventory = collect_context(path)
    root_context, child_contexts = workspace_nodes(inventory)
    workspace = inventory.get("workspace")
    workspace_components = workspace.get("components", []) if isinstance(workspace, dict) else []
    if not workspace_components and isinstance(inventory.get("component"), dict):
        workspace_components = [inventory["component"]]
    components_by_key = {
        str(component.get("key") or (component.get("profile") or {}).get("component")): component
        for component in workspace_components
        if isinstance(component, dict)
    }
    available = sorted(key for key in components_by_key if key and key != "None")
    selected, root_routes = select_component_keys(intent, requested_components, available, root_context)

    contexts: list[dict[str, Any]] = []
    if root_context is not None:
        contexts.append({"role": "workspace_root", "content": compact_context(root_context, intent)})
    for key in selected:
        context = child_contexts.get(key)
        if context is not None:
            contexts.append({"role": "component_leaf", "component": key, "content": compact_context(context, intent)})
    missing_contexts = [key for key in selected if key not in child_contexts]
    bundle = {
        "schema": BUNDLE_SCHEMA,
        "task": {"intent": intent, "requested_components": requested_components},
        "authority_order": ["active", "profile", "git", "source", "context"],
        "selected_components": selected,
        "matched_root_routes": root_routes,
        "workspace_context_freshness": (
            (workspace.get("ai_context_inputs") or {}).get("freshness") if isinstance(workspace, dict) else None
        ),
        "components": [compact_component(components_by_key[key]) for key in selected],
        "contexts": contexts,
        "missing_contexts": missing_contexts,
        "source_expansion_required": True,
        "completion_rule": "all_required_evidence_or_explicit_gap",
        "truncated_sections": [],
        "over_budget": False,
    }
    return shrink_bundle(bundle, max_bytes)


def parse_args() -> argparse.Namespace:
    """解析任务意图、组件选择和临时包体积预算。"""

    parser = argparse.ArgumentParser(description="按意图生成只读、最小化的代码库理解包。")
    parser.add_argument("--path", required=True, help="工作台、组件或普通仓库路径")
    parser.add_argument("--intent", required=True, help="本次任务的自然语言意图")
    parser.add_argument("--component", action="append", default=[], help="显式 Active 组件键，可重复")
    parser.add_argument("--max-bytes", type=int, default=32 * 1024, help="Bundle 最大建议字节数，默认 32768")
    return parser.parse_args()


def main() -> int:
    """输出 UTF-8 JSON；除标准输出外不创建任何持久文件。"""

    args = parse_args()
    if args.max_bytes <= 0:
        print("ERROR: --max-bytes 必须为正数")
        return 2
    try:
        bundle = build_bundle(Path(args.path), args.intent, args.component, args.max_bytes)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 2
    print(json.dumps(bundle, ensure_ascii=False, separators=(",", ":")))
    return 1 if bundle["over_budget"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
