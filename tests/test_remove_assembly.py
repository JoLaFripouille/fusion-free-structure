import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch


class Entity(SimpleNamespace):
    __eq__ = object.__eq__


class Occurrence(Entity):
    @staticmethod
    def cast(entity):
        return entity if isinstance(entity, Occurrence) else None


def load_command():
    root = Path(__file__).resolve().parents[1] / "addin" / "JHR_StructuralMembers_V1"
    package = "_jhr_remove_smoke"
    command_name = package + ".commands.remove_assembly"
    spec = importlib.util.spec_from_file_location(command_name, root / "commands" / "remove_assembly.py")
    ancestry = {name: ModuleType(name) for name in (
        package, package + ".commands", package + ".commands.inspect_assembly", package + ".lib",
        "adsk", "adsk.core", "adsk.fusion",
    )}
    for name in (package, package + ".commands", package + ".lib", "adsk"):
        ancestry[name].__path__ = []
    library = ancestry[package + ".lib"]
    library.addin_info = library.ui_layout = SimpleNamespace()
    library.assembly_operations = SimpleNamespace(ATTRIBUTE_GROUP="assembly")
    library.angle_cleat_creator = SimpleNamespace(ATTRIBUTE_GROUP="angle")
    library.brace_bay = SimpleNamespace(find_group=lambda entity: None)
    library.joint_records = SimpleNamespace(ATTRIBUTE_GROUP="joint")
    ancestry["adsk"].core = ancestry["adsk.core"]
    ancestry["adsk"].fusion = ancestry["adsk.fusion"]
    ancestry["adsk.fusion"].Occurrence = Occurrence
    for name in ("ValidateInputsEventHandler", "CommandEventHandler", "CommandCreatedEventHandler"):
        setattr(ancestry["adsk.core"], name, object)
    ancestry[package + ".commands.inspect_assembly"]._assembly = lambda entity: entity.assemblyContext
    with patch.dict(sys.modules, ancestry):
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


class RemoveAssemblyTests(unittest.TestCase):
    def setUp(self):
        self.command = load_command()
        self.marker = Entity(isValid=True, deleteMe=Mock(return_value=True))
        definition = dict(members=["support"], joint_records=[dict(member="support", name="cope_end")])
        component = self.component("Plat d’âme", {("assembly", "definition"): Entity(value=json.dumps(definition))})
        self.support = Occurrence(isValid=True, component=self.component("IPE", {("joint", "cope_end"): self.marker}),
                                  timelineObject=Entity(parentGroup=None))
        self.assembly = Occurrence(isValid=True, component=component, assemblyContext=None)
        self.plate = Occurrence(component=self.component("Platine"), assemblyContext=self.assembly)
        component.allOccurrences = [self.plate]
        self.items = [Entity(entity=self.assembly), Entity(entity=self.plate)]
        self.group = Entity(name=component.name, isValid=True, isCollapsed=True, index=1,
                            count=2, item=self.items.__getitem__, deleteMe=Mock(side_effect=self.delete_group))
        self.assembly.timelineObject = Entity(parentGroup=self.group)
        self.root = Entity(occurrences=[self.support, self.assembly], allOccurrences=[self.support, self.assembly],
                           allOccurrencesByComponent=lambda component: Entity(
                               count=int(self.assembly.isValid), item=lambda index: self.assembly,
                           ))
        self.tail = Entity(isValid=True)
        self.timeline = Entity(markerPosition=3, count=3, item=[None, self.group, self.tail].__getitem__)
        self.design = Entity(rootComponent=self.root, timeline=self.timeline,
                             findEntityByToken=lambda token: [self.support] if token == "support" else [])

    @staticmethod
    def component(name, markers=None):
        return Entity(name=name, allOccurrences=[],
                      attributes=Entity(itemByName=lambda group, key: (markers or {}).get((group, key))))

    def delete_group(self, delete_contents):
        self.assembly.isValid = False
        self.group.isValid = False
        return delete_contents

    def test_deletes_native_group_and_its_recorded_cope_marker(self):
        self.command.remove(self.design, self.plate)
        self.group.deleteMe.assert_called_once_with(True)
        self.marker.deleteMe.assert_called_once_with()
        self.assertTrue(self.support.isValid)
        self.assertTrue(self.tail.isValid)

    def test_refuses_when_scope_contains_another_root_component(self):
        self.support.timelineObject.parentGroup = self.group
        with self.assertRaisesRegex(ValueError, "autre composant racine"):
            self.command.remove(self.design, self.plate)
        self.group.deleteMe.assert_not_called()

    def test_refuses_an_operation_owned_by_an_unrelated_component(self):
        self.items.append(Entity(entity=Entity(parentComponent=self.component("Escalier"))))
        self.group.count += 1
        with self.assertRaisesRegex(ValueError, "Escalier"):
            self.command.remove(self.design, self.plate)
        self.group.deleteMe.assert_not_called()

    def test_angle_group_uses_source_token_after_profile_rename(self):
        definition = Entity(value=json.dumps({"members": ["support"]}))
        self.assembly.component.attributes.itemByName = (
            lambda group, key: definition if (group, key) == ("angle", "definition") else None
        )
        self.support.component.name = "Poutre renommée"
        self.items.append(Entity(entity=Entity(parentComponent=self.support.component)))
        self.group.count += 1
        self.command.remove(self.design, self.plate)
        self.group.deleteMe.assert_called_once_with(True)
        self.assertTrue(self.support.isValid)

    def test_raises_on_cascade_before_deleting_the_cope_marker(self):
        def cascade_delete(delete_contents):
            self.tail.isValid = False
            return self.delete_group(delete_contents)

        self.group.deleteMe.side_effect = cascade_delete
        with self.assertRaisesRegex(RuntimeError, "opération ultérieure"):
            self.command.remove(self.design, self.plate)
        self.marker.deleteMe.assert_not_called()


if __name__ == "__main__":
    unittest.main()
