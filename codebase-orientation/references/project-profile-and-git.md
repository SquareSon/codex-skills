# ProjectProfile and Git Evidence

Read this reference only when the target path contains a ProjectProfile-style `profile/` directory, an Active workspace, or multiple related Git repositories.

## Evidence Hierarchy

Use the following evidence in order:

1. Active links and current filesystem targets describe what the workspace can run now.
2. `profile/workspace.json` declares components, Active entry names, and shared runtime templates.
3. `profile/component.json` declares portable component identity, logical environment, IDE boundaries, entrypoints, and artifacts.
4. Git commit/tag/branch and dirty status describe the exact code provenance.
5. Third-party lock files and saved patches describe dependency provenance.

Do not treat generated `.idea` files, `active_profile.json`, logs, checkpoints, or local environment overrides as portable source of truth. They can corroborate the current machine state only.

## Workspace Interpretation

For a workspace profile, identify each declared component key and inspect the corresponding Active path. Report both the stable Active path and its resolved physical target. If a link is missing, broken, or points to a component whose profile disagrees with the workspace key, mark that component as unresolved instead of guessing.

Non-Active sibling versions are not automatically obsolete. Describe them as historical or candidate versions until their role is evidenced by the user, Git history, or documentation.

## Component Interpretation

Component profiles commonly contain these concepts, though field names may evolve:

| Concept | Orientation use |
|---|---|
| Identity/version | Name the precise code version being understood. |
| Logical runtime key | Recommend, but do not assume, an interpreter. |
| Source/test/resource roots | Prioritize code and behavioral evidence. |
| Excluded/generated folders | Avoid wasting analysis on outputs and caches. |
| Entrypoints | Locate real run/debug paths and primary workflows. |
| Third-party roots | Preserve dependency boundaries during analysis. |

`Excluded` does not change runtime imports or Git tracking. `.gitignore` is a separate policy; verify it only when version-control behavior matters.

## Python and PyCharm Interpreter Alignment

Keep the interpreter contract layered:

1. The workspace may declare `default_environment_key` for its project-level fallback.
2. Each component declares `runtime.environment_key` for module-specific work.
3. `environment_templates` maps a logical key to machine-local `python_bin` or `root`.
4. `.idea/misc.xml` records PyCharm's project SDK; Active `.iml` files record module SDKs.
5. A Run/Debug configuration may intentionally override either one.

Do not assume a ProjectProfile default when the field is absent. Report it as `missing`, even if PyCharm currently has a project SDK. A `shared` component has no required interpreter unless its Profile explicitly provides one.

Verify SDK display names against the expected environment directory name and, when the local PyCharm SDK registry is readable, against the registered Python executable. The registry is machine-local corroboration, not portable source of truth.

`codebase-orientation` must not write `.idea` or the SDK registry. If the user authorizes repair, update the ProjectProfile schema/synchronizer first, regenerate PyCharm configuration, then rerun the orientation check.

## Git and GitHub Evidence

Collect Git facts without mutation:

```bash
git -C <root> rev-parse --show-toplevel
git -C <root> branch --show-current
git -C <root> rev-parse HEAD
git -C <root> describe --tags --always --dirty
git -C <root> status --short
git -C <root> remote -v
```

Remote metadata only establishes an optional GitHub/GitLab relationship. Do not contact a remote, pull, push, or infer repository ownership during orientation. Sanitize credentials embedded in remote URLs before reporting them.

If `status --short` is non-empty, report the repository as dirty and distinguish committed baseline conclusions from working-tree conclusions. Do not inspect every changed file unless it matters to the request.

## Third-Party State

When `third_party/lock-*.json` exists, report its latest snapshot identifier and whether a matching `patches/third_party/` directory exists. Treat nested vendor repositories as read-only references by default. Read their implementation only for a request explicitly about that dependency.

## Recommended Reproducibility Summary

Use a compact summary rather than raw command output:

```text
Component: <key> → <resolved path>
Profile: <path>, version <version>
Git: <branch> @ <short HEAD>, <tag/describe>, clean|dirty
Runtime: <logical environment key>; actual interpreter <confirmed|unconfirmed>
Entrypoints: <relevant names>
Third party: <latest lock or none>
```
