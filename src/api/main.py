"""
NFL RAG API - FastAPI backend for the NFL RAG application.

This module provides REST endpoints for:
- /agent - AI agent with SQL tools for precise statistics
- /query - RAG pipeline for narrative questions
- /search - Semantic search without LLM generation
- /feedback - Rating and feedback on responses
- /data - Data update and management

The API runs locally using Ollama for LLM inference.
"""

import logging
import time
import json
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.config import API_HOST, API_PORT, DEBUG, AGENT_MODEL

# Configure logging for this module
logger = logging.getLogger(__name__)
from src.rag.pipeline import NFLRAGPipeline, RAGResponse
from src.retrieval.vector_store import SearchResult
from src.agent.agent import NFLStatsAgent, AgentResponse


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
    agent: bool
    chunk_count: int
    model: str
    agent_model: Optional[str] = None


class StatsResponse(BaseModel):
    """Statistics response."""
    chunk_count: int
    chunk_types: dict[str, int]
    embedding_model: str
    llm_model: str


# =============================================================================
# Agent Models
# =============================================================================

class AgentRequest(BaseModel):
    """Request body for agent queries."""
    question: str = Field(..., description="The question to ask", min_length=1, max_length=1000)
    verbose: bool = Field(default=False, description="Include thinking process in response")

    class Config:
        json_schema_extra = {
            "example": {
                "question": "What is Patrick Mahomes' record against the Bills in the playoffs?",
                "verbose": False,
            }
        }


class ToolCallInfo(BaseModel):
    """Information about a tool call made by the agent."""
    tool: str
    arguments: dict
    success: bool
    error: Optional[str] = None


class AgentQueryResponse(BaseModel):
    """Response from an agent query."""
    answer: str
    tool_calls: list[ToolCallInfo]
    thinking: list[str]
    iterations: int
    total_time_ms: float
    model: str
    feedback_entry_id: Optional[str] = None


# =============================================================================
# Application Setup
# =============================================================================

app = FastAPI(
    title="NFL RAG API",
    description="""
    An AI-powered API for NFL statistics and game data.

    ## Two Query Modes

    **Agent Mode (`/agent`)** - Best for precise statistics:
    - Uses SQL queries for exact numbers
    - Rankings and comparisons
    - Calculations and aggregations
    - Example: "What is Mahomes' record against the Bills in the playoffs?"

    **RAG Mode (`/query`)** - Best for narrative questions:
    - Uses semantic search for context
    - Historical stories and descriptions
    - "Tell me about" style questions
    - Example: "Tell me about the famous 13-seconds Chiefs-Bills game"

    ## Data Coverage
    - 12 years of NFL data (2014-2025)
    - 217,000+ player game records
    - 3,200+ games with scores and conditions
    - All runs locally using Ollama
    """,
    version="2.0.0",
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

# Global instances (initialized on startup)
pipeline: Optional[NFLRAGPipeline] = None
agent: Optional[NFLStatsAgent] = None


# =============================================================================
# Startup/Shutdown Events
# =============================================================================

@app.on_event("startup")
async def startup_event():
    """
    Initialize all components on API startup.

    This runs once when the server starts and sets up:
    - RAG pipeline for semantic search
    - Agent with SQL tools
    - Feedback storage
    - Data updater
    """
    global pipeline, agent, feedback_storage, data_updater

    logger.info("Starting NFL RAG API initialization...")

    # Initialize RAG Pipeline (for semantic search and narrative questions)
    logger.info("Initializing NFL RAG Pipeline...")
    try:
        pipeline = NFLRAGPipeline()
        health = pipeline.health_check()

        logger.info(f"RAG Pipeline initialized: {health['chunk_count']} chunks, LLM={health['llm']}")
        print(f"  Vector store: {health['chunk_count']} chunks")
        print(f"  LLM available: {health['llm']}")
        print(f"  Model: {health['llm_model']}")

        if not health['healthy']:
            logger.warning("RAG Pipeline not fully healthy")
            if not health['llm']:
                logger.warning("Ollama not available - start with: ollama serve")
    except Exception as e:
        logger.exception(f"Failed to initialize RAG pipeline: {e}")
        pipeline = None

    # Initialize Agent (for SQL queries and precise statistics)
    logger.info("Initializing NFL Stats Agent...")
    try:
        agent = NFLStatsAgent()
        if agent.is_available():
            logger.info(f"Agent ready: model={agent.model}, tools={list(agent.tools.keys())}")
            print(f"  Agent ready (model: {agent.model})")
            print(f"  Tools: {list(agent.tools.keys())}")
        else:
            logger.warning(f"Agent model '{agent.model}' not available")
    except Exception as e:
        logger.exception(f"Failed to initialize agent: {e}")
        agent = None

    # Initialize Feedback Storage (for rating responses)
    logger.info("Initializing Feedback Storage...")
    try:
        feedback_storage = FeedbackStorage()
        stats = feedback_storage.stats()
        logger.info(f"Feedback storage initialized: {stats['total']} entries")
        print(f"  Feedback entries: {stats['total']}")
    except Exception as e:
        logger.exception(f"Failed to initialize feedback storage: {e}")
        feedback_storage = None

    # Initialize Data Updater (for updating NFL data)
    logger.info("Initializing Data Updater...")
    try:
        data_updater = NFLDataUpdater()
        info = data_updater.get_current_data_info()
        logger.info(f"Data updater initialized: seasons {info['seasons']['min']}-{info['seasons']['max']}")
        print(f"  Data: {info['seasons']['min']}-{info['seasons']['max']}, week {info['latest_week']}")
    except Exception as e:
        logger.exception(f"Failed to initialize data updater: {e}")
        data_updater = None

    logger.info("NFL RAG API initialization complete")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup resources on shutdown."""
    global pipeline
    logger.info("Shutting down NFL RAG API...")
    pipeline = None
    logger.info("NFL RAG API shutdown complete")


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

    agent_available = agent is not None and agent.is_available()

    return HealthResponse(
        status="healthy" if health["healthy"] and agent_available else "degraded",
        vector_store=health["vector_store"],
        llm=health["llm"],
        agent=agent_available,
        chunk_count=health["chunk_count"],
        model=health["llm_model"],
        agent_model=agent.model if agent else None,
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
    Ask a question about NFL data using RAG (Retrieval-Augmented Generation).

    This endpoint:
    1. Retrieves relevant chunks from the vector database
    2. Builds a prompt with the context
    3. Generates an answer using the LLM

    Best for narrative questions like "Tell me about the 13-seconds game".
    For precise statistics, use /agent instead.

    Returns the answer along with source citations.
    """
    logger.info(f"RAG query received: {request.query[:100]}...")
    p = get_pipeline()

    try:
        response = p.query(
            query=request.query,
            num_results=request.num_results,
            temperature=request.temperature,
            auto_filter=request.auto_filter,
        )

        logger.info(
            f"RAG query completed: sources={len(response.sources)}, "
            f"retrieval={response.retrieval_time_ms:.0f}ms, "
            f"generation={response.generation_time_ms:.0f}ms"
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
        logger.exception(f"RAG query failed: {e}")
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
# Agent Endpoints
# =============================================================================

def get_agent() -> NFLStatsAgent:
    """Get the agent instance or raise an error."""
    if agent is None:
        raise HTTPException(
            status_code=503,
            detail="Agent not initialized. Check server logs.",
        )
    return agent


@app.post("/agent", response_model=AgentQueryResponse, tags=["Agent"])
async def agent_query(request: AgentRequest):
    """
    Ask a question using the AI agent with tools.

    The agent automatically decides which tools to use:
    - SQL queries for precise statistics
    - Rankings for "who led the league" questions
    - Calculator for computations
    - Semantic search for narrative/context questions

    Better than /query for:
    - Statistics and numbers
    - Rankings and comparisons
    - Calculations and aggregations
    - Questions requiring precise data

    Response includes a feedback_entry_id that can be used with /feedback/rate
    to provide feedback on the response quality.
    """
    logger.info(f"Agent query received: {request.question[:100]}...")
    a = get_agent()

    try:
        # Run the agent's ReAct loop
        response = a.run(request.question, verbose=request.verbose)

        logger.info(
            f"Agent completed: iterations={response.iterations}, "
            f"tools={[tc['tool'] for tc in response.tool_calls]}, "
            f"time={response.total_time_ms:.0f}ms"
        )

        # Convert tool calls to response format
        tool_calls = [
            ToolCallInfo(
                tool=tc["tool"],
                arguments=tc["arguments"],
                success=tc["success"],
                error=tc.get("error"),
            )
            for tc in response.tool_calls
        ]

        # Save to feedback storage for later rating
        feedback_entry_id = None
        if feedback_storage is not None:
            entry = feedback_storage.add(
                question=request.question,
                response=response.answer,
                mode="agent",
                tool_calls=[tc["tool"] for tc in response.tool_calls],
                response_time_ms=response.total_time_ms,
            )
            feedback_entry_id = entry.id
            logger.debug(f"Saved feedback entry: {feedback_entry_id}")

        return AgentQueryResponse(
            answer=response.answer,
            tool_calls=tool_calls,
            thinking=response.thinking if request.verbose else [],
            iterations=response.iterations,
            total_time_ms=round(response.total_time_ms, 2),
            model=a.model,
            feedback_entry_id=feedback_entry_id,
        )

    except Exception as e:
        logger.exception(f"Agent query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/agent", response_model=AgentQueryResponse, tags=["Agent"])
async def agent_query_get(
    q: str = Query(..., description="Question to ask", min_length=1),
):
    """
    Quick agent query via GET request.

    Example: /agent?q=Who+led+the+NFL+in+passing+yards+in+2024
    """
    request = AgentRequest(question=q)
    return await agent_query(request)


# =============================================================================
# Feedback Endpoints
# =============================================================================

from src.feedback.storage import FeedbackStorage
from src.data.updater import NFLDataUpdater


class FeedbackRatingRequest(BaseModel):
    """Request to rate a feedback entry."""
    entry_id: str = Field(..., description="ID of the entry to rate")
    rating: str = Field(..., description="Rating: correct, incorrect, partial")
    correct_answer: Optional[str] = Field(None, description="The correct answer if rating is incorrect/partial")
    notes: Optional[str] = Field(None, description="Additional notes")


class FeedbackStatsResponse(BaseModel):
    """Feedback statistics."""
    total: int
    by_rating: dict
    by_mode: dict
    exportable: int


# Global feedback storage (initialized in startup_event)
feedback_storage: Optional[FeedbackStorage] = None

# Data updater
data_updater: Optional[NFLDataUpdater] = None


@app.post("/feedback/rate", tags=["Feedback"])
async def rate_feedback(request: FeedbackRatingRequest):
    """
    Rate a response from a previous query.

    Use the entry_id from an agent response to provide feedback.
    """
    if feedback_storage is None:
        raise HTTPException(status_code=503, detail="Feedback storage not initialized")

    entry = feedback_storage.rate(
        entry_id=request.entry_id,
        rating=request.rating,
        correct_answer=request.correct_answer,
        notes=request.notes,
    )

    if entry is None:
        raise HTTPException(status_code=404, detail=f"Entry not found: {request.entry_id}")

    return {"status": "success", "entry_id": entry.id, "rating": entry.rating}


@app.get("/feedback/stats", response_model=FeedbackStatsResponse, tags=["Feedback"])
async def get_feedback_stats():
    """Get feedback statistics."""
    if feedback_storage is None:
        raise HTTPException(status_code=503, detail="Feedback storage not initialized")

    return feedback_storage.stats()


@app.get("/feedback/recent", tags=["Feedback"])
async def get_recent_feedback(limit: int = Query(default=10, ge=1, le=50)):
    """Get recent feedback entries."""
    if feedback_storage is None:
        raise HTTPException(status_code=503, detail="Feedback storage not initialized")

    entries = feedback_storage.recent(limit)
    return [e.to_dict() for e in entries]


@app.get("/feedback/incorrect", tags=["Feedback"])
async def get_incorrect_feedback():
    """Get all incorrect/partial feedback entries for review."""
    if feedback_storage is None:
        raise HTTPException(status_code=503, detail="Feedback storage not initialized")

    entries = feedback_storage.get_incorrect()
    return [e.to_dict() for e in entries]


# =============================================================================
# Data Update Endpoints
# =============================================================================

@app.get("/data/info", tags=["Data"])
async def get_data_info():
    """Get information about current data in the database."""
    if data_updater is None:
        raise HTTPException(status_code=503, detail="Data updater not initialized")

    return data_updater.get_current_data_info()


@app.get("/data/check-updates", tags=["Data"])
async def check_for_updates():
    """Check if new NFL data is available."""
    if data_updater is None:
        raise HTTPException(status_code=503, detail="Data updater not initialized")

    return data_updater.check_for_updates()


@app.post("/data/update", tags=["Data"])
async def trigger_update(full: bool = False):
    """
    Trigger a data update.

    Args:
        full: If True, do a full refresh. Otherwise, update current season only.
    """
    if data_updater is None:
        raise HTTPException(status_code=503, detail="Data updater not initialized")

    if full:
        result = data_updater.full_refresh()
    else:
        result = data_updater.update_current_season()

    return {
        "success": result.success,
        "timestamp": result.timestamp,
        "tables_updated": result.tables_updated,
        "errors": result.errors,
        "duration_seconds": result.duration_seconds,
    }


@app.get("/data/update-history", tags=["Data"])
async def get_update_history(limit: int = Query(default=10, ge=1, le=50)):
    """Get history of data updates."""
    if data_updater is None:
        raise HTTPException(status_code=503, detail="Data updater not initialized")

    return data_updater.get_update_history(limit)


# =============================================================================
# Run with Uvicorn
# =============================================================================

if __name__ == "__main__":
    import uvicorn

    # Configure logging for direct run
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    print(f"Starting NFL RAG API on {API_HOST}:{API_PORT}")
    print(f"Documentation: http://localhost:{API_PORT}/docs")

    uvicorn.run(
        "src.api.main:app",
        host=API_HOST,
        port=API_PORT,
        reload=DEBUG,
    )