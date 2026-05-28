from datetime import date

from pydantic import BaseModel, Field


class UserProfileInput(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    age: int | None = Field(default=None, ge=12, le=100)
    sex: str | None = None
    height_cm: float | None = Field(default=None, ge=80, le=260)
    body_weight_kg: float | None = Field(default=None, ge=20, le=350)
    experience_level: str = "principiante"
    goal: str = "salud general"
    days_per_week: int = Field(default=3, ge=1, le=7)
    session_duration: int = Field(default=60, ge=15, le=240)
    limitations: str | None = None
    equipment_available: str | None = None


class ExerciseRead(BaseModel):
    id: int
    name: str
    primary_muscle: str
    secondary_muscles: str | None = None
    exercise_type: str
    equipment: str | None = None
    recommended_level: str
    instructions: str
    common_errors: str | None = None
    technique_tips: str | None = None
    image_url: str | None = None
    source: str | None = None
    safety_notes: str | None = None

    class Config:
        from_attributes = True


class ExerciseSetInput(BaseModel):
    set_number: int = Field(ge=1)
    weight: float = Field(ge=0)
    reps: int = Field(ge=0)
    rpe: float | None = Field(default=None, ge=1, le=10)
    rest_seconds: int | None = Field(default=None, ge=0, le=1200)
    notes: str | None = None


class WorkoutSessionInput(BaseModel):
    date: date
    notes: str | None = None
