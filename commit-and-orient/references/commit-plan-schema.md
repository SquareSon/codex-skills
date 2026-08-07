# Commit plan manifest

Read this reference when a task spans multiple repositories, contains more than
20 explicit files, creates a repository's first commit, or needs approval bound
to the current working-tree contents.

## Candidate analysis before a draft

For a dirty tree with more than one possible concern, run `propose-plan` before
writing this manifest. Its JSON is a read-only, file-level analysis with
candidate groups, `bridge_paths`, and `unclassified_paths`.

```bash
conda run -n codex-tools python <skill-dir>/scripts/commit_scoped_changes.py \
  --mode propose-plan --repo <repository-root>
```

Do not copy a candidate into a draft automatically. Resolve every bridge path
first: assign the full file to one atomic commit, or merge the dependent
candidates. The current schema intentionally forbids a file in more than one
commit and does not support hunk-level automatic execution. Record the review
decision in the commit purpose or plan-side notes; only exact paths enter the
sealed manifest.

## Draft schema

Create a local-only UTF-8 JSON draft. A workspace `.planning/` directory is a
good location when it is already an approved non-commit path.

```json
{
  "schema": "commit-and-orient-plan/v2",
  "repositories": [
    {
      "repository": "/absolute/repository/root",
      "allow_unborn": false,
      "identity_policy": {"action": "require_existing"},
      "approved_remaining_paths": [".planning"]
    }
  ],
  "commits": [
    {
      "id": "runtime-fix",
      "repository": "/absolute/repository/root",
      "message": "fix(runtime): preserve sampled semantic authority",
      "paths": ["package/runtime.py", "tests/test_runtime.py"],
      "diff_check": "error",
      "validation": ["pytest tests/test_runtime.py"],
      "context_impact": "review"
    }
  ]
}
```

Rules:

- List files exactly. Directories and globs are invalid commit paths.
- A file may occur in only one commit in a sealed plan.
- `approved_remaining_paths` may be an exact path or a directory prefix; these
  paths remain local and are never staged by the plan.
- Use `diff_check: error` by default. `warn` requires a separately explained
  legacy-baseline exception.
- `context_impact` is `none`, `review`, or `refresh_planned`.
- Set `allow_unborn: true` only for an explicitly approved root commit.

For an approved repository-local identity, use:

```json
{
  "identity_policy": {
    "action": "set_repository_local",
    "name": "Approved Name",
    "email": "approved@example.com"
  }
}
```

Never put credentials, tokens, remote URLs containing credentials, or private
keys in the manifest.

## Seal and approve

Seal the draft without Git mutation:

```bash
conda run -n codex-tools python \
  <skill-dir>/scripts/commit_scoped_changes.py \
  --mode seal-plan --plan <draft.json> > <sealed.json>
```

The sealed envelope records repository branch/HEAD state, exact path contents,
permissions, identity policy, planned paths, and a canonical `plan_sha256`.
Show the commit table and this hash to the user. Approval applies only to that
hash.

Execute after approval:

```bash
conda run -n codex-tools python \
  <skill-dir>/scripts/commit_scoped_changes.py \
  --mode execute-plan --plan <sealed.json> \
  --approved-sha256 <approved-hash> --apply \
  --confirm I_CONFIRM_SCOPED_COMMIT
```

Add the following only when the sealed plan sets repository-local identity:

```text
--confirm-identity I_CONFIRM_REPOSITORY_LOCAL_IDENTITY
```

The executor validates all repository baselines before the first commit and
revalidates remaining path contents before each later commit. If a later commit
fails, it returns the completed commit records and does not roll them back.

## Small single commit

For one mature repository and a short exact file list, direct mode remains
available. Use `--path-file` when a reviewed newline-delimited list is clearer
than repeated `--path` options. Direct mode does not replace the plan-hash
approval barrier for complex or multi-repository work.
