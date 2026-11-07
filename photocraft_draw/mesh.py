# -*- coding: utf-8 -*-
"""网格渲染管线：顶点、变换矩阵、相机投影、面排序和背面剔除。

世界坐标定死：x 向右，y 向上，z 越大离观众越远。相机默认站在 -z，
沿 +z 看过去，所以画面上的 x 和世界 x 同向。

一条渲染链分五步，和蓝图 4.1 一致：
    1. 顶点乘变换矩阵，从模型坐标进世界坐标；
    2. 顶点乘相机基，进相机坐标；
    3. 透视先按近平面裁剪，再除以深度；正交只乘比例；
    4. 面法向量朝着相机才留，背对相机的剔掉；
    5. 按面中心深度从远到近排好，逐个画成多边形。

面法向量用 Newell 方法算，多边形不共面也不会算出零向量。顶点顺序定死：
从外面看过去逆时针，法向量朝外。图元生成器会自动把顺序翻正，手写网格
要自己保证。

用法有两种。写方案时把整个场景交给 `build`：

    {"component": "mesh_scene",
     "params": {"meshes": [...], "camera": {...}, "lighting": {...}}}

写代码时直接用渲染器：

    from photocraft_draw.mesh import Camera, make_box, render
    stats = render([make_box()], Camera(), pen)

公开的接口：
    Mesh / Camera / Projection          数据结构
    identity / matmul / translation      矩阵
    rotation_x / rotation_y / rotation_z
    scaling / compose_transform / apply_matrix
    make_box / make_sphere / make_cylinder / make_cone
    make_capsule / make_lathe / sweep     花苞、瓶罐、枝条
    bounds / is_watertight               顶点数、面数、包围盒和封闭检查
    subdivide                            Catmull-Clark 细分，低面数曲面变顺
    mesh_from_dict / camera_from_dict    方案参数转对象
    face_center / face_normal / shade_color
    project_points                       一组点投到画面
    clip_near                            按近平面切多边形，透视前用
    render / build                       渲染
    ortho_views / view_camera            三视图的正交相机
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable, Sequence

from .commands import Pen
from .palette import color_of

Point = tuple[float, float, float]
Matrix = list[list[float]]

PROJECTIONS = ("perspective", "ortho")
PRIMITIVES = ("mesh", "box", "sphere", "cylinder", "cone", "capsule", "lathe", "sweep")

# 透视时深度小于这个数的点算在相机后面
NEAR_PLANE = 0.001

# 平涂时颜色不动；开了光照也不许掉到死黑
MIN_BRIGHTNESS = 0.30
MAX_BRIGHTNESS = 1.20


# ------------------------------------------------------------------ 向量和矩阵

def _vec3(value, label: str, default: Point | None = None) -> Point:
    if value is None:
        if default is None:
            raise ValueError(f"{label} 必须给三个数：[x, y, z]")
        return default
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError(f"{label} 必须是 [x, y, z] 三个数")
    result = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise ValueError(f"{label} 的三个值必须是数字")
        result.append(float(item))
    return (result[0], result[1], result[2])


def _num(value, label: str, default: float | None = None, minimum: float | None = None,
         strict: bool = True) -> float:
    if value is None:
        if default is None:
            raise ValueError(f"{label} 必须给一个数字")
        return float(default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} 必须是数字")
    number = float(value)
    if minimum is not None:
        if strict and number <= minimum:
            raise ValueError(f"{label} 必须大于 {minimum:g}")
        if not strict and number < minimum:
            raise ValueError(f"{label} 不能小于 {minimum:g}")
    return number


def _sub(a: Point, b: Point) -> Point:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _mul(a: Point, factor: float) -> Point:
    return (a[0] * factor, a[1] * factor, a[2] * factor)


def _dot(a: Point, b: Point) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Point, b: Point) -> Point:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _length(a: Point) -> float:
    return math.sqrt(_dot(a, a))


def _unit(a: Point, label: str = "向量") -> Point:
    size = _length(a)
    if size < 1e-9:
        raise ValueError(f"{label} 长度是 0，没法定方向")
    return (a[0] / size, a[1] / size, a[2] / size)


def _rotate_about(vector: Point, axis: Point, angle: float) -> Point:
    """把向量绕单位轴转一个角度，用罗德里格公式，扫掠时逐点转截面。"""
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    turned = _cross(axis, vector)
    along = _dot(axis, vector) * (1.0 - cos_a)
    return (
        vector[0] * cos_a + turned[0] * sin_a + axis[0] * along,
        vector[1] * cos_a + turned[1] * sin_a + axis[1] * along,
        vector[2] * cos_a + turned[2] * sin_a + axis[2] * along,
    )


def _first_frame(tangent: Point) -> tuple[Point, Point]:
    """给切线配一个起始截面基 (u, v)，满足 u × v 等于切线。"""
    helper = (0.0, 1.0, 0.0)
    if abs(_dot(tangent, helper)) > 0.9:
        helper = (1.0, 0.0, 0.0)
    u = _unit(_cross(tangent, helper), "扫掠方向")
    return u, _cross(tangent, u)


def identity() -> Matrix:
    return [[1.0 if row == col else 0.0 for col in range(4)] for row in range(4)]


def matmul(a: Matrix, b: Matrix) -> Matrix:
    return [
        [sum(a[row][k] * b[k][col] for k in range(4)) for col in range(4)]
        for row in range(4)
    ]


def translation(offset: Point) -> Matrix:
    matrix = identity()
    matrix[0][3], matrix[1][3], matrix[2][3] = offset
    return matrix


def scaling(scale: Point) -> Matrix:
    return [
        [scale[0], 0.0, 0.0, 0.0],
        [0.0, scale[1], 0.0, 0.0],
        [0.0, 0.0, scale[2], 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]


def rotation_x(degrees: float) -> Matrix:
    angle = math.radians(float(degrees))
    cos, sin = math.cos(angle), math.sin(angle)
    return [
        [1.0, 0.0, 0.0, 0.0],
        [0.0, cos, -sin, 0.0],
        [0.0, sin, cos, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]


def rotation_y(degrees: float) -> Matrix:
    angle = math.radians(float(degrees))
    cos, sin = math.cos(angle), math.sin(angle)
    return [
        [cos, 0.0, sin, 0.0],
        [0.0, 1.0, 0.0, 0.0],
        [-sin, 0.0, cos, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]


def rotation_z(degrees: float) -> Matrix:
    angle = math.radians(float(degrees))
    cos, sin = math.cos(angle), math.sin(angle)
    return [
        [cos, -sin, 0.0, 0.0],
        [sin, cos, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]


def compose_transform(transform: dict | None) -> Matrix:
    """把 translate / rotate / scale 合成一个矩阵。

    先缩放，再绕 x、y、z 依次转，最后平移；rotate 写的是角度。
    """
    if transform is None:
        transform = {}
    if not isinstance(transform, dict):
        raise ValueError("transform 必须是对象，可以写 translate、rotate、scale")
    move = _vec3(transform.get("translate"), "transform.translate", (0.0, 0.0, 0.0))
    turn = _vec3(transform.get("rotate"), "transform.rotate", (0.0, 0.0, 0.0))
    size = _vec3(transform.get("scale"), "transform.scale", (1.0, 1.0, 1.0))

    matrix = translation(move)
    matrix = matmul(matrix, rotation_z(turn[2]))
    matrix = matmul(matrix, rotation_y(turn[1]))
    matrix = matmul(matrix, rotation_x(turn[0]))
    matrix = matmul(matrix, scaling(size))
    return matrix


def apply_matrix(matrix: Matrix, point: Point) -> Point:
    x, y, z = point
    return (
        matrix[0][0] * x + matrix[0][1] * y + matrix[0][2] * z + matrix[0][3],
        matrix[1][0] * x + matrix[1][1] * y + matrix[1][2] * z + matrix[1][3],
        matrix[2][0] * x + matrix[2][1] * y + matrix[2][2] * z + matrix[2][3],
    )


def transform_point(transform: dict | None, point: Point) -> Point:
    return apply_matrix(compose_transform(transform), point)


def transform_points(transform: dict | None, points: Iterable[Point]) -> list[Point]:
    matrix = compose_transform(transform)
    return [apply_matrix(matrix, point) for point in points]


# ------------------------------------------------------------------ 面

def face_center(points: Sequence[Point]) -> Point:
    if not points:
        raise ValueError("空多边形没有中心")
    total = [0.0, 0.0, 0.0]
    for point in points:
        total[0] += point[0]
        total[1] += point[1]
        total[2] += point[2]
    count = float(len(points))
    return (total[0] / count, total[1] / count, total[2] / count)


def face_normal(points: Sequence[Point]) -> Point:
    """Newell 法算面法向量，返回单位向量；多边形退化时返回零向量。"""
    if len(points) < 3:
        return (0.0, 0.0, 0.0)
    nx = ny = nz = 0.0
    for index, current in enumerate(points):
        following = points[(index + 1) % len(points)]
        nx += (current[1] - following[1]) * (current[2] + following[2])
        ny += (current[2] - following[2]) * (current[0] + following[0])
        nz += (current[0] - following[0]) * (current[1] + following[1])
    normal = (nx, ny, nz)
    size = _length(normal)
    if size < 1e-12:
        return (0.0, 0.0, 0.0)
    return (normal[0] / size, normal[1] / size, normal[2] / size)


def _orient_outward(vertices: list[Point], faces: list[list[int]], center: Point) -> list[list[int]]:
    """把每个面的顶点顺序翻成法向量朝外，图元生成器都走这一步。"""
    for face in faces:
        points = [vertices[index] for index in face]
        normal = face_normal(points)
        if _dot(normal, _sub(face_center(points), center)) < 0:
            face.reverse()
    return faces


# ------------------------------------------------------------------ 网格

@dataclass
class Mesh:
    """一块网格。vertices 是三维点，faces 是顶点下标，color 写角色名或十六进制。"""

    vertices: list[Point] = field(default_factory=list)
    faces: list[list[int]] = field(default_factory=list)
    color: str = "mid"
    name: str = "网格"
    transform: dict = field(default_factory=dict)
    cull: bool = True

    def matrix(self) -> Matrix:
        return compose_transform(self.transform)

    def world_vertices(self) -> list[Point]:
        matrix = self.matrix()
        return [apply_matrix(matrix, point) for point in self.vertices]

    def validate(self) -> "Mesh":
        if not isinstance(self.vertices, (list, tuple)) or not self.vertices:
            raise ValueError(f"网格 {self.name} 需要 vertices：一组三维点")
        if not isinstance(self.faces, (list, tuple)) or not self.faces:
            raise ValueError(f"网格 {self.name} 需要 faces：一组顶点下标")
        total = len(self.vertices)
        clean = []
        for index, point in enumerate(self.vertices):
            if not isinstance(point, (list, tuple)) or len(point) != 3:
                raise ValueError(f"网格 {self.name} 第 {index + 1} 个顶点要写成 [x, y, z]")
            for value in point:
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise ValueError(f"网格 {self.name} 第 {index + 1} 个顶点必须是数字")
        for index, face in enumerate(self.faces):
            if not isinstance(face, (list, tuple)) or len(face) < 3:
                raise ValueError(f"网格 {self.name} 第 {index + 1} 个面至少三个顶点")
            corners = []
            for corner in face:
                if isinstance(corner, bool) or not isinstance(corner, int):
                    raise ValueError(f"网格 {self.name} 第 {index + 1} 个面的顶点下标必须是整数")
                if corner < 0 or corner >= total:
                    raise ValueError(
                        f"网格 {self.name} 第 {index + 1} 个面的下标 {corner} 超出范围，共 {total} 个顶点"
                    )
                corners.append(corner)
            if len(set(corners)) < 3:
                raise ValueError(f"网格 {self.name} 第 {index + 1} 个面不足三个不同的顶点")
            clean.append(corners)
        self.vertices = [
            (float(point[0]), float(point[1]), float(point[2])) for point in self.vertices
        ]
        self.faces = clean
        if not isinstance(self.color, str) or not self.color:
            raise ValueError(f"网格 {self.name} 的 color 必须是角色名或 #rrggbb")
        if self.transform is None:
            self.transform = {}
        if not isinstance(self.transform, dict):
            raise ValueError(f"网格 {self.name} 的 transform 必须是对象")
        return self


# ------------------------------------------------------------------ 图元

def make_box(width: float = 1.0, height: float = 1.0, depth: float = 1.0,
             center: Point = (0.0, 0.0, 0.0), color: str = "mid",
             name: str = "盒子") -> Mesh:
    """立方体：八个顶点六个面。"""
    half_w = _num(width, "width", 1.0, 0) / 2
    half_h = _num(height, "height", 1.0, 0) / 2
    half_d = _num(depth, "depth", 1.0, 0) / 2
    cx, cy, cz = _vec3(center, "center", (0.0, 0.0, 0.0))
    vertices = [
        (cx - half_w, cy - half_h, cz - half_d),
        (cx + half_w, cy - half_h, cz - half_d),
        (cx + half_w, cy + half_h, cz - half_d),
        (cx - half_w, cy + half_h, cz - half_d),
        (cx - half_w, cy - half_h, cz + half_d),
        (cx + half_w, cy - half_h, cz + half_d),
        (cx + half_w, cy + half_h, cz + half_d),
        (cx - half_w, cy + half_h, cz + half_d),
    ]
    faces = [
        [0, 1, 2, 3],
        [4, 5, 6, 7],
        [0, 1, 5, 4],
        [3, 2, 6, 7],
        [1, 2, 6, 5],
        [0, 3, 7, 4],
    ]
    _orient_outward(vertices, faces, (cx, cy, cz))
    return Mesh(vertices, faces, color, name)


def make_sphere(radius: float = 1.0, segments: int = 16, rings: int = 8,
                center: Point = (0.0, 0.0, 0.0), color: str = "mid",
                name: str = "球") -> Mesh:
    """经纬球：上下两个极点，中间 rings-1 圈顶点。"""
    radius = _num(radius, "radius", 1.0, 0)
    segments = int(_num(segments, "segments", 16, 2))
    rings = int(_num(rings, "rings", 8, 1))
    cx, cy, cz = _vec3(center, "center", (0.0, 0.0, 0.0))

    vertices: list[Point] = [(cx, cy + radius, cz)]
    for ring in range(1, rings):
        theta = math.pi * ring / rings
        level = cy + radius * math.cos(theta)
        spread = radius * math.sin(theta)
        for segment in range(segments):
            phi = 2.0 * math.pi * segment / segments
            vertices.append((cx + spread * math.cos(phi), level, cz + spread * math.sin(phi)))
    vertices.append((cx, cy - radius, cz))
    bottom = len(vertices) - 1

    def at(ring: int, segment: int) -> int:
        return 1 + (ring - 1) * segments + (segment % segments)

    faces: list[list[int]] = []
    for segment in range(segments):
        faces.append([0, at(1, segment), at(1, segment + 1)])
    for ring in range(1, rings - 1):
        for segment in range(segments):
            faces.append([
                at(ring, segment), at(ring + 1, segment),
                at(ring + 1, segment + 1), at(ring, segment + 1),
            ])
    for segment in range(segments):
        faces.append([bottom, at(rings - 1, segment + 1), at(rings - 1, segment)])
    _orient_outward(vertices, faces, (cx, cy, cz))
    return Mesh(vertices, faces, color, name)


def make_cylinder(radius: float = 1.0, height: float = 1.0, segments: int = 16,
                  center: Point = (0.0, 0.0, 0.0), caps: bool = True,
                  color: str = "mid", name: str = "柱") -> Mesh:
    """圆柱：上下两圈顶点，侧面是四边形，两端可选封盖。"""
    radius = _num(radius, "radius", 1.0, 0)
    height = _num(height, "height", 1.0, 0)
    segments = int(_num(segments, "segments", 16, 2))
    cx, cy, cz = _vec3(center, "center", (0.0, 0.0, 0.0))
    half = height / 2.0

    vertices: list[Point] = []
    for level in (cy - half, cy + half):
        for segment in range(segments):
            phi = 2.0 * math.pi * segment / segments
            vertices.append((cx + radius * math.cos(phi), level, cz + radius * math.sin(phi)))

    faces: list[list[int]] = []
    for segment in range(segments):
        lower = segment
        upper = segments + segment
        next_lower = (segment + 1) % segments
        next_upper = segments + (segment + 1) % segments
        faces.append([lower, next_lower, next_upper, upper])
    if caps:
        bottom_center = len(vertices)
        vertices.append((cx, cy - half, cz))
        top_center = len(vertices)
        vertices.append((cx, cy + half, cz))
        for segment in range(segments):
            following = (segment + 1) % segments
            faces.append([bottom_center, segment, following])
            faces.append([top_center, segments + following, segments + segment])
    _orient_outward(vertices, faces, (cx, cy, cz))
    return Mesh(vertices, faces, color, name)


def make_cone(radius: float = 1.0, height: float = 1.0, segments: int = 16,
              center: Point = (0.0, 0.0, 0.0), color: str = "mid",
              name: str = "锥") -> Mesh:
    """圆锥：底圈顶点、一个尖顶和一个底面中心。"""
    radius = _num(radius, "radius", 1.0, 0)
    height = _num(height, "height", 1.0, 0)
    segments = int(_num(segments, "segments", 16, 2))
    cx, cy, cz = _vec3(center, "center", (0.0, 0.0, 0.0))
    half = height / 2.0

    vertices: list[Point] = []
    for segment in range(segments):
        phi = 2.0 * math.pi * segment / segments
        vertices.append((cx + radius * math.cos(phi), cy - half, cz + radius * math.sin(phi)))
    apex = len(vertices)
    vertices.append((cx, cy + half, cz))
    base_center = len(vertices)
    vertices.append((cx, cy - half, cz))

    faces: list[list[int]] = []
    for segment in range(segments):
        following = (segment + 1) % segments
        faces.append([segment, following, apex])
        faces.append([base_center, following, segment])
    _orient_outward(vertices, faces, (cx, cy, cz))
    return Mesh(vertices, faces, color, name)


def make_capsule(radius: float = 1.0, height: float = 1.0, segments: int = 16,
                 rings: int = 8, center: Point = (0.0, 0.0, 0.0),
                 color: str = "mid", name: str = "胶囊") -> Mesh:
    """胶囊：中间一段圆柱，两头各一个半球，花苞和果实的基础体。

    height 只算圆柱那一段，不算两个半球；总高是 height + 2·radius。
    rings 是每个半球分几层；height 为 0 时退化成球。
    """
    radius = _num(radius, "radius", 1.0, 0)
    height = _num(height, "height", 1.0, 0, strict=False)
    segments = int(_num(segments, "segments", 16, 2))
    rings = int(_num(rings, "rings", 8, 1))
    cx, cy, cz = _vec3(center, "center", (0.0, 0.0, 0.0))
    if height < 1e-9:
        return make_sphere(radius, segments, 2 * rings, center, color, name)

    half = height / 2.0
    profile: list[tuple[float, float]] = [(0.0, -half - radius)]
    for step in range(1, rings):
        theta = -math.pi / 2.0 + (math.pi / 2.0) * step / rings
        profile.append((radius * math.cos(theta), -half + radius * math.sin(theta)))
    profile.append((radius, -half))
    profile.append((radius, half))
    for step in range(1, rings):
        theta = (math.pi / 2.0) * step / rings
        profile.append((radius * math.cos(theta), half + radius * math.sin(theta)))
    profile.append((0.0, half + radius))
    return make_lathe(profile, segments, (cx, cy, cz), color, name)


def make_lathe(profile, segments: int = 16, center: Point = (0.0, 0.0, 0.0),
               color: str = "mid", name: str = "旋转体") -> Mesh:
    """把一条二维母线绕竖直轴转一圈，花瓶、果子、花萼都用它。

    profile 是一组 [r, y]，y 从下往上只增不减，r 不能是负数；r 为 0 的
    端点收成一个尖。首尾不在轴上时自动补平面盖，做出来的网格是水密的。
    """
    segments = int(_num(segments, "segments", 16, 2))
    cx, cy, cz = _vec3(center, "center", (0.0, 0.0, 0.0))
    if not isinstance(profile, (list, tuple)) or len(profile) < 2:
        raise ValueError("lathe 需要 profile：至少两个 [r, y]")

    shape: list[tuple[float, float]] = []
    for index, item in enumerate(profile):
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            raise ValueError(f"profile 第 {index + 1} 个点要写成 [r, y]")
        radius = _num(item[0], f"profile[{index}].r", None, 0, strict=False)
        level = _num(item[1], f"profile[{index}].y", None)
        if shape and abs(level - shape[-1][1]) < 1e-12 and abs(radius - shape[-1][0]) < 1e-12:
            continue
        shape.append((radius, level))
    if len(shape) < 2:
        raise ValueError("lathe 的 profile 去掉重复点以后不足两个")
    for index in range(len(shape) - 1):
        if shape[index + 1][1] < shape[index][1] - 1e-12:
            raise ValueError("lathe 的 profile 要按 y 从下往上写，y 不能回落")

    vertices: list[Point] = []
    rows: list[list[int]] = []
    for radius, level in shape:
        if radius <= 1e-9:
            rows.append([len(vertices)])
            vertices.append((cx, cy + level, cz))
            continue
        ring = []
        for segment in range(segments):
            phi = 2.0 * math.pi * segment / segments
            ring.append(len(vertices))
            vertices.append((
                cx + radius * math.cos(phi),
                cy + level,
                cz + radius * math.sin(phi),
            ))
        rows.append(ring)

    faces: list[list[int]] = []
    for index in range(len(rows) - 1):
        lower, upper = rows[index], rows[index + 1]
        if len(lower) == 1 and len(upper) == 1:
            raise ValueError("profile 相邻两点都在轴上，这一段没有体积")
        if len(lower) == 1:
            pole = lower[0]
            for segment in range(segments):
                faces.append([pole, upper[segment], upper[(segment + 1) % segments]])
        elif len(upper) == 1:
            pole = upper[0]
            for segment in range(segments):
                faces.append([lower[segment], pole, lower[(segment + 1) % segments]])
        else:
            for segment in range(segments):
                following = (segment + 1) % segments
                faces.append([lower[segment], upper[segment], upper[following], lower[following]])

    # 两端不在轴上就补平面盖；补了盖才是实心、水密的
    for row, level, flip in ((rows[0], shape[0][1], False), (rows[-1], shape[-1][1], True)):
        if len(row) == 1:
            continue
        center_index = len(vertices)
        vertices.append((cx, cy + level, cz))
        for segment in range(segments):
            following = (segment + 1) % segments
            if flip:
                faces.append([center_index, row[following], row[segment]])
            else:
                faces.append([center_index, row[segment], row[following]])

    return Mesh(vertices, faces, color, name).validate()


def sweep(points, radii, sides: int = 12, caps: bool = True,
          color: str = "mid", name: str = "扫掠") -> Mesh:
    """沿一条三维折线扫出变半径的管，枝条、花梗、藤蔓都用它。

    points 至少两个点；radii 给每个点一个半径，也可以只给一个数表示全程等粗。
    每一圈的方向用平行传输从上一点转过来，整条线不会突然翻面或拧起来。
    半径写 0 的点收成一个尖，像枝梢；caps 为真时两头补盖，管子是水密的。
    """
    if not isinstance(points, (list, tuple)) or len(points) < 2:
        raise ValueError("sweep 需要至少两个点")
    path = [_vec3(item, f"points[{index}]") for index, item in enumerate(points)]
    for index in range(len(path) - 1):
        if _length(_sub(path[index + 1], path[index])) < 1e-9:
            raise ValueError(f"points 第 {index + 1} 和第 {index + 2} 个点重合，没法定方向")
    sides = int(_num(sides, "sides", 12, 2))

    if isinstance(radii, (int, float)) and not isinstance(radii, bool):
        weights = [_num(radii, "radii", 0.0, 0, strict=False)] * len(path)
    else:
        if not isinstance(radii, (list, tuple)) or len(radii) != len(path):
            raise ValueError("radii 要和 points 一样长，或者只给一个数")
        weights = [
            _num(item, f"radii[{index}]", None, 0, strict=False)
            for index, item in enumerate(radii)
        ]

    tangents: list[Point] = []
    for index in range(len(path)):
        if index == 0:
            direction = _sub(path[1], path[0])
        elif index == len(path) - 1:
            direction = _sub(path[-1], path[-2])
        else:
            direction = _sub(path[index + 1], path[index - 1])
        tangents.append(_unit(direction, f"第 {index + 1} 个点的切线"))

    frames: list[tuple[Point, Point]] = [_first_frame(tangents[0])]
    for index in range(1, len(path)):
        previous = tangents[index - 1]
        current = tangents[index]
        axis = _cross(previous, current)
        sine = _length(axis)
        u = frames[-1][0]
        if sine > 1e-9:
            angle = math.atan2(sine, _dot(previous, current))
            u = _rotate_about(u, _mul(axis, 1.0 / sine), angle)
        # 每步重新正交化，误差不会一路积下去
        u = _unit(_sub(u, _mul(current, _dot(u, current))), "扫掠截面方向")
        frames.append((u, _cross(current, u)))

    vertices: list[Point] = []
    rows: list[list[int]] = []
    for index, (center, radius) in enumerate(zip(path, weights)):
        if radius <= 1e-9:
            rows.append([len(vertices)])
            vertices.append(center)
            continue
        u, v = frames[index]
        ring = []
        for side in range(sides):
            angle = 2.0 * math.pi * side / sides
            cos_a, sin_a = math.cos(angle), math.sin(angle)
            ring.append(len(vertices))
            vertices.append((
                center[0] + radius * (cos_a * u[0] + sin_a * v[0]),
                center[1] + radius * (cos_a * u[1] + sin_a * v[1]),
                center[2] + radius * (cos_a * u[2] + sin_a * v[2]),
            ))
        rows.append(ring)

    faces: list[list[int]] = []
    for index in range(len(rows) - 1):
        lower, upper = rows[index], rows[index + 1]
        if len(lower) == 1 and len(upper) == 1:
            raise ValueError(f"points 第 {index + 1} 和第 {index + 2} 个点的半径都是 0，这一段没有体积")
        if len(lower) == 1:
            pole = lower[0]
            for side in range(sides):
                faces.append([pole, upper[(side + 1) % sides], upper[side]])
        elif len(upper) == 1:
            pole = upper[0]
            for side in range(sides):
                faces.append([lower[side], lower[(side + 1) % sides], pole])
        else:
            for side in range(sides):
                following = (side + 1) % sides
                faces.append([lower[side], lower[following], upper[following], upper[side]])

    if caps:
        first, last = rows[0], rows[-1]
        if len(first) > 1:
            center_index = len(vertices)
            vertices.append(path[0])
            for side in range(sides):
                faces.append([center_index, first[(side + 1) % sides], first[side]])
        if len(last) > 1:
            center_index = len(vertices)
            vertices.append(path[-1])
            for side in range(sides):
                faces.append([center_index, last[side], last[(side + 1) % sides]])

    return Mesh(vertices, faces, color, name).validate()


def bounds(mesh: Mesh) -> dict:
    """网格世界坐标的包围盒，返回 min、max、size 三个三元组。"""
    points = mesh.world_vertices()
    if not points:
        raise ValueError(f"网格 {mesh.name} 没有顶点，算不出包围盒")
    low = (min(point[0] for point in points),
           min(point[1] for point in points),
           min(point[2] for point in points))
    high = (max(point[0] for point in points),
            max(point[1] for point in points),
            max(point[2] for point in points))
    size = (high[0] - low[0], high[1] - low[1], high[2] - low[2])
    return {"min": low, "max": high, "size": size}


def is_watertight(mesh: Mesh) -> bool:
    """每条边都正好被两个面共用，说明网格是封闭的，没有漏洞。"""
    uses: dict[tuple[int, int], int] = {}
    for face in mesh.faces:
        for index, corner in enumerate(face):
            following = face[(index + 1) % len(face)]
            key = (corner, following) if corner < following else (following, corner)
            uses[key] = uses.get(key, 0) + 1
    return bool(uses) and all(count == 2 for count in uses.values())


def _mean(points: Sequence[Point]) -> Point:
    count = len(points)
    return (
        sum(point[0] for point in points) / count,
        sum(point[1] for point in points) / count,
        sum(point[2] for point in points) / count,
    )


def _subdivide_once(mesh: Mesh) -> Mesh:
    """细分一次，所有面都变成四边形。"""
    vertices = mesh.vertices
    faces = mesh.faces
    face_points = [_mean([vertices[index] for index in face]) for face in faces]

    # 同名边只登记一次；owner 是一个面就是边界边，两个面是内部边
    edge_faces: dict[tuple[int, int], list[int]] = {}
    for face_index, face in enumerate(faces):
        count = len(face)
        for index in range(count):
            first = face[index]
            second = face[(index + 1) % count]
            key = (first, second) if first < second else (second, first)
            edge_faces.setdefault(key, []).append(face_index)
    edge_order = list(edge_faces)
    edge_index = {key: index for index, key in enumerate(edge_order)}

    edge_points: list[Point] = []
    for key, owners in edge_faces.items():
        first, second = key
        if len(owners) == 2:
            edge_points.append(_mean([
                vertices[first], vertices[second],
                face_points[owners[0]], face_points[owners[1]],
            ]))
        else:
            edge_points.append(_mean([vertices[first], vertices[second]]))

    vertex_faces: dict[int, list[int]] = {index: [] for index in range(len(vertices))}
    vertex_edges: dict[int, list[tuple[int, int]]] = {index: [] for index in range(len(vertices))}
    for face_index, face in enumerate(faces):
        for vertex in face:
            vertex_faces[vertex].append(face_index)
    for key in edge_order:
        vertex_edges[key[0]].append(key)
        vertex_edges[key[1]].append(key)

    # 边界顶点的两个邻居：只沿边界走，不借面点，边界不会被内部拽进去
    boundary_neighbours: dict[int, list[int]] = {}
    for key, owners in edge_faces.items():
        if len(owners) == 2:
            continue
        first, second = key
        boundary_neighbours.setdefault(first, []).append(second)
        boundary_neighbours.setdefault(second, []).append(first)

    positions: list[Point] = list(vertices)
    for index, point in enumerate(vertices):
        neighbours = boundary_neighbours.get(index)
        if neighbours is not None:
            if len(neighbours) == 2:
                before = vertices[neighbours[0]]
                after = vertices[neighbours[1]]
                positions[index] = (
                    (6.0 * point[0] + before[0] + after[0]) / 8.0,
                    (6.0 * point[1] + before[1] + after[1]) / 8.0,
                    (6.0 * point[2] + before[2] + after[2]) / 8.0,
                )
            # 边界上出现三个以上邻居是坏拓扑，钉住不动
            continue
        incident = vertex_edges[index]
        count = len(incident)
        if count == 0:
            continue
        around = _mean([face_points[face_index] for face_index in vertex_faces[index]])
        middle = _mean([_mean([vertices[a], vertices[b]]) for a, b in incident])
        positions[index] = (
            (around[0] + 2.0 * middle[0] + (count - 3.0) * point[0]) / count,
            (around[1] + 2.0 * middle[1] + (count - 3.0) * point[1]) / count,
            (around[2] + 2.0 * middle[2] + (count - 3.0) * point[2]) / count,
        )

    edge_base = len(vertices)
    face_base = edge_base + len(edge_order)
    new_faces: list[list[int]] = []
    for face_index, face in enumerate(faces):
        count = len(face)
        for index in range(count):
            current = face[index]
            following = face[(index + 1) % count]
            previous = face[(index - 1) % count]
            next_key = (current, following) if current < following else (following, current)
            prev_key = (previous, current) if previous < current else (current, previous)
            new_faces.append([
                current,
                edge_base + edge_index[next_key],
                face_base + face_index,
                edge_base + edge_index[prev_key],
            ])
    return Mesh(positions + edge_points + face_points, new_faces,
                mesh.color, mesh.name, dict(mesh.transform), mesh.cull)


def subdivide(mesh: Mesh, levels: int = 1) -> Mesh:
    """Catmull-Clark 细分，低面数的曲面变顺，返回新网格，不改原网格。

    四边形按面点、边点、顶点点三套规则生成；三角形和任意多边形走同一条
    路径，每个角生成一个四边形。边界边（只被一个面共用）的边点取中点，
    边界顶点只和两个相邻边界点做 6/8 平均，不看面点，所以边界只沿自己
    的方向平滑，不会被内部拽进去。levels 支持 0、1、2，超过 2 级直接报错，
    每升一级面数大约乘四。
    """
    mesh.validate()
    if isinstance(levels, bool) or not isinstance(levels, int):
        raise ValueError("levels 必须是整数")
    if levels < 0:
        raise ValueError("levels 不能是负数")
    if levels > 2:
        raise ValueError("levels 最多 2 级，再多面数涨得太快")
    result = Mesh(list(mesh.vertices), [list(face) for face in mesh.faces],
                  mesh.color, mesh.name, dict(mesh.transform), mesh.cull)
    for _ in range(levels):
        result = _subdivide_once(result)
    return result.validate()


# 图元的短名字，写代码时按需取用
box = make_box
sphere = make_sphere
cylinder = make_cylinder
cone = make_cone
capsule = make_capsule
lathe = make_lathe


def mesh_from_dict(data: dict) -> Mesh:
    """方案里的一个网格对象转成 Mesh，支持 mesh 和七种图元语法糖。"""
    if not isinstance(data, dict):
        raise ValueError("每个网格都要是一个对象")
    kind = str(data.get("type") or data.get("primitive") or "mesh").lower()
    if kind not in PRIMITIVES:
        raise ValueError(f"网格类型只能是 {'、'.join(PRIMITIVES)}，收到 {kind!r}")

    color = str(data.get("color") or "mid")
    name = str(data.get("name") or "网格")
    center = data.get("center") or data.get("position") or (0.0, 0.0, 0.0)

    if kind == "mesh":
        vertices = data.get("vertices")
        faces = data.get("faces")
        if not isinstance(vertices, (list, tuple)) or not vertices:
            raise ValueError(f"网格 {name} 需要 vertices：一组三维点")
        if not isinstance(faces, (list, tuple)) or not faces:
            raise ValueError(f"网格 {name} 需要 faces：一组顶点下标")
        mesh = Mesh(list(vertices), list(faces), color, name)
    elif kind == "box":
        size = data.get("size")
        if isinstance(size, (list, tuple)):
            if len(size) != 3:
                raise ValueError("box 的 size 要写成 [宽, 高, 深]")
            width, height, depth = size
        else:
            width = data.get("width", 1.0)
            height = data.get("height", 1.0)
            depth = data.get("depth", 1.0)
        mesh = make_box(width, height, depth, center, color, name)
    elif kind == "sphere":
        mesh = make_sphere(
            data.get("radius", 1.0), data.get("segments", 16), data.get("rings", 8),
            center, color, name,
        )
    elif kind == "cylinder":
        mesh = make_cylinder(
            data.get("radius", 1.0), data.get("height", 1.0), data.get("segments", 16),
            center, data.get("caps", True), color, name,
        )
    elif kind == "capsule":
        mesh = make_capsule(
            data.get("radius", 1.0), data.get("height", 1.0),
            data.get("segments", 16), data.get("rings", 8),
            center, color, name,
        )
    elif kind == "lathe":
        mesh = make_lathe(
            data.get("profile"), data.get("segments", 16), center, color, name,
        )
    elif kind == "sweep":
        mesh = sweep(
            data.get("points"), data.get("radii"),
            data.get("sides", 12), data.get("caps", True), color, name,
        )
    else:
        mesh = make_cone(
            data.get("radius", 1.0), data.get("height", 1.0), data.get("segments", 16),
            center, color, name,
        )

    mesh.transform = data.get("transform") or {}
    mesh.cull = bool(data.get("cull", True))
    return mesh.validate()


# ------------------------------------------------------------------ 相机

@dataclass(frozen=True)
class Projection:
    """一个点投到画面上的结果。visible 为假表示在相机背后。"""

    x: float
    y: float
    depth: float
    visible: bool


@dataclass(frozen=True)
class Camera:
    """一台相机。透视和正交共用同一组参数，只改 projection。

    position/target/up 决定朝向；focal 是像素焦距；frame 是画幅；
    ortho_scale 是正交时每世界单位多少像素，不给就按目标距离折算，
    切换投影时主体大小基本不变。near 是透视的近平面，默认 0.001 米，
    贴着相机走的面会被裁掉，不参与除法。
    """

    position: Point = (0.0, 1.2, -6.0)
    target: Point = (0.0, 1.2, 0.0)
    up: Point = (0.0, 1.0, 0.0)
    focal: float = 960.0
    frame: tuple[float, float] = (800.0, 450.0)
    projection: str = "perspective"
    ortho_scale: float | None = None
    center: tuple[float, float] | None = None
    near: float = NEAR_PLANE

    def basis(self) -> tuple[Point, Point, Point]:
        forward = _unit(_sub(self.target, self.position), "相机朝向")
        up = _unit(self.up, "相机的 up")
        right = _cross(up, forward)
        if _length(right) < 1e-9:
            raise ValueError("相机的 up 和朝向平行，定不出画面方向")
        right = _unit(right)
        true_up = _cross(forward, right)
        return right, true_up, forward

    def principal(self) -> tuple[float, float]:
        if self.center is not None:
            return (float(self.center[0]), float(self.center[1]))
        return (float(self.frame[0]) / 2.0, float(self.frame[1]) / 2.0)

    def scale(self) -> float:
        if self.projection == "ortho":
            if self.ortho_scale is not None:
                return float(self.ortho_scale)
            _, _, forward = self.basis()
            distance = max(_dot(_sub(self.target, self.position), forward), 1e-6)
            return self.focal / distance
        return 1.0

    def project(self, point: Point) -> Projection:
        right, up, forward = self.basis()
        relative = _sub(point, self.position)
        view_x = _dot(relative, right)
        view_y = _dot(relative, up)
        depth = _dot(relative, forward)
        cx, cy = self.principal()

        if self.projection == "perspective":
            if depth <= self.near:
                return Projection(0.0, 0.0, depth, False)
            scale = self.focal / depth
        elif self.projection == "ortho":
            scale = self.scale()
        else:
            raise ValueError(f"projection 只能是 {'、'.join(PROJECTIONS)}，收到 {self.projection!r}")

        return Projection(
            cx + scale * view_x,
            cy - scale * view_y,
            depth,
            True,
        )

    def to_camera(self, point: Point) -> Point:
        """世界坐标转相机坐标：x 向右，y 向上，z 向前。"""
        right, up, forward = self.basis()
        relative = _sub(point, self.position)
        return (
            _dot(relative, right),
            _dot(relative, up),
            _dot(relative, forward),
        )

    def project_view(self, view: Point) -> Projection:
        """相机坐标投到画面。传进来的点应该已经过了近平面裁剪。

        裁剪后的点正好落在 near 上也要能画，所以这里只挡 depth <= 0，
        除法的分母仍然有下界。
        """
        view_x, view_y, depth = view
        cx, cy = self.principal()

        if self.projection == "perspective":
            if depth <= 0.0:
                return Projection(0.0, 0.0, depth, False)
            scale = self.focal / depth
        elif self.projection == "ortho":
            scale = self.scale()
        else:
            raise ValueError(f"projection 只能是 {'、'.join(PROJECTIONS)}，收到 {self.projection!r}")

        return Projection(
            cx + scale * view_x,
            cy - scale * view_y,
            depth,
            True,
        )

    def project_points(self, points: Iterable[Point]) -> list[Projection]:
        return [self.project(point) for point in points]

    def facing(self, normal: Point, point: Point) -> bool:
        """面法向量是不是朝着相机。"""
        if self.projection == "ortho":
            _, _, forward = self.basis()
            return _dot(normal, _mul(forward, -1.0)) > 0
        return _dot(normal, _sub(self.position, point)) > 0


def project_points(points: Iterable[Point], camera: Camera) -> list[Projection]:
    return camera.project_points(points)


def _drop_repeats(points: Sequence[Point]) -> list[Point]:
    """去掉相邻重合的点，顺便把首尾重复也收掉。"""
    cleaned: list[Point] = []
    for point in points:
        if not cleaned or _length(_sub(point, cleaned[-1])) > 1e-12:
            cleaned.append(point)
    if len(cleaned) > 1 and _length(_sub(cleaned[0], cleaned[-1])) <= 1e-12:
        cleaned.pop()
    return cleaned


def clip_near(points: Sequence[Point], near: float = NEAR_PLANE) -> list[Point]:
    """把相机空间里的多边形按 z = near 切一刀，只留近平面之前的部分。

    points 是相机坐标（x 向右、y 向上、z 向前），不要传世界坐标。
    完全在近平面后的返回空表；完全在前的原样返回；跨平面的按交点切开，
    四个点可能切成三个或五个。逐边裁剪，顶点顺序不翻，绕向保持不变。
    """
    if isinstance(near, bool) or not isinstance(near, (int, float)):
        raise ValueError("near 必须是数字")
    near = float(near)
    if near <= 0:
        raise ValueError("near 必须大于 0")
    if not points:
        return []

    result: list[Point] = []
    count = len(points)
    for index in range(count):
        current = points[index]
        following = points[(index + 1) % count]
        current_in = current[2] >= near
        following_in = following[2] >= near
        if current_in:
            result.append(current)
        if current_in != following_in:
            span = following[2] - current[2]
            ratio = (near - current[2]) / span
            result.append((
                current[0] + (following[0] - current[0]) * ratio,
                current[1] + (following[1] - current[1]) * ratio,
                near,
            ))
    return _drop_repeats(result)


def _ray_hits_triangle(origin: Point, direction: Point, a: Point, b: Point,
                       c: Point) -> bool:
    """从 origin 沿 direction 打的射线有没有穿过三角形，用 Möller–Trumbore。"""
    edge1 = _sub(b, a)
    edge2 = _sub(c, a)
    h = _cross(direction, edge2)
    det = _dot(edge1, h)
    if abs(det) < 1e-12:
        return False
    inv = 1.0 / det
    s = _sub(origin, a)
    u = _dot(s, h) * inv
    if u < 0.0 or u > 1.0:
        return False
    q = _cross(s, edge1)
    v = _dot(direction, q) * inv
    if v < 0.0 or u + v > 1.0:
        return False
    t = _dot(edge2, q) * inv
    return t > 1e-9


# 判断相机在不在物体里面时用的斜射线，故意挑一个不和常见轴对齐的方向
_INSIDE_RAY = _unit((1.0, 0.5773502691896258, 0.2391073544210927))


def _inside_mesh(world: Sequence[Point], faces: Sequence[Sequence[int]],
                 point: Point) -> bool:
    """相机在不在网格里面：向斜上方打一条射线，穿过奇数个面就是在里面。"""
    hits = 0
    for face in faces:
        first = world[face[0]]
        for index in range(1, len(face) - 1):
            if _ray_hits_triangle(point, _INSIDE_RAY, first, world[face[index]],
                                  world[face[index + 1]]):
                hits += 1
    return hits % 2 == 1


def camera_from_dict(data: dict | None, pen: Pen | None = None) -> Camera:
    """方案里的 camera 对象转成 Camera；画幅默认跟着画笔的参考尺寸。"""
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ValueError("camera 必须是对象")
    frame = data.get("frame")
    if frame is None:
        width = pen.ref_width if pen is not None else 800.0
        height = pen.ref_height if pen is not None else 450.0
        frame = (width, height)
    if not isinstance(frame, (list, tuple)) or len(frame) != 2:
        raise ValueError("camera.frame 必须是 [宽, 高]")
    width = _num(frame[0], "camera.frame 的宽", 800.0, 0)
    height = _num(frame[1], "camera.frame 的高", 450.0, 0)
    focal = _num(data.get("focal"), "camera.focal", width * 1.2, 0)

    projection = str(data.get("projection") or "perspective").lower()
    if projection not in PROJECTIONS:
        raise ValueError(f"camera.projection 只能是 {'、'.join(PROJECTIONS)}，收到 {projection!r}")

    center = data.get("center")
    if center is not None:
        if not isinstance(center, (list, tuple)) or len(center) != 2:
            raise ValueError("camera.center 必须是 [x, y]")
        center = (_num(center[0], "camera.center 的 x"), _num(center[1], "camera.center 的 y"))

    ortho_scale = data.get("ortho_scale")
    if ortho_scale is not None:
        ortho_scale = _num(ortho_scale, "camera.ortho_scale", 1.0, 0)

    return Camera(
        position=_vec3(data.get("position"), "camera.position", (0.0, 1.2, -6.0)),
        target=_vec3(data.get("target"), "camera.target", (0.0, 1.2, 0.0)),
        up=_vec3(data.get("up"), "camera.up", (0.0, 1.0, 0.0)),
        focal=focal,
        frame=(width, height),
        projection=projection,
        ortho_scale=ortho_scale,
        center=center,
        near=_num(data.get("near"), "camera.near", NEAR_PLANE, 0),
    )


def view_camera(name: str, center: Point = (0.0, 0.0, 0.0),
                distance: float = 10.0, focal: float = 960.0,
                frame: tuple[float, float] = (800.0, 450.0)) -> Camera:
    """三视图用的正交相机。front 沿 +z，left 沿 +x，top 沿 -y。

    左视从左往右看，近的一侧落在右边；俯视从上看，x 和正视图同向，
    近的一侧落在下边。两条都和 views.py 的方向约定一致。
    """
    distance = _num(distance, "distance", 10.0, 0)
    focal = _num(focal, "focal", 960.0, 0)
    cx, cy, cz = _vec3(center, "center", (0.0, 0.0, 0.0))
    if name == "front":
        return Camera(position=(cx, cy, cz - distance), target=center,
                      up=(0.0, 1.0, 0.0), focal=focal, frame=frame,
                      projection="ortho")
    if name == "left":
        return Camera(position=(cx - distance, cy, cz), target=center,
                      up=(0.0, 1.0, 0.0), focal=focal, frame=frame,
                      projection="ortho")
    if name == "top":
        return Camera(position=(cx, cy + distance, cz), target=center,
                      up=(0.0, 0.0, 1.0), focal=focal, frame=frame,
                      projection="ortho")
    raise ValueError("视图名只能是 front、left、top")


def ortho_views(center: Point = (0.0, 0.0, 0.0), distance: float = 10.0,
                focal: float = 960.0,
                frame: tuple[float, float] = (800.0, 450.0)) -> dict[str, Camera]:
    """一次给出前、左、俯三台正交相机。"""
    return {
        name: view_camera(name, center, distance, focal, frame)
        for name in ("front", "left", "top")
    }


# ------------------------------------------------------------------ 光照

def _parse_light(light) -> dict | None:
    if light is None or light is False:
        return None
    if not isinstance(light, dict):
        raise ValueError("lighting 必须是对象，或者写 false 关掉")
    direction = _vec3(light.get("direction"), "lighting.direction", (-0.4, -1.0, 0.35))
    if _length(direction) < 1e-9:
        raise ValueError("lighting.direction 不能是零向量")
    return {
        "direction": _unit(direction),
        "ambient": _num(light.get("ambient"), "lighting.ambient", 0.55, 0, strict=False),
        "diffuse": _num(light.get("diffuse"), "lighting.diffuse", 0.45, 0, strict=False),
    }


def shade_color(color: str, normal: Point, light) -> str:
    """面法向量和光线方向的点积换成明度系数，乘到颜色上。

    light 里的 direction 是光线前进的方向，从光源指向物体。环境光加漫反射
    的下限抬到 0.30，避免出现死黑块。
    """
    parsed = _parse_light(light)
    if parsed is None:
        return str(color)
    facing = max(0.0, -_dot(normal, parsed["direction"]))
    factor = parsed["ambient"] + parsed["diffuse"] * facing
    factor = max(MIN_BRIGHTNESS, min(MAX_BRIGHTNESS, factor))
    return _tint(color, factor)


def _tint(value: str, factor: float) -> str:
    text = str(value)
    if len(text) != 7 or not text.startswith("#"):
        return text
    try:
        channels = [int(text[index:index + 2], 16) for index in (1, 3, 5)]
    except ValueError:
        return text
    result = []
    for channel in channels:
        scaled = int(round(channel * factor))
        result.append(max(1, min(254, scaled)))
    return "#%02x%02x%02x" % (result[0], result[1], result[2])


# ------------------------------------------------------------------ 渲染

def _average_depth(projections: Sequence[Projection]) -> float:
    return sum(item.depth for item in projections) / float(len(projections))


def _emit_face(pen: Pen, points, color: str, name, seal: bool) -> None:
    """把一个面画成路径。seal 时补一圈同色描边，盖住共边处的白缝。

    描边颜色和填充色相同，不是勾线；join 用圆角，避免尖角处拉出长刺。
    """
    knots = [[int(round(x * pen.k)), int(round(y * pen.k))] for x, y in points]
    params = {
        "kind": "path",
        "path": {"subpaths": [{"closed": True, "knots": knots}], "fillRule": "nonzero"},
        "fill": color,
        "stroke": None,
    }
    if seal:
        params["stroke"] = {
            "width": max(1, int(round(pen.k))),
            "color": color,
            "align": "center",
            "join": "round",
            "cap": "round",
        }
    if name:
        params["name"] = str(name)
    pen.commands.append({"command": "shape.create", "params": params})


def render(meshes: Sequence[Mesh], camera: Camera, pen: Pen,
           lighting=None, named: bool = False, seal: bool = True) -> dict:
    """把一组网格画进画笔，远的面先画，背对相机的剔掉。

    透视时每个面先在相机空间里按相机 near 裁剪，跨过近平面的面切开继续画；
    相机整个在物体里面时自动放开剔除，画内壁。正交不做近平面裁剪。
    seal 给每个面补一圈同色描边，盖住相邻面共边处露出的白缝；
    不要可以把 seal 关掉，但相邻面之间会透出底下的颜色。

    返回统计：原始面数、画出的面数、剔掉的面数和新增指令数。
    """
    if not isinstance(camera, Camera):
        raise ValueError("render 需要一个 Camera")
    light = _parse_light(lighting)

    queue = []
    total = 0
    culled = 0
    for mesh_index, mesh in enumerate(meshes):
        mesh.validate()
        matrix = mesh.matrix()
        world = [apply_matrix(matrix, point) for point in mesh.vertices]

        # 相机钻到物体里面时，外法线全都背对相机，正常剔除会把整块剔光；
        # 这时放开剔除，画内壁。先看包围盒，绝大多数情况一步就排除。
        from_inside = False
        if mesh.cull:
            low = (min(point[0] for point in world),
                   min(point[1] for point in world),
                   min(point[2] for point in world))
            high = (max(point[0] for point in world),
                    max(point[1] for point in world),
                    max(point[2] for point in world))
            if all(low[axis] <= camera.position[axis] <= high[axis] for axis in range(3)):
                from_inside = _inside_mesh(world, mesh.faces, camera.position)

        for face_index, face in enumerate(mesh.faces):
            total += 1
            points = [world[index] for index in face]
            if len(set(points)) < 3:
                culled += 1
                continue
            center = face_center(points)
            normal = face_normal(points)
            if _length(normal) < 1e-9:
                culled += 1
                continue
            if mesh.cull and not from_inside and not camera.facing(normal, center):
                culled += 1
                continue

            if camera.projection == "perspective":
                # 透视要先在相机空间里按近平面切一刀，再除以深度，
                # 否则贴着相机或跨过相机的面会把坐标甩到几万像素外。
                view = clip_near([camera.to_camera(point) for point in points], camera.near)
                if len(view) < 3:
                    culled += 1
                    continue
                projections = [camera.project_view(item) for item in view]
            else:
                projections = [camera.project(point) for point in points]
            if not all(item.visible for item in projections):
                culled += 1
                continue
            color = color_of(pen.palette, mesh.color)
            if light is not None:
                color = shade_color(color, normal, light)
            queue.append((
                _average_depth(projections),
                mesh_index,
                face_index,
                [(item.x, item.y) for item in projections],
                color,
                f"{mesh.name} {face_index + 1}" if named else None,
            ))

    # 远的先画，近的压在上面；同深度按网格和面的原始顺序，结果稳定
    queue.sort(key=lambda item: (-item[0], item[1], item[2]))
    before = len(pen.commands)
    for _, _, _, points, color, name in queue:
        _emit_face(pen, points, color, name, seal)
    return {
        "faces": total,
        "drawn": len(queue),
        "culled": culled,
        "commands": len(pen.commands) - before,
    }


def build(params: dict, pen: Pen) -> dict:
    """组件入口：一张方案参数画成一个网格场景。

    参数：
        meshes   网格列表，必填；每项写 type 和对应字段
        camera   相机参数，可选；默认站在 -z，看向原点
        lighting   光照，可选；写 false 或省略是平涂
        named_faces 是否给每个面起名，默认 false
        seal       是否给面补同色描边盖住细缝，默认 true
    """
    if not isinstance(params, dict):
        raise ValueError("网格场景参数必须是一个对象")
    items = params.get("meshes")
    if not isinstance(items, (list, tuple)) or not items:
        raise ValueError("网格场景需要 meshes：一个非空的网格列表")
    meshes = [mesh_from_dict(item) for item in items]
    camera = camera_from_dict(params.get("camera"), pen)
    return render(
        meshes, camera, pen,
        lighting=params.get("lighting"),
        named=bool(params.get("named_faces", False)),
        seal=bool(params.get("seal", True)),
    )


build_mesh_scene = build

# 登记用：和 components 下那些模块的 COMPONENTS 同一个格式，
# registry 里加一行 _SPECS.update(mesh.COMPONENTS) 就能用。
COMPONENTS = {
    "mesh_scene": {
        "name": "网格场景",
        "description": "顶点、变换矩阵、透视或正交相机、面排序和背面剔除，画三维白模",
        "params": {
            "meshes": "[{type, …}, …]，必填；type 写 mesh、box、sphere、cylinder、cone、capsule、lathe、sweep",
            "camera": "{position, target, up, focal, frame, projection, ortho_scale, near}，可选；near 默认 0.001",
            "lighting": "{direction, ambient, diffuse}，可选；写 false 是平涂",
            "seal": "是否补面缝，默认 true",
            "named_faces": "是否给每个面起名，默认 false",
        },
        "build": build,
    },
}

__all__ = [
    "Camera", "Mesh", "Projection", "PROJECTIONS", "PRIMITIVES", "COMPONENTS",
    "identity", "matmul", "translation", "scaling",
    "rotation_x", "rotation_y", "rotation_z",
    "compose_transform", "apply_matrix", "transform_point", "transform_points",
    "face_center", "face_normal", "shade_color",
    "make_box", "make_sphere", "make_cylinder", "make_cone",
    "make_capsule", "make_lathe", "sweep", "bounds", "is_watertight",
    "box", "sphere", "cylinder", "cone", "capsule", "lathe",
    "mesh_from_dict", "camera_from_dict",
    "view_camera", "ortho_views", "project_points", "clip_near",
    "render", "build", "build_mesh_scene",
]
