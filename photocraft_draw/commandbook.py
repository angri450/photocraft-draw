# -*- coding: utf-8 -*-
"""命令目录：953 条绘制指令的检索和调用入口。

每条命令除了编号、参数，还带会话可用性标注，由 tools/build_catalog.py 生成：

1. session_state 说明这条命令在当前会话里能不能直接跑。取值三种：
   「可执行」空文档下就能跑，「看上下文」要等文档、选区、图层类型满足，
   「会话禁用」serve 模式一律拒绝。session_evidence 标明这条判断的来路：
   「实测-调用」是真的执行过并拿到拒绝，「实测-查询」是 query engine.commands
   得到的空文档基线，「推断」是引擎没起起来时的兜底。「看上下文」的
   session_reason 里带引擎给的原始原因。
2. session_alternative 是命令被禁用时改用的文档层方法，目前有 doc.place、
   doc.open、doc.save 三种；session_alternative_note 说明替代方法缺了哪些
   参数。没有等价方法时是「无」，只能走 photocraft-cli run 一次性模式。
3. path_root 说明路径相对哪个根：读类命令相对读取根，写类命令相对写入根，
   会话禁用的命令相对进程工作目录（仅一次性模式），参数里的 path 指文档内
   路径对象时写明不是磁盘路径。path_params 列出哪几个参数是路径。

会话可用性跟着当前文档状态走，引擎当场返回的 engine.commands 才是最终
依据；目录里记的是新建 800×600 空文档的基线。
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

CATALOG_PATH = Path(__file__).with_name("catalog.json")

# 搜索时一起翻的字段。会话状态和替代方法也要能搜到。
SEARCH_FIELDS = (
    "id", "label", "menu", "params", "category_name", "keywords",
    "session_state", "session_alternative", "path_root", "session_reason",
)


@lru_cache(maxsize=1)
def load_catalog() -> dict:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _index() -> dict[str, dict]:
    return {item["id"]: item for item in load_catalog()["commands"]}


def categories() -> list[dict]:
    return list(load_catalog()["categories"])


def session_baseline() -> dict:
    """目录里的会话基线：什么时候测的、空文档下各类各有多少条。"""
    return dict(load_catalog().get("session_baseline") or {})


def search(keyword: str | None = None, category: str | None = None, limit: int = 30) -> list[dict]:
    """按关键字和类别找命令。关键字同时匹配编号、名称、菜单、参数和会话标注。"""
    text = (keyword or "").strip().lower()
    group = (category or "").strip().lower()
    found = []
    for item in load_catalog()["commands"]:
        if group and group not in (item["category"].lower(), item["category_name"].lower()):
            continue
        if text:
            haystack = " ".join(str(item.get(key, "")) for key in SEARCH_FIELDS).lower()
            if text not in haystack:
                continue
        found.append(item)
        if limit and len(found) >= limit:
            break
    return found


def blocked() -> list[dict]:
    """会话里跑不了的命令，带着替代方法和路径要求。"""
    return [item for item in load_catalog()["commands"] if item.get("session_state") == "会话禁用"]


def describe(command_id: str) -> dict:
    try:
        return _index()[command_id]
    except KeyError as error:
        raise KeyError(f"命令目录里没有 {command_id}，用 commands --search 查") from error


class CommandBook:
    """在已经打开的绘制服务上执行任意一条命令。"""

    def __init__(self, engine):
        self.engine = engine

    def run(self, command_id: str, params: dict | None = None) -> dict:
        describe(command_id)
        return self.engine.execute(command_id, params or {})
