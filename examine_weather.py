"""
Examine the weather-enriched NFL schedule data.
"""

import json
from pathlib import Path
from src.config import RAW_DATA_DIR


def main():
    # Check for schedules file
    schedules_file = RAW_DATA_DIR / "schedules.json"
    
    if not schedules_file.exists():
        print(f"Schedules file not found: {schedules_file}")
        print("Run the loader first:")
        print("  python -m src.ingestion.scraper --start-year 2023 --end-year 2023")
        return
    
    with open(schedules_file, "r") as f:
        schedules = json.load(f)
    
    print("=" * 70)
    print("NFL Schedule Weather Data Analysis")
    print("=" * 70)
    print(f"Total games: {len(schedules)}")
    print()
    
    # Analyze weather data
    has_weather = 0
    outdoor_games = 0
    dome_games = 0
    weather_errors = 0
    
    coldest_game = None
    coldest_temp = 999
    hottest_game = None
    hottest_temp = -999
    windiest_game = None
    max_wind = 0
    
    for game in schedules:
        weather = game.get("weather", {})
        
        if not weather:
            continue
        
        if not weather.get("is_outdoor_game", True):
            dome_games += 1
            continue
        
        outdoor_games += 1
        
        if weather.get("weather_fetched"):
            has_weather += 1
            
            temp = weather.get("temperature_f")
            if temp is not None:
                if temp < coldest_temp:
                    coldest_temp = temp
                    coldest_game = game
                if temp > hottest_temp:
                    hottest_temp = temp
                    hottest_game = game
            
            wind = weather.get("wind_speed_mph")
            if wind is not None and wind > max_wind:
                max_wind = wind
                windiest_game = game
        else:
            weather_errors += 1
    
    print("Game Breakdown:")
    print(f"  Outdoor games: {outdoor_games}")
    print(f"  Dome games: {dome_games}")
    print(f"  With weather data: {has_weather}")
    print(f"  Weather fetch errors: {weather_errors}")
    print()
    
    # Show extreme games
    if coldest_game:
        w = coldest_game.get("weather", {})
        print("=" * 70)
        print("COLDEST GAME")
        print("=" * 70)
        print(f"  {coldest_game.get('away_team')} @ {coldest_game.get('home_team')}")
        print(f"  Date: {coldest_game.get('gameday')}")
        print(f"  Stadium: {coldest_game.get('stadium', 'N/A')}")
        print(f"  Temperature: {w.get('temperature_f')}°F")
        print(f"  Feels like: {w.get('feels_like_f')}°F")
        print(f"  Wind: {w.get('wind_speed_mph')} mph {w.get('wind_direction_cardinal')}")
        print(f"  Conditions: {w.get('conditions')}")
        print()
    
    if hottest_game:
        w = hottest_game.get("weather", {})
        print("=" * 70)
        print("HOTTEST GAME")
        print("=" * 70)
        print(f"  {hottest_game.get('away_team')} @ {hottest_game.get('home_team')}")
        print(f"  Date: {hottest_game.get('gameday')}")
        print(f"  Stadium: {hottest_game.get('stadium', 'N/A')}")
        print(f"  Temperature: {w.get('temperature_f')}°F")
        print(f"  Feels like: {w.get('feels_like_f')}°F")
        print(f"  Humidity: {w.get('humidity_pct')}%")
        print(f"  Conditions: {w.get('conditions')}")
        print()
    
    if windiest_game:
        w = windiest_game.get("weather", {})
        print("=" * 70)
        print("WINDIEST GAME")
        print("=" * 70)
        print(f"  {windiest_game.get('away_team')} @ {windiest_game.get('home_team')}")
        print(f"  Date: {windiest_game.get('gameday')}")
        print(f"  Stadium: {windiest_game.get('stadium', 'N/A')}")
        print(f"  Wind: {w.get('wind_speed_mph')} mph {w.get('wind_direction_cardinal')}")
        print(f"  Gusts: {w.get('wind_gust_mph')} mph")
        print(f"  Temperature: {w.get('temperature_f')}°F")
        print(f"  Conditions: {w.get('conditions')}")
        print()
    
    # Show sample games with weather
    print("=" * 70)
    print("SAMPLE GAMES WITH WEATHER")
    print("=" * 70)
    
    shown = 0
    for game in schedules:
        weather = game.get("weather", {})
        if weather.get("weather_fetched") and shown < 5:
            print(f"\n{game.get('away_team')} @ {game.get('home_team')} - {game.get('gameday')}")
            print(f"  Temp: {weather.get('temperature_f')}°F (feels {weather.get('feels_like_f')}°F)")
            print(f"  Wind: {weather.get('wind_speed_mph')} mph {weather.get('wind_direction_cardinal')}")
            print(f"  Conditions: {weather.get('conditions')}")
            if weather.get('precipitation_inches', 0) > 0:
                print(f"  Precipitation: {weather.get('precipitation_inches')}\"")
            if weather.get('snowfall_inches', 0) > 0:
                print(f"  Snowfall: {weather.get('snowfall_inches')}\"")
            shown += 1
    
    # Weather conditions distribution
    print("\n" + "=" * 70)
    print("WEATHER CONDITIONS DISTRIBUTION")
    print("=" * 70)
    
    conditions_count = {}
    for game in schedules:
        weather = game.get("weather", {})
        if weather.get("weather_fetched"):
            condition = weather.get("conditions", "Unknown")
            conditions_count[condition] = conditions_count.get(condition, 0) + 1
    
    for condition, count in sorted(conditions_count.items(), key=lambda x: -x[1]):
        bar = "█" * (count // 2)
        print(f"  {condition:25} {count:4} {bar}")


if __name__ == "__main__":
    main()
