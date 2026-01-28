"""
NFL RAG API - FastAPI backend for the NFL RAG application.

Provides REST endpoints for:
- Querying the RAG pipeline
- Health checks
- Statistics and metadata
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional
import time
import json

from src.config import API_HOST, API_PORT, DEBUG
from src.rag.pipeline import NFLRAGPipeline, RAGResponse
from src.retrieval.vector_store import SearchResult


# =============================================================================
# Pydantic Models for Request/Response
# =============================================================================

class QueryRequest(BaseModel):
    """Request body for RAG queries."""
    query: str = Field(..., description="The question to ask", min_length=1, max_length=1000)
    num_results: int = Field(default=5, description="Number of chunks to retrieve", ge=1, le=20)
    temperature: float = Field(default=0.7, description="LLM temperature", ge=0.0, le=1.0)
    auto_filter: bool = Field(default=True, description="Auto-extract filters from query")
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "How did Patrick Mahomes perform against the Bills in the playoffs?",
                "num_results": 5,
                "temperature": 0.7,
                "auto_filter": True,
            }
        }


class SourceInfo(BaseModel):
    """Information about a source chunk."""
    chunk_id: str
    chunk_type: str
    score: float
    preview: str
    metadata: dict


class QueryResponse(BaseModel):
    """Response from a RAG query."""
    answer: str
    sources: list[SourceInfo]
    query: str
    model: str
    retrieval_time_ms: float
    generation_time_ms: float
    total_time_ms: float


class SearchRequest(BaseModel):
    """Request body for semantic search (without LLM generation)."""
    query: str = Field(..., description="Search query", min_length=1, max_length=500)
    num_results: int = Field(default=10, description="Number of results", ge=1, le=50)
    chunk_type: Optional[str] = Field(default=None, description="Filter by chunk type")
    team: Optional[str] = Field(default=None, description="Filter by team abbreviation")
    player_name: Optional[str] = Field(default=None, description="Filter by player name")
    season: Optional[int] = Field(default=None, description="Filter by season year")
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "cold weather playoff games",
                "num_results": 10,
                "team": "KC",
            }
        }


class SearchResponse(BaseModel):
    """Response from a semantic search."""
    results: list[SourceInfo]
    query: str
    total_results: int
    time_ms: float


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    vector_store: bool
    llm: bool
    chunk_count: int
    model: str


class StatsResponse(BaseModel):
    """Statistics response."""
    chunk_count: int
    chunk_types: dict[str, int]
    embedding_model: str
    llm_model: str


# =============================================================================
# Application Setup
# =============================================================================

app = FastAPI(
    title="NFL RAG API",
    description="""
    A Retrieval-Augmented Generation (RAG) API for NFL statistics and game data.
    
    Ask questions about:
    - Player statistics and performance
    - Game results and scores
    - Weather conditions and their impact
    - Betting lines and outcomes
    - Historical comparisons
    
    The API uses semantic search over 12 years of NFL data (2014-2025) and 
    generates answers using a local LLM (Ollama).
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global pipeline instance (initialized on startup)
pipeline: Optional[NFLRAGPipeline] = None


# =============================================================================
# Startup/Shutdown Events
# =============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize the RAG pipeline on startup."""
    global pipeline
    
    print("Initializing NFL RAG Pipeline...")
    try:
        pipeline = NFLRAGPipeline()
        health = pipeline.health_check()
        
        print(f"  Vector store: {health['chunk_count']} chunks")
        print(f"  LLM available: {health['llm']}")
        print(f"  Model: {health['llm_model']}")
        
        if not health['healthy']:
            print("⚠️  Warning: Pipeline not fully healthy")
            if not health['llm']:
                print("   - Ollama not available. Start with: ollama serve")
    except Exception as e:
        print(f"❌ Failed to initialize pipeline: {e}")
        pipeline = None


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    global pipeline
    pipeline = None
    print("NFL RAG API shutdown complete")


# =============================================================================
# Helper Functions
# =============================================================================

def get_pipeline() -> NFLRAGPipeline:
    """Get the pipeline instance or raise an error."""
    if pipeline is None:
        raise HTTPException(
            status_code=503,
            detail="RAG pipeline not initialized. Check server logs.",
        )
    return pipeline


def search_result_to_source_info(result: SearchResult) -> SourceInfo:
    """Convert a SearchResult to a SourceInfo response model."""
    return SourceInfo(
        chunk_id=result.chunk_id,
        chunk_type=result.metadata.get("chunk_type", "unknown"),
        score=round(result.score, 4),
        preview=result.text[:200] + "..." if len(result.text) > 200 else result.text,
        metadata=result.metadata,
    )


# =============================================================================
# API Endpoints
# =============================================================================

@app.get("/", tags=["Info"])
async def root():
    """Root endpoint with API information."""
    return {
        "name": "NFL RAG API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health", response_model=HealthResponse, tags=["Info"])
async def health_check():
    """Check the health of the API and its components."""
    p = get_pipeline()
    health = p.health_check()
    
    return HealthResponse(
        status="healthy" if health["healthy"] else "degraded",
        vector_store=health["vector_store"],
        llm=health["llm"],
        chunk_count=health["chunk_count"],
        model=health["llm_model"],
    )


@app.get("/stats", response_model=StatsResponse, tags=["Info"])
async def get_stats():
    """Get statistics about the RAG system."""
    p = get_pipeline()
    
    # Get chunk type counts
    chunk_types = p.vector_store.list_chunk_types()
    
    return StatsResponse(
        chunk_count=p.vector_store.count(),
        chunk_types=chunk_types,
        embedding_model=p.vector_store.embedding_model,
        llm_model=p.llm.model,
    )


@app.post("/query", response_model=QueryResponse, tags=["RAG"])
async def query(request: QueryRequest):
    """
    Ask a question about NFL data.
    
    This endpoint:
    1. Retrieves relevant chunks from the vector database
    2. Builds a prompt with the context
    3. Generates an answer using the LLM
    
    Returns the answer along with source citations.
    """
    p = get_pipeline()
    
    try:
        response = p.query(
            query=request.query,
            num_results=request.num_results,
            temperature=request.temperature,
            auto_filter=request.auto_filter,
        )
        
        sources = [search_result_to_source_info(s) for s in response.sources]
        
        return QueryResponse(
            answer=response.answer,
            sources=sources,
            query=response.query,
            model=response.model,
            retrieval_time_ms=round(response.retrieval_time_ms, 2),
            generation_time_ms=round(response.generation_time_ms, 2),
            total_time_ms=round(response.total_time_ms, 2),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/search", response_model=SearchResponse, tags=["Search"])
async def search(request: SearchRequest):
    """
    Perform a semantic search without LLM generation.
    
    Useful for:
    - Finding specific games or players
    - Exploring the data
    - Debugging retrieval quality
    """
    p = get_pipeline()
    
    start_time = time.time()
    
    # Build metadata filter
    from src.retrieval.vector_store import build_metadata_filter
    
    where = build_metadata_filter(
        chunk_type=request.chunk_type,
        team=request.team,
        player_name=request.player_name,
        season=request.season,
    )
    
    try:
        results = p.vector_store.search(
            query=request.query,
            n_results=request.num_results,
            where=where,
        )
        
        elapsed_ms = (time.time() - start_time) * 1000
        
        return SearchResponse(
            results=[search_result_to_source_info(r) for r in results],
            query=request.query,
            total_results=len(results),
            time_ms=round(elapsed_ms, 2),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/search", response_model=SearchResponse, tags=["Search"])
async def search_get(
    q: str = Query(..., description="Search query", min_length=1),
    n: int = Query(default=10, description="Number of results", ge=1, le=50),
    chunk_type: Optional[str] = Query(default=None, description="Filter by chunk type"),
    team: Optional[str] = Query(default=None, description="Filter by team"),
    player: Optional[str] = Query(default=None, description="Filter by player name"),
    season: Optional[int] = Query(default=None, description="Filter by season"),
):
    """
    Semantic search via GET request.
    
    Simpler interface for quick searches via URL.
    Example: /search?q=mahomes+playoff&team=KC&n=5
    """
    request = SearchRequest(
        query=q,
        num_results=n,
        chunk_type=chunk_type,
        team=team,
        player_name=player,
        season=season,
    )
    return await search(request)


@app.get("/query", response_model=QueryResponse, tags=["RAG"])
async def query_get(
    q: str = Query(..., description="Question to ask", min_length=1),
    n: int = Query(default=5, description="Number of sources", ge=1, le=20),
    temp: float = Query(default=0.7, description="Temperature", ge=0.0, le=1.0),
):
    """
    Ask a question via GET request.
    
    Simpler interface for quick queries via URL.
    Example: /query?q=who+won+the+super+bowl+in+2023
    """
    request = QueryRequest(
        query=q,
        num_results=n,
        temperature=temp,
    )
    return await query(request)


@app.get("/chunks/{chunk_id}", tags=["Data"])
async def get_chunk(chunk_id: str):
    """Get a specific chunk by ID."""
    p = get_pipeline()
    
    result = p.vector_store.get_by_id(chunk_id)
    
    if result is None:
        raise HTTPException(status_code=404, detail=f"Chunk not found: {chunk_id}")
    
    return {
        "chunk_id": result.chunk_id,
        "text": result.text,
        "metadata": result.metadata,
    }


@app.get("/teams", tags=["Data"])
async def list_teams():
    """List all NFL teams with their abbreviations."""
    teams = {
        "AFC East": {"BUF": "Buffalo Bills", "MIA": "Miami Dolphins", "NE": "New England Patriots", "NYJ": "New York Jets"},
        "AFC North": {"BAL": "Baltimore Ravens", "CIN": "Cincinnati Bengals", "CLE": "Cleveland Browns", "PIT": "Pittsburgh Steelers"},
        "AFC South": {"HOU": "Houston Texans", "IND": "Indianapolis Colts", "JAX": "Jacksonville Jaguars", "TEN": "Tennessee Titans"},
        "AFC West": {"DEN": "Denver Broncos", "KC": "Kansas City Chiefs", "LV": "Las Vegas Raiders", "LAC": "Los Angeles Chargers"},
        "NFC East": {"DAL": "Dallas Cowboys", "NYG": "New York Giants", "PHI": "Philadelphia Eagles", "WAS": "Washington Commanders"},
        "NFC North": {"CHI": "Chicago Bears", "DET": "Detroit Lions", "GB": "Green Bay Packers", "MIN": "Minnesota Vikings"},
        "NFC South": {"ATL": "Atlanta Falcons", "CAR": "Carolina Panthers", "NO": "New Orleans Saints", "TB": "Tampa Bay Buccaneers"},
        "NFC West": {"ARI": "Arizona Cardinals", "LA": "Los Angeles Rams", "SF": "San Francisco 49ers", "SEA": "Seattle Seahawks"},
    }
    return teams


# =============================================================================
# Run with Uvicorn
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    
    print(f"Starting NFL RAG API on {API_HOST}:{API_PORT}")
    print(f"Documentation: http://localhost:{API_PORT}/docs")
    
    uvicorn.run(
        "src.api.main:app",
        host=API_HOST,
        port=API_PORT,
        reload=DEBUG,
    )