"""Fixtures for query router regression tests."""

import sys
from pathlib import Path

import pytest

# Ensure backend is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import get_connection
from query_router import QueryRouter


DB_PATH = Path(__file__).parent.parent.parent / "data" / "godesia.db"


@pytest.fixture(scope="session")
def router():
    """Session-scoped QueryRouter connected to the real database."""
    conn = get_connection(str(DB_PATH))
    return QueryRouter(conn)
