# -*- coding: utf-8 -*-
"""图层批注页：把渲染图和图层树打成一个单文件网页，导出修改意见 JSON。"""
from __future__ import annotations

import base64
import json
import socket
import subprocess
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .engine import find_engine

TEMPLATE = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<style>
* { box-sizing: border-box; }
body { margin: 0; font: 14px/1.5 -apple-system, "Segoe UI", "Noto Sans CJK SC", sans-serif; color: #1f2933; background: #e9edf2; }
#app { display: flex; height: 100vh; overflow: hidden; }
aside { width: 320px; flex: 0 0 320px; background: #141a21; color: #e6edf3; display: flex; flex-direction: column; overflow: hidden; }
aside header { padding: 16px 16px 8px; }
aside h1 { margin: 0 0 4px; font-size: 16px; }
aside .hint { margin: 0; color: #8b98a5; font-size: 12px; }
aside .search { margin: 8px 16px; padding: 7px 9px; border-radius: 6px; border: 1px solid #2b3540; background: #0d1117; color: #e6edf3; }
#list { flex: 1; overflow: auto; padding: 4px 8px 12px; }
.row { padding: 4px 8px; border-radius: 5px; cursor: pointer; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: #c9d4df; }
.row:hover { background: #1f2933; }
.row.active { background: #2f5d8a; color: #fff; }
.row .kind { color: #7d8b99; font-size: 11px; margin-left: 6px; }
#editor { border-top: 1px solid #2b3540; padding: 12px 16px; background: #10161d; }
#editor h2 { margin: 0 0 8px; font-size: 13px; color: #9fb0c0; font-weight: 600; }
#editor label { display: block; margin: 8px 0 4px; color: #8b98a5; font-size: 12px; }
#editor select, #editor input, #editor textarea, .global textarea { width: 100%; border: 1px solid #2b3540; background: #0d1117; color: #e6edf3; border-radius: 5px; padding: 6px; font: inherit; }
#editor textarea { min-height: 56px; resize: vertical; }
.row2 { display: flex; gap: 8px; }
.row2 > div { flex: 1; }
.global { padding: 10px 16px; border-top: 1px solid #2b3540; }
.global label { color: #8b98a5; font-size: 12px; display: block; margin-bottom: 4px; }
.buttons { display: flex; gap: 8px; padding: 12px 16px 16px; }
button, .import { flex: 1; border: 1px solid #2b3540; background: #1f2933; color: #e6edf3; border-radius: 6px; padding: 8px; cursor: pointer; text-align: center; font: inherit; }
button.primary { background: #2f6f8f; border-color: #2f6f8f; }
button:hover, .import:hover { filter: brightness(1.15); }
.import input { display: none; }
main { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
#toolbar { height: 44px; display: flex; align-items: center; gap: 10px; padding: 0 14px; background: #fff; border-bottom: 1px solid #d8e0e8; }
#toolbar button { flex: 0 0 32px; padding: 4px; }
#zoomLabel { color: #52606d; width: 46px; text-align: center; }
#stage { flex: 1; overflow: auto; padding: 24px; }
#wrap { position: relative; display: inline-block; background: #fff; box-shadow: 0 2px 16px rgba(15,23,42,.12); }
#img { display: block; }
#box { position: absolute; border: 2px solid #e07a5f; background: rgba(224,122,95,.12); display: none; cursor: move; }
#box::after { content: "拖动"; position: absolute; top: -20px; left: 0; font-size: 11px; color: #fff; background: #e07a5f; padding: 1px 5px; border-radius: 3px; }
</style>
</head>
<body>
<div id="app">
  <aside>
    <header>
      <h1>图层批注</h1>
      <p class="hint">点图层看范围，拖方框记位移，改完导出 JSON。</p>
    </header>
    <input id="search" class="search" placeholder="搜图层名">
    <div id="list"></div>
    <div id="editor">
      <h2 id="selName">未选图层</h2>
      <label>动作</label>
      <select id="action">
        <option value="move">移动</option>
        <option value="hide">隐藏</option>
        <option value="show">显示</option>
        <option value="delete">删除</option>
        <option value="recolor">改色</option>
        <option value="retext">改字</option>
        <option value="note">只写意见</option>
      </select>
      <div class="row2">
        <div><label>横向位移</label><input id="dx" type="number" value="0"></div>
        <div><label>纵向位移</label><input id="dy" type="number" value="0"></div>
      </div>
      <label>备注</label>
      <textarea id="note" placeholder="这个图层要怎么改"></textarea>
    </div>
    <div class="global">
      <label>整体意见</label>
      <textarea id="globalNote" placeholder="整张图的意见"></textarea>
    </div>
    <div class="buttons">
      <button id="export" class="primary">导出意见</button>
      <button id="copy">复制 JSON</button>
    </div>
    <div class="buttons">
      <label class="import">导入意见<input id="import" type="file" accept=".json"></label>
      <button id="clear">清空</button>
    </div>
  </aside>
  <main>
    <div id="toolbar">
      <button id="zoomOut">−</button><span id="zoomLabel">100%</span><button id="zoomIn">+</button>
      <span id="meta" style="color:#52606d"></span>
    </div>
    <div id="stage"><div id="wrap"><img id="img" alt="画面"><div id="box"></div></div></div>
  </main>
</div>
<script>
const LAYERS = __LAYERS__;
const IMAGE_SRC = "__IMAGE_SRC__";
const PLAN_NAME = __PLAN_NAME__;
const IMAGE_NAME = __IMAGE_NAME__;
const CANVAS = __CANVAS__;
const list = document.getElementById('list');
const search = document.getElementById('search');
const img = document.getElementById('img');
const box = document.getElementById('box');
const selName = document.getElementById('selName');
const action = document.getElementById('action');
const dxInput = document.getElementById('dx');
const dyInput = document.getElementById('dy');
const noteInput = document.getElementById('note');
const globalNote = document.getElementById('globalNote');
const zoomLabel = document.getElementById('zoomLabel');
const meta = document.getElementById('meta');
const edits = new Map();
let selected = null;
let zoom = 1;
let natW = CANVAS[0], natH = CANVAS[1];

meta.textContent = CANVAS[0] + '×' + CANVAS[1] + ' · ' + LAYERS.length + ' 个图层';

function editOf(layer) {
  let item = edits.get(layer.id);
  if (!item) {
    item = { layer: layer.id, name: layer.name, kind: layer.kind, action: 'move', dx: 0, dy: 0, note: '' };
    edits.set(layer.id, item);
  }
  return item;
}

function renderList() {
  const query = search.value.trim().toLowerCase();
  list.innerHTML = '';
  LAYERS.forEach(layer => {
    if (query && !layer.name.toLowerCase().includes(query)) return;
    const row = document.createElement('div');
    row.className = 'row' + (selected && selected.id === layer.id ? ' active' : '');
    row.style.paddingLeft = (8 + layer.depth * 14) + 'px';
    row.textContent = layer.name;
    const kind = document.createElement('span');
    kind.className = 'kind';
    kind.textContent = layer.kind;
    row.appendChild(kind);
    row.title = layer.name + ' · ' + layer.kind;
    row.onclick = () => selectLayer(layer);
    list.appendChild(row);
  });
}

function selectLayer(layer) {
  selected = layer;
  selName.textContent = layer.name;
  const item = editOf(layer);
  action.value = item.action;
  dxInput.value = item.dx;
  dyInput.value = item.dy;
  noteInput.value = item.note;
  placeBox();
  renderList();
}

function placeBox() {
  if (!selected || !selected.bounds) { box.style.display = 'none'; return; }
  const item = edits.get(selected.id) || { dx: 0, dy: 0 };
  const [x, y, w, h] = selected.bounds;
  box.style.display = 'block';
  box.style.left = ((x + (item.dx || 0)) * zoom) + 'px';
  box.style.top = ((y + (item.dy || 0)) * zoom) + 'px';
  box.style.width = Math.max(2, w * zoom) + 'px';
  box.style.height = Math.max(2, h * zoom) + 'px';
}

function applyZoom() {
  img.style.width = (natW * zoom) + 'px';
  zoomLabel.textContent = Math.round(zoom * 100) + '%';
  placeBox();
}

function syncEdit() {
  if (!selected) return;
  const item = editOf(selected);
  item.action = action.value;
  item.dx = Number(dxInput.value) || 0;
  item.dy = Number(dyInput.value) || 0;
  item.note = noteInput.value;
  placeBox();
}

action.onchange = syncEdit;
dxInput.oninput = syncEdit;
dyInput.oninput = syncEdit;
noteInput.oninput = syncEdit;
search.oninput = renderList;

document.getElementById('zoomIn').onclick = () => { zoom = Math.min(3, zoom + 0.1); applyZoom(); };
document.getElementById('zoomOut').onclick = () => { zoom = Math.max(0.2, zoom - 0.1); applyZoom(); };

let drag = null;
box.addEventListener('mousedown', event => {
  if (!selected || !selected.bounds) return;
  event.preventDefault();
  const item = editOf(selected);
  item.action = 'move';
  action.value = 'move';
  drag = { x: event.clientX, y: event.clientY, dx: item.dx || 0, dy: item.dy || 0 };
});
window.addEventListener('mousemove', event => {
  if (!drag || !selected) return;
  const item = editOf(selected);
  item.dx = Math.round(drag.dx + (event.clientX - drag.x) / zoom);
  item.dy = Math.round(drag.dy + (event.clientY - drag.y) / zoom);
  dxInput.value = item.dx;
  dyInput.value = item.dy;
  placeBox();
});
window.addEventListener('mouseup', () => { drag = null; });

function payload() {
  return {
    plan: PLAN_NAME,
    image: IMAGE_NAME,
    canvas: CANVAS,
    edits: Array.from(edits.values()).filter(item => item.action !== 'move' || item.dx || item.dy || item.note),
    global: globalNote.value
  };
}

function download() {
  const data = JSON.stringify(payload(), null, 2);
  const blob = new Blob([data], { type: 'application/json' });
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = PLAN_NAME + '.review.json';
  link.click();
  URL.revokeObjectURL(link.href);
}

document.getElementById('export').onclick = download;
document.getElementById('copy').onclick = async () => {
  await navigator.clipboard.writeText(JSON.stringify(payload(), null, 2));
  document.getElementById('copy').textContent = '已复制';
  setTimeout(() => { document.getElementById('copy').textContent = '复制 JSON'; }, 1200);
};

document.getElementById('clear').onclick = () => {
  if (!confirm('清空所有修改意见？')) return;
  edits.clear();
  globalNote.value = '';
  if (selected) selectLayer(selected);
  renderList();
};

document.getElementById('import').onchange = event => {
  const file = event.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    try {
      const data = JSON.parse(reader.result);
      edits.clear();
      (data.edits || []).forEach(item => edits.set(item.layer, item));
      globalNote.value = data.global || '';
      if (selected) selectLayer(selected);
      renderList();
    } catch (error) { alert('JSON 解析失败：' + error.message); }
  };
  reader.readAsText(file);
};

img.onload = () => {
  natW = img.naturalWidth || CANVAS[0];
  natH = img.naturalHeight || CANVAS[1];
  applyZoom();
};
img.src = IMAGE_SRC;
renderList();
</script>
</body>
</html>
"""


def read_layers(psd_path: Path) -> tuple[int, int, list[dict]]:
    cli = find_engine()
    result = subprocess.run(
        [str(cli), "info", str(psd_path)], capture_output=True, text=True, check=True
    )
    data = json.loads(result.stdout)
    rows: list[dict] = []

    def bounds_of(node: dict):
        bounds = node.get("bounds")
        if bounds:
            return bounds
        boxes = [bounds_of(child) for child in node.get("children") or []]
        boxes = [item for item in boxes if item]
        if not boxes:
            return None
        x0 = min(item[0] for item in boxes)
        y0 = min(item[1] for item in boxes)
        x1 = max(item[0] + item[2] for item in boxes)
        y1 = max(item[1] + item[3] for item in boxes)
        return [x0, y0, x1 - x0, y1 - y0]

    def walk(nodes, depth: int) -> None:
        for node in nodes or []:
            rows.append({
                "id": node.get("id"),
                "name": node.get("name") or node.get("kind") or "未命名",
                "kind": node.get("kind") or "",
                "bounds": bounds_of(node),
                "depth": depth,
            })
            walk(node.get("children") or [], depth + 1)

    walk(data.get("layers") or [], 0)
    return int(data.get("width") or 0), int(data.get("height") or 0), rows


def write_review(png_path: Path, psd_path: Path, plan_name: str, out_path: Path) -> Path:
    width, height, layers = read_layers(psd_path)
    encoded = base64.b64encode(png_path.read_bytes()).decode("ascii")
    html = (
        TEMPLATE
        .replace("__TITLE__", f"{plan_name} 批注")
        .replace("__LAYERS__", json.dumps(layers, ensure_ascii=False))
        .replace("__IMAGE_SRC__", f"data:image/png;base64,{encoded}")
        .replace("__PLAN_NAME__", json.dumps(plan_name, ensure_ascii=False))
        .replace("__IMAGE_NAME__", json.dumps(png_path.name, ensure_ascii=False))
        .replace("__CANVAS__", json.dumps([width or 0, height or 0]))
    )
    out_path.write_text(html, encoding="utf-8")
    return out_path


def serve(path: Path, port: int) -> None:
    handler = partial(SimpleHTTPRequestHandler, directory=str(path.parent))
    with ThreadingHTTPServer(("0.0.0.0", port), handler) as server:
        try:
            local = socket.gethostbyname(socket.gethostname())
        except Exception:
            local = "127.0.0.1"
        print(f"批注页：http://{local}:{port}/{path.name}", flush=True)
        print(f"本机：http://127.0.0.1:{port}/{path.name}", flush=True)
        print("按 Ctrl+C 停止", flush=True)
        server.serve_forever()
