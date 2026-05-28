from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_user, templates
from app.models import User
from app.services.recommendation_service import suggest_next_training
from app.services.stats_service import dashboard_summary


router = APIRouter()


@router.get("/dashboard")
def dashboard(request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)):
    summary = dashboard_summary(db, user)
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "summary": summary,
            "next_training": suggest_next_training(db, user),
        },
    )
