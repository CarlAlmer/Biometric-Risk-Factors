import os
import sqlite3

import pandas as pd
import streamlit as st

# -------------------------------------------------------------------------
# PATH + DB
# -------------------------------------------------------------------------
_same_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "biometric.db")
_up_one = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../data/biometric.db")
DB_PATH = _same_dir if os.path.exists(_same_dir) else _up_one


def connect_db():
    return sqlite3.connect(DB_PATH)


# -------------------------------------------------------------------------
# PAGE CONFIG
# -------------------------------------------------------------------------
st.set_page_config(
    page_title="Firefighter Biometric Risk Dashboard",
    page_icon="🚒",
    layout="wide",
)

# -------------------------------------------------------------------------
# CSS
# -------------------------------------------------------------------------
st.markdown(
    """
<style>
.risk-banner {
    background: linear-gradient(135deg, #7A0A1C 0%, #C8102E 60%, #7A0A1C 100%);
    padding: 1.2rem 2rem;
    border-radius: 8px;
    margin-bottom: 1.5rem;
}
.risk-banner h1 { margin: 0; font-size: 1.8rem; font-weight: 800; color: white; }
.risk-banner p  { margin: 0.2rem 0 0; font-size: 0.95rem; color: rgba(255,255,255,0.85); }
div[data-testid="metric-container"] {
    border: 2px solid #C8102E;
    border-radius: 8px;
    padding: 0.75rem 1rem;
    background-color: #FBEEEE;
}
.stTabs [data-baseweb="tab-highlight"] { background-color: #C8102E !important; }
.stTabs [aria-selected="true"] { color: #C8102E !important; font-weight: 700; }
</style>
""",
    unsafe_allow_html=True,
)

# -------------------------------------------------------------------------
# HELPERS
# -------------------------------------------------------------------------
METRIC_COLUMNS = ["BMI", "WAIST", "TC", "HDL", "RTO", "GLU", "SYS", "DIA"]

# These are simple screening cutoffs to help flag records for analysis.
# They are not medical diagnoses.
RISK_RULES = {
    "BMI": (30, "high"),       # obesity threshold
    "WAIST": (40, "high"),    # common male risk threshold in inches
    "TC": (200, "high"),      # total cholesterol
    "HDL": (40, "low"),       # low HDL
    "RTO": (5, "high"),       # TC/HDL ratio
    "GLU": (100, "high"),     # fasting glucose prediabetes threshold
    "SYS": (130, "high"),     # elevated blood pressure range
    "DIA": (80, "high"),
}


def style_risk(val):
    try:
        v = float(val)
        if v >= 50:
            return "color: #C8102E; font-weight: 700"
        if v >= 25:
            return "color: #B36B00; font-weight: 700"
    except Exception:
        pass
    return ""


def style_positive_negative(val):
    try:
        v = float(val)
        if v > 0:
            return "color: #C8102E; font-weight: 600"
        if v < 0:
            return "color: green; font-weight: 600"
    except Exception:
        pass
    return ""


# -------------------------------------------------------------------------
# DATA LOADERS
# -------------------------------------------------------------------------
@st.cache_data
def load_biometric_data():
    conn = connect_db()
    df = pd.read_sql_query("SELECT * FROM biometric_data", conn)
    conn.close()

    for col in METRIC_COLUMNS + ["Age", "year"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


@st.cache_data
def load_sources():
    conn = connect_db()
    try:
        df = pd.read_sql_query("SELECT * FROM data_sources ORDER BY year, department", conn)
    except Exception:
        df = pd.DataFrame()
    conn.close()
    return df


def apply_filters(df, departments, years, age_range):
    out = df.copy()
    if departments:
        out = out[out["department"].isin(departments)]
    if years:
        out = out[out["year"].isin(years)]
    if "Age" in out.columns and age_range:
        out = out[(out["Age"] >= age_range[0]) & (out["Age"] <= age_range[1])]
    return out


def add_risk_flags(df):
    out = df.copy()
    for metric, (cutoff, direction) in RISK_RULES.items():
        if metric not in out.columns:
            continue
        if direction == "high":
            out[f"{metric}_risk"] = out[metric] >= cutoff
        else:
            out[f"{metric}_risk"] = out[metric] < cutoff

    risk_cols = [c for c in out.columns if c.endswith("_risk")]
    out["risk_factor_count"] = out[risk_cols].sum(axis=1) if risk_cols else 0
    return out


def risk_percent(df, metric):
    if metric not in df.columns or df.empty:
        return None
    cutoff, direction = RISK_RULES[metric]
    values = df[metric].dropna()
    if values.empty:
        return None
    if direction == "high":
        return (values >= cutoff).mean() * 100
    return (values < cutoff).mean() * 100


def summarize_by_department(df):
    if df.empty:
        return pd.DataFrame()

    grouped = df.groupby(["department", "year"], dropna=False)
    summary = grouped.agg(
        Records=("id", "count"),
        Avg_Age=("Age", "mean"),
        Avg_BMI=("BMI", "mean"),
        Avg_WAIST=("WAIST", "mean"),
        Avg_TC=("TC", "mean"),
        Avg_HDL=("HDL", "mean"),
        Avg_RTO=("RTO", "mean"),
        Avg_GLU=("GLU", "mean"),
        Avg_SYS=("SYS", "mean"),
        Avg_DIA=("DIA", "mean"),
        Avg_Risk_Factors=("risk_factor_count", "mean"),
    ).reset_index()

    for metric in RISK_RULES:
        summary[f"Pct_{metric}_Risk"] = grouped.apply(lambda g, m=metric: risk_percent(g, m)).values

    return summary


# -------------------------------------------------------------------------
# BANNER
# -------------------------------------------------------------------------
st.markdown(
    """
<div class="risk-banner">
    <h1>Firefighter Biometric Risk Dashboard</h1>
    <p>Department health screening trends, descriptive statistics, and risk factor summaries</p>
</div>
""",
    unsafe_allow_html=True,
)

# Optional password, only active if you add password to .streamlit/secrets.toml
if "password" in st.secrets:
    password = st.text_input("Enter password", type="password")
    if password != st.secrets["password"]:
        st.warning("Please enter the correct password.")
        st.stop()

# -------------------------------------------------------------------------
# LOAD DATA
# -------------------------------------------------------------------------
try:
    data = load_biometric_data()
except Exception as e:
    st.error(f"Could not load biometric.db. Make sure biometric.db is in the same folder as this app. Error: {e}")
    st.stop()

if data.empty:
    st.warning("No records found in biometric_data yet.")
    st.stop()

data = add_risk_flags(data)

# -------------------------------------------------------------------------
# SIDEBAR FILTERS
# -------------------------------------------------------------------------
st.sidebar.header("Filters")

department_options = sorted(data["department"].dropna().unique().tolist())
year_options = sorted(data["year"].dropna().astype(int).unique().tolist())

selected_departments = st.sidebar.multiselect("Department", department_options)
selected_years = st.sidebar.multiselect("Year", year_options, default=year_options)

if "Age" in data.columns and data["Age"].notna().any():
    min_age = int(data["Age"].min())
    max_age = int(data["Age"].max())
    selected_age = st.sidebar.slider("Age range", min_age, max_age, (min_age, max_age))
else:
    selected_age = None

filtered = apply_filters(data, selected_departments, selected_years, selected_age)

# -------------------------------------------------------------------------
# TABS
# -------------------------------------------------------------------------
tab_overview, tab_departments, tab_risk, tab_records, tab_sources = st.tabs(
    ["Overview", "Department Comparison", "Risk Factors", "Raw Records", "Data Sources"]
)

# =========================================================================
# OVERVIEW
# =========================================================================
with tab_overview:
    st.header("Overview")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Records", f"{len(filtered):,}")
    c2.metric("Departments", filtered["department"].nunique())
    c3.metric("Avg Age", f"{filtered['Age'].mean():.1f}" if filtered["Age"].notna().any() else "—")
    c4.metric("Avg Risk Factors", f"{filtered['risk_factor_count'].mean():.2f}")

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Avg BMI", f"{filtered['BMI'].mean():.1f}" if "BMI" in filtered else "—")
    c6.metric("Avg Glucose", f"{filtered['GLU'].mean():.1f}" if "GLU" in filtered else "—")
    c7.metric("Avg Total Chol.", f"{filtered['TC'].mean():.1f}" if "TC" in filtered else "—")
    c8.metric("Avg BP", f"{filtered['SYS'].mean():.0f}/{filtered['DIA'].mean():.0f}" if {"SYS", "DIA"}.issubset(filtered.columns) else "—")

    st.divider()
    st.subheader("Metric Distributions")
    metric = st.selectbox("Choose a metric", [m for m in METRIC_COLUMNS if m in filtered.columns])
    chart_df = filtered[[metric]].dropna()
    if not chart_df.empty:
        st.bar_chart(chart_df[metric].value_counts().sort_index())
    else:
        st.info("No values available for this metric.")

# =========================================================================
# DEPARTMENT COMPARISON
# =========================================================================
with tab_departments:
    st.header("Department Comparison")

    summary = summarize_by_department(filtered)
    if summary.empty:
        st.warning("No data for the selected filters.")
    else:
        chart_metric = st.selectbox(
            "Compare departments by",
            ["Avg_Risk_Factors", "Avg_BMI", "Avg_WAIST", "Avg_TC", "Avg_HDL", "Avg_RTO", "Avg_GLU", "Avg_SYS", "Avg_DIA"],
        )
        chart_data = summary.pivot_table(index="department", columns="year", values=chart_metric, aggfunc="mean")
        st.bar_chart(chart_data)

        st.divider()
        st.dataframe(
            summary.style.format({
                "Avg_Age": "{:.1f}",
                "Avg_BMI": "{:.1f}",
                "Avg_WAIST": "{:.1f}",
                "Avg_TC": "{:.1f}",
                "Avg_HDL": "{:.1f}",
                "Avg_RTO": "{:.2f}",
                "Avg_GLU": "{:.1f}",
                "Avg_SYS": "{:.1f}",
                "Avg_DIA": "{:.1f}",
                "Avg_Risk_Factors": "{:.2f}",
                "Pct_BMI_Risk": "{:.1f}%",
                "Pct_WAIST_Risk": "{:.1f}%",
                "Pct_TC_Risk": "{:.1f}%",
                "Pct_HDL_Risk": "{:.1f}%",
                "Pct_RTO_Risk": "{:.1f}%",
                "Pct_GLU_Risk": "{:.1f}%",
                "Pct_SYS_Risk": "{:.1f}%",
                "Pct_DIA_Risk": "{:.1f}%",
            }, na_rep="—").map(style_risk, subset=[c for c in summary.columns if c.startswith("Pct_")]),
            use_container_width=True,
            hide_index=True,
        )

# =========================================================================
# RISK FACTORS
# =========================================================================
with tab_risk:
    st.header("Risk Factors")
    st.caption("These flags are for descriptive screening only, not medical diagnosis.")

    risk_rows = []
    for metric, (cutoff, direction) in RISK_RULES.items():
        if metric not in filtered.columns:
            continue
        pct = risk_percent(filtered, metric)
        risk_rows.append({
            "Metric": metric,
            "Risk Rule": f"{'≥' if direction == 'high' else '<'} {cutoff}",
            "Percent Flagged": pct,
            "Records with Data": filtered[metric].notna().sum(),
        })
    risk_df = pd.DataFrame(risk_rows)

    if not risk_df.empty:
        st.dataframe(
            risk_df.style.format({"Percent Flagged": "{:.1f}%"}, na_rep="—").map(style_risk, subset=["Percent Flagged"]),
            use_container_width=True,
            hide_index=True,
        )
        st.bar_chart(risk_df.set_index("Metric")["Percent Flagged"])

    st.divider()
    st.subheader("Risk Factor Count by Record")
    count_data = filtered["risk_factor_count"].value_counts().sort_index()
    st.bar_chart(count_data)

# =========================================================================
# RAW RECORDS
# =========================================================================
with tab_records:
    st.header("Raw Records")
    st.caption("Use this for checking cleaned records. Consider hiding DOB before sharing publicly.")

    show_cols = [
        "id", "department", "year", "Age", "BMI", "WAIST", "TC", "HDL", "RTO", "GLU", "SYS", "DIA", "risk_factor_count"
    ]
    show_cols = [c for c in show_cols if c in filtered.columns]

    search_department = st.text_input("Search department name")
    records = filtered.copy()
    if search_department:
        records = records[records["department"].str.contains(search_department, case=False, na=False)]

    st.dataframe(records[show_cols], use_container_width=True, hide_index=True)

    csv = records[show_cols].to_csv(index=False).encode("utf-8")
    st.download_button("Download filtered records as CSV", csv, "filtered_biometric_records.csv", "text/csv")

# =========================================================================
# DATA SOURCES
# =========================================================================
with tab_sources:
    st.header("Data Sources")
    sources = load_sources()
    if sources.empty:
        st.info("No data source records found yet.")
    else:
        st.dataframe(sources, use_container_width=True, hide_index=True)
