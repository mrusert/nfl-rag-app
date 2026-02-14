"""
NFL Stats Agent - Tool-based query system.

Uses an LLM agent with specialized tools to answer NFL statistics questions.
The agent decides which tools to use based on the question type:
- SQL queries for precise statistics
- Semantic search for narrative/context questions
- Calculator for computations
"""

from src.agent.tools import (
    SQLQueryTool,
    PlayerStatsLookupTool,
    CalculatorTool,
    SemanticSearchTool,
    RankingsTool,
    ToolResult,
    get_all_tools,
    get_tools_description,
)
from src.agent.agent import NFLStatsAgent, AgentResponse

__all__ = [
    "NFLStatsAgent",
    "AgentResponse",
    "SQLQueryTool",
    "PlayerStatsLookupTool",
    "CalculatorTool",
    "SemanticSearchTool",
    "RankingsTool",
    "ToolResult",
    "get_all_tools",
    "get_tools_description",
]
