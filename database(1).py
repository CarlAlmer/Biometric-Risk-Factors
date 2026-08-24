import os
import sqlite3

import pandas as pd
import streamlit as st


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "biometric.db")


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


def upload_already_exists(upload_hash):
    """Return True when the exact same file has already been uploaded."""
    conn = connect_db()
    try:
        query = "SELECT COUNT(*) FROM data_sources WHERE upload_hash = ?"
        count = pd.read_sql_query(query, conn, params=(upload_hash,)).iloc[0, 0]
    except Exception:
        count = 0
    finally:
        conn.close()

    return count > 0


def department_year_exists(department, year):
    """
    Return True when the database already contains a source for the same
    department/town and year. Department matching is case-insensitive.
    """
    conn = connect_db()
    try:
        query = """
            SELECT COUNT(*)
            FROM data_sources
            WHERE LOWER(TRIM(department)) = LOWER(TRIM(?))
              AND year = ?
        """
        count = pd.read_sql_query(
            query,
            conn,
            params=(department, int(year)),
        ).iloc[0, 0]
    except Exception:
        count = 0
    finally:
        conn.close()

    return count > 0


def get_department_year_source(department, year):
    """
    Return the most recent data_sources row for a department/year pair.
    Used by the upload review dialog to show what would be replaced.
    """
    conn = connect_db()
    try:
        query = """
            SELECT
                source_id,
                department,
                year,
                filename,
                upload_hash,
                records_uploaded,
                uploaded_at
            FROM data_sources
            WHERE LOWER(TRIM(department)) = LOWER(TRIM(?))
              AND year = ?
            ORDER BY uploaded_at DESC, source_id DESC
            LIMIT 1
        """
        df = pd.read_sql_query(
            query,
            conn,
            params=(department, int(year)),
        )
    except Exception:
        df = pd.DataFrame()
    finally:
        conn.close()

    if df.empty:
        return None

    return df.iloc[0].to_dict()


def save_to_database(df, department, year, filename, upload_hash, uploaded_at):
    conn = connect_db()

    try:
        df.to_sql("biometric_data", conn, if_exists="append", index=False)

        source_df = pd.DataFrame([{
            "department": department.strip(),
            "year": int(year),
            "filename": filename,
            "upload_hash": upload_hash,
            "records_uploaded": len(df),
            "uploaded_at": uploaded_at,
        }])

        source_df.to_sql("data_sources", conn, if_exists="append", index=False)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def replace_department_year(
    df,
    department,
    year,
    filename,
    upload_hash,
    uploaded_at,
):
    """
    Replace all stored data for one department/year with the reviewed upload.

    The delete and insert happen in one database transaction so a failed insert
    does not leave the existing department/year removed.
    """
    conn = connect_db()

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            DELETE FROM biometric_data
            WHERE LOWER(TRIM(department)) = LOWER(TRIM(?))
              AND year = ?
            """,
            (department, int(year)),
        )

        cursor.execute(
            """
            DELETE FROM data_sources
            WHERE LOWER(TRIM(department)) = LOWER(TRIM(?))
              AND year = ?
            """,
            (department, int(year)),
        )

        insert_df = df.copy()
        insert_df.to_sql(
            "biometric_data",
            conn,
            if_exists="append",
            index=False,
        )

        source_df = pd.DataFrame([{
            "department": department.strip(),
            "year": int(year),
            "filename": filename,
            "upload_hash": upload_hash,
            "records_uploaded": len(insert_df),
            "uploaded_at": uploaded_at,
        }])

        source_df.to_sql(
            "data_sources",
            conn,
            if_exists="append",
            index=False,
        )

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@st.cache_data
def load_biometric_data():
    conn = connect_db()
    try:
        df = pd.read_sql_query("SELECT * FROM biometric_data", conn)
    except Exception:
        df = pd.DataFrame()
    finally:
        conn.close()

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
    finally:
        conn.close()

    return df
