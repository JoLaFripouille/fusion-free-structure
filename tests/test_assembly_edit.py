import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1] / "addin" / "JHR_StructuralMembers_V1"
sys.path.insert(0, str(ROOT))

import lib
from lib import assembly_catalog, assembly_geometry


def load_editor():
    class Occurrence:
        @staticmethod
        def cast(entity):
            return entity if getattr(entity, "is_occurrence", False) else None

    core = ModuleType("adsk.core")
    fusion = ModuleType("adsk.fusion")
    fusion.Occurrence = Occurrence
    adsk = ModuleType("adsk")
    adsk.core, adsk.fusion = core, fusion
    mechanism = ModuleType("lib.assembly_operations")
    mechanism.ATTRIBUTE_GROUP = "EI_JHR_Assembly"
    mechanism.AssemblyPlan = SimpleNamespace
    mechanism.joints = SimpleNamespace(_line_endpoints=lambda curve: curve)
    mechanism._member = lambda design, occurrence, role: SimpleNamespace(curve=occurrence.curve)
    package = "_jhr_edit_smoke"
    spec = importlib.util.spec_from_file_location(package + ".lib._editor_test", ROOT / "lib/assembly_edit.py")
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"adsk": adsk, "adsk.core": core, "adsk.fusion": fusion, spec.name: module,
                                  package + ".lib": lib}):
        with patch.object(lib, "assembly_operations", mechanism, create=True):
            spec.loader.exec_module(module)
    return module


class AssemblyEditingTests(unittest.TestCase):
    def setUp(self):
        self.editor = load_editor()
        self.marker = SimpleNamespace(value=json.dumps({
            "kind": "base_ih", "members": ["source"], "base_end_index": 1, "parameters_mm": {"width": 300},
        }))
        attributes = SimpleNamespace(itemByName=lambda group, key: self.marker)
        self.group = SimpleNamespace(component=SimpleNamespace(attributes=attributes), assemblyContext=None,
                                     is_occurrence=True)
        self.post = SimpleNamespace(is_occurrence=True, isValid=True, curve=((0, 0, 0), (0, 0, 100)))
        root = SimpleNamespace(allOccurrencesByComponent=lambda component: SimpleNamespace(count=1))
        self.design = SimpleNamespace(rootComponent=root, findEntityByToken=lambda token: [self.post])

    def test_selected_plate_returns_original_foot_type_and_parameters(self):
        target = self.editor.read(self.design, SimpleNamespace(assemblyContext=self.group))
        self.assertIs(self.group, target.group)
        self.assertEqual("base_ih", target.template.key)
        self.assertEqual((self.post,), target.occurrences)
        self.assertEqual(300, target.parameters_mm["width"])
        self.assertEqual(12, target.parameters_mm["thickness"])
        self.assertTrue(target.alternate)
        self.assertTrue(target.writable)

    def test_historical_anchor_style_is_retained(self):
        payload = json.loads(self.marker.value)
        payload["parameters_mm"]["anchor_diameter"] = 16
        self.marker.value = json.dumps(payload)
        target = self.editor.read(self.design, self.group)
        self.assertFalse(self.editor._use_hardware(target, {"anchor_diameter": 12}))
        payload["parameters_mm"]["anchor_diameter"] = 0
        self.marker.value = json.dumps(payload)
        target = self.editor.read(self.design, self.group)
        self.assertTrue(self.editor._use_hardware(target, {"anchor_diameter": 16}))

    def test_jarret_flat_edit_reworks_only_the_web(self):
        from dataclasses import dataclass, replace

        @dataclass(frozen=True)
        class Plate:
            outline: tuple
            origin: tuple = (0., 0., 0.)
            u: tuple = (1., 0., 0.)
            v: tuple = (0., 1., 0.)
            holes: tuple = ()
            thickness_cm: float = .8

        fixed, web_part, sole, bolts = object(), object(), object(), object()
        group = SimpleNamespace(childOccurrences=(fixed, web_part, sole, bolts))
        normal = Plate(((0, 0), (0, 10), (5, 0)))
        flat = replace(normal, outline=((0, 0), (0, 9), (1, 8), (5, 0)))
        before = SimpleNamespace(plates=(normal, normal, normal))
        after = SimpleNamespace(plates=(normal, flat, normal), settings_mm={"haunch_flat": 10},
                                alternate=False, fasteners=())
        target = SimpleNamespace(group=group, alternate=False, parameters_mm={"haunch_flat": 0},
                                 template=SimpleNamespace(key="beam_column_haunch"))
        touched = []
        with patch.object(self.editor, "_marker", return_value=self.marker), \
                patch.object(self.editor, "evaluate", return_value=before), \
                patch.object(self.editor, "_solid_matches", return_value=True), \
                patch.object(self.editor, "_modify_part",
                             side_effect=lambda design, part, *args: touched.append(part)), \
                patch.multiple(self.editor.assemblies, _plates_match=lambda *args: True,
                               _associated_bolts_match=lambda *args: True,
                               _check_bolted_assembly=lambda *args: None,
                               fastener_creator=SimpleNamespace(assembly_hardware=lambda group: (bolts,)),
                               create=True):
            self.assertTrue(self.editor._edit_jarret_contours(self.design, target, after))
        self.assertEqual(touched, [web_part])
        self.assertEqual(json.loads(self.marker.value)["parameters_mm"], {"haunch_flat": 10})

    def test_catalogue_assembly_edit_requires_an_owned_history_group(self):
        self.marker.value = json.dumps({"kind": "beam_column_haunch", "members": ["main", "side"],
                                        "parameters_mm": {"width": 135}, "end_plate_link": {"alternate": True}})
        remove = ModuleType("_jhr_edit_smoke.commands.remove_assembly")
        remove.target_group = lambda design, group: (group, object())
        with patch.dict(sys.modules, {remove.__name__: remove}):
            target = self.editor.read(self.design, self.group)
        self.assertEqual("beam_column_haunch", target.template.key)
        self.assertEqual(135, target.parameters_mm["width"])
        self.assertTrue(target.alternate)
        self.assertTrue(target.writable)
        with patch.object(remove, "target_group", side_effect=ValueError("Historique introuvable")):
            with patch.dict(sys.modules, {remove.__name__: remove}):
                target = self.editor.read(self.design, self.group)
        self.assertFalse(target.writable)
        with self.assertRaisesRegex(ValueError, "Historique introuvable"):
            self.editor.evaluate(self.design, target, target.parameters_mm)

    def test_adjustment_retains_existing_pieces_and_permits_trailing_parts(self):
        plate = SimpleNamespace(name="Platine de pied")
        rod = SimpleNamespace(name="Tige d’ancrage droite Ø16")
        new_rod = SimpleNamespace(name="Tige d’ancrage droite Ø18")
        washer = SimpleNamespace(name="Rondelle d’ancrage M18")
        self.editor._check_piece_layout([plate, rod], [plate, new_rod, washer])
        with self.assertRaisesRegex(ValueError, "retirerait"):
            self.editor._check_piece_layout([plate, rod], [plate])

    def test_proxy_transform_applies_pure_rotation_and_can_be_restored(self):
        class Frame:
            def __init__(self, axes):
                self.axes = axes

            def copy(self):
                return Frame(self.axes)

            def getAsCoordinateSystem(self):
                vectors = ((900, 0, 0), *self.axes)
                return tuple(SimpleNamespace(asArray=lambda vector=v: vector) for v in vectors)

        original = Frame(((1, 0, 0), (0, 1, 0), (0, 0, 1)))
        rotated = Frame(((.6, .8, 0), (-.8, .6, 0), (0, 0, 1)))
        proxy = SimpleNamespace(transform2=original, component=SimpleNamespace(name="Platine de pied"))
        design = SimpleNamespace(snapshots=SimpleNamespace(hasPendingSnapshot=False),
                                 timeline=SimpleNamespace(moveToEnd=lambda: None))
        journal = self.editor.Journal(design, SimpleNamespace(value="pied"), "pied")
        with patch.object(self.editor.assemblies, "TOL", 1e-4, create=True):
            self.editor._move_parts(design, [(proxy, rotated)], journal)
        self.assertEqual(proxy.transform2.axes, rotated.axes)
        journal.rollback()
        self.assertEqual(proxy.transform2.axes, original.axes)

    def test_rollback_restores_in_reverse_and_keeps_definition(self):
        events = []
        design = SimpleNamespace(timeline=SimpleNamespace(moveToEnd=lambda: events.append("timeline")))
        marker = SimpleNamespace(value="modifié")
        journal = self.editor.Journal(design, marker, "ancien")
        journal.undo.extend((lambda: events.append("premier"), lambda: events.append("second")))
        journal.rollback()
        self.assertEqual(events, ["second", "premier", "timeline"])
        self.assertEqual("ancien", marker.value)

    def test_joint_rotation_tries_opposite_sign_and_restores_original_expression(self):
        def frame(u, v):
            vectors = ((900, 0, 0), u, v, (0, 0, 1))
            return SimpleNamespace(getAsCoordinateSystem=lambda: tuple(
                SimpleNamespace(asArray=lambda value=vector: value) for vector in vectors
            ))

        class Parameter:
            def __init__(self):
                self.value = 0

            @property
            def expression(self):
                return "0 deg"

            @expression.setter
            def expression(self, _):
                self.value = 0

        original = frame((1, 0, 0), (0, 1, 0))
        desired = frame((0, 1, 0), (-1, 0, 0))
        group = object()
        angle = Parameter()
        joint = SimpleNamespace(name="Liaison au squelette – Pied", occurrenceOne=group,
                                geometryTwoTransform=original, angle=angle)
        root = SimpleNamespace(joints=[joint])
        design = SimpleNamespace(rootComponent=root, snapshots=SimpleNamespace(hasPendingSnapshot=False),
                                 timeline=SimpleNamespace(moveToEnd=lambda: None))
        placement = (SimpleNamespace(transform2=original), desired)
        journal = self.editor.Journal(design, SimpleNamespace(value="pied"), "pied")
        matrix3d = SimpleNamespace(create=lambda: SimpleNamespace(setToRotation=lambda *args: True))
        with patch.object(self.editor.assemblies, "TOL", 1e-4, create=True), \
             patch.object(self.editor.core, "Matrix3D", matrix3d, create=True), \
             patch.object(self.editor, "_rotation_matches", return_value=True), \
             patch.object(self.editor, "_matches_matrix", side_effect=lambda *args: angle.value < -1.5):
            self.assertTrue(self.editor._rotate_linked_group(design, group, [placement], journal))
        self.assertLess(angle.value, -1.5)
        journal.rollback()
        self.assertEqual(angle.value, 0)


if __name__ == "__main__":
    unittest.main()
