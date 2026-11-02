# PhotoCraft-Draw

用构图组件和绘制方案驱动 PhotoCraft 出图。一张画面先分图层，每层由若干构图组件拼成，组件只写参考坐标，脚本换算成画布坐标和绘制指令，引擎落成 PNG 和 PSD。PSD 里图层是图层组，文字是文字层，交付后还能改。

## 中文叫法

| 叫法 | 含义 |
|---|---|
| 构图组件 | 一段可复用的绘图代码，负责画面的一部分 |
| 绘制方案 | 一份 JSON，按图层列出用哪些构图组件、各给什么参数 |
| 组件目录 | 构图组件的清单和参数说明 |
| 图层 | 画面的一层，PSD 里是一个图层组 |
| 画面模板 | 整套构图方式，比如室内场景、海报 |
| 绘制指令 | 发给引擎的一条条命令 |
| 绘制服务 | 常驻进程，接收绘制指令并调用引擎 |
| 执行摘要 | 引擎返回的简短结果 |

## 七步工作流

1. 收到题目先想清楚画面要讲什么，把画面分成几个图层，每层写一句用途。
2. 到组件目录里找现成的构图组件，先搜再用，不要重复造。
3. 没有合适的组件，就新写一个：`photocraft_draw/components/` 下建文件，写 `build(params, pen)`，再到 `registry.py` 登记。
4. 把组件按层填进绘制方案，每层可以放一个或多个组件。
5. 做完一层就先 `check` 看指令数和参数，确认这一层没问题。
6. 所有层按从后到前的顺序排好，`draw` 一次组装成图；程序会把每个顶层组提到最前，保证后画的压在前面。
7. `annotate` 生成单文件批注页，你在网页上点图层、拖方框、写意见，导出 JSON 发回来，我按 JSON 改。

## 目录

```text
photocraft_draw/
  engine.py        绘制服务：找引擎、起会话、执行、存图
  commands.py      绘图笔：参考坐标换算、绘制指令生成
  palette.py       配色角色
  registry.py      组件目录
  plan.py          绘制方案：读取、校验、按图层合成
  commandbook.py   命令目录：953 条指令的检索和调用
  catalog.json     命令目录数据，由 tools/build_catalog.py 生成
  annotate.py      图层批注页
  cli.py           命令行入口
  components/      构图组件
plans/             绘制方案
tools/             命令目录生成工具
tests/             单元测试
out/               默认输出目录
```

## 安装

引擎是 `photocraft-cli` 0.19.0，发行包一百多兆，不进仓库。解压到 `~/opt/photocraft/`，然后让程序能找到它：

```sh
mkdir -p ~/opt/photocraft && cd ~/opt/photocraft
curl -L -o photocraft.tar.gz \
  'https://ghfast.top/https://github.com/storytold/photocraft/releases/download/v0.19.0/photocraft-0.19.0-linux-x86_64.tar.gz'
echo '123385b1730ace18f12bc0f494606e6a4cd3f4ab891f93036cd4e71b8aea70f7  photocraft.tar.gz' | sha256sum -c -
tar xzf photocraft.tar.gz
export PHOTOCRAFT_CLI=~/opt/photocraft/photocraft-0.19.0-linux-x86_64/bin/photocraft-cli
```

项目本身没有第三方依赖：

```sh
cd code/photocraft-draw
python3 -m pip install -e .
```

不装也能用，在项目根目录跑 `python3 -m photocraft_draw` 就行。

## 用法

```sh
photocraft-draw doctor                      # 看引擎路径和版本
photocraft-draw components --search 窗      # 搜构图组件
photocraft-draw check plans/framework.json  # 校验方案，统计图层、组件和指令
photocraft-draw draw plans/framework.json --out-dir out
photocraft-draw annotate plans/framework.json --out-dir out --serve
```

`draw` 默认同时写 PNG 和 PSD，也可以只给一个：

```sh
photocraft-draw draw plans/framework.json --png out/a.png
photocraft-draw draw plans/framework.json --png out/a.png --psd out/a.psd
```

默认只回一行执行摘要：

```text
ok | 1600x900 | 3 个图层 | 3 个构图组件 | 56 条绘制指令 | 3.9s | out/framework.png, out/framework.psd
```

要看每条指令的结果加 `--verbose`，平时不要开。

## 绘制方案

```json
{
  "name": "框架示例",
  "canvas": [1600, 900],
  "ref_width": 800,
  "palette": "fresco",
  "background": "bg",
  "caption": "PHOTOCRAFT-DRAW 0.1",
  "layers": [
    {
      "name": "室内背景",
      "components": [
        {"component": "indoor_backdrop", "params": {"wall": [0, 0, 800, 450]}}
      ]
    }
  ]
}
```

字段说明：

1. `canvas` 是最终像素，`ref_width` 是组件的参考宽度，组件坐标按参考宽度写，脚本按 `canvas宽 / ref_width` 统一放大。
2. `palette` 可以是配色名，也可以直接写角色表；组件里的颜色写角色名（bg、ink、line 等），不写死色值。
3. `background` 可选，写一个角色名，铺满整张画布。
4. `caption` 可选，画面左下角的一行字，会建成文字层，PSD 里可以改；`caption_color` 可选，默认 surface。
5. `layers` 按顺序画，先写的在下面，后写的压在上面；每一层是一个图层组，层里的组件是子组。
6. 也可以不写 `layers`，直接写 `components`，这时每个组件单独成一层，适合快速试验。

## 命令目录

953 条绘制指令分 38 个类别，数据在 `photocraft_draw/catalog.json`，引擎升级后用 `python3 tools/build_catalog.py` 重新生成。

```sh
photocraft-draw commands --count
photocraft-draw commands --search 曲线
photocraft-draw commands --search 锐化 --limit 10
photocraft-draw commands --category 滤镜效果 --limit 20
photocraft-draw commands --describe image.adjustments.curves
```

命令可以接在方案的后面执行，用来做后期：

```sh
photocraft-draw apply plans/framework.json image.adjustments.brightnessContrast \
  --params '{"brightness": 5, "contrast": 5}' --png out/graded.png
```

## 组件目录

| 编号 | 名称 | 必填参数 |
|---|---|---|
| indoor_backdrop | 室内背景 | wall |
| arched_windows | 拱形窗户 | windows |
| long_table | 长条餐桌 | table |

新增组件：在 `photocraft_draw/components/` 写 `build(params, pen)`，只画形状和文字，不建图层；图层由绘制方案负责。再到 `registry.py` 登记编号、名称、说明和参数。

## 批注页

`annotate` 会为每个顶层图层单独导出一张透明 PNG，只有这一层可见；网页按顺序叠放这些图，等于一个简易 Photoshop。页面是单文件，图层图和图层树都内嵌，可以直接发布到 WorkBuddy 站点：在 CodeBuddy 里用 Artifact 工具上传，拿到公开链接。`--serve` 只是本地预览的备选，端口默认 8898。

网页上可以：

1. 左边图层树点选图层，前面的眼睛开关控制显隐，关掉别的层就只看这一层。
2. 在图上拖动框选区域，卡片会自动识别框内的图层，默认取最具体的那层。
3. 写说明，Enter 保存；每条意见在图上画一个编号框。
4. 「批注」页集中列出所有意见，点一条跳回对应区域。
5. 导出 `review.json`，或在页面里复制 JSON。

导出的格式是图层、区域、意见三层数据：

```json
{
  "plan": "框架示例",
  "image": "framework.png",
  "canvas": [1600, 900],
  "annotations": [
    {
      "id": 1, "index": 1,
      "layer": 53, "layer_name": "长条餐桌", "kind": "Group",
      "rect": [925, 626, 44, 20],
      "layers": [
        {"id": 53, "name": "长条餐桌", "kind": "Group"},
        {"id": 22, "name": "室内背景", "kind": "Group"}
      ],
      "visible_layers": ["文字层", "长条餐桌", "拱形窗户", "室内背景", "底色"],
      "hidden_layers": [],
      "note": "往右挪 20 像素"
    }
  ]
}
```

框选后卡片会自动列出框内可见的顶层图层，默认取面积最小的那个作为批注对象；同时记下当时的显隐状态。JSON 里 `layer` 是选中的图层，`layers` 是框内所有可见图层，`visible_layers` 和 `hidden_layers` 是保存时哪些顶层图层显示、哪些关掉。拿到 JSON 后按名称找到构图组件参数，改绘制方案再重新出图。

按顶层图层出透明图要跑几次引擎，5 个顶层大约 2.3 秒，结果缓存在 `out/_layers/`。

## 写法约定

1. 组件只写参考坐标和配色角色，不写死画布尺寸和色值。
2. 组件不建图层，图层由绘制方案统一管理。
3. 新增组件必须进 `registry.py`，写清编号、名称、说明和每个参数。
4. 先 `check` 再 `draw`，方案有问题在合成阶段就报出来。
5. 默认只回执行摘要，调试才开 `--verbose`。
6. 文字用 `type.create` 建文字层，不要在 PSD 里当图形画，这样交付后还能改字。

## 边界

1. 现有三个构图组件，人物、面部、手势还没做。
2. 引擎是 early alpha，PSD 能否在 Adobe Photoshop 里正常打开没有验证过，只保证引擎自己能读、第三方 psd-tools 能解析。
3. 引擎的渐变是近似，带滤镜的组会被栅格化，复杂画面要逐张看。
4. 一张画面超过一百条指令，先想能不能拆组件或简化，不要硬堆。
5. 批注页目前只导出意见，回改要人工或脚本按 JSON 执行，还没有一键回改。
