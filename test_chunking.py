"""
Test the NFL data chunking functionality.
"""

import json
from pathlib import Path


def test_templates():
    """Test the template functions with sample data."""
    print("Testing template functions...")
    
    from src.processing.templates import (
        player_season_chunk,
        player_game_chunk,
        game_summary_chunk,
        player_bio_chunk,
        team_info_chunk,
        describe_spread_result,
        describe_weather,
        categorize_temperature,
    )
    
    passed = 0
    failed = 0
    
    # Test player season chunk
    sample_player_season = {
        "player_name": "P.Mahomes",
        "player_display_name": "Patrick Mahomes",
        "player_id": "00-0033873",
        "season": 2023,
        "position": "QB",
        "recent_team": "KC",
        "completions": 401,
        "attempts": 597,
        "passing_yards": 4183,
        "passing_tds": 27,
        "interceptions": 14,
        "rushing_yards": 389,
        "rushing_tds": 2,
        "carries": 75,
        "fantasy_points_ppr": 325.5,
    }
    
    text, metadata = player_season_chunk(sample_player_season)
    
    if "Patrick Mahomes" in text and "4183" in text:
        print("  ✓ player_season_chunk works")
        passed += 1
    else:
        print("  ✗ player_season_chunk failed")
        failed += 1
    
    if metadata["chunk_type"] == "player_season" and metadata["passing_yards"] == 4183:
        print("  ✓ player_season_chunk metadata correct")
        passed += 1
    else:
        print("  ✗ player_season_chunk metadata incorrect")
        failed += 1
    
    # Test game summary chunk
    sample_game = {
        "game_id": "2024_20_MIA_KC",
        "season": 2023,
        "week": 20,
        "game_type": "POST",
        "gameday": "2024-01-13",
        "home_team": "KC",
        "away_team": "MIA",
        "home_score": 26,
        "away_score": 7,
        "home_coach": "Andy Reid",
        "away_coach": "Mike McDaniel",
        "spread_line": -4.5,
        "total_line": 48.5,
        "home_rest": 14,
        "away_rest": 7,
        "stadium": "GEHA Field at Arrowhead Stadium",
        "weather": {
            "temperature_f": -4.0,
            "feels_like_f": -27.1,
            "wind_speed_mph": 18.5,
            "wind_direction_cardinal": "NW",
            "conditions": "Overcast",
            "is_outdoor_game": True,
            "weather_fetched": True,
        },
        "result": 19,  # home_score - away_score
        "overtime": 0,
    }
    
    text, metadata = game_summary_chunk(sample_game)
    
    if "KC" in text and "MIA" in text and "-4°F" in text:
        print("  ✓ game_summary_chunk works")
        passed += 1
    else:
        print(f"  ✗ game_summary_chunk failed")
        failed += 1
    
    if metadata["home_covered"] == True:  # KC covered as 4.5 point favorites (won by 19)
        print("  ✓ spread calculation correct")
        passed += 1
    else:
        print("  ✗ spread calculation incorrect")
        failed += 1
    
    # Test weather description
    weather_desc = describe_weather(sample_game["weather"])
    if "-4°F" in weather_desc and "18 mph" in weather_desc:
        print("  ✓ describe_weather works")
        passed += 1
    else:
        print("  ✗ describe_weather failed")
        failed += 1
    
    # Test temperature categorization
    if categorize_temperature(-4) == "freezing":
        print("  ✓ categorize_temperature works")
        passed += 1
    else:
        print("  ✗ categorize_temperature failed")
        failed += 1
    
    # Test player game chunk
    sample_player_game = {
        "player_name": "P.Mahomes",
        "player_display_name": "Patrick Mahomes",
        "player_id": "00-0033873",
        "season": 2023,
        "week": 20,
        "position": "QB",
        "recent_team": "KC",
        "opponent_team": "MIA",
        "completions": 23,
        "attempts": 35,
        "passing_yards": 262,
        "passing_tds": 2,
        "interceptions": 0,
        "fantasy_points_ppr": 22.5,
    }
    
    text, metadata = player_game_chunk(sample_player_game, sample_game)
    
    if "Patrick Mahomes" in text and "262" in text and "Weather:" in text:
        print("  ✓ player_game_chunk with game context works")
        passed += 1
    else:
        print("  ✗ player_game_chunk failed")
        failed += 1
    
    if metadata.get("temperature_category") == "freezing":
        print("  ✓ player_game_chunk weather metadata correct")
        passed += 1
    else:
        print("  ✗ player_game_chunk weather metadata incorrect")
        failed += 1
    
    # Test team chunk
    sample_team = {
        "team_abbr": "KC",
        "team_name": "Kansas City Chiefs",
        "team_conf": "AFC",
        "team_division": "AFC West",
        "team_city": "Kansas City",
        "team_stadium": "GEHA Field at Arrowhead Stadium",
    }
    
    text, metadata = team_info_chunk(sample_team)
    
    if "Kansas City Chiefs" in text and "AFC West" in text:
        print("  ✓ team_info_chunk works")
        passed += 1
    else:
        print("  ✗ team_info_chunk failed")
        failed += 1
    
    return passed, failed


def test_chunker_with_sample_data():
    """Test the chunker with sample data files."""
    print("\nTesting chunker with sample data...")
    
    from src.processing.chunker import NFLChunker, generate_chunk_id
    from src.config import RAW_DATA_DIR
    
    passed = 0
    failed = 0
    
    # Test chunk ID generation
    id1 = generate_chunk_id("player_season", "00-0033873", 2023)
    id2 = generate_chunk_id("player_season", "00-0033873", 2023)
    id3 = generate_chunk_id("player_season", "00-0033873", 2024)
    
    if id1 == id2:
        print("  ✓ Chunk IDs are deterministic")
        passed += 1
    else:
        print("  ✗ Chunk IDs not deterministic")
        failed += 1
    
    if id1 != id3:
        print("  ✓ Different inputs produce different IDs")
        passed += 1
    else:
        print("  ✗ Different inputs produce same ID")
        failed += 1
    
    # Check if raw data exists
    if not RAW_DATA_DIR.exists():
        print("  ⚠ No raw data directory - skipping data-dependent tests")
        print("    Run: python -m src.ingestion.scraper --start-year 2023 --end-year 2023")
        return passed, failed
    
    # Check for at least one data file
    test_file = RAW_DATA_DIR / "teams.json"
    if not test_file.exists():
        print("  ⚠ No data files found - skipping data-dependent tests")
        return passed, failed
    
    # Test chunker initialization
    try:
        chunker = NFLChunker()
        print("  ✓ Chunker initialized")
        passed += 1
    except Exception as e:
        print(f"  ✗ Chunker init failed: {e}")
        failed += 1
        return passed, failed
    
    # Test team chunking (smallest dataset)
    try:
        team_chunks = list(chunker.chunk_teams())
        if len(team_chunks) > 0:
            print(f"  ✓ Created {len(team_chunks)} team chunks")
            passed += 1
        else:
            print("  ✗ No team chunks created")
            failed += 1
    except Exception as e:
        print(f"  ✗ Team chunking failed: {e}")
        failed += 1
    
    # Test game chunking if schedules exist
    schedules_file = RAW_DATA_DIR / "schedules.json"
    if schedules_file.exists():
        try:
            game_chunks = list(chunker.chunk_games())
            if len(game_chunks) > 0:
                print(f"  ✓ Created {len(game_chunks)} game chunks")
                passed += 1
                
                # Check that at least some have weather data
                with_weather = sum(
                    1 for c in game_chunks 
                    if c.metadata.get("temperature_f") is not None
                )
                print(f"    ({with_weather} have weather data)")
            else:
                print("  ✗ No game chunks created")
                failed += 1
        except Exception as e:
            print(f"  ✗ Game chunking failed: {e}")
            failed += 1
    
    return passed, failed


def test_processor():
    """Test the data processor."""
    print("\nTesting data processor...")
    
    from src.processing.processor import NFLDataProcessor
    from src.config import RAW_DATA_DIR
    
    passed = 0
    failed = 0
    
    # Initialize processor
    try:
        processor = NFLDataProcessor()
        print("  ✓ Processor initialized")
        passed += 1
    except Exception as e:
        print(f"  ✗ Processor init failed: {e}")
        failed += 1
        return passed, failed
    
    # Check raw data status
    try:
        status = processor.check_raw_data()
        found = sum(1 for v in status.values() if v["exists"])
        print(f"  ✓ Found {found}/{len(status)} data files")
        passed += 1
    except Exception as e:
        print(f"  ✗ check_raw_data failed: {e}")
        failed += 1
    
    return passed, failed


def test_sample_output():
    """Show sample chunk output."""
    print("\nSample Chunk Output")
    print("=" * 60)
    
    from src.processing.templates import (
        player_season_chunk,
        player_game_chunk,
        game_summary_chunk,
    )
    
    # Create a realistic game example
    game = {
        "game_id": "2024_20_MIA_KC",
        "season": 2023,
        "week": 20,
        "game_type": "POST",
        "gameday": "2024-01-13",
        "home_team": "KC",
        "away_team": "MIA",
        "home_score": 26,
        "away_score": 7,
        "home_coach": "Andy Reid",
        "away_coach": "Mike McDaniel",
        "spread_line": -4.5,
        "total_line": 48.5,
        "home_rest": 14,
        "away_rest": 7,
        "stadium": "GEHA Field at Arrowhead Stadium",
        "div_game": 0,
        "weather": {
            "temperature_f": -4.0,
            "feels_like_f": -27.1,
            "wind_speed_mph": 18.5,
            "wind_direction_cardinal": "NW",
            "conditions": "Overcast",
            "precipitation_inches": 0,
            "snowfall_inches": 0,
            "is_outdoor_game": True,
            "weather_fetched": True,
        },
        "result": 19,
        "overtime": 0,
    }
    
    print("\n--- GAME SUMMARY CHUNK ---")
    text, metadata = game_summary_chunk(game)
    print(text)
    print(f"\nKey metadata: winner={metadata.get('winner')}, "
          f"home_covered={metadata.get('home_covered')}, "
          f"went_over={metadata.get('went_over')}, "
          f"temp={metadata.get('temperature_category')}")
    
    # Player game example
    player = {
        "player_display_name": "Patrick Mahomes",
        "player_id": "00-0033873",
        "season": 2023,
        "week": 20,
        "position": "QB",
        "recent_team": "KC",
        "opponent_team": "MIA",
        "completions": 23,
        "attempts": 35,
        "passing_yards": 262,
        "passing_tds": 2,
        "interceptions": 0,
        "rushing_yards": 29,
        "rushing_tds": 0,
        "carries": 4,
        "fantasy_points_ppr": 22.5,
    }
    
    print("\n--- PLAYER GAME CHUNK ---")
    text, metadata = player_game_chunk(player, game)
    print(text)
    print(f"\nKey metadata: is_home={metadata.get('is_home')}, "
          f"was_favorite={metadata.get('was_favorite')}, "
          f"temp={metadata.get('temperature_category')}")


def main():
    print("=" * 60)
    print("NFL Chunking Tests")
    print("=" * 60)
    
    total_passed = 0
    total_failed = 0
    
    # Test templates
    p, f = test_templates()
    total_passed += p
    total_failed += f
    
    # Test chunker
    p, f = test_chunker_with_sample_data()
    total_passed += p
    total_failed += f
    
    # Test processor
    p, f = test_processor()
    total_passed += p
    total_failed += f
    
    # Show sample output
    test_sample_output()
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    print(f"  Passed: {total_passed}")
    print(f"  Failed: {total_failed}")
    
    if total_failed == 0:
        print("\n✓ All tests passed!")
    else:
        print(f"\n✗ {total_failed} tests failed")


if __name__ == "__main__":
    main()