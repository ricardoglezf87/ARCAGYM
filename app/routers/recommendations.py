from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_user, templates
from app.models import User
from app.routers.auth import EXPERIENCE_LEVELS, GOALS
from app.services.recommendation_service import RecommendationInput, build_recommendation


router = APIRouter()

ROUTINE_PREFERENCES = ["sin preferencia", "full body", "torso/pierna", "push/pull/legs", "dividida por musculos"]


@router.get("/recommendations")
def recommendation_form(request: Request, user: User = Depends(require_user)):
    return templates.TemplateResponse(
        "recommendation_form.html",
        {
            "request": request,
            "user": user,
            "experience_levels": EXPERIENCE_LEVELS,
            "goals": GOALS,
            "routine_preferences": ROUTINE_PREFERENCES,
        },
    )


@router.post("/recommendations")
def recommendation_result(
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
    recommendation = build_recommendation(db, user, data)
    return templates.TemplateResponse(
        "recommendation_result.html",
        {"request": request, "user": user, "recommendation": recommendation, "input": data},
    )
