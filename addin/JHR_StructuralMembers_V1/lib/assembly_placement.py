"""Rangement des assemblages dans le contexte natif de la conception."""


DEFAULT_PARENT = object()


def _parents(occurrence):
    parent = occurrence.assemblyContext
    while parent:
        yield parent
        parent = parent.assemblyContext


def parent_for(design, members):
    """Prend le conteneur actif ou le plus proche parent commun des appuis."""
    members = tuple(members)
    active = design.activeOccurrence
    if active and active not in members:
        parent = active
    elif members:
        other_parents = [tuple(_parents(member)) for member in members[1:]]
        parent = next((candidate for candidate in _parents(members[0])
                       if all(candidate in chain for chain in other_parents)), None)
    else:
        parent = None
    if parent:
        root = design.rootComponent
        if (any(item.isReferencedComponent for item in (parent, *_parents(parent)))
                or root.allOccurrencesByComponent(parent.component).count != 1):
            raise ValueError("Le sous-assemblage cible doit être local et présent une seule fois.")
    return parent


def move_group(design, group, parent):
    """Déplace le composant existant avec ses références et contrôle sa pose réelle."""
    if not parent or group.assemblyContext == parent:
        return group
    component = group.component

    def bounds(item):
        box = item.preciseBoundingBox
        return (*box.minPoint.asArray(), *box.maxPoint.asArray())

    previous = bounds(group)
    if not group.moveToComponent(parent):
        raise RuntimeError("Fusion n’a pas rangé l’assemblage dans le composant cible.")
    occurrences = design.rootComponent.allOccurrencesByComponent(component)
    if occurrences.count != 1 or occurrences.item(0).assemblyContext != parent:
        raise RuntimeError("Le sous-assemblage créé n’est pas identifiable à l’emplacement demandé.")
    placed = occurrences.item(0)
    if max(abs(before-after) for before, after in zip(previous, bounds(placed))) > 1e-3:
        raise RuntimeError("Le rangement a modifié la position de l’assemblage.")
    return placed
