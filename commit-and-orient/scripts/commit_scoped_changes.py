#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""盘点、封存计划或安全执行显式范围内的本地 Git 提交。"""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence


PLAN_SCHEMA = "commit-and-orient-plan/v2"
PLAN_ENVELOPE_SCHEMA = "commit-and-orient-plan-envelope/v1"
SCOPED_CONFIRMATION = "I_CONFIRM_SCOPED_COMMIT"
IDENTITY_CONFIRMATION = "I_CONFIRM_REPOSITORY_LOCAL_IDENTITY"
DEFAULT_GIT_TIMEOUT_SECONDS = 120


# 仅用于只读候选聚类；任何主题都不是提交授权，也不替代后续人工审阅。
TOPIC_PATTERNS: dict[str, tuple[str, ...]] = {
    "repository-hygiene": (
        "gitignore", "planning", "artifact", "artifacts", "pycharm", "idea", "workspace",
    ),
    "precision": (
        "amp", "fp16", "bf16", "autocast", "gradscaler", "precision",
    ),
    "spatial": (
        "footprint", "mip", "ray", "convex", "frustum", "gaussian", "spatial", "camera",
    ),
    "evaluation": (
        "metric", "ssim", "lpips", "pyiqa", "intensity", "evaluation", "eval", "visualization",
    ),
    "cache-validation": (
        "cache", "prefetch", "stager", "snapshot", "authority", "validation", "validated",
    ),
    "observability": (
        "wandb", "watch", "logging", "preview", "monitor",
    ),
    "semantic": (
        "semantic", "voxel", "needle", "ontology", "label", "multilabel",
    ),
    "experiment": (
        "ablation", "chapter2", "chapter_2", "registry", "preflight", "benchmark", "nvs",
    ),
}

TOPIC_MESSAGES: dict[str, str] = {
    "repository-hygiene": "chore(workspace): exclude local generated artifacts",
    "precision": "feat(precision): align field AMP runtime",
    "spatial": "feat(spatial): refine physical ray integration",
    "evaluation": "feat(evaluation): harden metric runtime",
    "cache-validation": "feat(runtime): validate and prefetch training data",
    "observability": "feat(observability): unify experiment monitoring",
    "semantic": "feat(semantic): strengthen semantic field runtime",
    "experiment": "feat(experiment): extend reproducible experiment entrypoints",
}


class CommitScopeError(RuntimeError):
    """表示提交范围、Git 状态或用户确认不满足安全要求。"""


class PlanExecutionError(CommitScopeError):
    """表示计划执行中途失败，并保留已经成功的提交。"""

    def __init__(self, message: str, completed: Sequence[Mapping[str, Any]]) -> None:
        super().__init__(message)
        self.completed = [dict(item) for item in completed]


#region Git 基础证据
def run_git(
    repository: Path,
    *arguments: str,
    environment: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """在指定仓库执行 Git 命令，并始终捕获 UTF-8 文本输出。"""

    process_environment = os.environ.copy()
    if environment:
        process_environment.update(environment)
    return subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=DEFAULT_GIT_TIMEOUT_SECONDS,
        env=process_environment,
    )


def git_output(
    repository: Path,
    *arguments: str,
    environment: Mapping[str, str] | None = None,
) -> str:
    """返回成功 Git 命令的输出，否则抛出带上下文的错误。"""

    result = run_git(repository, *arguments, environment=environment)
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "未知 Git 错误"
        raise CommitScopeError(f"Git 命令失败：git {' '.join(arguments)}：{detail}")
    return result.stdout.strip()


def repository_root(path_text: str) -> Path:
    """解析真实 Git 根目录，避免误把父目录或链接目录当作提交范围。"""

    requested = Path(path_text).expanduser().resolve()
    if not requested.exists():
        raise CommitScopeError(f"仓库路径不存在：{requested}")
    return Path(git_output(requested, "rev-parse", "--show-toplevel")).resolve()


def head_state(repository: Path) -> dict[str, Any]:
    """兼容已有历史和尚无首个提交的仓库。"""

    verify = run_git(repository, "rev-parse", "--verify", "HEAD")
    branch_result = run_git(repository, "symbolic-ref", "--quiet", "--short", "HEAD")
    branch = (
        branch_result.stdout.strip()
        if branch_result.returncode == 0
        else git_output(repository, "branch", "--show-current")
    )
    if verify.returncode == 0:
        head = verify.stdout.strip()
        return {
            "head_state": "committed",
            "has_commits": True,
            "head": head,
            "branch": branch,
            "describe": git_output(repository, "describe", "--tags", "--always", "--dirty"),
        }
    return {
        "head_state": "unborn",
        "has_commits": False,
        "head": None,
        "branch": branch,
        "describe": f"unborn:{branch or 'detached'}",
    }


def status_lines(repository: Path) -> list[str]:
    """读取 porcelain 状态，保留 Git 原始双字符状态以便审查。"""

    output = git_output(repository, "status", "--porcelain=v1", "--untracked-files=all")
    return output.splitlines() if output else []


def staged_files(repository: Path, environment: Mapping[str, str] | None = None) -> list[str]:
    """读取暂存文件，并关闭 rename 折叠以保留删除端和新增端。"""

    output = git_output(
        repository,
        "diff",
        "--cached",
        "--name-only",
        "--no-renames",
        "-z",
        environment=environment,
    )
    return sorted(item for item in output.split("\0") if item)


def working_changes(repository: Path) -> list[str]:
    """返回全部非忽略的跟踪变更和未跟踪文件。"""

    tracked = git_output(repository, "diff", "--name-only", "--no-renames", "-z")
    untracked = git_output(repository, "ls-files", "--others", "--exclude-standard", "-z")
    return sorted({item for item in f"{tracked}\0{untracked}".split("\0") if item})


def git_operation_paths(repository: Path) -> list[Path]:
    """识别会使提交语义不明确的 Git 进行中操作。"""

    markers = (
        "MERGE_HEAD",
        "CHERRY_PICK_HEAD",
        "REVERT_HEAD",
        "rebase-merge",
        "rebase-apply",
        "BISECT_LOG",
    )
    active: list[Path] = []
    for marker in markers:
        marker_path = Path(git_output(repository, "rev-parse", "--git-path", marker))
        if not marker_path.is_absolute():
            marker_path = repository / marker_path
        if marker_path.exists():
            active.append(marker_path)
    return active


def config_value_with_origin(repository: Path, key: str) -> tuple[str | None, str | None]:
    """返回 Git 配置的有效值及来源。"""

    result = run_git(repository, "config", "--show-origin", "--get", key)
    if result.returncode != 0 or not result.stdout.strip():
        return None, None
    origin, _, value = result.stdout.strip().partition("\t")
    if not value:
        fields = result.stdout.strip().split(maxsplit=1)
        return (fields[1] if len(fields) == 2 else None), (fields[0] if fields else None)
    return value, origin


def identity_info(repository: Path) -> dict[str, Any]:
    """收集当前仓库将使用的有效 Git 身份，不主动修改配置。"""

    name, name_origin = config_value_with_origin(repository, "user.name")
    email, email_origin = config_value_with_origin(repository, "user.email")
    author = run_git(repository, "var", "GIT_AUTHOR_IDENT")
    return {
        "available": bool(name and email and author.returncode == 0),
        "name": name,
        "email": email,
        "name_origin": name_origin,
        "email_origin": email_origin,
    }


def inventory(repository: Path) -> dict[str, Any]:
    """返回提交计划所需的只读仓库证据。"""

    return {
        "repository": str(repository),
        **head_state(repository),
        "identity": identity_info(repository),
        "status": status_lines(repository),
        "working_changes": working_changes(repository),
        "staged_files": staged_files(repository),
        "git_operations": [str(path) for path in git_operation_paths(repository)],
        "remote_names": git_output(repository, "remote").splitlines(),
    }


def change_category(path_text: str) -> str:
    """以路径判断变更角色；此分类不决定科学或提交相关性。"""

    lowered = path_text.lower()
    name = Path(path_text).name.lower()
    if lowered.startswith(("tests/", "test/")) or name.startswith("test_"):
        return "test"
    if lowered.startswith(("docs/", "doc/")) or name.endswith((".md", ".rst")):
        return "documentation"
    if name.startswith(("run_", "benchmark_", "evaluate_", "preflight_")) or lowered.startswith("scripts/"):
        return "entrypoint_or_experiment"
    if lowered.startswith(("profile/", "docs/ai-guide/")):
        return "profile_or_context"
    if name in {".gitignore", "pyproject.toml", "setup.cfg"} or name.endswith((".json", ".toml", ".yaml", ".yml", ".tsv")):
        return "configuration"
    return "implementation"


def changed_text_for_analysis(repository: Path, path_text: str, *, maximum_bytes: int = 262_144) -> str:
    """读取已修改 hunks；新增文件使用有限内容，只返回给本地主题分析。"""

    diff = run_git(repository, "diff", "--no-ext-diff", "--unified=0", "--", path_text)
    if diff.returncode == 0 and diff.stdout.strip():
        return diff.stdout[:maximum_bytes]
    candidate = repository / path_text
    if candidate.is_file() and not candidate.is_symlink():
        try:
            return candidate.read_text(encoding="utf-8", errors="replace")[:maximum_bytes]
        except OSError:
            return ""
    return ""


def lexical_tokens(value: str) -> list[str]:
    """分割路径、snake_case 与 CamelCase，避免把 catalog 误判为 log。"""

    expanded = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", value)
    return re.findall(r"[a-z0-9]+", expanded.lower())


def topic_scores(repository: Path, path_text: str) -> dict[str, int]:
    """以路径和改动文本给出可解释的轻量主题分数。"""

    path_tokens = lexical_tokens(path_text)
    text_tokens = lexical_tokens(changed_text_for_analysis(repository, path_text))
    scores: dict[str, int] = {}
    for topic, terms in TOPIC_PATTERNS.items():
        path_hits = sum(path_tokens.count(term) for term in terms)
        text_hits = sum(text_tokens.count(term) for term in terms)
        score = path_hits * 5 + min(text_hits, 24)
        if score:
            scores[topic] = score
    return scores


def classify_change_topics(repository: Path, path_text: str) -> dict[str, Any]:
    """将单文件标为主主题、桥接文件或待人工归类项。"""

    scores = topic_scores(repository, path_text)
    category = change_category(path_text)
    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    if not ranked:
        return {
            "path": path_text,
            "category": category,
            "scores": scores,
            "primary_topic": None,
            "bridge_topics": [],
            "reason": "未从路径或已修改文本中取得足够主题信号",
        }
    primary, primary_score = ranked[0]
    bridge_topics = [
        topic
        for topic, score in ranked[1:]
        if score >= 3 and score * 10 >= primary_score * 7
    ]
    return {
        "path": path_text,
        "category": category,
        "scores": dict(ranked),
        "primary_topic": primary,
        "bridge_topics": bridge_topics,
        "reason": (
            f"主主题={primary}; 同强度主题={','.join(bridge_topics)}"
            if bridge_topics
            else f"主主题={primary}"
        ),
    }


def proposal_blockers(repository: Path) -> list[dict[str, Any]]:
    """报告会阻止候选进入封存/执行的状态，但保持 propose-plan 只读。"""

    blockers: list[dict[str, Any]] = []
    staged = staged_files(repository)
    if staged:
        blockers.append({"kind": "preexisting_staged", "paths": staged})
    operations = [str(path) for path in git_operation_paths(repository)]
    if operations:
        blockers.append({"kind": "git_operation", "paths": operations})
    state = head_state(repository)
    if not state["has_commits"]:
        blockers.append({"kind": "unborn_repository", "paths": []})
    if not identity_info(repository)["available"]:
        blockers.append({"kind": "missing_identity", "paths": []})
    return blockers


def propose_commit_groups(repository: Path) -> dict[str, Any]:
    """只读生成文件级候选提交；桥接文件必须人工分配或合并。"""

    changes = working_changes(repository)
    classified = [classify_change_topics(repository, path) for path in changes]
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    bridge_paths: list[dict[str, Any]] = []
    unclassified_paths: list[dict[str, Any]] = []
    for item in classified:
        if item["primary_topic"] is None:
            unclassified_paths.append(item)
        elif item["bridge_topics"]:
            bridge_paths.append(item)
        else:
            groups[str(item["primary_topic"])].append(item)

    candidates: list[dict[str, Any]] = []
    for topic in sorted(groups):
        entries = groups[topic]
        paths = sorted(str(item["path"]) for item in entries)
        categories = sorted({str(item["category"]) for item in entries})
        candidates.append(
            {
                "id": topic,
                "recommended_message": TOPIC_MESSAGES[topic],
                "paths": paths,
                "path_count": len(paths),
                "categories": categories,
                "confidence": "high" if len(categories) >= 2 else "medium",
                "executable_without_review": False,
                "reason": "仅包含单主题文件；仍须确认其与桥接实现的原子性。",
            }
        )
    blockers = proposal_blockers(repository)
    return {
        "repository": str(repository),
        "head": head_state(repository),
        "blocking_conditions": blockers,
        "safe_to_seal": not blockers and not bridge_paths and not unclassified_paths,
        "candidates": candidates,
        "bridge_paths": bridge_paths,
        "unclassified_paths": unclassified_paths,
        "analysis_policy": {
            "granularity": "file",
            "mutates_git": False,
            "requires_human_assignment_for_bridge_paths": True,
            "hunk_splitting": "not_supported",
        },
    }
#endregion


#region 路径、快照与计划封存
def normalize_relative_path(path_text: str, *, allow_directory: bool = False) -> str:
    """验证非空、非选项且不含目录穿越的仓库相对路径。"""

    candidate = Path(path_text)
    if (
        candidate.is_absolute()
        or path_text in {"", "."}
        or path_text.startswith("-")
        or ".." in candidate.parts
    ):
        raise CommitScopeError(f"路径必须是显式仓库相对路径：{path_text!r}")
    normalized = candidate.as_posix().removeprefix("./")
    if not normalized or (not allow_directory and normalized.endswith("/")):
        raise CommitScopeError(f"路径无效：{path_text!r}")
    return normalized


def is_tracked(repository: Path, path_text: str) -> bool:
    """判断路径是否存在于 Git index，用于识别已删除文件。"""

    return run_git(repository, "ls-files", "--error-unmatch", "--", path_text).returncode == 0


def file_sha256(path: Path) -> str:
    """以固定大小分块计算文件哈希，避免大型二进制文件占满内存。"""

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def validate_requested_paths(repository: Path, requested_paths: Sequence[str]) -> list[str]:
    """验证全部路径均是仓库内的显式文件，并拒绝隐式目录范围。"""

    if not requested_paths:
        raise CommitScopeError("至少需要一个显式文件路径，禁止提交整个仓库")
    normalized: list[str] = []
    changed = set(working_changes(repository))
    for path_text in requested_paths:
        relative = normalize_relative_path(path_text)
        candidate = repository / relative
        if candidate.is_dir() and not candidate.is_symlink():
            raise CommitScopeError(f"默认不接受目录范围，请展开为显式文件：{relative}")
        if not candidate.exists() and not candidate.is_symlink() and not is_tracked(repository, relative):
            raise CommitScopeError(f"路径既不存在也不是已删除的跟踪文件：{relative}")
        if relative not in changed:
            raise CommitScopeError(f"批准路径当前没有工作树变更：{relative}")
        if relative not in normalized:
            normalized.append(relative)
    return normalized


def file_state(repository: Path, path_text: str) -> dict[str, Any]:
    """为批准文件建立可重复的内容、类型和权限快照。"""

    path = repository / path_text
    if path.is_symlink():
        target = os.readlink(path)
        return {
            "kind": "symlink",
            "sha256": hashlib.sha256(target.encode("utf-8")).hexdigest(),
            "mode": oct(path.lstat().st_mode & 0o7777),
        }
    if path.is_file():
        return {
            "kind": "file",
            "sha256": file_sha256(path),
            "mode": oct(path.stat().st_mode & 0o7777),
        }
    if is_tracked(repository, path_text):
        return {"kind": "deleted", "sha256": None, "mode": None}
    raise CommitScopeError(f"无法为路径建立快照：{path_text}")


def path_states(repository: Path, paths: Sequence[str]) -> dict[str, dict[str, Any]]:
    """返回按路径排序的文件状态快照。"""

    return {path: file_state(repository, path) for path in sorted(paths)}


def canonical_sha256(value: Any) -> str:
    """计算稳定 JSON 表示的 SHA-256。"""

    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def path_allowed(path_text: str, allowed: Sequence[str]) -> bool:
    """允许精确文件或明确声明的剩余目录前缀。"""

    return any(path_text == item or path_text.startswith(f"{item}/") for item in allowed)


def load_json(path: Path) -> dict[str, Any]:
    """读取 JSON 对象并给出明确的格式错误。"""

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CommitScopeError(f"无法读取 JSON：{path}：{exc}") from exc
    if not isinstance(value, dict):
        raise CommitScopeError(f"JSON 顶层必须是对象：{path}")
    return value


def normalize_identity_policy(value: Any) -> dict[str, Any]:
    """规范仓库身份策略，默认只接受已有有效身份。"""

    policy = dict(value or {"action": "require_existing"})
    action = policy.get("action", "require_existing")
    if action not in {"require_existing", "set_repository_local"}:
        raise CommitScopeError(f"未知 identity_policy.action：{action!r}")
    if action == "set_repository_local":
        if not str(policy.get("name", "")).strip() or not str(policy.get("email", "")).strip():
            raise CommitScopeError("设置仓库本地身份时必须同时提供 name 和 email")
    return policy


def seal_plan(draft: Mapping[str, Any]) -> dict[str, Any]:
    """将用户可读草案解析为绑定 HEAD、路径和文件内容的可批准计划。"""

    if draft.get("schema") != PLAN_SCHEMA:
        raise CommitScopeError(f"计划 schema 必须是 {PLAN_SCHEMA}")
    repository_entries = draft.get("repositories")
    commit_entries = draft.get("commits")
    if not isinstance(repository_entries, list) or not repository_entries:
        raise CommitScopeError("计划至少需要一个 repositories 条目")
    if not isinstance(commit_entries, list) or not commit_entries:
        raise CommitScopeError("计划至少需要一个 commits 条目")

    policies: dict[str, dict[str, Any]] = {}
    for raw_policy in repository_entries:
        if not isinstance(raw_policy, dict):
            raise CommitScopeError("repositories 条目必须是对象")
        repository = repository_root(str(raw_policy.get("repository", "")))
        key = str(repository)
        if key in policies:
            raise CommitScopeError(f"仓库策略重复：{repository}")
        current_head = head_state(repository)
        allow_unborn = bool(raw_policy.get("allow_unborn", False))
        if not current_head["has_commits"] and not allow_unborn:
            raise CommitScopeError(f"仓库尚无提交，计划必须显式 allow_unborn：{repository}")
        if staged_files(repository):
            raise CommitScopeError(f"仓库已有暂存文件：{repository}")
        operations = git_operation_paths(repository)
        if operations:
            raise CommitScopeError(f"仓库存在进行中的 Git 操作：{repository}")
        remaining = [
            normalize_relative_path(str(item), allow_directory=True)
            for item in raw_policy.get("approved_remaining_paths", [])
        ]
        identity_policy = normalize_identity_policy(raw_policy.get("identity_policy"))
        if identity_policy["action"] == "require_existing" and not identity_info(repository)["available"]:
            raise CommitScopeError(f"仓库缺少有效 Git 身份：{repository}")
        policies[key] = {
            "repository": key,
            "branch": current_head["branch"],
            "head_state": current_head["head_state"],
            "expected_head": current_head["head"],
            "allow_unborn": allow_unborn,
            "identity_policy": identity_policy,
            "approved_remaining_paths": remaining,
        }

    sealed_commits: list[dict[str, Any]] = []
    planned_by_repository: dict[str, set[str]] = {key: set() for key in policies}
    identifiers: set[str] = set()
    for raw_commit in commit_entries:
        if not isinstance(raw_commit, dict):
            raise CommitScopeError("commits 条目必须是对象")
        identifier = str(raw_commit.get("id", "")).strip()
        if not identifier or identifier in identifiers:
            raise CommitScopeError(f"提交 id 为空或重复：{identifier!r}")
        identifiers.add(identifier)
        repository = repository_root(str(raw_commit.get("repository", "")))
        repository_key = str(repository)
        if repository_key not in policies:
            raise CommitScopeError(f"提交缺少对应仓库策略：{repository}")
        message = str(raw_commit.get("message", "")).strip()
        if not message:
            raise CommitScopeError(f"提交说明不能为空：{identifier}")
        paths = validate_requested_paths(repository, [str(item) for item in raw_commit.get("paths", [])])
        overlap = planned_by_repository[repository_key].intersection(paths)
        if overlap:
            raise CommitScopeError(f"同一文件不能出现在同一计划的多个提交中：{sorted(overlap)}")
        planned_by_repository[repository_key].update(paths)
        diff_check = str(raw_commit.get("diff_check", "error"))
        if diff_check not in {"error", "warn"}:
            raise CommitScopeError(f"diff_check 仅支持 error/warn：{identifier}")
        preflight = preflight_with_temporary_index(repository, paths, diff_check)
        sealed_commits.append(
            {
                "id": identifier,
                "repository": repository_key,
                "message": message,
                "paths": paths,
                "path_states": path_states(repository, paths),
                "diff_check": diff_check,
                "preflight": preflight,
                "validation": list(raw_commit.get("validation", [])),
                "context_impact": str(raw_commit.get("context_impact", "review")),
            }
        )

    for repository_key, policy in policies.items():
        changes = working_changes(Path(repository_key))
        allowed = sorted(planned_by_repository[repository_key])
        unexpected = [
            path
            for path in changes
            if path not in planned_by_repository[repository_key]
            and not path_allowed(path, policy["approved_remaining_paths"])
        ]
        if unexpected:
            raise CommitScopeError(f"计划未覆盖且未批准保留的变更：{repository_key}：{unexpected}")
        policy["planned_paths"] = allowed

    sealed = {
        "schema": PLAN_SCHEMA,
        "repositories": list(policies.values()),
        "commits": sealed_commits,
    }
    return {
        "schema": PLAN_ENVELOPE_SCHEMA,
        "plan_sha256": canonical_sha256(sealed),
        "plan": sealed,
    }
#endregion


#region 提交预检与执行
def summarize_diff_check(result: subprocess.CompletedProcess[str], policy: str) -> dict[str, Any]:
    """压缩 whitespace 诊断，避免遗留仓库输出淹没控制台。"""

    lines = [line for line in result.stdout.splitlines() if line.strip()]
    summary = {
        "policy": policy,
        "passed": result.returncode == 0,
        "issue_line_count": len(lines),
        "preview": lines[:20],
        "truncated": len(lines) > 20,
    }
    if result.returncode != 0 and policy == "error":
        preview = "\n".join(lines[:20])
        suffix = f"\n...另有 {len(lines) - 20} 行" if len(lines) > 20 else ""
        raise CommitScopeError(f"git diff --cached --check 未通过：\n{preview}{suffix}")
    return summary


def preflight_with_temporary_index(
    repository: Path,
    allowed_paths: Sequence[str],
    diff_check_policy: str,
) -> dict[str, Any]:
    """在临时 index 中完成精确 staged-set 和 whitespace 预检。"""

    with tempfile.TemporaryDirectory(prefix="commit-and-orient-") as directory:
        index_path = Path(directory) / "index"
        environment = {"GIT_INDEX_FILE": str(index_path)}
        if head_state(repository)["has_commits"]:
            git_output(repository, "read-tree", "HEAD", environment=environment)
        add_result = run_git(repository, "add", "--", *allowed_paths, environment=environment)
        if add_result.returncode != 0:
            detail = add_result.stderr.strip() or add_result.stdout.strip() or "未知 Git 错误"
            raise CommitScopeError(f"临时 index 暂存失败：{detail}")
        staged = staged_files(repository, environment)
        expected = sorted(allowed_paths)
        if staged != expected:
            raise CommitScopeError(f"临时 index staged-set 与批准路径不一致：expected={expected}, actual={staged}")
        diff_check = run_git(repository, "diff", "--cached", "--check", environment=environment)
        return {
            "staged_files": staged,
            "diff_check": summarize_diff_check(diff_check, diff_check_policy),
        }


def set_repository_identity(repository: Path, policy: Mapping[str, Any], confirmed: bool) -> None:
    """仅在计划明确批准时设置 repository-local Git 身份。"""

    if policy.get("action") != "set_repository_local":
        return
    if not confirmed:
        raise CommitScopeError(
            f"设置仓库本地身份需要 --confirm-identity {IDENTITY_CONFIRMATION}：{repository}"
        )
    git_output(repository, "config", "--local", "user.name", str(policy["name"]))
    git_output(repository, "config", "--local", "user.email", str(policy["email"]))


def verify_repository_ready(repository: Path, *, allow_unborn: bool) -> None:
    """检查会使提交语义不明确的仓库状态。"""

    state = head_state(repository)
    if not state["has_commits"] and not allow_unborn:
        raise CommitScopeError(f"仓库尚无提交；必须显式批准 allow_unborn：{repository}")
    operations = git_operation_paths(repository)
    if operations:
        raise CommitScopeError(f"仓库存在进行中的 Git 操作：{', '.join(map(str, operations))}")
    pre_staged = staged_files(repository)
    if pre_staged:
        raise CommitScopeError(f"仓库已有暂存文件：{', '.join(pre_staged)}")


def commit_one(
    repository: Path,
    message: str,
    requested_paths: Sequence[str],
    *,
    allow_unborn: bool,
    diff_check_policy: str,
) -> dict[str, Any]:
    """预检后只提交经批准的精确文件集合。"""

    if not message.strip():
        raise CommitScopeError("提交说明不能为空")
    verify_repository_ready(repository, allow_unborn=allow_unborn)
    if not identity_info(repository)["available"]:
        raise CommitScopeError(f"仓库缺少有效 Git 身份：{repository}")
    allowed_paths = validate_requested_paths(repository, requested_paths)
    before = head_state(repository)
    preflight = preflight_with_temporary_index(repository, allowed_paths, diff_check_policy)

    add_result = run_git(repository, "add", "--", *allowed_paths)
    if add_result.returncode != 0:
        detail = add_result.stderr.strip() or add_result.stdout.strip() or "未知 Git 错误"
        raise CommitScopeError(f"暂存指定文件失败：{detail}")
    staged = staged_files(repository)
    if staged != sorted(allowed_paths):
        raise CommitScopeError(
            "真实暂存区与批准路径不一致；已保留暂存区供人工检查："
            f"expected={sorted(allowed_paths)}, actual={staged}"
        )
    real_diff_check = run_git(repository, "diff", "--cached", "--check")
    summarize_diff_check(real_diff_check, diff_check_policy)

    commit_result = run_git(repository, "commit", "-m", message)
    if commit_result.returncode != 0:
        detail = commit_result.stderr.strip() or commit_result.stdout.strip() or "未知 Git 错误"
        raise CommitScopeError(f"提交失败；已保留暂存区供人工检查：{detail}")
    after = head_state(repository)
    return {
        "repository": str(repository),
        "before_head": before["head"],
        "after_head": after["head"],
        "message": message,
        "committed_files": staged,
        "preflight": preflight,
        "identity": identity_info(repository),
        "remaining_status": status_lines(repository),
        "network_activity": "none",
    }


def verify_sealed_plan(envelope: Mapping[str, Any], approved_sha256: str) -> dict[str, Any]:
    """验证计划 envelope 和用户批准的稳定哈希。"""

    if envelope.get("schema") != PLAN_ENVELOPE_SCHEMA or not isinstance(envelope.get("plan"), dict):
        raise CommitScopeError(f"计划文件必须是 {PLAN_ENVELOPE_SCHEMA}")
    plan = dict(envelope["plan"])
    actual_hash = canonical_sha256(plan)
    recorded_hash = str(envelope.get("plan_sha256", ""))
    if recorded_hash != actual_hash or approved_sha256 != actual_hash:
        raise CommitScopeError(
            f"计划哈希不匹配：recorded={recorded_hash}, approved={approved_sha256}, actual={actual_hash}"
        )
    if plan.get("schema") != PLAN_SCHEMA:
        raise CommitScopeError(f"内部计划 schema 必须是 {PLAN_SCHEMA}")
    return plan


def verify_plan_repository(policy: Mapping[str, Any]) -> Path:
    """核验计划执行前的仓库、分支、HEAD、身份和未批准变更。"""

    repository = repository_root(str(policy["repository"]))
    state = head_state(repository)
    if state["branch"] != policy.get("branch") or state["head"] != policy.get("expected_head"):
        raise CommitScopeError(
            f"仓库 HEAD/分支已漂移：{repository}："
            f"expected=({policy.get('branch')}, {policy.get('expected_head')}), "
            f"actual=({state['branch']}, {state['head']})"
        )
    verify_repository_ready(repository, allow_unborn=bool(policy.get("allow_unborn", False)))
    planned = set(policy.get("planned_paths", []))
    remaining = list(policy.get("approved_remaining_paths", []))
    unexpected = [
        path for path in working_changes(repository) if path not in planned and not path_allowed(path, remaining)
    ]
    if unexpected:
        raise CommitScopeError(f"计划后出现未批准变更：{repository}：{unexpected}")
    return repository


def execute_plan(
    plan: Mapping[str, Any],
    *,
    identity_confirmed: bool,
) -> list[dict[str, Any]]:
    """按计划顺序执行多仓库提交；失败时保留之前成功的提交。"""

    policies = {str(item["repository"]): dict(item) for item in plan.get("repositories", [])}
    repositories: dict[str, Path] = {}
    for key, policy in policies.items():
        repository = verify_plan_repository(policy)
        set_repository_identity(repository, policy["identity_policy"], identity_confirmed)
        if not identity_info(repository)["available"]:
            raise CommitScopeError(f"仓库缺少有效 Git 身份：{repository}")
        repositories[key] = repository

    completed: list[dict[str, Any]] = []
    remaining_paths = {
        key: set(policy.get("planned_paths", []))
        for key, policy in policies.items()
    }
    try:
        for commit_spec in plan.get("commits", []):
            repository_key = str(commit_spec["repository"])
            repository = repositories[repository_key]
            current_states = path_states(repository, commit_spec["paths"])
            if current_states != commit_spec["path_states"]:
                raise CommitScopeError(f"批准后文件内容发生变化：{commit_spec['id']}")
            unexpected = [
                path
                for path in working_changes(repository)
                if path not in remaining_paths[repository_key]
                and not path_allowed(path, policies[repository_key]["approved_remaining_paths"])
            ]
            if unexpected:
                raise CommitScopeError(f"执行中出现未批准变更：{repository}：{unexpected}")
            result = commit_one(
                repository,
                str(commit_spec["message"]),
                list(commit_spec["paths"]),
                allow_unborn=bool(policies[repository_key]["allow_unborn"]),
                diff_check_policy=str(commit_spec.get("diff_check", "error")),
            )
            result["id"] = commit_spec["id"]
            result["context_impact"] = commit_spec.get("context_impact", "review")
            result["validation"] = commit_spec.get("validation", [])
            result["identity_action"] = policies[repository_key]["identity_policy"]["action"]
            completed.append(result)
            remaining_paths[repository_key].difference_update(commit_spec["paths"])
    except CommitScopeError as exc:
        raise PlanExecutionError(str(exc), completed) from exc
    return completed
#endregion


#region CLI
def read_path_file(path: Path | None) -> list[str]:
    """读取一行一个路径的 UTF-8 文件，忽略空行和注释。"""

    if path is None:
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise CommitScopeError(f"无法读取路径清单：{path}：{exc}") from exc
    return [line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#")]


def parse_args() -> argparse.Namespace:
    """解析盘点、计划封存与显式提交参数。"""

    parser = argparse.ArgumentParser(
        description="盘点、提出候选计划、封存计划或安全提交显式 Git 文件范围。"
    )
    parser.add_argument(
        "--mode",
        choices=("inventory", "propose-plan", "seal-plan", "commit", "execute-plan"),
        default="inventory",
    )
    parser.add_argument("--repo", action="append", default=[], help="Git 仓库或其内部路径；盘点模式可重复")
    parser.add_argument("--message", default="", help="直接提交模式所需的已批准提交说明")
    parser.add_argument("--path", action="append", default=[], help="直接提交模式的仓库相对文件")
    parser.add_argument("--path-file", type=Path, help="直接提交模式的一行一个相对文件路径清单")
    parser.add_argument("--plan", type=Path, help="seal-plan 的草案或 execute-plan 的 sealed envelope")
    parser.add_argument("--approved-sha256", default="", help="execute-plan 必须匹配的用户批准计划哈希")
    parser.add_argument("--allow-unborn", action="store_true", help="直接提交模式允许创建首个提交")
    parser.add_argument("--diff-check", choices=("error", "warn"), default="error")
    parser.add_argument("--local-user-name", default="", help="直接提交模式显式设置 repository-local user.name")
    parser.add_argument("--local-user-email", default="", help="直接提交模式显式设置 repository-local user.email")
    parser.add_argument("--apply", action="store_true", help="允许执行本地提交")
    parser.add_argument("--confirm", default="", help=f"提交模式必须为 {SCOPED_CONFIRMATION}")
    parser.add_argument("--confirm-identity", default="", help=f"设置本地身份时必须为 {IDENTITY_CONFIRMATION}")
    parser.add_argument("--timeout", type=int, default=DEFAULT_GIT_TIMEOUT_SECONDS, help="单个 Git 命令超时秒数")
    return parser.parse_args()


def main() -> int:
    """输出 JSON；一切 Git 写入都需要显式开关和确认值。"""

    global DEFAULT_GIT_TIMEOUT_SECONDS
    args = parse_args()
    DEFAULT_GIT_TIMEOUT_SECONDS = max(1, int(args.timeout))
    try:
        if args.mode == "inventory":
            if not args.repo:
                raise CommitScopeError("inventory 至少需要一个 --repo")
            repositories = list(dict.fromkeys(repository_root(item) for item in args.repo))
            payload: dict[str, Any] = {
                "mode": "inventory",
                "repositories": [inventory(path) for path in repositories],
            }
        elif args.mode == "propose-plan":
            if not args.repo:
                raise CommitScopeError("propose-plan 至少需要一个 --repo")
            repositories = list(dict.fromkeys(repository_root(item) for item in args.repo))
            payload = {
                "mode": "propose-plan",
                "proposal_version": "file-clustering-v1",
                "repositories": [propose_commit_groups(path) for path in repositories],
                "safety_note": (
                    "候选不暂存、不提交、不自动分割同一文件；"
                    "请人工分配 bridge_paths 后再封存。"
                ),
            }
        elif args.mode == "seal-plan":
            if args.plan is None:
                raise CommitScopeError("seal-plan 需要 --plan <draft.json>")
            payload = {"mode": "seal-plan", **seal_plan(load_json(args.plan))}
        elif args.mode == "execute-plan":
            if not args.apply or args.confirm != SCOPED_CONFIRMATION:
                raise CommitScopeError(f"execute-plan 需要 --apply --confirm {SCOPED_CONFIRMATION}")
            if args.plan is None or not args.approved_sha256:
                raise CommitScopeError("execute-plan 需要 --plan 和 --approved-sha256")
            envelope = load_json(args.plan)
            plan = verify_sealed_plan(envelope, args.approved_sha256)
            try:
                completed = execute_plan(
                    plan,
                    identity_confirmed=args.confirm_identity == IDENTITY_CONFIRMATION,
                )
            except PlanExecutionError as exc:
                print(
                    json.dumps(
                        {
                            "mode": "execute-plan",
                            "error": str(exc),
                            "completed": exc.completed,
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                )
                return 2
            payload = {"mode": "execute-plan", "plan_sha256": args.approved_sha256, "completed": completed}
        else:
            if not args.apply or args.confirm != SCOPED_CONFIRMATION:
                raise CommitScopeError(f"commit 需要 --apply --confirm {SCOPED_CONFIRMATION}")
            if len(args.repo) != 1:
                raise CommitScopeError("直接提交模式一次只能处理一个 --repo")
            repository = repository_root(args.repo[0])
            identity_policy = normalize_identity_policy(
                {
                    "action": "set_repository_local",
                    "name": args.local_user_name,
                    "email": args.local_user_email,
                }
                if args.local_user_name or args.local_user_email
                else None
            )
            set_repository_identity(
                repository,
                identity_policy,
                args.confirm_identity == IDENTITY_CONFIRMATION,
            )
            paths = [*args.path, *read_path_file(args.path_file)]
            payload = {
                "mode": "commit",
                "commit": commit_one(
                    repository,
                    args.message,
                    paths,
                    allow_unborn=args.allow_unborn,
                    diff_check_policy=args.diff_check,
                ),
            }
    except (CommitScopeError, OSError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
#endregion
