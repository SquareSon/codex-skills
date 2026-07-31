---
name: commit-and-orient
description: Plan, review, and—only after explicit approval—perform safe, scoped local Git commits across one or more repositories, then refresh project orientation. Use when Codex needs to split current changes into coherent commits, write commit messages, commit a ProjectProfile workspace, or refresh codebase understanding after authorized commits.
---

# Commit And Orient

Create traceable local commits without confusing IDE configuration, generated artifacts, third-party state, and source changes. This skill never pushes, pulls, changes branches, rewrites history, or creates a remote.

## 1. Inspect Before Planning

1. Read `$codebase-orientation` and its `project-profile-and-git` reference before deciding repository scope.
2. For every requested repository, run the read-only inventory:

   ```bash
   conda run -n codex-tools python <skill-dir>/scripts/commit_scoped_changes.py \
     --mode inventory --repo <repository-root>
   ```

3. For a ProjectProfile workspace, resolve the Active links first. Treat the workspace and each selected component as independent Git repositories.
4. Inspect the relevant diffs. Separate source code, tests, documentation, `profile/`, workspace configuration, generated output, and third-party changes.
5. Stop and report if a repository already has staged changes, a merge/rebase/cherry-pick is in progress, Git identity is unavailable, or the requested scope is ambiguous.

`Excluded` only affects IDE indexing; `.gitignore` controls ordinary Git discovery. Do not treat either as proof that a file should be committed.

## 2. Propose a Commit Plan

Before mutating Git, provide a concise plan containing one row per intended commit:

| Repository | Explicit files | Purpose | Commit message | Validation |
| --- | --- | --- | --- | --- |
| `<root>` | `<relative paths>` | `<one coherent change>` | `<type(scope): summary>` | `<review/test or not run>` |

Follow these rules:

- Keep one repository per commit. A workspace repository does not commit files inside linked component repositories.
- Do not use `git add .`, `git commit -a`, wildcard staging, forced commits, or `--no-verify`.
- Keep a Profile migration separate from unrelated algorithm changes when practical.
- Include tests and the implementation they verify in the same feature commit.
- Include generated `.idea` files only when they are intentional, reproducible shared configuration derived from Profile; exclude personal IDE state.
- Do not stage logs, checkpoints, outputs, caches, data, secrets, nested third-party source, or unrelated pre-existing changes without explicit user direction.
- Write an imperative, concise message. Prefer `feat(cache): prefetch training image caches` over `update files`.

Ask for explicit confirmation of the displayed plan. A request to "commit everything" is not sufficient when multiple repositories or unrelated change groups are present.

## 3. Execute an Approved Commit

Only after the user confirms the exact plan, run one command per planned commit:

```bash
conda run -n codex-tools python <skill-dir>/scripts/commit_scoped_changes.py \
  --mode commit \
  --repo <repository-root> \
  --message "<approved message>" \
  --path <approved-relative-file> \
  --path <another-approved-relative-file> \
  --apply --confirm I_CONFIRM_SCOPED_COMMIT
```

The helper verifies the repository boundary, blocks in-progress Git operations and pre-existing staged changes, stages only explicit relative paths, verifies the staged set, and performs one ordinary local commit. If a later repository fails, stop and report earlier successful commits; never reset them automatically.

After every commit, record the new SHA and remaining working-tree changes. Do not push unless the user separately asks to configure or use a remote.

## 4. Refresh Orientation After Commit

After all approved commits finish, invoke `$codebase-orientation` again in read-only mode for the original workspace or component paths. It must refresh Active selection, Profile, HEAD/tag, dirty state, entrypoints, and third-party lock evidence.

Use `collect_orientation_context.py` for a concise machine-readable snapshot:

```bash
conda run -n codex-tools python \
  /home/square/.codex/skills/codebase-orientation/scripts/collect_orientation_context.py \
  --path <workspace-or-component>
```

Report the refreshed state as the current understanding. This is a new evidence pass, not hidden persistent memory. Update project README or other documentation only when the user explicitly asks to edit it.

## 5. Final Report

State:

1. committed repository, SHA, message, and exact staged files;
2. repositories deliberately left dirty and why;
3. tests or checks run, and checks intentionally not run;
4. whether a remote exists and whether any network action occurred; and
5. the refreshed orientation summary and remaining uncertainty.
