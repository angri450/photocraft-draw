# -*- coding: utf-8 -*-
"""包络检查：用两条轮廓夹住图形，不写死规则。

思路来自你提的那个办法：先画一个标准人形或马形，再画一条收紧的轮廓。
所有部件的顶点必须落在外轮廓里面；只要落进去，不管它具体是几个矩形、
什么角度，都算这个形状。比一条条写"头必须在躯干上方"聪明，也更宽容。

轮廓用归一化坐标：原点在肩部，身高或肩高按 1.0 算，y 向下为正。
"""
from __future__ import annotations

# 人形外轮廓：头顶到脚底正好一个身高，原点在肩部
PERSON_OUTLINE = (
    (-0.14, -0.32), (0.14, -0.32), (0.16, -0.10), (0.32, 0.02),
    (0.34, 0.44), (0.24, 0.50), (0.24, 0.72), (0.26, 0.74),
    (-0.26, 0.74), (-0.24, 0.72), (-0.24, 0.50), (-0.34, 0.44),
    (-0.32, 0.02), (-0.16, -0.10),
)

# 人形内轮廓：收进一圈，用来判断"够不够胖"
PERSON_INNER = (
    (-0.09, -0.27), (0.09, -0.27), (0.11, -0.08), (0.22, 0.04),
    (0.24, 0.42), (0.16, 0.48), (0.16, 0.64), (-0.16, 0.64),
    (-0.16, 0.48), (-0.24, 0.42), (-0.22, 0.04), (-0.11, -0.08),
)

# 马形外轮廓：按总高 1.0 归一（头顶到蹄），朝右
HORSE_OUTLINE = (
    (0.04, -0.46), (0.28, -0.52), (0.46, -0.42), (0.60, -0.48),
    (0.78, -0.42), (0.80, -0.24), (0.70, -0.08), (0.46, -0.04),
    (0.32, 0.08), (0.28, 0.20), (0.30, 0.70), (0.16, 0.70),
    (0.12, 0.20), (-0.30, 0.20), (-0.28, 0.70), (-0.42, 0.70),
    (-0.46, 0.16), (-0.62, 0.02), (-0.64, -0.28), (-0.46, -0.42),
    (-0.18, -0.46),
)

HORSE_INNER = (
    (0.08, -0.40), (0.28, -0.46), (0.44, -0.36), (0.58, -0.42),
    (0.72, -0.36), (0.72, -0.22), (0.64, -0.10), (0.42, -0.06),
    (0.28, 0.06), (0.22, 0.18), (0.24, 0.60), (0.14, 0.60),
    (0.08, 0.18), (-0.26, 0.18), (-0.24, 0.60), (-0.36, 0.60),
    (-0.40, 0.14), (-0.56, 0.02), (-0.58, -0.26), (-0.42, -0.40),
    (-0.16, -0.40),
)

# 椭圆包络：比多边形宽容，也更符合"内外两层圆"的说法
# center 是中心相对肩部的偏移，rx/ry 是外椭圆半径，inner 是内层比例
ENVELOPES = {
    "person": {"center": (0.0, 0.12), "rx": 0.48, "ry": 0.62, "inner": 0.55},
    "horse": {"center": (0.04, 0.10), "rx": 0.82, "ry": 0.68, "inner": 0.5},
}


def point_in_polygon(x: float, y: float, polygon) -> bool:
    """射线法判断点是否在多边形内。"""
    inside = False
    count = len(polygon)
    for index in range(count):
        x1, y1 = polygon[index]
        x2, y2 = polygon[(index + 1) % count]
        if (y1 > y) != (y2 > y):
            cross = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < cross:
                inside = not inside
    return inside


def _corners(box):
    x1, y1, x2, y2 = box
    return [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]


def _to_canvas(polygon, origin, scale):
    ox, oy = origin
    return [(ox + x * scale, oy + y * scale) for x, y in polygon]


def check_envelope(parts, kind: str, origin, scale: float) -> dict:
    """按椭圆包络检查：部件中心要落在外椭圆里，且有一部分落进内椭圆。

    origin 是肩部在画布上的位置，scale 是总高的像素值。
    """
    if kind not in ENVELOPES:
        raise ValueError(f"没有这套包络：{kind}，可选 {', '.join(ENVELOPES)}")
    spec = ENVELOPES[kind]
    ox, oy = origin
    cx = ox + spec["center"][0] * scale
    cy = oy + spec["center"][1] * scale
    rx = spec["rx"] * scale
    ry = spec["ry"] * scale

    problems = []
    outside = []
    reaching_inner = 0

    for part in parts:
        # 只看部件中心：姿态摆动时角会伸出去，中心仍在形状里
        px = (part["bbox"][0] + part["bbox"][2]) / 2
        py = (part["bbox"][1] + part["bbox"][3]) / 2
        d = (((px - cx) / rx) ** 2 + ((py - cy) / ry) ** 2) ** 0.5
        if d > 1.0:
            outside.append(f"{part['name']} 的中心 ({px:.0f},{py:.0f}) 出了外轮廓，距离 {d:.2f}")
        if d < spec["inner"]:
            reaching_inner += 1

    if outside:
        problems.extend(outside[:4])
        if len(outside) > 4:
            problems.append(f"另有 {len(outside) - 4} 个部件出界")

    if reaching_inner == 0:
        problems.append("没有任何部件落在内轮廓里，形状太瘦或位置偏了")
    elif reaching_inner == len(parts):
        problems.append("所有部件都缩在内层，整体太小，撑不满包络")

    return {
        "ok": not problems,
        "kind": kind,
        "parts": len(parts),
        "inner_hits": reaching_inner,
        "problems": problems,
    }


def envelope_text(result: dict) -> str:
    status = "检查通过" if result["ok"] else "检查未通过"
    return (f"{status} | {result['kind']} 包络 | {result['parts']} 个部件 | "
            f"{result['inner_hits']} 个落在内层" +
            ("".join(f"\n  - {item}" for item in result["problems"])))
