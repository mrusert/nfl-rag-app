"""
Data loader for converting JSON NFL data to DuckDB.

Handles initial load and incremental updates from the raw JSON files
to the structured DuckDB database.
"""

import json
import math
from pathlib import Path
from typing import Optional, Any
from dataclasses import dataclass
from datetime import datetime
import argparse

import duckdb

from src.config import RAW_DATA_DIR, DATA_DIR
from .database import NFLDatabase, DUCKDB_PATH


@dataclass
class LoadResult:
    """Result from a data loading operation."""
    table_name: str
    rows_loaded: int
    duration_seconds: float
    success: bool
    error: Optional[str] = None


class NFLDataLoader:
    """
    Loads NFL JSON data into DuckDB for structured queries.

    Creates and populates tables:
    - player_games: Individual game statistics
    - player_seasons: Season aggregates
    - games: Game schedules and results
    - players: Player biographical information
    - teams: Team metadata
    """

    def __init__(self, db_path: Optional[Path] = None, raw_data_dir: Optional[Path] = None):
        """
        Initialize the data loader.

        Args:
            db_path: Path for DuckDB database file
            raw_data_dir: Directory containing raw JSON files
        """
        self.db_path = db_path or DUCKDB_PATH
        self.raw_data_dir = raw_data_dir or RAW_DATA_DIR

    def _clean_value(self, value: Any) -> Any:
        """Clean a value for database insertion (handle NaN, None, etc.)."""
        if value is None:
            return None
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            return None
        if isinstance(value, dict):
            return json.dumps(value)  # Store nested objects as JSON strings
        return value

    def _clean_row(self, row: dict) -> dict:
        """Clean all values in a row."""
        return {k: self._clean_value(v) for k, v in row.items()}

    def _load_json_file(self, filename: str) -> list[dict]:
        """Load and parse a JSON file."""
        file_path = self.raw_data_dir / filename
        if not file_path.exists():
            raise FileNotFoundError(f"Data file not found: {file_path}")

        with open(file_path, 'r') as f:
            data = json.load(f)

        return [self._clean_row(row) for row in data]

    def create_tables(self, conn: duckdb.DuckDBPyConnection):
        """Create all database tables with proper schemas."""

        # Player Games table - weekly individual statistics
        conn.execute("""
            CREATE TABLE IF NOT EXISTS player_games (
                player_id VARCHAR,
                player_name VARCHAR,
                player_display_name VARCHAR,
                position VARCHAR,
                position_group VARCHAR,
                headshot_url VARCHAR,
                season INTEGER,
                week INTEGER,
                season_type VARCHAR,
                team VARCHAR,
                opponent_team VARCHAR,

                -- Passing stats
                completions INTEGER,
                attempts INTEGER,
                passing_yards INTEGER,
                passing_tds INTEGER,
                passing_interceptions INTEGER,
                sacks_suffered INTEGER,
                sack_yards_lost INTEGER,
                passing_air_yards INTEGER,
                passing_yards_after_catch INTEGER,
                passing_first_downs INTEGER,
                passing_epa DOUBLE,
                passing_cpoe DOUBLE,
                passing_2pt_conversions INTEGER,

                -- Rushing stats
                carries INTEGER,
                rushing_yards INTEGER,
                rushing_tds INTEGER,
                rushing_fumbles INTEGER,
                rushing_fumbles_lost INTEGER,
                rushing_first_downs INTEGER,
                rushing_epa DOUBLE,
                rushing_2pt_conversions INTEGER,

                -- Receiving stats
                receptions INTEGER,
                targets INTEGER,
                receiving_yards INTEGER,
                receiving_tds INTEGER,
                receiving_fumbles INTEGER,
                receiving_fumbles_lost INTEGER,
                receiving_air_yards INTEGER,
                receiving_yards_after_catch INTEGER,
                receiving_first_downs INTEGER,
                receiving_epa DOUBLE,
                receiving_2pt_conversions INTEGER,
                target_share DOUBLE,
                air_yards_share DOUBLE,
                wopr DOUBLE,

                -- Defensive stats
                def_tackles_solo INTEGER,
                def_tackles_with_assist INTEGER,
                def_tackle_assists INTEGER,
                def_tackles_for_loss INTEGER,
                def_fumbles_forced INTEGER,
                def_sacks DOUBLE,
                def_sack_yards DOUBLE,
                def_qb_hits INTEGER,
                def_interceptions INTEGER,
                def_interception_yards INTEGER,
                def_pass_defended INTEGER,
                def_tds INTEGER,

                -- Special teams
                special_teams_tds INTEGER,
                punt_returns INTEGER,
                punt_return_yards INTEGER,
                kickoff_returns INTEGER,
                kickoff_return_yards INTEGER,

                -- Kicking
                fg_made INTEGER,
                fg_att INTEGER,
                fg_missed INTEGER,
                fg_pct DOUBLE,
                fg_long DOUBLE,

                -- Fantasy
                fantasy_points DOUBLE,
                fantasy_points_ppr DOUBLE
            )
        """)

        # Player Seasons table - aggregated season statistics
        conn.execute("""
            CREATE TABLE IF NOT EXISTS player_seasons (
                player_id VARCHAR,
                player_name VARCHAR,
                player_display_name VARCHAR,
                season INTEGER,
                position VARCHAR,
                position_group VARCHAR,

                -- Passing
                completions INTEGER,
                attempts INTEGER,
                passing_yards INTEGER,
                passing_tds INTEGER,
                passing_air_yards INTEGER,
                passing_yards_after_catch INTEGER,
                passing_first_downs INTEGER,

                -- Rushing
                carries INTEGER,
                rushing_yards INTEGER,
                rushing_tds INTEGER,
                rushing_first_downs INTEGER,

                -- Receiving
                receptions INTEGER,
                targets INTEGER,
                receiving_yards INTEGER,
                receiving_tds INTEGER,
                receiving_first_downs INTEGER,
                receiving_yards_after_catch INTEGER,

                -- Fantasy
                fantasy_points DOUBLE,
                fantasy_points_ppr DOUBLE
            )
        """)

        # Games table - schedule and results
        conn.execute("""
            CREATE TABLE IF NOT EXISTS games (
                game_id VARCHAR PRIMARY KEY,
                season INTEGER,
                game_type VARCHAR,
                week INTEGER,
                gameday DATE,
                weekday VARCHAR,
                gametime VARCHAR,

                away_team VARCHAR,
                away_score DOUBLE,
                home_team VARCHAR,
                home_score DOUBLE,

                result DOUBLE,
                total DOUBLE,
                overtime DOUBLE,

                -- Betting lines
                away_moneyline DOUBLE,
                home_moneyline DOUBLE,
                spread_line DOUBLE,
                total_line DOUBLE,

                -- Venue/conditions
                roof VARCHAR,
                surface VARCHAR,
                temp DOUBLE,
                wind DOUBLE,
                stadium VARCHAR,

                -- QBs and coaches
                away_qb_name VARCHAR,
                home_qb_name VARCHAR,
                away_coach VARCHAR,
                home_coach VARCHAR,
                referee VARCHAR,

                -- Weather JSON (stored as string)
                weather_json VARCHAR
            )
        """)

        # Players table - biographical information
        conn.execute("""
            CREATE TABLE IF NOT EXISTS players (
                gsis_id VARCHAR,
                season INTEGER,
                team VARCHAR,
                position VARCHAR,
                jersey_number VARCHAR,
                status VARCHAR,
                full_name VARCHAR,
                first_name VARCHAR,
                last_name VARCHAR,
                birth_date VARCHAR,
                height DOUBLE,
                weight DOUBLE,
                college VARCHAR,
                years_exp DOUBLE,
                headshot_url VARCHAR,
                entry_year DOUBLE,
                rookie_year DOUBLE,
                draft_club VARCHAR,
                draft_number VARCHAR,

            )
        """)

        # Teams table - team metadata
        conn.execute("""
            CREATE TABLE IF NOT EXISTS teams (
                team_abbr VARCHAR PRIMARY KEY,
                team_name VARCHAR,
                team_nick VARCHAR,
                team_conf VARCHAR,
                team_division VARCHAR,
                team_color VARCHAR,
                team_color2 VARCHAR
            )
        """)

        print("Tables created successfully.")

    def create_indexes(self, conn: duckdb.DuckDBPyConnection):
        """Create indexes for common query patterns."""
        indexes = [
            ("idx_player_games_player", "player_games", "player_display_name"),
            ("idx_player_games_team", "player_games", "team"),
            ("idx_player_games_season", "player_games", "season"),
            ("idx_player_games_season_type", "player_games", "season_type"),
            ("idx_player_games_position", "player_games", "position"),
            ("idx_player_seasons_player", "player_seasons", "player_display_name"),
            ("idx_player_seasons_season", "player_seasons", "season"),
            ("idx_games_season", "games", "season"),
            ("idx_games_teams", "games", "home_team, away_team"),
            ("idx_players_name", "players", "full_name"),
            ("idx_players_team", "players", "team"),
        ]

        for idx_name, table, columns in indexes:
            try:
                conn.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table} ({columns})")
            except Exception as e:
                print(f"Warning: Could not create index {idx_name}: {e}")

        print("Indexes created successfully.")

    def load_player_games(self, conn: duckdb.DuckDBPyConnection) -> LoadResult:
        """Load weekly player statistics."""
        start_time = datetime.now()
        table_name = "player_games"

        try:
            data = self._load_json_file("weekly_offense.json")

            # Filter out rows with missing required fields
            data = [row for row in data if row.get('player_id') and row.get('season') and row.get('week')]

            # Clear existing data
            conn.execute(f"DELETE FROM {table_name}")

            # Insert data in batches
            batch_size = 5000
            total_inserted = 0

            for i in range(0, len(data), batch_size):
                batch = data[i:i + batch_size]

                # Get columns that exist in our schema
                schema_columns = {
                    'player_id', 'player_name', 'player_display_name', 'position',
                    'position_group', 'headshot_url', 'season', 'week', 'season_type',
                    'team', 'opponent_team', 'completions', 'attempts', 'passing_yards',
                    'passing_tds', 'passing_interceptions', 'sacks_suffered',
                    'sack_yards_lost', 'passing_air_yards', 'passing_yards_after_catch',
                    'passing_first_downs', 'passing_epa', 'passing_cpoe',
                    'passing_2pt_conversions', 'carries', 'rushing_yards', 'rushing_tds',
                    'rushing_fumbles', 'rushing_fumbles_lost', 'rushing_first_downs',
                    'rushing_epa', 'rushing_2pt_conversions', 'receptions', 'targets',
                    'receiving_yards', 'receiving_tds', 'receiving_fumbles',
                    'receiving_fumbles_lost', 'receiving_air_yards',
                    'receiving_yards_after_catch', 'receiving_first_downs',
                    'receiving_epa', 'receiving_2pt_conversions', 'target_share',
                    'air_yards_share', 'wopr', 'def_tackles_solo',
                    'def_tackles_with_assist', 'def_tackle_assists',
                    'def_tackles_for_loss', 'def_fumbles_forced', 'def_sacks',
                    'def_sack_yards', 'def_qb_hits', 'def_interceptions',
                    'def_interception_yards', 'def_pass_defended', 'def_tds',
                    'special_teams_tds', 'punt_returns', 'punt_return_yards',
                    'kickoff_returns', 'kickoff_return_yards', 'fg_made', 'fg_att',
                    'fg_missed', 'fg_pct', 'fg_long', 'fantasy_points', 'fantasy_points_ppr'
                }

                # Filter to schema columns and build insert
                columns = [c for c in batch[0].keys() if c in schema_columns]
                placeholders = ', '.join(['?' for _ in columns])
                col_names = ', '.join(columns)

                for row in batch:
                    values = tuple(row.get(c) for c in columns)
                    conn.execute(
                        f"INSERT INTO {table_name} ({col_names}) VALUES ({placeholders})",
                        values
                    )

                total_inserted += len(batch)

            duration = (datetime.now() - start_time).total_seconds()
            return LoadResult(table_name, total_inserted, duration, True)

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            return LoadResult(table_name, 0, duration, False, str(e))

    def load_player_seasons(self, conn: duckdb.DuckDBPyConnection) -> LoadResult:
        """Load season aggregate statistics."""
        start_time = datetime.now()
        table_name = "player_seasons"

        try:
            data = self._load_json_file("seasonal_offense.json")

            # Filter and deduplicate by (player_id, season)
            seen = set()
            deduped = []
            for row in data:
                if not row.get('player_id') or not row.get('season'):
                    continue
                key = (row['player_id'], row['season'])
                if key not in seen:
                    seen.add(key)
                    deduped.append(row)
            data = deduped

            conn.execute(f"DELETE FROM {table_name}")

            schema_columns = {
                'player_id', 'player_name', 'player_display_name', 'season',
                'position', 'position_group', 'completions', 'attempts',
                'passing_yards', 'passing_tds', 'passing_air_yards',
                'passing_yards_after_catch', 'passing_first_downs', 'carries',
                'rushing_yards', 'rushing_tds', 'rushing_first_downs', 'receptions',
                'targets', 'receiving_yards', 'receiving_tds', 'receiving_first_downs',
                'receiving_yards_after_catch', 'fantasy_points', 'fantasy_points_ppr'
            }

            columns = [c for c in data[0].keys() if c in schema_columns]
            placeholders = ', '.join(['?' for _ in columns])
            col_names = ', '.join(columns)

            for row in data:
                values = tuple(row.get(c) for c in columns)
                conn.execute(
                    f"INSERT INTO {table_name} ({col_names}) VALUES ({placeholders})",
                    values
                )

            duration = (datetime.now() - start_time).total_seconds()
            return LoadResult(table_name, len(data), duration, True)

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            return LoadResult(table_name, 0, duration, False, str(e))

    def load_games(self, conn: duckdb.DuckDBPyConnection) -> LoadResult:
        """Load game schedule and results."""
        start_time = datetime.now()
        table_name = "games"

        try:
            data = self._load_json_file("schedules.json")

            conn.execute(f"DELETE FROM {table_name}")

            for row in data:
                # Extract weather to JSON string
                weather = row.pop('weather', None)
                weather_json = json.dumps(weather) if weather else None

                conn.execute("""
                    INSERT INTO games (
                        game_id, season, game_type, week, gameday, weekday, gametime,
                        away_team, away_score, home_team, home_score,
                        result, total, overtime,
                        away_moneyline, home_moneyline, spread_line, total_line,
                        roof, surface, temp, wind, stadium,
                        away_qb_name, home_qb_name, away_coach, home_coach, referee,
                        weather_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    row.get('game_id'), row.get('season'), row.get('game_type'),
                    row.get('week'), row.get('gameday'), row.get('weekday'),
                    row.get('gametime'), row.get('away_team'), row.get('away_score'),
                    row.get('home_team'), row.get('home_score'), row.get('result'),
                    row.get('total'), row.get('overtime'), row.get('away_moneyline'),
                    row.get('home_moneyline'), row.get('spread_line'),
                    row.get('total_line'), row.get('roof'), row.get('surface'),
                    row.get('temp'), row.get('wind'), row.get('stadium'),
                    row.get('away_qb_name'), row.get('home_qb_name'),
                    row.get('away_coach'), row.get('home_coach'), row.get('referee'),
                    weather_json
                ))

            duration = (datetime.now() - start_time).total_seconds()
            return LoadResult(table_name, len(data), duration, True)

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            return LoadResult(table_name, 0, duration, False, str(e))

    def load_players(self, conn: duckdb.DuckDBPyConnection) -> LoadResult:
        """Load player biographical data."""
        start_time = datetime.now()
        table_name = "players"

        try:
            data = self._load_json_file("rosters.json")

            # Filter and deduplicate by (gsis_id, season)
            seen = set()
            deduped = []
            for row in data:
                if not row.get('gsis_id') or not row.get('season'):
                    continue
                key = (row['gsis_id'], row['season'])
                if key not in seen:
                    seen.add(key)
                    deduped.append(row)
            data = deduped

            conn.execute(f"DELETE FROM {table_name}")

            for row in data:
                conn.execute("""
                    INSERT INTO players (
                        gsis_id, season, team, position, jersey_number, status,
                        full_name, first_name, last_name, birth_date,
                        height, weight, college, years_exp, headshot_url,
                        entry_year, rookie_year, draft_club, draft_number
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    row.get('gsis_id'), row.get('season'), row.get('team'),
                    row.get('position'), row.get('jersey_number'), row.get('status'),
                    row.get('full_name'), row.get('first_name'), row.get('last_name'),
                    row.get('birth_date'), row.get('height'), row.get('weight'),
                    row.get('college'), row.get('years_exp'), row.get('headshot_url'),
                    row.get('entry_year'), row.get('rookie_year'),
                    row.get('draft_club'), row.get('draft_number')
                ))

            duration = (datetime.now() - start_time).total_seconds()
            return LoadResult(table_name, len(data), duration, True)

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            return LoadResult(table_name, 0, duration, False, str(e))

    def load_teams(self, conn: duckdb.DuckDBPyConnection) -> LoadResult:
        """Load team metadata."""
        start_time = datetime.now()
        table_name = "teams"

        try:
            data = self._load_json_file("teams.json")

            conn.execute(f"DELETE FROM {table_name}")

            for row in data:
                conn.execute("""
                    INSERT INTO teams (
                        team_abbr, team_name, team_nick, team_conf,
                        team_division, team_color, team_color2
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    row.get('team_abbr'), row.get('team_name'), row.get('team_nick'),
                    row.get('team_conf'), row.get('team_division'),
                    row.get('team_color'), row.get('team_color2')
                ))

            duration = (datetime.now() - start_time).total_seconds()
            return LoadResult(table_name, len(data), duration, True)

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            return LoadResult(table_name, 0, duration, False, str(e))

    def load_all(self, force: bool = False) -> dict[str, LoadResult]:
        """
        Load all data into DuckDB.

        Args:
            force: If True, delete and recreate the database

        Returns:
            Dictionary of table names to LoadResult
        """
        if force and self.db_path.exists():
            self.db_path.unlink()
            print(f"Deleted existing database: {self.db_path}")

        # Ensure data directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Connect with write access for loading
        conn = duckdb.connect(str(self.db_path))

        print(f"Loading data into: {self.db_path}")
        print("-" * 50)

        # Create tables
        self.create_tables(conn)

        # Load each table
        results = {}

        loaders = [
            ("player_games", self.load_player_games),
            ("player_seasons", self.load_player_seasons),
            ("games", self.load_games),
            ("players", self.load_players),
            ("teams", self.load_teams),
        ]

        for name, loader_func in loaders:
            print(f"Loading {name}...", end=" ", flush=True)
            result = loader_func(conn)
            results[name] = result

            if result.success:
                print(f"{result.rows_loaded:,} rows ({result.duration_seconds:.2f}s)")
            else:
                print(f"FAILED: {result.error}")

        # Create indexes
        print("-" * 50)
        self.create_indexes(conn)

        conn.close()

        return results

    def verify(self) -> bool:
        """Verify database integrity and print statistics."""
        print(f"\nVerifying database: {self.db_path}")
        print("=" * 50)

        if not self.db_path.exists():
            print("ERROR: Database file does not exist!")
            print("Run: python -m src.data.loader")
            return False

        db = NFLDatabase(self.db_path)
        health = db.health_check()

        if health['status'] != 'healthy':
            print(f"ERROR: {health.get('error', 'Unknown error')}")
            return False

        expected_counts = {
            'player_games': 200000,  # ~217K expected
            'player_seasons': 10000,  # ~15K expected
            'games': 3000,            # ~3.3K expected
            'players': 50000,         # ~70K expected
            'teams': 30,              # 32 expected
        }

        all_good = True
        for table, count in health['tables'].items():
            expected = expected_counts.get(table, 0)
            status = "OK" if count >= expected else "LOW"
            if status == "LOW":
                all_good = False
            print(f"{table}: {count:,} rows [{status}]")

        # Sample queries to verify data quality
        print("\nSample queries:")

        # Check seasons range
        result = db.execute_safe(
            "SELECT MIN(season), MAX(season) FROM player_games"
        )
        if result.rows:
            min_season, max_season = result.rows[0]
            print(f"  Seasons: {min_season} - {max_season}")

        # Check top passer for recent season
        result = db.execute_safe("""
            SELECT player_display_name, SUM(passing_yards) as yards
            FROM player_games
            WHERE season = 2024 AND season_type = 'REG'
            GROUP BY player_display_name
            ORDER BY yards DESC
            LIMIT 1
        """)
        if result.rows:
            name, yards = result.rows[0]
            print(f"  2024 passing leader: {name} ({int(yards):,} yards)")

        db.close()

        print("=" * 50)
        print(f"Verification: {'PASSED' if all_good else 'WARNINGS'}")

        return all_good


def incremental_update(loader: NFLDataLoader, table: str) -> LoadResult:
    """
    Perform incremental update for a specific table.

    This is a placeholder for future incremental loading logic.
    Currently just reloads the entire table.
    """
    conn = duckdb.connect(str(loader.db_path))

    loaders = {
        "player_games": loader.load_player_games,
        "player_seasons": loader.load_player_seasons,
        "games": loader.load_games,
        "players": loader.load_players,
        "teams": loader.load_teams,
    }

    if table not in loaders:
        return LoadResult(table, 0, 0, False, f"Unknown table: {table}")

    result = loaders[table](conn)
    conn.close()

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load NFL data into DuckDB")
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify existing database instead of loading"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force reload by deleting existing database"
    )

    args = parser.parse_args()

    loader = NFLDataLoader()

    if args.verify:
        success = loader.verify()
        exit(0 if success else 1)
    else:
        results = loader.load_all(force=args.force)

        # Summary
        print("\n" + "=" * 50)
        print("LOAD SUMMARY")
        print("=" * 50)

        total_rows = sum(r.rows_loaded for r in results.values())
        total_time = sum(r.duration_seconds for r in results.values())
        failures = [name for name, r in results.items() if not r.success]

        print(f"Total rows loaded: {total_rows:,}")
        print(f"Total time: {total_time:.2f}s")

        if failures:
            print(f"FAILURES: {', '.join(failures)}")
            exit(1)
        else:
            print("All tables loaded successfully!")
            print("\nRun verification: python -m src.data.loader --verify")
