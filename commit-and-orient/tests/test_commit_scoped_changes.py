#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在临时 Git 仓库中验证 commit-and-orient helper 的安全边界。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[1] / "scripts" / "commit_scoped_changes.py"
SCOPED_CONFIRMATION = "I_CONFIRM_SCOPED_COMMIT"
IDENTITY_CONFIRMATION = "I_CONFIRM_REPOSITORY_LOCAL_IDENTITY"


def run(command: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    """运行测试命令并捕获 UTF-8 输出。"""

    return subprocess.run(
        command,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )


def git(repository: Path, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    """运行隔离的本地 Git 命令。"""

    result = run(["git", "-C", str(repository), *arguments])
    if check and result.returncode != 0:
        raise AssertionError(result.stderr or result.stdout)
    return result


def initialize_repository(path: Path, *, with_identity: bool) -> Path:
    """创建不依赖全局身份的临时 main 仓库。"""

    path.mkdir()
    result = run(["git", "init", "-b", "main", str(path)])
    if result.returncode != 0:
        git(path, "init")
        git(path, "symbolic-ref", "HEAD", "refs/heads/main")
    if with_identity:
        git(path, "config", "--local", "user.name", "Skill Test")
        git(path, "config", "--local", "user.email", "skill-test@example.invalid")
    return path


def helper(*arguments: str) -> tuple[int, dict]:
    """调用 helper，并解析其 JSON 输出。"""

    environment = os.environ.copy()
    environment["GIT_CONFIG_GLOBAL"] = os.devnull
    environment["GIT_CONFIG_SYSTEM"] = os.devnull
    result = subprocess.run(
        [sys.executable, str(SCRIPT), *arguments],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        env=environment,
    )
    assert result.stdout.strip(), result.stderr
    return result.returncode, json.loads(result.stdout)


def create_baseline(repository: Path) -> str:
    """建立一个最小成熟仓库并返回 HEAD。"""

    (repository / "baseline.txt").write_text("baseline\n", encoding="utf-8")
    git(repository, "add", "--", "baseline.txt")
    git(repository, "commit", "-m", "chore: baseline")
    return git(repository, "rev-parse", "HEAD").stdout.strip()


def test_inventory_supports_unborn_repository(tmp_path: Path) -> None:
    repository = initialize_repository(tmp_path / "unborn", with_identity=False)

    code, payload = helper("--mode", "inventory", "--repo", str(repository))

    assert code == 0
    item = payload["repositories"][0]
    assert item["head_state"] == "unborn"
    assert item["head"] is None
    assert item["identity"]["available"] is False


def test_propose_plan_groups_single_topic_implementation_tests_and_docs(tmp_path: Path) -> None:
    repository = initialize_repository(tmp_path / "proposal", with_identity=True)
    create_baseline(repository)
    for relative_path in (
        "nerfus/evaluation/metric_runtime.py",
        "tests/test_metric_runtime.py",
        "docs/metric_runtime.md",
        "nerfus/nerf/ultrasound_ray_footprint.py",
        "tests/test_ultrasound_ray_footprint.py",
        "scripts/run_physical_footprint.py",
    ):
        path = repository / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# changed implementation\n", encoding="utf-8")

    code, payload = helper("--mode", "propose-plan", "--repo", str(repository))

    assert code == 0
    proposal = payload["repositories"][0]
    groups = {item["id"]: item for item in proposal["candidates"]}
    assert set(groups) == {"evaluation", "spatial"}
    assert "tests/test_metric_runtime.py" in groups["evaluation"]["paths"]
    assert "docs/metric_runtime.md" in groups["evaluation"]["paths"]
    assert "tests/test_ultrasound_ray_footprint.py" in groups["spatial"]["paths"]
    assert proposal["bridge_paths"] == []
    assert proposal["safe_to_seal"] is True
    assert git(repository, "diff", "--cached", "--name-only").stdout.strip() == ""


def test_propose_plan_marks_multi_topic_file_as_bridge_without_mutation(tmp_path: Path) -> None:
    repository = initialize_repository(tmp_path / "bridge", with_identity=True)
    create_baseline(repository)
    path = repository / "nerfus" / "nerf" / "metric_cache_runtime.py"
    path.parent.mkdir(parents=True)
    path.write_text("metric cache runtime\n", encoding="utf-8")

    code, payload = helper("--mode", "propose-plan", "--repo", str(repository))

    assert code == 0
    proposal = payload["repositories"][0]
    assert proposal["safe_to_seal"] is False
    assert proposal["bridge_paths"][0]["path"] == "nerfus/nerf/metric_cache_runtime.py"
    bridge = proposal["bridge_paths"][0]
    assert {bridge["primary_topic"], *bridge["bridge_topics"]} == {"cache-validation", "evaluation"}
    assert git(repository, "diff", "--cached", "--name-only").stdout.strip() == ""


def test_propose_plan_reports_preexisting_stage_as_blocker(tmp_path: Path) -> None:
    repository = initialize_repository(tmp_path / "proposal-staged", with_identity=True)
    create_baseline(repository)
    path = repository / "metric_runtime.py"
    path.write_text("metric\n", encoding="utf-8")
    git(repository, "add", "--", "metric_runtime.py")

    code, payload = helper("--mode", "propose-plan", "--repo", str(repository))

    assert code == 0
    proposal = payload["repositories"][0]
    assert proposal["safe_to_seal"] is False
    assert proposal["blocking_conditions"] == [
        {"kind": "preexisting_staged", "paths": ["metric_runtime.py"]}
    ]


def test_direct_commit_can_create_root_commit_with_approved_local_identity(tmp_path: Path) -> None:
    repository = initialize_repository(tmp_path / "root", with_identity=False)
    (repository / "README.md").write_text("# Root\n", encoding="utf-8")

    code, payload = helper(
        "--mode", "commit",
        "--repo", str(repository),
        "--message", "feat: establish baseline",
        "--path", "README.md",
        "--allow-unborn",
        "--local-user-name", "Root Author",
        "--local-user-email", "root@example.invalid",
        "--apply",
        "--confirm", SCOPED_CONFIRMATION,
        "--confirm-identity", IDENTITY_CONFIRMATION,
    )

    assert code == 0
    assert payload["commit"]["before_head"] is None
    assert git(repository, "rev-list", "--count", "HEAD").stdout.strip() == "1"
    assert git(repository, "config", "--local", "user.name").stdout.strip() == "Root Author"


def test_sealed_plan_can_create_root_commit_with_approved_identity(tmp_path: Path) -> None:
    repository = initialize_repository(tmp_path / "planned-root", with_identity=False)
    (repository / "README.md").write_text("# Planned root\n", encoding="utf-8")
    draft = {
        "schema": "commit-and-orient-plan/v2",
        "repositories": [
            {
                "repository": str(repository),
                "allow_unborn": True,
                "identity_policy": {
                    "action": "set_repository_local",
                    "name": "Planned Author",
                    "email": "planned@example.invalid",
                },
            }
        ],
        "commits": [
            {
                "id": "root",
                "repository": str(repository),
                "message": "feat: establish planned baseline",
                "paths": ["README.md"],
            }
        ],
    }
    draft_path = tmp_path / "root-draft.json"
    draft_path.write_text(json.dumps(draft), encoding="utf-8")
    seal_code, envelope = helper("--mode", "seal-plan", "--plan", str(draft_path))
    assert seal_code == 0
    envelope_path = tmp_path / "root-sealed.json"
    envelope_path.write_text(json.dumps(envelope), encoding="utf-8")

    execute_code, result = helper(
        "--mode", "execute-plan",
        "--plan", str(envelope_path),
        "--approved-sha256", envelope["plan_sha256"],
        "--apply",
        "--confirm", SCOPED_CONFIRMATION,
        "--confirm-identity", IDENTITY_CONFIRMATION,
    )

    assert execute_code == 0
    assert result["completed"][0]["before_head"] is None
    assert result["completed"][0]["identity_action"] == "set_repository_local"
    assert result["completed"][0]["identity"]["name"] == "Planned Author"


def test_diff_check_failure_does_not_touch_real_index(tmp_path: Path) -> None:
    repository = initialize_repository(tmp_path / "whitespace", with_identity=True)
    create_baseline(repository)
    (repository / "bad.txt").write_text("trailing  \n", encoding="utf-8")

    code, payload = helper(
        "--mode", "commit",
        "--repo", str(repository),
        "--message", "test: reject whitespace",
        "--path", "bad.txt",
        "--apply",
        "--confirm", SCOPED_CONFIRMATION,
    )

    assert code == 2
    assert "diff --cached --check" in payload["error"]
    assert git(repository, "diff", "--cached", "--name-only").stdout.strip() == ""


def test_sealed_plan_executes_two_commits_in_one_repository(tmp_path: Path) -> None:
    repository = initialize_repository(tmp_path / "planned", with_identity=True)
    create_baseline(repository)
    (repository / "a.txt").write_text("a\n", encoding="utf-8")
    (repository / "b.txt").write_text("b\n", encoding="utf-8")
    draft = {
        "schema": "commit-and-orient-plan/v2",
        "repositories": [{"repository": str(repository)}],
        "commits": [
            {"id": "a", "repository": str(repository), "message": "feat: add a", "paths": ["a.txt"]},
            {"id": "b", "repository": str(repository), "message": "feat: add b", "paths": ["b.txt"]},
        ],
    }
    draft_path = tmp_path / "draft.json"
    draft_path.write_text(json.dumps(draft), encoding="utf-8")

    seal_code, envelope = helper("--mode", "seal-plan", "--plan", str(draft_path))
    assert seal_code == 0
    envelope_path = tmp_path / "sealed.json"
    envelope_path.write_text(json.dumps(envelope), encoding="utf-8")
    execute_code, result = helper(
        "--mode", "execute-plan",
        "--plan", str(envelope_path),
        "--approved-sha256", envelope["plan_sha256"],
        "--apply",
        "--confirm", SCOPED_CONFIRMATION,
    )

    assert execute_code == 0
    assert [item["id"] for item in result["completed"]] == ["a", "b"]
    assert git(repository, "rev-list", "--count", "HEAD").stdout.strip() == "3"
    assert git(repository, "status", "--porcelain").stdout.strip() == ""


def test_execute_plan_stops_on_unapproved_drift(tmp_path: Path) -> None:
    repository = initialize_repository(tmp_path / "drift", with_identity=True)
    baseline = create_baseline(repository)
    (repository / "a.txt").write_text("a\n", encoding="utf-8")
    draft = {
        "schema": "commit-and-orient-plan/v2",
        "repositories": [{"repository": str(repository)}],
        "commits": [
            {"id": "a", "repository": str(repository), "message": "feat: add a", "paths": ["a.txt"]}
        ],
    }
    draft_path = tmp_path / "drift-draft.json"
    draft_path.write_text(json.dumps(draft), encoding="utf-8")
    seal_code, envelope = helper("--mode", "seal-plan", "--plan", str(draft_path))
    assert seal_code == 0
    envelope_path = tmp_path / "drift-sealed.json"
    envelope_path.write_text(json.dumps(envelope), encoding="utf-8")
    (repository / "unexpected.txt").write_text("new\n", encoding="utf-8")

    execute_code, result = helper(
        "--mode", "execute-plan",
        "--plan", str(envelope_path),
        "--approved-sha256", envelope["plan_sha256"],
        "--apply",
        "--confirm", SCOPED_CONFIRMATION,
    )

    assert execute_code == 2
    assert "未批准变更" in result["error"]
    assert git(repository, "rev-parse", "HEAD").stdout.strip() == baseline


def test_sealed_plan_hash_rejects_tampered_message(tmp_path: Path) -> None:
    repository = initialize_repository(tmp_path / "tamper", with_identity=True)
    create_baseline(repository)
    (repository / "a.txt").write_text("a\n", encoding="utf-8")
    draft = {
        "schema": "commit-and-orient-plan/v2",
        "repositories": [{"repository": str(repository)}],
        "commits": [
            {"id": "a", "repository": str(repository), "message": "feat: add a", "paths": ["a.txt"]}
        ],
    }
    draft_path = tmp_path / "tamper-draft.json"
    draft_path.write_text(json.dumps(draft), encoding="utf-8")
    seal_code, envelope = helper("--mode", "seal-plan", "--plan", str(draft_path))
    assert seal_code == 0
    approved_hash = envelope["plan_sha256"]
    envelope["plan"]["commits"][0]["message"] = "feat: changed after approval"
    envelope_path = tmp_path / "tampered.json"
    envelope_path.write_text(json.dumps(envelope), encoding="utf-8")

    execute_code, result = helper(
        "--mode", "execute-plan",
        "--plan", str(envelope_path),
        "--approved-sha256", approved_hash,
        "--apply",
        "--confirm", SCOPED_CONFIRMATION,
    )

    assert execute_code == 2
    assert "计划哈希不匹配" in result["error"]


def test_warn_policy_records_whitespace_and_commits(tmp_path: Path) -> None:
    repository = initialize_repository(tmp_path / "warn", with_identity=True)
    create_baseline(repository)
    (repository / "legacy.txt").write_text("legacy trailing  \n", encoding="utf-8")

    code, payload = helper(
        "--mode", "commit",
        "--repo", str(repository),
        "--message", "chore: preserve legacy whitespace",
        "--path", "legacy.txt",
        "--diff-check", "warn",
        "--apply",
        "--confirm", SCOPED_CONFIRMATION,
    )

    assert code == 0
    summary = payload["commit"]["preflight"]["diff_check"]
    assert summary["passed"] is False
    assert summary["issue_line_count"] > 0
    assert git(repository, "show", "--format=", "--name-only", "HEAD").stdout.strip() == "legacy.txt"


def test_plan_reports_partial_success_without_rollback(tmp_path: Path) -> None:
    repository = initialize_repository(tmp_path / "partial", with_identity=True)
    create_baseline(repository)
    (repository / "a.txt").write_text("a\n", encoding="utf-8")
    (repository / "b.txt").write_text("b\n", encoding="utf-8")
    hook = repository / ".git" / "hooks" / "commit-msg"
    hook.write_text(
        "#!/bin/sh\n"
        "grep -q 'feat: add b' \"$1\" && exit 1\n"
        "exit 0\n",
        encoding="utf-8",
    )
    hook.chmod(0o755)
    draft = {
        "schema": "commit-and-orient-plan/v2",
        "repositories": [{"repository": str(repository)}],
        "commits": [
            {"id": "a", "repository": str(repository), "message": "feat: add a", "paths": ["a.txt"]},
            {"id": "b", "repository": str(repository), "message": "feat: add b", "paths": ["b.txt"]},
        ],
    }
    draft_path = tmp_path / "partial-draft.json"
    draft_path.write_text(json.dumps(draft), encoding="utf-8")
    seal_code, envelope = helper("--mode", "seal-plan", "--plan", str(draft_path))
    assert seal_code == 0
    envelope_path = tmp_path / "partial-sealed.json"
    envelope_path.write_text(json.dumps(envelope), encoding="utf-8")

    execute_code, result = helper(
        "--mode", "execute-plan",
        "--plan", str(envelope_path),
        "--approved-sha256", envelope["plan_sha256"],
        "--apply",
        "--confirm", SCOPED_CONFIRMATION,
    )

    assert execute_code == 2
    assert [item["id"] for item in result["completed"]] == ["a"]
    assert git(repository, "rev-list", "--count", "HEAD").stdout.strip() == "2"
    assert git(repository, "diff", "--cached", "--name-only").stdout.strip() == "b.txt"


def test_directory_scope_is_rejected(tmp_path: Path) -> None:
    repository = initialize_repository(tmp_path / "directory", with_identity=True)
    create_baseline(repository)
    source = repository / "src"
    source.mkdir()
    (source / "module.py").write_text("VALUE = 1\n", encoding="utf-8")

    code, payload = helper(
        "--mode", "commit",
        "--repo", str(repository),
        "--message", "feat: add source",
        "--path", "src",
        "--apply",
        "--confirm", SCOPED_CONFIRMATION,
    )

    assert code == 2
    assert "目录范围" in payload["error"]


def test_preexisting_staged_change_is_rejected(tmp_path: Path) -> None:
    repository = initialize_repository(tmp_path / "staged", with_identity=True)
    create_baseline(repository)
    (repository / "staged.txt").write_text("staged\n", encoding="utf-8")
    git(repository, "add", "--", "staged.txt")

    code, payload = helper(
        "--mode", "commit",
        "--repo", str(repository),
        "--message", "feat: staged",
        "--path", "staged.txt",
        "--apply",
        "--confirm", SCOPED_CONFIRMATION,
    )

    assert code == 2
    assert "已有暂存文件" in payload["error"]


@pytest.mark.parametrize("path_text", ["../outside.txt", ".", "-option"])
def test_unsafe_paths_are_rejected(tmp_path: Path, path_text: str) -> None:
    repository = initialize_repository(tmp_path / f"unsafe-{abs(hash(path_text))}", with_identity=True)
    create_baseline(repository)
    path_arguments = [f"--path={path_text}"] if path_text.startswith("-") else ["--path", path_text]

    code, payload = helper(
        "--mode", "commit",
        "--repo", str(repository),
        "--message", "test: unsafe",
        *path_arguments,
        "--apply",
        "--confirm", SCOPED_CONFIRMATION,
    )

    assert code == 2
    assert "路径" in payload["error"] or "relative" in payload["error"]
