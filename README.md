# NFL RAG Application

A Retrieval-Augmented Generation (RAG) system for answering natural language questions about NFL statistics, games, players, and betting data.

## Overview

This application combines semantic search over 12 years of NFL data (2014-2025) with local LLM generation to provide accurate, sourced answers to questions about professional football.

**Example queries:**
- "How did Patrick Mahomes perform against the Bills in the playoffs?"
- "What was the coldest NFL game in 2023?"
- "Compare Travis Kelce and Tyreek Hill's stats in the Super Bowl"
- "Did the Chiefs cover the spread against the Dolphins?"

## Features

- **Natural Language Queries**: Ask questions in plain English
- **12 Years of Data**: Comprehensive NFL data from 2014-2025 seasons
- **Semantic Search**: Find relevant information even with different wording
- **Local LLM**: Uses Ollama for privacy-focused, offline generation
- **Weather Data**: Game conditions including temperature, wind, precipitation
- **Betting Data**: Spreads, over/unders, and cover results
- **REST API**: FastAPI backend for easy integration
- **Source Citations**: Every answer includes relevant source chunks

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        User Question                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FastAPI Backend                            │
│                    (src/api/main.py)                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      RAG Pipeline                               │
│                   (src/rag/pipeline.py)                         │
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │   Query     │  │  Retrieval  │  │      Generation         │ │
│  │ Processing  │─▶│  (ChromaDB) │─▶│       (Ollama)          │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Answer + Sources                             │
└─────────────────────────────────────────────────────────────────┘
```

## Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| Data Source | nflreadpy | NFL statistics and game data (via nflverse) |
| Vector Database | ChromaDB | Semantic search and storage |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) | Text to vector conversion |
| LLM | Ollama (llama3.1) | Answer generation |
| API Framework | FastAPI | REST API endpoints |
| Language | Python 3.10+ | Application code |

## Project Structure

```
nfl-rag-app/
├── README.md                 # This file
├── requirements.txt          # Python dependencies
├── .env                      # Environment configuration
│
├── frontend/                 # React frontend application
│   ├── src/                  # React source code
│   ├── package.json          # Node dependencies
│   └── vite.config.ts        # Vite configuration
│
├── src/
│   ├── config.py             # Application settings
│   │
│   ├── api/                  # FastAPI REST API
│   │   ├── __init__.py
│   │   └── main.py           # API endpoints
│   │
│   ├── ingestion/            # Data loading
│   │   ├── scraper.py        # nflverse data downloader
│   │   ├── stadiums.py       # Stadium coordinates
│   │   └── weather.py        # Weather data enrichment
│   │
│   ├── processing/           # Text processing
│   │   ├── chunker.py        # Document chunking
│   │   ├── processor.py      # Processing orchestration
│   │   └── templates.py      # Text templates for chunks
│   │
│   ├── retrieval/            # Vector search
│   │   ├── embedder.py       # Embedding generation
│   │   ├── indexer.py        # Index building
│   │   └── vector_store.py   # ChromaDB wrapper
│   │
│   └── rag/                  # RAG pipeline
│       ├── llm.py            # Ollama client
│       ├── pipeline.py       # Main RAG orchestration
│       └── prompts.py        # Prompt templates
│
├── data/
│   ├── raw/                  # Downloaded NFL data (JSON)
│   └── processed/            # Processed chunks (JSON)
│
└── chroma_db/                # Vector database storage
```

## Installation

### Prerequisites

- Python 3.10 or higher
- [Ollama](https://ollama.ai) installed and running
- ~2GB disk space for data and models

### Setup

```bash
# 1. Clone or create the project directory
mkdir nfl-rag-app && cd nfl-rag-app

# 2. Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Pull the LLM model
ollama pull llama3.1

# 5. Create .env file
cat > .env << EOF
DEBUG=false
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3.1
API_HOST=0.0.0.0
API_PORT=8000
EOF
```

### Load Data and Build Index

```bash
# 1. Download NFL data (2014-2025)
python -m src.ingestion.scraper --start-year 2014 --end-year 2025

# 2. Process data into chunks
python -m src.processing.processor

# 3. Build vector index
python -m src.retrieval.indexer --rebuild
```

**Data Loading Options:**
```bash
# Quick test with just one season
python -m src.ingestion.scraper --start-year 2023 --end-year 2023

# Skip weather data (faster)
python -m src.ingestion.scraper --start-year 2023 --end-year 2023 --no-weather

# Skip weekly player stats (smaller dataset)
python -m src.ingestion.scraper --start-year 2023 --end-year 2023 --no-weekly
```

This process takes approximately 15-20 minutes and creates:
- ~60,000+ text chunks
- ~200MB vector database

## Usage

### Start the API Server

```bash
# Make sure Ollama is running
ollama serve  # In a separate terminal

# Start the API
python -m src.api.main
```

The API will be available at:
- **API Root**: http://localhost:8000
- **Interactive Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | System health check |
| GET | `/stats` | Database statistics |
| POST | `/query` | Ask a question (full RAG) |
| GET | `/query?q=...` | Quick query via URL |
| POST | `/search` | Semantic search only |
| GET | `/search?q=...` | Quick search via URL |
| GET | `/chunks/{id}` | Get specific chunk |
| GET | `/teams` | List all NFL teams |

### Example Queries

```bash
# Ask a question
curl "http://localhost:8000/query?q=how+did+mahomes+play+against+the+bills"

# Search without LLM generation (faster)
curl "http://localhost:8000/search?q=freezing+playoff+game&team=KC&n=5"

# Check system health
curl http://localhost:8000/health
```

### Python Client

```python
import requests

# Ask a question
response = requests.post("http://localhost:8000/query", json={
    "query": "What was the coldest NFL playoff game?",
    "num_results": 5,
    "temperature": 0.7,
})
data = response.json()
print(data["answer"])

# Print sources
for source in data["sources"]:
    print(f"  - {source['chunk_type']}: {source['preview'][:100]}...")
```

### Interactive CLI

```bash
python -m src.rag.pipeline --interactive
```

## Data Coverage

### Seasons
- **Range**: 2014-2025 (12 seasons)
- **Games**: ~3,400 regular season + playoffs
- **Players**: ~15,000 unique players

### Chunk Types

| Type | Count | Description |
|------|-------|-------------|
| `player_game` | ~45,000 | Individual player performance per game |
| `player_season` | ~8,000 | Season totals for each player |
| `game_summary` | ~3,400 | Game results with scores and conditions |
| `player_bio` | ~6,000 | Player profiles (position, team, college) |
| `team_info` | 32 | Team information |

### Metadata Fields

Each chunk includes rich metadata for filtering:

- **Player**: `player_name`, `player_id`, `position`, `team`
- **Game**: `season`, `week`, `game_type`, `opponent`, `is_home`
- **Weather**: `temperature_f`, `temperature_category`, `wind_mph`, `venue_type`
- **Betting**: `team_spread`, `was_favorite`, `was_underdog`

### Weather Data Fields

Weather is fetched from the Open-Meteo Historical API for outdoor games. Dome games do not include weather data.

| Field | Description |
|-------|-------------|
| `temperature_f` | Temperature in Fahrenheit |
| `feels_like_f` | Wind chill / heat index |
| `humidity_pct` | Relative humidity |
| `precipitation_inches` | Total precipitation |
| `wind_speed_mph` | Wind speed |
| `wind_gust_mph` | Wind gusts |
| `wind_direction_cardinal` | Wind direction (N, NE, etc.) |
| `conditions` | Human-readable conditions (Clear, Overcast, Rain, Snow) |

### Example Chunks

**Player Game Chunk:**
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

**Game Summary Chunk:**
```
2023 NFL Playoff Week 20: MIA at KC
Date: 2024-01-13 at GEHA Field at Arrowhead Stadium
Coaches: Mike McDaniel (MIA) vs Andy Reid (KC)
Weather: -4°F (felt like -27°F), overcast, 18 mph NW wind.
Line: KC favored by 4.5 points, Over/Under: 48.5

Final: KC 26, MIA 7
KC covered as 4.5-point favorites.
The game went UNDER the 48.5 total (33 points scored).
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DEBUG` | `false` | Enable debug logging |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `llama3.1` | LLM model to use |
| `API_HOST` | `0.0.0.0` | API bind address |
| `API_PORT` | `8000` | API port |
| `CHROMA_PERSIST_DIRECTORY` | `./chroma_db` | Vector DB location |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Embedding model |

### Alternative LLM Models

```bash
# Faster, smaller model
ollama pull mistral
export OLLAMA_MODEL=mistral

# Larger, more capable model (requires more RAM)
ollama pull llama3.1:70b
export OLLAMA_MODEL=llama3.1:70b
```

## Performance

### Typical Response Times

| Component | Time |
|-----------|------|
| Query Processing | ~10ms |
| Embedding Generation | ~50ms |
| Vector Search | ~100-300ms |
| LLM Generation | ~2-5 seconds |
| **Total** | **~3-6 seconds** |

### Hardware Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| RAM | 8GB | 16GB |
| Storage | 2GB | 5GB |
| CPU | 4 cores | 8 cores |
| GPU | Not required | NVIDIA (for faster LLM) |

## How It Works

### 1. Data Ingestion
NFL data is downloaded using nflreadpy (a Python wrapper for nflverse data), including player statistics, game results, and schedules. Weather data is enriched using historical weather APIs based on stadium locations.

### 2. Chunking
Raw data is transformed into text chunks optimized for semantic search:
- Full team and player names (not just abbreviations)
- Natural language descriptions of weather conditions
- Context-rich formatting for better retrieval

### 3. Embedding & Indexing
Text chunks are converted to 384-dimensional vectors using sentence-transformers and stored in ChromaDB with metadata for filtering.

### 4. Query Processing
User queries are:
- Enhanced with full names (e.g., "Mahomes" → "Patrick Mahomes")
- Analyzed for metadata filters (team, player, playoff, weather)
- Converted to embeddings for semantic search

**Auto-Filtering**: The pipeline automatically extracts filters from natural language:

| Query Contains | Filter Applied |
|----------------|----------------|
| "Chiefs", "Kansas City" | `team: KC` |
| "playoff", "postseason" | `is_playoff: True` |
| "cold", "freezing" | `temperature_category: freezing` |
| "quarterback", "QB" | `position: QB` |

### 5. Retrieval
ChromaDB performs similarity search to find the most relevant chunks, optionally filtered by metadata.

**Metadata Filtering Examples:**
```python
from src.retrieval import build_metadata_filter

# Single filter
where = build_metadata_filter(team="KC")

# Multiple filters (AND)
where = build_metadata_filter(team="KC", position="QB", season=2023)

# Weather filters
where = build_metadata_filter(venue_type="outdoor", temperature_category="freezing")
```

### 6. Generation
Retrieved chunks are formatted into a prompt and sent to Ollama, which generates a natural language answer citing the sources.

## Troubleshooting

### "Ollama not available"
```bash
# Start Ollama server
ollama serve

# Verify it's running
curl http://localhost:11434/api/tags
```

### "Model not found"
```bash
# Pull the required model
ollama pull llama3.1
```

### Poor search results
- Try more specific queries
- Use metadata filters: `?team=KC&player=Patrick+Mahomes`
- Check if the data exists: use `/search` endpoint first

### Slow responses
- Use a smaller/faster model: `OLLAMA_MODEL=mistral`
- Reduce `num_results` parameter
- Use `/search` endpoint for retrieval-only queries

## Development

### Running Tests

```bash
# Test the complete RAG pipeline
python test_rag_pipeline.py

# Test retrieval and vector store
python test_retrieval.py

# Test data chunking
python test_chunking.py

# Test data loading
python test_data_loader.py

# Test weather enrichment
python test_weather.py
```

### Rebuilding the Index

```bash
# Full rebuild
python -m src.retrieval.indexer --rebuild

# Verify index
python -m src.retrieval.indexer --verify
```

### Adding New Data

```bash
# Download new season
python -m src.ingestion.scraper --start-year 2025 --end-year 2025

# Reprocess all data
rm data/processed/chunks.json
python -m src.processing.processor

# Rebuild index
python -m src.retrieval.indexer --rebuild
```

## React Frontend

The application includes a modern React frontend for interacting with the RAG API.

**Features:**
- Clean, responsive UI for asking questions
- Real-time answer display with source citations
- Collapsible source cards with metadata
- Search filters (team, season, data type)
- Query history within session
- Health status indicator
- Suggested queries for easy onboarding

**Technology Stack:**
- React 18 with TypeScript
- Vite for fast development
- Tailwind CSS for styling
- Axios for API calls
- TanStack Query for server state

### Running the Frontend

```bash
# Install dependencies
cd frontend
npm install

# Start development server
npm run dev
```

The frontend runs at http://localhost:5173 and expects the API at http://localhost:8000.

### Frontend Structure

```
frontend/
├── src/
│   ├── api/
│   │   └── client.ts         # Axios API client
│   ├── components/
│   │   ├── QueryInput.tsx    # Search input + submit
│   │   ├── AnswerDisplay.tsx # LLM response display
│   │   ├── SourcesList.tsx   # Collapsible sources
│   │   ├── FilterPanel.tsx   # Team/season filters
│   │   ├── HealthStatus.tsx  # API status indicator
│   │   └── LoadingSpinner.tsx
│   ├── hooks/
│   │   ├── useQuery.ts       # RAG query mutation
│   │   ├── useSearch.ts      # Semantic search
│   │   └── useHealth.ts      # Health polling
│   ├── types/
│   │   └── api.ts            # TypeScript interfaces
│   ├── App.tsx               # Main application
│   ├── main.tsx              # Entry point
│   └── index.css             # Tailwind imports
├── package.json
├── vite.config.ts
└── tailwind.config.js
```

---

## Future Enhancements

---

### Step 10: Docker Containerization
Package the application for easy deployment anywhere.

**Planned Components:**
- `Dockerfile` for the FastAPI backend
- `docker-compose.yml` for full stack (API + Ollama + ChromaDB)
- Volume mounts for persistent data
- Environment variable configuration
- Health checks and restart policies

**Example docker-compose.yml:**
```yaml
version: '3.8'
services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - OLLAMA_HOST=http://ollama:11434
    depends_on:
      - ollama
    volumes:
      - ./data:/app/data
      - ./chroma_db:/app/chroma_db

  ollama:
    image: ollama/ollama
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama

volumes:
  ollama_data:
```

**Deployment Options:**
- Local Docker Desktop
- AWS ECS / Fargate
- Google Cloud Run
- DigitalOcean App Platform
- Self-hosted with Docker Compose

---

### Step 11: Automated Testing
Add comprehensive test coverage for reliability.

**Test Categories:**

| Type | Purpose | Tools |
|------|---------|-------|
| Unit Tests | Test individual functions | pytest |
| Integration Tests | Test API endpoints | pytest + httpx |
| RAG Evaluation | Test answer quality | Custom metrics |
| Load Tests | Test performance under load | locust |

**Planned Test Files:**
```
tests/
├── unit/
│   ├── test_chunker.py
│   ├── test_embedder.py
│   ├── test_vector_store.py
│   └── test_prompts.py
├── integration/
│   ├── test_api_endpoints.py
│   ├── test_rag_pipeline.py
│   └── test_search_quality.py
├── evaluation/
│   ├── test_answer_relevance.py
│   ├── test_source_accuracy.py
│   └── benchmark_queries.json
└── conftest.py
```

**RAG Evaluation Metrics:**
- **Retrieval Precision**: Are the retrieved chunks relevant?
- **Answer Faithfulness**: Is the answer grounded in sources?
- **Answer Relevance**: Does the answer address the question?
- **Latency**: Response time benchmarks

---

### Step 12: Enhancements
Additional features to improve the user experience.

**Streaming Responses:**
```python
# Server-side (FastAPI)
@app.post("/query/stream")
async def query_stream(request: QueryRequest):
    async def generate():
        for chunk in pipeline.query_stream(request.query):
            yield f"data: {json.dumps({'chunk': chunk})}\n\n"
    return StreamingResponse(generate(), media_type="text/event-stream")

# Client-side (JavaScript)
const eventSource = new EventSource('/query/stream?q=...');
eventSource.onmessage = (event) => {
    const data = JSON.parse(event.data);
    appendToAnswer(data.chunk);
};
```

**Conversation History:**
- Multi-turn conversations with context
- Reference previous questions and answers
- "Follow-up" queries that understand context
- Session management and persistence

**Additional Enhancements:**
- [ ] Player comparison tool ("Compare Mahomes vs Allen in 2023")
- [ ] Season/career summaries on demand
- [ ] Fantasy football projections
- [ ] Game prediction analysis
- [ ] Historical trend analysis
- [ ] Export answers to PDF/Markdown
- [ ] Shareable query links
- [ ] User authentication and saved queries
- [ ] Rate limiting and API keys
- [ ] Caching layer for common queries
- [ ] Webhook notifications for new data

---

## Roadmap

| Phase | Status | Description |
|-------|--------|-------------|
| Data Ingestion | ✅ Complete | Load NFL data from nflverse |
| Weather Enrichment | ✅ Complete | Add historical weather data |
| Text Chunking | ✅ Complete | Process data into searchable chunks |
| Vector Indexing | ✅ Complete | Build ChromaDB embeddings |
| RAG Pipeline | ✅ Complete | Query processing and LLM generation |
| REST API | ✅ Complete | FastAPI backend |
| React Frontend | ✅ Complete | Web interface |
| Docker | 🔲 Planned | Containerization |
| Testing | 🔲 Planned | Automated test suite |
| Enhancements | 🔲 Planned | Streaming, history, etc. |

## License

This project is for educational purposes. NFL data is sourced from nflverse, which provides open-source NFL data.

## Acknowledgments

- [nflreadpy](https://github.com/nflverse/nflreadpy) - Python wrapper for nflverse data
- [nflverse](https://github.com/nflverse) - NFL data source
- [ChromaDB](https://www.trychroma.com/) - Vector database
- [Ollama](https://ollama.ai) - Local LLM runtime
- [FastAPI](https://fastapi.tiangolo.com/) - API framework
- [sentence-transformers](https://www.sbert.net/) - Embedding models