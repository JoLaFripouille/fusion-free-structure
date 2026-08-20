from __future__ import annotations

import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
ADDIN = ROOT / "addin" / "JHR_StructuralMembers_V1"
sys.path.insert(0, str(ADDIN))

from lib import angle_cleat_geometry, bolt_geometry, bolt_specs


class BoltGeometryTests(unittest.TestCase):
    def setUp(self):
        self.placements = angle_cleat_geometry.build_double_angle_frames(
            primary_web_face_point=(0.0, 0.3, 0.0),
            secondary_profile_x_axis=(1.0, 0.0, 0.0),
            vertical_axis=(0.0, 0.0, 1.0),
            toward_secondary_axis=(0.0, 1.0, 0.0),
            secondary_web_face_offsets_cm=(-0.25, 0.25),
            cleat_height_cm=10.0,
            vertical_offset_cm=0.0,
        )
        self.pattern = angle_cleat_geometry.build_hole_pattern(
            10.0, 5.0, 5.0, 1.8, 2, 5.0, 3.0, 3.0
        )
        self.spec = bolt_specs.default_bolt_spec()

    def _placements(self):
        return bolt_geometry.build_angle_cleat_bolt_placements(
            placements=self.placements,
            hole_pattern=self.pattern,
            primary_axis=(0.0, 1.0, 0.0),
            secondary_axis=(1.0, 0.0, 0.0),
            primary_web_thickness_cm=0.9,
            secondary_web_thickness_cm=0.5,
            angle_thickness_cm=0.5,
            spec=self.spec,
        )

    def test_two_rows_create_six_complete_bolt_positions(self):
        placements = self._placements()
        self.assertEqual(len(placements), 6)
        self.assertEqual(
            tuple(item.connection for item in placements),
            ("principale",) * 4 + ("secondaire",) * 2,
        )
        self.assertEqual(
            tuple(item.side for item in placements[-2:]),
            ("traversant", "traversant"),
        )

    def test_primary_and_secondary_grips_drive_safe_standard_lengths(self):
        placements = self._placements()
        for placement in placements[:4]:
            self.assertAlmostEqual(placement.grip_length_cm, 1.4)
            self.assertAlmostEqual(placement.bolt_length_cm, 4.0)
        for placement in placements[4:]:
            self.assertAlmostEqual(placement.grip_length_cm, 1.5)
            self.assertAlmostEqual(placement.bolt_length_cm, 4.0)

    def test_secondary_bolt_starts_outside_left_angle_and_crosses_both_sides(self):
        bolt = self._placements()[4]
        self.assertEqual(bolt.z_axis, (1.0, 0.0, 0.0))
        self.assertAlmostEqual(bolt.origin[0], -1.05)
        self.assertAlmostEqual(bolt.origin[1], 3.3)
        self.assertAlmostEqual(bolt.origin[2], -2.5)

    def test_frames_are_right_handed_for_both_bolt_directions(self):
        for placement in self._placements():
            cross = angle_cleat_geometry.joint_geometry.cross(
                placement.x_axis,
                placement.y_axis,
            )
            for actual, expected in zip(cross, placement.z_axis):
                self.assertAlmostEqual(actual, expected)

    def test_hole_must_be_larger_than_the_nominal_bolt(self):
        bolt_specs.validate_hole_diameter(self.spec, 1.8)
        with self.assertRaisesRegex(ValueError, "trop petit"):
            bolt_specs.validate_hole_diameter(self.spec, 1.6)


if __name__ == "__main__":
    unittest.main()
