# -*- coding: utf-8 -*-
"""测试路径分类与临时 Bundle 的关键确定性行为。"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from build_orientation_bundle import build_bundle, shrink_bundle, workspace_nodes
from collect_orientation_context import classification_diagnostics, collect_context, normalize_path_policy


class PathPolicyTests(unittest.TestCase):
    def test_normalize_mapping_policy(self) -> None:
        rules = normalize_path_policy(
            {
                "third_party": ["nerfus/lib/**"],
                "maintained_dependency": ["nerfus/lib/activation/**"],
            }
        )
        self.assertEqual(
            rules,
            [
                {"path": "nerfus/lib", "category": "third_party"},
                {"path": "nerfus/lib/activation", "category": "maintained_dependency"},
            ],
        )

    def test_boundary_exception_is_reported(self) -> None:
        claims = [
            {
                "path": "runs",
                "category": "generated_ephemeral",
                "source": "profile.artifacts.generated_folders",
                "explicit": False,
            }
        ]
        diagnostics = classification_diagnostics(claims, ["runs/manifests"])
        self.assertEqual(diagnostics[0]["kind"], "boundary_covers_gitignore_exception")


class BundleBudgetTests(unittest.TestCase):
    def test_shrink_records_removed_sections(self) -> None:
        bundle = {
            "components": [{"git": {"status": "x" * 500}}],
            "contexts": [],
            "truncated_sections": [],
            "over_budget": False,
        }
        result = shrink_bundle(bundle, 128)
        self.assertIn("component.git", result["truncated_sections"])
        self.assertNotIn("git", result["components"][0])

    def test_standalone_repository_context_is_discoverable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "skills"
            context_path = root / "docs" / "ai-guide" / "AI_CONTEXT.json"
            shard_path = root / "docs" / "ai-guide" / "workflows.AI_CONTEXT.json"
            context_path.parent.mkdir(parents=True)
            context = {
                "schema": "ai-project-context/v4",
                "reference_catalog": {
                    "context.workflows": {
                        "scope": "component",
                        "component": "skills",
                        "path": "docs/ai-guide/workflows.AI_CONTEXT.json",
                    }
                },
                "hierarchy": {
                    "role": "component_leaf",
                    "child_contexts": [],
                    "shard_contexts": [{"id": "workflows", "context_ref": "context.workflows"}],
                },
                "refresh": {"profile_fingerprint": None, "active_fingerprint": None, "semantic_fingerprints": []},
            }
            shard = {
                "schema": "ai-project-context/v4",
                "scope": "shard",
                "summary": {"purpose": "plan work", "architecture": [], "key_flows": []},
                "task_routes": [
                    {
                        "id": "persist-plan",
                        "intent": "persist and recover a task plan",
                        "components": ["skills"],
                        "attention_refs": [],
                        "expand": [],
                        "semantic_nodes": [],
                        "contract_ids": [],
                        "required_evidence": [],
                        "completion_rule": "all_required_evidence_or_explicit_gap",
                    }
                ],
                "semantic_nodes": [],
                "contracts": [],
                "reference_catalog": {},
            }
            context_path.write_text(json.dumps(context), encoding="utf-8")
            shard_path.write_text(json.dumps(shard), encoding="utf-8")

            inventory = collect_context(root)
            component = inventory["component"]
            self.assertEqual(component["key"], "skills")
            self.assertIsNone(component["ai_context_inputs"]["profile_fingerprint"])
            self.assertIsNone(component["ai_context_inputs"]["active_fingerprint"])
            self.assertEqual(component["ai_context_inputs"]["freshness"]["fingerprint_state"], "current")

            root_context, child_contexts = workspace_nodes(inventory)
            self.assertIsNone(root_context)
            self.assertEqual(child_contexts["skills"]["schema"], "ai-project-context/v4")

            bundle = build_bundle(root, "persist task plan", [], 32 * 1024)
            self.assertEqual(bundle["missing_shards"], [])
            self.assertTrue(
                any(context.get("role") == "semantic_shard" for context in bundle["contexts"])
            )


if __name__ == "__main__":
    unittest.main()
