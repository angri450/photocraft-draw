# -*- coding: utf-8 -*-
"""手稿页：结构成图、模型重绘、三视图、局部放大和观察记录排成一页。

四格版式，旧纸底。模型重绘那一格可以缺省，缺省时留一个空位。
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H = 1600, 2200
PAPER = "#F2E6C9"
INK = "#4A3524"
SOFT = "#7A6248"
LINE = "#9A4A34"
XK = "/home/wanli/.local/share/fonts/XiangcuiKesong.ttf"
NOTO = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"

DEFAULT_NOTES = (
    ("一", "出枝", "主枝从左下进画，与地平线约成四十二度，合折枝画的取势。"),
    ("二", "花数", "四朵开放、两个花苞，最大在右上，最小收在枝的中段。"),
    ("三", "朝向", "花面与视线夹角控制在四十五度以内，再侧就压成一条线。"),
    ("四", "叶序", "叶片全部在花后，只露边缘，不插进花心。"),
    ("五", "花梗", "梗长一厘米到一厘米半，长短不一，避免所有花贴在枝上。"),
)


def _font(path: str, size: int):
    return ImageFont.truetype(path, size)


def _paper() -> Image.Image:
    base = Image.new("RGB", (W, H), PAPER)
    arr = np.array(base).astype(np.int16)
    rng = np.random.default_rng(11)
    arr = np.clip(arr + rng.normal(0, 3.2, (H, W, 1)), 0, 255).astype(np.uint8)
    return Image.fromarray(arr)


def _fit(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    ratio = min(size[0] / image.width, size[1] / image.height)
    return image.resize((int(image.width * ratio), int(image.height * ratio)), Image.LANCZOS)


def _frame(page, box, alpha=90):
    draw = ImageDraw.Draw(page, "RGBA")
    draw.rectangle(box, outline=(122, 98, 72, alpha), width=2)


def build_page(model: Path, views: Path, out: Path, artwork: Path | None = None,
               title: str = "海棠花枝 · 结构研究",
               subtitle: str = "PhotoCraft 网格重构  ·  尺寸按厘米记",
               notes=DEFAULT_NOTES, detail_box=None) -> Path:
    page = _paper()
    draw = ImageDraw.Draw(page, "RGBA")

    draw.text((96, 84), title, font=_font(XK, 74), fill=INK)
    draw.text((100, 184), subtitle, font=_font(NOTO, 26), fill=SOFT)
    draw.line([(96, 238), (1504, 238)], fill=(122, 98, 72, 120), width=2)

    art = _fit(Image.open(model).convert("RGB"), (640, 853))
    ax, ay = 96, 300
    page.paste(art, (ax, ay))
    _frame(page, [ax, ay, ax + art.width, ay + art.height])
    draw.text((ax, ay + art.height + 14), "图一  结构成图：枝条与花瓣按空间位置落位",
              font=_font(NOTO, 24), fill=SOFT)

    mx, my = 836, 300
    if artwork and Path(artwork).is_file():
        painting = _fit(Image.open(artwork).convert("RGB"), (640, 853))
        page.paste(painting, (mx, my))
        _frame(page, [mx, my, mx + painting.width, my + painting.height])
        caption = "图二  同一构图重绘，工笔设色"
    else:
        draw.rectangle([mx, my, mx + 640, my + 853], outline=(122, 98, 72, 90), width=2)
        draw.text((mx + 220, my + 400), "模型重绘留空", font=_font(XK, 38), fill=SOFT)
        caption = "图二  同一构图交给模型重绘"
    draw.text((mx, my + 853 + 14), caption, font=_font(NOTO, 24), fill=SOFT)

    picture = _fit(Image.open(views).convert("RGB"), (760, 325))
    vx, vy = 96, 1258
    page.paste(picture, (vx, vy))
    _frame(page, [vx, vy, vx + picture.width, vy + picture.height])
    draw.text((vx, vy + picture.height + 12), "图三  同一枝的正、左、俯三视，花用五瓣薄片表示朝向",
              font=_font(NOTO, 24), fill=SOFT)

    source = artwork if (artwork and Path(artwork).is_file()) else model
    full = Image.open(source).convert("RGB")
    if detail_box:
        left, top, side = detail_box
        box = (left, top, left + side, top + side)
    else:
        side = min(full.width, full.height)
        left = (full.width - side) // 2
        top = (full.height - side) // 2
        box = (left, top, left + side, top + side)
    crop = full.crop(box).resize((540, 540), Image.LANCZOS)
    cx, cy = 900, 1238
    page.paste(crop, (cx, cy))
    _frame(page, [cx, cy, cx + 540, cy + 540], 110)
    draw.text((cx, cy + 552), "图四  主花放大：五瓣、瓣尖有缺、花心一圈花丝",
              font=_font(NOTO, 24), fill=SOFT)

    nx, ny = 96, 1690
    for index, (num, head, text) in enumerate(notes):
        y = ny + index * 76
        draw.text((nx, y), num, font=_font(XK, 32), fill=LINE)
        draw.text((nx + 44, y - 2), head, font=_font(XK, 30), fill=INK)
        draw.text((nx + 160, y + 2), text, font=_font(NOTO, 23), fill=SOFT)

    draw.line([(96, 2098), (1504, 2098)], fill=(122, 98, 72, 100), width=1)
    draw.text((96, 2112),
              "网格负责位置、朝向与遮挡，花瓣保留曲线形状；三视图只用于检查结构，不参与成图。",
              font=_font(NOTO, 22), fill=SOFT)

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    page.save(out, "PNG")
    return out


__all__ = ["build_page", "DEFAULT_NOTES"]
