"""
Data Updater - Incremental data updates for NFL stats.

Handles:
- Fetching new NFL data (latest games, updated stats)
- Updating DuckDB with new records
- Optionally updating ChromaDB embeddings
- Tracking update history

Usage:
    python -m src.data.updater --check      # Check for updates
    python -m src.data.updater --update     # Perform update
    python -m src.data.updater --current    # Update current season only
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, asdict

from src.config import RAW_DATA_DIR, DATA_DIR
from src.data.database import NFLDatabase, get_shared_database
from src.data.loader import NFLDataLoader


UPDATE_LOG_FILE = DATA_DIR / "update_log.json"


@dataclass
class UpdateResult:
    """Result of an update operation."""
    success: bool
    timestamp: str
    tables_updated: dict  # table_name -> rows_added
    errors: list
    duration_seconds: float


class NFLDataUpdater:
    """
    Handles incremental data updates for NFL statistics.

    Can update:
    - Current season data (as games happen)
    - Full historical data refresh
    """

    def __init__(self):
        self.db_loader = NFLDataLoader()
        # Use lazy property for database to avoid connection conflicts
        # Read operations use the shared read-only database
        # Write operations open their own connection when needed
        self._db = None
        self.update_log = self._load_update_log()

    @property
    def db(self) -> NFLDatabase:
        """Get shared read-only database for query operations."""
        if self._db is None:
            self._db = get_shared_database()
        return self._db

    def _load_update_log(self) -> list:
        """Load update history."""
        if UPDATE_LOG_FILE.exists():
            with open(UPDATE_LOG_FILE, "r") as f:
                return json.load(f)
        return []

    def _save_update_log(self, result: UpdateResult):
        """Save update result to log."""
        self.update_log.append(asdict(result))
        # Keep last 100 updates
        self.update_log = self.update_log[-100:]
        with open(UPDATE_LOG_FILE, "w") as f:
            json.dump(self.update_log, f, indent=2)

    def get_current_data_info(self) -> dict:
        """Get info about current data in database."""
        info = {}

        # Get season range
        result = self.db.execute_safe(
            "SELECT MIN(season), MAX(season) FROM player_games"
        )
        if result.rows:
            info["seasons"] = {"min": result.rows[0][0], "max": result.rows[0][1]}

        # Get latest week in current season
        result = self.db.execute_safe("""
            SELECT MAX(week) FROM player_games
            WHERE season = (SELECT MAX(season) FROM player_games)
        """)
        if result.rows:
            info["latest_week"] = result.rows[0][0]

        # Get record counts
        for table in ["player_games", "player_seasons", "games", "players"]:
            result = self.db.execute_safe(f"SELECT COUNT(*) FROM {table}")
            info[f"{table}_count"] = result.rows[0][0] if result.rows else 0

        # Get last update time
        if self.update_log:
            info["last_update"] = self.update_log[-1]["timestamp"]
        else:
            info["last_update"] = "Never"

        return info

    def check_for_updates(self) -> dict:
        """
        Check if new data is available.

        Returns dict with:
        - needs_update: bool
        - current_week: int (in DB)
        - available_week: int (from API)
        - message: str
        """
        from src.ingestion.scraper import NFLDataLoader as Scraper

        current_info = self.get_current_data_info()
        current_season = current_info["seasons"]["max"]
        current_week = current_info["latest_week"]

        # Check what's available from nflverse
        try:
            scraper = Scraper()
            latest_schedules = scraper.load_schedules([current_season])

            # Find latest completed game
            completed = latest_schedules[latest_schedules['away_score'].notna()]
            if len(completed) > 0:
                available_week = int(completed['week'].max())
            else:
                available_week = 0

            needs_update = available_week > current_week

            return {
                "needs_update": needs_update,
                "current_season": current_season,
                "current_week": current_week,
                "available_week": available_week,
                "message": f"Week {available_week} available, you have week {current_week}" if needs_update else "Data is up to date",
            }
        except Exception as e:
            return {
                "needs_update": False,
                "error": str(e),
                "message": f"Could not check for updates: {e}",
            }

    def update_current_season(self) -> UpdateResult:
        """
        Update data for the current season only.

        This is faster than a full refresh and suitable for
        weekly updates during the season.
        """
        start_time = datetime.now()
        errors = []
        tables_updated = {}

        try:
            from src.ingestion.scraper import NFLDataLoader as Scraper
            import duckdb

            current_info = self.get_current_data_info()
            current_season = current_info["seasons"]["max"]

            print(f"Updating data for {current_season} season...")

            # Fetch fresh data for current season
            scraper = Scraper()

            # Get connection for direct writes
            conn = duckdb.connect(str(self.db.db_path))

            # Update player_games
            print("  Fetching player stats...")
            weekly_df = scraper.load_weekly_stats([current_season])

            # Delete existing current season data and replace
            conn.execute(f"DELETE FROM player_games WHERE season = {current_season}")

            # Insert new data
            # Convert to records and insert
            records = weekly_df.to_dict(orient="records")
            inserted = 0
            for record in records:
                if not record.get('player_id'):
                    continue
                try:
                    # Build insert dynamically based on available columns
                    cols = [k for k in record.keys() if k in self._get_player_games_columns()]
                    vals = [record.get(c) for c in cols]
                    placeholders = ", ".join(["?" for _ in cols])
                    col_names = ", ".join(cols)

                    conn.execute(
                        f"INSERT INTO player_games ({col_names}) VALUES ({placeholders})",
                        vals
                    )
                    inserted += 1
                except Exception as e:
                    if "duplicate" not in str(e).lower():
                        errors.append(f"Insert error: {e}")

            tables_updated["player_games"] = inserted
            print(f"    Updated {inserted} player game records")

            # Update schedules/games
            print("  Fetching schedules...")
            schedules_df = scraper.load_schedules([current_season])

            conn.execute(f"DELETE FROM games WHERE season = {current_season}")

            games_inserted = 0
            for _, row in schedules_df.iterrows():
                try:
                    conn.execute("""
                        INSERT INTO games (game_id, season, game_type, week, gameday,
                                          away_team, away_score, home_team, home_score,
                                          result, total, stadium, temp, wind)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        row.get('game_id'), row.get('season'), row.get('game_type'),
                        row.get('week'), row.get('gameday'),
                        row.get('away_team'), row.get('away_score'),
                        row.get('home_team'), row.get('home_score'),
                        row.get('result'), row.get('total'),
                        row.get('stadium'), row.get('temp'), row.get('wind')
                    ))
                    games_inserted += 1
                except Exception as e:
                    if "duplicate" not in str(e).lower():
                        errors.append(f"Game insert error: {e}")

            tables_updated["games"] = games_inserted
            print(f"    Updated {games_inserted} games")

            conn.close()

            duration = (datetime.now() - start_time).total_seconds()

            result = UpdateResult(
                success=len(errors) == 0,
                timestamp=datetime.now().isoformat(),
                tables_updated=tables_updated,
                errors=errors,
                duration_seconds=duration,
            )

            self._save_update_log(result)
            return result

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            return UpdateResult(
                success=False,
                timestamp=datetime.now().isoformat(),
                tables_updated=tables_updated,
                errors=[str(e)],
                duration_seconds=duration,
            )

    def _get_player_games_columns(self) -> set:
        """Get valid columns for player_games table."""
        return {
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
            'air_yards_share', 'wopr', 'fantasy_points', 'fantasy_points_ppr'
        }

    def full_refresh(self, years: Optional[list[int]] = None) -> UpdateResult:
        """
        Full data refresh - reload all data from scratch.

        Args:
            years: Specific years to load (default: 2014-current)
        """
        start_time = datetime.now()

        if years is None:
            current_year = datetime.now().year
            years = list(range(2014, current_year + 1))

        print(f"Full refresh for years: {min(years)}-{max(years)}")
        print("This may take several minutes...")

        try:
            # Use the existing loader
            loader = NFLDataLoader()
            results = loader.load_all(force=True)

            tables_updated = {
                name: r.rows_loaded for name, r in results.items()
            }
            errors = [
                f"{name}: {r.error}" for name, r in results.items()
                if not r.success
            ]

            duration = (datetime.now() - start_time).total_seconds()

            result = UpdateResult(
                success=len(errors) == 0,
                timestamp=datetime.now().isoformat(),
                tables_updated=tables_updated,
                errors=errors,
                duration_seconds=duration,
            )

            self._save_update_log(result)
            return result

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            return UpdateResult(
                success=False,
                timestamp=datetime.now().isoformat(),
                tables_updated={},
                errors=[str(e)],
                duration_seconds=duration,
            )

    def get_update_history(self, limit: int = 10) -> list:
        """Get recent update history."""
        return self.update_log[-limit:]


# CLI
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="NFL Data Updater")
    parser.add_argument("--check", action="store_true", help="Check for available updates")
    parser.add_argument("--update", action="store_true", help="Update current season data")
    parser.add_argument("--full", action="store_true", help="Full data refresh")
    parser.add_argument("--info", action="store_true", help="Show current data info")
    parser.add_argument("--history", action="store_true", help="Show update history")

    args = parser.parse_args()

    updater = NFLDataUpdater()

    if args.info:
        info = updater.get_current_data_info()
        print("Current Data Info")
        print("=" * 40)
        for key, value in info.items():
            print(f"  {key}: {value}")

    elif args.check:
        print("Checking for updates...")
        result = updater.check_for_updates()
        print("=" * 40)
        for key, value in result.items():
            print(f"  {key}: {value}")

    elif args.update:
        print("Updating current season...")
        result = updater.update_current_season()
        print("=" * 40)
        print(f"Success: {result.success}")
        print(f"Duration: {result.duration_seconds:.1f}s")
        print(f"Tables updated: {result.tables_updated}")
        if result.errors:
            print(f"Errors: {result.errors}")

    elif args.full:
        print("Starting full refresh...")
        result = updater.full_refresh()
        print("=" * 40)
        print(f"Success: {result.success}")
        print(f"Duration: {result.duration_seconds:.1f}s")
        print(f"Tables updated: {result.tables_updated}")
        if result.errors:
            print(f"Errors: {result.errors}")

    elif args.history:
        history = updater.get_update_history()
        print("Update History")
        print("=" * 40)
        for entry in history:
            print(f"\n{entry['timestamp']}")
            print(f"  Success: {entry['success']}")
            print(f"  Duration: {entry['duration_seconds']:.1f}s")
            print(f"  Tables: {entry['tables_updated']}")

    else:
        parser.print_help()
