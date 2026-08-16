import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADDIN = ROOT / "addin" / "JHR_StructuralMembers_V1"
sys.path.insert(0, str(ADDIN))

from lib import ipe100


def _dxf_vertex_data(path):
    lines = path.read_text(encoding="ascii").splitlines()
    pairs = [
        (lines[index].strip(), lines[index + 1].strip())
        for index in range(0, len(lines) - 1, 2)
    ]
    vertices = []
    current = None
    for code, value in pairs:
        if code == "0":
            if current and current["type"] == "VERTEX":
                vertices.append(current)
            current = {"type": value}
        elif current and current["type"] == "VERTEX":
            if code == "10":
                current["x"] = float(value)
            elif code == "20":
                current["y"] = float(value)
            elif code == "42":
                current["bulge"] = float(value)
    if current and current["type"] == "VERTEX":
        vertices.append(current)
    return vertices


class Ipe100DxfTests(unittest.TestCase):
    def setUp(self):
        self.dxf_path = ROOT / "profiles" / "IPE" / "IPE_100.dxf"

    def test_repository_profile_path_is_resolved(self):
        self.assertEqual(ipe100.resolve_dxf_path(ADDIN), self.dxf_path)

    def test_standalone_addin_profile_path_is_resolved_first(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            addin_root = Path(temp_dir)
            local_dxf = addin_root / "profiles" / "IPE" / "IPE_100.dxf"
            local_dxf.parent.mkdir(parents=True)
            local_dxf.write_text("DXF TEST", encoding="ascii")
            self.assertEqual(ipe100.resolve_dxf_path(addin_root), local_dxf)

    def test_source_dxf_extents_are_exact(self):
        vertices = _dxf_vertex_data(self.dxf_path)
        self.assertEqual(len(vertices), 16)
        xs = [vertex["x"] for vertex in vertices]
        ys = [vertex["y"] for vertex in vertices]
        self.assertAlmostEqual(max(xs) - min(xs), ipe100.WIDTH_MM, places=9)
        self.assertAlmostEqual(max(ys) - min(ys), ipe100.HEIGHT_MM, places=9)

    def test_source_origin_and_center_anchor_offset(self):
        vertices = _dxf_vertex_data(self.dxf_path)
        xs = [vertex["x"] for vertex in vertices]
        ys = [vertex["y"] for vertex in vertices]
        self.assertAlmostEqual(min(xs), -ipe100.WIDTH_MM / 2.0, places=9)
        self.assertAlmostEqual(max(xs), ipe100.WIDTH_MM / 2.0, places=9)
        self.assertAlmostEqual(min(ys), 0.0, places=9)
        self.assertAlmostEqual(max(ys), ipe100.HEIGHT_MM, places=9)
        self.assertEqual(ipe100.IMPORT_OFFSET_CM, (0.0, -5.0))

    def test_source_contains_four_fillets(self):
        vertices = _dxf_vertex_data(self.dxf_path)
        fillets = [vertex["bulge"] for vertex in vertices if "bulge" in vertex]
        self.assertEqual(len(fillets), 4)
        for bulge in fillets:
            self.assertAlmostEqual(bulge, -0.414213562373095, places=12)


if __name__ == "__main__":
    unittest.main()
