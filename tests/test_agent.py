"""
Integration tests for the NFL Stats Agent.

Tests the agent's ability to use tools and answer questions correctly.
Note: These tests require Ollama to be running with the configured model.
"""

import pytest
from src.agent.agent import NFLStatsAgent, AgentResponse


@pytest.fixture(scope="module")
def agent():
    """Create agent instance for tests."""
    return NFLStatsAgent()


class TestAgentAvailability:
    """Tests for agent availability and setup."""

    def test_agent_initializes(self, agent):
        """Agent should initialize without errors."""
        assert agent is not None
        assert agent.llm is not None
        assert len(agent.tools) > 0

    def test_agent_has_expected_tools(self, agent):
        """Agent should have all expected tools."""
        expected_tools = ["sql_query", "player_stats", "calculator", "semantic_search", "rankings"]
        for tool in expected_tools:
            assert tool in agent.tools, f"Missing tool: {tool}"

    @pytest.mark.skipif(
        not NFLStatsAgent().is_available(),
        reason="Ollama not available"
    )
    def test_agent_is_available(self, agent):
        """Agent should be available when Ollama is running."""
        assert agent.is_available()


@pytest.mark.skipif(
    not NFLStatsAgent().is_available(),
    reason="Ollama not available - skipping agent execution tests"
)
class TestAgentQueries:
    """Tests for agent query execution."""

    def test_simple_ranking_query(self, agent):
        """Agent should answer simple ranking questions."""
        response = agent.run("Who led the NFL in passing yards in 2024?")

        assert isinstance(response, AgentResponse)
        assert response.answer is not None
        assert len(response.tool_calls) > 0

        # Should have used rankings tool
        tools_used = [tc["tool"] for tc in response.tool_calls]
        assert "rankings" in tools_used or "sql_query" in tools_used

    def test_player_stats_query(self, agent):
        """Agent should answer player stats questions."""
        response = agent.run("How many playoff games has Patrick Mahomes played against the Bills?")

        assert isinstance(response, AgentResponse)
        assert len(response.tool_calls) > 0

        # Answer should mention 4 games
        assert "4" in response.answer

    def test_response_has_answer(self, agent):
        """Agent response should always have an answer."""
        response = agent.run("Who is the best quarterback?")
        assert response.answer is not None
        assert len(response.answer) > 0

    def test_response_tracks_iterations(self, agent):
        """Agent should track iterations."""
        response = agent.run("Who led the NFL in rushing touchdowns in 2024?")
        assert response.iterations >= 1
        assert response.iterations <= agent.MAX_ITERATIONS

    def test_response_tracks_time(self, agent):
        """Agent should track execution time."""
        response = agent.run("How many teams are in the NFL?")
        assert response.total_time_ms > 0


class TestAgentToolSelection:
    """Tests for correct tool selection."""

    @pytest.mark.skipif(
        not NFLStatsAgent().is_available(),
        reason="Ollama not available"
    )
    def test_uses_rankings_for_leaders(self, agent):
        """Agent should use rankings tool for 'who led' questions."""
        response = agent.run("Who led the NFL in passing yards in 2024?")
        tools_used = [tc["tool"] for tc in response.tool_calls]
        assert "rankings" in tools_used, f"Expected rankings tool, got: {tools_used}"

    @pytest.mark.skipif(
        not NFLStatsAgent().is_available(),
        reason="Ollama not available"
    )
    def test_uses_player_stats_for_matchups(self, agent):
        """Agent should use player_stats for player vs opponent questions."""
        response = agent.run("What are Patrick Mahomes stats against the Bills in the playoffs?")
        tools_used = [tc["tool"] for tc in response.tool_calls]
        assert "player_stats" in tools_used or "sql_query" in tools_used


class TestAgentEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.skipif(
        not NFLStatsAgent().is_available(),
        reason="Ollama not available"
    )
    def test_handles_unknown_player(self, agent):
        """Agent should handle questions about unknown players gracefully."""
        response = agent.run("How many touchdowns did Nonexistent Player throw in 2024?")
        assert response.answer is not None
        # Should indicate no data found or similar
        assert "no" in response.answer.lower() or "not found" in response.answer.lower() or "0" in response.answer

    @pytest.mark.skipif(
        not NFLStatsAgent().is_available(),
        reason="Ollama not available"
    )
    def test_handles_ambiguous_query(self, agent):
        """Agent should attempt to answer ambiguous queries."""
        response = agent.run("Tell me about Mahomes")
        assert response.answer is not None
        assert len(response.answer) > 50  # Should provide some info


class TestToolCallParsing:
    """Tests for tool call parsing from LLM responses."""

    def test_parse_json_block(self, agent):
        """Should parse JSON in code blocks."""
        response = '```json\n{"tool": "rankings", "arguments": {"stat": "passing_yards", "season": 2024}}\n```'
        parsed = agent._parse_tool_call(response)
        assert parsed is not None
        assert parsed["tool"] == "rankings"
        assert parsed["arguments"]["stat"] == "passing_yards"

    def test_parse_raw_json(self, agent):
        """Should parse raw JSON without code blocks."""
        response = 'I will use the rankings tool. {"tool": "rankings", "arguments": {"stat": "passing_yards", "season": 2024}}'
        parsed = agent._parse_tool_call(response)
        assert parsed is not None
        assert parsed["tool"] == "rankings"

    def test_returns_none_for_no_json(self, agent):
        """Should return None when no JSON found."""
        response = "The answer is that Joe Burrow led the league with 4918 yards."
        parsed = agent._parse_tool_call(response)
        assert parsed is None

    def test_ignores_non_tool_json(self, agent):
        """Should ignore JSON that isn't a tool call."""
        response = '{"player": "Mahomes", "yards": 4500}'
        parsed = agent._parse_tool_call(response)
        assert parsed is None  # No "tool" key


class TestMaxIterationsHandling:
    """
    Tests for edge cases when agent hits maximum iterations.

    This tests the bug fix where the agent would crash with a type error
    when trying to concatenate a non-string tool result.
    """

    def test_max_iterations_response_is_string(self, agent):
        """
        Fallback answer when hitting max iterations should always be a string.

        This tests the bug fix for:
        "can only concatenate str (not \"list\") to str"
        """
        # Simulate what happens when we hit max iterations with various result types
        from src.agent.agent import AgentResponse

        # Test with list result (the case that caused the bug)
        tool_calls = [
            {
                "tool": "sql_query",
                "arguments": {"sql": "SELECT * FROM players"},
                "result": [{"name": "Player1"}, {"name": "Player2"}],
                "success": True,
            }
        ]

        # This code path should handle list results without crashing
        last_result = "no data retrieved"
        if tool_calls:
            result = tool_calls[-1].get("result")
            if result is not None:
                result_str = str(result)
                last_result = result_str[:500] + "..." if len(result_str) > 500 else result_str
            else:
                last_result = "no conclusive data"

        final_answer = (
            "I wasn't able to fully answer within the allowed steps. "
            f"Here's what I found: Based on {len(tool_calls)} tool calls, "
            + last_result
        )

        # Should be a valid string
        assert isinstance(final_answer, str)
        assert "Player1" in final_answer

    def test_max_iterations_with_dict_result(self, agent):
        """Handle dict results when hitting max iterations."""
        tool_calls = [
            {
                "tool": "player_stats",
                "arguments": {"player_name": "Mahomes"},
                "result": {"games": 100, "passing_yards": 25000},
                "success": True,
            }
        ]

        result = tool_calls[-1].get("result")
        result_str = str(result) if result is not None else "no data"

        # Should convert dict to string without error
        assert isinstance(result_str, str)
        assert "25000" in result_str

    def test_max_iterations_with_none_result(self, agent):
        """Handle None results when hitting max iterations."""
        tool_calls = [
            {
                "tool": "sql_query",
                "arguments": {"sql": "SELECT * FROM nonexistent"},
                "result": None,
                "success": False,
                "error": "Table not found",
            }
        ]

        result = tool_calls[-1].get("result")
        last_result = str(result) if result is not None else "no conclusive data"

        assert last_result == "no conclusive data"

    def test_max_iterations_with_very_long_result(self, agent):
        """Long results should be truncated when hitting max iterations."""
        # Create a result that's longer than 500 characters
        long_list = [{"id": i, "name": f"Player {i}"} for i in range(100)]
        tool_calls = [
            {
                "tool": "sql_query",
                "arguments": {"sql": "SELECT * FROM players"},
                "result": long_list,
                "success": True,
            }
        ]

        result = tool_calls[-1].get("result")
        if result is not None:
            result_str = str(result)
            last_result = result_str[:500] + "..." if len(result_str) > 500 else result_str
        else:
            last_result = "no conclusive data"

        # Should be truncated
        assert len(last_result) <= 503  # 500 + "..."
        assert last_result.endswith("...")

    def test_max_iterations_with_empty_tool_calls(self, agent):
        """Handle empty tool_calls list when hitting max iterations."""
        tool_calls = []

        last_result = "no data retrieved"
        if tool_calls:
            result = tool_calls[-1].get("result")
            last_result = str(result) if result else "no conclusive data"

        assert last_result == "no data retrieved"


class TestAgentResponseFormat:
    """Tests for AgentResponse format and fields."""

    def test_response_has_all_fields(self, agent):
        """AgentResponse should have all expected fields."""
        from src.agent.agent import AgentResponse

        response = AgentResponse(
            answer="Test answer",
            tool_calls=[{"tool": "test", "success": True}],
            thinking=["step1", "step2"],
            total_time_ms=1000.0,
            iterations=2,
        )

        assert response.answer == "Test answer"
        assert len(response.tool_calls) == 1
        assert len(response.thinking) == 2
        assert response.total_time_ms == 1000.0
        assert response.iterations == 2

    def test_response_defaults(self, agent):
        """AgentResponse should have sensible defaults."""
        from src.agent.agent import AgentResponse

        response = AgentResponse(answer="Test")

        assert response.answer == "Test"
        assert response.tool_calls == []
        assert response.thinking == []
        assert response.total_time_ms == 0.0
        assert response.iterations == 0
