# -*- coding: utf-8 -*-
"""部件分组：把同一个物体的部件归成一组。

组内的部件颜色接近是正常的，不该报冲突。同一个物体由两层信息构成：

    主体 + 实例编号 + 部位词

规则按名字的三个位置来定：

    结尾   独立成词的编号剥掉：「尾 1」->「尾」，「手 1」->「手」
    结尾   紧贴主体的编号剥掉：「手一」->「手」
    结尾   方位部位词剥掉：「山 1 脚」->「山 1」，「鬃毛上 头」->「鬃毛上」
    中间   编号留着，它区分不同实例：「山 1」和「山 2」是两座山

剥完剩下的是主体加实例号，同一个东西的各个部位就落到同一个组。

    「山 1 脚」「山 1 腰」  归成「山 1」
    「山 2 脚」            归成「山 2」
    「鬃毛上」「鬃毛下」    归成「鬃毛」
    「手一」「手二」        归成「手」
    「尾 1」「尾 1 头」     归成「尾 1」

光靠部件名猜归属并不可靠。中文没有词边界，「石影 1」和「石底 1」
是不是同一块石头，名字本身说不清。所以方案里可以给组件显式写 group
字段，直接声明归属。显式声明优先，名字推断只作兜底。

编号不只阿拉伯数字。中文方案里常见「手一」「袖二」这类写法，只剥
阿拉伯数字会让同一件东西的部件散成不同的组，于是同一件袍子的衣身和
袖子被当成相邻部件报出色差问题。

这份规则原先在多个模块各写了一遍，会分叉。
现在集中在这里，两处都从这里取。
"""
from __future__ import annotations

import re

# 复合部位词。两个词合起来才是一个部位，不能一个一个剥。
COMPOUND_PART_WORDS = ("雪尖", "亮边", "左脊", "右脊", "马鬃", "鬃毛")

# 方位部位词。中文部件名常用这些词标出大件上的部分：
# 「鬃毛上」「鬃毛下」「尾 1 头」里的「上」「下」「头」。
# 同一个主体配不同的方位词，是同一个东西的不同部位。
#
# 「腿」「臂」「手」「胸」「腹」「面」不在这里。马腿和马身是马身上的两件
# 东西，不是同一件东西的两个部位，混进方位词会把它们并成一组。
DIRECTION_WORDS = (
    "上", "下", "左", "右", "前", "后", "里", "外",
    "头", "尾", "顶", "底", "侧", "心", "腰", "脚", "背",
)

# 部位词。旧名保留，外部代码可能在用
PART_WORDS = DIRECTION_WORDS

# 编号。阿拉伯数字、汉字数字都算
_NUMERAL = "〇零一二三四五六七八九十百千万两0123456789"
# 复合编号。「字符段 1-21」里的「1-21」是行号和列号，是一个整体，
# 剥掉一半会把同一幅字符画拆成不同的组。
_COMPOSITE_NUM = re.compile(rf"^[0-9{_NUMERAL}]+-[0-9{_NUMERAL}]+$")
# 纯数字的一个词
_NUM_WORD = re.compile(rf"^[0-9{_NUMERAL}]+$")
# 汉字数字紧贴在词尾：「手一」的「一」
_CN_TAIL = re.compile(rf"[0-9{_NUMERAL}]+$")


def _strip_direction_suffix(word: str) -> str:
    """去掉贴在主体词后面的方位后缀。「鬃毛上」的「上」。"""
    for direction in sorted(DIRECTION_WORDS, key=len, reverse=True):
        if len(word) > len(direction) and word.endswith(direction):
            trimmed = word[: -len(direction)].strip()
            if trimmed:
                return trimmed
    return word


def _strip_tail_number(text: str) -> str:
    """剥掉紧贴在末尾的编号。

    「手一」的「一」要剥。用空格隔开的编号不剥，它是实例号：
    「尾 1」和「尾 2」是两条不同的尾巴，「山 1」和「山 2」是两座山。
    """
    tokens = text.split()
    if not tokens:
        return text

    # 只有一个词的时候，编号紧贴在后面：「手一」
    if len(tokens) == 1:
        stripped = _CN_TAIL.sub("", tokens[0])
        if stripped and stripped != tokens[0]:
            return stripped
    return text


def group(name: str, declared: str | None = None) -> str:
    """把部件名归到它所属的那一组。

    declared 是方案里显式写的 group，优先用它。没有显式声明时，
    从名字推断。

    「袖 1」「袖 2」「sleeve 1」归成一组；
    「手一」「手二」「手 1」「手 2」也归成一组；
    「山 1 脚」「山 1 腰」归成「山 1」，「山 2 脚」归成「山 2」；
    「鬃毛上」「鬃毛下」「鬃毛上 头」归成「鬃毛」。
    """
    if declared:
        return str(declared).strip()

    text = str(name).strip()

    # 英文命名：结尾的编号就是实例号，整名去掉编号就是组名
    if re.search(r"[A-Za-z]", text):
        tokens = text.split()
        if len(tokens) > 1 and _NUM_WORD.match(tokens[-1]):
            return " ".join(tokens[:-1])
        if len(tokens) == 1:
            stripped = _CN_TAIL.sub("", tokens[0])
            if stripped and stripped != tokens[0]:
                return stripped
        return text

    # 中文命名。从尾部往回剥，一次剥一段，剥到剥不动为止。
    while True:
        changed = False

        # 复合编号整体留着，它是实例号。「字符段 1-21」的「1-21」是
        # 行号和列号，剥一半就散了。
        tokens = text.split()
        if len(tokens) == 2 and _COMPOSITE_NUM.match(tokens[1]):
            return " ".join(tokens)

        # 剥末尾的复合部位词：「峰 2 雪尖」的「雪尖」
        tokens = text.split()
        if len(tokens) > 1:
            last = tokens[-1]
            for word in COMPOUND_PART_WORDS:
                if last == word:
                    tokens.pop()
                    text = " ".join(tokens)
                    changed = True
                    break
                if last.endswith(word) and len(last) > len(word):
                    trimmed = last[: -len(word)].strip()
                    if trimmed:
                        tokens[-1] = trimmed
                        text = " ".join(tokens)
                        changed = True
                        break
            if changed:
                continue

        # 剥末尾独立成词的方位词：「山 1 脚」的「脚」
        tokens = text.split()
        if len(tokens) > 1 and tokens[-1] in DIRECTION_WORDS:
            text = " ".join(tokens[:-1])
            changed = True
            continue

        # 剥主体后面的方位后缀：「鬃毛上」的「上」
        if len(text.split()) == 1:
            trimmed = _strip_direction_suffix(text)
            if trimmed != text:
                text = trimmed
                changed = True
                continue

        # 剥末尾的编号。中间隔着空格的编号不剥，它区分不同实例。
        stripped = _strip_tail_number(text)
        if stripped != text:
            text = stripped
            changed = True
            continue

        if not changed:
            break

    text = re.sub(r"[\s\-]+", " ", text).strip()
    # 跨组件归组。石头散在两个组件里，前后的石头是同一类东西。
    # 名字推不出更精确的组时用这一类兜底，精确分组优先。
    cross = cross_subject(text)
    if cross and not text:
        return cross
    return text


# 跨组件的同类物件。散在几个组件里的同一类东西，
# 前后的石头都是石头，天空和地面是同一片景。
# 键是主体词，值是这一类物件可能的各种叫法。
CROSS_GROUPS = {
    "石头": ("石头", "石块", "石光", "石影", "石底"),
    "天空": ("天空", "云", "云带"),
    "地面": ("地面", "岩地", "草坡", "坡地"),
    "山": ("山", "峰"),
    "河": ("河", "水", "水面", "水岸线", "浪花", "波浪", "水纹"),
    "路": ("路", "小路"),
    "树": ("树", "树干", "树冠", "枝", "主枝", "短枝"),
    "帷幔": ("帷幔", "帷幔投影", "帷幔顶褶", "帷幔竖褶", "挂杆"),
    "桌面": ("桌面", "桌沿", "桌布", "桌布褶", "桌布前垂"),
    "花": ("花", "瓣", "内瓣", "花心", "花萼"),
    "灯": ("灯", "灯罩", "灯杆", "灯柱", "灯晕"),
    "窗": ("窗", "窗框", "窗棂", "窗光", "窗光晕"),
    "盘": ("盘", "盘沿", "盘面"),
    "杯": ("杯", "杯身", "杯颈", "杯脚", "杯口"),
    "面包": ("面包", "面包割口", "面包影"),
    "帷幔": ("帷幔", "帷幔投影", "帷幔顶褶", "帷幔竖褶", "挂杆", "前垂"),
    "花": ("花", "瓣", "内瓣", "花心", "花萼", "花·"),
    "枝": ("主枝", "短枝", "短枝上", "短枝下", "枝"),
    "楼": ("右三楼", "右二楼", "右一楼", "左三楼", "左二楼", "左一楼"),
    "人物": ("人物", "人物背后亮部", "坐姿人物", "前倾人物", "人物躯干",
             "人物头部", "躯干", "头", "颈", "身体"),
    "树": ("树", "树干", "树冠", "枝", "主枝", "短枝"),
}


def cross_subject(name: str) -> str | None:
    """跨组件归组的主体词。名字对不上就返回空。

    「石块 12」归到「石头」这一类，「山 3」归到「山」这一类。
    """
    text = str(name).strip()
    # 先找最长的匹配，「桌面」比「桌」长
    best = None
    best_length = 0
    for group_name, words in CROSS_GROUPS.items():
        for word in words:
            # 名字以这个词开头，或者名字就是这个词
            if text.startswith(word) and len(word) > best_length:
                best = group_name
                best_length = len(word)
    return best


def cross_group_for(name: str, layer: str | None) -> str | None:
    # 跨组件归组。同类的物件在不同层里时归一组。
    # 石头在 rocky_ground 和 foreground_rocks 两个组件里，
    # 前后的石头是同一类东西，归一组，组内不查色差。
    # 同一层里的不同实例不归一组。山 1 和山 2 挨着的时候，
    # 要能看出边界。
    subject = cross_subject(name)
    if not subject:
        return None
    return f"{layer}:{subject}" if layer else subject


def subject_of(name: str) -> str:
    """取部件名的主体词。

    「树冠 423」的主体词是「树冠」，「果二 12」是「果二」，
    「近灯罩 3」是「近灯罩」。同一个主体词的部件是同一类物件。
    """
    text = str(name).strip()
    if re.search(r"[A-Za-z]", text):
        tokens = text.split()
        if len(tokens) > 1 and _NUM_WORD.match(tokens[-1]):
            return " ".join(tokens[:-1])
        return text

    # 剥掉末尾独立成词的方位部位词
    tokens = text.split()
    while len(tokens) > 1 and tokens[-1] in DIRECTION_WORDS:
        tokens.pop()
    # 剥掉编号。阿拉伯数字是实例号，汉字数字常常是主体的一部分，
    # 「果一」「果二」「果三」是三种不同的果子，不该被剥成一个「果」。
    if len(tokens) > 1 and _NUM_WORD.match(tokens[-1]) and tokens[-1].isdigit():
        tokens = tokens[:-1]
    if len(tokens) == 1:
        stripped = _CN_TAIL.sub("", tokens[0])
        if stripped and stripped != tokens[0] and tokens[0].isdigit():
            tokens = [stripped]
    result = " ".join(tokens)
    # 主体后面的方位后缀：「近灯罩」不去，「鬃毛上」去掉
    if len(tokens) == 1:
        result = _strip_direction_suffix(tokens[0])
    return re.sub(r"[\s\-]+", " ", result).strip()


# 旧名保留下来，外部代码可能还在用
_group = group
