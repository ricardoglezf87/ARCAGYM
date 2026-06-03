from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import BodyMeasurement, User


MEASUREMENT_FIELDS = [
    {"key": "weight_kg", "label": "Peso", "unit": "kg", "precision": 1},
    {"key": "chest_cm", "label": "Pecho", "unit": "cm", "precision": 1},
    {"key": "waist_cm", "label": "Cintura", "unit": "cm", "precision": 1},
    {"key": "hip_cm", "label": "Cadera", "unit": "cm", "precision": 1},
    {"key": "thigh_cm", "label": "Muslos", "unit": "cm", "precision": 1},
    {"key": "arm_cm", "label": "Brazos", "unit": "cm", "precision": 1},
    {"key": "body_fat_percent", "label": "Porcentaje de grasa", "unit": "%", "precision": 1},
]

DERIVED_FIELDS = [
    {"key": "bmi", "label": "IMC calculado", "unit": "", "precision": 1},
    {"key": "fat_mass_kg", "label": "Masa grasa calculada", "unit": "kg", "precision": 1},
    {"key": "lean_mass_kg", "label": "Masa magra calculada", "unit": "kg", "precision": 1},
    {"key": "waist_hip_ratio", "label": "Cintura/cadera calculada", "unit": "", "precision": 2},
]


def _round_value(value: float, precision: int) -> float:
    return round(float(value), precision)


def get_measurements(db: Session, user: User) -> list[BodyMeasurement]:
    return list(
        db.scalars(
            select(BodyMeasurement)
            .where(BodyMeasurement.user_id == user.id)
            .order_by(BodyMeasurement.date, BodyMeasurement.id)
        ).all()
    )


def calculated_values(measurement: BodyMeasurement, user: User) -> dict[str, float]:
    values: dict[str, float] = {}
    height_m = (user.height_cm or 0) / 100

    if measurement.weight_kg is not None and height_m > 0:
        values["bmi"] = measurement.weight_kg / (height_m * height_m)

    if measurement.weight_kg is not None and measurement.body_fat_percent is not None:
        fat_mass = measurement.weight_kg * (measurement.body_fat_percent / 100)
        values["fat_mass_kg"] = fat_mass
        values["lean_mass_kg"] = measurement.weight_kg - fat_mass

    if measurement.waist_cm and measurement.hip_cm:
        values["waist_hip_ratio"] = measurement.waist_cm / measurement.hip_cm

    return values


def _format_values(measurement: BodyMeasurement) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    for field in MEASUREMENT_FIELDS:
        raw_value = getattr(measurement, field["key"])
        if raw_value is None:
            continue
        values.append(
            {
                "key": field["key"],
                "label": field["label"],
                "value": _round_value(raw_value, field["precision"]),
                "unit": field["unit"],
            }
        )
    return values


def _format_derived(measurement: BodyMeasurement, user: User) -> list[dict[str, Any]]:
    calculated = calculated_values(measurement, user)
    values: list[dict[str, Any]] = []
    for field in DERIVED_FIELDS:
        raw_value = calculated.get(field["key"])
        if raw_value is None:
            continue
        values.append(
            {
                "key": field["key"],
                "label": field["label"],
                "value": _round_value(raw_value, field["precision"]),
                "unit": field["unit"],
            }
        )
    return values


def _chart_for_field(records: list[BodyMeasurement], field: dict[str, Any]) -> dict[str, Any] | None:
    points = []
    for record in records:
        raw_value = getattr(record, field["key"])
        if raw_value is None:
            continue
        points.append(
            {
                "date": record.date.isoformat(),
                "value": _round_value(raw_value, field["precision"]),
            }
        )

    if not points:
        return None

    return {
        "key": field["key"],
        "label": field["label"],
        "unit": field["unit"],
        "labels": [point["date"] for point in points],
        "values": [point["value"] for point in points],
        "points": points,
    }


def _chart_for_derived(records: list[BodyMeasurement], user: User, field: dict[str, Any]) -> dict[str, Any] | None:
    points = []
    for record in records:
        raw_value = calculated_values(record, user).get(field["key"])
        if raw_value is None:
            continue
        points.append(
            {
                "date": record.date.isoformat(),
                "value": _round_value(raw_value, field["precision"]),
            }
        )

    if not points:
        return None

    return {
        "key": field["key"],
        "label": field["label"],
        "unit": field["unit"],
        "labels": [point["date"] for point in points],
        "values": [point["value"] for point in points],
        "points": points,
    }


def _trend_items(charts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items = []
    for chart in charts:
        if len(chart["points"]) < 2:
            continue
        first = chart["points"][0]["value"]
        last = chart["points"][-1]["value"]
        delta = round(last - first, 2)
        items.append(
            {
                "key": chart["key"],
                "label": chart["label"],
                "unit": chart["unit"],
                "first": first,
                "last": last,
                "delta": delta,
            }
        )
    return items


def _summary_card(charts_by_key: dict[str, dict[str, Any]], key: str, fallback_label: str) -> dict[str, Any]:
    chart = charts_by_key.get(key)
    if not chart:
        return {"label": fallback_label, "value": None, "unit": "", "date": None}
    point = chart["points"][-1]
    return {
        "label": chart["label"],
        "value": point["value"],
        "unit": chart["unit"],
        "date": point["date"],
    }


def build_measurement_stats(db: Session, user: User) -> dict[str, Any]:
    records = get_measurements(db, user)

    measured_charts = [
        chart
        for chart in (_chart_for_field(records, field) for field in MEASUREMENT_FIELDS)
        if chart is not None
    ]
    derived_charts = [
        chart
        for chart in (_chart_for_derived(records, user, field) for field in DERIVED_FIELDS)
        if chart is not None
    ]
    charts = measured_charts + derived_charts
    charts_by_key = {chart["key"]: chart for chart in charts}
    chart_sections = [
        {"title": "Medidas introducidas", "charts": measured_charts},
        {"title": "Valores calculados", "charts": derived_charts},
    ]

    rows = [
        {
            "id": record.id,
            "date": record.date.isoformat(),
            "measures": _format_values(record),
            "derived": _format_derived(record, user),
            "notes": record.notes,
        }
        for record in reversed(records)
    ]

    return {
        "rows": rows,
        "charts": charts,
        "chart_sections": chart_sections,
        "summary_cards": [
            _summary_card(charts_by_key, "weight_kg", "Peso"),
            _summary_card(charts_by_key, "bmi", "IMC calculado"),
            _summary_card(charts_by_key, "body_fat_percent", "Porcentaje de grasa"),
            _summary_card(charts_by_key, "waist_cm", "Cintura"),
        ],
        "trends": _trend_items(charts),
        "has_records": bool(records),
        "has_charts": bool(charts),
        "has_height": bool(user.height_cm),
    }
