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


class Exercise(Base):
    __tablename__ = "exercises"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(160), unique=True, index=True, nullable=False)
    primary_muscle: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    secondary_muscles: Mapped[str | None] = mapped_column(Text, nullable=True)
    exercise_type: Mapped[str] = mapped_column(String(60), index=True, nullable=False)
    equipment: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommended_level: Mapped[str] = mapped_column(String(40), default="principiante", nullable=False)
    instructions: Mapped[str] = mapped_column(Text, nullable=False)
    common_errors: Mapped[str | None] = mapped_column(Text, nullable=True)
    technique_tips: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source: Mapped[str | None] = mapped_column(String(500), nullable=True)
    safety_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    workout_entries: Mapped[list["WorkoutExercise"]] = relationship(back_populates="exercise")


class WorkoutSession(Base):
    __tablename__ = "workout_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    user: Mapped[User] = relationship(back_populates="sessions")
    exercises: Mapped[list["WorkoutExercise"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="WorkoutExercise.order_index"
    )


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
