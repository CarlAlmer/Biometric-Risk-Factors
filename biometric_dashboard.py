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
from cleaning import clean_biometric_file, detect_department_and_year
from database import (
    connect_db,
    create_tables,
    department_year_exists,
    get_department_year_source,
    load_biometric_data,
    load_sources,
    replace_department_year,
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
# UPLOAD MANAGEMENT FUNCTIONS
# ============================================================
def load_uploads_for_management():
    """
    Load one row per uploaded source file so uploads can be reviewed
    and deleted safely.
    """
    conn = connect_db()

    try:
        df = pd.read_sql_query(
            """
            SELECT
                source_id,
                department,
                year,
                filename,
                upload_hash,
                records_uploaded,
                uploaded_at
            FROM data_sources
            ORDER BY year DESC, department ASC, uploaded_at DESC
            """,
            conn,
        )
    except Exception:
        df = pd.DataFrame()
    finally:
        conn.close()

    return df


def count_rows_for_upload(upload_hash):
    """
    Count biometric_data rows belonging to one exact uploaded file.
    """
    conn = connect_db()

    try:
        result = conn.execute(
            """
            SELECT COUNT(*)
            FROM biometric_data
            WHERE upload_hash = ?
            """,
            (upload_hash,),
        ).fetchone()

        return result[0] if result else 0
    except Exception:
        return 0
    finally:
        conn.close()


def delete_upload(upload_hash):
    """
    Permanently delete both:
      1. biometric_data rows created from the selected upload
      2. its matching data_sources record

    The upload hash is used so only the exact selected file is removed.
    """
    conn = connect_db()

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            DELETE FROM biometric_data
            WHERE upload_hash = ?
            """,
            (upload_hash,),
        )
        biometric_rows_deleted = cursor.rowcount

        cursor.execute(
            """
            DELETE FROM data_sources
            WHERE upload_hash = ?
            """,
            (upload_hash,),
        )
        source_rows_deleted = cursor.rowcount

        conn.commit()

        return biometric_rows_deleted, source_rows_deleted

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


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
(
    tab_upload,
    tab_overview,
    tab_departments,
    tab_risk,
    tab_records,
    tab_sources,
    tab_manage,
) = st.tabs(
    [
        "Upload Data",
        "Overview",
        "Department Comparison",
        "Risk Factors",
        "Raw Records",
        "Data Sources",
        "Manage Uploads",
    ]
)


# ============================================================
# UPLOAD REVIEW DIALOG
# ============================================================
@st.dialog("Review Upload")
def review_upload_dialog(uploaded_file, detected_department, detected_year):
    st.write(
        "The app detected the department and year from the filename. "
        "Review them below and correct anything that is wrong before storing the file."
    )

    st.write(f"**File:** {uploaded_file.name}")

    department = st.text_input(
        "Department / town",
        value=detected_department or "",
        help="Use only the town or city name, such as Stillwater.",
        key="review_department",
    )

    year_value = detected_year if detected_year is not None else 2026
    year = st.number_input(
        "Year",
        min_value=2000,
        max_value=2100,
        value=int(year_value),
        step=1,
        key="review_year",
    )

    department = department.strip()

    if not department:
        st.warning("Enter the town or city name before continuing.")
        return

    cleaned_df, upload_hash, uploaded_at = clean_biometric_file(
        uploaded_file,
        department,
        year,
    )

    st.divider()
    st.subheader("File Check")

    c1, c2, c3 = st.columns(3)
    c1.metric("Department", department)
    c2.metric("Year", int(year))
    c3.metric("Records", len(cleaned_df))

    missing_all = cleaned_df[METRIC_COLUMNS].isna().all(axis=1).sum()
    if missing_all > 0:
        st.warning(
            f"{missing_all} row(s) have no biometric values. "
            "Review the preview before storing this file."
        )

    with st.expander("Preview cleaned data", expanded=False):
        st.dataframe(
            cleaned_df.head(50),
            use_container_width=True,
            hide_index=True,
        )

    if upload_already_exists(upload_hash):
        st.error("This exact file has already been uploaded.")
        st.caption("Nothing has been changed in the database.")
        return

    existing_source = None
    if department_year_exists(department, year):
        existing_source = get_department_year_source(department, year)

    if existing_source is None:
        st.success(
            f"No existing {department} {int(year)} dataset was found. "
            "This upload is ready to store."
        )

        reviewed = st.checkbox(
            "I reviewed the department, year, and file preview.",
            key="confirm_new_upload_review",
        )

        if st.button(
            "Store Department Data",
            type="primary",
            disabled=not reviewed,
            use_container_width=True,
            key="store_new_department_data",
        ):
            try:
                save_to_database(
                    cleaned_df,
                    department,
                    year,
                    uploaded_file.name,
                    upload_hash,
                    uploaded_at,
                )
                st.cache_data.clear()
                st.session_state["upload_success_message"] = (
                    f"Stored {department} {int(year)} successfully "
                    f"with {len(cleaned_df)} record(s)."
                )
                st.session_state["upload_widget_key"] += 1
                st.rerun()
            except Exception as e:
                st.error(f"The file could not be stored: {e}")

    else:
        st.warning(
            f"A dataset for {department} {int(year)} already exists. "
            "Storing a second copy could duplicate the department's records."
        )

        st.write(f"**Existing file:** {existing_source.get('filename', 'Unknown')}")
        st.write(
            f"**Existing records:** "
            f"{existing_source.get('records_uploaded', 'Unknown')}"
        )
        st.write(
            f"**Originally uploaded:** "
            f"{existing_source.get('uploaded_at', 'Unknown')}"
        )

        st.error(
            "Replacing will permanently remove the existing data for this "
            "department and year and store this reviewed file in its place."
        )

        confirm_replace = st.checkbox(
            f"I want to replace the existing {department} {int(year)} dataset.",
            key="confirm_department_year_replace",
        )

        if st.button(
            "Replace Existing Data",
            type="primary",
            disabled=not confirm_replace,
            use_container_width=True,
            key="replace_department_year_data",
        ):
            try:
                replace_department_year(
                    cleaned_df,
                    department,
                    year,
                    uploaded_file.name,
                    upload_hash,
                    uploaded_at,
                )
                st.cache_data.clear()
                st.session_state["upload_success_message"] = (
                    f"Replaced {department} {int(year)} successfully "
                    f"with {len(cleaned_df)} record(s)."
                )
                st.session_state["upload_widget_key"] += 1
                st.rerun()
            except Exception as e:
                st.error(f"The existing dataset could not be replaced: {e}")


# ============================================================
# UPLOAD TAB
# ============================================================
with tab_upload:
    st.header("Upload New Department Data")

    st.info(
        "Step 1: choose a department file. The app will detect the town and "
        "year from the filename. Step 2: review and correct that information "
        "before anything is stored in the database."
    )

    if "upload_widget_key" not in st.session_state:
        st.session_state["upload_widget_key"] = 0

    if "upload_success_message" in st.session_state:
        st.success(st.session_state.pop("upload_success_message"))

    uploaded_file = st.file_uploader(
        "Choose department biometric file",
        type=["xlsx", "xls", "csv"],
        key=f"department_upload_{st.session_state['upload_widget_key']}",
    )

    if uploaded_file is None:
        st.caption(
            "The filename should include the town/city and year. Examples: "
            "Stillwater Fire Department 2025.xlsx, "
            "Stillwater_Fire_Department_2025.xlsx, or 2025-Stillwater-FD.xlsx."
        )
    else:
        detected_department, detected_year = detect_department_and_year(
            uploaded_file.name
        )

        st.subheader("Detected from Filename")

        c1, c2 = st.columns(2)
        c1.metric(
            "Department / town",
            detected_department if detected_department else "Not detected",
        )
        c2.metric(
            "Year",
            detected_year if detected_year is not None else "Not detected",
        )

        if not detected_department or detected_year is None:
            st.warning(
                "The app could not confidently identify everything from the "
                "filename. You can correct the missing information in the review window."
            )
        else:
            st.success(
                "The filename was read successfully. Review the detected "
                "information before storing the file."
            )

        if st.button(
            "Review Upload",
            type="primary",
            use_container_width=True,
            key="open_upload_review",
        ):
            review_upload_dialog(
                uploaded_file,
                detected_department,
                detected_year,
            )


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


# ============================================================
# MANAGE UPLOADS TAB
# ============================================================
with tab_manage:
    st.header("Manage Uploaded Department Files")

    st.write(
        "Use this tab to remove a department file that was uploaded incorrectly. "
        "Deleting an upload removes both the cleaned biometric records created "
        "from that file and its entry in the Data Sources table."
    )

    st.warning(
        "Deletion is permanent. Check the department, year, filename, and upload "
        "date carefully before confirming."
    )

    uploads = load_uploads_for_management()

    if uploads.empty:
        st.info("There are currently no uploaded department files to manage.")
    else:
        st.subheader("Current Uploads")

        display_columns = [
            "department",
            "year",
            "filename",
            "records_uploaded",
            "uploaded_at",
        ]

        display_columns = [
            col for col in display_columns
            if col in uploads.columns
        ]

        st.dataframe(
            uploads[display_columns],
            use_container_width=True,
            hide_index=True,
        )

        st.divider()
        st.subheader("Choose an Upload to Delete")

        uploads = uploads.copy()

        uploads["selection_label"] = uploads.apply(
            lambda row: (
                f"{row['department']} | "
                f"{int(row['year']) if pd.notna(row['year']) else 'Unknown year'} | "
                f"{row['filename']} | "
                f"Uploaded: {row['uploaded_at']}"
            ),
            axis=1,
        )

        selected_label = st.selectbox(
            "Select the exact upload",
            options=uploads["selection_label"].tolist(),
            index=None,
            placeholder="Choose a department file...",
            key="manage_upload_selection",
        )

        if selected_label is None:
            st.info(
                "Select a file above. Its details and delete confirmation "
                "will appear here."
            )
        else:
            selected = uploads.loc[
                uploads["selection_label"] == selected_label
            ].iloc[0]

            selected_hash = selected["upload_hash"]
            actual_record_count = count_rows_for_upload(selected_hash)

            st.subheader("Review Selected Upload")

            c1, c2, c3, c4 = st.columns(4)

            c1.metric("Department", selected["department"])
            c2.metric(
                "Year",
                int(selected["year"])
                if pd.notna(selected["year"])
                else "Unknown",
            )
            c3.metric("Database Records", actual_record_count)
            c4.metric(
                "Reported Records",
                int(selected["records_uploaded"])
                if pd.notna(selected["records_uploaded"])
                else "Unknown",
            )

            st.write(f"**Filename:** {selected['filename']}")
            st.write(f"**Uploaded:** {selected['uploaded_at']}")

            if actual_record_count == 0:
                st.warning(
                    "No biometric_data rows were found for this upload hash. "
                    "The Data Sources record can still be removed, but review "
                    "the selection carefully."
                )

            st.divider()
            st.subheader("Confirm Permanent Deletion")

            confirm_delete = st.checkbox(
                "I understand that this permanently deletes this upload's "
                "records from the database.",
                key="confirm_upload_delete",
            )

            confirmation_text = st.text_input(
                "Type DELETE to confirm",
                placeholder="DELETE",
                key="delete_confirmation_text",
            )

            delete_ready = (
                confirm_delete
                and confirmation_text.strip().upper() == "DELETE"
            )

            if st.button(
                "Permanently Delete Selected Upload",
                type="primary",
                disabled=not delete_ready,
                key="delete_selected_upload_button",
            ):
                try:
                    biometric_deleted, source_deleted = delete_upload(
                        selected_hash
                    )

                    st.cache_data.clear()

                    st.success(
                        f"Deleted {biometric_deleted} biometric record(s) "
                        f"and {source_deleted} data-source record(s)."
                    )

                    st.rerun()

                except Exception as e:
                    st.error(f"The upload could not be deleted: {e}")

