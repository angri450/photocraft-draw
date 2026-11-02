# -*- coding: utf-8 -*-
"""遮挡分析：给定一个分层文件，算出谁挡住谁、挡了多少。

单张位图没有层次信息，遮挡关系是猜不出来的。但分层文件不一样：每层都有
自己的透明通道，两层像素叠在一起的地方，上面那层就是遮挡方。这里把每层
单独渲染出来，两两比像素，输出一张遮挡表。

用法：
    python3 -m photocraft_draw.occlusion out/dawn-napoleon.psd
"""
from __future__ import annotations

import argparse
import base64
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image

from .annotate import read_layers, render_layer_images


def _alpha_from_src(src: str):
    if not src or "," not in src:
        return None
    raw = base64.b64decode(src.split(",", 1)[1])
    image = Image.open(BytesIO(raw)).convert("RGBA")
    return np.asarray(image)[..., 3] > 24


def analyze(psd_path: Path, tmp_dir: Path | None = None) -> dict:
    """返回每层两两之间的遮挡像素数。"""
    psd_path = Path(psd_path).resolve()
    width, height, layers = read_layers(psd_path)
    work = tmp_dir or psd_path.parent / "_occlusion"
    work.mkdir(parents=True, exist_ok=True)
    rendered = render_layer_images(psd_path, work)

    masks = {}
    for item in rendered:
        mask = _alpha_from_src(item.get("src") or "")
        if mask is not None:
            masks[item["name"]] = mask

    order = [name for name in (item["name"] for item in rendered) if name in masks]
    pairs = []
    for upper_index, upper in enumerate(order):
        for lower in order[upper_index + 1:]:
            overlap = int(np.logical_and(masks[upper], masks[lower]).sum())
            if overlap <= 0:
                continue
            pairs.append({
                "upper": upper,
                "lower": lower,
                "pixels": overlap,
                "upper_area": int(masks[upper].sum()),
                "lower_area": int(masks[lower].sum()),
                "covered_ratio": round(overlap / max(int(masks[lower].sum()), 1), 3),
            })
    pairs.sort(key=lambda item: item["pixels"], reverse=True)

    return {
        "canvas": [width, height],
        "layers": order,
        "pairs": pairs,
    }


def report(result: dict) -> str:
    lines = [f"画布 {result['canvas'][0]}x{result['canvas'][1]} | {len(result['layers'])} 层"]
    lines.append("从后到前：" + " → ".join(result["layers"]))
    if not result["pairs"]:
        lines.append("没有图层重叠")
        return "\n".join(lines)
    lines.append("遮挡关系（上面挡住下面）：")
    for item in result["pairs"]:
        lines.append(
            f"  {item['upper']} 挡住 {item['lower']}：{item['pixels']} 像素，"
            f"占下层 {item['covered_ratio'] * 100:.1f}%"
        )
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="分析分层文件的遮挡关系")
    parser.add_argument("psd")
    parser.add_argument("--tmp", help="临时目录")
    args = parser.parse_args(argv)
    result = analyze(Path(args.psd), Path(args.tmp) if args.tmp else None)
    print(report(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
