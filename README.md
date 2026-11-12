# PhotoCraft-Draw

这是一个画面结构工具。`plan` 用三维坐标描述对象、位置、形状、遮挡关系，绘制器按实际命令生成白模和分层 PSD。

人物造型、颜色、材质、光线以对象说明或明确参考为准；输出不包含模型适配或生成请求。

**当前统一主链：** 目标判断 → 必要时 `plan` → 校验 → 白模 → `prompt` 输出通用 `photocraft-layout/v2` → 细节交接。

## 常用输入和输出

| 名称 | 含义 |
|---|---|
| `plan` | 组件、位置、尺寸和绘制层次的 JSON |
| 白模 | 确认几何关系的 PNG，另有分层 PSD |
| Layout | 从真实绘制命令导出的 v2 结构 |
| `details` | 对象造型要求及每张参考的职责 |
| `quick` | 只比较位置时的快速命令序列 |

## 新版使用流程

PhotoCraft-Draw 用三维坐标控制对象的位置、形状、接触和遮挡。人物造型、服饰、材质和光线由画面说明或指定参考图负责。

### 先判断是否需要几何

1. 关系简单的画面直接写目标，交给 `image-prompt`，不用建立 `plan`。
2. 已有图片只改选定对象时，写清对象、保留区域和排除项，不用重画结构。
3. 只比较主体位置、大小和图文排布时，使用 `quick` 出试稿。
4. 人物关节、握持、咬合、兵器碰撞或前后遮挡必须成立时，再写 `plan` 并生成正面白模。

完整判定树位于 [完整判定树](skills/photocraft-draw/references/workflow.yaml)。本项目负责几何、白模和参考职责；模型、提示词转换、上传、生图和下载由 `image-prompt` 负责。

### 精确结构的实际命令

花果、人物和场景共用同一套绘制命令。下面用遮挡盒子演示，曾在本机实际执行：

```sh
photocraft-draw components --search 盒
photocraft-draw verify plans/box3d-test.json
photocraft-draw draw plans/box3d-test.json --out-dir out
photocraft-draw prompt plans/box3d-test.json --out out/layout.json
```

1. 在 `plan` 中声明画布、组件、部件参数和必要的深度关系。
2. `verify` 检查真实部件和画布范围；`check` 同时检查配色。
3. `draw` 输出 PNG 白模和 PSD，两种格式必须放在同一个目录。
4. `prompt` 用同一套绘制命令导出 `photocraft-layout/v2`。默认等于 `--detail geometry`。
5. 检查没通过，改原 `plan`。不要修改生成 JSON 掩盖几何问题，也不用生图反复试错。

如果只需要试验位置，可以跳过前两步：把一串绘制命令交给 `quick`。

```sh
photocraft-draw quick whitebox.json
```

### 检查器按当前问题使用

1. `verify`：部件数量、位置、画布边缘裁切。
2. `motion`、`facing`：施力方向和人物朝向。
3. `relations`：兵器、手臂及空间交叉。
4. `contact`：握持、咬合和遮挡必须落实到 PSD 时使用。
5. `views`：仅靠正面图无法解释空间关系时使用。
6. `colors`、`occlusion`：分辨相邻颜色、检查实际层间遮挡时使用。

要判定的关系成立就结束几何工作。这些检查不必全部执行，某一项通过也不证明画面全部正确。

### 按需输出几何、语义和参考职责

```sh
photocraft-draw prompt plans/xxx.json --detail geometry --out out/layout.json
photocraft-draw prompt plans/xxx.json --detail semantic --out out/semantic.json
photocraft-draw prompt plans/xxx.json --detail components --out out/components.json
photocraft-draw details plans/with-details.json --handoff out/visual.json
```

默认 `geometry` 在 `layers` 中给出实际绘制层、部件与坐标范围。`semantic` 给出方案层语义，按已有的 `details` 增加对象说明和参考职责。`components` 在相同结构上另加 `components`。

形状直接来自绘制命令，曲线按离散后的填充形状计范围。人物骨架只来自 `figure_rig` 的姿态表。兵器主轴和分段来自已有几何切分器。

`details` 只记录必要对象细节。每张参考图应说明 `targets`、`roles`、`instruction`、`avoid`，多张图可以分管局部，同一张也可承担多个职责。

`visual.json` 只含画面描述、画布和参考职责，不包含模型参数或上传地址。说明明确的对象造型不必另造白模，没有声明的参考不自动补造。

### 结果与返修的分工

`depth` 控制遮挡顺序，`z` 控制空间深度。文字用 `annotations` 记录，文字框是估算，不是光栅化测量。人物骨架当前只覆盖 `figure_rig`，其他人物组件不补造关节。

返修时先指认当前问题：位置和关节回改 `plan`，造型与材质回对象说明，接触问题只改动相关对象。已成立的部分列为保留项。

`sheet` 和 `annotate` 只用于讲解、复述或逐层确认，不进入常规结构流程。

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
  checker.py       结构检查：部件齐全、位置合规
  envelope.py      包络检查：部件是不是落在人形或马形里
  colorize.py      配色检查：颜色差距、同组与豁免
  grouping.py      部件归组：同件物体与同类物件
  geometry.py      将绘制形状转成多边形，判断真实相交
  pixel_colors.py  按形状相交检查相邻颜色
  solver.py        局部或全局的配色求解
  occlusion.py     遮挡分析：分层文件里谁挡住谁
  contact.py       接触点与穿帮检查：交叠在哪、关节压住谁、兵器穿没穿过去
  depth.py         立体关系：层序翻译成深度表和三维坐标
  motion.py        动作检查：角色往哪个方向使劲
  facing.py        朝向检查：角色给观众看的这一面
  relations.py     兵器空间关系：距离、交叉、穿缝、地面投影
  views.py         三视图：正视图、左视图、俯视图
  split.py         兵器按深度分段
  brief.py         画面稿翻译：方案转中英文提示词
  scatter.py       撒点填充
  annotate.py      图层批注页
  cli.py           命令行入口
  components/      构图组件
plans/             绘制方案
docs/              画法约定、遮挡规则、组件参考
skills/            skill 本体，供支持的客户端直接加载
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
photocraft-draw verify plans/framework.json # 查结构和包络，不出图
photocraft-draw draw plans/framework.json --out-dir out
photocraft-draw brief plans/framework.json --out-zh 中文.txt --out-en 英文.txt
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

## 中间稿与最终成品的分工

出图分两段，手段不能混着用。中间稿只回答位置摆得对不对：谁在前谁在后、留多少边距、文字排在哪一行。这一段能省则省，由 `quick` 直接把一串命令交给绘制服务，不必准备绘制方案。把下面这份 JSON 存成任意名字的文件，交给 `quick` 就能出图：

```json
{
  "name": "位置关系草稿",
  "canvas": [800, 600],
  "background": "transparent",
  "commands": [
    {"id": "layer.newFillLayer.solidColor", "params": {"color": "#E8DCC8"}},
    {"id": "shape.create", "params": {"kind": "rect", "rect": [0, 400, 800, 200], "fill": "#A8B8C0", "stroke": null, "name": "远山"}},
    {"id": "type.create", "params": {"x": 400, "y": 160, "text": "标题", "font": "Noto Sans CJK SC", "size": 48, "color": "#2A2A2E", "align": "center", "name": "标题"}},
    {"id": "file.scripts.deleteAllEmptyLayers", "params": {}}
  ]
}
```

```sh
photocraft-draw quick whitebox.json --verbose
```

命令序列写明画布、背景和要执行的条目。条目带 `id` 的走命令目录，编号的参数由 `photocraft-draw commands --describe` 给出；带 `method` 的走文档层方法，比如 `doc.place`。字体名按本机装的中文字体改。条目按顺序执行，最后同时输出 PNG 和 PSD，默认落在 `out/` 下，也可以用 `--png` 和 `--psd` 另指定。这套做法的实测数据和阶段边界的完整说明收在 `docs/whitebox-quick-experiment.md`。

白模确认之后进入最终阶段，要把图片素材、文字和组件组合成可交付的成品，这一段的手续一件都不能省：由绘制方案把位置和层序固定成图层组，缺的结构新增构图组件并登记进 `registry.py`，照片转绘、羽化、调色这类位图素材预处理该上就上，最后走 `draw` 交给引擎输出 PSD，文字仍是文字层、形状仍是形状层，交付之后还能改。七步工作流管的是这一段，`quick` 只管前一段。

PIL 在最终阶段管位图素材本身，比如裁切、羽化、调色和拼长条；图层之间的组合交给绘制方案和引擎。把各层焊成一张位图，文字层和形状层就都没了，PSD 交付后能改这个好处也跟着没了。

## 绘制方案

```json
{
  "name": "框架示例",
  "canvas": [1600, 900],
  "ref_width": 800,
  "palette": "fresco",
  "caption": "PHOTOCRAFT-DRAW 0.1",
  "layers": [
    {
      "name": "室内背景",
      "depth": 1,
      "components": [
        {"component": "indoor_backdrop", "params": {"wall": [0, 0, 800, 450]}}
      ]
    },
    {
      "name": "长条餐桌",
      "depth": 0,
      "components": [
        {"component": "long_table", "params": {"table": [50, 300, 700, 40]}}
      ]
    }
  ]
}
```

字段说明：

1. `canvas` 是最终像素，`ref_width` 是组件的参考宽度，组件坐标按参考宽度写，脚本按 `canvas宽 / ref_width` 统一放大。
2. `palette` 可以是配色名，也可以直接写角色表；组件里的颜色写角色名（bg、ink、line 等），不写死色值。
3. `background` 可选，写一个角色名，铺满整张画布；如果室内背景的墙已经铺满画布，就不用写，否则会多出一层颜色完全相同的底色。
4. `document_background` 可选，默认 `transparent`，不生成 `Background` 层，画完会自动清掉空图层；要白底就写 `white`。
5. `caption` 可选，画面左下角的一行字，会建成文字层，PSD 里可以改；`caption_color` 可选，默认 surface。
6. `layers` 按顺序画，先写的在下面，后写的压在上面；每一层是一个图层组，层里的组件是子组。
7. 每层可以写 `depth`，数字越大离观众越远。写了 `depth` 的层，层序由 `depth` 决定，数组顺序只用来分不出远近时的先后；`depth` 要么每层都写，要么都不写。
8. 也可以只写 `components`，每个组件单独成层，适合快速试验。
9. 人物层可以写 `motion`，声明这一层往哪个方向使劲。`action` 取动作词表里的词，`angle` 是方向角（0 度朝右，90 度朝下，180 度朝左，270 度朝上），`opponents` 写交战对象。`angle` 要落在 `action` 要求的范围里，超出范围在校验阶段就报错。兵器层写 `holder` 指明归谁拿。
10. 兵器层可以写 `segments`，一件兵器按深度拆成几段。每段写主轴上的起止位置 `from` `to`、这一段在白模里的前后顺序 `depth`，还有物理深度 `z_from` `z_to`。一件直兵器在空间里的深度是沿着长度一条直线变的，写两个数才是真的斜坡。各段各写一个深度，俯视图上就成了一堆平行的横线，`relations` 会报「地面投影是折的」。段的位置比例由模型算，不要手填。
11. 段上的 `depth` 要落在这一段 `z_from` `z_to` 换算出来的深度范围里。落在范围外说明前后顺序和空间位置打架了，校验阶段就报出来。

## 检查与出图

结构画完先验，验过了再译成提示词。

```sh
photocraft-draw verify plans/xxx.json --expect horse --envelope horse
photocraft-draw colors plans/xxx.json
photocraft-draw colors plans/xxx.json --pixel
photocraft-draw occlusion out/xxx.psd
photocraft-draw contact out/xxx.psd --plan plans/xxx.json --map out/contact-map.png
photocraft-draw depth out/xxx.psd
photocraft-draw depth out/xxx.psd --plan plans/xxx.json
photocraft-draw motion plans/xxx.json
photocraft-draw facing plans/xxx.json
photocraft-draw views plans/xxx.json --out-dir out --json out/views.json
photocraft-draw relations plans/xxx.json --json out/relations.json
photocraft-draw brief plans/xxx.json --out-zh 中文.txt --out-en 英文.txt
```

`verify` 查部件齐不齐、有没有出画、姿态对不对，`--envelope` 再用人形或马形的椭圆包络卡一遍；`colors` 查相邻部件同色或颜色太近；`occlusion` 读分层文件，列出谁挡住谁、挡了多少像素；`contact` 在遮挡之上再走一步，报交叠发生在哪个坐标、方案的关节压住哪些部件、有没有兵器从手或头上穿过去；`depth` 把层序翻译成深度表和三维坐标，带 `--plan` 就用方案里声明的 `depth` 算 z，再逐层对照方案和成品；`brief` 按图层顺序把方案串成中文稿和英文稿，中文稿给人确认，英文稿直接喂生图模型。

## 配色分组、色参与几何检查

直接安排颜色时，组件的 `colors` 优先于同一组件里的旧颜色参数。比如胶囊马可以写 `{"body": "mid", "colors": {"body": "#B27D4B", "dark": "#362C26"}}`，马身实际采用 `colors.body`；鬃毛和蹄采用 `colors.dark`。胶囊骑手支持 `horse、rider、skin、dark`，人物组件支持 `robe、trim、shade、skin、hair、collar` 中适用的几项，具体以 `photocraft-draw components` 的输出为准。`soft_shadow` 的 `fill` 优先于旧的 `color`。

同色或近色不一定需要拆开。同一件衣物的衣身与袖子、同一物体上的各块面、天空的连续色带，应该先声明归属。`custom_shape` 和 `mesh_scene` 的参数可以写 `group`；要按部件主体词归组时写 `group_by`。组件代码里可以用 `pen.group("名称")` 和 `pen.group_by("前缀")` 声明同样的事。图层之间有意接近的渐变可以写 `exempt`，列出另一层的名字；`exempt` 只处理已经明确的同一片景，不拿来盖住尚未判断的颜色问题。

```sh
photocraft-draw colors plans/xxx.json --pixel
photocraft-draw colors plans/xxx.json --pixel --fix
photocraft-draw colors plans/xxx.json --pixel --fix --apply
photocraft-draw colors plans/xxx.json --pixel --fix --global-fix --apply
```

`colors` 默认按包围盒判断，速度快但会把距离远的部件算进来。`--pixel` 将路径、椭圆和矩形转换成多边形，按形状是否真实相交判定，不对每个部件重复渲染图片。`--fix` 默认只局部调整；`--global-fix` 会重新排整幅画的相邻色，只有需要整体改色时才使用。`--apply` 才可以把求解结果写回方案。

求解器用于发现可行色值，画面颜色仍由方案作者决定。先确定前景、主体、远景的明度关系，再检查颜色差距；不要把部件推到近乎纯黑或纯白只为得到通过标记。形状相交也不等于两个颜色在成品中直接相邻，中间有第三个形状遮挡、透明区域、描边和阴影时，还要结合 PNG 或 PSD 复核。`verify` 负责结构、包络和出画检查，与配色、实际出图是三件不同的事。

`motion` 查每个角色往哪个方向使劲。它读绘制方案里的 `motion` 声明，核对意图向量、骨段方向和兵器主轴三者的关系：兵器和意图反向报拿反了，手离兵器太远报手没有握在兵器上，两个交战角色的意图向量夹角太小报对抗读不出来，两件兵器的交叉角太小报画面上叠成一条线。这一层要在写方案的时候就过一遍，动作含糊的话遮挡关系照样能算对，画出来的东西不对。

`facing` 查每个角色给观众看的这一面。量肩宽、头位、颈躯拧角、躯干倾角和肩线高差五样，核对声明的朝向和关节表对不对得上。项目规矩禁止背场，背对观众报出来由作者定夺。

`views` 出正视图、左视图、俯视图三张图。正视图管左右和高度，左视图管谁在前谁在后，俯视图管两个兵器在平面上是不是真的交叉。三张图里人物和兵器按远近一起画，远的先画，近的后画，跟白模同一套次序。两件兵器在画面上交叉的地方，连着的那一条就是离观众更近的那一条。报告给每个角色站在画面哪一格、离地多少、两人高低差，给两件兵器的深度和它们在画平面上的交点，深度差超过 24 像素报「它们碰不到一起」。

`relations` 算兵器和肢体在空间里的关系。拿线段算最近距离、算两件兵器在画面上交叉没有、算兵器有没有从持械者的胳膊和兵器之间的那个缝里穿过去。兵器压在胳膊上而深度在前头三十像素以上，报「从前面扫过去」，那是对的；深度卡在两者中间才报「缝里穿过去」，那是错。另外算每件兵器的地面投影，各段的深度连不成一条直线就报「地面投影是折的」。

## 几何数据与坐标来源

`semantic`、`components` 或 `geometry` 只是数据取用的层次，它们使用同一套几何来源。
`bbox_source` 区分填充路径离散、基本图元和线段中心线。计算时不含描边。文字记录为 `font_estimate`，其范围不是字体实际渲染测量。
`scene_caption` 提供整体画面描述，`caption` 用于左下角小标题。


## 组件扩展的编写约定

`photocraft-draw components` 列出当前组件，完整目录见 `skills/photocraft-draw/references/组件目录.txt`。花、人物、道具和网格使用相同的 Layout 导出规则。


`--width`、`--height`、`--detail geometry` 控制目标画布几何尺寸和输出增量；布局与画面人物各自独立。


## 命令目录

953 条绘制指令分 38 个类别，数据在 `photocraft_draw/catalog.json`，引擎升级后用 `python3 tools/build_catalog.py` 重新生成。

每条命令除了编号、名称和参数，还带一组会话可用性标注，说明它在绘制服务里能不能直接跑。serve 常驻会话会拦下带环境文件系统路径的命令，一次性执行模式没有这层限制，先查这一组字段，省得调下去才报错。

1. `session_state` 取「可执行」「看上下文」「会话禁用」三种，分别表示随时能跑、要等文档或选区满足条件、serve 会话一律拒绝。
2. `session_evidence` 标明判断的来路，「实测-调用」是真的执行过并收到拒绝，「实测-查询」是查询 `engine.commands` 得到的空文档基线；`session_reason` 给出引擎报的原始原因。
3. `session_alternative` 是被拦下时改用的文档层方法，`session_alternative_note` 说明替代方法少了哪些参数；没有等价方法时值为「无」，只能改走一次性执行模式。
4. `path_root` 说明路径要相对哪个根，`path_params` 列出哪几个参数是路径。

会话可用性跟着当前文档状态走，引擎当场返回的 `engine.commands` 才是最终依据，目录里记的是新建 800×600 空文档的基线，`session_baseline()` 可以读出它。`blocked()` 一次列出全部被拦命令，当前基线是 66 条。

```sh
photocraft-draw commands --count
photocraft-draw commands --search 曲线
photocraft-draw commands --search 锐化 --limit 10
photocraft-draw commands --category 滤镜效果 --limit 20
photocraft-draw commands --describe image.adjustments.curves
photocraft-draw commands --describe file.placeEmbedded
photocraft-draw commands --search 会话禁用 --limit 10
```

命令可以接在方案的后面执行，用来做后期：

```sh
photocraft-draw apply plans/framework.json image.adjustments.brightnessContrast \
  --params '{"brightness": 5, "contrast": 5}' --png out/graded.png
```

## 文档层

除了画图，绘制服务还有一组文档方法，已经收进 `DocumentBook`，也可以直接用 `Engine`：

| 方法 | 作用 |
|---|---|
| doc.new | 新建文档，默认透明 |
| doc.open | 打开已有 PSD 或图片 |
| doc.place | 把一张图片置入当前文档，作为智能对象 |
| doc.render | 渲染当前画面，返回 PNG |
| doc.save | 保存成 PNG、PSD、JPG 等 |
| doc.inspect | 读尺寸、层数、顶层名称和当前图层 |
| engine.execute | 执行一条绘制指令 |
| jobs.list / jobs.cancel | 看后台任务、取消任务 |

命令行：

```sh
photocraft-draw doc inspect out/framework.psd
photocraft-draw doc render out/framework.psd --png out/preview.png --max-side 1200
photocraft-draw doc place out/framework.psd <要置入的图片> --x 40 --y 40 --scale 20 --out out/placed.psd
photocraft-draw doc jobs
photocraft-draw doc cancel <任务编号>
```

示例里的 `<要置入的图片>` 换成自己手上的图片文件。`doc.open` 和 `doc.place` 读的文件必须在绘制服务的读取根里，命令行默认用项目当前目录；`doc.save` 写在目标文件所在目录。`doc.render` 的 base64 不会进模型，命令行只回路径和字节数；`doc.inspect` 只回摘要，不拉整棵图层树。

Python 里用 `DocumentBook`：

```python
from photocraft_draw.engine import Engine
from photocraft_draw.documents import DocumentBook

with Engine(read_root=".", write_root="out") as engine:
    book = DocumentBook(engine)
    book.open("out/framework.psd")
    print(book.inspect())
    book.render_to("out/preview.png", max_side=1200)
```


## 组件目录

一共 51 个，`photocraft-draw components` 输出完整参数。画法约定在 `docs/component-references.md`，人物和马的比例配方在 `docs/figure-recipes.md`，遮挡规则在 `docs/occlusion-rules.md`。

| 分组 | 编号 | 名称 | 必填参数 |
|---|---|---|---|
| 室内底子 | indoor_backdrop | 室内背景 | wall |
| 室内底子 | arched_windows | 拱形窗户 | windows |
| 室内底子 | long_table | 长条餐桌 | table |
| 建筑光影 | coffered_ceiling | 藻井天顶 | ceiling |
| 建筑光影 | side_drapery | 两侧帷幔 | draperies |
| 建筑光影 | window_glow | 窗光 | window |
| 建筑光影 | soft_vignette | 四角阴影 | frame |
| 桌上器物 | dinner_plate | 盘子 | center |
| 桌上器物 | bread_loaf | 面包 | center |
| 桌上器物 | wine_goblet | 酒杯 | center |
| 桌上器物 | table_cloth_folds | 桌布褶 | area |
| 平视人物 | seated_figure | 坐姿人物 | seat |
| 平视人物 | leaning_figure | 前倾人物 | seat、elbow |
| 平视人物 | figure_head | 人物头部 | center |
| 平视人物 | figure_hands | 一组手 | hands |
| 平视人物 | figure_row | 一排人物 | row、count |
| 平视人物 | rider_placeholder | 骑手占位 | box |
| 山景底子 | alpine_sky | 高山天空 | area |
| 山景底子 | alpine_peaks | 雪山 | peaks |
| 山景底子 | rocky_ground | 岩地 | area |
| 山景底子 | river_water | 河流 | area |
| 山景底子 | foreground_rocks | 前景石块 | rocks |
| 白模人物 | figure_rig | 人物白模 | root、height |
| 白模人物 | rig_person | 方块人 | root、height |
| 白模人物 | block_figure | 积木人 | root、height |
| 白模人物 | pixel_person | 像素人 | root、height |
| 白模人物 | capsule_person | 胶囊人 | root、height |
| 白模动物 | rig_horse | 关节马 | root、length |
| 白模动物 | block_horse | 积木马 | root、length |
| 白模动物 | capsule_horse | 胶囊马 | root、length |
| 白模动物 | capsule_rider | 骑手 | root、length |
| 三维场景 | box3d_scene | 三维盒子 | boxes |
| 三维场景 | rider3d | 三维骑手 | root、length |
| 通用形状 | custom_shape | 自定义路径 | subpaths |
| 通用形状 | ascii_art | 字符画 | art |
| 通用形状 | scatter_shape | 撒点填充 | box |
| 通用形状 | soft_shadow | 地面投影 | center、rx、ry |
| 现代题材 | bottle | 饮料瓶 | base |
| 现代题材 | apple | 苹果 | center |
| 现代题材 | apple_tree | 苹果树 | root |
| 现代题材 | truck | 厢式货车 | origin |
| 现代题材 | display_stand | 梯形货台 | frame |
| 现代题材 | holding_hand | 握持的手 | center |
| 花林包装 | grove_backdrop | 花林背景 | 无 |
| 花林包装 | crabapple_tree | 海棠树 | root |
| 花林包装 | crabapple_grove | 海棠花林 | trees |
| 花林包装 | crabapple_spray | 海棠花枝特写 | 无 |
| 花林包装 | grove_label | 包装文字 | 无 |
| 三维场景 | perspective_scene | 透视场景 | 无 |
| 网格有机 | mesh_scene | 网格场景 | meshes |
| 网格有机 | organic_layer | 有机形状层 | camera |

新增组件：在 `photocraft_draw/components/` 写 `build(params, pen)`，只画形状和文字，不建图层；图层由绘制方案负责。再到 `registry.py` 登记编号、名称、说明和参数。

## 测试与当前样例的状态

```sh
python3 -m pytest tests -q
photocraft-draw colors plans/scene-landscape.json --pixel
photocraft-draw draw plans/scene-landscape.json --out-dir out
```

当前测试结果：637 项通过，1 条第三方 pytest 插件的弃用警告。测试覆盖通用几何、人物骨架、兵器分段、文本估算、属性细节、参考职责和画面交接。最近精修的 15 份样例均通过 `colors --pixel`，并且成功生成 PNG 和 PSD。这组样例包括 `scene-landscape`、`dining-hall`、`framework`、`supper-demo`、`last-supper`、`scene-street`、`alpine-crossing`、`dawn-scene`、`dawn-napoleon`、`dawn-napoleon3d`、`mountain-horse`、`spray`、`scene-interior`、`scene-still-life`。

其中 11 份在额外的 `verify` 中仍报告画布边缘裁切。裁切来自原有的前景石头、四角暗角、花枝、右侧建筑或透视桌面，本轮配色精修没有调整它们的布局。颜色检查通过、实际出图成功、全部结构检查通过，这三个结果不要混为一谈。

配色规则的详细说明见 [docs/color-rules.md](docs/color-rules.md)，本轮重构与参数约定见 [docs/color-refactor-notes.md](docs/color-refactor-notes.md)。

## 图层批注与按需展示

`annotate` 生成 PSD 的逐层开关与选区批注页。只在用户要求查看或修改单个图层时运行，`sheet` 同样按需运行。

## 写法约定

1. 组件只写参考坐标和配色角色，不写死画布尺寸和色值。
2. 组件不建图层，图层由绘制方案统一管理。
3. 新增组件必须进 `registry.py`，写清编号、名称、说明和每个参数。
4. 先 `check` 再 `draw`，方案有问题在合成阶段就报出来。
5. 默认只回执行摘要，调试才开 `--verbose`。
6. 文字用 `type.create` 建文字层，不要在 PSD 里当图形画，这样交付后还能改字。

## 边界

1. 引擎没有 1024 像素的单边上限，那是早期记错的一条。实测 1080×3600（约 388 万像素）能正常出 PNG 和 PSD，1600×900 的示例也一直能出；更大的尺寸没有逐档测过，不写成无上限。`doc.render --max-side` 是预览图的最长边限制，只影响预览，不影响正式出图。
2. 引擎是 early alpha，PSD 能否在 Adobe Photoshop 里正常打开没有验证过，只保证引擎自己能读、第三方 psd-tools 能解析。
3. 引擎的渐变是近似，带滤镜的组会被栅格化，复杂画面要逐张看。
4. 一张画面超过一百条指令，先想能不能拆组件或简化，不要硬堆。
5. 颜色仍要人工定。按物体组自动重排色阶试过三版，都会把天空打散或把形状压平，自动色阶代码已删除。
6. 批注页目前只导出意见，回改要人工或脚本按 JSON 执行，还没有一键回改。

## 许可证

Apache License 2.0，全文见 `LICENSE`。可以商用、修改、再发布，保留版权声明和许可证副本即可。
