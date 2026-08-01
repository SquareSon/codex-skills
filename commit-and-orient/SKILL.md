---
name: commit-and-orient
description: Plan, seal, approve, execute, and audit safe scoped local Git commits across one or more existing or unborn repositories, then run read-only codebase orientation and hierarchical AI_CONTEXT impact checks. Use when Codex needs to split working-tree changes into coherent commits, establish an approved repository baseline, bind approval to exact file contents, commit a ProjectProfile workspace, or coordinate a separately authorized Context refresh.
---

# Commit And Orient

Create traceable local commits without mixing source, Profile, shared IDE
configuration, generated artifacts, third-party state, or AI Context changes.
Never push, pull, change branches, rewrite history, initialize repositories, or
create remotes.

## Inspect before planning

1. Read $codebase-orientation and its ProjectProfile/Git reference. Resolve
   Active links before choosing scope; a workspace and its selected components
   are independent Git repositories.
2. Inventory every requested repository:

   ~~~bash
   conda run -n codex-tools python <skill-dir>/scripts/commit_scoped_changes.py --mode inventory --repo <repository-root>
   ~~~

3. Inspect relevant diffs and classify source, tests, documentation, profile/,
   reproducible .idea configuration, Context, stable evidence, generated
   output, local-only planning, and third-party paths.
4. Stop on pre-existing staged files, active Git operations, unresolved
   repository boundaries, missing identity without an approved local-identity
   policy, or ambiguous scope.
5. Treat Excluded as IDE indexing only and .gitignore as Git discovery only;
   neither decides scientific or commit relevance.

Inventory supports an unborn repository with head null; it does not authorize
the first commit. Read
[initial-repository-and-context.md](references/initial-repository-and-context.md)
for root commits, identity exceptions, legacy whitespace, or Context refresh.

## Choose simple or sealed execution

Use direct mode only for one mature repository, one small coherent commit, and a
short exact file list. Use a sealed plan when any condition holds:

- more than one repository or commit;
- more than 20 files;
- an unborn repository or repository-local identity exception;
- approved remaining local changes;
- a legacy diff_check warn exception; or
- approval must survive a long-running task or concurrent user activity.

Read [commit-plan-schema.md](references/commit-plan-schema.md) for sealed-plan
format, hash approval, and execution commands.

## Propose and approve the plan

Before Git mutation, provide one row per intended commit:

| ID | Repository | Exact files/manifest | Purpose | Message | Validation | Context action |
| --- | --- | --- | --- | --- | --- | --- |
| <id> | <root> | <paths or manifest hash> | <change> | <type(scope): summary> | <checks> | <none/review/refresh_planned> |

Apply these rules:

- Keep one repository per commit. Never use git add dot, git commit -a,
  wildcards, directory scopes, forced commits, or --no-verify.
- Keep implementation and its tests together. Separate Profile migration,
  unrelated algorithms, workspace IDE integration, and Context when practical.
- Include .idea only when it is intentional, reproducible shared configuration
  derived from Profile.
- Exclude personal state, credentials, logs, checkpoints, outputs, caches,
  datasets, local environment maps, and nested third-party source unless the
  user explicitly approves a justified exception.
- Mark Context impact review for Profile/Active mapping, entrypoints, core
  control/data flow, configuration resolution, contracts, cross-component
  interfaces, behavioral tests, boundaries, or semantic evidence anchors.
- Treat “commit everything” as insufficient for unrelated repositories or
  change groups.

For sealed execution, show the canonical plan_sha256; approval binds to that
hash and the exact file states it represents. Re-seal and reapprove after any
planned file, HEAD, branch, identity policy, message, or path-set change.

## Execute approved commits

For a small direct commit:

~~~bash
conda run -n codex-tools python <skill-dir>/scripts/commit_scoped_changes.py --mode commit --repo <repository-root> --message "<approved message>" --path <approved-relative-file> --apply --confirm I_CONFIRM_SCOPED_COMMIT
~~~

The helper:

- validates repository, branch/HEAD state, identity, Git operations, and exact
  changed files;
- rejects directories, path traversal, unchanged paths, and pre-existing staged
  files;
- stages first in a temporary Git index;
- verifies the exact staged set and runs git diff --cached --check;
- touches the real index only after preflight succeeds;
- preserves hook behavior and retains the real staged set for inspection if
  the final ordinary git commit fails; and
- records before/after SHA, committed files, remaining status, and no network
  activity.

After every commit, record success before continuing. If a later commit fails,
stop, preserve earlier commits, report the partial result, and never reset them
automatically.

## Coordinate Context explicitly

Context has three actions:

- none: no semantic impact.
- review: commit code, then assess impact during post-commit read-only
  orientation.
- refresh_planned: after a Deep + inspect_only evidence pass, use
  $ai-project-guide to write and validate the actual v4 Context/provenance diff;
  obtain approval for that content and commit it separately.

Do not create or refresh Context merely because a commit exists. Do not treat
approval of a future unknown Context file as approval of its eventual content.

## Read-only orientation after commit

After all approved source and any separately approved Context commits, invoke
$codebase-orientation as Quick + read_only for every affected
workspace/component:

1. collect workspace Active/Profile/Git/runtime once;
2. validate current v3/v4 root and Active-child Context nodes;
3. build an intent-specific Bundle per affected component when a global Bundle
   would exceed budget;
4. report child coverage, stale semantic nodes, route/contract impact,
   interpreter alignment, boundaries, and explicit evidence gaps; and
5. distinguish validation states as passed, failed, resource_blocked, or
   not_run.

This pass never writes Context, alters AGENTS.md, contacts remotes, or treats a
commit as proof of execution or a paper claim.

## Final report

Report:

1. repository, SHA, message, and exact committed files; for a large plan, give
   file count plus the approved manifest path/hash;
2. partial successes and failures in original plan order;
3. remaining tracked and untracked changes, including approved local-only paths;
4. checks and their four-state outcomes, plus intentionally unrun checks;
5. effective local identity changes and approved exceptions;
6. remote names and actual network activity;
7. root/child Context state, child coverage, and Context action; and
8. remaining uncertainty and the smallest safe next action.
