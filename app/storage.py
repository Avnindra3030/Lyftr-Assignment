import logging
from datetime import datetime, timezone
from typing import Generator, Optional, Tuple

from sqlalchemy import create_engine, text, func
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from sqlalchemy.exc import IntegrityError

from app.config import settings

logger = logging.getLogger(__name__)

# Create SQLAlchemy engine with SQLite-specific settings
# check_same_thread=False is required for SQLite to work with FastAPI's async
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)

# Create SessionLocal class for creating database sessions
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for SQLAlchemy models
Base = declarative_base()


def init_db() -> None:
    """
    Initialize the database by creating all tables.
    Called during application startup.
    """
    try:
        # Import models to register them with Base.metadata
        from app.models import Message  
        
        Base.metadata.create_all(bind=engine)
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


def get_db() -> Generator[Session, None, None]:
    """
    Dependency to get database session.
    Yields a session and ensures it's closed after use.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_health() -> bool:
    """
    Check if the database is reachable and schema is applied.
    
    Returns:
        True if DB is healthy and schema exists, False otherwise.
    """
    try:
        with SessionLocal() as db:
            # Execute a simple query to check connectivity
            db.execute(text("SELECT 1"))
            # Check if messages table exists (schema is applied)
            db.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='messages'"
            ))
            result = db.execute(text(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='messages'"
            )).scalar()
            if result == 0:
                logger.error("Database schema not applied: 'messages' table not found")
                return False
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False


# =============================================================================
# Message Repository Functions
# =============================================================================

def create_message(
    db: Session,
    message_id: str,
    from_msisdn: str,
    to_msisdn: str,
    ts: str,
    text: Optional[str] = None
) -> Tuple[bool, bool]:
    """
    Create a new message in the database (idempotent).
    
    Args:
        db: Database session
        message_id: Unique message identifier
        from_msisdn: Sender phone number
        to_msisdn: Recipient phone number
        ts: Message timestamp (ISO-8601 UTC)
        text: Optional message text
    
    Returns:
        Tuple of (success: bool, is_duplicate: bool)
        - (True, False): Message created successfully
        - (True, True): Message already exists (duplicate, idempotent success)
        - (False, False): Error occurred
    """
    from app.models import Message
    
    try:
        # Create server timestamp
        created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        
        message = Message(
            message_id=message_id,
            from_msisdn=from_msisdn,
            to_msisdn=to_msisdn,
            ts=ts,
            text=text,
            created_at=created_at
        )
        
        db.add(message)
        db.commit()
        logger.info(f"Message created: {message_id}")
        return (True, False)  # Created successfully, not a duplicate
        
    except IntegrityError:
        # message_id already exists - this is expected for idempotency
        db.rollback()
        logger.info(f"Duplicate message detected: {message_id}")
        return (True, True)  # Success (idempotent), is duplicate
        
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create message {message_id}: {e}")
        return (False, False)  # Error


def get_message_by_id(db: Session, message_id: str):
    """
    Retrieve a message by its ID.
    
    Args:
        db: Database session
        message_id: Message identifier to look up
    
    Returns:
        Message object if found, None otherwise
    """
    from app.models import Message
    
    return db.query(Message).filter(Message.message_id == message_id).first()
