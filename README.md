# PhotoCraft-Draw

用构图组件和绘制方案驱动 PhotoCraft 出图。一张画面由若干构图组件拼成，组件只写参考坐标，脚本负责换算成画布坐标和绘制指令，引擎负责落成 PNG 和 PSD。PSD 里的文字仍然是文字层，形状仍然是形状层。

## 中文叫法

| 叫法 | 含义 |
|---|---|
| 构图组件 | 一段可复用的绘图代码，负责画面的一部分 |
| 绘制方案 | 一份 JSON，写明用哪些构图组件、各给什么参数 |
| 组件目录 | 构图组件的清单和参数说明 |
| 画面模板 | 整套构图方式，比如室内场景、海报 |
| 绘制指令 | 发给引擎的一条条命令 |
| 绘制服务 | 常驻进程，接收绘制指令并调用引擎 |
| 执行摘要 | 引擎返回的简短结果 |

## 目录

```text
photocraft_draw/
  engine.py        绘制服务：找引擎、起会话、执行、存图
  commands.py      绘图笔：参考坐标换算、绘制指令生成
  palette.py       配色角色
  registry.py      组件目录
  plan.py          绘制方案：读取、校验、合成
  cli.py           命令行入口
  components/      构图组件
plans/             绘制方案
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
photocraft-draw components                  # 列组件目录
photocraft-draw check plans/framework.json  # 校验方案，统计指令
photocraft-draw draw plans/framework.json --out-dir out
```

`draw` 默认同时写 PNG 和 PSD，也可以只给一个：

```sh
photocraft-draw draw plans/framework.json --png out/a.png
photocraft-draw draw plans/framework.json --png out/a.png --psd out/a.psd
```

默认只回一行执行摘要：

```text
ok | 1600x900 | 3 个构图组件 | 48 条绘制指令 | 3.3s | out/framework.png, out/framework.psd
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
  "components": [
    {
      "component": "indoor_backdrop",
      "params": {
        "wall": [0, 0, 800, 450],
        "floor": [0, 355, 800, 95],
        "ceiling": [90, 30, 620, 70],
        "tapestries": [[18, 110, 70, 230], [712, 110, 70, 230]]
      }
    },
    {
      "component": "arched_windows",
      "params": {
        "windows": [[300, 140, 90, 150], [395, 115, 110, 175], [520, 140, 90, 150]]
      }
    },
    {
      "component": "long_table",
      "params": {
        "table": [50, 300, 700, 40],
        "front": 38,
        "plates": [140, 230, 320, 395, 460, 540, 630, 700],
        "plate_y": 320,
        "cup_x": 465
      }
    }
  ]
}
```

字段说明：

1. `canvas` 是最终画布像素，`ref_width` 是组件的参考宽度，组件里的坐标都按参考宽度写，脚本按 `canvas宽 / ref_width` 统一放大。
2. `palette` 可以是配色名，也可以直接写角色表；组件里的颜色写角色名（bg、ink、line 等），不写死色值。
3. `background` 可选，写一个角色名，铺满整张画布。
4. `caption` 可选，画面左下角的一行字，会建成文字层，PSD 里可以改；`caption_color` 可选，默认 surface。
5. `components` 按顺序画，后面的压前面的。
6. `params` 里每个组件的必填项见 `photocraft-draw components`。

## 组件目录

| 编号 | 名称 | 必填参数 |
|---|---|---|
| indoor_backdrop | 室内背景 | wall |
| arched_windows | 拱形窗户 | windows |
| long_table | 长条餐桌 | table |

## 写法约定

1. 组件只写参考坐标，不关心最终画布多大，也不写死色值。
2. 新增组件必须进 `registry.py`，写清编号、名称、说明和每个参数。
3. 先 `check` 再 `draw`，方案有问题在合成阶段就报出来。
4. 默认只回执行摘要，调试才开 `--verbose`。
5. 文字用 `type.create` 建文字层，不要在 PSD 里当图形画，这样交付后还能改字。
6. 组件参数缺项要在组件里直接报错，不要静默用默认值兜底。

## 边界

1. 首版只有三个构图组件，人物、面部、手势还没做。
2. 引擎是 early alpha，PSD 能否在 Adobe Photoshop 里正常打开没有验证过，只保证引擎自己能读、第三方 psd-tools 能解析。
3. 引擎的渐变是近似，带滤镜的组会被栅格化，复杂画面要逐张看。
4. 一张画面不要堆几百条指令，超过一百条先想能不能拆成组件或简化结构。
