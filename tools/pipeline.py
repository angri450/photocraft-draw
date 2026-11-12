# -*- coding: utf-8 -*-
"""一条命令跑完整条链：结构图、三视图、英文提示词、手稿页。

    python3 tools/pipeline.py

产物：
    out/spray-hybrid.png   结构成图
    out/spray-views.png    三视图
    out/spray-brief.txt    英文画面说明
    charts/spray-sheet.png 研究手稿页

后续图像生成由 image-prompt 技能另行负责。
"""
from __future__ import annotations

import argparse
from pathlib import Path

import spray_hybrid


BRIEF = """close-up of a single crabapple branch entering from the lower left corner,
{n} pale rose-pink blossoms opening toward the upper right, the largest at the top
facing the viewer, two smaller blooms tilted beside it with narrower petals, one
small bloom low on the branch, {b} round pink buds at the tips, {l} narrow dark
green leaves tucked behind the flowers, slender brown twigs tapering toward the
ends, pale warm beige paper background, traditional Chinese gongbi flower
painting, flat color planes, fine even outlines, no realistic shading, soft
diffuse light, vertical composition, generous empty space at the upper left,
no text, no border
"""


def write_brief(path: Path) -> Path:
    meshes, flowers, leaves, buds = spray_hybrid.build()
    text = BRIEF.format(n=len(flowers), b=len(buds), l=len(leaves))
    path.write_text(text.strip() + "\n", encoding="utf-8")
    return path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="PhotoCraft 四样输出一条命令")
    parser.add_argument("--out-dir", default="out")
    parser.add_argument("--sheet", default="")
    args = parser.parse_args(argv)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    model = out / "spray-hybrid.png"
    views = out / "spray-views.png"
    spray_hybrid.main(["--out", str(model), "--views", str(views)])

    brief = write_brief(out / "spray-brief.txt")
    print("英文提示词：%s" % brief)

    if args.sheet:
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "code"))
        import build_spray_sheet
        build_spray_sheet.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
