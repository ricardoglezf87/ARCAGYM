import unittest
from datetime import date

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.database import Base
from app.models import (
    BodyMeasurement,
    ClinicalAnalysis,
    ClinicalResult,
    ClinicalVariable,
    User,
)
from app.routers.clinical import _entry_variables
from app.services.clinical_seed_service import seed_clinical_analyses
from app.services.clinical_service import (
    calculate_fatty_liver_index,
    normalize_numeric_unit,
    reference_limits,
    reference_status,
)


def _user() -> User:
    return User(
        name="Prueba",
        email="clinical-test@example.com",
        hashed_password="test",
        height_cm=180,
        experience_level="principiante",
        goal="salud general",
        days_per_week=3,
        session_duration=60,
    )


class ClinicalSeedTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)

    def tearDown(self):
        self.engine.dispose()

    def test_seed_is_complete_and_idempotent(self):
        with Session(self.engine) as db:
            user = _user()
            db.add(user)
            db.commit()
            db.refresh(user)

            first = seed_clinical_analyses(db, user)
            second = seed_clinical_analyses(db, user)

            self.assertEqual(first, {"variables": 139, "analyses": 23, "results": 740})
            self.assertEqual(second, {"variables": 0, "analyses": 0, "results": 0})
            self.assertEqual(db.scalar(select(func.count()).select_from(ClinicalVariable)), 139)
            self.assertEqual(db.scalar(select(func.count()).select_from(ClinicalAnalysis)), 23)
            self.assertEqual(db.scalar(select(func.count()).select_from(ClinicalResult)), 740)


class ClinicalCalculationTests(unittest.TestCase):
    def test_clinical_entry_excludes_values_sourced_from_measurements(self):
        variables = [
            ClinicalVariable(category="Antropometria", name="Cintura", value_type="numeric"),
            ClinicalVariable(category="Antropometria", name="IMC", value_type="numeric"),
            ClinicalVariable(category="Bioquimica", name="GGT", value_type="numeric"),
        ]

        self.assertEqual([variable.name for variable in _entry_variables(variables)], ["GGT"])

    def test_fatty_liver_index_prefers_a_reported_result(self):
        variable = ClinicalVariable(
            category="Bioquimica",
            name="Indice higado graso FLI",
            value_type="numeric",
        )
        analysis = ClinicalAnalysis(user_id=1, date=date(2026, 8, 18))
        analysis.results = [ClinicalResult(variable=variable, numeric_value=79)]

        result = calculate_fatty_liver_index(analysis, _user(), [])

        self.assertEqual(result["value"], 79)
        self.assertEqual(result["classification"], "Alto")
        self.assertEqual(result["calculation_type"], "reported")

    def test_fatty_liver_index_uses_the_published_formula(self):
        variables = {
            name: ClinicalVariable(category="Prueba", name=name, value_type="numeric")
            for name in ("Trigliceridos", "GGT", "IMC", "Cintura")
        }
        analysis = ClinicalAnalysis(user_id=1, date=date(2026, 8, 18))
        analysis.results = [
            ClinicalResult(variable=variables["Trigliceridos"], numeric_value=82, unit="mg/dL"),
            ClinicalResult(variable=variables["GGT"], numeric_value=29, unit="U/L"),
            ClinicalResult(variable=variables["IMC"], numeric_value=31.08, unit="kg/m2"),
            ClinicalResult(variable=variables["Cintura"], numeric_value=114, unit="cm"),
        ]

        result = calculate_fatty_liver_index(analysis, _user(), [])

        self.assertEqual(result["value"], 77.5)
        self.assertEqual(result["classification"], "Alto")
        self.assertEqual(result["calculation_type"], "calculated")
        self.assertFalse(result["missing"])

    def test_fatty_liver_index_uses_the_nearest_available_body_measurement(self):
        variables = {
            name: ClinicalVariable(category="Bioquimica", name=name, value_type="numeric")
            for name in ("Trigliceridos", "GGT")
        }
        analysis = ClinicalAnalysis(user_id=1, date=date(2026, 1, 10))
        analysis.results = [
            ClinicalResult(variable=variables["Trigliceridos"], numeric_value=100, unit="mg/dL"),
            ClinicalResult(variable=variables["GGT"], numeric_value=30, unit="U/L"),
        ]
        old_measurement = BodyMeasurement(
            user_id=1,
            date=date(2020, 1, 10),
            weight_kg=90,
            waist_cm=100,
        )

        result = calculate_fatty_liver_index(analysis, _user(), [old_measurement])

        self.assertIsNotNone(result["value"])
        self.assertGreater(result["measurement_distance_days"], 90)
        self.assertTrue(result["measurement_warning"])
        self.assertTrue(all("2020-01-10" in item["source"] for item in result["components"][2:]))

    def test_safe_blood_count_units_are_normalized(self):
        self.assertEqual(normalize_numeric_unit(3907, "/uL"), (3.907, "10^3/uL"))
        self.assertEqual(normalize_numeric_unit(3.84, "10^9/L"), (3.84, "10^3/uL"))

    def test_reference_status_supports_ranges_and_limits(self):
        high = ClinicalResult(numeric_value=64, reference="5 - 40")
        normal = ClinicalResult(numeric_value=51, reference=">40")
        negative = ClinicalResult(text_value="Negativo", reference="Negativo")

        self.assertEqual(reference_status(high), "high")
        self.assertEqual(reference_status(normal), "normal")
        self.assertEqual(reference_status(negative), "normal")

    def test_reference_limits_support_ranges_and_one_sided_values(self):
        self.assertEqual(reference_limits("0.35 - 4.94"), {"lower": 0.35, "upper": 4.94})
        self.assertEqual(reference_limits("<130 segun riesgo"), {"lower": None, "upper": 130})
        self.assertEqual(reference_limits(">=60"), {"lower": 60, "upper": None})


if __name__ == "__main__":
    unittest.main()
