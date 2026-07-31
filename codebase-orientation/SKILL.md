---
name: codebase-orientation
description: Build or refresh a reliable understanding of a codebase, component, or multi-repository workspace. Use when Codex needs to analyze a work path, active ProjectProfile selection, Git/GitHub provenance, Python runtime and PyCharm interpreter alignment, README freshness, entrypoints, tests, deprecated code, auxiliary references, reproducibility context, or current state after an authorized commit.
---

# Codebase Orientation

## Core Rule

Establish the exact code and configuration being understood before interpreting its logic. Start read-only. Do not run project entrypoints, tests, dependency installation, Git mutations, or documentation edits merely to orient the codebase.

Write reports and requested documentation in the user's language.

## 1. Identify the Scope

Treat the supplied path as one of the following:

- **Component**: a single repository or a versioned subproject.
- **Workspace**: a directory coordinating multiple components.
- **Auxiliary/reference path**: a dependency, historical version, dataset utility, vendor copy, or example supplied only for context.

Treat auxiliary paths as read-only unless the user explicitly authorizes changes. Do not deeply inspect deprecated versions, generated artifacts, caches, or vendored code unless the question depends on them.

## 2. Discover Profile and Git Context First

Before choosing Quick or Deep mode, search the supplied path and its ancestors for:

```text
profile/workspace.json
profile/component.json
active_profile.json
.git
third_party/lock-*.json
patches/third_party/
```

If a `profile/workspace.json` is present:

1. Read its component list and Active directory definition.
2. Resolve the current Active links or state record.
3. Treat selected Active components as the primary code to understand.
4. Treat sibling versions that are not selected as historical or candidate references.

If a `profile/component.json` is present, record its identity, version, logical runtime key, IDE roots, entrypoints, generated artifacts, and third-party roots. Do not assume a particular ProjectProfile schema or component name; report fields that are absent as unknown.

For every primary repository, collect read-only Git evidence: root, branch, HEAD, nearest tag or describe value, short status, and sanitized remote names/URLs when present. A dirty worktree means conclusions apply to the working tree rather than solely to a committed baseline.

When a profile or multi-repository workspace is found, read [references/project-profile-and-git.md](references/project-profile-and-git.md). Use `scripts/collect_orientation_context.py` when a deterministic JSON inventory will improve accuracy. The script uses only the Python standard library and read-only Git commands, so it may run with `conda run -n codex-tools` without confirming a project runtime.

## 3. Establish Reading Boundaries

Use profile and Git evidence to classify paths before reading source:

- **Active code**: selected component roots, declared source roots, entrypoints, and relevant tests.
- **Generated/ignored content**: Excluded folders, generated artifacts, logs, checkpoints, outputs, and caches. Confirm their purpose but do not inventory them.
- **Third-party/reference code**: declared vendor roots, submodules, external snapshots, and locked dependencies. Identify contribution and version state without deep code reading by default.
- **Historical/candidate versions**: non-Active sibling versions. Read only profile, Git, README, and a minimal structural summary unless explicitly requested.

`Excluded` affects IDE indexing only. `.gitignore` and Git status determine version-control state. Do not conflate either with Python runtime importability.

## 4. Verify Python and PyCharm Interpreter Alignment

Read logical runtime identifiers from Profile first. When a workspace maps environment keys to local paths, distinguish the portable logical key from the machine-local interpreter path.

For a PyCharm workspace, compare the following evidence in order:

1. `profile/workspace.json`: `default_environment_key` when explicitly declared, then `environment_templates`.
2. Every Active component `profile/component.json`: its `runtime.environment_key`.
3. PyCharm project SDK: `.idea/misc.xml` → `ProjectRootManager`.
4. PyCharm module SDK: the Active `.iml` → `NewModuleRootManager` → `orderEntry type="jdk"`.
5. Shared Run/Debug configurations: explicit SDK, module SDK, shell interpreter, and relevant runtime variables such as `ENV_ROOT` or `PYTHON_BIN`.
6. The local PyCharm SDK registry, when available, only to verify that an SDK name resolves to the expected executable.

Use `scripts/collect_orientation_context.py` to produce this comparison. Report each result as `aligned`, `mismatch`, `unverified`, `shared`, or `missing`; do not infer a missing Profile default from the current PyCharm setting.

The project SDK is only a fallback. A module SDK or an explicit Run/Debug interpreter may intentionally differ. Treat a difference as a mismatch only when it conflicts with the Profile environment declared for that module or configuration.

`codebase-orientation` is read-only: it verifies and reports alignment but never edits `.idea`, global PyCharm SDK records, or Profile files. When a correction is authorized, use the ProjectProfile synchronization workflow as the writer, then run this Skill again to verify the result.

Before running project scripts, tests, notebooks, or installing packages:

1. Report the recommended logical environment and supporting evidence.
2. Ask the user to confirm the actual Conda/interpreter environment if it is not explicitly known.
3. Use the confirmed environment only; never install into base, system Python, or an inferred environment.

Do not expose secrets from ignored local environment files, environment variables, remote URLs, or configuration files.

## 5. Refresh After an Authorized Commit

This skill remains read-only. When an authorized downstream workflow has just committed changes, start a fresh Quick Mode pass rather than relying on earlier Git state. Re-read the Profile/Active selection and collect the current branch, HEAD, tag/describe value, remaining dirty state, and third-party lock evidence.

Report the refreshed evidence as the current project understanding. Do not stage, commit, push, or write a persistent project journal from this skill; update project documentation only with separate user authorization.

## 6. Choose Analysis Depth

### Quick Understanding Mode

Use when the user asks to refresh context, resume work, inspect README freshness, or quickly identify the active project.

1. Read README, Profile/Git context, and Python/PyCharm alignment first.
2. Inspect current entrypoints, package metadata, top-level source, and relevant tests.
3. Compare README claims with current paths, Active selection, Git status, and entrypoints.
4. Report a compact code map, reproducibility context, stale documentation, and remaining uncertainty.

Do not perform a full file-by-file audit.

### Deep Analysis Mode

Use when the user asks to deeply analyze, review, summarize, or build global understanding before later work.

1. Complete Quick Mode context discovery, including Python/PyCharm alignment.
2. Inspect the active project tree using fast discovery such as `rg --files`.
3. Read documentation, package metadata, build scripts, configurations, entrypoints, representative source, and relevant tests.
4. Identify purpose, main technical idea, data/control flow, major modules, and external boundaries.
5. Separate active code, deprecated code, generated content, third-party/reference code, and historical versions with evidence.
6. Report the orientation before beginning downstream implementation.

## 7. Report Format

Include the following when evidence exists:

1. **Scope and reproducibility context**: workspace/component path, Active selection, profile path and version, Git branch/HEAD/tag/dirty state, logical runtime, entrypoints, and third-party lock state.
2. **Interpreter alignment**: Profile default/runtime key, project SDK, Active module SDKs, relevant Run/Debug overrides, registration evidence, and every mismatch or unverified field.
3. **Purpose and main workflow**: what the active code does and how major components interact.
4. **Active code map**: important folders/files and their responsibilities.
5. **Boundaries**: deprecated, generated, excluded, third-party, and read-only reference paths.
6. **Documentation assessment**: README facts verified, stale facts, and missing operational information.
7. **Readiness and uncertainty**: what can safely happen next, what needs environment confirmation, and what requires user direction.

Use absolute paths when they help disambiguate multiple versions. State whether a conclusion applies to the clean baseline or a dirty working tree.

## 8. Documentation and Safety Boundaries

- Default to reporting stale README facts; update README only when the user asks to edit documentation or explicitly authorizes the update.
- Preserve useful user-authored documentation when authorized to edit it.
- Do not switch branches, pull, push, commit, stage files, clean a worktree, update submodules, or modify third-party code during orientation.
- Do not start implementation or refactoring before delivering the requested orientation report.

## Final Self-Check

- Confirm scope and path roles.
- When present, confirm profile/Active selection, Git evidence, entrypoints, and third-party lock state.
- Confirm that Active, historical, generated, third-party, and auxiliary boundaries are separated.
- Confirm the runtime is only used after user confirmation for environment-dependent work.
- Confirm Profile runtime, PyCharm project/module SDKs, and relevant Run/Debug overrides were compared when available.
- Confirm no secrets or local-only absolute state are exposed.
- Confirm the user receives an evidence-backed orientation report before downstream work.
- After an authorized commit, confirm the report records new Git evidence and any intentionally remaining changes.
