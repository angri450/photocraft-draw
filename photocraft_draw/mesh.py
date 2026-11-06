# -*- coding: utf-8 -*-
"""网格渲染管线：顶点、变换矩阵、相机投影、面排序和背面剔除。

世界坐标定死：x 向右，y 向上，z 越大离观众越远。相机默认站在 -z，
沿 +z 看过去，所以画面上的 x 和世界 x 同向。

一条渲染链分五步，和蓝图 4.1 一致：
    1. 顶点乘变换矩阵，从模型坐标进世界坐标；
    2. 顶点乘相机基，进相机坐标；
    3. 透视除以深度，正交只乘比例，得到画面坐标；
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
    mesh_from_dict / camera_from_dict    方案参数转对象
    face_center / face_normal / shade_color
    project_points                       一组点投到画面
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
PRIMITIVES = ("mesh", "box", "sphere", "cylinder", "cone")

# 透视时深度小于这个数的点算在相机后面
NEAR_PLANE = 0.01

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


# 图元的短名字，写代码时按需取用
box = make_box
sphere = make_sphere
cylinder = make_cylinder
cone = make_cone


def mesh_from_dict(data: dict) -> Mesh:
    """方案里的一个网格对象转成 Mesh，支持 mesh 和四种图元语法糖。"""
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
    切换投影时主体大小基本不变。
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
            if mesh.cull and not camera.facing(normal, center):
                culled += 1
                continue
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
            "meshes": "[{type, …}, …]，必填；type 写 mesh、box、sphere、cylinder、cone",
            "camera": "{position, target, up, focal, frame, projection, ortho_scale}，可选",
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
    "box", "sphere", "cylinder", "cone",
    "mesh_from_dict", "camera_from_dict",
    "view_camera", "ortho_views", "project_points",
    "render", "build", "build_mesh_scene",
]
