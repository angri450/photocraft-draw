# -*- coding: utf-8 -*-
"""工作树必须模型无关；检查与展示均按需，不能重新长出常驻分支。"""
import re
from pathlib import Path
import pytest

yaml = pytest.importorskip("yaml")
BASE = Path(__file__).resolve().parents[1]
DOC = BASE / "skills/photocraft-draw/references/workflow.yaml"


def test_workflow_keeps_model_choice_outside():
    assert isinstance(yaml.safe_load(DOC.read_text(encoding="utf-8")), dict)
    for path in [
        BASE / "README.md",
        BASE / "skills/photocraft-draw/SKILL.md",
        DOC,
    ]:
        text = path.read_text(encoding="utf-8")
        assert "MOSS" not in text
        assert "MiniMax" not in text
        assert "H3" not in text
        assert "--compile-to" not in text
        assert "--request" not in text
        assert "--moss" not in text
        assert "prepare_request" not in text
    data = yaml.safe_load(DOC.read_text(encoding="utf-8"))
    assert data["schema"] == "photocraft-draw-workflow/v2"
    assert len(data["entry"]) == 5
    assert all(item.get("do") for item in data["entry"])
    assert data["handoff"]["target"] == "image-prompt"
    assert data["separate_tools"]["rule"]
    assert not (BASE / "photocraft_draw/prompt_compiler.py").exists()


def test_workflow_commands_exist():
    commands = {"colors", "occlusion", "contact", "depth", "motion", "facing",
                "relations", "views", "layout", "prompt", "sheet", "verify", "brief", "details",
                "check", "draw", "quick", "annotate", "doc", "commands", "components", "doctor"}
    found = set(re.findall(r"photocraft-draw ([a-z-]+)", DOC.read_text(encoding="utf-8")))
    assert found <= commands
    assert "workflow.yaml" in (BASE / "skills/photocraft-draw/SKILL.md").read_text(encoding="utf-8")
    assert "workflow.yaml" in (BASE / "README.md").read_text(encoding="utf-8")
