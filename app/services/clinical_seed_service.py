import json
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ClinicalAnalysis, ClinicalResult, ClinicalVariable, User


SEED_PATH = Path(__file__).resolve().parents[1] / "seed" / "clinical_analyses_seed.json"


def _load_seed() -> dict[str, Any]:
    with SEED_PATH.open("r", encoding="utf-8-sig") as file:
        payload = json.load(file)
    if not isinstance(payload, dict):
        raise ValueError("El fichero inicial de analiticas no tiene un formato valido.")
    return payload


def seed_clinical_analyses(db: Session, user: User) -> dict[str, int]:
    payload = _load_seed()
    source = str(payload.get("source") or SEED_PATH.name)

    existing_variables = list(db.scalars(select(ClinicalVariable)).all())
    variables_by_identity = {
        (variable.category, variable.name): variable for variable in existing_variables
    }
    variables_by_seed_key: dict[str, ClinicalVariable] = {}
    created_variables = 0

    for item in payload.get("variables", []):
        identity = (str(item["category"]), str(item["name"]))
        variable = variables_by_identity.get(identity)
        if variable is None:
            variable = ClinicalVariable(
                category=identity[0],
                name=identity[1],
                value_type=str(item.get("value_type") or "numeric"),
                default_unit=item.get("default_unit"),
                default_reference=item.get("default_reference"),
                sort_order=int(item.get("sort_order") or 0),
                is_active=True,
            )
            db.add(variable)
            variables_by_identity[identity] = variable
            created_variables += 1
        else:
            variable.value_type = str(item.get("value_type") or variable.value_type)
            variable.default_unit = item.get("default_unit")
            variable.default_reference = item.get("default_reference")
            variable.sort_order = int(item.get("sort_order") or variable.sort_order)
            variable.is_active = True
        variables_by_seed_key[str(item["key"])] = variable

    db.flush()

    existing_analyses = list(
        db.scalars(
            select(ClinicalAnalysis).where(
                ClinicalAnalysis.user_id == user.id,
                ClinicalAnalysis.source == source,
            )
        ).all()
    )
    analyses_by_date = {analysis.date: analysis for analysis in existing_analyses}
    created_analyses = 0
    created_results = 0

    for analysis_item in payload.get("analyses", []):
        analysis_date = date.fromisoformat(str(analysis_item["date"]))
        analysis = analyses_by_date.get(analysis_date)
        if analysis is None:
            analysis = ClinicalAnalysis(
                user_id=user.id,
                date=analysis_date,
                source=source,
                notes=None,
            )
            db.add(analysis)
            db.flush()
            analyses_by_date[analysis_date] = analysis
            created_analyses += 1

        existing_variable_ids = {
            result.variable_id
            for result in db.scalars(
                select(ClinicalResult).where(ClinicalResult.analysis_id == analysis.id)
            ).all()
        }
        for result_item in analysis_item.get("results", []):
            variable = variables_by_seed_key.get(str(result_item["variable_key"]))
            if variable is None or variable.id in existing_variable_ids:
                continue
            db.add(
                ClinicalResult(
                    analysis_id=analysis.id,
                    variable_id=variable.id,
                    numeric_value=result_item.get("numeric_value"),
                    text_value=result_item.get("text_value"),
                    unit=result_item.get("unit"),
                    reference=result_item.get("reference"),
                )
            )
            existing_variable_ids.add(variable.id)
            created_results += 1

    db.commit()
    return {
        "variables": created_variables,
        "analyses": created_analyses,
        "results": created_results,
    }
