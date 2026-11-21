from pathlib import Path
import sys
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "addin" / "JHR_StructuralMembers_V1"))

from lib import assembly_catalog, assembly_geometry, base_gusset_geometry


class BaseGussetTests(unittest.TestCase):
    def evaluate(self, parameters, anchor_washers=False):
        dims = assembly_geometry.dimensions(
            assembly_catalog.template_for("base_ih"),
            dict({"width": 300, "height": 340, "gauge": 240, "pitch": 260}, **parameters),
        )
        plate = assembly_geometry.rectangle(
            "Platine", (dims["offset_x"], dims["offset_y"], 0.),
            (1., 0., 0.), (0., 1., 0.), dims["width"], dims["height"], dims["thickness"],
            assembly_geometry.grid(dims["gauge"], dims["pitch"], dims["hole"]),
        )
        return base_gusset_geometry.foot_gussets(
            plate, 10., 20., dims, ((-9.5, 1.), (9.5, 1.)), anchor_washers=anchor_washers,
        )

    def test_existing_web_gussets_keep_default_auto_width(self):
        gussets = self.evaluate({"gusset": 6, "offset_y": -20})
        self.assertEqual(len(gussets), 2)
        self.assertEqual([g.name for g in gussets], ["Gousset de pied"] * 2)
        self.assertEqual(gussets[0].outline, ((0., 0.), (9., 0.), (9., 1.), (1., 7.), (0., 7.)))
        self.assertEqual(gussets[1].outline, ((0., 0.), (5., 0.), (5., 1.), (1., 7.), (0., 7.)))

    def test_flange_gussets_add_to_web_with_separate_dimensions_and_relief(self):
        web0, web1, *flanges = self.evaluate({
            "gusset": 6, "gusset_width": 45, "gusset_height": 60, "gusset_chamfer": 8, "gusset_flat": 5,
            "flange_gusset": 8, "flange_gusset_width": 40, "flange_gusset_height": 90,
            "flange_gusset_chamfer": 10, "flange_gusset_flat": 15,
        })
        self.assertEqual(len(flanges), 4)
        self.assertEqual(web0.outline, ((.8, 0.), (4.5, 0.), (4.5, .5), (.5, 6.), (0., 6.), (0., .8)))
        self.assertEqual(web1.outline, web0.outline)
        self.assertEqual(flanges[0].outline, ((1., 0.), (4., 0.), (4., 1.5), (1.5, 9.), (0., 9.), (0., 1.)))
        self.assertEqual([f.name for f in flanges], ["Gousset d’aile de pied"] * 4)
        centres = {(
            f.origin[0], round(f.origin[1] + f.normal[1]*f.thickness_cm/2, 8)
        ) for f in flanges}
        self.assertEqual(centres, {(-5., -9.5), (-5., 9.5), (5., -9.5), (5., 9.5)})

    def test_recorded_legacy_gussets_keep_their_original_contour(self):
        template = assembly_catalog.template_for("base_ih")
        legacy = assembly_catalog.recorded_parameters(template, {"gusset": 6, "flange_gusset": 8})
        self.assertEqual(legacy["gusset_flat"], 0)
        self.assertEqual(legacy["flange_gusset_flat"], 0)
        self.assertEqual(self.evaluate(legacy)[0].outline, ((0., 0.), (7., 0.), (0., 7.)))
        current = assembly_catalog.recorded_parameters(template, {"gusset_flat": 10, "flange_gusset_flat": 7})
        self.assertEqual((current["gusset_flat"], current["flange_gusset_flat"]), (10, 7))

    def test_rejects_dimensions_and_relief_that_lose_bearing(self):
        with self.assertRaisesRegex(ValueError, "débord de platine"):
            self.evaluate({"gusset": 6, "gusset_width": 71})
        with self.assertRaisesRegex(ValueError, "chanfrein de soudure"):
            self.evaluate({"gusset": 6, "gusset_width": 20, "gusset_chamfer": 20})
        with self.assertRaisesRegex(ValueError, "méplat doit être inférieur"):
            self.evaluate({"gusset": 6, "gusset_width": 20, "gusset_flat": 20})
        with self.assertRaisesRegex(ValueError, "chant d’appui"):
            self.evaluate({"flange_gusset": 12})
        with self.assertRaisesRegex(ValueError, "déborde du contour"):
            self.evaluate({"flange_gusset": 8, "chamfer": 80, "hole": 0})

    def test_hole_check_includes_washers_when_requested(self):
        parameters = {"flange_gusset": 8, "pitch": 224, "anchor_diameter": 16}
        self.assertEqual(len(self.evaluate(parameters)), 4)
        with self.assertRaisesRegex(ValueError, "perçage ou une rondelle"):
            self.evaluate(parameters, anchor_washers=True)

    def test_small_nonintersecting_gap_is_checked_against_configured_clearance(self):
        parameters = {"flange_gusset": 8, "pitch": 220}
        with self.assertRaisesRegex(ValueError, "minimum demandé 3 mm"):
            self.evaluate(parameters)
        template = assembly_catalog.template_for("base_ih")
        legacy = assembly_catalog.recorded_parameters(template, parameters)
        self.assertEqual(len(self.evaluate(legacy)), 4)
        self.assertEqual(len(self.evaluate(dict(parameters, pitch=224))), 4)


if __name__ == "__main__":
    unittest.main()
