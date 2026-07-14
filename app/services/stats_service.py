from collections import Counter, defaultdict
from datetime import date, timedelta
from typing import Any

from sqlalchemy import distinct, func, select
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
    muscle_weekly_volume: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    muscle_total_volume: Counter[str] = Counter()
    exercise_progress: dict[str, list[dict[str, Any]]] = defaultdict(list)
    prs: dict[str, dict[str, Any]] = {}
    total_volume = 0.0
    record_count = 0
    set_count = 0

    for session in sessions:
        week_key = f"{session.date.isocalendar().year}-S{session.date.isocalendar().week:02d}"
        session_has_data = False
        for workout_exercise in session.exercises:
            exercise = workout_exercise.exercise
            if exercise_id and exercise.id != exercise_id:
                continue
            if muscle and exercise.primary_muscle != muscle:
                continue

            sets = [item for item in workout_exercise.sets if item.reps is not None]
            if not sets:
                continue

            session_has_data = True
            record_count += 1
            set_count += len(sets)
            exercise_frequency[exercise.name] += 1
            muscle_distribution[exercise.primary_muscle] += len(sets)
            best_weight = max((item.weight or 0) for item in sets)
            total_reps = sum(item.reps or 0 for item in sets)
            entry_volume = sum((item.weight or 0) * (item.reps or 0) for item in sets)
            total_volume += entry_volume
            weekly_volume[week_key] += entry_volume
            exercise_volume[exercise.name] += entry_volume
            muscle_weekly_volume[exercise.primary_muscle][week_key] += entry_volume
            muscle_total_volume[exercise.primary_muscle] += entry_volume
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
        if session_has_data:
            weekly_sessions[week_key] += 1

    sorted_weeks = sorted(set(weekly_volume) | set(weekly_sessions))
    ordered_progress = {
        name: sorted(points, key=lambda item: item["date"])
        for name, points in exercise_progress.items()
        if points
    }
    selected_progress_name = ""
    selected_progress_points: list[dict[str, Any]] = []
    if ordered_progress:
        if exercise_id:
            selected_progress_name, selected_progress_points = next(iter(ordered_progress.items()))
        else:
            selected_progress_name, selected_progress_points = max(
                ordered_progress.items(),
                key=lambda item: (len(item[1]), sum(point["volume"] for point in item[1])),
            )

    exercise_progression_rows = []
    for name, points in ordered_progress.items():
        if len(points) < 2:
            continue
        first = points[0]
        last = points[-1]
        exercise_progression_rows.append(
            {
                "name": name,
                "sessions": len(points),
                "first_date": first["date"],
                "last_date": last["date"],
                "first_1rm": first["estimated_1rm"],
                "last_1rm": last["estimated_1rm"],
                "delta_1rm": round(last["estimated_1rm"] - first["estimated_1rm"], 2),
                "delta_volume": round(last["volume"] - first["volume"], 2),
                "delta_best_weight": round(last["best_weight"] - first["best_weight"], 2),
            }
        )
    exercise_progression_rows.sort(
        key=lambda item: (abs(item["delta_1rm"]), abs(item["delta_volume"])),
        reverse=True,
    )

    top_muscles = [item[0] for item in muscle_total_volume.most_common(6)]
    muscle_progression_datasets = [
        {
            "label": muscle_name,
            "values": [
                round(muscle_weekly_volume[muscle_name].get(week, 0), 2)
                for week in sorted_weeks
            ],
        }
        for muscle_name in top_muscles
    ]
    muscle_progression_summary = []
    for dataset in muscle_progression_datasets:
        non_zero_values = [
            (week, value)
            for week, value in zip(sorted_weeks, dataset["values"])
            if value > 0
        ]
        if not non_zero_values:
            continue
        first_week, first_value = non_zero_values[0]
        last_week, last_value = non_zero_values[-1]
        muscle_progression_summary.append(
            {
                "name": dataset["label"],
                "first_week": first_week,
                "last_week": last_week,
                "first_volume": first_value,
                "last_volume": last_value,
                "delta_volume": round(last_value - first_value, 2),
            }
        )

    return {
        "total_volume": round(total_volume, 2),
        "tracked_exercises": len(ordered_progress),
        "record_count": record_count,
        "set_count": set_count,
        "summary_count_label": "Registros del ejercicio"
        if exercise_id
        else "Registros del grupo"
        if muscle
        else "Ejercicios medidos",
        "summary_count_value": record_count if exercise_id or muscle else len(ordered_progress),
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
        "selected_exercise_progress": {
            "name": selected_progress_name,
            "labels": [point["date"] for point in selected_progress_points],
            "estimated_1rm": [point["estimated_1rm"] for point in selected_progress_points],
            "volume": [point["volume"] for point in selected_progress_points],
            "best_weight": [point["best_weight"] for point in selected_progress_points],
        },
        "exercise_progression_rows": exercise_progression_rows[:10],
        "muscle_progression": {
            "labels": sorted_weeks,
            "datasets": muscle_progression_datasets,
            "summary": muscle_progression_summary,
        },
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


def get_filter_options(db: Session, user: User) -> dict[str, Any]:
    exercise_rows = db.execute(
        select(Exercise, func.count(distinct(WorkoutExercise.id)).label("record_count"))
        .join(WorkoutExercise, WorkoutExercise.exercise_id == Exercise.id)
        .join(WorkoutSession, WorkoutSession.id == WorkoutExercise.session_id)
        .join(ExerciseSet, ExerciseSet.workout_exercise_id == WorkoutExercise.id)
        .where(WorkoutSession.user_id == user.id)
        .group_by(Exercise.id)
        .order_by(Exercise.primary_muscle, Exercise.name)
    ).all()
    exercises = [
        {
            "id": exercise.id,
            "name": exercise.name,
            "primary_muscle": exercise.primary_muscle,
            "exercise_type": exercise.exercise_type,
            "equipment": exercise.equipment,
            "record_count": record_count,
        }
        for exercise, record_count in exercise_rows
    ]

    muscle_rows = db.execute(
        select(Exercise.primary_muscle, func.count(distinct(WorkoutExercise.id)).label("record_count"))
        .join(WorkoutExercise, WorkoutExercise.exercise_id == Exercise.id)
        .join(WorkoutSession, WorkoutSession.id == WorkoutExercise.session_id)
        .join(ExerciseSet, ExerciseSet.workout_exercise_id == WorkoutExercise.id)
        .where(WorkoutSession.user_id == user.id)
        .group_by(Exercise.primary_muscle)
        .order_by(Exercise.primary_muscle)
    ).all()
    muscles = [{"name": muscle, "record_count": record_count} for muscle, record_count in muscle_rows]
    return {"exercises": exercises, "muscles": muscles}
