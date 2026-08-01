---
name: ai-project-guide
description: Create, migrate, refresh, or validate a compact task-routed AI_CONTEXT.json semantic tree and experiment provenance for a codebase or ProjectProfile workspace. Use when Codex needs durable evidence-backed summaries, cross-component contracts, task routes, semantic freshness, or attention maps so later agents can orient quickly without treating Context as source truth or a code-reading limit.
---

# AI Project Context

Maintain machine-first semantic context. Context is an attention prior and
compact verified summary; it is never source of truth, a session log, a human
handoff, or a whitelist of code that may be read.

Read [the v4 contract](references/ai-context-schema.md) before creating,
migrating, or restructuring a Context tree. Use
[assets/AI_CONTEXT.template.json](assets/AI_CONTEXT.template.json) only as the
starting structure.

## Ownership and tree construction

For a standalone component, maintain one file:

```text
<component-root>/docs/ai-guide/AI_CONTEXT.json
```

A standalone repository without ProjectProfile uses a `relative` component
locator, `profile_ref: null`, null Profile/Active refresh fingerprints, and
`boundaries.policy_source: repository.layout`. Do not invent a Profile merely
to satisfy Context metadata.

For a ProjectProfile workspace, maintain the root and one component leaf for
every current Active component:

```text
<workspace-root>/docs/ai-guide/AI_CONTEXT.json
<resolved-active-component-root>/docs/ai-guide/AI_CONTEXT.json
```

Write the root to the workspace repository. Resolve each Active link, then write
the child Context to its physical selected component repository; it therefore
copies, versions, and commits with that component. Never write a child Context
to an unselected sibling, auxiliary project, generated directory, or third-party
tree. The root names all Active child Contexts; children contain no fragile path
back to the root.

The root owns project purpose, active topology, cross-component contracts, and
cross-component key flows. A child owns internal architecture, data/control
flows, local entrypoints, runtime attention, tests, and boundaries. Do not
duplicate child implementation detail in the root.

When one component cannot remain compact without hiding independent subsystems,
the component leaf may reference semantic shard Contexts. A shard owns one
coherent subsystem and has no children. Prefer task routing and reference
deduplication before creating shards.

## Evidence workflow

1. Invoke `$codebase-orientation` in **Deep + inspect_only** policy before any
   Context write. It must inspect code, call paths, configurations, data
   contracts, tests, and cross-component interfaces without refreshing Context.
2. Resolve workspace/profile/Active selection. Use `Active > Profile >
   Git/current source > Context`; Context can prioritize attention but never
   override evidence.
3. Read existing root, child, and shard Contexts, then collect stable
   Profile/Active fingerprints, path-classification diagnostics, and evidence
   candidates with `collect_orientation_context.py`.
4. For each Context node, populate a deduplicated `reference_catalog`, concise
   summary, task routes, semantic nodes, structured contracts, component
   metadata, Profile-owned boundaries, `do_not_assume`, and semantic evidence
   fingerprints. Every high-leverage claim has source evidence and confidence.
5. Treat `task_routes.attention_refs` as an initial reading order. Its `expand`
   directions require following relevant callers, callees, configuration,
   data contracts, tests, and interfaces until the task has sufficient source
   evidence. Do not turn boundary or attention fields into a reading prohibition.
6. Require `all_required_evidence_or_explicit_gap` for each route. Link routes to
   semantic node and contract IDs; never infer configured/executed/reported
   experiment states from implementation alone.
7. Create or refresh all required tree nodes in one explicit operation. Preserve
   still-evidenced fields; remove stale claims instead of inventing replacements.

## Schema and validation

Create `ai-project-context/v4`. The validator continues to accept v3 as a
read-only migration source. Validate every root, child, and shard after writing:

```bash
conda run -n codex-tools python \
  /home/square/.codex/skills/ai-project-guide/scripts/validate_ai_context.py \
  --path <context-path>
```

Use a 16 KiB hard limit for roots, ordinary leaves, and shards. A component leaf
that explicitly owns semantic shards may use up to 24 KiB; first target 8–12 KiB
through reference IDs and concise claims. Temporary orientation Bundles use a
separate 32 KiB default budget. Exclude timestamps, Git HEAD/dirty snapshots,
absolute paths, credentials, logs, model outputs, broad dependency dumps, and
speculative relationships.

Treat v2, v3, and legacy Markdown as read-only migration inputs. Rebuild a
verified v4 tree under this explicitly invoked Skill; never auto-migrate during
orientation or delete an old file without separate authorization. Do not inject
v4 fields into a file that still declares v3.

## Path policy and experiment provenance

Prefer ProjectProfile `path_policy` as the durable path classification source.
Context `boundaries.overrides` stores only evidenced semantic exceptions and a
reason; it must not duplicate the full Profile classification. Resolve overlaps
by most-specific path and then Profile authority. Distinguish stable
`generated_evidence` from disposable `generated_ephemeral`.

For a standalone repository without ProjectProfile, use `repository.layout` as
the boundary source and keep overrides equally evidence-based and minimal.

When experiment claims matter, create one stable
`docs/ai-guide/EXPERIMENT_PROVENANCE.json` per owning component from
[the provenance template](assets/EXPERIMENT_PROVENANCE.template.json). Record
`implemented`, `configured`, `executed`, and `reported` independently as
`confirmed`, `missing`, or `unknown`, with stable evidence references and
limitations. Validate it with:

```bash
conda run -n codex-tools python \
  /home/square/.codex/skills/ai-project-guide/scripts/validate_experiment_provenance.py \
  --path <provenance-path>
```

Reference the file from `AI_CONTEXT.json`; do not copy logs, checkpoints, model
outputs, or narrative experiment history into Context.

## Freshness and write authority

Each node has a local status: `valid`, `partially_stale`, `stale_profile`,
`stale_active`, `stale_anchor`, `needs_deep_refresh`, `invalid_schema`, or
`missing`. v4 semantic fingerprints allow changed evidence to invalidate only
affected semantic nodes and their downstream routes/contracts/claims. A
workspace also reports child coverage separately: `complete`, `partial`, or
`missing`.

- `$codebase-orientation` Quick and Deep `read_only` modes do not write Context.
- Deep `inspect_only` is the required evidence pass for this Skill and does not
  write Context.
- Deep `refresh_existing` may refresh only a valid existing node after material
  source understanding. It never creates a missing root or child.
- This Skill has authority to create, migrate, split, or explicitly refresh the
  full tree after evidence collection and validation.

## Optional discovery pointer

Only on explicit request, add a concise delimited pointer in the relevant root
`AGENTS.md`. Preserve all existing instructions. State that Profile/Active and
current source outrank Context.

## Completion report

Report root/child/shard and provenance paths, local and semantic-node statuses,
child coverage, selected routes/contracts, classification conflicts, validation
results, evidence gaps, migration inputs, and changed repositories. Do not
report Context as a substitute for `$codebase-orientation` before
environment-sensitive work or implementation.
