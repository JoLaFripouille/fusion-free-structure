import copy
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADDIN = ROOT / "addin" / "JHR_StructuralMembers_V1"
sys.path.insert(0, str(ADDIN))

from lib import structural_materials


class FakeUnitsManager:
    def convert(self, value, input_units, output_units):
        raise AssertionError("La conversion des matériaux ne doit pas dépendre de Fusion.")


class FakeProperty:
    def __init__(self, property_id, name, units, value=0.0, read_only=False):
        self.id = property_id
        self.name = name
        self.units = units
        self.value = value
        self.isReadOnly = read_only


class FakeProperties:
    def __init__(self, properties):
        self._properties = properties
        self.count = len(properties)

    def item(self, index):
        return self._properties[index]


def steel_properties(yield_strength=235.0, tensile_strength=360.0):
    return FakeProperties(
        [
            FakeProperty("PrismMaterialDensity", "Densité", "kg/m^3", 7850.0),
            FakeProperty(
                "PrismMaterialYoungModulus",
                "Module d'Young",
                "MPa",
                210000.0,
            ),
            FakeProperty(
                "PrismMaterialPoissonsRatio",
                "Coefficient de Poisson",
                "Unitless",
                0.30,
            ),
            FakeProperty(
                "PrismMaterialYieldStrength",
                "Limite d'élasticité",
                "MPa",
                yield_strength,
            ),
            FakeProperty(
                "PrismMaterialTensileStrength",
                "Résistance à la traction",
                "MPa",
                tensile_strength,
            ),
        ]
    )


class FakeMaterial:
    def __init__(self, material_id, name, properties=None, description=""):
        self.id = material_id
        self.name = name
        self.description = description
        self.materialProperties = properties or steel_properties()
        self.isValid = True
        self.isUsed = False

    def deleteMe(self):
        self.isValid = False
        return True


class FakeMaterials:
    def __init__(self, materials):
        self._materials = list(materials)
        self.add_count = 0

    @property
    def count(self):
        return len([material for material in self._materials if material.isValid])

    def item(self, index):
        return [material for material in self._materials if material.isValid][index]

    def itemById(self, material_id):
        return next(
            (
                material
                for material in self._materials
                if material.isValid and material.id == material_id
            ),
            None,
        )

    def addByCopy(self, material, name):
        self.add_count += 1
        copied = FakeMaterial(
            "document-material-{}".format(self.add_count),
            name,
            copy.deepcopy(material.materialProperties),
            material.description,
        )
        self._materials.append(copied)
        return copied


class FakeLibrary:
    def __init__(self, library_id, name, materials):
        self.id = library_id
        self.name = name
        self.materials = materials
        self.isValid = True


class FakeLibraries:
    def __init__(self, libraries):
        self._libraries = list(libraries)
        self.count = len(libraries)

    def item(self, index):
        return self._libraries[index]

    def itemById(self, library_id):
        return next(
            (library for library in self._libraries if library.id == library_id),
            None,
        )


class FakeDesign:
    def __init__(self, materials):
        self.materials = materials
        self.unitsManager = FakeUnitsManager()


def material_for_spec(spec, material_id):
    yield_value = float(spec.yield_strength.split()[0])
    tensile_value = float(spec.tensile_strength.split()[0])
    return FakeMaterial(
        material_id,
        spec.name,
        steel_properties(yield_value, tensile_value),
    )


class StructuralMaterialTests(unittest.TestCase):
    def setUp(self):
        self.base = FakeMaterial("fusion-steel", "Acier", steel_properties())
        self.libraries = FakeLibraries(
            [
                FakeLibrary(
                    "fusion-library",
                    "Bibliothèque de matériaux Fusion",
                    FakeMaterials([self.base]),
                )
            ]
        )

    def test_creates_all_required_materials_once(self):
        document_materials = FakeMaterials([])
        design = FakeDesign(document_materials)

        first = structural_materials.ensure_required_materials(
            design,
            self.libraries,
        )
        second = structural_materials.ensure_required_materials(
            design,
            self.libraries,
        )

        self.assertEqual(first.existing_names, ())
        self.assertEqual(
            first.created_names,
            tuple(spec.name for spec in structural_materials.REQUIRED_MATERIALS),
        )
        self.assertEqual(second.created_names, ())
        self.assertEqual(document_materials.add_count, 3)
        self.assertEqual(document_materials.count, 3)

    def test_s275jr_uses_the_expected_first_thickness_range_values(self):
        s275_spec = structural_materials.REQUIRED_MATERIALS[1]

        self.assertEqual(s275_spec.grade, "S275JR")
        self.assertEqual(s275_spec.maximum_thickness_mm, 16)
        self.assertEqual(s275_spec.yield_strength, "275 MPa")
        self.assertEqual(s275_spec.tensile_strength, "410 MPa")

    def test_existing_conforming_material_is_not_modified(self):
        s235_spec = structural_materials.REQUIRED_MATERIALS[0]
        existing = material_for_spec(s235_spec, "existing-s235")
        original_description = existing.description
        document_materials = FakeMaterials([existing])

        result = structural_materials.ensure_required_materials(
            FakeDesign(document_materials),
            self.libraries,
        )

        self.assertEqual(result.existing_names, (s235_spec.name,))
        self.assertEqual(document_materials.add_count, 2)
        self.assertEqual(existing.description, original_description)

    def test_existing_material_with_wrong_strength_is_rejected_without_change(self):
        s235_spec = structural_materials.REQUIRED_MATERIALS[0]
        conflicting = FakeMaterial(
            "conflict",
            s235_spec.name,
            steel_properties(999.0, 360.0),
        )
        document_materials = FakeMaterials([conflicting])

        with self.assertRaisesRegex(RuntimeError, "ne correspond pas"):
            structural_materials.ensure_required_materials(
                FakeDesign(document_materials),
                self.libraries,
            )

        self.assertEqual(document_materials.add_count, 0)
        self.assertEqual(conflicting.materialProperties.item(3).value, 999.0)

    def test_missing_base_property_prevents_partial_creation(self):
        incomplete_properties = FakeProperties(
            steel_properties()._properties[:-1]
        )
        self.base.materialProperties = incomplete_properties
        document_materials = FakeMaterials([])

        with self.assertRaisesRegex(RuntimeError, "tensile_strength"):
            structural_materials.ensure_required_materials(
                FakeDesign(document_materials),
                self.libraries,
            )

        self.assertEqual(document_materials.add_count, 0)
        self.assertEqual(document_materials.count, 0)

    def test_material_values_are_converted_to_declared_property_units(self):
        poisson_property = FakeProperty(
            "PrismMaterialPoissonsRatio",
            "Coefficient de Poisson",
            "Unitless",
            0.30,
        )
        self.assertEqual(
            structural_materials._expected_value(
                FakeUnitsManager(),
                poisson_property,
                "0.3",
                "poisson_ratio",
                0.3,
            ),
            0.3,
        )
        self.assertEqual(
            structural_materials._physical_value_in_property_units(
                "density",
                "7850 kg/m^3",
                "kg / m^3",
            ),
            7850.0,
        )
        self.assertEqual(
            structural_materials._physical_value_in_property_units(
                "density",
                "7850 kg/m^3",
                "KilogramPerCubicMeter",
            ),
            7850.0,
        )
        self.assertAlmostEqual(
            structural_materials._physical_value_in_property_units(
                "density",
                "7850 kg/m^3",
                "kg / mm^3",
            ),
            7.85e-6,
            places=12,
        )
        self.assertEqual(
            structural_materials._physical_value_in_property_units(
                "young_modulus",
                "210 GPa",
                "Pa",
            ),
            210e9,
        )
        self.assertEqual(
            structural_materials._physical_value_in_property_units(
                "young_modulus",
                "210 GPa",
                "Pascal",
            ),
            210e9,
        )
        self.assertEqual(
            structural_materials._physical_value_in_property_units(
                "yield_strength",
                "355 MPa",
                "N / mm^2",
            ),
            355.0,
        )
        self.assertEqual(
            structural_materials._physical_value_in_property_units(
                "yield_strength",
                "355 MPa",
                "Megapascal",
            ),
            355.0,
        )


if __name__ == "__main__":
    unittest.main()
