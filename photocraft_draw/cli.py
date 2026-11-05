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
from .documents import DocumentBook
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
        engine.new_document(
            meta["width"], meta["height"], meta["name"],
            background=meta.get("document_background"),
        )
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
        if meta.get("document_background") == "transparent":
            engine.execute("file.scripts.deleteAllEmptyLayers", {})
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


def cmd_shade(args) -> int:
    from .autoshade import auto_shade, parts_from_commands, report
    from .palette import resolve_palette
    from .engine import Engine

    plan = load_plan(args.plan)
    commands, meta = compose_plan(plan)
    palette = resolve_palette(plan.get("palette"))
    parts = parts_from_commands(commands)
    shaded = auto_shade(parts, palette)

    # 按出现顺序把新颜色写回形状指令
    index = 0
    for command in commands:
        if command.get("command") != "shape.create":
            continue
        if index >= len(shaded):
            break
        command["params"]["fill"] = shaded[index]["hex"]
        index += 1
    print(report(shaded))

    if args.out:
        from pathlib import Path as _Path
        output = _Path(args.out).resolve()
        with Engine(read_root=_Path.cwd(), write_root=output.parent) as engine:
            engine.new_document(meta["width"], meta["height"], meta["name"],
                                background=meta.get("document_background"))
            for command in commands:
                engine.execute(command["command"], command.get("params") or {})
            engine.save(output)
        print(f"已出图 {output}")
    return 0


def cmd_colors(args) -> int:
    from .colorize import check_colors, parts_from_commands, report
    from .palette import resolve_palette

    plan = load_plan(args.plan)
    commands, meta = compose_plan(plan)
    result = check_colors(parts_from_commands(commands), resolve_palette(plan.get("palette")),
                          min_gap=args.gap)
    print(report(result))
    if args.verbose:
        for item in result["colors"]:
            print(f"  {item['name']}  {item['hex']}  亮度 {item['luma']}")
    return 0 if result["ok"] else 1


def cmd_occlusion(args) -> int:
    from .occlusion import analyze, report

    print(report(analyze(Path(args.psd), Path(args.tmp) if args.tmp else None)))
    return 0


def cmd_contact(args) -> int:
    from .contact import analyze, public, report, write_map

    result = analyze(Path(args.psd), Path(args.plan) if args.plan else None,
                      Path(args.tmp) if args.tmp else None)
    print(report(result))
    if args.map:
        out = Path(args.map)
        base = None
        if not args.no_base:
            from .contact import _render_composite
            base = _render_composite(Path(args.psd).resolve(),
                                     out.with_name(out.stem + "-base.png"))
        print(f"显露图：{write_map(result, out, base)}")
    if args.json:
        Path(args.json).write_text(
            json.dumps(public(result), ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"结构化结果：{args.json}")
    return 0


def cmd_depth(args) -> int:
    from .depth import analyze_depth, public, report_depth

    plan = load_plan(args.plan) if args.plan else None
    result = analyze_depth(Path(args.psd), unit=args.unit, skew_x=args.skew_x,
                            skew_y=args.skew_y, ref_width=args.ref_width, plan=plan)
    print(report_depth(result))
    if args.json:
        Path(args.json).write_text(
            json.dumps(public(result), ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"结构化结果：{args.json}")
    return 0


def cmd_motion(args) -> int:
    from .motion import analyze_plan, report

    plan = load_plan(args.plan)
    result = analyze_plan(plan)
    print(report(result))
    if args.json:
        Path(args.json).write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"结构化结果：{args.json}")
    return 0


def cmd_facing(args) -> int:
    from .facing import analyze_plan, report

    plan = load_plan(args.plan)
    result = analyze_plan(plan)
    print(report(result))
    if args.json:
        Path(args.json).write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"结构化结果：{args.json}")
    return 0


def cmd_relations(args) -> int:
    from .relations import run as run_relations

    return run_relations(args.plan, args.unit, args.json)


def cmd_views(args) -> int:
    from .views import run as run_views

    return run_views(args.plan, args.out_dir, args.unit, args.json)


def cmd_verify(args) -> int:
    from .checker import check_commands, report_text

    plan = load_plan(args.plan)
    commands, meta = compose_plan(plan)
    result = check_commands(commands, (meta["width"], meta["height"]), expect=args.expect)
    print(report_text(result))
    if args.envelope:
        from .checker import parts_of
        from .envelope import check_envelope, envelope_text

        layers = plan.get("layers") or [{"name": "全部", "components": plan.get("components")}]
        for layer in layers:
            sub_commands, _ = compose_plan({**plan, "layers": [layer]})
            parts = parts_of(sub_commands)
            if not parts:
                continue
            if args.origin:
                ox, oy = (float(value) for value in args.origin.split(","))
            else:
                top = min(part["bbox"][1] for part in parts)
                bottom = max(part["bbox"][3] for part in parts)
                left = min(part["bbox"][0] for part in parts)
                right = max(part["bbox"][2] for part in parts)
                ratio = 0.30 if args.envelope == "person" else 0.415
                ox, oy = (left + right) / 2, top + (bottom - top) * ratio
            scale = float(args.scale) if args.scale else (
                max(part["bbox"][3] for part in parts) - min(part["bbox"][1] for part in parts))
            env = check_envelope(parts, args.envelope, (ox, oy), scale)
            print(f"[{layer.get('name', '')}] {envelope_text(env)}")
            result["ok"] = result["ok"] and env["ok"]
    if args.verbose:
        for item in result["items"]:
            print(f"  {item['name']}  {item['bbox']}")
    return 0 if result["ok"] else 1


def cmd_brief(args) -> int:
    from .brief import build_brief

    info = build_brief(load_plan(args.plan))
    print("=== 中文稿 ===")
    print(info["zh"])
    print()
    print("=== 英文稿 ===")
    print(info["en"])
    if args.out_zh:
        Path(args.out_zh).write_text(info["zh"] + "\n", encoding="utf-8")
    if args.out_en:
        Path(args.out_en).write_text(info["en"] + "\n", encoding="utf-8")
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


def cmd_doc_inspect(args) -> int:
    path = Path(args.file).expanduser().resolve()
    with Engine(read_root=path.parent, write_root=path.parent) as engine:
        book = DocumentBook(engine)
        opened = book.open(path)
        info = book.inspect()
    print(
        f"ok | {opened['name']} | {opened['width']}x{opened['height']} | "
        f"{opened['layers']} 层 | 顶层 {'、'.join(info['top'])}"
    )
    return 0


def cmd_doc_render(args) -> int:
    path = Path(args.file).expanduser().resolve()
    out = Path(args.png).expanduser().resolve() if args.png else path.with_suffix(".preview.png")
    with Engine(read_root=path.parent, write_root=path.parent) as engine:
        book = DocumentBook(engine)
        book.open(path)
        saved = book.render_to(out, max_side=args.max_side)
    print(f"ok | {saved['path']} | {saved['bytes']} 字节")
    return 0


def cmd_doc_place(args) -> int:
    path = Path(args.file).expanduser().resolve()
    image = Path(args.image).expanduser().resolve()
    out = Path(args.out).expanduser().resolve() if args.out else path.with_name(
        f"{path.stem}-placed{path.suffix}"
    )
    with Engine(read_root=Path.cwd(), write_root=path.parent) as engine:
        book = DocumentBook(engine)
        book.open(path)
        placed = book.place(image, x=args.x, y=args.y, scale=args.scale)
        book.save(out, out.suffix.lstrip("."))
    print(f"ok | 置入 {image.name} | 图层 {placed['layer']} | {out}")
    return 0


def cmd_doc_jobs(args) -> int:
    with Engine(read_root=Path.cwd(), write_root=Path.cwd()) as engine:
        jobs = DocumentBook(engine).jobs()
    print(f"ok | {len(jobs)} 个后台任务")
    for job in jobs:
        print(f"  {job.get('id')}  {job.get('kind', '')}  {job.get('status', '')}")
    return 0


def cmd_doc_cancel(args) -> int:
    with Engine(read_root=Path.cwd(), write_root=Path.cwd()) as engine:
        result = DocumentBook(engine).cancel(args.id)
    print(f"ok | 取消 {result.get('cancelled', 0)} 个任务")
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

    shade = sub.add_parser("shade", help="按相邻关系自动分配色阶并出图")
    shade.add_argument("plan", help="绘制方案文件")
    shade.add_argument("--out", help="输出 PNG 路径")
    shade.set_defaults(func=cmd_shade)

    colors = sub.add_parser("colors", help="检查相邻部件的颜色冲突")
    colors.add_argument("plan", help="绘制方案文件")
    colors.add_argument("--gap", type=float, default=0.08, help="相邻部件的最小亮度差")
    colors.add_argument("--verbose", action="store_true", help="列出每个部件的颜色和亮度")
    colors.set_defaults(func=cmd_colors)

    occlusion = sub.add_parser("occlusion", help="分析分层文件的遮挡关系")
    occlusion.add_argument("psd", help="分层文件")
    occlusion.add_argument("--tmp", help="临时目录")
    occlusion.set_defaults(func=cmd_occlusion)

    contact = sub.add_parser("contact", help="查接触位置、关节归属和穿帮提示")
    contact.add_argument("psd", help="分层文件")
    contact.add_argument("--plan", help="绘制方案文件，用来查关节归属")
    contact.add_argument("--map", help="遮挡显露图输出路径")
    contact.add_argument("--no-base", action="store_true", help="显露图不用合成图做底")
    contact.add_argument("--json", help="结构化结果输出路径")
    contact.add_argument("--tmp", help="临时目录")
    contact.set_defaults(func=cmd_contact)

    depth = sub.add_parser("depth", help="反算分层文件的立体关系与三维坐标")
    depth.add_argument("psd", help="分层文件")
    depth.add_argument("--plan", help="绘制方案文件，取方案里声明的 depth")
    depth.add_argument("--unit", type=float, default=1.0, help="每层深度差，默认 1.0")
    depth.add_argument("--skew-x", type=float, default=0.45, help="深度到横向偏移")
    depth.add_argument("--skew-y", type=float, default=0.28, help="深度到纵向偏移")
    depth.add_argument("--ref-width", type=float, help="参考画布宽度，默认跟画布同宽")
    depth.add_argument("--json", help="结构化结果输出路径")
    depth.set_defaults(func=cmd_depth)
    motion = sub.add_parser("motion", help="检查角色的动作方向关系")
    motion.add_argument("plan", help="绘制方案文件")
    motion.add_argument("--json", help="结构化结果输出路径")
    motion.set_defaults(func=cmd_motion)
    facing = sub.add_parser("facing", help="检查角色给观众看的朝向")
    facing.add_argument("plan", help="绘制方案文件")
    facing.add_argument("--json", help="结构化结果输出路径")
    facing.set_defaults(func=cmd_facing)

    relations = sub.add_parser("relations", help="算兵器和肢体之间的空间关系")
    relations.add_argument("plan", help="绘制方案文件")
    relations.add_argument("--unit", type=float, default=40.0,
                           help="图层 depth 每差 1 相当于多少像素，默认 40")
    relations.add_argument("--json", help="结构化结果输出路径")
    relations.set_defaults(func=cmd_relations)

    views = sub.add_parser("views", help="按正视图、左视图、俯视图出三张图")
    views.add_argument("plan", help="绘制方案文件")
    views.add_argument("--out-dir", default="out", help="输出目录，默认 out")
    views.add_argument("--unit", type=float, default=40.0,
                       help="图层 depth 每差 1 相当于多少像素，默认 40")
    views.add_argument("--json", help="结构化结果输出路径")
    views.set_defaults(func=cmd_views)

    verify = sub.add_parser("verify", help="只读指令检查结构，不出图")
    verify.add_argument("plan", help="绘制方案文件")
    verify.add_argument("--expect", choices=["person", "horse"], help="按人物或马的规则检查")
    verify.add_argument("--verbose", action="store_true", help="列出每个部件的包围盒")
    verify.add_argument("--envelope", choices=["person", "horse"], help="额外按包络检查")
    verify.add_argument("--origin", help="肩部位置 x,y，不给就按包围盒推断")
    verify.add_argument("--scale", type=float, help="身高或肩高像素，不给就用总高")
    verify.set_defaults(func=cmd_verify)

    brief = sub.add_parser("brief", help="把绘制方案翻译成生图提示词")
    brief.add_argument("plan", help="绘制方案文件")
    brief.add_argument("--out-zh", help="中文稿输出路径")
    brief.add_argument("--out-en", help="英文稿输出路径")
    brief.set_defaults(func=cmd_brief)

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

    doc = sub.add_parser("doc", help="文档层：打开、置入、渲染、检查、任务")
    doc_sub = doc.add_subparsers(dest="doc_command", required=True)

    doc_inspect = doc_sub.add_parser("inspect", help="打开文档并读尺寸、层数和顶层")
    doc_inspect.add_argument("file")
    doc_inspect.set_defaults(func=cmd_doc_inspect)

    doc_render = doc_sub.add_parser("render", help="打开文档并渲染 PNG")
    doc_render.add_argument("file")
    doc_render.add_argument("--png", help="输出 PNG，默认 <文件名>.preview.png")
    doc_render.add_argument("--max-side", type=int, default=None, help="最长边像素")
    doc_render.set_defaults(func=cmd_doc_render)

    doc_place = doc_sub.add_parser("place", help="打开文档、置入图片并另存")
    doc_place.add_argument("file")
    doc_place.add_argument("image")
    doc_place.add_argument("--x", type=float, default=None)
    doc_place.add_argument("--y", type=float, default=None)
    doc_place.add_argument("--scale", type=float, default=None)
    doc_place.add_argument("--out", help="输出文件，默认 <文件名>-placed.<扩展名>")
    doc_place.set_defaults(func=cmd_doc_place)

    doc_jobs = doc_sub.add_parser("jobs", help="列出后台任务")
    doc_jobs.set_defaults(func=cmd_doc_jobs)

    doc_cancel = doc_sub.add_parser("cancel", help="取消后台任务")
    doc_cancel.add_argument("id")
    doc_cancel.set_defaults(func=cmd_doc_cancel)

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
