"""Presentation-only timeline groups; never reorder or delete model features."""
from __future__ import annotations

import logging


_LOG = logging.getLogger(__name__)


def _objects(entities):
    return [entity.timelineObject for entity in entities
            if entity and entity.isValid and entity.timelineObject]


def _add(timeline, objects, name):
    indices = [obj.index for obj in objects]
    if not indices or min(indices) < 0:
        return None
    start, end = min(indices), max(indices)
    if start == end:
        # Native Fusion requires at least two timeline items per group.
        return None
    # Do not absorb an existing group, including an expanded group whose index
    # is -1. Groups cannot be nested in Fusion.
    for index in range(start, end + 1):
        item = timeline.item(index)
        if item.isGroup or item.parentGroup:
            return None
    group = timeline.timelineGroups.add(start, end)
    if not group:
        raise RuntimeError("Fusion n'a pas créé le groupe de timeline.")
    group.name = name
    group.isCollapsed = True
    return group


def group_member(occurrence, entities):
    """Group only the newly created occurrence, plane, DXF sketch and sweep."""
    try:
        timeline = occurrence.component.parentDesign.timeline
        return _add(timeline, _objects(entities), occurrence.component.name)
    except Exception:
        # Presentation failure must not roll back an otherwise valid member.
        _LOG.warning("Regroupement du profil impossible", exc_info=True)
        return None


def group_operations(occurrence, entities, label):
    """Extend an adjacent member group, otherwise create a named operation group.

    Expansion is needed before reading child indices: collapsed children have
    index -1. Keep object references, never persist timeline indices.
    """
    previous = None
    was_collapsed = False
    expanded = False
    children = []
    old_name = ""
    timeline = None
    try:
        objects = _objects(entities)
        if not objects:
            return None
        timeline = occurrence.component.parentDesign.timeline
        previous = occurrence.timelineObject.parentGroup
        if previous and previous.name == occurrence.component.name:
            was_collapsed = previous.isCollapsed
            children = [previous.item(i) for i in range(previous.count)]
            old_name = previous.name
            previous.isCollapsed = False
            expanded = True
            indices = [obj.index for obj in objects]
            last = max(obj.index for obj in children)
            if min(indices) == last + 1 and min(indices) >= 0:
                # Fusion has no writable group bounds. Ungroup while retaining
                # every feature, then rebuild the contiguous presentation group.
                previous.isCollapsed = True
                if not previous.deleteMe(False):
                    raise RuntimeError("Fusion n'a pas pu dégrouper la timeline.")
                replacement = _add(timeline, children + objects, old_name)
                if not replacement:
                    raise RuntimeError("Fusion n'a pas pu étendre le groupe.")
                return replacement
        return _add(timeline, objects, "{} — {}".format(occurrence.component.name, label))
    except Exception:
        # If recreation failed, restore the old presentation group. Its model
        # features were retained by deleteMe(False).
        if previous and not previous.isValid and children:
            try:
                _add(timeline, children, old_name)
            except Exception:
                _LOG.warning("Restauration du groupe impossible", exc_info=True)
        _LOG.warning("Regroupement des opérations impossible", exc_info=True)
        return None
    finally:
        if expanded and previous and previous.isValid:
            try:
                previous.isCollapsed = was_collapsed
            except Exception:
                _LOG.warning("Restauration de l'affichage impossible", exc_info=True)


def release_member_group(occurrence):
    """Expose the occurrence before existing replacement/rollback deletion."""
    timeline_object = occurrence.timelineObject
    group = timeline_object.parentGroup if timeline_object else None
    if group and group.name == occurrence.component.name:
        was_collapsed = group.isCollapsed
        try:
            # Native Fusion rejects deleteMe(False) on an expanded group.
            group.isCollapsed = True
            if not group.deleteMe(False):
                raise RuntimeError("Fusion n'a pas pu dégrouper la barre à retirer.")
        finally:
            if group.isValid:
                group.isCollapsed = was_collapsed
