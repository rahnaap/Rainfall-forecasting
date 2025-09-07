import streamlit as st
import pandas as pd
import plotly.express as px
import json

# ================== Data Loading ==================
@st.cache_data
def load_data():
    df = pd.read_csv("forecast_results.csv")
    df["date"] = pd.to_datetime(df["date"])
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month
    df["month_name"] = df["date"].dt.strftime("%b")

    df["state_name"] = df["state_name"].replace({"Jammu And Kashmir": "Jammu and Kashmir"})

    merged_ut = "The Dadra And Nagar Haveli And Daman And Diu"
    ut_rows = df[df["state_name"] == merged_ut]
    ut_rows_dadra = ut_rows.copy(); ut_rows_dadra["state_name"]="Dadra and Nagar Haveli"
    ut_rows_daman = ut_rows.copy(); ut_rows_daman["state_name"]="Daman and Diu"
    df = df[df["state_name"] != merged_ut]
    df = pd.concat([df, ut_rows_dadra, ut_rows_daman], ignore_index=True)

    return df

@st.cache_data
def load_geojson():
    with open("test.geojson", "r") as f:
        india_states = json.load(f)
    india_states["features"] = [
        feat for feat in india_states["features"]
        if feat["properties"]["st_nm"] not in ["Andaman and Nicobar Islands", "Lakshadweep"]
    ]
    return india_states

df = load_data()
geojson = load_geojson()

# ================== selection ==================
st.set_page_config(layout="wide", page_title="India Rainfall Dashboard")
st.title("🌧️ India Rainfall Prediction Dashboard")

col_year, col_state = st.columns(2)
with col_year:
    selected_year = st.radio("Select Year", sorted(df['year'].unique()), horizontal=True)

with col_state:
    selected_state = st.selectbox("Select State/UT", sorted(df['state_name'].unique()))

# ================== Prepare Data ==================
df_year = df[df['year']==selected_year].groupby('state_name', as_index=False)['predicted_rainfall'].sum()

monthly = df.groupby(["state_name", "year", "month_name"], as_index=False)["predicted_rainfall"].sum()
monthly_pivot = monthly.pivot_table(index=["state_name","year"], columns="month_name", values="predicted_rainfall").reset_index()
month_order = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
monthly_pivot = monthly_pivot[["state_name","year"] + month_order]
row = monthly_pivot[(monthly_pivot["state_name"]==selected_state) & (monthly_pivot["year"]==selected_year)]
if not row.empty:
    data = row[month_order].T.reset_index()
    data.columns = ["Month","Rainfall"]

# ================== Layout ==================
col1, col2 = st.columns([2,1])

# ---- Column 1: Map ----
with col1:
    st.subheader(f"Rainfall Intensity Map - {selected_year}")
    fig_map = px.choropleth(
        df_year,
        geojson=geojson,
        featureidkey="properties.st_nm",
        locations="state_name",
        color="predicted_rainfall",
        color_continuous_scale="Blues",
        range_color=(df_year['predicted_rainfall'].min(), df_year['predicted_rainfall'].max()),
        hover_name="state_name",
        hover_data={"predicted_rainfall": True},
        template="plotly_dark"
    )
    fig_map.update_geos(
    fitbounds="locations",   # zoom to data
    visible=False,
    projection_scale=18,   # increase this to make map bigger
    center={"lat": 22, "lon": 80})

    fig_map.update_layout(height=700,
                          margin={"r":0,"t":0,"l":0,"b":0})
    st.plotly_chart(fig_map, use_container_width=True,config={"responsive": True})
    

# ---- Column 2: Line chart + Table ----
with col2:
    st.subheader(f"Monthly Rainfall Trend - {selected_state} ({selected_year})")
    if not row.empty:
        fig_line = px.line(data, x="Month", y="Rainfall", markers=True)
        fig_line.update_xaxes(categoryorder='array', categoryarray=month_order)
        st.plotly_chart(fig_line, use_container_width=True)
        st.subheader("Monthly Rainfall Data")
        st.table(data)
    else:
        st.warning("No monthly data for this selection")