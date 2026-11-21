import pathlib
import sys
from types import SimpleNamespace
import unittest


sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "addin" / "JHR_StructuralMembers_V1"))
from lib import timeline_groups


class Timeline:
    def __init__(self, *items):
        self.items = list(items)
        self.markerPosition = self.count
        self.ranges = []
        self.timelineGroups = SimpleNamespace(add=self.add)

    @property
    def count(self):
        return len(self.items)

    def item(self, index):
        return self.items[index]

    def append(self, *items):
        self.items.extend(items)
        self.markerPosition = self.count

    def add(self, start, end):
        self.ranges.append((start, end))
        return SimpleNamespace(name="", isCollapsed=False)


def item(*, is_group=False, parent=None):
    return SimpleNamespace(isGroup=is_group, parentGroup=parent)


class TimelineCreationGroupTests(unittest.TestCase):
    def test_groups_only_appended_operations_and_collapses_new_group(self):
        old = item(is_group=True)
        timeline = Timeline(old, item())
        start = timeline_groups.creation_start(timeline)
        timeline.append(item(), item(), item())
        group = timeline_groups.group_creation(timeline, start, "Pied de poteau")
        self.assertEqual(timeline.ranges, [(2, 4)])
        self.assertEqual(group.name, "Pied de poteau")
        self.assertTrue(group.isCollapsed)
        self.assertIs(timeline.item(0), old)

    def test_keeps_existing_group_boundaries_and_single_items(self):
        timeline = Timeline(item())
        start = timeline_groups.creation_start(timeline)
        timeline.append(item())
        self.assertIsNone(timeline_groups.group_creation(timeline, start, "Un perçage"))
        old = item(is_group=True)
        timeline.append(old, item())
        self.assertIsNone(timeline_groups.group_creation(timeline, start, "Groupe imbriqué"))
        self.assertEqual(timeline.ranges, [])

    def test_leaves_rolled_history_alone_before_or_after_changes(self):
        timeline = Timeline(item(), item())
        timeline.markerPosition = 1
        self.assertIsNone(timeline_groups.creation_start(timeline))
        timeline.markerPosition = 2
        start = timeline_groups.creation_start(timeline)
        timeline.append(item(), item())
        timeline.markerPosition = 3
        self.assertIsNone(timeline_groups.group_creation(timeline, start, "En cours"))
        self.assertEqual(timeline.ranges, [])

    def test_deferred_grouping_restores_outer_state_after_failure(self):
        timeline = Timeline(item())
        start = timeline_groups.creation_start(timeline)
        timeline.append(item(), item())
        with self.assertRaisesRegex(ValueError, "test"):
            with timeline_groups.defer_grouping():
                self.assertIsNone(timeline_groups.creation_start(timeline))
                self.assertIsNone(timeline_groups.group_creation(timeline, start, "Sous-opération"))
                self.assertIsNone(timeline_groups.group_member(None, []))
                self.assertIsNone(timeline_groups.group_operations(None, [], "Sous-opération"))
                raise ValueError("test")
        self.assertIsNotNone(timeline_groups.group_creation(timeline, start, "Montage complet"))


if __name__ == "__main__":
    unittest.main()
