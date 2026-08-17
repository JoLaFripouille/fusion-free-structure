from __future__ import annotations

from dataclasses import dataclass

from . import member_metadata


@dataclass(frozen=True)
class CurveUsage:
    curve: object
    occurrences: tuple


def _attribute_value(component, name):
    attribute = component.attributes.itemByName(
        member_metadata.ATTRIBUTE_GROUP,
        name,
    )
    return str(attribute.value).strip() if attribute else ""


def _source_token(component):
    return _attribute_value(component, "source_curve_token") or _attribute_value(
        component,
        "source_line_token",
    )


def _native_entity(entity):
    native = getattr(entity, "nativeObject", None)
    return native if native else entity


def _same_entity(first, second):
    first = _native_entity(first)
    second = _native_entity(second)
    if first == second:
        return True
    first_token = str(getattr(first, "entityToken", ""))
    second_token = str(getattr(second, "entityToken", ""))
    return bool(first_token and first_token == second_token)


def curve_usages(design, root_component, curves):
    """Retrouve les composants de barre déjà liés aux courbes demandées."""
    usages = [[curve, []] for curve in curves]
    for occurrence in root_component.allOccurrences:
        component = occurrence.component
        token = _source_token(component)
        if not token:
            continue
        for entity in design.findEntityByToken(token):
            for curve, occurrences in usages:
                if _same_entity(entity, curve) and occurrence not in occurrences:
                    occurrences.append(occurrence)
    return tuple(
        CurveUsage(curve=curve, occurrences=tuple(occurrences))
        for curve, occurrences in usages
    )


def unique_used_occurrences(usages):
    result = []
    for usage in usages:
        for occurrence in usage.occurrences:
            if occurrence not in result:
                result.append(occurrence)
    return tuple(result)
