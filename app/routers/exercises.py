from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_user, templates
from app.models import Exercise, User
from app.services.external_sources_service import ExternalSourcesService
from app.services.stats_service import get_filter_options


router = APIRouter()


@router.get("/exercises")
def exercise_library(
    request: Request,
    q: str = "",
    muscle: str = "",
    exercise_type: str = "",
    level: str = "",
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    query = select(Exercise).order_by(Exercise.primary_muscle, Exercise.name)
    if q.strip():
        query = query.where(Exercise.name.ilike(f"%{q.strip()}%"))
    if muscle:
        query = query.where(Exercise.primary_muscle == muscle)
    if exercise_type:
        query = query.where(Exercise.exercise_type == exercise_type)
    if level:
        query = query.where(Exercise.recommended_level == level)

    exercises = db.scalars(query).all()
    options = get_filter_options(db)
    external_results = ExternalSourcesService().search_exercises(q)
    types = sorted({exercise.exercise_type for exercise in db.scalars(select(Exercise)).all()})
    levels = sorted({exercise.recommended_level for exercise in db.scalars(select(Exercise)).all()})

    return templates.TemplateResponse(
        "exercises.html",
        {
            "request": request,
            "user": user,
            "exercises": exercises,
            "muscles": options["muscles"],
            "types": types,
            "levels": levels,
            "filters": {"q": q, "muscle": muscle, "exercise_type": exercise_type, "level": level},
            "external_results": external_results,
        },
    )


@router.get("/exercises/{exercise_id}")
def exercise_detail(
    request: Request,
    exercise_id: int,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    exercise = db.get(Exercise, exercise_id)
    if not exercise:
        raise HTTPException(status_code=404, detail="Ejercicio no encontrado")
    return templates.TemplateResponse(
        "exercise_detail.html",
        {"request": request, "user": user, "exercise": exercise},
    )
