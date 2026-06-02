from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sex: Mapped[str | None] = mapped_column(String(40), nullable=True)
    height_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    body_weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    experience_level: Mapped[str] = mapped_column(String(40), default="principiante", nullable=False)
    goal: Mapped[str] = mapped_column(String(80), default="salud general", nullable=False)
    days_per_week: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    session_duration: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    limitations: Mapped[str | None] = mapped_column(Text, nullable=True)
    equipment_available: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    sessions: Mapped[list["WorkoutSession"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    saved_routines: Mapped[list["SavedRoutine"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    body_measurements: Mapped[list["BodyMeasurement"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Exercise(Base):
    __tablename__ = "exercises"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    slug: Mapped[str | None] = mapped_column(String(180), unique=True, index=True, nullable=True)
    name: Mapped[str] = mapped_column(String(160), unique=True, index=True, nullable=False)
    category_label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    primary_muscle: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    secondary_muscles: Mapped[str | None] = mapped_column(Text, nullable=True)
    exercise_type: Mapped[str] = mapped_column(String(60), index=True, nullable=False)
    equipment: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommended_level: Mapped[str] = mapped_column(String(40), default="principiante", nullable=False)
    movement_pattern: Mapped[str | None] = mapped_column(String(80), nullable=True)
    instructions: Mapped[str] = mapped_column(Text, nullable=False)
    common_errors: Mapped[str | None] = mapped_column(Text, nullable=True)
    technique_tips: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    image_alt: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source: Mapped[str | None] = mapped_column(String(500), nullable=True)
    safety_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    workout_entries: Mapped[list["WorkoutExercise"]] = relationship(back_populates="exercise")


class WorkoutSession(Base):
    __tablename__ = "workout_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    saved_routine_id: Mapped[int | None] = mapped_column(
        ForeignKey("saved_routines.id"), index=True, nullable=True
    )
    routine_day_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    user: Mapped[User] = relationship(back_populates="sessions")
    saved_routine: Mapped["SavedRoutine | None"] = relationship(back_populates="sessions")
    exercises: Mapped[list["WorkoutExercise"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="WorkoutExercise.order_index"
    )


class SavedRoutine(Base):
    __tablename__ = "saved_routines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    split: Mapped[str] = mapped_column(String(80), nullable=False)
    goal: Mapped[str] = mapped_column(String(80), nullable=False)
    experience_level: Mapped[str] = mapped_column(String(40), nullable=False)
    days_per_week: Mapped[int] = mapped_column(Integer, nullable=False)
    session_duration: Mapped[int] = mapped_column(Integer, nullable=False)
    equipment_available: Mapped[str | None] = mapped_column(Text, nullable=True)
    limitations: Mapped[str | None] = mapped_column(Text, nullable=True)
    preferences: Mapped[str | None] = mapped_column(Text, nullable=True)
    avoid_exercises: Mapped[str | None] = mapped_column(Text, nullable=True)
    lagging_muscles: Mapped[str | None] = mapped_column(Text, nullable=True)
    routine_preference: Mapped[str | None] = mapped_column(String(80), nullable=True)
    progression: Mapped[str | None] = mapped_column(Text, nullable=True)
    safety_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    user: Mapped[User] = relationship(back_populates="saved_routines")
    days: Mapped[list["SavedRoutineDay"]] = relationship(
        back_populates="routine", cascade="all, delete-orphan", order_by="SavedRoutineDay.order_index"
    )
    sessions: Mapped[list[WorkoutSession]] = relationship(back_populates="saved_routine")


class SavedRoutineDay(Base):
    __tablename__ = "saved_routine_days"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    routine_id: Mapped[int] = mapped_column(ForeignKey("saved_routines.id"), index=True, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    focus: Mapped[str | None] = mapped_column(Text, nullable=True)

    routine: Mapped[SavedRoutine] = relationship(back_populates="days")
    exercises: Mapped[list["SavedRoutineExercise"]] = relationship(
        back_populates="day", cascade="all, delete-orphan", order_by="SavedRoutineExercise.order_index"
    )


class SavedRoutineExercise(Base):
    __tablename__ = "saved_routine_exercises"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    day_id: Mapped[int] = mapped_column(ForeignKey("saved_routine_days.id"), index=True, nullable=False)
    exercise_id: Mapped[int | None] = mapped_column(ForeignKey("exercises.id"), index=True, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    primary_muscle: Mapped[str | None] = mapped_column(String(80), nullable=True)
    sets: Mapped[str | None] = mapped_column(String(40), nullable=True)
    reps: Mapped[str | None] = mapped_column(String(40), nullable=True)
    rest: Mapped[str | None] = mapped_column(String(40), nullable=True)
    intensity: Mapped[str | None] = mapped_column(String(40), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    day: Mapped[SavedRoutineDay] = relationship(back_populates="exercises")
    exercise: Mapped[Exercise | None] = relationship()


class WorkoutExercise(Base):
    __tablename__ = "workout_exercises"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("workout_sessions.id"), index=True, nullable=False)
    exercise_id: Mapped[int] = mapped_column(ForeignKey("exercises.id"), index=True, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    session: Mapped[WorkoutSession] = relationship(back_populates="exercises")
    exercise: Mapped[Exercise] = relationship(back_populates="workout_entries")
    sets: Mapped[list["ExerciseSet"]] = relationship(
        back_populates="workout_exercise", cascade="all, delete-orphan", order_by="ExerciseSet.set_number"
    )


class ExerciseSet(Base):
    __tablename__ = "exercise_sets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    workout_exercise_id: Mapped[int] = mapped_column(
        ForeignKey("workout_exercises.id"), index=True, nullable=False
    )
    set_number: Mapped[int] = mapped_column(Integer, nullable=False)
    weight: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    reps: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rpe: Mapped[float | None] = mapped_column(Float, nullable=True)
    rest_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    workout_exercise: Mapped[WorkoutExercise] = relationship(back_populates="sets")


class BodyMeasurement(Base):
    __tablename__ = "body_measurements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    chest_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    waist_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    hip_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    thigh_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    arm_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    neck_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    body_fat_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    user: Mapped[User] = relationship(back_populates="body_measurements")
