# -*- coding: utf-8 -*-
import math
import unittest

from photocraft_draw.commands import Pen
from photocraft_draw.mesh import (
    Camera,
    Mesh,
    apply_matrix,
    bounds,
    build,
    camera_from_dict,
    clip_near,
    compose_transform,
    face_center,
    face_normal,
    identity,
    is_watertight,
    make_box,
    make_capsule,
    make_cone,
    make_cylinder,
    make_lathe,
    make_sphere,
    matmul,
    mesh_from_dict,
    ortho_views,
    project_points,
    render,
    rotation_x,
    rotation_y,
    rotation_z,
    scaling,
    shade_color,
    sweep,
    translation,
    view_camera,
)
from photocraft_draw.palette import PALETTES, resolve_palette


def pen(width=800, height=450):
    return Pen(width, height, ref_width=800, palette=resolve_palette("fresco"))


def paths(target):
    return [item for item in target.commands if item["command"] == "shape.create"]


def outward(mesh):
    """每个面的法向量都应该和「面中心减网格中心」同向。"""
    cx = sum(point[0] for point in mesh.vertices) / len(mesh.vertices)
    cy = sum(point[1] for point in mesh.vertices) / len(mesh.vertices)
    cz = sum(point[2] for point in mesh.vertices) / len(mesh.vertices)
    for face in mesh.faces:
        points = [mesh.vertices[index] for index in face]
        normal = face_normal(points)
        center = face_center(points)
        offset = (center[0] - cx, center[1] - cy, center[2] - cz)
        self_dot = sum(a * b for a, b in zip(normal, offset))
        if self_dot <= 0:
            return False, face, self_dot
    return True, None, None


def volume(mesh):
    """按面片算有向体积，正数说明面朝外，负数说明整体翻面。"""
    total = 0.0
    for face in mesh.faces:
        points = [mesh.vertices[index] for index in face]
        for index in range(1, len(points) - 1):
            a, b, c = points[0], points[index], points[index + 1]
            total += (
                a[0] * (b[1] * c[2] - b[2] * c[1])
                - a[1] * (b[0] * c[2] - b[2] * c[0])
                + a[2] * (b[0] * c[1] - b[1] * c[0])
            ) / 6.0
    return total


def edge_uses(mesh):
    uses = {}
    for face in mesh.faces:
        for index, corner in enumerate(face):
            following = face[(index + 1) % len(face)]
            key = (corner, following) if corner < following else (following, corner)
            uses[key] = uses.get(key, 0) + 1
    return uses


class MatrixTest(unittest.TestCase):
    def test_identity_leaves_point_alone(self):
        self.assertEqual(apply_matrix(identity(), (1, 2, 3)), (1, 2, 3))

    def test_translation_and_scale(self):
        matrix = matmul(translation((2, -1, 3)), scaling((2, 2, 2)))
        self.assertEqual(apply_matrix(matrix, (1, 1, 1)), (4, 1, 5))

    def test_rotation_quarter_turn(self):
        point = apply_matrix(rotation_z(90), (1, 0, 0))
        self.assertAlmostEqual(point[0], 0.0, places=6)
        self.assertAlmostEqual(point[1], 1.0, places=6)
        point = apply_matrix(rotation_x(90), (0, 1, 0))
        self.assertAlmostEqual(point[1], 0.0, places=6)
        self.assertAlmostEqual(point[2], 1.0, places=6)
        point = apply_matrix(rotation_y(90), (1, 0, 0))
        self.assertAlmostEqual(point[2], -1.0, places=6)

    def test_compose_transform_order(self):
        # 先放大两倍，再搬到 x=1，结果点应该是 3 不是 5
        matrix = compose_transform({"scale": [2, 2, 2], "translate": [1, 0, 0]})
        point = apply_matrix(matrix, (1, 0, 0))
        self.assertAlmostEqual(point[0], 3.0, places=6)

    def test_compose_transform_defaults(self):
        matrix = compose_transform(None)
        self.assertEqual(apply_matrix(matrix, (2, 3, 4)), (2, 3, 4))


class PrimitiveTest(unittest.TestCase):
    def test_box_topology(self):
        mesh = make_box(2, 3, 4)
        self.assertEqual(len(mesh.vertices), 8)
        self.assertEqual(len(mesh.faces), 6)
        self.assertTrue(outward(mesh)[0])
        xs = [point[0] for point in mesh.vertices]
        self.assertAlmostEqual(max(xs) - min(xs), 2.0)

    def test_box_center(self):
        mesh = make_box(2, 2, 2, center=(5, 6, 7))
        xs = [point[0] for point in mesh.vertices]
        self.assertAlmostEqual(sum(xs) / len(xs), 5.0)

    def test_sphere_topology(self):
        mesh = make_sphere(1, 12, 6)
        self.assertEqual(len(mesh.vertices), 2 + 12 * 5)
        self.assertEqual(len(mesh.faces), 12 * 6)
        self.assertTrue(outward(mesh)[0])
        for point in mesh.vertices:
            self.assertAlmostEqual(math.sqrt(sum(value * value for value in point)), 1.0, places=6)

    def test_cylinder_topology(self):
        mesh = make_cylinder(1, 2, 12)
        self.assertEqual(len(mesh.vertices), 26)
        self.assertEqual(len(mesh.faces), 12 + 12 + 12)
        self.assertTrue(outward(mesh)[0])

    def test_cylinder_without_caps(self):
        mesh = make_cylinder(1, 2, 12, caps=False)
        self.assertEqual(len(mesh.vertices), 24)
        self.assertEqual(len(mesh.faces), 12)

    def test_cone_topology(self):
        mesh = make_cone(1, 2, 12)
        self.assertEqual(len(mesh.vertices), 14)
        self.assertEqual(len(mesh.faces), 24)
        self.assertTrue(outward(mesh)[0])

    def test_primitive_rejects_zero_size(self):
        with self.assertRaises(ValueError):
            make_box(0, 1, 1)
        with self.assertRaises(ValueError):
            make_sphere(1, 1, 6)


class CapsuleTest(unittest.TestCase):
    def test_topology(self):
        mesh = make_capsule(1, 2, 12, 4)
        self.assertEqual(len(mesh.vertices), 98)
        self.assertEqual(len(mesh.faces), 108)

    def test_bounds_include_both_hemispheres(self):
        mesh = make_capsule(0.5, 1.2, 16, 6, center=(2, 3, 4))
        box = bounds(mesh)
        self.assertAlmostEqual(box["size"][0], 1.0, places=6)
        self.assertAlmostEqual(box["size"][1], 2.2, places=6)
        self.assertAlmostEqual(box["size"][2], 1.0, places=6)
        self.assertAlmostEqual(box["min"][1], 3 - 1.1, places=6)
        self.assertAlmostEqual(box["max"][1], 3 + 1.1, places=6)

    def test_watertight_and_outward(self):
        mesh = make_capsule(0.5, 1.0, 16, 6)
        self.assertTrue(is_watertight(mesh))
        self.assertGreater(volume(mesh), 0)

    def test_every_vertex_lies_on_the_surface(self):
        radius, height = 0.6, 1.4
        mesh = make_capsule(radius, height, 20, 8)
        half = height / 2.0
        for x, y, z in mesh.vertices:
            radial = math.hypot(x, z)
            if abs(y) <= half + 1e-9:
                self.assertAlmostEqual(radial, radius, places=6)
            else:
                bulge = abs(y) - half
                self.assertAlmostEqual(radial * radial + bulge * bulge,
                                       radius * radius, places=6)

    def test_zero_height_is_a_sphere(self):
        capsule = make_capsule(1, 0, 12, 4)
        sphere = make_sphere(1, 12, 8)
        self.assertEqual(len(capsule.vertices), len(sphere.vertices))
        self.assertEqual(len(capsule.faces), len(sphere.faces))
        self.assertTrue(is_watertight(capsule))

    def test_rejects_negative_radius(self):
        with self.assertRaises(ValueError):
            make_capsule(-1, 1)


class LatheTest(unittest.TestCase):
    def test_vase_topology_and_cap(self):
        mesh = make_lathe([(0.0, 0.0), (0.5, 0.0), (0.35, 0.6), (0.55, 1.2), (0.3, 1.5)], 20)
        self.assertEqual(len(mesh.vertices), 82)
        self.assertEqual(len(mesh.faces), 100)
        self.assertTrue(is_watertight(mesh))
        self.assertGreater(volume(mesh), 0)

    def test_closed_profile_needs_no_caps(self):
        # 一条从轴到轴的母线，两头都是尖，顶点里没有额外的盖子中心
        mesh = make_lathe([(0.0, 0.0), (0.6, 0.5), (0.0, 1.0)], 12)
        self.assertEqual(len(mesh.vertices), 2 + 12)
        self.assertEqual(len(mesh.faces), 24)
        self.assertTrue(is_watertight(mesh))

    def test_bounds(self):
        mesh = make_lathe([(0.0, 0.0), (0.5, 0.0), (0.5, 2.0), (0.0, 2.0)], 16)
        box = bounds(mesh)
        self.assertAlmostEqual(box["size"][1], 2.0, places=6)
        self.assertAlmostEqual(box["size"][0], 1.0, places=6)
        self.assertAlmostEqual(box["size"][2], 1.0, places=6)

    def test_duplicate_profile_points_are_dropped(self):
        clean = make_lathe([(0.0, 0.0), (0.5, 0.0), (0.5, 0.0), (0.0, 1.0)], 8)
        plain = make_lathe([(0.0, 0.0), (0.5, 0.0), (0.0, 1.0)], 8)
        self.assertEqual(len(clean.vertices), len(plain.vertices))
        self.assertEqual(len(clean.faces), len(plain.faces))

    def test_rejects_profile_going_down(self):
        with self.assertRaises(ValueError):
            make_lathe([(0.0, 1.0), (0.5, 0.0)], 8)

    def test_rejects_bad_profile(self):
        with self.assertRaises(ValueError):
            make_lathe([(0.5, 0.0)], 8)
        with self.assertRaises(ValueError):
            make_lathe([(0.0, 0.0), (0.5, 1.0, 2.0)], 8)
        with self.assertRaises(ValueError):
            make_lathe([(0.0, 0.0), (-0.5, 1.0)], 8)


class SweepTest(unittest.TestCase):
    def test_straight_tube_topology(self):
        mesh = sweep([(0, 0, 0), (0, 2, 0)], 0.3, sides=8)
        self.assertEqual(len(mesh.vertices), 2 * 8 + 2)
        self.assertEqual(len(mesh.faces), 8 + 16)
        self.assertTrue(is_watertight(mesh))

    def test_radius_follows_each_point(self):
        points = [(0, 0, 0), (0, 1, 0), (1, 2, 0), (2, 2, 0)]
        weights = [0.1, 0.2, 0.15, 0.05]
        sides = 10
        mesh = sweep(points, weights, sides=sides)
        for index, (center, radius) in enumerate(zip(points, weights)):
            for side in range(sides):
                vertex = mesh.vertices[index * sides + side]
                distance = math.dist(vertex, center)
                self.assertAlmostEqual(distance, radius, places=6)

    def test_planar_sweep_does_not_twist(self):
        points = [(0, 0, 0), (0, 1, 0), (0.6, 1.6, 0), (1.4, 1.4, 0), (2.0, 0.6, 0)]
        sides = 8
        mesh = sweep(points, 0.12, sides=sides)
        bases = []
        for index in range(len(points) - 1):
            center = points[index]
            vertex = mesh.vertices[index * sides]
            bases.append(tuple((vertex[axis] - center[axis]) / 0.12 for axis in range(3)))
        for basis in bases:
            overlap = sum(a * b for a, b in zip(basis, bases[0]))
            self.assertAlmostEqual(overlap, 1.0, places=6)
            self.assertAlmostEqual(abs(basis[2]), 1.0, places=6)

    def test_tip_radius_zero_makes_a_point(self):
        mesh = sweep([(0, 0, 0), (0, 1, 0), (0, 2, 0)], [0.2, 0.1, 0.0], sides=6)
        self.assertEqual(len(mesh.vertices), 6 + 6 + 1 + 1)
        self.assertIn((0.0, 2.0, 0.0), mesh.vertices)
        self.assertTrue(is_watertight(mesh))

    def test_caps_can_be_turned_off(self):
        capped = sweep([(0, 0, 0), (0, 1, 0)], 0.2, sides=6)
        open_tube = sweep([(0, 0, 0), (0, 1, 0)], 0.2, sides=6, caps=False)
        self.assertTrue(is_watertight(capped))
        self.assertFalse(is_watertight(open_tube))

    def test_bounds(self):
        mesh = sweep([(-1, 0, 0), (1, 0, 0)], 0.25, sides=16)
        box = bounds(mesh)
        # 两头是平盖，管的长度就是 2，管的粗细算在 y、z 上
        self.assertAlmostEqual(box["size"][0], 2.0, places=6)
        self.assertAlmostEqual(box["size"][1], 0.5, places=6)

    def test_rejects_bad_path(self):
        with self.assertRaises(ValueError):
            sweep([(0, 0, 0)], 0.1)
        with self.assertRaises(ValueError):
            sweep([(0, 0, 0), (0, 0, 0)], 0.1)
        with self.assertRaises(ValueError):
            sweep([(0, 0, 0), (0, 1, 0)], [0.1, 0.2, 0.3])
        with self.assertRaises(ValueError):
            sweep([(0, 0, 0), (0, 1, 0)], -0.1)


class PrimitiveInspectionTest(unittest.TestCase):
    def test_bounds_apply_transform(self):
        mesh = make_box(2, 2, 2, center=(0, 0, 0))
        mesh.transform = {"translate": [3, 0, 0]}
        box = bounds(mesh)
        self.assertAlmostEqual(box["min"][0], 2.0, places=6)
        self.assertAlmostEqual(box["max"][0], 4.0, places=6)

    def test_watertight_on_old_primitives(self):
        for mesh in (make_box(), make_sphere(1, 8, 4), make_cylinder(1, 2, 8),
                     make_cone(1, 2, 8)):
            self.assertTrue(is_watertight(mesh), mesh.name)
        self.assertFalse(is_watertight(make_cylinder(1, 2, 8, caps=False)))

    def test_every_edge_shared_by_two_faces(self):
        for mesh in (make_capsule(0.5, 1, 12, 4),
                     make_lathe([(0, 0), (0.4, 0.3), (0.2, 1.0)], 10),
                     sweep([(0, 0, 0), (0.5, 1, 0), (1, 1.5, 0.3)], [0.1, 0.15, 0.0], 8)):
            uses = edge_uses(mesh)
            self.assertTrue(uses)
            self.assertEqual(set(uses.values()), {2}, mesh.name)
            edges = len(uses)
            self.assertEqual(len(mesh.vertices) - edges + len(mesh.faces), 2, mesh.name)


class MeshFromDictTest(unittest.TestCase):
    def test_blueprint_schema(self):
        data = {
            "type": "mesh",
            "vertices": [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]],
            "faces": [[0, 1, 2], [0, 2, 3]],
            "color": "#C8455F",
            "transform": {"translate": [0, 1.2, 1.5], "rotate": [0, 15, -6], "scale": [1, 1, 1]},
        }
        mesh = mesh_from_dict(data)
        self.assertEqual(mesh.color, "#C8455F")
        self.assertEqual(mesh.transform["translate"], [0, 1.2, 1.5])
        world = mesh.world_vertices()
        self.assertNotAlmostEqual(world[0][1], 0.0)

    def test_primitive_sugar(self):
        mesh = mesh_from_dict({"type": "box", "size": [2, 2, 2], "center": [0, 1, 0]})
        self.assertEqual(len(mesh.vertices), 8)
        mesh = mesh_from_dict({"primitive": "sphere", "radius": 1, "segments": 6, "rings": 4})
        self.assertEqual(len(mesh.faces), 24)

    def test_new_primitive_sugar(self):
        capsule = mesh_from_dict({"type": "capsule", "radius": 0.5, "height": 1,
                                  "segments": 10, "rings": 3})
        self.assertEqual(capsule.name, "网格")
        self.assertTrue(is_watertight(capsule))

        lathe = mesh_from_dict({"type": "lathe", "segments": 12,
                                "profile": [[0, 0], [0.4, 0.2], [0, 1]]})
        self.assertEqual(len(lathe.vertices), 2 + 12)

        swept = mesh_from_dict({"type": "sweep", "sides": 6,
                                "points": [[0, 0, 0], [0, 1, 0]],
                                "radii": [0.1, 0.1]})
        self.assertTrue(is_watertight(swept))
        self.assertEqual(len(swept.faces), 6 + 12)

    def test_sweep_needs_radii(self):
        with self.assertRaises(ValueError):
            mesh_from_dict({"type": "sweep", "points": [[0, 0, 0], [0, 1, 0]]})

    def test_bad_index(self):
        with self.assertRaises(ValueError):
            mesh_from_dict({"vertices": [[0, 0, 0]], "faces": [[0, 1, 2]]})

    def test_short_face(self):
        with self.assertRaises(ValueError):
            mesh_from_dict({"vertices": [[0, 0, 0], [1, 0, 0]], "faces": [[0, 1]]})

    def test_unknown_type(self):
        with self.assertRaises(ValueError):
            mesh_from_dict({"type": "torus"})

    def test_validate_fills_floats(self):
        mesh = Mesh([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [[0, 1, 2]]).validate()
        self.assertEqual(mesh.vertices[0], (0.0, 0.0, 0.0))


class CameraTest(unittest.TestCase):
    def test_perspective_formula(self):
        camera = Camera(position=(0, 0, -10), target=(0, 0, 0),
                        focal=100, frame=(200, 100))
        self.assertEqual(camera.project((0, 0, 0)).x, 100.0)
        self.assertEqual(camera.project((0, 0, 0)).y, 50.0)
        self.assertEqual(camera.project((1, 0, 0)).x, 110.0)
        self.assertEqual(camera.project((0, 1, 0)).y, 40.0)

    def test_perspective_behind_camera(self):
        camera = Camera(position=(0, 0, -10), target=(0, 0, 0), focal=100)
        self.assertFalse(camera.project((0, 0, -12)).visible)

    def test_ortho_ignores_depth(self):
        camera = Camera(position=(0, 0, -10), target=(0, 0, 0), focal=100,
                        frame=(200, 100), projection="ortho", ortho_scale=10)
        near = camera.project((1, 0, 0))
        far = camera.project((1, 0, 8))
        self.assertEqual((near.x, near.y), (far.x, far.y))
        self.assertEqual(near.x, 110.0)

    def test_ortho_scale_follows_distance(self):
        camera = Camera(position=(0, 0, -10), target=(0, 0, 0), focal=100,
                        frame=(200, 100), projection="ortho")
        self.assertAlmostEqual(camera.scale(), 10.0)

    def test_bad_projection(self):
        camera = Camera(position=(0, 0, -10), target=(0, 0, 0), projection="fish")
        with self.assertRaises(ValueError):
            camera.project((0, 0, 0))

    def test_up_parallel_to_forward(self):
        camera = Camera(position=(0, 0, -10), target=(0, 0, 0), up=(0, 0, 1))
        with self.assertRaises(ValueError):
            camera.basis()

    def test_camera_from_dict_defaults(self):
        target = pen()
        camera = camera_from_dict(None, target)
        self.assertEqual(camera.frame, (800.0, 450.0))
        self.assertEqual(camera.projection, "perspective")

    def test_camera_from_dict_frame(self):
        camera = camera_from_dict({"frame": [640, 360], "focal": 500, "projection": "ortho"})
        self.assertEqual(camera.frame, (640.0, 360.0))
        self.assertEqual(camera.focal, 500.0)
        self.assertEqual(camera.projection, "ortho")

    def test_camera_from_dict_bad_projection(self):
        with self.assertRaises(ValueError):
            camera_from_dict({"projection": "isometric"})

    def test_project_points(self):
        camera = Camera(position=(0, 0, -10), target=(0, 0, 0), focal=100,
                        frame=(200, 100))
        results = project_points([(0, 0, 0), (1, 0, 0)], camera)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[1].x, 110.0)

    def test_ortho_views(self):
        views = ortho_views(center=(0, 1, 0), distance=5, focal=500)
        self.assertEqual(views["front"].position, (0.0, 1.0, -5.0))
        self.assertEqual(views["left"].position, (-5.0, 1.0, 0.0))
        self.assertEqual(views["top"].position, (0.0, 6.0, 0.0))
        for camera in views.values():
            self.assertEqual(camera.projection, "ortho")

    def test_left_view_keeps_near_side_on_the_right(self):
        camera = view_camera("left", center=(0, 0, 0), distance=5, focal=100)
        near = camera.project((0, 0, -1))
        far = camera.project((0, 0, 1))
        self.assertGreater(near.x, far.x)

    def test_top_view_keeps_near_side_at_the_bottom(self):
        camera = view_camera("top", center=(0, 0, 0), distance=5, focal=100)
        near = camera.project((0, 0, -1))
        far = camera.project((0, 0, 1))
        self.assertGreater(near.y, far.y)
        left = camera.project((-1, 0, 0))
        right = camera.project((1, 0, 0))
        self.assertLess(left.x, right.x)

    def test_view_camera_bad_name(self):
        with self.assertRaises(ValueError):
            view_camera("back")


class ClipNearTest(unittest.TestCase):
    def test_points_in_front_pass_through(self):
        points = [(-1, -1, 2), (1, -1, 2), (1, 1, 2), (-1, 1, 2)]
        self.assertEqual(clip_near(points, 0.1), points)

    def test_points_behind_are_dropped(self):
        points = [(-1, -1, -2), (1, -1, -2), (1, 1, -2)]
        self.assertEqual(clip_near(points, 0.1), [])

    def test_one_vertex_behind_makes_five(self):
        points = [(-1, -1, -0.5), (1, -1, 0.5), (1, 1, 0.5), (-1, 1, 0.5)]
        clipped = clip_near(points, 0.1)
        self.assertEqual(len(clipped), 5)
        for point in clipped:
            self.assertGreaterEqual(point[2], 0.1 - 1e-9)

    def test_three_vertices_behind_makes_three(self):
        points = [(-1, -1, -0.5), (1, -1, -0.5), (1, 1, -0.5), (-1, 1, 0.5)]
        self.assertEqual(len(clip_near(points, 0.1)), 3)

    def test_winding_is_preserved(self):
        points = [(-1, -1, -0.5), (1, -1, 0.5), (1, 1, 0.5), (-1, 1, 0.5)]
        before = face_normal(points)
        after = face_normal(clip_near(points, 0.1))
        self.assertGreater(sum(a * b for a, b in zip(before, after)), 0.0)

    def test_near_must_be_positive(self):
        with self.assertRaises(ValueError):
            clip_near([(0, 0, 1)], 0)
        with self.assertRaises(ValueError):
            clip_near([(0, 0, 1)], -0.5)

    def test_whole_mesh_behind_camera_draws_nothing(self):
        target = pen()
        camera = Camera(position=(0, 0, 0), target=(0, 0, 1), focal=100)
        stats = render([make_box(1, 1, 1, center=(0, 0, -2))], camera, target)
        self.assertEqual(stats["drawn"], 0)
        self.assertEqual(stats["commands"], 0)
        self.assertEqual(len(paths(target)), 0)

    def test_crossing_face_is_clipped_and_drawn(self):
        quad = Mesh([(-1, -1, -0.5), (1, -1, 0.5), (1, 1, 0.5), (-1, 1, 0.5)],
                    [[0, 1, 2, 3]], color="#8a6a3a")
        quad.cull = False
        camera = Camera(position=(0, 0, 0), target=(0, 0, 1), focal=100,
                        frame=(200, 100), near=0.1)
        target = pen()
        stats = render([quad], camera, target)
        self.assertEqual(stats["drawn"], 1)
        knots = paths(target)[0]["params"]["path"]["subpaths"][0]["knots"]
        self.assertEqual(len(knots), 5)

    def test_near_plane_is_adjustable(self):
        quad = Mesh([(-1, -1, -0.5), (1, -1, 0.5), (1, 1, 0.5), (-1, 1, 0.5)],
                    [[0, 1, 2, 3]], color="#8a6a3a")
        quad.cull = False
        tight = Camera(position=(0, 0, 0), target=(0, 0, 1), focal=100,
                       frame=(200, 100), near=0.1)
        wide = Camera(position=(0, 0, 0), target=(0, 0, 1), focal=100,
                      frame=(200, 100), near=0.6)
        first = pen()
        second = pen()
        self.assertEqual(render([quad], tight, first)["drawn"], 1)
        self.assertEqual(render([quad], wide, second)["drawn"], 0)
        self.assertEqual(Camera().near, 0.001)
        self.assertEqual(camera_from_dict({"near": 0.05}).near, 0.05)
        with self.assertRaises(ValueError):
            camera_from_dict({"near": 0})

    def test_vertex_at_camera_origin_does_not_divide_by_zero(self):
        triangle = Mesh([(0, 0, 0), (1, 0, 1), (0, 1, 1)], [[0, 1, 2]],
                        color="#8a6a3a")
        triangle.cull = False
        camera = Camera(position=(0, 0, 0), target=(0, 0, 1), focal=100,
                        frame=(200, 100))
        target = pen()
        stats = render([triangle], camera, target)
        self.assertEqual(stats["drawn"], 1)
        for item in paths(target):
            for x, y in item["params"]["path"]["subpaths"][0]["knots"]:
                self.assertTrue(math.isfinite(x) and math.isfinite(y))

    def test_empty_face_is_dropped(self):
        # 零面积的面、完全在近平面后的面都不画
        flat = Mesh([(0, 0, 1), (1, 0, 1), (2, 0, 1)], [[0, 1, 2]], color="#8a6a3a")
        flat.cull = False
        behind = Mesh([(-1, -1, -2), (1, -1, -2), (0, 1, -2)], [[0, 1, 2]],
                      color="#8a6a3a")
        behind.cull = False
        camera = Camera(position=(0, 0, 0), target=(0, 0, 1), focal=100,
                        frame=(200, 100))
        target = pen()
        stats = render([flat, behind], camera, target)
        self.assertEqual(stats["drawn"], 0)
        self.assertEqual(stats["culled"], 2)


class RenderTest(unittest.TestCase):
    def test_straight_on_box_shows_one_face(self):
        target = pen()
        camera = Camera(position=(0, 0, -10), target=(0, 0, 0), focal=100,
                        frame=(200, 100))
        stats = render([make_box(1, 1, 1)], camera, target)
        self.assertEqual(stats["faces"], 6)
        self.assertEqual(stats["drawn"], 1)
        self.assertEqual(stats["culled"], 5)
        self.assertEqual(len(paths(target)), 1)
        self.assertEqual(stats["commands"], 1)

    def test_culling_is_relative_to_camera(self):
        target = pen()
        camera = Camera(position=(4, 4, -8), target=(0, 0, 0), focal=200)
        stats = render([make_box(2, 2, 2)], camera, target)
        self.assertGreater(stats["drawn"], 1)
        self.assertLess(stats["drawn"], 6)

    def test_cull_false_keeps_back_faces(self):
        plane = mesh_from_dict({
            "vertices": [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]],
            "faces": [[0, 1, 2, 3]],
        })
        camera = Camera(position=(0, 0, -10), target=(0, 0, 0), focal=100,
                        frame=(200, 100))
        culled = pen()
        self.assertEqual(render([plane], camera, culled)["drawn"], 0)
        plane.cull = False
        kept = pen()
        self.assertEqual(render([plane], camera, kept)["drawn"], 1)

    def test_depth_order_far_first(self):
        target = pen()
        camera = Camera(position=(0, 0, -10), target=(0, 0, 0), focal=200)
        far = make_box(1, 1, 1, center=(0, 0, 2), name="远")
        near = make_box(1, 1, 1, center=(0, 0, -1), name="近")
        render([near, far], camera, target, named=True)
        first = paths(target)[0]["params"]["name"]
        self.assertTrue(first.startswith("远"), first)

    def test_flat_color_passes_through(self):
        target = pen()
        camera = Camera(position=(0, 0, -10), target=(0, 0, 0), focal=100,
                        frame=(200, 100))
        render([make_box(1, 1, 1, color="#8a6a3a")], camera, target)
        self.assertEqual(paths(target)[0]["params"]["fill"], "#8a6a3a")

    def test_role_color_resolves(self):
        target = pen()
        camera = Camera(position=(0, 0, -10), target=(0, 0, 0), focal=100)
        render([make_box(1, 1, 1, color="deep")], camera, target)
        self.assertEqual(paths(target)[0]["params"]["fill"], PALETTES["fresco"]["deep"])

    def test_path_is_closed_without_seal(self):
        target = pen()
        camera = Camera(position=(2, 2, -8), target=(0, 0, 0), focal=200)
        render([make_sphere(1, 8, 4)], camera, target, seal=False)
        self.assertGreater(len(paths(target)), 0)
        for item in paths(target):
            params = item["params"]
            self.assertEqual(params["kind"], "path")
            self.assertIsNone(params["stroke"])
            self.assertTrue(params["path"]["subpaths"][0]["closed"])
            self.assertGreaterEqual(len(params["path"]["subpaths"][0]["knots"]), 3)

    def test_seal_adds_same_color_stroke(self):
        target = pen()
        camera = Camera(position=(2, 2, -8), target=(0, 0, 0), focal=200)
        render([make_sphere(1, 8, 4)], camera, target, seal=True)
        params = paths(target)[0]["params"]
        self.assertEqual(params["stroke"]["color"], params["fill"])
        self.assertGreaterEqual(params["stroke"]["width"], 1)
        self.assertEqual(params["stroke"]["join"], "round")

    def test_camera_inside_box_keeps_inner_walls(self):
        # 相机在盒子里，六面墙只有一面在身后；另外五面裁完继续画，不能整块剔光
        target = pen()
        camera = Camera(position=(0, 0, 0), target=(0, 0, 1), focal=100)
        stats = render([make_box(2, 2, 2, center=(0, 0, 0))], camera, target)
        self.assertEqual(stats["drawn"], 5)
        self.assertEqual(stats["culled"], 1)
        self.assertEqual(len(paths(target)), 5)

    def test_shade_color(self):
        light = {"direction": [0, -1, 0], "ambient": 0.5, "diffuse": 0.5}
        self.assertEqual(shade_color("#808080", (0, 1, 0), light), "#808080")
        self.assertEqual(shade_color("#808080", (0, -1, 0), light), "#404040")

    def test_shade_never_black_or_white(self):
        light = {"direction": [0, -1, 0], "ambient": 0.0, "diffuse": 1.0}
        dark = shade_color("#000000", (0, -1, 0), light)
        bright = shade_color("#ffffff", (0, 1, 0), light)
        self.assertNotEqual(dark, "#000000")
        self.assertNotEqual(bright, "#ffffff")
        self.assertEqual(dark, "#010101")
        self.assertEqual(bright, "#fefefe")

    def test_shade_disabled(self):
        self.assertEqual(shade_color("#808080", (0, 1, 0), False), "#808080")

    def test_bad_light(self):
        with self.assertRaises(ValueError):
            shade_color("#808080", (0, 1, 0), {"direction": [0, 0, 0]})

    def test_new_primitives_render(self):
        target = pen()
        camera = Camera(position=(0, 0, -9), target=(0, 0, 0), focal=200,
                        frame=(200, 100))
        stats = render([
            make_capsule(0.4, 0.8, 12, 4, center=(-1.4, 0, 0), color="mid"),
            make_lathe([(0, -0.6), (0.4, -0.6), (0.25, 0.4), (0.15, 0.6)], 12,
                       center=(0, 0, 0), color="mid"),
            sweep([(1.0, -0.6, 0), (1.4, 0.2, 0), (1.2, 0.8, 0)], [0.12, 0.08, 0.0],
                  sides=8, color="mid"),
        ], camera, target)
        self.assertGreater(stats["drawn"], 3)
        self.assertEqual(stats["commands"], stats["drawn"])

    def test_build_scene(self):
        target = pen(400, 225)
        stats = build(
            {
                "meshes": [
                    {"type": "box", "size": [1, 1, 1], "color": "mid"},
                    {"type": "sphere", "radius": 0.5, "segments": 8, "rings": 4, "color": "mid"},
                ],
                "camera": {"position": [0, 0, -6], "target": [0, 0, 0], "focal": 300},
            },
            target,
        )
        self.assertGreater(stats["drawn"], 1)
        self.assertEqual(stats["commands"], stats["drawn"])
        self.assertEqual(len(paths(target)), stats["drawn"])

    def test_build_requires_meshes(self):
        with self.assertRaises(ValueError):
            build({}, pen())
        with self.assertRaises(ValueError):
            build({"meshes": []}, pen())

    def test_build_rejects_bad_mesh(self):
        with self.assertRaises(ValueError):
            build({"meshes": [{"type": "mesh"}]}, pen())


if __name__ == "__main__":
    unittest.main()
