import pandas as pd
import sqlite3
import requests
from io import BytesIO
from datetime import datetime

# =========================
# CONFIG
# =========================
GITHUB_OWNER = "CarlAlmer"
GITHUB_REPO = "Biometric-Risk-Factors"
GITHUB_FOLDER = "Department"

API_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{GITHUB_FOLDER}"

DB_PATH = "biometric.db"

# Optional (recommended if you hit rate limits)
# GITHUB_TOKEN = "your_token_here"
GITHUB_TOKEN = None

HEADERS = {}
if GITHUB_TOKEN:
    HEADERS["Authorization"] = f"token {GITHUB_TOKEN}"


# =========================
# CLEANING FUNCTION
# =========================
def clean_dataframe(df):

    # Fix header misalignment
    if "DOB" not in df.columns:
        df.columns = df.iloc[0]
        df = df[1:].reset_index(drop=True)

    # Clean column names
    df.columns = df.columns.astype(str).str.strip()

    # Remove Excel junk columns
    df = df.loc[:, ~df.columns.str.contains("^Unnamed")]

    # Remove year prefixes like "25 "
    df.columns = df.columns.str.replace(r"^\d+\s*", "", regex=True)

    # Numeric conversion
    cols = ["BMI", "WAIST", "TC", "HDL", "RTO", "GLU"]
    existing_cols = [c for c in cols if c in df.columns]
    df[existing_cols] = df[existing_cols].apply(pd.to_numeric, errors="coerce")

    # Blood pressure split
    if "BP" in df.columns:
        df["BP"] = df["BP"].astype(str).str.replace(" ", "")
        bp_split = df["BP"].str.split("/", expand=True)
        df["SYS"] = pd.to_numeric(bp_split[0], errors="coerce")
        df["DIA"] = pd.to_numeric(bp_split[1], errors="coerce")

    # DOB + Age
    if "DOB" in df.columns:
        df["DOB"] = pd.to_datetime(df["DOB"], errors="coerce")
        today = pd.Timestamp.today()
        df["Age"] = ((today - df["DOB"]).dt.days / 365.25).round().astype("Int64")

    return df


# =========================
# GET FILES FROM GITHUB
# =========================
def get_excel_files():
    response = requests.get(API_URL, headers=HEADERS)
    response.raise_for_status()

    files = response.json()

    excel_files = [
        f for f in files
        if f["name"].endswith(".xlsx")
    ]

    return excel_files


# =========================
# PARSE FILE METADATA
# =========================
def parse_file_info(filename):
    # Example: "2025 Excelsior Report.xlsx"
    name = filename.replace(".xlsx", "")
    parts = name.split()

    year = None
    department_parts = []

    for p in parts:
        if p.isdigit():
            year = int(p)
        else:
            department_parts.append(p)

    department = " ".join(department_parts).strip()

    return department, year


# =========================
# INSERT INTO DB
# =========================
def insert_into_db(df, department, year, file_name):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Skip if already imported
    cursor.execute(
        "SELECT 1 FROM data_sources WHERE file_name = ?",
        (file_name,)
    )
    if cursor.fetchone():
        print(f"⏭️ Already imported: {file_name}")
        conn.close()
        return

    # Insert rows
    for _, row in df.iterrows():
        cursor.execute("""
        INSERT INTO biometric_data (
            department, year, DOB, Age,
            BMI, WAIST, TC, HDL, RTO, GLU, SYS, DIA
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            department,
            year,
            str(row.get("DOB")),
            row.get("Age"),
            row.get("BMI"),
            row.get("WAIST"),
            row.get("TC"),
            row.get("HDL"),
            row.get("RTO"),
            row.get("GLU"),
            row.get("SYS"),
            row.get("DIA"),
        ))

    # Track file import
    cursor.execute("""
    INSERT INTO data_sources (file_name, department, year, date_loaded)
    VALUES (?, ?, ?, ?)
    """, (
        file_name,
        department,
        year,
        datetime.now().isoformat()
    ))

    conn.commit()
    conn.close()

    print(f"✅ Imported: {file_name}")


# =========================
# MAIN PIPELINE
# =========================
def main():
    files = get_excel_files()

    if not files:
        print("⚠️ No Excel files found in GitHub folder.")
        return

    for file in files:
        file_name = file["name"]
        download_url = file["download_url"]

        print(f"\n📄 Processing: {file_name}")

        try:
            response = requests.get(download_url)
            response.raise_for_status()

            excel_data = BytesIO(response.content)
            df = pd.read_excel(excel_data)

            df = clean_dataframe(df)

            department, year = parse_file_info(file_name)

            insert_into_db(df, department, year, file_name)

        except Exception as e:
            print(f"❌ Error processing {file_name}: {e}")


# =========================
# RUN
# =========================
if __name__ == "__main__":
    main()