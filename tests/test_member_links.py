import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADDIN = ROOT / "addin" / "JHR_StructuralMembers_V1"
sys.path.insert(0, str(ADDIN))

from lib import member_links, member_metadata


class FakeAttribute:
    def __init__(self, value):
        self.value = value


class FakeAttributes:
    def __init__(self, values):
        self._values = values

    def itemByName(self, group, name):
        if group != member_metadata.ATTRIBUTE_GROUP or name not in self._values:
            return None
        return FakeAttribute(self._values[name])


class FakeComponent:
    def __init__(self, name, values):
        self.name = name
        self.attributes = FakeAttributes(values)


class FakeOccurrence:
    def __init__(self, name, values):
        self.component = FakeComponent(name, values)


class FakeCurve:
    def __init__(self, token):
        self.entityToken = token
        self.nativeObject = None


class FakeRoot:
    def __init__(self, occurrences):
        self.allOccurrences = occurrences


class FakeDesign:
    def __init__(self, entities_by_saved_token):
        self._entities_by_saved_token = entities_by_saved_token

    def findEntityByToken(self, token):
        return self._entities_by_saved_token.get(token, ())


class MemberLinkTests(unittest.TestCase):
    def test_current_and_legacy_members_are_found_on_their_source_curves(self):
        first_curve = FakeCurve("current-token-a")
        second_curve = FakeCurve("current-token-b")
        first = FakeOccurrence("BARRE_IPE200_001", {
            "source_curve_token": "saved-token-a",
        })
        second = FakeOccurrence("BARRE_HEA160_001", {
            "source_line_token": "saved-token-b",
        })
        unrelated = FakeOccurrence("Composant ordinaire", {})
        design = FakeDesign({
            "saved-token-a": (first_curve,),
            "saved-token-b": (second_curve,),
        })
        usages = member_links.curve_usages(
            design,
            FakeRoot((first, second, unrelated)),
            (first_curve, second_curve),
        )
        self.assertEqual(usages[0].occurrences, (first,))
        self.assertEqual(usages[1].occurrences, (second,))
        self.assertEqual(
            member_links.unique_used_occurrences(usages),
            (first, second),
        )

    def test_unresolved_saved_token_does_not_block_a_free_curve(self):
        curve = FakeCurve("current-token")
        stale = FakeOccurrence("BARRE_ANCIENNE", {
            "source_curve_token": "stale-token",
        })
        usages = member_links.curve_usages(
            FakeDesign({}),
            FakeRoot((stale,)),
            (curve,),
        )
        self.assertEqual(usages[0].occurrences, ())
        self.assertEqual(member_links.unique_used_occurrences(usages), ())


if __name__ == "__main__":
    unittest.main()
