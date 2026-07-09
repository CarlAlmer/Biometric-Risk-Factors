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
    conn = connect_db()
    try:
        query = "SELECT COUNT(*) FROM data_sources WHERE upload_hash = ?"
        count = pd.read_sql_query(query, conn, params=(upload_hash,)).iloc[0, 0]
    except Exception:
        count = 0
    conn.close()
    return count > 0


def save_to_database(df, department, year, filename, upload_hash, uploaded_at):
    conn = connect_db()

    df.to_sql("biometric_data", conn, if_exists="append", index=False)

    source_df = pd.DataFrame([{
        "department": department,
        "year": int(year),
        "filename": filename,
        "upload_hash": upload_hash,
        "records_uploaded": len(df),
        "uploaded_at": uploaded_at,
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
