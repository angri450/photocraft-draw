---
name: photocraft-draw
description: 用三维坐标设计白模，压成 2.5 维画面，再把结构翻译成生图提示词交给模型出图。适合需要准确遮挡关系的人物、动物、场景，也支持分层 PSD 和原生文字层。触发词：PhotoCraft、白模、三维摆位、遮挡关系、2.5D、轴测投影、画面稿、生图提示词。
---

> 随时更新，修正 skill。本机引擎在 `D:\agent2\opt\photocraft\photocraft-cli.exe`，项目在 `D:\agent2\photocraft-draw`，引擎路径已写进用户环境变量 `PHOTOCRAFT_CLI`。命令行工具已 pip 安装，直接敲 `photocraft-draw` 即可，不需要 `python -m photocraft_draw`。

# PhotoCraft-Draw

## 这个技能做什么用

这个技能不是「画图工具」，是**白模设计器**。画笔只负责把结构摆对，质感和光影交给生图模型。

项目在 `D:\agent2\photocraft-draw`，引擎是 `photocraft-cli`。普通示意图、论文图、PPT 仍走 `svg-code-drawing`。

## 路由表

| 要做的事 | 去哪 |
|---|---|
| 查某个组件的完整参数 | [组件目录](references/组件目录.txt)，全量快照，不用跑命令 |
| 遮挡关系定深度的办法 | [关于明确遮挡关系的意见](references/关于明确遮挡关系的意见.md) |
| 先定人物动作状态的办法 | [关于确定动作状态的思维链](references/关于确定动作状态的思维链.md) |
| 接触点与穿帮提示 | [接触点与穿帮检查](references/接触点与穿帮检查.md) |
| 画人物、配色、场景构图规则 | [人物与场景画法](references/人物与场景画法.md) |
| 画多格连环画、人物兵器 | [四格连环画白模做法](references/四格连环画白模做法.md) |
| 直接开画 | 参照下面「核心思想」和「结构验证与画面稿翻译」 |

## 核心思想三维定结构

这套做法的名字：**轴测投影**加**画家算法**。每个部件先在三维坐标里定位置，再沿着一个固定方向压到平面上；绘制时按离观众的远近排序，远的先画、近的后画，近的自动盖住远的。艺术史上相近的做法是**立体主义**，把三维物体拆成几何形体，再在一个平面上重新拼起来。

一句话：**用三维的方法设计 2.5 维的画面。**

这样做解决了三件手绘解决不了的事：

- 遮挡不用猜。改一个 z 值，谁挡谁就变了，不用重排顺序。
- 结构可验证。部件齐不齐、出没出画、在不在人形或马形里面，命令一跑就知道。
- 结构能复用。同一套坐标表换个姿态、换个尺寸，还是同一个人。

## 三维坐标的书写约定

每个部件给两端点加一个宽度，端点带 z：

```json
{"x": 0.02, "y": 0.10, "z": -0.09, "w": 0.09}
```

坐标以主体上的一个锚点为原点，单位是肩高或身高，调用时给一个像素值整体缩放。z 越大越远。

投影时 z 会变成画面上的少量偏移（默认横向 0.42、纵向 0.22），看起来有一点斜视的立体感。调大了更像等距视角，调小了更像正交投影。

## 位置定了怎么配颜色

位置定完再定颜色，分三层：背景冷、主体暖、前景亮。

- 背景：天空、远山、近山、地面，全部冷色，明度从浅到深往下压。
- 主体：人和马，暖色，棕、赭红、浅金。
- 前景：压住画面底边的石头，比背景亮一档。

同一物体的部件保持同色系，靠明度区分，不靠换色相。撞色的地方跑 `colors`，它会告诉你是哪两个部件、差多少。具体色值和人物画法见 [人物与场景画法](references/人物与场景画法.md)。

## 结构验证与画面稿翻译

验证：

```sh
photocraft-draw verify plans/xxx.json --expect horse --envelope horse
photocraft-draw colors plans/xxx.json
photocraft-draw occlusion out/xxx.psd
photocraft-draw contact out/xxx.psd --plan plans/xxx.json --map out/contact-map.png
photocraft-draw depth out/xxx.psd --json out/depth.json
photocraft-draw depth out/xxx.psd --plan plans/xxx.json
photocraft-draw motion plans/xxx.json
```

- `verify`：部件齐不齐、有没有出画、头在不在躯干上方、马的腿是不是十二段。`--envelope` 配合人形或马形的椭圆包络再卡一遍。
- `colors`：相邻部件同色或颜色太近就报。同一物体的部件（天空色带、山的脚腰顶）算一组，组内不报。
- `occlusion`：分层文件里谁挡住谁、挡了多少像素，用来验证「该挡的挡住了」。
- `contact`：交叠发生在哪个位置、方案的关节压住了哪些部件、有没有兵器从手上穿过去。带 `--plan` 才有关节归属和穿帮提示，带 `--map` 另出一张遮挡显露图。
- `depth`：把层序翻译成深度表和三维坐标。z 越大离观众越远，坐标按引擎的投影斜度反算，重新投影一次位置不变。带 `--plan` 就用方案里声明的 `depth` 算 z，末尾多一段对照，逐层核对方案声明和成品层序。
- `motion`：查每个角色往哪个方向使劲。读绘制方案，核对意图向量、骨段方向和兵器主轴三者的关系。两人朝同一侧使劲会报「对抗读不出来」。动作这一层要在写方案的时候就过一遍，见 [关于确定动作状态的思维链](references/关于确定动作状态的思维链.md)。

翻译：

```sh
photocraft-draw brief plans/xxx.json --out-zh 中文.txt --out-en 英文.txt
```

方案里每层写 `describe_zh` 和 `describe_en`，顶层写 `brief_zh` 和 `brief_en`（主体、风格、光线、氛围、视角、色调）。`brief` 按图层顺序串成两段话，中文给人看，英文给模型看。

**图层名和 `describe_en` 都要写英文**。英文稿是直接喂给文生图模型的，图层名留中文，模型会照着中文乱画。没写 `describe_en` 的层，英文稿里会原样冒中文名，这是方案没写全，不是工具出错。

英文稿喂生图走本机的 MiniMax 出图通道：

```sh
mcode-tools connector call connector__matrix__generate_image --args-file 出图参数.json
```

```json
{"requests": [{"prompt": "英文稿全文", "aspect_ratio": "3:4", "resolution": "2K", "output_file": "final.png"}]}
```

`aspect_ratio` 可选 `1:1`、`16:9`、`9:16`、`4:3`、`3:4`、`21:9`，`resolution` 可选 `1K`、`2K`、`4K`。一次只提交一条请求。成功后返回 `node_id`，调 `mcode-tools get_asset_url <node_id>` 取下载地址，再自己存到本地。

## 可用组件与常见陷阱

`photocraft-draw components` 列出完整参数。常用的几组：

| 编号 | 干什么 |
|---|---|
| `box3d_scene` | 通用三维盒子，任意部件按 z 排序 |
| `rider3d` | 骑马的人，马和人有各自的 z |
| `block_figure` / `block_horse` | 积木人和积木马，由正方体拼成的 |
| `capsule_person` / `capsule_horse` | 胶囊人和胶囊马，四肢两端是圆的 |
| `alpine_sky` / `alpine_peaks` / `rocky_ground` / `river_water` / `foreground_rocks` | 山、天、地、河、石 |
| `soft_shadow` | 地面投影，把主体按在地上 |
| `custom_shape` | 任意路径，贝塞尔曲线 |
| `figure_rig` | 关节白模人，姿态可给内置名，也可直接给 14 关节表 |
| `ascii_art` | 字符画转矩形 |

新组件在 `photocraft_draw/components/` 里实现 `build(params, pen)`，只画形状，不建图层，再到 `registry.py` 登记。

实际有八个坑要绕开：

1. **全局重着色会压平形状**。颜色和语义绑在一起，算法不知道马该是棕的。撞色只做局部微调，别整体重排。
2. **同一个人的两条腿深度不同**。近侧腿挡马身，远侧腿被马身挡，不能一起算。
3. **手臂要画在躯干之前**。否则手臂根部露在胸口，出现一条斜线。
4. **`custom_shape` 的 `subpaths` 必须是扁平的 `[{closed, knots}]`**。多写一层嵌套会报 `'list' object has no attribute 'get'`。
5. **`figure_rig` 不适合走 `colors` 检查**。它的关节天然同色，检查一定误报，例如「关节 chest 和关节 neck 颜色都是 xxx」。这类人物改用 `verify` 配 `occlusion`。
6. **`custom_shape` 的包围盒按锚点算，不按贝塞尔控制点算**。控制点甩到画布外，`verify` 不报，但渲染会画出去。自己按控制点范围再扫一遍。
7. **同一层里的多个组件按列表顺序压盖**，后面的盖住前面的。可以拿底色形状叠出镂空，例如给兽头叠一个底色的嘴形。
8. **兵器会从手背后穿过去**。兵器单独成层，画在角色层前面，只要路径蹭到手的关节圆盘，手就被盖住，看上去像握着，其实手在兵器后面。`contact` 的「夹手」和「疑似穿手」两条提示查的就是这个。

## 出图与回改循环

```sh
photocraft-draw draw plans/xxx.json --out-dir out
```

产物是 `out/xxx.png` 白模图和 `out/xxx.psd` 分层文件，图层是图层组。文件名默认跟方案同名，`--png` 和 `--psd` 能另指定路径。PNG 和 PSD 必须在同一个目录，绘制服务一次只写一个目录。

出图后跑 `annotate` 生成批注页，按顶层图层导出透明图，叠成简易 Photoshop，可以开关图层、框选写意见：

```sh
photocraft-draw annotate plans/xxx.json --out-dir out
```

批注页是 `out/xxx.review.html`，放在 PNG 旁边。`--png` 和 `--psd` 指向的文件不存在时会先自动出图。加 `--serve` 会起本地网页服务，默认端口 8898。要把批注页发给别人，用 `website_deploy` 发布成 MiniMax 站点链接，不要给内网地址。

批注返回的 JSON 带 `layer_name`、`rect` 和意见，按图层名回改绘制方案，重新验、重新译、重新出图。

## 多格连环画的排法

连环画每一格当独立方案做，不要塞进同一份文件。三条理由。

一、遮挡分析互不干扰。`occlusion` 读的是分层文件，一格一份，报告里只出现这一格的人，不会把别的格的人物算进来。

二、每格能单独返工。哪一格的动作不对，只改那一格的文件，重跑那一格，其余三格不动。

三、最后再拼长条。每格出 900 乘 1200 的 PNG，用 Pillow 按顺序贴成一条长图：

```python
from PIL import Image
strip = Image.new("RGB", (W * 4, H), BG)
for index in range(4):
    image = Image.open(f"panel{index + 1}.png").convert("RGBA")
    strip.paste(image, (index * W, 0), image)
strip.save("长条.png")
```

生成器的完整范例在 `D:\agent2\comic\build.py`，一份文件写方案、跑 `verify`、跑 `draw`、跑 `occlusion`、跑 `brief`、拼长条，改参数重跑。人物兵器、屋脊、兽类剪影的具体做法见 [四格连环画白模做法](references/四格连环画白模做法.md)。

## 本机可跑的示例方案

`D:\agent2\photocraft-draw\plans\` 下有 24 份方案，都是能跑通的。新手先看这三个：

| 方案 | 场景 |
|---|---|
| `box3d-test.json` | 三个盒子按 z 叠放，最小样例，遮挡关系最直观 |
| `mountain-horse.json` | 完整场景，7 层：天空、远山、近山、岩地、河流、马、前景 |
| `horse-sheet.json` | 积木马部件表，练 `verify --expect horse` |

改动方案时先复制到自己的目录再改，不要动 `plans/` 里的原件。
