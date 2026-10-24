"""SQLite-based session storage for conversation history and execution records.

This module provides persistent storage for agent sessions using SQLite,
enabling conversation history recovery and execution tracking across runs.
"""

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from scooper.exceptions import SessionError, SessionNotFoundError
from scooper.models.base import Message, ToolCall
from scooper.runtime.executor import ExecutionResult

logger = logging.getLogger(__name__)

# Schema version for migrations
SCHEMA_VERSION = 1


class Session(BaseModel):
    """Represents a persistent agent session.

    Attributes:
        session_id: Unique identifier for the session
        agent_name: Name of the agent this session belongs to
        created_at: When the session was created (ISO format UTC)
        updated_at: When the session was last updated (ISO format UTC)
        metadata: Optional session metadata (JSON-serializable)
    """

    session_id: str = Field(
        description="Unique identifier for the session",
    )

    agent_name: str = Field(
        description="Name of the agent this session belongs to",
    )

    created_at: str = Field(
        description="Session creation timestamp (ISO format UTC)",
    )

    updated_at: str = Field(
        description="Session last update timestamp (ISO format UTC)",
    )

    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Optional session metadata",
    )

    model_config = {
        "frozen": True,
    }


class SessionStore:
    """SQLite-based storage for agent sessions and conversation history.

    This class provides an async-compatible interface for persisting agent
    sessions, conversation messages, and execution records. It uses SQLite
    for local storage with proper transaction handling and schema versioning.

    The store is designed to be non-blocking by avoiding long-running queries
    and using appropriate isolation levels.

    Attributes:
        db_path: Path to the SQLite database file
    """

    def __init__(self, db_path: str | Path = "scooper_sessions.db"):
        """Initialize the session store.

        Args:
            db_path: Path to the SQLite database file (created if missing)
        """
        self.db_path = Path(db_path)
        self._conn: sqlite3.Connection | None = None
        self._initialized = False

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create database connection.

        Returns:
            Active SQLite connection
        """
        if self._conn is None:
            self._conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,  # Allow use across async contexts
            )
            self._conn.row_factory = sqlite3.Row  # Enable column access by name
        return self._conn

    def _initialize_schema(self) -> None:
        """Initialize database schema if not already initialized.

        Creates tables for schema_version, sessions, messages, and executions
        with appropriate constraints and indexes.
        """
        if self._initialized:
            return

        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Check current schema version
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                )
                """
            )

            cursor.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1")
            row = cursor.fetchone()
            current_version = row[0] if row else 0

            if current_version < SCHEMA_VERSION:
                self._apply_migrations(cursor, current_version)
                cursor.execute(
                    "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
                    (SCHEMA_VERSION, datetime.now(timezone.utc).isoformat()),
                )

            conn.commit()
            self._initialized = True
            logger.info(f"Database schema initialized at version {SCHEMA_VERSION}")

        except Exception as e:
            conn.rollback()
            raise SessionError(f"Failed to initialize schema: {e}") from e

    def _apply_migrations(self, cursor: sqlite3.Cursor, from_version: int) -> None:
        """Apply schema migrations from current version to SCHEMA_VERSION.

        Args:
            cursor: Database cursor for executing migrations
            from_version: Current schema version
        """
        if from_version < 1:
            # Initial schema creation
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    agent_name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    metadata TEXT
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    sequence_number INTEGER NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'tool')),
                    content TEXT,
                    tool_calls TEXT,
                    tool_call_id TEXT,
                    name TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE,
                    UNIQUE(session_id, sequence_number)
                )
                """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_messages_session
                ON messages(session_id, sequence_number)
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS executions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    final_output TEXT,
                    iterations INTEGER NOT NULL,
                    stop_reason TEXT NOT NULL,
                    tool_calls_made INTEGER NOT NULL DEFAULT 0,
                    error TEXT,
                    started_at TEXT NOT NULL,
                    completed_at TEXT NOT NULL,
                    metadata TEXT,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
                )
                """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_executions_session
                ON executions(session_id, started_at)
                """
            )

            logger.info("Applied migration: Initial schema (version 1)")

    async def create_session(
        self,
        session_id: str,
        agent_name: str,
        metadata: dict[str, Any] | None = None,
    ) -> Session:
        """Create a new session.

        Args:
            session_id: Unique identifier for the session
            agent_name: Name of the agent
            metadata: Optional session metadata

        Returns:
            Created session

        Raises:
            SessionError: If session creation fails
        """
        self._initialize_schema()

        now = datetime.now(timezone.utc).isoformat()
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                INSERT INTO sessions (session_id, agent_name, created_at, updated_at, metadata)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    agent_name,
                    now,
                    now,
                    json.dumps(metadata) if metadata else None,
                ),
            )
            conn.commit()

            logger.info(f"Created session {session_id} for agent {agent_name}")

            return Session(
                session_id=session_id,
                agent_name=agent_name,
                created_at=now,
                updated_at=now,
                metadata=metadata,
            )

        except sqlite3.IntegrityError as e:
            conn.rollback()
            raise SessionError(f"Session '{session_id}' already exists") from e
        except Exception as e:
            conn.rollback()
            raise SessionError(f"Failed to create session: {e}") from e

    async def get_session(self, session_id: str) -> Session:
        """Retrieve a session by ID.

        Args:
            session_id: Session identifier

        Returns:
            Session object

        Raises:
            SessionNotFoundError: If session doesn't exist
        """
        self._initialize_schema()

        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT session_id, agent_name, created_at, updated_at, metadata FROM sessions WHERE session_id = ?",
            (session_id,),
        )

        row = cursor.fetchone()
        if not row:
            raise SessionNotFoundError(f"Session '{session_id}' not found")

        return Session(
            session_id=row["session_id"],
            agent_name=row["agent_name"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else None,
        )

    async def list_sessions(self, agent_name: str | None = None) -> list[Session]:
        """List all sessions, optionally filtered by agent name.

        Args:
            agent_name: Optional agent name filter

        Returns:
            List of sessions
        """
        self._initialize_schema()

        conn = self._get_connection()
        cursor = conn.cursor()

        if agent_name:
            cursor.execute(
                """
                SELECT session_id, agent_name, created_at, updated_at, metadata
                FROM sessions WHERE agent_name = ?
                ORDER BY created_at DESC
                """,
                (agent_name,),
            )
        else:
            cursor.execute(
                """
                SELECT session_id, agent_name, created_at, updated_at, metadata
                FROM sessions
                ORDER BY created_at DESC
                """
            )

        rows = cursor.fetchall()
        return [
            Session(
                session_id=row["session_id"],
                agent_name=row["agent_name"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                metadata=json.loads(row["metadata"]) if row["metadata"] else None,
            )
            for row in rows
        ]

    async def delete_session(self, session_id: str) -> None:
        """Delete a session and all associated data.

        Args:
            session_id: Session identifier

        Raises:
            SessionNotFoundError: If session doesn't exist
        """
        self._initialize_schema()

        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))

            if cursor.rowcount == 0:
                raise SessionNotFoundError(f"Session '{session_id}' not found")

            conn.commit()
            logger.info(f"Deleted session {session_id}")

        except SessionNotFoundError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise SessionError(f"Failed to delete session: {e}") from e

    async def save_message(self, session_id: str, message: Message) -> None:
        """Save a message to the session conversation history.

        Messages are stored in chronological order with sequence numbers.

        Args:
            session_id: Session identifier
            message: Message to save

        Raises:
            SessionNotFoundError: If session doesn't exist
            SessionError: If save fails
        """
        self._initialize_schema()

        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Get next sequence number
            cursor.execute(
                "SELECT COALESCE(MAX(sequence_number), 0) + 1 FROM messages WHERE session_id = ?",
                (session_id,),
            )
            sequence_number = cursor.fetchone()[0]

            # Serialize tool_calls if present
            tool_calls_json = None
            if message.tool_calls:
                tool_calls_json = json.dumps([tc.model_dump() for tc in message.tool_calls])

            # Insert message
            cursor.execute(
                """
                INSERT INTO messages
                (session_id, sequence_number, role, content, tool_calls, tool_call_id, name, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    sequence_number,
                    message.role,
                    message.content,
                    tool_calls_json,
                    message.tool_call_id,
                    message.name,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

            # Update session updated_at
            cursor.execute(
                "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
                (datetime.now(timezone.utc).isoformat(), session_id),
            )

            conn.commit()
            logger.debug(f"Saved message #{sequence_number} to session {session_id}")

        except sqlite3.IntegrityError as e:
            conn.rollback()
            raise SessionNotFoundError(f"Session '{session_id}' not found") from e
        except Exception as e:
            conn.rollback()
            raise SessionError(f"Failed to save message: {e}") from e

    async def load_messages(self, session_id: str) -> list[Message]:
        """Load all messages from a session in chronological order.

        Args:
            session_id: Session identifier

        Returns:
            List of messages in chronological order

        Raises:
            SessionNotFoundError: If session doesn't exist
        """
        self._initialize_schema()

        # Verify session exists
        await self.get_session(session_id)

        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT role, content, tool_calls, tool_call_id, name
            FROM messages
            WHERE session_id = ?
            ORDER BY sequence_number ASC
            """,
            (session_id,),
        )

        rows = cursor.fetchall()
        messages = []

        for row in rows:
            # Deserialize tool_calls if present
            tool_calls = None
            if row["tool_calls"]:
                tool_calls_data = json.loads(row["tool_calls"])
                tool_calls = [ToolCall(**tc) for tc in tool_calls_data]

            messages.append(
                Message(
                    role=row["role"],
                    content=row["content"],
                    tool_calls=tool_calls,
                    tool_call_id=row["tool_call_id"],
                    name=row["name"],
                )
            )

        logger.debug(f"Loaded {len(messages)} messages from session {session_id}")
        return messages

    async def save_execution(self, session_id: str, result: ExecutionResult) -> None:
        """Save an execution record to the session.

        Args:
            session_id: Session identifier
            result: Execution result to save

        Raises:
            SessionNotFoundError: If session doesn't exist
            SessionError: If save fails
        """
        self._initialize_schema()

        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            now = datetime.now(timezone.utc).isoformat()

            cursor.execute(
                """
                INSERT INTO executions
                (session_id, success, final_output, iterations, stop_reason, tool_calls_made,
                 error, started_at, completed_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    1 if result.success else 0,
                    result.final_output,
                    result.iterations,
                    result.stop_reason,
                    result.tool_calls_made,
                    result.error,
                    now,  # We don't track start time separately yet
                    now,
                    json.dumps(result.metadata) if result.metadata else None,
                ),
            )

            conn.commit()
            logger.debug(f"Saved execution record to session {session_id}")

        except sqlite3.IntegrityError as e:
            conn.rollback()
            raise SessionNotFoundError(f"Session '{session_id}' not found") from e
        except Exception as e:
            conn.rollback()
            raise SessionError(f"Failed to save execution: {e}") from e

    def close(self) -> None:
        """Close the database connection.

        This should be called when done with the store to release resources.
        """
        if self._conn:
            self._conn.close()
            self._conn = None
            self._initialized = False
            logger.debug("Closed database connection")

    def __enter__(self) -> "SessionStore":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.close()

    async def __aenter__(self) -> "SessionStore":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        self.close()
