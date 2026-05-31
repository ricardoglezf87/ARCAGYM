from datetime import date
import re

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.datastructures import FormData
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.dependencies import require_user, templates
from app.models import (
    Exercise,
    ExerciseSet,
    SavedRoutine,
    SavedRoutineDay,
    User,
    WorkoutExercise,
    WorkoutSession,
)


router = APIRouter()


def _get_user_session(db: Session, user: User, session_id: int) -> WorkoutSession:
    session = (
        db.scalars(
            select(WorkoutSession)
            .where(WorkoutSession.id == session_id, WorkoutSession.user_id == user.id)
            .options(
                joinedload(WorkoutSession.saved_routine),
                joinedload(WorkoutSession.exercises).joinedload(WorkoutExercise.exercise),
                joinedload(WorkoutSession.exercises).joinedload(WorkoutExercise.sets),
            )
        )
        .unique()
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Entrenamiento no encontrado")
    return session


def _float_or_none(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace(",", "."))
    except ValueError:
        return None


def _int_or_none(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _first_int(value: str | None, default: int) -> int:
    match = re.search(r"\d+", value or "")
    if not match:
        return default
    return int(match.group(0))


def _rest_seconds(value: str | None) -> int | None:
    match = re.search(r"\d+", value or "")
    if not match:
        return None
    amount = int(match.group(0))
    if "min" in (value or "").lower():
        return amount * 60
    return amount


def _parse_workout_form(form: FormData, db: Session) -> tuple[date | None, str | None, list[WorkoutExercise], str | None]:
    try:
        session_date = date.fromisoformat(str(form.get("date")))
    except ValueError:
        return None, None, [], "La fecha no es valida."

    exercise_ids = form.getlist("exercise_id")
    exercise_notes = form.getlist("exercise_notes")
    entries: list[WorkoutExercise] = []

    for index, raw_exercise_id in enumerate(exercise_ids):
        exercise_id = _int_or_none(str(raw_exercise_id))
        if not exercise_id:
            continue
        exercise = db.get(Exercise, exercise_id)
        if not exercise:
            continue

        entry = WorkoutExercise(
            exercise=exercise,
            order_index=index,
            notes=exercise_notes[index] if index < len(exercise_notes) else None,
        )
        weights = form.getlist(f"set_weight_{index}")
        reps = form.getlist(f"set_reps_{index}")
        rpes = form.getlist(f"set_rpe_{index}")
        rests = form.getlist(f"set_rest_{index}")
        notes = form.getlist(f"set_notes_{index}")

        for set_index, raw_reps in enumerate(reps):
            reps_value = _int_or_none(str(raw_reps))
            if reps_value is None or reps_value <= 0:
                continue
            weight_value = _float_or_none(str(weights[set_index])) if set_index < len(weights) else 0
            rpe_value = _float_or_none(str(rpes[set_index])) if set_index < len(rpes) else None
            rest_value = _int_or_none(str(rests[set_index])) if set_index < len(rests) else None
            if rpe_value is not None and not 1 <= rpe_value <= 10:
                rpe_value = None
            entry.sets.append(
                ExerciseSet(
                    set_number=len(entry.sets) + 1,
                    weight=max(weight_value or 0, 0),
                    reps=reps_value,
                    rpe=rpe_value,
                    rest_seconds=rest_value,
                    notes=notes[set_index] if set_index < len(notes) else None,
                )
            )

        if entry.sets:
            entries.append(entry)

    if not entries:
        return session_date, str(form.get("notes") or ""), [], "Anade al menos un ejercicio con una serie valida."
    return session_date, str(form.get("notes") or ""), entries, None


def _exercise_options(db: Session) -> list[Exercise]:
    return list(db.scalars(select(Exercise).order_by(Exercise.primary_muscle, Exercise.name)).all())


def _last_exercise_weights(db: Session, user: User, exclude_session_id: int | None = None) -> dict[int, float]:
    sessions = (
        db.scalars(
            select(WorkoutSession)
            .where(WorkoutSession.user_id == user.id)
            .options(
                joinedload(WorkoutSession.exercises).joinedload(WorkoutExercise.sets),
            )
            .order_by(WorkoutSession.date.desc(), WorkoutSession.id.desc())
        )
        .unique()
        .all()
    )
    weights: dict[int, float] = {}
    for session in sessions:
        if exclude_session_id and session.id == exclude_session_id:
            continue
        for entry in session.exercises:
            if entry.exercise_id in weights or not entry.sets:
                continue
            weights[entry.exercise_id] = entry.sets[-1].weight
    return weights


def _saved_routine_options(db: Session, user: User) -> list[SavedRoutine]:
    return list(
        db.scalars(
            select(SavedRoutine)
            .where(SavedRoutine.user_id == user.id)
            .options(joinedload(SavedRoutine.days).joinedload(SavedRoutineDay.exercises))
            .order_by(SavedRoutine.created_at.desc(), SavedRoutine.id.desc())
        )
        .unique()
        .all()
    )


def _get_saved_routine(db: Session, user: User, routine_id: int) -> SavedRoutine:
    routine = (
        db.scalars(
            select(SavedRoutine)
            .where(SavedRoutine.id == routine_id, SavedRoutine.user_id == user.id)
            .options(joinedload(SavedRoutine.days).joinedload(SavedRoutineDay.exercises))
        )
        .unique()
        .first()
    )
    if not routine:
        raise HTTPException(status_code=404, detail="Rutina guardada no encontrada")
    return routine


def _selected_routine_day(routine: SavedRoutine | None, routine_day_id: int | None) -> SavedRoutineDay | None:
    if not routine or not routine.days:
        return None
    if routine_day_id:
        for day in routine.days:
            if day.id == routine_day_id:
                return day
    return routine.days[0]


def _routine_day_entries(
    db: Session,
    routine_day: SavedRoutineDay | None,
    last_weights: dict[int, float],
) -> list[dict]:
    if not routine_day:
        return []

    entries: list[dict] = []
    for routine_exercise in routine_day.exercises:
        if not routine_exercise.exercise_id:
            continue
        exercise = db.get(Exercise, routine_exercise.exercise_id)
        if not exercise:
            continue
        set_count = max(1, min(_first_int(routine_exercise.sets, 3), 8))
        reps = max(1, _first_int(routine_exercise.reps, 10))
        rest_seconds = _rest_seconds(routine_exercise.rest)
        entries.append(
            {
                "exercise_id": exercise.id,
                "exercise": exercise,
                "notes": routine_exercise.notes or "",
                "sets": [
                    {
                        "weight": last_weights.get(exercise.id, 0),
                        "reps": reps,
                        "rpe": None,
                        "rest_seconds": rest_seconds,
                        "notes": "",
                    }
                    for _ in range(set_count)
                ],
            }
        )
    return entries


def _workout_form_context(
    request: Request,
    user: User,
    db: Session,
    session: WorkoutSession | None,
    mode: str,
    selected_routine: SavedRoutine | None = None,
    selected_day: SavedRoutineDay | None = None,
    prefill_entries: list[dict] | None = None,
    error: str | None = None,
    today: str | None = None,
) -> dict:
    return {
        "request": request,
        "user": user,
        "session": session,
        "exercises": _exercise_options(db),
        "last_weights": _last_exercise_weights(db, user, session.id if session else None),
        "saved_routines": _saved_routine_options(db, user),
        "selected_routine": selected_routine or (session.saved_routine if session else None),
        "selected_day": selected_day,
        "prefill_entries": prefill_entries or [],
        "today": today or date.today().isoformat(),
        "mode": mode,
        "error": error,
    }


def _routine_from_form(db: Session, user: User, form: FormData) -> tuple[SavedRoutine | None, str | None]:
    routine_id = _int_or_none(str(form.get("saved_routine_id") or ""))
    if not routine_id:
        return None, None
    routine = _get_saved_routine(db, user, routine_id)
    routine_day_name = str(form.get("routine_day_name") or "").strip() or None
    return routine, routine_day_name


@router.get("/workouts")
def workout_history(request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)):
    sessions = (
        db.scalars(
            select(WorkoutSession)
            .where(WorkoutSession.user_id == user.id)
            .options(
                joinedload(WorkoutSession.saved_routine),
                joinedload(WorkoutSession.exercises).joinedload(WorkoutExercise.exercise),
                joinedload(WorkoutSession.exercises).joinedload(WorkoutExercise.sets),
            )
            .order_by(WorkoutSession.date.desc(), WorkoutSession.id.desc())
        )
        .unique()
        .all()
    )
    return templates.TemplateResponse(
        "workout_history.html",
        {"request": request, "user": user, "sessions": sessions},
    )


@router.get("/workouts/new")
def new_workout(
    request: Request,
    routine_id: int | None = None,
    routine_day_id: int | None = None,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    selected_routine = _get_saved_routine(db, user, routine_id) if routine_id else None
    selected_day = _selected_routine_day(selected_routine, routine_day_id)
    last_weights = _last_exercise_weights(db, user)
    return templates.TemplateResponse(
        "workout_form.html",
        _workout_form_context(
            request,
            user,
            db,
            session=None,
            mode="create",
            selected_routine=selected_routine,
            selected_day=selected_day,
            prefill_entries=_routine_day_entries(db, selected_day, last_weights),
        ),
    )


@router.post("/workouts/new")
async def create_workout(request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)):
    form = await request.form()
    session_date, notes, entries, error = _parse_workout_form(form, db)
    selected_routine, routine_day_name = _routine_from_form(db, user, form)
    if error:
        return templates.TemplateResponse(
            "workout_form.html",
            _workout_form_context(
                request,
                user,
                db,
                session=None,
                mode="create",
                selected_routine=selected_routine,
                error=error,
                today=str(form.get("date") or date.today().isoformat()),
            ),
            status_code=400,
        )

    session = WorkoutSession(
        user_id=user.id,
        saved_routine_id=selected_routine.id if selected_routine else None,
        routine_day_name=routine_day_name,
        date=session_date,
        notes=notes,
    )
    session.exercises.extend(entries)
    db.add(session)
    db.commit()
    return RedirectResponse("/workouts", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/workouts/{session_id}/edit")
def edit_workout(
    request: Request,
    session_id: int,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    session = _get_user_session(db, user, session_id)
    return templates.TemplateResponse(
        "workout_form.html",
        _workout_form_context(request, user, db, session=session, mode="edit"),
    )


@router.post("/workouts/{session_id}/edit")
async def update_workout(
    request: Request,
    session_id: int,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    session = _get_user_session(db, user, session_id)
    form = await request.form()
    session_date, notes, entries, error = _parse_workout_form(form, db)
    selected_routine, routine_day_name = _routine_from_form(db, user, form)
    if error:
        return templates.TemplateResponse(
            "workout_form.html",
            _workout_form_context(
                request,
                user,
                db,
                session=session,
                mode="edit",
                selected_routine=selected_routine,
                error=error,
            ),
            status_code=400,
        )

    session.date = session_date
    session.notes = notes
    session.saved_routine_id = selected_routine.id if selected_routine else None
    session.routine_day_name = routine_day_name
    session.exercises.clear()
    session.exercises.extend(entries)
    db.add(session)
    db.commit()
    return RedirectResponse("/workouts", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/workouts/{session_id}/delete")
def delete_workout(
    session_id: int,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    session = _get_user_session(db, user, session_id)
    db.delete(session)
    db.commit()
    return RedirectResponse("/workouts", status_code=status.HTTP_303_SEE_OTHER)
