# Verification policy

Use source-derived user metrics as cloud anchors. Do not treat `_step` alone, a UI chart, or a final summary as evidence that history is complete.

For each anchor, record either its expected count or its exact ordered steps in the manifest. Select at least one dense training metric and one sparse evaluation metric when both exist. Compare state, anchor counts/steps, immutable configuration identity, and required media references.

For a locally rebuilt candidate, require equal history count, step range, missing-step count, media row count, and media file count before cloud sync. A `.wandb.synced` marker proves the CLI completed; perform cloud anchor verification afterwards because server-side indexing can lag.

Treat unsupported W&B SDK transaction versions, missing media, duplicate steps, non-monotonic steps, or ambiguous cloud API output as `indeterminate`, not as successful recovery.
