import json
import re
import unicodedata
from pathlib import Path
from typing import Any

from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from app.models import Exercise


SEED_PATH = Path(__file__).resolve().parents[1] / "seed" / "exercises_seed.json"
IMAGE_MANIFEST_PATH = Path(__file__).resolve().parents[1] / "seed" / "exercise_images.json"

EXERCISE_SCHEMA_COLUMNS = {
    "slug": "VARCHAR(180)",
    "category_label": "VARCHAR(120)",
    "movement_pattern": "VARCHAR(80)",
    "image_alt": "VARCHAR(255)",
}


def _to_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        return "\n".join(str(item).strip() for item in value if str(item).strip())
    return str(value).strip()


def _clean_string(value: Any, default: str | None = None, lowercase: bool = False) -> str | None:
    text_value = _to_text(value)
    if not text_value:
        return default
    return text_value.lower() if lowercase else text_value


def _slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_value).strip("-").lower()
    return slug or "ejercicio"


def _lookup_key(value: str | None) -> str:
    return _slugify(value or "")


def _load_seed_items() -> list[dict[str, Any]]:
    with SEED_PATH.open("r", encoding="utf-8-sig") as file:
        payload = json.load(file)
    if isinstance(payload, dict):
        return list(payload.get("exercises", []))
    return list(payload)


def _load_image_items() -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    if not IMAGE_MANIFEST_PATH.exists():
        return {}, {}

    with IMAGE_MANIFEST_PATH.open("r", encoding="utf-8-sig") as file:
        payload = json.load(file)
    items = payload.get("images", []) if isinstance(payload, dict) else payload
    image_items_by_slug: dict[str, dict[str, Any]] = {}
    image_items_by_name: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        slug = _clean_string(item.get("slug"))
        name = _clean_string(item.get("name"))
        if slug:
            image_items_by_slug[slug] = item
        if name:
            image_items_by_name[name] = item
    return image_items_by_slug, image_items_by_name


def _apply_image_values(values: dict[str, Any], image_item: dict[str, Any] | None) -> None:
    if not image_item:
        return
    values["image_url"] = _clean_string(image_item.get("image_url")) or values["image_url"]
    values["image_alt"] = _clean_string(image_item.get("image_alt")) or values["image_alt"]


def _apply_exercise_image(exercise: Exercise, image_item: dict[str, Any] | None) -> None:
    if not image_item:
        return
    image_url = _clean_string(image_item.get("image_url"))
    image_alt = _clean_string(image_item.get("image_alt"))
    if image_url:
        exercise.image_url = image_url
    if image_alt:
        exercise.image_alt = image_alt


def ensure_exercise_schema(db: Session) -> None:
    inspector = inspect(db.bind)
    if "exercises" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("exercises")}
    for column_name, ddl_type in EXERCISE_SCHEMA_COLUMNS.items():
        if column_name not in existing_columns:
            db.execute(text(f"ALTER TABLE exercises ADD COLUMN {column_name} {ddl_type}"))
    db.commit()


def _exercise_values(item: dict[str, Any]) -> dict[str, Any]:
    name = _clean_string(item.get("name"), "Ejercicio sin nombre") or "Ejercicio sin nombre"
    slug = _clean_string(item.get("slug")) or _slugify(name)
    return {
        "slug": slug,
        "name": name,
        "category_label": _clean_string(item.get("category_label")),
        "primary_muscle": _clean_string(item.get("primary_muscle"), "General") or "General",
        "secondary_muscles": _to_text(item.get("secondary_muscles")),
        "exercise_type": _clean_string(
            item.get("exercise_type"),
            "compuesto",
            lowercase=True,
        )
        or "compuesto",
        "equipment": _to_text(item.get("equipment")),
        "recommended_level": _clean_string(
            item.get("recommended_level", item.get("level")),
            "principiante",
            lowercase=True,
        )
        or "principiante",
        "movement_pattern": _clean_string(item.get("movement_pattern")),
        "instructions": _to_text(item.get("instructions")) or "Ejecuta el ejercicio con control.",
        "common_errors": _to_text(item.get("common_errors")),
        "technique_tips": _to_text(item.get("technique_tips")),
        "image_url": item.get("image_url"),
        "image_alt": _clean_string(item.get("image_alt")),
        "source": _clean_string(item.get("source"), "Base local inicial"),
        "safety_notes": _to_text(item.get("safety_notes", item.get("safety"))),
    }


def seed_exercises(db: Session) -> int:
    ensure_exercise_schema(db)
    exercises = _load_seed_items()
    image_items_by_slug, image_items_by_name = _load_image_items()
    existing_exercises = list(db.scalars(select(Exercise)).all())
    existing_by_slug = {exercise.slug: exercise for exercise in existing_exercises if exercise.slug}
    existing_by_name = {exercise.name: exercise for exercise in existing_exercises}
    normalized_names: dict[str, list[Exercise]] = {}
    for exercise in existing_exercises:
        normalized_names.setdefault(_lookup_key(exercise.name), []).append(exercise)
    existing_by_normalized_name = {
        key: items[0]
        for key, items in normalized_names.items()
        if key and len(items) == 1
    }

    changed = 0
    for item in exercises:
        values = _exercise_values(item)
        image_item = image_items_by_slug.get(values["slug"]) or image_items_by_name.get(values["name"])
        _apply_image_values(values, image_item)
        exercise = (
            existing_by_slug.get(values["slug"])
            or existing_by_name.get(values["name"])
            or existing_by_normalized_name.get(_lookup_key(values["name"]))
        )
        if exercise:
            for key, value in values.items():
                setattr(exercise, key, value)
        else:
            exercise = Exercise(**values)
            db.add(exercise)
            existing_by_slug[values["slug"]] = exercise
            existing_by_name[values["name"]] = exercise
        changed += 1

    for exercise in existing_exercises:
        image_item = None
        if exercise.slug:
            image_item = image_items_by_slug.get(exercise.slug)
        if not image_item:
            image_item = image_items_by_name.get(exercise.name)
        _apply_exercise_image(exercise, image_item)
    db.commit()
    return changed
