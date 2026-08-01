# AI Context v4 Contract

`AI_CONTEXT.json` is an evidence-backed semantic graph and task attention map.
It accelerates initial understanding; it never limits source investigation or
overrides Active selection, ProjectProfile, Git, or current source.

## Contents

1. Authority and ownership
2. Required fields
3. Reference catalog and components
4. Task routes and evidence gates
5. Contracts and semantic nodes
6. Boundaries and experiments
7. Hierarchy, freshness, and size
8. Migration and validation

## Authority and ownership

```text
Active selection > ProjectProfile > Git/current source > AI_CONTEXT.json
```

For a ProjectProfile workspace, maintain a root and one leaf for every resolved
Active component. A complex component may add semantic shards:

```text
<workspace>/docs/ai-guide/AI_CONTEXT.json
<active-component>/docs/ai-guide/AI_CONTEXT.json
<active-component>/docs/ai-guide/<subsystem>.AI_CONTEXT.json
```

The root owns active topology, cross-component key flows and contracts. A leaf
owns component internals, routes, tests, experiments and local boundaries. A
shard owns one coherent subsystem and has no children. Never duplicate leaf
implementation detail in the root or encode upward/absolute paths.

## Required fields

```text
schema, scope, authority_order, reference_catalog, summary, hierarchy,
bootstrap, components, task_routes, contracts, semantic_nodes,
experiment_provenance, do_not_assume, boundaries, refresh
```

- `schema`: exactly `ai-project-context/v4`.
- `scope`: `workspace`, `component`, or `shard`.
- `authority_order`: exactly `active, profile, git, source, context`.
- `summary`: `purpose`, concise `architecture`, and `key_flows`.
- `do_not_assume`: explicit inference prohibitions relevant to this node.

Use lowercase stable IDs matching `[a-z0-9][a-z0-9._-]*`. Keep statements
short, source-evidenced, and explicitly confident as `confirmed`, `inferred`, or
`unknown`.

## Reference catalog and components

Store each portable path once:

```json
"reference_catalog": {
  "workspace.profile": {"scope": "workspace", "path": "profile/workspace.json"},
  "nerf.train": {
    "scope": "component",
    "component": "nerf",
    "path": "scripts/train.py"
  }
}
```

Paths are relative, cannot traverse upward, and never contain local absolute
state. Every reference ID used elsewhere must exist in the catalog.

Each component contains exactly:

```text
id, role, locator, profile_ref, runtime_key, source_refs, entrypoint_refs
```

Use an Active or standalone locator:

```json
{"kind": "active_component", "key": "nerf"}
{"kind": "relative", "path": "."}
```

Component-scoped profile/source/entrypoint references must point to that same
component. `bootstrap.read_before_code` is a reference-ID array;
`bootstrap.active_components` contains each node-owned Active component once.

## Task routes and evidence gates

Each route contains exactly:

```text
id, intent, components, attention_refs, expand, semantic_nodes, contract_ids,
required_evidence, completion_rule
```

Example:

```json
{
  "id": "thyroid-to-nerf",
  "intent": "trace segmentation artifacts into NeRF training",
  "components": ["thyroid", "nerf"],
  "attention_refs": ["thyroid.export", "nerf.train"],
  "expand": ["callees", "configuration", "data_contracts", "tests", "interfaces"],
  "semantic_nodes": ["segmentation.export-flow", "nerf.mask-consumption"],
  "contract_ids": ["segmentation-mask"],
  "required_evidence": ["thyroid.manifest", "nerf.contract-test"],
  "completion_rule": "all_required_evidence_or_explicit_gap"
}
```

Allowed expansion directions are `callers`, `callees`, `configuration`,
`data_contracts`, `tests`, and `interfaces`. Attention references are starting
points, never a whitelist. Completion requires verifying every
`required_evidence` item or explicitly naming the gap and limiting the claim.

## Contracts and semantic nodes

Cross-component contracts encode the complete handoff:

```text
id, summary, producer_refs, artifact_refs, consumer_refs, validator_refs,
test_refs, confidence
```

Producer, artifact/schema, and consumer references are mandatory. Validator and
test lists may be empty only when the missing evidence is explicit in the task
route/report. Do not replace a contract with a prose-only flow description.

Semantic nodes contain exactly:

```text
id, kind, claim, evidence_refs, depends_on, confidence
```

Kinds are `architecture`, `control_flow`, `data_flow`, `interface`, `invariant`,
`evidence_gate`, and `experiment`. Each node has at least one evidence reference;
`depends_on` contains only non-self semantic node IDs. Summary key flows link to
route IDs and evidence references instead of repeating implementation detail.

## Boundaries and experiments

ProjectProfile owns complete path classification. Context stores only:

```json
"boundaries": {
  "policy_source": "profile.path_policy",
  "overrides": [
    {"ref": "nerf.activation", "category": "maintained_dependency", "reason": "project-maintained adapter"}
  ]
}
```

Resolve overlapping rules by the most-specific path and then Profile authority.
Allowed categories are:

```text
core | contract | entrypoint | experiment | test | evidence |
maintained_dependency | third_party | reference | historical |
generated_evidence | generated_ephemeral | local_only | auxiliary
```

For legacy Profile files, set `policy_source` to `profile.legacy_artifacts` and
use overrides only for verified exceptions. Do not copy all legacy boundary
lists into v4.

`experiment_provenance` contains `path_ref` and the ordered states
`implemented`, `configured`, `executed`, `reported`. The path points to a stable
`EXPERIMENT_PROVENANCE.json`; null means this node owns no experiment claims.
The provenance file uses `ai-project-experiment-provenance/v1`:

```json
{
  "schema": "ai-project-experiment-provenance/v1",
  "component": "nerf",
  "reference_catalog": {},
  "experiments": [
    {
      "id": "semantic-ablation",
      "claim": "semantic conditioning ablation",
      "states": {
        "implemented": {"status": "confirmed", "evidence_refs": ["ablation.code"]},
        "configured": {"status": "confirmed", "evidence_refs": ["ablation.config"]},
        "executed": {"status": "unknown", "evidence_refs": []},
        "reported": {"status": "missing", "evidence_refs": []}
      },
      "limitations": ["execution manifest not found"]
    }
  ]
}
```

States are independent: never cascade confirmation upward or downward. Use
stable manifests, metric summaries, tables, and paper references. Do not store
timestamps, logs, checkpoints, caches, model outputs, or narrative session
history.

## Hierarchy, freshness, and size

`hierarchy` always contains `role`, `child_contexts`, and `shard_contexts`:

- `workspace_root`: child contexts cover all Active components; no shards.
- `component_leaf`: no child contexts; optional semantic shards.
- `semantic_shard`: no children or shards.

Child entries contain `component` and a catalog `context_ref`. Shard entries
contain a stable `id` and `context_ref`.

`refresh.profile_fingerprint` and `active_fingerprint` come from orientation
inventory. `semantic_fingerprints` maps every semantic node to one or more
`ref`/`sha256` evidence pairs. A changed evidence fingerprint marks that semantic
node and its dependents `partially_stale`; it does not invalidate unrelated
nodes. A Profile/Active mismatch still requires topology reorientation.

Hard limits are 16 KiB for roots, ordinary leaves, and shards. A component leaf
that declares semantic shards may use 24 KiB. Target 8–12 KiB first. A temporary
orientation Bundle has a separate 32 KiB default budget.

## Migration and validation

v2, v3, and legacy Markdown are migration evidence only. During an explicit
`$ai-project-guide` operation, run `$codebase-orientation` in Deep +
`inspect_only`, rebuild a complete verified v4 tree, and preserve old files until
deletion is separately authorized. Never add v4-only fields to a v3 document.

Validate Context and experiment provenance independently:

```bash
conda run -n codex-tools python scripts/validate_ai_context.py --path <AI_CONTEXT.json>
conda run -n codex-tools python scripts/validate_experiment_provenance.py --path <EXPERIMENT_PROVENANCE.json>
```

The Context validator accepts current v3 nodes so existing workspaces remain
usable until explicitly migrated.
