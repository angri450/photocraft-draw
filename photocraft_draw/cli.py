# -*- coding: utf-8 -*-
"""命令行入口：check、draw、components、doctor。"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

from .engine import Engine, EngineError, engine_version, find_engine
from .plan import compose_plan, load_plan
from .registry import list_components


def _summary(meta: dict, elapsed: float, outputs: list[Path]) -> str:
    files = ", ".join(str(path) for path in outputs)
    return (
        f"ok | {meta['width']}x{meta['height']} | {meta['components']} 个构图组件 | "
        f"{meta['commands']} 条绘制指令 | {elapsed:.1f}s | {files}"
    )


def cmd_components(args) -> int:
    for component in list_components():
        print(f"{component.id}  {component.name}")
        print(f"  {component.description}")
        for key, value in component.params.items():
            print(f"  - {key}：{value}")
    return 0


def cmd_doctor(args) -> int:
    path = find_engine()
    print(f"引擎：{path}")
    print(f"版本：{engine_version(path) or '读不到版本号'}")
    print(f"Python：{sys.version.split()[0]}")
    return 0


def cmd_check(args) -> int:
    plan = load_plan(args.plan)
    commands, meta = compose_plan(plan)
    print(
        f"ok | {meta['width']}x{meta['height']} | {meta['components']} 个构图组件 | "
        f"{len(commands)} 条绘制指令"
    )
    if args.verbose:
        for index, command in enumerate(commands, 1):
            params = command.get("params") or {}
            name = params.get("name") or params.get("text") or params.get("kind") or ""
            print(f"  {index:>3} {command['command']} {name}")
    return 0


def cmd_draw(args) -> int:
    plan_path = Path(args.plan)
    plan = load_plan(plan_path)
    commands, meta = compose_plan(plan)

    outputs: list[tuple[str, Path]] = []
    if args.png:
        outputs.append(("png", Path(args.png)))
    if args.psd:
        outputs.append(("psd", Path(args.psd)))
    if not outputs:
        out_dir = Path(args.out_dir)
        outputs = [
            ("png", out_dir / f"{plan_path.stem}.png"),
            ("psd", out_dir / f"{plan_path.stem}.psd"),
        ]

    outputs = [(fmt, path.resolve()) for fmt, path in outputs]
    parents = {path.parent for _, path in outputs}
    if len(parents) != 1:
        raise ValueError("PNG 和 PSD 要放在同一个目录，绘制服务一次只给一个写入目录")
    out_dir = parents.pop()
    out_dir.mkdir(parents=True, exist_ok=True)
    for _, path in outputs:
        if path.parent != out_dir:
            raise ValueError(f"{path} 不在 {out_dir} 里")
        path.parent.mkdir(parents=True, exist_ok=True)

    started = time.time()
    with Engine(read_root=Path.cwd(), write_root=out_dir) as engine:
        engine.new_document(meta["width"], meta["height"], meta["name"])
        for index, command in enumerate(commands, 1):
            result = engine.execute(command["command"], command.get("params") or {})
            if args.verbose:
                print(f"  {index:>3} {command['command']} -> {result}")
        for fmt, path in outputs:
            saved = engine.save(path, fmt)
            if args.verbose and saved.get("warnings"):
                print("  警告：" + "；".join(saved["warnings"]))
    print(_summary(meta, time.time() - started, [path for _, path in outputs]))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="photocraft-draw",
        description="用构图组件和绘制方案驱动 PhotoCraft 出图",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="校验绘制方案并统计绘制指令")
    check.add_argument("plan", help="绘制方案文件")
    check.add_argument("--verbose", action="store_true", help="逐条列出绘制指令")
    check.set_defaults(func=cmd_check)

    draw = sub.add_parser("draw", help="按绘制方案出图，默认同时写 PNG 和 PSD")
    draw.add_argument("plan", help="绘制方案文件")
    draw.add_argument("--png", help="PNG 输出路径")
    draw.add_argument("--psd", help="PSD 输出路径")
    draw.add_argument("--out-dir", default="out", help="默认输出目录，默认 out")
    draw.add_argument("--verbose", action="store_true", help="打印每条指令的执行摘要")
    draw.set_defaults(func=cmd_draw)

    components = sub.add_parser("components", help="列出组件目录")
    components.set_defaults(func=cmd_components)

    doctor = sub.add_parser("doctor", help="检查绘制服务是否可用")
    doctor.set_defaults(func=cmd_doctor)
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except EngineError as error:
        print(f"fail | {error}", file=sys.stderr)
        return 3
    except (FileNotFoundError, ValueError) as error:
        print(f"fail | {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
