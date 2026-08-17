import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADDIN = ROOT / "addin" / "JHR_StructuralMembers_V1"
sys.path.insert(0, str(ADDIN))

from lib import physical_materials


class FakeProperties:
    def __init__(self, count):
        self.count = count


class FakeMaterial:
    def __init__(self, material_id, name, description="", property_count=8):
        self.id = material_id
        self.name = name
        self.description = description
        self.materialProperties = FakeProperties(property_count)
        self.isValid = True


class FakeMaterials:
    def __init__(self, materials):
        self._materials = materials
        self.count = len(materials)

    def item(self, index):
        return self._materials[index]

    def itemById(self, material_id):
        return next(
            (material for material in self._materials if material.id == material_id),
            None,
        )


class FakeLibrary:
    def __init__(self, library_id, name, materials):
        self.id = library_id
        self.name = name
        self.materials = FakeMaterials(materials)
        self.isValid = True


class FakeLibraries:
    def __init__(self, libraries):
        self._libraries = libraries
        self.count = len(libraries)

    def item(self, index):
        return self._libraries[index]

    def itemById(self, library_id):
        return next(
            (library for library in self._libraries if library.id == library_id),
            None,
        )


class PhysicalMaterialsTests(unittest.TestCase):
    def setUp(self):
        self.steel = FakeMaterial("mat-steel", "Acier", "Acier de construction")
        self.s355 = FakeMaterial("mat-s355", "S355J2", "Nuance structurale")
        self.aluminium = FakeMaterial("mat-al", "Aluminium 6061")
        self.library = FakeLibrary(
            "lib-fusion",
            "Bibliothèque de matériaux Fusion",
            [self.aluminium, self.s355, self.steel],
        )
        self.libraries = FakeLibraries([self.library])

    def test_only_real_steel_candidates_are_listed(self):
        choices = physical_materials.discover_steel_materials(self.libraries)
        self.assertEqual(
            [choice.material_id for choice in choices],
            ["mat-steel", "mat-s355"],
        )
        self.assertTrue(all(choice.property_count == 8 for choice in choices))

    def test_default_prefers_generic_fusion_steel(self):
        choices = physical_materials.discover_steel_materials(self.libraries)
        self.assertEqual(physical_materials.default_choice(choices).material_id, "mat-steel")

    def test_choice_and_resolution_use_unique_ids(self):
        choices = physical_materials.discover_steel_materials(self.libraries)
        selected = physical_materials.choice_from_label(choices, choices[1].display_label)
        self.assertIs(
            physical_materials.resolve_material(self.libraries, selected),
            self.s355,
        )

    def test_document_materials_are_listed_and_resolved(self):
        document_s235 = FakeMaterial(
            "doc-s235",
            "S235JR EN 10025-2 - t<=16 mm",
            "Acier de construction européen",
        )
        document_materials = FakeMaterials([document_s235])
        choices = physical_materials.discover_steel_materials(
            self.libraries,
            document_materials,
        )
        self.assertEqual(choices[0].material_id, "doc-s235")
        self.assertEqual(
            physical_materials.default_choice(choices).material_id,
            "doc-s235",
        )
        selected = next(
            choice for choice in choices if choice.material_id == "doc-s235"
        )
        self.assertEqual(
            selected.library_id,
            physical_materials.DOCUMENT_MATERIAL_SOURCE_ID,
        )
        self.assertIs(
            physical_materials.resolve_material(
                self.libraries,
                selected,
                document_materials,
            ),
            document_s235,
        )

    def test_document_material_resolution_requires_active_document(self):
        choice = physical_materials.MaterialChoice(
            physical_materials.DOCUMENT_MATERIAL_SOURCE_ID,
            physical_materials.DOCUMENT_MATERIAL_SOURCE_NAME,
            "missing",
            "S235JR",
            5,
            "S235JR — Document actif",
        )
        with self.assertRaisesRegex(RuntimeError, "document actif"):
            physical_materials.resolve_material(self.libraries, choice)

    def test_duplicate_visible_names_get_unique_labels(self):
        second_library = FakeLibrary(
            "lib-custom",
            "Ma bibliothèque",
            [FakeMaterial("mat-custom", "Acier")],
        )
        choices = physical_materials.discover_steel_materials(
            FakeLibraries([self.library, second_library])
        )
        self.assertEqual(len({choice.display_label for choice in choices}), len(choices))

    def test_missing_steel_is_reported(self):
        choices = physical_materials.discover_steel_materials(
            FakeLibraries([FakeLibrary("lib", "Fusion", [self.aluminium])])
        )
        with self.assertRaisesRegex(ValueError, "Aucun matériau acier"):
            physical_materials.default_choice(choices)

    def test_steel_without_physical_properties_is_not_offered(self):
        choices = physical_materials.discover_steel_materials(
            FakeLibraries(
                [
                    FakeLibrary(
                        "lib",
                        "Fusion",
                        [FakeMaterial("empty", "Steel placeholder", property_count=0)],
                    )
                ]
            )
        )
        self.assertEqual(choices, ())


if __name__ == "__main__":
    unittest.main()
