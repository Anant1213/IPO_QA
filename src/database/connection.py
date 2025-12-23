"""
Database connection management using SQLAlchemy
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from contextlib import contextmanager
import os

# Database URL
DATABASE_URL = os.getenv(
    'DATABASE_URL', 
    'postgresql://localhost/ipo_intelligence'
)

# Create engine with connection pooling
engine = create_engine(
    DATABASE_URL,
    pool_size=10,           # Max 10 connections
    max_overflow=20,        # Allow 20 overflow connections
    pool_pre_ping=True,     # Verify connections before use
    echo=False              # Set True for SQL logging during debug
)

# Session factory
SessionLocal = scoped_session(
    sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine
    )
)

@contextmanager
def get_db():
    """
    Context manager for database sessions
    
    Usage:
        with get_db() as db:
            result = db.query(Document).all()
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()

def test_connection():
    """Test database connection"""
    try:
        from sqlalchemy import text
        with get_db() as db:
            result = db.execute(text("SELECT 1")).fetchone()
            print("✅ Database connection successful!")
            return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False
