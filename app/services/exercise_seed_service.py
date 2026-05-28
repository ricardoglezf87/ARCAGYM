import json
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Exercise


SEED_PATH = Path(__file__).resolve().parents[1] / "seed" / "exercises_seed.json"


def _to_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        return "\n".join(str(item).strip() for item in value if str(item).strip())
    return str(value).strip()


def seed_exercises(db: Session) -> int:
    existing = db.scalar(select(Exercise).limit(1))
    if existing:
        return 0

    with SEED_PATH.open("r", encoding="utf-8") as file:
        exercises = json.load(file)

    created = 0
    for item in exercises:
        db.add(
            Exercise(
                name=item["name"],
                primary_muscle=item["primary_muscle"],
                secondary_muscles=_to_text(item.get("secondary_muscles")),
                exercise_type=item["exercise_type"],
                equipment=_to_text(item.get("equipment")),
                recommended_level=item.get("recommended_level", "principiante"),
                instructions=_to_text(item["instructions"]) or "",
                common_errors=_to_text(item.get("common_errors")),
                technique_tips=_to_text(item.get("technique_tips")),
                image_url=item.get("image_url"),
                source=item.get("source", "Base local inicial"),
                safety_notes=_to_text(item.get("safety_notes")),
            )
        )
        created += 1
    db.commit()
    return created
