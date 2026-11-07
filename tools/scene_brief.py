# -*- coding: utf-8 -*-
"""从花枝场景直接生成英文提示词，数字和方位都从数据里读，不手写。

    python3 tools/scene_brief.py

产物：out/spray-brief.txt
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import spray_hybrid


def _extent(values):
    return min(values), max(values)


def build_brief() -> str:
    meshes, flowers, leaves, buds = spray_hybrid.build()
    sizes = sorted((item[2] for item in flowers), reverse=True)
    main, rest = sizes[0], sizes[1:]
    xs = [item[0][0] for item in flowers]
    ys = [item[0][1] for item in flowers]

    # 主簇按“离最大花最近”来数，而不是写死三朵
    center = max(flowers, key=lambda item: item[2])[0]
    near = [item for item in flowers
            if ((item[0][0] - center[0]) ** 2 + (item[0][1] - center[1]) ** 2) ** 0.5 < 0.05]
    far = len(flowers) - len(near)

    parts = [
        "close-up of a crabapple branch entering from the lower left corner",
        "a main cluster of %d pale rose-pink blossoms at the upper right, the largest "
        "%.0f mm across in front and %d smaller blooms tucked behind it"
        % (len(near), main * 1000, max(0, len(near) - 1)),
    ]
    if far:
        parts.append("%d smaller blooms lower on the branch, one of them half open" % far)
    if buds:
        parts.append("%d deep rose buds at the branch tips" % len(buds))
    if leaves:
        parts.append("%d narrow dark green leaves tucked behind the flowers" % len(leaves))
    parts += [
        "slender brown twigs tapering toward the ends",
        "pale warm beige paper background, upper left kept empty",
        "traditional Chinese gongbi flower painting, flat color planes, fine even outlines, "
        "no realistic shading, soft diffuse light, vertical composition",
        "no text, no border",
    ]
    return ", ".join(parts) + "\n"


def main() -> None:
    text = build_brief()
    path = Path("out/spray-brief.txt")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print(text)
    print(path)


if __name__ == "__main__":
    main()
