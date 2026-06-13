---
name: academic-paper-writing
description: Polish, revise, review, and compose academic paper text. Use when Codex writes thesis or paper sections, rewrites manuscript drafts, checks academic logic and terminology consistency, synthesizes related work, performs Zotero-backed local literature review, plans online literature research, edits formulas and symbols, integrates figures and tables, creates bilingual captions, generates placeholder visuals or key-step schematics, analyzes experimental results, or prepares replacement-ready scholarly prose.
---

# Academic Paper Writing

## Core Workflow

- Produce replacement-ready final text, not a commentary about the revision process.
- Check global consistency before polishing local sentences: logic, terminology, variables, formulas, figure/table references, claims, and experiment interpretation.
- Preserve the target language and academic field style unless the user requests a language change.
- Maintain rigorous, restrained academic tone. Avoid inflated claims, marketing language, and AI-like generic phrasing.
- Prefer natural expressions commonly used by human researchers; keep sentences clear, precise, and readable.
- Do not fabricate experimental data, citations, figure/table contents, or source provenance.

## Logic And Terminology

- Check whether adjacent sections, paragraphs, and claims follow a coherent argument.
- Resolve contradictions, circular reasoning, unsupported causal claims, and abrupt topic jumps.
- Use one term for one concept. Do not mix translations, abbreviations, or synonyms unless the distinction is intentional.
- Define abbreviations and specialized terms at first use when appropriate.
- Keep contributions, method descriptions, experiments, results, and conclusions aligned.
- When a claim needs evidence that is absent, weaken the claim or mark the missing evidence with a clear placeholder such as `***`.

## Claim And Evidence Structure

- When arguing that the proposed method is better, use a two-stage evidence chain:
  first give a theoretical or prior analysis that explains why the method should be better,
  then use experiments to verify whether that prediction holds in practice.
- Make the theoretical stage explicit: identify the mechanism, assumption, inductive bias,
  optimization property, information advantage, or structural constraint that should improve the result.
- Convert the theoretical analysis into a concrete prediction before presenting experiments.
  State what metric, phenomenon, robustness pattern, failure reduction, or qualitative behavior should improve.
- Use the experimental stage as posterior verification. Show whether the observed results match the prediction,
  where they match only partially, and where the evidence is still insufficient.
- After presenting results, analyze why the method works and where it works: connect specific numbers,
  ablation results, visual examples, error cases, or robustness trends back to the earlier mechanism.
- Avoid the weak pattern "our method is better because the table is higher." Explain the causal or structural reason
  behind the improvement whenever the available evidence supports it.
- If theory predicts an advantage but experiments are missing, write the prediction cautiously and mark the missing
  verification with `***`. If experiments show an advantage but the mechanism is unclear, say so and suggest the
  analysis needed to support the claim.

## Related Work And Literature Review

- Build related work around a high-level intellectual thread, not a sequence of isolated paper summaries.
- Group literature by methods, assumptions, tasks, data, limitations, or research trajectories when this better supports the paper's argument.
- Use prior successes to justify the reasonableness of the paper's direction: the work should appear grounded in established progress rather than arbitrary.
- Use prior limitations to justify the paper's innovation: the new method should look like a careful refinement or necessary extension, not a dismissive rejection of prior work.
- Connect each cited work or literature group back to the manuscript's motivation, design choice, or claimed contribution.
- Avoid strawman comparisons. Describe limitations precisely and respectfully, especially when prior methods are strong in their intended setting.
- When references are insufficient for a claim, ask for more papers or mark the missing citation with `***` instead of inventing sources.
- For substantial related-work expansion, derive a systematic technical lineage before writing:
  identify representative works, order them by technical progression, explain what each step solved,
  what assumption or bottleneck remained, and how that limitation motivates the user's work.
- Do not merely add more citations. Add analysis that explains the progression of ideas, the changing problem setting,
  and why the proposed work is a justified next step.
- When representative figures from prior work would clarify the lineage, mention that they may be useful and identify
  which paper or concept they should illustrate. Do not copy copyrighted figures into the final text unless the user
  provides them or explicitly requests figure extraction with proper provenance.
- Use deficiencies of prior work to motivate innovation, but keep the critique technically specific:
  name the setting, data condition, modeling assumption, hardware constraint, robustness issue, or evaluation gap.

## Literature Retrieval

- When the user asks to search the local paper library, use the Zotero plugin and the `Zotero` skill when available.
- Start local Zotero work with the Zotero helper status check, then search the local library by keywords, title,
  author, method name, task, or citation clue.
- Prefer reading Zotero metadata and abstract fields first to quickly understand each paper and triage relevance.
- Return title, authors, year, Zotero item key, BibTeX key when available, and a one-sentence relevance note.
- Retrieve local PDF paths or indexed full text through Zotero only when the abstract is insufficient, the user asks
  for full-text analysis, or a claim requires exact method/result details.
- When enough local literature is not available, say what is missing and propose targeted search queries or venues.
- When online literature search is needed and access may require login, ask the user to log in or authorize access
  before relying on paywalled or account-gated sources.
- For online literature, prefer primary sources such as papers, official publisher pages, arXiv, conference pages,
  or author/project pages. Do not use unsourced summaries as evidence for manuscript claims.

## Style And Polishing

- Improve grammar, clarity, concision, and readability to meet academic standards.
- Avoid overly ornate wording, exaggerated certainty, and claims beyond the evidence.
- Prefer specific subject-verb structure over vague generic statements.
- Preserve technical precision while making transitions smoother.
- When rewriting Chinese academic text, use formal but natural Chinese scholarly prose.
- When rewriting English academic text, use idiomatic academic English without unnecessary complexity.
- Do not mention revision history or meta-context in final prose, including phrases meaning "previous version", "materials you provided", or "this document" unless they are part of a formal citation or required document title.

## Formulas And Symbols

- Use linear LaTeX for all formulas and symbols unless the user explicitly requests display math.
- Keep notation consistent across the full manuscript.
- Check that each variable has a clear definition, unit, and role when needed.
- Do not reuse the same symbol for unrelated concepts.
- Align formula descriptions with surrounding text, figures, tables, and experimental settings.
- If a formula is ambiguous, add a concise explanation in prose rather than leaving the symbol unexplained.

## Figures And Tables

- Reuse as many relevant figures and tables from the user's materials as possible.
- For every used figure or table, provide both Chinese and English captions when captions are missing or need improvement.
- Ensure captions accurately describe the visual content, variables, experimental setting, and key takeaway without overclaiming.
- Cite each figure or table at an appropriate point in the main text.
- Integrate figure/table interpretation into the paragraph argument instead of placing it as a stiff standalone explanation.
- Check that the text's figure/table reference, analysis, and surrounding logic are consistent and fluent.
- Report which figures and tables were used and where they came from, using file names, section names, or user-supplied labels when available.
- If an additional figure would make the method, workflow, experiment, or result easier to understand, propose it clearly.
- When a placeholder figure is useful and image generation is available, generate a replaceable example image for the user to later swap with the final figure.
- When a key procedural diagram would clarify the argument, use image generation when available to create a replaceable schematic placeholder that explains the key steps.
- If image generation is unavailable or unnecessary, provide a concise schematic layout description that can be turned into a figure later.
- When an additional table would strengthen the argument, create an empty table template with missing data marked as `***`.
- Clearly label generated figures and empty tables as placeholders outside the manuscript prose so they are not mistaken for final experimental evidence.

## Experiments And Results

- For missing experimental results, use `***` as the temporary placeholder and still write the surrounding analysis.
- Make the analysis match the actual or placeholder results without inventing unsupported trends.
- Ensure metric names, dataset names, baselines, units, and experimental conditions remain consistent.
- Ground experimental analysis in specific numbers from tables, plots, or stated results whenever available.
- Cite relevant figures and tables frequently enough that the reader can verify each key comparison and trend.
- Compare against baselines with explicit metrics, deltas, rankings, or qualitative observations when the materials support them.
- Explain why a result supports the method's design choice or claimed advantage, instead of merely restating that the result is better.
- Link empirical findings back to the theoretical prediction: state whether each key result confirms, refines, or contradicts the expected mechanism.
- If additional experiments, figures, or tables would strengthen the argument, state concrete suggestions after the replacement-ready text.
- Prefer suggestions that directly support a claim, close a logic gap, or make a comparison easier to verify.

## Output Discipline

- Give the final replacement text first when the user asks for paper writing or revision.
- Avoid prefacing the answer with explanations of what was changed unless the user asks for a change log.
- If reporting figure/table usage is required, place a concise figure/table usage list after the final text.
- If requesting missing data or additional materials, place concise supplement suggestions after the final text.
- Keep placeholders explicit and easy to search, preferably `***`.
- Do not introduce source names such as "the provided document" into the manuscript prose. Use actual file names or formal citation labels only outside the replacement text when reporting provenance.
