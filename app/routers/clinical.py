import re
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.datastructures import FormData
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_user, templates
from app.models import ClinicalAnalysis, ClinicalResult, ClinicalVariable, User
from app.services.clinical_service import build_clinical_dashboard, get_clinical_variables


router = APIRouter()
NUMERIC_VALUE_PATTERN = re.compile(r"^[+-]?(?:\d+(?:[.,]\d*)?|[.,]\d+)$")


def _parse_result_value(
    raw_value: object,
    variable: ClinicalVariable,
) -> tuple[float | None, str | None]:
    value = str(raw_value or "").strip()
    if not value:
        return None, None
    if variable.value_type != "text" and NUMERIC_VALUE_PATTERN.fullmatch(value):
        return float(value.replace(",", ".")), None
    return None, value


def _entry_groups(variables: list[ClinicalVariable]) -> list[dict[str, object]]:
    groups: list[dict[str, object]] = []
    for variable in variables:
        if not groups or groups[-1]["name"] != variable.category:
            groups.append({"name": variable.category, "variables": []})
        groups[-1]["variables"].append(variable)
    return groups


def _context(
    request: Request,
    user: User,
    db: Session,
    error: str | None = None,
    form_values: dict[str, object] | None = None,
):
    category = str(request.query_params.get("category") or "").strip() or None
    raw_variable_id = str(request.query_params.get("variable") or "").strip()
    try:
        variable_id = int(raw_variable_id) if raw_variable_id else None
    except ValueError:
        variable_id = None
    dashboard = build_clinical_dashboard(
        db,
        user,
        category=category,
        variable_id=variable_id,
    )
    variables = dashboard["variables"]
    return {
        "request": request,
        "user": user,
        "dashboard": dashboard,
        "entry_groups": _entry_groups(variables),
        "today": date.today().isoformat(),
        "error": error,
        "form_values": form_values or {},
    }


@router.get("/analiticas")
def clinical_analyses(
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    return templates.TemplateResponse("clinical.html", _context(request, user, db))


@router.get("/analiticas/estadisticas")
def clinical_statistics(
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    return templates.TemplateResponse("clinical_stats.html", _context(request, user, db))


@router.post("/analiticas")
async def create_clinical_analysis(
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    form = await request.form()
    try:
        analysis_date = date.fromisoformat(str(form.get("date") or ""))
    except ValueError:
        return templates.TemplateResponse(
            "clinical.html",
            _context(request, user, db, error="La fecha no es valida.", form_values=dict(form)),
            status_code=400,
        )

    variables = get_clinical_variables(db)
    parsed_results: list[tuple[ClinicalVariable, float | None, str | None]] = []
    for variable in variables:
        numeric_value, text_value = _parse_result_value(
            form.get(f"variable_{variable.id}"),
            variable,
        )
        if numeric_value is None and text_value is None:
            continue
        parsed_results.append((variable, numeric_value, text_value))

    if not parsed_results:
        return templates.TemplateResponse(
            "clinical.html",
            _context(
                request,
                user,
                db,
                error="Anade al menos un resultado.",
                form_values=dict(form),
            ),
            status_code=400,
        )

    analysis = ClinicalAnalysis(
        user_id=user.id,
        date=analysis_date,
        notes=str(form.get("notes") or "").strip() or None,
        source="Entrada manual",
    )
    db.add(analysis)
    db.flush()
    for variable, numeric_value, text_value in parsed_results:
        db.add(
            ClinicalResult(
                analysis_id=analysis.id,
                variable_id=variable.id,
                numeric_value=numeric_value,
                text_value=text_value,
                unit=variable.default_unit,
                reference=variable.default_reference,
            )
        )
    db.commit()
    return RedirectResponse(
        f"/analiticas?saved=1&analysis_id={analysis.id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/analiticas/{analysis_id}/delete")
def delete_clinical_analysis(
    analysis_id: int,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    analysis = db.scalar(
        select(ClinicalAnalysis).where(
            ClinicalAnalysis.id == analysis_id,
            ClinicalAnalysis.user_id == user.id,
        )
    )
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analitica no encontrada")
    db.delete(analysis)
    db.commit()
    return RedirectResponse("/analiticas", status_code=status.HTTP_303_SEE_OTHER)
