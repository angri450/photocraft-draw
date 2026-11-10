#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从引擎导出命令目录，生成 photocraft_draw/catalog.json。

用法：
  python3 tools/build_catalog.py [photocraft-cli 路径]

不给路径时按 PHOTOCRAFT_CLI、PATH、~/opt 的顺序找。

除了编号、名称、参数这些静态信息，每条命令还带一份会话可用性标注：
  session_state            可执行 / 看上下文 / 会话禁用
  session_evidence         实测-调用 / 实测-查询 / 推断
  session_reason           看上下文时的原因，或会话禁用时的判断依据
  session_alternative      被禁用时改用的文档层方法
  session_alternative_note 替代方法少了哪些能力
  path_root                路径要相对哪个根
  path_params              哪几个参数是路径

可用性怎么来的：
  1. 会话禁用那一批，是 2026-11-10 在 0.19.0 上逐条调用试出来的。serve
     会话会拒绝一切要碰会话外文件、打印队列或系统设备的命令，报错原文是
     「automation command `<id>` uses ambient filesystem paths and is disabled;
     use capability-scoped document methods」。
  2. 其余命令的可执行 / 看上下文，是新建一份 800×600 空文档后读
     engine.commands 得到的 enabled 和 disabledReason，标注写「实测-查询」，
     表示问过引擎当前能不能跑，没有真的执行。
  3. 引擎起不来时退化成按 needsDocument 推断，标注写成「推断」。

会话可用性跟着当前文档状态走，引擎当场给出的 engine.commands 才是最终
依据；目录里记的是空文档基线，用来让调用方一次查询就判断该走哪条路。
"""
from __future__ import annotations

import datetime
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CATEGORY_NAMES = {
    "layer": "图层操作",
    "filter": "滤镜效果",
    "edit": "编辑操作",
    "type": "文字排版",
    "image": "图像调整",
    "file": "文件操作",
    "select": "选择操作",
    "view": "视图控制",
    "paint": "绘制操作",
    "path": "路径编辑",
    "channel": "通道操作",
    "brush": "画笔设置",
    "actions": "动作录制",
    "layerComp": "图层复合",
    "history": "历史记录",
    "tools": "工具切换",
    "gradient": "渐变填充",
    "swatches": "色板管理",
    "document": "文档管理",
    "pattern": "图案填充",
    "shape": "形状绘制",
    "style": "样式管理",
    "count": "计数工具",
    "slice": "切片工具",
    "timeline": "时间轴操作",
    "tool": "工具设置",
    "cloneSource": "仿制源管理",
    "plugin": "插件扩展",
    "notes": "注释工具",
    "prefs": "首选项设置",
    "measurementLog": "测量记录",
    "jobs": "后台任务",
    "session": "会话管理",
    "command": "命令执行",
    "color": "颜色设置",
    "help": "帮助信息",
    "updates": "更新检查",
    "variables": "数据变量",
}

# 常用命令的中文说法，补在关键字里，方便按中文搜。
KEYWORDS = {
    "image.adjustments.curves": "曲线 色调曲线",
    "image.adjustments.levels": "色阶 明暗",
    "image.adjustments.brightnessContrast": "亮度 对比度",
    "image.adjustments.vibrance": "自然饱和度 饱和度",
    "image.adjustments.hueSaturation": "色相 饱和度 明度",
    "image.adjustments.colorBalance": "色彩平衡",
    "image.adjustments.exposure": "曝光",
    "image.adjustments.blackWhite": "黑白",
    "image.adjustments.photoFilter": "照片滤镜 色温",
    "image.adjustments.channelMixer": "通道混合器",
    "image.adjustments.invert": "反相",
    "image.adjustments.posterize": "色调分离",
    "image.adjustments.threshold": "阈值",
    "image.adjustments.gradientMap": "渐变映射",
    "image.adjustments.selectiveColor": "可选颜色",
    "image.adjustments.colorLookup": "颜色查找 调色",
    "image.adjustments.desaturate": "去色",
    "image.autoTone": "自动色调",
    "image.autoContrast": "自动对比度",
    "image.autoColor": "自动颜色",
    "filter.blur.gaussianBlur": "高斯模糊 模糊",
    "filter.blur.blur": "模糊",
    "filter.blur.blurMore": "进一步模糊",
    "filter.blur.motionBlur": "动感模糊",
    "filter.blur.radialBlur": "径向模糊",
    "filter.blur.boxBlur": "方框模糊",
    "filter.sharpen.sharpen": "锐化",
    "filter.sharpen.sharpenMore": "进一步锐化",
    "filter.sharpen.sharpenEdges": "锐化边缘",
    "filter.sharpen.unsharpMask": "USM 锐化 智能锐化",
    "filter.sharpen.smartSharpen": "智能锐化",
    "filter.noise.addNoise": "添加杂色 噪点",
    "filter.noise.median": "中间值 降噪",
    "filter.noise.dustAndScratches": "蒙尘与划痕 降噪",
    "filter.noise.despeckle": "去斑 降噪",
    "filter.pixelate.mosaic": "马赛克 像素化",
    "filter.stylize.emboss": "浮雕",
    "filter.stylize.findEdges": "查找边缘",
    "filter.stylize.oilPaint": "油画",
    "filter.other.highPass": "高反差保留",
    "image.imageSize": "图像大小 缩放",
    "image.canvasSize": "画布大小",
    "image.crop": "裁剪",
    "image.perspectiveCrop": "透视裁剪",
    "image.mode.grayscale": "灰度",
    "image.mode.cmyk": "CMYK",
    "layer.new.layer": "新建图层",
    "layer.new.group": "新建组 编组",
    "layer.duplicate": "复制图层",
    "layer.delete": "删除图层",
    "layer.mergeDown": "向下合并",
    "layer.mergeGroup": "合并组",
    "layer.flattenImage": "拼合图像",
    "layer.groupLayers": "图层编组",
    "layer.createClippingMask": "创建剪贴蒙版",
    "layer.setProps": "图层属性 不透明度 混合模式",
    "layer.layerMask.revealAll": "显示全部 蒙版",
    "layer.layerMask.hideAll": "隐藏全部 蒙版",
    "type.create": "新建文字 文字",
    "type.edit": "编辑文字 改字",
    "type.setStyle": "文字样式 字体 字号",
    "type.fonts": "字体列表",
    "shape.create": "新建形状 形状",
    "shape.edit": "编辑形状",
    "file.export.quickExport": "快速导出",
    "file.saveACopy": "存储副本",
    "file.export.layersToFiles": "图层导出为文件",
    "file.automate.batch": "批处理",
}

# 编号里的英文单词，逐词翻成中文，补进关键字。
TOKEN_NAMES = {
    "layer": "图层", "type": "文字", "shape": "形状", "image": "图像",
    "filter": "滤镜", "file": "文件", "select": "选择", "view": "视图",
    "paint": "绘制", "path": "路径", "channel": "通道", "brush": "画笔",
    "gradient": "渐变", "pattern": "图案", "history": "历史", "edit": "编辑",
    "adjustments": "调整", "export": "导出", "import": "导入", "transform": "变换",
    "rotate": "旋转", "flip": "翻转", "crop": "裁剪", "mask": "蒙版",
    "group": "编组", "delete": "删除", "duplicate": "复制", "new": "新建",
    "rename": "重命名", "merge": "合并", "flatten": "拼合", "arrange": "排列",
    "visible": "可见", "opacity": "不透明度", "blur": "模糊", "sharpen": "锐化",
    "noise": "杂色", "distort": "扭曲", "stylize": "风格化", "pixelate": "像素化",
    "text": "文字", "font": "字体", "scale": "缩放", "resize": "调整大小",
}

# serve 会话里一律被拒的命令。2026-11-10 在 0.19.0 上逐条调用确认，报错
# 都是 ambient filesystem paths and is disabled。
# 值：带环境路径的参数、替代方法、替代方法缺什么。
# 替代方法为 None 表示会话里没有等价做法，只能走 photocraft-cli run 一次性模式。
AMBIENT_BLOCKED = {
    # 置入：文档层有 doc.place
    "file.placeEmbedded": ("path", "doc.place",
                           "只收 path、x、y、scale，而且 serve 下 x、y 被忽略，图固定落在画布中心；要用 center、fit、smartObject 就改走一次性模式跑原命令"),
    "file.placeLinked": ("path", "doc.place",
                         "只收 path、x、y、scale，serve 下 x、y 被忽略；置入的是嵌入副本，不是链接"),
    # 打开：文档层有 doc.open
    "file.openAs": ("path", "doc.open", "整份打开，不能指定解码格式"),
    "file.openExrParts": ("path", "doc.open", "整份打开，挑不了 EXR 的 part 和通道组"),
    "file.exrParts": ("path", "doc.open", "只能打开文件，读不到 part 清单"),
    "file.import.notes": ("path", "doc.open", "只能打开整份文档，取不到注释"),
    "file.revert": ("", "doc.open", "要重新打开原文件；原文件路径在会话外"),
    # 另存与导出：文档层有 doc.save
    "file.saveACopy": ("path", "doc.save", "整份保存，没有 quality、layers 这些选项"),
    "file.export.quickExport": ("path", "doc.save", "整份保存，没有 Quick Export 的格式预设"),
    "layer.exportAs": ("path", "doc.save", "只能存整份文档，不能只导某一层"),
    "layer.quickExportAsPng": ("path", "doc.save", "只能存整份文档，不能只导某一层"),
    # 预设库、动作、插件：会话内没有等价方法
    "actions.load": ("path", None, ""),
    "actions.save": ("path", None, ""),
    "brush.presets.importAbr": ("path", None, ""),
    "brush.presets.importImage": ("path", None, ""),
    "gradient.presets.importGrd": ("path", None, ""),
    "pattern.import": ("path", None, ""),
    "pattern.export": ("path", None, ""),
    "style.presets.importAsl": ("path", None, ""),
    "style.presets.exportAsl": ("path", None, ""),
    "swatches.import": ("path", None, ""),
    "swatches.export": ("path", None, ""),
    "layer.layerStyle.contours.load": ("path", None, ""),
    "layer.layerStyle.contours.save": ("path", None, ""),
    "plugin.install": ("path", None, ""),
    "plugin.reload": ("path", None, ""),
    "measurementLog.export": ("path", None, ""),
    # 颜色查找表读外部 .cube 文件
    "image.adjustments.colorLookup": ("file", None, ""),
    "layer.newAdjustmentLayer.colorLookup": ("file", None, ""),
    # 智能对象读写磁盘
    "layer.smartObjects.convertToLinked": ("path", None, ""),
    "layer.smartObjects.exportContents": ("path", None, ""),
    "layer.smartObjects.relinkToFile": ("path", None, ""),
    "layer.smartObjects.replaceContents": ("path", None, ""),
    "layer.smartObjects.revealInFinder": ("", None, ""),
    "layer.smartObjects.updateAllModifiedContent": ("", None, ""),
    "layer.smartObjects.updateChanged": ("", None, ""),
    # 批处理与自动化
    "file.automate.batch": ("output", None, ""),
    "file.automate.contactSheetII": ("input、output", None, ""),
    "file.automate.createDroplet": ("path、output", None, ""),
    "file.automate.lensCorrection": ("input、output", None, ""),
    "file.automate.mergeToHdrPro": ("paths", None, ""),
    "file.automate.photomerge": ("paths", None, ""),
    "file.automate.runDroplet": ("droplet、input、output", None, ""),
    "file.import.variableDataSets": ("path", None, ""),
    # 批量导出
    "file.export.artboardsToFiles": ("dir", None, ""),
    "file.export.artboardsToPdf": ("path", None, ""),
    "file.export.colorLookupTables": ("path", None, ""),
    "file.export.dataSetsAsFiles": ("dir", None, ""),
    "file.export.layerCompsToFiles": ("dir", None, ""),
    "file.export.layersToFiles": ("dir", None, ""),
    "file.export.pathsToIllustrator": ("path", None, ""),
    "file.export.saveForWebLegacy": ("path、dir", None, ""),
    "file.package": ("dir", None, ""),
    "file.generate.imageAssets": ("dir", None, ""),
    # 脚本
    "file.scripts.browse": ("path", None, ""),
    "file.scripts.imageProcessor": ("input、output", None, ""),
    "file.scripts.loadFilesIntoStack": ("paths", None, ""),
    "file.scripts.statistics": ("input", None, ""),
    "file.scripts.scriptEventsManager": ("script", None, ""),
    # 打印与系统文件管理器
    "file.print": ("", None, ""),
    "file.print.page": ("", None, ""),
    "file.printOneCopy": ("", None, ""),
    "file.printers": ("", None, ""),
    "file.print.printers": ("", None, ""),
    "file.revealInFinder": ("", None, ""),
    "file.import.wiaSupport": ("", None, ""),
}

# 会话里能跑、但路径按写入根解析的命令。
SCOPED_WRITE_PATHS = {
    "file.export.renderVideo": "dir",
}

# 参数里也有 path，但那是文档内的路径对象，不是磁盘路径。列出来免得误会。
DOCUMENT_PATH_COMMANDS = {
    "edit.defineCustomShape",
    "path.set",
    "shape.create",
    "shape.edit",
    "shape.presets.new",
    "layer.vectorMask.add",
    "layer.vectorMask.edit",
}

NO_ALTERNATIVE_NOTE = "会话里没有等价方法；一次性模式（Engine.run_once 或 photocraft-cli run）能跑同一条命令，相对路径按进程工作目录解析"


def _document_path(command_id: str) -> bool:
    return (command_id in DOCUMENT_PATH_COMMANDS
            or command_id.startswith("layer.newAdjustmentLayer.")
            or command_id.startswith("layer.newFillLayer."))


def session_fields(command_id: str, statuses: dict[str, tuple[bool, str]] | None) -> dict:
    """一条命令的会话可用性标注。"""
    blocked = AMBIENT_BLOCKED.get(command_id)
    if blocked:
        params, alternative, note = blocked
        # 有替代方法时，路径按替代方法要求写；没有替代方法才落到进程工作目录。
        if alternative in ("doc.place", "doc.open"):
            root = "读取根"
        elif alternative == "doc.save":
            root = "写入根"
        elif params:
            root = "进程工作目录（仅一次性模式）"
        else:
            root = "不涉及"
        fields = {
            "session_state": "会话禁用",
            "session_evidence": "实测-调用",
            "session_reason": "serve 会话实测被拒：要碰会话外的文件、打印队列或系统设备，会话里禁用",
            "session_alternative": alternative or "无",
            "session_alternative_note": note or NO_ALTERNATIVE_NOTE,
            "path_root": root,
        }
        if params:
            fields["path_params"] = params
        return fields

    state, evidence, reason = "可执行", "推断", ""
    if statuses and command_id in statuses:
        enabled, why = statuses[command_id]
        evidence = "实测-查询"
        if not enabled:
            state = "看上下文"
            reason = "空文档下引擎报：%s" % (why or "上下文不满足")
    fields = {"session_state": state, "session_evidence": evidence}
    if reason:
        fields["session_reason"] = reason

    if command_id in SCOPED_WRITE_PATHS:
        fields["path_root"] = "写入根"
        fields["path_params"] = SCOPED_WRITE_PATHS[command_id]
    elif _document_path(command_id):
        fields["path_root"] = "文档内路径，不是磁盘路径"
        fields["path_params"] = "path"
    return fields


def build_entries(entries, statuses: dict[str, tuple[bool, str]] | None = None) -> list[dict]:
    """把引擎导出的命令表整理成目录条目。不碰磁盘，方便测试。"""
    commands = []
    for entry in entries:
        command_id = str(entry.get("id", "")).strip()
        if not command_id:
            continue
        menu = entry.get("menu") or ""
        if isinstance(menu, list):
            menu = " > ".join(str(part) for part in menu)
        shortcut = entry.get("shortcut") or ""
        if isinstance(shortcut, list):
            shortcut = " / ".join(str(part) for part in shortcut)
        category = command_id.split(".")[0]
        translated = [TOKEN_NAMES[part] for part in command_id.split(".") if part in TOKEN_NAMES]
        keywords = " ".join(item for item in (KEYWORDS.get(command_id, ""), " ".join(translated)) if item)
        item = {
            "id": command_id,
            "label": entry.get("label", ""),
            "menu": str(menu),
            "shortcut": str(shortcut),
            "params": str(entry.get("params", "")),
            "needs_document": bool(entry.get("needsDocument", True)),
            "category": category,
            "category_name": CATEGORY_NAMES.get(category, category),
            "keywords": keywords,
        }
        item.update(session_fields(command_id, statuses))
        commands.append(item)
    commands.sort(key=lambda item: (item["category"], item["id"]))
    return commands


def probe_statuses(cli) -> dict[str, tuple[bool, str]] | None:
    """开一份 800×600 空文档，读 engine.commands 的 enabled 和禁用原因。"""
    try:
        from photocraft_draw.engine import Engine

        with Engine(cli=cli) as engine:
            engine.new_document(800, 600, "catalog-baseline")
            reply = engine.call("engine.commands", {})
            if not reply.get("ok"):
                return None
            return {
                str(item.get("id")): (bool(item.get("enabled")), str(item.get("disabledReason") or ""))
                for item in reply.get("result") or []
            }
    except Exception:
        return None


def build_catalog(entries, version: str = "", statuses=None, measured_at: str | None = None) -> dict:
    commands = build_entries(entries, statuses)
    counts = Counter(item["category"] for item in commands)
    categories = [
        {"key": key, "name": CATEGORY_NAMES.get(key, key), "count": counts[key]}
        for key in sorted(counts)
    ]
    blocked = sum(1 for item in commands if item["session_state"] == "会话禁用")
    context = sum(1 for item in commands if item["session_state"] == "看上下文")
    return {
        "engine": version,
        "count": len(commands),
        "categories": categories,
        "session_baseline": {
            "measured_at": measured_at or datetime.date.today().isoformat(),
            "baseline": "新建 800×600 空文档后读 engine.commands",
            "blocked": blocked,
            "context": context,
            "ready": len(commands) - blocked - context,
            "note": "可用性跟着当前文档状态走，engine.commands 是最终依据；这里记的是空文档基线。",
        },
        "commands": commands,
    }


def main() -> int:
    from photocraft_draw.engine import engine_version, find_engine

    cli = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else find_engine()
    raw = subprocess.run(
        [str(cli), "commands", "--json"], capture_output=True, text=True, check=True
    ).stdout
    entries = json.loads(raw)
    statuses = probe_statuses(cli)
    catalog = build_catalog(entries, engine_version(cli), statuses)
    target = ROOT / "photocraft_draw" / "catalog.json"
    target.write_text(json.dumps(catalog, ensure_ascii=False, indent=1), encoding="utf-8")
    baseline = catalog["session_baseline"]
    print("写入 %s：%d 条命令，%d 个类别；会话禁用 %d 条，看上下文 %d 条，可执行 %d 条（%s）"
          % (target, catalog["count"], len(catalog["categories"]),
             baseline["blocked"], baseline["context"], baseline["ready"],
             "实测" if statuses else "推断，引擎没起起来"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
