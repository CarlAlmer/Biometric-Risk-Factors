import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool


def _database_url():
    """
    Read the permanent PostgreSQL connection string from Streamlit secrets.

    In Streamlit Community Cloud, add this in the app's Secrets settings:

        DATABASE_URL = "postgresql://..."

    Do not commit the real connection string or database password to GitHub.
    """
    try:
        database_url = st.secrets["DATABASE_URL"]
    except (KeyError, FileNotFoundError):
        st.error(
            "Permanent database connection is not configured yet. "
            "Add DATABASE_URL to this app's Streamlit Secrets settings."
        )
        st.stop()

    database_url = str(database_url).strip()

    # SQLAlchemy + psycopg2 uses this URL prefix.
    if database_url.startswith("postgres://"):
        database_url = database_url.replace(
            "postgres://",
            "postgresql+psycopg2://",
            1,
        )
    elif database_url.startswith("postgresql://"):
        database_url = database_url.replace(
            "postgresql://",
            "postgresql+psycopg2://",
            1,
        )

    return database_url


@st.cache_resource
def get_engine():
    """
    Create the PostgreSQL engine.

    NullPool is intentional here. Supabase already provides connection pooling,
    so the app opens a connection only when it needs one and closes it afterward.
    """
    return create_engine(
        _database_url(),
        poolclass=NullPool,
        pool_pre_ping=True,
        connect_args={"sslmode": "require"},
    )


def connect_db():
    """
    Return a SQLAlchemy connection.

    Kept as a helper for compatibility with the rest of the project.
    Prefer using `with connect_db() as conn:` so the connection is closed.
    """
    return get_engine().connect()


def create_tables():
    """
    Create the app tables in PostgreSQL if they do not already exist.

    The quoted biometric column names intentionally preserve the same column
    names used by the existing pandas cleaning/analysis code.
    """
    statements = [
        """
        CREATE TABLE IF NOT EXISTS biometric_data (
            id BIGSERIAL PRIMARY KEY,
            department TEXT,
            year INTEGER,
            "DOB" TEXT,
            "Age" DOUBLE PRECISION,
            "BMI" DOUBLE PRECISION,
            "WAIST" DOUBLE PRECISION,
            "TC" DOUBLE PRECISION,
            "HDL" DOUBLE PRECISION,
            "RTO" DOUBLE PRECISION,
            "GLU" DOUBLE PRECISION,
            "SYS" DOUBLE PRECISION,
            "DIA" DOUBLE PRECISION,
            upload_filename TEXT,
            upload_hash TEXT,
            uploaded_at TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS data_sources (
            source_id BIGSERIAL PRIMARY KEY,
            department TEXT,
            year INTEGER,
            filename TEXT,
            upload_hash TEXT,
            records_uploaded INTEGER,
            uploaded_at TEXT
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_biometric_department_year
        ON biometric_data (department, year)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_biometric_upload_hash
        ON biometric_data (upload_hash)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_sources_department_year
        ON data_sources (department, year)
        """,
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_sources_upload_hash_unique
        ON data_sources (upload_hash)
        """,
    ]

    with get_engine().begin() as conn:
        for statement in statements:
            conn.execute(text(statement))


def upload_already_exists(upload_hash):
    """Return True when the exact same file has already been uploaded."""
    query = text(
        """
        SELECT COUNT(*)
        FROM data_sources
        WHERE upload_hash = :upload_hash
        """
    )

    with get_engine().connect() as conn:
        count = conn.execute(
            query,
            {"upload_hash": upload_hash},
        ).scalar_one()

    return count > 0


def department_year_exists(department, year):
    """
    Return True when a source already exists for the same department and year.
    Department matching is case-insensitive.
    """
    query = text(
        """
        SELECT COUNT(*)
        FROM data_sources
        WHERE LOWER(TRIM(department)) = LOWER(TRIM(:department))
          AND year = :year
        """
    )

    with get_engine().connect() as conn:
        count = conn.execute(
            query,
            {
                "department": department,
                "year": int(year),
            },
        ).scalar_one()

    return count > 0


def get_department_year_source(department, year):
    """
    Return the most recent source record for one department/year pair.
    """
    query = text(
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
        WHERE LOWER(TRIM(department)) = LOWER(TRIM(:department))
          AND year = :year
        ORDER BY uploaded_at DESC, source_id DESC
        LIMIT 1
        """
    )

    with get_engine().connect() as conn:
        df = pd.read_sql_query(
            query,
            conn,
            params={
                "department": department,
                "year": int(year),
            },
        )

    if df.empty:
        return None

    return df.iloc[0].to_dict()


def save_to_database(
    df,
    department,
    year,
    filename,
    upload_hash,
    uploaded_at,
):
    """
    Save one reviewed department upload and its source record.

    Both inserts occur in the same transaction.
    """
    source_df = pd.DataFrame(
        [
            {
                "department": department.strip(),
                "year": int(year),
                "filename": filename,
                "upload_hash": upload_hash,
                "records_uploaded": len(df),
                "uploaded_at": uploaded_at,
            }
        ]
    )

    with get_engine().begin() as conn:
        df.to_sql(
            "biometric_data",
            conn,
            if_exists="append",
            index=False,
            method="multi",
        )

        source_df.to_sql(
            "data_sources",
            conn,
            if_exists="append",
            index=False,
            method="multi",
        )


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

    The delete and inserts occur in one transaction. If anything fails,
    PostgreSQL rolls the whole transaction back.
    """
    delete_biometric = text(
        """
        DELETE FROM biometric_data
        WHERE LOWER(TRIM(department)) = LOWER(TRIM(:department))
          AND year = :year
        """
    )

    delete_source = text(
        """
        DELETE FROM data_sources
        WHERE LOWER(TRIM(department)) = LOWER(TRIM(:department))
          AND year = :year
        """
    )

    source_df = pd.DataFrame(
        [
            {
                "department": department.strip(),
                "year": int(year),
                "filename": filename,
                "upload_hash": upload_hash,
                "records_uploaded": len(df),
                "uploaded_at": uploaded_at,
            }
        ]
    )

    params = {
        "department": department,
        "year": int(year),
    }

    with get_engine().begin() as conn:
        conn.execute(delete_biometric, params)
        conn.execute(delete_source, params)

        df.to_sql(
            "biometric_data",
            conn,
            if_exists="append",
            index=False,
            method="multi",
        )

        source_df.to_sql(
            "data_sources",
            conn,
            if_exists="append",
            index=False,
            method="multi",
        )


@st.cache_data(ttl=60)
def load_biometric_data():
    """
    Load all stored biometric records from the permanent PostgreSQL database.
    """
    query = text(
        """
        SELECT *
        FROM biometric_data
        ORDER BY year DESC, department ASC, id ASC
        """
    )

    with get_engine().connect() as conn:
        return pd.read_sql_query(query, conn)


@st.cache_data(ttl=60)
def load_sources():
    """
    Load upload/source history from the permanent PostgreSQL database.
    """
    query = text(
        """
        SELECT *
        FROM data_sources
        ORDER BY uploaded_at DESC, source_id DESC
        """
    )

    with get_engine().connect() as conn:
        return pd.read_sql_query(query, conn)


def load_uploads_for_management():
    """
    Load one row per uploaded source file for the Manage Uploads tab.
    """
    query = text(
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
        """
    )

    with get_engine().connect() as conn:
        return pd.read_sql_query(query, conn)


def count_rows_for_upload(upload_hash):
    """
    Count biometric records created by one exact uploaded file.
    """
    query = text(
        """
        SELECT COUNT(*)
        FROM biometric_data
        WHERE upload_hash = :upload_hash
        """
    )

    with get_engine().connect() as conn:
        return int(
            conn.execute(
                query,
                {"upload_hash": upload_hash},
            ).scalar_one()
        )


def delete_upload(upload_hash):
    """
    Permanently delete one exact uploaded file and all biometric rows
    associated with it.

    Returns:
        biometric_rows_deleted, source_rows_deleted
    """
    delete_biometric = text(
        """
        DELETE FROM biometric_data
        WHERE upload_hash = :upload_hash
        """
    )

    delete_source = text(
        """
        DELETE FROM data_sources
        WHERE upload_hash = :upload_hash
        """
    )

    params = {"upload_hash": upload_hash}

    with get_engine().begin() as conn:
        biometric_result = conn.execute(delete_biometric, params)
        source_result = conn.execute(delete_source, params)

    return biometric_result.rowcount, source_result.rowcount
