"""
Test the NFL data loader including weather enrichment.

Uses nflreadpy to fetch NFL data from nflverse repositories.
"""

import pandas as pd
from src.ingestion.scraper import NFLDataLoader


def test_seasonal_stats():
    """Test loading seasonal statistics."""
    print("Testing seasonal stats loading...")
    
    loader = NFLDataLoader()
    
    try:
        df = loader.load_seasonal_stats([2023])
        
        print(f"  ✓ Loaded {len(df)} player-season records")
        print(f"  ✓ Columns: {len(df.columns)}")
        
        # Find Patrick Mahomes
        if "player_name" in df.columns:
            mahomes = df[df["player_name"].str.contains("Mahomes", na=False)]
            if not mahomes.empty:
                m = mahomes.iloc[0]
                print(f"  ✓ Found Patrick Mahomes:")
                print(f"    - Passing yards: {m.get('passing_yards', 'N/A')}")
                print(f"    - Passing TDs: {m.get('passing_tds', 'N/A')}")
                print(f"    - Interceptions: {m.get('interceptions', 'N/A')}")
            else:
                print("  ⚠ Could not find Mahomes (might be in different format)")
        
        # Show sample columns
        print(f"  Sample columns: {list(df.columns)[:10]}...")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_rosters():
    """Test loading roster data."""
    print("\nTesting roster loading...")
    
    loader = NFLDataLoader()
    
    try:
        df = loader.load_rosters([2023])
        
        print(f"  ✓ Loaded {len(df)} roster entries")
        
        # Find Travis Kelce
        if "player_name" in df.columns:
            kelce = df[df["player_name"].str.contains("Kelce", na=False)]
            if not kelce.empty:
                k = kelce.iloc[0]
                print(f"  ✓ Found Travis Kelce:")
                print(f"    - Team: {k.get('team', 'N/A')}")
                print(f"    - Position: {k.get('position', 'N/A')}")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


def test_schedules():
    """Test loading schedule data."""
    print("\nTesting schedule loading...")
    
    loader = NFLDataLoader()
    
    try:
        df = loader.load_schedules([2023])
        
        print(f"  ✓ Loaded {len(df)} games")
        
        # Check for required columns
        required_cols = ["gameday", "home_team", "away_team", "roof"]
        for col in required_cols:
            if col in df.columns:
                print(f"  ✓ Has column: {col}")
            else:
                print(f"  ⚠ Missing column: {col}")
        
        # Find Super Bowl
        if "game_type" in df.columns:
            super_bowl = df[df["game_type"] == "SB"]
            if not super_bowl.empty:
                sb = super_bowl.iloc[0]
                print(f"  ✓ Found Super Bowl:")
                print(f"    - {sb.get('away_team', '?')} vs {sb.get('home_team', '?')}")
                print(f"    - Score: {sb.get('away_score', '?')} - {sb.get('home_score', '?')}")
        
        # Check roof distribution
        if "roof" in df.columns:
            roof_counts = df["roof"].value_counts().to_dict()
            print(f"  ✓ Roof types: {roof_counts}")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


def test_teams():
    """Test loading team data."""
    print("\nTesting team info loading...")
    
    loader = NFLDataLoader()
    
    try:
        df = loader.load_team_descriptions()
        
        print(f"  ✓ Loaded {len(df)} teams")
        
        # Find Chiefs
        if "team_name" in df.columns:
            chiefs = df[df["team_name"].str.contains("Chiefs", na=False)]
            if not chiefs.empty:
                c = chiefs.iloc[0]
                print(f"  ✓ Found Kansas City Chiefs:")
                print(f"    - Abbreviation: {c.get('team_abbr', 'N/A')}")
                print(f"    - Conference: {c.get('team_conf', 'N/A')}")
                print(f"    - Division: {c.get('team_division', 'N/A')}")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


def test_weather_enrichment():
    """Test weather enrichment on a small sample."""
    print("\nTesting weather enrichment (sample)...")
    
    loader = NFLDataLoader()
    
    try:
        # Load schedules
        df = loader.load_schedules([2023])
        
        # Filter to just a few outdoor games for testing
        outdoor = df[df["roof"] == "outdoors"].head(3)
        
        if len(outdoor) == 0:
            print("  ⚠ No outdoor games found in sample")
            return True
        
        print(f"  Testing weather fetch for {len(outdoor)} outdoor games...")
        
        # Enrich with weather
        enriched = loader.enrich_schedules_with_weather(outdoor, progress=False)
        
        # Check results
        weather_fetched = 0
        for _, game in enriched.iterrows():
            weather = game.get("weather", {})
            if isinstance(weather, dict) and weather.get("weather_fetched"):
                weather_fetched += 1
                
                # Show sample
                if weather_fetched == 1:
                    print(f"  ✓ Sample weather data:")
                    print(f"    - Game: {game.get('away_team')} @ {game.get('home_team')}")
                    print(f"    - Date: {game.get('gameday')}")
                    print(f"    - Temp: {weather.get('temperature_f')}°F")
                    print(f"    - Wind: {weather.get('wind_speed_mph')} mph")
                    print(f"    - Conditions: {weather.get('conditions')}")
        
        print(f"  ✓ Weather fetched for {weather_fetched}/{len(outdoor)} games")
        
        return weather_fetched > 0
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_full_load_no_weather():
    """Test loading all data without weather (faster)."""
    print("\nTesting full data load WITHOUT weather (2023 only)...")
    print("  (Weekly stats included by default)")
    
    loader = NFLDataLoader()
    
    try:
        data = loader.load_all_data([2023], include_weekly=True, include_weather=False)
        
        print(f"\n  ✓ Successfully loaded {len(data)} datasets:")
        for name, df in data.items():
            print(f"    - {name}: {len(df)} records")
        
        # Verify weekly stats are included
        if "weekly_offense" in data:
            print(f"  ✓ Weekly stats included ({len(data['weekly_offense'])} records)")
        else:
            print(f"  ⚠ Weekly stats not found")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_stadium_integration():
    """Test that stadium lookup integrates properly."""
    print("\nTesting stadium lookup integration...")
    
    from src.ingestion.stadiums import get_stadium, get_stadium_coordinates, find_stadium_by_team
    
    try:
        # Test direct lookup
        coords = get_stadium_coordinates("Arrowhead Stadium")
        if coords:
            print(f"  ✓ Arrowhead Stadium: {coords}")
        else:
            print(f"  ✗ Arrowhead Stadium not found")
            return False
        
        # Test team-based lookup
        stadium = find_stadium_by_team("KC", 2023)
        if stadium:
            print(f"  ✓ KC (2023): {stadium.name}")
        else:
            print(f"  ✗ KC team lookup failed")
            return False
        
        # Test historical lookup
        stadium = find_stadium_by_team("OAK", 2019)
        if stadium:
            print(f"  ✓ OAK (2019): {stadium.name}")
        else:
            print(f"  ✗ OAK historical lookup failed")
            return False
        
        # Test alias lookup
        stadium = get_stadium("Sun Life Stadium")
        if stadium and "Hard Rock" in stadium.name:
            print(f"  ✓ Alias 'Sun Life Stadium' → {stadium.name}")
        else:
            print(f"  ⚠ Alias lookup: got {stadium.name if stadium else 'None'}")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("NFL Data Loader Tests (with Weather)")
    print("=" * 60)
    
    results = []
    
    # Core data loading tests
    results.append(("Seasonal Stats", test_seasonal_stats()))
    results.append(("Rosters", test_rosters()))
    results.append(("Schedules", test_schedules()))
    results.append(("Teams", test_teams()))
    
    # Stadium integration
    results.append(("Stadium Integration", test_stadium_integration()))
    
    # Weather enrichment (small sample)
    results.append(("Weather Enrichment", test_weather_enrichment()))
    
    # Full load without weather (faster)
    results.append(("Full Load (no weather)", test_full_load_no_weather()))
    
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status}: {name}")
    
    passed_count = sum(1 for _, p in results if p)
    total_count = len(results)
    
    print(f"\n{passed_count}/{total_count} tests passed")
    
    if passed_count == total_count:
        print("\n✓ All tests passed!")
    else:
        print(f"\n✗ {total_count - passed_count} tests failed")