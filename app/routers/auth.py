from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import hash_password, login_user, logout_user, verify_password
from app.database import get_db
from app.dependencies import current_user, templates
from app.models import User


router = APIRouter()


EXPERIENCE_LEVELS = ["principiante", "intermedio", "avanzado"]
GOALS = ["fuerza", "hipertrofia", "perdida de grasa", "salud general", "recomposicion corporal", "otro"]


@router.get("/register")
def register_form(request: Request, user: User | None = Depends(current_user)):
    if user:
        return RedirectResponse("/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(
        "register.html",
        {
            "request": request,
            "experience_levels": EXPERIENCE_LEVELS,
            "goals": GOALS,
            "form": {},
        },
    )


@router.post("/register")
def register(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    age: int | None = Form(None),
    sex: str | None = Form(None),
    height_cm: float | None = Form(None),
    body_weight_kg: float | None = Form(None),
    experience_level: str = Form("principiante"),
    goal: str = Form("salud general"),
    days_per_week: int = Form(3),
    session_duration: int = Form(60),
    limitations: str | None = Form(None),
    equipment_available: str | None = Form(None),
    db: Session = Depends(get_db),
):
    email_normalized = email.strip().lower()
    form_data = dict(locals())
    form_data.pop("db", None)
    form_data.pop("request", None)

    error = None
    if len(password) < 8:
        error = "La contrasena debe tener al menos 8 caracteres."
    elif password != password_confirm:
        error = "Las contrasenas no coinciden."
    elif db.scalar(select(User).where(User.email == email_normalized)):
        error = "Ya existe un usuario con ese email."

    if error:
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "error": error,
                "experience_levels": EXPERIENCE_LEVELS,
                "goals": GOALS,
                "form": form_data,
            },
            status_code=400,
        )

    user = User(
        name=name.strip(),
        email=email_normalized,
        hashed_password=hash_password(password),
        age=age,
        sex=sex,
        height_cm=height_cm,
        body_weight_kg=body_weight_kg,
        experience_level=experience_level,
        goal=goal,
        days_per_week=days_per_week,
        session_duration=session_duration,
        limitations=limitations,
        equipment_available=equipment_available,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    login_user(request, user.id)
    return RedirectResponse("/dashboard", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/login")
def login_form(request: Request, next: str | None = None, user: User | None = Depends(current_user)):
    if user:
        return RedirectResponse("/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse("login.html", {"request": request, "next": next or ""})


@router.post("/login")
def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    next: str | None = Form(None),
    db: Session = Depends(get_db),
):
    user = db.scalar(select(User).where(User.email == email.strip().lower()))
    if not user or not verify_password(password, user.hashed_password):
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "error": "Email o contrasena incorrectos.",
                "email": email,
                "next": next or "",
            },
            status_code=400,
        )

    login_user(request, user.id)
    redirect_to = next if next and next.startswith("/") and not next.startswith("//") else "/dashboard"
    return RedirectResponse(redirect_to, status_code=status.HTTP_303_SEE_OTHER)


@router.get("/logout")
def logout(request: Request):
    logout_user(request)
    return RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)
