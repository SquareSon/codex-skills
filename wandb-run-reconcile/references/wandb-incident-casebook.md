# W&B incident casebook

## Partial online history

**Symptom:** a finished run has only an early prefix of training or evaluation metrics.

**Response:** preserve the source transaction; build a new offline candidate, verify it locally, then use `wandb sync` for that fixed ID. Do not rapidly replay directly to the cloud.

## `_step`-only cloud query is incomplete

**Symptom:** `scan_history(keys=["_step"])` is empty, sampled, or disagrees with visible metrics.

**Response:** query `_step` together with a known user metric. Verify several source-derived anchors because a metric query only returns rows containing that metric.

## Large-media timeout or transient state

**Symptom:** upload stalls, reports object-storage deadlines, or the run briefly reads `running`/`crashed`.

**Response:** inspect the offline directory and its synced marker, wait for server indexing, and retry the same directory/ID if the marker is absent. Never create a new candidate merely because of a transient state.

## Proxy conflict

**Symptom:** HTTP-capable environment fails when a SOCKS `ALL_PROXY` is also set.

**Response:** retain configured HTTP(S) proxies and remove only the conflicting SOCKS `ALL_PROXY` for the sync subprocess. Do not expose proxy credentials in reports.

## Post-training metrics absent from the source transaction

**Symptom:** source `.wandb` summary lacks metrics that were written later through a cloud API.

**Response:** recover core transaction first, then run a caller-supplied sidecar publisher. Record the sidecar input hashes and verify its resulting summary keys separately.

## Duplicate recovery candidates

**Symptom:** several new cloud runs claim to replace the same old run.

**Response:** classify candidates by source transaction hash and fixed ID. Keep at most one verified candidate; delete only explicitly approved duplicates through a locked cleanup manifest.
