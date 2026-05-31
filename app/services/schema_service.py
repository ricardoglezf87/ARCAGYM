from sqlalchemy import Engine, inspect, text


WORKOUT_SESSION_SCHEMA_COLUMNS = {
    "saved_routine_id": "INTEGER",
    "routine_day_name": "VARCHAR(120)",
}


def ensure_schema_upgrades(engine: Engine) -> None:
    inspector = inspect(engine)
    if "workout_sessions" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("workout_sessions")}
    missing_columns = [
        (column_name, ddl_type)
        for column_name, ddl_type in WORKOUT_SESSION_SCHEMA_COLUMNS.items()
        if column_name not in existing_columns
    ]
    if not missing_columns:
        return

    with engine.begin() as connection:
        for column_name, ddl_type in missing_columns:
            connection.execute(text(f"ALTER TABLE workout_sessions ADD COLUMN {column_name} {ddl_type}"))
