"""Contreventement en X entre deux faces de poteaux JHR."""

from dataclasses import dataclass, replace
from itertools import groupby
import json
from math import isfinite
from types import SimpleNamespace

import adsk.core as core
import adsk.fusion as fusion

from . import (
    angle_cleat_creator, assembly_catalog, assembly_geometry as shapes,
    assembly_operations as asm, assembly_placement, bolt_specs, brace_bay_geometry, crossing_braces,
    dxf_geometry, fastener_creator, gusset_geometry, joint_geometry as geo,
    profile_catalog, simple_fastener_creator, timeline_groups,
)


ATTRIBUTE_GROUP = "EI_JHR_BraceBay"
NAME = "JHR - Auto-contreventement"


@dataclass(frozen=True)
class Support:
    occurrence: object
    body: object
    pilot: tuple
    axis: tuple


@dataclass(frozen=True)
class Bay:
    faces: tuple
    supports: tuple
    profiles: tuple
    settings: dict
    branches: tuple
    plates: tuple
    drills: tuple
    fasteners: tuple


def _support(design, face, role):
    occurrence = face.assemblyContext
    if not occurrence or not occurrence.isValid:
        raise ValueError(f"Sélectionner une face du {role.lower()} JHR.")
    root = design.rootComponent
    if occurrence in root.occurrences:
        member = asm._member(design, occurrence, role)
        asm._i_geometry(member)
        body = member.body
        pilot, end = asm.joints._line_endpoints(member.curve)
        axis = geo.subtract(end, pilot)
    else:
        if occurrence not in root.allOccurrencesByComponent(occurrence.component):
            raise ValueError(f"Sélectionner une face du {role.lower()} dans la conception active.")
        metadata = asm.joints._member_metadata(occurrence, role)
        if metadata.source_curve_type != "line":
            raise ValueError(f"Le {role.lower()} doit être un profil JHR droit.")
        source = profile_catalog.resolve_profile_source(metadata.profile_source)
        asm._i_geometry(SimpleNamespace(family=metadata.profile_family, source=source))
        body = asm.joints._single_body(occurrence, role)
        plane = asm.joints._named_construction_plane(occurrence.component, asm.joints.MEMBER_MID_PLANE_NAME)
        plane = plane.createForAssemblyContext(occurrence) if plane else None
        if not plane or not plane.geometry:
            raise ValueError(f"Le plan de section du {role.lower()} est introuvable dans le sous-assemblage.")
        axis = tuple(plane.geometry.normal.asArray())
    face_body = face.body
    if (face_body.nativeObject or face_body) != body:
        raise ValueError(f"La face du {role.lower()} doit appartenir au solide du profil.")
    context_body = body.createForAssemblyContext(occurrence)
    if not context_body:
        raise ValueError(f"Le solide du {role.lower()} est introuvable dans son contexte d’assemblage.")
    if occurrence.assemblyContext:
        bounds = context_body.boundingBox
        pilot = geo.scale(geo.add(bounds.minPoint.asArray(), bounds.maxPoint.asArray()), .5)
    if not core.Plane.cast(face.geometry):
        raise ValueError(f"La face du {role.lower()} doit être plane.")
    success, normal = face.evaluator.getNormalAtPoint(face.pointOnFace)
    if not success:
        raise ValueError(f"La normale de la face du {role.lower()} est introuvable.")
    support = Support(occurrence, context_body, pilot, geo.normalize(axis))
    return support, tuple(face.pointOnFace.asArray()), tuple(normal.asArray())


def _up(supports):
    axes = tuple(support.axis for support in supports)
    if abs(geo.dot(*axes)) < 1.-asm.TOL:
        raise ValueError("Les axes des poteaux doivent être parallèles.")
    axis = axes[0]
    direction = max((1, 2), key=lambda index: abs(axis[index]))
    return geo.scale(axis, 1 if axis[direction] >= 0 else -1)


def _profile(path):
    source = profile_catalog.resolve_profile_source(path)
    shape = asm.cope_geometry.analyze_single_flange_profile_dxf(source)
    bounds = tuple(dxf_geometry.profile_bounds_mm(source))
    anchor = ((bounds[0]+bounds[2])/2, shape.min_y_mm)
    return source, bounds, anchor


def _diagonal(path, axis_points, frame, gap, flip):
    source, bounds, anchor = _profile(path)
    start, end = axis_points
    axis = geo.normalize(geo.subtract(end, start))
    y = geo.scale(frame.normal, -1)
    x = geo.cross(y, axis)
    if flip:
        x = geo.scale(x, -1)
    travel = geo.dot(axis, frame.across)
    offsets = sorted((edge-anchor[0])*.1*geo.dot(x, frame.across) for edge in (bounds[0], bounds[2]))
    near = geo.add(start, geo.scale(axis, (gap-offsets[0])/travel))
    far = geo.subtract(end, geo.scale(axis, (gap+offsets[1])/travel))
    if geo.dot(geo.subtract(far, near), axis) <= asm.TOL:
        raise shapes.DimensionError(("setback_mm",), "Le jeu ne laisse plus de longueur pour les cornières.")
    line = core.Line3D.create(core.Point3D.create(*near), core.Point3D.create(*far))
    return asm.Member(None, None, SimpleNamespace(worldGeometry=line), "Corniere", source, x, y, bounds, anchor)


def _face_range(face, up, origin, normal):
    heights = [geo.dot(vertex.geometry.asArray(), up) for vertex in face.vertices]
    return brace_bay_geometry.SupportFace(origin, normal, min(heights), max(heights))


def _end_plate(arm, support, boundary, frame, dims, name):
    normal = arm.normal
    face_of_angle = geo.add(arm.near, geo.scale(normal, arm.thickness_cm/2))
    inward = boundary.normal
    on_face = geo.subtract(face_of_angle, geo.scale(inward, geo.dot(geo.subtract(face_of_angle, boundary.origin), inward)))
    level = geo.dot(on_face, frame.up)
    edge = tuple(geo.add(on_face, geo.scale(frame.up, height-level)) for height in (boundary.low, boundary.high))
    bolt = bolt_specs.bolt_spec_by_designation(f"M{dims['bolt']*10:g}") if dims["bolt"] else None
    result = gusset_geometry.supported_gusset(
        (arm,), edge, thickness_cm=dims["thickness"], hole_diameter_cm=dims["hole"],
        rows=dims["rows"], end_distance_cm=dims["end_dist"], pitch_cm=dims["pitch"],
        edge_distance_cm=dims["edge"], pad_width_cm=dims["pad"], weld_length_cm=dims["weld_length"],
        washer_radius_cm=bolt.washer_outer_diameter_mm*.05 if bolt else 0.,
    )
    plate = replace(result.plate, name=name)
    welded = tuple(x for x, y in plate.outline if abs(y) < asm.TOL)
    for x in (min(welded)+.01, sum(welded)/2, max(welded)-.01):
        for fraction in (.02, .98):
            point = geo.add(plate.point(x, 0), geo.scale(plate.normal, dims["thickness"]*fraction))
            point = core.Point3D.create(*geo.subtract(point, geo.scale(inward, .01)))
            if support.body.pointContainment(point) != fusion.PointContainment.PointInsidePointContainment:
                raise ValueError("Le chant du gousset sort de la face choisie. Ajuster le déport ou choisir une face plus large.")
    return replace(result, plate=plate), bolt


def _evaluate(design, faces, profile_keys, settings):
    if len(faces) != 2 or len(profile_keys) != 2:
        raise ValueError("Sélectionner deux faces et deux sections de cornières.")
    descriptions = tuple(_support(design, face, f"Poteau {index}") for index, face in enumerate(faces, 1))
    supports = tuple(item[0] for item in descriptions)
    if supports[0].occurrence == supports[1].occurrence:
        raise ValueError("Sélectionner deux poteaux distincts.")
    up = _up(supports)
    boundaries = tuple(_face_range(face, up, origin, normal)
                       for face, (_, origin, normal) in zip(faces, descriptions))
    centre_axis = supports[0].pilot
    values = dict(bottom_mm=150., top_mm=150., setback_mm=20., offset_mm=0.,
                  flip_first=False, flip_second=False, central={}, ends={}, scalloped=False,
                  scallop_depth_mm=5.)
    values.update(settings)
    for key in ("bottom_mm", "top_mm", "setback_mm", "offset_mm"):
        value = values[key]
        if not isfinite(value) or (value < 0. and key != "offset_mm"):
            raise shapes.DimensionError((key,), "Renseigner une valeur valide pour cette cote.")
    try:
        frame = brace_bay_geometry.plan(
            *boundaries, up, centre_axis, bottom_cm=values["bottom_mm"]*.1, top_cm=values["top_mm"]*.1,
            offset_cm=values["offset_mm"]*.1,
        )
    except ValueError as error:
        if "retraits du bas" in str(error):
            raise shapes.DimensionError(("bottom_mm", "top_mm"), str(error)) from error
        raise
    diagonals = tuple(_diagonal(path, points, frame, values["setback_mm"]*.1, values[key])
                      for path, points, key in zip(profile_keys, frame.diagonals, ("flip_first", "flip_second")))
    central_dims = shapes.dimensions(assembly_catalog.template_for("gusset_cross"), values["central"])
    end_dims = shapes.dimensions(assembly_catalog.template_for("gusset_end_1"), values["ends"])
    depth = values["scallop_depth_mm"]*.1 if values["scalloped"] else 0.
    if values["scalloped"] and (not isfinite(depth) or depth <= asm.TOL):
        raise shapes.DimensionError(("scallop_depth_mm",), "Choisir une profondeur strictement positive.")
    try:
        cuts = crossing_braces.plan(diagonals, central_dims["cross_gap"])
        branches = tuple((diagonal, near, far) for diagonal, cut in zip(diagonals, cuts)
                         for near, far in cut.branches)
        arms = tuple(asm._brace_arm(diagonal, near, far) for diagonal, near, far in branches)
        central, bolt = asm._central_shape(arms, central_dims, False, bearing_vertical=frame.up,
                                           scallop_depth_cm=depth)
        profiles = tuple(item[0] for item in branches)
        plates, drills, batches = asm._brace_hardware(profiles, arms, central, central_dims, bolt, check_material=False)
    except shapes.DimensionError:
        raise
    except ValueError as error:
        raise ValueError(f"Platine centrale · {error}") from error
    drilling = [[drill] for drill in drills]
    for i, (diagonal, near, far) in enumerate(branches):
        index = i % 2
        arm = asm._brace_arm(diagonal, far, near)
        try:
            end, bolt = _end_plate(arm, supports[index], boundaries[index], frame, end_dims,
                                   f"Gousset d’extrémité {i+1}")
            new_plates, new_drills, new_batches = asm._brace_hardware(
                (diagonal,), (arm,), end, end_dims, bolt, check_material=False,
            )
        except ValueError as error:
            raise ValueError(f"Gousset {i+1} · {error}") from error
        plates += new_plates
        batches += new_batches
        drilling[i].extend(new_drills)
    return Bay(tuple(faces), supports, tuple(profile_keys), values, branches, plates,
               tuple(tuple(items) for items in drilling), batches)


def evaluate(design, faces, profile_keys, settings):
    if not design or design.designType != fusion.DesignTypes.ParametricDesignType:
        raise ValueError("Ouvrir une conception Fusion avec l’historique de conception.")
    return _evaluate(design, tuple(faces), tuple(profile_keys), settings)


def preview_segments(plan):
    return tuple((near, far) for _, near, far in plan.branches)


def branch_section(branch, index):
    member, start, end = branch
    axis = geo.normalize(geo.subtract(end, start))
    x, y = member.section_x, member.section_y
    handed = geo.dot(geo.cross(x, y), axis)
    ax, ay = member.anchor
    contour, radii = dxf_geometry.profile_outline_mm(member.source)

    def section_point(point):
        return (point[0]-ax)*.1*handed, (point[1]-ay)*.1

    outline = tuple(section_point(point) for point in contour)
    arcs = tuple((i, section_point(point)) for i, point in radii)
    return shapes.Plate(f"BARRE · {member.source.stem} · {index}", start, geo.scale(x, handed), y,
                        outline, geo.length(geo.subtract(end, start)), arcs=arcs)


def _create_branch(group, material, branch, holes, index):
    plate = branch_section(branch, index)
    child = asm._create_plate(group.component, plate, material)
    child.component.sketches.item(0).name = "Section de la cornière"
    child.component.features.extrudeFeatures.item(0).name = "Longueur de la cornière"
    proxy = child.createForAssemblyContext(group)
    body = child.component.bRepBodies.item(0)
    for drill in holes:
        proxy_body = asm.joints._body_proxy(body, proxy)
        samples = [geo.subtract(p, geo.scale(drill.axis, (drill.span-.2)/4)) for p in drill.centres]
        if any(proxy_body.pointContainment(core.Point3D.create(*sample)) !=
               fusion.PointContainment.PointInsidePointContainment for sample in samples):
            raise ValueError(f"Un perçage sort de l’aile de la cornière {index}.")
        angle_cleat_creator._create_member_cut_group(child.component, proxy, body, drill.centres, drill.axis,
                                                   drill.diameter, drill.span, "Perçages JHR", "Centres JHR")
    return proxy


def _read_definition(group):
    marker = group.component.attributes.itemByName(ATTRIBUTE_GROUP, "definition")
    return json.loads(marker.value) if marker else None


def find_group(entity):
    group = fusion.Occurrence.cast(entity) or getattr(entity, "assemblyContext", None)
    while group and not _read_definition(group):
        group = group.assemblyContext
    return group


def _unique_occurrence(design, component):
    occurrences = design.rootComponent.allOccurrencesByComponent(component)
    return occurrences.item(0) if occurrences.count == 1 else None


def read(design, entity):
    group = find_group(entity)
    if not group:
        raise ValueError("Sélectionner une pièce d’un auto-contreventement.")
    group = _unique_occurrence(design, group.component) or group
    definition = _read_definition(group)
    faces = []
    for token in definition["faces"]:
        candidates = [face for item in design.findEntityByToken(token) or ()
                      if (face := fusion.BRepFace.cast(item)) and face.isValid and face.assemblyContext]
        if len(candidates) != 1:
            raise ValueError("Une face porteuse a disparu. Resélectionner les deux faces du contreventement.")
        faces.append(candidates[0])
    return group, tuple(faces), definition


def _signature(plan):
    vectors = [coordinates for _, near, far in plan.branches for coordinates in (near, far)]
    for plate in plan.plates:
        vectors.extend((plate.origin, plate.u, plate.v, *plate.outline, *plate.holes,
                        *((index, *middle) for index, middle in plate.arcs)))
    return [[round(value, 6) for value in vector] for vector in vectors]


def _face_state(faces):
    return [sorted([round(value, 6) for value in vertex.geometry.asArray()]
                   for vertex in face.vertices) for face in faces]


def pending_update(design):
    """Retourne le dernier X si ses faces ont réellement changé."""
    timeline = design.timeline
    if not timeline.count or timeline.markerPosition != timeline.count or design.snapshots.hasPendingSnapshot:
        return None
    last_item = timeline.item(timeline.count-1)
    if not last_item.isGroup:
        return None
    for marker in design.findAttributes(ATTRIBUTE_GROUP, "definition"):
        group = _unique_occurrence(design, marker.parent)
        item = (group.nativeObject or group).timelineObject if group else None
        if not item or item.parentGroup != last_item:
            continue
        _, faces, record = read(design, group)
        if _face_state(faces) != record.get("face_state"):
            return group, faces, record
    return None


def editable_history(design, group):
    _, history = target_group(design, group)
    if not history.isCollapsed or history.index != design.timeline.count-1:
        raise ValueError("Le recalcul de cet X requiert son groupe replié en fin d’historique.")
    return history


def target_group(design, entity):
    """Vérifie que l'historique contient uniquement la géométrie de ce X."""
    group = find_group(entity)
    if not group:
        raise ValueError("Sélectionner une pièce d’un auto-contreventement.")
    group = _unique_occurrence(design, group.component)
    if not group:
        raise ValueError("Le X doit être une occurrence unique dans la conception.")
    item = (group.nativeObject or group).timelineObject
    history = item.parentGroup if item else None
    if not history or not history.isValid or history.name != group.component.name:
        raise ValueError("Le groupe d’historique de ce X est introuvable ou a été renommé.")
    components = [group.component, *(item.component for item in group.component.allOccurrences)]
    for index in range(history.count):
        item = history.item(index).entity
        occurrence = fusion.Occurrence.cast(item) if item else None
        owner = occurrence.component if occurrence else getattr(item, "parentComponent", None)
        if owner and owner not in components:
            raise ValueError(f"Le groupe du X contient une opération dans le composant {owner.name}.")
    return group, history


def _remove_history(design, group, history):
    timeline = design.timeline
    component = group.component
    if timeline.markerPosition != timeline.count:
        raise ValueError("Placer le marqueur en fin d’historique avant la suppression.")
    parent = group.assemblyContext
    siblings = parent.childOccurrences if parent else design.rootComponent.occurrences
    other_occurrences = [item for item in siblings if item != group]
    if parent:
        other_occurrences.append(parent)
    was_collapsed = history.isCollapsed
    if not was_collapsed:
        history.isCollapsed = True
    try:
        if history.index < 0:
            raise RuntimeError("Fusion n’a pas identifié la position du groupe du X.")
        later = [timeline.item(index) for index in range(history.index + 1, timeline.count)]
        if not history.deleteMe(True) or any(
            item.component == component for item in design.rootComponent.allOccurrences if item.isValid
        ):
            raise RuntimeError("Fusion refuse de retirer le groupe du X.")
        if any(not item.isValid for item in (*other_occurrences, *later)):
            raise RuntimeError("La suppression du X toucherait une autre opération de la conception.")
    finally:
        if not was_collapsed and history.isValid:
            history.isCollapsed = False


def remove(design, entity):
    """Retire un X et ses pièces dans la transaction courante."""
    group, history = target_group(design, entity)
    _remove_history(design, group, history)


def _edit_central_scallops(design, group, record, plan, state, signature):
    """Retouche la tôle en place si seules les cotes des évidements changent."""
    option_keys = {"scalloped", "scallop_depth_mm"}
    before = {key: value for key, value in record["settings"].items() if key not in option_keys}
    after = {key: value for key, value in plan.settings.items() if key not in option_keys}
    if before != after or tuple(record["profiles"]) != plan.profiles or record.get("face_state") != state:
        return False

    from . import assembly_edit

    original = evaluate(design, plan.faces, plan.profiles, record["settings"])
    old, new = original.plates[0], plan.plates[0]
    if replace(new, arcs=old.arcs) != old or record.get("signature") != _signature(original):
        return False
    plates = [child for child in group.childOccurrences
              if child.component.bRepBodies.count == 1 and child.component.bRepBodies.item(0).name == old.name]
    if len(plates) != 1 or not assembly_edit._matches_matrix(plates[0], assembly_edit._matrix(old)):
        raise ValueError("La platine centrale a été retouchée et ne correspond plus au montage.")
    target = plates[0]
    marker = group.component.attributes.itemByName(ATTRIBUTE_GROUP, "definition")
    journal = assembly_edit.Journal(design, marker, marker.value)
    try:
        assembly_edit._modify_part(design, target, old, new, journal)
        _check_clearance(design, plan, group)
        record.update(settings=plan.settings, signature=signature, face_state=state)
        marker.value = json.dumps(record)
    except Exception:
        journal.rollback()
        raise
    return True


def prepare_edit(design, group, plan, *, allow_earlier=False):
    """Vérifie les faces et l'historique avant la modification d'un X."""
    group, faces, record = read(design, group)
    if faces != plan.faces:
        raise ValueError("Les faces porteuses du X ont changé. Rouvrir l’assemblage.")
    state, signature = _face_state(plan.faces), _signature(plan)
    if record["settings"] == plan.settings and tuple(record["profiles"]) == plan.profiles and record.get("signature") == signature:
        return group, record, state, signature, None
    if design.timeline.markerPosition != design.timeline.count:
        raise ValueError("Placer le marqueur en fin d’historique avant la modification.")
    history = target_group(design, group)[1] if allow_earlier else editable_history(design, group)
    return group, record, state, signature, history


def reconfigure(design, group, plan, *, allow_earlier=False):
    group, record, state, signature, history = prepare_edit(design, group, plan, allow_earlier=allow_earlier)
    if history is None:
        if record.get("face_state") != state:
            record["face_state"] = state
            group.component.attributes.itemByName(ATTRIBUTE_GROUP, "definition").value = json.dumps(record)
        return group
    if _edit_central_scallops(design, group, record, plan, state, signature):
        return group
    new_group = create(design, plan, replacing=group)
    try:
        _remove_history(design, group, history)
    except Exception:
        remove(design, new_group)
        raise
    return new_group


def check_free_faces(design, faces, *, replacing=None):
    """Détecte un X déjà posé entre les deux mêmes faces, dans les deux ordres."""
    for marker in design.findAttributes(ATTRIBUTE_GROUP, "definition"):
        if replacing and marker.parent == replacing.component:
            continue
        record = json.loads(marker.value)
        if all(
            any(face == item for token in record["faces"] for item in design.findEntityByToken(token) or ())
            for face in faces
        ):
            raise ValueError("Un auto-contreventement existe déjà entre ces deux faces.")


def _check_clearance(design, plan, group):
    hardware = fastener_creator.assembly_hardware(group)
    parts = [child for child in group.childOccurrences if child not in hardware]
    parts.extend(asm._associated_bolts(group))
    parts.extend(support.body for support in plan.supports)
    fastener_creator.verify_clearance(design, parts)


def create(design, plan, *, replacing=None):
    """Construit les pièces dans un groupe unique. Les deux poteaux restent intacts."""
    root = design.rootComponent
    parent = (replacing.assemblyContext if replacing else
              assembly_placement.parent_for(design, tuple(support.occurrence for support in plan.supports)))
    face_tokens = [face.entityToken for face in plan.faces]
    check_free_faces(design, plan.faces, replacing=replacing)
    timeline = design.timeline
    start = timeline_groups.creation_start(timeline)
    group = root.occurrences.addNewComponent(core.Matrix3D.create())
    if not group:
        raise RuntimeError("Fusion refuse le groupe de contreventement.")
    component = group.component
    component.name = NAME
    material = plan.supports[0].body.material
    created = []
    try:
        for index, (branch, holes) in enumerate(zip(plan.branches, plan.drills), 1):
            _create_branch(group, material, branch, holes, index)
        for plate in plan.plates:
            asm._create_plate(component, plate, material)
        batches = sorted(plan.fasteners, key=lambda job: job[1:])
        for (diameter, length), jobs in groupby(batches, key=lambda job: job[1:]):
            placements = [placement for job, _, _ in jobs for placement in job]
            result = simple_fastener_creator.create_modeled_fasteners(
                design, placements, diameter, length, created_entities=created, assembly=group,
                ignored_assembly=replacing,
            )
            if result["occupied"] or result["created"] != len(placements):
                raise ValueError("Une position de boulon est déjà occupée.")
        if parent:
            group = assembly_placement.move_group(design, group, parent)
        _check_clearance(design, plan, group)
        if not asm._associated_bolts_match(group, plan.fasteners):
            raise RuntimeError("Les boulons ne correspondent pas aux axes de perçage.")
        payload = dict(faces=face_tokens, profiles=plan.profiles, settings=plan.settings, signature=_signature(plan),
                       face_state=_face_state(plan.faces))
        component.attributes.add(ATTRIBUTE_GROUP, "definition", json.dumps(payload))
        timeline_groups.group_creation(timeline, start, component.name)
    except Exception:
        if not group.isValid and component.isValid:
            group = _unique_occurrence(design, component)
        angle_cleat_creator._delete_valid([group, *created])
        raise
    return group
