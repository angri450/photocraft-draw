# -*- coding: utf-8 -*-
"""命令行入口：check、draw、apply、commands、components、doctor。"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from .annotate import serve as serve_review
from .annotate import write_review
from .commandbook import categories as command_categories
from .commandbook import describe as describe_command
from .commandbook import load_catalog, search as search_commands
from .engine import Engine, EngineError, engine_version, find_engine
from .plan import compose_plan, load_plan
from .registry import list_components


def _summary(meta: dict, elapsed: float, outputs: list[Path], extras: int = 0) -> str:
    files = ", ".join(str(path) for path in outputs)
    extra = f" | {extras} 条附加指令" if extras else ""
    return (
        f"ok | {meta['width']}x{meta['height']} | {meta.get('layers', 1)} 个图层 | "
        f"{meta['components']} 个构图组件 | "
        f"{meta['commands']} 条绘制指令{extra} | {elapsed:.1f}s | {files}"
    )


def _prepare_outputs(args, plan_path: Path) -> tuple[list[tuple[str, Path]], Path]:
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
    return outputs, out_dir


def _render(meta: dict, commands: list[dict], outputs: list[tuple[str, Path]],
            extras: list[tuple[str, dict]] | None = None, verbose: bool = False) -> int:
    started = time.time()
    out_dir = outputs[0][1].parent
    with Engine(read_root=Path.cwd(), write_root=out_dir) as engine:
        engine.new_document(meta["width"], meta["height"], meta["name"])
        for index, command in enumerate(commands, 1):
            result = engine.execute(command["command"], command.get("params") or {})
            if command["command"] == "layer.new.group" and not command.get("_nested"):
                layer_id = result.get("layer") if isinstance(result, dict) else None
                if layer_id is not None:
                    engine.execute("layer.arrange.bringToFront", {"layer": layer_id})
            if verbose:
                print(f"  {index:>3} {command['command']} -> {result}")
        for command_id, params in extras or []:
            result = engine.execute(command_id, params)
            if verbose:
                print(f"  附加 {command_id} -> {result}")
        for fmt, path in outputs:
            saved = engine.save(path, fmt)
            if verbose and saved.get("warnings"):
                print("  警告：" + "；".join(saved["warnings"]))
    print(_summary(meta, time.time() - started, [path for _, path in outputs], len(extras or [])))
    return 0


def cmd_components(args) -> int:
    keyword = (args.search or "").strip().lower()
    for component in list_components():
        if keyword:
            haystack = " ".join((component.id, component.name, component.description,
                                 " ".join(component.params))).lower()
            if keyword not in haystack:
                continue
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
        f"ok | {meta['width']}x{meta['height']} | {meta.get('layers', 1)} 个图层 | "
        f"{meta['components']} 个构图组件 | {len(commands)} 条绘制指令"
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
    outputs, _ = _prepare_outputs(args, plan_path)
    return _render(meta, commands, outputs, verbose=args.verbose)


def cmd_apply(args) -> int:
    plan_path = Path(args.plan)
    plan = load_plan(plan_path)
    commands, meta = compose_plan(plan)
    describe_command(args.command)
    try:
        params = json.loads(args.params) if args.params else {}
    except json.JSONDecodeError as error:
        raise ValueError(f"--params 不是合法 JSON：{error}") from error
    if not isinstance(params, dict):
        raise ValueError("--params 必须是 JSON 对象")
    outputs, _ = _prepare_outputs(args, plan_path)
    return _render(meta, commands, outputs, extras=[(args.command, params)], verbose=args.verbose)


def cmd_annotate(args) -> int:
    plan_path = Path(args.plan)
    plan = load_plan(plan_path)
    commands, meta = compose_plan(plan)
    outputs, _ = _prepare_outputs(args, plan_path)
    by_format = {fmt: path for fmt, path in outputs}
    if "png" not in by_format or "psd" not in by_format:
        raise ValueError("批注页需要同时生成 PNG 和 PSD，去掉 --png/--psd 用默认输出")
    if not by_format["png"].exists() or not by_format["psd"].exists():
        _render(meta, commands, outputs, verbose=args.verbose)
    html = write_review(
        by_format["png"], by_format["psd"], meta["name"],
        by_format["png"].with_suffix(".review.html"),
    )
    print(f"ok | 批注页 {html}")
    if args.serve:
        serve_review(html, args.port)
    return 0


def cmd_commands(args) -> int:
    if args.describe:
        item = describe_command(args.describe)
        print(f"{item['id']}  {item['label']}")
        print(f"类别：{item['category_name']}（{item['category']}）")
        if item.get("menu"):
            print(f"菜单：{item['menu']}")
        if item.get("shortcut"):
            print(f"快捷键：{item['shortcut']}")
        print(f"需要文档：{'是' if item.get('needs_document') else '否'}")
        print(f"参数：{item['params'] or '无'}")
        return 0
    if args.count:
        catalog = load_catalog()
        print(f"{catalog['count']} 条命令，{len(command_categories())} 个类别")
        return 0
    if args.search or args.category:
        found = search_commands(args.search, args.category, args.limit)
        for item in found:
            print(f"{item['id']:<46} {item['category_name']:<8} {item['label']}")
        print(f"共 {len(found)} 条")
        return 0
    for item in command_categories():
        print(f"{item['name']:<8} {item['key']:<16} {item['count']}")
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

    for name, help_text in (("draw", "按绘制方案出图"), ("apply", "出图后追加一条绘制指令")):
        node = sub.add_parser(name, help=help_text)
        node.add_argument("plan", help="绘制方案文件")
        if name == "apply":
            node.add_argument("command", help="命令编号，用 commands --search 查")
            node.add_argument("--params", default="{}", help="命令参数，JSON 对象")
        node.add_argument("--png", help="PNG 输出路径")
        node.add_argument("--psd", help="PSD 输出路径")
        node.add_argument("--out-dir", default="out", help="默认输出目录，默认 out")
        node.add_argument("--verbose", action="store_true", help="打印每条指令的执行摘要")
        node.set_defaults(func=cmd_draw if name == "draw" else cmd_apply)

    annotate = sub.add_parser("annotate", help="生成图层批注页")
    annotate.add_argument("plan", help="绘制方案文件")
    annotate.add_argument("--png", help="PNG 路径")
    annotate.add_argument("--psd", help="PSD 路径")
    annotate.add_argument("--out-dir", default="out", help="默认输出目录，默认 out")
    annotate.add_argument("--serve", action="store_true", help="生成后启动本地网页服务")
    annotate.add_argument("--port", type=int, default=8898, help="网页端口，默认 8898")
    annotate.add_argument("--verbose", action="store_true", help="打印绘制过程")
    annotate.set_defaults(func=cmd_annotate)

    commands = sub.add_parser("commands", help="查命令目录")
    commands.add_argument("--search", help="按关键字搜编号、名称、菜单和参数")
    commands.add_argument("--category", help="按类别筛选，中文名或英文键都行")
    commands.add_argument("--describe", help="看某条命令的详细参数")
    commands.add_argument("--limit", type=int, default=30, help="最多列多少条，默认 30")
    commands.add_argument("--count", action="store_true", help="只显示总数")
    commands.set_defaults(func=cmd_commands)

    components = sub.add_parser("components", help="列出组件目录")
    components.add_argument("--search", help="按关键字搜组件")
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
    except (FileNotFoundError, KeyError, ValueError) as error:
        print(f"fail | {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
