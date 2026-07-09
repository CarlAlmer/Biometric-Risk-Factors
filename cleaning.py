import pandas as pd
import streamlit as st

from utils import current_timestamp, file_hash


METRIC_COLUMNS = ["BMI", "WAIST", "TC", "HDL", "RTO", "GLU", "SYS", "DIA"]


def read_uploaded_file(uploaded_file):
    """
    Reads CSV or Excel files.

    Many department Excel files have a title row first and real column names
    on row 2, so Excel files are read with header=1.
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

    return df.rename(columns=rename_map)


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

    keep_cols = ["DOB", "Age", "BMI", "WAIST", "TC", "HDL", "RTO", "GLU", "SYS", "DIA"]
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

    uploaded_at = current_timestamp()
    upload_hash = file_hash(uploaded_file)

    df["department"] = department
    df["year"] = int(year)
    df["upload_filename"] = uploaded_file.name
    df["upload_hash"] = upload_hash
    df["uploaded_at"] = uploaded_at

    final_cols = [
        "department", "year", "DOB", "Age", "BMI", "WAIST", "TC", "HDL",
        "RTO", "GLU", "SYS", "DIA", "upload_filename", "upload_hash", "uploaded_at"
    ]

    return df[final_cols], upload_hash, uploaded_at
