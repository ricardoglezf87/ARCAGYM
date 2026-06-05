from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.dependencies import get_or_create_local_user
from app.routers import backup, dashboard, diet, exercises, measurements, profile, recommendations, stats, workouts
from app.services.exercise_seed_service import seed_exercises
from app.services.schema_service import ensure_schema_upgrades


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    ensure_schema_upgrades(engine)
    with SessionLocal() as db:
        seed_exercises(db)
        get_or_create_local_user(db)
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(dashboard.router)
app.include_router(exercises.router)
app.include_router(workouts.router)
app.include_router(measurements.router)
app.include_router(diet.router)
app.include_router(stats.router)
app.include_router(recommendations.router)
app.include_router(profile.router)
app.include_router(backup.router)


@app.get("/")
def index():
    return RedirectResponse("/dashboard")
