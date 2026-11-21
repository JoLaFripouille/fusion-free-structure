"""Régression de la proposition géométrique de doubles cornières."""

import importlib
import pathlib
import sys
import types
import unittest
from unittest.mock import patch


ADDIN = pathlib.Path(__file__).resolve().parents[1] / "addin" / "JHR_StructuralMembers_V1"
sys.path.insert(0, str(ADDIN))
from lib import joint_geometry as geo, profile_catalog


def _rectangle(left, right, low, high):
    points = [(left, low), (right, low), (right, high), (left, high)]
    return list(zip(points, points[1:] + points[:1]))


class AngleCleatSuggestionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        adsk = types.ModuleType("adsk")
        adsk.core = types.ModuleType("adsk.core")
        adsk.fusion = types.ModuleType("adsk.fusion")
        with patch.dict(sys.modules, {"adsk": adsk, "adsk.core": adsk.core, "adsk.fusion": adsk.fusion}):
            cls.builder = importlib.import_module("lib.angle_cleat_builder")
        cls.profiles = profile_catalog.discover_profiles(include_custom=False)

    def _member(self, section, start, end, across, up, land):
        profile = next(item for item in self.profiles if item.component_token == section)
        return types.SimpleNamespace(profile_family=profile.family_id, profile_source=profile.relative_path,
                                     anchor="C", path=(start, end), axes=(across, up), land=land)

    @staticmethod
    def _curve_end_data(line):
        start, end = line
        axis = geo.normalize(geo.subtract(end, start))
        return line, (geo.scale(axis, -1.), axis)

    def _suggest(self, rows, *, opposite_land=(.35, 80., -7.5, 7.)):
        upright = (0., 0., 1.)
        main = self._member("IPE240", (-60., 0., 0.), (60., 0., 0.), (0., 1., 0.), upright,
                            (-60., 60., -10., 10.))
        first = self._member("IPE240", (0., 0., 0.), (0., 80., 0.), (1., 0., 0.), upright,
                             (.35, 80., -8., 7.5))
        opposite = self._member("IPE200", (0., 0., 0.), (0., -80., 0.), (-1., 0., 0.),
                                (0., 0., -1.), opposite_land)
        b = self.builder

        def fake_edges(member, *args):
            outline = _rectangle(*member.occurrence.land)
            return [[outline], [outline]]

        with (patch.object(b.joint_builder, "_member_metadata", side_effect=lambda occurrence, role: occurrence),
              patch.object(b.joint_builder, "_linked_curve", side_effect=lambda design, metadata, *args, **kw: metadata.path),
              patch.object(b.joint_builder, "_line_endpoints", side_effect=lambda curve: curve),
              patch.object(b.joint_builder, "_curve_end_data", side_effect=self._curve_end_data),
              patch.object(b.cope_builder, "_profile_axes", side_effect=lambda curve, metadata: metadata.axes),
              patch.object(b, "_web_edges", side_effect=fake_edges)):
            return b.suggest_opposed_double_angle(None, main, first, opposite, self.profiles, rows)

    def test_available_height_runs_nearly_from_cut_to_cut(self):
        plan = self._suggest(0)
        self.assertAlmostEqual(plan.first.cleat_height_cm, 13.9)
        self.assertAlmostEqual(plan.first.vertical_offset_cm, -.25)
        self.assertGreater(plan.first.hole_pattern.row_count, 2)
        self.assertEqual(len(plan.bolt_placements), 4 * plan.first.hole_pattern.row_count)
        self.assertAlmostEqual(plan.opposite.vertical_offset_cm, .25)

    def test_explicit_row_count_is_not_reduced_to_make_the_part_fit(self):
        plan = self._suggest(2)
        self.assertEqual(plan.first.hole_pattern.row_count, 2)
        self.assertAlmostEqual(plan.first.cleat_height_cm, 13.9)
        with self.assertRaisesRegex(ValueError, "rondelles"):
            self._suggest(3, opposite_land=(.35, 80., -2.5, 2.5))

    def test_face_with_hole_yields_two_clear_bands_at_the_washer(self):
        outer = _rectangle(0., 8., -5., 5.)
        hole = _rectangle(2., 3., 1., 2.)
        plain = [[outer], [outer]]
        drilled = [[outer + hole], [outer]]
        self.assertEqual(self.builder._surface_band(plain, 1.5, 3.5, [(-8., 8.)]), [(-5., 5.)])
        self.assertEqual(self.builder._surface_band(drilled, 1.5, 3.5, [(-8., 8.)]),
                         [(-5., 1.), (2., 5.)])


if __name__ == "__main__":
    unittest.main()
