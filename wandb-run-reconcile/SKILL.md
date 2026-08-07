---
name: wandb-run-reconcile
description: Audit, reconcile, recover, republish, or clean Weights & Biases runs from local W&B transaction logs. Use when local logs and cloud runs disagree, history or media are incomplete, a safe offline-first republish is needed, duplicate or failed runs must be classified, or approved local/cloud run cleanup is requested. Never use for model retraining.
---

# W&B Run Reconcile

Reconcile experiment records without recomputing any model output. Treat the local W&B transaction as evidence, the cloud run as a publication target, and destructive cleanup as a separately approved action.

## Operating modes

Use the narrowest mode that satisfies the request:

- **Audit**: inspect local transaction files and/or cloud run anchors; never write.
- **Plan**: classify source, old cloud run, and candidate runs; write a manifest but do not upload or delete.
- **Recover**: rebuild a new offline run from a complete local transaction, validate it locally, then sync its fixed candidate ID.
- **Publish sidecars**: invoke a caller-provided command after core recovery. The skill does not interpret the command's metrics or domain semantics.
- **Cleanup**: delete only manifest-listed local paths and cloud run IDs after explicit user approval.

Never train, resume training, modify source transactions, overwrite an existing cloud run ID, or delete by glob/project-wide query.

## Workflow

1. Run `scripts/reconcile.py audit-local` for every local source and save the JSON report.
2. Define user-metric anchors in a manifest; do not use `_step` alone as a cloud-completeness test. Read [verification policy](references/verification-policy.md).
3. Run `scripts/reconcile.py audit-cloud` for each old or candidate run. Classify it as complete, incomplete, empty, duplicate, or indeterminate.
4. Write a reconciliation manifest. Include exact local paths, `entity/project/run_id`, expected anchor counts/steps, and optional post-publish sidecar commands.
5. Present the plan. Obtain explicit approval before either a new cloud run or cleanup.
6. For an approved recovery, run `scripts/build_offline_recovery.py`; it rejects a candidate unless its generated transaction matches the source on history and media references.
7. Run `scripts/sync_candidate.py` once per fixed candidate ID. Retry the same offline directory and ID on transient failure; never mint a replacement ID automatically.
8. Re-run cloud audit, then execute any approved sidecar command. Update project-owned mappings only after verification.
9. For approved cleanup, generate a final manifest hash and pass it unchanged to `scripts/reconcile.py cleanup --apply --approval-sha ...`.

## Commands

Run scripts with the environment that contains the same W&B version used by the source transaction. Do not install or upgrade W&B implicitly.

```bash
python scripts/reconcile.py audit-local --run-dir /path/to/wandb/run-... --output local-audit.json
python scripts/reconcile.py audit-cloud --run-path entity/project/runid --anchors anchors.json --output cloud-audit.json
python scripts/build_offline_recovery.py --source-run-dir /path/to/wandb/run-... --candidate-id fixedid --output-root /safe/recovery --report offline-audit.json
python scripts/sync_candidate.py --offline-run-dir /safe/recovery/wandb/offline-run-... --apply
python scripts/create_cleanup_manifest.py --targets reviewed-targets.json --output cleanup-manifest.json
python scripts/reconcile.py cleanup --manifest cleanup-manifest.json --apply --approval-sha <manifest-sha>
```

`anchors.json` is a list of objects with `metric`, and either `expected_count` or `expected_steps`. It is intentionally domain-neutral.

## Approval and cleanup

Before cleanup, show the exact manifest content and SHA-256 to the user. Require an explicit approval that includes both the target class and that SHA. The `cleanup` command must reject a missing/mismatched SHA, a running cloud run, a path outside the manifest, or an unsafe local target (filesystem root, home, current workspace, or a short ancestor path).

Use [incident casebook](references/wandb-incident-casebook.md) whenever a sync fails, a run state looks inconsistent, or a cloud query is ambiguous.
