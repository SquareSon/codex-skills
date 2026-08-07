# Reconciliation manifest schema

Use a JSON manifest as the immutable review object between audit and action. Store it outside source run directories.

```json
{
  "schema_version": "wandb-reconcile-v1",
  "source": {
    "local_audit": "/absolute/source-audit.json",
    "source_record_sha256": "..."
  },
  "old_cloud": {
    "run_path": "entity/project/oldid",
    "cloud_audit": "/absolute/old-cloud-audit.json"
  },
  "candidate": {
    "run_id": "fixedid",
    "offline_report": "/absolute/offline-report.json"
  },
  "verification": {
    "anchors": "/absolute/anchors.json"
  },
  "sidecars": [
    {
      "command": ["python", "/project/script.py", "--run-path", "entity/project/fixedid"],
      "input_sha256": {"/project/result.json": "..."}
    }
  ]
}
```

Keep all project-specific metrics, mappings, and post-publication commands inside `sidecars`; the generic skill only records their command, inputs, exit status, and verification requirements.

For cleanup, use `scripts/create_cleanup_manifest.py`. Each item must contain an exact `local_path`, exact `remote_run_path`, a classification, and a reason. Compute the SHA after the final review; any change invalidates approval.
