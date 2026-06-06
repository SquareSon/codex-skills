---
name: codebase-orientation
description: Build or refresh a global understanding of a codebase from a user-provided work path and optional auxiliary/reference paths. Use when the user asks Codex to analyze a code path, understand a project before working, quickly understand from README.md, inspect whether README.md is outdated, distinguish active code from deprecated old code, treat auxiliary paths as read-only references, or confirm the Python conda environment before dependency work.
---

# Codebase Orientation

## Core Idea

Use this skill when the user provides a code work path and optional auxiliary paths. First decide whether the user wants deep analysis or quick understanding, then build a reliable project mental model before doing downstream work.

Write reports and generated `README.md` content in the user's language unless they request otherwise.

## Path Roles

- Treat the work path as the primary project to understand and the place where `README.md` should be created or updated.
- Treat auxiliary paths as read-only reference paths by default. Read them to understand related designs, examples, APIs, or historical context, but do not modify them unless the user explicitly allows it.
- Do not modify deprecated old code unless the user explicitly asks to work on it.
- When a path role is ambiguous, infer conservatively from the user's wording and state the assumption briefly.

## Conda Environment

- When the project uses Python and the user has not explicitly named the current conda environment, ask the user to confirm which conda environment to use before installing Python packages or libraries.
- After the user confirms the conda environment, perform all Python package and library installation for that project inside the confirmed environment.
- Prefer environment-specific commands such as `conda run -n <env> python -m pip install ...` or activating the confirmed environment before installation.
- Do not install Python dependencies into base, the system Python, or an inferred environment unless the user explicitly approves it.
- If a repository file such as `environment.yml`, `conda.yml`, `requirements.txt`, or project documentation suggests an environment, mention it as evidence but still ask for confirmation when the user has not named the environment.

## Mode Selection

- Use Deep Analysis Mode when the user says they want to analyze, review, inspect, summarize, build a global understanding, or first understand a path before doing later work.
- Use Quick Understanding Mode when the user says they want to quickly understand, refresh context, resume work, or read the existing `README.md`.
- If both modes are implied, start with Quick Understanding Mode only when a useful `README.md` already exists in the work path; otherwise use Deep Analysis Mode.

## Deep Analysis Mode

Perform a broad but targeted codebase survey before starting downstream implementation.

1. Inspect the work path structure with fast file discovery such as `rg --files`.
2. Read existing project documentation, configuration, package metadata, build scripts, entrypoints, and representative source files.
3. Identify the project's core purpose and main technical idea.
4. Identify how the main files and modules jointly form the primary logic.
5. Summarize each important code file's task, responsibility, and relationship to the rest of the project.
6. Identify deprecated or abandoned old code. Use evidence such as directory names, filenames, comments, import absence, duplicate older implementations, backup/archive markers, and user-provided hints.
7. Identify read-only reference code, especially code under auxiliary paths or work-path folders that are clearly examples, references, vendor copies, or external snapshots.
8. Create or update `README.md` in the work path with the distilled understanding.
9. Report the global understanding to the user before continuing to later work.

Do not analyze deprecated old code deeply. Mention it as excluded, with the evidence for exclusion. Analyze read-only reference code only enough to understand what it contributes.

## Quick Understanding Mode

Use the existing `README.md` as the first source of truth, then verify it against the current code.

1. Read `README.md` from the work path first.
2. Inspect the current file tree and key files that README claims are important.
3. Check whether the README appears stale by comparing it with current entrypoints, major modules, config files, dependency files, and obvious renamed or removed files.
4. Read enough current code to verify the core purpose, main logic, active modules, deprecated code boundaries, and read-only reference boundaries.
5. Report a compact refreshed understanding to the user.
6. If the README is stale, clearly state what is outdated. Update it only when the user asks, or when the stale facts are straightforward and the user has not restricted edits.

Keep Quick Understanding Mode fast. Do not perform a full file-by-file audit unless the README is missing, very stale, or the user requests deeper analysis.

## README.md Content

When creating or updating the work-path `README.md`, include these sections unless a local README structure already exists and should be preserved:

- Project Purpose: the project's core goal and main idea.
- Main Workflow: how the code pieces work together end to end.
- Active Code Map: important files or folders and each one's task.
- Deprecated Or Ignored Code: old code that should not be changed or analyzed by default, with evidence.
- Read-Only Reference Code: auxiliary or reference paths that should be read but not edited.
- How To Resume Quickly: the shortest path for a future agent to re-understand the project.

Keep the README concise but specific. Prefer dense, practical orientation notes over generic project marketing text.

## Boundaries

- Do not start implementation or refactoring before reporting the orientation when the user requested analysis first.
- Preserve existing useful README content when updating; reorganize only enough to make future understanding faster.
- Do not overwrite user-authored project documentation blindly. Merge, update, or add an orientation section when a README already exists.
- Mark uncertainty explicitly when code evidence is incomplete.
- Prefer absolute paths in reports when distinguishing work and auxiliary paths.

## Final Self-Check

- Confirm the work path and auxiliary paths are identified.
- Confirm the conda environment is known before any Python dependency installation; if unknown, ask the user first.
- Confirm active code, deprecated old code, and read-only reference code are separated.
- Confirm the core purpose, main logic, and important file responsibilities are summarized.
- Confirm `README.md` exists or the reason for not writing it is stated.
- Confirm the user receives the orientation report before downstream work begins.
