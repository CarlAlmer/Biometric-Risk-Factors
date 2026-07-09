import hashlib
import os
import sqlite3
from datetime import datetime

import pandas as pd
import streamlit as st


# ============================================================
# PATH + DATABASE
# ============================================================
_same_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "biometric.db")
_up_one = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../data/biometric.db")
DB_PATH = _same_dir if os.path.exists(_same_dir) else _up_one


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
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="Firefighter Biometric Risk Dashboard",
    page_icon="🚒",
    layout="wide",
)


# ============================================================
# PASSWORD PROTECTION
# ============================================================
if "password" in st.secrets:
    password = st.text_input("Enter password", type="password")
    if password != st.secrets["password"]:
        st.warning("Please enter the correct password.")
        st.stop()


# ============================================================
# CSS
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
.stTabs [data-baseweb="tab-highlight"] {
    background-color: #C8102E !important;
}
.stTabs [aria-selected="true"] {
    color: #C8102E !important;
    font-weight: 700;
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
# FILE READING + CLEANING
# ============================================================
def file_hash(uploaded_file):
    uploaded_file.seek(0)
    file_bytes = uploaded_file.getvalue()
    uploaded_file.seek(0)
    return hashlib.md5(file_bytes).hexdigest()


def read_uploaded_file(uploaded_file):
    """
    Reads CSV or Excel files.

    Many department files have a title row first, then the real column names
    on the second row, so Excel files are read with header=1.
    """
    uploaded_file.seek(0)

    if uploaded_file.name.lower().endswith(".csv"):
        return pd.read_csv(uploaded_file)

    try:
        return pd.read_excel(uploaded_file, header=1, engine="openpyxl")
    except ImportError:
        st.error(
            "Missing package: openpyxl. Add openpyxl to requirements.txt, "
            "push to GitHub, and redeploy the Streamlit app."
        )
        st.stop()
    except Exception as e:
        st.error(f"Could not read Excel file: {e}")
        st.stop()


def clean_column_names(df):
    df = df.copy()

    df = df.loc[:, ~df.columns.astype(str).str.contains("^Unnamed")]

    df.columns = (
        df.columns.astype(str)
        .str.strip()
        .str.upper()
        .str.replace(r"^\d+\s*", "", regex=True)
        .str.replace(" ", "_")
        .str.replace(".", "", regex=False)
    )

    rename_map = {
        "DATE_OF_BIRTH": "DOB",
        "BIRTH_DATE": "DOB",
        "BIRTHDATE": "DOB",
        "AGE": "Age",
        "BP": "BP",
        "BLOOD_PRESSURE": "BP",
        "BLOOD_PRESSURE_READING": "BP",
        "TOTAL_CHOLESTEROL": "TC",
        "CHOLESTEROL": "TC",
        "GLUCOSE": "GLU",
        "WAIST_CIRCUMFERENCE": "WAIST",
        "TC/HDL": "RTO",
        "TC_HDL": "RTO",
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
    df = read_uploaded_file(uploaded_file)

    df = clean_column_names(df)
    df = split_blood_pressure(df)

    keep_cols = [
        "DOB",
        "Age",
        "BMI",
        "WAIST",
        "TC",
        "HDL",
        "RTO",
        "GLU",
        "SYS",
        "DIA",
    ]

    existing_cols = [col for col in keep_cols if col in df.columns]
    df = df[existing_cols].copy()

    for col in keep_cols:
        if col not in df.columns:
            df[col] = None

    numeric_cols = ["Age", "BMI", "WAIST", "TC", "HDL", "RTO", "GLU", "SYS", "DIA"]

    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    if "DOB" in df.columns:
        df["DOB"] = pd.to_datetime(df["DOB"], errors="coerce")

        if df["Age"].isna().all():
            today = pd.Timestamp.today()
            df["Age"] = ((today - df["DOB"]).dt.days / 365.25).round(1)

        df["DOB"] = df["DOB"].dt.strftime("%Y-%m-%d")

    df["department"] = department
    df["year"] = int(year)
    df["upload_filename"] = uploaded_file.name
    df["upload_hash"] = file_hash(uploaded_file)
    df["uploaded_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    final_cols = [
        "department",
        "year",
        "DOB",
        "Age",
        "BMI",
        "WAIST",
        "TC",
        "HDL",
        "RTO",
        "GLU",
        "SYS",
        "DIA",
        "upload_filename",
        "upload_hash",
        "uploaded_at",
    ]

    return df[final_cols]


# ============================================================
# DATABASE FUNCTIONS
# ============================================================
def upload_already_exists(upload_hash):
    conn = connect_db()

    try:
        query = "SELECT COUNT(*) FROM data_sources WHERE upload_hash = ?"
        count = pd.read_sql_query(query, conn, params=(upload_hash,)).iloc[0, 0]
    except Exception:
        count = 0

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

    try:
        df = pd.read_sql_query("SELECT * FROM biometric_data", conn)
    except Exception:
        df = pd.DataFrame()

    conn.close()

    for col in METRIC_COLUMNS + ["Age", "year"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


@st.cache_data
def load_sources():
    conn = connect_db()

    try:
        df = pd.read_sql_query(
            "SELECT * FROM data_sources ORDER BY uploaded_at DESC",
            conn
        )
    except Exception:
        df = pd.DataFrame()

    conn.close()

    return df


# ============================================================
# DASHBOARD FUNCTIONS
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


def apply_filters(df, departments, years, age_range):
    out = df.copy()

    if departments:
        out = out[out["department"].isin(departments)]

    if years:
        out = out[out["year"].isin(years)]

    if "Age" in out.columns and age_range:
        out = out[
            (out["Age"] >= age_range[0]) &
            (out["Age"] <= age_range[1])
        ]

    return out


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
    [
        "Upload Data",
        "Overview",
        "Department Comparison",
        "Risk Factors",
        "Raw Records",
        "Data Sources",
    ]
)


# ============================================================
# UPLOAD TAB
# ============================================================
with tab_upload:
    st.header("Upload New Department Data")

    st.info(
        "Upload an Excel or CSV file. The app will read the file, clean it, "
        "show a preview, and then save the cleaned data to the database."
    )

    uploaded_file = st.file_uploader(
        "Upload department biometric file",
        type=["xlsx", "xls", "csv"]
    )

    department = st.text_input("Department name")

    year = st.number_input(
        "Year",
        min_value=2000,
        max_value=2100,
        value=datetime.now().year,
        step=1
    )

    if uploaded_file is not None:
        if not department:
            st.warning("Enter a department name before saving.")
        else:
            upload_hash = file_hash(uploaded_file)
            cleaned_df = clean_biometric_file(uploaded_file, department, year)

            st.subheader("Cleaned Preview")
            st.dataframe(cleaned_df.head(50), use_container_width=True, hide_index=True)

            st.write(f"Records found: **{len(cleaned_df)}**")

            missing_all = cleaned_df[METRIC_COLUMNS].isna().all(axis=1).sum()
            if missing_all > 0:
                st.warning(
                    f"{missing_all} rows appear to have no biometric values. "
                    "You may want to check the file before saving."
                )

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
# LOAD DATA
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
        selected_age = st.sidebar.slider(
            "Age range",
            min_age,
            max_age,
            (min_age, max_age)
        )
    else:
        selected_age = None

    filtered = apply_filters(
        data,
        selected_departments,
        selected_years,
        selected_age
    )

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

        avg_age = filtered["Age"].mean()
        avg_risk = filtered["risk_factor_count"].mean()

        c3.metric("Avg Age", f"{avg_age:.1f}" if pd.notna(avg_age) else "—")
        c4.metric("Avg Risk Factors", f"{avg_risk:.2f}" if pd.notna(avg_risk) else "—")

        c5, c6, c7, c8 = st.columns(4)

        c5.metric("Avg BMI", f"{filtered['BMI'].mean():.1f}")
        c6.metric("Avg Glucose", f"{filtered['GLU'].mean():.1f}")
        c7.metric("Avg Total Chol.", f"{filtered['TC'].mean():.1f}")

        if {"SYS", "DIA"}.issubset(filtered.columns):
            avg_sys = filtered["SYS"].mean()
            avg_dia = filtered["DIA"].mean()
            if pd.notna(avg_sys) and pd.notna(avg_dia):
                c8.metric("Avg BP", f"{avg_sys:.0f}/{avg_dia:.0f}")
            else:
                c8.metric("Avg BP", "—")
        else:
            c8.metric("Avg BP", "—")

        st.divider()

        st.subheader("Metric Distributions")

        available_metrics = [m for m in METRIC_COLUMNS if m in filtered.columns]

        if available_metrics:
            metric = st.selectbox("Choose a metric", available_metrics)
            chart_df = filtered[[metric]].dropna()

            if not chart_df.empty:
                st.bar_chart(chart_df[metric].value_counts().sort_index())
            else:
                st.info("No values available for this metric.")
        else:
            st.info("No metric columns available.")


# ============================================================
# DEPARTMENT COMPARISON TAB
# ============================================================
with tab_departments:
    st.header("Department Comparison")

    if filtered.empty:
        st.warning("No data available.")
    else:
        summary = summarize_by_department(filtered)

        if summary.empty:
            st.warning("No summary data available.")
        else:
            chart_metric = st.selectbox(
                "Compare departments by",
                [
                    "Avg_Risk_Factors",
                    "Avg_BMI",
                    "Avg_WAIST",
                    "Avg_TC",
                    "Avg_HDL",
                    "Avg_RTO",
                    "Avg_GLU",
                    "Avg_SYS",
                    "Avg_DIA",
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

            format_cols = {
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
            }

            pct_cols = [c for c in summary.columns if c.startswith("Pct_")]

            st.dataframe(
                summary.style.format(format_cols, na_rep="—").map(
                    style_risk,
                    subset=pct_cols
                ),
                use_container_width=True,
                hide_index=True
            )


# ============================================================
# RISK FACTORS TAB
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

        if not risk_df.empty:
            st.dataframe(
                risk_df.style.format(
                    {"Percent Flagged": "{:.1f}%"},
                    na_rep="—"
                ).map(
                    style_risk,
                    subset=["Percent Flagged"]
                ),
                use_container_width=True,
                hide_index=True
            )

            st.bar_chart(risk_df.set_index("Metric")["Percent Flagged"])

        st.divider()

        st.subheader("Risk Factor Count by Record")

        if "risk_factor_count" in filtered.columns:
            st.bar_chart(filtered["risk_factor_count"].value_counts().sort_index())
        else:
            st.info("Risk factor counts are not available.")


# ============================================================
# RAW RECORDS TAB
# ============================================================
with tab_records:
    st.header("Raw Records")
    st.caption("Use this for checking cleaned records. Consider hiding DOB before sharing publicly.")

    if filtered.empty:
        st.warning("No records available.")
    else:
        show_cols = [
            "id",
            "department",
            "year",
            "Age",
            "BMI",
            "WAIST",
            "TC",
            "HDL",
            "RTO",
            "GLU",
            "SYS",
            "DIA",
            "risk_factor_count",
            "upload_filename",
            "uploaded_at",
        ]

        show_cols = [c for c in show_cols if c in filtered.columns]

        search_department = st.text_input("Search department name")

        records = filtered.copy()

        if search_department:
            records = records[
                records["department"].str.contains(
                    search_department,
                    case=False,
                    na=False
                )
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
