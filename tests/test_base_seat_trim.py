import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1] / "addin" / "JHR_StructuralMembers_V1"
sys.path.insert(0, str(ROOT))

import lib


def load_trim():
    spec = importlib.util.spec_from_file_location("lib._base_seat_trim_test", ROOT / "lib/base_seat_trim.py")
    module = importlib.util.module_from_spec(spec)
    with patch.object(lib, "joint_builder", SimpleNamespace(_line_endpoints=lambda curve: curve), create=True):
        spec.loader.exec_module(module)
    return module


class BaseSeatTrimTests(unittest.TestCase):
    def setUp(self):
        self.trim = load_trim()

    def test_contact_is_measured_inward_from_either_skeleton_endpoint(self):
        bottom = (0., 0., 5.)
        top = (0., 0., 105.)
        cases = (
            ((bottom, top), bottom, (0., 0., 1.), 0, (0., 0., 6.2)),
            ((top, bottom), bottom, (0., 0., 1.), 1, (0., 0., 6.2)),
            ((bottom, top), top, (0., 0., -1.), 1, (0., 0., 103.8)),
            (((0., 5., 0.), (0., 105., 0.)), (0., 5., 0.), (0., 1., 0.), 0, (0., 6.2, 0.)),
        )
        for path, origin, normal, index, contact in cases:
            with self.subTest(path=path, origin=origin):
                post = SimpleNamespace(curve=path)
                plate = SimpleNamespace(normal=normal, origin=origin, thickness_cm=1.2)
                result = self.trim._seat_geometry(post, plate)
                self.assertEqual(index, result[0])
                self.assertEqual(contact, result[-1])

    def test_plate_cannot_consume_the_entire_post(self):
        post = SimpleNamespace(curve=((0., 0., 5.), (0., 0., 5.5)))
        plate = SimpleNamespace(normal=(0., 0., 1.), origin=(0., 0., 5.), thickness_cm=1.2)
        with self.assertRaisesRegex(ValueError, "about valide"):
            self.trim._seat_geometry(post, plate)

    def test_plate_must_be_perpendicular_to_the_path(self):
        post = SimpleNamespace(curve=((0., 0., 5.), (0., 0., 105.)))
        plate = SimpleNamespace(normal=(1., 0., 0.), origin=(0., 0., 5.), thickness_cm=1.2)
        with self.assertRaisesRegex(ValueError, "perpendiculaire"):
            self.trim._seat_geometry(post, plate)


if __name__ == "__main__":
    unittest.main()
