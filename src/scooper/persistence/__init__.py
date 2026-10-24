"""Session persistence layer for Scooper.

This module provides SQLite-backed storage for agent sessions,
conversation history, and execution records.
"""

from scooper.persistence.session_store import Session, SessionStore

__all__ = [
    "Session",
    "SessionStore",
]
