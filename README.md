# ARCA Gym

Aplicacion web local para registrar entrenamientos de gimnasio, consultar una biblioteca inicial de ejercicios, seguir estadisticas basicas y generar rutinas recomendadas mediante reglas internas.

## Stack

- FastAPI
- Jinja2, HTML, CSS y JavaScript simple
- SQLite
- SQLAlchemy
- Chart.js para graficos
- Autenticacion con sesiones y contrasenas hasheadas con PBKDF2

## Instalacion

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edita `.env` y cambia `SECRET_KEY` antes de usar datos reales.

## Ejecucion

```powershell
uvicorn app.main:app --reload
```

Abre:

```text
http://127.0.0.1:8000
```

La base `arcagym.db` se crea automaticamente en el primer arranque y se carga con ejercicios iniciales desde `app/seed/exercises_seed.json`.

## Funcionalidades incluidas

- Registro, login y logout.
- Rutas privadas protegidas por sesion.
- Datos aislados por usuario.
- Perfil editable con objetivo, nivel, disponibilidad, limitaciones y equipamiento.
- Biblioteca local de ejercicios con instrucciones, errores, consejos y seguridad.
- Creacion, edicion y eliminacion de entrenamientos.
- Registro de ejercicios, series, peso, repeticiones, RPE, descanso y notas.
- Historial de sesiones.
- Estadisticas con volumen semanal, sesiones por semana, volumen por ejercicio, distribucion muscular, ejercicios mas entrenados, records personales y 1RM estimado con Epley.
- Recomendaciones de rutina por reglas segun objetivo, nivel, dias, tiempo, equipamiento, limitaciones y preferencias.
- Capa `external_sources_service.py` preparada para futuras fuentes externas opcionales.

## Notas de seguridad

Las recomendaciones son educativas y no sustituyen consejo medico, fisioterapeutico ni de un entrenador cualificado. Si existe lesion, enfermedad, dolor o duda tecnica, consulta con un profesional.

## Estructura

```text
app/
  main.py
  config.py
  database.py
  models.py
  schemas.py
  auth.py
  dependencies.py
  routers/
  services/
  templates/
  static/
  seed/
.env.example
requirements.txt
README.md
```

## Evolucion recomendada

- Agregar Alembic cuando haya cambios de esquema en produccion.
- Anadir tests automatizados para servicios, rutas y permisos de usuario.
- Guardar rutinas recomendadas como plantillas reutilizables.
- Permitir adjuntar imagenes propias o integrar una fuente abierta validada.
- Exportar entrenamientos y estadisticas a CSV.
