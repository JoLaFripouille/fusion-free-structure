from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch


ADDIN = Path(__file__).resolve().parents[1] / "addin" / "JHR_StructuralMembers_V1"
sys.path.insert(0, str(ADDIN))

from lib import fastener_geometry as geometry


def load_adapter():
    adsk = ModuleType("adsk")
    adsk.core = ModuleType("adsk.core")
    adsk.core.Circle3D = SimpleNamespace(cast=lambda entity: entity)
    adsk.core.Cone = SimpleNamespace(cast=lambda entity: entity if getattr(entity, "kind", None) == "cone" else None)
    adsk.core.Cylinder = SimpleNamespace(cast=lambda entity: entity if getattr(entity, "kind", None) == "cylinder" else None)
    adsk.fusion = ModuleType("adsk.fusion")
    adsk.fusion.DesignTypes = SimpleNamespace(ParametricDesignType="parametric")
    creator = SimpleNamespace(
        read_hole=lambda _: geometry.Hole((0., 0., .3), (0., 0., 1.), 1.02),
        read_support=lambda _: geometry.SupportPlane((0., 0., 0.), (0., 0., -1.)),
        point=tuple,
        existing_positions=lambda _: (),
    )
    spec = importlib.util.spec_from_file_location("lib._test_tapped_fastener", ADDIN / "lib" / "tapped_fastener.py")
    adapter = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"adsk": adsk, "adsk.core": adsk.core, "adsk.fusion": adsk.fusion}):
        with patch("lib.fastener_creator", creator, create=True):
            spec.loader.exec_module(adapter)
    return adapter


class TappedFastenerCompositionTests(unittest.TestCase):
    def setUp(self):
        self.adapter = load_adapter()
        self.hole = SimpleNamespace(geometry=SimpleNamespace(kind="cylinder"), edges=[
            SimpleNamespace(geometry=SimpleNamespace(center=(0., 0., z))) for z in (.3, 2.3)
        ])
        self.internal = SimpleNamespace(threadPitch=.175, minorDiameter=1.02, threadDesignation="M12x1.75")
        self.countersink = geometry.CountersunkHole((0., 0., 0.), (0., 0., 1.), 1.02, 2.688, .834)

    def bore(self, low, high):
        return SimpleNamespace(geometry=self.hole.geometry, edges=[
            SimpleNamespace(geometry=SimpleNamespace(center=(0., 0., z))) for z in (low, high)
        ])

    def test_names_keep_tapped_head_kind_and_legacy_h(self):
        self.assertEqual(geometry.configuration_name(12, 20, "H-Taraudage", 2.),
                         "VIS H M12x20 - TARAUDAGE + 1 RONDELLE")
        self.assertEqual(geometry.configuration_name(12, 20, "TF-Taraudage", 2.),
                         "VIS TF M12x20 - TARAUDAGE")

    def test_automatic_length_uses_optional_head_washer(self):
        seated, length, engagement = self.adapter.seat(self.hole, None, 12, 12, self.internal)
        bare, bare_length, _ = self.adapter.seat(self.hole, None, 12, 12, self.internal, head_washer=False)
        self.assertAlmostEqual(length, 17.5)
        self.assertAlmostEqual(bare_length, 15.)
        self.assertAlmostEqual(engagement, 12.)
        self.assertEqual(seated, bare)

    def test_manual_length_follows_actual_grip_and_respects_bore(self):
        _, length, engagement = self.adapter.seat(self.hole, None, 12, None, self.internal, length_mm=20.)
        self.assertEqual(length, 20.)
        self.assertAlmostEqual(engagement, 14.5)
        with self.assertRaisesRegex(ValueError, "entre 7.25 et 25.5 mm"):
            self.adapter.seat(self.hole, None, 12, None, self.internal, length_mm=26.)
        with self.assertRaisesRegex(ValueError, "entre 4.75 et 23 mm"):
            self.adapter.seat(self.hole, None, 12, None, self.internal, head_washer=False, length_mm=4.)

    def test_actual_engagement_is_forwarded_to_the_external_thread(self):
        design = SimpleNamespace(rootComponent=object(), designType="direct")
        external = object()
        with (
            patch.object(self.adapter, "thread_infos", return_value=(self.internal, external)),
            patch.object(self.adapter, "add_thread", return_value=SimpleNamespace(name="Taraudage")),
            patch.object(self.adapter.simple_fastener_creator, "create_modeled_fasteners",
                         return_value={"created": 1}) as create,
        ):
            result = self.adapter.place(design, self.hole, None, 12, None, head_washer=False, length_mm=20.)

        self.assertFalse(create.call_args.kwargs["head_washer"])
        self.assertAlmostEqual(create.call_args.kwargs["thread_depth_cm"], 1.7)
        self.assertAlmostEqual(result["engagement_mm"], 17.)

    def test_automatic_countersink_costs_cylindrical_engagement_in_preview(self):
        bore = self.bore(0., 2.)
        preparation = SimpleNamespace(hole=self.countersink)
        with (
            patch.object(self.adapter, "thread_infos", return_value=(self.internal, object())),
            patch.object(self.adapter.countersink_preparation, "plan", return_value=preparation),
            patch.object(self.adapter.countersink_preparation, "apply") as machining,
        ):
            result = self.adapter.place(None, bore, None, 12, 10, preview=True, head="TF",
                                        prepare_countersink=True)
            with self.assertRaisesRegex(ValueError, "longueur totale"):
                self.adapter.place(None, bore, None, 12, None, preview=True, head="TF",
                                   prepare_countersink=True, length_mm=20.1)

        self.assertTrue(result["prepares_countersink"])
        self.assertAlmostEqual(result["length_mm"], 18.34)
        self.assertAlmostEqual(result["engagement_mm"], 10.)
        machining.assert_not_called()

    def test_existing_countersink_reuses_remaining_bore_without_cutting(self):
        bore = self.bore(.834, 2.)
        cone = SimpleNamespace(geometry=SimpleNamespace(kind="cone"), edges=[
            SimpleNamespace(geometry=SimpleNamespace(center=(0., 0., .834)), faces=(bore,))
        ])
        with (
            patch.object(self.adapter, "thread_infos", return_value=(self.internal, object())),
            patch.object(self.adapter.fastener_creator, "read_countersink", return_value=self.countersink,
                         create=True),
            patch.object(self.adapter.countersink_preparation, "plan") as machining,
        ):
            result = self.adapter.place(None, cone, None, 12, None, preview=True, head="TF",
                                        prepare_countersink=True, length_mm=18.5)

        self.assertFalse(result["prepares_countersink"])
        self.assertAlmostEqual(result["engagement_mm"], 10.16)
        machining.assert_not_called()

    def test_countersunk_placement_threads_the_remaining_bore_and_links_to_new_cone(self):
        design = SimpleNamespace(rootComponent=object(), designType="direct")
        bore = self.bore(0., 2.)
        remaining_bore = self.bore(.834, 2.)
        cone, connection, external = object(), object(), object()
        preparation = SimpleNamespace(hole=self.countersink)
        with (
            patch.object(self.adapter, "thread_infos", return_value=(self.internal, external)),
            patch.object(self.adapter.countersink_preparation, "plan", return_value=preparation),
            patch.object(self.adapter.countersink_preparation, "apply", return_value=(cone, ())),
            patch.object(self.adapter.countersink_preparation, "bore_face", return_value=remaining_bore),
            patch.object(self.adapter, "_opening_binding", return_value=connection) as binding,
            patch.object(self.adapter, "add_thread", return_value=SimpleNamespace(name="Taraudage")) as tap,
            patch.object(self.adapter.simple_fastener_creator, "create_modeled_fasteners",
                         return_value={"created": 1}) as create,
        ):
            self.adapter.place(design, bore, None, 12, 10, head="TF", prepare_countersink=True,
                               link_to_hole=True)

        tap.assert_called_once_with(remaining_bore, self.internal, modeled=False)
        self.assertIs(binding.call_args.args[1], cone)
        self.assertIs(create.call_args.kwargs["bind_to_hole"], connection)
        self.assertEqual(create.call_args.kwargs["head"], "TF")
        self.assertFalse(create.call_args.kwargs["head_washer"])
        self.assertAlmostEqual(create.call_args.kwargs["thread_depth_cm"], 1.)
        self.assertEqual(create.call_args.args[1][0].countersink, self.countersink)

    def test_failed_fastener_rolls_back_thread_then_fraisure(self):
        design = SimpleNamespace(rootComponent=object(), designType="direct")
        bore = self.bore(0., 2.)
        preparation = SimpleNamespace(hole=self.countersink)
        removed = []
        tap = SimpleNamespace(isValid=True, deleteMe=Mock(side_effect=lambda: removed.append("thread")))
        sink = SimpleNamespace(isValid=True, deleteMe=Mock(side_effect=lambda: removed.append("countersink")))
        with (
            patch.object(self.adapter, "thread_infos", return_value=(self.internal, object())),
            patch.object(self.adapter.countersink_preparation, "plan", return_value=preparation),
            patch.object(self.adapter.countersink_preparation, "apply", return_value=(object(), (sink,))),
            patch.object(self.adapter.countersink_preparation, "bore_face", return_value=self.bore(.834, 2.)),
            patch.object(self.adapter, "add_thread", return_value=tap),
            patch.object(self.adapter.simple_fastener_creator, "create_modeled_fasteners",
                         side_effect=RuntimeError("solid error")),
        ):
            with self.assertRaisesRegex(RuntimeError, "solid error"):
                self.adapter.place(design, bore, None, 12, 10, head="TF", prepare_countersink=True)

        self.assertEqual(removed, ["thread", "countersink"])


if __name__ == "__main__":
    unittest.main()
