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
  --bg: #0f1419; --panel: #161c23; --panel-2: #1d252e; --line: #28323c;
  --text: #e6edf3; --muted: #8b98a5; --accent: #4a9eff;
  --accent-soft: rgba(74,158,255,.14); --warm: #e07a5f; --stage: #0a0e12;
  --ok: #3fb950;
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
button:disabled { opacity: .35; cursor: default; }
button:disabled:hover { border-color: var(--line); }
#app { height: 100vh; display: flex; flex-direction: column; }
header {
  flex: 0 0 56px; display: flex; align-items: center; gap: 18px; padding: 0 18px;
  background: var(--panel); border-bottom: 1px solid var(--line);
}
.brand { display: flex; align-items: center; gap: 10px; min-width: 200px; }
.logo {
  width: 30px; height: 30px; border-radius: 8px; background: var(--accent); color: #fff;
  display: grid; place-items: center; font-weight: 700; font-size: 12px; letter-spacing: .5px;
}
.brand h1 { margin: 0; font-size: 14px; font-weight: 600; }
.brand p { margin: 0; color: var(--muted); font-size: 11px; }
.spacer { flex: 1; }
.tools { display: flex; align-items: center; gap: 6px; }
.tools #zoomLabel { min-width: 48px; text-align: center; color: var(--muted); font-variant-numeric: tabular-nums; }
main { flex: 1; min-height: 0; display: grid; grid-template-columns: 280px minmax(0, 1fr); }
.side { background: var(--panel); border-right: 1px solid var(--line); display: flex; flex-direction: column; min-height: 0; }
.tabs { display: flex; gap: 4px; padding: 10px 12px 0; }
.tab {
  flex: 1; padding: 7px 8px; border: 1px solid transparent; border-bottom: 2px solid transparent;
  background: transparent; border-radius: 6px 6px 0 0; color: var(--muted);
}
.tab.active { color: var(--text); border-bottom-color: var(--accent); background: var(--panel-2); }
.tab .count { display: inline-block; min-width: 16px; padding: 0 4px; margin-left: 4px; border-radius: 8px; background: var(--warm); color: #fff; font-size: 10px; line-height: 16px; }
.side .search { margin: 10px 12px 6px; padding: 8px 10px; border-radius: 7px; border: 1px solid var(--line); background: var(--bg); color: var(--text); outline: none; }
.side .search:focus { border-color: var(--accent); }
#layerPane, #notePane { flex: 1; min-height: 0; overflow: auto; padding: 6px 8px 16px; }
.row {
  display: flex; align-items: center; gap: 6px; height: 28px; padding: 0 8px;
  border-radius: 6px; cursor: pointer; white-space: nowrap; user-select: none;
}
.row:hover, .row.hover { background: var(--panel-2); }
.row.active { background: var(--accent-soft); box-shadow: inset 0 0 0 1px var(--accent); }
.row .twist { width: 12px; flex: 0 0 12px; color: var(--muted); font-size: 9px; text-align: center; }
.row .name { flex: 1; overflow: hidden; text-overflow: ellipsis; }
.row .badge { flex: 0 0 auto; font-size: 10px; color: var(--muted); border: 1px solid var(--line); border-radius: 4px; padding: 0 4px; }
.row .dot { flex: 0 0 auto; width: 6px; height: 6px; border-radius: 50%; background: var(--warm); }
.workspace { min-width: 0; min-height: 0; display: flex; flex-direction: column; }
#stage {
  flex: 1; min-height: 0; min-width: 0; background: var(--stage); overflow: auto;
  display: flex; padding: 24px; position: relative;
}
#wrap { position: relative; flex: 0 0 auto; margin: auto; box-shadow: 0 8px 40px rgba(0,0,0,.35); }
#img { display: block; max-width: none; cursor: crosshair; }
#hover { position: absolute; border: 1px dashed var(--accent); background: rgba(74,158,255,.06); display: none; pointer-events: none; }
#hoverName {
  position: absolute; display: none; pointer-events: none; font-size: 10px; color: #fff;
  background: var(--accent); padding: 1px 6px; border-radius: 3px; white-space: nowrap;
}
#box {
  position: absolute; border: 2px solid var(--warm); background: rgba(224,122,95,.10);
  display: none; cursor: move; box-shadow: 0 0 0 1px rgba(0,0,0,.25);
}
#box::after {
  content: "拖动"; position: absolute; top: -20px; left: -2px; font-size: 10px;
  color: #fff; background: var(--warm); padding: 1px 6px; border-radius: 3px;
}
.pin {
  position: absolute; width: 20px; height: 20px; border-radius: 50%;
  background: var(--warm); color: #fff; font-size: 11px; font-weight: 600;
  display: grid; place-items: center; transform: translate(-50%, -50%);
  cursor: pointer; box-shadow: 0 2px 8px rgba(0,0,0,.4); border: 2px solid rgba(255,255,255,.85);
  z-index: 5;
}
.pin:hover { filter: brightness(1.1); }
#hint {
  position: absolute; left: 50%; bottom: 14px; transform: translateX(-50%);
  color: var(--muted); font-size: 11px; background: rgba(10,14,18,.72);
  padding: 4px 10px; border-radius: 12px; pointer-events: none;
}
#composer {
  flex: 0 0 auto; background: var(--panel); border-top: 1px solid var(--line);
  padding: 10px 18px 12px; display: none;
}
#composer.open { display: block; }
.composer-head { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.composer-head strong { font-size: 13px; }
.composer-head .badge { font-size: 10px; color: var(--muted); border: 1px solid var(--line); border-radius: 4px; padding: 0 5px; }
.composer-head .grow { flex: 1; }
.chips { display: flex; gap: 6px; margin-bottom: 8px; flex-wrap: wrap; }
.chip {
  padding: 3px 10px; border-radius: 12px; border: 1px solid var(--line);
  background: transparent; color: var(--muted); font-size: 12px;
}
.chip.active { background: var(--warm); border-color: var(--warm); color: #fff; }
.composer textarea {
  width: 100%; min-height: 48px; max-height: 120px; resize: vertical;
  border: 1px solid var(--line); background: var(--bg); color: var(--text);
  border-radius: 7px; padding: 8px 10px; outline: none;
}
.composer textarea:focus { border-color: var(--accent); }
.composer-foot { display: flex; align-items: center; gap: 8px; margin-top: 8px; }
.composer-foot .muted { flex: 1; color: var(--muted); font-size: 11px; }
.note-item {
  padding: 8px 10px; border: 1px solid var(--line); border-radius: 7px;
  margin-bottom: 6px; cursor: pointer; background: var(--panel-2);
}.note-item:hover { border-color: var(--accent); }
.note-item .head { display: flex; align-items: center; gap: 6px; }
.note-item .index { color: #fff; background: var(--warm); border-radius: 50%; width: 16px; height: 16px; font-size: 10px; display: grid; place-items: center; }
.note-item .name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.note-item .del { border: none; background: transparent; color: var(--muted); padding: 0 4px; }
.note-item .body { color: var(--muted); font-size: 11px; margin-top: 3px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.empty { color: var(--muted); text-align: center; padding: 30px 12px; font-size: 12px; }
.global-label { display: block; margin: 6px 2px 4px; color: var(--muted); font-size: 11px; }
.global-note {
  width: 100%; min-height: 56px; border: 1px solid var(--line); background: var(--bg);
  color: var(--text); border-radius: 7px; padding: 8px 10px; margin-bottom: 10px; resize: vertical;
}
.global-note:focus { border-color: var(--accent); outline: none; }
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
@media (max-width: 1100px) { main { grid-template-columns: 240px minmax(0, 1fr); } }
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
        <button class="tab" data-tab="notes">意见 <span id="noteCount" class="count">0</span></button>
      </div>
      <input id="search" class="search" placeholder="搜图层名">
      <div id="layerPane"><div id="list"></div></div>
      <div id="notePane" hidden>
        <label class="global-label">整体意见</label>
        <textarea id="globalNote" class="global-note" placeholder="整张图的意见"></textarea>
        <div id="notes"></div>
      </div>
    </aside>
    <div class="workspace">
      <section id="stage">
        <div id="wrap">
          <img id="img" alt="画面">
          <div id="hover"></div><div id="hoverName"></div>
          <div id="box"></div>
          <div id="pins"></div>
        </div>
        <div id="hint">点画面选图层，拖方框移动</div>
      </section>
      <div id="composer">
        <div class="composer-head">
          <strong id="compName"></strong><span id="compKind" class="badge"></span>
          <span class="grow"></span>
          <button id="compClose" title="关闭">×</button>
        </div>
        <div class="chips">
          <button class="chip active" data-action="move">移动</button>
          <button class="chip" data-action="note">备注</button>
          <button class="chip" data-action="hide">隐藏</button>
          <button class="chip" data-action="delete">删除</button>
          <button class="chip" data-action="recolor">改色</button>
          <button class="chip" data-action="retext">改字</button>
        </div>
        <textarea id="compNote" placeholder="这个图层要怎么改？写清楚就行，不用管格式。"></textarea>
        <div class="composer-foot">
          <span class="muted" id="compOffset">没有位移</span>
          <button id="compReset">复位位移</button>
          <button id="compDone" class="primary">完成</button>
        </div>
      </div>
    </div>
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
const notesBox = document.getElementById('notes');
const search = document.getElementById('search');
const img = document.getElementById('img');
const wrap = document.getElementById('wrap');
const stage = document.getElementById('stage');
const box = document.getElementById('box');
const hover = document.getElementById('hover');
const hoverName = document.getElementById('hoverName');
const pins = document.getElementById('pins');
const hint = document.getElementById('hint');
const composer = document.getElementById('composer');
const compName = document.getElementById('compName');
const compKind = document.getElementById('compKind');
const compNote = document.getElementById('compNote');
const compOffset = document.getElementById('compOffset');
const globalNote = document.getElementById('globalNote');
const noteCount = document.getElementById('noteCount');
const zoomLabel = document.getElementById('zoomLabel');
const meta = document.getElementById('meta');
const modal = document.getElementById('modal');
const jsonOut = document.getElementById('jsonOut');
const root = document.documentElement;

const rows = LAYERS.map((layer, index) => ({ ...layer, index }));
const collapsed = new Set();
const edits = new Map();
let selected = null;
let hovered = null;
let natW = CANVAS[0] || 1600;
let natH = CANVAS[1] || 900;
let scale = 1;
let autoFit = true;
let history = [];
let hIndex = -1;
let action = 'move';

const KIND = { Group: '组', Shape: '形状', Type: '文字', Pixel: '像素' };
const ACTION = { move: '移动', note: '备注', hide: '隐藏', delete: '删除', recolor: '改色', retext: '改字' };

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
function annotated(layer) {
  const item = edits.get(layer.id);
  return Boolean(item && (item.note || item.action !== 'move' || item.dx || item.dy));
}

function renderList() {
  const query = search.value.trim().toLowerCase();
  list.innerHTML = '';
  rows.forEach((layer, index) => {
    if (!query && isHidden(index)) return;
    if (query && !layer.name.toLowerCase().includes(query)) return;
    const row = document.createElement('div');
    row.className = 'row' + (selected && selected.id === layer.id ? ' active' : '')
      + (hovered && hovered.id === layer.id ? ' hover' : '');
    row.style.paddingLeft = (8 + layer.depth * 14) + 'px';
    row.dataset.id = layer.id;
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
    if (annotated(layer)) {
      const dot = document.createElement('span');
      dot.className = 'dot';
      row.append(twist, name, dot, badge);
    } else {
      row.append(twist, name, badge);
    }
    row.title = layer.name + ' · ' + (KIND[layer.kind] || layer.kind);
    row.onclick = () => selectLayer(layer);
    row.onmouseenter = () => setHover(layer);
    row.onmouseleave = () => setHover(null);
    list.appendChild(row);
  });
}

function renderNotes() {
  const entries = Array.from(edits.values()).filter(item => item.note || item.action !== 'move' || item.dx || item.dy);
  noteCount.textContent = String(entries.length);
  notesBox.innerHTML = '';
  if (!entries.length) {
    notesBox.innerHTML = '<div class="empty">还没有意见。<br>点画面上的元素，选个动作，写一句就行。</div>';
    return;
  }
  entries.forEach((item, index) => {
    const node = document.createElement('div');
    node.className = 'note-item';
    const head = document.createElement('div');
    head.className = 'head';
    const badge = document.createElement('span');
    badge.className = 'index';
    badge.textContent = String(index + 1);
    const name = document.createElement('span');
    name.className = 'name';
    name.textContent = item.name;
    const actionLabel = document.createElement('span');
    actionLabel.className = 'badge';
    actionLabel.textContent = ACTION[item.action] || item.action;
    const del = document.createElement('button');
    del.className = 'del';
    del.textContent = '×';
    del.title = '删掉这条意见';
    del.onclick = event => {
      event.stopPropagation();
      pushHistory();
      edits.delete(item.layer);
      if (selected && selected.id === item.layer) fillComposer();
      renderAll();
    };
    head.append(badge, name, actionLabel, del);
    node.appendChild(head);
    if (item.note) {
      const body = document.createElement('div');
      body.className = 'body';
      body.textContent = item.note;
      node.appendChild(body);
    }
    node.onclick = () => {
      const layer = rows.find(row => row.id === item.layer);
      if (layer) { selectLayer(layer); revealLayer(layer); }
    };
    notesBox.appendChild(node);
  });
}

function renderPins() {
  pins.innerHTML = '';
  const entries = Array.from(edits.values()).filter(item => item.note || item.action !== 'move' || item.dx || item.dy);
  entries.forEach((item, index) => {
    const layer = rows.find(row => row.id === item.layer);
    if (!layer || !layer.bounds) return;
    const [x, y, w] = layer.bounds;
    const pin = document.createElement('div');
    pin.className = 'pin';
    pin.textContent = String(index + 1);
    pin.style.left = ((x + w + (item.dx || 0)) * scale) + 'px';
    pin.style.top = ((y + (item.dy || 0)) * scale) + 'px';
    pin.title = item.name;
    pin.onclick = event => { event.stopPropagation(); selectLayer(layer); };
    pins.appendChild(pin);
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

function setHover(layer) {
  hovered = layer;
  if (!layer || !layer.bounds) {
    hover.style.display = 'none';
    hoverName.style.display = 'none';
  } else {
    const [x, y, w, h] = layer.bounds;
    hover.style.display = 'block';
    hover.style.left = (x * scale) + 'px';
    hover.style.top = (y * scale) + 'px';
    hover.style.width = Math.max(1, w * scale) + 'px';
    hover.style.height = Math.max(1, h * scale) + 'px';
    hoverName.style.display = 'block';
    hoverName.textContent = layer.name;
    hoverName.style.left = (x * scale) + 'px';
    hoverName.style.top = Math.max(0, y * scale - 20) + 'px';
  }
  document.querySelectorAll('.row').forEach(row => {
    row.classList.toggle('hover', Boolean(layer) && row.dataset.id === String(layer.id));
  });
}

function selectLayer(layer) {
  selected = layer;
  action = 'move';
  const item = editOf(layer);
  action = item.action || 'move';
  compName.textContent = layer.name;
  compKind.textContent = KIND[layer.kind] || layer.kind || '';
  compNote.value = item.note || '';
  document.querySelectorAll('.chip').forEach(chip => chip.classList.toggle('active', chip.dataset.action === action));
  updateOffset();
  composer.classList.add('open');
  hint.style.display = 'none';
  placeBox();
  renderList();
  if (autoFit) requestAnimationFrame(fitView); else applyScale();
  revealLayer(layer);
}

function revealLayer(layer) {
  const row = document.querySelector('.row[data-id="' + layer.id + '"]');
  if (row) row.scrollIntoView({ block: 'nearest' });
}

function deselect() {
  selected = null;
  box.style.display = 'none';
  composer.classList.remove('open');
  hint.style.display = 'block';
  setHover(null);
  renderList();
  if (autoFit) requestAnimationFrame(fitView); else applyScale();
}

function updateOffset() {
  if (!selected) { compOffset.textContent = '没有位移'; return; }
  const item = edits.get(selected.id) || { dx: 0, dy: 0 };
  compOffset.textContent = item.dx || item.dy ? ('位移 ' + (item.dx || 0) + ', ' + (item.dy || 0)) : '没有位移';
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

function fitView() {
  const pad = 48;
  const width = Math.max(80, stage.clientWidth - pad);
  const height = Math.max(80, stage.clientHeight - pad);
  scale = Math.max(0.05, Math.min(3, Math.min(width / natW, height / natH)));
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
  renderPins();
  if (hovered) setHover(hovered);
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

img.addEventListener('mousemove', event => {
  if (drag) return;
  const rect = img.getBoundingClientRect();
  const layer = hitTest((event.clientX - rect.left) / scale, (event.clientY - rect.top) / scale);
  if (!layer) { setHover(null); return; }
  if (!hovered || hovered.id !== layer.id) setHover(layer);
});
img.addEventListener('mouseleave', () => { if (!drag) setHover(null); });
img.addEventListener('click', event => {
  const rect = img.getBoundingClientRect();
  const layer = hitTest((event.clientX - rect.left) / scale, (event.clientY - rect.top) / scale);
  if (layer) selectLayer(layer); else deselect();
});

document.querySelectorAll('.tab').forEach(tab => {
  tab.onclick = () => {
    document.querySelectorAll('.tab').forEach(item => item.classList.toggle('active', item === tab));
    const showNotes = tab.dataset.tab === 'notes';
    document.getElementById('layerPane').hidden = showNotes;
    document.getElementById('notePane').hidden = !showNotes;
    search.style.display = showNotes ? 'none' : 'block';
  };
});

document.querySelectorAll('.chip').forEach(chip => {
  chip.onclick = () => {
    if (!selected) return;
    pushHistory();
    action = chip.dataset.action;
    const item = editOf(selected);
    item.action = action;
    document.querySelectorAll('.chip').forEach(other => other.classList.toggle('active', other === chip));
    renderAll();
  };
});

compNote.addEventListener('input', () => {
  if (!selected) return;
  editOf(selected).note = compNote.value;
  renderNotes();
  renderPins();
  renderList();
});

document.getElementById('compDone').onclick = () => { pushHistory(); deselect(); };
document.getElementById('compClose').onclick = () => deselect();
document.getElementById('compReset').onclick = () => {
  if (!selected) return;
  pushHistory();
  const item = editOf(selected);
  item.dx = 0;
  item.dy = 0;
  updateOffset();
  placeBox();
  renderPins();
};

let drag = null;
box.addEventListener('mousedown', event => {
  if (!selected || !selected.bounds) return;
  event.preventDefault();
  event.stopPropagation();
  const item = editOf(selected);
  item.action = 'move';
  action = 'move';
  document.querySelectorAll('.chip').forEach(chip => chip.classList.toggle('active', chip.dataset.action === 'move'));
  drag = { x: event.clientX, y: event.clientY, dx: item.dx || 0, dy: item.dy || 0, moved: false };
});
window.addEventListener('mousemove', event => {
  if (!drag || !selected) return;
  const item = editOf(selected);
  const dx = Math.round(drag.dx + (event.clientX - drag.x) / scale);
  const dy = Math.round(drag.dy + (event.clientY - drag.y) / scale);
  if (dx !== item.dx || dy !== item.dy) {
    drag.moved = true;
    item.dx = dx;
    item.dy = dy;
    updateOffset();
    placeBox();
    renderPins();
    renderNotes();
    renderList();
  }
});
window.addEventListener('mouseup', () => {
  if (drag && drag.moved) pushHistory();
  drag = null;
});

function snapshot() { return JSON.stringify(Array.from(edits.entries())); }
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
  edits.clear();
  JSON.parse(snap).forEach(([id, item]) => edits.set(id, item));
  renderAll();
  if (selected) {
    const item = edits.get(selected.id);
    compNote.value = item ? item.note : '';
    updateOffset();
    placeBox();
  }
}
function undo() { if (hIndex > 0) { hIndex -= 1; restore(history[hIndex]); updateHistoryButtons(); } }
function redo() { if (hIndex < history.length - 1) { hIndex += 1; restore(history[hIndex]); updateHistoryButtons(); } }
function updateHistoryButtons() {
  document.getElementById('undo').disabled = hIndex <= 0;
  document.getElementById('redo').disabled = hIndex >= history.length - 1;
}
document.getElementById('undo').onclick = undo;
document.getElementById('redo').onclick = redo;

function renderAll() { renderList(); renderNotes(); renderPins(); }

function payload() {
  return {
    plan: PLAN_NAME,
    image: IMAGE_NAME,
    canvas: CANVAS,
    edits: Array.from(edits.values()).filter(item => item.note || item.action !== 'move' || item.dx || item.dy),
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
    else if (selected) deselect();
    return;
  }
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'z') {
    event.preventDefault();
    if (event.shiftKey) redo(); else undo();
    return;
  }
  if (!selected || !composer.classList.contains('open')) return;
  if (event.target === compNote) return;
  const step = event.shiftKey ? 10 : 1;
  const item = edits.get(selected.id);
  if (!item) return;
  if (event.key === 'ArrowLeft') { item.dx = (item.dx || 0) - step; }
  else if (event.key === 'ArrowRight') { item.dx = (item.dx || 0) + step; }
  else if (event.key === 'ArrowUp') { item.dy = (item.dy || 0) - step; }
  else if (event.key === 'ArrowDown') { item.dy = (item.dy || 0) + step; }
  else return;
  event.preventDefault();
  item.action = 'move';
  updateOffset();
  placeBox();
  renderPins();
  renderNotes();
  renderList();
});

window.addEventListener('resize', () => { if (autoFit) fitView(); else applyScale(); });

img.onload = () => {
  natW = img.naturalWidth || CANVAS[0];
  natH = img.naturalHeight || CANVAS[1];
  fitView();
};
img.src = IMAGE_SRC;

history = [snapshot()];
hIndex = 0;
updateHistoryButtons();
renderAll();
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
