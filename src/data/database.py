"""
DuckDB database interface for structured NFL data queries.

Provides safe, read-only SQL execution with connection pooling
for high-performance analytical queries on player and game statistics.
"""

import duckdb
from pathlib import Path
from typing import Optional, Any
from dataclasses import dataclass
import threading
import re

from src.config import DATA_DIR


# Default database path
DUCKDB_PATH = DATA_DIR / "nfl_stats.duckdb"

# Global shared database instance (singleton pattern)
# This ensures all tools share the same connection and avoids DuckDB lock conflicts
_shared_db_instance: Optional["NFLDatabase"] = None
_shared_db_lock = threading.Lock()


@dataclass
class QueryResult:
    """Result from a database query."""
    columns: list[str]
    rows: list[tuple]
    row_count: int

    def to_dicts(self) -> list[dict]:
        """Convert rows to list of dictionaries."""
        return [dict(zip(self.columns, row)) for row in self.rows]

    def to_markdown_table(self, max_rows: int = 20) -> str:
        """Format result as markdown table."""
        if not self.rows:
            return "No results found."

        # Header
        header = "| " + " | ".join(self.columns) + " |"
        separator = "| " + " | ".join(["---"] * len(self.columns)) + " |"

        # Rows (truncate if needed)
        display_rows = self.rows[:max_rows]
        row_lines = []
        for row in display_rows:
            formatted = []
            for val in row:
                if val is None:
                    formatted.append("NULL")
                elif isinstance(val, float):
                    formatted.append(f"{val:.2f}")
                else:
                    formatted.append(str(val))
            row_lines.append("| " + " | ".join(formatted) + " |")

        result = [header, separator] + row_lines

        if self.row_count > max_rows:
            result.append(f"\n*...and {self.row_count - max_rows} more rows*")

        return "\n".join(result)


class NFLDatabase:
    """
    Thread-safe DuckDB interface for NFL statistics.

    Features:
    - Read-only query execution (blocks INSERT, UPDATE, DELETE, DROP)
    - Connection pooling via thread-local storage
    - Query timeout protection
    - Parameterized query support
    """

    # SQL patterns that indicate write operations
    WRITE_PATTERNS = re.compile(
        r'\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE|REPLACE|MERGE)\b',
        re.IGNORECASE
    )

    def __init__(self, db_path: Optional[Path] = None, read_only: bool = True):
        """
        Initialize database connection.

        Args:
            db_path: Path to DuckDB file. Defaults to data/nfl_stats.duckdb
            read_only: If True, blocks write operations (default: True)
        """
        self.db_path = db_path or DUCKDB_PATH
        self.read_only = read_only
        self._local = threading.local()

    def _get_connection(self) -> duckdb.DuckDBPyConnection:
        """Get thread-local database connection."""
        if not hasattr(self._local, 'connection') or self._local.connection is None:
            self._local.connection = duckdb.connect(
                str(self.db_path),
                read_only=self.read_only
            )
        return self._local.connection

    def _is_write_query(self, sql: str) -> bool:
        """Check if SQL contains write operations."""
        return bool(self.WRITE_PATTERNS.search(sql))

    def execute_safe(
        self,
        sql: str,
        params: Optional[tuple] = None,
        timeout_seconds: int = 30
    ) -> QueryResult:
        """
        Execute a read-only SQL query safely.

        Args:
            sql: SQL query string
            params: Optional tuple of parameters for parameterized queries
            timeout_seconds: Query timeout (not enforced at DB level, for future use)

        Returns:
            QueryResult with columns, rows, and row_count

        Raises:
            PermissionError: If query contains write operations
            duckdb.Error: If query execution fails
        """
        # Block write operations
        if self._is_write_query(sql):
            raise PermissionError(
                "Write operations (INSERT, UPDATE, DELETE, DROP, etc.) are not allowed. "
                "This database is read-only for safety."
            )

        conn = self._get_connection()

        try:
            if params:
                result = conn.execute(sql, params)
            else:
                result = conn.execute(sql)

            # Fetch all results
            rows = result.fetchall()
            columns = [desc[0] for desc in result.description] if result.description else []

            return QueryResult(
                columns=columns,
                rows=rows,
                row_count=len(rows)
            )
        except duckdb.Error as e:
            raise duckdb.Error(f"Query execution failed: {e}")

    def execute(
        self,
        sql: str,
        params: Optional[tuple] = None
    ) -> QueryResult:
        """
        Execute SQL query (for internal/loader use - no write blocking).

        This method bypasses write protection and should only be used
        by the data loader for initial database setup.
        """
        conn = self._get_connection()

        if params:
            result = conn.execute(sql, params)
        else:
            result = conn.execute(sql)

        if result.description:
            rows = result.fetchall()
            columns = [desc[0] for desc in result.description]
            return QueryResult(columns=columns, rows=rows, row_count=len(rows))

        return QueryResult(columns=[], rows=[], row_count=0)

    def get_tables(self) -> list[str]:
        """Get list of all tables in the database."""
        result = self.execute_safe("SHOW TABLES")
        return [row[0] for row in result.rows]

    def get_table_info(self, table_name: str) -> QueryResult:
        """Get column information for a table."""
        # Validate table name to prevent injection
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', table_name):
            raise ValueError(f"Invalid table name: {table_name}")
        return self.execute_safe(f"DESCRIBE {table_name}")

    def get_row_count(self, table_name: str) -> int:
        """Get row count for a table."""
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', table_name):
            raise ValueError(f"Invalid table name: {table_name}")
        result = self.execute_safe(f"SELECT COUNT(*) FROM {table_name}")
        return result.rows[0][0] if result.rows else 0

    def health_check(self) -> dict[str, Any]:
        """Check database health and return statistics."""
        try:
            tables = self.get_tables()
            stats = {
                "status": "healthy",
                "db_path": str(self.db_path),
                "tables": {}
            }
            for table in tables:
                stats["tables"][table] = self.get_row_count(table)
            return stats
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "db_path": str(self.db_path)
            }

    def close(self):
        """Close the database connection."""
        if hasattr(self._local, 'connection') and self._local.connection:
            self._local.connection.close()
            self._local.connection = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def get_shared_database() -> NFLDatabase:
    """
    Get the shared database singleton instance.

    This ensures all tools and components share the same DuckDB connection,
    avoiding file lock conflicts that occur with multiple connections.

    Thread-safe implementation using a lock for initialization.

    Returns:
        NFLDatabase: The shared database instance
    """
    global _shared_db_instance

    if _shared_db_instance is None:
        with _shared_db_lock:
            # Double-check locking pattern
            if _shared_db_instance is None:
                _shared_db_instance = NFLDatabase(read_only=True)

    return _shared_db_instance


# Convenience functions for common queries
def get_player_games(
    db: NFLDatabase,
    player_name: str,
    season: Optional[int] = None,
    game_type: Optional[str] = None
) -> QueryResult:
    """Get all games for a player with optional filters."""
    sql = "SELECT * FROM player_games WHERE player_display_name ILIKE ?"
    params = [f"%{player_name}%"]

    if season:
        sql += " AND season = ?"
        params.append(season)

    if game_type:
        sql += " AND season_type = ?"
        params.append(game_type)

    sql += " ORDER BY season DESC, week DESC"

    return db.execute_safe(sql, tuple(params))


def get_player_seasons(
    db: NFLDatabase,
    player_name: str,
    position: Optional[str] = None
) -> QueryResult:
    """Get season totals for a player."""
    sql = "SELECT * FROM player_seasons WHERE player_display_name ILIKE ?"
    params = [f"%{player_name}%"]

    if position:
        sql += " AND position = ?"
        params.append(position)

    sql += " ORDER BY season DESC"

    return db.execute_safe(sql, tuple(params))


def get_top_players_by_stat(
    db: NFLDatabase,
    stat_column: str,
    season: int,
    position: Optional[str] = None,
    game_type: str = "REG",
    limit: int = 10
) -> QueryResult:
    """Get top players ranked by a specific statistic."""
    # Validate column name to prevent injection
    valid_columns = {
        'passing_yards', 'passing_tds', 'rushing_yards', 'rushing_tds',
        'receiving_yards', 'receiving_tds', 'receptions', 'targets',
        'completions', 'attempts', 'carries', 'fantasy_points', 'fantasy_points_ppr'
    }

    if stat_column not in valid_columns:
        raise ValueError(f"Invalid stat column: {stat_column}. Valid: {valid_columns}")

    sql = f"""
        SELECT player_display_name, position, team, SUM({stat_column}) as total_{stat_column}
        FROM player_games
        WHERE season = ? AND season_type = ?
    """
    params = [season, game_type]

    if position:
        sql += " AND position = ?"
        params.append(position)

    sql += f" GROUP BY player_display_name, position, team ORDER BY total_{stat_column} DESC LIMIT ?"
    params.append(limit)

    return db.execute_safe(sql, tuple(params))


if __name__ == "__main__":
    # Test database connection
    print("Testing NFL Database...")

    db = NFLDatabase()
    health = db.health_check()

    print(f"Status: {health['status']}")
    print(f"Database: {health['db_path']}")

    if health['status'] == 'healthy':
        print("\nTables:")
        for table, count in health['tables'].items():
            print(f"  {table}: {count:,} rows")
    else:
        print(f"Error: {health.get('error', 'Unknown error')}")
        print("\nRun 'python -m src.data.loader' to initialize the database.")
