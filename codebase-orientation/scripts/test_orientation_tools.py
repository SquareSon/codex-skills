# -*- coding: utf-8 -*-
"""测试路径分类与临时 Bundle 的关键确定性行为。"""

from __future__ import annotations

import unittest

from build_orientation_bundle import shrink_bundle
from collect_orientation_context import classification_diagnostics, normalize_path_policy


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


if __name__ == "__main__":
    unittest.main()
