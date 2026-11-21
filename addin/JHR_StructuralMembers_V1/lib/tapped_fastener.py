"""Vis dans un trou taraudé, avec ou sans fraisure."""
import adsk.core as core
import adsk.fusion as fusion

from . import bolt_geometry, bolt_specs, countersink_preparation, fastener_creator, fastener_geometry as geometry
from . import joint_geometry as geo, simple_fastener_creator, timeline_groups

_TABLE = "ISO Metric profile"
_COARSE_PITCH = {12: 1.75, 16: 2., 20: 2.5, 24: 3.}


def thread_infos(diameter_mm):
    pitch = _COARSE_PITCH.get(diameter_mm)
    if pitch is None:
        raise ValueError("La vis pour taraudage accepte M12, M16, M20 et M24.")
    designations = fusion.ThreadDataQuery.create().allDesignations(_TABLE, f"{diameter_mm:.1f}")
    expected = f"M{diameter_mm:g}x{pitch:g}"
    designation = next((name for name in designations if name.replace(" ", "") == expected), None)
    if designation is None:
        raise ValueError("Le pas ISO métrique demandé est absent de la bibliothèque Fusion.")
    return tuple(fusion.ThreadInfo.create(False, internal, _TABLE, designation, tolerance, True)
                 for internal, tolerance in ((True, "6H"), (False, "6g")))


def add_thread(face, thread_info, depth_cm=None, at_high_end=False, modeled=False):
    native = face.nativeObject or face
    features = native.body.parentComponent.features.threadFeatures
    entry = features.createInput(native, thread_info)
    if not entry:
        raise RuntimeError("Fusion a refusé la définition du filetage.")
    entry.isModeled = modeled
    if depth_cm is not None:
        entry.isFullLength = False
        entry.threadLength = core.ValueInput.createByReal(depth_cm)
        entry.threadLocation = (fusion.ThreadLocations.HighEndThreadLocation if at_high_end else
                                fusion.ThreadLocations.LowEndThreadLocation)
    feature = features.add(entry)
    if not feature or feature.healthState != fusion.FeatureHealthStates.HealthyFeatureHealthState:
        message = feature.errorOrWarningMessage if feature else "fonction non créée"
        if feature:
            feature.deleteMe()
        raise RuntimeError(f"Filetage {thread_info.threadDesignation} : {message}")
    return feature


def seat(face, head_face, diameter_mm, engagement_mm, internal, *, head_washer=True, length_mm=None,
         countersink=None, pending_depth_cm=0.):
    hole = fastener_creator.read_hole(face)
    if not isinstance(hole, geometry.Hole):
        raise ValueError("Le taraudage doit partir d’un trou rond.")
    centres = [fastener_creator.point(circle.center) for edge in face.edges
               if (circle := core.Circle3D.cast(edge.geometry))]
    if len(centres) != 2:
        raise ValueError("Sélectionner la paroi cylindrique d’un avant-trou rond complet.")
    bore_mm = hole.diameter_cm * 10
    if not internal.minorDiameter*10-.45 <= bore_mm <= internal.minorDiameter*10+.45:
        raise ValueError(f"L’avant-trou Ø{bore_mm:g} mm ne correspond pas au taraudage demandé.")
    support = fastener_creator.read_support(head_face)
    dot = geo.dot(hole.axis, support.normal)
    if abs(dot) < .999:
        raise ValueError("L’appui sous la vis doit être perpendiculaire au taraudage.")
    offset = geo.dot(geo.subtract(support.point, hole.center), support.normal) / dot
    origin = geo.add(hole.center, geo.scale(hole.axis, offset))
    first, last = sorted(centres, key=lambda pt: geo.length(geo.subtract(pt, origin)))
    axis = geo.normalize(geo.subtract(last, first))
    grip_cm = geo.dot(geo.subtract(first, origin), axis)
    if grip_cm < -1e-4:
        raise ValueError("Sélectionner une face d’appui située devant l’avant-trou.")
    grip_cm = max(0., grip_cm)
    bore_length_cm = geo.length(geo.subtract(last, first))
    if countersink:
        if (geo.length(geo.subtract(origin, countersink.center)) > geometry.POSITION_TOLERANCE_CM
                or geo.dot(axis, countersink.axis) < 1. - geometry.PARALLEL_TOLERANCE):
            raise ValueError("Choisir le plan d’appui à l’ouverture de la fraisure.")
        grip_cm += pending_depth_cm
        bore_length_cm -= pending_depth_cm
    washer_mm = bolt_specs.bolt_spec_by_designation(f"M{diameter_mm:g}").washer_thickness_mm if head_washer else 0.
    if length_mm is None:
        engagement = geometry._positive(engagement_mm, "L’engagement") * .1
        length = (grip_cm + engagement)*10 + washer_mm
        message = "L’engagement demandé ne tient pas dans la longueur du trou."
    else:
        length = geometry._positive(length_mm, "La longueur de vis")
        engagement = (length - washer_mm)*.1 - grip_cm
        minimum = (grip_cm + internal.threadPitch)*10 + washer_mm
        maximum = (grip_cm + bore_length_cm)*10 + washer_mm
        kind = "totale" if countersink else "sous tête"
        message = f"Choisir une longueur {kind} entre {minimum:g} et {maximum:g} mm pour ce taraudage."
    if engagement < internal.threadPitch - 1e-5 or engagement > bore_length_cm + 1e-5:
        raise ValueError(message)
    tip = grip_cm + engagement
    position = geometry.Placement(origin, *bolt_geometry.perpendicular_axes(axis), tip, countersink)
    return position, length, engagement*10


def _bore_at_throat(cone, countersink):
    throat = geo.add(countersink.center, geo.scale(countersink.axis, countersink.depth_cm))
    for edge in cone.edges:
        circle = core.Circle3D.cast(edge.geometry)
        if not circle or geo.length(geo.subtract(fastener_creator.point(circle.center), throat)) > geometry.POSITION_TOLERANCE_CM:
            continue
        walls = [face for face in edge.faces if core.Cylinder.cast(face.geometry)]
        if len(walls) == 1:
            return walls[0]
    raise ValueError("La paroi cylindrique au fond de la fraisure est introuvable.")


def _opening_binding(design, face, placement, head):
    from . import fastener_hole_link

    opening = fastener_hole_link.source_for_pose((face,), placement, head)
    token = opening.entityToken

    def bind(pose, occurrence):
        edge = opening
        if not edge.isValid:
            candidates = [resolved for item in design.findEntityByToken(token) or ()
                          if (resolved := fusion.BRepEdge.cast(item)) and resolved.isValid]
            if len(candidates) != 1:
                raise RuntimeError("L’ouverture de la fixation est introuvable après le taraudage.")
            edge = candidates[0]
        return fastener_hole_link.bind(design, occurrence, pose, edge)

    return bind


def place(design, face, head_face, diameter_mm, engagement_mm, modeled=False, preview=False, *,
          head_washer=None, length_mm=None, bind_to_hole=None, head="H", prepare_countersink=False,
          link_to_hole=False):
    if head not in ("H", "TF"):
        raise ValueError("Le taraudage accepte une vis à tête H ou fraisée.")
    if prepare_countersink and head != "TF":
        raise ValueError("La préparation d’une fraisure exige une tête fraisée.")
    if link_to_hole and bind_to_hole:
        raise ValueError("Choisir une seule méthode de liaison au perçage.")
    head_washer, _ = geometry.modeled_washer_options(head, tapped=True, head_washer=head_washer)
    internal, external = thread_infos(diameter_mm)
    preparation = countersink = cone = None
    bore = face
    if head == "TF":
        if core.Cone.cast(face.geometry):
            cone = face
            countersink = fastener_creator.read_countersink(cone)
            bore = _bore_at_throat(cone, countersink)
        elif prepare_countersink:
            preparation = countersink_preparation.plan(face, head_face, diameter_mm)
            countersink = preparation.hole
        else:
            raise ValueError("Sélectionner la paroi conique de la fraisure ou activer sa préparation.")
    placement, length, engagement = seat(
        bore, head_face, diameter_mm, engagement_mm, internal, head_washer=head_washer, length_mm=length_mm,
        countersink=countersink, pending_depth_cm=countersink.depth_cm if preparation else 0.,
    )
    result = {"designation": internal.threadDesignation, "length_mm": length,
              "engagement_mm": engagement, "modeled": bool(modeled)}
    if countersink:
        result.update(countersink_depth_mm=countersink.depth_cm*10,
                      countersink_opening_mm=countersink.opening_diameter_cm*10,
                      prepares_countersink=bool(preparation))
    if preview:
        return result
    if any(geometry.same_position(placement, prior)
           for prior in fastener_creator.existing_positions(design.rootComponent)):
        return dict(result, created=0, occupied=1, parts=0)
    timeline = design.timeline if design.designType == fusion.DesignTypes.ParametricDesignType else None
    start = timeline_groups.creation_start(timeline)
    features = []
    try:
        if preparation:
            cone, milling = countersink_preparation.apply(design, preparation)
            features.extend(milling)
            bore = countersink_preparation.bore_face(preparation, cone)
        binding = _opening_binding(design, cone or face, placement, head) if link_to_hole else bind_to_hole
        tap = add_thread(bore, internal, modeled=modeled)
        features.append(tap)
        created = simple_fastener_creator.create_modeled_fasteners(
            design, [placement], diameter_mm, length, projection_mm=0.,
            external_thread=external, thread_depth_cm=engagement*.1, modeled_thread=modeled,
            head=head, head_washer=head_washer, bind_to_hole=binding,
        )
    except Exception:
        for feature in reversed(features):
            if feature.isValid:
                feature.deleteMe()
        raise
    timeline_groups.group_creation(timeline, start, f"JHR - Taraudage {internal.threadDesignation}")
    return dict(result, **created, tap_feature=tap.name)
