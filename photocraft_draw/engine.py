# -*- coding: utf-8 -*-
"""绘制服务：管理 photocraft-cli 的 serve 会话，只回执行摘要。"""
from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
import threading
import time
from pathlib import Path

TOKEN_RE = re.compile(r"control token:\s*([0-9a-fA-F]{64})")
SERVING_RE = re.compile(r"serving on\s+\[?([0-9a-fA-F:.]+?)\]?:(\d+)", re.I)
SUMMARY_KEYS = ("layer", "bounds", "name", "kind", "files", "count", "warnings")


class EngineError(RuntimeError):
    """绘制服务不可用或命令执行失败。"""


def find_engine() -> Path:
    """按环境变量、PATH、~/opt 的顺序找 photocraft-cli。"""
    candidates: list[Path] = []
    raw = os.environ.get("PHOTOCRAFT_CLI", "").strip()
    if raw:
        path = Path(raw).expanduser()
        candidates.append(path if path.is_file() else path / "photocraft-cli")
    found = shutil.which("photocraft-cli")
    if found:
        candidates.append(Path(found))
    root = Path.home() / "opt" / "photocraft"
    if root.is_dir():
        for child in sorted(root.iterdir(), reverse=True):
            candidates.append(child / "bin" / "photocraft-cli")
    for path in candidates:
        if path.is_file():
            return path
    raise EngineError(
        "找不到 photocraft-cli。设置环境变量 PHOTOCRAFT_CLI 指向可执行文件，"
        "或把它放到 PATH，或解压到 ~/opt/photocraft/<版本>/bin/。"
    )


def engine_version(path: Path | None = None) -> str:
    """读引擎版本号，读不到就返回空字符串。"""
    exe = path or find_engine()
    try:
        result = subprocess.run(
            [str(exe), "--version"], capture_output=True, text=True, timeout=15
        )
        return (result.stdout or result.stderr).strip()
    except Exception:
        return ""


def summarize(value):
    """把引擎的大回执压成几个关键字段。"""
    if value is None:
        return None
    if not isinstance(value, (dict, list)):
        return value
    if isinstance(value, list):
        return {"count": len(value), "bytes": len(json.dumps(value, ensure_ascii=False))}
    summary = {key: value[key] for key in SUMMARY_KEYS if key in value}
    if not summary:
        summary["keys"] = list(value)[:8]
    summary["bytes"] = len(json.dumps(value, ensure_ascii=False))
    return summary


class Engine:
    """一个常驻的绘制服务，同一份文档可以连续执行多条绘制指令。"""

    def __init__(self, cli: Path | str | None = None, read_root: Path | str | None = None,
                 write_root: Path | str | None = None, startup_timeout: float = 30.0):
        self.cli = Path(cli) if cli else find_engine()
        self.read_root = Path(read_root).resolve() if read_root else None
        self.write_root = Path(write_root).resolve() if write_root else None
        self.startup_timeout = float(startup_timeout)
        self._proc: subprocess.Popen | None = None
        self._sock: socket.socket | None = None
        self._reader = None
        self._id = 0
        self._ready = threading.Event()
        self._token: str | None = None
        self._host: str | None = None
        self._port: int | None = None
        self._stderr: list[str] = []

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.stop()

    @property
    def tail(self) -> str:
        return " | ".join(self._stderr[-3:])

    def start(self) -> None:
        if self._sock:
            return
        args = [str(self.cli), "serve", "--port", "0"]
        if self.read_root:
            args += ["--automation-read-root", str(self.read_root)]
        if self.write_root:
            args += ["--automation-write-root", str(self.write_root)]
        self._proc = subprocess.Popen(
            args, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            text=True, bufsize=1,
        )
        threading.Thread(target=self._drain, args=(self._proc,), daemon=True).start()
        if not self._ready.wait(self.startup_timeout):
            tail = self.tail
            self.stop()
            raise EngineError(f"绘制服务启动超时（{self.startup_timeout:.0f} 秒）" + (f"：{tail}" if tail else ""))
        if self._proc.poll() is not None:
            tail = self.tail
            raise EngineError(f"绘制服务启动失败，退出码 {self._proc.returncode}" + (f"：{tail}" if tail else ""))
        self._sock = socket.create_connection((self._host, self._port), timeout=10)
        self._reader = self._sock.makefile("rb")
        auth = self.call("auth", {"token": self._token}, timeout=10)
        if not auth.get("ok"):
            raise EngineError(f"绘制服务认证失败：{auth.get('error')}")

    def _drain(self, proc: subprocess.Popen) -> None:
        for line in proc.stderr or []:
            text = line.rstrip("\n")
            self._stderr.append(text)
            if len(self._stderr) > 200:
                del self._stderr[:100]
            match = TOKEN_RE.search(text)
            if match:
                self._token = match.group(1)
            match = SERVING_RE.search(text)
            if match:
                self._host = match.group(1)
                self._port = int(match.group(2))
            if self._token and self._port:
                self._ready.set()

    def call(self, method: str, params: dict | None = None, timeout: float = 120.0) -> dict:
        if not self._sock or not self._reader:
            raise EngineError("绘制服务没有启动")
        self._id += 1
        request_id = self._id
        payload = json.dumps(
            {"id": request_id, "method": method, "params": params or {}}, ensure_ascii=False
        ) + "\n"
        self._sock.sendall(payload.encode("utf-8"))
        deadline = time.time() + timeout
        while time.time() < deadline:
            self._sock.settimeout(max(0.1, deadline - time.time()))
            line = self._reader.readline()
            if not line:
                raise EngineError(f"{method} 调用中断，绘制服务已断开" + (f"：{self.tail}" if self.tail else ""))
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            if message.get("id") == request_id:
                return message
        raise EngineError(f"{method} 调用超时（{timeout:.0f} 秒）")

    def new_document(self, width: int, height: int, name: str = "untitled",
                     background: str | None = None) -> None:
        params = {"width": int(width), "height": int(height), "name": str(name)}
        if background:
            params["background"] = str(background)
        message = self.call("doc.new", params)
        if not message.get("ok"):
            raise EngineError(f"新建画布失败：{message.get('error')}")

    def execute(self, command: str, params: dict) -> dict:
        message = self.call("engine.execute", {"command": command, "params": params or {}})
        if not message.get("ok"):
            raise EngineError(f"绘制指令 {command} 失败：{message.get('error')}")
        return summarize(message.get("result"))

    def save(self, path: Path, fmt: str | None = None) -> dict:
        message = self.call("doc.save", {"path": str(path), "format": fmt or path.suffix.lstrip(".")})
        if not message.get("ok"):
            raise EngineError(f"保存 {path} 失败：{message.get('error')}")
        return message.get("result") or {}

    def close_document(self) -> None:
        try:
            self.call("doc.close", {}, timeout=5)
        except Exception:
            pass

    def stop(self) -> None:
        try:
            self.close_document()
        except Exception:
            pass
        try:
            if self._reader:
                self._reader.close()
        except Exception:
            pass
        try:
            if self._sock:
                self._sock.close()
        except Exception:
            pass
        self._sock = None
        self._reader = None
        proc, self._proc = self._proc, None
        if proc:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()
            try:
                if proc.stderr:
                    proc.stderr.close()
            except Exception:
                pass
