# -*- coding: utf-8 -*-
"""定位 image-prompt 内的 MOSS 官方编译器。

通用提示词技能承载四个模型的说明，本模块只消费 MOSS 的编译器。
优先位置是 IMAGE_PROMPT_HOME，再是工作区和用户 skills/image-prompt。
旧环境变量 MOSS_PROMPT_ENHANCER 与旧目录作为兼容路径保留。
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path

SKILL_NAME = "image-prompt"


def skill_home() -> Path:
    """返回含 scripts/compile_prompt.py 的技能目录。"""
    candidates = []
    for key in ("IMAGE_PROMPT_HOME", "MOSS_PROMPT_ENHANCER"):
        if os.environ.get(key):
            candidates.append(Path(os.environ[key]))
    candidates.append(Path(__file__).resolve().parent.parent / "skills" / SKILL_NAME)
    workspace = os.environ.get("MAVIS_WORKSPACE") or os.environ.get("WORKSPACE")
    if workspace:
        candidates.append(Path(workspace) / "skills" / SKILL_NAME)
    candidates.extend([
        Path("D:/agent2/skills") / SKILL_NAME,
        Path.home() / ".minimax" / "skills" / SKILL_NAME,
        Path.home() / ".minimax" / "skills" / "moss-image-prompt-enhancer",
        Path("D:/agent2/skills") / "moss-image-prompt-enhancer",
    ])
    for candidate in candidates:
        if (candidate.expanduser() / "scripts" / "compile_prompt.py").is_file():
            return candidate
    raise FileNotFoundError(
        "找不到 image-prompt/scripts/compile_prompt.py；"
        "请设置 IMAGE_PROMPT_HOME 指向技能目录，或把技能放进工作区 skills"
    )


def _compiler(custom_home: Path | None = None):
    home = custom_home or skill_home()
    path = home / "scripts" / "compile_prompt.py"
    if not path.is_file():
        raise FileNotFoundError(f"技能编译器不存在：{path}")
    spec = importlib.util.spec_from_file_location("moss_prompt_compiler_official", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"读不了技能编译器：{path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.compile_prompt


def compile_layout(draft: dict, custom_home: Path | None = None) -> str:
    """仅编译 MOSS-Image 草稿；其他模型不套用中心坐标约定。"""
    return _compiler(custom_home)(draft)
