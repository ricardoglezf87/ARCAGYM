import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from starlette.datastructures import FormData

from app.database import Base
from app.models import Exercise
from app.routers.workouts import _parse_workout_form


class WorkoutFormTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)

    def tearDown(self):
        self.engine.dispose()

    def test_accepts_sets_without_rest_or_notes(self):
        with Session(self.engine) as db:
            exercise = Exercise(
                name="Ejercicio de prueba",
                primary_muscle="General",
                exercise_type="compuesto",
                recommended_level="principiante",
                instructions="Realiza el ejercicio con control.",
            )
            db.add(exercise)
            db.commit()
            db.refresh(exercise)

            form = FormData(
                [
                    ("date", "2026-08-23"),
                    ("notes", "Nota general de la sesion"),
                    ("exercise_id", str(exercise.id)),
                    ("set_weight_0", "20"),
                    ("set_reps_0", "10"),
                ]
            )

            session_date, session_notes, entries, error = _parse_workout_form(form, db)

            self.assertIsNone(error)
            self.assertEqual(session_date.isoformat(), "2026-08-23")
            self.assertEqual(session_notes, "Nota general de la sesion")
            self.assertEqual(len(entries), 1)
            self.assertIsNone(entries[0].notes)
            self.assertIsNone(entries[0].sets[0].rest_seconds)
            self.assertIsNone(entries[0].sets[0].notes)


if __name__ == "__main__":
    unittest.main()
