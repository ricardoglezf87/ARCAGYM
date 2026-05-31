import re
import unicodedata

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.dependencies import require_user, templates
from app.models import Exercise, SavedRoutine, SavedRoutineDay, SavedRoutineExercise, User
from app.options import EXPERIENCE_LEVELS, GOALS
from app.services.recommendation_service import RecommendationInput, build_recommendation


router = APIRouter()

ROUTINE_PREFERENCES = ["sin preferencia", "full body", "torso/pierna", "push/pull/legs", "dividida por musculos"]

EQUIPMENT_GROUP_ORDER = ["Maquinas", "Pesas", "Peso corporal", "Complementos"]
EQUIPMENT_GROUPS_BY_KEY = {
    "assault bike": "Maquinas",
    "bicicleta": "Maquinas",
    "cinta": "Maquinas",
    "eliptica": "Maquinas",
    "maquina": "Maquinas",
    "polea": "Maquinas",
    "remo": "Maquinas",
    "stair climber": "Maquinas",
    "tobillera": "Maquinas",
    "banco": "Pesas",
    "banco predicador": "Pesas",
    "barra": "Pesas",
    "barra z": "Pesas",
    "kettlebell": "Pesas",
    "mancuernas": "Pesas",
    "rack": "Pesas",
    "barra de dominadas": "Peso corporal",
    "cajon": "Peso corporal",
    "cuerda": "Peso corporal",
    "paralelas": "Peso corporal",
    "pared": "Peso corporal",
    "peso corporal": "Peso corporal",
    "rueda abdominal": "Peso corporal",
    "banda elastica": "Complementos",
    "trineo": "Complementos",
}


def _normalize_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", ascii_value.lower()).strip()


def _split_equipment_text(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in re.split(r"[\n,;]+", value) if item.strip()]


def _equipment_text(equipment_items: list[str], equipment_available: str) -> str:
    selected = [item.strip() for item in equipment_items if item.strip()]
    if not selected:
        return equipment_available.strip()
    return ", ".join(dict.fromkeys(selected))


def _equipment_group(value: str) -> str:
    return EQUIPMENT_GROUPS_BY_KEY.get(_normalize_key(value), "Complementos")


def _equipment_label(value: str) -> str:
    if _normalize_key(value) == "peso corporal":
        return "Sin material"
    return value


def _equipment_groups(db: Session) -> list[dict]:
    items_by_key: dict[str, str] = {}
    for equipment_text in db.scalars(select(Exercise.equipment)).all():
        for item in _split_equipment_text(equipment_text):
            key = _normalize_key(item)
            items_by_key.setdefault(key, item)

    grouped = {group: [] for group in EQUIPMENT_GROUP_ORDER}
    for key, item in sorted(items_by_key.items(), key=lambda pair: pair[0]):
        group = _equipment_group(item)
        grouped.setdefault(group, []).append({"value": item, "label": _equipment_label(item)})

    return [
        {"name": group, "items": grouped[group]}
        for group in EQUIPMENT_GROUP_ORDER
        if grouped.get(group)
    ]


def _equipment_values(equipment_groups: list[dict]) -> list[str]:
    return [
        item["value"]
        for group in equipment_groups
        for item in group["items"]
    ]


def _exercise_options(db: Session) -> list[Exercise]:
    return list(db.scalars(select(Exercise).order_by(Exercise.primary_muscle, Exercise.name)).all())


def _equipment_defaults(equipment_text: str | None, equipment_options: list[str]) -> list[str]:
    option_by_key = {_normalize_key(option): option for option in equipment_options}
    selected: list[str] = []

    for item in _split_equipment_text(equipment_text):
        key = _normalize_key(item)
        option = option_by_key.get(key)
        if not option and key.endswith("s"):
            option = option_by_key.get(key[:-1])
        if option:
            selected.append(option)

    return list(dict.fromkeys(selected))


def _default_input(user: User) -> RecommendationInput:
    return RecommendationInput(
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


def _saved_routine_options(db: Session, user: User) -> list[SavedRoutine]:
    return list(
        db.scalars(
            select(SavedRoutine)
            .where(SavedRoutine.user_id == user.id)
            .options(joinedload(SavedRoutine.days).joinedload(SavedRoutineDay.exercises))
            .order_by(SavedRoutine.created_at.desc(), SavedRoutine.id.desc())
        )
        .unique()
        .all()
    )


def _get_saved_routine(db: Session, user: User, routine_id: int) -> SavedRoutine:
    routine = (
        db.scalars(
            select(SavedRoutine)
            .where(SavedRoutine.id == routine_id, SavedRoutine.user_id == user.id)
            .options(joinedload(SavedRoutine.days).joinedload(SavedRoutineDay.exercises))
        )
        .unique()
        .first()
    )
    if not routine:
        raise HTTPException(status_code=404, detail="Rutina guardada no encontrada")
    return routine


def _routine_to_recommendation(routine: SavedRoutine) -> dict:
    return {
        "split": routine.split,
        "days": [
            {
                "id": day.id,
                "name": day.name,
                "focus": day.focus or "",
                "exercises": [
                    {
                        "id": exercise.exercise_id,
                        "name": exercise.name,
                        "primary_muscle": exercise.primary_muscle or "",
                        "sets": exercise.sets or "",
                        "reps": exercise.reps or "",
                        "rest": exercise.rest or "",
                        "intensity": exercise.intensity or "",
                        "notes": exercise.notes or "",
                    }
                    for exercise in day.exercises
                ],
            }
            for day in routine.days
        ],
        "progression": routine.progression or "",
        "safety_notes": routine.safety_notes or "",
        "explanation": routine.explanation or "",
    }


def _template_context(request: Request, user: User, db: Session, form_values: RecommendationInput) -> dict:
    equipment_groups = _equipment_groups(db)
    selected_equipment = _equipment_defaults(form_values.equipment_available, _equipment_values(equipment_groups))
    return {
        "request": request,
        "user": user,
        "form_values": form_values,
        "experience_levels": EXPERIENCE_LEVELS,
        "goals": GOALS,
        "routine_preferences": ROUTINE_PREFERENCES,
        "equipment_groups": equipment_groups,
        "selected_equipment": selected_equipment,
        "saved_routines": _saved_routine_options(db, user),
    }


def _save_recommendation(
    db: Session,
    user: User,
    data: RecommendationInput,
    recommendation: dict,
    title: str,
) -> SavedRoutine:
    routine = SavedRoutine(
        user_id=user.id,
        title=title.strip() or f"Rutina {recommendation['split'].title()}",
        split=recommendation["split"],
        goal=data.goal,
        experience_level=data.experience_level,
        days_per_week=data.days_per_week,
        session_duration=data.session_duration,
        equipment_available=data.equipment_available,
        limitations=data.limitations,
        preferences=data.preferences,
        avoid_exercises=data.avoid_exercises,
        lagging_muscles=data.lagging_muscles,
        routine_preference=data.routine_preference,
        progression=recommendation.get("progression"),
        safety_notes=recommendation.get("safety_notes"),
        explanation=recommendation.get("explanation"),
    )
    for day_index, day in enumerate(recommendation["days"]):
        routine_day = SavedRoutineDay(
            order_index=day_index,
            name=day["name"],
            focus=day.get("focus"),
        )
        for exercise_index, exercise in enumerate(day["exercises"]):
            routine_day.exercises.append(
                SavedRoutineExercise(
                    exercise_id=exercise.get("id"),
                    order_index=exercise_index,
                    name=exercise["name"],
                    primary_muscle=exercise.get("primary_muscle"),
                    sets=exercise.get("sets"),
                    reps=exercise.get("reps"),
                    rest=exercise.get("rest"),
                    intensity=exercise.get("intensity"),
                    notes=exercise.get("notes"),
                )
            )
        routine.days.append(routine_day)

    db.add(routine)
    db.commit()
    db.refresh(routine)
    return routine


def _update_saved_routine_from_form(db: Session, routine: SavedRoutine, form) -> None:
    routine.title = str(form.get("title") or routine.title).strip() or routine.title
    routine.progression = str(form.get("progression") or "").strip() or None
    routine.safety_notes = str(form.get("safety_notes") or "").strip() or None

    for day in routine.days:
        day.name = str(form.get(f"day_name_{day.id}") or day.name).strip() or day.name
        day.focus = str(form.get(f"day_focus_{day.id}") or "").strip() or None
        exercise_ids = form.getlist(f"exercise_id_{day.id}")
        sets_values = form.getlist(f"sets_{day.id}")
        reps_values = form.getlist(f"reps_{day.id}")
        rest_values = form.getlist(f"rest_{day.id}")
        intensity_values = form.getlist(f"intensity_{day.id}")
        notes_values = form.getlist(f"notes_{day.id}")

        day.exercises.clear()
        for index, raw_exercise_id in enumerate(exercise_ids):
            try:
                exercise_id = int(str(raw_exercise_id))
            except ValueError:
                continue
            exercise = db.get(Exercise, exercise_id)
            if not exercise:
                continue
            day.exercises.append(
                SavedRoutineExercise(
                    exercise_id=exercise.id,
                    order_index=len(day.exercises),
                    name=exercise.name,
                    primary_muscle=exercise.primary_muscle,
                    sets=sets_values[index] if index < len(sets_values) else "",
                    reps=reps_values[index] if index < len(reps_values) else "",
                    rest=rest_values[index] if index < len(rest_values) else "",
                    intensity=intensity_values[index] if index < len(intensity_values) else "",
                    notes=notes_values[index] if index < len(notes_values) else "",
                )
            )


@router.get("/recommendations")
def recommendation_form(
    request: Request,
    saved: str = "",
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    context = _template_context(request, user, db, _default_input(user))
    context["saved_message"] = saved == "1"
    return templates.TemplateResponse("recommendation_form.html", context)


@router.post("/recommendations")
def recommendation_result(
    request: Request,
    goal: str = Form(...),
    experience_level: str = Form(...),
    days_per_week: int = Form(...),
    session_duration: int = Form(...),
    equipment_items: list[str] = Form(default=[]),
    equipment_available: str = Form(""),
    limitations: str = Form(""),
    preferences: str = Form(""),
    avoid_exercises: str = Form(""),
    lagging_muscles: str = Form(""),
    routine_preference: str = Form("sin preferencia"),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    data = RecommendationInput(
        goal=goal,
        experience_level=experience_level,
        days_per_week=max(1, min(days_per_week, 7)),
        session_duration=max(15, session_duration),
        equipment_available=_equipment_text(equipment_items, equipment_available),
        limitations=limitations,
        preferences=preferences,
        avoid_exercises=avoid_exercises,
        lagging_muscles=lagging_muscles,
        routine_preference=routine_preference,
    )
    recommendation = build_recommendation(db, user, data)
    return templates.TemplateResponse(
        "recommendation_result.html",
        {"request": request, "user": user, "recommendation": recommendation, "input": data},
    )


@router.post("/recommendations/edit")
def edit_recommendation_input(
    request: Request,
    goal: str = Form(...),
    experience_level: str = Form(...),
    days_per_week: int = Form(...),
    session_duration: int = Form(...),
    equipment_available: str = Form(""),
    limitations: str = Form(""),
    preferences: str = Form(""),
    avoid_exercises: str = Form(""),
    lagging_muscles: str = Form(""),
    routine_preference: str = Form("sin preferencia"),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    data = RecommendationInput(
        goal=goal,
        experience_level=experience_level,
        days_per_week=max(1, min(days_per_week, 7)),
        session_duration=max(15, session_duration),
        equipment_available=equipment_available,
        limitations=limitations,
        preferences=preferences,
        avoid_exercises=avoid_exercises,
        lagging_muscles=lagging_muscles,
        routine_preference=routine_preference,
    )
    return templates.TemplateResponse("recommendation_form.html", _template_context(request, user, db, data))


@router.post("/recommendations/save")
def save_recommendation(
    title: str = Form(""),
    goal: str = Form(...),
    experience_level: str = Form(...),
    days_per_week: int = Form(...),
    session_duration: int = Form(...),
    equipment_available: str = Form(""),
    limitations: str = Form(""),
    preferences: str = Form(""),
    avoid_exercises: str = Form(""),
    lagging_muscles: str = Form(""),
    routine_preference: str = Form("sin preferencia"),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    data = RecommendationInput(
        goal=goal,
        experience_level=experience_level,
        days_per_week=max(1, min(days_per_week, 7)),
        session_duration=max(15, session_duration),
        equipment_available=equipment_available,
        limitations=limitations,
        preferences=preferences,
        avoid_exercises=avoid_exercises,
        lagging_muscles=lagging_muscles,
        routine_preference=routine_preference,
    )
    recommendation = build_recommendation(db, user, data)
    routine = _save_recommendation(db, user, data, recommendation, title)
    return RedirectResponse(
        f"/recommendations/saved/{routine.id}?saved=1",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/recommendations/saved/{routine_id}")
def saved_routine_detail(
    request: Request,
    routine_id: int,
    saved: str = "",
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    routine = _get_saved_routine(db, user, routine_id)
    return templates.TemplateResponse(
        "saved_routine_detail.html",
        {
            "request": request,
            "user": user,
            "routine": routine,
            "recommendation": _routine_to_recommendation(routine),
            "saved_message": saved == "1",
        },
    )


@router.get("/recommendations/saved/{routine_id}/edit")
def edit_saved_routine(
    request: Request,
    routine_id: int,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    routine = _get_saved_routine(db, user, routine_id)
    return templates.TemplateResponse(
        "saved_routine_edit.html",
        {
            "request": request,
            "user": user,
            "routine": routine,
            "exercises": _exercise_options(db),
        },
    )


@router.post("/recommendations/saved/{routine_id}/edit")
async def update_saved_routine(
    request: Request,
    routine_id: int,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    routine = _get_saved_routine(db, user, routine_id)
    form = await request.form()
    _update_saved_routine_from_form(db, routine, form)
    db.add(routine)
    db.commit()
    return RedirectResponse(
        f"/recommendations/saved/{routine.id}?saved=1",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/recommendations/saved/{routine_id}/delete")
def delete_saved_routine(
    routine_id: int,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    routine = _get_saved_routine(db, user, routine_id)
    db.delete(routine)
    db.commit()
    return RedirectResponse("/recommendations", status_code=status.HTTP_303_SEE_OTHER)
