import json
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.datastructures import FormData
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_user, templates
from app.models import BodyMeasurement, User
from app.services.measurement_service import MEASUREMENT_FIELDS, build_measurement_stats


router = APIRouter()


def _float_or_none(value: object) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(str(value).replace(",", "."))
    except ValueError:
        return None


def _parse_measurement_form(form: FormData) -> tuple[date | None, dict[str, float | None], str | None, str | None]:
    try:
        measurement_date = date.fromisoformat(str(form.get("date")))
    except ValueError:
        return None, {}, None, "La fecha no es valida."

    values: dict[str, float | None] = {}
    for field in MEASUREMENT_FIELDS:
        value = _float_or_none(form.get(field["key"]))
        if value is None:
            values[field["key"]] = None
            continue
        if field["key"] == "body_fat_percent":
            if value < 0 or value > 100:
                return measurement_date, values, None, "El porcentaje de grasa debe estar entre 0 y 100."
        elif value <= 0:
            return measurement_date, values, None, f"{field['label']} debe ser mayor que 0."
        values[field["key"]] = value

    if not any(value is not None for value in values.values()):
        return measurement_date, values, None, "Anade al menos una medida."

    return measurement_date, values, str(form.get("notes") or "").strip() or None, None


def _context(
    request: Request,
    user: User,
    db: Session,
    error: str | None = None,
    form_values: dict[str, object] | None = None,
):
    stats = build_measurement_stats(db, user)
    return {
        "request": request,
        "user": user,
        "fields": MEASUREMENT_FIELDS,
        "stats": stats,
        "stats_json": json.dumps({"charts": stats["charts"]}),
        "today": date.today().isoformat(),
        "error": error,
        "form_values": form_values or {},
    }


@router.get("/measurements")
def measurements(request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)):
    return templates.TemplateResponse("measurements.html", _context(request, user, db))


@router.post("/measurements")
async def create_measurement(
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    form = await request.form()
    measurement_date, values, notes, error = _parse_measurement_form(form)
    if error:
        return templates.TemplateResponse(
            "measurements.html",
            _context(request, user, db, error=error, form_values=dict(form)),
            status_code=400,
        )

    measurement = BodyMeasurement(
        user_id=user.id,
        date=measurement_date,
        notes=notes,
        **values,
    )
    db.add(measurement)
    db.commit()
    return RedirectResponse("/measurements?saved=1", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/measurements/{measurement_id}/delete")
def delete_measurement(
    measurement_id: int,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    measurement = db.scalar(
        select(BodyMeasurement).where(
            BodyMeasurement.id == measurement_id,
            BodyMeasurement.user_id == user.id,
        )
    )
    if not measurement:
        raise HTTPException(status_code=404, detail="Medida no encontrada")
    db.delete(measurement)
    db.commit()
    return RedirectResponse("/measurements", status_code=status.HTTP_303_SEE_OTHER)
