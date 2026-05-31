# ARCA Gym

Aplicacion web local para registrar entrenamientos de gimnasio, consultar una biblioteca inicial de ejercicios, seguir estadisticas basicas y generar rutinas recomendadas mediante reglas internas.

## Stack

- FastAPI
- Jinja2, HTML, CSS y JavaScript simple
- SQLite
- SQLAlchemy
- Chart.js para graficos
- Modo local de usuario unico, sin autenticacion

## Instalacion

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Puedes editar `.env` para cambiar la ruta de la base de datos o activar futuras fuentes externas opcionales.

## Ejecucion

Opcion rapida en Windows:

```powershell
.\iniciar_arcagym.bat
```

Este script libera el puerto `5990` si ya esta ocupado, arranca el servidor y abre el navegador cuando la aplicacion responde.

Opcion manual:

```powershell
uvicorn app.main:app --host 127.0.0.1 --port 5990 --reload
```

Abre:

```text
http://127.0.0.1:5990
```

La base `arcagym.db` se crea automaticamente en el primer arranque y se carga con ejercicios iniciales desde `app/seed/exercises_seed.json`.

## Funcionalidades incluidas

- Modo local sin login, usando un perfil unico editable.
- Perfil editable con objetivo, nivel, disponibilidad, limitaciones y equipamiento.
- Biblioteca local de ejercicios con instrucciones, errores, consejos y seguridad.
- Creacion, edicion y eliminacion de entrenamientos.
- Registro de ejercicios, series, peso, repeticiones, RPE, descanso y notas.
- Historial de sesiones.
- Estadisticas con volumen semanal, sesiones por semana, volumen por ejercicio, distribucion muscular, ejercicios mas entrenados, records personales y 1RM estimado con Epley.
- Recomendaciones de rutina por reglas segun objetivo, nivel, dias, tiempo, equipamiento, limitaciones y preferencias.
- Equipamiento real de la biblioteca agrupado por Maquinas, Pesas, Peso corporal y Complementos al generar recomendaciones.
- Guardado y edicion de rutinas recomendadas como plantillas reutilizables.
- Registro de sesiones desde una rutina guardada y su dia planificado.
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
- Permitir adjuntar imagenes propias o integrar una fuente abierta validada.
- Exportar entrenamientos y estadisticas a CSV.
