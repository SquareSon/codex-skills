# -*- coding: utf-8 -*-
"""只读收集 ProjectProfile、Active 链接和 Git 证据，供代码库理解技能使用。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import xml.etree.ElementTree as element_tree
from pathlib import Path
from typing import Any


MAX_STATUS_LINES = 100
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
LEGACY_BOUNDARY_CATEGORIES = {
    "generated": "generated_ephemeral",
    "third_party": "third_party",
    "historical": "historical",
    "auxiliary": "auxiliary",
}


def read_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    """读取 JSON 对象；错误保留在结果中而不阻断其他只读发现。"""

    try:
        content = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, str(exc)
    if not isinstance(content, dict):
        return None, "JSON 根节点不是对象"
    return content, None


def sha256sum(path: Path) -> str:
    """计算小型 Profile 文件的 SHA-256 作为可复现证据。"""

    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_fingerprint(path: Path) -> str:
    """为文件内容添加 Schema 使用的 SHA-256 前缀。"""

    return f"sha256:{sha256sum(path)}"


def stable_fingerprint(value: Any) -> str:
    """计算确定性 JSON 数据的 SHA-256，避免依赖本机绝对路径。"""

    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"


def ancestor_directories(start: Path) -> list[Path]:
    """返回从目标目录到文件系统根目录的候选目录。"""

    directory = start if start.is_dir() else start.parent
    return [directory, *directory.parents]


def find_profile(start: Path, file_name: str) -> Path | None:
    """从目标向上查找 profile 文件，避免扫描无关的同级目录。"""

    for directory in ancestor_directories(start):
        candidate = directory / "profile" / file_name
        if candidate.is_file():
            return candidate
    return None


def component_profile_path(component_root: Path) -> Path | None:
    """支持通用 profile 路径，并只读兼容历史目录名。"""

    canonical_path = component_root / "profile" / "component.json"
    if canonical_path.is_file():
        return canonical_path
    legacy_path = component_root / "chapter4_profile" / "component.json"
    return legacy_path if legacy_path.is_file() else None


def active_workspace_profile(component_root: Path) -> Path | None:
    """从 Active 子项目反查相邻工作台，避免把软链接目标误当成独立上下文。"""

    candidate_parents = (component_root.parent, component_root.parent.parent)
    visited_workspaces: set[Path] = set()
    for workspace_parent in candidate_parents:
        try:
            candidates = sorted(path for path in workspace_parent.iterdir() if path.is_dir())
        except OSError:
            continue
        for workspace_root in candidates:
            if workspace_root in visited_workspaces:
                continue
            visited_workspaces.add(workspace_root)
            profile_path = workspace_root / "profile" / "workspace.json"
            content, error = read_json(profile_path) if profile_path.is_file() else (None, "missing")
            active_name = content.get("active_directory_name") if isinstance(content, dict) else None
            if error or content is None or not isinstance(active_name, str):
                continue
            active_root = workspace_root.parent / active_name
            for item in content.get("components", []):
                if not isinstance(item, dict) or not isinstance(item.get("key"), str):
                    continue
                candidate = active_root / item["key"]
                if candidate.exists() and candidate.resolve() == component_root.resolve():
                    return profile_path
    return None


def run_git(path: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    """执行无副作用 Git 查询，失败时由调用方作为缺失证据处理。"""

    command = ["git", "-C", str(path), *arguments]
    try:
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return subprocess.CompletedProcess(command, returncode=127, stdout="", stderr=str(exc))


def git_text(path: Path, *arguments: str) -> str | None:
    """读取成功 Git 查询的单行结果。"""

    result = run_git(path, *arguments)
    return result.stdout.strip() if result.returncode == 0 else None


def sanitize_remote_url(url: str) -> str:
    """隐藏 HTTP 远程地址中可能嵌入的凭据。"""

    return re.sub(r"(://)[^/@\s]+@", r"\1***@", url)


def git_context(path: Path) -> dict[str, Any] | None:
    """收集仓库身份、工作树状态和经过脱敏的远程信息。"""

    root_text = git_text(path, "rev-parse", "--show-toplevel")
    if not root_text:
        return None
    root = Path(root_text)
    status_result = run_git(root, "status", "--short")
    status_lines = status_result.stdout.splitlines()[:MAX_STATUS_LINES]
    remote_result = run_git(root, "remote", "-v")
    remotes: list[dict[str, str]] = []
    seen_remotes: set[tuple[str, str, str]] = set()
    for line in remote_result.stdout.splitlines():
        parts = line.split(maxsplit=2)
        if len(parts) != 3:
            continue
        name, url, direction = parts
        record = (name, sanitize_remote_url(url), direction.strip("()"))
        if record not in seen_remotes:
            seen_remotes.add(record)
            remotes.append({"name": record[0], "url": record[1], "direction": record[2]})
    return {
        "root": str(root),
        "branch": git_text(root, "branch", "--show-current"),
        "head": git_text(root, "rev-parse", "HEAD"),
        "describe": git_text(root, "describe", "--tags", "--always", "--dirty"),
        "dirty": bool(status_lines),
        "status_lines": status_lines,
        "status_truncated": len(status_result.stdout.splitlines()) > MAX_STATUS_LINES,
        "remotes": remotes,
    }


def profile_summary(profile_path: Path) -> dict[str, Any]:
    """只提取理解项目所需的 Profile 字段，避免输出本机私有配置。"""

    content, error = read_json(profile_path)
    summary: dict[str, Any] = {
        "path": str(profile_path),
        "sha256": sha256sum(profile_path),
    }
    if error or content is None:
        summary["error"] = error
        return summary
    identity = content.get("identity", {})
    runtime = content.get("runtime", {})
    ide = content.get("ide", {})
    entrypoints = content.get("entrypoints", [])
    artifacts = content.get("artifacts", {})
    identity = identity if isinstance(identity, dict) else {}
    runtime = runtime if isinstance(runtime, dict) else {}
    ide = ide if isinstance(ide, dict) else {}
    entrypoints = entrypoints if isinstance(entrypoints, list) else []
    artifacts = artifacts if isinstance(artifacts, dict) else {}
    summary.update(
        {
            "schema_version": content.get("schema_version"),
            "component": content.get("component"),
            "display_name": identity.get("display_name", content.get("display_name")),
            "version": identity.get("version", content.get("version")),
            "environment_key": runtime.get("environment_key", content.get("python_environment")),
            "ide": {
                "source_folders": ide.get("source_folders", []),
                "test_folders": ide.get("test_folders", []),
                "resource_folders": ide.get("resource_folders", []),
                "excluded_folders": ide.get("excluded_folders", content.get("pycharm_exclude_folders", [])),
            },
            "entrypoints": [
                {
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "type": item.get("type"),
                    "path": item.get("path"),
                }
                for item in entrypoints
                if isinstance(item, dict)
            ],
            "artifacts": {
                "generated_folders": artifacts.get("generated_folders", []),
                "third_party_roots": artifacts.get("third_party_roots", []),
            },
            "path_policy": normalize_path_policy(content.get("path_policy")),
        }
    )
    return summary


def normalize_relative_path(value: Any) -> str | None:
    """规范化可移植相对路径；通配符只保留到首个动态片段。"""

    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.strip().replace("\\", "/").lstrip("/")
    static_parts: list[str] = []
    for part in normalized.split("/"):
        if not part or part == ".":
            continue
        if any(marker in part for marker in "*?["):
            break
        if part == "..":
            return None
        static_parts.append(part)
    return "/".join(static_parts) or "."


def normalize_path_policy(value: Any) -> list[dict[str, Any]]:
    """兼容 rules 数组或 category→paths 映射形式的 Profile 路径策略。"""

    raw_rules: list[Any] = []
    if isinstance(value, list):
        raw_rules = value
    elif isinstance(value, dict):
        if isinstance(value.get("rules"), list):
            raw_rules = value["rules"]
        else:
            for category, paths in value.items():
                if category not in PATH_CATEGORIES or not isinstance(paths, list):
                    continue
                raw_rules.extend({"path": path, "category": category} for path in paths)

    rules: list[dict[str, Any]] = []
    for item in raw_rules:
        if not isinstance(item, dict):
            continue
        path = normalize_relative_path(item.get("path"))
        category = item.get("category")
        if path is None or category not in PATH_CATEGORIES:
            continue
        rule = {"path": path, "category": category}
        if isinstance(item.get("reason"), str) and item["reason"]:
            rule["reason"] = item["reason"]
        rules.append(rule)
    return rules


def third_party_context(component_root: Path) -> dict[str, Any]:
    """记录锁定清单和补丁目录的存在性，不展开扫描第三方源码。"""

    lock_root = component_root / "third_party"
    patch_root = component_root / "patches" / "third_party"
    lock_files = sorted(path.name for path in lock_root.glob("lock-*.json")) if lock_root.is_dir() else []
    patch_snapshots = sorted(path.name for path in patch_root.iterdir() if path.is_dir()) if patch_root.is_dir() else []
    return {"lock_files": lock_files, "patch_snapshots": patch_snapshots}


def profile_path_claims(profile: dict[str, Any] | None) -> list[dict[str, Any]]:
    """将显式 path_policy 与旧版 Profile 字段转换为统一分类声明。"""

    if not isinstance(profile, dict):
        return []
    explicit_rules = profile.get("path_policy")
    if isinstance(explicit_rules, list) and explicit_rules:
        return [
            {**rule, "source": "profile.path_policy", "explicit": True}
            for rule in explicit_rules
            if isinstance(rule, dict)
        ]

    claims: list[dict[str, Any]] = []
    ide = profile.get("ide") if isinstance(profile.get("ide"), dict) else {}
    artifacts = profile.get("artifacts") if isinstance(profile.get("artifacts"), dict) else {}
    legacy_fields = (
        (ide.get("source_folders", []), "core", "profile.ide.source_folders"),
        (ide.get("test_folders", []), "test", "profile.ide.test_folders"),
        (ide.get("resource_folders", []), "reference", "profile.ide.resource_folders"),
        (artifacts.get("generated_folders", []), "generated_ephemeral", "profile.artifacts.generated_folders"),
        (artifacts.get("third_party_roots", []), "third_party", "profile.artifacts.third_party_roots"),
    )
    for paths, category, source in legacy_fields:
        if not isinstance(paths, list):
            continue
        for value in paths:
            path = normalize_relative_path(value)
            if path is not None:
                claims.append({"path": path, "category": category, "source": source, "explicit": False})
    for entrypoint in profile.get("entrypoints", []):
        path = normalize_relative_path(entrypoint.get("path")) if isinstance(entrypoint, dict) else None
        if path is not None:
            claims.append(
                {
                    "path": path,
                    "category": "entrypoint",
                    "source": "profile.entrypoints",
                    "explicit": False,
                }
            )
    return claims


def context_path_claims(component_root: Path, component_key: str | None) -> list[dict[str, Any]]:
    """读取本组件 Context 的边界声明；不把 Context 提升为 Profile 权威。"""

    context_path = component_root / "docs" / "ai-guide" / "AI_CONTEXT.json"
    context, error = read_json(context_path) if context_path.is_file() else (None, "missing")
    if error or context is None:
        return []
    schema = context.get("schema")
    boundaries = context.get("boundaries")
    claims: list[dict[str, Any]] = []
    if schema == "ai-project-context/v3" and isinstance(boundaries, dict):
        for field, category in LEGACY_BOUNDARY_CATEGORIES.items():
            for reference in boundaries.get(field, []):
                if not isinstance(reference, dict) or reference.get("scope") != "component":
                    continue
                if component_key and reference.get("component") != component_key:
                    continue
                path = normalize_relative_path(reference.get("path"))
                if path is not None:
                    claims.append(
                        {
                            "path": path,
                            "category": category,
                            "source": f"context.boundaries.{field}",
                            "explicit": False,
                        }
                    )
    elif schema == "ai-project-context/v4" and isinstance(boundaries, dict):
        catalog = context.get("reference_catalog")
        catalog = catalog if isinstance(catalog, dict) else {}
        for override in boundaries.get("overrides", []):
            if not isinstance(override, dict):
                continue
            reference = catalog.get(override.get("ref"))
            if not isinstance(reference, dict) or reference.get("scope") != "component":
                continue
            if component_key and reference.get("component") != component_key:
                continue
            path = normalize_relative_path(reference.get("path"))
            category = override.get("category")
            if path is not None and category in PATH_CATEGORIES:
                claims.append(
                    {
                        "path": path,
                        "category": category,
                        "source": "context.boundaries.overrides",
                        "explicit": True,
                    }
                )
    return claims


def gitignore_exceptions(component_root: Path) -> list[str]:
    """提取 .gitignore 重新纳入规则的静态路径前缀，仅用于发现边界风险。"""

    path = component_root / ".gitignore"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    exceptions = {
        normalized
        for line in lines
        if line.startswith("!")
        if (normalized := normalize_relative_path(line[1:])) is not None
    }
    return sorted(exceptions)


def path_is_within(path: str, parent: str) -> bool:
    """判断规范化路径是否等于或位于父路径之下。"""

    if parent == ".":
        return True
    return path == parent or path.startswith(f"{parent}/")


def classification_diagnostics(
        claims: list[dict[str, Any]],
        exceptions: list[str],
) -> list[dict[str, Any]]:
    """发现同路径冲突、父子覆盖和被边界吞没的 Git 重新纳入路径。"""

    diagnostics: list[dict[str, Any]] = []
    for index, left in enumerate(claims):
        for right in claims[index + 1:]:
            if left["category"] == right["category"]:
                continue
            if left["path"] == right["path"]:
                diagnostics.append(
                    {
                        "kind": "classification_conflict",
                        "path": left["path"],
                        "claims": [
                            {"category": left["category"], "source": left["source"]},
                            {"category": right["category"], "source": right["source"]},
                        ],
                    }
                )
                continue
            if left["path"] == "." or right["path"] == ".":
                continue
            if path_is_within(left["path"], right["path"]) or path_is_within(right["path"], left["path"]):
                specific, broad = (left, right) if len(left["path"]) > len(right["path"]) else (right, left)
                diagnostics.append(
                    {
                        "kind": "classification_overlap",
                        "broad": {"path": broad["path"], "category": broad["category"], "source": broad["source"]},
                        "specific": {
                            "path": specific["path"],
                            "category": specific["category"],
                            "source": specific["source"],
                        },
                        "resolution": "most_specific_path" if specific.get("explicit") else "review_required",
                    }
                )
    boundary_categories = {"third_party", "historical", "generated_ephemeral", "auxiliary"}
    for exception in exceptions:
        for claim in claims:
            if claim["category"] in boundary_categories and path_is_within(exception, claim["path"]):
                diagnostics.append(
                    {
                        "kind": "boundary_covers_gitignore_exception",
                        "boundary": {"path": claim["path"], "category": claim["category"], "source": claim["source"]},
                        "exception": exception,
                        "resolution": "review_required",
                    }
                )
    unique = {json.dumps(item, ensure_ascii=False, sort_keys=True): item for item in diagnostics}
    return [unique[key] for key in sorted(unique)]


def path_classification_context(
        component_root: Path,
        profile: dict[str, Any] | None,
        component_key: str | None,
) -> dict[str, Any]:
    """汇总高权威路径策略与低权威边界，输出可机读漂移诊断。"""

    claims = profile_path_claims(profile) + context_path_claims(component_root, component_key)
    exceptions = gitignore_exceptions(component_root)
    return {
        "precedence": "most_specific_path_then_profile_authority",
        "claims": claims,
        "gitignore_exceptions": exceptions,
        "diagnostics": classification_diagnostics(claims, exceptions),
    }


def resolve_context_reference(
        reference: Any,
        workspace_root: Path | None,
        component_roots: dict[str, Path],
) -> Path | None:
    """将 Context 可移植引用解析到当前 Active 物理路径。"""

    if not isinstance(reference, dict) or not isinstance(reference.get("path"), str):
        return None
    relative_path = normalize_relative_path(reference["path"])
    if relative_path is None:
        return None
    if reference.get("scope") == "workspace" and workspace_root is not None:
        return workspace_root / relative_path
    if reference.get("scope") == "component":
        component_root = component_roots.get(reference.get("component"))
        return component_root / relative_path if component_root is not None else None
    return None


def context_freshness(
        context_path: Path,
        expected_profile: str | None,
        expected_active: str | None,
        workspace_root: Path | None,
        component_roots: dict[str, Path],
) -> dict[str, Any]:
    """比较拓扑与证据指纹；结构合法性仍交给 Context 验证器。"""

    if not context_path.is_file():
        return {"fingerprint_state": "missing", "structural_validation_required": True}
    context, error = read_json(context_path)
    if error or context is None or context.get("schema") not in {"ai-project-context/v3", "ai-project-context/v4"}:
        return {
            "fingerprint_state": "invalid_schema",
            "error": error,
            "structural_validation_required": True,
        }
    refresh = context.get("refresh")
    if not isinstance(refresh, dict):
        return {"fingerprint_state": "needs_deep_refresh", "structural_validation_required": True}
    mismatches: list[str] = []
    if expected_profile and refresh.get("profile_fingerprint") != expected_profile:
        mismatches.append("profile")
    if expected_active and refresh.get("active_fingerprint") != expected_active:
        mismatches.append("active")
    if mismatches:
        state = "stale_profile" if "profile" in mismatches else "stale_active"
        return {
            "fingerprint_state": state,
            "topology_mismatches": mismatches,
            "structural_validation_required": True,
        }

    changed_evidence: list[str] = []
    stale_semantic_nodes: list[str] = []
    if context["schema"] == "ai-project-context/v3":
        for anchor in refresh.get("anchor_files", []):
            if not isinstance(anchor, dict):
                continue
            candidate = resolve_context_reference(anchor.get("reference"), workspace_root, component_roots)
            try:
                current = sha256_fingerprint(candidate) if candidate is not None and candidate.is_file() else None
            except OSError:
                current = None
            if current != anchor.get("sha256"):
                changed_evidence.append(str(anchor.get("reference")))
        state = "stale_anchor" if changed_evidence else "current"
    else:
        catalog = context.get("reference_catalog")
        catalog = catalog if isinstance(catalog, dict) else {}
        for record in refresh.get("semantic_fingerprints", []):
            if not isinstance(record, dict):
                continue
            node_stale = False
            for evidence in record.get("evidence", []):
                if not isinstance(evidence, dict):
                    continue
                reference_id = evidence.get("ref")
                candidate = resolve_context_reference(catalog.get(reference_id), workspace_root, component_roots)
                try:
                    current = sha256_fingerprint(candidate) if candidate is not None and candidate.is_file() else None
                except OSError:
                    current = None
                if current != evidence.get("sha256"):
                    changed_evidence.append(str(reference_id))
                    node_stale = True
            node_id = record.get("semantic_node")
            if node_stale and isinstance(node_id, str):
                stale_semantic_nodes.append(node_id)
        state = "partially_stale" if stale_semantic_nodes else "current"
    return {
        "fingerprint_state": state,
        "stale_semantic_nodes": sorted(set(stale_semantic_nodes)),
        "changed_evidence": sorted(set(changed_evidence)),
        "structural_validation_required": True,
    }


def context_anchor_candidates(component: dict[str, Any]) -> list[dict[str, str]]:
    """从显式入口点生成少量 AI 上下文候选锚点，不扫描完整源码树。"""

    profile = component.get("profile")
    if not isinstance(profile, dict):
        return []
    root_value = component.get("resolved_root")
    component_key = component.get("key")
    if not isinstance(component_key, str) and isinstance(profile.get("component"), str):
        component_key = profile["component"]
    if not isinstance(root_value, str) or not isinstance(component_key, str):
        return []
    root = Path(root_value)
    anchors: list[dict[str, str]] = []
    seen_paths: set[str] = set()
    for entrypoint in profile.get("entrypoints", []):
        path_value = entrypoint.get("path") if isinstance(entrypoint, dict) else None
        if not isinstance(path_value, str) or not path_value or Path(path_value).is_absolute():
            continue
        candidate = root / path_value
        if path_value in seen_paths or not candidate.is_file():
            continue
        try:
            fingerprint = sha256_fingerprint(candidate)
        except OSError:
            continue
        seen_paths.add(path_value)
        anchors.append({"component": component_key, "path": path_value, "sha256": fingerprint})
    return anchors


def component_context_inputs(component: dict[str, Any]) -> dict[str, Any]:
    """提供独立组件 AI_CONTEXT 的位置、Profile 指纹与入口锚点。"""

    root_value = component.get("resolved_root")
    profile = component.get("profile")
    profile_fingerprint = profile.get("sha256") if isinstance(profile, dict) else None
    root = Path(root_value) if isinstance(root_value, str) else None
    component_key = component.get("key")
    if not isinstance(component_key, str) and isinstance(profile, dict):
        component_key = profile.get("component")
    context_path = root / "docs" / "ai-guide" / "AI_CONTEXT.json" if root else None
    active_record = (
        {
            "component": component_key,
            "target_name": root.name,
            "profile_sha256": profile_fingerprint,
        }
        if isinstance(component_key, str) and root is not None and isinstance(profile_fingerprint, str)
        else None
    )
    inputs = {
        "expected_path": str(context_path) if context_path else None,
        "exists": context_path.is_file() if context_path else False,
        "profile_fingerprint": f"sha256:{profile_fingerprint}" if isinstance(profile_fingerprint, str) else None,
        "active_fingerprint": stable_fingerprint(active_record) if active_record else None,
        "recommended_anchor_files": context_anchor_candidates(component),
    }
    component_roots = {component_key: root} if isinstance(component_key, str) and root is not None else {}
    if context_path is not None:
        inputs["freshness"] = context_freshness(
            context_path,
            inputs["profile_fingerprint"],
            inputs["active_fingerprint"],
            None,
            component_roots,
        )
    return inputs


def workspace_context_inputs(
        workspace_root: Path,
        active_directory_name: str,
        profile_fingerprint: str,
        components: list[dict[str, Any]],
) -> dict[str, Any]:
    """生成可跨本机路径复现的工作台 Profile/Active 上下文指纹。"""

    active_components: list[dict[str, Any]] = []
    recommended_anchors: list[dict[str, str]] = []
    for component in components:
        profile = component.get("profile")
        resolved_root = component.get("resolved_root")
        key = component.get("key")
        if not isinstance(key, str) or not isinstance(resolved_root, str):
            continue
        active_components.append(
            {
                "key": key,
                "target_name": Path(resolved_root).name,
                "profile_sha256": profile.get("sha256") if isinstance(profile, dict) else None,
            }
        )
        recommended_anchors.extend(context_anchor_candidates(component))
    active_record = {
        "active_directory_name": active_directory_name,
        "components": sorted(active_components, key=lambda item: item["key"]),
    }
    context_path = workspace_root / "docs" / "ai-guide" / "AI_CONTEXT.json"
    inputs = {
        "expected_path": str(context_path),
        "exists": context_path.is_file(),
        "profile_fingerprint": f"sha256:{profile_fingerprint}",
        "active_fingerprint": stable_fingerprint(active_record),
        "recommended_anchor_files": recommended_anchors,
    }
    component_roots = {
        component["key"]: Path(component["resolved_root"])
        for component in components
        if isinstance(component.get("key"), str) and isinstance(component.get("resolved_root"), str)
    }
    inputs["freshness"] = context_freshness(
        context_path,
        inputs["profile_fingerprint"],
        inputs["active_fingerprint"],
        workspace_root,
        component_roots,
    )
    return inputs


def hierarchical_context_tree(
        workspace_inputs: dict[str, Any],
        components: list[dict[str, Any]],
) -> dict[str, Any]:
    """输出工作台根与全部 Active 子项目 Context 的只读覆盖清单。"""

    children = []
    for component in components:
        key = component.get("key")
        inputs = component.get("ai_context_inputs")
        if not isinstance(key, str) or not isinstance(inputs, dict):
            continue
        children.append(
            {
                "key": key,
                "expected_path": inputs.get("expected_path"),
                "exists": inputs.get("exists", False),
                "profile_fingerprint": inputs.get("profile_fingerprint"),
                "active_fingerprint": inputs.get("active_fingerprint"),
                "freshness": inputs.get("freshness"),
            }
        )
    return {
        "root": {
            "expected_path": workspace_inputs.get("expected_path"),
            "exists": workspace_inputs.get("exists", False),
            "profile_fingerprint": workspace_inputs.get("profile_fingerprint"),
            "active_fingerprint": workspace_inputs.get("active_fingerprint"),
            "freshness": workspace_inputs.get("freshness"),
        },
        "children": children,
    }


def read_xml_root(path: Path) -> element_tree.Element | None:
    """读取小型 XML 配置；损坏或缺失的 IDE 文件视为不可验证。"""

    try:
        return element_tree.parse(path).getroot()
    except (OSError, element_tree.ParseError):
        return None


def sdk_name_from_iml(path: Path) -> str | None:
    """读取模块 IML 中绑定的 PyCharm Python SDK 名称。"""

    root = read_xml_root(path)
    if root is None:
        return None
    for entry in root.findall(".//orderEntry"):
        if entry.get("type") == "jdk":
            return entry.get("jdkName")
    return None


def pycharm_sdk_registry() -> dict[str, list[dict[str, str]]]:
    """读取当前用户可见的 PyCharm SDK 注册表，仅用于本机解释器核验。"""

    config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    jetbrains_root = config_home / "JetBrains"
    registry: dict[str, list[dict[str, str]]] = {}
    if not jetbrains_root.is_dir():
        return registry
    for table_path in sorted(jetbrains_root.glob("PyCharm*/options/jdk.table.xml")):
        root = read_xml_root(table_path)
        if root is None:
            continue
        for sdk in root.findall(".//jdk"):
            name_node = sdk.find("name")
            home_node = sdk.find("homePath")
            if name_node is None or home_node is None:
                continue
            name = name_node.get("value")
            home_path = home_node.get("value")
            if not name or not home_path:
                continue
            record = {"config": str(table_path), "python_bin": home_path}
            known = registry.setdefault(name, [])
            if record not in known:
                known.append(record)
    return registry


def expand_project_dir(value: str, workspace_root: Path) -> str:
    """展开 PyCharm 配置中可安全解析的项目目录占位符。"""

    expanded = value.replace("$PROJECT_DIR$", str(workspace_root))
    path = Path(expanded).expanduser()
    absolute_path = path if path.is_absolute() else workspace_root / path
    return os.path.normpath(str(absolute_path))


def expected_sdk_name(template: dict[str, Any], workspace_root: Path) -> str | None:
    """从环境模板推导当前约定的 PyCharm SDK 显示名。"""

    explicit_name = template.get("pycharm_sdk_name")
    if isinstance(explicit_name, str) and explicit_name:
        return explicit_name
    python_bin = template.get("python_bin")
    if isinstance(python_bin, str) and python_bin:
        return Path(expand_project_dir(python_bin, workspace_root)).parent.parent.name
    root = template.get("root")
    return Path(expand_project_dir(root, workspace_root)).name if isinstance(root, str) and root else None


def pycharm_project_sdk(workspace_root: Path) -> dict[str, Any]:
    """读取项目级 SDK 与 Black 格式化器 SDK，不将二者混为运行解释器。"""

    root = read_xml_root(workspace_root / ".idea" / "misc.xml")
    if root is None:
        return {"status": "missing", "sdk_name": None, "sdk_type": None, "black_sdk_name": None}
    project_manager = next(
        (item for item in root.findall(".//component") if item.get("name") == "ProjectRootManager"),
        None,
    )
    black_component = next(
        (item for item in root.findall(".//component") if item.get("name") == "Black"),
        None,
    )
    black_option = black_component.find("option") if black_component is not None else None
    return {
        "status": "found" if project_manager is not None else "missing",
        "sdk_name": project_manager.get("project-jdk-name") if project_manager is not None else None,
        "sdk_type": project_manager.get("project-jdk-type") if project_manager is not None else None,
        "black_sdk_name": black_option.get("value") if black_option is not None else None,
    }


def run_configuration_context(workspace_root: Path, module_sdks: dict[str, str | None]) -> list[dict[str, Any]]:
    """提取共享 Run/Debug 配置的解释器选择与显式运行环境变量。"""

    directory = workspace_root / ".idea" / "runConfigurations"
    records: list[dict[str, Any]] = []
    if not directory.is_dir():
        return records
    for path in sorted(directory.glob("*.xml")):
        root = read_xml_root(path)
        configuration = root.find("configuration") if root is not None else None
        if configuration is None:
            continue
        module = configuration.find("module")
        options = {
            option.get("name"): option.get("value")
            for option in configuration.findall("option")
            if option.get("name") and option.get("value")
        }
        environment = {
            variable.get("name"): variable.get("value")
            for variable in configuration.findall(".//env")
            if variable.get("name") in {"ENV_ROOT", "PYTHON_BIN"}
        }
        module_name = module.get("name") if module is not None else None
        explicit_sdk = options.get("SDK_HOME") or None
        uses_module_sdk = options.get("IS_MODULE_SDK") == "true"
        records.append(
            {
                "file": path.name,
                "name": configuration.get("name"),
                "type": configuration.get("type"),
                "module": module_name,
                "explicit_sdk_name": explicit_sdk,
                "module_sdk_name": module_sdks.get(module_name) if uses_module_sdk else None,
                "shell_interpreter": options.get("INTERPRETER_PATH"),
                "runtime_environment": environment,
            }
        )
    return records


def sdk_alignment(
        expected_sdk: str | None,
        expected_python: str | None,
        configured_sdk: str | None,
        registry: dict[str, list[dict[str, str]]],
) -> str:
    """判断 Profile、模块 SDK 与本机注册解释器是否可验证地一致。"""

    if expected_sdk is None or expected_python is None:
        return "shared"
    if configured_sdk is None:
        return "missing"
    if configured_sdk != expected_sdk:
        return "mismatch"
    registered = registry.get(configured_sdk, [])
    if not registered:
        return "unverified"
    expected_path = str(Path(expected_python).expanduser().resolve())
    registered_paths = {str(Path(item["python_bin"]).expanduser().resolve()) for item in registered}
    return "aligned" if expected_path in registered_paths else "mismatch"


def pycharm_alignment_context(
        workspace_root: Path,
        workspace_profile: dict[str, Any],
        components: list[dict[str, Any]],
) -> dict[str, Any]:
    """对比 Profile 运行契约与项目、模块、Run Configurations 的解释器设置。"""

    templates = workspace_profile.get("environment_templates", {})
    templates = templates if isinstance(templates, dict) else {}
    default_key = workspace_profile.get("default_environment_key")
    default_key = default_key if isinstance(default_key, str) and default_key else None
    registry = pycharm_sdk_registry()
    project_sdk = pycharm_project_sdk(workspace_root)
    module_records: list[dict[str, Any]] = []
    module_sdks: dict[str, str | None] = {}
    for component in components:
        key = component.get("key")
        profile = component.get("profile") or {}
        environment_key = profile.get("environment_key")
        template = templates.get(environment_key, {}) if isinstance(environment_key, str) else {}
        template = template if isinstance(template, dict) else {}
        module_name = component.get("module_name")
        module_file_name = component.get("module_config_name")
        configured_sdk = sdk_name_from_iml(workspace_root / ".idea" / module_file_name) if module_file_name else None
        if isinstance(module_name, str):
            module_sdks[module_name] = configured_sdk
        python_bin = template.get("python_bin")
        expected_python = expand_project_dir(python_bin, workspace_root) if isinstance(python_bin, str) else None
        expected_name = expected_sdk_name(template, workspace_root)
        module_records.append(
            {
                "key": key,
                "environment_key": environment_key,
                "expected_sdk_name": expected_name,
                "expected_python_bin": expected_python,
                "configured_sdk_name": configured_sdk,
                "status": sdk_alignment(expected_name, expected_python, configured_sdk, registry),
            }
        )

    default_template = templates.get(default_key, {}) if default_key else {}
    default_template = default_template if isinstance(default_template, dict) else {}
    default_python_value = default_template.get("python_bin")
    default_python = (
        expand_project_dir(default_python_value, workspace_root)
        if isinstance(default_python_value, str)
        else None
    )
    default_sdk = expected_sdk_name(default_template, workspace_root)
    default_status = "missing" if default_key is None else sdk_alignment(
        default_sdk,
        default_python,
        project_sdk.get("sdk_name"),
        registry,
    )
    return {
        "profile_default": {
            "environment_key": default_key,
            "expected_sdk_name": default_sdk,
            "expected_python_bin": default_python,
            "status": default_status,
        },
        "pycharm_project_sdk": project_sdk,
        "modules": module_records,
        "run_configurations": run_configuration_context(workspace_root, module_sdks),
        "registered_sdk_names": sorted(registry),
    }


def inspect_component(component_root: Path, component_key: str | None = None) -> dict[str, Any]:
    """组合一个组件的物理路径、Profile、Git 和第三方证据。"""

    resolved_root = component_root.resolve()
    profile_path = component_profile_path(resolved_root)
    component = {
        "requested_root": str(component_root),
        "resolved_root": str(resolved_root),
        "exists": resolved_root.is_dir(),
        "profile": profile_summary(profile_path) if profile_path else None,
        "git": git_context(resolved_root) if resolved_root.is_dir() else None,
        "third_party": third_party_context(resolved_root) if resolved_root.is_dir() else None,
    }
    if component_key is not None:
        component["key"] = component_key
    component["ai_context_inputs"] = component_context_inputs(component)
    component["path_classification"] = path_classification_context(
        resolved_root,
        component.get("profile"),
        component_key,
    )
    return component


def workspace_context(workspace_root: Path, workspace_profile_path: Path) -> dict[str, Any]:
    """解析工作台声明的组件及其实际 Active 目标。"""

    content, error = read_json(workspace_profile_path)
    result: dict[str, Any] = {
        "root": str(workspace_root),
        "profile_path": str(workspace_profile_path),
        "profile_sha256": sha256sum(workspace_profile_path),
        "git": git_context(workspace_root),
    }
    if error or content is None:
        result["error"] = error
        return result
    active_directory_name = content.get("active_directory_name")
    if not isinstance(active_directory_name, str):
        result["error"] = "workspace profile 缺少 active_directory_name"
        return result
    active_root = workspace_root.parent / active_directory_name
    components: list[dict[str, Any]] = []
    for item in content.get("components", []):
        if not isinstance(item, dict) or not isinstance(item.get("key"), str):
            continue
        key = item["key"]
        active_path = active_root / key
        component = inspect_component(active_path, key)
        component["is_symlink"] = active_path.is_symlink()
        component["module_name"] = item.get("module_name")
        component["module_config_name"] = item.get("module_config_name")
        component["ai_context_inputs"] = component_context_inputs(component)
        components.append(component)
    state_path = workspace_root / "active_profile.json"
    workspace_inputs = workspace_context_inputs(
        workspace_root,
        active_directory_name,
        result["profile_sha256"],
        components,
    )
    result.update(
        {
            "active_root": str(active_root),
            "active_state_path": str(state_path) if state_path.is_file() else None,
            "components": components,
            "pycharm_interpreter_alignment": pycharm_alignment_context(workspace_root, content, components),
            "ai_context_inputs": workspace_inputs,
            "ai_context_tree": hierarchical_context_tree(workspace_inputs, components),
        }
    )
    return result


def collect_context(target_path: Path) -> dict[str, Any]:
    """收集工作台或单组件上下文；无 Profile 的普通仓库也可正常输出。"""

    requested_target = target_path.expanduser().absolute()
    resolved_target = requested_target.resolve()
    workspace_profile_path = find_profile(requested_target, "workspace.json")
    component_profile = find_profile(requested_target, "component.json")
    if workspace_profile_path is None and component_profile is not None:
        workspace_profile_path = active_workspace_profile(component_profile.parent.parent)
    result: dict[str, Any] = {
        "schema_version": 4,
        "requested_path": str(target_path),
        "resolved_path": str(resolved_target),
        "workspace": None,
        "component": None,
        "git": git_context(resolved_target) if resolved_target.exists() else None,
    }
    if workspace_profile_path:
        result["workspace"] = workspace_context(workspace_profile_path.parent.parent, workspace_profile_path)
    if component_profile:
        component_summary = profile_summary(component_profile)
        component_key = component_summary.get("component")
        result["component"] = inspect_component(
            component_profile.parent.parent,
            component_key if isinstance(component_key, str) else None,
        )
    elif workspace_profile_path is None and resolved_target.is_dir():
        result["component"] = inspect_component(resolved_target, resolved_target.name)
    return result


def parse_args() -> argparse.Namespace:
    """解析只读上下文采集参数。"""

    parser = argparse.ArgumentParser(description="只读收集代码库的 Profile 与 Git 理解上下文。")
    parser.add_argument("--path", required=True, help="工作台、组件或普通仓库路径")
    return parser.parse_args()


def main() -> int:
    """输出 UTF-8 JSON，不修改项目或 Git 状态。"""

    args = parse_args()
    print(json.dumps(collect_context(Path(args.path)), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
