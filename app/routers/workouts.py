from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.datastructures import FormData
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.dependencies import require_user, templates
from app.models import Exercise, ExerciseSet, User, WorkoutExercise, WorkoutSession


router = APIRouter()


def _get_user_session(db: Session, user: User, session_id: int) -> WorkoutSession:
    session = (
        db.scalars(
            select(WorkoutSession)
            .where(WorkoutSession.id == session_id, WorkoutSession.user_id == user.id)
            .options(
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


@router.get("/workouts")
def workout_history(request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)):
    sessions = (
        db.scalars(
            select(WorkoutSession)
            .where(WorkoutSession.user_id == user.id)
            .options(
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
def new_workout(request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        "workout_form.html",
        {
            "request": request,
            "user": user,
            "session": None,
            "exercises": _exercise_options(db),
            "today": date.today().isoformat(),
            "mode": "create",
        },
    )


@router.post("/workouts/new")
async def create_workout(request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)):
    form = await request.form()
    session_date, notes, entries, error = _parse_workout_form(form, db)
    if error:
        return templates.TemplateResponse(
            "workout_form.html",
            {
                "request": request,
                "user": user,
                "session": None,
                "exercises": _exercise_options(db),
                "today": str(form.get("date") or date.today().isoformat()),
                "mode": "create",
                "error": error,
            },
            status_code=400,
        )

    session = WorkoutSession(user_id=user.id, date=session_date, notes=notes)
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
        {
            "request": request,
            "user": user,
            "session": session,
            "exercises": _exercise_options(db),
            "today": date.today().isoformat(),
            "mode": "edit",
        },
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
    if error:
        return templates.TemplateResponse(
            "workout_form.html",
            {
                "request": request,
                "user": user,
                "session": session,
                "exercises": _exercise_options(db),
                "today": date.today().isoformat(),
                "mode": "edit",
                "error": error,
            },
            status_code=400,
        )

    session.date = session_date
    session.notes = notes
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
