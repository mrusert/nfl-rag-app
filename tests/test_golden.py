"""
Golden test cases - Questions with known correct answers.

These tests serve as regression tests to ensure the app continues
to provide accurate answers for key questions.

To add new golden test cases:
1. Add them to GOLDEN_CASES below
2. Run: pytest tests/test_golden.py -v
3. If tests pass, commit the change

Golden cases should:
- Have verifiable correct answers
- Cover important use cases
- Be stable (answers shouldn't change frequently)
"""

import pytest
from src.agent.tools import SQLQueryTool, PlayerStatsLookupTool, RankingsTool


# =============================================================================
# GOLDEN TEST CASES
# =============================================================================
# Add new golden cases here as you discover important questions that need
# to always return correct answers.

GOLDEN_CASES = [
    # Ranking questions
    {
        "id": "2024_passing_leader",
        "question": "Who led the NFL in passing yards in 2024?",
        "expected_answer_contains": ["Burrow"],
        "expected_value": {"stat": "passing_yards", "value_gte": 4900},
        "tool": "rankings",
    },
    {
        "id": "2024_rushing_leader",
        "question": "Who led the NFL in rushing yards in 2024?",
        "expected_answer_contains": ["Barkley", "Henry"],  # Either is acceptable
        "tool": "rankings",
    },

    # Player vs opponent questions
    {
        "id": "mahomes_vs_bills_playoffs",
        "question": "Patrick Mahomes vs Bills in playoffs",
        "expected_answer_contains": ["4"],  # 4 games
        "expected_values": {
            "games_played": 4,
            "total_passing_tds_gte": 8,
            "total_interceptions": 0,
        },
        "tool": "player_stats",
    },

    # Season stats questions
    {
        "id": "mahomes_2024_passing_tds",
        "question": "Patrick Mahomes 2024 passing touchdowns",
        "expected_answer_contains": ["31"],
        "tool": "sql_query",
    },

    # Historical data
    {
        "id": "data_coverage",
        "question": "What seasons are in the database?",
        "expected_answer_contains": ["2014", "2025"],
        "tool": "sql_query",
    },
]


# =============================================================================
# TEST IMPLEMENTATION
# =============================================================================

class TestGoldenCasesTools:
    """Test golden cases directly against tools (no LLM required)."""

    @pytest.fixture
    def sql_tool(self):
        return SQLQueryTool()

    @pytest.fixture
    def stats_tool(self):
        return PlayerStatsLookupTool()

    @pytest.fixture
    def rankings_tool(self):
        return RankingsTool()

    def test_2024_passing_leader(self, rankings_tool):
        """Verify 2024 passing leader is Joe Burrow."""
        result = rankings_tool.execute("passing_yards", 2024, position="QB", limit=1)
        assert result.success, f"Tool failed: {result.error}"

        leader = result.data[0]
        assert "Burrow" in leader["player"], f"Expected Burrow, got {leader['player']}"
        assert leader["total_passing_yards"] >= 4900, f"Expected 4900+ yards, got {leader['total_passing_yards']}"

    def test_mahomes_vs_bills_playoffs(self, stats_tool):
        """Verify Mahomes vs Bills playoff record."""
        result = stats_tool.execute("Patrick Mahomes", opponent="BUF", season_type="POST")
        assert result.success, f"Tool failed: {result.error}"

        summary = result.data["summary"]
        assert summary["games_played"] == 4, f"Expected 4 games, got {summary['games_played']}"
        assert summary["total_passing_tds"] >= 8, f"Expected 8+ TDs, got {summary['total_passing_tds']}"
        assert summary["total_interceptions"] == 0, f"Expected 0 INTs, got {summary['total_interceptions']}"

    def test_mahomes_2024_stats(self, sql_tool):
        """Verify Mahomes 2024 season stats."""
        result = sql_tool.execute("""
            SELECT SUM(passing_tds) as tds, SUM(passing_yards) as yards
            FROM player_games
            WHERE player_display_name ILIKE '%Mahomes%'
            AND season = 2024
        """)
        assert result.success, f"Tool failed: {result.error}"

        stats = result.data[0]
        assert stats["tds"] == 31, f"Expected 31 TDs, got {stats['tds']}"
        assert stats["yards"] > 4500, f"Expected 4500+ yards, got {stats['yards']}"

    def test_data_seasons_coverage(self, sql_tool):
        """Verify data covers expected seasons."""
        result = sql_tool.execute("SELECT MIN(season), MAX(season) FROM player_games")
        assert result.success, f"Tool failed: {result.error}"

        min_season, max_season = result.data[0].values()
        assert min_season <= 2015, f"Expected data from 2015 or earlier, got {min_season}"
        assert max_season >= 2024, f"Expected data through 2024, got {max_season}"

    def test_team_count(self, sql_tool):
        """Verify team count."""
        result = sql_tool.execute("SELECT COUNT(DISTINCT team_abbr) FROM teams")
        assert result.success, f"Tool failed: {result.error}"

        count = list(result.data[0].values())[0]
        assert count >= 32, f"Expected 32+ teams, got {count}"


@pytest.mark.skipif(
    not __import__("src.agent.agent", fromlist=["NFLStatsAgent"]).NFLStatsAgent().is_available(),
    reason="Ollama not available - skipping agent golden tests"
)
class TestGoldenCasesAgent:
    """Test golden cases through the full agent (requires LLM)."""

    @pytest.fixture
    def agent(self):
        from src.agent.agent import NFLStatsAgent
        return NFLStatsAgent()

    def test_passing_leader_question(self, agent):
        """Agent should correctly answer passing leader question."""
        response = agent.run("Who led the NFL in passing yards in 2024?")
        assert "Burrow" in response.answer, f"Expected Burrow in answer: {response.answer}"

    def test_mahomes_vs_bills_question(self, agent):
        """Agent should correctly answer Mahomes vs Bills question."""
        response = agent.run("What is Patrick Mahomes record against the Bills in the playoffs?")
        # Should mention 4-0 or 4 wins
        assert "4" in response.answer, f"Expected '4' in answer: {response.answer}"


# =============================================================================
# UTILITY: Add new golden cases
# =============================================================================

def add_golden_case(
    question: str,
    tool: str,
    expected_contains: list,
    case_id: str = None,
):
    """
    Utility to add new golden cases.

    Usage:
        from tests.test_golden import add_golden_case
        add_golden_case(
            question="Who won the Super Bowl in 2024?",
            tool="sql_query",
            expected_contains=["Chiefs"],
            case_id="super_bowl_2024",
        )

    Then add the case to GOLDEN_CASES list above.
    """
    case = {
        "id": case_id or question[:30].replace(" ", "_").lower(),
        "question": question,
        "expected_answer_contains": expected_contains,
        "tool": tool,
    }
    print(f"Add this to GOLDEN_CASES in test_golden.py:\n{case}")
    return case
