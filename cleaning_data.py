import pandas as pd

print("pandas loaded successfully")

# =========================
# 1. LOAD EXCEL
# =========================
file_path = "department/2025 Excelsior Report.xlsx"
df = pd.read_excel(file_path)

# =========================
# 2. FIX HEADER MISALIGNMENT
# =========================
if "DOB" not in df.columns:
    print("⚠️ Header misalignment detected. Fixing headers...")
    df.columns = df.iloc[0]
    df = df[1:].reset_index(drop=True)

# Clean column names
df.columns = df.columns.astype(str).str.strip()

# Remove junk columns
df = df.loc[:, ~df.columns.str.contains("^Unnamed")]

# =========================
# 3. STANDARDIZE COLUMN NAMES
# =========================
# Removes "25 " prefix
df.columns = df.columns.str.replace(r"^\d+\s*", "", regex=True)

print("Cleaned Columns:", df.columns.tolist())

# =========================
# 4. CONVERT NUMERIC DATA
# =========================
cols = ["BMI", "WAIST", "TC", "HDL", "RTO", "GLU"]

existing_cols = [c for c in cols if c in df.columns]

df[existing_cols] = df[existing_cols].apply(pd.to_numeric, errors="coerce")

# =========================
# 5. HANDLE BLOOD PRESSURE (NEW)
# =========================
if "BP" in df.columns:
    # Clean whitespace just in case (e.g., "130 / 80")
    df["BP"] = df["BP"].astype(str).str.replace(" ", "")

    # Split into systolic / diastolic
    bp_split = df["BP"].str.split("/", expand=True)

    df["SYS"] = pd.to_numeric(bp_split[0], errors="coerce")
    df["DIA"] = pd.to_numeric(bp_split[1], errors="coerce")

# =========================
# 6. FIX DOB + COMPUTE AGE
# =========================
df["DOB"] = pd.to_datetime(df["DOB"], errors="coerce")

today = pd.Timestamp.today()
age_days = (today - df["DOB"]).dt.days

df["Age"] = (age_days / 365.25).round().astype("Int64")

# =========================
# 7. DATA QUALITY CHECK
# =========================
print("\nMissing Values:")
print(df.isna().sum())

# =========================
# 8. OUTPUT
# =========================
print("\nPreview:")
print(df.head(10))

print("\nData Info:")
df.info()

# Optional: show entire dataset
# pd.set_option("display.max_rows", None)
# print(df)
