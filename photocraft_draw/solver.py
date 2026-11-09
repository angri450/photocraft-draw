# -*- coding: utf-8 -*-
"""配色求解：在给定的相邻约束下，找一组色值。

colors 只会告诉你哪里颜色太近，不会告诉你该改成什么。这个模块补上
这一段：保留原来的配色，只在撞色的地方把明度挪开，直到所有相邻对的
色差都过线。

约束有两种来源：

    包围盒  部件的矩形相交就算相邻，快，但会把远隔的部件也算进去
    像素    两个部件真的贴在一起才算相邻，准，要先出图

同一个组的部件归在一起，组内不查色差。组里的部件原本颜色不同的时候，
各自的色相都留着，只按组统一挪一个明度偏移，避免把耳内的暗部改成主体色。

相邻的两个组要拉开距离，靠明度差实现。明度每档约 0.06 的色差，
要过 0.12 的阈值就得隔两档，所以真正能用的类别比档数少一半。
先按图着色给每组定类别，再在类别基础上微调。

用法：
    from photocraft_draw.solver import solve
    result = solve(parts, min_gap=0.12)
"""
from __future__ import annotations

from .colorize import _distance, _overlap
from .grouping import group as _group
from .palette import mix, resolve_palette, shade

# 明度档位。相邻部件要拉开距离，但不能拉太远，
# 否则整幅画会失去统一的色调。类别多了再按需扩。
CANDIDATE_STEPS = tuple(range(-4, 5))
# 隔两档才够越过 0.12 的阈值，所以类别按两档一算
CLASS_SPACING = 2
# 明度挪动的上限。一张图里同色系最多拉这么开，再多就散了
MAX_OFFSET = 12


def _group_of(part: dict) -> str:
    return _group(part.get("name"), part.get("group"))


def adjacent_pairs(parts: list[dict]) -> list[tuple[int, int]]:
    """按包围盒找出相邻的部件对。"""
    pairs = []
    for i in range(len(parts)):
        for j in range(i + 1, len(parts)):
            if _group_of(parts[i]) == _group_of(parts[j]):
                continue
            if _overlap(parts[i]["bounds"], parts[j]["bounds"]) <= 0:
                continue
            pairs.append((i, j))
    return pairs


def touching_pairs(commands: list[dict], parts: list[dict]) -> list[tuple[int, int]]:
    """按形状交叠找出相邻的部件对。

    包围盒相交只是粗筛，形状真的碰上了才算挨着。
    """
    from .geometry import adjacent_by_geometry

    index_of = {}
    for position, part in enumerate(parts):
        name = part.get("name")
        if name is not None and name not in index_of:
            index_of[name] = position
    groups = {part.get("name"): _group_of(part) for part in parts}
    pairs = []
    for first, second in adjacent_by_geometry(commands, groups):
        a = index_of.get(first)
        b = index_of.get(second)
        if a is None or b is None:
            continue
        pairs.append((a, b))
    return pairs


def _groups_of(parts: list[dict]):
    """把部件按组归拢，返回 (组名列表, 组内部件下标, 组代表色)。"""
    groups = [_group_of(part) for part in parts]
    order = list(dict.fromkeys(groups))
    index_of = {name: index for index, name in enumerate(order)}
    members = [[] for _ in order]
    for position, group_name in enumerate(groups):
        members[index_of[group_name]].append(position)
    # 组的代表色取组内出现最多的颜色；一样多取第一个
    representative = []
    for indexes in members:
        counts = {}
        for position in indexes:
            color = str(parts[position].get("color") or "mid").lower()
            counts[color] = counts.get(color, 0) + 1
        best_color = None
        best_count = -1
        for position in indexes:
            color = str(parts[position].get("color") or "mid")
            key = color.lower()
            if counts[key] > best_count:
                best_count = counts[key]
                best_color = color
        representative.append(best_color)
    return order, members, representative


def _greedy_classes(group_pairs, count: int) -> dict[int, int]:
    """按图着色给每组定类别，相邻的组类别不同。

    度数高的组先定，它们最难安排。类别数不预设上限，
    邻接太密的图会需要更多类别，类别多了明度偏移按比例放大。
    """
    neighbours = {index: set() for index in range(count)}
    for a, b in group_pairs:
        neighbours[a].add(b)
        neighbours[b].add(a)

    classes: dict[int, int] = {}
    order = sorted(range(count), key=lambda i: -len(neighbours[i]))
    for index in order:
        taken = {classes[other] for other in neighbours[index] if other in classes}
        chosen = 0
        while chosen in taken:
            chosen += 1
        classes[index] = chosen
    return classes


def _offset_for(class_number: int, class_count: int) -> int:
    """类别换算成明度偏移。

    类别相邻要差两档才够越过阈值，所以偏移按类别号乘两档。
    类别太多的时候整体压回来，别把一幅画拉散。
    """
    if class_count <= 1:
        return 0
    span = min(class_count - 1, MAX_OFFSET // CLASS_SPACING)
    if span <= 0:
        return 0
    ratio = class_number / span
    # 类别从中间往两边散，明度偏移才有正有负
    centered = (ratio - 0.5) * 2
    offset = int(round(centered * MAX_OFFSET / 2))
    return max(-MAX_OFFSET, min(MAX_OFFSET, offset))


def solve(parts: list[dict], min_gap: float = 0.12,
          pairs: list[tuple[int, int]] | None = None) -> dict:
    """找一组能过线的配色。

    返回 {"ok": 是否全部过线, "colors": [{name, hex, original, changed}],
    "worst": 最小色差, "min_gap": 要求, "tightest": 分不开的几对}
    """
    if pairs is None:
        pairs = adjacent_pairs(parts)

    order, members, representative = _groups_of(parts)
    groups = [_group_of(part) for part in parts]
    index_of = {name: index for index, name in enumerate(order)}

    # 组越大，改动代价越高
    group_weight = {}
    for index, indexes in enumerate(members):
        area = 0.0
        for position in indexes:
            bounds = parts[position].get("bounds") or [0, 0, 0, 0]
            area += float(bounds[2]) * float(bounds[3])
        group_weight[index] = 1.0 + min(3.0, area / max(len(parts) * 40000.0, 1.0))

    # 组级邻接
    group_pairs = []
    seen = set()
    for i, j in pairs:
        a = index_of[groups[i]]
        b = index_of[groups[j]]
        if a == b or (b, a) in seen:
            continue
        seen.add((a, b))
        group_pairs.append((a, b))

    # 每个组相邻的组，用来只重算受影响的边
    neighbours_of = {index: set() for index in range(len(order))}
    for a, b in group_pairs:
        neighbours_of[a].add(b)
        neighbours_of[b].add(a)

    def gap_between(a: int, b: int, assignment: dict) -> float:
        return _distance(assignment[a], assignment[b])

    def evaluate(assignment: dict) -> float:
        """所有相邻组里最小的色差。"""
        worst = 1.0
        for a, b in group_pairs:
            gap = gap_between(a, b, assignment)
            if gap < worst:
                worst = gap
        return worst

    def worst_around(index: int, assignment: dict, skip: int | None = None) -> float:
        """某个组相关的边里最小的色差。

        改动一个组只会影响它和邻居之间的边，别的边不用重算。
        """
        worst = 1.0
        for other in neighbours_of[index]:
            if other == skip:
                continue
            gap = gap_between(index, other, assignment)
            if gap < worst:
                worst = gap
        return worst

    def deviation(assignment: dict) -> float:
        """改动幅度。所有组离原色越远，总代价越高。

        求解的目标是在满足色差的前提下少改。色相和明度都算，
        明度挪一档代价小，色相跑掉代价大。

        面积大的部件代价更高。脸和手撞色的时候，改脸不如改手，
        脸是画面的主角，动了就毁了整幅画。
        """
        total = 0.0
        for index, original in enumerate(representative):
            weight = group_weight.get(index, 1.0)
            total += _deviation(original, assignment[index]) * weight
        return total

    def tightest(assignment: dict, count: int = 6):
        """列出最紧的几对，方便看是哪些地方分不开。"""
        scored = []
        for a, b in group_pairs:
            scored.append((_distance(assignment[a], assignment[b]), order[a], order[b]))
        scored.sort()
        return scored[:count]

    # 起点：保持原色
    best = dict(enumerate(representative))
    best_score = evaluate(best)
    if best_score >= min_gap:
        result = _result(parts, groups, order, index_of, best, best_score,
                         min_gap, representative)
        result["tightest"] = []
        return result

    def candidates_for(index: int) -> list[str]:
        """一个组可以取的颜色。

        两种改法：挪明度，色相不动；朝邻居色混，色相跟着走但保留一部分。
        混色能把暖色往冷色拉，色相偏移比整体换色小。
        """
        base = representative[index]
        options = [base]
        for step in range(-MAX_OFFSET, MAX_OFFSET + 1):
            if step:
                options.append(shade(base, step))
        for other, _ in group_pairs:
            if other == index:
                continue
            neighbour = representative[other]
            for ratio in (0.25, 0.4, 0.55):
                options.append(mix(base, neighbour, ratio))
        # 去重，保留原顺序
        seen = set()
        unique = []
        for option in options:
            key = option.lower()
            if key not in seen:
                seen.add(key)
                unique.append(option)
        return unique

    def better(first_score: float, first_cost: float,
               second_score: float, second_cost: float) -> bool:
        """先看色差够不够，再看改动小不小。"""
        if second_score > first_score + 1e-9:
            return True
        if abs(second_score - first_score) <= 1e-9 and second_cost < first_cost - 1e-9:
            return True
        return False

    best_cost = deviation(best)

    # 先按图着色定类别。逐组微调在环状约束上容易卡住，
    # 先把相邻的组分开，再微调就能跳出来。
    classes = _greedy_classes(group_pairs, len(order))
    class_count = len(set(classes.values()))
    seeded = {}
    for index, color in enumerate(representative):
        step = _offset_for(classes.get(index, 0), class_count)
        seeded[index] = shade(color, step) if step else color
    seeded_score = evaluate(seeded)
    seeded_cost = deviation(seeded)
    if better(best_score, best_cost, seeded_score, seeded_cost):
        best = seeded
        best_score = seeded_score
        best_cost = seeded_cost

    # 在类别基础上逐组微调
    # 改动一个组只影响它和邻居之间的边。只重算这些边，
    # 大样例上比全量重算快一个数量级。
    def local_score(group_index, candidate, current, current_score):
        # 换掉这个组之后，和它相关的边里最小的色差
        worst = current_score
        for other in neighbours_of[group_index]:
            gap = _distance(candidate, current[other])
            if gap < worst:
                worst = gap
        # 别的边不变，但当前全局最小值可能出在这个组上，
        # 所以还要看除这个组以外的那些边的最小值
        for a, b in group_pairs:
            if a == group_index or b == group_index:
                continue
            if _distance(current[a], current[b]) < worst:
                worst = _distance(current[a], current[b])
        return worst

    def local_cost(group_index, candidate, current, current_cost):
        weight = group_weight.get(group_index, 1.0)
        old = _deviation(representative[group_index], current[group_index])
        new = _deviation(representative[group_index], candidate)
        return current_cost - old * weight + new * weight

    for _ in range(80):
        improved = False
        for group in range(len(order)):
            for candidate in candidates_for(group):
                score = local_score(group, candidate, best, best_score)
                cost = local_cost(group, candidate, best, best_cost)
                if better(best_score, best_cost, score, cost):
                    best[group] = candidate
                    best_score = score
                    best_cost = cost
                    improved = True
        if not improved:
            break

    # 随机重启爬山。稠密的相邻图上逐组贪心容易卡住，
    # 换几个起点重来，跳出局部最优。
    import random

    rng = random.Random(20261109)
    for attempt in range(12):
        if best_score >= min_gap and best_cost <= 0.0:
            break
        current = dict(best)
        for group in rng.sample(range(len(order)), min(len(order), 8)):
            options = candidates_for(group)
            current[group] = options[rng.randrange(len(options))]
        current_score = evaluate(current)
        current_cost = deviation(current)
        for _ in range(80):
            improved = False
            for group in range(len(order)):
                for candidate in candidates_for(group):
                    trial = dict(current)
                    trial[group] = candidate
                    score = evaluate(trial)
                    cost = deviation(trial)
                    if better(current_score, current_cost, score, cost):
                        current = trial
                        current_score = score
                        current_cost = cost
                        improved = True
            if not improved:
                break
        if better(best_score, best_cost, current_score, current_cost):
            best = current
            best_score = current_score
            best_cost = current_cost

    result = _result(parts, groups, order, index_of, best, best_score,
                     min_gap, representative)
    result["cost"] = round(best_cost, 3)
    result["tightest"] = [
        {"a": name_a, "b": name_b, "gap": round(gap, 3)}
        for gap, name_a, name_b in tightest(best)
    ]
    return result


def _result(parts, groups, order, index_of, assignment, score, min_gap,
             representative) -> dict:
    colors = []
    for position, part in enumerate(parts):
        group = index_of[groups[position]]
        base = representative[group]
        final = assignment[group]
        original = str(part.get("color") or "mid")
        if final.lower() != original.lower():
            # 组里的部件色相不同。整组挪多少档，各自也跟着挪多少档，
            # 耳内的暗部还是暗部，不会被改成主体色。
            final = shade(original, _step_between(base, final))
        colors.append({
            "name": part.get("name"),
            "group": groups[position],
            "hex": final,
            "original": original,
            "changed": final.lower() != original.lower(),
        })
    return {
        "ok": score >= min_gap,
        "parts": len(parts),
        "colors": colors,
        "worst": round(score, 3),
        "min_gap": min_gap,
    }


def _step_between(base: str, target: str) -> int:
    """目标色比基准色亮了多少档。"""
    if base == target:
        return 0
    for step in range(-MAX_OFFSET, MAX_OFFSET + 1):
        if shade(base, step).lower() == target.lower():
            return step
    return 0


def _deviation(original: str, changed: str) -> float:
    """改动代价。色差的一半算明度代价，色相偏移另算。

    纯明度挪动代价低，色相跑掉代价高。求解时先保色相。
    """
    if original.lower() == changed.lower():
        return 0.0
    import colorsys

    def hsl(text):
        raw = str(text).lstrip("#")
        if len(raw) != 6:
            return 0.0, 0.5, 0.0
        rgb = tuple(int(raw[i:i + 2], 16) / 255 for i in (0, 2, 4))
        return colorsys.rgb_to_hls(*rgb)

    h1, l1, s1 = hsl(original)
    h2, l2, s2 = hsl(changed)
    lightness = abs(l2 - l1)
    hue = 0.0
    if s1 > 0.05 and s2 > 0.05:
        delta = abs(h1 - h2)
        hue = min(delta, 1.0 - delta) * 2.0
    return lightness * 1.0 + hue * 3.0


def solve_local(parts: list[dict], min_gap: float = 0.12,
                pairs: list[tuple[int, int]] | None = None) -> dict:
    """只修真正冲突的组对，别的部件保持原样。

    全局优化会把整幅画都调一遍，只为了让某一处过关。改色应该只动
    真正撞色的地方。

    逐对处理冲突。每对里挑改动代价小的那个挪开，挪到过线为止。
    已经挪过的组不再动，免得连锁反应。
    """
    if pairs is None:
        pairs = adjacent_pairs(parts)

    order, members, representative = _groups_of(parts)
    groups = [_group_of(part) for part in parts]
    index_of = {name: index for index, name in enumerate(order)}

    def hex_of(part):
        color = part.get("color") or "mid"
        if str(color).startswith("#"):
            return color
        return resolve_palette(None).get(color, color)

    def group_color(group_index):
        for position, part in enumerate(parts):
            if index_of[groups[position]] == group_index:
                return hex_of(part)
        return "#888888"

    # 组级邻接，只保留真正撞色的
    conflicts = []
    seen = set()
    for i, j in pairs:
        a = index_of[groups[i]]
        b = index_of[groups[j]]
        if a == b or (b, a) in seen:
            continue
        seen.add((a, b))
        gap = _distance(group_color(a), group_color(b))
        if gap < min_gap:
            conflicts.append((a, b))

    current = {index: group_color(index) for index in range(len(order))}
    touched = set()

    # 只在互相牵制的冲突组之间做图着色。
    # 一个组同时和多个组冲突时，挨个挪会来回撞，先定档位再落地。
    conflict_groups = sorted({index for pair in conflicts for index in pair})
    neighbours = {index: set() for index in conflict_groups}
    for a, b in conflicts:
        neighbours[a].add(b)
        neighbours[b].add(a)

    # 相邻的冲突组不能同档
    classes = {}
    for index in sorted(conflict_groups, key=lambda i: -len(neighbours[i])):
        taken = {classes[other] for other in neighbours[index] if other in classes}
        chosen = 0
        while chosen in taken:
            chosen += 1
        classes[index] = chosen

    # 档位换算成明度偏移。类别从中间往两边散，
    # 但每个组先试离原色最近的那一档，够用就行，不多挪。
    class_count = max(len(classes), 1)
    for index, class_number in classes.items():
        base = representative[index]
        span = max(class_count - 1, 1)
        ratio = class_number / span
        centered = (ratio - 0.5) * 2
        wanted = int(round(centered * MAX_OFFSET / 2))
        # 档位之间隔两格，色差才够 0.12
        wanted = wanted // CLASS_SPACING * CLASS_SPACING
        current[index] = shade(base, wanted) if wanted else base
        touched.add(index)

    # 迭代求解。一轮定不下来：后面的组会撞上前面定好的。
    # 反复把没过线的组往远处挪，直到全都过线或者挪到头。
    for _ in range(MAX_OFFSET):
        broken = False
        for index in sorted(conflict_groups, key=lambda i: -len(neighbours[i])):
            base = representative[index]
            for other in neighbours[index]:
                if _distance(current[index], current[other]) >= min_gap:
                    continue
                broken = True
                # 每轮回到原色重新挑。按代价从小到大排，
                # 代价一样挑明度偏离小的，避免掉进接近纯黑的地方。
                options = []
                for step in range(0, MAX_OFFSET + 1):
                    for sign in (1, -1):
                        if step == 0 and sign == -1:
                            continue
                        candidate = shade(base, sign * step) if step else base
                        # 跟所有邻居都要过线，不只当前这一个
                        if all(_distance(candidate, current[other_index]) >= min_gap
                               for other_index in neighbours[index]):
                            options.append((round(_deviation(base, candidate), 6),
                                            abs(step), candidate))
                if options:
                    options.sort()
                    current[index] = options[0][2]
                    touched.add(index)
                break
        if not broken:
            break

    # 复核
    worst = 1.0
    remaining = []
    for i, j in pairs:
        a = index_of[groups[i]]
        b = index_of[groups[j]]
        if a == b:
            continue
        gap = _distance(current[a], current[b])
        if gap < worst:
            worst = gap
        if gap < min_gap:
            remaining.append((order[a], order[b], round(gap, 3)))

    colors = []
    for position, part in enumerate(parts):
        group_index = index_of[groups[position]]
        original = hex_of(part)
        final = current[group_index]
        if group_index in touched and final.lower() != original.lower():
            # 组里色相不同的，各自跟着挪，别把耳内的暗部改成主体色
            final = shade(original, _step_between(representative[group_index], final))
        colors.append({
            "name": part.get("name"),
            "group": groups[position],
            "hex": final,
            "original": original,
            "changed": final.lower() != original.lower(),
        })

    return {
        "ok": worst >= min_gap,
        "parts": len(parts),
        "colors": colors,
        "worst": round(worst, 3),
        "min_gap": min_gap,
        "tightest": [{"a": a, "b": b, "gap": g} for a, b, g in remaining[:8]],
    }


def report(result: dict) -> str:
    status = "找到可行配色" if result["ok"] else "仍有冲突"
    lines = [f"{status} | 最小色差 {result['worst']:.3f}，要求 {result['min_gap']:.3f}"]
    changed = [item for item in result["colors"] if item["changed"]]
    if changed:
        lines.append(f"要改 {len(changed)} 个部件：")
        for item in changed:
            lines.append(f"  {item['name']}：{item['original']} -> {item['hex']}")
    elif result["ok"]:
        lines.append("原来的配色已经够用，不用改")
    else:
        lines.append("改不动。相邻关系太密，靠明度分不开。")
        tightest = result.get("tightest") or []
        if tightest:
            lines.append("分不开的几对：")
            for item in tightest:
                lines.append(f"  {item['a']} 和 {item['b']}：{item['gap']:.3f}")
        lines.append("先看是不是判定得太宽：跑 colors --pixel 按真实像素接触重查。")
    return "\n".join(lines)
