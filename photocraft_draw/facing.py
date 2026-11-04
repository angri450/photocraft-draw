# -*- coding: utf-8 -*-
"""演出朝向：角色把哪一面给观众看。

动作状态定的是谁往哪个方向使劲，朝向定的是身体的正面朝哪边。两者是不同
的事：一个人可以往下压，同时侧着身对着对手。

朝向必须写进方案。figure_rig 画的是关节、骨段和一个头椭圆，正面和背面
在几何上分不出来：正面和背面的肩一样宽，白模里也没有脸。没有脸就没有
正反面。方案里不写，生图模型就自己编，编出来的多半是两人转身互相砍，
背对观众。

这一层查三件事。

一，声明的朝向和关节表对不对得上。肩宽、头位、颈躯拧角三样能验：正面
朝观众的人两肩要展开，头要正对身体中线，脖子不能拧着。

二，背对观众。项目规矩是禁止背场，报出来由作者定夺。

三，没声明朝向的角色。跟 motion 一样，这一层不写不算错，报告里列出来。

用法：
    photocraft-draw facing plans/a.json
    photocraft-draw facing plans/a.json --json out/facing.json
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from .components.rig import FACE_WORDS
from .motion import _pose_table

FACE_TEXT = {
    "front": "正面朝观众，胸肩打开",
    "left": "侧身转向画面左侧",
    "right": "侧身转向画面右侧",
    "back": "背对观众",
}

FACE_EN = {
    "front": ("facing the audience squarely, chest and shoulders open to the "
              "viewer, face fully visible"),
    "left": "turned to the left, three-quarter view toward the viewer",
    "right": "turned to the right, three-quarter view toward the viewer",
    "back": "seen from behind",
}

# 正面朝观众的人，肩要展开。肩宽占身高的下限。
FRONT_SPAN_MIN = 0.18

# 头要正对身体中线，允许的横向偏移上限，占身高的比例。
FRONT_HEAD_MAX = 0.07

# 脖子和躯干不能拧着，转身的拧角上限，单位度。
FRONT_TWIST_MAX = 15.0

# 正面朝观众的人，躯干要立着。躯干偏离竖直超过这个数，读作侧身或者背对观众。
FRONT_TORSO_MAX = 20.0

# 正面朝观众的人，两肩要一样高。肩线一高一低，读作身子转过去了。
FRONT_SHOULDER_LEVEL = 0.04


def _tilt(vector):
    """向量跟竖直方向的夹角。0 度是正上，90 度是水平。"""
    return abs(math.degrees(math.atan2(vector[0], -vector[1])))


def _measure(joints: dict, height: float) -> dict:
    """从关节表量出朝向能验的三样：肩宽、头位、颈躯拧角。"""
    shoulder_l = joints["shoulder_l"]
    shoulder_r = joints["shoulder_r"]
    center_x = (shoulder_l[0] + shoulder_r[0]) / 2
    span = abs(shoulder_r[0] - shoulder_l[0])
    head = joints["head"]
    chest = joints["chest"]
    hip = joints["hip"]
    torso = (chest[0] - hip[0], chest[1] - hip[1])
    neck = (head[0] - chest[0], head[1] - chest[1])
    torso_tilt = _tilt(torso)
    neck_tilt = _tilt(neck)
    return {
        "span": span,
        "span_ratio": span / height,
        "head_off": abs(head[0] - center_x),
        "head_off_ratio": abs(head[0] - center_x) / height,
        "torso_tilt": torso_tilt,
        "neck_tilt": neck_tilt,
        "twist": abs(torso_tilt - neck_tilt),
        "shoulder_level": abs(shoulder_r[1] - shoulder_l[1]) / height,
    }


def _figures(plan: dict) -> list:
    """方案里每个人物白模，带绝对关节坐标和朝向声明。"""
    out = []
    for layer in plan.get("layers") or []:
        for item in layer.get("components") or []:
            if item.get("component") != "figure_rig":
                continue
            params = item.get("params") or {}
            table = _pose_table(params.get("pose", "stand"))
            if params.get("flip"):
                table = {name: (-x, y) for name, (x, y) in table.items()}
            ox, oy = float(params["root"][0]), float(params["root"][1])
            height = float(params["height"])
            joints = {name: (ox + x * height, oy + y * height)
                      for name, (x, y) in table.items()}
            face = params.get("face")
            out.append({
                "layer": str(layer.get("name", "")),
                "joints": joints,
                "height": height,
                "face": str(face) if isinstance(face, str) else None,
            })
    return out


def analyze_plan(plan: dict) -> dict:
    """读方案，量出每个角色给观众看的朝向。"""
    characters = []
    undeclared = []
    for figure in _figures(plan):
        layer = figure["layer"]
        face = figure["face"]
        measure = _measure(figure["joints"], figure["height"])
        issues = []
        if face is None:
            undeclared.append(layer)
        elif face not in FACE_WORDS:
            issues.append({
                "kind": "facing_unknown",
                "text": "%s 的朝向「%s」不在词表里，可用的是：%s"
                        % (layer, face, "、".join(FACE_WORDS)),
            })
        elif face == "back":
            issues.append({
                "kind": "facing_back",
                "text": "%s 背对观众，项目规矩禁止背场" % layer,
            })
        elif face == "front":
            if measure["span_ratio"] < FRONT_SPAN_MIN:
                issues.append({
                    "kind": "facing_span",
                    "text": ("%s 声明正面朝观众，肩宽只有 %.0f 像素，身高的 %.0f%%，"
                             "读作侧身" % (layer, measure["span"],
                                          measure["span_ratio"] * 100)),
                })
            if measure["head_off_ratio"] > FRONT_HEAD_MAX:
                issues.append({
                    "kind": "facing_head",
                    "text": ("%s 声明正面朝观众，头偏出身体中线 %.0f 像素，"
                             "读作扭头或者转身" % (layer, measure["head_off"])),
                })
            if measure["twist"] > FRONT_TWIST_MAX:
                issues.append({
                    "kind": "facing_twist",
                    "text": ("%s 声明正面朝观众，脖子和躯干拧了 %.1f 度，"
                             "读作转着身子" % (layer, measure["twist"])),
                })
            if measure["torso_tilt"] > FRONT_TORSO_MAX:
                issues.append({
                    "kind": "facing_torso",
                    "text": ("%s 声明正面朝观众，躯干偏离竖直 %.1f 度，"
                             "读作侧着身子或者背对观众"
                             % (layer, measure["torso_tilt"])),
                })
            if measure["shoulder_level"] > FRONT_SHOULDER_LEVEL:
                issues.append({
                    "kind": "facing_shoulder",
                    "text": ("%s 声明正面朝观众，两肩一高一低，高差 %.0f 像素，"
                             "读作身子转过去了"
                             % (layer, measure["shoulder_level"] * figure["height"])),
                })
        characters.append({
            "layer": layer,
            "face": face,
            "height": figure["height"],
            "face_text": FACE_TEXT.get(face, ""),
            "span": round(measure["span"], 1),
            "span_ratio": round(measure["span_ratio"], 3),
            "head_off": round(measure["head_off"], 1),
            "head_off_ratio": round(measure["head_off_ratio"], 3),
            "torso_tilt": round(measure["torso_tilt"], 1),
            "neck_tilt": round(measure["neck_tilt"], 1),
            "twist": round(measure["twist"], 1),
            "torso_tilt": round(measure["torso_tilt"], 1),
            "shoulder_level": round(measure["shoulder_level"], 3),
            "issues": issues,
        })
    return {"characters": characters, "undeclared": undeclared}


def report(result: dict) -> str:
    lines = ["角色朝向："]
    if not result["characters"]:
        lines.append("  方案里没有人物白模")
    for character in result["characters"]:
        if character["face"] is None:
            lines.append("  %s：未声明朝向" % character["layer"])
        else:
            lines.append("  %s：%s" % (character["layer"], character["face_text"]))
        lines.append("     肩宽 %.0f 像素（身高的 %.0f%%），头偏出身体中线 %.0f 像素，"
                     "颈与躯干拧 %.1f 度，躯干偏离竖直 %.1f 度，两肩高差 %.0f 像素"
                     % (character["span"], character["span_ratio"] * 100,
                        character["head_off"], character["twist"],
                        character["torso_tilt"],
                        character["shoulder_level"] * character["height"]))
    issues = []
    for character in result["characters"]:
        for issue in character["issues"]:
            issues.append(issue["text"])
    if issues:
        lines.append("")
        lines.append("朝向提示：")
        for text in issues:
            lines.append("  " + text)
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="检查角色给观众看的朝向")
    parser.add_argument("plan", help="绘制方案文件")
    parser.add_argument("--json", help="结构化结果输出路径")
    args = parser.parse_args(argv)

    from .plan import load_plan

    result = analyze_plan(load_plan(args.plan))
    print(report(result))
    if args.json:
        Path(args.json).write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
