-- Import de medidas desde G:/Mi unidad/Musica/Riko Wave/body.txt
-- Usuario destino: local@arcagym.app
-- Mapeo usado:
--   Peso -> weight_kg
--   Pecho relajado -> chest_cm
--   Abdomen -> waist_cm
--   Cadera -> hip_cm
--   Muslo izquierdo -> thigh_cm
--   Biceps relajado izquierdo -> arm_cm
--   Porcentaje de grasa -> body_fat_percent
--   Gluteos y Altura se guardan en notes porque no hay columna especifica.
--
-- Es idempotente por fecha: si ya existe una fila de body_measurements para
-- ese usuario y esa fecha, no inserta otra.

BEGIN TRANSACTION;

WITH target_user(id) AS (
    SELECT id
    FROM users
    WHERE email = 'local@arcagym.app'
    ORDER BY id
    LIMIT 1
),
data(measure_date, weight_kg, chest_cm, waist_cm, hip_cm, thigh_cm, arm_cm, neck_cm, body_fat_percent, notes) AS (
    VALUES
    ('2017-10-14', 88, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL),
    ('2020-02-13', 91, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL),
    ('2020-09-21', 81, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL),
    ('2021-10-26', 83.9, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL),
    ('2024-04-01', 88.9, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL),
    ('2024-08-12', 91, 105, 109, 100, 43.5, 26.5, NULL, 27.7, 'Datos extra no mapeados: Gluteos: 105 cm; Altura: 174 cm'),
    ('2024-09-09', 88.1, 105, 106, 99, 41.5, 28, NULL, 25.6, 'Datos extra no mapeados: Gluteos: 105 cm; Altura: 174 cm'),
    ('2024-10-03', 88.4, 105, 102, 97, 42.5, 26.5, NULL, 26, 'Datos extra no mapeados: Gluteos: 104 cm; Altura: 174 cm'),
    ('2024-10-07', 87.5, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL),
    ('2024-10-14', 87.1, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL),
    ('2024-10-16', 88, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL),
    ('2024-10-25', 86.6, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL),
    ('2024-10-28', 86.3, 104.5, 102, 95, 43, 26, NULL, 25, 'Datos extra no mapeados: Gluteos: 102 cm'),
    ('2024-11-15', 86, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL),
    ('2024-11-19', 87, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL),
    ('2024-11-20', 86.3, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL),
    ('2024-11-21', 85.6, 102, 103.5, 96, 41.5, 26, NULL, 24.6, 'Datos extra no mapeados: Gluteos: 102 cm'),
    ('2024-12-09', 84.5, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL),
    ('2024-12-17', 85.7, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL),
    ('2024-12-18', 85.9, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL),
    ('2024-12-23', 86.1, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL),
    ('2024-12-31', 85.1, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL),
    ('2025-01-10', 86.4, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL),
    ('2025-01-31', 85, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL),
    ('2025-02-23', 83, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL),
    ('2025-03-28', 85, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL)
)
INSERT INTO body_measurements (
    user_id,
    date,
    weight_kg,
    chest_cm,
    waist_cm,
    hip_cm,
    thigh_cm,
    arm_cm,
    neck_cm,
    body_fat_percent,
    notes
)
SELECT
    target_user.id,
    data.measure_date,
    data.weight_kg,
    data.chest_cm,
    data.waist_cm,
    data.hip_cm,
    data.thigh_cm,
    data.arm_cm,
    data.neck_cm,
    data.body_fat_percent,
    data.notes
FROM target_user
CROSS JOIN data
WHERE NOT EXISTS (
    SELECT 1
    FROM body_measurements AS existing
    WHERE existing.user_id = target_user.id
      AND existing.date = data.measure_date
);

COMMIT;
