import math
import sys
import unittest
from pathlib import Path


ADDIN = Path(__file__).resolve().parents[1] / "addin" / "JHR_StructuralMembers_V1"
sys.path.insert(0, str(ADDIN))

from lib import ipe100


class Ipe100GeometryTests(unittest.TestCase):
    def test_source_extents_are_exact(self):
        xs = [vertex[0] for vertex in ipe100.VERTICES_MM]
        ys = [vertex[1] for vertex in ipe100.VERTICES_MM]
        self.assertEqual(max(xs) - min(xs), 55.0)
        self.assertEqual(max(ys) - min(ys), 100.0)

    def test_center_anchor_is_origin(self):
        segments = ipe100.segments_mm(anchor=(0.0, 50.0))
        points = [point for segment in segments for point in (segment["start"], segment["end"])]
        self.assertEqual(min(point[0] for point in points), -27.5)
        self.assertEqual(max(point[0] for point in points), 27.5)
        self.assertEqual(min(point[1] for point in points), -50.0)
        self.assertEqual(max(point[1] for point in points), 50.0)

    def test_contour_is_sequential_and_closed(self):
        segments = ipe100.segments_mm()
        self.assertEqual(len(segments), 16)
        for first, second in zip(segments, segments[1:] + segments[:1]):
            self.assertAlmostEqual(first["end"][0], second["start"][0], places=9)
            self.assertAlmostEqual(first["end"][1], second["start"][1], places=9)

    def test_primitive_counts_and_radii(self):
        segments = ipe100.segments_mm()
        lines = [item for item in segments if item["type"] == "LINE"]
        arcs = [item for item in segments if item["type"] == "ARC"]
        self.assertEqual(len(lines), 12)
        self.assertEqual(len(arcs), 4)
        for arc in arcs:
            self.assertAlmostEqual(abs(arc["sweep"]), math.pi / 2, places=9)
            self.assertAlmostEqual(arc["radius"], 7.0, places=9)

    def test_centimeter_conversion(self):
        segments = ipe100.segments_cm()
        points = [point for segment in segments for point in (segment["start"], segment["end"])]
        self.assertEqual(min(point[0] for point in points), -2.75)
        self.assertEqual(max(point[1] for point in points), 5.0)


if __name__ == "__main__":
    unittest.main()
