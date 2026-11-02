# -*- coding: utf-8 -*-
"""撒点填充：给一个轮廓，随机撒方块，落在轮廓里的留下。

一条命令出一张图。做法是：
1. 取人形或马形的轮廓多边形；
2. 在轮廓的外接框里随机取中心、随机给宽高；
3. 矩形的四个角必须都在轮廓内，否则丢掉；
4. 攒够数量就停，或者试到上限就停。

颜色按高度分层，上面浅、下面深，这样即使全是方块，也能看出体积。
"""
from __future__ import annotations

import random

from .envelope import HORSE_OUTLINE, PERSON_OUTLINE

OUTLINES = {
    "person": PERSON_OUTLINE,
    "horse": HORSE_OUTLINE,
}


def _inner(polygon):
    xs = [point[0] for point in polygon]
    ys = [point[1] for point in polygon]
    return min(xs), min(ys), max(xs), max(ys)


def _inside(x: float, y: float, polygon) -> bool:
    result = False
    count = len(polygon)
    for index in range(count):
        x1, y1 = polygon[index]
        x2, y2 = polygon[(index + 1) % count]
        if (y1 > y) != (y2 > y):
            cross = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < cross:
                result = not result
    return result


def scatter_grid(outline: str, box, cell: float = 18, fill: float = 0.92,
                 jitter: float = 0.0, seed: int = 0) -> list[dict]:
    """按网格撒方块：先铺格子，格子中心在轮廓里就放一个。

    比纯随机覆盖均匀，空隙少。fill 控制方块占格子的比例，jitter 让每块
    随机偏移一点，看起来不呆板。
    """
    if outline not in OUTLINES:
        raise ValueError(f"没有这个轮廓：{outline}，可选 {', '.join(OUTLINES)}")
    polygon = OUTLINES[outline]
    minx, miny, maxx, maxy = _inner(polygon)
    spanx = maxx - minx
    spany = maxy - miny
    if spanx <= 0 or spany <= 0:
        raise ValueError("轮廓退化成一个点，检查一下")

    x0, y0, width, height = box
    if width <= 0 or height <= 0:
        raise ValueError("box 的宽高要大于 0")
    if cell <= 0:
        raise ValueError("cell 要大于 0")

    scale_x = width / spanx
    scale_y = height / spany
    canvas_poly = [(x0 + (px - minx) * scale_x, y0 + (py - miny) * scale_y)
                   for px, py in polygon]
    cminx, cminy, cmaxx, cmaxy = _inner(canvas_poly)

    rng = random.Random(seed)
    blocks = []
    side = cell * fill
    rows = int((cmaxy - cminy) / cell) + 1
    cols = int((cmaxx - cminx) / cell) + 1
    for row in range(rows):
        for col in range(cols):
            cx = cminx + (col + 0.5) * cell + rng.uniform(-jitter, jitter) * cell
            cy = cminy + (row + 0.5) * cell + rng.uniform(-jitter, jitter) * cell
            corners = [(cx - side / 2, cy - side / 2), (cx + side / 2, cy - side / 2),
                       (cx + side / 2, cy + side / 2), (cx - side / 2, cy + side / 2)]
            if not all(_inside(px, py, canvas_poly) for px, py in corners):
                continue
            blocks.append({"rect": [cx - side / 2, cy - side / 2, side, side],
                           "tone": (cy - cminy) / (cmaxy - cminy)})
    return blocks


def scatter_blocks(outline: str, box, count: int = 40,
                   min_size: float = 0.06, max_size: float = 0.16,
                   seed: int = 0, tries_per_block: int = 40) -> list[dict]:
    """在轮廓内随机撒矩形。

    参数：
        outline          人形或马形的名字
        box              [x, y, 宽, 高]，轮廓要落进这个框
        count            想要多少个方块
        min_size/max_size  方块边长占框宽的比例
        seed             随机种子，同一个种子出同一张图

    返回每个方块的 {rect, tone}，tone 是 0 到 1 的高度比例。
    """
    if outline not in OUTLINES:
        raise ValueError(f"没有这个轮廓：{outline}，可选 {', '.join(OUTLINES)}")
    polygon = OUTLINES[outline]
    minx, miny, maxx, maxy = _inner(polygon)
    spanx = maxx - minx
    spany = maxy - miny
    if spanx <= 0 or spany <= 0:
        raise ValueError("轮廓退化成一个点，检查一下")

    x0, y0, width, height = box
    if width <= 0 or height <= 0:
        raise ValueError("box 的宽高要大于 0")

    scale_x = width / spanx
    scale_y = height / spany
    to_canvas = lambda px, py: (x0 + (px - minx) * scale_x, y0 + (py - miny) * scale_y)

    canvas_poly = [to_canvas(px, py) for px, py in polygon]
    canvas_minx, canvas_miny, canvas_maxx, canvas_maxy = _inner(canvas_poly)

    rng = random.Random(seed)
    blocks = []
    attempts = 0
    limit = count * tries_per_block
    while len(blocks) < count and attempts < limit:
        attempts += 1
        side = rng.uniform(min_size, max_size) * width
        cx = rng.uniform(canvas_minx, canvas_maxx)
        cy = rng.uniform(canvas_miny, canvas_maxy)
        rect = [cx - side / 2, cy - side / 2, side, side]
        corners = [(rect[0], rect[1]), (rect[0] + side, rect[1]),
                   (rect[0] + side, rect[1] + side), (rect[0], rect[1] + side)]
        if not all(_inside(px, py, canvas_poly) for px, py in corners):
            continue
        blocks.append({"rect": rect, "tone": (cy - canvas_miny) / (canvas_maxy - canvas_miny)})

    return blocks
