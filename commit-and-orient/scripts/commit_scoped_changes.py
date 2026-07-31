# -*- coding: utf-8 -*-
"""只读盘点或显式范围内提交一个 Git 仓库，供 Commit And Orient Skill 调用。"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any, Sequence


class CommitScopeError(RuntimeError):
    """表示提交范围、Git 状态或用户确认不满足安全要求。"""


def run_git(repository: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    """在指定仓库执行 Git 命令，并始终捕获输出。"""

    return subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )


def git_output(repository: Path, *arguments: str) -> str:
    """返回成功 Git 命令的输出，否则抛出带上下文的错误。"""

    result = run_git(repository, *arguments)
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


def status_lines(repository: Path) -> list[str]:
    """读取 porcelain 状态，保留 Git 原始双字符状态以便审查。"""

    output = git_output(repository, "status", "--porcelain=v1")
    return output.splitlines() if output else []


def staged_files(repository: Path) -> list[str]:
    """读取已暂存文件，避免吞入用户原有暂存内容。"""

    output = git_output(repository, "diff", "--cached", "--name-only")
    return output.splitlines() if output else []


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


def inventory(repository: Path) -> dict[str, Any]:
    """返回提交计划所需的只读仓库证据。"""

    remotes = git_output(repository, "remote").splitlines()
    return {
        "repository": str(repository),
        "branch": git_output(repository, "branch", "--show-current"),
        "head": git_output(repository, "rev-parse", "HEAD"),
        "describe": git_output(repository, "describe", "--tags", "--always", "--dirty"),
        "status": status_lines(repository),
        "staged_files": staged_files(repository),
        "git_operations": [str(path) for path in git_operation_paths(repository)],
        "remote_names": remotes,
    }


def validate_requested_paths(repository: Path, requested_paths: Sequence[str]) -> list[str]:
    """验证全部路径均是仓库内的显式相对路径。"""

    if not requested_paths:
        raise CommitScopeError("提交模式至少需要一个 --path，禁止提交整个仓库")
    normalized: list[str] = []
    for path_text in requested_paths:
        candidate = Path(path_text)
        if candidate.is_absolute() or path_text in {"", "."} or path_text.startswith("-"):
            raise CommitScopeError(f"--path 必须是非空、非选项形式的相对路径：{path_text!r}")
        resolved = (repository / candidate).resolve(strict=False)
        try:
            relative = resolved.relative_to(repository)
        except ValueError as exc:
            raise CommitScopeError(f"--path 越出仓库边界：{path_text!r}") from exc
        normalized_path = relative.as_posix()
        if normalized_path not in normalized:
            normalized.append(normalized_path)
    return normalized


def is_within_allowed_path(path_text: str, allowed_paths: Sequence[str]) -> bool:
    """允许准确文件，或用户明确批准的目录下文件。"""

    return any(path_text == allowed or path_text.startswith(f"{allowed}/") for allowed in allowed_paths)


def commit(repository: Path, message: str, requested_paths: Sequence[str], confirmed: bool) -> dict[str, Any]:
    """只提交经确认的显式文件范围，并返回提交前后的可审计结果。"""

    if not confirmed:
        raise CommitScopeError("提交需要 --apply --confirm I_CONFIRM_SCOPED_COMMIT")
    if not message.strip():
        raise CommitScopeError("提交说明不能为空")
    active_operations = git_operation_paths(repository)
    if active_operations:
        raise CommitScopeError(f"仓库存在进行中的 Git 操作：{', '.join(str(path) for path in active_operations)}")
    pre_staged = staged_files(repository)
    if pre_staged:
        raise CommitScopeError(
            "仓库已有暂存文件；请先人工审查或清理暂存区，避免本工具混入已有提交范围："
            f"{', '.join(pre_staged)}"
        )

    allowed_paths = validate_requested_paths(repository, requested_paths)
    before_head = git_output(repository, "rev-parse", "HEAD")
    add_result = run_git(repository, "add", "--", *allowed_paths)
    if add_result.returncode != 0:
        detail = add_result.stderr.strip() or add_result.stdout.strip() or "未知 Git 错误"
        raise CommitScopeError(f"暂存指定文件失败：{detail}")

    staged = staged_files(repository)
    if not staged:
        raise CommitScopeError("指定路径没有产生可提交的变更")
    unexpected = [path for path in staged if not is_within_allowed_path(path, allowed_paths)]
    if unexpected:
        raise CommitScopeError(f"暂存区出现未批准文件：{', '.join(unexpected)}")

    commit_result = run_git(repository, "commit", "-m", message)
    if commit_result.returncode != 0:
        detail = commit_result.stderr.strip() or commit_result.stdout.strip() or "未知 Git 错误"
        raise CommitScopeError(f"提交失败；为避免隐式变更，已保留暂存区供人工检查：{detail}")
    after_head = git_output(repository, "rev-parse", "HEAD")
    return {
        "repository": str(repository),
        "before_head": before_head,
        "after_head": after_head,
        "message": message,
        "committed_files": staged,
        "remaining_status": status_lines(repository),
    }


def parse_args() -> argparse.Namespace:
    """解析盘点与单仓库显式范围提交参数。"""

    parser = argparse.ArgumentParser(description="盘点或安全地提交显式 Git 文件范围。")
    parser.add_argument("--mode", choices=("inventory", "commit"), default="inventory")
    parser.add_argument("--repo", action="append", required=True, help="Git 仓库或其内部路径；可重复用于盘点")
    parser.add_argument("--message", default="", help="提交模式所需的已批准提交说明")
    parser.add_argument("--path", action="append", default=[], help="提交模式允许的仓库相对文件或目录")
    parser.add_argument("--apply", action="store_true", help="允许执行本地提交")
    parser.add_argument("--confirm", default="", help="提交模式必须为 I_CONFIRM_SCOPED_COMMIT")
    return parser.parse_args()


def main() -> int:
    """输出 JSON，盘点默认只读，提交必须同时满足显式开关和确认值。"""

    args = parse_args()
    try:
        repositories = [repository_root(path_text) for path_text in args.repo]
        unique_repositories = list(dict.fromkeys(repositories))
        if args.mode == "inventory":
            payload: dict[str, Any] = {"mode": "inventory", "repositories": [inventory(path) for path in unique_repositories]}
        else:
            if len(unique_repositories) != 1:
                raise CommitScopeError("提交模式一次只能处理一个仓库")
            payload = {
                "mode": "commit",
                "commit": commit(
                    unique_repositories[0],
                    args.message,
                    args.path,
                    args.apply and args.confirm == "I_CONFIRM_SCOPED_COMMIT",
                ),
            }
    except (CommitScopeError, OSError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
