import re
import unicodedata

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Exercise, SavedRoutine, SavedRoutineDay, SavedRoutineExercise, User


ROUTINE_TITLE = "Rutina A/B/C - Hipertrofia máquinas"
ROUTINE_LEGACY_TITLES = ["Rutina A/B/C - Hipertrofia maquinas"]


CUSTOM_EXERCISES = [
    {
        "slug": "press-banca-maquina",
        "name": "Press de banca en máquina",
        "category_label": "PECHO - COMPUESTO",
        "primary_muscle": "Pecho",
        "secondary_muscles": ["Triceps", "Hombros anteriores"],
        "exercise_type": "Compuesto",
        "equipment": ["Maquina"],
        "recommended_level": "principiante",
        "movement_pattern": "Empuje",
        "instructions": [
            "Ajusta asiento y respaldo para que los agarres queden a la altura media del pecho.",
            "Apoya espalda y pies, y toma los agarres con munecas neutras.",
            "Empuja al frente sin bloquear los codos de forma agresiva.",
            "Vuelve controlando hasta sentir estiramiento comodo en el pecho.",
        ],
        "common_errors": [
            "Separar la espalda del respaldo.",
            "Elevar los hombros hacia las orejas.",
            "Rebotar al final del recorrido.",
        ],
        "technique_tips": [
            "Manten escapulas estables contra el respaldo.",
            "Usa un rango comodo para los hombros.",
            "Controla especialmente la vuelta.",
        ],
        "safety_notes": "Reduce carga o rango si aparece molestia anterior de hombro.",
        "image_alt": "Persona realizando press de banca en máquina",
    },
    {
        "slug": "press-inclinado-maquina",
        "name": "Press inclinado en máquina",
        "category_label": "PECHO - COMPUESTO",
        "primary_muscle": "Pecho superior",
        "secondary_muscles": ["Triceps", "Hombros anteriores"],
        "exercise_type": "Compuesto",
        "equipment": ["Maquina"],
        "recommended_level": "principiante",
        "movement_pattern": "Empuje",
        "instructions": [
            "Ajusta la maquina para que el empuje salga desde la parte alta del pecho.",
            "Apoya la espalda y fija los pies.",
            "Empuja siguiendo la trayectoria de la maquina.",
            "Baja lento hasta un rango comodo y repite.",
        ],
        "common_errors": [
            "Convertirlo en press de hombro por mala posicion.",
            "Perder contacto con el respaldo.",
            "Usar un recorrido demasiado corto.",
        ],
        "technique_tips": [
            "Manten el pecho alto.",
            "No subas los hombros al empujar.",
            "Prioriza control sobre carga.",
        ],
        "safety_notes": "Evita rangos dolorosos si notas pinzamiento de hombro.",
        "image_alt": "Persona realizando press inclinado en máquina",
    },
    {
        "slug": "press-hombro-maquina",
        "name": "Press de hombro en máquina",
        "category_label": "HOMBROS - COMPUESTO",
        "primary_muscle": "Hombros",
        "secondary_muscles": ["Triceps", "Trapecio"],
        "exercise_type": "Compuesto",
        "equipment": ["Maquina"],
        "recommended_level": "principiante",
        "movement_pattern": "Empuje",
        "instructions": [
            "Ajusta asiento para que los agarres queden cerca de la altura de los hombros.",
            "Apoya la espalda y toma los agarres.",
            "Empuja hacia arriba con control.",
            "Baja hasta un rango comodo sin perder tension.",
        ],
        "common_errors": [
            "Arquear la zona lumbar.",
            "Cerrar demasiado los codos.",
            "Bloquear arriba con brusquedad.",
        ],
        "technique_tips": [
            "Manten abdomen firme.",
            "Deja que la maquina marque la trayectoria.",
            "Evita encoger hombros al final.",
        ],
        "safety_notes": "No fuerces el rango si existe dolor de hombro o cuello.",
        "image_alt": "Persona realizando press de hombro en máquina",
    },
    {
        "slug": "pajaros-maquina",
        "name": "Pájaros en máquina",
        "category_label": "HOMBROS - AISLAMIENTO",
        "primary_muscle": "Deltoides posterior",
        "secondary_muscles": ["Espalda alta", "Trapecio medio"],
        "exercise_type": "Aislamiento",
        "equipment": ["Maquina"],
        "recommended_level": "principiante",
        "movement_pattern": "Traccion",
        "instructions": [
            "Ajusta el asiento de la peck deck inversa para alinear manos y hombros.",
            "Apoya pecho o espalda segun la maquina y toma los agarres.",
            "Abre los brazos llevando los codos hacia atras.",
            "Vuelve lento sin soltar la tension.",
        ],
        "common_errors": [
            "Usar impulso del tronco.",
            "Elevar demasiado los hombros.",
            "Convertirlo en remo.",
        ],
        "technique_tips": [
            "Usa carga moderada.",
            "Piensa en separar los brazos, no en tirar con las manos.",
            "Pausa brevemente atras.",
        ],
        "safety_notes": "Manten el movimiento controlado y sin dolor en hombros.",
        "image_alt": "Persona realizando pájaros en máquina",
    },
    {
        "slug": "crunch-maquina",
        "name": "Crunch en máquina",
        "category_label": "CORE - AISLAMIENTO",
        "primary_muscle": "Core",
        "secondary_muscles": ["Recto abdominal"],
        "exercise_type": "Aislamiento",
        "equipment": ["Maquina"],
        "recommended_level": "principiante",
        "movement_pattern": "Core",
        "instructions": [
            "Ajusta asiento y apoyos para que el eje de flexion sea comodo.",
            "Sujeta los agarres y fija la cadera.",
            "Flexiona el tronco contrayendo abdomen.",
            "Regresa lento sin relajar de golpe.",
        ],
        "common_errors": [
            "Tirar con brazos o cuello.",
            "Usar demasiada carga.",
            "Hacer el recorrido con impulso.",
        ],
        "technique_tips": [
            "Exhala al cerrar.",
            "Manten pelvis estable.",
            "Busca contraccion abdominal, no velocidad.",
        ],
        "safety_notes": "Evita cargas altas si hay molestias lumbares.",
        "image_alt": "Persona realizando crunch en máquina",
    },
    {
        "slug": "encogimientos-trapecio-maquina",
        "name": "Encogimientos para trapecio",
        "category_label": "TRAPECIO - AISLAMIENTO",
        "primary_muscle": "Trapecio",
        "secondary_muscles": ["Antebrazo"],
        "exercise_type": "Aislamiento",
        "equipment": ["Maquina", "Mancuernas"],
        "recommended_level": "principiante",
        "movement_pattern": "Traccion",
        "instructions": [
            "Colocate erguido con la carga a los lados o en la maquina.",
            "Eleva los hombros hacia arriba sin flexionar codos.",
            "Pausa un instante arriba.",
            "Baja controlando hasta estirar el trapecio.",
        ],
        "common_errors": [
            "Rotar los hombros.",
            "Doblar los codos.",
            "Inclinar el cuello hacia delante.",
        ],
        "technique_tips": [
            "Sube y baja en linea vertical.",
            "Manten cuello neutro.",
            "Usa agarre firme sin acelerar.",
        ],
        "safety_notes": "No rotes los hombros con carga si molesta el cuello.",
        "image_alt": "Persona realizando encogimientos para trapecio",
    },
    {
        "slug": "jalon-pecho-agarre-amplio",
        "name": "Jalón al pecho agarre amplio",
        "category_label": "ESPALDA - COMPUESTO",
        "primary_muscle": "Dorsal ancho",
        "secondary_muscles": ["Biceps", "Espalda alta"],
        "exercise_type": "Compuesto",
        "equipment": ["Polea", "Maquina"],
        "recommended_level": "principiante",
        "movement_pattern": "Traccion",
        "instructions": [
            "Ajusta el apoyo de muslos y toma la barra con agarre amplio.",
            "Inclina ligeramente el torso hacia atras manteniendo pecho alto.",
            "Tira llevando los codos hacia abajo y atras.",
            "Sube controlando sin perder tension en dorsales.",
        ],
        "common_errors": [
            "Tirar detras de la nuca.",
            "Balancear el torso.",
            "Encoger los hombros al tirar.",
        ],
        "technique_tips": [
            "Inicia bajando escapulas.",
            "Piensa en llevar codos hacia las costillas.",
            "Manten munecas neutras.",
        ],
        "safety_notes": "Evita llevar la barra tras la cabeza si molesta el hombro.",
        "image_alt": "Persona realizando jalón al pecho con agarre amplio",
    },
    {
        "slug": "remo-pecho-apoyado-maquina",
        "name": "Remo pecho apoyado en máquina",
        "category_label": "ESPALDA - COMPUESTO",
        "primary_muscle": "Espalda",
        "secondary_muscles": ["Dorsal ancho", "Trapecio medio", "Biceps"],
        "exercise_type": "Compuesto",
        "equipment": ["Maquina"],
        "recommended_level": "principiante",
        "movement_pattern": "Traccion",
        "instructions": [
            "Ajusta el apoyo para que el pecho quede firme contra la almohadilla.",
            "Toma los agarres con brazos extendidos.",
            "Rema llevando codos atras sin despegar el pecho.",
            "Vuelve controlando hasta estirar la espalda.",
        ],
        "common_errors": [
            "Separar el pecho del apoyo.",
            "Tirar con impulso.",
            "Encoger hombros hacia las orejas.",
        ],
        "technique_tips": [
            "Manten el torso pegado al soporte.",
            "Pausa atras si puedes mantener control.",
            "Ajusta agarre segun comodidad de hombros.",
        ],
        "safety_notes": "Reduce carga si no puedes mantener el pecho apoyado.",
        "image_alt": "Persona realizando remo pecho apoyado en máquina",
    },
]


ROUTINE_DAYS = [
    {
        "name": "Dia A",
        "focus": "Enfasis en pecho y cuadriceps",
        "exercises": [
            ("Extension de cuadriceps en maquina", "4", "12-15"),
            ("Press de banca en maquina", "4", "8-12"),
            ("Jalon al pecho agarre cerrado", "4", "10-12"),
            ("Remo en maquina", "3", "10-12"),
            ("Aperturas en maquina contractora", "3", "12-15"),
            ("Face pull", "3", "15"),
            ("Curl martillo", "2", "10-12"),
            ("Extension de triceps en polea", "2", "12-15"),
            ("Crunch en maquina", "3", "15-20"),
        ],
    },
    {
        "name": "Dia B",
        "focus": "Enfasis en espalda y hombro",
        "exercises": [
            ("Curl femoral sentado", "3", "10-12"),
            ("Hip thrust en maquina", "3", "10-12"),
            ("Extension de cuadriceps en maquina", "3", "15"),
            ("Remo sentado en polea", "4", "10-12"),
            ("Press de hombro en maquina", "3", "8-12"),
            ("Pajaros en maquina", "3", "12-15"),
            ("Elevaciones laterales", "3", "12-15"),
            ("Curl en polea baja", "2", "10-12"),
            ("Encogimientos para trapecio", "3", "12-15"),
            ("Crunch en maquina", "3", "15-20"),
        ],
    },
    {
        "name": "Dia C",
        "focus": "Enfasis en hipertrofia general",
        "exercises": [
            ("Extension de cuadriceps en maquina", "4", "12-15"),
            ("Press inclinado en maquina", "3", "8-12"),
            ("Jalon al pecho agarre amplio", "3", "10-12"),
            ("Remo pecho apoyado en maquina", "3", "10-12"),
            ("Aperturas en maquina contractora", "2", "12-15"),
            ("Face pull", "2", "15"),
            ("Curl martillo", "2", "10-12"),
            ("Extension de triceps en polea", "2", "12-15"),
            ("Crunch en maquina", "3", "15-20"),
        ],
    },
]


def _normalize_key(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", ascii_value.lower()).strip()


def _line_text(value: str | list[str] | None) -> str | None:
    if isinstance(value, list):
        return "\n".join(item.strip() for item in value if item.strip())
    return value.strip() if isinstance(value, str) and value.strip() else None


def _exercise_values(item: dict) -> dict:
    return {
        "slug": item["slug"],
        "name": item["name"],
        "category_label": item["category_label"],
        "primary_muscle": item["primary_muscle"],
        "secondary_muscles": _line_text(item.get("secondary_muscles")),
        "exercise_type": item["exercise_type"].lower(),
        "equipment": _line_text(item.get("equipment")),
        "recommended_level": item["recommended_level"],
        "movement_pattern": item["movement_pattern"],
        "instructions": _line_text(item.get("instructions")) or "Ejecuta el ejercicio con control.",
        "common_errors": _line_text(item.get("common_errors")),
        "technique_tips": _line_text(item.get("technique_tips")),
        "image_url": None,
        "image_alt": item.get("image_alt"),
        "source": "Base local propia",
        "safety_notes": item.get("safety_notes"),
    }


def _exercise_lookup(exercises: list[Exercise]) -> dict[str, Exercise]:
    lookup: dict[str, Exercise] = {}
    for exercise in exercises:
        lookup.setdefault(_normalize_key(exercise.name), exercise)
        if exercise.slug:
            lookup.setdefault(_normalize_key(exercise.slug), exercise)
    return lookup


def _ensure_custom_exercises(db: Session) -> dict[str, Exercise]:
    exercises = list(db.scalars(select(Exercise)).all())
    lookup = _exercise_lookup(exercises)

    for item in CUSTOM_EXERCISES:
        values = _exercise_values(item)
        exercise = lookup.get(_normalize_key(values["slug"])) or lookup.get(_normalize_key(values["name"]))
        if exercise:
            for field, value in values.items():
                if getattr(exercise, field) in (None, "") and value not in (None, ""):
                    setattr(exercise, field, value)
        else:
            exercise = Exercise(**values)
            db.add(exercise)
            exercises.append(exercise)
        lookup[_normalize_key(values["name"])] = exercise
        lookup[_normalize_key(values["slug"])] = exercise

    db.flush()
    return _exercise_lookup(list(db.scalars(select(Exercise)).all()))


def ensure_personal_routine(db: Session, user: User) -> SavedRoutine | None:
    exercise_lookup = _ensure_custom_exercises(db)
    existing = db.scalar(
        select(SavedRoutine).where(
            SavedRoutine.user_id == user.id,
            SavedRoutine.title.in_([ROUTINE_TITLE, *ROUTINE_LEGACY_TITLES]),
        )
    )
    if existing:
        existing.title = ROUTINE_TITLE
        db.commit()
        return existing

    routine = SavedRoutine(
        user_id=user.id,
        title=ROUTINE_TITLE,
        split="A/B/C",
        goal="hipertrofia",
        experience_level=user.experience_level,
        days_per_week=3,
        session_duration=60,
        equipment_available="Maquina, Polea, Mancuernas",
        preferences="Rutina de tres dias con enfasis rotatorio en pecho, cuadriceps, espalda y hombro.",
        progression="Usa doble progresion: primero sube repeticiones dentro del rango y despues aumenta el peso.",
        safety_notes="Calienta con series ligeras y ajusta cargas si aparece dolor articular.",
        explanation="Rutina de 3 dias y unos 60 minutos por sesion, orientada a hipertrofia con maquinas y poleas.",
    )

    for day_index, day in enumerate(ROUTINE_DAYS):
        routine_day = SavedRoutineDay(order_index=day_index, name=day["name"], focus=day["focus"])
        for exercise_index, (exercise_name, sets, reps) in enumerate(day["exercises"]):
            exercise = exercise_lookup.get(_normalize_key(exercise_name))
            if not exercise:
                continue
            routine_day.exercises.append(
                SavedRoutineExercise(
                    exercise_id=exercise.id,
                    order_index=exercise_index,
                    name=exercise.name,
                    primary_muscle=exercise.primary_muscle,
                    sets=sets,
                    reps=reps,
                    rest="",
                    notes="",
                )
            )
        routine.days.append(routine_day)

    db.add(routine)
    db.commit()
    db.refresh(routine)
    return routine
