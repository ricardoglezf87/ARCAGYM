from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import Exercise, User, WorkoutExercise, WorkoutSession


MUSCLE_BY_SPLIT = {
    "full body": [["Piernas", "Pecho", "Espalda", "Core"], ["Piernas", "Hombros", "Espalda", "Core"], ["Pecho", "Espalda", "Piernas", "Biceps", "Triceps"]],
    "torso/pierna": [["Pecho", "Espalda", "Hombros", "Biceps", "Triceps"], ["Piernas", "Core"], ["Pecho", "Espalda", "Hombros", "Biceps", "Triceps"], ["Piernas", "Core"]],
    "push/pull/legs": [["Pecho", "Hombros", "Triceps"], ["Espalda", "Biceps"], ["Piernas", "Core"], ["Pecho", "Hombros", "Triceps"], ["Espalda", "Biceps"], ["Piernas", "Core"]],
    "dividida por musculos": [["Pecho", "Triceps"], ["Espalda", "Biceps"], ["Piernas"], ["Hombros", "Core"], ["Cardio", "Movilidad"]],
}


@dataclass
class RecommendationInput:
    goal: str
    experience_level: str
    days_per_week: int
    session_duration: int
    equipment_available: str
    limitations: str
    preferences: str
    avoid_exercises: str
    lagging_muscles: str
    routine_preference: str


def _choose_split(data: RecommendationInput) -> str:
    if data.routine_preference and data.routine_preference != "sin preferencia":
        return data.routine_preference
    if data.experience_level == "principiante" or data.days_per_week <= 3:
        return "full body"
    if data.days_per_week == 4:
        return "torso/pierna"
    if data.days_per_week >= 5:
        return "push/pull/legs"
    return "full body"


def _goal_params(goal: str) -> dict[str, str]:
    if goal == "fuerza":
        return {"sets": "3-5", "reps": "3-6", "rest": "2-4 min", "intensity": "RPE 7-9"}
    if goal == "hipertrofia":
        return {"sets": "3-4", "reps": "6-15", "rest": "60-120 s", "intensity": "RPE 7-9"}
    if goal == "perdida de grasa":
        return {"sets": "2-4", "reps": "8-15", "rest": "45-90 s", "intensity": "RPE 6-8"}
    if goal == "recomposicion corporal":
        return {"sets": "3-4", "reps": "6-12", "rest": "60-150 s", "intensity": "RPE 7-8"}
    return {"sets": "2-3", "reps": "8-12", "rest": "60-120 s", "intensity": "RPE 6-8"}


def _recent_muscle_counter(db: Session, user: User) -> Counter[str]:
    since = date.today() - timedelta(days=21)
    sessions = (
        db.scalars(
            select(WorkoutSession)
            .where(WorkoutSession.user_id == user.id, WorkoutSession.date >= since)
            .options(joinedload(WorkoutSession.exercises).joinedload(WorkoutExercise.exercise))
        )
        .unique()
        .all()
    )
    counter: Counter[str] = Counter()
    for session in sessions:
        for workout_exercise in session.exercises:
            counter[workout_exercise.exercise.primary_muscle] += 1
    return counter


def _exercise_matches_equipment(exercise: Exercise, equipment_text: str) -> bool:
    if not equipment_text:
        return True
    exercise_equipment = (exercise.equipment or "").lower()
    equipment = equipment_text.lower()
    if "gimnasio completo" in equipment:
        return True
    return any(token.strip() and token.strip() in equipment for token in exercise_equipment.splitlines())


def _select_exercises(
    exercises: list[Exercise],
    muscles: list[str],
    equipment: str,
    avoid: str,
    max_items: int,
    short_session: bool,
) -> list[Exercise]:
    avoid_lower = avoid.lower()
    selected: list[Exercise] = []
    for muscle in muscles:
        candidates = [
            exercise
            for exercise in exercises
            if exercise.primary_muscle == muscle
            and exercise.name.lower() not in avoid_lower
            and _exercise_matches_equipment(exercise, equipment)
        ]
        candidates.sort(key=lambda item: (item.exercise_type != "compuesto", item.name))
        for exercise in candidates:
            if exercise not in selected:
                selected.append(exercise)
                break
    if not short_session and len(selected) < max_items:
        for exercise in exercises:
            if len(selected) >= max_items:
                break
            if exercise in selected or exercise.name.lower() in avoid_lower:
                continue
            if exercise.primary_muscle in muscles and _exercise_matches_equipment(exercise, equipment):
                selected.append(exercise)
    return selected[:max_items]


def build_recommendation(db: Session, user: User, data: RecommendationInput) -> dict[str, Any]:
    split = _choose_split(data)
    params = _goal_params(data.goal)
    all_exercises = list(db.scalars(select(Exercise).order_by(Exercise.exercise_type, Exercise.name)).all())
    recent_counter = _recent_muscle_counter(db, user)
    lagging = [item.strip() for item in data.lagging_muscles.split(",") if item.strip()]
    short_session = data.session_duration <= 45
    max_items = 4 if short_session else 6
    day_templates = MUSCLE_BY_SPLIT.get(split, MUSCLE_BY_SPLIT["full body"])
    days = []

    for index in range(max(1, min(data.days_per_week, 6))):
        muscles = list(day_templates[index % len(day_templates)])
        if lagging and index < len(lagging) and lagging[index] not in muscles:
            muscles.append(lagging[index])
        selected = _select_exercises(
            all_exercises,
            muscles,
            data.equipment_available,
            data.avoid_exercises,
            max_items=max_items,
            short_session=short_session,
        )
        exercises = []
        for exercise in selected:
            adjusted_sets = params["sets"]
            if recent_counter[exercise.primary_muscle] == 0 and exercise.primary_muscle in lagging:
                adjusted_sets = "3-5"
            exercises.append(
                {
                    "name": exercise.name,
                    "primary_muscle": exercise.primary_muscle,
                    "sets": adjusted_sets,
                    "reps": params["reps"],
                    "rest": params["rest"],
                    "intensity": params["intensity"],
                    "notes": "Prioriza tecnica estable y deja 1-3 repeticiones en recamara.",
                }
            )
        days.append({"name": f"Dia {index + 1}", "focus": ", ".join(muscles), "exercises": exercises})

    if data.goal == "fuerza":
        progression = "Cuando completes todas las series con buena tecnica, sube 2,5-5 kg en basicos o 1-2 kg en accesorios."
    elif data.goal == "hipertrofia":
        progression = "Usa doble progresion: primero sube repeticiones dentro del rango y despues aumenta el peso."
    else:
        progression = "Mantiene el esfuerzo moderado, aumenta volumen gradualmente y combina con pasos o cardio suave."

    explanation = (
        f"Se recomienda una estructura {split} porque encaja con {data.days_per_week} dias, "
        f"nivel {data.experience_level} y objetivo de {data.goal}. "
        "La seleccion prioriza ejercicios compuestos si el tiempo por sesion es limitado."
    )
    if data.limitations.strip():
        explanation += " Se han incluido advertencias para revisar molestias o limitaciones antes de cargar."

    return {
        "split": split,
        "days": days,
        "progression": progression,
        "safety_notes": (
            "Esta recomendacion no sustituye asesoramiento medico ni fisioterapeutico. "
            "Si tienes lesiones, enfermedad, dolor persistente o dudas tecnicas, consulta con un profesional cualificado."
        ),
        "explanation": explanation,
    }


def suggest_next_training(db: Session, user: User) -> str:
    data = RecommendationInput(
        goal=user.goal,
        experience_level=user.experience_level,
        days_per_week=user.days_per_week,
        session_duration=user.session_duration,
        equipment_available=user.equipment_available or "",
        limitations=user.limitations or "",
        preferences="",
        avoid_exercises="",
        lagging_muscles="",
        routine_preference="sin preferencia",
    )
    return _choose_split(data).title()
