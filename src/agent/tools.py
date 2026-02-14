"""
Agent Tools for NFL Stats queries.

Each tool has:
- name: Identifier for the agent to reference
- description: What the tool does (used by LLM to decide when to use it)
- execute(): Run the tool with given arguments

Tools available:
- sql_query: Execute SQL queries against the NFL database
- player_stats: Quick lookup for player statistics
- calculator: Perform mathematical calculations
- semantic_search: Search for narrative/contextual information
- rankings: Get player rankings for specific stats
"""

from typing import Any, Optional
from dataclasses import dataclass
import json

from src.data.database import get_shared_database


@dataclass
class ToolResult:
    """Result from a tool execution."""
    success: bool
    data: Any
    error: Optional[str] = None

    def to_string(self, max_rows: int = 15) -> str:
        """Format result for LLM context."""
        if not self.success:
            return f"Error: {self.error}"

        if isinstance(self.data, list):
            if len(self.data) == 0:
                return "No results found."
            # Format as readable JSON
            if len(self.data) <= max_rows:
                return json.dumps(self.data, indent=2, default=str)
            else:
                truncated = json.dumps(self.data[:max_rows], indent=2, default=str)
                return truncated + f"\n... and {len(self.data) - max_rows} more rows"

        if isinstance(self.data, dict):
            return json.dumps(self.data, indent=2, default=str)

        return str(self.data)


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
- player_games: Individual player stats per game
  Columns: player_id, player_name, player_display_name, position, season, week, season_type, team, opponent_team,
           passing_yards, passing_tds, passing_interceptions, completions, attempts,
           rushing_yards, rushing_tds, carries,
           receiving_yards, receiving_tds, receptions, targets,
           fantasy_points, fantasy_points_ppr

- player_seasons: Season totals per player
  Columns: player_id, player_display_name, season, position, passing_yards, passing_tds, rushing_yards, rushing_tds, receiving_yards, receiving_tds

- games: Game schedules and results
  Columns: game_id, season, game_type, week, gameday, home_team, away_team, home_score, away_score, temp, wind, stadium

- players: Player biographical info
  Columns: gsis_id, season, team, position, full_name, height, weight, college

- teams: Team metadata
  Columns: team_abbr, team_name, team_nick, team_conf, team_division

season_type values: 'REG' (regular season), 'POST' (playoffs)
game_type values: 'REG', 'WC' (wild card), 'DIV' (divisional), 'CON' (conference), 'SB' (super bowl)

Example queries:
- "SELECT * FROM player_games WHERE player_display_name ILIKE '%Mahomes%' AND opponent_team = 'BUF'"
- "SELECT player_display_name, SUM(passing_yards) as total FROM player_games WHERE season = 2024 GROUP BY player_display_name ORDER BY total DESC LIMIT 10"
"""

    def __init__(self):
        # Use shared database to avoid DuckDB lock conflicts
        self.db = get_shared_database()

    def execute(self, sql: str) -> ToolResult:
        """Execute a SQL query."""
        try:
            result = self.db.execute_safe(sql)

            if result.row_count == 0:
                return ToolResult(success=True, data=[])

            # Convert to list of dicts for easier LLM consumption
            return ToolResult(success=True, data=result.to_dicts())

        except PermissionError as e:
            return ToolResult(success=False, data=None, error=str(e))
        except Exception as e:
            return ToolResult(success=False, data=None, error=f"Query failed: {str(e)}")


class PlayerStatsLookupTool:
    """
    Quick lookup for player statistics with common filters.

    Use this tool for simple player stat queries without writing SQL.
    Easier than SQL for basic "how did player X do" questions.
    """

    name = "player_stats"
    description = """Look up stats for a specific player.

Arguments:
- player_name (required): Player name (partial match supported), e.g., "Patrick Mahomes" or "Mahomes"
- opponent (optional): Team abbreviation to filter by opponent, e.g., "BUF", "KC", "SF"
- season (optional): Year to filter by, e.g., 2024
- season_type (optional): 'REG' for regular season, 'POST' for playoffs

Returns game-by-game stats and a summary with totals/averages.

Example: player_stats("Mahomes", opponent="BUF", season_type="POST")
"""

    def __init__(self):
        # Use shared database to avoid DuckDB lock conflicts
        self.db = get_shared_database()

    def execute(
        self,
        player_name: str,
        opponent: Optional[str] = None,
        season: Optional[int] = None,
        season_type: Optional[str] = None,
    ) -> ToolResult:
        """Get player stats summary."""
        try:
            # Build query conditions
            conditions = ["player_display_name ILIKE ?"]
            params = [f"%{player_name}%"]

            if opponent:
                conditions.append("opponent_team = ?")
                params.append(opponent.upper())

            if season:
                conditions.append("season = ?")
                params.append(season)

            if season_type:
                conditions.append("season_type = ?")
                params.append(season_type.upper())

            where_clause = " AND ".join(conditions)

            # Get individual games
            games_sql = f"""
                SELECT season, week, season_type, team, opponent_team,
                       passing_yards, passing_tds, passing_interceptions,
                       rushing_yards, rushing_tds,
                       receiving_yards, receiving_tds
                FROM player_games
                WHERE {where_clause}
                ORDER BY season DESC, week DESC
                LIMIT 30
            """
            games_result = self.db.execute_safe(games_sql, tuple(params))

            # Get summary stats
            summary_sql = f"""
                SELECT
                    COUNT(*) as games_played,
                    SUM(CASE WHEN passing_yards > 0 OR rushing_yards > 0 THEN 1 ELSE 0 END) as games_with_stats,
                    ROUND(AVG(passing_yards), 1) as avg_passing_yards,
                    SUM(passing_yards) as total_passing_yards,
                    SUM(passing_tds) as total_passing_tds,
                    SUM(passing_interceptions) as total_interceptions,
                    ROUND(AVG(rushing_yards), 1) as avg_rushing_yards,
                    SUM(rushing_yards) as total_rushing_yards,
                    SUM(rushing_tds) as total_rushing_tds,
                    ROUND(AVG(receiving_yards), 1) as avg_receiving_yards,
                    SUM(receiving_yards) as total_receiving_yards,
                    SUM(receiving_tds) as total_receiving_tds
                FROM player_games
                WHERE {where_clause}
            """
            summary_result = self.db.execute_safe(summary_sql, tuple(params))

            return ToolResult(
                success=True,
                data={
                    "summary": summary_result.to_dicts()[0] if summary_result.rows else {},
                    "recent_games": games_result.to_dicts(),
                    "total_games_found": games_result.row_count,
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

Supported operations:
- average: Calculate mean of a list of numbers
- sum: Add up numbers
- min/max: Find minimum or maximum
- win_percentage: Calculate win % from {"wins": X, "losses": Y}
- percent_change: Calculate % change from {"old": X, "new": Y}
- divide: Divide first number by second
- expression: Evaluate a math expression

Examples:
- calculator("average", [280, 310, 295, 340])
- calculator("win_percentage", {"wins": 8, "losses": 2})
- calculator("percent_change", {"old": 4000, "new": 4500})
- calculator("expression", "324 / 18")
"""

    name = "calculator"

    def execute(self, operation: str, values: Any) -> ToolResult:
        """Perform a calculation."""
        try:
            result = None

            if operation == "average":
                if not values:
                    return ToolResult(success=False, data=None, error="No values provided")
                result = sum(values) / len(values)

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
                if old == 0:
                    return ToolResult(success=False, data=None, error="Cannot calculate percent change from 0")
                result = round((new - old) / old * 100, 1)

            elif operation == "divide":
                if len(values) != 2:
                    return ToolResult(success=False, data=None, error="Divide requires exactly 2 values")
                if values[1] == 0:
                    return ToolResult(success=False, data=None, error="Cannot divide by zero")
                result = values[0] / values[1]

            elif operation == "expression":
                # Safe evaluation of math expressions
                allowed_names = {"abs": abs, "round": round, "min": min, "max": max}
                result = eval(str(values), {"__builtins__": {}}, allowed_names)

            else:
                return ToolResult(success=False, data=None, error=f"Unknown operation: {operation}")

            return ToolResult(
                success=True,
                data={"result": round(result, 2) if isinstance(result, float) else result, "operation": operation}
            )

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
    description = """Search for relevant information using semantic similarity (RAG).

Best for narrative/contextual questions like:
- "Tell me about the famous Chiefs-Bills playoff game"
- "What happened in the freezing cold playoff game?"
- "Describe Mahomes' best performance"

NOT recommended for:
- Precise statistics (use sql_query or player_stats)
- Rankings or comparisons (use sql_query or rankings)
- Calculations (use calculator)

Arguments:
- query: Natural language search query
- num_results: Number of results to return (default 5)
"""

    def __init__(self):
        # Lazy load to avoid circular imports and slow startup
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
    ) -> ToolResult:
        """Perform semantic search."""
        try:
            results = self.pipeline.retrieve(
                query=query,
                num_results=num_results,
            )

            formatted = []
            for r in results:
                formatted.append({
                    "text": r.text,
                    "score": round(r.score, 3) if hasattr(r, 'score') else None,
                    "metadata": r.metadata if hasattr(r, 'metadata') else {},
                })

            return ToolResult(success=True, data=formatted)

        except Exception as e:
            return ToolResult(success=False, data=None, error=str(e))


class RankingsTool:
    """
    Get player rankings for various statistics.

    Supports both "best" (highest) and "worst" (lowest) rankings.
    Use this tool for "who led the league" or "worst performing" questions.
    """

    name = "rankings"
    description = """Get players ranked by a statistic (best or worst).

Arguments:
- stat: Statistic to rank by. Options:
  - passing_yards, passing_tds, passing_interceptions
  - rushing_yards, rushing_tds, carries
  - receiving_yards, receiving_tds, receptions, targets
  - fg_made, fg_att, fg_long (kicker stats)
  - fantasy_points, fantasy_points_ppr
- season: Year to rank (required), e.g., 2024
- position: Filter by position (optional): 'QB', 'RB', 'WR', 'TE', 'K' (kicker)
- limit: Number of players to return (default 10)
- season_type: 'REG' for regular season, 'POST' for playoffs (default 'REG')
- order: 'desc' for best/highest (default), 'asc' for worst/lowest
- min_games: Minimum games played to qualify (default 1, use higher like 10 for "worst" queries)

Examples:
- Best: rankings("passing_yards", 2024, position="QB", limit=10)
- Worst: rankings("passing_yards", 2024, position="QB", limit=10, order="asc", min_games=10)
- Kickers: rankings("fg_made", 2024, position="K", limit=10)
"""

    def __init__(self):
        # Use shared database to avoid DuckDB lock conflicts
        self.db = get_shared_database()

    def execute(
        self,
        stat: str,
        season: int,
        position: Optional[str] = None,
        limit: int = 10,
        season_type: str = "REG",
        order: str = "desc",
        min_games: int = 1,
    ) -> ToolResult:
        """Get rankings for a stat."""
        try:
            # Validate stat column to prevent SQL injection
            valid_stats = {
                'passing_yards', 'passing_tds', 'passing_interceptions',
                'rushing_yards', 'rushing_tds', 'carries',
                'receiving_yards', 'receiving_tds', 'receptions', 'targets',
                'fantasy_points', 'fantasy_points_ppr',
                # Kicker stats
                'fg_made', 'fg_att', 'fg_long',
            }

            if stat not in valid_stats:
                return ToolResult(
                    success=False,
                    data=None,
                    error=f"Invalid stat: {stat}. Valid options: {', '.join(sorted(valid_stats))}"
                )

            # Validate order direction
            order = order.lower()
            if order not in ('asc', 'desc'):
                order = 'desc'

            conditions = ["season = ?", "season_type = ?"]
            params = [season, season_type.upper()]

            if position:
                conditions.append("position = ?")
                params.append(position.upper())

            where_clause = " AND ".join(conditions)

            # For "worst" queries, require minimum stat value > 0 to exclude players with no attempts
            # For passing/rushing, this ensures the player actually played the position
            having_clause = f"COUNT(*) >= {min_games}"
            if order == "asc":
                # For worst queries, also require they have some stats (not just 0)
                having_clause += f" AND SUM({stat}) > 0"
            else:
                having_clause += f" AND SUM({stat}) > 0"

            sql = f"""
                SELECT
                    player_display_name as player,
                    position,
                    team,
                    SUM({stat}) as total_{stat},
                    COUNT(*) as games
                FROM player_games
                WHERE {where_clause}
                GROUP BY player_display_name, position, team
                HAVING {having_clause}
                ORDER BY total_{stat} {order.upper()}
                LIMIT ?
            """
            params.append(limit)

            result = self.db.execute_safe(sql, tuple(params))

            # Add rank numbers
            ranked = []
            rank_label = "rank" if order == "desc" else "worst_rank"
            for i, row in enumerate(result.to_dicts(), 1):
                row[rank_label] = i
                ranked.append(row)

            return ToolResult(success=True, data=ranked)

        except Exception as e:
            return ToolResult(success=False, data=None, error=str(e))


class NewsSearchTool:
    """
    Search NFL news and opinions.

    Use this tool for:
    - Recent news about players, teams, or events
    - Opinions and analysis
    - Trade rumors and speculation
    - Injury reports and updates
    """

    name = "news_search"
    description = """Search NFL news and opinions from ESPN, NFL.com, and Reddit.

Best for:
- Recent news and updates
- Trade rumors and speculation
- Injury reports
- Expert opinions and analysis
- Fan discussions and reactions

Arguments:
- query: What to search for (e.g., "Mahomes injury", "Chiefs trade rumors")
- source (optional): Filter by source - "espn", "nfl.com", "reddit"
- team (optional): Filter by team abbreviation (e.g., "KC", "BUF")
- num_results (optional): Number of results (default 5)

NOT for precise statistics (use sql_query or player_stats instead).
"""

    def __init__(self, storage=None):
        self._storage = storage

    @property
    def storage(self):
        if self._storage is None:
            from src.news.storage import NewsStorage
            self._storage = NewsStorage()
        return self._storage

    def execute(
        self,
        query: str,
        source: Optional[str] = None,
        team: Optional[str] = None,
        num_results: int = 5,
    ) -> ToolResult:
        """Search news."""
        try:
            results = self.storage.search(
                query=query,
                n_results=num_results,
                source=source,
                team=team,
            )

            if not results:
                return ToolResult(
                    success=True,
                    data={"message": "No news found. Try fetching news first with: python -m src.news.storage --fetch"}
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
        NewsSearchTool(),
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
    print("\n1. SQL Query Tool - Mahomes 2024 season:")
    sql_tool = SQLQueryTool()
    result = sql_tool.execute(
        "SELECT season, COUNT(*) as games, SUM(passing_tds) as tds, SUM(passing_yards) as yards "
        "FROM player_games WHERE player_display_name ILIKE '%Mahomes%' AND season = 2024 "
        "GROUP BY season"
    )
    print(result.to_string())

    # Test Player Stats
    print("\n2. Player Stats Tool - Mahomes vs Bills in playoffs:")
    stats_tool = PlayerStatsLookupTool()
    result = stats_tool.execute("Mahomes", opponent="BUF", season_type="POST")
    if result.success:
        print(f"Summary: {json.dumps(result.data.get('summary'), indent=2)}")
        print(f"Games found: {result.data.get('total_games_found')}")
    else:
        print(f"Error: {result.error}")

    # Test Calculator
    print("\n3. Calculator Tool - Win percentage:")
    calc_tool = CalculatorTool()
    result = calc_tool.execute("win_percentage", {"wins": 4, "losses": 0})
    print(result.to_string())

    # Test Rankings
    print("\n4. Rankings Tool - Top 5 QBs by passing yards in 2024:")
    rank_tool = RankingsTool()
    result = rank_tool.execute("passing_yards", 2024, position="QB", limit=5)
    print(result.to_string())

    print("\n" + "=" * 60)
    print("Tool tests complete!")
