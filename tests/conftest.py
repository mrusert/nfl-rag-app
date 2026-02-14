"""
Pytest configuration and fixtures for NFL RAG App tests.
"""

import pytest
from pathlib import Path
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(scope="session")
def db():
    """Provide a database connection for tests."""
    from src.data.database import NFLDatabase
    database = NFLDatabase()
    yield database
    database.close()


@pytest.fixture(scope="session")
def tools():
    """Provide initialized tools for tests."""
    from src.agent.tools import get_all_tools
    return {tool.name: tool for tool in get_all_tools()}


@pytest.fixture(scope="session")
def agent():
    """Provide an agent instance for tests."""
    from src.agent.agent import NFLStatsAgent
    return NFLStatsAgent()


@pytest.fixture(scope="module")
def client():
    """Provide a test client for API tests."""
    from fastapi.testclient import TestClient
    from src.api.main import app
    with TestClient(app) as c:
        yield c


# Golden test cases - questions with known correct answers
# These serve as regression tests
GOLDEN_TEST_CASES = [
    {
        "id": "passing_leader_2024",
        "question": "Who led the NFL in passing yards in 2024?",
        "expected_contains": ["Joe Burrow", "4918", "4,918"],
        "expected_tool": "rankings",
    },
    {
        "id": "mahomes_vs_bills_playoffs",
        "question": "What is Patrick Mahomes record against the Bills in the playoffs?",
        "expected_contains": ["4", "0", "undefeated"],  # 4-0
        "expected_tool": "player_stats",
    },
    {
        "id": "top_rusher_2024",
        "question": "Who led the NFL in rushing yards in 2024?",
        "expected_tool": "rankings",
        # Don't hardcode answer - just verify tool was used correctly
    },
    {
        "id": "mahomes_2024_stats",
        "question": "How many passing touchdowns did Patrick Mahomes throw in 2024?",
        "expected_contains": ["31"],  # Based on our data
        "expected_tool": "sql_query",
    },
]


@pytest.fixture
def golden_cases():
    """Provide golden test cases."""
    return GOLDEN_TEST_CASES
