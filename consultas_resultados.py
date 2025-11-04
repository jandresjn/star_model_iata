import duckdb

DB = "data/iata_star.duckdb"

q1 = r"""
-- 1) Aerolínea con más vuelos a Roma por año
WITH dest_roma AS (
  SELECT id_ciudad FROM dim_ciudad WHERE lower(nombre_ciudad) = 'roma'
),
base AS (
  SELECT f.id_tiempo, a.nombre_aerolinea
  FROM hecho_vuelos f
  JOIN dim_avion a USING (id_avion)
  JOIN dest_roma r ON f.id_ciudad_destino = r.id_ciudad
)
SELECT t.anio, nombre_aerolinea, COUNT(*) AS vuelos
FROM base b
JOIN dim_tiempo t ON b.id_tiempo = t.id_tiempo
GROUP BY 1,2
QUALIFY ROW_NUMBER() OVER (PARTITION BY t.anio ORDER BY COUNT(*) DESC) = 1
ORDER BY anio;
"""

q2 = r"""
-- 2) Recaudo por aerolínea en 1er semestre (2019 y 2020)
SELECT t.anio, a.nombre_aerolinea, SUM(f.costo) AS recaudo
FROM hecho_vuelos f
JOIN dim_avion a USING (id_avion)
JOIN dim_tiempo t ON f.id_tiempo = t.id_tiempo
WHERE t.semestre = 1 AND t.anio IN (2019, 2020)
GROUP BY 1,2
ORDER BY anio, recaudo DESC;
"""

q3 = r"""
-- 3) Modelo de avión con más vuelos por año
WITH base AS (
  SELECT t.anio, a.nombre_modelo
  FROM hecho_vuelos f
  JOIN dim_avion a USING (id_avion)
  JOIN dim_tiempo t ON f.id_tiempo = t.id_tiempo
)
SELECT anio, nombre_modelo, COUNT(*) AS vuelos
FROM base
GROUP BY 1,2
QUALIFY ROW_NUMBER() OVER (PARTITION BY anio ORDER BY COUNT(*) DESC) = 1
ORDER BY anio;
"""

q4 = r"""
-- 4) Ciudad de residencia con más viajeros por año
WITH base AS (
  SELECT t.anio, u.ciudad_residencia_nombre AS ciudad
  FROM hecho_vuelos f
  JOIN dim_usuario u USING (id_usuario)
  JOIN dim_tiempo t ON f.id_tiempo = t.id_tiempo
)
SELECT anio, ciudad, COUNT(*) AS viajes
FROM base
GROUP BY 1,2
QUALIFY ROW_NUMBER() OVER (PARTITION BY anio ORDER BY COUNT(*) DESC) = 1
ORDER BY anio;
"""

def run_query(con, title, sql):
    print(f"\n=== {title} ===")
    try:
        print(con.execute(sql).fetchdf().to_string(index=False))
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    con = duckdb.connect(DB, read_only=True)
    run_query(con, "Pregunta 1: Aerolínea líder a Roma por año", q1)
    run_query(con, "Pregunta 2: Recaudo S1 por aerolínea", q2)
    run_query(con, "Pregunta 3: Modelo líder por año", q3)
    run_query(con, "Pregunta 4: Ciudad de residencia con más viajeros por año", q4)
    con.close()
