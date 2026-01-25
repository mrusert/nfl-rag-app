"""
Weather data fetcher using Open-Meteo Historical API.

This module provides functions to fetch historical weather data
for NFL games based on stadium coordinates and game times.
"""

import time
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass, asdict

import requests
from tqdm import tqdm

from src.config import DEBUG


@dataclass
class GameWeather:
    """Weather conditions for an NFL game."""
    
    # Temperature
    temperature_f: Optional[float] = None
    feels_like_f: Optional[float] = None
    dew_point_f: Optional[float] = None
    
    # Humidity and pressure
    humidity_pct: Optional[float] = None
    pressure_mb: Optional[float] = None
    
    # Precipitation
    precipitation_inches: Optional[float] = None
    rain_inches: Optional[float] = None
    snowfall_inches: Optional[float] = None
    
    # Wind
    wind_speed_mph: Optional[float] = None
    wind_gust_mph: Optional[float] = None
    wind_direction_degrees: Optional[float] = None
    wind_direction_cardinal: Optional[str] = None
    
    # Visibility and clouds
    cloud_cover_pct: Optional[float] = None
    visibility_miles: Optional[float] = None
    
    # Conditions
    weather_code: Optional[int] = None
    conditions: Optional[str] = None
    
    # Metadata
    is_outdoor_game: bool = True
    weather_fetched: bool = False
    fetch_error: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


# WMO Weather interpretation codes
# See: https://open-meteo.com/en/docs
WMO_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Foggy",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow",
    73: "Moderate snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


def degrees_to_cardinal(degrees: float) -> str:
    """Convert wind direction in degrees to cardinal direction."""
    if degrees is None:
        return "N/A"
    
    directions = [
        "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
        "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"
    ]
    index = round(degrees / 22.5) % 16
    return directions[index]


def celsius_to_fahrenheit(celsius: float) -> float:
    """Convert Celsius to Fahrenheit."""
    if celsius is None:
        return None
    return round(celsius * 9/5 + 32, 1)


def kmh_to_mph(kmh: float) -> float:
    """Convert km/h to mph."""
    if kmh is None:
        return None
    return round(kmh * 0.621371, 1)


def mm_to_inches(mm: float) -> float:
    """Convert millimeters to inches."""
    if mm is None:
        return None
    return round(mm * 0.0393701, 2)


def cm_to_inches(cm: float) -> float:
    """Convert centimeters to inches."""
    if cm is None:
        return None
    return round(cm * 0.393701, 2)


def meters_to_miles(meters: float) -> float:
    """Convert meters to miles."""
    if meters is None:
        return None
    return round(meters * 0.000621371, 1)


class WeatherFetcher:
    """
    Fetches historical weather data from Open-Meteo API.
    
    Uses the Historical Weather API for games from 2020+.
    Rate limiting and caching are handled internally.
    """
    
    BASE_URL = "https://archive-api.open-meteo.com/v1/archive"
    
    # Weather variables to request
    HOURLY_VARIABLES = [
        "temperature_2m",
        "relative_humidity_2m",
        "dew_point_2m",
        "apparent_temperature",
        "precipitation",
        "rain",
        "snowfall",
        "surface_pressure",
        "cloud_cover",
        "visibility",
        "wind_speed_10m",
        "wind_direction_10m",
        "wind_gusts_10m",
        "weather_code",
    ]
    
    def __init__(self, requests_per_minute: int = 30):
        """
        Initialize the weather fetcher.
        
        Args:
            requests_per_minute: Rate limit for API calls
        """
        self.min_request_interval = 60.0 / requests_per_minute
        self.last_request_time = 0
        self.session = requests.Session()
    
    def _wait_for_rate_limit(self):
        """Ensure we don't exceed rate limits."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            time.sleep(self.min_request_interval - elapsed)
    
    def fetch_weather(
        self,
        latitude: float,
        longitude: float,
        game_date: str,
        game_time: Optional[str] = None,
        timezone: str = "America/New_York"
    ) -> GameWeather:
        """
        Fetch weather data for a specific location and time.
        
        Args:
            latitude: Stadium latitude
            longitude: Stadium longitude  
            game_date: Game date in YYYY-MM-DD format
            game_time: Game time in HH:MM format (24-hour), defaults to 13:00
            timezone: Timezone for the game
            
        Returns:
            GameWeather object with conditions
        """
        weather = GameWeather()
        
        try:
            # Parse game time
            if game_time:
                try:
                    hour = int(game_time.split(":")[0])
                except (ValueError, IndexError):
                    hour = 13  # Default to 1 PM
            else:
                hour = 13
            
            # Build API request
            params = {
                "latitude": latitude,
                "longitude": longitude,
                "start_date": game_date,
                "end_date": game_date,
                "hourly": ",".join(self.HOURLY_VARIABLES),
                "timezone": timezone,
                "temperature_unit": "celsius",
                "wind_speed_unit": "kmh",
                "precipitation_unit": "mm",
            }
            
            # Rate limiting
            self._wait_for_rate_limit()
            
            if DEBUG:
                print(f"    Fetching weather for {game_date} at ({latitude}, {longitude})")
            
            # Make request
            response = self.session.get(self.BASE_URL, params=params, timeout=30)
            self.last_request_time = time.time()
            
            if response.status_code != 200:
                weather.fetch_error = f"API error: {response.status_code}"
                return weather
            
            data = response.json()
            
            # Extract hourly data
            hourly = data.get("hourly", {})
            times = hourly.get("time", [])
            
            if not times:
                weather.fetch_error = "No data returned"
                return weather
            
            # Find the closest hour to game time
            target_hour = hour
            hour_index = None
            
            for i, t in enumerate(times):
                # Times are like "2023-09-10T13:00"
                time_hour = int(t.split("T")[1].split(":")[0])
                if time_hour == target_hour:
                    hour_index = i
                    break
            
            if hour_index is None:
                # Fall back to midday
                hour_index = min(12, len(times) - 1)
            
            # Extract values for the game hour
            def get_value(key: str) -> Optional[float]:
                values = hourly.get(key, [])
                if hour_index < len(values):
                    return values[hour_index]
                return None
            
            # Temperature
            temp_c = get_value("temperature_2m")
            weather.temperature_f = celsius_to_fahrenheit(temp_c)
            
            feels_like_c = get_value("apparent_temperature")
            weather.feels_like_f = celsius_to_fahrenheit(feels_like_c)
            
            dew_point_c = get_value("dew_point_2m")
            weather.dew_point_f = celsius_to_fahrenheit(dew_point_c)
            
            # Humidity and pressure
            weather.humidity_pct = get_value("relative_humidity_2m")
            weather.pressure_mb = get_value("surface_pressure")
            
            # Precipitation (get sum of a few hours around game time)
            precip_mm = get_value("precipitation")
            weather.precipitation_inches = mm_to_inches(precip_mm) if precip_mm else 0.0
            
            rain_mm = get_value("rain")
            weather.rain_inches = mm_to_inches(rain_mm) if rain_mm else 0.0
            
            snow_cm = get_value("snowfall")
            weather.snowfall_inches = cm_to_inches(snow_cm) if snow_cm else 0.0
            
            # Wind
            wind_kmh = get_value("wind_speed_10m")
            weather.wind_speed_mph = kmh_to_mph(wind_kmh)
            
            gust_kmh = get_value("wind_gusts_10m")
            weather.wind_gust_mph = kmh_to_mph(gust_kmh)
            
            wind_dir = get_value("wind_direction_10m")
            weather.wind_direction_degrees = wind_dir
            weather.wind_direction_cardinal = degrees_to_cardinal(wind_dir)
            
            # Visibility and clouds
            weather.cloud_cover_pct = get_value("cloud_cover")
            
            visibility_m = get_value("visibility")
            weather.visibility_miles = meters_to_miles(visibility_m) if visibility_m else None
            
            # Conditions
            weather_code = get_value("weather_code")
            weather.weather_code = int(weather_code) if weather_code is not None else None
            weather.conditions = WMO_CODES.get(weather.weather_code, "Unknown")
            
            weather.weather_fetched = True
            
        except requests.RequestException as e:
            weather.fetch_error = f"Request error: {str(e)}"
        except Exception as e:
            weather.fetch_error = f"Error: {str(e)}"
        
        return weather
    
    def fetch_weather_for_games(
        self,
        games: list[dict],
        stadium_lookup_fn,
        progress: bool = True
    ) -> list[dict]:
        """
        Fetch weather for a list of games.
        
        Args:
            games: List of game dictionaries with stadium, gameday, gametime fields
            stadium_lookup_fn: Function to get coordinates from stadium name
            progress: Show progress bar
            
        Returns:
            Games list with weather data added
        """
        iterator = tqdm(games, desc="Fetching weather") if progress else games
        
        outdoor_count = 0
        fetched_count = 0
        error_count = 0
        
        for game in iterator:
            # Check if this is an outdoor game
            roof = game.get("roof", "").lower()
            
            # Skip dome games
            if roof in ("dome", "closed"):
                game["weather"] = GameWeather(
                    is_outdoor_game=False,
                    weather_fetched=False
                ).to_dict()
                continue
            
            outdoor_count += 1
            
            # Get stadium coordinates
            stadium_name = game.get("stadium", "")
            coords = stadium_lookup_fn(stadium_name)
            
            if not coords:
                # Try to find by home team
                home_team = game.get("home_team", "")
                season = game.get("season", 2023)
                
                # Import here to avoid circular import
                from src.ingestion.stadiums import find_stadium_by_team
                stadium = find_stadium_by_team(home_team, season)
                
                if stadium:
                    coords = (stadium.latitude, stadium.longitude)
            
            if not coords:
                game["weather"] = GameWeather(
                    is_outdoor_game=True,
                    weather_fetched=False,
                    fetch_error=f"Stadium not found: {stadium_name}"
                ).to_dict()
                error_count += 1
                continue
            
            # Get game date and time
            game_date = game.get("gameday", "")
            if not game_date:
                # Try alternate field names
                game_date = game.get("game_date", "")
            
            game_time = game.get("gametime", "13:00")
            
            if not game_date:
                game["weather"] = GameWeather(
                    is_outdoor_game=True,
                    weather_fetched=False,
                    fetch_error="No game date"
                ).to_dict()
                error_count += 1
                continue
            
            # Determine timezone based on location
            # Simplified: use stadium longitude to estimate timezone
            lon = coords[1]
            if lon > -87:  # Eastern
                tz = "America/New_York"
            elif lon > -100:  # Central
                tz = "America/Chicago"
            elif lon > -115:  # Mountain
                tz = "America/Denver"
            else:  # Pacific
                tz = "America/Los_Angeles"
            
            # International games
            if coords[0] > 50:  # Europe
                tz = "Europe/London"
            elif coords[0] < 25:  # Mexico
                tz = "America/Mexico_City"
            
            # Fetch weather
            weather = self.fetch_weather(
                latitude=coords[0],
                longitude=coords[1],
                game_date=game_date,
                game_time=game_time,
                timezone=tz
            )
            
            game["weather"] = weather.to_dict()
            
            if weather.weather_fetched:
                fetched_count += 1
            else:
                error_count += 1
        
        if progress:
            print(f"\nWeather fetch complete:")
            print(f"  Outdoor games: {outdoor_count}")
            print(f"  Successfully fetched: {fetched_count}")
            print(f"  Errors: {error_count}")
        
        return games


# Quick test
if __name__ == "__main__":
    print("Weather Fetcher Test")
    print("=" * 50)
    
    fetcher = WeatherFetcher()
    
    # Test: Chiefs vs Bills, January 2024 (cold weather game)
    print("\nTest: Chiefs at Bills - January 21, 2024")
    weather = fetcher.fetch_weather(
        latitude=42.7738,  # Highmark Stadium
        longitude=-78.7870,
        game_date="2024-01-21",
        game_time="18:30",
        timezone="America/New_York"
    )
    
    if weather.weather_fetched:
        print(f"  ✓ Temperature: {weather.temperature_f}°F")
        print(f"  ✓ Feels like: {weather.feels_like_f}°F")
        print(f"  ✓ Wind: {weather.wind_speed_mph} mph {weather.wind_direction_cardinal}")
        print(f"  ✓ Conditions: {weather.conditions}")
        print(f"  ✓ Precipitation: {weather.precipitation_inches}\"")
        print(f"  ✓ Snowfall: {weather.snowfall_inches}\"")
    else:
        print(f"  ✗ Error: {weather.fetch_error}")
    
    # Test: Dolphins vs Chiefs, January 2024 (very cold)
    print("\nTest: Dolphins at Chiefs - January 13, 2024 (Freezing cold game)")
    weather = fetcher.fetch_weather(
        latitude=39.0489,  # Arrowhead
        longitude=-94.4839,
        game_date="2024-01-13",
        game_time="19:00",
        timezone="America/Chicago"
    )
    
    if weather.weather_fetched:
        print(f"  ✓ Temperature: {weather.temperature_f}°F")
        print(f"  ✓ Feels like: {weather.feels_like_f}°F")
        print(f"  ✓ Wind: {weather.wind_speed_mph} mph {weather.wind_direction_cardinal}")
        print(f"  ✓ Conditions: {weather.conditions}")
    else:
        print(f"  ✗ Error: {weather.fetch_error}")
