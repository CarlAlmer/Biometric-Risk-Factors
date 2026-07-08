import hashlib
import sqlite3
from datetime import datetime

import pandas as pd
import streamlit as st


# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="Firefighter Biometric Risk Dashboard",
    page_icon="🚒",
    layout="wide",
)


# ============================================================
# DATABASE SETUP
# ============================================================
DB_PATH = "biometric.db"


def connect_db():
    return sqlite3.connect(DB_PATH)


def create_tables():
    conn = connect_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS biometric_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            department TEXT,
            year INTEGER,
            DOB TEXT,
            Age REAL,
            BMI REAL,
            WAIST REAL,
            TC REAL,
            HDL REAL,
            RTO REAL,
            GLU REAL,
            SYS REAL,
            DIA REAL,
            upload_filename TEXT,
            upload_hash TEXT,
            uploaded_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS data_sources (
            source_id INTEGER PRIMARY KEY AUTOINCREMENT,
            department TEXT,
            year INTEGER,
            filename TEXT,
            upload_hash TEXT,
            records_uploaded INTEGER,
            uploaded_at TEXT
        )
    """)

    conn.commit()
    conn.close()


create_tables()


# ============================================================
# PASSWORD PROTECTION
# ============================================================
if "password" in st.secrets:
    password = st.text_input("Enter password", type="password")
    if password != st.secrets["password"]:
        st.warning("Please enter the correct password.")
        st.stop()


# ============================================================
# STYLING
# ============================================================
st.markdown(
    """
<style>
.risk-banner {
    background: linear-gradient(135deg, #7A0A1C 0%, #C8102E 60%, #7A0A1C 100%);
    padding: 1.2rem 2rem;
    border-radius: 8px;
    margin-bottom: 1.5rem;
}
.risk-banner h1 {
    margin: 0;
    font-size: 1.8rem;
    font-weight: 800;
    color: white;
}
.risk-banner p {
    margin: 0.2rem 0 0;
    font-size: 0.95rem;
    color: rgba(255,255,255,0.85);
}
div[data-testid="metric-container"] {
    border: 2px solid #C8102E;
    border-radius: 8px;
    padding: 0.75rem 1rem;
    background-color: #FBEEEE;
}
</style>
""",
    unsafe_allow_html=True,
)


# ============================================================
# CONSTANTS
# ============================================================
METRIC_COLUMNS = ["BMI", "WAIST", "TC", "HDL", "RTO", "GLU", "SYS", "DIA"]

RISK_RULES = {
    "BMI": (30, "high"),
    "WAIST": (40, "high"),
    "TC": (200, "high"),
    "HDL": (40, "low"),
    "RTO": (5, "high"),
    "GLU": (100, "high"),
    "SYS": (130, "high"),
    "DIA": (80, "high"),
}


# ============================================================
# CLEANING FUNCTIONS
# ============================================================
def file_hash(uploaded_file):
    file_bytes = uploaded_file.getvalue()
    return hashlib.md5(file_bytes).hexdigest()


def clean_column_names(df):
    df = df.copy()

    df = df.loc[:, ~df.columns.astype(str).str.contains("^Unnamed")]

    df.columns = (
        df.columns.astype(str)
        .str.strip()
        .str.upper()
        .str.replace(r"^\d+\s*", "", regex=True)
        .str.replace(" ", "_")
    )

    rename_map = {
        "DATE_OF_BIRTH": "DOB",
        "BIRTH_DATE": "DOB",
        "BP": "BP",
        "BLOOD_PRESSURE": "BP",
        "TOTAL_CHOLESTEROL": "TC",
        "CHOLESTEROL": "TC",
        "GLUCOSE": "GLU",
        "WAIST_CIRCUMFERENCE": "WAIST",
        "TC/HDL": "RTO",
        "RATIO": "RTO",
    }

    df = df.rename(columns=rename_map)
    return df


def split_blood_pressure(df):
    df = df.copy()

    if "BP" in df.columns and ("SYS" not in df.columns or "DIA" not in df.columns):
        bp_split = df["BP"].astype(str).str.extract(r"(\d{2,3})\s*/\s*(\d{2,3})")
        df["SYS"] = pd.to_numeric(bp_split[0], errors="coerce")
        df["DIA"] = pd.to_numeric(bp_split[1], errors="coerce")

    return df


def clean_biometric_file(uploaded_file, department, year):
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

    df = clean_column_names(df)
    df = split_blood_pressure(df)

    keep_cols = ["DOB", "Age", "BMI", "WAIST", "TC", "HDL", "RTO", "GLU", "SYS", "DIA"]
    existing_cols = [c for c in keep_cols if c in df.columns]
    df = df[existing_cols].copy()

    numeric_cols = ["Age", "BMI", "WAIST", "TC", "HDL", "RTO", "GLU", "SYS", "DIA"]

    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "DOB" in df.columns:
        df["DOB"] = pd.to_datetime(df["DOB"], errors="coerce")
        if "Age" not in df.columns or df["Age"].isna().all():
            today = pd.Timestamp.today()
            df["Age"] = ((today - df["DOB"]).dt.days / 365.25).round(1)
        df["DOB"] = df["DOB"].dt.strftime("%Y-%m-%d")

    for col in keep_cols:
        if col not in df.columns:
            df[col] = None

    df["department"] = department
    df["year"] = int(year)
    df["upload_filename"] = uploaded_file.name
    df["upload_hash"] = file_hash(uploaded_file)
    df["uploaded_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    final_cols = [
        "department", "year", "DOB", "Age", "BMI", "WAIST", "TC", "HDL",
        "RTO", "GLU", "SYS", "DIA", "upload_filename", "upload_hash", "uploaded_at"
    ]

    return df[final_cols]


# ============================================================
# DATABASE FUNCTIONS
# ============================================================
def upload_already_exists(upload_hash):
    conn = connect_db()
    query = "SELECT COUNT(*) FROM data_sources WHERE upload_hash = ?"
    count = pd.read_sql_query(query, conn, params=(upload_hash,)).iloc[0, 0]
    conn.close()
    return count > 0


def save_to_database(df, department, year, filename, upload_hash):
    conn = connect_db()

    df.to_sql("biometric_data", conn, if_exists="append", index=False)

    source_df = pd.DataFrame([{
        "department": department,
        "year": int(year),
        "filename": filename,
        "upload_hash": upload_hash,
        "records_uploaded": len(df),
        "uploaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }])

    source_df.to_sql("data_sources", conn, if_exists="append", index=False)

    conn.close()


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
    df = pd.read_sql_query("SELECT * FROM data_sources ORDER BY uploaded_at DESC", conn)
    conn.close()
    return df


# ============================================================
# ANALYSIS FUNCTIONS
# ============================================================
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
    else:
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
        summary[f"Pct_{metric}_Risk"] = grouped.apply(
            lambda g, m=metric: risk_percent(g, m)
        ).values

    return summary


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


# ============================================================
# HEADER
# ============================================================
st.markdown(
    """
<div class="risk-banner">
    <h1>Firefighter Biometric Risk Dashboard</h1>
    <p>Upload, clean, store, and analyze department biometric screening data</p>
</div>
""",
    unsafe_allow_html=True,
)


# ============================================================
# TABS
# ============================================================
tab_upload, tab_overview, tab_departments, tab_risk, tab_records, tab_sources = st.tabs(
    ["Upload Data", "Overview", "Department Comparison", "Risk Factors", "Raw Records", "Data Sources"]
)


# ============================================================
# UPLOAD TAB
# ============================================================
with tab_upload:
    st.header("Upload New Department Data")

    st.info(
        "Upload an Excel or CSV file. The app will clean the file, preview it, "
        "and then save it into the database."
    )

    uploaded_file = st.file_uploader(
        "Upload department file",
        type=["xlsx", "xls", "csv"]
    )

    department = st.text_input("Department name")
    year = st.number_input("Year", min_value=2000, max_value=2100, value=datetime.now().year)

    if uploaded_file is not None:
        if not department:
            st.warning("Enter a department name before saving.")
        else:
            cleaned_df = clean_biometric_file(uploaded_file, department, year)
            upload_hash = file_hash(uploaded_file)

            st.subheader("Cleaned Preview")
            st.dataframe(cleaned_df.head(50), use_container_width=True, hide_index=True)

            st.write(f"Records found: **{len(cleaned_df)}**")

            if upload_already_exists(upload_hash):
                st.error("This exact file has already been uploaded.")
            else:
                if st.button("Save Cleaned Data to Database"):
                    save_to_database(
                        cleaned_df,
                        department,
                        year,
                        uploaded_file.name,
                        upload_hash
                    )

                    st.cache_data.clear()
                    st.success("Data saved successfully.")
                    st.rerun()


# ============================================================
# LOAD DATA FOR DASHBOARD
# ============================================================
data = load_biometric_data()

if not data.empty:
    data = add_risk_flags(data)

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

    filtered = data.copy()

    if selected_departments:
        filtered = filtered[filtered["department"].isin(selected_departments)]

    if selected_years:
        filtered = filtered[filtered["year"].isin(selected_years)]

    if selected_age:
        filtered = filtered[
            (filtered["Age"] >= selected_age[0]) &
            (filtered["Age"] <= selected_age[1])
        ]

else:
    filtered = pd.DataFrame()


# ============================================================
# OVERVIEW TAB
# ============================================================
with tab_overview:
    st.header("Overview")

    if filtered.empty:
        st.warning("No records found yet. Upload data first.")
    else:
        c1, c2, c3, c4 = st.columns(4)

        c1.metric("Records", f"{len(filtered):,}")
        c2.metric("Departments", filtered["department"].nunique())
        c3.metric("Avg Age", f"{filtered['Age'].mean():.1f}")
        c4.metric("Avg Risk Factors", f"{filtered['risk_factor_count'].mean():.2f}")

        c5, c6, c7, c8 = st.columns(4)

        c5.metric("Avg BMI", f"{filtered['BMI'].mean():.1f}")
        c6.metric("Avg Glucose", f"{filtered['GLU'].mean():.1f}")
        c7.metric("Avg Total Chol.", f"{filtered['TC'].mean():.1f}")
        c8.metric("Avg BP", f"{filtered['SYS'].mean():.0f}/{filtered['DIA'].mean():.0f}")

        st.divider()

        metric = st.selectbox(
            "Choose a metric",
            [m for m in METRIC_COLUMNS if m in filtered.columns]
        )

        chart_df = filtered[[metric]].dropna()

        if not chart_df.empty:
            st.bar_chart(chart_df[metric].value_counts().sort_index())
        else:
            st.info("No values available for this metric.")


# ============================================================
# DEPARTMENT TAB
# ============================================================
with tab_departments:
    st.header("Department Comparison")

    if filtered.empty:
        st.warning("No data available.")
    else:
        summary = summarize_by_department(filtered)

        chart_metric = st.selectbox(
            "Compare departments by",
            [
                "Avg_Risk_Factors", "Avg_BMI", "Avg_WAIST", "Avg_TC",
                "Avg_HDL", "Avg_RTO", "Avg_GLU", "Avg_SYS", "Avg_DIA"
            ]
        )

        chart_data = summary.pivot_table(
            index="department",
            columns="year",
            values=chart_metric,
            aggfunc="mean"
        )

        st.bar_chart(chart_data)

        st.divider()

        st.dataframe(
            summary,
            use_container_width=True,
            hide_index=True
        )


# ============================================================
# RISK TAB
# ============================================================
with tab_risk:
    st.header("Risk Factors")
    st.caption("These flags are for descriptive screening only, not medical diagnosis.")

    if filtered.empty:
        st.warning("No data available.")
    else:
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

        st.dataframe(
            risk_df.style.format({"Percent Flagged": "{:.1f}%"}).map(
                style_risk,
                subset=["Percent Flagged"]
            ),
            use_container_width=True,
            hide_index=True
        )

        st.bar_chart(risk_df.set_index("Metric")["Percent Flagged"])

        st.divider()

        st.subheader("Risk Factor Count by Record")
        st.bar_chart(filtered["risk_factor_count"].value_counts().sort_index())


# ============================================================
# RAW RECORDS TAB
# ============================================================
with tab_records:
    st.header("Raw Records")

    if filtered.empty:
        st.warning("No records available.")
    else:
        show_cols = [
            "id", "department", "year", "Age", "BMI", "WAIST", "TC", "HDL",
            "RTO", "GLU", "SYS", "DIA", "risk_factor_count"
        ]

        show_cols = [c for c in show_cols if c in filtered.columns]

        search_department = st.text_input("Search department name")

        records = filtered.copy()

        if search_department:
            records = records[
                records["department"].str.contains(search_department, case=False, na=False)
            ]

        st.dataframe(records[show_cols], use_container_width=True, hide_index=True)

        csv = records[show_cols].to_csv(index=False).encode("utf-8")

        st.download_button(
            "Download filtered records as CSV",
            csv,
            "filtered_biometric_records.csv",
            "text/csv"
        )


# ============================================================
# DATA SOURCES TAB
# ============================================================
with tab_sources:
    st.header("Data Sources")

    sources = load_sources()

    if sources.empty:
        st.info("No uploaded files yet.")
    else:
        st.dataframe(sources, use_container_width=True, hide_index=True)
