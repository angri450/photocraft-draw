"""透视场景：按针孔相机模型把真实尺寸的几何体投影到画面。

相机站在原点，朝 +Z 看；X 向右，Y 向上，Z 是深度，单位都是米。
投影两条式子：

    sx = 画面中心 + f * X / Z
    sy = 视平线 - f * (Y - 相机高度) / Z

f 是焦距像素。物体按 Z 从大到小画，远的先画，遮挡自然正确。
这一层只负责结构和体块，光影另算。
"""
from __future__ import annotations
import math
import random
from ..commands import Pen
SKY = '#F4EBDF'
GROUND = '#E8DDC4'

def _rgb(value):
    v = str(value).lstrip('#')
    return tuple((int(v[i:i + 2], 16) for i in (0, 2, 4)))

def _hex(color):
    return '#%02X%02X%02X' % tuple((max(0, min(255, round(c))) for c in color))

def _shade(color, k):
    return _hex([c * k for c in _rgb(color)])

def _project(X, Y, Z, cam_h, f, cx, horizon):
    return (cx + f * X / Z, horizon - f * (Y - cam_h) / Z)

def _poly(pen, pts, fill, name):
    pen.path([{'closed': True, 'knots': [[float(x), float(y)] for x, y in pts]}], fill=fill, stroke=None, name=name)

def _box(pen, o, cam_h, f, cx, horizon):
    x, z = (float(o['x']), float(o['z']))
    y0 = float(o.get('y', 0.0))
    w, h, d = (float(o['w']), float(o['h']), float(o.get('d', o['w'])))
    color = o.get('color', '#C9A227')
    x0, x1 = (x - w / 2, x + w / 2)
    z0, z1 = (z - d / 2, z + d / 2)
    P = {}
    for ix, X in enumerate((x0, x1)):
        for iy, Y in enumerate((y0, y0 + h)):
            for iz, Z in enumerate((z0, z1)):
                P[ix, iy, iz] = _project(X, Y, Z, cam_h, f, cx, horizon)
    if x > 0:
        _poly(pen, [P[0, 0, 0], P[0, 1, 0], P[0, 1, 1], P[0, 0, 1]], _shade(color, 0.8), '方块·左侧面')
    elif x < 0:
        _poly(pen, [P[1, 0, 0], P[1, 1, 0], P[1, 1, 1], P[1, 0, 1]], _shade(color, 0.8), '方块·右侧面')
    if cam_h > y0 + h:
        _poly(pen, [P[0, 1, 0], P[1, 1, 0], P[1, 1, 1], P[0, 1, 1]], _shade(color, 1.1), '方块·顶面')
    _poly(pen, [P[0, 0, 0], P[1, 0, 0], P[1, 1, 0], P[0, 1, 0]], color, '方块·正面')

def _sphere(pen, o, cam_h, f, cx, horizon):
    x, z = (float(o['x']), float(o['z']))
    r = float(o['h']) / 2
    color = o.get('color', '#C8455F')
    sx, sy = _project(x, float(o.get('y', 0.0)) + r, z, cam_h, f, cx, horizon)
    rp = f * r / z
    pen.ellipse(sx, sy, rp, rp, fill=color, stroke=None, name='球·亮面')
    pen.ellipse(sx + rp * 0.14, sy + rp * 0.24, rp * 0.66, rp * 0.6, fill=_shade(color, 0.84), stroke=None, name='球·暗面')

def _cylinder(pen, o, cam_h, f, cx, horizon):
    x, z = (float(o['x']), float(o['z']))
    y0 = float(o.get('y', 0.0))
    r, h = (float(o.get('r', 0.4)), float(o['h']))
    color = o.get('color', '#7A9A5B')
    bx, by = _project(x, y0, z, cam_h, f, cx, horizon)
    tx, ty = _project(x, y0 + h, z, cam_h, f, cx, horizon)
    rw = f * r / z
    bh = max(rw * 0.14, min(rw * 0.55, rw * abs(by - horizon) / (f * 0.9)))
    th = max(rw * 0.12, bh * 0.82)
    _poly(pen, [(bx - rw, by), (bx - rw, ty), (tx + rw, ty), (tx + rw, by)], _shade(color, 0.86), '柱·侧面')
    pen.ellipse(bx, by, rw, bh, fill=color, stroke=None, name='柱·底面')
    pen.ellipse(tx, ty, rw, th, fill=_shade(color, 1.1), stroke=None, name='柱·顶面')

def _cone(pen, o, cam_h, f, cx, horizon):
    x, z = (float(o['x']), float(o['z']))
    y0 = float(o.get('y', 0.0))
    r, h = (float(o.get('r', 0.5)), float(o['h']))
    color = o.get('color', '#B3324C')
    bx, by = _project(x, y0, z, cam_h, f, cx, horizon)
    ax, ay = _project(x, y0 + h, z, cam_h, f, cx, horizon)
    rw = f * r / z
    bh = max(rw * 0.14, min(rw * 0.55, rw * abs(by - horizon) / (f * 0.9)))
    _poly(pen, [(bx - rw * 1.04, by), (ax, ay), (bx + rw * 1.04, by)], color, '锥·正面')
    pen.ellipse(bx, by, rw, bh, fill=_shade(color, 0.92), stroke=None, name='锥·底面')

def _tree(pen, o, cam_h, f, cx, horizon):
    """用柱加球拼一棵树，验证几何体能不能组合出具体物件。"""
    x, z = (float(o['x']), float(o['z']))
    th, tr = (float(o.get('trunk_h', 1.6)), float(o.get('trunk_r', 0.12)))
    cr, ch = (float(o.get('crown_r', 0.9)), float(o.get('crown_h', 3.0)))
    bx, by = _project(x, 0, z, cam_h, f, cx, horizon)
    th = max(th, ch - cr * 0.55)
    tx, ty = _project(x, th, z, cam_h, f, cx, horizon)
    rw = f * tr / z
    _poly(pen, [(bx - rw, by), (bx - rw, ty), (tx + rw, ty), (tx + rw, by)], '#6B4A36', '树·干')
    sx, sy = _project(x, ch, z, cam_h, f, cx, horizon)
    crp = f * cr / z
    pen.ellipse(sx, sy, crp, crp * 0.92, fill='#E3AEC4', stroke=None, name='树·冠暗')
    pen.ellipse(sx - crp * 0.2, sy - crp * 0.22, crp * 0.62, crp * 0.55, fill='#F6DCE6', stroke=None, name='树·冠亮')

def _segment(pen, o, cam_h, f, cx, horizon):
    """两点之间的枝条：投影两端，按两端的粗细画成四边形。"""
    a, b = (o['a'], o['b'])
    r0, r1 = (float(o.get('r0', 0.02)), float(o.get('r1', 0.012)))
    color = o.get('color', '#6B4A36')
    ax, ay = _project(float(a[0]), float(a[1]), float(a[2]), cam_h, f, cx, horizon)
    bx, by = _project(float(b[0]), float(b[1]), float(b[2]), cam_h, f, cx, horizon)
    wa, wb = (f * r0 / float(a[2]), f * r1 / float(b[2]))
    dx, dy = (bx - ax, by - ay)
    L = math.hypot(dx, dy) or 1.0
    nx, ny = (-dy / L, dx / L)
    _poly(pen, [(ax + nx * wa, ay + ny * wa), (bx + nx * wb, by + ny * wb), (bx - nx * wb, by - ny * wb), (ax - nx * wa, ay - ny * wa)], color, '枝')

def _leaf(pen, o, cam_h, f, cx, horizon):
    """一片叶：三维里是扁椭球，投影后用旋转椭圆近似。"""
    x, y, z = (float(o['x']), float(o['y']), float(o['z']))
    ln, wd = (float(o.get('length', 0.12)), float(o.get('width', 0.05)))
    ang = float(o.get('angle', 0.0))
    color = o.get('color', '#55703F')
    sx, sy = _project(x, y, z, cam_h, f, cx, horizon)
    rx, ry = (f * ln / z / 2, f * wd / z / 2)
    ca, sa = (math.cos(ang), math.sin(ang))
    pts = []
    for k in range(28):
        t = 2 * math.pi * k / 28
        ex, ey = (math.cos(t) * rx, math.sin(t) * ry)
        pts.append([sx + ex * ca - ey * sa, sy + ex * sa + ey * ca])
    pen.path([{'closed': True, 'knots': pts}], fill=color, stroke=None, name='叶')

def _petal(pen, sx, sy, angle, length, width, color):
    """一片倒卵形花瓣：基部在 (sx, sy)，沿 angle 方向长出 length。

    外端圆、基部窄，顶端中间带一个小凹缺，用六段三次贝塞尔围成。
    """
    ca, sa = (math.cos(angle), math.sin(angle))

    def P(x, y):
        return [sx + x * ca - y * sa, sy + x * sa + y * ca]
    w, L = (width, length)
    knots = [{'anchor': P(0, 0), 'in': P(w * 0.55, 0.06 * L), 'out': P(-w * 0.55, 0.06 * L)}, {'anchor': P(-w, 0.46 * L), 'in': P(-w * 0.6, 0.25 * L), 'out': P(-w * 0.98, 0.8 * L)}, {'anchor': P(-0.34 * w, 0.94 * L), 'in': P(-w * 0.7, 0.98 * L), 'out': P(-w * 0.18, 1.02 * L)}, {'anchor': P(0, 1.0 * L), 'in': P(-w * 0.16, 1.02 * L), 'out': P(w * 0.16, 1.02 * L)}, {'anchor': P(0.34 * w, 0.94 * L), 'in': P(w * 0.18, 1.02 * L), 'out': P(w * 0.7, 0.98 * L)}, {'anchor': P(w, 0.46 * L), 'in': P(w * 0.98, 0.8 * L), 'out': P(w * 0.6, 0.25 * L)}]
    pen.path([{'closed': True, 'knots': knots}], fill=color, stroke_width=2.0, stroke='#A83A52', name='花瓣')

def _flower(pen, o, cam_h, f, cx, horizon):
    """一朵重瓣花：花心一小块深色，外面三层花瓣，外大内小、逐层错开。"""
    x, y, z = (float(o['x']), float(o['y']), float(o['z']))
    r = float(o.get('r', 0.09))
    petal = o.get('color', '#C8455F')
    pale = o.get('mid', '#D25A72')
    heart = o.get('inner', '#B3324C')
    sx, sy = _project(x, y, z, cam_h, f, cx, horizon)
    rp = f * r / z
    tilt = float(o.get('tilt', 0.0))
    rx, ry = (rp, rp * (1.0 - 0.72 * tilt))
    pen.ellipse(sx, sy, rx * 0.16, ry * 0.16, fill=heart, stroke=None, name='花·底')
    rng = random.Random(int(o.get('seed', 1)))
    rings = ((5, 0.06, 0.98, 0.62, petal), (5, 0.04, 0.66, 0.5, pale), (4, 0.02, 0.4, 0.36, heart))
    for ri, (n, base, ln, wd, col) in enumerate(rings):
        off = ri * math.pi / n + rng.uniform(-0.05, 0.05)
        for k in range(n):
            a = off + k * 2 * math.pi / n + rng.uniform(-0.2, 0.2)
            d = base * rng.uniform(0.8, 1.2)
            L = rp * ln * rng.uniform(0.74, 1.1)
            W = rp * wd * rng.uniform(0.8, 1.16)
            _petal(pen, sx + math.cos(a) * rx * d, sy + math.sin(a) * ry * d, a, L, W, col)
    pen.ellipse(sx, sy, rx * 0.08, ry * 0.08, fill='#E8C24A', stroke=None, name='花·蕊')

def _bud(pen, o, cam_h, f, cx, horizon):
    x, y, z = (float(o['x']), float(o['y']), float(o['z']))
    r = float(o.get('r', 0.035))
    color = o.get('color', '#9E2A44')
    sx, sy = _project(x, y, z, cam_h, f, cx, horizon)
    rp = f * r / z
    pen.ellipse(sx, sy, rp * 0.8, rp, fill=color, stroke=None, name='花苞')
BUILDERS = {'box': _box, 'sphere': _sphere, 'cylinder': _cylinder, 'cone': _cone, 'tree': _tree, 'segment': _segment, 'leaf': _leaf, 'flower': _flower, 'bud': _bud}

def build_scene(params, pen):
    with pen.group('场景'):
        w = float(params.get('width', 900))
        h = float(params.get('height', 1200))
        horizon_ratio = float(params.get('horizon', 0.55))
        f = float(params.get('focal', 965))
        cam_h = float(params.get('camera_h', 1.6))
        objects = params.get('objects')
        if not isinstance(objects, (list, tuple)) or not objects:
            raise ValueError('perspective_scene 需要 objects：一组几何体')
        horizon = horizon_ratio * h
        pen.rect(0, 0, w, h, fill=SKY, stroke=None, name='底')
        if params.get('ground', True):
            pen.rect(0, horizon, w, h - horizon, fill=GROUND, stroke=None, name='地')
        ordered = sorted(objects, key=lambda o: -float(o.get('z', 1.0)))
        for i, o in enumerate(ordered):
            kind = str(o.get('type', 'box'))
            if kind not in BUILDERS:
                raise ValueError('第 %d 个物体的类型不认识：%s' % (i + 1, kind))
            BUILDERS[kind](pen, o, cam_h, f, w / 2, horizon)
COMPONENTS = {'perspective_scene': {'name': '透视场景', 'description': '按相机参数把真实尺寸的方块、球、柱、锥、树投影到画面，自动近大远小与遮挡', 'params': {'width': '画面宽，默认 900', 'height': '画面高，默认 1200', 'horizon': '视平线占画高比例，默认 0.55', 'focal': '焦距像素，默认 965，约等于 50 度水平视野', 'camera_h': '相机高度，米，默认 1.6', 'objects': '物体数组，每项含 type、坐标与尺寸；type 取 box / sphere / cylinder / cone / tree / segment / leaf / flower / bud'}, 'build': build_scene}}
__all__ = ['build_scene', 'COMPONENTS']
