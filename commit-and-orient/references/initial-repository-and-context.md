# Initial repositories and Context coordination

Read this reference for an unborn Git repository, a repository-local identity
exception, legacy whitespace, or an explicitly requested AI Context refresh.

## Initial repository policy

Inventory reports an unborn repository with `head: null`, its symbolic branch,
and effective identity. Before the first commit:

1. confirm that the repository root is intentional;
2. inspect all untracked files, oversized binaries, likely credentials, nested
   Git roots, generated outputs, and local environment files;
3. use exact files or a sealed manifest, never a directory staging shortcut;
4. require `allow_unborn: true` in the approved plan;
5. require a valid existing identity or an explicit repository-local identity
   policy; and
6. record `before_head: null` and the new root-commit SHA.

Do not initialize a repository, invent an identity, modify global Git config,
or treat “commit everything” as approval for a first commit.

## Whitespace exception

`git diff --cached --check` is strict by default and runs in a temporary index
before the real index is touched. For a legacy root baseline whose existing
line endings cause broad findings:

1. summarize issue count and the first 20 diagnostic lines;
2. explain whether the warnings are CRLF/trailing-space legacy content rather
   than newly introduced source edits;
3. ask for an explicit `diff_check: warn` exception in the commit plan; and
4. avoid formatting or normalizing the baseline merely to silence the check
   unless the user separately authorizes that change.

## Two-phase Context workflow

Use one of these paths:

- `none`: committed paths do not affect Context claims or routing.
- `review`: finish source/Profile commits, then run Quick + `read_only`; propose
  a later Context update only when evidence shows impact.
- `refresh_planned`: the user explicitly requested Context maintenance. Run
  `$codebase-orientation` Deep + `inspect_only`, then `$ai-project-guide`, write
  and validate the actual v4 Context diff, and obtain approval for that exact
  diff before its separate commit.

Do not let approval of an unknown future Context file stand in for approval of
its actual generated content. After Context commits, finish with Quick +
`read_only` across the workspace and affected components.

For a large workspace, collect orientation once at the root and build one
intent-specific Bundle per affected component. If a global Bundle reports
`over_budget=true`, narrow it; this is not a Context validation failure.
