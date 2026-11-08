import unittest
from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import Exercise, ExerciseSet, User, WorkoutExercise, WorkoutSession
from app.services.stats_service import build_stats, get_filter_options


class StatsFilterOptionsTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)

    def tearDown(self):
        self.engine.dispose()

    def test_returns_category_and_primary_muscle_filter_counts(self):
        with Session(self.engine) as db:
            user = User(name="Prueba", email="stats-test@example.com", hashed_password="test")
            exercise = Exercise(
                name="Press de prueba",
                category_label="Empuje",
                primary_muscle="Pecho",
                exercise_type="compuesto",
                instructions="Realiza el ejercicio con control.",
            )
            second_exercise = Exercise(
                name="Jalon de prueba",
                category_label="Traccion",
                primary_muscle="Espalda",
                exercise_type="compuesto",
                instructions="Realiza el ejercicio con control.",
            )
            db.add_all([user, exercise, second_exercise])
            db.flush()

            workout_session = WorkoutSession(user_id=user.id, date=date(2026, 11, 8))
            db.add(workout_session)
            db.flush()

            workout_exercise = WorkoutExercise(
                session_id=workout_session.id,
                exercise_id=exercise.id,
            )
            db.add(workout_exercise)
            db.flush()
            db.add(ExerciseSet(workout_exercise_id=workout_exercise.id, set_number=1))
            second_workout_exercise = WorkoutExercise(
                session_id=workout_session.id,
                exercise_id=second_exercise.id,
            )
            db.add(second_workout_exercise)
            db.flush()
            db.add(ExerciseSet(workout_exercise_id=second_workout_exercise.id, set_number=1))
            db.flush()

            options = get_filter_options(db, user)

            self.assertEqual(
                options["muscles"],
                [{"name": "Espalda", "record_count": 1}, {"name": "Pecho", "record_count": 1}],
            )
            self.assertEqual(
                options["categories"],
                [{"name": "Empuje", "record_count": 1}, {"name": "Traccion", "record_count": 1}],
            )
            category_options = get_filter_options(db, user, category="Empuje")
            self.assertEqual(category_options["muscles"], [{"name": "Pecho", "record_count": 1}])
            self.assertEqual(
                [item["name"] for item in category_options["exercises"]],
                ["Press de prueba"],
            )
            muscle_options = get_filter_options(db, user, muscle="Espalda")
            self.assertEqual(
                [item["name"] for item in muscle_options["exercises"]],
                ["Jalon de prueba"],
            )
            press = next(item for item in options["exercises"] if item["name"] == "Press de prueba")
            self.assertEqual(press["category_label"], "Empuje")
            self.assertEqual(build_stats(db, user, category="Empuje")["record_count"], 1)
            self.assertEqual(build_stats(db, user, muscle="Pecho")["record_count"], 1)


if __name__ == "__main__":
    unittest.main()
