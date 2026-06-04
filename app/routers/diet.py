from datetime import date
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_user, templates
from app.models import DietEntry, DietPlan, User
from app.services.diet_service import (
    DEFAULT_DAILY_TARGETS,
    build_daily_state,
    build_recommendations,
    conversion_rows,
    entry_from_item,
    entry_rows,
    equivalence_rows,
    format_number,
    parse_meal_text,
    targets_from_plan,
)


router = APIRouter()


def _parse_date(value: object | None) -> date:
    if not value:
        return date.today()
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return date.today()


def _float_from_form(value: object | None) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(str(value).replace(",", "."))
    except ValueError:
        return None


def _meal_label(value: object | None) -> str:
    label = str(value or "").strip()
    return (label or "Comida")[:80]


def _day_entries(db: Session, user: User, selected_date: date) -> list[DietEntry]:
    return list(
        db.scalars(
            select(DietEntry)
            .where(DietEntry.user_id == user.id, DietEntry.date == selected_date)
            .order_by(DietEntry.created_at.desc(), DietEntry.id.desc())
        ).all()
    )


def _ensure_default_plan(db: Session, user: User) -> DietPlan:
    existing = db.scalar(
        select(DietPlan).where(DietPlan.user_id == user.id).order_by(DietPlan.effective_from, DietPlan.id).limit(1)
    )
    if existing:
        return existing

    plan = DietPlan(
        user_id=user.id,
        effective_from=date.today(),
        lacteos_target=DEFAULT_DAILY_TARGETS["lacteos"],
        harinas_target=DEFAULT_DAILY_TARGETS["harinas"],
        frutas_target=DEFAULT_DAILY_TARGETS["frutas"],
        verduras_target=DEFAULT_DAILY_TARGETS["verduras"],
        proteinas_target=DEFAULT_DAILY_TARGETS["proteinas"],
        grasas_target=DEFAULT_DAILY_TARGETS["grasas"],
        notes="Plan base inicial",
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


def _active_plan(db: Session, user: User, selected_date: date) -> DietPlan:
    _ensure_default_plan(db, user)
    plan = db.scalar(
        select(DietPlan)
        .where(DietPlan.user_id == user.id, DietPlan.effective_from <= selected_date)
        .order_by(DietPlan.effective_from.desc(), DietPlan.id.desc())
        .limit(1)
    )
    if plan:
        return plan
    return db.scalar(
        select(DietPlan).where(DietPlan.user_id == user.id).order_by(DietPlan.effective_from, DietPlan.id).limit(1)
    )


def _plan_rows(db: Session, user: User) -> list[dict]:
    plans = list(
        db.scalars(
            select(DietPlan).where(DietPlan.user_id == user.id).order_by(DietPlan.effective_from.desc(), DietPlan.id.desc())
        ).all()
    )
    rows = []
    for plan in plans:
        targets = targets_from_plan(plan)
        rows.append(
            {
                "id": plan.id,
                "effective_from": plan.effective_from.isoformat(),
                "notes": plan.notes,
                "summary": ", ".join(f"{key}: {format_number(targets[key])}" for key in DEFAULT_DAILY_TARGETS),
            }
        )
    return rows


def _plan_form_values(plan: DietPlan, selected_date: date, form_values: dict[str, object] | None = None) -> dict[str, object]:
    if form_values:
        return form_values
    targets = targets_from_plan(plan)
    return {
        "effective_from": selected_date.isoformat(),
        "lacteos": format_number(targets["lacteos"]),
        "harinas": format_number(targets["harinas"]),
        "frutas": format_number(targets["frutas"]),
        "verduras": format_number(targets["verduras"]),
        "proteinas": format_number(targets["proteinas"]),
        "grasas": format_number(targets["grasas"]),
        "notes": "",
    }


def _context(
    request: Request,
    user: User,
    db: Session,
    selected_date: date,
    error: str | None = None,
    plan_error: str | None = None,
    form_values: dict[str, object] | None = None,
    plan_form_values: dict[str, object] | None = None,
    batch_id: str | None = None,
) -> dict:
    entries = _day_entries(db, user, selected_date)
    active_plan = _active_plan(db, user, selected_date)
    targets = targets_from_plan(active_plan)
    state = build_daily_state(entries, targets)
    selected_batch = batch_id or request.query_params.get("batch")
    batch_entries = [entry for entry in entries if selected_batch and entry.batch_id == selected_batch]
    return {
        "request": request,
        "user": user,
        "selected_date": selected_date.isoformat(),
        "today": date.today().isoformat(),
        "active_plan": active_plan,
        "state": state,
        "entry_rows": entry_rows(entries),
        "conversion_rows": conversion_rows(batch_entries),
        "recommendations": build_recommendations(state["remaining_values"]),
        "equivalences": equivalence_rows(),
        "plan_rows": _plan_rows(db, user),
        "error": error,
        "plan_error": plan_error,
        "form_values": form_values or {},
        "plan_form_values": _plan_form_values(active_plan, selected_date, plan_form_values),
    }


@router.get("/diet")
def diet_dashboard(
    request: Request,
    date_value: str | None = None,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    selected_date = _parse_date(date_value or request.query_params.get("date"))
    return templates.TemplateResponse("diet.html", _context(request, user, db, selected_date))


@router.post("/diet/text")
async def create_diet_text_entry(
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    form = await request.form()
    selected_date = _parse_date(form.get("date"))
    meal_label = _meal_label(form.get("meal_label"))
    source_text = str(form.get("entry_text") or "").strip()

    items, messages = parse_meal_text(source_text)
    if messages or not items:
        return templates.TemplateResponse(
            "diet.html",
            _context(
                request,
                user,
                db,
                selected_date,
                error=" ".join(messages),
                form_values=dict(form),
            ),
            status_code=400,
        )

    batch_id = uuid4().hex
    for item in items:
        db.add(entry_from_item(item, user.id, selected_date, meal_label, batch_id))
    db.commit()
    return RedirectResponse(
        f"/diet?date={selected_date.isoformat()}&saved=1&batch={batch_id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/diet/plans")
async def save_diet_plan(
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    form = await request.form()
    selected_date = _parse_date(form.get("selected_date"))
    effective_from = _parse_date(form.get("effective_from"))
    values = {key: _float_from_form(form.get(key)) for key in DEFAULT_DAILY_TARGETS}

    if any(value is None or value < 0 for value in values.values()) or not any((value or 0) > 0 for value in values.values()):
        return templates.TemplateResponse(
            "diet.html",
            _context(
                request,
                user,
                db,
                selected_date,
                plan_error="Introduce raciones validas. Pueden ser decimales, pero no negativas.",
                plan_form_values=dict(form),
            ),
            status_code=400,
        )

    plan = db.scalar(
        select(DietPlan).where(DietPlan.user_id == user.id, DietPlan.effective_from == effective_from).limit(1)
    )
    if not plan:
        plan = DietPlan(user_id=user.id, effective_from=effective_from)
        db.add(plan)

    plan.lacteos_target = values["lacteos"]
    plan.harinas_target = values["harinas"]
    plan.frutas_target = values["frutas"]
    plan.verduras_target = values["verduras"]
    plan.proteinas_target = values["proteinas"]
    plan.grasas_target = values["grasas"]
    plan.notes = str(form.get("notes") or "").strip() or None
    db.commit()
    return RedirectResponse(
        f"/diet?date={effective_from.isoformat()}&plan_saved=1",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/diet/entries/{entry_id}/delete")
def delete_diet_entry(
    entry_id: int,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    entry = db.scalar(select(DietEntry).where(DietEntry.id == entry_id, DietEntry.user_id == user.id))
    if not entry:
        raise HTTPException(status_code=404, detail="Registro de dieta no encontrado")
    selected_date = entry.date
    db.delete(entry)
    db.commit()
    return RedirectResponse(f"/diet?date={selected_date.isoformat()}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/diet/reset")
async def reset_diet_day(
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    form = await request.form()
    selected_date = _parse_date(form.get("date"))
    entries = _day_entries(db, user, selected_date)
    for entry in entries:
        db.delete(entry)
    db.commit()
    return RedirectResponse(f"/diet?date={selected_date.isoformat()}", status_code=status.HTTP_303_SEE_OTHER)
