---
name: python-code-style
description: Apply the user's Python coding standards and style preferences. Use when Codex writes, edits, refactors, reviews, explains, or tests Python code, especially for scripts, Bash/Python CLI interfaces, research code, model training, data processing, visualization, demos, paper-inspired implementations, and modules that benefit from Chinese comments, focused comments/docstrings, reusable existing helpers, mature libraries, concise Python syntax guided by The Zen of Python, documentation updates, and foldable region organization.
---

# Python Code Style

## Core Priority

- Follow the user's explicit request first.
- Follow the repository's existing conventions second.
- Apply this skill when the repository is silent, inconsistent, or leaves style decisions open.
- Keep changes concise, efficient, and easy to understand.
- Prefer maintainability through reuse of existing project code and functions.

## Encoding And Chinese Comments

- Use Chinese as the primary language for comments and explanatory docstrings unless the surrounding file clearly uses another style.
- When creating or editing Python files that contain Chinese comments or docstrings, keep the file encoded as UTF-8.
- Add `# -*- coding: utf-8 -*-` near the top of newly created Python files that contain Chinese text, below a shebang if one exists.
- Avoid tooling or shell commands that may rewrite Chinese text with the system default encoding. Prefer UTF-8 aware editors, formatters, and file operations.
- On Windows or PowerShell, use explicit UTF-8 operations such as `Get-Content -Encoding UTF8` and `Set-Content -Encoding UTF8` when inspecting or rewriting files with Chinese text.
- After edits involving Chinese comments, inspect representative changed lines to confirm the Chinese text is not mojibake or escaped into unreadable text.

## Comments And Docstrings

- Use clear names and structure first; omit docstrings for simple, self-documenting functions.
- Prefer focused single-line comments and inline comments inside code to clarify flow, assumptions, and non-obvious expressions.
- Avoid large block comments or long docstrings unless they explain a complex API, algorithm, data contract, or workflow.
- Force-wrap comment and docstring lines only when they exceed 128 characters.
- For comment and docstring lines no longer than 128 characters, wrap only for clear semantic shifts or readability reasons.
- If a comment is 64 characters or shorter and has no obvious semantic break, keep it on one line.
- For complex functions, include reStructuredText-style docstrings with `:param ...:`, `:returns:`, and `:raises ...:` only when they add useful information.
- For complex code blocks, add intermediate comments before major steps and line comments for non-obvious expressions.
- For global variables and major configuration parameters, include inline comments that explain their role and practical effect.
- Do not add empty comments that merely restate the code. Explain why the step exists, what assumption it depends on, or how the value is used.

## Preserving Existing Comments

- When modifying existing code, preserve the user's existing comments whenever practical.
- If code moves or changes shape, relocate existing comments to the closest still-accurate location.
- Update stale comments instead of deleting them when the original intent remains useful.
- Delete existing comments only when they are clearly wrong, misleading, duplicated by a better nearby comment, or tied to removed behavior.

## Simplicity And Validation

- Optimize for concise, efficient, readable code.
- Do not add heavy compatibility layers, security hardening, or exhaustive input validation by default.
- Add minimal validation only when it prevents confusing failures, protects data from accidental loss, or matches an existing local pattern.
- Avoid broad defensive programming unless the user explicitly asks for production-grade robustness.

## Reuse And Abstraction

- Prefer reusing existing project functions, classes, modules, and established libraries.
- Before implementing a new utility, search the current project for existing helper functions or patterns that already solve the problem.
- Prefer mature, well-maintained libraries for standard problems instead of reimplementing common functionality.
- Avoid creating helper functions that are only one thin forwarding layer with little added meaning.
- Add a helper only when it removes meaningful duplication, names a real concept, or makes a complex block easier to understand.
- Avoid frequent meaningless data copies, variable renaming, and alias-only assignments.
- Do not create aliases unless they significantly improve readability, shorten a genuinely noisy expression, or match a common library convention.

## Python Idioms

- Assume the user is comfortable with modern Python syntax.
- Follow the spirit of The Zen of Python (PEP 20) as style guidance, especially: Simple > complex > complicated.
- Use Python syntax sugar when it makes code shorter and clearer.
- Prefer `dataclass` for configuration objects and data containers when it reduces boilerplate.
- Use comprehensions, context managers, tuple unpacking, f-strings, pathlib, and standard library tools when they clarify intent.
- Keep idioms readable; do not use clever one-liners when a small commented block is easier to follow.

## Script Interfaces

- For Bash scripts and Python console entry points, prefer explicit script options over environment variables for user-controlled behavior.
- Use `argparse`, `typer`, `click`, or the repository's established CLI pattern for Python script parameters when appropriate.
- Reserve environment variables for credentials, external service configuration, CI/runtime integration, or values that are genuinely process-environment concerns.
- Document important script options in help text, module demos, README-style docs, or nearby usage examples when the script is meant to be reused.

## Research Sources

- When code is supported or inspired by a paper, cite the paper source and state the concrete support or inspiration.
- Include enough source detail to identify the paper, such as title, authors if available, year, DOI/arXiv URL, or the local bibliography key used by the project.
- Place paper-source notes near the relevant algorithm, model, loss function, preprocessing method, experiment setup, or documentation section.
- Distinguish direct implementation requirements from loose inspiration; do not imply a paper supports behavior that is only an engineering choice.

## Module Demo Blocks

- For module-style Python files, include a useful `if __name__ == "__main__":` demo by default when it fits the module.
- Make demos runnable and illustrative, not merely placeholder calls.
- Include sufficient visualization for computational, scientific, image, signal, geometry, model, or data-processing code when visualization helps verify behavior.
- For model training workflows, prefer Weights & Biases (`wandb`) for tracking metrics, losses, hyperparameters, artifacts, and training visualizations when it fits the project and credentials/runtime are available.
- Keep demos separated from library logic and clearly commented.

## Code Documentation

- Encourage lightweight, living documentation that helps Codex and future maintainers quickly understand the code.
- When changing code, update nearby docs, usage examples, README sections, module comments, or design notes that would otherwise become stale.
- Prefer concise overview docs for non-trivial modules, pipelines, training workflows, data formats, CLI usage, and experiment procedures.
- Do not create verbose standalone documentation when a short updated section or example near the code would be clearer.

## Region Organization

- For code that can be significantly grouped into foldable sections, wrap groups with `#region 名称` and `#endregion`.
- Use regions for meaningful modules of logic such as configuration, data loading, preprocessing, visualization, model setup, or demo execution.
- Avoid excessive regions around tiny blocks; use them only when folding improves navigation.

## Final Self-Check

- Confirm Chinese comments remain readable after the edit.
- Confirm comments and docstrings are not force-wrapped unless they exceed 128 characters.
- Confirm shorter comment and docstring lines are split only for clear semantic changes or readability.
- Confirm simple, self-documenting functions were not given unnecessary docstrings.
- Confirm complex functions have useful reStructuredText docstrings when they add real value.
- Confirm major configuration values and globals have inline explanatory comments.
- Confirm existing comments were preserved or intentionally updated.
- Confirm the code reuses local functionality where appropriate and avoids thin wrapper helpers.
- Confirm Bash/Python script parameters use explicit CLI options unless environment variables are the right abstraction.
- Confirm paper-supported or paper-inspired code cites the source and explains the specific support or inspiration.
- Confirm relevant docs or usage examples were updated together with code changes.
- Confirm model training code uses or considers `wandb` visualization when suitable.
