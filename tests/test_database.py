"""
Unit tests for the DuckDB database layer.

Tests database connectivity, query execution, and data integrity.
"""

import pytest
from src.data.database import NFLDatabase, QueryResult


class TestDatabaseConnection:
    """Tests for database connection and basic operations."""

    def test_database_connects(self, db):
        """Database should connect without errors."""
        assert db is not None
        assert db.db_path.exists()

    def test_health_check(self, db):
        """Health check should return healthy status."""
        health = db.health_check()
        assert health["status"] == "healthy"
        assert "tables" in health

    def test_tables_exist(self, db):
        """Required tables should exist."""
        tables = db.get_tables()
        expected = ["player_games", "player_seasons", "games", "players", "teams"]
        for table in expected:
            assert table in tables, f"Missing table: {table}"


class TestQueryExecution:
    """Tests for query execution."""

    def test_simple_select(self, db):
        """Simple SELECT query should work."""
        result = db.execute_safe("SELECT COUNT(*) as cnt FROM player_games")
        assert result.row_count == 1
        assert result.rows[0][0] > 200000  # Should have 200K+ rows

    def test_query_with_filter(self, db):
        """Query with WHERE clause should work."""
        result = db.execute_safe(
            "SELECT * FROM player_games WHERE player_display_name ILIKE ? LIMIT 5",
            ("%Mahomes%",)
        )
        assert result.row_count <= 5
        assert all("Mahomes" in str(row) for row in result.rows)

    def test_aggregation_query(self, db):
        """Aggregation queries should work."""
        result = db.execute_safe("""
            SELECT team, COUNT(*) as games
            FROM player_games
            WHERE season = 2024
            GROUP BY team
            ORDER BY games DESC
            LIMIT 5
        """)
        assert result.row_count == 5
        assert all(row[1] > 0 for row in result.rows)

    def test_query_returns_correct_columns(self, db):
        """Query should return correct column names."""
        result = db.execute_safe(
            "SELECT player_display_name, passing_yards FROM player_games LIMIT 1"
        )
        assert "player_display_name" in result.columns
        assert "passing_yards" in result.columns


class TestQuerySafety:
    """Tests for query safety (blocking write operations)."""

    def test_blocks_insert(self, db):
        """INSERT statements should be blocked."""
        with pytest.raises(PermissionError):
            db.execute_safe("INSERT INTO teams VALUES ('TEST', 'Test Team', 'Test', 'AFC', 'East', '#000', '#FFF')")

    def test_blocks_update(self, db):
        """UPDATE statements should be blocked."""
        with pytest.raises(PermissionError):
            db.execute_safe("UPDATE teams SET team_name = 'Hacked' WHERE team_abbr = 'KC'")

    def test_blocks_delete(self, db):
        """DELETE statements should be blocked."""
        with pytest.raises(PermissionError):
            db.execute_safe("DELETE FROM teams WHERE team_abbr = 'TEST'")

    def test_blocks_drop(self, db):
        """DROP statements should be blocked."""
        with pytest.raises(PermissionError):
            db.execute_safe("DROP TABLE teams")


class TestDataIntegrity:
    """Tests for data integrity and correctness."""

    def test_seasons_range(self, db):
        """Data should cover expected seasons."""
        result = db.execute_safe("SELECT MIN(season), MAX(season) FROM player_games")
        min_season, max_season = result.rows[0]
        assert min_season <= 2015, f"Expected data from 2015 or earlier, got {min_season}"
        assert max_season >= 2024, f"Expected data through 2024, got {max_season}"

    def test_team_count(self, db):
        """Should have at least 32 teams."""
        result = db.execute_safe("SELECT COUNT(*) FROM teams")
        assert result.rows[0][0] >= 32

    def test_mahomes_exists(self, db):
        """Patrick Mahomes should exist in the data."""
        result = db.execute_safe(
            "SELECT COUNT(*) FROM player_games WHERE player_display_name ILIKE '%Mahomes%'"
        )
        assert result.rows[0][0] > 100, "Mahomes should have 100+ game records"

    def test_2024_passing_leader(self, db):
        """Verify 2024 passing leader."""
        result = db.execute_safe("""
            SELECT player_display_name, SUM(passing_yards) as yards
            FROM player_games
            WHERE season = 2024 AND season_type = 'REG'
            GROUP BY player_display_name
            ORDER BY yards DESC
            LIMIT 1
        """)
        assert result.row_count == 1
        player, yards = result.rows[0]
        assert "Burrow" in player, f"Expected Burrow as 2024 leader, got {player}"
        assert yards > 4500, f"Expected 4500+ yards, got {yards}"


class TestQueryResultMethods:
    """Tests for QueryResult helper methods."""

    def test_to_dicts(self, db):
        """to_dicts should convert rows to dictionaries."""
        result = db.execute_safe("SELECT team_abbr, team_name FROM teams LIMIT 3")
        dicts = result.to_dicts()
        assert isinstance(dicts, list)
        assert len(dicts) == 3
        assert all(isinstance(d, dict) for d in dicts)
        assert "team_abbr" in dicts[0]

    def test_to_markdown_table(self, db):
        """to_markdown_table should format as markdown."""
        result = db.execute_safe("SELECT team_abbr, team_name FROM teams LIMIT 3")
        md = result.to_markdown_table()
        assert "|" in md
        assert "team_abbr" in md
        assert "---" in md
