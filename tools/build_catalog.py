#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从引擎导出命令目录，生成 photocraft_draw/catalog.json。

用法：
  python3 tools/build_catalog.py [photocraft-cli 路径]

不给路径时按 PHOTOCRAFT_CLI、PATH、~/opt 的顺序找。
"""
from __future__ import annotations

import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from photocraft_draw.engine import engine_version, find_engine  # noqa: E402

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


def main() -> int:
    cli = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else find_engine()
    raw = subprocess.run(
        [str(cli), "commands", "--json"], capture_output=True, text=True, check=True
    ).stdout
    entries = json.loads(raw)

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
        commands.append({
            "id": command_id,
            "label": entry.get("label", ""),
            "menu": str(menu),
            "shortcut": str(shortcut),
            "params": str(entry.get("params", "")),
            "needs_document": bool(entry.get("needsDocument", True)),
            "category": category,
            "category_name": CATEGORY_NAMES.get(category, category),
            "keywords": keywords,
        })
    commands.sort(key=lambda item: (item["category"], item["id"]))

    counts = Counter(item["category"] for item in commands)
    categories = [
        {
            "key": key,
            "name": CATEGORY_NAMES.get(key, key),
            "count": counts[key],
        }
        for key in sorted(counts)
    ]
    catalog = {
        "engine": engine_version(cli),
        "count": len(commands),
        "categories": categories,
        "commands": commands,
    }
    target = ROOT / "photocraft_draw" / "catalog.json"
    target.write_text(json.dumps(catalog, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"写入 {target}：{len(commands)} 条命令，{len(categories)} 个类别")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
