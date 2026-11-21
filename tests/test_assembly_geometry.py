import pathlib
import sys
import unittest


sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "addin" / "JHR_StructuralMembers_V1"))

from lib import assembly_catalog as catalogue, assembly_geometry as geometry


class AssemblyGeometryTests(unittest.TestCase):
    def test_base_hole_coordinates_follow_selected_edge_axes(self):
        template = catalogue.template_for("base_ih")
        for mode, expected in ((0, (45., 55.)), (1, (55., 65.)), (2, (55., 55.)), (3, (45., 65.))):
            with self.subTest(mode=mode):
                dims = geometry.dimensions(template, {
                    "width": 150, "height": 190, "hole_position": mode,
                    "gauge": 90, "pitch": 110, "hole_edge_x": 20, "hole_edge_y": 30,
                })
                holes = geometry.base_holes(dims)
                self.assertEqual({(round(x*10), round(y*10)) for x, y, _ in holes},
                                 {(sx*expected[0], sy*expected[1]) for sx in (-1, 1) for sy in (-1, 1)})

    def test_base_hole_retractions_validate_each_axis(self):
        template = catalogue.template_for("base_ih")
        with self.assertRaisesRegex(ValueError, "en X doit dépasser le rayon"):
            geometry.base_holes(geometry.dimensions(template, {"hole_position": 2, "hole_edge_x": 9}))
        with self.assertRaisesRegex(ValueError, "en Y trop grande"):
            geometry.base_holes(geometry.dimensions(template, {"hole_position": 3, "hole_edge_y": 132}))
        dims = geometry.dimensions(template, {"hole_position": 1, "hole": 0, "hole_edge_x": 0, "hole_edge_y": 0})
        self.assertEqual(geometry.base_holes(dims), ())

    def test_base_overhangs_set_effective_size_offset_and_hole_axes(self):
        template = catalogue.template_for("base_ih")
        settings = {
            "plate_position": 1, "plate_x_minus": 100, "plate_x_plus": 100,
            "plate_y_minus": 100, "plate_y_plus": 50, "hole_position": 1,
            "hole_edge_x": 30, "hole_edge_y": 40,
        }
        dims = geometry.dimensions(template, settings)
        actual = geometry.base_plate_dimensions(dims, 10., 20.)
        self.assertEqual((actual["width"], actual["height"], actual["offset_x"], actual["offset_y"]),
                         (30., 35., 0., -2.5))
        self.assertEqual((dims["width"], dims["height"], dims["offset_y"]), (24., 28., 0.))
        self.assertEqual(geometry.base_holes(actual)[-1][:2], (12., 13.5))
        reversed_y = geometry.base_plate_dimensions(dims, 10., 20., reverse_y=True)
        self.assertEqual(reversed_y["offset_y"], 2.5)
        self.assertEqual(geometry.base_holes(reversed_y), geometry.base_holes(actual))
        free = dict(dims, plate_position=0, offset_y=-4.)
        self.assertIs(geometry.base_plate_dimensions(free, 10., 20., reverse_y=True), free)
        actual = geometry.base_plate_dimensions(dims, 10., 24.)
        self.assertEqual(geometry.base_holes(actual)[-1][:2], (12., 15.5))

    def test_default_haunch_has_four_rows_and_weld_relief(self):
        dims = geometry.dimensions(catalogue.template_for("beam_column_haunch"), {})
        web, flange = geometry.haunch((0, 0, 0), (1, 0, 0), (0, 0, 1), 8.2, -8, dims)
        self.assertEqual(dims["rows"], 4)
        self.assertEqual(dims["top_setback"], .5)
        self.assertEqual(web.outline[:2], ((2., 0), (0, -2.)))
        self.assertLess(flange.normal[2], 0)

    def test_haunch_flats_leave_the_weld_relief_and_sole_in_place(self):
        model = catalogue.template_for("beam_column_haunch")
        dims = geometry.dimensions(model, {"haunch_flat": 10})
        axes = ((0, 0, 0), (1, 0, 0), (0, 0, 1), 8.2, -8)
        old_web, old_sole = geometry.haunch(*axes, {**dims, "haunch_flat": 0.})
        web, sole = geometry.haunch(*axes, dims)
        self.assertEqual(old_web.outline, ((2., 0), (0, -2.), (0, -11.), (22., 0)))
        self.assertEqual(web.outline, ((2., 0), (0, -2.), (0, -10.5), (1., -10.5), (20., -1.), (20., 0)))
        self.assertEqual(sole, old_sole)
        with self.assertRaises(geometry.DimensionError) as caught:
            geometry.haunch(*axes, {**dims, "haunch_flat": 9.})
        self.assertEqual(caught.exception.keys, ("haunch_flat",))

    def test_column_stiffeners_keep_legacy_positions_and_limit_the_haunch_option(self):
        for key in ("beam_column", "beam_column_rake", "beam_column_haunch"):
            model = catalogue.template_for(key)
            with self.subTest(key=key):
                dims = geometry.dimensions(model, {"stiffener": 8})
                self.assertEqual((dims["stiffener"], dims["stiffener_upper"], dims["stiffener_lower"]), (.8, 1, 1))
                self.assertEqual(dims["stiffener_clearance"], .1)
                legacy = catalogue.recorded_parameters(model, {"stiffener": 8})
                self.assertEqual(geometry.dimensions(model, legacy)["stiffener_clearance"], 0.)
                current = catalogue.recorded_parameters(model, {"stiffener": 8, "stiffener_clearance": 2})
                self.assertEqual(geometry.dimensions(model, current)["stiffener_clearance"], .2)
                self.assertEqual("stiffener_haunch" in dims, key == "beam_column_haunch")
                with self.assertRaises(geometry.DimensionError):
                    geometry.dimensions(model, {"stiffener_upper": 2})

    def test_rows_keep_spacing_and_skip_flange(self):
        rows = geometry.bolt_rows(4, 0, 20, 3, blocked=((6, 9), (17, 20.5)))
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(not (6 < y < 9 or 17 < y) for y in rows))
        self.assertTrue(all(b-a >= 3 for a, b in zip(rows, rows[1:])))
        with self.assertRaises(ValueError):
            geometry.bolt_rows(4, 0, 5, 3, blocked=())

    def test_shims_open_toward_the_split_and_match_anchor_axes(self):
        holes = geometry.grid(19, 22, 1.8)
        front, rear = geometry.fork_shims((0, 0, 0), (1, 0, 0), (0, 1, 0),
                                          24, 28, .3, holes, .1)
        self.assertEqual(front.arcs, ((4, (9.5, 12)), (8, (-9.5, 12))))
        self.assertEqual(rear.arcs, ((4, (9.5, -12)), (8, (-9.5, -12))))
        self.assertEqual((len(front.holes), len(rear.holes)), (0, 0))
        self.assertGreater(len(front.display_outline()), len(front.outline))

    def test_optional_base_fixings_preserve_existing_feet(self):
        for template in catalogue.TEMPLATES:
            if not template.key.startswith("base_"):
                continue
            with self.subTest(template=template.key):
                dims = geometry.dimensions(template, {})
                plate = geometry.rectangle(
                    "Pied", (0, 0, 0), (1, 0, 0), (0, 1, 0),
                    dims["width"], dims["height"], dims["thickness"],
                )
                self.assertEqual(geometry.base_fixings(plate, dims), ())

    def test_preset_plate_and_anchors_follow_the_four_hole_axes_and_stack(self):
        dims = geometry.dimensions(catalogue.template_for("base_ih"), {
            "width": 400, "height": 400, "thickness": 15, "shim": 10,
            "gauge": 240, "pitch": 240, "hole": 19,
            "anchor_diameter": 16, "anchor_length": 300, "anchor_projection": 35,
            "preset_thickness": 6, "preset_left": -25, "preset_right": 50,
            "preset_front": -25, "preset_back": 50, "preset_hole": 17, "preset_gap": 4,
        })
        plate = geometry.rectangle(
            "Pied", (1, 2, 3), (0, 1, 0), (0, 0, 1), dims["width"], dims["height"],
            dims["thickness"], geometry.grid(dims["gauge"], dims["pitch"], dims["hole"]),
        )
        preset, *parts = geometry.base_fixings(plate, dims)
        self.assertEqual(len(parts), 12)
        self.assertEqual(preset.origin, (3.9, 5.75, 6.75))
        for (x, y, _), (px, py, diameter), anchor, washer, nut in zip(
            plate.holes, preset.holes, parts[::3], parts[1::3], parts[2::3],
        ):
            point = plate.point(x, y)
            self.assertEqual(preset.point(px, py)[1:], point[1:])
            self.assertAlmostEqual(diameter, 1.7)
            self.assertEqual(anchor.origin, (point[0] - 3.5, *point[1:]))
            self.assertEqual(anchor.thickness_cm, 30.)
            self.assertEqual(anchor.outline[0], (.8, 0.))
            self.assertTrue(len(anchor.arcs) == 4 and not anchor.inherit_material)
            self.assertEqual(washer.origin[1:], point[1:])
            self.assertEqual(nut.origin[1:], point[1:])
            self.assertAlmostEqual(washer.origin[0] + washer.thickness_cm, point[0])
            self.assertAlmostEqual(nut.origin[0] + nut.thickness_cm, washer.origin[0])
            self.assertAlmostEqual(washer.thickness_cm, .3)
            self.assertAlmostEqual(washer.holes[0][2], 1.7)
            self.assertAlmostEqual(nut.thickness_cm, 1.3)
            self.assertGreater(nut.holes[0][2], 1.6)
            self.assertEqual(len(nut.outline), 6)
        self.assertEqual(geometry.base_fixings(plate, dims, include_hardware=False), (preset, *parts[::3]))

    def test_base_fixings_reject_short_rods_and_insufficient_holes(self):
        template = catalogue.template_for("base_ih")
        settings = {"anchor_diameter": 16, "preset_thickness": 6, "preset_hole": 17}
        def prepare(**overrides):
            dims = geometry.dimensions(template, dict(settings, **overrides))
            plate = geometry.rectangle(
                "Pied", (0, 0, 0), (1, 0, 0), (0, 1, 0),
                dims["width"], dims["height"], dims["thickness"],
                geometry.grid(dims["gauge"], dims["pitch"], dims["hole"]),
            )
            return geometry.base_fixings(plate, dims)

        with self.assertRaisesRegex(ValueError, "trous de pied"):
            prepare(hole=15)
        with self.assertRaisesRegex(ValueError, "trous de préscellement"):
            prepare(preset_hole=15)
        with self.assertRaisesRegex(ValueError, "empilement"):
            prepare(anchor_length=50, shim=3)
        with self.assertRaisesRegex(ValueError, "dépassement d’au moins 21 mm"):
            prepare(anchor_projection=20)
        with self.assertRaisesRegex(ValueError, "ne couvre pas"):
            prepare(hole=30)
        with self.assertRaisesRegex(ValueError, "appui des rondelles"):
            prepare(gauge=220)
        with self.assertRaisesRegex(ValueError, "déborde"):
            prepare(preset_left=-30)

    def test_anchor_hardware_preserves_diameters_outside_bolt_catalogue(self):
        dims = geometry.dimensions(catalogue.template_for("base_ih"), {"anchor_diameter": 14})
        plate = geometry.rectangle("Pied", (0, 0, 0), (1, 0, 0), (0, 1, 0), 24, 28, 1.2,
                                   geometry.grid(19, 22, 1.8))
        rod, washer, nut, *_ = geometry.base_fixings(plate, dims)
        self.assertAlmostEqual(rod.outline[0][0], .7)
        self.assertAlmostEqual(washer.outline[0][0], 1.3125)
        self.assertEqual(nut.name, "Écrou d’ancrage M14")


if __name__ == "__main__":
    unittest.main()
