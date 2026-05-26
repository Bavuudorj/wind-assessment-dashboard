import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium
from scipy.stats import weibull_min

from data_fetcher import fetch_wind_data
from wind_math import (
    fit_weibull,
    calculate_aep,
    get_all_turbine_names,
    get_power_curve,
    save_project,
    get_all_projects,
)

st.set_page_config(page_title="Wind Resource Assessment", layout="wide")
st.title("Салхины эрчим хүчний нөөцийн үнэлгээ")

DEFAULT_LAT, DEFAULT_LON = 47.92, 106.92


# --- Sidebar: years + turbine ---
with st.sidebar:
    st.header("Assessment Inputs")
    start_year = st.number_input("Эхлэх огноо", value=2019, min_value=1980, max_value=2026, step=1)
    end_year = st.number_input("Дуусах огноо", value=2023, min_value=1980, max_value=2026, step=1)

    turbine_names = get_all_turbine_names()
    if not turbine_names:
        st.error("No turbines found in database. Run database_setup.py first.")
        st.stop()
    selected_turbine = st.selectbox("Салхин турбины загвар сонгох", turbine_names)


# --- Main page: interactive map for site selection ---
st.subheader("Байршил сонгох")
st.caption("Доорх газрын зураг дээр сонирхосон байрлалаа тэмдэглэнэ үү.")

if "selected_coords" not in st.session_state:
    st.session_state["selected_coords"] = None

fmap = folium.Map(location=[DEFAULT_LAT, DEFAULT_LON], zoom_start=5)
if st.session_state["selected_coords"] is not None:
    lat_sel, lon_sel = st.session_state["selected_coords"]
    folium.Marker(
        [lat_sel, lon_sel],
        tooltip=f"Сонгогдсон байрлал ({lat_sel:.4f}, {lon_sel:.4f})",
        icon=folium.Icon(color="red"),
    ).add_to(fmap)

map_data = st_folium(fmap, width=None, height=450, returned_objects=["last_clicked"])

if map_data and map_data.get("last_clicked"):
    click = map_data["last_clicked"]
    new_coords = (click["lat"], click["lng"])
    if st.session_state["selected_coords"] != new_coords:
        st.session_state["selected_coords"] = new_coords
        st.rerun()

coords = st.session_state["selected_coords"]
if coords is None:
    st.info("Байршил согогдоогүй байна. Байршилаа газрын зураг дээр тэмдэглэнэ үү.")
else:
    st.success(f"Сонгогдсон байрлал: **Өргөрөг {coords[0]:.4f}, Уртраг {coords[1]:.4f}**")

run = st.button("Үнэлэх", type="primary", disabled=(coords is None))


# --- Chart helpers ---
def weibull_histogram(wind: pd.Series, k: float, c: float) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=wind, histnorm="probability density", nbinsx=40,
        name="Хэмжилт", marker_color="#4C9AFF", opacity=0.75,
    ))
    x = np.linspace(0, wind.max() * 1.05, 200)
    pdf = weibull_min.pdf(x, k, loc=0, scale=c)
    fig.add_trace(go.Scatter(
        x=x, y=pdf, mode="lines", name=f"Вейбуллийн тархалт k={k:.2f}, c={c:.2f})",
        line=dict(color="#FF6B6B", width=3),
    ))
    fig.update_layout(
        title="Салхины хурдны болон Вейбуллийн тархалт",
        xaxis_title="Салхины хурд (м/с)", yaxis_title="Магадлалын нягт", bargap=0.02,
    )
    return fig


def diurnal_profile_chart(df: pd.DataFrame, col: str) -> go.Figure:
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("DataFrame index must be a DatetimeIndex for diurnal profile.")
    hourly_mean = df.groupby(df.index.hour)[col].mean()
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=hourly_mean.index, y=hourly_mean.values,
        mode="lines+markers", line=dict(color="#36B37E", width=3), name="Mean wind speed",
    ))
    fig.update_layout(
        title="Салхины хурдны хоногын горим",
        xaxis_title="Цаг (орон нутаг)", yaxis_title="Салхины хурд (м/с)",
        xaxis=dict(tickmode="linear", dtick=2, range=[-0.5, 23.5]),
    )
    return fig


# --- Run assessment ---
if run and coords is not None:
    lat, lon = coords

    if end_year < start_year:
        st.error("End year must be >= start year.")
        st.stop()

    with st.spinner("Fetching wind data..."):
        df = fetch_wind_data(lat, lon, int(start_year), int(end_year))

    if df is None:
        st.error(
            "Unable to retrieve wind data. Please check your internet connection, "
            "verify the selected coordinates, or try again later."
        )
        st.stop()
    elif df.empty:
        st.error("The data source returned no records for this location and time period.")
        st.stop()
    else:
        power_curve = get_power_curve(selected_turbine)
        if not power_curve:
            st.error(f"No power curve found for '{selected_turbine}'.")
            st.stop()
        rated_kw = max(power_curve.values())

        with st.spinner("Fitting Weibull and computing AEP..."):
            k, c = fit_weibull(df)
            aep_mwh = calculate_aep(df, power_curve)
            wind = df["Wind_Speed_50m"].dropna()
            wind = wind[wind > 0]

        st.session_state["results"] = {
            "lat": lat, "lon": lon, "turbine": selected_turbine,
            "rated_kw": rated_kw, "k": k, "c": c, "aep_mwh": aep_mwh,
            "mean_ws": wind.mean(), "wind": wind, "df": df,
        }


# --- Render results (survives reruns from Save button etc.) ---
if "results" in st.session_state:
    r = st.session_state["results"]
    cf = r["aep_mwh"] / (r["rated_kw"] / 1000.0 * 8760) * 100

    st.subheader(f"Үр дүн ({r['lat']:.4f}, {r['lon']:.4f}) — {r['turbine']}")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Салхины дундаж хурд", f"{r['mean_ws']:.2f} м/с")
    m2.metric("Вейбуллийн хэлбэршилтийн параметр (k)", f"{r['k']:.2f}")
    m3.metric("Вейбуллийн хэмжээсийн параметр (c)", f"{r['c']:.2f} м/с")
    m4.metric(f"Жилд үйлдвэрлэх ЦЭХ ({r['rated_kw']/1000:.1f} МВт)",
              f"{r['aep_mwh']:,.0f} МВт.ц", f"Чадал ашиглалт {cf:.1f}%")

    st.plotly_chart(weibull_histogram(r["wind"], r["k"], r["c"]), use_container_width=True)
    st.plotly_chart(diurnal_profile_chart(r["df"], "Wind_Speed_50m"), use_container_width=True)

    st.divider()
    st.subheader("Хадаглах")
    project_name = st.text_input("Нэр", key="project_name_input")
    if st.button("Хадаглах"):
        if not project_name.strip():
            st.warning("Нэр оруулна уу.")
        else:
            new_id = save_project(
                project_name.strip(), r["lat"], r["lon"], r["turbine"], r["aep_mwh"],
            )
            st.success(f"Saved project '{project_name}' (id={new_id}).")


# --- Saved project history (always visible) ---
st.divider()
st.subheader("Хадаглагдсан төслүүд")
projects_df = get_all_projects()
if projects_df.empty:
    st.caption("No saved projects yet.")
else:
    st.dataframe(projects_df, use_container_width=True, hide_index=True)
