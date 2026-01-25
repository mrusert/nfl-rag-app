# Step 4.5: Weather Data Enrichment

## Overview

This step adds historical weather data to NFL games played in outdoor stadiums. Weather is fetched from the Open-Meteo Historical API and integrated directly into the schedules dataset.

## New Files Created

```
src/ingestion/
├── stadiums.py     # Stadium coordinates lookup (50+ stadiums)
├── weather.py      # Weather fetcher using Open-Meteo API
└── scraper.py      # Updated data loader with weather integration

test_weather.py     # Test script for weather functionality
examine_weather.py  # Script to analyze weather-enriched data
```

## New Dependencies

Add these to your `requirements.txt`:

```text
# Weather data
openmeteo-requests==1.2.0
requests-cache==1.2.0
retry-requests==2.0.0
```

Install them:

```bash
pip install openmeteo-requests requests-cache retry-requests
```

## How It Works

### 1. Stadium Lookup (`stadiums.py`)

Contains a comprehensive database of 50+ NFL stadiums including:
- Current stadiums (all 30 active venues)
- Historical stadiums (back to 2000)
- International venues (London, Mexico City, Germany)
- Name aliases (handles stadium renamings over time)

Each stadium includes:
- Latitude/longitude coordinates
- Roof type (outdoors, dome, retractable)
- Surface type (grass, turf)
- Years active

### 2. Weather Fetcher (`weather.py`)

Fetches from Open-Meteo's Historical Weather API:

| Field | Description |
|-------|-------------|
| `temperature_f` | Temperature in Fahrenheit |
| `feels_like_f` | Wind chill / heat index |
| `humidity_pct` | Relative humidity |
| `dew_point_f` | Dew point temperature |
| `pressure_mb` | Atmospheric pressure |
| `precipitation_inches` | Total precipitation |
| `rain_inches` | Rain amount |
| `snowfall_inches` | Snow amount |
| `wind_speed_mph` | Wind speed |
| `wind_gust_mph` | Wind gusts |
| `wind_direction_degrees` | Wind direction (0-360) |
| `wind_direction_cardinal` | Wind direction (N, NE, etc.) |
| `cloud_cover_pct` | Cloud coverage |
| `visibility_miles` | Visibility distance |
| `weather_code` | WMO weather code |
| `conditions` | Human-readable conditions |

### 3. Filtering Logic

Weather is only fetched for games where:
- `roof` = "outdoors" OR "open" (retractable roof open)

Skipped for:
- `roof` = "dome" (always indoor)
- `roof` = "closed" (retractable roof closed)

## Usage

### Run Tests First

```bash
python test_weather.py
```

Expected output:
```
============================================================
Weather Enrichment Tests
============================================================
Testing stadium lookup...
  ✓ 'Arrowhead Stadium' → GEHA Field at Arrowhead Stadium (39.05, -94.48)
  ✓ 'Lambeau Field' → Lambeau Field (44.50, -88.06)
  ...

Testing weather fetcher...
  ✓ Weather fetched successfully
    Temperature: -4.0°F
    Feels like: -27.0°F
    Wind: 18.5 mph NW
    Conditions: Overcast
  ...

✓ All tests passed!
```

### Download Data with Weather

```bash
# Full dataset (2020-2024) with weather AND weekly stats (default)
# This takes 15-20 minutes due to weather API calls
python -m src.ingestion.scraper --start-year 2020 --end-year 2024

# Quick test with just 2023
python -m src.ingestion.scraper --start-year 2023 --end-year 2023

# Without weather (faster, for testing)
python -m src.ingestion.scraper --start-year 2023 --end-year 2023 --no-weather

# Without weekly stats (smaller dataset)
python -m src.ingestion.scraper --start-year 2023 --end-year 2023 --no-weekly

# Minimal (no weather, no weekly) - fastest for testing
python -m src.ingestion.scraper --start-year 2023 --end-year 2023 --no-weather --no-weekly
```

**Note:** Data is fetched using `nflreadpy` (the replacement for the deprecated `nfl_data_py`).

### Examine Weather Data

After downloading:

```bash
python examine_weather.py
```

Output shows:
- Coldest game in dataset
- Hottest game in dataset
- Windiest game in dataset
- Weather conditions distribution
- Sample games with full weather details

## Example Weather Data

Here's what the weather looks like in a game record:

```json
{
  "game_id": "2024_20_MIA_KC",
  "season": 2023,
  "gameday": "2024-01-13",
  "gametime": "19:00",
  "home_team": "KC",
  "away_team": "MIA",
  "home_score": 26,
  "away_score": 7,
  "stadium": "GEHA Field at Arrowhead Stadium",
  "roof": "outdoors",
  "weather": {
    "temperature_f": -4.0,
    "feels_like_f": -27.1,
    "dew_point_f": -11.6,
    "humidity_pct": 68.0,
    "pressure_mb": 1028.5,
    "precipitation_inches": 0.0,
    "rain_inches": 0.0,
    "snowfall_inches": 0.0,
    "wind_speed_mph": 18.5,
    "wind_gust_mph": 33.6,
    "wind_direction_degrees": 315.0,
    "wind_direction_cardinal": "NW",
    "cloud_cover_pct": 100.0,
    "visibility_miles": 15.0,
    "weather_code": 3,
    "conditions": "Overcast",
    "is_outdoor_game": true,
    "weather_fetched": true,
    "fetch_error": null
  }
}
```

## How Weather Will Be Used in RAG

The weather data enables queries like:

- "How did Mahomes perform in cold weather games?"
- "What were the conditions for the Chiefs vs Dolphins playoff game?"
- "Show me games with snow in 2023"
- "Which games had wind over 20 mph?"
- "Compare passing stats in dome vs outdoor games"

The chunking step (Step 5) will incorporate weather context into game chunks, making this information retrievable.

## API Notes

### Open-Meteo

- **Free tier**: No API key required
- **Rate limit**: ~600 requests/minute (we use 30/min to be safe)
- **Historical data**: Available from 1940 onwards
- **Resolution**: Hourly data, 9km spatial resolution

### Handling Missing Data

- If stadium not found: `fetch_error` field explains why
- If API fails: Automatic retry with backoff
- Dome games: `is_outdoor_game: false`, no weather fetched

## Files Summary

| File | Purpose |
|------|---------|
| `src/ingestion/stadiums.py` | Stadium coordinates database |
| `src/ingestion/weather.py` | Open-Meteo API integration |
| `src/ingestion/scraper.py` | Main data loader (updated) |
| `test_weather.py` | Test the weather system |
| `examine_weather.py` | Analyze downloaded weather data |

## Next Steps

After completing this step:

1. Run `python test_weather.py` to verify setup
2. Run `python -m src.ingestion.scraper --start-year 2023 --end-year 2023` for a quick test
3. Run `python examine_weather.py` to see the results
4. Proceed to **Step 5: Text Processing & Chunking Strategies**