# -*- coding: utf-8 -*-
import unittest
from photocraft_draw.commands import Pen
from photocraft_draw.components import block, crabapple
from photocraft_draw.palette import resolve_palette

class ColourParamsTest(unittest.TestCase):
    def pen(self):
        return Pen(800, 1200, ref_width=800, palette=resolve_palette('fresco'))

    def test_horse_colours_override_role_defaults(self):
        pen = self.pen()
        block.build_capsule_horse({'root': [400, 600], 'length': 200,
            'body': 'mid', 'dark': 'line',
            'colors': {'body': '#B27D4B', 'dark': '#362C26'}}, pen)
        fills = [cmd['params'].get('fill') for cmd in pen.commands]
        self.assertIn('#B27D4B', fills)
        self.assertIn('#362C26', fills)
        self.assertNotIn('mid', fills)

    def test_rider_dark_colour_reaches_tail_and_mane(self):
        pen = self.pen()
        block.build_capsule_rider({'root': [400, 600], 'length': 200,
            'colors': {'dark': '#895935', 'skin': '#E4A77E'}}, pen)
        names = [cmd['params'].get('name') for cmd in pen.commands]
        colours = [cmd['params'].get('fill') for cmd in pen.commands]
        pairs = dict(zip(names, colours))
        self.assertEqual(pairs['鬃毛下'], '#895935')
        self.assertEqual(pairs['尾 1'], '#895935')
        self.assertEqual(pairs['头'], '#E4A77E')

    def test_tree_background_and_shadow_accepts_explicit_colors(self):
        pen = self.pen()
        crabapple.build_backdrop({'width': 800, 'height': 1200,
                                    'colors': {'sky': '#A8C2C9'}}, pen)
        crabapple.build_tree({'root': [400, 900], 'height': 300,
                                'colors': {'shadow': '#B5A082'}}, pen)
        names = [cmd['params'].get('name') for cmd in pen.commands]
        colours = [cmd['params'].get('fill') for cmd in pen.commands]
        pairs = dict(zip(names, colours))
        self.assertEqual(pairs['天光'], '#A8C2C9')
        self.assertEqual(pairs['树影'], '#B5A082')

    def test_shadow_fill_takes_precedence_over_color_alias(self):
        pen = self.pen()
        block.build_soft_shadow({'center': [400, 900], 'rx': 40, 'ry': 10,
                                   'color': 'bg', 'fill': '#10151A'}, pen)
        self.assertEqual(pen.commands[0]['params']['fill'], '#10151A')


if __name__ == '__main__':
    unittest.main()