# NFL RAG to Agent Refactor Guide

## Overview

This document provides step-by-step instructions for refactoring the NFL RAG application from a pure RAG (Retrieval-Augmented Generation) architecture to a hybrid Agent-based architecture. The agent will use structured SQL queries as the primary method for answering stats questions, with RAG demoted to one tool among many.

### Why This Refactor?

RAG has fundamental limitations for sports statistics:
- **Temporal blindness**: Can't distinguish 2024 stats from 2019 stats reliably
- **No calculations**: LLM hallucinates math on retrieved chunks
- **Context fragmentation**: Player careers split across hundreds of chunks
- **Numbers don't embed well**: "324 yards" and "324 passing yards" have different vectors

The agent approach uses:
- **SQL for precise queries**: Exact filters, aggregations, joins
- **Tools for specific tasks**: Calculator, comparisons, rankings
- **RAG for narratives**: "Tell me about the famous game" still works
- **LLM for orchestration**: Decides which tools to use

### Current Architecture

```
User Question → Embed → Vector Search → Retrieved Chunks → LLM → Answer
```

### Target Architecture

```
User Question → LLM Agent → Select Tools → Execute Tools → Synthesize → Answer
                              ↓
                    ┌─────────┴─────────┐
                    ↓         ↓         ↓
                SQL Tool  Calc Tool  RAG Tool
                    ↓         ↓         ↓
                 DuckDB   Python    ChromaDB
```

---

## Phase 1: DuckDB Data Layer

### 1.1 Install Dependencies

Add to `requirements.txt`:
```
duckdb>=0.10.0
pyarrow>=14.0.0
```

Then run:
```bash
pip install duckdb pyarrow
```

### 1.2 Create Database Module

Create `src/data/__init__.py`:
```python
"""NFL Data Layer - DuckDB interface for structured queries."""

from src.data.database import NFLDatabase
from src.data.loader import load_data_to_duckdb

__all__ = ["NFLDatabase", "load_data_to_duckdb"]
```

Create `src/data/database.py`:
```python
"""
DuckDB database interface for NFL data.

Provides fast SQL queries over NFL statistics without the overhead
of vector embeddings or similarity search.
"""

import duckdb
from pathlib import Path
from typing import Optional, Any
import json

from src.config import DATA_DIR


class NFLDatabase:
    """
    DuckDB interface for NFL statistics.
    
    Usage:
        db = NFLDatabase()
        results = db.query("SELECT * FROM player_games WHERE player_name = 'Patrick Mahomes'")
    """
    
    DB_PATH = DATA_DIR / "nfl.duckdb"
    
    def __init__(self, db_path: Optional[Path] = None):
        """Initialize database connection."""
        self.db_path = db_path or self.DB_PATH
        self.conn = duckdb.connect(str(self.db_path))
        self._setup_tables()
    
    def _setup_tables(self):
        """Create tables if they don't exist."""
        # Check if tables exist
        tables = self.conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
        ).fetchall()
        table_names = [t[0] for t in tables]
        
        if 'games' not in table_names:
            print("Database tables not found. Run load_data_to_duckdb() first.")
    
    def query(self, sql: str, params: Optional[list] = None) -> list[dict]:
        """
        Execute a SQL query and return results as list of dicts.
        
        Args:
            sql: SQL query string
            params: Optional query parameters
            
        Returns:
            List of row dictionaries
        """
        try:
            if params:
                result = self.conn.execute(sql, params)
            else:
                result = self.conn.execute(sql)
            
            columns = [desc[0] for desc in result.description]
            rows = result.fetchall()
            
            return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            return [{"error": str(e)}]
    
    def query_df(self, sql: str):
        """Execute query and return as DataFrame."""
        return self.conn.execute(sql).fetchdf()
    
    # Convenience methods for common queries
    
    def get_player_games(
        self,
        player_name: str,
        opponent: Optional[str] = None,
        season: Optional[int] = None,
        playoffs_only: bool = False,
    ) -> list[dict]:
        """Get games for a specific player with optional filters."""
        conditions = ["player_name = ?"]
        params = [player_name]
        
        if opponent:
            conditions.append("opponent = ?")
            params.append(opponent)
        
        if season:
            conditions.append("season = ?")
            params.append(season)
        
        if playoffs_only:
            conditions.append("game_type != 'REG'")
        
        sql = f"""
            SELECT *
            FROM player_games
            WHERE {' AND '.join(conditions)}
            ORDER BY season DESC, week DESC
        """
        
        return self.query(sql, params)
    
    def get_player_stats_summary(
        self,
        player_name: str,
        opponent: Optional[str] = None,
        playoffs_only: bool = False,
    ) -> dict:
        """Get aggregated stats for a player."""
        conditions = ["player_name = ?"]
        params = [player_name]
        
        if opponent:
            conditions.append("opponent = ?")
            params.append(opponent)
        
        if playoffs_only:
            conditions.append("game_type != 'REG'")
        
        sql = f"""
            SELECT 
                COUNT(*) as games_played,
                SUM(CASE WHEN result = 'W' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN result = 'L' THEN 1 ELSE 0 END) as losses,
                ROUND(AVG(passing_yards), 1) as avg_passing_yards,
                SUM(passing_tds) as total_passing_tds,
                SUM(interceptions) as total_ints,
                ROUND(AVG(rushing_yards), 1) as avg_rushing_yards,
                SUM(rushing_tds) as total_rushing_tds
            FROM player_games
            WHERE {' AND '.join(conditions)}
        """
        
        results = self.query(sql, params)
        return results[0] if results else {}
    
    def get_game_by_teams(
        self,
        team1: str,
        team2: str,
        season: Optional[int] = None,
        playoffs_only: bool = False,
    ) -> list[dict]:
        """Get games between two teams."""
        conditions = [
            "((home_team = ? AND away_team = ?) OR (home_team = ? AND away_team = ?))"
        ]
        params = [team1, team2, team2, team1]
        
        if season:
            conditions.append("season = ?")
            params.append(season)
        
        if playoffs_only:
            conditions.append("game_type != 'REG'")
        
        sql = f"""
            SELECT *
            FROM games
            WHERE {' AND '.join(conditions)}
            ORDER BY season DESC, week DESC
        """
        
        return self.query(sql, params)
    
    def get_rankings(
        self,
        stat: str,
        season: int,
        position: Optional[str] = None,
        limit: int = 10,
        playoffs_only: bool = False,
    ) -> list[dict]:
        """Get player rankings for a specific stat."""
        conditions = ["season = ?"]
        params = [season]
        
        if position:
            conditions.append("position = ?")
            params.append(position)
        
        if playoffs_only:
            conditions.append("game_type != 'REG'")
        
        # Map common stat names to columns
        stat_columns = {
            "passing_yards": "SUM(passing_yards)",
            "passing_tds": "SUM(passing_tds)",
            "rushing_yards": "SUM(rushing_yards)",
            "rushing_tds": "SUM(rushing_tds)",
            "receiving_yards": "SUM(receiving_yards)",
            "receiving_tds": "SUM(receiving_tds)",
            "receptions": "SUM(receptions)",
            "interceptions": "SUM(interceptions)",
            "fantasy_points": "SUM(fantasy_points_ppr)",
        }
        
        stat_col = stat_columns.get(stat.lower(), f"SUM({stat})")
        
        sql = f"""
            SELECT 
                player_name,
                team,
                position,
                {stat_col} as total_{stat},
                COUNT(*) as games
            FROM player_games
            WHERE {' AND '.join(conditions)}
            GROUP BY player_name, team, position
            ORDER BY total_{stat} DESC
            LIMIT {limit}
        """
        
        return self.query(sql, params)
    
    def get_cold_weather_games(
        self,
        max_temp: float = 32.0,
        player_name: Optional[str] = None,
    ) -> list[dict]:
        """Get games played in cold weather."""
        conditions = ["temperature_f <= ?"]
        params = [max_temp]
        
        if player_name:
            conditions.append("player_name = ?")
            params.append(player_name)
        
        sql = f"""
            SELECT *
            FROM player_games
            WHERE {' AND '.join(conditions)}
            ORDER BY temperature_f ASC
        """
        
        return self.query(sql, params)
    
    def execute_safe(self, sql: str) -> list[dict]:
        """
        Execute a read-only query safely.
        Blocks any write operations.
        """
        sql_lower = sql.lower().strip()
        
        # Block write operations
        forbidden = ['insert', 'update', 'delete', 'drop', 'create', 'alter', 'truncate']
        if any(sql_lower.startswith(f) for f in forbidden):
            return [{"error": "Write operations are not allowed"}]
        
        return self.query(sql)
    
    def get_schema(self) -> str:
        """Get database schema information for the agent."""
        schema_info = []
        
        tables = self.conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
        ).fetchall()
        
        for (table_name,) in tables:
            columns = self.conn.execute(f"DESCRIBE {table_name}").fetchall()
            col_info = ", ".join([f"{c[0]} ({c[1]})" for c in columns])
            schema_info.append(f"{table_name}: {col_info}")
        
        return "\n".join(schema_info)
    
    def close(self):
        """Close database connection."""
        self.conn.close()


# CLI for testing
if __name__ == "__main__":
    db = NFLDatabase()
    
    print("Database Schema:")
    print(db.get_schema())
    
    print("\nMahomes vs Bills (playoffs):")
    games = db.get_player_games("Patrick Mahomes", opponent="BUF", playoffs_only=True)
    for g in games:
        print(f"  {g.get('season')} Week {g.get('week')}: {g.get('result')} - {g.get('passing_yards')} yards")
    
    print("\nMahomes vs Bills Summary:")
    summary = db.get_player_stats_summary("Patrick Mahomes", opponent="BUF", playoffs_only=True)
    print(f"  Record: {summary.get('wins')}-{summary.get('losses')}")
    print(f"  Avg Passing: {summary.get('avg_passing_yards')} yards")
```

### 1.3 Create Data Loader

Create `src/data/loader.py`:
```python
"""
Load NFL JSON data into DuckDB.

Converts the raw JSON files into structured DuckDB tables
for fast SQL queries.
"""

import json
from pathlib import Path
import duckdb

from src.config import RAW_DATA_DIR, DATA_DIR


def load_data_to_duckdb(
    raw_dir: Path = RAW_DATA_DIR,
    db_path: Path = DATA_DIR / "nfl.duckdb",
    force_reload: bool = False,
):
    """
    Load all NFL JSON data into DuckDB.
    
    Args:
        raw_dir: Directory containing raw JSON files
        db_path: Path for DuckDB database file
        force_reload: If True, drop and recreate all tables
    """
    print(f"Loading NFL data into DuckDB...")
    print(f"  Source: {raw_dir}")
    print(f"  Database: {db_path}")
    
    conn = duckdb.connect(str(db_path))
    
    if force_reload:
        print("  Dropping existing tables...")
        conn.execute("DROP TABLE IF EXISTS player_games")
        conn.execute("DROP TABLE IF EXISTS player_seasons")
        conn.execute("DROP TABLE IF EXISTS games")
        conn.execute("DROP TABLE IF EXISTS players")
        conn.execute("DROP TABLE IF EXISTS teams")
    
    # Load weekly offensive stats → player_games
    weekly_file = raw_dir / "weekly_offense.json"
    if weekly_file.exists():
        print(f"  Loading player_games from {weekly_file.name}...")
        with open(weekly_file) as f:
            weekly_data = json.load(f)
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS player_games AS
            SELECT * FROM read_json_auto(?)
        """, [str(weekly_file)])
        
        count = conn.execute("SELECT COUNT(*) FROM player_games").fetchone()[0]
        print(f"    Loaded {count:,} player game records")
    
    # Load seasonal stats → player_seasons
    seasonal_file = raw_dir / "seasonal_offense.json"
    if seasonal_file.exists():
        print(f"  Loading player_seasons from {seasonal_file.name}...")
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS player_seasons AS
            SELECT * FROM read_json_auto(?)
        """, [str(seasonal_file)])
        
        count = conn.execute("SELECT COUNT(*) FROM player_seasons").fetchone()[0]
        print(f"    Loaded {count:,} player season records")
    
    # Load schedules → games
    schedules_file = raw_dir / "schedules.json"
    if schedules_file.exists():
        print(f"  Loading games from {schedules_file.name}...")
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS games AS
            SELECT * FROM read_json_auto(?)
        """, [str(schedules_file)])
        
        count = conn.execute("SELECT COUNT(*) FROM games").fetchone()[0]
        print(f"    Loaded {count:,} game records")
    
    # Load rosters → players
    rosters_file = raw_dir / "rosters.json"
    if rosters_file.exists():
        print(f"  Loading players from {rosters_file.name}...")
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS players AS
            SELECT * FROM read_json_auto(?)
        """, [str(rosters_file)])
        
        count = conn.execute("SELECT COUNT(*) FROM players").fetchone()[0]
        print(f"    Loaded {count:,} player records")
    
    # Load teams
    teams_file = raw_dir / "teams.json"
    if teams_file.exists():
        print(f"  Loading teams from {teams_file.name}...")
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS teams AS
            SELECT * FROM read_json_auto(?)
        """, [str(teams_file)])
        
        count = conn.execute("SELECT COUNT(*) FROM teams").fetchone()[0]
        print(f"    Loaded {count:,} team records")
    
    # Create indexes for common queries
    print("  Creating indexes...")
    
    try:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_pg_player ON player_games(player_name)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_pg_team ON player_games(team)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_pg_opponent ON player_games(opponent)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_pg_season ON player_games(season)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_pg_game_type ON player_games(game_type)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_games_teams ON games(home_team, away_team)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_games_season ON games(season)")
    except Exception as e:
        print(f"    Warning creating indexes: {e}")
    
    conn.close()
    
    print("✓ Data loading complete!")
    

def verify_database(db_path: Path = DATA_DIR / "nfl.duckdb"):
    """Verify the database was loaded correctly."""
    conn = duckdb.connect(str(db_path))
    
    print("\nDatabase Verification:")
    print("=" * 50)
    
    tables = conn.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
    ).fetchall()
    
    for (table_name,) in tables:
        count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        print(f"  {table_name}: {count:,} rows")
    
    # Sample queries
    print("\nSample Queries:")
    print("-" * 50)
    
    # Mahomes career stats
    result = conn.execute("""
        SELECT 
            COUNT(*) as games,
            SUM(passing_yards) as total_yards,
            SUM(passing_tds) as total_tds
        FROM player_games 
        WHERE player_name = 'Patrick Mahomes'
    """).fetchone()
    print(f"  Mahomes career: {result[0]} games, {result[1]:,} yards, {result[2]} TDs")
    
    # Season count
    seasons = conn.execute("SELECT DISTINCT season FROM player_games ORDER BY season").fetchall()
    print(f"  Seasons covered: {seasons[0][0]} - {seasons[-1][0]}")
    
    conn.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Load NFL data into DuckDB")
    parser.add_argument("--force", action="store_true", help="Force reload all data")
    parser.add_argument("--verify", action="store_true", help="Verify database")
    
    args = parser.parse_args()
    
    if args.verify:
        verify_database()
    else:
        load_data_to_duckdb(force_reload=args.force)
        verify_database()
```

### 1.4 Run Data Loading

```bash
# Load data into DuckDB
python -m src.data.loader

# Verify it worked
python -m src.data.loader --verify
```

Expected output:
```
Loading NFL data into DuckDB...
  Source: data/raw
  Database: data/nfl.duckdb
  Loading player_games from weekly_offense.json...
    Loaded 250,000 player game records
  Loading player_seasons from seasonal_offense.json...
    Loaded 18,000 player season records
  Loading games from schedules.json...
    Loaded 3,400 game records
  ...
✓ Data loading complete!

Database Verification:
==================================================
  player_games: 250,000 rows
  player_seasons: 18,000 rows
  games: 3,400 rows
  players: 45,000 rows
  teams: 32 rows

Sample Queries:
--------------------------------------------------
  Mahomes career: 128 games, 32,456 yards, 245 TDs
  Seasons covered: 2014 - 2025
```

---

## Phase 2: Agent Tools

### 2.1 Create Tools Module

Create `src/agent/__init__.py`:
```python
"""NFL Stats Agent - Tool-based query system."""

from src.agent.tools import (
    SQLQueryTool,
    CalculatorTool,
    SemanticSearchTool,
    get_all_tools,
)
from src.agent.agent import NFLStatsAgent

__all__ = [
    "SQLQueryTool",
    "CalculatorTool", 
    "SemanticSearchTool",
    "NFLStatsAgent",
    "get_all_tools",
]
```

Create `src/agent/tools.py`:
```python
"""
Agent Tools for NFL Stats queries.

Each tool has:
- name: Identifier for the agent to reference
- description: What the tool does (used by LLM to decide when to use it)
- execute(): Run the tool with given arguments
"""

from typing import Any, Optional
from dataclasses import dataclass
import json
import re

from src.data.database import NFLDatabase


@dataclass
class ToolResult:
    """Result from a tool execution."""
    success: bool
    data: Any
    error: Optional[str] = None
    
    def to_string(self) -> str:
        """Format result for LLM context."""
        if not self.success:
            return f"Error: {self.error}"
        
        if isinstance(self.data, list):
            if len(self.data) == 0:
                return "No results found."
            # Format as readable table/list
            if len(self.data) <= 10:
                return json.dumps(self.data, indent=2, default=str)
            else:
                return json.dumps(self.data[:10], indent=2, default=str) + f"\n... and {len(self.data) - 10} more rows"
        
        return json.dumps(self.data, indent=2, default=str)


class SQLQueryTool:
    """
    Execute SQL queries against the NFL database.
    
    Use this tool for:
    - Getting specific player stats
    - Filtering games by conditions (opponent, weather, playoffs)
    - Aggregating stats (totals, averages)
    - Comparisons between players or teams
    """
    
    name = "sql_query"
    description = """Execute a SQL query against the NFL database.
    
Available tables:
- player_games: Individual player stats per game (player_name, team, opponent, season, week, game_type, passing_yards, passing_tds, rushing_yards, receiving_yards, temperature_f, result, etc.)
- player_seasons: Season totals per player
- games: Game results (home_team, away_team, home_score, away_score, season, week, game_type, temperature_f, spread, over_under)
- players: Player info (name, position, team, college, height, weight)
- teams: Team info (abbreviation, name, conference, division)

game_type values: 'REG' (regular season), 'WC' (wild card), 'DIV' (divisional), 'CON' (conference championship), 'SB' (super bowl)

Example queries:
- "SELECT * FROM player_games WHERE player_name = 'Patrick Mahomes' AND opponent = 'BUF'"
- "SELECT player_name, SUM(passing_yards) as total FROM player_games WHERE season = 2024 GROUP BY player_name ORDER BY total DESC LIMIT 10"
"""
    
    def __init__(self):
        self.db = NFLDatabase()
    
    def execute(self, sql: str) -> ToolResult:
        """Execute a SQL query."""
        try:
            # Safety check
            results = self.db.execute_safe(sql)
            
            if results and "error" in results[0]:
                return ToolResult(success=False, data=None, error=results[0]["error"])
            
            return ToolResult(success=True, data=results)
        except Exception as e:
            return ToolResult(success=False, data=None, error=str(e))


class PlayerStatsLookupTool:
    """
    Quick lookup for player statistics with common filters.
    
    Use this tool for simple player stat queries without writing SQL.
    """
    
    name = "player_stats"
    description = """Look up stats for a specific player.
    
Arguments:
- player_name (required): Full player name, e.g., "Patrick Mahomes"
- opponent (optional): Team abbreviation, e.g., "BUF"
- season (optional): Year, e.g., 2024
- playoffs_only (optional): true/false

Returns aggregated stats including games played, wins, losses, passing/rushing/receiving totals and averages.
"""
    
    def __init__(self):
        self.db = NFLDatabase()
    
    def execute(
        self,
        player_name: str,
        opponent: Optional[str] = None,
        season: Optional[int] = None,
        playoffs_only: bool = False,
    ) -> ToolResult:
        """Get player stats summary."""
        try:
            # Get individual games
            games = self.db.get_player_games(
                player_name=player_name,
                opponent=opponent,
                season=season,
                playoffs_only=playoffs_only,
            )
            
            # Get summary stats
            summary = self.db.get_player_stats_summary(
                player_name=player_name,
                opponent=opponent,
                playoffs_only=playoffs_only,
            )
            
            return ToolResult(
                success=True,
                data={
                    "summary": summary,
                    "games": games[:20],  # Limit to 20 most recent
                    "total_games_found": len(games),
                }
            )
        except Exception as e:
            return ToolResult(success=False, data=None, error=str(e))


class CalculatorTool:
    """
    Perform calculations on numbers.
    
    Use this tool for:
    - Computing averages, totals, percentages
    - Comparing numbers
    - Win/loss records and percentages
    """
    
    name = "calculator"
    description = """Perform mathematical calculations.
    
Supports:
- Basic math: add, subtract, multiply, divide
- Statistics: average, sum, min, max
- Percentages: percent, win_percentage
- Comparisons: compare two values

Examples:
- calculate("average", [280, 310, 295, 340])
- calculate("win_percentage", {"wins": 8, "losses": 2})
- calculate("percent_change", {"old": 4000, "new": 4500})
"""
    
    name = "calculator"
    
    def execute(self, operation: str, values: Any) -> ToolResult:
        """Perform a calculation."""
        try:
            if operation == "average":
                result = sum(values) / len(values) if values else 0
            elif operation == "sum":
                result = sum(values)
            elif operation == "min":
                result = min(values)
            elif operation == "max":
                result = max(values)
            elif operation == "win_percentage":
                wins = values.get("wins", 0)
                losses = values.get("losses", 0)
                total = wins + losses
                result = round(wins / total * 100, 1) if total > 0 else 0
            elif operation == "percent_change":
                old = values.get("old", 0)
                new = values.get("new", 0)
                result = round((new - old) / old * 100, 1) if old != 0 else 0
            elif operation == "divide":
                result = values[0] / values[1] if values[1] != 0 else 0
            else:
                # Try to evaluate as expression
                result = eval(operation, {"__builtins__": {}}, {"values": values})
            
            return ToolResult(success=True, data={"result": result, "operation": operation})
        except Exception as e:
            return ToolResult(success=False, data=None, error=str(e))


class SemanticSearchTool:
    """
    Search for relevant context using semantic similarity.
    
    Use this tool for:
    - Finding narrative descriptions of games
    - Getting context about specific events
    - Questions about "tell me about..." or "describe..."
    
    NOT for precise stats - use sql_query or player_stats instead.
    """
    
    name = "semantic_search"
    description = """Search for relevant information using semantic similarity.
    
Best for narrative/contextual questions like:
- "Tell me about the famous Chiefs-Bills playoff game"
- "What happened in the freezing cold playoff game?"
- "Describe Mahomes' best performance"

NOT recommended for:
- Precise statistics (use sql_query)
- Rankings or comparisons (use sql_query)
- Calculations (use calculator)

Arguments:
- query: Natural language search query
- num_results: Number of results (default 5)
- filters: Optional metadata filters (team, player_name, season, etc.)
"""
    
    def __init__(self):
        # Lazy load to avoid circular imports
        self._pipeline = None
    
    @property
    def pipeline(self):
        if self._pipeline is None:
            from src.rag.pipeline import NFLRAGPipeline
            self._pipeline = NFLRAGPipeline()
        return self._pipeline
    
    def execute(
        self,
        query: str,
        num_results: int = 5,
        filters: Optional[dict] = None,
    ) -> ToolResult:
        """Perform semantic search."""
        try:
            results = self.pipeline.retrieve(
                query=query,
                num_results=num_results,
                filters=filters,
                auto_filter=True,
            )
            
            formatted = []
            for r in results:
                formatted.append({
                    "text": r.text,
                    "score": round(r.score, 3),
                    "metadata": r.metadata,
                })
            
            return ToolResult(success=True, data=formatted)
        except Exception as e:
            return ToolResult(success=False, data=None, error=str(e))


class RankingsTool:
    """
    Get player rankings for various statistics.
    """
    
    name = "rankings"
    description = """Get top players ranked by a statistic.
    
Arguments:
- stat: Statistic to rank by (passing_yards, passing_tds, rushing_yards, rushing_tds, receiving_yards, receptions, fantasy_points)
- season: Year to rank (required)
- position: Filter by position (optional: QB, RB, WR, TE)
- limit: Number of players (default 10)
- playoffs_only: Only playoff games (default false)

Example: Get top 10 passers in 2024
"""
    
    def __init__(self):
        self.db = NFLDatabase()
    
    def execute(
        self,
        stat: str,
        season: int,
        position: Optional[str] = None,
        limit: int = 10,
        playoffs_only: bool = False,
    ) -> ToolResult:
        """Get rankings."""
        try:
            results = self.db.get_rankings(
                stat=stat,
                season=season,
                position=position,
                limit=limit,
                playoffs_only=playoffs_only,
            )
            return ToolResult(success=True, data=results)
        except Exception as e:
            return ToolResult(success=False, data=None, error=str(e))


def get_all_tools() -> list:
    """Get instances of all available tools."""
    return [
        SQLQueryTool(),
        PlayerStatsLookupTool(),
        CalculatorTool(),
        SemanticSearchTool(),
        RankingsTool(),
    ]


def get_tools_description() -> str:
    """Get formatted description of all tools for the agent prompt."""
    tools = get_all_tools()
    descriptions = []
    
    for tool in tools:
        descriptions.append(f"## {tool.name}\n{tool.description}")
    
    return "\n\n".join(descriptions)


# CLI for testing tools
if __name__ == "__main__":
    print("Testing NFL Agent Tools")
    print("=" * 60)
    
    # Test SQL Query
    print("\n1. SQL Query Tool:")
    sql_tool = SQLQueryTool()
    result = sql_tool.execute(
        "SELECT season, COUNT(*) as games, SUM(passing_tds) as tds "
        "FROM player_games WHERE player_name = 'Patrick Mahomes' "
        "GROUP BY season ORDER BY season DESC LIMIT 5"
    )
    print(result.to_string())
    
    # Test Player Stats
    print("\n2. Player Stats Tool:")
    stats_tool = PlayerStatsLookupTool()
    result = stats_tool.execute("Patrick Mahomes", opponent="BUF", playoffs_only=True)
    print(f"Summary: {result.data.get('summary') if result.success else result.error}")
    
    # Test Calculator
    print("\n3. Calculator Tool:")
    calc_tool = CalculatorTool()
    result = calc_tool.execute("win_percentage", {"wins": 4, "losses": 0})
    print(result.to_string())
    
    # Test Rankings
    print("\n4. Rankings Tool:")
    rank_tool = RankingsTool()
    result = rank_tool.execute("passing_yards", 2024, position="QB", limit=5)
    print(result.to_string())
```

### 2.2 Test Tools

```bash
python -m src.agent.tools
```

---

## Phase 3: Agent Orchestration

### 3.1 Create Agent Module

Create `src/agent/agent.py`:
```python
"""
NFL Stats Agent - Orchestrates tools to answer questions.

Uses a ReAct-style loop:
1. Receive question
2. Think about what tools to use
3. Execute tools
4. Observe results
5. Either answer or continue with more tools
"""

import json
import re
from typing import Optional
from dataclasses import dataclass

from src.rag.llm import OllamaLLM
from src.agent.tools import (
    get_all_tools,
    get_tools_description,
    ToolResult,
    SQLQueryTool,
    PlayerStatsLookupTool,
    CalculatorTool,
    SemanticSearchTool,
    RankingsTool,
)


AGENT_SYSTEM_PROMPT = """You are an expert NFL statistics analyst with access to a comprehensive database of NFL data from 2014-2025.

You have access to the following tools:

{tools_description}

## How to Use Tools

To use a tool, respond with a JSON block in this exact format:
```json
{{
    "tool": "tool_name",
    "arguments": {{
        "arg1": "value1",
        "arg2": "value2"
    }}
}}
```

## Guidelines

1. **For statistics questions** (averages, totals, records, comparisons):
   - Use `sql_query` or `player_stats` tools
   - These give precise, accurate numbers
   
2. **For rankings** (top players, leaders):
   - Use `rankings` tool
   
3. **For calculations** (percentages, averages of results):
   - Use `calculator` tool after getting raw numbers
   
4. **For narrative/context** (tell me about, describe, famous games):
   - Use `semantic_search` tool
   
5. **Think step by step**:
   - Break complex questions into parts
   - Get data first, then calculate if needed
   - Verify your answer makes sense

## Important

- Always use tools to get data - don't make up statistics
- Player names should be full names: "Patrick Mahomes" not "Mahomes"
- Team abbreviations: KC, BUF, MIA, etc.
- game_type: 'REG', 'WC', 'DIV', 'CON', 'SB'
- After getting tool results, provide a clear, conversational answer

## Response Format

After using tools and getting results, provide your final answer in natural language.
Include specific numbers and cite which games/seasons the data comes from.
"""


@dataclass
class AgentResponse:
    """Response from the agent."""
    answer: str
    tool_calls: list[dict]
    thinking: list[str]
    total_time_ms: float


class NFLStatsAgent:
    """
    Agent that uses tools to answer NFL statistics questions.
    
    Usage:
        agent = NFLStatsAgent()
        response = agent.run("What's Mahomes' record against the Bills in the playoffs?")
        print(response.answer)
    """
    
    MAX_ITERATIONS = 5
    
    def __init__(self, llm: Optional[OllamaLLM] = None):
        """Initialize the agent."""
        self.llm = llm or OllamaLLM()
        
        # Initialize tools
        self.tools = {tool.name: tool for tool in get_all_tools()}
        
        # Build system prompt
        self.system_prompt = AGENT_SYSTEM_PROMPT.format(
            tools_description=get_tools_description()
        )
    
    def _parse_tool_call(self, response: str) -> Optional[dict]:
        """Extract tool call from LLM response."""
        # Look for JSON block
        json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        
        # Try to find raw JSON
        try:
            # Find JSON object in response
            start = response.find('{')
            end = response.rfind('}') + 1
            if start != -1 and end > start:
                return json.loads(response[start:end])
        except json.JSONDecodeError:
            pass
        
        return None
    
    def _execute_tool(self, tool_call: dict) -> ToolResult:
        """Execute a tool call."""
        tool_name = tool_call.get("tool")
        arguments = tool_call.get("arguments", {})
        
        if tool_name not in self.tools:
            return ToolResult(
                success=False,
                data=None,
                error=f"Unknown tool: {tool_name}"
            )
        
        tool = self.tools[tool_name]
        
        try:
            # Handle different tool signatures
            if tool_name == "sql_query":
                return tool.execute(arguments.get("sql", arguments.get("query", "")))
            elif tool_name == "player_stats":
                return tool.execute(
                    player_name=arguments.get("player_name"),
                    opponent=arguments.get("opponent"),
                    season=arguments.get("season"),
                    playoffs_only=arguments.get("playoffs_only", False),
                )
            elif tool_name == "calculator":
                return tool.execute(
                    operation=arguments.get("operation"),
                    values=arguments.get("values"),
                )
            elif tool_name == "semantic_search":
                return tool.execute(
                    query=arguments.get("query"),
                    num_results=arguments.get("num_results", 5),
                    filters=arguments.get("filters"),
                )
            elif tool_name == "rankings":
                return tool.execute(
                    stat=arguments.get("stat"),
                    season=arguments.get("season"),
                    position=arguments.get("position"),
                    limit=arguments.get("limit", 10),
                    playoffs_only=arguments.get("playoffs_only", False),
                )
            else:
                return ToolResult(
                    success=False,
                    data=None,
                    error=f"Tool {tool_name} not implemented"
                )
        except Exception as e:
            return ToolResult(success=False, data=None, error=str(e))
    
    def run(self, question: str, verbose: bool = False) -> AgentResponse:
        """
        Run the agent to answer a question.
        
        Args:
            question: The user's question
            verbose: Print intermediate steps
            
        Returns:
            AgentResponse with answer and metadata
        """
        import time
        start_time = time.time()
        
        tool_calls = []
        thinking = []
        
        # Build conversation
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": question},
        ]
        
        for iteration in range(self.MAX_ITERATIONS):
            if verbose:
                print(f"\n--- Iteration {iteration + 1} ---")
            
            # Get LLM response
            response = self.llm.chat(messages, temperature=0.3)
            response_text = response.content
            
            if verbose:
                print(f"LLM: {response_text[:500]}...")
            
            # Check for tool call
            tool_call = self._parse_tool_call(response_text)
            
            if tool_call:
                # Execute tool
                tool_name = tool_call.get("tool")
                if verbose:
                    print(f"Tool: {tool_name}")
                    print(f"Args: {tool_call.get('arguments')}")
                
                result = self._execute_tool(tool_call)
                
                if verbose:
                    print(f"Result: {result.to_string()[:500]}...")
                
                # Record tool call
                tool_calls.append({
                    "tool": tool_name,
                    "arguments": tool_call.get("arguments"),
                    "result": result.data if result.success else result.error,
                    "success": result.success,
                })
                
                # Add to conversation
                messages.append({"role": "assistant", "content": response_text})
                messages.append({
                    "role": "user",
                    "content": f"Tool result:\n{result.to_string()}\n\nBased on this result, please provide your answer or use another tool if needed."
                })
                
                thinking.append(f"Used {tool_name}: {result.to_string()[:200]}")
            else:
                # No tool call - this is the final answer
                thinking.append("Generated final answer")
                
                elapsed_ms = (time.time() - start_time) * 1000
                
                return AgentResponse(
                    answer=response_text,
                    tool_calls=tool_calls,
                    thinking=thinking,
                    total_time_ms=elapsed_ms,
                )
        
        # Max iterations reached
        elapsed_ms = (time.time() - start_time) * 1000
        
        return AgentResponse(
            answer="I wasn't able to fully answer the question within the allowed steps. Here's what I found: " + thinking[-1] if thinking else "No results",
            tool_calls=tool_calls,
            thinking=thinking,
            total_time_ms=elapsed_ms,
        )


# CLI for testing
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="NFL Stats Agent")
    parser.add_argument("question", nargs="?", help="Question to ask")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show thinking process")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive mode")
    
    args = parser.parse_args()
    
    agent = NFLStatsAgent()
    
    if args.interactive:
        print("NFL Stats Agent - Interactive Mode")
        print("=" * 60)
        print("Ask questions about NFL statistics.")
        print("Type 'quit' to exit.")
        print("=" * 60)
        
        while True:
            question = input("\n📋 Your question: ").strip()
            
            if question.lower() in ("quit", "exit", "q"):
                break
            
            if not question:
                continue
            
            print("\n🤔 Thinking...")
            response = agent.run(question, verbose=args.verbose)
            
            print("\n" + "=" * 60)
            print("🏈 Answer:")
            print(response.answer)
            print("=" * 60)
            print(f"Tools used: {len(response.tool_calls)}")
            print(f"Time: {response.total_time_ms:.0f}ms")
    
    elif args.question:
        response = agent.run(args.question, verbose=args.verbose)
        
        print("\n" + "=" * 60)
        print("Answer:")
        print(response.answer)
        print("=" * 60)
        print(f"\nTools used: {[tc['tool'] for tc in response.tool_calls]}")
        print(f"Time: {response.total_time_ms:.0f}ms")
    
    else:
        parser.print_help()
```

### 3.2 Test Agent

```bash
# Single question
python -m src.agent.agent "What's Mahomes' record against the Bills in the playoffs?" -v

# Interactive mode
python -m src.agent.agent -i
```

---

## Phase 4: API Integration

### 4.1 Add Agent Endpoint

Add to `src/api/main.py`:

```python
# Add imports at the top
from src.agent.agent import NFLStatsAgent, AgentResponse

# Add new Pydantic models
class AgentRequest(BaseModel):
    """Request for agent queries."""
    question: str = Field(..., description="Question to ask", min_length=1, max_length=1000)
    verbose: bool = Field(default=False, description="Include thinking process")


class AgentResponseModel(BaseModel):
    """Response from agent."""
    answer: str
    tool_calls: list[dict]
    thinking: list[str]
    total_time_ms: float


# Add global agent instance
agent: Optional[NFLStatsAgent] = None


# Update startup event
@app.on_event("startup")
async def startup_event():
    global pipeline, agent
    
    print("Initializing NFL RAG Pipeline...")
    # ... existing pipeline initialization ...
    
    print("Initializing NFL Stats Agent...")
    try:
        agent = NFLStatsAgent()
        print("  Agent initialized with tools:", list(agent.tools.keys()))
    except Exception as e:
        print(f"  Warning: Agent initialization failed: {e}")
        agent = None


# Add new endpoint
@app.post("/agent", response_model=AgentResponseModel, tags=["Agent"])
async def agent_query(request: AgentRequest):
    """
    Ask a question using the agent (tool-based approach).
    
    Better for:
    - Statistics and numbers
    - Rankings and comparisons
    - Calculations and aggregations
    - Questions requiring precise data
    
    The agent will automatically select and use appropriate tools.
    """
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    try:
        response = agent.run(request.question, verbose=request.verbose)
        
        return AgentResponseModel(
            answer=response.answer,
            tool_calls=response.tool_calls,
            thinking=response.thinking if request.verbose else [],
            total_time_ms=response.total_time_ms,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/agent", response_model=AgentResponseModel, tags=["Agent"])
async def agent_query_get(
    q: str = Query(..., description="Question to ask", min_length=1),
):
    """Quick agent query via GET."""
    return await agent_query(AgentRequest(question=q))
```

### 4.2 Test API

```bash
# Start server
python -m src.api.main

# Test agent endpoint
curl "http://localhost:8000/agent?q=What+is+Mahomes+record+against+the+Bills+in+the+playoffs"

# Compare with RAG
curl "http://localhost:8000/query?q=What+is+Mahomes+record+against+the+Bills+in+the+playoffs"
```

---

## Phase 5: Testing & Comparison

### 5.1 Create Comparison Test

Create `tests/test_agent_vs_rag.py`:
```python
"""
Compare Agent vs RAG responses for accuracy and speed.
"""

import time
import json
from src.rag.pipeline import NFLRAGPipeline
from src.agent.agent import NFLStatsAgent


TEST_QUESTIONS = [
    # Stats questions (Agent should excel)
    {
        "question": "What is Patrick Mahomes' record against the Bills in the playoffs?",
        "expected_contains": ["4-0", "four wins", "undefeated"],
        "type": "stats",
    },
    {
        "question": "Who led the NFL in passing yards in 2024?",
        "type": "ranking",
    },
    {
        "question": "What was the coldest game Mahomes has played in?",
        "type": "stats",
    },
    {
        "question": "Compare Josh Allen and Patrick Mahomes' 2024 playoff stats",
        "type": "comparison",
    },
    
    # Narrative questions (RAG might do better)
    {
        "question": "Tell me about the famous 13-seconds Chiefs vs Bills playoff game",
        "expected_contains": ["2021", "overtime", "Kelce", "Hill"],
        "type": "narrative",
    },
]


def run_comparison():
    print("=" * 70)
    print("Agent vs RAG Comparison")
    print("=" * 70)
    
    pipeline = NFLRAGPipeline()
    agent = NFLStatsAgent()
    
    results = []
    
    for i, test in enumerate(TEST_QUESTIONS, 1):
        question = test["question"]
        print(f"\n{'=' * 70}")
        print(f"Question {i}: {question}")
        print(f"Type: {test['type']}")
        print("=" * 70)
        
        # RAG
        print("\n--- RAG Response ---")
        start = time.time()
        rag_response = pipeline.query(question)
        rag_time = (time.time() - start) * 1000
        print(f"Answer: {rag_response.answer[:300]}...")
        print(f"Time: {rag_time:.0f}ms")
        
        # Agent
        print("\n--- Agent Response ---")
        start = time.time()
        agent_response = agent.run(question)
        agent_time = (time.time() - start) * 1000
        print(f"Answer: {agent_response.answer[:300]}...")
        print(f"Tools: {[tc['tool'] for tc in agent_response.tool_calls]}")
        print(f"Time: {agent_time:.0f}ms")
        
        results.append({
            "question": question,
            "type": test["type"],
            "rag_time_ms": rag_time,
            "agent_time_ms": agent_time,
            "rag_answer": rag_response.answer,
            "agent_answer": agent_response.answer,
        })
    
    # Summary
    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)
    
    for r in results:
        print(f"\n{r['question'][:50]}...")
        print(f"  Type: {r['type']}")
        print(f"  RAG: {r['rag_time_ms']:.0f}ms")
        print(f"  Agent: {r['agent_time_ms']:.0f}ms")
        print(f"  Faster: {'Agent' if r['agent_time_ms'] < r['rag_time_ms'] else 'RAG'}")


if __name__ == "__main__":
    run_comparison()
```

### 5.2 Run Comparison

```bash
python tests/test_agent_vs_rag.py
```

---

## Verification Checklist

After completing all phases, verify:

### Phase 1: DuckDB
- [ ] `data/nfl.duckdb` file exists
- [ ] `python -m src.data.loader --verify` shows correct row counts
- [ ] Sample query returns expected results

### Phase 2: Tools
- [ ] `python -m src.agent.tools` runs without errors
- [ ] SQL tool returns Mahomes vs Bills data
- [ ] Calculator computes win percentage correctly

### Phase 3: Agent
- [ ] `python -m src.agent.agent "Test question" -v` works
- [ ] Agent selects appropriate tools
- [ ] Final answer is coherent and cites data

### Phase 4: API
- [ ] `/agent` endpoint returns valid responses
- [ ] `/health` shows agent initialized
- [ ] Both `/query` (RAG) and `/agent` work

### Phase 5: Comparison
- [ ] Agent is more accurate for stats questions
- [ ] RAG is better for narrative questions
- [ ] Response times are reasonable

---

## Troubleshooting

### DuckDB "table not found"
```bash
# Reload data
python -m src.data.loader --force
```

### Agent tool errors
```bash
# Test tools individually
python -m src.agent.tools
```

### LLM not calling tools correctly
- Check the system prompt formatting
- Try lowering temperature (0.1-0.3)
- Ensure JSON format is exact

### Import errors
```bash
# Ensure all __init__.py files exist
touch src/data/__init__.py
touch src/agent/__init__.py
```

---

## Summary

After completing this refactor:

| Approach | Best For | Endpoint |
|----------|----------|----------|
| **Agent** | Stats, rankings, calculations, comparisons | `/agent` |
| **RAG** | Narratives, context, "tell me about" | `/query` |

The agent uses SQL for precise data retrieval and only falls back to semantic search when appropriate. This eliminates the hallucination and context fragmentation issues inherent in pure RAG for structured data.