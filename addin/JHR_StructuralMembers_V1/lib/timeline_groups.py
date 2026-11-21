"""Presentation-only timeline groups; never reorder or delete model features."""
from __future__ import annotations

import logging
from contextlib import contextmanager
from contextvars import ContextVar


_LOG = logging.getLogger(__name__)
_DEFERRED = ContextVar("jhr_timeline_grouping_deferred", default=False)


def _objects(entities):
    return [entity.timelineObject for entity in entities
            if entity and entity.isValid and entity.timelineObject]


def _add(timeline, objects, name):
    indices = [obj.index for obj in objects]
    if not indices or min(indices) < 0:
        return None
    return _add_range(timeline, min(indices), max(indices), name)


def _add_range(timeline, start, end, name):
    if start >= end:
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


@contextmanager
def defer_grouping():
    """Laisse le regroupement à la commande qui possède l’ensemble de la création."""
    token = _DEFERRED.set(True)
    try:
        yield
    finally:
        _DEFERRED.reset(token)


def creation_start(timeline):
    """Relève la fin avant écriture, si la commande ajoute ses opérations tout à la fin."""
    try:
        if timeline is not None and not _DEFERRED.get() and timeline.markerPosition == timeline.count:
            return timeline.count
    except Exception:
        _LOG.warning("Lecture de la fin de timeline impossible", exc_info=True)
    return None


def group_creation(timeline, start, label):
    """Regroupe seulement les opérations ajoutées à la suite depuis creation_start."""
    if start is None or start < 0 or _DEFERRED.get():
        return None
    try:
        end = timeline.count
        if timeline.markerPosition == end:
            return _add_range(timeline, start, end-1, label)
    except Exception:
        # Presentation must not cause a successful creation to be rolled back.
        _LOG.warning("Regroupement de la création impossible (%s)", label, exc_info=True)
    return None


def group_member(occurrence, entities):
    """Group only the newly created occurrence, plane, DXF sketch and sweep."""
    if _DEFERRED.get():
        return None
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
    if _DEFERRED.get():
        return None
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
