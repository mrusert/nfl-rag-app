"""
Data layer module for NFL Stats application.

Provides DuckDB-based structured data access for precise SQL queries
alongside the existing ChromaDB semantic search.
"""

from .database import NFLDatabase
from .loader import NFLDataLoader

__all__ = ["NFLDatabase", "NFLDataLoader"]
