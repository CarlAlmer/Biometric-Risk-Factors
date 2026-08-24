import os
import re

import pandas as pd
import streamlit as st

from utils import current_timestamp, file_hash


METRIC_COLUMNS = ["BMI", "WAIST", "TC", "HDL", "RTO", "GLU", "SYS", "DIA"]


# Words that commonly appear in filenames but are not part of the town name.
# The parser removes these after it identifies the year.
FILENAME_IGNORE_PHRASES = [
    r"\bfire\s+department\b",
    r"\bfire\s+dept\b",
    r"\bfire\s+dept\.\b",
    r"\bfire\s+district\b",
    r"\bdepartment\b",
    r"\bdept\b",
    r"\bfire\b",
    r"\bbiometric(?:s)?\b",
    r"\bbiometric\s+screening\b",
    r"\bscreening(?:s)?\b",
    r"\bhealth\b",
    r"\bwellness\b",
    r"\bdata\b",
    r"\bresults?\b",
    r"\breport\b",
    r"\bannual\b",
    r"\bemployee(?:s)?\b",
    r"\bmember(?:s)?\b",
]


def smart_title(text):
    """
    Apply title case while preserving a few common connector words.
    """
    words = text.split()
    if not words:
        return ""

    small_words = {"of", "the", "and"}
    formatted = []

    for index, word in enumerate(words):
        if index > 0 and word.lower() in small_words:
            formatted.append(word.lower())
        else:
            formatted.append(word[:1].upper() + word[1:].lower())

    return " ".join(formatted)


def detect_department_and_year(filename):
    """
    Try to detect the town/city name and year from an uploaded filename.

    Examples this is designed to handle:
      Stillwater Fire Department 2025.xlsx
      Stillwater_Fire_Department_2025.xlsx
      2025-Stillwater-Fire-Department.xlsx
      Stillwater FD 2025.csv
      Stillwater Biometrics 2025.xlsx

    Returns:
        department: detected town/city name, or "" if none can be found
        year: detected year as an int, or None if none can be found
    """
    base_name = os.path.splitext(os.path.basename(filename))[0]

    # Make common filename separators behave like spaces.
    working = re.sub(r"[_\-]+", " ", base_name)
    working = re.sub(r"[()\[\]{}]+", " ", working)
    working = re.sub(r"\s+", " ", working).strip()

    # Prefer a full four-digit year.
    four_digit_years = re.findall(r"(?<!\d)(20\d{2})(?!\d)", working)
    year = int(four_digit_years[-1]) if four_digit_years else None

    if year is not None:
        working = re.sub(rf"(?<!\d){year}(?!\d)", " ", working)
    else:
        # Optional fallback for filenames such as "Stillwater FD 25.xlsx".
        # Only 20-99 are accepted so station numbers such as "2" are not
        # mistaken for a year.
        two_digit_years = re.findall(r"(?<!\d)([2-9]\d)(?!\d)", working)
        if two_digit_years:
            short_year = int(two_digit_years[-1])
            year = 2000 + short_year
            working = re.sub(
                rf"(?<!\d){re.escape(two_digit_years[-1])}(?!\d)",
                " ",
                working,
                count=1,
            )

    # Remove common phrases that describe the file rather than the town.
    department_text = working
    for pattern in FILENAME_IGNORE_PHRASES:
        department_text = re.sub(
            pattern,
            " ",
            department_text,
            flags=re.IGNORECASE,
        )

    # Remove standalone FD after longer phrases have already been removed.
    department_text = re.sub(r"\bF\.?D\.?\b", " ", department_text, flags=re.IGNORECASE)

    # Remove common leading organization wording, e.g. "City of Stillwater".
    department_text = re.sub(
        r"^\s*(?:city|town|village)\s+of\s+",
        "",
        department_text,
        flags=re.IGNORECASE,
    )

    # Clean leftover punctuation and whitespace without destroying apostrophes.
    department_text = re.sub(r"[,;]+", " ", department_text)
    department_text = re.sub(r"\s+", " ", department_text).strip(" ._-\t")

    department = smart_title(department_text)
    return department, year


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

    df["department"] = department.strip()
    df["year"] = int(year)
    df["upload_filename"] = uploaded_file.name
    df["upload_hash"] = upload_hash
    df["uploaded_at"] = uploaded_at

    final_cols = [
        "department", "year", "DOB", "Age", "BMI", "WAIST", "TC", "HDL",
        "RTO", "GLU", "SYS", "DIA", "upload_filename", "upload_hash", "uploaded_at"
    ]

    return df[final_cols], upload_hash, uploaded_at
