# Step 7: Building the RAG Pipeline

## Overview

This step builds the complete RAG (Retrieval-Augmented Generation) pipeline that:
1. Takes a natural language question
2. Retrieves relevant NFL data from ChromaDB
3. Generates an answer using a local LLM (Ollama)
4. Returns the answer with source citations

## Files Created

```
src/rag/
├── __init__.py         # Module exports
├── llm.py              # Ollama LLM client
├── prompts.py          # Prompt templates and builder
└── pipeline.py         # Main RAG orchestration

test_rag.py             # Test script
```

## Prerequisites

### 1. Install Ollama

```bash
# macOS
brew install ollama

# Linux
curl -fsSL https://ollama.ai/install.sh | sh

# Windows
# Download from https://ollama.ai
```

### 2. Start Ollama Server

```bash
ollama serve
```

### 3. Pull a Model

```bash
# Recommended: llama3.1 (good balance of quality and speed)
ollama pull llama3.1

# Alternatives:
# ollama pull mistral      # Fast, good quality
# ollama pull llama3.1:70b # Best quality (needs 48GB+ RAM)
```

## Usage

### Quick Test

```bash
# Check if everything is working
python test_rag.py
```

### Single Query

```bash
python -m src.rag.pipeline --query "How did Mahomes play in the cold playoff game against the Dolphins?"
```

### Interactive Mode

```bash
python -m src.rag.pipeline --interactive
```

This starts an interactive session where you can ask multiple questions:

```
NFL RAG Assistant - Interactive Mode
============================================================
Ask questions about NFL games, players, and statistics.
Type 'quit' or 'exit' to end the session.
Type 'clear' to clear conversation history.
============================================================

📋 Your question: What was the coldest NFL playoff game?

🔍 Searching... Found 5 relevant sources.

------------------------------------------------------------
🏈 Answer:

Based on the data I have, one of the coldest NFL playoff games was the 
2023 Wild Card game between the Miami Dolphins and Kansas City Chiefs 
at Arrowhead Stadium on January 13, 2024. The weather conditions were 
extremely cold at -3°F (feeling like -16°F) with 13 mph northwest winds.

The Chiefs won this game 26-7, with Kansas City covering as 4.5-point 
underdogs. The game went well under the 43.5 total...
------------------------------------------------------------
Sources:
  1. 2023 Week 19: MIA @ KC (relevance: 0.62)
  2. Patrick Mahomes - 2023 Week 19 (relevance: 0.58)
  ...

⏱️ Time: 2847ms (retrieval: 45ms, generation: 2802ms)
```

### Python API

```python
from src.rag import NFLRAGPipeline

# Initialize
pipeline = NFLRAGPipeline()

# Check health
health = pipeline.health_check()
print(f"Ready: {health['healthy']}")

# Query
response = pipeline.query("Who won the Chiefs Dolphins playoff game?")

print(response.answer)
print(response.format_sources())
print(f"Time: {response.total_time_ms}ms")
```

## Configuration

### Environment Variables

Set in `.env` file:

```bash
# Ollama settings
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3.1

# Debug mode
DEBUG=false
```

### Pipeline Options

```python
pipeline = NFLRAGPipeline(
    default_num_results=5,      # Chunks to retrieve
    default_temperature=0.7,    # LLM creativity (0-1)
)

# Query with options
response = pipeline.query(
    query="Tell me about Mahomes",
    num_results=10,             # Override default
    temperature=0.3,            # More focused
    auto_filter=True,           # Extract filters from query
)
```

## Features

### Auto-Filtering

The pipeline automatically extracts filters from queries:

| Query Contains | Filter Applied |
|----------------|----------------|
| "Chiefs", "Kansas City" | `team: KC` |
| "playoff", "postseason" | `is_playoff: True` |
| "cold", "freezing" | `temperature_category: freezing` |
| "quarterback", "QB" | `position: QB` |

### Streaming Responses

```python
# Stream the response as it's generated
for chunk in pipeline.query_stream("Tell me about the game"):
    print(chunk, end="", flush=True)
```

### Conversation History

The pipeline maintains conversation history for context:

```python
pipeline.query("Who won the Chiefs Dolphins playoff game?")
pipeline.query("What was the score?")  # Knows we're talking about same game

# Clear history
pipeline.clear_history()
```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    User Question                        │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                  Query Processing                        │
│  • Extract filters (team, position, weather, etc.)      │
│  • Detect query type (comparison, stats, general)       │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                    Retrieval                             │
│  • Embed query using sentence-transformers              │
│  • Search ChromaDB with metadata filters                │
│  • Return top-k relevant chunks                         │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                  Prompt Building                         │
│  • Format retrieved chunks as context                   │
│  • Build system prompt (NFL expert persona)             │
│  • Combine into final prompt                            │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                   LLM Generation                         │
│  • Send prompt to Ollama                                │
│  • Generate natural language answer                     │
│  • Return with timing metrics                           │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                    RAG Response                          │
│  • Answer text                                          │
│  • Source citations                                     │
│  • Timing metrics                                       │
└─────────────────────────────────────────────────────────┘
```

## Example Queries

### Game Results
- "What was the score of the Chiefs Dolphins playoff game?"
- "Did the Eagles beat the Cowboys in week 10?"
- "Who won the Super Bowl in 2023?"

### Player Stats
- "How did Patrick Mahomes perform in cold weather games?"
- "What were Travis Kelce's stats in the 2023 season?"
- "Compare Josh Allen and Lamar Jackson's 2023 seasons"

### Weather & Conditions
- "What was the coldest NFL game this year?"
- "Show me games played in snow"
- "How do dome teams perform in outdoor cold games?"

### Betting & Spreads
- "Did the Chiefs cover the spread against the Dolphins?"
- "What games went over the total in week 15?"
- "How often do underdogs cover in playoff games?"

## Troubleshooting

### "Ollama not available"

```bash
# Make sure Ollama is running
ollama serve

# Check if it's accessible
curl http://localhost:11434/api/tags
```

### "Model not found"

```bash
# Pull the model
ollama pull llama3.1

# Or use a different model
python -m src.rag.pipeline --model mistral --interactive
```

### Slow responses

- Use a smaller model: `ollama pull llama3.1:8b`
- Reduce context: `--num-results 3`
- Check GPU availability (Ollama uses GPU if available)

### Poor answer quality

- Increase retrieval count: `--num-results 10`
- Lower temperature: `--temperature 0.3`
- Try a larger model: `ollama pull llama3.1:70b`

## Next Steps

After completing this step:

1. **Step 8**: Create FastAPI backend for the RAG system
2. **Step 9**: Testing and evaluation
3. **Step 10**: Deployment options

## Performance Notes

Typical response times:
- Retrieval: 30-100ms
- Generation (llama3.1): 2-5 seconds
- Total: 2-6 seconds

To speed up:
- Use a faster model (mistral, llama3.1:8b)
- Enable GPU acceleration
- Reduce retrieval count