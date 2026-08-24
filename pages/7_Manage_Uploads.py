
import os
import sqlite3

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Manage Biometric Uploads",
    page_icon="🗑️",
    layout="wide",
)

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(THIS_DIR)

_same_project_dir = os.path.join(PROJECT_DIR, "biometric.db")
_data_dir = os.path.join(PROJECT_DIR, "data", "biometric.db")

DB_PATH = _same_project_dir if os.path.exists(_same_project_dir) else _data_dir


def connect_db():
    return sqlite3.connect(DB_PATH)


def load_uploads():
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
    except Exception as e:
        conn.close()
        st.error(f"Could not read the data_sources table: {e}")
        st.stop()

    conn.close()
    return df


def count_biometric_rows(upload_hash):
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

        count = result[0] if result else 0

    except Exception:
        count = 0

    conn.close()
    return count


def delete_upload(upload_hash):
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


st.title("Manage Uploaded Department Files")

st.write(
    "Use this page to remove an incorrectly uploaded department file. "
    "Deleting an upload removes both its cleaned biometric records and "
    "its entry in the Data Sources table."
)

st.warning(
    "Deletion is permanent. Make sure you select the correct department, "
    "year, and filename before confirming."
)

uploads = load_uploads()

if uploads.empty:
    st.info("There are currently no uploaded department files to manage.")
    st.stop()

st.subheader("Current Uploads")

display_columns = [
    "department",
    "year",
    "filename",
    "records_uploaded",
    "uploaded_at",
]

available_display_columns = [
    col for col in display_columns if col in uploads.columns
]

st.dataframe(
    uploads[available_display_columns],
    use_container_width=True,
    hide_index=True,
)

st.divider()
st.subheader("Delete an Upload")

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
    "Select the upload you want to delete",
    options=uploads["selection_label"].tolist(),
    index=None,
    placeholder="Choose a department file...",
)

if selected_label is None:
    st.info("Select an upload above to see its details.")
    st.stop()

selected = uploads.loc[
    uploads["selection_label"] == selected_label
].iloc[0]

selected_hash = selected["upload_hash"]
actual_record_count = count_biometric_rows(selected_hash)

st.subheader("Selected Upload")

c1, c2, c3, c4 = st.columns(4)

c1.metric("Department", selected["department"])
c2.metric(
    "Year",
    int(selected["year"]) if pd.notna(selected["year"]) else "Unknown",
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
        "The Data Sources entry can still be deleted, but review this carefully."
    )

st.divider()
st.subheader("Confirm Permanent Deletion")

confirm_delete = st.checkbox(
    "I understand that this will permanently delete this uploaded file's "
    "records from the database."
)

confirmation_text = st.text_input(
    "Type DELETE to confirm",
    placeholder="DELETE",
)

delete_ready = confirm_delete and confirmation_text.strip().upper() == "DELETE"

if st.button(
    "Permanently Delete Selected Upload",
    type="primary",
    disabled=not delete_ready,
):
    try:
        biometric_deleted, source_deleted = delete_upload(selected_hash)

        st.cache_data.clear()

        st.success(
            f"Deleted {biometric_deleted} biometric record(s) and "
            f"{source_deleted} data-source record(s)."
        )

        st.rerun()

    except Exception as e:
        st.error(f"The upload could not be deleted: {e}")
