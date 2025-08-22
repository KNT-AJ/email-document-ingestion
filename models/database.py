"""Database connection handling and utilities."""

import logging
from contextlib import contextmanager
from typing import Generator, Optional, Any, Dict
from sqlalchemy import text, event
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError, DisconnectionError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool

from config.settings import settings
from .base import get_engine, get_session_factory

logger = logging.getLogger(__name__)


# Global database service instance
_db_service: Optional["DatabaseService"] = None


def get_db_service() -> "DatabaseService":
    """Get the global database service instance."""
    global _db_service
    if _db_service is None:
        _db_service = DatabaseService()
    return _db_service


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for database sessions.

    Yields:
        Database session that will be automatically closed after use
    """
    db_service = get_db_service()
    db = db_service.session_factory()
    try:
        yield db
    finally:
        db.close()


class DatabaseService:
    """Service for handling database connections and operations."""

    def __init__(self):
        """Initialize database service with connection pooling."""
        self.engine = get_engine()
        self.session_factory = get_session_factory()

        # Set up connection pool event listeners
        self._setup_connection_events()

    def _setup_connection_events(self):
        """Set up database connection event listeners for monitoring and error handling."""

        @event.listens_for(self.engine, "connect")
        def connect(dbapi_connection, connection_record):
            """Handle successful database connections."""
            logger.info("Database connection established")

        @event.listens_for(self.engine, "checkout")
        def checkout(dbapi_connection, connection_record, connection_proxy):
            """Handle connection checkout from pool."""
            logger.debug("Database connection checked out from pool")

        @event.listens_for(self.engine, "checkin")
        def checkin(dbapi_connection, connection_record):
            """Handle connection checkin to pool."""
            logger.debug("Database connection returned to pool")

        @event.listens_for(self.engine, "close")
        def close(dbapi_connection, connection_record):
            """Handle connection close."""
            logger.debug("Database connection closed")

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """Get a database session with proper error handling and cleanup.

        Yields:
            Session: Database session

        Raises:
            SQLAlchemyError: If database operation fails
        """
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()

    def health_check(self) -> Dict[str, Any]:
        """Perform database health check.

        Returns:
            Dict containing health check results
        """
        try:
            with self.get_session() as session:
                # Execute a simple query to test connectivity
                result = session.execute(text("SELECT 1 as health_check"))
                health_result = result.fetchone()

                return {
                    "status": "healthy",
                    "database_type": "postgresql",
                    "connection_pool_size": self.engine.pool.size(),
                    "connection_pool_checked_out": self.engine.pool.checkedout(),
                    "connection_pool_overflow": self.engine.pool.overflow(),
                    "test_query_result": health_result[0] if health_result else None
                }
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }

    def execute_query(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> Any:
        """Execute a raw SQL query.

        Args:
            query: SQL query string
            parameters: Query parameters

        Returns:
            Query result

        Raises:
            SQLAlchemyError: If query execution fails
        """
        try:
            with self.get_session() as session:
                result = session.execute(text(query), parameters or {})
                return result.fetchall()
        except SQLAlchemyError as e:
            logger.error(f"Query execution failed: {query}, Error: {e}")
            raise

    def execute_write_query(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> int:
        """Execute a write SQL query (INSERT, UPDATE, DELETE).

        Args:
            query: SQL query string
            parameters: Query parameters

        Returns:
            Number of affected rows

        Raises:
            SQLAlchemyError: If query execution fails
        """
        try:
            with self.get_session() as session:
                result = session.execute(text(query), parameters or {})
                return result.rowcount
        except SQLAlchemyError as e:
            logger.error(f"Write query execution failed: {query}, Error: {e}")
            raise

    def create_tables(self):
        """Create all database tables defined in models."""
        try:
            from . import Base
            Base.metadata.create_all(bind=self.engine)
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Failed to create database tables: {e}")
            raise

    def drop_tables(self):
        """Drop all database tables (use with caution)."""
        try:
            from . import Base
            Base.metadata.drop_all(bind=self.engine)
            logger.warning("All database tables dropped")
        except Exception as e:
            logger.error(f"Failed to drop database tables: {e}")
            raise

    def reset_database(self):
        """Reset database by dropping and recreating all tables."""
        logger.warning("Resetting database - all data will be lost")
        self.drop_tables()
        self.create_tables()
        logger.info("Database reset completed")


# Global database service instance (lazy initialization)
_db_service = None


def get_database_service() -> DatabaseService:
    """Get the global database service instance."""
    global _db_service
    if _db_service is None:
        _db_service = DatabaseService()
    return _db_service


@contextmanager
def transaction_context(session: Session):
    """Context manager for database transactions with rollback on error.

    Args:
        session: Database session

    Yields:
        Session: The database session
    """
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Transaction failed: {e}")
        raise
