import duckdb
import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="IATA – Mini Data Mart", layout="wide")

DB = "data/iata_star.duckdb"

@st.cache_data(show_spinner=False)
def run(sql: str):
    con = duckdb.connect(DB, read_only=True)
    df = con.execute(sql).fetchdf()
    con.close()
    return df

st.title("✈️ IATA – Mini Data Mart")
st.caption("Visualización interactiva de los análisis de vuelos (2019–2020)")

# =========================
# 1) Aerolínea con más vuelos a Roma por año
# =========================
st.subheader("1️⃣ Aerolínea con más vuelos a Roma por año")

q1 = r"""
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
ORDER BY anio;
"""
df1 = run(q1)
if not df1.empty:
    fig1 = px.bar(
        df1,
        x="anio",
        y="vuelos",
        color="nombre_aerolinea",
        text="vuelos",
        barmode="group",
        title="Número de vuelos a Roma por aerolínea y año",
        color_discrete_sequence=px.colors.qualitative.Bold
    )
    fig1.update_traces(textposition="outside")
    st.plotly_chart(fig1, use_container_width=True)
    st.dataframe(df1, use_container_width=True, height=200)
else:
    st.info("No se encontraron vuelos a Roma en los datos.")

st.markdown("---")

# =========================
# 2) Recaudo total por aerolínea (primer semestre)
# =========================
st.subheader("2️⃣ Recaudo total por aerolínea (primer semestre)")

years = st.multiselect("Selecciona años", [2019, 2020], default=[2019, 2020], key="years_q2")
anios = ", ".join(str(y) for y in years) if years else "2019, 2020"

q2 = f"""
SELECT t.anio, a.nombre_aerolinea, SUM(f.costo) AS recaudo
FROM hecho_vuelos f
JOIN dim_avion a USING (id_avion)
JOIN dim_tiempo t ON f.id_tiempo = t.id_tiempo
WHERE t.semestre = 1 AND t.anio IN ({anios})
GROUP BY 1,2
ORDER BY anio, recaudo DESC;
"""
df2 = run(q2)

if not df2.empty:
    # ---- Formato de dinero ----
    df2["recaudo_format"] = df2["recaudo"].apply(lambda x: f"${x:,.0f}")

    # ---- Visualización por año ----
    for anio in sorted(df2["anio"].unique()):
        df_anio = df2[df2["anio"] == anio]
        fig2 = px.pie(
            df_anio,
            names="nombre_aerolinea",
            values="recaudo",
            title=f"Recaudo por aerolínea – Año {anio}",
            hole=0.4,  # tipo donut
            color_discrete_sequence=px.colors.qualitative.Set3
        )
        # Mostrar valor monetario al pasar el mouse
        fig2.update_traces(
            textposition="inside",
            textinfo="percent+label",
            hovertemplate="<b>%{label}</b><br>Recaudo: $%{value:,.0f}<extra></extra>"
        )
        st.plotly_chart(fig2, use_container_width=True)

    # ---- Tabla formateada ----
    st.dataframe(
        df2[["anio", "nombre_aerolinea", "recaudo_format"]],
        use_container_width=True,
        height=220
    )
else:
    st.warning("No hay datos de recaudo para los años seleccionados.")
st.markdown("---")

# =========================
# 3) Modelo de avión con más vuelos por año
# =========================
st.subheader("3️⃣ Modelo de avión con más vuelos por año")

q3 = r"""
WITH base AS (
  SELECT t.anio, a.nombre_modelo
  FROM hecho_vuelos f
  JOIN dim_avion a USING (id_avion)
  JOIN dim_tiempo t ON f.id_tiempo = t.id_tiempo
)
SELECT anio, nombre_modelo, COUNT(*) AS vuelos
FROM base
GROUP BY 1,2
ORDER BY anio;
"""
df3 = run(q3)
if not df3.empty:
    fig3 = px.bar(
        df3,
        x="anio",
        y="vuelos",
        color="nombre_modelo",
        text="vuelos",
        title="Número de vuelos por modelo de avión",
        color_discrete_sequence=px.colors.qualitative.Safe
    )
    fig3.update_traces(textposition="outside")
    st.plotly_chart(fig3, use_container_width=True)
    st.dataframe(df3, use_container_width=True, height=200)
else:
    st.warning("No se encontraron registros de vuelos por modelo.")

st.markdown("---")

# =========================
# 4) Ciudad de residencia con más viajeros por año
# =========================
st.subheader("4️⃣ Ciudad de residencia con más viajeros por año")

q4 = r"""
WITH base AS (
  SELECT t.anio, u.ciudad_residencia_nombre AS ciudad
  FROM hecho_vuelos f
  JOIN dim_usuario u USING (id_usuario)
  JOIN dim_tiempo t ON f.id_tiempo = t.id_tiempo
)
SELECT anio, ciudad, COUNT(*) AS viajes
FROM base
GROUP BY 1,2
ORDER BY anio;
"""
df4 = run(q4)
if not df4.empty:
    for anio in sorted(df4["anio"].unique()):
        df_anio = df4[df4["anio"] == anio]
        fig4 = px.pie(
            df_anio,
            names="ciudad",
            values="viajes",
            hole=0.35,
            title=f"Distribución de viajeros por ciudad – Año {anio}",
            color_discrete_sequence=px.colors.qualitative.Vivid
        )
        fig4.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(fig4, use_container_width=True)
    st.dataframe(df4, use_container_width=True, height=200)
else:
    st.warning("No se encontraron datos de ciudades de residencia.")

st.markdown("---")
st.caption("Fuente: Base MySQL IATA → ETL → DuckDB → Streamlit")
