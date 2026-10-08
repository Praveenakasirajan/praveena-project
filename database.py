"""
database.py - MySQL Database connection and session management for AI Interview Coach.
Configured via environment variables (DATABASE_URL, or DB_HOST, DB_USER, DB_PASSWORD, etc.).
"""

import os
import logging
from typing import Generator
from urllib.parse import quote_plus
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session

load_dotenv()
logger = logging.getLogger(__name__)

# Base declarative class for ORM models
Base = declarative_base()

def get_database_url() -> str:
    """Resolve database URL from environment variables with safe encoding."""
    env_url = os.getenv("DATABASE_URL")
    if env_url:
        return env_url

    # Fallback to discrete variables
    host = os.getenv("DB_HOST", "127.0.0.1")
    port = os.getenv("DB_PORT", "3306")
    user = os.getenv("DB_USER", "root")
    password = os.getenv("DB_PASSWORD", "")
    db_name = os.getenv("DB_NAME", "interview_coach_db")

    encoded_password = quote_plus(password)
    return f"mysql+pymysql://{user}:{encoded_password}@{host}:{port}/{db_name}?charset=utf8mb4"


DATABASE_URL = get_database_url()

# Create SQLAlchemy Engine (supports both MySQL and SQLite)
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        echo=False,
    )
else:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=3600,
        pool_size=10,
        max_overflow=20,
        echo=False,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Create all tables if they do not already exist, and ensure schema migrations."""
    try:
        import models  # Ensure all models are registered
        Base.metadata.create_all(bind=engine)

        if engine.name == "mysql":
            # Ensure new schema columns exist in existing tables
            with engine.connect() as conn:
                def add_column_if_not_exists(table, column, col_type):
                    sql = text(f"""
                        SELECT COUNT(*) FROM information_schema.COLUMNS 
                        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = '{table}' AND COLUMN_NAME = '{column}'
                    """)
                    exists = conn.execute(sql).scalar()
                    if not exists:
                        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
                        conn.commit()

                add_column_if_not_exists("interview_sessions", "technical_subject", "VARCHAR(80) NULL")
                add_column_if_not_exists("session_questions", "technical_subject", "VARCHAR(80) NULL")
                add_column_if_not_exists("session_questions", "source_type", "VARCHAR(50) NULL")
                add_column_if_not_exists("session_questions", "source_reference", "VARCHAR(255) NULL")
                add_column_if_not_exists("resume_metadata", "candidate_name", "VARCHAR(120) NULL")
                add_column_if_not_exists("resume_metadata", "certifications", "JSON NULL")
                add_column_if_not_exists("resume_metadata", "skill_gaps", "JSON NULL")
                add_column_if_not_exists("resume_metadata", "resume_strengths", "JSON NULL")
                add_column_if_not_exists("resume_metadata", "recommended_improvements", "JSON NULL")
                add_column_if_not_exists("resume_metadata", "achievements", "JSON NULL")
                add_column_if_not_exists("resume_metadata", "structured_skills", "JSON NULL")

                # Ensure role columns are nullable in existing tables
                try:
                    conn.execute(text("ALTER TABLE interview_sessions MODIFY COLUMN `role` VARCHAR(100) NULL"))
                    conn.execute(text("ALTER TABLE session_questions MODIFY COLUMN `role` VARCHAR(100) NULL"))
                    conn.commit()
                except Exception as e:
                    logger.warning("Notice on altering role nullable: %s", e)

        logger.info("Database tables and schema columns verified/created successfully in %s.", engine.name)
    except Exception as e:
        logger.exception("Failed to initialize database tables: %s", e)
        raise


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for obtaining a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_connection() -> bool:
    """Health check helper to test database connectivity."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1;"))
            return True
    except Exception as e:
        logger.warning("Database health check failed: %s", e)
        return False
