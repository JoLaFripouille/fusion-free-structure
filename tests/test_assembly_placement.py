from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "addin" / "JHR_StructuralMembers_V1"))

from lib.assembly_placement import parent_for


class Occurrence:
    def __init__(self, parent=None, *, external=False):
        self.assemblyContext = parent
        self.component = object()
        self.isReferencedComponent = external


class AssemblyPlacementTests(unittest.TestCase):
    def setUp(self):
        root = SimpleNamespace(allOccurrencesByComponent=lambda component: SimpleNamespace(count=1))
        self.design = SimpleNamespace(rootComponent=root, activeOccurrence=None)

    def test_supports_in_different_subgroups_use_their_common_container(self):
        common = Occurrence()
        beam = Occurrence(Occurrence(common))
        post = Occurrence(Occurrence(common))
        self.assertIs(parent_for(self.design, (post, beam)), common)
        self.assertIsNone(parent_for(self.design, (post, Occurrence())))

    def test_explicit_active_container_takes_precedence_and_skips_an_active_support(self):
        first, active = Occurrence(), Occurrence()
        post, beam = Occurrence(first), Occurrence(first)
        self.design.activeOccurrence = active
        self.assertIs(parent_for(self.design, (post, beam)), active)
        self.design.activeOccurrence = beam
        self.assertIs(parent_for(self.design, (post, beam)), first)

    def test_external_ancestor_cannot_receive_a_local_group(self):
        parent = Occurrence(Occurrence(external=True))
        with self.assertRaisesRegex(ValueError, "doit être local"):
            parent_for(self.design, (Occurrence(parent), Occurrence(parent)))


if __name__ == "__main__":
    unittest.main()
