# ProjectProfile, Git, and Hierarchical AI Context Evidence

Read this reference only for a ProjectProfile-style `profile/` directory, an
Active workspace, or multiple related Git repositories.

## Evidence hierarchy

Use evidence in this exact order:

1. Active links and resolved filesystem targets describe what can run now.
2. `profile/workspace.json` declares components, Active names, and shared runtime templates.
3. `profile/component.json` declares portable identity, logical runtime, IDE roots,
   entrypoints, artifacts, and—when available—`path_policy`.
4. Git commit/tag/branch and dirty state describe exact code provenance.
5. Third-party locks and saved patches describe dependency provenance.
6. `docs/ai-guide/AI_CONTEXT.json` is an evidence-backed attention map and summary.

Do not treat `.idea`, `active_profile.json`, logs, checkpoints, or local
environment overrides as portable source of truth. They can corroborate the
current machine state only.

## Workspace and component interpretation

For a workspace Profile, inspect each declared component key at the Profile's
Active path. Record both stable Active path and resolved physical target. A
missing/broken link or Profile/key disagreement is `unresolved`, never a reason
to guess a version.

Non-Active siblings are historical or candidate versions until evidence says
otherwise. Profile component fields may evolve, but record available
identity/version, logical runtime key, source/test/resource roots, excluded and
generated folders, entrypoints, third-party roots, and path rules. `Excluded`
affects IDE indexing only; it does not alter imports or Git tracking.

## Path policy and drift

Prefer a Profile `path_policy.rules` array containing relative `path`, standard
`category`, and an optional short `reason`. Resolve rules using the most-specific
path first; when specificity ties, Profile outranks Context. Standard categories:

```text
core | contract | entrypoint | experiment | test | evidence |
maintained_dependency | third_party | reference | historical |
generated_evidence | generated_ephemeral | local_only | auxiliary
```

The distinction between `generated_evidence` and `generated_ephemeral` is
mandatory for research repositories: stable manifests, metric summaries, and
paper-bound tables remain discoverable; logs, caches, checkpoints, and temporary
renders remain low priority. A category is task-relative: `auxiliary` for model
training may be `core` for Profile maintenance.

When `path_policy` is absent, the collector converts legacy Profile fields into
provisional claims and compares them with Context boundaries and `.gitignore`
re-inclusion rules. Treat `classification_conflict`, unresolved
`classification_overlap`, and `boundary_covers_gitignore_exception` as evidence
gaps. Do not infer that a negated `.gitignore` pattern proves maintained code; it
only proves that a broad ignore/boundary rule needs review.

## Git evidence

Collect facts without mutation:

```bash
git -C <root> rev-parse --show-toplevel
git -C <root> branch --show-current
git -C <root> rev-parse HEAD
git -C <root> describe --tags --always --dirty
git -C <root> status --short
git -C <root> remote -v
```

Remote metadata establishes only an optional GitHub/GitLab relation. Do not
contact remotes, pull, push, or infer ownership during orientation. Sanitize
embedded credentials. If `status --short` is non-empty, distinguish the
committed baseline from working-tree conclusions.

When `third_party/lock-*.json` exists, report the selected lock snapshot and
matching `patches/third_party/` state. Treat vendor code as read-only unless the
task is explicitly about that dependency.

## Python and PyCharm alignment

Interpret runtime configuration in layers:

1. Workspace `default_environment_key` is the project fallback.
2. Component `runtime.environment_key` is the module requirement.
3. `environment_templates` maps logical keys to local `python_bin` or root.
4. `.idea/misc.xml` holds project SDK; Active `.iml` files hold module SDKs.
5. Run/Debug configuration may intentionally override either SDK.

Report a missing Profile default as `missing` even when PyCharm has a project
SDK. Verify SDK names against Profile templates and local registry only as
machine-local corroboration. Orientation never edits `.idea`, the registry, or
Profile; ProjectProfile synchronization is the authorized writer.

## Hierarchical AI context freshness

For a workspace, evaluate the root Context and one leaf Context for every Active
component. For an individual component, evaluate its local leaf and enclosing
root when current Profile reveals one. Context prioritizes first attention; it
does not whitelist source paths or replace a Deep implementation trace.

Validate each v3/v4 node before use. Compare its `profile_fingerprint` and
`active_fingerprint` with the deterministic inventory before source browsing. In
a Deep pass, compare v3 anchor hashes or v4 semantic evidence hashes after
reading source. Each node result is one of:

```text
valid | partially_stale | stale_profile | stale_active | stale_anchor |
needs_deep_refresh | invalid_schema | missing
```

For v4, `partially_stale` names the semantic node IDs whose evidence changed and
the task routes, contracts, experiments, tests, or paper claims that depend on
them. Unaffected semantic nodes remain usable. A Profile/Active fingerprint
mismatch still requires topology reorientation before local semantic reuse.

Also report workspace child coverage as `complete`, `partial`, or `missing`.
The fingerprints deliberately omit Git HEAD and dirty state so normal commits
do not cause context churn. A mismatch signals reorientation, not an IDE or Git
configuration error.

## Intent-specific Bundle

Use `build_orientation_bundle.py` after inventory collection when the task is
known. The script selects explicit components first, otherwise uses the best
root task route, and emits only compact reproducibility facts, matched routes,
required evidence, referenced semantic nodes/contracts, `do_not_assume`, and
classification diagnostics. The output is ephemeral stdout with a 32 KiB
default budget. If a section is removed to fit, `truncated_sections` records it;
`over_budget=true` requires a narrower component/intent selection.

The Bundle is an attention packet, never a source whitelist. Continue into
current source until all route-required evidence is verified or each gap is
explicitly reported.

## Compact reproducibility summary

```text
Component: <key> → <resolved path>
Profile: <path>, version <version>
Git: <branch> @ <short HEAD>, <tag/describe>, clean|dirty
Runtime: <logical environment key>; actual interpreter <confirmed|unconfirmed>
Entrypoints: <relevant names>
Third party: <latest lock or none>
AI context: <state>
```
