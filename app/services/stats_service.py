from collections import Counter, defaultdict
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import Exercise, ExerciseSet, User, WorkoutExercise, WorkoutSession


def epley_1rm(weight: float, reps: int) -> float:
    if reps <= 0:
        return 0
    if reps == 1:
        return weight
    return weight * (1 + reps / 30)


def get_recent_sessions(db: Session, user: User, limit: int = 5) -> list[WorkoutSession]:
    return list(
        db.scalars(
            select(WorkoutSession)
            .where(WorkoutSession.user_id == user.id)
            .options(
                joinedload(WorkoutSession.exercises).joinedload(WorkoutExercise.exercise),
                joinedload(WorkoutSession.exercises).joinedload(WorkoutExercise.sets),
            )
            .order_by(WorkoutSession.date.desc(), WorkoutSession.id.desc())
            .limit(limit)
        )
        .unique()
        .all()
    )


def _session_query(db: Session, user: User, start_date: date | None = None, end_date: date | None = None):
    query = (
        select(WorkoutSession)
        .where(WorkoutSession.user_id == user.id)
        .options(
            joinedload(WorkoutSession.exercises).joinedload(WorkoutExercise.exercise),
            joinedload(WorkoutSession.exercises).joinedload(WorkoutExercise.sets),
        )
        .order_by(WorkoutSession.date)
    )
    if start_date:
        query = query.where(WorkoutSession.date >= start_date)
    if end_date:
        query = query.where(WorkoutSession.date <= end_date)
    return db.scalars(query).unique().all()


def build_stats(
    db: Session,
    user: User,
    exercise_id: int | None = None,
    muscle: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, Any]:
    sessions = _session_query(db, user, start_date, end_date)
    weekly_volume: dict[str, float] = defaultdict(float)
    weekly_sessions: Counter[str] = Counter()
    exercise_volume: Counter[str] = Counter()
    exercise_frequency: Counter[str] = Counter()
    muscle_distribution: Counter[str] = Counter()
    exercise_progress: dict[str, list[dict[str, Any]]] = defaultdict(list)
    prs: dict[str, dict[str, Any]] = {}
    total_volume = 0.0

    for session in sessions:
        week_key = f"{session.date.isocalendar().year}-S{session.date.isocalendar().week:02d}"
        weekly_sessions[week_key] += 1
        for workout_exercise in session.exercises:
            exercise = workout_exercise.exercise
            if exercise_id and exercise.id != exercise_id:
                continue
            if muscle and exercise.primary_muscle != muscle:
                continue

            sets = [item for item in workout_exercise.sets if item.reps is not None]
            if not sets:
                continue

            exercise_frequency[exercise.name] += 1
            muscle_distribution[exercise.primary_muscle] += len(sets)
            best_weight = max((item.weight or 0) for item in sets)
            total_reps = sum(item.reps or 0 for item in sets)
            entry_volume = sum((item.weight or 0) * (item.reps or 0) for item in sets)
            total_volume += entry_volume
            weekly_volume[week_key] += entry_volume
            exercise_volume[exercise.name] += entry_volume
            best_1rm = max((epley_1rm(item.weight or 0, item.reps or 0) for item in sets), default=0)

            exercise_progress[exercise.name].append(
                {
                    "date": session.date.isoformat(),
                    "best_weight": round(best_weight, 2),
                    "total_reps": total_reps,
                    "volume": round(entry_volume, 2),
                    "estimated_1rm": round(best_1rm, 2),
                }
            )

            current_pr = prs.get(exercise.name)
            if not current_pr or best_1rm > current_pr["estimated_1rm"]:
                best_set = max(sets, key=lambda item: epley_1rm(item.weight or 0, item.reps or 0))
                prs[exercise.name] = {
                    "exercise": exercise.name,
                    "date": session.date.isoformat(),
                    "weight": best_set.weight,
                    "reps": best_set.reps,
                    "estimated_1rm": round(epley_1rm(best_set.weight or 0, best_set.reps or 0), 2),
                }

    sorted_weeks = sorted(set(weekly_volume) | set(weekly_sessions))
    return {
        "total_volume": round(total_volume, 2),
        "weekly_volume": {
            "labels": sorted_weeks,
            "values": [round(weekly_volume[week], 2) for week in sorted_weeks],
        },
        "weekly_sessions": {
            "labels": sorted_weeks,
            "values": [weekly_sessions[week] for week in sorted_weeks],
        },
        "exercise_volume": {
            "labels": [item[0] for item in exercise_volume.most_common(10)],
            "values": [round(item[1], 2) for item in exercise_volume.most_common(10)],
        },
        "exercise_frequency": exercise_frequency.most_common(10),
        "muscle_distribution": {
            "labels": list(muscle_distribution.keys()),
            "values": list(muscle_distribution.values()),
        },
        "exercise_progress": dict(exercise_progress),
        "personal_records": sorted(prs.values(), key=lambda item: item["estimated_1rm"], reverse=True)[:10],
    }


def dashboard_summary(db: Session, user: User) -> dict[str, Any]:
    today = date.today()
    start = today - timedelta(days=42)
    stats = build_stats(db, user, start_date=start, end_date=today)
    recent_sessions = get_recent_sessions(db, user, limit=5)
    return {
        "stats": stats,
        "recent_sessions": recent_sessions,
        "weekly_volume": stats["weekly_volume"]["values"][-1] if stats["weekly_volume"]["values"] else 0,
        "weekly_sessions": stats["weekly_sessions"]["values"][-1] if stats["weekly_sessions"]["values"] else 0,
        "personal_records": stats["personal_records"][:5],
    }


def get_filter_options(db: Session) -> dict[str, Any]:
    exercises = db.scalars(select(Exercise).order_by(Exercise.name)).all()
    muscles = sorted({exercise.primary_muscle for exercise in exercises})
    return {"exercises": exercises, "muscles": muscles}
