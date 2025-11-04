import os
import pandas as pd
import duckdb
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# =========================
# Configuración
# =========================
load_dotenv()

# Credenciales MySQL (tienen defaults con los datos que compartiste)
MYSQL_HOST = os.getenv("MYSQL_HOST")
MYSQL_PORT = int(os.getenv("MYSQL_PORT"))
MYSQL_USER = os.getenv("MYSQL_USER")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")
MYSQL_DB = os.getenv("MYSQL_DB")

# Ruta DuckDB (debe existir el esquema creado previamente)
DUCKDB_PATH = os.getenv("DUCKDB_PATH", "data/iata_star.duckdb")

mysql_url = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}"

# =========================
# Conexiones
# =========================
print("[INFO] Conectando a MySQL…")
engine = create_engine(mysql_url)

def read_table(name: str) -> pd.DataFrame:
    with engine.connect() as conn:
        return pd.read_sql(text(f"SELECT * FROM {name}"), conn)

print("[INFO] Leyendo tablas OLTP…")
df_aerolineas  = read_table("aerolineas")
df_ciudades    = read_table("ciudades")
df_aeropuertos = read_table("aeropuertos")
df_modelos     = read_table("modelos")
df_aviones     = read_table("aviones")
df_itins       = read_table("itinerarios")
df_usuarios    = read_table("usuarios")
df_vuelos      = read_table("vuelos")

# =========================
# Limpieza / Tipos
# =========================
for col in ("fecha_salida", "fecha_llegada"):
    if col in df_itins.columns:
        df_itins[col] = pd.to_datetime(df_itins[col], errors="coerce", utc=False)

# =========================
# Construcción de dimensiones
# =========================

# --- dim_tiempo (desde fecha_salida)
df_itins["fecha_date"] = df_itins["fecha_salida"].dt.date
unique_dates = sorted(df_itins["fecha_date"].dropna().unique())
id_map = {d: i+1 for i, d in enumerate(unique_dates)}  # surrogate simple, 1..N

dim_tiempo = pd.DataFrame({
    "id_tiempo": [id_map[d] for d in unique_dates],
    "fecha": pd.to_datetime(unique_dates),  # 00:00:00
})
dim_tiempo["anio"] = dim_tiempo["fecha"].dt.year.astype("Int64")
dim_tiempo["mes"] = dim_tiempo["fecha"].dt.month.astype("Int64")
dim_tiempo["semestre"] = ((dim_tiempo["mes"] - 1) // 6 + 1).astype("Int64")

# --- dim_ciudad (catálogo)
dim_ciudad = df_ciudades.rename(columns={"nombre": "nombre_ciudad"})[["id_ciudad", "nombre_ciudad"]].copy()

# --- dim_avion (desnormalizado con aerolínea y modelo)
dim_avion = (
    df_aviones
    .merge(df_aerolineas.rename(columns={"nombre": "nombre_aerolinea"}), on="id_aerolinea", how="left")
    .merge(df_modelos.rename(columns={"nombre": "nombre_modelo"}), on="id_modelo", how="left")
    .rename(columns={"nombre": "nombre_avion"})
    [["id_avion", "nombre_avion", "nombre_aerolinea", "nombre_modelo"]]
    .copy()
)

# --- dim_usuario (incluye nombre de ciudad de residencia ya copiado)
dim_usuario = (
    df_usuarios
    .merge(df_ciudades.rename(columns={"nombre": "ciudad_residencia_nombre"}), on="id_ciudad", how="left")
    .assign(nombre_completo=lambda d: d["nombre"].astype(str) + " " + d["apellido"].astype(str))
    .rename(columns={"cedula": "id_usuario"})
    [["id_usuario", "nombre_completo", "email", "ciudad_residencia_nombre"]]
    .copy()
)

# =========================
# Construcción de la tabla de hechos
# =========================

# Mapear ciudades origen/destino: itinerarios -> aeropuertos -> ciudades
origen = (
    df_itins[["id_itinerario", "id_aeropuerto_origen"]]
    .merge(
        df_aeropuertos[["id_aeropuerto", "id_ciudad"]],
        left_on="id_aeropuerto_origen",
        right_on="id_aeropuerto",
        how="left"
    )
    .rename(columns={"id_ciudad": "id_ciudad_origen"})
    [["id_itinerario", "id_ciudad_origen"]]
)

destino = (
    df_itins[["id_itinerario", "id_aeropuerto_destino"]]
    .merge(
        df_aeropuertos[["id_aeropuerto", "id_ciudad"]],
        left_on="id_aeropuerto_destino",
        right_on="id_aeropuerto",
        how="left"
    )
    .rename(columns={"id_ciudad": "id_ciudad_destino"})
    [["id_itinerario", "id_ciudad_destino"]]
)

# Vincular id_tiempo al itinerario
df_itins["id_tiempo"] = df_itins["fecha_date"].map(id_map).astype("Int64")

# Hecho
hecho_vuelos = (
    df_vuelos
    .merge(df_itins[["id_itinerario", "id_tiempo"]], on="id_itinerario", how="left")
    .merge(origen, on="id_itinerario", how="left")
    .merge(destino, on="id_itinerario", how="left")
    .assign(vuelo_cnt=1)
    [["id_tiempo", "id_avion", "id_usuario", "id_ciudad_origen", "id_ciudad_destino", "costo", "vuelo_cnt"]]
    .copy()
)

# =========================
# Carga a DuckDB (tablas ya creadas)
# =========================
print(f"[INFO] Conectando a DuckDB en {DUCKDB_PATH} …")
con = duckdb.connect(DUCKDB_PATH)

# Carga idempotente: limpiamos tablas antes de insertar
for t in ["hecho_vuelos", "dim_tiempo", "dim_avion", "dim_ciudad", "dim_usuario"]:
    con.execute(f"DELETE FROM {t};")

# Registrar dataframes y volcar
con.register("df_dim_tiempo", dim_tiempo)
con.register("df_dim_avion", dim_avion)
con.register("df_dim_ciudad", dim_ciudad)
con.register("df_dim_usuario", dim_usuario)
con.register("df_hecho", hecho_vuelos)

con.execute("INSERT INTO dim_tiempo SELECT * FROM df_dim_tiempo;")
con.execute("INSERT INTO dim_avion  SELECT * FROM df_dim_avion;")
con.execute("INSERT INTO dim_ciudad SELECT * FROM df_dim_ciudad;")
con.execute("INSERT INTO dim_usuario SELECT * FROM df_dim_usuario;")
con.execute("INSERT INTO hecho_vuelos SELECT * FROM df_hecho;")

# =========================
# Validaciones rápidas
# =========================
def scalar(sql: str):
    return con.execute(sql).fetchone()[0]

print("\n[OK] Carga completada. Conteos:")
print(" - dim_tiempo       :", scalar("SELECT COUNT(*) FROM dim_tiempo"))
print(" - dim_avion        :", scalar("SELECT COUNT(*) FROM dim_avion"))
print(" - dim_ciudad       :", scalar("SELECT COUNT(*) FROM dim_ciudad"))
print(" - dim_usuario      :", scalar("SELECT COUNT(*) FROM dim_usuario"))
print(" - hecho_vuelos     :", scalar("SELECT COUNT(*) FROM hecho_vuelos"))

# Sanity checks por años disponibles
try:
    df_years = con.execute("""
        SELECT anio, COUNT(*) AS vuelos
        FROM hecho_vuelos f
        JOIN dim_tiempo t ON f.id_tiempo = t.id_tiempo
        GROUP BY 1 ORDER BY 1
    """).fetchdf()
    print("\nDistribución por año:")
    print(df_years.to_string(index=False))
except Exception as e:
    print("[WARN] No fue posible calcular distribución por año:", e)

con.close()
engine.dispose()
print(f"\n[OK] ETL finalizado. DuckDB listo en: {DUCKDB_PATH}")
