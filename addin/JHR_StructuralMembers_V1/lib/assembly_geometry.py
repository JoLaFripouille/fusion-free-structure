"""Calcul des tôles et des perçages, sans dépendance à Fusion."""
from dataclasses import dataclass, replace
from math import atan2, cos, hypot, isfinite, sin, sqrt, tau

from . import bolt_specs, joint_geometry as geo


@dataclass(frozen=True)
class Plate:
    name: str
    origin: tuple
    u: tuple
    v: tuple
    outline: tuple
    thickness_cm: float
    holes: tuple = ()
    arcs: tuple = ()
    finishable: bool = False
    inherit_material: bool = True

    @property
    def normal(self):
        return geo.cross(self.u, self.v)

    def point(self, x, y):
        return geo.add(self.origin, geo.add(geo.scale(self.u, x), geo.scale(self.v, y)))

    def display_outline(self):
        """Échantillonne les arcs pour le seul aperçu."""
        curves = dict(self.arcs)
        result = []
        for index, (start, end) in enumerate(zip(self.outline, self.outline[1:]+self.outline[:1])):
            result.append(start)
            if index not in curves:
                continue
            bx, by = geo.subtract(curves[index], start)
            cx, cy = geo.subtract(end, start)
            d = 2*(bx*cy-by*cx)
            if abs(d) <= geo.GEOMETRY_TOLERANCE_CM:
                continue
            b2, c2 = bx*bx+by*by, cx*cx+cy*cy
            x, y = (b2*cy-c2*by)/d, (bx*c2-cx*b2)/d
            initial = atan2(-y, -x)
            span = (atan2(cy-y, cx-x)-initial) % tau
            if (atan2(by-y, bx-x)-initial) % tau > span:
                span -= tau
            radius = hypot(x, y)
            result.extend((start[0]+x+radius*cos(initial+span*step/8),
                           start[1]+y+radius*sin(initial+span*step/8)) for step in range(1, 8))
        return tuple(result)


class DimensionError(ValueError):
    """Une ou plusieurs cotes à signaler dans le formulaire."""

    def __init__(self, keys, message):
        super().__init__(message)
        self.keys = tuple(keys)


def dimensions(template, supplied):
    fields = {field.key: field for _, group in template.groups for field in group}
    unknown = set(supplied) - fields.keys()
    if unknown:
        raise ValueError("Cote inconnue : " + ", ".join(sorted(unknown)))
    result = {key: float(supplied.get(key, field.default)) * (.1 if field.unit == "mm" else 1)
              for key, field in fields.items()}
    for key, value in result.items():
        field = fields[key]
        if not isfinite(value) or (value < 0 and not field.signed):
            raise DimensionError((key,), "La cote n’est pas finie ou son signe est incompatible.")
        if not field.unit and (value != int(value) or not field.min_count <= value <= field.max_count):
            raise DimensionError((key,), "La valeur est hors des limites du modèle.")
    return result


def rectangle(name, origin, u, v, width, height, thickness, holes=(), offset_x=0, finishable=True):
    if min(width, height, thickness) <= 0:
        keys = tuple(key for key, value in (("width", width), ("height", height), ("thickness", thickness)) if value <= 0)
        raise DimensionError(keys, "Les dimensions de la tôle doivent être strictement positives.")
    for i, (x, y, diameter) in enumerate(holes):
        if diameter <= 0 or min(width / 2 - abs(x - offset_x), height / 2 - abs(y)) <= diameter / 2:
            raise DimensionError(("hole", "gauge", "pitch"), "Un perçage déborde de la tôle ou touche son chant.")
        for other_x, other_y, other_diameter in holes[:i]:
            if ((x-other_x)**2 + (y-other_y)**2)**.5 <= (diameter+other_diameter)/2:
                raise DimensionError(("hole", "gauge", "pitch"), "Deux perçages se touchent ou se recouvrent.")
    return Plate(name, origin, u, v, (
        (offset_x-width/2, -height/2), (offset_x+width/2, -height/2),
        (offset_x+width/2, height/2), (offset_x-width/2, height/2),
    ), thickness, tuple(holes), finishable=finishable)


def grid(gauge, pitch, hole):
    if not hole:
        return ()
    if min(gauge, pitch) <= hole:
        raise ValueError("Entraxes insuffisants pour quatre perçages distincts.")
    return tuple((x, y, hole) for x in (-gauge/2, gauge/2) for y in (-pitch/2, pitch/2))


def base_plate_dimensions(dims, section_width, section_height, *, reverse_y=False):
    """Résout les quatre débords du pied dans le repère local de la platine."""
    if dims.get("plate_position", 0) == 0:
        return dims
    minus_x, plus_x = dims["plate_x_minus"], dims["plate_x_plus"]
    minus_y, plus_y = dims["plate_y_minus"], dims["plate_y_plus"]
    offset_y = (minus_y-plus_y)/2 if reverse_y else (plus_y-minus_y)/2
    return dict(dims, width=section_width+minus_x+plus_x, height=section_height+minus_y+plus_y,
                offset_x=(plus_x-minus_x)/2, offset_y=offset_y)


def base_holes(dims):
    """Perçages symétriques selon les entraxes ou les retraits aux chants."""
    hole = dims["hole"]
    if not hole:
        return ()
    mode = dims.get("hole_position", 0)
    gauge, pitch = dims["gauge"], dims["pitch"]
    if mode in (1, 2):
        gauge = _edge_spacing(dims["width"], dims["hole_edge_x"], hole, "X", "hole_edge_x")
    if mode in (1, 3):
        pitch = _edge_spacing(dims["height"], dims["hole_edge_y"], hole, "Y", "hole_edge_y")
    if gauge <= hole or pitch <= hole:
        active = tuple(key for key, size in (("gauge", gauge), ("pitch", pitch)) if size <= hole)
        raise DimensionError(active, "Entraxes insuffisants pour quatre perçages distincts.")
    return grid(gauge, pitch, hole)


def _edge_spacing(span, edge, hole, axis, key):
    if edge <= hole/2:
        raise DimensionError((key,), f"La distance de l’axe du trou au bord en {axis} doit dépasser le rayon du trou.")
    spacing = span - 2*edge
    if spacing <= hole:
        raise DimensionError((key,), f"Distance au bord en {axis} trop grande pour des perçages distincts. "
                             "Réduire le retrait ou agrandir la platine sur cet axe.")
    return spacing


def _anchor_spec(diameter):
    nominal = round(diameter * 10, 6)
    if nominal in (4, 5, 6, 8, 10):
        return bolt_specs.modeled_spec(nominal, "CHC")[0]
    designation = f"M{nominal:g}"
    spec = next((item for item in bolt_specs.BOLT_SPECS if item.designation == designation), None)
    if spec:
        return spec
    reference = bolt_specs.default_bolt_spec()
    ratio = nominal / reference.nominal_diameter_mm
    # Les tiges de diamètre libre existaient déjà. Hors catalogue, garder une
    # représentation indicative des accessoires plutôt que bloquer leur pose.
    return replace(
        reference, designation=designation, nominal_diameter_mm=nominal,
        nut_across_flats_mm=reference.nut_across_flats_mm * ratio,
        nut_height_mm=reference.nut_height_mm * ratio,
        washer_inner_diameter_mm=reference.washer_inner_diameter_mm * ratio,
        washer_outer_diameter_mm=reference.washer_outer_diameter_mm * ratio,
        washer_thickness_mm=reference.washer_thickness_mm * ratio,
    )


def base_anchor_washer_diameter(diameter):
    return _anchor_spec(diameter).washer_outer_diameter_mm * .1


def _round_outline(radius):
    middle = radius / sqrt(2)
    return ((radius, 0.), (0., radius), (-radius, 0.), (0., -radius)), tuple(enumerate((
        (middle, middle), (-middle, middle), (-middle, -middle), (middle, -middle),
    )))


def _anchor_parts(plate, dims, diameter, projection, length, include_hardware):
    rod_outline, rod_arcs = _round_outline(diameter / 2)
    if include_hardware:
        spec = _anchor_spec(diameter)
        washer_thickness, nut_thickness = spec.washer_thickness_mm * .1, spec.nut_height_mm * .1
        stack = washer_thickness + nut_thickness
        required_projection = stack + spec.thread_projection_mm * .1
        if projection + geo.GEOMETRY_TOLERANCE_CM < required_projection:
            raise ValueError(f"Prévoir un dépassement d’au moins {required_projection*10:g} mm côté poteau "
                             "pour la rondelle, l’écrou et la tige au-dessus.")
        washer_diameter = spec.washer_outer_diameter_mm * .1
        if any(hole_diameter >= washer_diameter for _, _, hole_diameter in plate.holes):
            raise ValueError(f"La rondelle {spec.designation} ne couvre pas le trou de pied.")
        washer_outline, washer_arcs = _round_outline(washer_diameter / 2)
        washer_holes = ((0., 0., spec.washer_inner_diameter_mm * .1),)
        radius = spec.nut_across_flats_mm * .1 / sqrt(3)
        nut_outline = tuple((radius * cos(i * tau / 6), radius * sin(i * tau / 6)) for i in range(6))
        nut_holes = ((0., 0., diameter * 1.02),)
        try:
            footprints = tuple((x, y, washer_diameter) for x, y, _ in plate.holes)
            seating = rectangle(plate.name, plate.origin, plate.u, plate.v,
                                dims["width"], dims["height"], plate.thickness_cm, footprints)
            finish_rectangle(seating, dims.get("chamfer", 0.), dims.get("corner_radius", 0.))
        except ValueError as error:
            raise ValueError(f"L’appui des rondelles est insuffisant sur la platine. {error}") from error

    for x, y, _ in plate.holes:
        point = plate.point(x, y)

        def at(depth):
            return geo.add(point, geo.scale(plate.normal, -depth))

        yield Plate(f"Tige d’ancrage droite Ø{diameter*10:g}", at(projection), plate.u, plate.v,
                    rod_outline, length, arcs=rod_arcs, inherit_material=False)
        if include_hardware:
            yield Plate(f"Rondelle d’ancrage {spec.designation}", at(washer_thickness), plate.u, plate.v,
                        washer_outline, washer_thickness, washer_holes, washer_arcs, inherit_material=False)
            yield Plate(f"Écrou d’ancrage {spec.designation}", at(stack), plate.u, plate.v,
                        nut_outline, nut_thickness, nut_holes, inherit_material=False)


def base_fixings(plate, dims, *, include_hardware=True):
    """Pièces facultatives alignées sur les axes des trous de la platine de pied."""
    result = []
    depth = plate.thickness_cm + dims["shim"]
    hole_diameter = dims.get("preset_hole", 0.)
    preset_thickness = dims.get("preset_thickness", 0.)
    if preset_thickness:
        left, right, front, back = (dims[key] for key in (
            "preset_left", "preset_right", "preset_front", "preset_back",
        ))
        x, y = (right-left)/2, (back-front)/2
        depth += dims["preset_gap"]
        origin = geo.add(plate.point(x, y), geo.scale(plate.normal, depth))
        if hole_diameter and not plate.holes:
            raise ValueError("Les perçages de préscellement exigent les axes des trous du pied.")
        holes = tuple((h-x, v-y, hole_diameter or diameter) for h, v, diameter in plate.holes)
        preset = rectangle(
            "Platine de préscellement", origin, plate.u, plate.v,
            dims["width"] + left + right, dims["height"] + front + back, preset_thickness, holes,
        )
        result.append(preset)
        depth += preset_thickness
    diameter = dims.get("anchor_diameter", 0.)
    if diameter:
        if not plate.holes or any(diameter >= d for _, _, d in plate.holes):
            raise ValueError("Les tiges d’ancrage exigent des trous de pied plus larges que leur diamètre.")
        if preset_thickness and hole_diameter and diameter >= hole_diameter:
            raise ValueError("Les trous de préscellement doivent être plus larges que les tiges d’ancrage.")
        length = dims["anchor_length"]
        projection = dims["anchor_projection"]
        if length <= projection + depth:
            raise ValueError("La tige doit dépasser sous l’empilement après déduction de la projection.")
        result.extend(_anchor_parts(plate, dims, diameter, projection, length, include_hardware))
    return tuple(result)


def finish_rectangle(plate, chamfer=0., radius=0.):
    """Finit les quatre angles d’une platine rectangulaire, avec contrôle des trous."""
    if not (chamfer or radius):
        return plate
    if chamfer and radius:
        raise DimensionError(("chamfer", "corner_radius"), "Choisir un chanfrein ou un rayon pour les quatre angles.")
    x, y = zip(*plate.outline)
    x0, y0 = (max(x)+min(x))/2, (max(y)+min(y))/2
    a, b = (max(x)-min(x))/2, (max(y)-min(y))/2
    inset = chamfer or radius
    key = "chamfer" if chamfer else "corner_radius"
    if inset >= min(a, b):
        raise DimensionError((key,), f"La cote doit être inférieure à {min(a, b)*10:g} mm pour cette platine.")
    for h, v, diameter in plate.holes:
        h, v, r = abs(h-x0), abs(v-y0), diameter/2
        if chamfer and a+b-h-v-chamfer <= r*sqrt(2):
            raise DimensionError((key,), "Un perçage rencontre un angle chanfreiné.")
        if radius and h+r > a-radius and v+r > b-radius:
            if hypot(max(0, h-a+radius), max(0, v-b+radius))+r >= radius:
                raise DimensionError((key,), "Un perçage rencontre un angle arrondi.")
    outline = ((-a+inset, -b), (a-inset, -b), (a, -b+inset), (a, b-inset),
               (a-inset, b), (-a+inset, b), (-a, b-inset), (-a, -b+inset))
    arcs = ()
    if radius:
        corner = radius*(1-1/sqrt(2))
        arcs = tuple((idx, (x0+sx*(a-corner), y0+sy*(b-corner)))
                     for idx, sx, sy in ((1, 1, -1), (3, 1, 1), (5, -1, 1), (7, -1, -1)))
    return replace(plate, outline=tuple((x0+x, y0+y) for x, y in outline), arcs=arcs)


def bolt_rows(count, low, high, spacing, blocked=(), span=0):
    if count != int(count) or not 1 <= count <= 12:
        raise ValueError("Choisir entre 1 et 12 rangées entières.")
    count = int(count)
    allowed = [(low, high)] if low <= high else []
    for a, b in sorted(blocked):
        remaining = []
        for start, end in allowed:
            if b <= start or a >= end:
                remaining.append((start, end))
            else:
                if a > start:
                    remaining.append((start, a))
                if b < end:
                    remaining.append((b, end))
        allowed = remaining

    def fit(target, lower, upper):
        options = [min(max(target, l), r) for start, end in allowed
                   if (l := max(start, lower)) <= (r := min(end, upper))]
        if not options:
            raise ValueError("Les rangées ne tiennent pas entre les bords, les ailes et le jarret.")
        return min(options, key=lambda value: abs(value-target))

    if span:
        if (count == 1 or span/(count-1) < spacing):
            raise ValueError("Écarter les rangées de perçages.")
        targets = [(low+high-span)/2 + index*span/(count-1) for index in range(count)]
        return tuple(fit(y, y, y) for y in targets)
    latest = []
    upper = high
    for _ in range(count):
        latest.append(fit(upper, low, upper))
        upper = latest[-1]-spacing
    result = []
    lower = low
    for index, upper in enumerate(reversed(latest)):
        target = (low+high)/2 if count == 1 else low + index*(high-low)/(count-1)
        result.append(fit(target, lower, upper))
        lower = result[-1]+spacing
    return tuple(result)


def pitch_series(count, pitch):
    if count != int(count) or not 1 <= count <= 12:
        raise ValueError("Choisir entre 1 et 12 positions entières.")
    if count > 1 and pitch <= 0:
        raise ValueError("Renseigner un entraxe positif.")
    return tuple((index-(count-1)/2)*pitch for index in range(int(count)))


def fork_shims(origin, u, v, width, height, thickness, holes, extra, gap=2., inset=.2, cut=0.):
    if len(holes) != 4:
        raise ValueError("Les cales fourchettes suivent une grille de quatre ancrages.")
    axes_x = sorted({x for x, _, _ in holes})
    y = max(point[1] for point in holes)
    radius = holes[0][2]/2 + extra
    inner = gap/2
    half_w, half_h = width/2-inset, height/2-inset
    bevel = max(0, cut-2*inset)
    if len(axes_x) != 2 or min(half_w-abs(axes_x[0]), half_h-y, (axes_x[1]-axes_x[0])/2) <= radius or y <= inner:
        raise ValueError("Les fourchettes et leurs encoches ne tiennent pas sous la platine.")
    if (bevel >= min(half_w, half_h-inner) or
            (bevel and half_w+half_h-abs(axes_x[0])-y-bevel <= radius*sqrt(2))):
        raise ValueError("Une encoche rencontre le chanfrein de la cale.")
    left, right = axes_x
    outer = ((-half_w, half_h-bevel), (-half_w+bevel, half_h),
             (half_w-bevel, half_h), (half_w, half_h-bevel)) if bevel else (
             (-half_w, half_h), (half_w, half_h))
    outline = outer + ((half_w, inner),
                       (right+radius, inner), (right+radius, y), (right-radius, y),
                       (right-radius, inner), (left+radius, inner), (left+radius, y),
                       (left-radius, y), (left-radius, inner), (-half_w, inner))
    first_arc = len(outer)+2
    return tuple(Plate("Cale fourchette " + side, origin, u, v,
                       tuple((x, sign*h) for x, h in outline), thickness,
                       arcs=((first_arc, (right, sign*(y+radius))),
                             (first_arc+4, (left, sign*(y+radius)))))
                 for side, sign in (("avant", 1), ("arrière", -1)))


def haunch(origin, beam_axis, upward, section_width, bottom, dims, *, heel_ratio=0.):
    """Âme triangulaire centrée sous la poutre et semelle suivant sa pente."""
    reach, rise = dims["reach"], dims["drop"]
    web, flange, width = dims["web"], dims["flange"], dims["flange_width"]
    if min(reach, rise, web, flange, width) <= 0 or not web < width <= section_width:
        raise ValueError("Dimensions du jarret incompatibles avec la semelle de la poutre.")
    web_normal = geo.cross(beam_axis, upward)
    root = geo.add(origin, geo.scale(upward, bottom))
    web_origin = geo.add(root, geo.scale(web_normal, -web / 2))
    relief = dims["weld_relief"]
    if relief >= min(reach, rise):
        raise ValueError("Le chanfrein de soudure doit tenir dans l’âme du jarret.")
    corner = ((relief, 0), (-heel_ratio*relief, -relief)) if relief else ((0, 0),)
    heel_x = -heel_ratio*rise
    outline = corner + ((heel_x, -rise), (reach, 0))
    flat = dims.get("haunch_flat", 0.)
    if flat:
        heel_y = -rise + flat*rise/reach
        toe_x = reach - flat*(reach-heel_x)/rise
        tolerance = geo.PLANE_RELATION_TOLERANCE_CM
        if heel_y >= -max(relief, flat)-tolerance or toe_x <= relief+tolerance:
            raise DimensionError(("haunch_flat",), "Réduire le méplat pour conserver les chants d’appui du jarret.")
        heel = heel_ratio*heel_y
        outline = corner + ((heel, heel_y), (heel+flat, heel_y), (toe_x, -flat), (toe_x, 0))
    gusset = Plate("Âme de jarret", web_origin, beam_axis, upward, outline, web)
    low = geo.add(root, geo.scale(upward, -rise))
    diagonal = geo.add(geo.scale(beam_axis, reach), geo.scale(upward, rise))
    slope = geo.normalize(diagonal)
    distance = geo.length(diagonal)
    # Cette normale pointe sous l’âme. L’épaisseur se développe vers l’extérieur.
    lateral = geo.cross(upward, beam_axis)
    if geo.dot(geo.cross(slope, lateral), upward) > 0:
        lateral = geo.scale(lateral, -1)
    mid = geo.add(low, geo.scale(diagonal, .5))
    sole = rectangle("Semelle de jarret", mid, slope, lateral, distance, width, flange, finishable=False)
    return gusset, sole
