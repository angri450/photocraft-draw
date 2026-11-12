# -*- coding: utf-8 -*-
"""绘制完成结构后的细节清单与多参考图分工。

白模数量不设限。一个白模可以指导整幅布局，也可以只指导一个接触点；
每份参考的职责必须写明，不能靠图1、图2约定地位。
"""
from __future__ import annotations

import json
from pathlib import Path

from .brief import build_brief

ASPECTS = {
    "identity": "主体身份、物种、年龄、五官与标志",
    "appearance": "外形、脸型、体型、毛发与表面特征",
    "costume": "衣服、甲胄、层次、覆盖与摆动",
    "props": "道具、兵器、附件、数量与头尾形制",
    "anatomy": "骨架、四肢、手势、重心与姿态自然度",
    "material": "金属、织物、皮毛、云雾等表面质感",
    "expression": "表情、神态与情绪",
    "pattern": "纹样、皮毛花纹、织纹与装饰",
    "contact": "触碰、握持、交叠、遮挡与咬合",
    "pose": "站位、朝向、关节与受力方向",
    "geometry": "构图、透视、布局、留白与镜头",
    "colour": "色彩种类、面积、明暗与冷暖分工",
    "light": "光源、受光面、阴影与空气透视",
    "style": "线条、媒介、上色方式与细节密度",
    "text": "后期文字与版式",
    "continuity": "多格的角色、服制、道具与环境连续性",
}

REFERENCE_ROLES = {
    "pose": "站位、朝向、关节与受力方向",
    "geometry": "构图、透视、布局、留白与镜头",
    "layout": "整体构图与对象位置",
    "anatomy": "姿态、关节与受力",
    "contact": "握持、碰撞、咬合与遮挡",
    "identity": "主体身份与典型识别特征",
    "costume": "服制、甲胄与层次的覆盖关系",
    "props": "道具形状、归属与头尾形制",
    "colour": "色彩种类、面积、明暗与饱和度",
    "material": "表面材质与纹理",
    "style": "线条、媒介和上色方法",
    "pattern": "纹样的造型与分布",
}

PRIORITIES = {"primary": "当前主要矛盾", "preserve": "保留已成立的效果", "support": "次要指导"}

# identity 等属性描述「是什么」；这两类描述「怎么验收」与「不得出现」。
ASPECTSProps = set(ASPECTS) | {"reject", "acceptance"}
ASPECT_LABELS = {"reject": "不得出现", "acceptance": "验收标准"}
REFERENCE_SOURCES = {"whitebox": "几何白模", "character-sheet": "角色造型卡", "palette": "色彩参考", "photo": "照片参考", "other": "其他参考"}


def _text(value, where, errors):
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{where}必须是非空文字")
        return ""
    return value.strip()


def _items(value, where, errors):
    if isinstance(value, str):
        if not value.strip():
            errors.append(f"{where}不能是空字符串")
            return []
        return [value.strip()]
    if not isinstance(value, list) or not value or any(not isinstance(v, str) or not v.strip() for v in value):
        errors.append(f"{where}必须是非空的文字数组")
        return []
    return [v.strip() for v in value]


def targets(plan):
    """返回层名及角色名，让细节对象有结构归属，避免各说各话。"""
    result = [str(x.get("name")) for x in plan.get("layers", [])
              if isinstance(x, dict) and x.get("name")]
    result += [str(x.get("name")) for x in plan.get("actors", [])
               if isinstance(x, dict) and x.get("name")]
    seen = set()
    return [name for name in result if name not in seen and not seen.add(name)]


def validate_details(plan):
    """检查细节清单结构，但不要求为每种细节都造组件，也不要求全填。"""
    errors = []
    raw = plan.get("details")
    if raw is not None and not isinstance(raw, dict):
        errors.append("details 必须是对象")
    raw = raw if isinstance(raw, dict) else {}
    known = targets(plan)
    seen = set()
    for index, entry in enumerate(raw.get("subjects", [])):
        where = f"details.subjects[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{where}必须是对象")
            continue
        target = _text(entry.get("target"), where + ".target", errors)
        if target and target not in known:
            errors.append(f"{where}.target「{target}」不在已有图层或演员里")
        if target in seen:
            errors.append(f"细节对象「{target}」重复")
        seen.add(target)
        aspects = entry.get("aspects", {})
        if not isinstance(aspects, dict):
            errors.append(f"{where}.aspects 必须是对象")
            continue
        for kind, value in aspects.items():
            if kind not in ASPECTSProps:
                errors.append(f"{where}.aspects 有未知属性：{kind}")
            _items(value, f"{where}.aspects.{kind}", errors)
        if entry.get("priority") is not None and entry.get("priority") not in PRIORITIES:
            errors.append(f"{where}.priority 从 primary/preserve/support 选一个")
        if entry.get("reject") is not None:
            _items(entry.get("reject"), where + ".reject", errors)
        if entry.get("acceptance") is not None:
            _items(entry.get("acceptance"), where + ".acceptance", errors)
    for index, reference in enumerate(raw.get("references", [])):
        where = f"details.references[{index}]"
        if not isinstance(reference, dict):
            errors.append(f"{where}必须是对象")
            continue
        if reference.get("source") is not None and reference.get("source") not in REFERENCE_SOURCES:
            errors.append(f"{where}.source 只有在记里的几何白模或造型图种类")
        roles = _items(reference.get("roles"), where + ".roles", errors)
        for role in roles:
            if role not in REFERENCE_ROLES:
                errors.append(f"{where}.roles 有未知职责：{role}")
        if not reference.get("path") and not reference.get("url"):
            errors.append(f"{where} 要指定本地 path 或外部参考 url")
        targets_value = _items(reference.get("targets", ["*"]), where + ".targets", errors)
        for target in targets_value:
            if target != "*" and target not in known and not any(
                isinstance(entry, dict) and entry.get("name") == target
                for entry in raw.get("subjects", [])):
                errors.append(f"{where}.targets 引用了没有的「{target}」")
        if reference.get("priority") is not None and reference.get("priority") not in PRIORITIES:
            errors.append(f"{where}.priority 从 primary/preserve/support 选一个")
        if "instruction" in reference:
            _text(reference.get("instruction"), where + ".instruction", errors)
        if reference.get("avoid") is not None:
            _items(reference.get("avoid"), where + ".avoid", errors)
    return errors


def _accept(entry):
    return entry.get("acceptance") or []


def build_details(plan):
    """返回层级和参考图报告；放在画稿前供人识别当前主次，不做预检脚本。"""
    raw = plan.get("details") or {}
    known = targets(plan)
    subjects = []
    for entry in raw.get("subjects", []):
        facets = []
        for key, values in (entry.get("aspects") or {}).items():
            facets.append({"kind": key, "meaning": ASPECTS.get(key, key), "items": values})
        subjects.append({
            "target": entry.get("target"),
            "layer": next((layer for layer in plan.get("layers", [])
                          if layer.get("name") == entry.get("target")), None),
            "priority": entry.get("priority", "support"),
            "priority_zh": PRIORITIES[entry.get("priority", "support")],
            "aspects": facets,
            "reject": entry.get("reject") or [],
            "acceptance": _accept(entry),
        })
    ordered_subjects = sorted(subjects, key=lambda x: {"primary": 0, "support": 1, "preserve": 2}[x["priority"]])
    references = []
    for index, entry in enumerate(raw.get("references", []), 1):
        ref_dir = Path(plan.get("_plan_dir", "."))
        path = entry.get("path")
        resolved = entry.get("url")
        mime_type = entry.get("mime_type")
        if path:
            image = Path(path) if Path(path).is_absolute() else ref_dir / path
            image = image.resolve()
            if not image.is_file():
                raise FileNotFoundError(f"细节参考图不存在：{image}")
            resolved = str(image)
            if not mime_type:
                mime_type = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                             ".webp": "image/webp"}.get(image.suffix.lower())
        references.append({
            "id": f"ref-{index}",
            "kind": "path" if path else "url",
            "path": str(Path(path)) if path else None,
            "url": resolved,
            "roles": entry.get("roles") or [],
            "role_meanings": [REFERENCE_ROLES[x] for x in entry.get("roles", []) if x in REFERENCE_ROLES],
            "targets": entry.get("targets") or ["*"],
            "instruction": entry.get("instruction"),
            "avoid": entry.get("avoid") or [],
            "priority": entry.get("priority", "support"),
            "source": entry.get("source", "other"),
            "source_label": REFERENCE_SOURCES[entry.get("source", "other")],
            "mime_type": mime_type,
        })
    return {"subjects": ordered_subjects, "references": references}


def reference_labels(references):
    """只写参考画面的职责，不写流程动作。"""
    blocks = []
    for i, ref in enumerate(references, 1):
        lines = [f"Reference image {i}: use {', '.join(ref['roles'])} for {', '.join(ref['targets'])} only."]
        if ref.get("instruction"):
            lines.append(str(ref["instruction"]))
        if ref.get("avoid"):
            lines.append("Exclude " + "; ".join(ref["avoid"]) + ".")
        blocks.append("\n".join(lines))
    return blocks


def detail_brief(plan, lang="en"):
    """对象可见属性，优先级和验收只供流程使用。"""
    data = build_details(plan)
    lines = []
    if lang == "zh":
        for subject in data["subjects"]:
            for facet in subject["aspects"]:
                if facet["kind"] != "acceptance":
                    meaning = ASPECT_LABELS.get(facet["kind"], facet["meaning"])
                    lines.append(f"{subject['target']}的{meaning}：" + "；".join(facet["items"]))
            lines.extend(f"{subject['target']}不应出现：{item}" for item in subject["reject"])
        for i, ref in enumerate(data["references"], 1):
            items = [f"参考图{i}：" + "、".join(ref["role_meanings"]) + "，作用于" + "、".join(ref["targets"])]
            if ref.get("instruction"):
                items.append(ref["instruction"])
            if ref.get("avoid"):
                items.append("不要采用：" + "；".join(ref["avoid"]))
            lines.extend(items)
        return "\n".join(lines)
    for subject in data["subjects"]:
        for facet in subject["aspects"]:
            if facet["kind"] != "acceptance":
                lines.append(f"{subject['target']} {facet['kind']}: " + "; ".join(facet["items"]))
        lines.extend(f"{subject['target']} exclude: {item}." for item in subject["reject"])
    lines.extend(reference_labels(data["references"]))
    return "\n".join(lines)


def combine_brief(normal_brief, plan, lang="en"):
    """有对象细节就只交场景与对象说明，不重复逐层画稿。"""
    errors = validate_details(plan)
    if errors:
        raise ValueError("细节规划有问题：" + "; ".join(errors))
    raw = plan.get("details") or {}
    if not raw.get("subjects"):
        return normal_brief
    return "\n".join(str(part) for part in [raw.get("scene") or raw.get("scenario"), detail_brief(plan, lang)] if part)


def visual_handoff(plan):
    """通用画面交接，没有模型、上传或请求参数。"""
    return {"description": combine_brief(build_brief(plan)["en"], plan),
            "canvas": plan.get("canvas") or [1, 1],
            "references": build_details(plan)["references"]}
