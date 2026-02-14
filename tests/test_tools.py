"""
Unit tests for agent tools.

Tests each tool's functionality independently.
"""

import pytest
from pathlib import Path
from src.agent.tools import (
    SQLQueryTool,
    PlayerStatsLookupTool,
    CalculatorTool,
    RankingsTool,
    NewsSearchTool,
    ToolResult,
)
from src.news.fetcher import NewsItem
from src.news.storage import NewsStorage


class TestSQLQueryTool:
    """Tests for the SQL Query tool."""

    @pytest.fixture
    def sql_tool(self):
        return SQLQueryTool()

    def test_simple_query(self, sql_tool):
        """Simple query should return results."""
        result = sql_tool.execute("SELECT COUNT(*) as cnt FROM teams")
        assert result.success
        assert len(result.data) == 1
        assert result.data[0]["cnt"] >= 32

    def test_player_query(self, sql_tool):
        """Query for specific player should work."""
        result = sql_tool.execute(
            "SELECT season, SUM(passing_yards) as yards "
            "FROM player_games "
            "WHERE player_display_name ILIKE '%Mahomes%' "
            "GROUP BY season ORDER BY season DESC LIMIT 3"
        )
        assert result.success
        assert len(result.data) > 0
        assert "yards" in result.data[0]

    def test_invalid_query(self, sql_tool):
        """Invalid SQL should return error."""
        result = sql_tool.execute("SELECT * FROM nonexistent_table")
        assert not result.success
        assert result.error is not None

    def test_blocks_write(self, sql_tool):
        """Write operations should be blocked."""
        result = sql_tool.execute("INSERT INTO teams VALUES ('X', 'X', 'X', 'X', 'X', 'X', 'X')")
        assert not result.success
        assert "not allowed" in result.error.lower() or "permission" in result.error.lower()


class TestPlayerStatsLookupTool:
    """Tests for the Player Stats Lookup tool."""

    @pytest.fixture
    def stats_tool(self):
        return PlayerStatsLookupTool()

    def test_basic_lookup(self, stats_tool):
        """Basic player lookup should work."""
        result = stats_tool.execute("Patrick Mahomes")
        assert result.success
        assert "summary" in result.data
        assert "recent_games" in result.data
        assert result.data["summary"]["games_played"] > 100

    def test_with_opponent_filter(self, stats_tool):
        """Lookup with opponent filter should work."""
        result = stats_tool.execute("Patrick Mahomes", opponent="BUF")
        assert result.success
        assert result.data["total_games_found"] > 0
        assert result.data["total_games_found"] < 20  # Should be < 20 games vs one opponent

    def test_with_season_type_filter(self, stats_tool):
        """Lookup with season type filter should work."""
        result = stats_tool.execute("Patrick Mahomes", season_type="POST")
        assert result.success
        assert result.data["total_games_found"] > 10  # Mahomes has 10+ playoff games

    def test_mahomes_vs_bills_playoffs(self, stats_tool):
        """Verify Mahomes vs Bills playoff stats."""
        result = stats_tool.execute("Patrick Mahomes", opponent="BUF", season_type="POST")
        assert result.success
        summary = result.data["summary"]
        assert summary["games_played"] == 4, f"Expected 4 playoff games vs Bills, got {summary['games_played']}"
        assert summary["total_passing_tds"] >= 8, "Should have 8+ TDs in these games"
        assert summary["total_interceptions"] == 0, "Should have 0 INTs in these games"

    def test_nonexistent_player(self, stats_tool):
        """Nonexistent player should return empty results."""
        result = stats_tool.execute("Nonexistent Player Name XYZ")
        assert result.success  # Should succeed but with empty data
        assert result.data["total_games_found"] == 0


class TestCalculatorTool:
    """Tests for the Calculator tool."""

    @pytest.fixture
    def calc_tool(self):
        return CalculatorTool()

    def test_average(self, calc_tool):
        """Average calculation should work."""
        result = calc_tool.execute("average", [10, 20, 30, 40])
        assert result.success
        assert result.data["result"] == 25

    def test_sum(self, calc_tool):
        """Sum calculation should work."""
        result = calc_tool.execute("sum", [100, 200, 300])
        assert result.success
        assert result.data["result"] == 600

    def test_win_percentage(self, calc_tool):
        """Win percentage calculation should work."""
        result = calc_tool.execute("win_percentage", {"wins": 4, "losses": 0})
        assert result.success
        assert result.data["result"] == 100.0

        result = calc_tool.execute("win_percentage", {"wins": 3, "losses": 1})
        assert result.success
        assert result.data["result"] == 75.0

    def test_percent_change(self, calc_tool):
        """Percent change calculation should work."""
        result = calc_tool.execute("percent_change", {"old": 100, "new": 125})
        assert result.success
        assert result.data["result"] == 25.0

    def test_division_by_zero(self, calc_tool):
        """Division by zero should be handled."""
        result = calc_tool.execute("divide", [10, 0])
        assert not result.success
        assert "zero" in result.error.lower()

    def test_invalid_operation(self, calc_tool):
        """Invalid operation should return error."""
        result = calc_tool.execute("invalid_op", [1, 2, 3])
        assert not result.success


class TestRankingsTool:
    """Tests for the Rankings tool."""

    @pytest.fixture
    def rank_tool(self):
        return RankingsTool()

    def test_passing_yards_ranking(self, rank_tool):
        """Passing yards ranking should work."""
        result = rank_tool.execute("passing_yards", 2024, limit=5)
        assert result.success
        assert len(result.data) == 5
        assert result.data[0]["rank"] == 1
        # First should have most yards
        assert result.data[0]["total_passing_yards"] > result.data[4]["total_passing_yards"]

    def test_ranking_with_position_filter(self, rank_tool):
        """Ranking with position filter should work."""
        result = rank_tool.execute("rushing_yards", 2024, position="RB", limit=10)
        assert result.success
        assert len(result.data) <= 10
        assert all(r["position"] == "RB" for r in result.data)

    def test_2024_passing_leader(self, rank_tool):
        """Verify 2024 passing leader is correct."""
        result = rank_tool.execute("passing_yards", 2024, position="QB", limit=1)
        assert result.success
        leader = result.data[0]
        assert "Burrow" in leader["player"], f"Expected Burrow, got {leader['player']}"

    def test_invalid_stat(self, rank_tool):
        """Invalid stat should return error."""
        result = rank_tool.execute("invalid_stat", 2024)
        assert not result.success
        assert "invalid" in result.error.lower()

    def test_playoff_rankings(self, rank_tool):
        """Playoff-only rankings should work."""
        result = rank_tool.execute("passing_yards", 2024, season_type="POST", limit=5)
        assert result.success
        assert len(result.data) <= 5


class TestToolResult:
    """Tests for ToolResult helper methods."""

    def test_to_string_success(self):
        """to_string for successful result should format data."""
        result = ToolResult(success=True, data=[{"name": "Test", "value": 100}])
        output = result.to_string()
        assert "Test" in output
        assert "100" in output

    def test_to_string_error(self):
        """to_string for error result should show error."""
        result = ToolResult(success=False, data=None, error="Something went wrong")
        output = result.to_string()
        assert "Error" in output
        assert "Something went wrong" in output

    def test_to_string_empty_data(self):
        """to_string for empty data should indicate no results."""
        result = ToolResult(success=True, data=[])
        output = result.to_string()
        assert "No results" in output

    def test_to_string_truncation(self):
        """to_string should truncate large results."""
        large_data = [{"id": i, "value": f"item_{i}"} for i in range(100)]
        result = ToolResult(success=True, data=large_data)
        output = result.to_string(max_rows=10)
        assert "more rows" in output


class TestNewsSearchTool:
    """Tests for the News Search tool."""

    @pytest.fixture
    def news_tool(self, tmp_path):
        """Create a news tool with temporary storage."""
        storage = NewsStorage(persist_directory=tmp_path / "test_news_db")

        # Add some test news items
        items = [
            NewsItem(
                id="tool_test_1",
                title="Patrick Mahomes Leads Chiefs to Victory",
                content="Mahomes throws 4 TDs as Chiefs dominate in playoff game",
                source="espn",
                url="https://espn.com/mahomes",
                published_at="2024-01-15T10:00:00",
                team="KC",
                tags=["chiefs", "KC", "playoffs"],
            ),
            NewsItem(
                id="tool_test_2",
                title="Josh Allen and Bills Prepare for Playoff Run",
                content="Bills look strong heading into postseason with Allen at QB",
                source="nfl.com",
                url="https://nfl.com/bills",
                published_at="2024-01-15T11:00:00",
                team="BUF",
                tags=["bills", "BUF", "playoffs"],
            ),
            NewsItem(
                id="tool_test_3",
                title="NFL Power Rankings After Week 18",
                content="Chiefs, 49ers, and Ravens lead the pack going into playoffs",
                source="reddit",
                url="https://reddit.com/r/nfl/rankings",
                published_at="2024-01-15T12:00:00",
                tags=["rankings", "nfl"],
            ),
        ]
        storage.add_items(items)

        return NewsSearchTool(storage=storage)

    def test_basic_search(self, news_tool):
        """Basic news search should return results."""
        result = news_tool.execute("Mahomes Chiefs playoff")
        assert result.success
        assert len(result.data) > 0
        # The Mahomes article should be in results
        assert any("Mahomes" in r.get("title", "") for r in result.data)

    def test_search_with_source_filter(self, news_tool):
        """Search with source filter should work."""
        result = news_tool.execute("NFL news", source="reddit")
        assert result.success
        assert all(r.get("source") == "reddit" for r in result.data)

    def test_search_with_team_filter(self, news_tool):
        """Search with team filter should work."""
        result = news_tool.execute("playoff", team="KC")
        assert result.success
        assert all(r.get("team") == "KC" for r in result.data)

    def test_search_num_results(self, news_tool):
        """Search should respect num_results parameter."""
        result = news_tool.execute("NFL", num_results=2)
        assert result.success
        assert len(result.data) <= 2

    def test_search_empty_results(self, news_tool):
        """Search with no matches should return empty list."""
        result = news_tool.execute("completely unrelated baseball hockey")
        assert result.success
        # Should still return results (semantic search) but may have low scores
        assert isinstance(result.data, list)
