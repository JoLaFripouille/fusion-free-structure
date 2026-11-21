"""Tronçonnage ciblé d'un garde-corps JHR au droit d'un poteau plat."""

import json
import math
import re
from itertools import product

import adsk.core as core
import adsk.fusion as fusion

from . import guardrail_layout as layout, guardrail_operations as operations
from . import bolt_specs, fastener_geometry, joint_geometry as geo, simple_fastener_creator, timeline_groups


_BOLT_DIAMETER_MM = 8.
_BORE_DIAMETER_MM = 10.
_BOLT_HEAD = "CHC"
_BOLT_HEIGHTS = (.15, .35, .55, .72, .9)


def _piece_name(component):
    marker = component.attributes.itemByName(operations.ATTRIBUTE_GROUP, "piece_name")
    if marker:
        return marker.value
    return re.sub(r" \(\d+\)$", "", component.name)


def _same_piece(a, b):
    return (a.nativeObject or a) == (b.nativeObject or b)


def _group_for_post(design, selected):
    root = design.rootComponent
    for group in root.occurrences:
        marker = group.component.attributes.itemByName(operations.ATTRIBUTE_GROUP, "definition")
        if marker and any(_same_piece(child, selected) for child in group.childOccurrences):
            if root.allOccurrencesByComponent(group.component).count != 1:
                raise ValueError("Le garde-corps est instancié plusieurs fois.")
            if any(abs(a-b) > 1e-6 for a, b in zip(
                    group.transform2.asArray(), core.Matrix3D.create().asArray())):
                raise ValueError("Replacer le groupe de garde-corps dans son repère de création.")
            return group, json.loads(marker.value)
    raise ValueError("Sélectionner un poteau d’un garde-corps Structure JHR.")


def _resolve(design, tokens, caster):
    values = []
    for token in tokens:
        found = [item for entity in design.findEntityByToken(token)
                 if (item := caster(entity)) and item.isValid]
        if len(found) != 1:
            raise ValueError("Un segment ou un appui du garde-corps a perdu sa référence.")
        values.append(found[0])
    return values


def _layout(design, definition):
    paths = _resolve(design, definition["paths"], lambda entity: fusion.SketchLine.cast(entity)
                     or fusion.BRepEdge.cast(entity))
    faces = _resolve(design, definition["faces"], fusion.BRepFace.cast)
    if len(faces) == 1:
        faces *= len(paths)
    settings = layout._settings(definition["settings"])
    axes = ("Y", "Z") if settings["vertical_axis"] == "auto" else (settings["vertical_axis"],)
    for index, axis in enumerate(axes):
        settings["vertical_axis"] = axis
        try:
            segments = [operations._project_to_face(start, end, face, settings["mounting"],
                                                     layout.VERTICAL_AXES[axis])
                        for (start, end), face in zip(operations._ends(paths), faces)]
            return layout.plan_guardrail(segments, settings)
        except ValueError:
            if index == len(axes)-1:
                raise


def _editable(component):
    if component.bRepBodies.count != 1 or component.features.baseFeatures.count != 1:
        raise ValueError(f"{component.name} doit être une pièce JHR à corps unique.")
    base = component.features.baseFeatures.item(0)
    if base.bodies.count != 1 or len(base.sourceBodies) != 1:
        raise ValueError(f"{component.name} ne correspond plus au corps d’origine.")
    return base, base.bodies.item(0)


def _identity_occurrence(occurrence):
    if any(abs(a-b) > 1e-6 for a, b in zip(
            occurrence.transform2.asArray(), core.Matrix3D.create().asArray())):
        raise ValueError(f"{occurrence.component.name} n’est plus dans son repère de création.")


def _extent(body):
    box = body.boundingBox
    return 40*box.minPoint.distanceTo(box.maxPoint)+100.


def _crosses(body, normal, station):
    box = body.boundingBox
    corners = product(*zip(operations._mm(box.minPoint), operations._mm(box.maxPoint)))
    extents = [geo.dot(p, normal) for p in corners]
    return min(extents)+layout.TOL < station < max(extents)-layout.TOL


def _clip(manager, source, point, normal, extent, label):
    result = manager.copy(source)
    operations._trim(manager, result, point, normal, extent, label)
    if (not result.isSolid or result.lumps.count != 1 or result.volume <= 1e-8
            or result.volume >= source.volume-1e-8):
        raise ValueError(f"{label} ne donne pas deux tronçons solides distincts.")
    return result


def _check_volume(original, before, after, gap, label):
    total = before.volume+after.volume
    if gap == 0:
        if not math.isclose(total, original.volume, rel_tol=1e-6, abs_tol=1e-5):
            raise RuntimeError(f"{label} : les deux tronçons ne reconstituent pas le volume initial.")
    elif total >= original.volume:
        raise RuntimeError(f"{label} : le jeu demandé n’a pas été créé.")


def _rail_parts(group, row, cuts, manager):
    updates, additions = [], []
    for rail, cut in zip(row, cuts):
        label = rail["name"]
        piece_name = rail["piece_name"]
        candidates = []
        for occurrence in group.component.allOccurrences:
            if _piece_name(occurrence.component) != piece_name:
                continue
            _identity_occurrence(occurrence)
            base, body = _editable(occurrence.component)
            normal = cut["normal"]
            if (_crosses(body, normal, geo.dot(cut["before"], normal))
                    and _crosses(body, normal, geo.dot(cut["after"], normal))):
                candidates.append((base, body))
        found = []
        for base, body in candidates:
            extent = _extent(body)
            normal = cut["normal"]
            try:
                before = _clip(manager, body, cut["before"], normal, extent, label)
                after = _clip(manager, body, cut["after"], geo.scale(normal, -1.), extent, label)
            except ValueError:
                continue
            found.append((base, body, before, after))
        if len(found) != 1:
            raise ValueError(f"{label} : aucun tronçon unique à couper à cette station.")
        base, body, before, after = found[0]
        _check_volume(body, before, after, layout._dist(cut["before"], cut["after"]), label)
        updates.append((base, manager.copy(body), before))
        additions.append((piece_name, after, body.material))
    return updates, additions


def _post_parts(manager, selected, post, row, split):
    base, body = _editable(selected.component)
    axis = split["post_normal"]
    label = _piece_name(selected.component)
    station = geo.dot(post["start"], axis)
    distances = [geo.dot(operations._mm(vertex.geometry), axis) for vertex in body.vertices]
    depth = post["section"]["depth_mm"]
    if (not distances or abs(min(distances)-station+depth/2) > .02
            or abs(max(distances)-station-depth/2) > .02):
        raise ValueError("La position ou l’épaisseur du poteau a changé depuis sa création.")
    extent = _extent(body)
    plane = split["interface"]
    if split["mode"] == "halves":
        before = _clip(manager, body, plane, axis, extent, label)
        after = _clip(manager, body, plane, geo.scale(axis, -1), extent, label)
        _check_volume(body, before, after, 0, label)
        return base, body, before, after, label+" · demi-poteau suivant"

    thickness = split["added_thickness_mm"]
    if thickness == depth:
        after = manager.copy(body)
    else:
        point = geo.subtract(plane, geo.scale(axis, thickness))
        after = _clip(manager, body, point, geo.scale(axis, -1), extent, label)
    direction = row[0]["direction"]
    delta = geo.scale(direction, .1*thickness/geo.dot(axis, direction))
    shift = core.Matrix3D.create()
    shift.translation = core.Vector3D.create(*delta)
    if not manager.transform(after, shift):
        raise RuntimeError("Fusion n’a pas déplacé le plat adjacent.")
    return base, body, manager.copy(body), after, label+" · plat adjacent"


def _check_existing_plate(group, plate):
    matches = [occurrence for occurrence in group.childOccurrences
               if _piece_name(occurrence.component) == plate["name"]]
    if len(matches) != 1 or matches[0].component.bRepBodies.count != 1:
        raise ValueError("La platine d’appui du poteau n’est plus identifiable.")
    occurrence = matches[0]
    point, u, v, _ = occurrence.transform2.getAsCoordinateSystem()
    area = plate["along_mm"]*plate["across_mm"] - sum(math.pi*(diameter/2)**2
                                                   for _, _, diameter in plate["holes"])
    expected = area*plate["thickness_mm"]*.001
    if (layout._dist(operations._mm(point), plate["center"]) > layout.TOL
            or geo.dot(u.asArray(), plate["u"]) < .999999
            or geo.dot(v.asArray(), plate["v"]) < .999999
            or not math.isclose(occurrence.component.bRepBodies.item(0).volume, expected,
                                rel_tol=1e-5, abs_tol=1e-5)):
        raise ValueError("La platine d’appui a été modifiée. Vérifier l’assise du plat ajouté.")


def _rod(manager, start, end, axis, radius, extra=0.):
    a = operations._point(geo.subtract(start, geo.scale(axis, extra)))
    b = operations._point(geo.add(end, geo.scale(axis, extra)))
    return manager.createCylinderOrCone(a, radius*.1, b, radius*.1)


def _seat_has_material(manager, body, start, end, axis, radius):
    # Laisse les deux faces d'appui hors du test d'intersection pour éviter
    # que le solveur ait à comparer des surfaces coïncidentes.
    tool = _rod(manager, start, end, axis, radius, extra=-.03)
    copy = manager.copy(body)
    if not manager.booleanOperation(copy, tool, fusion.BooleanTypes.IntersectionBooleanType):
        return False
    return (copy.lumps.count == 1 and math.isclose(copy.volume, tool.volume, rel_tol=1e-5, abs_tol=1e-5))


def _post_bolts(manager, before, after, post, split, count):
    if type(count) is not int or not 0 <= count <= len(_BOLT_HEIGHTS):
        raise ValueError("Choisir de 0 à 5 boulons de liaison.")
    if not count:
        split["bolts"] = 0
        return (), None
    spec, _ = bolt_specs.modeled_spec(_BOLT_DIAMETER_MM, _BOLT_HEAD)
    axis, up = split["post_normal"], post["direction"]
    interface = split["interface"]
    base = split["existing_thickness_mm"]
    addition = split["added_thickness_mm"]
    radius = _BORE_DIAMETER_MM/2
    bearing = spec.washer_outer_diameter_mm/2 + .5
    # Répartition de la mezzanine ramenée à la hauteur disponible au montage.
    cap = post["tip_planes"][0][0] if post["tip_planes"] else post["end"]
    height = geo.dot(geo.subtract(cap, post["start"]), up)
    fractions = (0.5,) if count == 1 else tuple(
        _BOLT_HEIGHTS[round(index*(len(_BOLT_HEIGHTS)-1)/(count-1))]
        for index in range(count)
    )
    positions, spans, used = [], [], []
    for fraction in fractions:
        for adjustment in (0., -8., 8., -16., 16., -24., 24., -32., 32., -40., 40.):
            station = fraction*height + adjustment
            if (min(station, height-station) <= bearing
                    or any(abs(station-other) <= 2*bearing for other in used)):
                continue
            center = geo.add(interface, geo.scale(up, station))
            entry = geo.subtract(center, geo.scale(axis, base))
            exit = geo.add(center, geo.scale(axis, addition))
            if (_seat_has_material(manager, before, entry, center, axis, bearing)
                    and _seat_has_material(manager, after, center, exit, axis, bearing)):
                break
        else:
            raise ValueError("L’appui des rondelles rencontre les lisses ou déborde des plats. Réduire le nombre de boulons.")
        used.append(station)
        positions.append(center)
        spans.append((entry, exit))
    for entry, exit in spans:
        tool = _rod(manager, entry, exit, axis, radius, extra=.2)
        for body, thickness in ((before, base), (after, addition)):
            original_volume = body.volume
            operations._difference(manager, body, tool, "Boulonnage des deux plats")
            expected = math.pi*(radius*.1)**2*thickness*.1
            if (not body.isSolid or body.lumps.count != 1 or not math.isclose(
                    original_volume-body.volume, expected, rel_tol=1e-5, abs_tol=1e-5)):
                raise RuntimeError("Un perçage ne traverse pas entièrement l’épaisseur du plat.")
    entry, exit = (geo.scale(p, .1) for p in spans[0])
    holes = [fastener_geometry.Hole(geo.scale(position, .1), axis, _BORE_DIAMETER_MM*.1)
             for position in positions]
    _, poses, _, length = fastener_geometry.plan_modeled_fasteners(
        holes, fastener_geometry.SupportPlane(entry, axis), fastener_geometry.SupportPlane(exit, axis),
        _BOLT_DIAMETER_MM, head=_BOLT_HEAD,
    )
    split.update(bolts=len(poses), bore_diameter_mm=_BORE_DIAMETER_MM,
                 bolt_diameter_mm=_BOLT_DIAMETER_MM, bolt_length_mm=length,
                 bolt_heights_mm=sorted(used))
    return poses, length


def _update_body(base, body):
    if not base.startEdit():
        raise RuntimeError("Fusion n’a pas ouvert le corps d’origine en édition.")
    try:
        if not base.updateBody(base.sourceBodies[0], body):
            raise RuntimeError("Fusion n’a pas conservé l’identité du corps d’origine.")
    finally:
        if not base.finishEdit():
            raise RuntimeError("Fusion n’a pas terminé l’édition du corps.")
    if (base.bodies.count != 1 or not math.isclose(base.bodies.item(0).volume, body.volume,
                                                    rel_tol=1e-6, abs_tol=1e-5)):
        raise RuntimeError("Le volume recalculé ne correspond pas au tronçon prévu.")


def segment_guardrail(design, selected_post, mode="halves", gap_mm=0., added_thickness_mm=5.,
                      preview=False, bolt_count=5):
    group, definition = _group_for_post(design, selected_post)
    _identity_occurrence(selected_post)
    label = _piece_name(selected_post.component)
    if selected_post.component.attributes.itemByName(operations.ATTRIBUTE_GROUP, "split_done"):
        raise ValueError("Le garde-corps est déjà tronçonné sur ce poteau.")
    planned = _layout(design, definition)
    matches = [index for index, post in enumerate(planned["posts"]) if post["name"] == label]
    if len(matches) != 1:
        raise ValueError("Sélectionner un poteau plat d’origine.")
    index = matches[0]
    post = planned["posts"][index]
    segment = post["segment"]
    row = [dict(rail, piece_name=(f"{rail['name']} · tronçon {segment+1}"
                                 if len(planned["rails"]) > 1 else rail["name"]))
           for rail in planned["rails"][segment]]
    plate = planned["plates"][index]
    split = layout.plan_post_split(post, plate, row, mode, gap_mm, added_thickness_mm)
    if mode == "adjacent":
        _check_existing_plate(group, plate)
    manager = fusion.TemporaryBRepManager.get()
    updates, additions = _rail_parts(group, row, split["rail_cuts"], manager)
    post_base, original, before, after, new_label = _post_parts(manager, selected_post, post, row, split)
    poses, bolt_length = _post_bolts(manager, before, after, post, split, bolt_count)
    if mode == "halves" or bolt_count:
        updates.append((post_base, manager.copy(original), before))
    additions.append((new_label, after, original.material))
    split["post"] = label
    split["rails"] = len(row)
    if preview:
        return split

    timeline = design.timeline
    start = timeline_groups.creation_start(timeline)
    new_group = group.component.occurrences.addNewComponent(core.Matrix3D.create())
    if not new_group:
        raise RuntimeError("Fusion n’a pas créé le sous-ensemble suivant.")
    changed = []
    try:
        new_group.component.name = f"Tronçon après {label.lower()}"
        occurrence = new_group.createForAssemblyContext(group)
        split["assembly"] = occurrence.entityToken
        for name, body, material in additions:
            operations._add_solid(new_group.component, name, body, material)
        for base, previous, replacement in updates:
            changed.append((base, previous))
            _update_body(base, replacement)
        if poses:
            with timeline_groups.defer_grouping():
                result = simple_fastener_creator.create_modeled_fasteners(
                    design, poses, _BOLT_DIAMETER_MM, bolt_length, head=_BOLT_HEAD, assembly=occurrence,
                )
            if result["created"] != len(poses):
                raise RuntimeError("La pose n’a pas créé tous les boulons des deux plats.")
        new_group.component.attributes.add(operations.ATTRIBUTE_GROUP, "post_split", json.dumps(split))
        selected_post.component.attributes.add(operations.ATTRIBUTE_GROUP, "split_done", "1")
    except Exception as error:
        rollback_errors = []
        for base, previous in reversed(changed):
            try:
                _update_body(base, previous)
            except Exception as failure:
                rollback_errors.append(str(failure))
        if not new_group.deleteMe():
            rollback_errors.append("sous-ensemble")
        if rollback_errors:
            raise RuntimeError("Rétablissement incomplet : " + " ; ".join(rollback_errors)) from error
        raise
    timeline_groups.group_creation(timeline, start, new_group.component.name)
    return split
