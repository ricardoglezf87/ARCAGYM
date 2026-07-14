import json
from datetime import date
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_user, templates
from app.models import User
from app.services.stats_service import build_stats, get_filter_options


router = APIRouter()


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _stats_url(
    *,
    exercise_id: int | None = None,
    muscle: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> str:
    params: dict[str, str | int] = {}
    if exercise_id:
        params["exercise_id"] = exercise_id
    if muscle:
        params["muscle"] = muscle
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date
    query = urlencode(params)
    return f"/stats?{query}" if query else "/stats"


@router.get("/stats")
def stats(
    request: Request,
    exercise_id: int | None = Query(None),
    muscle: str | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    stats_data = build_stats(
        db,
        user,
        exercise_id=exercise_id,
        muscle=muscle or None,
        start_date=_parse_date(start_date),
        end_date=_parse_date(end_date),
    )
    options = get_filter_options(db, user)
    for exercise in options["exercises"]:
        exercise["url"] = _stats_url(
            exercise_id=exercise["id"],
            start_date=start_date,
            end_date=end_date,
        )
    for muscle_option in options["muscles"]:
        muscle_option["url"] = _stats_url(
            muscle=muscle_option["name"],
            start_date=start_date,
            end_date=end_date,
        )
    options["clear_url"] = _stats_url(start_date=start_date, end_date=end_date)
    return templates.TemplateResponse(
        "stats.html",
        {
            "request": request,
            "user": user,
            "stats": stats_data,
            "stats_json": json.dumps(stats_data),
            "filters": {
                "exercise_id": exercise_id,
                "muscle": muscle or "",
                "start_date": start_date or "",
                "end_date": end_date or "",
            },
            "options": options,
        },
    )
