from contextlib import nullcontext
import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch


ADAPTER = (Path(__file__).resolve().parents[1] / "addin" / "JHR_StructuralMembers_V1"
           / "lib" / "mcp_operations.py")


def load_adapter():
    adsk = ModuleType("adsk")
    adsk.core = ModuleType("adsk.core")
    adsk.fusion = ModuleType("adsk.fusion")
    adsk.core.Cone = SimpleNamespace(cast=lambda geometry: geometry if geometry == "cone" else None)
    for name in ("BRepFace", "BRepEdge", "BRepBody", "Occurrence"):
        setattr(adsk.fusion, name, SimpleNamespace(
            cast=lambda entity, kind=name: entity if getattr(entity, "kind", None) == kind else None))
    package = ModuleType("_mcp_test_fasteners")

    def stub(name):
        if name.startswith("__"):
            raise AttributeError(name)
        module = Mock()
        setattr(package, name, module)
        return module

    package.__getattr__ = stub
    spec = importlib.util.spec_from_file_location(package.__name__ + ".mcp_operations", ADAPTER)
    adapter = importlib.util.module_from_spec(spec)
    modules = {"adsk": adsk, "adsk.core": adsk.core, "adsk.fusion": adsk.fusion,
               package.__name__: package}
    with patch.dict(sys.modules, modules):
        spec.loader.exec_module(adapter)
    return adapter, package, modules


class McpFastenerTests(unittest.TestCase):
    def setUp(self):
        self.adapter, self.lib, modules = load_adapter()
        module_patch = patch.dict(sys.modules, modules)
        module_patch.start()
        self.addCleanup(module_patch.stop)
        self.head = SimpleNamespace(kind="BRepFace", geometry="plane")
        self.nut = SimpleNamespace(kind="BRepFace", geometry="plane")
        self.edge = SimpleNamespace(kind="BRepEdge", geometry="circle")
        self.cone = SimpleNamespace(kind="BRepFace", geometry="cone")
        self.body = SimpleNamespace(kind="BRepBody")
        self.design = SimpleNamespace(
            rootComponent=object(), timeline=object(), findEntityByToken=lambda key: [self.entities[key]])
        self.entities = {"head": self.head, "nut": self.nut, "hole": self.edge,
                         "cone": self.cone, "body": self.body}
        for entity in self.entities.values():
            entity.isValid = True
        self.adapter.active_design = Mock(return_value=self.design)

    def test_preview_measures_countersink_without_creating_it(self):
        hole = object()
        self.lib.countersink_preparation.plan.return_value = SimpleNamespace(
            head_face=self.head, backing_face=self.nut, hole=hole)
        self.lib.fastener_geometry.plan_modeled_fasteners.return_value = (
            None, (SimpleNamespace(countersink=hole),), 0, 25.)
        result = self.adapter.place_bolts("doc", ["hole"], None, None, 12, head="TF",
                                         prepare_countersink=True, preview=True, nut_washer=False)
        self.assertEqual(result["countersinks_to_prepare"], 1)
        self.assertEqual(result["length_mm"], 25.)
        self.assertFalse(self.lib.fastener_geometry.plan_modeled_fasteners.call_args.kwargs["nut_washer"])
        self.lib.countersink_preparation.apply.assert_not_called()
        self.lib.simple_fastener_creator.create_modeled_fasteners.assert_not_called()

    def test_countersink_liaison_uses_new_face(self):
        hole = object()
        pose = SimpleNamespace(countersink=hole)
        self.lib.countersink_preparation.plan.return_value = SimpleNamespace(hole=hole, head_face=self.head,
                                                                            backing_face=self.nut)
        self.lib.fastener_geometry.plan_modeled_fasteners.return_value = (None, (pose,), 1, 25.)
        self.lib.countersink_preparation.apply.return_value = (self.cone, (Mock(),))
        self.lib.timeline_groups.defer_grouping.return_value = nullcontext()
        occurrence = object()

        def create(*args, bind_to_hole, **kwargs):
            bind_to_hole(pose, occurrence)
            return {"created": 1, "occupied": 0}

        self.lib.simple_fastener_creator.create_modeled_fasteners.side_effect = create
        result = self.adapter.place_bolts("doc", ["hole"], "head", "nut", 12, head="TF",
                                         prepare_countersink=True, link_to_hole=True)
        self.assertEqual((result["created"], result["occupied"]), (1, 1))
        self.lib.fastener_hole_link.source_for_pose.assert_called_once_with([self.cone], pose, "TF")
        self.lib.fastener_hole_link.bind.assert_called_once_with(
            self.design, occurrence, pose, self.lib.fastener_hole_link.source_for_pose.return_value)

    def test_existing_prototype_keeps_its_hardware(self):
        self.lib.fastener_geometry.plan_placements.return_value = ((), 1)
        self.lib.fastener_creator.create_fasteners.return_value = {"created": 0, "occupied": 0}
        result = self.adapter.place_bolts("doc", ["hole"], "head", "nut", 12, 30,
                                         prototype_token="body", prototype_length_mm=25)
        self.lib.fastener_creator.read_prototype.assert_called_once_with(self.body, 12, 25)
        self.lib.simple_fastener_creator.create_modeled_fasteners.assert_not_called()
        self.assertEqual(result["occupied"], 1)

    def test_tapped_and_rivkle_settings_pass_to_native_operations(self):
        face = SimpleNamespace(kind="BRepFace", geometry="cylinder", isValid=True)
        self.entities["hole"] = face
        self.adapter.place_tapped_screw("doc", "hole", "head", 12, head="TF", length_mm=28,
                                       prepare_countersink=True, preview=True, link_to_hole=True)
        self.lib.tapped_fastener.place.assert_called_once_with(
            self.design, face, self.head, 12, None, False, True, head_washer=None,
            length_mm=28, head="TF", prepare_countersink=True, link_to_hole=True)
        self.adapter.place_rivet_nut("doc", "hole", "head", 6, screw_washer=False, link_to_hole=True)
        self.assertFalse(self.lib.rivet_nut.place.call_args.kwargs["screw_washer"])
        self.assertTrue(self.lib.rivet_nut.place.call_args.kwargs["link_to_hole"])
        self.adapter.attach_rivet_screw("doc", "body", support_face_token="head", screw_washer=False)
        self.lib.rivet_nut.attach_screw.assert_called_once_with(
            self.design, self.body, support_face=self.head, screw_head="CHC", screw_length_mm=None,
            screw_stack_mm=0., blind_clearance_mm=None, screw_washer=False, preview=False)


if __name__ == "__main__":
    unittest.main()
