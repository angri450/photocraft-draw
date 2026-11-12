"""从方案的画面说明中读取整体描述。"""
from __future__ import annotations


def caption_from_plan(plan: dict) -> str:
    """优先使用作者的整体描述，其余按已有图层说明写清画面。"""
    for key in ("scene_caption", "caption_en"):
        if plan.get(key):
            return str(plan[key])
    brief = plan.get("brief_en") or {}
    if isinstance(brief, dict):
        values = [str(brief[key]).strip() for key in
                  ("subject", "style", "light", "camera", "palette")
                  if str(brief.get(key) or "").strip()]
        if values:
            return ", ".join(values)
    roles = [str(layer["describe_en"]).strip()
             for layer in plan.get("layers", [])
             if str(layer.get("describe_en") or "").strip()]
    if roles:
        return ". ".join(roles)
    chinese = [str(layer["describe_zh"]).strip()
               for layer in plan.get("layers", [])
               if str(layer.get("describe_zh") or "").strip()]
    if chinese:
        return "；".join(chinese)
    brief_zh = plan.get("brief_zh") or {}
    if isinstance(brief_zh, dict) and str(brief_zh.get("subject") or "").strip():
        return str(brief_zh["subject"])
    return "按绘制方案中的实际对象、位置和层次表达画面"
