from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import BodyMeasurement, ClinicalAnalysis, ClinicalResult, ClinicalVariable, User


FATTY_LIVER_INDEX_SOURCE = "https://pmc.ncbi.nlm.nih.gov/articles/PMC1636651/"
DISTANT_BODY_MEASUREMENT_DAYS = 90


def get_clinical_variables(db: Session) -> list[ClinicalVariable]:
    return list(
        db.scalars(
            select(ClinicalVariable)
            .where(ClinicalVariable.is_active.is_(True))
            .order_by(ClinicalVariable.sort_order, ClinicalVariable.category, ClinicalVariable.name)
        ).all()
    )


def get_clinical_analyses(db: Session, user: User) -> list[ClinicalAnalysis]:
    return list(
        db.scalars(
            select(ClinicalAnalysis)
            .where(ClinicalAnalysis.user_id == user.id)
            .options(
                selectinload(ClinicalAnalysis.results).selectinload(ClinicalResult.variable)
            )
            .order_by(ClinicalAnalysis.date, ClinicalAnalysis.id)
        ).all()
    )


def _normalized_text(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    return normalized.encode("ascii", "ignore").decode("ascii").strip().lower()


def _clean_unit(value: str | None) -> str:
    return (value or "").strip().replace("µ", "u").replace("μ", "u")


def normalize_numeric_unit(value: float, unit: str | None) -> tuple[float, str]:
    cleaned = _clean_unit(unit)
    key = cleaned.replace(" ", "").lower()

    if key in {"10^9/l", "10^3/ul"}:
        return value, "10^3/uL"
    if key == "/ul":
        return value / 1000, "10^3/uL"
    if key in {"10^12/l", "10^6/ul"}:
        return value, "10^6/uL"
    if key in {"uui/ml", "mcui/ml"}:
        return value, "uUI/mL"
    if key in {"ug/dl", "mcg/dl"}:
        return value, "ug/dL"
    return value, cleaned or "Sin unidad"


def _display_number(value: float | None, precision: int = 3) -> int | float | None:
    if value is None:
        return None
    rounded = round(float(value), precision)
    if rounded.is_integer():
        return int(rounded)
    return rounded


def _parse_reference_number(value: str) -> float:
    return float(value.replace(",", "."))


def reference_limits(reference: str | None) -> dict[str, float | None] | None:
    reference = (reference or "").strip()
    if not reference or reference == "-":
        return None
    range_match = re.search(
        r"(-?\d+(?:[.,]\d+)?)\s*-\s*(-?\d+(?:[.,]\d+)?)",
        reference,
    )
    if range_match:
        return {
            "lower": _parse_reference_number(range_match.group(1)),
            "upper": _parse_reference_number(range_match.group(2)),
        }

    limit_match = re.search(r"(<=|>=|<|>)\s*(-?\d+(?:[.,]\d+)?)", reference)
    if not limit_match:
        return None
    operator, raw_limit = limit_match.groups()
    limit = _parse_reference_number(raw_limit)
    return {
        "lower": limit if operator in {">", ">="} else None,
        "upper": limit if operator in {"<", "<="} else None,
    }


def reference_status(result: ClinicalResult) -> str | None:
    reference = (result.reference or "").strip()
    if not reference or reference == "-":
        return None

    if result.numeric_value is None:
        if _normalized_text(reference) == "negativo":
            return "normal" if _normalized_text(result.text_value) == "negativo" else "attention"
        return None

    limits = reference_limits(reference)
    if limits is None:
        return None
    numeric = float(result.numeric_value)
    low = limits["lower"]
    high = limits["upper"]
    if low is not None and numeric < low:
        return "low"
    if high is not None and numeric > high:
        return "high"
    return "normal"


def _result_display(result: ClinicalResult) -> str:
    if result.numeric_value is not None:
        value = _display_number(result.numeric_value)
        return f"{value} {result.unit}".strip() if result.unit else str(value)
    return (result.text_value or "-").strip()


def _find_numeric_result(analysis: ClinicalAnalysis, names: set[str]) -> ClinicalResult | None:
    for result in analysis.results:
        if result.numeric_value is None:
            continue
        if _normalized_text(result.variable.name) in names:
            return result
    return None


def _nearest_measurement(
    measurements: list[BodyMeasurement],
    analysis_date: date,
    predicate,
) -> BodyMeasurement | None:
    candidates = [measurement for measurement in measurements if predicate(measurement)]
    if not candidates:
        return None
    nearest = min(
        candidates,
        key=lambda measurement: (
            abs((measurement.date - analysis_date).days),
            measurement.date > analysis_date,
            -measurement.date.toordinal(),
        ),
    )
    return nearest


def calculate_fatty_liver_index(
    analysis: ClinicalAnalysis,
    user: User,
    measurements: list[BodyMeasurement],
) -> dict[str, Any]:
    reported_result = _find_numeric_result(analysis, {"indice higado graso fli"})
    if reported_result is not None:
        reported_value = float(reported_result.numeric_value)
        if reported_value < 30:
            classification = "Bajo"
        elif reported_value < 60:
            classification = "Intermedio"
        else:
            classification = "Alto"
        return {
            "value": _display_number(reported_value, 1),
            "classification": classification,
            "calculation_type": "reported",
            "measurement_distance_days": None,
            "measurement_warning": False,
            "missing": [],
            "components": [
                {
                    "label": "FLI informado",
                    "value": _display_number(reported_value, 1),
                    "unit": reported_result.unit or "",
                    "source": f"Analitica {analysis.date.isoformat()}",
                }
            ],
        }

    triglycerides_result = _find_numeric_result(analysis, {"trigliceridos"})
    ggt_result = _find_numeric_result(analysis, {"ggt"})
    bmi_result = _find_numeric_result(analysis, {"imc"})
    waist_result = _find_numeric_result(analysis, {"cintura"})

    components: dict[str, dict[str, Any]] = {}
    if triglycerides_result is not None:
        components["triglycerides"] = {
            "label": "Trigliceridos",
            "value": float(triglycerides_result.numeric_value),
            "unit": triglycerides_result.unit or "mg/dL",
            "source": f"Analitica {analysis.date.isoformat()}",
        }
    if ggt_result is not None:
        components["ggt"] = {
            "label": "GGT",
            "value": float(ggt_result.numeric_value),
            "unit": ggt_result.unit or "U/L",
            "source": f"Analitica {analysis.date.isoformat()}",
        }
    if bmi_result is not None:
        components["bmi"] = {
            "label": "IMC",
            "value": float(bmi_result.numeric_value),
            "unit": bmi_result.unit or "kg/m2",
            "source": f"Analitica {analysis.date.isoformat()}",
        }
    if waist_result is not None:
        components["waist"] = {
            "label": "Cintura",
            "value": float(waist_result.numeric_value),
            "unit": waist_result.unit or "cm",
            "source": f"Analitica {analysis.date.isoformat()}",
        }

    if "bmi" not in components and user.height_cm:
        measurement = _nearest_measurement(
            measurements,
            analysis.date,
            lambda item: item.weight_kg is not None,
        )
        if measurement is not None:
            height_m = user.height_cm / 100
            distance_days = abs((measurement.date - analysis.date).days)
            components["bmi"] = {
                "label": "IMC",
                "value": measurement.weight_kg / (height_m * height_m),
                "unit": "kg/m2",
                "source": f"Medidas {measurement.date.isoformat()} ({distance_days} dias)",
                "distance_days": distance_days,
            }

    if "waist" not in components:
        measurement = _nearest_measurement(
            measurements,
            analysis.date,
            lambda item: item.waist_cm is not None,
        )
        if measurement is not None:
            distance_days = abs((measurement.date - analysis.date).days)
            components["waist"] = {
                "label": "Cintura",
                "value": float(measurement.waist_cm),
                "unit": "cm",
                "source": f"Medidas {measurement.date.isoformat()} ({distance_days} dias)",
                "distance_days": distance_days,
            }

    measurement_distance_days = max(
        (component.get("distance_days", 0) for component in components.values()),
        default=0,
    )
    measurement_warning = measurement_distance_days > DISTANT_BODY_MEASUREMENT_DAYS

    required = ["triglycerides", "ggt", "bmi", "waist"]
    missing = [
        {"key": key, "label": {"triglycerides": "Trigliceridos", "ggt": "GGT", "bmi": "IMC", "waist": "Cintura"}[key]}
        for key in required
        if key not in components
    ]
    if missing:
        return {
            "value": None,
            "classification": None,
            "calculation_type": None,
            "measurement_distance_days": measurement_distance_days,
            "measurement_warning": measurement_warning,
            "missing": missing,
            "components": list(components.values()),
        }

    triglycerides = components["triglycerides"]["value"]
    ggt = components["ggt"]["value"]
    bmi = components["bmi"]["value"]
    waist = components["waist"]["value"]
    if triglycerides <= 0 or ggt <= 0 or bmi <= 0 or waist <= 0:
        return {
            "value": None,
            "classification": None,
            "calculation_type": None,
            "measurement_distance_days": measurement_distance_days,
            "measurement_warning": measurement_warning,
            "missing": [{"key": "invalid", "label": "Valores positivos validos"}],
            "components": list(components.values()),
        }

    score = (
        0.953 * math.log(triglycerides)
        + 0.139 * bmi
        + 0.718 * math.log(ggt)
        + 0.053 * waist
        - 15.745
    )
    if score >= 0:
        index_value = 100 / (1 + math.exp(-score))
    else:
        exp_score = math.exp(score)
        index_value = 100 * exp_score / (1 + exp_score)

    if index_value < 30:
        classification = "Bajo"
    elif index_value < 60:
        classification = "Intermedio"
    else:
        classification = "Alto"
    return {
        "value": round(index_value, 1),
        "classification": classification,
        "calculation_type": "calculated",
        "measurement_distance_days": measurement_distance_days,
        "measurement_warning": measurement_warning,
        "missing": [],
        "components": [
            {**component, "value": _display_number(component["value"], 2)}
            for component in components.values()
        ],
    }


def _normalized_points(results: list[ClinicalResult]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for result in results:
        if result.numeric_value is None:
            continue
        value, unit = normalize_numeric_unit(float(result.numeric_value), result.unit)
        groups[unit].append(
            {
                "date": result.analysis.date.isoformat(),
                "value": value,
                "result": result,
            }
        )
    for points in groups.values():
        points.sort(key=lambda point: (point["date"], point["result"].id))
    return groups


def _unit_summary(unit: str, points: list[dict[str, Any]]) -> dict[str, Any]:
    values = [point["value"] for point in points]
    return {
        "unit": unit,
        "count": len(values),
        "min": _display_number(min(values)),
        "average": _display_number(sum(values) / len(values)),
        "max": _display_number(max(values)),
    }


def _preferred_group(
    variable: ClinicalVariable,
    groups: dict[str, list[dict[str, Any]]],
) -> tuple[str | None, list[dict[str, Any]]]:
    if not groups:
        return None, []
    if variable.default_unit:
        _, default_unit = normalize_numeric_unit(1, variable.default_unit)
        if default_unit in groups:
            return default_unit, groups[default_unit]
    unit, points = max(groups.items(), key=lambda item: len(item[1]))
    return unit, points


def _variable_stat(variable: ClinicalVariable, results: list[ClinicalResult]) -> dict[str, Any]:
    ordered = sorted(results, key=lambda result: (result.analysis.date, result.id))
    latest = ordered[-1] if ordered else None
    groups = _normalized_points(ordered)
    preferred_unit, preferred_points = _preferred_group(variable, groups)
    summary = _unit_summary(preferred_unit, preferred_points) if preferred_unit else None
    comparable_count = len(preferred_points) if groups else len(ordered)
    return {
        "id": variable.id,
        "category": variable.category,
        "name": variable.name,
        "value_type": variable.value_type,
        "count": len(ordered),
        "comparable_count": comparable_count,
        "unit": preferred_unit or variable.default_unit or "",
        "reference": (latest.reference if latest else None) or variable.default_reference,
        "latest": _result_display(latest) if latest else "-",
        "latest_date": latest.analysis.date.isoformat() if latest else None,
        "latest_status": reference_status(latest) if latest else None,
        "min": summary["min"] if summary else None,
        "average": summary["average"] if summary else None,
        "max": summary["max"] if summary else None,
        "has_multiple_units": len(groups) > 1,
    }


def _selected_variable_detail(
    variable: ClinicalVariable,
    results: list[ClinicalResult],
) -> dict[str, Any]:
    ordered = sorted(results, key=lambda result: (result.analysis.date, result.id))
    groups = _normalized_points(ordered)
    labels = sorted({point["date"] for points in groups.values() for point in points})
    datasets = []
    for unit, points in sorted(groups.items()):
        values_by_date = {point["date"]: _display_number(point["value"]) for point in points}
        datasets.append(
            {
                "label": unit,
                "values": [values_by_date.get(label) for label in labels],
            }
        )

    reference_result = next(
        (
            result
            for result in reversed(ordered)
            if result.numeric_value is not None and reference_limits(result.reference) is not None
        ),
        None,
    )
    reference = (
        reference_result.reference if reference_result is not None else variable.default_reference
    )
    reference_unit = reference_result.unit if reference_result is not None else variable.default_unit
    limits = reference_limits(reference)
    reference_lines: list[dict[str, Any]] = []
    if limits is not None:
        has_range = limits["lower"] is not None and limits["upper"] is not None
        for kind in ("lower", "upper"):
            raw_value = limits[kind]
            if raw_value is None:
                continue
            normalized_value, normalized_unit = normalize_numeric_unit(raw_value, reference_unit)
            label = (
                ("Limite inferior" if kind == "lower" else "Limite superior")
                if has_range
                else ("Referencia minima" if kind == "lower" else "Referencia maxima")
            )
            reference_lines.append(
                {
                    "kind": kind,
                    "label": label,
                    "value": _display_number(normalized_value),
                    "unit": normalized_unit,
                    "reference": reference,
                }
            )
    text_history = [
        {
            "date": result.analysis.date.isoformat(),
            "value": _result_display(result),
            "reference": result.reference,
            "status": reference_status(result),
        }
        for result in reversed(ordered)
        if result.numeric_value is None
    ]
    return {
        "id": variable.id,
        "category": variable.category,
        "name": variable.name,
        "labels": labels,
        "datasets": datasets,
        "reference_lines": reference_lines,
        "reference": reference,
        "unit_summaries": [_unit_summary(unit, points) for unit, points in sorted(groups.items())],
        "text_history": text_history,
        "has_numeric": bool(datasets),
    }


def _analysis_row(
    analysis: ClinicalAnalysis,
    category: str | None,
    fatty_liver_index: dict[str, Any],
) -> dict[str, Any]:
    results = sorted(
        (
            result
            for result in analysis.results
            if not category or result.variable.category == category
        ),
        key=lambda result: (result.variable.category, result.variable.sort_order, result.variable.name),
    )
    categories = Counter(result.variable.category for result in results)
    return {
        "id": analysis.id,
        "date": analysis.date.isoformat(),
        "notes": analysis.notes,
        "source": analysis.source,
        "result_count": len(results),
        "categories": [{"name": name, "count": count} for name, count in sorted(categories.items())],
        "results": [
            {
                "category": result.variable.category,
                "name": result.variable.name,
                "value": _result_display(result),
                "unit": result.unit,
                "reference": result.reference,
                "status": reference_status(result),
            }
            for result in results
        ],
        "fatty_liver_index": fatty_liver_index,
    }


def build_clinical_dashboard(
    db: Session,
    user: User,
    category: str | None = None,
    variable_id: int | None = None,
) -> dict[str, Any]:
    variables = get_clinical_variables(db)
    analyses = get_clinical_analyses(db, user)
    measurements = list(
        db.scalars(
            select(BodyMeasurement)
            .where(BodyMeasurement.user_id == user.id)
            .order_by(BodyMeasurement.date, BodyMeasurement.id)
        ).all()
    )

    categories = sorted({variable.category for variable in variables})
    valid_category = category if category in categories else None
    visible_variables = [
        variable for variable in variables if not valid_category or variable.category == valid_category
    ]
    results_by_variable: dict[int, list[ClinicalResult]] = defaultdict(list)
    all_results: list[ClinicalResult] = []
    for analysis in analyses:
        for result in analysis.results:
            results_by_variable[result.variable_id].append(result)
            all_results.append(result)

    variable_stats = [
        _variable_stat(variable, results_by_variable.get(variable.id, []))
        for variable in visible_variables
    ]
    variable_stats.sort(key=lambda item: (-item["count"], item["category"], item["name"]))

    selected_variable = next(
        (variable for variable in variables if variable.id == variable_id),
        None,
    )
    selected_detail = (
        _selected_variable_detail(
            selected_variable,
            results_by_variable.get(selected_variable.id, []),
        )
        if selected_variable
        else None
    )

    fli_by_analysis_id = {
        analysis.id: calculate_fatty_liver_index(analysis, user, measurements)
        for analysis in analyses
    }
    analysis_rows = [
        _analysis_row(analysis, valid_category, fli_by_analysis_id[analysis.id])
        for analysis in reversed(analyses)
    ]
    if valid_category:
        analysis_rows = [row for row in analysis_rows if row["result_count"]]

    latest_fli = next(
        (
            {"date": analysis.date.isoformat(), **fli_by_analysis_id[analysis.id]}
            for analysis in reversed(analyses)
            if fli_by_analysis_id[analysis.id]["value"] is not None
        ),
        None,
    )
    return {
        "categories": categories,
        "selected_category": valid_category,
        "variables": variables,
        "visible_variables": visible_variables,
        "variable_stats": variable_stats,
        "selected_variable": selected_detail,
        "analysis_rows": analysis_rows,
        "latest_fli": latest_fli,
        "summary": {
            "analyses": len(analyses),
            "results": len(all_results),
            "variables_with_data": len(results_by_variable),
            "latest_date": analyses[-1].date.isoformat() if analyses else None,
        },
        "has_analyses": bool(analyses),
        "fli_source": FATTY_LIVER_INDEX_SOURCE,
        "distant_body_measurement_days": DISTANT_BODY_MEASUREMENT_DAYS,
    }
