import re
import unicodedata

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Exercise, SavedRoutine, SavedRoutineDay, SavedRoutineExercise, User


ROUTINE_TITLE = "Rutina A/B/C - Hipertrofia máquinas"
ROUTINE_LEGACY_TITLES = ["Rutina A/B/C - Hipertrofia maquinas"]
DUMBBELL_ROUTINE_TITLE = "Rutina A/B/C - Hipertrofia mancuernas"
DUMBBELL_ROUTINE_LEGACY_TITLES = ["Rutina A/B/C - Hipertrofia con mancuernas"]

ROUTINE_DAYS = [
    {
        "name": "Dia A",
        "focus": "Enfasis en pecho y cuadriceps",
        "exercises": [
            ("Extension de cuadriceps en maquina", "4", "12-15"),
            ("Press de banca en maquina", "4", "8-12"),
            ("Jalon al pecho agarre cerrado", "4", "10-12"),
            ("Remo en maquina", "3", "10-12"),
            ("Aperturas en maquina contractora", "3", "12-15"),
            ("Face pull", "3", "15"),
            ("Curl martillo", "2", "10-12"),
            ("Extension de triceps en polea", "2", "12-15"),
            ("Crunch en máquina", "3", "15-20"),
        ],
    },
    {
        "name": "Dia B",
        "focus": "Enfasis en espalda y hombro",
        "exercises": [
            ("Curl femoral sentado", "3", "10-12"),
            ("Hip thrust en maquina", "3", "10-12"),
            ("Extension de cuadriceps en maquina", "3", "15"),
            ("Remo sentado en polea", "4", "10-12"),
            ("Press de hombro en maquina", "3", "8-12"),
            ("Pájaros en máquina", "3", "12-15"),
            ("Elevación lateral en máquina", "3", "12-15"),
            ("Curl en polea baja", "2", "10-12"),
            ("Encogimientos para trapecio", "3", "12-15"),
            ("Crunch en máquina", "3", "15-20"),
        ],
    },
    {
        "name": "Dia C",
        "focus": "Enfasis en hipertrofia general",
        "exercises": [
            ("Extension de cuadriceps en maquina", "4", "12-15"),
            ("Press inclinado en máquina", "3", "8-12"),
            ("Jalon al pecho agarre amplio", "3", "10-12"),
            ("Remo pecho apoyado en máquina", "3", "10-12"),
            ("Aperturas en maquina contractora", "2", "12-15"),
            ("Face pull", "2", "15"),
            ("Curl martillo", "2", "10-12"),
            ("Extension de triceps en polea", "2", "12-15"),
            ("Crunch en máquina", "3", "15-20"),
        ],
    },
]


DUMBBELL_ROUTINE_DAYS = [
    {
        "name": "Dia A",
        "focus": "Enfasis en pecho y cuadriceps con mancuernas",
        "exercises": [
            ("Zancada bulgara", "4", "12-15"),
            ("Press de banca con mancuernas", "4", "8-12"),
            ("Pullover con mancuerna para dorsales", "4", "10-12"),
            ("Remo con mancuerna a una mano", "3", "10-12"),
            ("Aperturas con mancuernas en banco plano", "3", "12-15"),
            ("Pajaros con mancuernas", "3", "15"),
            ("Curl martillo", "2", "10-12"),
            ("Extension de triceps sobre la cabeza con mancuerna", "2", "12-15"),
            ("Crunch con mancuerna", "3", "15-20"),
        ],
    },
    {
        "name": "Dia B",
        "focus": "Enfasis en espalda y hombro con mancuernas",
        "exercises": [
            ("Peso muerto rumano con mancuernas", "3", "10-12"),
            ("Hip thrust con mancuerna", "3", "10-12"),
            ("Zancada bulgara", "3", "15"),
            ("Remo con mancuerna a una mano", "4", "10-12"),
            ("Press sentado con mancuernas", "3", "8-12"),
            ("Pajaros con mancuernas", "3", "12-15"),
            ("Curl alterno con mancuernas", "2", "10-12"),
            ("Encogimientos con mancuernas", "3", "12-15"),
            ("Crunch con mancuerna", "3", "15-20"),
        ],
    },
    {
        "name": "Dia C",
        "focus": "Enfasis en hipertrofia general con mancuernas",
        "exercises": [
            ("Zancada bulgara", "4", "12-15"),
            ("Press inclinado con mancuernas", "3", "8-12"),
            ("Pullover con mancuerna para dorsales", "3", "10-12"),
            ("Remo con mancuerna a una mano", "3", "10-12"),
            ("Aperturas con mancuernas en banco plano", "2", "12-15"),
            ("Pajaros con mancuernas", "2", "15"),
            ("Curl martillo", "2", "10-12"),
            ("Extension de triceps sobre la cabeza con mancuerna", "2", "12-15"),
            ("Crunch con mancuerna", "3", "15-20"),
        ],
    },
]


def _normalize_key(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", ascii_value.lower()).strip()


def _exercise_lookup(exercises: list[Exercise]) -> dict[str, Exercise]:
    lookup: dict[str, Exercise] = {}
    for exercise in exercises:
        lookup.setdefault(_normalize_key(exercise.name), exercise)
        if exercise.slug:
            lookup.setdefault(_normalize_key(exercise.slug), exercise)
    return lookup


def _new_routine(
    user: User,
    exercise_lookup: dict[str, Exercise],
    *,
    title: str,
    days: list[dict],
    equipment_available: str,
    preferences: str,
    explanation: str,
) -> SavedRoutine:
    routine = SavedRoutine(
        user_id=user.id,
        title=title,
        split="A/B/C",
        goal="hipertrofia",
        experience_level=user.experience_level,
        days_per_week=3,
        session_duration=60,
        equipment_available=equipment_available,
        preferences=preferences,
        progression="Usa doble progresion: primero sube repeticiones dentro del rango y despues aumenta el peso.",
        safety_notes="Calienta con series ligeras y ajusta cargas si aparece dolor articular.",
        explanation=explanation,
    )

    for day_index, day in enumerate(days):
        routine_day = SavedRoutineDay(order_index=day_index, name=day["name"], focus=day["focus"])
        for exercise_index, (exercise_name, sets, reps) in enumerate(day["exercises"]):
            exercise = exercise_lookup.get(_normalize_key(exercise_name))
            if not exercise:
                continue
            routine_day.exercises.append(
                SavedRoutineExercise(
                    exercise_id=exercise.id,
                    order_index=exercise_index,
                    name=exercise.name,
                    primary_muscle=exercise.primary_muscle,
                    sets=sets,
                    reps=reps,
                    rest="",
                    notes="",
                )
            )
        routine.days.append(routine_day)

    return routine


def _ensure_routine(
    db: Session,
    user: User,
    exercise_lookup: dict[str, Exercise],
    *,
    title: str,
    legacy_titles: list[str],
    days: list[dict],
    equipment_available: str,
    preferences: str,
    explanation: str,
) -> SavedRoutine:
    existing = db.scalar(
        select(SavedRoutine).where(
            SavedRoutine.user_id == user.id,
            SavedRoutine.title.in_([title, *legacy_titles]),
        )
    )
    if existing:
        existing.title = title
        return existing

    routine = _new_routine(
        user,
        exercise_lookup,
        title=title,
        days=days,
        equipment_available=equipment_available,
        preferences=preferences,
        explanation=explanation,
    )
    db.add(routine)
    return routine


def ensure_personal_routine(db: Session, user: User) -> SavedRoutine | None:
    exercise_lookup = _exercise_lookup(list(db.scalars(select(Exercise)).all()))
    machine_routine = _ensure_routine(
        db,
        user,
        exercise_lookup,
        title=ROUTINE_TITLE,
        legacy_titles=ROUTINE_LEGACY_TITLES,
        days=ROUTINE_DAYS,
        equipment_available="Maquina, Polea, Mancuernas",
        preferences="Rutina de tres dias con enfasis rotatorio en pecho, cuadriceps, espalda y hombro.",
        explanation="Rutina de 3 dias y unos 60 minutos por sesion, orientada a hipertrofia con maquinas y poleas.",
    )
    _ensure_routine(
        db,
        user,
        exercise_lookup,
        title=DUMBBELL_ROUTINE_TITLE,
        legacy_titles=DUMBBELL_ROUTINE_LEGACY_TITLES,
        days=DUMBBELL_ROUTINE_DAYS,
        equipment_available="Mancuernas, Banco",
        preferences="Equivalente A/B/C de la rutina de maquinas, con los mismos grupos musculares y ejercicios de mancuernas.",
        explanation="Rutina de 3 dias y unos 60 minutos por sesion, orientada a hipertrofia con mancuernas.",
    )

    db.commit()
    db.refresh(machine_routine)
    return machine_routine
