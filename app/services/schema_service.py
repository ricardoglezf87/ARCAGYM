from sqlalchemy import Engine, inspect, text


WORKOUT_SESSION_SCHEMA_COLUMNS = {
    "saved_routine_id": "INTEGER",
    "routine_day_name": "VARCHAR(120)",
}

DIET_ENTRY_SCHEMA_COLUMNS = {
    "amount_source": "VARCHAR(40)",
    "inference_note": "TEXT",
}


def ensure_schema_upgrades(engine: Engine) -> None:
    inspector = inspect(engine)
    table_names = inspector.get_table_names()

    pending_alters: list[tuple[str, str, str]] = []
    if "workout_sessions" in table_names:
        existing_columns = {column["name"] for column in inspector.get_columns("workout_sessions")}
        pending_alters.extend(
            ("workout_sessions", column_name, ddl_type)
            for column_name, ddl_type in WORKOUT_SESSION_SCHEMA_COLUMNS.items()
            if column_name not in existing_columns
        )

    if "diet_entries" in table_names:
        existing_columns = {column["name"] for column in inspector.get_columns("diet_entries")}
        pending_alters.extend(
            ("diet_entries", column_name, ddl_type)
            for column_name, ddl_type in DIET_ENTRY_SCHEMA_COLUMNS.items()
            if column_name not in existing_columns
        )

    if not pending_alters:
        return

    with engine.begin() as connection:
        for table_name, column_name, ddl_type in pending_alters:
            connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl_type}"))
