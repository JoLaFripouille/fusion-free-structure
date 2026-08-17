from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, replace


_STEEL_WORDS = (
    "acier",
    "steel",
    "stainless",
    "inox",
    "stahl",
    "acero",
    "acciaio",
)
_STRUCTURAL_GRADE = re.compile(r"(?<![a-z0-9])s(?:235|275|355|420|460)(?!\d)")
_GENERIC_DEFAULT_NAMES = (
    "steel",
    "acier",
    "mild steel",
    "acier doux",
    "structural steel",
    "acier de construction",
)
DOCUMENT_MATERIAL_SOURCE_ID = "EI_JHR_ACTIVE_DOCUMENT_MATERIALS"
DOCUMENT_MATERIAL_SOURCE_NAME = "Document actif"


@dataclass(frozen=True)
class MaterialChoice:
    library_id: str
    library_name: str
    material_id: str
    material_name: str
    property_count: int
    display_label: str = ""
    document_index: int | None = None


def _normalized(value):
    text = unicodedata.normalize("NFKD", str(value))
    return "".join(character for character in text if not unicodedata.combining(character)).casefold()


def is_steel_material(name, description=""):
    """Détecte les matériaux acier sans supposer une langue unique de Fusion."""
    searchable = "{} {}".format(_normalized(name), _normalized(description))
    return any(word in searchable for word in _STEEL_WORDS) or bool(
        _STRUCTURAL_GRADE.search(searchable)
    )


def _with_unique_labels(choices):
    counts = {}
    labeled = []
    for choice in choices:
        base = "{} — {}".format(choice.material_name, choice.library_name)
        counts[base] = counts.get(base, 0) + 1
        suffix = "" if counts[base] == 1 else " [{}]".format(counts[base])
        labeled.append(replace(choice, display_label=base + suffix))
    return tuple(labeled)


def _append_material_choices(choices, seen, materials, library_id, library_name):
    for material_index in range(materials.count):
        material = materials.item(material_index)
        if not material or not material.isValid:
            continue
        if not is_steel_material(material.name, material.description):
            continue
        properties = material.materialProperties
        property_count = int(properties.count) if properties else 0
        if property_count == 0:
            continue
        is_document_material = library_id == DOCUMENT_MATERIAL_SOURCE_ID
        identity = (
            str(library_id),
            material_index if is_document_material else str(material.id),
        )
        if identity in seen:
            continue
        seen.add(identity)
        choices.append(
            MaterialChoice(
                library_id=str(library_id),
                library_name=str(library_name),
                material_id=str(material.id),
                material_name=str(material.name),
                property_count=property_count,
                document_index=(material_index if is_document_material else None),
            )
        )


def discover_steel_materials(material_libraries, document_materials=None):
    """Inventorie les matériaux acier réellement disponibles dans Fusion."""
    choices = []
    seen = set()
    if document_materials is not None:
        _append_material_choices(
            choices,
            seen,
            document_materials,
            DOCUMENT_MATERIAL_SOURCE_ID,
            DOCUMENT_MATERIAL_SOURCE_NAME,
        )
    for library_index in range(material_libraries.count):
        library = material_libraries.item(library_index)
        if not library or not library.isValid:
            continue
        _append_material_choices(
            choices,
            seen,
            library.materials,
            library.id,
            library.name,
        )

    choices.sort(
        key=lambda choice: (
            choice.library_id != DOCUMENT_MATERIAL_SOURCE_ID,
            _normalized(choice.material_name),
            _normalized(choice.library_name),
            choice.material_id,
        )
    )
    return _with_unique_labels(choices)


def default_choice(choices):
    if not choices:
        raise ValueError(
            "Aucun matériau acier n'est disponible dans les bibliothèques chargées par Fusion."
        )
    for choice in choices:
        if (
            choice.library_id == DOCUMENT_MATERIAL_SOURCE_ID
            and _normalized(choice.material_name).startswith("s235jr")
        ):
            return choice
    for expected_name in _GENERIC_DEFAULT_NAMES:
        for choice in choices:
            if _normalized(choice.material_name) == expected_name:
                return choice
    return choices[0]


def choice_from_label(choices, display_label):
    for choice in choices:
        if choice.display_label == display_label:
            return choice
    raise ValueError("Le matériau Fusion sélectionné n'est plus disponible.")


def resolve_material(material_libraries, choice, document_materials=None):
    """Résout par identifiants uniques, jamais par un nom potentiellement ambigu."""
    if choice.library_id == DOCUMENT_MATERIAL_SOURCE_ID:
        if document_materials is None:
            raise RuntimeError("Les matériaux du document actif ne sont plus disponibles.")
        if choice.document_index is not None:
            index = int(choice.document_index)
            if 0 <= index < document_materials.count:
                material = document_materials.item(index)
                if (
                    material
                    and material.isValid
                    and str(material.id) == choice.material_id
                    and str(material.name) == choice.material_name
                ):
                    return material

        matches = []
        for material_index in range(document_materials.count):
            material = document_materials.item(material_index)
            if (
                material
                and material.isValid
                and str(material.name) == choice.material_name
            ):
                matches.append(material)
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise RuntimeError(
                "Plusieurs matériaux Fusion portent le nom '{}' dans le document actif."
                .format(choice.material_name)
            )
        raise RuntimeError(
            "Le matériau Fusion '{}' n'est plus disponible dans le document actif."
            .format(choice.material_name)
        )

    library = material_libraries.itemById(choice.library_id)
    if not library or not library.isValid:
        raise RuntimeError(
            "La bibliothèque Fusion '{}' n'est plus disponible.".format(
                choice.library_name
            )
        )
    material = library.materials.itemById(choice.material_id)
    if not material or not material.isValid:
        raise RuntimeError(
            "Le matériau Fusion '{}' n'est plus disponible dans '{}'.".format(
                choice.material_name,
                choice.library_name,
            )
        )
    return material
