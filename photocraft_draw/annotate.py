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
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
:root {
  --bg: #0f1419;
  --panel: #161c23;
  --panel-2: #1d252e;
  --line: #28323c;
  --text: #e6edf3;
  --muted: #8b98a5;
  --accent: #4a9eff;
  --accent-soft: rgba(74,158,255,.14);
  --warm: #e07a5f;
  --stage: #0a0e12;
}
@media (prefers-color-scheme: light) {
  :root:not([data-theme]) {
    --bg: #eef2f6; --panel: #ffffff; --panel-2: #f4f7fa; --line: #d9e2eb;
    --text: #1f2933; --muted: #5b6b7a; --accent: #2f6f8f;
    --accent-soft: rgba(47,111,143,.12); --warm: #c25a3f; --stage: #dfe6ee;
  }
}
:root[data-theme="light"] {
  --bg: #eef2f6; --panel: #ffffff; --panel-2: #f4f7fa; --line: #d9e2eb;
  --text: #1f2933; --muted: #5b6b7a; --accent: #2f6f8f;
  --accent-soft: rgba(47,111,143,.12); --warm: #c25a3f; --stage: #dfe6ee;
}
* { box-sizing: border-box; }
html, body { height: 100%; }
body {
  margin: 0; overflow: hidden; background: var(--bg); color: var(--text);
  font: 13px/1.5 -apple-system, "Segoe UI", "Noto Sans CJK SC", "Microsoft YaHei", sans-serif;
  -webkit-font-smoothing: antialiased;
}
button, select, input, textarea { font: inherit; }
button, .import {
  background: var(--panel-2); color: var(--text); border: 1px solid var(--line);
  border-radius: 7px; padding: 6px 12px; cursor: pointer; line-height: 1.2;
  transition: border-color .15s, background .15s;
}
button:hover, .import:hover { border-color: var(--accent); }
button.primary { background: var(--accent); border-color: var(--accent); color: #fff; }
button.primary:hover { filter: brightness(1.08); }
#app { height: 100vh; display: flex; flex-direction: column; }
header {
  flex: 0 0 56px; display: flex; align-items: center; gap: 18px; padding: 0 18px;
  background: var(--panel); border-bottom: 1px solid var(--line);
}
.brand { display: flex; align-items: center; gap: 10px; min-width: 220px; }
.logo {
  width: 30px; height: 30px; border-radius: 8px; background: var(--accent); color: #fff;
  display: grid; place-items: center; font-weight: 700; font-size: 12px; letter-spacing: .5px;
}
.brand h1 { margin: 0; font-size: 14px; font-weight: 600; }
.brand p { margin: 0; color: var(--muted); font-size: 11px; }
.spacer { flex: 1; }
.tools { display: flex; align-items: center; gap: 6px; }
.tools #zoomLabel { min-width: 48px; text-align: center; color: var(--muted); font-variant-numeric: tabular-nums; }
main {
  flex: 1; min-height: 0; display: grid;
  grid-template-columns: 280px minmax(0, 1fr) 300px;
}
.layers { background: var(--panel); border-right: 1px solid var(--line); display: flex; flex-direction: column; min-height: 0; }
.layers .search { margin: 12px 12px 6px; padding: 8px 10px; border-radius: 7px; border: 1px solid var(--line); background: var(--bg); color: var(--text); outline: none; }
.layers .search:focus { border-color: var(--accent); }
#list { flex: 1; overflow: auto; padding: 6px 8px 16px; }
.row {
  display: flex; align-items: center; gap: 6px; height: 28px; padding: 0 8px;
  border-radius: 6px; cursor: pointer; white-space: nowrap; user-select: none;
}
.row:hover { background: var(--panel-2); }
.row.active { background: var(--accent-soft); box-shadow: inset 0 0 0 1px var(--accent); }
.row .twist { width: 12px; flex: 0 0 12px; color: var(--muted); font-size: 9px; text-align: center; }
.row .name { flex: 1; overflow: hidden; text-overflow: ellipsis; }
.row .badge { flex: 0 0 auto; font-size: 10px; color: var(--muted); border: 1px solid var(--line); border-radius: 4px; padding: 0 4px; }
#stage {
  min-width: 0; background: var(--stage); overflow: auto; display: flex;
  padding: 24px; position: relative;
}
#wrap { position: relative; flex: 0 0 auto; margin: auto; box-shadow: 0 8px 40px rgba(0,0,0,.35); }
#img { display: block; max-width: none; }
#box {
  position: absolute; border: 2px solid var(--warm); background: rgba(224,122,95,.12);
  display: none; cursor: move; box-shadow: 0 0 0 1px rgba(0,0,0,.25);
}
#box::after {
  content: "拖动"; position: absolute; top: -20px; left: -2px; font-size: 10px;
  color: #fff; background: var(--warm); padding: 1px 6px; border-radius: 3px;
}
.inspector { background: var(--panel); border-left: 1px solid var(--line); padding: 16px; overflow: auto; }
.sel { display: flex; align-items: center; gap: 8px; min-height: 24px; }
.sel h2 { margin: 0; font-size: 14px; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.sel .badge { font-size: 10px; color: var(--muted); border: 1px solid var(--line); border-radius: 4px; padding: 0 5px; }
.muted { color: var(--muted); }
#selBounds { margin: 6px 0 14px; font-size: 11px; }
.inspector label { display: block; margin: 12px 0 4px; color: var(--muted); font-size: 11px; }
.inspector select, .inspector input, .inspector textarea {
  width: 100%; border: 1px solid var(--line); background: var(--bg); color: var(--text);
  border-radius: 7px; padding: 7px 8px; outline: none;
}
.inspector select:focus, .inspector input:focus, .inspector textarea:focus { border-color: var(--accent); }
.inspector textarea { min-height: 64px; resize: vertical; }
.inspector textarea#globalNote { min-height: 56px; }
.row2 { display: flex; gap: 8px; }
.row2 > div { flex: 1; }
.buttons { display: flex; gap: 8px; margin-top: 14px; }
.buttons button, .buttons .import { flex: 1; text-align: center; }
.import input { display: none; }
.modal {
  position: fixed; inset: 0; background: rgba(6,9,12,.74); display: none;
  align-items: center; justify-content: center; z-index: 50; padding: 24px;
}
.modal.open { display: flex; }
.modal-card {
  width: min(760px, 100%); max-height: 88vh; display: flex; flex-direction: column;
  background: var(--panel); color: var(--text); border: 1px solid var(--line);
  border-radius: 12px; padding: 18px; box-shadow: 0 24px 80px rgba(0,0,0,.5);
}
.modal-card h3 { margin: 0 0 4px; font-size: 15px; }
.modal-card p { margin: 0 0 10px; color: var(--muted); font-size: 12px; }
#jsonOut {
  flex: 1; min-height: 340px; resize: vertical; border: 1px solid var(--line);
  background: var(--bg); color: var(--text); border-radius: 8px; padding: 10px;
  font: 12px/1.6 ui-monospace, "SFMono-Regular", Consolas, monospace;
}
.modal-card .buttons { margin-top: 10px; }
::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-thumb { background: var(--line); border-radius: 6px; border: 2px solid var(--panel); }
::-webkit-scrollbar-track { background: transparent; }
@media (max-width: 1100px) {
  main { grid-template-columns: 240px minmax(0, 1fr) 260px; }
}
</style>
</head>
<body>
<div id="app">
  <header>
    <div class="brand">
      <span class="logo">PD</span>
      <div><h1>图层批注</h1><p id="meta"></p></div>
    </div>
    <div class="spacer"></div>
    <div class="tools">
      <button id="fit">适应</button>
      <button id="zoomOut">−</button><span id="zoomLabel">100%</span><button id="zoomIn">+</button>
      <button id="theme" title="切换明暗">☀</button>
      <button id="export" class="primary">导出意见</button>
      <button id="copy">复制 JSON</button>
    </div>
  </header>
  <main>
    <aside class="layers">
      <input id="search" class="search" placeholder="搜图层名">
      <div id="list"></div>
    </aside>
    <section id="stage"><div id="wrap"><img id="img" alt="画面"><div id="box"></div></div></section>
    <aside class="inspector">
      <div class="sel"><h2 id="selName">未选图层</h2><span id="selKind" class="badge"></span></div>
      <p id="selBounds" class="muted">点左边的图层开始</p>
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
      <label>本层备注</label>
      <textarea id="note" placeholder="这个图层要怎么改"></textarea>
      <label>整体意见</label>
      <textarea id="globalNote" placeholder="整张图的意见"></textarea>
      <div class="buttons">
        <label class="import">导入意见<input id="import" type="file" accept=".json"></label>
        <button id="clear">清空</button>
      </div>
    </aside>
  </main>
</div>
<div id="modal" class="modal">
  <div class="modal-card">
    <h3>修改意见 JSON</h3>
    <p>复制下面这段发回来；下载按钮被浏览器拦下时也用复制。</p>
    <textarea id="jsonOut" readonly></textarea>
    <div class="buttons">
      <button id="modalCopy" class="primary">复制</button>
      <button id="modalDownload">下载文件</button>
      <button id="modalClose">关闭</button>
    </div>
  </div>
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
const wrap = document.getElementById('wrap');
const stage = document.getElementById('stage');
const box = document.getElementById('box');
const selName = document.getElementById('selName');
const selKind = document.getElementById('selKind');
const selBounds = document.getElementById('selBounds');
const action = document.getElementById('action');
const dxInput = document.getElementById('dx');
const dyInput = document.getElementById('dy');
const noteInput = document.getElementById('note');
const globalNote = document.getElementById('globalNote');
const zoomLabel = document.getElementById('zoomLabel');
const meta = document.getElementById('meta');
const modal = document.getElementById('modal');
const jsonOut = document.getElementById('jsonOut');
const root = document.documentElement;

const rows = LAYERS.map((layer, index) => ({ ...layer, index }));
const collapsed = new Set();
const edits = new Map();
let selected = null;
let natW = CANVAS[0] || 1600;
let natH = CANVAS[1] || 900;
let scale = 1;
let autoFit = true;

const KIND = { Group: '组', Shape: '形状', Type: '文字', Pixel: '像素' };
meta.textContent = CANVAS[0] + '×' + CANVAS[1] + ' · ' + rows.length + ' 个图层';

let theme = 'dark';
try {
  theme = localStorage.getItem('pd-theme') || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
} catch (error) {}
function applyTheme() {
  root.dataset.theme = theme;
  document.getElementById('theme').textContent = theme === 'dark' ? '☀' : '☾';
}
document.getElementById('theme').onclick = () => {
  theme = theme === 'dark' ? 'light' : 'dark';
  try { localStorage.setItem('pd-theme', theme); } catch (error) {}
  applyTheme();
};
applyTheme();

function hasChildren(index) {
  return index + 1 < rows.length && rows[index + 1].depth > rows[index].depth;
}

function isHidden(index) {
  let depth = rows[index].depth;
  for (let i = index - 1; i >= 0; i -= 1) {
    if (rows[i].depth < depth) {
      if (collapsed.has(rows[i].id)) return true;
      depth = rows[i].depth;
      if (depth === 0) break;
    }
  }
  return false;
}

function renderList() {
  const query = search.value.trim().toLowerCase();
  list.innerHTML = '';
  rows.forEach((layer, index) => {
    if (!query && isHidden(index)) return;
    if (query && !layer.name.toLowerCase().includes(query)) return;
    const row = document.createElement('div');
    row.className = 'row' + (selected && selected.id === layer.id ? ' active' : '');
    row.style.paddingLeft = (8 + layer.depth * 14) + 'px';
    const twist = document.createElement('span');
    twist.className = 'twist';
    twist.textContent = hasChildren(index) ? (collapsed.has(layer.id) ? '▶' : '▼') : '';
    if (hasChildren(index)) {
      twist.onclick = event => {
        event.stopPropagation();
        if (collapsed.has(layer.id)) collapsed.delete(layer.id); else collapsed.add(layer.id);
        renderList();
      };
    }
    const name = document.createElement('span');
    name.className = 'name';
    name.textContent = layer.name;
    const badge = document.createElement('span');
    badge.className = 'badge';
    badge.textContent = KIND[layer.kind] || layer.kind || '';
    row.append(twist, name, badge);
    row.title = layer.name + ' · ' + (KIND[layer.kind] || layer.kind);
    row.onclick = () => selectLayer(layer);
    list.appendChild(row);
  });
}

function editOf(layer) {
  let item = edits.get(layer.id);
  if (!item) {
    item = { layer: layer.id, name: layer.name, kind: layer.kind, action: 'move', dx: 0, dy: 0, note: '' };
    edits.set(layer.id, item);
  }
  return item;
}

function selectLayer(layer) {
  selected = layer;
  selName.textContent = layer.name;
  selKind.textContent = KIND[layer.kind] || layer.kind || '';
  selBounds.textContent = layer.bounds
    ? 'x ' + layer.bounds[0] + '  y ' + layer.bounds[1] + '  宽 ' + layer.bounds[2] + '  高 ' + layer.bounds[3]
    : '这个组没有直接边界';
  const item = editOf(layer);
  action.value = item.action;
  dxInput.value = item.dx;
  dyInput.value = item.dy;
  noteInput.value = item.note;
  placeBox();
  renderList();
}

function fitView() {
  const pad = 48;
  const width = Math.max(80, stage.clientWidth - pad);
  const height = Math.max(80, stage.clientHeight - pad);
  scale = Math.min(width / natW, height / natH);
  scale = Math.max(0.05, Math.min(scale, 3));
  autoFit = true;
  applyScale();
}

function applyScale() {
  img.style.width = (natW * scale) + 'px';
  img.style.height = (natH * scale) + 'px';
  wrap.style.width = (natW * scale) + 'px';
  wrap.style.height = (natH * scale) + 'px';
  zoomLabel.textContent = Math.round(scale * 100) + '%';
  placeBox();
}

function zoomBy(factor) {
  autoFit = false;
  scale = Math.max(0.05, Math.min(4, scale * factor));
  applyScale();
}

function placeBox() {
  if (!selected || !selected.bounds) { box.style.display = 'none'; return; }
  const item = edits.get(selected.id) || { dx: 0, dy: 0 };
  const [x, y, w, h] = selected.bounds;
  box.style.display = 'block';
  box.style.left = ((x + (item.dx || 0)) * scale) + 'px';
  box.style.top = ((y + (item.dy || 0)) * scale) + 'px';
  box.style.width = Math.max(2, w * scale) + 'px';
  box.style.height = Math.max(2, h * scale) + 'px';
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
document.getElementById('fit').onclick = fitView;
document.getElementById('zoomIn').onclick = () => zoomBy(1.2);
document.getElementById('zoomOut').onclick = () => zoomBy(1 / 1.2);

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
  item.dx = Math.round(drag.dx + (event.clientX - drag.x) / scale);
  item.dy = Math.round(drag.dy + (event.clientY - drag.y) / scale);
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

function openJson() {
  jsonOut.value = JSON.stringify(payload(), null, 2);
  modal.classList.add('open');
  jsonOut.focus();
  jsonOut.select();
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

document.getElementById('export').onclick = openJson;
document.getElementById('copy').onclick = openJson;
document.getElementById('modalClose').onclick = () => modal.classList.remove('open');
document.getElementById('modalDownload').onclick = download;
document.getElementById('modalCopy').onclick = async () => {
  const text = jsonOut.value || JSON.stringify(payload(), null, 2);
  jsonOut.value = text;
  jsonOut.focus();
  jsonOut.select();
  let ok = false;
  try { await navigator.clipboard.writeText(text); ok = true; } catch (error) {}
  if (!ok) { try { ok = document.execCommand('copy'); } catch (error) {} }
  const button = document.getElementById('modalCopy');
  button.textContent = ok ? '已复制' : '请手动复制';
  setTimeout(() => { button.textContent = '复制'; }, 1600);
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

window.addEventListener('resize', () => { if (autoFit) fitView(); else applyScale(); });

img.onload = () => {
  natW = img.naturalWidth || CANVAS[0];
  natH = img.naturalHeight || CANVAS[1];
  fitView();
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
