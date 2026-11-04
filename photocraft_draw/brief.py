# -*- coding: utf-8 -*-
"""画面稿：把绘制方案翻译成生图提示词。

绘制方案里的图层顺序就是遮挡顺序，后面的层压在前面的层上。这里按
从远到近的顺序把每层的描述串成一段话：中文给用户确认，英文给生图模型。
代码只负责组装，不做翻译，所以方案里要同时写好中文和英文描述。

用法：
    from photocraft_draw.brief import build_brief
    info = build_brief(load_plan("plans/alpine-crossing.json"))
    print(info["zh"])
"""
from __future__ import annotations

from .facing import FACE_EN, FACE_TEXT
from .motion import ACTION_EN, ACTION_TEXT
from .plan import load_plan, ordered_layers

FIELDS = (
    ("subject", "主体", "Subject"),
    ("style", "风格", "Style"),
    ("light", "光线", "Lighting"),
    ("mood", "氛围", "Mood"),
    ("camera", "视角", "Viewpoint"),
    ("palette", "色调", "Palette"),
)


def _motion_note(layer: dict, lang: str) -> str:
    """把这一层的动作声明拼成一句话。

    动作意图必须进画面稿。生图模型看不到方案里的关节表，只看得到稿子，
    稿子里不写方向，模型就自己编，编出来的多半是两个人一起站着。
    """
    motion = layer.get("motion")
    if not isinstance(motion, dict):
        return ""
    action = str(motion.get("action", ""))
    if lang == "zh":
        text = ACTION_TEXT.get(action, action)
    else:
        text = ACTION_EN.get(action, action)
    angle = motion.get("angle")
    if angle is None:
        return text
    return f"{text}（{float(angle):.0f} 度）" if lang == "zh" else f"{text} ({float(angle):.0f} degrees)"


def _facing_note(layer: dict, lang: str) -> str:
    """把这一层的朝向声明拼成一句话。

    朝向必须进画面稿。生图模型看不到关节表，只看得到稿子。稿子里不写
    朝向，模型就自己编，编出来的多半是两人转身对着打，观众看见两个背影。
    """
    for item in layer.get("components") or []:
        if item.get("component") != "figure_rig":
            continue
        face = (item.get("params") or {}).get("face")
        if not isinstance(face, str):
            continue
        if lang == "zh":
            return FACE_TEXT.get(face, "")
        return FACE_EN.get(face, "")
    return ""


def _describe(layer: dict, lang: str) -> str:
    text = layer.get(f"describe_{lang}")
    if not text:
        name = layer.get("name", "")
        names = [str(item.get("component", "")) for item in layer.get("components") or []]
        joined = "、".join(names) if lang == "zh" else ", ".join(names)
        text = f"{name}（{joined}）" if lang == "zh" else f"{name} ({joined})"
    text = str(text).strip()
    notes = [note for note in (_motion_note(layer, lang), _facing_note(layer, lang)) if note]
    if not notes:
        return text
    joined = "，".join(notes) if lang == "zh" else ", ".join(notes)
    return f"{text}，{joined}" if lang == "zh" else f"{text}, {joined}"


def _header(brief: dict, lang: str) -> str:
    lines = []
    for key, zh_label, en_label in FIELDS:
        value = brief.get(f"{key}_{lang}") or brief.get(key)
        if not value:
            continue
        label = zh_label if lang == "zh" else en_label
        lines.append((label, str(value).strip()))
    return lines


def _entries(plan: dict) -> list[dict]:
    """把图层和角色按遮挡顺序排成一条，角色插在 before 指定的层之前。"""
    layers = ordered_layers(plan)
    if not layers:
        raise ValueError("画面稿需要 layers，扁平 components 没有前后顺序")
    actors = plan.get("actors") or []
    used = set()
    entries = []
    for index, layer in enumerate(layers):
        name = str(layer.get("name", f"第 {index + 1} 层"))
        for actor_index, actor in enumerate(actors):
            if actor.get("before") != name:
                continue
            entries.append({
                "name": str(actor.get("name", "角色")),
                "zh": str(actor.get("describe_zh", "")).strip(),
                "en": str(actor.get("describe_en", "")).strip(),
                "actor": True,
            })
            used.add(actor_index)
        entries.append({
            "name": name,
            "zh": _describe(layer, "zh"),
            "en": _describe(layer, "en"),
            "actor": False,
        })
    for actor_index, actor in enumerate(actors):
        if actor_index in used:
            continue
        entries.append({
            "name": str(actor.get("name", "角色")),
            "zh": str(actor.get("describe_zh", "")).strip(),
            "en": str(actor.get("describe_en", "")).strip(),
            "actor": True,
        })
    return entries


def build_brief(plan: dict) -> dict:
    """把方案翻译成中文稿和英文稿。"""
    entries = _entries(plan)
    names = [entry["name"] for entry in entries]

    brief_zh = plan.get("brief_zh") or {}
    brief_en = plan.get("brief_en") or {}

    zh_lines = []
    for label, value in _header(brief_zh, "zh"):
        zh_lines.append(f"{label}：{value}")
    zh_lines.append("画面从远到近分 %d 层，依次是：" % len(entries))
    for index, entry in enumerate(entries):
        zh_lines.append(f"{index + 1}. {entry['zh']}")
    zh_lines.append(
        "遮挡关系：%s 各层从后往前叠，后一层挡住前一层；最前面的是%s。"
        % ("、".join(names), names[-1])
    )
    if plan.get("canvas"):
        width, height = plan["canvas"]
        zh_lines.append(f"画幅：{width}×{height}。")

    en_lines = []
    for label, value in _header(brief_en, "en"):
        en_lines.append(f"{label}: {value}")
    en_lines.append(f"The scene is built in {len(entries)} depth layers, from far to near:")
    for index, entry in enumerate(entries):
        en_lines.append(f"{index + 1}. {entry['en']}")
    en_lines.append(
        "Occlusion: the layers stack back to front, each nearer layer covering the one behind it; "
        f"the closest is {entries[-1]['en']}. "
    )
    if plan.get("canvas"):
        width, height = plan["canvas"]
        en_lines.append(f"Canvas {width}x{height}.")

    return {
        "name": plan.get("name", "未命名画面"),
        "layers": entries,
        "zh": "\n".join(zh_lines),
        "en": " ".join(en_lines).strip(),
    }


def main(argv=None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="把绘制方案翻译成生图提示词")
    parser.add_argument("plan")
    parser.add_argument("--out-zh")
    parser.add_argument("--out-en")
    args = parser.parse_args(argv)

    info = build_brief(load_plan(args.plan))
    print("=== 中文稿 ===")
    print(info["zh"])
    print()
    print("=== 英文稿 ===")
    print(info["en"])
    if args.out_zh:
        from pathlib import Path
        Path(args.out_zh).write_text(info["zh"], encoding="utf-8")
    if args.out_en:
        from pathlib import Path
        Path(args.out_en).write_text(info["en"], encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
