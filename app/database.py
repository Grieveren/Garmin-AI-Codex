"""Database session and base model setup."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.config import get_settings


settings = get_settings()
engine = create_engine(settings.database_url, echo=settings.debug, future=True)


class Base(DeclarativeBase):
    """Declarative base for SQLAlchemy models."""


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db():
    """FastAPI dependency yielding a transactional database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
