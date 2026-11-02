# -*- coding: utf-8 -*-
"""文档簿：把文档层的方法收在一处，方便脚本和后期创作调用。"""
from __future__ import annotations

from pathlib import Path


class DocumentBook:
    """一个已经打开的绘制服务上的文档操作入口。"""

    def __init__(self, engine):
        self.engine = engine

    def new(self, width: int, height: int, name: str = "untitled",
            background: str | None = None) -> dict:
        """新建文档，默认透明，不生成 Background。"""
        self.engine.new_document(width, height, name, background=background)
        return {
            "name": name,
            "width": int(width),
            "height": int(height),
            "background": background or "transparent",
        }

    def open(self, path: str | Path) -> dict:
        """打开已有文档，返回尺寸、层数和警告。"""
        return self.engine.open_document(path)

    def place(self, path: str | Path, x: float | None = None,
              y: float | None = None, scale: float | None = None) -> dict:
        """置入一张图片，作为智能对象图层。"""
        return self.engine.place(path, x=x, y=y, scale=scale)

    def render_to(self, path: str | Path, max_side: int | None = None) -> dict:
        """渲染当前文档并写文件，不把 base64 带出来。"""
        return self.engine.render_to(path, max_side=max_side)

    def save(self, path: str | Path, fmt: str | None = None) -> dict:
        """保存当前文档，格式由扩展名或 fmt 决定。"""
        return self.engine.save(Path(path), fmt)

    def inspect(self, brief: bool = True) -> dict:
        """读尺寸、层数、顶层名称和当前图层。"""
        return self.engine.inspect(brief=brief)

    def execute(self, command: str, params: dict | None = None) -> dict:
        """执行一条绘制指令。"""
        return self.engine.execute(command, params or {})

    def jobs(self) -> list[dict]:
        """列出后台任务。"""
        return self.engine.jobs()

    def cancel(self, job_id) -> dict:
        """取消一个后台任务。"""
        return self.engine.cancel_job(job_id)

    def close(self) -> None:
        """关闭当前文档。"""
        self.engine.close_document()
