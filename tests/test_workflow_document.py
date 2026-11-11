# -*- coding: utf-8 -*-
"""技能工作树的漏斗、命令和实际约束，防止文档把目标写成已经完成。"""
import json
import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

BASE = Path(__file__).resolve().parents[1]
FILE = BASE / "skills" / "photocraft-draw" / "references" / "workflow.yaml"


def test_workflow_branches_and_declared_limits():
    data = yaml.safe_load(FILE.read_text(encoding="utf-8"))
    assert data["schema"] == "photocraft-draw-workflow/v1"
    assert len(data["entry"]["branches"]) == 5
    assert [item["id"] for item in data["spatial"]["decision"]] == [
        "simple_layout", "multiple_jointed_subjects", "crossing_weapons",
        "weapon_or_contact_checks", "needed_part_has_empty_coverage",
    ]
    for item in data["entry"]["branches"]:
        assert item.get("next")
        assert isinstance(item.get("draws_whitebox"), bool)
    assert data["details"]["declare_subjects_and_references"]["blocking"]
    assert data["presentation"]["manuscript"]["current_limit"]
    assert data["model_adapter"]["options"]["minimax_h3"]["one_request_at_a_time"]


def test_declared_commands_exist_and_docs_link_workflow():
    commands = {"colors", "occlusion", "contact", "depth", "motion", "facing",
                "relations", "views", "layout", "prompt", "sheet", "verify",
                "brief", "details", "check", "draw", "quick", "annotate",
                "doc", "commands", "components", "doctor"}
    matches = set(re.findall(r"photocraft-draw ([a-z-]+)", FILE.read_text(encoding="utf-8")))
    assert matches <= commands
    assert "workflow.yaml" in (BASE / "skills/photocraft-draw/SKILL.md").read_text(encoding="utf-8")
    assert "workflow.yaml" in (BASE / "README.md").read_text(encoding="utf-8")
