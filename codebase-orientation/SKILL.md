---
name: codebase-orientation
description: Build task-routed, evidence-backed understanding of a codebase, component, or ProjectProfile workspace. Use when Codex needs to quickly or deeply understand active implementation, architecture, control/data flow, cross-component contracts, experiments, Git/runtime provenance, hierarchical AI_CONTEXT freshness, entrypoints, tests, boundaries, or reproducibility before downstream work.
---

# Codebase Orientation

Establish current selection and configuration before interpreting code. Start
read-only: do not run project entrypoints, tests, dependency installation, Git
mutations, or unrelated documentation edits merely to orient a project.

`AI_CONTEXT.json` is a verified attention map and compact semantic summary. It
prioritizes where understanding starts; it never narrows the source evidence
required for a conclusion, replaces implementation reading, or overrides
Active/Profile/Git/current source.

## Evidence and scope

Classify the supplied path as a component, ProjectProfile workspace, or
auxiliary/reference path. Resolve and use this order:

```text
Active selection > ProjectProfile > Git/current source > AI_CONTEXT.json
```

Before broad code reading, discover `profile/workspace.json`,
`profile/component.json`, `active_profile.json`, `.git`, third-party locks,
patches, root/child `docs/ai-guide/AI_CONTEXT.json`, and legacy
`PROJECT_GUIDE.md`.

For a workspace, resolve every declared Active link and treat selected targets as
primary code. Treat non-Active siblings as historical/candidate unless evidence
says otherwise. Collect read-only Git root, branch, HEAD, describe, short status,
and sanitized remotes for every primary repository. A dirty tree means results
apply to its working state.

For Profile workspaces, read
[references/project-profile-and-git.md](references/project-profile-and-git.md)
and run the deterministic inventory.

For an ordinary standalone repository without ProjectProfile, the inventory
uses the repository directory as one `relative` component and discovers its
local `docs/ai-guide/AI_CONTEXT.json` without inventing Profile or Active state.

For a concrete task, prefer the temporary Bundle because it selects
task-relevant components, routes, contracts, semantic nodes, and classification
diagnostics without copying the entire Context tree:

```bash
conda run -n codex-tools python \
  /home/square/.codex/skills/codebase-orientation/scripts/collect_orientation_context.py \
  --path <workspace-or-component>

conda run -n codex-tools python \
  /home/square/.codex/skills/codebase-orientation/scripts/build_orientation_bundle.py \
  --path <workspace-or-component> --intent "<current task>" \
  [--component <active-key>]
```

The Bundle is ephemeral machine input, not a project artifact. Its default
32 KiB budget is independent from persistent Context node budgets. It never
replaces source expansion or authorizes writes.

## Hierarchical AI Context

For a workspace, locate the workspace Context plus the Context in every
resolved Active component. For a component request, locate its local Context and
its enclosing workspace Context when a Profile reveals one.

1. Validate each `ai-project-context/v3` or `v4` node with
   `ai-project-guide/scripts/validate_ai_context.py` before using it.
2. Classify each local node as `valid`, `partially_stale`, `stale_profile`,
   `stale_active`, `stale_anchor`, `needs_deep_refresh`, `invalid_schema`, or
   `missing`. For v4, report stale semantic node IDs and affected routes,
   contracts, tests, experiments, or paper claims instead of invalidating the
   whole file when evidence permits a local result.
3. Report workspace child coverage independently as `complete`, `partial`, or
   `missing`. A valid root never makes a missing child valid.
4. For a global task, read the root summary and all relevant Active child
   summaries before source analysis. For a component task, read its child
   summary and the root only for cross-component topology and contracts.
5. Use an attention route only as the first investigation pass. Expand source
   reading according to the route and the actual code evidence. Generated,
   third-party, historical, and auxiliary boundaries are default priorities, not
   prohibitions.
6. Treat v2 or legacy Markdown guides as migration evidence only. Report them;
   never auto-convert, rewrite, or use them as current authority.

Read [the Context contract](../ai-project-guide/references/ai-context-schema.md)
when a Context tree exists, is stale, or must be evaluated.

## Task routing and evidence completion

Resolve task intent before broad source reading. Use explicit component keys
when supplied; otherwise select components from the highest-scoring root task
route. A global or unmatched task may start from all Active component summaries,
but Deep analysis still expands only where the question requires evidence.

For a v4 route, follow `attention_refs`, `semantic_nodes`, and `contract_ids`,
then inspect every `required_evidence` item. Completion requires
`all_required_evidence_or_explicit_gap`: either verify all required evidence or
name every missing/unreadable item and limit the conclusion. Enforce
`do_not_assume`, especially:

- implementation does not prove configuration;
- configuration does not prove execution;
- execution does not prove a reported paper claim;
- a generated or ignored path is not automatically irrelevant evidence.

## Understanding depth

Select one depth based on the request; do not let Context reduce the required
depth.

### Quick

Use for resuming work, identifying active code, checking Context/Git/runtime
state, or deciding where to continue reading.

1. Collect Profile/Active/Git/runtime inventory and Context tree status.
2. Read root/child summaries and attention anchors relevant to the request.
3. Verify selected entrypoints, package metadata, key configuration, and enough
   nearby code to reject stale or contradictory Context claims.
4. Report active topology, attention starting points, Context state, boundaries,
   interpreter alignment, and uncertainty.

Quick is not a file-by-file audit and never writes Context.

### Deep

Use for global understanding, architecture analysis, code review, research
interpretation, or before substantial modifications. Complete Quick discovery,
then build a source-evidenced model of the active implementation.

For every task-relevant active component, do all applicable work below:

1. Map package/module responsibilities from source layout, metadata, imports,
   registries, configuration, and explicit entrypoints.
2. Trace each relevant entrypoint through callers, callees, factories,
   configuration resolution, mode branches, error/edge handling, and externally
   visible outputs.
3. Trace data contracts end-to-end: producer, source/annotation/input format,
   serialized artifact or in-memory schema, consumer, transforms,
   shapes or schemas, persisted artifacts, model or algorithm boundaries,
   validator/test evidence, evaluation/export consumers, and failure-sensitive
   assumptions.
4. Read tests, fixtures, validation scripts, and representative experiments as
   independent behavioral evidence; do not infer behavior solely from names or
   README text.
5. Resolve cross-component interfaces in both directions: producer, serialized
   or in-memory contract, consumer, configuration handoff, and version/runtime
   assumptions.
6. Use Context attention anchors to begin, then expand into every source path
   needed to explain the actual control/data flow. Stop only when the requested
   conclusion has direct evidence and remaining gaps are explicit.

Do not mechanically read every file. Do not claim global understanding from
entrypoints alone. Prefer a coherent, source-cited semantic model over a broad
directory listing.

## Context policy

Apply one explicit Context policy independently from Quick/Deep depth:

| Policy | Read | Write | Required use |
| --- | --- | --- | --- |
| `read_only` | Validate and use Context | Never | Default; Quick; post-commit checks |
| `inspect_only` | Deeply validate Context and source | Never | Invoked by `$ai-project-guide` before tree creation/migration |
| `refresh_existing` | Deeply validate Context and source | Refresh current valid existing nodes only | Explicit request to maintain existing Context |

`refresh_existing` cannot create a missing root/child, migrate v2, alter
`AGENTS.md`, or touch an auxiliary/historical/third-party target. Use
`$ai-project-guide` for creation, migration, restructuring, or a full tree
refresh. Never begin a nested Context write when `$ai-project-guide` invoked
Deep `inspect_only`.

## Boundaries and runtime

Prefer Profile `path_policy`; resolve overlaps by the most-specific path and then
by authority. Standard categories are `core`, `contract`, `entrypoint`,
`experiment`, `test`, `evidence`, `maintained_dependency`, `third_party`,
`reference`, `historical`, `generated_evidence`, `generated_ephemeral`,
`local_only`, and `auxiliary`. When only legacy Profile fields exist, use them as
provisional claims and report Context/Profile/`.gitignore` drift rather than
silently choosing one. `Excluded` controls IDE indexing only; `.gitignore`
controls ordinary Git discovery; neither changes imports or semantic relevance.

Read Python runtime evidence in this order: workspace Profile default/template,
component runtime key, project SDK, module SDK, shared Run/Debug overrides, then
local PyCharm SDK registry. Report `aligned`, `mismatch`, `unverified`,
`shared`, or `missing`. Request actual interpreter confirmation before running
project code when it is not explicitly known. Never infer an environment or
install into base/system Python.

## After an authorized commit

Run Quick + `read_only` for every committed workspace/component. Recheck
Active/Profile/Git/runtime and root/child Context status. Report whether changed
files could alter an entrypoint, route, component role, data/control contract,
boundary, or anchor; recommend `$ai-project-guide` only when a new Deep evidence
pass is warranted. Do not write Context merely because a commit occurred.

## Report contract

Report: scope and reproducibility evidence; selected task route and components;
Context tree/node state and child coverage; stale semantic nodes and downstream
impact; source-evidenced purpose, architecture, control/data flows, concepts,
and producer→artifact→consumer→validator/test contracts; active code
responsibilities and classification drift; interpreter alignment; required
evidence checked, explicit gaps, `do_not_assume` constraints, source expansion,
confidence, and safe next actions. Use absolute paths only to disambiguate
versioned locations. Do not expose secrets.
