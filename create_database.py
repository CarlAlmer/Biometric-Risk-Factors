import sqlite3

print("Creating database and tables...")

# Connect to database (creates file if it doesn't exist)
conn = sqlite3.connect("biometric.db")
cursor = conn.cursor()

# =========================
# 1. MAIN DATA TABLE
# =========================
cursor.execute("""
CREATE TABLE IF NOT EXISTS biometric_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    department TEXT,
    year INTEGER,
    DOB TEXT,
    Age INTEGER,
    BMI REAL,
    WAIST REAL,
    TC REAL,
    HDL REAL,
    RTO REAL,
    GLU REAL,
    SYS REAL,
    DIA REAL
)
""")

# =========================
# 2. SUMMARY TABLE
# =========================
cursor.execute("""
CREATE TABLE IF NOT EXISTS department_summary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    department TEXT,
    year INTEGER,
    avg_bmi REAL,
    avg_waist REAL,
    avg_tc REAL,
    avg_hdl REAL,
    avg_glu REAL,
    pct_obese REAL,
    record_count INTEGER
)
""")

# =========================
# 3. DATA SOURCE TRACKING
# =========================
cursor.execute("""
CREATE TABLE IF NOT EXISTS data_sources (
    file_id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_name TEXT UNIQUE,
    department TEXT,
    year INTEGER,
    date_loaded TEXT
)
""")

# Save changes
conn.commit()

print("✅ Tables created successfully!")

# Close connection
conn.close()