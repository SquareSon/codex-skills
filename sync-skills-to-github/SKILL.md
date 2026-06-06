---
name: sync-skills-to-github
description: Ask before syncing local Codex skill changes to GitHub. Use whenever Codex creates, edits, updates, validates, or maintains skills under CODEX_HOME/skills or ~/.codex/skills, especially after using skill-creator, editing SKILL.md, changing agents/openai.yaml, adding skill scripts/references/assets, or otherwise modifying the local skills Git repository.
---

# Sync Skills To GitHub

## Overview

Use this skill as the final gate after local Codex skill changes. It keeps local skill maintenance separate from GitHub synchronization and asks the user before committing or pushing unless the user already explicitly requested synchronization in the same turn.

## Required Workflow

1. Finish the requested local skill creation or update first.
2. Identify the skill root:
   - Prefer `$CODEX_HOME/skills` when `CODEX_HOME` is set.
   - Otherwise use `~/.codex/skills`.
   - If the edited skill lives elsewhere, use the nearest intended skills directory.
3. Verify the Git repository boundary before using Git:
   - Run `git -C <skills-root> rev-parse --show-toplevel`.
   - The top-level must be the skills root itself.
   - If Git resolves to a parent directory such as the user's home directory, do not use that parent repository. Initialize or configure a dedicated skills repository only with user approval.
4. Inspect changes with `git -C <skills-root> status --short --branch`.
5. If there are no changes, tell the user no GitHub sync is needed.
6. If changes exist and the user did not already request a sync, ask a concise confirmation question before committing or pushing.

## Confirmation

Ask in plain language and include the remote when known:

```text
Local skill changes are ready. Should I commit and push them to GitHub remote <remote-url>?
```

If the remote is missing, ask whether to set one up rather than inventing a destination. For this user's current Windows setup, the expected remote is usually:

```text
https://github.com/SquareSon/codex-skills.git
```

Do not ask again when the user already explicitly requested sync, push, publish, or update GitHub in the same task. In that case, proceed after verifying scope.

## Approved Sync

When the user approves synchronization:

1. Review `git status --short` and stage only intended skill files.
2. Do not stage `.system/`, plugin caches, memories, sessions, `config.toml`, or unrelated files outside the skills repository.
3. Use a concise commit message, for example:

```bash
git -C <skills-root> add <changed-skill-paths>
git -C <skills-root> commit -m "Update Codex skills"
git -C <skills-root> push
```

4. If the commit has nothing to commit, skip the push and report that no sync was needed.
5. After pushing, verify with `git -C <skills-root> status --short --branch` and report the commit SHA.

## Declined Sync

If the user declines, leave local changes untouched. Report that the skill changes remain local and give the minimal commands they can run later:

```bash
git -C <skills-root> status
git -C <skills-root> add <paths>
git -C <skills-root> commit -m "Update Codex skills"
git -C <skills-root> push
```

## Safety Rules

- Never push skill changes without user approval unless the user explicitly requested sync in the same task.
- Never use a parent Git repository to track skills.
- Never include secrets, tokens, credentials, private keys, shell history, or full Codex sessions in the skills repository.
- Prefer a quick sensitive-content scan before the first push of a new skill or when adding scripts/assets from external sources.
