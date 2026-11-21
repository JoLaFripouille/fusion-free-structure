import pathlib
import sys
from types import SimpleNamespace as Entity
import unittest
from unittest.mock import patch


ADDIN = pathlib.Path(__file__).resolve().parents[1] / "addin" / "JHR_StructuralMembers_V1"
sys.path.insert(0, str(ADDIN))

import lib
from lib import countersink_preparation as preparation, fastener_geometry as geometry


def cast_kind(kind):
    return Entity(cast=lambda entity: entity if getattr(entity, "kind", None) == kind else None)


class CountersinkPreparationTests(unittest.TestCase):
    def setUp(self):
        core = Entity(Circle3D=cast_kind("circle"), Cylinder=cast_kind("cylinder"), Plane=cast_kind("plane"))
        fusion = Entity(BRepEdge=cast_kind("edge"), BRepFace=cast_kind("face"))
        creator = Entity(read_hole=lambda _: geometry.Hole((4., 5., 3.), (0., 0., 1.), 1.4), point=tuple)
        self.enterContext(patch.dict(sys.modules, {"adsk": Entity(core=core, fusion=fusion),
                                                   "adsk.core": core, "adsk.fusion": fusion,
                                                   "lib.fastener_creator": creator}))
        self.enterContext(patch.object(lib, "fastener_creator", creator, create=True))

    def hole(self, wall_depth, through=True):
        body = object()
        wall = Entity(kind="face", body=body, tempId=1, geometry=Entity(kind="cylinder"))
        entry = Entity(kind="face", body=body, tempId=2, geometry=Entity(kind="plane", normal=(0., 0., -1.)),
                       pointOnFace=(4., 3., 3.), evaluator=Entity(getNormalAtPoint=lambda _: (True, (0., 0., -1.))))
        normal = (0., 0., 1. if through else -1.)
        exit_face = Entity(kind="face", body=body, tempId=3, geometry=Entity(kind="plane", normal=normal),
                           pointOnFace=(4., 3., 3. + wall_depth),
                           evaluator=Entity(getNormalAtPoint=lambda _: (True, normal)))
        entry_edge = Entity(kind="edge", geometry=Entity(kind="circle", radius=.7, center=(4., 5., 3.)),
                            faces=[wall, entry])
        exit_edge = Entity(kind="edge", geometry=Entity(kind="circle", radius=.7, center=(4., 5., 3. + wall_depth)),
                           faces=[wall, exit_face])
        wall.edges = [entry_edge, exit_edge]
        return wall, entry, entry_edge, exit_face

    def test_infers_both_faces_from_opening_and_sizes_for_iso_head(self):
        _, entry, rim, exit_face = self.hole(1.8)
        result = preparation.plan(rim, None, 12.)
        self.assertIs(result.head_face, entry)
        self.assertIs(result.backing_face, exit_face)
        self.assertEqual(result.hole.center, (4., 5., 3.))
        self.assertEqual(result.hole.axis, (0., 0., 1.))
        self.assertAlmostEqual(result.hole.opening_diameter_cm, 2.688)
        self.assertAlmostEqual(result.hole.depth_cm, .644)
        self.assertAlmostEqual(result.hole.head_depth(1.2), .744)

    def test_blind_hole_floor_is_not_a_nut_support(self):
        wall, entry, _, floor = self.hole(1.8, through=False)
        self.assertIsNone(preparation.plan(wall, entry, 12.).backing_face)
        with self.assertRaisesRegex(ValueError, "face extérieure"):
            preparation.plan(wall, floor, 12.)

    def test_thin_wall_does_not_allow_the_cut(self):
        wall, entry, _, _ = self.hole(.6)
        with self.assertRaisesRegex(ValueError, "paroi est trop mince"):
            preparation.plan(wall, entry, 12.)


if __name__ == "__main__":
    unittest.main()
