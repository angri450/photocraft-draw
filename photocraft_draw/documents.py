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
        """置入一张图片，作为智能对象图层。

        serve 会话里的 doc.place 只按画布中心落图，x、y 会被忽略；
        要精确摆放，用 run_once 走一次性模式，调 file.placeEmbedded 的
        center、scale、fit、smartObject。
        """
        return self.engine.place(path, x=x, y=y, scale=scale)

    def run_once(self, commands, out: str | Path, *, source: str | Path | None = None,
                 new: dict | None = None, fmt: str | None = None,
                 timeout: float = 600.0) -> dict:
        """不经过当前会话，另起一个一次性进程执行命令并保存。

        file.placeEmbedded 这类被 serve 拦下的路径命令走这条路。
        """
        return self.engine.run_once(
            commands, out, source=source, new=new, fmt=fmt, timeout=timeout,
        )

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
