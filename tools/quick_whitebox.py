#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""白模快速出图的实验入口，现在只是 `photocraft-draw quick` 的薄壳。

这个脚本当初用来验证「不写绘制方案、不新增构图组件，直接把一串原生命令
交给绘制服务」能不能出图。验证通过后核心逻辑已经搬进 cli.run_quick，
脚本保留，方便按实验记录里的命令重跑。

用法：
  python3 tools/quick_whitebox.py out/whitebox_experiment.commands.json
  python3 -m photocraft_draw quick out/whitebox_experiment.commands.json
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from photocraft_draw.cli import run_quick  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("spec", help="命令序列 JSON")
    ap.add_argument("--no-roots", action="store_true",
                    help="不起 automation 读写根，放开 ambient 路径类命令")
    ap.add_argument("--verbose", action="store_true", help="逐条打印执行结果")
    args = ap.parse_args()

    info = run_quick(args.spec, no_roots=args.no_roots, verbose=args.verbose)
    print(f"ok | {info['width']}x{info['height']} | {info['commands']} 条命令 | "
          f"{info['elapsed']:.1f}s | {info['layers']} 层 | "
          f"{info['png'].name}, {info['psd'].name}")
    print(f"   PNG {info['png'].stat().st_size} 字节 | PSD {info['psd'].stat().st_size} 字节")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
