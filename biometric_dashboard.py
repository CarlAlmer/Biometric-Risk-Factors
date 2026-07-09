from datetime import datetime

import pandas as pd
import streamlit as st

from analysis import (
    METRIC_COLUMNS,
    RISK_RULES,
    add_risk_flags,
    apply_filters,
    prepare_numeric_columns,
    risk_percent,
    style_risk,
    summarize_by_department,
)
from cleaning import clean_biometric_file
from database import (
    create_tables,
    load_biometric_data,
    load_sources,
    save_to_database,
    upload_already_exists,
)
from plots import (
    department_comparison_chart,
    metric_distribution_chart,
    risk_factor_bar_chart,
    risk_factor_count_chart,
)


# ============================================================
# SETUP
# ============================================================
create_tables()

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
            cleaned_df, upload_hash, uploaded_at = clean_biometric_file(
                uploaded_file,
                department,
                year
            )

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
                        upload_hash,
                        uploaded_at,
                    )
                    st.cache_data.clear()
                    st.success("Data saved successfully.")
                    st.rerun()


# ============================================================
# LOAD DATA
# ============================================================
data = load_biometric_data()

if not data.empty:
    data = prepare_numeric_columns(data)
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

        avg_sys = filtered["SYS"].mean()
        avg_dia = filtered["DIA"].mean()
        if pd.notna(avg_sys) and pd.notna(avg_dia):
            c8.metric("Avg BP", f"{avg_sys:.0f}/{avg_dia:.0f}")
        else:
            c8.metric("Avg BP", "—")

        st.divider()
        st.subheader("Metric Distributions")

        available_metrics = [m for m in METRIC_COLUMNS if m in filtered.columns]
        if available_metrics:
            metric = st.selectbox("Choose a metric", available_metrics)
            metric_distribution_chart(filtered, metric)
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

            department_comparison_chart(summary, chart_metric)
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

            risk_factor_bar_chart(risk_df)

        st.divider()
        st.subheader("Risk Factor Count by Record")
        risk_factor_count_chart(filtered)


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
            "id", "department", "year", "Age", "BMI", "WAIST", "TC", "HDL",
            "RTO", "GLU", "SYS", "DIA", "risk_factor_count",
            "upload_filename", "uploaded_at",
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
