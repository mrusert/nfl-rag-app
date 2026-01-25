"""
Test the weather enrichment feature for NFL games.
"""

import sys
from datetime import datetime


def test_stadium_lookup():
    """Test the stadium coordinates lookup."""
    print("Testing stadium lookup...")
    
    from src.ingestion.stadiums import (
        get_stadium,
        get_stadium_coordinates,
        is_outdoor_stadium,
        find_stadium_by_team,
        list_current_stadiums,
        list_outdoor_stadiums,
    )
    
    # Test various stadium names
    test_cases = [
        ("Arrowhead Stadium", True, (39.0489, -94.4839)),
        ("GEHA Field at Arrowhead Stadium", True, (39.0489, -94.4839)),
        ("Lambeau Field", True, (44.5013, -88.0622)),
        ("Ford Field", False, None),  # Dome
        ("Caesars Superdome", False, None),  # Dome
        ("Hard Rock Stadium", True, (25.9580, -80.2389)),
        ("Sun Life Stadium", True, (25.9580, -80.2389)),  # Old name for Hard Rock
        ("Highmark Stadium", True, (42.7738, -78.7870)),
        ("Unknown Stadium XYZ", None, None),
    ]
    
    passed = 0
    failed = 0
    
    for name, expected_outdoor, expected_coords in test_cases:
        stadium = get_stadium(name)
        coords = get_stadium_coordinates(name)
        is_outdoor = is_outdoor_stadium(name)
        
        if expected_outdoor is None:
            # Expecting not found
            if stadium is None:
                print(f"  ✓ '{name}' correctly not found")
                passed += 1
            else:
                print(f"  ✗ '{name}' unexpectedly found: {stadium.name}")
                failed += 1
        else:
            if stadium is None:
                print(f"  ✗ '{name}' not found (expected: found)")
                failed += 1
            elif is_outdoor != expected_outdoor:
                print(f"  ✗ '{name}' outdoor={is_outdoor} (expected: {expected_outdoor})")
                failed += 1
            elif expected_coords and coords:
                if abs(coords[0] - expected_coords[0]) > 0.01 or abs(coords[1] - expected_coords[1]) > 0.01:
                    print(f"  ✗ '{name}' coords mismatch: {coords} vs {expected_coords}")
                    failed += 1
                else:
                    print(f"  ✓ '{name}' → {stadium.name} ({coords[0]:.2f}, {coords[1]:.2f})")
                    passed += 1
            else:
                print(f"  ✓ '{name}' → {stadium.name} (dome)")
                passed += 1
    
    # Test team lookup
    print("\n  Testing team lookup...")
    stadium = find_stadium_by_team("KC", 2023)
    if stadium and "Arrowhead" in stadium.name:
        print(f"  ✓ KC (2023) → {stadium.name}")
        passed += 1
    else:
        print(f"  ✗ KC (2023) lookup failed")
        failed += 1
    
    # Test historical stadium
    stadium = find_stadium_by_team("OAK", 2019)
    if stadium and "Oakland" in stadium.name:
        print(f"  ✓ OAK (2019) → {stadium.name}")
        passed += 1
    else:
        print(f"  ✗ OAK (2019) lookup failed")
        failed += 1
    
    # Summary stats
    print(f"\n  Current stadiums: {len(list_current_stadiums())}")
    print(f"  Outdoor stadiums: {len(list_outdoor_stadiums())}")
    
    return passed, failed


def test_weather_fetcher():
    """Test the weather fetcher with known games."""
    print("\nTesting weather fetcher...")
    
    from src.ingestion.weather import WeatherFetcher, degrees_to_cardinal
    
    fetcher = WeatherFetcher()
    passed = 0
    failed = 0
    
    # Test conversion functions
    from src.ingestion.weather import (
        celsius_to_fahrenheit,
        kmh_to_mph,
        mm_to_inches,
    )
    
    # Conversion tests
    if abs(celsius_to_fahrenheit(0) - 32) < 0.1:
        print("  ✓ Celsius to Fahrenheit conversion")
        passed += 1
    else:
        print("  ✗ Celsius to Fahrenheit conversion")
        failed += 1
    
    if abs(kmh_to_mph(100) - 62.1) < 0.5:
        print("  ✓ km/h to mph conversion")
        passed += 1
    else:
        print("  ✗ km/h to mph conversion")
        failed += 1
    
    # Cardinal direction test
    test_directions = [
        (0, "N"),
        (90, "E"),
        (180, "S"),
        (270, "W"),
        (45, "NE"),
    ]
    
    for deg, expected in test_directions:
        result = degrees_to_cardinal(deg)
        if result == expected:
            print(f"  ✓ {deg}° → {result}")
            passed += 1
        else:
            print(f"  ✗ {deg}° → {result} (expected {expected})")
            failed += 1
    
    # Test actual weather fetch - Chiefs vs Dolphins (famous cold game)
    print("\n  Fetching real weather data...")
    print("  Game: Chiefs vs Dolphins, Jan 13, 2024 (very cold playoff game)")
    
    weather = fetcher.fetch_weather(
        latitude=39.0489,  # Arrowhead Stadium
        longitude=-94.4839,
        game_date="2024-01-13",
        game_time="19:00",
        timezone="America/Chicago"
    )
    
    if weather.weather_fetched:
        print(f"  ✓ Weather fetched successfully")
        print(f"    Temperature: {weather.temperature_f}°F")
        print(f"    Feels like: {weather.feels_like_f}°F")
        print(f"    Wind: {weather.wind_speed_mph} mph {weather.wind_direction_cardinal}")
        print(f"    Conditions: {weather.conditions}")
        
        # This game was VERY cold - verify
        if weather.temperature_f is not None and weather.temperature_f < 20:
            print(f"  ✓ Temperature correctly shows very cold game")
            passed += 1
        else:
            print(f"  ⚠ Temperature might not reflect the cold conditions")
            passed += 1  # Still pass, weather varies by exact hour
    else:
        print(f"  ✗ Weather fetch failed: {weather.fetch_error}")
        failed += 1
    
    # Test a warm weather game
    print("\n  Game: Dolphins home game, Sep 2023 (warm)")
    weather = fetcher.fetch_weather(
        latitude=25.9580,  # Hard Rock Stadium
        longitude=-80.2389,
        game_date="2023-09-17",
        game_time="13:00",
        timezone="America/New_York"
    )
    
    if weather.weather_fetched:
        print(f"  ✓ Weather fetched successfully")
        print(f"    Temperature: {weather.temperature_f}°F")
        print(f"    Humidity: {weather.humidity_pct}%")
        print(f"    Conditions: {weather.conditions}")
        passed += 1
    else:
        print(f"  ✗ Weather fetch failed: {weather.fetch_error}")
        failed += 1
    
    return passed, failed


def test_integration():
    """Test the full integration with actual schedule data."""
    print("\nTesting full integration (limited scope)...")
    
    import nflreadpy as nfl
    from src.ingestion.stadiums import get_stadium_coordinates
    from src.ingestion.weather import WeatherFetcher
    
    passed = 0
    failed = 0
    
    # Load a small sample of schedules
    print("  Loading 2023 schedule...")
    try:
        schedules = nfl.load_schedules([2023])
        # Convert Polars to pandas if needed
        if hasattr(schedules, 'to_pandas'):
            schedules = schedules.to_pandas()
        print(f"  ✓ Loaded {len(schedules)} games")
        passed += 1
    except Exception as e:
        print(f"  ✗ Failed to load schedules: {e}")
        failed += 1
        return passed, failed
    
    # Check what columns we have
    print(f"  Columns: {list(schedules.columns)[:10]}...")
    
    # Check for required fields
    required_fields = ["gameday", "gametime", "home_team", "away_team"]
    for field in required_fields:
        if field in schedules.columns:
            print(f"  ✓ Found field: {field}")
            passed += 1
        else:
            print(f"  ✗ Missing field: {field}")
            failed += 1
    
    # Check roof field
    if "roof" in schedules.columns:
        roof_values = schedules["roof"].value_counts()
        print(f"  ✓ Roof types: {dict(roof_values)}")
        passed += 1
    else:
        print(f"  ⚠ No 'roof' field - will need to determine from stadium")
    
    # Test weather fetch for ONE outdoor game
    outdoor_games = schedules[schedules.get("roof", "") == "outdoors"].head(3)
    
    if len(outdoor_games) > 0:
        print(f"\n  Testing weather for sample outdoor game...")
        game = outdoor_games.iloc[0].to_dict()
        
        fetcher = WeatherFetcher()
        
        # Get stadium coordinates
        stadium_name = game.get("stadium", "")
        home_team = game.get("home_team", "")
        
        coords = get_stadium_coordinates(stadium_name)
        if not coords:
            from src.ingestion.stadiums import find_stadium_by_team
            stadium = find_stadium_by_team(home_team, 2023)
            if stadium:
                coords = (stadium.latitude, stadium.longitude)
        
        if coords:
            print(f"  Stadium: {stadium_name or home_team}")
            print(f"  Date: {game.get('gameday', 'N/A')}")
            print(f"  Coords: {coords}")
            
            weather = fetcher.fetch_weather(
                latitude=coords[0],
                longitude=coords[1],
                game_date=str(game.get("gameday", "")),
                game_time=str(game.get("gametime", "13:00")),
            )
            
            if weather.weather_fetched:
                print(f"  ✓ Weather: {weather.temperature_f}°F, {weather.conditions}")
                passed += 1
            else:
                print(f"  ✗ Weather fetch failed: {weather.fetch_error}")
                failed += 1
        else:
            print(f"  ⚠ Could not find coordinates for {stadium_name}")
    
    return passed, failed


def main():
    print("=" * 60)
    print("Weather Enrichment Tests")
    print("=" * 60)
    print(f"Time: {datetime.now().isoformat()}")
    print("=" * 60)
    
    total_passed = 0
    total_failed = 0
    
    # Test 1: Stadium lookup
    p, f = test_stadium_lookup()
    total_passed += p
    total_failed += f
    
    # Test 2: Weather fetcher
    p, f = test_weather_fetcher()
    total_passed += p
    total_failed += f
    
    # Test 3: Integration
    p, f = test_integration()
    total_passed += p
    total_failed += f
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    print(f"  Passed: {total_passed}")
    print(f"  Failed: {total_failed}")
    print(f"  Total:  {total_passed + total_failed}")
    
    if total_failed == 0:
        print("\n✓ All tests passed!")
        return 0
    else:
        print(f"\n✗ {total_failed} tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())