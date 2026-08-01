# Codex Skills

This repository stores personal Codex skills that should be shared across devices.

It is intended to be checked out as the `skills` directory under `CODEX_HOME`:

```powershell
%USERPROFILE%\.codex\skills
```

On this Windows setup, `CODEX_HOME` should point to the `.codex` root, not the
`skills` directory:

```powershell
[Environment]::SetEnvironmentVariable("CODEX_HOME", "$env:USERPROFILE\.codex", "User")
```

Restart Codex after changing `CODEX_HOME`.

## What This Repo Contains

Tracked custom skills:

- Project understanding and maintenance: `ai-project-guide`,
  `codebase-orientation`, `commit-and-orient`, `find-skills`,
  `planning-with-files`, and `sync-skills-to-github`.
- Writing and document work: `academic-paper-writing`, `humanizer`,
  `humanizer-zh`, `pdf`, and `python-code-style`.
- Visual and browser workflows: `artifact-template-sjtu`, `hatch-pet`, and
  `playwright`.

Not tracked:

- `.system/`: system-provided skills
- plugin caches
- Codex sessions
- memories
- `config.toml`
- machine-specific local settings

Those files are local runtime state and should not be synced through this repo.

## Install On A New Device

If the new device does not already have a `skills` directory:

```powershell
mkdir $env:USERPROFILE\.codex -Force
cd $env:USERPROFILE\.codex
git clone https://github.com/SquareSon/codex-skills.git skills
```

Then set `CODEX_HOME` if needed:

```powershell
[Environment]::SetEnvironmentVariable("CODEX_HOME", "$env:USERPROFILE\.codex", "User")
```

Restart Codex so it can rescan the skills.

## Install When `skills` Already Exists

If `%USERPROFILE%\.codex\skills` already exists, do not overwrite it directly.
Back it up or inspect it first.

One conservative workflow:

```powershell
cd $env:USERPROFILE\.codex\skills
git init
git remote add origin https://github.com/SquareSon/codex-skills.git
git fetch origin
git checkout -t origin/main
```

If Git reports conflicts or untracked files with the same names, resolve those
manually before continuing.

## Daily Update Workflow

Pull updates from GitHub:

```powershell
cd $env:USERPROFILE\.codex\skills
git pull
```

After editing or adding a skill:

```powershell
cd $env:USERPROFILE\.codex\skills
git status
git add <changed-skill-paths>
git commit -m "Update Codex skills"
git push
```

The `sync-skills-to-github` skill is intended to make Codex ask before committing
and pushing local skill changes.

## Creating Or Updating A Skill

Use Codex's `skill-creator` workflow when creating a new skill. A normal skill
has this shape:

```text
skill-name/
  SKILL.md
  agents/
    openai.yaml
  scripts/      optional
  references/   optional
  assets/       optional
```

Before committing, validate changed skills when practical:

```powershell
python $env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\quick_validate.py $env:USERPROFILE\.codex\skills\<skill-name>
```

`humanizer` and `planning-with-files` retain upstream Claude-oriented
frontmatter. Their scripts and package files are versioned here, but the strict
Codex validator currently reports the upstream-only metadata keys.

On this Windows machine, keep `SKILL.md` content ASCII-only unless non-ASCII is
necessary. Some local validation paths can read files with a non-UTF-8 default
encoding.

## Safety Checklist Before Push

Before pushing, check:

```powershell
git status --short --branch
```

Do not commit:

- secrets, tokens, API keys, private keys, or passwords
- `.system/`
- `.codex` plugin cache
- Codex sessions or memories
- machine-specific `config.toml`
- unrelated files outside this skills repository

For first-time pushes of a new skill, a quick scan is useful:

```powershell
rg -n -i "(api[_-]?key|secret|password|token|github_pat|ghp_|sk-|BEGIN (RSA|OPENSSH|PRIVATE) KEY)" .
```

## Troubleshooting

If Git appears to scan the whole user directory, verify the repository boundary:

```powershell
git rev-parse --show-toplevel
```

The result should be:

```text
C:/Users/square/.codex/skills
```

If it points to a parent directory such as `C:/Users/square`, stop and fix the
repository setup before staging files.

If `git push` asks for authentication, sign in with the GitHub account
`SquareSon`.
