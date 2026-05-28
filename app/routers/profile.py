from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_user, templates
from app.models import User
from app.routers.auth import EXPERIENCE_LEVELS, GOALS


router = APIRouter()


@router.get("/profile")
def profile(request: Request, user: User = Depends(require_user)):
    return templates.TemplateResponse(
        "profile.html",
        {
            "request": request,
            "user": user,
            "experience_levels": EXPERIENCE_LEVELS,
            "goals": GOALS,
            "saved": False,
        },
    )


@router.post("/profile")
def update_profile(
    request: Request,
    name: str = Form(...),
    age: int | None = Form(None),
    sex: str | None = Form(None),
    height_cm: float | None = Form(None),
    body_weight_kg: float | None = Form(None),
    experience_level: str = Form(...),
    goal: str = Form(...),
    days_per_week: int = Form(...),
    session_duration: int = Form(...),
    limitations: str | None = Form(None),
    equipment_available: str | None = Form(None),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    user.name = name.strip()
    user.age = age
    user.sex = sex
    user.height_cm = height_cm
    user.body_weight_kg = body_weight_kg
    user.experience_level = experience_level
    user.goal = goal
    user.days_per_week = max(1, min(days_per_week, 7))
    user.session_duration = max(15, session_duration)
    user.limitations = limitations
    user.equipment_available = equipment_available
    db.add(user)
    db.commit()
    return RedirectResponse("/profile?saved=1", status_code=status.HTTP_303_SEE_OTHER)
