import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# ---------------------------------------------------
# DATABASE URL (Postgres)
# Example:
# postgresql+psycopg://user:password@localhost:5432/wri
# ---------------------------------------------------

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5432/wri"
)

# ---------------------------------------------------
# Engine
# ---------------------------------------------------

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)

# ---------------------------------------------------
# Session
# ---------------------------------------------------

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()

# ---------------------------------------------------
# Dependency used by FastAPI routes
# THIS IS WHAT YOUR ERROR IS ABOUT
# ---------------------------------------------------

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()