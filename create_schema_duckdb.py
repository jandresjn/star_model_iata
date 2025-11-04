import os
import duckdb
from dotenv import load_dotenv

# Cargar variables de entorno (opcional)
load_dotenv()

# Ruta del archivo DuckDB (por defecto: data/iata_star.duckdb)
DUCKDB_PATH = os.getenv("DUCKDB_PATH", "data/iata_star.duckdb")

# Crear carpeta si no existe
os.makedirs(os.path.dirname(DUCKDB_PATH), exist_ok=True)

con = duckdb.connect(DUCKDB_PATH)

con.execute("""
PRAGMA threads=4;

-- Drop-and-create para idempotencia
DROP TABLE IF EXISTS hecho_vuelos;
DROP TABLE IF EXISTS dim_tiempo;
DROP TABLE IF EXISTS dim_avion;
DROP TABLE IF EXISTS dim_ciudad;
DROP TABLE IF EXISTS dim_usuario;

-- ============================
-- Dimensiones
-- ============================

CREATE TABLE dim_tiempo (
  id_tiempo INTEGER PRIMARY KEY,
  fecha      TIMESTAMP,     -- fecha (00:00:00)
  anio       SMALLINT,
  mes        TINYINT,
  semestre   TINYINT
);

CREATE TABLE dim_avion (
  id_avion          INTEGER PRIMARY KEY,   -- del OLTP
  nombre_avion      VARCHAR,
  nombre_aerolinea  VARCHAR,               -- desnormalizado
  nombre_modelo     VARCHAR                -- desnormalizado
);

CREATE TABLE dim_ciudad (
  id_ciudad     INTEGER PRIMARY KEY,       -- del OLTP
  nombre_ciudad VARCHAR
);

CREATE TABLE dim_usuario (
  id_usuario               BIGINT PRIMARY KEY,  -- cedula del OLTP
  nombre_completo          VARCHAR,
  email                    VARCHAR,
  ciudad_residencia_nombre VARCHAR             -- desnormalizado
);

-- ============================
-- Hecho
-- ============================

CREATE TABLE hecho_vuelos (
  id_tiempo         INTEGER,   -- FK dim_tiempo
  id_avion          INTEGER,   -- FK dim_avion
  id_usuario        BIGINT,    -- FK dim_usuario
  id_ciudad_origen  INTEGER,   -- FK dim_ciudad (rol: origen)
  id_ciudad_destino INTEGER,   -- FK dim_ciudad (rol: destino)
  costo             BIGINT,    -- monto pagado
  vuelo_cnt         TINYINT    -- constante 1 para conteos
);

-- Índices para acelerar joins/where
CREATE INDEX IF NOT EXISTS idx_fact_t  ON hecho_vuelos(id_tiempo);
CREATE INDEX IF NOT EXISTS idx_fact_a  ON hecho_vuelos(id_avion);
CREATE INDEX IF NOT EXISTS idx_fact_u  ON hecho_vuelos(id_usuario);
CREATE INDEX IF NOT EXISTS idx_fact_co ON hecho_vuelos(id_ciudad_origen);
CREATE INDEX IF NOT EXISTS idx_fact_cd ON hecho_vuelos(id_ciudad_destino);
""")

con.close()
print(f"[OK] Esquema creado en: {DUCKDB_PATH}")
