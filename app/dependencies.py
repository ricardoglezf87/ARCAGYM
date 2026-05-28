from fastapi import Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.options import DEFAULT_LOCAL_USER_EMAIL


templates = Jinja2Templates(directory="app/templates")


def get_or_create_local_user(db: Session) -> User:
    local_user = db.scalar(select(User).where(User.email == DEFAULT_LOCAL_USER_EMAIL))
    if local_user:
        return local_user

    users = list(db.scalars(select(User).order_by(User.id).limit(2)).all())
    if len(users) == 1:
        return users[0]

    local_user = User(
        name="Usuario Local",
        email=DEFAULT_LOCAL_USER_EMAIL,
        hashed_password="local-user",
        age=30,
        height_cm=175,
        body_weight_kg=75,
        experience_level="principiante",
        goal="salud general",
        days_per_week=3,
        session_duration=60,
        equipment_available="gimnasio completo, mancuernas, barra, maquinas, polea, peso corporal",
    )
    db.add(local_user)
    db.commit()
    db.refresh(local_user)
    return local_user


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    return get_or_create_local_user(db)


def require_user(request: Request, db: Session = Depends(get_db)) -> User:
    return get_or_create_local_user(db)


def split_lines(value: str | None) -> list[str]:
    if not value:
        return []
    return [line.strip("- ").strip() for line in value.splitlines() if line.strip()]


templates.env.filters["split_lines"] = split_lines
