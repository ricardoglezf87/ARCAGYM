import unittest
from datetime import date

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, selectinload

from app.database import Base
from app.models import (
    Exercise,
    ExerciseSet,
    SavedRoutine,
    SavedRoutineDay,
    User,
    WorkoutExercise,
    WorkoutSession,
)
from app.services.exercise_seed_service import seed_exercises
from app.services.local_routine_service import (
    DUMBBELL_ROUTINE_TITLE,
    ROUTINE_TITLE,
    ensure_personal_routine,
)
from app.services.stats_service import get_filter_options


def _user() -> User:
    return User(
        name="Prueba",
        email="routine-test@example.com",
        hashed_password="test",
        experience_level="principiante",
        goal="hipertrofia",
        days_per_week=3,
        session_duration=60,
    )


class LocalRoutineTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)

    def tearDown(self):
        self.engine.dispose()

    def _routines(self, db: Session) -> dict[str, SavedRoutine]:
        routines = db.scalars(
            select(SavedRoutine).options(
                selectinload(SavedRoutine.days)
                .selectinload(SavedRoutineDay.exercises)
            )
        ).all()
        return {routine.title: routine for routine in routines}

    def test_creates_machine_and_dumbbell_routines_idempotently(self):
        with Session(self.engine) as db:
            seed_exercises(db)
            user = _user()
            db.add(user)
            db.commit()
            db.refresh(user)

            ensure_personal_routine(db, user)
            ensure_personal_routine(db, user)

            routines = self._routines(db)
            self.assertEqual(set(routines), {ROUTINE_TITLE, DUMBBELL_ROUTINE_TITLE})
            self.assertEqual(len(routines[DUMBBELL_ROUTINE_TITLE].days), 3)
            self.assertEqual(
                [len(day.exercises) for day in routines[ROUTINE_TITLE].days],
                [9, 10, 9],
            )
            self.assertEqual(
                [len(day.exercises) for day in routines[DUMBBELL_ROUTINE_TITLE].days],
                [9, 9, 9],
            )

    def test_dumbbell_days_include_all_planned_exercises(self):
        with Session(self.engine) as db:
            seed_exercises(db)
            user = _user()
            db.add(user)
            db.commit()
            db.refresh(user)
            ensure_personal_routine(db, user)

            routines = self._routines(db)
            machine_days = routines[ROUTINE_TITLE].days
            dumbbell_days = routines[DUMBBELL_ROUTINE_TITLE].days

            self.assertEqual([len(day.exercises) for day in machine_days], [9, 10, 9])
            self.assertEqual([len(day.exercises) for day in dumbbell_days], [9, 9, 9])
            self.assertTrue(
                all(
                    "Mancuernas" in (exercise.exercise.equipment or "")
                    for day in dumbbell_days
                    for exercise in day.exercises
                )
            )

    def test_seed_updates_exercise_without_breaking_existing_workout_links(self):
        with Session(self.engine) as db:
            user = _user()
            exercise = Exercise(
                slug="press-banca-maquina",
                name="Legacy machine press",
                category_label="PECHO - COMPUESTO",
                primary_muscle="Pecho",
                exercise_type="compuesto",
                instructions="Registro anterior.",
            )
            db.add_all([user, exercise])
            db.flush()

            session = WorkoutSession(user_id=user.id, date=date(2026, 11, 9))
            db.add(session)
            db.flush()
            workout_exercise = WorkoutExercise(session_id=session.id, exercise_id=exercise.id)
            db.add(workout_exercise)
            db.flush()
            db.add(ExerciseSet(workout_exercise_id=workout_exercise.id, set_number=1, reps=10, weight=30))
            exercise_id = exercise.id
            workout_exercise_id = workout_exercise.id
            db.commit()

            seed_exercises(db)

            updated_exercise = db.get(Exercise, exercise_id)
            linked_workout_exercise = db.get(WorkoutExercise, workout_exercise_id)
            self.assertEqual(updated_exercise.slug, "press-banca-maquina")
            self.assertEqual(updated_exercise.name, "Press de banca en máquina")
            self.assertEqual(updated_exercise.category_label, "Pecho")
            self.assertEqual(linked_workout_exercise.exercise_id, exercise_id)
            options = get_filter_options(db, user)
            self.assertEqual(
                [
                    item["record_count"]
                    for item in options["exercises"]
                    if item["name"] == "Press de banca en máquina"
                ],
                [1],
            )


if __name__ == "__main__":
    unittest.main()
