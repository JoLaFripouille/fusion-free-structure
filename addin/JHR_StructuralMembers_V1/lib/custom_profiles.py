from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from . import dxf_geometry


CATEGORY_ID = "Personnalises"
CATEGORY_LABEL = "Personnalisés"
REGION_ID = "Local"
REGION_LABEL = "Local"
SCHEMA_VERSION = 1
MAX_DXF_SIZE_BYTES = 10 * 1024 * 1024
MIN_DIMENSION_MM = 1e-6


@dataclass(frozen=True)
class DxfAnalysis:
    source_path: Path
    width_mm: float
    height_mm: float
    contour_count: int
    entity_count: int
    sha256: str


@dataclass(frozen=True)
class CustomProfileRecord:
    family_id: str
    family_label: str
    section_label: str
    dxf_path: Path
    metadata_path: Path
    relative_path: str


@dataclass(frozen=True)
class ImportedProfile:
    record: CustomProfileRecord
    analysis: DxfAnalysis


@dataclass(frozen=True)
class DeletedProfile:
    relative_path: str
    trash_directory: Path
    active_reference_count: int


def default_data_root():
    appdata = str(os.environ.get("APPDATA", "")).strip()
    if not appdata:
        raise RuntimeError(
            "Le dossier de données utilisateur APPDATA est introuvable."
        )
    return Path(appdata) / "EI_JHR" / "fusion-free-structure"


def data_root_path(data_root=None):
    return Path(data_root) if data_root is not None else default_data_root()


def profiles_root(data_root=None):
    return data_root_path(data_root) / "profiles" / CATEGORY_ID


def trash_root(data_root=None):
    return data_root_path(data_root) / "corbeille_profils"


def _clean_label(value, label):
    result = str(value).strip()
    if not result:
        raise ValueError("{} obligatoire.".format(label))
    if len(result) > 80:
        raise ValueError("{} limité à 80 caractères.".format(label))
    if any(ord(character) < 32 for character in result):
        raise ValueError("{} contient un caractère de contrôle.".format(label))
    return result


def _safe_token(value, label):
    cleaned = _clean_label(value, label)
    ascii_value = unicodedata.normalize("NFKD", cleaned).encode(
        "ascii", "ignore"
    ).decode("ascii")
    token = re.sub(r"[^A-Za-z0-9._-]+", "_", ascii_value).strip("._-")
    token = re.sub(r"_+", "_", token)
    if not token:
        raise ValueError("{} ne permet pas de produire un nom de fichier sûr.".format(label))
    return token[:80]


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _is_ascii_r12(text):
    lines = text.splitlines()
    for index in range(len(lines) - 1):
        if lines[index].strip() == "1" and lines[index + 1].strip() == "AC1009":
            return True
    return False


def _polygon_area(points):
    return 0.5 * sum(
        first[0] * second[1] - second[0] * first[1]
        for first, second in zip(points, points[1:] + points[:1])
    )


def validate_dxf(source_path):
    path = Path(source_path)
    if not path.is_file():
        raise FileNotFoundError("Le fichier DXF sélectionné est introuvable.")
    if path.suffix.casefold() != ".dxf":
        raise ValueError("Le fichier sélectionné ne possède pas l'extension .dxf.")
    size = path.stat().st_size
    if size <= 0:
        raise ValueError("Le fichier DXF est vide.")
    if size > MAX_DXF_SIZE_BYTES:
        raise ValueError("Le DXF dépasse la limite de 10 Mo de cette première version.")
    try:
        text = path.read_text(encoding="ascii")
    except UnicodeDecodeError as error:
        raise ValueError("Le DXF doit être un fichier ASCII compatible R12.") from error
    if not _is_ascii_r12(text):
        raise ValueError("Le DXF doit être enregistré au format ASCII R12 (AC1009).")

    entities = dxf_geometry.read_r12_entities(path)
    contours = dxf_geometry.tessellate_profile_contours_mm(path)
    if any(abs(_polygon_area(contour)) <= MIN_DIMENSION_MM for contour in contours):
        raise ValueError("Un contour fermé possède une surface nulle.")
    min_x, min_y, max_x, max_y = dxf_geometry.profile_bounds_mm(path)
    width = max_x - min_x
    height = max_y - min_y
    if width <= MIN_DIMENSION_MM or height <= MIN_DIMENSION_MM:
        raise ValueError("Les dimensions du profil DXF sont nulles ou trop petites.")
    return DxfAnalysis(
        source_path=path,
        width_mm=width,
        height_mm=height,
        contour_count=len(contours),
        entity_count=len(entities),
        sha256=_sha256(path),
    )


def metadata_path_for_dxf(dxf_path):
    return Path(dxf_path).with_suffix(".profile.json")


def _logical_relative_path(family_id, filename):
    return (Path("profiles") / CATEGORY_ID / family_id / filename).as_posix()


def _record_from_metadata(metadata_path, root):
    resolved_root = root.resolve()
    resolved_metadata = metadata_path.resolve()
    if resolved_root not in resolved_metadata.parents:
        raise ValueError("Métadonnées situées hors de la bibliothèque personnalisée.")
    try:
        values = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(
            "Métadonnées personnalisées illisibles : {}.".format(metadata_path.name)
        ) from error
    if int(values.get("schema_version", 0)) != SCHEMA_VERSION:
        raise ValueError(
            "Version de métadonnées personnalisées non prise en charge : {}."
            .format(metadata_path.name)
        )
    if values.get("category_id") != CATEGORY_ID or values.get("units") != "mm":
        raise ValueError(
            "Métadonnées personnalisées incohérentes : {}.".format(
                metadata_path.name
            )
        )
    family_id = _safe_token(values.get("family_id", ""), "Identifiant de famille")
    family_label = _clean_label(values.get("family_label", ""), "Nom de famille")
    section_label = _clean_label(values.get("section_label", ""), "Désignation")
    filename = Path(str(values.get("filename", ""))).name
    if not filename or not filename.casefold().endswith(".dxf"):
        raise ValueError("Nom de DXF personnalisé invalide : {}.".format(metadata_path.name))
    dxf_path = metadata_path.parent / filename
    expected_parent = (resolved_root / family_id).resolve()
    if (
        resolved_root not in expected_parent.parents
        or metadata_path.parent.resolve() != expected_parent
        or metadata_path != metadata_path_for_dxf(dxf_path)
        or not dxf_path.is_file()
    ):
        raise ValueError(
            "Le DXF associé aux métadonnées {} est introuvable."
            .format(metadata_path.name)
        )
    return CustomProfileRecord(
        family_id=family_id,
        family_label=family_label,
        section_label=section_label,
        dxf_path=dxf_path,
        metadata_path=metadata_path,
        relative_path=_logical_relative_path(family_id, filename),
    )


def discover_records(data_root=None):
    root = profiles_root(data_root)
    if not root.is_dir():
        return ()
    records = [
        _record_from_metadata(metadata_path, root)
        for metadata_path in root.glob("*/*.profile.json")
    ]
    records.sort(key=lambda record: (
        record.family_label.casefold(),
        record.section_label.casefold(),
    ))
    return tuple(records)


def import_profile(source_path, family_label, section_label, data_root=None):
    analysis = validate_dxf(source_path)
    clean_family_label = _clean_label(family_label, "Nom de famille")
    clean_section_label = _clean_label(section_label, "Désignation")
    family_id = _safe_token(clean_family_label, "Nom de famille")
    filename = _safe_token(clean_section_label, "Désignation") + ".dxf"
    root = profiles_root(data_root)
    root.mkdir(parents=True, exist_ok=True)
    family_directory = root / family_id
    if root.resolve() not in family_directory.resolve().parents:
        raise ValueError("La famille sort de la bibliothèque personnalisée.")
    target_dxf = family_directory / filename
    target_metadata = metadata_path_for_dxf(target_dxf)
    if target_dxf.exists() or target_metadata.exists():
        raise FileExistsError(
            "Un profil personnalisé portant ce nom existe déjà dans cette famille."
        )

    family_directory.mkdir(parents=True, exist_ok=True)
    temporary_dxf = family_directory / (".import-{}-{}".format(uuid.uuid4().hex, filename))
    temporary_metadata = family_directory / (
        ".import-{}-{}.json".format(uuid.uuid4().hex, target_dxf.stem)
    )
    metadata = {
        "schema_version": SCHEMA_VERSION,
        "category_id": CATEGORY_ID,
        "family_id": family_id,
        "family_label": clean_family_label,
        "section_label": clean_section_label,
        "filename": filename,
        "original_filename": analysis.source_path.name,
        "units": "mm",
        "sha256": analysis.sha256,
        "imported_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    published_dxf = False
    published_metadata = False
    try:
        shutil.copyfile(analysis.source_path, temporary_dxf)
        if _sha256(temporary_dxf) != analysis.sha256:
            raise RuntimeError("La copie du DXF personnalisé n'est pas identique à la source.")
        temporary_metadata.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        # Les liens durs sont créés sans écraser une cible apparue entre-temps.
        # Les deux temporaires se trouvent dans le même dossier que leur cible.
        os.link(temporary_dxf, target_dxf)
        published_dxf = True
        os.link(temporary_metadata, target_metadata)
        published_metadata = True
    except Exception:
        for path, published in (
            (target_metadata, published_metadata),
            (target_dxf, published_dxf),
        ):
            if published and path.exists():
                path.unlink()
        raise
    finally:
        for path in (temporary_dxf, temporary_metadata):
            if path.exists():
                path.unlink()

    record = CustomProfileRecord(
        family_id=family_id,
        family_label=clean_family_label,
        section_label=clean_section_label,
        dxf_path=target_dxf,
        metadata_path=target_metadata,
        relative_path=_logical_relative_path(family_id, filename),
    )
    return ImportedProfile(record=record, analysis=analysis)


def _custom_paths_from_relative(relative_path, data_root=None):
    parts = Path(str(relative_path).replace("\\", "/")).parts
    if (
        len(parts) != 4
        or parts[0] != "profiles"
        or parts[1] != CATEGORY_ID
        or Path(parts[2]).name != parts[2]
        or Path(parts[3]).name != parts[3]
    ):
        raise ValueError("Le chemin ne désigne pas un profil personnalisé géré.")
    root = profiles_root(data_root).resolve()
    dxf_path = (root / parts[2] / parts[3]).resolve()
    if root not in dxf_path.parents:
        raise ValueError("Le chemin personnalisé sort de la bibliothèque locale.")
    return dxf_path, metadata_path_for_dxf(dxf_path)


def resolve_relative_path(relative_path, data_root=None):
    dxf_path, _ = _custom_paths_from_relative(relative_path, data_root)
    return dxf_path


def delete_profile(relative_path, active_reference_count=0, data_root=None):
    dxf_path, metadata_path = _custom_paths_from_relative(relative_path, data_root)
    if not dxf_path.is_file() or not metadata_path.is_file():
        raise FileNotFoundError("Le profil personnalisé ou ses métadonnées sont absents.")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = trash_root(data_root) / (
        "{}-{}-{}".format(timestamp, dxf_path.stem, uuid.uuid4().hex[:8])
    )
    destination.mkdir(parents=True, exist_ok=False)
    trash_dxf = destination / dxf_path.name
    trash_metadata = destination / metadata_path.name
    deletion_record = destination / "suppression.json"
    deletion_record.write_text(
        json.dumps({
            "schema_version": SCHEMA_VERSION,
            "original_relative_path": str(relative_path).replace("\\", "/"),
            "active_reference_count": int(active_reference_count),
            "deleted_at_utc": datetime.now(timezone.utc).isoformat(),
        }, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    try:
        shutil.move(str(dxf_path), str(trash_dxf))
        shutil.move(str(metadata_path), str(trash_metadata))
    except Exception:
        if trash_dxf.exists() and not dxf_path.exists():
            shutil.move(str(trash_dxf), str(dxf_path))
        if trash_metadata.exists() and not metadata_path.exists():
            shutil.move(str(trash_metadata), str(metadata_path))
        raise
    try:
        dxf_path.parent.rmdir()
    except OSError:
        pass
    return DeletedProfile(
        relative_path=str(relative_path).replace("\\", "/"),
        trash_directory=destination,
        active_reference_count=int(active_reference_count),
    )
