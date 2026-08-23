import unittest

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, selectinload

from app.database import Base
from app.models import SavedRoutine, SavedRoutineDay, User
from app.services.exercise_seed_service import seed_exercises
from app.services.local_routine_service import (
    DUMBBELL_ROUTINE_TITLE,
    ROUTINE_TITLE,
    ensure_personal_routine,
)


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

    def test_dumbbell_days_keep_the_machine_routine_muscle_groups(self):
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

            for machine_day, dumbbell_day in zip(machine_days, dumbbell_days, strict=True):
                self.assertEqual(
                    [exercise.primary_muscle for exercise in machine_day.exercises],
                    [exercise.primary_muscle for exercise in dumbbell_day.exercises],
                )
                self.assertTrue(
                    all("Mancuernas" in (exercise.exercise.equipment or "") for exercise in dumbbell_day.exercises)
                )


if __name__ == "__main__":
    unittest.main()
