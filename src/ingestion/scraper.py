"""
NFL Data Loader using nflreadpy.

This module provides functions to download and process NFL statistics
from the nflverse project (https://github.com/nflverse), with optional
weather data enrichment for outdoor games.

Note: This uses nflreadpy (the replacement for the deprecated nfl_data_py).
nflreadpy uses Polars internally but we convert to pandas for compatibility.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Optional

import pandas as pd

# Import nflreadpy (replacement for deprecated nfl_data_py)
try:
    import nflreadpy as nfl
    NFLREADPY_AVAILABLE = True
except ImportError:
    NFLREADPY_AVAILABLE = False
    print("Warning: nflreadpy not installed. Install with: pip install nflreadpy")

from src.config import RAW_DATA_DIR, DEBUG
from src.ingestion.stadiums import get_stadium_coordinates, get_stadium, find_stadium_by_team
from src.ingestion.weather import WeatherFetcher, GameWeather


def polars_to_pandas(df):
    """Convert Polars DataFrame to Pandas DataFrame if needed."""
    if hasattr(df, 'to_pandas'):
        return df.to_pandas()
    return df


class NFLDataLoader:
    """
    Loader for NFL data from nflverse.
    
    Features:
    - Downloads seasonal player statistics
    - Downloads weekly player statistics
    - Downloads roster information
    - Downloads team schedules and results
    - Enriches schedules with weather data for outdoor games
    - Caches data locally to avoid re-downloading
    """
    
    def __init__(self, cache_dir: Optional[Path] = None):
        """
        Initialize the data loader.
        
        Args:
            cache_dir: Directory to store downloaded data
        """
        if not NFLREADPY_AVAILABLE:
            raise ImportError(
                "nflreadpy is required but not installed. "
                "Install with: pip install nflreadpy"
            )
        
        self.cache_dir = cache_dir or RAW_DATA_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.weather_fetcher = WeatherFetcher()
    
    def load_player_stats(self, years: list[int], stat_type: str = "offense") -> pd.DataFrame:
        """
        Load player statistics (weekly, aggregatable to seasonal).
        
        Args:
            years: List of seasons to load (e.g., [2020, 2021, 2022, 2023])
            stat_type: Type of stats - "offense" or "defense"
            
        Returns:
            DataFrame with player statistics
        """
        if DEBUG:
            print(f"Loading {stat_type} player stats for {years}...")
        
        if stat_type == "offense":
            df = nfl.load_player_stats(years)
        else:
            df = nfl.load_player_stats(years, stat_type="defense")
        
        # Convert from Polars to Pandas
        df = polars_to_pandas(df)
        
        if DEBUG:
            print(f"  Loaded {len(df)} player stat records")
        
        return df
    
    def load_seasonal_stats(self, years: list[int]) -> pd.DataFrame:
        """
        Load seasonal player statistics (aggregated from weekly).
        
        Args:
            years: List of seasons to load
            
        Returns:
            DataFrame with seasonal player statistics
        """
        if DEBUG:
            print(f"Loading seasonal stats for {years}...")
        
        # Load weekly stats and aggregate to seasonal
        weekly = self.load_player_stats(years, "offense")
        
        # Group by player and season to create seasonal totals
        # Key columns to sum
        sum_cols = [
            'completions', 'attempts', 'passing_yards', 'passing_tds', 
            'interceptions', 'sacks', 'sack_yards', 'passing_air_yards',
            'passing_yards_after_catch', 'passing_first_downs',
            'carries', 'rushing_yards', 'rushing_tds', 'rushing_first_downs',
            'receptions', 'targets', 'receiving_yards', 'receiving_tds',
            'receiving_first_downs', 'receiving_yards_after_catch',
            'fantasy_points', 'fantasy_points_ppr'
        ]
        
        # Only include columns that exist
        available_sum_cols = [c for c in sum_cols if c in weekly.columns]
        
        # Group columns
        group_cols = ['player_id', 'player_name', 'player_display_name', 'season', 'position', 'position_group']
        available_group_cols = [c for c in group_cols if c in weekly.columns]
        
        if available_group_cols and available_sum_cols:
            seasonal = weekly.groupby(available_group_cols, as_index=False)[available_sum_cols].sum()
        else:
            seasonal = weekly
        
        if DEBUG:
            print(f"  Aggregated to {len(seasonal)} player-season records")
        
        return seasonal
    
    def load_weekly_stats(self, years: list[int]) -> pd.DataFrame:
        """
        Load weekly player statistics.
        
        Args:
            years: List of seasons to load
            
        Returns:
            DataFrame with player weekly statistics
        """
        if DEBUG:
            print(f"Loading weekly stats for {years}...")
        
        df = nfl.load_player_stats(years)
        df = polars_to_pandas(df)
        
        if DEBUG:
            print(f"  Loaded {len(df)} player-week records")
        
        return df
    
    def load_rosters(self, years: list[int]) -> pd.DataFrame:
        """
        Load team rosters.
        
        Args:
            years: List of seasons to load
            
        Returns:
            DataFrame with roster information
        """
        if DEBUG:
            print(f"Loading rosters for {years}...")
        
        df = nfl.load_rosters(years)
        df = polars_to_pandas(df)
        
        if DEBUG:
            print(f"  Loaded {len(df)} roster entries")
        
        return df
    
    def load_schedules(self, years: list[int]) -> pd.DataFrame:
        """
        Load game schedules and results.
        
        Args:
            years: List of seasons to load
            
        Returns:
            DataFrame with game schedules and scores
        """
        if DEBUG:
            print(f"Loading schedules for {years}...")
        
        df = nfl.load_schedules(years)
        df = polars_to_pandas(df)
        
        if DEBUG:
            print(f"  Loaded {len(df)} games")
        
        return df
    
    def load_team_descriptions(self) -> pd.DataFrame:
        """
        Load team information (names, abbreviations, colors, etc.).
        
        Returns:
            DataFrame with team information
        """
        if DEBUG:
            print("Loading team descriptions...")
        
        df = nfl.load_teams()
        df = polars_to_pandas(df)
        
        if DEBUG:
            print(f"  Loaded {len(df)} teams")
        
        return df
    
    def enrich_schedules_with_weather(
        self,
        schedules_df: pd.DataFrame,
        progress: bool = True
    ) -> pd.DataFrame:
        """
        Add weather data to schedules for outdoor games.
        
        Args:
            schedules_df: DataFrame with game schedules
            progress: Show progress bar
            
        Returns:
            DataFrame with weather column added
        """
        print("\nEnriching schedules with weather data...")
        
        # Convert to list of dicts for processing
        games = schedules_df.to_dict(orient="records")
        
        # Fetch weather
        games_with_weather = self.weather_fetcher.fetch_weather_for_games(
            games=games,
            stadium_lookup_fn=get_stadium_coordinates,
            progress=progress
        )
        
        # Convert back to DataFrame
        return pd.DataFrame(games_with_weather)
    
    def load_all_data(
        self,
        years: list[int],
        include_weekly: bool = True,
        include_weather: bool = True,
    ) -> dict[str, pd.DataFrame]:
        """
        Load all relevant NFL data for the RAG application.
        
        Args:
            years: List of seasons to load
            include_weekly: Whether to include weekly stats (default: True)
            include_weather: Whether to fetch weather data for outdoor games
            
        Returns:
            Dictionary mapping data type to DataFrame
        """
        print("=" * 60)
        print("NFL Data Loader (using nflreadpy)")
        print("=" * 60)
        print(f"Seasons: {min(years)} - {max(years)}")
        print(f"Include weekly stats: {include_weekly}")
        print(f"Include weather data: {include_weather}")
        print("=" * 60)
        
        data = {}
        
        # Seasonal offensive stats
        print("\n[1/6] Loading seasonal offensive stats...")
        data["seasonal_offense"] = self.load_seasonal_stats(years)
        
        # Rosters
        print("\n[2/6] Loading rosters...")
        data["rosters"] = self.load_rosters(years)
        
        # Schedules
        print("\n[3/6] Loading schedules...")
        schedules_df = self.load_schedules(years)
        
        # Weather enrichment
        if include_weather:
            print("\n[4/6] Fetching weather data for outdoor games...")
            schedules_df = self.enrich_schedules_with_weather(schedules_df)
        else:
            print("\n[4/6] Skipping weather data (use include_weather=True to include)")
        
        data["schedules"] = schedules_df
        
        # Team info
        print("\n[5/6] Loading team info...")
        data["teams"] = self.load_team_descriptions()
        
        # Weekly stats (default: included)
        if include_weekly:
            print("\n[6/6] Loading weekly stats...")
            data["weekly_offense"] = self.load_weekly_stats(years)
        else:
            print("\n[6/6] Skipping weekly stats (use include_weekly=True to include)")
        
        # Summary
        print("\n" + "=" * 60)
        print("Data Loading Complete!")
        print("=" * 60)
        for name, df in data.items():
            print(f"  {name}: {len(df)} records, {len(df.columns)} columns")
        
        return data
    
    def save_data(self, data: dict[str, pd.DataFrame], filename: str = "nfl_data.json"):
        """
        Save loaded data to JSON files.
        
        Args:
            data: Dictionary of DataFrames to save
            filename: Base filename for output
        """
        output_dir = self.cache_dir
        
        # Save metadata
        metadata = {
            "downloaded_at": datetime.now().isoformat(),
            "source": "nflverse (nflreadpy)",
            "datasets": {}
        }
        
        for name, df in data.items():
            # Convert DataFrame to records
            records = df.to_dict(orient="records")
            
            # Save individual dataset
            dataset_file = output_dir / f"{name}.json"
            with open(dataset_file, "w", encoding="utf-8") as f:
                json.dump(records, f, indent=2, default=str)
            
            metadata["datasets"][name] = {
                "file": str(dataset_file.name),
                "records": len(records),
                "columns": list(df.columns),
            }
            
            print(f"Saved {name} to {dataset_file}")
        
        # Save metadata
        metadata_file = output_dir / "metadata.json"
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
        
        print(f"\nMetadata saved to {metadata_file}")
        
        return output_dir
    
    def load_cached_data(self, dataset_name: str) -> list[dict]:
        """
        Load previously cached data.
        
        Args:
            dataset_name: Name of the dataset to load
            
        Returns:
            List of records
        """
        file_path = self.cache_dir / f"{dataset_name}.json"
        
        if not file_path.exists():
            raise FileNotFoundError(f"Cached data not found: {file_path}")
        
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)


def main():
    """Command-line interface for the data loader."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Download NFL data from nflverse")
    parser.add_argument(
        "--start-year",
        type=int,
        default=2020,
        help="First season to download (default: 2020)",
    )
    parser.add_argument(
        "--end-year",
        type=int,
        default=2024,
        help="Last season to download (default: 2024)",
    )
    parser.add_argument(
        "--no-weekly",
        action="store_true",
        help="Skip weekly stats (smaller download, faster)",
    )
    parser.add_argument(
        "--no-weather",
        action="store_true",
        help="Skip weather data enrichment",
    )
    
    args = parser.parse_args()
    
    years = list(range(args.start_year, args.end_year + 1))
    
    loader = NFLDataLoader()
    data = loader.load_all_data(
        years,
        include_weekly=not args.no_weekly,
        include_weather=not args.no_weather
    )
    loader.save_data(data)


if __name__ == "__main__":
    main()