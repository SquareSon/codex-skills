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
        }
    )
    return summary


def third_party_context(component_root: Path) -> dict[str, Any]:
    """记录锁定清单和补丁目录的存在性，不展开扫描第三方源码。"""

    lock_root = component_root / "third_party"
    patch_root = component_root / "patches" / "third_party"
    lock_files = sorted(path.name for path in lock_root.glob("lock-*.json")) if lock_root.is_dir() else []
    patch_snapshots = sorted(path.name for path in patch_root.iterdir() if path.is_dir()) if patch_root.is_dir() else []
    return {"lock_files": lock_files, "patch_snapshots": patch_snapshots}


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


def inspect_component(component_root: Path) -> dict[str, Any]:
    """组合一个组件的物理路径、Profile、Git 和第三方证据。"""

    resolved_root = component_root.resolve()
    profile_path = component_profile_path(resolved_root)
    return {
        "requested_root": str(component_root),
        "resolved_root": str(resolved_root),
        "exists": resolved_root.is_dir(),
        "profile": profile_summary(profile_path) if profile_path else None,
        "git": git_context(resolved_root) if resolved_root.is_dir() else None,
        "third_party": third_party_context(resolved_root) if resolved_root.is_dir() else None,
    }


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
        component = inspect_component(active_path)
        component["key"] = key
        component["is_symlink"] = active_path.is_symlink()
        component["module_name"] = item.get("module_name")
        component["module_config_name"] = item.get("module_config_name")
        components.append(component)
    state_path = workspace_root / "active_profile.json"
    result.update(
        {
            "active_root": str(active_root),
            "active_state_path": str(state_path) if state_path.is_file() else None,
            "components": components,
            "pycharm_interpreter_alignment": pycharm_alignment_context(workspace_root, content, components),
        }
    )
    return result


def collect_context(target_path: Path) -> dict[str, Any]:
    """收集工作台或单组件上下文；无 Profile 的普通仓库也可正常输出。"""

    resolved_target = target_path.expanduser().resolve()
    workspace_profile_path = find_profile(resolved_target, "workspace.json")
    component_profile = find_profile(resolved_target, "component.json")
    result: dict[str, Any] = {
        "schema_version": 2,
        "requested_path": str(target_path),
        "resolved_path": str(resolved_target),
        "workspace": None,
        "component": None,
        "git": git_context(resolved_target) if resolved_target.exists() else None,
    }
    if workspace_profile_path:
        result["workspace"] = workspace_context(workspace_profile_path.parent.parent, workspace_profile_path)
    if component_profile:
        result["component"] = inspect_component(component_profile.parent.parent)
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
