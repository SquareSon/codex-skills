# -*- coding: utf-8 -*-
"""测试 AI Context v4 与实验溯源验证器的关键约束。"""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from validate_ai_context import validate_v4
from validate_experiment_provenance import validate as validate_provenance


ASSET_ROOT = Path(__file__).resolve().parent.parent / "assets"
FINGERPRINT = f"sha256:{'0' * 64}"


def valid_v4_context() -> dict:
    """构造包含一个组件、路由和语义节点的最小有效工作台 Context。"""

    return {
        "schema": "ai-project-context/v4",
        "scope": "workspace",
        "authority_order": ["active", "profile", "git", "source", "context"],
        "reference_catalog": {
            "workspace.profile": {"scope": "workspace", "path": "profile/workspace.json"},
            "nerf.profile": {"scope": "component", "component": "nerf", "path": "profile/component.json"},
            "nerf.source": {"scope": "component", "component": "nerf", "path": "nerfus"},
            "nerf.train": {"scope": "component", "component": "nerf", "path": "scripts/train.py"},
            "nerf.context": {
                "scope": "component",
                "component": "nerf",
                "path": "docs/ai-guide/AI_CONTEXT.json",
            },
        },
        "summary": {
            "purpose": "Train an ultrasound NeRF.",
            "architecture": ["Workspace delegates implementation detail to component leaves."],
            "key_flows": [
                {
                    "id": "training-flow",
                    "summary": "Configuration enters the NeRF training entrypoint.",
                    "route_ids": ["train"],
                    "evidence_refs": ["nerf.train"],
                    "confidence": "confirmed",
                }
            ],
        },
        "hierarchy": {
            "role": "workspace_root",
            "child_contexts": [{"component": "nerf", "context_ref": "nerf.context"}],
            "shard_contexts": [],
        },
        "bootstrap": {"read_before_code": ["workspace.profile"], "active_components": ["nerf"]},
        "components": [
            {
                "id": "nerf",
                "role": "reconstruction",
                "locator": {"kind": "active_component", "key": "nerf"},
                "profile_ref": "nerf.profile",
                "runtime_key": "nerf",
                "source_refs": ["nerf.source"],
                "entrypoint_refs": ["nerf.train"],
            }
        ],
        "task_routes": [
            {
                "id": "train",
                "intent": "trace NeRF training",
                "components": ["nerf"],
                "attention_refs": ["nerf.train"],
                "expand": ["callees", "configuration", "tests"],
                "semantic_nodes": ["nerf.training"],
                "contract_ids": [],
                "required_evidence": ["nerf.train"],
                "completion_rule": "all_required_evidence_or_explicit_gap",
            }
        ],
        "contracts": [],
        "semantic_nodes": [
            {
                "id": "nerf.training",
                "kind": "control_flow",
                "claim": "The training entrypoint resolves configuration before creating the trainer.",
                "evidence_refs": ["nerf.train"],
                "depends_on": [],
                "confidence": "confirmed",
            }
        ],
        "experiment_provenance": {
            "path_ref": None,
            "required_states": ["implemented", "configured", "executed", "reported"],
        },
        "do_not_assume": ["Implementation does not prove execution."],
        "boundaries": {"policy_source": "profile.path_policy", "overrides": []},
        "refresh": {
            "profile_fingerprint": FINGERPRINT,
            "active_fingerprint": FINGERPRINT,
            "semantic_fingerprints": [
                {"semantic_node": "nerf.training", "evidence": [{"ref": "nerf.train", "sha256": FINGERPRINT}]}
            ],
        },
    }


def valid_standalone_context() -> dict:
    """构造无 ProjectProfile 或 Active 选择的独立仓库 Context。"""

    context = valid_v4_context()
    context["scope"] = "component"
    context["reference_catalog"] = {
        "skills.readme": {"scope": "component", "component": "skills", "path": "README.md"},
        "skills.source": {"scope": "component", "component": "skills", "path": "ai-project-guide"},
        "skills.entrypoint": {
            "scope": "component",
            "component": "skills",
            "path": "ai-project-guide/SKILL.md",
        },
    }
    context["hierarchy"] = {"role": "component_leaf", "child_contexts": [], "shard_contexts": []}
    context["bootstrap"] = {"read_before_code": ["skills.readme"], "active_components": ["skills"]}
    context["components"] = [
        {
            "id": "skills",
            "role": "Codex skill collection",
            "locator": {"kind": "relative", "path": "."},
            "profile_ref": None,
            "runtime_key": None,
            "source_refs": ["skills.source"],
            "entrypoint_refs": ["skills.entrypoint"],
        }
    ]
    context["task_routes"][0]["components"] = ["skills"]
    context["task_routes"][0]["attention_refs"] = ["skills.entrypoint"]
    context["task_routes"][0]["required_evidence"] = ["skills.entrypoint"]
    context["summary"]["key_flows"][0]["evidence_refs"] = ["skills.entrypoint"]
    context["semantic_nodes"][0]["evidence_refs"] = ["skills.entrypoint"]
    context["boundaries"] = {"policy_source": "repository.layout", "overrides": []}
    context["refresh"] = {
        "profile_fingerprint": None,
        "active_fingerprint": None,
        "semantic_fingerprints": [
            {
                "semantic_node": "nerf.training",
                "evidence": [{"ref": "skills.entrypoint", "sha256": FINGERPRINT}],
            }
        ],
    }
    return context


class ContextValidatorTests(unittest.TestCase):
    def test_template_is_valid_when_incomplete(self) -> None:
        template = json.loads((ASSET_ROOT / "AI_CONTEXT.template.json").read_text(encoding="utf-8"))
        self.assertEqual(validate_v4(template, allow_incomplete=True), [])

    def test_minimal_context_is_valid(self) -> None:
        self.assertEqual(validate_v4(valid_v4_context(), allow_incomplete=False), [])

    def test_standalone_context_without_profile_is_valid(self) -> None:
        self.assertEqual(validate_v4(valid_standalone_context(), allow_incomplete=False), [])

    def test_active_component_without_profile_is_rejected(self) -> None:
        context = copy.deepcopy(valid_v4_context())
        context["components"][0]["profile_ref"] = None
        errors = validate_v4(context, allow_incomplete=False)
        self.assertTrue(any("独立 relative 组件" in error for error in errors))

    def test_dangling_route_node_is_rejected(self) -> None:
        context = copy.deepcopy(valid_v4_context())
        context["task_routes"][0]["semantic_nodes"] = ["missing.node"]
        errors = validate_v4(context, allow_incomplete=False)
        self.assertTrue(any("悬空 ID" in error for error in errors))

    def test_missing_semantic_fingerprint_is_rejected(self) -> None:
        context = copy.deepcopy(valid_v4_context())
        context["refresh"]["semantic_fingerprints"] = []
        errors = validate_v4(context, allow_incomplete=False)
        self.assertTrue(any("覆盖全部 semantic_nodes" in error for error in errors))


class ProvenanceValidatorTests(unittest.TestCase):
    def test_states_remain_independent(self) -> None:
        value = {
            "schema": "ai-project-experiment-provenance/v1",
            "component": "nerf",
            "reference_catalog": {
                "experiment.code": {
                    "scope": "component",
                    "component": "nerf",
                    "path": "experiments/ablation.py",
                }
            },
            "experiments": [
                {
                    "id": "ablation",
                    "claim": "Semantic conditioning ablation.",
                    "states": {
                        "implemented": {"status": "confirmed", "evidence_refs": ["experiment.code"]},
                        "configured": {"status": "unknown", "evidence_refs": []},
                        "executed": {"status": "unknown", "evidence_refs": []},
                        "reported": {"status": "missing", "evidence_refs": []},
                    },
                    "limitations": ["No execution manifest found."],
                }
            ],
        }
        self.assertEqual(validate_provenance(value, allow_incomplete=False), [])


if __name__ == "__main__":
    unittest.main()
