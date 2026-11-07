# -*- coding: utf-8 -*-
"""复刻两幅名画的空间布局：蒙娜丽莎、呐喊。

只复刻构图，不追笔触。所有形状用自定义路径拼，人物是简化剪影，
目的是验证场景方案能不能撑起「有透视、有前后、有视觉中心」的画面。

    python3 tools/remake_masterpieces.py
    photocraft-draw draw plans/mona-lisa.json --png out/mona-lisa.png
    photocraft-draw draw plans/the-scream.json --png out/the-scream.png
"""
from __future__ import annotations

import json
import math
from pathlib import Path

W, H = 900, 1200


def knots(points, smooth=False):
    """直边多边形或平滑曲线。smooth 时用切线手柄。"""
    if not smooth:
        return [{"anchor": [x, y], "in": [x, y], "out": [x, y]} for x, y in points]
    result = []
    total = len(points)
    for index, (x, y) in enumerate(points):
        px, py = points[(index - 1) % total]
        nx, ny = points[(index + 1) % total]
        tx, ty = nx - px, ny - py
        norm = math.hypot(tx, ty) or 1.0
        tx, ty = tx / norm, ty / norm
        span = 0.34 * (math.hypot(x - nx, y - ny) + math.hypot(x - px, y - py)) * 0.5
        result.append({"anchor": [x, y], "in": [x - tx * span, y - ty * span],
                       "out": [x + tx * span, y + ty * span]})
    return result


def shape(points, fill, name, closed=True, smooth=False, stroke=None, width=None):
    params = {"subpaths": [{"closed": closed, "knots": knots(points, smooth)}],
              "fill": fill, "name": name}
    if stroke:
        params["stroke"] = stroke
        params["stroke_width"] = width or 1.0
    return {"component": "custom_shape", "params": params}


def layer(name, depth, z, components, describe_zh=""):
    return {"name": name, "depth": depth, "z": z,
            "describe_zh": describe_zh, "components": components}


def mona_lisa():
    layers = []
    # 天空：上冷下暖，三层平涂
    layers.append(layer("天空", 5, 500, [
        shape([(0, 0), (900, 0), (900, 300), (0, 320)], "#A9BFB2", "天空上"),
        shape([(0, 300), (900, 290), (900, 420), (0, 430)], "#C2C3A8", "天空下"),
    ]))
    # 远山：左右两段，右侧更高，制造空气透视
    layers.append(layer("远山", 4, 400, [
        shape([(0, 430), (90, 400), (170, 425), (260, 390), (340, 420), (420, 405),
               (520, 430), (620, 400), (720, 420), (820, 392), (900, 410),
               (900, 470), (0, 480)], "#7E8C77", "远山"),
        shape([(0, 470), (900, 470), (900, 540), (0, 545)], "#8E9472", "中景坡地"),
    ]))
    # 左侧河流与右侧道路，都是透视引导线
    layers.append(layer("水与路", 3, 300, [
        shape([(0, 505), (40, 500), (95, 520), (150, 500), (210, 528), (268, 512),
               (268, 536), (205, 552), (150, 524), (95, 545), (40, 524), (0, 530)],
              "#9FB3AE", "河"),
        shape([(620, 520), (700, 505), (780, 520), (860, 512), (900, 520),
               (900, 552), (820, 545), (740, 552), (660, 540), (620, 545)],
              "#C2A87A", "路"),
        shape([(0, 545), (900, 540), (900, 620), (0, 640)], "#6F7A4E", "草坡"),
    ]))
    # 阳台矮墙与两侧柱头
    layers.append(layer("矮墙", 2, 200, [
        shape([(0, 600), (900, 592), (900, 650), (0, 660)], "#6B5B45", "矮墙"),
        shape([(0, 560), (58, 556), (58, 700), (0, 706)], "#5A4A36", "左柱"),
        shape([(842, 556), (900, 552), (900, 700), (842, 704)], "#5A4A36", "右柱"),
    ]))
    # 人物：头发、脸、衣身、交叠的手
    layers.append(layer("人物", 1, 100, [
        shape([(330, 330), (300, 270), (330, 215), (390, 190), (455, 195),
               (510, 230), (530, 290), (515, 350), (480, 400), (400, 405),
               (350, 380)], "#2B2118", "头发", smooth=True),
        shape([(362, 300), (410, 272), (468, 282), (492, 330), (488, 392),
               (455, 432), (405, 436), (370, 400), (355, 345)], "#D8B58C", "脸", smooth=True),
        shape([(350, 430), (470, 420), (540, 470), (585, 560), (610, 700),
               (620, 880), (600, 980), (520, 1000), (330, 1000), (280, 960),
               (285, 830), (310, 690), (325, 540)], "#3B3226", "衣身", smooth=True),
        shape([(345, 500), (390, 470), (405, 640), (395, 850), (360, 940),
               (315, 930), (320, 760), (330, 600)], "#4A4030", "左袖", smooth=True),
        shape([(540, 500), (500, 472), (505, 650), (520, 860), (560, 950),
               (605, 935), (600, 760), (580, 610)], "#4A4030", "右袖", smooth=True),
        shape([(330, 940), (380, 910), (435, 918), (480, 940), (505, 968),
               (470, 992), (415, 980), (365, 990), (328, 970)], "#D8B58C", "手一", smooth=True),
        shape([(395, 972), (450, 958), (500, 970), (520, 1000), (492, 1022),
               (440, 1012), (398, 1002)], "#CBA57C", "手二", smooth=True),
    ]))
    return {"name": "蒙娜丽莎 · 空间布局复刻", "canvas": [W, H], "ref_width": W,
            "document_background": "#A9BFB2",
            "brief_zh": {"subject": "坐姿女子，双手交叠，身后是河流与远山",
                         "style": "平涂色块，空气透视", "camera": "正面平视",
                         "palette": "青绿 #A9BFB2、山绿 #7E8C77、衣褐 #3B3226、肤色 #D8B58C"},
            "layers": layers}


def the_scream():
    layers = []
    # 天空：三道弯曲的橙红色带
    layers.append(layer("天空", 5, 500, [
        shape([(0, 0), (900, 0), (900, 520), (0, 540)], "#D96A2B", "天空底"),
        shape([(0, 120), (160, 80), (300, 140), (420, 90), (560, 150), (700, 110),
               (900, 160), (900, 300), (700, 250), (560, 290), (420, 240),
               (300, 280), (160, 210), (0, 250)], "#E8A13C", "云带一", smooth=True),
        shape([(0, 330), (180, 290), (320, 350), (460, 300), (600, 350), (760, 310),
               (900, 350), (900, 440), (760, 420), (600, 450), (460, 410),
               (320, 450), (180, 400), (0, 430)], "#F2C96B", "云带二", smooth=True),
    ]))
    # 峡湾水面
    layers.append(layer("水面", 4, 400, [
        shape([(0, 540), (900, 520), (900, 1200), (0, 1200)], "#2F4B5E", "水"),
        shape([(0, 700), (220, 680), (420, 700), (620, 690), (820, 700), (900, 695),
               (900, 760), (700, 770), (480, 750), (260, 770), (0, 760)],
              "#3E6470", "水纹", smooth=True),
        shape([(0, 880), (240, 860), (460, 880), (700, 865), (900, 880),
               (900, 930), (680, 940), (440, 925), (220, 940), (0, 930)],
              "#356070", "水纹二", smooth=True),
    ]))
    # 桥面与栏杆：一条斜线把画面切成两半
    layers.append(layer("桥", 3, 300, [
        shape([(0, 980), (900, 610), (900, 760), (0, 1200)], "#C9A36A", "桥面"),
        shape([(0, 900), (900, 545), (900, 585), (0, 960)], "#8A5A32", "栏杆上"),
        shape([(0, 960), (900, 585), (900, 615), (0, 1010)], "#7A4A2A", "栏杆下"),
        shape([(120, 1000), (150, 985), (165, 900), (135, 912)], "#7A4A2A", "栏柱一"),
        shape([(420, 830), (450, 815), (462, 735), (432, 748)], "#7A4A2A", "栏柱二"),
        shape([(700, 705), (728, 692), (738, 620), (710, 632)], "#7A4A2A", "栏柱三"),
    ]))
    # 远处两个人影
    layers.append(layer("远人", 2, 200, [
        shape([(612, 660), (602, 605), (612, 585), (628, 588), (636, 610),
               (632, 660), (624, 668)], "#2E2A33", "远人一", smooth=True),
        shape([(676, 646), (668, 596), (678, 578), (692, 580), (700, 600),
               (696, 648), (688, 656)], "#2E2A33", "远人二", smooth=True),
    ]))
    # 主体：波浪形剪影、白脸、两只捂耳的手
    layers.append(layer("主体", 1, 100, [
        shape([(330, 690), (300, 760), (290, 860), (300, 960), (270, 1050),
               (250, 1130), (310, 1160), (360, 1120), (420, 1160), (470, 1120),
               (480, 1020), (450, 930), (460, 830), (440, 740), (400, 690)],
              "#2E2A33", "身体", smooth=True),
        shape([(330, 690), (320, 620), (345, 575), (390, 570), (420, 610),
               (415, 675), (385, 710)], "#E6D3B3", "脸", smooth=True),
        shape([(300, 645), (312, 600), (345, 585), (358, 615), (350, 670),
               (322, 690)], "#E6D3B3", "左手", smooth=True),
        shape([(418, 640), (430, 590), (458, 582), (468, 612), (458, 672),
               (430, 692)], "#E6D3B3", "右手", smooth=True),
    ]))
    return {"name": "呐喊 · 空间布局复刻", "canvas": [W, H], "ref_width": W,
            "document_background": "#D96A2B",
            "brief_zh": {"subject": "桥上捂耳尖叫的人，身后是扭曲的橙色天空和峡湾",
                         "style": "表现主义，平涂色带", "camera": "斜向透视，灭点在右侧",
                         "palette": "橙 #D96A2B、黄 #F2C96B、水蓝 #2F4B5E、桥土 #C9A36A、人影 #2E2A33"},
            "layers": layers}


def main() -> None:
    for name, plan in (("mona-lisa", mona_lisa()), ("the-scream", the_scream())):
        path = Path("plans") / (name + ".json")
        path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
        print(path)


if __name__ == "__main__":
    main()
