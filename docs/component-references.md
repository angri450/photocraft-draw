# 组件库参考与接口约定

日期：2026-11-02
用途：扩充 PhotoCraft-Draw 的构图组件前的共同参考，先看图和规则，再动笔。

## 一、参考来源与许可

1. 《最后的晚餐》高清图，Wikimedia Commons，公有领域（CC0/PD）。仓库的 `docs/references/` 收录了全图和七张局部裁图：`overview.jpg` 是整体构图，`left-group.jpg`、`center-jesus.jpg`、`right-group.jpg` 是三组人物，`table-detail.jpg` 是桌面，`faces-left.jpg`、`faces-right.jpg` 是两侧脸部。
2. Open Peeps，Pablo Stanley，CC0。只参考它把人物拆成头、发、五官、手、姿态的做法，不要照搬它的卡通线稿风格。
3. Humaaans，可商用但不是 CC0。不要直接复制它的文件。
4. unDraw，许可明确禁止打包再分发、程序化嵌入和用于训练。不要把它接进组件库，只能当视觉参考。
5. Excalidraw、draw.io 的图形库是示意图形状，不适合这种壁画场景。

## 二、从原画取到的颜色

按面积排序的主色：

```text
#70655a  #877160  #38271c  #54483c  #4e3a29  #5f5042
#41372e  #9a8a79  #6a5440  #a3968c  #8f8379  #b6aca5
```

规则：

1. 不用纯黑和纯白。最暗用 `#38271c`，最亮用 `#b6aca5`。
2. 现有 `fresco` 配色继续用，角色映射：bg `#d9c7a3`，surface `#e6d7b8`，ink `#3a2a1e`，muted `#7a6a55`，deep `#6b2f24`，mid `#8a6a3a`，soft `#c9b48a`，line `#9c8a6e`，accent `#f6e6bd`。
3. 大面积用低饱和土黄、赭石、灰绿；红色只做袍子和帷幔，蓝色只做披风。不要高饱和。

## 三、构图规则

1. 画布参考 800×450，横向。地平线在 52% 左右，桌子压在前景 55% 到 85%。
2. 十三个人：耶稣在正中，左右各六人，按三人一组分成四组；犹大在画面左侧、耶稣右手边，身体前倾，手肘撑桌。
3. 后墙三扇窗，中间一扇最大；顶部藻井横线向中心收；两侧挂深红或深绿帷幔。
4. 人物头部在画布高度的 26% 到 45% 之间；桌沿以上露上半身。

## 四、人物画法

1. 头身比约 1:6.5；坐姿躯干约 2.2 个头高，肩宽约 1.6 个头宽。
2. 脸用三块面：额头到鼻梁一块、颊部一块、下颌阴影一块。眼睛只画上眼睑和一点暗部，不画圆眼珠；鼻子用一条侧影或三角形暗面；嘴只画一条短线。
3. 头发是包住头骨的一整块，边缘用两三个起伏；胡须是一块向下收的形状，不画一根根线条。
4. 手用三到四个形状：手掌、拇指、并拢的四指、可选的前臂。手指不分开画，只做整体形。
5. 袍子先画大色块，再压两到三块暗部褶，最后一条亮边；不要黑色描边。
6. 姿态至少区分：正面端坐、侧身转头、前倾撑桌、双手摊开、手指指向。

## 五、器物与桌面

1. 桌布是浅色大块，前垂两到三折，褶用同色系的暗部，不用黑线。
2. 盘子是扁椭圆，边沿用比盘面深一档的颜色；面包是小椭圆或半圆；酒杯是细颈加小口，位置稀疏。
3. 每张桌子 6 到 8 个器物就够，不要堆满。

## 六、建筑与光影

1. 藻井用四到五条透视线，全部指向画面中心偏上；两侧墙用低对比的壁柱。
2. 窗户是上圆下方，窗光用比墙亮一到两档的暖色，窗棂细线。
3. 光从中间窗户进来，人物背后有一圈很淡的亮部；桌下有一块柔和的暗部，不做硬阴影。
4. 画面四角压暗，模拟壁画边缘的老化。

## 七、组件接口

1. 每个组件是一个 `build(params, pen)` 函数，放在 `photocraft_draw/components/` 下。
2. 组件里不要 `pen.stage`，图层由绘制方案负责。
3. 坐标按 800 宽的参考画布写，`pen` 会换算到目标尺寸。
4. 颜色只写角色名或 `#rrggbb`，不要写死纯黑纯白。
5. 必填参数缺失时直接 `raise ValueError`，错误信息写清要什么。
6. 一个组件控制在 120 条绘制指令以内，复杂人物拆成“身体”“头”“手”三个组件。
7. 新组件登记到 `photocraft_draw/registry.py`，由整合负责人统一合并，写组件的人不要改这个文件。
8. 每个组件配 `tests/test_<组件组>.py`，至少两条：正常参数出指令、缺参数报错。

## 八、并行分工与文件归属

| 任务 | 负责人 | 只改这些文件 |
|---|---|---|
| 人物组件 | 人物组件 | `photocraft_draw/components/figures.py`、`tests/test_figures.py` |
| 器物组件 | 器物组件 | `photocraft_draw/components/tableware.py`、`tests/test_tableware.py` |
| 建筑光影 | 建筑光影 | `photocraft_draw/components/architecture.py`、`tests/test_architecture.py` |
| 整合验收 | 整合验收 | `photocraft_draw/registry.py`、`plans/supper-demo.json`、`tests/test_supper_demo.py` |

谁都不改别人的文件和现有组件。整合负责人等三组完成后合并登记，跑全量测试，出一张 `out/supper-demo.png` 和 PSD，对照参考图检查。

## 九、验收

1. `python3 -m unittest discover -s tests -t .` 全过。
2. `photocraft-draw check plans/supper-demo.json` 通过。
3. `photocraft-draw draw plans/supper-demo.json --out-dir out` 出图，PSD 顶层至少四组。
4. 肉眼看：没有圆眼卡通脸、没有纯黑描边、没有高饱和色块；人物有坐姿差异，桌子有布褶和器物，窗户和藻井成立。
5. 每个组件附一句参数说明，整合负责人写进 registry。
