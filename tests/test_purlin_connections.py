from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "addin" / "JHR_StructuralMembers_V1"))

from lib import purlin_connections as connections
from lib.purlin_connections import Axis, _angle_cleat_pairs, match_ends


def axis(name, start, end):
    return Axis(SimpleNamespace(name=name), start, end)


class PurlinConnectionsTests(unittest.TestCase):
    def setUp(self):
        self.left = axis("Poutre gauche", (0, 0, 0), (0, 50, 0))
        self.right = axis("Poutre droite", (40, 0, 0), (40, 50, 0))

    def test_batch_pairs_both_ends_of_each_purlin(self):
        first = axis("Panne 1", (0, 10, 0), (40, 10, 0))
        second = axis("Panne 2", (40, 30, 0), (0, 30, 0))
        pairs, unmatched = match_ends((self.left, self.right), (first, second))
        self.assertEqual(pairs, (
            (self.left.occurrence, first.occurrence),
            (self.right.occurrence, first.occurrence),
            (self.right.occurrence, second.occurrence),
            (self.left.occurrence, second.occurrence),
        ))
        self.assertEqual(unmatched, ())

    def test_near_axis_can_match_only_selected_supports(self):
        purlin = axis("Panne", (.05, 10, 0), (40, 10, 0))
        self.assertEqual(
            match_ends((self.left,), (purlin,)),
            (((self.left.occurrence, purlin.occurrence),), ()),
        )

    def test_midspan_crossing_and_higher_purlin_are_not_end_connections(self):
        crossing = axis("Panne continue", (-10, 10, 0), (10, 10, 0))
        above = axis("Panne au-dessus", (0, 30, 1), (40, 30, 1))
        beyond = axis("Panne hors poutre", (0, 51, 0), (40, 51, 0))
        self.assertEqual(
            match_ends((self.left, self.right), (crossing, above, beyond)),
            ((), (crossing.occurrence, above.occurrence, beyond.occurrence)),
        )

    def test_parallel_member_does_not_make_support_ambiguous(self):
        purlin = axis("Panne", (0, 0, 0), (30, 0, 0))
        parallel = axis("Poutre parallèle", (-40, 0, 0), (0, 0, 0))
        self.assertEqual(
            match_ends((self.left, parallel), (purlin,)),
            (((self.left.occurrence, purlin.occurrence),), ()),
        )

    def test_ambiguity_at_joint_of_two_supports_prevents_batch(self):
        top = axis("Poutre gauche bis", (0, 50, 0), (0, 100, 0))
        purlin = axis("Panne", (0, 50, 0), (40, 50, 0))
        with self.assertRaisesRegex(ValueError, "plusieurs poutres possibles"):
            match_ends((self.left, self.right, top), (purlin,))

    def test_existing_angle_parts_are_deduplicated_by_component_pair(self):
        second = SimpleNamespace(value="PANNE_IPE160_001")
        owner = SimpleNamespace(attributes=SimpleNamespace(itemByName=lambda group, key: second))
        first = SimpleNamespace(value="POUTRE_IPE240_001", parent=owner)
        design = SimpleNamespace(findAttributes=lambda group, key: (first, first))
        self.assertEqual(_angle_cleat_pairs(design, "EI_JHR_AngleCleat"), {
            frozenset(("POUTRE_IPE240_001", "PANNE_IPE160_001")),
        })

    def test_second_cope_refreshes_references_after_first_connection(self):
        beam_a, beam_b = self.left.occurrence, self.right.occurrence
        purlin = SimpleNamespace(name="Panne 1", entityToken="panne")
        calls = []
        records = []
        purlin.component = SimpleNamespace(attributes=SimpleNamespace(itemsByGroup=lambda _: records))
        markers = {}

        def plan(beam):
            members = tuple(SimpleNamespace(occurrence=occurrence) for occurrence in (beam, purlin))
            return SimpleNamespace(members=members, settings_mm={}, alternate=False)

        def evaluate(design, kind, pair, settings, alternate):
            calls.append(("recalcul", pair[0]))
            return plan(pair[0])

        def create(design, current):
            beam = current.members[0].occurrence
            calls.append(("plat", beam))
            marker = SimpleNamespace(value="{}")
            markers[beam.name] = marker
            beam.component = SimpleNamespace(name=beam.name,
                                             attributes=SimpleNamespace(itemByName=lambda *args: marker))
            return beam

        def prepare(design, beam, purlin, clearances):
            calls.append(("nouvelle référence", beam))
            return beam

        def gruge(beam):
            calls.append(("grugeage", beam))
            records.append(SimpleNamespace(name=f"grugeage {len(records) + 1}"))

        operations = SimpleNamespace(evaluate=evaluate, create=create, ATTRIBUTE_GROUP="JHR")
        cope = SimpleNamespace(create_profile_cope=gruge)
        batch = connections.Batch((plan(beam_a), plan(beam_b)), 0, (), (beam_a, beam_b), (.1, .1, .1))
        package = sys.modules[connections.__package__]
        with patch.object(package, "assembly_operations", operations, create=True), \
             patch.object(package, "cope_creator", cope, create=True), \
             patch.object(connections, "_prepare_cope", prepare):
            self.assertEqual(connections.create_batch(SimpleNamespace(timeline=None), batch), (beam_a, beam_b))
        self.assertEqual(batch.cope_count, 2)
        self.assertIn('"name": "grugeage 1"', markers[beam_a.name].value)
        self.assertIn('"name": "grugeage 2"', markers[beam_b.name].value)
        self.assertEqual(calls, [
            ("grugeage", beam_a), ("recalcul", beam_a), ("plat", beam_a),
            ("nouvelle référence", beam_b), ("grugeage", beam_b), ("recalcul", beam_b), ("plat", beam_b),
        ])


if __name__ == "__main__":
    unittest.main()
