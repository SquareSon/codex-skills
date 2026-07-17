---
name: artifact-template-sjtu
description: "Create a presentation using the PPT模板-交大红 template and its retained reference file. Use when the user selects this template, names PPT模板-交大红, or explicitly invokes $artifact-template-sjtu. 使用上海交通大学“百廿红”红白校色版式，制作校级汇报、答辩、宣讲和其他正式展示演示文稿。"
---

# PPT模板-交大红

Create a new presentation from this template. Keep the reference file unchanged.

## Workflow

1. Read `artifact-template.json` and resolve its paths relative to this skill directory.
2. Load [@presentations](plugin://presentations@openai-primary-runtime) and invoke its reference/template workflow with the retained file.
3. Treat the user's prompt and available sources as the content input. Do not invent facts merely to fill a template slot.
4. Clone or import the reference instead of replacing its visual system with generic defaults.
5. Render and verify the finished presentation, then return the final artifact.

## Fidelity

Preserve source slides, layouts, masters, typography, geometry, images, charts, tables, and recurring slide chrome.

User instructions control requested content and explicit deviations. The retained reference controls layout and formatting where the user has not requested a change.
