# -*- coding: utf-8 -*-
"""图层批注页：按图层导出透明图，叠成简易 Photoshop，框选后导出三维意见。"""
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
  --bg: #0f1419; --panel: #161c23; --panel-2: #1d252e; --line: #28323c;
  --text: #e6edf3; --muted: #8b98a5; --accent: #4a9eff;
  --accent-soft: rgba(74,158,255,.14); --warm: #e07a5f; --stage: #0a0e12;
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
button {
  background: var(--panel-2); color: var(--text); border: 1px solid var(--line);
  border-radius: 7px; padding: 6px 12px; cursor: pointer; line-height: 1.2;
  transition: border-color .15s, background .15s;
}
button:hover { border-color: var(--accent); }
button.primary { background: var(--accent); border-color: var(--accent); color: #fff; }
button:disabled { opacity: .35; cursor: default; }
#app { height: 100vh; display: flex; flex-direction: column; }
header {
  flex: 0 0 56px; display: flex; align-items: center; gap: 18px; padding: 0 18px;
  background: var(--panel); border-bottom: 1px solid var(--line);
}
.brand { display: flex; align-items: center; gap: 10px; min-width: 200px; }
.logo {
  width: 30px; height: 30px; border-radius: 8px; background: var(--accent); color: #fff;
  display: grid; place-items: center; font-weight: 700; font-size: 12px;
}
.brand h1 { margin: 0; font-size: 14px; font-weight: 600; }
.brand p { margin: 0; color: var(--muted); font-size: 11px; }
.spacer { flex: 1; }
.tools { display: flex; align-items: center; gap: 6px; }
.tools #zoomLabel { min-width: 48px; text-align: center; color: var(--muted); font-variant-numeric: tabular-nums; }
main { flex: 1; min-height: 0; display: grid; grid-template-columns: 300px minmax(0, 1fr); }
.side { background: var(--panel); border-right: 1px solid var(--line); display: flex; flex-direction: column; min-height: 0; }
.tabs { display: flex; gap: 4px; padding: 10px 12px 0; }
.tab {
  flex: 1; padding: 7px 8px; border: 1px solid transparent; border-bottom: 2px solid transparent;
  background: transparent; border-radius: 6px 6px 0 0; color: var(--muted);
}
.tab.active { color: var(--text); border-bottom-color: var(--accent); background: var(--panel-2); }
.tab .count { display: inline-block; min-width: 16px; padding: 0 4px; margin-left: 4px; border-radius: 8px; background: var(--warm); color: #fff; font-size: 10px; line-height: 16px; }
#layerPane, #notePane { flex: 1; min-height: 0; display: flex; flex-direction: column; }
#layerPane[hidden], #notePane[hidden] { display: none; }
#notePane { padding: 10px 12px 14px; overflow: auto; }
.side .search { margin: 10px 12px 6px; padding: 8px 10px; border-radius: 7px; border: 1px solid var(--line); background: var(--bg); color: var(--text); outline: none; }
.side .search:focus { border-color: var(--accent); }
#list { flex: 1; overflow: auto; padding: 6px 8px 16px; }
.row {
  display: flex; align-items: center; gap: 5px; height: 30px; padding: 0 6px 0 8px;
  border-radius: 6px; cursor: pointer; white-space: nowrap; user-select: none;
}
.row:hover, .row.hover { background: var(--panel-2); }
.row.active { background: var(--accent-soft); box-shadow: inset 0 0 0 1px var(--accent); }
.row .eye {
  flex: 0 0 20px; width: 20px; height: 20px; padding: 0; border-radius: 4px;
  border: 1px solid var(--line); background: var(--panel); color: var(--muted);
  font-size: 11px; line-height: 1;
}
.row .eye.on { color: var(--accent); border-color: var(--accent); }
.row .spacer-eye { flex: 0 0 20px; }
.row .twist { width: 12px; flex: 0 0 12px; color: var(--muted); font-size: 9px; text-align: center; }
.row .name { flex: 1; overflow: hidden; text-overflow: ellipsis; }
.row .badge { flex: 0 0 auto; font-size: 10px; color: var(--muted); border: 1px solid var(--line); border-radius: 4px; padding: 0 4px; }
.row .dot { flex: 0 0 auto; width: 6px; height: 6px; border-radius: 50%; background: var(--warm); }
.workspace { min-width: 0; min-height: 0; display: flex; flex-direction: column; }
#stage {
  flex: 1; min-height: 0; min-width: 0; overflow: auto; display: flex; padding: 24px;
  position: relative;
  background: repeating-conic-gradient(#0f1318 0% 25%, #151a21 0% 50%) 50% / 24px 24px;
}
:root[data-theme="light"] #stage { background: repeating-conic-gradient(#dfe6ee 0% 25%, #e9eef4 0% 50%) 50% / 24px 24px; }
#wrap { position: relative; flex: 0 0 auto; margin: auto; box-shadow: 0 8px 40px rgba(0,0,0,.35); user-select: none; }
.layer { position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none; user-select: none; -webkit-user-drag: none; }
#stack { position: absolute; inset: 0; }
#selectionBox { position: absolute; border: 1px dashed var(--muted); display: none; pointer-events: none; z-index: 2; }
#marquee { position: absolute; inset: 0; cursor: crosshair; z-index: 3; touch-action: none; }
#drawRect {
  position: absolute; border: 1px dashed var(--accent); background: rgba(74,158,255,.12);
  display: none; pointer-events: auto; cursor: move; z-index: 4;
}
#drawRect .resize, .anno .resize {
  position: absolute; right: -6px; bottom: -6px; width: 12px; height: 12px;
  background: var(--warm); border: 2px solid #fff; border-radius: 2px;
  cursor: nwse-resize; z-index: 7;
}
.anno {
  position: absolute; border: 2px solid var(--warm); background: rgba(224,122,95,.10);
  cursor: move; z-index: 5; box-sizing: border-box;
}
.anno:hover { background: rgba(224,122,95,.18); }
.anno .num {
  position: absolute; top: -11px; left: -11px; width: 20px; height: 20px; border-radius: 50%;
  background: var(--warm); color: #fff; font-size: 10px; font-weight: 600;
  display: grid; place-items: center; border: 2px solid rgba(255,255,255,.85);
  box-shadow: 0 2px 8px rgba(0,0,0,.4);
}
#editor {
  position: absolute; width: 340px; background: var(--panel); border: 1px solid var(--line);
  border-radius: 10px; padding: 12px; box-shadow: 0 16px 50px rgba(0,0,0,.55);
  display: none; z-index: 20; user-select: text;
}
#editor * { user-select: text; }
#editor.open { display: block; }
.ed-head { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; cursor: grab; }
.ed-head.dragging { cursor: grabbing; }
.ed-head .grip { color: var(--muted); letter-spacing: -2px; font-size: 14px; }
.ed-head strong { font-size: 13px; }
.ed-visible { color: var(--muted); font-size: 11px; margin: -2px 0 8px; line-height: 1.5; }
.ed-head .badge { font-size: 10px; color: var(--muted); border: 1px solid var(--line); border-radius: 4px; padding: 0 5px; max-width: 170px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ed-head .grow { flex: 1; }
.ed-meta { color: var(--muted); font-size: 11px; margin-bottom: 8px; }
#edNote {
  width: 100%; min-height: 70px; max-height: 150px; resize: vertical;
  border: 1px solid var(--line); background: var(--bg); color: var(--text);
  border-radius: 7px; padding: 8px 10px; outline: none;
}
#edNote:focus { border-color: var(--accent); }
.ed-foot { display: flex; align-items: center; gap: 6px; margin-top: 8px; }
.ed-foot .muted { flex: 1; color: var(--muted); font-size: 11px; }
#hint {
  position: absolute; left: 50%; bottom: 14px; transform: translateX(-50%);
  color: var(--muted); font-size: 11px; background: rgba(10,14,18,.72);
  padding: 4px 10px; border-radius: 12px; pointer-events: none; z-index: 10;
}
#toast {
  position: absolute; left: 50%; bottom: 46px; transform: translateX(-50%) translateY(8px);
  background: var(--accent); color: #fff; padding: 6px 14px; border-radius: 14px;
  font-size: 12px; opacity: 0; pointer-events: none; transition: opacity .18s, transform .18s;
  z-index: 30;
}
#toast.show { opacity: 1; transform: translateX(-50%) translateY(0); }
.note-item {
  padding: 8px 10px; border: 1px solid var(--line); border-radius: 7px;
  margin-bottom: 6px; cursor: pointer; background: var(--panel-2);
}
.note-item:hover { border-color: var(--accent); }
.note-item .head { display: flex; align-items: center; gap: 6px; }
.note-item .index { color: #fff; background: var(--warm); border-radius: 50%; width: 16px; height: 16px; font-size: 10px; display: grid; place-items: center; }
.note-item .name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.note-item .del { border: none; background: transparent; color: var(--muted); padding: 0 4px; }
.note-item .body { color: var(--muted); font-size: 11px; margin-top: 3px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.empty { color: var(--muted); text-align: center; padding: 30px 12px; font-size: 12px; }
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
.modal-card .buttons { display: flex; gap: 8px; margin-top: 10px; }
.modal-card .buttons button { flex: 1; }
::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-thumb { background: var(--line); border-radius: 6px; border: 2px solid var(--panel); }
::-webkit-scrollbar-track { background: transparent; }
@media (max-width: 1100px) { main { grid-template-columns: 250px minmax(0, 1fr); } }
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
      <button id="undo" title="撤销 Ctrl+Z" disabled>↶</button>
      <button id="redo" title="重做 Ctrl+Shift+Z" disabled>↷</button>
      <button id="theme" title="切换明暗">☀</button>
      <button id="export" class="primary">导出意见</button>
      <button id="copy">复制 JSON</button>
    </div>
  </header>
  <main>
    <aside class="side">
      <div class="tabs">
        <button class="tab active" data-tab="layers">图层</button>
        <button class="tab" data-tab="notes">批注 <span id="noteCount" class="count">0</span></button>
      </div>
      <div id="layerPane">
        <input id="search" class="search" placeholder="搜图层名">
        <div id="list"></div>
      </div>
      <div id="notePane" hidden>
        <div id="notes"></div>
      </div>
    </aside>
    <div class="workspace">
      <section id="stage">
        <div id="wrap">
          <div id="stack"></div>
          <div id="selectionBox"></div>
          <div id="drawRect"><span class="resize"></span></div>
          <div id="marquee"></div>
          <div id="annos"></div>
          <div id="editor">
            <div class="ed-head">
              <span class="grip" title="拖动卡片">⠿</span>
              <strong id="edTitle">新批注</strong>
              <span class="grow"></span>
              <button id="edClose" title="关闭">×</button>
            </div>
            <div class="ed-meta" id="edMeta"></div>
            <div class="ed-visible" id="edVisible"></div>
            <textarea id="edNote" placeholder="这里要怎么改？写一句，Enter 保存"></textarea>
            <div class="ed-foot">
              <span class="muted">Enter 保存，Shift+Enter 换行</span>
              <button id="edDelete">删掉</button>
              <button id="edCancel">取消</button>
              <button id="edSave" class="primary">保存</button>
            </div>
          </div>
        </div>
        <div id="hint">在图上拖框，写一句，Enter 保存</div>
        <div id="toast"></div>
      </section>
    </div>
  </main>
</div>
<div id="modal" class="modal">
  <div class="modal-card">
    <h3>修改意见 JSON</h3>
    <p>每条意见带图层、区域和动作，复制下面这段发回来。</p>
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
const TOPS = __TOPS__;
const PLAN_NAME = __PLAN_NAME__;
const IMAGE_NAME = __IMAGE_NAME__;
const CANVAS = __CANVAS__;

const list = document.getElementById('list');
const notesBox = document.getElementById('notes');
const search = document.getElementById('search');
const stack = document.getElementById('stack');
const wrap = document.getElementById('wrap');
const stage = document.getElementById('stage');
const marquee = document.getElementById('marquee');
const drawRect = document.getElementById('drawRect');
const selectionBox = document.getElementById('selectionBox');
const annos = document.getElementById('annos');
const editor = document.getElementById('editor');
const edTitle = document.getElementById('edTitle');
const edMeta = document.getElementById('edMeta');
const edVisible = document.getElementById('edVisible');
const edNote = document.getElementById('edNote');
const noteCount = document.getElementById('noteCount');
const zoomLabel = document.getElementById('zoomLabel');
const meta = document.getElementById('meta');
const modal = document.getElementById('modal');
const jsonOut = document.getElementById('jsonOut');
const toast = document.getElementById('toast');
const hint = document.getElementById('hint');
const root = document.documentElement;

const rows = LAYERS.map((layer, index) => ({ ...layer, index }));
const topIds = new Set(TOPS.map(item => String(item.id)));
const collapsed = new Set();
const images = new Map();
const visible = new Map();
let annotations = [];
let editing = null;
let selected = null;
let nextId = 1;
let natW = CANVAS[0] || 1600;
let natH = CANVAS[1] || 900;
let scale = 1;
let autoFit = true;
let history = [];
let hIndex = -1;
let toastTimer = null;
let drawing = null;
let boxDrag = null;
let editorPos = null;
let editorDrag = null;

const KIND = { Group: '组', Shape: '形状', Type: '文字', Pixel: '像素' };

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

meta.textContent = CANVAS[0] + '×' + CANVAS[1] + ' · ' + rows.length + ' 个图层';

TOPS.slice().reverse().forEach(item => {
  const img = document.createElement('img');
  img.className = 'layer';
  img.src = item.src;
  img.alt = item.name;
  img.draggable = false;
  img.dataset.id = String(item.id);
  stack.appendChild(img);
  images.set(String(item.id), img);
  visible.set(String(item.id), true);
});

function topOf(index) {
  let depth = rows[index].depth;
  for (let i = index - 1; i >= 0; i -= 1) {
    if (rows[i].depth < depth) {
      if (rows[i].depth === 0) return rows[i];
      depth = rows[i].depth;
    }
  }
  return rows[index].depth === 0 ? rows[index] : null;
}
function topOfLayer(layer) {
  const index = rows.findIndex(item => item.id === layer.id);
  return index >= 0 ? topOf(index) : null;
}
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
function annotationCount(layerId) {
  return annotations.filter(item => item.layer === layerId).length;
}

function renderList() {
  const query = search.value.trim().toLowerCase();
  list.innerHTML = '';
  rows.forEach((layer, index) => {
    if (!query && isHidden(index)) return;
    if (query && !layer.name.toLowerCase().includes(query)) return;
    const row = document.createElement('div');
    row.className = 'row' + (selected && selected.id === layer.id ? ' active' : '');
    row.style.paddingLeft = (8 + layer.depth * 12) + 'px';
    row.dataset.id = layer.id;
    const isTop = layer.depth === 0 && topIds.has(String(layer.id));
    const eye = document.createElement('button');
    eye.className = 'eye' + (isTop && visible.get(String(layer.id)) ? ' on' : '');
    if (isTop) {
      eye.textContent = visible.get(String(layer.id)) ? '●' : '○';
      eye.title = visible.get(String(layer.id)) ? '隐藏这一层' : '显示这一层';
      eye.onclick = event => {
        event.stopPropagation();
        const on = !visible.get(String(layer.id));
        visible.set(String(layer.id), on);
        const img = images.get(String(layer.id));
        if (img) img.style.display = on ? 'block' : 'none';
        renderList();
      };
    } else {
      eye.style.visibility = 'hidden';
    }
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
    const count = annotationCount(layer.id);
    badge.textContent = (KIND[layer.kind] || layer.kind) + (count ? ' · ' + count : '');
    if (count) {
      const dot = document.createElement('span');
      dot.className = 'dot';
      row.append(eye, twist, name, dot, badge);
    } else {
      row.append(eye, twist, name, badge);
    }
    row.title = layer.name + ' · ' + (KIND[layer.kind] || layer.kind);
    row.onclick = () => selectLayer(layer);
    list.appendChild(row);
  });
}

function selectLayer(layer) {
  selected = layer;
  const top = topOfLayer(layer);
  if (top) {
    const key = String(top.id);
    if (!visible.get(key)) {
      visible.set(key, true);
      const img = images.get(key);
      if (img) img.style.display = 'block';
      showToast('已显示 ' + top.name);
    }
  }
  const bounds = layer.bounds;
  if (bounds) {
    const [x, y, w, h] = bounds;
    selectionBox.style.display = 'block';
    selectionBox.style.left = (x * scale) + 'px';
    selectionBox.style.top = (y * scale) + 'px';
    selectionBox.style.width = Math.max(1, w * scale) + 'px';
    selectionBox.style.height = Math.max(1, h * scale) + 'px';
  } else {
    selectionBox.style.display = 'none';
  }
  renderList();
  const row = document.querySelector('.row[data-id="' + layer.id + '"]');
  if (row) row.scrollIntoView({ block: 'nearest' });
}

function renderNotes() {
  noteCount.textContent = String(annotations.length);
  notesBox.innerHTML = '';
  if (!annotations.length) {
    notesBox.innerHTML = '<div class="empty">在图上拖一个框，写一句，就会生成一条带图层和区域的批注。</div>';
    return;
  }
  annotations.forEach((item, index) => {
    const node = document.createElement('div');
    node.className = 'note-item';
    const head = document.createElement('div');
    head.className = 'head';
    const indexBadge = document.createElement('span');
    indexBadge.className = 'index';
    indexBadge.textContent = String(index + 1);
    const name = document.createElement('span');
    name.className = 'name';
    name.textContent = item.layer_name;
    const del = document.createElement('button');
    del.className = 'del';
    del.textContent = '×';
    del.onclick = event => {
      event.stopPropagation();
      pushHistory();
      annotations = annotations.filter(other => other.id !== item.id);
      if (editing && editing.id === item.id) closeEditor();
      renderAll();
    };
    head.append(indexBadge, name, del);
    node.appendChild(head);
    const body = document.createElement('div');
    body.className = 'body';
    body.textContent = (item.note || '（没写说明）') + ' · ' + item.rect.map(Math.round).join(',');
    node.appendChild(body);
    node.onclick = () => openEditor(item);
    notesBox.appendChild(node);
  });
}

function clamp(value, min, max) { return Math.max(min, Math.min(max, value)); }
function updateMetaText(rect) {
  edMeta.textContent = '区域 ' + rect.map(Math.round).join(', ') + '　宽高 ' + Math.round(rect[2]) + '×' + Math.round(rect[3]);
}
function showDraftBox(rect) {
  drawRect.style.display = 'block';
  drawRect.style.left = (rect[0] * scale) + 'px';
  drawRect.style.top = (rect[1] * scale) + 'px';
  drawRect.style.width = (rect[2] * scale) + 'px';
  drawRect.style.height = (rect[3] * scale) + 'px';
}
function updateDraftMeta(rect) {
  if (!editing) return;
  editing.rect = rect.slice();
  const candidates = layersInRect(rect);
  editing.candidates = candidates;
  const preferred = candidates.find(item => String(item.id) === String(editing.layer)) || candidates[0] || null;
  if (preferred) {
    editing.layer = preferred.id;
    editing.layer_name = preferred.name;
    editing.kind = preferred.kind;
  }
  updateMetaText(rect);
  edVisible.textContent = '框内图层：' + (candidates.map(item => item.name).join('、') || '无')
    + (hiddenTopNames().length ? '　隐藏：' + hiddenTopNames().join('、') : '');
}
function beginBoxDrag(event, kind, el, rect, target) {
  event.preventDefault();
  event.stopPropagation();
  if (target === 'draft') drawing = null;
  boxDrag = {
    kind, el, target, startX: event.clientX, startY: event.clientY,
    startRect: rect.slice(), moved: false
  };
}

function renderAnnos() {
  annos.innerHTML = '';
  annotations.forEach((item, index) => {
    const node = document.createElement('div');
    node.className = 'anno';
    const [x, y, w, h] = item.rect;
    node.style.left = (x * scale) + 'px';
    node.style.top = (y * scale) + 'px';
    node.style.width = Math.max(2, w * scale) + 'px';
    node.style.height = Math.max(2, h * scale) + 'px';
    const num = document.createElement('span');
    num.className = 'num';
    num.textContent = String(index + 1);
    const handle = document.createElement('span');
    handle.className = 'resize';
    handle.title = '拖动缩放';
    handle.addEventListener('mousedown', event => {
      if (editing && editing.id !== item.id) { commitEditing(); return; }
      beginBoxDrag(event, 'resize', node, item.rect, String(item.id));
    });
    node.addEventListener('mousedown', event => {
      if (event.target.classList.contains('resize')) return;
      if (editing && editing.id !== item.id) { commitEditing(); return; }
      beginBoxDrag(event, 'move', node, item.rect, String(item.id));
    });
    node.append(num, handle);
    node.title = item.note || item.layer_name;
    annos.appendChild(node);
  });
}

function visibleTopNames() {
  return rows
    .filter(layer => layer.depth === 0 && topIds.has(String(layer.id)) && visible.get(String(layer.id)) !== false)
    .map(layer => layer.name);
}
function hiddenTopNames() {
  return rows
    .filter(layer => layer.depth === 0 && topIds.has(String(layer.id)) && visible.get(String(layer.id)) === false)
    .map(layer => layer.name);
}
function layersInRect(rect) {
  const [x, y, w, h] = rect;
  return rows
    .filter(layer => layer.depth === 0 && topIds.has(String(layer.id)))
    .filter(layer => {
      if (!layer.bounds) return false;
      if (visible.get(String(layer.id)) === false) return false;
      const [lx, ly, lw, lh] = layer.bounds;
      return lx < x + w && lx + lw > x && ly < y + h && ly + lh > y;
    })
    .sort((a, b) => (a.bounds[2] * a.bounds[3]) - (b.bounds[2] * b.bounds[3]));
}
function openEditor(existing) {
  if (editing) commitEditing();
  let rect;
  let candidates;
  if (existing) {
    rect = existing.rect;
    candidates = layersInRect(rect);
    if (existing.layer != null && !candidates.some(item => String(item.id) === String(existing.layer))) {
      const known = rows.find(item => item.id === existing.layer);
      candidates = candidates.concat([known || {
        id: existing.layer, name: existing.layer_name, kind: existing.kind, bounds: null, depth: 0
      }]);
    }
    const current = candidates.find(item => String(item.id) === String(existing.layer)) || candidates[0] || null;
    editing = {
      ...existing,
      layer: current ? current.id : existing.layer,
      layer_name: current ? current.name : existing.layer_name,
      kind: current ? current.kind : existing.kind,
      candidates
    };
  } else {
    rect = drawing;
    if (!rect) return;
    candidates = layersInRect(rect);
    const preferred = candidates[0] || null;
    editing = {
      id: null, layer: preferred ? preferred.id : null,
      layer_name: preferred ? preferred.name : '画面', kind: preferred ? preferred.kind : '',
      rect: rect.slice(), note: '', candidates
    };
  }
  edTitle.textContent = existing ? ('第 ' + (annotations.findIndex(item => item.id === existing.id) + 1) + ' 条') : '新批注';
  updateMetaText(editing.rect);
  edVisible.textContent = '框内图层：' + (candidates.map(item => item.name).join('、') || '无')
    + (hiddenTopNames().length ? '　隐藏：' + hiddenTopNames().join('、') : '');
  edNote.value = editing.note || '';
  document.getElementById('edDelete').style.display = existing ? 'inline-block' : 'none';
  if (existing) {
    drawRect.style.display = 'none';
  } else {
    showDraftBox(editing.rect);
  }
  placeEditor(editing.rect);
  editor.classList.add('open');
  hint.style.display = 'none';
  setTimeout(() => edNote.focus(), 0);
  renderNotes();
}

function placeEditor(rect) {
  const width = 340;
  const height = 250;
  const wrapW = natW * scale;
  const wrapH = natH * scale;
  if (editorPos) {
    const left = Math.max(0, Math.min(editorPos.left, Math.max(0, wrapW - width)));
    const top = Math.max(0, Math.min(editorPos.top, Math.max(0, wrapH - height)));
    editor.style.left = left + 'px';
    editor.style.top = top + 'px';
    return;
  }
  let left = rect[0] * scale + rect[2] * scale + 12;
  let top = rect[1] * scale;
  if (left + width > wrapW - 8) left = rect[0] * scale - width - 12;
  if (top + height > wrapH - 8) top = wrapH - height - 8;
  left = Math.max(8, Math.min(left, Math.max(8, wrapW - width - 8)));
  top = Math.max(8, Math.min(top, Math.max(8, wrapH - height - 8)));
  editor.style.left = left + 'px';
  editor.style.top = top + 'px';
}

const edHead = document.querySelector('.ed-head');
edHead.addEventListener('mousedown', event => {
  if (event.target.closest('button')) return;
  event.preventDefault();
  const left = parseFloat(editor.style.left) || 0;
  const top = parseFloat(editor.style.top) || 0;
  editorDrag = { x: event.clientX, y: event.clientY, left, top };
  edHead.classList.add('dragging');
});
window.addEventListener('mousemove', event => {
  if (!editorDrag) return;
  const wrapW = natW * scale;
  const wrapH = natH * scale;
  const width = editor.offsetWidth || 340;
  const height = editor.offsetHeight || 250;
  let left = editorDrag.left + (event.clientX - editorDrag.x);
  let top = editorDrag.top + (event.clientY - editorDrag.y);
  left = Math.max(0, Math.min(left, Math.max(0, wrapW - width)));
  top = Math.max(0, Math.min(top, Math.max(0, wrapH - height)));
  editor.style.left = left + 'px';
  editor.style.top = top + 'px';
  editorPos = { left, top };
});
window.addEventListener('mouseup', () => {
  if (!editorDrag) return;
  editorDrag = null;
  edHead.classList.remove('dragging');
});

function commitEditing() {
  if (!editing) return false;
  const note = edNote.value.trim();
  if (!note) { closeEditor(); return false; }
  editing.note = note;
  editing.layers = (editing.candidates || []).map(item => ({ id: item.id, name: item.name, kind: item.kind }));
  editing.visible_layers = visibleTopNames();
  editing.hidden_layers = hiddenTopNames();
  delete editing.candidates;
  if (editing.id == null) {
    editing.id = nextId++;
    annotations.push(editing);
  } else {
    const index = annotations.findIndex(item => item.id === editing.id);
    if (index >= 0) annotations[index] = editing;
  }
  pushHistory();
  closeEditor();
  renderAll();
  return true;
}

function closeEditor() {
  editing = null;
  editor.classList.remove('open');
  drawRect.style.display = 'none';
  drawing = null;
  hint.style.display = 'block';
  renderNotes();
}

function deleteEditing() {
  if (!editing || editing.id == null) { closeEditor(); return; }
  pushHistory();
  annotations = annotations.filter(item => item.id !== editing.id);
  closeEditor();
  renderAll();
  showToast('已删除');
}

function showToast(text) {
  toast.textContent = text;
  toast.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove('show'), 1100);
}

function fitView() {
  const pad = 48;
  const width = Math.max(80, stage.clientWidth - pad);
  const height = Math.max(80, stage.clientHeight - pad);
  scale = Math.max(0.05, Math.min(3, Math.min(width / natW, height / natH)));
  autoFit = true;
  applyScale();
}

function applyScale() {
  wrap.style.width = (natW * scale) + 'px';
  wrap.style.height = (natH * scale) + 'px';
  zoomLabel.textContent = Math.round(scale * 100) + '%';
  renderAnnos();
  if (selected && selected.bounds) {
    const [x, y, w, h] = selected.bounds;
    selectionBox.style.left = (x * scale) + 'px';
    selectionBox.style.top = (y * scale) + 'px';
    selectionBox.style.width = Math.max(1, w * scale) + 'px';
    selectionBox.style.height = Math.max(1, h * scale) + 'px';
  }
  if (editing) placeEditor(editing.rect);
}

function zoomBy(factor) {
  autoFit = false;
  scale = Math.max(0.05, Math.min(4, scale * factor));
  applyScale();
}

function hitTest(px, py) {
  let best = null;
  rows.forEach(layer => {
    if (!layer.bounds) return;
    const [x, y, w, h] = layer.bounds;
    if (px < x || px > x + w || py < y || py > y + h) return;
    const area = w * h;
    if (!best || layer.depth > best.depth || (layer.depth === best.depth && area < best.area)) {
      best = { ...layer, area };
    }
  });
  return best;
}

function pointFromEvent(event) {
  const rect = wrap.getBoundingClientRect();
  const x = Math.max(0, Math.min(natW, (event.clientX - rect.left) / scale));
  const y = Math.max(0, Math.min(natH, (event.clientY - rect.top) / scale));
  return [x, y];
}

marquee.addEventListener('mousedown', event => {
  event.preventDefault();
  if (editing) commitEditing();
  drawing = null;
  const [x, y] = pointFromEvent(event);
  drawing = [x, y, 0, 0];
  drawRect.style.display = 'block';
  drawRect.style.left = (x * scale) + 'px';
  drawRect.style.top = (y * scale) + 'px';
  drawRect.style.width = '0px';
  drawRect.style.height = '0px';
});

window.addEventListener('mousemove', event => {
  if (boxDrag) return;
  if (!drawing) return;
  const [x, y] = pointFromEvent(event);
  const rect = [
    Math.min(drawing[0], x), Math.min(drawing[1], y),
    Math.abs(x - drawing[0]), Math.abs(y - drawing[1])
  ];
  drawing = [drawing[0], drawing[1], rect[2], rect[3], rect[0], rect[1]];
  drawRect.style.left = (rect[0] * scale) + 'px';
  drawRect.style.top = (rect[1] * scale) + 'px';
  drawRect.style.width = (rect[2] * scale) + 'px';
  drawRect.style.height = (rect[3] * scale) + 'px';
});

window.addEventListener('mouseup', () => {
  if (boxDrag) return;
  if (!drawing) return;
  const raw = drawing;
  drawing = null;
  const rect = raw.length >= 6 ? [raw[4], raw[5], raw[2], raw[3]] : [raw[0], raw[1], raw[2], raw[3]];
  if (rect[2] < 4 || rect[3] < 4) {
    drawRect.style.display = 'none';
    return;
  }
  drawing = rect;
  openEditor(null);
  drawing = null;
});

drawRect.addEventListener('mousedown', event => {
  if (!editing) return;
  if (event.target.classList.contains('resize')) return;
  beginBoxDrag(event, 'move', drawRect, editing.rect, 'draft');
});
drawRect.querySelector('.resize').addEventListener('mousedown', event => {
  if (!editing) return;
  beginBoxDrag(event, 'resize', drawRect, editing.rect, 'draft');
});

window.addEventListener('mousemove', event => {
  if (!boxDrag) return;
  const moveX = event.clientX - boxDrag.startX;
  const moveY = event.clientY - boxDrag.startY;
  if (!boxDrag.moved && Math.abs(moveX) + Math.abs(moveY) < 3) return;
  boxDrag.moved = true;
  const r = boxDrag.startRect;
  let next;
  if (boxDrag.kind === 'move') {
    next = [
      clamp(r[0] + moveX / scale, 0, natW - r[2]),
      clamp(r[1] + moveY / scale, 0, natH - r[3]),
      r[2], r[3]
    ];
  } else {
    next = [
      r[0], r[1],
      clamp(r[2] + moveX / scale, 6, natW - r[0]),
      clamp(r[3] + moveY / scale, 6, natH - r[1])
    ];
  }
  const el = boxDrag.el;
  el.style.left = (next[0] * scale) + 'px';
  el.style.top = (next[1] * scale) + 'px';
  el.style.width = (next[2] * scale) + 'px';
  el.style.height = (next[3] * scale) + 'px';
  if (boxDrag.target === 'draft') {
    updateDraftMeta(next);
  } else {
    const item = annotations.find(candidate => String(candidate.id) === boxDrag.target);
    if (item) {
      item.rect = next;
      if (editing && String(editing.id) === boxDrag.target) {
        editing.rect = next;
        updateMetaText(next);
      }
    }
  }
});

window.addEventListener('mouseup', () => {
  if (!boxDrag) return;
  const drag = boxDrag;
  boxDrag = null;
  if (drag.moved) {
    pushHistory();
    renderAnnos();
    renderNotes();
  } else if (drag.target !== 'draft') {
    const item = annotations.find(candidate => String(candidate.id) === drag.target);
    if (item) openEditor(item);
  }
});

document.querySelectorAll('.tab').forEach(tab => {
  tab.onclick = () => {
    document.querySelectorAll('.tab').forEach(item => item.classList.toggle('active', item === tab));
    const showNotes = tab.dataset.tab === 'notes';
    document.getElementById('notePane').hidden = !showNotes;
    document.getElementById('layerPane').hidden = showNotes;
  };
});

edNote.addEventListener('keydown', event => {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    if (commitEditing()) showToast('已记录');
  }
});
document.getElementById('edSave').onclick = () => { if (commitEditing()) showToast('已记录'); };
document.getElementById('edCancel').onclick = closeEditor;
document.getElementById('edClose').onclick = closeEditor;
document.getElementById('edDelete').onclick = deleteEditing;

function snapshot() { return JSON.stringify(annotations); }
function pushHistory() {
  const current = snapshot();
  if (history[hIndex] === current) return;
  history = history.slice(0, hIndex + 1);
  history.push(current);
  if (history.length > 80) history.shift();
  hIndex = history.length - 1;
  updateHistoryButtons();
}
function restore(snap) {
  annotations = JSON.parse(snap);
  closeEditor();
  renderAll();
}
function undo() { if (hIndex > 0) { hIndex -= 1; restore(history[hIndex]); updateHistoryButtons(); } }
function redo() { if (hIndex < history.length - 1) { hIndex += 1; restore(history[hIndex]); updateHistoryButtons(); } }
function updateHistoryButtons() {
  document.getElementById('undo').disabled = hIndex <= 0;
  document.getElementById('redo').disabled = hIndex >= history.length - 1;
}
document.getElementById('undo').onclick = undo;
document.getElementById('redo').onclick = redo;

function renderAll() { renderList(); renderNotes(); renderAnnos(); }

function payload() {
  return {
    plan: PLAN_NAME,
    image: IMAGE_NAME,
    canvas: CANVAS,
    annotations: annotations.map((item, index) => ({
      id: item.id, index: index + 1, layer: item.layer, layer_name: item.layer_name,
      kind: item.kind, rect: item.rect.map(Math.round),
      layers: item.layers || [], visible_layers: item.visible_layers || [], hidden_layers: item.hidden_layers || [],
      note: item.note || ''
    }))
  };
}

function openJson() {
  jsonOut.value = JSON.stringify(payload(), null, 2);
  modal.classList.add('open');
  jsonOut.focus();
  jsonOut.select();
}
function download() {
  const blob = new Blob([JSON.stringify(payload(), null, 2)], { type: 'application/json' });
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

document.getElementById('fit').onclick = fitView;
document.getElementById('zoomIn').onclick = () => zoomBy(1.2);
document.getElementById('zoomOut').onclick = () => zoomBy(1 / 1.2);
search.oninput = renderList;

window.addEventListener('keydown', event => {
  if (event.key === 'Escape') {
    if (modal.classList.contains('open')) modal.classList.remove('open');
    else if (editing) closeEditor();
    return;
  }
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'z') {
    event.preventDefault();
    if (event.shiftKey) redo(); else undo();
    return;
  }
  if (editing && document.activeElement === edNote) return;
  if (event.key === 'Delete' && editing && editing.id != null) deleteEditing();
});

window.addEventListener('resize', () => { if (autoFit) fitView(); else applyScale(); });

natW = CANVAS[0] || natW;
natH = CANVAS[1] || natH;
const first = rows.find(row => row.depth === 0 && topIds.has(String(row.id)));
if (first) selectLayer(first);
history = [snapshot()];
hIndex = 0;
updateHistoryButtons();
renderAll();
fitView();
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


def render_layer_images(psd_path: Path, out_dir: Path) -> list[dict]:
    """每个顶层图层单独出一张透明 PNG，用来在网页里叠放和开关显隐。"""
    cli = find_engine()
    result = subprocess.run(
        [str(cli), "info", str(psd_path)], capture_output=True, text=True, check=True
    )
    data = json.loads(result.stdout)
    tops = [node for node in data.get("layers") or [] if node.get("name") != "Background"]
    background = next(
        (node for node in data.get("layers") or [] if node.get("name") == "Background"), None
    )
    image_dir = out_dir / "_layers"
    image_dir.mkdir(parents=True, exist_ok=True)
    rendered = []
    for target in tops:
        args = [str(cli), "run", str(psd_path)]
        for other in tops:
            if other.get("id") == target.get("id"):
                continue
            args += ["--cmd", "layer.setProps", "--params",
                     json.dumps({"layer": other.get("id"), "visible": False})]
        if background:
            args += ["--cmd", "layer.setProps", "--params",
                     json.dumps({"layer": background.get("id"), "visible": False})]
        path = image_dir / f"{target.get('id')}.png"
        args += ["--out", str(path)]
        subprocess.run(args, capture_output=True, check=True)
        rendered.append({
            "id": target.get("id"),
            "name": target.get("name") or target.get("kind"),
            "src": "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii"),
        })
    return rendered


def write_review(png_path: Path, psd_path: Path, plan_name: str, out_path: Path) -> Path:
    width, height, layers = read_layers(psd_path)
    tops = render_layer_images(psd_path, out_path.parent)
    html = (
        TEMPLATE
        .replace("__TITLE__", f"{plan_name} 批注")
        .replace("__LAYERS__", json.dumps(layers, ensure_ascii=False))
        .replace("__TOPS__", json.dumps(tops, ensure_ascii=False))
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
