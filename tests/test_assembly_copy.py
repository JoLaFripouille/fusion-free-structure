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


def load_copy(edit, operations):
    class Occurrence:
        @staticmethod
        def cast(entity):
            return entity if isinstance(entity, Item) else None

    adsk = ModuleType("adsk")
    fusion = ModuleType("adsk.fusion")
    fusion.Occurrence = Occurrence
    adsk.fusion = fusion
    spec = importlib.util.spec_from_file_location("lib._copy_test", ROOT / "lib/assembly_copy.py")
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"adsk": adsk, "adsk.fusion": fusion, spec.name: module}):
        with patch.object(lib, "assembly_operations", operations, create=True):
            with patch.object(lib, "assembly_edit", edit, create=True):
                spec.loader.exec_module(module)
    return module


class Attributes:
    def __init__(self, parent):
        self.parent, self.by_key = parent, {}

    def add(self, group, key, value):
        index = (group, key)

        def delete():
            del self.by_key[index]
            return True

        marker = SimpleNamespace(parent=self.parent, value=value, deleteMe=delete)
        self.by_key[index] = marker
        return marker

    def itemByName(self, group, key):
        return self.by_key.get((group, key))


class Item:
    def __init__(self, name):
        self.name = self.entityToken = name
        self.isValid = True
        self.component = SimpleNamespace(name=name)
        self.component.attributes = Attributes(self.component)


class CopyTests(unittest.TestCase):
    def setUp(self):
        self.type = SimpleNamespace(family="Pieds de poteau", key="base_ih", roles=("Poteau",))
        self.original = Item("Pied source")
        self.post1, self.post2, self.post3 = (Item(name) for name in ("P1", "P2", "P3"))
        self.groups = {self.original: self.record(self.original, self.post1, 325)}
        self.items = [self.original, self.post1, self.post2, self.post3]
        self.operations = SimpleNamespace(
            AssemblyPlan=SimpleNamespace, ATTRIBUTE_GROUP="JHR", TOL=1e-4,
            _base_end_index=lambda member, outward: 0, evaluate=self.evaluate, create=self.make_group,
        )
        self.editor = SimpleNamespace(EditTarget=SimpleNamespace, read=self.read, evaluate=self.propose,
                                      _apply=self.apply, prepare_refresh=self.refresh,
                                      _check_piece_layout=lambda old, new: None)
        self.module = load_copy(self.editor, self.operations)
        self.log = []
        self.design = SimpleNamespace(
            rootComponent=SimpleNamespace(occurrences=self.items),
            findEntityByToken=lambda token: [item for item in self.items if item.entityToken == token],
            findAttributes=lambda group, key: [attribute for item in self.items
                                              if (attribute := item.component.attributes.itemByName(group, key))],
        )

    def record(self, group, post, width):
        return SimpleNamespace(group=group, template=self.type, occurrences=(post,),
                               parameters_mm={"width": width}, alternate=False, writable=True)

    def read(self, design, entity):
        return self.groups[getattr(entity, "assemblyContext", entity)]

    @staticmethod
    def evaluate(design, kind, occurrences, settings, alternate):
        return SimpleNamespace(members=[SimpleNamespace(occurrence=occurrence) for occurrence in occurrences],
                               plates=[SimpleNamespace(normal=(0, 0, 1), origin=(0, 0, 0))],
                               base_flush=True, settings_mm=settings, alternate=alternate)

    def make_group(self, design, assembly):
        group = Item(f"Copie {len(self.groups)}")
        self.items.append(group)
        targets = tuple(member.occurrence for member in assembly.members)
        self.groups[group] = SimpleNamespace(group=group, template=self.type, occurrences=targets,
                                             parameters_mm=assembly.settings_mm, alternate=assembly.alternate,
                                             writable=True)
        return group

    def refresh(self, design, group):
        target = self.groups[group]
        return SimpleNamespace(target=target, plan=self.propose(design, target, target.parameters_mm))

    def propose(self, design, target, settings):
        return self.evaluate(design, "base_ih", target.occurrences, settings, target.alternate)

    def apply(self, design, revision, plan):
        group = revision.target.group
        original = revision.target.parameters_mm
        revision.target.parameters_mm = plan.settings_mm
        self.log.append(group.name)

        def restore():
            revision.target.parameters_mm = original
            self.log.append(f"annule {group.name}")

        undo = [restore]

        def rollback():
            for action in reversed(undo):
                action()

        return SimpleNamespace(undo=undo, rollback=rollback)

    def add_link(self, group, master_token):
        return group.component.attributes.add("JHR", self.module.SOURCE_ATTRIBUTE, master_token)

    def update(self, group, width):
        revision = self.refresh(self.design, group)
        plan = self.propose(self.design, revision.target, {"width": width})
        return self.module.apply_master_settings(self.design, revision, plan)

    def test_independent_copy_from_plate_on_other_post(self):
        plate = SimpleNamespace(assemblyContext=self.original)
        plan = self.module.prepare(self.design, plate, self.post2)
        copy = self.module.create(self.design, plan)
        self.assertEqual(self.groups[copy].parameters_mm, {"width": 325})
        self.assertIs(self.groups[copy].occurrences[0], self.post2)
        self.assertIsNone(copy.component.attributes.itemByName("JHR", self.module.SOURCE_ATTRIBUTE))

    def test_copy_of_linked_copy_uses_master(self):
        first = self.module.create(self.design, self.module.prepare(self.design, self.original, self.post2, True))
        self.groups[first].parameters_mm = {"width": 420}
        second = self.module.create(self.design, self.module.prepare(self.design, first, self.post3, True))
        self.assertEqual(second.component.attributes.itemByName("JHR", self.module.SOURCE_ATTRIBUTE).value,
                         self.original.entityToken)
        self.assertEqual(self.groups[second].parameters_mm, {"width": 325})

    def test_source_post_and_duplicate_at_target_end_refused(self):
        with self.assertRaisesRegex(ValueError, "autre poteau"):
            self.module.prepare(self.design, self.original, self.post1)
        self.original.component.attributes.add("JHR", "definition", json.dumps({
            "kind": "base_ih", "members": [self.post2.entityToken], "base_end_index": 0,
        }))
        with self.assertRaisesRegex(ValueError, "possède déjà"):
            self.module.prepare(self.design, self.original, self.post2)

    def test_catalogue_copy_uses_target_roles_and_source_settings(self):
        self.type = SimpleNamespace(family="Poutre-poutre", key="shear_plate",
                                    roles=("Poutre principale", "Poutre secondaire"))
        source = self.groups[self.original]
        source.template = self.type
        source.occurrences = (self.post1, self.post2)
        source.parameters_mm = {"thickness": 8, "rows": 3}
        source.alternate = True
        with patch.object(self.operations, "evaluate", wraps=self.evaluate) as evaluate:
            plan = self.module.prepare(self.design, self.original, (self.post1, self.post3))
            copy = self.module.create(self.design, plan)
        evaluate.assert_called_with(self.design, "shear_plate", (self.post1, self.post3),
                                    {"thickness": 8, "rows": 3}, True)
        self.assertEqual(self.groups[copy].occurrences, (self.post1, self.post3))
        self.assertTrue(self.groups[copy].alternate)
        self.assertIsNone(copy.component.attributes.itemByName("JHR", self.module.SOURCE_ATTRIBUTE))

    def test_multi_profile_copy_refuses_missing_duplicates_and_linking(self):
        source = self.groups[self.original]
        source.template = SimpleNamespace(family="Contreventements", key="gusset_end_2",
                                          roles=("Profil porteur", "Diagonale 1", "Diagonale 2"))
        source.occurrences = (self.post1, self.post2, self.post3)
        with self.assertRaisesRegex(ValueError, "dans l’ordre"):
            self.module.prepare(self.design, self.original, (self.post1, self.post2))
        with self.assertRaisesRegex(ValueError, "différent pour chaque rôle"):
            self.module.prepare(self.design, self.original, (self.post1, self.post2, self.post2))
        with self.assertRaisesRegex(ValueError, "différent de l’assemblage source"):
            self.module.prepare(self.design, self.original, source.occurrences)
        with self.assertRaisesRegex(ValueError, "uniquement pour les pieds"):
            self.module.prepare(self.design, self.original, source.occurrences, linked=True)

    def test_editing_a_copy_updates_master_and_other_copies(self):
        first = self.module.create(self.design, self.module.prepare(self.design, self.original, self.post2, True))
        second = self.module.create(self.design, self.module.prepare(self.design, self.original, self.post3, True))
        self.update(first, 400)
        self.assertEqual([self.groups[item].parameters_mm["width"] for item in (self.original, first, second)],
                         [400, 400, 400])
        self.assertEqual(self.log, ["Pied source", first.name, second.name])

    def test_later_failure_rolls_back_already_edited_pieds(self):
        first = self.module.create(self.design, self.module.prepare(self.design, self.original, self.post2, True))
        second = self.module.create(self.design, self.module.prepare(self.design, self.original, self.post3, True))

        def fail_last(design, revision, plan):
            if revision.target.group == second:
                raise RuntimeError("Refus Fusion")
            return self.apply(design, revision, plan)

        with patch.object(self.editor, "_apply", side_effect=fail_last):
            with self.assertRaisesRegex(RuntimeError, "Refus Fusion"):
                self.update(self.original, 400)
        self.assertEqual(self.log, ["Pied source", first.name, f"annule {first.name}", "annule Pied source"])
        self.assertEqual([self.groups[item].parameters_mm["width"] for item in (self.original, first, second)],
                         [325, 325, 325])

    def test_deleted_master_does_not_block_editing_and_rollback_can_restore_link(self):
        copy = self.module.create(self.design, self.module.prepare(self.design, self.original, self.post2, True))
        self.items.remove(self.original)
        journal = self.update(copy, 400)
        attributes = copy.component.attributes
        self.assertEqual(self.groups[copy].parameters_mm["width"], 400)
        self.assertIsNone(attributes.itemByName("JHR", self.module.SOURCE_ATTRIBUTE))
        journal.rollback()
        self.assertEqual(attributes.itemByName("JHR", self.module.SOURCE_ATTRIBUTE).value, self.original.entityToken)

    def test_link_cycle_is_refused(self):
        copy = self.module.create(self.design, self.module.prepare(self.design, self.original, self.post2, True))
        self.add_link(self.original, copy.entityToken)
        with self.assertRaisesRegex(ValueError, "boucle"):
            self.module.prepare(self.design, copy, self.post3, True)


if __name__ == "__main__":
    unittest.main()
