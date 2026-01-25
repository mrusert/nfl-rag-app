# Step 5: Text Processing & Chunking Strategies

## Overview

This step transforms raw NFL data into natural language text chunks that can be embedded and retrieved by our RAG system. Good chunking is critical for RAG quality.

## Files Created

```
src/processing/
├── __init__.py         # Module exports
├── templates.py        # Natural language templates
├── chunker.py          # Main chunking logic
└── processor.py        # Pipeline orchestrator

test_chunking.py        # Test script
```

## Chunk Types

### 1. Player Season Chunks (`player_season`)

Aggregated statistics for a player's entire season.

**Example:**
```
Patrick Mahomes (QB, KC) - 2023 Season Statistics
Passing: 4183 yards, 27 TDs, 14 INTs (401/597, 67.2% completion)
Rushing: 389 yards, 2 TDs on 75 carries (5.2 YPC)
Fantasy Points (PPR): 325.5
```

**Use cases:**
- "How did Mahomes do in 2023?"
- "Compare Brady and Rodgers' 2022 seasons"

---

### 2. Player Game Chunks (`player_game`)

Individual game performance with full context including weather, betting lines, and rest days.

**Example:**
```
Patrick Mahomes (QB, KC) - 2023 Playoffs Week 20 vs MIA (home)
Date: 2024-01-13
Rest: 14 days (opponent had 7 days)
KC was favored by 4.5 points
Weather: -4°F (felt like -27°F), overcast, 18 mph NW wind.
Result: KC won 26-7

Passing: 262 yards, 2 TDs, 0 INTs (23/35)
Rushing: 29 yards, 0 TDs on 4 carries
Fantasy Points (PPR): 22.5
```

**Use cases:**
- "How did Mahomes play in cold weather?"
- "Mahomes' performance as a favorite"
- "Best QB performances against Miami"

---

### 3. Game Summary Chunks (`game_summary`)

Complete game information including both teams, coaches, betting results, and weather.

**Example:**
```
2023 NFL Playoff Week 20: MIA at KC
Date: 2024-01-13 at GEHA Field at Arrowhead Stadium
Coaches: Mike McDaniel (MIA) vs Andy Reid (KC)
KC had a significant rest advantage (14 days vs 7 days).
Weather: -4°F (felt like -27°F), overcast, 18 mph NW wind.
Line: KC favored by 4.5 points
Over/Under: 48.5

Final: KC 26, MIA 7
KC won by 19 points
KC covered as 4.5-point favorites.
The game went UNDER the 48.5 total (33 points scored).
```

**Use cases:**
- "Did the Chiefs cover against the Dolphins?"
- "What were the conditions for the coldest playoff game?"
- "Games where the underdog covered"

---

### 4. Player Bio Chunks (`player_bio`)

Player biographical and roster information.

**Example:**
```
Patrick Mahomes - Player Profile
Position: QB
Team: KC
Jersey Number: #15
Height/Weight: 6-3, 230 lbs
Age: 28
Experience: 7 years
College: Texas Tech
Draft: 2017, Round 1, Pick 10
```

**Use cases:**
- "What college did Mahomes attend?"
- "Who are the rookies on the Chiefs?"

---

### 5. Team Info Chunks (`team_info`)

Team metadata.

**Example:**
```
Kansas City Chiefs (KC) - Team Profile
Conference: AFC
Division: AFC West
City: Kansas City
Stadium: GEHA Field at Arrowhead Stadium
```

---

## Metadata Fields

Each chunk includes rich metadata for filtering:

### Player Chunks
| Field | Description |
|-------|-------------|
| `player_name` | Player's display name |
| `player_id` | Unique identifier |
| `team` | Team abbreviation |
| `position` | Position (QB, RB, WR, etc.) |
| `season` | Season year |

### Game-Level Metadata
| Field | Description |
|-------|-------------|
| `game_id` | Unique game identifier |
| `week` | Week number |
| `game_type` | REG, POST, SB, etc. |
| `opponent` | Opponent team |
| `is_home` | Whether player was at home |

### Weather Metadata
| Field | Description |
|-------|-------------|
| `venue_type` | "outdoor" or "dome" |
| `temperature_f` | Temperature in Fahrenheit |
| `temperature_category` | freezing/cold/cool/warm/hot |
| `wind_mph` | Wind speed |

### Betting Metadata
| Field | Description |
|-------|-------------|
| `spread_line` | Point spread |
| `was_favorite` | Team was favored |
| `was_underdog` | Team was underdog |
| `home_covered` | Home team covered spread |
| `went_over` | Game went over total |

---

## Usage

### Run Tests

```bash
python test_chunking.py
```

### Process Data

```bash
# Full processing (after loading data)
python -m src.processing.processor

# Show sample chunks
python -m src.processing.processor --show-samples

# Skip player-game chunks (faster, smaller)
python -m src.processing.processor --no-player-games
```

### In Python

```python
from src.processing import NFLDataProcessor

# Initialize
processor = NFLDataProcessor()

# Process all data
chunks = processor.process_all()

# Filter chunks
cold_weather_games = processor.search_chunks(
    chunks,
    chunk_type="player_game",
    temperature_category="freezing"
)

# Get samples
samples = processor.get_sample_chunks(chunks, n_per_type=3)
```

---

## Expected Output

For a typical 4-year dataset (2020-2024):

| Chunk Type | Approximate Count |
|------------|-------------------|
| team_info | ~35 |
| player_bio | ~3,000 |
| player_season | ~2,500 |
| game_summary | ~1,100 |
| player_game | ~25,000 |
| **Total** | **~31,000** |

---

## Chunking Philosophy

### Why These Chunk Types?

1. **Self-contained**: Each chunk has enough context to be understood alone
2. **Query-aligned**: Chunks match how users ask questions
3. **Metadata-rich**: Enables filtering before semantic search
4. **Appropriately sized**: ~200-500 tokens per chunk (ideal for embeddings)

### Weather Integration

Weather is included in:
- `player_game` chunks: Shows conditions for that performance
- `game_summary` chunks: Full game weather context

This enables queries like:
- "Best QB performances in snow"
- "How does Mahomes perform in cold weather?"
- "Games affected by wind"

### Betting Integration

Betting data enables:
- "Did the Chiefs cover against the Raiders?"
- "Games where underdogs won outright"
- "Over/under trends for dome games"

---

## Next Steps

After running the processor:

1. **Step 6**: Generate embeddings for all chunks
2. **Step 7**: Store in ChromaDB with metadata
3. **Step 8**: Build the RAG query pipeline

---

## Troubleshooting

**"No data files found"**
```bash
# Run the data loader first
python -m src.ingestion.scraper --start-year 2020 --end-year 2024
```

**"Missing weather data"**
Weather is only available for outdoor games. Dome games will show `venue_type: "dome"` in metadata.

**Chunks too large/small**
Adjust thresholds in `NFLChunker`:
```python
chunker = NFLChunker(
    min_passing_yards=50,   # Lower = more chunks
    min_rushing_yards=10,
    min_receiving_yards=10,
)
```