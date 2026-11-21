"""Implantation géométrique d'un garde-corps sur des appuis acier, en mm."""

import bisect
import math

from . import joint_geometry as geo


UP = (0., 0., 1.)
VERTICAL_AXES = {"Y": (0., 1., 0.), "Z": UP}
TOL = 0.01
DEFAULTS = {
    "model": "industrial",
    "mounting": "top",
    "vertical_axis": "auto",
    "support": "steel",
    "drill_support": False,
    "anchor_diameter_mm": 12.,
    "anchor_embedment_mm": 80.,
    "anchor_projection_mm": 20.,
    "height_mm": 1100.,
    "start_margin_mm": 100.,
    "end_margin_mm": 100.,
    "post_spacing_max_mm": 1200.,
    "post_count": 0,
    "distribution": "horizontal",
    "post_type": "flat",
    "post_width_mm": 50.,
    "post_depth_mm": 10.,
    "post_wall_mm": 2.,
    "post_tip_height_mm": 60.,
    "post_tip_flat_mm": 10.,
    "handrail_type": "round_tube",
    "handrail_width_mm": 42.4,
    "handrail_depth_mm": 42.4,
    "handrail_wall_mm": 2.3,
    "middle_count": 1,
    "middle_type": "round_tube",
    "middle_width_mm": 21.3,
    "middle_depth_mm": 21.3,
    "middle_wall_mm": 2.3,
    "kickplate": True,
    "kickplate_side": "left",
    "kickplate_height_mm": 150.,
    "kickplate_thickness_mm": 6.,
    "kickplate_clearance_mm": 10.,
    "plate_along_mm": 100.,
    "plate_across_mm": 120.,
    "plate_thickness_mm": 10.,
    "hole_pitch_along_mm": 60.,
    "hole_pitch_across_mm": 80.,
    "hole_diameter_mm": 14.,
    "side_drop_mm": 60.,
    "clearance_mm": 0.7,
    "bar_shape": "square",
    "bar_width_mm": 12.,
    "bar_depth_mm": 6.,
    "max_clear_mm": 100.,
    "lower_rail_clearance_mm": 75.,
}


def _settings(supplied):
    supplied = dict(supplied or {})
    if unknown := supplied.keys() - DEFAULTS.keys():
        raise ValueError("Réglages inconnus du garde-corps : " + ", ".join(sorted(unknown)))
    values = DEFAULTS | supplied
    if values["model"] not in ("industrial", "barreaude"):
        raise ValueError("Choisir un garde-corps industriel ou barreaudé.")
    if values["model"] == "barreaude":
        defaults = {"handrail_type": "flat", "handrail_width_mm": values["post_width_mm"],
                    "handrail_depth_mm": values["post_depth_mm"], "kickplate": False}
        values.update({key: value for key, value in defaults.items() if key not in supplied})
        if values["post_type"] != "flat":
            raise ValueError("Le modèle barreaudé utilise des poteaux plats.")
    if values["mounting"] not in ("top", "side"):
        raise ValueError("Choisir une pose à la française (top) ou à l’anglaise (side).")
    if values["vertical_axis"] not in ("auto", "Y", "Z"):
        raise ValueError("Choisir l’axe vertical automatique, Y ou Z.")
    if values["support"] not in ("steel", "concrete"):
        raise ValueError("Choisir un support acier (steel) ou béton (concrete).")
    if type(values["drill_support"]) is not bool:
        raise ValueError("Le réglage de perçage du support doit être un booléen.")
    if values["support"] == "concrete" and values["drill_support"]:
        raise ValueError("L’usinage traversant du support est réservé aux appuis acier.")
    if values["distribution"] not in ("horizontal", "along_path"):
        raise ValueError("Répartition attendue : horizontale ou suivant le rampant.")
    if not isinstance(values["kickplate"], bool):
        raise ValueError("Le réglage de la plinthe doit être un booléen.")
    if values["kickplate_side"] not in ("left", "right"):
        raise ValueError("Choisir le côté gauche ou droit de la plinthe dans le sens du parcours.")
    for key, low, high in (("post_count", 0, 100), ("middle_count", 0, 10)):
        value = values[key]
        if type(value) is not int or not low <= value <= high:
            raise ValueError(f"{key} doit être un entier de {low} à {high}.")
    allow_zero = {"start_margin_mm", "end_margin_mm", "side_drop_mm",
                  "kickplate_clearance_mm", "clearance_mm", "anchor_projection_mm"}
    for key, value in values.items():
        if key.endswith("_mm") and (type(value) not in (int, float) or not math.isfinite(value)
                or value < 0 or (not value and key not in allow_zero)):
            raise ValueError(f"{key} doit être une cote valide en millimètres.")
    if values["support"] == "concrete" and values["anchor_diameter_mm"] >= values["hole_diameter_mm"]:
        raise ValueError("Le diamètre de l’ancrage doit être inférieur au trou de la platine.")
    return values


def _anchors(plates, cfg):
    if cfg["support"] != "concrete":
        return []
    anchors = []
    for plate in plates:
        axis = plate["normal"]
        for index, (u, v, _) in enumerate(plate["holes"]):
            point = geo.add(plate["center"], geo.add(geo.scale(plate["u"], u), geo.scale(plate["v"], v)))
            buried = geo.subtract(point, geo.scale(axis, cfg["anchor_embedment_mm"]))
            free = geo.add(point, geo.scale(axis, plate["thickness_mm"]+cfg["anchor_projection_mm"]))
            anchors.append(dict(name=f"Ancrage {plate['name'].lower()} · {index+1}", segment=plate["segment"],
                                start=buried, end=free, center=point, diameter_mm=cfg["anchor_diameter_mm"]))
    return anchors


def _section(cfg, name):
    section = {key: cfg[f"{name}_{key}"] for key in ("type", "width_mm", "depth_mm", "wall_mm")}
    kind = section["type"]
    if kind not in ("flat", "rectangular_tube", "round_tube"):
        raise ValueError(f"Section {name} inconnue.")
    width, depth, wall = (section[key] for key in ("width_mm", "depth_mm", "wall_mm"))
    if kind == "round_tube" and not math.isclose(width, depth, abs_tol=TOL):
        raise ValueError(f"Pour le tube rond {name}, les deux dimensions doivent être égales.")
    if kind != "flat" and wall * 2 >= min(width, depth):
        raise ValueError(f"Épaisseur de paroi trop grande pour {name}.")
    return section


def _dist(a, b):
    return geo.length(geo.subtract(a, b))


def _frames(segments, cfg):
    frames, stations = [], [0.]
    horizontal = outward = None
    up = VERTICAL_AXES.get(cfg["vertical_axis"], UP)
    if not 1 <= len(segments) <= 25:
        raise ValueError("Sélectionner de 1 à 25 segments droits consécutifs.")
    for index, (start, end, normal) in enumerate(segments):
        if not all(len(p) == 3 and all(math.isfinite(v) for v in p) for p in (start, end, normal)):
            raise ValueError("Points et normales d'appui invalides.")
        if index and _dist(start, frames[-1]["end"]) > TOL:
            raise ValueError(f"Le segment {index+1} doit joindre exactement le précédent sur l’appui.")
        delta = geo.subtract(end, start)
        direction = geo.normalize(delta)
        projection = geo.subtract(delta, geo.scale(up, geo.dot(delta, up)))
        length_xy = geo.length(projection)
        cosine = length_xy / geo.length(delta)
        if cosine < 0.15:
            raise ValueError("Le rampant est trop proche de la verticale.")
        run = geo.normalize(projection)
        side = geo.cross(up, run)
        rail_normal = geo.cross(direction, side)
        if horizontal is not None and geo.dot(horizontal, run) < 1.-1e-8:
            raise ValueError("Le raccord palier-rampant doit conserver la même direction en plan.")
        if cfg["mounting"] == "top":
            if geo.dot(normal, rail_normal) < 1.-1e-6:
                raise ValueError(f"La face {index+1} doit être le dessus plan du support, dans le sens du segment.")
        elif abs(geo.dot(normal, side)) < 1.-1e-6 or (outward and geo.dot(normal, outward) < 1.-1e-6):
            raise ValueError("Les faces latérales doivent rester du même côté d’un appui vertical.")
        frames.append(dict(start=tuple(start), end=tuple(end), normal=normal, direction=direction,
                           cosine=cosine, side=side, run=run, rail_normal=rail_normal, up=up))
        measured = length_xy if cfg["distribution"] == "horizontal" else geo.length(delta)
        stations.append(stations[-1]+measured)
        horizontal, outward = run, normal
    return frames, stations


def _stations(cfg, stations):
    first, last = cfg["start_margin_mm"], stations[-1]-cfg["end_margin_mm"]
    span = last-first
    if span <= TOL:
        raise ValueError("Les retraits de bout ne laissent aucun tronçon pour les poteaux.")
    max_pitch = cfg["post_spacing_max_mm"]
    count = cfg["post_count"] or (math.ceil(span/max_pitch)+1)
    if not 2 <= count <= 100:
        raise ValueError("Prévoir de 2 à 100 poteaux.")
    pitch = span/(count-1)
    if pitch > max_pitch+TOL:
        raise ValueError("Le nombre de poteaux choisi dépasse l'entraxe maximal.")
    result = []
    for index in range(count):
        distance = first + pitch*index
        # À la jonction exacte, le poteau appartient au support suivant.
        segment = min(bisect.bisect_right(stations, distance+1e-7)-1, len(stations)-2)
        start, end = stations[segment:segment+2]
        result.append((segment, (distance-start)/(end-start)))
    return pitch, result


def _rail_sections(cfg, frame, handrail, middle):
    # Reprise de Fusion Fabrication : hauteur au dessus de la main courante,
    # profondeur verticale corrigée du cosinus, et vides de sous-lisses égaux.
    cosine = frame["cosine"]
    handrail_depth = handrail["depth_mm"]/cosine
    height = cfg["height_mm"]
    lower = cfg["plate_thickness_mm"] if cfg["mounting"] == "top" else 0.
    sections = [("Main courante", height-handrail_depth/2, handrail)]
    if cfg["model"] == "barreaude":
        low = _section(cfg, "post")
        bottom = cfg["lower_rail_clearance_mm"]
        if bottom < lower or bottom+(low["depth_mm"]/cosine) >= height-handrail_depth:
            raise ValueError("La lisse basse doit rester entre les platines et la main courante.")
        return sections + [("Lisse basse", bottom+low["depth_mm"]/(2*cosine), low)]
    if cfg["kickplate"]:
        depth = cfg["kickplate_height_mm"]/cosine
        bottom = cfg["kickplate_clearance_mm"]
        if bottom < lower:
            raise ValueError("La plinthe interfère avec les platines.")
        sections.append(("Plinthe", bottom+depth/2, {
            "type": "flat", "width_mm": cfg["kickplate_thickness_mm"],
            "depth_mm": cfg["kickplate_height_mm"], "wall_mm": 0.,
        }))
        lower = bottom+depth
    count = cfg["middle_count"]
    depth = middle["depth_mm"]/cosine
    gap = (height-handrail_depth-lower-count*depth)/(count+1)
    if gap < TOL:
        raise ValueError("La hauteur du garde-corps ne laisse pas assez de place aux lisses.")
    for index in range(count):
        sections.append((f"Sous-lisse {index+1}", lower+gap*(index+1)+depth*(index+.5), middle))
    return sections


def _join_rails(rails, frames):
    for index, (previous, following) in enumerate(zip(rails, rails[1:])):
        a, b = frames[index:index+2]
        direction_a, direction_b = a["direction"], b["direction"]
        normal = geo.normalize(geo.add(direction_a, direction_b))
        determinant = geo.dot(geo.cross(direction_a, direction_b), a["side"])
        for left, right in zip(previous, following):
            delta = geo.subtract(right["start"], left["end"])
            if abs(determinant) < 1e-8:
                if geo.length(delta) > TOL:
                    raise ValueError("Deux lisses parallèles restent décalées au raccord.")
                point = left["end"]
            else:
                offset = geo.dot(geo.cross(delta, direction_b), a["side"])/determinant
                point = geo.add(left["end"], geo.scale(direction_a, offset))
            if (geo.dot(geo.subtract(point, left["start"]), direction_a) <= TOL
                    or geo.dot(geo.subtract(right["end"], point), direction_b) <= TOL):
                raise ValueError("Un segment est trop court pour la coupe au raccord.")
            left.update(end=point, end_plane=normal)
            right.update(start=point, start_plane=normal)


def _plate_at(cfg, frame, foot, post, lateral):
    along, across = cfg["plate_along_mm"], cfg["plate_across_mm"]
    thickness = cfg["plate_thickness_mm"]
    if lateral:
        v = frame["up"]
        u = geo.cross(v, frame["normal"])
        center = geo.add(foot, geo.scale(v, -cfg["side_drop_mm"]))
        footprint = post["depth_mm"]/2
    else:
        u, v = frame["direction"], frame["side"]
        center = foot
        footprint = post["depth_mm"]/(2*frame["cosine"])
    if 2*footprint > along or (not lateral and post["width_mm"] > across):
        raise ValueError("La platine est trop petite pour la section du poteau.")
    pitch_u, pitch_v = cfg["hole_pitch_along_mm"], cfg["hole_pitch_across_mm"]
    diameter = cfg["hole_diameter_mm"]
    radius = diameter/2
    if min(pitch_u, pitch_v) <= diameter or min(along-pitch_u, across-pitch_v) <= diameter:
        raise ValueError("Les trous se touchent ou débordent du contour des platines.")
    clearance_u = max(0., pitch_u/2 - footprint)
    clearance_v = 0. if lateral else max(0., pitch_v/2 - post["width_mm"]/2)
    if math.hypot(clearance_u, clearance_v) <= radius+TOL:
        raise ValueError("La grille de trous traverse l'emprise du poteau.")
    holes = [(x*pitch_u/2, y*pitch_v/2, diameter) for x in (-1, 1) for y in (-1, 1)]
    return dict(center=center, u=u, v=v, normal=frame["normal"],
                along_mm=along, across_mm=across, thickness_mm=thickness, holes=holes)


def _post_tip(cfg, frame, contact, post, handrail):
    if post["type"] != "flat" or (cfg["model"] == "barreaude" and handrail["type"] == "flat"):
        return ()
    half_flat = cfg["post_tip_flat_mm"]/2
    run = post["width_mm"]/2-half_flat
    if run <= TOL:
        raise ValueError("Le méplat de tête doit être plus étroit que le poteau plat.")
    n, across, cosine = frame["rail_normal"], frame["side"], frame["cosine"]
    # Le méplat est tangent à la sous-face. Chaque biais descend de la
    # hauteur réglée, mesurée verticalement comme sur le plat de référence.
    cap = geo.subtract(contact, geo.scale(frame["up"], handrail["depth_mm"]/(2*cosine)))
    steepness = cfg["post_tip_height_mm"]*cosine/run
    planes = [(cap, n)]
    for sign in (-1., 1.):
        origin = geo.add(cap, geo.scale(across, sign*half_flat))
        normal = geo.normalize(geo.add(n, geo.scale(across, sign*steepness)))
        planes.append((origin, normal))
    return tuple(planes)


def plan_guardrail(segments, settings=None):
    """Calcule les rails, montants et platines. Une face réelle par segment."""
    segments = tuple(segments)
    cfg = _settings(settings)
    up = VERTICAL_AXES.get(cfg["vertical_axis"], UP)
    lateral = cfg["mounting"] == "side"
    post, handrail, middle = (_section(cfg, name) for name in ("post", "handrail", "middle"))
    frames, lengths = _frames(segments, cfg)
    pitch, stations = _stations(cfg, lengths)
    rails = []
    for frame in frames:
        shift = geo.scale(frame["normal"], cfg["plate_thickness_mm"]+post["width_mm"]/2) if lateral else (0.,)*3
        frame["shift"] = shift
        row = []
        for name, height, section in _rail_sections(cfg, frame, handrail, middle):
            offset = geo.add(shift, geo.scale(up, height))
            if name == "Plinthe":
                sign = 1. if cfg["kickplate_side"] == "left" else -1.
                distance = (post["width_mm"]+section["width_mm"])/2
                offset = geo.add(offset, geo.scale(frame["side"], sign*distance))
            row.append(dict(name=name, start=geo.add(frame["start"], offset),
                            end=geo.add(frame["end"], offset), section=section, u=frame["side"],
                            v=frame["rail_normal"], direction=frame["direction"]))
        rails.append(row)
    _join_rails(rails, frames)
    posts, plates = [], []
    for index, (segment, fraction) in enumerate(stations):
        frame = frames[segment]
        foot = geo.add(frame["start"], geo.scale(geo.subtract(frame["end"], frame["start"]), fraction))
        plate = _plate_at(cfg, frame, foot, post, lateral)
        plate.update(segment=segment, name=f"Platine {index+1}")
        plates.append(plate)
        height = cfg["height_mm"]-handrail["depth_mm"]/(2*frame["cosine"])
        contact = geo.add(geo.add(foot, frame["shift"]), geo.scale(up, height))
        center = plate["center"]
        start = (geo.add(geo.add(center, frame["shift"]), geo.scale(up, -plate["across_mm"]/2))
                 if lateral else geo.add(center, geo.scale(frame["normal"], plate["thickness_mm"])))
        # A vertical post keeps its horizontal station when the top plate is inclined.
        if not lateral:
            start = geo.add(foot, geo.scale(up, plate["thickness_mm"]/frame["cosine"]))
        tip = _post_tip(cfg, frame, contact, post, handrail)
        if tip and geo.dot(geo.subtract(tip[0][0], start), up) <= cfg["post_tip_height_mm"]+TOL:
            raise ValueError("La hauteur disponible du poteau ne permet pas la taille en pointe.")
        posts.append(dict(name=f"Poteau {index+1}", start=start, end=contact, section=post,
                          u=frame["side"], v=frame["run"], direction=up, segment=segment,
                          foot_normal=up if lateral else frame["normal"], tip_planes=tip))
    plan = dict(settings=cfg, rails=rails, posts=posts, plates=plates,
                anchors=_anchors(plates, cfg), pitch_mm=pitch)
    if cfg["model"] == "barreaude":
        from . import guardrail_infill

        plan.update(guardrail_infill.plan_infill(rails, posts, up, cfg, support_segments=segments))
    return plan


def plan_post_split(post, plate, rails, mode="halves", gap_mm=0., added_thickness_mm=5.):
    """Coupe la main courante d’équerre et les autres pièces au plan des plats."""
    if post["section"]["type"] != "flat":
        raise ValueError("Sélectionner un poteau plat.")
    if mode not in ("halves", "adjacent"):
        raise ValueError("Choisir deux demi-poteaux ou un plat ajouté.")
    if type(gap_mm) not in (int, float) or not math.isfinite(gap_mm) or gap_mm < 0:
        raise ValueError("Le jeu de coupe doit être positif ou nul.")
    depth = post["section"]["depth_mm"]
    along = post["v"]
    original = post["start"]
    if mode == "adjacent":
        if (type(added_thickness_mm) not in (int, float) or not math.isfinite(added_thickness_mm)
                or not TOL < added_thickness_mm <= depth):
            raise ValueError("Le plat ajouté doit avoir une épaisseur positive au plus égale au plat existant.")
        allowance = plate["along_mm"]*abs(geo.dot(plate["u"], along))/2
        if depth/2+added_thickness_mm > allowance-TOL:
            raise ValueError("La platine ne couvre pas le renfort ajouté à cette position.")
        # Contrôle de l'emprise de la nouvelle tôle au droit des trous de la platine.
        for u, v, diameter in plate["holes"]:
            offset = geo.add(geo.scale(plate["u"], u), geo.scale(plate["v"], v))
            x = geo.dot(offset, along)
            y = abs(geo.dot(offset, post["u"]))
            dx = max(0., depth/2-x, x-(depth/2+added_thickness_mm))
            dy = max(0., y-post["section"]["width_mm"]/2)
            if math.hypot(dx, dy) <= diameter/2+TOL:
                raise ValueError("Le plat ajouté déborde sur un perçage de la platine.")
        interface = geo.add(original, geo.scale(along, depth/2))
    else:
        interface = original
    rail_cuts = []
    for rail in rails:
        axis = rail["direction"]
        normal = axis if rail["name"] == "Main courante" else along
        station = geo.dot(geo.subtract(interface, rail["start"]), along) / geo.dot(axis, along)
        total = geo.dot(geo.subtract(rail["end"], rail["start"]), axis)
        if min(station, total-station)*geo.dot(axis, normal) <= gap_mm/2+TOL:
            raise ValueError(f"{rail['name']} : le poteau n’est pas entre les deux bouts de la lisse.")
        point = geo.add(rail["start"], geo.scale(axis, station))
        rail_cuts.append(dict(name=rail["name"], point=point, normal=normal,
                              before=geo.subtract(point, geo.scale(normal, gap_mm/2)),
                              after=geo.add(point, geo.scale(normal, gap_mm/2))))
    return dict(mode=mode, interface=interface, post_normal=along,
                existing_thickness_mm=depth/2 if mode == "halves" else depth,
                added_thickness_mm=depth/2 if mode == "halves" else added_thickness_mm,
                rail_cuts=rail_cuts, gap_mm=gap_mm)
