# -*- coding: utf-8 -*-
"""命令目录：953 条绘制指令的检索和调用入口。"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

CATALOG_PATH = Path(__file__).with_name("catalog.json")


@lru_cache(maxsize=1)
def load_catalog() -> dict:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _index() -> dict[str, dict]:
    return {item["id"]: item for item in load_catalog()["commands"]}


def categories() -> list[dict]:
    return list(load_catalog()["categories"])


def search(keyword: str | None = None, category: str | None = None, limit: int = 30) -> list[dict]:
    """按关键字和类别找命令。关键字同时匹配编号、名称、菜单和参数说明。"""
    text = (keyword or "").strip().lower()
    group = (category or "").strip().lower()
    found = []
    for item in load_catalog()["commands"]:
        if group and group not in (item["category"].lower(), item["category_name"].lower()):
            continue
        if text:
            haystack = " ".join((
                str(item.get("id", "")), str(item.get("label", "")), str(item.get("menu", "")),
                str(item.get("params", "")), str(item.get("category_name", "")),
                str(item.get("keywords", "")),
            )).lower()
            if text not in haystack:
                continue
        found.append(item)
        if limit and len(found) >= limit:
            break
    return found


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
