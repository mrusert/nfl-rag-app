# Step 8: FastAPI Backend

## Overview

This step creates a REST API to expose the RAG pipeline, allowing any frontend or application to interact with the NFL data.

## Files Created

```
src/api/
├── __init__.py    # Module exports
└── main.py        # FastAPI application (~350 lines)
```

## Quick Start

### 1. Install Dependencies

Make sure FastAPI and Uvicorn are installed:

```bash
pip install fastapi uvicorn
```

### 2. Start the API Server

```bash
# Option 1: Run directly
python -m src.api.main

# Option 2: Use uvicorn (recommended for development)
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Access the API

- **API Root**: http://localhost:8000
- **Interactive Docs (Swagger)**: http://localhost:8000/docs
- **Alternative Docs (ReDoc)**: http://localhost:8000/redoc

## API Endpoints

### Info Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | API information |
| GET | `/health` | Health check |
| GET | `/stats` | System statistics |
| GET | `/teams` | List all NFL teams |

### RAG Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/query` | Ask a question (full RAG) |
| GET | `/query?q=...` | Quick query via URL |

### Search Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/search` | Semantic search (no LLM) |
| GET | `/search?q=...` | Quick search via URL |

### Data Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/chunks/{id}` | Get a specific chunk |

## Usage Examples

### Ask a Question (POST)

```bash
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How did Mahomes perform against the Bills in the playoffs?",
    "num_results": 5,
    "temperature": 0.7
  }'
```

### Ask a Question (GET)

```bash
curl "http://localhost:8000/query?q=who+won+super+bowl+2023"
```

### Semantic Search (POST)

```bash
curl -X POST "http://localhost:8000/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "cold weather games",
    "num_results": 10,
    "team": "KC"
  }'
```

### Semantic Search (GET)

```bash
curl "http://localhost:8000/search?q=mahomes+playoff&team=KC&n=5"
```

### Health Check

```bash
curl "http://localhost:8000/health"
```

### Get Statistics

```bash
curl "http://localhost:8000/stats"
```

## Response Examples

### Query Response

```json
{
  "answer": "Patrick Mahomes has played in several playoff games against the Bills...",
  "sources": [
    {
      "chunk_id": "player_game_abc123",
      "chunk_type": "player_game",
      "score": 0.8234,
      "preview": "Patrick Mahomes, QB for the Kansas City Chiefs...",
      "metadata": {
        "player_name": "Patrick Mahomes",
        "team": "KC",
        "opponent": "BUF",
        "season": 2021,
        "week": 20
      }
    }
  ],
  "query": "How did Mahomes perform against the Bills in the playoffs?",
  "model": "llama3.1",
  "retrieval_time_ms": 45.23,
  "generation_time_ms": 2341.56,
  "total_time_ms": 2386.79
}
```

### Search Response

```json
{
  "results": [
    {
      "chunk_id": "game_summary_xyz789",
      "chunk_type": "game_summary",
      "score": 0.7156,
      "preview": "2021 NFL Divisional Playoff Round: Buffalo Bills at Kansas City Chiefs...",
      "metadata": {...}
    }
  ],
  "query": "cold weather games",
  "total_results": 10,
  "time_ms": 52.34
}
```

### Health Response

```json
{
  "status": "healthy",
  "vector_store": true,
  "llm": true,
  "chunk_count": 65432,
  "model": "llama3.1"
}
```

## Configuration

Environment variables (set in `.env`):

```bash
# API settings
API_HOST=0.0.0.0
API_PORT=8000

# Enable auto-reload for development
DEBUG=true
```

## Error Handling

The API returns appropriate HTTP status codes:

| Code | Meaning |
|------|---------|
| 200 | Success |
| 400 | Bad request (invalid parameters) |
| 404 | Not found (chunk ID doesn't exist) |
| 422 | Validation error (Pydantic) |
| 500 | Server error |
| 503 | Service unavailable (pipeline not ready) |

## CORS

CORS is enabled for all origins by default. For production, update `allow_origins` in `main.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-frontend.com"],
    ...
)
```

## Python Client Example

```python
import requests

BASE_URL = "http://localhost:8000"

# Ask a question
response = requests.post(f"{BASE_URL}/query", json={
    "query": "What was the coldest NFL game ever?",
    "num_results": 5,
})
data = response.json()
print(data["answer"])

# Search for chunks
response = requests.get(f"{BASE_URL}/search", params={
    "q": "freezing playoff",
    "team": "KC",
    "n": 10,
})
for result in response.json()["results"]:
    print(f"{result['score']:.2f}: {result['preview']}")
```

## JavaScript/Fetch Example

```javascript
// Ask a question
const response = await fetch('http://localhost:8000/query', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    query: 'Who won the Super Bowl in 2023?',
    num_results: 5,
  }),
});
const data = await response.json();
console.log(data.answer);
```

## Next Steps

After the API is running:

1. **Step 9**: Add tests and evaluation
2. **Step 10**: Build a frontend (React, Vue, etc.)
3. **Step 11**: Deploy (Docker, cloud hosting)

## Troubleshooting

### "RAG pipeline not initialized"

The vector store or LLM isn't ready. Check:
- Is Ollama running? `ollama serve`
- Is the vector store built? `python -m src.retrieval.indexer --verify`

### Slow responses

- LLM generation is the bottleneck (~2-5 seconds)
- Use `/search` endpoint for faster retrieval-only queries
- Consider a faster model: `OLLAMA_MODEL=mistral`

### CORS errors

If accessing from a browser, make sure CORS is configured correctly in `main.py`.