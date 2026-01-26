# Step 6: Embeddings & ChromaDB

## Overview

This step generates vector embeddings for all text chunks and stores them in ChromaDB for semantic search. This is the foundation of the RAG retrieval system.

## Files Created

```
src/retrieval/
├── __init__.py         # Module exports
├── embedder.py         # Embedding generation
├── vector_store.py     # ChromaDB integration
└── indexer.py          # Indexing pipeline

test_retrieval.py       # Test script
```

## Architecture

```
┌─────────────┐     ┌───────────────┐     ┌────────────┐
│  Chunks     │ ──▶ │   Embedder    │ ──▶ │  ChromaDB  │
│  (JSON)     │     │ (all-MiniLM)  │     │  (Vector)  │
└─────────────┘     └───────────────┘     └────────────┘
                           │                     │
                    384-dim vectors        Persistent
                                           Storage
```

## Components

### 1. NFLEmbedder (`embedder.py`)

Generates vector embeddings using sentence-transformers.

**Model:** `all-MiniLM-L6-v2`
- 384-dimensional embeddings
- Fast inference
- Good semantic similarity
- Runs locally (no API needed)

```python
from src.retrieval import NFLEmbedder

embedder = NFLEmbedder()

# Single text
embedding = embedder.embed_text("Patrick Mahomes threw for 4183 yards")
# Returns: list of 384 floats

# Multiple texts
embeddings = embedder.embed_texts(["Text 1", "Text 2", "Text 3"])
# Returns: list of 384-float lists

# Find similar
query_emb = embedder.embed_text("Chiefs quarterback stats")
similar = embedder.find_most_similar(query_emb, embeddings, top_k=3)
# Returns: [(index, similarity_score), ...]
```

---

### 2. NFLVectorStore (`vector_store.py`)

Stores and queries embeddings using ChromaDB.

**Features:**
- Persistent storage (survives restarts)
- Metadata filtering
- Semantic similarity search
- Hybrid search (semantic + filters)

```python
from src.retrieval import NFLVectorStore, build_metadata_filter

store = NFLVectorStore()

# Search
results = store.search("How did Mahomes perform?", n_results=5)

# Search with filters
where = build_metadata_filter(team="KC", position="QB")
results = store.search("passing yards", n_results=5, where=where)

# Get by ID
chunk = store.get_by_id("player_season_abc123")

# Stats
stats = store.get_stats()
print(f"Total chunks: {stats['total_chunks']}")
```

---

### 3. NFLIndexer (`indexer.py`)

Orchestrates the complete indexing pipeline.

```python
from src.retrieval import NFLIndexer

indexer = NFLIndexer()

# Build the index
indexer.build_index()

# Rebuild from scratch
indexer.build_index(rebuild=True)

# Verify index
indexer.verify_index()
```

---

## Usage

### Step 1: Test Components

```bash
python test_retrieval.py
```

Expected output:
```
Testing NFLEmbedder...
  ✓ Embedder initialized with model: all-MiniLM-L6-v2
  ✓ Single embedding: 384 dimensions
  ✓ Batch embedding: 3 texts embedded
  ✓ Similarity search correct

Testing NFLVectorStore...
  ✓ Vector store initialized
  ✓ Added 4 chunks
  ✓ Search found Mahomes
  ...

✓ All tests passed!
```

### Step 2: Build the Index

First, make sure you have chunks (from Step 5):
```bash
# If not done already
python -m src.processing.processor
```

Then build the index:
```bash
python -m src.retrieval.indexer
```

Expected output:
```
============================================================
NFL RAG Indexer
============================================================
Chunks file: data/processed/chunks.json
Vector store: chroma_db
============================================================

[1/2] Loading chunks...
  Loaded 31234 chunks

  Chunks by type:
    game_summary: 1100
    player_bio: 3000
    player_game: 25000
    player_season: 2100
    team_info: 34

[2/2] Indexing chunks (batch_size=100)...
Embedding & storing: 100%|████████| 313/313 [05:23<00:00]
✓ Added 31234 chunks to vector store

============================================================
Indexing Complete!
============================================================
Chunks indexed: 31234
Time elapsed: 323.4 seconds
Rate: 96.6 chunks/second

Vector store now contains: 31234 chunks
```

### Step 3: Verify the Index

```bash
python -m src.retrieval.indexer --verify
```

### Step 4: Test Queries

```bash
# Search for Mahomes
python -m src.retrieval.vector_store --search "Patrick Mahomes 2023 stats" -n 3

# Search with team filter
python -m src.retrieval.vector_store --search "quarterback" --team KC -n 3

# Search with chunk type filter
python -m src.retrieval.vector_store --search "cold weather" --type game_summary -n 3
```

---

## Metadata Filtering

ChromaDB supports filtering on metadata fields. Use `build_metadata_filter()` for common patterns:

```python
from src.retrieval import build_metadata_filter

# Single filter
where = build_metadata_filter(team="KC")
# {"team": "KC"}

# Multiple filters (AND)
where = build_metadata_filter(team="KC", position="QB", season=2023)
# {"$and": [{"team": "KC"}, {"position": "QB"}, {"season": 2023}]}

# Boolean filters
where = build_metadata_filter(was_underdog=True)
# {"was_underdog": true}

# Weather filters
where = build_metadata_filter(
    venue_type="outdoor",
    temperature_category="freezing"
)
```

### Available Metadata Fields

| Field | Type | Chunk Types | Description |
|-------|------|-------------|-------------|
| `chunk_type` | str | all | player_season, player_game, etc. |
| `team` | str | most | Team abbreviation |
| `player_name` | str | player_* | Player's name |
| `position` | str | player_* | Position (QB, RB, WR, etc.) |
| `season` | int | most | Season year |
| `week` | int | player_game, game_summary | Week number |
| `venue_type` | str | player_game, game_summary | outdoor or dome |
| `temperature_category` | str | outdoor games | freezing/cold/cool/warm/hot |
| `was_favorite` | bool | player_game | Team was favored |
| `was_underdog` | bool | player_game | Team was underdog |
| `home_covered` | bool | game_summary | Home team covered spread |
| `went_over` | bool | game_summary | Game went over total |

---

## Index Statistics

```bash
python -m src.retrieval.indexer --stats
```

Output:
```
Index Statistics
============================================================
  total_chunks: 31234
  collection_name: nfl_chunks
  embedding_model: all-MiniLM-L6-v2
  persist_directory: chroma_db
  metadata_fields: ['chunk_type', 'game_id', 'home_covered', ...]

Chunk type counts:
  game_summary: 1100
  player_bio: 3000
  player_game: 25000
  player_season: 2100
  team_info: 34
```

---

## Rebuilding the Index

If you need to rebuild:

```bash
# Rebuild completely
python -m src.retrieval.indexer --rebuild

# With different batch size (if memory issues)
python -m src.retrieval.indexer --rebuild --batch-size 50
```

---

## Performance Notes

### Indexing Time

For ~31,000 chunks:
- Embedding generation: ~4-5 minutes
- ChromaDB insertion: ~30 seconds
- Total: ~5-6 minutes

### Query Time

- Typical query: 50-100ms
- With filters: 50-150ms

### Storage

- ChromaDB database: ~200-500MB
- Depends on chunk count and text length

---

## Troubleshooting

**"No chunks file found"**
```bash
# Run the processor first
python -m src.processing.processor
```

**"Index already exists"**
```bash
# Use --rebuild to recreate
python -m src.retrieval.indexer --rebuild
```

**Out of memory during indexing**
```bash
# Reduce batch size
python -m src.retrieval.indexer --batch-size 25
```

**Slow embedding generation**
The first run downloads the model (~90MB). Subsequent runs use the cached model.

---

## Next Steps

After building the index:

1. **Step 7**: Build the RAG query pipeline (combine retrieval + LLM)
2. **Step 8**: Create the FastAPI backend
3. **Step 9**: Testing and evaluation