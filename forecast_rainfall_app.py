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

    # Standardize state names to mach with the state names in geojson file
    df["state_name"] = df["state_name"].replace({"Jammu And Kashmir": "Jammu and Kashmir"})

    # Split merged UT into two separate rows
    merged_ut = "The Dadra And Nagar Haveli And Daman And Diu"
    ut_rows = df[df["state_name"] == merged_ut]
    ut_rows_dadra = ut_rows.copy(); ut_rows_dadra["state_name"] = "Dadra and Nagar Haveli"
    ut_rows_daman = ut_rows.copy(); ut_rows_daman["state_name"] = "Daman and Diu"
    df = df[df["state_name"] != merged_ut]
    df = pd.concat([df, ut_rows_dadra, ut_rows_daman], ignore_index=True)

    return df

@st.cache_data
def load_geojson():
    # load geojson file that contains the geometries of Indian states 
    with open("india_states.geojson", "r") as f:
        india_states = json.load(f)
    # Remove some small UTs if you don't want them
    india_states["features"] = [
        feat for feat in india_states["features"]
        if feat["properties"]["st_nm"] not in ["Andaman and Nicobar Islands", "Lakshadweep"]
    ]
    return india_states

# ================== Load data ==================
df = load_data()
geojson = load_geojson()

# ================== page layout and Selections ==================
st.set_page_config(layout="wide", page_title="India Rainfall")
st.title("🌧️ Rainfall Forecast - India (2024–2030)")
st.markdown("Tracking Tomorrow’s Rainfall Patterns Across India — State by State")

col_year, col_state = st.columns(2)
with col_year:
    selected_year = st.radio("Select Year", sorted(df['year'].unique()), horizontal=True)
with col_state:
    # Only states present in CSV for selection (Ladakh excluded)
    selectable_states = sorted(df['state_name'].unique())
    selected_state = st.selectbox("Select State/UT", selectable_states)

# ================== Prepare Data for Map ==================


# Get all states from geojson
geo_states = [feat["properties"]["st_nm"] for feat in geojson["features"]]
all_states_df = pd.DataFrame({"state_name": geo_states})

# Filter by selected year first
df_year = df[df['year'] == selected_year].groupby('state_name', as_index=False)['predicted_rainfall'].sum()

# Copy J&K rainfall to Ladakh for this year
if "Jammu and Kashmir" in df_year['state_name'].values and "Ladakh" not in df_year['state_name'].values:
    jk_value = df_year.loc[df_year['state_name'] == "Jammu and Kashmir", "predicted_rainfall"].values[0]
    df_year = pd.concat([df_year, pd.DataFrame({"state_name": ["Ladakh"], "predicted_rainfall": [jk_value]})], ignore_index=True)

# Merge with geojson states to include all
df_year = all_states_df.merge(df_year, on="state_name", how="left")

# ================== Prepare Monthly Data ==================
# Aggregating monthly rainfall per state and pivot for easier plotting in a line chart
monthly = df.groupby(["state_name", "year", "month_name"], as_index=False)["predicted_rainfall"].sum()
monthly_pivot = monthly.pivot_table(index=["state_name","year"], columns="month_name", values="predicted_rainfall").reset_index()
month_order = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
monthly_pivot = monthly_pivot[["state_name","year"] + month_order]

row = monthly_pivot[(monthly_pivot["state_name"]==selected_state) & (monthly_pivot["year"]==selected_year)]
if not row.empty:
    data = row[month_order].T.reset_index()
    data.columns = ["Month","Rainfall"]

# ================== Layout ==================
col1, col2 = st.columns([1,1])

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
        hover_name="state_name",
        hover_data={"predicted_rainfall": True,"state_name":False},
        template="plotly_dark"
    )
    fig_map.update_geos(fitbounds="locations",visible=False,)
    st.plotly_chart(fig_map, use_container_width=True)

    # ================== Year-over-Year Trend ==================
    st.subheader(f"Year-over-Year Rainfall Trend - {selected_state}")

    prev_year = selected_year - 1

    # Get current & previous rainfall totals
    curr_value = df[(df['state_name'] == selected_state) & (df['year'] == selected_year)]["predicted_rainfall"].sum()
    prev_value = df[(df['state_name'] == selected_state) & (df['year'] == prev_year)]["predicted_rainfall"].sum()

    if prev_value > 0:
        diff = curr_value - prev_value
        pct_change = (diff / prev_value * 100)
    else:
        diff, pct_change = None, None

    # Show metrics
    colA, colB, colC = st.columns(3)
    colA.metric(f"{selected_year} Rainfall", f"{curr_value:.1f} mm")
    colB.metric(f"{prev_year} Rainfall", f"{prev_value:.1f} mm")
    if pct_change is not None:
        colC.metric("Change", f"{diff:.1f} mm", f"{pct_change:+.1f}%")
    else:
        colC.warning("No previous year data")

    # Trend chart (side by side bars)
    if prev_value > 0:
        trend_df = pd.DataFrame({
            "Year": [prev_year, selected_year],
            "Rainfall": [prev_value, curr_value]
        })
        trend_df["Rainfall"] = trend_df["Rainfall"].round(2)
        fig_trend = px.bar(trend_df, x="Year", y="Rainfall", text="Rainfall",
                       color="Rainfall", color_continuous_scale="Blues", title=f"Rainfall Comparison: {prev_year} vs {selected_year}")
        fig_trend.update_xaxes(type="category", categoryorder="array", categoryarray=[prev_year, selected_year])
        st.plotly_chart(fig_trend, use_container_width=True)

# ---- Column 2: Line chart + Table ----
with col2:
    st.subheader(f"Monthly Rainfall Trend - {selected_state} ({selected_year})")
    if not row.empty:
        fig_line = px.line(data, x="Month", y="Rainfall", markers=True)
        fig_line.update_xaxes(categoryorder='array', categoryarray=month_order)
        st.plotly_chart(fig_line, use_container_width=True)
        st.subheader(f"Monthly Rainfall Data- {selected_year}")
        st.table(data.set_index("Month"))
    else:
        st.warning("No monthly data for this selection")

# ==== Yearly Trend (full-width) ====
yearly_state = df[df["state_name"] == selected_state].groupby("year", as_index=False)["predicted_rainfall"].sum()

if not yearly_state.empty:
    st.subheader(f"Yearly Rainfall Trend - {selected_state} (2024–2030)")
    fig_yearly = px.line(
        yearly_state,
        x="year",
        y="predicted_rainfall",
        markers=True,
    )
    fig_yearly.update_yaxes(title_text="Predicted Rainfall (mm)")
    fig_yearly.update_xaxes(title_text="Year", dtick=1)
    st.plotly_chart(fig_yearly, use_container_width=True)